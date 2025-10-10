---
title: Cilium 구성요소 & 배포하기 (kube-proxy replacement) [Cilium Study 1주차]
date: 2025-07-18 21:23:05 +0900
author: kkamji
categories: [Kubernetes, Cilium]
tags: [kubernetes, devops, cilium, cilium-study, cloudnet]     # TAG names should always be lowercase
comments: true
image:
  path: /assets/img/kubernetes/cilium/cilium.webp
---

저번 시간에 **Cilium**에 대해 알아보았습니다. 이번에는 **Cilium**의 구성요소에 대해 알아본 뒤, Helm을 통해 **Cilium**을 배포하면서 kube-proxy를 대체해 사용해보도록 하겠습니다.

### 관련 글

1. [Vagrant와 VirtualBox로 Kubernetes Cluster 구축하기 [Cilium Study 1주차]]({% post_url 2025/2025-07-14-deploy-kubernetes-vagrant-virtualbox %})
2. [Flannel CNI 배포하기 [Cilium Study 1주차]]({% post_url 2025/2025-07-15-deploy-flannel-cni %})
3. [Cilium CNI 알아보기 [Cilium Study 1주차]]({% post_url 2025/2025-07-16-cilium-cni-basic %})
4. [Cilium 구성요소 & 배포하기 (kube-proxy replacement) [Cilium Study 1주차] (현재 글)]({% post_url 2025/2025-07-18-deploy-cilium %})
5. [Cilium Hubble 알아보기 [Cilium Study 2주차]]({% post_url 2025/2025-07-21-hubble-basic %})
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

## 1. Cilium 구성 요소

