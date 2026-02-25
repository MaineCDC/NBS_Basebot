
from tqdm import tqdm
import time
import traceback
from selenium.webdriver.common.alert import Alert
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import ElementNotInteractableException
from selenium.common.exceptions import StaleElementReferenceException
import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)
import pandas as pd
pd.options.mode.chained_assignment = None
from bs4 import BeautifulSoup
from datetime import datetime
from io import StringIO
import re
import numpy as np
from dateutil.relativedelta import relativedelta
from pandas._libs.tslibs.parsing import DateParseError
from epiweeks import Week
from dotenv import load_dotenv
import os
from decorator import error_handle
import smtplib, ssl
from email.message import EmailMessage

def generator():
    while True:
        yield

reviewed_ids = []
what_do = []
is_in_production = os.getenv('ENVIRONMENT', 'production') != 'development'


@error_handle
def start_CovidEcr(username, passcode):
    
    from .CovidEcr import COVIDECR
    

    load_dotenv()
    NBS = COVIDECR(production=is_in_production)
    if is_in_production:
        print("Production Environment")
    else:
        print("Development Environment")
    NBS.get_credentials()
    NBS.log_in()
    attempt_counter = 0
    limit = 40
    loop = tqdm(generator())
    for _ in loop:
        if loop.n == limit:
            break
        partial_link = 'Documents Requiring Review'
        WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.element_to_be_clickable((By.PARTIAL_LINK_TEXT, partial_link)))
        NBS.find_element(By.PARTIAL_LINK_TEXT, partial_link).click()
        time.sleep(1)
        
        #Sort review queue so that only case reports are listed
        clear_filter_path = '//*[@id="removeFilters"]/table/tbody/tr/td[2]/a'
        document_path = '/html/body/div[2]/form/div/table[2]/tbody/tr/td/table/thead/tr/th[2]/img'
        
        #clear all filters
        WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.element_to_be_clickable((By.XPATH, clear_filter_path)))
        NBS.find_element(By.XPATH, clear_filter_path).click()
        time.sleep(5)
        
        #open document_path dropdown menu
        WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.presence_of_element_located((By.XPATH, document_path)))
        WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.element_to_be_clickable((By.XPATH, document_path)))
        NBS.find_element(By.XPATH, document_path).click()
        time.sleep(1)
        
        #clear checkboxes
        WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.element_to_be_clickable((By.XPATH, '/html/body/div[2]/form/div/table[2]/tbody/tr/td/table/thead/tr/th[2]/div/label[2]')))
        NBS.find_element(By.XPATH,'/html/body/div[2]/form/div/table[2]/tbody/tr/td/table/thead/tr/th[2]/div/label[2]').click()
        time.sleep(1)
        
        #select Case Reports
        try:
            results = NBS.find_elements(By.XPATH,"//label[contains(text(),'Case')]")
            for result in results:
                result.click()
        except (NoSuchElementException, ElementNotInteractableException) as e:
            pass
        time.sleep(1)
        
        #click ok
        try:
            WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.element_to_be_clickable((By.XPATH, '/html/body/div[2]/form/div/table[2]/tbody/tr/td/table/thead/tr/th[2]/div/label[1]/input[1]')))
            NBS.find_element(By.XPATH,'/html/body/div[2]/form/div/table[2]/tbody/tr/td/table/thead/tr/th[2]/div/label[1]/input[1]').click()
        except NoSuchElementException:
            #click cancel and go back to home page to wait for more ELRs
            WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.element_to_be_clickable((By.XPATH, '/html/body/div[2]/form/div/table[2]/tbody/tr/td/table/thead/tr/th[2]/div/label[1]/input[2]')))
            NBS.find_element(By.XPATH,'/html/body/div[2]/form/div/table[2]/tbody/tr/td/table/thead/tr/th[2]/div/label[1]/input[2]').click()
            NBS.go_to_home()
            time.sleep(3)
            NBS.Sleep()
            #this wont work if we are not running the for loop to cycle through the queue,
            #comment out if not running the whole thing
            continue
        time.sleep(1)
        
        #sort chronologically, oldest first
        submit_date_path = '//*[@id="parent"]/thead/tr/th[3]/a'
        WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.element_to_be_clickable((By.XPATH, submit_date_path)))
        NBS.find_element(By.XPATH, submit_date_path).click()
        WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.element_to_be_clickable((By.XPATH, submit_date_path)))
        NBS.find_element(By.XPATH, submit_date_path).click()
        
        #Grab all ECRs in the queue to reference later. Grab the event ID so we can make sure that we
        #don't get stuck in a loop at the top of the queue if an ECR doesn't get cleared out of the queue
        
        #Grab the ECR table 
        review_queue_table_path = '//*[@id="parent"]'
        html = NBS.find_element(By.XPATH, review_queue_table_path).get_attribute('outerHTML')
        soup = BeautifulSoup(html, 'html.parser')
        review_queue_table = pd.read_html(StringIO(str(soup)))[0]
        review_queue_table.fillna('', inplace = True)
        #maybe change above '' to None
        
        #Check to see if we have looked at this ECR before by the local ID
        #Check to see if we have looked at this ELR before by the local ID
        i = 0
        try:
            while review_queue_table["Local ID"].iloc[i] in reviewed_ids:
                i += 1
        except IndexError:
            print("No IDs to review. Stopping...")
            break

        #grab the first local ID we haven't reviewed and append it to the list for later use 
        doc_id = review_queue_table["Local ID"].iloc[i]
        reviewed_ids.append(doc_id) 
        #identify the element that has the document ID to be reviewed and navigate to that Lab Report
        
        
        try:
            anc = NBS.find_element(By.XPATH,f"//td[contains(text(),'{doc_id}')]/../td/a")
        except NoSuchElementException:
            anc = NBS.find_element(By.XPATH,f"//font[contains(text(),'{doc_id}')]/../../td/a")
        anc.click()
        #grab from the results section, check for the various test names. Maybe use a while loop?
        
        results_table = None
        covid_results = None
        pos_covid_results = None
        cov_pos = False
        investigation_table = None
        inv_found = False
        
        try:
            html = NBS.find_element(By.XPATH, '//*[@id="xmlBlock"]/table[12]').get_attribute('outerHTML')
            soup = BeautifulSoup(html, 'html.parser')
            results_table = pd.read_html(StringIO(str(soup)))[0]
            covid_results = results_table[results_table["Lab Test Name"].str.contains("SARS|COVID|nCoV|qPCR (Rutgers)|Severe Acute Respiratory Syndrome")]
            pos_covid_results = covid_results[covid_results["Lab Test Result Value"].str.contains("Positive|Detected|Present|Reactive")]
            if len(pos_covid_results) > 0:
                cov_pos = True
        except NoSuchElementException:
            print("No results table found. Continuing to next lab.")
        except KeyError:
            try:
            # "qPCR (Rutgers)", "Severe Acute Respiratory Syndrome"
                tests = ["SARS", "COVID", "nCoV"]
                for test in tests:
                    #test_elem = NBS.find_element(By.XPATH, f'//*[@id="xmlBlock"]/ul[1]/li[contains(text(),{test})]/table[1]')
                    test_table_path = f'//*[@id="xmlBlock"]/ul[1]/li[contains(text(),{test})]/table[1]'
                    elems = NBS.find_elements(By.XPATH, test_table_path)
                    for elem in elems:
                        html = elem.get_attribute('outerHTML')
                        soup = BeautifulSoup(html, 'html.parser')
                        results_table = pd.read_html(StringIO(str(soup)))[0]
                        covid_results = results_table[results_table["Component"].str.contains("SARS|COVID|nCoV|qPCR (Rutgers)|Severe Acute Respiratory Syndrome")]
                        covid_results["Value"] = covid_results["Value"].astype(str)
                        pos_covid_results = covid_results[covid_results["Value"].str.contains("Positive|Detected|Present|Reactive")]
                        if len(pos_covid_results) > 0:
                            cov_pos = True
            except KeyError:
                pass
            if not cov_pos:
                NBS.go_to_home()
                what_do.append("No COVID results found. Continuing to next lab.")
                print("No COVID results found. Continuing to next lab.")
                time.sleep(3)
                continue
            
            #html = NBS.page_source
            #soup = BeautifulSoup(html, "html.parser")
            #for tag in soup.find_all("tr"):
                #if "SARS" in tag.text or "COVID" in tag.text or "nCoV"in tag.text or "qPCR (Rutgers)" in tag.text or "Severe Acute Respiratory Syndrome" in tag.text:
                    #print(tag.text)
                    #if "Detected" in tag.text or "Positive" in tag.text or "Reactive" in tag.text or " Present " in tag.text:
                        #print("True")
                        
        #Go to patient file
        WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.element_to_be_clickable((By.XPATH, '//*[@id="srtLink"]/div/a[1]')))
        NBS.find_element(By.XPATH, '//*[@id="srtLink"]/div/a[1]').click()
        
        #Go to events tab
        WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.element_to_be_clickable((By.XPATH, '//*[@id="tabs0head1"]')))
        NBS.find_element(By.XPATH, '//*[@id="tabs0head1"]').click()
        
        #read investigations
        try:
            investigation_table = NBS.read_investigation_table()
        except NoSuchElementException:
            inv_found = False

        
        #Navigate to the lab report to be processed using the Document ID from the patient page
        case_report_table_path = '//*[@id="caseReports"]'
        case_report_table = NBS.ReadTableToDF(case_report_table_path)
        
        case_row = case_report_table[case_report_table['Event ID'] == re.findall(r'DOC\d+ME\d+',doc_id)[0]]
        case_index = int(case_row.index.to_list()[0]) + 1
        
        if case_index > 1:
            case_path = f'//*[@id="eventCaseReports"]/tbody/tr[{str(case_index)}]/td[1]/a'
        elif case_index == 1:
            case_path = '//*[@id="eventCaseReports"]/tbody/tr[1]/td[1]/a'
        WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.element_to_be_clickable((By.XPATH, case_path)))
        NBS.find_element(By.XPATH, case_path).click()

        existing_investigations = None
        # Define or initialize the 'lab' variable with required attributes
        lab = type('Lab', (object,), {})()  # Create a simple object to hold attributes
        lab.Specimen_Coll_DT = None  # Replace 'None' with the appropriate value or logic to set this attribute

        inv_found, existing_not_a_case = NBS.check_for_existing_investigation(lab.Specimen_Coll_DT)
        if existing_not_a_case:
            NBS.go_to_home()
            print('Existing COVID investigation in the last 90 days with Not a Case status. Lab skipped.')
            continue
        elif inv_found:
            #If an existing investigation is found associate the lab with that investigation.
            NBS.go_to_investigation_by_index(NBS.existing_investigation_index)
            NBS.go_to_manage_associations()
            NBS.associate_lab_with_investigation(doc_id)
            NBS.click_manage_associations_submit()
            NBS.enter_edit_mode()
            NBS.GoToCaseInfo()
            NBS.set_earliest_positive_collection_date(lab.Specimen_Coll_DT)
            NBS.update_report_date(lab.Lab_Rpt_Received_By_PH_Dt)
            NBS.set_county_and_state_report_dates(lab.Lab_Rpt_Received_By_PH_Dt)
            NBS.review_case_status(lab.TestType)
            NBS.update_case_info_aoes(lab.HOSPITALIZED
                                ,lab.RESIDENT_CONGREGATE_SETTING
                                ,lab.FIRST_RESPONDER
                                ,lab.EMPLOYED_IN_HEALTHCARE)
            NBS.write_general_comment(f' Associated lab {lab.doc_id}. -nbsbot {NBS.now_str}')
            NBS.GoToCOVID()
            NBS.GoToCOVID()
            NBS.update_pregnant_aoe(lab.PREGNANT)
            NBS.update_symptom_aoe(lab.SYMPTOMATIC_FOR_DISEASE, lab.ILLNESS_ONSET_DATE)
            NBS.click_submit()
        else:
            #create investigation
            '''WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.element_to_be_clickable((By.XPATH, '//*[@id="srtLink"]/div/a[1]')))
            NBS.find_element(By.XPATH, '//*[@id="srtLink"]/div/a[1]').click()
            WebDriverWait(NBS,NBS.wait_before_timeout).until(EC.element_to_be_clickable((By.XPATH, '//*[@id="tabs0head1"]')))
            NBS.find_element(By.XPATH, '//*[@id="tabs0head1"]').click()
            NBS.go_to_lab(doc_id)'''
            NBS.create_investigation()
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
            NBS.GoToCaseInfo()
            NBS.set_investigation_status_closed()
            NBS.set_state_case_id()
            NBS.set_county_and_state_report_dates(lab.Lab_Rpt_Received_By_PH_Dt)
            NBS.set_performing_lab(lab.Perform_Facility_Name)
            NBS.set_earliest_positive_collection_date(lab.Specimen_Coll_DT)
            NBS.review_case_status(lab.TestType)
            NBS.update_case_info_aoes(lab.HOSPITALIZED
                                ,lab.RESIDENT_CONGREGATE_SETTING
                                ,lab.FIRST_RESPONDER
                                ,lab.EMPLOYED_IN_HEALTHCARE)
            NBS.set_confirmation_date()
            NBS.set_mmwr()
            NBS.set_closed_date()
            NBS.write_general_comment(f'Created investigation from lab {lab.Lab_Local_ID}. -nbsbot {NBS.now_str}')
            NBS.GoToCOVID()
            NBS.update_symptom_aoe(lab.SYMPTOMATIC_FOR_DISEASE, lab.ILLNESS_ONSET_DATE)
            NBS.update_pregnant_aoe(lab.PREGNANT)
            NBS.set_immpact_query_to_yes()
            NBS.set_lab_testing_performed()
            NBS.click_submit()
            NBS.click_submit()
            NBS.patient_id = NBS.ReadPatientID()
            NBS.go_to_manage_associations()
            #Atempt collection vaccine records from Immpact
            if NBS.query_immpact():
                NBS.id_covid_vaccinations()
                if len(NBS.covid_vaccinations) >= 1:
                    NBS.import_covid_vaccinations()
                    NBS.determine_vaccination_status(NBS.current_collection_date)
                    NBS.switch_to.window(NBS.main_window_handle)
                    NBS.click_manage_associations_submit()
                    NBS.enter_edit_mode()
                    NBS.GoToCOVID()
                    NBS.set_vaccination_fields()
                    NBS.click_submit()
                else:
                    NBS.close()
                    NBS.switch_to.window(NBS.main_window_handle)
                    NBS.click_cancel()
            else:
                NBS.switch_to.window(NBS.main_window_handle)
                NBS.click_cancel()
                if NBS.multiple_possible_patients_in_immpact:
                    NBS.failed_immpact_query_log.append(NBS.ReadPatientID())

            if not all([NBS.street, NBS.city, NBS.zip_code, NBS.county, NBS.unambiguous_race, NBS.ethnicity]):
                NBS.read_investigation_id()
                NBS.return_to_patient_profile_from_inv()
                NBS.go_to_demographics()
                if not all([NBS.street, NBS.city, NBS.zip_code, NBS.county]):
                    NBS.read_demographic_address()
                if not NBS.unambiguous_race:
                    NBS.read_demographic_race()
                if (not NBS.ethnicity) | (NBS.ethnicity == 'unknown'):
                    NBS.read_demographic_ethnicity()
                NBS.go_to_events()
                NBS.go_to_investigation_by_id(NBS.investigation_id)
                if (type(NBS.demo_address) == pd.core.series.Series) | (any([NBS.demo_race, NBS.demo_ethnicity])):
                    NBS.enter_edit_mode()
                    if type(NBS.demo_address) == pd.core.series.Series:
                        NBS.write_demographic_address()
                    if NBS.demo_race:
                        NBS.write_demographic_race()
                    if NBS.demo_ethnicity:
                        NBS.write_demographic_ethnicity()
                    NBS.read_address()
                    if not all([NBS.street, NBS.city, NBS.zip_code, NBS.county]):
                        NBS.incomplete_address_log.append(NBS.ReadPatientID())
                    NBS.click_submit()
            NBS.create_notification()
            NBS.check_jurisdiction()
        NBS.go_to_home()
                            
        
            
