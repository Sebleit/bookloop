"""Rules for confirming handoffs, no-shows and missing handoffs.

Everyone in a swap meets at the same place and time, and nobody hands over a
book until everyone is there. So:
- if someone doesn't come, nobody has handed over anything yet: a no-show
  cancels the swap and everyone keeps their own book;
- once a book has changed hands (a code was typed), everyone was there, so it
  can't be a no-show. If someone then doesn't hand over their book, it's
  reported to a moderator, who checks what happened.
"""

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
    if any(trade.status == "completed" for trade in trades):
        return Decision.no(
            "A book has already changed hands in this swap, so everyone was there. "
            "Report a problem instead: a moderator will check what happened."
        )
    return Decision.yes()


def can_report_missing_handoff(
    loop: Loop, reporter_id: str, accused_id: str, trades: Sequence[Trade]
) -> Decision:
    """Check a report that someone was at the meeting but didn't hand over their book."""
    if loop.status != "scheduled":
        return Decision.no("Only active swaps can be reported.")
    participants = {
        participant_id
        for trade in trades
        for participant_id in (trade.giver_id, trade.receiver_id)
    }
    if reporter_id not in participants:
        return Decision.no("Only someone in the swap can report a problem.")
    if not any(trade.status == "completed" for trade in trades):
        return Decision.no(
            "No book has changed hands yet. If someone didn't come, report a no-show instead."
        )
    if accused_id == reporter_id:
        return Decision.no("Choose the person who didn't hand over their book.")
    if not any(trade.giver_id == accused_id and trade.status == "pending" for trade in trades):
        return Decision.no("That person has already handed over their book.")
    return Decision.yes()
