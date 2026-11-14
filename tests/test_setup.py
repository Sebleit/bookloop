# Person 1 owns this file: tests for project setup.
from dataclasses import fields, is_dataclass
from types import SimpleNamespace

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from bookloop.models import (
    AuditLog,
    Book,
    BookCourse,
    Copy,
    Course,
    Loop,
    Notification,
    Offer,
    Profile,
    Review,
    Round,
    RoundEntry,
    RoundWant,
    Trade,
    Wishlist,
)
from bookloop.rules.decision import Decision
from bookloop.rules.permissions import is_active, is_moderator
from bookloop.services.notify import get_notifications, notify
from bookloop.storage.copies_repo import get_copy, set_copy_status
from bookloop.storage.reviews_repo import is_blocked, swapper_score
from bookloop.storage.swaps_repo import create_loop


@pytest.mark.parametrize(
    ("model", "columns"),
    [
        (Profile, "id display_name role status created_at"),
        (Book, "id isbn title authors edition cover_url"),
        (Course, "id code name"),
        (BookCourse, "book_id course_id"),
        (Copy, "id book_id owner_id condition highlighting notes status created_at"),
        (Wishlist, "user_id book_id created_at"),
        (Notification, "id user_id text link read created_at"),
        (
            Offer,
            "id proposer_id offered_copy_id requested_copy_id status created_at expires_at",
        ),
        (
            Loop,
            "id source offer_id round_id status meet_place meet_time no_show_user_id",
        ),
        (
            Trade,
            "id loop_id copy_id giver_id receiver_id handoff_code code_attempts "
            "status completed_at",
        ),
        (
            Round,
            "id name phase entries_close_at wants_close_at meet_place meet_time created_by",
        ),
        (RoundEntry, "id round_id copy_id min_partner_score"),
        (RoundWant, "entry_id wanted_entry_id"),
        (
            Review,
            "id trade_id reviewer_id reviewee_id stars as_described actual_condition "
            "comment reply visible_from hidden_by_moderator hidden_reason created_at",
        ),
        (AuditLog, "id actor_id action target_table target_id created_at"),
    ],
)
def test_each_database_table_has_a_dataclass_with_every_column(model, columns):
    assert is_dataclass(model)
    assert [field.name for field in fields(model)] == columns.split()


def test_decision_yes_is_allowed_without_a_reason():
    assert Decision.yes() == Decision(allowed=True, reason=None)


def test_decision_no_keeps_its_reason():
    assert Decision.no("Only owners can do that.") == Decision(
        allowed=False,
        reason="Only owners can do that.",
    )


def test_user_with_moderator_role_is_a_moderator():
    assert is_moderator(SimpleNamespace(role="moderator")) is True


def test_student_is_not_a_moderator():
    assert is_moderator(SimpleNamespace(role="student")) is False


def test_missing_user_is_not_a_moderator():
    assert is_moderator(None) is False


def test_active_user_is_active():
    assert is_active(SimpleNamespace(status="active")) is True


def test_suspended_user_is_not_active():
    assert is_active(SimpleNamespace(status="suspended")) is False


def test_missing_user_is_not_active():
    assert is_active(None) is False


def test_get_copy_returns_copy_and_none_for_missing_id(make_user, make_book, make_copy):
    owner = make_user(name="Ana")
    book = make_book(id="book-a")
    copy = make_copy(owner=owner, book=book, id="copy-a")

    assert get_copy(copy.id) == copy
    assert get_copy("missing-copy") is None


def test_set_copy_status_updates_existing_copy(make_copy):
    copy = make_copy()

    set_copy_status(copy.id, "reserved")

    assert get_copy(copy.id).status == "reserved"


def test_set_copy_status_rejects_invalid_status_without_changing_copy(make_copy):
    copy = make_copy()
    with pytest.raises(ValueError):
        set_copy_status(copy.id, "broken")

    assert get_copy(copy.id).status == "available"


def test_set_copy_status_rejects_missing_copy():
    with pytest.raises(ValueError, match="Copy not found"):
        set_copy_status("missing-copy", "available")


def test_notify_adds_message_and_get_notifications_reads_it(make_user):
    user = make_user(name="Ana")
    other_user = make_user(name="Ben")

    created = notify(user.id, "A book you want is listed.", "/books/book-a")

    assert created.user_id == user.id
    assert created.text == "A book you want is listed."
    assert created.link == "/books/book-a"
    assert created.read is False
    assert get_notifications(user.id) == [created]
    assert get_notifications(other_user.id) == []


