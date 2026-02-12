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
from decorator import error_handle

def generator():
    while True:
        yield

reviewed_ids = []
what_do = []
reason = []

is_in_production = os.getenv('ENVIRONMENT', 'production') != 'development'
@error_handle
def start_ILIOutbreak(username, passcode):
    
    load_dotenv()
    from .ILIOutbreak import ILIOutbreak
    NBS = ILIOutbreak(production=is_in_production)  # production=True & Test = is_in_production
    if is_in_production:
        print("Production Environment")
    else:
        print("Development Environment")
        
    NBS.set_credentials(username, passcode)
    NBS.log_in()
    NBS.GoToApprovalQueue()

    patients_to_skip = []
    error_list = []
    error = False
    n = 1
    attempt_counter = 0
    limit = 8
    loop = tqdm(generator())
    for _ in loop:
        #check if the bot haa gone through the set limit of reviews
        if loop.n == limit:
            break
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
                    body = ''
                    if  all(case in NBS.issues  for case in ['City is blank.', 'County is blank.', 'Zip code is blank.']):
                        body = 'Hey, please only update City, Zip Code and County, then Click CN'
                    elif NBS.CorrectCaseStatus:
                        body = f'Hey, please only update the case status to {NBS.CorrectCaseStatus}, then click CN for this case.'
                    if body:
                        print('mail', body)
                        NBS.SendILIOutbreakEmail(NBS,body,inv_id)
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
    bot_act.to_excel(f"saved/ILIOutbreak/ILIOutbreak_bot_activity_{datetime.now().date().strftime('%m_%d_%Y')}.xlsx")
    print("Excel file created")

if __name__ == '__main__':
    start_ILIOutbreak()
