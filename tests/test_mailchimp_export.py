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

    assert workbook.sheetnames == ["Info INTERNAL", "Info Mailchimp"]
    assert [c.value for c in workbook["Info Mailchimp"][1]] == [
        "Email", "Company", "Country", "City", "Telephone", "Tag Exhibition",
        "Tag Hall",
    ]
    assert workbook["Info INTERNAL"]["M2"].value is not None
    assert _contacts(path)["info@acme.de"][5] == "METEC 2027"
    assert _contacts(path)["info@acme.de"][2] == "Germany"
    assert workbook["Info Mailchimp"].auto_filter.ref == "A1:G1"
    assert workbook["Info INTERNAL"].auto_filter.ref == "A1:M1"


def test_mailchimp_sheet_uses_mailchimp_country_spelling(mailchimp_db):
    _sync(_record("E1", "Acme Inc", "info@acme.com", country="USA"))
    path = mailchimp_export.export_mailchimp_list(mailchimp_db)
    workbook = load_workbook(path)

    assert _contacts(path)["info@acme.com"][2] == "United States of America"
    assert workbook["Info INTERNAL"]["B2"].value == "United States of America"


def test_shared_email_is_merged_and_missing_email_skipped(mailchimp_db):
    _sync(
        _record("E1", "Acme GmbH", "info@group.de", hall="Hall 1"),
        _record(
            "E2", "Beta GmbH", "INFO@group.de", hall="Hall 2",
            telephone="+49 211 123",
        ),
        _record("E3", "NoMail GmbH", None),
        _record("E4", "Bad GmbH", "not-an-email"),
    )
    contacts = _contacts(mailchimp_export.export_mailchimp_list(mailchimp_db))

    assert list(contacts) == ["info@group.de"]
    row = contacts["info@group.de"]
    assert row[1] == "Acme GmbH / Beta GmbH"
    assert row[6] == "Hall 1, Hall 2"
    assert row[4] == "+49 211 123"


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


def test_failed_mailchimp_workbook_leaves_contacts_pending(mailchimp_db, monkeypatch):
    _sync(_record("E1", "Acme GmbH", "info@acme.de"))

    def fail_write(*args, **kwargs):
        raise OSError("workbook write failed")

    monkeypatch.setattr(mailchimp_export, "_write_workbook", fail_write)
    with pytest.raises(OSError, match="workbook write failed"):
        mailchimp_export.export_mailchimp_list(mailchimp_db)
    assert list(mailchimp_export.pending_contacts()) == ["info@acme.de"]


def test_rebuild_recreates_last_export_without_changing_log(mailchimp_db):
    assert mailchimp_export.rebuild_mailchimp_list(
        output_dir=mailchimp_db
    ) is None
    _sync(_record("E1", "Acme GmbH", "info@acme.de"))
    mailchimp_export.export_mailchimp_list(mailchimp_db)
    _sync(
        _record("E1", "Acme GmbH", "info@acme.de"),
        _record("E2", "Beta GmbH", "info@beta.de"),
    )

    path = mailchimp_export.rebuild_mailchimp_list(output_dir=mailchimp_db)

    assert list(_contacts(path)) == ["info@acme.de"]
    assert list(mailchimp_export.pending_contacts()) == ["info@beta.de"]


def test_baseline_marks_existing_contacts_without_file(mailchimp_db):
    _sync(_record("E1", "Acme GmbH", "info@acme.de"))

    assert mailchimp_export.mark_current_contacts_as_exported() == 1
    assert mailchimp_export.export_mailchimp_list(mailchimp_db) is None
    assert not mailchimp_db.exists()