def test_create_loop_reserves_copies_and_creates_four_digit_codes(make_user, make_book, make_copy, database):
    ana = make_user(name="Ana")
    ben = make_user(name="Ben")
    copy_a = make_copy(owner=ana, book=make_book(title="Book A"))
    copy_b = make_copy(owner=ben, book=make_book(title="Book B"))

    loop = create_loop(
        [
            {"copy_id": copy_a.id, "giver_id": ana.id, "receiver_id": ben.id},
            {"copy_id": copy_b.id, "giver_id": ben.id, "receiver_id": ana.id},
        ],
        "offer",
        "Main library",
        "2026-11-20T14:00:00Z",
    )

    assert loop.source == "offer"
    assert loop.status == "scheduled"
    assert get_copy(copy_a.id).status == "reserved"
    assert get_copy(copy_b.id).status == "reserved"
    with database.connect() as connection:
        rows = connection.execute(
            text("SELECT handoff_code FROM trades WHERE loop_id = :loop_id"),
            {"loop_id": loop.id},
        ).scalars().all()
        loop_count = connection.execute(text("SELECT COUNT(*) FROM loops")).scalar_one()
    assert len(rows) == 2
    assert all(len(code) == 4 and code.isdigit() for code in rows)
    assert loop_count == 1


def test_create_loop_saves_nothing_if_a_copy_is_not_available(
    make_user, make_book, make_copy, database
):
    ana = make_user(name="Ana")
    ben = make_user(name="Ben")
    copy_a = make_copy(owner=ana, book=make_book())
    copy_b = make_copy(owner=ben, book=make_book(), status="in_round")
    trades = [
        {"copy_id": copy_a.id, "giver_id": ana.id, "receiver_id": ben.id},
        {"copy_id": copy_b.id, "giver_id": ben.id, "receiver_id": ana.id},
    ]

    with pytest.raises(ValueError, match="Copy is not available"):
        create_loop(trades, "offer", "Main library", "2026-11-20T14:00:00Z")

    assert get_copy(copy_a.id).status == "available"
    assert get_copy(copy_b.id).status == "in_round"
    with database.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM loops")).scalar_one() == 0
        assert connection.execute(text("SELECT COUNT(*) FROM trades")).scalar_one() == 0


def test_create_loop_rolls_back_prior_writes_if_a_trade_fails(
    make_user, make_book, make_copy, database
):
    ana = make_user(name="Ana")
    ben = make_user(name="Ben")
    copy_a = make_copy(owner=ana, book=make_book())
    copy_b = make_copy(owner=ben, book=make_book())
    trades = [
        {"copy_id": copy_a.id, "giver_id": ana.id, "receiver_id": ben.id},
        {"copy_id": copy_b.id, "giver_id": "missing-user", "receiver_id": ana.id},
    ]

    with pytest.raises(IntegrityError):
        create_loop(trades, "offer", "Main library", "2026-11-20T14:00:00Z")

    assert get_copy(copy_a.id).status == "available"
    assert get_copy(copy_b.id).status == "available"
    with database.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM loops")).scalar_one() == 0
        assert connection.execute(text("SELECT COUNT(*) FROM trades")).scalar_one() == 0


def test_swapper_score_without_reviews_is_four_and_new(make_user):
    user = make_user(name="Carla")

    score = swapper_score(user.id)

    assert score.score == 4.0
    assert score.accuracy == 0.0
    assert score.badge == "New"


def test_swapper_score_uses_formula_and_accuracy(make_user, make_review):
    reviewee = make_user(name="Ben")
    reviewer = make_user(name="Ana")
    for stars, accurate in ((5, True), (5, True), (4, True), (2, False)):
        make_review(
            reviewer=reviewer,
            reviewee=reviewee,
            stars=stars,
            as_described=accurate,
        )

    score = swapper_score(reviewee.id)

    assert score.score == 4.0
    assert score.accuracy == 75.0
    assert score.badge is None


def test_swapper_score_ignores_moderator_hidden_reviews(make_user, make_review):
    reviewee = make_user(name="Ben")
    reviewer = make_user(name="Ana")
    make_review(reviewer=reviewer, reviewee=reviewee, stars=5, as_described=True)
    make_review(
        reviewer=reviewer,
        reviewee=reviewee,
        stars=1,
        as_described=False,
        hidden_by_moderator=True,
        hidden_reason="Abusive content",
    )

    score = swapper_score(reviewee.id)

    assert score.score == 4.25
    assert score.accuracy == 100.0
    assert score.badge == "New"


def test_swapper_score_assigns_trusted_badge(make_user, make_review):
    reviewee = make_user(name="Ben")
    reviewer = make_user(name="Ana")
    for _ in range(5):
        make_review(reviewer=reviewer, reviewee=reviewee, stars=5, as_described=True)

    score = swapper_score(reviewee.id)

    assert score.score == 4.62
    assert score.accuracy == 100.0
    assert score.badge == "Trusted"


def test_swapper_score_assigns_under_review_badge(make_user, make_review):
    reviewee = make_user(name="Ben")
    reviewer = make_user(name="Ana")
    for stars, accurate in ((1, True), (2, False), (2, False)):
        make_review(
            reviewer=reviewer,
            reviewee=reviewee,
            stars=stars,
            as_described=accurate,
        )

    score = swapper_score(reviewee.id)

    assert score.score == 2.83
    assert score.badge == "Under review"


@pytest.mark.parametrize(
    ("status", "expected"),
    [("active", False), ("under_review", True), ("suspended", True)],
)
def test_is_blocked_matches_profile_status(make_user, status, expected):
    user = make_user(name="Ana", status=status)

    assert is_blocked(user.id) is expected
    assert is_blocked("missing-user") is False
