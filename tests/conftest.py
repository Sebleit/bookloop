# Person 1 owns this file: shared test database, factories and fake Open Library.
from pathlib import Path
from typing import Callable

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine

from bookloop.models import Book, Copy, Loop, Offer, Profile, Review
from bookloop.storage import db


CREATED_AT = "2026-11-14T00:00:00Z"


@pytest.fixture(autouse=True)
def database(tmp_path, monkeypatch) -> Engine:
    """Give every test a fresh SQLite database built from the project migration."""
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
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def make_user(database) -> Callable[..., Profile]:
    counter = 0

    def factory(
        name: str = "Ana",
        role: str = "student",
        status: str = "active",
        id: str | None = None,
    ) -> Profile:
        nonlocal counter
        counter += 1
        user = Profile(
            id=id or f"user-{counter:03}",
            display_name=name,
            role=role,
            status=status,
            created_at=CREATED_AT,
        )
        with db.transaction() as connection:
            connection.execute(
                text(
                    "INSERT INTO profiles (id, display_name, role, status, created_at) "
                    "VALUES (:id, :display_name, :role, :status, :created_at)"
                ),
                {
                    "id": user.id,
                    "display_name": user.display_name,
                    "role": user.role,
                    "status": user.status,
                    "created_at": user.created_at,
                },
            )
        return user

    return factory


@pytest.fixture
def make_book(database) -> Callable[..., Book]:
    counter = 0

    def factory(
        title: str = "Example Textbook",
        authors: str = "Example Author",
        isbn: str | None = None,
        edition: str | None = "1st",
        cover_url: str | None = None,
        id: str | None = None,
    ) -> Book:
        nonlocal counter
        counter += 1
        book_id = id or f"book-{counter:03}"
        book = Book(
            id=book_id,
            isbn=isbn or f"test-isbn-{counter:03}",
            title=title,
            authors=authors,
            edition=edition,
            cover_url=cover_url,
        )
        with db.transaction() as connection:
            connection.execute(
                text(
                    "INSERT INTO books (id, isbn, title, authors, edition, cover_url) "
                    "VALUES (:id, :isbn, :title, :authors, :edition, :cover_url)"
                ),
                {
                    "id": book.id,
                    "isbn": book.isbn,
                    "title": book.title,
                    "authors": book.authors,
                    "edition": book.edition,
                    "cover_url": book.cover_url,
                },
            )
        return book

    return factory


@pytest.fixture
def make_copy(database, make_user, make_book) -> Callable[..., Copy]:
    counter = 0

    def factory(
        owner: Profile | None = None,
        book: Book | None = None,
        condition: int = 3,
        highlighting: str = "none",
        notes: str | None = None,
        status: str = "available",
        id: str | None = None,
    ) -> Copy:
        nonlocal counter
        counter += 1
        owner = owner or make_user(name="Copy Owner")
        book = book or make_book()
        copy = Copy(
            id=id or f"copy-{counter:03}",
            book_id=book.id,
            owner_id=owner.id,
            condition=condition,
            highlighting=highlighting,
            notes=notes,
            status=status,
            created_at=CREATED_AT,
        )
        with db.transaction() as connection:
            connection.execute(
                text(
                    'INSERT INTO copies '
                    '(id, book_id, owner_id, "condition", highlighting, notes, status, created_at) '
                    "VALUES (:id, :book_id, :owner_id, :condition, :highlighting, :notes, :status, :created_at)"
                ),
                {
                    "id": copy.id,
                    "book_id": copy.book_id,
                    "owner_id": copy.owner_id,
                    "condition": copy.condition,
                    "highlighting": copy.highlighting,
                    "notes": copy.notes,
                    "status": copy.status,
                    "created_at": copy.created_at,
                },
            )
        return copy

    return factory


@pytest.fixture
def make_offer(database, make_user, make_copy) -> Callable[..., Offer]:
    counter = 0

    def factory(
        proposer: Profile | None = None,
        offered_copy: Copy | None = None,
        requested_copy: Copy | None = None,
        status: str = "pending",
        expires_at: str = "2026-11-17T00:00:00Z",
        id: str | None = None,
    ) -> Offer:
        nonlocal counter
        counter += 1
        if offered_copy is None:
            proposer = proposer or make_user(name="Offer Proposer")
            offered_copy = make_copy(owner=proposer)
        proposer = proposer or make_user(name="Offer Proposer")
        requested_copy = requested_copy or make_copy()
        offer = Offer(
            id=id or f"offer-{counter:03}",
            proposer_id=proposer.id,
            offered_copy_id=offered_copy.id,
            requested_copy_id=requested_copy.id,
            status=status,
            created_at=CREATED_AT,
            expires_at=expires_at,
        )
        with db.transaction() as connection:
            connection.execute(
                text(
                    "INSERT INTO offers "
                    "(id, proposer_id, offered_copy_id, requested_copy_id, status, created_at, expires_at) "
                    "VALUES (:id, :proposer_id, :offered_copy_id, :requested_copy_id, "
                    ":status, :created_at, :expires_at)"
                ),
                {
                    "id": offer.id,
                    "proposer_id": offer.proposer_id,
                    "offered_copy_id": offer.offered_copy_id,
                    "requested_copy_id": offer.requested_copy_id,
                    "status": offer.status,
                    "created_at": offer.created_at,
                    "expires_at": offer.expires_at,
                },
            )
        return offer

    return factory


