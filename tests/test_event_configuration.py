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
        assert str(event["edition"]) in event["event_label"]
        assert event["event_code"].startswith(f"GMTN{event['edition']}.")
    gifa = scraper.EVENTS["GIFA"]
    assert gifa["edition"] == 2027
    assert gifa["event_label"] == "GIFA 2027"
    assert gifa["event_code"] == "GMTN2027.gifa"


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


def test_directory_request_uses_configured_base_url_and_domain(monkeypatch):
    config = scraper.EVENTS["GIFA"]
    captured = {}

    class Response:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return []

    def fake_get(url, headers, timeout):
        captured.update(url=url, headers=headers, timeout=timeout)
        return Response()

    monkeypatch.setattr(scraper.requests, "get", fake_get)

    assert scraper.fetch_directory_letter("A", config) == []
    assert captured["url"] == f"{config['base_url']}/a"
    assert captured["headers"]["X-Vis-Domain"] == config["domain"]


def test_sync_configured_event_uses_one_generic_pipeline(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DATABASE_PATH", tmp_path / "test.db")
    monkeypatch.setattr(database, "DATA_DIR", tmp_path)

    config = scraper.EVENTS["METEC"]

    def fake_fetch_exhibitors_by_event(label, event_config=None):
        assert label == config["event_label"]
        assert event_config is config
        return [
            {
                "type": "profile",
                "exh": "GMTN2023.TEST",
                "exhSeoId": "SEO",
                "name": "Example Foundry GmbH",
                "country": "Germany",
                "city": "Düsseldorf",
                "eventIcons": [{"label": label}],
            }
        ]

    monkeypatch.setattr(
        scraper,
        "fetch_exhibitors_by_event",
        fake_fetch_exhibitors_by_event,
    )

    result = scraper.sync_configured_event("METEC")

    assert result["total"] == 1
    with database.get_connection() as connection:
        exhibition = connection.execute(
            "SELECT event_name, event_code FROM exhibitions"
        ).fetchone()
    assert exhibition["event_name"] == "METEC"
    assert exhibition["event_code"] == "GMTN2023.metec"
