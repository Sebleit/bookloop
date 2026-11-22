"""The loop finder: the heart of swap rounds.

Picture every book in the round as a dot. Draw an arrow from book A to book B
when A's owner would accept B in return for A. A loop is a circle of arrows:

    Ana's Statistics -> Ben's Microeconomics -> Carla's Finance -> back to Ana

Following the arrows, each person receives the book their arrow points to,
and gives their own book to the person whose arrow points at it:
Ana gets Microeconomics from Ben, Ben gets Finance from Carla, and Carla gets
Statistics from Ana. Nobody could have swapped directly, but all three can.

The method (the same one we do by hand on paper):
1. Draw the arrows. Skip an arrow if the owner at the other end has a score
   below the minimum the person chose.
2. Find the SHORTEST circle and lock it in.
3. Remove those books and repeat until no circles are left.

Why shortest first? If someone doesn't show up, the whole loop is cancelled,
so a small loop puts fewer people at risk.

Its limit: locking in the shortest loop first doesn't always give the largest
possible number of swaps overall. Checking every combination would, but it
gets very slow as rounds grow.

This is a rule, so it never uses Streamlit or the database: storage gives it
the entries, the wants and everyone's score.
"""

from collections import deque
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from bookloop.models import RoundWant
from bookloop.rules.rounds import RoundEntryInfo


# Longest loop we create. With more people, one no-show cancels too many swaps.
MAX_LOOP_SIZE = 6
# Same starting score swapper_score() gives someone with no reviews yet.
NEW_USER_SCORE = 4.0


@dataclass(frozen=True)
class ProposedTrade:
    """One book changing hands inside a loop."""

    copy_id: str
    giver_id: str
    receiver_id: str


def find_loops(
    entries: Iterable[RoundEntryInfo],
    wants: Iterable[RoundWant],
    scores: Mapping[str, float] | None = None,
    max_size: int = MAX_LOOP_SIZE,
) -> list[list[ProposedTrade]]:
    """Return the loops to create, shortest first, each as a list of trades.

    entries: the books in the round, with their owners and minimum scores.
    wants:   pairs "I'd accept wanted_entry_id in return for entry_id".
    scores:  each owner's Swapper Score (owners not listed count as new users).

    Every book appears in at most one loop, and every person at most once
    in the same loop. The inputs are never changed.
    """
    entries = list(entries)
    scores = scores or {}
    by_id = {entry.id: entry for entry in entries}
    order = [entry.id for entry in entries]  # keeps the result predictable
    arrows = _draw_arrows(entries, wants, by_id, scores)

    remaining = set(order)
    loops = []
    while True:
        circle = _shortest_circle(order, arrows, remaining, by_id, max_size)
        if circle is None:
            return loops
        loops.append(_to_trades(circle, by_id))
        remaining -= set(circle)


def _draw_arrows(
    entries: list[RoundEntryInfo],
    wants: Iterable[RoundWant],
    by_id: dict[str, RoundEntryInfo],
    scores: Mapping[str, float],
) -> dict[str, list[str]]:
    """Step 1: an arrow from each book to every book its owner would accept."""
    position = {entry.id: index for index, entry in enumerate(entries)}
    arrows: dict[str, list[str]] = {entry.id: [] for entry in entries}

    for want in wants:
        mine = by_id.get(want.entry_id)
        theirs = by_id.get(want.wanted_entry_id)
        if mine is None or theirs is None:
            continue  # a book that isn't in this list of entries
        if mine.owner_id == theirs.owner_id:
            continue  # you can't swap with yourself
        partner_score = scores.get(theirs.owner_id, NEW_USER_SCORE)
        if partner_score < mine.min_partner_score:
            continue  # the other owner's score is below the minimum you chose
        if theirs.id not in arrows[mine.id]:
            arrows[mine.id].append(theirs.id)

    for targets in arrows.values():
        targets.sort(key=position.get)
    return arrows


def _shortest_circle(
    order: list[str],
    arrows: dict[str, list[str]],
    remaining: set[str],
    by_id: dict[str, RoundEntryInfo],
    max_size: int,
) -> list[str] | None:
    """Step 2: try circles of 2 books, then 3, and so on; return the first found."""
    incoming = _incoming_arrows(arrows, remaining)
    steps_home: dict[str, dict[str, int]] = {}
    for size in range(2, max_size + 1):
        for start in order:
            if start not in remaining:
                continue
            if start not in steps_home:
                steps_home[start] = _steps_back_to(start, incoming)
            circle = _circle_from(start, size, arrows, remaining, by_id, steps_home[start])
            if circle is not None:
                return circle
    return None


def _incoming_arrows(arrows: dict[str, list[str]], remaining: set[str]) -> dict[str, list[str]]:
    """The same arrows turned around: for each book, which books point at it."""
    incoming: dict[str, list[str]] = {book: [] for book in remaining}
    for book, targets in arrows.items():
        if book in remaining:
            for target in targets:
                if target in remaining:
                    incoming[target].append(book)
    return incoming


def _steps_back_to(start: str, incoming: dict[str, list[str]]) -> dict[str, int]:
    """For each book, the fewest arrows it takes to get from it back to `start`.

    Books that can never get back to `start` aren't in the result. This lets
    the search below skip paths that can't close the circle in time.
    """
    steps = {start: 0}
    queue = deque([start])
    while queue:
        book = queue.popleft()
        for earlier in incoming[book]:
            if earlier not in steps:
                steps[earlier] = steps[book] + 1
                queue.append(earlier)
    return steps


def _circle_from(
    start: str,
    size: int,
    arrows: dict[str, list[str]],
    remaining: set[str],
    by_id: dict[str, RoundEntryInfo],
    steps_home: dict[str, int],
) -> list[str] | None:
    """Follow arrows from `start` looking for a circle of exactly `size` books."""

    def follow(path: list[str], owners: set[str]) -> list[str] | None:
        for next_book in arrows[path[-1]]:
            if next_book not in remaining:
                continue
            if len(path) == size:
                if next_book == start:
                    return path  # back where we started: a circle
                continue
            if len(path) + steps_home.get(next_book, size) > size:
                continue  # from there we can't get back to the start in time
            owner = by_id[next_book].owner_id
            if next_book in path or owner in owners:
                continue  # each book and each person only once per loop
            found = follow(path + [next_book], owners | {owner})
            if found is not None:
                return found
        return None

    return follow([start], {by_id[start].owner_id})


def _to_trades(circle: list[str], by_id: dict[str, RoundEntryInfo]) -> list[ProposedTrade]:
    """Turn a circle of books into trades.

    In the circle A -> B -> C -> A, A's owner wants B, so B's owner gives
    B to A's owner, and so on around the circle.
    """
    trades = []
    for index, book in enumerate(circle):
        wanted = by_id[circle[(index + 1) % len(circle)]]
        trades.append(
            ProposedTrade(
                copy_id=wanted.copy_id,
                giver_id=wanted.owner_id,
                receiver_id=by_id[book].owner_id,
            )
        )
    return trades
