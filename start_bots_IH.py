from threading import Thread
from datetime import datetime
import time
# import the three bots into this file
from anaplasma_files.anaplasma_bot import start_anaplasma
from audrey_files.audrey_bot import start_audrey
#from athena_files.athena_bot_prod import start_athena
from strep_files.strep_bot import start_strep
#from strep_files.strep_bot_prod import start_strep
from CovidECR_files.CovidEcr_bot import start_CovidEcr
from HepBnotificationreview_files.HepBnotificationreview_bot import start_HepBnotificationreview
from Gonorrhea_files.Gonorrhea_bot import start_Gonorrhea
from ILIOutbreak_files.ILIOutbreak_bot import start_ILIOutbreak
# run the get credentials function
bots = {
    #1: start_athena,
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
    global targets
    targets.clear()
    
    while True:
        try:
            select = input("Enter selections as space-separated numbers (e.g., 1 2 3): ")
            if not select.strip():
                print("Please enter at least one selection.")
                continue
                
            selected = list(map(int, select.split()))
            valid = True
            
            for option in selected:
                if option in bots:
                    targets.append(bots[option])
                else:
                    print(f"Invalid selection {option}. Valid options are 1-8.")
                    valid = False
                    break
            
            if valid and targets:
                break
            else:
                targets.clear()
                
        except ValueError:
            print("Please enter valid numbers separated by spaces.")
            continue

def run_bots():
    threads = []
    print("\n**Select Bots**")
    print("1. athena")
    print("2. audrey")
    print("3. anaplasma")
    print("4. strep")
    print("5. CovidEcr")
    print("6. HepBnotificationreview")
    print("7. Gonorrhea")
    print("8. ILIOutbreak")
    print()
    
    selection()
    
    if not targets:
        print("No valid bots selected.")
        return
    
    try:
        print("\n**Starting bots:**")
        for target in targets:
            bot_name = target.__name__.replace('start_', '')
            print(f"  - {bot_name}")
        print()
        
        # Run each bot in a separate thread (no credentials needed)
        for target in targets:
            try:
                thread = Thread(target=target, daemon=False)
                threads.append(thread)
                thread.start()
                time.sleep(30)
            except Exception as e:
                error_msg = f"{datetime.now().strftime('%m_%d_%Y %H:%M:%S')} - Error starting {target.__name__}: {str(e)}\n"
                print(error_msg)
                with open("error_log.txt", "a") as log:
                    log.write(error_msg)
        
        # Wait for all threads to complete
        print("\nWaiting for bots to complete...")
        for thread in threads:
            thread.join()
        
        print("All bots completed.")

    except Exception as e:
        import traceback
        error_msg = f"{datetime.now().strftime('%m_%d_%Y %H:%M:%S')} - {str(e)}\n{traceback.format_exc()}\n"
        print(error_msg)
        with open("error_log.txt", "a") as log:
            log.write(error_msg)


if __name__ == '__main__':
    print("waking bots...")
    run_bots()
    print("putting bots to sleep...")