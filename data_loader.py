import os
import io
import pandas as pd
from datetime import datetime, timedelta
from elasticsearch import Elasticsearch
from elasticsearch.helpers import scan
from elasticsearch.exceptions import ConnectionTimeout, TransportError
import pyarrow as pa
import pyarrow.parquet as pq
from concurrent.futures import ThreadPoolExecutor

# === Config ===
ES_INDEX = "uni_session"
cloud_id = os.getenv("ES_CLOUD_ID")
username = os.getenv("ES_USERNAME")
password = os.getenv("ES_PASSWORD")

if not all([cloud_id, username, password]):
    raise ValueError("One or more Elasticsearch credentials are missing.")

FIELDS = [
    "clientname", "suppliername", "respondentstatusid",
    "respondentstatus", "survey_enddate", "qualificationname"
]

MAX_CHUNK_SIZE_MB = 25
BATCH_SIZE = 10000
CHUNK_DIR = "data_chunks"

# === Functions ===

def fetch_last_3_months_data(es):
    end_date = datetime.now()
    start_date = end_date - timedelta(days=20)

    query = {
        "query": {
            "range": {
                "survey_enddate": {
                    "gte": start_date.strftime("%Y-%m-%dT%H:%M:%S"),
                    "lte": end_date.strftime("%Y-%m-%dT%H:%M:%S"),
                    "format": "strict_date_optional_time"
                }
            }
        }
    }

    print("Fetching data from Elasticsearch...")
    try:
        results = scan(
            es,
            index=ES_INDEX,
            query=query,
            _source_includes=FIELDS,
            size=10000,
            scroll='2m'
        )
        docs = [hit["_source"] for hit in results]
        print(f"Retrieved {len(docs)} records.")
        return pd.DataFrame(docs)
    except (ConnectionTimeout, TransportError) as e:
        print(f"Elasticsearch scan failed: {e}")
        return pd.DataFrame()

def write_parquet_chunk(chunk_df, chunk_index):
    table = pa.Table.from_pandas(chunk_df)
    path = os.path.join(CHUNK_DIR, f"clientandsupplier1_part{chunk_index}.parquet")
    pq.write_table(table, path)
    size_mb = table.nbytes / 1_000_000
    print(f"✅ Saved {path} ({size_mb:.2f} MB)")

def save_live_data_to_parquet_chunks():
    os.makedirs(CHUNK_DIR, exist_ok=True)

    # Clear old chunks
    for f in os.listdir(CHUNK_DIR):
        if f.endswith(".parquet"):
            os.remove(os.path.join(CHUNK_DIR, f))

    # Connect to Elasticsearch
    es = Elasticsearch(
        cloud_id=cloud_id,
        basic_auth=(username, password),
        request_timeout=60,
        max_retries=3,
        retry_on_timeout=True
    )

    df = fetch_last_3_months_data(es)
    if df.empty:
        print("No data to save.")
        return

    chunk_index = 0
    current_batch = []
    current_size = 0.0
    futures = []

    with ThreadPoolExecutor() as executor:
        for i in range(0, len(df), BATCH_SIZE):
            batch_df = df.iloc[i:i+BATCH_SIZE]
            batch_table = pa.Table.from_pandas(batch_df)
            sink = io.BytesIO()
            pq.write_table(batch_table, sink)
            size_mb = sink.getbuffer().nbytes / 1_000_000

            if current_size + size_mb > MAX_CHUNK_SIZE_MB and current_batch:
                full_df = pd.concat(current_batch)
                futures.append(executor.submit(write_parquet_chunk, full_df, chunk_index))
                chunk_index += 1
                current_batch = []
                current_size = 0.0

            current_batch.append(batch_df)
            current_size += size_mb

        # Final chunk
        if current_batch:
            full_df = pd.concat(current_batch)
            futures.append(executor.submit(write_parquet_chunk, full_df, chunk_index))

        # Wait for all writes to complete
        for future in futures:
            future.result()

    print("✅ All chunks saved successfully.")

if __name__ == "__main__":
    save_live_data_to_parquet_chunks()
