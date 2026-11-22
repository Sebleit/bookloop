# Person 2 owns this file: swap database operations.
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from secrets import randbelow
from typing import Any
from uuid import uuid4

from sqlalchemy import text

from bookloop.models import Copy, Loop, Offer
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


def _copy_from_row(row: Mapping[str, Any]) -> Copy:
    return Copy(
        id=row["id"],
        book_id=row["book_id"],
        owner_id=row["owner_id"],
        condition=row["condition"],
        highlighting=row["highlighting"],
        notes=row["notes"],
        status=row["status"],
        created_at=row["created_at"],
    )


def available_copies(
    *, owner_id: str | None = None, exclude_owner_id: str | None = None
) -> list[dict[str, Any]]:
    """Return available copies with their book details for offer forms."""
    if owner_id is not None and exclude_owner_id is not None:
        raise ValueError("Use owner_id or exclude_owner_id, not both.")

    owner_filter = "AND c.owner_id = :owner_id" if owner_id is not None else ""
    exclude_filter = "AND c.owner_id != :exclude_owner_id" if exclude_owner_id is not None else ""
    parameters = {
        key: value
        for key, value in {
            "owner_id": owner_id,
            "exclude_owner_id": exclude_owner_id,
        }.items()
        if value is not None
    }
    with transaction() as connection:
        rows = connection.execute(
            text(
                "SELECT c.id, c.book_id, c.owner_id, c.\"condition\", c.highlighting, "
                "c.notes, c.status, c.created_at, b.title, b.authors "
                "FROM copies c JOIN books b ON b.id = c.book_id "
                "WHERE c.status = 'available' "
                f"{owner_filter} {exclude_filter} "
                "ORDER BY b.title, c.id"
            ),
            parameters,
        ).mappings().all()

    return [
        {"copy": _copy_from_row(row), "title": row["title"], "authors": row["authors"]}
        for row in rows
    ]


def pending_offer_count(proposer_id: str) -> int:
    """Return the number of pending offers made by a user."""
    with transaction() as connection:
        return int(
            connection.execute(
                text(
                    "SELECT COUNT(*) FROM offers "
                    "WHERE proposer_id = :proposer_id AND status = 'pending'"
                ),
                {"proposer_id": proposer_id},
            ).scalar_one()
        )


def create_offer(
    proposer_id: str,
    offered_copy_id: str,
    requested_copy_id: str,
    expires_at: str,
) -> Offer:
    """Save a pending offer after the page has checked its rule."""
    offer = Offer(
        id=str(uuid4()),
        proposer_id=proposer_id,
        offered_copy_id=offered_copy_id,
        requested_copy_id=requested_copy_id,
        status="pending",
        created_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        expires_at=expires_at,
    )
    with transaction() as connection:
        connection.execute(
            text(
                "INSERT INTO offers "
                "(id, proposer_id, offered_copy_id, requested_copy_id, status, created_at, expires_at) "
                "VALUES (:id, :proposer_id, :offered_copy_id, :requested_copy_id, "
                ":status, :created_at, :expires_at)"
            ),
            {
                "id": offer.id,
                "proposer_id": offer.proposer_id,
                "offered_copy_id": offer.offered_copy_id,
                "requested_copy_id": offer.requested_copy_id,
                "status": offer.status,
                "created_at": offer.created_at,
                "expires_at": offer.expires_at,
            },
        )
    return offer


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
