# Tests for database setup and transactions.
import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from bookloop.storage import db


TABLES = {
    "profiles",
    "books",
    "courses",
    "book_courses",
    "copies",
    "wishlist",
    "notifications",
    "offers",
    "loops",
    "trades",
    "rounds",
    "round_entries",
    "round_wants",
    "reviews",
    "entity_ids",
    "audit_log",
}


def test_migration_builds_every_table_in_temporary_sqlite_database(database):
    assert set(inspect(database).get_table_names()) == TABLES


def test_transaction_commits_all_changes(database, make_user):
    user = make_user(name="Ana", id="user-1")

    with database.connect() as connection:
        result = connection.execute(
            text("SELECT display_name FROM profiles WHERE id = 'user-1'")
        ).scalar_one()

    assert result == user.display_name


def test_transaction_rolls_back_all_changes_when_one_fails(database):
    with pytest.raises(IntegrityError):
        with db.transaction() as connection:
            connection.execute(
                text("INSERT INTO books (id, isbn, title, authors) VALUES ('book-1', '1', 'A', 'B')")
            )
            connection.execute(
                text(
                    "INSERT INTO copies "
                    "(id, book_id, owner_id, \"condition\", highlighting, status, created_at) "
                    "VALUES ('copy-1', 'book-1', 'missing-user', 3, 'none', 'available', 'now')"
                )
            )

    with database.connect() as connection:
        book_count = connection.execute(
            text("SELECT COUNT(*) FROM books WHERE id = 'book-1'")
        ).scalar_one()

    assert book_count == 0


def test_audit_target_must_exist_in_the_typed_id_registry(database, make_user, make_book):
    user = make_user(name="Ana", id="user-1")
    book = make_book(id="book-1")
    with database.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO entity_ids (table_name, entity_key) "
                "VALUES ('profiles', 'user-1')"
            )
        )

    with pytest.raises(IntegrityError):
        with db.transaction() as connection:
            connection.execute(
                text(
                    "INSERT INTO audit_log "
                    "(id, actor_id, action, target_table, target_id, created_at) "
                    "VALUES ('audit-1', 'user-1', 'edit', 'books', 'missing-book', 'now')"
                )
            )

    with database.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO entity_ids (table_name, entity_key) "
                "VALUES (:table_name, :entity_key)"
            ),
            {"table_name": "books", "entity_key": book.id},
        )
        connection.execute(
            text(
                "INSERT INTO audit_log "
                "(id, actor_id, action, target_table, target_id, created_at) "
                "VALUES ('audit-2', :actor_id, 'edit', 'books', :target_id, 'now')"
            ),
            {"actor_id": user.id, "target_id": book.id},
        )


def test_postgresql_url_uses_psycopg_driver():
    assert db._normalise_database_url("postgresql://db.example/bookloop") == (
        "postgresql+psycopg://db.example/bookloop"
    )
