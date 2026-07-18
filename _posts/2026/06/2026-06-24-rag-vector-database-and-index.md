---
title: RAG 벡터 DB와 인덱스 - HNSW/IVF와 pgvector vs Qdrant [RAG 3]
date: 2026-06-24 09:00:00 +0900
author: kkamji
categories: [AI]
tags: [rag, vector-database, pgvector, qdrant, hnsw, ivf, ann, vector-search, ai]     # TAG names should always be lowercase
comments: true
image:
  path: /assets/img/kkam-img/kkam.webp
---

[RAG 2편](/posts/rag-chunking-embedding-contextual-retrieval/)에서 문서를 청크로 나누고 임베딩으로 벡터화하는 인덱싱 설계를 살펴봤습니다. 이제 만들어진 벡터에서 질의와 가까운 후보를 어떻게 찾는지 보겠습니다. 이번 글에서는 정확 검색과 ANN의 차이, 대표 인덱스인 **HNSW와 IVF**, 그리고 **pgvector와 Qdrant**를 선택 기준 관점에서 살펴봅니다. 인덱스는 검색 품질을 직접 보장하지 않지만, 같은 품질 목표를 어느 지연과 메모리 비용으로 달성할지 결정합니다.

> **TL;DR**  
>
> - 정확 검색은 모든 벡터를 비교해 정답 이웃을 보장한다. ANN(Approximate Nearest Neighbor)은 탐색 범위를 줄여 속도를 얻는 대신 결과가 근사값일 수 있다.  
> - HNSW는 다층 그래프를, IVF는 중심점과 목록 분할을 사용한다. 이 글의 IVF 설명은 pgvector의 `IVFFlat`을 기준으로 하며, IVF 계열에는 다른 압축 방식도 있다.  
> - HNSW의 `ef_search`와 IVFFlat의 `probes`는 recall과 지연을 바꾸는 질의 시점 손잡이다. 이 값은 목표 recall과 실제 필터 조건에서 측정해 정한다.  
> - pgvector와 Qdrant 모두 메타데이터 필터를 지원하지만, 필터와 ANN의 결합 방식이 다르다. 권한 필터는 기능 비교가 아니라 정확성과 격리 요구사항으로 검증해야 한다.  
{: .prompt-info}

---

## 1. 벡터 검색의 문제: exact vs ANN

벡터 검색은 질의 벡터 하나와 가장 가까운 벡터 top-k를 저장소에서 찾는 문제입니다. 가장 단순한 방법은 모든 벡터와 거리를 계산해 정렬하는 정확 검색(exact 또는 brute-force)입니다. 이 방식은 정답 이웃을 보장하지만, 데이터 수에 비례해 비교량이 늘어납니다.

지연 예산 안에서 정확 검색이 맞지 않을 때 **ANN(Approximate Nearest Neighbor)**을 검토합니다. ANN은 전량 비교 대신 후보 공간을 좁혀 탐색하는 근사 검색입니다. 즉 "가장 가까운 k개"를 완벽히 보장하지 않으므로, exact 검색 결과를 기준으로 recall을 측정한 뒤 속도와 메모리의 균형을 정해야 합니다.

---

## 2. 벡터 검색의 측정 축

벡터 검색 성능은 하나의 숫자로 요약되지 않습니다. 먼저 exact 검색 결과를 기준값으로 만들고, 서로 맞물려 움직이는 네 축을 같은 데이터와 동시성 조건에서 함께 봐야 합니다.

| 측정 축            | 의미                              | 주의점                            |
| :----------------- | :-------------------------------- | :-------------------------------- |
| **recall**         | 정답 벡터를 얼마나 회수하는가     | 높일수록 지연/메모리 부담 증가    |
| **latency**        | 질의 응답 지연, 특히 p99 tail     | 평균만 보면 꼬리 지연을 놓침      |
| **throughput**     | 초당 처리량(QPS)                  | recall 목표에 따라 크게 변함      |
| **memory**         | 인덱스가 차지하는 메모리/비용     | 인덱스 종류에 따라 편차 큼        |

이 네 축은 서로 trade-off 관계입니다. recall을 높이면 더 많은 후보를 탐색해야 하므로 지연이 늘고, 지연을 줄이려 후보를 줄이면 recall이 떨어집니다. 메모리를 많이 쓰는 인덱스는 대개 recall/지연이 유리한 대신 비용이 큽니다. 따라서 "어떤 인덱스가 더 빠른가" 같은 단일 질문은 성립하지 않으며, **어떤 recall 목표에서, 어떤 지연 예산과 메모리 예산 아래에서** 비교하는지를 함께 정해야 합니다.

특히 latency는 평균이 아니라 **p99 같은 tail**을 봐야 합니다. RAG는 검색 결과를 LLM 생성 앞단에 두므로, 꼬리 지연이 사용자 체감 응답 시간에 그대로 얹힙니다.

---

## 3. HNSW (Hierarchical Navigable Small World)

