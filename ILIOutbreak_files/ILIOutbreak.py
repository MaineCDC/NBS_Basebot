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
    """ A class to review ILIOutbreak cases in the notification queue.
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
        self.PopulationWithIli()
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
        self.affected_population = self.ReadTableToDF('//*[@id="ME8107"]//table') #  //*[@id="ME8107"]/tbody/tr[1]/td/table/tbody/tr/td[2], //*[@id="ME8107"]/tbody/tr[1]/td/table
        #self.lab_confirmed_values = []
        # initialize once (outside the loop)
        # Initialize once
        self.attack_rate_group_percent_list = []
        self.affected_population_type_list = []
        if self.affected_population.empty:
            self.issues.append('Affected population is blank.')
        for i, row in self.affected_population.iterrows():
            row_num = i + 1

            affected_population_type = row.get('Affected Population Type')
            if not affected_population_type:
                self.issues.append(f'Affected population type is blank for row {row_num}.')
                continue

            population_with_ili = row.get('Population with ILI (no lab)')
            if population_with_ili in [None, '']:
                self.issues.append(f'Population with ILI (no lab) is blank for row {row_num}.')
                continue

            lab_confirmed_influenza = row.get('Lab-confirmed influenza')
            if lab_confirmed_influenza in [None, '']:
                self.issues.append(f'Lab Confirmed Influenza is blank for row {row_num}.')
                continue

            total_population = row.get('Total Population of Group')
            if not total_population and self.outbreak_reporting_facility != 'Acute Care / Nosocomial':
                self.issues.append(f'Total Population of Group is blank for row {row_num}.')
                continue

            attack_rate_group = row.get('Attack Rate of Group')
            if attack_rate_group in [None, ''] and self.outbreak_reporting_facility != 'Acute Care / Nosocomial':
                self.issues.append(f'Attack Rate of Group is blank for row {row_num}.')
                continue

            # convert
            try:
                population_with_ili = int(population_with_ili)
                lab_confirmed_influenza = int(lab_confirmed_influenza)
                total_population = int(total_population or 0)
                attack_rate_group = int(attack_rate_group or 0)
            except ValueError:
                self.issues.append(f'Invalid numeric value in row {row_num}.')
                continue

            # Only now append (row is valid)
            self.affected_population_type_list.append(affected_population_type)

            if self.outbreak_reporting_facility != 'Acute Care / Nosocomial':
                calculated_rate = ((population_with_ili + lab_confirmed_influenza) / total_population * 100)
                calculated_rate = int(round(calculated_rate))
                self.attack_rate_group_percent_list.append(calculated_rate)

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
    
    def PopulationWithIli(self):
        self.population_with_ili_values = []
        self.affected_population = self.ReadTableToDF('//*[@id="ME8107"]/tbody/tr[1]/td/table/tbody/tr/td[2]') 
        for i in range(len(self.affected_population)):
            self.population_with_ili = self.affected_population.iloc[i]['Population with ILI (no lab)']
            if self.population_with_ili is not None:
                self.population_with_ili_values.append(self.population_with_ili)
        self.count_ili = []
        self.count_ili = [int(x) for x in self.population_with_ili_values if x is not None and str(x).strip() != '']
        self.count_ili_total = sum(self.count_ili)
            
    ### laboratory confirmation checks
    import re
    def LaboratoryConfirmation(self):
       self.laboratory_confirmation = self.ReadText('//*[@id="ME8108"]/tbody')
       counts_lab =  list(map(int,re.findall(r'(?:(?:Count|:)\s*)(\d+)',self.laboratory_confirmation)))
       lab_text_total = sum(counts_lab)
       if self.count != lab_text_total:
           self.issues.append(f'Sum of Lab-confirmed influenza in Affected Population ({self.count}) does not match total count in Laboratory Confirmation ({lab_text_total}).')
        
    def CaseStatusIliOutbreak(self):
        inv_id = self.ReadText('//*[@id="bd"]/table[3]/tbody/tr[2]/td[1]/span[2]')
        self.ili_assign_email = False
        self.ili_assign_email_id = []
        self.valid_affected_population_types = ['Staff','staff','Students','students']
        self.time_difference = (self.date_last_case_became_ill - self.date_first_case_became_ill).days
        if (self.outbreak_reporting_facility == 'School (K-12) or Daycare'):
            if self.current_case_status == 'Confirmed':
                if self.affected_population_type_list not in self.valid_affected_population_types:
                    self.issues.append('Affected Population Type must be Staff or Students.')
                elif len(self.affected_population) > 1: 
                    for i in range(len(self.affected_population)):
                        row_df = self.affected_population.iloc[i]
                        calculated_rate = ((int(row_df['Population with ILI (no lab)']) + int(row_df['Lab-confirmed influenza']))/ int(row_df['Total Population of Group'])* 100)
                        if row_df['Affected Population Type'] in self.valid_affected_population_types:
                            if calculated_rate < 7.5:
                                self.issues.append('incorrect case classification for school/daycare outbreaks:Attack Rate of Group must be greater or equal than 7.5%.')
                elif len(self.affected_population) == 1:
                    row_df = self.affected_population.iloc[0]
                    calculated_rate = ((int(row_df['Population with ILI (no lab)']) + int(row_df['Lab-confirmed influenza']))/ int(row_df['Total Population of Group'])* 100)
                    if row_df['Affected Population Type'] in self.valid_affected_population_types:
                        if calculated_rate < 7.5:
                            self.issues.append('incorrect case classification for school/daycare outbreaks:Attack Rate of Group must be greater or equal than 7.5%.')
                    elif row_df['Affected Population Type'] not in self.valid_affected_population_types:
                        self.issues.append('Affected Population Type must be Staff or Students.')
            elif self.current_case_status == 'Probable':
                self.issues.append('Probable case status is not allowed for school/daycare outbreaks.')
            elif self.current_case_status == 'Not a Case':
                if len(self.affected_population) > 1: 
                    for i in range(len(self.affected_population)):
                        row_df = self.affected_population.iloc[i]
                        calculated_rate = ((int(row_df['Population with ILI (no lab)']) + int(row_df['Lab-confirmed influenza']))/ int(row_df['Total Population of Group'])* 100)
                        if row_df['Affected Population Type'] in self.valid_affected_population_types:
                            if calculated_rate >= 7.5:
                                self.issues.append('incorrect case classification cannot be Not a Case.')
                elif len(self.affected_population) == 1:
                    row_df = self.affected_population.iloc[0]
                    calculated_rate = ((int(row_df['Population with ILI (no lab)']) + int(row_df['Lab-confirmed influenza']))/ int(row_df['Total Population of Group'])* 100)
                    if row_df['Affected Population Type'] in self.valid_affected_population_types:
                        if calculated_rate >= 7.5:
                            self.issues.append('incorrect case classification cannot be Not a Case.')
                            
        elif self.outbreak_reporting_facility == 'Acute Care / Nosocomial':
            if len(self.affected_population) > 1:
                self.ili_assign_email = True
                self.ili_assign_email_id.append(inv_id)
                self.issues.append('Acute Care / Nosocomial outbreaks with multiple affected populations require manual review .')
            elif len(self.affected_population) == 1:
                self.case2 = self.count_ili_total + self.count
                if self.count != 0 and self.case2 > 3:
                    if self.current_case_status != 'Confirmed':
                        self.issues.append(f'incorrect case classification for acute care / nosocomial outbreak- it should be confirmed case status.')
                    if self.current_case_status == 'Confirmed':
                        pass
                elif self.count != 0 and self.case2 == 3:
                    if self.time_difference > 3:
                        self.issues.append(f'for confirmed case status if lab-confirmed influenza is 3, should be within 72 hours of each other.')
                    elif self.time_difference <= 3:
                        if self.current_case_status != 'Confirmed':
                            self.issues.append(f'if lab-confirmed influenza and population with ili cases are 3 or more within 72 hours of each other - it should be confirmed case status.')
                elif self.count == 0 or self.case2 < 3:
                    if self.current_case_status != 'Not a Case':
                        self.issues.append(f'incorrect case classification for acute care / nosocomial outbreak - it should be Not a Case.')
                    elif self.current_case_status == 'Not a Case':
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
            self.ili_assign_email = True
            self.ili_assign_email_id.append(inv_id)
            self.issues.append(f'Event outbreaks require manual review .')
            
        elif self.outbreak_reporting_facility == 'Health Care Workers':
            if self.current_case_status != 'Not a Case':
                self.issues.append(f'Health Care Worker outbreaks should be classified as Not a Case.')
                
        elif self.outbreak_reporting_facility == 'Institutional (workplace, jail, shelter, etc)':
            self.ili_assign_email = True
            self.ili_assign_email_id.append(inv_id)
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
            if len(self.affected_population) > 1:
                self.ili_assign_email = True
                self.ili_assign_email_id.append(inv_id)
                self.issues.append('Long Term Care Facility outbreaks with multiple affected populations require manual review .')
            elif len(self.affected_population) == 1:
                row_df = self.affected_population.iloc[0]
                if self.current_case_status == 'Confirmed':
                    if int(row_df['Lab-confirmed influenza']) > 2:
                            pass
                    elif int(row_df['Lab-confirmed influenza']) < 2:
                        self.issues.append('At least 2 lab-confirmed influenza cases are required for confirmed status.')
                    elif int(row_df['Lab-confirmed influenza']) == 2:
                        if self.time_difference > 3:
                            if self.current_case_status == 'Confirmed':
                                self.issues.append('Does not meet  72 hour criteria.')
                            elif self.current_case_status != 'Not a Case':
                                self.issues.append('Does not meet  72 hour criteria.')
                        elif self.time_difference <= 3:
                            if self.current_case_status != 'Confirmed':
                                self.issues.append('lab-confirmed influenza cases are 2 within 72 hours of each other - it should be confirmed case status.')
                        elif self.time_difference <= 3:
                            if self.current_case_status == 'Confirmed':
                                pass
                if self.current_case_status == 'Probable':
                    if not int(row_df['Population with ILI (no lab)']):    
                        self.issues.append('Probable status requires at least 2 ILI (no lab) cases.')
                    elif int(row_df['Population with ILI (no lab)']) >= 2 and not int(row_df['Lab-confirmed influenza']):
                        pass
                    elif int(row_df['Population with ILI (no lab)']) >= 2 and int(row_df['Lab-confirmed influenza']) == 1:
                        self.issues.append('incorrect case classification.')
                    elif int(row_df['Population with ILI (no lab)']) < 2:
                        self.issues.append('Probable status requires at least 2 ILI (no lab) cases.')
                    elif int(row_df['Population with ILI (no lab)']) == 2 and int(row_df['Lab-confirmed influenza']) < 2:
                        if self.time_difference > 3:
                            if self.current_case_status == 'Probable':
                                self.issues.append('Does not meet  72 hour criteria.')
                            if self.current_case_status != 'Not a Case':
                                self.issues.append('Does not meet  72 hour criteria.')
                        elif self.time_difference <= 3:
                            if self.current_case_status != 'Probable':
                                self.issues.append('ILI (no lab) cases are 2 within 72 hours of each other - it should be probable case status.')
                        elif self.time_difference <= 3:
                            if self.current_case_status == 'Probable':
                                pass
                    elif int(row_df['Population with ILI (no lab)']) > 2 and int(row_df['Lab-confirmed influenza']) < 2:
                        pass
                elif int(row_df['Population with ILI (no lab)']) > 2 and int(row_df['Lab-confirmed influenza']) < 2:
                    if self.current_case_status != 'Not a Case':
                        self.issues.append('If at least 2 lab-confirmed influenza cases exist, status should be Not a case.')
                        
    def SendEmailToIliAssign(self):
        """ Send email containing NBS IDs that required manual review."""
        #self.ili_outbreak_investigator = ['vaishnavi.appidi@maine.gov', 'Anna.Krueger@maine.gov']
        if self.ili_assign_email_id:
            body = f"Need manual review for the below ILIOutbreak investigations,Investigation ids {self.ili_assign_email_id} "
            print(f"body", body)
            if body:
                self.send_smtp_email("disease.reporting@maine.gov", 'ERROR REPORT: NBSbot(ILI Outbreak ELR Review) AKA ILIbot', body, 'ILI outbreak cases Manual Review email')
                print('sent email to ili assign', self.ili_assign_email_id)

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
        message['Subject'] = f'ILI Outbreak Bot {inv_id}'
        message['From'] = self.nbsbot_email
        message['To'] = ', '.join(["disease.reporting@maine.gov"])   
        smtpObj = smtplib.SMTP(self.smtp_server)
        smtpObj.send_message(message)
        print('sent email', inv_id)