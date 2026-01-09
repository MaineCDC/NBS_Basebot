import re
from Base import NBSdriver
import pandas as pd
import smtplib, ssl
from email.message import EmailMessage
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime, date
from selenium.webdriver.chrome.service import Service
from bs4 import BeautifulSoup
from selenium import webdriver
driver=webdriver.Chrome()
import sys
#sys.stdout = open('logfile.txt', 'w')
class Logger:
    def __init__(self, filename):
            self.terminal = sys.stdout
            self.log = open(filename, 'a')
    def write(self, message):
            self.terminal.write(message)
            self.log.write(message)
    def flush(self):
        self.terminal.flush()
        self.log.flush()
sys.stdout = Logger("logfile.txt")

class ILIOutbreak(NBSdriver):
    """ A class to review COVID-19 cases in the notification queue.
    It inherits from NBSdriver."""
    
    def __init__(self, production=False):
        super().__init__(production)
        self.num_approved = 0
        self.num_rejected = 0
        self.num_fail = 0
        self.received_date = None

    def StandardChecks(self):
        """ A method to conduct checks that must be done on all cases regardless of investigator. """
        self.Reset()
        #self.initial_name = self.patient_name
        # Check Facility Tab
        self.OutbreakNameInfo()
        self.OutbreakReportingAddress()
        ###### Go to Outbreak Info Tab #########
        self.GoToOutbreakInfoTab()
        self.CheckJurisdiction()
        self.CheckProgramArea()
        self.CheckInvestigationStartDate()
        self.CheckInvestigationStatus()
        self.CheckSharedIndicator()
        #self.CheckStateCaseID()
        self.CheckClosedDate()
        self.CheckMmwrWeek()
        self.CheckMmwrYear()
        
        ##investigator info
        self.CheckInvestigator()
        self.CheckInvestigatorAssignDate()
        
        # reporting info
        self.CheckReportDate()
        self.CheckCountyStateReportDate()
        self.DateCaseBecameIll()
        self.GeneralComments()
        
        self.LabConfirmed()
        self.AffectedPopulation()
        self.LaboratoryConfirmation()
        self.CaseStatusIliOutbreak()

    def OutbreakNameInfo(self):
        """ Check outbreak name and type."""
        outbreak_facility_name = self.ReadText('//*[@id="DEM102"]')
        outbreak_facility_type = self.ReadText('//*[@id="DEM104"]')
        if not outbreak_facility_name:
            self.issues.append('Outbreak Facility name is blank.')
        if not outbreak_facility_type:
            self.issues.append('Outbreak Facility type is blank.')
        
    def OutbreakReportingAddress(self):
        """ Check outbreak reporting address."""
        self.outbreak_reporting_facility = self.ReadText('//*[@id="ME8145"]')
        if not self.outbreak_reporting_facility:
            self.issues.append('Outbreak Reporting Facility is blank.')
        street_address = self.CheckForValue('//*[@id="DEM159"]', 'Street address is blank.')
        if any(x in street_address for x in ["HOMELESS", "NO ADDRESS", "NO FIXED ADDRESS", "UNSHELTERED"]):
            self.CheckCounty()
            pass
        else: 
            self.CheckCity()
            self.CheckZip()
            self.CheckCounty()
        self.CheckState()
        self.CheckCountry()
        
    def GoToOutbreakInfoTab(self):
        """ navigate to the Outbreak Info tab."""
        outbreak_info_path = '//*[@id="tabs0head1"]'
        WebDriverWait(self,self.wait_before_timeout).until(EC.presence_of_element_located((By.XPATH, outbreak_info_path)))
        self.find_element(By.XPATH,'//*[@id="tabs0head1"]').click()
            
    def CheckProgramArea(self):
        """ Program area must be Influenza-like Illness. """
        program_area = self.ReadText('//*[@id="INV108"]') 
        if program_area != 'Influenza-like Illness':
            self.issues.append('Program Area is not "Influenza-like Illness".')
    
    def CheckClosedDate(self):
        """ Check if a closed date is provided and makes sense"""
        closed_date = self.ReadDate('//*[@id="ME11163"]')
        if not closed_date:
            self.issues.append('Investigation closed date is blank.')
        elif closed_date > self.now:
            self.issues.append('Closed date cannot be in the future.')
        elif closed_date < self.investigation_start_date:
            self.issues.append('Closed date cannot be before investigation start date.')
    
    def CheckSharedIndicator(self):
        """ Ensure shared indicator is yes. """
        shared_indicator = self.ReadText('//*[@id="NBS_UI_19"]/tbody/tr[5]/td[2]')
        if shared_indicator != 'Yes':
            self.issues.append('Shared indicator not selected.')
            
    def DateCaseBecameIll(self):
        """ Check date for first and last case became ill."""
        self.date_first_case_became_ill = self.ReadDate('//*[@id="ME26101"]')
        self.date_last_case_became_ill = self.ReadDate('//*[@id="ME26102"]')
        if not self.date_first_case_became_ill:
            self.issues.append('Date first case became ill is blank.')
        if not self.date_last_case_became_ill:
            self.issues.append('Date last case became ill is blank.')
    
    def GeneralComments(self):       
        """ Check general comments."""
        general_comments = self.ReadText('//*[@id="ME8110"]/tbody/tr/td[2]')
        self.current_case_status = self.ReadText('//*[@id="INV163"]')
        if self.current_case_status == 'Not a Case':
            if not general_comments:
                self.issues.append('case status is not a case and general comments are blank.') 
                      
    def AffectedPopulation(self):
        """ Check affected population."""
        self.affected_population = self.ReadTableToDF('//*[@id="ME8107"]/tbody/tr[1]/td/table/tbody/tr/td[2]') # //*[@id="ME8107"]/tbody/tr[1]/td/table
        #self.lab_confirmed_values = []
        # initialize once (outside the loop)
        # Initialize once
        self.attack_rate_group_percent_list = []

        if self.affected_population.empty:
            self.issues.append('Affected population is blank.')

        for i, row in self.affected_population.iterrows():
            row_num = i + 1

            # ---- Affected Population Type ----
            affected_population_type = row.get('Affected Population Type')
            if not affected_population_type:
                self.issues.append(f'Affected population type is blank for row {row_num}.')

            # ---- Population with ILI ----
            population_with_ili = row.get('Population with ILI (no lab)')
            if population_with_ili in [None, '']:
                self.issues.append(f'Population with ILI (no lab) is blank for row {row_num}.')
                continue

            # ---- Lab-confirmed influenza ----
            lab_confirmed_influenza = row.get('Lab-confirmed influenza')
            if lab_confirmed_influenza in [None, '']:
                self.issues.append(f'Lab Confirmed Influenza is blank for row {row_num}.')
                continue

            # ---- Total Population ----
            total_population = row.get('Total Population of Group')
            if not total_population:
                self.issues.append(f'Total Population of Group is blank for row {row_num}.')
                continue

            # ---- Attack Rate (Reported) ----
            attack_rate_group = row.get('Attack Rate of Group')
            if attack_rate_group in [None, '']:
                self.issues.append(f'Attack Rate of Group is blank for row {row_num}.')
                continue

            # ---- Convert to int safely ----
            try:
                population_with_ili = int(population_with_ili)
                lab_confirmed_influenza = int(lab_confirmed_influenza)
                total_population = int(total_population)
                attack_rate_group = int(attack_rate_group)
            except ValueError:
                self.issues.append(f'Invalid numeric value in row {row_num}.')
                continue

            # ---- Calculate Attack Rate % ----
            calculated_rate = (
                (population_with_ili + lab_confirmed_influenza)
                / total_population
                * 100
            )

            calculated_rate = int(round(calculated_rate))

            # ---- Store for later validations ----
            self.attack_rate_group_percent_list.append(calculated_rate)

            # ---- Validate against reported value ----
            if calculated_rate != attack_rate_group:
                self.issues.append(
                    f'Attack Rate of Group {attack_rate_group} does not match calculated value {calculated_rate}% for row {row_num}.'
                )


        
    ### sum of lab-confirmed influenza to check against laboratory confirmation total
    def LabConfirmed(self):
        self.lab_confirmed_values = []
        self.affected_population = self.ReadTableToDF('//*[@id="ME8107"]/tbody/tr[1]/td/table/tbody/tr/td[2]') 
        for i in range(len(self.affected_population)):
            self.lab_confirmed_influenza = self.affected_population.iloc[i]['Lab-confirmed influenza']
            if self.lab_confirmed_influenza is not None:
                self.lab_confirmed_values.append(self.lab_confirmed_influenza)
        self.count_influenza = []
        self.count_influenza = [int(x) for x in self.lab_confirmed_values if x is not None and str(x).strip() != '']
        self.count = sum(self.count_influenza)
            
    ### laboratory confirmation checks
    import re
    def LaboratoryConfirmation(self):
       self.laboratory_confirmation = self.ReadText('//*[@id="ME8108"]/tbody')
       counts_lab =  list(map(int,re.findall(r'(?:(?:Count|:)\s*)(\d+)',self.laboratory_confirmation)))
       lab_text_total = sum(counts_lab)
       if self.count != lab_text_total:
           self.issues.append(f'Sum of Lab-confirmed influenza in Affected Population ({self.count}) does not match total count in Laboratory Confirmation ({lab_text_total}).')
    
    def CaseStatusIliOutbreak(self):
        ili_assign_email = False
        ili_assign_email_id = []

        # Time difference in days
        self.time_difference = (
            self.date_last_case_became_ill - self.date_first_case_became_ill
        ).days

        facility = self.outbreak_reporting_facility
        status = self.current_case_status
        count = self.count

        # Always safely define row data
        row = None
        if self.affected_population is not None and not self.affected_population.empty:
            row = self.affected_population.iloc[0]
            lab_count = int(row.get('Lab-confirmed influenza', 0))
            ili_count = int(row.get('Population with ILI (no lab)', 0))
        else:
            lab_count = 0
            ili_count = 0

        # School / Daycare
        if facility == 'School (K-12) or Daycare' and status == 'Confirmed':
            if not self.attack_rate_group_percent_list:
                self.issues.append(
                    'No Attack Rate of Group values available to evaluate school/daycare threshold.'
                )
                return

            if not any(rate > 7.5 for rate in self.attack_rate_group_percent_list):
                self.issues.append(
                    'For confirmed school/daycare outbreaks, at least one Attack Rate of Group must be greater than 7.5%.'
                )

        # Acute Care / College / University
        elif facility in (
            'Acute Care / Nosocomial',
            'College / University / Boarding School',
        ):
            if count > 3:
                if status != 'Confirmed':
                    self.issues.append(
                        'If lab-confirmed influenza cases are more than 3, status should be Confirmed.'
                    )

            elif count == 3:
                if self.time_difference > 3:
                    self.issues.append(
                        'For confirmed case status, 3 lab-confirmed influenza cases must be within 72 hours.'
                    )
                elif status != 'Confirmed':
                    self.issues.append(
                        'If 3 lab-confirmed influenza cases occur within 72 hours, status should be Confirmed.'
                    )

            else:  # count < 3
                if status != 'Not a Case':
                    self.issues.append(
                        'If lab-confirmed influenza cases are less than 3, status should be Not a Case.'
                    )

        # Event
        elif facility == 'Event (wedding, etc.)':
            ili_assign_email = True
            ili_assign_email_id.append(self.inv_id)
            self.issues.append('Event outbreaks require manual review.')

        # Health Care Workers
        elif facility == 'Health Care Workers':
            if status != 'Not a Case':
                self.issues.append(
                    'Health Care Worker outbreaks should be classified as Not a Case.'
                )

        # Institutional
        elif facility == 'Institutional (workplace, jail, shelter, etc)':
            ili_assign_email = True
            ili_assign_email_id.append(self.inv_id)
            self.issues.append('Institutional outbreaks require manual review.')

        # Outpatient / Restaurant
        elif facility in (
            'Outpatient Healthcare Facility',
            'Restaurant',
        ):
            if status != 'Not a Case':
                self.issues.append(
                    f'{facility} outbreaks should be classified as Not a Case.'
                )

        # Summer Camp
        elif facility == 'Summer Camp':
            if count >= 1:
                if status != 'Confirmed':
                    self.issues.append(
                        'If at least 1 lab-confirmed influenza case exists, status should be Confirmed.'
                    )
            else:
                if status != 'Not a Case':
                    self.issues.append(
                        'If no lab-confirmed influenza cases exist, status should be Not a Case.'
                    )
        # Long Term Care Facility
        elif facility == 'Long Term Care Facility':
            if len(self.affected_population) > 1:
                ili_assign_email = True
                ili_assign_email_id.append(self.inv_id)
                self.issues.append(
                    'Long Term Care Facility outbreaks with multiple affected populations require manual review.'
                )
                return

            if lab_count < 2 and status == 'Confirmed':
                self.issues.append(
                    'At least 2 lab-confirmed influenza cases are required for confirmed status.'
                )

                if (lab_count == 1 and ili_count == 0) or (lab_count == 0 and ili_count == 1):
                    self.issues.append(
                        'Cannot determine whether cases are resident or staff; manual review required.'
                    )
                    ili_assign_email = True
                    ili_assign_email_id.append(self.inv_id)

            elif lab_count == 2:
                if self.time_difference > 3:
                    if status == 'Confirmed':
                        self.issues.append(
                            'For confirmed case status, 2 lab-confirmed cases must be within 72 hours.'
                        )
                    if status != 'Not a Case':
                        self.issues.append(
                            'If 2 lab-confirmed cases are not within 72 hours, status should be Not a Case.'
                        )
                else:
                    if status != 'Confirmed':
                        self.issues.append(
                            'If 2 lab-confirmed cases occur within 72 hours, status should be Confirmed.'
                        )

        return ili_assign_email, ili_assign_email_id

    '''def CaseStatusIliOutbreak(self):
        ili_assign_email = False
        ili_assign_email_id = []
        self.time_difference = (self.date_last_case_became_ill - self.date_first_case_became_ill).days
        if (self.outbreak_reporting_facility == 'School (K-12) or Daycare' and self.current_case_status == 'Confirmed'):
        # Ensure attack rates were calculated
            if not self.attack_rate_group_percent_list:
                self.issues.append('No Attack Rate of Group values available to evaluate school/daycare threshold.')
                return
            # Check if at least one attack rate is > 7.5%
            has_valid_attack_rate = any(rate > 7.5 for rate in self.attack_rate_group_percent_list)
            if not has_valid_attack_rate:
                self.issues.append('For confirmed school/daycare outbreaks, at least one Attack Rate of Group must be greater than 7.5%.') 

        elif self.outbreak_reporting_facility == 'Acute Care / Nosocomial':
            for i in range(len(self.affected_population)): 
                row_df = self.affected_population.iloc[[i]]
            if len(self.affected_population) == 1:
                if int(row_df['Lab-confirmed influenza']) > 3:
                    pass
                elif int(row_df['Lab-confirmed influenza']) == 3:
                    if self.time_difference > 3:
                        self.issues.append(f'for confirmed case status if lab-confirmed influenza is 3, should be within 72 hours of each other.')
                elif int(row_df['Lab-confirmed influenza']) < 3:
                    self.issues.append(f'if lab-confirmed influenza cases are less than 3 - it should be Not a Case.')
            if len(self.affected_population) > 1:
                for i in range(len(self.affected_population)):
                    if self.count > 3:
                        if self.current_case_status != 'Confirmed':
                            self.issues.append(f'if lab-confirmed influenza cases are more than 3 - it should be confirmed case status.')
                        if self.current_case_status == 'Confirmed':
                            pass
                    elif self.count == 3:
                        if self.time_difference > 3:
                            self.issues.append(f'for confirmed case status if lab-confirmed influenza is 3, should be within 72 hours of each other.')
                        elif self.time_difference <= 3:
                            if self.current_case_status != 'Confirmed':
                                self.issues.append(f'if lab-confirmed influenza cases are 3 within 72 hours of each other - it should be confirmed case status.')
                    elif self.count < 3:
                        if self.current_case_status != 'Not a Case':
                            self.issues.append(f'if lab-confirmed influenza cases are less than 3 - it should be Not a Case.')
                        if self.current_case_status == 'Not a Case':
                            pass
                        
        elif self.outbreak_reporting_facility == 'College / University / Boarding School':
            if len(self.affected_population) == 1:
                if int(row_df['Lab-confirmed influenza']) > 3:
                    pass
                elif int(row_df['Lab-confirmed influenza']) == 3:
                    if self.time_difference > 3:
                        self.issues.append(f'for confirmed case status if lab-confirmed influenza is 3, should be within 72 hours of each other.')
                elif int(row_df['Lab-confirmed influenza']) < 3:
                    self.issues.append(f'if lab-confirmed influenza cases are less than 3 - it should be Not a Case.')
            if len(self.affected_population) > 1:
                for i in range(len(self.affected_population)):
                    if self.count > 3:
                        if self.current_case_status != 'Confirmed':
                            self.issues.append(f'if lab-confirmed influenza cases are more than 3 - it should be confirmed case status.')
                        if self.current_case_status == 'Confirmed':
                            pass
                    elif self.count == 3:
                        if self.time_difference > 3:
                            self.issues.append(f'for confirmed case status if lab-confirmed influenza is 3, should be within 72 hours of each other.')
                        elif self.time_difference <= 3:
                            if self.current_case_status != 'Confirmed':
                                self.issues.append(f'if lab-confirmed influenza cases are 3 within 72 hours of each other - it should be confirmed case status.')
                    elif self.count < 3:
                        if self.current_case_status != 'Not a Case':
                            self.issues.append(f'if lab-confirmed influenza cases are less than 3 - it should be Not a Case.')
                        if self.current_case_status == 'Not a Case':
                            pass
        elif self.outbreak_reporting_facility == 'Event (wedding, etc.)':
            ili_assign_email = True
            ili_assign_email_id.append(self.inv_id)
            self.issues.append(f'Event outbreaks require manual review .')
            
        elif self.outbreak_reporting_facility == 'Health Care Workers':
            if self.current_case_status != 'Not a Case':
                self.issues.append(f'Health Care Worker outbreaks should be classified as Not a Case.')
                
        elif self.outbreak_reporting_facility == 'Institutional (workplace, jail, shelter, etc)':
            ili_assign_email = True
            ili_assign_email_id.append(self.inv_id)
            self.issues.append(f'Institutional outbreaks require manual review .')
            
        elif self.outbreak_reporting_facility == 'Outpatient Healthcare Facility':
            if self.current_case_status != 'Not a Case':
                self.issues.append(f'Outpatient Healthcare Facility outbreaks should be classified as Not a Case.')
                
        elif self.outbreak_reporting_facility == 'Restaurant':
            if self.current_case_status != 'Not a Case':
                self.issues.append(f'Restaurant outbreaks should be classified as Not a Case.')
                
        elif self.outbreak_reporting_facility == 'Summer Camp':
            if self.count >=1:
                if self.current_case_status == 'Confirmed':
                    pass
                elif self.current_case_status != 'Confirmed':
                    self.issues.append(f'if lab-confirmed influenza cases are at least 1 - it should be confirmed case status.')
            elif self.count < 1:
                if self.current_case_status != 'Not a Case':
                    self.issues.append(f'if lab-confirmed influenza cases are less than 1 - it should be Not a Case.')
            
        elif self.outbreak_reporting_facility == 'Long Term Care Facility':
            if len(self.affected_population)>1:
                ili_assign_email = True
                ili_assign_email_id.append(self.inv_id)
                self.issues.append(f'Long Term Care Facility outbreaks with multiple affected populations require manual review .')
            elif len(self.affected_population) == 1:
                if int(row_df['Lab-confirmed influenza']) >=2:
                    if self.current_case_status == 'Confirmed':
                        pass
                elif int(row_df['Lab-confirmed influenza']) < 2:
                    self.issues.append(f'At least 2 lab-confirmed influenza cases are required for confirmed status.')
                if  int(row_df['Lab-confirmed influenza'][i])  == 1  and not int(row_df['Population with ILI (no lab)'][i]):
                    self.issues.append(f'At least 2 lab-confirmed influenza cases are required for confirmed status cannot determine if its resident or staff.')
                    ili_assign_email = True
                    ili_assign_email_id.append(self.inv_id)
                elif not int(row_df['Lab-confirmed influenza'][i]) and int(row_df['Population with ILI (no lab)'][i]) == 1:
                    self.issues.append(f'At least 2 lab-confirmed influenza cases are required for confirmed status cannot determine if its resident or staff.')
                    ili_assign_email = True
                    ili_assign_email_id.append(self.inv_id)
                elif int(row_df['Lab-confirmed influenza'][i]) == 2:
                    if self.time_difference > 3:
                        if self.current_case_status == 'Confirmed':
                            self.issues.append(f'for confirmed case status if lab-confirmed influenza is 2, should be within 72 hours of each other.')
                        if self.current_case_status != 'Not a Case':
                            self.issues.append(f'if lab-confirmed influenza cases are 2 within 72 hours of each other - it should be not a case.')
                    elif self.time_difference <= 3:
                        if self.current_case_status != 'Confirmed':
                            self.issues.append(f'if lab-confirmed influenza cases are 2 within 72 hours of each other - it should be confirmed case status.')
                    elif self.time_difference <= 3:
                        if self.current_case_status == 'Confirmed':
                            pass'''
                
    def SendEmailToIliAssign(self, ili_assign_email_id):
        if ili_assign_email_id:
            body = ""
            body = f"At least 2 lab-confirmed influenza cases are required for confirmed status cannot determine if its resident or staff.\nThe following ILI Outbreak investigations {ili_assign_email_id} need to be reviewed and possibly reclassified to Probable:\n"
            if body:
                self.send_smtp_email("disease.reporting@maine.gov", 'ERROR REPORT: NBSbot(ILI Outbreak ELR Review) AKA ILIbot', body, 'ILI outbreak cases Manual Review email')
    

    def SendManualReviewEmail(self):
        """ Send email containing NBS IDs that required manual review."""
        if (len(self.not_a_case_log) > 0) | (len(self.lab_data_issues_log) > 0):
            subject = 'Cases Requiring Manual Review'
            email_name = 'manual review email'
            body = "COVID Commander,\nThe case(s) listed below have been moved to the rejected notification queue and require manual review.\n\nNot a case:"
            for id in self.not_a_case_log:
                body = body + f'\n{id}'
            body = body + '\n\nAssociated lab issues:'
            for id in self.lab_data_issues_log:
                body = body + f'\n{id}'
            body = body + '\n\n-Nbsbot'
            #self.send_smtp_email(recipient, cc, subject, body)
            self.send_smtp_email(self.covid_commander, subject, body, email_name)
            self.not_a_case_log = []
            self.lab_data_issues_log = []
    

    def SendILIOutbreakEmail(self, body,inv_id):
        message = EmailMessage()
        message.set_content(body)
        message['Subject'] = f'ILI Outbreak Bot {self.inv_id}'
        message['From'] = self.nbsbot_email
        message['To'] = ', '.join(["disease.reporting@maine.gov"])   #change email to disease.reporting
        smtpObj = smtplib.SMTP(self.smtp_server)
        smtpObj.send_message(message)
        print('sent email', self.inv_id)