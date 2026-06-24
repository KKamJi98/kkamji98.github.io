---
title: Spring은 왜 필요한가 - IoC/DI와 Bean
date: 2026-06-22 10:00:00 +0900
author: kkamji
categories: [Programming Language, Java]
tags: [java, spring, ioc, dependency-injection, bean]
comments: true
image:
  path: /assets/img/spring/spring.webp
---

[1편](/posts/spring-request-lifecycle/)에서 요청이 `Controller -> Service -> Repository`를 거쳐 처리되고, 이들이 "전부 빈(Bean)으로 힙에 상주한다"고 했습니다. 그런데 빈이 정확히 뭐고, 왜 우리는 이 객체들을 직접 `new`로 만들지 않을까요?

이 글은 Spring의 가장 근본적인 질문 - "Spring은 대체 무슨 일을 해주는가"에 답합니다. 핵심은 **IoC(제어의 역전)와 DI(의존성 주입)**, 그리고 그 결과물인 **빈**입니다.

> **TL;DR**  
> - 객체를 만들고 엮는 **조립 책임**을 내 코드에서 **컨테이너**로 넘기는 것이 IoC(제어의 역전)다.  
> - 컨테이너가 필요한 객체를 외부에서 넣어주는 메커니즘이 DI(의존성 주입)이고, **생성자 주입**이 권장된다.  
> - `@Component`(및 그 특수화 `@Service`/`@Repository`/`@Controller`)가 붙은 클래스는 컨테이너가 **빈**으로 등록한다. 기본 스코프는 **싱글톤**이라 1편의 그 객체들이 시작 시 1개씩 만들어져 모든 요청이 공유한다.  
{: .prompt-info}

---

## 1. 문제: 직접 new로 엮으면 강결합

주문 기능을 직접 만들어 봅니다. Controller가 Service를, Service가 Repository를 씁니다.

```java
public class OrderController {
    // 의존성을 내가 직접 생성한다
    private final OrderService service = new OrderService(new OrderRepository());
}
```

문제가 보입니다.

- `OrderController`가 `OrderRepository`를 어떻게 만드는지까지 알아야 한다 (강결합).
- 구현을 바꾸려면(테스트용 가짜, 다른 DB 구현 등) Controller 코드를 뜯어야 한다.
- 테스트할 때 진짜 DB 객체가 딸려와 단위 테스트가 어렵다.

클래스가 늘수록 이 "누가 누구를 `new` 해서 엮느냐"는 조립 코드가 거대해지고, 그 관리를 전부 내가 떠안게 됩니다.

![IoC 전후 결합도 비교](/assets/img/spring/spring-03-ioc-before-after.webp)
_왼쪽(수동 new, 강결합) vs 오른쪽(컨테이너가 조립/주입, 느슨한 결합)_

---

## 2. IoC: 조립 제어권을 컨테이너로 넘긴다

해법은 "객체를 누가 만들고 엮는가"의 주도권을 내 코드에서 컨테이너로 넘기는 것입니다. 각 클래스는 "나는 무엇이 필요하다"만 선언합니다.

```java
@RestController
public class OrderController {
    private final OrderService service;

    public OrderController(OrderService service) {   // new 하지 않고, 필요하다고 선언만
        this.service = service;
    }
}
```

그러면 컨테이너가 시작 시점에 의존 그래프를 계산해 순서대로 만들어 엮습니다.

```text
OrderRepository 생성 -> OrderService(repo 주입) -> OrderController(service 주입)
(내 코드는 new를 한 번도 쓰지 않는다. 조립은 컨테이너 담당.)
```

Spring 공식 레퍼런스는 이 "역전"을 이렇게 정의합니다.

> Dependency injection (DI) ... The IoC container then injects those dependencies when it creates the bean. This process is fundamentally the inverse (hence the name, Inversion of Control) of the bean itself controlling the instantiation ... of its dependencies.  

즉 예전엔 "객체 생성/조립의 흐름 제어"를 내 코드가 쥐고 있었는데, 그 제어권이 프레임워크로 넘어간 것입니다. 이것이 제어의 역전(Inversion of Control)입니다.

> DevSecOps 비유: 의존성을 코드에 박는 대신 런타임에 주입하는 건, 설정/시크릿을 이미지에 하드코딩하지 않고 ConfigMap/env로 파드에 주입하는 것과 같은 발상입니다.  
{: .prompt-tip}

---

## 3. DI: IoC를 실현하는 주입, 그리고 생성자 주입

컨테이너가 필요한 객체를 외부에서 넣어주는 것이 DI입니다. 주입 방식은 생성자/setter/field 셋이 있는데, **생성자 주입**이 권장됩니다.

