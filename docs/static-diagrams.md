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

그림의 버튼, 링크, hover 의존 정보, 숨겨진 내용, 재생, script, 애니메이션을 사용하지 않는다. 원본 HTML의 grid와 flow는 625px 본문 폭에서 export되며, 매핑된 본문 화면은 그 PNG만 비율을 유지해 축소한다. 좁은 화면에서 재배치한 별도 그림을 보여주지 않는다.

## 단일 PNG 표시

`figure.sd`는 계속 의미 구조와 접근성 텍스트, export의 정본이다. 모든 매핑된 사용처에서 바로 뒤의 `diagrams/download.html` helper는 동일한 PNG URL을 빈 `alt`의 inline 이미지, 다운로드 링크, 원본 열기 링크에 쓴다. 이미지의 중복 설명을 막고 figure의 `aria-labelledby`와 노드 텍스트를 보조 기술에 남긴다. helper가 없는 미사용 figure는 원래 HTML로 표시한다. `figure.sd:has(+ .diagram-download > img.diagram-inline)`는 해당 figure만 화면에서 시각적으로 클립한다. `display:none`, `visibility:hidden`, `aria-hidden`을 사용하지 않는다. 이미지에는 `data-static-diagram="true"`를 붙여 확대/래퍼 생성을 피한다.

PNG는 각 그림의 내용 높이를 유지하며 Chromium에서 625px 원본 캔버스를 DPR 3.072로 직접 렌더해 가로 1920px로 만든다. 1920x1080 고정 비율에 맞추려고 텍스트를 축소하거나 이미지에 여백을 덧대지 않는다. PNG는 intrinsic 비율로 본문 폭까지 축소된다. 360px와 625px, light와 dark, 인쇄에서 화면상 도식 구성은 동일한 PNG 픽셀이다. 좁은 화면에서는 확대가 필요할 수 있으므로 원본 이미지 열기 링크를 유지한다. 이미지는 텍스트 선택이 불가능하지만 의미 정보는 figure에 남는다. export 브라우저는 스크린샷 전 클립만 복구하고 helper를 숨겨 figure HTML을 캡처한다. 이는 게시 HTML 변경이 아니라 일회용 브라우저 스타일 변경이다. 품질/connector gate와 모바일 진단 캡처는 계속 원본 figure에 적용한다.

CSS의 공통 figure 팔레트는 테마/인쇄 모드와 관계없이 흰 바탕과 진한 텍스트/선이다. 그림 안의 중복 시각 제목은 숨기고 접근성 캡션 ID는 유지한다. 의미상 비교 가능한 두 개의 최상위 lane만 원본 캔버스에서 나란히 두며, 세로 비교, 조건 분기, 반복, 시퀀스는 그 의미를 보존한다. 짧은 직렬 3단계 그림 중 opt-in한 것만 가로 카드로 배치한다. 모든 다이어그램을 Jev의 정책 분기 토폴로지로 치환하지 않는다. 화면용 PNG는 `--theme light`와 결정적 폰트 프로필로 생성한다. export 전용 브라우저에서 `html`/`body` 배경을 흰색으로 고정하고, 첫 raster 픽셀이 흰색인지 검사해 어두운 본문 배경이 소수점 크롭 가장자리로 스며드는 실패를 막는다. 최종 전수 PNG의 네 모서리와 잘림, 과도한 높이도 실제 픽셀에서 별도로 점검한다. 기존 저장소 PNG는 새 팔레트를 반영하지 않으므로 소스/CSS 변경 후 전체 mapped corpus를 fresh build에서 재export하고 전체 check/release를 통과시켜야 한다. 한 장만 갱신하거나 현재 이미지를 새 스타일이라고 표시하지 않는다.

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

내부 제목은 `div` 또는 `strong`으로 만들어 본문 TOC의 heading과 구분한다. 제목을 보여주는 그림은 figure의 `aria-labelledby`가 고유한 title id를 참조한다. 시각 제목이 본문과 중복되는 그림은 제목을 그리지 않고 figure에 비어 있지 않은 `aria-label`로 접근성 이름만 남긴다. 조건을 담은 edge label은 보조 기술에서도 읽을 수 있어야 한다.

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

