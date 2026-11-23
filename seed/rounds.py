"""Demo data: a swap round that is ready to run.

Eli, Farah and Ana each want the next person's book, but no two of them want
each other's, so no direct swap is possible. When the moderator runs the
round, the loop finder finds the 3-way loop:

    Eli gets Farah's book, Farah gets Ana's, and Ana gets Eli's.

Ben also wants Eli's book, but nobody wants Ben's, so Ben gets no match and
his book goes back on his shelf. That shows both results in the demo.

The round's dates follow the day the demo data is built (entries closed
yesterday, wants close in two days, the meeting is in three days), so they
never look out of date, whenever the demo happens.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.engine import Connection


DEMO_ROUND = {
    "id": "round-demo",
    "name": "Winter textbook swap",
    "phase": "wants",
    "meet_place": "Nova SBE library, ground floor",
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


def _round_dates(now: datetime) -> dict[str, str]:
    """Entries closed yesterday at 18:00, wants close in two days, meeting in three days."""
    today = now.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    def as_text(moment: datetime) -> str:
        return moment.isoformat().replace("+00:00", "Z")

    return {
        "entries_close_at": as_text(today - timedelta(days=1) + timedelta(hours=18)),
        "wants_close_at": as_text(today + timedelta(days=2, hours=18)),
        "meet_time": as_text(today + timedelta(days=3, hours=14)),
    }


def seed(connection: Connection) -> None:
    """Insert the demo round, its entries and wants, and mark the books in_round."""
    connection.execute(
        text(
            "INSERT INTO rounds "
            "(id, name, phase, entries_close_at, wants_close_at, meet_place, meet_time, created_by) "
            "VALUES (:id, :name, :phase, :entries_close_at, :wants_close_at, "
            ":meet_place, :meet_time, :created_by)"
        ),
        {**DEMO_ROUND, **_round_dates(datetime.now(timezone.utc))},
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
