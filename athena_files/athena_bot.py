from tqdm import tqdm
import time
import traceback
from threading import Event
from custom_decorator import  error_handle
import os

def generator():
    while True:
        yield
is_in_production = os.getenv('ENVIRONMENT', 'production') != 'development'
@error_handle
def start_athena(username, passcode, login_complete: Event = None, is_logged_in=False):
    from .athena import Athena

    from bot_env import is_production, target_site_label
    print(f"[athena] target site: {target_site_label('athena')}")
    NBS = Athena(production=is_production('athena'))
    NBS.set_credentials(username, passcode)
    NBS.log_in(is_logged_in)
    if login_complete is not None:
        login_complete.set()
    NBS.GoToApprovalQueue()

    attempt_counter = 0

    for _ in tqdm(generator()):
        # try:
        NBS.SortApprovalQueue()

        if NBS.queue_loaded:
            NBS.queue_loaded = None
            continue
        elif NBS.queue_loaded == False:
            # Queue failed to load. End this pass; the round-robin orchestrator
            # will re-run athena on the next cycle. (Previously this chained into
            # strep and Sleep()'d forever -- the shared-session loop runs strep as
            # its own entry, so athena just returns when it has no work.)
            NBS.queue_loaded = None
            NBS.SendManualReviewEmail()
            return
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
                # No COVID-19 cases left in the queue: this bot's pass is done.
                # Return so the round-robin moves on to the next bot.
                attempt_counter = 0
                print("No COVID-19 cases in notification queue.")
                NBS.SendManualReviewEmail()
                return
        # except:
        #     tb = traceback.format_exc()
        #     print(tb)
        #     NBS.send_smtp_email(NBS.covid_informatics_list, 'ERROR REPORT: NBSbot(COVID Notification Review) AKA Athena', tb, 'error email')
        #     break
