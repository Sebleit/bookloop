"""Tests for listing books: the rules in bookloop/rules/copies.py, saving in
copies_repo.py, and the My Shelf and Browse pages.

Users, books and copies come from the shared factories in conftest.py.
Open Library is always replaced by a fake, so no test uses the internet.
"""

from copy import deepcopy
from pathlib import Path

import pytest
from sqlalchemy import text
from streamlit.testing.v1 import AppTest

from bookloop.models import Book
from bookloop.rules.copies import (
    can_add_copy,
    can_edit,
    can_list,
    can_withdraw,
    check_book_details,
    check_isbn,
    clean_isbn,
)
from bookloop.services import openlibrary
from bookloop.storage import copies_repo, db


# --- ISBNs and book details ------------------------------------------------


def test_isbns_with_dashes_and_spaces_are_cleaned():
    assert clean_isbn(" 978-1-7185-0270-3 ") == "9781718502703"
    assert clean_isbn("080442957x") == "080442957X"


def test_13_digit_and_10_character_isbns_are_accepted():
    assert check_isbn("978-1-7185-0270-3").allowed is True
    assert check_isbn("080442957X").allowed is True


def test_wrong_isbns_are_refused():
    for wrong in ["", "12345", "97817185027031", "abcdefghij"]:
        assert check_isbn(wrong).reason == "An ISBN has 10 or 13 digits, like 9780262046305."


def test_typed_book_details_need_a_title_and_an_author():
    assert check_book_details("Calculus", "James Stewart").allowed is True
    assert check_book_details("  ", "James Stewart").reason == "Type the book's title."
    assert check_book_details("Calculus", "").reason == "Type the book's author(s)."


# --- Adding a copy ---------------------------------------------------------


def test_a_student_can_add_a_copy_with_all_details(make_user):
    ana = make_user(name="Ana")

    assert can_add_copy(ana, condition=4, highlighting="none", notes="Like new").allowed is True


def test_a_copy_without_a_condition_is_refused(make_user):
    ana = make_user(name="Ana")

    decision = can_add_copy(ana, condition=None, highlighting="none", notes=None)

    assert decision.reason == "Choose the book's condition."


def test_wrong_highlighting_and_long_notes_are_refused(make_user):
    ana = make_user(name="Ana")

    assert can_add_copy(ana, 3, "some", None).reason == "Choose how much highlighting the book has."
    assert can_add_copy(ana, 3, "none", "x" * 501).reason == "Notes can be at most 500 characters."
    assert can_add_copy(ana, 3, "none", "x" * 500).allowed is True


def test_a_suspended_student_cannot_list_books(make_user):
    dina = make_user(name="Dina", status="suspended")

    assert can_add_copy(dina, 3, "none", None).allowed is False


# --- Editing, withdrawing and listing again --------------------------------


def test_the_owner_can_edit_an_available_book(make_user, make_copy):
    ana = make_user(name="Ana")
    copy = make_copy(owner=ana)

    assert can_edit(ana, copy, 2, "light", "Coffee stain on the cover").allowed is True


def test_cannot_edit_someone_elses_book_and_it_is_unchanged(make_user, make_copy):
    ana, ben = make_user(name="Ana"), make_user(name="Ben")
    bens_copy = make_copy(owner=ben)
    before = deepcopy(bens_copy)

    decision = can_edit(ana, bens_copy, 1, "heavy", None)

    assert decision.reason == "You can only edit your own books."
    assert copies_repo.get_copy(bens_copy.id) == before


def test_cannot_edit_a_book_someone_is_counting_on(make_user, make_copy):
    ana = make_user(name="Ana")

    reserved = can_edit(ana, make_copy(owner=ana, status="reserved"), 3, "none", None)
    in_round = can_edit(ana, make_copy(owner=ana, status="in_round"), 3, "none", None)

    assert reserved.reason == "This book is reserved for a swap."
    assert in_round.reason == "This book is in a swap round."


def test_owner_can_withdraw_available_book(make_user, make_copy):
    ana = make_user(name="Ana")

    assert can_withdraw(ana, make_copy(owner=ana)).allowed is True


def test_cannot_withdraw_someone_elses_book(make_user, make_copy):
    ana, ben = make_user(name="Ana"), make_user(name="Ben")

    assert can_withdraw(ana, make_copy(owner=ben)).allowed is False


def test_cannot_withdraw_reserved_book(make_user, make_copy):
    ana = make_user(name="Ana")
    copy = make_copy(owner=ana, status="reserved")

    assert can_withdraw(ana, copy).allowed is False


def test_cannot_withdraw_a_book_twice_or_while_it_is_in_a_round(make_user, make_copy):
    ana = make_user(name="Ana")

    assert can_withdraw(ana, make_copy(owner=ana, status="unlisted")).reason == "This book is already withdrawn."
    assert can_withdraw(ana, make_copy(owner=ana, status="in_round")).allowed is False


