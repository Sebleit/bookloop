"""My Shelf page: add, edit and withdraw my books, and manage my wishlist.

Adding a book: type the ISBN, and the title, authors and cover fill in from
Open Library. If Open Library doesn't know the ISBN or doesn't answer in
time, a form appears to type the details by hand. Then choose the condition,
highlighting, notes and the courses the book is used in: pick from the
courses other students added, or type a new one, which is then offered to
everyone. Editing a book can change its courses too.
"""

from uuid import uuid4

import streamlit as st

from bookloop import auth
from bookloop.models import Book, Profile
from bookloop.rules.copies import (
    CONDITIONS,
    HIGHLIGHTING,
    can_add_copy,
    can_edit,
    can_list,
    can_withdraw,
    check_book_details,
    check_course_name,
    check_isbn,
    clean_isbn,
    course_label,
)
from bookloop.rules.wishlist import can_add_to_wishlist, can_remove_from_wishlist
from bookloop.services import openlibrary
from bookloop.storage import copies_repo


FLASH_KEY = "shelf_message"
LOOKUP_KEY = "shelf_lookup"
STATUS_LABELS = {
    "available": "On your shelf: others can see it in Browse",
    "unlisted": "Withdrawn: only you can see it",
    "in_round": "In a swap round",
    "reserved": "Reserved for a swap",
}
CONDITION_ORDER = [4, 3, 2, 1]  # like new first


def _flash(kind: str, message: str) -> None:
    """Remember a message, then reload the page so it shows the latest data."""
    st.session_state[FLASH_KEY] = (kind, message)
    st.rerun()


def _show_flash() -> None:
    message = st.session_state.pop(FLASH_KEY, None)
    if message is None:
        return
    kind, text = message
    if kind == "success":
        st.success(text)
        st.toast(text, icon="✅")  # also pops up in the corner, wherever you've scrolled
    else:
        st.error(text)


def _course_picker(selected_ids: list[str] | None = None, key: str | None = None) -> list[str]:
    """Courses other students added, plus anything typed in: returns names."""
    labels = {course.id: course_label(course.code, course.name) for course in copies_repo.list_courses()}
    chosen = st.multiselect(
        "Courses it's used in",
        list(labels.values()),
        default=[labels[course_id] for course_id in (selected_ids or []) if course_id in labels],
        accept_new_options=True,
        placeholder="Pick a course, or type a new one",
        key=key,
    )
    st.caption(
        "These are the courses students have added so far. If yours isn't there, type its "
        "name and press Enter: it will be offered to everyone after you."
    )
    return chosen


def _course_ids(chosen: list[str]) -> tuple[list[str], str | None]:
    """The ids of the chosen courses, adding new ones. Returns (ids, error)."""
    for name in chosen:
        decision = check_course_name(name)
        if not decision.allowed:
            return [], decision.reason
    return [copies_repo.find_or_create_course(name).id for name in chosen], None


def find_book(isbn: str) -> Book | None:
    """Our own saved copy of the book first; only ask Open Library if it's new."""
    return copies_repo.get_book_by_isbn(isbn) or openlibrary.lookup(isbn)


# --- Adding a book ---------------------------------------------------------


def _add_book_section(user: Profile) -> None:
    st.subheader("Add a book")
    with st.form("isbn_form"):
        isbn = st.text_input("ISBN (the number above the barcode)", placeholder="9780262046305")
        looked_up = st.form_submit_button("Look up")
    if looked_up:
        decision = check_isbn(isbn)
        if not decision.allowed:
            st.error(decision.reason)
            return
        clean = clean_isbn(isbn)
        st.session_state[LOOKUP_KEY] = {"isbn": clean, "book": find_book(clean)}

    lookup = st.session_state.get(LOOKUP_KEY)
    if lookup:
        _add_copy_form(user, lookup["isbn"], lookup["book"])


def _add_copy_form(user: Profile, isbn: str, book: Book | None) -> None:
    if book is not None:
        col1, col2 = st.columns([1, 4])
        if book.cover_url:
            col1.image(book.cover_url, width=90)
        col2.write(f"**{book.title}**")
        col2.write(book.authors + (f" · {book.edition} edition" if book.edition else ""))
    else:
        st.info(
            "Open Library doesn't know this ISBN, or didn't answer in time. "
            "Type the book's details yourself."
        )

    with st.form("add_copy_form"):
        title = authors = edition = ""
        if book is None:
            title = st.text_input("Title")
            authors = st.text_input("Author(s)")
            edition = st.text_input("Edition (optional)")
        condition = st.selectbox(
            "Condition", CONDITION_ORDER, index=None, format_func=CONDITIONS.get, placeholder="Choose..."
        )
        highlighting = st.selectbox("Highlighting", HIGHLIGHTING)
        notes = st.text_area("Notes (optional)", max_chars=500)
        chosen_courses = _course_picker()
        submitted = st.form_submit_button("Add to my shelf")
    if not submitted:
        return

    decision = can_add_copy(user, condition, highlighting, notes)
    if book is None:
        details = check_book_details(title, authors)
        if not details.allowed:
            decision = details  # missing title or author is reported first
    if not decision.allowed:
        st.error(decision.reason)
        return

    try:
        course_ids, course_error = _course_ids(chosen_courses)
        if course_error:
            st.error(course_error)
            return
        if book is None:
            book = Book(id=str(uuid4()), isbn=isbn, title=title, authors=authors, edition=edition, cover_url=None)
        saved = copies_repo.save_book(book)
        _, told = copies_repo.add_copy(user.id, saved.id, condition, highlighting, notes, course_ids)
    except Exception:
        st.error("The book could not be saved. Please try again.")
        return

    st.session_state.pop(LOOKUP_KEY, None)
    message = f"“{saved.title}” is on your shelf and visible in Browse."
    if told:
        message += f" {told} student{'s' if told != 1 else ''} who wanted it got a notification."
    _flash("success", message)


