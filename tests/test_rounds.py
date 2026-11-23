"""Tests for swap rounds: the rules, saving to the database, the demo round and the page.

Users, books and copies come from the shared factories in conftest.py. For the
rules, rounds and entries are only needed in memory, so the helpers below
build them. All times are fixed so the tests give the same result on any day.
"""

import runpy
from copy import deepcopy
from pathlib import Path

import pytest
from sqlalchemy import text
from streamlit.testing.v1 import AppTest

from bookloop.models import Profile, Round
from bookloop.services.notify import get_notifications
from bookloop.storage import db, rounds_repo
from bookloop.storage.copies_repo import get_copy
from seed import base as seed_base
from seed import rounds as seed_rounds
from bookloop.rules.rounds import (
    RoundEntryInfo,
    can_advance,
    can_create_round,
    can_enter,
    can_run,
    can_set_min_score,
    can_want,
    next_phase,
)


NOW = "2026-11-18T12:00:00Z"
ENTRIES_CLOSE = "2026-11-19T12:00:00Z"
WANTS_CLOSE = "2026-11-20T12:00:00Z"
MEETING = "2026-11-21T14:00:00Z"
DURING_WANTS = "2026-11-19T18:00:00Z"


def a_round(phase: str = "entries", id: str = "round-1") -> Round:
    return Round(
        id=id,
        name="Spring textbook swap",
        phase=phase,
        entries_close_at=ENTRIES_CLOSE,
        wants_close_at=WANTS_CLOSE,
        meet_place="Nova SBE library",
        meet_time=MEETING,
        created_by="moderator-1",
    )


def an_entry(owner_id: str, id: str = "entry-1", round_id: str = "round-1") -> RoundEntryInfo:
    return RoundEntryInfo(id=id, round_id=round_id, copy_id=f"copy-{id}", owner_id=owner_id)


# --- Phases ----------------------------------------------------------------


def test_phases_go_in_order_and_stop_at_closed():
    assert next_phase("entries") == "wants"
    assert next_phase("wants") == "matched"
    assert next_phase("matched") == "closed"
    assert next_phase("closed") is None


# --- Creating a round ------------------------------------------------------


def test_moderator_can_create_a_round(make_user):
    moderator = make_user(name="Mia", role="moderator")

    decision = can_create_round(
        moderator, "Spring swap", ENTRIES_CLOSE, WANTS_CLOSE, "Library", MEETING, now=NOW
    )

    assert decision.allowed is True


def test_student_cannot_create_a_round(make_user):
    student = make_user(name="Ana")

    decision = can_create_round(
        student, "Spring swap", ENTRIES_CLOSE, WANTS_CLOSE, "Library", MEETING, now=NOW
    )

    assert decision.allowed is False
    assert decision.reason == "Only moderators can create rounds."


def test_round_needs_a_name_and_a_meeting_place(make_user):
    moderator = make_user(name="Mia", role="moderator")

    no_name = can_create_round(moderator, "   ", ENTRIES_CLOSE, WANTS_CLOSE, "Library", MEETING, now=NOW)
    no_place = can_create_round(moderator, "Swap", ENTRIES_CLOSE, WANTS_CLOSE, "", MEETING, now=NOW)

    assert no_name.reason == "Give the round a name."
    assert no_place.reason == "Add a meeting place and time for the handoffs."


def test_round_deadlines_must_be_in_order(make_user):
    moderator = make_user(name="Mia", role="moderator")

    past_entries = can_create_round(
        moderator, "Swap", "2026-11-01T12:00:00Z", WANTS_CLOSE, "Library", MEETING, now=NOW
    )
    wants_before_entries = can_create_round(
        moderator, "Swap", WANTS_CLOSE, ENTRIES_CLOSE, "Library", MEETING, now=NOW
    )
    meeting_before_wants = can_create_round(
        moderator, "Swap", ENTRIES_CLOSE, WANTS_CLOSE, "Library", ENTRIES_CLOSE, now=NOW
    )

    assert past_entries.reason == "The entries deadline must be in the future."
    assert wants_before_entries.reason == "Wants must close after entries close."
    assert meeting_before_wants.reason == "The meeting must be after wants close."


