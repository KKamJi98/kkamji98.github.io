#!/usr/bin/env python3
"""Repo-local docs wiki lint. Standard library only.

Five checks. Three are static (frontmatter, index, link). Two need a git base
ref (freshness, coupling) and only run when --base is given.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import subprocess
import sys
from pathlib import Path

REQUIRED_KEYS = ("title", "updated", "type", "status")
TYPES = frozenset({"architecture", "decision", "rule", "runbook", "evidence"})
STATUSES = frozenset({"current", "superseded", "archived"})

FENCE = re.compile(r"^```")
MD_LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")
WIKILINK = re.compile(r"\[\[[^\]]+\]\]")


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Return (mapping, body). Flat `key: value` lines only, which is the contract."""
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end == -1:
        return {}, text
    block = text[4:end]
    rest = text[end + len("\n---"):]
    if rest.startswith("\n"):
        rest = rest[1:]
    mapping: dict[str, str] = {}
    for line in block.split("\n"):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, sep, value = line.partition(":")
        if sep:
            mapping[key.strip()] = value.strip()
    return mapping, rest


def _governed(rel: Path) -> bool:
    """docs/index.md is the catalog itself and docs/_meta/ holds tooling and config."""
    return rel != Path("docs/index.md") and "_meta" not in rel.parts


def _git_docs_files(root: Path) -> list[Path] | None:
    """Markdown under docs/ that git would let you commit, or None outside a repo.

    Tracked plus untracked-but-not-ignored. Walking the filesystem instead would govern
    gitignored working files (local research notes, superpowers specs). Those exist on
    the author's machine and not in a CI checkout, so the lint would pass in CI and fail
    locally, and a gate that disagrees with itself gets bypassed.
    """
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "--cached", "--others",
         "--exclude-standard", "--", "docs"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return None
    return sorted(
        Path(line) for line in result.stdout.split("\n")
        if line.endswith(".md") and _governed(Path(line))
    )


def docs_files(root: Path) -> list[Path]:
    """Markdown under docs/, excluding docs/index.md and docs/_meta/."""
    from_git = _git_docs_files(root)
    if from_git is not None:
        return from_git
    docs = root / "docs"
    if not docs.is_dir():
        return []
    return [
        path.relative_to(root)
        for path in sorted(docs.rglob("*.md"))
        if _governed(path.relative_to(root))
    ]


def check_frontmatter(root: Path) -> list[str]:
    problems = []
    for rel in docs_files(root):
        front, _ = parse_frontmatter((root / rel).read_text(encoding="utf-8"))
        missing = [k for k in REQUIRED_KEYS if not front.get(k)]
        if missing:
            problems.append(f"{rel}: frontmatter is missing {', '.join(missing)}")
            continue
        if front["type"] not in TYPES:
            problems.append(f"{rel}: type '{front['type']}' is not one of {sorted(TYPES)}")
        if front["status"] not in STATUSES:
            problems.append(f"{rel}: status '{front['status']}' is not one of {sorted(STATUSES)}")
    return problems


def _body_without_code(body: str) -> str:
    kept, fenced = [], False
    for line in body.split("\n"):
        if FENCE.match(line):
            fenced = not fenced
            continue
        if not fenced:
            kept.append(line)
    return "\n".join(kept)


def check_index(root: Path) -> list[str]:
    index = root / "docs" / "index.md"
    if not index.is_file():
        return ["docs/index.md is missing"]
    targets = set()
    for raw in MD_LINK.findall(index.read_text(encoding="utf-8")):
        target = raw.split("#", 1)[0].split(" ", 1)[0].strip()
        if not target:
            continue
        targets.add((root / "docs" / target).resolve())
    problems = []
    for rel in docs_files(root):
        if (root / rel).resolve() not in targets:
            problems.append(f"{rel}: not linked from docs/index.md")
    return problems


def check_links(root: Path) -> list[str]:
    problems = []
    for rel in docs_files(root):
        text = (root / rel).read_text(encoding="utf-8")
        _, body = parse_frontmatter(text)
        stripped = _body_without_code(body)
        if WIKILINK.search(stripped):
            problems.append(f"{rel}: contains a wikilink; repo docs use relative markdown links")
        for raw in MD_LINK.findall(stripped):
            target = raw.split(" ", 1)[0].strip()
            if not target or target.startswith(("#", "http://", "https://", "mailto:")):
                continue
            target = target.split("#", 1)[0]
            if not target:
                continue
            resolved = (root / rel).parent / target
            if not resolved.exists():
                problems.append(f"{rel}: link target does not exist: {target}")
    return problems


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True, text=True,
    )


def changed_files(root: Path, base: str) -> list[str]:
    result = _git(root, "diff", "--name-only", f"{base}...HEAD")
    if result.returncode != 0:
        raise SystemExit(f"git diff against '{base}' failed: {result.stderr.strip()}")
    return [line for line in result.stdout.split("\n") if line]


def file_at(root: Path, ref: str, rel: str) -> str | None:
    result = _git(root, "show", f"{ref}:{rel}")
    return result.stdout if result.returncode == 0 else None


def check_freshness(root: Path, base: str) -> list[str]:
    problems = []
    tracked = {str(rel) for rel in docs_files(root)}
    for rel in changed_files(root, base):
        if rel not in tracked:
            continue
        before = file_at(root, base, rel)
        if before is None:
            continue  # new document; nothing to keep fresh yet
        after = (root / rel).read_text(encoding="utf-8")
        front_before, body_before = parse_frontmatter(before)
        front_after, body_after = parse_frontmatter(after)
        if body_before == body_after:
            continue
        if front_before.get("updated") == front_after.get("updated"):
            problems.append(f"{rel}: body changed but 'updated' was not bumped")
    return problems


def coupling_skip_reason(root: Path, base: str) -> str | None:
    result = _git(root, "log", f"{base}..HEAD", "--format=%B")
    if result.returncode != 0:
        return None
    prefix = "docs-coupling-skip:"
    for line in result.stdout.split("\n"):
        if line.strip().startswith(prefix):
            reason = line.strip()[len(prefix):].strip()
            if reason:
                return reason
    return None


def check_coupling(root: Path, base: str) -> list[str]:
    mapping_path = root / "docs" / "_meta" / "coupling.json"
    if not mapping_path.is_file():
        return []
    if coupling_skip_reason(root, base):
        return []
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    changed = changed_files(root, base)
    changed_set = set(changed)
    problems = []
    for doc, patterns in sorted(mapping.items()):
        if doc.startswith("$") or not isinstance(patterns, list):
            continue
        if doc in changed_set:
            continue
        hits = [
            path for path in changed
            for pattern in patterns
            if fnmatch.fnmatch(path, pattern)
        ]
        if hits:
            joined = ", ".join(sorted(set(hits)))
            problems.append(
                f"{doc}: coupled source changed but the document did not: {joined}"
            )
    return problems


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Repo-local docs wiki lint")
    parser.add_argument("--root", default=".")
    parser.add_argument("--base", default=None, help="git base ref; enables freshness and coupling")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()

    problems = check_frontmatter(root) + check_index(root) + check_links(root)
    if args.base:
        problems += check_freshness(root, args.base) + check_coupling(root, args.base)

    for problem in problems:
        print(f"::error::{problem}")
    if problems:
        print(f"docs lint failed with {len(problems)} problem(s)")
        return 1
    print("docs lint passed")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
