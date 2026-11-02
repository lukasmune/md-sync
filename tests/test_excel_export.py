from openpyxl import Workbook
from openpyxl import load_workbook

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


def test_export_omits_logo_and_includes_normalized_categories(tmp_path, monkeypatch):
    import database
    from excel_export import export_exhibition_to_excel

    monkeypatch.setattr(database, "DATABASE_PATH", tmp_path / "test.db")
    monkeypatch.setattr(database, "DATA_DIR", tmp_path)
    database.initialize_database()
    exhibition_id = database.get_or_create_exhibition(
        "GIFA", 2023, "GMTN2023.gifa"
    )
    database.sync_exhibitor(
        {
            "exh": "EVENT.123",
            "name": "Example Foundry GmbH",
            "categories": [
                {
                    "id": "prod=event.01",
                    "label": "Casting",
                    "hierarchy": [
                        {"id": "01", "label": "Foundry equipment"}
                    ],
                }
            ],
        },
        exhibition_id,
    )

    output = tmp_path / "export.xlsx"
    export_exhibition_to_excel("GIFA", 2023, output)
    workbook = load_workbook(output)

    company_headers = [
        cell.value for cell in workbook["Company Master"][1]
    ]
    lead_headers = [
        cell.value for cell in workbook["Sales Leads"][1]
    ]
    assert "Logo" not in company_headers
    assert "Logo" not in lead_headers
    assert "Contact Person" not in company_headers
    assert "Contact Person" not in lead_headers
    assert "Tags" not in lead_headers
    values = {
        header: workbook["Sales Leads"].cell(row=2, column=index + 1).value
        for index, header in enumerate(lead_headers)
    }
    assert values["Product Categories"] == "Casting"
    assert values["Product Groups"] == "Foundry equipment"


def test_export_event_is_limited_to_selected_edition(tmp_path, monkeypatch):
    import database
    from excel_export import export_database_to_excel, export_event

    monkeypatch.setattr(database, "DATABASE_PATH", tmp_path / "test.db")
    monkeypatch.setattr(database, "DATA_DIR", tmp_path)
    database.initialize_database()

    gifa_id = database.get_or_create_exhibition(
        "GIFA", 2023, "GMTN2023.gifa"
    )
    metec_id = database.get_or_create_exhibition(
        "METEC", 2023, "GMTN2023.metec"
    )
    record = {
        "exh": "SHARED.123",
        "name": "Shared Foundry GmbH",
        "country": "Germany",
        "city": "Düsseldorf",
        "categories": [
            {
                "id": "gifa.category",
                "label": "GIFA Casting",
                "hierarchy": [{"id": "gifa.group", "label": "GIFA Group"}],
            }
        ],
    }
    database.sync_exhibitor(record, gifa_id)
    record["categories"] = [
        {
            "id": "metec.category",
            "label": "METEC Steel",
            "hierarchy": [{"id": "metec.group", "label": "METEC Group"}],
        }
    ]
    database.sync_exhibitor(record, metec_id)

    gifa_path = export_event("GIFA", 2023, tmp_path)
    metec_path = export_event("METEC", 2023, tmp_path)
    assert gifa_path.name == "GIFA_2023.xlsx"
    assert metec_path.name == "METEC_2023.xlsx"

    def read_leads(path):
        workbook = load_workbook(path, read_only=True)
        sheet = workbook["Sales Leads"]
        headers = [cell.value for cell in next(sheet.iter_rows())]
        rows = [
            dict(zip(headers, row))
            for row in sheet.iter_rows(min_row=2, values_only=True)
        ]
        workbook.close()
        return rows

    gifa_rows = read_leads(gifa_path)
    metec_rows = read_leads(metec_path)
    assert len(gifa_rows) == 1
    assert len(metec_rows) == 1
    assert gifa_rows[0]["Event"] == "GIFA"
    assert metec_rows[0]["Event"] == "METEC"
    assert gifa_rows[0]["Product Categories"] == "GIFA Casting"
    assert metec_rows[0]["Product Categories"] == "METEC Steel"
    assert "Logo" not in gifa_rows[0]

    all_paths = export_database_to_excel(tmp_path / "all-editions.xlsx")
    assert {path.name for path in all_paths} == {
        "GIFA_2023.xlsx",
        "METEC_2023.xlsx",
    }


