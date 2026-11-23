"""Tests for what happens when someone doesn't hand over their book.

Everyone in a swap meets at the same place and time, and nobody hands over a
book until everyone is there. Before any book has changed hands, a no-show
cancels the swap and everyone keeps their own book. Once a code has been
typed, everyone was there: a missing book is reported to a moderator, who
checks what happened, with a picture of the swap.
"""

import re
from pathlib import Path

import pytest
from sqlalchemy import text
from streamlit.testing.v1 import AppTest

from bookloop.loop_picture import BOX_WIDTH, MAX_NAME, MAX_TITLE, SLOT_WIDTH, WIDTH, Layout, loop_svg
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


def reports_about(loop_id: str) -> list:
    """Open reports for one swap (the demo data has one of its own, last week's)."""
    return [report for report in reviews_repo.problem_reports() if report.loop_id == loop_id]


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
    swaps_repo.confirm_handoff("trade-demo-pending-a", "user-carla", code_for("trade-demo-pending-a"))

    with pytest.raises(ValueError, match="A book has already changed hands"):
        swaps_repo.report_no_show("loop-demo-pending", "user-carla", "user-dina")

    statuses = {step.title: step.status for step in rounds_repo.loop_trades("loop-demo-pending")}
    assert statuses == {"Automate the Boring Stuff with Python": "completed", "A Mind for Numbers": "pending"}


def test_a_missing_handoff_goes_to_the_moderators_and_cancels_nothing(demo):
    swaps_repo.confirm_handoff("trade-demo-pending-a", "user-carla", code_for("trade-demo-pending-a"))

    reviews_repo.report_missing_handoff("loop-demo-pending", "user-carla", "user-dina")

    (report,) = reports_about("loop-demo-pending")
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
    assert reports_about("loop-demo-pending") == []
    assert [report.loop_id for report in reviews_repo.problem_reports()] == ["loop-last"]  # the demo's own


def test_in_a_round_loop_anyone_can_report_who_did_not_hand_over(demo):
    rounds_repo.run_round("round-demo")
    trades = {(trade.giver_id, trade.receiver_id): trade for trade in _round_trades("round-demo")}
    ana_to_farah = trades[("user-ana", "user-farah")]
    swaps_repo.confirm_handoff(ana_to_farah.id, "user-ana", code_for(ana_to_farah.id))

    reviews_repo.report_missing_handoff(ana_to_farah.loop_id, "user-eli", "user-farah")

    (report,) = reports_about(ana_to_farah.loop_id)
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
    swaps_repo.confirm_handoff("trade-demo-pending-a", "user-carla", code_for("trade-demo-pending-a"))

    svg = loop_svg(rounds_repo.loop_trades("loop-demo-pending"))

    assert svg.startswith("<svg") and svg.endswith("</svg>")
    assert 'aria-label="Swap: Carla → Dina → Carla"' in svg
    # Carla's book was handed over (green), Dina's is still waiting (grey)
    assert re.search(r'fill="#2e7d32"><text [^>]*>Automate the Boring Stuff w…</text>', svg)
    assert re.search(r'fill="#757575"><text [^>]*>A Mind for Numbers</text>', svg)
    assert ">handed over</text>" in svg and ">waiting</text>" in svg


def test_long_titles_and_names_are_cut_but_shown_in_full_when_hovering():
    class Step:
        def __init__(self, title, giver, receiver):
            self.title, self.giver_name, self.receiver_name, self.status = title, giver, receiver, "pending"

    title = "World History: Patterns of Interaction"
    svg = loop_svg([Step(title, "Maria Margarida S.", "Bo"), Step("Short", "Bo", "Maria Margarida S.")])

    assert ">World History: Patterns of…</text>" in svg  # cut to 28 characters
    assert ">Maria Margari…</text>" in svg  # cut to 14 characters
    assert f"<title>{title} (waiting): Maria Margarida S. → Bo</title>" in svg  # full text on hover
    assert "<title>Maria Margarida S.</title>" in svg


