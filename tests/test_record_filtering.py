import pytest

import scraper


def test_configured_gifa_fetch_filters_and_transforms_fixture_records(
    gifa_2027_records,
    monkeypatch,
):
    config = scraper.EVENTS["GIFA"]
    monkeypatch.setattr(scraper, "DIRECTORY_LETTERS", "a")

    def fake_fetch_directory_letter(letter, event_config=None):
        assert letter == "a"
        assert event_config is config
        return gifa_2027_records

    monkeypatch.setattr(
        scraper,
        "fetch_directory_letter",
        fake_fetch_directory_letter,
    )
    profile_responses = {
        "gifa2027.001": {
            "email": "contact@example.com",
            "phone": {"phone": "+49 211 123"},
            "links": [{"link": "https://example.com"}],
            "categories": [{"id": "prod.01", "label": "Casting"}],
            "profileAddress": {"city": "Düsseldorf", "country": "Germany"},
            "name": "Example Foundry GmbH",
        },
        "gifa2027.002": {"phone": None, "links": None},
    }
    def fake_fetch_exhibitor_profile(exhibitor_id, event_config):
        assert event_config is config
        return profile_responses[exhibitor_id]

    monkeypatch.setattr(
        scraper,
        "fetch_exhibitor_profile",
        fake_fetch_exhibitor_profile,
    )

    exhibitors = scraper.fetch_exhibitors_by_event(
        config["event_label"],
        event_config=config,
    )

    assert [record["exh"] for record in exhibitors] == [
        "gifa2027.001",
        "gifa2027.co1",
        "gifa2027.001",
        "gifa2027.002",
    ]
    direct = exhibitors[0]
    assert direct["exhibitor_role"] == "direct"
    assert direct["email"] == "contact@example.com"
    assert direct["telephone"] == "+49 211 123"
    assert direct["website"] == "https://example.com"
    assert direct["categories"] == [{"id": "prod.01", "label": "Casting"}]
    assert direct["city"] == "Düsseldorf"
    assert direct["name"] == "Example Foundry GmbH"

    co_exhibitor = exhibitors[1]
    assert co_exhibitor["exhibitor_role"] == "co-exhibitor"
    assert co_exhibitor["parent_source_exhibitor_id"] == "gifa2027.001"
    optional_record = exhibitors[-1]
    assert optional_record["exh"] == "gifa2027.002"
    assert optional_record["telephone"] is None
    assert optional_record["website"] is None
    assert optional_record["categories"] == []


def test_historical_gifa_2023_fetch_fails_explicitly():
    with pytest.raises(RuntimeError, match="archived data source"):
        scraper.fetch_gifa_2023_exhibitors()