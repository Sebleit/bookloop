"""Demo data: three weekly swap rounds, each at a different moment.

Rounds run every week, so the demo can show every step without waiting:

- Last week's round has run: Ben, Ana and Farah met, Ben's and Ana's books
  changed hands, but Farah didn't hand over hers, and Ben reported it. The
  moderator sees it under "Books not handed over". Eli's book had no match.
- This week's round is ready to run: 23 books from 15 students, since some
  put in two. Carla and Ben want each other's books, so they swap (in the
  demo, Carla types the code shown in Ben's window). Eli, Farah and Ana each
  want the next person's book, but no two of them want each other's, so no
  direct swap is possible: the loop finder finds the 3-way loop, where Eli
  gets Farah's book, Farah gets Ana's, and Ana gets Eli's. Their classmates
  make four more loops: Gonçalo and Inês swap directly, Beatriz, Diogo and
  Leonor make a 3-way loop, Joana, Miguel, Sofia and Tiago a 4-way one, and
  Joana's, Miguel's and Sofia's second books another 3-way one. So: 6 loops,
  17 books change hands, 6 go back on the shelf.
- Next week's round is open for books: 11 are in already, from 7 students, so
  a student can enter theirs, the moderator can close entries, and everyone
  can tick what they'd accept.

Each round is named after its handoff day ("Weekly swap · 26 Nov"). The dates
follow the day the demo data is built, so they never look out of date,
whenever the demo happens.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.engine import Connection

from bookloop.rules.handoffs import new_code
from bookloop.storage.reviews_repo import MISSING_HANDOFF

PLACE = "Nova SBE library, ground floor"

# id, phase, and the days (from today) when entries close, wants close and people meet.
ROUNDS = (
    ("round-last", "matched", -8, -5, -4),
    ("round-demo", "wants", -1, 2, 3),
    ("round-next", "entries", 6, 9, 10),
)

# (entry id, round, copy id): the copies come from seed/base.py, or from LAST_COPIES below.
ENTRIES = (
    ("entry-eli", "round-demo", "copy-05"),  # Eli: Calculus: Early Transcendentals
    ("entry-farah", "round-demo", "copy-06"),  # Farah: Principles of Economics
    ("entry-ana", "round-demo", "copy-07"),  # Ana: The Economics Book
    ("entry-ben", "round-demo", "copy-08"),  # Ben: World History: Patterns of Interaction
    ("entry-carla", "round-demo", "copy-09"),  # Carla: A Little History of the World
    ("entry-goncalo", "round-demo", "copy-29"),  # Gonçalo: Python Crash Course
    ("entry-ines", "round-demo", "copy-31"),  # Inês: Principles of Economics
    ("entry-beatriz", "round-demo", "copy-27"),  # Beatriz: Psychology
    ("entry-diogo", "round-demo", "copy-28"),  # Diogo: Business Essentials
    ("entry-leonor", "round-demo", "copy-33"),  # Leonor: A Little History of the World
    ("entry-joana", "round-demo", "copy-32"),  # Joana: Introduction to Algorithms
    ("entry-miguel", "round-demo", "copy-35"),  # Miguel: University Physics
    ("entry-sofia", "round-demo", "copy-38"),  # Sofia: A Mind for Numbers
    ("entry-tiago", "round-demo", "copy-39"),  # Tiago: They Say / I Say
    ("entry-afonso", "round-demo", "copy-26"),  # Afonso: Biology
    # Second books in this week's round.
    ("entry-joana-2", "round-demo", "copy-40"),  # Joana: Chemistry: The Central Science
    ("entry-miguel-2", "round-demo", "copy-41"),  # Miguel: Automate the Boring Stuff with Python
    ("entry-sofia-2", "round-demo", "copy-42"),  # Sofia: World History: Patterns of Interaction
    ("entry-ines-2", "round-demo", "copy-46"),  # Inês: Calculus: Early Transcendentals
    ("entry-beatriz-2", "round-demo", "copy-48"),  # Beatriz: Calculus: Early Transcendentals
    ("entry-diogo-2", "round-demo", "copy-49"),  # Diogo: The Economics Book
    ("entry-goncalo-2", "round-demo", "copy-50"),  # Gonçalo: Chemistry: The Central Science
    ("entry-afonso-2", "round-demo", "copy-51"),  # Afonso: They Say / I Say
    ("entry-last-ana", "round-last", "copy-last-ana"),
    ("entry-last-ben", "round-last", "copy-last-ben"),
    ("entry-last-farah", "round-last", "copy-last-farah"),
    ("entry-last-eli", "round-last", "copy-last-eli"),
    ("entry-next-ana", "round-next", "copy-19"),  # Ana: A Mind for Numbers
    ("entry-next-ben", "round-next", "copy-20"),  # Ben: Calculus: Early Transcendentals
    ("entry-next-farah", "round-next", "copy-12"),  # Farah: University Physics
    ("entry-next-hugo", "round-next", "copy-30"),  # Hugo: The Economics Book
    ("entry-next-marta", "round-next", "copy-34"),  # Marta: Automate the Boring Stuff with Python
    ("entry-next-nuno", "round-next", "copy-36"),  # Nuno: Calculus: Early Transcendentals
    ("entry-next-rita", "round-next", "copy-37"),  # Rita: World History: Patterns of Interaction
    ("entry-next-hugo-2", "round-next", "copy-43"),  # Hugo: Python Crash Course
    ("entry-next-marta-2", "round-next", "copy-44"),  # Marta: Principles of Economics
    ("entry-next-nuno-2", "round-next", "copy-45"),  # Nuno: Psychology
    ("entry-next-rita-2", "round-next", "copy-47"),  # Rita: Biology
)

# (entry, wanted entry): "I'd accept that book in return for mine".
WANTS = (
    ("entry-eli", "entry-farah"),
    ("entry-farah", "entry-ana"),
    ("entry-ana", "entry-eli"),
    ("entry-ben", "entry-eli"),
    ("entry-ben", "entry-carla"),  # Ben and Carla want each other's books
    ("entry-carla", "entry-ben"),
    ("entry-goncalo", "entry-ines"),  # a direct swap
    ("entry-ines", "entry-goncalo"),
    ("entry-beatriz", "entry-diogo"),  # a 3-way loop
    ("entry-diogo", "entry-leonor"),
    ("entry-leonor", "entry-beatriz"),
    ("entry-joana", "entry-miguel"),  # a 4-way loop
    ("entry-miguel", "entry-sofia"),
    ("entry-sofia", "entry-tiago"),
    ("entry-tiago", "entry-joana"),
    ("entry-afonso", "entry-goncalo"),  # nobody wants Afonso's book: no match
    ("entry-joana-2", "entry-miguel-2"),  # second books: another 3-way loop
    ("entry-miguel-2", "entry-sofia-2"),
    ("entry-sofia-2", "entry-joana-2"),
    # Second books nobody wants: they go back on the shelf.
    ("entry-ines-2", "entry-leonor"),
    ("entry-beatriz-2", "entry-farah"),
    ("entry-goncalo-2", "entry-tiago"),
    ("entry-afonso-2", "entry-ines-2"),
    # Some people tick more than one book. Diogo's second book is wanted, but
    # Diogo ticked nothing for it, so it can't be in a loop.
    ("entry-leonor", "entry-diogo-2"),
    ("entry-tiago", "entry-diogo-2"),
    ("entry-last-ana", "entry-last-ben"),
    ("entry-last-ben", "entry-last-farah"),
    ("entry-last-farah", "entry-last-ana"),
    ("entry-last-eli", "entry-last-ana"),  # nobody wants Eli's book: no match
)

# Last week's books: (copy, book, condition, highlighting, first owner, owner now, status now).
LAST_COPIES = (
    ("copy-last-ana", "book-10", 3, "light", "user-ana", "user-farah", "available"),  # Biology: handed over
    ("copy-last-ben", "book-11", 4, "none", "user-ben", "user-ana", "available"),  # Chemistry: handed over
    ("copy-last-farah", "book-13", 3, "none", "user-farah", "user-farah", "reserved"),  # Psychology: not yet
    ("copy-last-eli", "book-01", 2, "heavy", "user-eli", "user-eli", "available"),  # no match: back on the shelf
)

# Last week's loop: (trade, copy, giver, receiver, handed over). Codes are random.
LAST_TRADES = (
    ("trade-last-ben", "copy-last-ben", "user-ben", "user-ana", True),
    ("trade-last-ana", "copy-last-ana", "user-ana", "user-farah", True),
    ("trade-last-farah", "copy-last-farah", "user-farah", "user-ben", False),
)


def _as_text(moment: datetime) -> str:
    return moment.isoformat().replace("+00:00", "Z")


def round_name(meet_time: datetime) -> str:
    """'Weekly swap · 26 Nov': named after the handoff day."""
    return f"Weekly swap · {meet_time.day} {meet_time:%b}"


def _round_rows(now: datetime) -> list[dict]:
    today = now.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    rows = []
    for round_id, phase, entries_close, wants_close, meet in ROUNDS:
        meet_time = today + timedelta(days=meet, hours=14)
        rows.append({
            "id": round_id,
            "name": round_name(meet_time),
            "phase": phase,
            "entries_close_at": _as_text(today + timedelta(days=entries_close, hours=18)),
            "wants_close_at": _as_text(today + timedelta(days=wants_close, hours=18)),
            "meet_place": PLACE,
            "meet_time": _as_text(meet_time),
            "created_by": "user-moderator",
        })
    return rows


def seed(connection: Connection) -> None:
    """Insert the three rounds, their entries and wants, and last week's swap."""
    now = datetime.now(timezone.utc)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    rounds = _round_rows(now)
    connection.execute(
        text(
            "INSERT INTO rounds "
            "(id, name, phase, entries_close_at, wants_close_at, meet_place, meet_time, created_by) "
            "VALUES (:id, :name, :phase, :entries_close_at, :wants_close_at, "
            ":meet_place, :meet_time, :created_by)"
        ),
        rounds,
    )
    connection.execute(
        text(
            'INSERT INTO copies (id, book_id, owner_id, "condition", highlighting, notes, status, created_at) '
            "VALUES (:id, :book, :owner, :condition, :highlighting, NULL, :status, :at)"
        ),
        [
            {"id": copy_id, "book": book, "owner": owner, "condition": condition,
             "highlighting": highlighting, "status": status, "at": _as_text(today - timedelta(days=12) + timedelta(hours=10))}
            for copy_id, book, condition, highlighting, _, owner, status in LAST_COPIES
        ],
    )
    connection.execute(
        text(
            "INSERT INTO round_entries (id, round_id, copy_id, min_partner_score) "
            "VALUES (:id, :round_id, :copy_id, 0)"
        ),
        [{"id": entry_id, "round_id": round_id, "copy_id": copy_id} for entry_id, round_id, copy_id in ENTRIES],
    )
    # Books in an open round are "in_round" until it runs.
    connection.execute(
        text("UPDATE copies SET status = 'in_round' WHERE id = :copy_id"),
        [{"copy_id": copy_id} for _, round_id, copy_id in ENTRIES if round_id != "round-last"],
    )
    connection.execute(
        text("INSERT INTO round_wants (entry_id, wanted_entry_id) VALUES (:entry, :wanted)"),
        [{"entry": entry, "wanted": wanted} for entry, wanted in WANTS],
    )
    _seed_last_weeks_swap(connection, rounds[0], today)


