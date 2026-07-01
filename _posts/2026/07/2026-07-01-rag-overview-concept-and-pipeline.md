---
title: RAG 개념과 파이프라인 Overview - LLM의 한계와 검색 증강 파이프라인 [RAG 1]
date: 2026-07-01 11:00:00 +0900
author: kkamji
categories: [AI]
tags: [rag, llm, retrieval-augmented-generation, embedding, vector-search, reranking, hallucination, ai]     # TAG names should always be lowercase
comments: true
image:
  path: /assets/img/kkam-img/kkam.webp
---

사내 정책 문서를 찾는 상황을 떠올려 봅니다. "출장 규정에서 숙박비 한도가 얼마였지", "보안 정책상 외부 저장소 사용이 허용되는가" 같은 질문의 답은 대부분 어딘가의 문서에 이미 존재합니다. 하지만 문서는 PDF, Confluence 위키, 사내 위키 등 여러 곳에 흩어져 있고, 일반 LLM에게 물으면 그 문서를 본 적이 없으니 그럴듯하지만 틀린 답을 내놓습니다. 이 문제를 푸는 대표적인 방법이 RAG(Retrieval-Augmented Generation)입니다. 이번 글에서는 RAG가 왜 필요한지, 전체 파이프라인이 어떻게 구성되는지, 그리고 실무에서 RAG를 만들 때 관통하는 세 가지 설계 목표(정확도, 지연, 보안)를 살펴봅니다.

> - LLM은 학습 시점 이후 지식(knowledge cutoff)과 조직 내부 문서를 모르며, 모를 때도 **그럴듯하게 지어내는(hallucination)** 경향이 있습니다.  
> - RAG는 질문 시점에 **관련 문서를 검색해 프롬프트에 함께 넣어** 생성하는 구조로, 모델을 재학습하지 않고 최신/내부 지식을 반영합니다.  
> - 파이프라인은 오프라인 **인덱싱(ingestion -> chunking -> embedding -> indexing)**과 온라인 **질의(retrieval -> reranking -> generation)** 두 단계로 나뉩니다.  
> - 실무 RAG의 품질은 세 축의 균형입니다: **정확도(faithfulness)**, **지연(latency)**, 그리고 사내 문서라면 반드시 따라오는 **보안/접근제어(DevSecOps)**.  
> - 이 글은 RAG 시리즈의 첫 글로, 개념과 큰 그림을 잡는 데 집중합니다.  
{: .prompt-info}

---

## 1. LLM만으로는 왜 부족한가

RAG를 이해하려면 먼저 LLM 단독 사용의 한계를 짚어야 합니다. LLM은 방대한 텍스트로 사전 학습된 모델이라 일반 지식과 언어 능력은 뛰어나지만, 사내 정책 문서 검색이라는 목적에서는 세 가지 구조적 한계가 있습니다.

### 1.1. Knowledge Cutoff (학습 시점의 한계)

모델은 특정 시점까지의 데이터로 학습됩니다. 그 이후에 개정된 정책이나, 애초에 학습 데이터에 포함되지 않은 조직 내부 문서는 모델의 파라미터 안에 존재하지 않습니다. 즉 "우리 회사의 최신 출장 규정"은 아무리 좋은 LLM이라도 알 수 없습니다.

### 1.2. Hallucination (환각)

더 큰 문제는, 모델이 모른다고 대답하는 대신 **그럴듯한 문장을 지어낸다**는 점입니다. 정책 문서 검색처럼 정확성이 중요한 맥락에서 hallucination은 치명적입니다. 존재하지 않는 조항을 실제 규정인 것처럼 제시하면, 사용자는 잘못된 정보를 신뢰하게 됩니다.

### 1.3. 근거(출처)의 부재

LLM이 답을 생성해도 "그 답이 어느 문서 몇 페이지에 근거하는가"를 제시하지 못하면, 사용자는 답을 검증할 수 없습니다. 정책/규정 도메인에서는 답 자체보다 **출처를 함께 제시하는 것(grounding)**이 신뢰의 전제가 됩니다.

---

## 2. RAG의 기본 아이디어

