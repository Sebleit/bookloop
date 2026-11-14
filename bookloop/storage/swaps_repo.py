# Person 2 owns this file: swap database operations.
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from secrets import randbelow
from typing import Any
from uuid import uuid4

from sqlalchemy import text

from bookloop.models import Loop
from bookloop.storage.db import transaction


def _value(item: Any, key: str, default: Any = None) -> Any:
    if isinstance(item, Mapping):
        return item.get(key, default)
    return getattr(item, key, default)


def _source_details(source: Any) -> tuple[str, str | None]:
    if isinstance(source, str):
        source_type = source
        source_id = None
    else:
        source_type = _value(source, "source", _value(source, "type"))
        source_id = _value(source, f"{source_type}_id") or _value(source, "id")

    if source_type not in {"offer", "round"}:
        raise ValueError("Source must be 'offer' or 'round'.")
    return source_type, source_id


def create_loop(
    trades: Sequence[Any], source: Any, meet_place: str | None, meet_time: str | None
) -> Loop:
    """Create a loop and reserve all its copies as one atomic database change."""
    if len(trades) < 2:
        raise ValueError("A loop must contain at least two trades.")

    source_type, source_id = _source_details(source)
    normalized_trades = []
    for trade in trades:
        copy_id = _value(trade, "copy_id")
        giver_id = _value(trade, "giver_id")
        receiver_id = _value(trade, "receiver_id")
        if not copy_id or not giver_id or not receiver_id:
            raise ValueError("Each trade needs a copy, giver, and receiver.")
        normalized_trades.append(
            {"copy_id": str(copy_id), "giver_id": str(giver_id), "receiver_id": str(receiver_id)}
        )

    copy_ids = [trade["copy_id"] for trade in normalized_trades]
    if len(copy_ids) != len(set(copy_ids)):
        raise ValueError("A loop cannot use the same copy more than once.")

    loop_id = str(uuid4())
    created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    loop = Loop(
        id=loop_id,
        source=source_type,
        offer_id=source_id if source_type == "offer" else None,
        round_id=source_id if source_type == "round" else None,
        status="scheduled",
        meet_place=meet_place,
        meet_time=meet_time,
        no_show_user_id=None,
    )

    with transaction() as connection:
        for copy_id in copy_ids:
            row = connection.execute(
                text("SELECT status FROM copies WHERE id = :copy_id"),
                {"copy_id": copy_id},
            ).first()
            if row is None:
                raise ValueError(f"Copy not found: {copy_id}")
            if row.status != "available":
                raise ValueError(f"Copy is not available: {copy_id}")

        connection.execute(
            text(
                "INSERT INTO loops "
                "(id, source, offer_id, round_id, status, meet_place, meet_time, no_show_user_id) "
                "VALUES (:id, :source, :offer_id, :round_id, :status, :meet_place, :meet_time, NULL)"
            ),
            {
                "id": loop.id,
                "source": loop.source,
                "offer_id": loop.offer_id,
                "round_id": loop.round_id,
                "status": loop.status,
                "meet_place": loop.meet_place,
                "meet_time": loop.meet_time,
            },
        )

        for trade in normalized_trades:
            result = connection.execute(
                text(
                    "UPDATE copies SET status = 'reserved' "
                    "WHERE id = :copy_id AND status = 'available'"
                ),
                {"copy_id": trade["copy_id"]},
            )
            if result.rowcount != 1:
                raise ValueError(f"Copy is no longer available: {trade['copy_id']}")

            connection.execute(
                text(
                    "INSERT INTO trades "
                    "(id, loop_id, copy_id, giver_id, receiver_id, handoff_code, "
                    "code_attempts, status, completed_at) "
                    "VALUES (:id, :loop_id, :copy_id, :giver_id, :receiver_id, "
                    ":handoff_code, 0, 'pending', NULL)"
                ),
                {
                    "id": str(uuid4()),
                    "loop_id": loop.id,
                    "copy_id": trade["copy_id"],
                    "giver_id": trade["giver_id"],
                    "receiver_id": trade["receiver_id"],
                    "handoff_code": f"{randbelow(10_000):04d}",
                },
            )

    return loop
