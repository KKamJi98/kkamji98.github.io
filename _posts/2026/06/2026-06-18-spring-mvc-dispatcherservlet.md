---
title: Spring MVC 깊이 보기 - DispatcherServlet과 thread-per-request
date: 2026-06-18 09:00:00 +0900
author: kkamji
categories: [Programming Language, Java]
tags: [java, spring, spring-mvc, dispatcherservlet, servlet, tomcat, thread-per-request]
comments: true
image:
  path: /assets/img/spring/spring.webp
---

[1편](/posts/spring-request-lifecycle/)에서 "DispatcherServlet이 front controller로 모든 요청을 받아 분배한다", "요청당 스레드 1개를 쓴다"고 선언만 했습니다. 이번 편에서는 그 **안을 해부**합니다. DispatcherServlet 내부가 어떻게 동작하는지, 그리고 "요청당 스레드 1개"가 정확히 무슨 의미이고 왜 그게 메모리/동시성의 갈림길인지를 다룹니다.

> **TL;DR**  
> - DispatcherServlet은 직접 일하지 않고 위임한다: **HandlerMapping(매칭) -> HandlerAdapter(호출) -> 반환값 변환(JSON/뷰)**.  
> - 매칭은 prefix가 아니라 **경로 패턴 + HTTP 메서드** 기준이다.  
> - Spring MVC는 **블로킹 모델**이라, 서블릿 컨테이너가 **큰 스레드풀**(Tomcat 기본 200)로 요청당 워커 1개를 점유한다.  
> - 워커 스레드의 호출 스택은 **힙이 아니라 native 메모리**(약 0.5-1MB)라 컨테이너 메모리 산정에 들어간다.  
{: .prompt-info}

---

## 1. 서블릿 / 서블릿 컨테이너 / Tomcat / DispatcherServlet

먼저 용어를 정리합니다.

- **서블릿(Servlet)**: HTTP 요청 1건을 처리하는 Java 객체의 표준 규격
- **서블릿 컨테이너**: 서블릿을 실행해주는 런타임. 요청을 `HttpServletRequest`로 감싸고 스레드를 붙여 서블릿을 호출하며 생명주기를 관리
- **Tomcat**: 그 서블릿 컨테이너의 구현체 (Spring Boot에선 내장)
- **DispatcherServlet**: Spring이 제공하는 단 하나의 서블릿으로, 기본적으로 `/`(전체 경로)에 매핑돼 모든 요청을 먼저 받는 front controller (Spring Boot에서 `spring.mvc.servlet.path`로 변경 가능)

> Spring MVC, as many other web frameworks, is designed around the front controller pattern where a central `Servlet`, the `DispatcherServlet`, provides a shared algorithm for request processing, while actual work is performed by configurable delegate components.  

마지막 문장이 이번 편의 열쇠입니다. **실제 일은 "configurable delegate components"(위임 컴포넌트)가 하고, DispatcherServlet은 그 흐름을 조율**합니다.

---

## 2. DispatcherServlet 안: 매칭과 호출의 분리

1편에서 "DispatcherServlet -> 컨트롤러"로 뭉뚱그렸지만, 실제로는 내부에서 여러 부품이 협력합니다.

![DispatcherServlet 내부 시퀀스](/assets/img/spring/spring-05-dispatcherservlet-sequence.webp)
_DispatcherServlet이 HandlerMapping(매칭) -> HandlerAdapter(호출) -> 반환값 변환으로 위임_

가장 중요한 분담은 **HandlerMapping(매칭)** 과 **HandlerAdapter(호출)** 의 분리입니다.

**HandlerMapping - 어떤 핸들러인지 찾기**

> Map a request to a handler along with a list of interceptors for pre- and post-processing. The mapping is based on some criteria, the details of which vary by `HandlerMapping` implementation.  

여기서 "some criteria"가 핵심입니다. **prefix(앞부분 일치)가 아니라 경로 패턴 + HTTP 메서드**(필요시 헤더/파라미터/content-type)를 종합해 매칭합니다. `@RequestMapping`을 처리하는 `RequestMappingHandlerMapping`이 대표 구현입니다.

HandlerMapping은 보통 하나가 아니라 여러 개가 등록됩니다. `@RequestMapping` 메서드를 처리하는 `RequestMappingHandlerMapping`, 정적 리소스를 처리하는 핸들러 등이 함께 존재하므로, DispatcherServlet은 **우선순위 순서대로** 각 HandlerMapping에 물어보고 처음 매칭되는 핸들러를 채택합니다. 이 순서는 `Ordered` 인터페이스로 결정됩니다.

> Note: Implementations can implement the `Ordered` interface to be able to specify a sorting order and thus a priority for getting applied by DispatcherServlet. Non-Ordered instances get treated as the lowest priority.  

