---
title: RAG 청킹과 임베딩, Contextual Retrieval - 검색 품질을 좌우하는 인덱싱 설계 [RAG 2]
date: 2026-06-23 09:00:00 +0900
author: kkamji
categories: [AI]
tags: [rag, chunking, embedding, contextual-retrieval, vector-search, metadata, llm, ai]     # TAG names should always be lowercase
comments: true
image:
  path: /assets/img/kkam-img/kkam.webp
---

[RAG 1편](/posts/rag-overview-concept-and-pipeline/)에서 RAG 파이프라인의 큰 그림을 살펴봤습니다. 이번 글에서는 그중에서도 검색 품질을 가장 크게 좌우하는 **인덱싱 단계**, 즉 문서를 어떻게 쪼개고(chunking), 어떤 임베딩으로 벡터화하며, 청킹 과정에서 잃어버리는 맥락을 어떻게 되살리는지(Contextual Retrieval)를 다룹니다. RAG는 "검색이 틀리면 생성도 틀린다"는 구조라, 인덱싱을 어떻게 설계하느냐가 전체 정확도의 상한을 결정합니다.

> - 청크는 너무 크면 서로 다른 주제가 섞여 **뭉개진 임베딩(noisy averaged embedding)**이 되고, 너무 작으면 **문맥이 끊겨** 단독으로 이해되지 않습니다. 크기에는 sweet spot이 있습니다.  
> - 흔한 출발점은 청크당 약 512 토큰 + 10-20% overlap이지만, **보편 최적값은 없으며** 문서/질의 유형에 맞춰 측정해야 합니다.  
> - 청킹은 각 청크가 원문 안에서 갖던 맥락을 제거합니다. **Contextual Retrieval**은 청크마다 50-100 토큰의 맥락을 LLM으로 생성해 임베딩/BM25 색인 전에 덧붙여 이 문제를 완화합니다.  
> - Anthropic 벤치마크 기준 검색 실패율이 Contextual Embeddings 단독 -35%, Contextual BM25 결합 -49%, reranking 추가 -67%까지 낮아집니다(자사 벤치, 도메인별 재측정 필요).  
> - 메타데이터(출처/부서/권한/개정일)는 필터링, 접근제어(5편), citation의 근거가 되므로 인덱싱 시점에 함께 설계합니다.  
{: .prompt-info}

---

## 1. 왜 청킹이 검색 품질을 좌우하는가

임베딩 모델은 입력 텍스트 하나를 고정 길이 벡터 하나로 압축합니다. 청크가 검색의 최소 단위이므로, 청크를 어떻게 자르느냐가 "무엇이 검색되는가"를 결정합니다. 청크 크기에는 양방향 실패 모드가 있습니다.

- **너무 크면**: 한 청크에 여러 주제가 섞입니다. 임베딩은 그 내용을 평균 낸 벡터가 되어, 특정 주제를 물어도 뭉개진 벡터라 정확히 매칭되지 않습니다(noisy averaged embedding). 또한 검색된 청크가 길면 관련 없는 내용까지 LLM 프롬프트에 들어가 생성 품질과 비용/지연에 부담을 줍니다.
- **너무 작으면**: 문맥이 끊깁니다. "그 한도는 20만원이다" 같은 문장만 남으면, 그것이 무엇의 한도인지(숙박비인지 식비인지) 알 수 없어 검색에도, 생성에도 도움이 되지 않습니다.

즉 청크는 **하나의 완결된 의미 단위**가 되도록 자르는 것이 이상적입니다. 문제는 문서마다 그 단위가 다르다는 점입니다.

---

## 2. 청킹 전략

같은 문서라도 어떤 기준으로 자르느냐에 따라 청크의 모양이 달라집니다. 대표적인 세 가지 접근을 비교하면 다음과 같습니다.

![청킹 전략 비교 - Fixed-size(동일 크기 + overlap, 의미 무시), Structure-aware(문서 구조/헤딩 기준 분할), Semantic(의미가 바뀌는 지점 기준 분할)이 같은 문서를 서로 다르게 나누는 모습](/assets/img/ai/rag-02-chunking-strategies.webp)

