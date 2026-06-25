from threading import Event
from datetime import datetime
import time, os
# Import every bot's entry point. All of these now share the unified
# (username, passcode, login_complete, is_logged_in) shared-session contract.
from anaplasma_files.anaplasma_bot import start_anaplasma
from audrey_files.audrey_bot import start_audrey
from athena_files.athena_bot import start_athena
from giardia_files.giardia_bot import start_giardia
from strep_files.strep_bot import start_strep
from babesia_files.babesia_bot import start_babesia
from CovidECR_files.CovidEcr_bot import start_CovidEcr
from HepBnotificationreview_files.HepBnotificationreview_bot import start_HepBnotificationreview
from Gonorrhea_files.Gonorrhea_bot import start_Gonorrhea
from ILIOutbreak_files.ILIOutbreak_bot import start_ILIOutbreak
import subprocess
import socket
import atexit
import shutil
from selenium import webdriver
from selenium.webdriver.chrome.options import Options


CHROME_PORT = 9223
USER_DATA_DIR = os.getcwd() + r"\chrome-bot-profile"


def kill_bot_profile_chrome():
    """Terminate only Chrome processes using the bot profile dir.

    A prior run that crashed, was Ctrl-C'd, or got interrupted by sleep can leave
    a Chrome bound to USER_DATA_DIR alive. The next launch then forwards its args
    to that survivor and exits without ever opening the remote-debugging port,
    producing "Chrome didn't open port ...". We match on the profile path in the
    command line so the user's normal Chrome (a different --user-data-dir) is
    never touched.
    """
    profile_token = os.path.basename(USER_DATA_DIR)  # "chrome-bot-profile"
    ps_command = (
        "Get-CimInstance Win32_Process -Filter \"name='chrome.exe'\" | "
        "Where-Object { $_.CommandLine -like '*" + profile_token + "*' } | "
        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
    )
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_command],
            timeout=30,
        )
    except Exception as e:
        print(f"kill_bot_profile_chrome: cleanup failed (continuing): {e}")


def clear_profile_locks():
    """Remove stale singleton/lock files that can block a fresh Chrome launch."""
    for name in ("SingletonLock", "SingletonCookie", "SingletonSocket", "lockfile"):
        path = os.path.join(USER_DATA_DIR, name)
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError as e:
            print(f"clear_profile_locks: could not remove {name} (continuing): {e}")


def find_chrome_binary():
    """Locate Chrome on the system. Adjust paths for your OS."""
    candidates = [
        "google-chrome",
        "google-chrome-stable",
        "chromium",
        "chromium-browser",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",        # Windows
    ]
    for c in candidates:
        path = shutil.which(c) if "/" not in c and "\\" not in c else c
        if path:
            return path
    raise RuntimeError("Chrome not found")