> The Spring team generally advocates constructor injection, as it lets you implement application components as immutable objects and ensures that required dependencies are not `null`.  

정리하면 생성자 주입의 이점은 (1) 필드를 `final`로 둘 수 있어 불변, (2) 필수 의존성이 `null`이 아님을 보장, (3) 완전히 초기화된 상태로 객체가 만들어져 테스트가 쉽다는 것입니다.

---

## 4. 컨테이너와 빈: 1편의 객체들이 왜 전부 빈이었나

- **IoC 컨테이너**(`ApplicationContext`, `BeanFactory`의 sub-interface): 빈 정의를 읽어 객체를 만들고 의존성을 엮고 생명주기를 관리한다.
- **빈(Bean)**: 그 컨테이너가 만들어 관리하는 객체.

> A bean is an object that is instantiated, assembled, and managed by a Spring IoC container.  

빈 등록의 핵심은 stereotype 어노테이션입니다.

> `@Component` is a generic stereotype ... `@Repository`, `@Service`, and `@Controller` are specializations of `@Component`.  

```text
@Controller     = @Component  (+ 프레젠테이션 계층 표시)
@RestController = @Controller + @ResponseBody  (응답을 JSON 등으로 직렬화)
@Service        = @Component  (+ 비즈니스 계층 표시)
@Repository     = @Component  (+ 데이터 계층 표시 + DB 예외 변환)
```

그래서 컴포넌트 스캔이 시작 시 이들을 찾아 각각 빈으로 등록합니다. 그리고 기본 스코프가 싱글톤입니다.

> The singleton scope is the default scope in Spring.  

이 둘을 1편과 합치면 답이 나옵니다.

```text
[앱 시작 시 - 한 번]  컨테이너가 Controller/Service/Repository 빈을 싱글톤으로 생성 (힙에 상주)
[요청마다]            DispatcherServlet이 이미 만들어진 그 빈의 메서드를 호출 (새로 new 하지 않음)
```

1편에서 "그 세 박스가 전부 빈, 힙에 상주"라고 한 이유가 이것입니다. **요청마다 만드는 게 아니라, 시작 때 1개씩 만들어 모든 요청이 같은 인스턴스를 공유**합니다.

> 따름 결론: 요청당 스레드 1개(1편)인데 그 스레드들이 같은 빈을 공유하므로, 빈은 보통 상태 없이(stateless) 설계해야 동시성 문제가 없습니다.  
{: .prompt-warning}

---

## 5. 빈 생명주기

빈은 컨테이너 안에서 다음 단계를 거칩니다.

![빈 생명주기](/assets/img/spring/spring-04-bean-lifecycle.webp)
_컴포넌트 스캔 -> 빈 정의 등록 -> 인스턴스화 -> 의존 주입 -> 초기화 콜백 -> 사용(싱글톤) -> 소멸_

- 컨테이너 시작 시 컴포넌트 스캔으로 빈 정의를 등록한다.
- 인스턴스를 만들고 의존성을 주입한다.
- `@PostConstruct` 초기화 콜백이 호출된다.
- 이후 앱이 사는 동안 싱글톤으로 상주하며 모든 요청에 재사용된다.
- 앱 종료 시 `@PreDestroy`가 호출되고 소멸한다.

---

## 6. 마무리

이번 편의 핵심은 (1) **조립 제어권이 내 코드에서 컨테이너로 역전**되었고(IoC), (2) 컨테이너가 필요한 객체를 **주입**하며(DI), (3) stereotype이 붙은 클래스가 **싱글톤 빈**으로 등록돼 모든 요청이 공유한다는 것입니다.

> capstone 복선: 싱글톤 빈들은 앱 생명주기 내내 힙에 머물러 **기준 힙 점유(baseline)** 를 형성합니다. "메모리가 왜 이만큼 깔려 있나"의 바닥이 여기이고, 뒤의 메모리/GC 편에서 이 baseline 위에 어떤 것들이 쌓이는지 보게 됩니다.  
{: .prompt-tip}

다음 편부터는 한 계층 아래로 내려가 이 모든 게 올라타 있는 **JVM과 메모리**를 다룹니다.

---

## 7. 참고 자료

- Spring Framework Reference - Introduction to the IoC Container and Beans: <https://docs.spring.io/spring-framework/reference/core/beans/introduction.html>
- Spring Framework Reference - Classpath Scanning and Stereotype Annotations: <https://docs.spring.io/spring-framework/reference/core/beans/classpath-scanning.html>
- Spring Framework Reference - Dependency Injection (constructor-based): <https://docs.spring.io/spring-framework/reference/core/beans/dependencies/factory-collaborators.html>
- Spring Framework Reference - Bean Scopes (singleton): <https://docs.spring.io/spring-framework/reference/core/beans/factory-scopes.html>
