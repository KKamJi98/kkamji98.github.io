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

## Same-source PNG export

`kkamji_scripts/blog/static_png/` captures the canonical `figure.sd` from an actual Jekyll-built article with compiled theme CSS. It does not author another drawing. Page scripts and external network access are disabled; article width is 625px at a 1280px viewport, mobile QA uses the native 360px viewport and gutters, both at DPR 2. Locale is `ko-KR`, timezone is UTC. Existing Playwright/Chromium and fontconfig are prerequisites; the runner never installs them. Select an existing Python environment using `DIAGRAM_PYTHON` and, if needed, `PYTHONPATH`.

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
  "$DIAGRAM_PYTHON" "$SCRIPT" check --site "$SITE" --out "$OUT" --jobs 4
```

Keep canonical includes at block level: indentation inside Markdown lists can produce escaped closing tags and break sibling adjacency. Wiring preserves prose, frontmatter, dates and footer; every helper must also pass fresh built-DOM checks. Certification tier subtitles and code inside primary labels use 16px. Native comparison tables opt into `sd-quality-table` to prevent theme percentage fonts and nowrap rules from shrinking or overflowing their cells.

For the Linux deterministic release environment, set `FONTCONFIG_FILE="$PWD/assets/fonts/deterministic-export/fontconfig.conf"` for both export and check. This process-local fontconfig sees only the two approved open font files instead of hashing the host's entire Windows/Linux font inventory for every figure. It does not change user or system font configuration. The strict CDP gate still requires the figure to use custom webfonts; installed/system fallback remains a failure, even if it is the same font family. This is a distinct recorded export environment, not byte parity with earlier host-font captures. Use a fresh build and regenerate all images after switching environments.

DOM geometry and selectable-text gates are not visual or semantic approval. Receipts retain `visual_review` and `semantic_review` as `not-run`. Height ratios are review flags, not universal vertical-layout failures. Dark mode must be exported and reviewed separately.

## Rollback

catalog의 원본 경로를 사용해 해당 본문의 include를 이전 이미지 참조로 되돌릴 수 있다. 그림 일부를 되돌릴 때 공통 CSS와 refactor-content 예외는 다른 static 그림이 사용하는지 확인한 뒤 제거한다.

## Mobile layout and stylesheet cache

- Figure padding uses explicit viewport units, `clamp(1rem, 3.5vw, 2rem)`; only descendants use the figure container query. Removing the ineffective self-query preserves existing mobile and desktop spacing without adding a wrapper. Fixed `1rem` was rejected because it moved the multi-column breakpoint and introduced regressions at 720px figure width.
- Titles use `word-break: keep-all` with `overflow-wrap: anywhere` as the long-token fallback. Direct figure arrows receive `0.75rem` block margins; nested flow arrows keep their existing grid gap.
- Only Packer detail code preserves its short HCL clauses with `white-space: nowrap`. Do not extend this selector to arbitrary long code.
- Theme 7.6.0 `head.html` and `swconf.js` overrides append the same `site.time` build timestamp to the theme stylesheet URL after `relative_url`. Rebase both full-file overrides when upgrading the gem. No service-worker fetch, activation, purge, or cache-name behavior changes.
- Old cached HTML can still request old CSS until the existing service-worker update lifecycle supplies new HTML. Versioned CSS is not an instant eviction mechanism.
