"""Rules for the wishlist: books a student wants.

When someone lists a book, everyone who has it on their wishlist gets a
notification, except the person who listed it.
"""

from collections.abc import Iterable

from bookloop.models import Profile
from bookloop.rules.decision import Decision


def can_add_to_wishlist(user: Profile, already_wanted: bool) -> Decision:
    """Check whether a book can be added to this user's wishlist."""
    if already_wanted:
        return Decision.no("This book is already on your wishlist.")
    return Decision.yes()


def can_remove_from_wishlist(user: Profile, already_wanted: bool) -> Decision:
    """Check whether a book can be removed from this user's wishlist."""
    if not already_wanted:
        return Decision.no("This book isn't on your wishlist.")
    return Decision.yes()


def people_to_notify(wanted_by: Iterable[str], lister_id: str) -> list[str]:
    """Who to tell that a wanted book was listed: everyone who wants it, except the lister."""
    return [user_id for user_id in dict.fromkeys(wanted_by) if user_id != lister_id]