`RequestMappingHandlerMapping`은 기본 order가 0(자동 설정 기준 비교적 높은 우선순위)이고, 정적 리소스용 매핑은 더 낮은 우선순위에 놓여 애플리케이션의 `@RequestMapping`이 먼저 평가되도록 배치됩니다.

```java
@RestController
public class OrderController {

    @GetMapping("/orders/{id}")     // 경로 패턴 + GET
    public OrderDto getOrder(@PathVariable Long id) { ... }

    @PostMapping("/orders")         // 같은 /orders 라도 POST 는 다른 핸들러
    public OrderDto create(@RequestBody CreateOrder req) { ... }
}
```

`GET /orders/42`는 첫 번째에 매칭되고(경로변수 `id=42`), `POST /orders`는 두 번째로 갑니다. 같은 경로라도 메서드가 다르면 다른 핸들러입니다.

**HandlerAdapter - 그 핸들러를 호출하기**

> Help the `DispatcherServlet` to invoke a handler mapped to a request, regardless of how the handler is actually invoked. For example, invoking an annotated controller requires resolving annotations. The main purpose of a `HandlerAdapter` is to shield the `DispatcherServlet` from such details.  

즉 "어떤 핸들러인지 고르는 일(매칭)"은 HandlerMapping이 끝내고, HandlerAdapter는 **그 핸들러를 실제로 호출**합니다 (`@PathVariable`, `@RequestBody` 같은 인자 바인딩 포함). 이후 반환값을 `HttpMessageConverter`(REST의 JSON 직렬화)나 `ViewResolver`(뷰 렌더링)가 응답으로 변환합니다.

**HttpMessageConverter와 content negotiation**: `@RestController`(= `@Controller` + `@ResponseBody`)에서 컨트롤러가 객체를 반환하면 그 객체는 `HttpMessageConverter`를 거쳐 응답 body로 직렬화됩니다.

> You can use the `@ResponseBody` annotation on a method to have the return serialized to the response body through an HttpMessageConverter.  

그렇다면 같은 `OrderDto`가 JSON이 될지 XML이 될지는 누가 정하는가. Spring MVC는 요청의 **content negotiation** 결과(클라이언트가 받고 싶어하는 media type)에 맞는 컨버터를 고릅니다. 기본 전략은 요청의 `Accept` 헤더만 보는 것입니다.

> By default, only the `Accept` header is checked.  

즉 `Accept: application/json`이면 Jackson 기반 JSON 컨버터가, XML 컨버터가 등록돼 있고 `Accept: application/xml`이면 XML 컨버터가 선택됩니다. URL 확장자(`.json`)나 쿼리 파라미터로도 협상하도록 설정할 수 있지만, 보안(suffix 매칭/RFD)상 기본값은 `Accept` 헤더 단독입니다.

> Filter(서블릿 스펙)는 DispatcherServlet 바깥, Interceptor(Spring)는 안(핸들러 전후)에서 동작합니다. 보안/인코딩 같은 공통 처리는 Filter, 핸들러 특화 전후 처리는 Interceptor.  
{: .prompt-tip}

---

## 3. thread-per-request: 요청 1개 = 워커 스레드 1개

이번 편의 진짜 핵심입니다. Spring MVC는 **블로킹 모델**을 전제합니다.

> In Spring MVC (and servlet applications in general), it is assumed that applications can block the current thread, (for example, for remote calls). For this reason, servlet containers use a large thread pool to absorb potential blocking during request handling.  

즉 DB나 외부 API 호출에서 스레드가 멈출(block) 수 있다고 보고, 그 블로킹을 흡수하려고 **큰 스레드풀**을 둡니다. Tomcat의 기본값은 200입니다.

> The maximum number of request processing threads ... If not specified, this attribute is set to 200.  

![thread-per-request 모델](/assets/img/spring/spring-06-thread-per-request.webp)
_요청당 워커 1개 점유(블로킹 포함), 풀이 차면 대기 큐 -> 거절/타임아웃_

동작을 정리하면:

- 요청 하나가 들어오면 워커 스레드 하나가 배정돼 **처리 시작부터 끝까지 전담**한다 (필터 -> 디스패처 -> 컨트롤러 -> 서비스 -> DB).
- 블로킹 구간(DB/외부 API 대기) 동안에도 그 스레드는 아무 일 안 하면서 **묶여** 있다.
- 동시 요청이 풀 크기(기본 200)를 넘으면 대기 큐에 쌓이고, 더 넘으면 거절되거나 타임아웃된다.

대기 큐의 길이는 Tomcat의 `acceptCount`로, 기본값 100입니다. 즉 워커 200개가 모두 묶인 상태에서 추가로 100개까지는 OS 연결 큐에서 대기하고, 그 너머는 거절/타임아웃됩니다.

