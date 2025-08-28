import streamlit as st
from pypdf import PdfReader, PdfWriter
import pdfplumber
import io
import zipfile
import re

st.set_page_config(page_title="PDF Policy Splitter", layout="centered")

st.title("📄 PDF Policy Splitter")

uploaded_file = st.file_uploader("Upload merged policy PDF", type=["pdf"])

split_mode = st.radio(
    "Choose split method:",
    ["Detect by TRAVEL PROTECTION CARD", "Fixed number of pages"],
)

pages_per_policy = None
if split_mode == "Fixed number of pages":
    pages_per_policy = st.number_input("Enter pages per policy:", min_value=1, value=4)

run = st.button("▶️ Run Splitter")

def clean_name(line: str) -> str:
    # Remove "NAME :", digits, ASSIST_NO, etc.
    name = re.sub(r"NAME\s*[:\-]?\s*", "", line, flags=re.IGNORECASE)
    name = re.sub(r"\d+", "", name)  # remove numbers
    name = re.sub(r"ASSIST.*", "", name, flags=re.IGNORECASE)  # remove ASSIST text
    name = name.strip().replace(" ", "_")
    return name if name else "Policy"

def get_unique_name(name: str, existing_names: dict) -> str:
    """
    Returns a unique filename (without extension).
    Example: Policy → Policy, Policy_1, Policy_2, ...
    """
    if name not in existing_names:
        existing_names[name] = 0
        return name
    else:
        existing_names[name] += 1
        return f"{name}_{existing_names[name]}"

if run and uploaded_file:
    reader = PdfReader(uploaded_file)
    policies = []
    name_counter = {}  # track duplicates

    if split_mode == "Detect by TRAVEL PROTECTION CARD":
        current_writer = None
        current_name = None

        with pdfplumber.open(uploaded_file) as pdf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ""

                if "TRAVEL PROTECTION CARD" in text.upper():
                    # Save previous policy
                    if current_writer and current_name:
                        pdf_bytes = io.BytesIO()
                        current_writer.write(pdf_bytes)
                        pdf_bytes.seek(0)
                        unique_name = get_unique_name(current_name, name_counter)
                        policies.append((unique_name, pdf_bytes))

                    # Start new policy
                    current_writer = PdfWriter()
                    current_writer.add_page(reader.pages[i])

                    # Extract name
                    found_name = None
                    for line in text.splitlines():
                        if "NAME" in line.upper():
                            found_name = clean_name(line)
                            break
                    current_name = found_name if found_name else f"Policy_{len(policies)+1}"
                else:
                    if current_writer:
                        current_writer.add_page(reader.pages[i])

            # Save last policy
            if current_writer and current_name:
                pdf_bytes = io.BytesIO()
                current_writer.write(pdf_bytes)
                pdf_bytes.seek(0)
                unique_name = get_unique_name(current_name, name_counter)
                policies.append((unique_name, pdf_bytes))

    elif split_mode == "Fixed number of pages":
        total_pages = len(reader.pages)
        num_policies = (total_pages + pages_per_policy - 1) // pages_per_policy

        with pdfplumber.open(uploaded_file) as pdf:
            for i in range(num_policies):
                start = i * pages_per_policy
                end = min(start + pages_per_policy, total_pages)

                writer = PdfWriter()
                for j in range(start, end):
                    writer.add_page(reader.pages[j])

                # Try to extract name
                text = pdf.pages[start].extract_text() or ""
                found_name = None
                for line in text.splitlines():
                    if "NAME" in line.upper():
                        found_name = clean_name(line)
                        break
                current_name = found_name if found_name else f"Policy_{i+1}"
                unique_name = get_unique_name(current_name, name_counter)

                pdf_bytes = io.BytesIO()
                writer.write(pdf_bytes)
                pdf_bytes.seek(0)
                policies.append((unique_name, pdf_bytes))

    # === Build ZIP ===
    if policies:
        first_name = policies[0][0]
        zip_filename = f"{first_name}_x_{len(policies)}.zip"

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            for name, pdf_bytes in policies:
                zf.writestr(f"{name}.pdf", pdf_bytes.getvalue())
        zip_buffer.seek(0)

        st.success(f"✅ Split into {len(policies)} policies!")
        st.download_button(
            label="⬇️ Download ZIP",
            data=zip_buffer,
            file_name=zip_filename,
            mime="application/zip",
        )
    else:
        st.error("❌ No policies detected. Check the PDF or mode.")
