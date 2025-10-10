---
title: Cilium Log Monitoring with Grafana Loki + Grafana Alloy [Cilium Study 2주차]
date: 2025-07-28 10:21:35 +0900
author: kkamji
categories: [Kubernetes, Cilium]
tags: [kubernetes, devops, monitoring, observability, sli, slo, sla, cilium-study, cloudnet]
comments: true
image:
  path: /assets/img/kubernetes/cilium/cilium.webp
---

저번 시간에는 Prometheus를 사용해 Cilium/Hubble의 상태를 수집했고, Grafana를 통해 Metric 시각화를 했습니다. 하지만 문제가 발생한 직후 원인을 빠르게 파악하기 위해서는 `L3`/`L4`/`L7` 레벨에서 **무엇이, 언제, 어디서, 왜** 일어났는지에 대한 로그와 해당 로그를 간편하게 조회할 수 있는 시스템이 필요합니다.

이번 글에서는 **Grafana Loki**와 **Grafana Alloy**에 대해 알아보고, 더 나아가 해당 툴을 사용해 **Cilium/Hubble Log Pipeline**을 구성하는 방법에 대해 알아보겠습니다.

- [Grafana Docs - Grafana Loki](https://grafana.com/docs/loki/latest/)
- [Grafana Docs - Grafana Alloy](https://grafana.com/docs/alloy/latest/)

### 관련 글

1. [Vagrant와 VirtualBox로 Kubernetes Cluster 구축하기 [Cilium Study 1주차]]({% post_url 2025/2025-07-14-deploy-kubernetes-vagrant-virtualbox %})
2. [Flannel CNI 배포하기 [Cilium Study 1주차]]({% post_url 2025/2025-07-15-deploy-flannel-cni %})
3. [Cilium CNI 알아보기 [Cilium Study 1주차]]({% post_url 2025/2025-07-16-cilium-cni-basic %})
4. [Cilium 구성요소 & 배포하기 (kube-proxy replacement) [Cilium Study 1주차]]({% post_url 2025/2025-07-18-deploy-cilium %})
5. [Cilium Hubble 알아보기 [Cilium Study 2주차]]({% post_url 2025/2025-07-21-hubble-basic %})
6. [Cilium & Hubble Command Cheat Sheet [Cilium Study 2주차]]({% post_url cheat-sheet/2025-07-23-cilium-hubble-cheat-sheet %})
7. [Star Wars Demo와 함께 Cilium Network Policy 알아보기 [Cilium Study 2주차]]({% post_url 2025/2025-07-24-hubble-demo %})
8. [Hubble Exporter와 Dynamic Exporter Configuration [Cilium Study 2주차]]({% post_url 2025/2025-07-25-hubble-exporter %})
9. [Monitoring VS Observability + SLI/SLO/SLA 알아보기 [Cilium Study 2주차]]({% post_url 2025/2025-07-26-monitoring-observability-sli-slo-sla %})
10. [Cilium Metric Monitoring with Prometheus + Grafana [Cilium Study 2주차]]({% post_url 2025/2025-07-27-hubble-metric-monitoring-with-prometheus-grafana %})
11. [Cilium Log Monitoring with Grafana Loki & Grafana Alloy [Cilium Study 2주차] (현재 글)]({% post_url 2025/2025-07-28-hubble-log-monitoring-with-grafana-loki %})
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

## 1. Grafana Loki란?

![Grafana Loki Overview](/assets/img/kubernetes/cilium/2w-grafana-loki-overview.webp)
> [Grafana Docs - Loki overview](https://grafana.com/docs/loki/latest/get-started/overview/)

Grafana Loki는 Prometheus에서 영감을 받아 개발된 수평 확장성과 고가용성을 갖춘 멀티테넌트 로그 집계 시스템입니다. 기존 로깅 시스템과 달리 Loki는 로그 전체 내용을 인덱싱하지 않고, 각 로그 스트림의 레이블(Label) 메타데이터만 인덱싱합니다. 이 설계 덕분에 작은 인덱스와 고도로 압축된 청크(Chunk) 구조로 저장이 가능하여 저장 비용이 저렴하고 운영이 간편합니다.

### 1.1. Grafana Loki 특징

| 특징                     | 설명                                                                                                                                                                                                                                 |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **비용 효율성**          | 로그 본문 전체를 인덱싱하지 않고, 각 로그 스트림의 **레이블(Label) 메타데이터**만 인덱싱.<br>작은 인덱스와 고도로 압축된 청크 저장 구조로 운영 비용 절감.<br>Elasticsearch 같은 풀텍스트 검색 시스템 대비 저장소 요구량이 훨씬 적음. |
| **확장성**               | 소규모(개발, PoC) 환경부터 페타바이트 규모의 대규모 환경까지 대응 가능.<br>**읽기(Read)**와 **쓰기(Write)** 경로를 독립적으로 확장할 수 있음.<br>모놀리식(단순 확장 가능 모드)과 마이크로서비스(분산 모드) 모두 지원.                |
| **멀티테넌시 지원**      | 하나의 Loki 인스턴스에서 여러 팀과 환경을 분리 운영 가능.<br>테넌트 ID를 통해 데이터와 요청을 논리적으로 분리.<br>API 요청 시 `X-Scope-OrgID` 헤더로 테넌트 지정.                                                                    |
| **유연한 저장소 백엔드** | Amazon S3, Google Cloud Storage, MinIO 등 객체 스토리지에 청크 저장 가능.<br>로컬 파일시스템 저장도 가능(개발 및 테스트 환경에 적합).<br>압축 및 청크 단위 저장 구조로 장기 보존에 효율적.                                           |
| **LogQL**                | PromQL과 유사한 ,Query 언어.<br>로그 필터링, 라벨 기반 집계, 시간 범위 지정 가능.<br>`rate()`, `count_over_time()` 등으로 로그를 메트릭처럼 분석 가능.                                                                               |
| **Grafana 연동**         | Grafana에서 Loki 데이터 소스를 추가하여 실시간 로그 조회.<br>메트릭과 트레이스와 함께 로그를 시각화하고 상관 분석 가능.<br>Explore 모드, 대시보드 패널, Alert Rule 모두 활용 가능.                                                   |
| **알림(Alerts)**         | Ruler 컴포넌트를 통해 로그 Query결과에 기반한 경보 생성.<br>Prometheus Alertmanager와 연계하여 Slack, Email, PagerDuty 등 다양한 채널로 알림 전송 가능.<br>특정 키워드, 에러율, 이벤트 패턴 감지 가능.                               |

### 1.2. Grafana Loki 구성 요소

![Grafana Loki Architecture](/assets/img/kubernetes/cilium/2w-grafana-loki-architecture.webp)
> [Grafana Docs - Loki Architecture](https://grafana.com/docs/loki/latest/get-started/architecture/)

Loki는 모듈형 시스템으로, 단일 바이너리(All-in-One)로도 실행할 수 있고, Read/Write/Backend 역할로 나누어 단순 확장형(Simple Scalable) 또는 마이크로서비스(Microservice) 형태로 구성할 수도 있습니다. 각 구성 요소에 대한 설명은 아래 표와 같습니다.

| 구성요소                                            | 역할                        | 주요 기능/세부 설명                                                                                                                                                                                                                                                                                                                            |
| --------------------------------------------------- | --------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Distributor**                                     | Write 경로의 첫 단계        | - 클라이언트로부터 로그 스트림을 수신<br>- **Validation**: 레이블 유효성, 타임스탬프 범위, 로그 길이 검증<br>- **Preprocessing**: 레이블 정렬(Caching 및 Hashing 최적화)<br>- **Rate Limiting**: 테넌트별 전송 속도 제한<br>- **Replication**: 일관성 해시 기반 N개의 Ingester로 데이터 전송(기본 3)<br>- 무상태(stateless) 구성으로 확장 용이 |
| **Ingester**                                        | 데이터 수집·저장·전송       | - In-memory Chunk 생성 및 압축<br>- 주기적으로 \*\*장기 저장소(S3/GCS/Azure Blob 등)\*\*로 전송<br>- Write Ahead Log(WAL) 지원으로 비정상 종료 시 데이터 보존<br>- 상태(State): `PENDING`, `JOINING`, `ACTIVE`, `LEAVING`, `UNHEALTHY`<br>- 중복 데이터 저장 방지(해시 기반)                                                                   |
| **Query Frontend**                                  | 읽기 성능 최적화            | - Querier API 엔드포인트 제공<br>- 대규모 Query **Split & 병렬 실행**<br>- FIFO 기반 **Query 큐잉**으로 테넌트별 공정성 보장<br>- 메트릭/로그 Query **Caching**(Memcached/Redis/In-memory)<br>- 대규모 Query OOM 방지                                                                                                                          |
| **Query Scheduler**                                 | 고급 큐잉 처리              | - Query Frontend에서 분할된 Query를 테넌트별 큐에 저장<br>- Querier가 Pull 방식으로 작업 처리<br>- 고가용성을 위해 2개 이상의 복제 권장                                                                                                                                                                                                        |
| **Querier**                                         | LogQL Query 실행            | - Ingester(메모리 데이터) + 장기 저장소 병합 조회<br>- 중복 로그 제거(동일 타임스탬프·레이블·메시지)<br>- 직접 API 처리 가능(단일 실행 모드)                                                                                                                                                                                                   |
| **Index Gateway**                                   | 메타데이터 Query 처리       | - 인덱스 기반 메타데이터 조회<br>- Chunk 참조 반환 및 Query 샤딩 지원<br>- 단순 모드/Hash Ring 모드 운영 가능                                                                                                                                                                                                                                  |
| **Compactor**                                       | 인덱스/로그 압축·보존 관리  | - 다중 인덱스 파일을 일 단위 단일 파일로 병합<br>- 인덱스 조회 효율성 향상<br>- **로그 보존(Deletion) 정책** 적용                                                                                                                                                                                                                              |
| **Ruler**                                           | 룰 기반 알림 처리           | - LogQL 기반 룰/알림 평가<br>- Object Storage 또는 로컬 저장소 사용 가능<br>- Query Frontend를 통한 원격 룰 평가 모드 지원                                                                                                                                                                                                                     |
| **Bloom Planner / Builder / Gateway** *(실험 기능)* | Bloom 필터 기반 검색 최적화 | - Planner: Bloom 생성 작업 계획 수립<br>- Builder: Bloom 블록 생성 및 메타데이터 관리<br>- Gateway: Bloom 기반 Chunk 필터링<br>- 대규모 환경에서 특정 레이블 검색 속도 향상                                                                                                                                                                    |

### 1.3. Grafana Loki Storage 구조

![Loki Data Format](/assets/img/kubernetes/cilium/2w-grafana-loki-data-format.webp)
> [Grafana Docs - Loki Architecture](https://grafana.com/docs/loki/latest/get-started/architecture/#data-format)

Loki는 모든 데이터를 Amazon S3, Google Cloud Storage(GCS), Azure Blob Storage 같은 단일 오브젝트 스토리지 백엔드에 저장합니다.
Loki 2.0 이후 Index Shipper 모드를 기본으로 사용하며, 인덱스(Index) 파일과 청크(Chunk) 파일 모두를 동일 스토리지에 보관합니다.

**주요 파일 타입**

- **Index**: 특정 라벨 세트의 로그 위치를 가리키는 목차 역할
- **Chunk**: 특정 라벨 세트 + 시간 범위의 로그 라인 데이터 묶음 (압축 저장)

### 1.4. Grafana Loki Wirte Path

1. Distributor가 HTTP POST(Log Stream)를 수신
2. Consistent Hash Ring 기반으로 Ingester 노드 선택
3. 데이터 복제(기본 3개 Ingester)
4. Ingester가 In-memory Chunk에 데이터 추가
5. 주기적으로 압축·저장소 전송
6. 과반수(Quorum) Ingester 승인 시 클라이언트에 성공 응답

### 1.5. Read Path (읽기 경로)

1. Query Frontend가 LogQL Query 수신
2. Query를 하위 작업으로 분할해 Query Scheduler에 전달
3. Querier가 Ingester 메모리 + Object Storage에서 데이터 조회
4. 중복 제거 및 결과 병합
5. 최종 응답 반환

---

## 2. Grafana Alloy란?

Grafana Alloy는 OpenTelemetry Collector를 기반으로 한 고성능, 유연한, 벤더 중립형(vendor-neutral) 수집기(Collector)로, 로그(Log), 메트릭(Metrics), 트레이스(Traces), 프로파일링(Profiling) 데이터를 단일 파이프라인에서 수집, 처리, 전송할 수 있도록 설계되었습니다. Promtail, Grafana Agent의 기능을 통합하면서도, 엔터프라이즈 환경에서의 확장성과 관리성까지 고려한 차세대 수집기입니다.

![Grafana Alloy Overview](/assets/img/kubernetes/cilium/2w-grafana-alloy-overview.webp)
> [Grafana Docs - Grafana Alloy](https://grafana.com/docs/alloy/latest/)

### 2.1. Grafana Alloy의 특징

| 특징                                   | 설명                                                                                                   |
| -------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| **All-in-One Observability Collector** | 애플리케이션과 인프라 모두에 대한 모든 원격 측정 데이터(로그, 메트릭, 트레이스, 프로파일링) 수집 가능. |
| **OpenTelemetry 호환**                 | OpenTelemetry, Prometheus, Loki, Pyroscope 등 오픈소스 표준과 완벽 호환.                               |
| **유연한 파이프라인**                  | 120개 이상의 컴포넌트를 조합해 데이터 수집 -> 변환 -> 전송 파이프라인 구성.                            |
| **엔터프라이즈 확장성**                | 클러스터링 지원으로 워크로드 분산과 수평 확장 가능, Fleet Management로 다중 배포 관리.                 |
| **GitOps 친화성**                      | Git, S3, HTTP 등에서 구성(Pipeline Config) 자동 가져오기 가능.                                         |
| **보안 및 비밀 관리**                  | HashiCorp Vault, Kubernetes Secrets 연동 지원, 인증 정보 안전 관리.                                    |

### 2.2. Grafana Alloy 주요 기능

| 기능                                              | 설명                                                                                                               |
| ------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| **사용자 정의 컴포넌트(Custom Components)**       | 여러 기존 컴포넌트를 하나의 컴포넌트로 묶어 간단히 재사용 가능. 커뮤니티 제공, Grafana 패키지 또는 직접 제작 가능. |
| **재사용 가능한 컴포넌트(Reusable Components)**   | 한 컴포넌트의 출력을 여러 다른 컴포넌트의 입력으로 활용 가능.                                                      |
| **컴포넌트 체이닝(Chained Components)**           | 컴포넌트를 순차적으로 연결해 파이프라인 구성 가능.                                                                 |
| **단일 작업 컴포넌트(Single Task per Component)** | 각 컴포넌트는 하나의 특정 작업에만 집중하도록 설계되어 가독성과 유지보수성 향상.                                   |
| **GitOps 호환성(GitOps Compatibility)**           | Git, S3, HTTP 등 다양한 소스에서 설정을 가져와 자동 반영 가능.                                                     |
| **클러스터링 지원(Clustering Support)**           | 클러스터링으로 워크로드를 분산하고 고가용성을 제공. 수평 확장 환경에 최적화.                                       |
| **보안 기능(Security)**                           | HashiCorp Vault, Kubernetes Secrets 연동을 통한 인증 정보와 비밀 안전 관리.                                        |
| **디버깅 및 UI 지원(Debugging Utilities)**        | 설정 문제 해결을 위한 내장 UI 및 진단 기능 제공.                                                                   |

---

### 2.3. Grafana Alloy 동작 방식 (OpenTelemetry Collector로서의 역할)

Grafana Alloy는 OpenTelemetry Collector 아키텍처를 기반으로 하며, **Collect -> Transform -> Write** 3단계로 동작합니다.

#### 2.3.1. Collect

- 120개 이상의 컴포넌트를 활용해 애플리케이션, 데이터베이스, OpenTelemetry Collector 등 다양한 소스에서 원격 측정 데이터 수집.
- **Pull 방식**(데이터를 Alloy가 가져옴)과 **Push 방식**(데이터를 Alloy에 전송) 모두 지원.
- Prometheus, OpenTelemetry, Loki, Pyroscope 등 다양한 데이터 생태계와 호환.

#### 2.3.2. Transform

- 수집된 데이터를 전송하기 전에 가공 및 필터링 가능.
- 예: 메타데이터 삽입, 불필요한 데이터 제거, 포맷 변환 등.
- 경량 필터링부터 복잡한 데이터 파이프라인까지 유연하게 구성 가능.

#### 2.3.3. Write

- 가공된 데이터를 OpenTelemetry 호환 데이터베이스, Grafana 스택, Grafana Cloud 등으로 전송.
- 알림 규칙을 지원하는 데이터베이스에 직접 쓰기 가능.
- 장기 보관, 분석, 경보 시스템과 손쉽게 연계.

---

> **Tip:** Grafana Alloy는 Promtail, Grafana Agent, OpenTelemetry Collector의 기능을 결합하면서도 엔터프라이즈 수준의 확장성과 관리성을 제공하므로, 단일 도구로 Observability 파이프라인을 단순화할 수 있습니다.


---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
