from datetime import datetime, timedelta, timezone

from bookloop.models import Copy, Offer
from bookloop.rules.offers import can_accept, can_cancel, can_make_offer, check_meeting, is_expired
from bookloop.storage.swaps_repo import (
    accept_offer,
    cancel_offer,
    create_offer,
    decline_offer,
    pending_offer_count,
)


def copy(id: str, owner_id: str, status: str = "available") -> Copy:
    return Copy(
        id=id,
        book_id=f"book-{id}",
        owner_id=owner_id,
        condition=4,
        highlighting="none",
        notes=None,
        status=status,
        created_at="2026-11-14T00:00:00Z",
    )


def offer(
    proposer_id: str = "alice",
    status: str = "pending",
    created_at: str = "2026-11-14T00:00:00Z",
    expires_at: str = "2026-11-17T00:00:00Z",
) -> Offer:
    return Offer(
        id="offer-1",
        proposer_id=proposer_id,
        offered_copy_id="copy-a",
        requested_copy_id="copy-b",
        status=status,
        created_at=created_at,
        expires_at=expires_at,
    )


def test_can_make_valid_offer():
    decision = can_make_offer(
        "alice", copy("copy-a", "alice"), copy("copy-b", "bob"), pending_offer_count=0
    )

    assert decision.allowed is True


def test_cannot_make_offer_with_someone_elses_copy():
    offered = copy("copy-a", "bob")

    decision = can_make_offer("alice", offered, copy("copy-b", "carla"), 0)

    assert decision.allowed is False
    assert "own" in decision.reason.lower()


def test_cannot_make_sixth_pending_offer():
    decision = can_make_offer(
        "alice", copy("copy-a", "alice"), copy("copy-b", "bob"), pending_offer_count=5
    )

    assert decision.allowed is False


def test_blocked_user_cannot_make_offer():
    decision = can_make_offer(
        "alice", copy("copy-a", "alice"), copy("copy-b", "bob"), 0, blocked=True
    )

    assert decision.allowed is False


def test_can_accept_valid_offer():
    decision = can_accept(
        offer(),
        "bob",
        copy("copy-a", "alice"),
        copy("copy-b", "bob"),
        now=datetime(2026, 11, 16, 12, tzinfo=timezone.utc),
    )

    assert decision.allowed is True


def test_cannot_accept_expired_offer():
    current_offer = offer()

    decision = can_accept(
        current_offer,
        "bob",
        copy("copy-a", "alice"),
        copy("copy-b", "bob"),
        now=datetime(2026, 11, 17, 0, tzinfo=timezone.utc),
    )

    assert decision.allowed is False
    assert current_offer.status == "pending"


def test_cannot_accept_when_requested_copy_is_no_longer_available():
    decision = can_accept(
        offer(),
        "bob",
        copy("copy-a", "alice"),
        copy("copy-b", "bob", status="reserved"),
        now=datetime(2026, 11, 16, 12, tzinfo=timezone.utc),
    )

    assert decision.allowed is False


def test_only_proposer_can_cancel_pending_offer():
    assert can_cancel(offer(), "alice").allowed is True
    assert can_cancel(offer(), "bob").allowed is False


def test_is_expired_at_exactly_72_hours():
    assert is_expired(
        offer(), now=datetime(2026, 11, 17, 0, tzinfo=timezone.utc)
    ) is True


def test_create_offer_saves_pending_offer(database, make_user, make_copy):
    alice = make_user(name="Alice")
    bob = make_user(name="Bob")
    offered = make_copy(owner=alice)
    requested = make_copy(owner=bob)

    saved = create_offer(
        alice.id,
        offered.id,
        requested.id,
        "2026-11-23T00:00:00Z",
    )

    assert saved.status == "pending"
    assert saved.proposer_id == alice.id
    assert pending_offer_count(alice.id) == 1


def test_pending_offer_count_ignores_finished_offers(database, make_user, make_copy, make_offer):
    alice = make_user(name="Alice")
    bob = make_user(name="Bob")
    offered = make_copy(owner=alice)
    requested = make_copy(owner=bob)
    make_offer(
        proposer=alice,
        offered_copy=offered,
        requested_copy=requested,
        status="cancelled",
    )

    assert pending_offer_count(alice.id) == 0


def test_cancel_offer_changes_pending_status(database, make_user, make_copy, make_offer):
    alice = make_user(name="Alice")
    bob = make_user(name="Bob")
    current_offer = make_offer(
        proposer=alice,
        offered_copy=make_copy(owner=alice),
        requested_copy=make_copy(owner=bob),
    )

    cancel_offer(current_offer, alice.id)

    with database.begin() as connection:
        status = connection.execute(
            __import__("sqlalchemy").text("SELECT status FROM offers WHERE id = :id"),
            {"id": current_offer.id},
        ).scalar_one()
    assert status == "cancelled"


def test_decline_offer_changes_pending_status(database, make_user, make_copy, make_offer):
    alice = make_user(name="Alice")
    bob = make_user(name="Bob")
    current_offer = make_offer(
        proposer=alice,
        offered_copy=make_copy(owner=alice),
        requested_copy=make_copy(owner=bob),
    )

    decline_offer(current_offer, bob.id)

    with database.begin() as connection:
        status = connection.execute(
            __import__("sqlalchemy").text("SELECT status FROM offers WHERE id = :id"),
            {"id": current_offer.id},
        ).scalar_one()
    assert status == "declined"


def test_accept_offer_reserves_both_copies(database, make_user, make_copy, make_offer):
    alice = make_user(name="Alice")
    bob = make_user(name="Bob")
    offered = make_copy(owner=alice)
    requested = make_copy(owner=bob)
    # Accepting checks the real clock, so the offer must expire in the future.
    in_72_hours = datetime.now(timezone.utc) + timedelta(hours=72)
    current_offer = make_offer(
        proposer=alice,
        offered_copy=offered,
        requested_copy=requested,
        expires_at=in_72_hours.isoformat().replace("+00:00", "Z"),
    )

    loop = accept_offer(current_offer, bob.id, offered, requested)

    assert loop.source == "offer"
    with database.begin() as connection:
        statuses = connection.execute(
            __import__("sqlalchemy").text(
                "SELECT status FROM copies WHERE id IN (:offered, :requested) ORDER BY id"
            ),
            {"offered": offered.id, "requested": requested.id},
        ).scalars().all()
    assert statuses == ["reserved", "reserved"]


# --- Agreeing where and when to meet ------------------------------------------

NOW = datetime(2026, 11, 23, 12, 0, tzinfo=timezone.utc)


def test_a_meeting_with_a_place_and_a_future_time_is_accepted():
    assert check_meeting("Nova SBE library", NOW + timedelta(days=1), NOW).allowed


def test_a_meeting_needs_a_place():
    decision = check_meeting("   ", NOW + timedelta(days=1), NOW)
    assert not decision.allowed and decision.reason == "Add where you'll meet."


def test_a_meeting_in_the_past_or_right_now_is_refused():
    assert check_meeting("Library", NOW - timedelta(minutes=1), NOW).reason == "Choose a meeting time in the future."
    assert not check_meeting("Library", NOW, NOW).allowed  # exactly now is too late


def test_a_meeting_place_of_100_characters_is_the_longest_allowed():
    assert check_meeting("x" * 100, "2026-11-24T14:00:00Z", NOW).allowed
    assert not check_meeting("x" * 101, "2026-11-24T14:00:00Z", NOW).allowed
