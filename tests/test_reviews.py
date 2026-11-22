"""Tests for the review rules in bookloop/rules/reviews.py.

Users come from the shared factories in conftest.py. Trades and reviews are
only needed in memory here, so the helpers below build them. All times are
fixed so the tests give the same result on any day.
"""

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import text
from streamlit.testing.v1 import AppTest

from bookloop.models import Profile, Review, Trade
from bookloop.rules.reviews import (
    can_hide_review,
    can_reply,
    can_resolve_flag,
    can_review,
    check_review_details,
    is_misdescribed,
    is_visible,
    needs_comment,
    review_visible_from,
)
from bookloop.services.notify import get_notifications
from bookloop.storage import db, reviews_repo
from seed import base as seed_base
from seed import reviews as seed_reviews


COMPLETED = "2026-11-10T14:00:00Z"
NEXT_DAY = "2026-11-11T14:00:00Z"


def a_trade(giver_id: str, receiver_id: str, status: str = "completed") -> Trade:
    return Trade(
        id="trade-1",
        loop_id="loop-1",
        copy_id="copy-1",
        giver_id=giver_id,
        receiver_id=receiver_id,
        handoff_code="1234",
        code_attempts=0,
        status=status,
        completed_at=COMPLETED if status == "completed" else None,
    )


def a_review(
    reviewer_id: str,
    reviewee_id: str,
    reply: str | None = None,
    visible_from: str | None = None,
    hidden: bool = False,
) -> Review:
    return Review(
        id="review-1",
        trade_id="trade-1",
        reviewer_id=reviewer_id,
        reviewee_id=reviewee_id,
        stars=2,
        as_described=False,
        actual_condition=1,
        comment="Torn cover.",
        reply=reply,
        visible_from=visible_from,
        hidden_by_moderator=hidden,
        hidden_reason="Abusive" if hidden else None,
        created_at=COMPLETED,
    )


# --- Who can review --------------------------------------------------------


def test_the_receiver_can_review_a_completed_trade(make_user):
    ana, ben = make_user(name="Ana"), make_user(name="Ben")
    trade = a_trade(giver_id=ana.id, receiver_id=ben.id)

    assert can_review(ben, trade, already_reviewed=False, now=NEXT_DAY).allowed is True


def test_the_giver_cannot_review_and_the_trade_is_unchanged(make_user):
    ana, ben = make_user(name="Ana"), make_user(name="Ben")
    trade = a_trade(giver_id=ana.id, receiver_id=ben.id)
    before = deepcopy(trade)

    decision = can_review(ana, trade, already_reviewed=False, now=NEXT_DAY)

    assert decision.allowed is False
    assert decision.reason == "Only the person who received the book can review it."
    assert trade == before


def test_a_trade_cannot_be_reviewed_twice(make_user):
    ana, ben = make_user(name="Ana"), make_user(name="Ben")
    trade = a_trade(giver_id=ana.id, receiver_id=ben.id)

    decision = can_review(ben, trade, already_reviewed=True, now=NEXT_DAY)

    assert decision.reason == "You've already reviewed this swap. Reviews can't be changed."


def test_cancelled_and_unfinished_trades_cannot_be_reviewed(make_user):
    ana, ben = make_user(name="Ana"), make_user(name="Ben")

    for status in ("cancelled", "pending"):
        trade = a_trade(giver_id=ana.id, receiver_id=ben.id, status=status)
        decision = can_review(ben, trade, already_reviewed=False, now=NEXT_DAY)
        assert decision.reason == "Only completed swaps can be reviewed."


def test_reviews_close_14_days_after_the_swap(make_user):
    ana, ben = make_user(name="Ana"), make_user(name="Ben")
    trade = a_trade(giver_id=ana.id, receiver_id=ben.id)

    on_the_last_moment = can_review(ben, trade, already_reviewed=False, now="2026-11-24T14:00:00Z")
    one_second_late = can_review(ben, trade, already_reviewed=False, now="2026-11-24T14:00:01Z")

    assert on_the_last_moment.allowed is True
    assert one_second_late.reason == "Reviews must be written within 14 days of the swap."


# --- What a review must contain --------------------------------------------


def test_a_normal_review_is_accepted():
    assert check_review_details(stars=4, actual_condition=3, comment=None).allowed is True


def test_stars_must_be_between_1_and_5():
    assert check_review_details(0, 3, "Fine").reason == "Stars must be between 1 and 5."
    assert check_review_details(6, 3, "Fine").reason == "Stars must be between 1 and 5."


