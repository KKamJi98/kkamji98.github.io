# AGENTS.md

## Rules

- 본문의 등장하는 외부 링크는 블로그 최 하단 Reference 헤더에 Unordered List로 정리. Format: `[Kubernetes Docs - Controller](Link)`
- Reference의 링크에서 링크드인, 실습에 사용된 개인 url은 절대 추가로 포함시키지 않음
- 응답과 편집물에서 '·', '→' 문자는 절대 사용하지 않음 (금지)

## Knowledge Layout

- **현재 구조, 결정, 규칙**: `docs/`. 카탈로그는 `docs/index.md`다. 코드나 테마를 바꾸기 전에 읽는다.
- **작업 일지, 백로그**: vault `workspaces/`. 날짜별 기록이다.
- **교차 repo 지식**: vault `wiki/`, `shapes/`, `runbooks/`.

이 파일은 라우팅만 담는다. 규칙 본문은 `docs/`에 쓴다.

- frontmatter 필수 키 네 개: `title`, `updated`, `type`, `status`.
- `type`: `architecture` | `decision` | `rule` | `runbook` | `evidence`
- `status`: `current` | `superseded` | `archived`
- 새 문서는 `docs/index.md`에 등록한다. 등록하지 않으면 CI가 막는다.
- wikilink를 쓰지 않는다. 상대경로 markdown 링크만 쓴다.
- `docs/_meta/coupling.json`에 매핑된 파일을 바꾸면 같은 PR에서 해당 문서도 바꾼다.
- `docs/_meta/docs_lint.py`는 손으로 고치지 않는다. 정본은 `kkamji-settings/agents/docs-wiki/docs_lint.py`다.
- 검증: `python3 docs/_meta/docs_lint.py --root .`

## Public Writing

- 계획 카드의 독자, 도착 역량, 범위, 비범위, 연재 의존성, 검증 기준은 작성과 리뷰를 위한 내부 산출물이다. 독자가 필요한 기술적 전제와 한계만 본문 맥락에 자연스럽게 녹인다.
- `이 글의 범위`, `연재에서의 위치`, `학습 점검`, `다음 글`, `읽기 순서`, `도착 역량`처럼 글 제작 과정을 드러내는 heading, checklist, roadmap 표는 공개 글에 기본으로 넣지 않는다. 실제 오해를 막는 범위나 버전 경계는 구체적인 기술 문장으로 쓴다.
- 도입은 독자가 실제로 만나는 증상, 질문, 코드, 관측값 중 하나에서 시작한다. generic TL;DR, "이번 글에서는", "의도적으로 제외", "무엇이 아닌가"의 반복, 대칭적인 세 항목 bullet을 자동으로 넣지 않는다.
- 각 heading은 내용 자체를 말한다. heading 아래에서 heading을 반복하는 한 문장, 글의 구성 공지, 다음 글 예고는 삭제한다. 기존 글에서 문맥상 필요한 내부 링크만 해당 기술 설명 곁에 둔다.
- 본문 문단은 `~합니다`, `~입니다` 존댓말로 쓴다. 개념을 설명하거나 무언가를 풀어서 서술하는 자리에 `~한다`, `~이다`를 쓰지 않는다.
- bullet, 번호 목록, 표 셀, TL;DR과 prompt callout, 그림 캡션은 `~한다`, `~하는 역할`처럼 짧은 평서체로 둔다. 여기서 존댓말로 늘리면 목록이 문단처럼 읽힌다.
- Cilium 학습 시리즈는 사용자가 직접 쓴 고유 기록이므로 AI 문체 후보나 자동 humanizer 수정 대상으로 분류하지 않는다. 주인님이 개별 수정을 요청한 경우에만 다룬다. 다만 스크립트가 주입한 정형 문구는 이 예외에 해당하지 않는다.
- 발행 전 `python3 kkamji_scripts/blog/audit_humanizer.py --strict --file <post>` humanizer review를 수행한다. 메타 서술, 과도한 부정 병렬, 기계적인 목록, 교과 과정 같은 문체를 찾고, 정확성 근거와 실험 증거는 유지한 채 고친다.

## Diagrams

- `assets/img/**/*.spec.json`이 source of truth다. `.drawio`와 `.webp`는 빌드 산출물이므로 손으로 편집하지 않는다.
- 다이어그램을 추가하거나 고칠 때는 spec을 쓴 뒤 `kkamji_scripts/blog/rebuild_diagrams.sh assets/img/<dir>`를 실행한다. 컴파일, 정규화, export, 검증이 한 번에 돈다. 실행 전 `export DRAWIO_SKILL_DIR="$HOME/.claude/skills/drawio-generate-diagram"` (Hermes는 `$HOME/.hermes/...`, Codex는 `$HOME/.codex/...`).
- spec 없이 손으로 쓴 `.drawio`는 컴파일러와 validator를 둘 다 건너뛴다. 모든 `.drawio`의 첫 줄은 `host="kkamji-blog"`여야 한다. `host="Electron"`이면 손으로 쓴 파일이므로 spec으로 다시 만든다.
- 노드 배치는 `col`, `row` 그리드다. 연결선이 이상하게 돌면 waypoint를 넣지 말고 노드를 옮긴다. 레이아웃이 해결책이고 waypoint는 증상이다.
- edge를 쓰는 다이어그램에서 어떤 edge도 닿지 않는 fill 박스는 미완성으로 읽힌다. validator가 경고하면 연결하거나, 설명 대상 박스 안에 넣거나, fill을 빼서 캡션으로 만든다.
- export한 실제 이미지를 눈으로 보기 전에는 검증됐다고 보고하지 않는다.

## Git Add, Commit, Push Convention

- 빌드 테스트
- 변경된 post에 대해 오타, 맞춤법 그리고 띄어쓰기 문제가 없는지 확인 후 교정
- `kkamji_scripts/blog/run_md_tools.sh` 실행

### pre-commit 게이트

- 훅은 `.githooks/pre-commit`으로 추적한다. **클론마다 한 번 `git config core.hooksPath .githooks`를 실행**해야 동작한다. `.git/hooks/`에 사본을 두지 않는다.
- 이 저장소는 CI에 품질 게이트를 두지 않는다. 되돌아가면 곤란한 규칙은 이 훅이 막는다.
  - `_posts/*.md` staged: `run_md_tools.sh`, staged 글에 대한 `audit_humanizer --strict`, `check_post_dates`, `check_series_order`, `check_high_impact_tldr`, 그리고 frontmatter/커버/내부 링크/금지 문자/footer 기계 검사.
  - `assets/img/**/*.spec.json` staged: spec을 compile + normalize한 결과와 커밋된 `.drawio`를 비교해 `rebuild_diagrams.sh` 누락을 잡고, `audit_diagram_badges`로 배지 위치를 확인한다.
- 훅은 스크립트가 실제로 내용을 바꾼 staged 파일만 다시 stage한다. 커밋 대상이 아닌데 포매터가 건드린 글은 unstaged로 남기고 이름을 출력한다.
- `jekyll build`, `check_inline_scripts`, 외부 링크 검사는 훅에 넣지 않는다. 발행 절차인 `kkamji_scripts/blog/pre_publish_check.sh`가 담당한다.
- 게이트를 우회해야 하면 `git commit --no-verify`를 쓰고 그 이유를 남긴다.





## Footer

- 아래 내용의 Footer를 절대 수정하지 말 것 (중요)
  ```md
  > **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
  > **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
  {: .prompt-info}
  ```