# Demo direct swaps.
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.engine import Connection

from bookloop.rules.handoffs import new_code  # random, like real swaps


CREATED_AT = "2026-11-14T00:00:00Z"
PENDING_EXPIRES_AT = "2026-11-23T00:00:00Z"


def _offer_times() -> tuple[str, str]:
    """Leonor made her offer yesterday at 16:00; it expires 72 hours later."""
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    made = today - timedelta(days=1) + timedelta(hours=16)
    return tuple(moment.isoformat().replace("+00:00", "Z") for moment in (made, made + timedelta(hours=72)))


def seed(connection: Connection) -> None:
    """Insert one completed and one pending direct swap for the demo, and an offer
    waiting for Carla's answer (Leonor's University Physics for her Business Essentials).
    Leonor is a classmate who never logs in, so accepting shows a made-up email."""
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
    made, expires = _offer_times()
    offers.append(
        {
            "id": "offer-demo-leonor",
            "proposer_id": "extra-leonor",
            "offered_copy_id": "copy-52",  # University Physics (seed/base.py)
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
            # A direct swap: Carla and Dina agree where and when by email.
            "meet_place": None,
            "meet_time": None,
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
            "handoff_code": new_code(),
            "status": "completed",
            "completed_at": "2026-11-15T14:10:00Z",
        },
        {
            "id": "trade-demo-completed-b",
            "loop_id": "loop-demo-completed",
            "copy_id": "copy-02",
            "giver_id": "user-ben",
            "receiver_id": "user-ana",
            "handoff_code": new_code(),
            "status": "completed",
            "completed_at": "2026-11-15T14:10:00Z",
        },
        {
            "id": "trade-demo-pending-a",
            "loop_id": "loop-demo-pending",
            "copy_id": "copy-03",
            "giver_id": "user-carla",
            "receiver_id": "user-dina",
            "handoff_code": new_code(),
            "status": "pending",
            "completed_at": None,
        },
        {
            "id": "trade-demo-pending-b",
            "loop_id": "loop-demo-pending",
            "copy_id": "copy-04",
            "giver_id": "user-dina",
            "receiver_id": "user-carla",
            "handoff_code": new_code(),
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
