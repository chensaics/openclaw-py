"""Skills marketplace — search/install/manage skills from GitHub and ClawHub."""

from __future__ import annotations

import ipaddress
import json
import logging
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

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


def _run_clawhub(*args: str, timeout_s: float = 20.0) -> tuple[bool, str]:
    if shutil.which("clawhub") is None:
        return False, ""
    try:
        proc = subprocess.run(
            ["clawhub", *args],
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_s,
        )
    except Exception:
        logger.exception("Failed to run clawhub command: %s", " ".join(args))
        return False, ""
    if proc.returncode != 0:
        return False, (proc.stderr or proc.stdout or "").strip()
    return True, (proc.stdout or "").strip()


def _extract_skill_name(raw: str) -> str:
    candidate = raw.strip()
    if not candidate:
        return ""
    for sep in ("@", " "):
        if sep in candidate:
            candidate = candidate.split(sep, 1)[0].strip()
    return candidate.strip("./")


def _is_blocked_host(hostname: str) -> bool:
    host = (hostname or "").strip().lower()
    if not host:
        return True
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return bool(
        ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified
    )


def _parse_clawhub_search_output(text: str) -> list[MarketplaceSkill]:
    parsed: list[MarketplaceSkill] = []
    if not text:
        return parsed
    try:
        obj = json.loads(text)
        if isinstance(obj, list):
            for item in obj:
                if not isinstance(item, dict):
                    continue
                name = str(item.get("slug") or item.get("name") or "").strip()
                if not name:
                    continue
                parsed.append(
                    MarketplaceSkill(
                        name=name,
                        description=str(item.get("description", "")).strip(),
                        url=str(item.get("url") or item.get("homepage") or "").strip(),
                    )
                )
            return parsed
    except Exception:
        pass
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith(("Search", "Found", "-")):
            continue
        name = _extract_skill_name(line)
        if name:
            parsed.append(MarketplaceSkill(name=name, description=f"Skill: {name}"))
    return parsed


async def _search_skills_from_github(query: str) -> list[MarketplaceSkill]:
    import httpx

    url = f"{CLAWHUB_API}/repos/{CLAWHUB_REPO}/contents/{CLAWHUB_SKILLS_PATH}"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers={"Accept": "application/vnd.github.v3+json"})
            if resp.status_code == 404:
                logger.debug("ClawHub skills directory not found")
                return []
            resp.raise_for_status()
            items = resp.json()
    except Exception:
        logger.exception("Failed to fetch GitHub skills index")
        return []

    if not isinstance(items, list):
        return []
    query_lower = query.lower()
    results: list[MarketplaceSkill] = []
    for item in items:
        if item.get("type") != "dir":
            continue
        name = str(item.get("name", "")).strip()
        if query_lower in name.lower():
            results.append(MarketplaceSkill(name=name, url=item.get("html_url", ""), description=f"Skill: {name}"))
    return results


async def search_skills(query: str) -> list[MarketplaceSkill]:
    """Search for skills with clawhub CLI first, then GitHub fallback."""
    ok, out = _run_clawhub("search", query, "--json")
    if ok:
        parsed = _parse_clawhub_search_output(out)
        if parsed:
            return parsed
    ok2, out2 = _run_clawhub("search", query)
    if ok2:
        parsed = _parse_clawhub_search_output(out2)
        if parsed:
            return parsed
    return await _search_skills_from_github(query)


async def fetch_skill_content(name: str) -> str | None:
    """Fetch SKILL.md for a named skill (GitHub fallback)."""
    import httpx

    url = f"{CLAWHUB_API}/repos/{CLAWHUB_REPO}/contents/{CLAWHUB_SKILLS_PATH}/{name}/SKILL.md"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers={"Accept": "application/vnd.github.v3.raw"})
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.text
    except Exception:
        logger.exception("Failed to fetch skill '%s' from GitHub fallback", name)
        return None


