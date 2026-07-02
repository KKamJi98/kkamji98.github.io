---
title: RAG 지연 최적화와 평가 - 캐싱, 인덱스 튜닝, Ragas [RAG 6]
date: 2026-06-28 09:00:00 +0900
author: kkamji
categories: [AI]
tags: [rag, latency, semantic-cache, prompt-caching, ragas, evaluation, faithfulness, ai]     # TAG names should always be lowercase
comments: true
image:
  path: /assets/img/kkam-img/kkam.webp
---

지금까지의 시리즈에서 검색 품질을 높이는 인덱싱, 벡터 DB, hybrid search와 접근제어를 다뤘습니다. 실제 서비스에 올리면 그다음으로 마주치는 문제는 **응답이 느리다**는 점입니다. RAG는 매 질문마다 검색과 생성을 모두 수행하므로 단계마다 지연이 쌓이고, 정확도를 높이려 붙인 reranking이나 접근제어가 다시 지연을 늘립니다. 이번 글에서는 RAG의 지연을 어디서 줄이는지(캐싱, 인덱스 튜닝, top-k), 그리고 그렇게 줄이는 과정에서 정확도가 떨어지지 않는지를 어떻게 측정하는지(Ragas)를 살펴봅니다.

> - RAG 지연은 `retrieval + (reranking) + generation`으로 쌓입니다. 평균이 아니라 **p99(tail)** 기준으로 관리해야 합니다.  
> - ANN 인덱스 파라미터(HNSW `ef_search`, IVF `nprobe`)와 top-k는 recall과 지연을 맞바꾸는 손잡이입니다. 목표 recall을 정하고 그 안에서 지연을 최소화합니다.  
> - **Semantic cache**는 질의 임베딩이 캐시 key와 임계값 tau 이내면 검색을 우회해 지연을 줄이지만, 5편의 접근제어와 충돌해 cross-user 유출 위험이 있습니다.  
> - **Prompt caching**은 정적 prefix를 재사용해 비용/지연을 줄이지만, cache breakpoint를 정적 prefix 끝에 둬야 이득이 납니다.  
> - Ragas의 **Faithfulness**, **Context Precision@K**로 파이프라인 변경 시 정확도 회귀를 게이트합니다.  
{: .prompt-info}

---

## 1. 지연 예산(latency budget) 분해

RAG의 응답 지연은 단일 값이 아니라 여러 단계의 합입니다.

```text
응답 지연 = retrieval + (reranking) + generation
```

일반 LLM 호출과 달리 RAG는 매 질문마다 검색을 먼저 수행하고, 정확도를 위해 reranking을 붙이면 검색 결과를 다시 한번 모델에 통과시키며, 그다음 생성이 이어집니다. 단계마다 지연이 누적되므로, 어느 단계가 병목인지 분리해서 봐야 최적화 지점을 찾을 수 있습니다.

지연을 관리할 때는 평균만 보면 안 됩니다. 평균은 정상이어도 일부 요청이 크게 느린 경우가 흔한데, 사용자 체감은 그 느린 요청에 좌우됩니다. 따라서 **p99 같은 tail 지연**을 기준으로 관리해야 합니다. 특정 질의에서 검색 후보가 많거나 생성 토큰이 길어지면 tail이 튀므로, 단계별 p99를 각각 측정해 어디서 늘어나는지 추적합니다.

---

![RAG 지연 예산과 평가 루프 - User Query가 Semantic Cache를 거쳐 hit면 바로 Answer로 bypass하고, miss면 Retrieval/Reranking/LLM Generation을 지나며 지연이 쌓이며, Answer는 Ragas eval로 품질을 측정](/assets/img/ai/rag-06-latency-eval.webp)

---

## 2. ANN 인덱스 튜닝: recall vs latency

[RAG 3편](/posts/rag-vector-database-and-index/)에서 다룬 ANN 인덱스는 정확도(recall)와 지연을 맞바꾸는 파라미터를 제공합니다.

- **HNSW의 `ef_search`**: 탐색 시 유지하는 후보 리스트 크기입니다. 키우면 더 많은 후보를 살펴 recall이 오르지만 지연도 늘고, 줄이면 반대로 빨라지지만 recall이 떨어집니다.
- **IVF의 `nprobe`**: 조회할 클러스터(cell) 수입니다. 키우면 더 많은 영역을 뒤져 recall이 오르지만 지연이 늘고, 줄이면 반대가 됩니다.

