---
title: buildpack과 JVM Memory Calculator
date: 2026-06-25 08:00:00 +0900
author: kkamji
categories: [Programming Language, Java]
tags: [java, jvm, buildpack, paketo, memory, container]
comments: true
image:
  path: /assets/img/jvm/duke.webp
---

[앞 편](/posts/jvm-memory-model/)에서 "컨테이너 메모리 = Heap + Non-heap + 여유"라는 걸 봤습니다. 그런데 **`-Xmx`(Heap)를 누가 정할까요?** 명시하지 않으면, Spring Boot 컨테이너 이미지에서는 **buildpack의 Memory Calculator**가 자동으로 계산합니다. 그리고 그 계산식이 앞 편의 분해 그대로입니다.

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
- 이미지에는 JRE + 애플리케이션 fat jar + **launch 로직**이 들어가고, 그 launch 단계에서 JVM 메모리 플래그가 자동 계산됩니다.

DevSecOps 관점 이점: 베이스 이미지/패치를 buildpack이 일관되게 관리해 재현성과 공급망 안정성이 오르고, Dockerfile 유지보수 부담이 줄어듭니다.

---

## 3. Memory Calculator: -Xmx를 자동 계산

Paketo Java buildpack의 핵심 부품이 **Memory Calculator**입니다. 의존 체인을 한 줄로 정리하면, Spring Boot의 `bootBuildImage`는 기본 builder로 `paketobuildpacks/builder-noble-java-tiny`(Paketo)를 호출하고, 그 Paketo BellSoft Liberica buildpack이 cloudfoundry의 java-buildpack-memory-calculator를 launch layer에 심어 컨테이너 시작 시 `-Xmx`를 계산합니다.

![Memory Calculator 차감식](/assets/img/jvm/jvm-06-memory-calculator.webp)
_컨테이너 메모리에서 non-heap을 빼고 남는 것이 Heap(-Xmx)_

계산식은 다음과 같이 명시돼 있습니다.

> total memory - (headroom amount + direct memory + metaspace + reserved code cache + (thread stack * thread count))  

> 중요: 이 계산은 빌드 때가 아니라 **컨테이너 시작 시(런타임)** 일어나며, **cgroup의 컨테이너 메모리 한도를 읽어** `-Xmx`를 정합니다. 컨테이너 메모리를 바꾸면 `-Xmx`가 자동 재계산됩니다.  
{: .prompt-warning}

---

## 4. 차감 항목과 기본값

각 항목의 기본값은 cloudfoundry java-buildpack-memory-calculator의 README[^calc]에 명시돼 있고, 이를 조정하는 환경변수는 Paketo BellSoft Liberica buildpack[^liberica]이 제공합니다.

| 항목 | 기본값 | 앞 편(ep2) 연결 |
| :--- | :--- | :--- |
| Headroom | 0% (`BPL_JVM_HEAD_ROOM`) | OS/기타 여유 |
| Direct Memory | 10M (`-XX:MaxDirectMemorySize` 미설정 시) | off-heap (netty) |
| Metaspace | `5800B x 클래스 수 + 14000000B` | 클래스 메타데이터 |
| Reserved Code Cache | 240M | JIT code cache |
| Thread Stacks | `1M x thread count` | 스레드 스택 (native) |

[^calc]: 계산식과 항목별 기본값(10M / 240M / metaspace 공식)의 출처는 cloudfoundry java-buildpack-memory-calculator README입니다: <https://github.com/cloudfoundry/java-buildpack-memory-calculator>
[^liberica]: `BPL_JVM_HEAD_ROOM` / `BPL_JVM_THREAD_COUNT` / `BPL_JVM_LOADED_CLASS_COUNT` 같은 조정용 환경변수의 출처는 Paketo BellSoft Liberica buildpack README입니다: <https://github.com/paketo-buildpacks/bellsoft-liberica>

각 항목이 실제로 어떻게 동작하고 무엇으로 조정하는지를 풀어 보겠습니다.

- **Direct Memory** - off-heap(netty 등 NIO 버퍼)이 차감됩니다. `-XX:MaxDirectMemorySize`를 명시하면 그 값이 그대로 차감액이 되고, 미설정이면 README 표현대로 "in the absence of any reasonable heuristic" 10M이 쓰입니다. netty 기반 reactive 스택에서 direct 사용량이 많다면 이 값을 키워 두는 편이 OOM 예방에 안전합니다.

> If `-XX:MaxDirectMemorySize` is configured it is used for the amount of direct memory. If not configured, `10M` (in the absence of any reasonable heuristic) is used.  

- **Metaspace** - 로드되는 클래스 수에 비례합니다. `-XX:MaxMetaspaceSize`를 명시하면 그 값을, 미설정이면 `(5800B * loaded class count) + 14000000b` 공식을 씁니다. 클래스 수는 `BPL_JVM_LOADED_CLASS_COUNT`로 직접 조정할 수 있는데, 미설정이면 buildpack이 빌드 시 발견한 클래스 수의 35%를 기본으로 잡습니다. 의존성이 많은 앱은 metaspace 차감이 커지므로 `-Xmx`가 줄어듭니다.

> If `-XX:MaxMetaspaceSize` is configured it is used for the amount of metaspace. If not configured, then the value is calculated as `(5800B * loaded class count) + 14000000b`.  

- **Reserved Code Cache** - JIT 컴파일 결과를 담는 영역으로 기본 240M가 고정 차감됩니다. `-XX:ReservedCodeCacheSize`로 바꿀 수 있으나, README가 "the JVM default"라 명시하듯 JVM 기본값과 동일해 보통 건드리지 않습니다.

> If `-XX:ReservedCodeCacheSize` is configured it is used for the amount of reserved code cache. If not configured, `240M` (the JVM default) is used.  

그리고 thread count 기본값이 핵심입니다.

> Configure the number of user threads at runtime. Defaults to `250`.  

즉 **스레드 스택만 1M x 250 = 약 250M**입니다. [Series 1 3편](/posts/spring-mvc-dispatcherservlet/)의 thread-per-request(Tomcat 기본 200 스레드)가 여기 그대로 들어옵니다. 실제보다 thread count가 크게 잡혀 있으면 `-Xmx`가 부당하게 작아집니다 - **스레드 수가 가장 큰 레버**입니다. `BPL_JVM_THREAD_COUNT`를 실제 worker 스레드 수에 맞게 줄이면(예: I/O 위주 reactive 앱에서 `100`) 스레드 스택 차감이 150M 줄어 그만큼 Heap이 늘어납니다.

튜닝은 컨테이너 환경변수로 전달합니다. 예를 들어 1G 한도 컨테이너에서 thread count를 줄이고 direct를 키우려면 다음처럼 지정합니다.

```bash
# 컨테이너 런타임에 환경변수로 전달 (예: Kubernetes env, docker run -e)
BPL_JVM_THREAD_COUNT=100
JAVA_TOOL_OPTIONS=-XX:MaxDirectMemorySize=64M
```

Memory Calculator는 시작 시 계산 결과를 로그로 남기므로, 컨테이너 첫 줄 로그에서 산출된 `-Xmx`를 바로 확인할 수 있습니다.

```text
Calculated JVM Memory Configuration: -XX:MaxDirectMemorySize=64M -Xmx411203K
  -XX:MaxMetaspaceSize=124300K -XX:ReservedCodeCacheSize=240M -Xss1M
  (Total Memory: 1G, Thread Count: 100, Loaded Class Count: 12354, Headroom: 0%)
```

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

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
