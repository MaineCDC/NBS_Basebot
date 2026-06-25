# NBS Bots — Status & How to Run

A plain-English guide to the NBS bot suite: what each bot does, how the bots run,
and how to start them (written for people who have never touched the code).

- [1. What these bots are](#1-what-these-bots-are)
- [2. How to run the bots (for noobs)](#2-how-to-run-the-bots-for-noobs)
- [3. How the bots run (round-robin + shared session)](#3-how-the-bots-run-round-robin--shared-session)
- [4. Neat features: retrying & same-session management](#4-neat-features-retrying--same-session-management)
- [5. Status of every bot](#5-status-of-every-bot)
- [6. Environment & site selection (prod vs test)](#6-environment--site-selection-prod-vs-test)
- [7. Known issues](#7-known-issues)

---

## 1. What these bots are

Each bot is a small program that logs into **NBS** (the Maine disease surveillance
system) in a real Chrome window and reviews cases for one disease — the same
clicking and checking a human reviewer would do. Depending on the bot it will
**approve** clean notifications, **reject** ones with problems (with a comment
explaining why), and/or **email** the people who need to fix or assign a case.

All bots share one base class, [`NBSdriver`](../Base.py) in [Base.py](../Base.py),
which handles login, queue navigation, reading fields, and sending email. Each
bot lives in its own `*_files` folder with two key files:

- `*_bot.py` — the entry point (a `start_<name>` function) that drives the queue loop.
- `<name>.py` — the disease-specific class with all the validation checks.

The orchestrator that launches everything is [start_bots.py](../start_bots.py).

---

## 2. How to run the bots (for noobs)

> You need Python installed and Google Chrome installed. The repo ships a virtual
> environment in `env/`.

### Step-by-step

1. **Open a terminal** (PowerShell) in the project folder
   (`...\NBS_Basebot`).

2. **Activate the virtual environment:**
   ```powershell
   .\env\Scripts\Activate.ps1
   ```
   (You should see `(env)` appear at the start of your prompt.)

3. **Start the bots:**
   ```powershell
   python start_bots.py
   ```

4. **Pick which bots to run.** You'll see a numbered menu:
   ```
   1. athena        (COVID-19)
   2. audrey        (Hep B/C lab review)
   3. anaplasma
   4. giardiasis
   5. strep         (Group A Strep / iGAS)
   6. babesia       (testing only)
   7. CovidEcr      (COVID lab/eCR)
   8. HepBnotificationreview
   9. Gonorrhea
   10. ILIOutbreak  (testing only)
   ```
   Type the numbers separated by spaces, e.g.:
   ```
   1 5 9
   ```
   **The order you type is the order they run.** (So `5 1` runs strep first, then athena.)

5. **Enter your login when asked:**
   - **SOM username** in the form `first_name.last_name`
   - **RSA passcode** (your PIN + the current token code)

6. **Watch it go.** Chrome opens, the first bot logs in, then each selected bot
   takes its turn. The terminal prints progress like
   `starting bot 1/3: athena (logging in)`.

7. **When every selected bot has gone through its queue once, the program stops
   on its own.** You'll see `PASS COMPLETE`. To run them again, just run
   `python start_bots.py` again.

8. **To stop early at any time:** press `Ctrl-C` in the terminal. It shuts down
   cleanly and closes the bot's Chrome.

### What you'll get

- The bots act directly in NBS (approve/reject) as they go.
- Some bots email summaries to `disease.reporting@maine.gov` and/or route cases to
  epidemiologists (see the table in [section 5](#5-status-of-every-bot)).
- Excel run logs are written under `saved/` for bots that produce them.
- Errors are appended to `error_logs.txt` (per-function) and `error_log.txt`
  (orchestrator) — check these first if something looks wrong.

---

## 3. How the bots run (round-robin + shared session)

When you select several bots, they run in a **single round-robin pass**:

```
log in once  ->  athena's queue  ->  strep's queue  ->  gonorrhea's queue  ->  STOP
              \________________ one shared Chrome session ________________/
```

- **One login, one browser.** The very first bot logs in. Every bot after it
  reuses that same warm session (`is_logged_in=True`), so you only authenticate
  once no matter how many bots you picked.
- **Each bot finishes its own queue, then hands off.** A bot keeps reviewing
  cases for its disease until its queue has no more matching cases, then returns
  so the next bot can start.
- **After the last bot, the program stops** — *unless athena is selected*. It
  does **not** loop back and re-run the bots automatically for a non-athena
  selection.

- **Athena loops continuously.** If `athena` is one of the selected bots,
  `start_bots.py` keeps running: it cycles the whole selected list, sleeps
  `ATHENA_LOOP_MINUTES` (default **60** — one hour), then runs them again, around
  the clock, until you Ctrl-C or the session needs a fresh login. This is the
  default way to run athena (the standalone `run_athena_loop.py` does the same
  thing for just COVID + iGAS). Athena only emails when a case actually needs
  manual review, so the loop doesn't spam.

> **Note (changed):** The bots used to loop forever — after finishing every bot
> they would sleep ~5 minutes and run the whole list again, and again, around the
> clock. That re-running is what spammed "bot run" emails even when there were no
> new cases. The unconditional auto-rerun was **removed**: a selection *without*
> athena now does exactly one pass and stops. Looping is now scoped to athena
> (whose pass is silent when there's nothing to do). Run `start_bots.py` again
> whenever you want another one-off pass of the non-athena bots.

---

## 4. Neat features: retrying & same-session management

These are the resilience features that let the suite run unattended without a
human babysitting Chrome.

### Same-session management
- **Single shared login.** `start_bots.py` launches one Chrome with remote
  debugging and passes a shared `login_complete` event between bots. Only the
  first bot authenticates; the rest attach to the live session
  (`is_logged_in=True`). No repeated RSA prompts, no duplicate browsers.
- **Site-conflict guard.** Production and the test site are *different websites*,
  but there's only one browser. Before running, the orchestrator drops any
  selected bot whose target site doesn't match the session (see
  [section 6](#6-environment--site-selection-prod-vs-test)) instead of letting a
  prod bot and a test bot fight over the same window.
- **Self-healing Chrome launch.** If a previous run crashed and left a Chrome
  bound to the bot profile, the launcher kills *only* that bot-profile Chrome
  (never your personal Chrome), clears stale lock files, and retries opening the
  debug port. On exit it reaps the bot Chrome so the next run starts clean.

### Retrying / error recovery
- **One bad bot can't stop the others.** Each bot call is wrapped so an exception
  is logged and the round-robin continues to the next bot.
- **Poison-case skipping.** If a single case throws mid-review, most bots record
  its name in a `skipped_names` set, reset to a clean queue, and step past it —
  so one broken case can't wall off every case behind it or get re-reviewed
  forever.
- **Consecutive-error cap.** Most bots stop their pass after ~5 errors in a row
  (an empty/unstable queue often surfaces as repeated stale-element reads),
  instead of spinning.
- **Per-pass case cap.** `MAX_CASES_PER_PASS` (default 500) is a backstop so a
  stuck case can't loop indefinitely.
- **Incremental saves.** Bots that write Excel logs snapshot every
  `SAVE_EVERY_CASES` cases (default 10), so a hard kill loses at most that batch.
- **Queue recovery.** On a bad/empty queue return, bots navigate home and
  re-request the queue (`HandleBadQueueReturn`) rather than crashing.
- **Hard reset after repeated page errors.** When a bot errors on the same page
  **twice in a row**, `RecoverQueueAfterError` bounces it through the Home page
  (a hard URL navigation that tears down a frozen/stuck page) before reloading the
  queue, so the current case gets re-filtered from a clean slate. The first error
  just reloads the queue in place; the streak resets as soon as a case loads
  normally again.
- **Persistent skip list.** Several bots read/write `patients_to_skip.txt` so
  flagged patients stay skipped across runs.

### Useful environment variables (optional)
| Variable | Default | Effect |
|---|---|---|
| `ENVIRONMENT` | `production` | Set to `development` to force **all** bots onto the test site. |
| `MAX_CASES_PER_PASS` | `500` | Max cases a bot reviews in one pass. |
| `SAVE_EVERY_CASES` | `10` | How often Excel logs are snapshotted. |
| `DRY_RUN` | varies | For bots that support it, walk the queue and log actions **without** changing anything. (Babesia defaults to dry-run.) |

---

## 5. Status of every bot

| # | Bot | Disease / condition | What it does | Ends its pass when… | Summary email | Status |
|---|-----|--------------------|--------------|---------------------|---------------|--------|
| 1 | **athena** | COVID-19 (notifications) | Approves clean notifications, rejects with comments | No COVID cases left, or hits error/case cap | `SendManualReviewEmail` (not-a-case / lab issues) | **Active** |
| 2 | **audrey** | Hep B & C (lab/ELR review) | Creates investigations, associates labs, assigns to epis | Queue exhausted (end-of-queue) | `SendManualReviewEmail` + epidemiologist emails | **Active** |
| 3 | **anaplasma** | Anaplasmosis | Approves/rejects notifications | 3 consecutive "no case" reads, or case cap | `SendAnaplasmaEmail` + `case_skipping.txt`; run-complete email | **Active** (supports dry-run) |
| 4 | **giardia** | Giardiasis | Approves/rejects notifications | No Giardia cases, or queue-load failures | `SendGiardiaEmail` (conditional) | **Active** |
| 5 | **strep** | Group A Strep / **iGAS** | Approves/rejects; finds reject row by name after re-sort | No more iGAS cases, or error/case cap | `SendManualReviewEmail` + `SendBotRunEmail` | **Active** |
| 6 | **babesia** | Babesiosis | Approves/rejects (record-only by default) | 3 consecutive "no case" reads, or case cap | `SendAnaplasmaEmail` (only when not dry-run) | **Testing** (test site, dry-run default) |
| 7 | **CovidEcr** | COVID-19 (eCR / lab) | Creates investigations, associates labs, imports ImmPact vax | No more document IDs in queue | None | **Active** (lighter error recovery) |
| 8 | **HepBnotificationreview** | Hepatitis B (notifications) | Approves/rejects; assigns to epis | No HepB cases, or error/case cap | `SendBotRunEmail` + `SendEmailToAssign` | **Active** (supports dry-run) |
| 9 | **Gonorrhea** | Gonorrhea | Approves/rejects; skips out-of-country | No more Gonorrhea cases, or error/case cap | `SendManualReviewEmail` + `SendGonorrheaEmail` | **Active** |
| 10 | **ILIOutbreak** | ILI-Related Outbreak | Approves/rejects | No ILI cases, or error/case cap | `SendBotRunEmail` + `SendEmailToIliAssign` | **Testing** (test site) |

> "Active" = used against production. "Testing" = locked to the InductiveHealth
> test site (see below) and/or defaults to dry-run; promote by removing it from
> `TEST_LOCKED_BOTS` in [bot_env.py](../bot_env.py).

---

## 6. Environment & site selection (prod vs test)

Defined in [bot_env.py](../bot_env.py):

- **Default:** every bot runs against **PRODUCTION**.
- **`TEST_LOCKED_BOTS`** (`babesia`, `ILIOutbreak`) **always** run against the
  **test site**, because they aren't promoted to production yet.
- Setting **`ENVIRONMENT=development`** in a `.env` file forces **all** bots onto
  the test site (good for a full dry run).
- Because one Chrome session can only be on one site, if you select a mix of prod
  and test bots in the same run, the orchestrator keeps the ones matching the
  session and **skips the rest** (it tells you which, and why). Run the skipped
  ones separately.

Each bot prints its target at startup, e.g. `[athena] target site: PRODUCTION`.

