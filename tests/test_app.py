"""Tests for app.py: every menu entry opens its page without errors.

They log in with the demo users (laptop mode, test database) and visit each
page through the real menu, so a wrong file name in app.py fails here.
"""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from bookloop.models import Profile
from seed import base as seed_base


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
