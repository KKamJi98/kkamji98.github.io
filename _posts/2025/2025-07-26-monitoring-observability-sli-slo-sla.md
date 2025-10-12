---
title: Monitoring VS Observability + SLI/SLO/SLA 알아보기 [Cilium Study 2주차]
date: 2025-07-26 01:29:14 +0900
author: kkamji
categories: [Monitoring & Observability]
tags: [kubernetes, devops, monitoring, observability, sli, slo, sla, cilium, cilium-study, cloudnet, gasida]
comments: true
image:
  path: /assets/img/observability/monitoring_and_observability_and_sli_slo_sla.webp
---

이번 글에서는 **Monitoring(모니터링)**과 **Observability(관측 가능성)**의 차이를 정리하고, **SLI/SLO/SLA** 개념에 대해 알아보도록 하겠습니다.

### 관련 글

1. [Vagrant와 VirtualBox로 Kubernetes Cluster 구축하기 [Cilium Study 1주차]]({% post_url 2025/2025-07-14-deploy-kubernetes-vagrant-virtualbox %})
2. [Flannel CNI 배포하기 [Cilium Study 1주차]]({% post_url 2025/2025-07-15-deploy-flannel-cni %})
3. [Cilium CNI 알아보기 [Cilium Study 1주차]]({% post_url 2025/2025-07-16-cilium-cni-basic %})
4. [Cilium 구성요소 & 배포하기 (kube-proxy replacement) [Cilium Study 1주차]]({% post_url 2025/2025-07-18-deploy-cilium %})
5. [Cilium Hubble 알아보기 [Cilium Study 2주차]]({% post_url 2025/2025-07-21-hubble-basic %})
6. [Cilium & Hubble Command Cheat Sheet [Cilium Study 2주차]]({% post_url cheat-sheet/2025-07-23-cilium-hubble-cheat-sheet %})
7. [Star Wars Demo와 함께 Cilium Network Policy 알아보기 [Cilium Study 2주차]]({% post_url 2025/2025-07-24-hubble-demo %})
8. [Hubble Exporter와 Dynamic Exporter Configuration [Cilium Study 2주차]]({% post_url 2025/2025-07-25-hubble-exporter %})
9. [Monitoring VS Observability + SLI/SLO/SLA 알아보기 [Cilium Study 2주차] (현재 글)]({% post_url 2025/2025-07-26-monitoring-observability-sli-slo-sla %})
10. [Cilium Metric Monitoring with Prometheus + Grafana [Cilium Study 2주차]]({% post_url 2025/2025-07-27-hubble-metric-monitoring-with-prometheus-grafana %})
11. [Cilium Log Monitoring with Grafana Loki & Grafana Alloy [Cilium Study 2주차]]({% post_url 2025/2025-07-28-hubble-log-monitoring-with-grafana-loki %})
12. [IPAM 개념 및 Kubernetes Host Scope -> Cluster Scope Migration 실습 [Cilium Study 3주차]]({% post_url 2025/2025-07-29-cilium-ipam-mode %})
13. [Cilium Network Routing 이해하기 – Encapsulation과 Native Routing 비교 [Cilium Study 3주차]]({% post_url 2025/2025-08-03-cilium-routing %})
14. [Cilium Native Routing 통신 확인 및 문제 해결 – Static Route & BGP [Cilium Study 4주차]]({% post_url 2025/2025-08-10-cilium-native-routing %})
15. [Cilium BGP Control Plane [Cilium Study 5주차]]({% post_url 2025/2025-08-11-cilium-bgp-control-plane %})
16. [Cilium Service LoadBalancer BGP Advertisement & ExternalTrafficPolicy [Cilium Study 5주차]]({% post_url 2025/2025-08-12-cilium-lb-ipam %})
17. [Kind로 Kubernetes Cluster 배포하기 [Cilium Study 5주차]]({% post_url 2025/2025-08-13-kind %})
18. [Cilium Cluster Mesh [Cilium Study 5주차]]({% post_url 2025/2025-08-14-cilium-cluster-mesh %})
19. [Cilium Service Mesh [Cilium Study 6주차]]({% post_url 2025/2025-08-18-cilium-service-mesh %})
20. [Kube-burner 소개 및 실습 [Cilium Study 7주차]]({% post_url 2025/2025-08-25-kube-burner %})
21. [Cilium Network Security [Cilium Study 8주차]]({% post_url 2025/2025-09-03-cilium-network-security %})

