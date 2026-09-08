---
title: Static diagram authoring and verification
updated: 2026-09-08
type: rule
status: current
---

# Static diagrams

블로그의 설명용 다이어그램은 정적 HTML을 정본으로 사용한다. 개별 그림은 `_includes/diagrams/static/`, 인증 지도와 Packer 그림은 `_includes/diagrams/`의 개별 include에 있다. 본문은 Liquid include로 그림을 삽입한다.

## 읽을 수 있는 구조

한 그림은 한 가지 관계나 차이를 설명한다. flow는 실제 전달 순서가 있을 때, comparison은 선택지의 차이를 볼 때, layer는 소속과 경계를 보여줄 때 사용한다. 속성 목록이나 서로 독립된 hook 사이에 실행 순서처럼 읽히는 화살표를 붙이지 않는다. 분기 조건과 실패 경로는 해당 위치에 명시한다.

제목은 22px 이상, 주요 라벨은 16px 이상, 보조 라벨과 표/코드는 14px 이상이다. 긴 설명은 본문에 둔다. 그림의 제목, 부제, 노드, 캡션에서 같은 문장을 반복하지 않는다. 전문 식별자는 원문을 유지하고 설명 문장은 간결한 한국어로 쓴다.

그림의 버튼, 링크, hover 의존 정보, 숨겨진 내용, 재생, script, 애니메이션을 사용하지 않는다. 좁은 화면에서는 내용을 줄여 숨기는 대신 grid와 flow를 재배치한다.

## 공통 클래스

`assets/css/jekyll-theme-chirpy.scss`의 `.sd` 규칙이 모든 그림의 스타일을 담당한다.

| 구조 | 클래스 |
| :--- | :--- |
| 그림과 제목 | `figure.sd`, `figcaption.sd-title` |
| 흐름 | `sd-flow`, `sd-node`, `sd-arrow`, `sd-edge-label` |
| 비교와 분기 | `sd-grid`, `sd-grid--three`, `sd-lane`, `sd-lane-title` |
| 계층과 경계 | `sd-stack`, `sd-band`, `sd-band-title` |
| 텍스트 | `sd-label`, `sd-detail`, `sd-note` |
| 의미 강조 | `sd-node--accent`, `sd-node--warning`, `sd-node--muted` |
| 비교 표 | `sd-table` |
| 공식 아이콘과 배지 | `sd-icon`, `sd-cert-card`, `sd-cert-badge`, `sd-cert-code` |

내부 제목은 `div` 또는 `strong`으로 만들어 본문 TOC의 heading과 구분한다. figure의 `aria-labelledby`는 고유한 title id를 참조한다. 조건을 담은 edge label은 보조 기술에서도 읽을 수 있어야 한다.

## 이미지와 원본 증적

공식 아이콘은 로컬 파일로 제공하고 출처와 해시를 기록한다. 그림의 모든 `img`에는 명시적 크기와 `data-static-diagram="true"`를 붙인다. 이 속성이 있으면 테마의 확대 링크와 shimmer wrapper 생성을 건너뛴다.

기존 spec, Draw.io, raster 파일은 증적과 rollback을 위해 보존한다. 새 static HTML을 이전 raster로 다시 생성하지 않는다. [Diagram catalog](diagram-catalog.json)는 각 include와 기존 원본, 사용 포스트를 연결한다. 커버, 로고, 사진, 콘솔 및 명령 캡처는 설명용 구조도와 구분해 관리한다.

## 검증

```bash
uv run python kkamji_scripts/blog/validate_static_diagrams.py --root . --inventory docs/diagram-catalog.json
JEKYLL_ENV=production bundle exec jekyll b -d /tmp/blog-static-site
uv run python kkamji_scripts/blog/check_inline_scripts.py /tmp/blog-static-site
uv run python docs/_meta/docs_lint.py --root .
```

빌드에는 저장소 lockfile에 맞는 Ruby/Bundler를 사용한다. 설치된 macOS 실행 환경의 경우 Ruby 3.4.7 경로를 PATH 앞에 넣어 Bundler 4.0.3을 사용할 수 있다.

검증은 source 정적성, 원본과의 의미 대조, production HTML, 실제 브라우저 렌더링을 나누어 확인한다. 실제 본문 폭과 360px 폭에서 글자 크기, 잘림, 가로 넘침, 배지 로드, 의미 없는 상호작용이 없는지 검사한다. source parser 통과만으로 시각 품질이 검증됐다고 보고하지 않는다.

## Rollback

catalog의 원본 경로를 사용해 해당 본문의 include를 이전 이미지 참조로 되돌릴 수 있다. 그림 일부를 되돌릴 때 공통 CSS와 refactor-content 예외는 다른 static 그림이 사용하는지 확인한 뒤 제거한다.

## Mobile layout and stylesheet cache

- Figure padding uses explicit viewport units, `clamp(1rem, 3.5vw, 2rem)`; only descendants use the figure container query. Removing the ineffective self-query preserves existing mobile and desktop spacing without adding a wrapper. Fixed `1rem` was rejected because it moved the multi-column breakpoint and introduced regressions at 720px figure width.
- Titles use `word-break: keep-all` with `overflow-wrap: anywhere` as the long-token fallback. Direct figure arrows receive `0.75rem` block margins; nested flow arrows keep their existing grid gap.
- Only Packer detail code preserves its short HCL clauses with `white-space: nowrap`. Do not extend this selector to arbitrary long code.
- Theme 7.6.0 `head.html` and `swconf.js` overrides append the same `site.time` build timestamp to the theme stylesheet URL after `relative_url`. Rebase both full-file overrides when upgrading the gem. No service-worker fetch, activation, purge, or cache-name behavior changes.
- Old cached HTML can still request old CSS until the existing service-worker update lifecycle supplies new HTML. Versioned CSS is not an instant eviction mechanism.
