"""Generate the API reference pages of the website from LLMSlim's signatures and docstrings.

The pages are written to ``web/src/data/api-reference.ts`` in the shape the site's documentation already renders
(``DocPage`` in ``web/src/data/docs.ts``): one page per module, one section per public name, each with its summary and
a typed stub of its signature and docstring. The source is read with griffe, statically, so no optional dependency has
to be installed and nothing is imported.

``tests/test_api_reference.py`` fails when the file is out of date. Regenerate it after changing a public signature or
docstring, or the version::

    python scripts/api_reference.py --write

While ``CHANGELOG.md`` lists changes under ``[Unreleased]``, the pages say they describe the main branch, not the
release in ``__version__``. The site shows them as the 1.0 docs, next to a frozen reference of the release PyPI
installs, which was generated once from a checkout of its tag (``git worktree add <dir> v0.12.0``)::

    python scripts/api_reference.py --write --source <dir> \\
        --output web/src/data/api-reference-0.12.ts --name API_REFERENCE_DOCS_0_12
"""

from __future__ import annotations

import argparse
import inspect
import json
import logging
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "web" / "src" / "data" / "api-reference.ts"
WIDTH = 100

#: The modules with a reference page, in the order the site lists them.
PAGES: Dict[str, Dict[str, str]] = {
    "llmslim": {
        "slug": "api-llmslim",
        "title": "API reference: llmslim",
        "subtitle": "Every public name in the llmslim package, with its signature and docstring.",
        "what": "compression, context planning, the agent context runtime, cache planning, token counting and the "
        "rewrite engine",
    },
    "llmslim.memory": {
        "slug": "api-llmslim-memory",
        "title": "API reference: llmslim.memory",
        "subtitle": "Memory, its stores and its result types, with their signatures and docstrings.",
        "what": "agent memory with no LLM in the loop: Memory, its stores and its result types",
    },
}

_ROLE = re.compile(r":(?:py:)?[a-z]+:`~?([^`]+)`")
_TICKS = re.compile(r"`+([^`]+)`+")


def load(root: Path = ROOT) -> Any:
    """The ``llmslim`` package as griffe reads it from this checkout, or from the checkout at ``root``."""

    import griffe

    logging.getLogger("griffe").setLevel(logging.ERROR)  # it notes every unannotated **kwargs
    loader = griffe.GriffeLoader(
        search_paths=[str(root)], docstring_parser="google", allow_inspection=False
    )
    # By name on the search path only: an ``llmslim`` folder in the working directory must not win over ``root``.
    package = loader.load("llmslim", try_relative_path=False)
    loader.resolve_aliases(external=False, implicit=False)
    return package


def _target(obj: Any) -> Any:
    return obj.final_target if obj.is_alias else obj


def _docstring(obj: Any) -> str:
    return inspect.cleandoc(obj.docstring.value) if obj.docstring else ""


def _plain(text: str) -> str:
    """Docstring markup as plain text, for the page's prose."""

    text = _ROLE.sub(lambda match: match.group(1).split(".")[-1], text)
    return " ".join(_TICKS.sub(r"\1", text).split())


def _summary(obj: Any) -> str:
    first = _docstring(obj).split("\n\n")[0]
    return _plain(first) if first else "No docstring yet."


def _quoted(text: str, indent: str) -> List[str]:
    if not text:
        return []
    lines = text.replace('"""', '\\"\\"\\"').splitlines()
    if len(lines) == 1:
        return [f'{indent}"""{lines[0]}"""']
    body = [f"{indent}{line}" if line else "" for line in lines[1:]]
    return [f'{indent}"""{lines[0]}', *body, f'{indent}"""']


def _parameters(function: Any) -> List[str]:
    rendered: List[str] = []
    kinds = [parameter.kind.value for parameter in function.parameters]
    for index, parameter in enumerate(function.parameters):
        kind = kinds[index]
        if (
            kind == "keyword-only"
            and "keyword-only" not in kinds[:index]
            and "variadic positional" not in kinds
        ):
            rendered.append("*")
        prefix = {"variadic positional": "*", "variadic keyword": "**"}.get(kind, "")
        text = prefix + parameter.name
        if parameter.annotation is not None:
            text += f": {parameter.annotation}"
        if parameter.default is not None and not prefix:
            text += (
                f" = {parameter.default}"
                if parameter.annotation is not None
                else f"={parameter.default}"
            )
        rendered.append(text)
        if kind == "positional-only" and (
            index + 1 == len(kinds) or kinds[index + 1] != "positional-only"
        ):
            rendered.append("/")
    return rendered


def _def(function: Any, indent: str = "", name: Optional[str] = None) -> List[str]:
    keyword = "async def" if "async" in function.labels else "def"
    returns = f" -> {function.returns}" if function.returns is not None else ""
    parameters = _parameters(function)
    head = f"{indent}{keyword} {name or function.name}("
    one_line = head + ", ".join(parameters) + f"){returns}:"
    if len(one_line) <= WIDTH:
        return [one_line]
    return [
        head,
        *(f"{indent}    {parameter}," for parameter in parameters),
        f"{indent}){returns}:",
    ]


