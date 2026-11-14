# Person 1 owns this file: send notifications.
from sqlalchemy import text

from bookloop.models import Notification
from bookloop.storage.db import transaction


def get_notifications(user_id: str) -> list[Notification]:
    """Return the user's notifications, newest first."""
    with transaction() as connection:
        rows = connection.execute(
            text(
                'SELECT id, user_id, text, link, "read", created_at '
                "FROM notifications WHERE user_id = :user_id "
                "ORDER BY created_at DESC, id"
            ),
            {"user_id": user_id},
        ).mappings()
        return [
            Notification(
                id=row["id"],
                user_id=row["user_id"],
                text=row["text"],
                link=row["link"],
                read=bool(row["read"]),
                created_at=row["created_at"],
            )
            for row in rows
        ]