# --- My books --------------------------------------------------------------


def _my_books_section(user: Profile) -> None:
    st.subheader("My books")
    items = copies_repo.list_my_copies(user.id)
    if not items:
        st.info("No books yet — add your first one above.")
        return

    for item in items:
        copy, book = item.copy, item.book
        with st.container(border=True):
            col1, col2 = st.columns([1, 4])
            if book.cover_url:
                col1.image(book.cover_url, width=70)
            col2.write(f"**{book.title}** · {book.authors}")
            col2.caption(STATUS_LABELS.get(copy.status, copy.status))
            col2.write(
                f"Condition: {CONDITIONS[copy.condition]} · highlighting: {copy.highlighting}"
                + (f" · {copy.notes}" if copy.notes else "")
            )

            if copy.status == "available" and col2.button("Withdraw", key=f"withdraw_{copy.id}"):
                _change_status(user, copy, "unlisted")
            if copy.status == "unlisted" and col2.button("Put back on my shelf", key=f"list_{copy.id}"):
                _change_status(user, copy, "available")
            if copy.status in ("available", "unlisted"):
                _edit_form(user, copy)


def _change_status(user: Profile, copy, new_status: str) -> None:
    decision = can_withdraw(user, copy) if new_status == "unlisted" else can_list(user, copy)
    if not decision.allowed:
        st.error(decision.reason)
        return
    try:
        copies_repo.set_copy_status(copy.id, new_status)
    except Exception:
        st.error("The book could not be updated. Please try again.")
        return
    done = "Your book was withdrawn." if new_status == "unlisted" else "Your book is back on your shelf."
    _flash("success", done)


def _edit_form(user: Profile, copy) -> None:
    with st.expander("Edit"):
        with st.form(f"edit_form_{copy.id}"):
            condition = st.selectbox(
                "Condition", CONDITION_ORDER, index=CONDITION_ORDER.index(copy.condition),
                format_func=CONDITIONS.get,
            )
            highlighting = st.selectbox("Highlighting", HIGHLIGHTING, index=HIGHLIGHTING.index(copy.highlighting))
            notes = st.text_area("Notes", value=copy.notes or "", max_chars=500)
            chosen_courses = _course_picker(copies_repo.book_course_ids(copy.book_id), key=f"courses_{copy.id}")
            st.caption("Courses belong to the book, so they change for everyone who has a copy of it.")
            submitted = st.form_submit_button("Save changes")
    if not submitted:
        return
    decision = can_edit(user, copy, condition, highlighting, notes)
    if not decision.allowed:
        st.error(decision.reason)
        return
    course_ids, course_error = _course_ids(chosen_courses)
    if course_error:
        st.error(course_error)
        return
    try:
        copies_repo.update_copy(copy.id, condition, highlighting, notes)
        copies_repo.set_book_courses(copy.book_id, course_ids)
    except Exception:
        st.error("Your changes could not be saved. Please try again.")
        return
    _flash("success", "Your changes are saved.")


# --- Wishlist --------------------------------------------------------------


def _wishlist_section(user: Profile) -> None:
    st.subheader("My wishlist")
    st.caption("Add books you want: you'll get a notification when someone lists one.")

    for book in copies_repo.wishlist_books(user.id):
        col1, col2 = st.columns([4, 1])
        col1.write(f"**{book.title}** · {book.authors}")
        if col2.button("Remove", key=f"unwish_{book.id}"):
            _remove_wish(user, book)

    with st.form("wishlist_form"):
        isbn = st.text_input("ISBN of a book you want")
        st.caption("If Open Library can't find it, also type the title and author.")
        title = st.text_input("Title (only if needed)")
        authors = st.text_input("Author(s) (only if needed)")
        submitted = st.form_submit_button("Add to wishlist")
    if submitted:
        _add_wish(user, isbn, title, authors)


def _add_wish(user: Profile, isbn: str, title: str, authors: str) -> None:
    decision = check_isbn(isbn)
    if not decision.allowed:
        st.error(decision.reason)
        return
    clean = clean_isbn(isbn)
    book = find_book(clean)
    if book is None:
        decision = check_book_details(title, authors)
        if not decision.allowed:
            st.error("Open Library doesn't know this ISBN. " + decision.reason)
            return
        book = Book(id=str(uuid4()), isbn=clean, title=title, authors=authors, edition=None, cover_url=None)
    try:
        saved = copies_repo.save_book(book)
        decision = can_add_to_wishlist(user, copies_repo.is_on_wishlist(user.id, saved.id))
        if not decision.allowed:
            st.error(decision.reason)
            return
        copies_repo.add_to_wishlist(user.id, saved.id)
    except Exception:
        st.error("Your wishlist could not be updated. Please try again.")
        return
    _flash("success", f"“{saved.title}” is on your wishlist.")


def _remove_wish(user: Profile, book: Book) -> None:
    decision = can_remove_from_wishlist(user, copies_repo.is_on_wishlist(user.id, book.id))
    if not decision.allowed:
        st.error(decision.reason)
        return
    copies_repo.remove_from_wishlist(user.id, book.id)
    _flash("success", f"“{book.title}” was removed from your wishlist.")


# --- The page --------------------------------------------------------------


def main() -> None:
    user = auth.current_user()
    st.title("My Shelf")
    _show_flash()
    try:
        _add_book_section(user)
        _my_books_section(user)
        _wishlist_section(user)
    except Exception:
        st.error("My Shelf is unavailable right now. Please try again later.")


if __name__ == "__main__":
    main()
