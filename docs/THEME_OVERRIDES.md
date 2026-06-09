# Theme Overrides (Gem Customizations)

이 블로그는 `jekyll-theme-chirpy`를 **gem**으로 사용합니다 (`Gemfile`: `~> 7.3`, 현재 설치 `7.4.1`).
gem 테마 파일을 직접 수정할 수 없으므로, **같은 경로에 파일을 두어 덮어쓰는(override)** 방식으로 커스텀합니다.
이 문서는 gem 기본 동작 위에 수동으로 얹은 변경을 추적하는 **레지스트리**입니다. 새 커스텀을 추가하면 여기에도 항목을 남깁니다.

## Override 메커니즘 (중요)

| 대상 | override 방법 | 동작 여부 |
| :--- | :--- | :--- |
| `_includes/*.html`, `_layouts/*.html` | repo 같은 경로에 파일을 두면 gem 파일을 **완전 대체** | 정상 동작 |
| `_data/*.yml` | 같은 경로 파일이 우선 | 정상 동작 |
| `_sass/pages/_*.scss` 등 **partial 파일 단위** | gem이 Dart Sass 모듈(`@use`/`@forward`)을 써서 `@forward 'search'`가 **gem 내부 파일을 상대경로로 먼저** 잡음 | **동작 안 함** |
| CSS 규칙 추가/수정 | 진입점 `assets/css/jekyll-theme-chirpy.scss`의 `/* append your custom style below */` 영역에 작성 | 정상 동작 |

> SCSS는 partial 파일을 통째로 override해도 production/dev 모두 반영되지 않는다. 반드시 `assets/css/jekyll-theme-chirpy.scss` 진입점에 규칙을 추가할 것.
{: .prompt-warning}

override는 파일을 **병합이 아니라 통째로 대체**한다. include/layout을 override할 때는 gem 원본 전체 + 변경분을 담은 완성본을 넣어야 한다.

## 검증

```bash
bash tools/test.sh   # production 빌드 + html-proofer (회귀 검증)
bash tools/run.sh    # 로컬 미리보기
```

빌드 후 `_site` 산출물에서 커스텀이 실제 반영됐는지 grep으로 확인한다 (빌드 성공 != override 반영).

---

## Overrides 목록

### 1. 검색 결과 페이지네이션

- **적용일**: 2026-06-09
- **gem 버전 기준**: `jekyll-theme-chirpy 7.4.1`
- **출처**: 본인 PR [cotes2020/jekyll-theme-chirpy#2584](https://github.com/cotes2020/jekyll-theme-chirpy/pull/2584) (이슈 #2583). upstream 미머지 상태라 수동 이식.
- **목적**: 기본 검색은 최대 10건만 노출. 변경 후 매칭되는 모든 글을 페이지당 N개로 페이지네이션.
- **성능 재작성(2026-06-09)**: 초기 구현은 PR #2584를 그대로 이식해 `SimpleJekyllSearch`가 매칭 전체를 hidden cache DOM에 렌더하고 `MutationObserver`로 페이지를 잘랐다. `search.json`의 `content`가 `full_text=true`(전체 본문, 약 1.6MB/144건)인데 `limit`을 전체로 올린 탓에, 한 글자 입력마다 수백 개 전체-본문 노드를 동기 렌더해 타이핑이 버벅였다. 이를 데이터 기반(메모리 배열 + debounce + 스니펫 + 현재 페이지만 렌더)으로 재작성해 해소. 이 시점부터 로컬 구현은 PR #2584와 다르다(`SimpleJekyllSearch` 결과 렌더링 미사용). 단, 라이브러리는 테마 `js-selector`가 CDN에서 계속 로드한다(미사용).

| 파일 | 변경 내용 |
| :--- | :--- |
| `_config.yml` | `search.limit`(빈값=전체), `search.per_page: 10` 키 추가 |
| `_includes/search-results.html` | 신규 override. 페이지네이션 `nav` 마크업 추가 |
| `_includes/search-loader.html` | 신규 override. 데이터 기반 페이지네이션. `search.json`을 1회 fetch해 메모리 배열로 보관하고, 입력은 debounce(250ms), 매칭은 substring(title/categories/tags/content), 현재 페이지만 DOM 렌더(스니펫 ~150자). `SimpleJekyllSearch` 결과 렌더링은 미사용 |
| `assets/css/jekyll-theme-chirpy.scss` | `#search-pagination` 스타일 추가 (원래 PR은 `_sass/pages/_search.scss`였으나 위 메커니즘 이유로 진입점으로 이동) |

- **설정**: `_config.yml`의 `search.per_page`(페이지당 개수), `search.limit`(전체 fetch 상한, 빈값=전체 글).
- **rollback 조건**: PR #2584가 upstream에 머지되고 gem을 해당 버전 이상으로 올리면, 위 4개 변경을 되돌린다 (중복/staleness 방지). gem 버전 bump 시 include 2개가 gem 신규 변경을 못 받으므로 재검토 필요.
