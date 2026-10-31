"""Snapshot LLMSlim's public API, so that changing it is a deliberate act.

The snapshot (``tests/fixtures/public_api.json``) records what ``docs/API_STABILITY.md`` promises:

- **Python**: for every public module, each name in ``__all__`` with its kind and signature; for classes, their
  bases and public members, and for enums, their values.
- **CLI**: the arguments of every ``llmslim`` command.
- **HTTP**: the routes and methods of ``llmslim serve``.
- **MCP**: the tools of ``llmslim mcp``, with their input and output schemas and hints.
- **Entry points** and the ``LLMSLIM_*`` **environment variables** the package reads.

``tests/test_public_api.py`` compares the live API with it. After an intended change, regenerate it and say what
changed in the CHANGELOG::

    python scripts/public_api.py --write

Run it in an environment with ``pip install -e ".[all,dev]"``. A module that can't be imported there keeps its
recorded entry. gptme and Hermes Agent can't be installed with ``all``; update their entries from an environment
that has them, leaving the rest of the snapshot alone::

    python scripts/public_api.py --write --module llmslim.integrations.gptme
"""

from __future__ import annotations

import argparse
import ast
import asyncio
import enum
import importlib
import inspect
import json
import os
import re
import sys
import typing
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:  # describe this checkout's llmslim, whatever is installed
    sys.path.insert(0, str(ROOT))
PACKAGE = ROOT / "llmslim"
SNAPSHOT = ROOT / "tests" / "fixtures" / "public_api.json"

STABLE = "stable"
EXPERIMENTAL = "experimental"

#: The public modules: ``status`` applies to every name in the module's ``__all__``, except the names listed under
#: ``experimental``. Keep this in step with docs/API_STABILITY.md.
MODULES: Dict[str, Dict[str, Any]] = {
    "llmslim": {"status": STABLE, "experimental": ["TransformersKVSession"]},
    "llmslim.context": {"status": STABLE},
    "llmslim.memory": {"status": STABLE},
    "llmslim.memory.compat": {"status": STABLE},
    "llmslim.planning": {"status": STABLE},
    "llmslim.tokens": {"status": STABLE},
    "llmslim.tools": {
        "status": STABLE,
        "experimental": [
            "LazyToolRegistry",
            "RankedTool",
            "ToolContextPlan",
            "ToolSelection",
            "plan_tool_context",
            "rank_tools",
            "select_tools",
        ],
    },
    "llmslim.mcp": {"status": STABLE},
    "llmslim.mcp_server": {"status": STABLE},
    "llmslim.server": {"status": STABLE},
    "llmslim.integrations.exa": {"status": STABLE},
    "llmslim.integrations.gptme": {"status": STABLE},
    "llmslim.integrations.haystack": {"status": STABLE},
    "llmslim.integrations.hermes": {"status": STABLE},
    "llmslim.integrations.langchain": {"status": STABLE},
    "llmslim.integrations.langchain_agents": {"status": STABLE},
    "llmslim.integrations.llama_index": {"status": STABLE},
    "llmslim.integrations.mongodb": {"status": STABLE},
    "llmslim.integrations.neo4j": {"status": STABLE},
    "llmslim.integrations.openai_agents": {"status": STABLE},
    "llmslim.integrations.pydantic_ai": {"status": STABLE},
    "llmslim.integrations.sarvam": {"status": STABLE},
    "llmslim.integrations.sarvam_documents": {"status": STABLE},
    "llmslim.integrations.sarvam_text": {"status": STABLE},
    "llmslim.integrations.web_search": {"status": STABLE},
    "llmslim.integrations.zoho": {"status": STABLE},
    "llmslim.proxy": {"status": EXPERIMENTAL},
    "llmslim.semantic_retrieval": {"status": EXPERIMENTAL},
    "llmslim.tool_retrieval": {"status": EXPERIMENTAL},
}

