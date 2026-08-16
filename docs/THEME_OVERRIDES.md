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

### 1. Sidebar quote spacing

- **적용일**: 2026-07-18
- **목적**: 사이트 tagline과 sidebar quote 사이의 공백을 full line break 대신 반 줄 수준으로 축소.
- **파일**:
  - `_includes/sidebar.html`: quote에 `profile-quote` class를 부여하고 별도 `<br>` 제거.
  - `assets/css/jekyll-theme-chirpy.scss`: `#sidebar .profile-quote { margin-top: 0.5rem; }` 추가.
- **검증**: production build 후 생성 CSS와 sidebar markup에서 class 및 margin rule을 확인.

### 2. 검색 결과 페이지네이션

- **적용일**: 2026-06-09
- **gem 버전 기준**: `jekyll-theme-chirpy 7.4.1`
- **출처**: 본인 PR [cotes2020/jekyll-theme-chirpy#2584](https://github.com/cotes2020/jekyll-theme-chirpy/pull/2584) (이슈 #2583). upstream 미머지 상태라 수동 이식.
- **목적**: 기본 검색은 최대 10건만 노출. 변경 후 매칭되는 모든 글을 페이지당 N개로 페이지네이션.
- **성능 재작성(2026-06-09)**: 초기 구현은 PR #2584를 그대로 이식해 `SimpleJekyllSearch`가 매칭 전체를 hidden cache DOM에 렌더하고 `MutationObserver`로 페이지를 잘랐다. `search.json`의 `content`가 `full_text=true`(전체 본문, 약 1.6MB/144건)인데 `limit`을 전체로 올린 탓에, 한 글자 입력마다 수백 개 전체-본문 노드를 동기 렌더해 타이핑이 버벅였다. 이를 데이터 기반(메모리 배열 + debounce + 스니펫 + 현재 페이지만 렌더)으로 재작성해 해소. 이 시점부터 로컬 구현은 PR #2584와 다르다(`SimpleJekyllSearch` 결과 렌더링 미사용). 단, 라이브러리는 테마 `js-selector`가 CDN에서 계속 로드한다(미사용).

| 파일 | 변경 내용 |
| :--- | :--- |
| `_config.yml` | `search.limit`(빈값=전체), `search.per_page: 10` 키 추가 |
| `_includes/search-results.html` | 신규 override. 페이지네이션 `nav` 마크업 추가 |
| `_includes/search-loader.html` | 신규 override. 데이터 기반 페이지네이션 + 관련도 랭킹. `search.json`을 1회 fetch해 메모리 배열로 보관하고, 입력은 debounce(250ms), 현재 페이지만 DOM 렌더(스니펫 ~150자). `SimpleJekyllSearch` 결과 렌더링은 미사용 |
| `assets/css/jekyll-theme-chirpy.scss` | `#search-pagination` 스타일 추가 (원래 PR은 `_sass/pages/_search.scss`였으나 위 메커니즘 이유로 진입점으로 이동) |

- **설정**: `_config.yml`의 `search.per_page`(페이지당 개수), `search.limit`(전체 fetch 상한, 빈값=전체 글).
- **인라인 스크립트 제약**: production은 `compress_html`로 페이지를 한 줄로 접기 때문에 이 loader 안에서는 `//` 주석을 쓸 수 없다(뒤 코드가 전부 주석에 먹혀 `SyntaxError`). 블록 주석만 사용하고, 빌드 후 `python3 kkamji_scripts/blog/check_inline_scripts.py <site>`로 검증한다.
- **rollback 조건**: PR #2584가 upstream에 머지되고 gem을 해당 버전 이상으로 올리더라도, 아래 3의 랭킹/점프 개선은 upstream에 없으므로 되돌리면 검색 품질이 함께 후퇴한다. 롤백은 페이지네이션 기본 동작 한정으로 판단하고, 3의 변경은 별도로 유지 여부를 결정한다. gem 버전 bump 시 include 2개가 gem 신규 변경을 못 받으므로 재검토 필요.

### 3. 검색 관련도 랭킹과 페이지 점프

- **적용일**: 2026-08-15
- **gem 버전 기준**: `jekyll-theme-chirpy 7.4.1`
- **문제 1 (관련도)**: 매칭이 질의 문자열 전체에 대한 substring 검사(`_haystack.includes(query)`)라 `kubernetes helm`처럼 두 단어를 치면 본문에 그 순서로 붙어 있는 글만 걸려 사실상 0건이었다. 점수 개념이 없어 정렬도 최신순 고정이라, 제목이 일치하는 글이 본문에 한 번 스친 최신 글보다 아래로 밀렸다.
- **문제 2 (페이지네이션)**: 테마의 `.pagination` 규칙(`_sass/pages/_home.scss`)이 `#post-list` 밖 top-level 셀렉터라 검색 결과에도 적용되는데, 992px 미만에서 첫/마지막을 제외한 모든 `.page-item`을 숨긴다. 그래서 좁은 화면에서는 화살표만 남았다. 데스크톱에서도 표시 윈도우가 현재±1이고 `...`가 `disabled`라 중간 페이지로 한 번에 갈 수 없었다.

| 파일 | 변경 내용 |
| :--- | :--- |
| `_includes/search-loader.html` | 질의를 공백으로 토큰화해 **모든 토큰이 포함된 글만** 통과(AND). 필드 가중치로 점수 계산(제목 10, 카테고리/태그 4, 본문 1 x 최대 3회) + 제목 구절 일치 15, 본문 구절 일치 5. 점수 내림차순 정렬(동점은 stable sort로 최신순 유지). 스니펫을 첫 매칭 위치 기준으로 잘라 표시. 페이지 윈도우 ±2, `...` 클릭 시 건너뛴 구간 중앙으로 점프, 처음/끝 버튼 추가. 숫자를 항상 노출하므로 모바일 전용 `n / m` 인덱스는 제거 |
| `assets/css/jekyll-theme-chirpy.scss` | `#search-pagination` 안에서 테마의 숨김 규칙을 무효화해 좁은 화면에서도 숫자 노출. `flex-wrap`, `row-gap`, 992px 미만 `column-gap` 추가 |

- **검증(2026-08-15, production build + Playwright)**: `check_inline_scripts.py`로 915 페이지 2,228개 인라인 스크립트 파싱 통과. `kubernetes helm` 41건 이상(기존 0건), `terraform import` 1위가 동명 포스트, 존재하지 않는 토큰을 섞으면 0건(AND 동작 확인). 1400px/500px 양쪽에서 숫자 노출 확인(500px에서 9개 항목 모두 visible, 가로 overflow 없음), 1페이지에서 `...` 한 번으로 중간 페이지 이동 확인.

### 4. 검색 동의어와 코드블록 제외 인덱스

- **적용일**: 2026-08-15
- **gem 버전 기준**: `jekyll-theme-chirpy 7.4.1`

**한/영 교차 검색**: 태그 639개 중 한글이 든 것은 2개뿐이라 글마다 표기를 추가하는 방식은 201개 글을 모두 손봐야 하고 신규 글마다 반복된다. 대신 질의 시점에 확장한다.

| 파일 | 변경 내용 |
| :--- | :--- |
| `_data/search_synonyms.yml` | 신규. 동의어 그룹 목록(`[kubernetes, k8s, 쿠버네티스, 쿠버]` 형태) 60여 개 |
| `_includes/search-loader.html` | `site.data.search_synonyms`를 jsonify로 주입해 `term -> 그룹` Map을 만들고, 각 질의 토큰을 그룹으로 확장. 필드 판정은 그룹 내 아무 표기나 걸리면 성립하고 본문 점수는 표기별 최고값을 쓴다. 스니펫은 확장된 표기 전체를 대상으로 첫 매칭 위치를 찾는다 |

- 그룹에 넣을 영어 표기는 **substring으로 흔한 단어에 숨지 않는 것만** 고른다. `log`(blog), `auth`(author), `cert`(certain)는 의도적으로 제외했다. 파일 상단 주석에 이 규칙을 적어두었다.
- 질의 문자열 그대로가 제목에 있으면 붙는 구절 보너스는 확장 대상이 아니다. 그래서 `k8s`와 `kubernetes`는 결과 집합이 같고 상위 순서만 다르다(질의 철자와 정확히 일치하는 제목이 우선).

**인덱스 크기**: 테마 인덱스는 렌더된 본문 전체를 담아 코드블록(이 블로그 마크다운의 47%)까지 들어갔다. 크기 문제이자 YAML 키/로그 출력이 매칭되는 정밀도 문제였다.

| 파일 | 변경 내용 |
| :--- | :--- |
| `assets/js/data/search.json` | 신규 override. `post.content`를 `<pre`로 split해 `</pre>` 뒤만 이어붙여 코드블록을 제거한 뒤 gem과 동일한 `markdownify | strip_html | ...` 파이프라인 적용. 인라인 `<code>`는 유지하므로 문장 속 명령어/플래그는 그대로 검색된다 |

- **효과(실측)**: raw 2,493,928 B -> **878,420 B**, gzip 731,250 B -> **263,344 B** (64% 감소). 본문 길이 중앙값 6,179자 -> 1,749자.
- **트레이드오프**: 코드블록에만 등장하는 문자열은 더 이상 검색되지 않는다. 확인된 예로 `apiversion`, `imagepullpolicy`는 0건이 된다. 반면 산문에서도 언급되는 `kubectl` 같은 용어는 그대로 걸린다.
- **검증(2026-08-15, production build + Playwright)**: `쿠버네티스`가 `kubernetes`와 동일한 결과 집합(상위 2건 동일), `모니터링`/`인증서`/`관측`이 영문 전용 글에 도달, `테라폼 배포`처럼 한글 다중 토큰도 동작. 인라인 스크립트 2,228개 파싱 통과, `bash tools/test.sh`(빌드 + html-proofer, 915 파일) 통과.
- **후속 판단 기준**: Pagefind 같은 청크 인덱스 전환은 gzip 인덱스가 1MB를 넘어설 때 재검토한다. 현재 263KB에서는 CI에 Node 인덱싱 스텝을 추가할 이득이 없다. Pagefind로 가더라도 한/영 매핑은 사전이 필요하므로 `search_synonyms.yml`은 그대로 쓴다.
