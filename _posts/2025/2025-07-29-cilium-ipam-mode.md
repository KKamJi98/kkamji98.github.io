---
title: IPAM 개념 및 Kubernetes Host Scope -> Cluster Scope Migration 실습 [Cilium Study 3주차]
date: 2025-07-29 01:13:54 +0900
author: kkamji
categories: [Kubernetes, Cilium]
tags: [kubernetes, devops, cilium, cilium-study, ipam, cloudnet, gasida]
comments: true
image:
  path: /assets/img/kubernetes/cilium/cilium.webp
---

저번 시간까지 Cilium의 Hubble을 비롯한 운영/모니터링 기능을 살펴보았습니다. 이번 시간에는 Cilium의 IP Address Management(IPAM) 개념을 알아보고, Kubernetes Host Scope와 Cluster Scope 두 가지 IPAM 모드의 동작 차이를 실습을 통해 확인해보겠습니다.

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
11. [Cilium Log Monitoring with Grafana Loki & Grafana Alloy [Cilium Study 2주차]]({% post_url 2025/2025-07-28-hubble-log-monitoring-with-grafana-loki %})
12. [IPAM 개념 및 Kubernetes Host Scope -> Cluster Scope Migration 실습 [Cilium Study 3주차] (현재 글)]({% post_url 2025/2025-07-29-cilium-ipam-mode %})
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

## 1. IPAM이란?

**IPAM(IP Address Management)은 네트워크에서 IP 주소의 할당과 관리를 중앙에서 추적하고 제어하는 시스템**을 말합니다. 기업에서 DHCP 서버와 연동해 사내 IP 풀을 정의하고 각 기기에 IP를 자동 할당하거나, 클라우드 환경에서 가용 IP 블록을 분할해 자원을 추적하는 등의 사례가 IPAM에 해당합니다. 쉽게 말해, IP 주소를 어떤 규칙으로 누구에게 언제 할당했고 남은 주소는 무엇인지 등을 체계적으로 관리하는 도구입니다.

Kubernetes 환경에서도 Pod에게 IP를 부여하기 위해 IPAM을 사용합니다. 쿠버네티스 기본 CNI는 쿠버네티스 컨트롤 플레인이 각 노드에 Pod CIDR 대역을 미리 할당하고, kubelet이 자체적으로 해당 CIDR 내 IP를 Pod에 할당하는 방식으로 동작합니다. 반면 CNI 플러그인에 따라 자체 IPAM 기능을 통해 IP를 관리하기도 합니다 (예: Calico의 IP Pool, Cilium의 IPAM)

---

## 2. Cilium의 IPAM Mode

Cilium은 사용자의 요구를 충족하기 위해 다양한 IPAM 모드를 지원합니다. 해당 포스트에서 다루는 주제인 `Kubernetes Host Scope`, `Cluster Scope`, `Multi-Pool`을 제외하고, `CRD-backed`, `AWS ENI`, `Azure IPAM`, `GKE`과 같은 다양한 IPAM 모드가 존재하는데 상세한 내용은 아래 공식문서에서 확인하실 수 있습니다.

| Feature                    | Kubernetes Host Scope | Cluster Scope (default) | Multi-Pool (Beta) | CRD-backed | AWS ENI…       |
| :------------------------- | :-------------------- | :---------------------- | :---------------- | :--------- | :------------- |
| Tunnel routing             | ✅                     | ✅                       | ❌                 | ❌          | ❌              |
| Direct routing             | ✅                     | ✅                       | ✅                 | ✅          | ✅              |
| CIDR Configuration         | Kubernetes            | Cilium                  | Cilium            | External   | External (AWS) |
| Multiple CIDRs per cluster | ❌                     | ✅                       | ✅                 | N/A        | N/A            |
| Multiple CIDRs per node    | ❌                     | ❌                       | ✅                 | N/A        | N/A            |
| Dynamic CIDR/IP allocation | ❌                     | ❌                       | ✅                 | ✅          | ✅              |

