---
title: Cilium Cluster Mesh [Cilium Study 5주차]
date: 2025-08-14 00:05:11 +0900
author: kkamji
categories: [Kubernetes, Cilium]
tags: [kubernetes, devops, cilium, cilium-study, cluster-mesh, service-affinity, hubble, kind]
comments: true
image:
  path: /assets/img/kubernetes/cilium/cilium.webp
---

**Cluster Mesh**는 여러 Kubernetes Cluster를 하나의 **Network Mesh**로 확장하는 기능으로, 연결된 모든 Cluster의 엔드포인트가 서로 통신할 수 있도록 하면서도 **정책(Policy) 적용**을 그대로 유지할 수 있게 해주는 기능입니다. 이를 통해 **Multi Cluster에서 Pod-to-Pod 간 연결**이 가능하며, 글로벌 서비스를 정의하여 여러 Cluster에 걸쳐 **로드밸런싱**을 수행할 수도 있습니다. 특히 멀티 Cluster 운영 환경에서 **서비스 가용성**을 높이고 **정책 기반의 보안**을 강화할 수 있다는 점에서 중요한 기능입니다.  

이번 시간에는 Kind를 사용해 2개의 Kubernetes Cluster를 배포하고, Cluster Mesh로 연결한 뒤, 통신이 되는 것을 확인해보도록 하겠습니다.

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
12. [IPAM 개념 및 Kubernetes Host Scope -> Cluster Scope Migration 실습 [Cilium Study 3주차]]({% post_url 2025/2025-07-29-cilium-ipam-mode %})
13. [Cilium Network Routing 이해하기 – Encapsulation과 Native Routing 비교 [Cilium Study 3주차]]({% post_url 2025/2025-08-03-cilium-routing %})
14. [Cilium Native Routing 통신 확인 및 문제 해결 – Static Route & BGP [Cilium Study 4주차]]({% post_url 2025/2025-08-10-cilium-native-routing %})
15. [Cilium BGP Control Plane [Cilium Study 5주차]]({% post_url 2025/2025-08-11-cilium-bgp-control-plane %})
16. [Cilium Service LoadBalancer BGP Advertisement & ExternalTrafficPolicy [Cilium Study 5주차]]({% post_url 2025/2025-08-12-cilium-lb-ipam %})
17. [Kind로 Kubernetes Cluster 배포하기 [Cilium Study 5주차]]({% post_url 2025/2025-08-13-kind %})
18. [Cilium Cluster Mesh [Cilium Study 5주차] (현재 글)]({% post_url 2025/2025-08-14-cilium-cluster-mesh %})
19. [Cilium Service Mesh [Cilium Study 6주차]]({% post_url 2025/2025-08-18-cilium-service-mesh %})
20. [Kube-burner 소개 및 실습 [Cilium Study 7주차]]({% post_url 2025/2025-08-25-kube-burner %})
21. [Cilium Network Security [Cilium Study 8주차]]({% post_url 2025/2025-09-03-cilium-network-security %})

---

## 1. Prerequisites & Requirements

Cluster Mesh를 구성하기 위해서는 몇 가지 공통적인 네트워크 및 설정 조건이 충족되어야 합니다.  

### 1.1. Cluster Addressing Requirements

- 모든 Cluster는 동일한 **Datapath 모드**(Encapsulation 또는 Native Routing)로 설정해야 합니다.  
- 각 Cluster의 **PodCIDR**은 서로 충돌하지 않고 고유해야 합니다.  
- 모든 Cluster의 노드들은 **InternalIP 기준으로 서로 통신 가능**해야 하며, 일반적으로 **VPC Peering**이나 **VPN Tunnel**을 통해 연결됩니다.  
- 방화벽이나 네트워크 정책에서 Cluster 간 통신이 허용되어야 하며, 필요한 포트는 Cilium Firewall Rules 문서를 참조해야 합니다.  

### 1.2. Additional Requirements for Native-routed Datapath Modes

- 각 Cluster의 PodCIDR을 모두 포함할 수 있는 **Native Routing CIDR**이 필요합니다.  
  - 예시: 모든 Cluster가 `10.0.0.0/8` 범위에서 할당받는 경우, 아래와 같이 지정해야 합니다.  
    ```yaml
    ConfigMap: ipv4-native-routing-cidr=10.0.0.0/8
    Helm 옵션: --set ipv4NativeRoutingCIDR=10.0.0.0/8
    CLI 설치 옵션: cilium install --set ipv4NativeRoutingCIDR=10.0.0.0/8
    ```
- Pod 역시 Cluster 간 직접 IP 통신이 가능해야 하며, 이를 위해 **VPN Tunnel**이나 **Network Peering** 구성이 필요합니다.  
- 방화벽 규칙은 `Pod-to-Pod` 트래픽에 대해 모든 포트가 열려 있어야 하며, 그렇지 않으면 워크로드 간 통신이 차단될 수 있습니다.  

### 1.3. Scaling Limitations

Cluster Mesh는 확장성에도 주의해야 합니다.  

- 기본적으로 연결 가능한 최대 Cluster 수는 **255개**입니다.  
- `maxConnectedClusters` 옵션을 통해 **511개**까지 확장이 가능하지만, 그만큼 **Cluster-local Identity** 수가 줄어듭니다.  
- 이 값은 **Cilium 설치 시점에만 지정**할 수 있으며, 운영 중인 Cluster에서 변경하면 **정책 적용 오류 및 연결 장애**가 발생할 수 있습니다.  

| MaxConnectedClusters | 최대 Cluster-local Identity 수 |
| -------------------- | ------------------------------ |
| 255 (기본값)         | 65,535                         |
| 511                  | 32,767                         |

설정 방법:
```yaml
ConfigMap: max-connected-clusters=511
Helm 옵션: --set clustermesh.maxConnectedClusters=511
CLI 설치 옵션: cilium install --set clustermesh.maxConnectedClusters=511
```

> 주의: maxConnectedClusters 값은 설치 이후 변경 불가하며, 잘못 변경하면 Cluster Mesh 전체에 통신 장애가 발생할 수 있습니다.
{: .prompt-danger}

---

## 2. Deploy Kubernetes Clusters using Kind

**Cilium Cluster Mesh** 구성에 사용될 `west`, `east` 두 개의 Kubernetes Cluster를 Kind를 사용해 배포하고, 각 노드에는 실습에 필요한 편의성 도구들을 설치하겠습니다.

Cilium 설치를 위해 `DefaultCNI` 와 `kube-proxy`는 배포하지 않았습니다.

```shell
########################################################
# west Cluster 배포
########################################################

kind create cluster --name west --image kindest/node:v1.33.2 --config - <<EOF
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
- role: control-plane
  extraPortMappings:
  - containerPort: 30000 # sample apps
    hostPort: 30000
  - containerPort: 30001 # hubble ui
    hostPort: 30001
- role: worker
  extraPortMappings:
  - containerPort: 30002 # sample apps
    hostPort: 30002
networking:
  podSubnet: "10.0.0.0/16"
  serviceSubnet: "10.2.0.0/16"
  disableDefaultCNI: true
  kubeProxyMode: none
EOF

########################################################
# west Cluster 설치 확인
########################################################

kubectl ctx
kubectl get node 
kubectl get pod -A

########################################################
# west Cluster 노드에 기본 툴 설치
########################################################

docker exec -it west-control-plane sh -c 'apt update && apt install tree psmisc lsof wget net-tools dnsutils tcpdump ngrep iputils-ping git -y'
docker exec -it west-worker sh -c 'apt update && apt install tree psmisc lsof wget net-tools dnsutils tcpdump ngrep iputils-ping git -y'


########################################################
# east Cluster 배포
########################################################

kind create cluster --name east --image kindest/node:v1.33.2 --config - <<EOF
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
- role: control-plane
  extraPortMappings:
  - containerPort: 31000 # sample apps
    hostPort: 31000
  - containerPort: 31001 # hubble ui
    hostPort: 31001
- role: worker
  extraPortMappings:
  - containerPort: 31002 # sample apps
    hostPort: 31002
networking:
  podSubnet: "10.1.0.0/16"
  serviceSubnet: "10.3.0.0/16"
  disableDefaultCNI: true
  kubeProxyMode: none
EOF

########################################################
# east Cluster 노드에 기본 툴 설치
########################################################

docker exec -it east-control-plane sh -c 'apt update && apt install tree psmisc lsof wget net-tools dnsutils tcpdump ngrep iputils-ping git -y'
docker exec -it east-worker sh -c 'apt update && apt install tree psmisc lsof wget net-tools dnsutils tcpdump ngrep iputils-ping git -y'


########################################################
# Cluster 배포 확인
########################################################

kubectl config get-contexts 
# CURRENT   NAME        CLUSTER          AUTHINFO           NAMESPACE
# *         kind-east   kind-east        kind-east          
#           kind-west   kind-west        kind-west          

kubectl config set-context kind-east
kubectl get node -v=6 --context kind-east
kubectl get node -v=6 --context kind-west
kubectl get pod -A --context kind-east
kubectl get pod -A --context kind-west


########################################################
# alias 설정
########################################################
alias kwest='kubectl --context kind-west'
alias keast='kubectl --context kind-east'

########################################################
# 확인
########################################################
kwest get node -owide
# NAME                 STATUS     ROLES           AGE     VERSION   INTERNAL-IP   EXTERNAL-IP   OS-IMAGE                         KERNEL-VERSION                     CONTAINER-RUNTIME
# west-control-plane   NotReady   control-plane   3m36s   v1.33.2   172.18.0.4    <none>        Debian GNU/Linux 12 (bookworm)   6.6.87.2-microsoft-standard-WSL2   containerd://2.1.3
# west-worker          NotReady   <none>          3m21s   v1.33.2   172.18.0.5    <none>        Debian GNU/Linux 12 (bookworm)   6.6.87.2-microsoft-standard-WSL2   containerd://2.1.3
keast get node -owide
# NAME                 STATUS     ROLES           AGE     VERSION   INTERNAL-IP   EXTERNAL-IP   OS-IMAGE                         KERNEL-VERSION                     CONTAINER-RUNTIME
# east-control-plane   NotReady   control-plane   4m37s   v1.33.2   172.18.0.3    <none>        Debian GNU/Linux 12 (bookworm)   6.6.87.2-microsoft-standard-WSL2   containerd://2.1.3
# east-worker          NotReady   <none>          4m27s   v1.33.2   172.18.0.2    <none>        Debian GNU/Linux 12 (bookworm)   6.6.87.2-microsoft-standard-WSL2   containerd://2.1.3
```

