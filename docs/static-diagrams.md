---
title: Static diagram authoring and verification
updated: 2026-10-13
type: rule
status: current
---

# Static diagrams

설명용 도식의 정본은 `_includes/diagrams/static/` 및 Packer와 AWS 인증 지도 include의 HTML figure다. 기존 노드, 조건, 접근성 이름과 본문 사용처를 보존한다. 시각 도식은 동일 figure 안의 inline SVG에 박스, 라벨과 간선 좌표를 직접 쓴다. 원본 spec, Draw.io, raster와 출처 및 라이선스는 rollback 증적으로 유지한다. [Diagram catalog](diagram-catalog.json)는 391개 정본 include와 사용처를 연결한다.

## 고정 FHD 캔버스

모든 SVG의 width는 1920, height는 1080, viewBox는 `0 0 1920 1080`이다. native PNG와 게시용 WebP의 실제 픽셀 치수도 정확히 1920 x 1080, 16:9이다. 기존 그림의 단순 확대, 축소, resampling, crop이나 비율 왜곡으로 캔버스를 맞추지 않는다. 새 도식의 카드 폭, 글자 크기, 여백과 분기 배치는 FHD 좌표에서 설계한다. 표시 정책만 바꿀 때는 기존 artwork, 원본 좌표와 export geometry를 그대로 보존한다.

원본 캔버스 픽셀과 CSS 표시 크기는 다른 값이다. 데스크톱과 모바일 본문의 `.diagram-download > img.diagram-inline`은 글 폭을 따르며 같은 artwork를 비례 축소한다. inline CSS는 `width:100%`, `min-width:0`, `max-width:100%`, `height:auto`, `min-height:0`, `max-height:none`, `aspect-ratio:16 / 9`를 사용한다. 이것은 저장된 PNG/WebP의 resize나 SVG 좌표 재작성과 다르다. 노드, 순서와 연결의 반응형 재배치, container query와 breakpoint별 artwork 변형은 금지한다. source SVG와 export fixture의 고정 1920 x 1080 CSS 경계는 축소하지 않는다. 표시 보고값은 `responsive-proportional`이다.

본문 이미지에 가로 스크롤을 강제하거나 가장자리 요소를 잘라 숨기지 않는다. 이미지, article과 document 모두 그림으로 인한 가로 overflow가 없어야 한다. 별도 full-size HTML viewer는 사용자가 링크로 직접 선택하는 경로이며 기본 1920 x 1080과 100%, 125%, 150% 확대를 유지한다. viewer의 스크롤 영역만 확대된 전체 그림에 키보드로 접근할 수 있게 한다. CSS 표시 치수, 화면 캡처 치수와 원본 이미지 픽셀 치수는 각각 기록한다. 모바일 축소는 글자를 물리적으로 작게 하므로 실제 article에서 가독성을 확인하고 필요하면 확대 링크를 사용한다.

커버는 본문 도식과 별도 자산이다. `.webp` 확장자나 1920 x 1080 치수만으로 커버를 본문 occurrence나 `.diagram-inline` 대상으로 분류하지 않는다. 도식의 원본 banner가 존재해도 post 커버를 그 body diagram으로 자동 대체하지 않는다.

## 읽을 수 있는 의미 구조

한 그림은 한 가지 관계나 차이를 설명한다. 주요 흐름은 가로로 배치하고 병렬 비교는 같은 축에 정렬한다. 실제 계층, 반복과 조건 분기는 의미에 맞게 유지한다. 비교 대상을 임의의 직렬 단계로 바꾸거나 모든 그림을 같은 정책 분기로 치환하지 않는다. 간선의 출발점, 도착점, 방향과 의미 라벨을 각각 확인한다.

제목은 22px 이상, 주요 라벨은 16px 이상, 보조 텍스트와 표 및 코드는 14px 이상이다. FHD에는 충분한 공간이 있으므로 기본 프로필은 주요 라벨 28px와 설명 22px를 사용한다. 복잡한 그림은 정해진 밀도 프로필과 개별 좌표 설계를 적용한다. 글자 크기를 낮춰 겨우 맞춘 그림은 자동 통과로 가독성이 증명되지 않는다.

흰 배경과 진한 글자 및 선을 사용하고 같은 역할에 같은 강조색을 쓴다. 그림 안에는 버튼, 링크, hover 의존 정보, script, 재생이나 애니메이션을 넣지 않는다. 확대와 다운로드 링크는 figure 밖 helper에 둔다.

## 정본과 표시

