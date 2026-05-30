import re
from datetime import datetime

import pandas as pd


DATE_FORMAT = "%d/%m/%Y"
PASSPORT_PATTERN = re.compile(r"^(?:[A-Z][0-9]{7}|[A-Z]{2}[0-9]{6}|[A-Z]{2}[0-9]{8})$")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _parse_date(value):
    value = str(value or "").strip()
    if not value:
        return None, None

    try:
        return datetime.strptime(value, DATE_FORMAT), None
    except ValueError:
        return None, f"Invalid date format: {value}"


def validate_row(row, index):
    errors = []

    passport = str(row.get("passport_number", "") or "").strip().upper()
    if not passport:
        errors.append(("passport_number", "Missing passport number"))
    elif not PASSPORT_PATTERN.match(passport):
        errors.append(("passport_number", f"Invalid passport number: {passport}"))

    required_fields = {
        "start_date": "Missing start date",
        "end_date": "Missing end date",
        "full_name": "Missing name",
        "gender": "Missing gender",
        "dob": "Missing DOB",
        "address_line_1": "Missing address",
        "pincode": "Missing pincode",
        "city": "Missing city",
        "district": "Missing district",
        "state": "Missing state",
        "country": "Missing country",
    }

    for field, message in required_fields.items():
        if not str(row.get(field, "") or "").strip():
            errors.append((field, message))

    if row.get("mobile_number") and not re.fullmatch(r"\d{10}", str(row.get("mobile_number"))):
        errors.append(("mobile_number", f"Invalid mobile number: {row.get('mobile_number')}"))

    if row.get("email") and not EMAIL_PATTERN.match(str(row.get("email"))):
        errors.append(("email", f"Invalid email address: {row.get('email')}"))

    if row.get("phone_number") and not re.fullmatch(r"\d{10}", str(row.get("phone_number"))):
        errors.append(("phone_number", f"Invalid phone number: {row.get('phone_number')}"))

    if row.get("gender") and row.get("gender") not in ("MALE", "FEMALE"):
        errors.append(("gender", "Missing or invalid gender"))

    parsed_dates = {}
    for field in ("start_date", "end_date", "dob"):
        parsed, error = _parse_date(row.get(field, ""))
        parsed_dates[field] = parsed
        if error:
            errors.append((field, error))

    start = parsed_dates["start_date"]
    end = parsed_dates["end_date"]
    dob = parsed_dates["dob"]

    if start and end and end < start:
        errors.append(("end_date", "End date earlier than start date"))

    if dob and dob > datetime.now():
        errors.append(("dob", "DOB is in future"))

    return errors


def generate_error_report(df):
    error_rows = []

    for index, row in df.iterrows():
        for field, message in validate_row(row, index):
            error_rows.append({
                "row_index": index + 1,
                "field": field,
                "issue": message,
                "value": row.get(field, ""),
                "source_sheet": row.get("source_sheet_name", ""),
            })

    return pd.DataFrame(error_rows)