def test_low_ratings_need_a_comment():
    assert needs_comment(1) is True
    assert needs_comment(2) is True
    assert needs_comment(3) is False

    no_comment = check_review_details(stars=1, actual_condition=1, comment=None)
    only_spaces = check_review_details(stars=2, actual_condition=2, comment="   ")

    assert no_comment.allowed is False
    assert only_spaces.reason.startswith("Please add a comment")


def test_comments_can_be_up_to_500_characters():
    assert check_review_details(2, 2, "x" * 500).allowed is True
    assert check_review_details(2, 2, "x" * 501).reason == "Comments can be at most 500 characters."


def test_actual_condition_must_be_one_of_the_four_levels():
    assert check_review_details(4, 0, None).reason == "Pick the condition the book was actually in."
    assert check_review_details(4, 5, None).allowed is False


# --- Misdescribed books ----------------------------------------------------


def test_a_book_two_or_more_levels_worse_is_misdescribed():
    assert is_misdescribed(listed_condition=4, actual_condition=2) is True  # like new -> fair
    assert is_misdescribed(listed_condition=4, actual_condition=1) is True  # like new -> poor


def test_one_level_worse_or_better_is_not_misdescribed():
    assert is_misdescribed(listed_condition=4, actual_condition=3) is False  # like new -> good
    assert is_misdescribed(listed_condition=2, actual_condition=4) is False  # better than listed


# --- Blind reviews ---------------------------------------------------------


def test_a_review_is_hidden_for_7_days_if_others_have_not_reviewed():
    when = review_visible_from(COMPLETED, everyone_reviewed=False, now=COMPLETED)

    assert when == "2026-11-17T14:00:00Z"
    assert is_visible(when, now="2026-11-17T13:59:59Z") is False
    assert is_visible(when, now="2026-11-17T14:00:00Z") is True


def test_a_review_is_visible_straight_away_once_everyone_has_reviewed():
    when = review_visible_from(COMPLETED, everyone_reviewed=True, now=NEXT_DAY)

    assert when == NEXT_DAY
    assert is_visible(when, now=NEXT_DAY) is True


def test_a_review_without_a_date_is_visible():
    assert is_visible(None, now=COMPLETED) is True


# --- Replies ---------------------------------------------------------------


def test_the_person_reviewed_can_reply_once(make_user):
    ana, ben = make_user(name="Ana"), make_user(name="Ben")
    review = a_review(reviewer_id=ben.id, reviewee_id=ana.id)

    assert can_reply(ana, review, "Sorry, it got damaged in my bag.", now=NEXT_DAY).allowed is True


def test_only_the_person_reviewed_can_reply_and_the_review_is_unchanged(make_user):
    ana, ben = make_user(name="Ana"), make_user(name="Ben")
    review = a_review(reviewer_id=ben.id, reviewee_id=ana.id)
    before = deepcopy(review)

    decision = can_reply(ben, review, "Thanks!", now=NEXT_DAY)

    assert decision.reason == "Only the person who was reviewed can reply."
    assert review == before


def test_a_second_reply_is_refused(make_user):
    ana, ben = make_user(name="Ana"), make_user(name="Ben")
    review = a_review(reviewer_id=ben.id, reviewee_id=ana.id, reply="Sorry!")

    assert can_reply(ana, review, "Sorry again!", now=NEXT_DAY).reason == (
        "You've already replied to this review."
    )


def test_cannot_reply_to_a_review_that_is_still_blind(make_user):
    ana, ben = make_user(name="Ana"), make_user(name="Ben")
    review = a_review(reviewer_id=ben.id, reviewee_id=ana.id, visible_from="2026-11-17T14:00:00Z")

    decision = can_reply(ana, review, "Sorry!", now=NEXT_DAY)

    assert decision.reason == "You can reply once the review is visible."


def test_an_empty_reply_is_refused(make_user):
    ana, ben = make_user(name="Ana"), make_user(name="Ben")
    review = a_review(reviewer_id=ben.id, reviewee_id=ana.id)

    assert can_reply(ana, review, "  ", now=NEXT_DAY).reason == "Write a reply first."


# --- Hiding abusive reviews ------------------------------------------------


def test_a_moderator_can_hide_a_review_with_a_reason(make_user):
    moderator = make_user(name="Mia", role="moderator")
    review = a_review(reviewer_id="user-ben", reviewee_id="user-ana")

    assert can_hide_review(moderator, review, "Insults the other student.").allowed is True


def test_a_student_cannot_hide_a_review_and_it_stays_visible(make_user):
    student = make_user(name="Ana")
    review = a_review(reviewer_id="user-ben", reviewee_id=student.id)
    before = deepcopy(review)

    decision = can_hide_review(student, review, "I don't like it.")

    assert decision.reason == "Only moderators can hide reviews."
    assert review == before


