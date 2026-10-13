# FHD 고정 크기 다이어그램

사용자가 첫 시안을 승인한 뒤 기존 7노드와 7방향 관계를 1920 x 1080 고정 캔버스에서 다시 배치했습니다. 모든 간선에 의미 라벨을 두었고, `LLM generation`과 `cross-encoder`를 단어 중간에서 나누지 않습니다.

- [1920 x 1080 PNG](hybrid-rerank.png)
- [핀 글꼴을 내장한 FHD SVG](hybrid-rerank.svg)
- [1280px 문서 viewport의 QA 캡처](viewport-1280.png)
- [360px 문서 viewport의 QA 캡처](viewport-360.png)
- [글꼴 라이선스](FONT-LICENSE.txt)

SVG의 width와 height는 1920과 1080이며 viewBox는 `0 0 1920 1080`입니다. PNG의 실제 헤더 치수도 정확히 1920 x 1080입니다. 기존 raster를 확대하거나 자른 결과가 아닙니다. 동일 source SVG를 Aside의 browser Canvas에 1:1 렌더했습니다.

블로그의 desktop 및 좁은 화면에서는 1920 x 1080 고정 크기를 유지합니다. 화면 폭에 따른 자동 축소, 재배치와 breakpoint 변형은 없습니다. 좁은 화면에서는 스크롤하며, script 없는 별도 viewer에서 사용자가 100%, 125%, 150%를 직접 선택할 수 있습니다. 원본 PNG로 이동하는 기본 브라우저 이미지 뷰어의 자동 축소에 의존하지 않습니다.

QA는 실제 built article과 theme JS, viewer를 같은 Aside의 same-origin iframe에서 열어 문서 innerWidth 1280/360/390과 고정 이미지 치수, 스크롤 끝 도달 및 사용자 선택 확대를 검사했습니다. 두 QA PNG 자체의 실제 치수는 1440 x 900입니다. 그 안의 iframe 문서 viewport가 파일명에 표시된 1280px 또는 360px입니다. 물리 모바일 기기 캡처와 구분합니다.

전체 카탈로그391개 도식의 원해상도 PNG와 원문/연결 의미 검토는 docs/diagram-fhd-reviews.json에 각각 기록했습니다. 사용처392개와 미사용 정본8개를 합친 게시용 PNG400개의 실제 치수와 bytes를 검증했습니다. 이 폴더의 QA 캡처만으로 전수 검토를 대신하지 않습니다. 사용자가 머지를 승인한 뒤 같은 PR23을 전체 FHD 구현으로 갱신하므로 미리보기와 전체 구현을 두 번 반영하지 않습니다. 최초 시안 커밋과 보관 검증 증거는 그대로입니다.
