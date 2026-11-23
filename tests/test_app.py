"""Tests for app.py: login, log out, and every menu entry opening its page.

They log in with the demo users (laptop mode, test database) and visit each
page through the real menu, so a wrong file name in app.py fails here. They
also check that a student is kept out of the moderator pages, and play the
demo's handoff on My Swaps.
"""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from bookloop import auth
from bookloop.models import Profile
from bookloop.storage import rounds_repo
from seed import base as seed_base
from seed import rounds as seed_rounds
from seed import swaps as seed_swaps


APP = Path(__file__).resolve().parents[1] / "app.py"
STUDENT_PAGES = {
    "pages/1_Browse.py": "Browse",
    "pages/2_My_Shelf.py": "My Shelf",
    "pages/3_Offers.py": "Offers",
    "pages/4_Swap_Round.py": "Swap Round",
    "pages/5_My_Swaps.py": "My Swaps",
    "pages/6_Profile.py": "Profile",
}
MODERATOR_PAGES = {"pages/7_Moderator.py": "Moderator", "pages/8_Stats.py": "Stats"}


def demo_user(id: str, name: str, role: str = "student") -> Profile:
    return Profile(id=id, display_name=name, role=role, status="active", created_at=seed_base.CREATED_AT)


def open_app(user: Profile) -> AppTest:
    app = AppTest.from_file(str(APP), default_timeout=30)
    app.session_state["current_user"] = user
    app.session_state["_auth_mode"] = "laptop"
    return app.run()


@pytest.fixture
def demo_data(database):
    with database.begin() as connection:
        seed_base.seed(connection)


@pytest.fixture
def demo_swaps(demo_data, database):
    with database.begin() as connection:
        seed_swaps.seed(connection)


def test_logged_out_the_app_shows_only_the_login_screen(demo_data):
    app = AppTest.from_file(str(APP), default_timeout=30).run()

    assert not app.exception
    assert [title.value for title in app.title] == ["Dev login"]


def test_online_the_app_shows_email_login_and_never_the_dev_login(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:password@example.invalid:5432/bookloop")
    monkeypatch.setenv("SUPABASE_URL", "https://example.invalid")
    monkeypatch.setenv("SUPABASE_KEY", "placeholder-not-a-real-key")

    app = AppTest.from_file(str(APP), default_timeout=30).run()

    assert not app.exception
    assert [title.value for title in app.title] == ["BookLoop login"]
    assert [tab.label for tab in app.tabs] == ["Log in", "Sign up"]
    assert not app.selectbox  # no list of demo users to pick from


# Streamlit's test tool can't follow a click on the login form into the menu, or open a page
# by its web address, so those were checked by hand in a browser: logging in opens Browse, a
# link to any page shows the login form and then that page, and Log out works in one click.
def test_the_dev_login_saves_the_chosen_user(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    session_state = {}

    saved = auth._save_dev_login(demo_user("user-carla", "Carla"), session_state)

    assert saved is True
    assert session_state["current_user"].display_name == "Carla"
    assert session_state["_auth_mode"] == "laptop"


def test_a_logged_in_student_lands_on_browse_with_log_out_in_the_sidebar(demo_data):
    app = open_app(demo_user("user-carla", "Carla"))

    assert not app.exception
    assert app.title[0].value == "Browse"
    assert "Logged in as **Carla**" in [text.value for text in app.sidebar.markdown]
    assert "Log out" in [button.label for button in app.sidebar.button]


def test_log_out_forgets_the_user_and_everything_remembered_for_them():
    # What the Log out button calls.
    session_state = {"current_user": demo_user("user-carla", "Carla"), "_auth_mode": "laptop", "shelf_lookup": {}}

    auth.logout(session_state)

    assert session_state == {}


@pytest.mark.parametrize(("page", "title"), STUDENT_PAGES.items())
def test_a_student_can_open_every_menu_page(demo_data, page, title):
    app = open_app(demo_user("user-ana", "Ana"))

    app.switch_page(page).run()

    assert not app.exception
    assert app.title[0].value == title
    assert not any("being built" in text.value for text in app.markdown)


@pytest.mark.parametrize(("page", "title"), MODERATOR_PAGES.items())
def test_a_moderator_can_open_the_moderator_pages(demo_data, page, title):
    app = open_app(demo_user("user-moderator", "Morgan", role="moderator"))

    app.switch_page(page).run()

    assert not app.exception
    assert app.title[0].value == title
    assert not app.error


@pytest.mark.parametrize("page", MODERATOR_PAGES)
def test_a_student_who_types_a_moderator_address_gets_a_clear_error(demo_data, page):
    app = open_app(demo_user("user-carla", "Carla"))

    app.switch_page(page).run()

    assert not app.exception
    assert [error.value for error in app.error] == ["You don't have permission to view this page."]
    assert not app.title


def test_my_swaps_shows_a_pending_swap_and_confirms_the_handoff(demo_swaps):
    # Carla gives a book to Dina and receives one from her in the same swap, so the
    # swap appears twice on the page: it must still open, with one no-show button.
    app = open_app(demo_user("user-carla", "Carla"))
    app.switch_page("pages/5_My_Swaps.py").run()

    assert not app.exception
    assert [button.label for button in app.button].count("Report no-show") == 1
    assert "Time: Sun 22 Nov, 11:00" in [text.value for text in app.markdown]  # Lisbon time

    app.text_input[0].input("0000")
    app = next(button for button in app.button if button.label == "Confirm handoff").click().run()
    assert [error.value for error in app.error] == ["The handoff code is incorrect."]

    app.text_input[0].input("3333")
    app = next(button for button in app.button if button.label == "Confirm handoff").click().run()
    assert not app.exception
    assert [message.value for message in app.success] == [
        "Handoff confirmed. The book now belongs to the receiver."
    ]
    assert "Confirm handoff" not in [button.label for button in app.button]


def test_in_a_round_loop_my_swaps_asks_who_did_not_come(demo_data, database):
    with database.begin() as connection:
        seed_rounds.seed(connection)
    rounds_repo.run_round("round-demo")

    app = open_app(demo_user("user-ana", "Ana"))
    app.switch_page("pages/5_My_Swaps.py").run()

    assert not app.exception
    (who,) = app.selectbox
    assert who.options == ["Eli", "Farah"]
    assert [button.label for button in app.button].count("Report no-show") == 1
