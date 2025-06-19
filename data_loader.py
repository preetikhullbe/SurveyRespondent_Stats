from elasticsearch import Elasticsearch
import pandas as pd
from datetime import datetime, timedelta, timezone
import os

ES_INDEX = "uni_session"

def save_live_data_to_parquet_chunks():
    es = Elasticsearch(
     cloud_id=st.secrets["ES_CLOUD_ID"],
     basic_auth=(st.secrets["ES_USERNAME"], st.secrets["ES_PASSWORD"])
   )

    # Last 3 months
    end_utc = datetime.now(timezone.utc)
    start_utc = end_utc - timedelta(days=1)
    start_utc_str = start_utc.isoformat().replace("+00:00", "Z")
    end_utc_str = end_utc.isoformat().replace("+00:00", "Z")

    query = {
        "query": {
            "bool": {
                "must": [
                    {
                        "range": {
                            "survey_enddate": {
                                "gte": start_utc_str,
                                "lte": end_utc_str,
                                "format": "strict_date_optional_time"
                            }
                        }
                    },
                    {"term": {"is_active": True}},
                    {"bool": {"must_not": {"term": {"clienttypeid": 1}}}}
                ]
            }
        },
        "_source": [
            "clientname", "suppliername", "respondentstatusid", "respondentstatus",
            "survey_date", "survey_enddate", "qualificationname"
        ]
    }

    scroll = '2m'
    page_size = 10000
    all_hits = []

    response = es.search(index=ES_INDEX, body=query, scroll=scroll, size=page_size)
    scroll_id = response['_scroll_id']
    hits = response['hits']['hits']
    all_hits.extend(hits)

    while hits:
        response = es.scroll(scroll_id=scroll_id, scroll=scroll)
        scroll_id = response['_scroll_id']
        hits = response['hits']['hits']
        all_hits.extend(hits)

    es.clear_scroll(scroll_id=scroll_id)

    records = [hit['_source'] for hit in all_hits]
    df = pd.DataFrame(records)

    if df.empty:
        print("⚠️ No data fetched.")
        return

    df.rename(columns={
        "clientname": "client",
        "suppliername": "supplier",
        "respondentstatusid": "RespondentStatus",
        "respondentstatus": "RespondentStatusName",
        "survey_date": "Survey_Date",
        "survey_enddate": "Survey_EndDate",
        "qualificationname": "QualificationName"
    }, inplace=True)

    os.makedirs("data_chunks", exist_ok=True)

    max_bytes = 25 * 1024 * 1024  # 25MB
    i, chunk_idx = 0, 1
    rows = len(df)

    while i < rows:
        for j in range(i + 1000, rows + 1000, 1000):
            chunk = df.iloc[i:j]
            path = f"data_chunks/chunk_{chunk_idx}.parquet"
            chunk.to_parquet(path, index=False)

            if os.path.getsize(path) > max_bytes:
                os.remove(path)
                break

            i = j
            chunk_idx += 1
            break

    print(f"✅ Saved {chunk_idx - 1} chunks in 'data_chunks/' folder.")

if __name__ == "__main__":
    save_live_data_to_parquet_chunks()
