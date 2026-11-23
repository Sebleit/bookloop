# Demo direct swaps.
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.engine import Connection


CREATED_AT = "2026-11-14T00:00:00Z"
PENDING_EXPIRES_AT = "2026-11-23T00:00:00Z"


def _next_full_hour() -> str:
    in_an_hour = datetime.now(timezone.utc) + timedelta(hours=1)
    return in_an_hour.replace(minute=0, second=0, microsecond=0).isoformat().replace("+00:00", "Z")


def _ben_offer_times() -> tuple[str, str]:
    """Ben made his offer yesterday at 16:00; it expires 72 hours later."""
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    made = today - timedelta(days=1) + timedelta(hours=16)
    return tuple(moment.isoformat().replace("+00:00", "Z") for moment in (made, made + timedelta(hours=72)))


def seed(connection: Connection) -> None:
    """Insert one completed and one pending direct swap for the demo, and an offer
    waiting for Carla's answer (Ben's They Say / I Say for her Business Essentials)."""
    offers = [
        {
            "id": "offer-demo-completed",
            "proposer_id": "user-ana",
            "offered_copy_id": "copy-01",
            "requested_copy_id": "copy-02",
            "status": "accepted",
            "created_at": CREATED_AT,
            "expires_at": PENDING_EXPIRES_AT,
        },
        {
            "id": "offer-demo-pending",
            "proposer_id": "user-carla",
            "offered_copy_id": "copy-03",
            "requested_copy_id": "copy-04",
            "status": "accepted",
            "created_at": CREATED_AT,
            "expires_at": PENDING_EXPIRES_AT,
        },
    ]
    made, expires = _ben_offer_times()
    offers.append(
        {
            "id": "offer-demo-ben",
            "proposer_id": "user-ben",
            "offered_copy_id": "copy-14",  # They Say / I Say
            "requested_copy_id": "copy-15",  # Carla's Business Essentials
            "status": "pending",
            "created_at": made,
            "expires_at": expires,
        }
    )
    connection.execute(
        text(
            "INSERT INTO offers "
            "(id, proposer_id, offered_copy_id, requested_copy_id, status, created_at, expires_at) "
            "VALUES (:id, :proposer_id, :offered_copy_id, :requested_copy_id, "
            ":status, :created_at, :expires_at)"
        ),
        offers,
    )

    loops = [
        {
            "id": "loop-demo-completed",
            "offer_id": "offer-demo-completed",
            "status": "completed",
            "meet_place": "Main library",
            "meet_time": "2026-11-15T14:00:00Z",
        },
        {
            "id": "loop-demo-pending",
            "offer_id": "offer-demo-pending",
            "status": "scheduled",
            "meet_place": "Student centre",
            # The next full hour after the demo data is built, so the meeting is "now".
            "meet_time": _next_full_hour(),
        },
    ]
    connection.execute(
        text(
            "INSERT INTO loops "
            "(id, source, offer_id, round_id, status, meet_place, meet_time, no_show_user_id) "
            "VALUES (:id, 'offer', :offer_id, NULL, :status, :meet_place, :meet_time, NULL)"
        ),
        loops,
    )

    trades = [
        {
            "id": "trade-demo-completed-a",
            "loop_id": "loop-demo-completed",
            "copy_id": "copy-01",
            "giver_id": "user-ana",
            "receiver_id": "user-ben",
            "handoff_code": "1111",
            "status": "completed",
            "completed_at": "2026-11-15T14:10:00Z",
        },
        {
            "id": "trade-demo-completed-b",
            "loop_id": "loop-demo-completed",
            "copy_id": "copy-02",
            "giver_id": "user-ben",
            "receiver_id": "user-ana",
            "handoff_code": "2222",
            "status": "completed",
            "completed_at": "2026-11-15T14:10:00Z",
        },
        {
            "id": "trade-demo-pending-a",
            "loop_id": "loop-demo-pending",
            "copy_id": "copy-03",
            "giver_id": "user-carla",
            "receiver_id": "user-dina",
            "handoff_code": "3333",
            "status": "pending",
            "completed_at": None,
        },
        {
            "id": "trade-demo-pending-b",
            "loop_id": "loop-demo-pending",
            "copy_id": "copy-04",
            "giver_id": "user-dina",
            "receiver_id": "user-carla",
            "handoff_code": "4444",
            "status": "pending",
            "completed_at": None,
        },
    ]
    connection.execute(
        text(
            "INSERT INTO trades "
            "(id, loop_id, copy_id, giver_id, receiver_id, handoff_code, "
            "code_attempts, status, completed_at) "
            "VALUES (:id, :loop_id, :copy_id, :giver_id, :receiver_id, "
            ":handoff_code, 0, :status, :completed_at)"
        ),
        trades,
    )

    connection.execute(
        text(
            "UPDATE copies SET owner_id = CASE id "
            "WHEN 'copy-01' THEN 'user-ben' WHEN 'copy-02' THEN 'user-ana' END, "
            "status = 'available' WHERE id IN ('copy-01', 'copy-02')"
        )
    )
    connection.execute(
        text("UPDATE copies SET status = 'reserved' WHERE id IN ('copy-03', 'copy-04')")
    )
