import os
import pandas as pd
from datetime import datetime, timedelta
from elasticsearch import Elasticsearch
import pyarrow as pa
import pyarrow.parquet as pq
import io

ES_INDEX = "uni_session"
cloud_id = os.getenv("ES_CLOUD_ID")
username = os.getenv("ES_USERNAME")
password = os.getenv("ES_PASSWORD")

if not all([cloud_id, username, password]):
    raise ValueError("One or more Elasticsearch credentials are missing.")

def fetch_last_3_months_data(es):
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)

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

    # Clear all existing parquet files first
    for f in os.listdir("data_chunks"):
        if f.endswith(".parquet"):
            os.remove(os.path.join("data_chunks", f))

    chunk_index = 0
    max_chunk_size_mb = 25
    table = pa.Table.from_pandas(df)
    batch_size = 10000

    current_batch = []
    current_size = 0.0

    writer = None
    for i in range(0, len(df), batch_size):
        batch_df = df.iloc[i:i+batch_size]
        batch_table = pa.Table.from_pandas(batch_df)

        sink = io.BytesIO()
        pq.write_table(batch_table, sink)
        size_mb = sink.getbuffer().nbytes / 1_000_000

        if current_size + size_mb > max_chunk_size_mb and current_batch:
            # Write current batch to file
            full_table = pa.Table.from_pandas(pd.concat(current_batch))
            chunk_path = f"data_chunks/clientandsupplier1_part{chunk_index}.parquet"
            pq.write_table(full_table, chunk_path)
            print(f"Saved {chunk_path} ({current_size:.2f} MB)")
            chunk_index += 1
            current_batch = []
            current_size = 0.0

        current_batch.append(batch_df)
        current_size += size_mb

    # Write remaining records
    if current_batch:
        full_table = pa.Table.from_pandas(pd.concat(current_batch))
        chunk_path = f"data_chunks/clientandsupplier1_part{chunk_index}.parquet"
        pq.write_table(full_table, chunk_path)
        print(f"Saved {chunk_path} ({current_size:.2f} MB)")

    # Cleanup: remove any leftover old files
    existing_files = set(f for f in os.listdir("data_chunks") if f.endswith(".parquet"))
    expected_files = {f"clientandsupplier1_part{i}.parquet" for i in range(chunk_index + 1)}
    leftovers = existing_files - expected_files
    for f in leftovers:
        os.remove(os.path.join("data_chunks", f))
        print(f"Removed old leftover file: {f}")

if __name__ == "__main__":
    save_live_data_to_parquet_chunks()
