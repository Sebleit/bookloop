# Person 1 owns this file: rebuilds the local database with demo data.
from pathlib import Path

from bookloop.storage.db import _create_engine
from seed import base, reviews, rounds, swaps


ROOT = Path(__file__).resolve().parent
DATABASE_PATH = ROOT / "bookloop.db"
MIGRATION_PATH = ROOT / "db" / "migrations" / "001_init.sql"


def rebuild_local_database() -> None:
    """Recreate the local SQLite database and load deterministic demo data."""
    sidecars = (
        Path(f"{DATABASE_PATH}-journal"),
        Path(f"{DATABASE_PATH}-wal"),
        Path(f"{DATABASE_PATH}-shm"),
    )
    for path in (DATABASE_PATH, *sidecars):
        if path.exists():
            path.unlink()

    engine = _create_engine(f"sqlite:///{DATABASE_PATH.as_posix()}")
    migration = MIGRATION_PATH.read_text(encoding="utf-8")

    try:
        with engine.begin() as connection:
            for statement in migration.split(";"):
                if statement.strip():
                    connection.exec_driver_sql(statement)

            base.seed(connection)
            swaps.seed(connection)
            rounds.seed(connection)
            reviews.seed(connection)
    finally:
        engine.dispose()

    students = ", ".join(base.STUDENTS)
    print(f"Rebuilt local database: {DATABASE_PATH.name}")
    print(f"Profiles: Morgan (moderator); {len(base.STUDENTS)} students ({students}).")
    print(
        f"Courses: {len(base.COURSES)}; textbooks: {len(base.BOOKS)}; "
        "copies: 25 (conditions 1 through 4)."
    )


if __name__ == "__main__":
    rebuild_local_database()
