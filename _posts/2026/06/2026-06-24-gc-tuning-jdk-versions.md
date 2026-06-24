---
title: GC 튜닝과 JDK 버전별 G1 거동 변화
date: 2026-06-24 11:00:00 +0900
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
- `-XX:InitiatingHeapOccupancyPercent` + `G1UseAdaptiveIHOP`: 마킹 시작 임계치(기본 adaptive)
- 진단: `-Xlog:gc*`, JFR

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

---

## 3. leak이 아니라 거동 변화

Old가 높게 유지된다고 곧 누수는 아닙니다. 위 메커니즘대로면 GC가 "덜 자주, 몰아서" 하도록 바뀐 **정상 거동**일 수 있습니다. 그리고 이 현상은 **`-Xmx`가 빠듯할 때** 더 잘 드러납니다. heap에 여유가 있으면 young을 크게 잡아도 Old가 차기까지 여유가 있어 완화되고, 빠듯하면 young 비대 -> 승격 -> Old 압박이 빨리 옵니다.

판별: 진짜 누수라면 mixed/full GC 후에도 Old의 live set이 **계속 우상향**합니다. 거동 변화면 톱니의 **저점이 일정**합니다. GC 로그 / 힙 덤프로 구분합니다.

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

- 1편: 프로세스 메모리(stack/heap) CS 기초
- 2편: JVM 메모리 모델(Heap + Non-heap)
- 3편: 컨테이너 + buildpack이 -Xmx를 계산
- 4편: GC 기초와 G1
- 5편: GC 튜닝과 JDK 버전별 거동 변화

이제 Series 1(요청이 흐르는 길)과 Series 2(JVM과 메모리)의 조각이 모두 모였습니다. 커리큘럼 마지막 **capstone**에서는 이 전부를 하나의 실전 사례로 회수합니다 - **서비스명이나 실측치 없이, 일반화된 메커니즘과 재구성된 예시로만** 다룹니다.

DevSecOps 비유: 런타임 업그레이드는 "성능 개선"이지만 GC 휴리스틱의 균형점을 옮길 수 있으므로, 업그레이드 후엔 메모리/GC 지표를 baseline과 비교 관측하는 게 안전합니다.

---

## 6. 참고 자료

- Oracle GC Tuning Guide (SE 21) - Garbage-First Garbage Collector Tuning (young 크기 / pause 목표): <https://docs.oracle.com/en/java/javase/21/gctuning/garbage-first-garbage-collector-tuning.html>
- Oracle GC Tuning Guide (SE 21) - Garbage-First (G1) Garbage Collector (adaptive IHOP / mixed): <https://docs.oracle.com/en/java/javase/21/gctuning/garbage-first-g1-garbage-collector1.html>
