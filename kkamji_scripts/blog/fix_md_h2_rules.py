#!/usr/bin/env python3
"""
Markdown의 모든 H2 헤더("## ") 바로 위에 수평선("---")을 보장합니다.

사용법(Usage):

- 단일 파일 처리:
  $ python3 kkamji_scripts/blog/fix_md_h2_rules.py --file _posts/2025/2025-08-19-my-post.md

- 디렉터리 재귀 처리(기본은 저장소의 `_posts`, 없으면 현재 디렉터리):
  $ python3 kkamji_scripts/blog/fix_md_h2_rules.py --root content/posts

- 변경 미리보기(파일 미작성):
  $ python3 kkamji_scripts/blog/fix_md_h2_rules.py --root . --dry-run

- 백업(.bak) 미생성:
  $ python3 kkamji_scripts/blog/fix_md_h2_rules.py --root . --no-backup

- 상세 로그 출력:
  $ python3 kkamji_scripts/blog/fix_md_h2_rules.py --root . --verbose

옵션:
- --file <path>: 단일 Markdown 파일만 처리
- --root <dir>: 루트 디렉터리부터 재귀 처리(기본: 저장소 `_posts` 또는 현재 디렉터리)
- --dry-run: 변경 사항만 출력하고 파일은 수정하지 않음
- --no-backup: 원본 .bak 백업 파일을 생성하지 않음
- --verbose: 삽입/수정 위치를 자세히 출력

세부 동작:
- 펜스 코드 블록(``` 또는 ~~~)은 건너뜁니다.
- YAML 프론트매터를 보존하며, 프론트매터 직후 첫 H2에도 HR을 보장합니다.
- 바로 위에 이미 HR이 있으면(빈 줄은 무시) 중복 삽입하지 않습니다.
- HR와 H2 사이에는 정확히 한 줄 공백, HR 위쪽 공백은 최대 한 줄로 정규화합니다.
- 기본적으로 .bak 백업 파일을 생성합니다(--no-backup 지정 시 미생성).
"""

import argparse
import os
import sys
from pathlib import Path

SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "node_modules",
    ".pnpm-store",
    ".idea",
    ".vscode",
    "dist",
    "build",
    "__pycache__",
}


def resolve_default_root() -> Path:
    script_path = Path(__file__).resolve()
    for parent in script_path.parents:
        candidate = parent / "_posts"
        if candidate.exists():
            return candidate
    return Path.cwd()


def is_h2(line: str) -> bool:
    # Treat lines that begin (possibly with up to 3 leading spaces) then '## '
    s = line.lstrip()
    leading = len(line) - len(s)
    return leading <= 3 and s.startswith("## ") and not s.startswith("###")


