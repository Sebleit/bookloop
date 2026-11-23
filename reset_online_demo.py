"""Reset the demo data on the online database (Supabase), before a demo.

Before the first reset, sign up once on the live app for each demo person,
with these first names: Morgan, Ana, Ben, Carla, Dina, Eli and Farah (any
email and password). The script finds the accounts by first name.

    uv run python reset_online_demo.py        # checks the accounts, changes nothing
    uv run python reset_online_demo.py --yes  # resets the demo data

It needs DATABASE_URL, the online database's address, in the terminal or in
.streamlit/secrets.toml, like the app. It never touches the laptop database
(for that, run seed.py).

Without DATABASE_URL, use db/demo_reset.sql instead: paste it into Supabase's
SQL Editor and run it. It does the same reset, moves every demo date to the
day it runs, and removes the profiles of accounts deleted in Supabase. After
changing the demo data, write it again with:

    uv run python reset_online_demo.py --sql db/demo_reset.sql

A reset happens in one transaction, so if anything fails, nothing changes:
1. it builds the same demo data as seed.py, in a temporary database;
2. it deletes every book, swap, round, review, notification and log entry
   online (accounts are kept);
3. it copies the demo data in, giving each demo person's books, swaps and
   reviews to their account, and sets roles and statuses (Morgan becomes the
   moderator, Dina is under review).

The demo also has 14 classmates (Afonso, Beatriz, ... Tiago) who never log in,
so they need no account: the reset creates their profiles itself, with ids
starting with "extra-", and replaces them at each reset.
"""

import re
import sys
import tempfile
from datetime import datetime, timezone
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


NO_LOGIN = f"{base.NO_LOGIN_PREFIX}%"


def _demo_people(demo: Connection) -> list[dict]:
    """The demo people who log in, so they need an account online."""
    rows = demo.execute(
        text(
            "SELECT id, display_name, role, status FROM profiles "
            "WHERE id NOT LIKE :no_login ORDER BY display_name"
        ),
        {"no_login": NO_LOGIN},
    ).mappings()
    return [dict(row) for row in rows]


