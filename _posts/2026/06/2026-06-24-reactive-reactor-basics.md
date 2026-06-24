---
title: 리액티브 프로그래밍과 Reactor 기초 - Reactive Streams, backpressure, Mono/Flux
date: 2026-06-24 12:00:00 +0900
author: kkamji
categories: [Programming Language, Java]
tags: [java, spring, webflux, reactor, reactive-streams, backpressure]
comments: true
image:
  path: /assets/img/spring/spring.webp
---

[Series 1 3편](/posts/spring-mvc-dispatcherservlet/)에서 Spring MVC는 thread-per-request, 즉 "요청당 워커 스레드 1개가 I/O를 기다리는 동안에도 묶여 있다"고 했습니다. Series 3은 그 블로킹을 **하지 않는** 다른 모델 - 리액티브(WebFlux) - 을 다룹니다. 그 첫걸음으로 이번 편은 리액티브의 개념과 Reactor의 기초를 잡습니다.

> **TL;DR**  
> - 블로킹(명령형)은 "호출하고 결과를 기다리며 스레드를 점유"하고, 리액티브(논블로킹)는 "데이터 흐름(stream)을 선언하고, 준비되면 반응"한다.  
> - **Reactive Streams**는 비동기 스트림 처리의 표준이고, 핵심은 **backpressure**(소비자가 받을 양을 `request(n)`으로 제어).  
> - **Reactor**(WebFlux의 기반)의 두 타입: **`Mono`(0..1)** / **`Flux`(0..N)**. 연산자는 파이프라인을 조립할 뿐, **`subscribe()` 전엔 아무 일도 일어나지 않는다(lazy)**.  
> - 블로킹을 안 하니 스레드가 묶이지 않고, 그래서 적은 스레드(event loop)로 많은 요청을 처리할 수 있다(다음 편).  
{: .prompt-info}

---

## 1. 블로킹 vs 리액티브

```java
// 블로킹 / 명령형
Order o = repo.findById(id);   // 결과 나올 때까지 이 스레드가 멈춰서 기다림
use(o);

// 리액티브 / 논블로킹
repo.findById(id)              // "조회하면 -> 이렇게 처리해라" 파이프라인을 선언
    .map(this::toDto)          // 스레드를 붙잡지 않음
    .subscribe(this::use);     // 데이터가 준비되면 그때 흘러옴
```

![블로킹 vs 논블로킹](/assets/img/spring/spring-09-blocking-vs-reactive.webp)
_블로킹: I/O 대기 동안 스레드 점유 vs 논블로킹: 파이프라인 선언, 스레드 freed, 준비되면 처리_

- 명령형: "호출하고, 기다리고, 받는다." 기다리는 동안 스레드 점유.
- 리액티브: "데이터 스트림을 선언하고, 오면 반응(react)한다." 기다리며 스레드를 묶지 않음.

---

## 2. Reactive Streams와 backpressure

리액티브의 공통 규격이 **Reactive Streams**입니다.

> provide a standard for **asynchronous stream processing with non-blocking back pressure**.  

4개 인터페이스로 구성됩니다 (Java의 `java.util.concurrent.Flow`에도 동일 규격이 있습니다).

- **Publisher**: 데이터를 내보내는 쪽
- **Subscriber**: 소비하는 쪽 (`onNext` / `onComplete` / `onError`)
- **Subscription**: 둘을 잇는 계약 (요청량/취소 제어)
- **Processor**: Publisher이자 Subscriber (중간 변환)

![Reactive Streams와 backpressure](/assets/img/spring/spring-10-mono-flux-backpressure.webp)
_Publisher -> operators -> Subscriber, 그리고 Subscriber가 request(n)으로 demand를 거꾸로 신호_

핵심은 **backpressure**입니다. 소비자가 `request(n)`으로 **받을 양을 직접 신호**하므로, 빠른 생산자가 느린 소비자를 압도하지 않습니다.

> back pressure is an integral part of this model in order to allow the queues which mediate between threads to be **bounded**.  

---

## 3. Reactor: Mono / Flux, 그리고 lazy

Spring WebFlux가 쓰는 구현체가 **Reactor**입니다. 두 핵심 타입:

> A `Flux` object represents a reactive sequence of 0..N items  

> a `Mono` object represents a single-value-or-empty (0..1) result  

```java
Mono<Order> one  = repo.findById(id);   // 0 또는 1
Flux<Order> many = repo.findAll();        // 0..N

many.filter(Order::isPaid)
    .map(Order::id)
    .subscribe(System.out::println);      // 이 시점에 비로소 데이터가 흐름
```

결정적 원칙은 **subscribe() 전엔 아무 일도 일어나지 않는다**는 것입니다.

> when you write a `Publisher` chain, data does not start pumping into it by default. Instead, you create an abstract description of your asynchronous process ... By the act of **subscribing**, you tie the `Publisher` to a `Subscriber`, which triggers the flow of data in the whole chain.  

즉 `map`/`filter` 등은 "조립(assembly)"만 하고, `subscribe()`가 호출돼야 데이터가 흐릅니다 (lazy).

---

## 4. 연결: 왜 이게 event loop를 가능케 하나

블로킹을 안 하니 스레드가 I/O 대기에 묶이지 않습니다. 그래서 **적은 수의 고정 스레드(event loop)로 수많은 요청을 번갈아 처리**할 수 있습니다. 이게 다음 편 **Spring WebFlux + netty event loop**의 핵심이고, Series 1 3편 thread-per-request(요청당 스레드 1개 점유)의 정반대입니다.

> 주의: 리액티브 파이프라인 안에서 블로킹 코드(예: 블로킹 JDBC, `Thread.sleep`)를 호출하면 event loop 스레드가 묶여 전체가 느려집니다. 이 트레이드오프는 Series 3 3편(MVC vs WebFlux 선택 기준)에서 다룹니다.  
{: .prompt-warning}

DevSecOps 비유: backpressure는 흐름 제어(TCP flow control, bounded queue, rate limit)와 같은 발상이고, 리액티브는 동기 블로킹 대신 이벤트 기반(nginx event loop, async handler)으로 일하는 모델입니다.

---

## 5. 참고 자료

- Reactor Reference - Core Features (Mono / Flux): <https://projectreactor.io/docs/core/release/reference/coreFeatures.html>
- Reactor Reference - Reactive Programming (Nothing Happens Until You subscribe()): <https://projectreactor.io/docs/core/release/reference/reactiveProgramming.html>
- Reactive Streams (표준 / backpressure): <https://www.reactive-streams.org/>