`figure.sd.sd--fhd`가 기존 의미 소스와 `svg.sd-fhd-artwork`를 함께 소유한다. 원래 caption은 figure의 직접 자식으로 유지한다. `.sd-semantic-source`는 원래 노드, 조건, 설명과 IDs를 접근성 트리에 남기고 시각적으로만 클립한다. `display:none`, `visibility:hidden`, `aria-hidden`으로 원래 의미 소스를 제거하지 않는다. 중복 시각 SVG는 `aria-hidden="true"`를 사용한다. SVG의 노드, 텍스트, 이미지와 간선은 그 의미 소스와 전수 대응해야 한다.

`kkamji_scripts/blog/fhd_svg.py`는 고정 작성 프로필의 좌표를 inline SVG와 독립 SVG 원본으로 저장한다. 같은 include에서 원래 HTML body를 바이트 그대로 복원해 원문 보존을 확인한다. 같은 source에 대해 결과가 다시 생성되는지도 검사한다. 정적 검사는 문자, 조건, 간선 역할, named endpoint, 이미지, 핀 폰트 glyph, 캔버스 경계와 겹침을 검사한다. 자동 그래프 런타임이나 Mermaid는 사용하지 않는다.

`_includes/diagrams/download.html`은 canonical figure의 바로 다음 sibling이다. legacy `png=` 입력은 native PNG provenance를 유지할 수 있지만 helper는 그 경로에서 공개 `.webp` URL을 계산한다. inline 이미지와 다운로드는 같은 native 1920 x 1080 WebP URL을 사용한다. 본문만 CSS로 비례 축소하고 확대 링크는 동일 WebP를 원본 크기로 표시하는 script 없는 HTML viewer로 이동한다. viewer의 100%, 125%, 150% 확대는 사용자가 직접 선택할 때만 적용하며, 확대된 전체 크기만큼 스크롤 영역도 늘린다. 그림 이미지는 빈 alt를 사용하며 figure의 접근성 이름과 의미 소스가 설명을 제공한다. `data-static-diagram="true"`는 테마의 별도 확대 및 shimmer wrapper를 방지한다. mapped source figure만 시각적으로 클립하며 고정 source의 min/max 경계가 document scrollWidth로 새지 않게 기존 1px 경계를 보존한다. 공개 WebP는 검토된 native PNG의 lossless 파생본이며 전체 decoded RGBA 픽셀 동일성을 검사한다. SVG와 native PNG는 삭제하거나 재압축하지 않고 원본 증적으로 보관한다.

[Download mapping](diagram-downloads.json)은 본문 참조를 게시 WebP URL과 native PNG 증적에 연결한다. 현재 source catalog는 391개 component이며, 203개 post의 391개 body reference에서 382개 include를 사용하고 body-unused include는 9개다. Jev banner는 별도 cover 사용처이며 body occurrence로 세지 않는다. 보존된 native snapshot의 400개 PNG 출력과 현재 body delivery coverage는 별도 지표다. 변경 전 snapshot의 occurrence 수를 현재 본문 참조 수로 보고하지 않는다. 사용처 수를 정본 작성 수나 시각 검토 완료 수로 보고하지 않는다. mapping의 `png` 같은 legacy 필드명만으로 실제 파일 형식을 추정하지 않고 URL, 응답 bytes와 image decoder로 확인한다.

## 폰트와 아이콘

FHD SVG는 로컬 OFL Noto Sans KR를 사용한다. `assets/fonts/deterministic-export/lock.json`이 Google Fonts revision, 원본 URL, 바이너리 SHA-256과 라이선스 파일을 고정한다. 외부 설치 폰트와 비밀 파일을 복사하지 않는다. 공식 아이콘과 인증 배지는 기존 로컬 자산 및 출처를 보존하며 SVG에서 비율을 유지한다. PNG 생성 때에는 같은 핀 폰트 bytes와 같은 이미지 bytes를 사용한다.

핀 glyph coverage는 source 문자 지원을 증명한다. 실제 브라우저의 글꼴 로딩과 PNG의 가독성은 별도로 확인한다. 원래 article 글꼴과 새 FHD 폰트의 byte parity를 주장하지 않는다. 변경한 폰트, 이미지나 렌더 도구는 출력 freshness를 무효화한다.

## 검증 순서

```bash
uv run python kkamji_scripts/blog/validate_static_diagrams.py --root .
uv run python kkamji_scripts/blog/fhd_svg.py --root . --check --report /tmp/fhd-source-check.json
uv run python docs/_meta/docs_lint.py --root .
DIAGRAM_FHD_PROOF=1 JEKYLL_ENV=production uv run --no-project python kkamji_scripts/blog/static_png/downloads.py build --site /tmp/blog-fhd-site
uv run python kkamji_scripts/blog/check_inline_scripts.py /tmp/blog-fhd-site
```

