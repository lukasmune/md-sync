import database


def test_first_seen_is_preserved_and_last_seen_updates(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DATABASE_PATH", tmp_path / "test.db")
    monkeypatch.setattr(database, "DATA_DIR", tmp_path)
    database.initialize_database()
    exhibition_id = database.get_or_create_exhibition(
        "GIFA", 2023, "GMTN2023.gifa"
    )

    times = iter(
        [
            "2026-10-06T08:00:00+00:00",
            "2026-10-06T08:00:00+00:00",
            "2026-10-07T08:00:00+00:00",
            "2026-10-07T08:00:00+00:00",
        ]
    )
    monkeypatch.setattr(database, "utc_now", lambda: next(times))
    record = {"exh": "EXH-1", "name": "Example Foundry GmbH"}
    database.sync_exhibitor(record, exhibition_id)
    database.sync_exhibitor(record, exhibition_id)

    with database.get_connection() as connection:
        company = connection.execute(
            "SELECT created_at, updated_at FROM companies"
        ).fetchone()
        participation = connection.execute(
            "SELECT first_seen_at, last_seen_at FROM exhibition_companies"
        ).fetchone()

    assert company["created_at"] == "2026-10-06T08:00:00+00:00"
    assert company["updated_at"] == "2026-10-07T08:00:00+00:00"
    assert participation["first_seen_at"] == "2026-10-06T08:00:00+00:00"
    assert participation["last_seen_at"] == "2026-10-07T08:00:00+00:00"
