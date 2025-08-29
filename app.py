import streamlit as st
from pypdf import PdfReader, PdfWriter
import pdfplumber
import io
import zipfile
import re
import time
import math
import pandas as pd
from typing import Tuple, Dict, List

# -------------------------
# Page config + CSS
# -------------------------
st.set_page_config(page_title="📄 PDF Tools", layout="centered", initial_sidebar_state="auto")

# Small CSS tweaks for bigger home buttons / cards
st.markdown(
    """
    <style>
    .big-card {
        border: 1px solid #e6e6e6;
        border-radius: 12px;
        padding: 28px;
        text-align: center;
        box-shadow: 0 2px 6px rgba(0,0,0,0.05);
        transition: transform .08s ease-in-out;
    }
    .big-card:hover { transform: translateY(-4px); }
    .big-btn { font-size: 18px; padding: 10px 18px; border-radius: 8px; }
    .muted { color: #6c757d; font-size: 13px; }
    .footer { color: gray; text-align:center; margin-top: 18px; font-size:13px; }
    </style>
    """,
    unsafe_allow_html=True,
)

# Tooltip in title (hover shows author)
st.markdown('<h1 title="Made by AG with ❤️">📄 PDF Tools</h1>', unsafe_allow_html=True)
st.write("")  # spacer

# -------------------------
# Navigation via session_state
# -------------------------
if "page" not in st.session_state:
    st.session_state["page"] = "home"

def go_home():
    st.session_state["page"] = "home"

def go_split():
    st.session_state["page"] = "split"

def go_merge():
    st.session_state["page"] = "merge"

# -------------------------
# Helper functions
# -------------------------
def human_size(nbytes: int) -> str:
    if nbytes == 0:
        return "0 B"
    sizes = ("B", "KB", "MB", "GB", "TB")
    i = int(math.floor(math.log(nbytes, 1024)))
    p = math.pow(1024, i)
    s = round(nbytes / p, 2)
    return f"{s} {sizes[i]}"

def clean_name(line: str) -> str:
    name = re.sub(r"NAME\s*[:\-]?\s*", "", line, flags=re.IGNORECASE)
    name = re.sub(r"\d+", "", name)  # remove numbers
    name = re.sub(r"ASSIST.*", "", name, flags=re.IGNORECASE)  # remove ASSIST text
    name = name.strip().replace(" ", "_")
    # remove disallowed filename chars
    name = re.sub(r'[\\/:"*?<>|]+', "", name)
    return name if name else "Policy"

def get_unique_name(name: str, existing_names: Dict[str,int]) -> str:
    if name not in existing_names:
        existing_names[name] = 0
        return name
    else:
        existing_names[name] += 1
        return f"{name}_{existing_names[name]}"

def safe_pdfplumber_open(uploaded_file) -> io.BytesIO:
    """Return a BytesIO usable by pdfplumber (copy of uploaded bytes)."""
    return io.BytesIO(uploaded_file.getvalue())

# -------------------------
# Home page
# -------------------------
if st.session_state["page"] == "home":
    col1, col2, _ = st.columns([1,1,0.3])
    with col1:
        if st.button("🪓 Split PDF", key="split_home", help="Split a merged policy PDF into multiple policies", on_click=go_split):
            pass
        st.write("")  # spacer
        st.markdown("<div class='muted'>Split a combined PDF into individual policy PDFs.<br>Duplicate names are handled automatically.</div>", unsafe_allow_html=True)

    with col2:
        if st.button("🔗 Merge PDF", key="merge_home", help="Merge multiple PDFs into one single PDF", on_click=go_merge):
            pass
        st.write("")
        st.markdown("<div class='muted'>Upload multiple PDFs and merge them into a single file.</div>", unsafe_allow_html=True)

    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown("<div class='muted'>Choose a tool to get started.</div>", unsafe_allow_html=True)
    st.markdown("<div class='footer'>Made by AG with ❤️</div>", unsafe_allow_html=True)

