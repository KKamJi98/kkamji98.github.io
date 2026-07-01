---
title: Datadog RUM 알아보기 - Real User Monitoring 개념과 Observability [Datadog 1]
date: 2026-06-29 11:00:00 +0900
author: kkamji
categories: [Monitoring & Observability]
tags: [datadog, rum, real-user-monitoring, observability, monitoring, frontend, apm, session-replay, core-web-vitals]     # TAG names should always be lowercase
comments: true
image:
  path: /assets/img/observability/datadog/datadog.webp
---

서버 쪽 observability는 APM, logs, metrics로 비교적 익숙하게 다룹니다. 그런데 "백엔드는 200 OK로 빠르게 응답했는데 사용자는 느리다고 한다"는 상황은 server-side 신호만으로는 잘 잡히지 않습니다. 느린 렌더링, 레이아웃 이동, 브라우저 JS 에러처럼 사용자가 실제로 겪는 문제는 대부분 client-side에서 발생하기 때문입니다. 이번 글에서는 이 갭을 메우는 **Datadog RUM(Real User Monitoring)**의 개념과 데이터 모델, 무엇을 관측할 수 있는지, 그리고 이를 통해 observability를 어떻게 향상시킬 수 있는지 살펴봅니다.

> - RUM은 server-side observability의 반대편인 **client-side에서 실제 사용자 세션을 그대로 관측**하는 frontend observability입니다.  
> - 데이터 모델은 `Session > View > (Action / Resource / Error / Long Task / Vital)` 트리 구조입니다.  
> - 성능(Core Web Vitals), 사용자 경험(Session Replay, Error Tracking, frustration signals), 프로덕트 분석(funnel/retention)까지 한 SDK로 관측합니다.  
> - `allowedTracingUrls`로 RUM과 APM trace를 같은 `trace_id`로 연결하면 프론트 클릭에서 백엔드 느린 SQL까지 한 화면에서 추적할 수 있습니다.  
{: .prompt-info}

> **TL;DR**  
> - 모니터링과 Observability 관점에서 수집, 시각화, 문제 분석 흐름을 정리합니다.  
> - 주요 키워드는 datadog, rum, real-user-monitoring이며, 글의 예제와 명령을 따라가며 전체 흐름을 확인할 수 있습니다.  
> - 운영 관점에서는 버전, 권한, 네트워크, 보안, 장애 시 확인 지점을 함께 점검하는 것이 중요합니다.  
{: .prompt-info}

---

## 1. RUM이란 무엇인가

Real User Monitoring(RUM)은 실제 사용자가 브라우저나 모바일 앱에서 겪는 활동과 경험을 실시간으로 가시화하는 client-side observability입니다. Datadog 공식 문서는 RUM의 용도를 크게 네 가지로 정리합니다.

- 페이지/액션 **성능** 추적
- error management를 통한 **버그 모니터링**
- 사용자 행동과 demographics를 보는 **analytics**
- 개별 세션을 들여다보는 **support 트러블슈팅**

핵심은 "인프라가 건강한가"가 아니라 **"실제 사용자가 실제로 무엇을 겪었는가"**를 본다는 점입니다.

### 1.1. server-side observability와의 차이

APM, logs, metrics는 백엔드 서비스와 인프라 관점의 신호입니다. 반면 RUM은 그 반대편인 client-side에서 web page, 화면, user action, network request, frontend code의 동작을 캡처합니다. 같은 요청이라도 서버가 빠르게 200 OK를 응답해도, 클라이언트의 느린 렌더링이나 JS 에러로 사용자 체감은 나쁠 수 있습니다. RUM은 바로 그 갭을 메웁니다.

### 1.2. Real User vs Synthetic

- **Real User**: 실제 트래픽을 그대로 관측합니다. 데이터 단위는 실사용자 세션입니다.
- **Synthetic**: 사전에 정의한 스크립트로 합성 트래픽을 주기적으로 보내 검증합니다.