RAG는 이 한계들을 "모델을 다시 학습시키지 않고" 해결합니다. 핵심 아이디어는 단순합니다. 질문이 들어오면 그 질문과 관련된 문서를 **먼저 검색**하고, 검색된 문서를 질문과 함께 프롬프트에 넣어 LLM이 **그 문서에 근거해 답을 생성**하도록 하는 것입니다.

비유하자면, 닫힌 책 시험(closed-book)을 보던 모델에게 열린 책 시험(open-book)을 보게 하는 것과 같습니다. 모델은 모든 것을 외우고 있을 필요 없이, 필요한 순간에 관련 페이지를 펼쳐 보고 답하면 됩니다. 이 구조 덕분에 RAG는 다음을 얻습니다.

- **최신성**: 인덱스만 갱신하면 최신 정책이 즉시 반영됩니다(재학습 불필요).
- **근거 제시**: 검색된 문서가 곧 출처이므로 citation을 붙일 수 있습니다.
- **환각 억제**: 모델이 제공된 문서 범위 안에서 답하도록 유도해 지어내기를 줄입니다.

### 2.1. RAG vs Fine-tuning

지식을 주입하는 다른 방법으로 fine-tuning이 있습니다. 둘은 경쟁 관계라기보다 목적이 다릅니다.

| 구분              | RAG                                  | Fine-tuning                          |
| :---------------- | :----------------------------------- | :----------------------------------- |
| **주입 대상**     | 지식(사실, 문서 내용)                | 행동/형식/톤, 도메인 표현            |
| **최신화**        | 인덱스 갱신으로 즉시 반영            | 재학습 필요                          |
| **출처 제시**     | 가능(검색 문서가 근거)              | 어려움(파라미터에 녹아듦)            |
| **접근제어**      | 검색 단계에서 문서별 권한 필터 가능 | 모델에 학습되면 분리/회수 어려움     |
| **초기 비용**     | 상대적으로 낮음                      | 상대적으로 높음                      |

사내 정책 문서처럼 **자주 바뀌고, 출처가 중요하며, 문서별 접근 권한이 다른** 데이터는 RAG가 자연스러운 선택입니다. 실무에서는 도메인 표현 학습(fine-tuning)과 지식 주입(RAG)을 함께 쓰기도 합니다.

---

## 3. RAG 파이프라인 전체 흐름

RAG는 크게 두 단계로 나뉩니다. 하나는 미리 문서를 검색 가능한 형태로 준비하는 **오프라인 인덱싱**, 다른 하나는 사용자 질문에 답하는 **온라인 질의**입니다. 두 단계는 벡터 DB를 공유합니다. 인덱싱이 벡터를 써 넣고, 질의가 그 벡터를 읽어 검색합니다.

![RAG end-to-end 파이프라인 - 오프라인 인덱싱(Sources -> Ingestion & Parsing -> Chunking -> Embedding -> Vector DB)과 온라인 질의(User Query -> Query Embedding -> Retrieval -> Reranking -> LLM Generation -> Answer + Citation)이 Vector DB를 공유하는 구조](/assets/img/ai/rag-01-pipeline.webp)

### 3.1. 오프라인 인덱싱 (ingestion -> chunking -> embedding -> indexing)

문서를 검색 가능한 벡터로 변환해 저장소에 넣는 준비 과정입니다. 사용자 질문과 무관하게 미리 수행합니다.

- **Ingestion(수집/파싱)**: PDF, Confluence, 위키 등 다양한 소스에서 원문 텍스트를 추출합니다. 포맷마다 파싱 난이도가 다르며(표/레이아웃이 많은 PDF는 특히 까다롭습니다), 이 단계에서 문서별 메타데이터(부서, 접근 권한, 개정일 등)도 함께 수집합니다.
- **Chunking(분할)**: 문서를 검색 단위인 청크(chunk)로 쪼갭니다. 너무 크면 관련 없는 내용이 섞여 검색 정확도가 떨어지고, 너무 작으면 문맥이 끊깁니다. 청크 크기와 전략은 검색 품질을 좌우하는 핵심 변수입니다(2편에서 상세히 다룹니다).
- **Embedding(임베딩)**: 각 청크를 의미를 담은 고차원 벡터로 변환합니다. 의미가 비슷한 텍스트는 벡터 공간에서 가깝게 위치하므로, 이후 "의미 기반 검색"이 가능해집니다.
- **Indexing(색인)**: 임베딩 벡터를 벡터 데이터베이스에 저장하고, 빠른 유사도 검색을 위한 인덱스(HNSW/IVF 등)를 구성합니다(3편에서 다룹니다).