def test_hiding_needs_a_reason_and_only_happens_once(make_user):
    moderator = make_user(name="Mia", role="moderator")
    visible = a_review(reviewer_id="user-ben", reviewee_id="user-ana")
    hidden = a_review(reviewer_id="user-ben", reviewee_id="user-ana", hidden=True)

    assert can_hide_review(moderator, visible, " ").reason == "Give a reason for hiding the review."
    assert can_hide_review(moderator, hidden, "Abusive").reason == "This review is already hidden."


def test_only_moderators_can_resolve_flags(make_user):
    assert can_resolve_flag(make_user(name="Mia", role="moderator")).allowed is True
    assert can_resolve_flag(make_user(name="Ana")).reason == "Only moderators can resolve flags."


# === Saving reviews, flags and moderator actions ============================


def now_text() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def count_rows(table: str) -> int:
    with db.transaction() as connection:
        return connection.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one()


@pytest.fixture
def swap(make_user, make_book, make_copy, make_loop):
    """A direct swap that just completed: Ben gave Ana a book listed as like new,
    and Ana gave Ben a book listed as good. Returns (ana, ben, ben_to_ana, ana_to_ben)."""
    ana, ben = make_user(name="Ana"), make_user(name="Ben")
    bens_book = make_copy(owner=ana, book=make_book(title="Microeconomics"), condition=4)
    anas_book = make_copy(owner=ben, book=make_book(title="Statistics"), condition=3)
    loop = make_loop(status="completed")
    trades = []
    for trade_id, copy, giver, receiver in [
        ("trade-ben-ana", bens_book, ben, ana),
        ("trade-ana-ben", anas_book, ana, ben),
    ]:
        with db.transaction() as connection:
            connection.execute(
                text(
                    "INSERT INTO trades (id, loop_id, copy_id, giver_id, receiver_id, handoff_code, "
                    "status, completed_at) VALUES (:id, :loop, :copy, :giver, :receiver, '1234', "
                    "'completed', :done)"
                ),
                {"id": trade_id, "loop": loop.id, "copy": copy.id, "giver": giver.id,
                 "receiver": receiver.id, "done": now_text()},
            )
        trades.append(reviews_repo.get_trade(trade_id))
    return ana, ben, trades[0], trades[1]


def test_books_waiting_for_review_are_the_ones_the_user_received(swap):
    ana, ben, ben_to_ana, _ = swap

    (waiting,) = reviews_repo.trades_to_review(ana.id)

    assert (waiting.trade.id, waiting.title, waiting.giver_name) == (ben_to_ana.id, "Microeconomics", "Ben")
    assert waiting.listed_condition == 4


def test_a_reviewed_trade_is_no_longer_waiting(swap):
    ana, _, ben_to_ana, _ = swap

    reviews_repo.save_review(ben_to_ana, 5, True, 4, None)

    assert reviews_repo.trades_to_review(ana.id) == []
    assert reviews_repo.has_review(ben_to_ana.id) is True


def test_a_new_review_stays_blind_until_the_other_side_reviews(swap):
    ana, ben, ben_to_ana, _ = swap

    saved = reviews_repo.save_review(ben_to_ana, 1, False, 3, "Coffee stains everywhere.")

    assert is_visible(saved.review.visible_from) is False
    assert reviews_repo.reviews_about(ben.id) == []
    assert reviews_repo.swapper_score(ben.id).score == 4.0  # not counted yet


def test_when_everyone_has_reviewed_both_reviews_become_visible(swap):
    ana, ben, ben_to_ana, ana_to_ben = swap
    reviews_repo.save_review(ben_to_ana, 4, True, 4, None)

    saved = reviews_repo.save_review(ana_to_ben, 5, True, 3, None)

    assert is_visible(saved.review.visible_from) is True
    assert [view.reviewer_name for view in reviews_repo.reviews_about(ben.id)] == ["Ana"]
    assert [view.reviewer_name for view in reviews_repo.reviews_about(ana.id)] == ["Ben"]
    assert reviews_repo.swapper_score(ben.id).score == 4.0  # (12 + 4) / 4


def test_a_misdescribed_book_flags_the_swap_and_tells_moderators(swap, make_user):
    ana, ben, ben_to_ana, _ = swap
    moderator = make_user(name="Mia", role="moderator")

    saved = reviews_repo.save_review(ben_to_ana, 2, False, 2, "Highlighted throughout.")

    assert saved.flagged is True  # listed like new (4), arrived fair (2)
    (flag,) = reviews_repo.flagged_swaps()
    assert (flag.trade_id, flag.giver_name, flag.receiver_name) == (ben_to_ana.id, "Ben", "Ana")
    assert "flagged" in get_notifications(moderator.id)[0].text


