---
title: Cilium Service LoadBalancer BGP Advertisement & ExternalTrafficPolicy [Cilium Study 5주차]
date: 2025-08-12 00:05:11 +0900
author: kkamji
categories: [Kubernetes, Cilium]
tags: [kubernetes, devops, cilium, cilium-study, bgp, lb-ipam, external-traffic-policy, ecmp, cloudnet, gasida]
comments: true
image:
  path: /assets/img/kubernetes/cilium/cilium.webp
---

지난 글 [Cilium BGP Control Plane [Cilium Study 5주차]]({% post_url 2025/2025-08-11-cilium-bgp-control-plane %})에서는 **PodCIDR 경로를 BGP로 전파**하고, Cilium이 왜 커널 라우팅 테이블을 직접 수정하지 않는지, 그리고 다중 NIC 환경에서 발생하는 문제를 해결하는 방법을 살펴봤습니다.

이번 글에서는 **Service(LoadBalancer) External IP를 BGP로 광고**하는 과정을 살펴보고, `ExternalTrafficPolicy`(Cluster vs Local)에 따른 동작 차이와 **Linux ECMP Hash Policy**가 트래픽 분산/소스IP 보존/연결 안정성에 미치는 영향을 실습을 통해 알아보겠습니다.

![L3 Announcement over BGP](/assets/img/kubernetes/cilium/5w-l3-announcement-over-bgp.webp)