## Same-source PNG export

`kkamji_scripts/blog/static_png/` captures the canonical `figure.sd` from an actual Jekyll-built article with compiled theme CSS. It does not author another drawing. Page scripts and external network access are disabled; article width is 625px at a 1280px viewport, desktop PNG is natively rasterized at DPR 3.072 (1920px width, variable height), and mobile QA uses the native 360px viewport and gutters at the same DPR. Locale is `ko-KR`, timezone is UTC. Existing Playwright/Chromium and fontconfig are prerequisites; the runner never installs them. Select an existing Python environment using `DIAGRAM_PYTHON` and, if needed, `PYTHONPATH`.

```bash
bash kkamji_scripts/blog/static_png/run.sh test
JEKYLL_ENV=production bundle exec jekyll b -d /tmp/blog-static-site
# Read-only whole-corpus discovery, no screenshots:
bash kkamji_scripts/blog/static_png/run.sh corpus plan \
  --site /tmp/blog-static-site --out /tmp/blog-png
# One diagnostic image only. Never treat fallback as production-identical:
bash kkamji_scripts/blog/static_png/run.sh \
  --site /tmp/blog-static-site --page posts/litellm-gateway/index.html \
  --figure litellm-architecture --out /tmp/blog-png-one \
  --font-profile local-fallback
# Add --check to the same command for read-only freshness and geometry checks.
```

### Font policy

Default `--font-profile production` fails closed without `--font-bundle /path/lock.json`. The bundle is an offline snapshot of exact production stylesheet and font URLs, with local binary bytes, SHA-256, source and license provenance. It is not a font-family substitution and does not inject replacement CSS. Bundle structure:

```json
{"resources": [{"url": "https://fonts.example/font.woff2", "path": "font.woff2", "sha256": "<actual SHA-256>", "content_type": "font/woff2", "source": "<provenance URL and revision>", "license": "<license provenance>"}]}
```

Relative paths must stay inside the lock directory. Duplicate URLs, changed bytes and missing provenance fail. Include the original remote CSS as well as all required font subsets and weights. No fetch, font download or installation is performed. Chromium CDP records fonts actually used for glyphs at both widths; a production run rejects any system-font fallback or blocked stylesheet/font request. Actual loaded web-font binary hashes and all bundle resource hashes enter the receipt fingerprint. Local built CSS/font/image files and installed font binaries from fontconfig are also fingerprinted. Actual system PostScript names are resolved to binary candidates; duplicate installations and font collections retain every matching candidate hash rather than claiming a unique file. Unresolved actual system-font names fail. `local-fallback` is an explicit diagnostic profile; receipts always set `production_identical: false`, including pinned runs, because an offline snapshot is not live production attestation.

The public snapshot is `assets/fonts/static-png/lock.json`: 41 exact-URL resources (Google Fonts CSS and fonts, third-party CDN stylesheets and Font Awesome webfonts), with SHA-256 and locally preserved OFL/MIT license evidence. `font_bundle.py` explicitly acquires public bytes; normal export never fetches them. It preserves CSS unchanged and does not copy installed Windows fonts. `coverage.json` records the single-five AI diagnostic coverage.

```bash
# Acquisition is an explicit online maintenance operation, not part of export:
"$DIAGRAM_PYTHON" kkamji_scripts/blog/static_png/font_bundle.py --out assets/fonts/static-png
# After a fresh production build:
bash kkamji_scripts/blog/static_png/run.sh \
  --site /tmp/blog-static-site --page posts/litellm-gateway/index.html \
  --figure litellm-architecture --out /tmp/blog-png-one \
  --font-profile production --font-bundle assets/fonts/static-png/lock.json
```

**Strict production remains blocked and unchanged.** `strict-production` is an explicit alias for `production`; `diagnostic-local` aliases `local-fallback`. The live article requests Lato and Source Sans Pro, neither supplying Hangul in these faces. The strict profile still rejects installed Korean/code fallback and blocked stylesheet/font requests. Do not relabel diagnostics as production parity.