def _function_stub(function: Any, name: str) -> str:
    lines = _def(function, name=name)
    lines += _quoted(_docstring(function), "    ") or ["    ..."]
    return "\n".join(lines)


def _declared_in_body(cls: Any, member: Any) -> bool:
    """Whether an attribute is declared in the class body, not assigned inside one of its methods."""

    for other in cls.members.values():
        other = _target(other)
        if other.is_function and other.lineno and other.endlineno:
            if other.lineno <= (member.lineno or 0) <= other.endlineno:
                return False
    return True


def _member_lines(cls: Any, member: Any) -> List[str]:
    """One member of a class: a field, an enum value, a method or a property."""

    if member.is_attribute and "property" in member.labels:
        returns = f" -> {member.annotation}" if member.annotation is not None else ""
        lines = ["    @property", f"    def {member.name}(self){returns}:"]
        return lines + (_quoted(_docstring(member).split("\n\n")[0], "        ") or ["        ..."])
    if member.is_attribute:
        if not _declared_in_body(cls, member):
            return []  # assigned in a method, not declared on the class
        text = f"    {member.name}"
        if member.annotation is not None:
            text += f": {member.annotation}"
        if member.value is not None:
            value = str(member.value)
            text += f" = {value if len(value) <= 60 else '...'}"
        return [text]
    if member.is_function:
        decorators = [
            f"    @{label}" for label in ("classmethod", "staticmethod") if label in member.labels
        ]
        summary = _docstring(member).split("\n\n")[0]
        return decorators + _def(member, "    ") + (_quoted(summary, "        ") or ["        ..."])
    return []


def _class_stub(cls: Any, name: str) -> str:
    bases = [str(base) for base in cls.bases]
    lines = [f"class {name}({', '.join(bases)}):" if bases else f"class {name}:"]
    lines += _quoted(_docstring(cls), "    ")
    separate = len(lines) > 1  # a blank line after the docstring, and around methods and properties
    members = [
        _target(member)
        for member_name, member in cls.members.items()
        if not member_name.startswith("_") or member_name in ("__init__", "__call__")
    ]
    # A dataclass's __init__ is generated from its fields, which are listed instead.
    if "dataclass" in cls.labels:
        members = [member for member in members if member.name != "__init__"]
    for member in sorted(members, key=lambda member: (member.lineno or 0, member.name)):
        rendered = _member_lines(cls, member)
        if rendered:
            block = member.is_function or "property" in member.labels
            if separate or block:
                lines.append("")
            lines += rendered
            separate = block
    if len(lines) == 1:
        lines.append("    ...")
    return "\n".join(lines)


def _attribute_stub(attribute: Any, name: str) -> str:
    text = name
    if attribute.annotation is not None:
        text += f": {attribute.annotation}"
    if attribute.value is not None:
        value = str(attribute.value)
        text += f" = {value if len(value) <= 60 else '...'}"
    return text


def _section_id(name: str, taken: set) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    section_id, n = base, 2
    while section_id in taken:
        section_id, n = f"{base}-{n}", n + 1
    taken.add(section_id)
    return section_id


def unannotated(package: Any, modules: Iterable[str] = PAGES) -> List[str]:
    """Public functions and methods of the documented modules with a parameter or return type missing."""

    missing = []

    def check(function: Any, where: str) -> None:
        for parameter in function.parameters:
            if parameter.name in ("self", "cls") or parameter.kind.value.startswith("variadic"):
                continue
            if parameter.annotation is None:
                missing.append(f"{where}: parameter {parameter.name!r}")
        if function.returns is None and function.name != "__init__":
            missing.append(f"{where}: return type")

    for module_path in modules:
        module = package[module_path.split(".", 1)[1]] if "." in module_path else package
        for name in module.exports or ():
            if name.startswith("_"):
                continue
            obj = _target(module[name])
            if obj.is_function:
                check(obj, f"{module_path}.{name}")
            elif obj.is_class:
                for member_name, member in obj.members.items():
                    member = _target(member)
                    public = not member_name.startswith("_") or member_name == "__init__"
                    if public and member.is_function:
                        check(member, f"{module_path}.{name}.{member_name}")
    return missing


def _release_month(version: str, root: Path = ROOT) -> str:
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    match = re.search(
        rf"^## \[{re.escape(version)}\] - (\d{{4}})-(\d{{2}})-(\d{{2}})", changelog, re.M
    )
    if match is None:
        raise SystemExit(f"CHANGELOG.md has no dated entry for {version}")
    return date(*map(int, match.groups())).strftime("%B %Y")


