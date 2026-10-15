import pytest

import scraper


@pytest.mark.live
@pytest.mark.parametrize(
    "event_name",
    ["GIFA", "METEC", "THERMPROCESS", "NEWCAST"],
)
def test_live_directory_api_returns_records_with_expected_shape(event_name):
    config = scraper.EVENTS[event_name]
    records = scraper.fetch_directory_letter("a", config)

    assert isinstance(records, list)
    assert all(isinstance(record, dict) for record in records)
    assert all("type" in record for record in records)
