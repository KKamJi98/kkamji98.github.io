---
title: Cilium Network Security [Cilium Study 8주차]
date: 2025-09-03 23:30:22 +0900
author: kkamji
categories: [Kubernetes]
tags: [kubernetes, devops, cilium, cilium-study, cilium-security]
comments: true
image:
  path: /assets/img/kubernetes/kubernetes.webp
---

Cilium은 **Identity-Based(Layer3)**, **Port Level(Layer4)**, **Application protocol Level(Layer7)** 보안을 제공합니다.

### 관련 글

1. [Vagrant와 VirtualBox로 Kubernetes Cluster 구축하기 [Cilium Study 1주차]]({% post_url 2025/2025-07-14-deploy-kubernetes-vagrant-virtualbox %})
2. [Flannel CNI 배포하기 [Cilium Study 1주차]]({% post_url 2025/2025-07-15-deploy-flannel-cni %})
3. [Cilium CNI 알아보기 [Cilium Study 1주차]]({% post_url 2025/2025-07-16-cilium-cni-basic %})
4. [Cilium 구성요소 & 배포하기 (kube-proxy replacement) [Cilium Study 1주차]]({% post_url 2025/2025-07-18-deploy-cilium %})
5. [Cilium Hubble 알아보기 [Cilium Study 2주차]]({% post_url 2025/2025-07-21-hubble-basic %})
6. [Cilium & Hubble Command Cheat Sheet [Cilium Study 2주차]]({% post_url cheat-sheet/2025-07-23-cilium-hubble-commands %})
7. [Star Wars Demo와 함께 Cilium Network Policy 알아보기 [Cilium Study 2주차]]({% post_url 2025/2025-07-24-hubble-demo %})
8. [Hubble Exporter와 Dynamic Exporter Configuration [Cilium Study 2주차]]({% post_url 2025/2025-07-25-hubble-exporter %})
9. [Monitoring VS Observability + SLI/SLO/SLA 알아보기 [Cilium Study 2주차]]({% post_url 2025/2025-07-26-monitoring-observability-sli-slo-sla %})
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
21. [Cilium Network Security [Cilium Study 8주차](현재 글)]({% post_url 2025/2025-09-03-cilium-network-security %})

## Cilium Network Policy

모든 보안 정책은 세션 기반 프로토콜에 대해 상태 저장 방식으로 적용됩니다. 즉, 정책에서 "A가 B에게 연결할 수 있다" 라고 정의되어 있으면 `A -> B` 로 세션이 시작되는 것은 허용되며, `B -> A`로 돌아오는 응답 패킷도 자동으로 허용됩니다(Stateful). 하지만 위 정책은 B가 독자적으로 A에게 연결을 시작할 수 있음을 의미하지 않으므로, `B -> A` 방향의 트래픽을 허용해야 합니다. 결국 일방적인 관계가 아닌 서로 상호작용하는 관계인 경우 `A -> B`, `B -> A` 서로 통신을 원활하게 양쪽 방향을 모두 정책으로 명시해야 합니다.

### Default Security Policy

- 정책이 로드되지 않은 경우, 정책 적용이 명시적으로 활성화되지 않은 한 모든 통신을 허용하는 것이 기본 동작입니다.
- 첫 번째 정책 규칙이 로드되는 즉시 정책 적용이 자동으로 활성화되며, 모든 통신은 허용 목록에 추가되어야 하며, 그렇지 않으면 관련 패킷이 삭제됩니다.
- 마찬가지로, 엔드포인트에 *L4* 정책이 적용되지 않으면 모든 포트와의 통신이 허용됩니다.
- 엔드포인트에 하나 이상의 *L4 정책을 연결하면 명시적으로 허용하지 않는 한 포트에 대한 모든 연결이 차단됩니다.*

## Cilium Identity

![Cilium Network Security](/assets/img/kubernetes/cilium/8w-cilium-identity-management.webp)

Cilium은 IP 대신 **레이블에서 파생된 Identity**로 통신 주체를 식별하고 규칙을 적용합니다. 동일한 보안 관련 레이블 집합을 가진 파드들은 동일한 `Identity`를 공유하며, 해당 Identity는 클러스터 전역에 유효합니다.

