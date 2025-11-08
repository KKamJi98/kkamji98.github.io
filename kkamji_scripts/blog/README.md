# 블로그 포스트 포매팅 스크립트

`kkamji_scripts/blog` 디렉터리는 `_posts` 폴더에 있는 마크다운 글을 자동으로 정리하기 위한 파이썬 도구를 제공합니다. 들여쓰기, 구분선, 헤더 번호 등 블로그 운영 시 반복되는 규칙을 한 번에 적용할 수 있습니다.

## 권장 실행 흐름

가장 간단한 방법은 `run_md_tools.sh` 스크립트를 사용하는 것입니다. 이 스크립트가 필요한 파이썬 스크립트를 올바른 순서로 실행해 줍니다.

- **사전 준비**: Python 3.9 이상이 설치되어 있어야 합니다.
- **실행 위치**: 저장소 루트(`/home/kkamji/Code/kkamji98.github.io`)에서 실행합니다.

```bash
# 기본 _posts 디렉터리에 일괄 적용
./kkamji_scripts/blog/run_md_tools.sh

# 다른 디렉터리에 적용
./kkamji_scripts/blog/run_md_tools.sh --root path/to/your/posts
```

> ⚠️ 실행 전 `_posts` 폴더를 백업하는 것을 권장합니다. 스크립트는 파일을 제자리에서 수정합니다.

```bash
# 타임스탬프 백업 예시
cp -a _posts _posts_backup_$(date +%Y%m%d%H%M%S)
```

---

## 개별 스크립트 설명

`run_md_tools.sh`는 아래 파이썬 스크립트를 순차 실행합니다. 필요하다면 개별 스크립트를 직접 호출해도 됩니다.

### 1. `fix_md_h2_rules.py`

- **역할**: 모든 H2(`##`) 헤더 위에 수평선(`---`)을 맞춰 가독성을 높입니다.
- **특징**
  - 코드 블록(백틱 3개)과 YAML 프런트매터는 자동으로 건너뜁니다.
  - 중복 수평선을 제거합니다.
  - 수평선과 헤더 사이의 공백을 1줄로 정규화합니다.
- **사용 예**

```bash
# 기본 _posts 디렉터리 실행
python3 kkamji_scripts/blog/fix_md_h2_rules.py

# 특정 파일을 드라이런으로 실행
python3 kkamji_scripts/blog/fix_md_h2_rules.py --file _posts/path/to/post.md --dry-run
```

### 2. `renumber_headers.py`

- **역할**: 헤더에 붙는 번호(`1.`, `1.1.`, `1.2.1.` 등)를 자동으로 부여하거나 정정합니다.
- **특징**
  - 기본값은 H2(`##`)부터 번호를 매기며 필요에 따라 조정할 수 있습니다.
  - 코드 블록을 건너뜁니다.
  - 기존 번호를 제거한 뒤 새 번호를 부여해 일관성을 보장합니다.
  - `관련 글`과 같은 특정 섹션은 번호에서 제외합니다.
- **사용 예**

```bash
# 기본 _posts 디렉터리 실행
python3 kkamji_scripts/blog/renumber_headers.py

# H3(###)부터 번호 매기기
python3 kkamji_scripts/blog/renumber_headers.py --min-level 3
```
