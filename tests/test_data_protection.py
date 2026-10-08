from sync import merge_external_data


def test_gifa_update_does_not_overwrite_internal_sales_data():
    existing_company = {
        "name": "Example Foundry",
        "country": "Germany",
        "website": "https://example.com",
        "sales_status": "Qualified",
        "sales_owner": "Lukas",
        "sales_notes": "Interested in ANKIROS 2026",
    }

    gifa_update = {
        "name": "Example Foundry GmbH",
        "country": "Germany",
        "website": "https://example-foundry.com",
        "sales_status": "Cold",
        "sales_owner": "Someone Else",
        "sales_notes": "No interest",
    }

    updated_company = merge_external_data(
        existing_company,
        gifa_update,
    )

    assert updated_company["name"] == "Example Foundry GmbH"
    assert updated_company["website"] == "https://example-foundry.com"

    assert updated_company["sales_status"] == "Qualified"
    assert updated_company["sales_owner"] == "Lukas"
    assert updated_company["sales_notes"] == "Interested in ANKIROS 2026"

def test_gifa_empty_values_do_not_overwrite_internal_sales_data():
    existing_company = {
        "name": "Example Foundry",
        "sales_status": "Qualified",
        "sales_owner": "Lukas",
        "sales_notes": "Interested in ANKIROS 2026",
    }

    gifa_update = {
        "name": "Example Foundry GmbH",
        "sales_status": None,
        "sales_owner": "",
        "sales_notes": None,
    }

    updated_company = merge_external_data(
        existing_company,
        gifa_update,
    )

    assert updated_company["sales_status"] == "Qualified"
    assert updated_company["sales_owner"] == "Lukas"
    assert updated_company["sales_notes"] == "Interested in ANKIROS 2026"

def test_missing_gifa_fields_do_not_remove_internal_sales_data():
    existing_company = {
        "name": "Example Foundry",
        "country": "Germany",
        "sales_status": "Qualified",
        "sales_owner": "Lukas",
        "sales_notes": "Interested in ANKIROS 2026",
    }

    gifa_update = {
        "name": "Example Foundry GmbH",
        "country": "Germany",
    }

    updated_company = merge_external_data(
        existing_company,
        gifa_update,
    )

    assert updated_company["sales_status"] == "Qualified"
    assert updated_company["sales_owner"] == "Lukas"
    assert updated_company["sales_notes"] == "Interested in ANKIROS 2026"