import streamlit as st
import tempfile
from finilized_respondent import process_data

st.set_page_config(page_title="Survey Respondent Report Generator", layout="wide")
st.title("📝 Survey Respondent Report Generator")

# User Input Filters
st.sidebar.header("Filters")

start_date = st.sidebar.date_input("Start Date", None)
end_date = st.sidebar.date_input("End Date", None)
client_filter = st.sidebar.text_input("Search Client (optional)")

if st.button("Generate Report"):
    with st.spinner("Processing... Please wait ⏳"):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
            process_data(tmp.name, start_date, end_date, client_filter)
            st.success("✅ Report Generated Successfully!")
            with open(tmp.name, "rb") as f:
                st.download_button("📥 Download Report", f, file_name="final_report.xlsx")
