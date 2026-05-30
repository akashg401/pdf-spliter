from modules.pax.pipeline import process_file

file_path = r"C:\Users\Dell\Downloads\Copy of INSURANCE.xlsx"
pin_master_path = r"C:\Users\Dell\pdf-spliter\pin_master.xlsx"

final_export, error_report = process_file(
    file_path,
    portal_type="new",   # <-- THIS is new portal
    pin_master_path=pin_master_path,
)

print("\n===== FINAL EXPORT (NEW PORTAL) =====")
print(final_export.head())

print("\n===== ERROR REPORT =====")
print(error_report.head(10))

print("\n===== PIN & STATE CHECK =====")
print(final_export[["Pincode*", "State*"]].head())

print("\n===== GENDER CHECK =====")
print(final_export[["Name*", "Gender*"]].head())

print("\n===== DATE CHECK =====")
print(final_export[["Start Date(DD/MM/YYYY)*", "End Date(DD/MM/YYYY)*"]].head())

print(
    final_export[
        [
            "Pincode*",
            "City*",
            "District*",
            "State*",
            "Country*"
        ]
    ].head()
)
print(normalized[["address_line_1", "pincode"]].head())

