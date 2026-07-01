---
title: RAG LLM API 연동과 고급 기법 - Citation, GraphRAG, Agentic RAG [RAG 7]
date: 2026-07-01 14:00:00 +0900
author: kkamji
categories: [AI]
tags: [rag, citation, grounding, graphrag, agentic-rag, llm-api, ai]     # TAG names should always be lowercase
comments: true
image:
  path: /assets/img/kkam-img/kkam.webp
---

[RAG 1편](/posts/rag-overview-concept-and-pipeline/)부터 [6편](/posts/rag-latency-optimization-and-evaluation/)까지 검색 파이프라인을 인덱싱, 벡터 DB, 검색 정확도, 보안, 지연/평가 순으로 살펴봤습니다. 이번 글에서는 검색된 청크를 LLM에 넘겨 답을 만드는 **generation 단계**와, 이 단계에서 출처(citation)를 어떻게 보장하는지를 다룹니다. 이어서 표준 vector RAG를 넘어서는 고급 기법인 **GraphRAG**와 **Agentic RAG**를 정리하고, 사내 정책 문서 RAG 관점에서 어떤 이점과 한계가 있는지 정직하게 짚어봅니다. 마지막 편인 만큼 시리즈를 관통한 원칙도 함께 정리합니다.

> - Generation 단계에서는 검색된 청크가 답의 근거가 되도록(grounding) 프롬프트를 구성하고, 출처(citation)를 함께 반환하게 만드는 것이 정책 RAG 신뢰의 전제입니다.  
> - Claude Citations API는 `citations.enabled=true`로 켜면 서버 측에서 citation을 파싱하고 `cited_text`를 직접 추출해, 반환된 인용이 제공 문서 내 유효 포인터임을 보장합니다(모델이 인용을 지어내는 것 방지).  
> - 단, 이 보장은 인용 포인터/텍스트의 진위이지 모델 해석의 정확성이 아니며, Citations는 structured output과 **동시 사용이 불가**합니다(둘을 함께 켜면 400 error).  
> - GraphRAG는 multi-hop/relational 질의에 강하지만 구축 비용이 크고, 단순 질의는 표준 vector RAG가 동등하거나 우수합니다. 질의를 라우팅하는 hybrid가 현실적입니다.  
> - Agentic RAG는 iterative retrieval/reflection으로 어려운 질의를 다루지만 compute/coordination overhead를 더합니다. 저지연 정책 RAG에서는 지연/비용 trade-off를 측정해 결정해야 합니다.  
{: .prompt-info}

---

## 1. Generation 단계와 컨텍스트 주입

검색이 끝나면 상위 청크들을 질의와 함께 프롬프트에 넣어 LLM에게 답을 생성하게 합니다. 이 단계의 핵심은 두 가지입니다.

- **Grounding**: 모델이 자기 사전 지식이 아니라 **제공된 문서에 근거해** 답하도록 유도합니다. 프롬프트에 "제공된 문서에 없는 내용은 답하지 말고 모른다고 하라" 같은 제약을 명시합니다.
- **Citation**: 답의 각 주장에 **출처를 함께 반환**하게 구성합니다. 정책 문서 RAG에서는 "어느 규정 몇 조에 근거했는가"를 제시하는 것이 신뢰의 전제입니다. 출처 없이 그럴듯한 답만 나오면, 사용자는 그 답을 검증할 수 없습니다.

문제는 프롬프트로 "출처를 붙여라"라고 지시해도, 모델이 출처 자체를 그럴듯하게 지어낼(hallucinate) 수 있다는 점입니다. 제공하지 않은 조항 번호를 만들어내거나, 실제와 다른 문장을 인용문으로 제시하는 경우입니다. 이를 API 차원에서 방지하는 기능이 citation 지원입니다.

---

## 2. Claude Citations API

Anthropic의 Claude API는 citation을 서버 측에서 처리하는 기능을 제공합니다. document content block에 `citations.enabled=true`를 설정하면, API가 응답을 여러 text block으로 나누고 인용된 block에는 `citations` 배열을 붙여 반환합니다. 각 citation은 `cited_text`(실제 인용된 원문), `document_index`, `document_title`, 그리고 위치 정보(plain text는 `char_location`의 `start_char_index`/`end_char_index`, PDF는 `page_location`)를 담습니다.

여기서 중요한 보장은, `cited_text`가 **모델의 생성물이 아니라 제공 문서에서 서버가 직접 추출한 값**이라는 점입니다. 반환된 citation은 제공 문서 내의 유효한 포인터를 가지며(deterministic char offset), 따라서 모델이 인용을 지어내는 것을 방지합니다. RAG처럼 출처의 신뢰가 핵심인 시스템에서 이 anti-fabrication 보장은 유용합니다.

RAG 청크를 citation과 함께 넘기는 방식은 목적에 따라 다릅니다.

