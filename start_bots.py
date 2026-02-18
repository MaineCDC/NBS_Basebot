from threading import Thread
from datetime import datetime
import time
# import the three bots into this file
from anaplasma_files.anaplasma_bot import start_anaplasma
from audrey_files.audrey_bot import start_audrey
from athena_files.athena_bot_prod import start_athena
from strep_files.strep_bot_prod import start_strep
from CovidECR_files.CovidEcr_bot import start_CovidEcr
from HepBnotificationreview_files.HepBnotificationreview_bot import start_HepBnotificationreview
from Gonorrhea_files.Gonorrhea_bot import start_Gonorrhea
from ILIOutbreak_files.ILIOutbreak_bot import start_ILIOutbreak
from bot_queue import BotQueue

bots = {
    1: start_athena,
    2: start_audrey,
    3: start_anaplasma,
    4: start_strep,
    5: start_CovidEcr,
    6: start_HepBnotificationreview,
    7: start_Gonorrhea,
    8: start_ILIOutbreak
    }
targets = []
def selection():
    select = input("Enter selections as space-separated numbers..: ")
    selected = map(int, select.split())

    for option in selected:
        if option in bots:
            targets.append(bots[option])
        else:
            print(f"Invalid selection {option}")
            targets.clear()
            selection()

def run_bots():
    # targets = []
    print("**select bots**")
    print("1. athena")
    print("2. audrey")
    print("3. anaplasma")
    print("4. strep")
    print("5. CovidEcr")
    print("6. HepBnotificationreview")
    print("7. Gonorrhea")
    print("8. ILIOutbreak")
    selection()
    try:
        for  target in targets:
            print(f"selected: {target.__name__.replace('start_', '') }")
        
        username = input('Enter your SOM username ("first_name.last_name"):')
        passcode = input('Enter your RSA passcode:')
        
        # Create a BotQueue instance with the selected bots
        bot_queue = BotQueue(targets)
        
        # Run bots continuously in a cycle
        # After all selected bots run once, sleep and then reset to first bot
        while True:
            for i in range(len(targets)):
                bot_func = bot_queue.get_current_bot()
                print(f"\nStarting {bot_func.__name__.replace('start_', '')}...")
                bot_func(username, passcode, driver_instance=None)
                print(f"{bot_func.__name__.replace('start_', '')} completed.\n")
                bot_queue.get_next_bot()
            
            # After all bots have run once, reset to the first bot
            print("All bots completed. Resetting to first bot...")
            bot_queue.reset_to_first()

    except Exception as e:
        with open("error_log.txt", "a") as log:
            log.write(f"{datetime.now().date().strftime('%m_%d_%Y')} - {str(e)}\n")


if __name__ == '__main__':
    print("waking bots...")
    run_bots()
    print("putting bots to sleep...")
