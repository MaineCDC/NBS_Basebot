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
    '''with open("patients_to_skip.txt", "r") as patient_reader:
        patients_to_skip.append(patient_reader.readlines())'''

    limit = 41
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
                NBS.inv_id = NBS.find_element(By.XPATH,'//*[@id="bd"]/table[3]/tbody/tr[2]/td[1]/span[2]').text 
                NBS.StandardChecks()
                if not NBS.issues:
                    reviewed_ids.append(NBS.inv_id)
                    what_do.append("Approved Notification")
                    reason.append('No issues found.')
                    print("Approved Notification")
                    NBS.ApproveNotification()
                    #NBS.SendILIOutbreakEmail("Hey, please don't change anything at all and just click CN", NBS.inv_id)
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
                    reviewed_ids.append(NBS.inv_id)
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
                        NBS.SendILIOutbreakEmail(NBS,body, NBS.inv_id)
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
        #     # print(tb)
        #     with open("error_log.txt", "a") as log:
        #         log.write(f"{datetime.now().date().strftime('%m_%d_%Y')} | ILI Related Outbreak - {str(tb)}")
        #     #NBS.send_smtp_email(NBS.covid_informatics_list, 'ERROR REPORT: NBSbot(ILI Related Outbreak Notification Review) AKA Athena', tb, 'error email')

    print("ending, printing, saving")
    bot_act = pd.DataFrame(
        {'Inv ID': reviewed_ids,
        'Action': what_do,
        'Reason': reason
        })
    bot_act.to_excel(f"ILIOutbreak_bot_activity_{datetime.now().date().strftime('%m_%d_%Y')}.xlsx")
    print("Excel file created")

    # body = "The list of ILI Related Outbreak notifications that need to be manually reviewed are in the attached spreadsheet."

    # message = EmailMessage()
    # message.set_content(body)
    # message['Subject'] = 'Notification Review Report: NBSbot(ILI Related Outbreak Notification Review) AKA ILI Related Outbreak'
    # message['From'] = NBS.nbsbot_email
    # message['To'] = ', '.join(["disease.reporting@maine.gov"])
    # with open(f"ILIOutbreak_bot_activity_{datetime.now().date().strftime('%m_%d_%Y')}.xlsx", "rb") as f:
    #     message.add_attachment(
    #         f.read(),
    #         filename=f"ILIOutbreak_bot_activity_{datetime.now().date().strftime('%m_%d_%Y')}.xlsx",
    #         maintype="application",
    #         subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    #     )
    # smtpObj = smtplib.SMTP(NBS.smtp_server)
    # smtpObj.send_message(message)
    
    '''with open("patients_to_skip.txt", "w") as patient_writer:
        for patient_id in patients_to_skip: patient_writer.write(f"{patient_id}\n")
    if error is not None: 
        raise Exception(error_list)'''
    #NBS.send_smtp_email("disease.reporting@maine.gov", 'Notification Review Report: NBSbot(Anaplasma Notification Review) AKA ILI Related Outbreak', body, 'ILI Related Outbreak Notification Review email')

if __name__ == '__main__':
    start_ILIOutbreak()
