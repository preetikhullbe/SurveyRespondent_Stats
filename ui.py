import streamlit as st
import pandas as pd
import tempfile
import base64
import os
import time
from datetime import datetime, timedelta
from finilized_respondent import process_data

# Set up the Streamlit page
st.set_page_config(page_title="Report Generator", layout="wide")

# Load background image and convert to base64
def get_base64(file_path):
    with open(file_path, "rb") as f:
        data = f.read()
    return base64.b64encode(data).decode()

background_base64 = get_base64("background.png")

# Inject styling
st.markdown(f"""
    <style>
    html, body, .stApp {{
        height: 100vh;
        margin: 0 !important;
        padding: 0 !important;
        overflow: hidden !important;
    }}
    .stApp {{
        background-image: url("data:image/png;base64,{background_base64}");
        background-size: cover;
        background-repeat: no-repeat;
        background-position: center;
        background-attachment: fixed;
    }}
    header {{visibility: hidden;}}
    .title {{
        background: linear-gradient(135deg, #00b4db, #0083b0);
        color: white;
        padding: 10px 15px;
        text-align: center;
        border-radius: 0 0 16px 16px;
        box-shadow: 0px 4px 12px rgba(0,0,0,0.25);
        font-size: 24px;
        font-weight: 600;
        margin-top: 10px !important;
        margin-bottom: 10px !important;
        position: fixed;
        top: 10px;
        width: 100%;
        z-index: 999;
        left: 50%;
        transform: translateX(-50%);
    }}
    .main-content {{
        position: fixed;
        top: 80px;
        left: 0;
        right: 0;
        bottom: 0;
        padding: 10px 20px;
    }}
    .stButton > button {{
        background-color: #FF4C4C !important;
        color: white !important;
        font-weight: 600 !important;
        border-radius: 10px !important;
        font-size: 16px !important;
        padding: 10px 30px !important;
    }}
    .stButton > button:hover {{
        background-color: #e84141 !important;
    }}
    div[data-testid="stDownloadButton"] > button {{
        background-color: #4CAF50 !important;
        color: white !important;
        font-weight: 600 !important;
        border-radius: 10px !important;
        font-size: 16px !important;
        padding: 10px 30px !important;
        margin-top: 0px !important;
    }}
    </style>
""", unsafe_allow_html=True)

# Title
st.markdown('<div class="title">Survey Respondent Report Generator</div>', unsafe_allow_html=True)

# Caching loaded data
@st.cache_data(ttl=86400)
def load_cached_data():
    chunk_folder = os.path.join(os.path.dirname(__file__), "data_chunks")
    if not os.path.exists(chunk_folder):
        st.error("❌ Data not found. Please make sure the `data_chunks/` folder exists with .parquet files.")
        st.stop()
    chunk_files = sorted(
        [f for f in os.listdir(chunk_folder) if f.endswith(".parquet")],
        key=lambda x: int(x.split("part")[1].split(".")[0])
    )
    all_chunks = [pd.read_parquet(os.path.join(chunk_folder, f)) for f in chunk_files]
    df = pd.concat(all_chunks, ignore_index=True)
    return df

# Load the data
with st.container():
    st.markdown('<div class="main-content">', unsafe_allow_html=True)

    df = load_cached_data()
    clients = sorted(df['clientname'].dropna().unique())

    left_col, right_col = st.columns([1, 2], gap="small")
    report_generated = False
    tmp_file_path = None

    with left_col:
        selected_clients = st.multiselect("Select Client(s)", ["All"] + clients, default=["All"])
        preset = st.selectbox("Quick Date Range", ["Custom", "Last 7 Days", "Last 15 Days", "This Month"])

        today = datetime.today().date()
        start_date, end_date = None, None

        if preset == "Last 7 Days":
            start_date = today - timedelta(days=7)
            end_date = today
        elif preset == "Last 15 Days":
            start_date = today - timedelta(days=15)
            end_date = today
        elif preset == "This Month":
            start_date = today.replace(day=1)
            end_date = today

        if preset == "Custom":
            start_date = st.date_input("Start Date")
            end_date = st.date_input("End Date")
        else:
            st.markdown(f"**Start Date:** {start_date}")
            st.markdown(f"**End Date:** {end_date}")

        btn_col1, btn_col2 = st.columns([1, 1])
        generate_clicked = btn_col1.button("Generate Report")

    with right_col:
        if generate_clicked:
            if not start_date or not end_date:
                st.warning("⚠️ Please select both Start Date and End Date.")
            elif end_date < start_date:
                st.warning("⚠️ End Date must be after Start Date.")
            elif not selected_clients:
                st.warning("⚠️ Please select at least one client.")
            else:
                client_filter = None if "All" in selected_clients else selected_clients

                my_bar = st.progress(0, text="⏳ Preparing to generate report...")

                def update_progress(progress, message):
                    percent = int(progress * 100)
                    my_bar.progress(min(progress, 1.0), text=f"{message} ({percent}%)")

                try:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
                        process_data(
                            df,
                            tmp.name,
                            start_date=start_date,
                            end_date=end_date,
                            client_filter=client_filter,
                            progress_callback=update_progress
                        )
                        tmp_file_path = tmp.name

                    if not os.path.exists(tmp_file_path) or os.path.getsize(tmp_file_path) == 0:
                        st.warning("⚠️ Report generation failed or resulted in an empty file.")
                        report_generated = False
                    else:
                        df_preview = pd.read_excel(tmp_file_path)
                        if df_preview.empty:
                            st.warning("⚠️ The report contains no data for the selected filters. Please adjust the date range or client.")
                            report_generated = False
                        else:
                            st.success(f"✅ Report Generated Successfully! ({len(df_preview)} rows)")
                            st.dataframe(df_preview, use_container_width=True, height=305)
                            report_generated = True

                except Exception as e:
                    st.error(f"❌ Report generation failed: {e}")
                    report_generated = False

    if report_generated and tmp_file_path:
        with btn_col2:
            with open(tmp_file_path, "rb") as f:
                st.download_button("Download Report", f, file_name="final_report.xlsx")

    st.markdown('</div>', unsafe_allow_html=True)
