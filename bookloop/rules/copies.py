"""Rules for listing, editing and withdrawing books (copies).

A "book" is a title (one row per ISBN in the books table). A "copy" is one
student's physical book of that title, with its own condition and notes.

A copy's status:
    unlisted  -> available   when the owner lists it (or puts it back)
    available -> unlisted    when the owner withdraws it
    available -> in_round    when it's entered in a swap round
    available -> reserved    when an offer is accepted or a round matches it
Reserved and in-round copies can't be edited or withdrawn: someone is
counting on them.

Like every rule, these functions never use Streamlit or the database.
"""

from bookloop.models import Copy, Profile
from bookloop.rules.decision import Decision


CONDITIONS = {4: "like new", 3: "good", 2: "fair", 1: "poor"}
HIGHLIGHTING = ("none", "light", "heavy")
MAX_NOTES_LENGTH = 500
BUSY_STATUSES = {
    "reserved": "This book is reserved for a swap.",
    "in_round": "This book is in a swap round.",
}


def clean_isbn(isbn: str | None) -> str:
    """Remove spaces and dashes: '978-0-262-04630-5' -> '9780262046305'."""
    return "".join(char for char in (isbn or "") if char.isalnum()).upper()


def is_valid_isbn(isbn: str) -> bool:
    """An ISBN has 10 characters (the last may be X) or 13 digits."""
    if len(isbn) == 13:
        return isbn.isdigit()
    if len(isbn) == 10:
        return isbn[:9].isdigit() and (isbn[9].isdigit() or isbn[9] == "X")
    return False


def check_isbn(isbn: str) -> Decision:
    """Check an ISBN before looking it up."""
    if not is_valid_isbn(clean_isbn(isbn)):
        return Decision.no("An ISBN has 10 or 13 digits, like 9780262046305.")
    return Decision.yes()


def check_book_details(title: str, authors: str) -> Decision:
    """Check the book details typed by hand when Open Library can't find them."""
    if not (title or "").strip():
        return Decision.no("Type the book's title.")
    if not (authors or "").strip():
        return Decision.no("Type the book's author(s).")
    return Decision.yes()


def _check_copy_details(condition: int | None, highlighting: str | None, notes: str | None) -> Decision:
    if condition not in CONDITIONS:
        return Decision.no("Choose the book's condition.")
    if highlighting not in HIGHLIGHTING:
        return Decision.no("Choose how much highlighting the book has.")
    if len((notes or "").strip()) > MAX_NOTES_LENGTH:
        return Decision.no(f"Notes can be at most {MAX_NOTES_LENGTH} characters.")
    return Decision.yes()


def can_add_copy(
    user: Profile,
    condition: int | None,
    highlighting: str | None,
    notes: str | None,
) -> Decision:
    """Check the details of a book a student wants to put on their shelf."""
    if user.status == "suspended":
        return Decision.no("Your account is suspended, so you can't list books.")
    return _check_copy_details(condition, highlighting, notes)


def can_edit(
    user: Profile,
    copy: Copy,
    condition: int | None,
    highlighting: str | None,
    notes: str | None,
) -> Decision:
    """Check a change to a book's condition, highlighting or notes."""
    if copy.owner_id != user.id:
        return Decision.no("You can only edit your own books.")
    if copy.status in BUSY_STATUSES:
        return Decision.no(BUSY_STATUSES[copy.status])
    return _check_copy_details(condition, highlighting, notes)


def can_withdraw(user: Profile, copy: Copy) -> Decision:
    """Check whether the owner can take a book off the shelf (it becomes unlisted)."""
    if copy.owner_id != user.id:
        return Decision.no("You can only withdraw your own books.")
    if copy.status in BUSY_STATUSES:
        return Decision.no(BUSY_STATUSES[copy.status])
    if copy.status == "unlisted":
        return Decision.no("This book is already withdrawn.")
    return Decision.yes()


def can_list(user: Profile, copy: Copy) -> Decision:
    """Check whether the owner can put a withdrawn book back on the shelf."""
    if copy.owner_id != user.id:
        return Decision.no("You can only list your own books.")
    if user.status == "suspended":
        return Decision.no("Your account is suspended, so you can't list books.")
    if copy.status != "unlisted":
        return Decision.no("This book is already on your shelf.")
    return Decision.yes()
