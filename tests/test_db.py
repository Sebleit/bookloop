# Person 1 owns this file: tests for database setup and transactions.
from pathlib import Path

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


@pytest.fixture
def temporary_database(tmp_path, monkeypatch):
    database_path = tmp_path / "bookloop-test.sqlite"
    engine = db._create_engine(f"sqlite:///{database_path.as_posix()}")
    migration_path = (
        Path(__file__).resolve().parents[1] / "db" / "migrations" / "001_init.sql"
    )
    migration = migration_path.read_text(encoding="utf-8")

    with engine.begin() as connection:
        for statement in migration.split(";"):
            if statement.strip():
                connection.exec_driver_sql(statement)

    monkeypatch.setattr(db, "engine", engine)
    yield engine
    engine.dispose()


def test_migration_builds_every_table_in_temporary_sqlite_database(temporary_database):
    assert set(inspect(temporary_database).get_table_names()) == TABLES


def test_transaction_commits_all_changes(temporary_database):
    with db.transaction() as connection:
        connection.execute(
            text(
                "INSERT INTO profiles (id, display_name, role, status, created_at) "
                "VALUES (:id, :name, :role, :status, :created_at)"
            ),
            {
                "id": "user-1",
                "name": "Ana",
                "role": "student",
                "status": "active",
                "created_at": "2026-11-14T12:00:00Z",
            },
        )

    with temporary_database.connect() as connection:
        result = connection.execute(
            text("SELECT display_name FROM profiles WHERE id = 'user-1'")
        ).scalar_one()

    assert result == "Ana"


def test_transaction_rolls_back_all_changes_when_one_fails(temporary_database):
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

    with temporary_database.connect() as connection:
        book_count = connection.execute(
            text("SELECT COUNT(*) FROM books WHERE id = 'book-1'")
        ).scalar_one()

    assert book_count == 0


def test_audit_target_must_exist_in_the_typed_id_registry(temporary_database):
    with temporary_database.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO profiles (id, display_name, role, status, created_at) "
                "VALUES ('user-1', 'Ana', 'student', 'active', 'now')"
            )
        )
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

    with temporary_database.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO entity_ids (table_name, entity_key) "
                "VALUES ('books', 'book-1')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO audit_log "
                "(id, actor_id, action, target_table, target_id, created_at) "
                "VALUES ('audit-2', 'user-1', 'edit', 'books', 'book-1', 'now')"
            )
        )


def test_postgresql_url_uses_psycopg_driver():
    assert db._normalise_database_url("postgresql://db.example/bookloop") == (
        "postgresql+psycopg://db.example/bookloop"
    )