def test_one_level_worse_is_not_flagged(swap):
    _, _, ben_to_ana, _ = swap

    saved = reviews_repo.save_review(ben_to_ana, 3, False, 3, None)

    assert saved.flagged is False
    assert reviews_repo.flagged_swaps() == []


def test_two_misdescribed_books_put_the_giver_under_review(swap, make_review):
    ana, ben, ben_to_ana, _ = swap
    make_review(reviewee=ben, stars=2, as_described=False, comment="Torn.")

    saved = reviews_repo.save_review(ben_to_ana, 2, False, 2, "Highlighted throughout.")

    assert saved.now_under_review is True
    assert reviews_repo.get_profile(ben.id).status == "under_review"
    assert reviews_repo.is_blocked(ben.id) is True
    assert "under review" in get_notifications(ben.id)[0].text


def test_a_good_review_does_not_change_the_givers_status(swap):
    _, ben, ben_to_ana, _ = swap

    saved = reviews_repo.save_review(ben_to_ana, 5, True, 4, None)

    assert saved.now_under_review is False
    assert reviews_repo.get_profile(ben.id).status == "active"


def test_a_suspended_user_stays_suspended_after_a_bad_review(swap, make_review, make_user):
    _, ben, ben_to_ana, _ = swap
    moderator = make_user(name="Mia", role="moderator")
    make_review(reviewee=ben, stars=1, as_described=False, comment="Torn.")
    reviews_repo.set_user_status(moderator.id, ben.id, "suspended")

    reviews_repo.save_review(ben_to_ana, 1, False, 1, "Pages missing.")

    assert reviews_repo.get_profile(ben.id).status == "suspended"


def test_the_database_refuses_a_second_review_of_the_same_trade(swap):
    _, _, ben_to_ana, _ = swap
    reviews_repo.save_review(ben_to_ana, 5, True, 4, None)

    with pytest.raises(Exception):
        reviews_repo.save_review(ben_to_ana, 1, False, 1, "Changed my mind.")

    assert count_rows("reviews") == 1


def test_a_reply_is_saved_once(make_review):
    review = make_review(stars=2, comment="Late.")

    reviews_repo.save_reply(review.id, "Sorry, the bus broke down.")
    with pytest.raises(ValueError):
        reviews_repo.save_reply(review.id, "Second reply")

    assert reviews_repo.get_review(review.id).reply == "Sorry, the bus broke down."


def test_hiding_a_review_saves_the_reason_logs_it_and_stops_it_counting(make_user, make_review):
    moderator = make_user(name="Mia", role="moderator")
    ben = make_user(name="Ben")
    review = make_review(reviewee=ben, stars=1, comment="Rude words")

    reviews_repo.hide_review(moderator.id, review.id, "Insulting language")

    hidden = reviews_repo.get_review(review.id)
    assert (hidden.hidden_by_moderator, hidden.hidden_reason) == (True, "Insulting language")
    assert reviews_repo.swapper_score(ben.id).score == 4.0
    (entry,) = reviews_repo.audit_entries()
    assert (entry.actor_name, entry.entry.action, entry.entry.target_id) == ("Mia", "hid review", review.id)


def test_hiding_a_review_twice_fails_and_logs_nothing_more(make_user, make_review):
    moderator = make_user(name="Mia", role="moderator")
    review = make_review(stars=1, comment="Rude words")
    reviews_repo.hide_review(moderator.id, review.id, "Insulting language")

    with pytest.raises(ValueError):
        reviews_repo.hide_review(moderator.id, review.id, "Again")

    assert count_rows("audit_log") == 1
    assert reviews_repo.get_review(review.id).hidden_reason == "Insulting language"


def test_resolving_a_flag_removes_it_from_the_list_and_logs_it(swap, make_user):
    _, _, ben_to_ana, _ = swap
    moderator = make_user(name="Mia", role="moderator")
    reviews_repo.save_review(ben_to_ana, 2, False, 1, "Pages missing.")

    reviews_repo.resolve_flag(moderator.id, ben_to_ana.id)

    assert reviews_repo.flagged_swaps() == []
    actions = [entry.entry.action for entry in reviews_repo.audit_entries()]
    assert actions == ["resolved flag", "flagged as misdescribed"]