---

## 3. Deploy Cilium CNI

cilium cil를 사용해 Cilium CNI를 설치하겠습니다. `--dry-run-helm-values` 옵션을 통해 Helm Value를 확인할 수도 있습니다

```shell
# 아래 홈페이지에서 환경에 맞는 Cilium CLI 설치 후 아래 실습 진행
# https://docs.cilium.io/en/stable/gettingstarted/k8s-install-default/#install-the-cilium-cli 

########################################################
# (west) cilium cli 로 cilium cni 설치
########################################################
cilium install --version 1.17.6 --set ipam.mode=kubernetes \
--set kubeProxyReplacement=true --set bpf.masquerade=true \
--set endpointHealthChecking.enabled=false --set healthChecking=false \
--set operator.replicas=1 --set debug.enabled=true \
--set routingMode=native --set autoDirectNodeRoutes=true --set ipv4NativeRoutingCIDR=10.0.0.0/16 \
--set ipMasqAgent.enabled=true --set ipMasqAgent.config.nonMasqueradeCIDRs='{10.1.0.0/16}' \
--set cluster.name=west --set cluster.id=1 \
--context kind-west

########################################################
# (east) cilium cli 로 cilium cni 설치
########################################################
cilium install --version 1.17.6 --set ipam.mode=kubernetes \
--set kubeProxyReplacement=true --set bpf.masquerade=true \
--set endpointHealthChecking.enabled=false --set healthChecking=false \
--set operator.replicas=1 --set debug.enabled=true \
--set routingMode=native --set autoDirectNodeRoutes=true --set ipv4NativeRoutingCIDR=10.1.0.0/16 \
--set ipMasqAgent.enabled=true --set ipMasqAgent.config.nonMasqueradeCIDRs='{10.0.0.0/16}' \
--set cluster.name=east --set cluster.id=2 \
--context kind-east

########################################################
# cilium Status 확인
########################################################
kwest get pod -A; keast get pod -A
# NAMESPACE            NAME                                         READY   STATUS    RESTARTS   AGE
# kube-system          cilium-5snp2                                 1/1     Running   0          3m30s
# kube-system          cilium-envoy-4dzhh                           1/1     Running   0          3m30s
# kube-system          cilium-envoy-h27gq                           1/1     Running   0          3m30s
# kube-system          cilium-lvnft                                 1/1     Running   0          3m30s
# kube-system          cilium-operator-867f8dc978-b4vzf             1/1     Running   0          3m30s
# kube-system          coredns-674b8bbfcf-v88m6                     1/1     Running   0          14m
# kube-system          coredns-674b8bbfcf-xbgl2                     1/1     Running   0          14m
# kube-system          etcd-west-control-plane                      1/1     Running   0          14m
# kube-system          kube-apiserver-west-control-plane            1/1     Running   0          14m
# kube-system          kube-controller-manager-west-control-plane   1/1     Running   0          14m
# kube-system          kube-scheduler-west-control-plane            1/1     Running   0          14m
# local-path-storage   local-path-provisioner-7dc846544d-j2pbf      1/1     Running   0          14m
# NAMESPACE            NAME                                         READY   STATUS    RESTARTS   AGE
# kube-system          cilium-cwgbs                                 1/1     Running   0          3m23s
# kube-system          cilium-envoy-6lrpv                           1/1     Running   0          3m23s
# kube-system          cilium-envoy-n29n5                           1/1     Running   0          3m23s
# kube-system          cilium-hk8tk                                 1/1     Running   0          3m23s
# kube-system          cilium-operator-955765ddf-96p95              1/1     Running   0          3m23s
# kube-system          coredns-674b8bbfcf-2w6pb                     1/1     Running   0          15m
# kube-system          coredns-674b8bbfcf-xzdx8                     1/1     Running   0          15m
# kube-system          etcd-east-control-plane                      1/1     Running   0          15m
# kube-system          kube-apiserver-east-control-plane            1/1     Running   0          15m
# kube-system          kube-controller-manager-east-control-plane   1/1     Running   0          15m
# kube-system          kube-scheduler-east-control-plane            1/1     Running   0          15m
# local-path-storage   local-path-provisioner-7dc846544d-qzfrg      1/1     Running   0          15m

cilium status --context kind-west && cilium status --context kind-east
#     /¯¯\
#  /¯¯\__/¯¯\    Cilium:             OK
#  \__/¯¯\__/    Operator:           OK
#  /¯¯\__/¯¯\    Envoy DaemonSet:    OK
#  \__/¯¯\__/    Hubble Relay:       disabled
#     \__/       ClusterMesh:        disabled

# DaemonSet              cilium                   Desired: 2, Ready: 2/2, Available: 2/2
# DaemonSet              cilium-envoy             Desired: 2, Ready: 2/2, Available: 2/2
# Deployment             cilium-operator          Desired: 1, Ready: 1/1, Available: 1/1
# Containers:            cilium                   Running: 2
#                        cilium-envoy             Running: 2
#                        cilium-operator          Running: 1
#                        clustermesh-apiserver
#                        hubble-relay
# Cluster Pods:          3/3 managed by Cilium
# Helm chart version:    1.17.6
# Image versions         cilium             quay.io/cilium/cilium:v1.17.6@sha256:544de3d4fed7acba72758413812780a4972d47c39035f2a06d6145d8644a3353: 2
#                        cilium-envoy       quay.io/cilium/cilium-envoy:v1.33.4-1752151664-7c2edb0b44cf95f326d628b837fcdd845102ba68@sha256:318eff387835ca2717baab42a84f35a83a5f9e7d519253df87269f80b9ff0171: 2
#                        cilium-operator    quay.io/cilium/operator-generic:v1.17.6@sha256:91ac3bf7be7bed30e90218f219d4f3062a63377689ee7246062fa0cc3839d096: 1
#     /¯¯\
#  /¯¯\__/¯¯\    Cilium:             OK
#  \__/¯¯\__/    Operator:           OK
#  /¯¯\__/¯¯\    Envoy DaemonSet:    OK
#  \__/¯¯\__/    Hubble Relay:       disabled
#     \__/       ClusterMesh:        disabled

# DaemonSet              cilium                   Desired: 2, Ready: 2/2, Available: 2/2
# DaemonSet              cilium-envoy             Desired: 2, Ready: 2/2, Available: 2/2
# Deployment             cilium-operator          Desired: 1, Ready: 1/1, Available: 1/1
# Containers:            cilium                   Running: 2
#                        cilium-envoy             Running: 2
#                        cilium-operator          Running: 1
#                        clustermesh-apiserver
#                        hubble-relay
# Cluster Pods:          3/3 managed by Cilium
# Helm chart version:    1.17.6
# Image versions         cilium             quay.io/cilium/cilium:v1.17.6@sha256:544de3d4fed7acba72758413812780a4972d47c39035f2a06d6145d8644a3353: 2
#                        cilium-envoy       quay.io/cilium/cilium-envoy:v1.33.4-1752151664-7c2edb0b44cf95f326d628b837fcdd845102ba68@sha256:318eff387835ca2717baab42a84f35a83a5f9e7d519253df87269f80b9ff0171: 2
#                        cilium-operator    quay.io/cilium/operator-generic:v1.17.6@sha256:91ac3bf7be7bed30e90218f219d4f3062a63377689ee7246062fa0cc3839d096: 1

cilium config view --context kind-west
cilium config view --context kind-east
kwest exec -it -n kube-system ds/cilium -- cilium status --verbose
keast exec -it -n kube-system ds/cilium -- cilium status --verbose

kwest -n kube-system exec ds/cilium -c cilium-agent -- cilium-dbg bpf ipmasq list
# IP PREFIX/ADDRESS
# 10.1.0.0/16
# 169.254.0.0/16

keast -n kube-system exec ds/cilium -c cilium-agent -- cilium-dbg bpf ipmasq list
# IP PREFIX/ADDRESS
# 169.254.0.0/16
# 10.0.0.0/16

########################################################
# coredns 확인 : 둘 다, cluster.local 기본 도메인 네임 사용
########################################################
kubectl describe cm -n kube-system coredns --context kind-west | grep kubernetes
    kubernetes cluster.local in-addr.arpa ip6.arpa {

kubectl describe cm -n kube-system coredns --context kind-west | grep kubernetes
    kubernetes cluster.local in-addr.arpa ip6.arpa {
```