> [ISOVALENT Blog - Migrating from metallb to Cilium](https://isovalent.com/blog/post/migrating-from-metallb-to-cilium/#l3-announcement-over-bgp)  
> [Cilium Docs - LoadBalancer IP Address Management (LB IPAM)](https://docs.cilium.io/en/stable/network/lb-ipam/)  

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
16. [Cilium Service LoadBalancer BGP Advertisement & ExternalTrafficPolicy [Cilium Study 5주차] (현재 글)]({% post_url 2025/2025-08-12-cilium-lb-ipam %})
17. [Kind로 Kubernetes Cluster 배포하기 [Cilium Study 5주차]]({% post_url 2025/2025-08-13-kind %})
18. [Cilium Cluster Mesh [Cilium Study 5주차]]({% post_url 2025/2025-08-14-cilium-cluster-mesh %})
19. [Cilium Service Mesh [Cilium Study 6주차]]({% post_url 2025/2025-08-18-cilium-service-mesh %})
20. [Kube-burner 소개 및 실습 [Cilium Study 7주차]]({% post_url 2025/2025-08-25-kube-burner %})
21. [Cilium Network Security [Cilium Study 8주차]]({% post_url 2025/2025-09-03-cilium-network-security %})

---

## 1. 실습 환경

![Lab Environment](/assets/img/kubernetes/cilium/5w-lab-environment.webp)

- 기본 VM: k8s-ctr, k8s-w1, k8s-w0, router(FRR)
- router: 192.168.10.0/24 ↔ 192.168.20.0/24 라우팅, 클러스터에 join되지 않은 독립 서버, FRR 설치로 BGP 실습 가능 (FRR Docs)
- k8s-w0: 다른 Node와 구분해 192.168.20.0/24 대역에 배치
- Static Routing: Vagrant 스크립트에서 자동 설정됨 [Vagrant Script File](<https://github.com/KKamJi98/cilium-lab/blob/main/vagrant/vagrant-5w/Vagrantfile>)

> FRR-Docs - [FRR-Docs](https://docs.frrouting.org/en/stable-10.4/about.html)

---

## 2. 핵심 개념

- **LB IPAM**
  - Service 타입 `LoadBalancer`에 사용할 외부 IP를 Cilium이 **IP Pool**에서 자동 할당
  - 노드 대역이 아니어도 사용 가능
- **ExternalTrafficPolicy**
  - **Cluster**: 모든 노드가 LoadBalancer의 External-IP를 수신 -> 로컬 파드 없으면 SNAT -> 소스 IP 미보존. 모든 노드가 BGP 광고에 참여
  - **Local**: **로컬 파드가 있는 노드**만 LoadBalancer의 External-IP를 수신 -> 소스 IP 보존. BGP도 해당 노드만 광고
- **ECMP Hash Policy (Linux)**
  - 기본은 **L3 해시**(src/dst IP)
  - `net.ipv4.fib_multipath_hash_policy=1`로 바꾸면 **L4 해시**(IP+포트) -> 흐름 고정성이 높아져 재시도 `RST`/`ENOTCONN`이 줄어듬

---

## 3. Sample Application 배포

```shell
###############################################
## 1. 샘플 애플리케이션 배포
###############################################
# webpod Deployment + Service 배포
cat << EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: webpod
spec:
  replicas: 3
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
                values: ["webpod"]
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

###############################################
## curl-pod 배포 (k8s-ctr에 고정)
###############################################

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

###############################################
## 확인
###############################################
kubectl get po -o wide
# NAME                      READY   STATUS    RESTARTS   AGE   IP             NODE      NOMINATED NODE   READINESS GATES
# curl-pod                  1/1     Running   0          8s    172.20.0.87    k8s-ctr   <none>           <none>
# webpod-5ddff96fcf-29257   1/1     Running   0          8s    172.20.2.229   k8s-w0    <none>           <none>
# webpod-5ddff96fcf-lgfqf   1/1     Running   0          8s    172.20.1.11    k8s-w1    <none>           <none>
# webpod-5ddff96fcf-lqhbb   1/1     Running   0          8s    172.20.0.47    k8s-ctr   <none>           <none>
```

---

## 4. LB IPAM Pool 생성 & Service를 LoadBalancer로 전환

```shell
###############################################
# 1) IP Pool 생성 (노드 대역이 아니어도 됨)
###############################################
cat << EOF | kubectl apply -f -
apiVersion: "cilium.io/v2"
kind: CiliumLoadBalancerIPPool
metadata:
  name: cilium-pool
spec:
  blocks:
  - cidr: "172.16.1.0/24"
EOF

###############################################
# 2) IP Pool 생성 확인
###############################################
kubectl get ippool 
# NAME          DISABLED   CONFLICTING   IPS AVAILABLE   AGE
# cilium-pool   false      False         253             61m

###############################################
# 3) webpod의 Service를 LoadBalancer로 전환
###############################################
kubectl patch svc webpod -p '{"spec": {"type": "LoadBalancer"}}'

###############################################
# 4) webpod의 Service 확인
###############################################
kubectl get svc webpod              
# NAME     TYPE           CLUSTER-IP     EXTERNAL-IP   PORT(S)        AGE
# webpod   LoadBalancer   10.96.170.16   172.16.1.1    80:30247/TCP   3m
```

---

## 5. LoadBalancer의 External-IP BGP 광고 설정

`app=webpod`인 Service의 **LoadBalancerIP만** BGP로 광고하도록 선언합니다.

```shell
###############################################
# 1) CiliumBGPAdvertisement 배포
###############################################
cat << EOF | kubectl apply -f -
apiVersion: cilium.io/v2
kind: CiliumBGPAdvertisement
metadata:
  name: bgp-advertisements-lb-exip-webpod
  labels:
    advertise: bgp
spec:
  advertisements:
    - advertisementType: "Service"
      service:
        addresses:
          - LoadBalancerIP
      selector:             
        matchExpressions:
          - { key: app, operator: In, values: [ webpod ] }
EOF

###############################################
# 2) CiliumBGPAdvertisement 배포 확인
###############################################
kubectl get CiliumBGPAdvertisement
# NAME                                AGE
# bgp-advertisements                  4m
# bgp-advertisements-lb-exip-webpod   7m

###############################################
# 3) 각 노드에서 Cilium BGP 라우터에 광고 가능한 IPv4 유니캐스크 경로 확인 (기존 PodCIDR 경로에 추가로 LoadBalancer IP가 포함됨)
###############################################
cilium bgp routes available ipv4 unicast
# Node      VRouter   Prefix          NextHop   Age      Attrs
# k8s-ctr   65001     172.16.1.1/32   0.0.0.0   8m36s   [{Origin: i} {Nexthop: 0.0.0.0}]   
#           65001     172.20.0.0/24   0.0.0.0   8m36s   [{Origin: i} {Nexthop: 0.0.0.0}]   
# k8s-w0    65001     172.16.1.1/32   0.0.0.0   8m36s   [{Origin: i} {Nexthop: 0.0.0.0}]   
#           65001     172.20.2.0/24   0.0.0.0   8m36s   [{Origin: i} {Nexthop: 0.0.0.0}]   
# k8s-w1    65001     172.16.1.1/32   0.0.0.0   8m23s   [{Origin: i} {Nexthop: 0.0.0.0}]   
#           65001     172.20.1.0/24   0.0.0.0   8m23s   [{Origin: i} {Nexthop: 0.0.0.0}] 
```

---

## 6. LoadBalancer IP로 접속 확인

### 6.1. Service -> Backend Mapping 확인

```shell
kubectl -n kube-system exec ds/cilium -c cilium-agent -- cilium-dbg service list | grep -A6 '172\.16\.1\.1\|webpod'
# 17   172.16.1.1:80/TCP      LoadBalancer   1 => 172.20.0.47:80/TCP (active)        
#                                            2 => 172.20.1.11:80/TCP (active)        
#                                            3 => 172.20.2.229:80/TCP (active)     
```

### 6.2. 통신 확인 (Source IP)

```shell
###############################################
# 1) (k8s-ctr node) LoadBalancer IP 확인
###############################################
LBIP=$(kubectl get svc webpod -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
echo "$LBIP"
# 172.16.1.1

###############################################
# 2) (router node) LoadBalancer IP로 통신 확인
###############################################
LBIP=172.16.1.1
curl -s http://$LBIP | egrep 'Hostname|RemoteAddr'
# Hostname: webpod-5ddff96fcf-29257
# RemoteAddr: 192.168.10.100:49962

curl -s http://$LBIP | egrep 'Hostname|RemoteAddr'
# Hostname: webpod-5ddff96fcf-lqhbb
# RemoteAddr: 192.168.10.101:49970

curl -s http://$LBIP | egrep 'Hostname|RemoteAddr'
# Hostname: webpod-5ddff96fcf-lqhbb
# RemoteAddr: 192.168.20.100:46000

curl -s http://$LBIP | egrep 'Hostname|RemoteAddr'
# Hostname: webpod-5ddff96fcf-lgfqf
# RemoteAddr: 192.168.20.200:53150

###############################################
# 3) (router node) 트래픽 분산 확인
###############################################
for i in {1..50}; do curl -s http://$LBIP | grep Hostname; done | sort | uniq -c | sort -nr
#  19 Hostname: webpod-5ddff96fcf-lqhbb
#  17 Hostname: webpod-5ddff96fcf-lgfqf
#  14 Hostname: webpod-5ddff96fcf-29257
```

> 위의 LoadBalancer의 IP로 Curl 결과를 보면 RemoteAddr이 node, router가 섞여 보이는 것을 확인할 수 있습니다.  
> 해당 차이는 ExternalTrafficPolicy 설정에 크게 영향을 받습니다.  
{: .prompt-tip}

---

## 7. ExternalTrafficPolicy (Cluster vs Local)

![External Policy Cluster vs Local](/assets/img/kubernetes/cilium/5w-external-policy-cluster-vs-local.webp)

### 7.1. Cluster Mode

#### 7.1.1. Cluster Mode의 특징

- **모든 노드**가 LoadBalancer IP로 들어온 요청을 처리(수신)하고, **로컬 파드가 없어도** 다른 노드로 트래픽을 전달합니다.
- 이때 **교차 노드 포워딩**을 위해 수신 노드에서 **SNAT**가 발생 -> **소스 IP 미보존**(Pod에서 보면 `RemoteAddr = 노드 IP`).
- Cilium BGP는 **모든 노드에서 동일 LBIP(/32)**를 광고 -> 라우터는 **ECMP**로 여러 next-hop을 사용합니다.

#### 7.1.2. Cluster Mode 실습

```bash
###############################################
# 1) (k8s-ctr node) 현재 ExternalTrafficPolicy 확인
###############################################
kubectl describe svc webpod | grep -i "External Traffic Policy"
# External Traffic Policy:  Cluster

###############################################
# 2) (k8s-ctr node) webpod replicas 3 -> 2로 감소 및 확인
###############################################
kubectl scale deploy/webpod --replicas=2
# deployment.apps/webpod scaled

kubectl get po -o wide                  
# NAME                      READY   STATUS    RESTARTS   AGE   IP             NODE      NOMINATED NODE   READINESS GATES
# curl-pod                  1/1     Running   0          31m   172.20.0.87    k8s-ctr   <none>           <none>
# webpod-5ddff96fcf-29257   1/1     Running   0          31m   172.20.2.229   k8s-w0    <none>           <none>
# webpod-5ddff96fcf-lgfqf   1/1     Running   0          31m   172.20.1.11    k8s-w1    <none>           <none>

###############################################
# 3) (router node) 트래픽 분포 확인
###############################################
LBIP=172.16.1.1
for i in {1..100};  do curl -s $LBIP | grep Hostname; done | sort | uniq -c | sort -nr
# 55 Hostname: webpod-5ddff96fcf-29257
# 45 Hostname: webpod-5ddff96fcf-lgfqf

###############################################
# 4) (router node) Routing Table 및 BGP 정보 확인 (webpod가 존재하지 않는 k8s-ctr의 IP도 포함이 되어있음)
###############################################
ip -c route | grep 172.16.1.1 -A4
# 172.16.1.1 nhid 37 proto bgp metric 20 
#         nexthop via 192.168.20.100 dev eth2 weight 1 
#         nexthop via 192.168.10.100 dev eth1 weight 1 
#         nexthop via 192.168.10.101 dev eth1 weight 1 
# 172.20.0.0/24 nhid 30 via 192.168.10.100 dev eth1 proto bgp metric 20 

vtysh -c 'show ip bgp'
# BGP table version is 7, local router ID is 192.168.10.200, vrf id 0
# Default local pref 100, local AS 65000
# Status codes:  s suppressed, d damped, h history, * valid, > best, = multipath,
#                i internal, r RIB-failure, S Stale, R Removed
# Nexthop codes: @NNN nexthop's vrf id, < announce-nh-self
# Origin codes:  i - IGP, e - EGP, ? - incomplete
# RPKI validation codes: V valid, I invalid, N Not found

#    Network          Next Hop            Metric LocPrf Weight Path
# *> 10.10.1.0/24     0.0.0.0                  0         32768 i
# *> 172.16.1.1/32    192.168.10.100                         0 65001 i
# *=                  192.168.20.100                         0 65001 i
# *=                  192.168.10.101                         0 65001 i
# *> 172.20.0.0/24    192.168.10.100                         0 65001 i
# *> 172.20.1.0/24    192.168.10.101                         0 65001 i
# *> 172.20.2.0/24    192.168.20.100                         0 65001 i

vtysh -c 'show ip bgp 172.16.1.1/32'
# BGP routing table entry for 172.16.1.1/32, version 7
# Paths: (3 available, best #1, table default)
#   Advertised to non peer-group peers:
#   192.168.10.100 192.168.10.101 192.168.20.100
#   65001
#     192.168.10.100 from 192.168.10.100 (192.168.10.100)
#       Origin IGP, valid, external, multipath, best (Older Path)
#       Last update: Mon Aug 18 23:30:10 2025
#   65001
#     192.168.20.100 from 192.168.20.100 (192.168.20.100)
#       Origin IGP, valid, external, multipath
#       Last update: Mon Aug 18 23:30:10 2025
#   65001
#     192.168.10.101 from 192.168.10.101 (192.168.10.101)
#       Origin IGP, valid, external, multipath
#       Last update: Mon Aug 18 23:30:22 2025
```

> 위의 상태에서는 라우터의 ECMP가 **요청마다**(혹은 짧은 간격의 새 연결마다) 다른 next-hop을 선택할 수 있고, 수신 노드가 **로컬 파드 유무와 무관**하게 처리/포워딩하기 때문에 **Pod에서 관찰되는 `RemoteAddr`이 노드 IP로 보이는 경우가 많습니다.**  
> Linux 기본 ECMP Hash는 **L3**(IP)라서, 요청마다 포트가 달라지면(새 연결) **다른 next-hop**으로 갈 확률이 있습니다. 흐름 고정성이 떨어져 **RST/ENOTCONN**이 관찰되기도 합니다.  
{: .prompt-tip}

### 7.2. Local Mode

#### 7.2.1. Local Mode의 특징

- **로컬 파드가 있는 노드만** LoadBalancer IP 트래픽을 처리함
- **소스 IP를 보존함** (교차 노드 포워딩 없음)
- BGP도 **파드 보유 노드만** LoadBalancer IP를 광고 -> 라우터 ECMP next-hop 수가 줄어 안정적임

#### 7.2.2. Local Mode 실습

```shell
###############################################
# 1) (k8s-ctr node) ExternalTrafficPolicy를 Local로 변경
###############################################
kubectl patch service webpod -p '{"spec":{"externalTrafficPolicy":"Local"}}'

###############################################
# 2) (k8s-ctr node) ExternalTrafficPolicy 변경 확인
###############################################
kubectl describe svc webpod | grep -i "External Traffic Policy"
# External Traffic Policy:  Local

###############################################
# 3) (router node) Routing 정보 확인 (실제 pod가 있는 노드로만 라우팅 3 -> 2)
###############################################
ip -c route | grep 172.16.1.1 -A4
# 172.16.1.1 nhid 45 proto bgp metric 20 
#         nexthop via 192.168.20.100 dev eth2 weight 1 
#         nexthop via 192.168.10.101 dev eth1 weight 1 
# 172.20.0.0/24 nhid 30 via 192.168.10.100 dev eth1 proto bgp metric 20 
# 172.20.1.0/24 nhid 32 via 192.168.10.101 dev eth1 proto bgp metric 20

vtysh -c 'show ip bgp'
# BGP table version is 8, local router ID is 192.168.10.200, vrf id 0
# Default local pref 100, local AS 65000
# Status codes:  s suppressed, d damped, h history, * valid, > best, = multipath,
#                i internal, r RIB-failure, S Stale, R Removed
# Nexthop codes: @NNN nexthop's vrf id, < announce-nh-self
# Origin codes:  i - IGP, e - EGP, ? - incomplete
# RPKI validation codes: V valid, I invalid, N Not found

#    Network          Next Hop            Metric LocPrf Weight Path
# *> 10.10.1.0/24     0.0.0.0                  0         32768 i
# *= 172.16.1.1/32    192.168.20.100                         0 65001 i
# *>                  192.168.10.101                         0 65001 i
# *> 172.20.0.0/24    192.168.10.100                         0 65001 i
# *> 172.20.1.0/24    192.168.10.101                         0 65001 i
# *> 172.20.2.0/24    192.168.20.100                         0 65001 i

# Displayed  5 routes and 6 total paths

vtysh -c 'show ip bgp 172.16.1.1/32'
# BGP routing table entry for 172.16.1.1/32, version 8
# Paths: (2 available, best #2, table default)
#   Advertised to non peer-group peers:
#   192.168.10.100 192.168.10.101 192.168.20.100
#   65001
#     192.168.20.100 from 192.168.20.100 (192.168.20.100)
#       Origin IGP, valid, external, multipath
#       Last update: Mon Aug 18 23:30:11 2025
#   65001
#     192.168.10.101 from 192.168.10.101 (192.168.10.101)
#       Origin IGP, valid, external, multipath, best (Router ID)
#       Last update: Mon Aug 18 23:30:23 2025


###############################################
# 4) (router node) LoadBalancer IP로 curl 했을 때 Source IP 보존 확인
###############################################
curl -s http://$LBIP | egrep 'Hostname|RemoteAddr'
# Hostname: webpod-5ddff96fcf-lgfqf
# RemoteAddr: 192.168.20.200:36846
curl -s http://$LBIP | egrep 'Hostname|RemoteAddr'
# Hostname: webpod-5ddff96fcf-29257
# RemoteAddr: 192.168.20.200:34232
curl -s http://$LBIP | egrep 'Hostname|RemoteAddr'
# Hostname: webpod-5ddff96fcf-lgfqf
# RemoteAddr: 192.168.20.200:34248
curl -s http://$LBIP | egrep 'Hostname|RemoteAddr'
# Hostname: webpod-5ddff96fcf-lgfqf
# RemoteAddr: 192.168.20.200:34264
curl -s http://$LBIP | egrep 'Hostname|RemoteAddr'
# Hostname: webpod-5ddff96fcf-29257
# RemoteAddr: 192.168.20.200:34278
```

> Pod에서 `RemoteAddr`가 **router(192.168.20.200)**로 **실제 소스 IP**로 보이는 것을 확인할 수 있습니다.  
> 라우팅 경로가 줄면서 **RST/ENOTCONN**이 줄어듭니다. (stale nexthop 적음)  
{: .prompt-tip}

---

## 8. ECMP Hash Policy (Router 권장 튜닝)

Linux Kernel의 Default인 L3 ECMP Hash는 같은 IP쌍이라면 포트가 달라도 다른 ECMP path로 흘러갈 수 있습니다. 따라서 하나의 클라이언트가 같은 서버로 여러 연결을 열면, 연결들이 서로 다른 노드로 분산되어 세션 일관성(Flow Affinity)이 깨질 수 있습니다.

반면 튜플 기반인 L4 Hash를 사용하게 되면 L3 Hash(default) 대비 **흐름 고정성**이 올라가서, 새 연결이라도 트래픽이 **동일하게**으로 흘러갑니다. 따라서 Cluster/Local Mode 모두에서 **분산 품질**과 **연결 안정성**이 개선될 수 있습니다.

- **ECMP** (Equal-Cost Multi-Path): 동일 목적지에 대해 동일한 비용(cost)을 가지는 라우트가 여러 개 있을 때, 커널은 이들 중 하나를 선택해 패킷을 전달 (리눅스 커널 기본값 `fib_multipath_hash_policy=0` (L3 Hash))

```bash
###############################################
# 즉시 적용
###############################################
sudo sysctl -w net.ipv4.fib_multipath_hash_policy=1

###############################################
# 영구 적용
###############################################
echo "net.ipv4.fib_multipath_hash_policy=1" | sudo tee -a /etc/sysctl.conf

###############################################
# 확인
###############################################
sysctl net.ipv4.fib_multipath_hash_policy
# net.ipv4.fib_multipath_hash_policy = 1
```

---

## 9. 마무리

- **LB IPAM + BGP**로 **노드 대역과 무관한 LBIP를 /32로 광고**하면, 라우터는 **ECMP**로 각 노드에 트래픽을 분산합니다.
- **ExternalTrafficPolicy**에 따라
  - **Cluster**: **모든 노드 수신 + SNAT(소스IP 미보존)** / nexthop ↑ / 분산 폭 넓음
  - **Local**: **로컬 파드 보유 노드만 수신 + 소스IP 보존** / nexthop ↓ / 안정성↑
- **ECMP Hash를 L4로** 바꾸면 흐름 고정성이 높아져 **RST/ENOTCONN**이 크게 줄어듭니다.

---

## 10. Reference

- [FRR Docs](https://docs.frrouting.org/en/stable-10.4/about.html)
- [ISOVALENT Blog - Migrating from metallb to Cilium](https://isovalent.com/blog/post/migrating-from-metallb-to-cilium/#l3-announcement-over-bgp)  
- [Cilium Docs - LoadBalancer IP Address Management (LB IPAM)](https://docs.cilium.io/en/stable/network/lb-ipam/)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
