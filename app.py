import streamlit as st
import time
import io
import zipfile
from pypdf import PdfReader, PdfWriter
import pdfplumber

# ----------------- SAFE HELPERS -----------------
def load_reader(uploaded_file):
    """Return a fresh PdfReader or None if failed."""
    try:
        return PdfReader(io.BytesIO(uploaded_file.getvalue()))
    except Exception:
        st.error(f"❌ Could not read PDF `{uploaded_file.name}`. File may be corrupted or encrypted.")
        return None

def safe_open_with_plumber(uploaded_file):
    """Return a pdfplumber.PDF or None if failed."""
    try:
        return pdfplumber.open(io.BytesIO(uploaded_file.getvalue()))
    except Exception:
        st.error("❌ Could not parse text from PDF. It may be scanned (image-only) or corrupted.")
        return None

# ----------------- SPLIT FUNCTION -----------------
def split_pdf(uploaded_file):
    start_time = time.time()
    progress = st.progress(0)

    reader = load_reader(uploaded_file)
    if not reader:
        st.stop()

    with safe_open_with_plumber(uploaded_file) as pdf:
        if not pdf:
            st.stop()

        policies = {}
        current_name = None
        current_writer = None
        total_pages = len(reader.pages)

        for i, page in enumerate(reader.pages):
            text = pdf.pages[i].extract_text() or ""

            # Detect policy header
            if "Policy Number:" in text:
                current_name = text.split("Policy Number:")[1].split("\n")[0].strip()
                if current_name in policies:
                    idx = 2
                    new_name = f"{current_name}_{idx}"
                    while new_name in policies:
                        idx += 1
                        new_name = f"{current_name}_{idx}"
                    current_name = new_name

                current_writer = PdfWriter()
                policies[current_name] = current_writer

            # Always add page if writer active
            if current_writer:
                current_writer.add_page(page)

            progress.progress((i + 1) / total_pages)

    # Create ZIP for download
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zipf:
        for name, writer in policies.items():
            pdf_bytes = io.BytesIO()
            writer.write(pdf_bytes)
            zipf.writestr(f"{name}.pdf", pdf_bytes.getvalue())

    zip_buffer.seek(0)
    elapsed = time.time() - start_time
    st.success(f"✅ Done! Split into {len(policies)} files in {elapsed:.2f} seconds.")

    st.download_button(
        "📥 Download All as ZIP",
        data=zip_buffer,
        file_name="split_policies.zip",
        mime="application/zip"
    )

# ----------------- MERGE FUNCTION -----------------
def merge_pdfs(uploaded_files):
    start_time = time.time()
    progress = st.progress(0)

    writer = PdfWriter()
    total_files = len(uploaded_files)

    for idx, f in enumerate(uploaded_files):
        reader = load_reader(f)
        if not reader:
            continue
        for page in reader.pages:
            writer.add_page(page)
        progress.progress((idx + 1) / total_files)

    # Export merged PDF
    output = io.BytesIO()
    writer.write(output)
    output.seek(0)

    elapsed = time.time() - start_time
    st.success(f"✅ Done! Merged {total_files} files in {elapsed:.2f} seconds.")

    st.download_button(
        "📥 Download Merged PDF",
        data=output,
        file_name="merged.pdf",
        mime="application/pdf"
    )

# ----------------- MAIN APP -----------------
st.set_page_config(page_title="📄 PDF Tools", page_icon="📄", layout="centered")

st.title("📄 PDF Tools")
st.caption("Hover over title → Made by AG ❤️")
st.markdown("---")

menu = st.sidebar.radio("Choose an option:", ["🏠 Home", "✂️ Split PDF", "📎 Merge PDF"])

if menu == "🏠 Home":
    st.header("Welcome to PDF Tools")
    st.write("Choose an option from the left sidebar to get started:")
    st.button("➡️ Split PDF", on_click=lambda: st.session_state.update(menu="✂️ Split PDF"))
    st.button("➡️ Merge PDF", on_click=lambda: st.session_state.update(menu="📎 Merge PDF"))

elif menu == "✂️ Split PDF":
    st.header("✂️ Split PDF by Policy Number")
    uploaded_file = st.file_uploader("Upload a PDF", type=["pdf"])
    if uploaded_file and st.button("Start Splitting"):
        split_pdf(uploaded_file)

elif menu == "📎 Merge PDF":
    st.header("📎 Merge Multiple PDFs")
    uploaded_files = st.file_uploader("Upload PDFs", type=["pdf"], accept_multiple_files=True)
    if uploaded_files and st.button("Start Merging"):
        merge_pdfs(uploaded_files)

# Footer
st.markdown("---")
st.markdown("<center>Made by AG with ❤️</center>", unsafe_allow_html=True)
