# -*- coding: utf-8 -*-
"""
Created on Mon September 22 2025
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
from custom_decorator import  error_handle

def generator():
    while True:
        yield

reviewed_ids = []
what_do = []
reason = []

is_in_production = os.getenv('ENVIRONMENT', 'production') != 'development'
@error_handle
def start_ILIOutbreak(username, passcode, login_complete=None, is_logged_in=False):

    load_dotenv()
    from .ILIOutbreak import ILIOutbreak
    from bot_env import is_production, target_site_label
    print(f"[ILIOutbreak] target site: {target_site_label('ILIOutbreak')}")
    NBS = ILIOutbreak(production=is_production('ILIOutbreak'))
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
    consecutive_errors = 0
    max_consecutive_errors = 5
    # what_do/reason are module-level; clear them so a fresh round-robin pass
    # doesn't re-save the previous pass's actions (NBS.reviewed_ids is per-run).
    what_do.clear(); reason.clear()
    save_every = int(os.getenv("SAVE_EVERY_CASES", "10"))
    # Whole queue per pass: the real stop is the "no cases" break below; this cap
    # is a high backstop against a stuck case (override with MAX_CASES_PER_PASS).
    limit = int(os.getenv("MAX_CASES_PER_PASS", "500"))
    loop = tqdm(generator())
    for _ in loop:
        #check if the bot haa gone through the set limit of reviews
        if loop.n >= limit:
            break

        # Incremental save: snapshot every save_every iterations so a hard kill
        # loses at most that batch, not the whole pass.
        if loop.n and loop.n % save_every == 0 and NBS.reviewed_ids:
            NBS.safe_save_excel(
                pd.DataFrame({'Inv ID': NBS.reviewed_ids, 'Action': what_do, 'Reason': reason}),
                f"saved/ILIOutbreak/ILIOutbreak_bot_activity_{datetime.now().date().strftime('%m_%d_%Y')}.xlsx",
            )
        try:
            #Sort review queue so that ILIOutbreak investigations are listed
            paths = {
                "clear_filter_path":'//*[@id="removeFilters"]/a/font',
                "description_path":'/html/body/div[2]/form/div/table[2]/tbody/tr/td/table/thead/tr/th[8]/img',
                "clear_checkbox_path":'/html/body/div[2]/form/div/table[2]/tbody/tr/td/table/thead/tr/th[8]/div/label[2]/input',
                "click_ok_path":'/html/body/div[2]/form/div/table[2]/tbody/tr/td/table/thead/tr/th[8]/div/label[1]/input[1]',
                "click_cancel_path":'/html/body/div[2]/form/div/table[2]/tbody/tr/td/table/thead/tr/th[8]/div/label[1]/input[2]',
                "tests":["ILI Related Outbreak"],
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
            if NBS.condition == 'ILI Related Outbreak':
                consecutive_errors = 0  # a real case was found
                NBS.GoToNCaseInApprovalQueue(n)
                if NBS.queue_loaded:
                    NBS.queue_loaded = None
                    continue
                inv_id = NBS.ReadText('//*[@id="bd"]/table[3]/tbody/tr[2]/td[1]/span[2]')
                NBS.StandardChecks()
                if not NBS.issues:
                    NBS.reviewed_ids.append(inv_id)
                    what_do.append("Approved Notification")
                    reason.append('No issues found.')
                    print("Approved Notification")
                    NBS.ApproveNotification()
                NBS.ReturnApprovalQueue()
                if NBS.queue_loaded:
                    NBS.queue_loaded = None
                    continue
                if len(NBS.issues) > 0:
                    NBS.SortQueue(paths)
                    if NBS.queue_loaded:
                        NBS.queue_loaded = None
                        continue
                    NBS.CheckFirstCase()

                    NBS.final_name = NBS.patient_name
                    #if NBS.final_name == NBS.initial_name:
                    NBS.reviewed_ids.append(inv_id)
                    what_do.append("Reject Notification")
                    reason.append(' '.join(NBS.issues))
                    NBS.RejectNotification()
                    '''body = ''
                    if  all(case in NBS.issues  for case in ['City is blank.', 'County is blank.', 'Zip code is blank.']):
                        body = 'Hey, please only update City, Zip Code and County, then Click CN'
                    elif NBS.CorrectCaseStatus:
                        body = f'Hey, please only update the case status to {NBS.CorrectCaseStatus}, then click CN for this case.'
                    if body:
                        print('mail', body)
                        NBS.SendILIOutbreakEmail(NBS,body,inv_id)'''
                        # NBS.ReturnApprovalQueue()
                    #elif NBS.final_name != NBS.initial_name:
                        #print(f"here : {NBS.final_name} {NBS.initial_name}")
                        #print('Case at top of queue changed. No action was taken on the reviewed case.')
                        #NBS.num_fail += 1
            else:
                if attempt_counter < NBS.num_attempts:
                    attempt_counter += 1
                else:
                    attempt_counter = 0
                    print("No ILI Related Outbreak cases in notification queue.")
                    NBS.SendManualReviewEmail()
                    #NBS.Sleep()
                    break
        except Exception as e:
            # raise Exception(e)
            error_list.append(str(e))
            error = True
            # Stop spinning once the queue is empty/unstable (stale reads land here).
            consecutive_errors += 1
            if consecutive_errors >= max_consecutive_errors:
                print("Queue appears empty/unstable after consecutive errors; ending run.")
                break
        
    NBS.ILIOutbreak_notification_bot = True
    NBS.SendEmailToIliAssign()
    NBS.SendBotRunEmail() 
    #NBS.CreateExcelSheet()
    
    print("ending, printing, saving")
    bot_act = pd.DataFrame(
        {'Inv ID': NBS.reviewed_ids,
        'Action': what_do,
        'Reason': reason
        })
    NBS.safe_save_excel(bot_act, f"saved/ILIOutbreak/ILIOutbreak_bot_activity_{datetime.now().date().strftime('%m_%d_%Y')}.xlsx")
    print("Excel file created")

if __name__ == '__main__':
    print("Run bots via start_bots.py (shared Chrome session); direct execution is no longer supported.")
