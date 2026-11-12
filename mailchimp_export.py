"""Mailchimp upload list: one new contact per distinct email address.

The internal exports keep all collected data. This module writes a separate
workbook shaped like the "Sample Exhibitor List" (sheets ``Info INTERNAL`` and
``Info Mailchimp``) and remembers every exported email address so that a
contact is never handed to Mailchimp twice.
"""

import re
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import NamedTuple

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

import database
from config import EVENTS, EXPORTS_DIR
from mailchimp_countries import mailchimp_country

MAILCHIMP_DIR = EXPORTS_DIR / "mailchimp"
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

INTERN_HEADERS = [
    "Company Name", "Country", "City", "Website", "Email", "Telephone",
    "Exhibition", "Hall", "Stand", "Location", "Premium", "Exhibitor Role",
    "Source Report Date",
]
MAILCHIMP_HEADERS = [
    "Email", "Company", "Country", "City", "Telephone", "Tag Exhibition",
    "Tag Hall",
]


def _connect():
    connection = sqlite3.connect(database.DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def _ensure_table(connection):
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS mailchimp_exported_emails (
            email TEXT PRIMARY KEY,
            exported_at TEXT NOT NULL,
            source_file TEXT
        )
        """
    )


def normalize_email(email):
    """Return the lowercase address, or None when it is not a valid email."""

    value = (email or "").strip().lower()
    return value if EMAIL_PATTERN.match(value) else None


def _current_participations(connection):
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
               ec.hall, ec.stand, ec.location, ec.premium, ec.exhibitor_role
        FROM exhibition_companies ec
        JOIN companies c ON c.id = ec.company_id
        JOIN exhibitions e ON e.id = ec.exhibition_id
        WHERE {clauses}
        ORDER BY c.name COLLATE NOCASE, c.id, e.event_name
        """,
        parameters,
    ).fetchall()


def _group_by_email(participations):
    """Merge every company and participation sharing one email address."""

    contacts = {}
    for row in participations:
        email = normalize_email(row["email"])
        if email:
            contacts.setdefault(email, []).append(row)
    return contacts


def _unique(values):
    return list(dict.fromkeys(v for v in values if v))


def _mailchimp_row(email, rows):
    return [
        email,
        " / ".join(_unique(r["name"] for r in rows)),
        next(
            (mailchimp_country(r["country"]) for r in rows if r["country"]),
            None,
        ),
        next((r["city"] for r in rows if r["city"]), None),
        next((r["telephone"] for r in rows if r["telephone"]), None),
        ", ".join(_unique(
            f"{r['event_name'].upper()} {r['edition']}" for r in rows
        )),
        ", ".join(_unique(r["hall"] for r in rows)),
    ]


def _write_sheet_header(worksheet, headers):
    worksheet.append(headers)
    for cell in worksheet[1]:
        cell.font = Font(bold=True)
    worksheet.freeze_panes = "A2"
    worksheet.auto_filter.ref = f"A1:{get_column_letter(len(headers))}1"
    for index in range(1, len(headers) + 1):
        worksheet.column_dimensions[
            worksheet.cell(row=1, column=index).column_letter
        ].width = 24


def _pending_contacts(connection):
    contacts = _group_by_email(_current_participations(connection))
    exported = {
        row["email"]
        for row in connection.execute(
            "SELECT email FROM mailchimp_exported_emails"
        )
    }
    return {
        email: rows for email, rows in contacts.items()
        if email not in exported
    }


def pending_contacts():
    """Return {email: rows} for current-edition emails never exported."""

    database.initialize_database()
    with _connect() as connection:
        _ensure_table(connection)
        return _pending_contacts(connection)


def _write_workbook(contacts, output_directory, timestamp, prefix="mailchimp"):
    report_date = timestamp.strftime("%Y-%m-%d")
    output_directory = Path(output_directory)
    output_directory.mkdir(parents=True, exist_ok=True)
    output_path = output_directory / (
        f"{prefix}_{timestamp:%Y-%m-%d_%H%M%S}.xlsx"
    )
    while output_path.exists():
        timestamp += timedelta(seconds=1)
        output_path = output_directory / (
            f"{prefix}_{timestamp:%Y-%m-%d_%H%M%S}.xlsx"
        )

    workbook = Workbook()
    intern = workbook.active
    intern.title = "Info INTERNAL"
    mailchimp = workbook.create_sheet("Info Mailchimp")
    _write_sheet_header(intern, INTERN_HEADERS)
    _write_sheet_header(mailchimp, MAILCHIMP_HEADERS)

    for email in sorted(contacts):
        rows = contacts[email]
        mailchimp.append(_mailchimp_row(email, rows))
        for row in rows:
            intern.append([
                row["name"], mailchimp_country(row["country"]), row["city"],
                row["website"],
                email, row["telephone"],
                f"{row['event_name'].upper()} {row['edition']}",
                row["hall"], row["stand"], row["location"],
                bool(row["premium"]), row["exhibitor_role"], report_date,
            ])
    workbook.save(output_path)
    return output_path


