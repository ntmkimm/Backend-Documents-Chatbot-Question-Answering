"""
Async migration system for Postgres using SQLAlchemy async engine.
"""

import asyncio
from pathlib import Path
from typing import List

from loguru import logger
from sqlalchemy import text

from open_notebook.database.repository import db_connection, repo_query, pg_execute 

class AsyncMigration:
    def __init__(self, statements: List[str]) -> None:
        self.statements = statements

    @classmethod
    def from_file(cls, file_path: str) -> "AsyncMigration":
        """Load and clean SQL file, split into executable statements."""
        raw_content = Path(file_path).read_text()

        # remove comments (both inline and full line)
        clean_lines = []
        for line in raw_content.splitlines():
            if line.strip().startswith("--"):
                continue
            # remove inline comments
            if "--" in line:
                line = line.split("--", 1)[0]
            if line.strip():
                clean_lines.append(line.strip())

        sql_clean = "\n".join(clean_lines)

        # Split by semicolon (drop empties)
        statements = [s.strip() for s in sql_clean.split(";") if s.strip()]
        return cls(statements)

    async def run(self, bump: bool = True) -> None:
        """Execute migration statements, then bump or lower version."""
        try:
            async with db_connection() as session:
                for stmt in self.statements:
                    await session.execute(text(stmt))
                await session.commit()

            if bump:
                await bump_version()
            else:
                await lower_version()

        except Exception as e:
            logger.error(f"Migration failed: {str(e)}")
            raise


class AsyncMigrationRunner:
    def __init__(self, up_migrations: List[AsyncMigration], down_migrations: List[AsyncMigration]):
        self.up_migrations = up_migrations
        self.down_migrations = down_migrations

    async def run_all(self):
        current_version = await get_latest_version()
        for i in range(current_version, len(self.up_migrations)):
            logger.info(f"Running migration {i + 1}")
            await self.up_migrations[i].run(bump=True)

    async def run_one_up(self):
        current_version = await get_latest_version()
        if current_version < len(self.up_migrations):
            logger.info(f"Running migration {current_version + 1}")
            await self.up_migrations[current_version].run(bump=True)

    async def run_one_down(self):
        current_version = await get_latest_version()
        if current_version > 0:
            logger.info(f"Rolling back migration {current_version}")
            await self.down_migrations[current_version - 1].run(bump=False)


class AsyncMigrationManager:
    def __init__(self):
        self.up_migrations = [
            AsyncMigration.from_file("migrations/all.sql"),  # your converted schema
        ]
        self.down_migrations = []
        self.runner = AsyncMigrationRunner(self.up_migrations, self.down_migrations)

    async def get_current_version(self) -> int:
        return await get_latest_version()

    async def needs_migration(self) -> bool:
        current_version = await self.get_current_version()
        return current_version < len(self.up_migrations)

    async def run_migration_up(self):
        current_version = await self.get_current_version()
        logger.info(f"Current version before migration: {current_version}")

        if await self.needs_migration():
            try:
                await self.runner.run_all()
                new_version = await self.get_current_version()
                logger.info(f"Migration successful. New version: {new_version}")
            except Exception as e:
                logger.error(f"Migration failed: {str(e)}")
                raise
        else:
            logger.info("Database is already at the latest version")


async def ensure_migrations_table():
    """Make sure the _sbl_migrations table exists."""
    await pg_execute("""
    CREATE TABLE IF NOT EXISTS _sbl_migrations (
        version INT PRIMARY KEY,
        applied_at TIMESTAMPTZ DEFAULT now()
    )
    """)


async def get_latest_version() -> int:
    try:
        await ensure_migrations_table()
        rows = await repo_query("SELECT version FROM _sbl_migrations ORDER BY version;")
        if not rows:
            return 0
        return max(r["version"] for r in rows)
    except Exception:
        return 0


async def bump_version() -> None:
    await ensure_migrations_table()
    current_version = await get_latest_version()
    new_version = current_version + 1
    await pg_execute(
        "INSERT INTO _sbl_migrations (version, applied_at) VALUES (:version, now())",
        {"version": new_version},
    )


async def lower_version() -> None:
    await ensure_migrations_table()
    current_version = await get_latest_version()
    if current_version > 0:
        await pg_execute("DELETE FROM _sbl_migrations WHERE version = :version", {"version": current_version})


async def migrate_all():
    mgr = AsyncMigrationManager()
    print("Current version before:", await mgr.get_current_version())
    await mgr.run_migration_up()
    print("Done. Current version after:", await mgr.get_current_version())