def test_wants_closing_at_the_same_moment_as_entries_is_refused(make_user):
    moderator = make_user(name="Mia", role="moderator")

    decision = can_create_round(
        moderator, "Swap", ENTRIES_CLOSE, ENTRIES_CLOSE, "Library", MEETING, now=NOW
    )

    assert decision.allowed is False


# --- Moving a round forward ------------------------------------------------


def test_moderator_can_close_entries_and_close_a_matched_round(make_user):
    moderator = make_user(name="Mia", role="moderator")

    assert can_advance(moderator, a_round("entries")).allowed is True
    assert can_advance(moderator, a_round("matched")).allowed is True


def test_student_cannot_advance_a_round_and_the_round_is_unchanged(make_user):
    student = make_user(name="Ana")
    round = a_round("entries")
    before = deepcopy(round)

    decision = can_advance(student, round)

    assert decision.allowed is False
    assert decision.reason == "Only moderators can move a round to the next phase."
    assert round == before


def test_wants_phase_can_only_end_by_running_the_round(make_user):
    moderator = make_user(name="Mia", role="moderator")

    decision = can_advance(moderator, a_round("wants"))

    assert decision.reason == "Run the round to match the books."


def test_a_closed_round_cannot_advance(make_user):
    moderator = make_user(name="Mia", role="moderator")

    assert can_advance(moderator, a_round("closed")).reason == "This round is already closed."


# --- Running a round -------------------------------------------------------


def test_moderator_can_run_a_round_in_the_wants_phase(make_user):
    moderator = make_user(name="Mia", role="moderator")

    assert can_run(moderator, a_round("wants")).allowed is True


def test_student_cannot_run_a_round(make_user):
    student = make_user(name="Ana")

    assert can_run(student, a_round("wants")).reason == "Only moderators can run a round."


def test_a_round_cannot_be_run_twice(make_user):
    moderator = make_user(name="Mia", role="moderator")

    assert can_run(moderator, a_round("matched")).reason == "This round has already been run."
    assert can_run(moderator, a_round("closed")).reason == "This round has already been run."


def test_a_round_cannot_be_run_while_entries_are_open(make_user):
    moderator = make_user(name="Mia", role="moderator")

    decision = can_run(moderator, a_round("entries"))

    assert decision.reason == "Close entries first, so students can choose their wants."


# --- Entering a book -------------------------------------------------------


def test_student_can_enter_their_available_book(make_user, make_copy):
    ana = make_user(name="Ana")
    copy = make_copy(owner=ana)

    assert can_enter(ana, a_round("entries"), copy, now=NOW).allowed is True


def test_entry_after_the_deadline_is_refused_and_the_copy_is_unchanged(make_user, make_copy):
    ana = make_user(name="Ana")
    copy = make_copy(owner=ana)
    before = deepcopy(copy)

    decision = can_enter(ana, a_round("entries"), copy, now="2026-11-19T12:00:01Z")

    assert decision.allowed is False
    assert decision.reason == "The entries deadline has passed."
    assert copy == before


def test_entry_exactly_at_the_deadline_is_refused(make_user, make_copy):
    ana = make_user(name="Ana")
    copy = make_copy(owner=ana)

    decision = can_enter(ana, a_round("entries"), copy, now=ENTRIES_CLOSE)

    assert decision.reason == "The entries deadline has passed."


def test_cannot_enter_someone_elses_book(make_user, make_copy):
    ana = make_user(name="Ana")
    bens_copy = make_copy(owner=make_user(name="Ben"))

    decision = can_enter(ana, a_round("entries"), bens_copy, now=NOW)

    assert decision.reason == "You can only enter your own books."


