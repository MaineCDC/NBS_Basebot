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
    # Names of cases reviewed this pass that could NOT be actioned. Tracked so the
    # bot steps past them instead of re-reading the same un-actionable case at the
    # top forever (one stuck case otherwise walls off the cases behind it).
    skipped_names = set()
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
            NBS.save_and_print_results("ILIOutbreak",
                {'Inv ID': NBS.reviewed_ids, 'Action': what_do, 'Reason': reason}, "final")
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
            NBS.CheckFirstCase(n)
            # Record the case at row n so the reject path can confirm it's still
            # the same case before rejecting (previously the reject acted on row 1
            # unconditionally, which could reject the WRONG case after the queue
            # reordered).
            NBS.initial_name = NBS.patient_name
            if NBS.condition == 'ILI Related Outbreak':
                consecutive_errors = 0  # a real case was found

                # Step over any case we already reviewed but could not action this
                # pass, so it can't block the cases behind it.
                if NBS.initial_name and NBS.initial_name in skipped_names:
                    n += 1
                    continue

                NBS.GoToNCaseInApprovalQueue(n)
                if NBS.queue_loaded:
                    NBS.queue_loaded = None
                    continue
                inv_id = NBS.ReadText('//*[@id="bd"]/table[3]/tbody/tr[2]/td[1]/span[2]')
                NBS.StandardChecks()
                # Track whether the case actually left the queue. If it did NOT,
                # advance past it; if it did, rows shifted up so rescan from row 1.
                actioned = False
                if not NBS.issues:
                    NBS.reviewed_ids.append(inv_id)
                    what_do.append("Approved Notification")
                    reason.append('No issues found.')
                    print("Approved Notification")
                    NBS.ApproveNotification()
                    actioned = True
                NBS.ReturnApprovalQueue()
                if NBS.queue_loaded:
                    NBS.queue_loaded = None
                    continue
                if len(NBS.issues) > 0:
                    NBS.SortQueue(paths)
                    if NBS.queue_loaded:
                        NBS.queue_loaded = None
                        continue
                    # The queue reorders after a case is viewed; find the reviewed
                    # case's actual row by name and reject THAT row instead of
                    # blindly rejecting row 1 (which could reject a different case).
                    reject_row = NBS.FindCaseRowByName(NBS.initial_name)
                    if reject_row:
                        NBS.reviewed_ids.append(inv_id)
                        what_do.append("Reject Notification")
                        reason.append(' '.join(NBS.issues))
                        NBS.RejectNotification(reject_row)
                        actioned = True
                        '''body = ''
                        if  all(case in NBS.issues  for case in ['City is blank.', 'County is blank.', 'Zip code is blank.']):
                            body = 'Hey, please only update City, Zip Code and County, then Click CN'
                        elif NBS.CorrectCaseStatus:
                            body = f'Hey, please only update the case status to {NBS.CorrectCaseStatus}, then click CN for this case.'
                        if body:
                            print('mail', body)
                            NBS.SendILIOutbreakEmail(NBS,body,inv_id)'''
                    else:
                        print(f"[ILIOutbreak] reviewed case {NBS.initial_name!r} not found in queue after re-sort; skipping.")
                        NBS.num_fail += 1

                if actioned:
                    # Case left the queue; rows shifted up, so rescan from the top.
                    n = 1
                else:
                    # Could not action this case; remember it and move past it.
                    if NBS.initial_name:
                        skipped_names.add(NBS.initial_name)
                    n += 1
            else:
                # No matching case at row n. If we've walked past row 1, the only
                # cases left are ones already skipped this pass, so the pass is
                # done. If still at row 1, the queue is genuinely empty.
                if n > 1:
                    print(f"[ILIOutbreak] reached row {n} with no further cases; "
                          f"{len(skipped_names)} skipped this pass. Ending pass.")
                    NBS.SendManualReviewEmail()
                    break
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
            consecutive_errors += 1
            # A case that raises MID-REVIEW is a "poison" case: it was never
            # actioned, so it stays in the queue. Record it, advance past it, and
            # reset to a clean approval queue so one bad case can't end the pass
            # and block every case behind it.
            if NBS.initial_name:
                skipped_names.add(NBS.initial_name)
            n += 1
            try:
                NBS.GoToApprovalQueue()
            except Exception as recover_err:
                print(f"[ILIOutbreak] queue recovery after exception failed: {recover_err}")
            # Stop spinning once the queue is empty/unstable (stale reads land here).
            if consecutive_errors >= max_consecutive_errors:
                print("Queue appears empty/unstable after consecutive errors; ending run.")
                break
        
    NBS.ILIOutbreak_notification_bot = True
    NBS.SendEmailToIliAssign()
    NBS.SendBotRunEmail() 
    #NBS.CreateExcelSheet()
    
    print("ending, printing, saving")
    NBS.save_and_print_results("ILIOutbreak",
        {'Inv ID': NBS.reviewed_ids,
        'Action': what_do,
        'Reason': reason
        }, "final")
    print("Excel file created")

if __name__ == '__main__':
    print("Run bots via start_bots.py (shared Chrome session); direct execution is no longer supported.")