def test_names_and_titles_cannot_break_the_picture():
    class Step:
        title, giver_name, receiver_name, status = '<b>"Best" & Co</b>', "Al <script>", "Bo", "lost"

    svg = loop_svg([Step(), Step()])

    assert "<script>" not in svg and "<b>" not in svg
    assert "&lt;b&gt;&quot;Best&quot; &amp; Co&lt;/b&gt;" in svg
    assert ">waiting</text>" in svg  # an unknown status is drawn as waiting


@pytest.mark.parametrize("people", [2, 3, 4, 5, 6])
def test_nothing_in_the_picture_can_overlap(people):
    layout = Layout(people)
    boxes = layout.boxes()

    for number, box in enumerate(boxes):
        assert 0 <= box.x and box.x + box.width <= WIDTH
        assert 0 <= box.y and box.y + box.height <= layout.height
        assert not any(box.overlaps(other) for other in boxes[number + 1:])
    # The longest title and name shown fit their space, even with wide letters (0.62 of the font size each).
    assert MAX_TITLE * 13 * 0.62 <= SLOT_WIDTH - 8
    assert MAX_NAME * 14 * 0.62 <= BOX_WIDTH - 16


# --- Pages -----------------------------------------------------------------


def test_my_swaps_offers_report_a_problem_once_a_book_has_changed_hands(demo):
    swaps_repo.confirm_handoff("trade-demo-pending-a", "user-carla", code_for("trade-demo-pending-a"))

    app = open_app(CARLA, "pages/5_My_Swaps.py")

    assert not app.exception
    labels = [button.label for button in app.button]
    assert "Report no-show" not in labels and "Report a problem" in labels
    assert any("Don't hand over your book until everyone is there" in info.value for info in app.info)

    app = next(button for button in app.button if button.label == "Report a problem").click().run()

    assert not app.exception
    assert [message.value for message in app.success] == ["Thanks. A moderator will check what happened with Dina."]
    assert len(reports_about("loop-demo-pending")) == 1


def test_before_any_handoff_my_swaps_still_offers_a_no_show(demo):
    app = open_app(CARLA, "pages/5_My_Swaps.py")

    labels = [button.label for button in app.button]
    assert "Report no-show" in labels and "Report a problem" not in labels


def test_the_moderator_sees_the_report_with_the_picture_and_can_resolve_it(demo):
    swaps_repo.confirm_handoff("trade-demo-pending-a", "user-carla", code_for("trade-demo-pending-a"))
    reviews_repo.report_missing_handoff("loop-demo-pending", "user-carla", "user-dina")

    app = open_app(MORGAN, "pages/7_Moderator.py")

    assert not app.exception
    assert "Books not handed over" in [header.value for header in app.subheader]
    assert any(
        "**Carla** says **Dina** didn't hand over “A Mind for Numbers”" in text.value for text in app.markdown
    )
    pictures = [text.value for text in app.markdown if text.value.startswith("<svg")]
    assert any("Swap: Carla → Dina → Carla" in picture for picture in pictures)
    assert any("Swap: Ana → Farah → Ben → Ana" in picture for picture in pictures)  # last week's, in the demo data
    # Everyone in the swap, with their email, so the moderator can ask what happened.
    captions = [text.value for text in app.caption]
    assert "Everyone in this swap: Carla (carla@example.com) · Dina (dina@example.com)" in captions
    assert "Everyone in this swap: Ana (ana@example.com) · Ben (ben@example.com) · Farah (farah@example.com)" in captions

    resolve = next(
        button for button in app.button
        if button.label == "Mark as resolved" and button.key == "resolve_problem_trade-demo-pending-b"
    )
    app = resolve.click().run()

    assert not app.exception
    assert reports_about("loop-demo-pending") == []


def test_the_swap_round_page_draws_the_loop_for_the_moderator(demo):
    app = open_app(MORGAN, "pages/4_Swap_Round.py")
    app = app.selectbox[0].set_value("round-demo").run()  # this week's round, ready to run
    app = next(button for button in app.button if button.label == "Run round").click().run()

    assert not app.exception
    pictures = [text.value for text in app.markdown if text.value.startswith("<svg")]
    assert len(pictures) == 5  # one for each loop
    assert any("Swap: Ana → Farah → Eli → Ana" in picture for picture in pictures)
    assert "Green: handed over. Grey: waiting. Red: cancelled." in [text.value for text in app.caption]
