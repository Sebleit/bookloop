"""Demo data: past swaps and reviews that give two users clear reputations.

- Carla is Trusted: five 5-star reviews, all "as described".
  Score (12 + 25) / (3 + 5) = 4.62, accuracy 100%.
- Dina is Under review: reviews of 1, 2 and 2 stars, two of them "not as
  described". Score (12 + 5) / (3 + 3) = 2.83, accuracy 33%. Both
  misdescribed swaps are flagged for the moderator, and Dina has replied to
  one review.

These swaps happened in October, so they're past the 14-day review window
and don't appear as "waiting for your review". Each one is a direct swap
(a loop of 2), and only one side reviewed. The swapped books are "unlisted"
copies owned by the person who received them, so they don't show up in Browse.

One more swap is ready for the review step of the demo: yesterday Eli gave
Carla a book listed as "like new", and Carla gave Eli one back. Eli has
already reviewed Carla (still blind), Carla hasn't reviewed Eli yet. When
Carla leaves 2 stars, "not as described", "poor" in the demo, the swap is
flagged, both reviews become visible at once, and Eli's score drops from
4.00 to 3.50. It's dated relative to when the data is loaded, so the 14-day
review window is always open for the demo.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.engine import Connection

from bookloop.rules.reviews import review_visible_from
from bookloop.storage.reviews_repo import FLAGGED


# (number, reviewee, reviewer, book, listed condition, stars, as described,
#  actual condition, comment, reply)
PAST_REVIEWS = (
    (1, "carla", "ana", "book-01", 4, 5, True, 4, "Exactly as described, thanks!", None),
    (2, "carla", "ben", "book-03", 3, 5, True, 3, None, None),
    (3, "carla", "dina", "book-05", 3, 5, True, 3, "Great condition.", None),
    (4, "carla", "eli", "book-07", 4, 5, True, 4, None, None),
    (5, "carla", "farah", "book-09", 2, 5, True, 2, "Quick and friendly swap.", None),
    (6, "dina", "eli", "book-02", 4, 1, False, 1,
     "Listed as like new, but pages were missing and there were coffee stains.",
     "The pages were already loose when I got it. Sorry, I should have said so."),
    (7, "dina", "farah", "book-04", 3, 2, False, 1,
     "Heavy highlighting on almost every page, not mentioned in the listing.", None),
    (8, "dina", "ana", "book-06", 3, 2, True, 3, "Book was fine, but she was 40 minutes late.", None),
)


def _day(number: int) -> str:
    return f"2026-10-{number + 1:02}"


def seed(connection: Connection) -> None:
    """Insert the past swaps, their reviews and flags, and Dina's status."""
    for number, reviewee, reviewer, book, listed, stars, described, actual, comment, reply in PAST_REVIEWS:
        giver, receiver = f"user-{reviewee}", f"user-{reviewer}"
        loop_id, done_at = f"loop-hist-{number:02}", f"{_day(number)}T15:00:00Z"
        connection.execute(
            text(
                "INSERT INTO loops "
                "(id, source, offer_id, round_id, status, meet_place, meet_time, no_show_user_id) "
                "VALUES (:id, 'offer', NULL, NULL, 'completed', 'Nova SBE library', :at, NULL)"
            ),
            {"id": loop_id, "at": f"{_day(number)}T14:30:00Z"},
        )
        # The reviewed book went from the reviewee to the reviewer, and another
        # book went back the other way. After a swap, each receiver owns the book.
        for side, (from_user, to_user, condition) in {
            "a": (giver, receiver, listed),
            "b": (receiver, giver, 3),
        }.items():
            copy_id, trade_id = f"copy-hist-{number:02}{side}", f"trade-hist-{number:02}{side}"
            connection.execute(
                text(
                    'INSERT INTO copies (id, book_id, owner_id, "condition", highlighting, notes, '
                    "status, created_at) VALUES (:id, :book, :owner, :condition, 'none', NULL, "
                    "'unlisted', '2026-09-15T00:00:00Z')"
                ),
                {"id": copy_id, "book": book if side == "a" else "book-10", "owner": to_user,
                 "condition": condition},
            )
            connection.execute(
                text(
                    "INSERT INTO trades (id, loop_id, copy_id, giver_id, receiver_id, handoff_code, "
                    "code_attempts, status, completed_at) VALUES (:id, :loop, :copy, :giver, "
                    ":receiver, '0000', 0, 'completed', :done)"
                ),
                {"id": trade_id, "loop": loop_id, "copy": copy_id, "giver": from_user,
                 "receiver": to_user, "done": done_at},
            )

        reviewed_at = f"{_day(number)}T20:00:00Z"
        connection.execute(
            text(
                "INSERT INTO reviews (id, trade_id, reviewer_id, reviewee_id, stars, as_described, "
                "actual_condition, comment, reply, visible_from, hidden_by_moderator, hidden_reason, "
                "created_at) VALUES (:id, :trade, :reviewer, :reviewee, :stars, :described, "
                ":actual, :comment, :reply, :visible, 0, NULL, :at)"
            ),
            {"id": f"review-hist-{number:02}", "trade": f"trade-hist-{number:02}a",
             "reviewer": receiver, "reviewee": giver, "stars": stars, "described": int(described),
             "actual": actual, "comment": comment, "reply": reply, "visible": reviewed_at,
             "at": reviewed_at},
        )

        if listed - actual >= 2:  # misdescribed: flag it for the moderator
            trade_id = f"trade-hist-{number:02}a"
            connection.execute(
                text("INSERT INTO entity_ids (table_name, entity_key) VALUES ('trades', :id)"),
                {"id": trade_id},
            )
            connection.execute(
                text(
                    "INSERT INTO audit_log (id, actor_id, action, target_table, target_id, created_at) "
                    "VALUES (:id, :actor, :action, 'trades', :target, :at)"
                ),
                {"id": f"audit-hist-{number:02}", "actor": receiver, "action": FLAGGED,
                 "target": trade_id, "at": reviewed_at},
            )

    connection.execute(text("UPDATE profiles SET status = 'under_review' WHERE id = 'user-dina'"))
    _seed_demo_review_swap(connection)


