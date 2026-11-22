"""Tests for the wishlist: the rules in bookloop/rules/wishlist.py, saving in
copies_repo.py, the notification when a wanted book is listed, and the
wishlist on the My Shelf page.
"""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from bookloop.rules.wishlist import can_add_to_wishlist, can_remove_from_wishlist, people_to_notify
from bookloop.services import openlibrary
from bookloop.services.notify import get_notifications
from bookloop.storage import copies_repo


# --- Rules -----------------------------------------------------------------


def test_a_book_can_be_added_to_the_wishlist(make_user):
    assert can_add_to_wishlist(make_user(name="Ana"), already_wanted=False).allowed is True


def test_adding_the_same_book_twice_is_refused(make_user):
    decision = can_add_to_wishlist(make_user(name="Ana"), already_wanted=True)

    assert decision.reason == "This book is already on your wishlist."


def test_only_books_on_the_wishlist_can_be_removed(make_user):
    ana = make_user(name="Ana")

    assert can_remove_from_wishlist(ana, already_wanted=True).allowed is True
    assert can_remove_from_wishlist(ana, already_wanted=False).reason == "This book isn't on your wishlist."


def test_everyone_who_wants_the_book_is_told_except_the_lister():
    assert people_to_notify(["ana", "ben", "ana", "carla"], lister_id="ben") == ["ana", "carla"]


# --- Saving ----------------------------------------------------------------


def test_adding_and_removing_wishlist_books(make_user, make_book):
    ana = make_user(name="Ana")
    book = make_book(title="Principles of Economics")

    copies_repo.add_to_wishlist(ana.id, book.id)
    assert copies_repo.is_on_wishlist(ana.id, book.id) is True
    assert [wanted.title for wanted in copies_repo.wishlist_books(ana.id)] == ["Principles of Economics"]

    copies_repo.remove_from_wishlist(ana.id, book.id)
    assert copies_repo.wishlist_books(ana.id) == []


def test_the_database_refuses_the_same_book_twice_and_keeps_one(make_user, make_book):
    ana = make_user(name="Ana")
    book = make_book()
    copies_repo.add_to_wishlist(ana.id, book.id)

    with pytest.raises(Exception):
        copies_repo.add_to_wishlist(ana.id, book.id)

    assert len(copies_repo.wishlist_books(ana.id)) == 1


# --- Notifications when a wanted book is listed ----------------------------


def test_listing_a_wanted_book_notifies_the_people_who_want_it(make_user, make_book):
    ana, ben, carla = make_user(name="Ana"), make_user(name="Ben"), make_user(name="Carla")
    book = make_book(title="Principles of Economics")
    copies_repo.add_to_wishlist(ana.id, book.id)
    copies_repo.add_to_wishlist(carla.id, book.id)

    _, told = copies_repo.add_copy(ben.id, book.id, 3, "light", None, [])

    assert told == 2
    (message,) = get_notifications(ana.id)
    assert message.text == (
        "“Principles of Economics” from your wishlist was just listed by Ben. Find it in Browse."
    )
    assert len(get_notifications(carla.id)) == 1


def test_listing_your_own_wanted_book_does_not_notify_you(make_user, make_book):
    ana = make_user(name="Ana")
    book = make_book()
    copies_repo.add_to_wishlist(ana.id, book.id)

    _, told = copies_repo.add_copy(ana.id, book.id, 3, "none", None, [])

    assert told == 0
    assert get_notifications(ana.id) == []


def test_listing_a_book_nobody_wants_notifies_nobody(make_user, make_book):
    ben = make_user(name="Ben")
    other = make_user(name="Ana")

    copies_repo.add_copy(ben.id, make_book().id, 3, "none", None, [])

    assert get_notifications(other.id) == []


# --- The wishlist on My Shelf ----------------------------------------------


ROOT = Path(__file__).resolve().parents[1]


def open_shelf(user) -> AppTest:
    page = AppTest.from_file(str(ROOT / "pages" / "2_My_Shelf.py"), default_timeout=30)
    page.session_state["current_user"] = user
    page.session_state["_auth_mode"] = "laptop"
    return page.run()


def by_label(widgets, label):
    return next(widget for widget in widgets if widget.label == label)


def click(page, label):
    return next(button for button in page.button if button.label == label).click().run()


def test_a_book_can_be_added_to_the_wishlist_from_my_shelf(make_user, monkeypatch, fake_open_library):
    monkeypatch.setattr(openlibrary, "lookup", fake_open_library.lookup)
    ana = make_user(name="Ana")

    page = open_shelf(ana)
    by_label(page.text_input, "ISBN of a book you want").input("9780000000000")
    page = click(page, "Add to wishlist")

    assert not page.exception
    assert page.success[0].value == "“A Fixed Open Library Book” is on your wishlist."
    assert [book.title for book in copies_repo.wishlist_books(ana.id)] == ["A Fixed Open Library Book"]


def test_my_shelf_refuses_the_same_wishlist_book_twice(make_user, make_book):
    ana = make_user(name="Ana")
    book = make_book(isbn="9781718502703")
    copies_repo.add_to_wishlist(ana.id, book.id)

    page = open_shelf(ana)
    by_label(page.text_input, "ISBN of a book you want").input("9781718502703")
    page = click(page, "Add to wishlist")

    assert page.error[0].value == "This book is already on your wishlist."
    assert len(copies_repo.wishlist_books(ana.id)) == 1


def test_a_book_can_be_removed_from_the_wishlist_on_my_shelf(make_user, make_book):
    ana = make_user(name="Ana")
    copies_repo.add_to_wishlist(ana.id, make_book(title="Biology").id)

    page = click(open_shelf(ana), "Remove")

    assert page.success[0].value == "“Biology” was removed from your wishlist."
    assert copies_repo.wishlist_books(ana.id) == []
