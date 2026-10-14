import re
import unicodedata


GIFA_PRODUCT_GROUP_MAPPINGS = (
    ("Gießereianlagen, Projektierung, Bau, Engineering",
     "Foundry plants and installations, planning, construction, engineering",
     True),
    ("Schmelzbetrieb", "Melting shop", True),
    ("Feuerfesttechnik", "Refractories technology", True),
    ("Metallische Einsatzstoffe", "Metallic charge materials", True),
    ("Form- und Kernherstellung", "Moulding and core making", True),
    ("Formstoffe", "Moulding sands", True),
    ("Formstoffaufbereitung und Formstoffregenerierung",
     "Moulding sand preparation and sand reclamation", True),
    ("Formereibedarf", "Foundry supplies", False),
    ("Anschnitt- und Speisertechnik", "Gating and risering technology", False),
    ("Gießmaschinen und Gießeinrichtungen",
     "Casting machines and pouring equipment", True),
    ("Ausleeren, Putzen, Rohgußnachbehandlung",
     "Knock-out, fettling and finishing", True),
    ("Oberflächenbehandlung", "Surface treatment", True),
    ("Schweiß- und Schneidtechnik", "Welding and cutting", True),
    ("Öfen zur Wärmebehandlung und -trocknung",
     "Heat treating and drying furnaces", True),
    ("Förder- und Lagertechnik", "Transportation and storage", True),
    ("Handhabungstechnik", "Manipulation", True),
    ("Modell- und Formenbau", "Pattern and die making", True),
    ("Steuerungs- und Regelungstechnik", "Control systems", True),
    ("Mess- und Prüftechnik", "Measurement and test technology", True),
    ("Drucklufttechnik", "Compressed air technology", False),
    ("Lufttechnik allgemein", "Exhaust and ventilation technology", True),
    ("Umweltschutz und Entsorgung",
     "Environmental protection and waste removal", True),
    ("Arbeitsschutz und Arbeitssicherheit",
     "Occupational health and safety", False),
    ("Informationsverarbeitung und Digitalisierung der Produktionsprozesse",
     "Information processing", True),
    ("Additive Verfahren", "Additive Manufacturing", True),
    ("Forschung, Entwicklung, Fachverbände, Institutionen",
     "Research, development, professional associations, institutions", False),
    ("Beratung, Planung, Dienstleistungen, Engineering",
     "Consulting, design, service and engineering", True),
    ("Fachverlage, Fachzeitschriften",
     "Technical publications, technical periodicals, associations", True),
    ("Ausbildung und Weiterbildung", "Training and further education", False),
)

GIFA_PRODUCT_GROUPS = tuple(
    english for _german, english, _verified in GIFA_PRODUCT_GROUP_MAPPINGS
)

GIFA_PRODUCT_GROUP_GERMAN_ALIASES = {
    german: english
    for german, english, _verified in GIFA_PRODUCT_GROUP_MAPPINGS
}

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
GIFA_PRODUCT_GROUP_BY_NORMALIZED_LABEL.update({
    normalize_product_group_label(german): english
    for german, english, _verified in GIFA_PRODUCT_GROUP_MAPPINGS
})


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


def canonicalize_gifa_product_groups(values):
    """Return canonical groups found in persisted source labels."""

    normalized = {
        GIFA_PRODUCT_GROUP_BY_NORMALIZED_LABEL.get(
            normalize_product_group_label(value)
        )
        for value in values
        if value
    }
    return tuple(
        label
        for label in GIFA_PRODUCT_GROUPS
        if label in normalized
    )
