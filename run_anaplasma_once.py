"""Single-pass Anaplasma runner.

Launches the shared bot Chrome (same self-healing launch/cleanup as
start_bots.py), logs in once, and runs the Anaplasma bot through its queue a
single time, then stops. Credentials come from NBS_USER / NBS_PASSCODE so it can
run unattended; otherwise it prompts.

Run:
    python run_anaplasma_once.py
Stop any time with Ctrl-C.
"""
from threading import Event
from datetime import datetime
import os

from start_bots import launch_chrome, kill_bot_profile_chrome
from anaplasma_files.anaplasma_bot import start_anaplasma


def run():
    username = os.getenv("NBS_USER") or input('Enter your SOM username ("first_name.last_name"): ')
    passcode = os.getenv("NBS_PASSCODE") or input('Enter your RSA passcode: ')

    login_complete = Event()
    try:
        launch_chrome()
        print("\n================= STARTING ANAPLASMA PASS =================")
        start_anaplasma(username, passcode, login_complete, is_logged_in=False)
        print("================= ANAPLASMA PASS COMPLETE =================")
    except KeyboardInterrupt:
        print("\nStop requested (Ctrl-C). Shutting down cleanly...")
    except Exception as e:
        with open("error_log.txt", "a") as log:
            log.write(f"{datetime.now().date().strftime('%m_%d_%Y')} - anaplasma_once - {str(e)}\n")
        raise
    finally:
        kill_bot_profile_chrome()


if __name__ == '__main__':
    print("waking anaplasma...")
    run()
    print("anaplasma stopped.")
