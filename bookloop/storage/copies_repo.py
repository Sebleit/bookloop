"""Saving and loading books, copies, courses and wishlists.

get_copy() and set_copy_status() are shared functions that other parts of the
app use: their names, inputs and outputs never change. This file never decides
whether something is allowed: the pages ask the rules first.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import text

from bookloop.models import Book, Copy, Course
from bookloop.rules.wishlist import people_to_notify
from bookloop.services.notify import notify
from bookloop.storage.db import transaction


COPY_STATUSES = {"unlisted", "available", "in_round", "reserved"}
COPY_COLUMNS = 'c.id, c.book_id, c.owner_id, c."condition", c.highlighting, c.notes, c.status, c.created_at'
BOOK_COLUMNS = "b.id AS b_id, b.isbn, b.title, b.authors, b.edition, b.cover_url"


@dataclass(frozen=True)
class ShelfItem:
    """One of the user's own copies, with its book."""

    copy: Copy
    book: Book


@dataclass(frozen=True)
class BrowseItem:
    """An available copy someone else owns, with what Browse shows about it."""

    copy: Copy
    book: Book
    owner_name: str
    courses: list[str]


def _now_text() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _copy(row) -> Copy:
    return Copy(
        id=row["id"],
        book_id=row["book_id"],
        owner_id=row["owner_id"],
        condition=row["condition"],
        highlighting=row["highlighting"],
        notes=row["notes"],
        status=row["status"],
        created_at=row["created_at"],
    )


def _book(row, id_key: str = "id") -> Book:
    return Book(
        id=row[id_key],
        isbn=row["isbn"],
        title=row["title"],
        authors=row["authors"],
        edition=row["edition"],
        cover_url=row["cover_url"],
    )


# --- Shared functions (don't change their names, inputs or outputs) -------


def get_copy(id: str) -> Copy | None:
    """Get one copy by ID, or return None when it does not exist."""
    with transaction() as connection:
        row = connection.execute(
            text(
                'SELECT id, book_id, owner_id, "condition", highlighting, notes, '
                "status, created_at FROM copies WHERE id = :copy_id"
            ),
            {"copy_id": id},
        ).mappings().first()

    if row is None:
        return None
    return Copy(
        id=row["id"],
        book_id=row["book_id"],
        owner_id=row["owner_id"],
        condition=row["condition"],
        highlighting=row["highlighting"],
        notes=row["notes"],
        status=row["status"],
        created_at=row["created_at"],
    )


def set_copy_status(id: str, status: str) -> None:
    """Set a copy's status, raising ValueError for invalid status or unknown ID."""
    if status not in COPY_STATUSES:
        raise ValueError(f"Unknown copy status: {status}")

    with transaction() as connection:
        result = connection.execute(
            text("UPDATE copies SET status = :status WHERE id = :copy_id"),
            {"status": status, "copy_id": id},
        )
        if result.rowcount == 0:
            raise ValueError(f"Copy not found: {id}")


# --- Books and courses -----------------------------------------------------


def get_book_by_isbn(isbn: str) -> Book | None:
    """The book with this ISBN, if someone already looked it up or listed it."""
    with transaction() as connection:
        row = connection.execute(
            text("SELECT id, isbn, title, authors, edition, cover_url FROM books WHERE isbn = :isbn"),
            {"isbn": isbn},
        ).mappings().first()
    return _book(row) if row else None


def save_book(book: Book) -> Book:
    """Save a book's details, so the same ISBN is never looked up twice.

    If the ISBN is already saved, the saved book is returned instead.
    """
    with transaction() as connection:
        connection.execute(
            text(
                "INSERT INTO books (id, isbn, title, authors, edition, cover_url) "
                "VALUES (:id, :isbn, :title, :authors, :edition, :cover_url) "
                "ON CONFLICT (isbn) DO NOTHING"
            ),
            {
                "id": book.id,
                "isbn": book.isbn,
                "title": book.title.strip(),
                "authors": book.authors.strip(),
                "edition": (book.edition or "").strip() or None,
                "cover_url": book.cover_url,
            },
        )
    return get_book_by_isbn(book.isbn)


def list_courses() -> list[Course]:
    with transaction() as connection:
        rows = connection.execute(text("SELECT id, code, name FROM courses ORDER BY code")).mappings().all()
    return [Course(**row) for row in rows]


# --- Copies ----------------------------------------------------------------


def add_copy(
    owner_id: str,
    book_id: str,
    condition: int,
    highlighting: str,
    notes: str | None,
    course_ids: list[str],
) -> tuple[Copy, int]:
    """Put a book on the owner's shelf (available), link its courses, and tell
    everyone who wants it. Returns the copy and how many people were told."""
    copy = Copy(
        id=str(uuid4()),
        book_id=book_id,
        owner_id=owner_id,
        condition=condition,
        highlighting=highlighting,
        notes=(notes or "").strip() or None,
        status="available",
        created_at=_now_text(),
    )
    with transaction() as connection:
        connection.execute(
            text(
                'INSERT INTO copies (id, book_id, owner_id, "condition", highlighting, notes, '
                "status, created_at) VALUES (:id, :book_id, :owner_id, :condition, "
                ":highlighting, :notes, :status, :created_at)"
            ),
            copy.__dict__,
        )
        for course_id in dict.fromkeys(course_ids):
            connection.execute(
                text(
                    "INSERT INTO book_courses (book_id, course_id) VALUES (:book, :course) "
                    "ON CONFLICT DO NOTHING"
                ),
                {"book": book_id, "course": course_id},
            )
        wanted_by = connection.execute(
            text("SELECT user_id FROM wishlist WHERE book_id = :book ORDER BY created_at"),
            {"book": book_id},
        ).scalars().all()
        title = connection.execute(
            text("SELECT title FROM books WHERE id = :book"), {"book": book_id}
        ).scalar_one()
        owner_name = connection.execute(
            text("SELECT display_name FROM profiles WHERE id = :owner"), {"owner": owner_id}
        ).scalar_one()

    to_notify = people_to_notify(wanted_by, owner_id)
    for user_id in to_notify:
        notify(
            user_id,
            f"“{title}” from your wishlist was just listed by {owner_name}. Find it in Browse.",
            None,
        )
    return copy, len(to_notify)


