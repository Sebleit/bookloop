"""Tests for reset_online_demo.py: putting the demo data on the online database.

The "online" database here is a temporary SQLite file whose accounts have
random ids, like Supabase accounts. The script was also tried by hand on a
real PostgreSQL set up with db/supabase_only.sql.
"""

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import text

import reset_online_demo
from bookloop.storage.db import _create_engine

DEMO_PEOPLE = ("Morgan", "Ana", "Ben", "Carla", "Dina", "Eli", "Farah")
MIGRATION = Path(reset_online_demo.MIGRATION_PATH).read_text(encoding="utf-8")


def _empty_database(path: Path):
    engine = _create_engine(f"sqlite:///{path}")
    with engine.begin() as connection:
        for statement in MIGRATION.split(";"):
            if statement.strip():
                connection.exec_driver_sql(statement)
    return engine


def _sign_up(engine, name: str) -> str:
    account_id = str(uuid.uuid4())
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO profiles (id, display_name, role, status, created_at) "
                "VALUES (:id, :name, 'student', 'active', '2026-11-23T10:00:00Z')"
            ),
            {"id": account_id, "name": name},
        )
    return account_id


@pytest.fixture
def demo(tmp_path):
    engine = _create_engine(f"sqlite:///{tmp_path / 'demo.db'}")
    reset_online_demo.build_demo_data(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def online(tmp_path):
    engine = _empty_database(tmp_path / "online.db")
    yield engine
    engine.dispose()


def _one(engine, sql: str, **params):
    with engine.connect() as connection:
        return connection.execute(text(sql), params).one()


def test_reset_gives_the_demo_data_to_the_demo_accounts(demo, online):
    accounts = {name: _sign_up(online, name) for name in DEMO_PEOPLE}

    counts = reset_online_demo.reset(demo, online)

    assert counts["books"] == 15 and counts["reviews"] > 0
    assert _one(online, "SELECT role, status FROM profiles WHERE id = :id", id=accounts["Morgan"]) == ("moderator", "active")
    assert _one(online, "SELECT status FROM profiles WHERE id = :id", id=accounts["Dina"]) == ("under_review",)
    # Carla's waiting handoff to Dina, with Dina's code.
    giver, receiver, code = _one(
        online, "SELECT giver_id, receiver_id, handoff_code FROM trades WHERE id = 'trade-demo-pending-a'"
    )
    assert (giver, receiver, code) == (accounts["Carla"], accounts["Dina"], "3333")
    # No row still points at a laptop demo user.
    assert _one(online, "SELECT count(*) FROM copies WHERE owner_id LIKE 'user-%'") == (0,)
    assert _one(online, "SELECT count(*) FROM rounds WHERE created_by = :id", id=accounts["Morgan"]) == (1,)


def test_reset_keeps_other_accounts_but_replaces_their_data(demo, online):
    for name in DEMO_PEOPLE:
        _sign_up(online, name)
    tester = _sign_up(online, "Tester")
    with online.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO books (id, isbn, title, authors) "
                "VALUES ('book-old', '9780000000002', 'Old test book', 'Someone')"
            )
        )

    reset_online_demo.reset(demo, online)
    reset_online_demo.reset(demo, online)  # a second reset works too

    assert _one(online, "SELECT display_name FROM profiles WHERE id = :id", id=tester) == ("Tester",)
    assert _one(online, "SELECT count(*) FROM books WHERE id = 'book-old'") == (0,)
    assert _one(online, "SELECT count(*) FROM books") == (15,)


def test_a_missing_account_stops_the_reset_and_changes_nothing(demo, online):
    for name in DEMO_PEOPLE:
        if name != "Eli":
            _sign_up(online, name)

    with pytest.raises(reset_online_demo.AccountsNotReady, match="No account called Eli"):
        reset_online_demo.reset(demo, online)

    assert _one(online, "SELECT count(*) FROM books") == (0,)
    assert _one(online, "SELECT count(*) FROM profiles WHERE role = 'moderator'") == (0,)


def test_two_accounts_with_the_same_name_stop_the_reset(demo, online):
    for name in DEMO_PEOPLE:
        _sign_up(online, name)
    _sign_up(online, "carla")

    with pytest.raises(reset_online_demo.AccountsNotReady, match="2 accounts are called Carla"):
        reset_online_demo.reset(demo, online)


def test_without_an_online_database_the_script_refuses(monkeypatch, capsys):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert reset_online_demo.main(["--yes"]) == 1

    monkeypatch.setenv("DATABASE_URL", "sqlite:///bookloop.db")
    assert reset_online_demo.main(["--yes"]) == 1

    assert "nothing was changed" in capsys.readouterr().out


def test_the_sql_version_links_every_demo_person_to_their_account(demo):
    sql = reset_online_demo.reset_sql(demo, datetime(2026, 11, 23, tzinfo=timezone.utc))

    assert sql.startswith("-- BookLoop: reset the online demo data.")
    assert "shift integer := (now() AT TIME ZONE 'UTC')::date - date '2026-11-23';" in sql
    assert "DELETE FROM profiles WHERE id NOT IN (SELECT id::text FROM auth.users);" in sql
    for table in reset_online_demo.TABLES:
        assert f"DELETE FROM {table};" in sql
    # A demo person's id only appears in the list of demo accounts or in a lookup of their
    # account, never as a raw value (which would break the links on Supabase).
    for name in DEMO_PEOPLE:
        demo_id = "'user-moderator'" if name == "Morgan" else f"'user-{name.lower()}'"
        everywhere = sql.count(demo_id)
        looked_up = sql.count(f"demo_id = {demo_id}")
        listed = sql.count(f"({demo_id}, '{name}'")
        assert everywhere == looked_up + listed and listed == 1


def test_the_sql_file_in_the_repo_matches_the_demo_data(demo):
    # If this fails, the demo data changed: run `uv run python reset_online_demo.py --sql
    # db/demo_reset.sql` again. Dates are compared without the day they were written.
    in_repo = (Path(reset_online_demo.__file__).parent / "db" / "demo_reset.sql").read_text(encoding="utf-8")
    made_on = re.search(r"date '(\d{4}-\d{2}-\d{2})'", in_repo)[1]
    fresh = reset_online_demo.reset_sql(demo, datetime.fromisoformat(made_on).replace(tzinfo=timezone.utc))

    def without_times(sql: str) -> str:
        return re.sub(r"timestamp '[^']+'", "timestamp '…'", sql)

    assert without_times(fresh) == without_times(in_repo)