def test_cannot_enter_a_book_that_is_reserved_or_already_in_a_round(make_user, make_copy):
    ana = make_user(name="Ana")
    reserved = make_copy(owner=ana, status="reserved")
    in_round = make_copy(owner=ana, status="in_round")

    assert can_enter(ana, a_round("entries"), reserved, now=NOW).reason == (
        "Only available books can be entered."
    )
    assert can_enter(ana, a_round("entries"), in_round, now=NOW).allowed is False


def test_cannot_enter_once_the_round_has_moved_on(make_user, make_copy):
    ana = make_user(name="Ana")
    copy = make_copy(owner=ana)

    decision = can_enter(ana, a_round("wants"), copy, now=NOW)

    assert decision.reason == "This round isn't taking new books."


def test_user_under_review_cannot_enter(make_user, make_copy):
    ana = make_user(name="Ana", status="under_review")
    copy = make_copy(owner=ana)

    decision = can_enter(ana, a_round("entries"), copy, now=NOW)

    assert decision.reason == "Your account is under review, so you can't join rounds."


def test_blocked_user_cannot_enter(make_user, make_copy):
    ana = make_user(name="Ana")
    copy = make_copy(owner=ana)

    assert can_enter(ana, a_round("entries"), copy, blocked=True, now=NOW).allowed is False


# --- Choosing wants --------------------------------------------------------


def test_student_can_want_another_students_book(make_user):
    ana, ben = make_user(name="Ana"), make_user(name="Ben")
    mine = an_entry(ana.id, id="entry-ana")
    theirs = an_entry(ben.id, id="entry-ben")

    decision = can_want(ana, a_round("wants"), mine, theirs, now=DURING_WANTS)

    assert decision.allowed is True


def test_cannot_want_your_own_book_and_entries_are_unchanged(make_user):
    ana = make_user(name="Ana")
    mine = an_entry(ana.id, id="entry-ana-1")
    also_mine = an_entry(ana.id, id="entry-ana-2")
    before = deepcopy((mine, also_mine))

    decision = can_want(ana, a_round("wants"), mine, also_mine, now=DURING_WANTS)

    assert decision.allowed is False
    assert decision.reason == "You can't want your own book."
    assert (mine, also_mine) == before


def test_cannot_choose_wants_for_someone_elses_entry(make_user):
    ana, ben, carla = make_user(name="Ana"), make_user(name="Ben"), make_user(name="Carla")
    bens_entry = an_entry(ben.id, id="entry-ben")
    carlas_entry = an_entry(carla.id, id="entry-carla")

    decision = can_want(ana, a_round("wants"), bens_entry, carlas_entry, now=DURING_WANTS)

    assert decision.reason == "You can only choose wants for your own books."


def test_wants_only_during_the_wants_phase_and_before_its_deadline(make_user):
    ana, ben = make_user(name="Ana"), make_user(name="Ben")
    mine, theirs = an_entry(ana.id, id="entry-ana"), an_entry(ben.id, id="entry-ben")

    too_early = can_want(ana, a_round("entries"), mine, theirs, now=NOW)
    too_late = can_want(ana, a_round("wants"), mine, theirs, now=WANTS_CLOSE)

    assert too_early.reason == "Wants can only be chosen during the wants phase."
    assert too_late.reason == "The wants deadline has passed."


def test_cannot_want_a_book_from_another_round(make_user):
    ana, ben = make_user(name="Ana"), make_user(name="Ben")
    mine = an_entry(ana.id, id="entry-ana")
    other_round = an_entry(ben.id, id="entry-ben", round_id="round-2")

    decision = can_want(ana, a_round("wants"), mine, other_round, now=DURING_WANTS)

    assert decision.reason == "That book isn't in this round."


def test_user_under_review_cannot_choose_wants(make_user):
    ana = make_user(name="Ana", status="under_review")
    ben = make_user(name="Ben")
    mine, theirs = an_entry(ana.id, id="entry-ana"), an_entry(ben.id, id="entry-ben")

    decision = can_want(ana, a_round("wants"), mine, theirs, now=DURING_WANTS)

    assert decision.allowed is False


# --- Minimum partner score -------------------------------------------------


