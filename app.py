import streamlit as st
from pypdf import PdfReader, PdfWriter
import io
import zipfile
import time
import os
from datetime import timedelta

# ============== PAGE CONFIG =================
st.set_page_config(page_title="📄 PDF Tools", page_icon="📄", layout="centered")

# Inject CSS for background color & footer
st.markdown("""
    <style>
        body {
            background-color: #f5f5f5;
        }
        footer {
            visibility: hidden;
        }
        .footer-text {
            position: fixed;
            bottom: 10px;
            width: 100%;
            text-align: center;
            color: grey;
            font-size: 14px;
        }
    </style>
""", unsafe_allow_html=True)

# ============== TITLE =================
st.markdown(
    """
    <h1 title="Made by AG with ❤️">📄 PDF Tools</h1>
    """,
    unsafe_allow_html=True
)

# Navigation
choice = st.sidebar.radio("Choose Tool", ["🔹 Split PDF", "🔹 Merge PDF"])

# ============== SPLIT PDF =================
if choice == "🔹 Split PDF":
    st.header("Split PDF")
    uploaded_file = st.file_uploader("Upload a PDF to split", type="pdf")

    split_mode = st.radio("Choose split mode:",
                          ("Fixed number of pages", "Search keyword"),
                          index=0)  # Default set to "Fixed number of pages"

    if split_mode == "Fixed number of pages":
        pages_per_split = st.number_input("Pages per split:", min_value=1, value=1)

    elif split_mode == "Search keyword":
        keyword = st.text_input("Enter keyword (e.g., TRAVEL PROTECTION CARD)", value="TRAVEL PROTECTION CARD")

    if uploaded_file and st.button("Start Splitting"):
        start_time = time.time()
        pdf_reader = PdfReader(uploaded_file)
        total_pages = len(pdf_reader.pages)

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zipf:
            if split_mode == "Fixed number of pages":
                for i in range(0, total_pages, pages_per_split):
                    pdf_writer = PdfWriter()
                    for j in range(i, min(i + pages_per_split, total_pages)):
                        pdf_writer.add_page(pdf_reader.pages[j])

                    output_stream = io.BytesIO()
                    pdf_writer.write(output_stream)
                    zipf.writestr(f"split_{i // pages_per_split + 1}.pdf", output_stream.getvalue())

                    progress = (i + pages_per_split) / total_pages
                    st.progress(min(progress, 1.0))

            elif split_mode == "Search keyword":
                pdf_writer = None
                part_number = 1

                for page_num, page in enumerate(pdf_reader.pages):
                    text = page.extract_text() or ""
                    if keyword in text:
                        if pdf_writer:  # save previous
                            output_stream = io.BytesIO()
                            pdf_writer.write(output_stream)
                            zipf.writestr(f"part_{part_number}.pdf", output_stream.getvalue())
                            part_number += 1
                        pdf_writer = PdfWriter()

                    if pdf_writer is None:
                        pdf_writer = PdfWriter()

                    pdf_writer.add_page(page)

                    st.progress((page_num + 1) / total_pages)

                if pdf_writer:  # save last part
                    output_stream = io.BytesIO()
                    pdf_writer.write(output_stream)
                    zipf.writestr(f"part_{part_number}.pdf", output_stream.getvalue())

        end_time = time.time()
        runtime = str(timedelta(seconds=int(end_time - start_time)))

        st.success(f"✅ Splitting complete in {runtime}")
        st.download_button("📥 Download ZIP", buffer.getvalue(),
                           file_name="split_pdfs.zip", mime="application/zip")

# ============== MERGE PDF =================
elif choice == "🔹 Merge PDF":
    st.header("Merge PDFs")
    uploaded_files = st.file_uploader("Upload PDFs to merge", type="pdf", accept_multiple_files=True)

    if uploaded_files and st.button("Start Merging"):
        start_time = time.time()
        pdf_writer = PdfWriter()

        for idx, uploaded_file in enumerate(uploaded_files):
            pdf_reader = PdfReader(uploaded_file)
            for page in pdf_reader.pages:
                pdf_writer.add_page(page)

            st.progress((idx + 1) / len(uploaded_files))

        buffer = io.BytesIO()
        pdf_writer.write(buffer)

        end_time = time.time()
        runtime = str(timedelta(seconds=int(end_time - start_time)))

        st.success(f"✅ Merging complete in {runtime}")
        st.download_button("📥 Download Merged PDF", buffer.getvalue(),
                           file_name="merged.pdf", mime="application/pdf")

# ============== FOOTER =================
st.markdown('<div class="footer-text">Made by AG with ❤️</div>', unsafe_allow_html=True)
