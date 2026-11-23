# Swap database operations.
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import text

from bookloop.models import Copy, Loop, Offer
from bookloop.models import Trade
from bookloop.rules.handoffs import check_code, is_locked, new_code, no_show_outcome
from bookloop.rules.offers import can_accept, can_cancel, is_expired
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
                "c.notes, c.status, c.created_at, b.title, b.authors, "
                "p.display_name AS owner_name "
                "FROM copies c JOIN books b ON b.id = c.book_id "
                "JOIN profiles p ON p.id = c.owner_id "
                "WHERE c.status = 'available' "
                f"{owner_filter} {exclude_filter} "
                "ORDER BY b.title, c.id"
            ),
            parameters,
        ).mappings().all()

    return [
        {
            "copy": _copy_from_row(row),
            "title": row["title"],
            "authors": row["authors"],
            "owner_name": row["owner_name"],
        }
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


def _offer_from_row(row: Mapping[str, Any]) -> Offer:
    return Offer(
        id=row["id"],
        proposer_id=row["proposer_id"],
        offered_copy_id=row["offered_copy_id"],
        requested_copy_id=row["requested_copy_id"],
        status=row["status"],
        created_at=row["created_at"],
        expires_at=row["expires_at"],
    )


def offers_for_user(user_id: str) -> list[dict[str, Any]]:
    """Return outgoing and incoming offers with book details for the Offers page."""
    with transaction() as connection:
        rows = connection.execute(
            text(
                "SELECT o.id, o.proposer_id, o.offered_copy_id, o.requested_copy_id, "
                "o.status, o.created_at, o.expires_at, "
                "offered_book.title AS offered_title, requested_book.title AS requested_title, "
                "requested_copy.owner_id AS requested_owner_id, "
                "proposer.display_name AS proposer_name, requested_owner.display_name AS requested_owner_name "
                "FROM offers o "
                "JOIN profiles proposer ON proposer.id = o.proposer_id "
                "JOIN copies offered_copy ON offered_copy.id = o.offered_copy_id "
                "JOIN books offered_book ON offered_book.id = offered_copy.book_id "
                "JOIN copies requested_copy ON requested_copy.id = o.requested_copy_id "
                "JOIN books requested_book ON requested_book.id = requested_copy.book_id "
                "JOIN profiles requested_owner ON requested_owner.id = requested_copy.owner_id "
                "WHERE o.proposer_id = :user_id OR requested_copy.owner_id = :user_id "
                "ORDER BY o.created_at DESC, o.id DESC"
            ),
            {"user_id": user_id},
        ).mappings().all()

    offers = []
    for row in rows:
        offer = _offer_from_row(row)
        if offer.status == "pending" and is_expired(offer):
            update_offer_status(offer.id, "expired")
            offer = Offer(
                id=offer.id,
                proposer_id=offer.proposer_id,
                offered_copy_id=offer.offered_copy_id,
                requested_copy_id=offer.requested_copy_id,
                status="expired",
                created_at=offer.created_at,
                expires_at=offer.expires_at,
            )
        offers.append(
            {
                "offer": offer,
                "offered_title": row["offered_title"],
                "requested_title": row["requested_title"],
                "requested_owner_id": row["requested_owner_id"],
                "proposer_name": row["proposer_name"],
                "requested_owner_name": row["requested_owner_name"],
            }
        )
    return offers


def update_offer_status(offer_id: str, status: str) -> None:
    """Set an offer status after its page rule has allowed the action."""
    if status not in {"declined", "cancelled", "expired"}:
        raise ValueError(f"Invalid offer status: {status}")
    with transaction() as connection:
        result = connection.execute(
            text("UPDATE offers SET status = :status WHERE id = :offer_id AND status = 'pending'"),
            {"status": status, "offer_id": offer_id},
        )
        if result.rowcount != 1:
            raise ValueError(f"Pending offer not found: {offer_id}")


def cancel_offer(offer: Offer, user_id: str) -> None:
    """Cancel an offer after checking that its proposer is the current user."""
    decision = can_cancel(offer, user_id)
    if not decision.allowed:
        raise ValueError(decision.reason)
    update_offer_status(offer.id, "cancelled")


def decline_offer(offer: Offer, user_id: str) -> None:
    """Decline an incoming pending offer owned by the current user."""
    if offer.status != "pending":
        raise ValueError("Only pending offers can be declined.")
    if offer.requested_copy_id == offer.offered_copy_id:
        raise ValueError("An offer must use two different copies.")
    with transaction() as connection:
        owner = connection.execute(
            text("SELECT owner_id FROM copies WHERE id = :copy_id"),
            {"copy_id": offer.requested_copy_id},
        ).scalar_one_or_none()
        if owner != user_id:
            raise ValueError("Only the requested copy's owner can decline this offer.")
    update_offer_status(offer.id, "declined")


def accept_offer(
    offer: Offer,
    accepter_id: str,
    offered_copy: Copy,
    requested_copy: Copy,
    meet_place: str | None = None,
    meet_time: str | None = None,
) -> Loop:
    """Accept an offer, create its two-person loop, and cancel conflicts."""
    decision = can_accept(offer, accepter_id, offered_copy, requested_copy)
    if not decision.allowed:
        raise ValueError(decision.reason)

    with transaction() as connection:
        loop = _create_loop_in_connection(
            connection,
            trades=[
                {
                    "copy_id": offered_copy.id,
                    "giver_id": offer.proposer_id,
                    "receiver_id": accepter_id,
                },
                {
                    "copy_id": requested_copy.id,
                    "giver_id": accepter_id,
                    "receiver_id": offer.proposer_id,
                },
            ],
            source={"source": "offer", "offer_id": offer.id},
            meet_place=meet_place,
            meet_time=meet_time,
        )
        connection.execute(
            text("UPDATE offers SET status = 'accepted' WHERE id = :offer_id"),
            {"offer_id": offer.id},
        )
        connection.execute(
            text(
                "UPDATE offers SET status = 'cancelled' "
                "WHERE status = 'pending' AND id != :offer_id "
                "AND (offered_copy_id IN (:offered_copy_id, :requested_copy_id) "
                "OR requested_copy_id IN (:offered_copy_id, :requested_copy_id))"
            ),
            {
                "offer_id": offer.id,
                "offered_copy_id": offered_copy.id,
                "requested_copy_id": requested_copy.id,
            },
        )
    return loop


def _create_loop_in_connection(
    connection: Any,
    trades: Sequence[Any], source: Any, meet_place: str | None, meet_time: str | None
) -> Loop:
    """Create a loop using an already-open transaction."""
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
                "handoff_code": new_code(),
            },
        )

    return loop


