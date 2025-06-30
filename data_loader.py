import os
import pandas as pd
from datetime import datetime, timedelta
from elasticsearch import Elasticsearch
import pyarrow as pa
import pyarrow.parquet as pq

ES_INDEX = "uni_session"
cloud_id = os.getenv("ES_CLOUD_ID")
username = os.getenv("ES_USERNAME")
password = os.getenv("ES_PASSWORD")

if not all([cloud_id, username, password]):
    raise ValueError("One or more Elasticsearch credentials are missing.")
    
def fetch_last_3_months_data(es):
    end_date = datetime.now()
    start_date = end_date - timedelta(days=3)

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
    es = Elasticsearch(cloud_id=cloud_id, basic_auth=(username, password))
    df = fetch_last_3_months_data(es)

    if df.empty:
        print("No data to save.")
        return

    os.makedirs("data_chunks", exist_ok=True)

    for f in os.listdir("data_chunks"):
        if f.endswith(".parquet"):
            os.remove(os.path.join("data_chunks", f))

    target_chunk_size_mb = 25
    rows_per_estimate = 10000
    chunk = []
    current_size = 0
    file_index = 0

    for i in range(0, len(df), rows_per_estimate):
        part = df.iloc[i:i + rows_per_estimate]
        table = pa.Table.from_pandas(part)
        sink = pa.BufferOutputStream()
        pq.write_table(table, sink)
        size_mb = sink.tell() / 1_000_000

        if current_size + size_mb >= target_chunk_size_mb and chunk:
            combined = pd.concat(chunk)
            chunk_path = f"data_chunks/clientandsupplier1_part{file_index}.parquet"
            combined.to_parquet(chunk_path, index=False)
            print(f"Saved {chunk_path} ({current_size:.2f} MB)")
            file_index += 1
            chunk = []
            current_size = 0

        chunk.append(part)
        current_size += size_mb

    if chunk:
        combined = pd.concat(chunk)
        chunk_path = f"data_chunks/clientandsupplier1_part{file_index}.parquet"
        combined.to_parquet(chunk_path, index=False)
        print(f"Saved {chunk_path} ({current_size:.2f} MB)")


if __name__ == "__main__":
    save_live_data_to_parquet_chunks()
