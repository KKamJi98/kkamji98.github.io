# Blog Content-Quality Harness

이 문서는 `kkamji_scripts/blog/audit_content_depth.py`(콘텐츠 깊이 하네스)의 설계 의도와 사용법을 정리한다.
기존 `audit_blog_quality.py`(기계적 감사)를 대체하지 않고 보완하는 도구이며, 편집 계획을 돕는 자문(advisory) 성격이다.

## 1. 배경과 동기

기존 `audit_blog_quality.py`는 프런트매터 누락, 깨진 이미지/내부 링크, 금지 문자, 푸터 존재 여부 같은 기계적 신호를 검사한다.
이 신호들은 릴리스 게이트로 유용하지만, "글이 사려 깊게 읽히는가"라는 편집 품질까지 다루지는 않는다.

블로그 운영자가 원하는 방향은 다음과 같다.

- 평범한 한국어 기술 설명 글은 억지로 늘리지 않으면서도 20-30분 정도의 사려 깊은 읽기 경험을 목표로 한다.
- 구조나 흐름을 설명할 때는 이해를 돕는 다이어그램을 곁들인다.
- 처음 등장하는 전문 용어와 약어는 그 자리에서 풀어 준다.
- 도입부, 본문, 결론이 매끄럽게 이어지는 서술을 유지한다.
- 주장에는 신뢰할 수 있는 출처를 붙이고 최하단 Reference에 정리한다.

콘텐츠 깊이 하네스는 이 목표들을 결정론적(deterministic)이고 의존성이 없는(stdlib only) 방식으로 계량화해, 리프레시 우선순위를 잡도록 돕는다.
다만 읽기 시간과 의미 신호는 본질적으로 추정이며, 사람이 판단해야 할 편집 결정을 대신하지 않는다.
그래서 이 신호들은 릴리스를 막지 않는 자문 신호로만 취급한다.

## 2. 품질 루브릭 (운영자 4대 원칙)

각 원칙은 하네스가 내보내는 자문 신호와 연결된다. 신호는 제안이지 판정이 아니다.

### 원칙 1. 적정 깊이와 분량 (padding 없이)

- 목표: 평범한 explainer는 20-30분 읽기를 편집 계획의 기준선으로 삼되, 분량을 채우려고 물타기하지 않는다.
- 읽기 시간은 추정치다. 짧고 집중된 글과 잘 구조화된 긴 시리즈 모두 정답일 수 있으므로, 20-30분은 pass/fail 규칙이 아니라 계획 가이드다.
- 관련 신호: `ENRICH`(주제는 넓은데 본문 추정치가 매우 낮음), `CONDENSE_OR_SPLIT`(본문이 과도하거나 독립적인 대형 H2 그룹이 많음), `DE_BOILERPLATE`(알려진 일반 상투 문구).

### 원칙 2. 이해를 돕는 시각 자료

- 목표: 아키텍처, 흐름, 구조를 말로만 설명하지 않고, 필요할 때 다이어그램이나 그림을 곁들인다.
- 관련 신호: `VISUALIZE`(구조/흐름 언어가 있는데 본문에 인라인 다이어그램이나 이미지가 없음). mermaid 코드 블록도 인라인 시각 자료로 인정한다.

### 원칙 3. 용어와 서술의 친절함

- 목표: 처음 등장하는 약어와 전문 용어를 그 자리에서 설명하고, 도입부-본문-결론이 매끄럽게 이어지도록 한다.
- 관련 신호: `TERM_GAPS`(첫 등장 설명이 없는 대문자 약어가 다수), `FLOW`(도입부, 섹션 구조, 결론 중 빠진 요소).

### 원칙 4. 신뢰할 수 있는 근거

