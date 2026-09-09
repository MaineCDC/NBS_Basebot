# -*- coding: utf-8 -*-
"""
Created on Wed Mar 26 2025

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
from decorator import error_handle

def generator():
    while True:
        yield

is_in_production = os.getenv('ENVIRONMENT', 'production') != 'development'


@error_handle
def start_strep(username, password, login_complete=None, is_logged_in=False):

    from .strep import Strep

    load_dotenv()
    
    reviewed_ids = []
    what_do = []
    reason = []
    
    from bot_env import is_production, target_site_label
    print(f"[strep] target site: {target_site_label('strep')}")
    NBS = Strep(production=is_production('strep'))
    if is_in_production:
        print("Production Environment")
    else:
        print("Development Environment")
        
    NBS.set_credentials(username, password)
    NBS.log_in(is_logged_in)
    if login_complete is not None:
        login_complete.set()
    NBS.GoToApprovalQueue()
    #NBS.reviewed_ids = []
    patients_to_skip = set()
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
    
    with open("patients_to_skip.txt", "r") as patient_reader:
        patients_to_skip |= set(patient_reader.readlines())

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
        if loop.n and loop.n % save_every == 0 and reviewed_ids:
            NBS.safe_save_excel(
                pd.DataFrame({'Inv ID': reviewed_ids, 'Action': what_do, 'Reason': reason}),
                f"saved/strep/Strep_bot_activity_{datetime.now().date().strftime('%m_%d_%Y')}.xlsx",
            )
        try:
            #Sort review queue so that only strep investigations are listed
            paths = {
                "clear_filter_path":'//*[@id="removeFilters"]/a/font',
                "description_path":'/html/body/div[2]/form/div/table[2]/tbody/tr/td/table/thead/tr/th[8]/img',
                "clear_checkbox_path":'/html/body/div[2]/form/div/table[2]/tbody/tr/td/table/thead/tr/th[8]/div/label[2]/input',
                "click_ok_path":'/html/body/div[2]/form/div/table[2]/tbody/tr/td/table/thead/tr/th[8]/div/label[1]/input[1]',
                "click_cancel_path":'/html/body/div[2]/form/div/table[2]/tbody/tr/td/table/thead/tr/th[8]/div/label[1]/input[2]',
                "tests":["STREPTOCOCCUS PYOGENES","Group A Streptococcus, invasive"],
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
            # the same case before rejecting. Without this, initial_name stays
            # None, the case is never rejected, and the bot loops on it.
            NBS.initial_name = NBS.patient_name
            if NBS.condition == 'Group A Streptococcus, invasive':
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
                inv_id = NBS.find_element(By.XPATH,'//*[@id="bd"]/table[3]/tbody/tr[2]/td[1]/span[2]').text

                NBS.StandardChecks()
                # Track whether the case actually left the queue. If it did NOT,
                # advance past it; if it did, rows shifted up so rescan from row 1.
                actioned = False
                if not NBS.issues:
                    reviewed_ids.append(inv_id)
                    what_do.append("Approved Notification")
                    reason.append('No issues found.')
                    print("Approved Notification")
                    NBS.ReturnApprovalQueue()
                    NBS.ApproveNotification()
                    actioned = True
                    #NBS.SendStrepEmail("Hey, please don't change anything at all and just click CN", inv_id)
                
                if NBS.queue_loaded:
                    NBS.queue_loaded = None
                    continue
                if len(NBS.issues) > 0:
                    NBS.SortQueue(paths)
                    if NBS.queue_loaded:
                        NBS.queue_loaded = None
                        continue
                    # The queue reorders after a case is viewed; find the reviewed
                    # case's actual row by name and reject THAT row (instead of only
                    # acting when it's still on top, which left most cases unrejected).
                    reject_row = NBS.FindCaseRowByName(NBS.initial_name)
                    if reject_row:
                        reviewed_ids.append(inv_id)
                        what_do.append("Reject Notification")
                        reason.append(' '.join(NBS.issues))
                        NBS.RejectNotification(reject_row)
                        actioned = True
                        print(f"[strep] rejected inv_id={inv_id} ({NBS.initial_name!r}) at row {reject_row}")
                        body = ''
                        if  all(case in NBS.issues  for case in ['City is blank.', 'County is blank.', 'Zip code is blank.']):
                            body = 'Hey, please only update City, Zip Code and County, then Click CN'
                        elif NBS.CorrectCaseStatus:
                            body = f'Hey, please only update the case status to {NBS.CorrectCaseStatus}, then click CN for this case.'
                        if body:
                            print('mail', body)
                            NBS.SendStrepEmail(body, inv_id)
                    else:
                        print(f"[strep] reviewed case {NBS.initial_name!r} not found in queue after re-sort; skipping.")
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
                    print(f"[strep] reached row {n} with no further cases; "
                          f"{len(skipped_names)} skipped this pass. Ending pass.")
                    NBS.SendManualReviewEmail()
                    break
                if attempt_counter < NBS.num_attempts:
                    attempt_counter += 1
                else:
                    attempt_counter = 0
                    print("No Group A strep cases in notification queue.")
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
                print(f"[strep] queue recovery after exception failed: {recover_err}")
            # Stop spinning once the queue is empty/unstable (stale reads land here).
            if consecutive_errors >= max_consecutive_errors:
                print("Queue appears empty/unstable after consecutive errors; ending run.")
                break
        #     # print(tb)
        #     with open("error_log.txt", "a") as log:
        #         log.write(f"{datetime.now().date().strftime('%m_%d_%Y')} | Group A Strep - {str(tb)}")
        #     #NBS.send_smtp_email(NBS.covid_informatics_list, 'ERROR REPORT: NBSbot(Group A Strep Notification Review) AKA Athena', tb, 'error email')
            
    NBS.iGAS_notification_bot = True
    NBS.SendBotRunEmail()
    #NBS.CreateExcelSheet()
    
    print("ending, printing, saving")
    bot_act = pd.DataFrame(
        {'Inv ID': reviewed_ids,
        'Action': what_do,
        'Reason': reason
        })
    NBS.safe_save_excel(bot_act, f"saved/strep/Strep_bot_activity_{datetime.now().date().strftime('%m_%d_%Y')}.xlsx")
    print("Excel sheet created")

    '''completion_message = (
    f"Group A Strep case closing bot has finished running on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}. "
    f"Total labs reviewed: {len(reviewed_ids)}."
)
    NBS.send_smtp_email("disease.reporting@maine.gov", "Group A Strep Case Closing Bot Completed", completion_message, "Daily Bot Run Notification")'''



    # body = "The list of Group A Strep notifications that need to be manually reviewed are in the attached spreadsheet."
    
    # message = EmailMessage()
    # message.set_content(body)
    # message['Subject'] = 'Notification Review Report: NBSbot(Group A Strep Notification Review) AKA Group A Strep'
    # message['From'] = NBS.nbsbot_email
    # message['To'] = ', '.join(["disease.reporting@maine.gov"])
    # with open(f"Strep_bot_activity_1{datetime.now().date().strftime('%m_%d_%Y')}.xlsx", "rb") as f:
    #     message.add_attachment(
    #         f.read(),
    #         filename=f"Anaplasma_bot_activity_{datetime.now().date().strftime('%m_%d_%Y')}.xlsx",
    #         maintype="application",
    #         subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    #     )
    # smtpObj = smtplib.SMTP(NBS.smtp_server)
    # smtpObj.send_message(message)
    
    with open("patients_to_skip.txt", "w") as patient_writer:
        patient_writer.write("\n".join(patients_to_skip) + "\n")
    
    if error: 
        raise Exception(error_list)

if __name__ == '__main__':
    print("Run bots via start_bots.py (shared Chrome session); direct execution is no longer supported.")
