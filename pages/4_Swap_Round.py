"""Swap Round page.

Students enter books, tick the books they'd accept, and see their own result.
Moderators also get controls to create a round, move it forward and run it.

Like every page, it shows data, asks a rule, saves through storage, and ends
with a "Done" or "why not" message.
"""

from datetime import date, datetime, time, timedelta, timezone

import streamlit as st

from bookloop import auth
from bookloop.loop_picture import loop_dot
from bookloop.models import Profile, Round
from bookloop.rules.permissions import is_moderator
from bookloop.rules.rounds import (
    can_advance,
    can_create_round,
    can_enter,
    can_run,
    can_set_min_score,
    can_want,
)
from bookloop.storage import rounds_repo
from bookloop.storage.reviews_repo import is_blocked, swapper_score


PHASE_LABELS = {
    "entries": "Entries open",
    "wants": "Choosing wants",
    "matched": "Matched",
    "closed": "Closed",
}
CONDITIONS = {1: "poor", 2: "fair", 3: "good", 4: "like new"}
FLASH_KEY = "swap_round_message"


# --- Small helpers ---------------------------------------------------------


def _local_zone():
    """Lisbon time if this computer knows it, otherwise UTC (the same in winter)."""
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo("Europe/Lisbon")
    except Exception:
        return timezone.utc


def _to_utc_text(day: date, clock: time) -> str:
    """Turn a date and time typed in Lisbon time into a UTC timestamp for the database."""
    moment = datetime.combine(day, clock, tzinfo=_local_zone()).astimezone(timezone.utc)
    return moment.isoformat().replace("+00:00", "Z")


def _show_time(value: str | None) -> str:
    """Show a stored UTC timestamp in Lisbon time, like 'Wed 16 Dec, 14:00'."""
    if not value:
        return "not set"
    moment = datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(_local_zone())
    return moment.strftime("%a %d %b, %H:%M")


def _flash(kind: str, message: str) -> None:
    """Remember a message, then reload the page so it shows the latest data."""
    st.session_state[FLASH_KEY] = (kind, message)
    st.rerun()


def _show_flash() -> None:
    message = st.session_state.pop(FLASH_KEY, None)
    if message is None:
        return
    kind, text = message
    if kind == "success":
        st.success(text)
        st.toast(text, icon="✅")  # also pops up in the corner, wherever you've scrolled
    else:
        st.error(text)


def _entry_label(entry: rounds_repo.EntryDetails, scores: dict[str, float]) -> str:
    condition = CONDITIONS.get(entry.condition, "unknown")
    score = scores.get(entry.info.owner_id)
    score_text = f", score {score:.2f}" if score is not None else ""
    return (
        f"{entry.title} ({condition}, {entry.highlighting} highlighting) "
        f"from {entry.owner_name}{score_text}"
    )


# --- Moderator: create, advance and run -----------------------------------


def _create_round_form(user: Profile) -> None:
    with st.expander("Create a new round"):
        today = date.today()
        with st.form("create_round_form"):
            name = st.text_input("Name", placeholder="Winter textbook swap")
            col1, col2 = st.columns(2)
            entries_day = col1.date_input("Entries close on", today + timedelta(days=3))
            entries_clock = col2.time_input("at", time(18, 0), key="entries_clock")
            wants_day = col1.date_input("Wants close on", today + timedelta(days=5))
            wants_clock = col2.time_input("at", time(18, 0), key="wants_clock")
            meet_place = st.text_input("Meeting place", placeholder="Nova SBE library")
            meet_day = col1.date_input("Meeting day", today + timedelta(days=7))
            meet_clock = col2.time_input("Meeting time", time(14, 0))
            st.caption("Times are Lisbon time.")
            submitted = st.form_submit_button("Create round")

    if not submitted:
        return
    entries_close = _to_utc_text(entries_day, entries_clock)
    wants_close = _to_utc_text(wants_day, wants_clock)
    meet_time = _to_utc_text(meet_day, meet_clock)
    decision = can_create_round(user, name, entries_close, wants_close, meet_place, meet_time)
    if not decision.allowed:
        st.error(decision.reason)
        return
    try:
        rounds_repo.create_round(name, entries_close, wants_close, meet_place, meet_time, user.id)
    except Exception:
        st.error("The round could not be saved. Please try again.")
        return
    _flash("success", f"Round “{name.strip()}” created. Students can now enter books.")


