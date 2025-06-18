import streamlit as st
import pandas as pd
import tempfile
import base64
from finilized_respondent import process_data
from datetime import datetime, timedelta
import time

st.set_page_config(page_title="Report Generator", layout="wide")

# Load background image and convert to base64
def get_base64(file_path):
    with open(file_path, "rb") as f:
        data = f.read()
    return base64.b64encode(data).decode()

background_base64 = get_base64("background.png")

# Inject fixed full-page layout and styling
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

# Title with single-line margin
st.markdown('<div class="title">Survey Respondent Report Generator</div>', unsafe_allow_html=True)

# Main content
with st.container():
    st.markdown('<div class="main-content">', unsafe_allow_html=True)

@st.cache_data(ttl=86400)
def load_cached_data():
    import os
    import pandas as pd

    chunk_folder = "data_chunks"
    chunk_files = sorted(
        [f for f in os.listdir(chunk_folder) if f.endswith(".parquet")],
        key=lambda x: int(x.split("_")[1].split(".")[0])
    )

    all_chunks = [pd.read_parquet(os.path.join(chunk_folder, f)) for f in chunk_files]
    df = pd.concat(all_chunks, ignore_index=True)
    return df
    df=load_cached_data()
    clients = sorted(df['client'].unique())

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
            start_date = st.date_input("Start Date", None)
            end_date = st.date_input("End Date", None)
        else:
            st.markdown(f"**Start Date:** {start_date}")
            st.markdown(f"**End Date:** {end_date}")

        # Buttons in the same row
        btn_col1, btn_col2 = st.columns([1, 1])
        generate_clicked = False

        with btn_col1:
            generate_clicked = st.button("Generate Report")

    with right_col:
        if generate_clicked:
            if not start_date or not end_date:
                st.warning("⚠️ Please select both Start Date and End Date.")
            elif end_date < start_date:
                st.warning("⚠️ End Date must be after Start Date.")
            elif not selected_clients:
                st.warning("⚠️ Please select at least one client.")
            else:
                client_to_pass = None if "All" in selected_clients else selected_clients

                progress_text = "⏳ Generating report..."
                my_bar = st.progress(0, text=progress_text)
                for percent_complete in range(0, 101):
                    time.sleep(0.005)
                    my_bar.progress(percent_complete, text=f"{progress_text} {percent_complete}%")

                with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
                   process_data(df,tmp.name, start_date, end_date, client_to_pass)
                   tmp_file_path = tmp.name

                   df_preview = pd.read_excel(tmp_file_path)

                   if len(df_preview) < 1:
                      st.warning("⚠️ Report is empty, select any other data range.")
                      report_generated = False
                   else:
                      st.success("✅ Report Generated Successfully!")
                      st.dataframe(df_preview, use_container_width=True, height=305)
                      report_generated = True


    # Show download button in the same row
    if report_generated and tmp_file_path:
        with btn_col2:
            with open(tmp_file_path, "rb") as f:
                st.download_button("Download Report", f, file_name="final_report.xlsx")

    st.markdown('</div>', unsafe_allow_html=True)
