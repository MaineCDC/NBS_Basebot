"""Continuous COVID + iGAS loop (Athena).

Runs Athena (COVID-19) and then Strep (iGAS / Group A Streptococcus) against NBS,
over and over, waiting ATHENA_LOOP_MINUTES (default 60 -- one hour) between full
passes. So
"athena" here covers BOTH conditions every cycle: Athena reviews the COVID cases
with COVID logic, Strep reviews the iGAS cases with iGAS logic. (They are separate
review pipelines -- running COVID checks on an iGAS case, or vice versa, errors
out, so each condition is handled by its own reviewer.)

One Chrome session, one login: the first bot of the first cycle performs the
single RSA login; every later run reuses the warm shared session (RSA passcodes
are single-use, so we cannot silently re-login). If NBS times the session out
during the hour-long wait, the next run detects it and pauses for a manual login
in the open Chrome window (see Base.log_in), then continues. The loop only ends
when you stop it (Ctrl-C) or a relogin is required.

Why a dedicated script instead of start_bots.py: start_bots.py now does ONE pass
and stops (its old auto-rerun spammed "bot run" emails). Athena specifically needs
to keep running on a timer and to cover both COVID and iGAS, so this loops just
those two.

Run:
    python run_athena_loop.py
You'll be prompted for your SOM username and RSA passcode (or set NBS_USER /
NBS_PASSCODE in the environment to run unattended). Stop any time with Ctrl-C.
Override the wait with ATHENA_LOOP_MINUTES.
"""
from threading import Event
from datetime import datetime
import os
import time

# Reuse the shared-Chrome launch/cleanup helpers so this runner behaves exactly
# like start_bots.py (same bot profile, same self-healing launch, same cleanup).
from start_bots import launch_chrome, kill_bot_profile_chrome
from athena_files.athena_bot import start_athena
from strep_files.strep_bot import start_strep

# Minutes to wait after each full COVID+iGAS pass before looping back to re-check
# both queues. Defaults to one hour. Periodic activity also keeps the NBS session
# warm.
LOOP_MINUTES = int(os.getenv("ATHENA_LOOP_MINUTES", "60"))

# (start function, label) in the order they run each cycle. Athena = COVID,
# Strep = iGAS -- together they cover "both covid and igas".
CYCLE = [
    (start_athena, "athena (COVID-19)"),
    (start_strep, "strep (iGAS)"),
]


def run():
    username = os.getenv("NBS_USER") or input('Enter your SOM username ("first_name.last_name"): ')
    passcode = os.getenv("NBS_PASSCODE") or input('Enter your RSA passcode: ')

    login_complete = Event()
    try:
        launch_chrome()
        cycle = 0
        while True:
            cycle += 1
            print(f"\n================= ATHENA LOOP CYCLE {cycle} =================")
            for i, (target, label) in enumerate(CYCLE):
                # First bot of the first cycle logs in; everything after reuses the
                # warm shared session.
                is_logged_in = not (cycle == 1 and i == 0)
                print(f"[cycle {cycle}] starting {label} "
                      f"({'reusing session' if is_logged_in else 'logging in'})")
                try:
                    target(username, passcode, login_complete, is_logged_in)
                except Exception as e:
                    # @error_handle already wrote the traceback to error_logs.txt;
                    # keep the loop alive so one bad pass can't stop the runner.
                    print(f"[cycle {cycle}] {label} raised an error; continuing: {e}")
                print(f"[cycle {cycle}] finished {label}.")

            print(f"================= CYCLE {cycle} COMPLETE ================="
                  f"\nWaiting {LOOP_MINUTES} minutes, then re-checking the COVID + "
                  f"iGAS queues. (Ctrl-C to stop.)")
            time.sleep(LOOP_MINUTES * 60)

    except KeyboardInterrupt:
        print("\nStop requested (Ctrl-C). Shutting down cleanly...")
    except Exception as e:
        with open("error_log.txt", "a") as log:
            log.write(f"{datetime.now().date().strftime('%m_%d_%Y')} - athena_loop - {str(e)}\n")
    finally:
        # Reap the bot-profile Chrome so the next run starts clean.
        kill_bot_profile_chrome()


if __name__ == '__main__':
    print("waking athena (continuous COVID + iGAS loop)...")
    run()
    print("athena loop stopped.")
