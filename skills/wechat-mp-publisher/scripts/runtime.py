from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Any

DEFAULT_THEME = "lapis"
DEFAULT_HIGHLIGHT = "solarized-light"
DEFAULT_MCP_SERVER = "wenyan-mcp"
DEFAULT_MCP_CONFIG = Path.home() / ".openclaw" / "mcp.json"
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
VIDEO_REF_RE = re.compile(r"\(([^)]+\.mp4)\)", re.IGNORECASE)


def run(
    payload: dict[str, Any] | None = None,
    *,
    workspace_dir: str = "",
    skill_key: str = "claw-wechat-article",
) -> dict[str, Any]:
    payload = payload or {}
    workspace = Path(workspace_dir or Path.cwd())
    skill_root = Path(__file__).resolve().parents[1]

    action = str(payload.get("action", "probe")).strip().lower()
    remote = _to_bool(payload.get("remote"), default=False)
    dry_run = _to_bool(payload.get("dry_run"), default=(action != "publish"))
    theme = str(payload.get("theme", DEFAULT_THEME)).strip() or DEFAULT_THEME
    highlight = str(payload.get("highlight", DEFAULT_HIGHLIGHT)).strip() or DEFAULT_HIGHLIGHT
    mcp_server = str(payload.get("mcp_server", DEFAULT_MCP_SERVER)).strip() or DEFAULT_MCP_SERVER
    mcp_config = _resolve_path(payload.get("mcp_config_file"), workspace, fallback=DEFAULT_MCP_CONFIG)
    article_path = _resolve_path(payload.get("article_path"), workspace)

    credentials = _load_credentials(payload, skill_root)
    probe = _build_probe(
        article_path=article_path,
        credentials=credentials,
        remote=remote,
        mcp_config=mcp_config,
    )

    if action not in {"probe", "publish"}:
        return {
            "skill": skill_key,
            "status": "invalid",
            "summary": "Unsupported action; expected probe or publish.",
            "blocking_items": ["invalid_action"],
            "action": action,
        }

    use_video = _resolve_use_video(payload.get("use_video"), probe["video_refs"])
    plan = _build_plan(
        skill_root=skill_root,
        article_path=article_path,
        remote=remote,
        use_video=use_video,
        theme=theme,
        highlight=highlight,
        mcp_server=mcp_server,
        mcp_config=mcp_config,
    )
    blockers = _collect_blockers(probe=probe, plan=plan, action=action)
    status = "ok" if not blockers else "needs_attention"

    if action == "probe" or dry_run:
        return {
            "skill": skill_key,
            "status": status,
            "summary": "Probe completed; publish plan prepared.",
            "action": action,
            "dry_run": dry_run,
            "remote": remote,
            "use_video": use_video,
            "probe": probe,
            "plan": plan,
            "blocking_items": blockers,
        }

    if blockers:
        return {
            "skill": skill_key,
            "status": "needs_attention",
            "summary": "Publish blocked by failed preflight checks.",
            "action": action,
            "remote": remote,
            "probe": probe,
            "plan": plan,
            "blocking_items": blockers,
        }

    if remote:
        result = _execute_remote_publish(
            article_path=article_path,
            mcp_server=mcp_server,
            mcp_config=mcp_config,
            credentials=credentials,
            theme=theme,
        )
    else:
        result = _execute_local_publish(
            plan=plan,
            credentials=credentials,
            cwd=workspace,
        )
    result.setdefault("skill", skill_key)
    result.setdefault("action", "publish")
    result.setdefault("remote", remote)
    return result


def _build_probe(
    *,
    article_path: Path | None,
    credentials: dict[str, str],
    remote: bool,
    mcp_config: Path,
) -> dict[str, Any]:
    binaries = {
        "wenyan": bool(shutil.which("wenyan")),
        "node": bool(shutil.which("node")),
        "mcporter": bool(shutil.which("mcporter")),
    }
    article = {
        "exists": bool(article_path and article_path.is_file()),
        "path": str(article_path) if article_path else "",
        "frontmatter": {"title": False, "cover": False},
        "video_refs": [],
    }
    if article["exists"] and article_path:
        text = article_path.read_text(encoding="utf-8", errors="ignore")
        article["frontmatter"] = _frontmatter_presence(text)
        article["video_refs"] = VIDEO_REF_RE.findall(text)

    creds_ok = bool(credentials.get("app_id") and credentials.get("app_secret"))
    mcp_ok = mcp_config.is_file()
    return {
        "binaries": binaries,
        "credentials": {
            "resolved": creds_ok,
            "source": credentials.get("source", ""),
        },
        "mcp_config": {"path": str(mcp_config), "exists": mcp_ok},
        "article": article,
        "video_refs": len(article["video_refs"]),
        "remote_requested": remote,
    }