def create_loop(
    trades: Sequence[Any], source: Any, meet_place: str | None, meet_time: str | None
) -> Loop:
    """Create a loop and reserve all its copies as one atomic database change."""
    with transaction() as connection:
        return _create_loop_in_connection(connection, trades, source, meet_place, meet_time)


def loop_participants(loop_id: str) -> list[dict[str, str]]:
    """Return the people taking part in a loop."""
    with transaction() as connection:
        rows = connection.execute(
            text(
                "SELECT DISTINCT p.id, p.display_name "
                "FROM profiles p JOIN trades t ON p.id IN (t.giver_id, t.receiver_id) "
                "WHERE t.loop_id = :loop_id ORDER BY p.display_name"
            ),
            {"loop_id": loop_id},
        ).mappings().all()
    return [{"id": row["id"], "display_name": row["display_name"]} for row in rows]


def report_no_show(loop_id: str, reporter_id: str, no_show_user_id: str):
    """Cancel a scheduled loop and return all its reserved copies to available."""
    with transaction() as connection:
        loop_row = connection.execute(
            text(
                "SELECT id, source, offer_id, round_id, status, meet_place, meet_time, "
                "no_show_user_id FROM loops WHERE id = :loop_id"
            ),
            {"loop_id": loop_id},
        ).mappings().first()
        if loop_row is None:
            raise ValueError("Swap not found.")

        trade_rows = connection.execute(
            text(
                "SELECT id, loop_id, copy_id, giver_id, receiver_id, handoff_code, "
                "code_attempts, status, completed_at FROM trades WHERE loop_id = :loop_id"
            ),
            {"loop_id": loop_id},
        ).mappings().all()
        current_loop = Loop(**dict(loop_row))
        current_trades = [_trade_from_row(row) for row in trade_rows]
        decision = no_show_outcome(current_loop, reporter_id, current_trades)
        if not decision.allowed:
            raise ValueError(decision.reason)

        participants = {
            participant_id
            for trade in current_trades
            for participant_id in (trade.giver_id, trade.receiver_id)
        }
        if no_show_user_id not in participants or no_show_user_id == reporter_id:
            raise ValueError("Choose another participant as the no-show user.")

        connection.execute(
            text(
                "UPDATE loops SET status = 'cancelled', no_show_user_id = :no_show_user_id "
                "WHERE id = :loop_id AND status = 'scheduled'"
            ),
            {"loop_id": loop_id, "no_show_user_id": no_show_user_id},
        )
        connection.execute(
            text("UPDATE trades SET status = 'cancelled' WHERE loop_id = :loop_id AND status = 'pending'"),
            {"loop_id": loop_id},
        )
        connection.execute(
            text(
                "UPDATE copies SET status = 'available' "
                "WHERE id IN (SELECT copy_id FROM trades WHERE loop_id = :loop_id) "
                "AND status = 'reserved'"
            ),
            {"loop_id": loop_id},
        )
        return decision


