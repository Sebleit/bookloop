"""Tests for the Swapper Score: the maths in bookloop/rules/reputation.py, and
swapper_score() in storage, which decides which reviews count.
"""

from pytest import approx

from bookloop.rules.reputation import (
    accuracy,
    badge,
    misdescribed_recently,
    score,
    should_be_under_review,
)
from bookloop.storage.reviews_repo import swapper_score


LONG_AGO = "2000-01-01T00:00:00Z"
FAR_FUTURE = "2099-01-01T00:00:00Z"


# --- The score formula: the plan's worked examples -------------------------


def test_one_five_star_review_gives_4_25():
    assert score([5]) == approx(4.25)


def test_reviews_5_5_4_2_give_4_00():
    assert score([5, 5, 4, 2]) == approx(4.00)


def test_reviews_1_2_2_give_2_83():
    assert round(score([1, 2, 2]), 2) == 2.83


def test_no_reviews_gives_the_starting_score_of_4():
    assert score([]) == approx(4.0)


# --- Accuracy --------------------------------------------------------------


def test_accuracy_is_the_percentage_as_described():
    assert accuracy([True, True, True, False]) == approx(75.0)


def test_accuracy_with_no_reviews_is_0():
    assert accuracy([]) == 0.0


def test_only_the_last_5_reviews_count_as_recent():
    # Newest first: the 6th review is too old to count.
    assert misdescribed_recently([False, True, True, True, True, False]) == 1
    assert misdescribed_recently([False, True, False, True, True]) == 2


# --- Under review ----------------------------------------------------------


def test_a_score_below_3_after_3_reviews_means_under_review():
    assert should_be_under_review(review_count=3, user_score=score([1, 2, 2]), misdescribed_in_last_five=0)


def test_exactly_3_after_3_reviews_is_not_under_review():
    exactly_three = score([2, 2, 2])  # (12 + 6) / 6 = 3.0
    assert exactly_three == approx(3.0)
    assert not should_be_under_review(3, exactly_three, 0)
    assert badge(3, exactly_three, 100.0, 0) is None


def test_a_low_score_with_fewer_than_3_reviews_is_not_under_review():
    two_bad = score([1, 1])  # 2.8, but only 2 reviews
    assert not should_be_under_review(2, two_bad, 0)
    assert badge(2, two_bad, 100.0, 0) == "New"


def test_2_misdescribed_books_in_the_last_5_means_under_review():
    assert should_be_under_review(review_count=6, user_score=4.4, misdescribed_in_last_five=2)
    assert not should_be_under_review(review_count=6, user_score=4.4, misdescribed_in_last_five=1)


# --- Badges ----------------------------------------------------------------


def test_fewer_than_3_reviews_is_new():
    assert badge(0, 4.0, 0.0, 0) == "New"
    assert badge(2, 4.6, 100.0, 0) == "New"


def test_5_great_accurate_reviews_is_trusted():
    stars = [5, 5, 5, 5, 5]
    assert badge(5, score(stars), 100.0, 0) == "Trusted"


def test_trusted_needs_all_three_conditions():
    assert badge(4, 4.6, 100.0, 0) is None    # only 4 reviews
    assert badge(5, 4.4, 100.0, 0) is None    # score below 4.5
    assert badge(5, 4.6, 80.0, 0) is None     # accuracy below 90%


def test_under_review_wins_over_trusted():
    assert badge(10, 4.8, 80.0, misdescribed_in_last_five=2) == "Under review"


# --- swapper_score(): which reviews count -----------------------------------


def test_blind_reviews_do_not_count_yet(make_user, make_review):
    ben = make_user(name="Ben")
    make_review(reviewee=ben, stars=5, visible_from=LONG_AGO)
    make_review(reviewee=ben, stars=1, as_described=False, comment="Torn.", visible_from=FAR_FUTURE)

    result = swapper_score(ben.id)

    assert result.score == 4.25  # only the visible 5-star review counts
    assert result.accuracy == 100.0


def test_a_review_counts_once_it_becomes_visible(make_user, make_review):
    ben = make_user(name="Ben")
    make_review(reviewee=ben, stars=1, as_described=False, comment="Torn.", visible_from=LONG_AGO)

    assert swapper_score(ben.id).score == 3.25  # (12 + 1) / 4


def test_a_hidden_review_no_longer_counts_in_the_score(make_user, make_review):
    ben = make_user(name="Ben")
    make_review(reviewee=ben, stars=5)
    make_review(reviewee=ben, stars=1, comment="Abusive text", hidden_by_moderator=True,
                hidden_reason="Abusive")

    assert swapper_score(ben.id).score == 4.25


def test_a_user_with_only_blind_reviews_still_looks_new(make_user, make_review):
    ben = make_user(name="Ben")
    for _ in range(3):
        make_review(reviewee=ben, stars=1, comment="Bad.", visible_from=FAR_FUTURE)

    assert swapper_score(ben.id) == (4.0, 0.0, "New")
