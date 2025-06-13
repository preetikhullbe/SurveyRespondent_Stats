
# Survey Respondent Report Generator

A web-based tool built with **Streamlit** for generating, previewing, and downloading survey respondent reports based on client, supplier, and date filters.

---

## Features

* Upload raw Excel files for processing.
* Select specific client or view all data.
* Set custom start and end dates.
* Preview processed report directly in browser.
* Download report as Excel file.

---

## Tech Stack

* **Python 3.10+**
* **Streamlit** (UI framework)
* **Pandas** (data processing)
* **OpenPyXL** (Excel file handling)

---

## Installation & Setup

### 1️⃣ Clone the repository

```bash
git clone https://github.com/your-username/survey-respondent-report-generator.git
cd survey-respondent-report-generator
```

### 2️⃣ Create virtual environment (optional but recommended)

```bash
python -m venv venv
source venv/bin/activate   # For Linux/macOS
venv\Scripts\activate      # For Windows
```

### 3️⃣ Install dependencies

```bash
pip install -r requirements.txt
```

> **Note:** Ensure `openpyxl` is correctly installed for Excel support.

### 4️⃣ Run Streamlit App

```bash
streamlit run ui.py
```

The app will open in your browser automatically.

---

## File Structure

```bash
.
├── clientandsupplier.parquet   # Pre-processed lookup file (optional)
├── ui.py                       # Main Streamlit app
├── utils.py (optional)         # Helper functions (if modularized)
├── requirements.txt            # Python dependencies
└── README.md                   # Project documentation
```

---

## Deployment

You can easily deploy this app on:

* **Streamlit Cloud**
* **Heroku**
* **Render.com**
* **Any cloud VM (AWS EC2, Azure, GCP)**

Just make sure the following files are uploaded:

* `requirements.txt`
* `ui.py`
* Any data files (`clientandsupplier.parquet` if used)

---

## Troubleshooting

* **openpyxl not found:**

  ```bash
  pip install openpyxl
  ```
* **Parquet file missing:**
  Ensure `clientandsupplier.parquet` is present in the project directory or modify the code to create it dynamically.

---

## License

This project is for internal use. Contact the maintainer for any redistribution or reuse.

---