#: Importable modules that are not public: their names are reached through a public module above, or they are
#: implementation (and every module whose path has a part starting with "_" is internal too).
INTERNAL = frozenset(
    {
        "llmslim.adapters",
        "llmslim.analysis",
        "llmslim.cache",
        "llmslim.cache_adapters",
        "llmslim.chunking",
        "llmslim.cli",
        "llmslim.context_graph",
        "llmslim.context_policy",
        "llmslim.core",
        "llmslim.cost",
        "llmslim.embeddings",
        "llmslim.envelope",
        "llmslim.focus",
        "llmslim.hosted",
        "llmslim.integrations",
        "llmslim.integrations.gptme_plugin",
        "llmslim.memory.mongo",
        "llmslim.memory.postgres",
        "llmslim.memory.stores",
        "llmslim.modes",
        "llmslim.optimizers",
        "llmslim.optimizers.json_opt",
        "llmslim.optimizers.markdown_opt",
        "llmslim.optimizers.xml_opt",
        "llmslim.optimizers.yaml_opt",
        "llmslim.pipelines",
        "llmslim.planning.boundary",
        "llmslim.planning.budget",
        "llmslim.planning.candidates",
        "llmslim.planning.mcp",
        "llmslim.planning.models",
        "llmslim.planning.planner",
        "llmslim.planning.policy",
        "llmslim.planning.profiles",
        "llmslim.planning.progressive",
        "llmslim.planning.scoring",
        "llmslim.planning.validation",
        "llmslim.proxy.app",
        "llmslim.proxy.cli",
        "llmslim.proxy.rewrite",
        "llmslim.proxy.store",
        "llmslim.quality",
        "llmslim.ranking",
        "llmslim.rerank",
        "llmslim.rewrite",
        "llmslim.rewrite.base",
        "llmslim.rewrite.engine",
        "llmslim.rewrite.templates",
        "llmslim.rewrite.validation",
        "llmslim.runtime",
        "llmslim.self_hosted",
        "llmslim.tokenization",
    }
)

#: ``llmslim`` subcommands: (module, parser builder, status). The default command (no subcommand) compresses text.
COMMANDS: Tuple[Tuple[str, str, str], ...] = (
    ("llmslim.cli", "build_parser", STABLE),
    ("llmslim.cli", "build_context_parser", STABLE),
    ("llmslim.cli", "build_plan_parser", STABLE),
    ("llmslim.cli", "build_tools_parser", STABLE),
    ("llmslim.mcp_server", "build_parser", STABLE),
    ("llmslim.server", "build_parser", STABLE),
    ("llmslim.proxy.cli", "build_parser", EXPERIMENTAL),
    ("llmslim.proxy.cli", "build_stats_parser", EXPERIMENTAL),
    ("llmslim.proxy.cli", "build_wrap_parser", EXPERIMENTAL),
)

#: Modules whose ``LLMSLIM_*`` variables configure the hosted demo, not the package.
_ENV_EXCLUDED = ("llmslim/hosted.py",)
_ENV_NAME = re.compile(r"LLMSLIM_[A-Z0-9_]+")


# --------------------------------------------------------------------------- module discovery


def package_modules() -> List[str]:
    """Every module in the package, from the file tree (nothing is imported)."""

    names = []
    for path in sorted(PACKAGE.rglob("*.py")):
        parts = list(path.relative_to(ROOT).with_suffix("").parts)
        if parts[-1] == "__init__":
            parts.pop()
        names.append(".".join(parts))
    return names


def is_internal(module: str) -> bool:
    return module in INTERNAL or any(part.startswith("_") for part in module.split("."))


# --------------------------------------------------------------------------- Python surface


class _Text:
    """Renders as its text, so ``str(Signature)`` shows normalized annotations and defaults."""

    __slots__ = ("text",)

    def __init__(self, text: str) -> None:
        self.text = text

    def __repr__(self) -> str:
        return self.text


_DOTTED = re.compile(r"\b(?:[A-Za-z_][A-Za-z0-9_]*\.)+([A-Za-z_][A-Za-z0-9_]*)")


def _annotation_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if value is type(None):
        return "None"
    if isinstance(value, typing.ForwardRef):
        return value.__forward_arg__
    if isinstance(value, type) and typing.get_origin(value) is None:
        return value.__qualname__
    # typing constructs: drop module paths ("typing.Optional[llmslim.core.ContextRole]" -> "Optional[ContextRole]").
    return _DOTTED.sub(r"\1", repr(value)).replace("NoneType", "None")


def _type_name(value: Any) -> str:
    """A value's type name, the same on every operating system (a path is a ``Path``, not a ``PosixPath``)."""

    return "Path" if isinstance(value, os.PathLike) else type(value).__name__