HNSW는 그래프 기반 ANN 인덱스입니다. 벡터를 노드로 두고 가까운 벡터끼리 이웃으로 연결한 그래프를 여러 계층으로 쌓습니다. 상위 계층은 노드가 성기게 있어 넓은 영역을 빠르게 건너뛰고, 하위 계층으로 내려갈수록 촘촘해집니다. 질의는 상위 계층에서 시작해 가까운 이웃으로 이동하며 하위 계층으로 내려가 후보를 좁힙니다. HNSW 원 논문은 이 계층적 근접 그래프가 탐색 규모를 줄이는 구조를 제시합니다.

pgvector 문서는 HNSW가 IVFFlat보다 speed-recall trade-off가 좋을 수 있지만, 빌드는 더 느리고 메모리를 더 사용한다고 설명합니다. 이 특성은 구현과 설정에 따라 달라지므로, 주요 튜닝 파라미터와 실제 workload에서 함께 확인해야 합니다.

- **M** (빌드 시): 각 노드가 갖는 이웃 연결 수. 크면 그래프가 촘촘해져 recall이 오르지만 메모리와 빌드 비용이 늘어납니다.
- **ef_construction** (빌드 시): 인덱스를 만들 때 탐색하는 후보 폭. 크면 그래프 품질이 좋아지지만 빌드가 느려집니다.
- **ef_search** (검색 시): 질의 시 탐색하는 후보 폭. 크게 하면 recall이 오르는 대신 지연이 늘어납니다. 질의 시점에 recall과 지연을 조절하는 손잡이입니다.

---

## 4. IVF (Inverted File Index)

IVF는 벡터 공간을 여러 **목록(list)**으로 나누는 인덱스 계열입니다. 이 글에서는 pgvector가 지원하는 `IVFFlat`을 가리킵니다. `IVFFlat`은 벡터를 목록에 배정하고, 질의와 가까운 목록 일부만 검색합니다. IVF에는 Product Quantization처럼 벡터를 압축하는 변형도 있으므로, 제품 문서에서 정확한 인덱스 이름을 확인해야 합니다.

핵심 튜닝 파라미터는 **probes**입니다. probes가 크면 더 많은 목록을 검색하므로 recall이 오르지만 그만큼 느려집니다. pgvector의 `IVFFlat`은 목록을 만들기 위한 학습 단계가 있으며, 인덱스를 만들기 전에 대표성 있는 데이터가 있어야 합니다. 데이터가 크게 달라진 뒤에는 현재 recall을 다시 측정해 인덱스 재구성이 필요한지 판단합니다.

| 항목            | HNSW                          | IVFFlat                          |
| :-------------- | :---------------------------- | :------------------------------- |
| 구조            | 계층형 그래프                 | 목록(list) 분할                  |
| 강점            | 높은 recall + 낮은 지연       | 메모리 효율                      |
| 약점            | 메모리 사용 큼                | 학습 필요, 분포 변화에 민감      |
| 검색 손잡이     | ef_search                     | probes                           |
| 빌드 특성       | M / ef_construction           | 목록 학습 후 벡터 배정           |

---

![HNSW vs IVF 인덱스 비교 - HNSW는 계층 그래프에서 greedy search로 탐색(높은 recall, 낮은 지연, 높은 메모리), IVF는 centroids로 클러스터를 나눠 top-nprobe list만 probe(메모리 효율, nprobe 튜닝)](/assets/img/ai/rag-03-hnsw-vs-ivf.webp)

---

## 5. pgvector vs Qdrant

인덱스 알고리즘만큼 중요한 것이 저장소 선택입니다. 대표적인 두 갈래를 선택 기준 관점에서 비교합니다.

### 5.1. pgvector

pgvector는 **PostgreSQL 확장(extension)**입니다. 기존 Postgres 테이블에 벡터 타입 컬럼을 추가하고, 그 위에 인덱스를 얹어 벡터 검색을 수행합니다. 가장 큰 강점은 **운영 단순성**입니다. 이미 Postgres를 쓰고 있다면 별도 시스템을 도입하지 않고, 기존 트랜잭션과 조인, 기존 관계형 데이터와 벡터를 한 곳에서 함께 다룰 수 있습니다. 메타데이터를 일반 컬럼으로 두고 SQL로 필터링하거나, 기존 애플리케이션 데이터와 벡터를 조인하는 것도 자연스럽습니다. 운영 스택을 늘리지 않고 RAG를 시작하려는 팀에 잘 맞습니다.

### 5.2. Qdrant

Qdrant는 벡터와 payload 메타데이터를 함께 다루는 전용 벡터 DB입니다. 공식 문서는 벡터 인덱스와 payload 인덱스를 결합해 필터가 있는 벡터 검색을 지원한다고 설명합니다. 필터에 쓸 payload 필드는 명시적으로 인덱싱해야 하며, 필터용 인덱스를 데이터 적재 전에 만들면 filter-aware HNSW를 활용할 수 있습니다. 벡터 검색과 필터링이 시스템의 중심이라면 이 모델을 운영 요구사항과 함께 검토할 수 있습니다.

### 5.3. 벤치마크는 어떻게 볼 것인가

