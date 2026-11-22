"""Saving and loading reviews, and each user's Swapper Score."""

from typing import NamedTuple

from sqlalchemy import text

from bookloop.rules import reputation
from bookloop.rules.reviews import is_visible
from bookloop.storage.db import transaction


class SwapperScore(NamedTuple):
    score: float
    accuracy: float
    badge: str | None


def swapper_score(user_id: str) -> SwapperScore:
    """Return the user's score, description accuracy and badge.

    Only reviews that count are used: not hidden by a moderator, and no longer
    blind (everyone in the swap has reviewed, or 7 days have passed). If blind
    reviews counted, someone could guess a bad review from their score dropping.
    """
    with transaction() as connection:
        rows = connection.execute(
            text(
                "SELECT stars, as_described, visible_from FROM reviews "
                "WHERE reviewee_id = :user_id AND hidden_by_moderator = 0 "
                "ORDER BY created_at DESC, id DESC"
            ),
            {"user_id": user_id},
        ).mappings().all()

    counted = [row for row in rows if is_visible(row["visible_from"])]
    stars = [row["stars"] for row in counted]
    answers = [bool(row["as_described"]) for row in counted]  # newest first

    raw_score = reputation.score(stars)
    raw_accuracy = reputation.accuracy(answers)
    badge = reputation.badge(
        len(counted), raw_score, raw_accuracy, reputation.misdescribed_recently(answers)
    )
    return SwapperScore(score=round(raw_score, 2), accuracy=round(raw_accuracy, 2), badge=badge)


def is_blocked(user_id: str) -> bool:
    """Return whether the user is under review or suspended."""
    with transaction() as connection:
        status = connection.execute(
            text("SELECT status FROM profiles WHERE id = :user_id"),
            {"user_id": user_id},
        ).scalar_one_or_none()
    return status in {"under_review", "suspended"}
