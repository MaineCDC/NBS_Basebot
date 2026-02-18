# -*- coding: utf-8 -*-
"""
Created on Wed Mar 26 2025

@author: Vaishnavi.Appidi
"""
from tqdm import tqdm
import time
from selenium.webdriver.common.by import By
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
def start_strep(username, passcode, driver_instance=None):
    from .strep_prod import Strep
    
    if driver_instance:
        nbs_driver = driver_instance
    else:
        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service
        chrome_driver_path = "C:/Users/vaishnavi.appidi/OneDrive - State of Maine/Desktop/chromedriver-win32/chromedriver.exe"
        service = Service(chrome_driver_path)
        nbs_driver = webdriver.Chrome(service=service)
    
    NBS = Strep(production=True, driver=nbs_driver)  # production=True & Test = is_in_production
    error_list = []
    error = False
    n = 1
    attempt_counter = 0
    '''with open("patients_to_skip.txt", "r") as patient_reader:
        patients_to_skip.append(patient_reader.readlines())'''

    loop = tqdm(generator())
    for _ in loop:
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
            
            #NBS.SortQueue(paths)
            NBS.SortApprovalQueueStrep()
            if NBS.queue_loaded:
                NBS.queue_loaded = None
                continue
            elif NBS.queue_loaded == False:
                NBS.queue_loaded = None
                NBS.SendManualReviewEmail()
                if attempt_counter < NBS.num_attempts:
                    attempt_counter += 1
                else:
                    attempt_counter = 0
                    print("No Group A strep cases in notification queue.")
                    NBS.SendManualReviewEmail()
                    NBS.Sleep()
                    break
                #NBS.Sleep()
                #continue
            
            NBS.CheckFirstCase()
            if NBS.condition == 'Group A Streptococcus, invasive':
                NBS.GoToNCaseInApprovalQueue(n)
                if NBS.queue_loaded:
                    NBS.queue_loaded = None
                    continue
                inv_id = NBS.driver.find_element(By.XPATH,'//*[@id="bd"]/table[3]/tbody/tr[2]/td[1]/span[2]').text 
                '''if any(inv_id in skipped_patients for skipped_patients in patients_to_skip):
                    print(f"present, {inv_id}")
                    NBS.ReturnApprovalQueue()
                    n = n + 1
                    continue'''
                
                NBS.StandardChecks()
                if not NBS.issues:
                    reviewed_ids.append(inv_id)
                    what_do.append("Approved Notification")
                    reason.append('No issues found.')
                    print("Approved Notification")
                    NBS.ApproveNotification()
                    #NBS.SendStrepEmail("Hey, please don't change anything at all and just click CN", inv_id)
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
                    '''if NBS.country != 'UNITED STATES':
                        print("Skipping patient. No action carried out")
                        patients_to_skip.append(inv_id)'''
                    if NBS.final_name == NBS.initial_name:
                        reviewed_ids.append(inv_id)
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
                            NBS.SendStrepEmail(body, inv_id)
                        # NBS.ReturnApprovalQueue()
                    elif NBS.final_name != NBS.initial_name:
                        print(f"here : {NBS.final_name} {NBS.initial_name}")
                        print('Case at top of queue changed. No action was taken on the reviewed case.')
                        NBS.num_fail += 1
            else:
                if attempt_counter < NBS.num_attempts:
                    attempt_counter += 1
                else:
                    attempt_counter = 0
                    print("No Group A strep cases in notification queue.")
                    NBS.SendManualReviewEmail()
                    NBS.Sleep()
                    break
        except Exception as e:
            # raise Exception(e)
            error_list.append(str(e))
            error = True



if __name__ == '__main__':
    start_strep()
