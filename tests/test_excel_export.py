from openpyxl import Workbook

from excel_export import _format_data_sheet


def test_table_export_uses_table_filter_only():
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.append(["Company ID", "Company Name"])
    worksheet.append([1, "Example Foundry GmbH"])

    _format_data_sheet(
        worksheet,
        table_name="CompaniesTable",
    )

    assert worksheet.auto_filter.ref is None
    assert worksheet.tables["CompaniesTable"].ref == "A1:B2"