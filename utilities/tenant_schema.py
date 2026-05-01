"""
Lightweight, idempotent schema upgrades for tenant SQLite databases.

There's no Alembic migration setup for tenant DBs (each tenant has its own
file, created via SQLAlchemy `create_all`). When a model gains a column, every
existing tenant DB needs an `ALTER TABLE … ADD COLUMN` — this module collects
those one-off upgrades and runs them at app startup against every tenant DB.

Each upgrade is written to be safe to run repeatedly: it inspects the table's
columns first and only runs the ALTER if the column is missing.

Add new upgrades by appending to TENANT_UPGRADES at the bottom of the file.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

from sqlalchemy import create_engine, inspect, text

log = logging.getLogger(__name__)


def _column_exists(engine, table: str, column: str) -> bool:
    insp = inspect(engine)
    if not insp.has_table(table):
        return True  # nothing to migrate; create_all will build the schema
    return column in {c["name"] for c in insp.get_columns(table)}


def add_column_if_missing(table: str, column: str, ddl: str) -> Callable:
    """Return an upgrade callable that adds a column to a table if absent.

    `ddl` is the column definition portion of the ALTER, e.g.
    `INTEGER REFERENCES contacts(id)`.
    """
    def _upgrade(engine, db_path: Path) -> bool:
        if _column_exists(engine, table, column):
            return False
        with engine.begin() as conn:
            conn.execute(text(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {ddl}'))
        log.info("[%s] added column %s.%s", db_path.name, table, column)
        return True

    _upgrade.__name__ = f"add_{table}_{column}"
    return _upgrade


# ----------------------------------------------------------------------------
# All tenant upgrades. Each one is idempotent.
# ----------------------------------------------------------------------------
TENANT_UPGRADES: list[Callable] = [
    # contact_id FK on item_checkouts so checkouts can link to a Contact
    # directly instead of relying on name-string matching.
    add_column_if_missing(
        table="item_checkouts",
        column="contact_id",
        ddl='INTEGER REFERENCES "contacts"("id") ON DELETE SET NULL',
    ),
]


def upgrade_tenant_db(db_path: Path) -> int:
    """Run all pending upgrades against a single tenant DB. Returns the
    number of upgrades that did something (0 = already up to date)."""
    if not db_path.exists():
        return 0
    engine = create_engine(f"sqlite:///{db_path.as_posix()}")
    applied = 0
    try:
        for upgrade in TENANT_UPGRADES:
            try:
                if upgrade(engine, db_path):
                    applied += 1
            except Exception:
                log.exception("[%s] upgrade %s failed", db_path.name, upgrade.__name__)
    finally:
        engine.dispose()
    return applied


def upgrade_all_tenant_dbs(tenant_dbs_dir: str = "tenant_dbs") -> tuple[int, int]:
    """Walk every *.db file in `tenant_dbs_dir` and run pending upgrades.

    Returns (db_count, total_applied)."""
    base = Path(tenant_dbs_dir)
    if not base.exists():
        return 0, 0

    db_count = 0
    total_applied = 0
    for db_path in sorted(base.glob("*.db")):
        db_count += 1
        try:
            total_applied += upgrade_tenant_db(db_path)
        except Exception:
            log.exception("[%s] failed to open for upgrade", db_path.name)

    log.info(
        "Tenant schema check complete: %d db(s) scanned, %d upgrade(s) applied.",
        db_count, total_applied,
    )
    return db_count, total_applied
