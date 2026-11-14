# Person 1 owns this file: tests for login setup.
from bookloop.auth import _save_dev_login


def test_dev_login_is_impossible_when_database_url_is_set(monkeypatch, make_user):
    monkeypatch.setenv("DATABASE_URL", "postgresql://example.invalid/bookloop")
    session_state = {}
    demo_user = make_user(name="Ana", id="user-ana")

    saved = _save_dev_login(demo_user, session_state)

    assert saved is False
    assert "current_user" not in session_state
