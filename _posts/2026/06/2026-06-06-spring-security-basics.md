---
title: Spring Security 기초 - 보안 필터 체인, 인증과 인가
date: 2026-06-06 19:00:00 +0900
author: kkamji
categories: [Programming Language, Java]
tags: [java, spring, spring-security, security, authentication, authorization]
comments: true
image:
  path: /assets/img/spring/spring.webp
---

[Series 5 1편](/posts/gradle-maven-build/)에서 빌드와 의존성을 봤습니다. 의존성에 `spring-boot-starter-security`를 더하면 갑자기 로그인 화면이 뜨고 권한 없는 요청은 막힙니다. 이 동작의 정체는 무엇일까요. 정답은 **컨트롤러 앞단에 서는 필터 체인**입니다. 이번 글에서는 Spring Security의 구조(필터 체인), 그리고 **인증(누구인가)**과 **인가(무엇을 허용)**의 차이를 정리합니다. 커리큘럼의 마지막 글입니다.

> **TL;DR**  
> - Spring Security는 **servlet Filter**로 동작한다. `DelegatingFilterProxy`(Servlet <-> Spring 브리지) -> `FilterChainProxy` -> `SecurityFilterChain`(보안 필터들) 순서로, [Series 1의 DispatcherServlet](/posts/spring-mvc-dispatcherservlet/) **앞단**에서 처리된다.  
> - **인증(Authentication)**: 누구인지 확정. `AuthenticationManager`가 수행하고, 결과를 `SecurityContextHolder`에 저장한다.  
> - **인가(Authorization)**: 그 권한으로 이 요청이 허용되는지 판단. `authorities/roles`를 접근 규칙과 비교해 허용/거부(403)한다.  
> - 거부되면 **앱 코드까지 도달하지 않는다.** 보안은 컨트롤러 앞에서 끝난다.  
{: .prompt-info}

---

## 1. Spring Security는 필터다

Spring Security의 서블릿 지원은 마법이 아니라 **servlet Filter**입니다.

> Spring Security's Servlet support is based on Servlet Filters, so it is helpful to look at the role of Filters generally first.  
> _- Spring Security Reference_  

![Spring Security 필터 체인](/assets/img/spring/spring-23-security-filter-chain.webp)
_DelegatingFilterProxy가 Servlet 컨테이너와 Spring을 잇고, FilterChainProxy가 SecurityFilterChain의 보안 필터들에 위임한다. 통과해야 컨트롤러에 도달한다._

세 가지 핵심 요소가 있습니다. 먼저 **`DelegatingFilterProxy`**가 서블릿 컨테이너와 Spring을 잇습니다.

> Spring provides a `Filter` implementation named `DelegatingFilterProxy` that allows bridging between the Servlet container's lifecycle and Spring's `ApplicationContext`.  
> _- Spring Security Reference_  

그 안에서 **`FilterChainProxy`**가 실제 보안 필터들에 위임합니다.

> `FilterChainProxy` is a special `Filter` provided by Spring Security that allows delegating to many `Filter` instances through `SecurityFilterChain`.  
> _- Spring Security Reference_  

그리고 어떤 필터를 적용할지는 **`SecurityFilterChain`**이 결정합니다.

> `SecurityFilterChain` is used by `FilterChainProxy` to determine which Spring Security `Filter` instances should be invoked for the current request.  
> _- Spring Security Reference_  

즉 보안은 [Series 1](/posts/spring-mvc-dispatcherservlet/)의 DispatcherServlet(컨트롤러) **앞단**에서 끝납니다. 거부되면 애플리케이션 코드는 실행조차 되지 않습니다.

---

## 2. 인증(Authentication) - 누구인가

인증은 "이 요청의 주체가 누구인지" 확정하는 단계입니다.

![인증과 인가](/assets/img/spring/spring-24-authn-authz.webp)
_인증: credentials -> AuthenticationManager -> 인증된 Authentication을 SecurityContextHolder에 저장. 인가: AuthorizationFilter가 권한을 접근 규칙과 비교해 허용/거부._

인증을 수행하는 API가 **`AuthenticationManager`**입니다.

> `AuthenticationManager` is the API that defines how Spring Security's `Filters` perform authentication.  
> _- Spring Security Reference_  

인증에 성공하면 결과(누가 인증됐는지)를 **`SecurityContextHolder`**에 저장합니다.

