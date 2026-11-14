# Person 1 owns this file: database connection and transactions.
import os
from contextlib import contextmanager
from typing import Iterator

import streamlit as st
from sqlalchemy import create_engine as sqlalchemy_create_engine
from sqlalchemy import event
from sqlalchemy.engine import Connection, Engine


def _normalise_database_url(database_url: str) -> str:
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return database_url


def _database_url_setting() -> str | None:
    value = os.environ.get("DATABASE_URL")
    if value:
        return value
    try:
        value = st.secrets.get("DATABASE_URL")
    except Exception:
        return None
    return str(value) if value else None


def _create_engine(database_url: str | None = None) -> Engine:
    configured_url = database_url or _database_url_setting()
    if configured_url:
        url = _normalise_database_url(configured_url)
    else:
        url = "sqlite:///bookloop.db"

    options = {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite:") else {}
    database_engine = sqlalchemy_create_engine(url, **options)

    if database_engine.dialect.name == "sqlite":

        @event.listens_for(database_engine, "connect")
        def enable_foreign_keys(dbapi_connection, _connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return database_engine


engine = _create_engine()


@contextmanager
def transaction() -> Iterator[Connection]:
    """Group database changes so they commit together or roll back together."""
    with engine.begin() as connection:
        yield connection
