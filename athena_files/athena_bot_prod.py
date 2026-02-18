
from tqdm import tqdm
import time
import traceback
from decorator import error_handle
import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service

chrome_driver_path ="C:/Users/vaishnavi.appidi/OneDrive - State of Maine/Desktop/chromedriver-win32/chromedriver.exe"
service = Service(chrome_driver_path)
driver = webdriver.Chrome(service=service)

def generator():
    while True:
        yield

is_in_production = os.getenv('ENVIRONMENT', 'production') != 'development'
@error_handle
def start_athena(username, passcode, driver_instance=None):
    from .athena_prod import Athena

    if driver_instance:
        nbs_driver = driver_instance
    else:
        nbs_driver = driver

    NBS = Athena(driver=nbs_driver, production=is_in_production)
    NBS.set_credentials(username, passcode)
    NBS.log_in()
    NBS.GoToApprovalQueue()

    attempt_counter = 0

    for _ in tqdm(generator()):
        NBS.SortApprovalQueueAthena()

        if NBS.queue_loaded:
            NBS.queue_loaded = None
            continue
        elif NBS.queue_loaded == False:
            NBS.queue_loaded = None
            NBS.SendManualReviewEmail()
            NBS.Sleep()
            break

        NBS.CheckFirstCase()
        NBS.initial_name = NBS.patient_name
        if NBS.condition == '2019 Novel Coronavirus (2019-nCoV)':
            NBS.GoToFirstCaseInApprovalQueue()
            if NBS.queue_loaded:
                NBS.queue_loaded = None
                continue
            NBS.StandardChecks()
            if not NBS.investigator:
                NBS.TriageReview()
            elif NBS.investigator_name in NBS.outbreak_investigators:
                NBS.OutbreakInvestigatorReview()
            else:
                NBS.CaseInvestigatorReview()

            if not NBS.issues:
                NBS.ApproveNotification()
            NBS.ReturnApprovalQueue()
            if NBS.queue_loaded:
                NBS.queue_loaded = None
                continue
            if len(NBS.issues) > 0:
                NBS.SortApprovalQueue()
                if NBS.queue_loaded:
                    NBS.queue_loaded = None
                    continue
                NBS.CheckFirstCase()
                NBS.final_name = NBS.patient_name
                if NBS.final_name == NBS.initial_name:
                    NBS.RejectNotification()
                elif NBS.final_name != NBS.initial_name:
                    print('Case at top of queue changed. No action was taken on the reviewed case.')
                    NBS.num_fail += 1
        else:
            if attempt_counter < NBS.num_attempts:
                attempt_counter += 1
            else:
                attempt_counter = 0
                print("No COVID-19 cases in notification queue.")
                NBS.Sleep()
                break
        # except:
        #     tb = traceback.format_exc()
        #     print(tb)
        #     NBS.send_smtp_email(NBS.covid_informatics_list, 'ERROR REPORT: NBSbot(COVID Notification Review) AKA Athena', tb, 'error email')
        #     break