- 목표: 실질적인 내용에는 신뢰할 수 있는 출처를 붙이고, AGENTS.md 규칙대로 최하단 Reference 헤더에 Unordered List로 정리한다.
- 관련 신호: `CITE`(내용은 실질적으로 보이는데 Reference 섹션이 없음).
- 주의: 출처의 존재만 확인한다. 링크가 실제로 주장을 뒷받침하는지, 사실이 맞는지는 사람이 검증한다(4장 참고).

## 3. 자동 게이트 vs 사람 팩트체크 게이트

| 구분 | 담당 | 성격 | 예시 |
| --- | --- | --- | --- |
| 기계적 위반 (자동, 게이트) | 이 하네스 `--fail-on mechanical` | 결정론적, 객관적 | 잘못된 `content_kind` 값, 표준 푸터 중복 또는 마커 오류, 이미지 alt 누락 |
| 콘텐츠 자문 신호 (자동, 비게이트) | 이 하네스 기본 실행 | 휴리스틱, 추정 | 읽기 시간 추정, `ENRICH`/`VISUALIZE`/`CITE` 등 |
| 사실 검증 (사람, 게이트) | 작성자/리뷰어 | 판단 필요 | 주장과 출처의 정합성, 명령/설정의 정확성, 최신성 |

핵심 규칙:

- 자동 게이트는 오직 기계적 위반뿐이다. `--fail-on mechanical`에서만 0이 아닌 종료 코드를 반환한다.
- 읽기 시간과 의미 신호는 어떤 경우에도 릴리스를 막지 않는다. 기본 실행은 항상 0을 반환한다.
- 사실 검증은 사람의 몫이다. 이 도구는 내용의 정확성을 검증하지 않는다.

## 4. content_kind 예외 처리

깊이 신호는 `explainer` 장르에만 적용한다. cheat sheet, 공지, 명시적 면제 글에서 오탐이 나지 않도록 아래 규칙으로 장르를 분류한다.

- `content_quality_exempt: true` 프런트매터가 있으면 `exempt`로 분류하고 깊이 신호를 내보내지 않는다.
- `content_kind: cheatsheet|lab|explainer|announcement` 프런트매터로 수동 분류할 수 있다. 알 수 없는 값은 기계적 오류로 보고한다.
- 자동 분류: 경로가 `_posts/cheat-sheet` 아래이거나 태그에 `cheat-sheet`가 있으면 `cheatsheet`, 코드 비중이 높으면 `lab`, 그 외에는 `explainer`.
- 깊이 신호 대상: `explainer`. `cheatsheet`, `lab`, `announcement`, `exempt`는 깊이 신호를 내보내지 않는다.

읽기 시간 추정은 모든 장르에 대해 계산해 참고 지표로 제공하지만, 위 규칙에 따라 explainer가 아닌 글에는 triage 신호를 붙이지 않는다.

## 5. 읽기 시간 추정 공식 (투명 공개)

프런트매터, HTML 주석, 코드 펜스, 표, 이미지를 제거한 본문에서 다음을 계산한다.

```text
est_minutes = korean_chars / 500 + latin_words / 200
```

- `korean_chars`: 한글 음절 문자 수.
- `latin_words`: 라틴 문자 단어 수.
- 상수: 한국어 기술 산문 500자/분, 영어 기술 산문 200단어/분.
- 모든 분(minute) 값은 추정치(estimate)로 표기한다.
- 코드와 다이어그램의 읽기 시간은 제외되므로, 코드가 많은 글은 실제 체감 시간보다 추정치가 낮게 나온다. 이 값은 절대 기준이 아니라 상대 비교와 계획용 신호다.

이 공식은 조정 가능하며, 스크립트 상단 상수(`KOREAN_CHARS_PER_MIN`, `LATIN_WORDS_PER_MIN`)에서 바꿀 수 있다.
영어 200단어/분 기준은 아래 9장의 Brysbaert(2019) 읽기 속도 메타분석을 참고했고, 한국어 500자/분은 기술 산문에 맞춰 보정한 프로젝트 휴리스틱이다.

