
import pandas as pd


def read_excel_file(file_path):
    """
    Reads an Excel file and returns a list of dictionaries:
    [
        {
            "sheet_name": "Sheet1",
            "data": dataframe
        },
        ...
    ]
    """

    sheets_data = []

    # Load Excel file
    excel_file = pd.ExcelFile(file_path)

    for sheet_name in excel_file.sheet_names:
        df = excel_file.parse(sheet_name)

        # Drop completely empty rows
        df = df.dropna(how="all")

        # Drop completely empty columns
        df = df.dropna(axis=1, how="all")

        # Skip if sheet becomes empty
        if df.empty:
            continue

        # Reset index
        df = df.reset_index(drop=True)

        sheets_data.append({
            "sheet_name": sheet_name,
            "data": df
        })

    return sheets_data
