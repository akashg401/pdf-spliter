import pandas as pd
from modules.pax.config import CANONICAL_COLUMNS, HEADER_MAPPING


def normalize_header(header):
    if pd.isna(header):
        return ""
    return str(header).strip().lower()


def headers_look_valid(df):
    """
    Check if current dataframe columns already look like real headers.
    """
    score = 0

    for col in df.columns:
        col_str = normalize_header(col)
        for key in HEADER_MAPPING.keys():
            if key in col_str:
                score += 1
                break

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
                value_str = normalize_header(value)
                for key in HEADER_MAPPING.keys():
                    if key in value_str:
                        score += 1
                        break

            if score >= 2:
                df.columns = df.iloc[i]
                df = df[(i + 1):].reset_index(drop=True)
                break

    mapped_df = pd.DataFrame()

    for col in df.columns:
        normalized = normalize_header(col)

        matched_column = None

        # Match longer keys first
        for key in sorted(HEADER_MAPPING.keys(), key=len, reverse=True):
            if key in normalized:
                matched_column = HEADER_MAPPING[key]
                break


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