def _build_plan(
    *,
    skill_root: Path,
    article_path: Path | None,
    remote: bool,
    use_video: bool,
    theme: str,
    highlight: str,
    mcp_server: str,
    mcp_config: Path,
) -> dict[str, Any]:
    if remote:
        return {
            "mode": "remote",
            "steps": ["upload_file", "publish_article"],
            "toolchain": ["mcporter"],
            "mcp_server": mcp_server,
            "mcp_config_file": str(mcp_config),
            "theme": theme,
            "article_path": str(article_path) if article_path else "",
        }
    if use_video:
        script = skill_root / "scripts" / "publisher" / "publish_with_video.js"
        cmd = ["node", str(script), str(article_path), theme, highlight]
        return {
            "mode": "local-video",
            "toolchain": ["node", "wenyan"],
            "command": cmd,
            "command_display": " ".join(shlex.quote(s) for s in cmd),
        }
    cmd = ["wenyan", "publish", "-f", str(article_path), "-t", theme, "-h", highlight]
    return {
        "mode": "local-basic",
        "toolchain": ["wenyan"],
        "command": cmd,
        "command_display": " ".join(shlex.quote(s) for s in cmd),
    }


def _collect_blockers(*, probe: dict[str, Any], plan: dict[str, Any], action: str) -> list[str]:
    blockers: list[str] = []
    article = probe["article"]
    binaries = probe["binaries"]
    if action == "publish":
        if not article["exists"]:
            blockers.append("article_not_found")
        frontmatter = article["frontmatter"]
        if not frontmatter.get("title"):
            blockers.append("frontmatter_title_missing")
        if not frontmatter.get("cover"):
            blockers.append("frontmatter_cover_missing")
        if not probe["credentials"]["resolved"]:
            blockers.append("wechat_credentials_missing")

    mode = plan.get("mode")
    if mode == "remote":
        if not binaries.get("mcporter"):
            blockers.append("mcporter_missing")
        if not probe["mcp_config"]["exists"]:
            blockers.append("mcp_config_missing")
    elif mode == "local-video":
        if not binaries.get("node"):
            blockers.append("node_missing")
        if not binaries.get("wenyan"):
            blockers.append("wenyan_missing")
        script = Path(plan["command"][1])
        if not script.is_file():
            blockers.append("video_script_missing")
    else:
        if not binaries.get("wenyan"):
            blockers.append("wenyan_missing")
    return blockers


def _execute_local_publish(
    *,
    plan: dict[str, Any],
    credentials: dict[str, str],
    cwd: Path,
) -> dict[str, Any]:
    command = plan.get("command")
    if not isinstance(command, list) or not command:
        return {
            "status": "invalid",
            "summary": "No executable local command found in plan.",
            "blocking_items": ["local_command_missing"],
        }
    env = os.environ.copy()
    env["WECHAT_APP_ID"] = credentials["app_id"]
    env["WECHAT_APP_SECRET"] = credentials["app_secret"]
    proc = subprocess.run(
        command,
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        "status": "ok" if proc.returncode == 0 else "needs_attention",
        "summary": "Local publish finished." if proc.returncode == 0 else "Local publish failed.",
        "mode": plan.get("mode"),
        "command_display": plan.get("command_display", ""),
        "exit_code": proc.returncode,
        "stdout": (proc.stdout or "")[-6000:],
        "stderr": (proc.stderr or "")[-6000:],
        "blocking_items": [] if proc.returncode == 0 else ["publish_command_failed"],
    }


def _execute_remote_publish(
    *,
    article_path: Path | None,
    mcp_server: str,
    mcp_config: Path,
    credentials: dict[str, str],
    theme: str,
) -> dict[str, Any]:
    if article_path is None:
        return {
            "status": "invalid",
            "summary": "Missing article path for remote publish.",
            "blocking_items": ["article_not_found"],
        }
    content = article_path.read_text(encoding="utf-8", errors="ignore")
    upload_args = {
        "content": content,
        "filename": article_path.name,
    }
    upload_res = _run_mcporter_call(
        server_method=f"{mcp_server}.upload_file",
        config_file=mcp_config,
        args=upload_args,
    )
    if upload_res["error"]:
        return {
            "status": "needs_attention",
            "summary": "Remote upload failed.",
            "step": "upload_file",
            "blocking_items": ["remote_upload_failed"],
            "detail": upload_res,
        }
    file_id = str(upload_res["data"].get("file_id", "")).strip()
    if not file_id:
        return {
            "status": "needs_attention",
            "summary": "Remote upload succeeded but file_id is missing.",
            "step": "upload_file",
            "blocking_items": ["remote_upload_file_id_missing"],
            "detail": upload_res,
        }

    publish_args = {
        "file_id": file_id,
        "theme_id": theme,
        "wechat_app_id": credentials["app_id"],
        "wechat_app_secret": credentials["app_secret"],
    }
    publish_res = _run_mcporter_call(
        server_method=f"{mcp_server}.publish_article",
        config_file=mcp_config,
        args=publish_args,
    )
    if publish_res["error"]:
        return {
            "status": "needs_attention",
            "summary": "Remote publish failed.",
            "step": "publish_article",
            "blocking_items": ["remote_publish_failed"],
            "detail": publish_res,
        }
    media_id = str(publish_res["data"].get("media_id", "")).strip()
    if not media_id:
        return {
            "status": "needs_attention",
            "summary": "Remote publish response missing media_id.",
            "step": "publish_article",
            "blocking_items": ["remote_publish_media_id_missing"],
            "detail": publish_res,
        }
    return {
        "status": "ok",
        "summary": "Remote publish completed.",
        "mode": "remote",
        "file_id": file_id,
        "media_id": media_id,
        "blocking_items": [],
    }


