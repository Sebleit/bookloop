# Person 1 owns this file: tests for project setup.
from dataclasses import fields, is_dataclass
from types import SimpleNamespace

import pytest

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
