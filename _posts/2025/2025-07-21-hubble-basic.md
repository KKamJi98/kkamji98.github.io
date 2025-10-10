---
title: Cilium Hubble 알아보기 [Cilium Study 2주차]
date: 2025-07-21 01:43:55 +0900
author: kkamji
categories: [Kubernetes, Cilium]
tags: [kubernetes, devops, hubble, hubble-relay ,cilium, cilium-study, cloudnet]     # TAG names should always be lowercase
comments: true
image:
  path: /assets/img/kubernetes/cilium/cilium.webp
---

저번 시간에 **Cilium**의 구성요소에 대해 알아보았고, Cilium을 배포까지 해보았습니다. 이번시간에는 Cilium의 구성요소 중 **Observability**를 담당하는 Hubble에 대해 알아보고 배포해보도록 하겠습니다.

![Hubble Web UI](/assets/img/kubernetes/cilium/hubble-web-ui.webp)
> Hubble UI - <https://docs.cilium.io/en/latest/observability/hubble/hubble-ui/>

### 관련 글

1. [Vagrant와 VirtualBox로 Kubernetes Cluster 구축하기 [Cilium Study 1주차]]({% post_url 2025/2025-07-14-deploy-kubernetes-vagrant-virtualbox %})
2. [Flannel CNI 배포하기 [Cilium Study 1주차]]({% post_url 2025/2025-07-15-deploy-flannel-cni %})
3. [Cilium CNI 알아보기 [Cilium Study 1주차]]({% post_url 2025/2025-07-16-cilium-cni-basic %})
4. [Cilium 구성요소 & 배포하기 (kube-proxy replacement) [Cilium Study 1주차]]({% post_url 2025/2025-07-18-deploy-cilium %})
5. [Cilium Hubble 알아보기 [Cilium Study 2주차] (현재 글)]({% post_url 2025/2025-07-21-hubble-basic %})
6. [Cilium & Hubble Command Cheat Sheet [Cilium Study 2주차]]({% post_url cheat-sheet/2025-07-23-cilium-hubble-cheat-sheet %})
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
21. [Cilium Network Security [Cilium Study 8주차]]({% post_url 2025/2025-09-03-cilium-network-security %})

---

## 1. Hubble이란?