---

## 1. Monitoring 개념

**Monitoring**은 **사전에 정의한 지표를 기준으로 시스템 상태를 감시하고 이상을 알리는 활동**입니다. 주로 CPU 사용률, 에러율, 요청 수 같은 메트릭을 수집하고, 임계치를 넘으면 경고를 보내는 방식으로 동작합니다.

- 목표: 문제 발생 여부와 시점을 빠르게 감지하여 팀이 즉시 대응할 수 있도록 합니다.
- 데이터 소스: 미리 선정한 메트릭과 상태 값이 중심입니다.
- 적용 대상: 비교적 동작이 예측 가능한 시스템, 정해진 기준으로 충분히 감시 가능한 대상입니다.
- 사용 방식: 대시보드 확인, 알람(Alert) 발송, 정적 임계치 기반 룰이 일반적입니다.

> "정의된 정상 범위를 벗어났는가?"를 빠르게 알려주는 시스템  
{: .prompt-tip}

---

## 2. Observability 개념

**Observability**는 **시스템 외부에서 관찰 가능한 모든 출력(로그, 메트릭, 트레이스 등)을 활용해 내부 상태와 원인을 이해할 수 있는 능력**입니다. **Monitoring**이 "무엇이 잘못됐는가"를 알려준다면, 관측 가능성은 "왜, 어디서, 어떻게 잘못됐는가"까지 파고들 수 있게 합니다. 특히 알려지지 않은 유형의 문제를 탐지하고 분석하는 데 필수적입니다.

- 목표: 원인 진단과 성능 최적화를 가능하게 합니다.
- 데이터 소스: 로그, 메트릭, 트레이스, 이벤트 등 다양한 신호를 통합합니다.
- 적용 대상: 복잡한 분산 시스템, 마이크로서비스 아키텍처, 빠르게 변하는 환경입니다.
- 사용 방식: 임시 쿼리, 상관관계 분석, 가설 검증 등 동적이고 탐색적인 분석이 핵심입니다.

> "알 수 없던 문제를 발견하고, 근본 원인을 추적하는 역량"  
{: .prompt-tip}

---

## 3. Monitoring과 Observability 비교

아래 표는 위에서 정의한 핵심 차이를 정리한 것입니다.

| 구분      | 모니터링(Monitoring)                                       | 관측 가능성(Observability)                            |
| :-------- | :--------------------------------------------------------- | :---------------------------------------------------- |
| 정의      | 사전에 정의한 지표로 상태를 감시하고 문제 발생 여부를 파악 | 외부 출력 데이터를 바탕으로 내부 상태와 원인까지 이해 |
| 초점      | 알려진 지표와 임계치 기반 경보                             | 알려지지 않은 문제 탐지, 탐색형 분석                  |
| 데이터    | 주로 메트릭                                                | 로그, 메트릭, 트레이스, 이벤트 등 다양한 신호         |
| 사용 패턴 | 대시보드 확인, 정적 알람                                   | 임시 쿼리, 가설 검증, 상관관계 분석                   |
| 적용 환경 | 단순·정형 시스템                                           | 분산 마이크로서비스, 클라우드 네이티브 등 복잡한 환경 |

---

## 4. 관측 가능성의 세 가지 핵심 신호 (Metrics, Logs, Traces)

