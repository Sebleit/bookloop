# Person 1 owns this file: tests for project setup.
from dataclasses import fields, is_dataclass
from pathlib import Path
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
from bookloop.storage import db
from bookloop.storage.copies_repo import get_copy, set_copy_status
from bookloop.storage.reviews_repo import is_blocked, swapper_score
from bookloop.storage.swaps_repo import create_loop


@pytest.fixture
def shared_function_database(tmp_path, monkeypatch):
    engine = db._create_engine(f"sqlite:///{(tmp_path / 'shared-functions.sqlite').as_posix()}")
    migration_path = Path(__file__).resolve().parents[1] / "db" / "migrations" / "001_init.sql"
    migration = migration_path.read_text(encoding="utf-8")
    with engine.begin() as connection:
        for statement in migration.split(";"):
            if statement.strip():
                connection.exec_driver_sql(statement)

        for user_id, name, role, status in (
            ("user-a", "Ana", "student", "active"),
            ("user-b", "Ben", "student", "active"),
            ("user-c", "Carla", "student", "active"),
        ):
            connection.execute(
                text(
                    "INSERT INTO profiles (id, display_name, role, status, created_at) "
                    "VALUES (:id, :name, :role, :status, '2026-11-14T00:00:00Z')"
                ),
                {"id": user_id, "name": name, "role": role, "status": status},
            )

        for book_id in ("book-a", "book-b", "book-c"):
            connection.execute(
                text(
                    "INSERT INTO books (id, isbn, title, authors) "
                    "VALUES (:id, :isbn, :title, 'Test Author')"
                ),
                {"id": book_id, "isbn": f"isbn-{book_id}", "title": book_id},
            )

        for index, (book_id, owner_id) in enumerate(
            (("book-a", "user-a"), ("book-b", "user-b"), ("book-c", "user-c")),
            start=1,
        ):
            connection.execute(
                text(
                    'INSERT INTO copies '
                    '(id, book_id, owner_id, "condition", highlighting, status, created_at) '
                    "VALUES (:id, :book_id, :owner_id, 3, 'none', 'available', '2026-11-14T00:00:00Z')"
                ),
                {"id": f"copy-{index}", "book_id": book_id, "owner_id": owner_id},
            )

    monkeypatch.setattr(db, "engine", engine)
    yield engine
    engine.dispose()


def _add_review(connection, index, stars, as_described, hidden=0, reviewee_id="user-b"):
    loop_id = f"review-loop-{index}"
    trade_id = f"review-trade-{index}"
    created_at = f"2026-11-14T00:00:{index:02d}Z"
    connection.execute(
        text(
            "INSERT INTO loops (id, source, status) "
            "VALUES (:id, 'round', 'completed')"
        ),
        {"id": loop_id},
    )
    connection.execute(
        text(
            "INSERT INTO trades "
            "(id, loop_id, copy_id, giver_id, receiver_id, handoff_code, status, completed_at) "
            "VALUES (:id, :loop_id, 'copy-1', 'user-b', 'user-a', '1234', 'completed', :created_at)"
        ),
        {"id": trade_id, "loop_id": loop_id, "created_at": created_at},
    )
    connection.execute(
        text(
            "INSERT INTO reviews "
            "(id, trade_id, reviewer_id, reviewee_id, stars, as_described, actual_condition, "
            "hidden_by_moderator, created_at) "
            "VALUES (:id, :trade_id, 'user-a', :reviewee_id, :stars, :as_described, 3, :hidden, :created_at)"
        ),
        {
            "id": f"review-{index}",
            "trade_id": trade_id,
            "reviewee_id": reviewee_id,
            "stars": stars,
            "as_described": as_described,
            "hidden": hidden,
            "created_at": created_at,
        },
    )


