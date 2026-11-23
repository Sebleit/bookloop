"""Tests for what happens when someone doesn't hand over their book.

Everyone in a swap meets at the same place and time, and nobody hands over a
book until everyone is there. Before any book has changed hands, a no-show
cancels the swap and everyone keeps their own book. Once a code has been
typed, everyone was there: a missing book is reported to a moderator, who
checks what happened, with a picture of the swap.
"""

from pathlib import Path

import pytest
from sqlalchemy import text
from streamlit.testing.v1 import AppTest

from bookloop.loop_picture import loop_dot
from bookloop.models import Loop, Profile, Trade
from bookloop.rules.handoffs import can_report_missing_handoff, no_show_outcome
from bookloop.services.notify import get_notifications
from bookloop.storage import reviews_repo, rounds_repo, swaps_repo
from seed import base as seed_base
from seed import rounds as seed_rounds
from seed import swaps as seed_swaps

APP = Path(__file__).resolve().parents[1] / "app.py"
CARLA = Profile("user-carla", "Carla", "student", "active", seed_base.CREATED_AT)
MORGAN = Profile("user-moderator", "Morgan", "moderator", "active", seed_base.CREATED_AT)


@pytest.fixture
def demo(database):
    with database.begin() as connection:
        seed_base.seed(connection)
        seed_swaps.seed(connection)
        seed_rounds.seed(connection)


def a_loop(status: str = "scheduled") -> Loop:
    return Loop("loop-1", "round", None, "round-1", status, "Library", None, None)


def a_trade(giver: str, receiver: str, status: str = "pending") -> Trade:
    return Trade(f"{giver}-{receiver}", "loop-1", f"copy-{giver}", giver, receiver, "1234", 0, status, None)


def code_for(trade_id: str) -> str:
    from bookloop.storage import db

    with db.transaction() as connection:
        return connection.execute(
            text("SELECT handoff_code FROM trades WHERE id = :id"), {"id": trade_id}
        ).scalar_one()


def open_app(user: Profile, page: str) -> AppTest:
    app = AppTest.from_file(str(APP), default_timeout=30)
    app.session_state["current_user"] = user
    app.session_state["_auth_mode"] = "laptop"
    app.run()
    return app.switch_page(page).run()


# --- Rules -----------------------------------------------------------------


def test_a_no_show_is_allowed_only_before_any_book_changes_hands():
    before = [a_trade("ana", "farah"), a_trade("farah", "eli"), a_trade("eli", "ana")]
    after = [a_trade("ana", "farah", "completed"), a_trade("farah", "eli"), a_trade("eli", "ana")]

    assert no_show_outcome(a_loop(), "ana", before).allowed is True
    refused = no_show_outcome(a_loop(), "ana", after)
    assert refused.allowed is False
    assert refused.reason.startswith("A book has already changed hands in this swap")


def test_a_missing_handoff_can_be_reported_only_once_a_book_has_changed_hands():
    before = [a_trade("ana", "farah"), a_trade("farah", "eli"), a_trade("eli", "ana")]
    after = [a_trade("ana", "farah", "completed"), a_trade("farah", "eli"), a_trade("eli", "ana")]

    assert can_report_missing_handoff(a_loop(), "eli", "farah", after).allowed is True
    assert "report a no-show instead" in can_report_missing_handoff(a_loop(), "eli", "farah", before).reason
    assert can_report_missing_handoff(a_loop(), "eli", "eli", after).allowed is False
    assert can_report_missing_handoff(a_loop(), "eli", "ana", after).reason == (
        "That person has already handed over their book."
    )
    assert can_report_missing_handoff(a_loop(), "ben", "farah", after).allowed is False
    assert can_report_missing_handoff(a_loop("cancelled"), "eli", "farah", after).allowed is False


# --- Storage ---------------------------------------------------------------


def test_after_a_handoff_a_no_show_is_refused_and_nothing_is_cancelled(demo):
    swaps_repo.confirm_handoff("trade-demo-pending-a", "user-carla", "3333")

    with pytest.raises(ValueError, match="A book has already changed hands"):
        swaps_repo.report_no_show("loop-demo-pending", "user-carla", "user-dina")

    statuses = {step.title: step.status for step in rounds_repo.loop_trades("loop-demo-pending")}
    assert statuses == {"Automate the Boring Stuff with Python": "completed", "A Mind for Numbers": "pending"}


def test_a_missing_handoff_goes_to_the_moderators_and_cancels_nothing(demo):
    swaps_repo.confirm_handoff("trade-demo-pending-a", "user-carla", "3333")

    reviews_repo.report_missing_handoff("loop-demo-pending", "user-carla", "user-dina")

    (report,) = reviews_repo.problem_reports()
    assert (report.reporter_name, report.giver_name, report.receiver_name, report.title) == (
        "Carla",
        "Dina",
        "Carla",
        "A Mind for Numbers",
    )
    assert "Carla says Dina didn't hand over “A Mind for Numbers”" in get_notifications("user-moderator")[0].text
    assert "Carla reported that you didn't hand over" in get_notifications("user-dina")[0].text
    with pytest.raises(ValueError, match="already been reported"):
        reviews_repo.report_missing_handoff("loop-demo-pending", "user-carla", "user-dina")

    reviews_repo.resolve_flag("user-moderator", report.trade_id)
    assert reviews_repo.problem_reports() == []


