from open_notebook.database.async_migrate import AsyncMigrationManager

import asyncio
if __name__ == "__main__":
    mgr = AsyncMigrationManager()
    print("Current version before:", asyncio.run(mgr.get_current_version()))
    asyncio.run(mgr.run_migration_up())
    print("Done. Current version after:", asyncio.run(mgr.get_current_version()))