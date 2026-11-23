"""Saving and loading reviews, each user's Swapper Score, and moderator actions.

This file never decides whether something is allowed: the pages ask the rules
in bookloop/rules/reviews.py and bookloop/rules/reputation.py first.

Flags: when a review says a book arrived 2+ levels worse than listed, the
swap is flagged by writing a "flagged" entry in audit_log. A moderator
resolves it, which writes a "resolved flag" entry. So the log keeps the full
history, and a flag is open while it has no "resolved flag" after it.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import NamedTuple
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.engine import Connection

from bookloop.models import AuditLog, Loop, Profile, Review, Trade
from bookloop.rules import reputation
from bookloop.rules.handoffs import can_report_missing_handoff
from bookloop.rules.reviews import arrived_as_described, is_misdescribed, is_visible, review_visible_from
from bookloop.services.notify import notify
from bookloop.storage.db import transaction


FLAGGED = "flagged as misdescribed"
RESOLVED = "resolved flag"
MISSING_HANDOFF = "reported a missing handoff"
REVIEW_COLUMNS = (
    "id, trade_id, reviewer_id, reviewee_id, stars, as_described, actual_condition, "
    "comment, reply, visible_from, hidden_by_moderator, hidden_reason, created_at"
)
TRADE_COLUMNS = (
    "id, loop_id, copy_id, giver_id, receiver_id, handoff_code, code_attempts, status, completed_at"
)


class SwapperScore(NamedTuple):
    score: float
    accuracy: float
    badge: str | None


@dataclass(frozen=True)
class TradeToReview:
    """A book the user received and hasn't reviewed yet."""

    trade: Trade
    title: str
    giver_name: str
    listed_condition: int


@dataclass(frozen=True)
class SavedReview:
    review: Review
    flagged: bool
    now_under_review: bool


@dataclass(frozen=True)
class ReviewView:
    """A review with the names and title the pages show."""

    review: Review
    reviewer_name: str
    reviewee_name: str
    title: str


@dataclass(frozen=True)
class HistoryItem:
    """One book the user gave or received."""

    title: str
    gave: bool
    other_name: str
    status: str
    date: str | None


@dataclass(frozen=True)
class ProblemReport:
    """Someone says a person in their swap didn't hand over their book."""

    trade_id: str
    loop_id: str
    title: str
    giver_id: str
    giver_name: str
    receiver_name: str
    reporter_name: str
    reported_at: str


@dataclass(frozen=True)
class FlaggedSwap:
    trade_id: str
    title: str
    giver_id: str
    giver_name: str
    receiver_name: str
    actual_condition: int
    stars: int
    comment: str | None
    flagged_at: str


@dataclass(frozen=True)
class AuditView:
    entry: AuditLog
    actor_name: str


def _now_text() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _review(row) -> Review:
    values = dict(row)
    values["as_described"] = bool(values["as_described"])
    values["hidden_by_moderator"] = bool(values["hidden_by_moderator"])
    return Review(**values)


def _log(connection: Connection, actor_id: str, action: str, table: str, target_id: str) -> None:
    """Write one audit_log entry (its target must be registered in entity_ids first)."""
    connection.execute(
        text(
            "INSERT INTO entity_ids (table_name, entity_key) VALUES (:table, :key) "
            "ON CONFLICT DO NOTHING"
        ),
        {"table": table, "key": target_id},
    )
    connection.execute(
        text(
            "INSERT INTO audit_log (id, actor_id, action, target_table, target_id, created_at) "
            "VALUES (:id, :actor, :action, :table, :target, :at)"
        ),
        {
            "id": str(uuid4()),
            "actor": actor_id,
            "action": action,
            "table": table,
            "target": target_id,
            "at": _now_text(),
        },
    )


# --- The score -------------------------------------------------------------


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


# --- Reading ---------------------------------------------------------------


def get_profile(user_id: str) -> Profile | None:
    with transaction() as connection:
        row = connection.execute(
            text("SELECT id, display_name, role, status, created_at FROM profiles WHERE id = :id"),
            {"id": user_id},
        ).mappings().first()
    return Profile(**row) if row else None


def list_profiles() -> list[Profile]:
    """Everyone, in alphabetical order (for the "view a profile" list)."""
    with transaction() as connection:
        rows = connection.execute(
            text("SELECT id, display_name, role, status, created_at FROM profiles ORDER BY display_name, id")
        ).mappings().all()
    return [Profile(**row) for row in rows]


