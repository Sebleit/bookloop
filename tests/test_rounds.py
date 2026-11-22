"""Tests for the swap round rules in bookloop/rules/rounds.py.

Users and copies come from the shared factories in conftest.py. Rounds and
entries are only needed in memory here, so the helpers below build them.
All times are fixed so the tests give the same result on any day.
"""

from copy import deepcopy

from bookloop.models import Round
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
