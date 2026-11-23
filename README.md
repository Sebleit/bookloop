# BookLoop

Students swap textbooks with each other: no money, just books for books.

**Online app:** https://bookloop-2y6l6lsym6mznfylnxegux.streamlit.app/

## Team

| Name | Student number | GitHub |
|---|---|---|
| Seb FILL IN SURNAME | FILL IN | [Sebleit](https://github.com/Sebleit) |
| Michele FILL IN SURNAME | FILL IN | [michelecamilli](https://github.com/michelecamilli) |
| Edoardo Journo | FILL IN | [edoardo-journo](https://github.com/edoardo-journo) |
| Filippo FILL IN SURNAME | FILL IN | [ariaudo](https://github.com/ariaudo) |

## What it does

- **List your books.** Type an ISBN and the title, authors and cover come from Open Library. If Open Library doesn't answer, you type them yourself.
- **Browse and wishlist.** Search by title, author or ISBN, filter by course and condition. Add a book to your wishlist and you're notified when someone lists it.
- **Nova SBE courses.** Each book shows the courses it's used in. Students pick from the courses others added, or type a new one, which is then offered to everyone.
- **Direct swaps.** Offer one of your books for someone else's. They accept, decline, or let it expire after 72 hours.
- **Swap rounds.** Everyone puts in books and ticks the ones they'd accept. The app finds loops (Ana → Farah → Eli → Ana), so three or more people can swap when no two of them could swap directly.
- **Safe handoffs.** Everyone in a swap meets at the same place and time, and nobody hands over a book until everyone is there. The giver types the receiver's 4-digit code, which moves the book to its new owner; three wrong codes lock the trade. If someone doesn't come, a no-show cancels the swap and everyone keeps their own book. If someone came but didn't hand over their book, it's reported to a moderator.
- **Reviews and Swapper Score.** The receiver reviews the giver in two parts: stars for the swap (the person and the meeting) and the condition the book arrived in. Reviews stay hidden until everyone in the swap has reviewed, or the 14 days for reviewing end, so nobody can review in revenge. They build each person's score and badge (New, Trusted, Under review).
- **Moderation.** Moderators see each swap as a picture (who gives which book to whom, and what has been handed over), reports of books not handed over, and books that arrived 2+ conditions worse than listed. They clear or suspend users, hide abusive reviews, and see community stats.

## Run it on your laptop

You need Python 3.12 or newer and [uv](https://docs.astral.sh/uv/).

```bash
uv sync                      # install the exact library versions in uv.lock
uv run python seed.py        # build a local database (bookloop.db) full of demo data
uv run streamlit run app.py  # start the app
```

Then open http://localhost:8501. On a laptop there's a **Dev login**: pick a demo user from the list, no password. Run `seed.py` again at any time to reset the demo data.

| Demo user | Who they are |
|---|---|
| Morgan | the moderator |
| Ana, Ben, Eli, Farah | students in the demo swap round ("Winter textbook swap", ready to run) |
| Carla | Trusted student, with a handoff to Dina waiting and a book from Eli to review |
| Dina | student under review: low score and two books worse than described |

## Run the tests

```bash
uv run pytest      # all tests, on a temporary database (no internet needed)
uv run pip-audit   # check the libraries for known security problems
```

GitHub Actions runs both on every push and pull request (Python 3.12). See `.github/workflows/`.

## The online version

The online app runs on Streamlit Community Cloud, with its data in Supabase (a PostgreSQL database and its login service).

- The app needs three settings: `DATABASE_URL`, `SUPABASE_URL` and `SUPABASE_KEY`. They live only in the host's secret settings, never in this repository (`.env` and `.streamlit/secrets.toml` are ignored by git; see `.env.example`).
- When `DATABASE_URL` is set, the app is in **online mode**: people sign up and log in with email and password, and the dev login is switched off.
- To set up a new Supabase project, run `db/migrations/001_init.sql` and then `db/supabase_only.sql` (row-level security) in its SQL editor. To make someone a moderator, change their `role` to `moderator` in the `profiles` table.
- A free Supabase project pauses after a week without activity. Open its dashboard before a demo.

**Demo data online.** Sign up once on the live app for each demo person, with these first names: Morgan, Ana, Ben, Carla, Dina, Eli and Farah. Then reset the demo data in one of two ways:

- **In Supabase (no setup needed):** open the SQL Editor, paste all of `db/demo_reset.sql` and run it. It works on any day, because every demo date moves to the day it runs.
- **From a laptop**, with `DATABASE_URL` set to the online database:
  ```bash
  uv run python reset_online_demo.py        # checks the demo accounts, changes nothing
  uv run python reset_online_demo.py --yes  # resets the online demo data
  ```

The reset deletes every book, swap, round, review and notification online (accounts are kept) and loads the same demo data as `seed.py`, linked to those accounts. Morgan becomes the moderator. It's one transaction: if anything fails, nothing changes.

Email confirmation is off in Supabase (Authentication → Sign In / Providers) for the demo: Supabase's free email sender only emails the project's own team, at most 2 emails an hour. With real users we'd connect an email service and turn it back on.

## Where things are

```
app.py           starts the app: login, sidebar, menu
pages/           one file per page (Browse, My Shelf, Offers, Swap Round, My Swaps, Profile, Moderator, Stats)
bookloop/
  rules/         the rules: who may do what (no Streamlit, no database)
  storage/       all database code
  services/      notifications and the Open Library lookup
  auth.py        login and role checks
  models.py      the data shapes (Profile, Book, Copy, Trade, ...)
db/              the database tables (001_init.sql), Supabase security rules, and the online demo reset (demo_reset.sql)
seed.py, seed/   demo data for the laptop database
tests/           the tests
```

## More

- [ARCHITECTURE.md](ARCHITECTURE.md): how it's built, why, and its limits.
- [docs/DEMO.md](docs/DEMO.md): the 3-minute demo script.
- [docs/WALKTHROUGH.md](docs/WALKTHROUGH.md): questions the teachers may ask, with answers.
