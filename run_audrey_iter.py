"""
Iterate-friendly Audrey runner.

Connects to the Chrome already running on debug port 9223 (launched separately so
it stays warm across code-fix restarts) and runs ONLY Audrey with the raw
(un-decorated) start_audrey so unhandled exceptions print a full traceback to the
console instead of being swallowed by error_handle.

Credentials + session reuse come from env vars so the run can be relaunched after
a code fix without re-typing (and, on a warm session, without a fresh passcode):
    AUDREY_USER        SOM username (first_name.last_name)
    AUDREY_PASS        RSA passcode (only needed for a cold login)
    AUDREY_LOGGED_IN   "1" to reuse the warm NBS session (no re-login), else "0"
"""
import os
import sys
import traceback

from audrey_files.audrey_bot import start_audrey


def main():
    username = os.environ.get("AUDREY_USER", "").strip()
    passcode = os.environ.get("AUDREY_PASS", "").strip()
    is_logged_in = os.environ.get("AUDREY_LOGGED_IN", "0").strip() == "1"

    print(f"[run_audrey_iter] user={username!r} is_logged_in={is_logged_in}")

    # error_handle wraps start_audrey; __wrapped__ is the raw function.
    target = getattr(start_audrey, "__wrapped__", start_audrey)
    try:
        target(username, passcode, None, is_logged_in)
    except Exception:
        print("\n==================== UNHANDLED EXCEPTION ====================")
        traceback.print_exc()
        print("============================================================")
        sys.exit(1)


if __name__ == "__main__":
    main()
