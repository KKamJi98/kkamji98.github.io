---
title: Spring/JVM Capstone - 업그레이드 후 Old gen과 off-heap 메모리 진단
date: 2026-06-08 17:00:00 +0900
author: kkamji
categories: [Programming Language, Java]
tags: [java, jvm, gc, g1gc, spring-boot, netty, memory]
comments: true
image:
  path: /assets/img/jvm/duke.webp
---

이 커리큘럼은 하나의 질문에서 시작했습니다. **"Spring Boot 메이저 업그레이드(새 JDK/G1GC 동반) 이후, Old gen이 예전보다 높게 유지되고 컨테이너 메모리가 빠듯해 보인다. 메모리 누수일까?"** 마지막 글에서는 Series 1~4에서 쌓은 조각(요청 처리, JVM 메모리, GC, 동시성, 데이터 계층)을 모아 이 질문을 끝까지 진단합니다.

> 이 글은 특정 서비스의 실제 수치가 아니라, **일반화된 메커니즘과 재구성된 예시**로만 다룹니다. 등장하는 숫자는 설명용 가정값입니다.  
{: .prompt-warning}

> **TL;DR**  
> - "Old gen이 높다"는 그 자체로 누수가 아니다. **G1은 Old를 mixed GC로 점진 회수**하고, IHOP(Initiating Heap Occupancy) 전까지는 Old를 높게 들고 있는다(설계상 정상).  
> - JDK 업그레이드는 **adaptive IHOP/휴리스틱을 바꿔** 같은 워크로드에서도 Old 점유 baseline을 이동시킬 수 있다. 회귀가 아니라 새 기준선이다.  
> - **heap만 보면 안 된다.** netty 같은 off-heap(direct memory)은 `-Xmx` 바깥이라, 컨테이너 OOMKill인데 heap은 여유인 경우가 있다.  
> - 처방은 **측정 기반**으로: `MaxNewSize`/`IHOP`로 GC 거동을, `MaxDirectMemorySize`로 off-heap을 다루고, 컨테이너 메모리는 heap + off-heap을 모두 담아야 한다.  
{: .prompt-info}

---

## 1. 증상과 첫 질문

일반화된 시나리오는 이렇습니다. 잘 돌던 Spring 애플리케이션을 메이저 업그레이드(프레임워크 + 새 JDK + 그에 딸린 G1GC)했더니, 업그레이드 후 **Old gen 사용량이 이전보다 높은 수준에서 머무릅니다.** 그래프만 보면 "메모리가 안 빠진다 = 누수"처럼 보이고, 컨테이너 메모리도 빠듯해 보입니다.

여기서 바로 "누수"로 결론 내리면 엉뚱한 곳을 파게 됩니다. [장애 분석의 기본](/posts/jvm-memory-model/)대로, 단일 수치가 아니라 **거동(시간에 따른 추이)과 baseline**을 먼저 봐야 합니다.

---

## 2. 진단: 누수인가, GC 거동인가, off-heap인가

세 갈래로 나눠 봅니다.

![Old gen 높음 진단 플로우](/assets/img/jvm/jvm-11-capstone-diagnosis.webp)
_mixed GC 후에도 live가 계속 우상향이면 누수, heap은 여유인데 컨테이너가 OOMKill이면 off-heap, Old는 높지만 회수되고 안정적이면 G1의 지연 회수(정상)._

- **누수**: mixed GC가 돌고 난 뒤에도 live set이 시간에 따라 **계속 우상향**한다면 진짜 누수 신호입니다. heap dump로 어떤 객체가 쌓이는지 봅니다.
- **off-heap**: heap(`-Xmx`)은 여유로운데 **컨테이너가 OOMKill** 된다면, 범인은 heap 밖입니다. direct memory / metaspace / thread stack 같은 off-heap을 봐야 합니다([JVM 메모리 모델](/posts/jvm-memory-model/) 참고).
- **GC 거동**: Old가 높지만 mixed GC 후 회수되고 일정 수준에서 **안정적**이라면, 이건 누수가 아니라 G1의 정상 동작입니다. 다음 절이 그 이유입니다.

---

## 3. 왜 Old gen이 높게 유지되나 - G1의 지연 회수

[GC 기초와 G1GC](/posts/gc-basics-g1gc/) 편에서 본 것처럼, G1은 Old를 한 번에 비우지 않고 **mixed collection으로 점진적으로** 회수합니다.

> The space-reclamation phase is where G1 reclaims space in the old generation incrementally, in addition to handling the young generation.  
> _- Oracle GC Tuning Guide, Garbage-First (G1) Garbage Collector_  

그리고 이 Old 회수(space-reclamation)는 아무 때나 시작되지 않습니다. Old 점유율이 **IHOP(Initiating Heap Occupancy) 임계치**에 도달해야 시작됩니다.

> The transition between the young-only phase and the space-reclamation phase starts when the old generation occupancy reaches a certain threshold, the Initiating Heap Occupancy threshold.  
> _- Oracle GC Tuning Guide, Garbage-First (G1) Garbage Collector_  

즉 **IHOP에 닿기 전까지 Old를 높게 들고 있는 것은 G1의 설계된 동작**입니다. "안 빠지는" 게 아니라 "아직 빼야 할 때가 아닌" 것입니다. 게다가 G1은 기본적으로 IHOP를 자동으로 조정합니다.

> G1 by default automatically determines an optimal IHOP by observing how long marking takes and how much memory is typically allocated in the old generation during marking cycles.  
> _- Oracle GC Tuning Guide, Garbage-First (G1) Garbage Collector_  

