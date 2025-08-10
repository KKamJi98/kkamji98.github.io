import os
import re
from typing import Optional

# 헤더/번호 정규식
HEADER_RE = re.compile(r'^(#{1,6})\s+(.*)$')
STRIP_NUM_RE = re.compile(r'^(?:\d+(?:\.\d+)*\.?)\s+')

# 넘버링 제외 제목(공백 제거 후 비교)
EXCLUDE_NORMALIZED = {"관련글"}

def _normalize_title(s: str) -> str:
    # 공백, 탭 등 제거 후 소문자
    return re.sub(r'\s+', '', s).lower()

def renumber_headers(content: str, min_header_level: Optional[int] = None) -> str:
    lines = content.splitlines()
    fence_re = re.compile(r'^(```|~~~)')

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
        return content

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
            clean_title = STRIP_NUM_RE.sub('', title).strip()
            out.append(f'{hashes} {clean_title}')
            continue

        level = hash_count - base_hashes + 1
        clean_title = STRIP_NUM_RE.sub('', title).strip()
        normalized = _normalize_title(clean_title)

        # 3. 제외 제목은 절대 넘버링하지 않음
        if normalized in EXCLUDE_NORMALIZED:
            out.append(f'{hashes} {clean_title}')
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
        prefix = '.'.join(parts)
        if level == 1:
            prefix += '.'

        out.append(f'{hashes} {prefix} {clean_title}')

    return '\n'.join(out)


def process_files(directory: str, min_header_level: Optional[int] = None):
    for root, _, files in os.walk(directory):
        for file in files:
            if not file.endswith('.md'):
                continue
            path = os.path.join(root, file)
            print(f'Processing: {path}')
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    original = f.read()
                updated = renumber_headers(original, min_header_level=min_header_level)
                if updated != original:
                    with open(path, 'w', encoding='utf-8') as f:
                        f.write(updated)
                    print('  -> Updated.')
                else:
                    print('  -> No changes needed.')
            except Exception as e:
                print(f'  -> Error processing file: {e}')


if __name__ == '__main__':
    # H2부터 번호 시작
    process_files('.', min_header_level=2)
    print('\nDone.')
