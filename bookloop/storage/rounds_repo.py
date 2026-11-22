"""Saving and loading swap rounds.

This is the only file that reads or writes the rounds, round_entries and
round_wants tables. It never decides whether something is allowed: the page
asks the rules in bookloop/rules/rounds.py first, then calls these functions.
"""

from dataclasses import dataclass
from uuid import uuid4

from sqlalchemy import text

from bookloop.models import Copy, Loop, Round, RoundWant
from bookloop.rules.loop_finder import find_loops
from bookloop.rules.rounds import RoundEntryInfo, next_phase
from bookloop.services.notify import notify
from bookloop.storage.db import transaction
from bookloop.storage.reviews_repo import swapper_score
from bookloop.storage.swaps_repo import create_loop


ROUND_COLUMNS = (
    "id, name, phase, entries_close_at, wants_close_at, meet_place, meet_time, created_by"
)


@dataclass(frozen=True)
class EntryDetails:
    """A book in a round, with what the page needs to show it."""

    info: RoundEntryInfo
    title: str
    owner_name: str
    condition: int
    highlighting: str
    copy_status: str


@dataclass(frozen=True)
class CopyChoice:
    """One of a student's own books, with its title, for the "enter a book" list."""

    copy: Copy
    title: str


@dataclass(frozen=True)
class MyTrade:
    """One book a user gives or receives in a round's loop."""

    title: str
    giver_id: str
    giver_name: str
    receiver_id: str
    receiver_name: str
    status: str
    meet_place: str | None
    meet_time: str | None


@dataclass(frozen=True)
class RunResult:
    """What happened when a round was run."""

    loops: list[Loop]
    books_swapped: int
    books_returned: int


# --- Rounds ----------------------------------------------------------------


def create_round(
    name: str,
    entries_close_at: str,
    wants_close_at: str,
    meet_place: str,
    meet_time: str,
    created_by: str,
) -> Round:
    """Save a new round. It starts in the entries phase."""
    round = Round(
        id=str(uuid4()),
        name=name.strip(),
        phase="entries",
        entries_close_at=entries_close_at,
        wants_close_at=wants_close_at,
        meet_place=meet_place.strip(),
        meet_time=meet_time,
        created_by=created_by,
    )
    with transaction() as connection:
        connection.execute(
            text(
                f"INSERT INTO rounds ({ROUND_COLUMNS}) VALUES (:id, :name, :phase, "
                ":entries_close_at, :wants_close_at, :meet_place, :meet_time, :created_by)"
            ),
            round.__dict__,
        )
    return round


def get_round(round_id: str) -> Round | None:
    """Get one round, or None if it doesn't exist."""
    with transaction() as connection:
        row = connection.execute(
            text(f"SELECT {ROUND_COLUMNS} FROM rounds WHERE id = :id"), {"id": round_id}
        ).mappings().first()
    return Round(**row) if row else None


def list_rounds() -> list[Round]:
    """All rounds, the most recent first."""
    with transaction() as connection:
        rows = connection.execute(
            text(f"SELECT {ROUND_COLUMNS} FROM rounds ORDER BY entries_close_at DESC, name")
        ).mappings().all()
    return [Round(**row) for row in rows]


def advance_round(round_id: str) -> Round:
    """Move a round from entries to wants, or from matched to closed.

    Going from wants to matched happens only through run_round().
    """
    round = get_round(round_id)
    if round is None:
        raise ValueError("Round not found.")
    if round.phase in ("wants", "closed"):
        raise ValueError(f"A round in the {round.phase} phase can't be moved forward here.")

    new_phase = next_phase(round.phase)
    with transaction() as connection:
        result = connection.execute(
            text("UPDATE rounds SET phase = :new WHERE id = :id AND phase = :old"),
            {"new": new_phase, "id": round_id, "old": round.phase},
        )
        if result.rowcount != 1:
            raise ValueError("Someone else changed this round. Reload the page.")
    return get_round(round_id)


# --- Entries and wants -----------------------------------------------------


def available_copies(owner_id: str) -> list[CopyChoice]:
    """A student's books that are available, so they can be entered in a round."""
    with transaction() as connection:
        rows = connection.execute(
            text(
                'SELECT c.id, c.book_id, c.owner_id, c."condition", c.highlighting, c.notes, '
                "c.status, c.created_at, b.title FROM copies c "
                "JOIN books b ON b.id = c.book_id "
                "WHERE c.owner_id = :owner_id AND c.status = 'available' ORDER BY b.title, c.id"
            ),
            {"owner_id": owner_id},
        ).mappings().all()
    return [
        CopyChoice(copy=Copy(**{key: row[key] for key in row if key != "title"}), title=row["title"])
        for row in rows
    ]


