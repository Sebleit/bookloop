# BookLoop

Nova SBE students swap textbooks with each other: no money, just one book for another.

**Live app:** https://bookloop-nova.streamlit.app/

## Team

| Name | Student number |
|---|---|
| Michele Camilli | 83914 |
| Edoardo Journo | 83923 |
| Sebastian Leitner | 83506 |
| Filippo Rondoletti | 83459 |
| Filippo Ariaudo | 83921 |

## What it does

Students list the textbooks they no longer need and swap them for ones they do. There are two ways to swap: a **direct swap** between two people, or a weekly **swap round**, where the app finds circles of students who can all swap at once, even when no two of them want each other's book. Every handoff is confirmed with a code, receivers review what they got, and moderators deal with problems.

**Listing books (My Shelf).** Type a book's ISBN and its title, authors and cover come from Open Library; if Open Library doesn't know it, you type them yourself. You add the condition (poor, fair, good or like new), any highlighting and a note. You can edit or withdraw a book while nobody is counting on it.

**Browsing and wishlist (Browse, My Shelf).** Search all available books by title, author or ISBN, and filter by Nova SBE course or condition. Each book shows the courses it's used in, and students can add a course that's missing. Put a book on your wishlist and you get a notification when someone lists it.

**Direct swaps (Offers).** Offer one of your books for one of someone else's, and see their Swapper Score first. They can accept or decline; an offer expires after 72 hours. Accepting shares both people's emails, so the two can agree where and when to meet.

**Swap rounds (Swap Round).** A moderator opens a round each week. First, students put in the books they're willing to give. Then each student ticks the books they'd accept in return, optionally only from people above a minimum Swapper Score. When the moderator runs the round, the app finds loops of 2 to 6 people (Ana gives to Farah, Farah to Eli, Eli to Ana), shortest first, and everyone in a loop meets at the place and time the moderator set. Books nobody wanted go back on their owners' shelves.

**Handoffs (My Swaps).** Everyone in a swap meets at the same time, and nobody hands over a book until everyone is there. The receiver shows a random 4-digit code and the giver types it, which makes the receiver the new owner. Three wrong codes lock the trade. If someone doesn't come, a no-show cancels the swap and everyone keeps their book; if someone came but didn't hand over their book, the others report it to a moderator.

**Reviews and Swapper Score (Profile).** After a swap, the receiver gives stars for the swap and says what condition the book arrived in. Reviews stay hidden until both sides have reviewed, or the 14 days for reviewing are over, so nobody can review in revenge. Reviews build each person's Swapper Score and badge (New, Trusted or Under review). Everyone starts as if they had three 4-star reviews, and someone with a low score or repeatedly misdescribed books goes under review: they can't make offers or join rounds until a moderator clears them.

**Moderation (Moderator, Stats).** Moderators see reports of books not handed over, with a picture of the swap and the email of everyone in it, and books that arrived two or more conditions worse than listed. They can resolve a problem, clear or suspend a user, and hide an abusive review; every action is logged. The Stats page shows books listed, swaps completed, the average score and the most-wanted books, with a CSV download.

## Run it locally

You need Python 3.12 or newer and [uv](https://docs.astral.sh/uv/).

```bash
uv sync                      # install the libraries
uv run python seed.py        # build a local database with demo data
uv run streamlit run app.py  # start the app, then open http://localhost:8501
```

On your laptop there's a **Dev login**: pick a demo user from the list, no password. Morgan is the moderator.

## Re-run the demo

The demo from our presentation works on your laptop, with the demo data and no passwords. After the commands above, use the **Dev login** to be each person (**Log out** to switch). Run `uv run python seed.py` to start over at any time.

1. **Carla** → **My Shelf**: add ISBN `9780134472089`, condition *good*. The title and cover come from Open Library.
2. **Carla** → **Offers**: Leonor offers *University Physics* for Carla's *Business Essentials*. Click **Accept and share my email**: you'll see Leonor's email to arrange the meeting.
3. **Carla** → **Swap Round**: in the round that says *Entries open*, enter *Options, Futures, and Other Derivatives*, then *Principles of Economics*.
4. **Morgan** (the moderator) → **Swap Round**, same round → **Close entries and open wants**.
5. **Carla** → **Swap Round**: under *Options, Futures…*, tick *A Mind for Numbers* from Ana → **Save**.
6. **Morgan** → **Swap Round**: choose the *Choosing wants* round with the **earlier** date → **Run round**. The app finds 6 loops, including Carla and Ben's swap and Ana → Farah → Eli, and draws each one.
7. **Ben** → **My Swaps**: his code is under *You get "A Little History of the World" from Carla*. Then **Carla** → **My Swaps**: type it to confirm the handoff. A wrong code is refused, and three wrong codes lock the trade.
8. **Carla** → **Profile**: review *Chemistry: The Central Science* from Eli: 2 stars, condition *poor*, with a comment. The swap is flagged as worse than described.
9. **Morgan** → **Moderator**: Ben's report that Farah didn't hand over *Psychology*, with a picture of the swap and everyone's email, and the flagged Chemistry book. **Stats** shows the community numbers.

Online, anyone can sign up on the live app with any email and use it as a student.

## Run the tests

```bash
uv run pytest
```

The tests also run automatically on every push to GitHub.

## Where things are

```
app.py        starts the app: login and menu
pages/        one file per page
bookloop/     rules (who may do what), storage (database code), services (Open Library, notifications)
db/           the database tables
seed/         demo data
tests/        the tests
```

Online, the app uses Supabase for its database and login. Its keys and passwords are in the host's secret settings, never in this repository.
