---
title: Post descriptions
updated: 2026-11-06
type: rule
status: current
---

# Post descriptions

모든 `_posts` 글에 명시적인 `description`을 작성합니다. LoRA 글처럼 제목 아래의 짧은 부제와 검색 및 공유 메타데이터에 같은 설명을 사용합니다. 제목, 날짜, 본문과 footer를 자동 요약으로 대체하지 않습니다.

## 작성 기준

- 글의 실제 원리, 방법, 구별점과 읽고 얻을 내용을 한두 문장으로 적습니다.
- 한국어 문장과 정확한 기술명을 사용합니다. 일반적인 길이는 60-130자이며, 자동 검사는 Unicode 문자 수 40-160자를 허용합니다. 이 범위는 편집 기준이며 검색 노출이나 검색엔진의 표시 길이를 보장하지 않습니다.
- 값은 공백으로 감싸지 않은 한 줄 문자열입니다. YAML에서는 따옴표로 감싸서 `:`와 `#` 등을 안전하게 보존합니다.
- Markdown, HTML, Liquid와 제어 문자를 넣지 않습니다. 새로 쓰는 문장 부호는 ASCII를 사용합니다.
- inline emphasis와 링크는 Markdown parser로 판별합니다. 실제 서식이 아닌 `user_data.tpl`, `C++`, `*.md` 같은 기술 표기는 허용합니다. Unicode punctuation과 line/paragraph separator도 원문 단계에서 검사합니다.
- 제목만 반복하거나 여러 글에 같은 설명을 복제하지 않습니다. '이번 글에서는' 같은 구성 안내보다 내용 자체를 설명합니다.
- 본문에 없는 실험 결과, 최신성, 안전성이나 성능 보장을 추가하지 않습니다. 과거 환경에서 수행한 실습을 현재의 일반적인 권장 설정으로 바꾸지 않습니다.
- 기존 글의 설명을 보강할 때도 본문, 제목, 날짜, 코드, 자산과 footer는 별도 요청 없이 수정하지 않습니다.

## 화면과 메타데이터

Chirpy와 `jekyll-seo-tag`의 기존 경로를 그대로 사용합니다. 별도의 `post` layout이나 head override를 추가하지 않습니다.

production post HTML에서 다음 값이 frontmatter의 설명과 같아야 합니다.

- 화면의 `.post-desc` 부제.
- `meta[name="description"]`.
- `og:description`.
- `twitter:description`.
- Article 계열 JSON-LD의 `description`.

Open Graph와 Twitter가 한 `meta` 요소의 `property`와 `name`에 함께 있어도 허용합니다. HTML entity는 DOM 파서가 한 번 해제한 값을 비교합니다. 부제는 원문 값과 비교합니다. SEO와 JSON-LD는 원문을 현재 사이트의 Markdown converter에 통과시킨 텍스트와 비교합니다. `jekyll-seo-tag`가 apostrophe 등에 적용하는 정상적인 typography는 허용하되, 비교 기준을 렌더 결과에서 역으로 가져오지는 않습니다. 같은 항목이 중복되거나 다른 자동 발췌로 교체되면 실패합니다.

## 검증

저장소의 Ruby bundle 환경에서 실행합니다.

```bash
bundle exec ruby tools/test_post_descriptions.rb
bundle exec ruby kkamji_scripts/blog/check_post_descriptions.rb
bundle exec ruby kkamji_scripts/blog/check_post_descriptions.rb --staged
JEKYLL_ENV=production bundle exec jekyll b -d _site
```

source 검사는 전체 추적 포스트를 읽습니다. `--staged`는 작업 파일 대신 Git index의 전체 포스트 집합을 검사해서 부분 staging의 누락을 잡습니다. 체크아웃에 없는 파일, 잘못된 frontmatter와 중복 `description` 키도 실패합니다. 오류에는 설명 내용 대신 파일 경로와 검사 이름만 출력합니다.

`_plugins/post-descriptions.rb`는 Jekyll의 `post_read`에서 실제 원본 파일의 명시적 값과 중복을 검사하고 변경 불가능한 사본을 보관합니다. frontmatter defaults는 원문의 누락을 대신하지 못합니다. 각 글의 `post_render`에서는 현재 `post.data`가 원본에서 바뀌지 않았는지 확인한 뒤, 보관한 원본으로 실제 HTML 부제와 메타데이터를 대조합니다. 따라서 다른 hook이 값을 바꾸거나 production HTML이 달라지는 경우도 build가 실패합니다.

pre-commit과 `pre_publish_check.sh`는 source 검사와 회귀 테스트를 실행합니다. pre-commit은 rename을 포함한 포스트 변경에서 전체 index를 검사합니다. Pages CI도 같은 검사를 실행하며, 실제 build의 렌더 검사를 생략하지 않습니다. 기존 산문, 날짜, 코드와 다이어그램 게이트는 유지합니다. 이 검사는 내용의 기술적 정확성이나 검색 순위를 자동으로 판정하지 않습니다.

## 관련 문서

- [Technical post template](blog-post-template.md).
- [Code block rendering](code-block-rendering.md).