def enter_copy(round_id: str, copy_id: str) -> RoundEntryInfo:
    """Put a book in a round. It becomes in_round, so it can't be offered elsewhere."""
    entry_id = str(uuid4())
    with transaction() as connection:
        result = connection.execute(
            text(
                "UPDATE copies SET status = 'in_round' "
                "WHERE id = :copy_id AND status = 'available'"
            ),
            {"copy_id": copy_id},
        )
        if result.rowcount != 1:
            raise ValueError("That book is no longer available.")
        connection.execute(
            text(
                "INSERT INTO round_entries (id, round_id, copy_id, min_partner_score) "
                "VALUES (:id, :round_id, :copy_id, 0)"
            ),
            {"id": entry_id, "round_id": round_id, "copy_id": copy_id},
        )
        owner_id = connection.execute(
            text("SELECT owner_id FROM copies WHERE id = :copy_id"), {"copy_id": copy_id}
        ).scalar_one()
    return RoundEntryInfo(id=entry_id, round_id=round_id, copy_id=copy_id, owner_id=owner_id)


def list_entries(round_id: str) -> list[EntryDetails]:
    """Every book entered in a round, with its title and owner."""
    with transaction() as connection:
        rows = connection.execute(
            text(
                "SELECT e.id, e.round_id, e.copy_id, e.min_partner_score, c.owner_id, "
                'c."condition", c.highlighting, c.status, b.title, p.display_name '
                "FROM round_entries e "
                "JOIN copies c ON c.id = e.copy_id "
                "JOIN books b ON b.id = c.book_id "
                "JOIN profiles p ON p.id = c.owner_id "
                "WHERE e.round_id = :round_id ORDER BY b.title, p.display_name, e.id"
            ),
            {"round_id": round_id},
        ).mappings().all()
    return [
        EntryDetails(
            info=RoundEntryInfo(
                id=row["id"],
                round_id=row["round_id"],
                copy_id=row["copy_id"],
                owner_id=row["owner_id"],
                min_partner_score=float(row["min_partner_score"]),
            ),
            title=row["title"],
            owner_name=row["display_name"],
            condition=row["condition"],
            highlighting=row["highlighting"],
            copy_status=row["status"],
        )
        for row in rows
    ]


def get_wants(round_id: str) -> list[RoundWant]:
    """Every "I'd accept this book for mine" choice in a round."""
    with transaction() as connection:
        rows = connection.execute(
            text(
                "SELECT w.entry_id, w.wanted_entry_id FROM round_wants w "
                "JOIN round_entries e ON e.id = w.entry_id "
                "WHERE e.round_id = :round_id ORDER BY w.entry_id, w.wanted_entry_id"
            ),
            {"round_id": round_id},
        ).mappings().all()
    return [RoundWant(**row) for row in rows]


def save_wants(entry_id: str, wanted_entry_ids: list[str], min_partner_score: float) -> None:
    """Replace the wants for one entry, and its minimum partner score, together."""
    with transaction() as connection:
        connection.execute(
            text("DELETE FROM round_wants WHERE entry_id = :entry_id"), {"entry_id": entry_id}
        )
        for wanted_id in dict.fromkeys(wanted_entry_ids):  # skips duplicates, keeps order
            connection.execute(
                text(
                    "INSERT INTO round_wants (entry_id, wanted_entry_id) "
                    "VALUES (:entry_id, :wanted_id)"
                ),
                {"entry_id": entry_id, "wanted_id": wanted_id},
            )
        connection.execute(
            text("UPDATE round_entries SET min_partner_score = :score WHERE id = :entry_id"),
            {"score": min_partner_score, "entry_id": entry_id},
        )


# --- Running a round -------------------------------------------------------


def run_round(round_id: str) -> RunResult:
    """Find the loops, create them, put unmatched books back, and tell everyone.

    1. Mark the round as matched straight away, so it can never run twice.
    2. find_loops() decides the loops; create_loop() saves each one.
    3. Books that weren't matched go back to available.
    4. notify() tells every person in the round what happened.

    If something goes wrong halfway, the round goes back to the wants phase.
    Loops already created stay, and running again skips their books.
    """
    with transaction() as connection:
        claimed = connection.execute(
            text("UPDATE rounds SET phase = 'matched' WHERE id = :id AND phase = 'wants'"),
            {"id": round_id},
        )
        if claimed.rowcount != 1:
            raise ValueError("This round has already been run, or it isn't in the wants phase.")

    try:
        round = get_round(round_id)
        details = [entry for entry in list_entries(round_id) if entry.copy_status == "in_round"]
        entries = [entry.info for entry in details]
        owners = {entry.owner_id for entry in entries}
        scores = {owner: swapper_score(owner).score for owner in owners}
        proposed = find_loops(entries, get_wants(round_id), scores)

        loops = []
        for trades in proposed:
            loops.append(_create_round_loop(round, trades))

        matched = {trade.copy_id for trades in proposed for trade in trades}
        unmatched = [entry.copy_id for entry in entries if entry.copy_id not in matched]
        _move_copies(unmatched, from_status="in_round", to_status="available")
    except Exception:
        with transaction() as connection:
            connection.execute(
                text("UPDATE rounds SET phase = 'wants' WHERE id = :id"), {"id": round_id}
            )
        raise

    _notify_everyone(round, details, proposed)
    return RunResult(loops=loops, books_swapped=len(matched), books_returned=len(unmatched))


