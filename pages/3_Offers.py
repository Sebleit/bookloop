from datetime import date, datetime, time, timedelta, timezone

import streamlit as st

from bookloop import auth
from bookloop.rules.copies import CONDITIONS
from bookloop.rules.offers import can_make_offer, check_meeting
from bookloop.services.notify import notify
from bookloop.storage.reviews_repo import is_blocked, swapper_score
from bookloop.storage.swaps_repo import (
    accept_offer,
    available_copies,
    cancel_offer,
    create_offer,
    decline_offer,
    offers_for_user,
    pending_offer_count,
)


FLASH_KEY = "offers_message"
# What each offer status means, in words.
STATUS_WORDS = {
    "pending": "waiting for an answer",
    "accepted": "accepted: the handoff is in My Swaps",
    "declined": "declined",
    "cancelled": "cancelled",
    "expired": "expired after 72 hours",
}


DEFAULT_PLACE = "Nova SBE library, ground floor"


def _my_copy_label(item: dict) -> str:
    return f"{item['title']} ({CONDITIONS.get(item['copy'].condition, '?')})"


def _score_text(user_id: str, scores: dict[str, float | None]) -> str:
    """'Swapper Score 4.00', worked out once per person on this page."""
    if user_id not in scores:
        try:
            scores[user_id] = swapper_score(user_id).score
        except Exception:
            scores[user_id] = None
    value = scores[user_id]
    return "Swapper Score unknown" if value is None else f"Swapper Score {value:.2f}"


def _local_zone():
    """Lisbon time if this computer knows it, otherwise UTC (the same in winter)."""
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo("Europe/Lisbon")
    except Exception:
        return timezone.utc


def _to_utc_text(day: date, clock: time) -> str:
    """A day and time typed in Lisbon time, as the UTC timestamp the database keeps."""
    moment = datetime.combine(day, clock, tzinfo=_local_zone()).astimezone(timezone.utc)
    return moment.isoformat().replace("+00:00", "Z")


def _show_time(value: str) -> str:
    """'Tue 24 Nov, 14:00' in Lisbon time."""
    moment = datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(_local_zone())
    return moment.strftime("%a %d %b, %H:%M")


def _flash(message: str) -> None:
    """Remember a message, then reload the page so the list shows the change."""
    st.session_state[FLASH_KEY] = message
    st.rerun()


def main() -> None:
    user = auth.current_user()
    st.title("Offers")
    message = st.session_state.pop(FLASH_KEY, None)
    if message:
        st.success(message)
        st.toast(message, icon="✅")  # also pops up in the corner, wherever you've scrolled
    st.write("Swap one of your books for one of someone else's, one for one.")

    try:
        my_copies = available_copies(owner_id=user.id)
        requested_copies = available_copies(exclude_owner_id=user.id)
    except Exception:
        st.error("Offers are unavailable right now. Please try again later.")
        return

    scores: dict[str, float | None] = {}  # each person's Swapper Score, looked up once
    # The form to make an offer, when there's something to swap; your offers always.
    if not my_copies:
        st.info("You have no available books to offer yet. Add one on My Shelf.")
    elif not requested_copies:
        st.info("There are no other available books to ask for yet.")
    else:
        _make_offer_form(user, my_copies, requested_copies, scores)
    _show_existing_offers(user, scores)


def _make_offer_form(user, my_copies: list, requested_copies: list, scores: dict) -> None:
    def their_copy_label(item: dict) -> str:
        owner = f"{item['owner_name']} ({_score_text(item['copy'].owner_id, scores)})"
        return f"{_my_copy_label(item)} from {owner}"

    with st.form("make_offer_form"):
        offered_item = st.selectbox("Your book", my_copies, format_func=_my_copy_label)
        requested_item = st.selectbox(
            "The book you want", requested_copies, format_func=their_copy_label
        )
        submitted = st.form_submit_button("Make offer")
    if not submitted:
        return

    offered_copy = offered_item["copy"]
    requested_copy = requested_item["copy"]
    decision = can_make_offer(
        user.id,
        offered_copy,
        requested_copy,
        pending_offer_count(user.id),
        blocked=is_blocked(user.id),
    )
    if not decision.allowed:
        st.error(decision.reason)
        return

    expires_at = (
        datetime.now(timezone.utc) + timedelta(hours=72)
    ).isoformat().replace("+00:00", "Z")
    try:
        create_offer(user.id, offered_copy.id, requested_copy.id, expires_at)
    except Exception:
        st.error("The offer could not be saved. Please try again.")
        return
    _flash(
        f"Offer sent to {requested_item['owner_name']}: your “{offered_item['title']}” for their "
        f"“{requested_item['title']}”. They have 72 hours to answer."
    )


