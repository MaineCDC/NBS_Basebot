from selenium import webdriver
from selenium.webdriver.chrome.service import Service


#service = Service(driver)
#driver = webdriver.Chrome() 

from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from datetime import datetime
from fractions import Fraction
from dateutil.relativedelta import relativedelta
from bs4 import BeautifulSoup
import pandas as pd
import sys
import re
import win32com.client as win32
import getpass
from pathlib import Path
from shutil import rmtree
import time
from selenium.common.exceptions import TimeoutException, ElementNotInteractableException
from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import ElementClickInterceptedException
from selenium.common.exceptions import NoAlertPresentException, StaleElementReferenceException
import configparser
import smtplib
from email.message import EmailMessage
from selenium.webdriver.common.by import By
from geopy.geocoders import Nominatim
from usps import USPSApi, Address
import json
from io import StringIO
from strep_files.strep_bot import start_strep 

class NBSdriver(webdriver.Chrome):
    """ A class to provide basic functionality in NBS via Selenium. """
    def __init__(self, driver, production=False):
        self.driver = driver
        self.production = production
        self.read_config()
        self.get_email_info()
        self.get_usps_user_id()
        if self.production:
            self.site = 'https://nbs.iphis.maine.gov/'
        else:
            self.site = 'https://nbstest.state.me.us/'

        self.Reset()
        self.GetObInvNames()
        self.not_a_case_log = []
        self.lab_data_issues_log = []

        self.options = webdriver.ChromeOptions()
        self.options.add_argument('log-level=3')
        #self.options.add_argument('--headless')
        self.options.add_argument('--ignore-ssl-errors=yes')
        self.options.add_argument('--ignore-certificate-errors')
        super(NBSdriver, self).__init__(options = self.options)
        self.issues = []
        self.reviewed_ids = []
        self.what_do = []
        self.reason = []
        self.HepB_notification_bot = False
        self.iGAS_notification_bot = False
        self.ILIOutbreak_notification_bot = False
        self.num_attempts = 3
        self.queue_loaded = None
        self.wait_before_timeout = 30
        #self.sleep_duration = 3300 #Value in seconds
        self.sleep_duration = 120
    def GetObInvNames(self):
        """ Read list of congregate setting outbreak investigators from config.cfg. """
        self.outbreak_investigators = self.config.get('OutbreakInvestigators', 'Investigators').split(', ')
        
    def Reset(self):
        """ Clear values of attributes assigned during case investigation review.
        To be used on initialization and between case reviews. """
        self.issues = []
        self.now = datetime.now().date()
        self.collection_date = None
        self.received_date = None
        self.cong_aoe = None
        self.cong_setting_indicator = None
        self.county = None
        self.country = None #new variable
        self.current_report_date = None
        self.current_status = None
        self.patient_die_from_illness = None
        self.dob = None
        self.first_responder = None
        self.fr_aoe = None
        self.hcw_aoe = None
        self.healthcare_worker = None
        self.hosp_aoe = None
        self.hospitalization_indicator = None
        self.icu_aoe = None
        self.icu_indicator = None
        self.immpact = None
        self.investigation_start_date = None
        self.investigator = None
        self.jurisdiction = None        #new variable to allow access from multiple functions
        self.labs = None
        self.ltf = None
        self.preg_aoe = None
        #self.report_date = None
        self.status = None
        self.symp_aoe = None
        self.symptoms = None
        self.symptoms_list = []         #new variable initially undeclared
        self.vax_recieved = None
        self.initial_name = None        #new variable initially undeclared
        self.final_name = None          #new variable initially undeclared
        self.CaseStatus = None          #new variable initially undeclared
        self.CorrectCaseStatus = None   #new variable initially undeclared

    ########################### NBS Navigation Methods ############################
    def get_credentials(self):
        """ A method to prompt user to provide a valid username and RSA token
        to log in to NBS. Must """
        self.username = input('Enter your SOM username ("first_name.last_name"):')
        self.passcode = input('Enter your RSA passcode:')

    def set_credentials(self, username, passcode):
        """ A method to prompt user to provide a valid username and RSA token
        to log in to NBS. Must """
        self.username = username
        self.passcode = passcode

    def log_in(self):
        """ Log in to NBS. """
        try:
            self.driver.get(self.site)
            print('passed')
            self.driver.switch_to.frame("contentFrame")
            self.driver.find_element(By.ID, "username").send_keys(self.username) #find_element_by_id() has been deprecated
            self.driver.find_element(By.ID, 'passcode').send_keys(self.passcode)
            WebDriverWait(self.driver,self.wait_before_timeout).until(EC.element_to_be_clickable((By.XPATH, '/html/body/div[2]/p[2]/input[1]')))
            self.driver.find_element(By.XPATH,'/html/body/div[2]/p[2]/input[1]').click()
            time.sleep(3) #wait for the page to load, I'm not sure why the following wait to be clickable does not handle this, but this fixed the error
            #print(str(self.current_url))
            print(self.driver.page_source) #for some reason removing this makes nbsbot unable to log in to nbs
            WebDriverWait(self.driver,self.wait_before_timeout).until(EC.element_to_be_clickable((By.XPATH, '//*[@id="bea-portal-window-content-4"]/tr/td/h2[4]/font/a'))) #switch to element_to_be_clickable
            self.driver.find_element(By.XPATH,'//*[@id="bea-portal-window-content-4"]/tr/td/h2[4]/font/a').click()
        except Exception as e:
            print(f"Login failed. Please check your credentials and internet connection. Error details: {str(e)}")

################### Name Details check methods####################
    def CheckFirstName(self):
        """ Must provide first name. """
        first_name = self.ReadText('//*[@id="DEM104"]') 
        if not first_name:
            self.issues.append('First name is blank.')

    def CheckLastName(self):
        """ Must provide last name. """
        last_name = self.ReadText( '//*[@id="DEM102"]')
        if not last_name:
            self.issues.append('Last name is blank.')

################ Check Phone Methods #####################
    def CheckPhone(self):
        """ If a phone number is provided make sure it is ten digits. """
        home_phone = self.ReadText('//*[@id="DEM177"]')
        work_phone = self.ReadText('//*[@id="NBS002"]')
        cell_phone = self.ReadText('//*[@id="NBS006"]')
        if home_phone:
            #check if phone is ten digits if it exists
            if len(re.findall(r'\d', str(home_phone))) != 10:
                self.issues.append('Phone number is not ten digits.')
        elif work_phone:
            #check if phone is ten digits if it exists
            if len(re.findall(r'\d', str(work_phone))) != 10:
                self.issues.append('Phone number is not ten digits.')
        elif cell_phone:
            #check if phone is ten digits if it exists
            if len(re.findall(r'\d', str(cell_phone))) != 10:
                self.issues.append('Phone number is not ten digits.')
    
