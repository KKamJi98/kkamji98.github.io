#!/usr/bin/env python3
"""Advisory content-depth harness for kkamji.net blog posts.

This tool complements (does NOT replace) the mechanical audit in
``audit_blog_quality.py``. Its purpose is editorial planning support for
ordinary Korean technical explainers: aim for a thoughtful 20-30 minute read
without padding, add diagrams when they clarify, explain first-use jargon,
keep a smooth narrative, and cite reliable sources.

Design guarantees
------------------
* Dependency-free and deterministic (stdlib only).
* Reading-time and semantic quality are ADVISORY signals, never release gates.
  ``python3 audit_content_depth.py`` returns 0 even when advisory signals fire.
* The ONLY failures surfaced by ``--fail-on mechanical`` are the deterministic
  structural checks newly introduced here:
    1. frontmatter ``content_kind`` has an invalid value,
    2. the standard footer is duplicated or uses a marker other than
       ``.prompt-info`` (when a footer exists),
    3. an inline Markdown image is missing mandatory ``alt`` text.
* Existing AGENTS.md rules are preserved: the final Reference section, the fixed
  footer, and the forbidden characters (``\\u00b7`` and ``\\u2192``) are never
  emitted by this tool.

Reading-time estimate formula (transparent, documented)
-------------------------------------------------------
After removing frontmatter, HTML comments, fenced code blocks, tables, and
images, prose is measured as::

    est_minutes = korean_chars / KOREAN_CHARS_PER_MIN
                + latin_words  / LATIN_WORDS_PER_MIN

with KOREAN_CHARS_PER_MIN = 500 and LATIN_WORDS_PER_MIN = 200. Every reported
minute value is explicitly labeled an estimate. The 20-30 minute band is
editorial planning guidance, not a pass/fail rule.
"""

from __future__ import annotations

import argparse
import csv
import fnmatch
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from statistics import mean, median

ROOT = Path(__file__).resolve().parents[2]
POSTS_SUBDIR = "_posts"
REPORT_SUBDIR = Path(".hermes") / "reports"
REPORT_STEM = "blog-content-depth"

# --- Reading-time model (documented, tunable) -------------------------------
KOREAN_CHARS_PER_MIN = 500  # technical Korean prose, chars/min
LATIN_WORDS_PER_MIN = 200  # technical English prose, words/min
TARGET_MIN_MINUTES = 20
TARGET_MAX_MINUTES = 30

# --- Advisory signal thresholds (all editorial, never gates) ----------------
ENRICH_MAX_MINUTES = 4.0  # "very low prose" ceiling for ENRICH (estimate, minutes)
CONDENSE_MINUTES = 35.0  # prose estimate above this suggests condense/split
CONDENSE_H2_GROUPS = 9  # many independent H2 groups suggests split
SUBSTANTIVE_MINUTES = 5.0  # below this a post is not "substantive-looking"
TERM_GAP_THRESHOLD = 8  # distinct unexplained acronyms before TERM_GAPS fires

VALID_CONTENT_KINDS = {"cheatsheet", "lab", "explainer", "announcement"}
# Genres this tool assigns; "exempt" is derived from content_quality_exempt.
DEPTH_ANALYZED_GENRE = "explainer"

FOOTER_SNIPPET = "Written with [KKamJi](https://www.linkedin.com/in/taejikim/)"
FOOTER_MARKER = "prompt-info"

