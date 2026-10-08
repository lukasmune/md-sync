# Fields owned by our internal sales team
# External synchronization must never create, modify, or delete these fields.
PROTECTED_FIELDS = {
    "sales_status",
    "sales_owner",
    "sales_notes",
}


def merge_external_data(existing_company, external_data):
    updated_company = existing_company.copy()

    for key, value in external_data.items():
        if key not in PROTECTED_FIELDS:
            updated_company[key] = value

    return updated_company


# Compatibility alias for callers of the former application-specific helper.
merge_gifa_data = merge_external_data