def test_student_can_set_a_minimum_score_between_0_and_5(make_user):
    ana = make_user(name="Ana")
    mine = an_entry(ana.id)

    assert can_set_min_score(ana, a_round("wants"), mine, 4.5, now=DURING_WANTS).allowed is True


def test_minimum_score_outside_0_to_5_is_refused(make_user):
    ana = make_user(name="Ana")
    mine = an_entry(ana.id)

    too_high = can_set_min_score(ana, a_round("wants"), mine, 6, now=DURING_WANTS)
    negative = can_set_min_score(ana, a_round("wants"), mine, -1, now=DURING_WANTS)

    assert too_high.reason == "The minimum score must be between 0 and 5."
    assert negative.allowed is False


def test_minimum_score_of_exactly_0_and_5_is_allowed(make_user):
    ana = make_user(name="Ana")
    mine = an_entry(ana.id)

    assert can_set_min_score(ana, a_round("wants"), mine, 0, now=DURING_WANTS).allowed is True
    assert can_set_min_score(ana, a_round("wants"), mine, 5, now=DURING_WANTS).allowed is True


# === Saving rounds to the database ==========================================


def saved_round(make_user, phase: str = "entries") -> Round:
    """Save a round created by a moderator, then put it in the given phase."""
    moderator = make_user(name="Mia", role="moderator")
    round = rounds_repo.create_round(
        "Spring swap", ENTRIES_CLOSE, WANTS_CLOSE, "Library", MEETING, moderator.id
    )
    if phase != "entries":
        set_phase(round.id, phase)
    return rounds_repo.get_round(round.id)


def set_phase(round_id: str, phase: str) -> None:
    with db.transaction() as connection:
        connection.execute(
            text("UPDATE rounds SET phase = :phase WHERE id = :id"), {"phase": phase, "id": round_id}
        )


def count_rows(table: str) -> int:
    with db.transaction() as connection:
        return connection.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one()


@pytest.fixture
def three_way_round(make_user, make_book, make_copy):
    """A round in the wants phase: Ana, Ben and Carla form a loop; Dina gets no match."""
    round = saved_round(make_user, phase="entries")
    people, entries = {}, {}
    for name, title in [("Ana", "Statistics"), ("Ben", "Micro"), ("Carla", "Finance"), ("Dina", "History")]:
        people[name] = make_user(name=name)
        copy = make_copy(owner=people[name], book=make_book(title=title))
        entries[name] = rounds_repo.enter_copy(round.id, copy.id)
    set_phase(round.id, "wants")
    rounds_repo.save_wants(entries["Ana"].id, [entries["Ben"].id], 0)
    rounds_repo.save_wants(entries["Ben"].id, [entries["Carla"].id], 0)
    rounds_repo.save_wants(entries["Carla"].id, [entries["Ana"].id], 0)
    rounds_repo.save_wants(entries["Dina"].id, [entries["Ana"].id], 0)
    return round, people, entries


def test_create_round_saves_it_in_the_entries_phase(make_user):
    round = saved_round(make_user)

    assert round.phase == "entries"
    assert round.name == "Spring swap"
    assert [saved.id for saved in rounds_repo.list_rounds()] == [round.id]


def test_entering_a_book_puts_it_in_the_round(make_user, make_book, make_copy):
    round = saved_round(make_user)
    ana = make_user(name="Ana")
    copy = make_copy(owner=ana, book=make_book(title="Statistics"))

    entry = rounds_repo.enter_copy(round.id, copy.id)

    assert entry.owner_id == ana.id
    assert get_copy(copy.id).status == "in_round"
    (details,) = rounds_repo.list_entries(round.id)
    assert (details.title, details.owner_name) == ("Statistics", "Ana")


def test_entering_an_unavailable_book_fails_and_changes_nothing(make_user, make_copy):
    round = saved_round(make_user)
    copy = make_copy(status="reserved")

    with pytest.raises(ValueError):
        rounds_repo.enter_copy(round.id, copy.id)

    assert get_copy(copy.id).status == "reserved"
    assert rounds_repo.list_entries(round.id) == []


