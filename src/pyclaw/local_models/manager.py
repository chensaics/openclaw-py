"""Local model download, listing, and deletion."""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Optional, cast

from pyclaw.config.paths import resolve_state_dir

from .schema import (
    BackendType,
    DownloadSource,
    LocalModelInfo,
    LocalModelsManifest,
)

logger = logging.getLogger(__name__)

MODELS_DIR = resolve_state_dir() / "local_models"
MANIFEST_PATH = MODELS_DIR / "manifest.json"


def _ensure_models_dir() -> Path:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    return MODELS_DIR


def _load_manifest() -> LocalModelsManifest:
    if MANIFEST_PATH.is_file():
        try:
            raw = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
            return cast(LocalModelsManifest, LocalModelsManifest.model_validate(raw))
        except (json.JSONDecodeError, ValueError):
            logger.warning("Corrupted manifest.json, starting fresh")
    return LocalModelsManifest()


def _save_manifest(manifest: LocalModelsManifest) -> None:
    _ensure_models_dir()
    MANIFEST_PATH.write_text(
        json.dumps(manifest.model_dump(mode="json"), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def list_local_models(backend: Optional[BackendType] = None) -> list[LocalModelInfo]:
    manifest = _load_manifest()
    models = list(manifest.models.values())
    if backend is not None:
        models = [m for m in models if m.backend == backend]
    return models


def get_local_model(model_id: str) -> Optional[LocalModelInfo]:
    manifest = _load_manifest()
    return manifest.models.get(model_id)


def get_active_model() -> Optional[LocalModelInfo]:
    manifest = _load_manifest()
    if manifest.active_model_id:
        return manifest.models.get(manifest.active_model_id)
    return None


def set_active_model(model_id: str) -> None:
    manifest = _load_manifest()
    if model_id not in manifest.models:
        raise ValueError(f"Model '{model_id}' not found in manifest")
    manifest.active_model_id = model_id
    _save_manifest(manifest)


def delete_local_model(model_id: str) -> None:
    manifest = _load_manifest()
    info = manifest.models.pop(model_id, None)
    if info is None:
        raise ValueError(f"Local model '{model_id}' not found.")
    path = Path(info.local_path)
    if path.is_dir():
        shutil.rmtree(path, ignore_errors=True)
        logger.info("Deleted model directory: %s", path)
    elif path.is_file():
        path.unlink(missing_ok=True)
        logger.info("Deleted model file: %s", path)
    if manifest.active_model_id == model_id:
        manifest.active_model_id = ""
    _save_manifest(manifest)


def _sanitize_repo_id(repo_id: str) -> str:
    return repo_id.replace("/", "--")


class LocalModelManager:
    """Handles downloading models from HuggingFace Hub or ModelScope."""

    @staticmethod
    def download_model(
        repo_id: str,
        filename: Optional[str] = None,
        backend: BackendType = BackendType.LLAMACPP,
        source: DownloadSource = DownloadSource.HUGGINGFACE,
    ) -> LocalModelInfo:
        if source == DownloadSource.HUGGINGFACE:
            return LocalModelManager._download_from_huggingface(repo_id, filename, backend)
        elif source == DownloadSource.MODELSCOPE:
            return LocalModelManager._download_from_modelscope(repo_id, filename, backend)
        else:
            raise ValueError(f"Unknown download source: {source}")

    @staticmethod
    def _download_from_huggingface(
        repo_id: str,
        filename: Optional[str],
        backend: BackendType,
    ) -> LocalModelInfo:
        try:
            from huggingface_hub import hf_hub_download, list_repo_files
        except ImportError as exc:
            raise ImportError(
                "huggingface_hub is required for model downloads. "
                "Install with: pip install 'pyclaw[llamacpp]' or pip install huggingface_hub"
            ) from exc

        _ensure_models_dir()
        local_dir = MODELS_DIR / _sanitize_repo_id(repo_id)

        if backend == BackendType.MLX:
            from huggingface_hub import snapshot_download

            logger.info("Downloading full repo %s (MLX)...", repo_id)
            snapshot_dir = snapshot_download(repo_id=repo_id, local_dir=str(local_dir))
            return LocalModelManager._register_model(
                repo_id, filename or "(full repo)", backend,
                DownloadSource.HUGGINGFACE, snapshot_dir,
            )

        if filename is None:
            filename = LocalModelManager._auto_select_file(
                list(list_repo_files(repo_id)), backend,
            )

        logger.info("Downloading %s/%s from Hugging Face...", repo_id, filename)
        downloaded_path = hf_hub_download(
            repo_id=repo_id, filename=filename, local_dir=str(local_dir),
        )
        return LocalModelManager._register_model(
            repo_id, filename, backend, DownloadSource.HUGGINGFACE, downloaded_path,
        )

    @staticmethod
    def _download_from_modelscope(
        repo_id: str,
        filename: Optional[str],
        backend: BackendType,
    ) -> LocalModelInfo:
        try:
            from modelscope.hub.file_download import model_file_download
        except ImportError as exc:
            raise ImportError(
                "modelscope is required for ModelScope downloads. "
                "Install with: pip install modelscope"
            ) from exc

        _ensure_models_dir()
        if filename is None:
            try:
                from modelscope.hub.api import HubApi
                api = HubApi()
                files = [
                    f["Path"] for f in api.get_model_files(repo_id)
                    if isinstance(f, dict) and "Path" in f
                ]
            except Exception as exc:
                raise ValueError(
                    f"Cannot list files for {repo_id} on ModelScope. "
                    "Please specify the filename explicitly."
                ) from exc
            filename = LocalModelManager._auto_select_file(files, backend)

        local_dir = MODELS_DIR / _sanitize_repo_id(repo_id)
        local_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Downloading %s/%s from ModelScope...", repo_id, filename)
        downloaded_path = model_file_download(
            model_id=repo_id, file_path=filename, local_dir=str(local_dir),
        )
        return LocalModelManager._register_model(
            repo_id, filename, backend, DownloadSource.MODELSCOPE, downloaded_path,
        )

    @staticmethod
    def _auto_select_file(files: list[str], backend: BackendType) -> str:
        if backend == BackendType.LLAMACPP:
            gguf_files = [f for f in files if f.endswith(".gguf")]
            if not gguf_files:
                raise ValueError(
                    "No .gguf files found. This repo may not provide GGUF-format models."
                )
            return next((f for f in gguf_files if "Q4_K_M" in f), gguf_files[0])
        elif backend == BackendType.MLX:
            st_files = [f for f in files if f.endswith(".safetensors")]
            if not st_files:
                raise ValueError("No .safetensors files found for MLX backend.")
            return st_files[0]
        else:
            raise ValueError(f"Unknown backend: {backend}")

    @staticmethod
    def _register_model(
        repo_id: str,
        filename: str,
        backend: BackendType,
        source: DownloadSource,
        downloaded_path: str,
    ) -> LocalModelInfo:
        resolved = Path(downloaded_path).resolve()
        if resolved.is_dir():
            file_size = sum(
                f.stat().st_size for f in resolved.rglob("*")
                if f.is_file() and not any(p.name.startswith(".") for p in f.parents)
            )
            model_id = repo_id
            repo_short = repo_id.split("/")[-1] if "/" in repo_id else repo_id
            display_name = repo_short
        else:
            file_size = resolved.stat().st_size
            model_id = f"{repo_id}/{filename}"
            repo_short = repo_id.split("/")[-1] if "/" in repo_id else repo_id
            display_name = f"{repo_short} ({filename})"

        info = LocalModelInfo(
            id=model_id,
            repo_id=repo_id,
            filename=filename,
            backend=backend,
            source=source,
            file_size=file_size,
            local_path=str(resolved),
            display_name=display_name,
        )
        manifest = _load_manifest()
        manifest.models[model_id] = info
        _save_manifest(manifest)
        logger.info("Registered local model: %s (%s)", model_id, display_name)
        return info
