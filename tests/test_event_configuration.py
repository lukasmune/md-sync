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
    expected = {
        "GIFA": ("GIFA 2027", "GMTN2027.gifa"),
        "METEC": ("METEC 2027", "GMTN2027.metec"),
        "THERMPROCESS": ("THERMPROCESS 2027", "GMTN2027.thermpro"),
        "NEWCAST": ("NEWCAST 2027", "GMTN2027.newcast"),
    }
    for event_name, (label, event_code) in expected.items():
        event = scraper.EVENTS[event_name]
        assert event["edition"] == 2027
        assert event["event_label"] == label
        assert event["event_code"] == event_code


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


def test_each_fair_filters_only_its_event_associations(
    fair_associations_2027,
):
    expected_ids = {
        "GIFA": {"gifa-only", "shared-gifa-metec"},
        "METEC": {"metec-only", "shared-gifa-metec"},
        "THERMPROCESS": {"thermprocess-only"},
        "NEWCAST": {"newcast-only"},
    }

    for event_name, config in scraper.EVENTS.items():
        filtered = scraper.filter_exhibitors_by_event(
            fair_associations_2027,
            config["event_label"],
        )
        assert {record["exh"] for record in filtered} == expected_ids[event_name]


def test_all_configured_events_sync_only_their_source_associations(
    tmp_path,
    monkeypatch,
    fair_associations_2027,
):
    monkeypatch.setattr(database, "DATABASE_PATH", tmp_path / "test.db")
    monkeypatch.setattr(database, "DATA_DIR", tmp_path)
    monkeypatch.setattr(scraper, "DIRECTORY_LETTERS", "a")
    request_configs = []
    report_modes = []

    def fake_fetch_directory_letter(letter, event_config):
        assert letter == "a"
        request_configs.append(event_config)
        return fair_associations_2027

    def fake_fetch_exhibitor_profile(exhibitor_id, event_config):
        assert exhibitor_id
        assert event_config in scraper.EVENTS.values()
        return {}

    def fake_report_run_results(run_id, changes, emit_summary=True):
        assert run_id
        assert isinstance(changes, list)
        report_modes.append(emit_summary)

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

    results = scraper.sync_configured_events()

    assert [result["total"] for result in results] == [2, 2, 1, 1]
    assert request_configs == list(scraper.EVENTS.values())
    assert report_modes == [True]
    with database.get_connection() as connection:
        exhibitions = connection.execute(
            """
            SELECT event_name, edition, event_code
            FROM exhibitions
            ORDER BY event_name
            """
        ).fetchall()
        participations = connection.execute(
            """
            SELECT e.event_name, ec.source_exhibitor_id
            FROM exhibition_companies ec
            JOIN exhibitions e ON e.id = ec.exhibition_id
            ORDER BY e.event_name, ec.source_exhibitor_id
            """
        ).fetchall()
        company_count = connection.execute(
            "SELECT COUNT(*) FROM companies"
        ).fetchone()[0]

    assert {
        (row["event_name"], row["edition"], row["event_code"])
        for row in exhibitions
    } == {
        ("GIFA", 2027, "GMTN2027.gifa"),
        ("METEC", 2027, "GMTN2027.metec"),
        ("THERMPROCESS", 2027, "GMTN2027.thermpro"),
        ("NEWCAST", 2027, "GMTN2027.newcast"),
    }
    assert {
        (row["event_name"], row["source_exhibitor_id"])
        for row in participations
    } == {
        ("GIFA", "gifa-only"),
        ("GIFA", "shared-gifa-metec"),
        ("METEC", "metec-only"),
        ("METEC", "shared-gifa-metec"),
        ("THERMPROCESS", "thermprocess-only"),
        ("NEWCAST", "newcast-only"),
    }
    assert company_count == 5


def test_directory_request_uses_configured_base_url_and_domain(monkeypatch):
    captured = []

    class Response:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return []

    def fake_get(url, headers, timeout):
        captured.append((url, headers, timeout))
        return Response()

    monkeypatch.setattr(scraper.requests, "get", fake_get)

    for config in scraper.EVENTS.values():
        assert scraper.fetch_directory_letter("A", config) == []

    assert len(captured) == len(scraper.EVENTS)
    for config, (url, headers, timeout) in zip(
        scraper.EVENTS.values(),
        captured,
    ):
        assert url == f"{config['base_url']}/a"
        assert headers["X-Vis-Domain"] == config["domain"]
        assert timeout == scraper.REQUEST_TIMEOUT


def test_sync_configured_event_uses_one_generic_pipeline(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DATABASE_PATH", tmp_path / "test.db")
    monkeypatch.setattr(database, "DATA_DIR", tmp_path)

    def no_op_report(run_id, changes, emit_summary=True):
        assert run_id
        assert isinstance(changes, list)
        assert emit_summary is True

    monkeypatch.setattr(
        scraper,
        "_report_run_results",
        no_op_report,
    )

    config = scraper.EVENTS["METEC"]

    def fake_fetch_exhibitors_by_event(label, event_config=None):
        assert label == config["event_label"]
        assert event_config is config
        return [
            {
                "type": "profile",
                "exh": "GMTN2027.TEST",
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
            "SELECT event_name, edition, event_code FROM exhibitions"
        ).fetchone()
    assert exhibition["event_name"] == "METEC"
    assert exhibition["edition"] == 2027
    assert exhibition["event_code"] == "GMTN2027.metec"