두 파라미터 모두 방향은 같습니다. 값을 키우면 recall과 지연이 함께 오르고, 줄이면 함께 내려갑니다. 실무에서는 **목표 recall을 먼저 정하고**, 그 recall을 만족하는 선에서 지연이 가장 낮아지는 값을 찾는 방식으로 튜닝합니다. 무작정 값을 키워 recall을 높이면 지연 예산을 초과하고, 무작정 줄이면 검색이 틀려 생성까지 틀립니다.

---

## 3. top-k 조정

검색에서 몇 개의 청크를 가져올지(top-k)도 지연과 정확도를 함께 움직입니다.

- **너무 많이 가져오면**: 이후 reranking과 generation이 처리할 양이 늘어 지연과 비용이 커집니다. 특히 reranker는 후보 수에 비례해 느려집니다.
- **너무 적게 가져오면**: 정작 필요한 청크가 후보에 들어오지 못해 recall이 손실됩니다.

[RAG 4편](/posts/rag-hybrid-search-and-reranking/)에서 다룬 흐름이 이 딜레마의 해법입니다. 검색 단계에서는 넉넉히 가져오되(over-retrieve), reranker로 관련도 높은 순서로 재정렬한 뒤 상위 top-N만 생성에 넘깁니다. 검색은 빠르고 넓게, reranking은 정밀하게, 생성에는 소수만 전달하는 구조로 recall과 지연을 동시에 잡습니다.

---

## 4. Semantic cache (approximate)

같은 질문이나 의미가 거의 같은 질문이 반복되면, 매번 벡터 DB를 조회하는 것은 낭비입니다. **Semantic cache**는 질의 임베딩을 key로, 그 질의에 대해 검색된 문서(또는 응답)를 value로 캐싱합니다. 새 질의가 들어오면 그 임베딩과 캐시 key들 사이의 거리를 재고, 임계값 tau 이내에 있으면 캐시된 결과를 그대로 반환해 벡터 DB 조회를 우회합니다. 이렇게 검색 지연을 줄입니다.

연구(arXiv:2503.05530, Proximity)에서는 이 approximate semantic cache로 정확도를 유지하면서 검색 지연을 MMLU 기준 최대 59%, MedRAG 기준 최대 70.8%까지 줄였다고 보고합니다.

> 위 수치는 'up to' 형태의 best-case이며, MMLU/MedRAG를 retrieval workload로 차용해 측정한 값입니다. 자체 질의 분포에서는 재측정해야 하고, 질의가 다양할수록 hit rate가 낮아져 이득이 줄어듭니다.  
{: .prompt-warning}

### 4.1. 접근제어와의 충돌 (보안 경고)

semantic cache는 [RAG 5편](/posts/rag-security-and-access-control/)에서 다룬 접근제어와 정면으로 충돌합니다. 캐시가 사용자 권한을 구분하지 않으면, 특정 권한의 사용자를 위해 검색된 결과가 캐시에 올라가고, 이후 다른 권한의 사용자가 유사한 질의를 던졌을 때 그 캐시가 반환될 수 있습니다. 결과적으로 권한 없는 사용자에게 문서가 새거나, cross-user 하이재킹 및 side channel(캐시 hit 여부로 다른 사용자의 질의를 추론) 위험이 생깁니다.

해결책은 **권한 차원을 캐시 key에 포함**하는 것입니다. per-role 또는 per-tenant로 캐시를 격리하면 다른 권한의 결과가 섞이지 않습니다. 다만 key가 세분화될수록 캐시가 잘게 쪼개져 hit rate가 떨어지고, 그만큼 지연 이득도 줄어듭니다. 지연 최적화와 보안 사이의 명확한 trade-off이며, 민감한 문서를 다루는 RAG에서는 보안을 우선해 권한 격리를 기본값으로 두는 편이 안전합니다.

---

## 5. Prompt caching과 cache breakpoint 함정

Semantic cache가 검색 단계를 줄인다면, prompt caching은 생성 단계의 LLM 입력을 줄입니다. 시스템 프롬프트나 정책 문서처럼 **매 요청 동일한 정적 prefix**를 캐시에 올려 재사용하면, 그 부분을 매번 다시 처리하지 않아 비용과 지연이 줄어듭니다. Anthropic 기준으로 cache read는 base input token 가격의 0.1배 수준이라 반복 요청에서 이득이 큽니다.

