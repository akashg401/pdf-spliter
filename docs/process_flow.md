# PDF Tools - Business Process Flow

## Definitions

### Hub

A Hub is a client-defined passenger group.

Examples:

* Mumbai
* Mumbai 1
* Mumbai 2
* Delhi
* Delhi 1
* Pune

Important Rules:

* Hub names come from client data.
* Hub names must never be modified by the system.
* Hub names are independent of portal batch limits.
* Hub names determine the final policy download folder structure.

Example:

Mumbai 1 = 40 Pax

Mumbai 2 = 70 Pax

Even though total passengers are only 110 and can be issued together, downloaded policies must be saved separately:

Mumbai 1/

* 40 PDFs

Mumbai 2/

* 70 PDFs

---

### Batch

A Batch is an operational grouping created by our system.

Purpose:

Portal allows approximately 150 passengers per upload.

Example:

Total formatted data = 420 passengers

System creates:

Batch 1 = 150 passengers

Batch 2 = 150 passengers

Batch 3 = 120 passengers

Important Rules:

* Batch is temporary.
* Batch exists only for portal upload.
* Batch has no relationship with Hub.
* Batch information is not required after policy issuance.

---

## Current Workflow

### Step 1 - Raw Data Received

Input:

Client raw data

Typical information:

* Traveller Name
* Passport Number
* Travel Dates
* Address
* Hub Name (if provided)

---

### Step 2 - CSV Formatter

Process:

* Header Mapping
* Data Normalization
* Name Cleaning
* Gender Inference
* Mobile Normalization
* Address Cleaning
* PIN Lookup
* Validation

Output:

Formatted_Output.xlsx

Error_Report.xlsx

Hub column preserved if available.

---

### Step 3 - Batch Splitter (Optional)

Purpose:

Prepare files for portal upload.

User Options:

* Keep Full Data
* Split Into Batches

If enabled:

Formatted_Output.xlsx

Batch_1.xlsx

Batch_2.xlsx

Batch_3.xlsx

Batch_n.xlsx

Default batch size:

150 passengers

---

### Step 4 - Portal Issuance

User uploads batches to portal.

Policies are issued.

User downloads issued policy reports.

Multiple reports may exist.

Example:

Policy_Report_1.xlsx

Policy_Report_2.xlsx

Policy_Report_3.xlsx

---

### Step 5 - Policy Report Merge

System merges all policy reports.

Output:

Merged_Policy_Report.xlsx

---

### Step 6 - Hub Recovery

Input:

Formatted_Output.xlsx

Merged_Policy_Report.xlsx

Match Key:

Passport Number

Process:

Recover Hub Name from original formatted file.

Output:

Hub_Mapped_Policies.xlsx

Columns:

* Passport Number
* Traveller Name
* Policy Number
* Policy Path
* Hub Name

---

### Step 7 - Hub Summary

Display:

Hub Name | Policy Count

Example:

Mumbai | 220

Mumbai 1 | 40

Mumbai 2 | 70

Delhi | 120

Pune | 50

Show:

* Total Policies
* Matched Policies
* Unmatched Policies

---

### Step 8 - Future Hub Download Module

Input:

Hub_Mapped_Policies.xlsx

Output:

Final ZIP

Mumbai/

Mumbai 1/

Mumbai 2/

Delhi/

Pune/

Each folder contains only the PDFs belonging to that Hub.

---

## Future Roadmap

### Hub Manager

* Hub Detection
* Batch Splitter
* Policy Report Merge
* Passport Lookup
* Hub Recovery
* Hub Summary
* Hub-wise Downloads

### Performance Improvements

* Parallel PDF Downloads
* Faster ZIP Creation

### Desktop Version

* Windows EXE
* No Streamlit Dependency
* No Browser Required