def test_a_withdrawn_book_can_be_put_back_on_the_shelf(make_user, make_copy):
    ana = make_user(name="Ana")

    assert can_list(ana, make_copy(owner=ana, status="unlisted")).allowed is True
    assert can_list(ana, make_copy(owner=ana)).reason == "This book is already on your shelf."
    assert can_list(ana, make_copy(owner=make_user(name="Ben"), status="unlisted")).allowed is False


# --- Saving books and copies -----------------------------------------------


def a_book(isbn: str = "9781718502703", title: str = "Python Crash Course") -> Book:
    return Book(id=f"book-{isbn}", isbn=isbn, title=title, authors="Eric Matthes", edition="3rd", cover_url=None)


def add_course(code: str = "NOVA101", name: str = "Introduction to Programming") -> str:
    course_id = f"course-{code}"
    with db.transaction() as connection:
        connection.execute(
            text("INSERT INTO courses (id, code, name) VALUES (:id, :code, :name)"),
            {"id": course_id, "code": code, "name": name},
        )
    return course_id


def test_a_book_is_saved_once_per_isbn():
    first = copies_repo.save_book(a_book())
    second = copies_repo.save_book(Book(id="another-id", isbn=first.isbn, title="Other", authors="X",
                                        edition=None, cover_url=None))

    assert second == first
    assert copies_repo.get_book_by_isbn("9781718502703").title == "Python Crash Course"


def test_adding_a_copy_puts_it_on_the_shelf_with_its_courses(make_user):
    ana = make_user(name="Ana")
    book = copies_repo.save_book(a_book())
    course = add_course()

    copy, told = copies_repo.add_copy(ana.id, book.id, 4, "none", "  Barely used  ", [course])

    assert (copy.status, copy.notes, told) == ("available", "Barely used", 0)
    (item,) = copies_repo.search_available("python")
    assert item.courses == ["NOVA101"]


def test_editing_a_copy_saves_the_new_details(make_user, make_copy):
    copy = make_copy(owner=make_user(name="Ana"), condition=4)

    copies_repo.update_copy(copy.id, 2, "heavy", "Pages folded")

    saved = copies_repo.get_copy(copy.id)
    assert (saved.condition, saved.highlighting, saved.notes) == (2, "heavy", "Pages folded")


def test_my_shelf_lists_all_my_books_whatever_their_status(make_user, make_copy):
    ana = make_user(name="Ana")
    for status in ("available", "unlisted", "reserved"):
        make_copy(owner=ana, status=status)
    make_copy(owner=make_user(name="Ben"))

    assert sorted(item.copy.status for item in copies_repo.list_my_copies(ana.id)) == [
        "available", "reserved", "unlisted"
    ]


# --- Searching (Browse) ----------------------------------------------------


@pytest.fixture
def shelf(make_user, make_book, make_copy):
    """Ben and Carla offer three books; Ana is the one browsing."""
    ana, ben, carla = make_user(name="Ana"), make_user(name="Ben"), make_user(name="Carla")
    stats = make_book(title="Statistics for Business", authors="David Levine", isbn="9780134685106")
    python = make_book(title="Python Crash Course", authors="Eric Matthes", isbn="9781718502703")
    make_copy(owner=ben, book=stats, condition=2)
    make_copy(owner=carla, book=python, condition=4)
    make_copy(owner=carla, book=stats, condition=4, status="reserved")  # not available
    make_copy(owner=ana, book=python)  # Ana's own copy
    course = add_course()
    with db.transaction() as connection:
        connection.execute(
            text("INSERT INTO book_courses (book_id, course_id) VALUES (:book, :course)"),
            {"book": python.id, "course": course},
        )
    return ana, course


def titles(items) -> list[str]:
    return [item.book.title for item in items]


def test_browse_shows_only_other_peoples_available_books(shelf):
    ana, _ = shelf

    assert titles(copies_repo.search_available(exclude_owner_id=ana.id)) == [
        "Python Crash Course", "Statistics for Business"
    ]


def test_search_matches_title_author_or_isbn_ignoring_case(shelf):
    ana, _ = shelf

    assert titles(copies_repo.search_available("STATISTICS", exclude_owner_id=ana.id)) == ["Statistics for Business"]
    assert titles(copies_repo.search_available("matthes", exclude_owner_id=ana.id)) == ["Python Crash Course"]
    assert titles(copies_repo.search_available("978-1-7185", exclude_owner_id=ana.id)) == ["Python Crash Course"]
    assert copies_repo.search_available("chemistry", exclude_owner_id=ana.id) == []


def test_filters_for_course_and_minimum_condition(shelf):
    ana, course = shelf

    assert titles(copies_repo.search_available(course_id=course, exclude_owner_id=ana.id)) == ["Python Crash Course"]
    assert titles(copies_repo.search_available(min_condition=3, exclude_owner_id=ana.id)) == ["Python Crash Course"]