---

## 4. Setting Up Cluster Mesh

```shell
########################################################
# 라우팅 정보 확인 (다른 Cluster에 대한 Routing 정보 없음)
########################################################
docker exec -it west-control-plane ip -c route
docker exec -it west-worker ip -c route
docker exec -it east-control-plane ip -c route
docker exec -it east-worker ip -c route
# default via 172.18.0.1 dev eth0
# 10.0.0.0/24 via 10.0.0.95 dev cilium_host proto kernel src 10.0.0.95
# 10.0.0.95 dev cilium_host proto kernel scope link
# 10.0.1.0/24 via 172.18.0.5 dev eth0 proto kernel
# 172.18.0.0/16 dev eth0 proto kernel scope link src 172.18.0.4
# default via 172.18.0.1 dev eth0
# 10.0.0.0/24 via 172.18.0.4 dev eth0 proto kernel
# 10.0.1.0/24 via 10.0.1.218 dev cilium_host proto kernel src 10.0.1.218
# 10.0.1.218 dev cilium_host proto kernel scope link
# 172.18.0.0/16 dev eth0 proto kernel scope link src 172.18.0.5
# default via 172.18.0.1 dev eth0
# 10.1.0.0/24 via 10.1.0.227 dev cilium_host proto kernel src 10.1.0.227
# 10.1.0.227 dev cilium_host proto kernel scope link
# 10.1.1.0/24 via 172.18.0.2 dev eth0 proto kernel
# 172.18.0.0/16 dev eth0 proto kernel scope link src 172.18.0.3
# default via 172.18.0.1 dev eth0
# 10.1.0.0/24 via 172.18.0.3 dev eth0 proto kernel
# 10.1.1.0/24 via 10.1.1.19 dev cilium_host proto kernel src 10.1.1.19
# 10.1.1.19 dev cilium_host proto kernel scope link
# 172.18.0.0/16 dev eth0 proto kernel scope link src 172.18.0.2

########################################################
# CA(Certificate Authority) 공유
########################################################
keast get secret -n kube-system cilium-ca
keast delete secret -n kube-system cilium-ca

kubectl --context kind-west get secret -n kube-system cilium-ca -o yaml | \
kubectl --context kind-east create -f -

keast get secret -n kube-system cilium-ca

########################################################
# Enable Cluster Mesh : 간단한 실습 환경으로 NodePort 로 진행
########################################################
cilium clustermesh enable --service-type NodePort --enable-kvstoremesh=false --context kind-west
cilium clustermesh enable --service-type NodePort --enable-kvstoremesh=false --context kind-east

########################################################
# (west) 32379 NodePort 정보 -> clustermesh-apiserver 서비스 정보
########################################################
kwest get svc,ep -n kube-system clustermesh-apiserver --context kind-west
# Warning: v1 Endpoints is deprecated in v1.33+; use discovery.k8s.io/v1 EndpointSlice
# NAME                            TYPE       CLUSTER-IP     EXTERNAL-IP   PORT(S)          AGE
# service/clustermesh-apiserver   NodePort   10.2.174.206   <none>        2379:32379/TCP   111s

# NAME                              ENDPOINTS         AGE
# endpoints/clustermesh-apiserver   10.0.1.234:2379   111s

kwest get pod -n kube-system -owide | grep clustermesh
# clustermesh-apiserver-5cf45db9cc-6jfgr       2/2     Running     0          2m53s   10.0.1.234   west-worker          <none>           <none>
# clustermesh-apiserver-generate-certs-4rl64   0/1     Completed   0          2m53s   172.18.0.5   west-worker          <none>           <none>

########################################################
# (east) 32379 NodePort 정보 -> clustermesh-apiserver 서비스 정보
########################################################
keast get svc,ep -n kube-system clustermesh-apiserver --context kind-east
# Warning: v1 Endpoints is deprecated in v1.33+; use discovery.k8s.io/v1 EndpointSlice
# NAME                            TYPE       CLUSTER-IP     EXTERNAL-IP   PORT(S)          AGE
# service/clustermesh-apiserver   NodePort   10.3.176.230   <none>        2379:32379/TCP   3m1s

# NAME                              ENDPOINTS        AGE
# endpoints/clustermesh-apiserver   10.1.1.44:2379   3m1s

keast get pod -n kube-system -owide | grep clustermesh
# clustermesh-apiserver-5cf45db9cc-j4ssr       2/2     Running     0          3m35s   10.1.1.44    east-worker          <none>           <none>
# clustermesh-apiserver-generate-certs-dtc6m   0/1     Completed   0          3m35s   172.18.0.2   east-worker          <none>           <none>

########################################################
# 모니터링 : 신규 터미널 2개 (띄워두고 진행)
########################################################
watch -d "cilium clustermesh status --context kind-west --wait"
watch -d "cilium clustermesh status --context kind-east --wait"

########################################################
# Connect Cluster Mesh
########################################################
cilium clustermesh connect --context kind-west --destination-context kind-east
# ✨ Extracting access information of cluster west...
# 🔑 Extracting secrets from cluster west...
# ⚠️  Service type NodePort detected! Service may fail when nodes are removed from the cluster!
# ℹ️  Found ClusterMesh service IPs: [172.18.0.4]
# ✨ Extracting access information of cluster east...
# 🔑 Extracting secrets from cluster east...
# ⚠️  Service type NodePort detected! Service may fail when nodes are removed from the cluster!
# ℹ️  Found ClusterMesh service IPs: [172.18.0.3]
# ℹ️ Configuring Cilium in cluster kind-west to connect to cluster kind-east
# ℹ️ Configuring Cilium in cluster kind-east to connect to cluster kind-west
# ✅ Connected cluster kind-west <=> kind-east!
```

![Cluster Mesh Status](/assets/img/kubernetes/cilium/5w-cluster-mesh-status.webp)

---

## 5. Cluster Mesh 확인

