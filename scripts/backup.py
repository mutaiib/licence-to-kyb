"""Back up the databases of a data directory (make backup).

    python3 scripts/backup.py DATA_DIR OUT_DIR

Copies every ``*.sqlite3`` file in DATA_DIR (the run database and the checkpoints) into a new
folder OUT_DIR/<UTC time>/ with SQLite's online backup API, which is safe while the app is
writing (a plain file copy of a database in WAL mode is not). Exits with an error when DATA_DIR
holds no database, so a wrong path never looks like a successful backup.

The encrypted files (DATA_DIR/files/) are not copied: they are useless without the database
and the Fernet keys, and they are large. Back them up with the volume if needed.
"""

from __future__ import annotations

import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path


def backup(data_dir: Path, out_dir: Path) -> list[Path]:
    databases = sorted(data_dir.glob("*.sqlite3"))
    if not databases:
        raise SystemExit(f"no *.sqlite3 database in {data_dir}: nothing backed up")
    target = out_dir / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    target.mkdir(parents=True, exist_ok=False)
    copies = []
    for database in databases:
        copy = target / database.name
        with sqlite3.connect(database) as source, sqlite3.connect(copy) as dest:
            source.backup(dest)
        copies.append(copy)
    return copies


def main() -> None:
    args = sys.argv[1:]
    if len(args) != len(("DATA_DIR", "OUT_DIR")):
        raise SystemExit(__doc__)
    data_dir, out_dir = (Path(a) for a in args)
    for copy in backup(data_dir, out_dir):
        print(f"ok {copy}")


if __name__ == "__main__":
    main()
