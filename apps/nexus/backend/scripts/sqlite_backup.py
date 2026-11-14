"""Offline SQLite backup/restore to a NEW path. Never overwrites a database.

Usage: python -m scripts.sqlite_backup {backup,restore} SOURCE DESTINATION
Keep the original SECRET_KEY separately; encrypted links depend on it.
"""
from __future__ import annotations

import argparse
import os
import sqlite3
from pathlib import Path


def copy_database(source: Path, destination: Path) -> None:
    source = source.resolve(strict=True)
    if not source.is_file():
        raise ValueError("Source must be a database file")
    destination = destination.absolute()
    with sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as origin:
        if origin.execute("PRAGMA integrity_check").fetchone() != ("ok",):
            raise ValueError("Source failed SQLite integrity check")
        # Exclusive creation also rejects an existing symlink or same source.
        descriptor = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(descriptor)
        try:
            with sqlite3.connect(destination) as target:
                origin.backup(target)
                if target.execute("PRAGMA integrity_check").fetchone() != ("ok",):
                    raise ValueError("Backup failed SQLite integrity check")
        except Exception:
            destination.unlink(missing_ok=True)
            raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["backup", "restore"])
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    copy_database(args.source, args.destination)
    print(f"{args.action}: integrity verified; new database created")


if __name__ == "__main__":
    main()
