import json
import sqlite3

import pytest

import archive
import database
import scraper


def record(exh, name, country, city, label="GIFA 2023", **extra):
    data = {
        "type": "profile",
        "exh": exh,
        "exhSeoId": f"seo-{exh}",
        "name": name,
        "country": country,
        "city": city,
        "website": f"http://{name.split()[0].lower()}.example",
        "email": f"info@{name.split()[0].lower()}.example",
        "telephone": "+49 1",
        "location": "Hall 13 / A66",
        "premium": False,
        "tags": [],
        "eventIcons": [{"label": label, "src": "x"}],
    }
    data.update(extra)
    return data


CATEGORY = {
    "id": "prod=SHARED.01",
    "label": "Old label",
    "catalogIndex": "gifa.01",
    "hierarchy": [{"id": "01", "label": "Group one"}],
    "productList": [{"id": "01.01", "label": "Sub group"}],
}

TAG = {"id": "tag=1", "label": "Participant", "icon": "fa fa-university"}

RECORDS_2023 = [
    record("GMTN2023.1", "Alpha GmbH", "Germany", "Berlin",
           premium=True, tags=[TAG], categories=[CATEGORY]),
    record("GMTN2023.2", "Beta SA", "France", "Paris", location="Hall 1"),
    record("GMTN2023.3", "Gamma Ltd", "UK", "London", location=""),
]


def populate(path, records, event, edition, code, historical=False):
    with archive._database_target(path):
        database.initialize_database()
        exhibition_id = database.get_or_create_exhibition(
            event, edition, code
        )
        for item in records:
            database.sync_exhibitor(
                item, exhibition_id, historical=historical
            )


def rows(path, sql, args=()):
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        return [dict(row) for row in connection.execute(sql, args)]
    finally:
        connection.close()


@pytest.fixture
def source_db(tmp_path):
    path = tmp_path / "source" / "md-sync.db"
    path.parent.mkdir()
    populate(path, RECORDS_2023, "GIFA", 2023, "GMTN2023.gifa")
    return path


@pytest.fixture
def gifa_archive(tmp_path, source_db):
    return archive.export_archive(
        "GIFA", 2023, source_db, tmp_path / "archive"
    )


def rewrite(archive_path, records=None, **manifest_changes):
    """Modify an archive and keep its checksum consistent."""

    manifest_file = archive_path / archive.MANIFEST_NAME
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    if records is not None:
        data = archive._dump(records)
        (archive_path / archive.EXHIBITORS_FILE).write_bytes(data)
        import hashlib

        manifest["files"][0]["sha256"] = hashlib.sha256(data).hexdigest()
        manifest["files"][0]["record_count"] = len(records)
        manifest["record_count"] = len(records)
    manifest.update(manifest_changes)
    manifest_file.write_text(json.dumps(manifest), encoding="utf-8")


def load_records(archive_path):
    return json.loads(
        (archive_path / archive.EXHIBITORS_FILE).read_text(encoding="utf-8")
    )


def test_export_writes_manifest_and_records(gifa_archive):
    manifest, records = archive.load_archive(gifa_archive)

    assert manifest["fair"] == "GIFA"
    assert manifest["edition"] == 2023
    assert manifest["event_label"] == "GIFA 2023"
    assert manifest["event_code"] == "GMTN2023.gifa"
    assert manifest["source"] == "db-export"
    assert manifest["is_raw_api_snapshot"] is False
    assert manifest["captured_at"] is None
    assert manifest["format_version"] == archive.FORMAT_VERSION
    assert manifest["record_count"] == 3 == len(records)
    assert manifest["limitations"]

    alpha = next(item for item in records if item["exh"] == "GMTN2023.1")
    assert alpha["premium"] is True
    assert alpha["tags"] == [TAG]
    assert list(alpha["tags"][0]) == ["id", "label", "icon"]
    assert alpha["location"] == "Hall 13 / A66"
    assert alpha["categories"][0]["id"] == "prod=SHARED.01"
    assert alpha["categories"][0]["hierarchy"] == CATEGORY["hierarchy"]
    assert {r["exhibitor_role"] for r in records} == {"direct"}


