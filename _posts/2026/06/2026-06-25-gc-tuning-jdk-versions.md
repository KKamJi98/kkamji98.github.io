---
title: GC 튜닝과 JDK 버전별 G1 거동 변화
date: 2026-06-25 09:00:00 +0900
author: kkamji
categories: [Programming Language, Java]
tags: [java, jvm, gc, g1gc, tuning, jdk]
comments: true
image:
  path: /assets/img/jvm/duke.webp
---

[앞 편](/posts/gc-basics-g1gc/)에서 G1의 기계장치(pause 목표, adaptive IHOP, mixed collection)를 봤습니다. Series 2의 마지막인 이번 편은 그 손잡이를 **튜닝**하거나, **JDK 버전이 G1의 휴리스틱을 바꿀 때** 메모리 곡선이 어떻게 달라지는지를 다룹니다.

흔한 증상 하나: "런타임(JDK) 업그레이드 후 Old gen이 예전보다 높게 유지된다." 결론부터 말하면 이건 보통 **메모리 누수가 아니라 GC 동작 방식의 변화**입니다. 그 메커니즘을 일반화해서 봅니다.

> **TL;DR**  
> - G1은 **young 크기를 pause 목표에 맞춰 조절**한다 (young = pause-time의 핵심 레버).  
> - 그래서 GC가 빨라지면(JDK 업그레이드 등) 같은 pause 목표 안에서 **young이 커지고 -> minor GC가 줄고 -> adaptive IHOP가 마킹을 미루고 -> 승격이 늘어 Old가 톱니로 높게 유지**될 수 있다.  
> - 이건 **leak이 아니라 거동 변화**이며 `-Xmx`가 빠듯할수록 두드러진다.  
> - 처방으로 young을 고정(`-XX:MaxNewSize`)하면 승격은 줄지만 **Oracle은 이를 경고**한다(pause-time 제어가 꺼짐). 무엇이든 **측정 후** 결정.  
{: .prompt-info}

---

## 1. 핵심 튜닝 손잡이

![G1 튜닝 파라미터](/assets/img/jvm/jvm-09-gc-tuning-params.webp)
_각 플래그가 제어하는 것_

- `-Xms` / `-Xmx`: 초기 / 최대 heap
- `-XX:MaxGCPauseMillis`(기본 200): pause 목표
- `-XX:MaxNewSize` / `-Xmn`: young 상한
- `-XX:InitiatingHeapOccupancyPercent`(기본 45) + `G1UseAdaptiveIHOP`: 마킹 시작 임계치(기본 adaptive)
- 진단: `-Xlog:gc*`, JFR

여기서 IHOP 플래그와 adaptive 모드의 관계를 먼저 정리해야 혼란이 없습니다. **adaptive IHOP가 켜진 기본 상태에서 `-XX:InitiatingHeapOccupancyPercent`는 "고정 임계치"가 아니라 "초기 추정값"입니다.** Oracle 가이드 본문이 명확히 못 박습니다.

> If this feature is active, then the option `-XX:InitiatingHeapOccupancyPercent` determines the initial value as a percentage of the size of the current old generation as long as there aren't enough observations to make a good prediction of the Initiating Heap Occupancy threshold. Turn off this behavior of G1 using the option`-XX:-G1UseAdaptiveIHOP`. In this case, the value of `-XX:InitiatingHeapOccupancyPercent` always determines this threshold.  

즉 adaptive가 켜진 동안에는 G1이 마킹 소요 시간과 old 할당량을 관측해 임계치를 스스로 옮기고, IHOP 값은 관측이 쌓이기 전 초기 몇 사이클에만 쓰입니다(기본 45%). adaptive를 끄면(`-XX:-G1UseAdaptiveIHOP`) 비로소 IHOP 값이 **항상** 임계치로 고정됩니다. 그래서 "IHOP를 45로 박았는데 왜 안 지켜지나"는 보통 버그가 아니라 adaptive가 켜진 정상 동작입니다.

> Defaults for controlling the initiating heap occupancy indicate that adaptive determination of that value is turned on, and that for the first few collection cycles G1 will use an occupancy of 45% of the old generation as mark start threshold.  

여기서 가장 중요한 사실 하나를 Oracle G1 튜닝 가이드가 못 박습니다.

> the young generation size is the main means for G1 to allow it to meet the pause-time.  

즉 **young 크기가 G1이 pause 목표를 맞추는 핵심 수단**입니다. 그리고 young 수거 비용은 크기에 비례합니다.

> any young collection roughly takes time proportional to the size of the young generation  

---

## 2. 인과 사슬: JDK가 올라가면 왜 Old 거동이 바뀌나

![JDK 버전별 G1 거동 변화](/assets/img/jvm/jvm-10-jdk-version-gc-shift.webp)
_faster G1 -> young 비대 -> minor GC 감소 -> IHOP 지연 -> 승격 -> Old 톱니 (일반 예시)_

