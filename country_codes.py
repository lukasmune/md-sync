"""ISO 3166-1 alpha-2 lookup for the country names used by Messe Düsseldorf."""

_COUNTRY_CODES = {
    "Albania": "AL", "Algeria": "DZ", "Argentina": "AR", "Armenia": "AM",
    "Australia": "AU", "Austria": "AT", "Azerbaijan": "AZ", "Bahrain": "BH",
    "Bangladesh": "BD", "Belarus": "BY", "Belgium": "BE", "Bhutan": "BT",
    "Bosnia and Herzegovina": "BA", "Brazil": "BR", "Bulgaria": "BG",
    "Cambodia": "KH", "Canada": "CA", "Chile": "CL", "China": "CN",
    "Colombia": "CO", "Croatia": "HR", "Cyprus": "CY", "Czechia": "CZ",
    "Czech Republic": "CZ", "Denmark": "DK", "Ecuador": "EC", "Egypt": "EG",
    "Estonia": "EE", "Finland": "FI", "France": "FR", "Georgia": "GE",
    "Germany": "DE", "Greece": "GR", "Hong Kong, China SAR": "HK",
    "Hong Kong": "HK", "Hungary": "HU", "Iceland": "IS", "India": "IN",
    "Indonesia": "ID", "Iran, Islamic Republic": "IR",
    "Iran, Islamic Republic of": "IR", "Iraq": "IQ", "Ireland": "IE",
    "Israel": "IL", "Italy": "IT", "Japan": "JP", "Jordan": "JO",
    "Kazakhstan": "KZ", "Korea, Republic": "KR", "Korea, Republic of": "KR",
    "Kuwait": "KW", "Latvia": "LV", "Lebanon": "LB", "Liechtenstein": "LI",
    "Lithuania": "LT", "Luxembourg": "LU", "Malaysia": "MY", "Malta": "MT",
    "Mexico": "MX", "Moldova, Republic": "MD", "Moldova, Republic of": "MD",
    "Monaco": "MC", "Montenegro": "ME", "Morocco": "MA", "Netherlands": "NL",
    "New Zealand": "NZ", "Nigeria": "NG", "North Macedonia": "MK",
    "Norway": "NO", "Oman": "OM", "Pakistan": "PK", "Peru": "PE",
    "Philippines": "PH", "Poland": "PL", "Portugal": "PT", "Qatar": "QA",
    "Romania": "RO", "Russia": "RU", "Russian Federation": "RU",
    "Saudi Arabia": "SA", "Serbia": "RS", "Singapore": "SG",
    "Slovakia": "SK", "Slovenia": "SI", "South Africa": "ZA", "Spain": "ES",
    "Sri Lanka": "LK", "Sweden": "SE", "Switzerland": "CH", "Taiwan": "TW",
    "Thailand": "TH", "Tunisia": "TN", "Türkiye": "TR", "Turkey": "TR",
    "USA": "US", "United States": "US", "United States of America": "US",
    "Ukraine": "UA", "United Arab Emirates": "AE",
    "United Kingdom of Great Britain and Northern Ireland": "GB",
    "United Kingdom": "GB", "Uzbekistan": "UZ", "Vietnam": "VN",
    "Viet Nam": "VN",
}

_LOOKUP = {name.casefold(): code for name, code in _COUNTRY_CODES.items()}


def country_code(country):
    """Return the ISO 3166-1 alpha-2 code for a country name, or None."""

    if not country:
        return None
    return _LOOKUP.get(str(country).strip().casefold())