def _value_text(value: Any) -> str:
    """A default value as text that is the same on every machine and supported Python version."""

    if isinstance(value, enum.Enum):  # before str and int: an enum may subclass either
        return f"{type(value).__name__}.{value.name}"
    if value is None or isinstance(value, (bool, int, float, str, bytes)):
        return repr(value)
    if isinstance(value, tuple):
        items = [_value_text(item) for item in value]
        return "(" + ", ".join(items) + ("," if len(items) == 1 else "") + ")"
    if isinstance(value, list):
        return "[" + ", ".join(_value_text(item) for item in value) + "]"
    if isinstance(value, (set, frozenset)):
        items = sorted(_value_text(item) for item in value)
        return (
            f"{type(value).__name__}({{{', '.join(items)}}})"
            if items
            else f"{type(value).__name__}()"
        )
    if isinstance(value, dict):
        pairs = (f"{_value_text(k)}: {_value_text(v)}" for k, v in value.items())
        return "{" + ", ".join(pairs) + "}"
    if isinstance(value, os.PathLike):
        return "<path>"
    if inspect.isclass(value) or inspect.isroutine(value):
        return getattr(value, "__qualname__", type(value).__name__)
    if repr(value) == "<factory>":  # a dataclass field with default_factory
        return "<factory>"
    return f"<{type(value).__name__}>"


def _signature(obj: Any, *, drop_first: bool = False, keep: Optional[set] = None) -> Optional[str]:
    try:
        signature = inspect.signature(obj)
    except (TypeError, ValueError):
        return None
    parameters = list(signature.parameters.values())
    if (
        drop_first
        and parameters
        and parameters[0].kind
        in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        )
    ):
        parameters = parameters[1:]
    if keep is not None:
        parameters = [parameter for parameter in parameters if parameter.name in keep]
    normalized = [
        parameter.replace(
            annotation=parameter.annotation
            if parameter.annotation is inspect.Parameter.empty
            else _Text(_annotation_text(parameter.annotation)),
            default=parameter.default
            if parameter.default is inspect.Parameter.empty
            else _Text(_value_text(parameter.default)),
        )
        for parameter in parameters
    ]
    returns = signature.return_annotation
    if returns is not inspect.Signature.empty:
        returns = _Text(_annotation_text(returns))
    return str(signature.replace(parameters=normalized, return_annotation=returns))


def _annotations(owner: type) -> Dict[str, Any]:
    """The annotations a class declares itself (``inspect.get_annotations`` is Python 3.10+)."""

    get_annotations = getattr(inspect, "get_annotations", None)
    if get_annotations is not None:
        return dict(get_annotations(owner))
    return dict(vars(owner).get("__annotations__", {}))


def _ours(klass: type) -> bool:
    return (getattr(klass, "__module__", "") or "").split(".")[0] == "llmslim"


def _class_signature(klass: type) -> Optional[str]:
    for owner in klass.__mro__:
        if "__init__" in vars(owner) and owner is not object:
            if owner is klass or _ours(owner):
                return _signature(vars(owner)["__init__"], drop_first=True)
            break
    # Construction comes from a framework base class (a Pydantic model, a NamedTuple, ...): keep the parameters
    # that LLMSlim's own classes declare, so a framework release can't change the snapshot.
    declared: set = set()
    for owner in klass.__mro__:
        if owner is klass or _ours(owner):
            declared.update(_annotations(owner))
    return _signature(klass, keep=declared)


def _member(value: Any) -> Optional[str]:
    if isinstance(value, (property,)) or type(value).__name__ == "cached_property":
        return "property"
    if isinstance(value, classmethod):
        return f"classmethod {_signature(value.__func__, drop_first=True)}"
    if isinstance(value, staticmethod):
        return f"staticmethod {_signature(value.__func__)}"
    if inspect.isfunction(value):
        prefix = "async method" if inspect.iscoroutinefunction(value) else "method"
        return f"{prefix} {_signature(value, drop_first=True)}"
    if inspect.isclass(value):
        return "class"
    return None


def _class(klass: type) -> Dict[str, Any]:
    entry: Dict[str, Any] = {
        "kind": "enum" if issubclass(klass, enum.Enum) else "class",
        # Public names only: a framework or an implementation module may move a class without changing it, and a
        # private base is implementation (its public members are recorded below).
        "bases": [
            base.__qualname__ for base in klass.__bases__ if not base.__name__.startswith("_")
        ],
    }
    if issubclass(klass, enum.Enum):
        entry["values"] = {member.name: _value_text(member.value) for member in klass}
    else:
        entry["signature"] = _class_signature(klass)
    members: Dict[str, str] = {}
    for owner in reversed(klass.__mro__):
        if not (owner is klass or _ours(owner)):
            continue
        annotations = _annotations(owner)
        for name, annotation in annotations.items():
            if not name.startswith("_"):
                members[name] = f"attribute: {_annotation_text(annotation)}"
        for name, value in vars(owner).items():
            if name.startswith("_") or (issubclass(klass, enum.Enum) and name in klass.__members__):
                continue
            described = _member(value)
            if described is not None:
                members[name] = described
            elif name not in annotations:
                members[name] = f"attribute: {_type_name(value)}"
    entry["members"] = dict(sorted(members.items()))
    return entry