### 2.1. Fixed-size Chunking (고정 크기 + overlap)

토큰/문자 수를 기준으로 일정 크기마다 자르고, 인접 청크가 일부 겹치도록 overlap을 둡니다. overlap은 경계에서 문맥이 끊기는 것을 완화합니다. 실무의 흔한 출발점은 **청크당 약 512 토큰, overlap은 청크 크기의 10-20%**입니다. 단순하고 예측 가능하지만, 의미 경계를 무시하고 자르므로 문장/조항 중간이 잘릴 수 있습니다.

> 512 토큰 / 10-20% overlap은 **보편 최적값이 아니라 시작점**입니다. 사실 검색용 짧은 청크와 서술형 긴 청크의 최적치가 다르므로, 실제 문서와 질의로 측정해 조정해야 합니다.  
{: .prompt-warning}

### 2.2. Recursive / Structure-aware Chunking (구조 인식 분할)

문서의 구조(제목, 문단, 리스트, 표 등)를 우선 경계로 삼아 자릅니다. 먼저 큰 단위(섹션)로 나누고, 너무 크면 문단, 문장 순으로 재귀적으로 쪼갭니다. 정책 문서처럼 "조/항/호" 같은 구조가 명확한 문서에 잘 맞습니다. 마크다운/HTML(Confluence)의 헤딩 구조를 활용하면 청크가 자연스러운 의미 단위로 떨어집니다.

### 2.3. Semantic Chunking (의미 기반 분할)

문장 단위 임베딩의 유사도가 급격히 바뀌는 지점을 경계로 삼아, 의미가 이어지는 문장들을 한 청크로 묶습니다. 의미 응집도가 높은 청크를 만들 수 있지만, 사전 임베딩 계산 비용이 들고 항상 고정 크기보다 낫다고 보장되지는 않습니다(도메인에 따라 결과가 갈립니다).

### 2.4. Parent-Child (Small-to-Big)

검색은 작은 청크로 하되, LLM에 넘길 때는 그 청크가 속한 더 큰 부모 청크(또는 원문 구간)를 함께 제공합니다. "검색 정밀도(작은 청크)"와 "생성 문맥(큰 청크)"을 분리해 둘 다 취하는 방식입니다. 정책 문서에서 특정 조항으로 검색한 뒤, 답변에는 해당 조 전체를 근거로 주고 싶을 때 유용합니다.

### 2.5. 전략 비교

| 전략              | 경계 기준         | 장점                          | 주의점                          |
| :---------------- | :---------------- | :---------------------------- | :------------------------------ |
| Fixed-size        | 토큰/문자 수      | 단순, 예측 가능               | 의미 경계 무시, 중간 잘림       |
| Recursive         | 문서 구조         | 구조 있는 문서에 적합         | 구조가 없는 문서엔 효과 제한    |
| Semantic          | 임베딩 유사도     | 높은 의미 응집도              | 사전 계산 비용, 이득 불확실     |
| Parent-Child      | 검색/생성 분리    | 정밀도와 문맥 동시 확보       | 저장/구현 복잡도 증가           |

정답은 하나가 아닙니다. 혼합 소스라면 포맷별로 전략을 달리 적용(구조 있는 위키는 recursive, 평문 PDF는 fixed+overlap)하는 것도 실용적입니다.

---

## 3. 임베딩 모델 선택 기준

임베딩 모델은 검색의 의미 이해 수준을 결정합니다. 선택 시 다음을 함께 봅니다.

- **벡터 차원(dimension)**: 차원이 크면 표현력이 늘지만 저장/검색 비용도 늘어납니다. 검색 품질과 비용의 균형점을 봅니다.
- **최대 입력 길이(context length)**: 청크 크기 전략과 맞아야 합니다. 청크가 모델 입력 한도를 넘으면 잘려서 임베딩됩니다.
- **도메인/언어 적합성**: 한국어 정책 문서라면 한국어(또는 다국어) 성능이 중요합니다. 벤치마크(예: MTEB) 점수와 함께 실제 코퍼스로 검증합니다.
- **운영 방식**: API형(간편, 데이터 외부 전송)과 self-host형(데이터 통제, 운영 부담)의 trade-off가 있습니다. 사내 정책 문서처럼 민감한 데이터라면 데이터 전송 경계가 중요한 선택 기준입니다(5편에서 다룹니다).
- **일관성**: 인덱싱과 질의에 **반드시 같은 임베딩 모델**을 써야 합니다. 모델을 바꾸면 전체 재색인이 필요합니다.

