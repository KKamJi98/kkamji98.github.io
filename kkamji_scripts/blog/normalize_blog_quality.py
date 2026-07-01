#!/usr/bin/env python3
"""Apply safe mechanical quality fixes to kkamji.net blog posts.

This script intentionally performs only deterministic fixes:
- Replace repository-forbidden typography characters.
- Add the standard footer when missing.
- Add a Reference section for posts that have external links but no Reference.

It does not rewrite prose or generate TL;DR content. Those remain review tasks.
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
POSTS_DIR = ROOT / "_posts"

FOOTER = """> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
"""

HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
REFERENCE_HEADING_RE = re.compile(r"^##\s+(?:\d+[.)]?\s*)?(?:Reference|References|참고|참고 자료)\s*$", re.I | re.M)
EXTERNAL_LINK_RE = re.compile(r"https?://[^\s)<>\]\}\"']+")
FOOTER_RE = re.compile(r"> \*\*궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요\.\*\*\s*\n> \*\*Written with \[KKamJi\]\(https://www\.linkedin\.com/in/taejikim/\)\*\*\s*\n\{: \.prompt-info\}", re.M)
H2_RE = re.compile(r"^##\s+", re.M)

EXCLUDED_REFERENCE_HOSTS = {
    "localhost",
    "127.0.0.1",
    "kkamji.net",
    "www.kkamji.net",
    "linkedin.com",
    "www.linkedin.com",
    "private-user-images.githubusercontent.com",
}
EXCLUDED_REFERENCE_HOST_PARTS = ["github.com/kkamji98/", "github.com/KKamJi98/"]


@dataclass
class Change:
    path: str
    action: str
    detail: str


def strip_comments(text: str) -> str:
    return HTML_COMMENT_RE.sub("", text)


def split_frontmatter(text: str) -> tuple[str, str, str]:
    if text.startswith("---") and text.count("---") >= 2:
        first, fm, body = text.split("---", 2)
        return first + "---" + fm + "---", fm, body
    return "", "", text


def existing_reference_urls(body: str) -> set[str]:
    if not REFERENCE_HEADING_RE.search(body):
        return set()
    match = list(REFERENCE_HEADING_RE.finditer(body))[-1]
    section = body[match.end():]
    footer_match = FOOTER_RE.search(section)
    if footer_match:
        section = section[:footer_match.start()]
    return set(clean_url(url) for url in EXTERNAL_LINK_RE.findall(section))


def clean_url(url: str) -> str:
    return url.rstrip(".,;:")


def is_private_or_placeholder_url(url: str) -> bool:
    if any(token in url for token in ["${", "$", "{", "}", "@"]):
        return True
    try:
        parsed = urlparse(url)
    except ValueError:
        return True
    host = parsed.netloc.lower().split(":", 1)[0]
    if not host or host == "localhost":
        return True
    if "." not in host:
        return True
    if re.match(r"^\d+\.\d+\.\d+\.\d+$", host):
        parts = [int(part) for part in host.split(".")]
        return (
            parts[0] == 10
            or parts[0] == 127
            or (parts[0] == 172 and 16 <= parts[1] <= 31)
            or (parts[0] == 192 and parts[1] == 168)
        )
    return False


def should_reference(url: str) -> bool:
    cleaned = clean_url(url)
    if is_private_or_placeholder_url(cleaned):
        return False
    try:
        parsed = urlparse(cleaned)
    except ValueError:
        return False
    if parsed.scheme != "https":
        return False
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host_no_www = host[4:]
    else:
        host_no_www = host
    if host in EXCLUDED_REFERENCE_HOSTS or host_no_www in EXCLUDED_REFERENCE_HOSTS:
        return False
    lowered = cleaned.lower()
    return not any(part.lower() in lowered for part in EXCLUDED_REFERENCE_HOST_PARTS)


def source_label(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc.replace("www.", "") or "External Source"
    path = parsed.path.strip("/")
    if not path:
        return f"{host} - Home"
    parts = [p for p in path.split("/") if p]
    tail = parts[-1] if parts else path
    tail = re.sub(r"[-_]+", " ", tail)
    tail = re.sub(r"\.(html|md|php|aspx?)$", "", tail, flags=re.I).strip()
    if len(tail) > 60:
        tail = tail[:57].rstrip() + "..."
    return f"{host} - {tail or 'Reference'}"


def next_reference_number(body: str) -> int:
    nums = [int(m.group(1)) for m in re.finditer(r"^##\s+(\d+)\.\s+", body, re.M)]
    return max(nums, default=len(H2_RE.findall(body))) + 1


def remove_trailing_footer(body: str) -> tuple[str, bool]:
    match = FOOTER_RE.search(body)
    if not match:
        return body, False
    before = body[:match.start()].rstrip()
    after = body[match.end():].strip()
    if after:
        return body, True
    return before + "\n", True


def add_reference_section(body: str, urls: list[str]) -> str:
    if not urls:
        return body
    body_without_footer, had_footer = remove_trailing_footer(body)
    ref_no = next_reference_number(body_without_footer)
    ref_lines = [f"## {ref_no}. Reference", ""]
    for url in urls:
        ref_lines.append(f"- [{source_label(url)}]({url})")
    ref_lines.append("")
    new_body = body_without_footer.rstrip() + "\n\n" + "\n".join(ref_lines)
    if had_footer:
        new_body += "\n" + FOOTER
    return new_body


def ensure_footer(body: str) -> str:
    if FOOTER_RE.search(body):
        return body
    return body.rstrip() + "\n\n" + FOOTER


def normalize_text(text: str, path: Path, dry_run: bool) -> tuple[str, list[Change]]:
    changes: list[Change] = []
    original = text

    if "\u2192" in text:
        text = text.replace("\u2192", "->")
        changes.append(Change(path.as_posix(), "replace", "right arrow to ASCII arrow"))
    if "\u00b7" in text:
        text = text.replace("\u00b7", ",")
        changes.append(Change(path.as_posix(), "replace", "middle dot to comma"))

    prefix, _fm, body = split_frontmatter(text)
    scan_body = strip_comments(body)

    existing_refs = existing_reference_urls(scan_body)
    if not REFERENCE_HEADING_RE.search(scan_body):
        urls = []
        seen = set()
        for raw_url in EXTERNAL_LINK_RE.findall(scan_body):
            url = clean_url(raw_url)
            if not should_reference(url) or url in seen or url in existing_refs:
                continue
            seen.add(url)
            urls.append(url)
        if urls:
            body = add_reference_section(body, urls)
            text = prefix + body if prefix else body
            changes.append(Change(path.as_posix(), "add-reference", f"{len(urls)} URLs"))

    prefix, _fm, body = split_frontmatter(text)
    if not FOOTER_RE.search(body):
        body = ensure_footer(body)
        text = prefix + body if prefix else body
        changes.append(Change(path.as_posix(), "add-footer", "standard footer"))

    if dry_run:
        return original, changes
    return text, changes


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--root", default=str(POSTS_DIR))
    args = parser.parse_args()

    root = Path(args.root)
    all_changes: list[Change] = []
    for path in sorted(root.glob("**/*.md")):
        text = path.read_text(encoding="utf-8")
        new_text, changes = normalize_text(text, path.relative_to(ROOT), args.dry_run)
        if changes:
            all_changes.extend(changes)
            if not args.dry_run and new_text != text:
                path.write_text(new_text, encoding="utf-8")

    for change in all_changes:
        print(f"{change.action}: {change.path} ({change.detail})")
    print(f"changed_files={len(set(c.path for c in all_changes))} changes={len(all_changes)}")


if __name__ == "__main__":
    main()
