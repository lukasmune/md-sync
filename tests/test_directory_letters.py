import string

import requests


BASE_URL = "https://widgets.messe-duesseldorf.de/vis-api/vis/v1/en/directory"
DOMAIN = "www.gifa.com"
TARGET_EVENT = "GIFA 2023"


def fetch_letter(letter):
    url = f"{BASE_URL}/{letter}"

    response = requests.get(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0",
            "X-Vis-Domain": DOMAIN,
        },
        timeout=30,
    )

    response.raise_for_status()

    return response.json()


def is_target_event(exhibitor):
    return any(
        icon.get("label") == TARGET_EVENT
        for icon in exhibitor.get("eventIcons", [])
    )


def test_gifa_2023_directory():
    print("\n--- GIFA 2023 DIRECTORY ---")

    all_records = []
    gifa_records = []

    for letter in string.ascii_lowercase:
        records = fetch_letter(letter)

        print(f"{letter.upper()}: {len(records)} records")

        all_records.extend(records)

        gifa_records.extend(
            record
            for record in records
            if is_target_event(record)
        )

    unique_records = {
        record["id"]: record
        for record in gifa_records
        if record.get("id")
    }

    countries = {
        record.get("country")
        for record in unique_records.values()
        if record.get("country")
    }

    with_logo = sum(
        1
        for record in unique_records.values()
        if record.get("logo")
    )

    premium = sum(
        1
        for record in unique_records.values()
        if record.get("premium") is True
    )

    missing_location = sum(
        1
        for record in unique_records.values()
        if not record.get("location")
    )

    print("\n--- STATISTICS ---")
    print(f"Total API records:      {len(all_records)}")
    print(f"GIFA 2023 records:      {len(gifa_records)}")
    print(f"Unique GIFA exhibitors: {len(unique_records)}")
    print(f"Countries:              {len(countries)}")
    print(f"With logo:              {with_logo}")
    print(f"Premium:                {premium}")
    print(f"Missing location:       {missing_location}")

    print("\n--- SAMPLE EXHIBITORS ---")

    for record in list(unique_records.values())[:10]:
        print(
            f"{record.get('name')} | "
            f"{record.get('country')} | "
            f"{record.get('city')} | "
            f"{record.get('location')}"
        )

    print("\n--- END GIFA 2023 DIRECTORY ---")


def filter_exhibitors_by_event(records, event_label):
    """Return profile records associated with the requested event."""

    exhibitors = []

    for record in records:
        if record.get("type") != "profile":
            continue

        event_icons = record.get("eventIcons", [])

        if any(
            icon.get("label") == event_label
            for icon in event_icons
        ):
            exhibitors.append(record)

    return exhibitors