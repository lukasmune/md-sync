import sqlite3
import json
from contextlib import contextmanager
from datetime import datetime, timezone

from config import DATABASE_PATH, DATA_DIR
from normalizer import (
    normalize_company_name,
    normalize_country,
    normalize_city,
)


def utc_now():
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def get_connection():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DATABASE_PATH)

    connection.row_factory = sqlite3.Row

    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database():
    """
    Create the database schema if it does not already exist.
    """

    with get_connection() as connection:
        cursor = connection.cursor()

        cursor.executescript(
            """
            CREATE TABLE IF NOT EXISTS companies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                name TEXT NOT NULL,
                normalized_name TEXT NOT NULL,

                country TEXT,
                normalized_country TEXT,

                city TEXT,
                normalized_city TEXT,

                website TEXT,
                logo TEXT,

                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_companies_normalized_name
                ON companies(normalized_name);

            CREATE INDEX IF NOT EXISTS idx_companies_name_country
                ON companies(normalized_name, normalized_country);


            CREATE TABLE IF NOT EXISTS exhibitions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                event_name TEXT NOT NULL,
                edition INTEGER NOT NULL,
                event_code TEXT NOT NULL UNIQUE,

                created_at TEXT NOT NULL
            );


            CREATE TABLE IF NOT EXISTS exhibition_companies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                company_id INTEGER NOT NULL,
                exhibition_id INTEGER NOT NULL,

                gifa_exhibitor_id TEXT,
                seo_id TEXT,

                hall TEXT,
                stand TEXT,
                location TEXT,

                premium INTEGER NOT NULL DEFAULT 0,

                tags_json TEXT,
                event_icons_json TEXT,

                scraped_at TEXT NOT NULL,

                FOREIGN KEY (company_id)
                    REFERENCES companies(id),

                FOREIGN KEY (exhibition_id)
                    REFERENCES exhibitions(id),

                UNIQUE(exhibition_id, gifa_exhibitor_id)
            );

            CREATE INDEX IF NOT EXISTS idx_exhibition_companies_company
                ON exhibition_companies(company_id);

            CREATE INDEX IF NOT EXISTS idx_exhibition_companies_exhibition
                ON exhibition_companies(exhibition_id);

            CREATE INDEX IF NOT EXISTS idx_exhibition_companies_gifa_id
                ON exhibition_companies(gifa_exhibitor_id);
            """
        )

        for column in ("first_seen_at", "last_seen_at", "changed_at"):
            try:
                cursor.execute(
                    f"ALTER TABLE exhibition_companies ADD COLUMN {column} TEXT"
                )
            except sqlite3.OperationalError as error:
                if "duplicate column name" not in str(error):
                    raise

        for column in (
            "email",
            "contact_person",
            "telephone",
            "product_categories_json",
            "product_groups_json",
        ):
            try:
                cursor.execute(
                    f"ALTER TABLE companies ADD COLUMN {column} TEXT"
                )
            except sqlite3.OperationalError as error:
                if "duplicate column name" not in str(error):
                    raise

        cursor.execute(
            """
            UPDATE exhibition_companies
            SET
                first_seen_at = COALESCE(first_seen_at, scraped_at),
                last_seen_at = COALESCE(last_seen_at, scraped_at)
            WHERE first_seen_at IS NULL
               OR last_seen_at IS NULL
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS gifa_sync_metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        migration = cursor.execute(
            """
            SELECT 1 FROM gifa_sync_metadata
            WHERE key = 'change_tracking_initialized'
            """
        ).fetchone()
        if migration is None:
            cursor.execute(
                "UPDATE exhibition_companies SET changed_at = NULL"
            )
            cursor.execute(
                """
                INSERT INTO gifa_sync_metadata (key, value)
                VALUES ('change_tracking_initialized', ?)
                """,
                (utc_now(),),
            )


def get_or_create_exhibition(event_name, edition, event_code):
    """
    Return the internal exhibition ID.
    Create the exhibition if it does not exist.
    """

    with get_connection() as connection:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT id
            FROM exhibitions
            WHERE event_code = ?
            """,
            (event_code,),
        )

        row = cursor.fetchone()

        if row:
            return row["id"]

        cursor.execute(
            """
            INSERT INTO exhibitions (
                event_name,
                edition,
                event_code,
                created_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                event_name,
                edition,
                event_code,
                utc_now(),
            ),
        )

        return cursor.lastrowid


def find_company(name, country=None, city=None):
    """
    Find an existing company using deterministic identity matching.

    Matching priority:

    1. normalized name + country + city
    2. normalized name + country
    3. normalized name

    The final name-only match is only accepted when it is unique.
    """

    normalized_name = normalize_company_name(name)
    normalized_country = normalize_country(country)
    normalized_city = normalize_city(city)

    with get_connection() as connection:
        cursor = connection.cursor()

        # Strongest match.
        cursor.execute(
            """
            SELECT *
            FROM companies
            WHERE normalized_name = ?
              AND normalized_country = ?
              AND normalized_city = ?
            """,
            (
                normalized_name,
                normalized_country,
                normalized_city,
            ),
        )

        row = cursor.fetchone()

        if row:
            return row

        # Name + country.
        cursor.execute(
            """
            SELECT *
            FROM companies
            WHERE normalized_name = ?
              AND normalized_country = ?
            """,
            (
                normalized_name,
                normalized_country,
            ),
        )

        rows = cursor.fetchall()

        if len(rows) == 1:
            return rows[0]

        # Name only, but only if unique.
        cursor.execute(
            """
            SELECT *
            FROM companies
            WHERE normalized_name = ?
            """,
            (normalized_name,),
        )

        rows = cursor.fetchall()

        if len(rows) == 1:
            return rows[0]

        return None


def create_company(record):
    """
    Create a new company from a GIFA API record.
    """

    name = record.get("name", "").strip()
    country = record.get("country")
    city = record.get("city")
    website = record.get("website")
    logo = record.get("logo")
    optional = extract_profile_fields(record)

    normalized_name = normalize_company_name(name)
    normalized_country = normalize_country(country)
    normalized_city = normalize_city(city)

    now = utc_now()

    with get_connection() as connection:
        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO companies (
                name,
                normalized_name,
                country,
                normalized_country,
                city,
                normalized_city,
                website,
                logo,
                email,
                contact_person,
                telephone,
                product_categories_json,
                product_groups_json,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                name,
                normalized_name,
                country,
                normalized_country,
                city,
                normalized_city,
                website,
                logo,
                optional["email"],
                optional["contact_person"],
                optional["telephone"],
                optional["product_categories_json"],
                optional["product_groups_json"],
                now,
                now,
            ),
        )

        return cursor.lastrowid


def update_company(company_id, record):
    """
    Update the current company information without changing
    its permanent internal ID.
    """

    name = record.get("name", "").strip()
    country = record.get("country")
    city = record.get("city")
    website = record.get("website")
    logo = record.get("logo")
    optional = extract_profile_fields(record)

    with get_connection() as connection:
        cursor = connection.cursor()

        cursor.execute(
            """
            UPDATE companies
            SET
                name = ?,
                normalized_name = ?,
                country = COALESCE(?, country),
                normalized_country = COALESCE(?, normalized_country),
                city = COALESCE(?, city),
                normalized_city = COALESCE(?, normalized_city),
                website = COALESCE(?, website),
                logo = COALESCE(?, logo),
                email = COALESCE(?, email),
                contact_person = COALESCE(?, contact_person),
                telephone = COALESCE(?, telephone),
                product_categories_json = COALESCE(?, product_categories_json),
                product_groups_json = COALESCE(?, product_groups_json),
                updated_at = ?
            WHERE id = ?
            """,
            (
                name,
                normalize_company_name(name),
                country,
                normalize_country(country) if country is not None else None,
                city,
                normalize_city(city) if city is not None else None,
                website,
                logo,
                optional["email"],
                optional["contact_person"],
                optional["telephone"],
                optional["product_categories_json"],
                optional["product_groups_json"],
                utc_now(),
                company_id,
            ),
        )


def upsert_exhibition_company(company_id, exhibition_id, record):
    """
    Create or update the company's participation in an exhibition.
    """

    event_icons = record.get("eventIcons", [])
    tags = record.get("tags", [])

    location = record.get("location") or ""

    hall = None
    stand = None

    if "/" in location:
        hall, stand = [
            value.strip()
            for value in location.split("/", 1)
        ]
    else:
        hall = location.strip() or None

    scraped_at = utc_now()
    exhibitor_id = record.get("exh")
    tags_json = json.dumps(tags)
    event_icons_json = json.dumps(event_icons)

    with get_connection() as connection:
        cursor = connection.cursor()
        existing = cursor.execute(
            """
            SELECT seo_id, hall, stand, location, premium,
                   tags_json, event_icons_json
            FROM exhibition_companies
            WHERE exhibition_id = ? AND gifa_exhibitor_id = ?
            """,
            (exhibition_id, exhibitor_id),
        ).fetchone()
        duplicate = bool(
            existing
            and (
                existing["seo_id"],
                existing["hall"],
                existing["stand"],
                existing["location"],
                existing["premium"],
                existing["tags_json"],
                existing["event_icons_json"],
            )
            == (
                record.get("exhSeoId"),
                hall,
                stand,
                location,
                1 if record.get("premium") else 0,
                tags_json,
                event_icons_json,
            )
        )

        cursor.execute(
            """
            INSERT INTO exhibition_companies (
                company_id,
                exhibition_id,
                gifa_exhibitor_id,
                seo_id,
                hall,
                stand,
                location,
                premium,
                tags_json,
                event_icons_json,
                scraped_at,
                first_seen_at,
                last_seen_at,
                changed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)

            ON CONFLICT(exhibition_id, gifa_exhibitor_id)
            DO UPDATE SET
                gifa_exhibitor_id = excluded.gifa_exhibitor_id,
                seo_id = excluded.seo_id,
                hall = excluded.hall,
                stand = excluded.stand,
                location = excluded.location,
                premium = excluded.premium,
                tags_json = excluded.tags_json,
                event_icons_json = excluded.event_icons_json,
                                scraped_at = excluded.scraped_at,
                                last_seen_at = excluded.last_seen_at,
                                changed_at = CASE
                                        WHEN exhibition_companies.seo_id IS NOT excluded.seo_id
                                            OR exhibition_companies.hall IS NOT excluded.hall
                                            OR exhibition_companies.stand IS NOT excluded.stand
                                            OR exhibition_companies.location IS NOT excluded.location
                                            OR exhibition_companies.premium IS NOT excluded.premium
                                            OR exhibition_companies.tags_json IS NOT excluded.tags_json
                                            OR exhibition_companies.event_icons_json IS NOT excluded.event_icons_json
                                        THEN excluded.changed_at
                                        ELSE exhibition_companies.changed_at
                                END
            """,
            (
                company_id,
                exhibition_id,
                exhibitor_id,
                record.get("exhSeoId"),
                hall,
                stand,
                location,
                1 if record.get("premium") else 0,
                tags_json,
                event_icons_json,
                scraped_at,
                scraped_at,
                scraped_at,
                scraped_at,
            ),
        )

    return {
        "created": existing is None,
        "updated": existing is not None and not duplicate,
        "duplicate": duplicate,
    }


def extract_profile_fields(record):
    """Extract optional public profile fields without requiring their presence."""

    def first_value(*keys):
        for key in keys:
            value = record.get(key)
            if value not in (None, ""):
                return str(value)
        return None

    def json_value(*keys):
        for key in keys:
            value = record.get(key)
            if value not in (None, ""):
                return json.dumps(value) if not isinstance(value, str) else value
        return None

    return {
        "email": first_value("email", "contactEmail", "companyEmail"),
        "contact_person": first_value(
            "contactPerson", "contact_person", "contactName"
        ),
        "telephone": first_value("telephone", "phone", "telephoneNumber"),
        "product_categories_json": json_value(
            "productCategories", "product_categories", "categories"
        ),
        "product_groups_json": json_value(
            "productGroups", "product_groups", "groups"
        ),
    }


def sync_exhibitor(record, exhibition_id):
    """
    Synchronize one scraped exhibitor.

    Returns:
        {
            "company_id": int,
            "created": bool
        }
    """

    name = record.get("name")

    if not name:
        raise ValueError("Exhibitor record has no company name.")

    company = find_company(
        name=name,
        country=record.get("country"),
        city=record.get("city"),
    )

    if company is None:
        company_id = create_company(record)
        created = True
    else:
        company_id = company["id"]
        update_company(company_id, record)
        created = False

    participation = upsert_exhibition_company(
        company_id=company_id,
        exhibition_id=exhibition_id,
        record=record,
    )

    return {
        "company_id": company_id,
        "created": created,
        "participation_created": participation["created"],
        "participation_updated": participation["updated"],
        "duplicate": participation["duplicate"],
    }