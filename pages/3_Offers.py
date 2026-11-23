from datetime import datetime, timedelta, timezone

import streamlit as st

from bookloop import auth
from bookloop.rules.copies import CONDITIONS
from bookloop.rules.offers import can_make_offer
from bookloop.storage.reviews_repo import is_blocked
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


def _my_copy_label(item: dict) -> str:
    return f"{item['title']} ({CONDITIONS.get(item['copy'].condition, '?')})"


def _their_copy_label(item: dict) -> str:
    return f"{_my_copy_label(item)} from {item['owner_name']}"


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

    # The form to make an offer, when there's something to swap; your offers always.
    if not my_copies:
        st.info("You have no available books to offer yet. Add one on My Shelf.")
    elif not requested_copies:
        st.info("There are no other available books to ask for yet.")
    else:
        _make_offer_form(user, my_copies, requested_copies)
    _show_existing_offers(user.id)


def _make_offer_form(user, my_copies: list, requested_copies: list) -> None:
    with st.form("make_offer_form"):
        offered_item = st.selectbox("Your book", my_copies, format_func=_my_copy_label)
        requested_item = st.selectbox(
            "The book you want", requested_copies, format_func=_their_copy_label
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


def _show_existing_offers(user_id: str) -> None:
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
                f"**{row['proposer_name']}** offers you “{row['offered_title']}” "
                f"for your “{row['requested_title']}”"
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
            accept_key = f"accept-{offer.id}"
            decline_key = f"decline-{offer.id}"
            accept_clicked = st.button("Accept", key=accept_key)
            decline_clicked = st.button("Decline", key=decline_key)
            if accept_clicked:
                try:
                    offered_copy = next(
                        item["copy"]
                        for item in available_copies(exclude_owner_id=user_id)
                        if item["copy"].id == offer.offered_copy_id
                    )
                    requested_copy = next(
                        item["copy"]
                        for item in available_copies(owner_id=user_id)
                        if item["copy"].id == offer.requested_copy_id
                    )
                    accept_offer(offer, user_id, offered_copy, requested_copy)
                except StopIteration:
                    st.error("One of these books isn't available any more.")
                except Exception as error:
                    st.error(str(error))
                else:
                    _flash(
                        f"Swap agreed with {row['proposer_name']}: you give “{row['requested_title']}” "
                        f"and get “{row['offered_title']}”. Agree where and when to meet; "
                        "the handoff is in My Swaps."
                    )
            elif decline_clicked:
                try:
                    decline_offer(offer, user_id)
                except Exception as error:
                    st.error(str(error))
                else:
                    _flash(f"Offer from {row['proposer_name']} declined.")
        else:
            if st.button("Cancel", key=f"cancel-{offer.id}"):
                try:
                    cancel_offer(offer, user_id)
                except Exception as error:
                    st.error(str(error))
                else:
                    _flash("Offer cancelled.")


if __name__ == "__main__":
    main()
