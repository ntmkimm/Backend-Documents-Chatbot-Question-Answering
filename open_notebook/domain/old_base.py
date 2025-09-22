from datetime import datetime, timezone
from typing import Any, ClassVar, Dict, List, Optional, Type, TypeVar, cast

from loguru import logger
from pydantic import BaseModel, ValidationError, field_validator, model_validator

from open_notebook.database.repository import (
    ensure_record_id,
    repo_create,
    repo_delete,
    repo_query,
    repo_relate,
    repo_update,
    repo_upsert,
)
from open_notebook.exceptions import (
    DatabaseOperationError,
    InvalidInputError,
    NotFoundError,
)

T = TypeVar("T", bound="ObjectModel")


class ObjectModel(BaseModel):
    id: Optional[str] = None
    table_name: ClassVar[str] = ""
    created: Optional[datetime] = None
    updated: Optional[datetime] = None

    @classmethod
    async def get_all(cls: Type[T], order_by: Optional[str] = None) -> List[T]:
        if not cls.table_name:
            raise InvalidInputError("get_all() must be called from a subclass with table_name")
        try:
            query = f"SELECT * FROM {cls.table_name}"
            if order_by:
                query += f" ORDER BY {order_by}"

            rows = await repo_query(query)
            return [cls(**row) for row in rows]
        except Exception as e:
            logger.error(f"Error fetching all {cls.table_name}: {str(e)}")
            raise DatabaseOperationError(e)

    @classmethod
    async def get(cls: Type[T], id: str) -> T:
        """Fetch by UUID (Postgres PK)."""
        if not id:
            raise InvalidInputError("ID cannot be empty")

        try:
            result = await repo_query(
                f"SELECT * FROM {cls.table_name} WHERE id = :id",
                {"id": ensure_record_id(id)},
            )
            if result:
                return cls(**result[0])
            raise NotFoundError(f"{cls.table_name} with id {id} not found")
        except Exception as e:
            logger.error(f"Error fetching {cls.table_name} with id {id}: {e}")
            raise NotFoundError(f"Object with id {id} not found - {str(e)}")

    async def save(self, provided_id: bool = False) -> None:
        """Insert or update the record."""
        from open_notebook.domain.models import model_manager

        try:
            self.model_validate(self.model_dump(), strict=True)
            data = self._prepare_save_data()
            now = datetime.now(timezone.utc)
            data["updated"] = now

            if self.needs_embedding():
                embedding_content = self.get_embedding_content()
                if embedding_content:
                    EMBEDDING_MODEL = await model_manager.get_embedding_model()
                    if EMBEDDING_MODEL:
                        data["embedding"] = (await EMBEDDING_MODEL.aembed([embedding_content]))[0]

            if self.id is None:
                data["created"] = now
                repo_result = await repo_create(self.__class__.table_name, data)
            elif provided_id:
                data["created"] = now
                repo_result = await repo_create(
                    self.__class__.table_name, data, set_id=True
                )
            else:
                data["created"] = self.created or now
                repo_result = await repo_update(
                    self.__class__.table_name, self.id, data
                )

            # Update current instance
            if repo_result:
                for key, value in repo_result.items():
                    setattr(self, key, value)

        except ValidationError as e:
            logger.error(f"Validation failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Error saving record: {e}")
            raise DatabaseOperationError(e)

    def _prepare_save_data(self) -> Dict[str, Any]:
        return {k: v for k, v in self.model_dump().items() if v is not None}

    async def delete(self) -> bool:
        if self.id is None:
            raise InvalidInputError("Cannot delete without an ID")
        try:
            return await repo_delete(self.__class__.table_name, self.id)
        except Exception as e:
            logger.error(f"Error deleting {self.__class__.table_name} {self.id}: {e}")
            raise DatabaseOperationError(e)

    async def relate(
        self, relationship: str, target_id: str, data: Optional[Dict] = None
    ) -> Any:
        if not relationship or not target_id or not self.id:
            raise InvalidInputError("Relationship and target ID must be provided")
        try:
            return await repo_relate(
                source=f"{self.__class__.table_name}:{self.id}",
                relationship=relationship,
                target=target_id,
                data=data or {},
            )
        except Exception as e:
            logger.error(f"Error creating relationship: {e}")
            raise DatabaseOperationError(e)

    def needs_embedding(self) -> bool:
        return False

    def get_embedding_content(self) -> Optional[str]:
        return None

    @field_validator("created", "updated", mode="before")
    @classmethod
    def parse_datetime(cls, value):
        if isinstance(value, str):
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        return value


class RecordModel(BaseModel):
    """Singleton-like record, used for config or metadata rows."""

    record_id: ClassVar[str]
    auto_save: ClassVar[bool] = False
    _instances: ClassVar[Dict[str, "RecordModel"]] = {}

    class Config:
        validate_assignment = True
        arbitrary_types_allowed = True
        extra = "allow"
        from_attributes = True
        defer_build = True

    def __new__(cls, **kwargs):
        if cls.record_id in cls._instances:
            instance = cls._instances[cls.record_id]
            if kwargs:
                for k, v in kwargs.items():
                    setattr(instance, k, v)
            return instance

        instance = super().__new__(cls)
        cls._instances[cls.record_id] = instance
        return instance

    def __init__(self, **kwargs):
        if not hasattr(self, "_initialized"):
            object.__setattr__(self, "__dict__", {})
            super().__init__(**kwargs)
            object.__setattr__(self, "_initialized", True)
            object.__setattr__(self, "_db_loaded", False)

    async def _load_from_db(self):
        if not getattr(self, "_db_loaded", False):
            rows = await repo_query(
                f"SELECT * FROM {self.__class__.table_name} WHERE id = :id",
                {"id": ensure_record_id(self.record_id)},
            )
            if rows:
                row = rows[0]
                for k, v in row.items():
                    if hasattr(self, k):
                        object.__setattr__(self, k, v)
            object.__setattr__(self, "_db_loaded", True)

    @classmethod
    async def get_instance(cls) -> "RecordModel":
        instance = cls()
        await instance._load_from_db()
        return instance

    @model_validator(mode="after")
    def auto_save_validator(self):
        if self.__class__.auto_save:
            logger.warning(
                f"Auto-save is enabled for {self.__class__.__name__}, "
                f"but updates must be awaited manually via update()."
            )
        return self

    async def update(self):
        data = {
            f: getattr(self, f)
            for f, fi in self.model_fields.items()
            if not str(fi.annotation).startswith("typing.ClassVar")
        }

        await repo_upsert(
            self.__class__.table_name, self.record_id, data, id_col="id"
        )

        rows = await repo_query(
            f"SELECT * FROM {self.__class__.table_name} WHERE id = :id",
            {"id": ensure_record_id(self.record_id)},
        )
        if rows:
            for k, v in rows[0].items():
                if hasattr(self, k):
                    object.__setattr__(self, k, v)
        return self

    @classmethod
    def clear_instance(cls):
        if cls.record_id in cls._instances:
            del cls._instances[cls.record_id]

    async def patch(self, model_dict: dict):
        for k, v in model_dict.items():
            setattr(self, k, v)
        await self.update()
