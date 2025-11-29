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

## 1. Overview

마이크로서비스와 분산 시스템이 복잡해질수록, 우리는 점점 더 많은 대시보드와 알람에 노출되며, 실제로 중요한 문제의 원인을 찾지 못한 채 “무엇이 고장 났는가”만 반복적으로 확인하는 경우가 많습니다.  

하지만 **SRE 관점에서의 모니터링**은 단순히 장애를 ‘탐지’하는 것이 아닌, **문제의 징후(Symptom)를 신속히 감지하고**, 동시에 **근본 원인(Root Cause)을 파악할 수 있는 구조를 갖추는 것**입니다.  

이를 위한 가장 기본적이면서도 강력한 두 가지 방법론이 바로 **Black-Box Monitoring**과 **White-Box Monitoring**입니다.

---

## 2. Black-Box & White-Box Monitoring 소개

| 구분          | 블랙박스 모니터링 (Black-Box)                      | 화이트박스 모니터링 (White-Box)                    |
| ------------- | -------------------------------------------------- | -------------------------------------------------- |
| **관점**      | 외부 사용자 관점, 서비스의 “결과” 관찰             | 시스템 내부 관점, 동작의 “원인” 분석               |
| **초점**      | 증상(Symptom) 감지 — 가용성, 지연 시간, 정확성     | 원인(Cause) 파악 — 자원 제약, 내부 상태, 로직 이상 |
| **대표 예시** | 업타임 체크, 합성 모니터링, 종단 간 요청 지연 측정 | CPU 사용률, 메시지 큐 깊이, DB 연결 풀 상태        |
| **SRE 철학**  | 사용자가 체감하는 문제를 측정 (SLO 기반)           | 근본 원인을 신속히 추적해 복구 시간을 단축         |

- Black-Box Monitoring: 시스템 외부(사용자) 관점에서 시스템을 관찰하여 문제가 발생했음을 파악 -> "**무엇이 고장 났는가?**"
- White-Box Monitoring: 시스템 내부(시스템) 관점에서 문제가 왜 발생했는지(근본 원인)를 파악 -> "**왜 고장 났는가?**"

> Black-Box와 White-Box Monitoring은 서로 대체하는 관계가 아닌 상호 보완적 관계입니다.  
{: .prompt-tip}

---

## 3. Black-Box Monitoring 개념

Black-Box Monitoring은 사용자가 경험하는 것을 측정하는 것을 목표로, 외부 관찰자 관점에서 시스템을 바라보는 방식입니다. 시스템의 내부 구현에 대한 지식 없이, 외부에서 관찰 가능한 동작에만 집중합니다. 치명적인 장애 발생을 신속하게 감지하여 "**무엇이 고장 났는가?**"를 파악할 때 사용합니다. Black-Box Monitoring은 **사용자 체감 문제**를 빠르게 감지하기 위한 경보의 핵심입니다.

SLO는 사용자 경험 중심인 Black-Box Monitoring 기반으로 수립되어야 하며, SLO Alarm 또한 사용자가 체감하는 증상에 맞춰 Alarm을 설정해야 합니다.

### 3.1. Black-Box Monitoring의 대표적인 예시

- **가용성(Availability):** 웹 서비스가 99.9%의 시간 동안 정상 응답을 반환하는가  
- **지연 시간(Latency):** API 응답이 300ms 이내인가  
- **정확성(Correctness):** 응답 데이터가 올바른 값을 포함하는가  
- **Synthetic Monitoring (합성 모니터링):** 실제 사용자의 동작을 스크립트로 재현하여 서비스 전반의 상태를 주기적으로 점검  

---

## 4. White-Box Monitoring

White-Box Monitoring은 시스템 내부 상태에서 노출되는 메트릭, 로그, 트레이스를 기반으로 시스템의 구체적인 내부 상태와 동작방식을 이해하고, 문제의 근본 원인(Root Cause)를 진단합니다. 문제가 발생했을 때 시스템 구성 요소의 내부 자원 제약이나 알려진 이슈를 추적하는 데 활용하며, "**왜 고장 났는가?**"를 파악할 때 사용합니다.

해당 접근 방법은 단순한 지표 수집을 넘어서 시스템의 **행동 양상(Behavior)**를 모델링하고 **이상 징후(Anomaly)**를 감지하는 데 목적이 있습니다.

### 4.1. White-Box Monitoring의 대표적인 예시

- **리소스 관찰 (Resource Metrics):** CPU, 메모리, 네트워크 사용률  
- **큐 및 연결 상태 (Queue Depth / Connection Pool):** 메시지 지연, DB 연결 포화  
- **애플리케이션 카운터:** 요청 수, 실패율, 에러 코드 분포  
- **구조화 로그 & 트레이스:** 로그와 분산 추적을 결합하여 병목 원인 분석  

---

## 5. 마무리

모니터링의 목적은 **장애를 없애는 것**이 아니라, **장애가 발생했을 때 빠르게 이해하고 대응하는 능력**을 기르는 데 있습니다.

- **Black-Box**는 사용자의 관점에서 시스템의 **증상(Symptom)**을 탐지하고,  
- **White-Box**는 내부 상태를 분석해 **원인(Cause)**을 규명합니다.

SRE는 이 두 가지 관점을 결합하여 **“관찰 가능한 시스템(Observable System)”**을 만드는 데 초점을 둡니다. 즉, 단순한 ‘수집’이 아니라 **의미 있는 해석이 가능한 데이터 구조**가 핵심입니다.

---

## 6. Reference

- [Google SRE Book — Monitoring Distributed Systems](https://sre.google/sre-book/monitoring-distributed-systems/)
- [Google SRE Workbook — Monitoring, Alerting on SLOs](https://sre.google/workbook/monitoring/)
- [OpenTelemetry Docs — Collector](https://opentelemetry.io/docs/collector/)
- [OpenTelemetry Specs — Overview](https://opentelemetry.io/docs/specs/otel/overview/)
- [Prometheus — Blackbox Exporter](https://github.com/prometheus/blackbox_exporter)
- [Prometheus — Alerting Best Practices](https://prometheus.io/docs/practices/alerting/)
- [Brendan Gregg — USE Method](https://www.brendangregg.com/usemethod.html)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
