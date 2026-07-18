---
title: White-Box vs Black-Box 모니터링 방법론 소개
date: 2025-10-09 01:02:31 +0900
author: kkamji
categories: [Monitoring & Observability]
tags: [kubernetes, devops, sre, observability, monitoring, black-box, white-box, google-sre]
comments: true
image:
  path: /assets/img/observability/white-box_black-box.webp
---

서비스가 느리거나 오류를 낼 때 운영자가 먼저 알아야 할 사실은 두 가지입니다. 사용자가 지금 영향을 받고 있는지, 그리고 어느 계층을 조사해야 하는지입니다. 이 질문을 각각 잘 다루는 접근이 Black-box Monitoring과 White-box Monitoring입니다.

> **TL;DR**  
> - Black-box Monitoring은 사용자에게 보이는 동작을 검사해 현재의 증상을 찾습니다.  
> - White-box Monitoring은 애플리케이션과 인프라가 노출한 내부 신호로 원인과 임박한 위험을 좁힙니다.  
> - 페이지는 사용자 영향이 있는 증상에 우선 연결하고, 내부 지표는 진단과 용량 관리에 사용합니다.  
{: .prompt-info}

---

## 1. 두 접근의 역할

Google SRE는 모니터링을 시스템의 실시간 정량 데이터를 수집, 처리, 집계, 표시하는 활동으로 정의합니다. 이 활동은 장기 추세 분석과 디버깅에도 쓰이지만, 온콜을 깨우는 경보에서는 신호 대비 잡음이 특히 중요합니다.

| 구분 | Black-box Monitoring | White-box Monitoring |
| --- | --- | --- |
| 관찰 위치 | 시스템 바깥 | 시스템 내부 |
| 핵심 질문 | 사용자가 지금 실패를 경험하는가 | 어느 구성 요소가 왜 실패하거나 포화되는가 |
| 대표 신호 | 합성 요청의 성공 여부, 종단 간 지연 시간, 응답 내용 | 요청 수, 오류 수, 큐 길이, 연결 풀, CPU, 메모리 |
| 강점 | 실제 사용자 영향에 가까운 경보 | 재시도에 가려진 실패와 임박한 포화를 조기에 파악 |
| 한계 | 원인 식별에 필요한 단서가 적음 | 내부 신호만으로 사용자 영향 여부를 단정하기 어려움 |

두 방식은 계층에 따라 상대적입니다. 데이터베이스 팀에 느린 읽기는 증상일 수 있지만, 웹 서비스 팀에는 그 지연이 원인일 수 있습니다. 따라서 "Black-box는 증상, White-box는 원인"이라는 구분은 출발점으로만 사용해야 합니다.

두 관측은 서로의 빈틈을 메웁니다. 합성 점검이 성공해도 특정 지역, 로그인 상태, 결제 수단에서만 발생하는 실패는 놓칠 수 있습니다. 반대로 내부 오류율이 상승해도 retry와 cache가 사용자를 보호하고 있다면 즉시 page를 보낼 이유는 약합니다. 사용자 여정 SLI와 내부 신호를 같은 incident timeline에서 비교해야 이 차이를 판단할 수 있습니다.

```mermaid
flowchart LR
    U[사용자 또는 합성 점검] --> B[Black-box: 성공 여부와 지연 시간]
    B -->|영향 확인| A[증상 기반 경보]
    A --> W[White-box: 메트릭, 로그, 트레이스]
    W --> D[원인 범위 축소와 복구]
```

---

## 2. Black-box Monitoring

Black-box Monitoring은 내부 구현을 전제하지 않고 외부에서 보이는 동작을 시험합니다. 예를 들어 별도 위치에서 로그인 API를 호출하고, TLS 연결부터 응답 본문 검증까지 성공했는지 측정할 수 있습니다. 단순한 HTTP 200 확인만으로는 잘못된 콘텐츠나 인증 실패를 놓칠 수 있으므로, 중요한 사용자 여정에서는 성공 조건을 업무 결과까지 정의해야 합니다.

### 2.1. 무엇을 측정할까

- 가용성: 지정한 요청이 성공 조건을 충족한 비율
- 지연 시간: 성공 요청과 실패 요청을 구분한 종단 간 응답 시간
- 정확성: 기대한 데이터, 권한, 결제 결과처럼 응답 코드만으로 표현되지 않는 결과
- 도달성: DNS, TLS, 네트워크 경로를 포함해 관측 지점에서 대상에 연결할 수 있는지

Prometheus Blackbox Exporter 같은 multi-target exporter는 대상에 에이전트를 설치하지 않고 네트워크로 probe를 수행합니다. 이는 특정 관측 지점에서 웹사이트의 도달성과 지연 시간을 확인할 때 적합합니다. 다만 probe 위치가 실제 사용자와 다르면 결과도 달라질 수 있으므로, 중요한 지역이나 네트워크 경로는 별도 대상으로 설계합니다.

### 2.2. 경보에 우선하는 이유

