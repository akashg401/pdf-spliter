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

def clean_name(line):
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
                    # Save previous policy first
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
                policies.append((current_name, pdf_bytes))

    # === Mode 2: Fixed number of pages ===
    elif pages_per_policy and pages_per_policy > 0:
        total_policies = (len(reader.pages) + pages_per_policy - 1) // pages_per_policy
        with pdfplumber.open(uploaded_file) as pdf:
            for i in range(total_policies):
                start_page = i * pages_per_policy
                end_page = min(start_page + pages_per_policy, len(reader.pages))
                writer = PdfWriter()
                for j in range(start_page, end_page):
                    writer.add_page(reader.pages[j])

                # Extract passenger name from first page of split
                raw_text = pdf.pages[start_page].extract_text() or ""
                policy_name = None
                for line in raw_text.splitlines():
                    if "NAME" in line.upper():
                        policy_name = clean_name(line)
                        break
                if not policy_name:
                    policy_name = f"Policy_{i+1}"

                pdf_bytes = io.BytesIO()
                writer.write(pdf_bytes)
                pdf_bytes.seek(0)
                policies.append((policy_name, pdf_bytes))

    # === Build ZIP file ===
    if policies:
        first_name = policies[0][0]
        total_count = len(policies)
        zip_name = f"{first_name}_x_{total_count}.zip"

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zipf:
            for policy_name, pdf_bytes in policies:
                zipf.writestr(f"{policy_name}.pdf", pdf_bytes.read())

        zip_buffer.seek(0)
        st.success(f"✅ Done! Split into {total_count} policies")
        st.download_button("⬇️ Download All Policies (ZIP)", zip_buffer, zip_name, "application/zip")
