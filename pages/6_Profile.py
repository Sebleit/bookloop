"""Profile page.

Anyone's profile shows their Swapper Score, badge, accuracy, the reviews they
received (with replies) and their swap history. On your own profile you also
see the swaps waiting for your review, with the review form, and you can
reply once to each review about you.
"""

from datetime import datetime

import streamlit as st

from bookloop import auth
from bookloop.models import Profile
from bookloop.rules.reviews import (
    CONDITIONS,
    can_reply,
    can_review,
    check_review_details,
    is_visible,
)
from bookloop.storage import reviews_repo


FLASH_KEY = "profile_message"
CONDITION_ORDER = [4, 3, 2, 1]  # like new first


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
    else:
        st.error(text)


def _stars(count: int) -> str:
    return "★" * count + "☆" * (5 - count)


def _show_date(value: str | None) -> str:
    if not value:
        return ""
    return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime("%d %b %Y")


# --- Score and badge -------------------------------------------------------


def _header(person: Profile, own: bool, review_count: int) -> None:
    result = reviews_repo.swapper_score(person.id)
    st.subheader(person.display_name)
    col1, col2, col3 = st.columns(3)
    col1.metric("Swapper Score", f"{result.score:.2f}")
    col2.metric("Accuracy", f"{result.accuracy:.0f}%" if review_count else "—")
    col3.metric("Badge", result.badge or "—")
    st.caption(
        f"Based on {review_count} review{'s' if review_count != 1 else ''}. Everyone starts "
        "as if they had 3 reviews of 4 stars, so one review can't make a score perfect."
    )
    if own and person.status == "under_review":
        st.warning(
            "Your account is under review after recent reviews. Until a moderator clears it, "
            "you can't make offers or join swap rounds."
        )
    elif own and person.status == "suspended":
        st.error("Your account is suspended. You can't make offers or join swap rounds.")


# --- Writing reviews (own profile) ----------------------------------------


def _reviews_to_write(user: Profile) -> None:
    st.subheader("Swaps waiting for your review")
    waiting = [
        item for item in reviews_repo.trades_to_review(user.id)
        if can_review(user, item.trade, already_reviewed=False).allowed
    ]
    if not waiting:
        st.caption("No swaps waiting for your review.")
        return

    st.caption(
        "Reviews can't be changed after you submit them. Your review stays hidden until "
        "everyone in the swap has reviewed, or for 7 days, so nobody can review in revenge."
    )
    for item in waiting:
        with st.form(f"review_form_{item.trade.id}"):
            st.write(
                f"**{item.title}** from **{item.giver_name}**, listed as "
                f"*{CONDITIONS[item.listed_condition]}*"
            )
            stars = st.select_slider("Stars", options=[1, 2, 3, 4, 5], value=5)
            described = st.radio("Was the condition as described?", ["Yes", "No"], horizontal=True)
            actual = st.selectbox(
                "Actual condition",
                CONDITION_ORDER,
                index=CONDITION_ORDER.index(item.listed_condition),
                format_func=CONDITIONS.get,
            )
            comment = st.text_area("Comment (required for 1 or 2 stars)", max_chars=500)
            submitted = st.form_submit_button("Submit review")
        if submitted:
            _submit_review(user, item, stars, described == "Yes", actual, comment)


def _submit_review(user: Profile, item, stars: int, as_described: bool, actual: int, comment: str) -> None:
    trade = reviews_repo.get_trade(item.trade.id)  # fresh copy, in case it changed
    decision = can_review(user, trade, reviews_repo.has_review(trade.id))
    if decision.allowed:
        decision = check_review_details(stars, actual, comment)
    if not decision.allowed:
        st.error(decision.reason)
        return
    try:
        saved = reviews_repo.save_review(trade, stars, as_described, actual, comment)
    except Exception:
        st.error("Your review could not be saved. Please try again.")
        return

    message = f"Thanks! Your review of {item.giver_name} is saved."
    if is_visible(saved.review.visible_from):
        message += " Everyone in the swap has now reviewed, so the reviews are visible."
    else:
        message += " It will appear once everyone in the swap has reviewed, or in 7 days."
    if saved.flagged:
        message += " The book arrived 2+ levels worse than listed, so a moderator will check the swap."
    _flash("success", message)


# --- Reviews received ------------------------------------------------------


def _reviews_received(user: Profile, person: Profile, own: bool, views: list) -> None:
    st.subheader("Reviews received")
    if not views:
        st.caption("No reviews yet." if not own else "No reviews yet. They appear here after your swaps.")
        return

    for view in views:
        review = view.review
        with st.container(border=True):
            st.write(
                f"{_stars(review.stars)} · **{view.reviewer_name}** on "
                f"“{view.title}” · {_show_date(review.created_at)}"
            )
            if review.as_described:
                st.write("Condition as described.")
            else:
                st.write(f"Not as described: it arrived *{CONDITIONS[review.actual_condition]}*.")
            if review.comment:
                st.write(f"“{review.comment}”")
            if review.reply:
                st.caption(f"Reply from {person.display_name}: {review.reply}")
            elif own:
                _reply_form(user, review)


def _reply_form(user: Profile, review) -> None:
    with st.form(f"reply_form_{review.id}"):
        reply = st.text_input("Reply (you can reply once)", max_chars=500)
        submitted = st.form_submit_button("Post reply")
    if not submitted:
        return
    decision = can_reply(user, review, reply)
    if not decision.allowed:
        st.error(decision.reason)
        return
    try:
        reviews_repo.save_reply(review.id, reply)
    except ValueError as error:
        st.error(str(error))
        return
    except Exception:
        st.error("Your reply could not be saved. Please try again.")
        return
    _flash("success", "Your reply is posted.")


# --- Swap history ----------------------------------------------------------


def _history(person: Profile) -> None:
    st.subheader("Swap history")
    items = reviews_repo.swap_history(person.id)
    if not items:
        st.caption("No swaps yet.")
        return
    st.dataframe(
        [
            {
                "Date": _show_date(item.date),
                "Book": item.title,
                "": "Gave to" if item.gave else "Received from",
                "With": item.other_name,
                "Status": item.status,
            }
            for item in items
        ],
        hide_index=True,
    )


# --- The page --------------------------------------------------------------


def main() -> None:
    user = auth.current_user()
    st.title("Profile")
    _show_flash()

    try:
        profiles = reviews_repo.list_profiles()
    except Exception:
        st.error("Profiles are unavailable right now. Please try again later.")
        return
    by_id = {profile.id: profile for profile in profiles}
    ids = list(by_id)
    if user.id not in by_id:
        st.error("Your profile couldn't be found. Please log in again.")
        return

    chosen = st.selectbox(
        "Whose profile",
        ids,
        index=ids.index(user.id),
        format_func=lambda id: "You" if id == user.id else by_id[id].display_name,
    )
    person = by_id[chosen]
    own = person.id == user.id

    try:
        views = reviews_repo.reviews_about(person.id)
        _header(person, own, len(views))
        if own:
            _reviews_to_write(by_id[user.id])
        _reviews_received(by_id[user.id], person, own, views)
        _history(person)
    except Exception:
        st.error("This profile couldn't be loaded. Please try again later.")


if __name__ == "__main__":
    main()