- 엔드포인트의 ID는 [엔드포인트](https://docs.cilium.io/en/stable/gettingstarted/terminology/#endpoint) 에서 파생된 포드 또는 컨테이너와 연관된 [레이블](https://docs.cilium.io/en/stable/gettingstarted/terminology/#labels)을 기반으로 결정됩니다.
- **파드 또는 컨테이너가 시작**되면 Cilium은 **컨테이너 런타임**에서 수신한 **이벤트**를 기반으로 네트워크에서 포드 또는 컨테이너를 나타내는 [엔드포인트](https://docs.cilium.io/en/stable/gettingstarted/terminology/#endpoint) 를 생성합니다.
- 다음 단계로 Cilium은 생성된 [엔드포인트](https://docs.cilium.io/en/stable/gettingstarted/terminology/#endpoint) 의 ID를 확인합니다. 포드 또는 컨테이너의 [레이블](https://docs.cilium.io/en/stable/gettingstarted/terminology/#labels)이 변경될 때마다 ID가 재확인되고 필요에 따라 자동으로 수정됩니다.

보안 적용 계층

- **L3 -> Identity 기반** 접근 제어  
- **L4 Layer** -> Port/Protocol 기반 접근 제어  
- **L7 Layer** -> Application Protocol(HTTP Method/Header/URL Path/...) 기반 접근 제어

### Cilium Identity 확인

```shell
##########################################################
# Cilium Endpoint & Identity 확인
##########################################################

## 특정 네임스페이스 Pod에 할당된
kubectl get ciliumendpoints.cilium.io -n kube-system
# NAME                              SECURITY IDENTITY   ENDPOINT STATE   IPV4           IPV6
# coredns-674b8bbfcf-79cm9          8281                ready            172.20.0.33
# coredns-674b8bbfcf-jb2f9          8281                ready            172.20.0.242
# hubble-relay-fdd49b976-mf9w4      58732               ready            172.20.0.43
# hubble-ui-655f947f96-h5m52        1156                ready            172.20.0.83
# metrics-server-5dd7b49d79-r6s7w   60013               ready            172.20.0.217

## 네임스페이스별 Identity 확인
kubectl get ciliumidentities.cilium.io 
# NAME    NAMESPACE            AGE
# 1156    kube-system          4h9m
# 16327   cilium-monitoring    4h9m
# 3712    cilium-monitoring    4h9m
# 41479   local-path-storage   4h9m
# 58732   kube-system          4h9m
# 60013   kube-system          4h9m
# 8281    kube-system          4h9m

##########################################################
# CoreDNS Cilium Identity 상세 확인
##########################################################
kubectl get ciliumidentities.cilium.io 8281 -o yaml | yq
# apiVersion: cilium.io/v2
# kind: CiliumIdentity
# metadata:
#   creationTimestamp: "2025-09-06T08:37:45Z"
#   generation: 1
#   labels:
#     io.kubernetes.pod.namespace: kube-system
#   name: "8281"
#   resourceVersion: "801"
#   uid: c3aa01ea-c5dc-4da2-aec5-c6254bae091d
# security-labels:
#   k8s:io.cilium.k8s.namespace.labels.kubernetes.io/metadata.name: kube-system
#   k8s:io.cilium.k8s.policy.cluster: default
#   k8s:io.cilium.k8s.policy.serviceaccount: coredns
#   k8s:io.kubernetes.pod.namespace: kube-system
#   k8s:k8s-app: kube-dns

kubectl exec -it -n kube-system ds/cilium -- cilium identity list | grep 8281 -A 5
# 8281    k8s:io.cilium.k8s.namespace.labels.kubernetes.io/metadata.name=kube-system
#         k8s:io.cilium.k8s.policy.cluster=default
#         k8s:io.cilium.k8s.policy.serviceaccount=coredns
#         k8s:io.kubernetes.pod.namespace=kube-system
#         k8s:k8s-app=kube-dns
# 16327   k8s:app=grafana

kubectl get pod -n kube-system -l k8s-app=kube-dns --show-labels
# NAME                       READY   STATUS    RESTARTS      AGE     LABELS
# coredns-674b8bbfcf-79cm9   1/1     Running   0             4h13m   k8s-app=kube-dns,pod-template-hash=674b8bbfcf
# coredns-674b8bbfcf-jb2f9   1/1     Running   0             4h13m   k8s-app=kube-dns,pod-template-hash=674b8bbfcf

##########################################################
# CoreDNS Pod에 Label 추가 후 Identity 변경 테스트
##########################################################

## 기존 Identity
kubectl exec -it -n kube-system ds/cilium -- cilium identity list | grep "k8s:k8s-app=kube-dns" -B4
# 8281    k8s:io.cilium.k8s.namespace.labels.kubernetes.io/metadata.name=kube-system
#         k8s:io.cilium.k8s.policy.cluster=default
#         k8s:io.cilium.k8s.policy.serviceaccount=coredns
#         k8s:io.kubernetes.pod.namespace=kube-system
#         k8s:k8s-app=kube-dns

## Label 추가 
kubectl label pods -n kube-system -l k8s-app=kube-dns study=8w

## Identity 확인 (기존 Identity는 유지된 상태로 새로운 레이블이 추가 됨)
kubectl exec -it -n kube-system ds/cilium -- cilium identity list | rg "k8s:k8s-app=kube-dns" -B5
# 3805    k8s:io.cilium.k8s.namespace.labels.kubernetes.io/metadata.name=kube-system
#         k8s:io.cilium.k8s.policy.cluster=default
#         k8s:io.cilium.k8s.policy.serviceaccount=coredns
#         k8s:io.kubernetes.pod.namespace=kube-system
#         k8s:k8s-app=kube-dns
#         k8s:study=8w
# 8281    k8s:io.cilium.k8s.namespace.labels.kubernetes.io/metadata.name=kube-system
#         k8s:io.cilium.k8s.policy.cluster=default
#         k8s:io.cilium.k8s.policy.serviceaccount=coredns
#         k8s:io.kubernetes.pod.namespace=kube-system
#         k8s:k8s-app=kube-dns

## 시간이 지난 뒤 재확인 (기존 Identity가 사라짐)
kubectl exec -it -n kube-system ds/cilium -- cilium identity list | grep "k8s:k8s-app=kube-dns" -B5
# 3805    k8s:io.cilium.k8s.namespace.labels.kubernetes.io/metadata.name=kube-system
#         k8s:io.cilium.k8s.policy.cluster=default
#         k8s:io.cilium.k8s.policy.serviceaccount=coredns
#         k8s:io.kubernetes.pod.namespace=kube-system
#         k8s:k8s-app=kube-dns
#         k8s:study=8w
```

### Cilium Identity 변경 테스트

- Cilium은 pod update 이벤트를 watch하므로, labels 변경 시 endpoint가 waiting-for-identity 상태로 전환되어 새로운 identity를 할당받습니다.
- 이로 인해 security labels와 관련된 네트워크 정책도 자동으로 재적용됩니다.
- 예시: 간단한 pod(simple-pod)를 생성하면 초기 security identity(예: 26830)가 할당됩니다.
- 이후 `kubectl label pod/simple-pod run=not-simple-pod --overwrite`로 labels를 변경하면, `kubectl get ciliumendpoints` 명령에서 identity가 새 값(예: 8710)으로 업데이트된 것을 확인할 수 있습니다. 이는 policy enforcement에 즉시 반영됩니다.
- 다만, 대규모 클러스터에서 자주 labels를 변경하면 identity 할당이 빈번해져 성능 저하가 발생할 수 있으므로, identity-relevant labels를 제한하는 것이 권장됩니다

## Special Identity

Cilium에서 관리하는 모든 엔드포인트에는 Identity가 할당됩니다. 또한, Cilium에서 관리하지 않는 네트워크 엔드포인트와의 통신을 허용하기 위해 이러한 엔드포인트를 나타내는 특수 Identity가 존재하며, `reserved` 문자열 접두사가 붙습니다.

| **Identity** | **Numeric ID** | **Description** |
| --- | --- | --- |
| `reserved:unknown` | 0 | The identity could not be derived. |
| `reserved:host` | 1 | The local host. Any traffic that originates from or is designated to one of the local host IPs. |
| `reserved:world` | 2 | Any network endpoint outside of the cluster |
| `reserved:unmanaged` | 3 | An endpoint that is not managed by Cilium, e.g. a Kubernetes pod that was launched before Cilium was installed. |
| `reserved:health` | 4 | This is health checking traffic generated by Cilium agents. |
| `reserved:init` | 5 | An endpoint for which the identity has not yet been resolved is assigned the init identity. This represents the phase of an endpoint in which some of the metadata required to derive the security identity is still missing. This is typically the case in the bootstrapping phase.
The init identity is only allocated if the labels of the endpoint are not known at creation time. This can be the case for the Docker plugin. |
| `reserved:remote-node` | 6 | The collection of all remote cluster hosts. Any traffic that originates from or is designated to one of the IPs of any host in any connected cluster other than the local node. |
| `reserved:kube-apiserver` | 7 | Remote node(s) which have backend(s) serving the kube-apiserver running. |
| `reserved:ingress` | 8 | Given to the IPs used as the source address for connections from Ingress proxies. |

### Sepcial Identity 확인

```shell
kubectl exec -it -n kube-system ds/cilium -- cilium identity list |  head -n 13
# ID      LABELS
# 1       reserved:host
# 2       reserved:world
# 3       reserved:unmanaged
# 4       reserved:health
# 5       reserved:init
# 6       reserved:remote-node
# 7       reserved:kube-apiserver
#         reserved:remote-node
# 8       reserved:ingress
# 9       reserved:world-ipv4
# 10      reserved:world-ipv6
# 1156    k8s:app.kubernetes.io/name=hubble-ui
```

## Reference

- [Cilium Docs - Overview of Network Security(Introduction)](https://docs.cilium.io/en/stable/security/network/intro/)
- [Cilium Docs - Overview of Network Security(Identity-Based)](https://docs.cilium.io/en/stable/security/network/identity/)
- [Cilium Docs - Overview of Network Security(Policy Enforcement)](https://docs.cilium.io/en/stable/security/network/policyenforcement/)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
