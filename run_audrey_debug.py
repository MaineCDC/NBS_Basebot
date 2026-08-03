"""
Standalone runner for the Audrey (Hepatitis ELR review) bot only.

Differences from start_bots.py:
  * Runs ONLY Audrey (no threads, no other bots).
  * Bypasses the error_handle decorator so any unhandled exception is printed
    to the console with a full traceback instead of being silently written to
    Error_logs.txt and stopping the whole run.

Run this in a terminal and type the SOM username + RSA passcode when prompted.
"""
import sys
from threading import Event
from start_bots import launch_chrome
from audrey_files.audrey_bot import start_audrey


def main():
    username = input('SOM username (first_name.last_name): ').strip()
    passcode = input('RSA passcode: ').strip()
    launch_chrome()
    login_complete = Event()

    # error_handle wraps start_audrey; __wrapped__ is the raw function.
    target = getattr(start_audrey, "__wrapped__", start_audrey)
    target(username, passcode, login_complete, False)


if __name__ == '__main__':
    main()
