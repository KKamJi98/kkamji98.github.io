---
title: JVM 메모리 모델 - Heap과 Non-heap, 그리고 -Xmx의 진실
date: 2026-06-23 12:00:00 +0900
author: kkamji
categories: [Programming Language, Java]
tags: [java, jvm, memory, heap, metaspace, off-heap]
comments: true
image:
  path: /assets/img/jvm/duke.webp
---

[앞 편](/posts/process-memory-layout/)에서 프로세스 메모리가 stack/heap 등으로 나뉜다는 CS 기초를 다시 잡았습니다. 이번 편은 그 위에서 **JVM이 자기 메모리를 어떤 영역으로 조직하는지**를 봅니다. JVM도 하나의 프로세스지만, 자기만의 "런타임 데이터 영역(runtime data areas)"으로 메모리를 관리합니다.

이 편의 한 문장: **`-Xmx`는 Heap만 제한한다.** 나머지는 전부 그 바깥의 native 메모리이고, 컨테이너 메모리는 그 둘을 다 합친 것입니다.

> **TL;DR**  
> - JVM 메모리는 **Heap(공유, GC 관리, `-Xmx`)** 과 **Non-heap/native(metaspace, 스레드 스택, code cache, direct)** 로 갈린다.  
> - Heap은 모든 객체가 사는 곳이고, HotSpot에서는 young(eden+survivor)/old로 나뉜다.  
> - Metaspace(클래스 메타데이터), 스레드 스택(`-Xss`), code cache, direct memory(`-XX:MaxDirectMemorySize`)는 전부 **`-Xmx` 바깥의 native**다.  
> - 컨테이너 메모리 = Heap + Non-heap + 여유. **`-Xmx`만 보면 안 된다.**  
{: .prompt-info}

---

## 1. JVM 런타임 데이터 영역

JVM은 메모리를 용도별 영역으로 나눕니다. 큰 구분은 **Heap vs Non-heap**입니다.

![JVM 메모리 영역](/assets/img/jvm/jvm-03-jvm-memory-areas.webp)
_Heap(객체, GC, -Xmx) vs Non-heap/native(metaspace, 스레드 스택, code cache, direct)_

---

## 2. Heap: 객체가 사는 곳, GC가 관리

JVM 명세는 Heap을 이렇게 정의합니다.

> The Java Virtual Machine has a heap that is shared among all Java Virtual Machine threads. The heap is the run-time data area from which memory for all class instances and arrays is allocated. ... Heap storage for objects is reclaimed by an automatic storage management system (known as a garbage collector); objects are never explicitly deallocated.  

- 모든 객체/배열이 사는 **공유** 영역이고, **`-Xmx`가 상한**입니다.
- HotSpot의 generational GC는 Heap을 **Young(Eden + Survivor) + Old**로 나눕니다. 새 객체는 Eden에 태어나고, 살아남으면 Survivor를 거쳐 Old로 **승격(promotion)** 됩니다. (GC 동작은 뒤 편에서 깊게)
- [2편](/posts/spring-ioc-di-container/)의 싱글톤 빈들이 여기 상주하며 baseline 힙 점유를 만듭니다.

> 정밀화: 명세는 "no particular type of automatic storage management system"이라고 해서 GC 방식을 규정하지 않습니다. **young/old 분할은 HotSpot의 generational 구현**이지 JVM 명세 강제가 아닙니다.  
{: .prompt-tip}

---

## 3. Non-heap (native): -Xmx 바깥의 세계

여기가 이번 편의 핵심이자 자주 놓치는 부분입니다. JVM 명세는 스레드별 스택과 클래스 메타데이터 영역을 따로 둡니다.

> (JVM Stack) Each Java Virtual Machine thread has a private Java Virtual Machine stack ... A Java Virtual Machine stack stores frames ... it holds local variables and partial results ...  

> (Method Area) The Java Virtual Machine has a method area that is shared among all Java Virtual Machine threads. ... It stores per-class structures such as the run-time constant pool, field and method data, and the code for methods ...  

