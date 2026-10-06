from pathlib import Path
import sqlite3

from openpyxl import Workbook
from openpyxl.styles import Font, Alignment
from openpyxl.worksheet.table import Table, TableStyleInfo
from openpyxl.utils import get_column_letter

import database


def get_connection():
    """Return a connection to the local SQLite database."""
    connection = sqlite3.connect(database.DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def export_exhibition_to_excel(
    event_name,
    edition,
    output_path,
):
    """
    Export one exhibition and its companies to an Excel workbook.

    The SQLite database remains the source of truth.
    Excel is only an exported reporting format.
    """

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    database.initialize_database()

    with get_connection() as connection:
        exhibition = connection.execute(
            """
            SELECT
                id,
                event_name,
                edition,
                event_code
            FROM exhibitions
            WHERE event_name = ?
              AND edition = ?
            """,
            (event_name, edition),
        ).fetchone()

        if exhibition is None:
            raise ValueError(
                f"Exhibition not found: {event_name} {edition}"
            )

        companies = connection.execute(
            """
            SELECT
                c.id AS company_id,
                c.name AS company_name,
                c.country,
                c.city,
                c.website,
                c.logo,
                c.created_at,
                c.updated_at
            FROM companies c
            INNER JOIN exhibition_companies ec
                ON ec.company_id = c.id
            WHERE ec.exhibition_id = ?
            ORDER BY c.name COLLATE NOCASE
            """,
            (exhibition["id"],),
        ).fetchall()

        exhibition_records = connection.execute(
            """
            SELECT
                c.id AS company_id,
                c.name AS company_name,
                c.country,
                c.city,
            c.website,
            c.logo,
            c.created_at AS company_created_at,
            c.updated_at AS company_updated_at,
            c.email,
            c.contact_person,
            c.telephone,
            c.product_categories_json,
            c.product_groups_json,
                e.event_name,
                e.edition,
                e.event_code,
                ec.gifa_exhibitor_id,
                ec.seo_id AS exh_seo_id,
            ec.hall,
            ec.stand,
                ec.location,
            ec.premium,
            ec.tags_json,
            ec.first_seen_at,
            ec.last_seen_at,
            ec.changed_at
            FROM exhibition_companies ec
            INNER JOIN companies c
                ON ec.company_id = c.id
            INNER JOIN exhibitions e
                ON ec.exhibition_id = e.id
            WHERE ec.exhibition_id = ?
            ORDER BY c.name COLLATE NOCASE
            """,
            (exhibition["id"],),
        ).fetchall()

    workbook = Workbook()

    summary_sheet = workbook.active
    summary_sheet.title = "Summary"

    companies_sheet = workbook.create_sheet("Company Master")
    records_sheet = workbook.create_sheet("Sales Leads")

    _build_summary_sheet(
        summary_sheet,
        exhibition,
        companies,
        exhibition_records,
    )

    _build_companies_sheet(
        companies_sheet,
        companies,
    )

    _build_records_sheet(
        records_sheet,
        exhibition_records,
    )

    workbook.save(output_path)

    return output_path


def export_database_to_excel(output_path):
    """Export all GIFA editions in the local database for sales analysis."""

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    database.initialize_database()

    with get_connection() as connection:
        records = connection.execute(
            """
            SELECT c.id AS company_id, c.name AS company_name, c.country,
                c.city, c.website, c.logo,
                c.created_at AS company_created_at,
                c.updated_at AS company_updated_at,
                c.email, c.contact_person, c.telephone,
                c.product_categories_json, c.product_groups_json,
                e.event_name, e.edition, e.event_code,
                ec.gifa_exhibitor_id, ec.seo_id AS exh_seo_id,
                ec.hall, ec.stand, ec.location, ec.premium, ec.tags_json,
                ec.first_seen_at, ec.last_seen_at, ec.changed_at
            FROM exhibition_companies ec
            JOIN companies c ON c.id = ec.company_id
            JOIN exhibitions e ON e.id = ec.exhibition_id
            ORDER BY e.edition, c.name COLLATE NOCASE
            """
        ).fetchall()

        companies = connection.execute(
            """
            SELECT DISTINCT c.id AS company_id, c.name AS company_name,
                c.country, c.city, c.website, c.logo,
                c.created_at, c.updated_at
            FROM companies c
            JOIN exhibition_companies ec ON ec.company_id = c.id
            ORDER BY c.name COLLATE NOCASE
            """
        ).fetchall()

    if not records:
        raise ValueError("No exhibitor records found in the database.")

    workbook = Workbook()
    summary_sheet = workbook.active
    summary_sheet.title = "Summary"
    companies_sheet = workbook.create_sheet("Company Master")
    records_sheet = workbook.create_sheet("Sales Leads")
    summary = {
        "event_name": "GIFA",
        "edition": "All editions",
        "event_code": "Multiple editions",
    }
    _build_summary_sheet(summary_sheet, summary, companies, records)
    _build_companies_sheet(companies_sheet, companies)
    _build_records_sheet(records_sheet, records)
    workbook.save(output_path)
    return output_path


def _build_summary_sheet(
    worksheet,
    exhibition,
    companies,
    exhibition_records,
):
    """Build the summary worksheet."""

    worksheet["A1"] = "GIFA Sales Export"
    worksheet["A1"].font = Font(
        bold=True,
        size=16,
    )

    worksheet["A3"] = "Event"
    worksheet["B3"] = exhibition["event_name"]

    worksheet["A4"] = "Edition"
    worksheet["B4"] = exhibition["edition"]

    worksheet["A5"] = "Event Code"
    worksheet["B5"] = exhibition["event_code"]

    worksheet["A7"] = "Sales Leads"
    worksheet["B7"] = len(companies)

    worksheet["A8"] = "Participation Records"
    worksheet["B8"] = len(exhibition_records)

    worksheet["A10"] = "Generated By"
    worksheet["B10"] = "gifa-sync"

    worksheet.column_dimensions["A"].width = 24
    worksheet.column_dimensions["B"].width = 40


def _build_companies_sheet(
    worksheet,
    companies,
):
    """Build the companies worksheet."""

    headers = [
        "Company ID", "Company Name", "Country", "City", "Website", "Logo",
        "Created At", "Updated At",
    ]

    worksheet.append(headers)

    for company in companies:
        worksheet.append(
            [
                company["company_id"],
                company["company_name"],
                company["country"],
                company["city"],
                company["website"],
                company["logo"],
                company["created_at"],
                company["updated_at"],
            ]
        )

    _format_data_sheet(
        worksheet,
        table_name="SalesLeadsTable",
    )


def _build_records_sheet(
    worksheet,
    records,
):
    """Build the exhibition records worksheet."""

    headers = [
        "Company ID",
        "Company Name",
        "Country",
        "City",
        "Website",
        "Logo",
        "Company Created At",
        "Company Updated At",
        "Event",
        "Edition",
        "Event Code",
        "GIFA Exhibitor ID",
        "Exhibition SEO ID",
        "Hall",
        "Stand",
        "Location",
        "Premium",
        "Lead Status",
        "Tags",
        "Email",
        "Contact Person",
        "Telephone",
        "Product Categories",
        "Product Groups",
        "First Seen",
        "Last Seen",
        "Last Changed",
    ]

    worksheet.append(headers)

    for record in records:
        worksheet.append(
            [
                record["company_id"],
                record["company_name"],
                record["country"],
                record["city"],
                record["website"],
                record["logo"],
                record["company_created_at"],
                record["company_updated_at"],
                record["event_name"],
                record["edition"],
                record["event_code"],
                record["gifa_exhibitor_id"],
                record["exh_seo_id"],
                record["hall"],
                record["stand"],
                record["location"],
                bool(record["premium"]),
                _lead_status(record),
                record["tags_json"],
                record["email"],
                record["contact_person"],
                record["telephone"],
                record["product_categories_json"],
                record["product_groups_json"],
                record["first_seen_at"],
                record["last_seen_at"],
                record["changed_at"],
            ]
        )

    _format_data_sheet(
        worksheet,
        table_name="ParticipationHistoryTable",
    )


def _lead_status(record):
    if record["changed_at"] is None:
        return "Existing"
    if record["first_seen_at"] == record["changed_at"]:
        return "New this edition"
    if record["changed_at"] and record["changed_at"] != record["first_seen_at"]:
        return "Updated"
    return "Existing"


def _format_data_sheet(
    worksheet,
    table_name,
):
    """Apply common formatting to a data worksheet."""

    worksheet.freeze_panes = "A2"

    for cell in worksheet[1]:
        cell.font = Font(
            bold=True,
        )
        cell.alignment = Alignment(
            horizontal="center",
            vertical="center",
        )

    for row in worksheet.iter_rows():
        for cell in row:
            cell.alignment = Alignment(
                vertical="top",
            )

    if worksheet.max_row >= 2:
        table = Table(
            displayName=table_name,
            ref=worksheet.dimensions,
        )

        table_style = TableStyleInfo(
            name="TableStyleMedium2",
            showFirstColumn=False,
            showLastColumn=False,
            showRowStripes=True,
            showColumnStripes=False,
        )

        table.tableStyleInfo = table_style
        worksheet.add_table(table)

    for column_cells in worksheet.columns:
        max_length = 0
        column_letter = get_column_letter(
            column_cells[0].column
        )

        for cell in column_cells:
            value = cell.value

            if value is None:
                continue

            max_length = max(
                max_length,
                len(str(value)),
            )

        worksheet.column_dimensions[
            column_letter
        ].width = min(
            max(max_length + 2, 12),
            50,
        )


if __name__ == "__main__":
    output_file = Path("exports") / "GIFA_Sales_Database.xlsx"

    export_database_to_excel(output_file)

    print(
        f"Excel export created: {output_file}"
    )