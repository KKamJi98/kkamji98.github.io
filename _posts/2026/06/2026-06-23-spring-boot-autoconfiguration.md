---
title: Spring Boot 자동설정, 스타터, fat jar 동작 원리
date: 2026-06-23 10:00:00 +0900
author: kkamji
categories: [Programming Language, Java]
tags: [java, spring, spring-boot, auto-configuration, starter, fat-jar]
comments: true
image:
  path: /assets/img/spring/spring.webp
---

지금까지 당연하게 넘긴 것들이 있습니다. [1편](/posts/spring-request-lifecycle/)에서 내장 Tomcat이 알아서 떴고, [3편](/posts/spring-mvc-dispatcherservlet/)에서 DispatcherServlet이 알아서 등록됐으며, [2편](/posts/spring-ioc-di-container/)에서 `@Service`/`@Repository`가 알아서 빈으로 스캔됐습니다. 누가 이걸 다 해줬을까요?

답은 **Spring Boot의 auto-configuration(자동설정)** 입니다. Series 1의 마지막 편인 이번 글은 그 "마법"을 해체하고, 앱이 어떻게 패키징되고 실행되는지(fat jar)까지 마무리합니다.

> **TL;DR**  
> - `@SpringBootApplication` = `@SpringBootConfiguration` + `@EnableAutoConfiguration` + `@ComponentScan` 의 합성이다.  
> - auto-configuration은 **클래스패스에 있는 jar를 보고** 합리적 기본 빈을 구성하되, **내가 직접 빈을 정의하면 물러난다(backs away)**.  
> - 스타터는 "이 기능에 필요한 의존성 묶음"이고, 그걸 넣으면 클래스패스가 채워져 자동설정 조건이 발동한다.  
> - 실행 산출물은 **executable(fat) jar**: 내 코드 + 의존성 + 로더를 하나로 묶어 `java -jar`로 단일 프로세스 실행된다.  
{: .prompt-info}

---

## 1. 1~3편의 "마법"은 누가 해줬나

지금까지 우리가 설정하지 않았는데 동작한 것들:

- 내장 Tomcat 기동 (1편)
- DispatcherServlet 등록 + `/` 매핑 (1/3편)
- `@Service`/`@Repository` 빈 스캔 (2편)

이걸 가능하게 한 게 `@SpringBootApplication` 한 줄입니다. 그 안을 봅니다.

---

## 2. @SpringBootApplication = 3개 어노테이션의 합

모든 Boot 앱의 시작점인 이 어노테이션은 사실 셋의 합성입니다.

> A single `@SpringBootApplication` annotation can be used to enable those three features, that is: `@EnableAutoConfiguration` ... `@ComponentScan` ... `@SpringBootConfiguration` ...  

```java
@SpringBootApplication
//  = @SpringBootConfiguration  (= @Configuration 의 Boot 특수화, 설정 소스)
//  + @ComponentScan            (내 @Component/@Service/... 스캔 - 2편)
//  + @EnableAutoConfiguration  (자동설정 켜기 - 이번 편의 핵심)
public class MyApplication {
    public static void main(String[] args) {
        SpringApplication.run(MyApplication.class, args);
    }
}
```

`@ComponentScan`은 2편에서 본 "내가 짠 빈 찾기"이고, 핵심은 `@EnableAutoConfiguration`입니다.

---

## 3. auto-configuration: 클래스패스 기반 + 양보

자동설정의 원리는 두 문장으로 요약됩니다.

> Spring Boot auto-configuration attempts to automatically configure your Spring application based on the jar dependencies that you have added.  

즉 **클래스패스에 어떤 jar가 있는지** 보고 알맞은 기본 빈을 구성합니다. 그리고 결정적으로,

> Auto-configuration is non-invasive. At any point, you can start to define your own configuration to replace specific parts of the auto-configuration. For example, if you add your own `DataSource` bean, the default embedded database support backs away.  

**내가 직접 빈을 정의하면 자동설정은 물러납니다.** 그래서 "기본은 알아서, 필요하면 내가 덮어쓰기"가 됩니다.

![auto-configuration 평가 흐름](/assets/img/spring/spring-07-autoconfiguration-flow.webp)
_후보 로드 -> @Conditional 평가 -> 통과 시 빈 등록, 아니면 backs off_

이 "켜고 끄기"의 구현 메커니즘이 `@Conditional` 계열입니다. 1편에서 확인한 `ServletWebServerFactoryAutoConfiguration`이 실제 예시입니다.

```java
@AutoConfiguration
@ConditionalOnClass(ServletRequest.class)        // 서블릿 클래스가 클래스패스에 있을 때만
@ConditionalOnWebApplication(type = SERVLET)     // 서블릿 웹앱일 때만
public class ServletWebServerFactoryAutoConfiguration { ... }
```