def test_export_is_immutable_and_read_only(tmp_path, source_db):
    before = source_db.read_bytes()
    target = archive.export_archive("GIFA", 2023, source_db, tmp_path / "a")

    with pytest.raises(archive.ArchiveError, match="immutable"):
        archive.export_archive("GIFA", 2023, source_db, tmp_path / "a")

    assert target.is_dir()
    assert source_db.read_bytes() == before


def test_export_rejects_unknown_exhibition(tmp_path, source_db):
    with pytest.raises(archive.ArchiveError, match="No exhibition"):
        archive.export_archive("METEC", 2023, source_db, tmp_path / "a")


def test_invalid_checksum_is_rejected(gifa_archive):
    data_file = gifa_archive / archive.EXHIBITORS_FILE
    data_file.write_bytes(data_file.read_bytes() + b" ")

    with pytest.raises(archive.ArchiveError, match="Checksum"):
        archive.load_archive(gifa_archive)


def test_missing_data_file_is_rejected(gifa_archive):
    (gifa_archive / archive.EXHIBITORS_FILE).unlink()

    with pytest.raises(archive.ArchiveError, match="not found"):
        archive.load_archive(gifa_archive)


def test_unsafe_data_path_is_rejected(gifa_archive):
    manifest = json.loads(
        (gifa_archive / archive.MANIFEST_NAME).read_text(encoding="utf-8")
    )
    manifest["files"][0]["path"] = "../exhibitors.json"
    (gifa_archive / archive.MANIFEST_NAME).write_text(
        json.dumps(manifest), encoding="utf-8"
    )

    with pytest.raises(archive.ArchiveError, match="Unsafe"):
        archive.load_archive(gifa_archive)


def test_fair_mismatch_is_rejected(gifa_archive):
    rewrite(gifa_archive, fair="METEC")

    with pytest.raises(archive.ArchiveError, match="does not match"):
        archive.load_archive(gifa_archive)


def test_edition_mismatch_is_rejected(gifa_archive):
    rewrite(gifa_archive, edition=2019)

    with pytest.raises(archive.ArchiveError, match="does not match"):
        archive.load_archive(gifa_archive)


def test_current_edition_archive_is_not_historical(gifa_archive):
    rewrite(
        gifa_archive,
        edition=2027,
        event_label="GIFA 2027",
        event_code="GMTN2027.gifa",
    )

    with pytest.raises(archive.ArchiveError, match="not historical"):
        archive.load_archive(gifa_archive)


def test_2027_record_in_2023_archive_is_rejected(gifa_archive):
    records = load_records(gifa_archive)
    records.append(
        record("gifa2027.9", "Delta AG", "Germany", "Bonn", label="GIFA 2027")
    )
    rewrite(gifa_archive, records)

    with pytest.raises(archive.ArchiveError, match="not labelled 'GIFA 2023'"):
        archive.load_archive(gifa_archive)


def test_record_with_contradicting_second_label_is_rejected(gifa_archive):
    records = load_records(gifa_archive)
    records[0]["eventIcons"].append({"label": "GIFA 2027", "src": "x"})
    rewrite(gifa_archive, records)

    with pytest.raises(archive.ArchiveError, match="contradicts"):
        archive.load_archive(gifa_archive)


def test_other_fair_label_in_record_is_rejected(gifa_archive):
    records = load_records(gifa_archive)
    records[0]["eventIcons"] = [{"label": "METEC 2023", "src": "x"}]
    rewrite(gifa_archive, records)

    with pytest.raises(archive.ArchiveError, match="not labelled"):
        archive.load_archive(gifa_archive)


def test_duplicate_exhibitor_ids_are_rejected(gifa_archive):
    records = load_records(gifa_archive)
    records.append(dict(records[0]))
    rewrite(gifa_archive, records)

    with pytest.raises(archive.ArchiveError, match="Duplicate"):
        archive.load_archive(gifa_archive)


