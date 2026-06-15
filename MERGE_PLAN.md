# NBS Bots — Unification & Multi-Bot Merge Plan

**Goal:** One repo (`NBS_Basebot`, the team's, since it has the most bots and is the most
accessible) that adopts `nbsbot.v1.5`'s shared-session architecture, runs **all** bots in a
**continuous round-robin loop** off **one login**, saves Excel safely (no permission-denied
crashes), and stops randomly crashing.

**Decisions (2026-06-15):**
- Home repo = `NBS_Basebot` (remote `MaineCDC/NBS_Basebot`).
- Architecture transplanted *from* `nbsbot.v1.5` (shared Chrome on debug port 9223). We do
  **not** merge the other direction — that would re-break the relogin fix.
- Run model = continuous round-robin (one login, cycle bots, keep checking dropdowns for new cases).

---

## Architecture: before → after

| | NBS_Basebot (now) | nbsbot.v1.5 (now) | Unified (target) |
|---|---|---|---|
| Browser | each bot launches its **own** Chrome (`webdriver.Chrome` subclass) | **one** shared Chrome on `debuggerAddress 127.0.0.1:9223` | shared Chrome (v1.5 model) |
| Login | per-bot RSA form, **one passcode per bot** | login once, `log_in(is_logged_in)` skips RSA when warm | login **once** for the whole run |
| Multi-bot | `threading.Thread` per bot | sequential, session shared | **continuous round-robin loop** |
| Base files | **4 forks**: `Base.py`, `Base_IH.py`, `base_athena.py`, `base_strep.py` | **1**: `base.py` | **1** unified `Base.py` |
| `start_*` sig | `(username, passcode)` (+ 2 oddballs) | `(username, passcode, login_complete, is_logged_in=False)` | the v1.5 4-arg contract for all |
| Excel save | `df.to_excel()`, no lock handling | `save_and_print_results()`, no lock handling | `safe_save_excel()` w/ retry + fallback |

---

## Phase 0 — Safety & setup

1. In `NBS_Basebot`, create branch `merge-shared-session` (never touch `main` directly).
2. Extend `NBS_Basebot/.gitignore` so runtime junk is never committed:
   `logfile.txt`, `liverun_output.txt`, `run_*_debug.out`, `*.out`, `Error_logs.txt`,
   `error_logs.txt`, `chrome-bot-profile/`, `chrome_profile/`, `__pycache__/`, `~$*.xlsx`,
   `env/`, `.env`.
3. Confirm `requirements.txt` covers v1.5's extra deps: `python-dotenv`, `tqdm`,
   `webdriver-manager` (used by v1.5's driver). Add any missing.
4. Snapshot both base classes' method lists (done) for the Phase 1 reconciliation below.

**Deliverable:** clean branch, correct `.gitignore`, aligned `requirements.txt`.

---

## Phase 1 — Unify the base class (highest risk)

Build **one** `Base.py` in `NBS_Basebot` from v1.5's richer `base.py` (it already has the
shared-session driver, `log_in(is_logged_in)` + warm-session skip, tab nav,
`save_and_print_results`, `disease_case_count`), then fold in everything the team bots need
that only exists in the Basebot forks.

### 1a. Method reconciliation (Base.py ↔ base.py)
The two are ~90% aligned. Known deltas to resolve **before** swapping:

| Concern | NBS_Basebot `Base.py` | v1.5 `base.py` | Action |
|---|---|---|---|
| Demographics nav | `cgo_to_demographics` (typo) | `go_to_demographics` | Add a `cgo_to_demographics = go_to_demographics` alias OR rename callers. Grep all team bots first. |
| Perf. lab check | `CheckPreformingLaboratory` (misspelled) | `CheckPerformingLaboratory` | Keep both names (alias) so no bot breaks. |
| `CheckRace` | has nested `get_race_list` | different impl | Diff behavior; keep whichever the team bots rely on, expose both code paths if needed. |
| Excel | `CreateExcelSheet` only | `save_and_print_results` + `disease_case_count` + `CreateExcelSheet` | Unified base keeps **all three** (route through `safe_save_excel`, Phase 3). |
| Login | `log_in(self)` RSA-only | `log_in(is_logged_in)` + `_log_in_inductive` + `log_in_v2` | Keep v1.5's; verify every team bot calls `log_in(is_logged_in)` after Phase 2. |

**Method-by-method grep of every `NBS.<method>()` call in all `*_bot.py` / disease `*.py`
files happens here** — any base method a team bot calls that's missing/renamed in the unified
base is added or aliased. Nothing is deleted blind.

