---
title: Static diagram authoring and verification
updated: 2026-10-13
type: rule
status: current
---

# Static diagrams

설명용 도식의 정본은 `_includes/diagrams/static/` 및 Packer와 AWS 인증 지도 include의 HTML figure다. 기존 노드, 조건, 접근성 이름과 본문 사용처를 보존한다. 시각 도식은 동일 figure 안의 inline SVG에 박스, 라벨과 간선 좌표를 직접 쓴다. 원본 spec, Draw.io, raster와 출처 및 라이선스는 rollback 증적으로 유지한다. [Diagram catalog](diagram-catalog.json)는 391개 정본 include와 사용처를 연결한다.

## 고정 FHD 캔버스

모든 SVG의 width는 1920, height는 1080, viewBox는 `0 0 1920 1080`이다. 모든 PNG의 실제 픽셀 치수도 정확히 1920 x 1080, 16:9이다. 기존 그림의 단순 확대, 축소, crop이나 비율 왜곡으로 캔버스를 맞추지 않는다. 카드 폭, 글자 크기, 여백과 분기 배치를 FHD 좌표에서 다시 설계한다.

데스크톱과 모바일 모두 표시 크기를 1920 x 1080으로 고정한다. 반응형 재배치, 화면 폭에 따른 자동 축소, container query, breakpoint별 변형을 사용하지 않는다. 화면 폭에 관계없이 같은 노드, 순서, 연결과 16:9 캔버스를 표시한다. `width:100%`, `max-width:100%`, `height:auto`를 그림에 적용해 자동 축소하지 않는다. 스크롤 영역의 폭만 글의 폭을 따르며 내부 그림은 고정 크기다.

좁은 화면에서는 가로 스크롤과 사용자가 선택하는 고정 HTML viewer와 직접 선택하는 확대 링크를 제공한다. 스크롤 영역은 키보드로 접근 가능해야 하고 가장자리 요소를 잘라 숨기지 않는다. 화면 캡처의 치수와 그림 PNG의 치수는 서로 다르므로 구분해 기록한다.

## 읽을 수 있는 의미 구조

한 그림은 한 가지 관계나 차이를 설명한다. 주요 흐름은 가로로 배치하고 병렬 비교는 같은 축에 정렬한다. 실제 계층, 반복과 조건 분기는 의미에 맞게 유지한다. 비교 대상을 임의의 직렬 단계로 바꾸거나 모든 그림을 같은 정책 분기로 치환하지 않는다. 간선의 출발점, 도착점, 방향과 의미 라벨을 각각 확인한다.

제목은 22px 이상, 주요 라벨은 16px 이상, 보조 텍스트와 표 및 코드는 14px 이상이다. FHD에는 충분한 공간이 있으므로 기본 프로필은 주요 라벨 28px와 설명 22px를 사용한다. 복잡한 그림은 정해진 밀도 프로필과 개별 좌표 설계를 적용한다. 글자 크기를 낮춰 겨우 맞춘 그림은 자동 통과로 가독성이 증명되지 않는다.

흰 배경과 진한 글자 및 선을 사용하고 같은 역할에 같은 강조색을 쓴다. 그림 안에는 버튼, 링크, hover 의존 정보, script, 재생이나 애니메이션을 넣지 않는다. 확대와 다운로드 링크는 figure 밖 helper에 둔다.

## 정본과 표시

`figure.sd.sd--fhd`가 기존 의미 소스와 `svg.sd-fhd-artwork`를 함께 소유한다. 원래 caption은 figure의 직접 자식으로 유지한다. `.sd-semantic-source`는 원래 노드, 조건, 설명과 IDs를 접근성 트리에 남기고 시각적으로만 클립한다. `display:none`, `visibility:hidden`, `aria-hidden`으로 원래 의미 소스를 제거하지 않는다. 중복 시각 SVG는 `aria-hidden="true"`를 사용한다. SVG의 노드, 텍스트, 이미지와 간선은 그 의미 소스와 전수 대응해야 한다.

`kkamji_scripts/blog/fhd_svg.py`는 고정 작성 프로필의 좌표를 inline SVG와 독립 SVG 원본으로 저장한다. 같은 include에서 원래 HTML body를 바이트 그대로 복원해 원문 보존을 확인한다. 같은 source에 대해 결과가 다시 생성되는지도 검사한다. 정적 검사는 문자, 조건, 간선 역할, named endpoint, 이미지, 핀 폰트 glyph, 캔버스 경계와 겹침을 검사한다. 자동 그래프 런타임이나 Mermaid는 사용하지 않는다.

