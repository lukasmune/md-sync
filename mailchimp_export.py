"""Mailchimp upload list: one new contact per distinct email address.

The internal exports keep all collected data. This module writes a separate
workbook shaped like the "Sample Exhibitor List" (sheets ``Info INTERNAL`` and
``Info Mailchimp``) and remembers every exported email address so that a
contact is never handed to Mailchimp twice.
"""

import re
import sqlite3
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

import database
from config import EVENTS, EXPORTS_DIR

MAILCHIMP_DIR = EXPORTS_DIR / "mailchimp"
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

INTERN_HEADERS = [
    "Company Name", "Country", "City", "Website", "Email", "Telephone",
    "Exhibition", "Hall", "Stand", "Location", "Premium", "Exhibitor Role",
    "Source Report Date",
]
MAILCHIMP_HEADERS = [
    "Email", "Company", "Country", "City", "Tag Exhibition", "Tag Hall",
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
        next((r["country"] for r in rows if r["country"]), None),
        next((r["city"] for r in rows if r["city"]), None),
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


def pending_contacts():
    """Return {email: rows} for current-edition emails never exported."""

    database.initialize_database()
    with _connect() as connection:
        _ensure_table(connection)
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


def _write_workbook(contacts, output_directory, timestamp, prefix="mailchimp"):
    report_date = timestamp.strftime("%Y-%m-%d")
    output_directory = Path(output_directory)
    output_directory.mkdir(parents=True, exist_ok=True)
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
                row["name"], row["country"], row["city"], row["website"],
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

    contacts = pending_contacts()
    if not contacts:
        return None

    timestamp = timestamp or datetime.now().astimezone()
    output_path = _write_workbook(contacts, output_dir, timestamp)
    _record_exported(contacts, timestamp, output_path.name)
    return output_path


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


def _record_exported(emails, timestamp, source_file):
    with _connect() as connection:
        _ensure_table(connection)
        connection.executemany(
            "INSERT OR IGNORE INTO mailchimp_exported_emails "
            "(email, exported_at, source_file) VALUES (?, ?, ?)",
            [(email, timestamp.isoformat(), source_file) for email in emails],
        )


def mark_current_contacts_as_exported():
    """Record all current emails as already in Mailchimp, without a file.

    Use once, before the first export, when the existing contacts were
    contacted by other means. Returns the number of emails recorded.
    """

    contacts = pending_contacts()
    _record_exported(
        contacts, datetime.now().astimezone(), "baseline (not exported)"
    )
    return len(contacts)
