import pandas as pd
from modules.pax.config import OLD_PORTAL_COLUMNS, NEW_PORTAL_COLUMNS


# ---------------------------------------------------
# OLD PORTAL EXPORT
# ---------------------------------------------------
def export_old_portal(df):
    df = df.copy()

    # Ensure required columns exist
    for col in OLD_PORTAL_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    export_df = df[OLD_PORTAL_COLUMNS]

    export_df = export_df.rename(columns={
        "start_date": "Commence Date",
        "end_date": "End Date",
        "full_name": "Name",
        "passport_number": "Passport Number",
        "dob": "Dob",
        "address_line_1": "Address",
        "address_line_2": "Address 2",
        "pincode": "Pincode",
        "city": "City",
        "district": "District",
        "state": "State",
        "country": "Country",
        "phone_number": "Phone Number",
        "mobile_number": "Mobile Number",
        "nominee": "Nominee",
        "nominee_relation": "Relation",
        "past_illness": "Past Illness",
        "email": "Emailaddess",
        "cr_reference": "CR",
        "gst_number": "Gstno",
    })

    # Global Portal defaults

    export_df["Address 2"] = (
        export_df["Address 2"]
        .fillna("")
        .astype(str)
        .replace("", ".")
    )

    export_df.loc[
        (
            export_df["Phone Number"]
            .fillna("")
            .astype(str)
            .str.strip()
            == ""
        ),
        "Phone Number"
    ] = export_df["Mobile Number"]

    return export_df


# ---------------------------------------------------
# NEW PORTAL EXPORT
# ---------------------------------------------------
def export_new_portal(df):
    df = df.copy()

    for col in NEW_PORTAL_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    export_df = df[NEW_PORTAL_COLUMNS]

    export_df = export_df.rename(columns={
        "start_date": "Start Date(DD/MM/YYYY)*",
        "end_date": "End Date(DD/MM/YYYY)*",
        "passport_number": "Passport Number*",
        "full_name": "Name*",
        "gender": "Gender*",
        "dob": "Date of Birth(DD/MM/YYYY)*",
        "nominee": "Nominee*",
        "nominee_relation": "Relationship*",
        "address_line_1": "Address*",
        "pincode": "Pincode*",
        "city": "City*",
        "district": "District*",
        "state": "State*",
        "country": "Country*",
        "mobile_number": "Mobile Number (Without Code)*",
        "email": "Email Address*",
        "remarks": "Remarks",
        "cr_reference": "CR Reference Number",
        "past_illness": "Past Illness",
        "emergency_contact_name": "Emergency Contact Person",
        "emergency_contact_number": "Emergency Contact Number",
        "emergency_email": "Emergency Email ID",
        "gst_number": "GST Number",
        "gst_state": "GST State",
    })

    # NEW portal rule: no dot placeholders
    export_df["City*"] = export_df["City*"].replace(".", "")
    export_df["District*"] = export_df["District*"].replace(".", "")

    return export_df
