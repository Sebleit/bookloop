# How BookLoop is built

BookLoop is a Python web app made with [Streamlit](https://streamlit.io). The same code runs in two places:

| | On a laptop | Online |
|---|---|---|
| Database | a SQLite file, `bookloop.db`, filled with demo data by `seed.py` | PostgreSQL on Supabase |
| Login | **Dev login**: pick a demo user, no password | Supabase Auth: email and password |
| Settings | none (no `DATABASE_URL`) | `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_KEY` in the host's secret settings |

The app decides which mode it's in from one thing: whether `DATABASE_URL` is set.

## The layers

```
 browser
    │
 app.py ─────────── login, sidebar, menu
    │
 pages/ ─────────── what you see: show data, ask a rule, save, say "Done" or why not
    │        │         │
 rules/   storage/  services/
 who may  all the    notify (in-app messages)
 do what  database   openlibrary (book details from an ISBN)
          code
             │
       SQLite or PostgreSQL
```

- **`pages/`**: one file per page. Every action follows the same steps: read the data, ask a rule whether it's allowed, save it through `storage/`, and end with a "Done" message or the rule's reason for saying no.
- **`bookloop/rules/`**: plain Python functions. They take data and answer with a `Decision` (`Decision.yes()` or `Decision.no("reason")`). They never touch Streamlit or the database, so they're quick to test and easy to read.
- **`bookloop/storage/`**: all SQL lives here. `transaction()` groups changes so they're saved together or not at all. Every query passes values as parameters (`:name`), never glued into the SQL text.
- **`bookloop/services/`**: `notify` saves in-app notifications (shown in the sidebar); `openlibrary` asks Open Library for a book's title, authors and cover.
- **`bookloop/auth.py`**: login, `current_user()` (every page calls it) and `require_role("moderator")`.
- **`bookloop/models.py`**: the data shapes (`Profile`, `Book`, `Copy`, `Offer`, `Loop`, `Trade`, `Round`, `Review`, ...).

**Example, confirming a handoff.** On My Swaps the giver types the receiver's code. The page calls `swaps_repo.confirm_handoff()`, which in one transaction reads the trade, asks the rule `check_code()`, and then either completes the trade and makes the receiver the book's owner, or counts a wrong attempt (three lock the trade). The page shows "Handoff confirmed" or the reason.

## The data

The tables are defined in `db/migrations/001_init.sql` (16 tables, with foreign keys and `CHECK` rules).

- **People:** `profiles` (name, role `student` or `moderator`, status `active`, `under_review` or `suspended`).
- **Books:** `books` is one row per title (ISBN, title, authors, cover); `copies` is one row per physical book (owner, condition 1–4, highlighting, notes, status). A copy is `available`, `in_round`, `reserved` (promised in a swap) or `unlisted`. `courses`, `book_courses` and `wishlist` link books to courses and to the people who want them.
- **Swaps:** `offers` (direct swap proposals); `rounds`, `round_entries` and `round_wants` (swap rounds); `loops` and `trades` (the swaps themselves). A **loop** is one meeting; each **trade** is one book going from a giver to a receiver, with the receiver's handoff code.
- **Trust:** `reviews` (stars, "as described?", actual condition, comment, reply, when it becomes visible); `audit_log` records every moderator action and every automatic flag. `entity_ids` lets the log point at rows from different tables.
- **Messages:** `notifications`.

## Main decisions, and why

1. **Rules are separate from pages and from the database.** All the "who may do what" lives in one place, it can be tested without a browser or a database, and a page can't forget a check that lives in the rule it calls.
2. **Every action is checked again when it happens, not just by hiding buttons.** Students don't see the Moderator and Stats pages in the menu, but that's only convenience: if a student opens the page's address, the page itself refuses ("You don't have permission to view this page."). The storage functions check too, for example only the giver can confirm a handoff.
3. **Books and copies are separate tables.** Title, authors and cover belong to the book, so they're looked up once per ISBN and shared by every copy. Condition and owner belong to the copy. Wishlists and course links are about books, so "someone listed a book you want" works whichever copy it is.
4. **A direct swap is a loop of 2.** Direct swaps and swap rounds create the same `loops` and `trades`, so handoff codes, no-shows, My Swaps and reviews are written once and work for both.
5. **Changes that belong together are one transaction.** Accepting an offer reserves both copies and creates the swap in one go, or not at all. Running a round first "claims" it with `UPDATE rounds SET phase = 'matched' WHERE phase = 'wants'`, so two moderators clicking at once can't run it twice. If anything fails, the round goes back to the wants phase.
6. **The loop finder takes the shortest loop first, with at most 6 people.** Shorter loops are easier to meet up for, and if someone doesn't come, only a small loop is cancelled. Each person appears at most once in a loop, and an arrow is skipped if the giver's score is below the minimum the receiver chose.
7. **The Swapper Score is an adjusted average, calculated every time it's shown.** Everyone starts as if they had 3 reviews of 4 stars: `score = (3 × 4.0 + sum of stars) / (3 + number of reviews)`. One 5-star review gives 4.25, not a "perfect" 5.0. It's never stored, so it can't go out of date.
8. **Reviews are blind.** A review stays hidden until everyone in the swap has reviewed, or 7 days pass, so nobody can answer a bad review with a revenge review. Hidden reviews don't count in the score shown to others, but they do count when deciding if someone should be put under review (safety first).
9. **Misdescribed books are flagged automatically.** If a book arrives 2 or more conditions worse than listed, the swap is flagged for moderators. Someone with a score below 3.0 after 3+ reviews, or 2 misdescribed books in their last 5 swaps, goes under review and can't make offers or join rounds until a moderator clears them.
10. **Open Library is optional.** The lookup gives up after 5 seconds or on any error, and the page shows a form to type the details. A book found once is saved in `books`, so the same ISBN isn't looked up again.
11. **Two modes, one codebase.** Anyone can run the app on a laptop with no accounts or internet: `seed.py` builds the database and the dev login needs no password. SQLAlchemy runs the same SQL on SQLite and PostgreSQL. The dev login only works without `DATABASE_URL`, so it can't appear online, and a test checks this.

## Security

- **Login:** Supabase Auth online. The dev login is refused whenever `DATABASE_URL` is set.
- **Permissions:** checked in the rules and in the storage functions, and moderator pages call `require_role("moderator")`. `tests/test_permissions.py` and `tests/test_app.py` try pages as the wrong user.
- **Input:** SQL always uses parameters, so typed text can't change a query (no SQL injection). Search escapes `%` and `_`, so they're searched for literally. The rules check lengths and allowed values, and the database has `CHECK` rules and foreign keys as a last line.
- **Supabase:** row-level security is on for every table (`db/supabase_only.sql`). Through Supabase's public API, a logged-in user can read only their own profile. The app itself reaches the data through the private `DATABASE_URL`, which only the server has.
- **Secrets:** only in the host's settings. `.env`, `.streamlit/secrets.toml` and `bookloop.db` are ignored by git.
- **Libraries:** few, with exact versions pinned in `uv.lock`, and `pip-audit` checks them for known vulnerabilities on every push.

## Tests

`uv run pytest` runs about 290 tests, also on every push (GitHub Actions).

- **Rules:** accepted actions, refused actions and edge cases (an offer at exactly 72 hours, a review one second after the 14-day window, two loops that want the same book).
- **Storage:** on a fresh temporary SQLite database, using shared factories (`make_user`, `make_copy`, ...) instead of the demo data.
- **Pages:** opened with Streamlit's test tool (`AppTest`) as different users, including a few demo steps.
- **Open Library:** faked responses (found, unknown ISBN, timeout, error), so the tests don't need the internet.

**Not covered by automatic tests:** the real PostgreSQL/Supabase database and its row-level security, the real Supabase login, the real Open Library, and a real browser. The online demo reset (`reset_online_demo.py`) and the demo steps were tried by hand on a real PostgreSQL set up with `db/supabase_only.sql`. Streamlit's test tool can't follow a click on the login form into the menu or open a page by its address, so those were checked by hand in a browser: logging in, links to a page while logged out, and Log out.

## Limits we know about

| Limit | Why it matters | How we'd fix it |
|---|---|---|
| The loop finder doesn't always find the largest possible number of swaps. | Taking the shortest loop first can use a book that a longer loop needed. | Treat it as an optimisation problem (choose the set of loops that swaps the most books, for example with integer programming), or try several orders and keep the best. |
| Two friends could swap back and forth to raise each other's score. | The score trusts every review equally. | Count only one review per pair of people per month, and give less weight to reviews from people with few swaps. |
| A handoff code proves people met, not that the book was as described. | Someone could still overstate the condition. | Ask for a photo when listing. Today the receiver's review and the automatic flag catch it afterwards. |
| Notifications only appear inside the app. | You only see them when you log in. | Send an email too, through an email service. |
| A no-show is recorded, but nothing happens automatically after repeated no-shows. | Unreliable people can keep joining swaps. | Put someone under review after, say, 2 no-shows, like we do for misdescribed books. |
| Meeting places are free text. | People may type unclear places. | Offer a list of campus meeting points. |

## How it could change

- **More users:** searching and counting already happen in SQL. With many more users we'd add database indexes on the columns Browse searches, and show results page by page. The loop finder works on one round at a time; very large rounds would need the faster optimisation approach above.
- **A mobile app or another front end:** the rules and storage don't depend on Streamlit, so they could sit behind an API unchanged.
- **New rules** (for example a limit on rounds per term) go in `bookloop/rules/` with their tests; the pages just show the reason.
