---
title: "AI agent 엔지니어링 계층 - loop, graph [AI Agent 1]"
date: 2026-08-24 01:21:00 +0900
author: kkamji
categories: [AI, Agent]
tags: [ai-agent, loop-engineering, graph-engineering, prompt-engineering, context-engineering, claude-code, study]
comments: true
image:
  path: /assets/img/ai/agent-eng-layer-ladder.webp
---

"Boris Cherny가 프롬프트를 안 쓴다더라"는 이야기가 커뮤니티에 돌았습니다. Anthropic Claude Code를 이끄는 사람이 자기 제품에 프롬프트를 안 붙인다는 말이니 모순처럼 들립니다. 원문을 찾아보면 모순이 아니라 방향 전환에 대한 선언입니다.

> "I don't prompt Claude anymore. I have loops running that prompt Claude and figuring out what to do. My job is to write loops." (Boris Cherny, Addy Osmani 글에서 인용)  

프롬프트를 쓰지 않는 게 아니라, 프롬프트를 대신 써 주는 시스템을 짜는 겁니다. 이 글은 이 방향 전환이 속한 계층 구조를 정리하고, loop engineering과 graph engineering이 각각 무엇을 설계 대상으로 삼는지 확인합니다.

> **TL;DR**  
> - loop engineering: 에이전트를 대신 프롬프트하는 반복 시스템을 설계한다  
> - graph engineering: 여러 루프와 에이전트, 상태를 그래프로 연결한다  
> - 계층 순서: prompt, context, loop, graph. 뒤로 갈수록 다루는 단위가 커진다  
> - 학술 계열은 2026-08 survey(arXiv 2608.21156)가 System Intelligence로 정리했다  
{: .prompt-info}

---

## 1. 계층 구조

![AI agent engineering의 네 계층](/assets/img/ai/agent-eng-layer-ladder.webp)

같은 에이전트를 다루는 일이라도 무엇을 설계 대상으로 삼는지에 따라 층이 나뉩니다.

- prompt engineering: 한 번의 지시문을 다듬는다. 질문 하나와 답 하나의 품질이 대상이다
- context engineering: 모델이 매 턴 무엇을 보게 할지 고른다. 검색, 메모리, 문서 주입이 여기 온다
- loop engineering: 지시를 대신 수행하는 반복 시스템을 만든다. 사람이 프롬프트하는 대신 시스템이 프롬프트한다
- graph engineering: 여러 루프와 에이전트, 상태를 그래프 구조로 연결해 시스템 하나로 동작하게 한다

뒤로 갈수록 다루는 단위가 문장에서 작업으로, 작업에서 조직으로 커집니다. 2026-08에 공개된 survey(arXiv 2608.21156)는 이를 Model Intelligence, Individual Intelligence, System Intelligence의 진화로 정리하고, loop 설계는 Individual 단계에, 그래프 구조 조직화는 System 단계에 둡니다.

---

## 2. loop engineering

![한 개의 agent loop 구성](/assets/img/ai/loop-anatomy.webp)

루프는 목적을 정의해두면 AI가 완료까지 스스로 반복하는 재귀적 목표입니다. Addy Osmani의 정의가 이 구조를 압축합니다.

> "Loop engineering is replacing yourself as the person who prompts the agent. You design the system that does it instead."  

한 바퀴의 루프는 보통 다섯 단계로 묘사됩니다. 일거리를 찾고(find), 에이전트에게 범위를 정해 넘기고(hand out), 테스트와 게이트로 검증하고(verify), 결과를 기록하고(record), 계속할지 멈출지 판단합니다(decide next). 마지막 판단이 다시 일거리를 만들면 루프가 됩니다.

Peter Steinberger의 표현도 같은 방향을 가리킵니다. "코딩 에이전트에게 프롬프트하지 말아야 한다. 에이전트를 프롬프트하는 루프를 설계해야 한다."

여기서 중요한 점은 루프 설계가 프롬프트 작성보다 어렵다는 것입니다. Osmani도 같은 글에서 이를 인정합니다. 프롬프트 하나는 그 순간의 맥락에서 판단하면 되지만, 루프는 사람이 자리를 비운 사이에 반복됩니다. 그래서 검증 단계가 루프의 심장이 되고, 검증 없는 루프는 그냥 무한 반복기입니다.

---

## 3. loop가 실제로 생기는 모습

