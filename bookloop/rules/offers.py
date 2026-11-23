"""Rules for direct swap offers.

The rules stay independent from Streamlit and the database.  The page and the
storage layer provide the copies, the number of pending offers, and the user's
blocked status as inputs.
"""

from datetime import datetime, timedelta, timezone

from bookloop.models import Copy, Offer
from bookloop.rules.decision import Decision


MAX_PENDING_OFFERS = 5
OFFER_LIFETIME = timedelta(hours=72)


def _as_utc(value: str | datetime) -> datetime:
    """Parse an ISO timestamp and return it as a timezone-aware UTC value."""
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def is_expired(offer: Offer, now: datetime | None = None) -> bool:
    """Return whether an offer has reached its 72-hour deadline."""
    current_time = now or datetime.now(timezone.utc)
    return _as_utc(current_time) >= _as_utc(offer.expires_at)


def can_make_offer(
    proposer_id: str,
    offered_copy: Copy,
    requested_copy: Copy,
    pending_offer_count: int,
    blocked: bool = False,
) -> Decision:
    """Check whether a student can create a direct swap offer."""
    if blocked:
        return Decision.no("Blocked users cannot make offers.")
    if pending_offer_count >= MAX_PENDING_OFFERS:
        return Decision.no("You already have 5 pending offers.")
    if offered_copy.owner_id != proposer_id:
        return Decision.no("You can only offer one of your own copies.")
    if requested_copy.owner_id == proposer_id:
        return Decision.no("You cannot request your own copy.")
    if offered_copy.id == requested_copy.id:
        return Decision.no("You must choose two different copies.")
    if offered_copy.status != "available" or requested_copy.status != "available":
        return Decision.no("Both copies must be available.")
    return Decision.yes()


def can_accept(
    offer: Offer,
    accepter_id: str,
    offered_copy: Copy,
    requested_copy: Copy,
    now: datetime | None = None,
) -> Decision:
    """Check whether the owner of the requested copy can accept an offer."""
    if offer.status != "pending":
        return Decision.no("Only pending offers can be accepted.")
    if is_expired(offer, now):
        return Decision.no("This offer has expired.")
    if requested_copy.owner_id != accepter_id:
        return Decision.no("Only the requested copy's owner can accept this offer.")
    if offered_copy.owner_id != offer.proposer_id:
        return Decision.no("The offered copy no longer belongs to the proposer.")
    if offered_copy.id == requested_copy.id:
        return Decision.no("An offer must use two different copies.")
    if offered_copy.status != "available" or requested_copy.status != "available":
        return Decision.no("Both copies must be available.")
    return Decision.yes()


def can_cancel(offer: Offer, user_id: str) -> Decision:
    """Check whether the proposer can cancel a pending offer."""
    if offer.status != "pending":
        return Decision.no("Only pending offers can be cancelled.")
    if offer.proposer_id != user_id:
        return Decision.no("Only the person who made the offer can cancel it.")
    return Decision.yes()


MAX_PLACE_LENGTH = 100


def check_meeting(meet_place: str | None, meet_time: str | datetime, now: datetime | None = None) -> Decision:
    """When accepting an offer, the two people agree where and when to meet.

    The place can't be empty or too long, and the time must be in the future.
    """
    place = (meet_place or "").strip()
    if not place:
        return Decision.no("Add where you'll meet.")
    if len(place) > MAX_PLACE_LENGTH:
        return Decision.no(f"Keep the meeting place under {MAX_PLACE_LENGTH} characters.")
    if _as_utc(meet_time) <= _as_utc(now or datetime.now(timezone.utc)):
        return Decision.no("Choose a meeting time in the future.")
    return Decision.yes()
