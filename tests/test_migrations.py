"""Exercise real migrations in subprocesses, separate from API test engines."""
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
BASELINE = "1718f08c0454"
HEAD = "46577a49b999"


def migrate(db_path, operation, revision, *, succeeds=True):
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    result = subprocess.run(
        [sys.executable, "-m", "alembic", operation, revision],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=30,
    )
    if succeeds:
        assert result.returncode == 0, result.stdout + result.stderr
    else:
        assert result.returncode != 0
    return result


@pytest.fixture
def migration_database(tmp_path):
    path = tmp_path / "migration.db"
    migrate(path, "upgrade", BASELINE)
    with sqlite3.connect(path) as db:
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("INSERT INTO inventories VALUES (1, 'Inventory')")
        db.execute("INSERT INTO products VALUES ('p', 'Product')")
        db.execute("INSERT INTO users VALUES (1, 'user', 'unused')")
        db.execute("INSERT INTO customers VALUES (1, 1, 'Customer', NULL, NULL)")
        db.execute("INSERT INTO orders VALUES (1, 1, 1, 'confirmed')")
        db.execute("INSERT INTO order_items VALUES (1, 'p', 2, 10)")
    return path


def test_upgrade_preserves_orders_and_enforces_customer_identity(migration_database):
    migrate(migration_database, "upgrade", "head")
    with sqlite3.connect(migration_database) as db:
        db.execute("PRAGMA foreign_keys=ON")
        assert db.execute("SELECT customer_id, directory_customer_id FROM orders").fetchall() == [(1, None)]
        assert db.execute("SELECT * FROM order_items").fetchall() == [(1, 'p', 2, 10)]
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
        db.execute("INSERT INTO orders (id, directory_customer_id, inventory_id, status) VALUES (2, 1, 1, 'confirmed')")
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("INSERT INTO orders (id, inventory_id, status) VALUES (3, 1, 'confirmed')")
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("INSERT INTO orders (id, directory_customer_id, inventory_id, status) VALUES (4, 999, 1, 'confirmed')")


def test_downgrade_and_reupgrade_preserve_order_items(migration_database):
    migrate(migration_database, "upgrade", "head")
    migrate(migration_database, "downgrade", BASELINE)
    with sqlite3.connect(migration_database) as db:
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"carts", "cart_items"} <= tables
        assert db.execute("SELECT * FROM order_items").fetchall() == [(1, 'p', 2, 10)]
    migrate(migration_database, "upgrade", "head")


def test_downgrade_refuses_offline_orders_without_changing_schema(migration_database):
    migrate(migration_database, "upgrade", "head")
    with sqlite3.connect(migration_database) as db:
        db.execute("INSERT INTO orders (id, directory_customer_id, inventory_id, status) VALUES (2, 1, 1, 'confirmed')")
    result = migrate(migration_database, "downgrade", BASELINE, succeeds=False)
    assert "Cannot downgrade while offline orders exist" in result.stderr
    with sqlite3.connect(migration_database) as db:
        assert db.execute("SELECT version_num FROM alembic_version").fetchone() == (HEAD,)
        assert db.execute("SELECT directory_customer_id FROM orders WHERE id=2").fetchone() == (1,)


def test_migration_rejects_existing_broken_references(migration_database):
    with sqlite3.connect(migration_database) as db:
        db.execute("INSERT INTO order_items VALUES (999, 'p', 1, 10)")
    result = migrate(migration_database, "upgrade", "head", succeeds=False)
    assert "foreign-key violations before migration" in result.stderr
    with sqlite3.connect(migration_database) as db:
        assert db.execute("SELECT version_num FROM alembic_version").fetchone() == (BASELINE,)
        assert db.execute("SELECT name FROM sqlite_master WHERE name='carts'").fetchone() == ('carts',)