```shell
########################################################
# Connect Cluster Mesh 확인
########################################################
kubectl exec -it -n kube-system ds/cilium -c cilium-agent --context kind-west -- cilium-dbg troubleshoot clustermesh
# Found 1 cluster configurations

# Cluster "east":
# 📄 Configuration path: /var/lib/cilium/clustermesh/east

# 🔌 Endpoints:
#    - https://east.mesh.cilium.io:32379
#      ✅ Hostname resolved to: 172.18.0.3
#      ✅ TCP connection successfully established to 172.18.0.3:32379
#      ✅ TLS connection successfully established to 172.18.0.3:32379
#      ℹ️  Negotiated TLS version: TLS 1.3, ciphersuite TLS_AES_128_GCM_SHA256
#      ℹ️  Etcd server version: 3.5.21

# 🔑 Digital certificates:
#    ✅ TLS Root CA certificates:
#       - Serial number:       ca:3e:3b:ab:7a:46:92:72:24:f0:b2:b1:60:08:42:d8
#         Subject:             CN=Cilium CA
#         Issuer:              CN=Cilium CA
#         Validity:
#           Not before:  2025-08-20 12:45:55 +0000 UTC
#           Not after:   2028-08-19 12:45:55 +0000 UTC
#    ✅ TLS client certificates:
#       - Serial number:       43:1e:fe:17:a1:03:bd:bb:8c:c6:14:81:c9:f8:95:56:27:fd:3d:95
#         Subject:             CN=remote
#         Issuer:              CN=Cilium CA
#         Validity:
#           Not before:  2025-08-20 13:05:00 +0000 UTC
#           Not after:   2028-08-19 13:05:00 +0000 UTC
#         ⚠️ Cannot verify certificate with the configured root CAs

# ⚙️ Etcd client:
#    ✅ Etcd connection successfully established
#    ℹ️  Etcd cluster ID: 8bdad773a2b323fa

kubectl exec -it -n kube-system ds/cilium -c cilium-agent --context kind-east -- cilium-dbg troubleshoot clustermesh
# Found 1 cluster configurations

# Cluster "west":
# 📄 Configuration path: /var/lib/cilium/clustermesh/west

# 🔌 Endpoints:
#    - https://west.mesh.cilium.io:32379
#      ✅ Hostname resolved to: 172.18.0.4
#      ✅ TCP connection successfully established to 172.18.0.4:32379
#      ✅ TLS connection successfully established to 172.18.0.4:32379
#      ℹ️  Negotiated TLS version: TLS 1.3, ciphersuite TLS_AES_128_GCM_SHA256
#      ℹ️  Etcd server version: 3.5.21

# 🔑 Digital certificates:
#    ✅ TLS Root CA certificates:
#       - Serial number:       ca:3e:3b:ab:7a:46:92:72:24:f0:b2:b1:60:08:42:d8
#         Subject:             CN=Cilium CA
#         Issuer:              CN=Cilium CA
#         Validity:
#           Not before:  2025-08-20 12:45:55 +0000 UTC
#           Not after:   2028-08-19 12:45:55 +0000 UTC
#    ✅ TLS client certificates:
#       - Serial number:       47:06:82:3e:8d:b4:43:37:07:da:dc:91:43:92:f5:4a:78:82:46:34
#         Subject:             CN=remote
#         Issuer:              CN=Cilium CA
#         Validity:
#           Not before:  2025-08-20 13:05:00 +0000 UTC
#           Not after:   2028-08-19 13:05:00 +0000 UTC
#         ⚠️ Cannot verify certificate with the configured root CAs

# ⚙️ Etcd client:
#    ✅ Etcd connection successfully established
#    ℹ️  Etcd cluster ID: 6f26c1464b24da58

########################################################
# Pod Status 확인
########################################################
kwest get pod -A && keast get pod -A
# NAMESPACE            NAME                                         READY   STATUS      RESTARTS   AGE
# kube-system          cilium-2n7t5                                 1/1     Running     0          2m8s
# kube-system          cilium-envoy-4dzhh                           1/1     Running     0          26m
# kube-system          cilium-envoy-h27gq                           1/1     Running     0          26m
# kube-system          cilium-nsbrf                                 1/1     Running     0          2m8s
# kube-system          cilium-operator-867f8dc978-b4vzf             1/1     Running     0          26m
# kube-system          clustermesh-apiserver-5cf45db9cc-6jfgr       2/2     Running     0          9m4s
# kube-system          clustermesh-apiserver-generate-certs-ndvhh   0/1     Completed   0          2m11s
# kube-system          coredns-674b8bbfcf-v88m6                     1/1     Running     0          36m
# kube-system          coredns-674b8bbfcf-xbgl2                     1/1     Running     0          36m
# kube-system          etcd-west-control-plane                      1/1     Running     0          37m
# kube-system          kube-apiserver-west-control-plane            1/1     Running     0          37m
# kube-system          kube-controller-manager-west-control-plane   1/1     Running     0          37m
# kube-system          kube-scheduler-west-control-plane            1/1     Running     0          37m
# local-path-storage   local-path-provisioner-7dc846544d-j2pbf      1/1     Running     0          36m
# NAMESPACE            NAME                                         READY   STATUS      RESTARTS   AGE
# kube-system          cilium-62jps                                 1/1     Running     0          2m1s
# kube-system          cilium-dspkc                                 1/1     Running     0          2m1s
# kube-system          cilium-envoy-6lrpv                           1/1     Running     0          26m
# kube-system          cilium-envoy-n29n5                           1/1     Running     0          26m
# kube-system          cilium-operator-955765ddf-96p95              1/1     Running     0          26m
# kube-system          clustermesh-apiserver-5cf45db9cc-j4ssr       2/2     Running     0          8m35s
# kube-system          clustermesh-apiserver-generate-certs-9wbtr   0/1     Completed   0          2m3s
# kube-system          coredns-674b8bbfcf-2w6pb                     1/1     Running     0          37m
# kube-system          coredns-674b8bbfcf-xzdx8                     1/1     Running     0          37m
# kube-system          etcd-east-control-plane                      1/1     Running     0          38m
# kube-system          kube-apiserver-east-control-plane            1/1     Running     0          38m
# kube-system          kube-controller-manager-east-control-plane   1/1     Running     0          38m
# kube-system          kube-scheduler-east-control-plane            1/1     Running     0          38m
# local-path-storage   local-path-provisioner-7dc846544d-qzfrg      1/1     Running     0          37m

########################################################
# Cilium Status 확인 (ClusterMesh: OK) 가 추가됨
########################################################
cilium status --context kind-west
#     /¯¯\
#  /¯¯\__/¯¯\    Cilium:             OK
#  \__/¯¯\__/    Operator:           OK
#  /¯¯\__/¯¯\    Envoy DaemonSet:    OK
#  \__/¯¯\__/    Hubble Relay:       disabled
#     \__/       ClusterMesh:        OK

# DaemonSet              cilium                   Desired: 2, Ready: 2/2, Available: 2/2
# DaemonSet              cilium-envoy             Desired: 2, Ready: 2/2, Available: 2/2
# Deployment             cilium-operator          Desired: 1, Ready: 1/1, Available: 1/1
# Deployment             clustermesh-apiserver    Desired: 1, Ready: 1/1, Available: 1/1
# Containers:            cilium                   Running: 2
#                        cilium-envoy             Running: 2
#                        cilium-operator          Running: 1
#                        clustermesh-apiserver    Running: 1
#                        hubble-relay
# Cluster Pods:          4/4 managed by Cilium
# Helm chart version:    1.17.6
# Image versions         cilium                   quay.io/cilium/cilium:v1.17.6@sha256:544de3d4fed7acba72758413812780a4972d47c39035f2a06d6145d8644a3353: 2
#                        cilium-envoy             quay.io/cilium/cilium-envoy:v1.33.4-1752151664-7c2edb0b44cf95f326d628b837fcdd845102ba68@sha256:318eff387835ca2717baab42a84f35a83a5f9e7d519253df87269f80b9ff0171: 2
#                        cilium-operator          quay.io/cilium/operator-generic:v1.17.6@sha256:91ac3bf7be7bed30e90218f219d4f3062a63377689ee7246062fa0cc3839d096: 1
#                        clustermesh-apiserver    quay.io/cilium/clustermesh-apiserver:v1.17.6@sha256:f619e97432db427e1511bf91af3be8ded418c53a353a09629e04c5880659d1df: 2

cilium status --context kind-east
#     /¯¯\
#  /¯¯\__/¯¯\    Cilium:             OK
#  \__/¯¯\__/    Operator:           OK
#  /¯¯\__/¯¯\    Envoy DaemonSet:    OK
#  \__/¯¯\__/    Hubble Relay:       disabled
#     \__/       ClusterMesh:        OK

# DaemonSet              cilium                   Desired: 2, Ready: 2/2, Available: 2/2
# DaemonSet              cilium-envoy             Desired: 2, Ready: 2/2, Available: 2/2
# Deployment             cilium-operator          Desired: 1, Ready: 1/1, Available: 1/1
# Deployment             clustermesh-apiserver    Desired: 1, Ready: 1/1, Available: 1/1
# Containers:            cilium                   Running: 2
#                        cilium-envoy             Running: 2
#                        cilium-operator          Running: 1
#                        clustermesh-apiserver    Running: 1
#                        hubble-relay
# Cluster Pods:          4/4 managed by Cilium
# Helm chart version:    1.17.6
# Image versions         cilium                   quay.io/cilium/cilium:v1.17.6@sha256:544de3d4fed7acba72758413812780a4972d47c39035f2a06d6145d8644a3353: 2
#                        cilium-envoy             quay.io/cilium/cilium-envoy:v1.33.4-1752151664-7c2edb0b44cf95f326d628b837fcdd845102ba68@sha256:318eff387835ca2717baab42a84f35a83a5f9e7d519253df87269f80b9ff0171: 2
#                        cilium-operator          quay.io/cilium/operator-generic:v1.17.6@sha256:91ac3bf7be7bed30e90218f219d4f3062a63377689ee7246062fa0cc3839d096: 1
#                        clustermesh-apiserver    quay.io/cilium/clustermesh-apiserver:v1.17.6@sha256:f619e97432db427e1511bf91af3be8ded418c53a353a09629e04c5880659d1df: 2

########################################################
# Cilium Status 확인 (--verbose)
########################################################
kwest exec -it -n kube-system ds/cilium -- cilium status --verbose
keast exec -it -n kube-system ds/cilium -- cilium status --verbose
# ClusterMesh:   1/1 remote clusters ready, 0 global-services
#    east: ready, 2 nodes, 4 endpoints, 3 identities, 0 services, 0 MCS-API service exports, 0 reconnections (last: never)
#    └  etcd: 1/1 connected, leases=0, lock leases=0, has-quorum=true: endpoint status checks are disabled, ID: c6ba18866da7dfd8
#    └  remote configuration: expected=true, retrieved=true, cluster-id=2, kvstoremesh=false, sync-canaries=true, service-exports=disabled
#    └  synchronization status: nodes=true, endpoints=true, identities=true, services=true

########################################################
# (west) Helm Value 확인
########################################################
helm get values -n kube-system cilium --kube-context kind-west
# USER-SUPPLIED VALUES:
# autoDirectNodeRoutes: true
# bpf:
#   masquerade: true
# cluster:
#   id: 1
#   name: west
# clustermesh:
#   apiserver:
#     kvstoremesh:
#       enabled: false
#     service:
#       type: NodePort
#     tls:
#       auto:
#         enabled: true
#         method: cronJob
#         schedule: 0 0 1 */4 *
#   config:
#     clusters:
#     - ips:
#       - 172.18.0.3
#       name: east
#       port: 32379
#     enabled: true
#   useAPIServer: true
# debug:
#   enabled: true
# endpointHealthChecking:
#   enabled: false
# healthChecking: false
# ipMasqAgent:
#   config:
#     nonMasqueradeCIDRs:
#     - 10.1.0.0/16
#   enabled: true
# ipam:
#   mode: kubernetes
# ipv4NativeRoutingCIDR: 10.0.0.0/16
# k8sServiceHost: 172.18.0.4
# k8sServicePort: 6443
# kubeProxyReplacement: true
# operator:
#   replicas: 1
# routingMode: native

########################################################
# (east) Helm Value 확인
########################################################
helm get values -n kube-system cilium --kube-context kind-east
# USER-SUPPLIED VALUES:
# autoDirectNodeRoutes: true
# bpf:
#   masquerade: true
# cluster:
#   id: 2
#   name: east
# clustermesh:
#   apiserver:
#     kvstoremesh:
#       enabled: false
#     service:
#       type: NodePort
#     tls:
#       auto:
#         enabled: true
#         method: cronJob
#         schedule: 0 0 1 */4 *
#   config:
#     clusters:
#     - ips:
#       - 172.18.0.4
#       name: west
#       port: 32379
#     enabled: true
#   useAPIServer: true
# debug:
#   enabled: true
# endpointHealthChecking:
#   enabled: false
# healthChecking: false
# ipMasqAgent:
#   config:
#     nonMasqueradeCIDRs:
#     - 10.0.0.0/16
#   enabled: true
# ipam:
#   mode: kubernetes
# ipv4NativeRoutingCIDR: 10.1.0.0/16
# k8sServiceHost: 172.18.0.3
# k8sServicePort: 6443
# kubeProxyReplacement: true
# operator:
#   replicas: 1
# routingMode: native

########################################################
# 라우팅 정보 확인: Cluster간 PodCIDR 라우팅 주입 확인 (ClusterMesh로 연결된 Cluster와 통신에 필요한 라우팅 경로가 추가됨)
########################################################
docker exec -it west-control-plane ip -c route
docker exec -it west-worker ip -c route
docker exec -it east-control-plane ip -c route
docker exec -it east-worker ip -c route
# default via 172.18.0.1 dev eth0
# 10.0.0.0/24 via 10.0.0.95 dev cilium_host proto kernel src 10.0.0.95
# 10.0.0.95 dev cilium_host proto kernel scope link
# 10.0.1.0/24 via 172.18.0.5 dev eth0 proto kernel
# 10.1.0.0/24 via 172.18.0.3 dev eth0 proto kernel
# 10.1.1.0/24 via 172.18.0.2 dev eth0 proto kernel
# 172.18.0.0/16 dev eth0 proto kernel scope link src 172.18.0.4
# default via 172.18.0.1 dev eth0
# 10.0.0.0/24 via 172.18.0.4 dev eth0 proto kernel
# 10.0.1.0/24 via 10.0.1.218 dev cilium_host proto kernel src 10.0.1.218
# 10.0.1.218 dev cilium_host proto kernel scope link
# 10.1.0.0/24 via 172.18.0.3 dev eth0 proto kernel
# 10.1.1.0/24 via 172.18.0.2 dev eth0 proto kernel
# 172.18.0.0/16 dev eth0 proto kernel scope link src 172.18.0.5
# default via 172.18.0.1 dev eth0
# 10.0.0.0/24 via 172.18.0.4 dev eth0 proto kernel
# 10.0.1.0/24 via 172.18.0.5 dev eth0 proto kernel
# 10.1.0.0/24 via 10.1.0.227 dev cilium_host proto kernel src 10.1.0.227
# 10.1.0.227 dev cilium_host proto kernel scope link
# 10.1.1.0/24 via 172.18.0.2 dev eth0 proto kernel
# 172.18.0.0/16 dev eth0 proto kernel scope link src 172.18.0.3
# default via 172.18.0.1 dev eth0
# 10.0.0.0/24 via 172.18.0.4 dev eth0 proto kernel
# 10.0.1.0/24 via 172.18.0.5 dev eth0 proto kernel
# 10.1.0.0/24 via 172.18.0.3 dev eth0 proto kernel
# 10.1.1.0/24 via 10.1.1.19 dev cilium_host proto kernel src 10.1.1.19
# 10.1.1.19 dev cilium_host proto kernel scope link
# 172.18.0.0/16 dev eth0 proto kernel scope link src 172.18.0.2
```

