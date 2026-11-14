import os
import sqlite3

import pytest

from scripts.sqlite_backup import copy_database


def test_backup_restore_preserves_data_and_integrity(tmp_path):
    source, backup, restored = [tmp_path / name for name in ("source.db", "backup.db", "restored.db")]
    with sqlite3.connect(source) as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("CREATE TABLE items(value TEXT)")
        db.execute("INSERT INTO items VALUES ('unchanged')")
        db.commit()
        copy_database(source, backup)
    copy_database(backup, restored)
    with sqlite3.connect(restored) as db:
        assert db.execute("SELECT value FROM items").fetchall() == [("unchanged",)]
        assert db.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    if os.name == "posix":
        assert backup.stat().st_mode & 0o777 == 0o600


def test_restore_refuses_overwrite_and_symlink(tmp_path):
    source = tmp_path / "source.db"
    with sqlite3.connect(source) as db:
        db.execute("CREATE TABLE items(value TEXT)")
    with pytest.raises(FileExistsError):
        copy_database(source, source)
    link = tmp_path / "link.db"
    link.symlink_to(source)
    with pytest.raises(FileExistsError):
        copy_database(source, link)


def test_invalid_backup_does_not_create_destination(tmp_path):
    bad, target = tmp_path / "bad.db", tmp_path / "target.db"
    bad.write_bytes(b"this is not a database")
    with pytest.raises(sqlite3.DatabaseError):
        copy_database(bad, target)
    assert not target.exists()
