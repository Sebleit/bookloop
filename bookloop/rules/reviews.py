"""Rules for reviews.

The person who receives a book rates whether it matched its listing:
1-5 stars, "was the condition as described?", the actual condition, and a
comment (required for 1-2 stars). Those reviews become the giver's score.

The rules:
- Only the receiver of a completed trade can review it, once, within 14 days.
- Cancelled, no-show and unfinished trades can't be reviewed.
- Reviews can't be edited after they're submitted.
- Blind reviews: a review stays hidden until everyone in that swap has
  reviewed, or 7 days pass, so nobody can take revenge after reading a bad
  review about themselves.
- The person reviewed can reply once.
- Moderators can hide abusive reviews, with the reason saved.

Like every rule, these functions never use Streamlit or the database.
"""

from datetime import datetime, timedelta, timezone

from bookloop.models import Profile, Review, Trade
from bookloop.rules.decision import Decision
from bookloop.rules.permissions import is_moderator


REVIEW_WINDOW_DAYS = 14
BLIND_DAYS = 7
MAX_TEXT_LENGTH = 500
CONDITIONS = {1: "poor", 2: "fair", 3: "good", 4: "like new"}


def _as_utc(value: str | datetime) -> datetime:
    """Turn an ISO timestamp like '2026-11-20T14:00:00Z' into a UTC datetime."""
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _now(now: str | datetime | None) -> datetime:
    """Use the given time (handy in tests) or the real current time."""
    return _as_utc(now) if now is not None else datetime.now(timezone.utc)


def _as_text(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


# --- Writing a review ------------------------------------------------------


def can_review(
    user: Profile,
    trade: Trade,
    already_reviewed: bool,
    now: str | datetime | None = None,
) -> Decision:
    """Check whether this user may review this trade at all."""
    if trade.status != "completed" or trade.completed_at is None:
        return Decision.no("Only completed swaps can be reviewed.")
    if trade.receiver_id != user.id:
        return Decision.no("Only the person who received the book can review it.")
    if already_reviewed:
        return Decision.no("You've already reviewed this swap. Reviews can't be changed.")
    deadline = _as_utc(trade.completed_at) + timedelta(days=REVIEW_WINDOW_DAYS)
    if _now(now) > deadline:
        return Decision.no(f"Reviews must be written within {REVIEW_WINDOW_DAYS} days of the swap.")
    return Decision.yes()


def needs_comment(stars: int) -> bool:
    """A comment is required for 1 or 2 stars, so the giver knows what went wrong."""
    return stars <= 2


def check_review_details(stars: int, actual_condition: int, comment: str | None) -> Decision:
    """Check what the reviewer filled in on the form."""
    if not 1 <= stars <= 5:
        return Decision.no("Stars must be between 1 and 5.")
    if actual_condition not in CONDITIONS:
        return Decision.no("Pick the condition the book was actually in.")
    text = (comment or "").strip()
    if needs_comment(stars) and not text:
        return Decision.no("Please add a comment explaining what went wrong (required for 1-2 stars).")
    if len(text) > MAX_TEXT_LENGTH:
        return Decision.no(f"Comments can be at most {MAX_TEXT_LENGTH} characters.")
    return Decision.yes()


def is_misdescribed(listed_condition: int, actual_condition: int) -> bool:
    """True if the book arrived 2 or more levels worse than its listing said.

    Example: listed "like new" (4), arrived "fair" (2) or "poor" (1).
    These swaps are flagged to a moderator automatically.
    """
    return listed_condition - actual_condition >= 2


# --- Blind reviews ---------------------------------------------------------


def review_visible_from(
    created_at: str | datetime,
    everyone_reviewed: bool,
    now: str | datetime | None = None,
) -> str:
    """When a new review becomes visible.

    Straight away if everyone in the swap has now reviewed, otherwise
    7 days after it was written.
    """
    if everyone_reviewed:
        return _as_text(_now(now))
    return _as_text(_as_utc(created_at) + timedelta(days=BLIND_DAYS))


def is_visible(visible_from: str | None, now: str | datetime | None = None) -> bool:
    """Whether a review can be shown and counted yet.

    None means "visible straight away" (for example, demo reviews).
    """
    if visible_from is None:
        return True
    return _now(now) >= _as_utc(visible_from)


# --- Replying and hiding ---------------------------------------------------


def can_reply(
    user: Profile,
    review: Review,
    reply: str,
    now: str | datetime | None = None,
) -> Decision:
    """Check whether the person reviewed can post this reply."""
    if review.reviewee_id != user.id:
        return Decision.no("Only the person who was reviewed can reply.")
    if review.reply is not None:
        return Decision.no("You've already replied to this review.")
    if not is_visible(review.visible_from, now):
        return Decision.no("You can reply once the review is visible.")
    text = (reply or "").strip()
    if not text:
        return Decision.no("Write a reply first.")
    if len(text) > MAX_TEXT_LENGTH:
        return Decision.no(f"Replies can be at most {MAX_TEXT_LENGTH} characters.")
    return Decision.yes()


def can_hide_review(user: Profile, review: Review, reason: str) -> Decision:
    """Check whether a moderator can hide an abusive review."""
    if not is_moderator(user):
        return Decision.no("Only moderators can hide reviews.")
    if review.hidden_by_moderator:
        return Decision.no("This review is already hidden.")
    if not (reason or "").strip():
        return Decision.no("Give a reason for hiding the review.")
    return Decision.yes()


def can_resolve_flag(user: Profile) -> Decision:
    """Check whether this user can mark a flagged swap as dealt with."""
    if not is_moderator(user):
        return Decision.no("Only moderators can resolve flags.")
    return Decision.yes()
