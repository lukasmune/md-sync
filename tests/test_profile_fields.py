import database
import scraper
import sqlite3


def test_optional_profile_fields_are_stored_and_missing_fields_are_safe(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(database, "DATABASE_PATH", tmp_path / "test.db")
    monkeypatch.setattr(database, "DATA_DIR", tmp_path)
    database.initialize_database()
    exhibition_id = database.get_or_create_exhibition(
        "GIFA", 2023, "GMTN2023.gifa"
    )

    record = {
        "exh": "EXH-1",
        "name": "Example Foundry GmbH",
        "country": "Germany",
        "city": "Düsseldorf",
        "email": "info@example.test",
        "telephone": "+49 211 123",
        "productCategories": ["Casting"],
        "productGroups": ["Furnaces"],
    }
    database.sync_exhibitor(record, exhibition_id)

    with database.get_connection() as connection:
        row = connection.execute(
            "SELECT email, telephone, "
            "product_categories_json, product_groups_json FROM companies"
        ).fetchone()
    assert row["email"] == "info@example.test"
    assert row["telephone"] == "+49 211 123"
    assert row["product_categories_json"] == '["Casting"]'
    assert row["product_groups_json"] == '["Furnaces"]'

    database.sync_exhibitor(
        {
            "exh": "EXH-2",
            "name": "Another Company",
        },
        exhibition_id,
    )


def test_profile_enrichment_extracts_categories_and_telephone(monkeypatch):
    class Response:
        status_code = 200
        headers = {}

        def raise_for_status(self):
            pass

        def json(self):
            return {
                "name": "Example Foundry GmbH",
                "email": "info@example.test",
                "phone": {"phone": "+49 211 123"},
                "links": [{"link": "https://example.test"}],
                "categories": [
                    {
                        "id": "prod=event.01.02",
                        "label": "Casting",
                        "catalogIndex": "01.02",
                        "productList": [
                            {"id": "product=1", "label": "Furnaces"}
                        ],
                        "hierarchy": [
                            {"id": "01", "label": "Foundry equipment"},
                            {"id": "01.02", "label": "Casting"},
                        ],
                    },
                    {
                        "id": "prod=event.03",
                        "label": "Automation",
                        "catalogIndex": "03",
                        "hierarchy": [],
                    },
                ],
            }

    monkeypatch.setattr(scraper.requests, "get", lambda *args, **kwargs: Response())
    result = scraper.enrich_exhibitor_record(
        {"exh": "EVENT.123", "name": "Example Foundry GmbH"},
        {"domain": "www.gifa.com"},
    )

    assert result["email"] == "info@example.test"
    assert result["telephone"] == "+49 211 123"
    assert result["website"] == "https://example.test"
    assert [category["label"] for category in result["categories"]] == [
        "Casting",
        "Automation",
    ]


def test_profile_request_retries_rate_limit(monkeypatch):
    class Response:
        def __init__(self, status_code):
            self.status_code = status_code
            self.headers = {}

        def raise_for_status(self):
            if self.status_code != 200:
                raise RuntimeError("request failed")

        def json(self):
            return {"categories": []}

    responses = iter([Response(429), Response(200)])
    monkeypatch.setattr(scraper.requests, "get", lambda *args, **kwargs: next(responses))
    monkeypatch.setattr(scraper.time, "sleep", lambda _: None)

    result = scraper.fetch_exhibitor_profile(
        "EVENT.123",
        {"domain": "www.metec.com"},
    )

    assert result == {"categories": []}


def test_categories_are_normalized_and_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DATABASE_PATH", tmp_path / "test.db")
    monkeypatch.setattr(database, "DATA_DIR", tmp_path)
    database.initialize_database()
    exhibition_id = database.get_or_create_exhibition(
        "GIFA", 2023, "GMTN2023.gifa"
    )
    record = {
        "exh": "EVENT.123",
        "name": "Example Foundry GmbH",
        "categories": [
            {
                "id": "prod=event.01.02",
                "label": "Casting",
                "catalogIndex": "01.02",
                "hierarchy": [
                    {"id": "01", "label": "Foundry equipment"},
                    {"id": "01.02", "label": "Casting"},
                ],
            }
        ],
    }

    database.sync_exhibitor(record, exhibition_id)
    database.sync_exhibitor(record, exhibition_id)

    with database.get_connection() as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM product_categories"
        ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT COUNT(*) FROM product_groups"
        ).fetchone()[0] == 2
        assert connection.execute(
            "SELECT COUNT(*) FROM exhibition_company_categories"
        ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT COUNT(*) FROM product_category_groups"
        ).fetchone()[0] == 2


def test_existing_logo_column_is_removed_without_losing_company_data(
    tmp_path,
    monkeypatch,
):
    database_path = tmp_path / "legacy.db"
    connection = sqlite3.connect(database_path)
    connection.execute(
        """
        CREATE TABLE companies (
            id INTEGER PRIMARY KEY,
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
        )
        """
    )
    connection.execute(
        """
        INSERT INTO companies
            (name, normalized_name, website, logo, created_at, updated_at)
        VALUES ('Legacy Co', 'legacy co', 'https://legacy.test',
                'https://legacy.test/logo.png', 'a', 'b')
        """
    )
    connection.commit()
    connection.close()

    monkeypatch.setattr(database, "DATABASE_PATH", database_path)
    monkeypatch.setattr(database, "DATA_DIR", tmp_path)
    database.initialize_database()

    with database.get_connection() as connection:
        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(companies)")
        }
        company = connection.execute(
            "SELECT name, website FROM companies"
        ).fetchone()
    assert "logo" not in columns
    assert "contact_person" not in columns
    assert company["name"] == "Legacy Co"
    assert company["website"] == "https://legacy.test"


def test_external_sync_preserves_internal_sales_fields(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(database, "DATABASE_PATH", tmp_path / "test.db")
    monkeypatch.setattr(database, "DATA_DIR", tmp_path)
    database.initialize_database()
    exhibition_id = database.get_or_create_exhibition(
        "GIFA", 2023, "GMTN2023.gifa"
    )

    database.sync_exhibitor(
        {
            "exh": "EXH-1",
            "name": "Example Foundry GmbH",
            "country": "Germany",
        },
        exhibition_id,
    )

    with database.get_connection() as connection:
        connection.execute(
            """
            UPDATE companies
            SET sales_status = ?, sales_owner = ?, sales_notes = ?
            WHERE name = ?
            """,
            ("Qualified", "Lukas", "Keep this note", "Example Foundry GmbH"),
        )

    database.sync_exhibitor(
        {
            "exh": "EXH-1",
            "name": "Example Foundry GmbH",
            "country": "Germany",
            "sales_status": "Cold",
            "sales_owner": "External",
            "sales_notes": "Overwrite attempt",
        },
        exhibition_id,
    )

    with database.get_connection() as connection:
        row = connection.execute(
            """
            SELECT sales_status, sales_owner, sales_notes
            FROM companies
            WHERE name = ?
            """,
            ("Example Foundry GmbH",),
        ).fetchone()

    assert tuple(row) == ("Qualified", "Lukas", "Keep this note")