---

## 4. 청킹의 근본 문제: 맥락 손실

청킹에는 전략과 무관한 공통 약점이 있습니다. 청크를 잘라내는 순간, 각 청크가 **원문 어디에 속했는지**에 대한 맥락이 사라진다는 점입니다.

예를 들어 어떤 정책 문서의 한 청크가 "본 한도는 직전 분기 대비 10% 이내로 조정한다"라고만 되어 있다면, 이것이 어느 정책의, 무슨 한도에 대한 규정인지 청크 자체로는 알 수 없습니다. 임베딩은 이 애매한 문장을 그대로 벡터화하므로, "출장 숙박비 한도"를 물어도 이 청크가 검색되지 않을 수 있습니다. 문서 전체를 읽는 사람에게는 자명한 맥락이, 잘린 청크에는 없는 것입니다.

---

## 5. Contextual Retrieval

Anthropic이 제안한 Contextual Retrieval은 이 맥락 손실을 정면으로 다룹니다. 핵심은 각 청크를 색인하기 전에, **그 청크가 원문에서 갖는 맥락을 짧게(50-100 토큰) 생성해 청크 앞에 덧붙이는(prepend)** 것입니다. 이 맥락 생성은 LLM에게 "원문 전체"와 "해당 청크"를 주고 "이 청크의 맥락을 요약하라"고 시켜 얻습니다.

앞의 예시 청크는 다음과 같이 보강됩니다.

```text
# 생성된 맥락(prepend)
이 청크는 "2026년 국내 출장 규정"의 숙박비 한도 조정 조항에 속한다.

# 원본 청크
본 한도는 직전 분기 대비 10% 이내로 조정한다.
```

이렇게 맥락이 덧붙은 텍스트를 **임베딩과 키워드 색인(BM25) 양쪽 모두**에 사용합니다. 그러면 "출장 숙박비 한도 조정"으로 검색했을 때 이 청크가 제대로 매칭됩니다.

![Contextual Retrieval 흐름 - Original Document(prompt caching)와 Chunk를 LLM에 주어 맥락을 생성하고, 맥락이 prepend된 Contextualized Chunk를 Embedding Index와 BM25 Index 양쪽에 색인](/assets/img/ai/rag-02-contextual-retrieval.webp)

### 5.1. 효과

Anthropic의 벤치마크에서 top-20 검색 실패율은 다음처럼 누적적으로 감소했습니다.

| 구성                                         | 검색 실패율(top-20) | 감소폭 |
| :------------------------------------------- | :------------------ | :----- |
| 기본 임베딩(baseline)                        | 5.7%                | -      |
| + Contextual Embeddings                      | 3.7%                | 35%    |
| + Contextual BM25                            | 2.9%                | 49%    |
| + Reranking                                  | 1.9%                | 67%    |

hybrid search(4편)와 reranking(4편)을 함께 쓸수록 효과가 쌓입니다.

> 위 수치는 Anthropic 자사 eval set 기준의 best-case이며, 코드/문서 등 특정 도메인에서 측정된 값입니다. 사내 정책 문서 코퍼스에서는 직접 재측정해야 합니다.  
{: .prompt-warning}

### 5.2. 비용과 상쇄

청크마다 LLM을 호출해 맥락을 생성하므로 ingestion 비용이 듭니다. 다만 원문을 청크마다 다시 전달하는 대신 **prompt caching**으로 원문을 한 번만 캐시에 올리고 재사용하면 비용이 크게 줄어듭니다. Anthropic은 이 일회성 비용을 문서 백만 토큰당 약 $1.02 수준으로 제시합니다. 이는 특정 모델/시점 기준의 추정치이므로, 실제 도입 시 현재 모델 가격으로 재계산해야 합니다.

