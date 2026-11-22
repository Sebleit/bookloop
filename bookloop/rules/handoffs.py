"""Rules for confirming handoffs and reporting no-shows."""

from collections.abc import Sequence

from bookloop.models import Loop, Trade
from bookloop.rules.decision import Decision


MAX_WRONG_CODE_ATTEMPTS = 3


def is_locked(trade: Trade) -> bool:
    """Return whether three wrong code attempts have locked the trade."""
    return trade.code_attempts >= MAX_WRONG_CODE_ATTEMPTS


def check_code(trade: Trade, entered_code: str) -> Decision:
    """Check the receiver's four-digit code without changing the trade."""
    if trade.status != "pending":
        return Decision.no("This trade is no longer pending.")
    if is_locked(trade):
        return Decision.no("This trade is locked after 3 wrong codes.")
    if entered_code.strip() != trade.handoff_code:
        return Decision.no("The handoff code is incorrect.")
    return Decision.yes()


def no_show_outcome(
    loop: Loop, reporter_id: str, trades: Sequence[Trade]
) -> Decision:
    """Check whether a participant can report a no-show for an active loop."""
    if loop.status != "scheduled":
        return Decision.no("Only scheduled swaps can be reported as a no-show.")
    participants = {
        participant_id
        for trade in trades
        for participant_id in (trade.giver_id, trade.receiver_id)
    }
    if reporter_id not in participants:
        return Decision.no("Only someone in the swap can report a no-show.")
    return Decision.yes()
