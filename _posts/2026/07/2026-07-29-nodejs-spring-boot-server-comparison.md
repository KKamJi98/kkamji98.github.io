---
title: "Node.js와 Spring Boot 서버 비교 - 실행 스택 중심으로"
date: 2026-07-29 19:00:00 +0900
author: kkamji
categories: [Backend, Node.js]
tags: [nodejs, spring-boot, spring-mvc, spring-webflux, servlet, reactor-netty, server, architecture]
comments: true
image:
  path: /assets/img/nodejs/nodejs-logo-history-banner.png
---

Node.js와 Spring Boot를 "싱글 스레드 대 멀티 스레드" 또는 "어느 쪽이 더 빠른가"로 비교하면 실행 모델을 잃기 쉽습니다. Node.js는 JavaScript runtime이고 Spring Boot는 Servlet 기반 MVC 또는 reactive WebFlux 같은 웹 스택을 구성합니다. 같은 HTTP server로 보여도 요청을 실행하는 단위와 블로킹의 비용은 스택마다 다릅니다.

> **TL;DR**<br>  
> - 비교 대상은 Node.js core HTTP, Spring Boot MVC, Spring Boot WebFlux 세 가지입니다.<br>  
> - Node.js의 main JavaScript 실행 흐름, MVC의 servlet request thread, WebFlux의 event loop worker는 같은 역할의 이름이 아닙니다.<br>  
> - I/O 대기와 CPU 작업의 비용은 각 스택에서 다르게 나타나며, 단일 RPS 숫자로 선택하면 안 됩니다.<br>  
> - `starter-web`과 `starter-webflux`를 함께 넣어도 Spring Boot는 기본적으로 MVC를 자동 구성합니다.  
{: .prompt-info}

---

## 1. 세 실행 스택을 같은 층위에서 비교하지 않기

Node.js는 runtime이고 Spring Boot는 framework입니다. 서비스 선택을 논의할 때 비교 대상은 Node.js의 `node:http`, Spring Boot MVC, Spring Boot WebFlux라는 세 실행 스택입니다.

세 stack에서 blocking dependency, I/O wait, CPU 작업이 어느 실행 단위를 점유하는지 보면, 단일 RPS 숫자보다 서비스에 필요한 관측 지점과 분리 전략이 먼저 드러납니다.

---

## 2. 세 server stack의 책임 경계

Node.js core HTTP는 Node process에서 `http.Server`와 application handler를 조립합니다. 기본 JavaScript 실행 흐름에서 handler의 동기 코드가 실행되고, I/O 완료 뒤 callback 또는 Promise continuation이 이어집니다.

Spring Boot MVC는 Servlet API와 servlet container 위에서 controller를 실행합니다. blocking 작업은 request thread를 점유할 수 있으므로 thread pool, queue, request latency를 함께 관찰해야 합니다. Spring Boot WebFlux는 non-blocking I/O와 Reactive Streams 계약을 전제로 하는 별도 웹 스택입니다. 기본 server 선택은 Reactor Netty이지만 WebFlux 자체와 Netty는 같은 개념이 아닙니다.

![Node.js, Spring MVC, Spring WebFlux의 요청 실행 경계](/assets/img/server/nodejs-spring-server-stacks.webp)
_세 칸은 성능 순위가 아니라 요청을 실행하는 책임 경계다. 블로킹 코드가 어느 실행 단위를 점유하는지, CPU 작업을 어디로 분리할지는 각 stack의 계약 안에서 판단한다._

---

## 3. 요청을 실행하는 단위는 무엇인가

| 비교 축 | Node.js core HTTP | Spring Boot MVC | Spring Boot WebFlux |
| --- | --- | --- | --- |
| 제품 층위 | JavaScript runtime의 core API | Servlet 기반 web stack | reactive web stack |
| 일반 handler 경계 | main JavaScript 실행 흐름 | servlet request thread | event loop worker와 reactive pipeline |
| I/O 대기 | callback 또는 Promise 후속 작업 | request thread가 점유될 수 있음 | non-blocking contract를 전제로 함 |
| 블로킹 코드 | event loop 지연 가능 | thread pool 고갈 가능 | event loop worker에 영향 가능 |
| CPU-heavy 작업 | Worker Thread 또는 process 분리 검토 | executor 또는 서비스 경계 검토 | event loop 밖 scheduler 또는 서비스 경계 검토 |
| 우선 관측 | event loop delay, CPU, latency | active thread, queue, latency | event loop blocking, scheduler, latency |

"Node.js는 싱글 스레드"라는 문장은 기본 JavaScript 실행 흐름을 가리킬 때만 유효합니다. libuv Worker Pool, Worker Threads, cluster process는 별도의 실행 단위입니다. 반대로 MVC request thread와 WebFlux event loop worker도 JVM의 모든 thread를 뜻하지 않습니다.

---

## 4. I/O wait와 blocking code의 비용

I/O wait는 CPU를 계속 계산하는 작업과 다릅니다. Node.js에서 비동기 I/O를 시작한 뒤 현재 handler가 기다리는 동안 ready callback이 처리될 수 있지만, 긴 동기 JavaScript는 main event loop를 점유합니다. [비동기 HTTP handler 글](/posts/nodejs-async-http-handling/)의 `await`도 process 전체를 멈추는 기능은 아닙니다.

