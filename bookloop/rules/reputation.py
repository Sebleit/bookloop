"""Rules for reputation: the Swapper Score, accuracy and badges.

The score formula. A plain average would be unfair: one 5-star review would
make a brand-new user "perfect". So everyone starts as if they already had
3 reviews of 4 stars, and real reviews gradually take over:

    score = (3 x 4.0 + sum of all stars) / (3 + number of reviews)

    One 5-star (new user):  (12 + 5)  / (3 + 1) = 4.25
    5, 5, 4, 2:             (12 + 16) / (3 + 4) = 4.00
    1, 2, 2:                (12 + 5)  / (3 + 3) = 2.83

Accuracy is the percentage of reviews that said "as described".

Badges:
- New: fewer than 3 reviews.
- Trusted: 5+ reviews, a score of 4.5 or more, and 90%+ accuracy.
- Under review: a score below 3.0 after 3+ reviews, or 2 misdescribed books
  in the last 5 swaps. These users can't make offers or join rounds until a
  moderator clears them.

The score is calculated from the reviews every time it's shown, never
stored, so it can never be out of date. The score functions only do the
maths: storage gives them the reviews that count.

At the end, can_change_status() decides when a moderator can clear or
suspend a user.
"""

from collections.abc import Sequence

from bookloop.models import Profile
from bookloop.rules.decision import Decision
from bookloop.rules.permissions import is_moderator


STARTING_REVIEWS = 3
STARTING_STARS = 4.0
NEW_USER_REVIEWS = 3
TRUSTED_REVIEWS = 5
TRUSTED_SCORE = 4.5
TRUSTED_ACCURACY = 90.0
UNDER_REVIEW_SCORE = 3.0
UNDER_REVIEW_MIN_REVIEWS = 3
RECENT_SWAPS = 5
MISDESCRIBED_LIMIT = 2


def score(stars: Sequence[int]) -> float:
    """The Swapper Score for these star ratings (not rounded)."""
    return (STARTING_REVIEWS * STARTING_STARS + sum(stars)) / (STARTING_REVIEWS + len(stars))


def accuracy(as_described: Sequence[bool]) -> float:
    """The percentage of reviews that said "as described" (0 with no reviews)."""
    if not as_described:
        return 0.0
    return 100 * sum(bool(answer) for answer in as_described) / len(as_described)


def misdescribed_recently(as_described_newest_first: Sequence[bool]) -> int:
    """How many of the last 5 reviews said "not as described"."""
    recent = as_described_newest_first[:RECENT_SWAPS]
    return sum(not bool(answer) for answer in recent)


def should_be_under_review(review_count: int, user_score: float, misdescribed_in_last_five: int) -> bool:
    """A low score after enough reviews, or too many misdescribed books lately."""
    low_score = review_count >= UNDER_REVIEW_MIN_REVIEWS and user_score < UNDER_REVIEW_SCORE
    return low_score or misdescribed_in_last_five >= MISDESCRIBED_LIMIT


def badge(
    review_count: int,
    user_score: float,
    user_accuracy: float,
    misdescribed_in_last_five: int,
) -> str | None:
    """The badge shown next to the score. "Under review" wins over the others."""
    if should_be_under_review(review_count, user_score, misdescribed_in_last_five):
        return "Under review"
    if (
        review_count >= TRUSTED_REVIEWS
        and user_score >= TRUSTED_SCORE
        and user_accuracy >= TRUSTED_ACCURACY
    ):
        return "Trusted"
    if review_count < NEW_USER_REVIEWS:
        return "New"
    return None


# --- Account status --------------------------------------------------------


STATUS_NAMES = {"active": "cleared", "suspended": "suspended"}


def can_change_status(moderator: Profile, user: Profile, new_status: str) -> Decision:
    """Check whether a moderator can clear a user (back to active) or suspend them."""
    if not is_moderator(moderator):
        return Decision.no("Only moderators can clear or suspend users.")
    if new_status not in STATUS_NAMES:
        return Decision.no("A user can only be cleared or suspended.")
    if user.id == moderator.id:
        return Decision.no("You can't change your own status.")
    if is_moderator(user):
        return Decision.no("Moderators can't clear or suspend other moderators.")
    if user.status == new_status:
        return Decision.no(f"{user.display_name} is already {STATUS_NAMES[new_status]}.")
    return Decision.yes()
