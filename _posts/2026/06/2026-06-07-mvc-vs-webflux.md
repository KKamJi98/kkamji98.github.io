---
title: Spring MVC vs WebFlux - 선택 기준과 트레이드오프
date: 2026-06-07 13:00:00 +0900
author: kkamji
categories: [Programming Language, Java]
tags: [java, spring, webflux, spring-mvc, architecture]
comments: true
image:
  path: /assets/img/spring/spring.webp
---

[Series 3 1편](/posts/reactive-reactor-basics/)에서 리액티브와 Reactor의 기초를, [2편](/posts/spring-webflux-netty-event-loop/)에서 WebFlux의 event loop와 netty direct memory를 봤습니다. 그러면 자연스러운 질문이 남습니다. **그래서 새 서비스에 MVC를 쓸까, WebFlux를 쓸까.** 흥미롭게도 Spring 공식 문서의 답은 "무조건 최신(WebFlux)"이 아니라 의외로 담백합니다. 이번 글에서는 두 모델의 선택 기준과 트레이드오프를, Spring 공식 문서의 권고에 근거해 정리합니다. Series 3의 마무리입니다.

> **TL;DR**  
> - WebFlux가 항상 정답은 아니다. **"잘 동작하는 MVC 앱이면 바꿀 이유가 없다"**가 Spring 공식 권고다.  
> - **의존성으로 판단**한다: 핵심 의존성이 블로킹(JPA/JDBC)이면 MVC가 맞다. 블로킹을 논블로킹 스택에 억지로 끼우면 WebFlux의 이점이 사라진다.  
> - WebFlux는 **고동시성 I/O bound, 스트리밍**, 그리고 논블로킹 스택을 끝까지 적용할 수 있을 때 이득이다.  
> - 큰 팀이라면 **러닝커브**(논블로킹/함수형/선언형)를 고려하고, 불확실하면 MVC로 시작해 `WebClient`만 부분 도입하는 게 안전하다.  
{: .prompt-info}

---

## 1. 두 모델 한눈에 (1-2편 복습)

[Series 1 3편](/posts/spring-mvc-dispatcherservlet/)에서 본 Spring MVC는 **thread-per-request**(동기 블로킹), 2편에서 본 WebFlux는 **event loop**(논블로킹)입니다. 핵심 차이를 한 장으로 정리하면 다음과 같습니다.

![Spring MVC vs WebFlux 비교](/assets/img/spring/spring-13-mvc-vs-webflux.webp)
_왼쪽 MVC(동기/요청당 스레드/블로킹 라이브러리 그대로) vs 오른쪽 WebFlux(논블로킹/적은 고정 스레드/논블로킹 라이브러리 필요). 둘은 우열이 아니라 적합한 상황이 다르다._

표로 다시 보면 이렇습니다.

| 항목                  | Spring MVC                      | Spring WebFlux                     |
| :-------------------- | :------------------------------ | :--------------------------------- |
| **실행 모델**         | 동기 / 명령형(imperative)       | 비동기 / 논블로킹 / 선언형         |
| **스레드**            | 요청당 1개 (수백 개)            | 적은 고정 풀 (CPU 코어 수 수준)    |
| **블로킹 라이브러리** | JPA / JDBC 그대로 사용          | R2DBC / WebClient 등 논블로킹 필요 |
| **적합**              | 대부분의 일반 앱, 디버깅 용이   | 고동시성 I/O bound, 스트리밍       |

---

## 2. Spring 공식의 선택 기준

Spring 레퍼런스의 WebFlux 개요에는 "Applicability"라는 절이 있고, 여기서 Spring 팀이 직접 선택 기준을 제시합니다. 메시지는 한결같이 담백합니다.

**(1) 잘 동작하면 바꾸지 마라.**

> If you have a Spring MVC application that works fine, there is no need to change. Imperative programming is the easiest way to write, understand, and debug code. You have maximum choice of libraries, since, historically, most are blocking.  
> _- Spring Framework Reference, Web on Reactive Stack (Applicability)_  

**(2) 의존성으로 판단하라.** 핵심 의존성이 블로킹(JPA/JDBC)이면 MVC가 맞습니다.

> A simple way to evaluate an application is to check its dependencies. If you have blocking persistence APIs (JPA, JDBC) or networking APIs to use, Spring MVC is the best choice for common architectures at least. It is technically feasible with both Reactor and RxJava to perform blocking calls on a separate thread but you would not be making the most of a non-blocking web stack.  
> _- Spring Framework Reference, Web on Reactive Stack (Applicability)_  

이게 [2편의 황금률](/posts/spring-webflux-netty-event-loop/)과 이어집니다. 블로킹을 `boundedElastic`으로 격리할 수는 있지만, 그건 "탈출구"이지 논블로킹 스택을 제대로 쓰는 게 아닙니다. 블로킹이 핵심이면 처음부터 MVC가 단순합니다.

**(3) 팀과 러닝커브를 고려하라.**