**Approved deterministic export:** `--font-profile deterministic-export` uses `assets/fonts/deterministic-export/lock.json` by default (`--export-font-bundle` can select another verified lock). It pins OFL Noto Sans KR for Korean/Latin and OFL Noto Sans Mono for code to google/fonts revision `5e35378e6bda803962ee6fd257e444a7d459660d`. Both upstream binaries, license text and SHA-256 are preserved locally. Export makes no online request: exact font URLs are fulfilled from verified local bytes. The existing production snapshot can still supply article stylesheet dependencies via `--font-bundle`.

Only the export browser receives uniquely named `@font-face` rules and `figure.sd`-scoped family overrides; article source and shared webpage CSS are untouched. Code uses the pinned monospace face only; unsupported code glyphs fail closed rather than silently selecting another family. CDP rejects every system font and every unexpected webfont actually used within the figure at both widths. Receipts declare `profile: deterministic-export`, `production_identical: false`, record export CSS and font hashes, and retain browser/OS versions. Byte equality is verified on the recorded browser/host, not promised across different Chromium or rasterizer versions.

```bash
DIAGRAM_PYTHON=/home/kkamji/.local/bin/python3.11 bash kkamji_scripts/blog/static_png/run.sh \
  --site /tmp/blog-static-site --page posts/litellm-gateway/index.html \
  --figure litellm-architecture --out /tmp/blog-png-one \
  --font-profile deterministic-export --font-bundle assets/fonts/static-png/lock.json
# Repeat with --check for read-only freshness and quality verification.
```

Offline loading waits for the document load event, `document.fonts.ready`, and figure image decoding with explicit 30-second bounds. There is no network-idle dependency or fixed sleep. Tests cover missing Hangul, missing code fonts, unexpected fonts, byte-identical repeated desktop/mobile PNGs, and changed font freshness.

The single-five diagnostic run uses this bundle with explicit `local-fallback`; its receipts record exact installed font binary hashes, `production_identical: false`, and actual fonts at both widths. These are reproducible inputs on the recorded host only, not release approval. Existing DejaVu fixtures remain synthetic integration tests, not production evidence. Review refreshed screenshots and pass all quality gates before releasing assets.

### Corpus and freshness

After the layout is final, run `corpus export` with the same `--site`, `--out`, `--theme` and production font bundle options, then `corpus check`. Do not batch-export during layout editing. Discovery inventories every catalog include and every built figure occurrence, including ID-less SAP figures selected through `aria-labelledby` and Docker `include.instance` variants. Unused includes are reported explicitly; missing used figures, unknown built figures and duplicate selectors fail. Each page occurrence has a separate output directory to prevent overwrites.

The manifest binds the complete plan, source include hashes, catalog hash, theme/profile and every receipt hash. Check rebuilds the inventory, verifies the exact manifest, then reruns every receipt check. Receipts bind built page HTML, figure HTML, local dependencies, font inputs, browser/OS/tool versions, desktop and mobile PNG bytes. Missing or modified images and changed input fingerprints fail. Failed quality checks are diagnostic artifacts, not successful release gates.

Freshness proves consistency with the supplied built site. It does not certify that a stale build reflects the current source tree. A fresh production build after all source edits is mandatory. Whole-page HTML hashing is intentionally conservative: build timestamps, prose or helper edits invalidate receipts. Add sibling download includes first, make the final build, then export from it; export itself never modifies built article HTML. Do not rebuild the HTML after capture without rerunning export/check.

`_includes/diagrams/download.html` accepts `png="/assets/img/diagrams/...png"` and must be an immediate sibling after the canonical figure. It provides native download and direct image access without JavaScript. [Download mapping](diagram-downloads.json) accounts for every post occurrence, including repeated include instances, and reserves collision-checked paths. Its pending state is a source mapping, not an export receipt. [Verified export manifest](diagram-export-release.json) records the checked PNG hashes, source identities and rendering environment for the current local release candidate.

