"""Moderator page (moderators only).

- Flagged swaps: books that arrived 2+ levels worse than listed.
- Users: people under review or suspended, to clear or suspend.
- Reviews: hide an abusive review, with a reason.
- Log: every moderator action, plus the automatic flags.

Every action is checked by a rule first and saved in audit_log.
"""

from datetime import datetime

import streamlit as st

from bookloop import auth
from bookloop.loop_picture import loop_dot
from bookloop.models import Profile
from bookloop.rules.reputation import can_change_status
from bookloop.rules.reviews import CONDITIONS, can_hide_review, can_resolve_flag
from bookloop.storage import reviews_repo, rounds_repo


FLASH_KEY = "moderator_message"
STATUS_LABELS = {"active": "Active", "under_review": "Under review", "suspended": "Suspended"}


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


def _stars(count: int) -> str:
    return "★" * count + "☆" * (5 - count)


def _show_time(value: str) -> str:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime("%d %b %Y, %H:%M")


# --- Actions ---------------------------------------------------------------


def _change_status(moderator: Profile, person: Profile, new_status: str) -> None:
    decision = can_change_status(moderator, person, new_status)
    if not decision.allowed:
        st.error(decision.reason)
        return
    try:
        reviews_repo.set_user_status(moderator.id, person.id, new_status)
    except Exception:
        st.error("The status could not be changed. Please try again.")
        return
    done = "cleared: they can swap again" if new_status == "active" else "suspended"
    _flash("success", f"{person.display_name} has been {done}.")


def _resolve(moderator: Profile, trade_id: str) -> None:
    decision = can_resolve_flag(moderator)
    if not decision.allowed:
        st.error(decision.reason)
        return
    try:
        reviews_repo.resolve_flag(moderator.id, trade_id)
    except Exception:
        st.error("The flag could not be resolved. Please try again.")
        return
    _flash("success", "Flag resolved.")


# --- Tabs ------------------------------------------------------------------


def _flags_tab(moderator: Profile) -> None:
    problems = reviews_repo.problem_reports()
    flags = reviews_repo.flagged_swaps()
    if not problems and not flags:
        st.info("No flagged swaps right now.")
        return
    if problems:
        st.subheader("Books not handed over")
        st.caption(
            "Someone in these swaps says a person didn't hand over their book. "
            "The picture shows which books have changed hands."
        )
        for problem in problems:
            with st.container(border=True):
                st.write(
                    f"**{problem.reporter_name}** says **{problem.giver_name}** didn't hand over "
                    f"“{problem.title}” ({problem.giver_name} → {problem.receiver_name})."
                )
                st.graphviz_chart(loop_dot(rounds_repo.loop_trades(problem.loop_id)))
                st.caption(f"Reported {_show_time(problem.reported_at)}")
                col1, col2 = st.columns(2)
                if col1.button("Mark as resolved", key=f"resolve_problem_{problem.trade_id}"):
                    _resolve(moderator, problem.trade_id)
                if col2.button(f"Suspend {problem.giver_name}", key=f"suspend_problem_{problem.trade_id}"):
                    _change_status(moderator, reviews_repo.get_profile(problem.giver_id), "suspended")
    if not flags:
        return
    if problems:
        st.subheader("Books worse than described")
    st.caption("These books arrived 2 or more levels worse than their listing said.")
    for flag in flags:
        with st.container(border=True):
            st.write(
                f"**{flag.title}**: {flag.giver_name} → {flag.receiver_name}, arrived "
                f"*{CONDITIONS[flag.actual_condition]}* · {_stars(flag.stars)}"
            )
            if flag.comment:
                st.write(f"“{flag.comment}”")
            st.caption(f"Flagged {_show_time(flag.flagged_at)}")
            col1, col2 = st.columns(2)
            if col1.button("Mark as resolved", key=f"resolve_{flag.trade_id}"):
                _resolve(moderator, flag.trade_id)
            if col2.button(f"Suspend {flag.giver_name}", key=f"suspend_flag_{flag.trade_id}"):
                giver = reviews_repo.get_profile(flag.giver_id)
                _change_status(moderator, giver, "suspended")


def _users_tab(moderator: Profile) -> None:
    people = reviews_repo.users_needing_attention()
    if not people:
        st.info("Nobody is under review or suspended.")
        return
    for person in people:
        result = reviews_repo.swapper_score(person.id)
        with st.container(border=True):
            st.write(
                f"**{person.display_name}** · {STATUS_LABELS[person.status]} · "
                f"score {result.score:.2f}, accuracy {result.accuracy:.0f}%"
            )
            col1, col2 = st.columns(2)
            if col1.button("Clear", key=f"clear_{person.id}"):
                _change_status(moderator, person, "active")
            if person.status != "suspended" and col2.button("Suspend", key=f"suspend_{person.id}"):
                _change_status(moderator, person, "suspended")


def _reviews_tab(moderator: Profile) -> None:
    views = reviews_repo.recent_reviews()
    if not views:
        st.info("No reviews yet.")
        return
    st.caption("Hide a review only if it's abusive. Hidden reviews stop counting in the score.")
    with st.form("hide_review_form"):
        chosen = st.selectbox(
            "Review",
            views,
            format_func=lambda view: (
                f"{view.reviewer_name} about {view.reviewee_name}: {_stars(view.review.stars)} "
                f"“{(view.review.comment or 'no comment')[:60]}”"
            ),
        )
        reason = st.text_input("Reason for hiding it")
        submitted = st.form_submit_button("Hide review")
    if not submitted:
        return
    decision = can_hide_review(moderator, chosen.review, reason)
    if not decision.allowed:
        st.error(decision.reason)
        return
    try:
        reviews_repo.hide_review(moderator.id, chosen.review.id, reason)
    except ValueError as error:
        st.error(str(error))
        return
    except Exception:
        st.error("The review could not be hidden. Please try again.")
        return
    _flash("success", f"The review by {chosen.reviewer_name} is hidden and no longer counts.")


def _log_tab() -> None:
    entries = reviews_repo.audit_entries()
    if not entries:
        st.info("No moderator actions yet.")
        return
    names = {profile.id: profile.display_name for profile in reviews_repo.list_profiles()}
    st.dataframe(
        [
            {
                "When": _show_time(item.entry.created_at),
                "Who": item.actor_name,
                "Action": item.entry.action,
                "On": names.get(item.entry.target_id, f"{item.entry.target_table} {item.entry.target_id}"),
            }
            for item in entries
        ],
        hide_index=True,
    )


# --- The page --------------------------------------------------------------


def main() -> None:
    moderator = auth.require_role("moderator")
    st.title("Moderator")
    _show_flash()

    flags_tab, users_tab, reviews_tab, log_tab = st.tabs(["Flagged swaps", "Users", "Reviews", "Log"])
    try:
        with flags_tab:
            _flags_tab(moderator)
        with users_tab:
            _users_tab(moderator)
        with reviews_tab:
            _reviews_tab(moderator)
        with log_tab:
            _log_tab()
    except Exception:
        st.error("The moderator tools couldn't be loaded. Please try again later.")


if __name__ == "__main__":
    main()
