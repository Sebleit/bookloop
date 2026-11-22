from sqlalchemy import text

from bookloop.models import Loop, Trade
from bookloop.rules.handoffs import check_code, is_locked, no_show_outcome
from bookloop.storage.swaps_repo import confirm_handoff, trades_for_user


def trade(code_attempts: int = 0, status: str = "pending") -> Trade:
    return Trade(
        id="trade-1",
        loop_id="loop-1",
        copy_id="copy-1",
        giver_id="alice",
        receiver_id="bob",
        handoff_code="1234",
        code_attempts=code_attempts,
        status=status,
        completed_at=None,
    )


def loop(status: str = "scheduled") -> Loop:
    return Loop(
        id="loop-1",
        source="offer",
        offer_id="offer-1",
        round_id=None,
        status=status,
        meet_place="Main library",
        meet_time="2026-11-20T14:00:00Z",
        no_show_user_id=None,
    )


def test_right_code_is_accepted():
    assert check_code(trade(), "1234").allowed is True


def test_wrong_code_is_rejected_without_changing_trade():
    current_trade = trade()

    decision = check_code(current_trade, "9999")

    assert decision.allowed is False
    assert current_trade.code_attempts == 0
    assert current_trade.status == "pending"


def test_three_wrong_attempts_lock_the_trade():
    assert is_locked(trade(code_attempts=3)) is True
    assert check_code(trade(code_attempts=3), "1234").allowed is False


def test_fourth_attempt_is_rejected():
    assert check_code(trade(code_attempts=3), "9999").allowed is False


def test_participant_can_report_no_show():
    assert no_show_outcome(loop(), "alice", [trade()]).allowed is True


def test_stranger_cannot_report_no_show():
    assert no_show_outcome(loop(), "carla", [trade()]).allowed is False


def test_completed_loop_cannot_be_reported_as_no_show():
    assert no_show_outcome(loop(status="completed"), "alice", [trade()]).allowed is False


def save_trade(database, current_trade: Trade, current_loop: Loop):
    with database.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO loops "
                "(id, source, offer_id, round_id, status, meet_place, meet_time, no_show_user_id) "
                "VALUES (:id, 'offer', NULL, NULL, :status, 'Main library', "
                "'2026-11-20T14:00:00Z', NULL)"
            ),
            {"id": current_loop.id, "status": current_loop.status},
        )
        connection.execute(
            text(
                "INSERT INTO trades "
                "(id, loop_id, copy_id, giver_id, receiver_id, handoff_code, "
                "code_attempts, status, completed_at) "
                "VALUES (:id, :loop_id, :copy_id, :giver_id, :receiver_id, "
                ":handoff_code, :code_attempts, :status, :completed_at)"
            ),
            {
                "id": current_trade.id,
                "loop_id": current_trade.loop_id,
                "copy_id": current_trade.copy_id,
                "giver_id": current_trade.giver_id,
                "receiver_id": current_trade.receiver_id,
                "handoff_code": current_trade.handoff_code,
                "code_attempts": current_trade.code_attempts,
                "status": current_trade.status,
                "completed_at": current_trade.completed_at,
            },
        )


def test_confirm_handoff_completes_trade_and_changes_owner(database, make_user, make_copy):
    alice = make_user(name="Alice")
    bob = make_user(name="Bob")
    current_copy = make_copy(owner=alice, status="reserved")
    current_loop = loop()
    current_trade = trade()
    current_trade = Trade(
        **{**current_trade.__dict__, "id": "trade-1", "loop_id": current_loop.id,
           "copy_id": current_copy.id, "giver_id": alice.id, "receiver_id": bob.id}
    )
    save_trade(database, current_trade, current_loop)

    decision = confirm_handoff(current_trade.id, alice.id, "1234")

    assert decision.allowed is True
    with database.begin() as connection:
        owner = connection.execute(
            text("SELECT owner_id FROM copies WHERE id = :copy_id"),
            {"copy_id": current_copy.id},
        ).scalar_one()
        status = connection.execute(
            text("SELECT status FROM trades WHERE id = :trade_id"),
            {"trade_id": current_trade.id},
        ).scalar_one()
    assert owner == bob.id
    assert status == "completed"


def test_wrong_handoff_code_records_attempt_without_completing(database, make_user, make_copy):
    alice = make_user(name="Alice")
    bob = make_user(name="Bob")
    current_copy = make_copy(owner=alice, status="reserved")
    current_loop = loop()
    current_trade = Trade(
        **{**trade().__dict__, "loop_id": current_loop.id, "copy_id": current_copy.id,
           "giver_id": alice.id, "receiver_id": bob.id}
    )
    save_trade(database, current_trade, current_loop)

    decision = confirm_handoff(current_trade.id, alice.id, "9999")

    assert decision.allowed is False
    with database.begin() as connection:
        attempts = connection.execute(
            text("SELECT code_attempts FROM trades WHERE id = :trade_id"),
            {"trade_id": current_trade.id},
        ).scalar_one()
    assert attempts == 1


def test_locked_trade_rejects_fourth_code(database, make_user, make_copy):
    alice = make_user(name="Alice")
    bob = make_user(name="Bob")
    current_copy = make_copy(owner=alice, status="reserved")
    current_loop = loop()
    current_trade = Trade(
        **{**trade().__dict__, "loop_id": current_loop.id, "copy_id": current_copy.id,
           "giver_id": alice.id, "receiver_id": bob.id, "code_attempts": 3}
    )
    save_trade(database, current_trade, current_loop)

    decision = confirm_handoff(current_trade.id, alice.id, "1234")

    assert decision.allowed is False
    assert is_locked(current_trade) is True


def test_trades_for_user_returns_pending_handoff(database, make_user, make_copy):
    alice = make_user(name="Alice")
    bob = make_user(name="Bob")
    current_copy = make_copy(owner=alice, status="reserved")
    current_loop = loop()
    current_trade = Trade(
        **{**trade().__dict__, "loop_id": current_loop.id, "copy_id": current_copy.id,
           "giver_id": alice.id, "receiver_id": bob.id}
    )
    save_trade(database, current_trade, current_loop)

    swaps = trades_for_user(alice.id)

    assert len(swaps) == 1
    assert swaps[0]["trade"].id == current_trade.id
