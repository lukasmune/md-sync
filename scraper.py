import requests
import sys
import time
from datetime import datetime
from uuid import uuid4

from config import (
    DIRECTORY_LETTERS,
    DIRECTORY_REQUEST_DELAY,
    DIRECTORY_REQUEST_RETRIES,
    EVENTS,
    FINDER_BASE_URL,
    PROFILE_REQUEST_DELAY,
    PROFILE_REQUEST_RETRIES,
    GIFA_BASE_URL,
    GIFA_DOMAIN,
    GIFA_EVENT_ID,
    REQUEST_TIMEOUT,
)

from database import (
    get_or_create_exhibition,
    initialize_database,
    sync_exhibitor,
    discard_change_history,
    get_change_history,
)
from excel_export import export_change_report, summarize_change_rows


def fetch_directory_letter(letter, event_config=None):
    """Fetch one directory letter using the selected event configuration."""

    event_config = event_config or EVENTS["GIFA"]

    url = f"{event_config['base_url']}/{letter.lower()}"

    headers = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0",
        "X-Vis-Domain": event_config["domain"],
    }
    for attempt in range(DIRECTORY_REQUEST_RETRIES + 1):
        response = requests.get(
            url,
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )
        if response.status_code != 429:
            response.raise_for_status()
            return response.json()

        if attempt == DIRECTORY_REQUEST_RETRIES:
            response.raise_for_status()

        retry_after = response.headers.get("Retry-After")
        try:
            delay = max(float(retry_after), DIRECTORY_REQUEST_DELAY)
        except (TypeError, ValueError):
            delay = DIRECTORY_REQUEST_DELAY * (2 ** attempt)
        time.sleep(delay)

    raise RuntimeError("Directory request retry loop completed unexpectedly.")


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

        matching = filter_exhibitors_by_event(records, event_label)
        if event_config and event_config.get("enrich_profiles"):
            matching = [
                enrich_exhibitor_record(record, event_config)
                for record in matching
            ]
        for exhibitor in matching:
            exhibitors.extend(expand_exhibitor_records(exhibitor))

    return exhibitors


def expand_exhibitor_records(record):
    """Expand source-provided co-exhibitors without changing direct records."""

    expanded = [dict(record, exhibitor_role="direct")]
    nested_keys = (
        "coExhibitors",
        "co_exhibitors",
        "coExhibitor",
        "subExhibitors",
        "sub_exhibitors",
    )
    for key in nested_keys:
        nested = record.get(key) or []
        if isinstance(nested, dict):
            nested = [nested]
        for child in nested:
            if not isinstance(child, dict):
                continue
            child_record = dict(child)
            child_record["exhibitor_role"] = "co-exhibitor"
            child_record["parent_source_exhibitor_id"] = record.get("exh")
            expanded.append(child_record)
    return expanded


def fetch_exhibitor_profile(exhibitor_id, event_config):
    """Fetch the structured VIS profile for one exhibitor appearance."""

    url = (
        f"{FINDER_BASE_URL}/en/exhibitors/"
        f"{exhibitor_id}/slices/profile"
    )
    headers = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0",
        "X-Vis-Domain": event_config["domain"],
    }
    for attempt in range(PROFILE_REQUEST_RETRIES + 1):
        response = requests.get(
            url,
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )
        if response.status_code != 429:
            response.raise_for_status()
            return response.json()

        if attempt == PROFILE_REQUEST_RETRIES:
            response.raise_for_status()

        retry_after = response.headers.get("Retry-After")
        try:
            delay = max(float(retry_after), PROFILE_REQUEST_DELAY)
        except (TypeError, ValueError):
            delay = PROFILE_REQUEST_DELAY * (2 ** attempt)
        time.sleep(delay)

    raise RuntimeError("Profile request retry loop completed unexpectedly.")


def enrich_exhibitor_record(record, event_config):
    """Merge profile data, including structured product categories, into a record."""

    exhibitor_id = record.get("exh")
    if not exhibitor_id:
        return record

    profile = fetch_exhibitor_profile(exhibitor_id, event_config)
    enriched = dict(record)
    enriched.update(
        {
            "email": profile.get("email") or profile.get("getInTouchEmail"),
            "telephone": (profile.get("phone") or {}).get("phone"),
            "website": next(
                (
                    link.get("link")
                    for link in profile.get("links", [])
                    if link.get("link")
                ),
                None,
            ),
            "categories": profile.get("categories", []),
        }
    )
    address = profile.get("profileAddress") or {}
    for source, target in (("city", "city"), ("country", "country")):
        if address.get(source):
            enriched[target] = address[source]
    if profile.get("name"):
        enriched["name"] = profile["name"]
    return enriched


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
    run_id=None,
    emit_summary=True,
):
    """
    Synchronize a collection of exhibitor records for one exhibition.
    """

    initialize_database()
    owns_run = run_id is None
    run_id = run_id or str(uuid4())

    exhibition_id = get_or_create_exhibition(
        event_name=event_name,
        edition=edition,
        event_code=event_code,
    )

    created = 0
    updated = 0

    try:
        for record in exhibitors:
            result = sync_exhibitor(record, exhibition_id, run_id=run_id)

            if result["created"]:
                created += 1
            else:
                updated += 1
    except Exception:
        discard_change_history(run_id)
        raise

    changes = get_change_history(run_id)
    if owns_run:
        _report_run_results(
            run_id,
            changes,
            emit_summary=emit_summary,
        )

    return {
        "total": len(exhibitors),
        "created": created,
        "updated": updated,
    }


def _report_run_results(run_id, changes, emit_summary=True):
    """Create edition reports and print counts from the same source rows."""

    reports = []
    grouped = {}
    for change in changes:
        key = (str(change["event_name"]).strip().upper(), change["edition"])
        grouped.setdefault(key, []).append(change)

    timestamp = datetime.now().astimezone()
    summaries = []
    for (event_name, edition), edition_changes in grouped.items():
        counts = summarize_change_rows(edition_changes)
        report_path = export_change_report(
            run_id,
            edition_changes,
            timestamp=timestamp,
        )
        reports.append(report_path)
        summaries.append((event_name, edition, counts, report_path))

    if emit_summary:
        if not summaries:
            print("Sync completed. No changes detected.")
        else:
            print("Sync completed. Changes detected.")
            for index, (
                event_name,
                edition,
                counts,
                report_path,
            ) in enumerate(summaries):
                print(
                    f"{event_name} {edition}: "
                    f"New companies: {counts['new_company_count']} | "
                    f"New participations: "
                    f"{counts['new_participation_count']} | "
                    f"Updated records: "
                    f"{counts['updated_record_count']} | "
                    f"Changed fields: {counts['changed_field_count']}"
                )
                print(f"Change report: {report_path}")
                if index < len(summaries) - 1:
                    print()
    return reports, summaries


def sync_configured_events(event_names=None):
    """Synchronize configured events as one run with edition reports."""

    selected = event_names or list(EVENTS)
    run_id = str(uuid4())
    results = []
    try:
        for event_name in selected:
            config = get_event_config(event_name)
            exhibitors = fetch_exhibitors_by_event(
                config["event_label"],
                event_config=config,
            )
            results.append(
                sync_event(
                    event_name=event_name.upper(),
                    edition=config["edition"],
                    event_code=config["event_code"],
                    exhibitors=exhibitors,
                    run_id=run_id,
                    emit_summary=False,
                )
            )
    except Exception:
        discard_change_history(run_id)
        raise

    changes = get_change_history(run_id)
    _report_run_results(run_id, changes)
    return results


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
    sync_configured_event(selected_event)