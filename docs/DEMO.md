# Demo script (about 3 minutes)

Two browser windows side by side, with only the app open in each:

- **Left: a student.** First a new account you sign up live, then Carla.
- **Right: Morgan**, the moderator.

The steps were played in a real browser on a copy of the app with the demo data, and the messages in quotes are what the app shows. Rehearse them once on the live app before the demo.

## The demo accounts

Seven accounts were signed up on the live app for the demo. Their emails and password are in the team chat: never put them on GitHub, because this repository is public.

| Demo person | Who they are in the demo |
|---|---|
| Morgan | the **moderator** |
| Carla | a Trusted student: a handoff with Dina waiting (Dina's code is 3333) and a book from Eli to review |
| Dina | **under review**: two books arrived worse than she listed |
| Ana, Eli, Farah | the 3-way loop in the swap round |
| Ben | in the round too, but nobody wants his book |

## Before the demo

**The day before**

- [ ] In Supabase, **Authentication → Sign In / Providers → Confirm email** is off, so the live sign-up logs straight in.
- [ ] The seven demo accounts exist (**Authentication → Users**).
- [ ] Rehearse the whole script once on the live app, then reset (below).
- [ ] Look up the ISBN once and check that a cover appears: **9780134472089** (Hull, *Options, Futures, and Other Derivatives*). Backup: **9780061234002** (*Freakonomics*). If neither shows a cover, pick another book that isn't already in the demo data.

**30 minutes before**

- [ ] Supabase dashboard: the project isn't paused. A free project pauses after a week without activity.
- [ ] Open the app's address. If it says the app is asleep, click the button to wake it, and wait until the login form appears.
- [ ] **Authentication → Users:** delete the account you signed up live in the last rehearsal (**⋮ → Delete user**). Never delete the seven demo accounts.
- [ ] **Reset the demo data:** **SQL Editor → New query**, paste all of `db/demo_reset.sql`, **Run**. The round hasn't run yet, Carla's handoff is waiting, and Eli's book is waiting for Carla's review. Every date moves to today.
- [ ] **Left window:** the app's login screen, on the **Sign up** tab.
- [ ] **Right window:** log in as Morgan and open **Swap Round**.
- [ ] No passwords, dashboards or other tabs on screen. Zoom the browser to 110–125% so the room can read it.

## The script

Keep each sentence short: the steps take about 3 minutes.

| When | Window | Do | Say |
|---|---|---|---|
| 0:00 | both | — | "BookLoop lets students swap textbooks, no money involved. On the right is Morgan, our moderator. On the left, I'll be a new student." |
| 0:10 | left | **Sign up**: your first name, `demo1@example.com`, a password → **Create account**. You land on **Browse**, with the books listed. | "Anyone can sign up, and everyone starts as a student. The password goes straight to Supabase, which only keeps a hash of it." |
| 0:25 | left | Add `/Moderator` to the end of the address and press Enter. Log in again with the new account. | The app shows "You don't have permission to view this page." Say: "The menu doesn't even list the moderator pages, but hiding a link isn't security: the page itself checks the role and refuses." |
| 0:40 | left | **Log out**, then log in as Carla. | "Now Carla, a student who has already swapped a few books." |
| 0:50 | left | **My Shelf** → ISBN `9780134472089` → **Look up**. The title, authors and cover appear. Choose a **Condition** (good) → **Add to my shelf**. | "Type an ISBN and the details and cover come from Open Library. If Open Library is down or slow, a form appears instead, so listing never breaks." The app shows "“…” is on your shelf and visible in Browse." |
| 1:15 | right | On **Swap Round** ("Winter textbook swap"), click **Run round**. | The app shows "Found 1 loop: 3 books will change hands and 1 goes back on the shelf." and "**Loop 1:** Ana → Farah → Eli → Ana", with a picture of the loop. Say: "Ana gives her book to Farah, Farah gives hers to Eli, and Eli gives his to Ana. No two of them wanted each other's books, so no direct swap was possible: the app found the circle. Nobody wanted Ben's book, so it goes back on his shelf. They all meet at the same time and place, and nobody hands over a book until everyone is there." |
| 1:45 | left | **My Swaps**. Carla meets Dina at the Student centre and gives her *Automate the Boring Stuff with Python*. Type `0000` in **Receiver's 4-digit code** → **Confirm handoff**. | "The giver types the receiver's code. A wrong code…" The app shows "The handoff code is incorrect." |
| 1:55 | left | Type `3333` (Dina's code) → **Confirm handoff**. | "…and the right one." The app shows "Handoff confirmed. The book now belongs to the receiver." Say: "Three wrong codes would lock the trade. The code proves they met." |
| 2:10 | left | **Profile** → *Chemistry: The Central Science* from Eli, listed as *like new*. **1. How did the swap with Eli go?** 2 stars. **2. What condition did the book arrive in?** poor. Comment "Listed like new, but the cover is torn." → **Submit review**. | "A review has two parts: stars for the person and the meeting, and the condition the book really arrived in." The app says the review is saved, both reviews are now visible, and "a moderator will check the swap". Say: "Reviews stay hidden until everyone has reviewed or the 14 days are over, so nobody can review in revenge. Eli had already reviewed Carla, so both appear now." |
| 2:30 | left | In **Whose profile**, choose **Eli**. | Eli's Swapper Score is **3.50**. "Everyone starts at 4.00, as if they had three 4-star reviews, so one review can't make you perfect or ruin you." |
| 2:40 | right | **Moderator** → **Flagged swaps**. | The new flag is at the top: "Chemistry: The Central Science: Eli → Carla, arrived poor · ★★☆☆☆". Say: "The book arrived two conditions worse than listed, so the swap was flagged automatically. Morgan can resolve it, or suspend Eli." |
| 2:55 | — | — | "Behind this: the rules are separate from the pages, about 300 tests run on every push, and the data is in Supabase with row-level security." |

## If something goes wrong

| What you see | What to do |
|---|---|
| Sign up says the email is already registered. | Last rehearsal's account wasn't deleted. Use `demo2@example.com` and carry on. |
| Sign up says "Account created. Confirm the email, then log in." | Email confirmation is on. Skip the live sign-up: log in as Carla, and do the moderator-page check with her. |
| "Open Library doesn't know this ISBN, or didn't answer in time." | Say "this is our fallback", type the title (*Options, Futures, and Other Derivatives*) and author (*John C. Hull*), and carry on. |
| No **Run round** button; it says "This round created 1 loop." | The round already ran (the data wasn't reset). The loop is still listed underneath, so explain it from there. |
| No handoff form on My Swaps | The handoff was already done. Say what it does and move on. |
| The trade is locked | Never type more than one wrong code. |
| Nothing waiting for review | The review was already left. Show Eli's profile and the flag instead. |
| The app is slow to respond | Free hosting can be slow on the first click after waking. Wait a few seconds, and don't click twice. |

## The online demo data

`seed.py` only builds the laptop database. Online, people log in with Supabase accounts, so the demo data is linked to the seven demo accounts:

1. **Once:** sign up on the live app's **Sign up** tab with the first names **Morgan, Ana, Ben, Carla, Dina, Eli, Farah**.
2. **Before each demo or rehearsal:** in Supabase's **SQL Editor**, run `db/demo_reset.sql`. It deletes every book, swap, round, review and notification online (accounts are kept), loads the same demo data as `seed.py` linked to those accounts by first name, makes Morgan the moderator and puts Dina under review. It's one transaction: if anything fails (for example a demo account is missing), nothing changes. It also removes the profiles of accounts deleted in **Authentication → Users**.

From a laptop with the project and `DATABASE_URL`, `uv run python reset_online_demo.py --yes` does the same. If the demo data in `seed/` changes, write the SQL file again with `uv run python reset_online_demo.py --sql db/demo_reset.sql`.

## Rehearsing on a laptop

Run `uv run python seed.py`, then `uv run streamlit run app.py`. The dev login replaces sign-up, email and password: pick a demo user from the list. For the moderator-page check, open http://localhost:8501/Moderator and choose Carla. Run `seed.py` again to reset everything.