############ Demographic/Address Check Methods #####################
    def CheckStAddr(self):
        """ Must provide street address. """
        street_address = self.ReadText( '//*[@id="DEM159"]')
        if not street_address:
            self.issues.append('Street address is blank.')
            
    def CheckCity(self):
        """ Must provide city. """
        self.city = self.ReadText( '//*[@id="DEM161"]')
        if not self.city:
            self.issues.append('City is blank.')
            
    def CheckState(self):
        """ Must provide state and if it is not Maine case should be not a case. """
        self.state = self.ReadText( '//*[@id="DEM162"]')
        if not self.state:
            self.issues.append('State is blank.')
        elif self.state != 'Maine':
            self.issues.append('State is not Maine.')
            print(f"state: {self.state}")
    
    
    def CheckZip(self):
        """ Must provide zip code. """
        self.zipcode = self.ReadText( '//*[@id="DEM163"]')
        if not self.zipcode:    
            self.issues.append('Zip code is blank.')

    def CheckCounty(self):
        """ Must provide county unless the jurisdiction is 'Out of State'. """
        self.county = self.ReadText( '//*[@id="DEM165"]')
        self.jurisdiction = self.ReadText('//*[@id="INV107"]')
        if not self.county:
            self.issues.append('County is blank.')
        if self.jurisdiction == 'Out of State':                                        #new code
            return #skip further county checks if out of state                       #new code
        
    def CheckCountry(self):
        """ Must provide country. """
        self.country = self.ReadText( '//*[@id="DEM167"]')
        if not self.country:
            self.issues.append('Country is blank.')
        elif self.country != 'UNITED STATES':
            self.issues.append('Out of State') #new code

    
