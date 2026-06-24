---
title: GC 기초와 G1GC - 동작 원리와 튜닝 손잡이
date: 2026-06-24 10:00:00 +0900
author: kkamji
categories: [Programming Language, Java]
tags: [java, jvm, gc, g1gc, garbage-collection, memory]
comments: true
image:
  path: /assets/img/jvm/duke.webp
---

[ep2~3](/posts/jvm-memory-model/)에서 메모리가 "어떻게 잡히나"(Heap + Non-heap, buildpack이 -Xmx 계산)를 봤습니다. 이번 편은 그 **Heap 안에서 GC가 메모리를 어떻게 회수하는지**입니다. 그리고 이게 다음 편(업무 메모리/GC 이슈)의 토대가 됩니다.

> **TL;DR**  
> - GC는 **도달 가능성(reachability)** 으로 live/garbage를 가른다: GC roots에서 닿으면 live, 아니면 회수 대상.  
> - **weak generational 가설**("대부분 객체는 금방 죽는다") -> Heap을 young/old로 나눔. young은 **minor GC**로 자주·싸게 청소, 살아남으면 Old로 **승격**.  
> - **G1**(JDK9+ 기본)은 Heap을 **같은 크기 region**으로 쪼개고, `MaxGCPauseMillis`(기본 200ms) 목표로 수거량을 조절하며, **concurrent marking** 후 **mixed collection**으로 Old를 정리한다.  
> - marking 시작점 **IHOP는 adaptive가 기본**(초기 45%) - 다음 편 업무 이슈의 핵심.  
{: .prompt-info}

---

## 1. GC와 도달 가능성(reachability)

[1편](/posts/process-memory-layout/)에서 C는 `free`로 수동 해제, Java는 GC가 회수한다고 했습니다. GC의 판단 기준은 도달 가능성입니다.

```text
GC Roots (스택 지역변수, static 필드, JNI 등)
   | 참조를 따라감
   v
도달 가능(reachable) = live (유지)
도달 불가능          = garbage (회수)
```

기본 아이디어는 **mark(도달 가능한 것 표시) 후 회수**입니다. (reachability/mark는 GC 일반 이론으로, 특정 구현/버전과 무관합니다.)

---

## 2. Generational 가설: 대부분 객체는 금방 죽는다

핵심 관찰을 Oracle GC 튜닝 가이드는 이렇게 적습니다.

> the weak generational hypothesis, which states that most objects survive for only a short period of time  

> Efficient collection is made possible by focusing on the fact that a majority of objects "die young."  

그래서 [ep2](/posts/jvm-memory-model/)에서 본 것처럼 Heap을 young/old로 나눕니다.

![generational GC 흐름](/assets/img/jvm/jvm-07-gc-generational.webp)
_new object -> Eden -> (minor GC, aging) Survivor -> 승격 -> Old_

> The young generation consists of eden and two survivor spaces.  

> When the young generation fills up, it causes a **minor collection** in which only the young generation is collected ... a young generation full of dead objects is collected very quickly.  

즉 **Minor GC**는 young만 청소하므로, 대부분 객체가 거기서 죽는 한 자주 돌아도 쌉니다. 그리고 오래 살아남은 객체는 Old로 옮겨집니다.

> some fraction of the surviving objects from the young generation are moved to the old generation during each minor collection ... This process is also called **aging**.  

---

## 3. Major / Mixed GC, 그리고 STW

Old가 차오르면 Old를 청소해야 하는데, 전통적 generational에서는 major collection이 일어납니다.

> Eventually, the old generation fills up and must be collected, resulting in a **major collection**, in which the entire heap is collected.  

> 정밀화: 전통적 major는 "전체 heap을 한 번에" 청소합니다. 뒤에 볼 **G1의 mixed collection은 young + 선택된 일부 Old region만** 점진적으로 청소한다는 점이 다릅니다.  
{: .prompt-tip}

GC 중 일부 구간은 **Stop-The-World(STW)** 로, 앱 스레드를 잠깐 멈춥니다. 이 pause가 길어지면 지연(latency)에 직접 영향을 줍니다.

> capstone 복선: "금방 죽어야 할 객체가 Old로 잘못 승격(premature promotion)"되면 Old가 빨리 차고 무거운 Old 청소가 잦아집니다. 다음 편 업무 이슈의 핵심 증상이 이것입니다.  
{: .prompt-warning}

---

## 4. G1GC: region 기반 + pause 목표

JDK 9+ 기본 수집기인 G1을 Oracle은 이렇게 정의합니다.

> G1 is the default collector.  

> G1 is a **generational, incremental, parallel, mostly concurrent, stop-the-world, and evacuating** garbage collector  

![G1 region과 수집 사이클](/assets/img/jvm/jvm-08-g1gc-regions.webp)
_Heap = 같은 크기 region(E/S/O/H), 사이클: young -> concurrent mark(IHOP) -> mixed_

핵심은 region입니다.

> G1 partitions the heap into a set of **equally sized heap regions** ... each of these regions can be empty, or assigned to a particular generation, young or old.  

그리고 동작 3가지:

- **Pause-time 목표**: `-XX:MaxGCPauseMillis=200` ("The goal for the maximum pause time"). G1은 이 목표 안에 끝낼 만큼만 수거하도록 young 크기를 동적으로 조절합니다.
- **Concurrent Marking + IHOP**: Old 점유율이 임계치(IHOP)를 넘으면 백그라운드로 Old의 live 객체를 표시합니다. 그런데 그 임계치가 고정이 아닙니다.

> `-XX:+G1UseAdaptiveIHOP` and `-XX:InitiatingHeapOccupancyPercent=45` ... adaptive determination of that value is turned on, and that for the first few collection cycles G1 will use an occupancy of 45% of the old generation as mark start threshold.  

- **Mixed collection**: 마킹 후, young + 회수 효율 좋은 일부 Old region을 함께 수거해 Old를 정리합니다.

> ... evacuate live objects of sets of old generation regions. These collections are also called **Mixed collections**.  

---

## 5. 다음 편(업무 이슈) 예고

핵심 손잡이를 정리하면: `MaxGCPauseMillis`가 young 크기를 좌우하고, **adaptive IHOP**가 mixed 시작 시점을 좌우하며, 그 사이에서 승격이 일어납니다. JDK 버전이 바뀌어 이 손잡이들의 균형이 달라지면 "Old가 천천히 차다가 mixed GC로 한 번에 뚝 떨어지는 톱니 패턴"이 나타납니다.

다음 편에서는 이 메커니즘으로 **GC 튜닝과 JDK 17 -> 25에서의 G1 동작 변화**(일반화된 사례)를 분석합니다.

DevSecOps 비유: GC pause는 짧은 stall, `MaxGCPauseMillis`는 수집기가 맞추려는 SLO, IHOP는 "Old가 이만큼 차면 청소 시작"하는 임계치(알람 threshold 같은)입니다.

---

## 6. 참고 자료

- Oracle GC Tuning Guide (SE 21) - Garbage Collector Implementation (generational / minor / 승격): <https://docs.oracle.com/en/java/javase/21/gctuning/garbage-collector-implementation.html>
- Oracle GC Tuning Guide (SE 21) - Garbage-First (G1) Garbage Collector (region / mixed / IHOP / pause 목표): <https://docs.oracle.com/en/java/javase/21/gctuning/garbage-first-g1-garbage-collector1.html>
