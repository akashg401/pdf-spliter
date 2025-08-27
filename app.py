import io
import re
import zipfile
import streamlit as st
import pdfplumber
from pypdf import PdfReader, PdfWriter

st.title("📄 PDF Policy Splitter")

uploaded_file = st.file_uploader("Upload a PDF", type="pdf")

split_mode = st.radio(
    "How do you want to split?",
    ["Detect by NAME :", "Fixed number of pages"]
)

pages_per_policy = None
if split_mode == "Fixed number of pages":
    pages_per_policy = st.number_input(
        "Enter number of pages per policy",
        min_value=1,
        max_value=50,
        value=4,  # default
        step=1
    )

def clean_name(line):
    clean = re.sub(r"NAME\s*[:\-]?\s*", "", line, flags=re.IGNORECASE).strip()
    clean = re.sub(r"\bASSIST.*", "", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\d+", "", clean)  # remove numbers
    return clean.strip().replace(" ", "_")

if uploaded_file and st.button("🚀 Run Splitter"):
    reader = PdfReader(uploaded_file)
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w") as zipf:
        if split_mode == "Detect by NAME :":
            # Dynamic detection mode
            current_writer = None
            curre
