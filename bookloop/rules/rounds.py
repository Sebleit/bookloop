"""Rules for swap rounds.

A round moves through four phases, always in this order:

    entries -> wants -> matched -> closed

- entries: students add their available books to the round.
- wants:   for each book they entered, students tick the books they'd accept.
- matched: the moderator has run the round and the loops are created.
- closed:  the round is over.

Only moderators move a round forward. Going from "wants" to "matched" happens
by running the round (can_run), not by a plain "next phase" click.

Like every rule, these functions never use Streamlit or the database: the page
and the storage layer give them everything they need as inputs.
"""

from dataclasses import dataclass
from datetime import datetime, timezone

from bookloop.models import Copy, Profile, Round
from bookloop.rules.decision import Decision
from bookloop.rules.permissions import is_active, is_moderator


PHASES = ("entries", "wants", "matched", "closed")
MIN_SCORE = 0.0
MAX_SCORE = 5.0


@dataclass(frozen=True)
class RoundEntryInfo:
    """A book entered in a round, together with who owns it.

    The round_entries table doesn't store the owner (that's in the copies
    table), so storage joins the two and gives the rules this combined view.
    """

    id: str
    round_id: str
    copy_id: str
    owner_id: str
    min_partner_score: float = 0.0


def _as_utc(value: str | datetime) -> datetime:
    """Turn an ISO timestamp like '2026-11-20T14:00:00Z' into a UTC datetime."""
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _now(now: str | datetime | None) -> datetime:
    """Use the given time (handy in tests) or the real current time."""
    return _as_utc(now) if now is not None else datetime.now(timezone.utc)


def next_phase(phase: str) -> str | None:
    """Return the phase after this one, or None if the round is closed."""
    position = PHASES.index(phase)
    if position == len(PHASES) - 1:
        return None
    return PHASES[position + 1]


def can_create_round(
    user: Profile,
    name: str,
    entries_close_at: str | datetime,
    wants_close_at: str | datetime,
    meet_place: str | None,
    meet_time: str | datetime | None,
    now: str | datetime | None = None,
) -> Decision:
    """Check the details of a new round before it is saved."""
    if not is_moderator(user):
        return Decision.no("Only moderators can create rounds.")
    if not name or not name.strip():
        return Decision.no("Give the round a name.")
    if not meet_place or not meet_place.strip() or meet_time is None:
        return Decision.no("Add a meeting place and time for the handoffs.")

    entries_close = _as_utc(entries_close_at)
    wants_close = _as_utc(wants_close_at)
    meeting = _as_utc(meet_time)
    if entries_close <= _now(now):
        return Decision.no("The entries deadline must be in the future.")
    if wants_close <= entries_close:
        return Decision.no("Wants must close after entries close.")
    if meeting <= wants_close:
        return Decision.no("The meeting must be after wants close.")
    return Decision.yes()


def can_advance(user: Profile, round: Round) -> Decision:
    """Check whether a moderator can move the round to its next phase."""
    if not is_moderator(user):
        return Decision.no("Only moderators can move a round to the next phase.")
    if round.phase == "wants":
        return Decision.no("Run the round to match the books.")
    if round.phase == "closed":
        return Decision.no("This round is already closed.")
    return Decision.yes()


def can_run(user: Profile, round: Round) -> Decision:
    """Check whether a moderator can run the round (find and create the loops)."""
    if not is_moderator(user):
        return Decision.no("Only moderators can run a round.")
    if round.phase == "entries":
        return Decision.no("Close entries first, so students can choose their wants.")
    if round.phase in ("matched", "closed"):
        return Decision.no("This round has already been run.")
    return Decision.yes()


def can_enter(
    user: Profile,
    round: Round,
    copy: Copy,
    blocked: bool = False,
    now: str | datetime | None = None,
) -> Decision:
    """Check whether a student can add one of their books to the round."""
    if blocked or not is_active(user):
        return Decision.no("Your account is under review, so you can't join rounds.")
    if round.phase != "entries":
        return Decision.no("This round isn't taking new books.")
    if _now(now) >= _as_utc(round.entries_close_at):
        return Decision.no("The entries deadline has passed.")
    if copy.owner_id != user.id:
        return Decision.no("You can only enter your own books.")
    if copy.status != "available":
        return Decision.no("Only available books can be entered.")
    return Decision.yes()


def _can_edit_wants(
    user: Profile,
    round: Round,
    entry: RoundEntryInfo,
    blocked: bool,
    now: str | datetime | None,
) -> Decision:
    """Checks shared by can_want and can_set_min_score."""
    if blocked or not is_active(user):
        return Decision.no("Your account is under review, so you can't join rounds.")
    if round.phase != "wants":
        return Decision.no("Wants can only be chosen during the wants phase.")
    if _now(now) >= _as_utc(round.wants_close_at):
        return Decision.no("The wants deadline has passed.")
    if entry.round_id != round.id:
        return Decision.no("That book isn't in this round.")
    if entry.owner_id != user.id:
        return Decision.no("You can only choose wants for your own books.")
    return Decision.yes()


def can_want(
    user: Profile,
    round: Round,
    my_entry: RoundEntryInfo,
    wanted_entry: RoundEntryInfo,
    blocked: bool = False,
    now: str | datetime | None = None,
) -> Decision:
    """Check whether a student can say "I'd accept wanted_entry for my_entry"."""
    decision = _can_edit_wants(user, round, my_entry, blocked, now)
    if not decision.allowed:
        return decision
    if wanted_entry.round_id != round.id:
        return Decision.no("That book isn't in this round.")
    if wanted_entry.owner_id == user.id:
        return Decision.no("You can't want your own book.")
    return Decision.yes()


def can_set_min_score(
    user: Profile,
    round: Round,
    entry: RoundEntryInfo,
    min_score: float,
    blocked: bool = False,
    now: str | datetime | None = None,
) -> Decision:
    """Check the optional "only swap with people scoring at least X" filter."""
    decision = _can_edit_wants(user, round, entry, blocked, now)
    if not decision.allowed:
        return decision
    if not MIN_SCORE <= min_score <= MAX_SCORE:
        return Decision.no("The minimum score must be between 0 and 5.")
    return Decision.yes()
