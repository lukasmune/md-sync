"""Versioned historical archives and the explicit historical import.

An archive is a directory ``archive/<FAIR>/<edition>/`` holding a
``manifest.json`` and the data files it lists.  Archives are immutable:
exporting never overwrites an existing archive.  Importing reads only the
archive path it is given and never contacts the live API.

Usage:
    python archive.py export --all --edition 2023
    python archive.py verify archive/GIFA/2023
    python archive.py import archive/GIFA/2023            (dry run)
    python archive.py import archive/GIFA/2023 --apply
"""

import argparse
import hashlib
import json
import re
import shutil
import sqlite3
import sys
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import config
import database

FORMAT_VERSION = 1
SUPPORTED_SOURCES = ("db-export",)
MANIFEST_NAME = "manifest.json"
EXHIBITORS_FILE = "exhibitors.json"
DEFAULT_ARCHIVE_ROOT = config.BASE_DIR / "archive"

DB_EXPORT_LIMITATIONS = [
    "Reconstructed from the md-sync database; not an original API snapshot.",
    "Raw API payloads, profile slices and unstored fields are not recovered.",
    "The original capture date is unknown (captured_at is null).",
    "Company contact details (website, email, telephone) are company-level "
    "values and may have been updated by later syncs after 2023.",
    "Product groups are labelled as currently stored in the database.",
    "No co-exhibitor relationships exist in the source data; every record "
    "has role 'direct'.",
]

MANIFEST_KEYS = (
    "format_version",
    "fair",
    "edition",
    "event_code",
    "event_label",
    "source",
    "captured_at",
    "record_count",
    "files",
)


class ArchiveError(Exception):
    """Raised when an archive is missing, inconsistent or unsafe to import."""


def expected_identity(fair, edition):
    """Return the (event_label, event_code) implied by the configuration."""

    if fair not in config.EVENTS:
        raise ArchiveError(f"Unknown fair: {fair!r}")
    label = f"{fair} {edition}"
    code = re.sub(
        r"^GMTN\d{4}",
        f"GMTN{edition}",
        config.EVENTS[fair]["event_code"],
    )
    return label, code


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _dump(data, sort_keys=False):
    return json.dumps(
        data, ensure_ascii=False, indent=1, sort_keys=sort_keys
    ).encode("utf-8")


def archive_dir(fair, edition, root=DEFAULT_ARCHIVE_ROOT):
    return Path(root) / fair / str(edition)


# --------------------------------------------------------------------- export


def _categories_for(connection, participation_id):
    categories = []
    rows = connection.execute(
        """
        SELECT pc.id, pc.source_id, pc.label, pc.catalog_index,
               pc.hierarchy_json
        FROM exhibition_company_categories ecc
        JOIN product_categories pc ON pc.id = ecc.product_category_id
        WHERE ecc.exhibition_company_id = ?
        ORDER BY pc.source_id
        """,
        (participation_id,),
    ).fetchall()
    for row in rows:
        hierarchy = json.loads(row["hierarchy_json"] or "[]")
        hierarchy_ids = {item.get("id") for item in hierarchy}
        product_list = [
            {"id": group["source_id"], "label": group["label"]}
            for group in connection.execute(
                """
                SELECT pg.source_id, pg.label
                FROM product_category_groups pcg
                JOIN product_groups pg ON pg.id = pcg.product_group_id
                WHERE pcg.product_category_id = ?
                ORDER BY pcg.position
                """,
                (row["id"],),
            )
            if group["source_id"] not in hierarchy_ids
        ]
        category = {
            "id": row["source_id"],
            "label": row["label"],
            "catalogIndex": row["catalog_index"],
            "hierarchy": hierarchy,
        }
        if product_list:
            category["productList"] = product_list
        categories.append(category)
    return categories


