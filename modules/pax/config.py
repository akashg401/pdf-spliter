
# Canonical internal schema
CANONICAL_COLUMNS = [
    "source_sheet_name",
    "start_date",
    "end_date",
    "passport_number",
    "full_name",
    "gender",
    "dob",
    "nominee",
    "nominee_relation",
    "address_line_1",
    "address_line_2",
    "pincode",
    "city",
    "district",
    "state",
    "country",
    "mobile_number",
    "phone_number",
    "email",
    "remarks",
    "cr_reference",
    "past_illness",
    "emergency_contact_name",
    "emergency_contact_number",
    "emergency_email",
    "gst_number",
    "gst_state",
]


DEFAULT_VALUES = {
    "nominee": "LEGAL HEIR",
    "nominee_relation": "LEGAL HEIR",
    "mobile_number": "9999999999",
    "email": "na@na.com",
}

GENDER_KEYWORDS = {
    "MR": "MALE",
    "MRS": "FEMALE",
    "MS": "FEMALE",
    "MISS": "FEMALE",
    "MASTER": "MALE",
    "INF": "FEMALE",  # if INF-F, we handle in normalizer
}
ALLOWED_GENDERS = ["MALE", "FEMALE"]


RELATIONSHIP_MAP = {
    "SON": "SON",
    "S/O": "SON",
    "DAUGHTER": "DAUGHTER",
    "D/O": "DAUGHTER",
    "WIFE": "SPOUSE",
    "HUSBAND": "SPOUSE",
    "SPOUSE": "SPOUSE",
}

ADDRESS_REMOVE_WORDS = [
    "PIN",
    "CODE",
    "STATE",
    "COUNTRY",
    "DIST",
    "DISTRICT",
    "CITY",
]

HEADER_MAPPING = {
    "full name": "full_name",
    "first name": "given_name",
    "last name": "surname",
    "given name": "given_name",
    "surname": "surname",
    "source sheet name": None,
    "name": "full_name",

    "dot": "start_date",
    "dep date": "start_date",
    "departure date": "start_date",
    "onward date": "start_date",
    "going date": "start_date",
    "start date": "start_date",
    "commence date": "start_date",
    "commencement date": "start_date",
    "date of travel": "start_date",
    "dor": "end_date",
    "arr. date": "end_date",
    "arr date": "end_date",
    "arrival date": "end_date",
    "end date": "end_date",
    "return date": "end_date",

    "dob": "dob",
    "d.o.b.": "dob",
    "d.o.b": "dob",
    "date of birth": "dob",

    "ppt no": "passport_number",
    "ppt number": "passport_number",
    "passport number": "passport_number",
    "passport no": "passport_number",
    "passport": "passport_number",

    "title": "gender",
    "tital": "gender",
    "mr.": "gender",
    "mrs.": "gender",
    "ms.": "gender",
    "gender": "gender",
    "nominee": "nominee",
    "relation": "nominee_relation",
    "relationship": "nominee_relation",

    "address": "address_line_1",
    "address 1": "address_line_1",
    "address 2": "address_line_2",

    "pincode": "pincode",
    "pin": "pincode",

    "city": "city",
    "district": "district",
    "state": "state",
    "country visiting": None,
    "visiting country": None,
    "destination country": None,
    "country": "country",

    "emergency contact person": "emergency_contact_name",
    "emergency contact name": "emergency_contact_name",
    "emergency contact number": "emergency_contact_number",
    "emergency email id": "emergency_email",
    "emergency email": "emergency_email",

    "contact no": "mobile_number",
    "contact number": "mobile_number",
    "contact": "mobile_number",
    "mobile number": "mobile_number",
    "mobile no": "mobile_number",
    "mobile": "mobile_number",
    "phone number": "phone_number",
    "phone no": "phone_number",
    "phone": "phone_number",

    "email": "email",
    "email address": "email",
    "email id": "email",
    "mail id": "email",

    "cr reference": "cr_reference",
    "cr": "cr_reference",

    "past illness": "past_illness",
    "gst number": "gst_number",
    "gst state": "gst_state",
}



OLD_PORTAL_COLUMNS = [
    "start_date",
    "end_date",
    "full_name",
    "passport_number",
    "dob",
    "address_line_1",
    "address_line_2",
    "pincode",
    "city",
    "district",
    "state",
    "country",
    "phone_number",
    "mobile_number",
    "nominee",
    "nominee_relation",
    "past_illness",
    "email",
    "cr_reference",
    "gst_number",
]

NEW_PORTAL_COLUMNS = [
    "start_date",
    "end_date",
    "passport_number",
    "full_name",
    "gender",
    "dob",
    "nominee",
    "nominee_relation",
    "address_line_1",
    "pincode",
    "city",
    "district",
    "state",
    "country",
    "mobile_number",
    "email",
    "remarks",
    "cr_reference",
    "past_illness",
    "emergency_contact_name",
    "emergency_contact_number",
    "emergency_email",
    "gst_number",
    "gst_state",
]
