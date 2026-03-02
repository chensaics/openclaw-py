"""Local model management — download, register, and run models locally."""

from .chat_model import local_chat, local_chat_stream
from .manager import (
    LocalModelManager,
    delete_local_model,
    get_active_model,
    get_local_model,
    list_local_models,
    set_active_model,
)
from .schema import BackendType, DownloadSource, LocalModelInfo

__all__ = [
    "BackendType",
    "DownloadSource",
    "LocalModelInfo",
    "LocalModelManager",
    "delete_local_model",
    "get_active_model",
    "get_local_model",
    "list_local_models",
    "local_chat",
    "local_chat_stream",
    "set_active_model",
]
