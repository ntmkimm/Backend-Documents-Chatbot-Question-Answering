
import os
import asyncio
from contextlib import asynccontextmanager
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from pathlib import Path
import pandas as pd

load_dotenv()

def get_postgres_url(): 
    '''
    return async postgres url engine for upload db
    '''
    POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "notebook")
    POSTGRES_HOST = os.getenv("POSTGRES_ADDRESS", "db")
    POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
    POSTGRES_DB = os.getenv("POSTGRES_DB", "postgres")
    DB_URI = f"postgresql+asyncpg://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
    return DB_URI

_engine: Optional[AsyncEngine] = None
_session_factory: Optional[sessionmaker] = None

def _ensure_engine() -> AsyncEngine:
    global _engine, _session_factory
    if _engine is None:
        _engine = create_async_engine(
            get_postgres_url(),
            pool_pre_ping=True,
            future=True,
        )
        _session_factory = sessionmaker(
            _engine, expire_on_commit=False, class_=AsyncSession
        )
    return _engine

@asynccontextmanager
async def pg_session() -> AsyncSession:
    _ensure_engine()
    assert _session_factory is not None
    async with _session_factory() as session:
        try:
            yield session
        finally:
            # Session đóng tự động bởi context
            ...

async def pg_query(sql: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """
    Chạy SELECT và trả về list[dict].
    """
    async with pg_session() as s:
        res = await s.execute(text(sql), params or {})
        # result.mappings() - trả về MappingResult (dict-like rows)
        rows = res.mappings().all()
        return [dict(r) for r in rows]

async def pg_execute(sql: str, params: Optional[Dict[str, Any]] = None) -> int:
    """
    Chạy DDL/DML (INSERT/UPDATE/DELETE/CREATE/…) - trả rows affected.
    """
    async with pg_session() as s:
        r = await s.execute(text(sql), params or {})
        await s.commit()
        return r.rowcount or 0

async def upload_table_from_path(path: Path, table: str, chunksize: int = 1000,
                                 csv_encoding: str = "cp1252",
                                 sheet_name: str | int | list[str] | None = 0):
    """
    Đọc file CSV/XLSX và nạp vào Postgres bằng pandas.to_sql (chạy qua async engine).
    - CSV: dùng encoding (mặc định 'cp1252' — hợp với file xuất từ Excel/Windows).
    - XLSX: không cần encoding; có thể chọn sheet qua sheet_name.
      + 0 hoặc tên sheet => một DataFrame
      + None => đọc tất cả sheet -> dict[sheet_name -> DataFrame]
      + list => chỉ các sheet chỉ định
    """
    path = Path(path)
    suffix = path.suffix.lower()

    if suffix == ".csv":
        df = pd.read_csv(str(path), encoding=csv_encoding)
        frames = {table: df}
    elif suffix in (".xlsx", ".xlsm", ".xls"):
        # read_excel có thể trả về DataFrame (1 sheet) hoặc dict (nhiều sheet)
        raw = pd.read_excel(str(path), sheet_name=sheet_name, engine="openpyxl")
        if isinstance(raw, dict):
            # nhiều sheet
            frames = {f"{table}_{name}".replace(" ", "_"): df for name, df in raw.items()}
        else:
            frames = {table: raw}
    else:
        raise ValueError(f"Not support file with suffix: {suffix}")

    # Đưa vào Postgres (qua async engine + run_sync)
    engine = _ensure_engine()
    async with engine.begin() as conn:
        for tbl_name, frame in frames.items():
            # làm sạch tên cột: bỏ khoảng trắng
            frame.columns = [str(c).strip().replace(" ", "_") for c in frame.columns]

            def _to_sql(sync_conn):
                frame.to_sql(
                    name=tbl_name,
                    con=sync_conn,
                    if_exists="replace", 
                    index=False,
                    method="multi",
                    chunksize=chunksize,
                )
            await conn.run_sync(_to_sql)

async def _demo():
    # Query
    rows = await pg_query('SELECT * FROM youtube LIMIT 5')
    print(rows)

if __name__ == "__main__":
    asyncio.run(_demo())