`_includes/diagrams/download.html`은 canonical figure의 바로 다음 sibling이다. inline PNG와 다운로드는 같은 PNG URL을 사용한다. 확대 링크는 동일 PNG를 1920 x 1080 고정 크기로 표시하는 script 없는 HTML viewer로 이동한다. 기본 이미지 브라우저의 자동 축소에 의존하지 않는다. viewer의 100%, 125%, 150% 확대는 사용자가 직접 선택할 때만 적용하며, 확대된 전체 크기만큼 스크롤 영역도 늘린다. 그림 이미지는 빈 alt를 사용하며 figure의 접근성 이름과 의미 소스가 설명을 제공한다. `data-static-diagram="true"`는 테마의 별도 확대 및 shimmer wrapper를 방지한다. mapped source figure만 시각적으로 클립하고 helper의 1920 x 1080 PNG를 스크롤 영역에서 표시한다.

[Download mapping](diagram-downloads.json)은 392개 본문 참조를 PNG URL에 연결한다. 383개 used include, 8개 unused include와 반복 사용처를 구분한다. 사용처별 출력 392개와 미사용 정본 출력 8개를 합쳐 PNG 경로는 400개다. 사용처 수를 정본 작성 수나 시각 검토 완료 수로 보고하지 않는다.

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

- 정본 391개와 PNG 사용처 목록의 중복 및 누락 검사.
- 기존 HTML 원문, 원본 이미지와 spec 및 Draw.io 보존 비교.
- SVG width, height, viewBox와 모든 PNG의 실제 헤더 치수 검사.
- 원래 노드, 텍스트, 순서, 조건, fork, merge, loop, 방향과 named endpoint의 SVG 대응.
- 각 PNG를 실제 열어 글자, 선, 화살촉, 글꼴, 여백, 겹침과 잘림을 검토한 결과.
- 데스크톱과 360px/390px에서 1920 x 1080 고정 표시 및 모든 영역의 스크롤 도달 검사.
- source, built HTML, CSS, font, image, SVG, tool, browser와 PNG 해시의 freshness 검사.

정적 parser, DOM 치수 또는 PNG 생성 성공만으로 시각 또는 내용 검토를 완료로 보고하지 않는다. 도식의 작성, 구조 검증, 의미 검증, PNG 생성, 실제 시각 검토와 게시 수를 나눠 기록한다.

## Same-source PNG export

브라우저 자동화는 전역 AGENTS의 Aside 단일 경로를 따른다. MCP가 노출됐으면 `mcp__aside__repl`을 사용한다. MCP가 없으면 현재 help와 guide로 확인한 one-shot `aside repl --host local` 예외만 사용한다. 산출물은 Aside 세션의 `./artifacts/`에 저장하고 반환된 실제 경로와 파일 존재를 확인한 뒤 복사한다.

허용된 Aside 경로가 없으면 렌더링을 차단으로 기록한다. 기존 `static_png/pipeline.py`, connector CDP scanner와 Playwright/Chromium test runner는 과거 구현 및 회귀 증거이며 현재 정책의 폴백 실행 경로가 아니다. 별도 Chromium 설치, 다른 브라우저 실행이나 Full Access 플래그로 우회하지 않는다. `file://` 접근 거절을 받으면 local-file 권한을 자동으로 넓히지 않는다. 승인된 공개 build fixture의 localhost HTTP 검증은 운영 담당자가 소유한다.

`fhd_export.py --site <fresh-site> --out <evidence-dir> --base-url <approved-local-http-url>`는 최대 10개의 SVG를 한 Aside 호출에서 렌더하고 자기 탭을 닫는다. `--start`, `--count`로 체크포인트 이후 범위만 이어갈 수 있다. fixture는 `DIAGRAM_FHD_PROOF=1`인 격리 검증 build에서만 생성된다. 일반 운영 build에 별도 검증 페이지를 게시하지 않는다.