def wait_for_port(port, host="127.0.0.1", timeout=30):
    """Block until Chrome's debug port is accepting connections."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except (ConnectionRefusedError, OSError):
            time.sleep(0.2)
    raise TimeoutError(f"Chrome didn't open port {port} in {timeout}s")


def launch_chrome():
    """Start Chrome with remote debugging enabled.

    Retries to survive a stale bot-profile Chrome left over from a prior run: if
    the debug port never opens (because a survivor stole our args and we exited),
    kill those leftovers, clear stale locks, and relaunch.
    """
    chrome = find_chrome_binary()
    print(f"Launching: {chrome}")
    if not os.path.exists(USER_DATA_DIR):
        os.makedirs(USER_DATA_DIR)

    # Reap the whole bot-profile Chrome tree on exit, not just our Popen handle.
    atexit.register(kill_bot_profile_chrome)

    max_attempts = 2
    for attempt in range(1, max_attempts + 1):
        # Start from a clean profile so the new process actually owns it (and so
        # it doesn't forward its args to a survivor and exit without a port).
        kill_bot_profile_chrome()
        clear_profile_locks()

        process = subprocess.Popen(
            [
                chrome,
                f"--remote-debugging-port={CHROME_PORT}",
                f"--user-data-dir={USER_DATA_DIR}",
                "--no-first-run",
                "--no-default-browser-check",
            ],
        )
        try:
            wait_for_port(CHROME_PORT)
            return process
        except TimeoutError as e:
            print(f"launch_chrome: attempt {attempt}/{max_attempts} failed: {e}")
            if attempt == max_attempts:
                raise


# Bot menu. The number -> function mapping; the user's selection ORDER is
# preserved (see selection()), and the round-robin runs the bots in that order
# every cycle.
bots = {
    1: start_athena,
    2: start_audrey,
    3: start_anaplasma,
    4: start_giardia,
    5: start_strep,
    6: start_babesia,
    7: start_CovidEcr,
    8: start_HepBnotificationreview,
    9: start_Gonorrhea,
    10: start_ILIOutbreak,
}
targets = []


def selection():
    select = input("Enter selections as space-separated numbers..: ")
    selected = list(map(int, select.split()))

    for option in selected:
        if option in bots:
            # Preserve the order the user typed -- the round-robin cycles bots
            # in exactly this order each pass.
            targets.append(bots[option])
        else:
            print(f"Invalid selection {option}")
            targets.clear()
            selection()
            return


def run_bots():
    print("**select bots** (selection order is the round-robin order)")
    print("1. athena")
    print("2. audrey")
    print("3. anaplasma")
    print("4. giardiasis")
    print("5. strep")
    print("6. babesia")
    print("7. CovidEcr")
    print("8. HepBnotificationreview")
    print("9. Gonorrhea")
    print("10. ILIOutbreak")
    selection()

    login_complete = Event()
    chrome_process = None
    try:
        for target in targets:
            print(f"selected: {target.__name__.replace('start_', '')}")

        # One Chrome session can only be on ONE site. bot_env decides each bot's
        # site (default production; bots in TEST_LOCKED_BOTS always test;
        # ENVIRONMENT=development forces everything to test). Drop any selected
        # bot whose site doesn't match this session rather than letting a prod
        # bot and a test bot fight over the single shared browser.
        from bot_env import is_production, session_is_production
        session_prod = session_is_production()
        compatible, dropped = [], []
        for t in targets:
            name = t.__name__.replace('start_', '')
            (compatible if is_production(name) == session_prod else dropped).append((t, name))
        if dropped:
            sess = "PRODUCTION" if session_prod else "TEST"
            print(
                f"\n*** This is a {sess} session. Skipping these bots whose site "
                f"does not match: {[n for _, n in dropped]}.\n"
                f"    They are locked to the other site -- run them separately "
                f"(set ENVIRONMENT in .env accordingly). ***\n"
            )
        targets[:] = [t for t, _ in compatible]
        if not targets:
            print("No selected bots are compatible with this session. Nothing to run.")
            return

        username = input('Enter your SOM username ("first_name.last_name"):')
        passcode = input('Enter your RSA passcode:')
        chrome_process = launch_chrome()

        # SINGLE ROUND-ROBIN PASS: run the selected bots once, in the user's
        # order. The FIRST bot performs the single login (is_logged_in=False);
        # every other run reuses the warm shared session (is_logged_in=True).
        # Each bot ends its own pass when its queue is empty, then the next bot
        # runs. After the last bot finishes we STOP -- the bots no longer loop
        # back to re-check the queues (that auto-rerun spammed a "bot run" email
        # every cycle even when there were no new cases). Re-run start_bots.py
        # whenever you want another pass.
        # The @error_handle decorator on each start_* already logs per-bot
        # exceptions, and we also guard here so one bad bot never stops the pass.
        # Stop cleanly any time with Ctrl-C.
        print("\n================= STARTING SINGLE PASS =================")
        for i, target in enumerate(targets):
            is_logged_in = i != 0
            name = target.__name__.replace('start_', '')
            print(f"starting bot {i + 1}/{len(targets)}: {name} "
                  f"({'reusing session' if is_logged_in else 'logging in'})")
            try:
                target(username, passcode, login_complete, is_logged_in)
            except Exception as e:
                # @error_handle already wrote the traceback to error_logs.txt;
                # keep going so a single failing bot can't halt the others.
                print(f"{name} raised an error; continuing: {e}")
            print(f"finished bot {name}; moving to the next bot...")

        print("================= PASS COMPLETE ================="
              "\nAll selected bots have run once. Stopping (no auto-rerun). "
              "Run start_bots.py again for another pass.")

    except KeyboardInterrupt:
        print("\nStop requested (Ctrl-C). Shutting the bots down cleanly...")
    except Exception as e:
        with open("error_log.txt", "a") as log:
            log.write(f"{datetime.now().date().strftime('%m_%d_%Y')} - {str(e)}\n")
    finally:
        # Reap the bot-profile Chrome so the next run starts clean.
        kill_bot_profile_chrome()


if __name__ == '__main__':
    print("waking bots...")
    run_bots()
    print("putting bots to sleep...")
