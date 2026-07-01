---
title: JVM 메모리 모델 - Heap과 Non-heap, -Xmx가 제한하는 영역
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

### 3.1. 영역별 증상 - 진단 - 옵션

native 영역은 `-Xmx`처럼 한 줄로 묶이지 않고, 영역마다 터지는 증상과 진단 신호, 손잡이(옵션)가 다릅니다. heap이 멀쩡한데 컨테이너 RSS가 천천히 올라가 OOMKill로 죽는다면 거의 이쪽입니다.

**Metaspace (클래스 메타데이터)**

- 증상: `java.lang.OutOfMemoryError: Metaspace`. heap OOM(`Java heap space`)과 메시지가 다릅니다. 클래스를 동적으로 많이 생성/로드하는 경우(프록시, 코드 생성, hot reload, 클래스로더 누수)에 천천히 또는 급격히 증가합니다.
- 진단: NMT의 `Class` 카테고리, 또는 `jstat -gcmetacapacity <pid>`로 metaspace 용량 추이를 봅니다.
- 옵션: `-XX:MaxMetaspaceSize`. 명세상 method area지만 HotSpot에서는 native 메모리라 기본값이 무제한입니다.

> `-XX:MaxMetaspaceSize=size` "Sets the maximum amount of native memory that can be allocated for class metadata. By default, the size isn't limited."  

기본값이 무제한이라는 점이 함정입니다. 한도를 안 걸면 metaspace가 컨테이너 한도까지 먹다가 heap이 아니라 **컨테이너가** OOMKill될 수 있습니다.

**Thread Stacks (스레드별 호출 스택)**

- 증상: 스레드 하나가 너무 깊게 재귀하면 `java.lang.StackOverflowError`(스택 하나의 한도 초과), 스레드를 너무 많이 만들면 `OutOfMemoryError: unable to create new native thread`(스택들의 총합이 native를 압박).
- 진단: NMT의 `Thread` 카테고리(`(reserved)`/`(committed)`)와 thread 개수. 총합 = `-Xss` x 스레드 수이므로 스레드 폭증이 곧 native 폭증입니다.
- 옵션: `-Xss`(스택 하나 크기). 기본값은 플랫폼 의존이라 문서가 수치를 박지 않습니다.

> `-Xss` "Sets the thread stack size (in bytes). ... The default value depends on the platform."  

**Code Cache (JIT 컴파일 기계어)**

- 증상: code cache가 가득 차면 JIT가 컴파일을 멈추고 인터프리터로 떨어집니다. OOM으로 죽지는 않지만 **성능이 조용히 저하**됩니다(로그에 `CodeCache is full. Compiler has been disabled.`).
- 진단: NMT의 `Code` 카테고리.
- 옵션: `-XX:ReservedCodeCacheSize`. 기본 상한이 명시돼 있습니다.

> `-XX:ReservedCodeCacheSize` "Sets the maximum code cache size (in bytes) for JIT-compiled code. ... The default maximum code cache size is 240 MB; if you disable tiered compilation with the option `-XX:-TieredCompilation`, then the default size is 48 MB."  

**Direct Memory (NIO off-heap 버퍼)**

- 증상: `java.lang.OutOfMemoryError: Direct buffer memory`. netty/NIO를 쓰는 서비스(게이트웨이, 리액티브 HTTP 클라이언트)에서 트래픽이 몰릴 때 버퍼가 해제 속도를 못 따라가면 발생합니다.
- 진단: NMT의 `Other`(또는 `Internal`) 카테고리. heap이 멀쩡한데 RSS만 늘면 1순위 의심 대상입니다.
- 옵션: `-XX:MaxDirectMemorySize`. 기본 동작이 중요합니다.

> `-XX:MaxDirectMemorySize` "Sets the maximum total size (in bytes) of the `java.nio` package, direct-buffer allocations. ... If not set, the flag is ignored and the JVM chooses the size for NIO direct-buffer allocations automatically."  

명시하지 않으면 JVM이 자동으로 정하는데, HotSpot 구현에서는 그 자동값이 사실상 `-Xmx`(heap 최대치)와 같은 크기로 잡힙니다. 즉 `-Xmx`를 1GB로 주면 direct memory도 별도로 최대 1GB까지 쓸 수 있어, 컨테이너 한도 산정 시 이 native 몫을 따로 더해야 합니다. off-heap 버퍼를 많이 쓰는 서비스는 자동값에 맡기지 말고 명시적으로 한도를 거는 편이 예측 가능합니다.

### 3.2. native 실측 명령

추측 대신 실제 영역별 점유를 봐야 합니다. native 메모리는 heap GC 통계에 안 잡히므로 전용 도구가 필요합니다.

**NMT (Native Memory Tracking)**: JVM이 자기 native 사용량을 영역별로 추적하는 기능입니다. startup 플래그로 켜야 합니다.

> "The Native Memory Tracking (NMT) is a Java HotSpot VM feature that tracks internal memory usage for a Java HotSpot VM."  

