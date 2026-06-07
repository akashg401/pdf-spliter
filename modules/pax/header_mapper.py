import pandas as pd
from modules.pax.config import CANONICAL_COLUMNS, HEADER_MAPPING


def normalize_header(header):
    if pd.isna(header):
        return ""
    value = str(header).strip().lower()
    value = value.replace("*", "")
    value = value.replace(".", " ")
    value = value.replace("_", " ")
    value = value.replace("-", " ")
    value = " ".join(value.split())
    return value


NORMALIZED_HEADER_MAPPING = {
    normalize_header(key): value
    for key, value in HEADER_MAPPING.items()
}


SAFE_CONTAINS_KEYS = [
    key
    for key in sorted(NORMALIZED_HEADER_MAPPING.keys(), key=len, reverse=True)
    if key not in {"name", "passport", "pin", "state", "country", "contact", "phone", "email"}
]


def match_header(header):
    normalized = normalize_header(header)
    if not normalized:
        return None

    if normalized in NORMALIZED_HEADER_MAPPING:
        return NORMALIZED_HEADER_MAPPING[normalized]

    for key in SAFE_CONTAINS_KEYS:
        if key and key in normalized:
            return NORMALIZED_HEADER_MAPPING[key]

    return None


def headers_look_valid(df):
    """
    Check if current dataframe columns already look like real headers.
    """
    score = 0

    for col in df.columns:
        if match_header(col):
            score += 1

    return score >= 2  # threshold


def map_headers(sheet_name, df):
    """
    Converts raw sheet dataframe into canonical schema dataframe
    """

    # If columns are integers or invalid, then detect header row
    if not headers_look_valid(df):

        # Try detecting header row inside data
        for i in range(min(10, len(df))):
            row = df.iloc[i]
            score = 0

            for value in row:
                if match_header(value):
                    score += 1

            if score >= 2:
                df.columns = df.iloc[i]
                df = df[(i + 1):].reset_index(drop=True)
                break

    mapped_df = pd.DataFrame()

    for col in df.columns:
        matched_column = match_header(col)

        if matched_column:
            if matched_column in mapped_df.columns:
                mapped_df[matched_column] = mapped_df[matched_column].where(
                    mapped_df[matched_column].notna()
                    & (mapped_df[matched_column].astype(str).str.strip() != ""),
                    df[col],
                )
            else:
                mapped_df[matched_column] = df[col]

    # Ensure all canonical columns exist
    for col in CANONICAL_COLUMNS:
        if col not in mapped_df.columns:
            mapped_df[col] = ""

    # Add source sheet name
    mapped_df["source_sheet_name"] = sheet_name

    return mapped_df