> - [Cilium Docs - Component Overview](https://docs.cilium.io/en/stable/overview/component-overview/)

![Cilium Overview](/assets/img/kubernetes/cilium/cilium-overview.webp)
> Cilium Overview - <https://docs.cilium.io/en/stable/overview/component-overview/>

Cilium은 크게 `Cilium Operator`, `Cilium Agent`, `Cilium Client`, `Hubble`, `DataStore` 로 나뉘며 각 구성 요소들은 다음과 같이 동작합니다.

### 1.1. Cilium Operator

클러스터 전역에 하나 또는 고가용성을 위해 2~3대 정도로 배포되는 구성요소로, 노드별 에이전트가 아닌 클러스터 전체적인 작업을 담당합니다. 예를 들어 Pod IP 할당(IPAM), 노드 간 라우팅 정보 관리, kvstore(ETCD 등)와의 연동을 처리합니다

### 1.2. Cilium Agent

데몬셋으로 실행되어 각 노드에서 Kubernetes와 상호작용합니다. NetworkPolicy, Service 등의 리소스를 감지하고 이를 기반으로 eBPF 프로그램 및 맵을 구성하여 Pod 사이의 모든 트래픽을 제어합니다. 예를 들어 새로운 Pod가 생성되면 에이전트는 해당 Pod 네트워크 네임스페이스에 eBPF hook을 설정하고 필요한 경로 설정, 정책맵 초기화를 수행합니다.

### 1.3. Cilium Client (CLI)

Cilium은 관리용 CLI 도구(cilium CLI)를 제공하여 설치, 상태 점검, 문제 해결 등을 지원합니다. 또한 각 노드 에이전트와 통신하는 디버그 CLI(cilium-dbg)를 통해 로컬 eBPF 맵 상태 등을 점검할 수 있습니다.

### 1.4. Hubble (Option)

Hubble은 Cilium에 통합된 네트워크 가시성/모니터링 모듈로서, 각 노드의 Cilium 에이전트에 내장된 Hubble 서버를 통해 eBPF로 수집된 플로우 데이터를 gRPC API로 제공합니다. 추가로 Hubble Relay를 배포하면 각 노드의 Hubble 서버와 연결되어 클러스터 전체의 플로우를 집계하며, 여기에 CLI나 Hubble UI 웹 인터페이스를 연결해 실시간 서비스 맵과 흐름 추적을 시각화할 수 있습니다.

### 1.5. Data Store

Cilium Agent 간의 상태를 저장하고 전파하기 위해 사용되는 데이터 저장소입니다. Cilium은 에이전트 간 보안 ID·라우팅·정책 메타데이터를 전파하기 위해 다음과 같이 두 가지 방식을 지원합니다.

- **Kubernetes CRD** (`default`):별도 인프라 없이 쿠버네티스 API 서버(etcd)에 바로 저장합니다. 설치가 가장 간단하며, 일반적인 규모의 클러스터(수천 노드 미만)에서는 이 방법만으로 충분합니다.
- **Key‑Value Store** (`etcd`): 대규모-멀티클러스터 환경에서 성능 최적화를 위해 사용할 수 있습니다. CRD와 병행해 하이브리드 모드로도 운영 가능하며, 실서비스에서는 3 Node 이상 HA 구성을 권장합니다.

---

## 2. System Requirements 확인

> - [Cilium Docs - System Requirements](https://docs.cilium.io/en/stable/operations/system_requirements/)

Cilium을 배포하기 전, 현재 시스템이 Cilium의 최소 요구사항을 충족하는지 확인해보도록 하겠습니다. Cilium의 최소 요구사항은 다음과 같습니다.

- Hosts with either AMD64 or AArch64 architecture
- Linux kernel >= 5.4 or equivalent (e.g., 4.18 on RHEL 8.6)

### 2.1. CPU Architecture, Kerner Version & Options 확인

```bash
###############################################
## 1. Architecture Check
###############################################
❯ arch
x86_64 #AMD64

###############################################
## 2. Kernel Version Check
###############################################
❯ uname -r
6.8.0-53-generic # >= 5.4

###############################################
## 3. Kernel Configuration Options Check (check-cilium-kernel-cfg.sh)
###############################################
---
#!/usr/bin/env bash
# ==== Cilium Kernel Config Checker ====
#
# Script to check kernel configuration for Cilium.
#
# Status Legend:
#   [OK]   builtin: Kernel built-in
#   [OK]   module loaded: Module is loaded
#   [WARN] module not loaded: Module is not loaded (needs modprobe)
#   [FAIL] absent: Not included in kernel (requires kernel recompile or HWE kernel)

CFG="/boot/config-$(uname -r)"
[[ -f $CFG ]] || { echo "Kernel config file ($CFG) not found"; exit 1; }

# ==== Map kernel config options to module names ====
declare -A MODMAP=(
  # ==== eBPF ====
  [CONFIG_NET_CLS_BPF]=cls_bpf
  [CONFIG_NET_SCH_INGRESS]=sch_ingress
  [CONFIG_CRYPTO_USER_API_HASH]=algif_hash

  # ==== Iptables-based Masquerading ====
  [CONFIG_NETFILTER_XT_SET]=xt_set
  [CONFIG_IP_SET]=ip_set
  [CONFIG_IP_SET_HASH_IP]=ip_set_hash_ip
  [CONFIG_NETFILTER_XT_MATCH_COMMENT]=xt_comment
  [CONFIG_NETFILTER_XT_TARGET_TPROXY]=xt_TPROXY
  [CONFIG_NETFILTER_XT_TARGET_MARK]=xt_mark
  [CONFIG_NETFILTER_XT_TARGET_CT]=xt_CT
  [CONFIG_NETFILTER_XT_MATCH_MARK]=xt_mark
  [CONFIG_NETFILTER_XT_MATCH_SOCKET]=xt_socket

  # ==== Bandwidth Manager ====
  [CONFIG_NET_SCH_FQ]=sch_fq

  # ==== Netkit Device Mode ====
  [CONFIG_NETKIT]=netkit

  # ==== IPsec ====
  [CONFIG_XFRM_ALGO]=xfrm_algo
  [CONFIG_XFRM_USER]=xfrm_user
  [CONFIG_INET_ESP]=esp4
  [CONFIG_INET6_ESP]=esp6
  [CONFIG_INET_IPCOMP]=ipcomp
  [CONFIG_INET6_IPCOMP]=ipcomp6
  [CONFIG_INET_XFRM_TUNNEL]=xfrm4_tunnel
  [CONFIG_INET6_XFRM_TUNNEL]=xfrm6_tunnel
  [CONFIG_INET_TUNNEL]=tunnel4
  [CONFIG_INET6_TUNNEL]=tunnel6
)

# ==== Required Kernel Options ====
OPTS=(
  # ==== eBPF ====
  CONFIG_BPF CONFIG_BPF_SYSCALL CONFIG_NET_CLS_BPF CONFIG_BPF_JIT
  CONFIG_NET_CLS_ACT CONFIG_NET_SCH_INGRESS CONFIG_CRYPTO_SHA1
  CONFIG_CRYPTO_USER_API_HASH CONFIG_CGROUPS CONFIG_CGROUP_BPF
  CONFIG_PERF_EVENTS CONFIG_SCHEDSTATS

  # ==== Iptables-based Masquerading ====
  CONFIG_NETFILTER_XT_SET CONFIG_IP_SET CONFIG_IP_SET_HASH_IP
  CONFIG_NETFILTER_XT_MATCH_COMMENT

  # ==== Tunneling and Routing ====
  CONFIG_VXLAN CONFIG_GENEVE CONFIG_FIB_RULES

  # ==== L7 and FQDN Policies ====
  CONFIG_NETFILTER_XT_TARGET_TPROXY CONFIG_NETFILTER_XT_TARGET_MARK
  CONFIG_NETFILTER_XT_TARGET_CT CONFIG_NETFILTER_XT_MATCH_MARK
  CONFIG_NETFILTER_XT_MATCH_SOCKET

  # ==== IPsec ====
  CONFIG_XFRM CONFIG_XFRM_OFFLOAD CONFIG_XFRM_STATISTICS
  CONFIG_XFRM_ALGO CONFIG_XFRM_USER CONFIG_INET_ESP CONFIG_INET6_ESP
  CONFIG_INET_IPCOMP CONFIG_INET6_IPCOMP CONFIG_INET_XFRM_TUNNEL
  CONFIG_INET6_XFRM_TUNNEL CONFIG_INET_TUNNEL CONFIG_INET6_TUNNEL
  CONFIG_INET_XFRM_MODE_TUNNEL CONFIG_CRYPTO_AEAD CONFIG_CRYPTO_AEAD2
  CONFIG_CRYPTO_GCM CONFIG_CRYPTO_SEQIV CONFIG_CRYPTO_CBC
  CONFIG_CRYPTO_HMAC CONFIG_CRYPTO_SHA256 CONFIG_CRYPTO_AES

  # ==== Bandwidth Manager ====
  CONFIG_NET_SCH_FQ

  # ==== Netkit Device Mode ====
  CONFIG_NETKIT
)

# ==== Check Kernel Config ====
echo "Checking Cilium kernel options for kernel $(uname -r)"
for opt in "${OPTS[@]}"; do
  mod=${MODMAP[$opt]:-${opt#CONFIG_}}
  if grep -q "^$opt=y" "$CFG"; then
    printf "  [OK]   %-35s builtin\n" "$opt"
  elif grep -q "^$opt=m" "$CFG"; then
    if lsmod | grep -qw "$mod"; then
      printf "  [OK]   %-35s module loaded\n" "$opt"
    else
      printf "  [WARN] %-35s module not loaded\n" "$opt"
    fi
  else
    printf "  [FAIL] %-35s absent\n" "$opt"
  fi
done

---
❯ bash check-cilium-kernel-cfg.sh
Cilium 요구 커널 옵션 점검 (kernel 6.8.0-53-generic)
  [OK]  CONFIG_BPF (builtin)
  [OK]  CONFIG_BPF_SYSCALL (builtin)
  [OK]  CONFIG_NET_CLS_BPF (module loaded)
  [OK]  CONFIG_BPF_JIT (builtin)
  [OK]  CONFIG_NET_CLS_ACT (builtin)
  [OK]  CONFIG_NET_SCH_INGRESS (module loaded)
  [OK]  CONFIG_CRYPTO_SHA1 (builtin)
  [OK]  CONFIG_CRYPTO_USER_API_HASH (module loaded)
  [OK]  CONFIG_CGROUPS (builtin)
  [OK]  CONFIG_CGROUP_BPF (builtin)
  [OK]  CONFIG_PERF_EVENTS (builtin)
  [OK]  CONFIG_SCHEDSTATS (builtin)
  ...
  ...

```

### 2.2. Kernel Versions for Advanced Features

| Cilium Feature                               | Minimum Kernel Version |
| :------------------------------------------- | :--------------------- |
| WireGuard Transparent Encryption             | `>= 5.6`               |
| Full support for Session Affinity            | `>= 5.7`               |
| BPF-based proxy redirection                  | `>= 5.7`               |
| Socket-level LB bypass in pod netns          | `>= 5.7`               |
| L3 devices                                   | `>= 5.8`               |
| BPF-based host routing                       | `>= 5.10`              |
| Multicast Support in Cilium (Beta) (AMD64)   | `>= 5.10`              |
| IPv6 BIG TCP support                         | `>= 5.19`              |
| Multicast Support in Cilium (Beta) (AArch64) | `>= 6.0`               |
| IPv4 BIG TCP support                         | `>= 6.3`               |

---

## 3. Cilium 배포하기 (Without kube-proxy)

- [Cilium Docs - Kubernetes Without kube-proxy](https://docs.cilium.io/en/stable/network/kubernetes/kubeproxy-free/)

```bash
# Node Status 확인 (현재 CNI 미 설치 상태 => NotRunning)
NAMESPACE     NAME                                READY   STATUS    RESTARTS   AGE   IP               NODE        NOMINATED NODE   READINESS GATES                                                                                                                                      kube-system   coredns-674b8bbfcf-7g6qk            0/1     Pending   0          15m   <none>           <none>      <none>           <none>
kube-system   coredns-674b8bbfcf-t46dz            0/1     Pending   0          15m   <none>           <none>      <none>           <none>
kube-system   etcd-cilium-m1                      1/1     Running   0          15m   192.168.10.100   cilium-m1   <none>           <none>
kube-system   kube-apiserver-cilium-m1            1/1     Running   0          15m   192.168.10.100   cilium-m1   <none>           <none>
kube-system   kube-controller-manager-cilium-m1   1/1     Running   0          15m   192.168.10.100   cilium-m1   <none>           <none>
kube-system   kube-proxy-clkg2                    1/1     Running   0          13m   192.168.10.101   cilium-w1   <none>           <none>
kube-system   kube-proxy-njvtk                    1/1     Running   0          15m   192.168.10.100   cilium-m1   <none>           <none>
kube-system   kube-proxy-szkxb                    1/1     Running   0          11m   192.168.10.102   cilium-w2   <none>           <none>
kube-system   kube-scheduler-cilium-m1            1/1     Running   0          15m   192.168.10.100   cilium-m1   <none>           <none>

# Pod Status 확인
❯ k get po -o wide -A
NAMESPACE     NAME                                READY   STATUS    RESTARTS   AGE   IP               NODE        NOMINATED NODE   READINESS GATES
kube-system   coredns-674b8bbfcf-7g6qk            0/1     Pending   0          16m   <none>           <none>      <none>           <none>
kube-system   coredns-674b8bbfcf-t46dz            0/1     Pending   0          16m   <none>           <none>      <none>           <none>
kube-system   etcd-cilium-m1                      1/1     Running   0          16m   192.168.10.100   cilium-m1   <none>           <none>
kube-system   kube-apiserver-cilium-m1            1/1     Running   0          16m   192.168.10.100   cilium-m1   <none>           <none>
kube-system   kube-controller-manager-cilium-m1   1/1     Running   0          16m   192.168.10.100   cilium-m1   <none>           <none>
kube-system   kube-proxy-clkg2                    1/1     Running   0          14m   192.168.10.101   cilium-w1   <none>           <none>
kube-system   kube-proxy-njvtk                    1/1     Running   0          16m   192.168.10.100   cilium-m1   <none>           <none>
kube-system   kube-proxy-szkxb                    1/1     Running   0          12m   192.168.10.102   cilium-w2   <none>           <none>
kube-system   kube-scheduler-cilium-m1            1/1     Running   0          16m   192.168.10.100   cilium-m1   <none>           <none>

# 기존 kube-proxy 제거
❯ kubectl -n kube-system delete ds kube-proxy
❯ kubectl -n kube-system delete cm kube-proxy

# Cilium 설치 with Helm
❯ helm repo add cilium https://helm.cilium.io/

# 모든 NIC 지정 + bpf.masquerade=true + NoIptablesRules
❯ helm install cilium cilium/cilium --version 1.17.5 --namespace kube-system \
--set k8sServiceHost=192.168.10.100 --set k8sServicePort=6443 \
--set kubeProxyReplacement=true \
--set routingMode=native \
--set autoDirectNodeRoutes=true \
--set ipam.mode="cluster-pool" \
--set ipam.operator.clusterPoolIPv4PodCIDRList={"172.20.0.0/16"} \
--set ipv4NativeRoutingCIDR=172.20.0.0/16 \
--set endpointRoutes.enabled=true \
--set installNoConntrackIptablesRules=true \
--set bpf.masquerade=true \
--set ipv6.enabled=false

# Value 및 배포 확인
❯ helm get values cilium -n kube-system
USER-SUPPLIED VALUES:
autoDirectNodeRoutes: true
bpf:
  masquerade: true
endpointRoutes:
  enabled: true
installNoConntrackIptablesRules: true
ipam:
  mode: cluster-pool
  operator:
    clusterPoolIPv4PodCIDRList:
    - 172.20.0.0/16
ipv4NativeRoutingCIDR: 172.20.0.0/16
ipv6:
  enabled: false
k8sServiceHost: 192.168.10.100
k8sServicePort: 6443
kubeProxyReplacement: true
routingMode: native

❯ helm list -A
NAME    NAMESPACE       REVISION        UPDATED                                 STATUS  CHART            APP VERSION
cilium  kube-system     1               2025-07-20 05:59:47.929229605 +0900 KST deployedcilium-1.17.5    1.17.5

❯ kubectl get crd
NAME                                         CREATED AT
ciliumcidrgroups.cilium.io                   2025-07-19T21:01:35Z
ciliumclusterwidenetworkpolicies.cilium.io   2025-07-19T21:01:35Z
ciliumendpoints.cilium.io                    2025-07-19T21:01:35Z
ciliumexternalworkloads.cilium.io            2025-07-19T21:01:35Z
ciliumidentities.cilium.io                   2025-07-19T21:01:35Z
ciliuml2announcementpolicies.cilium.io       2025-07-19T21:01:35Z
ciliumloadbalancerippools.cilium.io          2025-07-19T21:01:35Z
ciliumnetworkpolicies.cilium.io              2025-07-19T21:01:35Z
ciliumnodeconfigs.cilium.io                  2025-07-19T21:01:35Z
ciliumnodes.cilium.io                        2025-07-19T21:01:35Z
ciliumpodippools.cilium.io                   2025-07-19T21:01:35Z

❯ watch -d kubectl get pod -A
NAMESPACE     NAME                                READY   STATUS    RESTARTS   AGE
kube-system   cilium-5xkzn                        1/1     Running   0          2m12s
kube-system   cilium-envoy-nhg9g                  1/1     Running   0          2m12s
kube-system   cilium-envoy-pqnnx                  1/1     Running   0          2m12s
kube-system   cilium-envoy-qmlpt                  1/1     Running   0          2m12s
kube-system   cilium-nddsq                        1/1     Running   0          2m12s
kube-system   cilium-operator-865bc7f457-f74mb    1/1     Running   0          2m12s
kube-system   cilium-operator-865bc7f457-z8vxs    1/1     Running   0          2m12s
kube-system   cilium-xts8r                        1/1     Running   0          2m12s
kube-system   coredns-674b8bbfcf-7g6qk            1/1     Running   0          26m
kube-system   coredns-674b8bbfcf-t46dz            1/1     Running   0          26m
kube-system   etcd-cilium-m1                      1/1     Running   0          26m
kube-system   kube-apiserver-cilium-m1            1/1     Running   0          26m
kube-system   kube-controller-manager-cilium-m1   1/1     Running   0          26m
kube-system   kube-scheduler-cilium-m1            1/1     Running   0          26m

# Cilium 상태 확인
kubectl exec -it -n kube-system ds/cilium -c cilium-agent -- cilium-dbg status --verbose
KubeProxyReplacement:   True   [eth0    10.0.2.15 fd17:625c:f037:2:a00:27ff:fe71:19d8 fe80::a00:27ff:fe71:19d8, eth1   192.168.10.102 fe80::a00:27ff:fed3:64b (Direct Routing)]
Routing:                Network: Native   Host: BPF
Masquerading:           BPF   [eth0, eth1]   172.20.0.0/16 [IPv4: Enabled, IPv6: Disabled]
...
...

# 노드에 iptables 확인
for i in cilium-m1 cilium-w1 cilium-w2 ; do echo ">> node : $i <<"; ssh $i sudo iptables -t nat -S ; echo; done

for i in cilium-m1 cilium-w1 cilium-w2 ; do echo ">> node : $i <<"; ssh $i sudo iptables-save ; echo; done

# ciliumnodes 확인
❯ kubectl get ciliumnodes
NAME        CILIUMINTERNALIP   INTERNALIP       AGE
cilium-m1   172.20.0.12        192.168.10.100   14m
cilium-w1   172.20.1.69        192.168.10.101   14m
cilium-w2   172.20.2.126       192.168.10.102   14m

# PodCIDR 확인
❯ kubectl get ciliumnodes -o json | grep podCIDRs -A2
                    "podCIDRs": [
                        "172.20.0.0/24"
                    ],
--
                    "podCIDRs": [
                        "172.20.1.0/24"
                    ],
--
                    "podCIDRs": [
                        "172.20.2.0/24"
                    ],

# PodCIDR IPAM 확인
❯ kubectl get nodes -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.podCIDR}{"\n"}{end}'
cilium-m1       10.244.0.0/24
cilium-w1       10.244.1.0/24
cilium-w2       10.244.2.0/24


# Sample Application 배포
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


# cilium-m1 노드에 curl-pod 파드 배포
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: curl-pod
  labels:
    app: curl
spec:
  nodeName: cilium-m1
  containers:
    - name: curl
      image: alpine/curl
      command: ["sleep", "36000"]
EOF

# pod status 확인
❯ kubectl get pod -owide
NAME                      READY   STATUS    RESTARTS   AGE     IP             NODE        NOMINATED NODE   READINESS GATES
curl-pod                  1/1     Running   0          4m19s   172.20.0.87    cilium-m1   <none>           <none>
webpod-697b545f57-bjlnx   1/1     Running   0          4m19s   172.20.2.2     cilium-w2   <none>           <none>
webpod-697b545f57-lqzm9   1/1     Running   0          4m19s   172.20.1.249   cilium-w1   <none>           <none>

# cilium endpoints 확인
❯ kubectl get ciliumendpoints
NAME                      SECURITY IDENTITY   ENDPOINT STATE   IPV4           IPV6
curl-pod                  3012                ready            172.20.0.87
webpod-697b545f57-bjlnx   18197               ready            172.20.2.2
webpod-697b545f57-lqzm9   18197               ready            172.20.1.249

# cilium endpoint list 확인
❯ kubectl exec -it -n kube-system ds/cilium -c cilium-agent -- cilium-dbg endpoint list
ENDPOINT   POLICY (ingress)   POLICY (egress)   IDENTITY   LABELS (source:key[=value])                                                  IPv6   IPv4           STATUS
           ENFORCEMENT        ENFORCEMENT
234        Disabled           Disabled          3012       k8s:app=curl                                                                        172.20.0.87    ready
                                                           k8s:io.cilium.k8s.namespace.labels.kubernetes.io/metadata.name=default
                                                           k8s:io.cilium.k8s.policy.cluster=default
                                                           k8s:io.cilium.k8s.policy.serviceaccount=default
                                                           k8s:io.kubernetes.pod.namespace=default
491        Disabled           Disabled          4          reserved:health                                                                     172.20.0.223   ready
1059       Disabled           Disabled          3176       k8s:io.cilium.k8s.namespace.labels.kubernetes.io/metadata.name=kube-system          172.20.0.24    ready
                                                           k8s:io.cilium.k8s.policy.cluster=default
                                                           k8s:io.cilium.k8s.policy.serviceaccount=coredns
                                                           k8s:io.kubernetes.pod.namespace=kube-system
                                                           k8s:k8s-app=kube-dns
1960       Disabled           Disabled          3176       k8s:io.cilium.k8s.namespace.labels.kubernetes.io/metadata.name=kube-system          172.20.0.249   ready
                                                           k8s:io.cilium.k8s.policy.cluster=default
                                                           k8s:io.cilium.k8s.policy.serviceaccount=coredns
                                                           k8s:io.kubernetes.pod.namespace=kube-system
                                                           k8s:k8s-app=kube-dns
2068       Disabled           Disabled          1          k8s:node-role.kubernetes.io/control-plane                                                          ready
                                                           k8s:node.kubernetes.io/exclude-from-external-load-balancers
                                                           reserved:host

# 통신 확인
for i in {1..5}; do kubectl exec curl-pod -- curl -s webpod | grep Hostname; done
Hostname: webpod-697b545f57-bjlnx
Hostname: webpod-697b545f57-lqzm9
Hostname: webpod-697b545f57-lqzm9
Hostname: webpod-697b545f57-lqzm9
Hostname: webpod-697b545f57-bjlnx
```

---

## 4. Cilium 설치 확인

```bash
# Cilium CLI 설치
CILIUM_CLI_VERSION=$(curl -s https://raw.githubusercontent.com/cilium/cilium-cli/main/stable.txt)
CLI_ARCH=amd64
if [ "$(uname -m)" = "aarch64" ]; then CLI_ARCH=arm64; fi
curl -L --fail --remote-name-all https://github.com/cilium/cilium-cli/releases/download/${CILIUM_CLI_VERSION}/cilium-linux-${CLI_ARCH}.tar.gz >/dev/null 2>&1
tar xzvfC cilium-linux-${CLI_ARCH}.tar.gz /usr/local/bin
rm cilium-linux-${CLI_ARCH}.tar.gz

# cilium status 확인
❯ cilium status
    /¯¯\
 /¯¯\__/¯¯\    Cilium:             OK
 \__/¯¯\__/    Operator:           OK
 /¯¯\__/¯¯\    Envoy DaemonSet:    OK
 \__/¯¯\__/    Hubble Relay:       disabled
    \__/       ClusterMesh:        disabled

DaemonSet              cilium                   Desired: 3, Ready: 3/3, Available: 3/3
DaemonSet              cilium-envoy             Desired: 3, Ready: 3/3, Available: 3/3
Deployment             cilium-operator          Desired: 2, Ready: 2/2, Available: 2/2
Containers:            cilium                   Running: 3
                       cilium-envoy             Running: 3
                       cilium-operator          Running: 2
                       clustermesh-apiserver
                       hubble-relay
Cluster Pods:          2/2 managed by Cilium
Helm chart version:    1.17.5
Image versions         cilium             quay.io/cilium/cilium:v1.17.5@sha256:baf8541723ee0b72d6c489c741c81a6fdc5228940d66cb76ef5ea2ce3c639ea6: 3
                       cilium-envoy       quay.io/cilium/cilium-envoy:v1.32.6-1749271279-0864395884b263913eac200ee2048fd985f8e626@sha256:9f69e290a7ea3d4edf9192acd81694089af048ae0d8a67fb63bd62dc1d72203e: 3
                       cilium-operator    quay.io/cilium/operator-generic:v1.17.5@sha256:f954c97eeb1b47ed67d08cc8fb4108fb829f869373cbb3e698a7f8ef1085b09e: 2

# cilium config 확인
❯ cilium config view
❯ kubectl get cm -n kube-system cilium-config -o json | jq

# cilium debug 켜기
❯ cilium config set debug true && watch kubectl get pod -A

✨ Patching ConfigMap cilium-config with debug=true...
♻️  Restarted Cilium pods

❯ cilium config view | grep -i debug
debug                                             true
debug-verbose

# debug 정보 확인
❯ kubectl exec -n kube-system -c cilium-agent -it ds/cilium -- cilium-dbg config
##### Read-write configurations #####
ConntrackAccounting               : Disabled
ConntrackLocal                    : Disabled
Debug                             : Disabled
DebugLB                           : Disabled
DebugPolicy                       : Enabled
DropNotification                  : Enabled
MonitorAggregationLevel           : Medium
PolicyAccounting                  : Enabled
PolicyAuditMode                   : Disabled
PolicyTracing                     : Disabled
PolicyVerdictNotification         : Enabled
SourceIPVerification              : Enabled
TraceNotification                 : Enabled
MonitorNumPages                   : 64
PolicyEnforcement                 : default

# debug 상세 정보 확인
❯ kubectl exec -n kube-system -c cilium-agent -it ds/cilium -- cilium-dbg status --verbose
...
KubeProxyReplacement:   True   [eth0    10.0.2.15 fd17:625c:f037:2:a00:27ff:fe71:19d8 fe80::a00:27ff:fe71:19d8, eth1   192.168.10.102 fe80::a00:27ff:fef6:fcbc (Direct Routing)]
Routing:                Network: Native   Host: BPF
Attach Mode:            TCX
Device Mode:            veth
Masquerading:           BPF   [eth0, eth1]   172.20.0.0/16 [IPv4: Enabled, IPv6: Disabled]
...
KubeProxyReplacement Details:
  Status:                 True
  Socket LB:              Enabled
  Socket LB Tracing:      Enabled
  Socket LB Coverage:     Full
  Devices:                eth0    10.0.2.15 fd17:625c:f037:2:a00:27ff:fe71:19d8 fe80::a00:27ff:fe71:19d8, eth1   192.168.10.102 fe80::a00:27ff:fef6:fcbc (Direct Routing)
  Mode:                   SNAT
  Backend Selection:      Random
  Session Affinity:       Enabled
  Graceful Termination:   Enabled
  NAT46/64 Support:       Disabled
  XDP Acceleration:       Disabled
  Services:
  - ClusterIP:      Enabled
  - NodePort:       Enabled (Range: 30000-32767) 
  - LoadBalancer:   Enabled 
  - externalIPs:    Enabled 
  - HostPort:       Enabled
...

```

---

## 5. Reference

- [Cilium Docs - Component Overview](https://docs.cilium.io/en/stable/overview/component-overview/)
- [Cilium Docs - System Requirements](https://docs.cilium.io/en/stable/operations/system_requirements/)
- [Cilium Docs - Kubernetes Without kube-proxy](https://docs.cilium.io/en/stable/network/kubernetes/kubeproxy-free/)
- [Cilium Docs - Helm Reference](https://docs.cilium.io/en/stable/helm-reference/)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
