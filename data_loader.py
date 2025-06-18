# data_loader.py (RUN SEPARATELY - e.g. once a day)
import pandas as pd
import pyodbc
import streamlit as st

def save_live_data_to_parquet():
    # Load credentials from environment or .env
    server = st.secrets["DB_SERVER"]
    database = st.secrets["DB_NAME"]
    username = st.secrets["DB_USER"]
    password = st.secrets["DB_PASS"]
    conn_str = (
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={server};DATABASE={database};UID={username};PWD={password}"
    )

    query = """
    SELECT
        C.ClientName AS client, 
        cv.SupplierName AS supplier,
        S.RespondentStatus,
        rs.Name AS RespondentStatusName,
        S.Survey_Date,
        S.Survey_EndDate,
        q.QualificationName
    FROM APIClient_Surveys AS acs 
    LEFT JOIN Clients C WITH (NOLOCK) ON acs.ClientId = C.ClientId
    LEFT JOIN Survey_Info S WITH (NOLOCK) ON acs.SurveyId = S.SurveyId
    LEFT JOIN Suppliers cv WITH (NOLOCK) ON cv.SupplierId = S.SupplierId
    LEFT JOIN RespondentStatus rs WITH (NOLOCK) ON S.RespondentStatus = rs.RespondentStatusId
    LEFT JOIN Qualifications q WITH (NOLOCK) ON q.QualificationId = S.TermQualificationId
    WHERE 
        S.Survey_EndDate >= CAST(DATEADD(DAY, -1, GETDATE()) AS DATE)
        AND C.clientTypeId <> 1 
        AND C.ISActive = 1
    """

    with pyodbc.connect(conn_str) as conn:
        df = pd.read_sql(query, conn)

    df.to_parquet("clientandsupplier1.parquet", index=False)
    print(f"✅ Saved {len(df)} rows to clientandsupplier1.parquet")

if __name__ == "__main__":
    save_live_data_to_parquet()
