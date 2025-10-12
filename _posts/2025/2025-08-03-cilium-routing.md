---
title: Cilium Network Routing 이해하기 – Encapsulation과 Native Routing 비교 [Cilium Study 3주차]
date: 2025-08-03 07:14:41 +0900
author: kkamji
categories: [Kubernetes, Cilium]
tags: [kubernetes, devops, cilium, cilium-study, cloudnet, gasida, routing]
comments: true
image:
  path: /assets/img/kubernetes/cilium/cilium.webp
---

지난 포스트에서는 Cilium의 IPAM Mode에 대해 살펴보았습니다. 이번 글에서는 **Cilium이 제공하는 두 가지 Routing 모델, Encapsulation Mode와 Native Routing Mode를 비교하며 각각의 특징과 장단점을 이해**해보겠습니다. Cilium은 eBPF를 활용하여 클러스터 간 트래픽을 전달하는 방식을 세밀하게 제어할 수 있습니다. 기본값으로는 `VXLAN`/`GENEVE` 기반의 Overlay(Encapsulation) 방식을 사용하지만, 네트워크 환경에 따라 Native Routing을 사용할 수도 있습니다.

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
13. [Cilium Network Routing 이해하기 – Encapsulation과 Native Routing 비교 [Cilium Study 3주차] (현재 글)]({% post_url 2025/2025-08-03-cilium-routing %})
14. [Cilium Native Routing 통신 확인 및 문제 해결 – Static Route & BGP [Cilium Study 4주차]]({% post_url 2025/2025-08-10-cilium-native-routing %})
15. [Cilium BGP Control Plane [Cilium Study 5주차]]({% post_url 2025/2025-08-11-cilium-bgp-control-plane %})
16. [Cilium Service LoadBalancer BGP Advertisement & ExternalTrafficPolicy [Cilium Study 5주차]]({% post_url 2025/2025-08-12-cilium-lb-ipam %})
17. [Kind로 Kubernetes Cluster 배포하기 [Cilium Study 5주차]]({% post_url 2025/2025-08-13-kind %})
18. [Cilium Cluster Mesh [Cilium Study 5주차]]({% post_url 2025/2025-08-14-cilium-cluster-mesh %})
19. [Cilium Service Mesh [Cilium Study 6주차]]({% post_url 2025/2025-08-18-cilium-service-mesh %})
20. [Kube-burner 소개 및 실습 [Cilium Study 7주차]]({% post_url 2025/2025-08-25-kube-burner %})
21. [Cilium Network Security [Cilium Study 8주차]]({% post_url 2025/2025-09-03-cilium-network-security %})

---

## 1. Cilium에서 제공하는 두 가지 Routing Mode

Cilium은 쿠버네티스 클러스터에서 Pod 간 트래픽을 전달하는 데 두 가지 주요 방식의 Routing을 제공합니다. **Encapsulation Mode**는 `VXLAN` 혹은 `GENEVE` 터널을 사용하여 **Overlay Network**를 형성하는 방식이며, **Native Routing Mode**는 기본 네트워크의 Routing 기능을 활용하여 패킷을 전합니다. Pod들이 서로 다른 노드에 존재하는 경우, 각 노드는 자신이 소유하지 않은 Pod IP에 대해 Routing 경로를 갖습니다.

서로 다른 노드에 존재하는 Pod간 통신의 경우 **Encapsulation Mode**에서는 트래픽이 터널을 통해 Encapsulation되어 전달되고, **Native Routing** Mode에서는 Linux Kernel의 Routing Table을 통해 직접 전달됩니다.  

---

## 2. Encapsulation Mode (VXLAN / GENEVE)

Encapsulation Mode는 별도의 설정을 하지 않으면 Cilium이 자동으로 활성화하는 기본 Routing 방식입니다. 클러스터의 모든 노드가 `VXLAN` 또는 `GENEVE`와 같은 UDP 기반 캡슐화 프로토콜을 사용하여 `Tunnel Mesh`를 형성합니다. 모든 노드 간 트래픽은 해당 터널을 통해 캡슐화되어 전달됩니다.

### 2.1. 네트워크 요구사항

- 노드들이 서로 IP/UDP로 통신 가능하다면 추가 Routing 조건은 없음
- IPv6 Only 클러스터에서만 IPv6 언더레이를 사용할 수 있으며, 듀얼 스택 환경은 지원하지 않음
- `Encapsulation`된 패킷을 허용하기 위해 다음 포트가 열려 있어야 함

