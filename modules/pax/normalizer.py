import re
import pandas as pd
from datetime import datetime

from modules.pax.config import (
    DEFAULT_VALUES,
    GENDER_KEYWORDS,
    ALLOWED_GENDERS,
    RELATIONSHIP_MAP,
    ADDRESS_REMOVE_WORDS,
)


# ---------------------------------------------------
# Basic Text Cleaning
# ---------------------------------------------------
def clean_text(value):
    if pd.isna(value):
        return ""
    value = str(value).strip()
    value = re.sub(r"[,;]+", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value


# ---------------------------------------------------
# Field Normalizers
# ---------------------------------------------------
def normalize_passport(value):
    return clean_text(value).upper()


def normalize_mobile(value):
    value = clean_text(value)
    digits = re.sub(r"\D", "", value)

    if not digits:
        return DEFAULT_VALUES["mobile_number"]

    if len(digits) == 12 and digits.startswith("91"):
        return digits[2:]

    if len(digits) == 10:
        return digits

    return value


def normalize_phone(value):
    value = clean_text(value)
    digits = re.sub(r"\D", "", value)

    if len(digits) == 12 and digits.startswith("91"):
        return digits[2:]

    if len(digits) == 10:
        return digits

    return value


def normalize_email(value):
    value = clean_text(value).lower()
    if not value:
        return DEFAULT_VALUES["email"]
    return value


def normalize_gender(value):
    value = clean_text(value).upper()
    value = value.strip(".")

    if value in ["M", "MALE", "MR", "MASTER"]:
        return "MALE"

    if value in ["F", "FEMALE", "MRS", "MS", "MISS"]:
        return "FEMALE"

    if value in ALLOWED_GENDERS:
        return value

    for key, gender in GENDER_KEYWORDS.items():
        if key in value:
            return gender

    return ""


def infer_gender_from_title_text(value):
    value = clean_text(value).upper()
    if re.search(r"\b(MR|MASTER)\.?\b", value):
        return "MALE"
    if re.search(r"\b(MRS|MS|MISS)\.?\b", value):
        return "FEMALE"
    return ""


def normalize_nominee(name, relation):
    name = clean_text(name).upper()
    relation = clean_text(relation).upper()

    if not name:
        return DEFAULT_VALUES["nominee"], DEFAULT_VALUES["nominee_relation"]

    if not relation:
        return name, DEFAULT_VALUES["nominee_relation"]

    relation = RELATIONSHIP_MAP.get(relation, relation)

    return name, relation


def normalize_address(
    value,
    city="",
    district="",
    state="",
    country=""
):

    value = clean_text(value).upper()

    for word in ADDRESS_REMOVE_WORDS:
        value = value.replace(word, "")

    value = re.sub(r"[:;,]+", " ", value)

    for item in [
        city,
        district,
        state,
        country
    ]:

        item = str(item).strip().upper()

        if item:

            value = re.sub(
                rf"\b{re.escape(item)}\b",
                "",
                value,
                flags=re.IGNORECASE
            )

    value = re.sub(r"\s+", " ", value)

    return value.strip()

# ---------------------------------------------------
# Date Normalization
# ---------------------------------------------------
def normalize_date(value):
    if pd.isna(value):
        return ""

    if isinstance(value, (pd.Timestamp, datetime)):
        return value.strftime("%d/%m/%Y")

    value = clean_text(value)

    if not value:
        return ""

    value = value.replace(".", "/")

    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d/%m/%y",
        "%d-%m-%Y",
        "%d-%m-%y",
        "%d/%m/%Y %H:%M:%S",
        "%d-%m-%Y",
        "%d %b %Y",
        "%d %B %Y",
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(value, fmt)
            return dt.strftime("%d/%m/%Y")
        except:
            continue

    try:
        dt = datetime.strptime(value, "%d/%m")
        dt = dt.replace(year=datetime.now().year)
        return dt.strftime("%d/%m/%Y")
    except:
        pass

    if "to" in value.lower():
        parts = value.lower().split("to")
        start = clean_text(parts[0])
        end = clean_text(parts[1])

        try:
            current_year = datetime.now().year

            start_dt = datetime.strptime(start, "%d %b")
            start_dt = start_dt.replace(year=current_year)

            end_dt = datetime.strptime(end, "%d %b")

            if end_dt.month < start_dt.month:
                end_dt = end_dt.replace(year=current_year + 1)
            else:
                end_dt = end_dt.replace(year=current_year)

            return (
                start_dt.strftime("%d/%m/%Y")
                + " | "
                + end_dt.strftime("%d/%m/%Y")
            )
        except:
            return value

    return value


# ---------------------------------------------------
# Full Name Merge
# ---------------------------------------------------
def normalize_full_name(row):

    given = clean_text(row.get("given_name", ""))
    surname = clean_text(row.get("surname", ""))
    existing_name = clean_text(row.get("full_name", ""))

    if given and surname:
        name = f"{given} {surname}"
    elif given:
        name = given
    elif existing_name:
        name = existing_name
    else:
        name = surname

    name = name.upper()

    name = re.sub(
        r"\b(MR|MRS|MS|MISS|MASTER|INF)\.?\b",
        "",
        name
    )

    name = re.sub(r"\s+", " ", name).strip()

    return name

# ---------------------------------------------------
# DataFrame Normalization
# ---------------------------------------------------
def normalize_dataframe(df):
    df = df.copy()

    def text_series(column):
        if column in df.columns:
            return df[column].fillna("").astype(str)
        return pd.Series([""] * len(df), index=df.index)

    # -----------------------------
    # Full Name + Gender Extraction
    # -----------------------------
    if (
        "given_name" in df.columns
        or "surname" in df.columns
        or "full_name" in df.columns
    ):
        if "gender" not in df.columns:
            df["gender"] = ""

        title_source = (
            text_series("full_name")
            + " "
            + text_series("given_name")
            + " "
            + text_series("surname")
        )
        current_gender = df["gender"].fillna("").astype(str).str.strip()
        inferred_gender = title_source.apply(infer_gender_from_title_text)
        df.loc[
            (current_gender == "")
            & (inferred_gender != ""),
            "gender",
        ] = inferred_gender

        df["full_name"] = df.apply(
            normalize_full_name,
            axis=1
        )

    # -----------------------------
    # Passport
    # -----------------------------
    if "passport_number" in df.columns:
        df["passport_number"] = df["passport_number"].apply(
            normalize_passport
        )

    # -----------------------------
    # Mobile
    # -----------------------------
    if "mobile_number" in df.columns:
        df["mobile_number"] = df["mobile_number"].apply(
            normalize_mobile
        )

    if "phone_number" in df.columns:
        df["phone_number"] = df["phone_number"].apply(
            normalize_phone
        )

    if (
        "mobile_number" in df.columns
        and "phone_number" in df.columns
    ):
        df.loc[
            (
                df["mobile_number"]
                == DEFAULT_VALUES["mobile_number"]
            )
            & (df["phone_number"] != ""),
            "mobile_number",
        ] = df["phone_number"]

    # -----------------------------
    # Email
    # -----------------------------
    if "email" in df.columns:
        df["email"] = df["email"].apply(
            normalize_email
        )

    # -----------------------------
    # Gender
    # -----------------------------
    if "gender" in df.columns:
        df["gender"] = df["gender"].apply(
            normalize_gender
        )

    # -----------------------------
    # Address
    # -----------------------------
    if "address_line_1" in df.columns:
        df["address_line_1"] = df["address_line_1"].apply(
            normalize_address
        )

    # -----------------------------
    # Dates
    # -----------------------------
    if "start_date" in df.columns:
        df["start_date"] = df["start_date"].apply(
            normalize_date
        )

    if "end_date" in df.columns:
        df["end_date"] = df["end_date"].apply(
            normalize_date
        )

    if "dob" in df.columns:
        df["dob"] = df["dob"].apply(
            normalize_date
        )

    # -----------------------------
    # Nominee
    # -----------------------------
    if (
        "nominee" in df.columns
        and "nominee_relation" in df.columns
    ):
        df["nominee"], df["nominee_relation"] = zip(
            *df.apply(
                lambda row: normalize_nominee(
                    row.get("nominee", ""),
                    row.get("nominee_relation", "")
                ),
                axis=1,
            )
        )

    # -----------------------------
    # Remove PIN from Address
    # -----------------------------
    if (
        "address_line_1" in df.columns
        and "pincode" in df.columns
    ):
        df["address_line_1"] = df.apply(
            remove_pincode_from_address,
            axis=1
        )

    

    return df

def remove_pincode_from_address(row):

    address = str(
        row.get("address_line_1", "")
    ).upper().strip()

    pincode = str(
        row.get("pincode", "")
    ).strip()

    city = str(
        row.get("city", "")
    ).upper().strip()

    district = str(
        row.get("district", "")
    ).upper().strip()

    state = str(
        row.get("state", "")
    ).upper().strip()

    country = str(
        row.get("country", "")
    ).upper().strip()

    if pincode:
        address = re.sub(
            rf"\b{re.escape(pincode)}\b",
            "",
            address
        )

    for value in {
        city,
        district,
        state,
        country,
        "INDIA",
        "INDIAN"
    }:

        if value:

            address = re.sub(
                rf"\b{re.escape(value)}\b",
                "",
                address,
                flags=re.IGNORECASE
            )

    address = re.sub(
        r"[:;,/\-]+",
        " ",
        address
    )

    address = re.sub(
        r"\s+",
        " ",
        address
    )

    return address.strip()

import re

