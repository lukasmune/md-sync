"""One workbook with the current editions of all configured fairs.

This is a read-only internal export. It never touches the Mailchimp export
history, so it cannot affect the Mailchimp sync cycle.
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from openpyxl import Workbook

import database
from config import EVENTS, EXPORTS_DIR
from country_codes import country_code
from excel_export import _format_data_sheet

FULL_LIST_DIR = EXPORTS_DIR / "all_editions"

EXHIBITOR_HEADERS = [
    "Company Name", "Country", "Country Code", "City", "Website", "Email",
    "Telephone", "Exhibition", "Edition", "Hall", "Stand", "Location",
    "Premium", "Exhibitor Role", "Exhibitor ID", "Exhibition SEO ID",
    "Product Categories", "First Seen", "Last Seen", "Last Changed",
]
COMPANY_HEADERS = [
    "Company Name", "Country", "Country Code", "City", "Website", "Email",
    "Telephone", "Exhibitions",
]


def _connect():
    connection = sqlite3.connect(database.DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def _participations(connection):
    clauses = " OR ".join(
        "(UPPER(e.event_name) = ? AND e.edition = ?)" for _ in EVENTS
    )
    parameters = [
        value
        for name, config in EVENTS.items()
        for value in (name.upper(), config["edition"])
    ]
    return connection.execute(
        f"""
        SELECT c.id AS company_id, c.name, c.country, c.city, c.website,
               c.email, c.telephone, e.event_name, e.edition,
               ec.hall, ec.stand, ec.location, ec.premium,
               ec.exhibitor_role, ec.source_exhibitor_id, ec.seo_id,
               ec.first_seen_at, ec.last_seen_at, ec.changed_at,
               COALESCE((
                   SELECT group_concat(label, '; ')
                   FROM (
                       SELECT DISTINCT pc.label
                       FROM exhibition_company_categories ecc
                       JOIN product_categories pc
                           ON pc.id = ecc.product_category_id
                       WHERE ecc.exhibition_company_id = ec.id
                       ORDER BY pc.label
                   )
               ), '') AS product_categories
        FROM exhibition_companies ec
        JOIN companies c ON c.id = ec.company_id
        JOIN exhibitions e ON e.id = ec.exhibition_id
        WHERE {clauses}
        ORDER BY c.name COLLATE NOCASE, c.id, e.event_name
        """,
        parameters,
    ).fetchall()


def _label(row):
    return f"{row['event_name'].upper()} {row['edition']}"


def export_full_list(output_dir=FULL_LIST_DIR, timestamp=None):
    """Write all exhibitors of the current editions of every fair.

    Returns the workbook path. Each call writes a new timestamped file.
    """

    database.initialize_database()
    with _connect() as connection:
        rows = _participations(connection)

    timestamp = timestamp or datetime.now().astimezone()
    output_directory = Path(output_dir)
    output_directory.mkdir(parents=True, exist_ok=True)
    output_path = output_directory / f"all_editions_{timestamp:%Y-%m-%d_%H%M%S}.xlsx"
    while output_path.exists():
        timestamp += timedelta(seconds=1)
        output_path = (
            output_directory / f"all_editions_{timestamp:%Y-%m-%d_%H%M%S}.xlsx"
        )

    workbook = Workbook()
    summary = workbook.active
    summary.title = "Summary"
    exhibitors = workbook.create_sheet("All Exhibitors")
    companies_sheet = workbook.create_sheet("Companies")

    exhibitors.append(EXHIBITOR_HEADERS)
    companies = {}
    per_fair = {}
    for row in rows:
        exhibitors.append([
            row["name"], row["country"], country_code(row["country"]),
            row["city"], row["website"], row["email"], row["telephone"],
            row["event_name"].upper(), row["edition"], row["hall"],
            row["stand"], row["location"], bool(row["premium"]),
            row["exhibitor_role"], row["source_exhibitor_id"], row["seo_id"],
            row["product_categories"], row["first_seen_at"],
            row["last_seen_at"], row["changed_at"],
        ])
        companies.setdefault(row["company_id"], []).append(row)
        per_fair.setdefault(_label(row), set()).add(row["company_id"])

    companies_sheet.append(COMPANY_HEADERS)
    for company_rows in companies.values():
        first = company_rows[0]
        companies_sheet.append([
            first["name"], first["country"], country_code(first["country"]),
            first["city"], first["website"], first["email"],
            first["telephone"],
            ", ".join(dict.fromkeys(_label(r) for r in company_rows)),
        ])

    summary.append(["Exported At", timestamp.replace(tzinfo=None)])
    summary["B1"].number_format = "yyyy-mm-dd hh:mm:ss"
    for name, config in EVENTS.items():
        label = f"{name.upper()} {config['edition']}"
        summary.append([label, len(per_fair.get(label, ()))])
    summary.append(["Distinct companies", len(companies)])
    summary.append(["Exhibitor entries", len(rows)])
    summary.column_dimensions["A"].width = 28
    summary.column_dimensions["B"].width = 24

    _format_data_sheet(exhibitors, "AllExhibitorsTable")
    _format_data_sheet(companies_sheet, "CompaniesTable")
    workbook.save(output_path)
    return output_path
