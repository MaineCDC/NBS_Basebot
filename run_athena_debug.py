"""
Standalone runner for the Athena (COVID notification review) bot only.
Runs ONLY Athena and bypasses the error_handle decorator so any unhandled
exception is printed with a full traceback instead of being swallowed.

Uses the shared-session model: launches the debug Chrome on port 9223, then
attaches Athena to it (same as start_bots.py, just for one bot).
"""
from threading import Event
from start_bots import launch_chrome
from athena_files.athena_bot import start_athena


def main():
    username = input('SOM username (first_name.last_name): ').strip()
    passcode = input('RSA passcode: ').strip()
    launch_chrome()
    login_complete = Event()
    # Bypass @error_handle so tracebacks surface instead of being logged+swallowed.
    target = getattr(start_athena, "__wrapped__", start_athena)
    target(username, passcode, login_complete, False)


if __name__ == '__main__':
    main()