여기서 업그레이드 이야기와 연결됩니다. [GC 튜닝과 JDK 버전](/posts/gc-tuning-jdk-versions/) 편에서 봤듯, JDK가 바뀌면 G1의 기본값과 adaptive 휴리스틱이 달라질 수 있습니다. 그러면 **같은 워크로드라도 Old 점유 baseline이 이전과 다르게 잡힐 수 있습니다.** 이것은 코드의 회귀가 아니라 GC가 새로 잡은 기준선입니다.

---

## 4. off-heap도 함께 봐야 한다 - netty와 컨테이너 메모리

heap만 보는 함정은 특히 [WebFlux/netty](/posts/spring-webflux-netty-event-loop/) 기반 앱에서 큽니다. netty는 소켓 I/O 버퍼로 **direct memory(off-heap)**를 쓰는데, 이건 `-Xmx`가 관리하는 heap **바깥**입니다.

그래서 컨테이너 메모리는 heap만이 아니라 off-heap까지 모두 담아야 합니다. [buildpack memory calculator](/posts/buildpack-memory-calculator/) 편에서 본 것처럼, 컨테이너 메모리는 다음을 모두 포함해야 합니다.

```text
컨테이너 메모리 >= heap(-Xmx) + direct memory + metaspace + thread stacks + code cache + ...
```

`-XX:MaxDirectMemorySize`로 off-heap 상한을 명시하지 않으면, 동시 커넥션이 많을 때 direct memory가 늘어 컨테이너 한도를 넘길 수 있습니다. 이때 heap 그래프만 보면 멀쩡해 보이므로 진단이 헛돕니다.

---

## 5. 처방

원인이 정리되면 처방은 명확해집니다. 핵심은 "관찰된 원인(누수 아님)"을 그에 맞는 레버로 다루는 것입니다.

![원인과 처방 레버](/assets/img/jvm/jvm-12-capstone-levers.webp)
_Old 점유는 MaxNewSize/IHOP로, off-heap은 MaxDirectMemorySize로, 컨테이너 메모리는 heap+off-heap 합으로 다룬다. 수치는 측정해서 정한다._

- **`MaxNewSize`**: young 영역 상한을 두어 Old로의 승격 속도와 Old 증가를 관리합니다.
- **IHOP 하향**: mixed GC를 더 일찍 트리거해 Old 회수를 앞당깁니다(adaptive를 끄고 고정하거나 임계치를 낮춤).
- **`MaxDirectMemorySize` 명시**: off-heap 상한을 정해 컨테이너 한도와 정합을 맞춥니다.
- **컨테이너 메모리 산정**: heap + off-heap을 모두 담도록 잡습니다.

> 구체적 수치(young 크기, IHOP %, direct 상한)는 정답이 따로 없습니다. 워크로드별로 **측정**하고, 변경 전후를 **baseline과 비교**해 검증해야 합니다. 단일 수치로 "정상/이상"을 단정하지 않는 것이 핵심입니다.  
{: .prompt-tip}

---

## 6. 커리큘럼 회수

이 한 건의 진단에 커리큘럼 전체가 들어왔습니다.

| 시리즈 | 이 진단에서의 역할 |
| :--- | :--- |
| [Series 1 요청 처리](/posts/spring-mvc-dispatcherservlet/) | thread-per-request면 스레드 스택(off-heap)도 메모리 항목. 동시성 모델이 메모리 성격을 가른다 |
| [Series 2 JVM/메모리/GC](/posts/jvm-memory-model/) | heap/non-heap 분해, buildpack 메모리 산정, G1 동작과 튜닝 - 이 글의 토대 전부 |
| [Series 3 WebFlux/netty](/posts/spring-webflux-netty-event-loop/) | netty의 direct memory(off-heap)가 컨테이너 메모리에 들어가는 이유 |
| [Series 4 데이터 계층](/posts/jpa-n-plus-1/) | 대량 엔티티/1차 캐시가 heap에 쌓이는 또 다른 압박원 |

요청이 흐르는 길, 그 요청이 쓰는 메모리, 그 메모리를 청소하는 GC, 그리고 데이터 계층까지 - 따로 배운 조각들이 하나의 메모리 진단에서 만났습니다.

---

## 7. 마치며

가장 큰 교훈은 단순합니다. **"높다"가 "샌다"는 아니다.** 업그레이드 후의 거동 변화는 회귀가 아니라 새 기준선일 수 있고, 그 판단은 메커니즘 이해 + baseline 비교 + evidence로 해야 합니다.

DevSecOps 비유: 런타임/플랫폼 업그레이드 후 지표가 달라지는 것은 흔한 일이고, 그때마다 "회귀"로 단정하기보다 **baseline을 재설정하고 비교 관측**하는 것이 안전합니다. 추측으로 방향을 정하지 않고, golden signal과 canary로 변화를 측정해 좁혀가는 태도는 GC 튜닝이든 인프라 변경이든 똑같이 적용됩니다.

여기까지가 Spring/JVM 커리큘럼의 마지막입니다. 프레임워크의 "마법"을 한 겹씩 벗겨 메커니즘으로 바꾸는 것이 이 시리즈의 목표였고, 그 마지막 증명이 이 진단이었습니다.

---

## 8. 참고 자료

- Oracle GC Tuning Guide (SE 21) - Garbage-First (G1) Garbage Collector (space-reclamation / IHOP / adaptive): <https://docs.oracle.com/en/java/javase/21/gctuning/garbage-first-g1-garbage-collector1.html>
- Oracle GC Tuning Guide (SE 21) - Garbage-First Garbage Collector Tuning (young 크기 / pause 목표): <https://docs.oracle.com/en/java/javase/21/gctuning/garbage-first-garbage-collector-tuning.html>
- The java Command (SE 21) - JVM 옵션(-Xmx / -XX:MaxNewSize / -XX:MaxDirectMemorySize / IHOP): <https://docs.oracle.com/en/java/javase/21/docs/specs/man/java.html>

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
