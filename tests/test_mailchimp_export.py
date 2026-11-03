import pytest
from openpyxl import load_workbook

import database
import mailchimp_export
import scraper


def _record(exh, name, email, hall="Hall 1", label="METEC 2027", **values):
    record = {
        "type": "profile",
        "exh": exh,
        "exhSeoId": "SEO-" + exh,
        "name": name,
        "country": "Germany",
        "city": "Berlin",
        "location": f"{hall} / A1",
        "premium": False,
        "tags": [],
        "eventIcons": [{"label": label}],
        "email": email,
    }
    record.update(values)
    return record


@pytest.fixture
def mailchimp_db(tmp_path, monkeypatch):
    database.DATABASE_PATH = tmp_path / "sync.db"
    database.DATA_DIR = tmp_path
    monkeypatch.setattr(
        scraper, "export_change_report", lambda *a, **k: None
    )
    return tmp_path / "mailchimp"


def _sync(*records):
    scraper.sync_event("METEC", 2027, "METEC2027", list(records))


def _contacts(path):
    sheet = load_workbook(path)["Info Mailchimp"]
    return {row[0]: row for row in sheet.iter_rows(min_row=2, values_only=True)}


def test_sheets_and_headers_match_sample(mailchimp_db):
    _sync(_record("E1", "Acme GmbH", "Info@Acme.de"))
    path = mailchimp_export.export_mailchimp_list(mailchimp_db)
    workbook = load_workbook(path)

    assert workbook.sheetnames == ["Info INTERN", "Info Mailchimp"]
    assert [c.value for c in workbook["Info Mailchimp"][1]] == [
        "Email", "Company", "Country", "City", "Tag Exhibition", "Tag Hall",
    ]
    assert workbook["Info INTERN"]["M2"].value is not None
    assert _contacts(path)["info@acme.de"][4] == "METEC 2027"
    assert _contacts(path)["info@acme.de"][2] == "DE"
    assert workbook["Info Mailchimp"].auto_filter.ref == "A1:F1"
    assert workbook["Info INTERN"].auto_filter.ref == "A1:M1"


def test_shared_email_is_merged_and_missing_email_skipped(mailchimp_db):
    _sync(
        _record("E1", "Acme GmbH", "info@group.de", hall="Hall 1"),
        _record("E2", "Beta GmbH", "INFO@group.de", hall="Hall 2"),
        _record("E3", "NoMail GmbH", None),
        _record("E4", "Bad GmbH", "not-an-email"),
    )
    contacts = _contacts(mailchimp_export.export_mailchimp_list(mailchimp_db))

    assert list(contacts) == ["info@group.de"]
    row = contacts["info@group.de"]
    assert row[1] == "Acme GmbH / Beta GmbH"
    assert row[5] == "Hall 1, Hall 2"


def test_contact_is_never_exported_twice(mailchimp_db):
    _sync(_record("E1", "Acme GmbH", "info@acme.de"))
    assert mailchimp_export.export_mailchimp_list(mailchimp_db) is not None
    assert mailchimp_export.export_mailchimp_list(mailchimp_db) is None

    _sync(
        _record("E1", "Acme GmbH", "info@acme.de"),
        _record("E2", "Beta GmbH", "info@beta.de"),
    )
    path = mailchimp_export.export_mailchimp_list(mailchimp_db)
    assert list(_contacts(path)) == ["info@beta.de"]


def test_baseline_marks_existing_contacts_without_file(mailchimp_db):
    _sync(_record("E1", "Acme GmbH", "info@acme.de"))

    assert mailchimp_export.mark_current_contacts_as_exported() == 1
    assert mailchimp_export.export_mailchimp_list(mailchimp_db) is None
    assert not mailchimp_db.exists()
