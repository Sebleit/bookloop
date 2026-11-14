# Person 1 owns this file: login, current user and role checks.
import os
from datetime import datetime, timezone
from typing import Any

import streamlit as st
from sqlalchemy import text
from supabase import create_client

from bookloop.models import Profile
from bookloop.storage import db


def _is_laptop_mode() -> bool:
    return not bool(os.environ.get("DATABASE_URL"))


def _profile_from_row(row: Any) -> Profile:
    return Profile(
        id=str(row["id"]),
        display_name=row["display_name"],
        role=row["role"],
        status=row["status"],
        created_at=row["created_at"],
    )


def _save_user(profile: Profile, mode: str, session_state: Any = None) -> None:
    state = st.session_state if session_state is None else session_state
    state["current_user"] = profile
    state["_auth_mode"] = mode


def _save_dev_login(profile: Profile, session_state: Any = None) -> bool:
    """Save a demo user only when the app is running without a database URL."""
    if not _is_laptop_mode():
        return False
    _save_user(profile, "laptop", session_state)
    return True


def _demo_users() -> list[Profile]:
    with db.transaction() as connection:
        rows = connection.execute(
            text(
                "SELECT id, display_name, role, status, created_at "
                "FROM profiles ORDER BY role, display_name"
            )
        ).mappings()
        return [_profile_from_row(row) for row in rows]


def _supabase_client():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        st.error("Online login is not configured. Ask the project owner to check the app settings.")
        return None

    try:
        client = create_client(url, key)
    except Exception:
        st.error("We couldn't connect to Supabase Auth. Check the project settings and try again.")
        return None

    return client


def _profile_for_auth_user(auth_user: Any) -> Profile | None:
    user_id = str(auth_user.id)
    with db.transaction() as connection:
        row = connection.execute(
            text(
                "SELECT id, display_name, role, status, created_at "
                "FROM profiles WHERE id = :id"
            ),
            {"id": user_id},
        ).mappings().first()
    return _profile_from_row(row) if row else None


def _sign_up(client: Any, display_name: str, email: str, password: str) -> None:
    try:
        response = client.auth.sign_up({"email": email, "password": password})
        auth_user = response.user
        if auth_user is None:
            st.error("We couldn't create the account. Check your details and try again.")
            return

        created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        with db.transaction() as connection:
            connection.execute(
                text(
                    "INSERT INTO profiles (id, display_name, role, status, created_at) "
                    "VALUES (:id, :display_name, 'student', 'active', :created_at) "
                    "ON CONFLICT (id) DO NOTHING"
                ),
                {
                    "id": str(auth_user.id),
                    "display_name": display_name,
                    "created_at": created_at,
                },
            )

        if response.session is None:
            st.success("Account created. Sign in after confirming your email.")
            return

        profile = _profile_for_auth_user(auth_user)
        if profile is None:
            st.error("Your account was created, but its profile could not be loaded. Ask for help.")
            return
        _save_user(profile, "online")
        st.rerun()
    except Exception:
        st.error("We couldn't create the account. Check your details and try again.")


def _sign_in(client: Any, email: str, password: str) -> None:
    try:
        response = client.auth.sign_in_with_password({"email": email, "password": password})
        if response.user is None:
            st.error("Email or password was not accepted.")
            return

        profile = _profile_for_auth_user(response.user)
        if profile is None:
            st.error("Your account profile is missing. Ask the project owner for help.")
            return
        _save_user(profile, "online")
        st.rerun()
    except Exception:
        st.error("Email or password was not accepted.")


def _show_dev_login() -> None:
    st.title("Dev login")
    try:
        users = _demo_users()
    except Exception:
        st.error("The local database is not ready. Run `uv run python seed.py` and try again.")
        return

    if not users:
        st.info("There are no demo users yet. Run `uv run python seed.py` first.")
        return

    with st.form("dev_login_form"):
        selected = st.selectbox("Dev login", users, format_func=lambda user: user.display_name)
        submitted = st.form_submit_button("Continue")

    if submitted:
        if _save_dev_login(selected):
            st.rerun()
        else:
            st.error("Dev login is disabled when DATABASE_URL is set.")


def _show_online_login() -> None:
    st.title("BookLoop login")
    client = _supabase_client()
    if client is None:
        return

    login_tab, sign_up_tab = st.tabs(("Log in", "Sign up"))
    with login_tab:
        with st.form("login_form"):
            email = st.text_input("Email", key="login_email")
            password = st.text_input("Password", type="password", key="login_password")
            submitted = st.form_submit_button("Log in")
        if submitted:
            _sign_in(client, email.strip(), password)

    with sign_up_tab:
        with st.form("sign_up_form"):
            display_name = st.text_input("First name", key="sign_up_name")
            email = st.text_input("Email", key="sign_up_email")
            password = st.text_input("Password", type="password", key="sign_up_password")
            submitted = st.form_submit_button("Create account")
        if submitted:
            if not display_name.strip() or not email.strip() or not password:
                st.error("Enter your first name, email, and password.")
            else:
                _sign_up(client, display_name.strip(), email.strip(), password)


def login() -> Profile | None:
    """Show the laptop demo login or online Supabase Auth forms."""
    mode = "laptop" if _is_laptop_mode() else "online"
    user = st.session_state.get("current_user")
    if user is not None and st.session_state.get("_auth_mode") == mode:
        return user
    if user is not None:
        st.session_state.pop("current_user", None)
        st.session_state.pop("_auth_mode", None)

    if mode == "laptop":
        _show_dev_login()
    else:
        _show_online_login()
    return st.session_state.get("current_user")


def current_user() -> Profile:
    """Return the signed-in profile or stop the page with a friendly message."""
    user = st.session_state.get("current_user")
    expected_mode = "laptop" if _is_laptop_mode() else "online"
    if user is None or st.session_state.get("_auth_mode") != expected_mode:
        st.info("Please log in to continue.")
        st.stop()
    return user


def require_role(role: str) -> Profile:
    """Return the signed-in profile, stopping the page if its role does not match."""
    user = current_user()
    if user.role != role:
        st.error("You don't have permission to view this page.")
        st.stop()
    return user