`static_png/downloads.py` integrates source wiring, production build stamping, exact-path export and receipt checks. The build stamp binds source and built HTML; later edits require a fresh build. Export uses the approved deterministic font profile, writes per-occurrence evidence outside the repository and copies only passed PNG bytes to the linked repository and built-site paths. Any blocked or failed occurrence makes the complete release fail. Do not rebuild article HTML between export and check. Rebuilding for a later release requires renewed export evidence.

```bash
export DIAGRAM_PYTHON=/home/kkamji/.local/bin/python3.11
SCRIPT=kkamji_scripts/blog/static_png/downloads.py
SITE=/tmp/blog-static-release
OUT=/tmp/blog-png-release
"$DIAGRAM_PYTHON" "$SCRIPT" source-check
"$DIAGRAM_PYTHON" "$SCRIPT" build --site "$SITE"
FONTCONFIG_FILE="$PWD/assets/fonts/deterministic-export/fontconfig.conf" \
  "$DIAGRAM_PYTHON" "$SCRIPT" export --site "$SITE" --out "$OUT" --jobs 4
FONTCONFIG_FILE="$PWD/assets/fonts/deterministic-export/fontconfig.conf" \
  "$DIAGRAM_PYTHON" "$SCRIPT" release --site "$SITE" --out "$OUT" --jobs 4
```

Keep canonical includes at block level: indentation inside Markdown lists can produce escaped closing tags and break sibling adjacency. Wiring preserves prose, frontmatter, dates and footer; every helper must also pass fresh built-DOM checks. Certification tier subtitles and code inside primary labels use 16px. Native comparison tables opt into `sd-quality-table` to prevent theme percentage fonts and nowrap rules from shrinking or overflowing their cells.

For the Linux deterministic release environment, set `FONTCONFIG_FILE="$PWD/assets/fonts/deterministic-export/fontconfig.conf"` for both export and check. This process-local fontconfig sees only the two approved open font files instead of hashing the host's entire Windows/Linux font inventory for every figure. It does not change user or system font configuration. The strict CDP gate still requires the figure to use custom webfonts; installed/system fallback remains a failure, even if it is the same font family. This is a distinct recorded export environment, not byte parity with earlier host-font captures. Use a fresh build and regenerate all images after switching environments.

DOM geometry and selectable-text gates are not visual or semantic approval. Receipts retain `visual_review` and `semantic_review` as `not-run`. Height ratios are review flags, not universal vertical-layout failures. The source palette is light in both site modes. Dark-mode article QA checks the same PNG against its surrounding theme; a separate dark PNG is not a published variant.

## Connector acceptance and recurrence gates

Connector layout is checked against **paint**, not just the unrotated CSS layout box. The [corpus connector review](diagram-connector-review.json) records all include-level results and the scope of native-image review. `static_png/connector_audit.py` collects transformed CDP outer/padding quads without changing canonical HTML. `connector_geometry.py` decomposes painted border sides; empty corners of rotated arrowheads and L-shaped borders are not treated as strokes. Browser Range rectangles represent text layout, not segmented glyph ink.

- Standalone markers reserve at least 4px from nearby endpoint boundaries and their own labels. Primary Gateway markers use the stricter 6px contract; outcome arrows retain 8px card clearance. Issuance arrows are centered between actual text ranges, with a 1.5px symmetry tolerance, rather than between oversized empty text tracks.
- Attached edges retain intentional node-border contact. Collinear mobile bus strokes and their joins must agree within 0.5px. Gateway fork source and branch axes use a 0.25px tolerance. A standalone whitespace rule must not detach a real edge.
- Rounded loops keep their return/self-action meaning. The head must meet the first action, and the source rail the last action, within 0.5px. `connector_loop.py` models straight border strips and quarter-elliptical annuli, with a 0.0001px curve approximation bound; uncertain numerical boundaries and unsupported paint styles fail closed.
- Unknown connector roles, hidden registered markers, malformed named endpoints and unclassified painted pseudo relations are blocking findings, not advisory results or silent omissions. The single retained inline SVG boundary marker is matched by its exact reviewed path/stroke/dash signature, not merely the figure name.

Explicit roles resolve cross-container meanings without inventing nodes:

