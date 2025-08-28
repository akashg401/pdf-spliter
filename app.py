import streamlit as st
import pdfplumber
from PyPDF2 import PdfWriter
import os

# Output folder for split policies
OUTPUT_FOLDER = "split_policies"

if not os.path.exists(OUTPUT_FOLDER):
    os.makedirs(OUTPUT_FOLDER)

def get_unique_filename(base_name, ext=".pdf"):
    """
    Ensures duplicate policy names get saved with numbering.
    Example: PolicyName.pdf, PolicyName_1.pdf, PolicyName_2.pdf
    """
    filename = f"{base_name}{ext}"
    counter = 1
    while os.path.exists(os.path.join(OUTPUT_FOLDER, filename)):
        filename = f"{base_name}_{counter}{ext}"
        counter += 1
    return os.path.join(OUTPUT_FOLDER, filename)

def split_policies(pdf_file):
    """
    Splits the uploaded PDF into separate policy files based on detected policy numbers/names.
    """
    policies_saved = []

    with pdfplumber.open(pdf_file) as pdf:
        writer = None
        current_name = None

        for page_num, page in enumerate(pdf.pages):
            text = page.extract_text() or ""

            # Detect policy name/number (customize regex if needed)
            for line in text.split("\n"):
                if "Policy" in line and "No" in line:  # Example condition
                    if writer and current_name:
                        # Save previous policy
                        file_path = get_unique_filename(current_name)
                        with open(file_path, "wb") as f:
                            writer.write(f)
                        policies_saved.append(file_path)

                    # Start new policy
                    writer = PdfWriter()
                    current_name = line.strip().replace(" ", "_").replace(":", "_")
            
            # Add page to current writer
            if writer:
                writer.add_page(pdf.pages[page_num].to_pdf_page())

        # Save the last policy
        if writer and current_name:
            file_path = get_unique_filename(current_name)
            with open(file_path, "wb") as f:
                writer.write(f)
            policies_saved.append(file_path)

    return policies_saved


# =========================
# Streamlit UI
# =========================
st.set_page_config(page_title="Policy PDF Splitter", layout="centered")

st.title("📄 Policy PDF Splitter")
st.write("Upload a combined policy PDF, and this tool will split it into individual policies.")

uploaded_pdf = st.file_uploader("Upload PDF", type=["pdf"])

if uploaded_pdf:
    with st.spinner("Processing PDF..."):
        saved_files = split_policies(uploaded_pdf)

    st.success(f"✅ Done! {len(saved_files)} policies extracted.")
    st.write("Download split files below:")

    for f in saved_files:
        with open(f, "rb") as file:
            st.download_button(
                label=f"⬇️ Download {os.path.basename(f)}",
                data=file,
                file_name=os.path.basename(f),
                mime="application/pdf"
            )
