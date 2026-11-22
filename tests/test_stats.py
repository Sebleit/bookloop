from sqlalchemy import text

from seed import base, swaps
from bookloop.storage.stats_repo import community_stats, stats_csv


def test_community_stats_counts_listed_copies_and_completed_swaps(
    database, make_user, make_copy, make_loop
):
    alice = make_user(name="Alice")
    make_copy(owner=alice, status="available")
    make_copy(owner=alice, status="unlisted")
    make_loop(status="completed")

    stats = community_stats()

    # make_loop also creates two available demo copies for its offer.
    assert stats["listed_copies"] == 3
    assert stats["completed_swaps"] == 1
    assert stats["average_score"] == 4.0


def test_stats_show_most_wanted_book(database, make_user, make_book):
    alice = make_user(name="Alice")
    book = make_book(title="A, Book")
    with database.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO wishlist (user_id, book_id, created_at) "
                "VALUES (:user_id, :book_id, '2026-11-20T00:00:00Z')"
            ),
            {"user_id": alice.id, "book_id": book.id},
        )

    stats = community_stats()

    assert stats["most_wanted"] == [{"title": "A, Book", "wanted_count": 1}]


def test_empty_stats_have_sensible_values(database):
    stats = community_stats()

    assert stats == {
        "listed_copies": 0,
        "completed_swaps": 0,
        "most_wanted": [],
        "average_score": 0.0,
    }


def test_stats_csv_quotes_titles_with_commas():
    csv_text = stats_csv(
        {
            "listed_copies": 2,
            "completed_swaps": 1,
            "average_score": 4.0,
            "most_wanted": [{"title": "A, Book", "wanted_count": 3}],
        }
    )

    assert '"A, Book",3' in csv_text


def test_demo_swaps_seed_adds_completed_and_pending_loops(database):
    with database.begin() as connection:
        base.seed(connection)
        swaps.seed(connection)
        loop_statuses = connection.execute(
            text("SELECT status FROM loops ORDER BY id")
        ).scalars().all()
        trade_statuses = connection.execute(
            text("SELECT status FROM trades ORDER BY id")
        ).scalars().all()

    assert loop_statuses == ["completed", "scheduled"]
    assert trade_statuses == ["completed", "completed", "pending", "pending"]
