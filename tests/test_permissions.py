# Person 2 owns this file: tests for permissions.
import pytest
from streamlit.runtime.scriptrunner import StopException

from bookloop import auth
from bookloop.models import Profile
from bookloop.rules.offers import can_make_offer
from bookloop.storage.reviews_repo import is_blocked


def profile(user_id: str, role: str = "student", status: str = "active") -> Profile:
    return Profile(
        id=user_id,
        display_name=user_id.title(),
        role=role,
        status=status,
        created_at="2026-11-14T00:00:00Z",
    )


def test_logged_out_user_cannot_access_a_page(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(auth.st, "session_state", {})
    monkeypatch.setattr(auth.st, "info", lambda _message: None)
    monkeypatch.setattr(auth.st, "stop", lambda: (_ for _ in ()).throw(StopException()))

    with pytest.raises(StopException):
        auth.current_user()


def test_student_cannot_open_moderator_page(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    state = {"current_user": profile("student"), "_auth_mode": "laptop"}
    monkeypatch.setattr(auth.st, "session_state", state)
    monkeypatch.setattr(auth.st, "error", lambda _message: None)
    monkeypatch.setattr(auth.st, "stop", lambda: (_ for _ in ()).throw(StopException()))

    with pytest.raises(StopException):
        auth.require_role("moderator")


def test_moderator_can_open_moderator_page(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    moderator = profile("moderator", role="moderator")
    monkeypatch.setattr(
        auth.st,
        "session_state",
        {"current_user": moderator, "_auth_mode": "laptop"},
    )

    assert auth.require_role("moderator") == moderator


def test_under_review_user_cannot_make_an_offer(database, make_copy, make_user):
    blocked_user = make_user(name="Blocked", status="under_review")
    other_user = make_user(name="Other")
    offered = make_copy(owner=blocked_user)
    requested = make_copy(owner=other_user)

    decision = can_make_offer(
        blocked_user.id,
        offered,
        requested,
        pending_offer_count=0,
        blocked=is_blocked(blocked_user.id),
    )

    assert decision.allowed is False