def test_the_same_book_cannot_be_entered_twice(make_user, make_copy):
    round = saved_round(make_user)
    copy = make_copy()
    rounds_repo.enter_copy(round.id, copy.id)

    with pytest.raises(ValueError):
        rounds_repo.enter_copy(round.id, copy.id)

    assert len(rounds_repo.list_entries(round.id)) == 1


def test_available_copies_lists_only_the_students_available_books(make_user, make_book, make_copy):
    ana = make_user(name="Ana")
    make_copy(owner=ana, book=make_book(title="Statistics"))
    make_copy(owner=ana, status="reserved")
    make_copy(owner=make_user(name="Ben"))

    assert [choice.title for choice in rounds_repo.available_copies(ana.id)] == ["Statistics"]


def test_saving_wants_replaces_the_old_ones_and_sets_the_minimum_score(three_way_round):
    round, _, entries = three_way_round

    rounds_repo.save_wants(entries["Ana"].id, [entries["Carla"].id, entries["Dina"].id], 4.5)

    anas_wants = [w.wanted_entry_id for w in rounds_repo.get_wants(round.id) if w.entry_id == entries["Ana"].id]
    assert sorted(anas_wants) == sorted([entries["Carla"].id, entries["Dina"].id])
    anas_entry = next(e for e in rounds_repo.list_entries(round.id) if e.info.id == entries["Ana"].id)
    assert anas_entry.info.min_partner_score == 4.5


def test_advance_moves_entries_to_wants_and_matched_to_closed(make_user):
    round = saved_round(make_user)
    assert rounds_repo.advance_round(round.id).phase == "wants"

    set_phase(round.id, "matched")
    assert rounds_repo.advance_round(round.id).phase == "closed"


def test_advance_refuses_the_wants_phase_and_leaves_the_round_unchanged(make_user):
    round = saved_round(make_user, phase="wants")

    with pytest.raises(ValueError):
        rounds_repo.advance_round(round.id)

    assert rounds_repo.get_round(round.id).phase == "wants"


def test_running_a_round_creates_the_loop_and_returns_unmatched_books(three_way_round):
    round, people, entries = three_way_round

    result = rounds_repo.run_round(round.id)

    assert len(result.loops) == 1
    assert (result.books_swapped, result.books_returned) == (3, 1)
    loop = result.loops[0]
    assert (loop.source, loop.round_id, loop.meet_place) == ("round", round.id, "Library")
    assert count_rows("trades") == 3
    assert rounds_repo.get_round(round.id).phase == "matched"
    for name in ["Ana", "Ben", "Carla"]:
        assert get_copy(entries[name].copy_id).status == "reserved"
    assert get_copy(entries["Dina"].copy_id).status == "available"


def test_running_a_round_notifies_everyone(three_way_round):
    round, people, _ = three_way_round

    rounds_repo.run_round(round.id)

    (ana_message,) = get_notifications(people["Ana"].id)
    assert "give “Statistics” to Carla" in ana_message.text
    assert "receive “Micro” from Ben" in ana_message.text
    (dina_message,) = get_notifications(people["Dina"].id)
    assert "no match for “History”" in dina_message.text


def test_a_round_cannot_be_run_twice_and_nothing_changes(three_way_round):
    round, people, _ = three_way_round
    rounds_repo.run_round(round.id)
    before = (count_rows("loops"), count_rows("trades"), count_rows("notifications"))

    with pytest.raises(ValueError):
        rounds_repo.run_round(round.id)

    assert (count_rows("loops"), count_rows("trades"), count_rows("notifications")) == before


def test_running_a_round_with_no_entries_finds_nothing(make_user):
    round = saved_round(make_user, phase="wants")

    result = rounds_repo.run_round(round.id)

    assert result.loops == []
    assert rounds_repo.get_round(round.id).phase == "matched"


