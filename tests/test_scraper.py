import pytest

import scraper


@pytest.mark.live
def test_live_directory_api_returns_records_with_expected_shape():
    config = scraper.EVENTS["GIFA"]
    records = scraper.fetch_directory_letter("a", config)

    assert isinstance(records, list)
    assert all(isinstance(record, dict) for record in records)
    assert all("type" in record for record in records)
