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