def _moderator_controls(user: Profile, round: Round, entries: list, wants: list) -> None:
    with st.container(border=True):
        st.subheader("Moderator controls")
        people = {entry.info.owner_id for entry in entries}
        st.write(f"{len(entries)} books from {len(people)} students, {len(wants)} wants ticked.")

        if round.phase == "entries":
            if st.button("Close entries and open wants"):
                _advance(user, round, "Entries are closed. Students can now choose their wants.")
        elif round.phase == "wants":
            st.caption("Running the round finds the loops, creates the swaps and notifies everyone.")
            if st.button("Run round", type="primary"):
                _run(user, round)
        elif round.phase == "matched":
            st.write(f"This round created {_loop_count(round)}.")
            _show_loops(round)
            if st.button("Close round"):
                _advance(user, round, "The round is closed.")
        else:
            st.write(f"This round is closed. It created {_loop_count(round)}.")
            _show_loops(round)


def _loop_count(round: Round) -> str:
    try:
        count = rounds_repo.count_loops(round.id)
    except Exception:
        return "an unknown number of loops"
    return f"{count} loop{'s' if count != 1 else ''}"


def _show_loops(round: Round) -> None:
    """For moderators: each loop around the circle, and who gives which book."""
    try:
        loops = rounds_repo.loops_in_round(round.id)
    except Exception:
        st.caption("The loops can't be shown right now.")
        return
    for number, trades in enumerate(loops, start=1):
        circle = " → ".join([trade.giver_name for trade in trades] + [trades[0].giver_name])
        st.write(f"**Loop {number}:** {circle}")
        st.graphviz_chart(loop_dot(trades))
        for trade in trades:
            st.caption(f"{trade.giver_name} gives “{trade.title}” to {trade.receiver_name}")
    if loops:
        st.caption("Green: handed over. Grey: waiting. Red: cancelled.")


def _advance(user: Profile, round: Round, done_message: str) -> None:
    decision = can_advance(user, round)
    if not decision.allowed:
        st.error(decision.reason)
        return
    try:
        rounds_repo.advance_round(round.id)
    except ValueError as error:
        st.error(str(error))
        return
    except Exception:
        st.error("The round could not be updated. Please try again.")
        return
    _flash("success", done_message)


def _run(user: Profile, round: Round) -> None:
    decision = can_run(user, round)
    if not decision.allowed:
        st.error(decision.reason)
        return
    try:
        result = rounds_repo.run_round(round.id)
    except ValueError as error:
        st.error(str(error))
        return
    except Exception:
        st.error("The round could not be run. Nothing was matched; please try again.")
        return

    loops = len(result.loops)
    if loops == 0:
        message = "No loops found this time. Every book is back on its owner's shelf."
    else:
        returned = result.books_returned
        message = (
            f"Found {loops} loop{'s' if loops != 1 else ''}: {result.books_swapped} books will "
            f"change hands and {returned} {'goes' if returned == 1 else 'go'} back on the shelf. "
            "Everyone has been notified."
        )
    _flash("success", message)


# --- Students: entries, wants, results ------------------------------------


def _entries_section(user: Profile, round: Round, entries: list) -> None:
    st.subheader("Enter a book")
    st.write(f"Entries close **{_show_time(round.entries_close_at)}**.")

    mine = [entry for entry in entries if entry.info.owner_id == user.id]
    if mine:
        st.write("Your books in this round:")
        for entry in mine:
            st.write(f"- {entry.title}")

    choices = rounds_repo.available_copies(user.id)
    if not choices:
        st.info("You have no available books to enter. Add one in My Shelf first.")
        return

    with st.form("enter_book_form"):
        choice = st.selectbox(
            "Your book",
            choices,
            format_func=lambda item: f"{item.title} ({CONDITIONS.get(item.copy.condition, '?')})",
        )
        submitted = st.form_submit_button("Enter this book")
    if not submitted:
        return

    decision = can_enter(user, round, choice.copy, blocked=is_blocked(user.id))
    if not decision.allowed:
        st.error(decision.reason)
        return
    try:
        rounds_repo.enter_copy(round.id, choice.copy.id)
    except ValueError as error:
        st.error(str(error))
        return
    except Exception:
        st.error("The book could not be entered. Please try again.")
        return
    _flash(
        "success",
        f"“{choice.title}” is in the round. It can't be offered elsewhere until the round is run.",
    )


