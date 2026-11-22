from bookloop.models import Loop, Trade
from bookloop.rules.handoffs import check_code, is_locked, no_show_outcome


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