@pytest.fixture
def make_loop(database, make_user, make_offer) -> Callable[..., Loop]:
    counter = 0

    def factory(
        source: str = "offer",
        offer: Offer | None = None,
        round_id: str | None = None,
        status: str = "scheduled",
        meet_place: str | None = "Main library",
        meet_time: str | None = "2026-11-20T14:00:00Z",
        no_show_user_id: str | None = None,
        id: str | None = None,
    ) -> Loop:
        nonlocal counter
        counter += 1
        if source not in {"offer", "round"}:
            raise ValueError("Source must be 'offer' or 'round'.")

        offer_id = None
        if source == "offer":
            offer = offer or make_offer()
            offer_id = offer.id
        elif round_id is None:
            creator = make_user(name="Round Creator", role="moderator")
            round_id = f"round-{counter:03}"
            with db.transaction() as connection:
                connection.execute(
                    text(
                        "INSERT INTO rounds "
                        "(id, name, phase, entries_close_at, wants_close_at, meet_place, meet_time, created_by) "
                        "VALUES (:id, 'Test round', 'entries', :entries_close_at, :wants_close_at, "
                        ":meet_place, :meet_time, :created_by)"
                    ),
                    {
                        "id": round_id,
                        "entries_close_at": CREATED_AT,
                        "wants_close_at": CREATED_AT,
                        "meet_place": meet_place,
                        "meet_time": meet_time,
                        "created_by": creator.id,
                    },
                )

        loop = Loop(
            id=id or f"loop-{counter:03}",
            source=source,
            offer_id=offer_id,
            round_id=round_id if source == "round" else None,
            status=status,
            meet_place=meet_place,
            meet_time=meet_time,
            no_show_user_id=no_show_user_id,
        )
        with db.transaction() as connection:
            connection.execute(
                text(
                    "INSERT INTO loops "
                    "(id, source, offer_id, round_id, status, meet_place, meet_time, no_show_user_id) "
                    "VALUES (:id, :source, :offer_id, :round_id, :status, :meet_place, :meet_time, :no_show_user_id)"
                ),
                {
                    "id": loop.id,
                    "source": loop.source,
                    "offer_id": loop.offer_id,
                    "round_id": loop.round_id,
                    "status": loop.status,
                    "meet_place": loop.meet_place,
                    "meet_time": loop.meet_time,
                    "no_show_user_id": loop.no_show_user_id,
                },
            )
        return loop

    return factory


@pytest.fixture
def make_review(database, make_user, make_copy, make_loop) -> Callable[..., Review]:
    counter = 0

    def factory(
        reviewer: Profile | None = None,
        reviewee: Profile | None = None,
        trade_id: str | None = None,
        stars: int = 5,
        as_described: bool = True,
        actual_condition: int = 3,
        comment: str | None = None,
        reply: str | None = None,
        visible_from: str | None = None,
        hidden_by_moderator: bool = False,
        hidden_reason: str | None = None,
        id: str | None = None,
    ) -> Review:
        nonlocal counter
        counter += 1
        reviewer = reviewer or make_user(name="Reviewer")
        reviewee = reviewee or make_user(name="Reviewee")
        if trade_id is None:
            loop = make_loop()
            copy = make_copy(owner=reviewee)
            trade_id = f"trade-{counter:03}"
            with db.transaction() as connection:
                connection.execute(
                    text(
                        "INSERT INTO trades "
                        "(id, loop_id, copy_id, giver_id, receiver_id, handoff_code, status, completed_at) "
                        "VALUES (:id, :loop_id, :copy_id, :giver_id, :receiver_id, '1234', 'completed', :completed_at)"
                    ),
                    {
                        "id": trade_id,
                        "loop_id": loop.id,
                        "copy_id": copy.id,
                        "giver_id": reviewee.id,
                        "receiver_id": reviewer.id,
                        "completed_at": CREATED_AT,
                    },
                )

        review = Review(
            id=id or f"review-{counter:03}",
            trade_id=trade_id,
            reviewer_id=reviewer.id,
            reviewee_id=reviewee.id,
            stars=stars,
            as_described=as_described,
            actual_condition=actual_condition,
            comment=comment,
            reply=reply,
            visible_from=visible_from,
            hidden_by_moderator=hidden_by_moderator,
            hidden_reason=hidden_reason,
            created_at=CREATED_AT,
        )
        with db.transaction() as connection:
            connection.execute(
                text(
                    "INSERT INTO reviews "
                    "(id, trade_id, reviewer_id, reviewee_id, stars, as_described, actual_condition, "
                    "comment, reply, visible_from, hidden_by_moderator, hidden_reason, created_at) "
                    "VALUES (:id, :trade_id, :reviewer_id, :reviewee_id, :stars, :as_described, "
                    ":actual_condition, :comment, :reply, :visible_from, :hidden_by_moderator, "
                    ":hidden_reason, :created_at)"
                ),
                {
                    "id": review.id,
                    "trade_id": review.trade_id,
                    "reviewer_id": review.reviewer_id,
                    "reviewee_id": review.reviewee_id,
                    "stars": review.stars,
                    "as_described": int(review.as_described),
                    "actual_condition": review.actual_condition,
                    "comment": review.comment,
                    "reply": review.reply,
                    "visible_from": review.visible_from,
                    "hidden_by_moderator": int(review.hidden_by_moderator),
                    "hidden_reason": review.hidden_reason,
                    "created_at": review.created_at,
                },
            )
        return review

    return factory


class FakeOpenLibrary:
    """Return a fixed textbook record without making any network request."""

    def lookup(self, isbn: str) -> Book:
        return Book(
            id="open-library-fixed-book",
            isbn=isbn,
            title="A Fixed Open Library Book",
            authors="Example Author",
            edition="1st",
            cover_url=None,
        )

    def __call__(self, isbn: str) -> Book:
        return self.lookup(isbn)


@pytest.fixture
def fake_open_library() -> FakeOpenLibrary:
    return FakeOpenLibrary()