핵심 함정은 **cache breakpoint 위치**입니다. cache breakpoint는 정적 prefix가 끝나는 지점에 둬야 합니다. 프롬프트는 앞에서부터 순서대로 캐시 매칭되므로, 매 요청 바뀌는 내용(timestamp, 사용자 질의 등)이 캐시 블록 안에 들어가면 그 지점부터 prefix가 매번 달라져 cache hit가 나지 않습니다. 결과적으로 매 요청 새로 cache write만 발생하고(write는 read보다 비쌈), 재사용 이득이 사라집니다.

> 정적 프롬프트와 문서는 **prefix**에 두고, 가변 query는 **suffix**에 둡니다. cache breakpoint는 정적 부분의 끝에 배치해야 그 앞부분이 재사용됩니다.  
{: .prompt-tip}

---

## 6. 평가(Evaluation)와 정확도 회귀 방지

지금까지의 최적화는 모두 지연을 줄이는 대신 recall이나 정확도를 조금씩 희생할 수 있습니다. 그래서 파이프라인을 바꿀 때마다 정확도가 떨어지지 않았는지 측정하는 **회귀 게이트**가 필요합니다. Ragas는 RAG 파이프라인을 정량 평가하는 대표 지표를 제공합니다.

- **Faithfulness**: 응답이 검색된 맥락에 의해 지지되는 정도입니다.

```text
Faithfulness = (검색 맥락이 지지하는 응답 claim 수) / (응답 전체 claim 수)
```

0에서 1 사이 값이며, 높을수록 factual합니다. 0.5면 응답 claim의 절반이 검색 맥락에 근거가 없다는 뜻으로, hallucination을 잡아내는 지표입니다.

- **Context Precision@K**: retriever가 relevant한 청크를 irrelevant한 청크보다 상위에 랭크하는 능력을 측정합니다. 검색이 관련 문서를 잘 가져오고 순위도 잘 매기는지를 보는 지표입니다.

이 지표들을 CI의 회귀 게이트로 사용합니다. 예를 들어 지연을 줄이려 `ef_search`를 낮추거나 semantic cache를 켠 뒤, 평가 셋에서 Faithfulness와 Context Precision@K가 기준선 아래로 떨어지면 변경을 반려합니다. 이렇게 하면 지연 최적화가 정확도를 조용히 갉아먹는 것을 막을 수 있습니다.

---

## 7. 정리

정확도(faithfulness)와 지연은 서로 반대로 당기는 축입니다. 인덱스 튜닝, top-k 축소, semantic cache, prompt caching은 모두 지연을 줄여 주지만, 그 대가로 recall이나 faithfulness를 얼마간 희생할 수 있습니다. 따라서 최적화는 항상 짝을 이뤄 진행해야 합니다. 지연을 줄이는 변경을 넣을 때마다 Ragas로 정확도를 함께 측정하고, tail 지연과 정확도 지표를 동시에 만족하는 지점에서 균형을 잡습니다. 다음 편에서는 검색 결과에 citation과 grounding을 붙이고, GraphRAG/Agentic RAG 같은 고급 구성을 LLM API와 연동하는 방법을 다룹니다.

---

## 8. 시리즈 맵

- [(1) RAG 개념과 파이프라인 Overview](/posts/rag-overview-concept-and-pipeline/)
- [(2) 청킹/임베딩과 Contextual Retrieval](/posts/rag-chunking-embedding-contextual-retrieval/)
- [(3) 벡터 DB와 인덱스](/posts/rag-vector-database-and-index/)
- [(4) 검색 정확도: Hybrid Search + Reranking](/posts/rag-hybrid-search-and-reranking/)
- [(5) 보안과 접근제어(DevSecOps)](/posts/rag-security-and-access-control/)
- **(6) 지연 최적화와 평가** (현재 글)
- [(7) LLM API 연동과 고급](/posts/rag-llm-api-and-advanced/)

---

## 9. Reference

- [Ragas Docs - Available Metrics](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/)
- [Anthropic Docs - Prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
- [arXiv - Proximity: Approximate Semantic Caching for RAG](https://arxiv.org/abs/2503.05530)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
