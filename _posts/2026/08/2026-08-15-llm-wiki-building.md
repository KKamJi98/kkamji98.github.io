---
title: "LLM Wiki 구축하기 - Obsidian Vault와 검색 계층 [LLM Wiki 2]"
date: 2026-08-15 13:10:00 +0900
author: kkamji
categories: [AI, Knowledge Base]
tags: [ai, llm, knowledge-base, wiki, rag, bm25, hybrid-search, obsidian, git]
comments: true
image:
  path: /assets/img/ai/llm-wiki/llm-wiki.webp
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
sources:                 # 출처는 slug가 아니라 되짚어갈 수 있는 URL로 적습니다
  - https://kubernetes.io/docs/reference/access-authn-authz/admission-controllers/
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

사람 손으로만 이 규칙을 지키면 반드시 깨진 링크가 쌓입니다. 그래서 **pre-commit 훅으로 깨진 링크 감지를 자동화**합니다. git hook에서 전체 `[[...]]`를 추출해 파일 존재를 검사하고, 하나라도 풀리지 않으면 커밋을 차단합니다. 깨진 링크 검사만 놓고 보면 40줄 남짓으로 시작할 수 있습니다. 다만 실제로 운영하다 보면 모호한 링크 판별, frontmatter 필수 필드, 원문 체크섬, 고아 문서 탐지가 차례로 붙습니다. 제 경우 이 lint는 255줄까지 자랐습니다. 처음부터 크게 만들 필요는 없고, 깨진 링크 하나만 막는 데서 시작하면 충분합니다.

---

## 4. 검색 계층 구축

![Vault, index, and commit hook](/assets/img/ai/llm-wiki/llm-wiki-build-pipeline.webp)
_커밋 훅에서 색인으로 가는 점선은 데이터 흐름이 아니라 갱신 트리거다. 이 훅이 없으면 색인과 링크 그래프가 노트에서 조용히 멀어진다._

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

## 5. Ingestion 파이프라인

새 지식이 위키로 들어오는 ingestion 흐름을 절차화합니다. 회의록, 기술 문서 스냅샷, 에이전트 작업 결과가 들어올 때마다 다음을 반복합니다.

1. 원문을 `raw/`에 그대로 보관 (파일명에 날짜 포함)
2. 정리본을 `concepts/` 또는 `runbooks/`에 작성하고 frontmatter 작성
3. 기존 문서와 겹치면 링크로 연결하고, 모순이 있으면 양쪽 문서에 명시
4. `index.md`에 한 줄 추가
5. `log.md`에 변경 이력 한 줄 추가
6. 커밋 (pre-commit 링크 검사 통과)

이 여섯 단계를 사람이 전부 수행하면 부담이 크고, 에이전트에게 전부 맡기면 환각이 섞입니다. 실제 운영에서는 **원문 보관과 초안 작성은 에이전트가, 분류와 링크 판단은 사람이** 하는 분업이 안정적입니다. 에이전트가 초안을 만들고 링크 후보를 제안하면 사람이 검토하는 구조입니다.

---

## 6. Reference

- [Karpathy - LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
- [Obsidian - Internal link](https://help.obsidian.md/Linking+notes+and+files/Internal+links)
- [BM25 - Wikipedia](https://en.wikipedia.org/wiki/Okapi_BM25)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