> [Cilium Docs - IPAM](https://docs.cilium.io/en/stable/network/concepts/ipam/)

---

## 3. Kubernetes Host Scope Mode

Kubernetes Host Scope Mode에서는 쿠버네티스 컨트롤 플레인이 각 노드에 고유한 Pod CIDR 대역(예: 10.244.1.0/24)을 할당하고, Cilium 에이전트는 해당 노드의 CIDR 범위 내에서만 각 Pod에 IP를 부여합니다.Cilium은 쿠버네티스 노드 리소스의 `.spec.podCIDR` Field 또는 Annotation을 조회하여 노드별 사용 가능한 Pod IP 대역을 파악합니다. 노드 단위로 IP 공간이 분리되므로, 한 노드의 Pod IP를 다른 노드에 할당할 수 없어 IP 이용 효율이 낮을 수 있지만, 쿠버네티스 기본 방식이므로 설정이 간단하고 특별한 Operator 개입이 필요 없습니다.

해당 모드에서 노드 하나당 하나의 서브넷이 고정되며, 클러스터의 `Pod CIDR`(예: 10.244.0.0/16)을 노드 개수만큼 분할하여 사용합니다. 만약 특정 노드의 `Pod CIDR` 대역이 포드 증가로 고갈되면, 해당 노드에는 더 이상 Pod를 생성할 수 없고 (남은 다른 노드 CIDR의 유휴 IP 활용 불가), 이를 해소하려면 클러스터 전체 Pod CIDR 자체를 더 크게 잡거나 수동으로 조정해야 합니다.

> [Cilium Docs - Kubernetes-host scope IPAM Mode](https://docs.cilium.io/en/stable/network/concepts/ipam/cluster-pool/)  

> Cilium 공식문서에서는 클러스터의 IPAM 모드를 변경하는 것을 권장하지 않고, 새로운 IPAM 구성으로 새로운 Kubernetes Cluster를 설치하는 것을 추천하고 있습니다.  
> 라이브 환경에서 IPAM 모드를 변경하면 기존 워크로드의 지속적인 연결 중단이 발생할 수 있습니다.  
{: .prompt-danger}

![Kubernetes-host scope IPAM Mode](/assets/img/kubernetes/cilium/kubernetes_host_scope_ipam_mode.webp)

- Kubernetes 호스트 범위 IPAM 모드는 `ipam: Kubernetes`에서 활성화되며, 클러스터의 각 개별 노드가 가진 `PodCIDR`에서 Pod IP 할당
- Cilium 에이전트는 시작 시, 활성화된 IP Address Family마다 `v1.Node`에 `PodCIDR`이 제공될 때까지 대기
- PodCIDR은 아래 두 방법 중 하나로 v1.Node에 제공

### 3.1. `v1.Node` Resource Filed

| Field           | Description                    |
| --------------- | ------------------------------ |
| `spec.podCIDRs` | IPv4 및/또는 IPv6 PodCIDR 범위 |
| `spec.podCIDR`  | IPv4 또는 IPv6 PodCIDR 범위    |

> kube-controller-manager를 `--allocate-node-cidrs` 플래그와 함께 실행해야 Kubernetes가 노드별 PodCIDR 범위를 할당합니다.  
{: .prompt-tip}

### 3.2. `v1.Node` Annotation

| Annotation                           | Description                           |
| ------------------------------------ | ------------------------------------- |
| `network.cilium.io/ipv4-pod-cidr`    | IPv4 PodCIDR 범위                     |
| `network.cilium.io/ipv6-pod-cidr`    | IPv6 PodCIDR 범위                     |
| `network.cilium.io/ipv4-cilium-host` | cilium 호스트 인터페이스의 IPv4 주소  |
| `network.cilium.io/ipv6-cilium-host` | cilium 호스트 인터페이스의 IPv6 주소  |
| `network.cilium.io/ipv4-health-ip`   | cilium-health 엔드포인트의 IPv4 주소  |
| `network.cilium.io/ipv6-health-ip`   | cilium-health 엔드포인트의 IPv6 주소  |
| `network.cilium.io/ipv4-Ingress-ip`  | cilium-ingress 엔드포인트의 IPv4 주소 |
| `network.cilium.io/ipv6-Ingress-ip`  | cilium-ingress 엔드포인트의 IPv6 주소 |

---

## 4. Cluster Scope (Default)

Cluster Scope 모드는 Cilium 설치 시 기본 활성화되는 IPAM 방식으로, `Cilium Operator`가 클러스터 전체 `Pod IP Pool`을 중앙에서 관리합니다. 지정된 `Cluster CIDR`에서 노드별 서브넷을 동적으로 배정하고, 각 노드의 Cilium 에이전트가 자기 서브넷 안에서 Pod IP를 분배합니다. 이때 Kubernetes의 `v1.Node.spec.podCIDR`에 의존하지 않습니다.

Cluster Scope의 장점은 IP 주소 활용 효율이 높다는 것입니다. 예를 들어 여유 IP가 많은 노드의 CIDR을 축소하고 부족한 노드에 재할당하는 식으로 유휴 IP를 클러스터 전체에서 재분배할 수 있습니다.

> [Cilium Docs - Cluster Scope IPAM Mode](https://docs.cilium.io/en/stable/network/concepts/ipam/cluster-pool/)

![Cluster Scope IPAM Mode](/assets/img/kubernetes/cilium/cluster_scope_ipam_mode.webp)

- 클러스터 범위 IPAM 모드는 각 노드에 노드별 PodCIDR을 할당하고 각 노드에 호스트 범위 할당기를 사용하여 IP를 할당
- 차이점은 Kubernetes가 `Kubernetes v1.Node` 리소스를 통해 노드별 PodCIDR을 할당하는 대신, Cilium 운영자가 `v2.CiliumNode` 리소스(CRD)를 통해 노드별 PodCIDR을 관리
- 최소 마스크 길이는 `/30`, 권장 최소 마스크 길이는 `/29` 이상
- `10.0.0.0/8` is the default pod CIDR.  `clusterPoolIPv4PodCIDRList`

---

## 5. Multi-Pool (Beta)

Multi-Pool 모드는 `Cluster Scope`의 확장된 형태로, 여러 개의 `Pod CIDR` 풀을 정의하고 Namespace나 Pod의 속성에 따라 다른 IP Pool에서 IP를 할당하는 기능입니다. 예를 들어 `A` 네임스페이스의 Pod는 `10.0.0.0/16`풀에서, `B` 네임스페이스의 Pod는 `172.16.0.0/16` 풀에서 IP를 받도록 구성할 수 있습니다. Pod에 특정 Annotation(`ipam.cilium.io/ip-pool: <pool-name>`)이 있으면 그 Pool에서 IP를 할당하며, Pod에 Annotation이 없으면 Namespace의 기본 Pool, Namespace에도 없으면 전역 기본 Pool을 따르는 방식으로 동작합니다.

하지만 아직 **베타 단계**이므로 `VXLAN` 등의 Tunnel Mode나 `IPsec` 암호화 모드와 호환되지 않으며, 여러 Pool 간에 중복 IP 할당을 방지하기 위한 검증이 제한적이므로 실험적으로만 사용하는 것이 좋습니다.

- [Isovalent Blog - Overcoming Kubernetes IP Address Exhaustion with Cilium](https://isovalent.com/blog/post/overcoming-kubernetes-ip-address-exhaustion-with-cilium/)

> Multi-Pool - <https://docs.cilium.io/en/stable/network/concepts/ipam/multi-pool/>

![Multi-Pool](/assets/img/kubernetes/cilium/multi-pool.webp)

- 팀/환경/워크로드 특성별 IP 대역 분리 가능
- 네임스페이스 또는 Pod에 어노테이션으로 원하는 풀 지정
- 아직 베타 기능. 특정 터널 모드나 IPsec 등과의 제약 존재 가능
- 일반적으로 Cluster Scope 계열의 운영 모델 위에서 사용

---

## 6. Kubernetes Host Scope Mode -> Cluster Scope Migration 실습

앞서 개념적으로 살펴본 Kubernetes Host Scope와 Cluster Scope IPAM 모드의 차이를, 실습을 통해 확인해보도록 하겠습니다. 실습 환경은 두 개의 노드로 구성된 Kubernetes Cluster이며, 초기에는 쿠버네티스 Host Scope 모드(IPAM: kubernetes)로 Cilium이 설치되어 있습니다. (클러스터 생성 시 각 Node에 고유한 Pod CIDR이 할당된 상태) Cilium 및 Hubble은 이미 배포되어있습니다.

### 6.1. 실습 환경

![Kubernetes Cluster Environment Architecture](/assets/img/kubernetes/cilium/kubernetes-cluster-environment-arch.webp)

- 기본 배포 가상 머신 : k8s-ctr, k8s-w1, **router**
- **router** : 사내망 10.10.0.0/16 대역 통신과 연결, k8s 에 join 되지 않은 서버, loop1/loop2 dump 인터페이스 배치
- Cilium CNI 설치 상태로 배포 완료

### 6.2. Kubernetes Host Scope Mode에서 클러스터 상태 확인 (사전 작업)

#### 6.2.1. 현재 클러스터 정보 확인

```shell
# 클러스터 정보 확인
❯ kubectl cluster-info dump | grep -m 2 -E "cluster-cidr|service-cluster-ip-range"
                            "--service-cluster-ip-range=10.96.0.0/16",
                            "--cluster-cidr=10.244.0.0/16",

# ipam 모드 확인
❯ cilium config view | grep ^ipam
ipam                                              kubernetes

# 노드별 파드에 할당되는 IPAM(PodCIDR) 정보 확인
# --allocate-node-cidrs=true 로 설정된 kube-controller-manager에서 CIDR을 자동 할당
❯ kubectl get nodes -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.podCIDR}{"\n"}{end}'
k8s-ctr 10.244.0.0/24
k8s-w1  10.244.1.0/24

❯ k describe pod -n kube-system kube-controller-manager-k8s-ctr
...
    Command:
      kube-controller-manager
      --allocate-node-cidrs=true
      --cluster-cidr=10.244.0.0/16
      --service-cluster-ip-range=10.96.0.0/16
...

❯ kubectl get ciliumnode -o json | grep podCIDRs -A2
                    "podCIDRs": [
                        "10.244.0.0/24"
                    ],
--
                    "podCIDRs": [
                        "10.244.1.0/24"
                    ],
# 파드 정보 : 상태, 파드 IP 확인
❯ kubectl get ciliumendpoints.cilium.io -A
NAMESPACE            NAME                                      SECURITY IDENTITY   ENDPOINT STATE   IPV4           IPV6
cilium-monitoring    grafana-5c69859d9-fgfc8                   49020               ready            10.244.0.110
cilium-monitoring    prometheus-6fc896bc5d-4xmch               1975                ready            10.244.0.44
kube-system          coredns-674b8bbfcf-4xhdq                  39444               ready            10.244.0.66
kube-system          coredns-674b8bbfcf-gvp85                  39444               ready            10.244.0.240
kube-system          hubble-relay-5dcd46f5c-tx6hr              7333                ready            10.244.0.113
kube-system          hubble-ui-76d4965bb6-h5hp2                54546               ready            10.244.0.67
local-path-storage   local-path-provisioner-74f9666bc9-sf27m   50353               ready            10.244.0.98
```

#### 6.2.2. 샘플 애플리케이션 배포

```shell
# 샘플 애플리케이션 배포
cat << EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: webpod
spec:
  replicas: 2
  selector:
    matchLabels:
      app: webpod
  template:
    metadata:
      labels:
        app: webpod
    spec:
      affinity:
        podAntiAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
          - labelSelector:
              matchExpressions:
              - key: app
                operator: In
                values:
                - sample-app
            topologyKey: "kubernetes.io/hostname"
      containers:
      - name: webpod
        image: traefik/whoami
        ports:
        - containerPort: 80
---
apiVersion: v1
kind: Service
metadata:
  name: webpod
  labels:
    app: webpod
spec:
  selector:
    app: webpod
  ports:
  - protocol: TCP
    port: 80
    targetPort: 80
  type: ClusterIP
EOF


# k8s-ctr 노드에 curl-pod 파드 배포
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: curl-pod
  labels:
    app: curl
spec:
  nodeName: k8s-ctr
  containers:
  - name: curl
    image: nicolaka/netshoot
    command: ["tail"]
    args: ["-f", "/dev/null"]
  terminationGracePeriodSeconds: 0
EOF
```

#### 6.2.3. 샘플 애플리케이션 배포 후 통신 확인

```shell
###############################
# 배포 확인
###############################
# 리소스 정보 확인
❯ kubectl get deploy,svc,ep webpod -owide
Warning: v1 Endpoints is deprecated in v1.33+; use discovery.k8s.io/v1 EndpointSlice
NAME                     READY   UP-TO-DATE   AVAILABLE   AGE     CONTAINERS   IMAGES           SELECTOR
deployment.apps/webpod   2/2     2            2           2m16s   webpod       traefik/whoami   app=webpod

NAME             TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)   AGE     SELECTOR
service/webpod   ClusterIP   10.96.158.245   <none>        80/TCP    2m16s   app=webpod

NAME               ENDPOINTS                       AGE
endpoints/webpod   10.244.0.1:80,10.244.1.178:80   2m16s

# endpointslice 확인
❯ kubectl get endpointslices -l app=webpod
NAME           ADDRESSTYPE   PORTS   ENDPOINTS                 AGE
webpod-9tmxz   IPv4          80      10.244.0.1,10.244.1.178   2m41s

# IP 확인
❯ kubectl get ciliumendpoints 
NAME                      SECURITY IDENTITY   ENDPOINT STATE   IPV4           IPV6
curl-pod                  7908                ready            10.244.0.226
webpod-697b545f57-5zlzm   13437               ready            10.244.0.1
webpod-697b545f57-vj9tk   13437

# Agent Pod에 들어가서 Cilium이 관리하는 네트워크 엔드포인트 목록을 확인
❯ kubectl exec -it -n kube-system ds/cilium -c cilium-agent -- cilium-dbg endpoint list
...
...

###############################
# 통신 확인
###############################
❯ kubectl exec -it curl-pod -- curl webpod | grep Hostname
Hostname: webpod-697b545f57-5zlzm
...
```

#### 6.2.4. Flow Log 모니터링 (hubble, tcpdump, termshark)

```shell
# hubble relay 포트 포워딩 실행
❯ cilium hubble port-forward&
cilium hubble port-forward&
[1] 10879
ℹ️  Hubble Relay is available at 127.0.0.1:4245
❯ hubble status
Healthcheck (via localhost:4245): Ok
Current/Max Flows: 7,002/8,190 (85.49%)
Flows/s: 34.35
Connected Nodes: 2/2

# flow log 모니터링에 필요한 트래픽 발생 (1번)
❯ kubectl exec -it curl-pod -- curl webpod | grep Hostname

# flow log 모니터링에 필요한 트래픽을 지속적으로 발생 (다른 터미널에서 사용)
❯ kubectl exec -it curl-pod -- sh -c 'while true; do curl -s webpod | grep Hostname; sleep 1; done'
Hostname: webpod-697b545f57-5zlzm
Hostname: webpod-697b545f57-5zlzm
Hostname: webpod-697b545f57-5zlzm
Hostname: webpod-697b545f57-5zlzm
Hostname: webpod-697b545f57-vj9tk
Hostname: webpod-697b545f57-vj9tk
Hostname: webpod-697b545f57-5zlzm

# flow log 모니터링
❯ hubble observe -f --protocol tcp --to-pod curl-pod
Jul 29 02:48:06.807: default/curl-pod:55764 (ID:7908) <- default/webpod-697b545f57-vj9tk:80 (ID:13437) to-endpoint FORWARDED (TCP Flags: SYN, ACK)
Jul 29 02:48:06.812: default/curl-pod:55764 (ID:7908) <- default/webpod-697b545f57-vj9tk:80 (ID:13437) to-endpoint FORWARDED (TCP Flags: ACK, PSH)
Jul 29 02:48:06.813: default/curl-pod:55764 (ID:7908) <- default/webpod-697b545f57-vj9tk:80 (ID:13437) to-endpoint FORWARDED (TCP Flags: ACK, FIN)
Jul 29 02:48:07.072: default/curl-pod:55764 (ID:7908) <- default/webpod-697b545f57-vj9tk:80 (ID:13437) to-network FORWARDED (TCP Flags: SYN, ACK)
Jul 29 02:48:07.075: default/curl-pod:55764 (ID:7908) <- default/webpod-697b545f57-vj9tk:80 (ID:13437) to-network FORWARDED (TCP Flags: ACK, PSH)
Jul 29 02:48:07.077: default/curl-pod:55764 (ID:7908) <- default/webpod-697b545f57-vj9tk:80 (ID:13437) to-network FORWARDED (TCP Flags: ACK, FIN)

❯ hubble observe -f --protocol tcp --from-pod curl-pod
Jul 29 02:49:33.071: default/curl-pod (ID:7908) <> 10.96.158.245:80 (world) pre-xlate-fwd TRACED (TCP)
Jul 29 02:49:33.071: default/curl-pod (ID:7908) <> default/webpod-697b545f57-vj9tk:80 (ID:13437) post-xlate-fwd TRANSLATED (TCP)
Jul 29 02:49:33.071: default/curl-pod:53802 (ID:7908) -> default/webpod-697b545f57-vj9tk:80 (ID:13437) to-network FORWARDED (TCP Flags: SYN)
Jul 29 02:49:33.073: default/curl-pod:53802 (ID:7908) -> default/webpod-697b545f57-vj9tk:80 (ID:13437) to-network FORWARDED (TCP Flags: ACK)
Jul 29 02:49:33.074: default/curl-pod:53802 (ID:7908) -> default/webpod-697b545f57-vj9tk:80 (ID:13437) to-network FORWARDED (TCP Flags: ACK, PSH)
Jul 29 02:49:33.079: default/curl-pod:53802 (ID:7908) -> default/webpod-697b545f57-vj9tk:80 (ID:13437) to-network FORWARDED (TCP Flags: ACK, FIN)
Jul 29 02:49:33.082: default/curl-pod:53802 (ID:7908) -> default/webpod-697b545f57-vj9tk:80 (ID:13437) to-network FORWARDED (TCP Flags: ACK)
Jul 29 02:49:33.347: default/curl-pod:53802 (ID:7908) -> default/webpod-697b545f57-vj9tk:80 (ID:13437) to-endpoint FORWARDED (TCP Flags: SYN)
Jul 29 02:49:33.349: default/curl-pod:53802 (ID:7908) -> default/webpod-697b545f57-vj9tk:80 (ID:13437) to-endpoint FORWARDED (TCP Flags: ACK)
Jul 29 02:49:33.349: default/curl-pod:53802 (ID:7908) <> default/webpod-697b545f57-vj9tk (ID:13437) pre-xlate-rev TRACED (TCP)
Jul 29 02:49:33.349: default/curl-pod:53802 (ID:7908) <> default/webpod-697b545f57-vj9tk (ID:13437) pre-xlate-rev TRACED (TCP)
Jul 29 02:49:33.349: default/curl-pod:53802 (ID:7908) <> default/webpod-697b545f57-vj9tk (ID:13437) pre-xlate-rev TRACED (TCP)
Jul 29 02:49:33.350: default/curl-pod:53802 (ID:7908) -> default/webpod-697b545f57-vj9tk:80 (ID:13437) to-endpoint FORWARDED (TCP Flags: ACK, PSH)
Jul 29 02:49:33.351: default/curl-pod:53802 (ID:7908) <> default/webpod-697b545f57-vj9tk (ID:13437) pre-xlate-rev TRACED (TCP)
Jul 29 02:49:33.351: default/curl-pod:53802 (ID:7908) <> default/webpod-697b545f57-vj9tk (ID:13437) pre-xlate-rev TRACED (TCP)
Jul 29 02:49:33.354: default/curl-pod:53802 (ID:7908) -> default/webpod-697b545f57-vj9tk:80 (ID:13437) to-endpoint FORWARDED (TCP Flags: ACK, FIN)
Jul 29 02:49:33.357: default/curl-pod:53802 (ID:7908) -> default/webpod-697b545f57-vj9tk:80 (ID:13437) to-endpoint FORWARDED (TCP Flags: ACK)

❯ hubble observe -f --protocol tcp --pod curl-pod
Jul 29 02:50:03.340: default/curl-pod (ID:7908) <> 10.96.158.245:80 (world) pre-xlate-fwd TRACED (TCP)
Jul 29 02:50:03.340: default/curl-pod (ID:7908) <> default/webpod-697b545f57-vj9tk:80 (ID:13437) post-xlate-fwd TRANSLATED (TCP)
Jul 29 02:50:03.341: default/curl-pod:49856 (ID:7908) -> default/webpod-697b545f57-vj9tk:80 (ID:13437) to-network FORWARDED (TCP Flags: SYN)
Jul 29 02:50:03.342: default/curl-pod:49856 (ID:7908) <- default/webpod-697b545f57-vj9tk:80 (ID:13437) to-endpoint FORWARDED (TCP Flags: SYN, ACK)
Jul 29 02:50:03.343: default/curl-pod:49856 (ID:7908) -> default/webpod-697b545f57-vj9tk:80 (ID:13437) to-network FORWARDED (TCP Flags: ACK, PSH)
Jul 29 02:50:03.345: default/curl-pod:49856 (ID:7908) <- default/webpod-697b545f57-vj9tk:80 (ID:13437) to-endpoint FORWARDED (TCP Flags: ACK, PSH)
Jul 29 02:50:03.348: default/curl-pod:49856 (ID:7908) -> default/webpod-697b545f57-vj9tk:80 (ID:13437) to-network FORWARDED (TCP Flags: ACK, FIN)
Jul 29 02:50:03.350: default/curl-pod:49856 (ID:7908) <- default/webpod-697b545f57-vj9tk:80 (ID:13437) to-endpoint FORWARDED (TCP Flags: ACK, FIN)
Jul 29 02:50:03.351: default/curl-pod:49856 (ID:7908) -> default/webpod-697b545f57-vj9tk:80 (ID:13437) to-network FORWARDED (TCP Flags: ACK)
Jul 29 02:50:03.616: default/curl-pod:49856 (ID:7908) -> default/webpod-697b545f57-vj9tk:80 (ID:13437) to-endpoint FORWARDED (TCP Flags: SYN)
Jul 29 02:50:03.616: default/curl-pod:49856 (ID:7908) <- default/webpod-697b545f57-vj9tk:80 (ID:13437) to-network FORWARDED (TCP Flags: SYN, ACK)
Jul 29 02:50:03.618: default/curl-pod:49856 (ID:7908) -> default/webpod-697b545f57-vj9tk:80 (ID:13437) to-endpoint FORWARDED (TCP Flags: ACK)
Jul 29 02:50:03.618: default/curl-pod:49856 (ID:7908) -> default/webpod-697b545f57-vj9tk:80 (ID:13437) to-endpoint FORWARDED (TCP Flags: ACK, PSH)
Jul 29 02:50:03.619: default/curl-pod:49856 (ID:7908) <> default/webpod-697b545f57-vj9tk (ID:13437) pre-xlate-rev TRACED (TCP)
Jul 29 02:50:03.619: default/curl-pod:49856 (ID:7908) <> default/webpod-697b545f57-vj9tk (ID:13437) pre-xlate-rev TRACED (TCP)
Jul 29 02:50:03.619: default/curl-pod:49856 (ID:7908) <> default/webpod-697b545f57-vj9tk (ID:13437) pre-xlate-rev TRACED (TCP)
Jul 29 02:50:03.619: default/curl-pod:49856 (ID:7908) <> default/webpod-697b545f57-vj9tk (ID:13437) pre-xlate-rev TRACED (TCP)
Jul 29 02:50:03.620: default/curl-pod:49856 (ID:7908) <> default/webpod-697b545f57-vj9tk (ID:13437) pre-xlate-rev TRACED (TCP)
Jul 29 02:50:03.620: default/curl-pod:49856 (ID:7908) <- default/webpod-697b545f57-vj9tk:80 (ID:13437) to-network FORWARDED (TCP Flags: ACK, PSH)
Jul 29 02:50:03.623: default/curl-pod:49856 (ID:7908) -> default/webpod-697b545f57-vj9tk:80 (ID:13437) to-endpoint FORWARDED (TCP Flags: ACK, FIN)
Jul 29 02:50:03.624: default/curl-pod:49856 (ID:7908) <- default/webpod-697b545f57-vj9tk:80 (ID:13437) to-network FORWARDED (TCP Flags: ACK, FIN)
Jul 29 02:50:03.626: default/curl-pod:49856 (ID:7908) -> default/webpod-697b545f57-vj9tk:80 (ID:13437) to-endpoint FORWARDED (TCP Flags: ACK)
## pre-xlate-fwd , TRACED : NAT (IP 변환) 전 , 추적 중인 flow
## post-xlate-fwd , TRANSLATED : NAT 후의 흐름 , NAT 변환이 일어남


# tcpdump 사용해 확인 (Pod IP 확인)
❯ tcpdump -i eth1 tcp port 80 -nn
tcpdump: verbose output suppressed, use -v[v]... for full protocol decode
listening on eth1, link-type EN10MB (Ethernet), snapshot length 262144 bytes
02:54:33.987193 IP 10.244.0.226.50712 > 10.244.1.178.80: Flags [S], seq 3191136896, win 64240, options [mss 1460,sackOK,TS val 2307588823 ecr 0,nop,wscale 7], length 0
02:54:33.988501 IP 10.244.1.178.80 > 10.244.0.226.50712: Flags [S.], seq 1813004609, ack 3191136897, win 65160, options [mss 1460,sackOK,TS val 89254236 ecr 2307588823,nop,wscale 7], length 0
02:54:33.988957 IP 10.244.0.226.50712 > 10.244.1.178.80: Flags [.], ack 1, win 502, options [nop,nop,TS val 2307588825 ecr 89254236], length 0
02:54:33.989431 IP 10.244.0.226.50712 > 10.244.1.178.80: Flags [P.], seq 1:71, ack 1, win 502, options [nop,nop,TS val 2307588825 ecr 89254236], length 70: HTTP: GET / HTTP/1.1
02:54:33.990810 IP 10.244.1.178.80 > 10.244.0.226.50712: Flags [.], ack 71, win 509, options [nop,nop,TS val 89254239 ecr 2307588825], length 0
02:54:33.992767 IP 10.244.1.178.80 > 10.244.0.226.50712: Flags [P.], seq 1:323, ack 71, win 509, options [nop,nop,TS val 89254240 ecr 2307588825], length 322: HTTP: HTTP/1.1 200 OK
02:54:33.993080 IP 10.244.0.226.50712 > 10.244.1.178.80: Flags [.], ack 323, win 501, options [nop,nop,TS val 2307588829 ecr 89254240], length 0
02:54:33.994078 IP 10.244.0.226.50712 > 10.244.1.178.80: Flags [F.], seq 71, ack 323, win 501, options [nop,nop,TS val 2307588830 ecr 89254240], length 0
02:54:33.995483 IP 10.244.1.178.80 > 10.244.0.226.50712: Flags [F.], seq 323, ack 72, win 509, options [nop,nop,TS val 89254243 ecr 2307588830], length 0
02:54:33.996040 IP 10.244.0.226.50712 > 10.244.1.178.80: Flags [.], ack 324, win 501, options [nop,nop,TS val 2307588832 ecr 89254243], length 0

# 캡처된 패킷 데이터를 화면에 출력하는 대신 지정된 파일에 저장 (pcap 파일 생성)
❯ tcpdump -i eth1 tcp port 80 -w /tmp/http.pcap
tcpdump: listening on eth1, link-type EN10MB (Ethernet), snapshot length 262144 bytes
364 packets captured
364 packets received by filter

# termshark 설치
❯ export DEBIAN_FRONTEND=noninteractive
❯ apt-get install -y termshark

# termshark로 `/tmp/http.pcap` 확인 
❯ termshark -r /tmp/http.pcap
```
![Termshark HTTP GET Request 확인](/assets/img/kubernetes/cilium/termshark-http-get.webp)

### 6.3. Kubernetes Host Scope Mode -> Cluster Scope로 변경

```shell
# 반복 요청 해두기
❯ kubectl exec -it curl-pod -- sh -c 'while true; do curl -s webpod | grep Hostname; sleep 1; done'

# Cluster Scopre 로 설정 변경
❯ helm upgrade cilium cilium/cilium --version 1.17.6 --namespace kube-system --reuse-values \
  --set ipam.mode="cluster-pool" \
  --set ipam.operator.clusterPoolIPv4PodCIDRList={"172.20.0.0/16"} \
  --set ipv4NativeRoutingCIDR=172.20.0.0/16

# Operator 재시작 및 Cilium Agent Rollout Restart
❯ kubectl -n kube-system rollout restart deploy/cilium-operator # 오퍼레이터 재시작 필요
❯ kubectl -n kube-system rollout restart ds/cilium

# 설정 적용 확인
❯ cilium config view | grep ^ipam
ipam                                              cluster-pool

# PodCIDR 확인 (바뀌지 않음) -> 해당 Node는 kube-controller-manager에 의해 podCIDR가 이미 할당이 되어있기 때문
❯ kubectl get ciliumnode -o json | grep podCIDRs -A2
                    "podCIDRs": [
                        "10.244.0.0/24"
                    ],
--
                    "podCIDRs": [
                        "10.244.1.0/24"
                    ],

❯ kubectl get ciliumendpoints.cilium.io -A
NAMESPACE            NAME                                      SECURITY IDENTITY   ENDPOINT STATE   IPV4           IPV6
cilium-monitoring    grafana-5c69859d9-fgfc8                   49020               ready            10.244.0.110
cilium-monitoring    prometheus-6fc896bc5d-4xmch               1975                ready            10.244.0.44
default              curl-pod                                  7908                ready            10.244.0.226
default              webpod-697b545f57-5zlzm                   13437               ready            10.244.0.1
default              webpod-697b545f57-vj9tk                   13437               ready            10.244.1.178
kube-system          coredns-674b8bbfcf-4xhdq                  39444               ready            10.244.0.66
kube-system          coredns-674b8bbfcf-gvp85                  39444               ready            10.244.0.240
kube-system          hubble-relay-5dcd46f5c-tx6hr              7333                ready            10.244.0.113
kube-system          hubble-ui-76d4965bb6-h5hp2                54546               ready            10.244.0.67
local-path-storage   local-path-provisioner-74f9666bc9-sf27m   50353               ready            10.244.0.98
```

IPAM Mode를 `Cluster Scope`로 모드를 바꾸었음에도 불구하고 `CiliumNode`의 `podCIDR` 정보는 여전히 이전 값(`10.244.x.0/24`)으로 남아있습니다. 해당 이유는 처음 클러스터를 구성할 때 쿠버네티스가 각 노드에 PodCIDR을 할당했고 Cilium이 그 정보를 기반으로 초기화
했기 때문입니다.

Cilium IPAM 모드를 중간에 변경해도 기존의 CiliumNode 자원에 담긴 노드별 CIDR 상태와 이미 할당된 Pod IP 정보는 자동으로 갱신되지 않습니다. 따라서 새로운 CIDR 풀(172.20.0.0/16)을 사용하려면, 수동으로 각 노드의 Cilium IPAM 상태를 초기화하고 기존 Pod들을 모두 재배포하여 새 IP로 다시 받는 작업이 필요합니다.

```shell
# k8s-m1 노드 ciliumnode 리소스 삭제 후 daemonset rollout restart
❯ kubectl delete ciliumnode k8s-w1
❯ kubectl -n kube-system rollout restart ds/cilium

# 다시 확인
❯ kubectl get ciliumnode -o json | grep podCIDRs -A2
                    "podCIDRs": [
                        "10.244.0.0/24"
                    ],
--
                    "podCIDRs": [
                        "172.20.0.0/24" # 변경이 되어있음
                    ],

# k8s-ctr 노드 ciliumnode 리소스 삭제 후 daemonset rollout restart
❯ kubectl delete ciliumnode k8s-ctr
❯ kubectl -n kube-system rollout restart ds/cilium
❯ kubectl get ciliumnode -o json | grep podCIDRs -A2
                    "podCIDRs": [
                        "172.20.1.0/24"
                    ],
--
                    "podCIDRs": [
                        "172.20.0.0/24"
                    ],
❯ kubectl get ciliumendpoints.cilium.io -A # 파드 IP 변경 확인
NAMESPACE     NAME                       SECURITY IDENTITY   ENDPOINT STATE   IPV4           IPV6
kube-system   coredns-674b8bbfcf-5cbsj   39444               ready            172.20.1.206
kube-system   coredns-674b8bbfcf-czdzk   39444               ready            172.20.0.24

# 노드의 poccidr static routing 자동 변경 적용 확인
❯ ip -c route
default via 10.0.2.2 dev eth0 proto dhcp src 10.0.2.15 metric 100
10.0.2.0/24 dev eth0 proto kernel scope link src 10.0.2.15 metric 100
10.0.2.2 dev eth0 proto dhcp scope link src 10.0.2.15 metric 100
10.0.2.3 dev eth0 proto dhcp scope link src 10.0.2.15 metric 100
10.10.0.0/16 via 192.168.10.200 dev eth1 proto static
172.20.0.0/24 via 192.168.10.101 dev eth1 proto kernel   # Changed
172.20.1.206 dev lxc26067ff7c52e proto kernel scope link # Changed
192.168.10.0/24 dev eth1 proto kernel scope link src 192.168.10.100

# 기존에 생성된 Pod들의 상태 확인 (이전 IP를 가지고 있고 상태에 문제가 있음)
❯ kubectl get pod -A -owide | grep 10.244.
cilium-monitoring    grafana-5c69859d9-fgfc8                   0/1     Running            0             118m    10.244.0.110     k8s-ctr   <none>           <none>
cilium-monitoring    prometheus-6fc896bc5d-4xmch               1/1     Running            0             118m    10.244.0.44      k8s-ctr   <none>           <none>
default              curl-pod                                  1/1     Running            0             100m    10.244.0.226     k8s-ctr   <none>           <none>
default              webpod-697b545f57-5zlzm                   1/1     Running            0             100m    10.244.0.1       k8s-ctr   <none>           <none>
default              webpod-697b545f57-vj9tk                   1/1     Running            0             100m    10.244.1.178     k8s-w1    <none>           <none>
kube-system          hubble-relay-5dcd46f5c-tx6hr              0/1     Running            3 (37s ago)   118m    10.244.0.113     k8s-ctr   <none>           <none>
kube-system          hubble-ui-76d4965bb6-h5hp2                1/2     CrashLoopBackOff   5 (81s ago)   118m    10.244.0.67      k8s-ctr   <none>           <none>
local-path-storage   local-path-provisioner-74f9666bc9-sf27m   1/1     Running            0             118m    10.244.0.98      k8s-ctr   <none>           <none>

# 직접 rollout restart 시켜 Pod IP 재할상
❯ kubectl -n kube-system rollout restart deploy/hubble-relay deploy/hubble-ui
❯ kubectl -n cilium-monitoring rollout restart deploy/prometheus deploy/grafana
❯ kubectl rollout restart deploy/webpod
❯ kubectl delete pod curl-pod

# 통신 확인을 위해 hubble port-forward
❯ cilium hubble port-forward&
❯ ss -tnlp | grep 4245
(⎈|HomeLab:N/A) root@k8s-ctr:~# ss -tnlp | grep 4245
LISTEN 0      4096        127.0.0.1:4245       0.0.0.0:*    users:(("cilium",pid=10879,fd=7))
LISTEN 0      4096            [::1]:4245          [::]:*    users:(("cilium",pid=10879,fd=8))

# k8s-ctr 노드에 curl-pod 파드 재배포
❯ cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: curl-pod
  labels:
    app: curl
spec:
  nodeName: k8s-ctr
  containers:
  - name: curl
    image: nicolaka/netshoot
    command: ["tail"]
    args: ["-f", "/dev/null"]
  terminationGracePeriodSeconds: 0
EOF

# 파드 IP 변경 확인
❯ kubectl get ciliumendpoints.cilium.io -A
NAMESPACE           NAME                            SECURITY IDENTITY   ENDPOINT STATE   IPV4           IPV6
cilium-monitoring   grafana-56ff55d977-rhx44        49020               ready            172.20.0.230
cilium-monitoring   prometheus-865c848f6b-hgxj9     1975                ready            172.20.0.26
default             curl-pod                        7908                ready            172.20.1.40
default             webpod-5d558dbbb-fv5cp          13437               ready            172.20.1.119
default             webpod-5d558dbbb-svndg          13437               ready            172.20.0.248
kube-system         coredns-674b8bbfcf-5cbsj        39444               ready            172.20.1.206
kube-system         coredns-674b8bbfcf-czdzk        39444               ready            172.20.0.24
kube-system         hubble-relay-67bcff9864-4vk69   7333                ready            172.20.0.4
kube-system         hubble-ui-6d89597799-rnlrs      54546               ready            172.20.0.34

# 통신 확인 (정상)
❯ kubectl exec -it curl-pod -- sh -c 'while true; do curl -s webpod | grep Hostname; sleep 1; done'
Hostname: webpod-5d558dbbb-fv5cp
Hostname: webpod-5d558dbbb-svndg
Hostname: webpod-5d558dbbb-fv5cp
Hostname: webpod-5d558dbbb-fv5cp
```

---

## 7. 마무리

실습 결과와 같이 이미 Pod들이 동작 중인 클러스터에서 IPAM 모드를 변경하는 것은 안전하지 않으므로 피해야 합니다. Cilium 공식 문서에서도 "IPAM 모드를 바꾸고 싶다면 새로운 IPAM 설정으로 클러스터를 새로 구성하는 것이 가장 안전한 경로"라고 명시하고 있습니다. 실제로 Cluster Scope 모드를 쓰려면 초기 Cilium 설치 시부터 clusterpool로 설정하여 Pod들이 처음부터 그 대역으로 IP를 받도록 해야 합니다.

---

## 8. Reference

- [Cilium Docs - IPAM](https://docs.cilium.io/en/stable/network/concepts/ipam/)
- [Cilium Docs - Kubernetes-host scope IPAM Mode](https://docs.cilium.io/en/stable/network/concepts/ipam/cluster-pool/)  
- [Cilium Docs - Cluster Scope IPAM Mode](https://docs.cilium.io/en/stable/network/concepts/ipam/cluster-pool/)
- [Cilium Docs - Multi-Pool](https://docs.cilium.io/en/stable/network/concepts/ipam/multi-pool/)
- [Isovalent Blog - Overcoming Kubernetes IP Address Exhaustion with Cilium](https://isovalent.com/blog/post/overcoming-kubernetes-ip-address-exhaustion-with-cilium/)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
