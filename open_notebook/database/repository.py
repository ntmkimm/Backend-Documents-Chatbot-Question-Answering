import os
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union, AsyncGenerator
from sqlalchemy.exc import IntegrityError

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

import uuid
from typing import Union

from open_notebook.config import POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_PORT, POSTGRES_ADDRESS, POSTGRES_DB
load_dotenv()

def get_database_url() -> str:
    return f"postgresql+asyncpg://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_ADDRESS}:{POSTGRES_PORT}/{POSTGRES_DB}"

_engine: Optional[AsyncEngine] = None
_session_factory: Optional[sessionmaker] = None

def _ensure_engine() -> AsyncEngine:
    global _engine, _session_factory
    if _engine is None:
        _engine = create_async_engine(
            get_database_url(),
            pool_pre_ping=True,
            future=True,
        )
        _session_factory = sessionmaker(
            _engine, expire_on_commit=False, class_=AsyncSession
        )
    return _engine

@asynccontextmanager
async def db_connection() -> AsyncGenerator[AsyncSession, None]:
    _ensure_engine()
    assert _session_factory is not None
    async with _session_factory() as session:
        yield session


def ensure_record_id(value: Union[str, uuid.UUID]) -> uuid.UUID:
    """
    Ensure a value is a UUID (Postgres primary key).
    """
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except Exception as e:
        raise ValueError(f"Invalid UUID: {value}") from e

def _ensure_datetime(value):
    """Convert str to datetime if needed."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            raise ValueError(f"Invalid datetime string: {value}")
    return datetime.now(timezone.utc)  # fallback

def _convert_uuid_id_to_string(row: dict) -> dict:
    out = {}
    for k, v in row.items():
        if isinstance(v, uuid.UUID):
            out[k] = str(v)
        else:
            out[k] = v
    return out

async def repo_query(query_str: str, vars: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Run a SELECT and return rows as list[dict]."""
    async with db_connection() as s:
        res = await s.execute(text(query_str), vars or {})
        rows = res.mappings().all()
        return [_convert_uuid_id_to_string(dict(r)) for r in rows]  

import uuid

async def repo_create(
    table: str,
    data: Dict[str, Any],
    set_id: bool = False
) -> Dict[str, Any]:
    """INSERT into table and return the created row (with timestamps)."""

    data = dict(data)

    if not set_id:
        data.pop("id", None)  # prevent overriding PK
    else:
        # validate/normalize id
        if "id" in data:
            if not isinstance(data["id"], uuid.UUID):
                try:
                    data["id"] = uuid.UUID(str(data["id"]))
                except Exception as e:
                    raise ValueError(f"Invalid UUID for {table}.id: {data['id']}") from e
        else:
            # if caller says set_id=True but forgot id, generate one
            data["id"] = uuid.uuid4()

    now = datetime.now(timezone.utc)
    data["created"] = _ensure_datetime(now)
    data["updated"] = _ensure_datetime(now)


    cols = ", ".join(data.keys())
    vals = ", ".join([f":{k}" for k in data.keys()])
    sql = f"INSERT INTO {table} ({cols}) VALUES ({vals}) RETURNING *"

    async with db_connection() as s:
        try:
            res = await s.execute(text(sql), data)
            await s.commit()
            row = res.mappings().first()
            if not row:
                raise RuntimeError(f"Failed to insert into {table}: {data}")
            return _convert_uuid_id_to_string(dict(row))

        except IntegrityError as e:
            await s.rollback()
            # Kiểm tra lỗi có phải do duplicate key không
            if "duplicate key value violates unique constraint" in str(e.orig):
                raise RuntimeError("Invalid ID: The ID already exists") from None
            else:
                # Nếu là lỗi khác thì re-raise lại
                raise


async def repo_update(table: str, id_value: Any, data: Dict[str, Any], id_col: str = "id") -> Dict[str, Any]:
    """Update record by id and return updated row."""
    data = dict(data)
    data.pop("id", None)
    data["updated"] = datetime.now(timezone.utc)

    set_clause = ", ".join([f"{k}=:{k}" for k in data.keys()])
    sql = f"UPDATE {table} SET {set_clause} WHERE {id_col}=:pk RETURNING *"

    params = {**data, "pk": id_value}

    async with db_connection() as s:
        res = await s.execute(text(sql), params)
        await s.commit()
        row = res.mappings().first()
        return dict(row) if row else {}

