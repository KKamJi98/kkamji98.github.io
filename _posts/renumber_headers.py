import os
import re

HEADER_RE = re.compile(r'^(#{1,6})\s+(.*)$')  # 헤더 탐지
STRIP_NUM_RE = re.compile(r'^(?:\d+(?:\.\d+)*\.?)\s+')  # 선행 번호 제거 (1. / 1.2 / 1.2.3. )

def renumber_headers(content: str, min_header_level: int | None = None) -> str:
    lines = content.splitlines()
    in_code = False
    fence_re = re.compile(r'^(```|~~~)')  # 코드펜스 토글

    # 1) 문서 내 번호를 매길 헤더들의 최소 해시 수 결정
    header_hash_counts = []
    for ln in lines:
        if fence_re.match(ln):
            in_code = not in_code
            continue
        if in_code:
            continue
        m = HEADER_RE.match(ln)
        if not m:
            continue
        hashes = m.group(1)
        header_hash_counts.append(len(hashes))

    if not header_hash_counts:
        return content

    detected_min = min(header_hash_counts)
    # 사용자가 강제하고 싶다면 인자로 지정. 지정이 없으면 문서 최소 해시 사용
    base_hashes = max(min_header_level or detected_min, 1)

    # 2) 카운터 준비
    # 최대 6단계까지 지원. 인덱스 1부터 사용
    counters = [0] * 8

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

        # base_hashes 보다 작으면 번호 부여하지 않음 (예: H1은 제외)
        if hash_count < base_hashes:
            out.append(ln)
            continue

        # 3) 상대 레벨 계산: 가장 작은 해시 개수를 레벨 1로
        level = hash_count - base_hashes + 1
        if level < 1:
            out.append(ln)
            continue

        # 4) 카운터 갱신
        counters[level] += 1
        # 더 깊은 레벨은 리셋
        for i in range(level + 1, len(counters)):
            counters[i] = 0

        # 5) 기존 번호 제거
        clean_title = STRIP_NUM_RE.sub('', title).strip()

        # 6) 접두 번호 구성
        parts = [str(counters[i]) for i in range(1, level + 1)]
        prefix = '.'.join(parts)
        # 최상위 레벨만 끝에 점 추가 → "1."
        if level == 1:
            prefix += '.'

        out.append(f'{hashes} {prefix} {clean_title}')

    return '\n'.join(out)


def process_files(directory: str, min_header_level: int | None = None):
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
    # H1은 제목으로 두고 H2부터 번호를 매기고 싶다면 2로 고정
    process_files('.', min_header_level=2)
    # process_files('.')
    print('\nDone.')