def get_trade(trade_id: str) -> Trade | None:
    with transaction() as connection:
        row = connection.execute(
            text(f"SELECT {TRADE_COLUMNS} FROM trades WHERE id = :id"), {"id": trade_id}
        ).mappings().first()
    return Trade(**row) if row else None


def get_review(review_id: str) -> Review | None:
    with transaction() as connection:
        row = connection.execute(
            text(f"SELECT {REVIEW_COLUMNS} FROM reviews WHERE id = :id"), {"id": review_id}
        ).mappings().first()
    return _review(row) if row else None


def has_review(trade_id: str) -> bool:
    with transaction() as connection:
        return connection.execute(
            text("SELECT COUNT(*) FROM reviews WHERE trade_id = :id"), {"id": trade_id}
        ).scalar_one() > 0


def trades_to_review(user_id: str) -> list[TradeToReview]:
    """Completed trades where the user received a book and hasn't reviewed it.

    The page still asks can_review() for each one (for example, the 14 days).
    """
    with transaction() as connection:
        rows = connection.execute(
            text(
                "SELECT t.id, t.loop_id, t.copy_id, t.giver_id, t.receiver_id, t.handoff_code, "
                't.code_attempts, t.status, t.completed_at, b.title, c."condition", '
                "p.display_name FROM trades t "
                "JOIN copies c ON c.id = t.copy_id "
                "JOIN books b ON b.id = c.book_id "
                "JOIN profiles p ON p.id = t.giver_id "
                "LEFT JOIN reviews r ON r.trade_id = t.id "
                "WHERE t.receiver_id = :user_id AND t.status = 'completed' AND r.id IS NULL "
                "ORDER BY t.completed_at DESC, t.id"
            ),
            {"user_id": user_id},
        ).mappings().all()
    trade_keys = TRADE_COLUMNS.split(", ")
    return [
        TradeToReview(
            trade=Trade(**{key: row[key] for key in trade_keys}),
            title=row["title"],
            giver_name=row["display_name"],
            listed_condition=row["condition"],
        )
        for row in rows
    ]


def _review_views(where: str, params: dict) -> list[ReviewView]:
    with transaction() as connection:
        rows = connection.execute(
            text(
                "SELECT r.id, r.trade_id, r.reviewer_id, r.reviewee_id, r.stars, r.as_described, "
                "r.actual_condition, r.comment, r.reply, r.visible_from, r.hidden_by_moderator, "
                "r.hidden_reason, r.created_at, b.title, rv.display_name AS reviewer_name, "
                "re.display_name AS reviewee_name FROM reviews r "
                "JOIN trades t ON t.id = r.trade_id "
                "JOIN copies c ON c.id = t.copy_id "
                "JOIN books b ON b.id = c.book_id "
                "JOIN profiles rv ON rv.id = r.reviewer_id "
                "JOIN profiles re ON re.id = r.reviewee_id "
                f"WHERE {where} ORDER BY r.created_at DESC, r.id DESC"
            ),
            params,
        ).mappings().all()
    return [
        ReviewView(
            review=_review({key: row[key] for key in REVIEW_COLUMNS.split(", ")}),
            reviewer_name=row["reviewer_name"],
            reviewee_name=row["reviewee_name"],
            title=row["title"],
        )
        for row in rows
    ]


def reviews_about(user_id: str) -> list[ReviewView]:
    """Reviews of this user that anyone can see: not hidden, and no longer blind."""
    views = _review_views("r.reviewee_id = :user_id AND r.hidden_by_moderator = 0", {"user_id": user_id})
    return [view for view in views if is_visible(view.review.visible_from)]


def recent_reviews(limit: int = 50) -> list[ReviewView]:
    """The latest reviews that aren't hidden, blind ones included (for moderators)."""
    return _review_views("r.hidden_by_moderator = 0", {})[:limit]


