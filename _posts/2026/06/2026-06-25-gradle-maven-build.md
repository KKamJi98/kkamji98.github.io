---
title: 빌드 도구와 의존성 관리 - Gradle/Maven과 Spring Boot 패키징
date: 2026-06-25 18:00:00 +0900
author: kkamji
categories: [Programming Language, Java]
tags: [java, spring, spring-boot, gradle, maven, build]
comments: true
image:
  path: /assets/img/spring/spring.webp
---

매일 `./gradlew bootJar`나 `mvn package`를 치고, 만들어진 `app.jar`를 `java -jar`로 실행합니다. 그런데 그 사이에 무슨 일이 일어날까요. 의존성에 버전을 안 적었는데 어떻게 빌드가 되고, 하나의 jar 안에 라이브러리가 전부 들어가는 건 어떻게일까요. Series 5(빌드/보안)의 첫 글에서는 빌드 도구가 하는 일, 의존성 관리(BOM), 그리고 실행 가능 jar 패키징을 정리합니다.

> **TL;DR**  
> - 빌드 도구(Gradle/Maven)는 **compile -> test -> package**와 **의존성 관리**를 담당한다. Gradle은 태스크 DAG + DSL, Maven은 phase 생명주기 + XML.  
> - Spring Boot 플러그인의 `bootJar`(Gradle) / repackage(Maven)는 **앱 + 모든 의존성을 담은 실행 가능 fat jar**를 만들어 `java -jar`로 실행하게 한다.  
> - 의존성에 **버전을 안 적어도 되는 이유**는 `spring-boot-dependencies` **BOM**이 호환되는 버전 집합으로 맞춰 주기 때문이다.  
{: .prompt-info}

---

## 1. 빌드 도구가 하는 일

빌드 도구의 역할은 크게 둘입니다. 하나는 **빌드 단계 실행**(소스 컴파일, 테스트, 패키징)이고, 다른 하나는 **의존성 관리**(필요한 라이브러리와 그 전이 의존성을 가져와 버전을 맞추는 것)입니다.

Gradle과 Maven은 접근이 다릅니다.

| 항목       | Maven                          | Gradle                              |
| :--------- | :----------------------------- | :---------------------------------- |
| **설정**   | `pom.xml` (XML, 선언적)        | `build.gradle(.kts)` (Groovy/Kotlin DSL) |
| **실행 모델** | 고정된 phase 생명주기          | 태스크 그래프(DAG), 증분 빌드/캐시  |
| **빌드 명령** | `mvn package`                  | `./gradlew build`                   |

어느 쪽이든 "소스 + 의존성 -> 실행 가능한 산출물"을 만드는 목적은 같습니다.

---

## 2. 빌드 파이프라인과 실행 가능 jar

빌드의 흐름과 최종 산출물을 정리하면 다음과 같습니다.

![빌드 파이프라인과 실행 가능 fat jar](/assets/img/spring/spring-21-build-pipeline.webp)
_compile + test -> Spring Boot 플러그인 패키징 -> 앱과 모든 의존성을 담은 실행 가능 jar -> java -jar로 실행._

Spring Boot Gradle 플러그인은 `bootJar` 태스크로 실행 가능 jar를 만듭니다.

> Executable jars can be built using the `bootJar` task.  
> _- Spring Boot Gradle Plugin Reference_  

이 jar는 **애플리케이션의 모든 의존성을 포함**해 `java -jar`로 바로 실행됩니다.

> The plugin can create executable archives (jar files and war files) that contain all of an application's dependencies and can then be run with `java -jar`.  
> _- Spring Boot Gradle Plugin Reference_  

내부 레이아웃은 [Series 1의 fat jar 편](/posts/spring-boot-autoconfiguration/)에서 본 것과 같습니다.

> By default, the `bootJar` task builds an archive that contains the application's classes and dependencies in `BOOT-INF/classes` and `BOOT-INF/lib` respectively.  
> _- Spring Boot Gradle Plugin Reference_  

