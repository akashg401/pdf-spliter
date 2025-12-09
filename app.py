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
st.write("")

# -------------------------
# Navigation + session
# -------------------------
if "page" not in st.session_state:
    st.session_state["page"] = "home"

if "invoice_result" not in st.session_state:
    st.session_state["invoice_result"] = None

def go_home():
    st.session_state["page"] = "home"

def go_split():
    st.session_state["page"] = "split"

def go_merge():
    st.session_state["page"] = "merge"

# -------------------------
# Helper functions (generic)
# -------------------------
def human_size(nbytes: int) -> str:
    if nbytes == 0:
        return "0 B"
    sizes = ("B", "KB", "MB", "GB", "TB")
    i = int(math.floor(math.log(nbytes, 1024)))
    p = math.pow(1024, i)
    s = round(nbytes / p, 2)
    return f"{s} {sizes[i]}"

def get_unique_name(name: str, existing_names: Dict[str, int]) -> str:
    if name not in existing_names:
        existing_names[name] = 0
        return name
    existing_names[name] += 1
    return f"{name}_{existing_names[name]}"

def safe_pdfplumber_open(uploaded_file) -> io.BytesIO:
    return io.BytesIO(uploaded_file.getvalue())

# -------------------------
# Policy metadata helpers
# -------------------------
def clean_policy_name_segment(raw: str) -> str:
    """
    Clean the raw text after 'Insured Name:' or similar into a proper name.
    - Drop tokens with digits (e.g. '2Date', 'Dat1e')
    - Stop at label tokens like DATE / BIRTH / DOB
    - Keep only A–Z tokens that look like names
    """
    if not raw:
        return ""

    tokens = re.split(r"\s+", raw.strip())
    cleaned_tokens: List[str] = []

    for tok in tokens:
        core = tok.strip(",:/()")
        if not core:
            continue

        up = core.upper()

        # Stop when we hit label-ish tokens
        if up in {"DATE", "DAT", "BIRTH", "DOB"}:
            break

        # Drop OCR garbage containing digits
        if re.search(r"\d", core):
            continue

        # Drop useless filler (from "Date of Birth")
        if up in {"OF"}:
            continue

        # Only keep alphabetic name-looking tokens
        if not re.match(r"^[A-Z][A-Z'-]*$", up):
            continue

        cleaned_tokens.append(core)

    if not cleaned_tokens:
        # Fallback – return trimmed raw if everything was filtered out
        return raw.strip()

    return " ".join(cleaned_tokens)