################### Personal Details check methods ####################

    def CheckDOB(self):
        """ Must provide DOB. """
        self.dob = self.ReadDate('//*[@id="DEM115"]')
        self.age = self.ReadText('//*[@id="INV2001"]')
        if not self.dob:
            self.issues.append('DOB is blank.')
        elif self.dob > self.now:
            self.issues.append('DOB cannot be in the future.')

    def CheckAge(self):
        """ Must provide age. """
        self.age = self.ReadText('//*[@id="INV2001"]')
        self.age_units = self.ReadText('//*[@id="INV2002"]')
        self.current_report_date = self.ReadDate('//*[@id="INV111"]')
        self.investigation_start_date = self.ReadDate('//*[@id="INV147"]')
        if not self.age:
            self.issues.append('Correct Age is blank.') 
        if self.age_units == 'Years':
            if int((self.investigation_start_date - self.dob).days / 365.25) != int(self.age):
                self.issues.append('Age mismatch.')
        elif self.age_units == 'Months':
            if int((self.investigation_start_date - self.dob).days / 30) != int(self.age):
                self.issues.append('Age mismatch.')
             
    def CheckAgeType(self):
        """ Must age type must be one of Days, Months, Years. """
        self.age_type = self.ReadText('//*[@id="INV2002"]')
        if not self.age_type:
            self.issues.append('Age Type is blank.')
        elif self.age_type != "Days" and self.age_type != "Months" and self.age_type != "Years":
            self.issues.append('Age Type is not one of Days, Months, or Years.')

    def CheckCurrentSex(self):
        """ Ensure patient current sex is not blank. """
        self.patient_sex = self.ReadText('//*[@id="DEM113"]')
        if not self.patient_sex:
            self.issues.append('Patient sex is blank.')
        elif self.patient_sex == "Unknown":
            comment = self.ReadText('//*[@id="DEM196"]')
            if not comment:
                self.issues.append('Patient sex is Unknown without a note.')

    ############ Ethnicity and Race Information Check Methods #####################
    def CheckEthnicity(self):
        """ Must provide ethnicity. """
        self.ethnicity = self.ReadText('//*[@id="DEM155"]')
        if not self.ethnicity:
            self.issues.append('Ethnicity is blank.')
    
    def CheckRace(self):
        """ Must provide race and selection must make sense. """
        self.race = self.CheckForValue('//*[@id="patientRacesViewContainer"]','Race is blank.')
        # Race should only be unknown if no other options are selected.
        ambiguous_answers = ['Unknown', 'Other', 'Refused to answer', 'Not Asked']
        for answer in ambiguous_answers:
            if (answer in self.race) and (self.race != answer) and (self.race == 'Native Hawaiian or Other Pacific Islander'):
                self.issues.append('"'+ answer + '"' + ' selected in addition to other options for race.')

    def CheckRaceAna(self):
        """ Must provide race and selection must make sense. """
        self.race = self.CheckForValue('//*[@id="patientRacesViewContainer"]','Race is blank.')
        #If white is selected, other should not be selected
        if "White" in self.race and "Unknown" in self.race:
            self.issues.append("White and Unknown race should not be selected at the same time.")
        if "Other" in self.race:
            self.CheckForValue('//*[@id="DEM196"]', "If Other race is selected there needs to be a comment.")
        # Race should only be unknown if no other options are selected.
        ambiguous_answers = ['Unknown', 'Other', 'Refused to answer', 'Not Asked']
        for answer in ambiguous_answers:
            if (answer in self.race) and (self.race != answer) and (self.race == 'Native Hawaiian or Other Pacific Islander'):
                self.issues.append('"'+ answer + '"' + ' selected in addition to other options for race.')

    def go_to_id(self, id):
        """ Navigate to specific patient by NBS ID from Home. """
        self.driver.find_element(By.XPATH,'//*[@id="DEM229"]').send_keys(id)
        self.driver.find_element(By.XPATH,'//*[@id="patientSearchByDetails"]/table[2]/tbody/tr[8]/td[2]/input[1]').click()
        search_result_path = '//*[@id="searchResultsTable"]/tbody/tr/td[1]/a'
        WebDriverWait(self.driver,self.wait_before_timeout).until(EC.presence_of_element_located((By.XPATH, search_result_path)))
        self.driver.find_element(By.XPATH, search_result_path).click()

    def clean_patient_id(self, patient_id):
        """Remove the leading and trailing characters from local patient
        ids to leave an id that is searchable in through the front end of NBS."""
        if patient_id[0:4] == 'PSN1':
            patient_id = patient_id[4:len(patient_id)-4]
        elif patient_id[0:4] == 'PSN2':
            patient_id = '1' + patient_id[4:len(patient_id)-4]
        return patient_id

    def go_to_summary(self):
        """ Within a patient profile navigate to the Summary tab."""
        self.driver.find_element(By.XPATH,'//*[@id="tabs0head0"]').click()

    def go_to_events(self):
        """ Within patient profile navigate to the Events tab. """
        events_path = '//*[@id="tabs0head1"]'
        try:
            WebDriverWait(self.driver,self.wait_before_timeout).until(EC.presence_of_element_located((By.XPATH, events_path)))
            self.driver.find_element(By.XPATH, events_path).click()
            error_encountered = False
        except TimeoutException:
            error_encountered = True
        return error_encountered

    def cgo_to_demographics(self):
        """ Within a patient profile navigate to the Demographics tab."""
        demographics_path = '//*[@id="tabs0head2"]'
        WebDriverWait(self.driver,self.wait_before_timeout).until(EC.presence_of_element_located((By.XPATH, demographics_path)))
        self.driver.find_element(By.XPATH,'//*[@id="tabs0head2"]').click()

    def go_to_home(self):
        """ Go to NBS Home page. """
        #xpath = '//*[@id="bd"]/table[1]/tbody/tr/td[1]/table/tbody/tr/td[1]/a'
        partial_link = 'Home'
        for i in range(3):
            try:
                #WebDriverWait(self.driver,self.wait_before_timeout).until(EC.presence_of_element_located((By.XPATH, xpath)))
                #self.driver.find_element(By.XPATH, xpath).click()
                timeout = self.wait_before_timeout + i*10
                WebDriverWait(self.driver, timeout).until(EC.presence_of_element_located((By.PARTIAL_LINK_TEXT, partial_link)))
                self.driver.find_element(By.PARTIAL_LINK_TEXT, partial_link).click()
                self.home_loaded = True
                break
            except StaleElementReferenceException:
                print("StaleElementReferenceException encountered, retrying...")
                self.home_loaded = False
            except TimeoutException:
                self.home_loaded = False
        if not self.home_loaded:
            sys.exit(print(f"Made {i} unsuccessful attempts to load Home page. A persistent issue with NBS was encountered."))

    def GoToApprovalQueue(self):
        """ Navigate to approval queue from Home page. """
        partial_link = 'Approval Queue for Initial Notifications'
        try:
            WebDriverWait(self.driver,self.wait_before_timeout).until(EC.presence_of_element_located((By.PARTIAL_LINK_TEXT, partial_link)))
            self.driver.find_element(By.PARTIAL_LINK_TEXT, partial_link).click()
        except TimeoutException:
            self.HandleBadQueueReturn()

    def ReturnApprovalQueue(self):
        """ Return to Approval Queue from an investigation initally accessed from the queue. """
        xpath = '//*[@id="bd"]/div[1]/a'
        try:
            WebDriverWait(self.driver,self.wait_before_timeout).until(EC.presence_of_element_located((By.XPATH, xpath)))
            self.driver.find_element(By.XPATH, xpath).click()
        except TimeoutException:
            self.HandleBadQueueReturn()

    def SortQueue(self, paths:dict):
        #Sort review queue so that only Anaplasma investigations are listed
        try:    
            #clear all filters
            WebDriverWait(self.driver,self.wait_before_timeout).until(EC.element_to_be_clickable((By.XPATH, paths['clear_filter_path'])))
            self.driver.find_element(By.XPATH, paths['clear_filter_path']).click()
            time.sleep(5)

            #open condition dropdown menu
            WebDriverWait(self.driver,self.wait_before_timeout).until(EC.presence_of_element_located((By.XPATH, paths['description_path'])))
            WebDriverWait(self.driver,self.wait_before_timeout).until(EC.element_to_be_clickable((By.XPATH, paths['description_path'])))
            self.driver.find_element(By.XPATH, paths['description_path']).click()
            time.sleep(1)

            #clear checkboxes
            WebDriverWait(self.driver,self.wait_before_timeout).until(EC.element_to_be_clickable((By.XPATH, paths['clear_checkbox_path'])))
            self.driver.find_element(By.XPATH, paths['clear_checkbox_path']).click()
            time.sleep(1)

            #select all tests
            for test in paths['tests']:
                try:
                    results = self.driver.find_elements(By.XPATH,f"//label[contains(text(),'{test}')]")
                    for result in results:
                        result.click()
                except (NoSuchElementException, ElementNotInteractableException) as e:
                    pass
            time.sleep(1)

            #click ok
            try:
                WebDriverWait(self.driver,self.wait_before_timeout).until(EC.element_to_be_clickable((By.XPATH, paths['click_ok_path'])))
                self.driver.find_element(By.XPATH, paths['click_ok_path']).click()
            except (NoSuchElementException, TimeoutException):
                #click cancel and go back to home page to wait for more ELRs
                WebDriverWait(self.driver,self.wait_before_timeout).until(EC.element_to_be_clickable((By.XPATH, paths['click_cancel_path'])))
                self.driver.find_element(By.XPATH, paths['click_cancel_path']).click()
                #self.go_to_home()
                time.sleep(3)
                #self.Sleep()
                #this wont work if we are not running the for loop to cycle through the queue,
                #comment out if not running the whole thing
                
            time.sleep(1)

            #sort chronologically, oldest first
            WebDriverWait(self.driver,self.wait_before_timeout).until(EC.element_to_be_clickable((By.XPATH, paths['submit_date_path'])))
            self.driver.find_element(By.XPATH, paths['submit_date_path']).click()
            WebDriverWait(self.driver,self.wait_before_timeout).until(EC.element_to_be_clickable((By.XPATH, paths['submit_date_path'])))
            self.driver.find_element(By.XPATH, paths['submit_date_path']).click() #---here
        except (TimeoutException, ElementClickInterceptedException):
            self.HandleBadQueueReturn()

    def SortApprovalQueueAthena(self):
        """ Sort approval queue so that case are listed chronologically by
        notification creation date and in reverse alpha order so that
        "2019 Novel..." is at the top. """
        clear_filter_path = '//*[@id="removeFilters"]/a/font'
        submit_date_path = '//*[@id="parent"]/thead/tr/th[3]/a'
        condition_path = '//*[@id="parent"]/thead/tr/th[8]/a'
        description_path = '//html/body/div[2]/form/div/table[2]/tbody/tr/td/table/thead/tr/th[8]/img'
        clear_checkbox_path = '/html/body/div[2]/form/div/table[2]/tbody/tr/td/table/thead/tr/th[8]/div/label[2]/input'
        try:
            # Clear all filters
            WebDriverWait(self.driver,self.wait_before_timeout).until(EC.element_to_be_clickable((By.XPATH, clear_filter_path)))
            self.driver.find_element(By.XPATH, clear_filter_path).click()
            # The logic for this is somewhat weird but here is my understanding of what happens.
            # If we have anything in the queue that isn't covid-19 the bot will run until it hits that case and then stall out.
            # To prevent this we can select covid-19 cases from the condition menu, but if there are no covid-19 cases we still
            # have to pick something from the dropdown menu or cancel out. We will cancel out of the dropdown menu if there are
            # no covid-19 cases which will give us only non-covid-19 cases. The check for covid-19 later on will prevent us
            # from reviewing the next case in the queue and it will hit the wait until we have more covid-19 cases. I think this
            # will allow for conditions besides covid-19 in the queue and allow us to process all covid-19 cases without
            # stalling the bot permanently once it runs into a non-covid-19 case.
            # Open Condition dropdown menu
            time.sleep(3)
            WebDriverWait(self.driver,self.wait_before_timeout).until(EC.element_to_be_clickable((By.XPATH, description_path)))
            self.driver.find_element(By.XPATH, description_path).click()
            # Clear checkboxes
            WebDriverWait(self.driver,self.wait_before_timeout).until(EC.element_to_be_clickable((By.XPATH, clear_checkbox_path)))
            self.driver.find_element(By.XPATH, clear_checkbox_path).click()
            try:
                # Click on the 2019 Novel Coronavirus checkbox
                self.driver.find_element(By.XPATH, "//label[contains(text(),'2019 Novel Coronavirus (2019-nCoV)')]/input").click()
                try:
                    self.driver.find_element(By.XPATH, "//label[contains(text(),'2019 Novel Coronavirus (2019-nCoV)')]/input").click()
                    
                except Exception as e:
                    print(f"Error encountered: {e}")
                # Click on the okay button
                self.driver.find_element(By.XPATH,'/html/body/div[2]/form/div/table[2]/tbody/tr/td/table/thead/tr/th[8]/div/label[1]/input[1]').click()
            except NoSuchElementException:
                self.driver.find_element(By.XPATH,'/html/body/div[2]/form/div/table[2]/tbody/tr/td/table/thead/tr/th[8]/div/label[1]/input[2]').click()             
                self.queue_loaded = False
            except Exception as e:
                print(f"Error encountered: {e}")
            
            for i in range(3):
                try:
                    WebDriverWait(self.driver,self.wait_before_timeout).until(EC.element_to_be_clickable((By.XPATH, submit_date_path)))
                    self.driver.find_element(By.XPATH, submit_date_path).click()
                    WebDriverWait(self.driver,self.wait_before_timeout).until(EC.element_to_be_clickable((By.XPATH, submit_date_path)))
                    self.driver.find_element(By.XPATH, submit_date_path).click()
                    break
                except StaleElementReferenceException:
                    print(f"StaleElementReferenceException for submit_date_path, trying again... retry_number: {i}")
                except TimeoutException:
                    print(f"TimeoutException for submit_date_path, trying again... retry_number: {i}")
            # Double click condition for reverse alpha order.
            WebDriverWait(self.driver,self.wait_before_timeout).until(EC.element_to_be_clickable((By.XPATH, condition_path)))
            self.driver.find_element(By.XPATH,condition_path).click()
            WebDriverWait(self.driver,self.wait_before_timeout).until(EC.element_to_be_clickable((By.XPATH, condition_path)))
            self.driver.find_element(By.XPATH,condition_path).click()
            WebDriverWait(self.driver,self.wait_before_timeout).until(EC.element_to_be_clickable((By.XPATH, condition_path)))
        except (TimeoutException, ElementClickInterceptedException):
            self.HandleBadQueueReturn()

    def HandleBadQueueReturn(self):
        """ When a request is sent to NBS to load or filter the approval queue
        and "Nothing found to display", or anything other than the populated
        queue is returned, navigate back to the home page and request the queue
        again."""
        # Recursion seems like a good idea here, but if the queue is truly empty there will be nothing to display and recursion will result in a stack overflow.
        for _ in range(self.num_attempts):
            try:
                self.go_to_home()
                self.GoToApprovalQueue()
                self.queue_loaded = True
                break
            except TimeoutException:
                self.queue_loaded = False
        if not self.queue_loaded:
            print(f"Made {self.num_attempts} unsuccessful attempts to load approval queue. Either to queue is truly empty, or a persistent issue with NBS was encountered.")

    def CheckFirstCase(self):
        """ Ensure that first case is COVID and save case's name for later use."""
        try:
            self.condition = self.driver.find_element(By.XPATH, '//*[@id="parent"]/tbody/tr[1]/td[8]/a').get_attribute('innerText')
            self.patient_name = self.driver.find_element(By.XPATH, '//*[@id="parent"]/tbody/tr[1]/td[7]/a').get_attribute('innerText')
        except NoSuchElementException:
            self.condition = None
            self.patient_name = None
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            self.condition = None
            self.patient_name = None

    def GoToFirstCaseInApprovalQueue(self):
        """ Navigate to first case in the approval queue. """
        xpath_to_case = '//*[@id="parent"]/tbody/tr[1]/td[8]/a'
        xpath_to_first_name = '//*[@id="DEM104"]'
        try:
            # Make sure queue loads properly before navigating to first case.
            WebDriverWait(self.driver,self.wait_before_timeout).until(EC.presence_of_element_located((By.XPATH, xpath_to_case)))
            self.driver.find_element(By.XPATH, xpath_to_case).click()
            # Make sure first case loads properly before moving on.
            WebDriverWait(self.driver,self.wait_before_timeout).until(EC.presence_of_element_located((By.XPATH, xpath_to_first_name)))
        except TimeoutException:
            self.HandleBadQueueReturn()

    def GoToNCaseInApprovalQueue(self, n=1):
        """ Navigate to first case in the approval queue. """
        xpath_to_case = f'//*[@id="parent"]/tbody/tr[{n}]/td[8]/a'
        xpath_to_first_name = '//*[@id="DEM104"]'
        try:
            # Make sure queue loads properly before navigating to first case.
            WebDriverWait(self.driver,self.wait_before_timeout).until(EC.presence_of_element_located((By.XPATH, xpath_to_case)))
            self.driver.find_element(By.XPATH, xpath_to_case).click()
            # Make sure first case loads properly before moving on.
            WebDriverWait(self.driver,self.wait_before_timeout).until(EC.presence_of_element_located((By.XPATH, xpath_to_first_name)))
        except TimeoutException:
            self.HandleBadQueueReturn()

    def GoToCaseInfo(self):
        """ Within a COVID investigation navigate to the Case Info tab. """
        case_info_tab_path = '//*[@id="tabs0head1"]'
        WebDriverWait(self.driver,self.wait_before_timeout).until(EC.presence_of_element_located((By.XPATH, case_info_tab_path)))
        self.driver.find_element(By.XPATH, case_info_tab_path ).click()

    def GoToCOVID(self):
        """ Within a COVID investigation navigate to the COVID tab. """
        covid_tab_path = '//*[@id="tabs0head2"]'
        WebDriverWait(self.driver,self.wait_before_timeout).until(EC.presence_of_element_located((By.XPATH, covid_tab_path)))
        self.driver.find_element(By.XPATH, covid_tab_path).click()

    def go_to_lab(self, lab_id):
        """ Navigate to a lab from a patient profile navigate to a lab. """
        lab_report_table_path = '//*[@id="lab1"]'
        lab_report_table = self.ReadTableToDF(lab_report_table_path)
        if len(lab_report_table) > 1:
            lab_row_index = lab_report_table[lab_report_table['Event ID'] == lab_id].index.tolist()[0]
            lab_row_index = str(int(lab_row_index) + 1)
            lab_path = f'/html/body/div[2]/form/div/table[4]/tbody/tr[2]/td/div[2]/table/tbody/tr/td/div[1]/div[5]/div/table/tbody/tr/td/table/tbody/tr[{lab_row_index}]/td[1]/a'
        else:
            lab_path = '/html/body/div[2]/form/div/table[4]/tbody/tr[2]/td/div[2]/table/tbody/tr/td/div[1]/div[5]/div/table/tbody/tr/td/table/tbody/tr/td[1]/a'
        self.driver.find_element(By.XPATH,lab_path).click()

    # adding code to read investigation table
    def read_investigation_table(self):
        """ Read the investigations table in the Events tab of a patient profile
        of all investigations on record, both open and closed."""
        investigation_table_path = '//*[@id="inv1"]'
        investigation_table = self.ReadTableToDF(investigation_table_path)
        '''if type(investigation_table) == pd.core.frame.DataFrame:
            investigation_table['Start Date'] = pd.to_datetime(investigation_table['Start Date'])
        return investigation_table'''
        if isinstance(investigation_table, pd.core.frame.DataFrame):
            if 'Start Date' in investigation_table.columns:
                investigation_table['Start Date'] = pd.to_datetime(investigation_table['Start Date'], errors='coerce')
        return investigation_table

    def go_to_investigation_by_index(self, index):
        """Navigate to an existing investigation based on its position in the
        Investigations table in the Events tab of a patient profile."""
        if index > 1:
            existing_investigation_path = f'/html/body/div[2]/form/div/table[4]/tbody/tr[2]/td/div[2]/table/tbody/tr/td/div[1]/div[3]/div/table/tbody/tr[2]/td/table/tbody/tr[{str(index)}]/td[1]/a'
        elif index == 1:
            existing_investigation_path = f'/html/body/div[2]/form/div/table[4]/tbody/tr[2]/td/div[2]/table/tbody/tr/td/div[1]/div[3]/div/table/tbody/tr[2]/td/table/tbody/tr/td[1]/a'
        self.driver.find_element(By.XPATH, existing_investigation_path).click()

    def go_to_investigation_by_id(self, inv_id):
        """Navigate to an investigation with a given id from a patient profile."""
        inv_table = self.read_investigation_table()
        inv_row = inv_table[inv_table['Investigation ID'] == inv_id]
        inv_index = int(inv_row.index.to_list()[0]) + 1
        self.go_to_investigation_by_index(inv_index)

    def return_to_patient_profile_from_inv(self):
        """ Go back to the patient profile from within an investigation."""
        return_to_file_path = '//*[@id="bd"]/div[1]/a'
        self.driver.find_element(By.XPATH, return_to_file_path).click()

    def return_to_patient_profile_from_lab(self):
        """ Go back to the patient profile from within a lab report."""
        return_to_file_path = '//*[@id="doc3"]/div[1]/a'
        self.driver.find_element(By.XPATH, return_to_file_path).click()

    def click_submit(self):
        """ Click submit button to save changes."""
        submit_button_path = '/html/body/div/div/form/div[2]/div[1]/table[2]/tbody/tr/td[2]/table/tbody/tr/td[1]/input'
        for i in range(3):
            try:
                timeout = self.wait_before_timeout + i*10
                element = WebDriverWait(self.driver, timeout).until(EC.element_to_be_clickable((By.XPATH, submit_button_path)))
                element.click()
                break
            except TimeoutException:
                print(f"TimeoutException for submit_button_path, trying again... retry_number: {i}")
            except StaleElementReferenceException:
                print(f"StaleElementReferenceException for submit_button_path, trying again... retry_number: {i}")
            except NoSuchElementException:
                print(f"No submit_button_path found, trying again... retry_number: {i}")
                time.sleep(1)
            except Exception as e:
                print(f"{e} has occured for submit_button_path, retry_number: {i}")

    def click_manage_associations_submit(self):
        """ Click submit button in the Manage Associations window."""
        submit_button_path = '/html/body/div[2]/div/table[2]/tbody/tr/td/table/tbody/tr/td[2]/input'
        self.driver.find_element(By.XPATH, submit_button_path).click()

    def enter_edit_mode(self):
        """From within an investigation click the edit button to enter edit mode."""
        edit_button_path = '/html/body/div/div/form/div[2]/div[1]/table[2]/tbody/tr/td[2]/table/tbody/tr/td[1]/input'
        self.driver.find_element(By.XPATH, edit_button_path).click()
        try:
            self.switch_to.alert.accept()
        except NoAlertPresentException:
            pass

    def click_cancel(self):
        """ Click cancel."""
        cancel_path = '//*[@id="Cancel"]'
        self.driver.find_element(By.XPATH, cancel_path).click()
        self.switch_to.alert.accept()

    def go_to_manage_associations(self):
        """ Click button to navigate to the Manage Associations page from an investigation."""
        manage_associations_path = '//*[@id="manageAssociations"]'
        self.driver.find_element(By.XPATH, manage_associations_path).click()
        try:
            self.switch_to.alert.accept()
        except NoAlertPresentException:
            pass

    def CheckInvestigationStatus(self):
        """ Only accept closed investigations for review. """
        inv_status = self.ReadText('//*[@id="INV109"]')
        if not inv_status:
            self.issues.append('Investigation status is blank.')
        elif inv_status.lower() == 'open':
            self.issues.append('Investigation status is open.')

    def CheckInvestigatorAssignDate(self):
        """ If an investigator was assinged then there should be an investigator
        assigned date. """
        if self.investigator:
            assigned_date = self.ReadText('//*[@id="INV110"]')
            if not assigned_date:
                self.issues.append('Missing investigator assigned date.')
   
    def CheckInvestigator(self):
        """ Check if an investigator was assigned to the case. """
        investigator = self.ReadText('//*[@id="INV180"]')
        self.investigator_name = investigator
        if not investigator:
            self.issues.append('Investigator is blank.')

