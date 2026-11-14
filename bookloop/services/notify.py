# Person 1 owns this file: send notifications.
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import text as sql_text

from bookloop.models import Notification
from bookloop.storage.db import transaction


def notify(user_id: str, text: str, link: str | None) -> Notification:
    """Add a notification to a user's inbox and return it."""
    notification = Notification(
        id=str(uuid4()),
        user_id=user_id,
        text=text,
        link=link,
        read=False,
        created_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    )
    with transaction() as connection:
        connection.execute(
            sql_text(
                'INSERT INTO notifications (id, user_id, text, link, "read", created_at) '
                "VALUES (:id, :user_id, :text, :link, :read, :created_at)"
            ),
            {
                "id": notification.id,
                "user_id": notification.user_id,
                "text": notification.text,
                "link": notification.link,
                "read": 0,
                "created_at": notification.created_at,
            },
        )
    return notification


def get_notifications(user_id: str) -> list[Notification]:
    """Return the user's notifications, newest first."""
    with transaction() as connection:
        rows = connection.execute(
            sql_text(
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
