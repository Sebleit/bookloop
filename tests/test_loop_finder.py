"""Tests for find_loops().

The loop finder is a pure rule, so these tests build entries in memory
instead of saving them to the database. Small helpers at the top keep each
test short: entry("ana-stats", "ana") is "Ana entered her Statistics book".
"""

from copy import deepcopy

from bookloop.models import RoundWant
from bookloop.rules.loop_finder import ProposedTrade, find_loops
from bookloop.rules.rounds import RoundEntryInfo


def entry(entry_id: str, owner_id: str, min_score: float = 0.0) -> RoundEntryInfo:
    """A book in the round. Its copy id is the entry id with 'copy-' in front."""
    return RoundEntryInfo(
        id=entry_id,
        round_id="round-1",
        copy_id=f"copy-{entry_id}",
        owner_id=owner_id,
        min_partner_score=min_score,
    )


def want(mine: str, theirs: str) -> RoundWant:
    """'I'd accept `theirs` in return for `mine`.'"""
    return RoundWant(entry_id=mine, wanted_entry_id=theirs)


def books_in(loop: list[ProposedTrade]) -> set[str]:
    return {trade.copy_id for trade in loop}


# --- Accepted: loops that should be found ---------------------------------


def test_finds_a_two_person_loop():
    entries = [entry("ana-stats", "ana"), entry("ben-micro", "ben")]
    wants = [want("ana-stats", "ben-micro"), want("ben-micro", "ana-stats")]

    loops = find_loops(entries, wants)

    assert len(loops) == 1
    assert set(loops[0]) == {
        ProposedTrade(copy_id="copy-ben-micro", giver_id="ben", receiver_id="ana"),
        ProposedTrade(copy_id="copy-ana-stats", giver_id="ana", receiver_id="ben"),
    }


def test_finds_a_three_person_loop_nobody_could_swap_directly():
    # Ana wants Ben's book, Ben wants Carla's, Carla wants Ana's.
    entries = [
        entry("ana-stats", "ana"),
        entry("ben-micro", "ben"),
        entry("carla-finance", "carla"),
    ]
    wants = [
        want("ana-stats", "ben-micro"),
        want("ben-micro", "carla-finance"),
        want("carla-finance", "ana-stats"),
    ]

    loops = find_loops(entries, wants)

    assert len(loops) == 1
    assert set(loops[0]) == {
        ProposedTrade(copy_id="copy-ben-micro", giver_id="ben", receiver_id="ana"),
        ProposedTrade(copy_id="copy-carla-finance", giver_id="carla", receiver_id="ben"),
        ProposedTrade(copy_id="copy-ana-stats", giver_id="ana", receiver_id="carla"),
    }


def test_everyone_in_a_loop_gives_one_book_and_receives_one_book():
    entries = [entry("a", "ana"), entry("b", "ben"), entry("c", "carla"), entry("d", "diogo")]
    wants = [want("a", "b"), want("b", "c"), want("c", "d"), want("d", "a")]

    (loop,) = find_loops(entries, wants)

    assert sorted(trade.giver_id for trade in loop) == ["ana", "ben", "carla", "diogo"]
    assert sorted(trade.receiver_id for trade in loop) == ["ana", "ben", "carla", "diogo"]
    assert all(trade.giver_id != trade.receiver_id for trade in loop)


def test_finds_two_separate_loops_in_the_same_round():
    entries = [
        entry("a", "ana"), entry("b", "ben"),
        entry("c", "carla"), entry("d", "diogo"), entry("e", "eva"),
    ]
    wants = [
        want("a", "b"), want("b", "a"),                    # Ana <-> Ben
        want("c", "d"), want("d", "e"), want("e", "c"),    # Carla -> Diogo -> Eva
    ]

    loops = find_loops(entries, wants)

    assert [books_in(loop) for loop in loops] == [
        {"copy-a", "copy-b"},
        {"copy-c", "copy-d", "copy-e"},
    ]


# --- Rejected: matches that must not happen, inputs left unchanged ---------


def test_minimum_score_removes_a_match_and_leaves_the_inputs_unchanged():
    # Ana only accepts books from people scoring at least 4.5; Ben has 3.2.
    entries = [entry("ana-stats", "ana", min_score=4.5), entry("ben-micro", "ben")]
    wants = [want("ana-stats", "ben-micro"), want("ben-micro", "ana-stats")]
    scores = {"ana": 4.0, "ben": 3.2}
    before = deepcopy((entries, wants, scores))

    loops = find_loops(entries, wants, scores)

    assert loops == []
    assert (entries, wants, scores) == before


def test_minimum_score_allows_a_partner_exactly_at_the_minimum():
    entries = [entry("ana-stats", "ana", min_score=4.5), entry("ben-micro", "ben")]
    wants = [want("ana-stats", "ben-micro"), want("ben-micro", "ana-stats")]

    loops = find_loops(entries, wants, {"ana": 4.0, "ben": 4.5})

    assert len(loops) == 1