################# Key Report Dates Check Methods ###############################
    def CheckReportDate(self):
        """ Check if the current value of Report Date matches the earliest
        Report Date from the associated labs. """
        self.current_report_date = self.ReadDate('//*[@id="INV111"]')
        if not self.current_report_date:
            self.issues.append('Report date is blank.')
        elif self.current_report_date > self.investigation_start_date:
            self.issues.append('Report date cannot be after investigation start date.')

    def CheckCountyStateReportDate(self):
        """ Check if the current value of county report date is consistent with
        the current value of earliest report to state date and the report date. """
        current_county_date = self.ReadDate('//*[@id="INV120"]')
        current_state_date = self.ReadDate('//*[@id="INV121"]')
        if not current_county_date:
            self.issues.append('Report to county date missing.')
        elif current_county_date < self.current_report_date:
            self.issues.append('Earliest report to county cannot be prior to inital report date.')
        elif current_county_date > self.investigation_start_date:
            self.issues.append('Earliest report to county date cannot be after investigation start date')
        if not current_state_date:
            self.issues.append('Report to state date missing.')
        elif current_state_date < self.current_report_date:
            self.issues.append('Earliest report to state cannot be prior to inital report date.')
        elif current_state_date > self.investigation_start_date:
            self.issues.append('Earliest report to state date cannot be after investigation start date.')
        if current_county_date != current_state_date:
            self.issues.append('Earliest dates reported to county and state do not match.')