def guess_skill_name_from_url(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    if not path:
        return "skill"
    name = path.rsplit("/", 1)[-1]
    if name.lower() == "skill.md":
        name = path.rsplit("/", 2)[-2] if "/" in path else "skill"
    if name in {"tree", "blob"}:
        return "skill"
    return _extract_skill_name(name) or "skill"


async def _fetch_text(url: str) -> str | None:
    import httpx

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        logger.warning("Rejected non-http(s) skill URL: %s", url)
        return None
    if _is_blocked_host(parsed.hostname or ""):
        logger.warning("Rejected blocked host for skill URL: %s", url)
        return None
    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            resp = await client.get(url)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            text = resp.text
            if len(text) > 512_000:
                logger.warning("Rejected oversized skill URL response: %s", url)
                return None
            return text
    except Exception:
        logger.exception("Failed to fetch URL: %s", url)
        return None


async def fetch_skill_from_url(url: str) -> str | None:
    """Fetch SKILL.md from a URL."""
    target = url.rstrip("/")
    if not target.endswith("SKILL.md"):
        target += "/SKILL.md"
    return await _fetch_text(target)


async def _fetch_github_tree_bundle(
    owner: str,
    repo: str,
    ref: str,
    base_path: str,
) -> dict[str, str] | None:
    import httpx

    headers = {"Accept": "application/vnd.github.v3+json"}
    files: dict[str, str] = {}
    max_files = 80
    max_total_chars = 800_000
    total_chars = 0

    async def walk(path: str) -> None:
        nonlocal total_chars
        if len(files) >= max_files:
            return
        list_url = f"{CLAWHUB_API}/repos/{owner}/{repo}/contents/{path}?ref={ref}"
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(list_url, headers=headers)
            if resp.status_code == 404:
                return
            resp.raise_for_status()
            items = resp.json()
            if isinstance(items, dict):
                items = [items]
            if not isinstance(items, list):
                return
            for item in items:
                if len(files) >= max_files or total_chars >= max_total_chars:
                    return
                if not isinstance(item, dict):
                    continue
                item_type = item.get("type")
                item_path = str(item.get("path", "")).strip()
                if not item_path:
                    continue
                if item_type == "dir":
                    await walk(item_path)
                    continue
                if item_type != "file":
                    continue
                download_url = str(item.get("download_url", "")).strip()
                if not download_url:
                    continue
                file_resp = await client.get(download_url)
                if file_resp.status_code != 200:
                    continue
                text = file_resp.text
                rel = item_path[len(base_path) :].lstrip("/")
                if not rel:
                    rel = Path(item_path).name
                files[rel] = text
                total_chars += len(text)

    try:
        await walk(base_path)
    except Exception:
        logger.exception("Failed to fetch GitHub tree bundle: %s/%s %s %s", owner, repo, ref, base_path)
        return None
    if "SKILL.md" not in files:
        return None
    return files


async def fetch_skill_bundle_from_url(url: str) -> tuple[str, dict[str, str]] | None:
    """Fetch skill bundle from URL (GitHub tree/root or direct SKILL.md URL)."""
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    path = parsed.path.rstrip("/")
    if host in {"github.com", "www.github.com"}:
        parts = [p for p in path.split("/") if p]
        if len(parts) >= 4 and parts[2] == "tree":
            owner, repo, _, ref = parts[:4]
            base_path = "/".join(parts[4:]) if len(parts) > 4 else ""
            if not base_path:
                base_path = ""
            name = _extract_skill_name(parts[-1]) if len(parts) > 4 else _extract_skill_name(repo)
            if not name:
                name = "skill"
            bundle = await _fetch_github_tree_bundle(owner, repo, ref, base_path)
            if bundle:
                return name, bundle
        if len(parts) >= 2:
            owner, repo = parts[0], parts[1]
            name = _extract_skill_name(repo)
            for ref in ("main", "master"):
                raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{ref}/SKILL.md"
                text = await _fetch_text(raw_url)
                if text:
                    return name or "skill", {"SKILL.md": text}
    text = await fetch_skill_from_url(url)
    if not text:
        return None
    return guess_skill_name_from_url(url), {"SKILL.md": text}


def _is_safe_relpath(relpath: str) -> bool:
    p = Path(relpath)
    cleaned = relpath.strip()
    if not cleaned:
        return False
    if p.is_absolute() or ".." in p.parts:
        return False
    if any(part in {"", ".", ".."} for part in p.parts):
        return False
    return not len(cleaned) > 240


def install_skill_bundle(
    name: str,
    files: dict[str, str],
    workspace_dir: str | Path | None = None,
    *,
    force: bool = False,
) -> Path:
    """Install a complete skill bundle (SKILL.md + supporting files)."""
    from pyclaw.agents.progress import ProgressEvent, ProgressStatus, emit_progress

    if workspace_dir is None:
        workspace_dir = Path.home() / ".pyclaw" / "workspace"
    workspace_dir = Path(workspace_dir)
    task_id = f"install-skill-{name}"
    emit_progress(
        ProgressEvent(task_id=task_id, status=ProgressStatus.STARTED, message=f"Installing skill '{name}'...")
    )
    skill_root = workspace_dir / ".skills" / name
    skill_file = skill_root / "SKILL.md"
    if skill_file.exists() and not force:
        emit_progress(
            ProgressEvent(task_id=task_id, status=ProgressStatus.FAILED, message=f"Skill '{name}' already installed")
        )
        raise FileExistsError(f"Skill '{name}' already installed at {skill_file}. Use --force to overwrite.")
    if force and skill_root.exists():
        shutil.rmtree(skill_root, ignore_errors=True)
    skill_root.mkdir(parents=True, exist_ok=True)
    if "SKILL.md" not in files:
        raise ValueError("Skill bundle missing SKILL.md")
    for relpath, content in files.items():
        if not _is_safe_relpath(relpath):
            raise ValueError(f"Unsafe path in bundle: {relpath}")
        out = skill_root / relpath
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(content, encoding="utf-8")
    emit_progress(
        ProgressEvent(
            task_id=task_id, status=ProgressStatus.COMPLETED, progress=1.0, message=f"Skill '{name}' installed"
        )
    )
    return skill_file


def install_skill(
    name: str,
    content: str,
    workspace_dir: str | Path | None = None,
    *,
    force: bool = False,
) -> Path:
    """Install one-file skill content."""
    return install_skill_bundle(name=name, files={"SKILL.md": content}, workspace_dir=workspace_dir, force=force)


def install_skill_via_clawhub(name: str) -> tuple[bool, str]:
    """Install a skill with local clawhub CLI if available."""
    return _run_clawhub("install", name, timeout_s=60.0)


def remove_skill(name: str, workspace_dir: str | Path | None = None) -> bool:
    """Remove an installed skill (local pyclaw workspace first, then clawhub fallback)."""
    if workspace_dir is None:
        workspace_dir = Path.home() / ".pyclaw" / "workspace"
    workspace_dir = Path(workspace_dir)
    skills_dir = workspace_dir / ".skills" / name
    if skills_dir.exists():
        shutil.rmtree(skills_dir)
        return True
    ok, _ = _run_clawhub("uninstall", name)
    return ok


def clawhub_sync() -> tuple[bool, str]:
    return _run_clawhub("sync", timeout_s=60.0)


def clawhub_update_all() -> tuple[bool, str]:
    return _run_clawhub("update", "--all", timeout_s=60.0)


def clawhub_inspect(name: str) -> tuple[bool, str]:
    ok, out = _run_clawhub("inspect", name, "--json")
    if ok:
        return ok, out
    return _run_clawhub("inspect", name)


def _parse_clawhub_list_output(text: str) -> list[dict[str, str]]:
    parsed: list[dict[str, str]] = []
    if not text:
        return parsed
    try:
        obj = json.loads(text)
        if isinstance(obj, list):
            for item in obj:
                if isinstance(item, dict):
                    name = str(item.get("slug") or item.get("name") or "").strip()
                    if name:
                        parsed.append({"name": name, "path": str(item.get("path", "")), "source": "clawhub"})
            return parsed
    except Exception:
        pass
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith(("Installed", "-")):
            continue
        name = _extract_skill_name(line)
        if name:
            parsed.append({"name": name, "path": "", "source": "clawhub"})
    return parsed


def list_installed_skills(workspace_dir: str | Path | None = None) -> list[dict[str, str]]:
    """List installed skills in pyclaw workspace and clawhub (if available)."""
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
                results.append({"name": child.name, "path": str(skill_file), "source": source})

    ok, out = _run_clawhub("list", "--json")
    if ok:
        results.extend(_parse_clawhub_list_output(out))
    else:
        ok2, out2 = _run_clawhub("list")
        if ok2:
            results.extend(_parse_clawhub_list_output(out2))
    dedup: dict[tuple[str, str], dict[str, str]] = {}
    for item in results:
        key = (item.get("name", ""), item.get("source", ""))
        dedup[key] = item
    return [dedup[k] for k in sorted(dedup.keys())]