| 캡슐화 Mode   | 포트 범위/프로토콜 |
| :------------ | :----------------- |
| VXLAN(기본값) | 8472/UDP           |
| GENEVE        | 6081/UDP           |

### 2.2. Encapsulation Mode의 장점

1. **단순성(Simplicity)** – 네트워크가 PodCIDR을 인식할 필요가 없으며, 클러스터 노드는 여러 Routing 또는 링크 레이어 도메인을 생성할 수 있습니다. 네트워크 토폴로지에 관계없이 노드 간 연결만 확보되면 됩니다.
2. **주소 공간(Addressing space)** – 기본 네트워크 제약에 의존하지 않기 때문에 PodCIDR 크기만 충분히 크게 설정하면 노드당 수천 개의 Pod를 실행할 수 있습니다.
3. **자동 구성(Auto-configuration)** – Kubernetes와 함께 실행될 때 노드 목록과 할당 프리픽스가 각 에이전트에 자동으로 전달됩니다. 신규 노드가 추가되면 자동으로 터널 메시에 편입됩니다.
4. **정체성 맥락(Identity context)** – 캡슐화 프로토콜은 패킷에 메타데이터를 함께 실어 보낼 수 있어 Cilium이 소스 보안 ID 등의 정보를 전송하는 데 활용합니다

### 2.3. Encapsulation Mode의 단점

1. **MTU 오버헤드** – 캡슐화 헤더(약 50바이트)가 추가되기 때문에 유효 MTU가 줄어들어 Native Routing보다 처리량이 낮을 수 있습니다. Jumbo Frame(예: `9000 Byte MTU`)을 활성화하면 이러한 오버헤드를 크게 완화할 수 있습니다.

> **MTU** - Maximum Transmission Unit (최대 전송 단위)

### 2.4. Encapsulation Mode 설정

Encapsulation Mode는 기본값으로 활성화되며, 아래 **Cilium 에이전트 설정 옵션**으로 세부 동작을 조정할 수 있습니다.

```shell
tunnel-protocol: vxlan   # geneve 또는 vxlan 선택, 기본값 vxlan
underlay-protocol: ipv4  # underlay IP 버전, 기본값 ipv4
tunnel-port: 8472        # 프로토콜 포트 (Geneve는 6081)
```

---

## 3. Native Routing Mode

![Cilium Native Routing Mode](/assets/img/kubernetes/cilium/cilium-native-routing-mode.webp)

Native Routing Mode는 Cilium이 캡슐화를 사용하지 않고 기본 네트워크의 Routing 기능을 활용하는 Mode입니다. `routing-mode: native`로 설정해 활성화하며, Cilium은 로컬 엔드포인트가 아닌 패킷을 모두 Linux 커널의 Routing 하위 시스템에 위임합니다. 즉, Pod에서 발생하는 패킷이 로컬 프로세스처럼 Routing됩니다.

### 3.1. 네트워크 요구 사항

- 클러스터 노드를 연결하는 네트워크는 모든 PodCIDR 주소를 전달할 수 있어야 함
- 각 노드 또는 라우터는 다른 노드의 Pod IP에 대한 경로를 알고 있어야 함. 이를 달성하는 방법은 아래 두 가지가 있음
  1. 중앙 Routing  
     - 노드들은 직접 Pod IP를 알지 못하지만, 네트워크에 있는 라우터가 모든 Pod에 대한 경로를 알고 있는 경우  
     - 클라우드 제공자 네트워크 통합(GKE, AWS ENI 등)이 해당
  2. 직접 Routing  
     - 각 노드가 다른 모든 노드의 Pod IP를 Routing할 수 있도록 Routing Table을 유지  
     - 단일 L2 네트워크를 공유한다면 `auto-direct-node-routes: true` 옵션으로 자동 관리할 수 있음  
     - 그렇지 않은 경우 BGP 데몬 등 외부 시스템이 경로를 배포해야 함

### 3.2. Native Routing Mode 설정

Native Routing Mode를 사용하려면 아래 값을 지정합니다

```shell
routing-mode: native                    # native routing mode 활성화
ipv4-native-routing-cidr: 10.10.0.0/16  # Native Routing이 적용될 PodCIDR 범위
auto-direct-node-routes: true           # L2 네트워크에 있는 노드 간 Routing 자동 설정
# Optional
direct-routing-skip-unreachable: true    # BGP 라우터가 있는 경우, 직접 Routing 불가능한 경로를 건너뛰기
```