def test_wildcard_characters_in_a_search_do_not_match_everything(shelf):
    ana, _ = shelf

    assert copies_repo.search_available("%%", exclude_owner_id=ana.id) == []
    assert copies_repo.search_available("_", exclude_owner_id=ana.id) == []
    assert copies_repo.search_available("100%", exclude_owner_id=ana.id) == []


# === The pages ===============================================================


ROOT = Path(__file__).resolve().parents[1]


def open_page(page_file: str, user) -> AppTest:
    page = AppTest.from_file(str(ROOT / "pages" / page_file), default_timeout=30)
    page.session_state["current_user"] = user
    page.session_state["_auth_mode"] = "laptop"
    return page.run()


def by_label(widgets, label):
    return next(widget for widget in widgets if widget.label == label)


def click(page, label):
    return next(button for button in page.button if button.label == label).click().run()


@pytest.fixture
def fake_lookup(monkeypatch, fake_open_library):
    """Make My Shelf use the fake Open Library. Set .found = False for "not found"."""

    class Lookup:
        found = True
        calls = []

        def __call__(self, isbn):
            self.calls.append(isbn)
            return fake_open_library.lookup(isbn) if self.found else None

    lookup = Lookup()
    lookup.calls = []
    monkeypatch.setattr(openlibrary, "lookup", lookup)
    return lookup


def test_my_shelf_lists_a_book_found_on_open_library(make_user, fake_lookup):
    ana = make_user(name="Ana")

    page = open_page("2_My_Shelf.py", ana)
    page.text_input[0].input("978-0-00-000000-0")
    page = click(page, "Look up")
    assert "**A Fixed Open Library Book**" in [text.value for text in page.markdown]
    by_label(page.selectbox, "Condition").set_value(4)
    page = click(page, "Add to my shelf")

    assert not page.exception
    assert page.success[0].value.startswith("“A Fixed Open Library Book” is on your shelf")
    (item,) = copies_repo.list_my_copies(ana.id)
    assert (item.book.isbn, item.copy.condition, item.copy.status) == ("9780000000000", 4, "available")


def test_an_isbn_already_saved_is_not_looked_up_again(make_user, fake_lookup):
    copies_repo.save_book(a_book())

    page = open_page("2_My_Shelf.py", make_user(name="Ana"))
    page.text_input[0].input("9781718502703")
    click(page, "Look up")

    assert fake_lookup.calls == []


def test_my_shelf_shows_a_manual_form_when_open_library_cannot_help(make_user, fake_lookup):
    fake_lookup.found = False
    ana = make_user(name="Ana")

    page = open_page("2_My_Shelf.py", ana)
    page.text_input[0].input("9789999999999")
    page = click(page, "Look up")
    assert page.info[0].value.startswith("Open Library doesn't know this ISBN")
    by_label(page.text_input, "Title").input("Lecture Notes in Finance")
    by_label(page.text_input, "Author(s)").input("Nova SBE")
    by_label(page.selectbox, "Condition").set_value(3)
    page = click(page, "Add to my shelf")

    assert not page.exception
    (item,) = copies_repo.list_my_copies(ana.id)
    assert (item.book.title, item.book.authors) == ("Lecture Notes in Finance", "Nova SBE")


def test_my_shelf_refuses_a_book_without_a_condition_and_saves_nothing(make_user, fake_lookup):
    ana = make_user(name="Ana")

    page = open_page("2_My_Shelf.py", ana)
    page.text_input[0].input("9780000000000")
    page = click(page, "Look up")
    page = click(page, "Add to my shelf")

    assert page.error[0].value == "Choose the book's condition."
    assert copies_repo.list_my_copies(ana.id) == []


def test_my_shelf_can_withdraw_a_book(make_user, make_copy):
    ana = make_user(name="Ana")
    copy = make_copy(owner=ana)

    page = click(open_page("2_My_Shelf.py", ana), "Withdraw")

    assert page.success[0].value == "Your book was withdrawn."
    assert copies_repo.get_copy(copy.id).status == "unlisted"


def test_my_shelf_shows_a_sensible_message_when_empty(make_user):
    page = open_page("2_My_Shelf.py", make_user(name="Ana"))

    assert "No books yet — add your first one above." in [info.value for info in page.info]


def test_browse_shows_books_with_the_owners_score(shelf):
    ana, _ = shelf

    page = open_page("1_Browse.py", ana)

    assert not page.exception
    assert page.caption[0].value == "2 books available"
    assert any("Offered by **Carla** · ★ 4.00 · New" == text.value for text in page.markdown)


def test_browse_search_box_narrows_the_list(shelf):
    ana, _ = shelf

    page = open_page("1_Browse.py", ana)
    page.text_input[0].input("statistics").run()

    assert page.caption[0].value == "1 book available"


def test_browse_shows_a_sensible_message_when_nothing_matches(shelf):
    ana, _ = shelf

    page = open_page("1_Browse.py", ana)
    page.text_input[0].input("quantum chemistry").run()

    assert page.info[0].value.startswith("No books match your search.")
