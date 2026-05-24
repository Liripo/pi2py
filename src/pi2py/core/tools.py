from __future__ import annotations

import asyncio
import fnmatch
import json
import os
import subprocess
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ToolHandler = Callable[[dict[str, Any]], Awaitable[str]]


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: ToolHandler

    def to_openai_tool(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


def create_default_tools(cwd: Path, *, allow_bash: bool = True) -> list[Tool]:
    root = cwd.resolve()
    tools = [
        Tool(
            name="read",
            description="读取工作区中的 UTF-8 文本文件。",
            parameters=_schema(
                {
                    "path": {"type": "string"},
                    "offset": {"type": "integer", "minimum": 0, "default": 0},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 1000, "default": 200},
                },
                ["path"],
            ),
            handler=lambda args: _read(root, args),
        ),
        Tool(
            name="write",
            description="在工作区写入 UTF-8 文本文件，并自动创建父目录。",
            parameters=_schema(
                {"path": {"type": "string"}, "content": {"type": "string"}},
                ["path", "content"],
            ),
            handler=lambda args: _write(root, args),
        ),
        Tool(
            name="edit",
            description="在工作区文件中替换完全匹配的文本。",
            parameters=_schema(
                {
                    "path": {"type": "string"},
                    "old": {"type": "string"},
                    "new": {"type": "string"},
                    "replace_all": {"type": "boolean", "default": False},
                },
                ["path", "old", "new"],
            ),
            handler=lambda args: _edit(root, args),
        ),
        Tool(
            name="grep",
            description="在文本文件中搜索字面量文本。",
            parameters=_schema(
                {
                    "pattern": {"type": "string"},
                    "path": {"type": "string", "default": "."},
                    "glob": {"type": "string", "default": "*"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 500, "default": 100},
                },
                ["pattern"],
            ),
            handler=lambda args: _grep(root, args),
        ),
        Tool(
            name="find",
            description="根据 glob 模式查找文件。",
            parameters=_schema(
                {
                    "pattern": {"type": "string"},
                    "path": {"type": "string", "default": "."},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 500, "default": 100},
                },
                ["pattern"],
            ),
            handler=lambda args: _find(root, args),
        ),
        Tool(
            name="ls",
            description="列出工作区路径下的文件和目录。",
            parameters=_schema(
                {
                    "path": {"type": "string", "default": "."},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 500, "default": 100},
                },
                [],
            ),
            handler=lambda args: _ls(root, args),
        ),
    ]
    if allow_bash:
        tools.append(
            Tool(
                name="bash",
                description="在工作区运行 shell 命令，并返回 stdout/stderr。",
                parameters=_schema(
                    {
                        "command": {"type": "string"},
                        "timeout": {"type": "integer", "minimum": 1, "maximum": 60, "default": 20},
                    },
                    ["command"],
                ),
                handler=lambda args: _bash(root, args),
            )
        )
    return tools


def _schema(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {"type": "object", "properties": properties, "required": required, "additionalProperties": False}


def _resolve(root: Path, raw_path: str | None) -> Path:
    raw = raw_path or "."
    path = (root / raw).resolve()
    if path != root and root not in path.parents:
        raise ValueError(f"路径越过工作区边界：{raw}")
    return path


async def _read(root: Path, args: dict[str, Any]) -> str:
    path = _resolve(root, args["path"])
    offset = int(args.get("offset", 0))
    limit = int(args.get("limit", 200))
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    selected = lines[offset : offset + limit]
    prefix = f"{path.relative_to(root)} 第 {offset + 1}-{offset + len(selected)} 行，共 {len(lines)} 行"
    return prefix + "\n" + "\n".join(f"{offset + i + 1}: {line}" for i, line in enumerate(selected))


async def _write(root: Path, args: dict[str, Any]) -> str:
    path = _resolve(root, args["path"])
    path.parent.mkdir(parents=True, exist_ok=True)
    content = str(args["content"])
    path.write_text(content, encoding="utf-8")
    return f"已写入 {path.relative_to(root)}（{len(content)} 个字符）"


async def _edit(root: Path, args: dict[str, Any]) -> str:
    path = _resolve(root, args["path"])
    text = path.read_text(encoding="utf-8")
    old = str(args["old"])
    new = str(args["new"])
    if old not in text:
        raise ValueError("未找到待替换文本")
    count = -1 if args.get("replace_all") else 1
    updated = text.replace(old, new, count)
    path.write_text(updated, encoding="utf-8")
    replacements = text.count(old) if args.get("replace_all") else 1
    return f"已编辑 {path.relative_to(root)}（{replacements} 处替换）"


async def _grep(root: Path, args: dict[str, Any]) -> str:
    base = _resolve(root, args.get("path"))
    pattern = str(args["pattern"])
    glob = str(args.get("glob") or "*")
    limit = int(args.get("limit", 100))
    matches: list[str] = []
    for path in _iter_files(base):
        rel = path.relative_to(root).as_posix()
        if not fnmatch.fnmatch(path.name, glob) and not fnmatch.fnmatch(rel, glob):
            continue
        try:
            for lineno, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                if pattern in line:
                    matches.append(f"{rel}:{lineno}: {line[:300]}")
                    if len(matches) >= limit:
                        return "\n".join(matches)
        except OSError:
            continue
    return "\n".join(matches) if matches else "未找到匹配项"


async def _find(root: Path, args: dict[str, Any]) -> str:
    base = _resolve(root, args.get("path"))
    pattern = str(args["pattern"])
    limit = int(args.get("limit", 100))
    found = []
    for path in _iter_files(base):
        rel = path.relative_to(root).as_posix()
        if fnmatch.fnmatch(path.name, pattern) or fnmatch.fnmatch(rel, pattern):
            found.append(rel)
            if len(found) >= limit:
                break
    return "\n".join(found) if found else "未找到文件"


async def _ls(root: Path, args: dict[str, Any]) -> str:
    path = _resolve(root, args.get("path"))
    limit = int(args.get("limit", 100))
    entries = sorted(path.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower()))[:limit]
    return "\n".join(f"{entry.name}/" if entry.is_dir() else entry.name for entry in entries)


async def _bash(root: Path, args: dict[str, Any]) -> str:
    command = str(args["command"])
    timeout = int(args.get("timeout", 20))

    def run() -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            command,
            cwd=root,
            shell=True,
            text=True,
            capture_output=True,
            timeout=timeout,
        )

    try:
        completed = await asyncio.to_thread(run)
    except subprocess.TimeoutExpired:
        return f"命令在 {timeout} 秒后超时"
    payload = {
        "exit_code": completed.returncode,
        "stdout": completed.stdout[-8000:],
        "stderr": completed.stderr[-8000:],
    }
    return json.dumps(payload, ensure_ascii=False)


def _iter_files(base: Path):
    ignored_dirs = {".git", ".venv", "__pycache__", "node_modules", "dist", "build"}
    if base.is_file():
        yield base
        return
    for current, dirs, files in os.walk(base):
        dirs[:] = [item for item in dirs if item not in ignored_dirs]
        for name in files:
            yield Path(current) / name
