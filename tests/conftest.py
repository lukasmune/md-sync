import json
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolated_change_reports(tmp_path, monkeypatch):
    """Keep tests from writing change reports into the real exports folder."""

    import excel_export

    monkeypatch.setattr(excel_export, "CHANGES_DIR", tmp_path / "changes")


@pytest.fixture
def gifa_2027_records():
    fixture_path = Path(__file__).parent / "fixtures" / "gifa_2027_directory.json"
    return json.loads(fixture_path.read_text(encoding="utf-8"))


@pytest.fixture
def fair_associations_2027():
    fixture_path = (
        Path(__file__).parent
        / "fixtures"
        / "fair_associations_2027.json"
    )
    return json.loads(fixture_path.read_text(encoding="utf-8"))