def test_clearing_and_suspending_users_is_logged_and_notified(make_user):
    moderator = make_user(name="Mia", role="moderator")
    dina = make_user(name="Dina", status="under_review")
    assert [person.display_name for person in reviews_repo.users_needing_attention()] == ["Dina"]

    reviews_repo.set_user_status(moderator.id, dina.id, "active")

    assert reviews_repo.get_profile(dina.id).status == "active"
    assert reviews_repo.users_needing_attention() == []
    assert reviews_repo.audit_entries()[0].entry.action == "cleared user"
    assert "cleared" in get_notifications(dina.id)[0].text


def test_swap_history_shows_what_the_user_gave_and_received(swap):
    ana, _, _, _ = swap

    history = {(item.title, item.gave, item.other_name) for item in reviews_repo.swap_history(ana.id)}

    assert history == {("Microeconomics", False, "Ben"), ("Statistics", True, "Ben")}


# === The demo reviews =======================================================


def load_demo_reviews(database) -> None:
    with database.begin() as connection:
        seed_base.seed(connection)
        seed_reviews.seed(connection)


def test_the_demo_data_makes_carla_trusted_and_dina_under_review(database):
    load_demo_reviews(database)

    assert reviews_repo.swapper_score("user-carla") == (4.62, 100.0, "Trusted")
    assert reviews_repo.swapper_score("user-dina") == (2.83, 33.33, "Under review")
    assert reviews_repo.get_profile("user-dina").status == "under_review"
    assert {flag.receiver_name for flag in reviews_repo.flagged_swaps()} == {"Eli", "Farah"}


def test_the_demo_swaps_are_too_old_to_review(database):
    # Carla received a book back in each of her 5 October swaps, but the
    # 14 days have passed, so none of them can be reviewed now.
    load_demo_reviews(database)
    carla = seed_profile("user-carla", "Carla")

    received = reviews_repo.trades_to_review(carla.id)

    assert len(received) == 5
    assert not any(can_review(carla, item.trade, False).allowed for item in received)


# === The Profile and Moderator pages ========================================


ROOT = Path(__file__).resolve().parents[1]


def seed_profile(id: str, name: str, role: str = "student", status: str = "active") -> Profile:
    return Profile(id=id, display_name=name, role=role, status=status, created_at=seed_base.CREATED_AT)


def open_page(page_file: str, user: Profile) -> AppTest:
    """Open a page logged in as `user` (laptop mode, test database)."""
    page = AppTest.from_file(str(ROOT / "pages" / page_file), default_timeout=30)
    page.session_state["current_user"] = user
    page.session_state["_auth_mode"] = "laptop"
    return page.run()


def test_profile_page_shows_score_badge_and_reviews(database):
    load_demo_reviews(database)

    page = open_page("6_Profile.py", seed_profile("user-carla", "Carla"))

    assert not page.exception
    metrics = {metric.label: metric.value for metric in page.metric}
    assert metrics == {"Swapper Score": "4.62", "Accuracy": "100%", "Badge": "Trusted"}
    assert "No swaps waiting for your review." in [caption.value for caption in page.caption]


def test_profile_page_review_form_saves_a_review(swap):
    ana, ben, ben_to_ana, _ = swap

    page = open_page("6_Profile.py", ana)
    page.select_slider[0].set_value(2)
    page.radio[0].set_value("No")
    page.selectbox[1].set_value(1)
    page.text_area[0].input("Torn cover and missing pages.")
    page = page.button[0].click().run()

    assert not page.exception
    assert page.success[0].value.startswith("Thanks! Your review of Ben is saved.")
    assert "a moderator will check the swap" in page.success[0].value
    assert reviews_repo.has_review(ben_to_ana.id) is True


def test_profile_page_refuses_a_low_rating_without_a_comment(swap):
    ana, _, ben_to_ana, _ = swap

    page = open_page("6_Profile.py", ana)
    page.select_slider[0].set_value(1)
    page = page.button[0].click().run()

    assert page.error[0].value.startswith("Please add a comment")
    assert reviews_repo.has_review(ben_to_ana.id) is False


def test_moderator_page_shows_flags_and_can_clear_a_user(database):
    load_demo_reviews(database)
    moderator = seed_profile("user-moderator", "Morgan", role="moderator")

    page = open_page("7_Moderator.py", moderator)
    assert not page.exception
    assert [b.label for b in page.button].count("Mark as resolved") == 2
    page = next(b for b in page.button if b.label == "Clear").click().run()

    assert page.success[0].value == "Dina has been cleared: they can swap again."
    assert reviews_repo.get_profile("user-dina").status == "active"


def test_students_cannot_open_the_moderator_page(database):
    load_demo_reviews(database)

    page = open_page("7_Moderator.py", seed_profile("user-ana", "Ana"))

    assert page.error[0].value == "You don't have permission to view this page."