################# Check Jurisdiction ####################
    def CheckJurisdiction(self):
        """ Jurisdiction and county must match. """
        self.jurisdiction = self.ReadText('//*[@id="INV107"]')
        if not self.jurisdiction:
            self.issues.append('Jurisdiction is blank.')
        if self.jurisdiction not in self.county:
            self.issues.append('County and jurisdiction mismatch.')

 ################### Investigation Details Check Methods ########################
    def CheckInvestigationStartDate(self):
        """ Verify investigation start date is on or after report date. """
        self.investigation_start_date = self.ReadDate('//*[@id="INV147"]')
        if not self.investigation_start_date:
            self.issues.append('Investigation start date is blank.')
        elif self.investigation_start_date > self.now:
            self.issues.append('Investigation start date cannot be in the future.')

    def CheckStateCaseID(self):
        """ State Case ID must be provided. """
        case_id = self.ReadText('//*[@id="INV173"]')
        if not case_id:
            self.issues.append('State Case ID is blank.')
            
    def CheckSharedIndicator(self):
        """ Ensure shared indicator is yes. """
        shared_indicator = self.ReadText('//*[@id="NBS_UI_19"]/tbody/tr[5]/td[2]')
        if shared_indicator != 'Yes':
            self.issues.append('Shared indicator not selected.')

