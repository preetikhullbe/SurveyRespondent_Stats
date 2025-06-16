import streamlit as st
import pandas as pd
import tempfile
from finilized_respondent import process_data
import openpyxl

# Full-width layout, no scroll effect
st.set_page_config(page_title="Respondent Report Generator", layout="wide")

# Custom Styling - FULL REDESIGN
st.markdown("""
    <style>
    /* Global App Styling */
    .stApp {
        background-color: #f7f9fc;
        color: #333333;
        font-family: 'Segoe UI', sans-serif;
        padding-top: 0rem !important;
        margin-top: -50px !important;  /* Remove extra space above title */
    }
    header {visibility: hidden;}

    /* Title Styling */
    .title-box {
        background: linear-gradient(135deg, #00b4db, #0083b0);
        padding: 15px 0px;
        color: white;
        text-align: center;
        font-size: 38px;
        font-weight: 600;
        margin-bottom: 40px;  /* Increased space after title */
        box-shadow: 0 4px 10px rgba(0,0,0,0.2);
        border-bottom-left-radius: 25px;
        border-bottom-right-radius: 25px;
    }

    /* Form Styling */
    label, .stTextInput > label, .stDateInput > label, .stSelectbox > label {
        color: #333333 !important;
        font-weight: 600;
        font-size: 16px;
    }

    /* Generate Button Styling */
    .stButton > button {
        background-color: #FF4C4C;
        color: white;
        border-radius: 10px;
        font-size: 18px;
        padding: 0.7em 0em;
        width: 250px;
        font-weight: 600;
        white-space: nowrap;
    }

    /* Download Button Styling */
    div[data-testid="stDownloadButton"] > button {
        background-color: #4CAF50 !important;  /* Green color */
        color: white !important;
        border-radius: 10px;
        font-size: 18px !important;
        padding: 0.7em 2em !important;
        font-weight: 600 !important;
    }

    /* Report container */
    .report-container {
        background-color: #ffffff;
        padding: 25px;
        border-radius: 18px;
        margin-top: 25px;
        box-shadow: 0 0 10px rgba(0,0,0,0.15);
    }
    </style>
""", unsafe_allow_html=True)

# Title
st.markdown('<div class="title-box">Survey Respondent Report Generator</div>', unsafe_allow_html=True)

# Load parquet file
@st.cache_data
def load_data():
    df = pd.read_parquet('newclientandsupplier.parquet')
    return df

df = load_data()

# Form Layout
col1, col2, col3 = st.columns([3, 3, 3])

with col1:
    clients = sorted(df['client'].unique())
    selected_client = st.selectbox("Select Client", ["All"] + clients)

with col2:
    start_date = st.date_input("Start Date", None)

with col3:
    end_date = st.date_input("End Date", None)

# Button Centered Exactly
st.write("")
st.write("")
generate_col = st.columns([3, 3, 3])
with generate_col[1]:
    if st.button("Generate Report"):
        with st.spinner("Processing..... Please wait"):
            with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
                client_to_pass = None if selected_client == "All" else selected_client
                process_data(tmp.name, start_date, end_date, client_to_pass)
                st.success("Report Generated Successfully!")

                excel_preview = pd.read_excel(tmp.name)

                st.markdown("<h3>Report Preview</h3>", unsafe_allow_html=True)

                preview_container = st.container()
                with preview_container:
                    st.dataframe(
                        excel_preview,
                        use_container_width=True,
                        height=300,
                    )

                with open(tmp.name, "rb") as f:
                    st.download_button("Download Excel Report", f, file_name="final_report.xlsx")