### 3.2. 온라인 질의 (retrieval -> reranking -> generation)

사용자 질문이 들어온 시점에 실시간으로 동작하는 과정입니다.

- **Retrieval(검색)**: 질문도 같은 임베딩 모델로 벡터화한 뒤, 벡터 DB에서 의미적으로 가까운 청크 상위 K개를 가져옵니다. 여기에 키워드 검색(BM25)을 결합한 hybrid search가 정확도를 높입니다(4편).
- **Reranking(재순위화)**: 1차로 가져온 후보를 더 정밀한 모델(cross-encoder 등)로 다시 정렬해, 정말 관련 있는 청크를 상위로 끌어올립니다. 정확도를 크게 올리지만 지연이 추가되는 trade-off가 있습니다(4편).
- **Generation(생성)**: 최종 선별된 청크를 질문과 함께 프롬프트에 넣어 LLM이 답을 생성합니다. 이때 답이 제공된 문서에 근거하도록 유도하고, 출처(citation)를 함께 반환하도록 구성합니다(7편).

### 3.3. 두 단계를 한눈에

| 단계          | 시점       | 하는 일                                  | 주로 결정하는 것            |
| :------------ | :--------- | :--------------------------------------- | :-------------------------- |
| Ingestion     | 오프라인   | 소스에서 텍스트/메타데이터 추출          | 파싱 품질                   |
| Chunking      | 오프라인   | 검색 단위로 분할                         | 검색 정확도의 토대          |
| Embedding     | 오프라인   | 청크를 의미 벡터로 변환                  | 의미 검색 성능              |
| Indexing      | 오프라인   | 벡터 DB 저장 + 인덱스 구성               | 검색 속도/확장성            |
| Retrieval     | 온라인     | 질문과 가까운 청크 K개 검색              | 재현율(recall)              |
| Reranking     | 온라인     | 후보를 정밀 재정렬                       | 정밀도(precision)           |
| Generation    | 온라인     | 문서 근거로 답 생성 + 출처               | 답변 품질/신뢰              |

---

## 4. 사내 정책 문서라는 관통 예시

이 시리즈는 "사내 정책 문서 검색"을 관통 예시로 삼습니다. 이 도메인이 RAG의 여러 이슈를 한꺼번에 드러내기 때문입니다.

- **혼합 소스**: 정책은 PDF 사규, Confluence 페이지, 위키 등 서로 다른 포맷으로 존재합니다. ingestion/chunking 전략이 포맷마다 달라집니다.
- **정확성이 중요**: 규정을 잘못 답하면 실무 판단이 어긋납니다. 환각 억제와 출처 제시가 필수입니다.
- **접근 권한 분리**: 인사/보안/재무 정책은 열람 권한이 다릅니다. "누가 어떤 문서를 검색할 수 있는가"가 처음부터 설계에 들어와야 합니다.
- **응답 속도**: 사내 도구로 쓰이려면 질문에 빠르게 답해야 합니다. 지연이 크면 아무도 쓰지 않습니다.

이처럼 정확도, 지연, 보안이 동시에 요구되는 점이 이 시리즈가 잡는 세 가지 설계 목표로 이어집니다.

---

## 5. RAG의 세 가지 설계 목표

실무 RAG는 하나의 지표만 좋아서는 쓸 수 없습니다. 서로 당기는 세 축을 균형 있게 맞추는 일입니다.

### 5.1. 정확도 (Accuracy / Faithfulness)

"검색이 관련 문서를 잘 찾았는가"와 "생성된 답이 그 문서에 충실한가(faithfulness)"의 두 층으로 나뉩니다. 검색이 틀리면 아무리 좋은 LLM도 틀린 근거로 답하고, 검색이 맞아도 모델이 문서를 벗어나 지어내면 신뢰할 수 없습니다. 그래서 청킹/hybrid search/reranking으로 검색 품질을 올리고, Ragas 같은 지표로 faithfulness를 측정해 회귀를 막습니다(6편).

### 5.2. 지연 (Latency)

