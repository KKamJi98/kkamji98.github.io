---
title: "LLM Wiki 구축하기 - Obsidian Vault와 검색 계층 [LLM Wiki 2]"
date: 2026-08-15 13:10:00 +0900
author: kkamji
categories: [AI]
tags: [ai, llm, knowledge-base, wiki, rag, bm25, hybrid-search, obsidian, git]
comments: true
image:
  path: /assets/img/ai/rag-04-hybrid-rerank.webp
---

개념을 알았으면 이제 만들어야 한다. 이 글에서는 마크다운 vault 하나를 검색 가능한 LLM Wiki로 만드는 과정을 다룬다. 도구는 Obsidian과 git, 그리고 검색 스크립트다. 특정 SaaS 구독이나 벡터 DB 클러스터는 필요 없다.

---

## 1. 저장소 설계

시작은 디렉터리 구조를 정하는 것이다. 목적별로 나눈 최소 구성은 이렇다.

```
kkamji-vault/
  wiki/
    index.md           # 문서 목차 (전체 조회入口)
    log.md             # 변경 이력
    SCHEMA.md          # 이 vault의 규칙 문서
    concepts/          # 재사용 개념 (기술, 아이디어)
    runbooks/          # 운영 절차 (장애 대응, 배포 절차)
    queries/           # 자주 묻는 질문과 답변 기록
    raw/               # 원문 스냅샷, 절대 수정하지 않는다
    evaluations/       # 검색 품질 측정 결과
  workspaces/          # 진행 중인 프로젝트별 작업 공간
  inbox/               # 분류 전 임시 수집함
```

핵심 원칙은 두 가지다. 첫째, **raw와 정리본을 분리**한다. 원문은 사실의 최종 근거이므로 불변으로 두고, 정리와 해석은 concepts/runbooks에 쓴다. 둘째, **inbox를 둔다**. 완벽하게 분류하려다 첫 주에 포기하는 것이 제일 흔한 실패라, 일단 던져넣고 나중에 분류하는 흐름을 만든다.

파일 이름은 소문자와 하이픈으로 통일한다 (`kubernetes-admission-control.md`). 공백이나 대문자가 들어가면 링크와 검색에서 예외 케이스가 계속 생긴다.

---

## 2. Frontmatter 규격

모든 문서는 같은 frontmatter 형식을 가진다. 이게 LLM이 문서를 평가하는 재료다.

```yaml
---
title: 쿠버네티스 어드미션 컨트롤
created: 2026-05-02
updated: 2026-08-01
type: concept          # concept | runbook | query | decision | ...
tags: [kubernetes, security]
sources: [k8s-docs]
source_status: official  # official | primary | compiled-research | verified-operation | none
confidence: high         # high | medium | low
---
```

`source_status`와 `confidence`가 핵심이다. 공식 문서 기반인지, 내 실험 결과인지, 추정인지를 문서 단위로 남긴다. 에이전트가 답할 때 "high 신뢰도 문서 근거로는 이렇고, low 문서에는 다른 얘기가 있다"고 구분해서 답할 수 있는 기반이 여기서 나온다.

---

## 3. 위키링크와 연결 규칙

문서 사이는 `[[위키링크]]`로 잇는다. 규칙은 단순하게 유지한다.

- 링크는 반드시 실제 파일로 풀려야 한다. 깨진 링크를 남기지 않는다.
- 이름이 중복될 수 있으면 경로까지 쓴다 (`[[runbooks/eks-auth]]`).
- 문서 끝에 "관련 문서" 절을 두고 2~5개 링크를 건다. 그 이상은 목록이 되고 그 이하는 고립된다.

이 규칙을 사람 손으로만 지키면 반드시 깨진다. 그래서 **pre-commit 훅으로 깨진 링크 감지**를 자동화한다. git hook에서 전체 `[[...]]`를 추출해 파일 존재를 검사하고, 하나라도 안 풀리면 커밋을 막는다. 간단한 스크립트 40줄이면 충분하고, 이 훅 하나로 위키 링크 건전성이 영구적으로 유지된다.