def _wants_section(user: Profile, round: Round, entries: list, wants: list) -> None:
    st.subheader("Choose your wants")
    st.write(f"Wants close **{_show_time(round.wants_close_at)}**.")

    mine = [entry for entry in entries if entry.info.owner_id == user.id]
    others = [entry for entry in entries if entry.info.owner_id != user.id]
    if not mine:
        st.info("You didn't enter a book in this round, so there's nothing to choose.")
        return
    if not others:
        st.info("Nobody else has entered a book in this round.")
        return

    st.caption("Tick every book you'd accept: more ticks mean more chances of a match.")
    scores = {}
    for owner in {entry.info.owner_id for entry in others}:
        try:
            scores[owner] = swapper_score(owner).score
        except Exception:
            pass
    labels = {entry.info.id: _entry_label(entry, scores) for entry in others}
    by_id = {entry.info.id: entry for entry in entries}

    for entry in mine:
        current = [
            want.wanted_entry_id
            for want in wants
            if want.entry_id == entry.info.id and want.wanted_entry_id in labels
        ]
        with st.form(f"wants_form_{entry.info.id}"):
            st.write(f"For your **{entry.title}**, I'd accept:")
            chosen = st.multiselect(
                "Books",
                options=list(labels),
                default=current,
                format_func=labels.get,
                label_visibility="collapsed",
            )
            min_score = st.number_input(
                "Only swap with people scoring at least (0 = anyone)",
                min_value=0.0,
                max_value=5.0,
                value=float(entry.info.min_partner_score),
                step=0.25,
            )
            submitted = st.form_submit_button("Save")
            st.caption(_saved_wants_text(len(current), entry.info.min_partner_score))
        if submitted:
            _save_wants(user, round, entry, [by_id[wanted] for wanted in chosen], min_score)


def _saved_wants_text(count: int, min_score: float) -> str:
    """What is saved right now for one of my books, shown under its form."""
    if count == 0:
        return "Nothing saved yet: tick the books you'd accept, then click Save."
    text = f"✅ Saved: you'd accept {count} book{'s' if count != 1 else ''}"
    if min_score:
        text += f", from people scoring at least {min_score:.2f}"
    return text + ". You can change it until wants close."


def _save_wants(user: Profile, round: Round, entry, chosen: list, min_score: float) -> None:
    blocked = is_blocked(user.id)
    decision = can_set_min_score(user, round, entry.info, min_score, blocked=blocked)
    for wanted in chosen:
        if not decision.allowed:
            break
        decision = can_want(user, round, entry.info, wanted.info, blocked=blocked)
    if not decision.allowed:
        st.error(decision.reason)
        return
    try:
        rounds_repo.save_wants(entry.info.id, [wanted.info.id for wanted in chosen], min_score)
    except Exception:
        st.error("Your wants could not be saved. Please try again.")
        return
    count = len(chosen)
    _flash("success", f"Saved: {count} book{'s' if count != 1 else ''} you'd accept for “{entry.title}”.")


def _results_section(user: Profile, round: Round, entries: list) -> None:
    st.subheader("Your result")
    trades = rounds_repo.my_trades(round.id, user.id)
    traded = rounds_repo.traded_copy_ids(round.id)
    unmatched = [
        entry for entry in entries
        if entry.info.owner_id == user.id and entry.info.copy_id not in traded
    ]

    if not trades and not unmatched:
        st.info("You didn't take part in this round.")
        return

    if trades:
        st.success("You're in a swap loop!")
        for trade in trades:
            if trade.giver_id == user.id:
                st.write(f"**Give** “{trade.title}” to **{trade.receiver_name}**")
            else:
                st.write(f"**Receive** “{trade.title}” from **{trade.giver_name}**")
        first = trades[0]
        st.write(f"Where and when: **{first.meet_place}**, **{_show_time(first.meet_time)}**")
        st.caption("Your handoff code is on the My Swaps page.")

    for entry in unmatched:
        st.info(f"No match for “{entry.title}” this time. It's back on your shelf.")


# --- The page --------------------------------------------------------------


def main() -> None:
    user = auth.current_user()
    st.title("Swap Round")
    st.write(
        "Put books into a round and tick the ones you'd accept. The app then finds loops "
        "of students who can all swap at once, even when no two of them could swap directly."
    )
    _show_flash()

    if is_moderator(user):
        _create_round_form(user)

    try:
        rounds = rounds_repo.list_rounds()
    except Exception:
        st.error("Swap rounds are unavailable right now. Please try again later.")
        return
    if not rounds:
        hint = "Create the first one above." if is_moderator(user) else "A moderator will open one soon."
        st.info(f"No swap rounds yet. {hint}")
        return

    round = st.selectbox(
        "Round", rounds, format_func=lambda item: f"{item.name} — {PHASE_LABELS[item.phase]}"
    )
    st.write(
        f"**{PHASE_LABELS[round.phase]}** · handoffs at **{round.meet_place}**, "
        f"**{_show_time(round.meet_time)}**"
    )

    try:
        entries = rounds_repo.list_entries(round.id)
        wants = rounds_repo.get_wants(round.id)
    except Exception:
        st.error("This round couldn't be loaded. Please try again later.")
        return

    if is_moderator(user):
        _moderator_controls(user, round, entries, wants)

    if round.phase == "entries":
        _entries_section(user, round, entries)
    elif round.phase == "wants":
        _wants_section(user, round, entries, wants)
    else:
        _results_section(user, round, entries)


if __name__ == "__main__":
    main()
