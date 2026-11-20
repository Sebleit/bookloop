import streamlit as st

from bookloop import auth
from bookloop.storage.swaps_repo import confirm_handoff, trades_for_user


def main() -> None:
    user = auth.current_user()
    st.title("My Swaps")
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

    for item in swaps:
        trade = item["trade"]
        st.subheader(item["title"])
        st.write(f"Place: {item['meet_place'] or 'To be arranged'}")
        st.write(f"Time: {item['meet_time'] or 'To be arranged'}")

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
                        st.success("Handoff confirmed. The book now belongs to the receiver.")
                        st.rerun()
                    else:
                        st.error(decision.reason)


if __name__ == "__main__":
    main()
