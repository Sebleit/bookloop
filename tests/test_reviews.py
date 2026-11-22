"""Tests for the review rules in bookloop/rules/reviews.py.

Users come from the shared factories in conftest.py. Trades and reviews are
only needed in memory here, so the helpers below build them. All times are
fixed so the tests give the same result on any day.
"""

from copy import deepcopy

from bookloop.models import Review, Trade
from bookloop.rules.reviews import (
    can_hide_review,
    can_reply,
    can_review,
    check_review_details,
    is_misdescribed,
    is_visible,
    needs_comment,
    review_visible_from,
)


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
