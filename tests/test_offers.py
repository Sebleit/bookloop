from datetime import datetime, timezone

from bookloop.models import Copy, Offer
from bookloop.rules.offers import can_accept, can_cancel, can_make_offer, is_expired
from bookloop.storage.swaps_repo import create_offer, pending_offer_count


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
