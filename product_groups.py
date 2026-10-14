import re
import unicodedata


GIFA_PRODUCT_GROUPS = (
    "Gießereianlagen, Projektierung, Bau, Engineering",
    "Schmelzbetrieb",
    "Feuerfesttechnik",
    "Metallische Einsatzstoffe",
    "Form- und Kernherstellung",
    "Formstoffe",
    "Formstoffaufbereitung und Formstoffregenerierung",
    "Formereibedarf",
    "Anschnitt- und Speisertechnik",
    "Gießmaschinen und Gießeinrichtungen",
    "Ausleeren, Putzen, Rohgußnachbehandlung",
    "Oberflächenbehandlung",
    "Schweiß- und Schneidtechnik",
    "Öfen zur Wärmebehandlung und -trocknung",
    "Förder- und Lagertechnik",
    "Handhabungstechnik",
    "Modell- und Formenbau",
    "Steuerungs- und Regelungstechnik",
    "Mess- und Prüftechnik",
    "Drucklufttechnik",
    "Lufttechnik allgemein",
    "Umweltschutz und Entsorgung",
    "Arbeitsschutz und Arbeitssicherheit",
    "Informationsverarbeitung und Digitalisierung der Produktionsprozesse",
    "Additive Verfahren",
    "Forschung, Entwicklung, Fachverbände, Institutionen",
    "Beratung, Planung, Dienstleistungen, Engineering",
    "Fachverlage, Fachzeitschriften",
    "Ausbildung und Weiterbildung",
)

GIFA_PRODUCT_GROUP_COLUMNS = tuple(
    f"{index}. {label}"
    for index, label in enumerate(GIFA_PRODUCT_GROUPS, start=1)
)


def normalize_product_group_label(value):
    value = unicodedata.normalize("NFKD", str(value))
    value = "".join(char for char in value if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


GIFA_PRODUCT_GROUP_BY_NORMALIZED_LABEL = {
    normalize_product_group_label(label): label
    for label in GIFA_PRODUCT_GROUPS
}


def extract_gifa_product_groups(categories):
    """Return only canonical groups explicitly present in source categories."""

    matches = set()
    for category in categories or []:
        if not isinstance(category, dict):
            continue
        values = list(category.get("hierarchy") or [])
        values.extend(category.get("productList") or [])
        for value in values:
            if isinstance(value, dict):
                value = value.get("label")
            canonical = GIFA_PRODUCT_GROUP_BY_NORMALIZED_LABEL.get(
                normalize_product_group_label(value)
            )
            if canonical:
                matches.add(canonical)
    return tuple(
        label for label in GIFA_PRODUCT_GROUPS if label in matches
    )
