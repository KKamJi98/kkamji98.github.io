---
title: "Graph engineering 기초 - 루프에서 시스템으로 [AI Agent 2]"
date: 2026-08-27 02:17:00 +0900
author: kkamji
categories: [AI, Agent]
tags: [ai-agent, graph-engineering, ontology, langgraph, multi-agent, study]
comments: true
image:
  path: /assets/img/ai/graph-system-intelligence.webp
---

루프 하나야 잘 돌아간다. 문제는 둘째부터입니다. 코딩 루프는 커밋을 만들고, 검토 루프는 그 커밋을 읽고, 문서 루프는 그 변경을 노트에 남깁니다. 각자의 루프가 각자의 상태를 들고 있으면, 누가 무엇을 했는지 아무도 모르는 상태가 됩니다.

이 지점에서 다루는 대상이 바뀝니다. 루프 하나의 내부가 아니라, 루프와 에이전트와 상태를 어떻게 연결할 것인가. 이 계층을 graph engineering이라고 부릅니다.

> **TL;DR**  
> - graph engineering: 여러 루프, 에이전트, 상태를 그래프 구조로 조직한다  
> - 2026-08 survey(arXiv 2608.21156)가 Model, Individual, System Intelligence로 계층화했다  
> - 다루는 것은 task organization, agent coordination, state management, system evolution  
> - 온톨로지가 공유 어휘 계층으로 붙는다  
{: .prompt-info}

---

## 1. 계층상 위치

2026-08에 공개된 survey(arXiv 2608.21156)는 AI agent 엔지니어링을 세 계층으로 정리합니다.

- Model Intelligence: 학습, 프롬프트, 컨텍스트. 단일 모델의 능력을 다룬다
- Individual Intelligence: 단일 에이전트에 tool, memory, skill, runtime, loop를 붙인다. loop engineering이 여기 있다
- System Intelligence: 태스크와 에이전트, 상태, 진화를 명시적 그래프로 조직한다. graph engineering이 여기 있다

loop engineering이 "하나의 반복을 끝까지 돌게 만드는 것"이라면, graph engineering은 "반복 여러 개가 서로를 물고 돌게 만드는 것"입니다. 개별 지능을 시스템 지능으로 올리는 단계라는 게 survey의 프레임입니다.

---

## 2. 그래프가 조직하는 것

![graph engineering이 시스템 전체를 조직하는 구조](/assets/img/ai/graph-system-intelligence.webp)

survey는 그래프가 조직하는 대상을 네 가지로 정리합니다.

- task organization: 작업을 노드로, 의존성을 엣지로 둔다. 어떤 작업이 어떤 작업을 기다리는지가 구조가 된다
- agent coordination: 이기종 에이전트가 누구에게 무엇을 넘길지 정한다. 코딩 에이전트, 검토 에이전트, 문서 에이전트가 각자 루프를 돌더라도 넘겨주는 지점이 그래프에 있다
- state management: 실행 상태가 어디에 저장되고 누가 읽는지 정한다. 루프가 각자 상태를 들면 시스템이 아니라 병렬 실행일 뿐이다
- system evolution: 시스템 자체가 구조를 바꾸며 성장하는 경로를 다룬다

여기에 온톨로지 엔지니어링이 공유 의미 계층으로 붙습니다. 에이전트마다 "파일", "배포", "완료"를 다르게 부르면 그래프가 흐트러집니다. 용어와 관계를 먼저 합의하는 계층이 온톨로지입니다.

---

## 3. 생태계의 실체

이 관점의 도구들은 이미 크게 자랐습니다.

- LangGraph(4만 스타): 상태 그래프로 에이전트 흐름을 정의한다. 노드가 단계, 엣지가 전이, 상태가 그래프 전체에서 공유된다
- Graphify(11만 스타): 코드베이스와 문서를 쿼리 가능한 지식 그래프로 바꾼다. 검색의 단위가 문장이 아니라 관계가 된다
- Awesome-Graph-Engineering(2026-08): survey를 동반한 리소스 컬렉션. Loop Architecture 항목에 StateFlow, Magentic-One 같은 연구가 정리돼 있다

학술 연구도 축적되고 있습니다. "Stop Hand-Holding Your Coding Agent"는 루프 설계를, "From Agent Loops to Structured Graphs"는 루프에서 그래프로의 스케줄링 이론을 다룹니다. 이름이 마케팅처럼 들려도 그 밑에 패턴의 축적은 실재합니다.

---

## 4. 개인 규모의 그래프

이 관점은 대규모 멀티 에이전트에만 해당하지 않습니다.

wikilink로 노트를 연결한 Obsidian vault는 작은 지식 그래프입니다. 노트가 노드, 링크가 엣지, frontmatter의 태그가 온톨로지의 역할을 합니다. 이 블로그의 발행 파이프라인도 보면 루프(pre-commit 게이트, CI)와 그래프(wiki 노트 연결, study 트랙 의존성)가 같이 있습니다.

개인이 그래프 관점을 취하면 얻는 것은 검색의 질입니다. "이 주제와 연결된 노트"가 "이 키워드를 포함한 노트"보다 정확합니다. 관계가 명시적인 순간 retrieval의 단위가 달라집니다.

---

## 5. 어디까지 신뢰할 수 있나

분리해서 봐야 할 것들이 있습니다.

- 실체의 선행: pre-commit, cron, CI는 이 용어가 생기기 전부터 있었습니다. 용어는 실체를 따라온 것입니다
- 발화 주체의 무게: Claude Code 책임자의 "루프를 쓴다" 발화는 유행어가 아니라 실제 업무 방식의 공개입니다
- 미확인 영역: survey가 2026-08 신규라 피인용과 후속 검증이 축적되지 않았습니다. graph engineering이 안정된 학술 분야로 정착할지는 시간이 필요합니다

지금 단계에서는 "실무 패턴에 붙은 이름"으로 읽고, 도구와 논문은 각자 검증해서 쓰는 것이 정확합니다.

---

## 6. Reference

- [arXiv 2608.21156 - Graph Engineering in the Era of LLM Agents](https://arxiv.org/abs/2608.21156)
- [DEEP-JLU - Awesome-Graph-Engineering](https://github.com/DEEP-JLU/Awesome-Graph-Engineering)
- [LangGraph](https://github.com/langchain-ai/langgraph)
- [Graphify](https://github.com/Graphify-Labs/graphify)
- [arXiv 2604.11378 - From Agent Loops to Structured Graphs](https://arxiv.org/abs/2604.11378)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