def reconstruct_records(connection, exhibition_id):
    """Build import-ready records from stored participations (read-only)."""

    rows = connection.execute(
        """
        SELECT ec.*, co.name, co.country, co.city, co.website, co.email,
               co.telephone
        FROM exhibition_companies ec
        JOIN companies co ON co.id = ec.company_id
        WHERE ec.exhibition_id = ?
        ORDER BY ec.source_exhibitor_id
        """,
        (exhibition_id,),
    ).fetchall()
    records = []
    for row in rows:
        record = {
            "type": "profile",
            "exh": row["source_exhibitor_id"],
            "exhSeoId": row["seo_id"],
            "name": row["name"],
            "country": row["country"],
            "city": row["city"],
            "website": row["website"],
            "email": row["email"],
            "telephone": row["telephone"],
            "location": row["location"],
            "premium": bool(row["premium"]),
            "tags": json.loads(row["tags_json"] or "[]"),
            "eventIcons": json.loads(row["event_icons_json"] or "[]"),
            "exhibitor_role": row["exhibitor_role"],
            "parent_source_exhibitor_id": row["parent_source_exhibitor_id"],
            "categories": _categories_for(connection, row["id"]),
            "_db_timestamps": {
                "first_seen_at": row["first_seen_at"],
                "last_seen_at": row["last_seen_at"],
                "scraped_at": row["scraped_at"],
            },
        }
        records.append(record)
    return records


def export_archive(fair, edition, database_path, root=DEFAULT_ARCHIVE_ROOT):
    """Write an immutable db-export archive; the database is opened read-only."""

    label, code = expected_identity(fair, edition)
    target = archive_dir(fair, edition, root)
    if target.exists():
        raise ArchiveError(
            f"Archive already exists and is immutable: {target}"
        )
    database_path = Path(database_path)
    if not database_path.exists():
        raise ArchiveError(f"Database not found: {database_path}")

    connection = sqlite3.connect(
        f"{database_path.resolve().as_uri()}?mode=ro", uri=True
    )
    connection.row_factory = sqlite3.Row
    try:
        exhibition = connection.execute(
            "SELECT id, event_name, edition, event_code FROM exhibitions "
            "WHERE event_code = ?",
            (code,),
        ).fetchone()
        if exhibition is None:
            raise ArchiveError(f"No exhibition {code} in {database_path}")
        if (exhibition["event_name"], exhibition["edition"]) != (
            fair,
            edition,
        ):
            raise ArchiveError(
                f"Exhibition {code} does not match {fair} {edition}"
            )
        records = reconstruct_records(connection, exhibition["id"])
    finally:
        connection.close()

    if not records:
        raise ArchiveError(f"No participations stored for {code}")
    for record in records:
        labels = {icon.get("label") for icon in record["eventIcons"]}
        if label not in labels:
            raise ArchiveError(
                f"Stored record {record['exh']} is not labelled {label!r}; "
                "refusing to archive it."
            )

    data = _dump(records)
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".staging-", dir=target.parent))
    try:
        (staging / EXHIBITORS_FILE).write_bytes(data)
        manifest = {
            "format_version": FORMAT_VERSION,
            "fair": fair,
            "edition": edition,
            "event_code": code,
            "event_label": label,
            "source": "db-export",
            "is_raw_api_snapshot": False,
            "captured_at": None,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "record_count": len(records),
            "files": [
                {
                    "path": EXHIBITORS_FILE,
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "record_count": len(records),
                }
            ],
            "limitations": DB_EXPORT_LIMITATIONS,
        }
        (staging / MANIFEST_NAME).write_bytes(
            _dump(manifest, sort_keys=True) + b"\n"
        )
        _rename_staging(staging, target)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return target


RENAME_ATTEMPTS = 5
RENAME_DELAY_SECONDS = 0.2


def _rename_staging(staging, target):
    """Rename the staging directory, retrying transient Windows lock errors.

    Only PermissionError is retried, and never when the target already exists,
    so an existing archive can never be replaced. The final error is re-raised.
    """

    for attempt in range(1, RENAME_ATTEMPTS + 1):
        if target.exists():
            raise ArchiveError(f"Archive already exists: {target}")
        try:
            staging.rename(target)
            return
        except PermissionError:
            if attempt == RENAME_ATTEMPTS:
                raise
            time.sleep(RENAME_DELAY_SECONDS)


# ----------------------------------------------------------------- validation