def extract_policy_metadata_from_text(full_text: str) -> Dict[str, str]:
    """
    Extract policy-level metadata from one policy's text:
      - Name
      - Assist No (travel/assist/certificate/card code)
      - Start Date
      - End Date
      - Date of Birth
      - Passport Number
    Handles both old 'TRAVEL PROTECTION CARD' PDFs and newer ICICI/Asego policies.
    """
    meta = {
        "Name": "",
        "Assist No": "",
        "Start Date": "",
        "End Date": "",
        "Date of Birth": "",
        "Passport Number": "",
    }

    def first_match(pattern: str, flags=re.IGNORECASE) -> str:
        m = re.search(pattern, full_text, flags)
        return m.group(1).strip() if m else ""

    # ----- Assist No / Certificate / Card code -----
    assist = ""

    # 1) Certificate No (prefer this; clean in certificate section)
    m = re.search(
        r"Certificate\s+No\s*[:.]?\s*([A-Z0-9]+)",
        full_text,
        flags=re.IGNORECASE,
    )
    if m:
        candidate = m.group(1).strip()
        if re.search(r"\d", candidate) and len(candidate) >= 5:
            assist = candidate

    # 2) Assist No
    if not assist:
        m = re.search(
            r"Assist\s*No\.?\s*[:.]?\s*([A-Z0-9]+)",
            full_text,
            flags=re.IGNORECASE,
        )
        if m:
            candidate = m.group(1).strip()
            if re.search(r"\d", candidate) and len(candidate) >= 5:
                assist = candidate

    # 3) Travel Protection Card line: ICxxxx right under the heading
    if not assist:
        m = re.search(
            r"Travel\s+Protection\s+Card\s*[\r\n]+([A-Z0-9]{5,})",
            full_text,
            flags=re.IGNORECASE,
        )
        if m:
            candidate = m.group(1).strip()
            if re.search(r"\d", candidate):
                assist = candidate

    meta["Assist No"] = assist

    # ----- Name -----
    name = ""

    # Primary: "Insured Name: <line>"
    m = re.search(
        r"Insured\s+Name\s*:\s*([^\r\n]+)",
        full_text,
        flags=re.IGNORECASE,
    )
    if m:
        name = clean_policy_name_segment(m.group(1))

    # Fallback: "Traveller" + next line on card
    if not name:
        m = re.search(
            r"Traveller\s*[\r\n]+([A-Za-z][A-Za-z\s\.'-]+)",
            full_text,
            flags=re.IGNORECASE,
        )
        if m:
            name = clean_policy_name_segment(m.group(1))

    # Very generic fallback: "Name: ..." but not "Name of ..."
    if not name:
        m = re.search(
            r"\bName\s*:\s*([^\r\n]+)",
            full_text,
            flags=re.IGNORECASE,
        )
        if m and "name of" not in m.group(0).lower():
            name = clean_policy_name_segment(m.group(1))

    meta["Name"] = name

    # ----- Start / End Date -----
    start_date = ""
    end_date = ""

    # 1) "Commencement Date: From: dd/mm/yyyy End Date: dd/mm/yyyy"
    m = re.search(
        r"Commencement\s+Date\s*:\s*From\s*:\s*([0-9/]+)\s*End\s*Date\s*:\s*([0-9/]+)",
        full_text,
        flags=re.IGNORECASE,
    )
    if not m:
        # 2) Card layout: Start Date\n<date> ... End Date\n<date>
        m = re.search(
            r"Start\s*Date\s*\n\s*([0-9/]+).*?End\s*Date\s*\n\s*([0-9/]+)",
            full_text,
            flags=re.IGNORECASE | re.DOTALL,
        )
    if not m:
        # 3) "Date of your travel : dd/mm/yyyy to dd/mm/yyyy"
        m = re.search(
            r"Date\s+of\s+your\s+travel\s*[:\-]?\s*([0-9/]+)\s*(?:to|-)\s*([0-9/]+)",
            full_text,
            flags=re.IGNORECASE,
        )

    if m:
        start_date = m.group(1).strip()
        end_date = m.group(2).strip()

    meta["Start Date"] = start_date
    meta["End Date"] = end_date

    # ----- Date of Birth -----
    meta["Date of Birth"] = first_match(
        r"Date\s+of\s+Birth.*?:\s*([0-9/]+)"
    )

    # ----- Passport Number -----
    meta["Passport Number"] = first_match(
        r"Passport\s+Number\s*[:\-]?\s*([A-Z0-9]+)"
    )

    return meta


def build_policy_filename(name: str, assist_no: str) -> str:
    """
    Build filename as 'Insured Full Name_AssistNo', cleaned for filesystem.
    """
    if name and assist_no:
        raw = f"{name}_{assist_no}"
    elif name:
        raw = name
    elif assist_no:
        raw = assist_no
    else:
        return "Policy"

    raw = re.sub(r'[\\/:"*?<>|]+', "", raw)
    raw = re.sub(r"\s+", " ", raw).strip()
    return raw.replace(" ", "_")

# -------------------------
# Invoice helpers
# -------------------------
def sanitize_invoice_name(name: str) -> str:
    """
    Clean up invoice filename: remove illegal characters, squeeze spaces.
    """
    name = name.strip()
    name = re.sub(r'[\\/:"*?<>|]+', "", name)
    name = re.sub(r"\s+", " ", name)
    return name or "Invoice"


