from Base import NBSdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException
from datetime import datetime
from fractions import Fraction
import re
from dateutil.relativedelta import relativedelta
from geopy.geocoders import Nominatim
import pandas as pd
from io import StringIO
from bs4 import BeautifulSoup
import smtplib
from email.message import EmailMessage
from tqdm import tqdm
import time
import traceback
import smtplib, ssl
from email.message import EmailMessage




class Anaplasma(NBSdriver):
    """ A class inherits all basic NBS functionality from NBSdriver and adds
    methods for reviewing COVID case investigations for data accuracy and completeness. """
    def __init__(self, production=False):
        super().__init__(production)
        self.num_approved = 0
        self.num_rejected = 0
        self.num_fail = 0

    def StandardChecks(self):
        self.Reset()
        self.initial_name = self.patient_name
        
        self.CheckFirstName()
        self.CheckLastName()
        self.CheckDOB()
        self.CheckAge()
        self.CheckAgeType()
        self.CheckCurrentSex()#removed Ana
        #self.CheckStAddr()
        street_address = self.CheckForValue( '//*[@id="DEM159"]', 'Street address is blank.')
        if any(x in street_address for x in ["HOMELESS", "NO ADDRESS", "NO FIXED ADDRESS", "UNSHELTERED"]):
            pass
        else: 
            self.CheckCity()
            self.CheckZip()
            self.CheckCounty()
            #self.CheckCityCountyMatch()
        self.CheckState()
        self.CheckCountry()
        self.CheckPhone()
        self.CheckEthnicity()
        self.CheckRaceAna()
        self.GoToTickBorne()
        self.CheckInvestigationStartDate()#removed Ana
        self.CheckReportDate()
        self.CheckCountyStateReportDate()
        if self.county:
            self.CheckCounty()                 #new code
        self.CheckJurisdiction()              #new code
        self.CheckInvestigationStatus()
        self.CheckInvestigatorAna()
        self.CheckInvestigatorAssignDateAna()
        self.CheckMmwrWeek()
        self.CheckMmwrYear()
        self.CheckReportingSourceType()
        self.CheckReportingOrganization()
        self.CheckConfirmationDate()
        self.CheckAdmissionDate() #new code to get admission date and compare to discharge
        self.CheckDischargeDate()                                   #new code, added this from covidcase review. modified method logic
        self.CheckIllnessDurationUnits()
        self.CheckHospitalization()
        self.CheckDeath()                         #removed '77' after parenthesis
        ###Anaplasma Specific Checks###
        self.CheckImmunosupressed()
        self.CheckLifeThreatening()
        #Check lab name, spelling is wrong but that is how it is defined in the legacy code
        self.CheckPreformingLaboratory()
        self.CheckTickBite()
        self.CheckPhysicianVisit()                                  #new code
        self.CheckSerology()
        self.CheckOutbreak()
        self.CheckSymptoms()#removed Ana
        self.CheckIllnessLength()
        self.CheckCase()
        # if self.CaseStatus == "Not a Case":
        #     continue
        self.CheckDetectionMethod() #new code                           #new code reject if not detectionmethod
        self.CheckConfirmationMethod() #removed Ana
    def CheckInvestigatorAssignDateAna(self):
            """ If an investigator was assigned then there should be an investigator
            assigned date. """
            if self.investigator_name:
                self.assigned_date = self.ReadDate('//*[@id="INV110"]')
                if not self.assigned_date:
                    self.issues.append('Missing investigator assigned date.')
                elif self.assigned_date and self.investigation_start_date:
                    if self.assigned_date < self.investigation_start_date:
                        self.issues.append('Investigator assigned date is before investigation start date.')

    
    ################# Anaplasma Specific Check Methods ###############################
        def CheckTickBite(self):
            """ If Tick bite is yes, need details """
            self.TickBiteIndicator = self.ReadText('//*[@id="ME23117"]')
            #if not self.TickBiteIndicator:                                           #code commented. not necessary to have tickbite history
                #self.issues.append('Missing tick bite history.')                    #code commented. not necessary
            if self.TickBiteIndicator == "Yes":
                self.TickBiteNote = self.ReadText('//*[@id="ME23119"]')
                if not self.TickBiteNote:
                    self.issues.append('History of tick bite, but no details.')
                    print(f"tick_bite: {self.TickBiteIndicator}")
        def CheckOutbreak(self):
            """ Outbreak should not be yes """
            self.OutbreakIndicator = self.ReadText('//*[@id="INV150"]')
            if self.OutbreakIndicator == "Yes":
                self.issues.append('Outbreak should not be yes.')
                print(f"out_break: {self.OutbreakIndicator}")
        def CheckImmunosupressed(self):
            """ If patient is immunosupressed, need condition info """
            self.ImmunosupressedIndicator = self.ReadText('//*[@id="ME24123"]')
            if self.ImmunosupressedIndicator == "Yes":
                self.ImmunosupressedNote = self.ReadText('//*[@id="ME15113"]')
                if not self.ImmunosupressedNote:
                    self.issues.append('Patient is immunosurpressed, but the condition is not listed.')
                    print(f"Immunosuppressed: {self.ImmunosupressedIndicator}")
        def CheckLifeThreatening(self):
            """ If patient has a life threatening condition, need condition info """
            self.LifeThreateningIndicator = self.ReadText('//*[@id="ME24117"]')
            if self.LifeThreateningIndicator == "Other":
                self.LifeThreateningNote = self.ReadText('//*[@id="ME24124"]')
                if not self.LifeThreateningNote:
                    self.issues.append('Patient has other life-threatening condition, but the condition is not listed.')
                    print(f"life_threatening: {self.LifeThreateningIndicator}")
        def CheckPhysicianVisit(self):                                                                                   #new method defined here. -JH
            """If patient saw physician, but there is no visit date, then reject case"""
            saw_physician = self.ReadText('//*[@id="ME8169"]')
            physician_visit_date = self.ReadDate('//*[@id="ME12169"]')
            if saw_physician == 'No':
                if not physician_visit_date:
                    self.issues.append("Case rejected: No physician visit date documented")
                    print(f"physician_visit_date: {physician_visit_date}")
            else:
                if not physician_visit_date:
                    self.issues.append("Case rejected: Physician visit date is missing despite seeing physician")
                    print(f"physician_visit_date: {physician_visit_date}")
                    
                    
        def CheckSerology(self):
            """ If patient has reported positive serology the serology section needs to be filled out. """
            #Serology info is only displayed if you click on the button next to the lab report. There could be more than one.
            html = self.find_element(By.XPATH, '//*[@id="ME24112"]/tbody/tr[1]/td/table/tbody/tr/td[2]/table').get_attribute('outerHTML')
            soup = BeautifulSoup(html, 'html.parser')
            self.Sero_table = pd.read_html(StringIO(str(soup)))[0]
            if len(self.Sero_table) > 0:
                if any(pd.isnull(self.Sero_table["Serology Collection Date"].values)):
                    self.issues.append('Patient has a reported serology test, but the collection date is not listed.')
                    print(f"serology_collection_date]: {self.Sero_table["Serology Collection Date"].values}")
                if any(pd.isnull(self.Sero_table["Serology Test Type"].values)):
                    self.issues.append('Patient has a reported serology test, but the test type is not listed.')
                    print(f"serology_test_type: {self.Sero_table["Serology Test Type"].values}")
                if any(pd.isnull(self.Sero_table["Serology Positive?"].values)):
                    self.issues.append('Patient has a reported serology test, but the result is not listed.')
                    print(f"serology_positive: {self.Sero_table["Serology Positive?"].values}")
        def CheckClinicallyCompatible(self):
            """ Check if a patient is clinically compatible and make sure they have the correct case status. """
            self.ClinicCompIndicator = self.ReadText('//*[@id="ME12174"]')
            self.ConfirmationMethod = self.ReadText('//*[@id="INV161"]')
            self.CaseStatus = self.ReadText('//*[@id="INV163"]')
            if self.CaseStatus == "Confirmed" and (self.ClinicCompIndicator != "Yes" or self.ConfirmationMethod != "Laboratory confirmed"):
                self.issues.append('Patient has a confirmed case status, but is not clinically compatible or does not have a confirmatory lab.')
            elif self.CaseStatus == "Probable" and (self.ClinicCompIndicator != "Yes" or self.ConfirmationMethod != "Laboratory report"):
                self.issues.append('Patient has a probable case status, but is not clinically compatible or does not only have a serology lab.')
            elif self.CaseStatus == "Suspect" and self.ClinicCompIndicator != "Unknown":
                self.issues.append('Patient has a suspected case status, but does not have unknown clinically compatiblity.')
            elif self.isnull(self.ConfirmationMethod) or self.isnull(self.CheckDetectionMethod):                         #new code, but may not need since function defined in covidcasereview
                self.issues.append('Confirmation Method is Missing')                                                     #new code
                
        def CheckIllnessLength(self):
            """ Check if a patient has an illness onset date. """
            self.IllnessOnset = self.ReadText('//*[@id="INV137"]')
            # if not self.IllnessOnset:
            #     self.issues.append('Patient is missing illness onset date.')
            #     print(f"Illness_length: {self.IllnessOnset}")
            
        def CheckSymptoms(self):
            """ Check patient symptoms, Patient needs one if they have a DNA test or two if there have an antibody test. """
            self.ClinicCompIndicator = self.ReadText('//*[@id="ME12174"]')
            if self.ClinicCompIndicator == 'Unknown':                                                                       #new code, this exits early without performing symptom checks if the indicator is unknown
                return                                                                                                      #new code
            self.Fever = self.CheckForValue('//*[@id="ME14101"]','Fever should not be left blank.')
            #self.Rash = self.ReadText('//*[@id="ME23100"]')
            self.Headache = self.CheckForValue('//*[@id="ME23101"]','Headache should not be left blank.')
            self.Myalgia = self.CheckForValue('//*[@id="ME23102"]','Myalgia should not be left blank.')
            self.Anemia = self.CheckForValue('//*[@id="ME24118"]','Anemia should not be left blank.')
            self.Leukopenia = self.CheckForValue('//*[@id="ME24119"]','Leukopenia should not be left blank.')
            self.Thrombocytopenia = self.CheckForValue('//*[@id="ME24120"]','Thrombocytopenia should not be left blank.')
            self.ElevatedHepaticTransaminase =  self.CheckForValue('//*[@id="ME24121"]','Elevated Heaptic Transaminases should not be left blank.')
            #self.Eschar = self.CheckForValue('//*[@id="ME24125"]','Eschar should not be left blank.')
            self.Chills =  self.CheckForValue('//*[@id="ME24126"]','Sweats/Chills should not be left blank.')
            #self.Sweats = self.ReadText('//*[@id="ME24127"]')
            self.FatigueMalaise = self.CheckForValue('//*[@id="ME18116"]','Fatigue/Malaise should not be left blank.')
            #self.ElevatedCRP = self.CheckForValue('//*[@id="NBS729"]','CRP Interpretation should not be left blank.')
            self.ElevatedCRP = self.ReadText('//*[@id="NBS729"]')
            self.symptoms_list = [self.Fever, self.Chills, self.Headache, self.Myalgia, self.FatigueMalaise, self.Anemia, self.Leukopenia, self.Thrombocytopenia, self.ElevatedHepaticTransaminase, self.ElevatedCRP]
            if self.ClinicCompIndicator == "Yes" and any(symptom == 'Yes' for symptom in self.symptoms_list):
                return
            else:
                self.issues.append("Clinically compatible illness is 'Yes' but no symptom is 'Yes'")
                print(f"symptoms__clinically_compatible: {self.ClinicCompIndicator}")

        def CheckCase(self):
            """ Check if a patient's case status matches the case definition using test type and symptoms. """
            self.CaseStatus = self.ReadText('//*[@id="INV163"]')
            self.DNATest = self.ReadText('//*[@id="ME24175"]')
            self.DNAResult = self.ReadText('//*[@id="ME24149"]')
            self.AntibodyTest = self.ReadText('//*[@id="ME24115"]')
            has_any_symptom = any(symptom == 'Yes' for symptom in self.symptoms_list)
            has_no_symptom = all(symptom != 'Yes' for symptom in self.symptoms_list)
            if has_any_symptom and self.CaseStatus != "Confirmed":
                self.issues.append("Meets case definition for a confirmed case but is not a confirmed case.")
                self.CorrectCaseStatus = "Confirmed"

            elif self.CaseStatus == "Not a Case":
                return
            
            elif self.ClinicCompIndicator == 'unknown' and self.CaseStatus != 'probable':
                self.issues.append("Clinically compatible is unknown but case status isn't probable")
                self.CorrectCaseStatus = "Probable"
                print(f"case_status: {self.CaseStatus}")

            elif self.Fever == "Yes" and self.Headache == "Yes" or self.Myalgia == "Yes" or self.FatigueMalaise == "Yes" or self.Anemia == "Yes" or self.Leukopenia == "Yes" or self.Thrombocytopenia == "Yes" or self.ElevatedHepaticTransaminase == "Yes" or self.ElevatedCRP == "Yes":
                if self.CaseStatus != "Probable":
                    self.issues.append("Meets case definition for a probable case but is not a probable case.")
                    self.CorrectCaseStatus = "Probable"
        
            elif self.DNAResult == "Yes" and self.DNATest == "Yes":
                if has_any_symptom and self.CaseStatus != "Confirmed":
                        self.issues.append("Meets case definition for a confirmed case but is not a confirmed case.")
                        self.CorrectCaseStatus = "Confirmed"
                        print(f"case_status: {self.CaseStatus}")
                elif has_no_symptom and self.CaseStatus != "Not a Case" and self.CaseStatus != "Suspect":                                                                             #new code. changed from 'or' to 'and' statement
                        self.issues.append("Does not meet the case definition, but does not have Not a Case or Suspect status.")
                        self.CorrectCaseStatus = "Not a Case or  Suspect"
                        print(f"case_status: {self.CaseStatus}")
            elif any(self.Sero_table["Serology Positive?"] == "Yes"):
                titer_value = None
                # if re.search(r"NaN", str(self.Sero_table["Titer Value"])):
                #     print(f"titer: {str(self.Sero_table["Titer Value"])}")
                #     titer_value = 0
                try:
                    if re.search(r":", str(self.Sero_table["Titer Value"])):
                        print(f"titer1: {str(self.Sero_table["Titer Value"])}")
                        val = str(self.Sero_table["Titer Value"]).split("    ")[1].split(":")
                        print(f"titer2: {val}")
                        titer_value = Fraction(int(val[0].replace("\nName", "")), int(val[1].replace("\nName", "")))
                        print(f"titer3: {titer_value}")
                    else:
                        titer_value = int(self.Sero_table["Titer Value"])
                except Exception as e:
                    print(f"error titer_value: {str(self.Sero_table["Titer Value"])}: {str(e)}")
                    titer_value = 0

                if float(titer_value) < 128:
                    if self.CaseStatus != "Not a Case":
                        self.issues.append("Does not meet the case definition, but does not have Not a Case status.")
                        self.CorrectCaseStatus = "Not a Case"
                        print(f"case_status: {self.CaseStatus}")
                else:
                    if has_no_symptom and self.CaseStatus != "Suspect":
                            self.issues.append("Does not meet the case definition, but does not have Suspect status.")
                            self.CorrectCaseStatus = "Suspect"
                            print(f"case_status: {self.CaseStatus}")
                    elif self.Fever == "Yes":
                        if has_any_symptom and self.CaseStatus != "Probable":
                                self.issues.append("Meets case definition for a probable case but is not a probable case.")
                                self.CorrectCaseStatus = "Probable"
                                print(f"case_status: {self.CaseStatus}")
                        elif has_no_symptom and self.CaseStatus != "Not a Case":
                                self.issues.append("Does not meet the case definition, but does not have Not a Case status.")
                                self.CorrectCaseStatus = "Not a Case"
                                print(f"case_status: {self.CaseStatus}")
                    else:
                        if self.Chills == "Yes":
                            if has_any_symptom and self.CaseStatus != "Probable":
                                self.issues.append("Meets case definition for a probable case but is not a probable case.")
                                self.CorrectCaseStatus = "Probable"
                                print(f"case_status: {self.CaseStatus}")
                            else:
                                if (self.Headache == "Yes" and self.Myalgia == "Yes") or (self.Headache == "Yes" and self.FatigueMalaise == "Yes") or (self.FatigueMalaise == "Yes" and self.Myalgia == "Yes"):
                                    if self.CaseStatus != "Probable":
                                        self.issues.append("Meets case definition for a probable case but is not a probable case.")
                                        self.CorrectCaseStatus = "Probable"
                                        print(f"case_status: {self.CaseStatus}")
                                else:
                                    if self.CaseStatus != "Not a Case":
                                        self.issues.append("Does not meet the case definition, but does not have Not a Case status.")
                                        self.CorrectCaseStatus = "Not a Case"
                                        print(f"case_status: {self.CaseStatus}")
                        elif self.Chills != "Yes":
                            if self.CaseStatus != "Not a Case":
                                self.issues.append("Does not meet the case definition, but does not have Not a Case status.")
                                self.CorrectCaseStatus = "Not a Case"
                                print(f"case_status: {self.CaseStatus}")
            else:
                if self.CaseStatus != "Not a Case":
                    self.issues.append("Does not meet the case definition, but does not have Not a Case status.")
                    self.CorrectCaseStatus = "Not a Case"

        
        
        def SendAnaplasmaEmail(self, body, inv_id):
            message = EmailMessage()
            message.set_content(body)
            message['Subject'] = f'AnA Bot {inv_id}'
            message['From'] = self.nbsbot_email
            message['To'] = ', '.join(["disease.reporting@maine.gov"])
            smtpObj = smtplib.SMTP(self.smtp_server)
            smtpObj.send_message(message)
            print('sent email', inv_id)