def load_archive(path):
    """Validate an archive and return ``(manifest, records)``."""

    path = Path(path)
    manifest_path = path / MANIFEST_NAME
    if not manifest_path.is_file():
        raise ArchiveError(f"Archive manifest not found: {manifest_path}")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except ValueError as error:
        raise ArchiveError(f"Invalid manifest JSON: {error}") from error
    if not isinstance(manifest, dict):
        raise ArchiveError("Manifest must be a JSON object.")

    missing = [key for key in MANIFEST_KEYS if key not in manifest]
    if missing:
        raise ArchiveError(f"Manifest is missing keys: {missing}")
    if manifest["format_version"] != FORMAT_VERSION:
        raise ArchiveError(
            f"Unsupported archive format version: {manifest['format_version']}"
        )
    if manifest["source"] not in SUPPORTED_SOURCES:
        raise ArchiveError(f"Unsupported archive source: {manifest['source']}")

    fair, edition = manifest["fair"], manifest["edition"]
    if not isinstance(edition, int) or isinstance(edition, bool):
        raise ArchiveError("Manifest edition must be an integer.")
    label, code = expected_identity(fair, edition)
    if manifest["event_label"] != label or manifest["event_code"] != code:
        raise ArchiveError(
            f"Manifest event identity {manifest['event_label']!r}/"
            f"{manifest['event_code']!r} does not match {label!r}/{code!r}."
        )
    if edition >= config.GMTN_EDITION:
        raise ArchiveError(
            f"Edition {edition} is not historical; the configured current "
            f"edition is {config.GMTN_EDITION}."
        )

    files = manifest["files"]
    if not isinstance(files, list) or len(files) != 1:
        raise ArchiveError("Manifest must list exactly one data file.")
    entry = files[0]
    relative = Path(str(entry.get("path", "")))
    if relative.is_absolute() or ".." in relative.parts or not relative.name:
        raise ArchiveError(f"Unsafe data file path: {entry.get('path')!r}")
    data_path = path / relative
    if not data_path.is_file():
        raise ArchiveError(f"Archive data file not found: {data_path}")
    if _sha256(data_path) != entry.get("sha256"):
        raise ArchiveError(f"Checksum mismatch for {relative}")

    try:
        records = json.loads(data_path.read_text(encoding="utf-8"))
    except ValueError as error:
        raise ArchiveError(f"Invalid data JSON: {error}") from error
    if not isinstance(records, list):
        raise ArchiveError("Archive data must be a list of records.")
    if not (
        len(records) == manifest["record_count"] == entry.get("record_count")
    ):
        raise ArchiveError("Record count does not match the manifest.")

    _validate_records(records, fair, label)
    return manifest, records


def _validate_records(records, fair, label):
    seen = set()
    same_fair = re.compile(rf"^{re.escape(fair)} \d{{4}}$")
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise ArchiveError(f"Record {index} is not an object.")
        exhibitor_id = record.get("exh")
        if not exhibitor_id or not record.get("name"):
            raise ArchiveError(f"Record {index} lacks 'exh' or 'name'.")
        if exhibitor_id in seen:
            raise ArchiveError(f"Duplicate exhibitor ID {exhibitor_id}.")
        seen.add(exhibitor_id)
        icons = record.get("eventIcons")
        labels = {
            icon.get("label")
            for icon in icons or []
            if isinstance(icon, dict)
        }
        if label not in labels:
            raise ArchiveError(
                f"Record {exhibitor_id} is not labelled {label!r} "
                f"(found {sorted(map(str, labels))})."
            )
        conflicting = sorted(
            item for item in labels
            if isinstance(item, str) and same_fair.match(item) and item != label
        )
        if conflicting:
            raise ArchiveError(
                f"Record {exhibitor_id} also carries {conflicting}, which "
                f"contradicts the archive edition {label!r}."
            )


# --------------------------------------------------------------------- import


@contextmanager
def _database_target(path):
    path = Path(path)
    saved = (database.DATABASE_PATH, database.DATA_DIR)
    database.DATABASE_PATH = path
    database.DATA_DIR = path.parent
    try:
        yield
    finally:
        database.DATABASE_PATH, database.DATA_DIR = saved