def _show_existing_offers(user, scores: dict) -> None:
    user_id = user.id
    st.subheader("Your offers")
    try:
        rows = offers_for_user(user_id)
    except Exception:
        st.error("Offers are unavailable right now. Please try again later.")
        return

    if not rows:
        st.info("No offers yet.")
        return

    for row in rows:
        offer = row["offer"]
        is_incoming = row["requested_owner_id"] == user_id and offer.proposer_id != user_id
        if is_incoming:
            text = (
                f"**{row['proposer_name']}** ({_score_text(offer.proposer_id, scores)}) offers you "
                f"“{row['offered_title']}” for your “{row['requested_title']}”"
            )
        else:
            text = (
                f"You offered your “{row['offered_title']}” for "
                f"**{row['requested_owner_name']}**'s “{row['requested_title']}”"
            )
        st.write(f"{text} · {STATUS_WORDS.get(offer.status, offer.status)}")

        if offer.status != "pending":
            continue
        if is_incoming:
            _answer_offer(user, row)
        else:
            if st.button("Cancel", key=f"cancel-{offer.id}"):
                try:
                    cancel_offer(offer, user_id)
                except Exception as error:
                    st.error(str(error))
                else:
                    _flash("Offer cancelled.")


def _answer_offer(user, row: dict) -> None:
    """Accept (saying where and when to meet) or decline an offer made to you."""
    offer = row["offer"]
    with st.form(f"accept-{offer.id}"):
        st.caption("To accept, say where and when you'll meet. Both of you will see it in My Swaps.")
        place = st.text_input("Meeting place", value=DEFAULT_PLACE, key=f"place-{offer.id}")
        col1, col2 = st.columns(2)
        day = col1.date_input("Day", value=date.today() + timedelta(days=1), key=f"day-{offer.id}")
        clock = col2.time_input("Time (Lisbon)", value=time(14, 0), key=f"time-{offer.id}")
        accepted = st.form_submit_button("Accept")
    declined = st.button("Decline", key=f"decline-{offer.id}")

    if accepted:
        meet_time = _to_utc_text(day, clock)
        decision = check_meeting(place, meet_time)
        if not decision.allowed:
            st.error(decision.reason)
            return
        try:
            offered_copy = next(
                item["copy"]
                for item in available_copies(exclude_owner_id=user.id)
                if item["copy"].id == offer.offered_copy_id
            )
            requested_copy = next(
                item["copy"]
                for item in available_copies(owner_id=user.id)
                if item["copy"].id == offer.requested_copy_id
            )
            accept_offer(offer, user.id, offered_copy, requested_copy, place.strip(), meet_time)
        except StopIteration:
            st.error("One of these books isn't available any more.")
            return
        except Exception as error:
            st.error(str(error))
            return
        when = f"{place.strip()}, {_show_time(meet_time)}"
        notify(
            offer.proposer_id,
            f"{user.display_name} accepted your offer: your “{row['offered_title']}” for their "
            f"“{row['requested_title']}”. You meet at {when}. The handoff is in My Swaps.",
            None,
        )
        _flash(
            f"Swap agreed with {row['proposer_name']}: you give “{row['requested_title']}” and get "
            f"“{row['offered_title']}”. You meet at {when}. The handoff is in My Swaps."
        )
    elif declined:
        try:
            decline_offer(offer, user.id)
        except Exception as error:
            st.error(str(error))
        else:
            _flash(f"Offer from {row['proposer_name']} declined.")


if __name__ == "__main__":
    main()