def describe(value: Any) -> Dict[str, Any]:
    """One public name: what it is and how it is called."""

    if inspect.isclass(value):
        entry = _class(value)
    elif inspect.isroutine(value):
        kind = "async function" if inspect.iscoroutinefunction(value) else "function"
        entry = {"kind": kind, "signature": _signature(value)}
    elif typing.get_origin(value) is not None or isinstance(value, typing.TypeVar):
        entry = {"kind": "type alias", "value": _annotation_text(value)}
    elif inspect.ismodule(value):
        entry = {"kind": "module", "value": value.__name__}
    else:
        entry = {"kind": "data", "type": _type_name(value)}
    message = vars(value).get("__deprecated__") if hasattr(value, "__dict__") else None
    if isinstance(message, str):
        entry["deprecated"] = message
    return entry


def module_surface(name: str) -> Dict[str, Any]:
    """The recorded surface of one public module. Raises ImportError when its optional dependency is missing."""

    config = MODULES[name]
    module = importlib.import_module(name)
    exported = getattr(module, "__all__", None)
    if exported is None:
        raise AssertionError(f"{name} is public but has no __all__")
    experimental = set(config.get("experimental", ()))
    unknown = experimental - set(exported)
    if unknown:
        raise AssertionError(f"{name}: experimental names not in __all__: {sorted(unknown)}")
    names = {}
    for exported_name in sorted(exported):
        entry = describe(getattr(module, exported_name))
        entry["status"] = EXPERIMENTAL if exported_name in experimental else config["status"]
        names[exported_name] = entry
    return {"status": config["status"], "names": names}


# --------------------------------------------------------------------------- CLI, HTTP, MCP, environment


def _arguments(parser: argparse.ArgumentParser) -> Dict[str, Any]:
    arguments: Dict[str, Any] = {}
    subcommands: Dict[str, Any] = {}
    for action in parser._actions:
        if isinstance(action, argparse._HelpAction):
            continue
        if isinstance(action, argparse._SubParsersAction):
            for name, subparser in action.choices.items():
                subcommands[name] = _arguments(subparser)
            continue
        key = ", ".join(action.option_strings) or action.dest
        described: Dict[str, Any] = {}
        if action.nargs == 0:
            described["flag"] = True
        elif action.nargs is not None:
            described["nargs"] = action.nargs
        if action.choices is not None:
            described["choices"] = sorted(str(choice) for choice in action.choices)
        if action.required and action.option_strings:
            described["required"] = True
        arguments[key] = described
    result: Dict[str, Any] = {"arguments": dict(sorted(arguments.items()))}
    if subcommands:
        result["subcommands"] = dict(sorted(subcommands.items()))
    return result


def cli_surface() -> Dict[str, Any]:
    commands = {}
    for module, builder, status in COMMANDS:
        parser = getattr(importlib.import_module(module), builder)()
        commands[parser.prog] = {"status": status, **_arguments(parser)}
    return dict(sorted(commands.items()))


def http_surface() -> Dict[str, Any]:
    """Routes of ``llmslim serve``. Raises ImportError without the server extra."""

    from llmslim.memory import Memory
    from llmslim.server import create_app

    routes = {}
    for route in create_app(Memory()).routes:
        routes[route.path] = sorted(route.methods or ())
    return {"status": STABLE, "routes": dict(sorted(routes.items()))}


def _schema(node: Any) -> Any:
    """A JSON schema without its human-readable ``title`` and ``description`` annotations."""

    if isinstance(node, list):
        return [_schema(item) for item in node]
    if not isinstance(node, dict):
        return node
    cleaned = {}
    for key, value in node.items():
        if key in ("title", "description"):
            continue
        if key in ("properties", "$defs", "definitions", "patternProperties") and isinstance(
            value, dict
        ):
            cleaned[key] = {name: _schema(sub) for name, sub in value.items()}
        else:
            cleaned[key] = _schema(value)
    return cleaned