# -------------------------
# Split page
# -------------------------
if st.session_state["page"] == "split":
    st.markdown("### Split PDFs")
    st.button("⬅️ Back to Home", on_click=go_home)

    uploaded_file = st.file_uploader("Upload merged policy PDF", type=["pdf"])
    st.write("")  # spacer

    split_mode = st.radio(
        "Choose split method:",
        ["Detect by TRAVEL PROTECTION CARD", "Fixed number of pages"],
    )

    pages_per_policy = None
    if split_mode == "Fixed number of pages":
        pages_per_policy = st.number_input("Enter pages per policy:", min_value=1, value=4)

    prefix = st.text_input("Optional output prefix (keeps duplicate numbering)", value="")
    download_mode = st.radio("Download output as:", ["ZIP (recommended)", "Individual files"])

    run = st.button("▶️ Run Splitter")

    if run:
        if not uploaded_file:
            st.error("Please upload a PDF file first.")
        else:
            # Start runtime timer
            start_time = time.time()

            # Prepare
            reader = PdfReader(uploaded_file)
            total_pages = len(reader.pages)
            file_size = len(uploaded_file.getvalue())
            st.info(f"File info — Pages: {total_pages} • Size: {human_size(file_size)}")
            st.write("")  # spacer

            pdf_bytes_for_plumber = safe_pdfplumber_open(uploaded_file)

            policies: List[Tuple[str, io.BytesIO]] = []
            name_counter: Dict[str,int] = {}

            progress = st.progress(0.0)
            status = st.empty()
            pages_processed = 0

            # Splitting logic
            if split_mode == "Detect by TRAVEL PROTECTION CARD":
                current_writer = None
                current_name = None
                # open pdfplumber
                try:
                    with pdfplumber.open(pdf_bytes_for_plumber) as pdf:
                        for i, page in enumerate(pdf.pages):
                            try:
                                text = page.extract_text() or ""
                            except Exception:
                                text = ""

                            pages_processed += 1
                            # progress update
                            progress.progress(pages_processed / total_pages)
                            status.text(f"Processing page {pages_processed} / {total_pages}")

                            if "TRAVEL PROTECTION CARD" in text.upper():
                                # Save previous policy
                                if current_writer and current_name:
                                    buf = io.BytesIO()
                                    current_writer.write(buf)
                                    buf.seek(0)
                                    name_with_prefix = f"{prefix}_{current_name}" if prefix else current_name
                                    unique_name = get_unique_name(name_with_prefix, name_counter)
                                    policies.append((unique_name, buf))

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
                            buf = io.BytesIO()
                            current_writer.write(buf)
                            buf.seek(0)
                            name_with_prefix = f"{prefix}_{current_name}" if prefix else current_name
                            unique_name = get_unique_name(name_with_prefix, name_counter)
                            policies.append((unique_name, buf))
                except Exception as e:
                    st.error("Error while parsing PDF text. The file might be scanned or corrupted.")
                    st.exception(e)

            else:  # Fixed number of pages
                total_pages = len(reader.pages)
                num_policies = (total_pages + pages_per_policy - 1) // pages_per_policy
                try:
                    with pdfplumber.open(pdf_bytes_for_plumber) as pdf:
                        for i in range(num_policies):
                            start = i * pages_per_policy
                            end = min(start + pages_per_policy, total_pages)

                            writer = PdfWriter()
                            for j in range(start, end):
                                writer.add_page(reader.pages[j])

                                pages_processed += 1
                                # progress update relative to all pages
                                progress.progress(pages_processed / total_pages)
                                status.text(f"Gathering pages: {pages_processed} / {total_pages}")

                            # Try to extract name from first page of this chunk
                            try:
                                text = pdf.pages[start].extract_text() or ""
                            except Exception:
                                text = ""

                            found_name = None
                            for line in text.splitlines():
                                if "NAME" in line.upper():
                                    found_name = clean_name(line)
                                    break
                            current_name = found_name if found_name else f"Policy_{i+1}"
                            name_with_prefix = f"{prefix}_{current_name}" if prefix else current_name
                            unique_name = get_unique_name(name_with_prefix, name_counter)

                            buf = io.BytesIO()
                            writer.write(buf)
                            buf.seek(0)
                            policies.append((unique_name, buf))
                except Exception as e:
                    st.error("Error while processing PDF.")
                    st.exception(e)

            progress.progress(1.0)
            status.text("Finalizing...")

            # Runtime
            runtime = time.time() - start_time

            # Show preview of extracted names
            if policies:
                st.success(f"✅ Split complete — {len(policies)} policy files created.")
                st.write(f"⏱ Runtime: {runtime:.2f} seconds")
                st.write("")
                df = pd.DataFrame([(i+1, name, len(buf.getvalue())) for i,(name,buf) in enumerate(policies)],
                                  columns=["#", "Filename", "Size (bytes)"])
                df["Size"] = df["Size (bytes)"].apply(human_size)
                df = df.drop(columns=["Size (bytes)"])
                st.dataframe(df, use_container_width=True)

                # Download options
                if download_mode == "ZIP":
                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(zip_buffer, "w") as zf:
                        for name, buf in policies:
                            zf.writestr(f"{name}.pdf", buf.getvalue())
                    zip_buffer.seek(0)
                    zip_filename = f"{policies[0][0]}_x_{len(policies)}.zip"
                    st.download_button("⬇️ Download ZIP", data=zip_buffer, file_name=zip_filename, mime="application/zip")
                else:
                    st.markdown("#### Download individually")
                    for name, buf in policies:
                        st.download_button(label=f"⬇️ {name}.pdf", data=buf.getvalue(), file_name=f"{name}.pdf", mime="application/pdf")
            else:
                st.error("No policies were produced. Check file and split settings.")

    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown("<div class='footer'>Made by AG with ❤️</div>", unsafe_allow_html=True)

