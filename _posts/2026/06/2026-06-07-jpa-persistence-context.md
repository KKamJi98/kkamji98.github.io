---
title: JPA 영속성 컨텍스트 - 1차 캐시, 엔티티 상태, dirty checking
date: 2026-06-07 09:00:00 +0900
author: kkamji
categories: [Programming Language, Java]
tags: [java, spring, spring-data-jpa, jpa, hibernate, persistence-context]
comments: true
image:
  path: /assets/img/spring/spring.webp
---

JPA로 데이터를 다루다 보면 이상한 경험을 합니다. 엔티티의 필드를 바꾸기만 했는데 `update()` 같은 걸 부르지 않아도 DB에 반영됩니다. 같은 트랜잭션에서 같은 id를 두 번 조회하면 두 번째는 쿼리가 안 나갑니다. 이 "마법"의 정체가 **영속성 컨텍스트(persistence context)**입니다. 이번 글에서는 영속성 컨텍스트가 무엇이고(1차 캐시), 엔티티가 어떤 상태를 오가며, 변경이 어떻게 자동 반영(dirty checking)되는지를 정리합니다. Series 4(데이터 계층)의 출발점입니다.

> **TL;DR**  
> - **영속성 컨텍스트 = 1차 캐시**. id -> 엔티티의 유일한 매핑을 트랜잭션 범위에서 관리한다. 같은 id 재조회는 DB를 안 간다.  
> - 엔티티는 **transient / managed / detached / removed** 네 상태를 오간다. 상태 전이는 `persist` / `find` / `merge` / `remove` 같은 `EntityManager` 호출로 일어난다.  
> - **dirty checking**: managed 엔티티의 변경을 Hibernate가 알아서 감지해 flush 시점에 `UPDATE`로 반영한다. 명시적 update 호출이 필요 없다.  
> - **flush**는 영속성 컨텍스트의 변경을 DB와 동기화하는 과정이다(write-behind). 변경을 모아 두었다가 한 번에 `INSERT/UPDATE/DELETE`로 내보낸다.  
{: .prompt-info}

---

## 1. 영속성 컨텍스트 = 1차 캐시

JPA에서 엔티티를 관리하는 주체는 `EntityManager`(Hibernate의 `Session`)이고, 그 안에서 엔티티들이 사는 공간이 영속성 컨텍스트입니다. 공식 문서는 이를 **1차 캐시(first-level cache)**라고 부릅니다.

> A persistence context, also known as the first-level cache, holds a unique mapping of entity identifiers to entity instances that have been read or made persistent within its scope.  
> _- Hibernate ORM User Guide_  

![영속성 컨텍스트와 1차 캐시](/assets/img/spring/spring-15-persistence-context.webp)
_영속성 컨텍스트는 트랜잭션 범위의 1차 캐시. managed 엔티티(id -> entity)를 보관하고, 변경은 dirty checking으로 flush 시 DB에 write-behind된다._

핵심은 **"id마다 유일한 인스턴스"**입니다. 같은 트랜잭션에서 같은 id를 두 번 조회하면, 두 번째는 DB로 가지 않고 1차 캐시에서 같은 객체를 돌려줍니다.

```java
Member a = em.find(Member.class, 1L);  // DB 조회 -> 1차 캐시에 적재
Member b = em.find(Member.class, 1L);  // 캐시 hit (쿼리 없음)
// a == b  (동일 인스턴스 보장)
```

> 1차 캐시는 영속성 컨텍스트(보통 트랜잭션) 범위입니다. 트랜잭션이 끝나면 사라지며, 여러 트랜잭션이 공유하는 2차 캐시와는 다릅니다.  
{: .prompt-info}

---

## 2. 엔티티의 네 가지 상태

엔티티 인스턴스는 영속성 컨텍스트와의 관계에 따라 네 가지 상태를 가집니다.

> Entities within this context can be in one of four states: transient (newly instantiated, not associated with a context), managed/persistent (associated with a context and an identifier), detached (associated with an identifier but no longer with a context), or removed (associated with a context and scheduled for database removal).  
> _- Hibernate ORM User Guide_  

![JPA 엔티티 상태 전이](/assets/img/spring/spring-16-entity-states.webp)
_persist()로 transient -> managed, find()/query로 DB에서 managed 적재, detach/clear/close로 detached, merge()로 다시 managed, remove()로 removed._

- **transient (new)**: `new`로 막 만든 객체. 아직 영속성 컨텍스트와 무관하고 DB에도 없습니다.
- **managed (persistent)**: 영속성 컨텍스트가 추적 중인 상태. **이 상태에서만 dirty checking이 동작**합니다.
- **detached**: 한때 managed였지만 컨텍스트에서 분리된 상태(`em.detach()`, `em.clear()`, 트랜잭션 종료 등). id는 있지만 더 이상 추적되지 않습니다.
- **removed**: 삭제 예약 상태. flush/commit 시 `DELETE`가 나갑니다.

