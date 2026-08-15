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

LLM Wiki의 개념을 이해했다면 다음 단계는 직접 구축하는 것입니다. 이 글에서는 마크다운 vault 하나를 검색 가능한 LLM Wiki로 만드는 과정을 정리합니다. 도구는 Obsidian과 git, 검색 스크립트면 충분하며 특정 SaaS 구독이나 벡터 DB 클러스터는 필요하지 않습니다.

---

## 1. 저장소 설계

시작은 디렉터리 구조를 정하는 것입니다. 목적별로 나눈 구성은 다음과 같습니다.

```
kkamji-vault/
  wiki/
    index.md           # 문서 목차
    log.md             # 변경 이력
    SCHEMA.md          # 이 vault의 규칙 문서
    concepts/          # 재사용 개념 (기술, 아이디어)
    runbooks/          # 운영 절차 (장애 대응, 배포 절차)
    queries/           # 자주 묻는 질문과 답변 기록
    raw/               # 원문 스냅샷, 수정하지 않음
    evaluations/       # 검색 품질 측정 결과
  workspaces/          # 진행 중인 프로젝트별 작업 공간
  inbox/               # 분류 전 임시 수집함
```

핵심 원칙은 두 가지입니다. 첫째, **raw와 정리본을 분리**합니다. 원문은 사실의 최종 근거이므로 불변으로 두고, 정리와 해석은 concepts/runbooks에 작성합니다. 둘째, **inbox를 둡니다**. 처음부터 완벽하게 분류하려다 중도에 포기하는 경우가 많으므로, 일단 수집하고 나중에 분류하는 흐름을 만드는 것이 안정적입니다.

파일 이름은 소문자와 하이픈으로 통일합니다 (`kubernetes-admission-control.md`). 공백이나 대문자가 들어가면 링크와 검색에서 예외 케이스가 계속 발생합니다.

---

## 2. Frontmatter 규격

모든 문서는 동일한 frontmatter 형식을 사용합니다. 이 메타데이터가 LLM이 문서를 평가하는 재료가 됩니다.

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

`source_status`와 `confidence`가 핵심입니다. 공식 문서 기반인지, 직접 확인한 실험 결과인지, 추정인지를 문서 단위로 남깁니다. 에이전트가 답변할 때 "high 신뢰도 문서 근거로는 이렇고, low 문서에는 다른 내용이 있다"고 구분해서 답할 수 있는 기반이 여기서 만들어집니다.

---

## 3. 위키링크와 연결 규칙

문서 사이는 `[[위키링크]]`로 연결합니다. 규칙은 단순하게 유지합니다.

- 링크는 반드시 실제 파일로 풀려야 하며, 깨진 링크를 남기지 않습니다.
- 이름이 중복될 수 있으면 경로까지 작성합니다 (`[[runbooks/eks-auth]]`).
- 문서 끝에 "관련 문서" 절을 두고 2~5개 링크를 겁니다. 그 이상은 목록이 되고, 그 이하는 고립됩니다.

사람 손으로만 이 규칙을 지키면 반드시 깨진 링크가 쌓입니다. 그래서 **pre-commit 훅으로 깨진 링크 감지를 자동화**합니다. git hook에서 전체 `[[...]]`를 추출해 파일 존재를 검사하고, 하나라도 풀리지 않으면 커밋을 차단합니다. 간단한 스크립트 40줄이면 충분하고, 이 훅 하나로 위키 링크 건전성이 계속 유지됩니다.

---

## 4. 검색 계층 구축

vault가 자라면 먼저 키워드 검색부터 추가합니다. 첫 단계는 grep, 즉 BM25 계열 풀텍스트 검색입니다.

```
# 기본 구성: 파일명 + 본문 grep
rg -l "어드미션 컨트롤" wiki/
```

곧 한계에 부딪힙니다. 문서에 쓴 표현과 질의 표현이 다르면 검색되지 않습니다 ("pod security" vs "파드 보안"). 그래서 다음 단계는 **하이브리드 검색**입니다. 키워드 검색(BM25)과 임베딩 검색(벡터 유사도)을 각각 수행하고 결과를 결합합니다. 로컬에서는 다음과 같이 시작할 수 있습니다.

- BM25: 파일 전문 인덱싱 (whoosh, tantivy 등 로컬 엔진)
- 임베딩: 문서 단위 임베딩을 미리 계산해 로컬 파일로 보관
- 결합: 두 스코어를 정규화해 가중합 (예: 키워드 0.6 + 벡터 0.4)

임베딩 모델은 로컬 소형 모델로도 첫 계층은 충분합니다. 중요한 것은 모델 성능이 아니라 **문서와 검색 인덱스가 동기화되는 파이프라인**입니다. 문서가 갱신되면 인덱스도 갱신되어야 합니다. 이 파이프라인이 없으면 검색은 시간이 지나면서 옛날 지식을 내놓게 됩니다.

---

## 5. 섭취 파이프라인

새 지식이 들어오는 흐름을 절차화합니다. 회의록, 기술 문서 스냅샷, 에이전트 작업 결과가 들어올 때마다 다음을 반복합니다.

1. 원문을 `raw/`에 그대로 보관 (파일명에 날짜 포함)
2. 정리본을 `concepts/` 또는 `runbooks/`에 작성하고 frontmatter 작성
3. 기존 문서와 겹치면 링크로 연결하고, 모순이 있으면 양쪽 문서에 명시
4. `index.md`에 한 줄 추가
5. `log.md`에 변경 이력 한 줄 추가
6. 커밋 (pre-commit 링크 검사 통과)

이 여섯 단계를 사람이 전부 수행하면 부담이 크고, 에이전트에게 전부 맡기면 환각이 섞입니다. 실제 운영에서는 **원문 보관과 초안 작성은 에이전트가, 분류와 링크 판단은 사람이** 하는 분업이 안정적입니다. 에이전트가 초안을 만들고 링크 후보를 제안하면 사람이 검토하는 구조입니다.

---

## 6. 품질 측정

문서 수가 100개를 넘으면 검색 품질 측정을 시작합니다. 방법은 다음과 같습니다.

- 자주 묻는 질문 30~50개를 뽑아 평가셋을 구성합니다
- 각 질문에 "정답으로 가져와야 할 문서"를 지정합니다
- Recall@5 (상위 5개 결과에 정답 문서가 포함되는 비율)을 주기적으로 측정합니다

이 측정이 없으면 검색 품질 저하를 감지할 수 없습니다. 문서가 늘면 검색 품질은 반드시 변화하는데, 이를 수치로 확인하지 못하면 원인 파악 없이 감각적인 불만만 남게 됩니다. 측정 결과는 `evaluations/`에 쌓아 추세를 확인합니다.

---

## 7. 운영 첫 달 체크리스트

- 문서 50개 이상, 깨진 위키링크 0개 유지
- 검색 평가셋 30문항 이상, Recall@5 측정 1회 이상 수행
- raw와 정리본 분리 원칙 준수
- log.md에 주 1회 이상 기록
- inbox에 2주치 이상 쌓이지 않도록 정리

이 구성이 안정되면 다음 단계는 지식 그래프 실험과 검색 품질 회귀 대응입니다.

---

## 8. Reference

- [Karpathy - LLM Wiki](https://github.com/karpathy/llm-wiki)
- [Obsidian - Internal link](https://help.obsidian.md/Linking+notes+and+files/Internal+links)
- [BM25 - Wikipedia](https://en.wikipedia.org/wiki/Okapi_BM25)
