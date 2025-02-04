
# -*- coding: utf-8 -*-
"""
Created on Tue Jan  9 13:14:44 2024

@author: Jared.Strauch
"""
import os
from tqdm import tqdm
import time
import traceback
from selenium.webdriver.common.alert import Alert
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import NoSuchElementException, ElementNotInteractableException
from selenium.common.exceptions import ElementNotInteractableException
from selenium.common.exceptions import StaleElementReferenceException
from selenium.common.exceptions import TimeoutException
import warnings

import pandas as pd

from bs4 import BeautifulSoup
from datetime import datetime
from io import StringIO
import re
import numpy as np

from dateutil.relativedelta import relativedelta
from pandas._libs.tslibs.parsing import DateParseError
from epiweeks import Week
from decorator import error_handle 


def generator():
    while True:
        yield

reviewed_ids = []
what_do = []
merges = []
merge_ids = []
is_in_production = os.getenv('ENVIRONMENT', 'production') != 'development'

if is_in_production:
    print("Production Environment")
else:
    print('Development Environment')



@error_handle
def start_audrey(username, passcode):
    warnings.simplefilter(action='ignore', category=FutureWarning)
    pd.options.mode.chained_assignment = None

    from .audrey import Audrey
    
    NBS = Audrey(production=is_in_production)
    NBS.set_credentials(username, passcode)
    NBS.log_in()
    attempt_counter = 0
    NBS.get_db_connection_info()
    NBS.get_patient_table()
    NBS.pause_for_database()

    limit = 40
    loop = tqdm(generator())
    for _ in loop:
        #check if the bot haa gone through the set limit of reviews
        if loop.n == limit:
            break
        #Go to Document Requiring Review
        partial_link = 'Documents Requiring Review'
        WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.element_to_be_clickable((By.PARTIAL_LINK_TEXT, partial_link)))
        NBS.find_element(By.PARTIAL_LINK_TEXT, partial_link).click()
        time.sleep(1)
        
        #Sort review queue so that only hepatitis cases are listed
        clear_filter_path = '//*[@id="removeFilters"]/table/tbody/tr/td[2]/a'
        description_path = '/html/body/div[2]/form/div/table[2]/tbody/tr/td/table/thead/tr/th[6]/img'
        clear_checkbox_path = '//*[@id="parent"]/thead/tr/th[6]/div/label[2]/input'
        click_ok_path = '/html/body/div[2]/form/div/table[2]/tbody/tr/td/table/thead/tr/th[6]/div/label[1]/input[1]'
        click_cancel_path = '/html/body/div[2]/form/div/table[2]/tbody/tr/td/table/thead/tr/th[6]/div/label[1]/input[2]'
        submit_date_path = '//*[@id="parent"]/thead/tr/th[3]/a'

        #clear all filters
        WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.element_to_be_clickable((By.XPATH, clear_filter_path)))
        NBS.find_element(By.XPATH, clear_filter_path).click()
        time.sleep(5)
        
        #NBS.find_element(By.XPATH, '//*[@id="myQueues"]/div/div[3]/ul/li[3]/a').click()
        #open description dropdown menu
        WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.presence_of_element_located((By.XPATH, description_path)))
        WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.element_to_be_clickable((By.XPATH, description_path)))
        NBS.find_element(By.XPATH, description_path).click()
        time.sleep(1)
        
        #clear checkboxes
        WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.element_to_be_clickable((By.XPATH, clear_checkbox_path)))
        NBS.find_element(By.XPATH,clear_checkbox_path).click()
        time.sleep(1)
        
        #select all hepatitis tests
        tests = ["Hep", "HEP", "HAV", "HBV", "HCV", "Alanine", "ALT"]
        for test in tests:
            try:
                results = NBS.find_elements(By.XPATH,f"//label[contains(text(),'{test}')]")
                for result in results:
                    result.click()
            except (NoSuchElementException, ElementNotInteractableException) as e:
                pass
        time.sleep(1)
        
        #click ok
        try:
            WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.element_to_be_clickable((By.XPATH, click_ok_path)))
            NBS.find_element(By.XPATH,click_ok_path).click()
        except NoSuchElementException:
            #click cancel and go back to home page to wait for more ELRs
            WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.element_to_be_clickable((By.XPATH, click_cancel_path)))
            NBS.find_element(By.XPATH,click_cancel_path).click()
            NBS.go_to_home()
            time.sleep(3)
            NBS.Sleep()
            #this wont work if we are not running the for loop to cycle through the queue,
            #comment out if not running the whole thing
            continue
        time.sleep(1)
        
        #sort chronologically, oldest first
        WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.element_to_be_clickable((By.XPATH, submit_date_path)))
        NBS.find_element(By.XPATH, submit_date_path).click()
        WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.element_to_be_clickable((By.XPATH, submit_date_path)))
        NBS.find_element(By.XPATH, submit_date_path).click()
        
        #Grab all ELRs in the queue to reference later. Grab the event ID so we can make sure that we
        #don't get stuck in a loop at the top of the queue if an ELR doesn't get cleared out of the queue
        
        #Grab the ELR table 
        review_queue_table_path = '//*[@id="parent"]'
        html = NBS.find_element(By.XPATH, review_queue_table_path).get_attribute('outerHTML')
        soup = BeautifulSoup(html, 'html.parser')
        review_queue_table = pd.read_html(StringIO(str(soup)))[0]
        review_queue_table.fillna('', inplace = True)
        #maybe change above '' to None
        
        #Check to see if we have looked at this ELR before by the local ID
        i = 0
        try:
            while review_queue_table["Local ID"].iloc[i] in reviewed_ids:
                i += 1
        except IndexError:
            print("No IDs to review. Stopping...")
            break

        #grab the first local ID we haven't reviewed and append it to the list for later use 
        event_id = review_queue_table["Local ID"].iloc[i]
        reviewed_ids.append(event_id) 
        #identify the element that has the event id to be reviewed and navigate to that Lab Report
        
        try:
            anc = NBS.find_element(By.XPATH,f"//td[contains(text(),'{event_id}')]/../td/a")
        except NoSuchElementException:
            anc = NBS.find_element(By.XPATH,f"//font[contains(text(),'{event_id}')]/../../td/a")
        anc.click()
        
        #check the patient name if it is a source patient skip, look for numbers in the name
        pat_name_elem = NBS.find_element(By.XPATH, '//*[@id="Name"]')
        pat_name = pat_name_elem.text
        if bool(re.search(r'\d', pat_name)) or bool(re.search(r'SRC', pat_name)):
            print("Source patient, skip")
            what_do.append("Source patient, skip")
            continue
        
        #grab the patients age, if younger the 3 years do not continue
        pat_dob_elem = NBS.find_element(By.XPATH, '//*[@id="Dob"]')
        pat_dob_text = pat_dob_elem.text
        pat_dob_date = re.findall(r'\b\d{2}/\d{2}/\d{4}\b',pat_dob_text)[0]
        pat_dob = datetime.strptime(pat_dob_date, '%m/%d/%Y').date()
        
        #grab the patient gender, we are going to let an epi take care of inveg=tigations for females age 14-39
        pat_gen_elem = NBS.find_element(By.XPATH, '//*[@id="Sex"]')
        pat_gen = pat_gen_elem.text
        
        
        #go to the patient file to review investigations
        WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.element_to_be_clickable((By.XPATH, '//*[@id="doc3"]/div[1]/a[1]')))
        NBS.find_element(By.XPATH, '//*[@id="doc3"]/div[1]/a[1]').click()
        
        time.sleep(3)
        
        #Go to events tab
        WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.element_to_be_clickable((By.XPATH, '//*[@id="tabs0head1"]')))
        NBS.find_element(By.XPATH, '//*[@id="tabs0head1"]').click()
        
        try:
            investigation_table = NBS.read_investigation_table()
        except NoSuchElementException:
            inv_found = False
            existing_not_a_case = False   
            
        #Navigate to the lab report to be processed using the Event ID from the patient page
        lab_report_table_path = '//*[@id="lab1"]'
        lab_report_table = NBS.ReadTableToDF(lab_report_table_path)
        
        lab_row = lab_report_table[lab_report_table['Event ID'] == re.findall(r'OBS\d+ME\d+',event_id)[0]]
        lab_index = int(lab_row.index.to_list()[0]) + 1
        
        if lab_index > 1:
            lab_path = f'/html/body/div[2]/form/div/table[4]/tbody/tr[2]/td/div[2]/table/tbody/tr/td/div[1]/div[5]/div/table/tbody/tr/td/table/tbody/tr[{str(lab_index)}]/td[1]/a'
        elif lab_index == 1:
            lab_path = '/html/body/div[2]/form/div/table[4]/tbody/tr[2]/td/div[2]/table/tbody/tr/td/div[1]/div[5]/div/table/tbody/tr/td/table/tbody/tr/td[1]/a'
        WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.element_to_be_clickable((By.XPATH, lab_path)))
        NBS.find_element(By.XPATH, lab_path).click()
        
        #Grab alanine aminotransferase results in case we need to create an investigation
        alt_lab_table = lab_report_table[lab_report_table["Test Results"].str.contains("ALANINE|ALT|Alanine")]
        
        #sometime we don't have a collection date or report date, try collection date first then report date
        try:
            lab_elem_path = '//*[@id="bd"]/table[1]/tbody/tr[5]/td[1]/span[2]'
            WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.presence_of_element_located((By.XPATH, lab_elem_path)))
            lab_elem = NBS.find_element(By.XPATH, lab_elem_path)
            lab_date_text = lab_elem.text
            lab_date = datetime.strptime(lab_date_text, '%m/%d/%Y').date()
        except ValueError:
            lab_elem = NBS.find_element(By.XPATH, '//*[@id="bd"]/table[1]/tbody/tr[5]/td[2]/span[2]')
            lab_date_text = lab_elem.text
            lab_date = datetime.strptime(lab_date_text, '%m/%d/%Y').date()
        
        #make sure the patient is over 36 months old
        age = lab_date - pat_dob
        if age.days < 1095:
            NBS.go_to_home()
            print("Patient under 36 months old")
            what_do.append("Too young")
            continue
        
            
        alt_lab = None
        #We only care about the highest alanine aminotransferase result that has the highest result within a +- 3 month interval
        if len(alt_lab_table) >= 1:
            try:
                alt_lab_table['Date Collected'] = pd.to_datetime(alt_lab_table['Date Collected'])
                keep = (alt_lab_table["Date Collected"] <= lab_date  + pd.DateOffset(months=3)) & (alt_lab_table["Date Collected"] >= lab_date - pd.DateOffset(months=3))
                alt_lab_table = alt_lab_table[keep]
                #need to make sure the first number is always the result. pretty sure it is
                alt_lab_table["num_res"] = alt_lab_table['Test Results'].str.extract(r'(\d+)').astype(int)
                alt_lab = alt_lab_table[alt_lab_table.index == alt_lab_table["num_res"].idxmax()]
            except ValueError:
                try:
                    alt_lab_table['Date Received'] = pd.to_datetime(alt_lab_table['Date Received'])
                    keep = (alt_lab_table["Date Received"] <= lab_date  + pd.DateOffset(months=3)) & (alt_lab_table["Date Received"] >= lab_date - pd.DateOffset(months=3))
                    alt_lab_table = alt_lab_table[keep]
                    #need to make sure the first number is always the result. pretty sure it is
                    alt_lab_table["num_res"] = alt_lab_table['Test Results'].str.extract(r'(\d+)').astype(int)
                    alt_lab = alt_lab_table[alt_lab_table.index == alt_lab_table["num_res"].idxmax()]
                except ValueError:
                    pass
        
        
        #grab date reported to public health from lab report
        #WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.presence_of_element_located((By.XPATH, '//*[@id="NBS_LAB201"]')))
        #PH_report = NBS.find_element(By.XPATH, '//*[@id="NBS_LAB201"]')
        WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.presence_of_element_located((By.XPATH, '//*[@id="bd"]/table[1]/tbody/tr[5]/td[3]/span[2]')))
        PH_report = NBS.find_element(By.XPATH, '//*[@id="bd"]/table[1]/tbody/tr[5]/td[3]/span[2]')
        PH_report_date_text = PH_report.text
        PH_report_date = datetime.strptime(PH_report_date_text, '%m/%d/%Y').date()
        
        time.sleep(3)
        
        #Read the ELR into a dataframe
        resulted_test_path = '//*[@id="RESULTED_TEST_CONTAINER"]/tbody/tr[1]/td/table'
        resulted_test_table = NBS.ReadTableToDF(resulted_test_path)
        
        #Process the ELR so that it is easier to go through the logic trees for Hepatitis B and C ELRs
        test_type = None
        mark_reviewed = False
        create_inv = False
        update_status = False
        associate = False
        send_alt_email = False
        send_inv_email = False
        condition = None
        update_inv_type = False
        not_a_case = False
        acute_inv = None
        chronic_inv = None
        Genotype_test = None
        genotype = None
        NBS.incomplete_address_log = []
        if len(resulted_test_table) == 2:
            #check for ELRs that have two Hep B tests, if so only look at the antigen test
            resulted_test_table_B = resulted_test_table[resulted_test_table["Resulted Test"].str.contains("HBV|Hepatitis B")]
            if len(resulted_test_table_B) == 2:
                resulted_test_table = resulted_test_table_B[resulted_test_table_B["Resulted Test"].str.contains("Ag|Antigen|AG")]
            #Some Hep C RNA tests have base 10 and log 10 values, we only need one. 
            #Some tests have both Hep C RNA and Genotype. Use the RNA for the workflows, save the genotype in case an investigation needs to be created.
            resulted_test_table_C = resulted_test_table[resulted_test_table["Resulted Test"].str.contains("HCV|Hepatitis C")]
            if len(resulted_test_table_C) == 2:
                resulted_test_table_C = resulted_test_table_C[resulted_test_table_C["Resulted Test"].str.contains("RNA")]
                if len(resulted_test_table_C) == 2:
                    resulted_test_table = resulted_test_table_C[resulted_test_table_C["Resulted Test"].str.contains("Log|log|LOG")]
                elif len(resulted_test_table_C) == 1:
                    Genotype_test = resulted_test_table[resulted_test_table["Resulted Test"].str.contains("GEN|Gen|gen")]
                    resulted_test_table = resulted_test_table_C
                    
        if len(resulted_test_table) == 1:    
            #Clean up test name
            if any(x in str(resulted_test_table["Resulted Test"]) for x in ["Hepatitis C", "HEPATITIS C", "HCV"]):
                test_condition = "Hepatitis C"
            elif any(x in str(resulted_test_table["Resulted Test"]) for x in ["Hepatitis B", "HEPATITIS B", "HBV"]):
                test_condition = "Hepatitis B"
            elif any(x in str(resulted_test_table["Resulted Test"]) for x in ["Alanine", "ALT"]):
                test_condition = "Hepatitis"
            else:
                test_condition = "Hepatitis A"
            
            #Check if the test is antibody, antigen, RNA, DNA or genotype
            if any(x in str(resulted_test_table["Resulted Test"]) for x in ["Ab", "AB", "IgG", "IgM", "ANTIBODY", "Antibody", "antibody", "IGG", "IgG"]):
                test_type = "Antibody"
            if any(x in str(resulted_test_table["Resulted Test"]) for x in ["RNA", "Qnt"]):
                test_type = "RNA"
            if "DNA" in str(resulted_test_table["Resulted Test"]):
                test_type = "DNA"
            if any(x in str(resulted_test_table["Resulted Test"]) for x in ["Gen", "gen", "GEN"]):
                test_type = "Genotype"
            if any(x in str(resulted_test_table["Resulted Test"]) for x in ["Ag", "AG", "Antigen", "antigen", "ANTIGEN"]):
                test_type = "Antigen"
            if any(x in str(resulted_test_table["Resulted Test"]) for x in ["Alanine", "ALT"]):
                test_type = "Alanine"
            #else:
                #test_type = "Something else"   
            
            """ Review the Investigations table in the Events tab of a patient profile
            to determine if the case already has an existing investigation. """
            existing_investigations = None
            if type(investigation_table) == pd.core.frame.DataFrame:
                existing_investigations = investigation_table[investigation_table["Condition"].str.contains(test_condition)]
                existing_investigations = existing_investigations[existing_investigations["Case Status"].str.contains("Confirmed|Probable")]
                
                if len(existing_investigations) >= 1:
                    inv_found = True
                    #If there is an existing perinatal investigation we are going to leave the ELR alone.
                    perinatal_inv = existing_investigations[existing_investigations["Condition"].str.contains("perinatal")]
                    if len(perinatal_inv) >= 1:
                        print("Patient has a perinatal investigation, leave for an epi")
                        what_do.append("Patient has a perinatal investigation, leave for an epi")
                        NBS.go_to_home()
                        continue
                    #Sometimes the C is capitalised in chronic investigations and sometimes 
                    #it is not so we are just going to look for "hronic" to avoid it
                    chronic_inv = existing_investigations[existing_investigations["Condition"].str.contains("hronic")]
                    acute_inv = existing_investigations[existing_investigations["Condition"].str.contains("acute")]
                    try:
                        inv_date = acute_inv['Start Date'].iloc[0]
                        inv_date = inv_date.date()
                        #get difference in time between lab result and time from investigation
                        time_diff = lab_date - inv_date
                        diff_days = time_diff.days
                    except:
                        inv_date = chronic_inv['Start Date'].iloc[0]
                        inv_date = inv_date.date()
                        time_diff = lab_date - inv_date
                        diff_days = time_diff.days

                    if len(existing_investigations.loc[existing_investigations['Case Status'] == 'Not a Case']) > 0:
                        existing_not_a_case = True
                    else:
                        existing_not_a_case = False
                else:
                        NBS.existing_investigation_index = None
                        inv_found = False
                        existing_not_a_case = False
            else:
                    inv_found = False
                    existing_not_a_case = False
            
            #if there is more than one probable/confirmed of the same investigation, skip over the ELR and send an email
            #chronic_inv.loc[chronic_inv.index.repeat(2)]
            if acute_inv is not None and chronic_inv is not None:
                if len(acute_inv) > 1:
                    if len(np.unique(acute_inv.Condition)) == 1 and len(acute_inv[acute_inv["Case Status"].str.contains("Probable|Confirmed")]) >=2:
                        send_inv_email = True
                        NBS.go_to_home()
                        print("More than one acute investigation of the same condition")
                        what_do.append("Multiple Investigations of same condition")
                        continue  
                if len(chronic_inv) > 1:
                    if len(np.unique(chronic_inv.Condition)) == 1 and len(chronic_inv[chronic_inv["Case Status"].str.contains("Probable|Confirmed")]) >=2:
                        send_inv_email = True
                        NBS.go_to_home()
                        print("More than one chronic investigation of the same condition")
                        what_do.append("Multiple Investigations of same condition")
                        continue

            #If there is a "<" in the results skip for now, could be either negative or positive and it is hard to tell without manual review
            if resulted_test_table["Coded Result / Organism Name"].astype(str).str.contains("<").iloc[0] or resulted_test_table["Text Result"].astype(str).str.contains("<").iloc[0] or resulted_test_table["Numeric Result"].astype(str).str.contains("<").iloc[0]:
                print("< in result, skip")
                what_do.append("< in result, skip")
                NBS.go_to_home()
                continue

            ###Hepatitis A###
            if test_condition == "Hepatitis A":
                if test_type == "Antibody" and "IgM" not in str(resulted_test_table["Resulted Test"]) and "IGM" not in str(resulted_test_table["Resulted Test"]):
                    mark_reviewed = True
                else:
                    print("Hepatitis A, skip")
                    what_do.append("Hepatitis A, skip")
                    NBS.go_to_home()
                    continue
            
            
            ###Hepatitis C Antibody test logic###
            if test_condition == "Hepatitis C" and test_type == "Antibody":
                if (any(x in str(resulted_test_table["Coded Result / Organism Name"]) for x in ["POS", "Positive", "POSITIVE", "Reactive", "REACTIVE", "Detected", "DETECTED"]) or any(x in str(resulted_test_table["Text Result"]) for x in ["POS", "Positive", "POSITIVE", "Reactive", "REACTIVE", "Detected", "DETECTED"])) and ("Non-Reactive" not in resulted_test_table["Text Result"].iloc[0] and "Non Reactive" not in resulted_test_table["Text Result"].iloc[0] and "Non-Reactive" not in resulted_test_table["Coded Result / Organism Name"].iloc[0] and "Non Reactive" not in resulted_test_table["Coded Result / Organism Name"].iloc[0] and "NON-REACTIVE" not in resulted_test_table["Coded Result / Organism Name"].iloc[0] and "NON-REACTIVE" not in resulted_test_table["Text Result"].iloc[0]): 
                    #grab all negative RNA\Genotype labs within a year, but not after
                    Gen_rna_lab = lab_report_table[lab_report_table["Test Results"].str.contains("Gen|RNA")]
                    Gen_rna_lab = Gen_rna_lab[Gen_rna_lab["Test Results"].str.contains("HEPATITIS C|HCV|Hepatitis C")]
                    try:
                        Gen_rna_lab["Date Collected"] = pd.to_datetime(Gen_rna_lab["Date Collected"]).dt.date
                        Gen_rna_lab = Gen_rna_lab[Gen_rna_lab["Date Collected"]<lab_date]
                    except (DateParseError, ValueError):
                        Gen_rna_lab["Date Received"] = pd.to_datetime(Gen_rna_lab["Date Received"]).dt.date
                        Gen_rna_lab = Gen_rna_lab[Gen_rna_lab["Date Received"]<lab_date]
                    
                    
                    year = int(datetime.today().strftime("%Y"))
                    mmwr_week = Week(year, 1)
                    
                    #put space in front to avoid grabbing tests that have the results in the reference range
                    Neg_Gen_rna_lab = Gen_rna_lab[Gen_rna_lab["Test Results"].str.contains(" Neg| NEG| neg| See Below| UNDETECTED| Undetected| undetected| Non-Reactive| NON-REACTIVE| NOT DETECTED| Not Detected")]
                    #grab all negative genotype or RNA tests to use as an index to find all positive genotype or RNA tests
                    Pos_Gen_rna_lab = Gen_rna_lab.drop(Neg_Gen_rna_lab.index)
                    Neg_Gen_rna_lab["Date Collected"] = pd.to_datetime(Neg_Gen_rna_lab["Date Collected"]).dt.date
                    Neg_Gen_rna_lab = Neg_Gen_rna_lab[Neg_Gen_rna_lab["Date Collected"]>mmwr_week.startdate()]
                    
                    #grab all negative labs within a year, add a space for the name so it doesn't trigger on the reference range
                    Neg_lab = lab_report_table[lab_report_table["Test Results"].str.contains(" Neg| NEG| neg| Not Detected| NOT DETECTED| UNDETECTED| Undetected| undetected")]
                    Neg_lab = Neg_lab[Neg_lab["Test Results"].str.contains("HEPATITIS C|HCV|Hepatitis C")]
                    Neg_lab["Date Collected"].replace('No Date', pd.NA, inplace=True)
                    Neg_lab["Date Collected"] = pd.to_datetime(Neg_lab["Date Collected"]).dt.date
                    Neg_lab = Neg_lab[Neg_lab["Date Collected"]>lab_date-relativedelta(years=1)]
                    #check investigation status
                    if chronic_inv is not None and acute_inv is not None:    
                        if len(chronic_inv) > 0 and chronic_inv["Case Status"].str.contains("Probable").any() or chronic_inv["Case Status"].str.contains("Confirmed").any():
                            mark_reviewed = True
                        elif len(acute_inv) > 0 and "Probable" in acute_inv["Case Status"].values or "Confirmed" in acute_inv["Case Status"].values:
                            mark_reviewed = True
                    elif len(Pos_Gen_rna_lab) == 0:
                        create_inv = True
                        if alt_lab is not None:    
                            if alt_lab["num_res"].iloc[0] <= 200 and len(Neg_lab) == 0:            
                                condition = 'Hepatitis C, chronic'
                            else:
                                condition = "Hepatitis C, acute"
                        else:
                            condition = "Hepatitis C, chronic"
                    elif len(Neg_Gen_rna_lab) >= 1:
                        mark_reviewed = True
                    elif len(Pos_Gen_rna_lab) > 0:
                            print("Skip, Previous positive RNA/Genotype. Should already have investigation created")
                            what_do.append("Skip, Previous positive RNA/Genotype. Should already have investigation created")
                        
                else:
                    #Mark as reviewed
                    mark_reviewed = True
            
            ###Hepatitis C RNA/Genotype logic###
            if test_condition == "Hepatitis C" and test_type in ("RNA", "DNA", "Genotype"):
                if type(resulted_test_table["Numeric Result"].iloc[0]) == str  and resulted_test_table["Numeric Result"].iloc[0] != "" and bool(re.search(r'\d', resulted_test_table["Numeric Result"].iloc[0])):
                    if resulted_test_table["Numeric Result"].str.extract(r'(\d+)').astype(int).iloc[0,0] > 0:
                        num_res = True
                elif type(resulted_test_table["Text Result"].iloc[0]) == str  and resulted_test_table["Text Result"].iloc[0] != "" and bool(re.search(r'\d', resulted_test_table["Text Result"].iloc[0])):
                    if resulted_test_table["Text Result"].str.extract(r'(\d+)').astype(int).iloc[0,0] > 0:
                        num_res = True
                elif type(resulted_test_table["Coded Result / Organism Name"].iloc[0]) == str  and resulted_test_table["Coded Result / Organism Name"].iloc[0] != "" and bool(re.search(r'\d', resulted_test_table["Coded Result / Organism Name"].iloc[0])):
                    if resulted_test_table["Coded Result / Organism Name"].str.extract(r'(\d+)').astype(int).iloc[0,0] > 0:
                        num_res = True
                elif type(resulted_test_table["Numeric Result"].iloc[0]) == np.int64:
                    if int(resulted_test_table["Numeric Result"].iloc[0])  > 0:
                        num_res = True
                elif type(resulted_test_table["Text Result"].iloc[0]) == np.int64:
                    if int(resulted_test_table["Text Result"].iloc[0])  > 0:
                        num_res = True
                elif type(resulted_test_table["Numeric Result"].iloc[0]) == np.float64:
                    if int(resulted_test_table["Numeric Result"].iloc[0])  > 0:
                        num_res = True
                elif type(resulted_test_table["Text Result"].iloc[0]) == np.float64:
                    if int(resulted_test_table["Text Result"].iloc[0])  > 0:
                        num_res = True
                elif type(resulted_test_table["Numeric Result"].iloc[0]) == float:
                    if int(resulted_test_table["Numeric Result"].iloc[0])  > 0:
                        num_res = True
                elif type(resulted_test_table["Text Result"].iloc[0]) == float:
                    if int(resulted_test_table["Text Result"].iloc[0])  > 0:
                        num_res = True
                elif type(resulted_test_table["Numeric Result"].iloc[0]) == int:
                    if int(resulted_test_table["Numeric Result"].iloc[0])  > 0:
                        num_res = True
                elif type(resulted_test_table["Text Result"].iloc[0]) == int:
                    if int(resulted_test_table["Text Result"].iloc[0])  > 0:
                        num_res = True
                elif resulted_test_table["Coded Result / Organism Name"].iloc[0] == "Detected":
                    num_res = True
                else:
                    num_res = False
                #grab negative labs within the last year, put a space for the name so that we don't grab the reference range by accident
                Neg_lab = lab_report_table[lab_report_table["Test Results"].str.contains(" Neg| NEG| Not Detected| NOT DETECTED| UNDETECTED")]
                Neg_lab = Neg_lab[Neg_lab["Test Results"].str.contains("HEPATITIS C|HCV|Hepatitis C")]
                Neg_lab["Date Collected"] = pd.to_datetime(Neg_lab["Date Collected"]).dt.date
                Neg_lab = Neg_lab[Neg_lab["Date Collected"]>lab_date-relativedelta(years=1)]
                
                if "Not Detected" not in resulted_test_table["Coded Result / Organism Name"].values and "Below threshold" not in resulted_test_table["Coded Result / Organism Name"].values and "Not Detected" not in resulted_test_table["Text Result"].values and "Below threshold" not in resulted_test_table["Text Result"].values and "Unable" not in resulted_test_table["Text Result"].values and "Unable" not in resulted_test_table["Coded Result / Organism Name"].values and "HCV RNA Not Detected" not in resulted_test_table["Result Comments"].values and num_res:
                    if chronic_inv is not None and acute_inv is not None:
                        if len(chronic_inv) > 0 and "Confirmed" in chronic_inv["Case Status"].values:
                            #Mark as reviewed
                            mark_reviewed = True
                        elif len(chronic_inv) > 0 and "Probable" in chronic_inv["Case Status"].values:
                            #update investigation to confirmed
                            update_status = True
                        elif len(acute_inv) > 0 and "Confirmed" in acute_inv["Case Status"].values and diff_days < 365:
                            #Mark as reviewed
                            mark_reviewed = True
                        elif len(acute_inv) > 0 and "Confirmed" in acute_inv["Case Status"].values and diff_days >= 365:  
                            create_inv = True
                            condition = "Hepatitis C, chronic"
                        elif len(acute_inv) > 0 and "Probable" in acute_inv["Case Status"].values and diff_days < 365:
                            #update investigation to confirmed
                            update_status = True
                        elif len(acute_inv) > 0 and "Probable" in acute_inv["Case Status"].values and diff_days >= 365:
                            create_inv = True
                            condition = "Hepatitis C, chronic"
                    else:
                        create_inv = True
                        if alt_lab is not None:
                            if alt_lab["num_res"].iloc[0] <= 200 and len(Neg_lab) == 0:            
                                condition = 'Hepatitis C, chronic'
                            else:
                                condition = "Hepatitis C, acute"
                        else:
                            condition = "Hepatitis C, chronic"
                elif any(x in str(resulted_test_table["Coded Result / Organism Name"]) for x in ["Undetected", "Not Detected", "UNDETECTED", "NOT DETECTED", "Negative", "NEGATIVE", "Unable"])  or any(x in str(resulted_test_table["Text Result"]) for x in ["Undetected", "Not Detected", "UNDETECTED", "NOT DETECTED", "Negative", "NEGATIVE", "Unable"]) or any(x in str(resulted_test_table["Result Comments"]) for x in ["HCV RNA Not Detected"]):
                    if acute_inv is not None and chronic_inv is not None: 
                        year = int(datetime.today().strftime("%Y"))
                        mmwr_week = Week(year, 1)
                        if len(acute_inv) > 0  and inv_date > mmwr_week.startdate() and test_type == "RNA" and "Probable" in acute_inv["Case Status"].values:
                            update_status = True
                            not_a_case = True
                            associate = True  
                        elif len(chronic_inv) > 0  and inv_date > mmwr_week.startdate() and test_type == "RNA" and "Probable" in chronic_inv["Case Status"].values:
                            update_status = True
                            not_a_case = True
                            associate = True
                        else:
                            mark_reviewed = True
                    else:
                        mark_reviewed = True
                else:
                    #Mark as reviewed
                    mark_reviewed = True
                #putting this here to override above logic since it won't catch 
                #ambiguous results
                if "See Below" in resulted_test_table["Text Result"].values:
                    print("Do nothing") 
                    what_do.append("Skip, ambiguous result")
                    mark_reviewed = False
                    
            ###Hepatitis B Logic###
            if test_condition == "Hepatitis B":
                if "Not Detected" in str(resulted_test_table["Coded Result / Organism Name"].iloc[0]) or "Below threshold" in str(resulted_test_table["Coded Result / Organism Name"].iloc[0]) or "Not Detected" in str(resulted_test_table["Text Result"].iloc[0]) or "Below threshold" in str(resulted_test_table["Text Result"].iloc[0]) or "Unable" in str(resulted_test_table["Text Result"].iloc[0]) or "Unable" in str(resulted_test_table["Coded Result / Organism Name"].iloc[0]) or "not detected" in str(resulted_test_table["Text Result"].iloc[0]) or "not detected" in str(resulted_test_table["Coded Result / Organism Name"].iloc[0]) or "UNDETECTED" in str(resulted_test_table["Text Result"].iloc[0]) or "UNDETECTED" in str(resulted_test_table["Coded Result / Organism Name"].iloc[0]) or "UNDETECTED" in str(resulted_test_table["Numeric Result"].iloc[0]) or "Negative" in str(resulted_test_table["Coded Result / Organism Name"].iloc[0]) or "Negative" in str(resulted_test_table["Numeric Result"].iloc[0]) or "Non-Reactive" in str(resulted_test_table["Coded Result / Organism Name"].iloc[0]) or "Non-Reactive" in str(resulted_test_table["Numeric Result"].iloc[0]) or "Non-Reactive" in str(resulted_test_table["Text Result"].iloc[0]) or "NEG" in str(resulted_test_table["Coded Result / Organism Name"].iloc[0]) or "NEG" in str(resulted_test_table["Numeric Result"].iloc[0]) or "NEG" in str(resulted_test_table["Text Result"].iloc[0]) or "NON-REACTIVE" in str(resulted_test_table["Coded Result / Organism Name"].iloc[0]) or "NON-REACTIVE" in str(resulted_test_table["Numeric Result"].iloc[0]) or "NON-REACTIVE" in str(resulted_test_table["Text Result"].iloc[0]):
                    mark_reviewed = True
                else:
                    IgM_lab = lab_report_table[lab_report_table["Test Results"].str.contains("IgM|IGM")]
                    IgM_lab = IgM_lab[IgM_lab["Test Results"].str.contains("HEPATITIS B|HBV|Hepatitis B")]
                
                    try:
                        IgM_lab["Date Collected"] = pd.to_datetime(IgM_lab["Date Collected"]).dt.date
                        IgM_lab = IgM_lab[IgM_lab["Date Collected"]>lab_date-relativedelta(months=6)]
                    except DateParseError:
                        IgM_lab["Date Received"] = pd.to_datetime(IgM_lab["Date Received"]).dt.date
                        IgM_lab = IgM_lab[IgM_lab["Date Received"]>lab_date-relativedelta(months=6)]
                        
                    Neg_IgM_lab = IgM_lab[IgM_lab["Test Results"].str.contains("Neg|NEG|See Below")]
                    Pos_IgM_lab = IgM_lab[IgM_lab["Test Results"].str.contains("Pos|POS|Det|DET|REA|Rea")]
                    if acute_inv is None and chronic_inv is None:
                        if len(resulted_test_table) == 1 and test_type == "Antibody" and "IgM" not in str(resulted_test_table["Resulted Test"]) and "IGM" not in str(resulted_test_table["Resulted Test"]): #add in logic for IgM
                            mark_reviewed = True
                        elif len(resulted_test_table) == 1 and test_type == "Antibody" and ("IgM" in str(resulted_test_table["Resulted Test"]) or "IGM" in str(resulted_test_table["Resulted Test"])) and "EQUIVOCAL" not in resulted_test_table["Coded Result / Organism Name"].iloc[0]:
                            #create_inv = True
                            #condition = "Hepatitis B, acute"
                            print("Hepatitis B, acute investigation to be assigned out")
                            what_do.append("Hepatitis B, acute investigation to be assigned out")
                            NBS.go_to_home()
                            continue
                        elif len(resulted_test_table) == 1 and test_type == "Antibody" and ("IgM" in str(resulted_test_table["Resulted Test"]) or "IGM" in str(resulted_test_table["Resulted Test"]))  and "EQUIVOCAL" in resulted_test_table["Coded Result / Organism Name"].iloc[0]:
                            mark_reviewed = True
                        elif test_type in ("Antigen", "DNA", "RNA"):
                            #add in logic to check IgM and ALT results
                            if len(IgM_lab) == 0:
                                #create_inv = True
                                if alt_lab is not None:
                                    if alt_lab["num_res"].iloc[0] <= 200:            
                                        #condition = 'Hepatitis B virus infection, chronic'
                                        print("Hepatitis B, chronic investigation to be assigned out")
                                        what_do.append("Hepatitis B, chronic investigation to be assigned out")
                                        NBS.go_to_home()
                                        continue
                                    else:
                                        #condition = "Hepatitis B, acute"
                                        print("Hepatitis B, acute investigation to be assigned out")
                                        what_do.append("Hepatitis B, acute investigation to be assigned out")
                                        NBS.go_to_home()
                                        continue
                                else:
                                    #condition = 'Hepatitis B virus infection, chronic'
                                    print("Hepatitis B, chronic investigation to be assigned out")
                                    what_do.append("Hepatitis B, chronic investigation to be assigned out")
                                    NBS.go_to_home()
                                    continue
                            elif len(Pos_IgM_lab) > 0:
                                #create_inv = True
                                #condition = "Hepatitis B, acute"
                                print("Hepatitis B, acute investigation to be assigned out")
                                what_do.append("Hepatitis B, acute investigation to be assigned out")
                                NBS.go_to_home()
                                continue
                            elif len(Neg_IgM_lab) > 0:
                                #create_inv = True
                                #condition = "Hepatitis B virus infection, Chronic"
                                print("Hepatitis B, chronic investigation to be assigned out")
                                what_do.append("Hepatitis B, chronic investigation to be assigned out")
                                NBS.go_to_home()
                                continue
                    elif chronic_inv is not None and acute_inv is not None and test_type in ("Antigen", "DNA", "RNA"):
                        if len(chronic_inv) > 0 and "Confirmed" in chronic_inv["Case Status"].values:
                            mark_reviewed = True
                        elif len(chronic_inv) > 0 and "Probable" in chronic_inv["Case Status"].values and diff_days >= 183 and test_type == "Antigen":
                            update_status = True
                        elif len(chronic_inv) > 0 and "Probable" in chronic_inv["Case Status"].values and diff_days < 183 and test_type == "Antigen":
                            mark_reviewed = True
                        elif len(chronic_inv) > 0 and "Probable" in chronic_inv["Case Status"].values and test_type in ("DNA", "RNA"):
                            update_status = True

                        if len(acute_inv) > 0 and "Confirmed" in acute_inv["Case Status"].values and diff_days >= 183 and len(chronic_inv) == 0:
                            #create_inv = True
                            #condition = "Hepatitis B virus infection, Chronic"
                            print("Hepatitis B, chronic investigation to be assigned out")
                            what_do.append("Hepatitis B, chronic investigation to be assigned out")
                            NBS.go_to_home()
                            continue
                        elif len(acute_inv) > 0 and "Confirmed" in acute_inv["Case Status"].values and diff_days < 183:
                            associate = True
                        #elif len(acute_inv) > 0 and "Probable" in acute_inv["Case Status"].values and test_type == "DNA":
                            #change case status to confirmed
                            #update_status = True
                        elif len(acute_inv) > 0 and "Probable" in acute_inv["Case Status"].values and diff_days < 183:
                            #change case status to confirmed
                            update_status = True
                        elif len(acute_inv) > 0 and "Probable" in acute_inv["Case Status"].values and diff_days >= 183 and len(chronic_inv) == 0:
                            #create_inv = True
                            #condition = "Hepatitis B virus infection, Chronic"
                            print("Hepatitis B, chronic investigation to be assigned out")
                            what_do.append("Hepatitis B, chronic investigation to be assigned out")
                            NBS.go_to_home()
                            continue
                    elif acute_inv is not None and chronic_inv is not None and test_type in "Antibody":
                        if len(acute_inv) > 0:
                            mark_reviewed = True
                        elif "IgM" in str(resulted_test_table["Resulted Test"]) and diff_days < 183 and len(acute_inv) == 0 and "Probable" in chronic_inv["Case Status"].values:
                            #change to confirmed acute
                            update_inv_type = True
                            condition = "Hepatitis B, acute"
                        else:
                            mark_reviewed = True
                        
            ###ALT Logic###
            #Sometimes the numeric result will have a < or > in it which converts the type to a string so we have to deal with that
            if test_condition == "Hepatitis" and test_type == "Alanine":
                if len(resulted_test_table) == 1:
                    if type(resulted_test_table["Numeric Result"].iloc[0]) == str  and resulted_test_table["Numeric Result"].iloc[0] != "" and bool(re.search(r'\d', resulted_test_table["Numeric Result"].iloc[0])):
                        if resulted_test_table["Numeric Result"].str.extract(r'(\d+)').astype(int).loc[0,0] > 200:
                            if acute_inv is not None and chronic_inv is not None and diff_days > 92:
                                mark_reviewed = True
                            elif acute_inv is not None and chronic_inv is not None and diff_days < 92:
                                if len(acute_inv) > 0:
                                    mark_reviewed = True
                                elif chronic_inv["Status"].iloc[0] == "Open":
                                    associate = True
                                    send_alt_email = True
                                elif chronic_inv["Status"].iloc[0] == "Closed" and "Hepatitis C" in chronic_inv["Condition"].iloc[0]:
                                    associate = True
                                    condition = "Hepatitis C, acute"
                                    send_alt_email = True
                                elif chronic_inv["Status"].iloc[0] == "Closed" and "Hepatitis B" in chronic_inv["Condition"].iloc[0]:
                                    send_alt_email = True
                            elif chronic_inv is None and acute_inv is None:
                                mark_reviewed = True
                        elif resulted_test_table["Numeric Result"].str.extract(r'(\d+)').astype(int).loc[0,0]  <= 200:
                            mark_reviewed = True
                elif type(resulted_test_table["Text Result"].iloc[0]) == str  and resulted_test_table["Text Result"].iloc[0] != "" and bool(re.search(r'\d', resulted_test_table["Text Result"].iloc[0])):
                        if resulted_test_table["Text Result"].str.extract(r'(\d+)').astype(int).loc[0,0] > 200:
                            if acute_inv is not None and chronic_inv is not None and diff_days > 92:
                                mark_reviewed = True
                            elif acute_inv is not None and chronic_inv is not None and diff_days < 92:
                                if len(acute_inv) > 0:
                                    mark_reviewed = True
                                elif chronic_inv["Status"].iloc[0] == "Open":
                                    associate = True
                                    send_alt_email = True
                                elif chronic_inv["Status"].iloc[0] == "Closed" and "Hepatitis C" in chronic_inv["Condition"].iloc[0]:
                                    associate = True
                                    condition = "Hepatitis C, acute"
                                    send_alt_email = True
                                elif chronic_inv["Status"].iloc[0] == "Closed" and "Hepatitis B" in chronic_inv["Condition"].iloc[0]:
                                    send_alt_email = True
                            elif chronic_inv is None and acute_inv is None:
                                mark_reviewed = True
                        elif resulted_test_table["Text Result"].str.extract(r'(\d+)').astype(int).loc[0,0]  <= 200:
                            mark_reviewed = True
                elif type(resulted_test_table["Numeric Result"].iloc[0]) == np.int64:
                    if int(resulted_test_table["Numeric Result"].iloc[0])  <= 200:
                        mark_reviewed = True
                    elif int(resulted_test_table["Numeric Result"].iloc[0]) > 200:
                        #add in within 3 months of lab specimen collection date in investigation
                        if acute_inv is not None and chronic_inv is not None and diff_days > 92:
                            mark_reviewed = True
                        elif acute_inv is not None and chronic_inv is not None and diff_days <= 92:
                            if len(acute_inv) > 0:
                                mark_reviewed = True
                            elif chronic_inv["Status"].iloc[0] == "Open":
                                associate = True
                                send_alt_email = True
                            elif chronic_inv["Status"].iloc[0] == "Closed" and "Hepatitis C" in chronic_inv["Condition"].iloc[0]:
                                associate = True
                                condition = "Hepatitis C, acute"
                                send_alt_email = True
                            elif chronic_inv["Status"].iloc[0] == "Closed" and "Hepatitis B" in chronic_inv["Condition"].iloc[0]:
                                send_alt_email = True
                        elif chronic_inv is None and acute_inv is None:
                            mark_reviewed = True
                elif type(resulted_test_table["Text Result"].iloc[0]) == np.int64:
                        if int(resulted_test_table["Text Result"].iloc[0])  <= 200:
                            mark_reviewed = True
                        elif int(resulted_test_table["Text Result"].iloc[0]) > 200:
                            #add in within 3 months of lab specimen collection date in investigation
                            if acute_inv is not None and chronic_inv is not None and diff_days > 92:
                                mark_reviewed = True
                            elif acute_inv is not None and chronic_inv is not None and diff_days < 92:  
                                if len(acute_inv) > 0:
                                    mark_reviewed = True
                                elif chronic_inv["Status"].iloc[0] == "Open":
                                    associate = True
                                    send_alt_email = True
                                elif chronic_inv["Status"].iloc[0] == "Closed" and "Hepatitis C" in chronic_inv["Condition"].iloc[0]:
                                    associate = True
                                    condition = "Hepatitis C, acute"
                                    send_alt_email = True
                                elif chronic_inv["Status"].iloc[0] == "Closed" and "Hepatitis B" in chronic_inv["Condition"].iloc[0]:
                                    send_alt_email = True
                            elif chronic_inv is None and acute_inv is None:
                                mark_reviewed = True
                else:
                    print("Could not parse")
                    what_do.append("Could not parse result, skipped")
        else:
            #pass
            print("More than one test in ELR")
            what_do.append("Skip, more than one test in ELR")
            print(review_queue_table[review_queue_table["Local ID"] == event_id]["Patient"])
            NBS.go_to_home()
            continue
        print(review_queue_table[review_queue_table["Local ID"] == event_id]["Patient"])
        
        ###If there is an open investigation, associate the lab to that investigation###
        if investigation_table is not None:
            open_inv = None
            open_inv = investigation_table[investigation_table["Condition"].str.contains(test_condition)]
            open_inv = open_inv[open_inv["Status"].str.contains("Open")]
            if len(open_inv) >= 1:
                associate = True
                mark_reviewed = False
                create_inv = False
                update_status = False
                update_inv_type = False
        
        #Now that we have determined what action we want to take, we need to actually do it
        if mark_reviewed == True and create_inv == False and update_status == False:
            WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.element_to_be_clickable((By.XPATH, '//*[@id="doc3"]/div[2]/table/tbody/tr/td[1]/input')))
            NBS.find_element(By.XPATH, '//*[@id="doc3"]/div[2]/table/tbody/tr/td[1]/input').click()
            print("Mark as Reviewed")
            what_do.append("Mark as Reviewed")
        elif create_inv == True and update_status == False:
            #don't create an investigation for female patients that are 14-49 
            if test_condition == "Hepatitis C" and pat_gen == "Female" and  5113 <= age.days <= 18263:
                print("Female patient between 14-49, let an epi handle this investigation")
                what_do.append("Female patient between 14-49, let an epi handle this investigation")
                NBS.go_to_home()
                continue
            #Hep C acute investigations need to be followed up by a field epi
            if condition == "Hepatitis C, acute":
                print("Hepatitis C, acute investigation. Leave for field epi follow up.")
                what_do.append("Hepatitis C, acute investigation. Leave for field epi follow up.")
                NBS.go_to_home()
                continue
            
            #We need a smart way to grab the first and last name of a patient, this isn't it but I think it will catch most of what we want.
            #Sometime a patient name in NBS will be just FIRST LAST, other times it can be FIRST I LAST or with suffixes.
            #If it is just FIRST LAST, grab those. If it is anything more complicated, the last name is usually third in the string so grab that.
            #This will run into problems with hyphenated last names or if they are St.something.
            #We only check the first two characters in the merge function though so hopefully it will be alright.
            if len(pat_name.split()) > 2:
                first_name = pat_name.split()[0]
                last_name = pat_name.split()[2]
            else:
                first_name = pat_name.split()[0]
                last_name = pat_name.split()[1]
                
                
            matches = NBS.patient_list.loc[(NBS.patient_list.FIRST_NM.str[:2] == first_name[:2]) & (NBS.patient_list.LAST_NM.str[:2] == last_name[:2]) & (NBS.patient_list.BIRTH_DT == pat_dob)]
            unique_profiles = matches.PERSON_PARENT_UID.unique()
            if len(unique_profiles) >= 2:
                print('Possible merge(s) found. Lab skipped.')
                what_do.append('Possible merge(s) found. Lab skipped.')
                merges.append(event_id)
                merge_ids.append(str(unique_profiles))
                NBS.go_to_home()
                continue
        
            #check to make sure the address is from Maine
            WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.presence_of_element_located((By.XPATH, '//*[@id="Address"]')))
            add_elem = NBS.find_element(By.XPATH, '//*[@id="Address"]')
            address = add_elem.text
            if 'ME' not in address:
                print('Out of State Patient Lab skipped.')
                what_do.append('Out of State Patient Lab skipped.')
                NBS.go_to_home()
                continue
            
            #create investigation
            create_investigation_button_path = '//*[@id="doc3"]/div[2]/table/tbody/tr/td[2]/input[1]'
            WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.element_to_be_clickable((By.XPATH, create_investigation_button_path)))
            NBS.find_element(By.XPATH, create_investigation_button_path).click()
            select_condition_field_path = '//*[@id="ccd_ac_table"]/tbody/tr[1]/td/input'
            
            
            WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.presence_of_element_located((By.XPATH, select_condition_field_path)))
            NBS.find_element(By.XPATH, select_condition_field_path).send_keys(condition)
            submit_button_path = '/html/body/table/tbody/tr/td/table/tbody/tr[3]/td/table/thead/tr[2]/td/div/table/tbody/tr/td/table/tbody/tr/td[4]/table[1]/tbody/tr[1]/td/input'
            WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.element_to_be_clickable((By.XPATH, submit_button_path)))
            NBS.find_element(By.XPATH, submit_button_path).click()
            NBS.read_address()
            NBS.set_state('M')
            NBS.set_country('UNITED S')
            if not NBS.county and NBS.city:
                NBS.county = NBS.county_lookup(NBS.city, 'Maine')
                NBS.write_county()
            if not NBS.zip_code and NBS.street and NBS.city:
                NBS.zip_code = NBS.zip_code_lookup(NBS.street, NBS.city, 'ME')
                NBS.write_zip()
            NBS.check_ethnicity()
            NBS.check_race()
            NBS.patient_id = NBS.ReadPatientID()
            if not all([NBS.street, NBS.city, NBS.zip_code, NBS.county, NBS.ethnicity, NBS.unambiguous_race]):
                NBS.incomplete_address_log.append(NBS.ReadPatientID())
                body = f"A new investigation has been created for patient {NBS.ReadPatientID()}, but they are missing demographic information. The investigation has been left open for manual review."
                NBS.send_smtp_email("chloe.manchester@maine.gov", 'ERROR REPORT: NBSbot(Hepatitis ELR Review) AKA Audrey Hepbot', body, 'Hepatitis Investigation Missing Demographic Info email')
            NBS.GoToCaseInfo()
            #NBS.set_investigation_status_closed()
            investigation_status_down_arrow = '//*[@id="NBS_UI_19"]/tbody/tr[4]/td[2]/img'
            #set this to option[2] for open or option[1] for closed
            if len(NBS.incomplete_address_log) > 0: 
                closed_option = '//*[@id="INV109"]/option[2]' 
            else:
                closed_option = '//*[@id="INV109"]/option[1]' 
            WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.element_to_be_clickable((By.XPATH, investigation_status_down_arrow)))
            NBS.find_element(By.XPATH, investigation_status_down_arrow).click()
            WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.element_to_be_clickable((By.XPATH, closed_option)))
            NBS.find_element(By.XPATH, closed_option).click()
            NBS.set_state_case_id()
            NBS.set_county_and_state_report_dates(PH_report_date)
            #Reporting organization is automatically filled in
            
            #set reporting source type
            WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.element_to_be_clickable((By.XPATH, '//*[@id="NBS_UI_23"]/tbody/tr[1]/td[2]/img')))
            NBS.find_element(By.XPATH, '//*[@id="NBS_UI_23"]/tbody/tr[1]/td[2]/img').click()
            
            #Set reporting source to Laboratory
            WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.element_to_be_clickable((By.XPATH, '//*[@id="INV112"]/option[15]')))
            NBS.find_element(By.XPATH, '//*[@id="INV112"]/option[15]').click()
            
            #set case status
            case_status_path = '//*[@id="NBS_UI_2"]/tbody/tr[5]/td[2]/input'
            
            NBS.find_element(By.XPATH, case_status_path).send_keys(Keys.CONTROL+'a')
            if test_type != "Antibody":
                WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.presence_of_element_located((By.XPATH, case_status_path)))
                NBS.find_element(By.XPATH, case_status_path).send_keys("Confirmed")
                #set confirmation method to laboratory confirmed
                WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.element_to_be_clickable((By.XPATH, '//*[@id="INV161"]/option[6]')))
                NBS.find_element(By.XPATH, '//*[@id="INV161"]/option[6]').click()
            elif test_type == "Antibody":
                WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.presence_of_element_located((By.XPATH, case_status_path)))
                NBS.find_element(By.XPATH, case_status_path).send_keys("Probable")
                #set confirmation method to lab report
                WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.element_to_be_clickable((By.XPATH, '//*[@id="INV161"]/option[7]')))
                NBS.find_element(By.XPATH, '//*[@id="INV161"]/option[7]').click()
            
            NBS.set_confirmation_date()
            
            NBS.write_general_comment(f'Created investigation from lab {event_id}. -nbsbot {NBS.now_str}')
            
            #add in lab info
            WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.element_to_be_clickable((By.XPATH, '//*[@id="tabs0head2"]')))
            NBS.find_element(By.XPATH, '//*[@id="tabs0head2"]').click()
            if test_type == "Antibody" or test_type == "Antigen":
                WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.presence_of_element_located((By.XPATH, '//*[@id="LP38332_0_DT"]')))
                NBS.find_element(By.XPATH, '//*[@id="LP38332_0_DT"]').send_keys(lab_date.strftime('%m/%d/%Y'))
                WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.presence_of_element_located((By.XPATH, '//*[@id="NBS_INV_HEP_UI_8"]/tbody/tr[23]/td[2]/input')))
                NBS.find_element(By.XPATH, '//*[@id="NBS_INV_HEP_UI_8"]/tbody/tr[23]/td[2]/input').send_keys("Positive")
            elif test_type == "RNA":
                WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.presence_of_element_located((By.XPATH, '//*[@id="LP38335_3_DT"]')))
                NBS.find_element(By.XPATH, '//*[@id="LP38335_3_DT"]').send_keys(lab_date.strftime('%m/%d/%Y'))
                WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.presence_of_element_located((By.XPATH, '//*[@id="NBS_INV_HEP_UI_8"]/tbody/tr[28]/td[2]/input')))
                NBS.find_element(By.XPATH, '//*[@id="NBS_INV_HEP_UI_8"]/tbody/tr[28]/td[2]/input').send_keys("Positive")
                if Genotype_test  is not None:
                    WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.presence_of_element_located((By.XPATH, '//*[@id="ME121009"]')))
                    NBS.find_element(By.XPATH, '//*[@id="ME121009"]').send_keys(lab_date.strftime('%m/%d/%Y'))
                    WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.presence_of_element_located((By.XPATH, '//*[@id="NBS_INV_HEP_UI_8"]/tbody/tr[30]/td[2]/input')))
                    NBS.find_element(By.XPATH, '//*[@id="NBS_INV_HEP_UI_8"]/tbody/tr[30]/td[2]/input').send_keys("Yes")
                    if resulted_test_table["Coded Result / Organism Name"].iloc[0] != "":
                        print(f"fgen: {genotype}")
                        if pd.isna(resulted_test_table["Coded Result / Organism Name"].str.extract(r'(\d+[A-Za-z])').loc[0,0]):
                            genotype = resulted_test_table["Coded Result / Organism Name"].str.extract(r'(\d+)').loc[0,0]
                        elif not pd.isna(resulted_test_table["Coded Result / Organism Name"].str.extract(r'(\d+[A-Za-z])').loc[0,0]):
                            genotype = resulted_test_table["Coded Result / Organism Name"].str.extract(r'(\d+[A-Za-z])').loc[0,0]
                    elif resulted_test_table["Text Result"].iloc[0] != "":
                        print(f"sgen: {genotype}")
                        if pd.isna(resulted_test_table["Text Result"].str.extract(r'(\d+[A-Za-z])').loc[0,0]):
                            genotype = resulted_test_table["Text Result"].str.extract(r'(\d+)').loc[0,0]
                        elif not pd.isna(resulted_test_table["Text Result"].str.extract(r'(\d+[A-Za-z])').loc[0,0]):
                            genotype = resulted_test_table["Text Result"].str.extract(r'(\d+[A-Za-z])').loc[0,0]
                    print(f"gen: {genotype}")
                    if genotype is not None:
                        NBS.find_element(By.XPATH, '//*[@id="ME121011"]').send_keys(genotype)
            elif test_type == "Genotype":
                WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.presence_of_element_located((By.XPATH, '//*[@id="ME121009"]')))
                NBS.find_element(By.XPATH, '//*[@id="ME121009"]').send_keys(lab_date.strftime('%m/%d/%Y'))
                WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.presence_of_element_located((By.XPATH, '//*[@id="NBS_INV_HEP_UI_8"]/tbody/tr[30]/td[2]/input')))
                NBS.find_element(By.XPATH, '//*[@id="NBS_INV_HEP_UI_8"]/tbody/tr[30]/td[2]/input').send_keys("Yes")
                if resulted_test_table["Coded Result / Organism Name"].iloc[0] != "":
                    if pd.isna(resulted_test_table["Coded Result / Organism Name"].str.extract(r'(\d+[A-Za-z])').loc[0,0]):
                        genotype = resulted_test_table["Coded Result / Organism Name"].str.extract(r'(\d+)').loc[0,0]
                    elif not pd.isna(resulted_test_table["Coded Result / Organism Name"].str.extract(r'(\d+[A-Za-z])').loc[0,0]):
                        genotype = resulted_test_table["Coded Result / Organism Name"].str.extract(r'(\d+[A-Za-z])').loc[0,0]
                elif resulted_test_table["Text Result"].iloc[0] != "":
                    if pd.isna(resulted_test_table["Text Result"].str.extract(r'(\d+[A-Za-z])').loc[0,0]):
                        genotype = resulted_test_table["Text Result"].str.extract(r'(\d+)').loc[0,0]
                    elif not pd.isna(resulted_test_table["Text Result"].str.extract(r'(\d+[A-Za-z])').loc[0,0]):
                        genotype = resulted_test_table["Text Result"].str.extract(r'(\d+[A-Za-z])').loc[0,0]
                elif resulted_test_table["Numeric Result"].iloc[0] != "":
                    if type(resulted_test_table["Numeric Result"].iloc[0]) == float:
                        genotype = int(resulted_test_table["Numeric Result"].iloc[0])
                    elif pd.isna(resulted_test_table["Numeric Result"].str.extract(r'(\d+[A-Za-z])').loc[0,0]):
                        genotype = resulted_test_table["Numeric Result"].str.extract(r'(\d+)').loc[0,0]
                    elif not pd.isna(resulted_test_table["Numeric Result"].str.extract(r'(\d+[A-Za-z])').loc[0,0]):
                        genotype = resulted_test_table["Numeric Result"].str.extract(r'(\d+[A-Za-z])').loc[0,0]
                if genotype is not None:
                    NBS.find_element(By.XPATH, '//*[@id="ME121011"]').send_keys(genotype)
                
            
            if alt_lab is not None:
                WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.presence_of_element_located((By.XPATH, '//*[@id="1742_6"]')))
                NBS.find_element(By.XPATH, '//*[@id="1742_6"]').send_keys(re.findall(r'\b\d+\b',alt_lab["Test Results"].iloc[0])[0])
                WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.presence_of_element_located((By.XPATH, '//*[@id="INV826"]')))
                NBS.find_element(By.XPATH, '//*[@id="INV826"]').send_keys(re.findall(r'\b\d{2}/\d{2}/\d{4}\b',lab_report_table["Date Received"].iloc[0])[0])
                try:
                    ref_range = re.findall(r'(\d+-\d+)',alt_lab["Test Results"].iloc[0])
                    upper_limit_text = ref_range[0]
                except IndexError:
                    ref_range = re.findall(r'(\d+ - \d+)',alt_lab["Test Results"].iloc[0])
                    upper_limit_text = ref_range[0]
                upper_limit = upper_limit_text.rsplit('-',1)[-1]
                WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.presence_of_element_located((By.XPATH, '//*[@id="INV827"]')))
                NBS.find_element(By.XPATH, '//*[@id="INV827"]').send_keys(upper_limit)
                
            #WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.element_to_be_clickable((By.XPATH, '//*[@id="SubmitTop"]')))
            #NBS.find_element(By.XPATH, '//*[@id="SubmitTop"]').click()
            time.sleep(3)
            NBS.click_submit()
            
            try:
                NBS.check_jurisdiction()
            except NoSuchElementException:
                WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.element_to_be_clickable((By.XPATH, '//*[@id="SubmitTop"]')))
                NBS.find_element(By.XPATH, '//*[@id="SubmitTop"]').click()
                NBS.check_jurisdiction()
            if len(NBS.incomplete_address_log) > 0: 
                pass
            else:
                NBS.create_notification() 
            #in covidlabreview, changed transfer_ownership_path to [4] instead of [3]
            print("Create Investigation: " + condition)
            what_do.append("Create Investigation: " + condition)
        elif update_status == True and create_inv == False:
            #update investigation status
            #go to events 
            WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.element_to_be_clickable((By.XPATH, '//*[@id="doc3"]/div[1]/a')))
            NBS.find_element(By.XPATH,'//*[@id="doc3"]/div[1]/a').click()
            #click on investigation date
            #WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.element_to_be_clickable((By.XPATH, f"//a[contains(text(),'{inv_date.strftime('%m/%d/%Y')}')]")))
            #NBS.find_element(By.XPATH,f"//a[contains(text(),'{inv_date.strftime('%m/%d/%Y')}')]").click()
            
            results = NBS.find_elements(By.XPATH,f"//a[contains(text(),'{inv_date.strftime('%m/%d/%Y')}')]")
            for result in results:
                try:
                    result.click()
                except (ElementNotInteractableException, StaleElementReferenceException) as e:
                    pass
            #click edit 
            WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.element_to_be_clickable((By.XPATH, '//*[@id="delete"]')))
            NBS.find_element(By.XPATH, '//*[@id="delete"]').click()
            #click okay
            try:
                WebDriverWait(NBS, 10).until(EC.alert_is_present())
                NBS.switch_to.alert.accept()
                time.sleep(5)
            except TimeoutException:
                pass
            #click case info tab 
            #WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.element_to_be_clickable((By.XPATH, '//*[@id="tabs0head1"]')))
            #NBS.find_element(By.XPATH, '//*[@id="tabs0head1"]').click()
            NBS.GoToCaseInfo()
            time.sleep(1)
            
            #change confirmation method to laboratory confirmed
            WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.element_to_be_clickable((By.XPATH, '//*[@id="INV161"]/option[6]')))
            lab_conf = NBS.find_element(By.XPATH, '//*[@id="INV161"]/option[6]')
            if lab_conf.is_selected():
                pass
            else:
                lab_conf.click()
            
            #update confirmation date
            WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.presence_of_element_located((By.XPATH, '//*[@id="INV162"]')))
            NBS.find_element(By.XPATH, '//*[@id="INV162"]').clear()
            NBS.find_element(By.XPATH, '//*[@id="INV162"]').send_keys(lab_date.strftime('%m/%d/%Y'))
            
            #Enter confirmed
            WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.element_to_be_clickable((By.XPATH, '//*[@id="NBS_UI_2"]/tbody/tr[5]/td[2]/img')))
            NBS.find_element(By.XPATH, '//*[@id="NBS_UI_2"]/tbody/tr[5]/td[2]/img').click()
            WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.element_to_be_clickable((By.XPATH, '//*[@id="INV163"]/option[2]')))
            NBS.find_element(By.XPATH, '//*[@id="INV163"]/option[2]').click()
            
            WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.presence_of_element_located((By.XPATH, '//*[@id="bd"]/h1/table/tbody/tr[1]/td[1]/a')))
            inv_type_elem = NBS.find_element(By.XPATH, '//*[@id="bd"]/h1/table/tbody/tr[1]/td[1]/a')
            inv_type = inv_type_elem.text
            
            if test_condition == "Hepatitis B" and test_type in ("Antigen", "DNA", "RNA") and "acute" in inv_type and not_a_case == False:
                NBS.write_general_comment(f'\nNew HBsAg+, HBeAg+, HBV DNA+ within 6 months. Case classification is changed from probable to confirmed. Lab Id: {event_id} -nbsbot {NBS.now_str}')
            if test_condition == "Hepatitis B" and test_type in ("Antigen", "DNA", "RNA") and "Chronic" in inv_type and not_a_case == False:
                NBS.write_general_comment(f'\nNew HBsAg+, HBeAg+, HBV DNA+ 6 months or more apart. Case classification is changed from probable to confirmed. Lab Id: {event_id} -nbsbot {NBS.now_str}')
            if test_condition == "Hepatitis C" and test_type in ("Genotype", "RNA") and "acute" in inv_type and not_a_case == False:
                NBS.write_general_comment(f'\nNew hepatitis C NAAT within 1 year. Case classification is changed from probable to confirmed. Lab Id: {event_id} -nbsbot {NBS.now_str}')
            if test_condition == "Hepatitis C" and test_type in ("Genotype", "RNA") and "chronic" in inv_type and not_a_case == False:
                NBS.write_general_comment(f'\nNew hepatitis C NAAT. Case classification is changed from probable to confirmed. Lab Id: {event_id} -nbsbot {NBS.now_str}')
                
            if not_a_case:
                WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.element_to_be_clickable((By.XPATH, '//*[@id="NBS_UI_2"]/tbody/tr[5]/td[2]/img')))
                NBS.find_element(By.XPATH, '//*[@id="NBS_UI_2"]/tbody/tr[5]/td[2]/img').click()
                WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.element_to_be_clickable((By.XPATH, '//*[@id="INV163"]/option[2]')))
                NBS.find_element(By.XPATH, '//*[@id="INV163"]/option[3]').click()
                NBS.write_general_comment(f'\nNegative Hepatitis C RNA test for a patient with a probable Hepatitis C investigation. Case classification is changed from probable to Not a Case. Lab Id: {event_id} -nbsbot {NBS.now_str}')
            #add in lab info
            #Do we want to overwrite if there is already a test? No
            NBS.find_element(By.XPATH, '//*[@id="tabs0head2"]').click()
            if test_type == "Antibody" :
                if test_condition == "Hepatitis B":
                    if any(x in str(resulted_test_table["Resulted Test"]) for x in ["surface", "Surface", "SURFACE"]): 
                        date_path = '//*[@id="ME117002"]'
                        text_path = '//*[@id="NBS_INV_HEP_UI_8"]/tbody/tr[18]/td[2]/input'
                    elif any(x in str(resulted_test_table["Resulted Test"]) for x in ["e Ab", "e ab", "E Ab", "E ab", "e An", "e an", "E An", "E an"]): 
                        date_path = '//*[@id="ME121002"]'
                        text_path = '//*[@id="NBS_INV_HEP_UI_8"]/tbody/tr[20]/td[2]/input'
                    elif any(x in str(resulted_test_table["Resulted Test"]) for x in ["IgM", "IGM", "igm"]): 
                        date_path = '//*[@id="LP38325_4_DT"]'
                        text_path = '//*[@id="NBS_INV_HEP_UI_8"]/tbody/tr[12]/td[2]/input'
                    else:
                        date_path = '//*[@id="LP38323_9_DT"]'
                        text_path = '//*[@id="NBS_INV_HEP_UI_8"]/tbody/tr[10]/td[2]/input'
                elif test_condition == "Hepatitis C":
                    date_path = '//*[@id="LP38332_0_DT"]'
                    text_path = '//*[@id="NBS_INV_HEP_UI_8"]/tbody/tr[23]/td[2]/input'
                WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.presence_of_element_located((By.XPATH, date_path)))
                date_elem = NBS.find_element(By.XPATH, date_path)
                WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.presence_of_element_located((By.XPATH, text_path)))
                text_elem = NBS.find_element(By.XPATH, text_path)
                if date_elem.get_attribute("value") == '' and text_elem.get_attribute("value") == '':
                    NBS.find_element(By.XPATH, date_path).send_keys(lab_date.strftime('%m/%d/%Y'))
                    NBS.find_element(By.XPATH, text_path).send_keys("Positive")
            elif test_type == "Antigen":
                if any(x in str(resulted_test_table["Resulted Test"]) for x in ["surface", "Surface", "SURFACE"]): 
                    date_path = '//*[@id="LP38331_2_DT"]'
                    text_path = '//*[@id="NBS_INV_HEP_UI_8"]/tbody/tr[8]/td[2]/input'
                elif any(x in str(resulted_test_table["Resulted Test"]) for x in ["e Ag", "e ag", "E Ag", "E ag", "e An", "e an", "E An", "E an"]): 
                    date_path = '//*[@id="LP38329_6_DT"]'
                    text_path = '//*[@id="NBS_INV_HEP_UI_8"]/tbody/tr[16]/td[2]/input'
                WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.presence_of_element_located((By.XPATH, date_path)))
                date_elem = NBS.find_element(By.XPATH, date_path)
                WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.presence_of_element_located((By.XPATH, text_path)))
                text_elem = NBS.find_element(By.XPATH, text_path)
                if date_elem.get_attribute("value") == '' and text_elem.get_attribute("value") == '':
                    NBS.find_element(By.XPATH, date_path).send_keys(lab_date.strftime('%m/%d/%Y'))
                    NBS.find_element(By.XPATH, text_path).send_keys("Positive")
            elif test_type == "RNA":
                WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.presence_of_element_located((By.XPATH, '//*[@id="LP38335_3_DT"]')))
                date_elem = NBS.find_element(By.XPATH, '//*[@id="LP38335_3_DT"]')
                WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.presence_of_element_located((By.XPATH, '//*[@id="NBS_INV_HEP_UI_8"]/tbody/tr[28]/td[2]/input')))
                text_elem = NBS.find_element(By.XPATH, '//*[@id="NBS_INV_HEP_UI_8"]/tbody/tr[28]/td[2]/input')
                if date_elem.get_attribute("value") == '' and text_elem.get_attribute("value") == '':
                    NBS.find_element(By.XPATH, '//*[@id="LP38335_3_DT"]').send_keys(lab_date.strftime('%m/%d/%Y'))
                    if not_a_case == False:
                        NBS.find_element(By.XPATH, '//*[@id="NBS_INV_HEP_UI_8"]/tbody/tr[28]/td[2]/input').send_keys("Positive")
                    elif not_a_case:
                        NBS.find_element(By.XPATH, '//*[@id="NBS_INV_HEP_UI_8"]/tbody/tr[28]/td[2]/input').send_keys("Negative")
            elif test_type == "DNA":
                WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.presence_of_element_located((By.XPATH, '//*[@id="LP38320_5_DT"]')))
                date_elem = NBS.find_element(By.XPATH, '//*[@id="LP38320_5_DT"]')
                WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.presence_of_element_located((By.XPATH, '//*[@id="NBS_INV_HEP_UI_8"]/tbody/tr[14]/td[2]/input')))
                text_elem = NBS.find_element(By.XPATH, '//*[@id="NBS_INV_HEP_UI_8"]/tbody/tr[14]/td[2]/input')
                if date_elem.get_attribute("value") == '' and text_elem.get_attribute("value") == '':
                    NBS.find_element(By.XPATH, '//*[@id="LP38320_5_DT"]').send_keys(lab_date.strftime('%m/%d/%Y'))
                    NBS.find_element(By.XPATH, '//*[@id="NBS_INV_HEP_UI_8"]/tbody/tr[14]/td[2]/input').send_keys("Positive")
            elif test_type == "Genotype":
                WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.presence_of_element_located((By.XPATH, '//*[@id="ME121009"]')))
                date_elem = NBS.find_element(By.XPATH, '//*[@id="ME121009"]')
                WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.presence_of_element_located((By.XPATH, '//*[@id="NBS_INV_HEP_UI_8"]/tbody/tr[30]/td[2]/input')))
                text_elem = NBS.find_element(By.XPATH, '//*[@id="NBS_INV_HEP_UI_8"]/tbody/tr[30]/td[2]/input')
                if date_elem.get_attribute("value") == '' and text_elem.get_attribute("value") == '':
                    NBS.find_element(By.XPATH, '//*[@id="ME121009"]').send_keys(lab_date.strftime('%m/%d/%Y'))
                    #WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.presence_of_element_located((By.XPATH, '//*[@id="NBS_INV_HEP_UI_8"]/tbody/tr[30]/td[2]/input')))
                    NBS.find_element(By.XPATH, '//*[@id="NBS_INV_HEP_UI_8"]/tbody/tr[30]/td[2]/input').send_keys("Yes")
                    if resulted_test_table["Coded Result / Organism Name"].iloc[0] != "":
                        if pd.isna(resulted_test_table["Coded Result / Organism Name"].str.extract(r'(\d+[A-Za-z])').loc[0,0]):
                            genotype = resulted_test_table["Coded Result / Organism Name"].str.extract(r'(\d+)').loc[0,0]
                        elif not pd.isna(resulted_test_table["Coded Result / Organism Name"].str.extract(r'(\d+[A-Za-z])').loc[0,0]):
                            genotype = resulted_test_table["Coded Result / Organism Name"].str.extract(r'(\d+[A-Za-z])').loc[0,0]
                    elif resulted_test_table["Text Result"].iloc[0] != "":
                        if pd.isna(resulted_test_table["Text Result"].str.extract(r'(\d+[A-Za-z])').loc[0,0]):
                            genotype = resulted_test_table["Text Result"].str.extract(r'(\d+)').loc[0,0]
                        elif not pd.isna(resulted_test_table["Text Result"].str.extract(r'(\d+[A-Za-z])').loc[0,0]):
                            genotype = resulted_test_table["Text Result"].str.extract(r'(\d+[A-Za-z])').loc[0,0]
                    if genotype is not None:
                        NBS.find_element(By.XPATH, '//*[@id="ME121011"]').send_keys(genotype)
            if alt_lab is not None:
                WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.presence_of_element_located((By.XPATH, '//*[@id="1742_6"]')))
                text_elem = NBS.find_element(By.XPATH, '//*[@id="1742_6"]')
                WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.presence_of_element_located((By.XPATH, '//*[@id="INV826"]')))
                date_elem = NBS.find_element(By.XPATH, '//*[@id="INV826"]')
                if date_elem.get_attribute("value") == '' and text_elem.get_attribute("value") == '':
                    NBS.find_element(By.XPATH, '//*[@id="1742_6"]').send_keys(re.findall(r'\b\d+\b',alt_lab["Test Results"].iloc[0])[0])
                    NBS.find_element(By.XPATH, '//*[@id="INV826"]').send_keys(re.findall(r'\b\d{2}/\d{2}/\d{4}\b',lab_report_table["Date Received"].iloc[0])[0])
                    try:
                        ref_range = re.findall(r'(\d+-\d+)',alt_lab["Test Results"].iloc[0])
                        upper_limit_text = ref_range[0]
                    except IndexError:
                        ref_range = re.findall(r'(\d+ - \d+)',alt_lab["Test Results"].iloc[0])
                        upper_limit_text = ref_range[0]
                    upper_limit = upper_limit_text.rsplit('-',1)[-1]
                    WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.presence_of_element_located((By.XPATH, '//*[@id="INV827"]')))
                    NBS.find_element(By.XPATH, '//*[@id="INV827"]').send_keys(upper_limit)
            #click on submit
            WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.element_to_be_clickable((By.XPATH, '//*[@id="SubmitBottom"]')))
            NBS.find_element(By.XPATH, '//*[@id="SubmitBottom"]').click()
            associate = True
            print("Update Status")
            
            #go back to patient page
            WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.element_to_be_clickable((By.XPATH, '//*[@id="bd"]/div[1]/a')))
            NBS.find_element(By.XPATH, '//*[@id="bd"]/div[1]/a').click()
            
            #go to lab
            try:
                anc = NBS.find_element(By.XPATH,f"//td[contains(text(),'{event_id.split()[0]}')]/../td/a") #possible index error
                anc.click()
            except ElementNotInteractableException:
                WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.element_to_be_clickable((By.XPATH, '//*[@id="tabs0head0"]')))
                NBS.find_element(By.XPATH, '//*[@id="tabs0head0"]').click()
                anc = NBS.find_element(By.XPATH,f"//td[contains(text(),'{event_id.split()[0]}')]/../td/a") #possible index error
                anc.click()
                
        #update investigation to acute if ALT > 200 and there is a closed chronic Hep C investigation, update if there is a Hep acute and there is a negative RNA test
        if update_inv_type == True:
            #change condition status to acute
            #go to events 
            WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.element_to_be_clickable((By.XPATH, '//*[@id="doc3"]/div[1]/a')))
            NBS.find_element(By.XPATH,'//*[@id="doc3"]/div[1]/a').click()
            #click into investigation
            WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.element_to_be_clickable((By.XPATH, f"//a[contains(text(),'{inv_date.strftime('%m/%d/%Y')}')]")))
            NBS.find_element(By.XPATH,f"//a[contains(text(),'{inv_date.strftime('%m/%d/%Y')}')]").click()
            #click change condition
            WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.element_to_be_clickable((By.XPATH, '//*[@id="changeCond"]')))
            NBS.find_element(By.XPATH, '//*[@id="changeCond"]').click()
            #navigate to the new window
            original_window = NBS.window_handles[0] #possible index error
            new_window = NBS.window_handles[1] #possible index error
            NBS.switch_to.window(new_window)
            #Enter either Hepatitis B/C, acute
            WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.presence_of_element_located((By.XPATH, '//*[@id="subsect_chng_cond"]/tbody/tr[2]/td[2]/input')))
            NBS.find_element(By.XPATH, '//*[@id="subsect_chng_cond"]/tbody/tr[2]/td[2]/input').send_keys(condition)
            #click submit
            WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.element_to_be_clickable((By.XPATH, '//*[@id="popupButtonBottom"]/input[1]')))
            NBS.find_element(By.XPATH, '//*[@id="popupButtonBottom"]/input[1]').click()
            #click okay
            WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.element_to_be_clickable((By.XPATH, '//*[@id="confirmationText"]/tbody/tr[11]/td/input[1]')))
            NBS.find_element(By.XPATH, '//*[@id="confirmationText"]/tbody/tr[11]/td/input[1]').click()
            #go back to original window
            NBS.switch_to.window(original_window)
            #leave comment
            if condition == "Hepatitis B, acute":
                WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.presence_of_element_located((By.XPATH, '//*[@id="DEM196"]')))
                NBS.find_element(By.XPATH, '//*[@id="DEM196"]').send_keys(f'\nNew IgM anti-HBc+ within 6 months. Case classification is changed from probable chronic to confirmed acute. -nbsbot Lab Id: {event_id} -nbsbot {NBS.now_str}')
                #NBS.write_general_comment(f'\nNew IgM anti-HBc+ within 6 months. Case classification is changed from probable chronic to confirmed acute. -nbsbot Lab Id: {lab_report_table["Event ID"].iloc[0]} -nbsbot {NBS.now_str}')
                '//*[@id="DEM196"]'
            elif condition == "Hepatitis C, acute":
                WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.presence_of_element_located((By.XPATH, '//*[@id="DEM196"]')))
                NBS.find_element(By.XPATH, '//*[@id="DEM196"]').send_keys(f'\nNew ALT lab >200 within 3 months. Case classification is changed from chronic to confirmed acute. -nbsbot Lab Id: {event_id} -nbsbot {NBS.now_str}')
                
            #set investigation status to closed
            investigation_status_down_arrow = '//*[@id="NBS_UI_19"]/tbody/tr[4]/td[2]/img'
            closed_option = '//*[@id="INV109"]/option[1]' 
            WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.element_to_be_clickable((By.XPATH, investigation_status_down_arrow)))
            NBS.find_element(By.XPATH, investigation_status_down_arrow).click()
            WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.element_to_be_clickable((By.XPATH, closed_option)))
            NBS.find_element(By.XPATH, closed_option).click()
            #set case status to confirmed
            WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.presence_of_element_located((By.XPATH, case_status_path)))
            NBS.find_element(By.XPATH, case_status_path).send_keys("Confirmed")
            
            #go to hepatitis core tab
            WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.element_to_be_clickable((By.XPATH, '//*[@id="tabs0head2"]')))
            NBS.find_element(By.XPATH, '//*[@id="tabs0head2"]').click()
            
            #fill in lab info
            if test_type == "Antigen":
                if any(x in str(resulted_test_table["Resulted Test"]) for x in ["surface", "Surface", "SURFACE"]): 
                    date_path = '//*[@id="LP38331_2_DT"]'
                    text_path = '//*[@id="NBS_INV_HEP_UI_8"]/tbody/tr[8]/td[2]/input'
                elif any(x in str(resulted_test_table["Resulted Test"]) for x in ["e Ag", "e ag", "E Ag", "E ag", "e An", "e an", "E An", "E an"]): 
                    date_path = '//*[@id="LP38329_6_DT"]'
                    text_path = '//*[@id="NBS_INV_HEP_UI_8"]/tbody/tr[16]/td[2]/input'
                WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.presence_of_element_located((By.XPATH, date_path)))
                date_elem = NBS.find_element(By.XPATH, date_path)
                WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.presence_of_element_located((By.XPATH, text_path)))
                text_elem = NBS.find_element(By.XPATH, text_path)
                if date_elem.get_attribute("value") == '' and text_elem.get_attribute("value") == '':
                    NBS.find_element(By.XPATH, date_path).send_keys(lab_date.strftime('%m/%d/%Y'))
                    NBS.find_element(By.XPATH, text_path).send_keys("Positive")
            elif test_type == "Alanine":
                WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.presence_of_element_located((By.XPATH, '//*[@id="1742_6"]')))
                text_elem = NBS.find_element(By.XPATH, '//*[@id="1742_6"]')
                WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.presence_of_element_located((By.XPATH, '//*[@id="INV826"]')))
                date_elem = NBS.find_element(By.XPATH, '//*[@id="INV826"]')
                if date_elem.get_attribute("value") == '' and text_elem.get_attribute("value") == '':
                    if resulted_test_table["Numeric Result"].iloc[0] != "": #possible index error
                        NBS.find_element(By.XPATH, '//*[@id="1742_6"]').send_keys(resulted_test_table["Numeric Result"].iloc[0])  #possible index error
                    elif resulted_test_table["Text Result"].iloc[0] != "":  #possible index error  
                        NBS.find_element(By.XPATH, '//*[@id="1742_6"]').send_keys(resulted_test_table["Text Result"].iloc[0]) #possible index error
                    NBS.find_element(By.XPATH, '//*[@id="INV826"]').send_keys(lab_date.strftime('%m/%d/%Y'))
                    
                    WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.presence_of_element_located((By.XPATH, '//*[@id="INV827"]')))
                    NBS.find_element(By.XPATH, '//*[@id="INV827"]').send_keys(resulted_test_table["Ref Range To"].iloc[0]) #possible index error
                    
            #click submit
            WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.element_to_be_clickable((By.XPATH, '//*[@id="SubmitTop"]')))
            NBS.find_element(By.XPATH, '//*[@id="SubmitTop"]').click()
            print("Update investigation to acute")
            what_do.append("Update investigation to acute")
        #associate with investigation
        #click on associate button
        if associate == True:
            WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.element_to_be_clickable((By.XPATH, '//*[@id="doc3"]/div[2]/table/tbody/tr/td[2]/input[2]')))
            NBS.find_element(By.XPATH, '//*[@id="doc3"]/div[2]/table/tbody/tr/td[2]/input[2]').click()
            time.sleep(3)
            #identify investigation, name and date? maybe index from investigations table
            inv_to_assoc = investigation_table[investigation_table["Condition"].str.contains(test_condition)]
            for i in inv_to_assoc.index:
                inv_ind = i+1
                WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.element_to_be_clickable((By.XPATH, f"//*[@id='parent']/tbody/tr[{inv_ind}]/td[1]/div/input")))
                NBS.find_element(By.XPATH, f"//*[@id='parent']/tbody/tr[{inv_ind}]/td[1]/div/input").click()
            #click submit
            WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.element_to_be_clickable((By.XPATH, '//*[@id="Submit"]')))
            NBS.find_element(By.XPATH, '//*[@id="Submit"]').click()
            print("Associate with Investigation")
            if update_status == True:
                what_do.append("Update and Associate with Investigation")
            else:
                what_do.append("Associate with Investigation")
        if send_alt_email == True:
            body = f"An Alanine Aminotransferase ELR needs to be manually reviewed. The lab ID is {event_id}"
            NBS.send_smtp_email("chloe.manchester@maine.gov", 'ERROR REPORT: NBSbot(Hepatitis ELR Review) AKA Audrey Hepbot', body, 'Hepatitis Manual Review email')
            what_do.append("Send ALT Email")
        if send_inv_email == True:
            body = f"A patient has multiple Hepatitis investigations of the same condition with a probable/confirmed status. {existing_investigations}"
            NBS.send_smtp_email("chloe.manchester@maine.gov", 'ERROR REPORT: NBSbot(Hepatitis ELR Review) AKA Audrey Hepbot', body, 'Hepatitis Investigation Review email')
            what_do.append("Send Multiple Investigation Email")
        NBS.go_to_home()
        time.sleep(3)
        
    if len(merges) >= 1:
        # Patient Ids: {merge_ids}
        body = f"Potential merges have been identified for patients associated with the following ELRs: {merges}."
        NBS.send_smtp_email("disease.reporting@maine.gov", 'Merge Report: NBSbot(Hepatitis ELR Review) AKA Audrey Hepbot', body, 'Hepatitis Merge Review email')

    bot_act = pd.DataFrame(
        {'Lab ID': reviewed_ids,
        'Action': what_do
        })
    bot_act.to_excel(f"Hepatitis_bot_activity_{datetime.now().date().strftime('%m_%d_%Y')}.xlsx")

if __name__ == '__main__':
    start_audrey()
