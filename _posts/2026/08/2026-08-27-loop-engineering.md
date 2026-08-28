---
title: "Loop engineering 기초 - prompt, context, loop [AI Agent 1]"
date: 2026-08-27 01:41:00 +0900
author: kkamji
categories: [AI, Agent]
tags: [ai-agent, loop-engineering, prompt-engineering, context-engineering, claude-code, study]
comments: true
image:
  path: /assets/img/ai/agent/loop-engineering.webp
---

"Boris Cherny가 프롬프트를 안 쓴다더라"는 이야기가 커뮤니티에 돌았습니다. Anthropic Claude Code를 이끄는 사람이 자기 제품에 프롬프트를 안 붙인다는 말이니 모순처럼 들립니다. 원문을 찾아보면 모순이 아니라 방향 전환에 대한 선언입니다.

> "I don't prompt Claude anymore. I have loops running that prompt Claude and figuring out what to do. My job is to write loops." (Boris Cherny, Addy Osmani 글에서 인용)  

프롬프트를 쓰지 않는 게 아니라, 프롬프트를 대신 써 주는 시스템을 짜는 겁니다. 이 글은 이 방식을 부르는 이름인 loop engineering이 어떤 계층에 놓이는지, 그리고 루프 하나가 어떻게 생겼는지를 정리합니다.

> **TL;DR**  
> - loop engineering: 에이전트를 대신 프롬프트하는 반복 시스템을 설계한다  
> - 계층 순서는 prompt, context, loop. 다루는 단위가 문장에서 작업으로 커진다  
> - 루프의 심장은 검증 단계다. 검증 없는 루프는 무한 반복기다  
> - pre-commit, cron, CI가 이미 같은 뼈대로 돌고 있다  
{: .prompt-info}

---

## 1. 계층 구조

![AI agent engineering의 계층, prompt에서 graph까지](/assets/img/ai/agent-eng-layer-ladder.webp)

같은 에이전트를 다루는 일이라도 무엇을 설계 대상으로 삼는지에 따라 층이 나뉩니다.

- prompt engineering: 한 번의 지시문을 다듬는다. 질문 하나와 답 하나의 품질이 대상이다
- context engineering: 모델이 매 턴 무엇을 보게 할지 고른다. 검색, 메모리, 문서 주입이 여기 온다
- loop engineering: 지시를 대신 수행하는 반복 시스템을 만든다. 사람이 프롬프트하는 대신 시스템이 프롬프트한다

앞의 두 층은 모델에게 무엇을 말할지, 무엇을 보여줄지를 다룹니다. loop engineering부터는 대상이 바뀝니다. 모델이 아니라 모델을 부르는 절차가 설계 대상이 됩니다. 뒤로 갈수록 다루는 단위가 문장에서 작업으로 커지는 이유입니다.

---

## 2. 루프의 정의

루프는 목적을 정의해두면 AI가 완료까지 스스로 반복하는 재귀적 목표입니다. Addy Osmani의 정의가 이 구조를 압축합니다.

> "Loop engineering is replacing yourself as the person who prompts the agent. You design the system that does it instead."  

Peter Steinberger의 표현도 같은 방향을 가리킵니다. "코딩 에이전트에게 프롬프트하지 말아야 한다. 에이전트를 프롬프트하는 루프를 설계해야 한다."

여기서 중요한 점은 루프 설계가 프롬프트 작성보다 어렵다는 것입니다. Osmani도 같은 글에서 이를 인정합니다. 프롬프트 하나는 그 순간의 맥락에서 판단하면 되지만, 루프는 사람이 자리를 비운 사이에 반복됩니다. 판단 기준을 미리 코드로 박아둬야 합니다.

---

## 3. 루프 하나의 해부

![한 개의 agent loop 구성](/assets/img/ai/loop-anatomy.webp)

한 바퀴의 루프는 보통 다섯 단계로 묘사됩니다.

- find: 일거리를 찾는다. 백로그, 이슈, 코드 변경 감지가 입력이다
- hand out: 에이전트에게 범위를 정해 넘긴다. 맥락과 완료 조건이 함께 간다
- verify: 테스트와 게이트로 검증한다. 루프의 심장이다
- record: 결과를 기록한다. 다음 판단의 입력이 된다
- decide next: 계속할지 멈출지 판단한다. 다시 일거리를 만들면 루프가 된다

검증이 심장인 이유는 나머지 네 단계가 모두 검증을 믿고 자동화되기 때문입니다. 검증 없는 루프는 그냥 무한 반복기이고, 사람이 계속 지켜봐야 하면 루프가 아니라 채팅입니다.

---

## 4. 루프는 이미 주변에 있다

일상적인 개발 환경에도 이미 루프가 있습니다. 형태만 낯설 뿐입니다.

- pre-commit 게이트: 커밋을 감지하고 포매터와 검사기를 돌리고 실패하면 되돌린다. 사람이 매 커밋을 검사하지 않는다
- cron 브리핑: 정해진 시간에 수집하고 요약하고 채널로 보낸다. 사람이 매일 명령하지 않는다
- CI 파이프라인: push를 감지하고 빌드와 테스트를 돌리고 결과를 알린다

공통점은 세 가지입니다. 시작 조건이 자동이고, 판정 기준이 코드로 고정돼 있고, 결과가 기록됩니다. Boris Cherny의 "루프를 쓴다"는 말도 특별한 도구 이야기가 아니라, 이 구조를 코딩 에이전트에 적용한다는 뜻입니다.

Claude Code의 hooks와 스킬 파일, Hermes의 cron과 pre-commit 게이트도 같은 뼈대입니다. 중요한 건 도구 이름이 아니라 판정을 코드에 두느냐입니다.

루프가 여러 개 모이고 그 사이의 연결이 문제가 되면 다음 계층이 됩니다. 여러 루프와 에이전트, 상태를 그래프로 조직하는 graph engineering은 다음 글에서 다룹니다.

---

## 5. Reference

- [Addy Osmani - Loop Engineering](https://addyosmani.com/blog/loop-engineering/)
- [cobusgreyling - loop-engineering](https://github.com/cobusgreyling/loop-engineering)
- [arXiv 2607.00038 - Stop Hand-Holding Your Coding Agent](https://arxiv.org/abs/2607.00038)
- [arXiv 2607.01641 - When Agents Do Not Stop](https://arxiv.org/abs/2607.01641)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
