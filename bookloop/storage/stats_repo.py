# Person 2 owns this file: statistics database operations.
import csv
from io import StringIO

from bookloop.storage.reviews_repo import swapper_score
from bookloop.storage.db import transaction
from sqlalchemy import text


def community_stats() -> dict:
    """Return the moderator statistics shown on the Stats page."""
    with transaction() as connection:
        listed_copies = connection.execute(
            text("SELECT COUNT(*) FROM copies WHERE status != 'unlisted'")
        ).scalar_one()
        completed_swaps = connection.execute(
            text("SELECT COUNT(*) FROM loops WHERE status = 'completed'")
        ).scalar_one()
        wanted_rows = connection.execute(
            text(
                "SELECT b.title, COUNT(*) AS wanted_count "
                "FROM wishlist w JOIN books b ON b.id = w.book_id "
                "GROUP BY b.id, b.title "
                "ORDER BY wanted_count DESC, b.title "
                "LIMIT 10"
            )
        ).mappings().all()
        user_ids = connection.execute(
            text("SELECT id FROM profiles WHERE role = 'student'")
        ).scalars().all()

    scores = [swapper_score(user_id).score for user_id in user_ids]
    return {
        "listed_copies": int(listed_copies),
        "completed_swaps": int(completed_swaps),
        "most_wanted": [
            {"title": row["title"], "wanted_count": int(row["wanted_count"])}
            for row in wanted_rows
        ],
        "average_score": round(sum(scores) / len(scores), 2) if scores else 0.0,
    }


def stats_csv(stats: dict | None = None) -> str:
    """Return the moderator statistics as a CSV string."""
    stats = stats or community_stats()
    output = StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["metric", "value"])
    writer.writerow(["listed_copies", stats["listed_copies"]])
    writer.writerow(["completed_swaps", stats["completed_swaps"]])
    writer.writerow(["average_score", stats["average_score"]])
    writer.writerow([])
    writer.writerow(["most_wanted_book", "wishlist_count"])
    for item in stats["most_wanted"]:
        writer.writerow([item["title"], item["wanted_count"]])
    return output.getvalue()
