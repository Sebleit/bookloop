# Person 1 owns this file: starts the app: login, sidebar, menu.
import streamlit as st

from bookloop import auth
from bookloop.models import Profile
from bookloop.services.notify import get_notifications


def _placeholder_page(title: str, owner: int, moderator_only: bool = False) -> None:
    if moderator_only:
        auth.require_role("moderator")
    else:
        auth.current_user()
    st.title(title)
    st.write(f"This page is being built by Person {owner}.")


def _browse() -> None:
    _placeholder_page("Browse", 1)


def _my_shelf() -> None:
    _placeholder_page("My Shelf", 1)


def _offers() -> None:
    _placeholder_page("Offers", 2)


def _swap_round() -> None:
    _placeholder_page("Swap Round", 3)


def _my_swaps() -> None:
    _placeholder_page("My Swaps", 2)


def _profile() -> None:
    _placeholder_page("Profile", 4)


def _moderator() -> None:
    _placeholder_page("Moderator", 4, moderator_only=True)


def _stats() -> None:
    _placeholder_page("Stats", 2, moderator_only=True)


def _show_sidebar(user: Profile) -> None:
    st.sidebar.subheader("BookLoop")
    st.sidebar.write(f"Logged in as **{user.display_name}**")
    st.sidebar.caption(user.role.title())
    st.sidebar.subheader("Notifications")

    try:
        notifications = get_notifications(user.id)
    except Exception:
        st.sidebar.info("Notifications are unavailable right now.")
        return

    if not notifications:
        st.sidebar.caption("No notifications yet.")
        return

    for notification in notifications:
        marker = "✓" if notification.read else "•"
        st.sidebar.write(f"{marker} {notification.text}")


def main() -> None:
    user = auth.login()
    if user is None:
        st.stop()

    user = auth.current_user()
    _show_sidebar(user)

    pages = [
        st.Page(_browse, title="Browse", default=True),
        st.Page(_my_shelf, title="My Shelf"),
        st.Page(_offers, title="Offers"),
        st.Page(_swap_round, title="Swap Round"),
        st.Page(_my_swaps, title="My Swaps"),
        st.Page(_profile, title="Profile"),
    ]
    if user.role == "moderator":
        pages.extend(
            [
                st.Page(_moderator, title="Moderator"),
                st.Page(_stats, title="Stats"),
            ]
        )

    navigation = st.navigation(pages)
    navigation.run()


if __name__ == "__main__":
    main()