> If you have a large team, keep in mind the steep learning curve in the shift to non-blocking, functional, and declarative programming. A practical way to start without a full switch is to use the reactive `WebClient`. Beyond that, start small and measure the benefits. We expect that, for a wide range of applications, the shift is unnecessary.  
> _- Spring Framework Reference, Web on Reactive Stack (Applicability)_  

"많은 경우 전환은 불필요하다(the shift is unnecessary)"를 프레임워크 제작자가 직접 적어 둔 점이 인상적입니다.

**(4) WebFlux가 빛나는 경우.** 고동시성 I/O bound, 스트리밍, 그리고 가벼운 함수형 엔드포인트입니다.

> If you are interested in a lightweight, functional web framework for use with Java or Kotlin, you can use the Spring WebFlux functional web endpoints. That can also be a good choice for smaller applications or microservices with less complex requirements that can benefit from greater transparency and control.  
> _- Spring Framework Reference, Web on Reactive Stack (Applicability)_  

---

## 3. 결정 가이드

위 기준을 흐름으로 옮기면 다음과 같습니다.

![MVC vs WebFlux 결정 가이드](/assets/img/spring/spring-14-when-to-use.webp)
_기존 MVC가 잘 동작하면 유지. 핵심 의존성이 블로킹이면 MVC. 고동시성 I/O bound/스트리밍이고 논블로킹 스택을 끝까지 적용할 수 있으면 WebFlux. 불확실하면 MVC로 시작해 WebClient만 부분 도입._

핵심은 **"끝까지 논블로킹"**입니다. WebFlux를 골랐다면 DB 접근(R2DBC), 외부 호출(WebClient)까지 논블로킹으로 이어져야 event loop의 이점이 나옵니다. 중간에 블로킹 한 곳이 끼면 그 event loop 스레드가 묶이고, 그 스레드가 담당하던 수많은 커넥션이 함께 느려집니다.

---

## 4. 흔한 오해와 함정

- **"WebFlux가 더 빠르다"는 아니다.** WebFlux의 이점은 단건 응답 속도가 아니라, **같은 자원으로 더 많은 동시 I/O를 버티는 효율**입니다. CPU bound이거나 동시성이 낮은 워크로드에서는 이점이 거의 없고, 오히려 복잡도와 디버깅 비용만 늘 수 있습니다.
- **부분 도입이 현실적이다.** 전면 전환 대신 외부 호출 클라이언트만 논블로킹 `WebClient`로 바꾸는 것은 MVC 앱에서도 가능합니다. Spring 문서도 이를 "full switch 없이 시작하는 실용적 방법"으로 권합니다.
- **블로킹을 섞는 게 최악이다.** WebFlux 위에서 블로킹 JDBC를 그대로 호출하면 MVC보다 못한 결과(event loop 마비)가 납니다. 논블로킹을 끝까지 못 갈 상황이면 차라리 MVC가 안전합니다.

> 정리하면, WebFlux는 "더 좋은 MVC"가 아니라 **다른 트레이드오프를 가진 다른 도구**입니다. 고동시성 I/O와 논블로킹 스택 전반을 감당할 준비가 됐을 때 이득이 큽니다.  
{: .prompt-tip}

---

## 5. Series 3 마무리

세 편에 걸쳐 [리액티브/Reactor의 기초](/posts/reactive-reactor-basics/) -> [WebFlux event loop와 off-heap](/posts/spring-webflux-netty-event-loop/) -> MVC vs WebFlux 선택 기준을 봤습니다. 요청이 흐르는 길(Series 1), JVM과 메모리(Series 2)에 이어 동시성 모델까지 두 갈래(thread-per-request / event loop)를 정리한 셈입니다.

이제 커리큘럼의 조각이 대부분 모였습니다. 남은 **capstone**에서는 이 전부 - 요청 처리, JVM 메모리, GC, 동시성 모델 - 를 하나의 실전 사례로 회수합니다. **서비스명이나 실측치 없이, 일반화된 메커니즘과 재구성된 예시로만** 다룹니다.

DevSecOps 비유: 도구 선택의 원칙은 인프라와 똑같습니다. "최신이라서" 또는 "남들이 써서"가 아니라 **워크로드 특성(I/O bound인가, 동시성이 큰가, 팀이 감당하는가)에 맞춰** 고르고, 불확실하면 기본(MVC)에서 시작해 측정하며 좁혀갑니다. nginx 이벤트 루프 대 동기 워커, 큐 선택, 캐시 도입과 같은 결정에서 늘 적용되는 기준입니다.

---

## 6. 참고 자료

- Spring Framework Reference - Web on Reactive Stack (Applicability: MVC vs WebFlux 선택 기준): <https://docs.spring.io/spring-framework/reference/web/webflux/new-framework.html>
- Spring Framework Reference - Web on Servlet Stack (Spring MVC): <https://docs.spring.io/spring-framework/reference/web/webmvc.html>

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