> - [Cilium Docs - Introduction to Cilium & Hubble](https://docs.cilium.io/en/stable/overview/intro/)

**Hubble**은 **완전 분산형 네트워킹·보안 가시성(Observability) 플랫폼**입니다. Cilium과 eBPF 위에 구축되어, **서비스 간 통신과 네트워크 인프라의 동작을 투명하고 깊이 관찰**할 수 있게 해 줍니다.

Cilium을 기반으로 동작하기 때문에 **eBPF의 강력한 가시성 기능을 그대로 활용**할 수 있습니다. eBPF는 프로그래머블하고 동적으로 구성이 가능해, **필요한 수준만큼 세밀한 정보를 수집하면서도 오버헤드는 최소화**합니다. Hubble은 이러한 eBPF의 장점을 극대화하도록 설계된 도구입니다.

기본적으로 **Hubble API**는 **Cilium 에이전트가 실행되는 개별 노드의 범위 내에서 작동**합니다. 이는 로컬 Cilium 에이전트가 관찰한 트래픽에 대한 네트워크 인사이트를 제한합니다. **Hubble CLI는 로컬 유닉스 도메인 소켓을 통해 제공되는 Hubble API를 쿼리하는 데 사용**할 수 있습니다. **Hubble CLI 바이너리는 기본적으로 Cilium 에이전트 포드에 설치**됩니다.

**Hubble Relay**를 배포하면 클러스터 메시 시나리오에서 **전체 클러스터 또는 여러 클러스터에 대한 네트워크 가시성이 제공**됩니다. 이 모드에서는 Hubble CLI를 Hubble Relay 서비스로 안내하거나 Hubble UI를 통해 Hubble 데이터에 액세스할 수 있습니다. Hubble UI는 웹 인터페이스로, **L3/L4 및 심지어 L7 계층에서 서비스 종속성 그래프를 자동으로 검색**할 수 있게 하여 사용자 친화적인 시각화 및 서비스 맵으로서의 데이터 흐름 필터링을 가능하게 합니다.

![Hubble Architecture](/assets/img/kubernetes/cilium/hubble-architecture.webp)
> Hubble Architecture - <https://github.com/cilium/hubble>

Hubble이 답할 수 있는 질문들은 다음과 같습니다.

### 1.1 서비스 종속성 & 통신 맵

- 어떤 서비스끼리 통신하며, 빈도는 얼마나 되는가?
- 서비스 간 의존 관계(그래프)는 어떻게 생겼는가?
- 어떤 HTTP 호출이 이루어지고 있는가?
- 특정 서비스가 소비·생산하는 Kafka 토픽은 무엇인가?

### 1.2 네트워크 모니터링 & 알림

- 통신이 실패한다면 그 원인은 무엇인가?
- DNS 문제인가? 애플리케이션 오류인가? 네트워크 자체 문제인가?
- L4(TCP) 층에서 끊겼는가, L7(HTTP) 층에서 끊겼는가?
- 최근 5분 동안 DNS 해석에 실패한 서비스는?
- 최근 TCP 연결이 끊기거나 타임아웃이 발생한 서비스는?
- 응답받지 못한 TCP SYN 요청 비율은 얼마인가?

### 1.3 애플리케이션 모니터링

- 특정 서비스(또는 전체 클러스터)의 4xx/5xx HTTP 응답 비율은?
- HTTP 요청–응답 지연의 95·99 퍼센타일은?
- 가장 성능이 나쁜 서비스는 어디인가?
- 두 서비스 간 지연 시간은 얼마인가?

### 1.4 보안 관측

- 네트워크 정책 때문에 차단된 서비스는 무엇인가?
- 클러스터 외부에서 접근된 서비스는 어디인가?
- 특정 DNS 이름을 조회한 서비스는?

> 이처럼 Hubble은 서비스 토폴로지부터 성능·보안 이슈까지, 쿠버네티스 클러스터 내부 네트워크의 현미경 역할을 수행합니다.  
{: .prompt-tip}

---

## 2. Hubble 배포 전 현재 환경 점검

```shell
## Cilium Status 확인
❯ cilium status
    /¯¯\
 /¯¯\__/¯¯\    Cilium:             OK
 \__/¯¯\__/    Operator:           OK
 /¯¯\__/¯¯\    Envoy DaemonSet:    OK
 \__/¯¯\__/    Hubble Relay:       disabled
    \__/       ClusterMesh:        disabled

DaemonSet              cilium                   Desired: 3, Ready: 3/3, Available: 3/3
DaemonSet              cilium-envoy             Desired: 3, Ready: 3/3, Available: 3/3
Deployment             cilium-operator          Desired: 1, Ready: 1/1, Available: 1/1
Containers:            cilium                   Running: 3
                       cilium-envoy             Running: 3
                       cilium-operator          Running: 1
                       clustermesh-apiserver
                       hubble-relay
Cluster Pods:          46/46 managed by Cilium
Helm chart version:    1.17.6
Image versions         cilium             quay.io/cilium/cilium:v1.17.6@sha256:544de3d4fed7acba72758413812780a4972d47c39035f2a06d6145d8644a3353: 3
                       cilium-envoy       quay.io/cilium/cilium-envoy:v1.33.4-1752151664-7c2edb0b44cf95f326d628b837fcdd845102ba68@sha256:318eff387835ca2717baab42a84f35a83a5f9e7d519253df87269f80b9ff0171: 3
                       cilium-operator    quay.io/cilium/operator-generic:v1.17.6@sha256:91ac3bf7be7bed30e90218f219d4f3062a63377689ee7246062fa0cc3839d096: 1

## Hubble 활성화 여부 확인
❯ cilium config view | grep -i hubble
enable-hubble                                     false

## Cilium 설정 확인
❯ kubectl get cm -n kube-system cilium-config -o json | jq
❯ cilium config view
...
cgroup-root                                       /run/cilium/cgroupv2
cilium-endpoint-gc-interval                       5m0s
cluster-id                                        0
cluster-name                                      default
cluster-pool-ipv4-cidr                            172.20.0.0/16
cluster-pool-ipv4-mask-size                       24
clustermesh-enable-endpoint-sync                  false
clustermesh-enable-mcs-api                        false
cni-exclusive                                     true
cni-log-file                                      /var/run/cilium/cilium-cni.log
custom-cni-conf                                   false
datapath-mode                                     veth
debug                                             true
...

## Hubble 배포 전 Cilium, Hubble 사용 포트 확인 (In Control Plane)
❯ ss -tnlp | grep -iE 'cilium|hubble' | tee before.txt
LISTEN 0      4096       127.0.0.1:41655      0.0.0.0:*    users:(("cilium-agent",pid=250860,fd=43))
LISTEN 0      4096       127.0.0.1:9234       0.0.0.0:*    users:(("cilium-operator",pid=250940,fd=9))
LISTEN 0      4096         0.0.0.0:9964       0.0.0.0:*    users:(("cilium-envoy",pid=251287,fd=25))
LISTEN 0      4096         0.0.0.0:9964       0.0.0.0:*    users:(("cilium-envoy",pid=251287,fd=24))
LISTEN 0      4096       127.0.0.1:9891       0.0.0.0:*    users:(("cilium-operator",pid=250940,fd=6))
LISTEN 0      4096       127.0.0.1:9890       0.0.0.0:*    users:(("cilium-agent",pid=250860,fd=6))
LISTEN 0      4096       127.0.0.1:9879       0.0.0.0:*    users:(("cilium-agent",pid=250860,fd=52))
LISTEN 0      4096       127.0.0.1:9878       0.0.0.0:*    users:(("cilium-envoy",pid=251287,fd=27))
LISTEN 0      4096       127.0.0.1:9878       0.0.0.0:*    users:(("cilium-envoy",pid=251287,fd=26))
LISTEN 0      4096               *:9963             *:*    users:(("cilium-operator",pid=250940,fd=7))


############################
## Cilium Debug 명령어 정리
############################

# Cilium 런타임 설정 확인
kubectl exec -n kube-system -c cilium-agent -it ds/cilium -- cilium-dbg config          # 모든 에이전트 설정 값 출력

# Cilium 클러스터 상태 상세 보기
kubectl exec -n kube-system -c cilium-agent -it ds/cilium -- cilium-dbg status --verbose # 헬스·버전·에러 등 상세 상태 확인

# Prometheus 메트릭 목록 확인
kubectl exec -n kube-system -c cilium-agent -it ds/cilium -- cilium-dbg metrics list     # 수집 가능한 메트릭 이름 나열

# 네임스페이스별 엔드포인트 현황
kubectl get ciliumendpoints -A                                                          # 모든 CiliumEndpoint 리소스 조회

# 실시간 패킷 이벤트 모니터
kubectl exec -n kube-system -c cilium-agent -it ds/cilium -- cilium-dbg monitor         # 기본 모니터(요약 뷰)
kubectl exec -n kube-system -c cilium-agent -it ds/cilium -- cilium-dbg monitor -v      # 상세 레이어,라벨 포함
kubectl exec -n kube-system -c cilium-agent -it ds/cilium -- cilium-dbg monitor -v -v   # 패킷 디섹션 정보까지 최대 상세

# 특정 엔드포인트(ID) 관련 이벤트만 필터링
kubectl exec -n kube-system -c cilium-agent -it ds/cilium -- cilium-dbg monitor --related-to=<id> # 해당 엔드포인트 관련 흐름만 표시

# 드롭된 패킷 알림만 보기
kubectl exec -n kube-system -c cilium-agent -it ds/cilium -- cilium-dbg monitor --type drop       # drop 이벤트만 출력

# 패킷 페이로드를 Hex로 출력(디섹션 생략)
kubectl exec -n kube-system -c cilium-agent -it ds/cilium -- cilium-dbg monitor -v -v --hex       # payload를 16진수로 표시

# L7 이벤트만 보기
kubectl exec -n kube-system -c cilium-agent -it ds/cilium -- cilium-dbg monitor -v --type l7      # HTTP/gRPC 등 L7 로그만 추적
```

---

## 3. Hubble 배포 (Helm)

기존 Cilium을 배포에 사용되었던 Value를 재사용하고, 아래와 같은 옵션들을 추가해 배포해보도록 하겠습니다. 각 옵션의 용도는 다음과 같습니다.

| 설정                                                                    | 설명                                                           |
| ----------------------------------------------------------------------- | -------------------------------------------------------------- |
| `--set hubble.enabled=true`                                             | Hubble 가시성 기능 전체 활성화                                 |
| `--set hubble.relay.enabled=true`                                       | Hubble Relay(gRPC 집계 서비스) 배포                            |
| `--set hubble.ui.enabled=true`                                          | Hubble UI(웹 대시보드) 배포                                    |
| `--set hubble.ui.service.type=NodePort`                                 | UI를 NodePort로 노출                                           |
| `--set hubble.ui.service.nodePort=31234`                                | UI NodePort 번호를 **31234**로 고정                            |
| `--set hubble.export.static.enabled=true`                               | 플로우 이벤트를 **파일로 내보내기** 기능 활성화                |
| `--set hubble.export.static.filePath=/var/run/cilium/hubble/events.log` | 내보낼 로그 파일 경로 지정                                     |
| `--set prometheus.enabled=true`                                         | Cilium 에이전트 측 메트릭 Service 노출                         |
| `--set operator.prometheus.enabled=true`                                | Cilium Operator 메트릭도 노출                                  |
| `--set hubble.metrics.enableOpenMetrics=true`                           | Hubble 메트릭을 **OpenMetrics**(Prometheus 호환) 포맷으로 노출 |

* 추가 설명 (길어서 분리)
`--set hubble.metrics.enabled="{dns,drop,tcp,flow,port-distribution,icmp,httpV2:exemplars=true;labelsContext=source_ip\\,source_namespace\\,source_workload\\,destination_ip\\,destination_namespace\\,destination_workload\\,traffic_direction}"`

- 활성화할 메트릭 종류 및 옵션 지정  
  - 메트릭 수집 - `dns`, `drop`, `tcp`, `flow`, `port-distribution`, `icmp`, `httpV2`  
  - Latency Exemplar 기록 활성화 - `httpV2:exemplars=true`  
  - 메트릭에 소스/목적지 IP·네임스페이스 등 라벨 포함 - `labelsContext=source_ip\\,source_namespace\\...`  

```shell
helm upgrade cilium cilium/cilium --namespace kube-system --reuse-values \
--set hubble.enabled=true \
--set hubble.relay.enabled=true \
--set hubble.ui.enabled=true \
--set hubble.ui.service.type=NodePort \
--set hubble.ui.service.nodePort=31234 \
--set hubble.export.static.enabled=true \
--set hubble.export.static.filePath=/var/run/cilium/hubble/events.log \
--set prometheus.enabled=true \
--set operator.prometheus.enabled=true \
--set hubble.metrics.enableOpenMetrics=true \
--set hubble.metrics.enabled="{dns,drop,tcp,flow,port-distribution,icmp,httpV2:exemplars=true;labelsContext=source_ip\,source_namespace\,source_workload\,destination_ip\,destination_namespace\,destination_workload\,traffic_direction}"
```

---

## 4. Hubble 배포 확인

### 4.1 Hubble 상태 확인

```shell
## Cilium Status 확인 (Hubble Relay: OK)
❯ cilium status
    /¯¯\
 /¯¯\__/¯¯\    Cilium:             OK
 \__/¯¯\__/    Operator:           OK
 /¯¯\__/¯¯\    Envoy DaemonSet:    OK
 \__/¯¯\__/    Hubble Relay:       OK
    \__/       ClusterMesh:        disabled

DaemonSet              cilium                   Desired: 3, Ready: 3/3, Available: 3/3
DaemonSet              cilium-envoy             Desired: 3, Ready: 3/3, Available: 3/3
Deployment             cilium-operator          Desired: 1, Ready: 1/1, Available: 1/1
Deployment             hubble-relay             Desired: 1, Ready: 1/1, Available: 1/1
Deployment             hubble-ui                Desired: 1, Ready: 1/1, Available: 1/1
Containers:            cilium                   Running: 3
                       cilium-envoy             Running: 3
                       cilium-operator          Running: 1
                       clustermesh-apiserver
                       hubble-relay             Running: 1
                       hubble-ui                Running: 1
Cluster Pods:          48/48 managed by Cilium
Helm chart version:    1.17.6
Image versions         cilium             quay.io/cilium/cilium:v1.17.6@sha256:544de3d4fed7acba72758413812780a4972d47c39035f2a06d6145d8644a3353: 3
                       cilium-envoy       quay.io/cilium/cilium-envoy:v1.33.4-1752151664-7c2edb0b44cf95f326d628b837fcdd845102ba68@sha256:318eff387835ca2717baab42a84f35a83a5f9e7d519253df87269f80b9ff0171: 3
                       cilium-operator    quay.io/cilium/operator-generic:v1.17.6@sha256:91ac3bf7be7bed30e90218f219d4f3062a63377689ee7246062fa0cc3839d096: 1
                       hubble-relay       quay.io/cilium/hubble-relay:v1.17.6@sha256:7d17ec10b3d37341c18ca56165b2f29a715cb8ee81311fd07088d8bf68c01e60: 1
                       hubble-ui          quay.io/cilium/hubble-ui-backend:v0.13.2@sha256:a034b7e98e6ea796ed26df8f4e71f83fc16465a19d166eff67a03b822c0bfa15: 1
                       hubble-ui          quay.io/cilium/hubble-ui:v0.13.2@sha256:9e37c1296b802830834cc87342a9182ccbb71ffebb711971e849221bd9d59392: 1

## Cilium 설정 확인 (두 명령어 동일)
❯ kubectl get cm -n kube-system cilium-config -o json | grep -i hubble
❯ cilium config view | grep -i hubble
enable-hubble                                     true
enable-hubble-open-metrics                        true
hubble-disable-tls                                false
hubble-export-allowlist
hubble-export-denylist
hubble-export-fieldmask
hubble-export-file-max-backups                    5
hubble-export-file-max-size-mb                    10
hubble-export-file-path                           /var/run/cilium/hubble/events.log
hubble-listen-address                             :4244
hubble-metrics                                    dns drop tcp flow port-distribution icmp httpV2:exemplars=true;labelsContext=source_ip,source_namespace,source_workload,destination_ip,destination_namespace,destination_workload,traffic_direction
hubble-metrics-server                             :9965
hubble-metrics-server-enable-tls                  false
hubble-socket-path                                /var/run/cilium/hubble.sock
hubble-tls-cert-file                              /var/lib/cilium/tls/hubble/server.crt
hubble-tls-client-ca-files                        /var/lib/cilium/tls/hubble/client-ca.crt
hubble-tls-key-file                               /var/lib/cilium/tls/hubble/server.key

## Hubble 관련 Secret 확인
❯ kubectl get secret -n kube-system | grep -iE 'cilium-ca|hubble'
cilium-ca                            Opaque               2      3m19s
hubble-ca-secret                     Opaque               2      78d
hubble-relay-client-certs            kubernetes.io/tls    3      3m19s
hubble-server-certs                  kubernetes.io/tls    3      3m19s

## Cilium, Hubble 사용 포트 확인 (In Control Plane)
root@k8s-m1:~# ss -tnlp | grep -iE 'cilium|hubble' | tee after.txt
LISTEN 0      4096       127.0.0.1:41655      0.0.0.0:*    users:(("cilium-agent",pid=252230,fd=52))
LISTEN 0      4096       127.0.0.1:9234       0.0.0.0:*    users:(("cilium-operator",pid=250940,fd=9))
LISTEN 0      4096         0.0.0.0:9964       0.0.0.0:*    users:(("cilium-envoy",pid=251287,fd=25))
LISTEN 0      4096         0.0.0.0:9964       0.0.0.0:*    users:(("cilium-envoy",pid=251287,fd=24))
LISTEN 0      4096       127.0.0.1:9891       0.0.0.0:*    users:(("cilium-operator",pid=250940,fd=6))
LISTEN 0      4096       127.0.0.1:9890       0.0.0.0:*    users:(("cilium-agent",pid=252230,fd=6))
LISTEN 0      4096       127.0.0.1:9879       0.0.0.0:*    users:(("cilium-agent",pid=252230,fd=60))
LISTEN 0      4096       127.0.0.1:9878       0.0.0.0:*    users:(("cilium-envoy",pid=251287,fd=27))
LISTEN 0      4096       127.0.0.1:9878       0.0.0.0:*    users:(("cilium-envoy",pid=251287,fd=26))
LISTEN 0      4096               *:4244             *:*    users:(("cilium-agent",pid=252230,fd=39))
LISTEN 0      4096               *:9965             *:*    users:(("cilium-agent",pid=252230,fd=32))
LISTEN 0      4096               *:9963             *:*    users:(("cilium-operator",pid=250940,fd=7))
LISTEN 0      4096               *:9962             *:*    users:(("cilium-agent",pid=252230,fd=7))


root@k8s-m1:~# vim -d before.txt after.txt
```

### 4.2 Hubble 배포 전 & 배포 후 포트 변경 확인

![Hubble Port Comparison](/assets/img/kubernetes/cilium/hubble_port_comparsion.webp)

> 새로 4244(Hubble gRPC), 9965(Hubble Metrics), 9962(Cilium Metrics)의 포트가 추가된 것 확인할 수 있습니다.  
> 특히 4244 포트는 각 노드의 cilium-agent가 Hubble gRPC 서비스를 외부에 열어주는 핵심 포트로, 클러스터 네트워크 이벤트를 gRPC 스트림으로 실시간 노출합니다.  
> hubble-relay 컴포넌트가 이 4244 포트를 통해 각 노드의 cilium-agent와 연결하고, 여러 노드의 이벤트를 집계하여 UI나 CLI 등 클러스터 전체 관점에서 조회가 가능하게 만들어줍니다.  
> 여기에 hubble-peer라는 ClusterIP 서비스가 있는데, 이 서비스가 각 노드의 4244 포트를 백엔드(Endpoints)로 묶어줍니다. Relay가 바로 이 peer 서비스를 통해 각 노드와 통신합니다.  
{: .prompt-tip}

```shell
## 각 노드에서 포트 확인
❯ for i in m1 w1 w2 ; do echo ">> node : k8s-$i <<"; ssh k8s-$i sudo ss -tnlp |grep 4244 ; echo; done                          

>> node : k8s-m1 <<
LISTEN 0      4096               *:4244             *:*    users:(("cilium-agent",pid=252230,fd=39))               

>> node : k8s-w1 <<
LISTEN 0      4096               *:4244             *:*    users:(("cilium-agent",pid=3251969,fd=34))  

>> node : k8s-w2 <<
LISTEN 0      4096               *:4244             *:*    users:(("cilium-agent",pid=2654424,fd=54))   

## hubble-peer 서비스/엔드포인트 확인
❯ kubectl get svc,ep -n kube-system hubble-peer
NAME                  TYPE        CLUSTER-IP    EXTERNAL-IP   PORT(S)   AGE
service/hubble-peer   ClusterIP   10.96.145.0   <none>        443/TCP   5h55m

NAME                    ENDPOINTS                                                     AGE
endpoints/hubble-peer   192.168.10.100:4244,192.168.10.101:4244,192.168.10.102:4244   5h55m

## hubble relay config 확인
❯ kubectl describe cm -n kube-system hubble-relay-config
...
cluster-name: default
peer-service: "hubble-peer.kube-system.svc.cluster.local.:443"
listen-address: :4245
...
```

### 4.3 Hubble 접속 확인

```shell
## 아까 서비스의 노드포트로 지정한 31234 포트 확인
❯ kubectl get svc | grep hubble-ui    
hubble-ui                                       NodePort    10.233.17.147   <none>        80:31234/TCP                   46h

## Node IP 확인 후 브라우저에서 <Node IP>:31234 로 접속 (Node IP -> 10.0.0.101로 접속)
❯ kubectl get no -o wide                                                                                                             
NAME     STATUS   ROLES           AGE    VERSION   INTERNAL-IP   EXTERNAL-IP   OS-IMAGE             KERNEL-VERSION     CONTAINER-RUNTIME
k8s-m1   Ready    control-plane   216d   v1.33.2   10.0.0.101    <none>        Ubuntu 24.04.1 LTS   6.8.0-63-generic   containerd://2.0.5
k8s-w1   Ready    <none>          216d   v1.33.2   10.0.0.201    <none>        Ubuntu 24.04.1 LTS   6.8.0-63-generic   containerd://2.0.5
k8s-w2   Ready    <none>          216d   v1.33.2   10.0.0.202    <none>        Ubuntu 24.04.1 LTS   6.8.0-63-generic   containerd://2.0.5
```

![Hubble UI](/assets/img/kubernetes/cilium/hubble_ui.webp)
![Hubble Web UI Network Flow Check](/assets/img/kubernetes/cilium/hubble_ui_network_flow_check.webp)

---

## 5. Hubble CLI 알아보기

이번에는 Hubble CLI를 설치하고 사용하는 방법을 알아보겠습니다. Hubble은 기본적으로 Hubble Relay의 gRPC API에 연결하여 네트워크 흐름을 조회합니다. 이를 위해 먼저 로컬 포트로 API 접근을 연결해 줘야 합니다.

### 5.1 Install Hubble CLI

```shell
# Hubble CLI Install <https://docs.cilium.io/en/stable/observability/hubble/setup/#install-the-hubble-client>
HUBBLE_VERSION=$(curl -s https://raw.githubusercontent.com/cilium/hubble/master/stable.txt)
HUBBLE_ARCH=amd64
if [ "$(uname -m)" = "aarch64" ]; then HUBBLE_ARCH=arm64; fi
curl -L --fail --remote-name-all https://github.com/cilium/hubble/releases/download/$HUBBLE_VERSION/hubble-linux-${HUBBLE_ARCH}.tar.gz{,.sha256sum}
sudo tar xzvfC hubble-linux-${HUBBLE_ARCH}.tar.gz /usr/local/bin
which hubble
hubble status
```

### 5.2 Hubble API 접근을 위한 Port-Forward 설정

hubble CLI는 기본적으로 로컬의 `localhost:4245`를 참조하지만, 보통 로컬과 클러스터는 따로 있는 경우가 많습니다. 해당 경우 직접 API 주소를 명시해서 외부에서 사용하거나 포트 포워딩을 한 뒤 사용해야합니다. 저는 `hubble config set port-forward true` 해당 명령어를 통해 hubble 명령어를 칠 때 자동으로 port-forward해서 사용하도록 하겠습니다.

```shell
## kubeconfig를 로컬 PC에 구성한 경우 (명령어에 Endpoint 명시)
hubble status --server <API-SERVER-ENDPOINT>:4245

## server 주소를 기본값으로 설정 (Endpoint 설정 유지)
hubble config set server <API-SERVER-ENDPOINT>:4245

## Hubble Relay를 로컬 4245 포트로 연결
cilium hubble port-forward &

## Hubble CLI를 날릴 때 단발성으로 잠깐 포트포워딩
hubble <command> -P

## Hubble CLI를 날릴 때 포트포워딩을 하는 설정을 유지 (-P 옵션 없이도 자동 포트포워딩)
hubble config set port-forward true

###################################
## Hubble CLI Test
###################################

## 클러스터는 외부에 있지만 기본으로 localhost인 127.0.0.1:4245 로 API를 요청 (실패)
❯ hubble status   
failed getting status: rpc error: code = Unavailable desc = connection error: desc = "transport: Error while dialing: dial tcp 127.0.0.1:4245: connect: connection refused"

## 포트포워딩 자동 설정
❯ hubble config set port-forward true

## 설정 확인
❯ hubble config view
...
kube-namespace: kube-system
kubeconfig: ""
port-forward: true
port-forward-port: "4245"
request-timeout: 12s
server: localhost:4245
...

## 명령어 다시 시도 (성공)
❯ hubble status                      
Healthcheck (via 127.0.0.1:4245): Ok
Current/Max Flows: 12,285/12,285 (100.00%)
Flows/s: 225.93
Connected Nodes: 3/3

# You can also query the flow API and look for flows
❯ k get ciliumendpoints.cilium.io -n kube-system
NAME                                        SECURITY IDENTITY   ENDPOINT STATE   IPV4            IPV6
coredns-675485d6df-vrnqg                    2793                ready            10.233.66.62
coredns-675485d6df-xkf24                    2793                ready            10.233.65.168
coredns-secondary-786c7b8cb9-jlmp5          47610               ready            10.233.64.145
coredns-secondary-786c7b8cb9-nr99w          47610               ready            10.233.66.75
dns-autoscaler-c54cbdb65-pbph5              40763               ready            10.233.66.77
dns-autoscaler-secondary-85746d6f77-v5rpv   37943               ready            10.233.66.226
external-dns-7c55468cb8-sljnj               9341                ready            10.233.64.154
hubble-relay-5dcd46f5c-4rf8n                61428               ready            10.233.65.13
hubble-ui-76d4965bb6-pgcv7                  817                 ready            10.233.65.37
metrics-server-77bd77b6cb-g4z2t             3009                ready            10.233.64.1

❯ hubble observe # Kubernetes Cluster 내에서 발생하고 있는 네트워크 흐름(flow) 이벤트 확인
Jul 24 13:42:21.107: 127.0.0.1:8080 (world) <> kube-system/coredns-675485d6df-xkf24 (ID:2793) pre-xlate-rev TRACED (TCP)
Jul 24 13:42:21.107: 127.0.0.1:8080 (world) <> kube-system/coredns-675485d6df-xkf24 (ID:2793) pre-xlate-rev TRACED (TCP)
Jul 24 13:42:21.107: 127.0.0.1:8080 (world) <> kube-system/coredns-675485d6df-xkf24 (ID:2793) pre-xlate-rev TRACED (TCP)
Jul 24 13:42:21.107: 127.0.0.1:8080 (world) <> kube-system/coredns-675485d6df-xkf24 (ID:2793) pre-xlate-rev TRACED (TCP)
Jul 24 13:42:21.107: 127.0.0.1:8080 (world) <> kube-system/coredns-675485d6df-xkf24 (ID:2793) pre-xlate-rev TRACED (TCP)
Jul 24 13:42:21.108: 127.0.0.1:60146 (world) <> kube-system/coredns-675485d6df-xkf24 (ID:2793) pre-xlate-rev TRACED (TCP)
Jul 24 13:42:21.108: 127.0.0.1:60146 (world) <> kube-system/coredns-675485d6df-xkf24 (ID:2793) pre-xlate-rev TRACED (TCP)
Jul 24 13:42:21.127: 127.0.0.1:35786 (world) <> kube-system/coredns-secondary-786c7b8cb9-jlmp5 (ID:47610) pre-xlate-rev TRACED (TCP)
Jul 24 13:42:21.127: 127.0.0.1:8080 (world) <> kube-system/coredns-secondary-786c7b8cb9-jlmp5 (ID:47610) pre-xlate-rev TRACED (TCP)
Jul 24 13:42:21.127: 127.0.0.1:8080 (world) <> kube-system/coredns-secondary-786c7b8cb9-jlmp5 (ID:47610) pre-xlate-rev TRACED (TCP)
Jul 24 13:42:21.127: 127.0.0.1:35786 (world) <> kube-system/coredns-secondary-786c7b8cb9-jlmp5 (ID:47610) pre-xlate-rev TRACED (TCP)
Jul 24 13:42:21.127: 127.0.0.1:35786 (world) <> kube-system/coredns-secondary-786c7b8cb9-jlmp5 (ID:47610) pre-xlate-rev TRACED (TCP)
Jul 24 13:42:21.127: 127.0.0.1:8080 (world) <> kube-system/coredns-secondary-786c7b8cb9-jlmp5 (ID:47610) pre-xlate-rev TRACED (TCP)
Jul 24 13:42:21.127: 127.0.0.1:8080 (world) <> kube-system/coredns-secondary-786c7b8cb9-jlmp5 (ID:47610) pre-xlate-rev TRACED (TCP)
Jul 24 13:42:21.127: 127.0.0.1:8080 (world) <> kube-system/coredns-secondary-786c7b8cb9-jlmp5 (ID:47610) pre-xlate-rev TRACED (TCP)
Jul 24 13:42:21.127: 127.0.0.1:35786 (world) <> kube-system/coredns-secondary-786c7b8cb9-jlmp5 (ID:47610) pre-xlate-rev TRACED (TCP)
Jul 24 13:42:21.162: 127.0.0.1:54966 (world) <> kube-system/hubble-relay-5dcd46f5c-4rf8n (ID:61428) pre-xlate-rev TRACED (TCP)
Jul 24 13:42:21.163: 127.0.0.1:54966 (world) <> kube-system/hubble-relay-5dcd46f5c-4rf8n (ID:61428) pre-xlate-rev TRACED (TCP)
Jul 24 13:42:21.163: 127.0.0.1:54966 (world) <> kube-system/hubble-relay-5dcd46f5c-4rf8n (ID:61428) pre-xlate-rev TRACED (TCP)
Jul 24 13:42:21.163: 127.0.0.1:54966 (world) <> kube-system/hubble-relay-5dcd46f5c-4rf8n (ID:61428) pre-xlate-rev TRACED (TCP)


❯ hubble observe -f                          # 클러스터 내에서 발생하는 모든 네트워크 흐름 이벤트를 실시간으로 스트리밍하여 화면에 출력
❯ hubble observe -f --pod {POD_NAME}         # 특정 Ppd에 대한 네트워크 흐름 이벤트 확인
❯ hubble observe -f --namespace my-namespace # 특정 Namespace에 대한 네트워크 흐름 이벤트 확인
```

---

## 6. Reference

- [Cilium Docs - Introduction to Cilium & Hubble](https://docs.cilium.io/en/stable/overview/intro/)
- [Cilium Docs - Network Observability with Hubble](https://docs.cilium.io/en/stable/observability/hubble/)
- [Cilium Docs - Service Map & Hubble UI](https://docs.cilium.io/en/latest/observability/hubble/hubble-ui/)
- [Cilium Docs - Setting up Hubble Observability](https://docs.cilium.io/en/stable/observability/hubble/setup/)
- [Cilium Github](https://github.com/cilium/hubble)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
