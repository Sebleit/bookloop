# Person 4 owns this file: review database operations.
from typing import NamedTuple

from sqlalchemy import text

from bookloop.storage.db import transaction


class SwapperScore(NamedTuple):
    score: float
    accuracy: float
    badge: str | None


def swapper_score(user_id: str) -> SwapperScore:
    """Return the user's Bayesian score, description accuracy, and badge."""
    with transaction() as connection:
        rows = connection.execute(
            text(
                "SELECT stars, as_described FROM reviews "
                "WHERE reviewee_id = :user_id AND hidden_by_moderator = 0 "
                "ORDER BY created_at DESC, id DESC"
            ),
            {"user_id": user_id},
        ).mappings().all()

    review_count = len(rows)
    if review_count == 0:
        return SwapperScore(score=4.0, accuracy=0.0, badge="New")

    raw_score = (3 * 4.0 + sum(row["stars"] for row in rows)) / (3 + review_count)
    score = round(raw_score, 2)
    accurate_count = sum(bool(row["as_described"]) for row in rows)
    accuracy = round(100 * accurate_count / review_count, 2)
    misdescribed_in_last_five = sum(not bool(row["as_described"]) for row in rows[:5])

    if (review_count >= 3 and raw_score < 3.0) or misdescribed_in_last_five >= 2:
        badge = "Under review"
    elif review_count >= 5 and raw_score >= 4.5 and accuracy >= 90:
        badge = "Trusted"
    elif review_count < 3:
        badge = "New"
    else:
        badge = None

    return SwapperScore(score=score, accuracy=accuracy, badge=badge)


def is_blocked(user_id: str) -> bool:
    """Return whether the user is under review or suspended."""
    with transaction() as connection:
        status = connection.execute(
            text("SELECT status FROM profiles WHERE id = :user_id"),
            {"user_id": user_id},
        ).scalar_one_or_none()
    return status in {"under_review", "suspended"}