def swap_history(user_id: str) -> list[HistoryItem]:
    """Every book the user gave or received, newest first."""
    with transaction() as connection:
        rows = connection.execute(
            text(
                "SELECT b.title, t.giver_id, g.display_name AS giver_name, "
                "r.display_name AS receiver_name, t.status, "
                "COALESCE(t.completed_at, l.meet_time) AS happened_at FROM trades t "
                "JOIN loops l ON l.id = t.loop_id "
                "JOIN copies c ON c.id = t.copy_id "
                "JOIN books b ON b.id = c.book_id "
                "JOIN profiles g ON g.id = t.giver_id "
                "JOIN profiles r ON r.id = t.receiver_id "
                "WHERE t.giver_id = :user_id OR t.receiver_id = :user_id "
                "ORDER BY happened_at DESC, t.id"
            ),
            {"user_id": user_id},
        ).mappings().all()
    return [
        HistoryItem(
            title=row["title"],
            gave=row["giver_id"] == user_id,
            other_name=row["receiver_name"] if row["giver_id"] == user_id else row["giver_name"],
            status=row["status"],
            date=row["happened_at"],
        )
        for row in rows
    ]


# --- Writing a review ------------------------------------------------------


def save_review(
    trade: Trade,
    stars: int,
    actual_condition: int,
    comment: str | None,
) -> SavedReview:
    """Save the receiver's review, then flag and set under_review if needed.

    "As described" isn't asked: it's worked out from the condition the book
    arrived in, compared with its listing.

    In one transaction:
    1. Work out when the review becomes visible: now if everyone in the swap
       has now reviewed (and then the others become visible too), otherwise
       when the 14 days for reviewing the swap are over.
    2. Flag the swap if the book arrived 2+ levels worse than listed.
    3. Set the giver to under_review if the reputation rules say so. This
       check uses blind reviews too: it protects other students straight away,
       while the public score waits.
    """
    now = _now_text()
    review_id = str(uuid4())
    text_comment = (comment or "").strip() or None

    with transaction() as connection:
        listed_condition = connection.execute(
            text('SELECT "condition" FROM copies WHERE id = :id'), {"id": trade.copy_id}
        ).scalar_one()
        trades_in_loop = connection.execute(
            text("SELECT COUNT(*) FROM trades WHERE loop_id = :loop"), {"loop": trade.loop_id}
        ).scalar_one()
        reviewed_in_loop = connection.execute(
            text(
                "SELECT COUNT(*) FROM reviews r JOIN trades t ON t.id = r.trade_id "
                "WHERE t.loop_id = :loop"
            ),
            {"loop": trade.loop_id},
        ).scalar_one()
        everyone_reviewed = reviewed_in_loop + 1 >= trades_in_loop
        visible = review_visible_from(trade.completed_at, everyone_reviewed, now)
        as_described = arrived_as_described(listed_condition, actual_condition)

        review = Review(
            id=review_id,
            trade_id=trade.id,
            reviewer_id=trade.receiver_id,
            reviewee_id=trade.giver_id,
            stars=stars,
            as_described=as_described,
            actual_condition=actual_condition,
            comment=text_comment,
            reply=None,
            visible_from=visible,
            hidden_by_moderator=False,
            hidden_reason=None,
            created_at=now,
        )
        connection.execute(
            text(
                f"INSERT INTO reviews ({REVIEW_COLUMNS}) VALUES (:id, :trade_id, :reviewer_id, "
                ":reviewee_id, :stars, :as_described, :actual_condition, :comment, :reply, "
                ":visible_from, :hidden_by_moderator, :hidden_reason, :created_at)"
            ),
            {**review.__dict__, "as_described": int(as_described), "hidden_by_moderator": 0},
        )
        if everyone_reviewed:
            connection.execute(
                text(
                    "UPDATE reviews SET visible_from = :now WHERE trade_id IN "
                    "(SELECT id FROM trades WHERE loop_id = :loop)"
                ),
                {"now": now, "loop": trade.loop_id},
            )

        flagged = is_misdescribed(listed_condition, actual_condition)
        if flagged:
            _log(connection, trade.receiver_id, FLAGGED, "trades", trade.id)

        now_under_review = _update_status(connection, trade.giver_id)

    _send_review_notifications(review, flagged, now_under_review)
    return SavedReview(review=review, flagged=flagged, now_under_review=now_under_review)


