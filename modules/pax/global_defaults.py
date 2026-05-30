
def apply_global_defaults(
    df,
    global_start_date=None,
    global_end_date=None,
    global_address=None,
    global_cr=None,
):
    df = df.copy()

    # Start Date
    if global_start_date:
        df.loc[df["start_date"] == "", "start_date"] = global_start_date

    # End Date
    if global_end_date:
        df.loc[df["end_date"] == "", "end_date"] = global_end_date

    # Address
    if global_address:
        df.loc[df["address_line_1"] == "", "address_line_1"] = global_address

    # CR Reference
    if global_cr:
        df.loc[df["cr_reference"] == "", "cr_reference"] = global_cr

    return df
