# Person 1 owns this file: starts the app: login, sidebar, menu.
import streamlit as st

from bookloop import auth
from bookloop.models import Profile
from bookloop.services.notify import get_notifications


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

    # Each menu entry runs one file in pages/. Each page checks the login itself.
    pages = [
        st.Page("pages/1_Browse.py", title="Browse", default=True),
        st.Page("pages/2_My_Shelf.py", title="My Shelf"),
        st.Page("pages/3_Offers.py", title="Offers"),
        st.Page("pages/4_Swap_Round.py", title="Swap Round"),
        st.Page("pages/5_My_Swaps.py", title="My Swaps"),
        st.Page("pages/6_Profile.py", title="Profile"),
    ]
    if user.role == "moderator":
        pages.extend(
            [
                st.Page("pages/7_Moderator.py", title="Moderator"),
                st.Page("pages/8_Stats.py", title="Stats"),
            ]
        )

    navigation = st.navigation(pages)
    navigation.run()


if __name__ == "__main__":
    main()