Ruby와 Bundler는 실제 설치 환경 및 repository dependency를 확인해서 선택한다. 공유 환경의 무거운 build와 전수 export는 한 번에 하나만 실행한다. 모든 source 변경 후 fresh production build를 만들고, 그 build에서 동일 SVG를 PNG로 렌더한다. 오래된 build, 이전 625px/DPR 3.072 출력이나 가변 높이 PNG는 새 FHD 검증 증거로 재사용하지 않는다.

다음 항목을 서로 다른 증거로 남긴다.

- 정본 391개와 현재 body delivery mapping의 중복 및 누락 검사. native snapshot coverage와 body delivery coverage는 별도로 기록하며 커버는 본문 occurrence에 포함하지 않는다.
- 기존 HTML 원문, 원본 이미지와 spec 및 Draw.io 보존 비교.
- SVG width, height, viewBox와 모든 native PNG 및 WebP의 실제 decoded 치수 검사. PNG와 WebP의 전체 decoded RGBA 픽셀 동일성을 별도로 검사한다.
- 원래 노드, 텍스트, 순서, 조건, fork, merge, loop, 방향과 named endpoint의 SVG 대응.
- 각 native PNG와 게시 WebP를 실제 열어 글자, 선, 화살촉, 글꼴, 여백, 겹침과 잘림을 검토한 결과.
- 데스크톱과 360px/390px의 실제 article에서 로딩 완료와 nonzero naturalWidth를 기다린 뒤 글 폭에 맞는 비례 표시, 16:9 비율과 이미지, article 및 document의 가로 overflow 부재를 검사한다. 고정 source/export fixture와 user-selected full-size viewer는 별도로 검사한다.
- source, built HTML, CSS, font, image, SVG, tool, browser, native PNG와 게시 WebP 해시의 freshness 검사.

정적 parser, CSS 계약 테스트, DOM 치수 또는 이미지 생성 성공만으로 시각 또는 내용 검토를 완료로 보고하지 않는다. `static_png/test_responsive_display.py`는 inline 규칙, source 경계, clipping과 보고값만 검사하며 브라우저 cascade, document overflow나 raster 가독성을 증명하지 않는다. 도식의 작성, 구조 검증, 의미 검증, native PNG 생성, WebP 변환, 실제 시각 검토와 게시 수를 나눠 기록한다.

## Same-source PNG export

브라우저 자동화는 전역 AGENTS의 Aside 단일 경로를 따른다. MCP가 노출됐으면 `mcp__aside__repl`을 사용한다. MCP가 없으면 현재 help와 guide로 확인한 one-shot `aside repl --host local` 예외만 사용한다. 산출물은 Aside 세션의 `./artifacts/`에 저장하고 반환된 실제 경로와 파일 존재를 확인한 뒤 복사한다.

허용된 Aside 경로가 없으면 렌더링을 차단으로 기록한다. 기존 `static_png/pipeline.py`, connector CDP scanner와 Playwright/Chromium test runner는 과거 구현 및 회귀 증거이며 현재 정책의 폴백 실행 경로가 아니다. 별도 Chromium 설치, 다른 브라우저 실행이나 Full Access 플래그로 우회하지 않는다. `file://` 접근 거절을 받으면 local-file 권한을 자동으로 넓히지 않는다. 승인된 공개 build fixture의 localhost HTTP 검증은 운영 담당자가 소유한다.

`fhd_export.py --site <fresh-site> --out <evidence-dir> --base-url <approved-local-http-url>`는 최대 10개의 SVG를 한 Aside 호출에서 렌더하고 자기 탭을 닫는다. `--start`, `--count`로 체크포인트 이후 범위만 이어갈 수 있다. fixture는 `DIAGRAM_FHD_PROOF=1`인 격리 검증 build에서만 생성된다. 일반 운영 build에 별도 검증 페이지를 게시하지 않는다.

Aside article viewport 캡처와 FHD PNG 생성을 구분한다. native export fixture는 viewport가 1440 x 900이어도 그림을 1920 x 1080으로 유지하며 필요한 스크롤을 허용한다. 본문 inline 이미지는 이 fixture와 달리 글 폭에 맞춰 비례 축소한다. 같은 직접 좌표 SVG를 browser Canvas의 1920 x 1080에 1:1 렌더하는 PNG 경로는 원본 raster의 resize/crop과 다르다. 이 경로도 font 및 image bytes, canonical SVG, fresh build와 결과 PNG를 대응하고 모든 품질 검사를 통과해야 한다. 게시 WebP 변환은 이 native PNG를 입력으로 하며 geometry를 변경하지 않는다. 캡처나 저장 실패를 생성 성공으로 처리하지 않는다.

