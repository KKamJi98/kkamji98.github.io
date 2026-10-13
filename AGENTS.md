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
- 필자가 겪은 일을 다룬 글(장애, 취약점 발견, 마이그레이션, 실험 기록)은 `docs/first-person-experience-posts.md`의 체크리스트를 함께 적용한다. `audit_humanizer.py`는 화자 부재를 검출하지 못하므로 strict 통과를 생략 근거로 쓰지 않는다.
- 화자를 되돌리는 것과 서사로 각색하는 것은 다르다. `범인은`, `그 순간`, `드디어`, `결국 ~에 닿았습니다`, `헤맸습니다`, `숨은 원인`, `아무리 ~해 봐도` 같은 연출 표현은 쓰지 않고 관측값 그대로 쓴다. 금지선은 `docs/first-person-experience-posts.md`.
- 본문 강조는 `docs/emphasis-and-bold.md`를 따른다. 3,000자 이상 글은 판단이 걸린 문장에 볼드를 둔다. 확인은 `python3 kkamji_scripts/blog/check_emphasis.py --file <post>`.

## Diagrams

- 설명용 다이어그램은 기존 HTML figure의 의미 구조를 보존하고 inline SVG의 박스, 연결과 텍스트 좌표를 직접 작성한다. 원본은 `_includes/diagrams/static/` 및 Packer/AWS 인증의 개별 include이며, 제작 기준과 원본 매핑은 `docs/static-diagrams.md`를 따른다.
- 정렬, 정보 구성과 승인된 프로젝트 색도 시각 검토의 합격 조건이다. 같은 위계의 카드와 그룹, 제목 baseline, padding과 비교 대상의 크기를 대조한다. 큰 빈 영역은 본문에 근거가 있는 입력, 반환 값, 조건이나 예시로 설명력을 높인 뒤 다시 배치한다. 단순 확대나 장식용 내용으로 채우지 않는다. Jev의 네온 accent 선호는 Jev에만 적용한다. 상세 기준은 `docs/static-diagrams.md`와 `.agents/skills/diagram/SKILL.md`를 따른다.
- 모든 SVG는 `width="1920"`, `height="1080"`, `viewBox="0 0 1920 1080"`을 사용한다. native PNG와 게시용 WebP의 실제 픽셀 치수도 정확히 1920 x 1080, 16:9이어야 한다. 원본 좌표와 artwork를 보존하고 resize, resampling, crop이나 비율 왜곡으로 맞추지 않는다. SVG와 native PNG는 원본 증적으로 보관하고, WebP는 PNG와 전체 decoded RGBA 픽셀이 같은 lossless 파생본을 사용한다.
- 원본 캔버스 픽셀과 CSS 표시 크기를 구분한다. 데스크톱과 모바일 본문의 `.diagram-download > img.diagram-inline`만 글 폭에 맞춰 비례 축소한다. `width:100%`, `min-width:0`, `max-width:100%`, `height:auto`, `min-height:0`, `max-height:none`, `aspect-ratio:16 / 9`를 사용한다. 노드 재배치, container query와 breakpoint별 artwork 변형은 금지한다. 본문과 문서에 그림으로 인한 가로 overflow나 강제 스크롤을 만들지 않는다. 별도 full-size viewer의 고정 크기와 확대는 사용자가 링크와 배율을 직접 선택할 때만 적용한다.
- 커버는 본문 도식과 별도 자산이다. 확장자나 FHD 치수만으로 커버를 `.diagram-inline` 대상으로 분류하거나 본문 도식으로 교체하지 않는다. source SVG와 export fixture의 1920 x 1080 CSS 경계 및 의미 소스의 clipping은 inline 표시 규칙과 분리해서 보존한다.
- 공통 스타일은 `assets/css/jekyll-theme-chirpy.scss`의 `.sd` 규칙이다. 흰 배경의 라이트 테마를 유지한다. 버튼, 클릭, hover 의존 정보, 애니메이션, script를 그림에 추가하지 않는다. 제목 22px, 라벨 16px, 보조 텍스트 14px 이상을 유지한다.
- 그림 안 이미지에는 `data-static-diagram="true"`를 붙여 테마의 확대 링크 생성을 건너뛴다. 실제 관계와 조건을 보존하고 상세 설명은 본문에 둔다.
- 검증: `uv run python kkamji_scripts/blog/validate_static_diagrams.py --root .` 실행 후 SVG 원본, native PNG와 모든 WebP의 실제 치수, decoded 픽셀 동일성, 노드, 라벨, 조건과 간선의 대응을 확인한다. production build의 360px/390px 및 데스크톱 article에서 이미지 로딩 완료 후 글 폭에 맞는 비례 표시와 이미지, article 및 document의 가로 overflow 부재를 검사한다. source/export fixture와 사용자가 선택한 full-size viewer는 별도로 검사한다. 폰트, 가독성, 겹침과 잘림은 실제 그림과 article 화면을 열어 검토한다. 정적 CSS 테스트를 브라우저 또는 픽셀 QA로 보고하지 않는다. 구조 검증, 내용 검증, native PNG 생성, WebP 변환, 실제 시각 검토와 게시 수를 별도로 기록한다.
- 브라우저 자동화는 전역 지침의 Aside 단일 경로를 따른다. 허용 Aside 경로가 없거나 캡처가 실패하면 정확한 미검증 범위를 남긴다. 기존 Playwright/Chromium exporter나 다른 브라우저 설치를 폴백으로 실행하지 않는다.
- 기존 `assets/img/**/*.spec.json`, `.drawio`, `.svg`, native `.png`와 이전 `.webp`는 원본 증적과 rollback용으로 보존한다. 기존 Draw.io를 수정하는 경우에만 `rebuild_diagrams.sh`를 사용한다.

## Git Add, Commit, Push Convention

- 빌드 테스트
- 변경된 post에 대해 오타, 맞춤법 그리고 띄어쓰기 문제가 없는지 확인 후 교정
- `kkamji_scripts/blog/run_md_tools.sh` 실행

### pre-commit 게이트

- 훅은 `.githooks/pre-commit`으로 추적한다. **클론마다 한 번 `git config core.hooksPath .githooks`를 실행**해야 동작한다. `.git/hooks/`에 사본을 두지 않는다.
- 이 저장소는 CI에 품질 게이트를 두지 않는다. 되돌아가면 곤란한 규칙은 이 훅이 막는다.
  - `_posts/*.md` staged: `run_md_tools.sh`, staged 글에 대한 `audit_humanizer --strict`, `check_post_dates`, `check_series_order`, `check_high_impact_tldr`, 그리고 frontmatter/커버/내부 링크/금지 문자/footer 기계 검사.
  - 정적 다이어그램, CSS, export 도구, PNG, WebP 또는 diagram include 줄 변경 staged: `kkamji_scripts/blog/static_png/release_manifest.py --if-staged`로 source fingerprint, native PNG와 게시 WebP의 해시, index 일치를 확인한다. 생성과 검증 절차는 `docs/static-diagrams.md`의 `Connector acceptance and recurrence gates`를 따른다. 일반 본문만 수정하면 이 게이트는 적용하지 않는다.
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
