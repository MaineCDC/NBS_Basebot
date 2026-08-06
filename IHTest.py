import pandas as pd

import pyodbc

from openpyxl import load_workbook

from datetime import datetime


#1.connect to sql

conn = pyodbc.connect("DRIVER={SQL Server};"

                          "SERVER=172.17.135.14;"
                          "port=1433;"

                          "DATABASE=rdb;"

                          "UID=me_rdb_readonly;"

                          "PWD=Stu0icuKi$=uTrep;"

                     )
print("Connection established successfully.")

views = {

  "Outbreak_data": "Select * from  rdb.dbo.outbreak_datamart where  season = '2025_2026'",

}

today = datetime.today().strftime('%m_%d_%Y')

output_file = fr"C:\Users\vaishnavi.appidi\Documents\Roux_{today}.xlsx"

with pd.ExcelWriter(output_file,engine="openpyxl") as writer :

    for sheet_name,query in views.items():

        df = pd.read_sql_query(query, conn)

        df.to_excel(writer,sheet_name=sheet_name , index=False)


conn.close()
 
print(f"Report create sucessfully: {output_file}")
 