def _seed_last_weeks_swap(connection: Connection, last: dict, today: datetime) -> None:
    """Last week's loop: two books handed over, one not, and Ben's report about it."""
    met = datetime.fromisoformat(last["meet_time"].replace("Z", "+00:00"))
    connection.execute(
        text(
            "INSERT INTO loops (id, source, offer_id, round_id, status, meet_place, meet_time, no_show_user_id) "
            "VALUES ('loop-last', 'round', NULL, :round, 'scheduled', :place, :at, NULL)"
        ),
        {"round": last["id"], "place": last["meet_place"], "at": last["meet_time"]},
    )
    connection.execute(
        text(
            "INSERT INTO trades (id, loop_id, copy_id, giver_id, receiver_id, handoff_code, "
            "code_attempts, status, completed_at) VALUES (:id, 'loop-last', :copy, :giver, "
            ":receiver, :code, 0, :status, :done)"
        ),
        [
            {"id": trade_id, "copy": copy_id, "giver": giver, "receiver": receiver, "code": new_code(),
             "status": "completed" if done else "pending",
             "done": _as_text(met + timedelta(minutes=10)) if done else None}
            for trade_id, copy_id, giver, receiver, done in LAST_TRADES
        ],
    )
    # Ben reports that Farah didn't hand over her book: the moderator checks it.
    reported = _as_text(met + timedelta(hours=1))
    connection.execute(
        text("INSERT INTO entity_ids (table_name, entity_key) VALUES ('trades', 'trade-last-farah')")
    )
    connection.execute(
        text(
            "INSERT INTO audit_log (id, actor_id, action, target_table, target_id, created_at) "
            "VALUES ('audit-last-report', 'user-ben', :action, 'trades', 'trade-last-farah', :at)"
        ),
        {"action": MISSING_HANDOFF, "at": reported},
    )
    connection.execute(
        text(
            "INSERT INTO notifications (id, user_id, text, link, read, created_at) "
            "VALUES (:id, :user, :text, NULL, 0, :at)"
        ),
        [
            {"id": "note-last-moderator", "user": "user-moderator", "at": reported,
             "text": "Ben says Farah didn't hand over “Psychology”. Check it on the Moderator page."},
            {"id": "note-last-farah", "user": "user-farah", "at": reported,
             "text": "Ben reported that you didn't hand over “Psychology”. A moderator will check what happened."},
        ],
    )