상태 전이는 `EntityManager` 호출로 일어납니다. `persist()`(transient -> managed), `find()/query`(DB -> managed), `merge()`(detached -> managed), `remove()`(managed -> removed).

---

## 3. dirty checking - update를 부르지 않아도 반영되는 이유

1절에서 본 "필드만 바꿨는데 반영되는" 동작의 정체입니다. managed 상태의 엔티티는 애플리케이션이 직접 수정할 수 있고, Hibernate가 그 변경을 알아서 감지합니다.

> Entities in a managed/persistent state can be modified directly by the application. Hibernate automatically detects these changes and persists them when the persistence context is flushed, without requiring explicit methods to mark modifications as persistent.  
> _- Hibernate ORM User Guide_  

```java
@Transactional
public void rename(Long id, String name) {
    Member m = em.find(Member.class, id);  // managed
    m.setName(name);                        // 필드만 변경
    // em.update(m) 같은 호출이 없다
}                                           // 커밋 시점 flush -> UPDATE 자동 발행
```

Hibernate는 엔티티를 1차 캐시에 적재할 때 **스냅샷**을 떠 두고, flush 시점에 현재 값과 비교해 바뀐 필드가 있으면 `UPDATE`를 만듭니다. 이게 dirty checking입니다.

그 변경을 실제 DB에 내보내는 과정이 **flush**입니다.

> Flushing is the process of synchronizing the state of the persistence context with the underlying database. ... The flush operation takes every entity state change and translates it to an INSERT, UPDATE or DELETE statement.  
> _- Hibernate ORM User Guide_  

즉 영속성 컨텍스트는 변경을 즉시 DB에 쓰지 않고 모아 두었다가(write-behind), flush(보통 커밋 직전, 또는 JPQL 실행 전)에 한 번에 내보냅니다.

---

## 4. 흔한 함정

- **detached 엔티티 수정은 반영되지 않는다.** dirty checking은 managed 상태에서만 동작합니다. 트랜잭션 밖에서 조회한(이미 detached된) 엔티티의 필드를 바꿔도 DB에 반영되지 않으며, 반영하려면 `merge()`로 다시 managed로 만들어야 합니다.
- **flush != commit.** flush는 SQL을 DB로 보내는 것이고, 최종 확정(commit)은 트랜잭션이 합니다. flush가 일어났다고 영구 반영된 것은 아닙니다(롤백 가능).
- **1차 캐시는 메모리에 쌓인다.** 대량의 엔티티를 한 트랜잭션에서 managed로 쌓으면 1차 캐시와 스냅샷이 모두 힙에 머뭅니다. 배치 처리에서는 주기적으로 `flush()` + `clear()`로 비워 메모리/성능을 관리합니다.

> 트랜잭션 경계가 곧 영속성 컨텍스트의 수명입니다. "언제 managed이고 언제 detached인가"는 트랜잭션이 어디서 시작하고 끝나는지에 달려 있습니다. 이 트랜잭션 이야기는 다음 편에서 다룹니다.  
{: .prompt-tip}

---

## 5. 다음 글

이번 편에서 영속성 컨텍스트(1차 캐시), 엔티티 상태, dirty checking을 봤습니다. 다음 편은 이 컨텍스트의 수명을 결정하는 **`@Transactional`과 트랜잭션 전파**를, 그다음은 **N+1 문제와 성능**을 다룹니다.

capstone 연결: managed 엔티티와 1차 캐시는 모두 [JVM 힙](/posts/jvm-memory-model/)에 상주합니다. 대량 처리에서 영속성 컨텍스트를 비우지 않으면 힙 사용이 늘고, 이는 Series 2에서 본 GC 압박/메모리 산정과 직결됩니다.

DevSecOps 비유: write-behind flush는 변경을 모아 한 번에 내보내는 **버퍼링/배치 쓰기**와 같고, dirty checking은 **선언된 상태와 실제 상태를 비교해 차이만 반영하는 reconciliation**(Terraform plan/apply, Kubernetes 컨트롤러의 desired vs actual)과 같은 발상입니다.

---

## 6. 참고 자료

- Hibernate ORM User Guide - Persistence Context / Flushing (1차 캐시, 엔티티 상태, dirty checking, flush): <https://docs.hibernate.org/orm/current/userguide/html_single/Hibernate_User_Guide.html>
- Jakarta Persistence (엔티티 생명주기 / EntityManager 스펙): <https://jakarta.ee/specifications/persistence/>
- Spring Data JPA Reference: <https://docs.spring.io/spring-data/jpa/reference/>

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
