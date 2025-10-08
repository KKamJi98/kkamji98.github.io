# blog 스크립트 사용 가이드

## 공통 사전 준비

- Python 3.9 이상이 설치되어 있어야 합니다.
- 현재 작업 디렉터리는 저장소 루트(`kkamji_scripts/`)라고 가정합니다.
- 변경 전에 `_posts/` 디렉터리 백업을 권장합니다. 자동 포맷팅 스크립트이므로 롤백이 어려울 수 있습니다.

```bash
# 예시: 백업 디렉터리 생성
cp -a ../_posts ../_posts_backup_$(date +%Y%m%d%H%M%S)
```

## add_headers.py

- 목적: Markdown 파일에서 `##` 레벨 헤더 앞에 구분선을 삽입해 가독성을 높입니다.
- 동작: `_posts/` 트리 내 모든 `.md` 파일을 순회하며 `\n## ` 패턴 앞에 `---` 라인을 추가합니다.
- 실행 예:

```bash
python blog/add_headers.py
```

- 주의 사항:
  - `_posts/` 상대 경로는 현재 작업 디렉터리를 기준으로 합니다. 다른 경로를 사용하려면 스크립트 내 `posts_directory` 상수를 수정해야 합니다.
  - 이미 `---`가 있는 경우에도 다시 삽입할 수 있으므로 Git diff를 확인한 뒤 커밋하세요.

## insert_blank_lines.py

- 목적: `---` 구분선과 `##` 헤더 사이에 한 줄 공백을 강제하여 Markdown 렌더링을 안정화합니다.
- 동작: `_posts/` 트리 내 `.md` 파일에서 `---`와 `##` 사이에 빈 줄이 없으면 추가합니다.
- 실행 예:

```bash
python blog/insert_blank_lines.py
```

- 주의 사항:
  - `add_headers.py` 실행 후 후속 단계로 사용하면 헤더 블록 구조가 정리됩니다.
  - 추가 공백 외에는 파일을 변경하지 않습니다. 그러나 다중 실행 시에도 안전하므로 필요할 때마다 반복 실행 가능합니다.

## 권장 실행 순서

1. `python blog/add_headers.py`
2. `python blog/insert_blank_lines.py`
3. Git diff를 확인하고 결과를 검토합니다.