# Keywords driving advisory signals. Kept ASCII-safe and lowercase for matching.
BROAD_SCOPE_KEYWORDS = [
    "구축", "설계", "가이드", "정리", "완벽", "이해", "아키텍처", "소개",
    "심층", "전체", "완전", "총정리", "overview", "guide", "introduction",
    "architecture", "deep dive", "designing", "building",
]
VISUAL_KEYWORDS = [
    "아키텍처", "architecture", "flow", "흐름", "구조", "topology", "토폴로지",
    "파이프라인", "pipeline", "sequence", "시퀀스", "diagram", "다이어그램",
    "데이터 흐름", "component", "컴포넌트", "레이어", "계층", "workflow",
]
CONCLUSION_KEYWORDS = [
    "결론", "정리", "마무리", "conclusion", "요약", "summary", "wrap",
]
GENERIC_TLDR_PHRASES = [
    "이 글에서는 아래 내용을 다룹니다",
    "이번 글에서는 아래 내용을 다룹니다",
    "아래 내용을 다룹니다",
    "함께 알아보겠습니다",
    "차근차근 알아보겠습니다",
    "하나씩 알아보겠습니다",
]
# Ubiquitous acronyms that need no first-use explanation.
ACRONYM_ALLOWLIST = {
    "TL", "DR", "TLDR", "OK", "ID", "OS", "IP", "PC", "CPU", "GPU", "RAM",
    "SSD", "HDD", "URL", "URI", "HTTP", "HTTPS", "HTML", "CSS", "JS", "JSON",
    "YAML", "XML", "SQL", "API", "SDK", "CLI", "GUI", "UI", "UX", "CI", "CD",
    "AWS", "GCP", "VM", "DNS", "TCP", "UDP", "SSH", "TLS", "SSL", "PDF", "CSV",
    "AI", "ML", "LLM", "RAG", "IT", "DB", "GB", "MB", "KB", "TB", "MS", "FAQ",
}

# --- Regexes ----------------------------------------------------------------
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")
MERMAID_FENCE_RE = re.compile(r"^\s*(?:`{3,}|~{3,})\s*mermaid\b", re.M)
H2_RE = re.compile(r"^##\s+", re.M)
H3_RE = re.compile(r"^###\s+", re.M)
H2_LINE_RE = re.compile(r"^##\s+(.*)$", re.M)
REFERENCE_HEADING_RE = re.compile(
    r"^#{1,3}\s+(?:\d+[.)]?\s*)?(?:Reference|References|참고|참고 자료)\s*$",
    re.I | re.M,
)
MD_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)[^)]*\)")
MD_LINK_TEXT_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")
INLINE_CODE_RE = re.compile(r"`[^`]*`")
URL_RE = re.compile(r"https?://[^\s)>\]]+")
HANGUL_RE = re.compile(r"[가-힣]")
LATIN_WORD_RE = re.compile(r"[A-Za-z]+(?:['-][A-Za-z]+)*")
MARKER_RE = re.compile(r"^\{:\s*\.([A-Za-z0-9-]+)\s*\}$")
TABLE_SEP_RE = re.compile(r"^\|?[\s:|-]*-[\s:|-]*\|[\s:|-]*$")
ACRONYM_RE = re.compile(r"\b[A-Z][A-Z0-9]{1,7}\b")


@dataclass
class ContentAudit:
    """Per-post advisory + mechanical signal record."""

    path: str = ""
    title: str = ""
    genre: str = ""
    confidence: str = ""
    prose_chars: int = 0  # korean chars + latin chars (prose only)
    korean_chars: int = 0
    latin_words: int = 0
    est_minutes_estimate: float = 0.0
    headings: int = 0
    h2: int = 0
    h3: int = 0
    code_lines: int = 0
    inline_visuals: int = 0
    mermaid: int = 0
    has_reference: bool = False
    has_tldr: bool = False
    footer_count: int = 0
    footer_marker: str = ""
    signals: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    mechanical: list[str] = field(default_factory=list)