@pytest.mark.parametrize(
    ("model", "columns"),
    [
        (Profile, "id display_name role status created_at"),
        (Book, "id isbn title authors edition cover_url"),
        (Course, "id code name"),
        (BookCourse, "book_id course_id"),
        (
            Copy,
            "id book_id owner_id condition highlighting notes status created_at",
        ),
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


def test_get_copy_returns_copy_and_none_for_missing_id(shared_function_database):
    copy = get_copy("copy-1")

    assert copy == Copy(
        id="copy-1",
        book_id="book-a",
        owner_id="user-a",
        condition=3,
        highlighting="none",
        notes=None,
        status="available",
        created_at="2026-11-14T00:00:00Z",
    )
    assert get_copy("missing-copy") is None


def test_set_copy_status_updates_existing_copy(shared_function_database):
    set_copy_status("copy-1", "reserved")

    assert get_copy("copy-1").status == "reserved"


def test_set_copy_status_rejects_invalid_status_without_changing_copy(shared_function_database):
    with pytest.raises(ValueError):
        set_copy_status("copy-1", "broken")

    assert get_copy("copy-1").status == "available"


def test_set_copy_status_rejects_missing_copy(shared_function_database):
    with pytest.raises(ValueError, match="Copy not found"):
        set_copy_status("missing-copy", "available")


def test_notify_adds_message_and_get_notifications_reads_it(shared_function_database):
    created = notify("user-a", "A book you want is listed.", "/books/book-a")

    assert created.user_id == "user-a"
    assert created.text == "A book you want is listed."
    assert created.link == "/books/book-a"
    assert created.read is False
    assert get_notifications("user-a") == [created]
    assert get_notifications("user-b") == []


def test_create_loop_reserves_copies_and_creates_four_digit_codes(shared_function_database):
    loop = create_loop(
        [
            {"copy_id": "copy-1", "giver_id": "user-a", "receiver_id": "user-b"},
            {"copy_id": "copy-2", "giver_id": "user-b", "receiver_id": "user-a"},
        ],
        "offer",
        "Main library",
        "2026-11-20T14:00:00Z",
    )

    assert loop.source == "offer"
    assert loop.status == "scheduled"
    assert get_copy("copy-1").status == "reserved"
    assert get_copy("copy-2").status == "reserved"
    with shared_function_database.connect() as connection:
        rows = connection.execute(
            text("SELECT handoff_code FROM trades WHERE loop_id = :loop_id"),
            {"loop_id": loop.id},
        ).scalars().all()
        loop_count = connection.execute(text("SELECT COUNT(*) FROM loops")).scalar_one()
    assert len(rows) == 2
    assert all(len(code) == 4 and code.isdigit() for code in rows)
    assert loop_count == 1


def test_create_loop_saves_nothing_if_a_copy_is_not_available(shared_function_database):
    set_copy_status("copy-2", "in_round")
    trades = [
        {"copy_id": "copy-1", "giver_id": "user-a", "receiver_id": "user-b"},
        {"copy_id": "copy-2", "giver_id": "user-b", "receiver_id": "user-a"},
    ]

    with pytest.raises(ValueError, match="Copy is not available"):
        create_loop(trades, "offer", "Main library", "2026-11-20T14:00:00Z")

    assert get_copy("copy-1").status == "available"
    assert get_copy("copy-2").status == "in_round"
    with shared_function_database.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM loops")).scalar_one() == 0
        assert connection.execute(text("SELECT COUNT(*) FROM trades")).scalar_one() == 0


def test_create_loop_rolls_back_prior_writes_if_a_trade_fails(shared_function_database):
    trades = [
        {"copy_id": "copy-1", "giver_id": "user-a", "receiver_id": "user-b"},
        {"copy_id": "copy-2", "giver_id": "missing-user", "receiver_id": "user-a"},
    ]

    with pytest.raises(IntegrityError):
        create_loop(trades, "offer", "Main library", "2026-11-20T14:00:00Z")

    assert get_copy("copy-1").status == "available"
    assert get_copy("copy-2").status == "available"
    with shared_function_database.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM loops")).scalar_one() == 0
        assert connection.execute(text("SELECT COUNT(*) FROM trades")).scalar_one() == 0


def test_swapper_score_without_reviews_is_four_and_new(shared_function_database):
    score = swapper_score("user-c")

    assert score.score == 4.0
    assert score.accuracy == 0.0
    assert score.badge == "New"


def test_swapper_score_uses_formula_and_accuracy(shared_function_database):
    with shared_function_database.begin() as connection:
        for index, stars, accurate in (
            (1, 5, 1),
            (2, 5, 1),
            (3, 4, 1),
            (4, 2, 0),
        ):
            _add_review(connection, index, stars, accurate)

    score = swapper_score("user-b")

    assert score.score == 4.0
    assert score.accuracy == 75.0
    assert score.badge is None


def test_swapper_score_ignores_moderator_hidden_reviews(shared_function_database):
    with shared_function_database.begin() as connection:
        _add_review(connection, 1, 5, 1)
        _add_review(connection, 2, 1, 0, hidden=1)

    score = swapper_score("user-b")

    assert score.score == 4.25
    assert score.accuracy == 100.0
    assert score.badge == "New"


def test_swapper_score_assigns_trusted_badge(shared_function_database):
    with shared_function_database.begin() as connection:
        for index in range(1, 6):
            _add_review(connection, index, 5, 1)

    score = swapper_score("user-b")

    assert score.score == 4.62
    assert score.accuracy == 100.0
    assert score.badge == "Trusted"


def test_swapper_score_assigns_under_review_badge(shared_function_database):
    with shared_function_database.begin() as connection:
        _add_review(connection, 1, 1, 1)
        _add_review(connection, 2, 2, 0)
        _add_review(connection, 3, 2, 0)

    score = swapper_score("user-b")

    assert score.score == 2.83
    assert score.badge == "Under review"


@pytest.mark.parametrize(
    ("status", "expected"),
    [("active", False), ("under_review", True), ("suspended", True)],
)
def test_is_blocked_matches_profile_status(shared_function_database, status, expected):
    with shared_function_database.begin() as connection:
        connection.execute(
            text("UPDATE profiles SET status = :status WHERE id = 'user-a'"),
            {"status": status},
        )

    assert is_blocked("user-a") is expected
    assert is_blocked("missing-user") is False
