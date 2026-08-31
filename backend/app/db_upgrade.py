"""Idempotent SQLite column-adder.

SQLite has no migration tooling in this project, and existing `fieldbot.db`
files must keep working as `models.py` grows new columns on existing tables
(ARD §3). `Base.metadata.create_all` only creates missing *tables* — it never
alters an existing one — so any new column on `projects` or `vendors` needs to
be added by hand, once, via `ALTER TABLE ... ADD COLUMN`.

`run_upgrade` reads `PRAGMA table_info(<table>)` for each table this module
knows about and adds only the columns that are missing, so it's safe to call
on every startup (a fresh DB created by `create_all` already has every column,
so every ALTER is skipped; an old DB gets exactly the columns it's missing).

Call this from the lifespan in main.py, right after `Base.metadata.create_all`.
"""
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

logger = logging.getLogger("fieldbot.db_upgrade")

# table -> [(column_name, ddl_type_and_default), ...]
# Keep in lockstep with the additive columns in models.py (ARD §3.1, §3.2).
# SQLite ADD COLUMN requires a *constant* default (no expressions), and JSON
# columns are stored as TEXT — a default of '[]'/'{}' matches SQLAlchemy's
# JSON type reading them back as list/dict.
COLUMNS: dict[str, list[tuple[str, str]]] = {
    "projects": [
        ("state", "VARCHAR NOT NULL DEFAULT 'Selangor'"),
        ("system_type", "VARCHAR NOT NULL DEFAULT 'on_grid'"),
        ("monthly_consumption_kwh", "NUMERIC(10, 2)"),
        ("tariff_category", "VARCHAR NOT NULL DEFAULT 'domestic'"),
        ("roof_area_m2", "NUMERIC(10, 2)"),
        ("roof_tilt_deg", "NUMERIC(5, 2)"),
        ("roof_azimuth_deg", "NUMERIC(5, 2)"),
        ("shading_factor", "NUMERIC(4, 3)"),
        ("obstructions", "JSON NOT NULL DEFAULT '[]'"),
    ],
    "vendors": [
        ("bnef_tier", "INTEGER"),
        ("brands_carried", "JSON NOT NULL DEFAULT '[]'"),
        ("country", "VARCHAR NOT NULL DEFAULT 'Malaysia'"),
        ("quote_currency", "VARCHAR NOT NULL DEFAULT 'MYR'"),
    ],
}


async def run_upgrade(conn: AsyncConnection) -> None:
    for table, columns in COLUMNS.items():
        result = await conn.execute(text(f"PRAGMA table_info({table})"))
        existing = {row[1] for row in result.fetchall()}  # row[1] = column name
        for name, ddl in columns:
            if name in existing:
                continue
            logger.info("db_upgrade: adding %s.%s", table, name)
            await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
