"""Tests for the Open Library lookup in bookloop/services/openlibrary.py.

Tests never use the internet: each test replaces the one function that would
go online (_get) with a fake that returns a prepared answer or an error.
"""

import httpx
import pytest

from bookloop.services import openlibrary


ISBN = "9781718502703"


def answer(payload=None, status: int = 200, text: str | None = None) -> httpx.Response:
    """A pretend reply from Open Library."""
    request = httpx.Request("GET", openlibrary.API_URL)
    if text is not None:
        return httpx.Response(status, text=text, request=request)
    return httpx.Response(status, json=payload if payload is not None else {}, request=request)


@pytest.fixture
def open_library(monkeypatch):
    """Replace the internet call. Set .reply (a response) or .error (an exception)."""

    class Fake:
        reply = answer({})
        error = None
        calls = []

        def get(self, url, params, timeout):
            self.calls.append({"url": url, "params": params, "timeout": timeout})
            if self.error is not None:
                raise self.error
            return self.reply

    fake = Fake()
    fake.calls = []
    monkeypatch.setattr(openlibrary, "_get", fake.get)
    return fake


def test_fake_open_library_returns_a_fixed_book_without_network(fake_open_library):
    book = fake_open_library.lookup("9780000000000")

    assert book.isbn == "9780000000000"
    assert book.title == "A Fixed Open Library Book"
    assert book.authors == "Example Author"


def test_lookup_finds_the_title_authors_and_cover(open_library):
    open_library.reply = answer({
        f"ISBN:{ISBN}": {
            "title": "Python Crash Course",
            "authors": [{"name": "Eric Matthes", "url": "https://openlibrary.org/authors/x"}],
            "cover": {"small": "https://covers.example/s.jpg", "medium": "https://covers.example/m.jpg"},
        }
    })

    book = openlibrary.lookup(ISBN)

    assert (book.isbn, book.title, book.authors) == (ISBN, "Python Crash Course", "Eric Matthes")
    assert book.cover_url == "https://covers.example/m.jpg"


def test_lookup_asks_for_that_isbn_and_waits_at_most_5_seconds(open_library):
    openlibrary.lookup(ISBN)

    (call,) = open_library.calls
    assert call["params"]["bibkeys"] == f"ISBN:{ISBN}"
    assert call["timeout"] == 5.0


def test_several_authors_are_joined_with_commas(open_library):
    open_library.reply = answer({
        f"ISBN:{ISBN}": {"title": "Algorithms", "authors": [{"name": "A. One"}, {"name": "B. Two"}]}
    })

    assert openlibrary.lookup(ISBN).authors == "A. One, B. Two"


def test_a_book_without_cover_or_authors_still_works(open_library):
    open_library.reply = answer({f"ISBN:{ISBN}": {"title": "Mystery Book"}})

    book = openlibrary.lookup(ISBN)

    assert (book.title, book.authors, book.cover_url) == ("Mystery Book", "Unknown author", None)


def test_an_unknown_isbn_returns_none(open_library):
    open_library.reply = answer({})

    assert openlibrary.lookup(ISBN) is None


def test_open_library_being_down_returns_none(open_library):
    open_library.error = httpx.ConnectError("no connection")

    assert openlibrary.lookup(ISBN) is None


def test_open_library_taking_too_long_returns_none(open_library):
    open_library.error = httpx.ReadTimeout("took more than 5 seconds")

    assert openlibrary.lookup(ISBN) is None


def test_an_error_page_returns_none(open_library):
    open_library.reply = answer(status=500, text="Internal Server Error")

    assert openlibrary.lookup(ISBN) is None


def test_an_answer_that_is_not_json_returns_none(open_library):
    open_library.reply = answer(text="<html>maintenance</html>")

    assert openlibrary.lookup(ISBN) is None