def process_file(path: Path, dry_run: bool, make_backup: bool, verbose: bool) -> bool:
    try:
        original_text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        print(f"Error reading {path}: {e}", file=sys.stderr)
        return False

    text = original_text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    out = []
    changed = False

    in_code = False
    code_fence = None
    in_front = False
    at_top = True
    just_closed_front = False

    # Front matter only if file starts with '---' on the very first non-empty line
    idx0 = 0
    while idx0 < len(lines) and lines[idx0].strip() == "":
        idx0 += 1
    if idx0 < len(lines) and lines[idx0].strip() == "---":
        in_front = True

    def prev_nonempty(buf):
        for j in range(len(buf) - 1, -1, -1):
            if buf[j].strip() != "":
                return j, buf[j]
        return None, None

    def squash_double_blank_before(buf):
        # Reduce consecutive blank lines at tail to at most one
        while len(buf) >= 2 and buf[-1].strip() == "" and buf[-2].strip() == "":
            buf.pop()

    i = 0
    while i < len(lines):
        raw = lines[i]
        stripped = raw.strip()

        # YAML front matter open/close only near file start region
        if not in_code and stripped == "---" and (in_front or at_top):
            out.append(raw)
            if in_front:
                in_front = False
                just_closed_front = True
                at_top = False
            else:
                in_front = True
            i += 1
            continue

        at_top = False

        # Fenced code blocks
        if not in_front and (stripped.startswith("```") or stripped.startswith("~~~")):
            fence = "```" if stripped.startswith("```") else "~~~"
            if not in_code:
                in_code = True
                code_fence = fence
            elif code_fence == fence:
                in_code = False
                code_fence = None
            out.append(raw)
            i += 1
            continue

        if not in_code and not in_front and is_h2(raw):
            # Look upward through out[] to find the nearest non-empty line
            idx, prev = prev_nonempty(out)
            already_has_hr = (
                prev is not None and prev.strip() == "---" and not just_closed_front
            )
            if not already_has_hr:
                squash_double_blank_before(out)
                # Ensure at most one blank line before HR
                if len(out) > 0 and out[-1].strip() != "" and not just_closed_front:
                    out.append("")
                # Insert HR and ensure exactly one blank after
                out.append("---")
                out.append("")
                changed = True
                if verbose:
                    print(f"Inserted HR above H2: {path} (around line {i+1})")
            else:
                trailing_segment = out[idx + 1 :] if idx is not None else []
                needs_normalize = trailing_segment != [""]  # 0개 또는 다수/공백문자 포함 시 true
                if needs_normalize:
                    while len(out) > (idx + 1) and out[-1].strip() == "":
                        out.pop()
                    out.append("")
                    changed = True
                    if verbose:
                        print(
                            f"Normalized spacing above H2: {path} (around line {i+1})"
                        )
            out.append(raw)
            just_closed_front = False
            i += 1
            continue

        if stripped != "":
            just_closed_front = False

        out.append(raw)
        i += 1

    new_text = "\n".join(out)
    file_changed = new_text != text

    if dry_run:
        if file_changed:
            print(f"[DRY-RUN] Would update: {path}")
        return file_changed

    if file_changed:
        if make_backup:
            try:
                Path(str(path) + ".bak").write_text(original_text, encoding="utf-8")
            except Exception as e:
                print(
                    f"Warning: failed to write backup for {path}: {e}", file=sys.stderr
                )
        try:
            path.write_text(new_text, encoding="utf-8")
        except Exception as e:
            print(f"Error writing {path}: {e}", file=sys.stderr)
            return False

    return file_changed


def gather_files(root: Path) -> list[Path]:
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")
        ]
        for fn in filenames:
            if fn.lower().endswith(".md"):
                files.append(Path(dirpath) / fn)
    return files


def main():
    ap = argparse.ArgumentParser(
        description="Insert --- above every H2 (## ) header in Markdown."
    )
    ap.add_argument(
        "--root",
        type=str,
        default=None,
        help="Root directory to scan (default: repository _posts or current directory)",
    )
    ap.add_argument("--file", type=str, help="Process only a single file")
    ap.add_argument(
        "--dry-run", action="store_true", help="Preview changes without writing files"
    )
    ap.add_argument(
        "--no-backup", action="store_true", help="Do not create .bak backups"
    )
    ap.add_argument("--verbose", action="store_true", help="Verbose output")
    args = ap.parse_args()

    files = []
    if args.file:
        p = Path(args.file).expanduser().resolve()
        if not p.exists():
            print(f"Error: file not found: {p}", file=sys.stderr)
            sys.exit(2)
        files = [p]
    else:
        if args.root:
            root = Path(args.root).expanduser().resolve()
            if not root.exists():
                print(f"Error: root path not found: {root}", file=sys.stderr)
                sys.exit(2)
        else:
            root = resolve_default_root()
        files = gather_files(root)

    total = 0
    changed_count = 0
    for f in files:
        total += 1
        if process_file(
            f,
            dry_run=args.dry_run,
            make_backup=(not args.no_backup),
            verbose=args.verbose,
        ):
            changed_count += 1

    mode = "DRY-RUN" if args.dry_run else "APPLY"
    print(f"[{mode}] Examined {total} files, changed {changed_count}.")


if __name__ == "__main__":
    main()