위 building block(young = pause 레버, 비용 비례, adaptive IHOP)을 이으면 다음 연쇄가 됩니다.

```text
새 JDK에서 G1이 더 빨라짐 (pause 단축)
 -> 같은 pause 목표 안에 young을 더 크게 잡음
 -> young이 크니 minor GC 횟수 감소
 -> adaptive IHOP가 concurrent marking을 뒤로 미룸
 -> 그 사이 객체가 Old로 더 승격됨 (premature promotion)
 -> Old가 높게 유지되다 mixed GC로 한 번에 정리 = 톱니(sawtooth)
```

> 정직한 구분: "young = pause 레버", "adaptive IHOP", "young 비용 비례"는 공식 문서로 확인된 사실입니다. 하지만 **"JDK N이 이렇게 만든다"고 명시한 문서는 없습니다.** 위 버전별 연쇄는 그 사실들 위에 선 **합리적 추론 + 관측되는 일반 패턴**이고, premature promotion은 일반 GC 개념(앞 편의 승격)입니다. 실제로는 GC 로그로 확인해야 합니다.  
{: .prompt-warning}

### 2.1. 버전 변경은 실제로 GC 기본값을 바꾼다

세부 휴리스틱이 "JDK N에서 이렇게 변했다"는 변경점을 한 줄로 추적하기는 어렵지만, **GC 기본값 자체가 버전에서 바뀐 사례는 릴리스 문서로 확정됩니다.** 가장 큰 변곡점은 JDK 9입니다. JEP 248이 default collector를 Parallel GC에서 G1으로 교체했습니다.

> Make G1 the default garbage collector on 32- and 64-bit server configurations.  

또한 현재 G1은 IHOP를 관측 기반으로 스스로 조정하는 adaptive IHOP를 기본으로 켜고(앞 절 인용), region 크기(`-XX:G1HeapRegionSize`)는 max heap에 따라 ergonomic으로 결정합니다(약 2048개 region을 목표, 상한 32MB).

> The default value is based on the maximum heap size and it is calculatedto render roughly 2048 regions, with a maximum ergonomically determined value of 32 MB.  

즉 `-Xmx`가 바뀌면 region 크기와 region 개수가 함께 바뀌고, 같은 코드라도 collector 종류 자체가 버전 경계에서 달라질 수 있습니다. 이 한 가지만으로도 "런타임만 올렸는데 메모리 곡선이 달라졌다"가 충분히 설명됩니다 - 버전별 미세 휴리스틱 변화는 그 위에 더해지는 효과입니다.

---

## 3. leak이 아니라 거동 변화

Old가 높게 유지된다고 곧 누수는 아닙니다. 위 메커니즘대로면 GC가 "덜 자주, 몰아서" 하도록 바뀐 **정상 거동**일 수 있습니다. 그리고 이 현상은 **`-Xmx`가 빠듯할 때** 더 잘 드러납니다. heap에 여유가 있으면 young을 크게 잡아도 Old가 차기까지 여유가 있어 완화되고, 빠듯하면 young 비대 -> 승격 -> Old 압박이 빨리 옵니다.

판별: 진짜 누수라면 mixed/full GC 후에도 Old의 live set이 **계속 우상향**합니다. 거동 변화면 톱니의 **저점이 일정**합니다. GC 로그 / 힙 덤프로 구분합니다.

### 3.1. `-Xlog:gc*`로 보는 Pause Young vs Mixed

`-Xlog:gc*`를 켜면 collection마다 종류와 전후 heap 점유가 한 줄씩 남습니다. 아래는 **수치를 일반화해 재구성한** 발췌입니다(실측 로그 아님). 먼저 평상시에는 `Pause Young (Normal)`이 반복되며 young을 비웁니다.

```text
[12.030s][info][gc] GC(41) Pause Young (Normal) (G1 Evacuation Pause) 820M->210M(2048M) 6.142ms
[14.880s][info][gc] GC(42) Pause Young (Normal) (G1 Evacuation Pause) 845M->232M(2048M) 6.503ms
```

old 점유가 IHOP 임계치를 넘으면 G1이 concurrent marking 사이클을 시작합니다. 로그에는 `Pause Young (Concurrent Start)` -> `Concurrent Mark Cycle`로 나타나고, 이때부터 마킹이 트리거된 것입니다.

```text
[31.204s][info][gc] GC(58) Pause Young (Concurrent Start) (G1 Humongous Allocation) 940M->300M(2048M) 7.880ms
[31.205s][info][gc] GC(59) Concurrent Mark Cycle
[31.560s][info][gc] GC(59) Concurrent Mark Cycle 355.018ms
```