def _run_mcporter_call(*, server_method: str, config_file: Path, args: dict[str, Any]) -> dict[str, Any]:
    cmd = [
        "mcporter",
        "call",
        server_method,
        "--config",
        str(config_file),
        "--args",
        json.dumps(args, ensure_ascii=False),
    ]
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
    )
    stdout = (proc.stdout or "").strip()
    stderr = (proc.stderr or "").strip()
    if proc.returncode != 0:
        return {
            "error": True,
            "exit_code": proc.returncode,
            "stdout": stdout[-4000:],
            "stderr": stderr[-4000:],
            "data": {},
        }
    try:
        parsed = json.loads(stdout) if stdout else {}
    except json.JSONDecodeError:
        parsed = {"raw": stdout}
    if isinstance(parsed, dict) and parsed.get("error"):
        return {
            "error": True,
            "exit_code": proc.returncode,
            "stdout": stdout[-4000:],
            "stderr": stderr[-4000:],
            "data": parsed,
        }
    return {
        "error": False,
        "exit_code": proc.returncode,
        "stdout": stdout[-4000:],
        "stderr": stderr[-4000:],
        "data": parsed if isinstance(parsed, dict) else {"raw": parsed},
    }


def _frontmatter_presence(text: str) -> dict[str, bool]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {"title": False, "cover": False}
    raw = match.group(1)
    title = re.search(r"^\s*title\s*:\s*.+$", raw, flags=re.MULTILINE) is not None
    cover = re.search(r"^\s*cover\s*:\s*.+$", raw, flags=re.MULTILINE) is not None
    return {"title": title, "cover": cover}


def _load_credentials(payload: dict[str, Any], skill_root: Path) -> dict[str, str]:
    from_payload = (
        str(payload.get("wechat_app_id", "")).strip(),
        str(payload.get("wechat_app_secret", "")).strip(),
    )
    if from_payload[0] and from_payload[1]:
        return {"app_id": from_payload[0], "app_secret": from_payload[1], "source": "payload"}

    app_id = os.environ.get("WECHAT_APP_ID", "").strip()
    app_secret = os.environ.get("WECHAT_APP_SECRET", "").strip()
    if app_id and app_secret:
        return {"app_id": app_id, "app_secret": app_secret, "source": "env"}

    env_file = skill_root / "wechat.env"
    file_creds = _parse_env_file(env_file)
    if file_creds["app_id"] and file_creds["app_secret"]:
        file_creds["source"] = "wechat.env"
        return file_creds

    for tools_md in _candidate_tools_md():
        creds = _parse_tools_md(tools_md)
        if creds["app_id"] and creds["app_secret"]:
            creds["source"] = str(tools_md)
            return creds
    return {"app_id": "", "app_secret": "", "source": ""}


def _parse_env_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {"app_id": "", "app_secret": "", "source": ""}
    app_id = ""
    app_secret = ""
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        s = line.strip()
        if s.startswith("export WECHAT_APP_ID="):
            app_id = _strip_assignment_value(s.split("=", 1)[1])
        elif s.startswith("export WECHAT_APP_SECRET="):
            app_secret = _strip_assignment_value(s.split("=", 1)[1])
    return {"app_id": app_id, "app_secret": app_secret, "source": ""}


def _parse_tools_md(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {"app_id": "", "app_secret": "", "source": ""}
    app_id = ""
    app_secret = ""
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        m_id = re.search(r"export\s+WECHAT_APP_ID\s*=\s*(\S+)", line)
        if m_id:
            app_id = _strip_assignment_value(m_id.group(1))
        m_secret = re.search(r"export\s+WECHAT_APP_SECRET\s*=\s*(\S+)", line)
        if m_secret:
            app_secret = _strip_assignment_value(m_secret.group(1))
    return {"app_id": app_id, "app_secret": app_secret, "source": ""}


def _candidate_tools_md() -> list[Path]:
    home = Path.home()
    return [
        home / ".openclaw" / "workspace-xina-gongzhonghao" / "TOOLS.md",
        home / ".openclaw" / "workspace" / "TOOLS.md",
    ]


def _resolve_use_video(raw: Any, detected_refs: int) -> bool:
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str):
        normalized = raw.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
    return detected_refs > 0


def _to_bool(value: Any, *, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
    if isinstance(value, int):
        return value != 0
    return default


def _resolve_path(value: Any, workspace: Path, fallback: Path | None = None) -> Path | None:
    if isinstance(value, str) and value.strip():
        raw = value.strip()
        path = Path(raw).expanduser()
        return path if path.is_absolute() else (workspace / path).resolve()
    return fallback.resolve() if fallback is not None else None


def _strip_assignment_value(raw: str) -> str:
    value = raw.strip()
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    return value
