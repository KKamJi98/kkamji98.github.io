---
name: diagram
description: 블로그의 설명용 도식을 고정 좌표 inline SVG로 설계하거나 검증할 때 사용한다. 기존 의미 구조와 1920 x 1080 원본을 보존하고 본문 이미지만 글 폭에 맞춰 비례 표시한다.
---

# Blog diagram

저장소 AGENTS.md, docs/index.md, docs/static-diagrams.md와 catalog를 먼저 읽고 현재 branch, HEAD, 사용자 변경을 확인한다. 이 스킬은 도식 작성과 검증을 지원한다. 원격 게시, 머지와 운영 배포는 현재 사용자의 승인 범위를 따른다.

이 블로그의 캔버스, 표시, export와 의미 보존 기준은 저장소 AGENTS.md와 docs/static-diagrams.md를 정본으로 삼는다. 전역 blog-diagram-pipeline guide를 적용할 때도 캔버스 픽셀과 CSS 표시 크기를 분리한다. 블로그의 원본은 정확히 1920 x 1080이며 본문 이미지만 responsive-proportional로 비례 표시한다. 화면 폭에 따른 노드 재배치는 금지한다.

## 고정 FHD 작성

모든 그림을 1920 x 1080, 16:9의 고정 캔버스에서 설계한다. SVG의 width="1920", height="1080", viewBox="0 0 1920 1080"을 사용하고 native PNG와 게시용 WebP의 실제 픽셀 치수도 정확히 1920 x 1080이어야 한다. 공개 WebP는 native PNG와 전체 decoded RGBA 픽셀이 같은 lossless 파생본이다. SVG, native PNG와 이전 raster는 원본 증적으로 보존한다.

새 그림의 박스, 화살표와 라벨 좌표는 inline SVG에 직접 쓴다. Mermaid 등 자동 그래프 레이아웃으로 대체하지 않는다. 기존 이미지의 확대, 축소, resampling, crop이나 비율 왜곡으로 캔버스를 맞추지 않는다. 표시 정책만 수정할 때는 글자 크기, 카드 폭, 여백, 분기 좌표와 export geometry를 바꾸지 않는다.

HTML figure의 기존 의미 구조와 접근성 이름을 보존한다. source와 SVG의 노드, 순서, 방향, 분기 조건, 합류와 반복을 각각 대조한다. 비교의 병렬 대상 사이에 실행 순서를 새로 만들지 않는다. 역할이 같은 요소는 같은 색과 선을 사용하고 배경은 흰색으로 고정한다. 원본 spec, Draw.io, raster, 라이선스와 rollback 자료는 보존한다.

## 정렬과 정보 구성

- 좌표를 쓰기 전에 같은 위계의 카드, 그룹 경계, 제목 baseline과 안쪽 여백의 공통 정렬축을 정한다. 주 흐름 카드의 중심선과 높이, 같은 줄 제목의 baseline과 좌우 padding을 일치시킨다. 의미상 필요한 차이는 검토 기록에 이유를 남긴다.
- 충분한 여백과 설명 없는 큰 빈 영역을 구분한다. 큰 빈 영역은 본문에 있는 입력 필드, 반환 값, 정책 조건이나 측정 예시로 기존 요소의 설명력을 높여 채운다. 글자만 키우거나 빈 카드를 늘리지 않으며, 출처 없는 값이나 새 실행 단계를 만들지 않는다.
- 라벨은 짧게 쓰고 긴 설명은 본문에 둔다. 같은 역할의 카드와 연결은 같은 색, 선 두께와 화살촉을 쓴다. 연결선은 corpus 공통 회색을 유지하고 강조색은 카드와 라벨에만 쓴다.
- 승인된 프로젝트 역할색과 브랜드 표현을 보존한다. Jev는 커버와 같은 보라/청록 neon(`#6e77ff`, `#2ed6b8`)을 쓰며, 이 선호를 다른 프로젝트의 공통 팔레트로 확대하지 않는다. 흰 배경과 본문 대비는 유지한다.
- 비교 대상은 같은 크기를 쓰고 역할이 다른 카드는 정보량에 맞춘 폭을 쓴다. 병렬 질문을 직렬 실행 단계로 바꾸지 않는다.

