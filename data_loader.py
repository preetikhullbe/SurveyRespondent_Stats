import os
import pandas as pd
from datetime import datetime, timedelta
from elasticsearch import Elasticsearch
import subprocess

ES_INDEX = "uni_session"
cloud_id = os.getenv("ES_CLOUD_ID")
username = os.getenv("ES_USERNAME")
password = os.getenv("ES_PASSWORD")

if not all([cloud_id, username, password]):
    raise ValueError("One or more Elasticsearch credentials are missing.")
    
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

    response = es.search(index=ES_INDEX, query=query["query"], _source=query["_source"], scroll=scroll, size=page_size)
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
        cloud_id=cloud_id,
        basic_auth=(username, password)
    )
    df = fetch_last_3_months_data(es)

    if df.empty:
        print("No data to save.")
        return

    os.makedirs("data_chunks", exist_ok=True)

    # Clear old files
    for f in os.listdir("data_chunks"):
        if f.endswith(".parquet"):
            os.remove(os.path.join("data_chunks", f))

    approx_rows_per_chunk = 100_000
    for i, start in enumerate(range(0, len(df), approx_rows_per_chunk)):
        chunk = df.iloc[start:start + approx_rows_per_chunk]
        chunk_path = f"data_chunks/clientandsupplier1_part{i}.parquet"
        chunk.to_parquet(chunk_path, index=False)
        size_mb = os.path.getsize(chunk_path) / 1_000_000
        print(f"Saved {chunk_path} ({size_mb:.2f} MB)")

    # Git commit & push
    subprocess.run(["git", "config", "--global", "user.email", "data-bot@example.com"])
    subprocess.run(["git", "config", "--global", "user.name", "GitHub Action Bot"])

    subprocess.run(["git", "add", "data_chunks/*.parquet"])
    subprocess.run(["git", "commit", "-m", "🔄 Auto-update: new daily data chunks"], check=False)
    subprocess.run(["git", "push"], check=True)
    print("Pushed updated data chunks to GitHub.")


if __name__ == "__main__":
    save_live_data_to_parquet_chunks()