def mcp_surface() -> Dict[str, Any]:
    """Tools of ``llmslim mcp``. Raises ImportError without the mcp extra."""

    from llmslim.mcp_server import build_server
    from llmslim.memory import Memory
    from mcp import Client

    async def listed() -> Any:
        async with Client(build_server(Memory())) as client:
            return (await client.list_tools()).tools

    tools = {}
    for tool in asyncio.run(listed()):
        dumped = tool.model_dump(by_alias=True, exclude_none=True)
        hints = {
            key: value for key, value in dumped.get("annotations", {}).items() if key != "title"
        }
        tools[tool.name] = {
            "inputSchema": _schema(dumped.get("inputSchema")),
            "outputSchema": _schema(dumped.get("outputSchema")),
            "annotations": dict(sorted(hints.items())),
        }
    return {"status": STABLE, "tools": dict(sorted(tools.items()))}


def entry_points_surface() -> Dict[str, Any]:
    """Console scripts and plugin entry points, read from pyproject.toml. Raises ImportError on Python 3.10."""

    import tomllib

    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    groups: Dict[str, Any] = {"console_scripts": dict(project.get("scripts", {}))}
    groups.update(
        {group: dict(points) for group, points in project.get("entry-points", {}).items()}
    )
    return dict(sorted(groups.items()))


def environment_surface() -> List[str]:
    """``LLMSLIM_*`` names that appear as string literals in the package (the hosted demo's are excluded)."""

    found = set()
    for path in sorted(PACKAGE.rglob("*.py")):
        if path.relative_to(ROOT).as_posix() in _ENV_EXCLUDED:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if _ENV_NAME.fullmatch(node.value):
                    found.add(node.value)
    return sorted(found)


# --------------------------------------------------------------------------- snapshot I/O


def _optional(collect: Callable[[], Any], previous: Any, label: str) -> Any:
    try:
        return collect()
    except ImportError as error:
        state = "kept the recorded entry" if previous is not None else "NOT RECORDED"
        print(f"{label}: {state} ({error})", file=sys.stderr)
        return previous


def collect(previous: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    """The whole surface. Parts that can't be built here keep their entries from ``previous``."""

    previous = previous or {}
    old_modules = previous.get("python", {})
    python = {}
    for name in sorted(MODULES):
        surface = _optional(lambda name=name: module_surface(name), old_modules.get(name), name)
        if surface is not None:
            python[name] = surface
    return {
        "about": "Generated by scripts/public_api.py; see docs/API_STABILITY.md. Do not edit by hand.",
        "python": python,
        "cli": cli_surface(),
        "http": _optional(http_surface, previous.get("http"), "llmslim serve routes"),
        "mcp": _optional(mcp_surface, previous.get("mcp"), "llmslim mcp tools"),
        "entry_points": _optional(
            entry_points_surface, previous.get("entry_points"), "entry points"
        ),
        "environment": environment_surface(),
    }


def load(path: Path = SNAPSHOT) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def dump(surface: Mapping[str, Any]) -> str:
    return json.dumps(surface, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def differences(recorded: Any, live: Any, path: str = "") -> List[str]:
    """Readable paths where ``live`` differs from ``recorded``."""

    if isinstance(recorded, dict) and isinstance(live, dict):
        found = []
        for key in sorted(set(recorded) | set(live)):
            where = f"{path}.{key}" if path else str(key)
            if key not in live:
                found.append(f"removed: {where}")
            elif key not in recorded:
                found.append(f"added:   {where}")
            else:
                found.extend(differences(recorded[key], live[key], where))
        return found
    if recorded != live:
        return [f"changed: {path}\n    was: {recorded!r}\n    now: {live!r}"]
    return []


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--write", action="store_true", help=f"Rewrite {SNAPSHOT.relative_to(ROOT)}."
    )
    parser.add_argument(
        "--module",
        action="append",
        choices=sorted(MODULES),
        help="Only these Python modules (repeatable); the rest of the snapshot is kept as recorded.",
    )
    args = parser.parse_args(argv)
    previous = load() if SNAPSHOT.exists() else {}
    if args.module:
        surface = json.loads(dump(previous))
        for name in args.module:
            surface["python"][name] = module_surface(name)
    else:
        surface = collect(previous)
    if args.write:
        SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
        with SNAPSHOT.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(dump(surface))
        print(f"wrote {SNAPSHOT.relative_to(ROOT)}")
        return 0
    found = differences(previous, json.loads(dump(surface)))
    print("\n".join(found) if found else "The public API matches the snapshot.")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