def update_copy(copy_id: str, condition: int, highlighting: str, notes: str | None) -> None:
    """Change a copy's condition, highlighting and notes."""
    with transaction() as connection:
        result = connection.execute(
            text(
                'UPDATE copies SET "condition" = :condition, highlighting = :highlighting, '
                "notes = :notes WHERE id = :id"
            ),
            {
                "condition": condition,
                "highlighting": highlighting,
                "notes": (notes or "").strip() or None,
                "id": copy_id,
            },
        )
        if result.rowcount != 1:
            raise ValueError("Book not found.")


def list_my_copies(owner_id: str) -> list[ShelfItem]:
    """All of a user's copies, whatever their status, newest first."""
    with transaction() as connection:
        rows = connection.execute(
            text(
                f"SELECT {COPY_COLUMNS}, {BOOK_COLUMNS} FROM copies c "
                "JOIN books b ON b.id = c.book_id "
                "WHERE c.owner_id = :owner ORDER BY c.created_at DESC, c.id"
            ),
            {"owner": owner_id},
        ).mappings().all()
    return [ShelfItem(copy=_copy(row), book=_book(row, "b_id")) for row in rows]


def search_available(
    query: str = "",
    course_id: str | None = None,
    min_condition: int | None = None,
    exclude_owner_id: str | None = None,
) -> list[BrowseItem]:
    """Available copies matching the search, for Browse.

    query matches the title, the authors or the ISBN (ignoring upper/lower case).
    """
    filters = ["c.status = 'available'"]
    params: dict = {}
    words = query.strip().lower()
    isbn_part = "".join(char for char in words if char.isalnum()).upper()
    if words:
        # % and _ are wildcards in LIKE: escape them so they match themselves.
        escaped = words.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        match = "LOWER(b.title) LIKE :q ESCAPE '\\' OR LOWER(b.authors) LIKE :q ESCAPE '\\'"
        if isbn_part:
            match += " OR b.isbn LIKE :isbn"
            params["isbn"] = f"%{isbn_part}%"
        filters.append(f"({match})")
        params["q"] = f"%{escaped}%"
    if course_id:
        filters.append(
            "EXISTS (SELECT 1 FROM book_courses bc WHERE bc.book_id = b.id AND bc.course_id = :course)"
        )
        params["course"] = course_id
    if min_condition:
        filters.append('c."condition" >= :min_condition')
        params["min_condition"] = min_condition
    if exclude_owner_id:
        filters.append("c.owner_id != :me")
        params["me"] = exclude_owner_id

    with transaction() as connection:
        rows = connection.execute(
            text(
                f"SELECT {COPY_COLUMNS}, {BOOK_COLUMNS}, p.display_name FROM copies c "
                "JOIN books b ON b.id = c.book_id JOIN profiles p ON p.id = c.owner_id "
                f"WHERE {' AND '.join(filters)} ORDER BY b.title, c.\"condition\" DESC, c.id"
            ),
            params,
        ).mappings().all()
        course_rows = connection.execute(
            text(
                "SELECT bc.book_id, co.code FROM book_courses bc "
                "JOIN courses co ON co.id = bc.course_id ORDER BY co.code"
            )
        ).mappings().all()

    courses: dict[str, list[str]] = {}
    for row in course_rows:
        courses.setdefault(row["book_id"], []).append(row["code"])
    return [
        BrowseItem(
            copy=_copy(row),
            book=_book(row, "b_id"),
            owner_name=row["display_name"],
            courses=courses.get(row["b_id"], []),
        )
        for row in rows
    ]


# --- Wishlist --------------------------------------------------------------


def wishlist_books(user_id: str) -> list[Book]:
    """The books on a user's wishlist, most recently added first."""
    with transaction() as connection:
        rows = connection.execute(
            text(
                "SELECT b.id, b.isbn, b.title, b.authors, b.edition, b.cover_url "
                "FROM wishlist w JOIN books b ON b.id = w.book_id "
                "WHERE w.user_id = :user ORDER BY w.created_at DESC, b.title"
            ),
            {"user": user_id},
        ).mappings().all()
    return [_book(row) for row in rows]


def is_on_wishlist(user_id: str, book_id: str) -> bool:
    with transaction() as connection:
        return connection.execute(
            text("SELECT COUNT(*) FROM wishlist WHERE user_id = :user AND book_id = :book"),
            {"user": user_id, "book": book_id},
        ).scalar_one() > 0


def add_to_wishlist(user_id: str, book_id: str) -> None:
    with transaction() as connection:
        connection.execute(
            text("INSERT INTO wishlist (user_id, book_id, created_at) VALUES (:user, :book, :at)"),
            {"user": user_id, "book": book_id, "at": _now_text()},
        )


def remove_from_wishlist(user_id: str, book_id: str) -> None:
    with transaction() as connection:
        connection.execute(
            text("DELETE FROM wishlist WHERE user_id = :user AND book_id = :book"),
            {"user": user_id, "book": book_id},
        )