### 1b. Fold in the 3 other base forks
- **`Base_IH.py`** (ILIOutbreak, SSO/Inductive Health login, `social-mesaml` click, no RSA):
  its SSO path already exists in v1.5 as `_log_in_inductive` / the test-site branch. Route
  ILIOutbreak through the unified `log_in` behind a site/environment flag. Delete `Base_IH.py`.
- **`base_athena.py`** (athena-prod; wraps methods in try/except, `self.driver = self`):
  the `self.driver = self` trick existed to hand athena's browser to strep. With one shared
  Chrome, that's obsolete — strep just attaches to 9223 like everyone else. Migrate any
  athena-only try/except hardening into the unified base (Phase 5 does this globally). Delete
  `base_athena.py`.
- **`base_strep.py`** (strep-prod; **not** a `webdriver.Chrome` subclass — reuses athena's
  driver): collapse into a normal shared-session `Strep(NBSdriver)` subclass. Delete `base_strep.py`.

**Deliverable:** single `NBS_Basebot/Base.py`; `Base_IH.py`, `base_athena.py`, `base_strep.py`
removed; all base methods every bot calls are present (real name or alias).

---

## Phase 2 — Put every bot on the shared-session contract

Standardize **every** `start_*` to `(username, passcode, login_complete: Event=None,
is_logged_in=False)` and make each pass `is_logged_in` into `log_in`.

| Bot | Current sig | Change |
|---|---|---|
| anaplasma, giardia, babesia | already 4-arg (v1.5) | bring over as-is |
| athena | `(username, passcode)` | add 2 params; drop the `self.driver`→strep hand-off |
| audrey | `(username, passcode)` | add 2 params + `is_logged_in` into `log_in` |
| strep | `(username,passcode)` **and** `(driver)` (two forms) | collapse to one 4-arg shared-session bot |
| CovidECR | `(username, passcode)` | add 2 params |
| HepB | `(username, passcode)` | add 2 params |
| Gonorrhea | `(username, passcode)` | add 2 params |
| ILIOutbreak | `()` (no args, SSO) | give it the 4-arg sig; SSO handled in unified `log_in` |