- `data-connector-role="continuation"`: a flow's terminal marker targets its immediate following structural group. Group members remain alternatives or a collective destination, not an invented serial chain.
- `data-connector-role="reference"`: `data-from`/`data-to` name existing nodes. The following local boundary is still checked for clearance; a physically routed bus from a remote named source is not implied.
- `data-connector-role="loop"`: named endpoints must match the actual last and first action nodes. A one-node self-action remains a self-action.
- `data-connector-role="reference-note"`: an explicit named annotation, with no arrow class or painted pseudo arrowheads. This prevents misleading terminal glyphs from pointing at an unrelated next section.

Both PNG export and read-only `check` call the connector gate at desktop and mobile sizes. `release` runs the same complete check and then records the public release manifest with a source fingerprint. Receipts bind the connector helper code hashes, and the build seal also includes exporter/gate sources. Changing a gate during an export cannot produce a valid mixed-version release.

The normal pre-commit hook runs the fast `release_manifest.py --if-staged` consistency gate for staged diagram source/style/tool/font/PNG changes or changed diagram include lines. It verifies complete source/PNG coverage, current hashes and index agreement. Only confirmed Git-ignored Jekyll cache/build directories and an untracked local `Gemfile.lock` are exempt from index membership; their local hashes remain sealed, and ordinary source images are never exempt. A stale release manifest cannot silently accompany a diagram change. Ordinary prose-only commits do not trigger a whole-corpus export. No browser work is hidden inside the commit hook.

Before corpus publication, run the full connector scan after a stamped fresh build:

```bash
FONTCONFIG_FILE="$PWD/assets/fonts/deterministic-export/fontconfig.conf" \
  /home/kkamji/.local/bin/python3.11 kkamji_scripts/blog/static_png/connector_corpus.py \
  --site /tmp/blog-static-release --out /tmp/blog-connector-audit.json
```

The scan covers every referenced occurrence plus every unused canonical include, at native 360/390 viewports and target 625/720 figure-content widths, in both themes. Three opt-in fixed-canvas sources (Jev and two three-card landscape rows) retain their 625px outer artwork width in both desktop cases; the scanner identifies these as `fixed-source-content` and checks the actual content width after padding, rather than falsely reporting 625/720px reflow. Unused fragments are identified as isolated harness cases, never as article renders. Keep reports outside source/build trees. Geometry checks are supplemented by native-image review of representative problem families; screenshot generation alone is not visual approval. Tests preserve already-spaced flow/direct-arrow controls, role identities and typography floors.

## Rollback

catalog의 원본 경로를 사용해 해당 본문의 include를 이전 이미지 참조로 되돌릴 수 있다. 그림 일부를 되돌릴 때 공통 CSS와 refactor-content 예외는 다른 static 그림이 사용하는지 확인한 뒤 제거한다.

## Mobile layout and stylesheet cache

- Figure padding uses explicit viewport units, `clamp(1rem, 3.5vw, 2rem)`; only descendants use the figure container query. Removing the ineffective self-query preserves existing mobile and desktop spacing without adding a wrapper. Fixed `1rem` was rejected because it moved the multi-column breakpoint and introduced regressions at 720px figure width.
- 시각적으로 중복되는 내부 제목은 숨기되 `figcaption.sd-title`과 `aria-labelledby`를 보존해 ID-less figure 식별과 보조 기술 접근성을 유지한다. 렌더 검사에서는 정확히 클립된 접근성 제목만 그림 내부 글자 크기 및 오버플로 검사에서 제외한다.
- Only Packer detail code preserves its short HCL clauses with `white-space: nowrap`. Do not extend this selector to arbitrary long code.
- Theme 7.6.0 `head.html` and `swconf.js` overrides append the same `site.time` build timestamp to the theme stylesheet URL after `relative_url`. Rebase both full-file overrides when upgrading the gem. No service-worker fetch, activation, purge, or cache-name behavior changes.
- Old cached HTML can still request old CSS until the existing service-worker update lifecycle supplies new HTML. Versioned CSS is not an instant eviction mechanism.