def _create_round_loop(round: Round, trades: list) -> Loop:
    """Save one loop with the shared create_loop().

    create_loop() only accepts available books, so the loop's books go from
    in_round back to available just before it reserves them.
    """
    copy_ids = [trade.copy_id for trade in trades]
    _move_copies(copy_ids, from_status="in_round", to_status="available")
    try:
        return create_loop(
            trades, {"source": "round", "round_id": round.id}, round.meet_place, round.meet_time
        )
    except Exception:
        _move_copies(copy_ids, from_status="available", to_status="in_round")
        raise


def _move_copies(copy_ids: list[str], from_status: str, to_status: str) -> None:
    """Change the status of several copies, but only those still in from_status."""
    with transaction() as connection:
        for copy_id in copy_ids:
            connection.execute(
                text("UPDATE copies SET status = :new WHERE id = :id AND status = :old"),
                {"new": to_status, "id": copy_id, "old": from_status},
            )


def _notify_everyone(round: Round, details: list[EntryDetails], proposed: list) -> None:
    """Send each person one message per loop they're in, and one per unmatched book."""
    titles = {entry.info.copy_id: entry.title for entry in details}
    names = {entry.info.owner_id: entry.owner_name for entry in details}
    matched = set()

    for trades in proposed:
        for person in dict.fromkeys(trade.giver_id for trade in trades):
            gives = next(trade for trade in trades if trade.giver_id == person)
            gets = next(trade for trade in trades if trade.receiver_id == person)
            matched.add(gives.copy_id)
            notify(
                person,
                f"Swap round “{round.name}”: give “{titles[gives.copy_id]}” "
                f"to {names[gives.receiver_id]} and receive “{titles[gets.copy_id]}” "
                f"from {names[gets.giver_id]}. Your handoff details are in My Swaps.",
                None,
            )

    for entry in details:
        if entry.info.copy_id not in matched:
            notify(
                entry.info.owner_id,
                f"Swap round “{round.name}”: no match for “{entry.title}” "
                "this time. It's back on your shelf.",
                None,
            )


# --- Results ---------------------------------------------------------------


def my_trades(round_id: str, user_id: str) -> list[MyTrade]:
    """The trades in this round's loops where the user gives or receives a book."""
    with transaction() as connection:
        rows = connection.execute(
            text(
                "SELECT b.title, t.giver_id, g.display_name AS giver_name, t.receiver_id, "
                "r.display_name AS receiver_name, t.status, l.meet_place, l.meet_time "
                "FROM trades t "
                "JOIN loops l ON l.id = t.loop_id "
                "JOIN copies c ON c.id = t.copy_id "
                "JOIN books b ON b.id = c.book_id "
                "JOIN profiles g ON g.id = t.giver_id "
                "JOIN profiles r ON r.id = t.receiver_id "
                "WHERE l.round_id = :round_id "
                "AND (t.giver_id = :user_id OR t.receiver_id = :user_id) "
                "ORDER BY l.id, t.giver_id = :user_id DESC"
            ),
            {"round_id": round_id, "user_id": user_id},
        ).mappings().all()
    return [MyTrade(**row) for row in rows]


def traded_copy_ids(round_id: str) -> set[str]:
    """Every book that changes hands in this round's loops."""
    with transaction() as connection:
        rows = connection.execute(
            text(
                "SELECT t.copy_id FROM trades t JOIN loops l ON l.id = t.loop_id "
                "WHERE l.round_id = :round_id"
            ),
            {"round_id": round_id},
        ).scalars().all()
    return set(rows)


def count_loops(round_id: str) -> int:
    """How many loops a round created."""
    with transaction() as connection:
        return connection.execute(
            text("SELECT COUNT(*) FROM loops WHERE round_id = :round_id"), {"round_id": round_id}
        ).scalar_one()
