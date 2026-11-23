# Person 1 owns this file: starts the app: login, sidebar, menu.
import streamlit as st

from bookloop import auth
from bookloop.models import Profile
from bookloop.services.notify import get_notifications


def _show_sidebar(user: Profile) -> None:
    st.sidebar.subheader("BookLoop")
    st.sidebar.write(f"Logged in as **{user.display_name}**")
    st.sidebar.caption(user.role.title())
    if st.sidebar.button("Log out"):
        auth.logout()
        st.rerun()
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


# Each menu entry runs one file in pages/. Each page checks the login itself.
PAGES = (
    ("pages/1_Browse.py", "Browse"),
    ("pages/2_My_Shelf.py", "My Shelf"),
    ("pages/3_Offers.py", "Offers"),
    ("pages/4_Swap_Round.py", "Swap Round"),
    ("pages/5_My_Swaps.py", "My Swaps"),
    ("pages/6_Profile.py", "Profile"),
)
MODERATOR_PAGES = (
    ("pages/7_Moderator.py", "Moderator"),
    ("pages/8_Stats.py", "Stats"),
)


def _menu(user: Profile) -> list:
    """The pages for this user. Browse is the first page after logging in."""
    pages = [st.Page(path, title=title, default=(index == 0)) for index, (path, title) in enumerate(PAGES)]
    # Students don't see the moderator pages in the menu. If one types the address anyway,
    # the page itself refuses with a clear message (auth.require_role), instead of
    # Streamlit's "page not found" box.
    moderator_menu = "visible" if user.role == "moderator" else "hidden"
    pages += [st.Page(path, title=title, visibility=moderator_menu) for path, title in MODERATOR_PAGES]
    return pages


def _login_screen() -> None:
    """The page at every address while nobody is logged in: the login form."""
    auth.login()


def _login_menu() -> list:
    """While nobody is logged in, every page address shows the login form.

    So a shared link, or reloading the browser on any page (which logs you out), shows the
    login form instead of Streamlit's "page not found", and after logging in you are on
    the page you asked for: Streamlit matches pages by their address.
    """
    return [
        st.Page(_login_screen, title="Log in", url_path=st.Page(path).url_path, default=(index == 0))
        for index, (path, _title) in enumerate(PAGES + MODERATOR_PAGES)
    ]


def main() -> None:
    user = auth.logged_in_user()
    if user is None:
        # The login form is the only thing on screen: no menu before login. The form is
        # drawn inside the login page, not before the menu: Streamlit files each widget
        # under the page that draws it, and this way the first click on Continue counts.
        st.navigation(_login_menu(), position="hidden").run()
        return

    _show_sidebar(user)
    navigation = st.navigation(_menu(user))
    navigation.run()


if __name__ == "__main__":
    main()