def test_in_a_round_loop_anyone_can_report_who_did_not_hand_over(demo):
    rounds_repo.run_round("round-demo")
    trades = {(trade.giver_id, trade.receiver_id): trade for trade in _round_trades("round-demo")}
    ana_to_farah = trades[("user-ana", "user-farah")]
    swaps_repo.confirm_handoff(ana_to_farah.id, "user-ana", code_for(ana_to_farah.id))

    reviews_repo.report_missing_handoff(ana_to_farah.loop_id, "user-eli", "user-farah")

    (report,) = reviews_repo.problem_reports()
    assert (report.reporter_name, report.giver_name, report.receiver_name) == ("Eli", "Farah", "Eli")


def _round_trades(round_id: str) -> list[Trade]:
    from bookloop.storage import db

    with db.transaction() as connection:
        rows = connection.execute(
            text(
                "SELECT t.id, t.loop_id, t.copy_id, t.giver_id, t.receiver_id, t.handoff_code, "
                "t.code_attempts, t.status, t.completed_at FROM trades t "
                "JOIN loops l ON l.id = t.loop_id WHERE l.round_id = :round"
            ),
            {"round": round_id},
        ).mappings()
        return [Trade(**row) for row in rows]


# --- The picture of a swap -------------------------------------------------


def test_the_picture_has_an_arrow_per_book_coloured_by_what_happened(demo):
    swaps_repo.confirm_handoff("trade-demo-pending-a", "user-carla", "3333")

    dot = loop_dot(rounds_repo.loop_trades("loop-demo-pending"))

    assert dot.startswith("digraph swap {")
    assert '"Carla" -> "Dina"' in dot and '"Dina" -> "Carla"' in dot
    assert "Automate the Boring Stuff with Python\\nhanded over" in dot
    assert "A Mind for Numbers\\nwaiting" in dot
    assert dot.count("#2e7d32") == 2  # green line and label for the book handed over


def test_names_with_quotes_cannot_break_the_picture():
    class Step:
        title, giver_name, receiver_name, status = 'The "Best" Book', 'Al "Q" B', "Bo\\b", "pending"

    dot = loop_dot([Step()])

    assert '"Al \\"Q\\" B" -> "Bo\\\\b"' in dot
    assert 'The \\"Best\\" Book' in dot


# --- Pages -----------------------------------------------------------------


def test_my_swaps_offers_report_a_problem_once_a_book_has_changed_hands(demo):
    swaps_repo.confirm_handoff("trade-demo-pending-a", "user-carla", "3333")

    app = open_app(CARLA, "pages/5_My_Swaps.py")

    assert not app.exception
    labels = [button.label for button in app.button]
    assert "Report no-show" not in labels and "Report a problem" in labels
    assert any("Don't hand over your book until everyone is there" in info.value for info in app.info)

    app = next(button for button in app.button if button.label == "Report a problem").click().run()

    assert not app.exception
    assert [message.value for message in app.success] == ["Thanks. A moderator will check what happened with Dina."]
    assert len(reviews_repo.problem_reports()) == 1


def test_before_any_handoff_my_swaps_still_offers_a_no_show(demo):
    app = open_app(CARLA, "pages/5_My_Swaps.py")

    labels = [button.label for button in app.button]
    assert "Report no-show" in labels and "Report a problem" not in labels


def test_the_moderator_sees_the_report_with_the_picture_and_can_resolve_it(demo):
    swaps_repo.confirm_handoff("trade-demo-pending-a", "user-carla", "3333")
    reviews_repo.report_missing_handoff("loop-demo-pending", "user-carla", "user-dina")

    app = open_app(MORGAN, "pages/7_Moderator.py")

    assert not app.exception
    assert "Books not handed over" in [header.value for header in app.subheader]
    assert any(
        "**Carla** says **Dina** didn't hand over “A Mind for Numbers”" in text.value for text in app.markdown
    )
    assert len(app.get("graphviz_chart")) == 1

    resolve = next(
        button for button in app.button if button.label == "Mark as resolved" and "problem" in button.key
    )
    app = resolve.click().run()

    assert not app.exception
    assert reviews_repo.problem_reports() == []


def test_the_swap_round_page_draws_the_loop_for_the_moderator(demo):
    app = open_app(MORGAN, "pages/4_Swap_Round.py")
    app = next(button for button in app.button if button.label == "Run round").click().run()

    assert not app.exception
    (chart,) = app.get("graphviz_chart")
    assert '"Ana" -> "Farah"' in chart.proto.spec
    assert "Green: handed over. Grey: waiting. Red: cancelled." in [text.value for text in app.caption]