async def repo_upsert(table: str, id_value: Any, data: Dict[str, Any], id_col: str = "id") -> Dict[str, Any]:
    """UPSERT by id (INSERT ... ON CONFLICT DO UPDATE)."""
    data = dict(data)
    data.pop("id", None)
    now = datetime.now(timezone.utc)
    data["updated"] = now
    if id_value is None:
        data["created"] = now

    cols = list(data.keys())
    insert_cols = ", ".join(cols + [id_col] if id_value else cols)
    insert_vals = ", ".join([f":{c}" for c in cols] + ([":pk"] if id_value else []))

    update_clause = ", ".join([f"{c}=EXCLUDED.{c}" for c in cols])

    sql = f"""
    INSERT INTO {table} ({insert_cols})
    VALUES ({insert_vals})
    ON CONFLICT ({id_col})
    DO UPDATE SET {update_clause}
    RETURNING *
    """

    params = {**data}
    if id_value is not None:
        params["pk"] = id_value

    async with db_connection() as s:
        res = await s.execute(text(sql), params)
        await s.commit()
        return dict(res.mappings().first())

async def repo_delete(table: str, id_value: Any, id_col: str = "id") -> int:
    """Delete a record and return rows affected."""
    sql = f"DELETE FROM {table} WHERE {id_col}=:pk"
    async with db_connection() as s:
        res = await s.execute(text(sql), {"pk": id_value})
        await s.commit()
        return res.rowcount or 0

async def repo_insert(table: str, rows: List[Dict[str, Any]]) -> int:
    """Bulk insert many rows. Returns number of rows inserted."""
    if not rows:
        return 0
    keys = rows[0].keys()
    cols = ", ".join(keys)
    vals = ", ".join([f":{k}" for k in keys])
    sql = f"INSERT INTO {table} ({cols}) VALUES ({vals})"

    async with db_connection() as s:
        await s.execute_many(text(sql), rows)  # SQLAlchemy 2.0 supports executemany
        await s.commit()
        return len(rows)

async def repo_relate(
    source: str, relationship: str, target: str, data: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    Create a relationship between two records with optional data.
    In Postgres this maps to inserting into a join table.
    
    Example:
        await repo_relate("source:1", "reference", "notebook:42", {"note": "extra"})
    will insert into the `reference` table.
    """
    if data is None:
        data = {}

    # Parse IDs like "source:1"  ("source", 1)
    def parse_record_id(rid: str):
        tbl, pk = rid.split(":")
        return tbl, pk

    src_table, src_id = parse_record_id(source)
    tgt_table, tgt_id = parse_record_id(target)

    # Relationship table is already known (e.g. "reference" or "refers_to")
    cols = [f"{src_table}_id", f"{tgt_table}_id"] + list(data.keys())
    vals = [f":{c}" for c in cols]

    sql = f"""
    INSERT INTO {relationship} ({", ".join(cols)})
    VALUES ({", ".join(vals)})
    RETURNING *
    """

    params = {**data, f"{src_table}_id": src_id, f"{tgt_table}_id": tgt_id}

    async with db_connection() as s:
        res = await s.execute(text(sql), params)
        await s.commit()
        rows = res.mappings().all()
        return [dict(r) for r in rows]

async def pg_execute(sql: str, params: Optional[Dict[str, Any]] = None) -> int: 
    """ Chạy DDL/DML (INSERT/UPDATE/DELETE/CREATE/…) - trả rows affected. """ 
    async with db_connection() as s: 
        r = await s.execute(text(sql), params or {}) 
        await s.commit() 
        return r.rowcount or 0

@asynccontextmanager
async def transaction():
    """
    Provides a transactional scope for a series of database operations.
    Ensures that all operations within the context are committed atomically.
    """
    async with db_connection() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            print("error",e)
            await session.rollback()
            raise e

