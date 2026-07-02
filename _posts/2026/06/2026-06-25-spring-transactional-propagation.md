---
title: Spring @Transactional과 트랜잭션 전파 - 프록시, 롤백 규칙, REQUIRED vs REQUIRES_NEW
date: 2026-06-25 18:00:00 +0900
author: kkamji
categories: [Programming Language, Java]
tags: [java, spring, spring-data-jpa, transaction, aop, jpa]
comments: true
image:
  path: /assets/img/spring/spring.webp
---

[Series 4 1편](/posts/jpa-persistence-context/)에서 영속성 컨텍스트의 수명이 트랜잭션에 묶인다고 했습니다. 그 트랜잭션을 거는 도구가 `@Transactional`인데, 메서드에 한 줄 붙이면 트랜잭션이 시작되고 끝납니다. 그런데 정확히 어떻게 동작할까요. 언제 롤백되고, 트랜잭션 메서드가 또 다른 트랜잭션 메서드를 호출하면 어떻게 될까요. 이번 글에서는 `@Transactional`의 동작(AOP 프록시), 롤백 규칙, 그리고 **트랜잭션 전파(propagation)**를 정리합니다.

> **TL;DR**  
> - `@Transactional`은 **AOP 프록시**로 동작한다. 프록시가 메서드 호출을 가로채 트랜잭션을 begin/commit/rollback으로 감싼다.  
> - **롤백 규칙**: 기본값은 **unchecked 예외(RuntimeException, Error)에서만 자동 롤백**. checked 예외는 기본적으로 롤백하지 않는다(`rollbackFor`로 변경).  
> - **전파**: `REQUIRED`(기본)는 기존 트랜잭션에 합류해 **하나의 물리 트랜잭션**, `REQUIRES_NEW`는 **독립된 물리 트랜잭션**을 새로 만든다(독립 commit/rollback).  
> - **함정**: 같은 클래스 안에서 `this.method()`로 호출하면 프록시를 거치지 않아 `@Transactional`이 **무효**가 된다(self-invocation).  
{: .prompt-info}

---

## 1. @Transactional은 어떻게 동작하나 - AOP 프록시

`@Transactional`은 마법이 아니라 **AOP 프록시**입니다. Spring이 빈을 감싸는 프록시를 만들고, 그 프록시가 메서드 호출 앞뒤로 트랜잭션을 시작하고 끝냅니다.

> The combination of AOP with transactional metadata yields an AOP proxy that uses a `TransactionInterceptor` in conjunction with an appropriate `TransactionManager` implementation to drive transactions around method invocations.  
> _- Spring Framework Reference_  

![@Transactional AOP 프록시 동작](/assets/img/spring/spring-17-transactional-proxy.webp)
_프록시(TransactionInterceptor)가 메서드 호출을 가로채 begin -> 메서드 실행(영속성 컨텍스트 활성) -> commit/rollback으로 감싼다. self-invocation은 프록시를 우회한다._

즉 호출자는 실제 빈이 아니라 프록시를 호출하고, 프록시가 트랜잭션을 시작한 뒤 실제 메서드를 실행하고, 정상 종료면 commit, 예외면 rollback합니다. 1편에서 본 영속성 컨텍스트는 이 트랜잭션 경계 안에서 살아 있습니다.

---

## 2. 롤백 규칙 - unchecked만 자동 롤백

직관과 어긋나기 쉬운 부분입니다. Spring의 기본 롤백 규칙은 **unchecked 예외에서만 자동 롤백**입니다.

> While the Spring default behavior for declarative transaction management follows EJB convention (roll back is automatic only on unchecked exceptions), it is often useful to customize this behavior.  
> _- Spring Framework Reference_  

즉 `RuntimeException`과 `Error`는 자동 롤백되지만, **checked 예외는 기본적으로 롤백되지 않고 커밋**됩니다.

```java
// IOException(checked)이 던져져도 기본값에서는 롤백되지 않고 커밋된다
@Transactional
public void save() throws IOException { ... }

// checked 예외에서도 롤백하려면 rollbackFor 지정
@Transactional(rollbackFor = IOException.class)
public void saveStrict() throws IOException { ... }
```

"예외가 나면 당연히 롤백"이라고 가정했다가, checked 예외가 조용히 커밋되어 데이터가 어중간하게 남는 사고가 흔합니다.

---

## 3. 트랜잭션 전파 - REQUIRED vs REQUIRES_NEW

트랜잭션 메서드가 또 다른 트랜잭션 메서드를 호출할 때, 트랜잭션을 합칠지 새로 만들지를 정하는 것이 **전파(propagation)**입니다.

![전파 REQUIRED vs REQUIRES_NEW](/assets/img/spring/spring-18-propagation.webp)
_REQUIRED는 기존 트랜잭션에 합류해 1개의 물리 트랜잭션(inner rollback이 전체에 영향). REQUIRES_NEW는 독립된 물리 트랜잭션(독립 commit/rollback)._

