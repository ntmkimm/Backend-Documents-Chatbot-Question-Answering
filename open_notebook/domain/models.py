import os
from typing import ClassVar, Dict, Optional, Union

from esperanto import (
    AIFactory,
    EmbeddingModel,
    LanguageModel,
    SpeechToTextModel,
    TextToSpeechModel,
)

from open_notebook.database.repository import repo_query
from open_notebook.domain.base import ObjectModel, RecordModel

ModelType = Union[LanguageModel, EmbeddingModel, SpeechToTextModel, TextToSpeechModel]


class Model(ObjectModel):
    table_name: ClassVar[str] = "model"
    name: str
    provider: str
    type: str

    # @classmethod
    # async def get_models_by_type(cls, model_type):
    #     models = await repo_query(
    #         "SELECT * FROM model WHERE type=$model_type;", {"model_type": model_type}
    #     )
    #     return [Model(**model) for model in models]

class DefaultModels(RecordModel):
    record_id: ClassVar[str] = "open_notebook:default_models"
    default_chat_model: Optional[str] = os.getenv("DEFAULT_CHAT_MODEL")
    default_transformation_model: Optional[str] = os.getenv("DEFAULT_TRANSFORMATION_MODEL")
    large_context_model: Optional[str] = os.getenv("DEFAULT_LARGE_CONTEXT_MODEL")
    default_text_to_speech_model: Optional[str] = os.getenv("DEFAULT_TEXT_TO_SPEECH_MODEL")
    default_speech_to_text_model: Optional[str] = os.getenv("DEFAULT_SPEECH_TO_TEXT_MODEL")
    default_embedding_model: Optional[str] = os.getenv("DEFAULT_EMBEDDING_MODEL")
    default_tools_model: Optional[str] = os.getenv("DEFAULT_TOOLS_MODEL")


class ModelManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ModelManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_initialized"):
            self._initialized = True
            self._model_cache: Dict[str, ModelType] = {}
            self._default_models = None

    async def get_model(self, model_id: dict, **kwargs) -> Optional[ModelType]:
        model_type = model_id.get("type")
        if not model_type or model_type not in [
            "language",
            "embedding",
            "speech_to_text",
            "text_to_speech",
        ]:
            raise ValueError(f"Invalid model type: {model_type}")
        
        name = model_id.get("name")
        provider = model_id.get("provider")
        
        if model_type == "language":
            return AIFactory.create_language(model_name=name, provider=provider, config=kwargs)
        elif model_type == "embedding":
            if provider.lower() == "openai":
                embedding_base_url = os.getenv("EMBEDDING_BASE_URL")
                if embedding_base_url:
                    kwargs['base_url'] = embedding_base_url
            return AIFactory.create_embedding(model_name=name, provider=provider, config=kwargs)
        elif model_type == "speech_to_text":
            return AIFactory.create_speech_to_text(model_name=name, provider=provider, config=kwargs)
        elif model_type == "text_to_speech":
            return AIFactory.create_text_to_speech(model_name=name, provider=provider, config=kwargs)
        
        raise ValueError(f"Invalid model type: {model_type}")

    async def refresh_defaults(self):
        """Refresh the default models from the database"""
        self._default_models = await DefaultModels.get_instance()

    async def get_defaults(self) -> DefaultModels:
        """Get the default models configuration"""
        if not self._default_models:
            await self.refresh_defaults()
            if not self._default_models:
                raise RuntimeError("Failed to initialize default models configuration")
        return self._default_models

    async def get_speech_to_text(self, **kwargs) -> Optional[SpeechToTextModel]:
        """Get the default speech-to-text model"""
        model_id = {
            "name": "",
            "provider": "",
            "type": "",
        }
        model = await self.get_model(model_id=model_id, **kwargs)
        assert model is None or isinstance(model, SpeechToTextModel), (
            f"Expected SpeechToTextModel but got {type(model)}"
        )
        return model

    async def get_text_to_speech(self, **kwargs) -> Optional[TextToSpeechModel]:
        """Get the default text-to-speech model"""
        model_id = {
            "name": "",
            "provider": "",
            "type": "",
        }
        model = await self.get_model(model_id=model_id, **kwargs)
        assert model is None or isinstance(model, TextToSpeechModel), (
            f"Expected TextToSpeechModel but got {type(model)}"
        )
        return model

    async def get_embedding_model(self, **kwargs) -> Optional[EmbeddingModel]:
        """Get the default embedding model"""
        model_id = {
            "name": os.getenv("DEFAULT_EMBEDDING_MODEL"),
            "provider": "openai",
            "type": "embedding",
        }
        model = await self.get_model(model_id=model_id, **kwargs)
        assert model is None or isinstance(model, EmbeddingModel), (
            f"Expected EmbeddingModel but got {type(model)}"
        )
        return model

    async def get_default_model(self, model_type: str, **kwargs) -> Optional[ModelType]:
        """
        Get the default model for a specific type.

        Args:
            model_type: The type of model to retrieve (e.g., 'chat', 'embedding', etc.)
            **kwargs: Additional arguments to pass to the model constructor
        """
        defaults = await self.get_defaults()
        model_id = None

        if model_type == "chat":
            model_id = {
                "name": os.getenv("DEFAULT_CHAT_MODEL"),
                "provider": os.getenv("LANGUAGE_MODEL_PROVIDER"),
                "type": "language",
            }
        elif model_type == "transformation":
            model_id = {
                "name": os.getenv("DEFAULT_TRANSFORMATION_MODEL"),
                "provider": os.getenv("LANGUAGE_MODEL_PROVIDER"),
                "type": "language",
            }
        elif model_type == "tools":
            model_id = {
                "name": os.getenv("DEFAULT_TOOLS_MODEL"),
                "provider": os.getenv("LANGUAGE_MODEL_PROVIDER"),
                "type": "language",
            }
        elif model_type == "embedding":
            model_id = {
                "name": os.getenv("DEFAULT_EMBEDDING_MODEL"),
                "provider": "openai",
                "type": "embedding",
            }
        elif model_type == "text_to_speech":
            model_id = {
                "name": os.getenv("DEFAULT_TEXT_TO_SPEECH_MODEL"),
                "provider": os.getenv("LANGUAGE_MODEL_PROVIDER"),
                "type": "text_to_speech",
            }
        elif model_type == "speech_to_text":
            model_id = {
                "name": os.getenv("DEFAULT_SPEECH_TO_TEXT_MODEL"),
                "provider": os.getenv("LANGUAGE_MODEL_PROVIDER"),
                "type": "speech_to_text",
            }
        elif model_type == "large_context":
            model_id = {
                "name": os.getenv("DEFAULT_LARGE_CONTEXT_MODEL"),
                "provider": os.getenv("LANGUAGE_MODEL_PROVIDER"),
                "type": "language"
            }

        if not model_id:
            return None

        return await self.get_model(model_id=model_id, **kwargs)

    def clear_cache(self):
        """Clear the model cache"""
        self._model_cache.clear()


model_manager = ModelManager()