def test_a_person_cannot_swap_with_themselves():
    # Ana entered two books and "wants" one for the other: that's not a swap.
    entries = [entry("ana-stats", "ana"), entry("ana-micro", "ana")]
    wants = [want("ana-stats", "ana-micro"), want("ana-micro", "ana-stats")]

    assert find_loops(entries, wants) == []


def test_a_person_appears_only_once_in_the_same_loop():
    # The only circle is Ana -> Ben -> Ana (again, with a second book) -> Carla.
    entries = [entry("a1", "ana"), entry("b", "ben"), entry("a2", "ana"), entry("c", "carla")]
    wants = [want("a1", "b"), want("b", "a2"), want("a2", "c"), want("c", "a1")]

    assert find_loops(entries, wants) == []


def test_a_one_way_chain_is_not_a_loop():
    # Ana wants Ben's book and Ben wants Carla's, but Carla wants nothing.
    entries = [entry("a", "ana"), entry("b", "ben"), entry("c", "carla")]
    wants = [want("a", "b"), want("b", "c")]

    assert find_loops(entries, wants) == []


# --- Edge cases ------------------------------------------------------------


def test_a_round_with_no_entries_finds_no_loops():
    assert find_loops([], []) == []


def test_nobody_wants_anything_finds_no_loops():
    entries = [entry("a", "ana"), entry("b", "ben")]

    assert find_loops(entries, []) == []


def test_overlapping_loops_choose_the_shortest_and_use_each_book_once():
    # Ana's book is in a 3-person loop (Ana, Ben, Carla) AND a 2-person loop
    # (Ana, Diogo). The 2-person loop wins; the 3-person loop can't happen.
    entries = [entry("a", "ana"), entry("b", "ben"), entry("c", "carla"), entry("d", "diogo")]
    wants = [
        want("a", "b"), want("b", "c"), want("c", "a"),
        want("a", "d"), want("d", "a"),
    ]

    loops = find_loops(entries, wants)

    assert [books_in(loop) for loop in loops] == [{"copy-a", "copy-d"}]


def test_a_book_wanted_by_several_people_goes_to_only_one_of_them():
    # Ben, Carla and Diogo all want Ana's book, and Ana would take any of theirs.
    entries = [entry("a", "ana"), entry("b", "ben"), entry("c", "carla"), entry("d", "diogo")]
    wants = [
        want("b", "a"), want("c", "a"), want("d", "a"),
        want("a", "b"), want("a", "c"), want("a", "d"),
    ]

    loops = find_loops(entries, wants)

    assert len(loops) == 1
    all_books = [trade.copy_id for loop in loops for trade in loop]
    assert all_books.count("copy-a") == 1


def test_no_book_appears_in_two_loops():
    entries = [entry(name, name) for name in ["a", "b", "c", "d", "e", "f"]]
    wants = [
        want("a", "b"), want("b", "a"),
        want("b", "c"), want("c", "b"),
        want("c", "d"), want("d", "e"), want("e", "c"),
        want("e", "f"), want("f", "e"),
    ]

    loops = find_loops(entries, wants)

    all_books = [trade.copy_id for loop in loops for trade in loop]
    assert len(all_books) == len(set(all_books))


def test_a_loop_longer_than_the_maximum_size_is_not_created():
    names = ["a", "b", "c", "d", "e", "f", "g"]  # a circle of 7 people
    entries = [entry(name, name) for name in names]
    wants = [want(names[i], names[(i + 1) % 7]) for i in range(7)]

    assert find_loops(entries, wants) == []
    assert len(find_loops(entries, wants, max_size=7)) == 1


def test_wants_pointing_outside_the_entries_are_ignored():
    entries = [entry("a", "ana"), entry("b", "ben")]
    wants = [want("a", "b"), want("b", "a"), want("a", "withdrawn-book")]

    assert len(find_loops(entries, wants)) == 1


def test_owners_without_a_score_count_as_new_users():
    # New users start at 4.0, so a minimum of 4.0 lets them in but 4.1 doesn't.
    entries = [entry("a", "ana", min_score=4.0), entry("b", "ben")]
    wants = [want("a", "b"), want("b", "a")]
    assert len(find_loops(entries, wants)) == 1

    entries = [entry("a", "ana", min_score=4.1), entry("b", "ben")]
    assert find_loops(entries, wants) == []


def test_the_result_is_the_same_every_time():
    entries = [entry(name, name) for name in ["a", "b", "c", "d"]]
    wants = [want("a", "b"), want("b", "a"), want("c", "d"), want("d", "c"), want("a", "c")]

    assert find_loops(entries, wants) == find_loops(entries, wants)
