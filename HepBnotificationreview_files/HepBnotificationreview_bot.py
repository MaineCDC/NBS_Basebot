# -*- coding: utf-8 -*-
"""
Created on Apr 16 10:35:46 2025
@author: Vaishnavi.Appidi
"""
from tqdm import tqdm
import time
import traceback
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import ElementNotInteractableException
from selenium.common.exceptions import StaleElementReferenceException
from selenium.common.exceptions import TimeoutException
import pandas as pd
from datetime import datetime
import smtplib, ssl
from email.message import EmailMessage
from dotenv import load_dotenv
import os
from custom_decorator import error_handle

def generator():
    while True:
        yield

reviewed_ids = []
what_do = []
reason = []

is_in_production = os.getenv('ENVIRONMENT', 'production') != 'development'

@error_handle
def start_HepBnotificationreview(username, passcode, login_complete=None, is_logged_in=False):

    from .HepBnotificationreview import HepBNotificationReview

    load_dotenv()

    from bot_env import is_production, target_site_label
    print(f"[HepBnotificationreview] target site: {target_site_label('HepBnotificationreview')}")
    NBS = HepBNotificationReview(production=is_production('HepBnotificationreview'))

    NBS.set_credentials(username, passcode)
    NBS.log_in(is_logged_in)
    if login_complete is not None:
        login_complete.set()
    NBS.GoToApprovalQueue()

    patients_to_skip = []
    error_list = []
    error = False
    n = 1
    attempt_counter = 0
    # Break the run after this many CONSECUTIVE errored iterations with no case
    # actioned -- prevents spinning on an emptied queue (stale-element reads).
    consecutive_errors = 0
    max_consecutive_errors = 5
    '''with open("patients_to_skip.txt", "r") as patient_reader:
        patients_to_skip.append(patient_reader.readlines())'''

    save_every = int(os.getenv("SAVE_EVERY_CASES", "10"))
    # Whole queue per pass: the real stop is the "no cases" break below; this cap
    # is a high backstop against a stuck case (override with MAX_CASES_PER_PASS).
    limit = int(os.getenv("MAX_CASES_PER_PASS", "500"))
    loop = tqdm(generator())
    for _ in loop:
        #check if the bot has gone through the set limit of reviews
        if loop.n >= limit:
            break

        # Incremental save: snapshot every save_every iterations so a hard kill
        # loses at most that batch, not the whole pass.
        if loop.n and loop.n % save_every == 0 and NBS.reviewed_ids:
            NBS.safe_save_excel(
                pd.DataFrame({'Inv ID': NBS.reviewed_ids, 'Action': NBS.what_do, 'Reason': NBS.reason}),
                f"saved/HepB/HepB_bot_activity_{datetime.now().date().strftime('%m_%d_%Y')}.xlsx",
            )
        try:
            #Sort review queue so that only Hepatitis B investigations are listed
            paths = {
                "clear_filter_path":'//*[@id="removeFilters"]/a/font',
                "description_path":'/html/body/div[2]/form/div/table[2]/tbody/tr/td/table/thead/tr/th[8]/img',
                "clear_checkbox_path":'/html/body/div[2]/form/div/table[2]/tbody/tr/td/table/thead/tr/th[8]/div/label[2]/input',
                "click_ok_path":'/html/body/div[2]/form/div/table[2]/tbody/tr/td/table/thead/tr/th[8]/div/label[1]/input[1]',
                "click_cancel_path":'/html/body/div[2]/form/div/table[2]/tbody/tr/td/table/thead/tr/th[8]/div/label[1]/input[2]',
                "tests":["Hepatitis B", "HEPATITIS B", "HBV"],
                "submit_date_path":'/html/body/div[2]/form/div/table[2]/tbody/tr/td/table/thead/tr/th[3]/a'
            }
            
            NBS.SortQueue(paths)

            if NBS.queue_loaded:
                NBS.queue_loaded = None
                continue
            elif NBS.queue_loaded == False:
                NBS.queue_loaded = None
                #NBS.SendManualReviewEmail()
                #NBS.Sleep()
                continue
            
            NBS.CheckFirstCase()
            # Remember the case currently at the top of the queue. The reject
            # path below re-sorts, re-reads the top case, and only rejects if it
            # is still the SAME case (final_name == initial_name). Without this,
            # initial_name stays None, the comparison is always False, the case
            # is never rejected, stays at the top, and the bot re-reviews the
            # same case forever.
            NBS.initial_name = NBS.patient_name
            # Guard against None (empty queue): CheckFirstCase sets condition=None
            # when there's no row, and None.lower() would crash into the except
            # handler and spin instead of reaching the no-case break below.
            if NBS.condition and 'hepatitis b' in NBS.condition.lower():
                consecutive_errors = 0  # a real HepB case was found
                NBS.GoToNCaseInApprovalQueue(n)
                if NBS.queue_loaded:
                    NBS.queue_loaded = None
                    continue
                inv_id = NBS.find_element(By.XPATH,'//*[@id="bd"]/table[3]/tbody/tr[2]/td[1]/span[2]').text
                print(f"[HepB] reviewing inv_id={inv_id} name={NBS.patient_name!r}")
                '''if any(inv_id in skipped_patients for skipped_patients in patients_to_skip):
                    print(f"present, {inv_id}")
                    NBS.ReturnApprovalQueue()
                    n = n + 1
                    continue'''

                NBS.StandardChecks()
                print(f"[HepB] inv_id={inv_id} issues={NBS.issues}")
                if not NBS.issues:
                    NBS.reviewed_ids.append(inv_id)
                    NBS.what_do.append("Approve Notification")
                    NBS.reason.append('No issues found.')
                    NBS.ApproveNotification()
                    print(f"Approved notification for {inv_id}")
                NBS.ReturnApprovalQueue()
                if NBS.queue_loaded:
                    NBS.queue_loaded = None
                    continue
                if len(NBS.issues) > 0:
                    NBS.SortQueue(paths)
                    if NBS.queue_loaded:
                        NBS.queue_loaded = None
                        continue
                    # The queue reorders after a case is viewed, so the reviewed
                    # case is usually no longer at row 1. Find its actual row by
                    # name and reject THAT row -- the old code only acted when the
                    # case happened to still be on top, so most cases were never
                    # cleared ("Case at top of queue changed").
                    reject_row = NBS.FindCaseRowByName(NBS.initial_name)
                    if reject_row:
                        NBS.reviewed_ids.append(inv_id)
                        NBS.what_do.append("Reject Notification")
                        NBS.reason.append(' '.join(NBS.issues))
                        NBS.RejectNotification(reject_row)
                        print(f"[HepB] rejected inv_id={inv_id} ({NBS.initial_name!r}) at row {reject_row}")
                        body = ''
                        if  all(case in NBS.issues  for case in ['City is blank.', 'County is blank.', 'Zip code is blank.']):
                            body = 'Hey, please only update City, Zip Code and County, then Click CN'
                        elif NBS.CorrectCaseStatus:
                            body = f'Hey, please only update the case status to {NBS.CorrectCaseStatus}, then click CN for this case.'
                        if body:
                            print('mail', body)
                            NBS.SendHepBnotificationreviewEmail(body, inv_id)
                    else:
                        print(f"[HepB] reviewed case {NBS.initial_name!r} not found in queue after re-sort; "
                              f"skipping (may have been actioned elsewhere).")
                        NBS.num_fail += 1
            else:
                if attempt_counter < NBS.num_attempts:
                    attempt_counter += 1
                else:
                    attempt_counter = 0
                    print("No Hep_B cases in notification queue.")
                    NBS.SendManualReviewEmail()
                    break
                    #NBS.Sleep()
        except Exception as e:
            # Print the per-case exception (was silently swallowed, which hid why
            # a case never got actioned and the bot re-read it forever).
            import traceback as _tb
            print(f"[HepB] EXCEPTION on case: {e}")
            print(_tb.format_exc())
            error_list.append(str(e))
            error = True
            # Once the queue is empty, SortQueue/CheckFirstCase keep throwing
            # (stale element / nothing to read) and that lands here every pass.
            # Without a bound the bot spins until the MAX_CASES_PER_PASS backstop.
            # Break after several CONSECUTIVE errors (reset whenever a real case is
            # found), so an emptied queue ends the run cleanly.
            consecutive_errors += 1
            if consecutive_errors >= max_consecutive_errors:
                print(f"[HepB] {consecutive_errors} consecutive errors with no case "
                      f"actioned; queue appears empty/unstable. Ending run.")
                break
        #     # print(tb)
        #     with open("error_log.txt", "a") as log:
        #         log.write(f"{datetime.now().date().strftime('%m_%d_%Y')} | HepB - {str(tb)}")
        #     #NBS.send_smtp_email(NBS.covid_informatics_list, 'ERROR REPORT: NBSbot(HepB Notification Review) AKA HepB', tb, 'error email')
            
    NBS.HepB_notification_bot = True
    NBS.SendBotRunEmail()
    #NBS.CreateExcelSheet()
    NBS.SendEmailToAssign()
    
    
    print("ending, printing, saving")
    bot_act = pd.DataFrame(
        {'Inv ID': NBS.reviewed_ids,
        'Action': NBS.what_do,
        'Reason': NBS.reason
        })
    NBS.safe_save_excel(bot_act, f"saved/HepB/HepB_bot_activity_{datetime.now().date().strftime('%m_%d_%Y')}.xlsx")
    print("excel sheet created")
    
if __name__ == '__main__':
    print("Run bots via start_bots.py (shared Chrome session); direct execution is no longer supported.")
