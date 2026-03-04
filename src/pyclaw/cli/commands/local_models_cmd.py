"""CLI commands for local model management."""

from __future__ import annotations

import json

import typer


def local_models_download(
    repo_id: str,
    *,
    filename: str = "",
    backend: str = "llamacpp",
    source: str = "huggingface",
) -> None:
    """Download a model from HuggingFace or ModelScope."""
    from pyclaw.local_models.manager import LocalModelManager
    from pyclaw.local_models.schema import BackendType, DownloadSource

    be = BackendType(backend)
    src = DownloadSource(source)

    typer.echo(f"Downloading {repo_id} (backend={backend}, source={source})...")
    try:
        info = LocalModelManager.download_model(
            repo_id,
            filename=filename or None,
            backend=be,
            source=src,
        )
        typer.echo(f"Downloaded: {info.display_name}")
        typer.echo(f"  Path: {info.local_path}")
        typer.echo(f"  Size: {info.size_mb:.1f} MB")
        typer.echo(f"  ID: {info.id}")
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)


def local_models_list(*, output_json: bool = False) -> None:
    """List downloaded local models."""
    from pyclaw.local_models.manager import get_active_model, list_local_models

    models = list_local_models()
    active = get_active_model()
    active_id = active.id if active else ""

    if output_json:
        typer.echo(
            json.dumps(
                [m.summary() for m in models],
                indent=2,
                ensure_ascii=False,
            )
        )
        return

    if not models:
        typer.echo("No local models downloaded. Use: pyclaw models download <repo>")
        return

    for m in models:
        marker = " *" if m.id == active_id else ""
        typer.echo(f"  {m.display_name}{marker}")
        typer.echo(f"    ID: {m.id}")
        typer.echo(f"    Backend: {m.backend.value} | Size: {m.size_mb:.1f} MB")


def local_models_delete(model_id: str) -> None:
    """Delete a downloaded local model."""
    from pyclaw.local_models.manager import delete_local_model

    try:
        delete_local_model(model_id)
        typer.echo(f"Deleted: {model_id}")
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)


def local_models_select(model_id: str) -> None:
    """Set a local model as the active model."""
    from pyclaw.local_models.manager import set_active_model

    try:
        set_active_model(model_id)
        typer.echo(f"Active model set to: {model_id}")
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
