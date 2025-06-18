import os
import pandas as pd
import pyodbc

def save_live_data_to_parquet_chunks():
    server = ${{ secrets.DB_SERVER }}
    database = ${{ secrets.DB_NAME }}
    username = ${{ secrets.DB_USER }}
    password = ${{ secrets.DB_PASS }}

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
        S.Survey_EndDate >= CAST(DATEADD(DAY, -10, GETDATE()) AS DATE)
        AND C.clientTypeId <> 1 
        AND C.ISActive = 1
    """

    with pyodbc.connect(conn_str) as conn:
        df = pd.read_sql(query, conn)

    os.makedirs("data_chunks", exist_ok=True)

    max_mb = 24
    max_bytes = max_mb * 1024 * 1024
    rows = len(df)
    i, chunk_idx = 0, 1

    while i < rows:
        for j in range(i + 1000, rows + 1000, 1000):
            chunk = df.iloc[i:j]
            temp_path = f"data_chunks/chunk_{chunk_idx}.parquet"
            chunk.to_parquet(temp_path, index=False)
            if os.path.getsize(temp_path) > max_bytes:
                os.remove(temp_path)
                break
            i = j
            chunk_idx += 1
            break

    print(f"✅ Saved {chunk_idx - 1} chunks in 'data_chunks/' folder")

if __name__ == "__main__":
    save_live_data_to_parquet_chunks()
