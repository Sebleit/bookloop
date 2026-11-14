# Person 1 owns this file: dataclasses for database tables.
from dataclasses import dataclass


@dataclass
class Profile:
    id: str
    display_name: str
    role: str
    status: str
    created_at: str


@dataclass
class Book:
    id: str
    isbn: str
    title: str
    authors: str
    edition: str | None
    cover_url: str | None


@dataclass
class Course:
    id: str
    code: str
    name: str


@dataclass
class BookCourse:
    book_id: str
    course_id: str


@dataclass
class Copy:
    id: str
    book_id: str
    owner_id: str
    condition: int
    highlighting: str
    notes: str | None
    status: str
    created_at: str


@dataclass
class Wishlist:
    user_id: str
    book_id: str
    created_at: str


@dataclass
class Notification:
    id: str
    user_id: str
    text: str
    link: str | None
    read: bool
    created_at: str


@dataclass
class Offer:
    id: str
    proposer_id: str
    offered_copy_id: str
    requested_copy_id: str
    status: str
    created_at: str
    expires_at: str


@dataclass
class Loop:
    id: str
    source: str
    offer_id: str | None
    round_id: str | None
    status: str
    meet_place: str | None
    meet_time: str | None
    no_show_user_id: str | None


@dataclass
class Trade:
    id: str
    loop_id: str
    copy_id: str
    giver_id: str
    receiver_id: str
    handoff_code: str
    code_attempts: int
    status: str
    completed_at: str | None


@dataclass
class Round:
    id: str
    name: str
    phase: str
    entries_close_at: str
    wants_close_at: str
    meet_place: str | None
    meet_time: str | None
    created_by: str


@dataclass
class RoundEntry:
    id: str
    round_id: str
    copy_id: str
    min_partner_score: float


@dataclass
class RoundWant:
    entry_id: str
    wanted_entry_id: str


@dataclass
class Review:
    id: str
    trade_id: str
    reviewer_id: str
    reviewee_id: str
    stars: int
    as_described: bool
    actual_condition: int
    comment: str | None
    reply: str | None
    visible_from: str | None
    hidden_by_moderator: bool
    hidden_reason: str | None
    created_at: str


@dataclass
class AuditLog:
    id: str
    actor_id: str
    action: str
    target_table: str
    target_id: str
    created_at: str
