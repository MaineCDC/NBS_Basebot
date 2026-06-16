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

    # DRY_RUN walks the real queue and logs what it WOULD do, but performs NO
    # production mutations: no ApproveNotification, no RejectNotification, and no
    # epidemiologist/assignment/run emails. Enable with DRY_RUN=1 (or true/yes).
    # Use it to validate the queue-walking + forward-progress fix safely. (Note:
    # in dry-run nothing leaves the queue, so every case is treated as "skipped"
    # and the bot steps through the whole queue once, then ends the pass.)
    dry_run = os.getenv("DRY_RUN", "").strip().lower() in ("1", "true", "yes")
    if dry_run:
        print("[HepB] DRY-RUN enabled: no approvals, rejections, or emails will be sent.")

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
    # Names of cases reviewed this pass that could NOT be actioned (e.g. the case
    # couldn't be relocated by name to reject). Tracked so the bot steps past them
    # instead of re-reading the same un-actionable case at the top forever.
    skipped_names = set()
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
            
            NBS.CheckFirstCase(n)
            # Remember the case currently at row n. The reject path below re-sorts,
            # re-reads the case, and only rejects if it is still the SAME case
            # (final_name == initial_name). Without this, initial_name stays None,
            # the comparison is always False, the case is never rejected, stays in
            # the queue, and the bot re-reviews it forever.
            NBS.initial_name = NBS.patient_name
            # Guard against None (empty queue / walked past the last row):
            # CheckFirstCase sets condition=None when there's no row at n, and
            # None.lower() would crash into the except handler and spin instead of
            # reaching the no-case handling below.
            if NBS.condition and 'hepatitis b' in NBS.condition.lower():
                consecutive_errors = 0  # a real HepB case was found

                # A case we reviewed but could NOT action this pass stays in the
                # queue. The bot always re-reads from the top, so without stepping
                # past such a case it re-reviews it forever -- one stuck case walls
                # off every case behind it (this is what left cases in the queue).
                # Step over anything already skipped this pass.
                if NBS.initial_name and NBS.initial_name in skipped_names:
                    n += 1
                    continue

                NBS.GoToNCaseInApprovalQueue(n)
                if NBS.queue_loaded:
                    NBS.queue_loaded = None
                    continue
                inv_id = NBS.find_element(By.XPATH,'//*[@id="bd"]/table[3]/tbody/tr[2]/td[1]/span[2]').text
                print(f"[HepB] reviewing inv_id={inv_id} name={NBS.patient_name!r} (row {n})")

                NBS.StandardChecks()
                print(f"[HepB] inv_id={inv_id} issues={NBS.issues}")
                # Track whether the case actually left the queue. If it did NOT,
                # advance past it; if it did, rows shifted up so rescan from row 1.
                actioned = False
                if not NBS.issues:
                    NBS.reviewed_ids.append(inv_id)
                    NBS.what_do.append("DRY-RUN would Approve" if dry_run else "Approve Notification")
                    NBS.reason.append('No issues found.')
                    if not dry_run:
                        NBS.ApproveNotification()
                        actioned = True
                        print(f"Approved notification for {inv_id}")
                    else:
                        print(f"[DRY-RUN] would APPROVE {inv_id} (no issues)")
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
                        NBS.what_do.append("DRY-RUN would Reject" if dry_run else "Reject Notification")
                        NBS.reason.append(' '.join(NBS.issues))
                        if dry_run:
                            print(f"[DRY-RUN] would REJECT {inv_id} ({NBS.initial_name!r}) at row {reject_row}. "
                                  f"Issues: {' | '.join(NBS.issues)}")
                        else:
                            NBS.RejectNotification(reject_row)
                            actioned = True
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

                if actioned:
                    # Case left the queue; rows shifted up, so rescan from the top.
                    # Any earlier-skipped cases now at the top are stepped over via
                    # the skipped_names guard above.
                    n = 1
                else:
                    # Could not action this case; remember it and move past it so
                    # it can't block the cases behind it.
                    if NBS.initial_name:
                        skipped_names.add(NBS.initial_name)
                    n += 1
            else:
                # No HepB case at row n. If we've walked past row 1, the only HepB
                # cases left are ones already skipped this pass, so the pass is
                # effectively done. If still at row 1, the queue is genuinely empty
                # of HepB cases.
                if n > 1:
                    print(f"[HepB] reached row {n} with no further HepB cases; "
                          f"{len(skipped_names)} case(s) skipped this pass. Ending pass.")
                    if not dry_run:
                        NBS.SendManualReviewEmail()
                    break
                if attempt_counter < NBS.num_attempts:
                    attempt_counter += 1
                else:
                    attempt_counter = 0
                    print("No Hep_B cases in notification queue.")
                    if not dry_run:
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
            consecutive_errors += 1

            # A case that raises MID-REVIEW (e.g. a missing field on this
            # particular case) is a "poison" case: it was never actioned, so it
            # stays in the queue. Record it and advance past it so a single poison
            # case can't end the pass and block every case behind it on every
            # cycle. Then reset to a clean approval queue -- a failed case often
            # leaves the page in a state where the next SortQueue throws
            # stale-element errors, which would otherwise burn the consecutive-
            # error budget and end the pass on an avoidable cascade.
            if NBS.initial_name:
                skipped_names.add(NBS.initial_name)
                log_offending = NBS.initial_name
            else:
                log_offending = "<unknown>"
            print(f"[HepB] recording poison case {log_offending!r} as skipped and advancing.")
            n += 1
            try:
                NBS.GoToApprovalQueue()
            except Exception as recover_err:
                print(f"[HepB] queue recovery after exception failed: {recover_err}")

            # Once the queue is empty, SortQueue/CheckFirstCase keep throwing
            # (stale element / nothing to read) and that lands here every pass.
            # Break after several CONSECUTIVE errors (reset whenever a real case is
            # found), so an emptied/persistently-broken queue ends the run cleanly.
            if consecutive_errors >= max_consecutive_errors:
                print(f"[HepB] {consecutive_errors} consecutive errors with no case "
                      f"actioned; queue appears empty/unstable. Ending run.")
                break
        #     # print(tb)
        #     with open("error_log.txt", "a") as log:
        #         log.write(f"{datetime.now().date().strftime('%m_%d_%Y')} | HepB - {str(tb)}")
        #     #NBS.send_smtp_email(NBS.covid_informatics_list, 'ERROR REPORT: NBSbot(HepB Notification Review) AKA HepB', tb, 'error email')
            
    NBS.HepB_notification_bot = True
    if not dry_run:
        NBS.SendBotRunEmail()
        #NBS.CreateExcelSheet()
        NBS.SendEmailToAssign()
    else:
        print("[DRY-RUN] skipping SendBotRunEmail / SendEmailToAssign.")


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