## Connector acceptance and recurrence gates

normal commit hook의 `static_png/release_manifest.py --if-staged`는 현재 delivery의 source fingerprint, native PNG와 게시 WebP 해시, 목록 coverage와 index 일치를 검사해야 한다. source, renderer나 delivery CSS 변경을 반영한 fresh build/check 증거가 없으면 기존 release manifest는 stale이다. old gate를 건너뛰거나 미검증 변경을 이전 passed manifest로 통과시키지 않는다. native schema 2 release와 400개 PNG snapshot은 원래 source 검토 및 당시 occurrence 출력에 대한 보존 증거이며 현재 body delivery 개수를 증명하지 않는다. `fhd_release.py`는 모든 native PNG의 실제 검토가 `docs/diagram-fhd-reviews.json`에 해당 SVG 및 PNG 해시와 함께 기록된 뒤에만 native release를 저장한다. `fhd_release.py --promote`는 native PNG 승격 경로이며 WebP 변환 증거를 대신하지 않는다. 공개 delivery는 현재 mapping의 모든 대상에 대해 WebP bytes, 실제 치수, native PNG와의 전체 decoded RGBA 픽셀 동일성, built inline/download/viewer URL과 index coverage를 추가로 검사해야 한다. cover와 body-unused source의 별도 사용처도 각각 보고한다. 원본 SVG, PNG, 검토 receipt와 이전 manifest는 원본 증적으로 남긴다. 렌더나 변환 도구는 실제 시각/의미 검토 상태를 자동으로 passed로 바꾸지 않는다.

normal commit hook는 diagram 변경 시 `test_responsive_display.py`, `test_cover_contract.py`, `test_webp_review_regressions.py`를 먼저 실행한다. 이미지 픽셀 치수와 CSS 표시 크기 혼동, 표지 누락 및 비율, 검증 중 manifest/index 변경과 cover `srcset` 대체가 다시 들어오면 커밋을 막는다. 이 빠른 CPU 회귀는 실제 Aside 검사와 원본/변환 이미지의 byte 검증을 대신하지 않는다.

WebP 검증 환경은 `python3 -m venv .venv`와 `.venv/bin/python -m pip install -r kkamji_scripts/blog/static_png/requirements-webp.txt`로 준비한다. 실제 설치 Ruby/Bundler dependency를 확인한 뒤 해당 Python을 `PYTHON_BIN`으로 사용한다. `downloads.py wire`, `webp_release.py convert --native-stamp <original-stamp> --native-revision <native-commit>`, `downloads.py build --site <fresh-external-site>`, `webp_release.py seal --site <fresh-external-site> --native-stamp <original-stamp> --native-revision <native-commit>`, `webp_release.py check --site <fresh-external-site>` 순서다. 원래 stamp가 없으면 현재 snapshot을 대신 만들어 넣지 않는다. 검증된 이전 WebP release에 보존된 `native_build_stamp` 데이터의 원래 두 fingerprint를 대조해 복원하거나 fresh native render/review를 수행한다.

원래 CSS connector 검사는 continuation, reference, reference-note와 loop의 역할 및 paint를 검증했다. inline SVG 이관에서도 그 의미를 보존하고 대응 endpoint와 실제 좌표를 검사한다. 모르는 역할, 명명된 endpoint 누락, 칠해지지 않은 간선이나 clipping은 blocking finding이다. 원래 CSS가 아닌 SVG의 paint를 검증해야 하므로 과거 scanner 성공을 새 SVG 품질로 확대하지 않는다.

[Verified native export manifest](diagram-export-release.json)는 이전 native raster의 증거로 보존한다. SVG, font, source image나 renderer를 바꾸면 fresh native render와 전수 검토 증거를 갱신한다. 원본을 그대로 둔 format/inline display 변경은 [WebP delivery manifest](diagram-webp-release.json)의 무손실 변환, fresh delivery build와 실제 표시 증거를 갱신하며 이전 native fingerprint를 재계산해 덮어쓰지 않는다. 게시, 머지와 배포는 현재 사용자의 명시적 승인 범위와 저장소 규칙을 따른다. 이미 승인한 같은 목표의 검토나 게시 승인을 단계마다 다시 요구하지 않는다.

