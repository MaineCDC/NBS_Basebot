elif case_less_than_not_detected or (any(x in str(resulted_test_table["Coded Result / Organism Name"]) for x in ["Undetected", "Not Detected", "UNDETECTED", "NOT DETECTED", "Negative", "NEGATIVE", "Unable" ])  or any(x in str(resulted_test_table["Text Result"]) for x in ["Undetected", "Not Detected", "UNDETECTED", "NOT DETECTED", "Negative", "NEGATIVE", "Unable"]) or any(x in str(resulted_test_table["Result Comments"]) for x in ["HCV RNA Not Detected"])): 
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







elif case_less_than_not_detected or (any(x in str(resulted_test_table["Coded Result / Organism Name"]) for x in ["Undetected", "Not Detected", "UNDETECTED", "NOT DETECTED", "Negative", "NEGATIVE", "Unable" ])  or any(x in str(resulted_test_table["Text Result"]) for x in ["Undetected", "Not Detected", "UNDETECTED", "NOT DETECTED", "Negative", "NEGATIVE", "Unable"]) or any(x in str(resulted_test_table["Result Comments"]) for x in ["HCV RNA Not Detected"])):

    if lab_reports.
    if acute is not none and chronic is not none:
        year = int(datetime.today().strftime("%Y"))
        mmwr_week = Week(year, 1)
        if len(acute) > 0  and inv_date > mmwr_week.startdate() and test_type == "RNA" and "Probable" in acute["Case Status"].values:
            not_a_case = True
            update_status = True
            associate = True  
        elif len(chronic) > 0  and inv_date > mmwr_week.startdate() and test_type == "RNA" and "Probable" in chronic["Case Status"].values:
            not_a_case = True
            update_status = True
            associate = True
        else:
            mark_reviewed = True
    