즉 `BOOT-INF/classes`(내 코드) + `BOOT-INF/lib`(의존성 jar들) 구조이고, 이걸 `JarLauncher`가 전용 클래스로더로 실행합니다. 빌드의 산출물이 곧 Series 1에서 본 실행 구조입니다.

---

## 3. 의존성 관리 - 버전을 안 적어도 되는 이유

Spring Boot 프로젝트의 `build.gradle`을 보면 의존성에 버전이 없습니다.

```groovy
dependencies {
    implementation 'org.springframework.boot:spring-boot-starter-web'
    implementation 'org.springframework.boot:spring-boot-starter-data-jpa'
}
```

이게 가능한 이유는 **dependency management(BOM)** 때문입니다.

![의존성 관리와 BOM](/assets/img/spring/spring-22-dependency-bom.webp)
_버전을 생략해 선언하면, spring-boot-dependencies BOM이 호환되는 버전 집합으로 채워 직접/전이 의존성을 정렬한다._

> When you apply the `io.spring.dependency-management` plugin, Spring Boot's plugin will automatically import the `spring-boot-dependencies` bom from the version of Spring Boot that you are using. ... it allows you to omit version numbers when declaring dependencies that are managed in the bom.  
> _- Spring Boot Gradle Plugin Reference_  

`spring-boot-dependencies` BOM은 수많은 라이브러리의 **검증된 호환 버전 집합**을 정의합니다. 그래서 버전을 직접 안 적어도 BOM이 채워 주고, 라이브러리 간 버전 충돌이 줄어듭니다. **starter**(예: `spring-boot-starter-web`)는 이 위에서 "이 기능에 필요한 의존성 묶음"을 한 번에 가져오는 역할을 합니다.

---

## 4. 함정과 팁

- **버전 강제 override 주의.** BOM이 관리하는 라이브러리의 버전을 임의로 올리면, BOM이 보장하던 호환 집합을 벗어나 미묘한 충돌이 날 수 있습니다. 꼭 필요할 때만, 영향 범위를 확인하고 바꿉니다.
- **전이 의존성 충돌 확인.** 같은 라이브러리를 서로 다른 버전이 끌고 오면 충돌합니다. `./gradlew dependencyInsight --dependency <name>` 또는 `mvn dependency:tree`로 실제 해석된 버전을 확인합니다.
- **무엇이 왜 들어왔는지 본다.** fat jar의 `BOOT-INF/lib`가 비대해지면 의존성 트리를 점검해 불필요한 것을 줄입니다.

---

## 5. 다음 글

이번 편에서 빌드 단계, 실행 가능 jar(`bootJar`), 의존성 관리(BOM)를 봤습니다. 다음 편은 Series 5의 두 번째 주제인 **Spring Security**(인증/인가와 필터 체인)를 다룹니다.

연결 고리도 분명합니다. 빌드 산출물인 fat jar는 [Series 1](/posts/spring-boot-autoconfiguration/)에서 실행되고, 의존성 버전(특히 JDK/라이브러리 메이저 업그레이드)은 [Capstone](/posts/jvm-spring-capstone/)에서 본 "업그레이드 후 거동 변화"의 출발점이기도 합니다.

DevSecOps 비유: BOM/버전 고정은 **lockfile과 재현 가능한 빌드**(같은 입력 -> 같은 산출물)의 발상이고, 의존성 트리 관리는 **공급망 보안(SBOM, 취약점 스캔)**과 직결됩니다. 빌드 파이프라인의 compile/test/package 단계는 그대로 CI 파이프라인의 단계가 됩니다.

---

## 6. 참고 자료

- Spring Boot Gradle Plugin - Packaging Executable Archives (`bootJar` / fat jar / BOOT-INF): <https://docs.spring.io/spring-boot/gradle-plugin/packaging.html>
- Spring Boot Gradle Plugin - Managing Dependencies (dependency management / BOM): <https://docs.spring.io/spring-boot/gradle-plugin/managing-dependencies.html>
- Spring Boot Maven Plugin (repackage / 의존성 관리): <https://docs.spring.io/spring-boot/maven-plugin/>

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
