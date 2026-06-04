"""
Standalone runner for the Athena (COVID notification review) bot only.
Runs ONLY Athena and bypasses the error_handle decorator so any unhandled
exception is printed with a full traceback instead of being swallowed.
"""
from athena_files.athena_bot_prod import start_athena


def main():
    username = input('SOM username (first_name.last_name): ').strip()
    passcode = input('RSA passcode: ').strip()
    target = getattr(start_athena, "__wrapped__", start_athena)
    target(username, passcode)


if __name__ == '__main__':
    main()
