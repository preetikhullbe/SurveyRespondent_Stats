import os
import pandas as pd
from datetime import datetime, timedelta, timezone
from elasticsearch import Elasticsearch, helpers

ES_INDEX = "uni_session"

def fetch_last_3_months_data(es):
    end_utc = datetime.now(timezone.utc)
    start_utc = end_utc - timedelta(days=1)

    query = {
        "query": {
            "range": {
                "survey_enddate": {
                    "gte": start_utc.isoformat().replace('+00:00', 'Z'),
                    "lte": end_utc.isoformat().replace('+00:00', 'Z'),
                    "format": "strict_date_optional_time"
                }
            }
        },
        "_source": [
            "clientname", "suppliername", "respondentstatusid",
            "respondentstatus", "survey_enddate", "qualificationname"
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
    print(f"Retrieved {len(all_hits)} records.")
    return pd.DataFrame([hit['_source'] for hit in all_hits])


def save_live_data_to_parquet_chunks():
    es = Elasticsearch(
        cloud_id=os.environ.get("ES_CLOUD_ID"),
        basic_auth=(os.environ.get("ES_USER"), os.environ.get("ES_PASS"))
    )

    df = fetch_last_3_months_data(es)

    if df.empty:
        print("No data to save.")
        return

    os.makedirs("data_chunks", exist_ok=True)
    max_file_size_mb = 25
    chunk_rows = 100_000  # adjust based on typical row size

    i = 0
    for start in range(0, len(df), chunk_rows):
        chunk = df.iloc[start:start + chunk_rows]
        tmp_path = f"data_chunks/clientandsupplier1_part{i}.parquet"
        chunk.to_parquet(tmp_path, index=False)
        size_mb = os.path.getsize(tmp_path) / 1_000_000
        if size_mb > max_file_size_mb:
            print(f"Warning: {tmp_path} is {size_mb:.2f}MB, consider reducing chunk_rows.")
        else:
            print(f"Saved chunk {i} to {tmp_path} ({size_mb:.2f}MB)")
        i += 1


if __name__ == "__main__":
    save_live_data_to_parquet_chunks()