MVC에서는 blocking JDBC, file I/O, remote call 같은 작업이 request thread를 오래 점유할 수 있습니다. WebFlux는 blocking dependency를 없애는 마법이 아닙니다. event loop worker에서 blocking call을 실행하면 적은 worker가 다수 요청에 영향을 줄 수 있습니다. 따라서 WebFlux에서 `Thread.sleep()`을 non-blocking API처럼 사용하면 안 됩니다.

여기서 "비동기"라는 단어만으로 처리량, latency, memory 효율을 단정할 수 없습니다. workload shape, 동시성, payload, CPU limit, downstream dependency의 blocking 여부와 runtime version을 함께 봐야 합니다.

---

## 5. Worker Thread와 MVC request thread를 등치하지 않기

Node Worker Threads는 CPU-intensive JavaScript를 분리하는 데 적합합니다. I/O-intensive 작업을 위해 request마다 Worker Thread를 만드는 모델은 적절하지 않습니다. Worker 생성, message passing, shared memory 정책은 별도 설계 대상입니다.

MVC의 request thread는 request lifecycle 동안 blocking 작업을 처리할 수 있도록 container가 관리하는 실행 단위입니다. WebFlux의 scheduler도 Node Worker Thread와 같은 API가 아닙니다. 세 경우 모두 "블로킹 작업을 어디에서 실행할 것인가"라는 질문은 같지만, lifecycle, queue, cancellation, observability가 다릅니다.

---

## 6. Spring Boot에서 MVC와 WebFlux를 고르는 실제 규칙

`spring-boot-starter-web` 계열은 MVC servlet application을 구성합니다. `spring-boot-starter-webflux`는 reactive web application을 구성합니다. 두 starter가 함께 있으면 Spring Boot는 기본적으로 MVC를 자동 구성합니다. MVC application에서 `WebClient`를 사용하기 위해 WebFlux dependency를 추가하는 경우를 지원하기 위한 선택입니다.

server stack은 dependency graph만으로 드러나지 않습니다. startup log, ApplicationContext type, active server implementation, handler thread name을 실제 환경에서 확인해야 합니다. reactive return type을 controller에서 쓴다는 사실만으로 WebFlux server라고 결론 내릴 수도 없습니다.

---

## 7. localhost lab으로 실행 stack 확인하기

동일한 `/whoami` HTTP contract를 두 Spring Boot application에 두고 ephemeral port에서 실행했습니다. 각 endpoint는 자신이 선택한 stack 이름과 handler thread name을 JSON으로 반환합니다. 이 lab은 성능 benchmark가 아니라 startup과 request handling 경계를 확인하는 용도입니다.

```java
@RestController
class WhoAmIController {
  @GetMapping("/whoami")
  Map<String, String> whoAmI() {
    return Map.of("stack", "mvc", "thread", Thread.currentThread().getName());
  }
}
```

Spring Initializr가 생성한 Maven wrapper를 사용해 Java `21.0.11`, Spring Boot `4.1.0`에서 실행한 결과입니다.

```text
MVC:     Tomcat started on port 34217
MVC:     Tests run: 1, Failures: 0, Errors: 0
WebFlux: Netty started on port 41647
WebFlux: Tests run: 1, Failures: 0, Errors: 0
```

두 실행은 모두 `127.0.0.1`과 random port만 사용했습니다. 이 결과는 해당 dependency와 버전에서 MVC sample이 Tomcat, WebFlux sample이 Reactor Netty로 시작했다는 관측입니다. 다른 embedded server dependency나 운영 설정까지 일반화하는 benchmark 결과는 아닙니다.

---

## 8. 선택 질문으로 정리하기

stack을 고르기 전에 다음을 확인합니다.

1. request path에 blocking JDBC, SDK, file I/O가 많은가
2. 높은 동시성 I/O와 streaming이 핵심인가
3. CPU-heavy 작업을 request path에서 분리할 수 있는가
4. 팀이 JavaScript와 JVM 생태계 중 어느 쪽의 dependency와 observability를 운영할 수 있는가
5. thread pool, scheduler, event loop delay, queue를 어떤 metric으로 검증할 것인가

Node.js가 빠른지 Spring Boot가 빠른지를 먼저 묻기보다, 서비스가 어떤 작업을 기다리고 무엇을 block하며 어떤 실행 단위를 관측할 수 있는지부터 답해야 합니다.

---

## 9. Reference

- [Node.js v26 Documentation - HTTP](https://nodejs.org/docs/latest-v26.x/api/http.html)
- [Node.js v26 Documentation - Worker Threads](https://nodejs.org/docs/latest-v26.x/api/worker_threads.html)
- [Node.js Learn - Don't Block the Event Loop](https://nodejs.org/en/learn/asynchronous-work/dont-block-the-event-loop)
- [Spring Framework Reference - Spring Web MVC](https://docs.spring.io/spring-framework/reference/web/webmvc.html)
- [Spring Framework Reference - WebFlux Overview and Applicability](https://docs.spring.io/spring-framework/reference/web/webflux/new-framework.html)
- [Spring Boot Reference - Servlet Web Applications](https://docs.spring.io/spring-boot/reference/web/servlet.html)
- [Spring Boot Reference - Reactive Web Applications](https://docs.spring.io/spring-boot/reference/web/reactive.html)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
