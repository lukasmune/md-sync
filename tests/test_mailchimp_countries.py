import sqlite3

import pytest

import database
from country_codes import _COUNTRY_CODES
from mailchimp_countries import (
    MAILCHIMP_COUNTRIES,
    is_mailchimp_country,
    mailchimp_country,
)


@pytest.mark.parametrize(
    "name, expected",
    [
        ("USA", "United States of America"),
        ("Czechia", "Czech Republic"),
        ("Türkiye", "Turkiye"),
        ("Hong Kong, China SAR", "Hong Kong"),
        ("Iran, Islamic Republic", "Iran"),
        ("Korea, Republic", "South Korea"),
        ("Moldova, Republic", "Moldova"),
        ("North Macedonia", "Macedonia"),
        ("United Kingdom of Great Britain and Northern Ireland",
         "United Kingdom"),
        ("germany", "Germany"),
        ("Atlantis", "Atlantis"),
        (None, None),
    ],
)
def test_mailchimp_country_spelling(name, expected):
    assert mailchimp_country(name) == expected


def test_country_list_has_no_duplicates():
    assert len(MAILCHIMP_COUNTRIES) == 251
    assert len({n.casefold() for n in MAILCHIMP_COUNTRIES}) == 251


def test_every_known_country_name_maps_to_mailchimp_list():
    assert [
        name for name in _COUNTRY_CODES if not is_mailchimp_country(name)
    ] == []


def test_every_stored_country_maps_to_mailchimp_list():
    if not database.DATABASE_PATH.exists():
        pytest.skip("no local database")
    with sqlite3.connect(database.DATABASE_PATH) as connection:
        countries = [
            row[0] for row in connection.execute(
                "SELECT DISTINCT country FROM companies "
                "WHERE country IS NOT NULL AND country <> ''"
            )
        ]
    assert [c for c in countries if not is_mailchimp_country(c)] == []
