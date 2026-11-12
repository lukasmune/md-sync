"""Country names accepted by Mailchimp and the mapping from source names."""

MAILCHIMP_COUNTRIES = (
    "United States of America", "Aaland Islands", "Afghanistan", "Albania",
    "Algeria", "American Samoa", "Andorra", "Angola", "Anguilla",
    "Antarctica", "Antigua And Barbuda", "Argentina", "Armenia", "Aruba",
    "Australia", "Austria", "Azerbaijan", "Bahamas", "Bahrain", "Bangladesh",
    "Barbados", "Belarus", "Belgium", "Belize", "Benin", "Bermuda", "Bhutan",
    "Bolivia", "Bonaire, Saint Eustatius and Saba", "Bosnia and Herzegovina",
    "Botswana", "Bouvet Island", "Brazil", "British Indian Ocean Territory",
    "Brunei Darussalam", "Bulgaria", "Burkina Faso", "Burundi", "Cambodia",
    "Cameroon", "Canada", "Cape Verde", "Cayman Islands",
    "Central African Republic", "Chad", "Chile", "China", "Christmas Island",
    "Cocos (Keeling) Islands", "Colombia", "Comoros", "Congo",
    "Congo, Democratic Republic of the", "Cook Islands", "Costa Rica",
    "Cote D'Ivoire", "Croatia", "Cuba", "Curacao", "Cyprus",
    "Czech Republic", "Denmark", "Djibouti", "Dominica",
    "Dominican Republic", "Ecuador", "Egypt", "El Salvador",
    "Equatorial Guinea", "Eritrea", "Estonia", "Ethiopia",
    "Falkland Islands", "Faroe Islands", "Fiji", "Finland", "France",
    "French Guiana", "French Polynesia", "French Southern Territories",
    "Gabon", "Gambia", "Georgia", "Germany", "Ghana", "Gibraltar", "Greece",
    "Greenland", "Grenada", "Guadeloupe", "Guam", "Guatemala", "Guernsey",
    "Guinea", "Guinea-Bissau", "Guyana", "Haiti",
    "Heard and Mc Donald Islands", "Honduras", "Hong Kong", "Hungary",
    "Iceland", "India", "Indonesia", "Iran", "Iraq", "Ireland",
    "Isle of Man", "Israel", "Italy", "Jamaica", "Japan",
    "Jersey (Channel Islands)", "Jordan", "Kazakhstan", "Kenya", "Kiribati",
    "Kuwait", "Kyrgyzstan", "Lao People's Democratic Republic", "Latvia",
    "Lebanon", "Lesotho", "Liberia", "Libya", "Liechtenstein", "Lithuania",
    "Luxembourg", "Macau", "Macedonia", "Madagascar", "Malawi", "Malaysia",
    "Maldives", "Mali", "Malta", "Marshall Islands", "Martinique",
    "Mauritania", "Mauritius", "Mayotte", "Mexico",
    "Micronesia, Federated States of", "Moldova", "Monaco", "Mongolia",
    "Montenegro", "Montserrat", "Morocco", "Mozambique", "Myanmar",
    "Namibia", "Nauru", "Nepal", "Netherlands", "Netherlands Antilles",
    "New Caledonia", "New Zealand", "Nicaragua", "Niger", "Nigeria", "Niue",
    "Norfolk Island", "North Korea", "Northern Mariana Islands", "Norway",
    "Oman", "Pakistan", "Palau", "Palestine", "Panama", "Papua New Guinea",
    "Paraguay", "Peru", "Philippines", "Pitcairn", "Poland", "Portugal",
    "Puerto Rico", "Qatar", "Republic of Kosovo", "Reunion", "Romania",
    "Russia", "Rwanda", "Saint Kitts and Nevis", "Saint Lucia",
    "Saint Martin", "Saint Vincent and the Grenadines",
    "Samoa (Independent)", "San Marino", "Sao Tome and Principe",
    "Saudi Arabia", "Senegal", "Serbia", "Seychelles", "Sierra Leone",
    "Singapore", "Sint Maarten", "Slovakia", "Slovenia", "Solomon Islands",
    "Somalia", "South Africa", "South Georgia and the South Sandwich Islands",
    "South Korea", "South Sudan", "Spain", "Sri Lanka", "St. Helena",
    "St. Pierre and Miquelon", "Sudan", "Suriname",
    "Svalbard and Jan Mayen Islands", "Swaziland", "Sweden", "Switzerland",
    "Syria", "Taiwan", "Tajikistan", "Tanzania", "Thailand", "Timor-Leste",
    "Togo", "Tokelau", "Tonga", "Trinidad and Tobago", "Tunisia", "Turkiye",
    "Turkmenistan", "Turks & Caicos Islands", "Turks and Caicos Islands",
    "Tuvalu", "Uganda", "Ukraine", "United Arab Emirates", "United Kingdom",
    "Uruguay", "USA Minor Outlying Islands", "Uzbekistan", "Vanuatu",
    "Vatican City State (Holy See)", "Venezuela", "Vietnam",
    "Virgin Islands (British)", "Virgin Islands (U.S.)",
    "Wallis and Futuna Islands", "Western Sahara", "Yemen", "Zambia",
    "Zimbabwe",
)

_ALIASES = {
    "USA": "United States of America",
    "United States": "United States of America",
    "Czechia": "Czech Republic",
    "Türkiye": "Turkiye",
    "Turkey": "Turkiye",
    "Hong Kong, China SAR": "Hong Kong",
    "Iran, Islamic Republic": "Iran",
    "Iran, Islamic Republic of": "Iran",
    "Korea, Republic": "South Korea",
    "Korea, Republic of": "South Korea",
    "Moldova, Republic": "Moldova",
    "Moldova, Republic of": "Moldova",
    "North Macedonia": "Macedonia",
    "Russian Federation": "Russia",
    "United Kingdom of Great Britain and Northern Ireland": "United Kingdom",
    "Viet Nam": "Vietnam",
}

_LOOKUP = {name.casefold(): name for name in MAILCHIMP_COUNTRIES}
_LOOKUP.update({alias.casefold(): name for alias, name in _ALIASES.items()})


def mailchimp_country(country):
    """Return the Mailchimp spelling of a country name.

    A name Mailchimp does not know is returned unchanged so no data is lost.
    """

    if not country:
        return country
    value = str(country).strip()
    return _LOOKUP.get(value.casefold(), value)


def is_mailchimp_country(country):
    return bool(country) and str(country).strip().casefold() in _LOOKUP