# --- Parsing helpers --------------------------------------------------------
def split_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Conservatively parse Jekyll YAML frontmatter into flat string values."""
    if not text.startswith("---") or text.count("---") < 2:
        return {}, text
    parts = text.split("---", 2)
    raw_fm = parts[1]
    body = parts[2]
    data: dict[str, str] = {}
    current_key = None
    for line in raw_fm.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line.startswith((" ", "\t")) and ":" in line:
            key, value = line.split(":", 1)
            current_key = key.strip()
            data[current_key] = value.strip()
        elif current_key:
            data[current_key] += "\n" + line
    return data, body


def strip_code_fences(body: str) -> tuple[str, int]:
    """Remove fenced code blocks; return (prose_text, code_line_count).

    Handles both backtick and tilde fences and requires the closing fence to
    match the opening fence character with an equal-or-greater run length.
    """
    prose: list[str] = []
    code_lines = 0
    fence_char: str | None = None
    fence_len = 0
    for line in body.splitlines():
        match = FENCE_RE.match(line)
        if fence_char is None:
            if match:
                fence_char = match.group(1)[0]
                fence_len = len(match.group(1))
                code_lines += 1
                continue
            prose.append(line)
        else:
            code_lines += 1
            if match and match.group(1)[0] == fence_char and len(match.group(1)) >= fence_len:
                fence_char = None
    return "\n".join(prose), code_lines


def extract_prose(prose_body: str) -> str:
    """Reduce a code-stripped body to plain prose for reading-time counting."""
    kept: list[str] = []
    for line in prose_body.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("|"):  # table row
            continue
        if TABLE_SEP_RE.match(stripped):  # table separator
            continue
        kept.append(line)
    text = "\n".join(kept)
    text = MD_IMAGE_RE.sub(" ", text)  # drop images
    text = MD_LINK_TEXT_RE.sub(r"\1", text)  # keep link text, drop URLs
    text = INLINE_CODE_RE.sub(" ", text)  # drop inline code spans
    text = URL_RE.sub(" ", text)  # drop bare URLs
    return text


def analyze_footer(body: str) -> tuple[int, str]:
    """Return (footer_snippet_count, marker_of_first_footer_block)."""
    lines = body.splitlines()
    footer_indices = [i for i, line in enumerate(lines) if FOOTER_SNIPPET in line]
    marker = ""
    if footer_indices:
        for line in lines[footer_indices[0] + 1:]:
            match = MARKER_RE.match(line.strip())
            if match:
                marker = match.group(1)
                break
    return len(footer_indices), marker


def parse_listish(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


# --- Genre classification ---------------------------------------------------
def classify_genre(
    rel_path: str, fm: dict[str, str], tags: str, code_lines: int, prose_lines: int
) -> tuple[str, str, str | None]:
    """Return (genre, confidence, mechanical_error_or_None)."""
    exempt_raw = fm.get("content_quality_exempt", "").strip().strip('"').lower()
    if exempt_raw == "true":
        return "exempt", "high", None

    mech: str | None = None
    content_kind = fm.get("content_kind", "").strip().strip('"').lower()
    if content_kind:
        if content_kind in VALID_CONTENT_KINDS:
            return content_kind, "high", None
        mech = f"invalid content_kind: {content_kind}"

    posix = rel_path.replace("\\", "/")
    if "/cheat-sheet/" in f"/{posix}" or "cheat-sheet" in tags.lower():
        return "cheatsheet", "high", mech

    content_lines = code_lines + prose_lines
    if code_lines >= 60 and content_lines and code_lines >= 0.4 * content_lines:
        return "lab", "medium", mech
    return "explainer", "medium", mech


# --- Advisory signal computation --------------------------------------------
def _first_use_unexplained_acronyms(text: str) -> list[str]:
    """Distinct acronyms with no parenthetical expansion anywhere in the text."""
    found: list[str] = []
    seen: set[str] = set()
    for token in ACRONYM_RE.findall(text):
        if token in ACRONYM_ALLOWLIST or token in seen:
            continue
        seen.add(token)
        explained = re.search(
            rf"(?:{re.escape(token)}\s*\([^)]+\)|\([^)]*{re.escape(token)}[^)]*\))",
            text,
        )
        if not explained:
            found.append(token)
    return found


def compute_signals(audit: ContentAudit, prose_text: str, body: str) -> None:
    """Populate advisory signals + reason strings for explainer posts only."""
    if audit.genre != DEPTH_ANALYZED_GENRE:
        return

    title_l = audit.title.lower()
    haystack = f"{audit.title}\n{prose_text}".lower()
    est = audit.est_minutes_estimate
    substantive = est >= SUBSTANTIVE_MINUTES or audit.has_reference or audit.inline_visuals

    # ENRICH: the title promises a broad scope but the prose is genuinely thin.
    # Broad scope is matched on the title only (a broad promise), not on body
    # prose, so common words in the body do not trigger false positives.
    broad_hits = [kw for kw in BROAD_SCOPE_KEYWORDS if kw in title_l]
    if broad_hits and est < ENRICH_MAX_MINUTES:
        audit.signals.append("ENRICH")
        audit.reasons.append(
            f"ENRICH: title promises broad scope ({broad_hits[0]}) but prose estimate "
            f"only {est:.1f} min (estimate); add depth or concrete examples"
        )

    # CONDENSE_OR_SPLIT: too much prose OR many independent H2 groups.
    condense_reasons: list[str] = []
    if est > CONDENSE_MINUTES:
        condense_reasons.append(
            f"prose estimate {est:.1f} min (estimate) exceeds the thoughtful upper band"
        )
    if audit.h2 >= CONDENSE_H2_GROUPS and est > TARGET_MAX_MINUTES:
        condense_reasons.append(
            f"{audit.h2} independent H2 groups; consider splitting into a series"
        )
    if condense_reasons:
        audit.signals.append("CONDENSE_OR_SPLIT")
        audit.reasons.append("CONDENSE_OR_SPLIT: " + "; ".join(condense_reasons))

    # VISUALIZE: structure/flow language but no inline diagram or illustration.
    visual_hits = [kw for kw in VISUAL_KEYWORDS if kw in haystack]
    if visual_hits and audit.inline_visuals == 0 and audit.mermaid == 0:
        audit.signals.append("VISUALIZE")
        audit.reasons.append(
            f"VISUALIZE: architecture/flow language ({visual_hits[0]}) with no inline "
            "diagram or illustration; a mermaid diagram or image may clarify"
        )

    # CITE: substantive content with no Reference section.
    if substantive and not audit.has_reference:
        audit.signals.append("CITE")
        audit.reasons.append(
            "CITE: substantive-looking content with no Reference section; "
            "add reliable sources to the final Reference list"
        )

    # TERM_GAPS: many unexplained first-use acronyms.
    gaps = _first_use_unexplained_acronyms(prose_text)
    if len(gaps) >= TERM_GAP_THRESHOLD:
        preview = ", ".join(gaps[:8])
        audit.signals.append("TERM_GAPS")
        audit.reasons.append(
            f"TERM_GAPS: {len(gaps)} acronyms lack a first-use explanation "
            f"(e.g. {preview}); expand on first mention"
        )

    # FLOW: missing intro / section structure / conclusion.
    if substantive:
        lead = body.split("\n## ", 1)[0]
        lead_prose = extract_prose(strip_code_fences(HTML_COMMENT_RE.sub("", lead))[0])
        has_intro = bool(HANGUL_RE.search(lead_prose) or LATIN_WORD_RE.search(lead_prose))
        has_structure = audit.h2 >= 2
        h2_titles = " ".join(H2_LINE_RE.findall(body)).lower()
        has_conclusion = any(kw in h2_titles for kw in CONCLUSION_KEYWORDS)
        missing: list[str] = []
        if not has_intro:
            missing.append("intro")
        if not has_structure:
            missing.append("section structure")
        if not has_conclusion and est >= 10:
            missing.append("conclusion")
        if missing and (not has_intro or not has_structure or "conclusion" in missing):
            audit.signals.append("FLOW")
            audit.reasons.append("FLOW: missing " + ", ".join(missing))

    # DE_BOILERPLATE: known generic TL;DR / filler phrase.
    boiler = [p for p in GENERIC_TLDR_PHRASES if p in prose_text]
    if boiler:
        audit.signals.append("DE_BOILERPLATE")
        audit.reasons.append(
            f"DE_BOILERPLATE: generic filler phrase detected ({boiler[0]}); "
            "replace with a specific takeaway"
        )


# --- Mechanical checks (the only --fail-on mechanical failures) -------------
def compute_mechanical(
    audit: ContentAudit, fm_mech: str | None, scan_body: str
) -> None:
    if fm_mech:
        audit.mechanical.append(fm_mech)

    if audit.footer_count >= 2:
        audit.mechanical.append(f"duplicate standard footer ({audit.footer_count})")
    if audit.footer_count >= 1 and audit.footer_marker != FOOTER_MARKER:
        shown = audit.footer_marker or "none"
        audit.mechanical.append(
            f"footer marker must be .{FOOTER_MARKER} (found .{shown})"
        )

    for match in MD_IMAGE_RE.finditer(scan_body):
        if not match.group(1).strip():
            audit.mechanical.append(f"image missing alt text: {match.group(2)}")


# --- Core analysis ----------------------------------------------------------
def analyze(rel_path: str, text: str) -> ContentAudit:
    """Pure, deterministic analysis of one post given its relative path + text."""
    fm, body = split_frontmatter(text)
    no_comments = HTML_COMMENT_RE.sub("", body)
    prose_body, code_lines = strip_code_fences(no_comments)
    prose_text = extract_prose(prose_body)

    korean_chars = len(HANGUL_RE.findall(prose_text))
    latin_words = len(LATIN_WORD_RE.findall(prose_text))
    latin_chars = sum(len(w) for w in LATIN_WORD_RE.findall(prose_text))
    est_minutes = korean_chars / KOREAN_CHARS_PER_MIN + latin_words / LATIN_WORDS_PER_MIN

    tags = parse_listish(fm.get("tags", ""))
    prose_lines = len([ln for ln in prose_body.splitlines() if ln.strip()])
    genre, confidence, fm_mech = classify_genre(rel_path, fm, tags, code_lines, prose_lines)

    footer_count, footer_marker = analyze_footer(no_comments)

    audit = ContentAudit(
        path=rel_path,
        title=fm.get("title", "").strip().strip('"'),
        genre=genre,
        confidence=confidence if genre != "exempt" else "n/a",
        prose_chars=korean_chars + latin_chars,
        korean_chars=korean_chars,
        latin_words=latin_words,
        est_minutes_estimate=round(est_minutes, 1),
        headings=len(H2_RE.findall(no_comments)) + len(H3_RE.findall(no_comments)),
        h2=len(H2_RE.findall(no_comments)),
        h3=len(H3_RE.findall(no_comments)),
        code_lines=code_lines,
        inline_visuals=len(MD_IMAGE_RE.findall(prose_body)),
        mermaid=len(MERMAID_FENCE_RE.findall(no_comments)),
        has_reference=bool(REFERENCE_HEADING_RE.search(prose_body)),
        has_tldr=("TL;DR" in prose_body or "요약" in prose_text[:1500]),
        footer_count=footer_count,
        footer_marker=footer_marker,
    )

    compute_signals(audit, prose_text, no_comments)
    compute_mechanical(audit, fm_mech, prose_body)
    return audit


# --- Collection + filtering -------------------------------------------------
def collect_posts(posts_dir: Path) -> list[Path]:
    return sorted(posts_dir.glob("**/*.md"))


def matches_only(rel_path: str, only: str) -> bool:
    posix = rel_path.replace("\\", "/")
    candidates = [posix, posix.split("/", 1)[-1] if "/" in posix else posix, Path(posix).name]
    if posix.startswith(f"{POSTS_SUBDIR}/"):
        candidates.append(posix[len(POSTS_SUBDIR) + 1:])
    return any(fnmatch.fnmatch(c, only) for c in candidates)


def audit_all(root: Path, only: str | None) -> list[ContentAudit]:
    posts_dir = root / POSTS_SUBDIR
    audits: list[ContentAudit] = []
    for path in collect_posts(posts_dir):
        rel = path.relative_to(root).as_posix()
        if only and not matches_only(rel, only):
            continue
        audits.append(analyze(rel, path.read_text(encoding="utf-8")))
    return sorted(audits, key=lambda a: a.path)


# --- Report writers ---------------------------------------------------------
CSV_COLUMNS = [
    "path", "title", "genre", "confidence", "prose_chars", "korean_chars",
    "latin_words", "est_minutes_estimate", "headings", "code_lines",
    "inline_visuals", "mermaid", "has_reference", "has_tldr", "signals",
    "mechanical", "reasons",
]


def write_csv(audits: list[ContentAudit], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(CSV_COLUMNS)
        for a in audits:
            writer.writerow([
                a.path, a.title, a.genre, a.confidence, a.prose_chars,
                a.korean_chars, a.latin_words, a.est_minutes_estimate, a.headings,
                a.code_lines, a.inline_visuals, a.mermaid, a.has_reference,
                a.has_tldr, "; ".join(a.signals), "; ".join(a.mechanical),
                " | ".join(a.reasons),
            ])


def write_json(audits: list[ContentAudit], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "blog-content-depth/1",
        "advisory": True,
        "reading_time_formula": (
            "est_minutes = korean_chars/{kc} + latin_words/{lw} (estimate only)"
        ).format(kc=KOREAN_CHARS_PER_MIN, lw=LATIN_WORDS_PER_MIN),
        "target_band_minutes": [TARGET_MIN_MINUTES, TARGET_MAX_MINUTES],
        "posts": [asdict(a) for a in audits],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


# Group priority for the human-readable triage section.
SIGNAL_ORDER = [
    ("CITE", "Add reliable sources (Reference section)"),
    ("VISUALIZE", "Add a diagram or illustration where structure/flow is described"),
    ("ENRICH", "Broad topic but thin prose - add depth or examples"),
    ("CONDENSE_OR_SPLIT", "Too much prose or too many groups - condense or split"),
    ("FLOW", "Improve intro / section structure / conclusion"),
    ("TERM_GAPS", "Explain first-use jargon and acronyms"),
    ("DE_BOILERPLATE", "Replace generic filler with a specific takeaway"),
]


def write_markdown(audits: list[ContentAudit], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    explainers = [a for a in audits if a.genre == DEPTH_ANALYZED_GENRE]
    ests = [a.est_minutes_estimate for a in explainers]

    genre_counts: dict[str, int] = {}
    for a in audits:
        genre_counts[a.genre] = genre_counts.get(a.genre, 0) + 1

    def bucket_label(m: float) -> str:
        if m < 10:
            return "< 10 min"
        if m < TARGET_MIN_MINUTES:
            return f"10 - {TARGET_MIN_MINUTES} min"
        if m <= TARGET_MAX_MINUTES:
            return f"{TARGET_MIN_MINUTES} - {TARGET_MAX_MINUTES} min (target band)"
        return f"> {TARGET_MAX_MINUTES} min"

    dist: dict[str, int] = {}
    for m in ests:
        dist[bucket_label(m)] = dist.get(bucket_label(m), 0) + 1

    mech_posts = [a for a in audits if a.mechanical]

    lines: list[str] = []
    lines.append("# Blog Content-Depth Harness (Advisory)")
    lines.append("")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    lines.append("## How to read this report")
    lines.append("")
    lines.append(
        "- Reading-time and semantic signals here are ADVISORY editorial planning "
        "aids. They never block a release."
    )
    lines.append(
        "- The 20-30 minute band is a planning target for ordinary explainers, not "
        "a pass/fail rule. A shorter focused post or a longer well-structured series "
        "can both be correct."
    )
    lines.append(
        f"- Reading time is an ESTIMATE: est_minutes = korean_chars/{KOREAN_CHARS_PER_MIN}"
        f" + latin_words/{LATIN_WORDS_PER_MIN}, after removing frontmatter, code, "
        "tables, and images."
    )
    lines.append(
        "- Only the Mechanical Violations section is objective and gate-worthy "
        "(run with --fail-on mechanical). Everything else is a suggestion."
    )
    lines.append("")
    lines.append("### Genre exemptions from depth signals")
    lines.append("")
    lines.append(
        "- Depth signals run for `explainer` posts only. `cheatsheet`, `lab`, "
        "`announcement`, and `content_quality_exempt: true` posts are excluded to "
        "avoid false positives."
    )
    lines.append(
        "- Manual classification is supported via frontmatter "
        "`content_kind: cheatsheet|lab|explainer|announcement` and "
        "`content_quality_exempt: true`."
    )
    lines.append("")

    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("| --- | ---: |")
    lines.append(f"| Posts analyzed | {len(audits)} |")
    lines.append(f"| Explainers (depth-analyzed) | {len(explainers)} |")
    lines.append(f"| Mean explainer estimate (min) | {mean(ests):.1f} (estimate) |" if ests else "| Mean explainer estimate (min) | n/a |")
    lines.append(f"| Median explainer estimate (min) | {median(ests):.1f} (estimate) |" if ests else "| Median explainer estimate (min) | n/a |")
    lines.append(f"| Posts with advisory signals | {sum(1 for a in audits if a.signals)} |")
    lines.append(f"| Posts with mechanical violations | {len(mech_posts)} |")
    lines.append("")

    lines.append("### Genre distribution")
    lines.append("")
    lines.append("| Genre | Posts |")
    lines.append("| --- | ---: |")
    for genre in sorted(genre_counts):
        lines.append(f"| {genre} | {genre_counts[genre]} |")
    lines.append("")

    lines.append("### Explainer reading-time distribution (estimate)")
    lines.append("")
    if dist:
        lines.append("| Band | Posts |")
        lines.append("| --- | ---: |")
        for label in ["< 10 min", f"10 - {TARGET_MIN_MINUTES} min",
                      f"{TARGET_MIN_MINUTES} - {TARGET_MAX_MINUTES} min (target band)",
                      f"> {TARGET_MAX_MINUTES} min"]:
            if label in dist:
                lines.append(f"| {label} | {dist[label]} |")
    else:
        lines.append("None.")
    lines.append("")

    lines.append("## Mechanical Violations (objective, gate-worthy)")
    lines.append("")
    lines.append(
        "These are the only findings that `--fail-on mechanical` treats as failures."
    )
    lines.append("")
    if mech_posts:
        lines.append("| Post | Violations |")
        lines.append("| --- | --- |")
        for a in mech_posts:
            lines.append(f"| `{a.path}` | {'; '.join(a.mechanical)} |")
    else:
        lines.append("None.")
    lines.append("")

    lines.append("## Prioritized Advisory Triage")
    lines.append("")
    lines.append(
        "Grouped by signal, highest editorial priority first. All items are "
        "suggestions, not gates."
    )
    lines.append("")
    for code, blurb in SIGNAL_ORDER:
        group = [a for a in explainers if code in a.signals]
        lines.append(f"### {code} - {blurb} ({len(group)})")
        lines.append("")
        if not group:
            lines.append("None.")
            lines.append("")
            continue
        lines.append("| Post | Estimate | Reason |")
        lines.append("| --- | ---: | --- |")
        for a in sorted(group, key=lambda x: (-x.est_minutes_estimate, x.path)):
            reason = next((r for r in a.reasons if r.startswith(code)), "")
            reason = reason.split(":", 1)[1].strip() if ":" in reason else reason
            lines.append(f"| `{a.path}` | {a.est_minutes_estimate} min (est) | {reason} |")
        lines.append("")

    lines.append("## Editorial guidance")
    lines.append("")
    lines.append(
        "1. Fix mechanical violations first (footer, alt text, content_kind)."
    )
    lines.append(
        "2. Treat the 20-30 minute band as a planning target; do not pad to hit it."
    )
    lines.append(
        "3. Add diagrams only where they clarify structure or flow (VISUALIZE)."
    )
    lines.append(
        "4. Explain first-use jargon (TERM_GAPS) and cite reliable sources (CITE)."
    )
    lines.append(
        "5. Human fact-checking of claims and sources remains a manual gate; this "
        "tool never verifies correctness of content."
    )
    lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


# --- CLI --------------------------------------------------------------------
def run(root: Path, only: str | None, fail_on: str) -> int:
    audits = audit_all(root, only)
    report_dir = root / REPORT_SUBDIR
    md_path = report_dir / f"{REPORT_STEM}.md"
    csv_path = report_dir / f"{REPORT_STEM}.csv"
    json_path = report_dir / f"{REPORT_STEM}.json"

    write_csv(audits, csv_path)
    write_json(audits, json_path)
    write_markdown(audits, md_path)

    explainers = sum(1 for a in audits if a.genre == DEPTH_ANALYZED_GENRE)
    with_signals = sum(1 for a in audits if a.signals)
    mech_posts = [a for a in audits if a.mechanical]
    mech_count = sum(len(a.mechanical) for a in mech_posts)

    print(f"Analyzed {len(audits)} posts ({explainers} explainers)")
    print(f"Advisory: {with_signals} posts carry at least one triage signal (advisory only)")
    print(f"Mechanical: {mech_count} violations across {len(mech_posts)} posts")
    try:
        print(f"Reports: {md_path.relative_to(root)}, {csv_path.relative_to(root)}, {json_path.relative_to(root)}")
    except ValueError:
        print(f"Reports: {md_path}, {csv_path}, {json_path}")

    if fail_on == "mechanical" and mech_count:
        print("FAIL: mechanical violations present (--fail-on mechanical)")
        for a in mech_posts:
            for issue in a.mechanical:
                print(f"- {a.path}: {issue}")
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=str(ROOT), help="repository root (default: repo root)")
    parser.add_argument("--only", default=None, help="glob to limit posts (matched against _posts-relative path)")
    parser.add_argument(
        "--fail-on",
        choices=["none", "mechanical"],
        default="none",
        help="'mechanical' exits nonzero on deterministic structural violations; advisory findings never fail",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return run(Path(args.root).resolve(), args.only, args.fail_on)


if __name__ == "__main__":
    raise SystemExit(main())