def _classmates(demo: Connection) -> list[dict]:
    """The classmates who never log in: the reset creates their profiles."""
    rows = demo.execute(
        text("SELECT * FROM profiles WHERE id LIKE :no_login ORDER BY id"),
        {"no_login": NO_LOGIN},
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
        classmates = _classmates(source)
        rows = {table: [dict(row) for row in source.execute(text(f"SELECT * FROM {table}")).mappings()] for table in TABLES}

    with online.begin() as target:
        accounts = find_accounts(target, people)
        for table in reversed(TABLES):
            target.execute(text(f"DELETE FROM {table}"))
        target.execute(text("DELETE FROM profiles WHERE id LIKE :no_login"), {"no_login": NO_LOGIN})
        if classmates:
            _insert(target, "profiles", classmates)
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


# --- The same reset as SQL, for Supabase's SQL Editor ----------------------

TIMESTAMP = re.compile(r"^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}:\d{2})(\.\d+)?Z$")
# A round named after its handoff day, like "Weekly swap · 26 Nov".
DATED_NAME = re.compile(r"^(.*) · \d{1,2} [A-Z][a-z]{2}$")


def _sql_literal(value) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return repr(value)
    return "'" + str(value).replace("'", "''") + "'"


def reset_sql(demo: Engine, today: datetime) -> str:
    """The reset as one PL/pgSQL block: all of it happens, or none of it.

    Each demo person's id becomes a lookup of their account by first name,
    and each date moves by the number of days between `today` and the day
    the SQL runs, so the file works on any day.
    """
    with demo.connect() as source:
        people = _demo_people(source)
        classmates = _classmates(source)
        rows = {table: [dict(row) for row in source.execute(text(f"SELECT * FROM {table}")).mappings()] for table in TABLES}
    demo_ids = {person["id"] for person in people}

    def value(item) -> str:
        if isinstance(item, str) and item in demo_ids:
            return f"(SELECT account_id FROM demo_accounts WHERE demo_id = {_sql_literal(item)})"
        if isinstance(item, str) and (match := TIMESTAMP.match(item)):
            return (
                f"to_char(timestamp '{match[1]} {match[2]}' + shift * interval '1 day', "
                "'YYYY-MM-DD\"T\"HH24:MI:SS\"Z\"')"
            )
        return _sql_literal(item)

    def round_name(row: dict) -> str:
        """A round named after its handoff day keeps that day when the dates move."""
        match = DATED_NAME.match(row["name"])
        meet = TIMESTAMP.match(row["meet_time"] or "")
        if not (match and meet):
            return value(row["name"])
        return (
            f"{_sql_literal(match[1] + ' · ')} || to_char(timestamp '{meet[1]} {meet[2]}' "
            "+ shift * interval '1 day', 'FMDD Mon')"
        )

    names = ", ".join(person["display_name"] for person in people)
    lines = [
        "-- BookLoop: reset the online demo data. Paste all of it into Supabase -> SQL Editor -> Run.",
        "-- It's one block: if anything fails, nothing changes. It works on any day: every demo",
        "-- date moves to the day it runs. It also removes the profiles of accounts deleted in",
        "-- Authentication -> Users. Made by: uv run python reset_online_demo.py --sql db/demo_reset.sql",
        f"-- It needs one account for each of these first names: {names}.",
        "DO $reset$",
        "DECLARE",
        "    problem text;",
        f"    shift integer := (now() AT TIME ZONE 'UTC')::date - date '{today:%Y-%m-%d}';",
        "BEGIN",
        "    CREATE TEMP TABLE demo_accounts (demo_id text PRIMARY KEY, name text, role text, status text, "
        "account_id text) ON COMMIT DROP;",
        "    INSERT INTO demo_accounts (demo_id, name, role, status) VALUES",
        ",\n".join(
            f"        ({_sql_literal(p['id'])}, {_sql_literal(p['display_name'])}, "
            f"{_sql_literal(p['role'])}, {_sql_literal(p['status'])})"
            for p in people
        ) + ";",
        "",
        "    SELECT string_agg(d.name, ', ' ORDER BY d.name) INTO problem FROM demo_accounts d",
        "    WHERE (SELECT count(*) FROM profiles p WHERE lower(trim(p.display_name)) = lower(d.name)) <> 1;",
        "    IF problem IS NOT NULL THEN",
        "        RAISE EXCEPTION 'Each of these needs exactly one account with that name: %. "
        "Nothing was changed.', problem;",
        "    END IF;",
        "    UPDATE demo_accounts d SET account_id = p.id FROM profiles p "
        "WHERE lower(trim(p.display_name)) = lower(d.name);",
        "",
    ]
    lines += [f"    DELETE FROM {table};" for table in reversed(TABLES)]
    lines += [
        "",
        "    -- Accounts deleted in Authentication -> Users: remove their profiles too.",
        "    -- This also removes the classmates who never log in; they're added again below.",
        "    DELETE FROM profiles WHERE id NOT IN (SELECT id::text FROM auth.users);",
        "",
        "    UPDATE profiles p SET display_name = d.name, role = d.role, status = d.status",
        "    FROM demo_accounts d WHERE p.id = d.account_id;",
        "",
    ]
    if classmates:
        columns = list(classmates[0])
        quoted = ", ".join(f'"{column}"' for column in columns)
        values = ",\n".join(
            "        (" + ", ".join(value(row[column]) for column in columns) + ")" for row in classmates
        )
        lines.append(f"    INSERT INTO profiles ({quoted}) VALUES\n{values};")
    for table in TABLES:
        if rows[table]:
            columns = list(rows[table][0])
            quoted = ", ".join(f'"{column}"' for column in columns)
            values = ",\n".join(
                "        ("
                + ", ".join(
                    round_name(row) if (table, column) == ("rounds", "name") else value(row[column])
                    for column in columns
                )
                + ")"
                for row in rows[table]
            )
            lines.append(f"    INSERT INTO {table} ({quoted}) VALUES\n{values};")
    lines += [
        "END",
        "$reset$;",
        "",
        "-- Who's who now: Morgan should be the moderator and Dina under review.",
        "SELECT display_name, role, status FROM profiles ORDER BY role DESC, display_name;",
        "",
    ]
    return "\n".join(lines)


def main(arguments: list[str]) -> int:
    if "--sql" in arguments:
        target = Path(arguments[arguments.index("--sql") + 1])
        with tempfile.TemporaryDirectory() as folder:
            demo = _create_engine(f"sqlite:///{Path(folder) / 'demo.db'}")
            build_demo_data(demo)
            target.write_text(reset_sql(demo, datetime.now(timezone.utc)), encoding="utf-8")
            demo.dispose()
        print(f"Wrote {target}: paste it into Supabase's SQL Editor and run it.")
        return 0

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
        f"reviews: {counts['reviews']}; this week's round is ready to run."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