| 넣는 방식                       | 동작                                    |
| :------------------------------ | :-------------------------------------- |
| plain-text document block       | 문장 단위 인용을 원할 때 각 청크를 넣음 |
| custom content document block   | chunking을 억제하고 원하는 단위로 인용  |
| search_result content block     | source/title 필수, 아래 두 위치로 전달  |

전용 `search_result` content block은 `source`와 `title`이 필수이며, tool_result 내부에 넣으면 동적으로 검색한 결과(dynamic RAG)에, user message의 top-level에 넣으면 미리 가져온 결과(pre-fetched)에 사용합니다.

> Citation이 보장하는 것은 **인용 포인터와 텍스트의 진위(anti-fabrication)**이지, 모델이 그 인용을 올바르게 해석했는지가 아닙니다. 즉 "이 문장은 실제로 문서에 있다"는 보장이지 "이 문장이 질문에 대한 올바른 근거다"라는 보장은 아닙니다.  
{: .prompt-warning}

---

## 3. 중요 제약: Citation과 structured output의 비호환

정책 RAG를 설계할 때 반드시 알아야 할 제약이 있습니다. **Citations는 structured output과 동시에 사용할 수 없습니다.** citation을 켠 채로 출력 포맷(structured output, `output_config.format`)을 지정하면 API가 400 error를 반환합니다.

이유는 두 기능의 출력 구조가 충돌하기 때문입니다. citation은 citation block을 text와 interleave(교차 배치)해야 하는데, structured output이 요구하는 strict JSON schema는 이런 교차 구조를 허용하지 않습니다. 하나의 응답에서 "인용이 붙은 자유 텍스트"와 "고정 스키마 JSON"을 동시에 만들 수 없다는 의미입니다.

정책 문서 RAG에서 흔히 원하는 두 요구, 즉 "출처 인용을 강제하고 싶다"와 "답을 구조화된 JSON으로 받고 싶다"가 정면으로 부딪힙니다. 실무에서는 다음 중 하나를 택해야 합니다.

- 둘 중 하나를 포기한다(citation을 취하고 자유 텍스트를 받거나, 구조화 출력을 취하고 citation을 포기).
- 호출을 분리한다. 예를 들어 1차 호출로 citation이 붙은 답을 받고, 2차 호출로 그 답을 구조화된 JSON으로 정리합니다.

참고로 OpenAI 등 다른 LLM API도 컨텍스트 주입과 프롬프트 구성에 대한 가이드를 제공하므로, 사용하는 provider의 공식 문서에서 grounding/citation 관련 기능을 확인하는 것이 좋습니다.

---

## 4. 고급 기법 - GraphRAG

표준 RAG는 청크를 벡터로 색인하고 유사도로 검색합니다. **GraphRAG**는 다른 접근입니다. 문서에서 엔티티와 관계를 추출해 knowledge graph를 만들고, 검색 시 그래프를 순회(traverse)해 관련 정보를 모읍니다.

GraphRAG의 강점은 **multi-hop/relational 질의**입니다. "A 정책이 B 정책과 어떻게 연결되는가", "이 규정을 바꾸면 어떤 다른 규정이 영향을 받는가"처럼 여러 문서에 걸친 관계를 따라가야 하는 질문에서, 그래프 구조는 표준 vector RAG보다 유리할 수 있습니다.

다만 어느 방식도 일관되게 우월하지는 않습니다. task별로 강점이 갈립니다. 단순 single-hop lookup(하나의 조항만 찾으면 되는 질의)에서는 표준 vector RAG가 GraphRAG와 동등하거나 오히려 우수합니다. 게다가 그래프를 구축하는 preprocessing과 저장 비용이 큽니다.

그래서 현실적인 선택은 전면 GraphRAG가 아니라 **질의를 라우팅하는 hybrid**입니다. 단순한 질의는 vector RAG로, 복잡한 multi-hop 질의는 GraphRAG로 보내는 방식입니다(arXiv:2502.11371). 정책 문서에서는 "여러 정책 간 상충 해석" 같은 cross-document 추론에 잠재적 이점이 있습니다.

---

## 5. 고급 기법 - Agentic RAG

표준 RAG는 검색 -> 생성이 정적이고 선형적입니다. **Agentic RAG**는 autonomous agent를 도입해, 검색 과정을 능동적으로 만듭니다. agent는 iterative retrieval(한 번 검색해 부족하면 다시 검색), planning, reflection(중간 결과를 스스로 평가), 그리고 상황에 맞는 동적 검색 전략 선택을 수행합니다.

한 번의 검색으로 충분하지 않은 어려운 질의에서 이런 능동성은 답 품질을 높입니다. 다만 대가가 있습니다. 특히 multi-agent 구성은 측정 가능한 **compute/coordination overhead**를 더합니다. 추론 호출 횟수와 토큰 사용이 늘고, agent 간 조율 비용이 발생합니다(arXiv:2501.09136).