---

## 4. 검색 계층 구축

vault가 자라면 키워드 검색부터 넣는다. 첫 단계는 grep, 즉 BM25 계열 풀텍스트 검색이다.

```
# 초보 구성: 파일명 + 본문 grep
rg -l "어드미션 컨트롤" wiki/
```

곧 한계가 온다. 내가 쓴 표현과 질의 표현이 다르면 못 찾는다 ("pod security" vs "파드 보안"). 그래서 두 번째 단계는 **하이브리드 검색**이다. 키워드 검색(BM25)과 임베딩 검색(벡터 유사도)을 각각 돌리고 결과를 섞는다. 로컬에서는 이렇게 시작할 수 있다.

- BM25: 파일 전문 인덱싱 (whoosh, tantivy 등 로컬 엔진)
- 임베딩: 문서 단위 임베딩을 미리 계산해 로컬 파일로 보관
- 결합: 두 스코어를 정규화해 가중합 (예: 키워드 0.6 + 벡터 0.4)

임베딩 모델은 로컬 소형 모델로도 첫 계층은 충분하다. 중요한 것은 모델 성능이 아니라 **문서가 검색 인덱스와 동기화되는 파이프라인**이다. 문서가 갱신되면 인덱스도 갱신돼야 한다. 이 파이프라인이 없으면 검색은 3주 뒤 옛날 지식을 내놓는다.

---

## 5. 섭취 파이프라인

새 지식이 들어오는 흐름을 절차화한다. 회의록, 기술 문서 스냅샷, 에이전트 작업 결과가 들어올 때마다 다음을 반복한다.

1. 원문을 `raw/`에 그대로 보관 (파일명에 날짜)
2. 정리본을 `concepts/` 또는 `runbooks/`에 작성, frontmatter 작성
3. 기존 문서와 겹치면 링크로 연결하고 모순이 있으면 양쪽에 명시
4. `index.md`에 한 줄 추가
5. `log.md`에 변경 이력 한 줄 추가
6. 커밋 (pre-commit 링크 검사 통과)

이 여섯 단계를 사람이 다 하면 지치고, 에이전트가 다 하면 환각이 섞인다. 실제 운영에서는 **원문 보관과 초안은 에이전트가, 분류와 링크 판단은 사람이** 하는 분업이 안정적이다. 에이전트가 초안을 만들고 링크 후보를 제안하면 사람이 승인하는 구조다.

---

## 6. 품질 측정을 붙이는 시점

문서 수가 100을 넘으면 검색 품질을 측정하기 시작한다. 방법은 간단하다.

- 자주 묻는 질문 30~50개를 뽑아 평가셋을 만든다
- 각 질문에 "정답으로 가져와야 할 문서"를 지정한다
- Recall@5 (상위 5개 안에 정답 문서가 몇 개나 오는가)을 주기적으로 측정한다

이 측정이 없으면 검색이 나빠지는 걸 알 방법이 없다. 문서가 늘면 검색 품질은 반드시 변하는데, 그 변화를 수치로 못 보면 "요즘 위키가 이상한데"라는 막연한 느낌만 남는다. 측정 결과는 `evaluations/`에 쌓아 추세를 본다.

---

## 7. 운영 첫 달 체크리스트

- 문서 50개 이상, 깨진 위키링크 0개 유지
- 검색 평가셋 30문항 이상, Recall@5 측정 1회 이상
- raw와 정리본 분리 원칙 준수
- log.md에 주 1회 이상 기록
- inbox가 2주치 이상 쌓이지 않도록 비움

이 구성이 안정되면 다음 단계는 지식 그래프 실험과 검색 품질 회귀 대응이다. 그 이야기는 다음 글에서 다룬다.

---

## 8. Reference

- [Karpathy - LLM Wiki](https://github.com/karpathy/llm-wiki)
- [Obsidian - Internal link](https://help.obsidian.md/Linking+notes+and+files/Internal+links)
- [BM25 - Wikipedia](https://en.wikipedia.org/wiki/Okapi_BM25)