---

## 4. 실습) Encapsulation Mode와 Native Routing Mode에서 노드 간 파드 통신 상세 확인

### 4.1. Sample Application 배포

```shell
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

# Control Plane Node에 curl-pod 파드 배포
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
    image: nicolaka/netshoot
    command: ["tail"]
    args: ["-f", "/dev/null"]
  terminationGracePeriodSeconds: 0
EOF
```

### 4.2. Encapsulation Mode에서 노드 간 파드 통신 확인

```shell
## routing mode 확인 (tunnel)
❯ cilium config view | grep routing-mode
routing-mode                                      tunnel

## Pod Status 확인
❯ kubectl get po -o wide
NAME                      READY   STATUS    RESTARTS   AGE     IP             NODE        NOMINATED NODE   READINESS GATES
curl-pod                  1/1     Running   0          6m55s   10.244.0.4     cilium-m1   <none>           <none>
webpod-7f69dc7985-b2cpb   1/1     Running   0          42s     10.244.1.232   cilium-w1   <none>           <none>
webpod-7f69dc7985-tw4q2   1/1     Running   0          49s     10.244.0.176   cilium-m1   <none>           <none>

## 편의성 설정
export WEBPODIP1=$(kubectl get -l app=webpod pods --field-selector spec.nodeName=cilium-m1 -o jsonpath='{.items[0].status.podIP}')
export WEBPODIP2=$(kubectl get -l app=webpod pods --field-selector spec.nodeName=cilium-w1  -o jsonpath='{.items[0].status.podIP}')
echo $WEBPODIP1 $WEBPODIP2

## 통신 확인 curl-pod 에서 WEBPODIP2 로 ping (유지)
❯ kubectl exec -it curl-pod -- ping $WEBPODIP2
PING 10.244.1.232 (10.244.1.232) 56(84) bytes of data.
64 bytes from 10.244.1.232: icmp_seq=1 ttl=63 time=1.47 ms
64 bytes from 10.244.1.232: icmp_seq=2 ttl=63 time=0.812 ms
64 bytes from 10.244.1.232: icmp_seq=3 ttl=63 time=0.702 ms

## Routing 정보 확인 (cilium-w1 node)
❯ ip -c route
default via 10.0.2.2 dev eth0 proto dhcp src 10.0.2.15 metric 100
10.0.2.0/24 dev eth0 proto kernel scope link src 10.0.2.15 metric 100
10.0.2.2 dev eth0 proto dhcp scope link src 10.0.2.15 metric 100
10.0.2.3 dev eth0 proto dhcp scope link src 10.0.2.15 metric 100
10.244.0.0/24 via 10.244.1.55 dev cilium_host proto kernel src 10.244.1.55 mtu 1450
10.244.1.0/24 via 10.244.1.55 dev cilium_host proto kernel src 10.244.1.55
10.244.1.55 dev cilium_host proto kernel scope link
10.244.1.159 dev lxc7e2f1b098b5e proto kernel scope link
10.244.1.170 dev lxcf961c0828463 proto kernel scope link
10.244.1.171 dev lxc8ecde0060715 proto kernel scope link
10.244.1.206 dev lxca6737b0b907e proto kernel scope link
10.244.1.220 dev lxcb6693998d529 proto kernel scope link
10.244.1.232 dev lxce2b79d6af2f8 proto kernel scope link
192.168.10.0/24 dev eth1 proto kernel scope link src 192.168.10.101

## vxlan 인터페이스 정보 확인 (cilium-w1 node)
❯ ip -d link show cilium_vxlan
24: cilium_vxlan: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UNKNOWN mode DEFAULT group default
    link/ether 12:b1:e4:fb:04:d3 brd ff:ff:ff:ff:ff:ff promiscuity 0  allmulti 0 minmtu 68 maxmtu 65535
    vxlan external id 0 srcport 0 0 dstport 8472 nolearning ttl auto ageing 300 udpcsum noudp6zerocsumtx noudp6zerocsumrx addrgenmode eui64 numtxqueues 1 numrxqueues 1 gso_max_size 65536 gso_max_segs 65535 tso_max_size 65536 tso_max_segs 65535 gro_max_size 65536

## tcpdump로 확인 (cilium-w1 node)
## 터널 Mode에서는 파드 간 트래픽이 VXLAN(UDP 8472)로 캡슐화돼서 icmp 로 식별 불가 
❯ tcpdump -i eth1 icmp
tcpdump: verbose output suppressed, use -v[v]... for full protocol decode
listening on eth1, link-type EN10MB (Ethernet), snapshot length 262144 bytes
0 packets captured
0 packets received by filter
0 packets dropped by kernel

## VXLAN 인터페이스의 UDP 8472포트로 확인
❯ tcpdump -i eth1 -nn 'udp port 8472' -c 10
tcpdump: verbose output suppressed, use -v[v]... for full protocol decode
listening on eth1, link-type EN10MB (Ethernet), snapshot length 262144 bytes
21:05:48.204749 IP 192.168.10.100.38265 > 192.168.10.101.8472: OTV, flags [I] (0x08), overlay 0, instance 3245
IP 10.244.0.4 > 10.244.1.232: ICMP echo request, id 533, seq 1, length 64
21:05:48.205199 IP 192.168.10.101.44579 > 192.168.10.100.8472: OTV, flags [I] (0x08), overlay 0, instance 12317
IP 10.244.1.232 > 10.244.0.4: ICMP echo reply, id 533, seq 1, length 64
21:05:49.206769 IP 192.168.10.100.38265 > 192.168.10.101.8472: OTV, flags [I] (0x08), overlay 0, instance 3245
IP 10.244.0.4 > 10.244.1.232: ICMP echo request, id 533, seq 2, length 64
21:05:49.206920 IP 192.168.10.101.44579 > 192.168.10.100.8472: OTV, flags [I] (0x08), overlay 0, instance 12317
IP 10.244.1.232 > 10.244.0.4: ICMP echo reply, id 533, seq 2, length 64

## 캡처한 패킷을 /tmp/icmp.pcap 으로 저장
❯ tcpdump -i eth1 -nn 'udp port 8472' -w /tmp/icmp.pcap -c 10
tcpdump: listening on eth1, link-type EN10MB (Ethernet), snapshot length 262144 bytes
10 packets captured
10 packets received by filter
0 packets dropped by kernel

## 확인
❯ termshark -r /tmp/icmp.pcap
...
```