def _trade_from_row(row: Mapping[str, Any]) -> Trade:
    return Trade(
        id=row["id"],
        loop_id=row["loop_id"],
        copy_id=row["copy_id"],
        giver_id=row["giver_id"],
        receiver_id=row["receiver_id"],
        handoff_code=row["handoff_code"],
        code_attempts=row["code_attempts"],
        status=row["status"],
        completed_at=row["completed_at"],
    )


def trades_for_user(user_id: str) -> list[dict[str, Any]]:
    """Return a user's pending handoffs with meeting and book details.

    In a direct swap (from an offer) both people agreed to share their email
    when the offer was made and accepted, so each sees the other's email to
    arrange the meeting. In a round the moderator sets the meeting, and
    nobody's email is shared. Only the user's own swaps are returned, so a
    user never gets the email of someone they aren't swapping with.
    """
    with transaction() as connection:
        rows = connection.execute(
            text(
                "SELECT t.id, t.loop_id, t.copy_id, t.giver_id, t.receiver_id, "
                "t.handoff_code, t.code_attempts, t.status, t.completed_at, "
                "l.source, l.meet_place, l.meet_time, b.title, "
                "giver.display_name AS giver_name, receiver.display_name AS receiver_name, "
                "CASE WHEN l.source = 'offer' THEN giver.email END AS giver_email, "
                "CASE WHEN l.source = 'offer' THEN receiver.email END AS receiver_email "
                "FROM trades t "
                "JOIN loops l ON l.id = t.loop_id "
                "LEFT JOIN offers o ON o.id = l.offer_id "
                "JOIN profiles giver ON giver.id = t.giver_id "
                "JOIN profiles receiver ON receiver.id = t.receiver_id "
                "JOIN copies c ON c.id = t.copy_id "
                "JOIN books b ON b.id = c.book_id "
                "WHERE (t.giver_id = :user_id OR t.receiver_id = :user_id) "
                "AND t.status = 'pending' AND l.status = 'scheduled' "
                # Swaps with a meeting time first, soonest first; then direct swaps,
                # newest offer first. In each swap, the book you give comes first.
                "ORDER BY CASE WHEN l.meet_time IS NULL THEN 1 ELSE 0 END, l.meet_time, "
                "o.created_at DESC, t.loop_id, "
                "CASE WHEN t.giver_id = :user_id THEN 0 ELSE 1 END, t.id"
            ),
            {"user_id": user_id},
        ).mappings().all()

    return [
        {
            "trade": _trade_from_row(row),
            "source": row["source"],
            "meet_place": row["meet_place"],
            "meet_time": row["meet_time"],
            "title": row["title"],
            "giver_name": row["giver_name"],
            "receiver_name": row["receiver_name"],
            "giver_email": row["giver_email"],
            "receiver_email": row["receiver_email"],
        }
        for row in rows
    ]


def confirm_handoff(trade_id: str, giver_id: str, entered_code: str):
    """Confirm a handoff or record a wrong code attempt atomically."""
    with transaction() as connection:
        row = connection.execute(
            text(
                "SELECT id, loop_id, copy_id, giver_id, receiver_id, handoff_code, "
                "code_attempts, status, completed_at "
                "FROM trades WHERE id = :trade_id"
            ),
            {"trade_id": trade_id},
        ).mappings().first()
        if row is None:
            raise ValueError("Trade not found.")

        trade = _trade_from_row(row)
        if trade.giver_id != giver_id:
            raise ValueError("Only the giver can confirm this handoff.")

        decision = check_code(trade, entered_code)
        if not decision.allowed:
            if trade.status == "pending" and not is_locked(trade):
                connection.execute(
                    text(
                        "UPDATE trades SET code_attempts = code_attempts + 1 "
                        "WHERE id = :trade_id AND code_attempts < 3"
                    ),
                    {"trade_id": trade.id},
                )
            return decision

        completed_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        updated_trade = connection.execute(
            text(
                "UPDATE trades SET status = 'completed', completed_at = :completed_at "
                "WHERE id = :trade_id AND status = 'pending'"
            ),
            {"trade_id": trade.id, "completed_at": completed_at},
        )
        if updated_trade.rowcount != 1:
            raise ValueError("This trade is no longer pending.")

        updated_copy = connection.execute(
            text(
                "UPDATE copies SET owner_id = :receiver_id, status = 'available' "
                "WHERE id = :copy_id AND status = 'reserved'"
            ),
            {"receiver_id": trade.receiver_id, "copy_id": trade.copy_id},
        )
        if updated_copy.rowcount != 1:
            raise ValueError("The copy is not reserved for this trade.")

        remaining = connection.execute(
            text(
                "SELECT COUNT(*) FROM trades "
                "WHERE loop_id = :loop_id AND status = 'pending'"
            ),
            {"loop_id": trade.loop_id},
        ).scalar_one()
        if remaining == 0:
            connection.execute(
                text("UPDATE loops SET status = 'completed' WHERE id = :loop_id"),
                {"loop_id": trade.loop_id},
            )
        return decision
