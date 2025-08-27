# Deployment sync test


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
    ["Detect by TRAVEL PROTECTION CARD", "Fixed number of pages"]
)

pages_per_policy = None
if split_mode == "Fixed number of pages":
    pages_per_policy = st.number_input(
        "Enter number of pages per policy",
        min_value=1,
        max_value=50,
        value=4,
        step=1
    )

def clean_name(line: str) -> str:
    """Clean the passenger name from a NAME: line."""
    clean = re.sub(r"NAME\s*[:\-]?\s*", "", line, flags=re.IGNORECASE).strip()
    clean = re.sub(r"\bASSIST.*", "", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\d+", "", clean)  # remove numbers
    return clean.strip().replace(" ", "_")

if uploaded_file and st.button("🚀 Run Splitter"):
    reader = PdfReader(uploaded_file)
    policies = []  # store tuples (policy_name, pdf_bytes)

    # === Mode 1: Detect by keyword ===
    if split_mode == "Detect by TRAVEL PROTECTION CARD":
        current_writer = None
        current_name = None

        with pdfplumber.open(uploaded_file) as pdf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ""

                if "TRAVEL PROTECTION CARD" in text.upper():
                    # Save previous policy before starting new
                    if current_writer and current_name:
                        pdf_bytes = io.BytesIO()
                        current_writer.write(pdf_bytes)
                        pdf_bytes.seek(0)
                        policies.append((current_name, pdf_bytes))

                    # Start new policy
                    current_writer = PdfWriter()
                    current_writer.add_page(reader.pages[i])

                    # Extract passenger name
                    current_name = None
                    for line in text.splitlines():
                        if "NAME" in line.upper():
                            current_name = clean_name(line)
                            break
                    if not current_name:
                        current_name = f"Policy_{len(policies)+1}"
                else:
                    # Add page to current policy
                    if current_writer:
                        current_writer.add_page(reader.pages[i])

            # Save last policy
            if current_writer and current_name:
                pdf_bytes = io.BytesIO()
                current_writer.write(pdf_bytes)
                pdf_bytes.seek(0)
                polic