Also: **copy `giardia_files/` and `babesia_files/` from v1.5 into `NBS_Basebot`**, plus their
runners (`run_anaplasma.py`, `run_babesia.py`) and `decorator.py` (the `@error_handle` v1.5
bots use — reconcile with Basebot's `custom_decorator.py`).

**Deliverable:** all bots import the unified `Base.py`, share one session, and present the same
4-arg entry point.

---

## Phase 3 — Bullet-proof Excel saving (the permission-denied fix)

Add one helper to the unified base and route **every** Excel write through it:

```python
def safe_save_excel(self, df, path, retries=3, wait=2):
    """Write df to path; if the file is open/locked (PermissionError), retry a few
    times, then fall back to '<name>_<HHMMSS>.xlsx' so a run NEVER loses results
    or crashes because someone left the workbook open in Excel."""
    import time
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    for attempt in range(retries):
        try:
            df.to_excel(path)
            return path
        except PermissionError:
            if attempt < retries - 1:
                time.sleep(wait)
            else:
                stamp = datetime.now().strftime("%H%M%S")
                base, ext = os.path.splitext(path)
                alt = f"{base}_{stamp}{ext}"
                df.to_excel(alt)
                print(f"[safe_save_excel] {path} was locked; wrote {alt} instead.")
                return alt
```

- Route `save_and_print_results`, `CreateExcelSheet`, and every direct `df.to_excel(...)` in
  the team bots (`anaplasma_bot.py:162`, `Gonorrhea_bot.py:159`, `audrey_bot.py:2055`,
  `strep_bot.py:157`, `HepBnotificationreview_bot.py:164`, `ILIOutbreak_bot.py:143`,
  `Base.py:CreateExcelSheet`) through `safe_save_excel`.
- **Fix the `CreateExcelSheet` filename bug:** it uses `%H:%M:%S` — colons are illegal in
  Windows filenames and crash the save. Change to `%H%M%S`.

**Deliverable:** no run ever dies on a locked/open `.xlsx`; results always land somewhere.

---

## Phase 4 — Continuous round-robin orchestrator

Rewrite `NBS_Basebot/start_bots.py` (keep v1.5's `launch_chrome` / `kill_bot_profile_chrome` /
`clear_profile_locks` / `wait_for_port` helpers — they already exist and work):

```
launch Chrome once (port 9223, dedicated profile)
prompt username + RSA passcode ONCE
first_pass = True
idle_cycles = 0
while not stop_requested:
    any_work = False
    for bot in selected_bots:
        is_logged_in = not (first_pass and bot is first_bot)
        cases_done = bot(username, passcode, login_complete, is_logged_in)  # returns count
        any_work = any_work or cases_done > 0
    first_pass = False
    if not any_work:
        idle_cycles += 1
        sleep(IDLE_BACKOFF)          # e.g. 5 min between empty sweeps
        if idle_cycles >= MAX_IDLE:  # optional clean auto-stop
            break
    else:
        idle_cycles = 0
```

- Each `start_*` already "ends itself when its queue is empty"; we wrap that in the outer loop
  so after the last bot we loop back to the first and **re-check every dropdown for new cases**.
- Make each `start_*` **return the number of cases it actioned** this pass (so the loop knows
  when everything's idle and can back off instead of hammering NBS).
- Clean stop: `Ctrl-C` (KeyboardInterrupt) → finish current case, save, exit; plus optional
  `MAX_IDLE` empty-sweep auto-stop.
- Session-keepalive: if NBS times out the session during a long idle, the next bot's
  `log_in(is_logged_in=True)` warm-check will detect it's logged out and re-auth (one place to
  handle re-login, not per bot).

**Deliverable:** start once, log in once, bots cycle forever checking dropdowns, no relogin.

---

## Phase 5 — Crash hardening (stop the random crashes)

Apply across the unified base + disease modules:

1. **`ReadText` never returns `None`** — return `""` when retries exhaust, so the many callers
   doing `.replace()/.lower()/ in` stop throwing `AttributeError`. (#1 random-crash cause.)
2. **Promote babesia's `_safe()` wrapper into the base** so every `Check*` records its error
   into `self.check_errors` instead of crashing the whole case.
3. **Fix no-arg `self.issues.append()`** at `anaplasma.py:663` and `babesia.py:769` (`TypeError`).
4. **Replace `sys.exit()`** in `go_to_home` / `go_to_home_from_error_page` with a recoverable
   exception so one bad page fails one case, not the whole run.
5. **Harden `RejectNotification` / `ApproveNotification`** window indexing
   (`handles[2] if len>2 else handles[1]` assumption) — verify the popup window explicitly.
6. **Narrow bare `except:`** blocks that currently swallow real errors and produce confusing
   downstream `None`s; log what they catch.

**Deliverable:** a bad case or flaky read degrades to "skip + log", never a process crash.

---

## Phase 6 — Test each bot (safe, no prod changes)

1. Run with `ENVIRONMENT=development` (test site) and `DRY_RUN=1` where supported to walk each
   bot end-to-end with **zero production mutations** (no Approve/Reject/email).
2. Test order: each bot **alone** first (anaplasma, giardia, babesia, athena, audrey, strep,
   CovidECR, HepB, Gonorrhea, ILIOutbreak), then **all together** through the round-robin loop.
3. For each bot capture: does it log in via the shared session? sort its dropdown? count cases?
   save Excel via `safe_save_excel`? loop back and re-check? Log every crash cause found.
4. Verify the **no-relogin** goal: select 3+ bots, confirm exactly **one** passcode prompt.
5. Verify the **permission-denied** goal: open a results `.xlsx` in Excel mid-run, confirm the
   bot writes the fallback file instead of crashing.

**Deliverable:** a per-bot pass/fail table + list of remaining issues.

---

## Phase 7 — Commit & push

- Commit per phase with clear messages on `merge-shared-session`.
- Open a PR to `MaineCDC/NBS_Basebot` summarizing the architecture change so the team reviews
  before it hits `main`.
- Keep `nbsbot.v1.5` untouched as a reference until the team has adopted the unified repo.

---

## Risks & how we de-risk

| Risk | Mitigation |
|---|---|
| Phase 1 silently breaks a colleague's working bot | Grep every `NBS.<method>()` call before swapping the base; alias renamed methods; no blind deletes. |
| A team bot relies on per-bot browser behavior | Tested alone in Phase 6 before the combined loop. |
| Test site differs from prod (XPaths) | v1.5 already has the dev/prod `_field()` split for babesia; extend the pattern where needed. |
| Long idle logs the bot out of NBS | Warm-session re-login in `log_in(is_logged_in=True)` handles it in one place. |
| Big binary/log files bloat the repo | `.gitignore` in Phase 0. |

## Out of scope (flag, don't do unless asked)
- Rewriting the NBS XPath selectors wholesale.
- Changing any bot's clinical/review decision logic (we preserve each bot's existing rules).
- Switching off Selenium / changing the automation stack.