관측 가능성을 구성하는 대표 신호는 메트릭, 로그, 트레이스입니다. 각각의 성격을 먼저 이해한 뒤, 어떤 질문에 어떤 신호가 필요한지 판단해야 합니다.

- 메트릭: 수치 기반 시계열 데이터로 추세 확인과 임계치 경보에 적합합니다.
- 로그: 이벤트에 대한 텍스트 기록으로 디버깅에 유리하며, 시점별 상세 정보를 남깁니다.
- 트레이스: 분산 트랜잭션 경로와 지연 시간을 보여주어 병목 지점을 분석할 수 있습니다.

| 비교 항목   | 메트릭(Metrics)             | 로그(Logs)                     | 트레이스(Tracing)                       |
| :---------- | :-------------------------- | :----------------------------- | :-------------------------------------- |
| 정의        | 수치로 표현된 시계열 데이터 | 이벤트 기반 텍스트 데이터      | 요청 흐름(분산 트랜잭션) 데이터         |
| 예시 데이터 | CPU 사용률, 요청 수, 에러율 | 오류 메시지, 접근 로그         | 서비스 간 호출 경로, 지연 시간          |
| 주요 목적   | 성능 모니터링, 알림         | 디버깅, 포렌식 분석            | 병목 분석, 근본 원인 파악               |
| 저장 방식   | TSDB (예: Prometheus)       | Log-Store (ELK Stack, Loki 등) | 분산 트레이싱 시스템(Jaeger, Zipkin 등) |

> 처음에는 메트릭으로 "이상 징후"를 감지하고, 로그와 트레이스로 왜 그랬는지를 파고드는 흐름으로 접근하면 좋을 것 같습니다.  
{: .prompt-tip}

---

## 5. SLI, SLO, SLA의 의미와 차이

Monitoring/Observability로 수집한 데이터를 조직의 공통 언어로 수치화하려면 **SLI/SLO/SLA**가 필요합니다. 먼저 용어를 간단히 정리하면 다음과 같습니다.

- SLI(Service Level Indicator): 실제로 측정한 서비스 성능 지표입니다.
- SLO(Service Level Objective): 우리가 지켜야 하는 목표 수준입니다.
- SLA(Service Level Agreement): 고객과 맺은 공식 계약으로, 목표 미달 시 보상 조항이 포함될 수 있습니다.

| 비교 항목   | SLI (Service Level Indicator)                 | SLO (Service Level Objective)    | SLA (Service Level Agreement)         |
| :---------- | :-------------------------------------------- | :------------------------------- | :------------------------------------ |
| 정의        | 서비스 성능을 정량적으로 측정하는 지표입니다. | 유지해야 하는 성능 목표입니다.   | 고객과 체결하는 공식 계약 수준입니다. |
| 목적        | 현재 품질 상태 모니터링                       | 내부 목표 설정 및 품질 유지·개선 | 법적·금전적 보상 기준 제공            |
| 예시        | 100ms 이내 응답 비율 99.9%                    | "에러율 0.1% 이하 유지"          | 99.9% 미만 시 요금 일부 환불          |
| 법적 구속력 | 없음                                          | 없음                             | 있음                                  |

### 5.1. SLI 계산 예시

SLI(가용성) = (성공한 요청 수) / (총 요청 수)
SLI(지연 시간) = (특정 임계치 이하 응답 비율) / (총 요청 수)

### 5.2. SLO 설정 예시

"우리는 한 달 동안 99.9% 이상의 요청이 100ms 이내로 응답해야 한다"
"오류율이 월간 0.1%를 넘지 않아야 한다"

### 5.3. Error Budget 개념

SLO를 99.9%로 설정했다면, 남은 0.1%는 오류 허용치(Error Budget)입니다. 서비스의 SLI 지표가 SLO에 위협이 될 정도로 하락하면 신규 배포를 중단하거나 안정화 작업을 우선순위로 두는 등 운영 정책을 결정할 수 있습니다.

---

## 6. 실무 적용 가이드

