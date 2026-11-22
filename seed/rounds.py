"""Demo data: a swap round that is ready to run.

Eli, Farah and Ana each want the next person's book, but no two of them want
each other's, so no direct swap is possible. When the moderator runs the
round, the loop finder finds the 3-way loop:

    Eli gets Farah's book, Farah gets Ana's, and Ana gets Eli's.

Ben also wants Eli's book, but nobody wants Ben's, so Ben gets no match and
his book goes back on his shelf. That shows both results in the demo.
"""

from sqlalchemy import text
from sqlalchemy.engine import Connection


DEMO_ROUND = {
    "id": "round-demo",
    "name": "Winter textbook swap",
    "phase": "wants",
    "entries_close_at": "2026-11-20T18:00:00Z",
    "wants_close_at": "2026-12-15T18:00:00Z",
    "meet_place": "Nova SBE library, ground floor",
    "meet_time": "2026-12-16T14:00:00Z",
    "created_by": "user-moderator",
}

# (entry id, copy id): the copies come from seed/base.py.
ENTRIES = (
    ("entry-eli", "copy-05"),  # Eli: Calculus: Early Transcendentals
    ("entry-farah", "copy-06"),  # Farah: Principles of Economics
    ("entry-ana", "copy-07"),  # Ana: The Economics Book
    ("entry-ben", "copy-08"),  # Ben: World History: Patterns of Interaction
)

# (entry, wanted entry): "I'd accept that book in return for mine".
WANTS = (
    ("entry-eli", "entry-farah"),
    ("entry-farah", "entry-ana"),
    ("entry-ana", "entry-eli"),
    ("entry-ben", "entry-eli"),
)


def seed(connection: Connection) -> None:
    """Insert the demo round, its entries and wants, and mark the books in_round."""
    connection.execute(
        text(
            "INSERT INTO rounds "
            "(id, name, phase, entries_close_at, wants_close_at, meet_place, meet_time, created_by) "
            "VALUES (:id, :name, :phase, :entries_close_at, :wants_close_at, "
            ":meet_place, :meet_time, :created_by)"
        ),
        DEMO_ROUND,
    )
    connection.execute(
        text(
            "INSERT INTO round_entries (id, round_id, copy_id, min_partner_score) "
            "VALUES (:id, :round_id, :copy_id, 0)"
        ),
        [
            {"id": entry_id, "round_id": DEMO_ROUND["id"], "copy_id": copy_id}
            for entry_id, copy_id in ENTRIES
        ],
    )
    connection.execute(
        text("UPDATE copies SET status = 'in_round' WHERE id = :copy_id"),
        [{"copy_id": copy_id} for _, copy_id in ENTRIES],
    )
    connection.execute(
        text("INSERT INTO round_wants (entry_id, wanted_entry_id) VALUES (:entry, :wanted)"),
        [{"entry": entry, "wanted": wanted} for entry, wanted in WANTS],
    )