![Term Shark In Encapsulation Mode](/assets/img/kubernetes/cilium/termshark_in_encapsulation_mode.webp)

### 4.3. Native Mode에서 노드 간 Pod 통신 확인

```shell
## Encapsulation Mode에서 -> Native로 변경
❯ helm upgrade cilium cilium/cilium --namespace kube-system --version=1.17.6 --reuse-values \
  --set routingMode=native \
  --set autoDirectNodeRoutes=true \
  --set endpointRoutes.enabled=true

Release "cilium" has been upgraded. Happy Helming!

## 확인
❯ cilium config view | grep routing-mode                                                                  
routing-mode                                      native

## 통신 확인 curl-pod 에서 WEBPODIP2 로 ping (유지)
❯ kubectl exec -it curl-pod -- ping $WEBPODIP2
PING 10.244.1.232 (10.244.1.232) 56(84) bytes of data.
64 bytes from 10.244.1.232: icmp_seq=1 ttl=62 time=2.04 ms
64 bytes from 10.244.1.232: icmp_seq=2 ttl=62 time=0.722 ms

## Routing 정보 확인 (cilium-w1 node)
❯ ip -c route
default via 10.0.2.2 dev eth0 proto dhcp src 10.0.2.15 metric 100
10.0.2.0/24 dev eth0 proto kernel scope link src 10.0.2.15 metric 100
10.0.2.2 dev eth0 proto dhcp scope link src 10.0.2.15 metric 100
10.0.2.3 dev eth0 proto dhcp scope link src 10.0.2.15 metric 100
10.244.0.0/24 via 192.168.10.100 dev eth1 proto kernel #cilium-m1 node
10.244.1.159 dev lxc7e2f1b098b5e proto kernel scope link
10.244.1.170 dev lxcf961c0828463 proto kernel scope link
10.244.1.171 dev lxc8ecde0060715 proto kernel scope link
10.244.1.206 dev lxca6737b0b907e proto kernel scope link
10.244.1.220 dev lxcb6693998d529 proto kernel scope link
10.244.1.232 dev lxce2b79d6af2f8 proto kernel scope link
192.168.10.0/24 dev eth1 proto kernel scope link src 192.168.10.101

## tcpdump로 확인 (cilium-w1 node)
❯ tcpdump -i eth1 icmp
tcpdump: verbose output suppressed, use -v[v]... for full protocol decode
listening on eth1, link-type EN10MB (Ethernet), snapshot length 262144 bytes
20:39:53.324902 IP 10.244.0.4 > 10.244.1.232: ICMP echo request, id 511, seq 94, length 64
20:39:53.325016 IP 10.244.1.232 > 10.244.0.4: ICMP echo reply, id 511, seq 94, length 64
20:39:54.350035 IP 10.244.0.4 > 10.244.1.232: ICMP echo request, id 511, seq 95, length 64
20:39:54.350464 IP 10.244.1.232 > 10.244.0.4: ICMP echo reply, id 511, seq 95, length 64

## 캡처한 패킷을 /tmp/icmp.pcap 으로 저장
❯ tcpdump -i eth1 icmp -w /tmp/icmp.pcap
tcpdump: listening on eth1, link-type EN10MB (Ethernet), snapshot length 262144 bytes
6 packets captured
6 packets received by filter
0 packets dropped by kernel

## 확인
❯ termshark -r /tmp/icmp.pcap
```
![Term Shark In Native Mode](/assets/img/kubernetes/cilium/termshark_in_native_mode.webp)