def find_invoice_start_pages(pdf_bytes: bytes, trigger_text: str) -> List[int]:
    """
    Return 0-based page indices where a new invoice starts.

    We detect by presence of trigger_text (e.g. 'ADIONA TRAVELS PVT LTD'
    or 'Tax Invoice') in page text.
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
    Extract invoice metadata from pages [start_idx, end_idx]:

      - invoice_no: e.g. 12298282 or INV-10124343
      - total_members: highest Sr. No. in traveller table
      - first_member: full name of Sr. No. 1
      - full_text: concatenated text (for debugging)

    Works for:
      - Old Adiona invoices: 'Sr. No. / Name of Member ...'
      - New Matrix invoices: 'Sr. No. Name of Traveller ...'
    """
    texts: List[str] = []
    for i in range(start_idx, end_idx + 1):
        try:
            t = pdf.pages[i].extract_text() or ""
        except Exception:
            t = ""
        texts.append(t)

    full_text = "\n".join(texts)

    # ---------- Invoice number ----------
    invoice_no = ""
    for pattern in [
        r"Invoice\s*no\.?\s*[:\-]?\s*([A-Za-z0-9\-\/]+)",
        r"Invoice\s*No\.?\s*[:\-]?\s*([A-Za-z0-9\-\/]+)",
    ]:
        m = re.search(pattern, full_text, flags=re.IGNORECASE)
        if m:
            invoice_no = m.group(1).strip()
            break

    # ---------- Limit to table area (before 'Total Amount') ----------
    area = full_text
    idx_total = area.lower().find("total amount")
    if idx_total != -1:
        area = area[:idx_total]

    # ---------- Sr. No. rows for both formats ----------
    # Example old: "1 ROHIT BHALLA 0 110070112795 70012795 118.64 ... "
    # Example new: "01. ANCHAL NARAYAN IC83152 2396.62 431.38 2828.00"
    # We want:
    #   group(1) -> "1" or "01"
    #   group(2) -> "ROHIT BHALLA" / "ANCHAL NARAYAN"
    sr_pattern = re.compile(
        r"^\s*(\d+)\.?\s+([A-Z][A-Za-z]*(?:\s+[A-Z][A-Za-z]*)*)\s+\S+",
        flags=re.MULTILINE
    )

    matches = list(sr_pattern.finditer(area))

    total_members = 0
    first_member = ""

    if matches:
        # Total pax = highest Sr. No.
        try:
            total_members = max(int(m.group(1)) for m in matches)
        except ValueError:
            total_members = 0

        # First pax = smallest Sr. No. (normally 1 / 01)
        first_match = min(matches, key=lambda m: int(m.group(1)))
        first_member_raw = first_match.group(2)
        first_member = re.sub(r"\s+", " ", first_member_raw).strip()

    return invoice_no, total_members, first_member, full_text


