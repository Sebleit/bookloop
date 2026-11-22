"""Look up a book's title, authors and cover on Open Library from its ISBN.

Open Library is a free online book catalogue. Asking another website for data
like this is called using an API. We ask:

    https://openlibrary.org/api/books?bibkeys=ISBN:<isbn>&format=json&jscmd=data

If Open Library doesn't know the ISBN, is down, or takes more than 5 seconds,
lookup() returns None and the page shows a form to type the details by hand.
So listing a book still works when Open Library doesn't.

This service never touches the database. To avoid asking twice for the same
ISBN, the page first looks for the book in our own books table, and only asks
Open Library if it isn't there yet (then saves what it finds).
"""

from uuid import uuid4

import httpx

from bookloop.models import Book


API_URL = "https://openlibrary.org/api/books"
TIMEOUT_SECONDS = 5.0


def _get(url: str, params: dict, timeout: float) -> httpx.Response:
    """The one place that goes on the internet (tests replace it with a fake)."""
    return httpx.get(url, params=params, timeout=timeout)


def lookup(isbn: str) -> Book | None:
    """Return the book for this ISBN, or None if Open Library can't tell us."""
    key = f"ISBN:{isbn}"
    try:
        response = _get(API_URL, {"bibkeys": key, "format": "json", "jscmd": "data"}, TIMEOUT_SECONDS)
        response.raise_for_status()
        data = response.json().get(key)
    except (httpx.HTTPError, ValueError, AttributeError):
        return None  # down, too slow, an error page, or an answer we can't read

    if not isinstance(data, dict) or not data.get("title"):
        return None  # Open Library doesn't know this ISBN

    authors = ", ".join(
        author.get("name", "") for author in data.get("authors", []) if author.get("name")
    )
    cover = data.get("cover") or {}
    return Book(
        id=str(uuid4()),
        isbn=isbn,
        title=data["title"],
        authors=authors or "Unknown author",
        edition=data.get("edition_name") or None,
        cover_url=cover.get("medium") or cover.get("small"),
    )
