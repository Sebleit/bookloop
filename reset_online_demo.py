"""Reset the demo data on the online database (Supabase), before a demo.

Before the first reset, sign up once on the live app for each demo person,
with these first names: Morgan, Ana, Ben, Carla, Dina, Eli and Farah (any
email and password). The script finds the accounts by first name.

    uv run python reset_online_demo.py        # checks the accounts, changes nothing
    uv run python reset_online_demo.py --yes  # resets the demo data

It needs DATABASE_URL, the online database's address, in the terminal or in
.streamlit/secrets.toml, like the app. It never touches the laptop database
(for that, run seed.py).

A reset happens in one transaction, so if anything fails, nothing changes:
1. it builds the same demo data as seed.py, in a temporary database;
2. it deletes every book, swap, round, review, notification and log entry
   online (accounts are kept);
3. it copies the demo data in, giving each demo person's books, swaps and
   reviews to their account, and sets roles and statuses (Morgan becomes the
   moderator, Dina is under review).
"""

import sys
import tempfile
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from bookloop.storage.db import _create_engine, _database_url_setting
from seed import base, reviews, rounds, swaps

MIGRATION_PATH = Path(__file__).resolve().parent / "db" / "migrations" / "001_init.sql"

# In the order 001_init.sql creates them, so the rows each row links to are
# already there when it's copied. Accounts (profiles) are kept, not copied.
TABLES = (
    "books",
    "courses",
    "book_courses",
    "copies",
    "wishlist",
    "notifications",
    "offers",
    "rounds",
    "loops",
    "trades",
    "round_entries",
    "round_wants",
    "reviews",
    "entity_ids",
    "audit_log",
)


class AccountsNotReady(Exception):
    """Some demo people have no account online, or more than one."""


def build_demo_data(engine: Engine) -> None:
    """Create the tables and the demo data, exactly as seed.py does."""
    with engine.begin() as connection:
        for statement in MIGRATION_PATH.read_text(encoding="utf-8").split(";"):
            if statement.strip():
                connection.exec_driver_sql(statement)
        base.seed(connection)
        swaps.seed(connection)
        rounds.seed(connection)
        reviews.seed(connection)


def _demo_people(demo: Connection) -> list[dict]:
    rows = demo.execute(
        text("SELECT id, display_name, role, status FROM profiles ORDER BY display_name")
    ).mappings()
    return [dict(row) for row in rows]


def find_accounts(online: Connection, people: list[dict]) -> dict[str, str]:
    """Match each demo person to the online account with the same first name."""
    by_name: dict[str, list[str]] = {}
    for account in online.execute(text("SELECT id, display_name FROM profiles")).mappings():
        by_name.setdefault(account["display_name"].strip().lower(), []).append(account["id"])

    accounts, problems = {}, []
    for person in people:
        name = person["display_name"]
        found = by_name.get(name.lower(), [])
        if not found:
            problems.append(f"No account called {name}: sign up on the app with the first name {name}.")
        elif len(found) > 1:
            problems.append(
                f"{len(found)} accounts are called {name}: rename the extra ones "
                "(display_name in the profiles table)."
            )
        else:
            accounts[person["id"]] = found[0]
    if problems:
        raise AccountsNotReady("\n".join(problems))
    return accounts


def _insert(online: Connection, table: str, rows: list[dict]) -> None:
    columns = list(rows[0])
    names = ", ".join(f'"{column}"' for column in columns)
    values = ", ".join(f":{column}" for column in columns)
    online.execute(text(f"INSERT INTO {table} ({names}) VALUES ({values})"), rows)


def reset(demo: Engine, online: Engine) -> dict[str, int]:
    """Replace the online data with the demo data. Returns how many rows each table got."""
    with demo.connect() as source:
        people = _demo_people(source)
        rows = {table: [dict(row) for row in source.execute(text(f"SELECT * FROM {table}")).mappings()] for table in TABLES}

    with online.begin() as target:
        accounts = find_accounts(target, people)
        for table in reversed(TABLES):
            target.execute(text(f"DELETE FROM {table}"))
        for person in people:
            target.execute(
                text("UPDATE profiles SET role = :role, status = :status WHERE id = :id"),
                {"role": person["role"], "status": person["status"], "id": accounts[person["id"]]},
            )
        for table in TABLES:
            if rows[table]:
                # Any value that is a demo person's id (an owner, a giver, a reviewer...)
                # becomes the id of that person's account.
                linked = [
                    {column: accounts.get(value, value) if isinstance(value, str) else value for column, value in row.items()}
                    for row in rows[table]
                ]
                _insert(target, table, linked)
    return {table: len(rows[table]) for table in TABLES}


def main(arguments: list[str]) -> int:
    url = _database_url_setting()
    if not url or url.startswith("sqlite"):
        print("DATABASE_URL isn't set to the online database, so nothing was changed.")
        print("Set it in this terminal or in .streamlit/secrets.toml. (For the laptop, run seed.py.)")
        return 1

    online = _create_engine(url)
    with tempfile.TemporaryDirectory() as folder:
        demo = _create_engine(f"sqlite:///{Path(folder) / 'demo.db'}")
        try:
            build_demo_data(demo)
            with demo.connect() as source:
                people = _demo_people(source)
            with online.connect() as target:
                accounts = find_accounts(target, people)
            if "--yes" not in arguments:
                names = ", ".join(person["display_name"] for person in people)
                print(f"All {len(accounts)} demo accounts were found ({names}). Nothing was changed.")
                print("To reset the online demo data, run again with --yes.")
                return 0
            counts = reset(demo, online)
        except AccountsNotReady as problem:
            print(problem)
            print("Nothing was changed.")
            return 1
        finally:
            demo.dispose()
            online.dispose()

    print("The online demo data is reset.")
    print(f"Accounts linked: {len(accounts)} (Morgan is the moderator, Dina is under review).")
    print(
        f"Books: {counts['books']}, copies: {counts['copies']}, swaps: {counts['loops']}, "
        f"reviews: {counts['reviews']}; the round \"Winter textbook swap\" is ready to run."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
