import database

import scraper


def test_configured_gifa_sync_uses_fixture_and_config_values(
    tmp_path,
    monkeypatch,
    gifa_2027_records,
):
    database_path = tmp_path / "test.db"

    monkeypatch.setattr(database, "DATABASE_PATH", database_path)
    monkeypatch.setattr(database, "DATA_DIR", tmp_path)
    config = scraper.EVENTS["GIFA"]
    monkeypatch.setattr(scraper, "DIRECTORY_LETTERS", "a")
    fetch_configs = []

    def fake_fetch_directory_letter(_letter, event_config=None):
        assert _letter == "a"
        fetch_configs.append(event_config)
        return gifa_2027_records

    def fake_report_run_results(run_id, changes, emit_summary=True):
        assert run_id
        assert isinstance(changes, list)
        assert emit_summary is True

    def fake_fetch_exhibitor_profile(exhibitor_id, event_config):
        assert event_config is config
        assert exhibitor_id in {"gifa2027.001", "gifa2027.002"}
        return {}

    monkeypatch.setattr(
        scraper,
        "fetch_directory_letter",
        fake_fetch_directory_letter,
    )
    monkeypatch.setattr(
        scraper,
        "fetch_exhibitor_profile",
        fake_fetch_exhibitor_profile,
    )
    monkeypatch.setattr(
        scraper,
        "_report_run_results",
        fake_report_run_results,
    )

    result = scraper.sync_configured_event("GIFA")

    assert result == {"total": 4, "created": 3, "updated": 1}
    assert fetch_configs == [config]
    with database.get_connection() as connection:
        companies = connection.execute(
            "SELECT COUNT(*) FROM companies"
        ).fetchone()[0]
        participations = connection.execute(
            "SELECT COUNT(*) FROM exhibition_companies"
        ).fetchone()[0]
        exhibition = connection.execute(
            "SELECT event_name, edition, event_code FROM exhibitions"
        ).fetchone()
        updated_location = connection.execute(
            """
            SELECT location
            FROM exhibition_companies
            WHERE source_exhibitor_id = 'gifa2027.001'
            """
        ).fetchone()[0]

    assert companies == 3
    assert participations == 3
    assert dict(exhibition) == {
        "event_name": "GIFA",
        "edition": 2027,
        "event_code": "GMTN2027.gifa",
    }
    assert updated_location == "Hall 15 / F25"


def test_historical_gifa_2023_sync_fails_without_archive():
    import pytest

    with pytest.raises(RuntimeError, match="archived data source"):
        scraper.sync_gifa_2023()

def test_sync_event_accepts_different_exhibitions(
    tmp_path,
    monkeypatch,
):
    import database
    import scraper

    database_path = tmp_path / "test.db"

    monkeypatch.setattr(database, "DATABASE_PATH", database_path)
    monkeypatch.setattr(database, "DATA_DIR", tmp_path)

    records = [
        {
            "type": "profile",
            "exh": "GMTN2027.TEST001",
            "exhSeoId": "SEO2027",
            "name": "Example Foundry GmbH",
            "country": "Germany",
            "city": "Düsseldorf",
            "location": "Hall 5 / B20",
            "premium": False,
            "tags": [],
            "eventIcons": [{"label": "GIFA 2027"}],
        }
    ]

    result = scraper.sync_event(
        event_name="GIFA",
        edition=2027,
        event_code="GMTN2027.gifa",
        exhibitors=records,
    )

    assert result["total"] == 1
    assert result["created"] == 1
    assert result["updated"] == 0

    with database.get_connection() as connection:
        company_count = connection.execute(
            "SELECT COUNT(*) FROM companies"
        ).fetchone()[0]

        exhibition_count = connection.execute(
            "SELECT COUNT(*) FROM exhibition_companies"
        ).fetchone()[0]

        exhibition = connection.execute(
            """
            SELECT event_name, edition, event_code
            FROM exhibitions
            """
        ).fetchone()

    assert company_count == 1
    assert exhibition_count == 1

    assert exhibition["event_name"] == "GIFA"
    assert exhibition["edition"] == 2027
    assert exhibition["event_code"] == "GMTN2027.gifa"

def test_filter_exhibitors_by_event():
    from scraper import filter_exhibitors_by_event

    records = [
        {
            "type": "profile",
            "name": "Company A",
            "eventIcons": [{"label": "GIFA 2023"}],
        },
        {
            "type": "profile",
            "name": "Company B",
            "eventIcons": [{"label": "GIFA 2027"}],
        },
        {
            "type": "trademark",
            "name": "Company C",
            "eventIcons": [{"label": "GIFA 2023"}],
        },
        {
            "type": "profile",
            "name": "Company D",
            "eventIcons": [
                {"label": "METEC 2023"},
                {"label": "GIFA 2023"},
            ],
        },
    ]

    result = filter_exhibitors_by_event(
        records,
        "GIFA 2023",
    )

    assert [record["name"] for record in result] == [
        "Company A",
        "Company D",
    ]

def test_fetch_exhibitors_by_event(monkeypatch):
    from scraper import fetch_exhibitors_by_event

    records_by_letter = {
        "a": [
            {
                "type": "profile",
                "name": "Company A",
                "eventIcons": [{"label": "GIFA 2027"}],
            },
            {
                "type": "profile",
                "name": "Company B",
                "eventIcons": [{"label": "METEC 2023"}],
            },
        ],
        "b": [
            {
                "type": "profile",
                "name": "Company C",
                "eventIcons": [
                    {"label": "GIFA 2027"},
                    {"label": "METEC 2023"},
                ],
            },
        ],
    }

    def fake_fetch_directory_letter(letter):
        return records_by_letter.get(letter, [])

    monkeypatch.setattr(
        "scraper.fetch_directory_letter",
        fake_fetch_directory_letter,
    )

    monkeypatch.setattr(
        "scraper.DIRECTORY_LETTERS",
        "ab",
    )

    result = fetch_exhibitors_by_event("GIFA 2027")

    assert [record["name"] for record in result] == [
        "Company A",
        "Company C",
    ]

def test_generic_event_sync_uses_generic_fetcher(
    tmp_path,
    monkeypatch,
):
    import database
    import scraper

    database_path = tmp_path / "test.db"

    monkeypatch.setattr(database, "DATABASE_PATH", database_path)
    monkeypatch.setattr(database, "DATA_DIR", tmp_path)

    records = [
        {
            "type": "profile",
            "exh": "GMTN2027.TEST001",
            "exhSeoId": "SEO2027",
            "name": "Example Foundry GmbH",
            "country": "Germany",
            "city": "Düsseldorf",
            "location": "Hall 5 / B20",
            "premium": False,
            "tags": [],
            "eventIcons": [{"label": "GIFA 2027"}],
        }
    ]

    def fake_fetch_exhibitors_by_event(event_label):
        assert event_label == "GIFA 2027"
        return records

    monkeypatch.setattr(
        scraper,
        "fetch_exhibitors_by_event",
        fake_fetch_exhibitors_by_event,
    )

    result = scraper.sync_event_from_api(
        event_name="GIFA",
        edition=2027,
        event_code="GMTN2027.gifa",
        event_label="GIFA 2027",
    )

    assert result == {
        "total": 1,
        "created": 1,
        "updated": 0,
    }

    with database.get_connection() as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM companies"
        ).fetchone()[0] == 1

        assert connection.execute(
            "SELECT COUNT(*) FROM exhibition_companies"
        ).fetchone()[0] == 1