---

## 6. Hubble Enable

```shell
########################################################
# 설정
########################################################
helm upgrade cilium cilium/cilium --version 1.17.6 --namespace kube-system --reuse-values \
--set hubble.enabled=true --set hubble.relay.enabled=true --set hubble.ui.enabled=true \
--set hubble.ui.service.type=NodePort --set hubble.ui.service.nodePort=30001 --kube-context kind-west
kwest -n kube-system rollout restart ds/cilium

## 혹은 cilium hubble enable --ui --relay --context kind-west
## kubectl --context kind-west patch svc -n kube-system hubble-ui -p '{"spec": {"type": "NodePort", "ports": [{"port": 80, "targetPort": 8081, "nodePort": 30001}]}}'

########################################################
# 설정
########################################################
helm upgrade cilium cilium/cilium --version 1.17.6 --namespace kube-system --reuse-values \
--set hubble.enabled=true --set hubble.relay.enabled=true --set hubble.ui.enabled=true \
--set hubble.ui.service.type=NodePort --set hubble.ui.service.nodePort=31001 --kube-context kind-east
kwest -n kube-system rollout restart ds/cilium

## 혹은 cilium hubble enable --ui --relay --context kind-east
## kubectl --context kind-east patch svc -n kube-system hubble-ui -p '{"spec": {"type": "NodePort", "ports": [{"port": 80, "targetPort": 8081, "nodePort": 31001}]}}'

########################################################
# 확인
########################################################
kwest get svc,ep -n kube-system hubble-ui --context kind-west
keast get svc,ep -n kube-system hubble-ui --context kind-east

########################################################
# hubble-ui 접속
########################################################
http://localhost:30001 #(kind-west)
http://localhost:31001 #(kind-east)
```

---

## 7. west <-> east Cluster Pod 간 통신 확인

