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

[RAG 2편](/posts/rag-chunking-embedding-contextual-retrieval/)에서 문서를 청크로 나누고 임베딩으로 벡터화하는 인덱싱 설계를 살펴봤습니다. 이렇게 만들어진 수백만 개의 벡터에서 질의와 가까운 것을 빠르게 찾으려면 저장소와 인덱스가 필요합니다. 이번 글에서는 벡터 검색의 핵심 문제와 측정 축, 대표 인덱스인 **HNSW와 IVF**의 동작 원리, 그리고 **pgvector와 Qdrant**를 선택 기준 관점에서 살펴봅니다. RAG는 검색이 전체 품질의 상한을 정하므로, 인덱스를 어떻게 고르고 튜닝하느냐가 정확도와 지연, 비용을 동시에 좌우합니다.

> - 정확 검색(exact/brute-force)은 수백만 벡터 규모에서 느려서, 실무는 약간의 recall을 내주고 속도를 얻는 **ANN(Approximate Nearest Neighbor)**을 씁니다.  
> - 벡터 검색은 **recall, latency(특히 p99 tail), throughput(QPS), memory** 네 축의 trade-off로 평가하며, 하나의 수치로 우열을 판단하지 않습니다.  
> - **HNSW**는 그래프 기반으로 높은 recall과 낮은 지연이 강점이지만 메모리를 많이 씁니다. **IVF**는 클러스터 분할로 메모리 효율적이며 nprobe로 recall/latency를 조절합니다.  
> - **pgvector**는 기존 PostgreSQL 운영/트랜잭션/조인과 함께 쓸 수 있는 운영 단순성이, **Qdrant**는 벡터 검색에 특화된 전용 DB라는 점이 강점입니다.  
> - 벤치마크 수치는 환경 의존도가 크므로, 특정 인용값보다 **네 측정 축과 trade-off를 이해하고 자기 데이터로 측정**하는 것이 핵심입니다.  
{: .prompt-info}

---

## 1. 벡터 검색의 문제: exact vs ANN

벡터 검색은 질의 벡터 하나와 가장 가까운(유사도가 높은) 벡터 top-k를 저장소에서 찾는 문제입니다. 가장 단순한 방법은 모든 벡터와 거리를 계산해 정렬하는 정확 검색(exact/brute-force)입니다. 정확한 답을 주지만, 벡터 수가 수백만에 이르면 질의마다 전량을 훑어야 하므로 지연이 크게 늘어납니다.

그래서 실무는 대부분 **ANN(Approximate Nearest Neighbor)**을 사용합니다. ANN은 전량 비교 대신 후보 공간을 좁혀 탐색하는 근사 검색으로, 약간의 recall을 내주고 속도를 크게 얻습니다. 즉 "가장 가까운 k개"를 완벽히 보장하지는 않지만, 대부분의 정답을 훨씬 빠르게 반환합니다. RAG에서는 이 근사가 만들어내는 오차와 속도의 균형을 이해하는 것이 인덱스 선택의 출발점입니다.

---

## 2. 벡터 검색의 측정 축

벡터 검색 성능은 하나의 숫자로 요약되지 않습니다. 서로 맞물려 움직이는 네 축을 함께 봐야 합니다.

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

HNSW는 그래프 기반 ANN 인덱스입니다. 벡터들을 노드로 두고 가까운 벡터끼리 이웃으로 연결한 그래프를 만들되, 이를 **계층 구조**로 쌓습니다. 상위 계층은 노드가 성기게 있어 넓은 영역을 빠르게 건너뛰고, 하위 계층으로 내려갈수록 촘촘해집니다. 질의가 들어오면 최상위 계층에서 시작해 가까운 이웃으로 greedy하게 이동하며 계층을 내려가, 최하위에서 정밀하게 후보를 좁힙니다.

강점은 **높은 recall과 낮은 지연**을 동시에 얻기 쉽다는 점입니다. 대신 그래프 연결과 계층을 모두 메모리에 올려야 해서 **메모리 사용량이 큽니다**. 주요 튜닝 파라미터는 다음과 같습니다.

