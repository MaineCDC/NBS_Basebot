"""Staged LIVE run of the HepB notification bot for debugging.

Real run (it will approve/reject real cases), but capped via MAX_CASES_PER_PASS
so we can verify the first few actions in NBS before clearing the whole queue.
Calls the undecorated function so tracebacks surface instead of being swallowed.
Credentials come from env (NBS_USER / NBS_PASS) -- not stored on disk.
"""
import os
from threading import Event
from start_bots import launch_chrome
from HepBnotificationreview_files.HepBnotificationreview_bot import start_HepBnotificationreview

username = os.environ["NBS_USER"]
passcode = os.environ["NBS_PASS"]

print(f"MAX_CASES_PER_PASS={os.environ.get('MAX_CASES_PER_PASS', '(default)')}", flush=True)
print("launching chrome...", flush=True)
launch_chrome()

login_complete = Event()
fn = getattr(start_HepBnotificationreview, "__wrapped__", start_HepBnotificationreview)
print("starting HepB (LIVE, capped)...", flush=True)
fn(username, passcode, login_complete, False)
print("HepB run finished (capped).", flush=True)
