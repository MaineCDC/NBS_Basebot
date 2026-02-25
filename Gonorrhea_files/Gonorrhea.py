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

class Gonorrhea(NBSdriver):
    """ A class to review Gonorrhea cases in the notification queue.
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
        self.initial_name = self.patient_name
        
        # Check Patient Tab
        self.CheckFirstName()
        self.CheckLastName()
        self.CheckDOB()
        self.CheckAge()
        self.CheckCurrentSexGonorrhea()
        street_address = self.CheckForValue( '//*[@id="DEM159"]', 'Street address is blank.')
        if any(x in street_address for x in ["HOMELESS", "NO ADDRESS", "NO FIXED ADDRESS", "UNSHELTERED"]):
            pass
        else: 
            self.CheckCity()
            self.CheckZip()
            self.CheckCounty()
        self.CheckState()
        self.CheckCountry()
        self.CheckEthnicity()
        self.CheckRaceAna()   #### Check code for race 
     
        # Read Associated labs
        self.GoToSupplementalinfo()
       
        self.ReadAssociatedLabs()# add associated treatment
        self.AssociatedTreatments()
        #self.AssignLabTypes()
        #self.DetermineCaseStatus()
        self.GetCollectionDate()
        self.GetReceivedDate()

        ### navigate to Case Info Tab
        self.GoToCaseInfo()
        
        self.CheckJurisdiction()
        self.CheckProgramArea()
        self.CheckReferralBasis()
        self.CheckInvestigationStartDate()
        self.CheckInvestigationStatus()
        self.CheckSharedIndicator()
        #self.CheckStateCaseID()
        ##investigator info
        self.CheckInvestigator()
        #self.CheckInvestigatorAssignDate()
        # reporting info
        self.CheckReportDate()
        self.CheckCountyStateReportDate()
        self.CheckReportingSourceType()
        self.CheckReportingOrganization()
        self.CheckReportingProvider()
        self.CheckReportingOrderingClinic()  # reporting ordering clinic
        #self.CheckPreformingLaboratory()    #laboratory name
        #self.CheckDateSpecimen()            #date_specimen
        #self.CheckSterileSite()             #sterile site
        self.CheckPhysician()               #physician
        self.CheckLaboratoryInformation()  #laboratory information
        self.CheckPatientHospitalized()
        if self.hospitalization_indicator == 'Yes':
            self.CheckAdmissionDate()
            self.CheckDischargeDate()
        self.CheckDieFromIllness()
        #if self.patient_die_from_illness == 'Yes':
            #self.CheckDeathDate()    
        #self.CheckDiagnosisDate()
        #self.CheckSymptomDates()            #symptoms
        #self.CheckTypeofinfection()         #type of infection
        #self.CheckUnderlyingConditions()    #underlying conditions
        #self.CheckHealthcareAssociations()  #healthcare association  
        #self.CheckHighRiskExposure()        #high risk exposure      
        #self.CheckHypoTension()             #hypotension
        #self.CheckDiseaseAcquisition()
        self.CheckCaseStatusNew()           #CaseStatusNew
        self.CheckMmwrWeek()
        self.CheckMmwrYear()
        
        ### navigate to Case Management tab
        self.GoToCaseManagementTab()
        self.CheckIntialFollowUp()
        self.NotificationOfExposureInformation()
        self.FieldFollowUpInformation()
        self.InterviewCaseAssignment()
        self.CaseClosure()
        
        ## navigate to core Info tab
        self.GoToCoreInfoTab()
        self.CheckPregnancy()
        self.PatientHivStatus()
        self.RiskFactors()
        self.PartnersInfo()
        self.StdHistory()
        self.PartnerServiceInformation()

        ## navigate to contact Records tab
        self.GoToContactRecordsTab()
            
        ## check for case classification
        self.CheckCaseClassification()
            
    def GoToSupplementalinfo(self):
        """ Within a patient profile navigate to the Demographics tab."""
        supplemental_info_path = '//*[@id="tabs0head4"]'
        WebDriverWait(self,self.wait_before_timeout).until(EC.presence_of_element_located((By.XPATH, supplemental_info_path)))
        self.find_element(By.XPATH,'//*[@id="tabs0head4"]').click()
    
    def AssociatedTreatments(self):
        import re
        """ Check for associated treatments."""
        self.disposition = self.ReadText('//*[@id="NBS173"]')
        self.associated_treatments = self.ReadTableToDF('//*[@id="viewSupplementalInformation2"]/tbody')
        if self.disposition in ['A - Preventative Treatment', 'C - Infected, Brought to Treatment', 'E - Previously Treated for This Infection']:
            if len(self.associated_treatments) == 0:
                self.issues.append('Associate treatments.')
            for index, row in self.associated_treatments.iterrows():
                elements = row['Treatment'].lower().split(', ')
                treatment_name = elements[0] if elements else ''
                dose = elements[1] if len(elements) > 1 else ''
                treatment = elements[2] if len(elements) > 2 else ''
                dose_type = elements[3] if len(elements) > 3 else ''
                dose_number = int(re.search(r'\d+', dose).group())
                dose_unit = 'g'
                if 'mg' in dose.lower():
                    dose_unit = 'mg'
                
                if dose_unit == 'mg' and dose_number < 500 and treatment_name == 'ceftriaxone' :
                    self.issues.append('Ceftriaxone dose is less than 500mg .')                    
                elif dose_unit == 'g' and dose_number < 0.5 and treatment_name == 'ceftriaxone' :
                    self.issues.append('Ceftriaxone dose is less than 500mg .')
                
                if dose_unit == 'mg' and dose_number < 800 and treatment_name == 'cefixime' :
                    self.issues.append('Cefixime dose is less than 800mg .')
                elif dose_unit == 'g' and dose_number < 0.8 and treatment_name == 'cefixime' :
                    self.issues.append('Cefixime dose is less than 800mg .')

                #add azithromycin
                if dose_unit == 'mg' and dose_number <240 and treatment_name == 'gentamicin':
                    self.issues.append('Gentamicin dose is less than 240mg .')
                elif dose_unit == 'g' and dose_number < 0.24 and treatment_name == 'gentamicin':
                    self.issues.append('Gentamicin dose is less than 240mg .')

                '''if treatment_name:
                    pass
                if row['Treatment'].lower() == 'ceftriaxone' and row['Route of Administration'].lower() != 'im':
                    self.issues.append('Ceftriaxone treatment is not associated with IM route.')
                if row['Treatment'].lower() == 'azithromycin' and row['Route of Administration'].lower() != 'oral':
                    self.issues.append('Azithromycin treatment is not associated with oral route.')'''
                    
    def CheckProgramArea(self):
        """ Program area must be Airborne. """
        program_area = self.CheckForValue('//*[@id="INV108"]','Program Area is blank.')
        if program_area != 'STDs':
            self.issues.append('Program Area is not "STDs".')
    
    def CheckReferralBasis(self):
        """ Referral basis must be 'Lab Report' or 'Provider Report'."""
        self.referral_basis = self.ReadText('//*[@id="NBS110"]')
        if not self.referral_basis:
            self.issues.append('Referral basis is blank.')
    
    def CheckReportingOrderingClinic(self):
        """ Ensure reporting ordering clinic is not empty. """
        self.reporting_ordering_clinic = self.ReadText('//*[@id="NBS291"]')
        if not self.reporting_ordering_clinic:
            self.issues.append('Reporting ordering clinic is blank.')
    
    def CheckLaboratoryInformation(self):        
        """ Check for laboratory information."""
        was_extragential_testing_done = self.ReadText('//*[@id="ME10098100"]')
        laboratory_testing = self.ReadTableToDF('//*[@id="ME10098104"]/tbody/tr[1]/td/table/tbody')
        laboratory_name = self.ReadText('//*[@id="ME6105"]')
        test_type = self.ReadText('//*[@id="ME10098101"]')
        other_test_type = self.ReadText('//*[@id="ME15111"]')
        specimen_collection_date = self.ReadDate('//*[@id="ME10084122"]')
        test_result = self.ReadText('//*[@id="ME8165"]')
        specimen_source_tested = self.ReadText('//*[@id="ME10098102"]')
        other_type_sample = self.ReadText('//*[@id="ME10091107"]')
        if not was_extragential_testing_done:
            self.issues.append('Was extragenital testing done? is blank.')
        elif was_extragential_testing_done.lower() == 'yes':
            if laboratory_testing['Test Result'].lower().str.contains('positive') and ["urine|endocervix|urethra"] not in str(laboratory_testing['What specimen source was tested']).lower():
                self.issues.append('Correct extragential testing question')
        elif was_extragential_testing_done.lower() == 'no':
            if laboratory_testing['Test Result'].lower().str.contains('positive') and ["urine|endocervix|urethra"] in str(laboratory_testing['What specimen source was tested']).lower():
                self.issues.append('Correct extragential testing question')
        if not laboratory_name:
            self.issues.append('Laboratory name is blank.')
        if not test_type:
            self.issues.append('Test type is blank.')
        elif test_type.lower() == 'other':
            if not other_test_type:
                self.issues.append('Other test type is blank.')
        if not specimen_collection_date:
            self.issues.append('Specimen collection date is blank.')
        if test_result not in ['Positive', 'Negative', 'Unknown']:
            self.issues.append('Missing lab test result.')
        if not specimen_source_tested:
            self.issues.append('Specimen source tested is blank.')
        elif specimen_source_tested.lower() == 'other':
            if not other_type_sample:
                self.issues.append('Other type sample is blank.')

#################### Housing Check Methods ###################################
    def CheckCongregateSetting(self):
        """ Check if a patient lives in congregate setting."""
        if self.site == 'https://nbstest.state.me.us/':
            xpath = '//*[@id="95421_4"]'
        else:
            xpath = '//*[@id="ME3130"]'
        self.cong_setting_indicator = self.ReadText(xpath)
        if self.investigator:
            if (self.investigator_name in self.outbreak_investigators) & (self.cong_setting_indicator not in ['Yes', 'No']):
                self.issues.append('Congregate setting question must be answered with "Yes" or "No".')
            elif (self.ltf != 'Yes') & (not self.cong_setting_indicator):
                self.issues.append('Congregate setting status must have a value.')


#################### Hospital Check Methods ###################################
    def CheckPatientHospitalized(self):
        #check if patient is hospitalized for this illness
        self.hospitalization_indicator = self.ReadText('//*[@id="INV128"]')
        self.hospital_name = self.ReadText('//*[@id="INV184"]')
        if not self.hospitalization_indicator:
            self.issues.append('Hospitalized for this illness is blank.')
        elif self.hospitalization_indicator == 'Yes' and not self.hospital_name:
            self.issues.append('Hospitalized for this illness is yes but hospital name is blank.')
            
    def CheckAdmissionDate(self):
        #Check for hospital admission date.
        self.admission_date = self.ReadDate('//*[@id="INV132"]')
        if not self.admission_date:
            self.issues.append('Admission date is missing.')
        elif self.hospitalization_indicator == 'Yes' and not self.admission_date:
            self.issues.append('Hospitalized for this illness is yes but admission date is blank.')
        elif self.admission_date and self.admission_date > self.now:
            self.issues.append('Admission date cannot be in the future.')

    def CheckDischargeDate(self):
        """ Check for hospital discharge date."""
        self.duration_stay_inhosipital = self.ReadText('//*[@id="INV134"]')
        if self.discharge_date and not self.duration_stay_inhosipital:
            self.issues.append('Discharge date is present but duration of stay in hospital is blank.')
        if self.patient_die_from_illness == "Yes" and self.hospitalization_indicator == "Yes":
            if not self.discharge_date:                                                         #commented out
                self.issues.append('patient die from illness and patient hospitalized is yes, Discharge date is blank.')   #commented out
        if self.admission_date:
            if self.discharge_date and self.discharge_date < self.admission_date:
                self.issues.append('Discharge date must be after admission date.')
        elif self.discharge_date > self.now:
            self.issues.append('Discharge date cannot be in the future.')
    
    
    def CheckDeathDate(self):
        """ Death date must be present."""
        death_date = self.ReadDate('//*[@id="INV146"]')
        if not death_date:
            self.issues.append('Date of death is blank.')
        elif death_date > self.now:
            self.issues.append('Date of death date cannot be in the future')


    def CheckSharedIndicator(self):
        """ Ensure shared indicator is yes. """
        shared_indicator = self.ReadText('//*[@id="NBS_UI_19"]/tbody/tr[8]/td[2]')
        if shared_indicator.lower() != 'yes':
            self.issues.append('Shared indicator not selected.')


########################### Parse and process labs ############################
    def ReadAssociatedLabs(self):
        """ Read table of associated labs."""
        self.labs = self.ReadTableToDF('//*[@id="viewSupplementalInformation1"]/tbody')
        self.name_match = False
        for index in range(len(self.labs)):
            row_df = self.labs.iloc[[index]]
            if row_df['Test Results'].str.contains(' gonorrhoeae', na=False, case=False).any():
                self.labs = self.labs.loc[index]
                self.name_match = True
                break
        if not self.name_match:
            self.labs = pd.DataFrame()
            self.issues.append('Test results does not have  gonorrhoeae.')
     

    def GetReceivedDate(self):
        """Find earliest report date by reviewing associated labs"""
        #self.current_report_date = self.ReadDate('//*[@id="INV111"]')
        if not self.name_match:
            self.issues.append('No associated labs found,Cant determine Report date.')
        elif self.labs['Date Received'] == 'Nothing found to display.':
            self.received_date = datetime(1900, 1, 1).date()
        else:
            try:
                self.labs['Date Received'] = pd.to_datetime(self.labs['Date Received'],format = '%m/%d/%Y %I:%M %p').date()
            except Exception as e:
                self.labs['Date Received'] = pd.to_datetime(self.labs['Date Received'], errors='coerce').date()  #format = '%m/%d/%Y%I:%M %p',
            self.received_date = self.labs['Date Received']

    def GetCollectionDate(self):
        """Find earliest collection date by reviewing associated labs"""
        if not self.name_match:
            self.issues.append('No associated labs found,Cant determine collection date.')
        elif self.labs['Date Collected'] == 'Nothing found to display.':
            self.collection_date = datetime(1900, 1, 1).date()
        else:
            # Check for any associated labs missing collection date:
            # 1. Set collection date to 01/01/2100 to avoid type errors.
            # 2. Log patient id for manual review.
            no_col_dt_labs = True if self.labs['Date Collected'] == 'No Date' else False
            #date_specimen = self.ReadDate('//*[@id="ME8117"]')
            if no_col_dt_labs:
                self.labs['Date Collected'] = '01/01/2100'
                self.issues.insert(0,'**SOME ASSOCIATED LABS MISSING COLLECTION DATE: CENTRAL EPI REVIEW REQUIRED**')
                self.lab_data_issues_log.append(self.ReadPatientID())   
            self.labs['Date Collected'] = pd.to_datetime(self.labs['Date Collected'], format = '%m/%d/%Y').date()
            self.collection_date = self.labs['Date Collected']
            
    
############### Preforming Lab Check Methods ##################################
    # def CheckPreformingLaboratory(self):
    #     """ Ensure that preforming laboratory is not empty. """
    #     reporting_organization = self.ReadText('//*[@id="ME6105"]')
    #     if not reporting_organization:
    #         self.issues.append('Performing laboratory is blank.')


    def CheckSterileSite(self):
        self.current_case_status = self.ReadText('//*[@id="INV163"]')
        sterile_site = self.ReadText('//*[@id="ME127000"]')
        self.non_sterile_site = self.ReadText('//*[@id="ME127002"]')
        if self.current_case_status == 'Not a Case' and not sterile_site:
            pass
        elif not sterile_site :
            self.issues.append('No sterile site is listed.')
        elif sterile_site.lower() == 'Other normally sterile site':
            other_sterile_site = self.CheckForValue('//*[@id="ME127001"]','Other sterile site is blank')  
            #non_sterile_site = self.CheckForValue('//*[@id="ME127002"]','Other sterile site is blank')  
            if not other_sterile_site:
                self.issues.append('Other normally sterile site(specify) is selected but is not specified.')

    def CheckPhysician(self):
        """ Ensure that physician is not empty. """
        self.physician = self.ReadText('//*[@id="INV182"]')
        if not self.physician:
            self.issues.append('Physician is blank.')
            
            #check for no , yes or unkown- leave all others 
###############Condition#############
    def CheckDiagnosisDate(self):
        """ Check if diagnosis date is present and matches earliest date from
        associated labs. """
        diagnosis_date = self.ReadDate('//*[@id="INV136"]')
        if not diagnosis_date:
            self.issues.append('Diagnosis date is missing.')
        else:
            if diagnosis_date > self.now:
                self.issues.append('Diagnosis date cannot be in the future.')
            if diagnosis_date < self.onset_illness_date:
                self.issues.append('Diagnosis date cannot be before onset illness date.')
            
    def CheckSymptomDates(self):
        """ Ensure date of symptom onset, resolution, and current symptom status
        are consistent."""
        self.illness_end_date = self.ReadDate('//*[@id="INV138"]')
        self.patient_die_from_illness =  self.ReadText('//*[@id="INV145"]')
        death_date = self.ReadDate('//*[@id="INV146"]')
        self.is_patient_deceased =self.ReadText('//*[@id="DEM127"]')
        if not self.onset_illness_date:
            self.issues.append('Illness onset date is blank.')
        if self.patient_die_from_illness == 'Yes' and not self.illness_end_date:
            self.issues.append('patient died due to illness is yes but Illness end date is blank.')
        if self.illness_end_date and self.onset_illness_date and self.illness_end_date < self.onset_illness_date:
            self.issues.append('Illness end date cannot be before onset date.')
        
    def CheckIllness_Duration(self):
            """ Ensure if there is a number for illness duration that there is also an illness duration units.  Added Sept 2022 to account for notifications that were failing.STILL NEED TO FIX!!!"""
            Illness_Duration = self.ReadText('//*[@id="INV139"]')
            if Illness_Duration == 'Yes':
                Illness_Duration_Units = self.ReadDate('//*[@id="INV140"]')
                if (not Illness_Duration_Units):
                    self.issues.append("If ilness duration has a number then illness duration units must be specified.")
    
    
    def CheckDieFromIllness(self):
        """ Died from illness should be yes or no. """
        self.current_case_status = self.ReadText('//*[@id="INV163"]')
        self.patient_die_from_illness =  self.ReadText('//*[@id="INV145"]')
        is_patient_deceased=self.ReadText('//*[@id="DEM127"]')
        patient_deceased_date = self.ReadDate('//*[@id="DEM128"]')
        death_date = self.ReadDate('//*[@id="INV146"]')
        self.discharge_date = self.ReadDate('//*[@id="NBS_INV_GENV2_UI_3"]/tbody/tr[4]/td[2]|//*[@id="INV133"]')
        if self.current_case_status != 'Not a Case':
            if not self.patient_die_from_illness:
                self.issues.append('"Did the patient die from this illness" needs a response, yes, no or unknown.')
            elif self.patient_die_from_illness.lower() == 'yes':
                if not is_patient_deceased:
                    self.issues.append('Patient died from illness is yes but patient deceased is blank.')
                if not death_date:
                    self.issues.append('Patient died from illness is yes but death date is blank.')
                elif is_patient_deceased.lower() == 'no':
                    self.issues.append('Patient died from illness is yes but patient deceased is no.')
                if not patient_deceased_date:
                    self.issues.append('Patient died from illness is yes but patient deceased date is blank.')
                if death_date and patient_deceased_date != death_date:
                    self.issues.append('Patient died from illness is yes, patient deceased date should be the same as death date.') 
                if patient_deceased_date > self.now :
                    self.issues.append('Patient died from illness is yes but patient deceased date cannot be in the future.') 
                if death_date and self.illness_end_date and death_date != self.illness_end_date:
                    self.issues.append('Patient died from illness is yes, death date should be the same as illness end date.')   
            elif self.patient_die_from_illness.lower() == 'unknown':
                if self.hospitalization_indicator.lower() == 'no':
                    self.issues.append('Patient died from illness is unknown but patient hospitalized is no.')
                elif self.hospitalization_indicator.lower() == 'yes' and self.discharge_date:
                    self.issues.append('Patient died from illness is unknown but patient hospitalized is yes and discharge date is not blank.')
                if self.illness_end_date:
                    self.issues.append('Patient died from illness is unknown but illness end date is not blank.')
            elif self.patient_die_from_illness.lower() == 'no':
                if self.hospitalization_indicator.lower() == 'yes' or (self.hospitalization_indicator.lower() == 'no' and self.discharge_date):
                    self.issues.append('Patient died from illness is no but patient hospitalized is yes or discharge date is not blank.')
                    
    def CheckTypeofinfection(self):
        Type_of_infection = self.ReadText('//*[@id="ME128016"]')
        if not Type_of_infection  and self.current_case_status != 'Not a Case':
            self.issues.append("infection is not selected and casestatus is not not a case.")
        elif Type_of_infection.lower() == 'none' and self.current_case_status == 'Not a Case':
            self.issues.append("Type of infection is none and case status isn't not a case.")
        elif Type_of_infection == 'Other':
            other_type_infection = self.ReadText('//*[@id="ME128017"]')
            if not other_type_infection:
                self.issues.append('Other type of infection is blank.')
            elif other_type_infection.lower() in ["not invasive","non invasive","non-invasive","not sterile","non sterile","non-sterile"] and self.current_case_status != 'Not a Case':
                self.issues.append('other type of infection is {other_type_infection} but case status is not not a case.')
            elif other_type_infection:
                pass
    
    def CheckCurrentSexGonorrhea(self):
        """ Ensure patient current sex is not blank. """
        self.patient_current_sex = self.ReadText('//*[@id="DEM113"]') 
        self.patient_birth_sex = self.ReadText('//*[@id="DEM114"]')
        self.unknown_reason = self.ReadText('//*[@id="NBS272"]')
        self.transgender_information = self.ReadText('//*[@id="NBS274"]')
        self.additional_gender = self.ReadText('//*[@id="NBS213"]')
        if not self.patient_current_sex:
            self.issues.append('patient Sex is blank.')
        elif ((self.patient_current_sex and self.patient_birth_sex) and (self.patient_current_sex != self.patient_birth_sex)):
            if not self.transgender_information or not self.additional_gender:
                self.issues.append('Current sex and birth sex are not the same, provide transgender or additional gender information.')
        elif self.patient_current_sex.lower() == 'unknown':
            if not self.unknown_reason or not self.transgender_information or not self.additional_gender:
                self.issues.append('Current sex is unknown with no additional information.')
            
                 
    def CheckPregnancy(self):
        """ Check if patient is pregnant. """
        pregnant_status = self.ReadText('//*[@id="INV178"]')
        if self.patient_current_sex and self.patient_current_sex == 'Female' and not pregnant_status:
            self.issues.append('When current sex is listed as female  prgnancy status should be yes, no, or unknown')
            
    def CheckUnderlyingConditions (self):
        """ Check if patient has underlying conditions. """
        Did_underlying_condition = self.ReadText('//*[@id="INV235"]')
        underlying_condition_yes_explain = self.ReadText('//*[@id="ME15113"]')
        underlying_condition = self.ReadText('//*[@id="ME144040"]')
        if self.current_case_status != 'Not a Case':
            if not Did_underlying_condition:
                self.issues.append('Underlying condition is blank.')        
            elif Did_underlying_condition == 'Yes':
                if not underlying_condition_yes_explain:
                    self.issues.append('Underlying condition is yes but explanation is not filled.')
                if underlying_condition == 'None' or underlying_condition == 'Unknown':
                    self.issues.append('underlying condition exists but underlying condition is none or unknown." .')
                if not underlying_condition :
                    self.issues.append('Did Underlying condition exist is yes but underlying condition  is blank.')
            else:
                if Did_underlying_condition.lower() in ['no','unknown']:
                    if underlying_condition_yes_explain and underlying_condition_yes_explain.lower() not in ['none', 'unknown']:
                        self.issues.append('Underlying conditions selection error.')
                    if underlying_condition.lower() not in ['none', 'unknown']:
                        self.issues.append('Underlying condition is no but underlying condition GAS/STSS is selected .')
                        
    #######################Healthcare Associations (in the 30 days prior to first positive)#########
    def CheckHealthcareAssociations(self):
        type_of_procedure = self.ReadText('//*[@id="ME120001"]')
        Name_of_facility = self.ReadText('//*[@id="ME128014"]')
        Discharged_prior = self.ReadText('//*[@id="ME128019"]')
        Location_post_surgical = self.ReadText('//*[@id="ME128020"]')
        self.invasive_procedure = self.ReadText('//*[@id="ME128025"]')
        self.Type_invasive_procedure = self.ReadText('//*[@id="ME128027"]')
        facilityname_procedure = self.ReadText('//*[@id="ME128027"]')
        Discharge_infection_procedure = self.ReadText('//*[@id="ME128029"]')
        Type_of_healthcare = self.ReadText('//*[@id="ME128030"]')
        other_healthcare_setting = self.ReadText('//*[@id="ME128031"]')
        healthcare_discharge_date = self.ReadDate('//*[@id="ME124047"]')  
        Have_surgery = self.ReadText('//*[@id="ME128012"]')
        Delivered_baby = self.ReadText('//*[@id="ME128015"]/tbody/tr[8]/td[2]')
        Delivery_type = self.ReadText('//*[@id="ME128022"]')
        Discharge_prior_Infection = self.ReadText('//*[@id="ME128015"]/tbody/tr[11]/td[2]')
        if self.current_case_status != 'Not a Case' :
            if not Have_surgery:
                self.issues.append('Healthcare association is blank.')
            elif Have_surgery == 'Yes':
                if self.surgery_date and self.surgery_date > self.date_specimen:
                    self.issues.append('Surgery date cannot be after specimen collection date.')  
                if self.surgery_date and self.surgery_date > self.now:
                    self.issues.append('Surgery date cannot be in the future.')
                if not type_of_procedure or not Name_of_facility or not self.surgery_date or not Discharged_prior or not Location_post_surgical:
                    self.issues.append('Surgery is yes, below fields are missing.')
            if self.patient_current_sex and self.patient_current_sex == 'Female':
                if not Delivered_baby:
                    self.issues.append('Delivered baby is blank is blank.')
                elif Delivered_baby == 'Yes':
                    if self.Delivery_date and self.Delivery_date > self.now:
                        self.issues.append('Delivery date cannot be in the future.')
                    if not self.Delivery_date or not Delivery_type or not Discharge_prior_Infection:
                        self.issues.append('Delivered baby is yes,below fields are missing.')
            if not self.invasive_procedure:
                self.issues.append('invasive procedure cannot be empty.')
            elif self.invasive_procedure == 'Yes':
                if not self.Date_invasive_procedure or not self.Type_invasive_procedure or not facilityname_procedure or not Discharge_infection_procedure:
                    self.issues.append('invasive procedure is yes, below fields are missing.')  
            if Type_of_healthcare and Type_of_healthcare.lower() in ["inpatient", "outpatient","same day surgery"]:
                if  not self.healthcare_admissiondate or not healthcare_discharge_date:
                    self.issues.append(f'type of Healthcare is {Type_of_healthcare}, admission date and discharge date are missing .')
            elif Type_of_healthcare and Type_of_healthcare.lower() in ["other"]:
                if  not other_healthcare_setting or not self.healthcare_admissiondate or not healthcare_discharge_date:
                    self.issues.append('type of Healthcare is other,but other type of healthcare, admission date and discharge date are missing .')
            
###########Epidemiologic####            
##########Exposure##############
    def CheckHighRiskExposure(self):
        """ Check if high risk exposure is indicated. """ 
        High_risk_exposure = self.ReadText('//*[@id="ME134007"]')
        facility_name = self.ReadText('//*[@id="ME134008"]')
        any_igas_cases = self.ReadText('//*[@id="ME134009"]')
        if self.current_case_status != 'Not a Case':
            if High_risk_exposure == 'Yes':
                if not facility_name:
                    self.issues.append('If high risk exposure is indicated then facility name must be provided.')
                if not any_igas_cases:
                    self.issues.append('If high risk exposure is indicated then any igas cases must be provided.')
        
    def CheckHypoTension(self):
        hypotension = self.ReadText('//*[@id="ME128033"]')
        if self.current_case_status != 'Not a Case':
            if not hypotension:
                self.issues.append('Hypotension is blank.')
        
        
    def CheckCongregateFacilityName(self):         #Exposure  facility name
        """ Need a congregate faciltiy name if patient lives in congregate setting."""
        if self.investigator_name:
            cong_fac_name = self.CheckForValue('//*[@id="ME134008"]','Name of congregate facility is missing.')
        
###########Epi-link########
    def CheckOutbreakExposure(self):
        """ If outbreak exposure is indicated then outbreak name must be provided.
        If the case is assigned to outbreak investigator outbreak exposure section must be complete."""
        outbreak_exposure_path = '//*[@id="INV150"]'
        outbreak_name_path = '//*[@id="ME125032"]'
        check_condition = 'Yes'
        message = "Outbreak name must be provided if outbreak exposure is indicated."

        if self.investigator_name in self.outbreak_investigators:
            ob_exposure = self.ReadText(outbreak_exposure_path)
            if ob_exposure != 'Yes':
                self.issues.append('Outbreak exposure must be "Yes" and outbreak name must be specified.')
            else:
                self.CheckForValue(outbreak_name_path, 'Outbreak name in exposure section is blank.')
        else:
            self.CheckIfField(outbreak_exposure_path, outbreak_name_path, check_condition, message)
            
#########Disease Acquisition##########
    def CheckDiseaseAcquisition(self):
        """ Check if disease acquisition is indicated. """
        disease_acquisition = self.ReadText('//*[@id="INV152"]')
        #country_of_usual_residence = self.ReadText('//*[@id="INV501"]')
        if self.current_case_status != 'Not a Case':
            if not disease_acquisition:
                self.issues.append('Disease acquisition is blank.')
            #if not country_of_usual_residence:
                #self.issues.append('Country of usual residence is blank.')
        
    def CheckCaseStatusNew(self):
        """ Transmission mode should blank or airborne"""
        transmission_mode =  self.ReadText('//*[@id="INV157"]')
        detection_method = self.ReadText('//*[@id="INV159"]')
        confirmation_method = self.ReadText('//*[@id="INV161"]')
        confirmation_date = self.ReadDate('//*[@id="INV162"]')
        if self.current_case_status != 'Not a Case':
            if not transmission_mode:
                self.issues.append('Transmission mode is blank.')
            if not detection_method:
                self.issues.append('Detection method is blank.')
            if not confirmation_method:
                self.issues.append('Confirmation method is blank.')
            if self.current_case_status.lower() == 'probable' and confirmation_method.lower() != 'laboratory report':
                self.issues.append('Case status is probable but confirmation method is not laboratory report.')   
            if not confirmation_date:
                self.issues.append('Confirmation date is blank.')
            elif self.received_date and confirmation_date < self.received_date:
                self.issues.append('Confirmation date cannot be prior to report date.')
            elif confirmation_date > self.now:
                self.issues.append('Confirmation date cannot be in the future.')
        
        """ Case status must be consistent with associated labs. """
        self.current_case_status = self.ReadText('//*[@id="INV163"]')
        #sterile_site = self.ReadText('//*[@id="ME127000"]')
        status_pairs = {'Confirmed':'C', 'Probable':'P', 'Suspect':'S', 'Not a Case':'N'}
        diagnosis_reported_to_cdc = self.ReadText('//*[@id="NBS136"]')
        pid = self.ReadText('//*[@id="INV179"]')
        disseminated = self.ReadText('//*[@id="NBS137"]')
        conjunctivitis = self.ReadText('//*[@id="INV361"]')
        if not diagnosis_reported_to_cdc:
            self.issues.append('Diagnosis reported to CDC is blank.')       
        if not pid:
            self.issues.append('Pid is blank.')
        if not disseminated:
            self.issues.append('Disseminated is blank.')
        if not conjunctivitis:
            self.issues.append('Conjunctivitis is blank.')
        id = self.ReadPatientID()
        if not self.current_case_status or self.current_case_status in ['Unknown', 'Suspect', 'Probable']:
            self.issues.append(' Review Case status.')
        if self.current_case_status == "Not a Case":
            if self.state != 'Maine':
                if id not in self.not_a_case_log:
                    self.not_a_case_log.append(id)
                self.issues.append('State is not Maine and current_case_status is not "Not a Case".')
     
    def CheckMmwrWeek(self):
        """ MMWR week must be provided."""
        mmwr_week = self.ReadText( '//*[@id="INV165"]')
        if not mmwr_week:
            self.issues.append('MMWR Week is blank.')

    def CheckMmwrYear(self):
        """ MMWR year must be provided."""
        mmwr_year = self.ReadText( '//*[@id="INV166"]')
        #self.date_specimen = self.ReadDate('//*[@id="ME10098104"]/tbody/tr[5]/td[2]')
        if not mmwr_year:
            self.issues.append('MMWR Year is blank.')
        elif self.collection_date and int(mmwr_year) != self.collection_date.year:
            self.issues.append('MMWR Year does not match collection date.')
    
    def GoToCaseManagementTab(self):
        """ Within a patient profile navigate to the Case Management tab."""
        case_management_path = '//*[@id="tabs0head2"]'
        WebDriverWait(self,self.wait_before_timeout).until(EC.presence_of_element_located((By.XPATH, case_management_path)))
        self.find_element(By.XPATH,'//*[@id="tabs0head2"]').click() 
    
    def CheckIntialFollowUp(self):
        """ Check if initial follow up is indicated. """
        investigator = self.ReadText('//*[@id="NBS139"]')
        initial_follow_up = self.ReadText('//*[@id="NBS140"]')
        if not investigator:
            self.issues.append('Initial follow up is blank.')   
        if not initial_follow_up:
            self.issues.append('Investigator is blank.') 
            
    def NotificationOfExposureInformation(self):
        """ Check if notification of exposure information is indicated. """
        patient_notification_of_exposure = self.ReadText('//*[@id="NBS143"]')
        if not patient_notification_of_exposure:
            self.issues.append('Notification of exposure information is blank.') 
    
    def FieldFollowUpInformation(self):
        """ Check if field follow up information is indicated. """
        field_follow_up_investigator = self.ReadText('//*[@id="NBS161"]')
        field_follow_up_dateassigned = self.ReadDate('//*[@id="NBS162"]')
        disposition_date = self.ReadDate('//*[@id="NBS174"]')
        disposition_by = self.ReadText('//*[@id="NBS175"]')
        supervisor = self.ReadText('//*[@id="NBS176"]')
        if not field_follow_up_investigator:
            self.issues.append('case assignment investigator cannot be blank.')  
        if not field_follow_up_dateassigned:
            self.issues.append('Field follow up date assigned is blank.')  
        if not self.disposition:
            self.issues.append('Disposition is blank.')
        elif self.disposition.lower() == 'l - other':  
            self.issues.append('Disposition cannot be "L - Other".')  
        elif  self.disposition == 'X - Patient Deceased':
            if self.is_patient_deceased.lower() != 'yes':
                self.issues.append('Disposition is "X - Patient Deceased" but patient deceased is not yes.')
        elif [self.disposition].str.contains("E - Previously Treated for This Infection|C - Infected, Brought to Treatment"):
            if "Ceftriaxone, 500 mg, IM, x 1 dose" not in str(self.associated_treatments['Treatment']):
                self.issues.append("disposition doesnot match associated treatment for E or C")
        elif  self.disposition == 'D - Infected, Not Treated':
            if "Cefixime, 400 mg, PO, x 1 dose" not in str(self.associated_treatments['Treatment']) and  "Cefixime, 400 mg, PO, x 1 dose" not in str(self.associated_treatments['Treatment']):
                self.issues.append("disposition doesnot match associated treatment for D")
        elif [self.disposition].str.contains("A - Preventative Treatment|B - Refused Preventative Treatment|F - Not Infected|K - Sent Out Of Jurisdiction|Z - Previous Preventative Treatment") and self.current_case_status == "Not a Case":
            if "gentamicin 240 mg " not in str(self.associated_treatments['Treatment']) and  " Azithromycin, 2 gm, PO, X 1 dose" not in str(self.associated_treatments['Treatment']):
                self.issues.append(f'disposition is {self.disposition}, associated_treatments is {self.associated_treatments['Treatment']} ,case status is {self.current_case_status} disposition doesnot match associated treatment and casestatus')
        if not disposition_date :
            self.issues.append("disposition date cannot be blank")
        if not disposition_by :
            self.issues.append("disposition by cannot be blank")    
        if not supervisor:
            self.issues.append("supervisor cannot be blank")
    
    def InterviewCaseAssignment(self):
        """ Check if interview case assignment information is indicated. """
        interview_case_assignment_investigator = self.ReadText('//*[@id="NBS186"]')
        interview_case_assignment_dateassigned = self.ReadDate('//*[@id="NBS187"]')
        self.patient_interview_status = self.ReadText('//*[@id="NBS192"]')
        if not interview_case_assignment_investigator:
            self.issues.append('Interview case assignment investigator cannot be blank.')
        if not interview_case_assignment_dateassigned:
            self.issues.append('Interview case assignment date assigned is blank.')
        if not self.patient_interview_status:
            self.issues.append('Patient interview status is blank.')
            
    def CaseClosure(self):
        """ Check if case closure information is indicated. """
        date_closure = self.ReadText('//*[@id="NBS196"]')
        closed_by = self.ReadDate('//*[@id="NBS197"]')
        if not date_closure:
            self.issues.append('Date closure cannot be blank.')
        if not closed_by:
            self.issues.append('Closed by cannot be blank.')

    def GoToCoreInfoTab(self):
        """ Within a patient profile navigate to the Core Information tab."""
        core_info_path = '//*[@id="tabs0head1"]'
        WebDriverWait(self,self.wait_before_timeout).until(EC.presence_of_element_located((By.XPATH, core_info_path)))
        self.find_element(By.XPATH,'//*[@id="tabs0head3"]').click()

    def PatientHivStatus(self):
        self.hiv_status = self.ReadText('//*[@id="NBS153"]')
        if not self.hiv_status:
            self.issues.append('900 status cannot be blank.')
            
    def RiskFactors(self):
        """ Check if risk factors are indicated. """
        self.was_behavioral_risk_assessed = self.ReadText('//*[@id="NBS229"]')
        self.sex_patners = self.ReadText('//*[@id="NBS_INV_STD_UI_42"]/tbody')
        self.sex_behavior = self.ReadText('//*[@id="NBS_INV_STD_UI_43"]/tbody')
        self.risk_behavior = self.ReadText('//*[@id="NBS_INV_STD_UI_44"]/tbody')
        self.drug_use = self.ReadText('//*[@id="NBS_INV_STD_UI_45"]/tbody')  #drug use past 12 months
        if not self.was_behavioral_risk_assessed:
            self.issues.append('behavioral risk assessment cannot be blank.')
        if self.was_behavioral_risk_assessed == '1 - Completed Risk Profile':
            row_data_new = []
            for risk in self.sex_patners:
                cells = risk.find_elements(By.TAG_NAME, 'td')
                row_data_new.extend([cell.text for cell in cells if cell.text])
                if not row_data_new:
                    self.issues.append('Sex partners information is blank.')
            row_data_new1 = []
            for risk in self.sex_behavior:
                cells = risk.find_elements(By.TAG_NAME, 'td')
                row_data_new1.extend([cell.text for cell in cells if cell.text]) 
                if not row_data_new1:
                    self.issues.append('Sexual behavior information is blank.')
            row_data_new2 = []
            for risk in self.risk_behavior:
                cells = risk.find_elements(By.TAG_NAME, 'td')
                row_data_new2.extend([cell.text for cell in cells if cell.text])
                if not row_data_new2:
                    self.issues.append('Risk behavior information is blank.')
            row_data_new3 = []
            for risk in self.drug_use:
                cells = risk.find_elements(By.TAG_NAME, 'td')
                row_data_new3.extend([cell.text for cell in cells if cell.text]) 
                if not row_data_new3:
                    self.issues.append('Drug use information is blank.')

    def PartnersInfo(self):
        partners_last_year = self.ReadText('//*[@id="NBS_INV_STD_UI_53"]/tbody')
        partners_interviewed_period = self.ReadText('//*[@id="NBS_INV_STD_UI_54"]/tbody')
        partners_internet_info = self.ReadText('//*[@id="STD119"]')
        row_data = []
        for risk in partners_last_year:
            cells = risk.find_elements(By.TAG_NAME, 'td')
            row_data.extend([cell.text for cell in cells if cell.text])
            if not row_data:
                self.issues.append('Partners last year information is blank.')
        row_data1 = []
        for risk in partners_interviewed_period:
            cells = risk.find_elements(By.TAG_NAME, 'td')
            row_data1.extend([cell.text for cell in cells if cell.text])
            if not row_data1:
                self.issues.append('Partners interviewed period information is blank.')
        if not partners_internet_info:
            self.issues.append('Partners internet information is blank.')
    
    def StdHistory(self):
        previous_std_history = self.ReadText('//*[@id="STD117"]')
        self.pervious_confirmed_probable = self.ReadText('//*[@id="ME10099100"]')
        self.earliest_specimen_date = self.ReadDate('//*[@id="ME10099101"]')
        evidence_reinfection = self.ReadText('//*[@id="ME10099102"]')
        if not previous_std_history:
            self.issues.append("Self reported STD history is missing")
        if not self.pervious_confirmed_probable :
            self.issues.append("Previous gonorrhea investigation cannot be blank")
        elif self.pervious_confirmed_probable.lower() == 'yes' :
            if not self.earliest_specimen_date :
                self.issues.append("Missing specimen collection date for previous gonorrhea investigation")
            if not evidence_reinfection :
                self.issues.append("Evidence of reinfection cannot be blank")

    def PartnerServiceInformation(self):
        self.enrolled_partner_service = self.ReadText('//*[@id="NBS257"]')
        previous_900_test = self.ReadText('//*[@id="NBS254"]')
        client_on_prep = self.ReadText('//*[@id="NBS443"]')
        avt_last_year = self.ReadText('//*[@id="NBS255"]')
        if not self.enrolled_partner_service:
            self.issues.append('enrolled in Partner services is blank.')
        if self.enrolled_partner_service == 'No Partner Service Needed':
            if self.current_case_status != 'Not a Case':
                self.issues.append('no partner services needed cannot be used.')
            if self.was_behavioral_risk_assessed == '5 - Asked, No Risks Identified':
                self.issues.append('no partner services needed cannot be used.')
        if not previous_900_test:
            self.issues.append('Previous 900 test is blank.')
        if self.hiv_status in ['1 - Negative', '2 - Newly Diagnosed','6 - Other', '9 - Unknown']:
            if not client_on_prep:
                self.issues.append(f'hiv status is {self.hiv_status} but Client on PrEP is blank.')
        if not client_on_prep:
            if not avt_last_year:
                self.issues.append('Is the Client Currently On PrEP is blank ,Anti-viral Therapy - Last 12 Months.')
        if not avt_last_year:
            if self.hiv_status == '1 - Negative':
                self.issues.append('Anti-viral Therapy - Last 12 Months is blank but HIV status is negative.')
                
    def GoToContactRecordsTab(self):
        interview = self.ReadTableToDF('//*[@id="interviewListID"]')
        contact_records = self.ReadTableToDF('//*[@id="contactNamedByPatListID"]')
        if self.patient_interview_status == 'I - Interviewed':
            if not interview:
                self.issues.append("add interview")
        if not contact_records:
            if self.enrolled_partner_service.lower() == 'accepted':
                self.issues.append("add contact records")
        # add code for contact records

    def CheckCaseClassification(self):
        self.laboratory_testing = self.ReadText('//*[@id="ME10098104"]/tbody/tr[1]/td/table/tbody/tr/td[2]')
        if self.pervious_confirmed_probable.lower() == 'yes':
            if self.earliest_specimen_date and self.collection_date and (self.collection_date - self.earliest_specimen_date).days > 30:
                if self.name_match and self.labs["Text Result"].lower().str.contains("positive"):
                   for i in range(len(self.laboratory_testing)): 
                       row_df = self.laboratory_testing.iloc[[i]]
                       if row_df["What test type(s) were used for testing?"].str.contains("NAAT | Culture").any():
                           if row_df["Test Result"].lower().str.contains("positive").any():
                               if self.current_case_status == 'Confirmed':
                                   if row_df["What specimen source was tested?"].str.contains("Blood|CSF|Skin|Synovial Fluid").any():
                                       if verified dgi 
                                        pass
                                    else:
                                        self.issues.append("Other specimen type, requires manual review.")
                        else:
                            row_df["What test type(s) were used for testing?"].str.contains("Microscopy | Culture").any()
######################### Symptom Check Methods ################################
    def CheckDateSpecimen(self):
        """ Check if date specimen is present and matches earliest date from
        associated labs. """
        #date of surgery
        self.surgery_date = self.ReadDate('//*[@id="ME128013"]')
        self.Delivery_date = self.ReadDate('//*[@id="ME116004"]')
        self.Date_invasive_procedure = self.ReadDate('//*[@id="ME128026"]')
        self.healthcare_admissiondate = self.ReadDate('//*[@id="ME124046"]')
        self.onset_illness_date = self.ReadDate('//*[@id="INV137"]') # 	03/26/2025
        self.date_specimen = self.ReadDate('//*[@id="ME8117"]')
        if not self.date_specimen:
            self.issues.append('Date specimen is missing.')
        elif self.date_specimen > self.now:
            self.issues.append('Date specimen cannot be in the future.')
        elif self.onset_illness_date and self.date_specimen < self.onset_illness_date:
            self.issues.append('Date specimen cannot be before collection date.')
        elif self.date_specimen == self.onset_illness_date and self.date_specimen > self.onset_illness_date:
            print("")
        elif self.collection_date and self.date_specimen != self.collection_date:
            self.issues.append('Date specimen does not match collection date.')
        if self.Delivery_date and self.Delivery_date > self.date_specimen:
            self.issues.append('Delivery date cannot be after specimen collection date.')
        if self.Date_invasive_procedure and self.Date_invasive_procedure > self.date_specimen:
            self.issues.append('Invasive procedure date cannot be after specimen collection date.')
        if self.healthcare_admissiondate and self.healthcare_admissiondate > self.date_specimen:
            self.issues.append('Healthcare admission date cannot be after specimen collection date.')
            
                      
    def CheckLaboratoryDetails(self):
        """" Check symptom status of case. """
        laboratory_name = self.ReadText('//*[@id="ME6105"]')
        date_specimen = self.ReadText('//*[@id="ME8117"]')
        sterile_site = self.ReadText('//*[@id="ME127000"]')
        if sterile_site.lower() == "other":
            other_sterile_site = self.ReadText('//*[@id="ME127001"]')
            non_sterile_site = self.ReadText('//*[@id="ME127002"]')
            
        if (self.ltf != 'Yes') & (self.investigator):
            if not self.symptoms:
                self.issues.append("Symptom status is blank.")

 #new code added from covidnotificationbot, it also inherits from here
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
    

    def SendStrepEmail(self, body, inv_id):
        message = EmailMessage()
        message.set_content(body)
        message['Subject'] = f'Strep Bot {inv_id}'
        message['From'] = self.nbsbot_email
        message['To'] = ', '.join(["vaishnavi.appidi@maine.gov"])   #change email to disease.reporting
        smtpObj = smtplib.SMTP(self.smtp_server)
        smtpObj.send_message(message)
        print('sent email', inv_id)