- **M** (빌드 시): 각 노드가 갖는 이웃 연결 수. 크면 그래프가 촘촘해져 recall이 오르지만 메모리와 빌드 비용이 늘어납니다.
- **ef_construction** (빌드 시): 인덱스를 만들 때 탐색하는 후보 폭. 크면 그래프 품질이 좋아지지만 빌드가 느려집니다.
- **ef_search** (검색 시): 질의 시 탐색하는 후보 폭. 크게 하면 recall이 오르는 대신 지연이 늘어납니다. 질의 시점에 recall과 지연을 조절하는 손잡이입니다.

---

## 4. IVF (Inverted File Index)

IVF는 벡터 공간을 미리 여러 **클러스터(list)**로 나눠 두는 방식입니다. k-means 등으로 벡터를 여러 클러스터로 분할하고, 각 클러스터의 중심(centroid)을 기록합니다. 질의가 들어오면 모든 벡터가 아니라, 질의와 가까운 **nprobe개의 클러스터만** 골라 그 안에서만 비교합니다. 탐색 대상을 크게 줄이므로 빠르고, 그래프를 통째로 올릴 필요가 없어 **메모리 효율적**입니다.

핵심 튜닝 파라미터는 **nprobe**입니다. nprobe가 크면 더 많은 클러스터를 뒤지므로 recall이 오르지만 그만큼 느려지고, 작으면 빠르지만 정답을 놓칠 수 있습니다. 클러스터 분할을 위해 대표 벡터로 **학습(train) 단계가 필요**하다는 점도 HNSW와 다른 특징입니다. 데이터 분포가 학습 시점과 크게 달라지면 클러스터가 편향돼 recall이 떨어질 수 있으므로, 대량 갱신이 잦다면 재학습을 고려해야 합니다.

| 항목            | HNSW                          | IVF                              |
| :-------------- | :---------------------------- | :------------------------------- |
| 구조            | 계층형 그래프                 | 클러스터(list) 분할              |
| 강점            | 높은 recall + 낮은 지연       | 메모리 효율                      |
| 약점            | 메모리 사용 큼                | 학습 필요, 분포 변화에 민감      |
| 검색 손잡이     | ef_search                     | nprobe                           |
| 빌드 특성       | M / ef_construction           | 사전 train(k-means 등)           |

---

![HNSW vs IVF 인덱스 비교 - HNSW는 계층 그래프에서 greedy search로 탐색(높은 recall, 낮은 지연, 높은 메모리), IVF는 centroids로 클러스터를 나눠 top-nprobe list만 probe(메모리 효율, nprobe 튜닝)](/assets/img/ai/rag-03-hnsw-vs-ivf.webp)

---

## 5. pgvector vs Qdrant

인덱스 알고리즘만큼 중요한 것이 저장소 선택입니다. 대표적인 두 갈래를 선택 기준 관점에서 비교합니다.

### 5.1. pgvector

pgvector는 **PostgreSQL 확장(extension)**입니다. 기존 Postgres 테이블에 벡터 타입 컬럼을 추가하고, 그 위에 인덱스를 얹어 벡터 검색을 수행합니다. 가장 큰 강점은 **운영 단순성**입니다. 이미 Postgres를 쓰고 있다면 별도 시스템을 도입하지 않고, 기존 트랜잭션과 조인, 기존 관계형 데이터와 벡터를 한 곳에서 함께 다룰 수 있습니다. 메타데이터를 일반 컬럼으로 두고 SQL로 필터링하거나, 기존 애플리케이션 데이터와 벡터를 조인하는 것도 자연스럽습니다. 운영 스택을 늘리지 않고 RAG를 시작하려는 팀에 잘 맞습니다.

### 5.2. Qdrant

Qdrant는 벡터 검색을 위해 처음부터 만들어진 **전용(purpose-built) 벡터 DB**입니다. 벡터 인덱싱, 메타데이터 페이로드 기반 필터링, 대규모 벡터 컬렉션 관리 등 벡터 검색에 특화된 기능과 최적화를 제공합니다. 벡터 검색이 시스템의 중심이고 대규모/고성능 요구가 명확한 경우, 전용 DB의 특화된 동작이 이점이 됩니다.

