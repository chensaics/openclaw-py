"""Skills marketplace — search and install public skills from ClawHub."""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

logger = logging.getLogger(__name__)

CLAWHUB_API = "https://api.github.com"
CLAWHUB_REPO = "openclaw/clawhub"
CLAWHUB_SKILLS_PATH = "skills"


@dataclass
class MarketplaceSkill:
    """A skill available in the marketplace."""

    name: str
    description: str = ""
    url: str = ""
    download_url: str = ""
    homepage: str = ""
    tags: list[str] = field(default_factory=list)
    size: int = 0


async def search_skills(query: str) -> list[MarketplaceSkill]:
    """Search for skills in the ClawHub repository."""
    import httpx

    url = f"{CLAWHUB_API}/repos/{CLAWHUB_REPO}/contents/{CLAWHUB_SKILLS_PATH}"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                url,
                headers={"Accept": "application/vnd.github.v3+json"},
            )
            if resp.status_code == 404:
                logger.debug("ClawHub skills directory not found")
                return []
            resp.raise_for_status()
            items = resp.json()
    except Exception:
        logger.exception("Failed to fetch ClawHub skills index")
        return []

    if not isinstance(items, list):
        return []

    query_lower = query.lower()
    results: list[MarketplaceSkill] = []
    for item in items:
        if item.get("type") != "dir":
            continue
        name = item.get("name", "")
        if query_lower in name.lower():
            results.append(
                MarketplaceSkill(
                    name=name,
                    url=item.get("html_url", ""),
                    description=f"Skill: {name}",
                )
            )

    return results


async def fetch_skill_content(name: str) -> str | None:
    """Fetch the SKILL.md content for a named skill from ClawHub."""
    import httpx

    url = f"{CLAWHUB_API}/repos/{CLAWHUB_REPO}/contents/{CLAWHUB_SKILLS_PATH}/{name}/SKILL.md"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                url,
                headers={"Accept": "application/vnd.github.v3.raw"},
            )
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return cast(str, resp.text)
    except Exception:
        logger.exception("Failed to fetch skill '%s' from ClawHub", name)
        return None


async def fetch_skill_from_url(url: str) -> str | None:
    """Fetch SKILL.md from an arbitrary URL."""
    import httpx

    target = url
    if not target.endswith("SKILL.md"):
        target = target.rstrip("/") + "/SKILL.md"
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(target)
            resp.raise_for_status()
            return cast(str, resp.text)
    except Exception:
        logger.exception("Failed to fetch skill from URL: %s", url)
        return None


def install_skill(
    name: str,
    content: str,
    workspace_dir: str | Path | None = None,
    *,
    force: bool = False,
) -> Path:
    """Install a skill to the workspace skills directory."""
    from pyclaw.agents.progress import ProgressEvent, ProgressStatus, emit_progress

    if workspace_dir is None:
        workspace_dir = Path.home() / ".pyclaw" / "workspace"
    workspace_dir = Path(workspace_dir)

    task_id = f"install-skill-{name}"

    emit_progress(
        ProgressEvent(
            task_id=task_id,
            status=ProgressStatus.STARTED,
            message=f"Installing skill '{name}'...",
        )
    )

    skills_dir = workspace_dir / ".skills" / name
    skill_file = skills_dir / "SKILL.md"

    if skill_file.exists() and not force:
        emit_progress(
            ProgressEvent(
                task_id=task_id,
                status=ProgressStatus.FAILED,
                message=f"Skill '{name}' already installed",
            )
        )
        raise FileExistsError(
            f"Skill '{name}' already installed at {skill_file}. Use --force to overwrite."
        )

    skills_dir.mkdir(parents=True, exist_ok=True)
    skill_file.write_text(content, encoding="utf-8")

    emit_progress(
        ProgressEvent(
            task_id=task_id,
            status=ProgressStatus.COMPLETED,
            progress=1.0,
            message=f"Skill '{name}' installed",
        )
    )
    return skill_file


def remove_skill(name: str, workspace_dir: str | Path | None = None) -> bool:
    """Remove an installed skill."""
    if workspace_dir is None:
        workspace_dir = Path.home() / ".pyclaw" / "workspace"
    workspace_dir = Path(workspace_dir)

    skills_dir = workspace_dir / ".skills" / name
    if not skills_dir.exists():
        return False

    shutil.rmtree(skills_dir)
    return True


def list_installed_skills(workspace_dir: str | Path | None = None) -> list[dict[str, str]]:
    """List installed skills in the workspace."""
    if workspace_dir is None:
        workspace_dir = Path.home() / ".pyclaw" / "workspace"
    workspace_dir = Path(workspace_dir)

    results: list[dict[str, str]] = []
    for src_dir_name, source in [
        (".skills", "workspace"),
        (".cursor/skills", "cursor"),
        (".agents/skills", "agents"),
    ]:
        src_dir = workspace_dir / src_dir_name
        if not src_dir.is_dir():
            continue
        for child in sorted(src_dir.iterdir()):
            skill_file = child / "SKILL.md"
            if child.is_dir() and skill_file.exists():
                results.append(
                    {
                        "name": child.name,
                        "path": str(skill_file),
                        "source": source,
                    }
                )
    return results