def test_minimum_score_uses_the_real_swapper_score(three_way_round, make_review):
    # Ben has three 1-star reviews: (12 + 3) / (3 + 3) = 2.5. Ana only accepts 3.0+.
    round, people, entries = three_way_round
    for _ in range(3):
        make_review(reviewee=people["Ben"], stars=1, comment="Torn cover.")
    rounds_repo.save_wants(entries["Ana"].id, [entries["Ben"].id], 3.0)

    result = rounds_repo.run_round(round.id)

    assert result.loops == []
    assert get_copy(entries["Ana"].copy_id).status == "available"


def test_if_saving_a_loop_fails_the_round_goes_back_to_wants(three_way_round, monkeypatch):
    round, _, entries = three_way_round

    def broken_create_loop(*args, **kwargs):
        raise RuntimeError("database hiccup")

    monkeypatch.setattr(rounds_repo, "create_loop", broken_create_loop)
    with pytest.raises(RuntimeError):
        rounds_repo.run_round(round.id)

    assert rounds_repo.get_round(round.id).phase == "wants"
    assert all(get_copy(entry.copy_id).status == "in_round" for entry in entries.values())


def test_each_person_sees_only_their_own_trades(three_way_round):
    round, people, _ = three_way_round
    rounds_repo.run_round(round.id)

    anas = rounds_repo.my_trades(round.id, people["Ana"].id)

    assert {(t.title, t.giver_name, t.receiver_name) for t in anas} == {
        ("Statistics", "Ana", "Carla"),
        ("Micro", "Ben", "Ana"),
    }
    assert rounds_repo.my_trades(round.id, people["Dina"].id) == []


# === The demo round =========================================================


def load_demo_data(database) -> None:
    with database.begin() as connection:
        seed_base.seed(connection)
        seed_rounds.seed(connection)


def seed_profile(id: str, name: str, role: str = "student") -> Profile:
    """One of the demo users from seed/base.py."""
    return Profile(id=id, display_name=name, role=role, status="active", created_at=seed_base.CREATED_AT)


def test_the_demo_round_produces_a_three_way_loop(database):
    load_demo_data(database)

    result = rounds_repo.run_round("round-demo")

    (loop,) = result.loops
    eli = {(t.title, t.giver_name, t.receiver_name) for t in rounds_repo.my_trades("round-demo", "user-eli")}
    assert eli == {
        ("Calculus: Early Transcendentals", "Eli", "Ana"),
        ("Principles of Economics", "Farah", "Eli"),
    }
    assert rounds_repo.my_trades("round-demo", "user-ben") == []
    assert result.books_returned == 1


def test_the_demo_loop_is_listed_in_order_around_the_circle(database):
    load_demo_data(database)
    rounds_repo.run_round("round-demo")

    (loop,) = rounds_repo.loops_in_round("round-demo")

    assert [trade.giver_name for trade in loop] == ["Ana", "Farah", "Eli"]
    for trade, following in zip(loop, loop[1:] + loop[:1]):
        assert trade.receiver_id == following.giver_id  # each receiver gives the next book
    assert rounds_repo.loops_in_round("no-such-round") == []


# === The Swap Round page ====================================================


PAGE = Path(__file__).resolve().parents[1] / "pages" / "4_Swap_Round.py"


def open_page(user, round_id: str | None = None) -> AppTest:
    """Open the Swap Round page logged in as `user` (laptop mode, test database),
    showing `round_id` (otherwise the newest round, as the page does)."""
    page = AppTest.from_file(str(PAGE), default_timeout=30)
    page.session_state["current_user"] = user
    page.session_state["_auth_mode"] = "laptop"
    if round_id:
        page.session_state["swap_round_shown"] = round_id
    return page.run()


def test_page_shows_a_sensible_message_when_there_are_no_rounds(make_user):
    page = open_page(make_user(name="Ana"))

    assert not page.exception
    assert page.info[0].value == "No swap rounds yet. A moderator will open one soon."


def test_page_lets_a_student_choose_wants_in_the_demo_round(database):
    load_demo_data(database)
    ana = seed_profile("user-ana", "Ana")

    page = open_page(ana, "round-demo")

    assert not page.exception
    (wants,) = page.multiselect
    assert len(wants.options) == 3  # the three books Ana doesn't own
    assert page.multiselect[0].value == ["entry-eli"]  # what the demo already ticked


