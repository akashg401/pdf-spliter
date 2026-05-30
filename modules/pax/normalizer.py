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
    value = value.replace("+91", "")
    value = re.sub(r"\D", "", value)

    if not value:
        return DEFAULT_VALUES["mobile_number"]

    return value


def normalize_phone(value):
    value = clean_text(value)
    value = value.replace("+91", "")
    return re.sub(r"\D", "", value)


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


def normalize_nominee(name, relation):
    name = clean_text(name).upper()
    relation = clean_text(relation).upper()

    if not name:
        return DEFAULT_VALUES["nominee"], DEFAULT_VALUES["nominee_relation"]

    if not relation:
        return name, DEFAULT_VALUES["nominee_relation"]

    relation = RELATIONSHIP_MAP.get(relation, relation)

    return name, relation


def normalize_address(value):
    value = clean_text(value).upper()

    for word in ADDRESS_REMOVE_WORDS:
        value = value.replace(word, "")

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

    name = re.sub(r"\b(MR|MRS|MS|MISS|MASTER|INF)\.?\b", "", name)

    name = re.sub(r"\s+", " ", name).strip()

    return name


# ---------------------------------------------------
# DataFrame Normalization
# ---------------------------------------------------
def normalize_dataframe(df):
    df = df.copy()

    if "given_name" in df.columns or "surname" in df.columns or "full_name" in df.columns:
        df["full_name"] = df.apply(normalize_full_name, axis=1)

    if "passport_number" in df.columns:
        df["passport_number"] = df["passport_number"].apply(normalize_passport)

    if "mobile_number" in df.columns:
        df["mobile_number"] = df["mobile_number"].apply(normalize_mobile)

    if "phone_number" in df.columns:
        df["phone_number"] = df["phone_number"].apply(normalize_phone)

    if "mobile_number" in df.columns and "phone_number" in df.columns:
        df.loc[
            (df["mobile_number"] == DEFAULT_VALUES["mobile_number"])
            & (df["phone_number"] != ""),
            "mobile_number",
        ] = df["phone_number"]

    if "email" in df.columns:
        df["email"] = df["email"].apply(normalize_email)

    if "gender" in df.columns:
        df["gender"] = df["gender"].apply(normalize_gender)

    if "address_line_1" in df.columns:
        df["address_line_1"] = df["address_line_1"].apply(normalize_address)

    if "start_date" in df.columns:
        df["start_date"] = df["start_date"].apply(normalize_date)

    if "end_date" in df.columns:
        df["end_date"] = df["end_date"].apply(normalize_date)

    if "dob" in df.columns:
        df["dob"] = df["dob"].apply(normalize_date)

    if "nominee" in df.columns and "nominee_relation" in df.columns:
        df["nominee"], df["nominee_relation"] = zip(
            *df.apply(
                lambda row: normalize_nominee(
                    row.get("nominee", ""),
                    row.get("nominee_relation", "")
                ),
                axis=1,
            )
        )

    if "address_line_1" in df.columns and "pincode" in df.columns:
        df["address_line_1"] = df.apply(remove_pincode_from_address, axis=1)

    return df

def remove_pincode_from_address(row):

    address = str(row.get("address_line_1", "")).strip()
    pincode = str(row.get("pincode", "")).strip()

    if pincode:
        address = address.replace(pincode, "")

    address = " ".join(address.split())

    return address