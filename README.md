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

- **List your books.** Type an ISBN and the title, authors and cover come from Open Library.
- **Browse and wishlist.** Search books by title, author, ISBN or course, and get notified when a book you want is listed.
- **Direct swaps.** Offer one of your books for someone else's. If they accept, you both see each other's email to agree where and when to meet.
- **Swap rounds.** Everyone puts in books and ticks the ones they'd accept. The app finds loops, so three or more people can swap even when no two of them could swap directly.
- **Handoffs.** The receiver shows a 4-digit code and the giver types it, which moves the book to its new owner.
- **Reviews and moderation.** Receivers review the swap and the book's condition, which builds each person's Swapper Score. Moderators check reported problems.

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