def _as_text(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _seed_demo_review_swap(connection: Connection) -> None:
    """Yesterday's swap between Eli and Carla, ready for Carla's review in the demo."""
    done = datetime.now(timezone.utc) - timedelta(days=1)
    eli_reviewed = done + timedelta(hours=2)
    connection.execute(
        text(
            "INSERT INTO loops "
            "(id, source, offer_id, round_id, status, meet_place, meet_time, no_show_user_id) "
            "VALUES ('loop-demo-review', 'offer', NULL, NULL, 'completed', 'Nova SBE library', :at, NULL)"
        ),
        {"at": _as_text(done)},
    )
    # (copy, book, listed condition, giver, receiver): each receiver owns the book now.
    for side, book, condition, giver, receiver in (
        ("a", "book-11", 4, "user-eli", "user-carla"),  # Chemistry, listed like new
        ("b", "book-15", 3, "user-carla", "user-eli"),  # Business Essentials, listed good
    ):
        connection.execute(
            text(
                'INSERT INTO copies (id, book_id, owner_id, "condition", highlighting, notes, '
                "status, created_at) VALUES (:id, :book, :owner, :condition, 'none', NULL, "
                "'unlisted', '2026-10-20T00:00:00Z')"
            ),
            {"id": f"copy-demo-review-{side}", "book": book, "owner": receiver, "condition": condition},
        )
        connection.execute(
            text(
                "INSERT INTO trades (id, loop_id, copy_id, giver_id, receiver_id, handoff_code, "
                "code_attempts, status, completed_at) VALUES (:id, 'loop-demo-review', :copy, "
                ":giver, :receiver, '0000', 0, 'completed', :done)"
            ),
            {"id": f"trade-demo-review-{side}", "copy": f"copy-demo-review-{side}", "giver": giver,
             "receiver": receiver, "done": _as_text(done)},
        )
    # Eli's review of Carla's book: hidden until Carla reviews too, or the 14 days for reviewing end.
    connection.execute(
        text(
            "INSERT INTO reviews (id, trade_id, reviewer_id, reviewee_id, stars, as_described, "
            "actual_condition, comment, reply, visible_from, hidden_by_moderator, hidden_reason, "
            "created_at) VALUES ('review-demo-eli', 'trade-demo-review-b', 'user-eli', 'user-carla', "
            "5, 1, 3, 'Exactly as described.', NULL, :visible, 0, NULL, :at)"
        ),
        {"visible": review_visible_from(done, everyone_reviewed=False), "at": _as_text(eli_reviewed)},
    )
