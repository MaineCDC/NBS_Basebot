"""
Temporary workaround for multi-bot execution.
Run individual bots with these scripts instead of using start_bots.py
"""

import subprocess
import time

def run_multiple_bots():
    """Run multiple bots sequentially (not parallel, but all cases processed)."""
    username = input('Enter your SOM username ("first_name.last_name"): ').strip()
    password = input('Enter your RSA password: ').strip()
    
    bots = [
        ("anaplasma", "run_anaplasma_debug.py"),
        ("giardia", "run_giardia_debug.py"),
        ("HepBnotificationreview", "run_hepbnotificationreview_debug.py"),
    ]
    
    print("\n" + "="*60)
    print("Running bots sequentially...")
    print("="*60 + "\n")
    
    for bot_name, script in bots:
        print(f"\n>>> Starting {bot_name}...")
        # Note: Can't easily pass credentials to subprocess
        # User will need to enter them for each bot
        # subprocess.run([f"python {script}"], shell=True)
        print(f"Run: python {script}")
        print(f"Enter credentials when prompted\n")

if __name__ == '__main__':
    print("""
    MULTI-BOT WORKAROUND
    ===================
    
    Since multi-bot through start_bots.py has architecture issues,
    run the bots individually in this order:
    
    1. python run_anaplasma_debug.py
    2. python run_giardia_debug.py  
    3. python run_hepbnotificationreview_debug.py
    
    Each will process all cases in its queue.
    """)