Aside viewport 캡처와 FHD PNG 생성을 구분한다. viewport가 1440 x 900이면 그림은 여전히 1920 x 1080으로 표시하며 스크롤한다. 같은 직접 좌표 SVG를 browser Canvas의 1920 x 1080에 1:1 렌더하는 PNG 경로는 원본 raster의 resize/crop과 다르다. 이 경로도 font 및 image bytes, canonical SVG, fresh build와 결과 PNG를 대응하고 모든 품질 검사를 통과해야 한다. 캡처나 저장 실패를 생성 성공으로 처리하지 않는다.

## Connector acceptance and recurrence gates

기존 normal commit hook의 `static_png/release_manifest.py --if-staged`는 source fingerprint, 모든 PNG 해시, 목록 coverage와 index 일치를 검사한다. 새 source나 renderer를 반영한 전수 build/export/check 증거가 없으면 기존 release manifest는 stale이다. old gate를 건너뛰거나 미검증 FHD 변경을 이전 passed manifest로 통과시키지 않는다. 새 schema 2 release는 391개 source의 검토와 392개 게시 사용처, 미사용 source 8개의 PNG를 각각 검증한다. `fhd_release.py`는 모든 PNG의 실제 검토가 `docs/diagram-fhd-reviews.json`에 해당 SVG 및 PNG 해시와 함께 기록된 뒤에만 release를 저장한다. 렌더 도구는 검토 상태를 자동으로 passed로 바꾸지 않는다. native PNG는 검토 cache에만 저장하며, 전수 자동 게이트와 실제 시각/의미 검토가 통과한 뒤 `fhd_release.py --promote`로 400개 게시 출력 경로에 복사하고 실제 치수와 bytes를 다시 검사한다.

원래 CSS connector 검사는 continuation, reference, reference-note와 loop의 역할 및 paint를 검증했다. inline SVG 이관에서도 그 의미를 보존하고 대응 endpoint와 실제 좌표를 검사한다. 모르는 역할, 명명된 endpoint 누락, 칠해지지 않은 간선이나 clipping은 blocking finding이다. 원래 CSS가 아닌 SVG의 paint를 검증해야 하므로 과거 scanner 성공을 새 SVG 품질로 확대하지 않는다.

[Verified export manifest](diagram-export-release.json)는 기존 release의 증거다. FHD 변경 후에는 새 검증된 전수 증거로 갱신해야 한다. 게시, 머지와 배포는 현재 사용자 승인 범위와 저장소 규칙을 따른다. 첫 시안은 사용자가 확인 후 승인했으므로 그 검토 대기를 다시 만들지 않는다. 이번 FHD 정정은 추가 머지 또는 운영 배포 권한을 부여하지 않았다.

원문 visible text는 레이아웃 atom 추출기와 별도의 HTML data 수집으로 전체 coverage를 대조한다. 혼합 inline의 질문, 예시, 쉼표와 부정 표현도 유지한다. 실행 분기와 그룹 endpoint에는 실제 공통 경계 또는 개별 간선을 그리고, typed connector와 dashed reference의 paint를 보존한다. 긴 API 이름은 카드/간선 폭과 작성 density를 조정하며 단어 내부 분절을 검증 실패로 기록한다. return loop에는 footer와 겹치지 않는 별도 corridor를 배정한다.

## Exact per-source freshness

전체 build fingerprint가 바뀌어도, 한 source의 모든 렌더 입력 bytes가 동일하면 그 source의 통과 native PNG만 재사용할 수 있다. 기존 의미 HTML SHA, authored SVG exact bytes, 고정 폰트 SHA, sealed build의 원본 이미지 bytes, 실제 HTTP fixture에서 읽은 style bytes, native renderer JavaScript SHA와 실제 Aside browser UA를 전부 비교한다. 누락, 변경 또는 이전 자동 실패가 하나라도 있으면 해당 source를 다시 렌더한다. SVG 또는 PNG bytes가 바뀌면 기존 실제 시각/의미 승인을 무효화한다.

과거 receipt에 입력 필드가 없으면 sealed build stamp, 보존된 renderer source, actual HTTP fixture/font와 원본 receipt를 대조하는 명시적 migration을 수행한다. 원본 receipt와 원래 render build ID는 별도로 보존한다. 새 build에서 Aside가 실제 관측한 fixture/font SHA와 browser UA를 다시 확인한 뒤 revalidation build ID를 별도 기록한다. 전체 release gate의 source fingerprint, 검토 SHA와 index 검사도 계속 적용한다. 이 절차는 오래된 625px 출력이나 실패 PNG에 적용되지 않는다.
