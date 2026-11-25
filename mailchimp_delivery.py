"""Copy the Mailchimp export to the shared drive in the team's folder layout.

``mailchimp_2026-11-25_090917.xlsx`` becomes
``<delivery dir>/Export 25112026/Export_2026-11-25_090917.xlsx``. The local
file stays in ``exports/mailchimp`` as the original.
"""

import os
import re
import shutil
from datetime import datetime
from pathlib import Path

from config import MAILCHIMP_DELIVERY_DIR
from mailchimp_export import MAILCHIMP_DIR, export_mailchimp_list

_NAME_PATTERN = re.compile(r"^mailchimp_(\d{4}-\d{2}-\d{2})_(\d{6})\.xlsx$")


def delivery_names(source):
    """Return (folder name, file name) for an export file."""

    source = Path(source)
    match = _NAME_PATTERN.match(source.name)
    if match:
        stamp = datetime.strptime(
            f"{match.group(1)}_{match.group(2)}", "%Y-%m-%d_%H%M%S"
        )
    else:
        stamp = datetime.fromtimestamp(source.stat().st_mtime)
    return (
        f"Export {stamp:%d%m%Y}",
        f"Export_{stamp:%Y-%m-%d_%H%M%S}.xlsx",
    )


def deliver_export(source, destination_root=None):
    """Copy an export into its dated folder; never overwrite a file.

    The file is written under a temporary name and renamed, so a partial
    copy never appears in the shared folder. Raises OSError when the drive is
    unavailable and FileExistsError if the delivered file already exists.
    """

    source = Path(source)
    root = Path(destination_root or MAILCHIMP_DELIVERY_DIR)
    if not root.is_dir():
        raise FileNotFoundError(f"Delivery folder not reachable: {root}")
    folder_name, file_name = delivery_names(source)
    folder = root / folder_name
    folder.mkdir(exist_ok=True)
    target = folder / file_name
    if target.exists():
        raise FileExistsError(f"Already delivered: {target}")
    temporary = folder / (file_name + ".part")
    try:
        shutil.copy2(source, temporary)
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()
    return target


def latest_export(output_dir=MAILCHIMP_DIR):
    """Return the newest regular export file (rebuilt files are skipped)."""

    files = sorted(
        path for path in Path(output_dir).glob("mailchimp_*.xlsx")
        if _NAME_PATTERN.match(path.name)
    )
    return files[-1] if files else None


def publish(output_dir=MAILCHIMP_DIR, destination_root=None):
    """Export pending contacts and copy the file to the shared drive.

    Returns a process exit code: 0 on success or when nothing is new, 1 when
    the copy failed. The export is already recorded in that case; the local
    file is kept and ``deliver_latest`` retries the copy.
    """

    path = export_mailchimp_list(output_dir)
    if path is None:
        print("No new Mailchimp contacts")
        return 0
    print(path)
    return _deliver_and_report(path, destination_root)


def deliver_latest(output_dir=MAILCHIMP_DIR, destination_root=None):
    """Copy the newest local export to the shared drive (retry helper)."""

    path = latest_export(output_dir)
    if path is None:
        print("No Mailchimp export found to deliver")
        return 1
    return _deliver_and_report(path, destination_root)


def _deliver_and_report(path, destination_root):
    try:
        target = deliver_export(path, destination_root)
    except OSError as error:
        print(f"Delivery FAILED: {error}")
        print(f"The export is saved locally: {path}")
        print("Retry with: .\\md-sync.ps1 mailchimp-deliver")
        return 1
    print(f"Delivered: {target}")
    return 0
