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

# CSS tweaks
st.markdown(
    """
    <style>
   .stApp {
    background-color: #f7f7f8;
}
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

# Tooltip in title
st.markdown('<h1 title="Made by AG with ❤️">📄 PDF Tools</h1>', unsafe_allow_html=True)
st.write("")  # spacer

# -------------------------
# Navigation
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
# Helper functions (existing)
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
    name = re.sub(r"\d+", "", name)
    name = re.sub(r"ASSIST.*", "", name, flags=re.IGNORECASE)
    name = name.strip().replace(" ", "_")
    name = re.sub(r'[\\/:"*?<>|]+', "", name)
    return name if name else "Policy"

def get_unique_name(name: str, existing_names: Dict[str, int]) -> str:
    if name not in existing_names:
        existing_names[name] = 0
        return name
    else:
        existing_names[name] += 1
        return f"{name}_{existing_names[name]}"

def safe_pdfplumber_open(uploaded_file) -> io.BytesIO:
    return io.BytesIO(uploaded_file.getvalue())

# -------------------------
# NEW Helper functions for invoice splitting
# -------------------------
def sanitize_invoice_name(name: str) -> str:
    """
    Clean name for filenames – keep spaces, remove bad characters.
    """
    name = name.strip()
    name = re.sub(r'[\\/:"*?<>|]+', "", name)
    name = re.sub(r"\s+", " ", name)
    return name or "Invoice"

def find_invoice_start_pages(pdf_bytes: bytes, trigger_text: str) -> List[int]:
    """
    Return 0-based page indices where a new invoice starts.
    We detect by presence of trigger_text (e.g. ADIONA TRAVELS PVT LTD)
    in page text.
    """
    starts: List[int] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for i, page in enumerate(pdf.pages):
            try:
                text = page.extract_text() or ""
            except Exception:
                text = ""
            if trigger_text.upper() in text.upper():
                starts.append(i)
    return starts

def compute_invoice_ranges(start_pages: List[int], total_pages: int) -> List[Tuple[int, int]]:
    """
    Given 0-based start pages and total pages, return list of (start, end)
    page ranges (0-based, inclusive).
    """
    ranges: List[Tuple[int, int]] = []
    for idx, start in enumerate(start_pages):
        if idx < len(start_pages) - 1:
            end = start_pages[idx + 1] - 1
        else:
            end = total_pages - 1
        ranges.append((start, end))
    return ranges

def extract_invoice_metadata(pdf, start_idx: int, end_idx: int) -> Tuple[str, int, str, str]:
    """
    From pages [start_idx, end_idx] (0-based, inclusive) of a pdfplumber PDF,
    extract:
      - invoice_no (str or None)
      - total_members (int or None)
      - first_member_name (str or None)
      - full_text (str)  # for debug / analysis

    Designed to handle both:
      - older multi-column tables ("Name of Member")
      - newer Asego format ("Name of Traveller") :contentReference[oaicite:1]{index=1}
    """
    texts = []
    for i in range(start_idx, end_idx + 1):
        try:
            t = pdf.pages[i].extract_text() or ""
        except Exception:
            t = ""
        texts.append(t)
    full_text = "\n".join(texts)

    # -------------------------
    # 1) Invoice number
    # -------------------------
    invoice_no = None
    m = re.search(
        r"Invoice\s*No\.?\s*[:\-]?\s*([A-Za-z0-9\-\/]+)",
        full_text,
        flags=re.IGNORECASE
    )
    if not m:
        # fallback to 'Invoice no.' variant
        m = re.search(
            r"Invoice\s*no\.?\s*[:\-]?\s*([A-Za-z0-9\-\/]+)",
            full_text,
            flags=re.IGNORECASE
        )
    if m:
        invoice_no = m.group(1).strip()

    # -------------------------
    # 2) Locate table segment
    # -------------------------
    header_idx = -1
    for header in ["name of member", "name of traveller"]:
        header_idx = full_text.lower().find(header)
        if header_idx != -1:
            break

    segment = full_text[header_idx:] if header_idx != -1 else full_text

    lines = [ln for ln in segment.splitlines() if ln.strip()]

    # -------------------------
    # 3) Detect member rows & total_members
    #    Row pattern: starts with 1 / 01 / 1. / 01. etc
    # -------------------------
    row_pattern = re.compile(r"^\s*\d+\s*[.)]?\s+")
    member_lines = [ln for ln in lines if row_pattern.match(ln)]

    total_members = len(member_lines) if member_lines else None

    # -------------------------
    # 4) First member name
    #    We parse the first member row line.
    # -------------------------
    first_member = None
    if member_lines:
        row_line = member_lines[0]
        # Remove Sr. No. prefix
        row_line = row_pattern.sub("", row_line).strip()

        tokens = row_line.split()
        name_tokens = []
        for tok in tokens:
            # Stop name at first token containing a digit (IC82221, 110070081838, etc.)
            if re.search(r"\d", tok):
                break
            name_tokens.append(tok)

        if name_tokens:
            first_member = re.sub(r"\s+", " ", " ".join(name_tokens)).strip()

    return invoice_no, total_members, first_member, full_text


# -------------------------
# Home page
# -------------------------
if st.session_state["page"] == "home":
    col1, col2, _ = st.columns([1, 1, 0.3])
    with col1:
        if st.button("🪓 Split PDF", key="split_home", help="Split a merged policy PDF into multiple policies", on_click=go_split):
            pass
        st.write("")
        st.markdown(
            "<div class='muted'>Split a combined PDF into individual policy PDFs.<br>Duplicate names are handled automatically.</div>",
            unsafe_allow_html=True
        )

    with col2:
        if st.button("🔗 Merge PDF", key="merge_home", help="Merge multiple PDFs into one single PDF", on_click=go_merge):
            pass
        st.write("")
        st.markdown(
            "<div class='muted'>Upload multiple PDFs and merge them into a single file.</div>",
            unsafe_allow_html=True
        )

    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown("<div class='muted'>Choose a tool to get started.</div>", unsafe_allow_html=True)
    st.markdown("<div class='footer'>Made by AG with ❤️</div>", unsafe_allow_html=True)

# -------------------------
# Split page
# -------------------------
if st.session_state["page"] == "split":
    st.markdown("### Split PDFs")
    st.button("⬅️ Back to Home", on_click=go_home)

    # Select feature: existing Policies or new Invoices
    split_feature = st.radio(
        "What do you want to split?",
        ["Policies (existing)", "Invoices (Asego Global)"],
        index=0
    )

    # -------------------------
    # Existing POLICY splitter (unchanged, just wrapped)
    # -------------------------
    if split_feature == "Policies (existing)":
        uploaded_file = st.file_uploader("Upload merged policy PDF", type=["pdf"])
        st.write("")

        split_mode = st.radio(
            "Choose split method:",
            ["Fixed number of pages", "Detect by TRAVEL PROTECTION CARD"],
            index=0
        )

        pages_per_policy = None
        if split_mode == "Fixed number of pages":
            pages_per_policy = st.number_input("Enter pages per policy:", min_value=1, value=4)

        run = st.button("▶️ Run Splitter")

        if run:
            if not uploaded_file:
                st.error("Please upload a PDF file first.")
            else:
                start_time = time.time()

                reader = PdfReader(uploaded_file)
                total_pages = len(reader.pages)
                file_size = len(uploaded_file.getvalue())
                st.info(f"File info — Pages: {total_pages} • Size: {human_size(file_size)}")
                st.write("")

                pdf_bytes_for_plumber = safe_pdfplumber_open(uploaded_file)
                policies: List[Tuple[str, io.BytesIO]] = []
                name_counter: Dict[str, int] = {}

                progress = st.progress(0.0)
                status = st.empty()
                pages_processed = 0

                if split_mode == "Detect by TRAVEL PROTECTION CARD":
                    current_writer, current_name = None, None
                    try:
                        with pdfplumber.open(pdf_bytes_for_plumber) as pdf:
                            for i, page in enumerate(pdf.pages):
                                try:
                                    text = page.extract_text() or ""
                                except Exception:
                                    text = ""
                                pages_processed += 1
                                progress.progress(pages_processed / total_pages)
                                status.text(f"Processing page {pages_processed} / {total_pages}")

                                if "TRAVEL PROTECTION CARD" in text.upper():
                                    if current_writer and current_name:
                                        buf = io.BytesIO()
                                        current_writer.write(buf)
                                        buf.seek(0)
                                        unique_name = get_unique_name(current_name, name_counter)
                                        policies.append((unique_name, buf))

                                    current_writer = PdfWriter()
                                    current_writer.add_page(reader.pages[i])

                                    found_name = None
                                    for line in text.splitlines():
                                        if "NAME" in line.upper():
                                            found_name = clean_name(line)
                                            break
                                    current_name = found_name if found_name else f"Policy_{len(policies)+1}"
                                else:
                                    if current_writer:
                                        current_writer.add_page(reader.pages[i])

                            if current_writer and current_name:
                                buf = io.BytesIO()
                                current_writer.write(buf)
                                buf.seek(0)
                                unique_name = get_unique_name(current_name, name_counter)
                                policies.append((unique_name, buf))
                    except Exception as e:
                        st.error("Error while parsing PDF text. The file might be scanned or corrupted.")
                        st.exception(e)

                else:  # Fixed number of pages
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
                                    progress.progress(pages_processed / total_pages)
                                    status.text(f"Gathering pages: {pages_processed} / {total_pages}")

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
                                unique_name = get_unique_name(current_name, name_counter)

                                buf = io.BytesIO()
                                writer.write(buf)
                                buf.seek(0)
                                policies.append((unique_name, buf))
                    except Exception as e:
                        st.error("Error while processing PDF.")
                        st.exception(e)

                progress.progress(1.0)
                status.text("Finalizing...")
                runtime = time.time() - start_time

                if policies:
                    st.success(f"✅ Split complete — {len(policies)} policy files created.")
                    st.write(f"⏱ Runtime: {runtime:.2f} seconds")
                    df = pd.DataFrame(
                        [(i+1, name, len(buf.getvalue())) for i, (name, buf) in enumerate(policies)],
                        columns=["#", "Filename", "Size (bytes)"]
                    )
                    df["Size"] = df["Size (bytes)"].apply(human_size)
                    df = df.drop(columns=["Size (bytes)"])
                    st.dataframe(df, use_container_width=True)

                    # ZIP only
                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(zip_buffer, "w") as zf:
                        for name, buf in policies:
                            zf.writestr(f"{name}.pdf", buf.getvalue())
                    zip_buffer.seek(0)
                    zip_filename = f"{policies[0][0]}_x_{len(policies)}.zip"
                    st.download_button(
                        "⬇️ Download ZIP",
                        data=zip_buffer,
                        file_name=zip_filename,
                        mime="application/zip"
                    )
                else:
                    st.error("No policies were produced. Check file and split settings.")

        st.markdown("<hr>", unsafe_allow_html=True)
        st.markdown("<div class='footer'>Made by AG with ❤️</div>", unsafe_allow_html=True)

            # -------------------------
    # NEW: Invoice splitter
    # -------------------------
    if split_feature == "Invoices (Asego Global)":
        uploaded_file = st.file_uploader(
            "Upload merged invoices PDF",
            type=["pdf"]
        )

        trigger_text = st.text_input(
            "Text that marks start of each invoice (client name / header)",
            value="",
            placeholder="e.g. ASEGO GLOBAL ASSISTANCE LIMITED",
            help="Each time this text appears on a new page, a new invoice is assumed to start."
        )

        debug_mode = st.checkbox(
            "Debug: show parsed invoice text for each invoice",
            value=False
        )

        run_invoice = st.button("▶️ Run Invoice Splitter")

        if run_invoice:
            if not uploaded_file:
                st.error("Please upload a PDF file first.")
            elif not trigger_text.strip():
                st.error("Please enter a trigger text to detect invoice starts.")
            else:
                start_time = time.time()

                reader = PdfReader(uploaded_file)
                total_pages = len(reader.pages)
                file_size = len(uploaded_file.getvalue())
                st.info(f"File info — Pages: {total_pages} • Size: {human_size(file_size)}")
                st.write("")

                raw_bytes = uploaded_file.getvalue()
                start_pages_0 = find_invoice_start_pages(raw_bytes, trigger_text)
                if not start_pages_0:
                    st.error("No invoice start pages found using the given trigger text.")
                    st.stop()

                ranges = compute_invoice_ranges(start_pages_0, total_pages)

                pdf_bytes_for_plumber = safe_pdfplumber_open(uploaded_file)
                invoices: List[Tuple[str, io.BytesIO]] = []
                summary_rows: List[Dict[str, object]] = []
                name_counter: Dict[str, int] = {}

                progress = st.progress(0.0)
                status = st.empty()
                pages_processed = 0

                try:
                    with pdfplumber.open(pdf_bytes_for_plumber) as pdf:
                        for idx, (start, end) in enumerate(ranges, start=1):
                            writer = PdfWriter()
                            for j in range(start, end + 1):
                                writer.add_page(reader.pages[j])
                                pages_processed += 1
                                progress.progress(pages_processed / total_pages)
                                status.text(f"Processing pages: {pages_processed} / {total_pages}")

                            invoice_no, total_members, first_member, invoice_text = extract_invoice_metadata(
                                pdf, start, end
                            )

                            if first_member and total_members:
                                base_name = f"{first_member} x {total_members}"
                            elif first_member:
                                base_name = first_member
                            elif invoice_no:
                                base_name = f"Invoice_{invoice_no}"
                            else:
                                base_name = f"Invoice_{idx}"

                            base_name = sanitize_invoice_name(base_name)
                            unique_name = get_unique_name(base_name, name_counter)

                            buf = io.BytesIO()
                            writer.write(buf)
                            buf.seek(0)
                            invoices.append((unique_name, buf))

                            summary_rows.append({
                                "#": idx,
                                "Filename": f"{unique_name}.pdf",
                                "Invoice Number": invoice_no or "",
                                "Members": total_members if total_members is not None else "",
                                "Pages": (end - start + 1),
                            })

                            # Debug: show parsed text for this invoice
                            if debug_mode:
                                with st.expander(f"Debug: Invoice {idx} – {unique_name}"):
                                    st.text(invoice_text)
                except Exception as e:
                    st.error("Error while processing invoice PDF.")
                    st.exception(e)
                    st.stop()

                progress.progress(1.0)
                status.text("Finalizing...")
                runtime = time.time() - start_time

                if invoices:
                    st.success(f"✅ Split complete — {len(invoices)} invoice files created.")
                    st.write(f"⏱ Runtime: {runtime:.2f} seconds")

                    # Summary table
                    df = pd.DataFrame(summary_rows)
                    st.dataframe(df, use_container_width=True)

                    # CSV download
                    csv_bytes = df.to_csv(index=False).encode("utf-8")
                    st.download_button(
                        "⬇️ Download CSV summary",
                        data=csv_bytes,
                        file_name="invoice_summary.csv",
                        mime="text/csv"
                    )

                    # Per-invoice download (Point 2)
                    with st.expander("Download individual invoices"):
                        for (name, buf), row in zip(invoices, summary_rows):
                            st.download_button(
                                label=f"Download #{row['#']}: {name}",
                                data=buf.getvalue(),
                                file_name=f"{name}.pdf",
                                mime="application/pdf",
                                key=f"dl_invoice_{row['#']}"
                            )

                    # ZIP of invoices
                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(zip_buffer, "w") as zf:
                        for name, buf in invoices:
                            zf.writestr(f"{name}.pdf", buf.getvalue())
                    zip_buffer.seek(0)
                    zip_filename = f"invoices_x_{len(invoices)}.zip"
                    st.download_button(
                        "⬇️ Download ZIP of invoices",
                        data=zip_buffer,
                        file_name=zip_filename,
                        mime="application/zip"
                    )
                else:
                    st.error("No invoices were produced. Check file and trigger text.")

        st.markdown("<hr>", unsafe_allow_html=True)
        st.markdown("<div class='footer'>Made by AG with ❤️</div>", unsafe_allow_html=True)

# -------------------------
# Merge page
# -------------------------
if st.session_state["page"] == "merge":
    st.markdown("### Merge PDFs")
    st.button("⬅️ Back to Home", on_click=go_home)

    uploaded_files = st.file_uploader(
        "Upload PDFs to merge (in desired order)",
        type=["pdf"],
        accept_multiple_files=True
    )
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
            total_pages, pages_done, processed = 0, 0, 0

            for f in uploaded_files:
                try:
                    r = PdfReader(f)
                    total_pages += len(r.pages)
                except Exception:
                    pass

            for f_idx, f in enumerate(uploaded_files):
                try:
                    r = PdfReader(f)
                except Exception as e:
                    st.warning(f"Could not read {f.name}: {e}")
                    continue
                for p in r.pages:
                    writer.add_page(p)
                    pages_done += 1
                    if total_pages > 0:
                        progress.progress(pages_done / total_pages)
                        status.text(f"Merging pages: {pages_done} / {total_pages}")
                processed += 1

            merged_buf = io.BytesIO()
            writer.write(merged_buf)
            merged_buf.seek(0)
            runtime = time.time() - start_time
            st.success(f"✅ Merged {processed} files into one.")
            st.write(f"Pages: {pages_done} • Runtime: {runtime:.2f} seconds")
            st.download_button(
                "⬇️ Download merged PDF",
                data=merged_buf.getvalue(),
                file_name=f"{merge_prefix}.pdf",
                mime="application/pdf"
            )

    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown("<div class='footer'>Made by AG with ❤️</div>", unsafe_allow_html=True)