기본값은 **`REQUIRED`**입니다.

> `PROPAGATION_REQUIRED` enforces a physical transaction, either locally for the current scope if no transaction exists yet or participating in an existing 'outer' transaction defined for a larger scope. ... In the case of standard `PROPAGATION_REQUIRED` behavior, all these scopes are mapped to the same physical transaction.  
> _- Spring Framework Reference_  

즉 기존 트랜잭션이 있으면 합류하고 없으면 새로 만들며, 합류한 경우 **하나의 물리 트랜잭션**입니다. 그래서 inner에서 롤백되면 전체가 롤백됩니다.

반대로 **`REQUIRES_NEW`**는 항상 독립된 물리 트랜잭션을 만듭니다.

> `PROPAGATION_REQUIRES_NEW`, in contrast to `PROPAGATION_REQUIRED`, always uses an independent physical transaction for each affected transaction scope, never participating in an existing transaction for an outer scope. In such an arrangement, the underlying resource transactions are different and, hence, can commit or roll back independently, with an outer transaction not affected by an inner transaction's rollback status ...  
> _- Spring Framework Reference_  

예를 들어 "주문은 실패해도 감사 로그는 남겨야 한다" 같은 경우, 로그 기록을 `REQUIRES_NEW`로 분리하면 바깥 트랜잭션이 롤백돼도 로그는 독립적으로 커밋할 수 있습니다.

> 참고로 `NESTED`는 하나의 물리 트랜잭션 안에 savepoint를 두어, inner만 부분 롤백하고 outer는 계속 진행할 수 있게 합니다.  
{: .prompt-info}

---

## 4. 함정: self-invocation (프록시 우회)

가장 자주 당하는 함정입니다. `@Transactional`은 프록시를 통해 호출될 때만 동작하는데, **같은 클래스 안에서 `this`로 호출하면 프록시를 거치지 않습니다.**

> once the call has finally reached the target object ... any method calls that it may make on itself, such as `this.bar()` or `this.foo()`, are going to be invoked against the `this` reference, and not the proxy. ... self invocation is not going to result in the advice associated with a method invocation getting a chance to run.  
> _- Spring Framework Reference_  

```java
@Service
public class OrderService {
    public void outer() {
        inner();   // this.inner() -> 프록시 우회 -> @Transactional 무효!
    }

    @Transactional
    public void inner() { ... }
}
```

위 `outer()`에서 `inner()`를 호출하면 `@Transactional`이 적용되지 않습니다. 해결책은 호출 대상을 **다른 빈으로 분리**(프록시를 거치도록)하거나, 자기 자신을 주입(self-injection)해 프록시 참조로 호출하는 것입니다.

---

## 5. 다음 글

이번 편에서 `@Transactional`의 프록시 동작, 롤백 규칙, 전파(REQUIRED/REQUIRES_NEW), self-invocation 함정을 봤습니다. [1편의 영속성 컨텍스트](/posts/jpa-persistence-context/)는 바로 이 트랜잭션 경계 안에서 살아 있습니다. 다음 편은 데이터 계층 성능의 단골 문제인 **N+1과 그 해결(fetch join, batch size)**을 다룹니다.

capstone 연결: 전파를 잘못 설계하면(예: 불필요한 `REQUIRES_NEW` 남발) 물리 트랜잭션과 DB 커넥션이 늘어 커넥션 풀과 메모리에 압박을 줍니다. 트랜잭션 경계 설계는 [JVM 메모리](/posts/jvm-memory-model/)와 자원 사용으로 이어집니다.

DevSecOps 비유: 전파는 **중첩 작업의 원자성 경계 설계**입니다. REQUIRED는 "전부 함께 성공/실패", REQUIRES_NEW는 "독립 커밋"이고, 이는 분산 시스템의 saga/보상 트랜잭션이나 nested 작업의 부분 롤백(savepoint) 설계와 같은 고민입니다. self-invocation 함정은 **데코레이터/미들웨어를 우회하는 직접 호출**(프록시를 안 거치면 부가기능이 안 붙는다)과 동일한 패턴입니다.

---

## 6. 참고 자료

- Spring Framework Reference - Declarative Transaction Management (AOP 프록시 / 롤백 규칙): <https://docs.spring.io/spring-framework/reference/data-access/transaction/declarative.html>
- Spring Framework Reference - Transaction Propagation (REQUIRED / REQUIRES_NEW / NESTED): <https://docs.spring.io/spring-framework/reference/data-access/transaction/declarative/tx-propagation.html>
- Spring Framework Reference - Understanding AOP Proxies (self-invocation): <https://docs.spring.io/spring-framework/reference/core/aop/proxying.html>

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