> The maximum length of the operating system provided queue for incoming connection requests when `maxConnections` has been reached. ... When this queue is full, the operating system may actively refuse additional connections or those connections may time out. The default value is 100.  

DevSecOps 비유로는 Apache prefork/worker MPM처럼 "연결 하나가 워커 하나를 묶는" 모델입니다.

---

## 4. 스레드 스택은 힙이 아니라 native 메모리

여기가 capstone(메모리)과 직결됩니다.

> 각 워커 스레드는 자기만의 호출 스택(call stack)을 가지며, 이 스택은 **힙(`-Xmx`)이 아니라 native 메모리**에 잡힙니다 (`-Xss`로 크기 지정, 대략 0.5-1MB. 정확한 기본값은 플랫폼/JDK마다 다릅니다). 그래서 스레드 200개면 스택만 ~100-200MB의 off-heap/native 메모리를 씁니다. 단, `-Xss`는 스택의 **이론상 최대 크기**이고, 실제 OS는 보통 스택 영역을 lazy하게 commit(접근한 페이지만 물리 메모리에 매핑)하므로 200개 스레드가 항상 ~100-200MB를 물리적으로 점유하는 것은 아닙니다. 메모리 산정에서는 "최악의 상한"으로 잡아두는 값입니다.  
{: .prompt-warning}

이 스택 메모리가 왜 중요한가:

- 컨테이너 메모리 한도는 **힙 + 스레드 스택 + 기타 native + off-heap**을 다 합친 것이라, "`-Xmx`만 보면 안 되는" 이유의 한 갈래가 이 스레드 스택입니다.
- 블로킹 모델이라 I/O 지연이 길어지면 스레드가 더 오래 묶이고, 처리량을 유지하려면 스레드를 늘려야 하는데 그만큼 메모리가 더 듭니다.

스레드 스택의 정확한 동작과 native 메모리 영역은 [JVM 메모리 모델 편](/posts/jvm-memory-model/)에서 깊게 다룹니다. 여기서는 "스레드 수가 메모리에 직접 영향을 준다"는 연결만 잡아둡니다.

---

## 5. 마무리

이번 편의 핵심은 (1) DispatcherServlet은 **매칭(HandlerMapping)과 호출(HandlerAdapter)을 분리해 위임**하고, (2) Spring MVC는 **블로킹 + 큰 스레드풀(요청당 워커 1개)** 모델이며, (3) 그 **스레드 스택이 native 메모리**라 컨테이너 메모리에 영향을 준다는 것입니다.

> capstone 복선: [1편](/posts/spring-request-lifecycle/)(단일 프로세스 = 메모리 경계 하나) + [2편](/posts/spring-ioc-di-container/)(싱글톤 빈 baseline) + 3편(스레드 스택 native)이 모두 컨테이너 메모리 한도 안에서 더해집니다. buildpack memory calculator가 빼는 항목들이 바로 이것들입니다.  
{: .prompt-tip}

블로킹 + 큰 스레드풀의 한계를 깨려는 것이 바로 **이벤트 루프 기반의 WebFlux**입니다.

> In Spring WebFlux (and non-blocking servers in general) ... non-blocking servers use a small, fixed-size thread pool (event loop workers) to handle requests.  

이 대비(thread-per-request vs event loop)는 [WebFlux와 netty event loop 편](/posts/spring-webflux-netty-event-loop/)에서 다룹니다. 그 전에 [다음 편](/posts/spring-boot-autoconfiguration/)에서는 이 모든 게 어떻게 패키징되고 실행되는지 - Spring Boot의 자동설정과 fat jar를 다룹니다.

---

## 6. 참고 자료

- Spring Framework Reference - DispatcherServlet: <https://docs.spring.io/spring-framework/reference/web/webmvc/mvc-servlet.html>
- Spring Framework Reference - Special Bean Types (HandlerMapping / HandlerAdapter): <https://docs.spring.io/spring-framework/reference/web/webmvc/mvc-servlet/special-bean-types.html>
- Spring Framework Reference - Concurrency (MVC blocking vs WebFlux): <https://docs.spring.io/spring-framework/reference/web/webflux/new-framework.html>
- Spring Framework Javadoc - HandlerMapping (Ordered 우선순위): <https://docs.spring.io/spring-framework/docs/current/javadoc-api/org/springframework/web/servlet/HandlerMapping.html>
- Spring Framework Reference - @ResponseBody (HttpMessageConverter): <https://docs.spring.io/spring-framework/reference/web/webmvc/mvc-controller/ann-methods/responsebody.html>
- Spring Framework Reference - Content Types (content negotiation): <https://docs.spring.io/spring-framework/reference/web/webmvc/mvc-config/content-negotiation.html>
- Apache Tomcat - HTTP Connector (maxThreads): <https://tomcat.apache.org/tomcat-10.1-doc/config/http.html>

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
