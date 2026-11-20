from datetime import datetime, timedelta, timezone

import streamlit as st

from bookloop import auth
from bookloop.rules.offers import can_make_offer
from bookloop.storage.reviews_repo import is_blocked
from bookloop.storage.swaps_repo import (
    available_copies,
    create_offer,
    pending_offer_count,
)


def _copy_label(item: dict) -> str:
    copy = item["copy"]
    return f"{item['title']} — condition {copy.condition}, copy {copy.id}"


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


if __name__ == "__main__":
    main()
