import streamlit as st

from bookloop import auth
from bookloop.storage.stats_repo import community_stats, stats_csv


def main() -> None:
    auth.require_role("moderator")
    st.title("Stats")

    try:
        stats = community_stats()
    except Exception:
        st.error("Statistics are unavailable right now. Please try again later.")
        return

    first, second, third = st.columns(3)
    first.metric("Books listed", stats["listed_copies"])
    second.metric("Swaps completed", stats["completed_swaps"])
    third.metric("Average score", f"{stats['average_score']:.2f}")

    st.subheader("Most-wanted books")
    if stats["most_wanted"]:
        st.table(stats["most_wanted"])
    else:
        st.info("No wishlist entries yet.")

    st.download_button(
        "Download CSV",
        data=stats_csv(stats),
        file_name="bookloop-stats.csv",
        mime="text/csv",
    )


if __name__ == "__main__":
    main()
