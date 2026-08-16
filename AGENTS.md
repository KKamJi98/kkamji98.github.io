# AGENTS.md

## Rules

- 본문의 등장하는 외부 링크는 블로그 최 하단 Reference 헤더에 Unordered List로 정리. Format: `[Kubernetes Docs - Controller](Link)`
- Reference의 링크에서 링크드인, 실습에 사용된 개인 url은 절대 추가로 포함시키지 않음
- 응답과 편집물에서 '·', '→' 문자는 절대 사용하지 않음 (금지)

## Public Writing

- 계획 카드의 독자, 도착 역량, 범위, 비범위, 연재 의존성, 검증 기준은 작성과 리뷰를 위한 내부 산출물이다. 독자가 필요한 기술적 전제와 한계만 본문 맥락에 자연스럽게 녹인다.
- `이 글의 범위`, `연재에서의 위치`, `학습 점검`, `다음 글`, `읽기 순서`, `도착 역량`처럼 글 제작 과정을 드러내는 heading, checklist, roadmap 표는 공개 글에 기본으로 넣지 않는다. 실제 오해를 막는 범위나 버전 경계는 구체적인 기술 문장으로 쓴다.
- 도입은 독자가 실제로 만나는 증상, 질문, 코드, 관측값 중 하나에서 시작한다. generic TL;DR, "이번 글에서는", "의도적으로 제외", "무엇이 아닌가"의 반복, 대칭적인 세 항목 bullet을 자동으로 넣지 않는다.
- 각 heading은 내용 자체를 말한다. heading 아래에서 heading을 반복하는 한 문장, 글의 구성 공지, 다음 글 예고는 삭제한다. 기존 글에서 문맥상 필요한 내부 링크만 해당 기술 설명 곁에 둔다.
- Cilium 학습 시리즈는 사용자가 직접 쓴 고유 기록이므로 AI 문체 후보나 자동 humanizer 수정 대상으로 분류하지 않는다. 주인님이 개별 수정을 요청한 경우에만 다룬다.
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





## Footer

- 아래 내용의 Footer를 절대 수정하지 말 것 (중요)
  ```md
  > **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
  > **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
  {: .prompt-info}
  ```