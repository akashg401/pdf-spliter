from modules.pax.reader import read_excel_file
from modules.pax.header_mapper import map_headers
from modules.pax.normalizer import normalize_address, normalize_dataframe, normalize_date
from modules.pax.validators import generate_error_report
from modules.pax.global_defaults import apply_global_defaults
from modules.pax.exporter import export_old_portal, export_new_portal

import pandas as pd
import re


INDIAN_STATE_NAMES = {
    "ANDHRA PRADESH",
    "ARUNACHAL PRADESH",
    "ASSAM",
    "BIHAR",
    "CHHATTISGARH",
    "GOA",
    "GUJARAT",
    "HARYANA",
    "HIMACHAL PRADESH",
    "JHARKHAND",
    "KARNATAKA",
    "KERALA",
    "MADHYA PRADESH",
    "MAHARASHTRA",
    "MANIPUR",
    "MEGHALAYA",
    "MIZORAM",
    "NAGALAND",
    "ODISHA",
    "ORISSA",
    "PUNJAB",
    "RAJASTHAN",
    "SIKKIM",
    "TAMIL NADU",
    "TELANGANA",
    "TRIPURA",
    "UTTAR PRADESH",
    "UTTARAKHAND",
    "WEST BENGAL",
    "DELHI",
    "JAMMU AND KASHMIR",
    "LADAKH",
    "PUDUCHERRY",
    "CHANDIGARH",
    "ANDAMAN AND NICOBAR ISLANDS",
    "DADRA AND NAGAR HAVELI AND DAMAN AND DIU",
    "LAKSHADWEEP",
}


# ---------------------------------------------------
# Helper: Extract PIN from address
# ---------------------------------------------------
def extract_pincode_from_address(row):
    pincode = str(row.get("pincode", "")).strip()
    address = str(row.get("address_line_1", "")).strip()

    normalized_pin = normalize_pincode(pincode)
    if normalized_pin:
        return normalized_pin

    match = re.search(r"\b\d{6}\b", address)
    if match:
        return match.group()

    return ""


def normalize_pincode(value):
    value = str(value or "").strip()
    if not value:
        return ""

    digits = re.sub(r"\D", "", value)
    if len(digits) >= 6:
        return digits[:6]

    return ""


def clean_address_after_lookup(row):
    address = normalize_address(row.get("address_line_1", ""))
    pincode = normalize_pincode(row.get("pincode", ""))

    if pincode:
        address = re.sub(rf"\b{re.escape(pincode)}\b", "", address)

    values_to_remove = {
        str(row.get("state", "") or "").strip().upper(),
        str(row.get("country", "") or "").strip().upper(),
        "INDIA",
        "INDIAN",
    }
    values_to_remove.update(INDIAN_STATE_NAMES)

    for value in sorted(values_to_remove, key=len, reverse=True):
        value = str(value or "").strip().upper()
        if value:
            address = re.sub(rf"\b{re.escape(value)}\b", "", address)

    address = re.sub(r"\s+", " ", address)
    return address.strip()


def normalize_dates_after_defaults(df):
    df = df.copy()
    for col in ["start_date", "end_date", "dob"]:
        if col in df.columns:
            df[col] = df[col].apply(normalize_date)
    return df


# ---------------------------------------------------
# Helper: Split date range (start | end)
# ---------------------------------------------------
def split_date_range(df):
    df = df.copy()

    for col in ["start_date", "end_date"]:
        if col not in df.columns:
            df[col] = ""

    def split_row(row):
        val = str(row.get("start_date", "")).strip()

        if "|" in val:
            parts = [p.strip() for p in val.split("|")]
            if len(parts) == 2:
                row["start_date"] = parts[0]
                row["end_date"] = parts[1]

        return row

    return df.apply(split_row, axis=1)


# ---------------------------------------------------
# Helper: Gender inference fallback
# ---------------------------------------------------
def infer_gender_from_name(row):
    gender = str(row.get("gender", "")).upper().strip()
    name = str(row.get("full_name", "")).upper().strip()

    # If already valid gender, keep it
    if gender in ["MALE", "FEMALE"]:
        return gender

    # Title-based inference
    if " MR" in name or name.endswith(" MR"):
        return "MALE"

    if " MRS" in name or " MS" in name:
        return "FEMALE"

    # Infant cases
    if " INF" in name and " F" in name:
        return "FEMALE"

    if " INF" in name and " M" in name:
        return "MALE"

    return ""


# ---------------------------------------------------
# MAIN PIPELINE CONTROLLER
# ---------------------------------------------------
def process_file(
    file_path,
    pin_master_path=None,
    portal_type="new",
    global_start_date=None,
    global_end_date=None,
    global_address=None,
    global_cr=None,
    include_source_sheet=False,
):
    """
    Main orchestration function.

    Returns:
        final_export_df,
        error_report_df
    """

    all_processed_rows = []
    all_errors = []

    sheets = read_excel_file(file_path)

    # Load PIN master if provided
    pin_lookup = None
    if pin_master_path:
        from modules.pax.lookup import PinLookup
        pin_lookup = PinLookup(pin_master_path)

    # Process each sheet
    for sheet in sheets:

        # 1. Header mapping
        mapped = map_headers(sheet["sheet_name"], sheet["data"])

        # 2. Normalize
        normalized = normalize_dataframe(mapped)

        # 3. Apply global defaults
        normalized = apply_global_defaults(
            normalized,
            global_start_date=global_start_date,
            global_end_date=global_end_date,
            global_address=global_address,
            global_cr=global_cr,
        )

        normalized = normalize_dates_after_defaults(normalized)

        # 4. Split date ranges
        normalized = split_date_range(normalized)

        # 5. Extract PIN from address
        normalized["pincode"] = normalized.apply(
            extract_pincode_from_address,
            axis=1
        )

        # 6. PIN → LOCATION Lookup
        if pin_lookup:
            def apply_location_lookup(row):
                location = pin_lookup.get_location(
                    row.get("pincode", "")
                )

                if not row.get("city"):
                    row["city"] = location.get("city", "")

                if not row.get("district"):
                    row["district"] = location.get("district", "")

                if not row.get("state"):
                    row["state"] = location.get("state", "")

                if not row.get("country"):
                    row["country"] = location.get("country", "")

                return row

            normalized = normalized.apply(
                apply_location_lookup,
                axis=1
            )

        # 7. Gender inference fallback
        normalized["gender"] = normalized.apply(
            infer_gender_from_name,
            axis=1
        )

        # 8. Validation
        errors = generate_error_report(normalized)

        all_processed_rows.append(normalized)
        all_errors.append(errors)

    # If no data
    if not all_processed_rows:
        return pd.DataFrame(), pd.DataFrame()

    combined_df = pd.concat(all_processed_rows, ignore_index=True)

    combined_errors = (
        pd.concat(all_errors, ignore_index=True)
        if all_errors else pd.DataFrame()
    )

    # 9. Export formatting
    if portal_type.lower() == "old":
        final_export = export_old_portal(combined_df)
    else:
        final_export = export_new_portal(combined_df)

    if include_source_sheet and "source_sheet_name" in combined_df.columns:
        final_export["SOURCE SHEET NAME"] = combined_df["source_sheet_name"].values

    return final_export, combined_errors
