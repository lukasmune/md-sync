import pytest
from openpyxl import load_workbook

import database
import full_list_export
import mailchimp_export
import scraper


def _record(exh, name, email, label, country="Germany"):
    return {
        "type": "profile",
        "exh": exh,
        "exhSeoId": "SEO-" + exh,
        "name": name,
        "country": country,
        "city": "Berlin",
        "location": "Hall 1 / A1",
        "premium": False,
        "tags": [],
        "eventIcons": [{"label": label}],
        "email": email,
    }


@pytest.fixture
def two_fairs(tmp_path, monkeypatch):
    database.DATABASE_PATH = tmp_path / "sync.db"
    database.DATA_DIR = tmp_path
    monkeypatch.setattr(scraper, "export_change_report", lambda *a, **k: None)
    scraper.sync_event("GIFA", 2027, "GIFA2027", [
        _record("G1", "Acme GmbH", "info@acme.de", "GIFA 2027", "Germany"),
        _record("G2", "NoMail GmbH", None, "GIFA 2027"),
    ])
    scraper.sync_event("METEC", 2027, "METEC2027", [
        _record("M1", "Acme GmbH", "info@acme.de", "METEC 2027"),
    ])
    scraper.sync_event("GIFA", 2023, "GIFA2023", [
        _record("O1", "Old GmbH", "old@example.com", "GIFA 2023"),
    ])
    return tmp_path / "all_editions"


def _rows(sheet):
    values = list(sheet.iter_rows(values_only=True))
    return [dict(zip(values[0], row)) for row in values[1:]]


def test_full_list_contains_current_editions_of_all_fairs(two_fairs):
    path = full_list_export.export_full_list(two_fairs)
    workbook = load_workbook(path)

    assert workbook.sheetnames == ["Summary", "All Exhibitors", "Companies"]
    exhibitors = _rows(workbook["All Exhibitors"])
    assert sorted((r["Company Name"], r["Exhibition"]) for r in exhibitors) == [
        ("Acme GmbH", "GIFA"), ("Acme GmbH", "METEC"), ("NoMail GmbH", "GIFA"),
    ]
    assert {r["Country Code"] for r in exhibitors} == {"DE"}
    assert all(r["Edition"] == 2027 for r in exhibitors)

    companies = {r["Company Name"]: r for r in _rows(workbook["Companies"])}
    assert companies["Acme GmbH"]["Exhibitions"] == "GIFA 2027, METEC 2027"
    assert len(companies) == 2


def test_full_list_does_not_change_mailchimp_history(two_fairs):
    before = mailchimp_export.pending_contacts()
    full_list_export.export_full_list(two_fairs)
    full_list_export.export_full_list(two_fairs)

    assert list(mailchimp_export.pending_contacts()) == list(before)
    with mailchimp_export._connect() as connection:
        count = connection.execute(
            "SELECT COUNT(*) FROM mailchimp_exported_emails"
        ).fetchone()[0]
    assert count == 0
    assert len(list(two_fairs.glob("all_editions_*.xlsx"))) == 2