마킹이 끝나면 회수 가능 region을 가려낸 뒤 `Pause Young (Prepare Mixed)`을 거쳐 `Pause Mixed`가 돕니다. **Mixed가 young과 함께 old region을 같이 비우므로** old 점유가 한 번에 크게 떨어집니다 - 이 지점이 톱니의 하강 구간입니다.

```text
[33.870s][info][gc] GC(64) Pause Young (Prepare Mixed) (G1 Evacuation Pause) 980M->360M(2048M) 7.214ms
[36.410s][info][gc] GC(65) Pause Mixed (G1 Evacuation Pause) 990M->250M(2048M) 9.030ms
```

판별 포인트: Mixed/Concurrent 사이클 직후의 점유(위 예시의 `->250M`)가 **사이클마다 일정**하면 거동 변화, 사이클을 거듭할수록 **저점이 계속 올라가면** live set 증가, 즉 누수 의심입니다.

### 3.2. JFR로 보는 톱니

JDK Flight Recorder의 `jdk.GCHeapSummary` / `jdk.G1HeapRegionStatistics` 이벤트를 시간축으로 그리면 old 점유가 **상승 -> Mixed에서 급락 -> 다시 상승**을 반복하는 톱니가 그대로 보입니다. 아스키로 그린 개념도입니다.

```text
old gen
점유   ^
  90% -|        /|        /|        /|
       |       / |       / |       / |
  60% -|      /  |      /  |      /  |
       |     /   |     /   |     /   |
  30% -|____/    |____/    |____/    |____  <- Mixed 직후 저점(일정하면 거동 변화)
       +----------------------------------> time
            ^ IHOP 도달          ^ Mixed GC
```

저점선이 우상향(점선이 계단처럼 올라감)이면 누수, 수평이면 정상 톱니라는 판별이 JFR 그래프에서는 한눈에 됩니다.

---

## 4. 처방과 트레이드오프

흔히 거론되는 손잡이는 young 고정입니다.

- `-XX:MaxNewSize`로 **young 상한을 묶으면**: minor GC가 자주 돌아 단명 객체가 young에서 죽고, Old 승격이 줄어듭니다.

그런데 Oracle은 이 방법을 **경고**합니다.

> Avoid limiting the young generation size ... using options like `-Xmn` ... because the young generation size is the main means for G1 to allow it to meet the pause-time.  

> Setting the young generation size to a single value overrides and practically disables pause-time control.  

즉 young을 고정하면 **G1의 pause-time 자동 제어가 꺼집니다.** young GC가 잦아져 pause 빈도가 늘 수 있고, 처리량/지연 트레이드오프가 생깁니다. IHOP를 낮게 고정해 마킹을 당기는 방법도 있지만 너무 낮으면 마킹이 과해져 CPU를 더 씁니다.

> 그래서 결론은 하나입니다: **GC 로그/JFR로 before-after를 측정하고 결정한다.** 단정하지 않는다.  
{: .prompt-tip}

---

## 5. Series 2 정리, 그리고 capstone

Series 2로 "앱 아래의 세계"를 훑었습니다.

- 1편: [프로세스 메모리(stack/heap) CS 기초](/posts/process-memory-layout/)
- 2편: [JVM 메모리 모델(Heap + Non-heap)](/posts/jvm-memory-model/)
- 3편: [컨테이너 + buildpack이 -Xmx를 계산](/posts/buildpack-memory-calculator/)
- 4편: [GC 기초와 G1](/posts/gc-basics-g1gc/)
- 5편: GC 튜닝과 JDK 버전별 거동 변화 (이 글)

이제 Series 1(요청이 흐르는 길)과 Series 2(JVM과 메모리)의 조각이 모두 모였습니다. 커리큘럼 마지막 **capstone**에서는 이 전부를 하나의 실전 사례로 회수합니다 - **서비스명이나 실측치 없이, 일반화된 메커니즘과 재구성된 예시로만** 다룹니다.

DevSecOps 비유: 런타임 업그레이드는 "성능 개선"이지만 GC 휴리스틱의 균형점을 옮길 수 있으므로, 업그레이드 후엔 메모리/GC 지표를 baseline과 비교 관측하는 게 안전합니다.

---

## 6. 참고 자료

- Oracle GC Tuning Guide (SE 21) - Garbage-First Garbage Collector Tuning (young 크기 / pause 목표): <https://docs.oracle.com/en/java/javase/21/gctuning/garbage-first-garbage-collector-tuning.html>
- Oracle GC Tuning Guide (SE 21) - Garbage-First (G1) Garbage Collector (adaptive IHOP / IHOP 기본 45 / region size ergonomic / mixed): <https://docs.oracle.com/en/java/javase/21/gctuning/garbage-first-g1-garbage-collector1.html>
- OpenJDK - JEP 248: Make G1 the Default Garbage Collector (JDK 9에서 default collector 교체): <https://openjdk.org/jeps/248>

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