측정 대상 자체가 다릅니다. RUM은 "지금 실제 사용자가 어떤 경험을 하고 있는가"를, Synthetic은 "정해진 시나리오가 정상 동작하는가"를 봅니다. 둘의 관계는 [5장](#5-rum-vs-synthetic-vs-apm)에서 다시 정리합니다.

### 1.3. 어디에 instrumentation이 사는가

RUM instrumentation은 전적으로 client-side에 존재합니다. 브라우저는 JS SDK(`@datadog/browser-rum`)를 페이지에 로드하고, 모바일/그 외 플랫폼은 네이티브 SDK가 앱에 임베드됩니다. 지원 플랫폼은 Browser, Android, iOS, Flutter, React Native, Roku, Kotlin Multiplatform, Unity입니다. SDK가 사용자 디바이스에서 직접 이벤트를 수집해 Datadog로 전송합니다.

---

## 2. RUM 데이터 모델

RUM 데이터는 트리 구조입니다. 최상위 **Session**이 한 사용자의 여정 전체를 묶고, 그 아래 **View**가 페이지/화면 단위로 생기며, 나머지 이벤트는 모두 수집 시점의 active View에 귀속됩니다.

![Datadog RUM 데이터 모델 - Session > View > Action/Resource/Error/Long Task/Vital 계층 트리](/assets/img/observability/datadog-rum-01-data-model.webp)

| 이벤트         | 무엇을 캡처                                              | 대표 속성 / 예시                                   |
| :------------- | :------------------------------------------------------ | :------------------------------------------------- |
| **Session**    | 한 사용자의 여정 전체 (최대 4h, 15min 비활동 시 만료)   | `session.id`, `session.type`                       |
| **View**       | 페이지/화면 단위 (initial load 또는 route change)       | `view.id`, `view.loading_time`, Core Web Vitals    |
| **Action**     | click/tap 등 사용자 인터랙션, frustration signals       | `action.type`, `action.target.name`               |
| **Resource**   | XHR/fetch, JS, 이미지, 폰트 등 네트워크 요청            | `resource.type`, `resource.status_code`, 단계별 타이밍 |
| **Error**      | unhandled exception, console error, 모바일 crash        | `error.source`, `error.message`, `error.stack`     |
| **Long Task**  | 브라우저 main thread를 50ms 이상 블록한 작업            | `long_task.duration`                               |
| **Vital**      | 컴포넌트 단위 custom 측정값                             | `startDurationVital` API                           |

> Session은 **15분간 비활동(inactivity) 시 만료**되고 **최대 4시간**까지 지속됩니다. 과금 단위(per 1,000 sessions)와 직결되므로 이 경계를 알아두면 좋습니다.  
{: .prompt-tip}

모든 이벤트에는 공통 표준 속성이 자동 부착됩니다. device(`device.type/brand/model`), OS(`os.name/version`), browser(`browser.name/version`), 위치(`geo.country/city`, client IP에서 서버측 resolve), connectivity(주로 모바일), 그리고 `setUser`로 지정한 사용자 신원(`usr.id/name/email`)까지 붙어, 어떤 기기/브라우저/지역에서 문제가 더 심한지 facet으로 쪼갤 수 있습니다.

---

## 3. 무엇을 관측할 수 있는가

### 3.1. 성능 - Core Web Vitals와 타이밍

RUM은 Google의 Core Web Vitals 세 가지를 View 이벤트에 자동 수집합니다.

| 지표    | 의미                                                  | good 기준 | RUM 속성                          |
| :------ | :---------------------------------------------------- | :-------- | :-------------------------------- |
| **LCP** | 뷰포트에서 가장 큰 콘텐츠가 렌더되는 시점             | < 2.5s    | `view.largest_contentful_paint`   |
| **INP** | 사용자 인터랙션부터 다음 paint까지의 최악 지연        | < 200ms   | `view.interaction_to_next_paint`  |
| **CLS** | 예기치 않은 레이아웃 이동 (점수, 0 = 이동 없음)       | < 0.1     | `view.cumulative_layout_shift`    |

Google은 2024년에 인터랙티비티 Core Web Vital을 기존 FID(First Input Delay)에서 **INP로 교체**했습니다. Datadog은 INP를 SPA route change를 포함한 모든 view에서 측정하며(`view.first_input_delay`는 legacy 속성으로 여전히 노출), LCP와 INP는 sub-parts(예: INP는 input delay / processing duration / presentation delay)까지 분해해 어느 구간이 병목인지 짚어줍니다.

이 외에도 FCP(`view.first_contentful_paint`), TTFB(`view.first_byte`), Datadog 커스텀 지표인 Loading Time(`view.loading_time`), Time Spent(`view.time_spent`)를 수집합니다. **Resource** 이벤트는 Performance Resource Timing API로 단계별 타이밍(`resource.dns` / `connect` / `ssl` / `first_byte` / `download`)을 분해해, DNS인지 TLS인지 다운로드인지 어느 단계가 느린지 바로 알 수 있습니다.

> Core Web Vitals 같은 분포형 지표는 평균이 아니라 **75th percentile(p75)** 로 보는 것을 Datadog이 권장합니다.  
{: .prompt-tip}

### 3.2. 사용자 경험 - Session Replay, Error Tracking, frustration signals

- **Session Replay**: 실제 사용자 세션을 재생합니다. 영상 녹화가 아니라 **DOM/CSS 스냅샷 + 증분 이벤트(클릭/스크롤/입력)를 기록해 페이지를 재구성**하는 방식(브라우저는 오픈소스 rrweb 기반, 모바일은 wireframe)이라 가볍고 구조적입니다. 버그 재현에 강력합니다.
- **Error Tracking**: 수천 개의 유사 에러를 `error type + message + stack trace` 기반 **fingerprint로 하나의 issue로 그룹핑**합니다. 브라우저는 source map 업로드로 minified stack trace를 복원하고, 모바일은 `.dSYM`(iOS)/R8 mapping(Android)으로 symbolicate합니다. issue는 **Impacted Sessions(영향받은 세션 수)** 로 정렬되어, 단순 발생 횟수가 아니라 실제 사용자 영향 기준으로 우선순위를 매길 수 있습니다.
- **Frustration Signals**: 마우스 클릭에서 사용자 좌절을 잡아냅니다.
  - **Rage Click**: 같은 요소를 1초 sliding window 안에 3회 초과 클릭
  - **Dead Click**: 아무 동작도 일어나지 않는 정적 요소 클릭
  - **Error Click**: 클릭 직후 JS 에러 발생
- **Heatmap**: Click map, Top Elements, Scroll map으로 어디를 클릭/스크롤하는지 집계합니다.

### 3.3. 프로덕트 분석 - funnel, journey, retention

같은 `Session / View / Action` 데이터 위에서 Product Analytics(별도 제품, 동일 SDK)가 동작합니다. 추가 instrumentation 없이 **Funnel(전환/이탈 분석)**, **Pathways(사용자 여정)**, **Retention(재방문)**, **Segments(사용자 분류)** 를 볼 수 있고, 행동 이벤트는 15개월 retention을 가집니다. 엔지니어링 지표(Core Web Vitals, 에러)와 프로덕트 지표(전환율, 이탈)가 **하나의 데이터셋**에서 나오므로 개발팀과 프로덕트팀이 같은 기준점을 공유합니다.

### 3.4. 모바일 RUM

모바일은 Android Vitals/Apple MetricKit에서 영감받은 Mobile Vitals를 수집합니다.

| 항목                | 기준                                  |
| :------------------ | :------------------------------------ |
| **App start**       | TTID(첫 프레임) / TTFD(완전 표시)     |
| **Slow renders**    | 16ms(60Hz) 초과 렌더 프레임           |
| **Frozen frames**   | 700ms 초과 프레임 (멈춘 것처럼 보임)  |
| **CPU**             | < 40 ticks/sec good                   |
| **Memory**          | < 200MB good                          |
| **응답성 문제**     | iOS app hang(250ms+), Android ANR     |

여기에 crash reporting과 crash-free sessions까지 더해, 네이티브 앱의 stability와 responsiveness를 정량화합니다.

---

## 4. Observability를 어떻게 향상시키는가

RUM의 진짜 가치는 단독 frontend 지표가 아니라, **다른 telemetry와 연결되어 end-to-end 가시성을 만든다**는 데 있습니다.

### 4.1. RUM + APM trace linking (full-stack)

가장 중요한 연결입니다. Browser RUM SDK는 `allowedTracingUrls`에 매칭되는 요청에 trace context 헤더를 주입하고, 백엔드 APM tracer가 같은 `trace_id`를 이어받습니다. 그 결과 **프론트 Resource와 백엔드 분산 trace가 같은 trace로 묶여**, 사용자 클릭에서 백엔드의 느린 SQL까지 한 흐름으로 추적됩니다.

![Browser RUM SDK가 trace header를 주입하고 백엔드 APM tracer가 trace_id를 이어받아 RUM 세션과 APM trace가 연결되는 full-stack 흐름](/assets/img/observability/datadog-rum-02-trace-linking.webp)

- **Datadog 헤더**: `x-datadog-trace-id`, `x-datadog-parent-id`, `x-datadog-origin: rum`, `x-datadog-sampling-priority`
- **W3C 헤더**: `traceparent`, `tracestate`
- RUM Explorer에서 세션을 열면 request 분해 + flame graph + `View Trace in APM` 링크가 제공되고, APM trace에서도 `See View/Resource in RUM`으로 역방향 이동이 됩니다.

> `traceSampleRate`는 백엔드 trace 보존 비율만 조절하며 RUM 세션 sampling에는 영향을 주지 않습니다. **browser SDK는 미설정 시 100%** 가 기본이지만(예: Kotlin Multiplatform은 20%로 기본이 다름) 플랫폼별 default가 다르니 명시하는 편이 안전합니다.  
{: .prompt-warning}

### 4.2. 구체적인 결과물

- **MTTR 단축**: 프론트 에러가 급증하면 같은 `session_id`/`trace_id`로 연결된 백엔드 trace로 바로 pivot합니다. 로그 -> trace -> RUM 세션을 도구 전환 없이 한 화면에서 봅니다.
- **실사용자 영향 기반 우선순위**: Error Tracking의 Impacted Sessions로 "몇 명이 실제로 영향받았는가"를 기준으로 fix 우선순위를 정합니다.
- **배포/릴리스 추적**: `version` 태그로 릴리스 간 error rate, Core Web Vitals, Loading Time, crash rate를 비교해 나쁜 배포를 조기에 잡아냅니다.
- **RUM 기반 monitor/SLO**: RUM 이벤트에서 custom metric(100% 트래픽 반영, 15개월 retention)을 생성해 INP p75 임계 초과, crash-free sessions 같은 사용자 중심 SLO를 겁니다.
- **Logs 상관**: 브라우저 로그가 `session_id`/`view.id`로 RUM 세션과 자동 연결됩니다.

RUM은 APM, Logs, Synthetics, Infrastructure와 함께 Datadog의 single pane of glass를 구성하는 한 축입니다.

---

## 5. RUM vs Synthetic vs APM

세 가지는 경쟁이 아니라 보완 관계입니다.

![RUM vs Synthetic vs APM 위치도 - client-side(RUM, Synthetic)와 server-side(APM) 구분 및 함께 쓰기](/assets/img/observability/datadog-rum-03-positioning.webp)

| 구분          | RUM                     | Synthetic Monitoring        | APM                          |
| :------------ | :---------------------- | :-------------------------- | :--------------------------- |
| **관측 위치** | client-side             | client-side (스케줄 실행)   | server-side                  |
| **트래픽**    | 실사용자                | 합성(simulated)             | 실제 백엔드 요청             |
| **목적**      | 실제 경험 측정          | 선제적 회귀/가용성 검증     | 백엔드 병목 추적             |
| **데이터 단위** | session / view        | test run                    | trace / span                 |

Synthetic으로 사용자가 겪기 전에 회귀를 잡고, RUM으로 실제 영향을 측정하며, APM으로 server-side 근본 원인을 추적합니다. `allowedTracingUrls`가 RUM과 APM을 이어 frontend부터 backend까지 전 구간을 커버합니다.

---

## 6. 도입 방법 개요

브라우저 기준으로, Datadog UI의 `Digital Experience > Add an Application`에서 JavaScript 타입으로 애플리케이션을 만들면 `applicationId`와 `clientToken`이 발급됩니다. `clientToken`은 **client-side에 노출돼도 안전한 write-only 토큰**이라 프론트 코드에 그대로 넣습니다(Datadog API key와 다름). 이후 `@datadog/browser-rum`을 설치하고 초기화합니다.

```javascript
import { datadogRum } from '@datadog/browser-rum';

datadogRum.init({
  applicationId: '<APPLICATION_ID>',
  clientToken: '<CLIENT_TOKEN>',
  site: 'datadoghq.com',            // EU: datadoghq.eu, AP1: ap1.datadoghq.com 등 region별로 다름
  service: 'my-web-app',
  env: 'production',
  version: '1.0.0',                 // source map / 배포 추적의 기준
  sessionSampleRate: 100,           // RUM 세션 수집 비율
  sessionReplaySampleRate: 20,      // 위에서 수집된 세션 중 Session Replay 녹화 비율 (기본 0)
  trackUserInteractions: true,      // action + frustration signals
  trackResources: true,
  trackLongTasks: true,
  defaultPrivacyLevel: 'mask-user-input',
  allowedTracingUrls: ['https://api.example.com'],  // APM trace 연결 대상
});
```

- **Sampling은 2단계**입니다. `sessionSampleRate`가 어떤 세션을 수집할지 정하고, `sessionReplaySampleRate`는 그중 **얼마나 replay를 녹화할지**를 정합니다. 둘은 곱으로 동작하므로 `100 x 20`이면 전체의 약 20%가 replay됩니다. `sessionReplaySampleRate`는 기본 0이라 올리기 전까지 replay가 녹화되지 않습니다.
- **Privacy(PII)**: `defaultPrivacyLevel`은 `mask` / `mask-user-input` / `allow` 중 하나입니다. **마스킹은 SDK가 데이터를 보내기 전 client-side에서 적용**되어, 마스킹된 내용은 Datadog로 전송되지 않습니다(GDPR/PIPA 대응의 근거). password/email/tel 입력과 credit-card autocomplete 필드는 설정과 무관하게 항상 마스킹됩니다. 요소 단위로는 `data-dd-privacy` 속성이나 `dd-privacy-*` 클래스로 override합니다.
- **`site` 주의**: region을 잘못 지정하면 데이터가 조용히 전송되지 않습니다. 내 조직의 Datadog region에 맞게 설정해야 합니다.
- **SPA route change**: Browser SDK는 History API(`pushState`/`replaceState`/`popstate`)로 SPA 화면 전환을 감지해 새 View를 만듭니다. 자동 감지가 안 맞는 프레임워크에서는 `trackViewsManually` + `startView` API로 수동 instrumentation합니다.

---

## 7. 주의사항 / 한계 / 비용 모델

### 7.1. RUM이 못 하는 것 (한계)

- **client-side 전용**: 백엔드 내부는 APM 없이는 보이지 않습니다. full-stack은 trace linking이 전제입니다.
- **수집 누락 가능**: ad-blocker나 tracking 차단 브라우저가 SDK나 요청을 막을 수 있습니다.
- **샘플링된 데이터**: 완전한 audit log가 아닙니다. bot/crawler 트래픽이나 매우 짧은 bounce도 모두 잡히지는 않습니다.

### 7.2. sampling이 데이터를 어디서 자르나

| knob                       | 자르는 지점                                      | 영향                                            |
| :------------------------- | :----------------------------------------------- | :---------------------------------------------- |
| `sessionSampleRate`        | ingest 이전 (세션 자체를 수집 안 함)             | 버려진 세션은 영구 손실, 과금도 안 됨           |
| retention filter           | ingest 후 indexing 단계                          | Explorer에서만 빠짐. metric은 100% 세션 반영    |
| `sessionReplaySampleRate`  | 수집된 세션의 replay 녹화 여부                    | 세션 이벤트는 남고 replay 영상만 없음           |

RUM without Limits는 ingestion과 retention을 분리해, `sessionSampleRate: 100`으로 전부 수집하면서 retention filter로 가치 있는 세션만 장기 보관하는 모델을 제공합니다.

### 7.3. 비용 모델

Datadog RUM은 **ingest된 세션 1,000개 단위(per 1,000 sessions)** 로 과금합니다. 세션은 15분 비활동/최대 4시간 경계로 끊깁니다. base RUM, Session Replay 포함(더 높은 요율), Mobile RUM, 그리고 별도 제품인 Product Analytics 등으로 나뉩니다.

> 정확한 가격과 tier 구성은 자주 바뀝니다. 본문은 **과금 모델**만 설명하므로, 실제 도입 시에는 [공식 pricing 페이지](https://www.datadoghq.com/pricing/)에서 현재 수치를 확인하시기 바랍니다.  
{: .prompt-warning}

---

## 8. 시리즈 맵

이 글은 Datadog observability 시리즈의 첫 글입니다. 앞으로 다음 주제를 이어갈 예정입니다.

- **(1) Datadog RUM 알아보기** - 개념, 데이터 모델, 관측 항목, observability 향상 (현재 글)
- (2) RUM 도입 실습 - Browser SDK 설정과 Session Replay, frustration signals 확인
- (3) RUM + APM trace linking - frontend부터 backend까지 full-stack 추적
- (4) RUM 기반 monitor와 SLO - 실사용자 중심 알림과 신뢰성 목표

---

## 9. Reference

- [Datadog Docs - Real User Monitoring](https://docs.datadoghq.com/real_user_monitoring/)
- [Datadog Docs - Understanding the RUM Event Hierarchy](https://docs.datadoghq.com/real_user_monitoring/guide/understanding-the-rum-event-hierarchy/)
- [Datadog Docs - Browser RUM Data Collected](https://docs.datadoghq.com/real_user_monitoring/application_monitoring/browser/data_collected/)
- [Datadog Docs - Monitoring Page Performance](https://docs.datadoghq.com/real_user_monitoring/application_monitoring/browser/monitoring_page_performance/)
- [Datadog Docs - Frustration Signals](https://docs.datadoghq.com/real_user_monitoring/application_monitoring/browser/frustration_signals/)
- [Datadog Docs - Session Replay](https://docs.datadoghq.com/session_replay/)
- [Datadog Docs - Session Replay Privacy Options](https://docs.datadoghq.com/session_replay/browser/privacy_options/)
- [Datadog Docs - RUM Error Tracking](https://docs.datadoghq.com/real_user_monitoring/error_tracking/)
- [Datadog Docs - Connect RUM and Traces](https://docs.datadoghq.com/tracing/other_telemetry/rum/)
- [Datadog Docs - RUM Browser Setup](https://docs.datadoghq.com/real_user_monitoring/application_monitoring/browser/setup/client/)
- [Datadog Docs - RUM without Limits](https://docs.datadoghq.com/real_user_monitoring/rum_without_limits/)
- [Datadog Docs - RUM Billing](https://docs.datadoghq.com/account_management/billing/rum/)
- [Datadog Docs - RUM and Product Analytics](https://docs.datadoghq.com/product_analytics/guide/rum_and_product_analytics/)
- [Datadog Docs - Mobile Vitals (Android)](https://docs.datadoghq.com/real_user_monitoring/application_monitoring/android/mobile_vitals/)
- [web.dev - Interaction to Next Paint (INP)](https://web.dev/articles/inp)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
