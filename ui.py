import streamlit as st
import pandas as pd
import tempfile
from finilized_respondent import process_data
import openpyxl

# Wide layout for full width
st.set_page_config(page_title="Survey Respondent Report", layout="wide")

# Custom CSS Styling
st.markdown("""
    <style>
    .stApp {
        background-color: #2a2a2a;
        color: #E0E0E0;
        font-family: 'Segoe UI', sans-serif;
        padding-top: 0rem !important;
    }
    header {visibility: hidden;}
    .title-box {
        background-color: #2196F3;
        padding: 10px 0px;
        border-radius: 12px;
        color: white;
        text-align: center;
        font-size: 26px;
        font-weight: 500;
        margin-bottom: 15px;
        box-shadow: 0 3px 8px rgba(0,0,0,0.4);
    }
    label, .stTextInput > label, .stDateInput > label, .stSelectbox > label {
        color: #E0E0E0 !important;
        font-weight: 600;
    }
    .stButton > button {
        background-color: #2196F3;
        color: white;
        border-radius: 10px;
        font-size: 18px;
        padding: 0.6em 2.5em;
        margin-top: 10px;
    }
    .stDataFrame {
        background-color: #1F1F1F !important;
    }
    .report-container {
        background-color: #1f1f1f;
        padding: 20px;
        border-radius: 12px;
        margin-top: 20px;
        box-shadow: 0 0 10px rgba(0,0,0,0.4);
    }
    </style>
""", unsafe_allow_html=True)

# Page Title - No top margin
st.markdown('<div class="title-box">Survey Respondent Report Generator</div>', unsafe_allow_html=True)

# Load parquet
@st.cache_data
def load_data():
    df = pd.read_parquet('newclientandsupplier.parquet')
    return df

df = load_data()

# Layout the form
col1, col2, col3 = st.columns([3, 3, 3])

with col1:
    clients = sorted(df['client'].unique())
    selected_client = st.selectbox("Select Client", ["All"] + clients)

with col2:
    start_date = st.date_input("Start Date", None)

with col3:
    end_date = st.date_input("End Date", None)

# Generate Button - exactly below Start Date (centered under col2)
st.write("")
st.write("")
generate_col = st.columns([3, 3, 3])
with generate_col[1]:
    if st.button("Generate Report"):
        with st.spinner("Processing... Please wait ⏳"):
            with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
                client_to_pass = None if selected_client == "All" else selected_client
                process_data(tmp.name, start_date, end_date, client_to_pass)
                st.success("Report Generated Successfully!")

                excel_preview = pd.read_excel(tmp.name)

                st.markdown("<h3>Report Preview</h3>", unsafe_allow_html=True)

                # Leave side margins for cleaner look
                preview_container = st.container()
                with preview_container:
                    st.dataframe(
                        excel_preview,
                        use_container_width=True,
                        height=430  # adjusted height to fit download button
                    )

                # Download button below preview
                with open(tmp.name, "rb") as f:
                    st.download_button("Download Excel Report", f, file_name="final_report.xlsx")