### 4.4. 실습 결론

1. **Native Mode**
   - 언더레이 NIC에서 바로 PodIP에서 PodIP로 가는 ICMP 확인 가능
   - 캡슐화 없음, 따라서 MTU 손실이 없고 디버깅이 직관적
2. **Encapsulation Mode**
   - 언더레이 NIC에서 패킷을 보면 NodeIP에서 NodeIP로 가는 UDP 8472(또는 6081) 확인 가능
   - 터널 오버헤드로 유효 MTU 감소, 방화벽에 8472/UDP(VXLAN) 또는 6081/UDP(Geneve) 허용 필요

> Encapsulation에서는 언더레이 캡처가 **NodeIP <-> NodeIP(UDP 8472/6081)** 로 보이며, 페이로드를 열어봐야 **PodIP <-> PodIP(ICMP)** 를 확인할 수 있습니다.  
> 반면 Native에서는 언더레이에서 **PodIP <-> PodIP(ICMP)** 가 바로 보입니다.  
{: .prompt-tip}

---

## 5. 마무리

| 항목              | Encapsulation(VXLAN·GENEVE)                           | Native Routing                                                |
| :---------------- | :---------------------------------------------------- | :------------------------------------------------------------ |
| 네트워크 요구사항 | 노드 간 IP/UDP 통신만 가능하면 됨                     | PodCIDR Routing 가능해야 함                                   |
| 데이터 패스       | 모든 노드 간 트래픽을 터널로 캡슐화                   | Linux 커널 Routing Table로 직접 포워딩                        |
| 포트/프로토콜     | VXLAN 8472/UDP, Geneve 6081/UDP                       | 별도 포트 요구 없음(언더레이 Routing 필요)                    |
| MTU 영향          | 캡슐화 오버헤드로 유효 MTU 감소, Jumbo Frame 권장     | 오버헤드 없음, 일반 MTU 그대로                                |
| 구성 난이도       | 간단, 토폴로지 의존성 낮음                            | Routing, Advertisement 구성 필요, 토폴로지 의존성 있음        |
| 확장/성능         | 손쉬운 확장, 처리량은 MTU 영향 받음                   | 고성능·낮은 지연, Routing 수·수렴 시간 고려                   |
| 트러블슈팅        | 터널(UDP) 레벨 캡처 필요                              | 평면 IP로 디버깅 용이(tcpdump, hubble Event 직관적)           |
| 대표 사용처       | Hybrid/Segmented 네트워크, 빠른 PoC, 단순한 초기 구축 | 단일 L2·클라우드 라우터 환경, 고성능/저지연 요구, 대규모 운영 |

---

## 6. Reference

- [Cilium Docs - Routing](https://docs.cilium.io/en/stable/network/concepts/routing/)
- [Cilium Docs - LoadBalancer IP Address Management (LB IPAM)](https://docs.cilium.io/en/stable/network/lb-ipam/)
- [Isovalent Blog - Overcoming Kubernetes IP Address Exhaustion with Cilium](https://isovalent.com/blog/post/overcoming-kubernetes-ip-address-exhaustion-with-cilium)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