### 5.3. 벤치마크는 어떻게 볼 것인가

두 저장소의 우열을 하나의 벤치마크로 단정할 수는 없습니다. 예를 들어 50M 규모의 Cohere 768차원 데이터셋에서 99% recall을 목표로 한 특정 벤치마크에서는, Qdrant의 tail latency가 Postgres보다 낮게 측정된 사례가 있습니다(p99 약 38.71ms vs 74.60ms). 다만 이는 특정 인스턴스 사양과 recall 목표에 강하게 의존하는 단일 벤치 환경의 결과입니다.

> **throughput(QPS)** 우열은 벤치마크마다 상충하는 결과가 있어 결론을 보류합니다. "누가 몇 배 빠르다" 식의 수치를 그대로 인용하는 것은 위험하며, 자기 데이터와 recall 목표로 직접 측정한 값만 신뢰합니다.  
{: .prompt-warning}

교훈은 특정 수치를 외우는 것이 아니라, **recall/latency/throughput/memory 네 축과 그 trade-off를 이해하고 자기 코퍼스로 측정**하는 것입니다. 벤치마크는 방향을 잡는 참고자료일 뿐, 도입 결정의 근거는 자기 데이터 위에서 나와야 합니다.

---

## 6. 메타데이터 필터링

실무 RAG는 순수 벡터 유사도만으로 검색하지 않습니다. "특정 부서 문서만", "특정 문서 유형만", "사용자가 열람 권한을 가진 문서만" 같은 조건을 벡터 검색에 결합합니다. 이때 필터를 언제 적용하느냐에 따라 두 방식으로 갈립니다.

- **pre-filter**: 먼저 메타데이터 조건으로 후보를 좁힌 뒤 그 안에서 벡터 검색을 합니다. 필터가 강하게 걸리면 탐색 대상이 줄어 정확하지만, ANN 인덱스와 필터를 결합하는 구현이 까다로울 수 있습니다.
- **post-filter**: 벡터 검색으로 top-k를 먼저 뽑은 뒤 메타데이터 조건으로 걸러냅니다. 구현은 단순하지만, 필터에 걸려 상당수가 탈락하면 최종 결과 수가 부족해질 수 있습니다.

둘은 정확도와 결과 충족도, 구현 복잡도에서 trade-off를 가지며, 저장소마다 지원 방식이 다릅니다. 이 메타데이터 필터링은 사용자 권한과 문서 접근 권한을 대조해 검색 결과를 제한하는 **권한 기반 retrieval 필터의 토대**이기도 합니다. 접근제어 관점의 상세한 설계는 [5편](/posts/rag-security-and-access-control/)에서 다룹니다.

---

## 7. 인덱스와 저장소 선택 가이드

정답은 하나가 아니며, 다음 요소를 함께 놓고 판단합니다.

- **데이터 규모**: 수십만 수준이면 인덱스 선택의 영향이 작지만, 수백만 이상으로 커질수록 recall/지연/메모리 trade-off가 뚜렷해집니다.
- **recall 목표**: 높은 recall이 필수라면 HNSW가 유리한 경우가 많고, 어느 정도의 recall을 메모리 절감과 맞바꿀 수 있다면 IVF가 대안이 됩니다.
- **메모리 예산**: 메모리를 넉넉히 쓸 수 있으면 HNSW, 비용을 아껴야 하면 IVF 쪽을 검토합니다.
- **갱신 빈도**: 대량 갱신이 잦다면 학습이 필요한 IVF는 분포 변화에 민감하므로 재학습 전략을 고려합니다.
- **운영 스택**: 이미 PostgreSQL을 운영 중이라면, 새 시스템을 늘리지 않고 pgvector로 시작하는 것도 충분히 합리적인 선택입니다. 벡터 검색이 시스템의 중심이고 대규모 특화 요구가 명확해지면 전용 DB를 검토합니다.

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
- [arXiv - Efficient and robust approximate nearest neighbor search using HNSW](https://arxiv.org/abs/1603.09320)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