def _update_status(connection: Connection, user_id: str) -> bool:
    """Set an active user to under_review if the rules say so. True if it changed."""
    rows = connection.execute(
        text(
            "SELECT stars, as_described FROM reviews "
            "WHERE reviewee_id = :id AND hidden_by_moderator = 0 ORDER BY created_at DESC, id DESC"
        ),
        {"id": user_id},
    ).mappings().all()
    stars = [row["stars"] for row in rows]
    answers = [bool(row["as_described"]) for row in rows]
    if not reputation.should_be_under_review(
        len(rows), reputation.score(stars), reputation.misdescribed_recently(answers)
    ):
        return False
    result = connection.execute(
        text("UPDATE profiles SET status = 'under_review' WHERE id = :id AND status = 'active'"),
        {"id": user_id},
    )
    return result.rowcount == 1


def _send_review_notifications(review: Review, flagged: bool, now_under_review: bool) -> None:
    if flagged:
        for moderator in _moderators():
            notify(moderator, "A swap was flagged: a book arrived 2+ levels worse than listed.", None)
    if now_under_review:
        notify(
            review.reviewee_id,
            "Your account is under review after recent reviews. A moderator will look at it soon; "
            "until then you can't make offers or join swap rounds.",
            None,
        )


def _moderators() -> list[str]:
    with transaction() as connection:
        return list(
            connection.execute(text("SELECT id FROM profiles WHERE role = 'moderator'")).scalars()
        )


def save_reply(review_id: str, reply: str) -> None:
    """Save the one reply to a review."""
    with transaction() as connection:
        result = connection.execute(
            text("UPDATE reviews SET reply = :reply WHERE id = :id AND reply IS NULL"),
            {"reply": reply.strip(), "id": review_id},
        )
        if result.rowcount != 1:
            raise ValueError("This review already has a reply.")


# --- Moderator actions (each one is saved in audit_log) --------------------


def flagged_swaps() -> list[FlaggedSwap]:
    """Swaps flagged as misdescribed that no moderator has resolved yet."""
    with transaction() as connection:
        rows = connection.execute(
            text(
                "SELECT f.target_id AS trade_id, f.created_at AS flagged_at, b.title, t.giver_id, "
                "g.display_name AS giver_name, rc.display_name AS receiver_name, "
                "r.actual_condition, r.stars, r.comment FROM audit_log f "
                "JOIN trades t ON t.id = f.target_id "
                "JOIN copies c ON c.id = t.copy_id "
                "JOIN books b ON b.id = c.book_id "
                "JOIN profiles g ON g.id = t.giver_id "
                "JOIN profiles rc ON rc.id = t.receiver_id "
                "JOIN reviews r ON r.trade_id = t.id "
                "WHERE f.action = :flagged AND f.target_table = 'trades' AND NOT EXISTS ("
                "  SELECT 1 FROM audit_log done WHERE done.action = :resolved "
                "  AND done.target_table = 'trades' AND done.target_id = f.target_id"
                "  AND done.created_at >= f.created_at"
                ") ORDER BY f.created_at DESC"
            ),
            {"flagged": FLAGGED, "resolved": RESOLVED},
        ).mappings().all()
    return [FlaggedSwap(**row) for row in rows]


def report_missing_handoff(loop_id: str, reporter_id: str, accused_id: str) -> None:
    """Tell the moderators that someone in a swap didn't hand over their book.

    Nothing is cancelled automatically: a book has already changed hands, so a
    moderator checks what happened. The report stays open until it's resolved.
    """
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
        trades = [
            Trade(**row)
            for row in connection.execute(
                text(
                    "SELECT id, loop_id, copy_id, giver_id, receiver_id, handoff_code, "
                    "code_attempts, status, completed_at FROM trades WHERE loop_id = :loop_id"
                ),
                {"loop_id": loop_id},
            ).mappings()
        ]
        decision = can_report_missing_handoff(Loop(**dict(loop_row)), reporter_id, accused_id, trades)
        if not decision.allowed:
            raise ValueError(decision.reason)
        trade = next(t for t in trades if t.giver_id == accused_id and t.status == "pending")
        if trade.id in {report.trade_id for report in _open_problem_reports(connection)}:
            raise ValueError("This has already been reported. A moderator will check it.")
        _log(connection, reporter_id, MISSING_HANDOFF, "trades", trade.id)
        names = dict(
            connection.execute(
                text("SELECT id, display_name FROM profiles WHERE id IN (:reporter, :accused)"),
                {"reporter": reporter_id, "accused": accused_id},
            ).all()
        )
        title = connection.execute(
            text("SELECT b.title FROM copies c JOIN books b ON b.id = c.book_id WHERE c.id = :copy"),
            {"copy": trade.copy_id},
        ).scalar_one()

    for moderator in _moderators():
        notify(
            moderator,
            f"{names[reporter_id]} says {names[accused_id]} didn't hand over “{title}”. "
            "Check it on the Moderator page.",
            None,
        )
    notify(
        accused_id,
        f"{names[reporter_id]} reported that you didn't hand over “{title}”. "
        "A moderator will check what happened.",
        None,
    )