원문 visible text는 레이아웃 atom 추출기와 별도의 HTML data 수집으로 전체 coverage를 대조한다. 혼합 inline의 질문, 예시, 쉼표와 부정 표현도 유지한다. 실행 분기와 그룹 endpoint에는 실제 공통 경계 또는 개별 간선을 그리고, typed connector와 dashed reference의 paint를 보존한다. 긴 API 이름은 카드/간선 폭과 작성 density를 조정하며 단어 내부 분절을 검증 실패로 기록한다. return loop에는 footer와 겹치지 않는 별도 corridor를 배정한다.

## Exact per-source freshness

native 갱신에서 본문 대신 커버로 쓰는 그림은 검토된 이전 PNG 경로를 유지한다. 바뀐 native PNG의 공개 WebP를 갱신할 때만 `convert --replace-reviewed`를 사용한다. 이 옵션도 새 native 전체 검증을 먼저 요구하며, 기존 WebP가 이전 sealed delivery의 정확한 해시와 다르면 교체를 거부한다. 변경 전 PNG, WebP, manifest와 검토 증거는 보존한다. 기존 출력이 손상된 경우 이 옵션으로 자동 복구하지 않는다.

SVG를 실제로 수정한 native release는 해당 source를 fresh build에서 다시 렌더하고 검토한다. 입력이 byte 단위로 동일한 source는 아래 재검증 절차로 기존 PNG와 검토를 재사용한다. 새 native manifest와 검토 기록을 생성한 뒤 WebP 변환의 `--native-revision`에 `sha256:<docs/diagram-export-release.json의 정확한 SHA-256>`을 사용할 수 있다. 이 주소는 아직 존재하지 않는 Git 커밋을 가정하지 않으며, native manifest, 원래 build stamp, 검토, 모든 raster 입력과 staged bytes 검증을 유지한다. 기존 release의 Git commit 주소도 계속 지원한다. 이전 증거는 보존하고 실제 변경 source만 새 검토로 교체한다.

전체 build fingerprint가 바뀌어도, 한 source의 모든 렌더 입력 bytes가 동일하면 그 source의 통과 native PNG만 재사용할 수 있다. 기존 의미 HTML SHA, authored SVG exact bytes, 고정 폰트 SHA, sealed build의 원본 이미지 bytes, 실제 HTTP fixture에서 읽은 style bytes, native renderer JavaScript SHA와 실제 Aside browser UA를 전부 비교한다. 누락, 변경 또는 이전 자동 실패가 하나라도 있으면 해당 source를 다시 렌더한다. SVG 또는 PNG bytes가 바뀌면 기존 실제 시각/의미 승인을 무효화한다.

과거 receipt에 입력 필드가 없으면 sealed build stamp, 보존된 renderer source, actual HTTP fixture/font와 원본 receipt를 대조하는 명시적 migration을 수행한다. 원본 receipt와 원래 render build ID는 별도로 보존한다. 새 build에서 Aside가 실제 관측한 fixture/font SHA와 browser UA를 다시 확인한 뒤 revalidation build ID를 별도 기록한다. 전체 release gate의 source fingerprint, 검토 SHA와 index 검사도 계속 적용한다. 이 절차는 오래된 625px 출력이나 실패 PNG에 적용되지 않는다.

## 정렬, 정보 구성과 프로젝트 스타일

같은 위계의 카드와 그룹은 공통 정렬축을 사용한다. 제목 baseline, 비교 카드의 크기, padding과 행 간격을 확인한다. 카드 폭은 역할과 정보량에 따라 다를 수 있으나 그 차이가 제목과 연결의 정렬을 깨면 안 된다. 의미상 필요한 비대칭은 검토 기록에 근거를 남긴다.

FHD의 큰 빈 영역은 본문에 있는 입력 필드, typed answer, 정책 조건이나 실제 예시로 설명력을 높인 뒤 다시 배치한다. 단순 확대, 빈 패널 추가나 출처 없는 내용으로 채우지 않는다. 한 가지 관계를 설명하는 단순한 그림에 불필요한 세부사항을 강제하지 않는다.

승인된 프로젝트의 역할색과 브랜드 표현을 보존한다. Jev의 기존 네온 accent를 회색으로 지우지 않으며, 이 선호를 다른 프로젝트의 색 규칙으로 확대하지 않는다. 흰 배경과 텍스트 대비는 유지하고 사용자 지정 테마는 해당 요청에 따른다.

정렬 오류, 이유 없는 큰 빈 영역과 승인된 색 소실은 시각 검토 미완료 사유다. 치수, hash, byte parity와 구조 검사만으로 이 합격 조건을 대체하지 않는다. 수정한 SVG와 native 출력 및 실제 article을 열고 해당 출력 hash와 판정을 연결한다.