```bash
# 1) startup에 NMT 활성화 (summary 또는 detail)
java -XX:NativeMemoryTracking=summary -jar app.jar

# 2) 실행 중 영역별 요약 출력 (Java/Class/Thread/Code/GC 등)
jcmd <pid> VM.native_memory summary

# 3) baseline 설정 후 증분만 추적 (누수 추적에 유용)
jcmd <pid> VM.native_memory baseline
jcmd <pid> VM.native_memory summary.diff
```

NMT는 JVM 내부 사용량만 추적하고 non-JVM native 코드 할당은 못 본다는 한계가 있으며, 활성화 시 성능이 5-10% 떨어집니다.

> "Since NMT doesn't track memory allocations by non-JVM code, you may have to use tools supported by the operating system to detect memory leaks in native code."  

**jstat (GC/영역 통계)**: heap 세대별 + metaspace 사용률을 주기적으로 찍습니다(startup 플래그 불필요).

```bash
# 1초 간격으로 GC 통계 출력 (S0/S1/Eden/Old/Metaspace 사용률 %)
jstat -gcutil <pid> 1000

# metaspace 용량/최소,최대 (Metaspace 누수 추적)
jstat -gcmetacapacity <pid>
```

**jmap (heap 덤프/요약)**: heap OOM 쪽을 의심할 때 객체 분포를 봅니다.

```bash
# heap 요약 (사용 중 GC, 세대별 capacity/used)
jmap -heap <pid>

# 살아있는 객체 히스토그램 (클래스별 인스턴스 수/바이트, 누수 클래스 탐지)
jmap -histo:live <pid>
```

진단 순서는 간단합니다. `jstat -gcutil`로 heap/metaspace가 차는지부터 보고, heap이 멀쩡한데 컨테이너 RSS만 오르면 NMT로 어느 native 카테고리(Thread/Code/Other)가 범인인지 좁힙니다.

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

### 4.1. -Xmx 고정 vs -XX:MaxRAMPercentage

컨테이너에서 heap을 어떻게 잡을지는 두 갈래입니다. 고정 바이트(`-Xmx512m`)로 박거나, 컨테이너 한도의 비율(`-XX:MaxRAMPercentage`)로 잡는 방법입니다.

> `-XX:MaxRAMPercentage=percent` "Sets the maximum amount of memory that the JVM may use for the Java heap before applying ergonomics heuristics as a percentage of the maximum amount determined as described in the `-XX:MaxRAM` option. The default value is 25 percent."  

trade-off는 이렇습니다.

- **`-Xmx` 고정**: 절대 크기가 명확해 예측 가능합니다. 단, 파드 memory limit을 바꾸면 `-Xmx`도 같이 손봐야 하고, 안 고치면 한도를 키워도 heap은 그대로라 메모리를 놀립니다.
- **`-XX:MaxRAMPercentage`**: 컨테이너 한도에 비례해 heap이 따라가므로 limit만 바꿔도 됩니다. 단, **기본값 25%**는 큰 컨테이너에서 heap을 과소 할당해 남는 메모리를 못 쓰는 함정이 있습니다(예: 4GB limit에 heap 1GB). off-heap이 적은 일반 웹 앱이라면 의도적으로 올려(예: 75%) 사용해야 합니다.

> 함정: `-XX:MaxRAMPercentage` 기본 25%를 그대로 두면 컨테이너를 키워도 heap이 1/4밖에 안 늘어 "메모리를 줬는데 왜 안 쓰지?"가 됩니다. 반대로 native(metaspace/스택/code cache/direct)가 큰 서비스에서 무턱대고 비율을 높이면 native가 들어갈 자리가 줄어 native OOM으로 돌아옵니다. 비율은 native 몫을 뺀 뒤 정해야 합니다.  
{: .prompt-warning}

---

## 5. 앞 편들, 그리고 다음 편과의 연결

```text
1편 CS stack  -> JVM Thread Stacks (native, -Xss, 스레드별)
1편 CS heap   -> JVM Heap (young/old, GC, -Xmx)
(JVM 고유)     -> Metaspace / Code Cache / Direct (off-heap)
```

> 다음 편 연결: 이 Heap + Non-heap 분해가 곧 다음 편(buildpack memory calculator)이 컨테이너 메모리를 나누는 항목이고, 운영 이슈에서 "컨테이너 메모리 > Xmx", "MaxDirectMemorySize 설정"이 나온 이유입니다.  
{: .prompt-tip}

다음 편에서는 이 분해를 자동으로 계산해주는 paketo buildpack의 memory calculator를 봅니다.

---

## 6. 참고 자료

- JVM Specification (SE 21) - Run-Time Data Areas: <https://docs.oracle.com/javase/specs/jvms/se21/html/jvms-2.html>
- The java Command (JVM 옵션: -Xmx / -Xss / -XX:MaxMetaspaceSize / -XX:ReservedCodeCacheSize / -XX:MaxDirectMemorySize / -XX:MaxRAMPercentage): <https://docs.oracle.com/en/java/javase/21/docs/specs/man/java.html>
- Java Platform Troubleshooting Guide (Native Memory Tracking, jcmd VM.native_memory): <https://docs.oracle.com/en/java/javase/21/troubleshoot/diagnostic-tools.html>

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
