#!/usr/bin/env python3
"""Validate the static HTML diagram contract.

The checker intentionally validates structure and unsafe affordances rather
than judging prose. It scans the reconstructed fragments under
``_includes/diagrams/static`` and the two legacy include paths that are being
converted in parallel.

Examples:

    python3 kkamji_scripts/blog/validate_static_diagrams.py --root .
    python3 kkamji_scripts/blog/validate_static_diagrams.py --root . \
        --inventory /tmp/static-diagrams.json \
        --report /tmp/static-diagrams-report.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

SPECIAL_PATHS = (
    Path("_includes/diagrams/packer-golden-image.html"),
    Path("_includes/diagrams/aws-certification-map.html"),
)
SPECIAL_SOURCE_ALIASES = {
    "_includes/diagrams/static/iac/packer-golden-image-flow.html": "_includes/diagrams/packer-golden-image.html",
    "_includes/diagrams/static/sap-c02/aws-certification-tiers.html": "_includes/diagrams/aws-certification-map.html",
}
STATIC_DIR = Path("_includes/diagrams/static")
VOID_TAGS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}
FORBIDDEN_TAGS = {
    "a",
    "audio",
    "button",
    "canvas",
    "details",
    "embed",
    "form",
    "iframe",
    "input",
    "link",
    "object",
    "script",
    "select",
    "summary",
    "template",
    "textarea",
    "video",
}
INTERACTIVE_ATTRIBUTES = {
    "aria-controls",
    "aria-expanded",
    "aria-pressed",
    "data-action",
    "data-choice",
    "data-enhanced",
    "data-focus",
    "data-playing",
    "data-step",
    "data-track",
    "data-toggle",
    "data-target",
    "contenteditable",
    "draggable",
}
BANNED_CHARS = re.compile(
    "[\u00b7\u2012\u2013\u2014\u2015\u2018\u2019\u201c\u201d\u2026\u2192]"
)
BANNED_ENTITIES = re.compile(
    r"&#(?:x0*(?:b7|2012|2013|2014|2015|2018|2019|201c|201d|2026|2192)|(?:183|8210|8211|8212|8213|8216|8217|8220|8221|8230|8594));",
    re.IGNORECASE,
)
GEOMETRY_STYLE = re.compile(
    r"\b(?:bottom|font-size|height|inset|left|max-height|max-width|min-height|min-width|position|right|rotate|scale|top|transform|translate|width|z-index)\s*:",
    re.IGNORECASE,
)
MOTION_STYLE = re.compile(
    r"(?:animation|transition)(?:-[a-z-]+)?\s*:|@keyframes\b", re.IGNORECASE
)
HIDDEN_STYLE = re.compile(
    r"\b(?:content-visibility|display|visibility)\s*:\s*(?:none|hidden)", re.IGNORECASE
)
INTERACTION_STYLE = re.compile(
    r"\b(?:cursor|pointer-events)\s*:\s*(?:pointer|auto|all)", re.IGNORECASE
)
EVENT_ATTRIBUTE = re.compile(r"^on[a-z]+$", re.IGNORECASE)
ASSET_ATTRIBUTES = {"src", "srcset", "poster"}
LOCAL_ASSET_PREFIXES = ("/assets/", "assets/")


@dataclass
class Finding:
    severity: str
    code: str
    message: str
    line: int | None = None


@dataclass
class Element:
    tag: str
    attrs: dict[str, str]
    classes: set[str]
    line: int
    parent: Element | None = None
    children: list[Element] = field(default_factory=list)
    closed: bool = False


class FragmentParser(HTMLParser):
    """Small tolerant HTML parser with enough tree data for semantic checks."""

    def __init__(self, root: Path, source: Path) -> None:
        super().__init__(convert_charrefs=True)
        self.root = root
        self.source = source
        self.findings: list[Finding] = []
        self.elements: list[Element] = []
        self.roots: list[Element] = []
        self.stack: list[Element] = []
        self.ids: dict[str, int] = {}

    def add(
        self, severity: str, code: str, message: str, line: int | None = None
    ) -> None:
        self.findings.append(Finding(severity, code, message, line))

    def _line(self) -> int:
        return self.getpos()[0]

    def _check_typography(self, value: str, line: int) -> None:
        if BANNED_CHARS.search(value) or BANNED_ENTITIES.search(value):
            self.add(
                "error",
                "banned-typography",
                "non-ASCII dash, quote, ellipsis, arrow or middle dot is present",
                line,
            )

    def _check_asset(self, tag: str, attr: str, value: str, line: int) -> None:
        for part in value.split(","):
            tokens = part.strip().split()
            if not tokens:
                continue
            candidate = tokens[0]
            if not candidate or candidate.startswith(("#", "data:", "mailto:")):
                continue
            if "{{" in candidate or "{%" in candidate:
                continue
            parsed = urlsplit(candidate)
            if parsed.scheme or candidate.startswith("//"):
                if parsed.scheme in {"http", "https"} and tag == "img":
                    self.add(
                        "warning",
                        "external-asset",
                        f"external image URL remains: {candidate}",
                        line,
                    )
                continue
            clean = parsed.path.split("?", 1)[0].split("#", 1)[0]
            if clean.startswith(LOCAL_ASSET_PREFIXES):
                asset = self.root / clean.lstrip("/")
                if not asset.is_file():
                    self.add(
                        "error",
                        "missing-asset",
                        f"local asset does not exist: {clean}",
                        line,
                    )

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        line = self._line()
        values = {name.lower(): value or "" for name, value in attrs}
        self._check_typography(self.get_starttag_text() or "", line)
        if tag in FORBIDDEN_TAGS:
            self.add(
                "error", "forbidden-tag", f"static fragment contains <{tag}>", line
            )
        if tag == "style":
            self.add(
                "error",
                "style-block",
                "fragment must use shared CSS, not a <style> block",
                line,
            )
        if tag == "img" and values.get("data-static-diagram", "").lower() != "true":
            self.add(
                "error",
                "missing-static-marker",
                'diagram images must set data-static-diagram="true"',
                line,
            )

        element = Element(
            tag=tag,
            attrs=values,
            classes=set(values.get("class", "").split()),
            line=line,
            parent=self.stack[-1] if self.stack else None,
        )
        if element.parent:
            element.parent.children.append(element)
        else:
            self.roots.append(element)
        self.elements.append(element)

        element_id = values.get("id", "")
        if element_id:
            if element_id in self.ids:
                self.add("error", "duplicate-id", f"id is repeated: {element_id}", line)
            else:
                self.ids[element_id] = line

        for attr, value in values.items():
            self._check_typography(value, line)
            if EVENT_ATTRIBUTE.fullmatch(attr):
                self.add(
                    "error",
                    "event-handler",
                    f"event handler attribute is not allowed: {attr}",
                    line,
                )
            if attr in INTERACTIVE_ATTRIBUTES or attr == "tabindex":
                self.add(
                    "error",
                    "interactive-attribute",
                    f"interactive attribute is not allowed: {attr}",
                    line,
                )
            if attr == "role" and value.lower() in {
                "button",
                "checkbox",
                "combobox",
                "link",
                "listbox",
                "radio",
                "slider",
                "switch",
                "tab",
            }:
                self.add(
                    "error",
                    "interactive-role",
                    f"interactive role is not allowed: {value}",
                    line,
                )
            if attr == "hidden":
                self.add(
                    "error",
                    "hidden-content",
                    "hidden-by-default content is not allowed",
                    line,
                )
            if attr == "style":
                if GEOMETRY_STYLE.search(value):
                    self.add(
                        "error",
                        "geometry-style",
                        "inline geometry or downscaling style is not allowed",
                        line,
                    )
                if MOTION_STYLE.search(value):
                    self.add(
                        "error",
                        "motion-style",
                        "animation and transition styles are not allowed",
                        line,
                    )
                if HIDDEN_STYLE.search(value):
                    self.add(
                        "error",
                        "hidden-content",
                        "hidden-by-default content is not allowed",
                        line,
                    )
                if INTERACTION_STYLE.search(value):
                    self.add(
                        "error",
                        "interaction-style",
                        "interactive pointer style is not allowed",
                        line,
                    )
            if attr in ASSET_ATTRIBUTES:
                self._check_asset(tag, attr, value, line)

        if tag not in VOID_TAGS:
            self.stack.append(element)
        else:
            element.closed = True

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if self.stack and self.stack[-1].tag == tag.lower():
            self.stack[-1].closed = True
            self.stack.pop()

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        line = self._line()
        if tag in VOID_TAGS:
            self.add(
                "error", "unexpected-close", f"void element </{tag}> is closed", line
            )
            return
        if not self.stack:
            self.add(
                "error",
                "unexpected-close",
                f"closing tag has no open element: </{tag}>",
                line,
            )
            return
        if self.stack[-1].tag == tag:
            self.stack[-1].closed = True
            self.stack.pop()
            return
        open_tags = [element.tag for element in self.stack]
        if tag not in open_tags:
            self.add(
                "error",
                "unexpected-close",
                f"closing tag has no matching opener: </{tag}>",
                line,
            )
            return
        self.add(
            "error",
            "mismatched-close",
            f"closing tag does not match <{self.stack[-1].tag}>: </{tag}>",
            line,
        )
        while self.stack:
            element = self.stack.pop()
            element.closed = element.tag == tag
            if element.tag == tag:
                break

    def handle_data(self, data: str) -> None:
        self._check_typography(data, self._line())

    def finish(self) -> None:
        for element in self.stack:
            self.add(
                "error",
                "unclosed-tag",
                f"element is not closed: <{element.tag}>",
                element.line,
            )


def _has_class(element: Element, name: str) -> bool:
    return name in element.classes


def _descendants(element: Element) -> Iterable[Element]:
    for child in element.children:
        yield child
        yield from _descendants(child)


def semantic_findings(parser: FragmentParser) -> list[Finding]:
    findings: list[Finding] = []
    figures = [
        element
        for element in parser.elements
        if element.tag == "figure" and _has_class(element, "sd")
    ]
    if not figures:
        findings.append(
            Finding("error", "missing-root", "fragment must contain a figure.sd root")
        )
    elif len(figures) > 1:
        findings.append(
            Finding(
                "error",
                "multiple-roots",
                "fragment must contain exactly one figure.sd root",
            )
        )

    titles = [
        element
        for element in parser.elements
        if element.tag == "figcaption" and _has_class(element, "sd-title")
    ]
    if not titles:
        findings.append(
            Finding(
                "error", "missing-title", "figure must contain a figcaption.sd-title"
            )
        )

    nodes = [element for element in parser.elements if _has_class(element, "sd-node")]
    semantic_content = any(
        _has_class(element, class_name)
        for element in parser.elements
        for class_name in ("sd-node", "sd-table", "sd-band", "sd-lane")
    )
    if not semantic_content:
        findings.append(
            Finding(
                "error",
                "missing-content",
                "figure must contain .sd-node, .sd-table, .sd-band or .sd-lane content",
            )
        )
    for node in nodes:
        if not _has_class(node, "sd-label") and not any(
            _has_class(child, "sd-label") for child in _descendants(node)
        ):
            findings.append(
                Finding(
                    "error",
                    "node-without-label",
                    ".sd-node must contain a .sd-label",
                    node.line,
                )
            )

    for lane in (
        element for element in parser.elements if _has_class(element, "sd-lane")
    ):
        if not any(
            _has_class(child, "sd-lane-title") for child in _descendants(lane)
        ) and not _has_class(lane, "sd-lane-title"):
            findings.append(
                Finding(
                    "error",
                    "lane-without-title",
                    ".sd-lane must contain a .sd-lane-title",
                    lane.line,
                )
            )
    for band in (
        element for element in parser.elements if _has_class(element, "sd-band")
    ):
        if not any(
            _has_class(child, "sd-band-title") for child in _descendants(band)
        ) and not _has_class(band, "sd-band-title"):
            findings.append(
                Finding(
                    "error",
                    "band-without-title",
                    ".sd-band must contain a .sd-band-title",
                    band.line,
                )
            )

    for element in parser.elements:
        for attr in ("aria-labelledby", "aria-describedby"):
            reference = element.attrs.get(attr, "")
            if reference:
                for target in reference.split():
                    if target not in parser.ids:
                        findings.append(
                            Finding(
                                "error",
                                "missing-aria-target",
                                f"{attr} references missing id: {target}",
                                element.line,
                            )
                        )
    return findings


def parse_fragment(root: Path, path: Path, special: bool) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace")
    parser = FragmentParser(root, path)
    try:
        parser.feed(text)
        parser.close()
    except (ValueError, AssertionError) as exc:
        parser.add("error", "html-parse", f"HTML parser failed: {exc}")
    parser.finish()
    findings = parser.findings + semantic_findings(parser)
    result = {
        "path": path.relative_to(root).as_posix(),
        "special": special,
        "status": "error"
        if any(item.severity == "error" for item in findings)
        else "warning"
        if findings
        else "ok",
        "findings": [asdict(item) for item in findings],
        "element_count": len(parser.elements),
        "node_count": sum(
            _has_class(element, "sd-node") for element in parser.elements
        ),
    }
    return result


def fragment_paths(root: Path) -> tuple[list[Path], list[str]]:
    paths: list[Path] = []
    notes: list[str] = []
    static_dir = root / STATIC_DIR
    if static_dir.is_dir():
        paths.extend(
            sorted(path for path in static_dir.rglob("*.html") if path.is_file())
        )
    else:
        notes.append(f"static fragment directory is absent: {STATIC_DIR.as_posix()}")
    for relative in SPECIAL_PATHS:
        path = root / relative
        if path.is_file():
            paths.append(path)
        else:
            notes.append(f"special include is absent: {relative.as_posix()}")
    return list(dict.fromkeys(paths)), notes


def _relative_path(root: Path, value: str) -> str | None:
    candidate = value.strip().replace("\\", "/")
    if not candidate:
        return None
    candidate = candidate.removeprefix("./")
    try:
        path = Path(candidate)
        if path.is_absolute():
            return path.relative_to(root).as_posix()
    except ValueError:
        return candidate.lstrip("/")
    return candidate


def inventory_entries(data: Any) -> list[dict[str, str]]:
    if isinstance(data, list):
        raw_entries = data
    elif isinstance(data, dict):
        raw_entries = []
        for key in ("mappings", "fragments", "entries", "items", "diagrams"):
            value = data.get(key)
            if isinstance(value, list):
                raw_entries.extend(value)
        if not raw_entries and isinstance(data.get("batch_ownership"), list):
            # The repository inventory records spec-backed sources by batch.
            # Derive the agreed include path so coverage can run directly
            # against inventory-full.json without a second mapping file.
            for batch in data["batch_ownership"]:
                if not isinstance(batch, dict):
                    continue
                for source in batch.get("sources", []):
                    if not isinstance(source, str) or not source:
                        continue
                    source_base = source.removesuffix(".spec.json")
                    include_base = source_base.removeprefix("assets/img/")
                    raw_entries.append(
                        {
                            "fragment": f"_includes/diagrams/static/{include_base}.html",
                            "source": f"{source_base}.spec.json",
                        }
                    )
    else:
        return []
    entries: list[dict[str, str]] = []
    for item in raw_entries:
        if not isinstance(item, dict):
            continue
        fragment = next(
            (
                item.get(key)
                for key in ("fragment", "include", "html", "output")
                if item.get(key)
            ),
            None,
        )
        source = next(
            (
                item.get(key)
                for key in ("source", "spec", "original", "asset")
                if item.get(key)
            ),
            None,
        )
        if isinstance(item.get("path"), str):
            path_value = item["path"]
            if path_value.endswith(".html") and not fragment:
                fragment = path_value
            elif path_value.endswith(".spec.json") and not source:
                source = path_value
        if fragment or source:
            if isinstance(fragment, str) and fragment.startswith("diagrams/"):
                fragment = f"_includes/{fragment}"
            entries.append(
                {"fragment": str(fragment or ""), "source": str(source or "")}
            )
    return entries


def coverage_findings(
    root: Path, paths: list[Path], inventory_path: Path | None
) -> tuple[list[Finding], dict[str, Any]]:
    if inventory_path is None:
        return [], {"provided": False, "entries": 0}
    try:
        data = json.loads(inventory_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [Finding("error", "inventory-parse", f"cannot read inventory: {exc}")], {
            "provided": True,
            "entries": 0,
        }

    entries = inventory_entries(data)
    findings: list[Finding] = []
    scanned_all = {path.relative_to(root).as_posix() for path in paths}
    scanned = {
        path.relative_to(root).as_posix()
        for path in paths
        if path.relative_to(root) not in SPECIAL_PATHS
    }
    listed_fragments: set[str] = set()
    for entry in entries:
        fragment = (
            _relative_path(root, entry["fragment"]) if entry["fragment"] else None
        )
        source = _relative_path(root, entry["source"]) if entry["source"] else None
        if fragment:
            listed_fragments.add(fragment)
            alias = SPECIAL_SOURCE_ALIASES.get(fragment)
            if fragment not in scanned_all and alias not in scanned_all:
                findings.append(
                    Finding(
                        "warning",
                        "inventory-missing-fragment",
                        f"inventory fragment is not scanned: {fragment}",
                    )
                )
        if source and not (root / source).is_file():
            findings.append(
                Finding(
                    "warning",
                    "inventory-missing-source",
                    f"inventory source is absent: {source}",
                )
            )
    for fragment in sorted(scanned - listed_fragments):
        findings.append(
            Finding(
                "warning",
                "fragment-not-in-inventory",
                f"fragment is absent from inventory: {fragment}",
            )
        )
    return findings, {
        "provided": True,
        "entries": len(entries),
        "listed_fragments": len(listed_fragments),
    }


def build_report(
    root: Path, paths: list[Path], notes: list[str], inventory: Path | None
) -> dict[str, Any]:
    fragments = [
        parse_fragment(root, path, path.relative_to(root) in SPECIAL_PATHS)
        for path in paths
    ]
    coverage, coverage_meta = coverage_findings(root, paths, inventory)
    errors = sum(
        len([finding for finding in item["findings"] if finding["severity"] == "error"])
        for item in fragments
    )
    warnings = sum(
        len(
            [
                finding
                for finding in item["findings"]
                if finding["severity"] == "warning"
            ]
        )
        for item in fragments
    )
    errors += sum(finding.severity == "error" for finding in coverage)
    warnings += sum(finding.severity == "warning" for finding in coverage)
    return {
        "root": str(root),
        "fragments": fragments,
        "notes": notes,
        "coverage": {**coverage_meta, "findings": [asdict(item) for item in coverage]},
        "summary": {"files": len(fragments), "errors": errors, "warnings": warnings},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "root_positional",
        nargs="?",
        type=Path,
        help="repository root (default: current directory)",
    )
    parser.add_argument("--root", dest="root_option", type=Path, help="repository root")
    parser.add_argument(
        "--inventory", type=Path, help="optional JSON source-to-fragment inventory"
    )
    parser.add_argument("--report", type=Path, help="write a JSON report to this path")
    args = parser.parse_args(argv)

    root = (args.root_option or args.root_positional or Path.cwd()).resolve()
    if not root.is_dir():
        print(f"repository root is not a directory: {root}", file=sys.stderr)
        return 2
    paths, notes = fragment_paths(root)
    report = build_report(root, paths, notes, args.inventory)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    summary = report["summary"]
    print(
        f"checked {summary['files']} static diagram fragment(s): {summary['errors']} error(s), {summary['warnings']} warning(s)"
    )
    for note in report["notes"]:
        print(f"  NOTE {note}")
    for fragment in report["fragments"]:
        for finding in fragment["findings"]:
            location = f":{finding['line']}" if finding.get("line") else ""
            print(
                f"  {finding['severity'].upper()} {fragment['path']}{location} {finding['code']}: {finding['message']}"
            )
    for finding in report["coverage"]["findings"]:
        print(
            f"  {finding['severity'].upper()} inventory {finding['code']}: {finding['message']}"
        )
    return 1 if summary["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
