import os
import re
import tempfile
import streamlit as st
import pdfplumber
from pypdf import PdfReader, PdfWriter

# === Function to clean name ===
def extract_name(text):
    for line in text.splitlines():
        if "NAME" in line.upper():
            clean = re.sub(r"NAME\s*[:\-]?\s*", "", line, flags=re.IGNORECASE).strip()
            clean = re.sub(r"\bASSIST.*", "", clean, flags=re.IGNORECASE)  # remove ASSIST+
            clean = re.sub(r"\d+", "", clean)  # remove numbers
            return clean.strip().replace(" ", "_")
    return None

# === Streamlit UI ===
st.title("📑 Policy Splitter")
st.write("Upload a multi-policy PDF, and I’ll split it into individual policies by **Name :** field.")

uploaded_file = st.file_uploader("Upload PDF", type=["pdf"])

if uploaded_file is not None:
    if st.button("🚀 Run Splitter"):
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(uploaded_file.read())
            input_pdf = tmp.name

        reader = PdfReader(input_pdf)
        total_policies = len(reader.pages) // 4

        # Extract first name for folder naming
        with pdfplumber.open(input_pdf) as pdf:
            first_page_text = pdf.pages[0].extract_text()
            first_text = extract_name(first_page_text) if first_page_text else "Policy"

        output_folder = f"{first_text}_x_{total_policies}"
        os.makedirs(output_folder, exist_ok=True)

        # Split policies
        for i in range(total_policies):
            start_page = i * 4
            end_page = start_page + 4

            with pdfplumber.open(input_pdf) as pdf:
                raw_text = pdf.pages[start_page].extract_text()
                policy_name = extract_name(raw_text) if raw_text else None

            if not policy_name:
                policy_name = f"Policy_{i+1}"

            writer = PdfWriter()
            for j in range(start_page, end_page):
                if j < len(reader.pages):
                    writer.add_page(reader.pages[j])

            output_file = os.path.join(output_folder, f"{policy_name}.pdf")
            with open(output_file, "wb") as f:
                writer.write(f)

        st.success(f"✅ Done! Split into {total_policies} files inside `{output_folder}`")

        # Create zip for download
        import shutil
        zip_file = f"{output_folder}.zip"
        shutil.make_archive(output_folder, 'zip', output_folder)

        with open(zip_file, "rb") as f:
            st.download_button("⬇️ Download All Policies (ZIP)", f, file_name=zip_file)