# -------------------------
# Merge page
# -------------------------
if st.session_state["page"] == "merge":
    st.markdown("### Merge PDFs")
    st.button("⬅️ Back to Home", on_click=go_home)

    uploaded_files = st.file_uploader("Upload PDFs to merge (in desired order)", type=["pdf"], accept_multiple_files=True)
    merge_prefix = st.text_input("Optional output filename (without extension)", value="merged")
    merge_run = st.button("▶️ Merge PDFs")

    if merge_run:
        if not uploaded_files:
            st.error("Please upload one or more PDF files to merge.")
        else:
            start_time = time.time()
            total_files = len(uploaded_files)
            progress = st.progress(0.0)
            status = st.empty()
            writer = PdfWriter()
            processed = 0
            total_pages = 0

            # count pages (for a better progress estimation)
            for f in uploaded_files:
                try:
                    r = PdfReader(f)
                    total_pages += len(r.pages)
                except Exception:
                    pass

            pages_done = 0
            for f_idx, f in enumerate(uploaded_files):
                try:
                    r = PdfReader(f)
                except Exception as e:
                    st.warning(f"Could not read {f.name}: {e}")
                    continue
                for p in r.pages:
                    writer.add_page(p)
                    pages_done += 1
                    # progress by pages if possible
                    if total_pages > 0:
                        progress.progress(pages_done / total_pages)
                        status.text(f"Merging pages: {pages_done} / {total_pages}")
                processed += 1

            # finalize
            merged_buf = io.BytesIO()
            writer.write(merged_buf)
            merged_buf.seek(0)
            runtime = time.time() - start_time
            st.success(f"✅ Merged {processed} files into one.")
            st.write(f"Pages: {pages_done} • Runtime: {runtime:.2f} seconds")
            st.download_button("⬇️ Download merged PDF", data=merged_buf.getvalue(), file_name=f"{merge_prefix}.pdf", mime="application/pdf")

    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown("<div class='footer'>Made by AG with ❤️</div>", unsafe_allow_html=True)
