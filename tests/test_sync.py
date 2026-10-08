import database

from scraper import sync_gifa_2023


def test_gifa_2023_sync_populates_database(tmp_path, monkeypatch):
    database_path = tmp_path / "test.db"

    monkeypatch.setattr(database, "DATABASE_PATH", database_path)
    monkeypatch.setattr(database, "DATA_DIR", tmp_path)

    result = sync_gifa_2023()

    assert result["total"] == 879
    assert result["created"] == 866
    assert result["updated"] == 13

    with database.get_connection() as connection:
        company_count = connection.execute(
            "SELECT COUNT(*) FROM companies"
        ).fetchone()[0]

        exhibition_count = connection.execute(
            "SELECT COUNT(*) FROM exhibition_companies"
        ).fetchone()[0]

        gifa_id_count = connection.execute(
            """
            SELECT COUNT(DISTINCT source_exhibitor_id)
            FROM exhibition_companies
            """
        ).fetchone()[0]

    assert company_count == 866
    assert exhibition_count == 879
    assert gifa_id_count == 879

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

    monkeypatch.setattr(
        scraper,
        "fetch_exhibitors_by_event",
        lambda event_label: records,
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