import database
import scraper


def test_all_supported_events_have_complete_configuration():
    assert set(scraper.EVENTS) == {
        "GIFA",
        "METEC",
        "THERMPROCESS",
        "NEWCAST",
    }
    for event in scraper.EVENTS.values():
        assert event["base_url"].endswith("/directory")
        assert event["domain"]
        assert event["event_code"]
        assert event["event_label"]
        assert event["edition"] == 2023


def test_each_event_label_filters_profile_records():
    for event in scraper.EVENTS.values():
        records = [
            {
                "type": "profile",
                "name": "Match",
                "eventIcons": [{"label": event["event_label"]}],
            },
            {
                "type": "profile",
                "name": "Other event",
                "eventIcons": [{"label": "Unrelated 2023"}],
            },
        ]
        assert [
            record["name"]
            for record in scraper.filter_exhibitors_by_event(
                records, event["event_label"]
            )
        ] == ["Match"]


def test_sync_configured_event_uses_one_generic_pipeline(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DATABASE_PATH", tmp_path / "test.db")
    monkeypatch.setattr(database, "DATA_DIR", tmp_path)
    monkeypatch.setattr(
        scraper,
        "fetch_exhibitors_by_event",
        lambda label, event_config=None: [
            {
                "type": "profile",
                "exh": "GMTN2023.TEST",
                "exhSeoId": "SEO",
                "name": "Example Foundry GmbH",
                "country": "Germany",
                "city": "Düsseldorf",
                "eventIcons": [{"label": label}],
            }
        ],
    )

    result = scraper.sync_configured_event("METEC")

    assert result["total"] == 1
    with database.get_connection() as connection:
        exhibition = connection.execute(
            "SELECT event_name, event_code FROM exhibitions"
        ).fetchone()
    assert exhibition["event_name"] == "METEC"
    assert exhibition["event_code"] == "GMTN2023.metec"