## 6. 명령어

저장소 루트에서 실행한다.

```bash
# 전체 _posts 스캔 후 자문 리포트 생성 (항상 0 반환)
python3 kkamji_scripts/blog/audit_content_depth.py

# 특정 글만 대상으로 (glob, _posts 상대 경로 기준)
python3 kkamji_scripts/blog/audit_content_depth.py --only '2026/**'
python3 kkamji_scripts/blog/audit_content_depth.py --only '*cmux*'

# 기계적 위반이 있으면 0이 아닌 코드로 종료 (자문 신호는 절대 실패시키지 않음)
python3 kkamji_scripts/blog/audit_content_depth.py --fail-on mechanical

# 테스트
python3 kkamji_scripts/blog/test_audit_content_depth.py
```

산출물은 `.hermes/reports/`(gitignore 대상)에 생성된다.

- `blog-content-depth.md`: 요약, 분포, 우선순위별 triage, 자문 한계, 장르 예외, 20-30분 목표의 편집 가이드 설명.
- `blog-content-depth.csv`: 신호 컬럼(genre, prose chars, Latin words, estimate, headings, code lines, inline visuals, mermaid, reference, TLDR, signals, confidence 등).
- `blog-content-depth.json`: 동일 데이터의 구조화 버전과 공식/목표 밴드 메타데이터.

## 7. 단계적 도입

이 도구는 처음부터 강한 게이트로 도입하지 않는다.

1. 관찰 단계: 기본 실행으로 리포트만 생성해 분포와 triage를 확인한다. 릴리스는 막지 않는다.
2. 정리 단계: 기계적 위반(푸터 중복/마커, alt 누락, 잘못된 `content_kind`)을 먼저 수리한다.
3. 자문 활용 단계: `pre_publish_check.sh`에 연결해 매 발행 시 자문 리포트를 남긴다. 읽기 시간과 의미 신호는 비게이트이며, 결정론적 기계 위반만 배포를 막는다.
4. 유지 단계: 기계적 위반을 0으로 유지하고, 자문 신호는 우선순위 백로그와 사람 리뷰로 해결한다. 읽기 시간과 의미 신호는 게이트 승격 대상이 아니다.

## 8. AGENTS.md 규칙 보존

이 하네스는 기존 규칙을 그대로 존중한다.

- 최하단 Reference 헤더 규칙: `CITE` 신호는 Reference 섹션 존재를 확인하는 방향으로만 동작한다.
- 고정 푸터: 표준 푸터는 수정하지 않으며, 존재할 경우 정확히 1개이고 마커가 `.prompt-info`인지 확인만 한다.
- 금지 문자: 이 도구의 산출물에는 금지 문자를 쓰지 않는다.

## 9. 참고 자료 (Research Sources)

- [Nielsen Norman Group - How Users Read on the Web](https://www.nngroup.com/articles/how-users-read-on-the-web/)
- [Nielsen Norman Group - F-Shaped Pattern of Reading on the Web](https://www.nngroup.com/articles/f-shaped-pattern-reading-web-content/)
- [Nielsen Norman Group - How Little Do Users Read](https://www.nngroup.com/articles/how-little-do-users-read/)
- [Mayer, R. E. (2009). Multimedia Learning, 2nd ed., Cambridge University Press](https://www.cambridge.org/core/books/multimedia-learning/A0DA71C0D95F62E59ABF2B87AA1015CD)
- [Mayer, R. E. (Ed.) (2014). The Cambridge Handbook of Multimedia Learning, 2nd ed., Cambridge University Press](https://www.cambridge.org/core/books/cambridge-handbook-of-multimedia-learning/6A3CDFC0D6D218A784EE6D3E5D02CD79)
- [Brysbaert, M. (2019). How many words do we read per minute? A review and meta-analysis of reading rate, Journal of Memory and Language](https://doi.org/10.1016/j.jml.2019.104047)