def _run_import(manifest, records):
    database.initialize_database()
    with database.get_connection() as connection:
        existing = connection.execute(
            "SELECT event_name, edition FROM exhibitions WHERE event_code = ?",
            (manifest["event_code"],),
        ).fetchone()
    if existing is not None and (
        existing["event_name"],
        existing["edition"],
    ) != (manifest["fair"], manifest["edition"]):
        raise ArchiveError(
            f"Exhibition {manifest['event_code']} already exists as "
            f"{existing['event_name']} {existing['edition']}."
        )

    with database.transaction():
        return _import_records(manifest, records, existing)


def _import_records(manifest, records, existing):
    exhibition_id = database.get_or_create_exhibition(
        manifest["fair"], manifest["edition"], manifest["event_code"]
    )
    summary = {
        "exhibition_created": existing is None,
        "records": len(records),
        "companies_created": 0,
        "companies_matched": 0,
        "participations_created": 0,
        "participations_updated": 0,
        "participations_unchanged": 0,
    }
    for record in records:
        result = database.sync_exhibitor(
            record, exhibition_id, run_id=None, historical=True
        )
        key = "companies_created" if result["created"] else "companies_matched"
        summary[key] += 1
        if result["participation_created"]:
            summary["participations_created"] += 1
        elif result["participation_updated"]:
            summary["participations_updated"] += 1
        else:
            summary["participations_unchanged"] += 1
    return summary


def import_archive(path, apply=False, database_path=None):
    """Import an archive. Without ``apply`` only a copy of the DB is written."""

    manifest, records = load_archive(path)
    target = Path(database_path or config.DATABASE_PATH)

    if apply:
        with _database_target(target):
            summary = _run_import(manifest, records)
    else:
        with tempfile.TemporaryDirectory(prefix="md-sync-dry-run-") as temp:
            scratch = Path(temp) / "md-sync.db"
            if target.exists():
                source = sqlite3.connect(
                    f"{target.resolve().as_uri()}?mode=ro", uri=True
                )
                copy = sqlite3.connect(scratch)
                try:
                    source.backup(copy)
                finally:
                    copy.close()
                    source.close()
            with _database_target(scratch):
                summary = _run_import(manifest, records)

    summary.update(
        applied=apply,
        fair=manifest["fair"],
        edition=manifest["edition"],
        database=str(target),
    )
    return summary


# ------------------------------------------------------------------------ CLI


def _parser():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)

    export = sub.add_parser("export", help="Reconstruct archives from the DB")
    group = export.add_mutually_exclusive_group(required=True)
    group.add_argument("--fair", choices=sorted(config.EVENTS))
    group.add_argument("--all", action="store_true")
    export.add_argument("--edition", type=int, required=True)
    export.add_argument("--database", default=str(config.DATABASE_PATH))
    export.add_argument("--archive-root", default=str(DEFAULT_ARCHIVE_ROOT))

    verify = sub.add_parser("verify", help="Validate an archive")
    verify.add_argument("path")

    run = sub.add_parser("import", help="Import an archive (dry run default)")
    run.add_argument("path")
    run.add_argument("--apply", action="store_true")
    run.add_argument("--database", default=str(config.DATABASE_PATH))
    return parser


def main(argv=None):
    args = _parser().parse_args(argv)
    try:
        if args.command == "export":
            fairs = sorted(config.EVENTS) if args.all else [args.fair]
            for fair in fairs:
                target = export_archive(
                    fair, args.edition, args.database, args.archive_root
                )
                print(f"Exported {target}")
        elif args.command == "verify":
            manifest, records = load_archive(args.path)
            print(
                f"OK: {manifest['event_label']} ({manifest['event_code']}), "
                f"{len(records)} records, source={manifest['source']}"
            )
        else:
            summary = import_archive(
                args.path, apply=args.apply, database_path=args.database
            )
            mode = "APPLIED" if summary["applied"] else "DRY RUN (no changes)"
            print(f"{mode}: {summary['fair']} {summary['edition']} "
                  f"-> {summary['database']}")
            for key, value in summary.items():
                if key not in {"applied", "fair", "edition", "database"}:
                    print(f"  {key}: {value}")
    except ArchiveError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
