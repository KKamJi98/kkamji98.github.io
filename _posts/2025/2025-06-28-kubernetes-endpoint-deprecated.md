---
title: Kubernetes v1.33 Endpoints API Deprecated
date: 2025-06-28 01:01:29 +0900
author: kkamji
categories: [Kubernetes]
tags: [kubernetes, devops, endpoint, endpoint-slice, kubernetes-api]     # TAG names should always be lowercase
comments: true
image:
  path: /assets/img/kubernetes/endpoint_vs_endpointslice.webp
---

아래 Kubernetes v1.33의 CHANGELOG를 확인하다보면 아래와 같이 **Endpoints API(core/v1)**가 **Deprecated** 되고, 이를 대체할 수 있는 **EndpointSlice API(discovery.k8s.io/v1)**의 사용을 권장하고 있음을 확인하실 수 있습니다.  

[Kubernetes v1.33 Release Notes](https://kubernetes.io/blog/2025/04/23/kubernetes-v1-33-release/#deprecation-of-the-stable-endpoints-api)

```text
Deprecation of the stable Endpoints API
The EndpointSlices API has been stable since v1.21, which effectively replaced the original Endpoints API. While the original Endpoints API was simple and straightforward, it also posed some challenges when scaling to large numbers of network endpoints. The EndpointSlices API has introduced new features such as dual-stack networking, making the original Endpoints API ready for deprecation.

This deprecation affects only those who use the Endpoints API directly from workloads or scripts; these users should migrate to use EndpointSlices instead. There will be a dedicated blog post with more details on the deprecation implications and migration plans.

You can find more in KEP-4974: Deprecate v1.Endpoints.
```

따라서 이번 글에서는 **Endpoints API**를 사용하는 Application이나 Kubernetes Resource들을 확인하고 해당 리소스들을 **EndpointSlice API**로 전환하기 위해 도움이 될 내용들에 대해 다루도록 하겠습니다.

---

## 1. Kubernetes API란?

Kubernetes API는 클러스터의 모든 자원을 관리하고 조작할 수 있는 핵심적인 `RESTful` 인터페이스입니다. 특히 **API Server**는 Kubernetes Control Plane의 중심으로 다음과 같은 주요 기능을 담당합니다.

- **RESTful API 제공**: Kubernetes 리소스 생성, 조회, 수정, 삭제(CRUD)
- **인증(Authentication)**: 클러스터 접근 사용자 및 요청 인증
- **권한 부여(Authorization)**: RBAC 및 ABAC 기반 접근 권한 관리
- **승인(Admission)**: 리소스 요청 처리 전 승인 컨트롤러를 통한 검증 및 수정
- **상태 저장**: 클러스터의 상태 정보를 etcd에 저장하고 관리

Kubernetes API는 API 그룹으로 구성되어 있으며, 각 그룹은 독립적으로 버전 관리됩니다. **Core Group**에는 Pod, Service, Namespace 등 핵심 리소스가 포함되고, **Named Group**에는 apps, networking.k8s.io 등 특정 기능별로 그룹화된 리소스들이 있습니다.

---

## 2. Endpoints API란?

**Endpoints API**는 Service -> Pod IP 매핑 테이블을 저장하고 있는 객체 입니다.

- 각 Service가 가리키고 있는 Pod들의 IP가 하나의 JSON 필드 안에 나열 됨
- kube-proxy, CoreDNS 등이 이를 감시(watch)하여 노드 로컬의 `iptables`/`ipvs`/`eBPF` 규칙을 업데이트 함

| 한계                           | 영향                                                                           |
| ------------------------------ | ------------------------------------------------------------------------------ |
| Large‑scale scaling issue      | Endpoints 객체가 커질 경우 API Server, etcd, kube-proxy에 큰 부하 발생         |
| Full update overhead           | 단 하나의 Endpoint 변경에도 전체 객체가 전송되어 네트워크와 컴퓨팅 리소스 낭비 |
| Dual‑Stack, Topology 정보 부족 | IPv6, Multi-Zone 등 환경에서 정보 부족으로 정확한 라우팅 및 서비스 관리 어려움 |

---

## 3. EndpointSlice API란?

**EndpointSlice API**는 **Endpoints API**가 가진 확장성,기능적 한계를 근본적으로 해결하는 **Dual-Stack**, **Topology Information**과 EndpointSlice에서 변경된 내용이 존재하는 Slice만 kube-proxy에 **Patch**를 지원하도록 설계된 **Service Discovery API** 입니다. 기본적으로 서비스 엔드포인트를 `Slice(Shard)` 단위(기본 100개)로 나눠 관리함으로써 API Server 부하를 대폭 줄이고, 대규모, Multi-Zone, IPv4/IPv6 환경에서도 풍부한 메타데이터를 제공할 수 있습니다.

| 기능                      | 설명                                                                                                     |
| ------------------------- | -------------------------------------------------------------------------------------------------------- |
| Sharding                  | 기본 100개의 Endpoint를 슬라이스로 분할 -> 변경 Slice만 전송 -> API Server,kube‑proxy 부하 감소          |
| Rich Metadata             | addressType(`IPv4`/`IPv6`/`FQDN`), topology(`zone`,`node`) 필드로 Dual‑Stack, Topology‑aware 라우팅 지원 |
| incremental update(Patch) | Slice 단위 Patch 로 watch 트래픽 최소화, CoreDNS, kube‑proxy는 필요한 부분만 갱신                        |

> EndpointSlice는 Endpoints보다 더 효율적이고 상세한 정보를 제공하며, 특히 대규모 클러스터 환경에서 안정적인 서비스 로드밸런싱을 지원합니다.  
{: .prompt-tip}

---

## 4. Endpoints API vs EndpointSlice API 비교

Endpoints와 EndpointSlice의 차이를 이해하기 쉽도록 그림을 그려봤습니다. EndpointSlice에는 그림의 정보에 추가적으로 `Address Type`과 `Topology Information`이 추가됩니다.

![Endpoints VS EndpointSlice](/assets/img/kubernetes/endpoint_vs_endpointslice.webp)

---

## 5. Endpoints -> EndpointSlice Migration Checklist

- Legacy Controller : 구버전 Ingress Controller, Service Mesh 등에서 `Endpoints API`를 직접 호출하는 경우가 있는지 확인
- Custom Scripts: `kubectl get endpoints` 명령어의 결과나 `Endpoints API`를 직접 호출해 사용하는 Scripts가 있는지 확인
- Monitoring Tools: Prometheus와 Grafana 대시보드에서 사용하는 메트릭을 `kube_endpoint_*`에서 `kube_endpoint_slice_*`로 변경
- API permissions: ClusterRole 또는 Role에서 `endpoints` 권한을 사용하는 리소스를 점검하고 `endpointslices` 권한으로 업데이트

> 주요 오픈소스는 최신 릴리스에서 EndpointSlice 지원 추가할 가능성이 큽니다. 따라서 대부분의 경우 버전 업그레이드로 해결이 될 수 있습니다.  
{: .prompt-tip}

---

## 6. Reference

- Kubernetes v1.33: Octarine - <https://kubernetes.io/blog/2025/04/23/kubernetes-v1-33-release/>
- Kubernetes v1.33: Continuing the transition from Endpoints to EndpointSlices — <https://kubernetes.io/blog/2025/04/24/endpoints-deprecation/>

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