def test_baseline_reports_previously_exported_new_and_unusable(mailchimp_db):
    _sync(_record("E1", "Acme GmbH", "info@acme.de"))
    export = mailchimp_export.export_mailchimp_list(mailchimp_db)
    _sync(
        _record("E1", "Acme GmbH", "info@acme.de"),
        _record("E2", "Beta GmbH", "info@beta.de"),
        _record("E3", "Shared GmbH", "INFO@beta.de"),
        _record("E4", "NoMail GmbH", None),
        _record("E5", "Bad GmbH", "not-an-email"),
    )

    result = mailchimp_export.baseline_current_contacts()
    assert result == (2, 1, 1, 2)
    assert mailchimp_export.pending_contacts() == {}
    with mailchimp_export._connect() as connection:
        sources = dict(connection.execute(
            "SELECT email, source_file FROM mailchimp_exported_emails"
        ))
    assert sources == {
        "info@acme.de": export.name,
        "info@beta.de": "baseline (not exported)",
    }

    assert mailchimp_export.baseline_current_contacts() == (2, 2, 0, 2)


def test_baseline_terminal_explains_zero_and_empty_editions(mailchimp_db, capsys):
    mailchimp_export.print_baseline_result()
    output = capsys.readouterr().out
    assert "Current-edition distinct usable addresses: 0" in output
    assert "No usable email addresses found" in output

    _sync(_record("E1", "Acme GmbH", "info@acme.de"))
    mailchimp_export.print_baseline_result()
    capsys.readouterr()
    mailchimp_export.print_baseline_result()
    output = capsys.readouterr().out
    assert "Already recorded by previous exports or baselines: 1" in output
    assert "Newly marked by this baseline: 0" in output
    assert "not verified against the Mailchimp audience" in output


def test_recover_baselined_run_combines_new_fairs_without_reexporting(
    mailchimp_db, monkeypatch
):
    _sync(_record("E0", "Existing GmbH", "existing@example.com"))
    mailchimp_export.export_mailchimp_list(mailchimp_db)
    records = {
        "GIFA 2027": [
            _record("G1", "New GmbH", "new@example.com"),
            _record("G2", "Existing GmbH", "existing@example.com"),
        ],
        "METEC 2027": [
            _record("M1", "New GmbH", "new@example.com"),
            _record("M2", "Other GmbH", "other@example.com"),
            _record("M3", "Missing GmbH", None),
        ],
    }
    monkeypatch.setattr(
        scraper, "fetch_exhibitors_by_event",
        lambda label, event_config=None: records[label],
    )
    scraper.sync_configured_events(["GIFA", "METEC"])
    with mailchimp_export._connect() as connection:
        run_id = connection.execute(
            "SELECT run_id FROM change_history ORDER BY id DESC LIMIT 1"
        ).fetchone()["run_id"]
    assert mailchimp_export.baseline_current_contacts().newly_recorded == 2
    with mailchimp_export._connect() as connection:
        baseline_time = connection.execute(
            "SELECT exported_at FROM mailchimp_exported_emails "
            "WHERE source_file = 'baseline (not exported)' LIMIT 1"
        ).fetchone()["exported_at"]
        before = list(connection.execute(
            "SELECT email, exported_at, source_file FROM mailchimp_exported_emails "
            "ORDER BY email"
        ))

    path = mailchimp_export.recover_baselined_run(
        run_id, baseline_time, output_dir=mailchimp_db
    )
    second_path = mailchimp_export.recover_baselined_run(
        run_id, baseline_time, output_dir=mailchimp_db
    )
    assert path != second_path
    contacts = _contacts(path)
    assert set(contacts) == {"new@example.com", "other@example.com"}
    assert "GIFA 2027" in contacts["new@example.com"][5]
    assert "METEC 2027" in contacts["new@example.com"][5]
    with mailchimp_export._connect() as connection:
        after = list(connection.execute(
            "SELECT email, exported_at, source_file FROM mailchimp_exported_emails "
            "ORDER BY email"
        ))
    assert [tuple(row) for row in before] == [tuple(row) for row in after]
    with pytest.raises(ValueError, match="No matching baselined contacts"):
        mailchimp_export.recover_baselined_run(
            run_id, "wrong timestamp", output_dir=mailchimp_db
        )
