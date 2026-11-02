import sqlite3

import pytest

import database
from country_codes import country_code


@pytest.mark.parametrize(
    "name, code",
    [
        ("Germany", "DE"),
        ("  usa ", "US"),
        ("Türkiye", "TR"),
        ("Korea, Republic", "KR"),
        ("United Kingdom of Great Britain and Northern Ireland", "GB"),
        ("Hong Kong, China SAR", "HK"),
        ("Atlantis", None),
        (None, None),
        ("", None),
    ],
)
def test_country_code_lookup(name, code):
    assert country_code(name) == code


def test_every_stored_country_has_a_code():
    if not database.DATABASE_PATH.exists():
        pytest.skip("no local database")
    with sqlite3.connect(database.DATABASE_PATH) as connection:
        countries = [
            row[0]
            for row in connection.execute(
                "SELECT DISTINCT country FROM companies "
                "WHERE country IS NOT NULL AND country <> ''"
            )
        ]
    assert [c for c in countries if country_code(c) is None] == []