```shell
########################################################
# Test Pod 생성
########################################################
cat << EOF | kubectl apply --context kind-west -f -
apiVersion: v1
kind: Pod
metadata:
  name: curl-pod
  labels:
    app: curl
spec:
  containers:
  - name: curl
    image: nicolaka/netshoot
    command: ["tail"]
    args: ["-f", "/dev/null"]
  terminationGracePeriodSeconds: 0
EOF

cat << EOF | kubectl apply --context kind-east -f -
apiVersion: v1
kind: Pod
metadata:
  name: curl-pod
  labels:
    app: curl
spec:
  containers:
  - name: curl
    image: nicolaka/netshoot
    command: ["tail"]
    args: ["-f", "/dev/null"]
  terminationGracePeriodSeconds: 0
EOF


########################################################
# 확인
########################################################
kwest get pod -A && keast get pod -A
kwest get pod -owide && keast get pod -owide
# NAME       READY   STATUS    RESTARTS   AGE     IP           NODE          NOMINATED NODE   READINESS GATES
# curl-pod   1/1     Running   0          2m30s   10.0.1.105   west-worker   <none>           <none>
# NAME       READY   STATUS    RESTARTS   AGE     IP           NODE          NOMINATED NODE   READINESS GATES
# curl-pod   1/1     Running   0          2m29s   10.1.1.153   east-worker   <none>           <none>

########################################################
# hubble-ui 접속 (default namespace)
########################################################
http://localhost:30001 #(kind-west)
http://localhost:31001 #(kind-east)

########################################################
# 통신 확인 west -> east
########################################################
kubectl exec -it curl-pod --context kind-west -- ping -c 1 10.1.1.153
# PING 10.1.1.153 (10.1.1.153) 56(84) bytes of data.
# 64 bytes from 10.1.1.153: icmp_seq=1 ttl=62 time=0.156 ms

# --- 10.1.1.153 ping statistics ---
# 1 packets transmitted, 1 received, 0% packet loss, time 0ms
# rtt min/avg/max/mdev = 0.156/0.156/0.156/0.000 ms

########################################################
# 통신 확인 east -> west
########################################################
kubectl exec -it curl-pod --context kind-east -- ping 10.0.1.105
# PING 10.0.1.105 (10.0.1.105) 56(84) bytes of data.
# 64 bytes from 10.0.1.105: icmp_seq=1 ttl=64 time=0.023 ms
# 64 bytes from 10.0.1.105: icmp_seq=2 ttl=64 time=0.034 ms
# ...

########################################################
# 목적지 파드에서 tcpdump 로 확인 -> NAT 없이 직접 라우팅.
########################################################
kubectl exec -it curl-pod --context kind-west -- tcpdump -i eth0 -nn
# tcpdump: verbose output suppressed, use -v[v]... for full protocol decode
# listening on eth0, link-type EN10MB (Ethernet), snapshot length 262144 bytes
# 14:30:34.788988 IP6 fe80::507a:bdff:fe46:899c > ff02::2: ICMP6, router solicitation, length 16
# 14:31:00.908882 IP 10.0.1.105.60538 > 10.0.0.161.53: 29492+ A? 10.0.1.105kubectl.default.svc.cluster.local. (61)
# 14:31:00.909503 IP 10.0.0.161.53 > 10.0.1.105.60538: 29492 NXDomain*- 0/1/0 (154)
# 14:31:00.909655 IP 10.0.1.105.42896 > 10.0.0.23.53: 32562+ A? 10.0.1.105kubectl.svc.cluster.local. (53)
# 14:31:00.910372 IP 10.0.0.23.53 > 10.0.1.105.42896: 32562 NXDomain*- 0/1/0 (146)
# 14:31:00.910506 IP 10.0.1.105.36278 > 10.0.0.161.53: 686+ A? 10.0.1.105kubectl.cluster.local. (49)
# 14:31:00.910745 IP 10.0.0.161.53 > 10.0.1.105.36278: 686 NXDomain*- 0/1/0 (142)
# 14:31:00.910816 IP 10.0.1.105.59107 > 10.0.0.23.53: 48981+ A? 10.0.1.105kubectl. (35)
# 14:31:02.914138 IP 10.0.0.23.53 > 10.0.1.105.59107: 48981 ServFail- 0/0/0 (35)
# 14:31:02.914155 IP 10.0.1.105 > 10.0.0.23: ICMP 10.0.1.105 udp port 59107 unreachable, length 71
# 14:31:02.966269 IP 10.1.1.153 > 10.0.1.105: ICMP echo request, id 8, seq 1, length 64
# 14:31:02.966282 IP 10.0.1.105 > 10.1.1.153: ICMP echo reply, id 8, seq 1, length 64


########################################################
# 목적지 k8s 노드에서 icmp tcpdump 로 확인 : 다른곳 경유하지 않고 직접 노드에서 파드로 인입 확인
########################################################
docker exec -it west-control-plane tcpdump -i any icmp -nn
docker exec -it west-worker tcpdump -i any icmp -nn
```

![West -> East 통신 확인](/assets/img/kubernetes/cilium/5w-cluster-mesh-hubble.webp)

---

## 8. Load-balancing & Service Discovery

이제 Cluster Mesh 환경에서 **Global Service**를 생성해보겠습니다. `west` Cluster와 `east` Cluster 각각에 동일한 `webpod` Deployment와 Service를 배포한 뒤, Cilium의 `service.cilium.io/global: "true"` 어노테이션을 활용해 **Cluster 간 서비스 디스커버리 및 로드밸런싱**을 확인하겠습니다.

```shell
########################################################
# (west) Deploy Sample Application 
########################################################
cat << EOF | kubectl apply --context kind-west -f -
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
  annotations:
    service.cilium.io/global: "true"
spec:
  selector:
    app: webpod
  ports:
  - protocol: TCP
    port: 80
    targetPort: 80
  type: ClusterIP
EOF


########################################################
# (east) Deploy Sample Application 
########################################################
cat << EOF | kubectl apply --context kind-east -f -
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
  annotations:
    service.cilium.io/global: "true"
spec:
  selector:
    app: webpod
  ports:
  - protocol: TCP
    port: 80
    targetPort: 80
  type: ClusterIP
EOF

########################################################
# 확인
########################################################
kwest get svc,ep webpod && keast get svc,ep webpod
# Warning: v1 Endpoints is deprecated in v1.33+; use discovery.k8s.io/v1 EndpointSlice
# NAME             TYPE        CLUSTER-IP     EXTERNAL-IP   PORT(S)   AGE
# service/webpod   ClusterIP   10.2.164.148   <none>        80/TCP    2m52s

# NAME               ENDPOINTS                    AGE
# endpoints/webpod   10.0.1.14:80,10.0.1.162:80   2m52s
# Warning: v1 Endpoints is deprecated in v1.33+; use discovery.k8s.io/v1 EndpointSlice
# NAME             TYPE        CLUSTER-IP     EXTERNAL-IP   PORT(S)   AGE
# service/webpod   ClusterIP   10.3.193.106   <none>        80/TCP    2m52s

# NAME               ENDPOINTS                   AGE
# endpoints/webpod   10.1.1.2:80,10.1.1.221:80   2m52s

kwest exec -it -n kube-system ds/cilium -c cilium-agent -- cilium service list --clustermesh-affinity
# ID   Frontend                Service Type   Backend
# 1    10.2.0.1:443/TCP        ClusterIP      1 => 172.18.0.4:6443/TCP (active)
# 2    10.2.234.216:443/TCP    ClusterIP      1 => 172.18.0.4:4244/TCP (active)
# 3    10.2.0.10:53/UDP        ClusterIP      1 => 10.0.0.161:53/UDP (active)
#                                             2 => 10.0.0.23:53/UDP (active)
# 4    10.2.0.10:53/TCP        ClusterIP      1 => 10.0.0.161:53/TCP (active)
#                                             2 => 10.0.0.23:53/TCP (active)
# 5    10.2.0.10:9153/TCP      ClusterIP      1 => 10.0.0.161:9153/TCP (active)
#                                             2 => 10.0.0.23:9153/TCP (active)
# 6    10.2.174.206:2379/TCP   ClusterIP      1 => 10.0.1.234:2379/TCP (active)
# 7    172.18.0.4:32379/TCP    NodePort       1 => 10.0.1.234:2379/TCP (active)
# 8    0.0.0.0:32379/TCP       NodePort       1 => 10.0.1.234:2379/TCP (active)
# 9    10.2.35.127:80/TCP      ClusterIP      1 => 10.0.1.137:4245/TCP (active)
# 10   10.2.122.1:80/TCP       ClusterIP      1 => 10.0.1.118:8081/TCP (active)
# 11   172.18.0.4:30001/TCP    NodePort       1 => 10.0.1.118:8081/TCP (active)
# 12   0.0.0.0:30001/TCP       NodePort       1 => 10.0.1.118:8081/TCP (active)
# 13   10.2.164.148:80/TCP     ClusterIP      1 => 10.0.1.14:80/TCP (active)
#                                             2 => 10.1.1.2:80/TCP (active)
#                                             3 => 10.0.1.162:80/TCP (active)
#                                             4 => 10.1.1.221:80/TCP (active)

keast exec -it -n kube-system ds/cilium -c cilium-agent -- cilium service list --clustermesh-affinity
# ID   Frontend                Service Type   Backend
# 1    10.3.0.1:443/TCP        ClusterIP      1 => 172.18.0.3:6443/TCP (active)
# 2    10.3.133.59:443/TCP     ClusterIP      1 => 172.18.0.2:4244/TCP (active)
# 3    10.3.0.10:53/TCP        ClusterIP      1 => 10.1.1.36:53/TCP (active)
#                                             2 => 10.1.1.124:53/TCP (active)
# 4    10.3.0.10:9153/TCP      ClusterIP      1 => 10.1.1.36:9153/TCP (active)
#                                             2 => 10.1.1.124:9153/TCP (active)
# 5    10.3.0.10:53/UDP        ClusterIP      1 => 10.1.1.36:53/UDP (active)
#                                             2 => 10.1.1.124:53/UDP (active)
# 6    10.3.176.230:2379/TCP   ClusterIP      1 => 10.1.1.44:2379/TCP (active)
# 7    172.18.0.2:32379/TCP    NodePort       1 => 10.1.1.44:2379/TCP (active)
# 8    0.0.0.0:32379/TCP       NodePort       1 => 10.1.1.44:2379/TCP (active)
# 9    10.3.20.187:80/TCP      ClusterIP      1 => 10.1.1.3:4245/TCP (active)
# 10   10.3.239.8:80/TCP       ClusterIP      1 => 10.1.1.81:8081/TCP (active)
# 11   172.18.0.2:31001/TCP    NodePort       1 => 10.1.1.81:8081/TCP (active)
# 12   0.0.0.0:31001/TCP       NodePort       1 => 10.1.1.81:8081/TCP (active)
# 13   10.3.193.106:80/TCP     ClusterIP      1 => 10.0.1.14:80/TCP (active)
#                                             2 => 10.1.1.2:80/TCP (active)
#                                             3 => 10.0.1.162:80/TCP (active)
#                                             4 => 10.1.1.221:80/TCP (active)

kwest describe svc webpod | grep Annotations -A1
# Annotations:              service.cilium.io/global: true
# Selector:                 app=webpod

keast describe svc webpod | grep Annotations -A1
# Annotations:              service.cilium.io/global: true
# Selector:                 app=webpod

########################################################
# Hubble 관측을 위해 반복적으로 Curl 요청 (다른 터미널 2개 사용)
########################################################
kubectl exec -it curl-pod --context kind-west -- sh -c 'while true; do curl -s --connect-timeout 1 webpod ; sleep 1; echo "---"; done;'
kubectl exec -it curl-pod --context kind-east -- sh -c 'while true; do curl -s --connect-timeout 1 webpod ; sleep 1; echo "---"; done;'

########################################################
# (west) 로컬 Cluster의 webpod 의 replicas를 0으로 줄인 후 service 호출 통신 확인
########################################################
kwest scale deployment webpod --replicas 0
# deployment.apps/webpod scaled

kwest exec -it -n kube-system ds/cilium -c cilium-agent -- cilium service list --clustermesh-affinity
# ID   Frontend                Service Type   Backend                             
# ...
# 13   10.2.164.148:80/TCP     ClusterIP      1 => 10.1.1.2:80/TCP (active)       
#                                             2 => 10.1.1.221:80/TCP (active)  

keast exec -it -n kube-system ds/cilium -c cilium-agent -- cilium service list --clustermesh-affinity
# ID   Frontend                Service Type   Backend                             
# ...
# 13   10.3.193.106:80/TCP     ClusterIP      1 => 10.1.1.2:80/TCP (active)       
#                                             2 => 10.1.1.221:80/TCP (active) 

kubectl get pod --context kind-west
# NAME       READY   STATUS    RESTARTS   AGE
# curl-pod   1/1     Running   0          34m

kubectl get endpoints --context kind-west             
# Warning: v1 Endpoints is deprecated in v1.33+; use discovery.k8s.io/v1 EndpointSlice
# NAME         ENDPOINTS         AGE
# kubernetes   172.18.0.4:6443   145m
# webpod       <none>            23m

kubectl exec -it curl-pod --context kind-west -- sh -c 'while true; do curl -s --connect-timeout 1 webpod ; sleep 1; echo "---"; done;'

Hostname: webpod-697b545f57-xdg89
IP: 127.0.0.1
IP: ::1
IP: 10.1.1.2
IP: fe80::202f:c5ff:fed3:21c4
RemoteAddr: 10.0.1.105:60758
GET / HTTP/1.1
Host: webpod
User-Agent: curl/8.14.1
Accept: */*
```

