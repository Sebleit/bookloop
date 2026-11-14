# Person 1 owns this file: tests for login setup.
from bookloop.auth import _save_dev_login
from bookloop.models import Profile


def test_dev_login_is_impossible_when_database_url_is_set(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://example.invalid/bookloop")
    session_state = {}
    demo_user = Profile(
        id="user-ana",
        display_name="Ana",
        role="student",
        status="active",
        created_at="2026-11-14T00:00:00Z",
    )

    saved = _save_dev_login(demo_user, session_state)

    assert saved is False
    assert "current_user" not in session_state