## 표시와 접근

캔버스 픽셀은 CSS 표시 크기가 아니다. 데스크톱과 모바일 본문의 `.diagram-download > img.diagram-inline`만 `width:100%`, `min-width:0`, `max-width:100%`, `height:auto`, `min-height:0`, `max-height:none`, `aspect-ratio:16 / 9`로 글 폭에 맞춰 비례 표시한다. CSS 축소는 저장된 artwork의 resize나 resampling이 아니다. responsive 노드 재배치, container query와 breakpoint별 artwork 변형은 금지한다. SVG 내부 배치, 순서와 연결은 모든 화면에서 동일하다.

본문 그림에 강제 가로 스크롤이나 clipping을 만들지 않는다. 이미지, article과 document에 그림으로 인한 가로 overflow가 없어야 한다. 별도 full-size HTML viewer의 기본 그림 크기는 1920 x 1080으로 유지하며 사용자가 링크와 100%, 125%, 150% 확대를 직접 선택할 때만 고정 크기와 스크롤 접근을 적용한다. source SVG와 export fixture의 고정 CSS 경계, mapped 의미 소스의 1px clipping을 본문 표시 규칙과 혼동하지 않는다. 원본, inline과 다운로드는 같은 artwork이며 공개 경로는 WebP다.

커버는 별도 자산이다. 확장자나 FHD 치수만으로 커버를 body diagram이나 `.diagram-inline` 대상으로 분류하지 않는다. missing 커버를 본문 diagram으로 자동 대체하지 않는다.

## 검증

정렬, 정보 구성과 승인된 색은 별도 합격 조건이다. 치수, hash와 byte parity가 맞아도 정렬 오류, 설명 없는 큰 빈 영역이나 요청한 역할색 소실이 있으면 시각 검토는 미완료다. native PNG와 실제 article을 열어 확인한 뒤 판정을 해당 출력 hash에 연결한다.

정적 검증과 실제 렌더링은 별도로 기록한다. 모든 SVG/native PNG/WebP의 치수와 viewBox, 전체 decoded RGBA 픽셀 동일성을 검사하고 source 대응, 글꼴과 라이선스, 텍스트 경계, 겹침, 잘림, 방향과 화살촉을 확인한다. 각 source의 구조 검증, SVG 작성, native PNG 생성, WebP 변환, 실제 시각 검토와 게시 완료 수를 나눠 보고한다.

브라우저 자동화는 현재 전역 지침의 Aside 단일 경로만 사용한다. Aside MCP가 없으면 문서화된 one-shot CLI 예외만 사용한다. 허용된 경로가 없거나 캡처가 실패하면 렌더링과 PNG 검증을 미완료로 남긴다. 기존 Playwright/Chromium exporter를 정책 우회로 실행하거나 다른 브라우저를 설치하지 않는다.

실제 desktop과 360px/390px article에서 이미지 complete와 nonzero naturalWidth를 기다린 뒤 글 폭에 맞는 비례 표시, 16:9 비율과 이미지, article 및 document의 가로 overflow 부재를 확인한다. source/export fixture와 user-selected full-size viewer는 별도 검사한다. 실제 native PNG, WebP와 모바일 article을 열어 가독성과 잘림을 판정한다. 정적 parser와 CSS 계약 테스트 통과만으로 브라우저 검증이나 시각 품질 통과를 주장하지 않는다.

inline CSS나 보고값 변경은 `kkamji_scripts/blog/static_png/test_responsive_display.py`에 focused 테스트를 먼저 추가하고 실제 RED와 GREEN을 기록한다. 기존 source/export 경계와 clipping 검사는 characterization임을 구분한다. 이 테스트는 정적 계약만 확인하며 브라우저와 픽셀 QA는 별도 증거로 남긴다.

무거운 build와 전체 corpus export는 공유 자원 담당자와 직렬 조율한다. 사용자의 첫 시안 승인은 현재 요청에 확인됐으면 다시 요구하지 않는다. 머지와 운영 배포는 별도 승인 범위를 확인한다.
