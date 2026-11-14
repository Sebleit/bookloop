# Person 1 owns this file: permission checks.
from typing import Any


def is_moderator(user: Any) -> bool:
    """Return whether the user has the moderator role."""
    return getattr(user, "role", None) == "moderator"


def is_active(user: Any) -> bool:
    """Return whether the user's account is active."""
    return getattr(user, "status", None) == "active"
