import asyncio
import os
from dotenv import load_dotenv
from pymilvus import connections, utility
from sqlalchemy import inspect

from open_notebook.database.async_migrate import down_migrate_all
from open_notebook.database.repository import db_connection

load_dotenv()

async def list_tables():
    async with db_connection() as session:
        async with session.bind.connect() as conn:
            def do_inspect(sync_conn):
                inspector = inspect(sync_conn)
                return inspector.get_table_names()

            tables = await conn.run_sync(do_inspect)
            print("Tables:", tables)
            return tables

async def main():
    connections.connect(
        host=os.getenv("MILVUS_ADDRESS"),
        port=os.getenv("MILVUS_PORT")
    )

    # List Milvus collections
    collections = utility.list_collections()

    print("Before down migrate: ")
    await list_tables()

    print("Down migrate: ")
    for collection_name in collections:
        try:
            if collection_name not in ['agent_memory1', 'source_embedding']:
                continue
            utility.drop_collection(collection_name)
            print(f"Collection {collection_name} deleted successfully.")
        except Exception as e:
            print(f"Failed to delete collection {collection_name}: {e}")

    await down_migrate_all()

    print("After down migrate: ")
    await list_tables()

if __name__ == "__main__":
    asyncio.run(main())
