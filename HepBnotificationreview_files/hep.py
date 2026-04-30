'''def CheckDiagnosticTestResults(self):  
        import re
        self.hbsag_specimen_date = self.ReadDate('//*[@id="LP38331_2_DT"]')
        self.hbsag_result = self.ReadText('//*[@id="LP38331_2"]')
        self.total_hbc_result = self.ReadText('//*[@id="LP38323_9"]')
        self.total_hbc_specimen_date = self.ReadDate('//*[@id="LP38323_9_DT"]')
        self.igm_hbc_result = self.ReadText('//*[@id="LP38325_4"]')
        self.igm_hbc_specimen_date = self.ReadDate('//*[@id="LP38325_4_DT"]')
        self.hbdna_result = self.ReadText('//*[@id="LP38320_5"]')
        self.hbdna_specimen_date = self.ReadDate('//*[@id="LP38320_5_DT"]')
        self.hbeag_result = self.ReadText('//*[@id="LP38329_6"]')
        self.hbeag_specimen_date = self.ReadDate('//*[@id="LP38329_6_DT"]')
        self.hbsab_result = self.ReadText('//*[@id="ME116006"]')
        self.hbsab_specimen_date = self.ReadDate('//*[@id="ME117002"]')
        self.hbeab_result = self.ReadText('//*[@id="ME121005"]')
        self.hbeab_specimen_date = self.ReadDate('//*[@id="ME121002"]')
        self.positive_results = ['detected', 'reactive', 'positive', 'pos']
        self.negative_results = ['not detected', 'negative', 'non-reactive','neg','non react']
        

        dna_dates_new = {
            'hepatitis b virus, dna': [self.hbdna_result, self.hbdna_specimen_date],
            'hepatitis b virus surface antigen': [self.hbsag_result, self.hbsag_specimen_date],
            'igm anti-hbc': [self.igm_hbc_result, self.igm_hbc_specimen_date],
            'hepatitis b virus core ab': [self.total_hbc_result, self.total_hbc_specimen_date],
            'hepatitis b virus e antigen': [self.hbeag_result, self.hbeag_specimen_date],
            'hepatitis b virus surface antibody': [self.hbsab_result, self.hbsab_specimen_date],
            'anti-hbe': [self.hbeab_result, self.hbeab_specimen_date]
        }
        self.data = []
        self.data = [key.strip().lower() for key in self.dna_dates.keys() if key.strip().lower()]
        for item in self.data:
            if item.lower() in self.text:
                if item.lower() in dna_dates_new or [x for x in self.text if x == item.lower()]:
                    del dna_dates_new[item.lower()]
                if not self.hbdna_result:
                    self.issues.append('Hepatitis B DNA result is missing.')
                if not self.hbdna_specimen_date:
                    self.issues.append('Hepatitis B DNA collection date is missing.')
                if self.dna_date and self.hbdna_specimen_date and self.hbdna_specimen_date != self.dna_date:
                    self.issues.append('Hepatitis B DNA specimen date does not match the collection date from associated lab reports.')
                
            elif item.lower() in self.text1:
                if item.lower() in dna_dates_new or [x for x in self.text1 if x == item.lower()]:
                    del dna_dates_new[item.lower()]
                if not self.hbsag_result:
                    self.issues.append('Hepatitis B surface antigen result is missing.')
                if not self.hbsag_specimen_date:
                    self.issues.append('Hepatitis B surface antigen collection date is missing.')
                if self.hbsag_result and not self.hbsag_specimen_date:
                    self.issues.append('Hepatitis B surface antigen result is provided but specimen date is not.')
                if self.hbsag_date and self.hbsag_specimen_date and self.hbsag_specimen_date != self.hbsag_date:
                    self.issues.append('Hepatitis B surface antigen specimen date does not match the collection date from associated lab reports.')
                result_ag = (any(x in self.result_check_antigen.lower() for x in self.positive_results) and any(x in self.hbsag_result.lower() for x in self.positive_results)) or (any(x in self.result_check_antigen.lower() for x in self.negative_results) and any(x in self.hbsag_result.lower() for x in self.negative_results))
                if self.hbsag_result and not result_ag:
                    self.issues.append(f'Hepatitis B surface antigen result and associated lab result- result mismatch.')
            elif item.lower() in self.text3:
                if item.lower() in dna_dates_new or [x for x in self.text3 if x == item.lower()]:
                    del dna_dates_new[item.lower()]
                if not self.igm_hbc_result:
                    self.issues.append('IgM Hepatitis B core antibody result is missing.')
                if not self.igm_hbc_specimen_date:
                    self.issues.append('IgM Hepatitis B core antibody collection date is missing.')
                if self.igm_hbc_result and not self.igm_hbc_specimen_date:
                    self.issues.append('IgM Hepatitis B core antibody result is provided but specimen date is not.')
                if self.igm_anti_hbc_date and self.igm_hbc_specimen_date and self.igm_hbc_specimen_date != self.igm_anti_hbc_date:
                    self.issues.append('IgM Hepatitis B core antibody specimen date does not match the collection date from associated lab reports.')
                result_igm = (any(x in self.result_check_igm.lower() for x in self.positive_results) and any(x in self.igm_hbc_result.lower() for x in self.positive_results)) or (any(x in self.result_check_igm.lower() for x in self.negative_results) and any(x in self.igm_hbc_result.lower() for x in self.negative_results))
                if self.igm_hbc_result and not result_igm:
                    self.issues.append(f'IgM Hepatitis B core antibody result and associated lab result- result mismatch.')
            elif item.lower() in self.text2:
                if item.lower() in dna_dates_new or [x for x in self.text2 if x == item.lower()]:
                    del dna_dates_new[item.lower()]
                    if not self.total_hbc_result:
                        self.issues.append('Total Hepatitis B core antibody result is missing.')
                    if  not self.total_hbc_specimen_date:
                        self.issues.append('Total Hepatitis B core antibody collection date is missing.')
                    if self.total_hbc_result and not self.total_hbc_specimen_date:
                        self.issues.append('Total Hepatitis B core antibody result is provided but specimen date is not.')
                    if self.total_anti_hbc_date and self.total_hbc_specimen_date and self.total_hbc_specimen_date != self.total_anti_hbc_date:
                        self.issues.append('Total Hepatitis B core antibody specimen date does not match the collection date from associated lab reports.')
                    result_core = (any(x in self.result_check_core.lower() for x in self.positive_results) and any(x in self.total_hbc_result.lower() for x in self.positive_results)) or (any(x in self.result_check_core.lower() for x in self.negative_results) and any(x in self.total_hbc_result.lower() for x in self.negative_results))
                    if self.total_hbc_result and not result_core:
                        self.issues.append(f'Total Hepatitis B core antibody result and associated lab result- result mismatch.')

            elif item.lower() in self.text4:
                if item.lower() in dna_dates_new or [x for x in self.text4 if x == item.lower()]:
                    del dna_dates_new[item.lower()]
                if not self.hbeag_result:
                    self.issues.append('Hepatitis B e antigen result is missing.')
                if not self.hbeag_specimen_date:
                    self.issues.append('Hepatitis B e antigen collection date is missing.')
                if self.hbeag_result and not self.hbeag_specimen_date:
                    self.issues.append('Hepatitis B e antigen result is provided but specimen date is not.')
                if self.hbeag_date and self.hbeag_specimen_date and self.hbeag_specimen_date != self.hbeag_date:
                    self.issues.append('Hepatitis B e antigen specimen date does not match the collection date from associated lab reports.')
                result_hbeag = (any(x in self.result_check_hbeag.lower() for x in self.positive_results) and any(x in self.hbeag_result.lower() for x in self.positive_results)) or (any(x in self.result_check_hbeag.lower() for x in self.negative_results) and any(x in self.hbeag_result.lower() for x in self.negative_results))
                if self.hbeag_result and not result_hbeag:
                    self.issues.append(f'Hepatitis B e antigen result and associated lab result- result mismatch.')

            elif item.lower() in self.text5:
                if item.lower() in dna_dates_new or [x for x in self.text5 if x == item.lower()]:
                    del dna_dates_new[item.lower()]
                if not self.hbsab_result:
                    self.issues.append('Hepatitis B surface antibody result is missing.')
                if not self.hbsab_specimen_date:
                    self.issues.append('Hepatitis B surface antibody collection date is missing.')
                if self.hbsab_result and not self.hbsab_specimen_date:
                    self.issues.append('Hepatitis B surface antibody result is provided but specimen date is not.')
                if self.anti_hbs_date and self.hbsab_specimen_date and self.hbsab_specimen_date != self.anti_hbs_date:
                    self.issues.append('Hepatitis B surface antibody specimen date does not match the collection date from associated lab reports.')
                result_hbsab = (any(x in self.result_check_anti_hbs.lower() for x in self.positive_results) and any(x in self.hbsab_result.lower() for x in self.positive_results)) or (any(x in self.result_check_anti_hbs.lower() for x in self.negative_results) and any(x in self.hbsab_result.lower() for x in self.negative_results))
                if self.hbsab_result and not result_hbsab:
                    self.issues.append(f'Hepatitis B surface antibody result and associated lab result- result mismatch.')

            elif item.lower() in self.text6:
                if item.lower() in dna_dates_new or [x for x in self.text6 if x == item.lower()]:
                    del dna_dates_new[item.lower()]
                if not self.hbeab_result:
                    self.issues.append('Hepatitis B e antibody result is missing.')
                if not self.hbeab_specimen_date:
                    self.issues.append('Hepatitis B e antibody collection date is missing.')
                if self.hbeab_result and not self.hbeab_specimen_date:
                    self.issues.append('Hepatitis B e antibody result is provided but specimen date is not.')
                if self.hbeab_date and self.hbeab_specimen_date and self.hbeab_specimen_date != self.hbeab_date:
                    self.issues.append('Hepatitis B e antibody specimen date does not match the collection date from associated lab reports.')
                result_hbeab = (any(x in self.result_check_anti_hbe.lower() for x in self.positive_results) and any(x in self.hbeab_result.lower() for x in self.positive_results)) or (any(x in self.result_check_anti_hbe.lower() for x in self.negative_results) and any(x in self.hbeab_result.lower() for x in self.negative_results))
                if self.hbeab_result and not result_hbeab:
                    self.issues.append(f'Hepatitis B e antibody result and associated lab result- result mismatch.')
        for key, value in dna_dates_new.items():
            if value[0]:
                self.issues.append(f'{key} associated labs are not matching with diagnostic results.')
            if value[1]:
                self.issues.append(f'{key} associated labs are not matching with diagnostic specimen date.')'''
    
    
    '''def ReadAssociatedLabs(self):
        """ Read table of associated labs. """
        from collections import defaultdict
        from datetime import datetime
        import pandas as pd
        from selenium.webdriver.common.by import By
        # Helper: positivity detection
        def is_negative(text):
            t = text.lower()
            return any(word in t for word in [
                'negative', 'not detected', 'non-reactive','neg','nonreactive','no significant change'
            ])
        def is_positive(text):
            t = text.lower()
            return any(word in t for word in [
                'positive', 'detected', 'reactive','pos','react'
            ])

        self.labs = self.ReadTableToDF('//*[@id="viewSupplementalInformation1"]/tbody')
        self.name_match = False
        lab_reports = self.find_elements(By.XPATH, '//*[@id="eventLabReport"]/tbody/tr')

        # Structure:
        # { test_key: { date_collected: (date_received, result_text) } }
        self.dna_dates = defaultdict(dict)

        test_map = {
            "hepatitis b virus, dna": [
                'hepatitis b virus dna',
                'hepatitis b virus, dna',
                'hepatitis b virus (hbv)'
            ],
            "hepatitis b virus surface antigen": [
                'hepatitis b virus surface antigen (hbsag)',
                'hepatitis b virus surface antigen',
                'hepatitis b virus surface ag',
                'hbsag',
                'hep b surface ag',
                'hbsag confirmation'
            ],
            "igm anti-hbc": [
                'igm anti-hbc',
                'hep b core ab, igm',
                'hepatitis b virus core antibody, igm',
                'hepatitis b virus core ab.igm'
            ],
            "hepatitis b virus core ab": [
                'hepatitis b virus core ab',
                'hepatitis b virus core antibody',
                'total anti-hbc',
                'Hepatitis B virus Core antibodies, Total'
            ],
            "hepatitis b virus e antigen": [
                'hbeag',
                'hepatitis b virus e antigen',
                'hepatitis b virus little e antigen',
                'hepatitis b virus little e ag'
            ],
            "hepatitis b virus surface antibody": [
                'hepatitis b virus surface antibody',
                'hepatitis b virus surface ab',
                'hbv surface ab',
                'hbsab'
            ],
            "anti-hbe": [
                'anti-hbe',
                'hepatitis b virus e antibody'
            ]
        }

        # MAIN PARSING LOOP
        for row in lab_reports:
            cells = row.find_elements(By.TAG_NAME, 'td')

            try:
                date_received = datetime.strptime(
                    cells[0].text.strip().split()[0], "%m/%d/%Y"
                ).date()

                date_collected = datetime.strptime(
                    cells[2].text.strip(), "%m/%d/%Y"
                ).date()
            except Exception:
                continue

            result_cell = cells[3]
            divs = result_cell.find_elements(By.TAG_NAME, 'div')
            results = [d.text.strip() for d in divs] if divs else [result_cell.text.strip()]

            for result in results:
                result_lower = result.lower()

                for key, keywords in test_map.items():
                    if any(keyword in result_lower for keyword in keywords):

                        existing = self.dna_dates[key].get(date_collected)

                        #  POSITIVE PRIORITY LOGIC
                        if not existing:
                            self.dna_dates[key][date_collected] = (date_received, result)

                        else:
                            existing_received, existing_result = existing

                            new_pos = is_positive(result)
                            old_pos = is_positive(existing_result)

                            # Positive always wins
                            if new_pos and not old_pos:
                                self.dna_dates[key][date_collected] = (date_received, result)

                            # If same polarity → keep latest received
                            elif new_pos == old_pos and date_received > existing_received:
                                self.dna_dates[key][date_collected] = (date_received, result)
                        break
        # INITIALIZE OUTPUT FIELDS
        self.dna_date = None
        self.hbsag_date = None
        self.total_anti_hbc_date = None
        self.igm_anti_hbc_date = None
        self.hbeag_date = None
        self.anti_hbs_date = None
        self.hbeab_date = None

        self.result_check_dna = None
        self.result_check_antigen = None
        self.result_check_core = None
        self.result_check_igm = None
        self.result_check_hbeag = None
        self.result_check_anti_hbs = None
        self.result_check_anti_hbe = None

        # FINAL EXTRACTION
        for key, collected_dict in self.dna_dates.items():
            if not collected_dict:
                continue

            earliest_collected = min(collected_dict.keys())
            date_received, result_text = collected_dict[earliest_collected]
            clean_result = result_text.split("Reference Range")[0].strip()

            if key == "hepatitis b virus, dna":
                self.dna_date = earliest_collected
                self.result_check_dna = clean_result

            elif key == "hepatitis b virus e antigen":
                self.hbeag_date = earliest_collected
                self.result_check_hbeag = clean_result

            elif key == "hepatitis b virus surface antigen":
                self.hbsag_date = earliest_collected
                self.result_check_antigen = clean_result

            elif key == "igm anti-hbc":
                self.igm_anti_hbc_date = earliest_collected
                self.result_check_igm = clean_result

            elif key == "hepatitis b virus core ab":
                self.total_anti_hbc_date = earliest_collected
                self.result_check_core = clean_result

            elif key == "hepatitis b virus surface antibody":
                self.anti_hbs_date = earliest_collected
                self.result_check_anti_hbs = clean_result

            elif key == "anti-hbe":
                self.hbeab_date = earliest_collected
                self.result_check_anti_hbe = clean_result

        # =============================
        # CHECK LAB TABLE
        # =============================
        for index in range(len(self.labs)):
            row_df = self.labs.iloc[[index]]
            if row_df['Test Results'].str.contains('hepatitis b', na=False, case=False).any():
                self.labs = self.labs.loc[index]
                self.name_match = True
                break

        if not self.name_match:
            self.labs = pd.DataFrame()
            self.issues.append('Test results does not have hepatitis b.')'''

    '''def ReadAssociatedLabs(self):
        """ Read table of associated labs."""
        self.labs = self.ReadTableToDF('//*[@id="viewSupplementalInformation1"]/tbody')
        self.name_match = False
        lab_reports = self.find_elements(By.XPATH, '//*[@id="eventLabReport"]/tbody/tr')
        self.dna_date, self.hbsag_date, self.total_anti_hbc_date, self.igm_anti_hbc_date, self.hbeag_date, self.anti_hbs_date, self.anti_hbe_date = (None,) * 7
        self.dna_dates = {}
        self.test_names = []
        self.text = ['hepatitis b virus dna', 'hepatitis b virus, dna', 'hepatitis b virus (hbv)','Hepatitis B virus (HBV)']
        self.text1 = ['hepatitis b virus surface antigen (hbsag)','hepatitis b virus surface antigen', 'hepatitis b virus surface ag', 'hbsag', 'hepatitis b surface ag','hepatitis b virus surface antigen, neutralization','hbsag confirmation','hep b surface ag','hepatitis b virus, antigen'] 
        self.text3 = ['igm anti-hbc', 'hep b core ab, igm', 'hepatitis b virus igm antibody', 'hepatitis b virus core antibody, igm','hepatitis b virus core ab.igg+igm','HEPATITIS B VIRUS CORE AB.IGM','hepatitis b virus core ab.igm']
        self.text2 = ['hepatitis b virus core ab', 'hepatitis b virus core antibody', 'hepatitis b virus total antibody', 'hbv core ab, igg/igm diff', 'hep b core ab, tot', 'total anti-hbc', 'hepatitis b virus core antibodies, total']
        self.text4 = ['hbeag', 'hepatitis b virus e antigen', 'hep b e ag', 'hepatitis be virus antigen (hbeag)']
        self.text5 = ['hepatitis b virus surface antibody', 'hepatitis b virus (hbv), antibody', 'hepatitis b virus surface antibody (hbsab)','hepatitis b virus surface ab', 'hbv surface ab', 'hep b surface ab','hbv surface antibody','hbsab']
        self.text6 = ['anti-hbe', 'anti-hbe antibody', 'hepatitis b virus e antibody', 'hep be ab','hepatitis b virus little e ab.igg']
        for risk in lab_reports:
            cells = risk.find_elements(By.TAG_NAME, 'td')
            date_collected = datetime.strptime(cells[2].text.strip(), "%m/%d/%Y").date()
            if cells[3].find_elements(By.TAG_NAME, 'div'):
                div_tags = cells[3].find_elements(By.TAG_NAME, 'div')
                for tag in div_tags:
                    self.result = tag.text.strip()
                    data_exists = [x for x in self.text if x in self.result.lower()]
                    if data_exists:
                        if self.dna_dates.get('hepatitis b virus, dna'):
                            #if 'positive' in self.result.lower():
                            self.dna_dates['hepatitis b virus, dna'].append(date_collected)
                            self.test_names.append(self.result)
                        else:
                            #if 'positive' in self.result.lower():
                            self.dna_dates['hepatitis b virus, dna'] = [date_collected]
                            self.test_names.append(self.result)
                            
                    elif any(x in self.result.lower() for x in self.text1):
                        if self.dna_dates.get('hepatitis b virus surface antigen'):
                            #if 'positive' in self.result.lower():
                            self.dna_dates['hepatitis b virus surface antigen'].append(date_collected)
                            self.test_names.append(self.result)
                        else:
                            self.dna_dates['hepatitis b virus surface antigen'] = [date_collected]
                            self.test_names.append(self.result)
                
                    elif any(x in self.result.lower() for x in self.text3):
                        if self.dna_dates.get('igm anti-hbc'):
                            self.dna_dates['igm anti-hbc'].append(date_collected)
                            self.test_names.append(self.result)
                        else:
                            self.dna_dates['igm anti-hbc'] = [date_collected]
                            self.test_names.append(self.result)
                            
                    elif any(x in self.result.lower() for x in self.text2):
                        if self.dna_dates.get('hepatitis b virus core ab'):
                            self.dna_dates['hepatitis b virus core ab'].append(date_collected)
                            self.test_names.append(self.result)
                        else:
                            self.dna_dates['hepatitis b virus core ab'] = [date_collected]
                            self.test_names.append(self.result)
                            
                    elif any(x in self.result.lower() for x in self.text4):
                        if self.dna_dates.get('hepatitis b virus e antigen'):
                            self.dna_dates['hepatitis b virus e antigen'].append(date_collected)
                            self.test_names.append(self.result)
                        else:
                            self.dna_dates['hepatitis b virus e antigen'] = [date_collected]
                            self.test_names.append(self.result)
                            
                    elif any(x in self.result.lower() for x in self.text5):
                        if self.dna_dates.get('hepatitis b virus surface antibody'):
                            self.dna_dates['hepatitis b virus surface antibody'].append(date_collected)
                            self.test_names.append(self.result)
                        else:
                            self.dna_dates['hepatitis b virus surface antibody'] = [date_collected]
                            self.test_names.append(self.result)
                            
                    elif any(x in self.result.lower() for x in self.text6):
                        if self.dna_dates.get('anti-hbe'):
                            self.dna_dates['anti-hbe'].append(date_collected)
                            self.test_names.append(self.result)
                        else:
                            self.dna_dates['anti-hbe'] = [date_collected]
                            self.test_names.append(self.result)
            else:
                self.result = cells[3].text.strip()
                if any(x in self.result.lower() for x in self.text):
                    if self.dna_dates.get('hepatitis b virus, dna'):
                        self.dna_dates['hepatitis b virus, dna'].append(date_collected)
                        self.test_names.append(self.result)
                    else:
                        self.dna_dates['hepatitis b virus, dna'] = [date_collected]
                        self.test_names.append(self.result)
                        
                elif any(x in self.result.lower() for x in self.text1):
                    if self.dna_dates.get('hepatitis b virus surface antigen'):
                        if 'positive' in self.result.lower():
                            self.dna_dates['hepatitis b virus surface antigen'].append(date_collected)
                            self.test_names.append(self.result)
                    else:
                        if 'positive' in self.result.lower():
                            self.dna_dates['hepatitis b virus surface antigen'] = [date_collected]
                            self.test_names.append(self.result)
                
                elif any(x in self.result.lower() for x in self.text3):
                    if self.dna_dates.get('igm anti-hbc'):
                        self.dna_dates['igm anti-hbc'].append(date_collected)
                        self.test_names.append(self.result)
                    else:
                        self.dna_dates['igm anti-hbc'] = [date_collected]
                        self.test_names.append(self.result)        
                
                elif any(x in self.result.lower() for x in self.text2):
                    if self.dna_dates.get('hepatitis b virus core ab'):
                        self.dna_dates['hepatitis b virus core ab'].append(date_collected)
                        self.test_names.append(self.result)
                    else:
                        self.dna_dates['hepatitis b virus core ab'] = [date_collected]
                        self.test_names.append(self.result)
                        
                elif any(x in self.result.lower() for x in self.text4):
                    if self.dna_dates.get('hepatitis b virus e antigen'):
                        self.dna_dates['hepatitis b virus e antigen'].append(date_collected)
                        self.test_names.append(self.result)
                    else:
                        self.dna_dates['hepatitis b virus e antigen'] = [date_collected]
                        self.test_names.append(self.result)
                        
                elif any(x in self.result.lower() for x in self.text5):
                    if self.dna_dates.get('hepatitis b virus surface antibody'):
                        self.dna_dates['hepatitis b virus surface antibody'].append(date_collected)
                        self.test_names.append(self.result)
                    else:
                        self.dna_dates['hepatitis b virus surface antibody'] = [date_collected]
                        self.test_names.append(self.result)
                        
                elif any(x in self.result.lower() for x in self.text6):
                    if self.dna_dates.get('anti-hbe'):
                        self.dna_dates['anti-hbe'].append(date_collected)
                        self.test_names.append(self.result)
                    else:
                        self.dna_dates['anti-hbe'] = [date_collected]
                        self.test_names.append(self.result)
        self.test1_names =  [x.split(':')[0].strip() for x in self.test_names]   
        self.result_check_dna = []
        self.result_check_antigen = []
        self.result_check_core = []
        self.result_check_igm = []
        self.result_check_anti_hbs = []
        self.result_check_hbeag = []
        self.result_check_anti_hbe = []
        for key, value in self.dna_dates.items():
            if key == "hepatitis b virus, dna":
                for x in self.test1_names:
                    for y in self.test_names:
                            if x.lower() in self.text:
                                if x in y:
                                    self.result_check_dna = y.split(':')[1].strip().lower() and y.split('Reference Range')[0].strip()
                                    self.dna_date = min(value)
            elif key == "hepatitis b virus surface antigen":
                if len(value) > 1:
                    for x in self.test1_names:
                        for y in self.test_names:
                            if x.lower() in self.text1:
                                if x in y:
                                    self.result_check_antigen =y.split(':')[1].strip().lower() and y.split('Reference Range')[0].strip()
                                    self.hbsag_date = min(value)
                else:
                    for x in self.test1_names:
                        for y in self.test_names:
                            if x.lower() in self.text1:
                                if x in y:
                                    self.result_check_antigen = y.split(':')[1].strip().lower()
                                    self.hbsag_date = min(value)
            elif key == "hepatitis b virus core ab":
                self.total_anti_hbc_date = min(value)
                for x in self.test1_names:
                    for y in self.test_names:
                        if x.lower() in self.text2:
                            if x in y:
                                self.result_check_core = y.split(':')[1].strip().lower()
            elif key == "igm anti-hbc":
                self.igm_anti_hbc_date = min(value)
                for x in self.test1_names:
                    for y in self.test_names:
                        if x.lower() in self.text3:
                            if x in y:
                                self.result_check_igm = y.split(':')[1].strip().lower()
            elif key == "hepatitis b virus e antigen":
                self.hbeag_date = min(value)
                for x in self.test1_names:
                    for y in self.test_names:
                        if x.lower() in self.text4:
                            if x in y:
                                self.result_check_hbeag = y.split(':')[1].strip().lower()
            elif key == "hepatitis b virus surface antibody":
                self.anti_hbs_date = min(value)
                for x in self.test1_names:
                    for y in self.test_names:
                        if x.lower() in self.text5:
                            if x in y:
                                self.result_check_anti_hbs = y.split(':')[1].strip().lower()
            elif key == "hepatitis b virus e antibody":
                self.hbeab_date = min(value)
                for x in self.test1_names:
                    for y in self.test_names:
                        if x.lower() in self.text6:
                            if x in y:
                                self.result_check_anti_hbe = y.split(':')[1].strip().lower()
        for index in range(len(self.labs)):
            row_df = self.labs.iloc[[index]]
            if row_df['Test Results'].str.contains('hepatitis b', na=False, case=False).any():
                self.labs = self.labs.loc[index]
                self.name_match = True
                break
        if not self.name_match:
            self.labs = pd.DataFrame()
            self.issues.append('Test results does not have hepatitis b.')'''