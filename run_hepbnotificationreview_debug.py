"""
Standalone runner for the HepBnotificationreview bot only.
Runs ONLY HepBnotificationreview and bypasses the error_handle decorator so any unhandled
exception is printed with a full traceback instead of being swallowed.

Uses the shared-session model: launches the debug Chrome on port 9223, then
attaches HepB to it (same as start_bots.py, just for one bot).
"""
from threading import Event
from start_bots import launch_chrome
from HepBnotificationreview_files.HepBnotificationreview_bot import start_HepBnotificationreview


def main():
    username = input('SOM username (first_name.last_name): ').strip()
    password = input('RSA password: ').strip()
    launch_chrome()
    login_complete = Event()
    # Bypass @error_handle so tracebacks surface instead of being logged+swallowed.
    target = getattr(start_HepBnotificationreview, "__wrapped__", start_HepBnotificationreview)
    target(username, password, login_complete, False)


if __name__ == '__main__':
    main()
