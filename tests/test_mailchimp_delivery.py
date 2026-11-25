import pytest

import database
import mailchimp_delivery
import mailchimp_export
import scraper


def _record(exh, name, email):
    return {
        "type": "profile", "exh": exh, "exhSeoId": "SEO-" + exh,
        "name": name, "country": "Germany", "city": "Berlin",
        "location": "Hall 1 / A1", "premium": False, "tags": [],
        "eventIcons": [{"label": "METEC 2027"}], "email": email,
    }


@pytest.fixture
def setup(tmp_path, monkeypatch):
    database.DATABASE_PATH = tmp_path / "sync.db"
    database.DATA_DIR = tmp_path
    monkeypatch.setattr(scraper, "export_change_report", lambda *a, **k: None)
    scraper.sync_event(
        "METEC", 2027, "METEC2027", [_record("E1", "Acme", "a@acme.de")]
    )
    return tmp_path / "local", tmp_path / "share"


def test_folder_and_file_names_follow_team_layout(tmp_path):
    source = tmp_path / "mailchimp_2026-11-25_090917.xlsx"
    assert mailchimp_delivery.delivery_names(source) == (
        "Export 25112026", "Export_2026-11-25_090917.xlsx",
    )


def test_deliver_copies_into_dated_folder_and_keeps_original(tmp_path):
    share = tmp_path / "share"
    share.mkdir()
    source = tmp_path / "mailchimp_2026-11-25_090917.xlsx"
    source.write_bytes(b"data")

    target = mailchimp_delivery.deliver_export(source, share)

    assert target == share / "Export 25112026" / "Export_2026-11-25_090917.xlsx"
    assert target.read_bytes() == b"data"
    assert source.exists()
    assert not list(target.parent.glob("*.part"))
    with pytest.raises(FileExistsError):
        mailchimp_delivery.deliver_export(source, share)


def test_second_run_same_day_goes_into_existing_folder(tmp_path):
    share = tmp_path / "share"
    share.mkdir()
    for stamp in ("090917", "151500"):
        source = tmp_path / f"mailchimp_2026-11-25_{stamp}.xlsx"
        source.write_bytes(b"x")
        mailchimp_delivery.deliver_export(source, share)

    assert len(list((share / "Export 25112026").glob("*.xlsx"))) == 2


def test_publish_exports_and_delivers(setup, capsys):
    local, share = setup
    share.mkdir()

    assert mailchimp_delivery.publish(local, share) == 0

    delivered = list(share.glob("Export */Export_*.xlsx"))
    assert len(delivered) == 1
    assert len(list(local.glob("mailchimp_*.xlsx"))) == 1
    assert mailchimp_delivery.publish(local, share) == 0
    assert "No new Mailchimp contacts" in capsys.readouterr().out
    assert len(list(share.glob("Export */Export_*.xlsx"))) == 1


def test_unreachable_drive_keeps_local_file_and_retry_delivers(setup, capsys):
    local, share = setup

    assert mailchimp_delivery.publish(local, share) == 1
    assert "Delivery FAILED" in capsys.readouterr().out
    assert len(list(local.glob("mailchimp_*.xlsx"))) == 1
    assert mailchimp_export.pending_contacts() == {}

    share.mkdir()
    assert mailchimp_delivery.deliver_latest(local, share) == 0
    assert len(list(share.glob("Export */Export_*.xlsx"))) == 1


def test_latest_export_ignores_rebuilt_files(tmp_path):
    (tmp_path / "mailchimp_2026-11-18_091251.xlsx").write_bytes(b"a")
    (tmp_path / "mailchimp_rebuilt_2026-11-30_100000.xlsx").write_bytes(b"b")

    assert mailchimp_delivery.latest_export(tmp_path).name == (
        "mailchimp_2026-11-18_091251.xlsx"
    )