두 저장소의 우열을 하나의 벤치마크로 단정할 수는 없습니다. 데이터 차원, 거리 함수, 인덱스 파라미터, 필터 선택도, 동시성, 하드웨어, 목표 recall이 모두 결과를 바꿉니다. 따라서 임의의 공개 수치보다 실제 문서와 질의에서 exact 결과를 기준으로 비교하는 편이 안전합니다.

> 비교 시에는 같은 질의와 필터, 같은 top-k, 같은 목표 recall을 고정하고 p50/p95/p99 지연, QPS, 인덱스 빌드 시간, 메모리 및 디스크 사용량을 함께 기록합니다. "누가 몇 배 빠르다"는 조건이 빠진 수치만으로는 도입 근거가 될 수 없습니다.  
{: .prompt-warning}

교훈은 특정 수치를 외우는 것이 아니라, **recall, latency, throughput, memory 네 축과 그 trade-off를 이해하고 자기 코퍼스로 측정**하는 것입니다. 벤치마크는 방향을 잡는 참고자료일 뿐, 도입 결정의 근거는 자기 데이터 위에서 나와야 합니다.

---

## 6. 메타데이터 필터링

실무 RAG는 순수 벡터 유사도만으로 검색하지 않습니다. "특정 부서 문서만", "특정 문서 유형만", "사용자가 열람 권한을 가진 문서만" 같은 조건을 벡터 검색에 결합합니다. 이 결합 방식은 제품별로 확인해야 합니다.

- **pgvector**: 공식 문서에 따르면 ANN 인덱스를 쓸 때 `WHERE` 필터는 인덱스 탐색 후 적용될 수 있습니다. 그 결과 후보가 탈락하면 요청한 top-k보다 적은 결과가 나올 수 있습니다. 필터 컬럼용 일반 인덱스, partial index 또는 partitioning을 검토하고, 필요하면 iterative index scan으로 더 탐색합니다.
- **Qdrant**: vector index와 payload index를 별도로 만들고, 필터에 쓸 필드를 payload index로 선언합니다. filter-aware HNSW의 이점을 얻으려면 공식 문서가 권장하는 대로 payload index를 데이터 적재 전에 만들어야 합니다.

이 메타데이터 필터링은 사용자 권한과 문서 접근 권한을 대조해 검색 결과를 제한하는 **권한 기반 retrieval 필터의 토대**이기도 합니다. 권한 필터가 걸린 대표 질의에서 결과 수, recall, 다른 테넌트 문서 노출 여부를 별도로 검증해야 합니다. 접근제어 관점의 상세한 설계는 [5편](/posts/rag-security-and-access-control/)에서 다룹니다.

---

## 7. 인덱스와 저장소 선택 가이드

정답은 하나가 아니며, 다음 요소를 함께 놓고 판단합니다.

- **정답 기준**: 먼저 exact 검색으로 대표 질의의 정답 이웃을 만들고, 필요한 recall과 top-k를 정합니다.
- **지연과 메모리 예산**: HNSW와 IVFFlat의 파라미터를 바꾸며 p95/p99 지연, QPS, 메모리와 디스크 사용량을 같은 조건에서 측정합니다.
- **필터와 격리**: 문서 권한과 테넌트 필터가 결과 수와 recall을 낮추지 않는지 확인합니다. 이 항목은 보안 요구사항이므로 성능 테스트에서 빠뜨리면 안 됩니다.
- **운영 경계**: 기존 PostgreSQL의 트랜잭션과 조인이 중요한지, 또는 벡터와 payload 필터링을 독립적으로 확장하고 운영해야 하는지를 먼저 결정합니다.
- **갱신 후 재검증**: 코퍼스 또는 임베딩 모델이 바뀌면 이전 튜닝 값을 신뢰하지 말고, exact 기준 recall과 필터 동작을 다시 측정합니다.

검색 정확도 자체를 더 끌어올리는 방법인 hybrid search와 reranking은 [4편](/posts/rag-hybrid-search-and-reranking/)에서 이어서 다룹니다.

---

## 8. 시리즈 맵

- [(1) RAG 개념과 파이프라인 Overview](/posts/rag-overview-concept-and-pipeline/)
- [(2) 청킹/임베딩과 Contextual Retrieval](/posts/rag-chunking-embedding-contextual-retrieval/)
- **(3) 벡터 DB와 인덱스** (현재 글)
- [(4) 검색 정확도: Hybrid Search + Reranking](/posts/rag-hybrid-search-and-reranking/)
- [(5) 보안과 접근제어(DevSecOps)](/posts/rag-security-and-access-control/)
- [(6) 지연 최적화와 평가](/posts/rag-latency-optimization-and-evaluation/)
- [(7) LLM API 연동과 고급](/posts/rag-llm-api-and-advanced/)

---

## 9. Reference

- [pgvector - GitHub](https://github.com/pgvector/pgvector)
- [Qdrant Docs - Indexing](https://qdrant.tech/documentation/concepts/indexing/)
- [Qdrant Docs - Filtering](https://qdrant.tech/documentation/concepts/filtering/)
- [arXiv - Efficient and robust approximate nearest neighbor search using HNSW](https://arxiv.org/abs/1603.09320)
- [Faiss - Indexes](https://github.com/facebookresearch/faiss/wiki/Faiss-indexes)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