RAG는 검색과 생성을 매 질문마다 수행하므로 단계마다 지연이 쌓입니다. 벡터 검색, reranking, LLM 생성이 각각 시간을 먹고, 특히 reranking처럼 정확도를 올리는 단계는 지연을 늘립니다. 캐싱, 인덱스 튜닝, top-k 조정으로 지연을 줄이되 정확도를 얼마나 희생하는지 함께 봐야 합니다(6편).

### 5.3. 보안 / 접근제어 (DevSecOps)

사내 문서 RAG에서 보안은 부가 기능이 아니라 **1급 설계 제약**입니다. 문서별 권한에 따라 검색 결과를 필터링하고(RBAC/metadata filtering), 민감정보(PII)를 인덱싱 전에 처리하며, 검색된 문서가 프롬프트로 들어오는 특성상 prompt injection과 데이터 유출(exfiltration)을 방어해야 합니다. 이 시리즈가 일반적인 RAG 튜토리얼과 다른 지점이며, 5편에서 비중 있게 다룹니다.

> 정확도를 위한 최적화가 보안과 충돌하기도 합니다. 예를 들어 지연을 줄이려는 캐시가 권한 기반 검색과 충돌해 다른 권한 사용자에게 결과가 새는 경우가 있습니다. 이런 교차 지점은 5편/6편에서 함께 다룹니다.  
{: .prompt-warning}

---

## 6. Naive RAG의 함정

가장 단순한 RAG(문서를 자르고, 임베딩하고, top-k 검색해서, 그대로 프롬프트에 넣기)는 데모로는 잘 동작하지만 실무에서는 금방 한계를 드러냅니다.

- **청킹 시 문맥 손실**: 청크를 쪼개면 각 청크가 원문 어디에 속했는지 맥락이 사라져, 검색이 엉뚱한 청크를 가져옵니다. 이를 보완하는 기법이 Contextual Retrieval입니다(2편).
- **의미 검색만의 한계**: 벡터 검색은 의미는 잘 잡지만 정확한 키워드(제품명, 조항 번호)에는 약합니다. 키워드 검색과 결합한 hybrid search가 필요합니다(4편).
- **순위의 부정확성**: 1차 검색 상위 결과가 항상 가장 관련 있는 것은 아니라, reranking으로 재정렬이 필요합니다(4편).
- **보안 공백**: 권한/PII/injection을 고려하지 않은 RAG는 사내에 그대로 올릴 수 없습니다(5편).

즉 "동작하는 RAG"에서 "정확하고, 빠르고, 안전한 RAG"로 가는 과정이 이 시리즈의 나머지 내용입니다.

---

## 7. 시리즈 맵

이 글은 RAG 시리즈의 첫 글입니다. 앞으로 다음 주제를 이어갈 예정입니다.

- **(1) RAG 개념과 파이프라인 Overview** - LLM 한계, 파이프라인 전체 흐름, 세 가지 설계 목표 (현재 글)
- (2) 청킹/임베딩과 Contextual Retrieval - 청킹 전략, 임베딩 모델 선택, 문맥 손실 보완, 메타데이터 설계
- (3) 벡터 DB와 인덱스 - HNSW/IVF 개념, pgvector vs Qdrant, 메타데이터 필터링
- (4) 검색 정확도 - Hybrid Search(BM25 + dense), RRF 융합, reranking
- (5) 보안과 접근제어(DevSecOps) - RBAC/metadata filtering, PII 처리, prompt injection, 캐시-권한 충돌
- (6) 지연 최적화와 평가 - 캐싱, 인덱스 튜닝, top-k, Ragas로 정확도 회귀 방지
- (7) LLM API 연동과 고급 - citation/grounding, GraphRAG/Agentic RAG

---

## 8. Reference

- [arXiv - Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks](https://arxiv.org/abs/2005.11401)
- [Anthropic - Introducing Contextual Retrieval](https://www.anthropic.com/news/contextual-retrieval)
- [AWS Docs - Protect sensitive data in RAG applications with Amazon Bedrock](https://aws.amazon.com/blogs/machine-learning/protect-sensitive-data-in-rag-applications-with-amazon-bedrock/)
- [OWASP - LLM01:2025 Prompt Injection](https://genai.owasp.org/llmrisk/llm01-prompt-injection/)
- [Ragas Docs - Available Metrics](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