def test_missing_archive_fails_without_network(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("network access attempted")

    monkeypatch.setattr(scraper.requests, "get", forbidden)

    with pytest.raises(archive.ArchiveError, match="manifest not found"):
        archive.import_archive(
            tmp_path / "missing", apply=True,
            database_path=tmp_path / "t.db",
        )
    assert not (tmp_path / "t.db").exists()


def test_import_never_uses_network(tmp_path, gifa_archive, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("network access attempted")

    monkeypatch.setattr(scraper.requests, "get", forbidden)

    summary = archive.import_archive(
        gifa_archive, apply=True, database_path=tmp_path / "t" / "md-sync.db"
    )

    assert summary["participations_created"] == 3


def test_dry_run_does_not_write_database(tmp_path, gifa_archive):
    target = tmp_path / "t" / "md-sync.db"

    summary = archive.import_archive(gifa_archive, database_path=target)

    assert summary["applied"] is False
    assert summary["participations_created"] == 3
    assert not target.exists()


def test_dry_run_leaves_existing_database_untouched(
    tmp_path, gifa_archive,
):
    target = tmp_path / "t" / "md-sync.db"
    target.parent.mkdir()
    populate(target, [], "GIFA", 2027, "GMTN2027.gifa")
    before = target.read_bytes()

    summary = archive.import_archive(gifa_archive, database_path=target)

    assert summary["participations_created"] == 3
    assert target.read_bytes() == before


def test_apply_creates_edition_specific_records(tmp_path, gifa_archive):
    target = tmp_path / "t" / "md-sync.db"

    summary = archive.import_archive(
        gifa_archive, apply=True, database_path=target
    )

    assert summary["exhibition_created"] is True
    assert summary["companies_created"] == 3
    exhibitions = rows(
        target, "SELECT event_name, edition, event_code FROM exhibitions"
    )
    assert exhibitions == [
        {"event_name": "GIFA", "edition": 2023, "event_code": "GMTN2023.gifa"}
    ]
    stored = rows(
        target,
        "SELECT source_exhibitor_id, hall, stand, premium, tags_json "
        "FROM exhibition_companies ORDER BY source_exhibitor_id",
    )
    assert [r["source_exhibitor_id"] for r in stored] == [
        "GMTN2023.1", "GMTN2023.2", "GMTN2023.3",
    ]
    assert (stored[0]["hall"], stored[0]["stand"], stored[0]["premium"]) == (
        "Hall 13", "A66", 1,
    )
    assert json.loads(stored[0]["tags_json"]) == [TAG]
    assert rows(target, "SELECT COUNT(*) AS n FROM change_history")[0]["n"] == 0


def test_round_trip_matches_source_database(tmp_path, source_db, gifa_archive):
    target = tmp_path / "t" / "md-sync.db"
    archive.import_archive(gifa_archive, apply=True, database_path=target)

    query = (
        "SELECT co.name, co.country, co.city, co.website, co.email, "
        "co.telephone, ec.source_exhibitor_id, ec.seo_id, ec.hall, ec.stand, "
        "ec.location, ec.premium, ec.tags_json, ec.event_icons_json "
        "FROM exhibition_companies ec JOIN companies co "
        "ON co.id = ec.company_id ORDER BY ec.source_exhibitor_id"
    )
    assert rows(target, query) == rows(source_db, query)
    category_query = (
        "SELECT ec.source_exhibitor_id, pc.source_id, pc.label, pg.source_id "
        "AS group_id FROM exhibition_company_categories ecc "
        "JOIN exhibition_companies ec ON ec.id = ecc.exhibition_company_id "
        "JOIN product_categories pc ON pc.id = ecc.product_category_id "
        "JOIN product_category_groups pcg ON pcg.product_category_id = pc.id "
        "JOIN product_groups pg ON pg.id = pcg.product_group_id "
        "ORDER BY 1, 2, 4"
    )
    assert rows(target, category_query) == rows(source_db, category_query)


def test_repeat_import_is_idempotent(tmp_path, gifa_archive):
    target = tmp_path / "t" / "md-sync.db"
    archive.import_archive(gifa_archive, apply=True, database_path=target)
    snapshot = {
        table: rows(target, f"SELECT * FROM {table}")
        for table in (
            "companies", "exhibitions", "exhibition_companies",
            "product_categories", "product_groups",
            "exhibition_company_categories", "product_category_groups",
        )
    }

    summary = archive.import_archive(
        gifa_archive, apply=True, database_path=target
    )

    assert summary["exhibition_created"] is False
    assert summary["companies_created"] == 0
    assert summary["participations_created"] == 0
    assert summary["participations_updated"] == 0
    assert summary["participations_unchanged"] == 3
    for table, before in snapshot.items():
        assert rows(target, f"SELECT * FROM {table}") == before


@pytest.fixture
def current_db(tmp_path):
    """A database that already holds current 2027 data and sales fields."""

    path = tmp_path / "t" / "md-sync.db"
    path.parent.mkdir()
    category = dict(CATEGORY, label="New label")
    populate(
        path,
        [
            record(
                "gifa2027.1", "Alpha GmbH", "Germany", "Berlin",
                label="GIFA 2027", website="http://alpha-new.example",
                email="sales@alpha-new.example", telephone="+49 999",
                categories=[category],
            ),
            record("gifa2027.7", "Omega GmbH", "Germany", "Essen",
                   label="GIFA 2027"),
        ],
        "GIFA", 2027, "GMTN2027.gifa",
    )
    connection = sqlite3.connect(path)
    connection.execute(
        "UPDATE companies SET sales_status = 'Contacted', "
        "sales_owner = 'LM', sales_notes = 'Call in Q3' "
        "WHERE name = 'Alpha GmbH'"
    )
    connection.commit()
    connection.close()
    return path


def test_import_preserves_company_and_sales_fields(
    current_db, gifa_archive,
):
    companies_before = rows(current_db, "SELECT * FROM companies ORDER BY id")
    participations_before = rows(
        current_db,
        "SELECT * FROM exhibition_companies ORDER BY id",
    )
    categories_before = rows(
        current_db, "SELECT * FROM product_categories ORDER BY id"
    )
    groups_before = rows(current_db, "SELECT * FROM product_groups ORDER BY id")

    summary = archive.import_archive(
        gifa_archive, apply=True, database_path=current_db
    )

    assert summary["companies_matched"] == 1
    assert summary["companies_created"] == 2
    companies_after = rows(current_db, "SELECT * FROM companies ORDER BY id")
    assert companies_after[: len(companies_before)] == companies_before
    alpha = companies_after[0]
    assert (alpha["website"], alpha["email"], alpha["telephone"]) == (
        "http://alpha-new.example", "sales@alpha-new.example", "+49 999",
    )
    assert (alpha["sales_status"], alpha["sales_owner"], alpha["sales_notes"]) == (
        "Contacted", "LM", "Call in Q3",
    )
    assert rows(
        current_db,
        "SELECT * FROM exhibition_companies WHERE id <= ? ORDER BY id",
        (len(participations_before),),
    ) == participations_before
    assert rows(
        current_db, "SELECT * FROM product_categories ORDER BY id"
    ) == categories_before
    assert rows(
        current_db, "SELECT * FROM product_groups ORDER BY id"
    ) == groups_before


def test_import_links_2023_participation_to_existing_company(
    current_db, gifa_archive,
):
    archive.import_archive(gifa_archive, apply=True, database_path=current_db)

    alpha = rows(
        current_db,
        "SELECT e.edition, ec.source_exhibitor_id, ec.company_id "
        "FROM exhibition_companies ec JOIN exhibitions e "
        "ON e.id = ec.exhibition_id JOIN companies co "
        "ON co.id = ec.company_id WHERE co.name = 'Alpha GmbH' "
        "ORDER BY e.edition",
    )
    assert [(r["edition"], r["source_exhibitor_id"]) for r in alpha] == [
        (2023, "GMTN2023.1"), (2027, "gifa2027.1"),
    ]
    assert len({r["company_id"] for r in alpha}) == 1
    assert rows(
        current_db,
        "SELECT COUNT(*) AS n FROM exhibition_companies ec "
        "JOIN exhibitions e ON e.id = ec.exhibition_id "
        "WHERE e.edition = 2027",
    )[0]["n"] == 2


def test_import_into_populated_database_is_repeatable(
    current_db, gifa_archive,
):
    archive.import_archive(gifa_archive, apply=True, database_path=current_db)
    before = {
        table: rows(current_db, f"SELECT * FROM {table}")
        for table in ("companies", "exhibition_companies")
    }

    summary = archive.import_archive(
        gifa_archive, apply=True, database_path=current_db
    )

    assert summary["participations_unchanged"] == 3
    for table, expected in before.items():
        assert rows(current_db, f"SELECT * FROM {table}") == expected


def _all_tables(path):
    names = [
        row["name"]
        for row in rows(
            path,
            "SELECT name FROM sqlite_master WHERE type = 'table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name",
        )
    ]
    return {name: rows(path, f"SELECT * FROM {name}") for name in names}


def _fail_on_call(monkeypatch, number):
    real = database.sync_exhibitor
    calls = {"count": 0}

    def flaky(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == number:
            raise RuntimeError("simulated failure")
        return real(*args, **kwargs)

    monkeypatch.setattr(database, "sync_exhibitor", flaky)
    return calls


def test_failed_apply_rolls_back_all_tables(
    tmp_path, gifa_archive, current_db, monkeypatch
):
    before = _all_tables(current_db)
    calls = _fail_on_call(monkeypatch, 2)

    with pytest.raises(RuntimeError, match="simulated failure"):
        archive.import_archive(gifa_archive, apply=True, database_path=current_db)

    assert calls["count"] == 2  # the first record was written, then rolled back
    assert _all_tables(current_db) == before
    assert database._shared_connection is None


def test_failed_apply_into_new_database_leaves_no_data(
    tmp_path, gifa_archive, monkeypatch
):
    target = tmp_path / "fresh" / "md-sync.db"
    _fail_on_call(monkeypatch, 2)

    with pytest.raises(RuntimeError):
        archive.import_archive(gifa_archive, apply=True, database_path=target)

    for table in ("companies", "exhibition_companies", "exhibitions"):
        assert rows(target, f"SELECT * FROM {table}") == []


def test_apply_succeeds_after_a_failed_attempt(
    tmp_path, gifa_archive, current_db, monkeypatch
):
    with monkeypatch.context() as patch:
        _fail_on_call(patch, 2)
        with pytest.raises(RuntimeError):
            archive.import_archive(
                gifa_archive, apply=True, database_path=current_db
            )

    summary = archive.import_archive(
        gifa_archive, apply=True, database_path=current_db
    )
    assert summary["participations_created"] > 0
    repeat = archive.import_archive(
        gifa_archive, apply=True, database_path=current_db
    )
    assert repeat["participations_created"] == 0
    assert repeat["participations_updated"] == 0


def test_normal_connections_still_commit_independently(tmp_path, monkeypatch):
    path = tmp_path / "n" / "md-sync.db"
    path.parent.mkdir()
    with archive._database_target(path):
        database.initialize_database()
        database.get_or_create_exhibition("GIFA", 2027, "GMTN2027.gifa")
        with pytest.raises(RuntimeError):
            with database.get_connection() as connection:
                connection.execute(
                    "UPDATE exhibitions SET edition = 2028"
                )
                raise RuntimeError("boom")
    assert rows(path, "SELECT edition FROM exhibitions")[0]["edition"] == 2027

    with archive._database_target(path):
        with database.get_connection() as connection:
            connection.execute("UPDATE exhibitions SET edition = 2029")
    assert rows(path, "SELECT edition FROM exhibitions")[0]["edition"] == 2029


def test_normal_sync_still_updates_company_fields(current_db):
    populate(
        current_db,
        [record("gifa2027.1", "Alpha GmbH", "Germany", "Berlin",
                label="GIFA 2027", website="http://changed.example")],
        "GIFA", 2027, "GMTN2027.gifa",
    )

    website = rows(
        current_db, "SELECT website FROM companies WHERE name = 'Alpha GmbH'"
    )[0]["website"]
    assert website == "http://changed.example"


def test_cli_import_defaults_to_dry_run(tmp_path, gifa_archive, capsys):
    target = tmp_path / "t" / "md-sync.db"

    code = archive.main(
        ["import", str(gifa_archive), "--database", str(target)]
    )

    assert code == 0
    assert "DRY RUN" in capsys.readouterr().out
    assert not target.exists()


def test_cli_reports_invalid_archive(tmp_path, capsys):
    code = archive.main(["verify", str(tmp_path / "missing")])

    assert code == 1
    assert "ERROR" in capsys.readouterr().err