![Hubble Observe WebPod Communication2](/assets/img/kubernetes/cilium/5w-cluster-mesh-service-communication2.webp)
![Hubble Observe WebPod Communication](/assets/img/kubernetes/cilium/5w-cluster-mesh-service-communication.webp)

위와 같이 두 Cluster에 동일한 Service가 생성되고, `service.cilium.io/global: "true"` Annotation을 서비스에 추가하면 Cilium이 이를 글로벌 서비스로 인식합니다. `kwest exec -it -n kube-system ds/cilium -c cilium-agent -- cilium service list --clustermesh-affinity` 명령어의 결과를 통해 Service의 Backend에 west에 존재하는 webpod와 east에 존재하는 webpod의 Endpoint가 모두 추가된 것을 확인하였습니다.  

curl pod를 사용해 실제 통신을 하게 되면 위 사진과 같이 Hubble 에서 각 Cluster에 존재하는 webpod와 모두 통신하고 있는 것을 더 명확하게 확인할 수 있습니다. 또한 자신의 Cluster에 해당 service의 pod가 존재하지 않을 때 다른 Cluster에 존재하는 pod로 요청을 하는 것도 알 수 있습니다.

---

## 9. Service Affinity & Shared

Cluster Mesh의 Global Service는 기본적으로 모든 Cluster의 Endpoint를 Backend로 등록해 라운드로빈 방식으로 트래픽을 분산시킵니다. 하지만 운영 환경에서는 트래픽을 로컬 우선(local affinity) 혹은 원격(remote affinity) 으로 제한하거나, 특정 Cluster에서 서비스 공유 여부(shared) 를 제어해야 할 때가 있습니다.

이를 위해 Cilium은 다음과 같은 Service Annotation을 제공합니다.

### 9.1. service.cilium.io/affinity

- `remote`: 로컬 Cluster에 Endpoint가 있더라도 원격 Cluster의 Endpoint로 우선 트래픽을 보냄
- `local`: 로컬 Cluster에 Endpoint가 있으면 무조건 로컬만 사용

