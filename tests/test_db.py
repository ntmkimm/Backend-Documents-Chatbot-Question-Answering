import asyncio
import os
from psycopg_pool import AsyncConnectionPool
from dotenv import load_dotenv
load_dotenv() 

# Load DB config from env or defaults
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "notebook")
POSTGRES_HOST = os.getenv("POSTGRES_ADDRESS", "db")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "postgres")

DB_URI = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
print(DB_URI)
connection_kwargs = {
    "autocommit": True,
    "prepare_threshold": None,
}

async def test_db():
    # 🔄 create the pool *inside* the async function
    pool = AsyncConnectionPool(DB_URI, kwargs=connection_kwargs)

    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT version();")
                row = await cur.fetchone()
                print("✅ Connected! PostgreSQL version:", row[0])
    except Exception as e:
        print("❌ Connection failed:", e)
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(test_db())
