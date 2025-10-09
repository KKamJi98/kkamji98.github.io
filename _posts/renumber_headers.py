"""
Markdown 헤더에 번호 접두어를 부여/정규화합니다.

사용법(Usage):

- 스크립트 직접 실행(현재 디렉터리 재귀 처리, H2부터 번호 시작):
  $ python3 renumber_headers.py

- 모듈로 사용(디렉터리/시작 레벨 지정):
  >>> from renumber_headers import process_files
  >>> process_files('_posts', min_header_level=2)  # 변경된 파일 경로 리스트 반환

- 문자열 기반 처리(단일 콘텐츠 가공):
  >>> from renumber_headers import renumber_headers
  >>> new_text = renumber_headers(original_text, min_header_level=2)

동작 요약:
- 코드 펜스(``` 또는 ~~~) 내부는 변경하지 않습니다.
- 파일 내 최소 해시 수를 감지하여 기준 레벨을 정하지만, `min_header_level`로 강제 지정할 수 있습니다.
- 기준 레벨보다 상위 헤더는 번호를 제거(있다면)하고, 하위부터는 1. / 1.1 / 1.2.1 형태로 번호를 부여합니다.
- 제목이 "관련 글"(공백 제거 후 비교)인 섹션은 번호에서 제외합니다.
"""

import os
import re
from typing import Optional

# 헤더/번호 정규식
HEADER_RE = re.compile(r"^(#{1,6})\s+(.*)$")
STRIP_NUM_RE = re.compile(r"^(?:\d+(?:\.\d+)*\.?)\s+")

# 넘버링 제외 제목(공백 제거 후 비교)
EXCLUDE_NORMALIZED = {"관련글"}


def _normalize_title(s: str) -> str:
    return re.sub(r"\s+", "", s).lower()


def renumber_headers(content: str, min_header_level: Optional[int] = None) -> str:
    lines = content.splitlines()
    fence_re = re.compile(r"^(```|~~~)")

    # 1. 최소 해시 수 산출
    in_code = False
    header_hash_counts = []
    for ln in lines:
        if fence_re.match(ln):
            in_code = not in_code
            continue
        if in_code:
            continue
        m = HEADER_RE.match(ln)
        if m:
            header_hash_counts.append(len(m.group(1)))

    if not header_hash_counts:
        return content if content.endswith("\n") else content + "\n"

    detected_min = min(header_hash_counts)
    base_hashes = max((min_header_level or detected_min), 1)

    # 2. 재번호화
    counters = [0] * 8  # 인덱스 1..6 사용
    out = []
    in_code = False

    for ln in lines:
        if fence_re.match(ln):
            in_code = not in_code
            out.append(ln)
            continue

        if in_code:
            out.append(ln)
            continue

        m = HEADER_RE.match(ln)
        if not m:
            out.append(ln)
            continue

        hashes, title = m.group(1), m.group(2)
        hash_count = len(hashes)

        # 상위 레벨은 번호 제외, 기존 번호만 제거
        if hash_count < base_hashes:
            clean_title = STRIP_NUM_RE.sub("", title).strip()
            out.append(f"{hashes} {clean_title}")
            continue

        level = hash_count - base_hashes + 1
        clean_title = STRIP_NUM_RE.sub("", title).strip()
        normalized = _normalize_title(clean_title)

        # 3. 제외 제목은 절대 넘버링하지 않음
        if normalized in EXCLUDE_NORMALIZED:
            out.append(f"{hashes} {clean_title}")
            continue

        # 4. 부모 카운터 보정으로 0.1 방지
        for i in range(1, level):
            if counters[i] == 0:
                counters[i] = 1

        counters[level] += 1

        # 더 깊은 레벨 리셋
        for i in range(level + 1, len(counters)):
            counters[i] = 0

        # 5. 접두 번호 구성
        parts = [str(counters[i]) for i in range(1, level + 1)]
        prefix = ".".join(parts)
        if level == 1:
            prefix += "."

        out.append(f"{hashes} {prefix} {clean_title}")

    return "\n".join(out) + "\n"


def process_files(
    directory: str, min_header_level: Optional[int] = None, print_errors: bool = True
):
    """업데이트된 파일 경로만 반환"""
    updated_paths = []
    for root, _, files in os.walk(directory):
        for file in files:
            if not file.endswith(".md"):
                continue
            path = os.path.join(root, file)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    original = f.read()
                updated = renumber_headers(original, min_header_level=min_header_level)
                if updated != original:
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(updated)
                    updated_paths.append(path)
            except Exception as e:
                if print_errors:
                    print(f"Error: {path}: {e}")
    return updated_paths


if __name__ == "__main__":
    # H2부터 번호 시작, 변경된 md 파일 경로만 출력
    for p in process_files(".", min_header_level=2):
        print(p)
