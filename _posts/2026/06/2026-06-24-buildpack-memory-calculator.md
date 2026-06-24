---
title: 컨테이너로 가는 길 - buildpack과 Memory Calculator
date: 2026-06-24 09:00:00 +0900
author: kkamji
categories: [Programming Language, Java]
tags: [java, jvm, buildpack, paketo, memory, container]
comments: true
image:
  path: /assets/img/jvm/jvm-06-memory-calculator.webp
---

[앞 편](/posts/jvm-memory-model/)에서 "컨테이너 메모리 = Heap + Non-heap + 여유"라는 걸 봤습니다. 그런데 **`-Xmx`(Heap)를 누가 정할까요?** 내가 명시하지 않으면, Spring Boot 컨테이너 이미지에서는 **buildpack의 Memory Calculator**가 자동으로 계산합니다. 그리고 그 계산식이 앞 편의 분해 그대로입니다.

이 편은 [Series 1 4편](/posts/spring-boot-autoconfiguration/)의 fat jar가 어떻게 컨테이너가 되는지(빠진 고리)와, 그 안에서 메모리가 어떻게 나뉘는지를 잇습니다.

> **TL;DR**  
> - buildpack은 fat jar를 **Dockerfile 없이** OCI 컨테이너 이미지로 만든다 (Cloud Native Buildpacks / Paketo).  
> - 이미지의 **Memory Calculator**가 컨테이너 시작 시 컨테이너 메모리 한도에서 non-heap을 빼고 **`-Xmx`를 자동 계산**한다.  
> - 식: `Heap = total - (headroom + direct + metaspace + reserved code cache + (thread stack x thread count))`.  
> - **thread count 기본 250**, thread stack 1M -> 스레드 스택만 약 250M. 스레드 수가 가장 큰 레버다.  
{: .prompt-info}

---

## 1. 빠진 고리: fat jar는 어떻게 컨테이너가 되나

Series 1에서 앱은 fat jar로 패키징된다고 했습니다. 그 jar를 컨테이너 이미지로 만드는 한 방법이 **buildpack**입니다.

![fat jar에서 컨테이너까지](/assets/img/jvm/jvm-05-fatjar-to-container.webp)
_fat jar -> buildpack -> OCI 이미지 -> 컨테이너 실행 (Dockerfile 없이)_

---

## 2. buildpack이란

> buildpack = 소스/jar를 Dockerfile 없이 컨테이너 이미지로 변환하는 도구.  

- 표준은 **Cloud Native Buildpacks(CNB)**, 대표 구현이 **Paketo**입니다.
- Spring Boot에서는 `gradle bootBuildImage` / `mvn spring-boot:build-image`로 호출하면 Paketo가 이미지를 만듭니다.
- 이미지에는 JRE + 내 fat jar + **launch 로직**이 들어가고, 그 launch 단계에서 JVM 메모리 플래그가 자동 계산됩니다.

DevSecOps 관점 이점: 베이스 이미지/패치를 buildpack이 일관되게 관리해 재현성과 공급망 안정성이 오르고, Dockerfile 유지보수 부담이 줄어듭니다.

---

## 3. Memory Calculator: -Xmx를 자동 계산

Paketo Java buildpack의 핵심 부품이 **Memory Calculator**입니다 (Spring Boot 도 내부적으로 cloudfoundry의 java-buildpack-memory-calculator를 사용).

![Memory Calculator 차감식](/assets/img/jvm/jvm-06-memory-calculator.webp)
_컨테이너 메모리에서 non-heap을 빼고 남는 것이 Heap(-Xmx)_

계산식은 다음과 같이 명시돼 있습니다.

> total memory - (headroom amount + direct memory + metaspace + reserved code cache + (thread stack * thread count))  

> 중요: 이 계산은 빌드 때가 아니라 **컨테이너 시작 시(런타임)** 일어나며, **cgroup의 컨테이너 메모리 한도를 읽어** `-Xmx`를 정합니다. 컨테이너 메모리를 바꾸면 `-Xmx`가 자동 재계산됩니다.  
{: .prompt-warning}

---

## 4. 차감 항목과 기본값

각 항목의 기본값(공식 문서 기준)은 다음과 같습니다.

| 항목 | 기본값 | 앞 편(ep2) 연결 |
| :--- | :--- | :--- |
| Headroom | 0% (`BPL_JVM_HEAD_ROOM`) | OS/기타 여유 |
| Direct Memory | 10M (`-XX:MaxDirectMemorySize` 미설정 시) | off-heap (netty) |
| Metaspace | `5800B x 클래스 수 + 14000000B` | 클래스 메타데이터 |
| Reserved Code Cache | 240M | JIT code cache |
| Thread Stacks | `1M x thread count` | 스레드 스택 (native) |

그리고 thread count 기본값이 핵심입니다.

> `BPL_JVM_THREAD_COUNT`: "Configure the number of user threads at runtime. Defaults to 250."  

즉 **스레드 스택만 1M x 250 = 약 250M**입니다. [Series 1 3편](/posts/spring-mvc-dispatcherservlet/)의 thread-per-request(Tomcat 기본 200 스레드)가 여기 그대로 들어옵니다. 실제보다 thread count가 크게 잡혀 있으면 `-Xmx`가 부당하게 작아집니다 - **스레드 수가 가장 큰 레버**입니다.

---

## 5. 함의, 그리고 capstone

- 컨테이너 메모리를 늘리면 -> 남는 만큼 `-Xmx`가 자동으로 커진다.
- `-XX:MaxDirectMemorySize`를 명시하면 -> direct 차감액이 그 값으로 고정된다.
- thread count를 실제에 맞게 줄이면 -> 스레드 스택 차감이 줄어 `-Xmx`가 커진다.

> capstone 연결: 업무에서 마주친 "buildpack 메모리 계산", "컨테이너 메모리 증설", "MaxDirectMemorySize 설정"이 전부 이 식의 항목을 조정한 것입니다. 앞 편들의 조각 - 단일 프로세스(S1-1) / 싱글톤 빈 heap baseline(S1-2) / 스레드 스택(S1-3) / netty direct(off-heap) / heap+non-heap 분해(ep2) - 이 이 한 식으로 모입니다.  
{: .prompt-tip}

여기까지가 "메모리가 어떻게 잡히나"였습니다. 다음 편부터는 그 Heap 안에서 **GC가 어떻게 메모리를 회수하는지**(GC 기초와 G1GC)로 들어갑니다.

---

## 6. 참고 자료

- Paketo - How to build Java apps (runtime JVM 설정): <https://paketo.io/docs/howto/java/>
- java-buildpack-memory-calculator (계산식): <https://github.com/cloudfoundry/java-buildpack-memory-calculator>
- Paketo BellSoft Liberica buildpack (`BPL_JVM_THREAD_COUNT` / `BPL_JVM_HEAD_ROOM`): <https://github.com/paketo-buildpacks/bellsoft-liberica>
