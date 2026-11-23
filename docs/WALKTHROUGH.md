# Walkthrough questions

After the demo, the teachers open the repository and ask questions. Any of us can be asked about any part, so everyone should be able to answer all of these. Short answers first, then where to point in the code.

## The four questions from the plan

**Where is the data stored?**
Online in Supabase's PostgreSQL database; on a laptop in a local SQLite file, `bookloop.db`, that `seed.py` fills with demo data. The tables are defined once, in `db/migrations/001_init.sql`. All database code is in `bookloop/storage/`.

**What do the tests cover, and what don't they?**
About 290 tests, run on every push by GitHub Actions. They cover the rules (accepted actions, refused actions, edge cases), the storage code on a temporary SQLite database, the pages (opened with Streamlit's test tool as different users), and Open Library with faked answers. They don't cover the real Supabase database and its row-level security, the real Supabase login, the real Open Library, or a real browser. Logging in through the form, links to a page while logged out, and Log out were checked by hand in a browser, because Streamlit's test tool can't follow them.

**What happens if Open Library is unavailable?**
The lookup gives up after 5 seconds or on any error and returns nothing, and My Shelf shows a form to type the title and author. Listing still works. A book found once is saved in our `books` table, so we don't ask Open Library twice for the same ISBN. (`bookloop/services/openlibrary.py`, `tests/test_openlibrary.py`)

**Why is it built this way, and what would you change?**
See the sections below and [ARCHITECTURE.md](../ARCHITECTURE.md). In one sentence: the rules are separate from the pages and the database so they're easy to test and every action is checked in one place; and direct swaps and rounds share one loop/trade model, so handoffs and reviews are written once.

## How the project is organised

**What are the layers?**
`pages/` shows things and handles clicks; `bookloop/rules/` decides who may do what (plain functions returning `Decision.yes()` or `Decision.no("reason")`, no Streamlit, no database); `bookloop/storage/` holds all SQL; `bookloop/services/` holds notifications and Open Library. Every page action is: read, ask a rule, save, show "Done" or the reason.

**How did you work together?**
Each of us owned some files. Changes were made on branches and merged into `main` through pull requests on GitHub, where the tests and `pip-audit` run automatically. The online app runs the `main` branch.

**How do you run it?**
`uv sync`, `uv run python seed.py`, `uv run streamlit run app.py`. Tests: `uv run pytest`. See the [README](../README.md).

**How do you get the demo data onto the live app?**
We signed up seven demo accounts on the live app (Morgan, Ana, Ben, Carla, Dina, Eli, Farah). Then `db/demo_reset.sql`, pasted into Supabase's SQL Editor, loads the same demo data as `seed.py`, linked to those accounts by first name (`reset_online_demo.py` does the same from a laptop). It's one transaction, so if anything fails nothing changes, and it moves every demo date to the day it runs.

## Listings and login

**Why are books and copies separate tables?**
A book is a title (one row per ISBN: title, authors, cover); a copy is a physical book someone owns (condition, notes, status). Details are looked up once and shared by every copy, and wishlists and courses work at the book level.

**Why can the dev login never appear online?**
The app is in laptop mode only when `DATABASE_URL` isn't set. Online it's always set, so `auth.py` shows the email login and `_save_dev_login()` refuses to log anyone in. `tests/test_auth.py` checks this.

**How does search stay safe?**
The search text is passed to SQL as a parameter, never pasted into the query, so it can't change the query (no SQL injection). `%` and `_` are escaped, so searching "100%" looks for those characters instead of matching everything. (`search_available` in `bookloop/storage/copies_repo.py`)

**What does the wishlist do?**
You add a book you want; when someone lists a copy of it, everyone who wants it gets a notification in the sidebar.

## Direct swaps, handoffs and stats

**Why is a direct swap a loop of 2?**
A swap round produces loops of 2 to 6 people. Treating a direct swap as a loop of 2 means one model for both: the same `loops` and `trades` tables, the same My Swaps page, handoff codes, no-shows and reviews.

**Why must accepting an offer be one transaction?**
Accepting reserves both copies, creates the loop and its two trades, and cancels other offers on those copies. If it stopped halfway, a book could be reserved with no swap, or promised twice. In one transaction it all happens or none of it does. (`accept_offer` in `bookloop/storage/swaps_repo.py`)

**What are the offer rules?**
At most 5 pending offers each; an offer expires after 72 hours; you can only offer your own available copy; users under review or suspended can't make offers. (`bookloop/rules/offers.py`)

**How do handoff codes work?**
Each trade has a 4-digit code that only the receiver sees. At the meeting the giver types it into My Swaps. Right code: the trade completes and the receiver becomes the owner. Wrong code: refused and counted; after 3 wrong codes the trade is locked. It proves the two people met. (`bookloop/rules/handoffs.py`)

**What happens with a no-show?**
Anyone in the swap can report who didn't come (in a round loop they choose the person). The loop is cancelled, every book goes back to available, and the no-show is recorded on the loop.

**What does the Stats page show?**
For moderators: books listed, swaps completed, the average score, the most-wanted books, and a CSV download of it all.

**How are permissions checked on every action, not just by hiding buttons?**
The rules check the user: for example, only the owner of the requested book can accept an offer, and only the giver can confirm a handoff. The moderator pages call `require_role("moderator")`, so a student who types the address gets "You don't have permission to view this page." `tests/test_permissions.py` and `tests/test_app.py` try these as the wrong user.

## Swap rounds

**What are the phases?**
entries → wants → matched → closed, and only a moderator can move a round forward. In *entries* students put in available books (they become `in_round`, so they can't be offered elsewhere). In *wants* each student ticks the books they'd accept in return, with an optional minimum Swapper Score. *Run round* finds the loops; then the round is closed. (`bookloop/rules/rounds.py`)

**How does the loop finder work?**
1. Draw an arrow from each book to every book its owner would accept.
2. Find the shortest circle of arrows: that's a loop, so lock it in.
3. Remove those books and repeat until no circles are left.
4. Skip an arrow if the giver's score is below the minimum the receiver chose (someone with no reviews counts as 4.0).
Loops have at most 6 people, and each person appears once per loop. (`bookloop/rules/loop_finder.py`, `tests/test_loop_finder.py`)

**Why shortest loops first, and why at most 6 people?**
Short loops are easier to meet up for. If someone doesn't come, only a small loop is cancelled, so fewer people lose their swap. Six keeps the meeting manageable and the search fast.

**What's the limit of the loop finder?**
It doesn't always find the largest possible number of swaps: taking the shortest circle first can use a book that two longer circles needed. To fix it, we'd choose the set of loops that swaps the most books (an optimisation problem, for example with integer programming), or try several orders and keep the best result.

**Can a round run twice? What if it fails halfway?**
Running a round first changes its phase from *wants* to *matched* with one conditional `UPDATE`; if two moderators click at once, only one succeeds. If anything fails while creating the loops, the round goes back to *wants*. (`run_round` in `bookloop/storage/rounds_repo.py`)

**Who sees what?**
Each student sees only their own result: what to give, to whom, and what they'll receive. Moderators see every loop (for example "Loop 1: Ana → Farah → Eli → Ana").

## Reviews, reputation and moderation

**How is the Swapper Score calculated, and why?**
`score = (3 × 4.0 + sum of stars) / (3 + number of reviews)`. Everyone starts as if they had three 4-star reviews, so one review can't make a new user perfect or ruin them. Examples: one 5-star review → 4.25; reviews 5, 5, 4, 2 → 4.00; reviews 1, 2, 2 → 2.83. (`bookloop/rules/reputation.py`)

**Why is the score calculated, not stored?**
It's worked out from the reviews every time it's shown, so it can't go out of date. When a moderator hides a review, the score changes straight away.

**What does a review grade?**
Two separate things, and the form says which is which. *1. How did the swap go?* Stars for the person and the meeting: on time, polite, easy to arrange. *2. What condition did the book arrive in?* The book. Someone can hand over a perfect book but come 40 minutes late, or be lovely but overstate the condition, so one number can't grade both. Stars build the Swapper Score. The condition builds accuracy, the flags and the misdescribed-books rule.

**Why don't you ask "was it as described?"**
We used to, and it was the same question as the condition, asked twice: someone could even answer "yes, as described" and "arrived poor" for a book listed "like new". Now the app works it out: as listed or better means as described. The answers can't contradict each other, and there's one question fewer.

**How does accuracy fit in?**
Accuracy is the share of someone's books that arrived as described. It doesn't change the score; it's shown on the profile, it's needed for the Trusted badge (90%+), and 2 books worse than listed in someone's last 5 swaps put them under review.

**Why are reviews blind, and can someone still take revenge?**
A review stays hidden until everyone in the swap has reviewed, or the 14 days for reviewing are over. Since nobody can review after those 14 days, nobody can ever read a review about themselves and then answer it: no revenge reviews. Hidden reviews don't count in the score others see, but they do count when deciding if someone should be put under review (safety first).

**What are the review rules?**
Only the receiver of a completed trade can review it, once, within 14 days. 1–2 stars need a comment. Reviews can't be edited. The person reviewed can reply once. (`bookloop/rules/reviews.py`)

**When is a swap flagged, and when is someone put under review?**
A swap is flagged when the book arrives 2 or more conditions worse than listed (for example listed "like new", arrived "fair"). Someone goes under review with a score below 3.0 after 3+ reviews, or 2 books worse than listed in their last 5 swaps. While under review they can't make offers or join rounds, until a moderator clears them.

**What are the badges?**
New: fewer than 3 reviews. Trusted: 5+ reviews, a score of 4.5 or more and 90%+ accuracy. Under review: see above.

**What can moderators do, and is it recorded?**
See flagged swaps and resolve them, clear or suspend users, and hide an abusive review with a reason. Every action is saved in `audit_log` with who did it, and so is every automatic flag. The Log tab shows them.

**How could someone cheat the score, and how would you stop it?**
Two friends could swap back and forth and give each other 5 stars. Fix: count only one review per pair of people per month, and give less weight to reviews from people with few swaps.

## Security

**How is access controlled?**
Supabase login online, permission checks in the rules and storage, `require_role` on moderator pages, and row-level security on every Supabase table, so the public API only lets a logged-in user read their own profile.

**How is input validated?**
The rules check lengths and allowed values (ISBN, condition, stars, comment length); SQL always uses parameters; the database has `CHECK` rules and foreign keys as a last line.

**How are users' passwords stored? Can you see them?**
BookLoop never stores passwords: the login form passes them straight to Supabase Auth over HTTPS. Supabase keeps only a bcrypt hash, a one-way fingerprint, so nobody can read them: not us, not Supabase. At login, Supabase hashes what you type and compares the two.

**What happens if someone forgets their password?**
There's no "Forgot password?" link yet; it's a known limit. Supabase Auth can email a reset link, but its free email sender only reaches our own team, two emails an hour. With a proper email service connected, we'd add the link. Today, an administrator can give the account a new password in Supabase, and the person keeps all their books, swaps and reviews.

**Why is email confirmation off?**
For the same reason: Supabase's free sender can't email real users, so sign-up would fail. It's off for the demo; with an email service we'd turn it back on, so nobody can sign up with an address they don't own.

**How does someone become a moderator?**
Nobody can choose it when signing up: everyone starts as a student. An administrator changes their role to `moderator` in the database, so students can't give themselves admin rights.

**Where are the database address and keys?**
Only in the hosting service's secret settings. `.env` and `.streamlit/secrets.toml` are ignored by git, and the repository and its history contain no keys.

**How do you keep the libraries safe?**
Few libraries, exact versions pinned in `uv.lock`, and `pip-audit` checks them for known vulnerabilities on every push.

## Limits we say out loud

- The loop finder doesn't always find the largest possible number of swaps. *Fix: optimise over all possible loops.*
- Two friends could swap back and forth to boost each other's scores. *Fix: one review per pair per month.*
- A handoff code proves people met, not that the condition was honest. *Fix: require a photo when listing.*
- Notifications only appear inside the app. *Fix: send an email too.*
- There's no "Forgot password?" link, and email confirmation is off for the demo. *Fix: connect an email service, add the link and turn confirmation back on.*
- Repeated no-shows are recorded but don't lead to anything automatically. *Fix: put someone under review after 2 no-shows.*