################### Reporting Organization Check Methods #######################
    def CheckReportingSourceType(self):
        """ Ensure that reporting source type is not empty. """
        reporting_source_type = self.ReadText('//*[@id="INV112"]')
        if not reporting_source_type:
            self.issues.append('Reporting source type is blank.')
        elif reporting_source_type == 'Other':
            reporting_source_type_other = self.ReadText('//*[@id="INV183"]')
            if not reporting_source_type_other:
                self.issues.append('Reporting source type is Other but no other type provided.')

    def CheckReportingOrganization(self):
        """ Ensure that reporting organization is not empty. """
        reporting_organization = self.ReadText('//*[@id="INV183"]')
        if not reporting_organization:
            self.issues.append('Reporting organization is blank.')
    
    def CheckReportingProvider(self):
        """ Ensure that reporting provider is not empty. """
        reporting_provider = self.ReadText('//*[@id="INV181"]')
        if not reporting_provider:
            self.issues.append('Reporting Provider is blank.')
    
    def CheckReportingCounty(self):
        """ Ensure that reporting county is not empty. """
        reporting_county = self.ReadText('//*[@id="NOT113"]')
        if not reporting_county:
            self.issues.append('Reporting county is blank.')
    
    ######################### Case Status Check Methods ############################
    def CheckTransmissionMode(self):
        """ Transmission mode should blank or airborne"""
        transmission_method =  self.ReadText('//*[@id="INV157"]')
        if transmission_method not in ['', 'Airborne']:
            self.issues.append('Transmission mode should be blank or airborne.')
    
    def CheckConfirmationMethod(self):
        """ Confirmation Method must be blank or consistent with correct case status."""
        confirmation_method =  self.ReadText('//*[@id="INV161"]')
        if confirmation_method:
            if (self.status == 'C') & ('Laboratory confirmed' not in confirmation_method):
                self.issues.append('Since correct case status is confirmed confirmation method should include "Laboratory confirmed".')
            elif (self.status == 'P') & ('Laboratory report' not in confirmation_method):
                self.issues.append('Since correct case status is probable confirmation method should include "Laboratory report".')
            elif (self.status == 'S') & ('Clinical diagnosis (non-laboratory confirmed)' not in confirmation_method):
                self.issues.append('Since correct case status is probable confirmation method should include "Clinical diagnosis (non-laboratory confirmed)".')
        elif not confirmation_method: #new code
            self.issues.append("Confirmation method is missing")
            print(f"confirmation_method: {confirmation_method}")

    def CheckDetectionMethod(self):
        """ Ensure Detection Method is not blank. """
        detection_method = self.CheckForValue( '//*[@id="INV159"]', 'Detection method is blank.')
        if not detection_method: #new code
            self.issues.append('Detection method is missing')
            print(f"detection_method: {detection_method}")

    def CheckConfirmationDate(self):
        """ Confirmation date must be on or after report date. """
        confirmation_date = self.ReadDate('//*[@id="INV162"]')
        if not confirmation_date:
            self.issues.append('Confirmation date is blank.')
            print(f"confirmation_date: {confirmation_date}")
        elif self.received_date and confirmation_date < self.received_date:
            self.issues.append('Confirmation date cannot be prior to report date.')
            print(f"confirmation_date: {confirmation_date}")
        elif confirmation_date > self.now:
            self.issues.append('Confirmation date cannot be in the future.')
            print(f"confirmation_date: {confirmation_date}")
        return confirmation_date
    
    def CheckAdmissionDate(self):
        """ Check for hospital admission date."""
        self.admission_date = self.ReadDate('//*[@id="INV132"]')
        if not self.admission_date:
            self.issues.append('Admission date is missing.')
            print(f"admission_date: {self.admission_date}")
        elif self.admission_date and self.admission_date > self.now:
            self.issues.append('Admission date cannot be in the future.')
            print(f"admission_date: {self.admission_date}")

    def CheckDischargeDate(self):
        """ Check for hospital discharge date."""
        discharge_date = self.ReadDate('//*[@id="NBS_INV_GENV2_UI_3"]/tbody/tr[4]/td[2]|//*[@id="INV133"]')
        if self.self.patient_die_from_illness == "Yes" and self.hospitalization_indicator == "Yes":
            if not discharge_date:                                                         #commented out
                self.issues.append('Discharge date is blank.')                           #commented out
        if self.admission_date:
            if discharge_date and discharge_date < self.admission_date:
                self.issues.append('Discharge date must be after admission date.')
                print(f"discharge_date: {discharge_date}")
        elif discharge_date > self.now:
            self.issues.append('Discharge date cannot be in the future.')
            print(f"discharge_date: {discharge_date}")

    ############MMWR check should not be blank####################
    def CheckMmwrWeek(self):
        """ MMWR week must be provided."""
        mmwr_week = self.ReadText( '//*[@id="INV165"]')
        if not mmwr_week:
            self.issues.append('MMWR Week is blank.')

    def CheckMmwrYear(self):
        """ MMWR year must be provided."""
        mmwr_year = self.ReadText( '//*[@id="INV166"]')
        if not mmwr_year:
            self.issues.append('MMWR Year is blank.')
        elif self.collection_date and int(mmwr_year) != self.collection_date.year:
            self.issues.append('MMWR Year does not match specimen collection date year.')
            print(f"mmwr_year: {mmwr_year}, collection_date: {self.collection_date}")
            
            
####################### Patient Status Check Methods ############################
    def CheckDeath(self):
        """If died from illness is yes or no, need a death date """
        self.self.patient_die_from_illness =  self.CheckForValue('//*[@id="INV145"]','Died from illness must be yes or no.')
        if self.self.patient_die_from_illness == "Yes":
            """ Death date must be present."""
            death_date = self.ReadDate('//*[@id="INV146"]')
            if not death_date:
                self.issues.append('Date of death is blank.')
            elif death_date > self.now:
                self.issues.append('Date of death date cannot be in the future')

    def CheckHospitalization(self):
        """ Read hospitalization status. If yes need date and hospital """
        self.hospitalization_indicator = self.ReadText('//*[@id="INV128"]')
        if self.hospitalization_indicator == "Yes":
            hospital_name = self.ReadText('//*[@id="INV184"]')
            if not hospital_name:
                self.issues.append('Hospital name missing.')
                print(f"hospitalization, hospital_name: {hospital_name}")
            self.admission_date = self.ReadDate('//*[@id="INV132"]')
            if not self.admission_date:
                self.issues.append('Admission date is blank.')
                print(f"hospitalization, admission_date: {self.admission_date}")
            elif self.admission_date > self.now:
                self.issues.append('Admission date cannot be in the future.')
                print(f"hospitalization, admission_date: {self.admission_date}")
        elif self.hospitalization_indicator not in ['Yes', 'No']: 
            self.issues.append("Patient hospitalization status not indicated.")

    def CheckIllnessDurationUnits(self):
        """ Read Illness duration units, should be either Day, Month, or Year """
        self.IllnessDurationUnits = self.ReadText('//*[@id="INV140"]')
        if self.IllnessDurationUnits != "":
            if self.IllnessDurationUnits != "Day" and self.IllnessDurationUnits != "Month" and self.IllnessDurationUnits != "Year":
                self.issues.append('Illness Duration is not in Days, Months, or Years.')
                print(f"illness_duration_units: {self.IllnessDurationUnits}")
    