정리하면 Non-heap/native 영역은 다음과 같습니다.

| 영역 | 무엇 | 크기 옵션 |
| :--- | :--- | :--- |
| Metaspace | 클래스 메타데이터 (명세의 "method area"를 HotSpot이 구현. JDK8+, PermGen 대체) | `-XX:MaxMetaspaceSize` |
| Thread Stacks | 스레드별 호출 스택 (= 1편 stack) | `-Xss` x 스레드 수 |
| Code Cache | JIT가 컴파일한 기계어 | `-XX:ReservedCodeCacheSize` |
| Direct Memory | NIO/netty의 off-heap 버퍼 | `-XX:MaxDirectMemorySize` |

> 정밀화: 명세 용어는 "method area"이고, **HotSpot이 이를 Metaspace로 구현**합니다(JDK8에서 PermGen을 native 메모리 Metaspace로 대체). 그래서 "method area(명세) = Metaspace(HotSpot)"로 보면 됩니다.  
{: .prompt-tip}

`java` 도구 문서도 이를 뒷받침합니다.

> `-Xmx` "Specifies the maximum size ... of the heap." / `-Xss` "Sets the thread stack size." / `-XX:MaxDirectMemorySize` "Sets the maximum total size ... of the java.nio package, direct-buffer allocations."  

즉 **`-Xmx`는 Heap만 제한**하고, metaspace/스택/code cache/direct는 각각 별도의 native 영역입니다.

---

## 4. 컨테이너 메모리 = Heap + Non-heap + 여유

그래서 컨테이너 메모리 한도는 이렇게 구성됩니다.

![컨테이너 메모리 분해](/assets/img/jvm/jvm-04-container-memory-breakdown.webp)
_컨테이너 메모리 = Heap(-Xmx) + metaspace + 스레드 스택 + code cache + direct + 여유_

```text
컨테이너 memory limit
 = Heap (-Xmx)
 + Metaspace
 + Thread Stacks (-Xss x 스레드 수)
 + Code Cache
 + Direct Memory
 + Headroom (기타 native, OS)
```

> 컨테이너에 1.5GB를 주고 `-Xmx`도 1.5GB로 잡으면 non-heap이 들어갈 자리가 없어 컨테이너 OOMKill 또는 native OOM이 납니다. `-Xmx`는 "남는 자리"가 아니라 "전체에서 non-heap을 뺀 자리"로 잡아야 합니다.  
{: .prompt-warning}

DevSecOps 비유: 파드 memory limit을 산정할 때 앱 힙만 생각하면 안 되고 native까지 합쳐 잡아야 하는 것과 같습니다.

---

## 5. Series 1, 그리고 capstone과의 연결

```text
1편 CS stack  -> JVM Thread Stacks (native, -Xss, 스레드별)   [S1-3편 "스레드 스택=native"]
1편 CS heap   -> JVM Heap (young/old, GC, -Xmx)              [S1-2편 싱글톤 빈 baseline]
(JVM 고유)     -> Metaspace / Code Cache / Direct(off-heap)   [netty = Direct, S1 netty 언급]
```

> capstone 연결: 이 Heap + Non-heap 분해가 곧 다음 편(buildpack memory calculator)이 컨테이너 메모리를 나누는 항목이고, 업무 이슈에서 "컨테이너 메모리 > Xmx", "MaxDirectMemorySize 설정"이 나온 이유입니다.  
{: .prompt-tip}

다음 편에서는 이 분해를 자동으로 계산해주는 paketo buildpack의 memory calculator를 봅니다.

---

## 6. 참고 자료

- JVM Specification (SE 21) - Run-Time Data Areas: <https://docs.oracle.com/javase/specs/jvms/se21/html/jvms-2.html>
- The java Command (JVM 옵션: -Xmx / -Xss / -XX:MaxDirectMemorySize): <https://docs.oracle.com/en/java/javase/21/docs/specs/man/java.html>