def unreleased(root: Path = ROOT) -> bool:
    """Whether ``CHANGELOG.md`` lists changes under ``[Unreleased]``: the source is past its last release."""

    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    match = re.search(r"^## \[Unreleased\][^\n]*\n(.*?)(?=^## \[|\Z)", changelog, re.M | re.S)
    return bool(match and re.search(r"^\s*- ", match.group(1), re.M))


def _source(version: str, root: Path) -> str:
    """What the pages were generated from, as the site says it."""

    if unreleased(root):
        return f"the main branch (llmslim {version} and the changes since, not released yet)"
    return f"the source of llmslim {version}"


def page(package: Any, module_path: str, root: Path = ROOT) -> Dict[str, Any]:
    """The ``DocPage`` for one module."""

    meta = PAGES[module_path]
    module = package[module_path.split(".", 1)[1]] if "." in module_path else package
    version = str(package["__version__"].value).strip("'\"")
    source = _source(version, root)
    names = [name for name in (module.exports or []) if not name.startswith("_")]
    taken: set = {"about"}
    sections = [
        {
            "id": "about",
            "title": "About this reference",
            "content": f"Each entry is a name you import from {module_path}: {meta['what']}. It shows the full "
            f"signature with its type annotations, and the docstring. The page is generated from {source} by "
            "scripts/api_reference.py, so it changes only when the code does.",
        }
    ]
    for name in names:
        obj = _target(module[name])
        if obj.is_function:
            title, code = f"{name}()", _function_stub(obj, name)
        elif obj.is_class:
            title, code = name, _class_stub(obj, name)
        else:
            title, code = name, _attribute_stub(obj, name)
        sections.append(
            {
                "id": _section_id(name, taken),
                "title": title,
                "content": _summary(obj),
                "codeSnippet": {
                    "language": "python",
                    "filename": f"from {module_path} import {name}",
                    "code": code,
                },
            }
        )
    words = sum(len(json.dumps(section).split()) for section in sections)
    others = [
        {"title": other["title"], "slug": other["slug"]}
        for path, other in PAGES.items()
        if path != module_path
    ]
    return {
        "slug": meta["slug"],
        "title": meta["title"],
        "subtitle": meta["subtitle"],
        "description": f"Signatures, type annotations and docstrings of the {len(names)} public names in "
        f"{module_path}, generated from {source}.",
        "category": "API Reference",
        "searchIntent": f"LLMSlim Python API reference for {module_path}: signatures, parameters and return types.",
        "lastUpdated": _release_month(version, root),
        "readingTime": f"{max(1, round(words / 220))} min read",
        "sections": sections,
        "faqs": [],
        "relatedPages": [*others, {"title": "Python quickstart", "slug": "quickstart-python"}],
    }


def render(package: Any, root: Path = ROOT, name: str = "API_REFERENCE_DOCS") -> str:
    """The TypeScript module the site imports."""

    pages = [page(package, module_path, root) for module_path in PAGES]
    body = json.dumps(pages, indent=2, ensure_ascii=False)
    if root == ROOT:
        header = (
            "// Generated by scripts/api_reference.py from the llmslim source; do not edit by hand.\n"
            "// After changing a public signature or docstring: python scripts/api_reference.py --write\n"
        )
    else:
        version = str(package["__version__"].value).strip("'\"")
        header = (
            f"// Generated by scripts/api_reference.py from the source of llmslim {version}; do not edit by hand.\n"
            f"// A released version does not change. To regenerate it, from a checkout of v{version} in <dir>:\n"
            f"// python scripts/api_reference.py --write --source <dir> --output <this file> --name {name}\n"
        )
    return (
        header
        + f'import type {{ DocPage }} from "./docs"\n\nexport const {name}: DocPage[] = {body}\n'
    )


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--write", action="store_true", help=f"Rewrite {OUTPUT.relative_to(ROOT)}.")
    parser.add_argument(
        "--source",
        type=Path,
        default=ROOT,
        help="Read the llmslim source from this checkout instead (for the reference of a release).",
    )
    parser.add_argument("--output", type=Path, help="The file to write or check (needs --source).")
    parser.add_argument(
        "--name",
        default="API_REFERENCE_DOCS",
        help="The exported constant's name (needs --source).",
    )
    args = parser.parse_args(argv)
    source = args.source.resolve()
    if source != ROOT and args.output is None:
        parser.error(
            "--source needs --output: the reference of this checkout stays in its own file"
        )
    if source == ROOT and (args.output is not None or args.name != "API_REFERENCE_DOCS"):
        parser.error("--output and --name go with --source")
    output = (args.output or OUTPUT).resolve()
    shown = output.relative_to(ROOT) if output.is_relative_to(ROOT) else output
    text = render(load(source), source, args.name)
    if args.write:
        with output.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        print(f"wrote {shown}")
        return 0
    current = output.read_text(encoding="utf-8").replace("\r\n", "\n") if output.exists() else ""
    if current != text:
        print(f"{shown} is out of date: run python scripts/api_reference.py --write")
        return 1
    print(f"{shown} is up to date.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