조건이 맞으면(서블릿이 클래스패스에 있음) 내장 서버를 구성하고, `@ConditionalOnMissingBean`이면 "내가 만든 빈이 없을 때만" 기본 빈을 등록합니다. 자동설정 후보 목록은 `META-INF/spring/...AutoConfiguration.imports`에 들어 있습니다.

---

## 4. 스타터: 큐레이션된 의존성 묶음

그럼 "클래스패스에 Tomcat이 있나?"의 클래스패스는 누가 채울까요? 스타터입니다.

> Starters are a set of convenient dependency descriptors that you can include in your application. You get a one-stop shop for all the Spring and related technologies that you need ...  

> `spring-boot-starter-web` - Starter for building web, including RESTful, applications using Spring MVC. Uses Tomcat as the default embedded container.  

즉 `spring-boot-starter-web` 하나를 넣으면 Spring MVC + 내장 Tomcat + JSON 라이브러리가 클래스패스에 깔리고, 그러면 3장의 `@ConditionalOnClass`들이 발동해 웹앱이 "그냥 됩니다". 버전은 Spring Boot가 관리하므로 내가 고르지 않습니다.

---

## 5. fat jar: 어떻게 단일 파일로 실행되나

1편에서 `java -jar app.jar`로 단일 프로세스가 뜬다고 했습니다. 그 jar가 **executable(fat) jar**입니다.

![executable jar 구조와 실행 경로](/assets/img/spring/spring-08-fatjar-layout.webp)
_jar 내부 구조(좌)와 java -jar -> JarLauncher -> 중첩 classloader -> Start-Class main(우)_

구조는 이렇습니다.

```text
app.jar
├── META-INF/MANIFEST.MF        Main-Class: JarLauncher / Start-Class: MyApplication
├── org/springframework/boot/loader/   (Boot 로더 클래스)
└── BOOT-INF/
    ├── classes/   (내 코드)
    └── lib/       (의존성 jar들 - "jar 안의 jar")
```

여기서 핵심 문제와 해법:

> Java does not provide any standard way to load nested jar files (that is, jar files that are themselves contained within a jar).  

표준 `java -jar`는 jar 안의 jar를 못 읽습니다. 그래서 Boot는 MANIFEST의 `Main-Class`를 **JarLauncher**로 두고, JarLauncher가 중첩 jar를 읽는 특수 classloader를 세팅한 뒤 내 `Start-Class`의 `main()`을 호출합니다.

> fat jar는 "내 코드 + 모든 의존성 + 로더"를 하나로 묶은 자체 완결 실행체입니다. JRE만 있으면 어디서든 `java -jar`로 돕니다.  
{: .prompt-tip}

---

## 6. 마무리: Series 1 정리

이번 편으로 Series 1을 닫습니다. 요청 한 건이 흐르는 길을 위에서 아래로 따라왔습니다.

- 1편: 요청이 단일 프로세스(내장 Tomcat) 안에서 DispatcherServlet을 거쳐 처리된다
- 2편: 그 안의 객체들은 IoC 컨테이너가 만든 싱글톤 빈이다
- 3편: 요청당 워커 스레드 1개가 블로킹 포함 전담하고, 그 스택은 native 메모리다
- 4편: 이 모든 걸 자동설정이 엮고, fat jar로 패키징해 실행한다

> capstone 연결: fat jar -> 컨테이너 이미지(Series 2 / 5편 buildpack) -> 단일 프로세스 실행(1편) -> 그 프로세스 메모리를 buildpack memory calculator가 계산(capstone). 그리고 그 메모리 식의 항목들 - 힙(싱글톤 빈 baseline, 2편) / 스레드 스택(3편) / off-heap - 이 다음 시리즈의 주제입니다.  
{: .prompt-tip}

다음 시리즈(Series 2)에서는 한 계층 더 내려가, 까먹기 쉬운 메모리 CS 기초부터 다시 잡고 JVM 메모리 모델과 GC로 들어갑니다.

DevSecOps 관점에서 보면, auto-configuration은 Helm values의 합리적 기본값처럼 "convention over configuration"이고, `@Conditional`은 조건이 맞을 때만 리소스를 만드는 Terraform의 conditional과 닮았으며, fat jar는 정적 바이너리/컨테이너 이미지처럼 다 싸들고 다니는 자체 완결 산출물입니다.

---

## 7. 참고 자료

- Spring Boot Reference - Using the @SpringBootApplication Annotation: <https://docs.spring.io/spring-boot/reference/using/using-the-springbootapplication-annotation.html>
- Spring Boot Reference - Auto-configuration: <https://docs.spring.io/spring-boot/reference/using/auto-configuration.html>
- Spring Boot Reference - Build Systems (Starters): <https://docs.spring.io/spring-boot/reference/using/build-systems.html>
- Spring Boot - Executable Jar / Nested JARs: <https://docs.spring.io/spring-boot/specification/executable-jar/nested-jars.html>
