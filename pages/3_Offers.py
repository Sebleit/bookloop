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


def _copy_label(item: dict) -> str:
    copy = item["copy"]
    condition = CONDITIONS.get(copy.condition, "unknown condition")
    return f"{item['title']} — condition: {condition}, owner: {item['owner_name']}"


def main() -> None:
    user = auth.current_user()
    st.title("Offers")
    st.write("Offer one of your available copies for another student's copy.")

    try:
        my_copies = available_copies(owner_id=user.id)
        requested_copies = available_copies(exclude_owner_id=user.id)
    except Exception:
        st.error("Offers are unavailable right now. Please try again later.")
        return

    if not my_copies:
        st.info("You have no available copies to offer yet.")
        return
    if not requested_copies:
        st.info("There are no other available copies to request yet.")
        return

    with st.form("make_offer_form"):
        offered_item = st.selectbox("Your copy", my_copies, format_func=_copy_label)
        requested_item = st.selectbox(
            "Copy you want", requested_copies, format_func=_copy_label
        )
        submitted = st.form_submit_button("Make offer")

    if not submitted:
        _show_existing_offers(user.id)
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
    st.success("Offer sent successfully.")
    _show_existing_offers(user.id)


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
            text = f"Incoming: {row['offered_title']} for your {row['requested_title']}"
        else:
            text = f"Outgoing: your {row['offered_title']} for {row['requested_title']}"
        st.write(f"{text} — {offer.status}")

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
                    st.success("Offer accepted and both copies reserved.")
                    st.rerun()
                except Exception as error:
                    st.error(str(error))
            elif decline_clicked:
                try:
                    decline_offer(offer, user_id)
                    st.success("Offer declined.")
                    st.rerun()
                except Exception as error:
                    st.error(str(error))
        else:
            if st.button("Cancel", key=f"cancel-{offer.id}"):
                try:
                    cancel_offer(offer, user_id)
                    st.success("Offer cancelled.")
                    st.rerun()
                except Exception as error:
                    st.error(str(error))


if __name__ == "__main__":
    main()
