#!/usr/bin/env python3
"""
根据 git 变更范围解析 pytest 目标：全量 ``tests/`` 或增量（相关包目录 / 改动的测试文件）。

环境变量：
  PYCLAW_TEST_BASE   — incremental/run 时 diff 的基准 ref（默认 origin/master）
  PYCLAW_TEST_MODE          — run 子命令默认模式：full | incremental
  PYCLAW_INCREMENTAL_EMPTY  — incremental 且无匹配时：skip=跳过 pytest；否则全量

示例：
  python scripts/pytest_scope.py targets
  python scripts/pytest_scope.py run --mode incremental -- -q
  PYCLAW_TEST_BASE=origin/main python scripts/pytest_scope.py run --mode incremental
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 改动这些文件时始终全量跑测（避免漏测依赖）
FULL_SUITE_TRIGGERS = frozenset(
    {
        "pyproject.toml",
        "tests/conftest.py",
    }
)


def _git(argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(ROOT), *argv],
        capture_output=True,
        text=True,
    )


def merge_base(base: str) -> str:
    r = _git(["merge-base", base, "HEAD"])
    if r.returncode == 0 and r.stdout.strip():
        return r.stdout.strip()
    return base


def changed_files(base_ref: str) -> list[str]:
    ref = merge_base(base_ref)
    r = _git(["diff", "--name-only", "--diff-filter=ACMR", ref, "HEAD"])
    if r.returncode != 0:
        print(f"pytest_scope: git diff failed (base={base_ref!r}): {r.stderr}", file=sys.stderr)
        return []
    return [ln.strip().replace("\\", "/") for ln in r.stdout.splitlines() if ln.strip()]


def _test_dirs_for_src(norm: str) -> list[str] | None:
    """Return test directory paths for a source file, or None => 应全量."""
    if not norm.startswith("src/pyclaw/") or not norm.endswith(".py"):
        return []
    rel = norm[len("src/pyclaw/") :]
    if "/" not in rel:
        return None
    parent = rel.rsplit("/", 1)[0]
    parts = parent.split("/")
    for i in range(len(parts), 0, -1):
        sub = "/".join(parts[:i])
        d = ROOT / "tests" / "pyclaw" / sub
        if d.is_dir():
            return [str(d)]
    first = ROOT / "tests" / "pyclaw" / parts[0]
    if first.is_dir():
        return [str(first)]
    return None


def resolve_targets(files: list[str]) -> list[str] | None:
    """
    None  => 全量 tests/
    []    => 无匹配（仅非 src/tests/skills 等变更）
    list  => 传给 pytest 的路径
    """
    targets: set[str] = set()
    relevant = False

    for f in files:
        if f in FULL_SUITE_TRIGGERS:
            return None

        if f.startswith("tests/pyclaw/") and f.endswith(".py") and "__pycache__" not in f:
            relevant = True
            if f.endswith("__init__.py") and f.count("/") <= 2:
                continue
            p = ROOT / f
            if p.is_file():
                targets.add(f)

        if f.startswith("src/pyclaw/") and f.endswith(".py"):
            relevant = True
            dirs = _test_dirs_for_src(f)
            if dirs is None:
                return None
            targets.update(dirs)

        if f.startswith("skills/") and f.endswith((".md", ".py", ".json")):
            relevant = True
            d = ROOT / "tests" / "pyclaw" / "agents" / "skills"
            if d.is_dir():
                targets.add(str(d))

    if not relevant:
        return []

    if not targets:
        return None

    return sorted(targets)


def cmd_targets(base: str, fallback_full: bool) -> int:
    files = changed_files(base)
    if not files:
        print("tests" if fallback_full else "")
        return 0
    t = resolve_targets(files)
    if t is None:
        print("tests")
        return 0
    if not t:
        print("tests" if fallback_full else "")
        return 0
    print(" ".join(t))
    return 0


def cmd_run(mode: str, base: str, pytest_argv: list[str]) -> int:
    if mode == "full":
        paths = ["tests"]
    else:
        files = changed_files(base)
        if not files:
            paths = ["tests"]
        else:
            t = resolve_targets(files)
            if t is None:
                paths = ["tests"]
            elif not t:
                if os.environ.get("PYCLAW_INCREMENTAL_EMPTY") == "skip":
                    print(
                        "pytest_scope: incremental — 无相关变更，跳过 pytest "
                        "(unset PYCLAW_INCREMENTAL_EMPTY 则改为全量)",
                        file=sys.stderr,
                    )
                    return 0
                paths = ["tests"]
            else:
                paths = t
    argv = [sys.executable, "-m", "pytest", *paths, *pytest_argv]
    print(f"pytest_scope: mode={mode} -> {' '.join(paths)}", file=sys.stderr)
    return subprocess.call(argv, cwd=ROOT)


def main() -> int:
    default_base = os.environ.get("PYCLAW_TEST_BASE", "origin/master")
    parser = argparse.ArgumentParser(
        description="全量 / 增量 pytest 范围（基于 git diff）",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_t = sub.add_parser("targets", help="输出一行：pytest 路径（空格分隔）或 tests")
    p_t.add_argument("--base", default=default_base, help="对比基准 ref")
    p_t.add_argument(
        "--fallback-full",
        action="store_true",
        help="无变更或仅非代码文件时仍输出 tests",
    )

    p_r = sub.add_parser("run", help="直接执行 pytest")
    p_r.add_argument(
        "--mode",
        choices=("full", "incremental"),
        default=os.environ.get("PYCLAW_TEST_MODE", "full"),
    )
    p_r.add_argument("--base", default=default_base)
    p_r.add_argument(
        "pytest_args",
        nargs=argparse.REMAINDER,
        help="pytest 参数（可写 -- -q）",
    )

    args = parser.parse_args()
    if args.cmd == "targets":
        return cmd_targets(args.base, args.fallback_full)

    py_args = args.pytest_args
    if py_args and py_args[0] == "--":
        py_args = py_args[1:]
    return cmd_run(args.mode, args.base, py_args)


if __name__ == "__main__":
    raise SystemExit(main())