```shell
########################################################
# Replicas 원복
########################################################
kwest scale deployment webpod --replicas 2
keast scale deployment webpod --replicas 2

########################################################
# 현재 설정 상태 확인
########################################################
kwest exec -it -n kube-system ds/cilium -c cilium-agent -- cilium service list --clustermesh-affinity
# ID   Frontend                Service Type   Backend                             
# 1    10.2.0.1:443/TCP        ClusterIP      1 => 172.18.0.4:6443/TCP (active)   
# 2    10.2.234.216:443/TCP    ClusterIP      1 => 172.18.0.4:4244/TCP (active)   
# 3    10.2.0.10:53/UDP        ClusterIP      1 => 10.0.0.161:53/UDP (active)     
#                                             2 => 10.0.0.23:53/UDP (active)      
# 4    10.2.0.10:53/TCP        ClusterIP      1 => 10.0.0.161:53/TCP (active)     
#                                             2 => 10.0.0.23:53/TCP (active)      
# 5    10.2.0.10:9153/TCP      ClusterIP      1 => 10.0.0.161:9153/TCP (active)   
#                                             2 => 10.0.0.23:9153/TCP (active)    
# 6    10.2.174.206:2379/TCP   ClusterIP      1 => 10.0.1.234:2379/TCP (active)   
# 7    172.18.0.4:32379/TCP    NodePort       1 => 10.0.1.234:2379/TCP (active)   
# 8    0.0.0.0:32379/TCP       NodePort       1 => 10.0.1.234:2379/TCP (active)   
# 9    10.2.35.127:80/TCP      ClusterIP      1 => 10.0.1.137:4245/TCP (active)   
# 10   10.2.122.1:80/TCP       ClusterIP      1 => 10.0.1.118:8081/TCP (active)   
# 11   172.18.0.4:30001/TCP    NodePort       1 => 10.0.1.118:8081/TCP (active)   
# 12   0.0.0.0:30001/TCP       NodePort       1 => 10.0.1.118:8081/TCP (active)   
# 13   10.2.164.148:80/TCP     ClusterIP      1 => 10.1.1.2:80/TCP (active)       
#                                             2 => 10.1.1.221:80/TCP (active)     
#                                             3 => 10.0.1.171:80/TCP (active)     
#                                             4 => 10.0.1.46:80/TCP (active)   
keast exec -it -n kube-system ds/cilium -c cilium-agent -- cilium service list --clustermesh-affinity
# ID   Frontend                Service Type   Backend                             
# 1    10.3.0.1:443/TCP        ClusterIP      1 => 172.18.0.3:6443/TCP (active)   
# 2    10.3.133.59:443/TCP     ClusterIP      1 => 172.18.0.2:4244/TCP (active)   
# 3    10.3.0.10:53/TCP        ClusterIP      1 => 10.1.1.36:53/TCP (active)      
#                                             2 => 10.1.1.124:53/TCP (active)     
# 4    10.3.0.10:9153/TCP      ClusterIP      1 => 10.1.1.36:9153/TCP (active)    
#                                             2 => 10.1.1.124:9153/TCP (active)   
# 5    10.3.0.10:53/UDP        ClusterIP      1 => 10.1.1.36:53/UDP (active)      
#                                             2 => 10.1.1.124:53/UDP (active)     
# 6    10.3.176.230:2379/TCP   ClusterIP      1 => 10.1.1.44:2379/TCP (active)    
# 7    172.18.0.2:32379/TCP    NodePort       1 => 10.1.1.44:2379/TCP (active)    
# 8    0.0.0.0:32379/TCP       NodePort       1 => 10.1.1.44:2379/TCP (active)    
# 9    10.3.20.187:80/TCP      ClusterIP      1 => 10.1.1.3:4245/TCP (active)     
# 10   10.3.239.8:80/TCP       ClusterIP      1 => 10.1.1.81:8081/TCP (active)    
# 11   172.18.0.2:31001/TCP    NodePort       1 => 10.1.1.81:8081/TCP (active)    
# 12   0.0.0.0:31001/TCP       NodePort       1 => 10.1.1.81:8081/TCP (active)    
# 13   10.3.193.106:80/TCP     ClusterIP      1 => 10.1.1.2:80/TCP (active)       
#                                             2 => 10.1.1.221:80/TCP (active)     
#                                             3 => 10.0.1.171:80/TCP (active)     
#                                             4 => 10.0.1.46:80/TCP (active)  
kwest describe svc webpod | grep Annotations -A3
# Annotations:              service.cilium.io/global: true
# Selector:                 app=webpod
# Type:                     ClusterIP
# IP Family Policy:         SingleStack
keast describe svc webpod | grep Annotations -A3
# Annotations:              service.cilium.io/global: true
# Selector:                 app=webpod
# Type:                     ClusterIP
# IP Family Policy:         SingleStack


########################################################
# remote 설정
########################################################
kwest annotate service webpod service.cilium.io/affinity=remote --overwrite
# Annotations:              service.cilium.io/affinity: remote
#                           service.cilium.io/global: true
# Selector:                 app=webpod
# Type:                     ClusterIP
keast annotate service webpod service.cilium.io/affinity=remote --overwrite
# Annotations:              service.cilium.io/affinity: remote
#                           service.cilium.io/global: true
# Selector:                 app=webpod
# Type:                     ClusterIP

########################################################
# affinity 확인 (preferred)
########################################################
kwest exec -it -n kube-system ds/cilium -c cilium-agent -- cilium service list --clustermesh-affinity

ID   Frontend                Service Type   Backend                                       
1    10.2.0.1:443/TCP        ClusterIP      1 => 172.18.0.4:6443/TCP (active)             
2    10.2.234.216:443/TCP    ClusterIP      1 => 172.18.0.4:4244/TCP (active)             
3    10.2.0.10:53/UDP        ClusterIP      1 => 10.0.0.161:53/UDP (active)               
                                            2 => 10.0.0.23:53/UDP (active)                
4    10.2.0.10:53/TCP        ClusterIP      1 => 10.0.0.161:53/TCP (active)               
                                            2 => 10.0.0.23:53/TCP (active)                
5    10.2.0.10:9153/TCP      ClusterIP      1 => 10.0.0.161:9153/TCP (active)             
                                            2 => 10.0.0.23:9153/TCP (active)              
6    10.2.174.206:2379/TCP   ClusterIP      1 => 10.0.1.234:2379/TCP (active)             
7    172.18.0.4:32379/TCP    NodePort       1 => 10.0.1.234:2379/TCP (active)             
8    0.0.0.0:32379/TCP       NodePort       1 => 10.0.1.234:2379/TCP (active)             
9    10.2.35.127:80/TCP      ClusterIP      1 => 10.0.1.137:4245/TCP (active)             
10   10.2.122.1:80/TCP       ClusterIP      1 => 10.0.1.118:8081/TCP (active)             
11   172.18.0.4:30001/TCP    NodePort       1 => 10.0.1.118:8081/TCP (active)             
12   0.0.0.0:30001/TCP       NodePort       1 => 10.0.1.118:8081/TCP (active)             
13   10.2.164.148:80/TCP     ClusterIP      1 => 10.1.1.2:80/TCP (active) (preferred)     
                                            2 => 10.1.1.221:80/TCP (active) (preferred)   
                                            3 => 10.0.1.171:80/TCP (active)               
                                            4 => 10.0.1.46:80/TCP (active)   

keast exec -it -n kube-system ds/cilium -c cilium-agent -- cilium service list --clustermesh-affinity

ID   Frontend                Service Type   Backend                                       
1    10.3.0.1:443/TCP        ClusterIP      1 => 172.18.0.3:6443/TCP (active)             
2    10.3.133.59:443/TCP     ClusterIP      1 => 172.18.0.2:4244/TCP (active)             
3    10.3.0.10:53/TCP        ClusterIP      1 => 10.1.1.36:53/TCP (active)                
                                            2 => 10.1.1.124:53/TCP (active)               
4    10.3.0.10:9153/TCP      ClusterIP      1 => 10.1.1.36:9153/TCP (active)              
                                            2 => 10.1.1.124:9153/TCP (active)             
5    10.3.0.10:53/UDP        ClusterIP      1 => 10.1.1.36:53/UDP (active)                
                                            2 => 10.1.1.124:53/UDP (active)               
6    10.3.176.230:2379/TCP   ClusterIP      1 => 10.1.1.44:2379/TCP (active)              
7    172.18.0.2:32379/TCP    NodePort       1 => 10.1.1.44:2379/TCP (active)              
8    0.0.0.0:32379/TCP       NodePort       1 => 10.1.1.44:2379/TCP (active)              
9    10.3.20.187:80/TCP      ClusterIP      1 => 10.1.1.3:4245/TCP (active)               
10   10.3.239.8:80/TCP       ClusterIP      1 => 10.1.1.81:8081/TCP (active)              
11   172.18.0.2:31001/TCP    NodePort       1 => 10.1.1.81:8081/TCP (active)              
12   0.0.0.0:31001/TCP       NodePort       1 => 10.1.1.81:8081/TCP (active)              
13   10.3.193.106:80/TCP     ClusterIP      1 => 10.1.1.2:80/TCP (active)                 
                                            2 => 10.1.1.221:80/TCP (active)               
                                            3 => 10.0.1.171:80/TCP (active) (preferred)   
                                            4 => 10.0.1.46:80/TCP (active) (preferred)  
```

![Cluster Mesh Service Affinity](/assets/img/kubernetes/cilium/5w-cluster-mesh-service-affinity.webp)

`remote`로 설정 시, `west`에 Pod가 있어도 `east`의 Pod를 우선적으로 호출함을 curl 테스트로 확인할 수 있습니다. 또한 반대로 `service.cilium.io/affinity=local`과 같이 `remote`가 아닌 `local`로 설정하면 본인이 속한 Cluster의 Pod만 호출하는 것을 알 수 있습니다. 다만 `remote`로 설정하더라도 원격 Cluster의 Endpoint가 모두 사라진 경우에는 요청이 실패하지 않고, 자동으로 로컬 Pod로 트래픽이 전달됩니다. 운영 환경에서는 Affinity 전략과 Pod 배치 정책을 함께 고려하여 트래픽 흐름을 설계하는 것이 중요합니다.

### 9.2. service.cilium.io/shared

- `true` (기본값): 해당 Service는 Cluster Mesh에 공유
- `false`: 해당 Cluster의 Service는 Mesh에서 제외되어, 다른 Cluster에서 접근 불가

```shell
# 현재 설정 상태 확인
kwest exec -it -n kube-system ds/cilium -c cilium-agent -- cilium service list --clustermesh-affinity
keast exec -it -n kube-system ds/cilium -c cilium-agent -- cilium service list --clustermesh-affinity

# shared=false 설정
kwest annotate service webpod service.cilium.io/shared=false
```

shared=false로 설정하면 west의 Service가 east에 공유되지 않으며, east Cluster에서 해당 Service 호출이 실패합니다.

---

## 10. 마무리

이번 글에서는 Kind 기반의 두 Kubernetes Cluster(`west`, `east`)를 구성하고, Cilium Cluster Mesh를 통해 멀티 Cluster 간 Pod-to-Pod 통신, Global Service, 로드밸런싱, Service Affinity, Shared 옵션까지 단계별로 실습해보았습니다.

실습을 통해 알 수 있었던 핵심 포인트는 다음과 같습니다.

- Cluster Mesh 연결 전에는 각 Cluster의 라우팅 테이블에 상대 Cluster PodCIDR 정보가 없어 통신이 불가능
- Cluster Mesh 연결 후에는 라우팅 경로가 자동 주입되어 Cluster 간 Pod-to-Pod 통신이 가능
- `service.cilium.io/global: "true"` 어노테이션을 통해 Global Service를 선언하면, 두 Cluster의 Pod가 모두 Backend로 등록되어 Round-Robin 방식으로 로드밸런싱이 수행
- `service.cilium.io/affinity=remote` 설정 시 원격 Cluster의 Pod를 우선 호출하지만, Endpoint가 사라지면 자동으로 로컬 Pod로 트래픽이 전달되는 동작을 확인
- `service.cilium.io/shared=false` 설정 시 특정 Cluster의 Service를 Mesh에서 제외하여, 다른 Cluster에서는 접근할 수 없음을 확인

---

## 11. Reference

- [Cilium Docs - Installation Using Kind](https://docs.cilium.io/en/latest/installation/kind/)
- [Cilium Docs - Cluster Mesh](https://docs.cilium.io/en/stable/network/clustermesh/clustermesh/)
- [Cilium Page - Cluster Mesh](https://cilium.io/use-cases/cluster-mesh/)
- [Cilium Docs - Load-balancing & Service Discovery](https://docs.cilium.io/en/stable/network/clustermesh/services/)
- [Cilium Docs - Service Affinity](https://docs.cilium.io/en/latest/network/clustermesh/affinity/)
- [Cilium Docs - Cilium Operator](https://docs.cilium.io/en/stable/internals/cilium_operator/)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