> The `SecurityContextHolder` is where Spring Security stores the details of who is authenticated.  
> _- Spring Security Reference_  

`SecurityContextHolder`는 기본적으로 **`ThreadLocal`**을 씁니다. 여기서 [Series 1의 thread-per-request](/posts/spring-mvc-dispatcherservlet/)와 만납니다. 요청당 스레드 모델이라, 그 스레드 안에서는 파라미터로 넘기지 않아도 현재 인증 정보를 어디서나 꺼낼 수 있습니다. 인증된 `Authentication`은 `principal`(누구), `credentials`(비밀번호 등), `authorities`(권한)를 담습니다.

---

## 3. 인가(Authorization) - 무엇을 허용

인증으로 "누구인지"가 정해지면, 인가는 "그 권한으로 이 요청이 허용되는지"를 판단합니다. `AuthorizationFilter`가 요청 주체의 `authorities/roles`를 접근 규칙과 비교해 **허용하거나 거부(403 Forbidden)**합니다.

여기서 두 응답을 구분해야 합니다. **누구인지 모를 때(미인증)는 401 Unauthorized**, **누구인지는 알지만 권한이 없을 때는 403 Forbidden**입니다.

---

## 4. 최소 설정 예시

Spring Security 설정의 중심은 `SecurityFilterChain` 빈입니다.

```java
@Bean
SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
    http
        .authorizeHttpRequests(auth -> auth
            .requestMatchers("/admin/**").hasRole("ADMIN")   // 인가 규칙
            .requestMatchers("/public/**").permitAll()
            .anyRequest().authenticated())                    // 그 외는 인증 필요
        .formLogin(Customizer.withDefaults());
    return http.build();
}
```

`authorizeHttpRequests`가 인가 규칙을, `formLogin` 등이 인증 방식을 정합니다. 이 빈이 곧 1절의 `SecurityFilterChain`이 됩니다.

---

## 5. 함정과 팁

- **401 vs 403 혼동.** "권한 오류"를 뭉뚱그리면 디버깅이 어렵습니다. 인증 실패(401)인지 인가 실패(403)인지부터 가립니다.
- **`SecurityContext`는 ThreadLocal.** 작업을 별도 스레드로 넘기면 인증 정보가 자동 전파되지 않습니다. [WebFlux](/posts/spring-webflux-netty-event-loop/) 같은 논블로킹 스택은 ThreadLocal이 맞지 않아 reactive 전용 보안(컨텍스트 전파)을 씁니다.
- **순서가 핵심.** 보안 필터는 컨트롤러 앞에 있으므로, 인가 규칙이 잘못되면 정상 요청이 막히거나 반대로 보호되어야 할 경로가 뚫립니다. 규칙의 순서와 범위를 항상 확인합니다.

---

## 6. 마치며 - 커리큘럼 전체를 닫으며

Series 5에서 [빌드/의존성](/posts/gradle-maven-build/)과 보안(Spring Security)을 보며, 요청 처리(Series 1) -> JVM/메모리(Series 2) -> 동시성(Series 3) -> 데이터 계층(Series 4) -> [실전 진단(Capstone)](/posts/jvm-spring-capstone/) -> 빌드/보안(Series 5)까지 한 바퀴를 돌았습니다. 프레임워크가 가려 둔 "마법"을 한 겹씩 벗겨 메커니즘으로 바꾸는 것이 이 커리큘럼의 목표였습니다.

DevSecOps 비유: 보안 필터 체인은 **요청이 앱에 닿기 전 게이트웨이/미들웨어에서 정책을 적용**하는 구조(WAF, API gateway의 authn/authz)와 같습니다. 인증과 인가의 분리는 IAM의 AuthN/AuthZ 분리와 동일하고, "권한은 필요한 만큼만"이라는 최소 권한 원칙이 인가 규칙 설계에도 그대로 적용됩니다.

---

## 7. 참고 자료

- Spring Security Reference - Servlet Architecture (Filter / DelegatingFilterProxy / FilterChainProxy / SecurityFilterChain): <https://docs.spring.io/spring-security/reference/servlet/architecture.html>
- Spring Security Reference - Authentication Architecture (SecurityContextHolder / Authentication / AuthenticationManager): <https://docs.spring.io/spring-security/reference/servlet/authentication/architecture.html>
- Spring Security Reference - Authorization Architecture (AuthorizationFilter): <https://docs.spring.io/spring-security/reference/servlet/authorization/architecture.html>

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