### 6.1. Static Monitoring + Dynamic Observability 조합

- 평시에는 정적으로 정의한 경보 규칙과 대시보드로 비용을 최소화합니다.
- 장애나 성능 저하가 발생하면 관측 가능성을 강화합니다. ex) Hubble Exporter에서 Dynamic 규칙을 수정해 추가 필드를 기록하도록 하여 사건 대응에 필요한 데이터를 추가로 수집

### 6.2. 사용자 여정 기반 SLI 정의

- 로그인, 결제, 사진 업로드 등 비즈니스 임팩트가 큰 사용자 흐름을 기준으로 SLI를 설계
- "사용자가 클릭한 뒤 첫 화면이 보이기까지의 시간"처럼 사용자 경험에 직결되는 지표를 선정합

### 6.3. 도구 선택과 파이프라인 구성

- Metrics: Prometheus, Grafana
- Logs: Loki, ELK Stack
- Traces: Jaeger, Zipkin
- 통합/표준화: OpenTelemetry(OTel)를 활용해 동일한 스키마와 파이프라인을 유지

### 6.4. 비용과 성능 튜닝

- 이벤트 필터로 수집량을 먼저 줄이고, `fieldMask`로 필드 개수를 줄여 파일 크기와 CPU 사용량을 제어합니다.
- 파일 로테이션과 압축 정책을 설정하고, Exporter 프로세스의 CPU/메모리를 모니터링합니다.

---

## 7. 예시: Cilium Hubble Exporter로 보는 관측 가능성 강화

Cilium Hubble Exporter는 각 노드의 cilium-agent에서 네트워크 플로우를 파일로 저장할 수 있도록 제공합니다. 이때 다음과 같은 전략을 사용할 수 있습니다.

- Static Export: DROP/ERROR 이벤트 위주로 상시 수집해 비용을 통제합니다.
- Dynamic Export: 장애 대응 시 특정 서비스나 포트, 레이블에 대한 세밀한 필터를 켜고 원인 파악 후 제거
- fieldMask A/B 테스트로 어떤 필드 조합이 가장 효율적인지 측정합니다.
- 로그는 중앙 스토리지(Loki, S3 등)에 보관하고 만료 정책을 명확히 둡니다.

이렇게 하면 평균적인 운영 비용은 낮추면서도, 필요할 때 깊이 있는 데이터로 문제를 빨리 해결할 수 있습니다.

---

## 8. 마무리

**Monitoring**과 **Observability** 은 대체 관계가 아니라 보완 관계입니다. **Monitoring**으로 "이상이 발생했다"는 사실을 빠르게 확인하고, **Observability**으로 "왜 발생했는지"를 끝까지 추적합니다. 그리고 **SLI/SLO/SLA**는 이를 수치화하고 조직 내 공통 언어로 정착시키는 프레임워크입니다.

---

## 9. Reference

- [LY Corporation Tech Blog - 신뢰성 향상을 위한 SLI/SLO 도입 1편 - 소개와 필요성](https://techblog.lycorp.co.jp/ko/sli-and-slo-for-improving-reliability-1)
- [LY Corporation Tech Blog - 신뢰성 향상을 위한 SLI/SLO 도입 2편 - 플랫폼 적용 사례](https://techblog.lycorp.co.jp/ko/sli-and-slo-for-improving-reliability-2)
- [Google SRE Book - Service Level Objectives](https://sre.google/sre-book/service-level-objectives/)
- [Google SRE Book - Implementing SLOs](https://sre.google/workbook/implementing-slos)
- [Google Cloud - SRE fundamentals: SLIs, SLAs and SLOs](https://cloud.google.com/blog/products/devops-sre/sre-fundamentals-slis-slas-and-slos)
- [IBM - What is Observability?](https://www.ibm.com/topics/observability)
- [Cilium Docs - Configuring Hubble exporter](https://docs.cilium.io/en/stable/observability/hubble/configuration/export/)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