사용자 영향이 이미 발생한 증상은 경보의 우선순위를 정하기 쉽습니다. Prometheus도 가능한 한 스택 상단의 지연 시간과 오류율에 경보를 걸고, 원인을 찾을 수 있는 콘솔을 연결하라고 권장합니다. 반대로 내부 CPU 사용률 하나만으로 즉시 페이지를 보내면, 실제 영향이 없는 일시적 부하까지 온콜을 방해할 수 있습니다.

---

## 3. White-box Monitoring

White-box Monitoring은 애플리케이션 코드, 런타임, 데이터베이스, 큐, Kubernetes가 노출한 신호를 수집합니다. 코드 계측은 경보에서 코드까지 추적하기 쉬운 위치에 메트릭을 두는 것이 좋습니다. 온라인 서비스라면 요청 수, 오류 수, 지연 시간, 진행 중인 요청 수가 기본 신호입니다.

### 3.1. 조사에 유용한 신호

| 영역 | 먼저 볼 신호 | 확인할 질문 |
| --- | --- | --- |
| 요청 처리 | 요청률, 오류율, 지연 시간 분포 | 특정 경로 또는 의존성에서만 실패하는가 |
| 포화 | 큐 길이, 연결 풀 대기, CPU, 메모리, 디스크 여유 | 처리 능력보다 수요가 큰가 |
| 의존성 | 클라이언트와 서버 양쪽의 오류와 지연 | 서버 문제인가, 두 서비스 사이 경로 문제인가 |
| 배포 | 버전별 오류와 지연, 재시작 수 | 변경 직후에 영향이 시작됐는가 |

라벨은 분석에 유용하지만 무제한으로 늘리면 시계열 수와 저장 비용이 급증합니다. 사용자 ID, 요청 ID처럼 값의 종류가 계속 늘어나는 값은 메트릭 라벨보다 로그나 트레이스에 두는 편이 안전합니다.

### 3.2. Golden Signals로 시작하기

사용자 대상 서비스의 첫 대시보드는 다음 네 신호로 시작할 수 있습니다.

- Latency: 성공과 실패를 구분한 응답 시간과 긴 꼬리 지연 시간
- Traffic: 요청 수, 세션 수, 처리량처럼 서비스 수요를 나타내는 값
- Errors: 명시적 오류뿐 아니라 잘못된 결과와 목표 시간 초과를 포함한 실패
- Saturation: 가장 부족한 자원의 포화도와 포화에 가까워지는 추세

이 네 신호는 모든 문제의 원인을 설명하지는 않습니다. 대신 사용자 영향, 수요 변화, 실패, 자원 한계를 한 화면에서 연결하는 최소한의 출발점이 됩니다.

---

## 4. 운영 흐름

1. 사용자 여정에서 성공과 실패를 정의하고 Black-box SLI를 만듭니다. SLI는 목표의 근거가 되는 측정값이고, SLO는 그 SLI에 약속한 목표 수준입니다.
2. 그 SLI의 오류 예산을 빠르게 소모하는 사건에만 긴급 경보를 연결합니다. 오류 예산은 SLO를 만족하면서 허용되는 실패량이며, 소진 속도는 긴급도를 정하는 기준이 됩니다.
3. 경보에는 관련 대시보드, 로그 검색, 트레이스 탐색 경로를 함께 둡니다.
4. White-box 신호로 배포, 의존성, 포화 중 어디를 먼저 조사할지 좁힙니다.
5. 반복되는 원인은 자동화하거나 제거하고, 더 이상 행동으로 이어지지 않는 경보는 정리합니다.

이 흐름의 핵심은 모든 내부 이상을 페이지로 보내지 않는 데 있습니다. 원인 신호는 진단과 예방에 중요하지만, 페이지는 긴급하고 행동 가능하며 실제 또는 임박한 사용자 영향과 연결되어야 합니다.

---

## 5. 마무리

Black-box Monitoring은 "서비스가 지금 기대한 결과를 내는가"를 확인합니다. White-box Monitoring은 "어느 내부 상태가 그 결과에 영향을 주는가"를 설명합니다. 둘 중 하나를 선택하는 문제가 아니라, 증상으로 경보를 시작하고 내부 신호로 복구 시간을 줄이는 조합이 안정적인 운영의 기본입니다. 새 경보를 만들 때는 먼저 "이 신호가 사용자의 어떤 실패를 설명하는가"와 "누가 어떤 조치를 할 수 있는가"를 답해 보세요. 두 질문에 답하지 못하면 page보다 dashboard나 capacity planning 신호일 가능성이 큽니다.

---

## 6. Reference

- [Google SRE Book - Monitoring Distributed Systems](https://sre.google/sre-book/monitoring-distributed-systems/)
- [Google SRE Workbook - Alerting on SLOs](https://sre.google/workbook/alerting-on-slos/)
- [Prometheus - Instrumentation](https://prometheus.io/docs/practices/instrumentation/)
- [Prometheus - Multi-target exporter pattern](https://prometheus.io/docs/guides/multi-target-exporter/)
- [Prometheus - Alerting](https://prometheus.io/docs/practices/alerting/)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