---

## 6. 메타데이터 설계

청크를 저장할 때 텍스트/벡터만이 아니라 메타데이터를 함께 저장합니다. 메타데이터는 이후 여러 기능의 근거가 됩니다.

- **필터링/성능**: 부서/문서 유형으로 검색 범위를 좁혀 정확도와 속도를 높입니다(3편).
- **접근제어**: 문서별 권한(열람 가능 역할)을 메타데이터로 두고, 검색 시점에 사용자 권한과 대조해 결과를 필터링합니다(5편의 핵심).
- **출처(citation)**: 문서 ID, 제목, 페이지/섹션을 저장해 답변에 근거를 붙입니다(7편).
- **최신성**: 개정일을 저장해 오래된 규정과 최신 규정을 구분하거나 재색인 대상을 관리합니다.

정책 문서 RAG의 예시 메타데이터 스키마는 다음과 같습니다.

```yaml
chunk:
  id: policy-travel-2026#c012
  text: "..."            # (Contextual Retrieval 적용 시 맥락 prepend된 텍스트)
  embedding: [...]
  metadata:
    doc_id: policy-travel-2026
    title: "2026 국내 출장 규정"
    source: confluence      # pdf | confluence | wiki
    department: hr
    access_roles: [employee, hr]   # 접근제어 근거 (5편)
    section: "제3조 숙박비"
    updated_at: 2026-05-01
```

> 접근제어에 쓸 권한 메타데이터는 **인덱싱 시점에** 정확히 부여해야 합니다. 누락되거나 오래되면(stale) 권한 필터가 새거나 과하게 막습니다. 이 문제는 5편에서 자세히 다룹니다.  
{: .prompt-tip}

---

## 7. 정책 문서에 적용할 때

- **혼합 소스 파싱**: PDF는 표/레이아웃 때문에 파싱이 까다롭고, Confluence/위키는 HTML 구조가 있어 recursive 분할에 유리합니다. 소스별로 파이프라인을 분기하는 편이 현실적입니다.
- **구조 보존**: "조/항/호" 같은 조항 구조를 메타데이터(section)로 보존하면, 검색 정확도와 citation 품질이 함께 올라갑니다.
- **맥락 보강**: 조항만 잘라내면 맥락이 약하므로, Contextual Retrieval이나 parent-child로 상위 맥락을 함께 확보합니다.
- **재색인 전략**: 정책은 개정됩니다. 개정일 메타데이터와 문서 단위 재색인 파이프라인을 처음부터 설계해 둡니다.

---

## 8. 시리즈 맵

- [(1) RAG 개념과 파이프라인 Overview](/posts/rag-overview-concept-and-pipeline/) - LLM 한계, 파이프라인, 세 가지 목표
- **(2) 청킹/임베딩과 Contextual Retrieval** - 청킹 전략, 임베딩 선택, 맥락 손실 보완, 메타데이터 (현재 글)
- (3) 벡터 DB와 인덱스 - HNSW/IVF, pgvector vs Qdrant, 메타데이터 필터링
- (4) 검색 정확도 - Hybrid Search(BM25 + dense), RRF 융합, reranking
- (5) 보안과 접근제어(DevSecOps) - RBAC/metadata filtering, PII 처리, prompt injection, 캐시-권한 충돌
- (6) 지연 최적화와 평가 - 캐싱, 인덱스 튜닝, top-k, Ragas
- (7) LLM API 연동과 고급 - citation/grounding, GraphRAG/Agentic RAG

---

## 9. Reference

- [Anthropic - Introducing Contextual Retrieval](https://www.anthropic.com/news/contextual-retrieval)
- [Anthropic - Contextual Retrieval (Engineering)](https://www.anthropic.com/engineering/contextual-retrieval)
- [Anthropic Docs - Prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
- [Weaviate - Chunking Strategies for RAG](https://weaviate.io/blog/chunking-strategies-for-rag)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