def test_page_lets_a_moderator_run_the_demo_round_and_shows_results(database):
    load_demo_data(database)
    moderator = seed_profile("user-moderator", "Morgan", role="moderator")

    page = open_page(moderator, "round-demo")
    page = next(button for button in page.button if button.label == "Run round").click().run()

    assert not page.exception
    assert page.success[0].value.startswith("Found 1 loop: 3 books will change hands")
    assert "**Loop 1:** Ana → Farah → Eli → Ana" in [text.value for text in page.markdown]
    assert "Eli gives “Calculus: Early Transcendentals” to Ana" in [text.value for text in page.caption]
    assert "This round created 1 loop." in [text.value for text in page.markdown]
    ana_page = open_page(seed_profile("user-ana", "Ana"), "round-demo")
    assert ana_page.success[0].value == "You're in a swap loop!"
    ben_page = open_page(seed_profile("user-ben", "Ben"), "round-demo")
    assert "back on your shelf" in ben_page.info[0].value


def test_page_shows_what_is_saved_and_confirms_a_new_save(database):
    load_demo_data(database)
    ana = seed_profile("user-ana", "Ana")

    page = open_page(ana, "round-demo")
    captions = [text.value for text in page.caption]
    assert "✅ Saved: you'd accept 1 book. You can change it until wants close." in captions

    page.multiselect[0].set_value(["entry-eli", "entry-farah"])
    page = next(button for button in page.button if button.label == "Save").click().run()

    assert not page.exception
    assert page.success[0].value.startswith("Saved: 2 books you'd accept for")
    assert page.toast[0].value.startswith("Saved: 2 books you'd accept for")  # pops up in the corner
    captions = [text.value for text in page.caption]
    assert "✅ Saved: you'd accept 2 books. You can change it until wants close." in captions


def test_saved_wants_line_says_when_nothing_is_saved_and_shows_the_minimum_score():
    module = runpy.run_path(str(PAGE), run_name="not_main")
    saved_text = module["_saved_wants_text"]

    assert saved_text(0, 0.0) == "Nothing saved yet: tick the books you'd accept, then click Save."
    assert saved_text(3, 4.0) == (
        "✅ Saved: you'd accept 3 books, from people scoring at least 4.00. "
        "You can change it until wants close."
    )


def test_the_page_keeps_showing_a_round_after_it_runs(database):
    load_demo_data(database)
    moderator = seed_profile("user-moderator", "Morgan", role="moderator")
    newer = rounds_repo.create_round(
        "Next week", "2099-01-01T18:00:00Z", "2099-01-03T18:00:00Z", "Library", "2099-01-04T14:00:00Z", moderator.id
    )

    page = open_page(moderator)
    (menu,) = page.selectbox
    assert menu.value == newer.id  # the newest round comes first
    page = menu.set_value("round-demo").run()
    page = next(button for button in page.button if button.label == "Run round").click().run()

    assert not page.exception
    assert page.selectbox[0].value == "round-demo"  # still the round that just ran, now matched
    assert "This round created 1 loop." in [text.value for text in page.markdown]
    assert any(text.value.startswith("<svg") for text in page.markdown)  # with its picture


def test_a_moderator_sees_the_round_they_just_created(database):
    load_demo_data(database)
    moderator = seed_profile("user-moderator", "Morgan", role="moderator")

    page = open_page(moderator)
    form_inputs = [box for box in page.text_input if box.label in ("Name", "Meeting place")]
    form_inputs[0].input("Next week")
    form_inputs[1].input("Library")
    page = next(button for button in page.button if button.label == "Create round").click().run()

    assert not page.exception
    assert page.success[0].value == "Round “Next week” created. Students can now enter books."
    created = next(item for item in rounds_repo.list_rounds() if item.name == "Next week")
    assert page.selectbox[0].value == created.id
