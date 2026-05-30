import pandas as pd
import re


class PinLookup:

    def __init__(self, pin_master_path):
        self.pin_map = self._load_pin_master(pin_master_path)

    def _load_pin_master(self, path):

        df = pd.read_excel(path)

        # Normalize column names
        df.columns = [
            str(col).strip().lower()
            for col in df.columns
        ]

        # Expected columns from your master
        required_cols = {
            "pincode": "pincode",
            "statename": "state",
            "districtsname": "district",
            "city": "city",
            "country": "country",
        }

        # Validate required columns
        for source_col in required_cols.keys():
            if source_col not in df.columns:
                raise ValueError(
                    f"Missing column in PIN master: {source_col}"
                )

        pin_dict = {}

        for _, row in df.iterrows():

            pin = self._normalize_pin(
                row["pincode"]
            )

            if not pin:
                continue

            pin_dict[pin] = {
                "city": (
    ""
    if pd.isna(row["city"])
    else str(row["city"]).strip().upper()
),

"district": (
    ""
    if pd.isna(row["districtsname"])
    else str(row["districtsname"]).strip().upper()
),

"state": (
    ""
    if pd.isna(row["statename"])
    else str(row["statename"]).strip().upper()
),

"country": (
    "INDIA"
    if pd.isna(row["country"])
    else str(row["country"]).strip().upper()
),
            }

        return pin_dict

    # ---------------------------------------------------
    # Main Lookup
    # ---------------------------------------------------
    def get_location(self, pincode):

        pincode = self._normalize_pin(pincode)

        if not pincode:
            return {}

        return self.pin_map.get(
            pincode,
            {
                "city": "",
                "district": "",
                "state": "",
                "country": "",
            }
        )

    # ---------------------------------------------------
    # Normalize PIN
    # ---------------------------------------------------
    @staticmethod
    def _normalize_pin(value):

        value = str(value or "").strip()

        digits = re.sub(r"\D", "", value)

        if len(digits) >= 6:
            return digits[:6]

        return ""