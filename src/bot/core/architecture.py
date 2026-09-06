"""Source-backed architecture model; semantic relationships are reviewed, not inferred."""

import ast
from datetime import UTC, datetime
from functools import lru_cache
from importlib.util import resolve_name
from pathlib import Path
from typing import Literal
from urllib.parse import quote

from pydantic import BaseModel, Field

from bot.config import settings
from bot.core import etiquette

ROOT = Path(__file__).resolve().parents[3]
BOT = ROOT / "src/bot"


class Source(BaseModel):
    path: str
    symbol: str = ""
    repo: str = "bot"


class Component(BaseModel):
    id: str
    label: str
    lane: int = Field(ge=0, le=3)
    row: int = Field(ge=0, le=6)
    summary: str
    details: str
    sources: list[Source]
    tags: list[str]
    status: Literal["implemented", "planned"]


class Connection(BaseModel):
    source: str
    target: str
    label: str
    planned: bool


class Specification(BaseModel):
    nodes: list[Component]
    edges: list[Connection]


def specification() -> Specification:
    return Specification.model_validate_json(
        Path(__file__).with_suffix(".json").read_text()
    )


def module_name(path: Path) -> str:
    parts = list(path.relative_to(BOT).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(["bot", *parts])


def internal_imports(tree: ast.AST, package: str, known: set[str]) -> list[str]:
    result = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(
                a.name
                for a in node.names
                if a.name == "bot" or a.name.startswith("bot.")
            )
        elif isinstance(node, ast.ImportFrom):
            base = (
                resolve_name("." * node.level + (node.module or ""), package)
                if node.level
                else node.module or ""
            )
            if base == "bot" or base.startswith("bot."):
                for alias in node.names:
                    child = f"{base}.{alias.name}"
                    result.add(child if child in known else base)
    return sorted(result)


@lru_cache(maxsize=1)
def source_inventory() -> list[dict]:
    """Parse packaged Python source without importing or executing the modules."""
    modules = []
    paths = sorted(BOT.rglob("*.py"))
    known = {module_name(path) for path in paths}
    for path in paths:
        tree = ast.parse(path.read_text())
        functions = [
            {"name": n.name, "line": n.lineno}
            for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef)
            or isinstance(n, ast.AsyncFunctionDef)
            or isinstance(n, ast.ClassDef)
        ]
        name = module_name(path)
        package = name if path.name == "__init__.py" else name.rpartition(".")[0]
        imports = internal_imports(tree, package, known)
        modules.append(
            {
                "path": str(path.relative_to(ROOT)),
                "package": str(path.relative_to(BOT).parent).replace(".", "root"),
                "name": name,
                "imports": imports,
                "functions": functions,
            }
        )
    return modules


def source_reference(source: Source, modules: list[dict]) -> dict:
    path = ROOT / source.path
    line = None
    if source.repo == "bot" and source.symbol:
        module = next((m for m in modules if m["path"] == source.path), None)
        if module:
            line = next(
                (f["line"] for f in module["functions"] if f["name"] == source.symbol),
                None,
            )
    evidence = "external reference"
    if source.repo == "bot":
        evidence = "packaged source" if path.is_file() else "repository reference"
        if source.symbol and line is None:
            evidence = "symbol not found"
    url = f"https://github.com/zzstoatzz/{source.repo}/blob/main/{quote(source.path)}"
    return {
        **source.model_dump(),
        "line": line,
        "evidence": evidence,
        "url": url + (f"#L{line}" if line else ""),
    }


def architecture_model() -> dict:
    spec = specification()
    modules = source_inventory()
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "basis": "Reviewed semantic connections plus Python AST inventory from this running release. Configuration is not a service health check.",
        "nodes": [
            {
                **n.model_dump(),
                "sources": [source_reference(s, modules) for s in n.sources],
            }
            for n in spec.nodes
        ],
        "edges": [e.model_dump() for e in spec.edges],
        "modules": modules,
        "entry_points": [
            f
            for m in modules
            if m["path"] == "src/bot/agent.py"
            for f in m["functions"]
            if f["name"].startswith("process_")
        ],
        "prompt_blocks": [
            f
            for m in modules
            if m["path"] == "src/bot/agent.py"
            for f in m["functions"]
            if f["name"].startswith("inject_")
        ],
        "skills": sorted(p.parent.name for p in (ROOT / "skills").glob("*/SKILL.md")),
        "configuration": {
            "main_model": settings.agent_model,
            "policy_model": settings.policy_model,
            "memory_model": settings.extraction_model,
            "etiquette": etiquette.VERSION,
            "prefect_authenticated": bool(settings.prefect_api_auth_string),
            "semble_writes_configured": bool(settings.semble_api_key),
        },
    }