일상적인 개발 환경에도 이미 루프가 있습니다. 형태만 낯설 뿐입니다.

- pre-commit 게이트: 커밋을 감지하고 포매터와 검사기를 돌리고 실패면 되돌린다. 사람이 매 커밋을 검사하지 않는다
- cron 브리핑: 정해진 시간에 수집하고 요약하고 채널로 보낸다. 사람이 매일 명령하지 않는다
- CI 파이프라인: push를 감지하고 빌드와 테스트를 돌리고 결과를 알린다

공통점은 세 가지입니다. 시작 조건이 자동이고, 판정 기준이 코드로 고정돼 있고, 결과가 기록됩니다. Boris Cherny의 "루프를 쓴다"는 말도 특별한 도구 이야기가 아니라, 이 구조를 코딩 에이전트에 적용한다는 뜻입니다.

Claude Code의 hooks와 스킬 파일, Hermes의 cron과 pre-commit 게이트도 같은 뼈대입니다. 중요한 건 도구 이름이 아니라 판정을 코드에 두느냐입니다.

---

## 4. graph engineering

루프가 하나의 사이클이라면, graph engineering은 사이클 여러 개와 그 사이의 연결을 다룹니다. survey(arXiv 2608.21156)는 다음을 그래프가 조직한다고 정리합니다.

- task organization: 작업을 노드로, 의존성을 엣지로
- agent coordination: 이기종 에이전트가 누구에게 무엇을 넘길지
- state management: 실행 상태가 어디에 저장되고 누가 읽는지
- system evolution: 시스템 자체가 구조를 바꾸며 성장하는 경로

온톨로지 엔지니어링이 공유 의미 계층으로 붙습니다. 에이전트마다 "파일", "배포", "완료"를 다르게 부르면 그래프가 흐트러지니, 용어와 관계를 먼저 합의한다는 접근입니다.

생태계에서는 이 관점의 도구들이 이미 크게 자랐습니다. LangGraph(4만 스타)는 상태 그래프로 에이전트 흐름을 정의하고, Graphify(11만 스타)는 코드베이스를 쿼리 가능한 지식 그래프로 바꿉니다. 개인 규모의 예로, wikilink로 노트를 연결한 Obsidian vault도 작은 지식 그래프입니다. 이 블로그의 발행 파이프라인도 보면 루프(pre-commit 게이트)와 그래프(wiki 노트 연결, study 트랙)가 같이 있습니다.

---

## 5. 어디까지 신뢰할 수 있나

용어 자체에는 냄새가 섞여 있습니다. "loop engineering"은 마케팅처럼 들릴 수 있고, 실제로 개인 브랜드를 가진 개발자들의 글에서 퍼진 표현입니다. 다만 세 가지는 분리해서 봐야 합니다.

- 발화 주체의 무게: Boris Cherny(Claude Code 책임자)와 Peter Steinberger의 발화는 유행어 수준이 아니라 실제 업무 방식의 공개입니다
- 학술 정리의 존재: 2026-08 survey가 graph engineering을 체계화했고, Loop Architecture 관련 논문들(StateFlow, Magentic-One, "Stop Hand-Holding Your Coding Agent")이 축적돼 있습니다
- 실체의 선행: 위에서 본 pre-commit, cron, CI는 이 용어가 생기기 전부터 있었습니다. 용어는 실체를 따라온 것입니다

반대로 아직 확인할 수 없는 것도 남습니다. survey가 2026-08 신규라 피인용과 후속 검증이 축적되지 않았고, "graph engineering"이 안정된 학술 분야로 정착할지는 시간이 필요합니다. 지금 단계에서는 "실무 패턴에 붙은 이름" 정도로 읽는 것이 정확합니다.

---

## 6. Reference

- [Addy Osmani - Loop Engineering](https://addyosmani.com/blog/loop-engineering/)
- [arXiv 2608.21156 - Graph Engineering in the Era of LLM Agents](https://arxiv.org/abs/2608.21156)
- [DEEP-JLU - Awesome-Graph-Engineering](https://github.com/DEEP-JLU/Awesome-Graph-Engineering)
- [cobusgreyling - loop-engineering](https://github.com/cobusgreyling/loop-engineering)
- [LangGraph](https://github.com/langchain-ai/langgraph)
- [Graphify](https://github.com/Graphify-Labs/graphify)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