def export_mailchimp_list(output_dir=MAILCHIMP_DIR, timestamp=None):
    """Write the upload workbook for contacts not exported before.

    Returns the workbook path, or None when there is nothing new. The emails
    are recorded as exported only after the file was saved.
    """

    database.initialize_database()
    with _connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        _ensure_table(connection)
        contacts = _pending_contacts(connection)
        if not contacts:
            return None

        timestamp = timestamp or datetime.now().astimezone()
        output_path = _write_workbook(contacts, output_dir, timestamp)
        connection.executemany(
            "INSERT INTO mailchimp_exported_emails "
            "(email, exported_at, source_file) VALUES (?, ?, ?)",
            [(email, timestamp.isoformat(), output_path.name) for email in contacts],
        )
        return output_path


def recover_baselined_run(run_id, baseline_timestamp, output_dir=MAILCHIMP_DIR,
                          timestamp=None):
    """Recreate a sync's new contacts marked by a particular baseline.

    The export history is not modified. Previously exported addresses and
    contacts not included in the specified baseline remain excluded.
    """

    database.initialize_database()
    with _connect() as connection:
        _ensure_table(connection)
        company_ids = {
            row["company_id"]
            for row in connection.execute(
                "SELECT DISTINCT company_id FROM change_history "
                "WHERE run_id = ? AND record_type = 'participation' "
                "AND is_new = 1",
                (run_id,),
            )
        }
        baseline_emails = {
            row["email"]
            for row in connection.execute(
                "SELECT email FROM mailchimp_exported_emails "
                "WHERE source_file = ? AND exported_at = ?",
                ("baseline (not exported)", baseline_timestamp),
            )
        }
        all_contacts = _group_by_email(_current_participations(connection))
        contacts = {
            email: rows for email, rows in all_contacts.items()
            if email in baseline_emails
            and any(row["company_id"] in company_ids for row in rows)
        }
    if not contacts:
        raise ValueError("No matching baselined contacts found for the sync run")
    timestamp = timestamp or datetime.now().astimezone()
    return _write_workbook(
        contacts, output_dir, timestamp, prefix="mailchimp_recovered"
    )


def rebuild_mailchimp_list(
    source_file=None, output_dir=MAILCHIMP_DIR, timestamp=None
):
    """Recreate an already exported list from the current data.

    Writes the contacts of ``source_file`` (default: the most recent real
    export) with today's data and format. The export log is not changed, so
    the contacts stay marked as exported. Returns the path, or None when no
    export exists.
    """

    database.initialize_database()
    with _connect() as connection:
        _ensure_table(connection)
        if source_file is None:
            latest = connection.execute(
                "SELECT source_file FROM mailchimp_exported_emails "
                "WHERE source_file NOT LIKE 'baseline%' "
                "ORDER BY exported_at DESC LIMIT 1"
            ).fetchone()
            if latest is None:
                return None
            source_file = latest["source_file"]
        emails = {
            row["email"]
            for row in connection.execute(
                "SELECT email FROM mailchimp_exported_emails "
                "WHERE source_file = ?",
                (source_file,),
            )
        }
        contacts = {
            email: rows
            for email, rows in _group_by_email(
                _current_participations(connection)
            ).items()
            if email in emails
        }
    if not contacts:
        return None
    timestamp = timestamp or datetime.now().astimezone()
    return _write_workbook(
        contacts, output_dir, timestamp, prefix="mailchimp_rebuilt"
    )


class BaselineResult(NamedTuple):
    eligible_addresses: int
    already_recorded: int
    newly_recorded: int
    companies_without_usable_email: int


def baseline_current_contacts():
    """Record current addresses and return counts for the baseline operation."""

    database.initialize_database()
    with _connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        _ensure_table(connection)
        participations = _current_participations(connection)
        contacts = _group_by_email(participations)
        companies = {row["company_id"]: row for row in participations}
        missing = sum(
            normalize_email(row["email"]) is None for row in companies.values()
        )
        before = connection.total_changes
        timestamp = datetime.now().astimezone().isoformat()
        connection.executemany(
            "INSERT OR IGNORE INTO mailchimp_exported_emails "
            "(email, exported_at, source_file) VALUES (?, ?, ?)",
            [(email, timestamp, "baseline (not exported)") for email in contacts],
        )
        newly_recorded = connection.total_changes - before
        return BaselineResult(
            len(contacts), len(contacts) - newly_recorded, newly_recorded, missing
        )


def mark_current_contacts_as_exported():
    """Record current addresses without a file; return the number newly marked."""

    return baseline_current_contacts().newly_recorded


def print_baseline_result():
    """Run the baseline and explain its coverage in the terminal."""

    result = baseline_current_contacts()
    print(f"Current-edition distinct usable addresses: {result.eligible_addresses}")
    print(f"Already recorded by previous exports or baselines: {result.already_recorded}")
    print(f"Newly marked by this baseline: {result.newly_recorded}")
    print(
        "Current-edition companies without a usable email: "
        f"{result.companies_without_usable_email}"
    )
    if not result.eligible_addresses:
        print("No usable email addresses found for the configured current editions.")
    print("Recorded addresses are not verified against the Mailchimp audience.")
