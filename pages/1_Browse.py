"""Browse page: find books other students are offering.

Search by title, author or ISBN, filter by course and condition, and see each
book's condition and its owner's Swapper Score before you make an offer. Badges
(New, Trusted, Under review) are on each person's Profile page.
"""

import streamlit as st

from bookloop import auth
from bookloop.rules.copies import CONDITIONS, course_label
from bookloop.storage import copies_repo
from bookloop.storage.reviews_repo import swapper_score


CONDITION_FILTERS = {
    None: "Any condition",
    4: "Like new",
    3: "Good or better",
    2: "Fair or better",
}


def _owner_line(item: copies_repo.BrowseItem, scores: dict) -> str:
    score = scores.get(item.copy.owner_id)
    if score is None:
        return f"Offered by **{item.owner_name}**"
    return f"Offered by **{item.owner_name}** · Swapper Score {score.score:.2f}"


def _show_item(item: copies_repo.BrowseItem, scores: dict) -> None:
    book, copy = item.book, item.copy
    with st.container(border=True):
        col1, col2 = st.columns([1, 5])
        if book.cover_url:
            col1.image(book.cover_url, width=80)
        col2.write(f"**{book.title}**")
        col2.write(book.authors + (f" · {book.edition} edition" if book.edition else ""))
        col2.write(f"Condition: {CONDITIONS[copy.condition]} · highlighting: {copy.highlighting}")
        if copy.notes:
            col2.caption(copy.notes)
        if item.courses:
            col2.caption("Courses: " + ", ".join(item.courses))
        col2.write(_owner_line(item, scores))


def main() -> None:
    user = auth.current_user()
    st.title("Browse")
    st.write("Books other students are offering. To swap one, make an offer on the Offers page.")

    try:
        courses = copies_repo.list_courses()
    except Exception:
        st.error("Browse is unavailable right now. Please try again later.")
        return

    query = st.text_input("Search by title, author or ISBN")
    col1, col2 = st.columns(2)
    course_names = {course.id: course_label(course.code, course.name) for course in courses}
    course_id = col1.selectbox(
        "Course", [None, *course_names], format_func=lambda id: "All courses" if id is None else course_names[id]
    )
    min_condition = col2.selectbox("Condition", list(CONDITION_FILTERS), format_func=CONDITION_FILTERS.get)

    try:
        items = copies_repo.search_available(query, course_id, min_condition, exclude_owner_id=user.id)
        scores = {owner: swapper_score(owner) for owner in {item.copy.owner_id for item in items}}
    except Exception:
        st.error("Browse is unavailable right now. Please try again later.")
        return

    if not items:
        if query.strip() or course_id or min_condition:
            st.info(
                "No books match your search. Try fewer words, or add the book to your wishlist "
                "on My Shelf to get a notification when someone lists it."
            )
        else:
            st.info("No books listed yet. Add yours on My Shelf.")
        return

    st.caption(f"{len(items)} book{'s' if len(items) != 1 else ''} available")
    for item in items:
        _show_item(item, scores)


if __name__ == "__main__":
    main()
