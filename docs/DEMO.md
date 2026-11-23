# Demo script (about 3 minutes)

Two browser windows side by side, with only the app open in each:

- **Left: Carla**, a student.
- **Right: Morgan**, the moderator.

Every step below was played on the demo data in a real browser, and the messages in quotes are exactly what the app shows.

## Before the demo

**The day before**

- [ ] The demo accounts exist on the live app (see [The online demo data](#the-online-demo-data) below), and `uv run python reset_online_demo.py` finds all seven.
- [ ] Rehearse the whole script once on the online app, then reset the demo data.
- [ ] Look up the ISBN for step 2 once and check that a cover appears: **9780134472089** (Hull, *Options, Futures, and Other Derivatives*). Backup: **9780061234002** (*Freakonomics*). If neither shows a cover, pick another book that isn't already in the demo data.

**30 minutes before**

- [ ] Supabase dashboard: the project isn't paused. A free project pauses after a week without activity.
- [ ] Open the app's address. If it says the app is asleep, click the button to wake it, and wait until the login form appears.
- [ ] Reset the demo data: `uv run python reset_online_demo.py --yes`. The round hasn't run yet, Carla's handoff is waiting, and Eli's book is waiting for Carla's review. The dates follow the day of the reset, so always reset on the demo day.
- [ ] **Left window:** open the app's address with `/Moderator` at the end, and log in as Carla. She sees "You don't have permission to view this page." Leave it like that: it's the first thing you show.
- [ ] **Right window:** log in as Morgan and open **Swap Round**.
- [ ] No passwords, dashboards or other tabs on screen. Zoom the browser to 110–125% so the room can read it.

## The script

The steps follow the plan's order, except the student check (plan step 6) comes first, because Carla's window is already showing it.

| When | Window | Do | Say |
|---|---|---|---|
| 0:00 | both | — | "BookLoop lets students swap textbooks, no money involved. On the left is Carla, a student; on the right Morgan, our moderator." |
| 0:10 | left | Point at the error and at Carla's menu. | "Carla typed the Moderator page's address. Her menu doesn't even list it, but hiding a link isn't security: the page itself checks her role and refuses. Morgan's menu has Moderator and Stats." |
| 0:25 | left | **My Shelf** → ISBN `9780134472089` → **Look up**. The title, authors and cover appear. Choose a **Condition** (good) → **Add to my shelf**. | "Type an ISBN and the details and cover come from Open Library. If Open Library is down or slow, a form appears instead, so listing never breaks." The app shows "“…” is on your shelf and visible in Browse." |
| 0:55 | right | On **Swap Round** ("Winter textbook swap"), click **Run round**. | The app shows "Found 1 loop: 3 books will change hands and 1 goes back on the shelf." and "**Loop 1:** Ana → Farah → Eli → Ana", with who gives which book. Say: "Ana gives her book to Farah, Farah gives hers to Eli, and Eli gives his to Ana. No two of them wanted each other's books, so no direct swap was possible; the app found the circle. Nobody wanted Ben's book, so it goes back on his shelf, and everyone got a notification." |
| 1:30 | left | **My Swaps**. Carla meets Dina at the Student centre: she gives *Automate the Boring Stuff with Python*. Type `0000` in **Receiver's 4-digit code** → **Confirm handoff**. | "The giver types the receiver's code. A wrong code…" The app shows "The handoff code is incorrect." |
| 1:45 | left | Type `3333` (Dina's code) → **Confirm handoff**. | "…and the right one." The app shows "Handoff confirmed. The book now belongs to the receiver." Say: "Three wrong codes would lock the trade. The code proves they met." |
| 2:00 | left | **Profile** → under "Swaps waiting for your review": *Chemistry: The Central Science* from Eli, listed as *like new*. Stars **2**, condition as described **No**, actual condition **poor**, comment "Listed like new, but the cover is torn." → **Submit review**. | "Yesterday Eli gave Carla a book he listed as like new. It wasn't." The app says the review is saved, both reviews are now visible, and "a moderator will check the swap". Say: "Reviews are blind until everyone in the swap has reviewed, so nobody can take revenge. Eli had already reviewed Carla, so both appear now." |
| 2:25 | left | In **Whose profile**, choose **Eli**. | Eli's Swapper Score is **3.50**. "Everyone starts at 4.00, as if they had three 4-star reviews, so one review can't make you perfect or ruin you. Eli's first real review pulled him down to 3.50." |
| 2:35 | right | **Moderator** → **Flagged swaps**. | The new flag is at the top: "Chemistry: The Central Science: Eli → Carla, arrived poor · ★★☆☆☆". Say: "The book arrived two conditions worse than listed, so the swap was flagged automatically. Morgan can resolve it, or suspend Eli." |
| 2:50 | — | — | "Behind this: the rules are separate from the pages, about 290 tests run on every push, and the data is in Supabase with row-level security." |

## If something goes wrong

| What you see | What to do |
|---|---|
| "Open Library doesn't know this ISBN, or didn't answer in time." | Say "this is our fallback", type the title (*Options, Futures, and Other Derivatives*) and author (*John C. Hull*), and carry on. |
| No **Run round** button; it says "This round created 1 loop." | The round already ran (the data wasn't reset). The loop is still listed underneath, so explain it from there. |
| No handoff form on My Swaps | The handoff was already done. Say what it does and move on. |
| The trade is locked | Never type more than one wrong code. |
| Nothing waiting for review | The review was already left. Show Eli's profile and the flag instead. |
| The app is slow to respond | Free hosting can be slow on the first click after waking. Wait a few seconds, and don't click twice. |

## The online demo data

`seed.py` only builds the laptop database. Online, people log in with Supabase accounts, so the demo data has to be linked to real accounts:

1. **Once:** on the live app's **Sign up** tab, create an account for each demo person with these first names: **Morgan, Ana, Ben, Carla, Dina, Eli, Farah** (any emails you can open, and passwords kept in a password manager).
2. **Before each demo**, from a laptop with the project, with `DATABASE_URL` set to the online database (in the terminal or in `.streamlit/secrets.toml`):
   ```bash
   uv run python reset_online_demo.py        # checks that all seven accounts exist; changes nothing
   uv run python reset_online_demo.py --yes  # resets the online demo data
   ```
   The reset deletes every book, swap, round, review and notification online (accounts are kept), loads the same demo data as `seed.py` linked to those accounts, makes Morgan the moderator and puts Dina under review. It's one transaction: if anything fails, nothing changes.

## Rehearsing on a laptop

Run `uv run python seed.py`, then `uv run streamlit run app.py`. The dev login replaces email and password. For the first step, open http://localhost:8501/Moderator and choose Carla. Run `seed.py` again to reset everything.
