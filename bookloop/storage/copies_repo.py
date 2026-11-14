# Person 1 owns this file: copy database operations.
from sqlalchemy import text

from bookloop.models import Copy
from bookloop.storage.db import transaction


COPY_STATUSES = {"unlisted", "available", "in_round", "reserved"}


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
