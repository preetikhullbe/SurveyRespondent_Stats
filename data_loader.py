import os
import pandas as pd
from datetime import datetime, timedelta
from elasticsearch import Elasticsearch

ES_INDEX = "uni_session"

def fetch_last_3_months_data(es):
    end_date = datetime.now()
    start_date = end_date - timedelta(days=1)

    start_str = start_date.strftime("%Y-%m-%dT%H:%M:%S")
    end_str = end_date.strftime("%Y-%m-%dT%H:%M:%S")

    query = {
        "query": {
            "range": {
                "survey_enddate": {
                    "gte": start_str,
                    "lte": end_str,
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

    print(f"✅ Retrieved {len(all_hits)} records.")
    return pd.DataFrame([hit['_source'] for hit in all_hits])


def save_live_data_to_parquet_chunks():
    es = Elasticsearch(
        cloud_id=os.environ.get("ES_CLOUD_ID"),
        basic_auth=(os.environ.get("ES_USERNAME"), os.environ.get("ES_PASSWORD"))
    )

    df = fetch_last_3_months_data(es)

    if df.empty:
        print("⚠️ No data to save.")
        return

    os.makedirs("data_chunks", exist_ok=True)

    max_file_size_mb = 25
    approx_rows_per_chunk = 100_000
    i = 0

    for start in range(0, len(df), approx_rows_per_chunk):
        chunk = df.iloc[start:start + approx_rows_per_chunk]
        chunk_path = f"data_chunks/clientandsupplier1_part{i}.parquet"
        chunk.to_parquet(chunk_path, index=False)
        file_size = os.path.getsize(chunk_path) / 1_000_000
        print(f"✅ Saved {chunk_path} ({file_size:.2f} MB)")
        i += 1


if __name__ == "__main__":
    save_live_data_to_parquet_chunks()
