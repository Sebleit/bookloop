from datetime import datetime, timezone

import streamlit as st

from bookloop import auth
from bookloop.storage.swaps_repo import (
    confirm_handoff,
    loop_participants,
    report_no_show,
    trades_for_user,
)

FLASH_KEY = "my_swaps_message"


def _show_time(value: str | None) -> str:
    """Show a stored UTC timestamp in Lisbon time, like 'Sun 22 Nov, 11:00'."""
    if not value:
        return "To be arranged"
    try:
        from zoneinfo import ZoneInfo

        zone = ZoneInfo("Europe/Lisbon")
    except Exception:
        zone = timezone.utc  # the same as Lisbon in winter
    moment = datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(zone)
    return moment.strftime("%a %d %b, %H:%M")


def _flash(message: str) -> None:
    """Remember a message, then reload the page so it shows the latest data."""
    st.session_state[FLASH_KEY] = message
    st.rerun()


def main() -> None:
    user = auth.current_user()
    st.title("My Swaps")
    message = st.session_state.pop(FLASH_KEY, None)
    if message:
        st.success(message)
    st.write("Your upcoming handoffs and their meeting details.")
    st.page_link("pages/6_Profile.py", label="Open your Profile to leave a review")

    try:
        swaps = trades_for_user(user.id)
    except Exception:
        st.error("Swaps are unavailable right now. Please try again later.")
        return

    if not swaps:
        st.info("No upcoming handoffs.")
        return

    # In every swap you both give and receive, so the same swap appears twice here.
    # The no-show button is drawn only once per swap.
    swaps_with_button = set()
    for item in swaps:
        trade = item["trade"]
        st.subheader(item["title"])
        st.write(f"Place: {item['meet_place'] or 'To be arranged'}")
        st.write(f"Time: {_show_time(item['meet_time'])}")

        if trade.receiver_id == user.id:
            st.code(trade.handoff_code, language="text")
            st.caption("Show this code to the person giving you the book.")
        elif trade.giver_id == user.id:
            with st.form(f"handoff-{trade.id}"):
                entered_code = st.text_input("Receiver's 4-digit code")
                submitted = st.form_submit_button("Confirm handoff")
            if submitted:
                try:
                    decision = confirm_handoff(trade.id, user.id, entered_code)
                except ValueError as error:
                    st.error(str(error))
                else:
                    if decision.allowed:
                        _flash("Handoff confirmed. The book now belongs to the receiver.")
                    else:
                        st.error(decision.reason)

        if trade.loop_id in swaps_with_button:
            continue
        swaps_with_button.add(trade.loop_id)
        participants = [
            participant
            for participant in loop_participants(trade.loop_id)
            if participant["id"] != user.id
        ]
        if not participants:
            continue
        # In a round loop there are several other people: ask which one didn't come.
        no_show_user = participants[0]
        if len(participants) > 1:
            no_show_user = st.selectbox(
                "If someone doesn't come, who was it?",
                participants,
                format_func=lambda participant: participant["display_name"],
                key=f"no-show-who-{trade.loop_id}",
            )
        if st.button("Report no-show", key=f"no-show-{trade.loop_id}"):
            try:
                report_no_show(trade.loop_id, user.id, no_show_user["id"])
            except ValueError as error:
                st.error(str(error))
            else:
                _flash(f"Swap cancelled. {no_show_user['display_name']} was recorded as a no-show.")


if __name__ == "__main__":
    main()