def _open_problem_reports(connection: Connection) -> list[ProblemReport]:
    rows = connection.execute(
        text(
            "SELECT f.target_id AS trade_id, t.loop_id, f.created_at AS reported_at, b.title, "
            "t.giver_id, g.display_name AS giver_name, rc.display_name AS receiver_name, "
            "rp.display_name AS reporter_name FROM audit_log f "
            "JOIN trades t ON t.id = f.target_id "
            "JOIN copies c ON c.id = t.copy_id "
            "JOIN books b ON b.id = c.book_id "
            "JOIN profiles g ON g.id = t.giver_id "
            "JOIN profiles rc ON rc.id = t.receiver_id "
            "JOIN profiles rp ON rp.id = f.actor_id "
            "WHERE f.action = :reported AND f.target_table = 'trades' AND NOT EXISTS ("
            "  SELECT 1 FROM audit_log done WHERE done.action = :resolved "
            "  AND done.target_table = 'trades' AND done.target_id = f.target_id"
            "  AND done.created_at >= f.created_at"
            ") ORDER BY f.created_at DESC"
        ),
        {"reported": MISSING_HANDOFF, "resolved": RESOLVED},
    ).mappings().all()
    return [ProblemReport(**row) for row in rows]


def problem_reports() -> list[ProblemReport]:
    """Reports of books not handed over that no moderator has resolved yet."""
    with transaction() as connection:
        return _open_problem_reports(connection)


def resolve_flag(moderator_id: str, trade_id: str) -> None:
    with transaction() as connection:
        _log(connection, moderator_id, RESOLVED, "trades", trade_id)


def hide_review(moderator_id: str, review_id: str, reason: str) -> None:
    """Hide an abusive review and save the reason. It stops counting in the score."""
    with transaction() as connection:
        result = connection.execute(
            text(
                "UPDATE reviews SET hidden_by_moderator = 1, hidden_reason = :reason "
                "WHERE id = :id AND hidden_by_moderator = 0"
            ),
            {"reason": reason.strip(), "id": review_id},
        )
        if result.rowcount != 1:
            raise ValueError("This review is already hidden.")
        _log(connection, moderator_id, "hid review", "reviews", review_id)


def users_needing_attention() -> list[Profile]:
    """Users who are under review or suspended."""
    with transaction() as connection:
        rows = connection.execute(
            text(
                "SELECT id, display_name, role, status, created_at FROM profiles "
                "WHERE status IN ('under_review', 'suspended') ORDER BY status, display_name"
            )
        ).mappings().all()
    return [Profile(**row) for row in rows]


def set_user_status(moderator_id: str, user_id: str, status: str) -> None:
    """Clear a user (back to active) or suspend them, and tell them."""
    action = {"active": "cleared user", "suspended": "suspended user"}[status]
    with transaction() as connection:
        connection.execute(
            text("UPDATE profiles SET status = :status WHERE id = :id"),
            {"status": status, "id": user_id},
        )
        _log(connection, moderator_id, action, "profiles", user_id)
    if status == "active":
        notify(user_id, "A moderator has cleared your account. You can make offers and join rounds again.", None)
    else:
        notify(user_id, "A moderator has suspended your account. You can't make offers or join rounds.", None)


def audit_entries(limit: int = 100) -> list[AuditView]:
    """The log of moderator actions and flags, newest first."""
    with transaction() as connection:
        rows = connection.execute(
            text(
                "SELECT a.id, a.actor_id, a.action, a.target_table, a.target_id, a.created_at, "
                "p.display_name FROM audit_log a JOIN profiles p ON p.id = a.actor_id "
                "ORDER BY a.created_at DESC, a.id DESC LIMIT :limit"
            ),
            {"limit": limit},
        ).mappings().all()
    return [
        AuditView(
            entry=AuditLog(**{key: row[key] for key in row if key != "display_name"}),
            actor_name=row["display_name"],
        )
        for row in rows
    ]