############### Preforming Lab Check Methods ##################################
    def CheckPreformingLaboratory(self):
        """ Ensure that preforming laboratory is not empty. """
        reporting_organization = self.ReadText('//*[@id="ME6105"]')
        if not reporting_organization:
            self.issues.append('Performing laboratory is blank.')

############################# Data Reading/Validation Methods ##################################
    def CheckForValue(self, xpath, blank_message):
        """ If value is blank add appropriate message to list of issues. """
        value = self.driver.find_element(By.XPATH, xpath).get_attribute('innerText')
        value = value.replace('\n','')
        # if not value:
        #     self.issues.append(blank_message)
        return value
    
    def ReadText(self, xpath):
        from time import sleep
        """ A method to read the text of any web element identified by an Xpath
        and remove leading an trailing carriage returns sometimes included by
        Selenium's get_attribute('innerText')."""
        for i in range(self.num_attempts): 
            try:
                value = self.driver.find_element(By.XPATH, xpath).get_attribute('innerText')
                value = value.replace('\n','')
                return value
            except NoSuchElementException:
                sleep((i+1)*10)
                print(f"no value ReadText for xpath: {xpath}, retry_number:{i}")
            except TimeoutException:
                print(f"Timeout waiting for ReadText for xpath: {xpath}, retry_number: {i}")
            except StaleElementReferenceException:
                sleep((i+1)*10)
                print(f"StaleElementReferenceException for ReadText for xpath: {xpath}, trying again... retry_number: {i}")
            except Exception as e:
                print(f"{e} has occured for ReadText for xpath: {xpath}, retry_number: {i}") 
    def ReadElement(self, xpath):
        """ A method to read the web element identified by an Xpath."""
        try:
            element = self.driver.find_element(By.XPATH, xpath)
            return element
        except Exception as e:
            print(f"Error reading element for xpath: {xpath}, {e}")
            return None

    def check_for_value_bool(self, path):
        """ Return boolean value based on whether a value is present."""
        value = self.ReadText(path)
        if value:
            check = True
        else:
            check = False
        return check

    def ReadDate(self, xpath, attribute='innerText'):
        """ Read date from NBS and return a datetime.date object. """
        date = self.driver.find_element(By.XPATH, xpath).get_attribute(attribute)
        date = date.replace('\n','')
        try:
            date = datetime.strptime(date, '%m/%d/%Y').date()
        except ValueError:
            date = ''
        return date

    def CheckIfField(self, parent_xpath, child_xpath, value, message):
        """ If parent field is value ensure that child field is not blank. """
        parent = self.driver.find_element(By.XPATH, parent_xpath).get_attribute('innerText')
        parent = parent.replace('\n','')
        if parent == value:
            child = self.driver.find_element(By.XPATH, child_xpath).get_attribute('innerText')
            child = child.replace('\n','')
            if not child:
                self.issues.append(message)

    def ReadTableToDF(self, xpath):
        """ A method to read tables into pandas Data Frames for easy manipulation. """
        try:
            html = self.driver.find_element(By.XPATH, xpath).get_attribute('innerHTML')
            soup = BeautifulSoup(html, 'html.parser')
            table = pd.read_html(StringIO(str(soup)))[0]
            table.fillna('', inplace = True)
        except ValueError:
            table = None
        return table

    def ReadPatientID(self):
        """ Read patient ID from within patient profile. """
        patient_id = self.ReadText('//*[@id="bd"]/table[3]/tbody/tr[1]/td[2]/span[2]')
        return patient_id

    def Sleep(self):
        """ Pause all action for the specified number of seconds. """
        for i in range(self.sleep_duration):
            time_remaining = self.sleep_duration - i
            print(f'Sleeping for: {time_remaining//60:02d}:{time_remaining%60:02d}', end='\r', flush=True)
            time.sleep(1)
        print('Sleeping for: 00:00', end='\r', flush=True)

    def send_email_local_outlook_client (self, recipient, cc, subject, message, attachment = None):
        """ Send an email using local Outlook client."""
        self.clear_gen_py()
        outlook = win32.Dispatch('outlook.application')
        mail = outlook.CreateItem(0)
        mail.GetInspector
        mail.To = recipient
        mail.CC = cc
        mail.Subject = subject
        mail.Body = message
        if attachment != None:
            mail.Attachments.Add(attachment)
        mail.Send()

    def clear_gen_py(self):
        """ Clear the contents of the the gen_py directory to ensure emails can
        always be sent."""
        # Construct to path gen_py directory if it exists.
        current_user = getpass.getuser().lower()
        gen_py_path = r'C:\Users' +'\\' + current_user + r'\AppData\Local\Temp\gen_py'
        
        gen_py_path = Path(gen_py_path)

        # If gen_py exists delete it and all contents.
        if gen_py_path.exists() and gen_py_path.is_dir():
            rmtree(gen_py_path)

    def read_config(self):
        """ Read in data from config.cfg"""
        self.config = configparser.ConfigParser()
        self.config.read('config.cfg')

    def get_email_info(self):
        """ Read information required for NBSbot to send emails via an smtp
        server to various email lists."""
        self.smtp_server = self.config.get('email', 'smtp_server')
        self.nbsbot_email = self.config.get('email', 'nbsbot_email')
        self.covid_informatics_list = self.config.get('email', 'covid_informatics_list')
        self.covid_admin_list = self.config.get('email', 'covid_admin_list')
        self.covid_commander = self.config.get('email', 'covid_commander')

    def get_usps_user_id(self):
        """ Extract the USPS User ID from the config file for later use in the
        zip_code_lookup() method."""
        self.usps_user_id = self.config.get('usps', 'user_id')

    def send_smtp_email(self, receiver, subject, body, email_name):
        """ Send emails using an SMTP server """
        message = EmailMessage()
        message.set_content(body)
        message['Subject'] = subject
        message['From'] = self.nbsbot_email
        message['To'] = ', '.join([receiver])
        try:
           smtpObj = smtplib.SMTP(self.smtp_server)
           smtpObj.send_message(message)
           print(f"Successfully sent {email_name}.")
        except smtplib.SMTPException:
           print(f"Error: unable to send {email_name}.")

    def get_main_window_handle(self):
        """ Run after login to identify and store the main window handle that the handles for pop-up windows can be differentiated."""
        self.main_window_handle = self.current_window_handle

    def switch_to_secondary_window(self):
        """ Set a secondary window as the current window in order to interact with the pop up."""
        new_window_handle = None
        for handle in self.window_handles:
            if handle != self.main_window_handle:
                new_window_handle = handle
                break
        if new_window_handle:
            self.switch_to.window(new_window_handle)

    def select_checkbox(self, xpath):
        """ Ensure the a given checkbox or radio button is selected. If not selected then click it to select."""
        checkbox = self.driver.find_element(By.XPATH, xpath)
        if not checkbox.is_selected():
            checkbox.click()

    def unselect_checkbox(self, xpath):
        """ Ensure the a given checkbox or radio button is not selected. If selected then click it to un-select."""
        checkbox = self.driver.find_element(By.XPATH, xpath)
        if checkbox.is_selected():
            checkbox.click()

    def county_lookup(self, city, state):
        """ Use the Nominatim geocode service via the geopy API to look up the county of a given town/city and state."""
        geolocator = Nominatim(user_agent = 'nbsbot')
        location = geolocator.geocode(city + ', ' + state)
        if location:
            location = location[0].split(', ')
            county = [x for x in location if 'County' in x]
            if len(county) == 1:
                county = county[0].split(' ')[0]
            else:
                county = ''
        else:
            county = ''
        return county

    def zip_code_lookup(self, street, city, state):
        """ Given a street address, city, and state use the USPS API via the usps
        Python package to lookup the associated zip code."""
        address = Address(
            name='',
            address_1=street,
            city=city,
            state=state,
            zipcode=''
        )
        usps = USPSApi(self.usps_user_id, test=True)
        try:
            validation = usps.validate_address(address)
            if not 'Address Not Found' in json.dumps(validation.result):
                zip_code = validation.result['AddressValidateResponse']['Address']['Zip5']
            else:
                zip_code = ''
        except Exception:
            zip_code = ''
        return zip_code

    def check_for_error_page(self):
        """ See if NBS encountered an error."""
        error_page_path = '/html/body/table/tbody/tr/td/table/tbody/tr[2]/td/table/tbody/tr/td/table/tbody/tr[2]/td[1]'
        try:
            if self.ReadText(error_page_path) == '\xa0Error Page':
                nbs_error = True
            else:
                nbs_error = False
        except Exception:
            nbs_error = False
        return nbs_error

    def go_to_home_from_error_page(self):
        """ Go to NBS Home page from an NBS error page. """
        xpath = '/html/body/table/tbody/tr/td/table/tbody/tr[1]/td/table/tbody/tr/td/table/tbody/tr/td[1]/a'
        for _ in range(self.num_attempts):
            try:
                WebDriverWait(self.driver,self.wait_before_timeout).until(EC.presence_of_element_located((By.XPATH, xpath)))
                self.driver.find_element(By.XPATH, xpath).click()
                self.home_loaded = True
                break
            except TimeoutException:
                self.home_loaded = False
        if not self.home_loaded:
            sys.exit(print(f"Made {self.num_attempts} unsuccessful attempts to load Home page. A persistent issue with NBS was encountered."))

    ################# Notification Check############
    def RejectNotification(self):
        """ Reject notification on first case in notification queue.
        To be used when issues were encountered during review of the case."""
        reject_path = '//*[@id="parent"]/tbody/tr[1]/td[2]/img'
        main_window_handle = self.driver.current_window_handle
        WebDriverWait(self.driver,self.wait_before_timeout).until(EC.element_to_be_clickable((By.XPATH, reject_path)))
        self.driver.find_element(By.XPATH,reject_path).click()
        WebDriverWait(self.driver, self.wait_before_timeout).until(EC.new_window_is_opened([main_window_handle]))
        rejection_comment_window = None
        for handle in self.driver.window_handles:
            if handle != main_window_handle:
                rejection_comment_window = handle
                break
        if rejection_comment_window:
            self.driver.switch_to.window(rejection_comment_window)
            timestamp = datetime.now().strftime("%m/%d/%Y, %H:%M:%S")
            self.issues.append('-nbsbot ' + timestamp)
            WebDriverWait(self.driver, self.wait_before_timeout).until(EC.visibility_of_element_located((By.XPATH, '//*[@id="rejectComments"]')))
            self.driver.find_element(By.XPATH,'//*[@id="rejectComments"]').send_keys(' '.join(self.issues))
            self.driver.find_element(By.XPATH,'/html/body/form/table/tbody/tr[3]/td/input[1]').click()
            self.driver.switch_to.window(main_window_handle)
            self.num_rejected += 1

    def ApproveNotification(self):
        """ Approve notification on first case in notification queue. """
        main_window_handle = self.current_window_handle
        self.driver.find_element(By.XPATH,'//*[@id="createNoti"]').click()
        for handle in self.driver.window_handles:
            if handle != main_window_handle:
                approval_comment_window = handle
                break
        self.driver.switch_to.window(approval_comment_window)
        self.driver.find_element(By.XPATH,'//*[@id="botcreatenotId"]/input[1]').click()
        self.driver.switch_to.window(main_window_handle)
        self.num_approved += 1

    ### Specific to case closing bots ###
    ### these functions are for sending email and creating excel sheet at end of bot run ###
    def SendBotRunEmail(self):
        if self.HepB_notification_bot == True:
            bot_name = "Hepatitis B Case Closing Bot"
        elif self.iGAS_notification_bot == True:
            bot_name = "iGAS Case Closing Bot"
        elif self.ILIOutbreak_notification_bot == True:
            bot_name = "ILI Outbreak Case Closing Bot"
        completion_message = (
    f"{bot_name} has finished running on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}. ")
    #f"Total labs reviewed: {len(self.reviewed_ids)} , self.reviewed_ids = {self.reviewed_ids}.")
        self.send_smtp_email("disease.reporting@maine.gov", f"{bot_name} ", completion_message, "Daily Bot Run Notification")
   
    def CreateExcelSheet(self):
        """ Create an Excel spreadsheet summarizing the cases reviewed."""
        print("ending, printing, saving")
        bot_act = pd.DataFrame(
            {'Inv ID': self.reviewed_ids,
            'Action': self.what_do,
            'Reason': self.reason
            })
        if self.HepB_notification_bot == True:
            bot_act.to_excel(f"saved/HepB/HepB_bot_activity_{datetime.now().date().strftime('%m_%d_%Y')}.xlsx")
            print("excel sheet created")
        if self.iGAS_notification_bot == True:
            bot_act.to_excel(f"saved/Strep/iGAS_bot_activity_{datetime.now().date().strftime('%m_%d_%Y')}.xlsx")
            print("excel sheet created")
        if self.ILIOutbreak_notification_bot == True:
            bot_act.to_excel(f"saved/ILIOutbreak/ILIOutbreak_bot_activity_{datetime.now().date().strftime('%m_%d_%Y')}.xlsx")
            print("excel sheet created")
    

    