# -------------------------
# Home page
# -------------------------
if st.session_state["page"] == "home":
    col1, col2, _ = st.columns([1, 1, 0.3])
    with col1:
        if st.button("🪓 Split PDF", key="split_home", on_click=go_split):
            pass
        st.write("")
        st.markdown(
            "<div class='muted'>Split a combined PDF into individual policy PDFs or invoices.<br>Duplicate names are handled automatically.</div>",
            unsafe_allow_html=True
        )

    with col2:
        if st.button("🔗 Merge PDF", key="merge_home", on_click=go_merge):
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

    split_feature = st.radio(
        "What do you want to split?",
        ["Policies (existing)", "Invoices (Asego Global)"],
        index=0
    )

    # -------------------------
    # POLICY SPLITTER
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

        debug_policies = st.checkbox(
            "Debug policies: show parsed text and metadata",
            value=False
        )

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
                policy_summary_rows: List[Dict[str, object]] = []
                policy_texts: List[str] = []
                policy_meta_list: List[Dict[str, str]] = []

                progress = st.progress(0.0)
                status = st.empty()
                pages_processed = 0

                # Mode 1: Detect by TRAVEL PROTECTION CARD
                if split_mode == "Detect by TRAVEL PROTECTION CARD":
                    current_writer = None
                    current_text_parts: List[str] = []

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

                                is_new_card = "TRAVEL PROTECTION CARD" in text.upper()

                                if is_new_card:
                                    # finalize previous policy
                                    if current_writer is not None and current_text_parts:
                                        full_text = "\n".join(current_text_parts)
                                        meta = extract_policy_metadata_from_text(full_text)

                                        base_name = build_policy_filename(
                                            meta.get("Name", ""),
                                            meta.get("Assist No", "")
                                        )
                                        unique_name = get_unique_name(base_name, name_counter)

                                        buf = io.BytesIO()
                                        current_writer.write(buf)
                                        buf.seek(0)
                                        policies.append((unique_name, buf))

                                        policy_summary_rows.append({
                                            "#": len(policy_summary_rows) + 1,
                                            "Filename": f"{unique_name}.pdf",
                                            "Name": meta.get("Name", ""),
                                            "Assist No": meta.get("Assist No", ""),
                                            "Start Date": meta.get("Start Date", ""),
                                            "End Date": meta.get("End Date", ""),
                                            "Date of Birth": meta.get("Date of Birth", ""),
                                            "Passport Number": meta.get("Passport Number", ""),
                                        })
                                        policy_texts.append(full_text)
                                        policy_meta_list.append(meta)

                                    # start new policy
                                    current_writer = PdfWriter()
                                    current_writer.add_page(reader.pages[i])
                                    current_text_parts = [text]
                                else:
                                    if current_writer is not None:
                                        current_writer.add_page(reader.pages[i])
                                        current_text_parts.append(text)

                            # finalize last policy
                            if current_writer is not None and current_text_parts:
                                full_text = "\n".join(current_text_parts)
                                meta = extract_policy_metadata_from_text(full_text)

                                base_name = build_policy_filename(
                                    meta.get("Name", ""),
                                    meta.get("Assist No", "")
                                )
                                unique_name = get_unique_name(base_name, name_counter)

                                buf = io.BytesIO()
                                current_writer.write(buf)
                                buf.seek(0)
                                policies.append((unique_name, buf))

                                policy_summary_rows.append({
                                    "#": len(policy_summary_rows) + 1,
                                    "Filename": f"{unique_name}.pdf",
                                    "Name": meta.get("Name", ""),
                                    "Assist No": meta.get("Assist No", ""),
                                    "Start Date": meta.get("Start Date", ""),
                                    "End Date": meta.get("End Date", ""),
                                    "Date of Birth": meta.get("Date of Birth", ""),
                                    "Passport Number": meta.get("Passport Number", ""),
                                })
                                policy_texts.append(full_text)
                                policy_meta_list.append(meta)
                    except Exception as e:
                        st.error("Error while parsing policy PDF.")
                        st.exception(e)

                # Mode 2: Fixed number of pages
                else:
                    num_policies = (total_pages + pages_per_policy - 1) // pages_per_policy
                    try:
                        with pdfplumber.open(pdf_bytes_for_plumber) as pdf:
                            for i in range(num_policies):
                                start_idx = i * pages_per_policy
                                end_idx = min(start_idx + pages_per_policy, total_pages)

                                writer = PdfWriter()
                                texts: List[str] = []
                                for j in range(start_idx, end_idx):
                                    writer.add_page(reader.pages[j])
                                    pages_processed += 1
                                    progress.progress(pages_processed / total_pages)
                                    status.text(f"Gathering pages: {pages_processed} / {total_pages}")
                                    try:
                                        t = pdf.pages[j].extract_text() or ""
                                    except Exception:
                                        t = ""
                                    texts.append(t)

                                full_text = "\n".join(texts)
                                if full_text.strip():
                                    meta = extract_policy_metadata_from_text(full_text)
                                else:
                                    meta = {
                                        "Name": "",
                                        "Assist No": "",
                                        "Start Date": "",
                                        "End Date": "",
                                        "Date of Birth": "",
                                        "Passport Number": "",
                                    }

                                base_name = build_policy_filename(
                                    meta.get("Name", ""),
                                    meta.get("Assist No", "")
                                )
                                unique_name = get_unique_name(base_name, name_counter)

                                buf = io.BytesIO()
                                writer.write(buf)
                                buf.seek(0)
                                policies.append((unique_name, buf))

                                policy_summary_rows.append({
                                    "#": len(policy_summary_rows) + 1,
                                    "Filename": f"{unique_name}.pdf",
                                    "Name": meta.get("Name", ""),
                                    "Assist No": meta.get("Assist No", ""),
                                    "Start Date": meta.get("Start Date", ""),
                                    "End Date": meta.get("End Date", ""),
                                    "Date of Birth": meta.get("Date of Birth", ""),
                                    "Passport Number": meta.get("Passport Number", ""),
                                })
                                policy_texts.append(full_text)
                                policy_meta_list.append(meta)
                    except Exception as e:
                        st.error("Error while processing policy PDF.")
                        st.exception(e)

                progress.progress(1.0)
                status.text("Finalizing...")
                runtime = time.time() - start_time

                if policies:
                    st.success(f"✅ Split complete — {len(policies)} policy files created.")
                    st.write(f"⏱ Runtime: {runtime:.2f} seconds")

                    df = pd.DataFrame(policy_summary_rows) if policy_summary_rows else pd.DataFrame(
                        [(i + 1, name) for i, (name, _) in enumerate(policies)],
                        columns=["#", "Filename"]
                    )
                    st.dataframe(df, use_container_width=True)

                    if debug_policies and policy_texts:
                        st.markdown("#### Debug: raw text and parsed metadata (policies)")
                        for row, text_block, meta in zip(policy_summary_rows, policy_texts, policy_meta_list):
                            with st.expander(f"Policy {row['#']} – {row['Filename']}"):
                                st.write("Parsed metadata:", meta)
                                st.text(text_block[:4000])

                    # ZIP download
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
    # INVOICE SPLITTER (Asego Global)
    # -------------------------
    if split_feature == "Invoices (Asego Global)":
        uploaded_file = st.file_uploader(
            "Upload merged invoices PDF",
            type=["pdf"],
            key="invoice_file"
        )

        trigger_text = st.text_input(
            "Text that marks start of each invoice (client name / header)",
            value="",
            placeholder="e.g. ADIONA TRAVELS PVT LTD or Tax Invoice",
            help="Each time this text appears on a new page, a new invoice is assumed to start.",
            key="invoice_trigger"
        )

        debug_mode = st.checkbox(
            "Debug invoices (show raw text per invoice)",
            value=False,
            key="invoice_debug"
        )

        run_invoice = st.button("▶️ Run Invoice Splitter", key="run_invoice")

        if run_invoice:
            if not uploaded_file:
                st.error("Please upload a PDF file first.")
            elif not trigger_text.strip():
                st.error("Please enter a trigger text to detect invoice starts.")
            else:
                start_time = time.time()

                raw_bytes = uploaded_file.getvalue()
                reader = PdfReader(io.BytesIO(raw_bytes))
                total_pages = len(reader.pages)
                file_size = len(raw_bytes)

                st.info(f"File info — Pages: {total_pages} • Size: {human_size(file_size)}")
                st.write("")

                # Detect invoice start pages
                start_pages_0 = find_invoice_start_pages(raw_bytes, trigger_text)
                if not start_pages_0:
                    st.error("No invoice start pages found using the given trigger text.")
                    st.stop()

                ranges = compute_invoice_ranges(start_pages_0, total_pages)

                invoices: List[Tuple[str, bytes]] = []
                summary_rows: List[Dict[str, object]] = []
                texts_per_invoice: List[str] = []
                name_counter: Dict[str, int] = {}

                progress = st.progress(0.0)
                status = st.empty()
                pages_processed = 0

                try:
                    with pdfplumber.open(io.BytesIO(raw_bytes)) as pdf:
                        for idx, (start_idx, end_idx) in enumerate(ranges, start=1):
                            writer = PdfWriter()
                            for j in range(start_idx, end_idx + 1):
                                writer.add_page(reader.pages[j])
                                pages_processed += 1
                                progress.progress(pages_processed / total_pages)
                                status.text(f"Processing pages: {pages_processed} / {total_pages}")

                            invoice_no, total_members, first_member, full_text = extract_invoice_metadata(
                                pdf, start_idx, end_idx
                            )

                            # STRICT requirement:
                            # filename = first pax full name x total pax
                            if first_member and total_members > 0:
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
                            data_out = buf.getvalue()
                            invoices.append((unique_name, data_out))
                            texts_per_invoice.append(full_text)

                            summary_rows.append({
                                "#": idx,
                                "Filename": f"{unique_name}.pdf",
                                "Invoice Number": invoice_no,
                                "Members (pax)": total_members if total_members > 0 else "",
                                "Pages": (end_idx - start_idx + 1),
                            })
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

                    # Debug (optional)
                    if debug_mode:
                        st.markdown("#### Debug: raw text per invoice")
                        for row, text_block in zip(summary_rows, texts_per_invoice):
                            with st.expander(f"Invoice {row['#']} – {row['Filename']}"):
                                st.text(text_block[:4000])

                    # CSV download
                    csv_bytes = df.to_csv(index=False).encode("utf-8")
                    st.download_button(
                        "⬇️ Download CSV summary",
                        data=csv_bytes,
                        file_name="invoice_summary.csv",
                        mime="text/csv",
                        key="invoice_csv"
                    )

                    # ZIP of invoices
                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(zip_buffer, "w") as zf:
                        for name, data_out in invoices:
                            zf.writestr(f"{name}.pdf", data_out)
                    zip_buffer.seek(0)
                    st.download_button(
                        "⬇️ Download ZIP of invoices",
                        data=zip_buffer,
                        file_name=f"invoices_x_{len(invoices)}.zip",
                        mime="application/zip",
                        key="invoice_zip"
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

            for f in uploaded_files:
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