def test_non_gifa_exports_mark_top_level_category_assignments(
    tmp_path, monkeypatch
):
    import database
    from excel_export import export_event

    monkeypatch.setattr(database, "DATABASE_PATH", tmp_path / "test.db")
    monkeypatch.setattr(database, "DATA_DIR", tmp_path)
    database.initialize_database()

    events = ("METEC", "NEWCAST", "THERMPROCESS")
    for event in events:
        exhibition_id = database.get_or_create_exhibition(
            event, 2023, f"GMTN2023.{event.lower()}"
        )
        for suffix, root_label in (
            ("A", "Production equipment"),
            ("B", "Services"),
        ):
            database.sync_exhibitor(
                {
                    "exh": f"{event}-{suffix}",
                    "name": f"{event} Company {suffix}",
                    "categories": [
                        {
                            "id": f"{event}-category-{suffix}",
                            "label": f"Category {suffix}",
                            "hierarchy": [
                                {
                                    "id": f"{event}-root-{suffix}",
                                    "label": root_label,
                                },
                                {
                                    "id": f"{event}-child-{suffix}",
                                    "label": f"Child {suffix}",
                                },
                            ],
                        }
                    ],
                },
                exhibition_id,
            )

    for event in events:
        path = export_event(event, 2023, tmp_path)
        workbook = load_workbook(path, read_only=True)
        sheet = workbook["Sales Leads"]
        headers = [cell.value for cell in next(sheet.iter_rows())]
        rows = [
            dict(zip(headers, values))
            for values in sheet.iter_rows(min_row=2, values_only=True)
        ]

        assert headers[-3:] == [
            "Product Assignment Source",
            "1. Production equipment",
            "2. Services",
        ]
        assert len(rows) == 2
        production_row = next(
            row for row in rows
            if row["Exhibitor ID"].endswith("-A")
        )
        services_row = next(
            row for row in rows
            if row["Exhibitor ID"].endswith("-B")
        )
        assert production_row["1. Production equipment"] == "x"
        assert production_row["Product Assignment Source"] == (
            "Current edition source"
        )
        assert production_row["2. Services"] in ("", None)
        assert services_row["1. Production equipment"] in ("", None)
        assert services_row["2. Services"] == "x"
        assert services_row["Product Assignment Source"] == (
            "Current edition source"
        )
        workbook.close()

        next_edition_id = database.get_or_create_exhibition(
            event, 2027, f"GMTN2027.{event.lower()}"
        )
        database.sync_exhibitor(
            {
                "exh": f"{event}-2027",
                "name": f"{event} Company A",
            },
            next_edition_id,
        )
        database.sync_exhibitor(
            {
                "exh": f"{event}-2027-new",
                "name": f"{event} New Company",
            },
            next_edition_id,
        )
        next_path = export_event(event, 2027, tmp_path)
        next_workbook = load_workbook(next_path, read_only=True)
        next_sheet = next_workbook["Sales Leads"]
        next_headers = [cell.value for cell in next(next_sheet.iter_rows())]
        next_rows = [
            dict(zip(next_headers, values))
            for values in next_sheet.iter_rows(min_row=2, values_only=True)
        ]
        assert next_headers[-3:] == [
            "Product Assignment Source",
            "1. Production equipment",
            "2. Services",
        ]
        carried_row = next(
            row for row in next_rows
            if row["Exhibitor ID"].endswith("-2027")
        )
        new_row = next(
            row for row in next_rows
            if row["Exhibitor ID"].endswith("-2027-new")
        )
        assert carried_row["1. Production equipment"] == "x"
        assert carried_row["2. Services"] in ("", None)
        assert carried_row["Product Assignment Source"] == (
            "2023 historical carry-forward"
        )
        assert new_row["1. Production equipment"] in ("", None)
        assert new_row["2. Services"] in ("", None)
        assert new_row["Product Assignment Source"] in ("", None)
        next_workbook.close()