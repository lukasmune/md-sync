import requests
import sys

from config import (
    DIRECTORY_LETTERS,
    EVENTS,
    GIFA_BASE_URL,
    GIFA_DOMAIN,
    GIFA_EVENT_ID,
    REQUEST_TIMEOUT,
)

from database import (
    get_or_create_exhibition,
    initialize_database,
    sync_exhibitor,
)


def fetch_directory_letter(letter, event_config=None):
    """Fetch one directory letter using the selected event configuration."""

    event_config = event_config or EVENTS["GIFA"]

    url = f"{event_config['base_url']}/{letter.lower()}"

    response = requests.get(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0",
            "X-Vis-Domain": event_config["domain"],
        },
        timeout=REQUEST_TIMEOUT,
    )

    response.raise_for_status()

    return response.json()


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


def fetch_exhibitors_by_event(event_label, event_config=None):
    """Fetch all profile records associated with an event."""

    exhibitors = []

    for letter in DIRECTORY_LETTERS:
        if event_config is None:
            records = fetch_directory_letter(letter)
        else:
            records = fetch_directory_letter(letter, event_config)

        exhibitors.extend(
            filter_exhibitors_by_event(
                records,
                event_label,
            )
        )

    return exhibitors


def fetch_gifa_2023_exhibitors():
    """Fetch and return all GIFA 2023 exhibitor profile records."""

    return fetch_exhibitors_by_event("GIFA 2023")


def get_event_config(event_name):
    """Return a configured event by case-insensitive name."""

    try:
        return EVENTS[event_name.upper()]
    except KeyError as error:
        raise ValueError(
            f"Unknown event {event_name!r}; choose from {', '.join(EVENTS)}"
        ) from error


def sync_event(
    event_name,
    edition,
    event_code,
    exhibitors,
):
    """
    Synchronize a collection of exhibitor records for one exhibition.
    """

    initialize_database()

    exhibition_id = get_or_create_exhibition(
        event_name=event_name,
        edition=edition,
        event_code=event_code,
    )

    created = 0
    updated = 0

    for record in exhibitors:
        result = sync_exhibitor(
            record,
            exhibition_id,
        )

        if result["created"]:
            created += 1
        else:
            updated += 1

    return {
        "total": len(exhibitors),
        "created": created,
        "updated": updated,
    }


def sync_event_from_api(
    event_name,
    edition,
    event_code,
    event_label,
):
    """
    Fetch exhibitors for an event and synchronize them
    into the local database.
    """

    exhibitors = fetch_exhibitors_by_event(event_label)

    return sync_event(
        event_name=event_name,
        edition=edition,
        event_code=event_code,
        exhibitors=exhibitors,
    )


def sync_configured_event(event_name):
    """Fetch and synchronize one of the configured Messe Düsseldorf events."""

    config = get_event_config(event_name)
    exhibitors = fetch_exhibitors_by_event(
        config["event_label"],
        event_config=config,
    )
    return sync_event(
        event_name=event_name.upper(),
        edition=config["edition"],
        event_code=config["event_code"],
        exhibitors=exhibitors,
    )


def sync_gifa_2023():
    """
    Fetch GIFA 2023 exhibitors and synchronize them
    into the local database.
    """

    return sync_event_from_api(
        event_name="GIFA",
        edition=2023,
        event_code=GIFA_EVENT_ID,
        event_label="GIFA 2023",
    )


if __name__ == "__main__":
    selected_event = sys.argv[1] if len(sys.argv) > 1 else "GIFA"
    result = sync_configured_event(selected_event)

    print(f"\n--- {selected_event.upper()} SYNC ---")
    print(f"Total exhibitors:    {result['total']}")
    print(f"New companies:       {result['created']}")
    print(f"Updated companies:   {result['updated']}")
    print("--- END SYNC ---")