정적 RAG와 agentic RAG의 차이는 흔히 System 1과 System 2로 비유됩니다. 정적 RAG는 빠르게 반응하는 System 1, agentic RAG는 느리지만 숙고하는 System 2에 해당합니다. 저지연이 중요한 정책 문서 RAG에서는 이 지연/비용 trade-off를 신중히 저울질해야 합니다. 모든 질의에 agent를 붙이면 6편에서 다룬 지연 목표를 지키기 어렵습니다.

---

![Vector RAG vs GraphRAG vs Agentic RAG 비교 - Vector RAG는 Query에서 Retrieve, Generate로 이어지는 선형(single-hop, 빠름), GraphRAG는 Graph Traversal로 multi-hop(구축 비용 큼), Agentic RAG는 plan에서 retrieve, reflect로 도는 Agent Loop(적응적, overhead 큼)](/assets/img/ai/rag-07-rag-variants.webp)

---

## 6. 한계와 미해결 영역

GraphRAG와 Agentic RAG는 연구가 활발한 영역이지만, 사내 정책 문서 RAG의 구체적 요구사항과 어떻게 맞물리는지는 아직 근거가 충분하지 않은 부분이 있습니다.

- **보안/감사와의 정합성**: 5편에서 다룬 multi-tenancy 격리, 감사 로깅 요구사항과 GraphRAG/Agentic RAG가 어떻게 호환되는지는 도메인 직접 근거가 부족합니다. 그래프 순회나 agent의 동적 검색이 접근제어 경계를 넘지 않도록 하는 설계는 추가 검증이 필요합니다.
- **실효 이득의 불확실성**: 정책 문서의 상충 해석에서 GraphRAG가 실제로 얼마나 이득을 주는지, agentic 접근이 비용 대비 답 품질을 얼마나 개선하는지는 자체 코퍼스로 측정하기 전에는 단정하기 어렵습니다.

결론은 명확합니다. 이 기법들의 도입은 유행이 아니라 **비용/지연 대비 이득을 측정한 뒤** 결정해야 합니다. 표준 vector RAG로 목표 정확도가 나온다면, 복잡도를 더할 이유가 없습니다.

---

## 7. 시리즈 마무리

1편부터 7편까지 관통한 원칙을 정리합니다.

- **세 축의 균형**: RAG는 정확도(검색 품질), 지연, 보안을 동시에 만족시켜야 합니다. 하나를 위해 다른 하나를 무너뜨리지 않도록 균형을 잡는 것이 설계의 핵심입니다.
- **자기 데이터로 측정**: 청크 크기, 임베딩, 인덱스 파라미터, top-k, 고급 기법 도입까지 보편 최적값은 없습니다. 자사 코퍼스와 질의로 측정하고 개선하는 루프가 벤치마크 수치보다 우선합니다.
- **보안은 1급 제약**: 사내 정책 문서 RAG는 편의 기능이 아니라 보안을 1급 제약으로 놓고 설계해야 합니다. 접근제어, PII 처리, prompt injection 방어, citation을 통한 검증 가능성을 처음부터 파이프라인에 넣습니다.

RAG는 "검색이 틀리면 생성도 틀린다"는 구조 위에서, 검색 품질을 끌어올리고 그 결과를 안전하고 검증 가능하게 사용자에게 전달하는 일련의 엔지니어링입니다. 이 시리즈가 그 전체 그림을 잡는 데 도움이 되었기를 바랍니다.

---

## 8. 시리즈 맵

- [(1) RAG 개념과 파이프라인 Overview](/posts/rag-overview-concept-and-pipeline/)
- [(2) 청킹/임베딩과 Contextual Retrieval](/posts/rag-chunking-embedding-contextual-retrieval/)
- [(3) 벡터 DB와 인덱스](/posts/rag-vector-database-and-index/)
- [(4) 검색 정확도: Hybrid Search + Reranking](/posts/rag-hybrid-search-and-reranking/)
- [(5) 보안과 접근제어(DevSecOps)](/posts/rag-security-and-access-control/)
- [(6) 지연 최적화와 평가](/posts/rag-latency-optimization-and-evaluation/)
- **(7) LLM API 연동과 고급** (현재 글)

---

## 9. Reference

- [Anthropic Docs - Citations](https://platform.claude.com/docs/en/build-with-claude/citations)
- [Anthropic Docs - Search results](https://platform.claude.com/docs/en/build-with-claude/search-results)
- [arXiv - Retrieval-Augmented Generation with Graphs (GraphRAG)](https://arxiv.org/abs/2502.11371)
- [arXiv - Agentic Retrieval-Augmented Generation: A Survey](https://arxiv.org/abs/2501.09136)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
