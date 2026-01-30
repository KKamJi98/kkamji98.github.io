---
title: Cilium BGP Control Plane [Cilium Study 5주차]
date: 2025-08-11 01:04:55 +0900
author: kkamji
categories: [Kubernetes, Cilium]
tags: [kubernetes, devops, cilium, cilium-study, cilium-5w, cloudnet, gasida, cilium-bgp-control-plane, bgp]
comments: true
image:
  path: /assets/img/kubernetes/cilium/cilium.webp
---

지난 글 [Cilium Network Routing 이해하기 – Encapsulation과 Native Routing 비교 [Cilium Study 3주차]]({% post_url 2025/08/2025-08-03-cilium-routing %})에서는 Native Routing 모드에서 **각 Node/Router가 다른 Node의 PodCIDR 경로를 알고 있어야 한다**는 점을 살펴봤습니다.  

이번 시간에는 실제로 **PodCIDR 간 라우팅이 설정되지 않았을 때 어떤 문제가 발생하는지**를 실습 환경에서 확인하고, `tcpdump`로 그 흐름을 분석한 뒤 **Static Route와 BGP를 통한 해결 방법**을 다뤄보겠습니다.

---

## 1. 실습 환경

![Lab Environment](/assets/img/kubernetes/cilium/5w-lab-environment.webp)

- 기본 VM: k8s-ctr, k8s-w1, k8s-w0, router(FRR)
- router: 192.168.10.0/24 ↔ 192.168.20.0/24 라우팅, 클러스터에 join되지 않은 독립 서버, FRR 설치로 BGP 실습 가능 (FRR Docs)
- k8s-w0: 다른 Node와 구분해 192.168.20.0/24 대역에 배치
- Static Routing: Vagrant 스크립트에서 자동 설정됨 [Vagrant Script File](<https://github.com/KKamJi98/cilium-lab/blob/main/vagrant/vagrant-5w/Vagrantfile>)

> FRR-Docs - [FRR-Docs](https://docs.frrouting.org/en/stable-10.4/about.html)  

---

## 2. 실습 환경 확인

### 2.1. 기본 클러스터 & 네트워크 상태 확인

```shell
###############################################
## [k8s-ctr] 접속 후 기본 정보 확인
###############################################

# /etc/hosts: VM 간 hostname-IP 매핑 확인
cat /etc/hosts

# 각 VM 접속 후 hostname 확인
for i in k8s-w0 k8s-w1 router ; do
  echo ">> node : $i <<"
  sshpass -p 'vagrant' ssh -o StrictHostKeyChecking=no vagrant@$i hostname
  echo
done


###############################################
## 클러스터 정보 확인
###############################################

# Kubernetes Cluster 엔드포인트 정보
kubectl cluster-info

# 클러스터 네트워크 CIDR (PodCIDR / ServiceCIDR)
kubectl cluster-info dump | grep -m 2 -E "cluster-cidr|service-cluster-ip-range"

# kubeadm 초기 설정 및 kubelet 설정 확인
kubectl describe cm -n kube-system kubeadm-config
kubectl describe cm -n kube-system kubelet-config


###############################################
## Node 정보 확인
###############################################

# 각 Node VM 내부 IP (eth 인터페이스)
ifconfig | grep -iEA1 'eth[0-9]:'

# Kubernetes Node 상태 + INTERNAL-IP
kubectl get node -o wide


###############################################
## 파드 및 Cilium 정보 확인
###############################################

# 각 Node별 PodCIDR 확인
kubectl get nodes -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.podCIDR}{"\n"}{end}'

# CiliumNode 리소스에서 PodCIDRs 확인
kubectl get ciliumnode -o json | grep podCIDRs -A2

# 파드 상태 및 파드 IP
kubectl get pod -A -o wide

# Cilium Endpoints (파드 단위 네트워크 엔드포인트)
kubectl get ciliumendpoints -A

# Cilium IPAM 모드 확인 (host-scope / cluster-pool 여부)
cilium config view | grep ^ipam


###############################################
## iptables 확인
###############################################

iptables-save
iptables -t nat -S
iptables -t filter -S
iptables -t mangle -S
iptables -t raw -S


###############################################
## Router 네트워크 인터페이스 정보
###############################################

sshpass -p 'vagrant' ssh vagrant@router ip -br -c -4 addr


###############################################
## Node 네트워크 인터페이스 정보
###############################################

ip -c -4 addr show dev eth1

for i in w1 w0 ; do
  echo ">> node : k8s-$i <<"
  sshpass -p 'vagrant' ssh vagrant@k8s-$i ip -c -4 addr show dev eth1
  echo
done


###############################################
## 라우팅 테이블 확인 (autoDirectNodeRoutes=false)
###############################################

sshpass -p 'vagrant' ssh vagrant@router ip -c route
ip -c route | grep static
ip -c route

for i in w1 w0 ; do
  echo ">> node : k8s-$i <<"
  sshpass -p 'vagrant' ssh vagrant@k8s-$i ip -c route
  echo
done


###############################################
## 통신 확인
###############################################

ping -c 1 192.168.20.100  # k8s-w0 eth1


###############################################
## [k8s-ctr] Cilium 설치 상태 확인
###############################################

kubectl get cm -n kube-system cilium-config -o json | jq
cilium status
cilium config view | grep -i bgp

kubectl exec -n kube-system -c cilium-agent -it ds/cilium -- cilium-dbg status --verbose
kubectl exec -n kube-system -c cilium-agent -it ds/cilium -- cilium-dbg metrics list

kubectl exec -n kube-system -c cilium-agent -it ds/cilium -- cilium-dbg monitor
kubectl exec -n kube-system -c cilium-agent -it ds/cilium -- cilium-dbg monitor -v
kubectl exec -n kube-system -c cilium-agent -it ds/cilium -- cilium-dbg monitor -v -v
```

### 2.2. 샘플 애플리케이션 배포 및 통신 문제 확인

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

# curl-pod 배포 (k8s-ctr에 고정)
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
## 2. 통신 문제 확인 (같은 Node내에서만 통신 가능) 
###############################################
# curl-pod, webpod-697b545f57-smfjd (같은 Node)
kubectl get deploy,svc,ep webpod -o wide
kubectl get endpointslices -l app=webpod
kubectl get ciliumendpoints -A

(⎈|HomeLab:N/A) root@k8s-ctr:~# kubectl get po -A -o wide
NAMESPACE            NAME                                      READY   STATUS    RESTARTS      AGE     IP               NODE      NOMINATED NODE   READINESS GATES
default              curl-pod                                  1/1     Running   0             4m26s   172.20.0.169     k8s-ctr   <none>           <none>
default              webpod-697b545f57-47tbm                   1/1     Running   0             4m27s   172.20.2.99      k8s-w0    <none>           <none>
default              webpod-697b545f57-dmcqr                   1/1     Running   0             4m27s   172.20.1.124     k8s-w1    <none>           <none>
default              webpod-697b545f57-smfjd                   1/1     Running   0             4m27s   172.20.0.88      k8s-ctr   <none>           <none>

(⎈|HomeLab:N/A) root@k8s-ctr:~# kubectl exec -it curl-pod -- sh -c 'while true; do curl -s --connect-timeout 1 webpod | grep Hostname; echo "---" ; sleep 1; done'
---
---
Hostname: webpod-697b545f57-smfjd 
---
Hostname: webpod-697b545f57-smfjd
---
Hostname: webpod-697b545f57-smfjd
---
---


###############################################
## 3. Cilium Debug (Maps & BPF 상태)
###############################################

kubectl exec -n kube-system ds/cilium -- cilium-dbg ip list
kubectl exec -n kube-system ds/cilium -- cilium-dbg endpoint list
kubectl exec -n kube-system ds/cilium -- cilium-dbg service list
kubectl exec -n kube-system ds/cilium -- cilium-dbg bpf lb list
kubectl exec -n kube-system ds/cilium -- cilium-dbg bpf nat list
kubectl exec -n kube-system ds/cilium -- cilium-dbg map list | grep -v '0             0'
kubectl exec -n kube-system ds/cilium -- cilium-dbg map get cilium_lb4_services_v2
kubectl exec -n kube-system ds/cilium -- cilium-dbg map get cilium_lb4_backends_v3
kubectl exec -n kube-system ds/cilium -- cilium-dbg map get cilium_lb4_reverse_nat
kubectl exec -n kube-system ds/cilium -- cilium-dbg map get cilium_ipcache_v2
```

---

## 3. Cilium BGP Control Plane

Cilium BGP Control Plane(BGPv2)는 Cilium의 Custom Resources로 BGP 구성을 선언적으로 관리합니다. 또한 Cilium BGP는 기본적으로 외부 경로를 커널 라우팅 테이블에 주입하지 않습니다.

![Cilium Docs - Cilium BGP Control Plane v2 Architecture](/assets/img/kubernetes/cilium/5w-bgp-control-plane-v2-architecture.webp)

> [Cilium Docs - BGP Control Plane Resources](https://docs.cilium.io/en/stable/network/bgp-control-plane/bgp-control-plane-v2/)  
> [Cilium GitHub - BGP Code](https://github.com/cilium/cilium/tree/main/operator/pkg/bgpv2)  

### 3.1. 핵심 Custom Resources

- CiliumBGPClusterConfig: 여러 Node에 적용할 BGP 인스턴스와 피어 정의
- CiliumBGPPeerConfig: 공통 BGP 피어 설정 템플릿
- CiliumBGPAdvertisement: 광고할 프리픽스 정의
- CiliumBGPNodeConfigOverride: Node 단위 세부 오버라이드

### 3.2. FRR Router 확인

```bash
# k8s-ctr 에서 router 접속
sshpass -p 'vagrant' ssh vagrant@router

# FRR 데몬 동작 확인
ss -tnlp | grep -iE 'zebra|bgpd'
ps -ef | grep -E 'frr|zebra|bgpd' | grep -v grep

# 러닝 컨피그 확인
vtysh -c 'show running'
cat /etc/frr/frr.conf
...
router bgp 65000
  bgp router-id 192.168.10.200
  bgp graceful-restart
  no bgp ebgp-requires-policy
  bgp bestpath as-path multipath-relax
  maximum-paths 4
  network 10.10.1.0/24

# BGP 요약 및 테이블 확인
vtysh -c 'show ip bgp summary'
vtysh -c 'show ip bgp'

# 커널 라우팅 및 FRR 라우팅 확인
ip -c route
vtysh -c 'show ip route'
...
Codes: K - kernel route, C - connected, S - static, R - RIP,
       O - OSPF, I - IS-IS, B - BGP, E - EIGRP, N - NHRP,
       T - Table, v - VNC, V - VNC-Direct, A - Babel, F - PBR,
       f - OpenFabric,
       > - selected route, * - FIB route, q - queued, r - rejected, b - backup
       t - trapped, o - offload failure

K>* 0.0.0.0/0 [0/100] via 10.0.2.2, eth0, src 10.0.2.15, 02:10:50
C>* 10.0.2.0/24 [0/100] is directly connected, eth0, 02:10:50
K>* 10.0.2.2/32 [0/100] is directly connected, eth0, 02:10:50
K>* 10.0.2.3/32 [0/100] is directly connected, eth0, 02:10:50
C>* 10.10.1.0/24 is directly connected, loop1, 02:10:50
C>* 10.10.2.0/24 is directly connected, loop2, 02:10:50
C>* 192.168.10.0/24 is directly connected, eth1, 02:10:50
C>* 192.168.20.0/24 is directly connected, eth2, 02:10:50
```

### 3.3. FRR Router 설정

```shell
# Cilium Node BGP 설정 (node neighbor 설정파일)
cat << 'EOF' | sudo tee -a /etc/frr/frr.conf
neighbor CILIUM peer-group
neighbor CILIUM remote-as external
neighbor 192.168.10.100 peer-group CILIUM
neighbor 192.168.10.101 peer-group CILIUM
neighbor 192.168.20.100 peer-group CILIUM
EOF

sudo systemctl daemon-reexec
sudo systemctl restart frr
systemctl status frr --no-pager --full

# 로그 모니터링 (다른 터미널 사용)
journalctl -u frr -f
```

### 3.4. Cilium BGP 설정

```shell
# 모니터링 터미널 1 (router)
journalctl -u frr -f

# 모니터링 터미널 2 (k8s-ctr)
kubectl exec -it curl-pod -- sh -c 'while true; do curl -s --connect-timeout 1 webpod | grep Hostname; echo "---"; sleep 1; done'

# BGP 활성화 대상 노드를 위해 Labeling
kubectl label nodes k8s-ctr k8s-w0 k8s-w1 enable-bgp=true
kubectl get node -l enable-bgp=true

# Cilium BGP 설정
cat << EOF | kubectl apply -f -
apiVersion: cilium.io/v2
kind: CiliumBGPAdvertisement
metadata:
  name: bgp-advertisements
  labels:
    advertise: bgp
spec:
  advertisements:
    - advertisementType: "PodCIDR"
---
apiVersion: cilium.io/v2
kind: CiliumBGPPeerConfig
metadata:
  name: cilium-peer
spec:
  timers:
    holdTimeSeconds: 9
    keepAliveTimeSeconds: 3
  ebgpMultihop: 2
  gracefulRestart:
    enabled: true
    restartTimeSeconds: 15
  families:
    - afi: ipv4
      safi: unicast
      advertisements:
        matchLabels:
          advertise: "bgp"
---
apiVersion: cilium.io/v2
kind: CiliumBGPClusterConfig
metadata:
  name: cilium-bgp
spec:
  nodeSelector:
    matchLabels:
      "enable-bgp": "true"
  bgpInstances:
  - name: "instance-65001"
    localASN: 65001
    peers:
    - name: "tor-switch"
      peerASN: 65000
      peerAddress: 192.168.10.200  # router ip address
      peerConfigRef:
        name: "cilium-peer"
EOF

# 모니터링 터미널 1 출력 (router)
Aug 17 06:12:10 router bgpd[5154]: [M59KS-A3ZXZ] bgp_update_receive: rcvd End-of-RIB for IPv4 Unicast from 192.168.10.101 in vrf default
Aug 17 06:12:10 router bgpd[5154]: [M59KS-A3ZXZ] bgp_update_receive: rcvd End-of-RIB for IPv4 Unicast from 192.168.20.100 in vrf default
Aug 17 06:12:10 router bgpd[5154]: [M59KS-A3ZXZ] bgp_update_receive: rcvd End-of-RIB for IPv4 Unicast from 192.168.10.100 in vrf default
```

### 3.5. 통신 확인

```shell
# 세션 포트 확인 (k8s-ctr)
ss -tnp | grep :179
...
ESTAB 0      0               192.168.10.100:44891          192.168.10.200:179   users:(("cilium-agent",pid=5384,fd=58)) 

# Cilium BGP 상태 확인
cilium bgp peers
...
Node      Local AS   Peer AS   Peer Address     Session State   Uptime   Family         Received   Advertised
k8s-ctr   65001      65000     192.168.10.200   established     7m31s    ipv4/unicast   4          2    
k8s-w0    65001      65000     192.168.10.200   established     7m30s    ipv4/unicast   4          2    
k8s-w1    65001      65000     192.168.10.200   established     7m30s    ipv4/unicast   4          2    

#
cilium bgp routes available ipv4 unicast
...
Node      VRouter   Prefix          NextHop   Age     Attrs
k8s-ctr   65001     172.20.0.0/24   0.0.0.0   7m51s   [{Origin: i} {Nexthop: 0.0.0.0}]   
k8s-w0    65001     172.20.2.0/24   0.0.0.0   7m51s   [{Origin: i} {Nexthop: 0.0.0.0}]   
k8s-w1    65001     172.20.1.0/24   0.0.0.0   7m51s   [{Origin: i} {Nexthop: 0.0.0.0}]   

# CR 리소스 확인
kubectl get ciliumbgpadvertisements,ciliumbgppeerconfigs,ciliumbgpclusterconfigs
kubectl get ciliumbgpnodeconfigs -o yaml | yq

# Router 설정 확인 
sshpass -p 'vagrant' ssh vagrant@router "ip -c route | grep bgp"
...
172.20.0.0/24 nhid 30 via 192.168.10.100 dev eth1 proto bgp metric 20 
172.20.1.0/24 nhid 31 via 192.168.10.101 dev eth1 proto bgp metric 20 
172.20.2.0/24 nhid 32 via 192.168.20.100 dev eth2 proto bgp metric 20 

#
sshpass -p 'vagrant' ssh vagrant@router "sudo vtysh -c 'show ip bgp summary'"
...

IPv4 Unicast Summary (VRF default):
BGP router identifier 192.168.10.200, local AS number 65000 vrf-id 0
BGP table version 4
RIB entries 7, using 1344 bytes of memory
Peers 3, using 2172 KiB of memory
Peer groups 1, using 64 bytes of memory

Neighbor        V         AS   MsgRcvd   MsgSent   TblVer  InQ OutQ  Up/Down State/PfxRcd   PfxSnt Desc
192.168.10.100  4      65001       246       249        0    0    0 00:12:06            1        4 N/A
192.168.10.101  4      65001       245       249        0    0    0 00:12:06            1        4 N/A
192.168.20.100  4      65001       245       248        0    0    0 00:12:05            1        4 N/A

Total number of neighbors 3

# 
sshpass -p 'vagrant' ssh vagrant@router "sudo vtysh -c 'show ip bgp'"
...
BGP table version is 4, local router ID is 192.168.10.200, vrf id 0
Default local pref 100, local AS 65000
Status codes:  s suppressed, d damped, h history, * valid, > best, = multipath,
               i internal, r RIB-failure, S Stale, R Removed
Nexthop codes: @NNN nexthop's vrf id, < announce-nh-self
Origin codes:  i - IGP, e - EGP, ? - incomplete
RPKI validation codes: V valid, I invalid, N Not found

   Network          Next Hop            Metric LocPrf Weight Path
*> 10.10.1.0/24     0.0.0.0                  0         32768 i
*> 172.20.0.0/24    192.168.10.100                         0 65001 i
*> 172.20.1.0/24    192.168.10.101                         0 65001 i
*> 172.20.2.0/24    192.168.20.100                         0 65001 i

Displayed  4 routes and 4 total paths

# 모니터링 터미널 2 출력 (k8s-ctr, 그대로 통신이 안됨)
Hostname: webpod-697b545f57-smfjd
---
Hostname: webpod-697b545f57-smfjd
---
Hostname: webpod-697b545f57-smfjd
---
Hostname: webpod-697b545f57-smfjd
```

### 3.6. Termshark와 tcpdump를 사용한 패킷 분석

```shell
# 패킷 캡처 (k8s-ctr, 다른 터미널에서)
tcpdump -i eth1 tcp port 179 -w /tmp/bgp.pcap


# frr 재시작 후 로그 모니터링 (router)
sudo systemctl restart frr
journalctl -u frr -f
...
Aug 17 06:36:04 router watchfrr[5810]: [QDG3Y-BY5TN] bgpd state -> up : connect succeeded
Aug 17 06:36:04 router watchfrr[5810]: [QDG3Y-BY5TN] staticd state -> up : connect succeeded
Aug 17 06:36:04 router watchfrr[5810]: [KWE5Q-QNGFC] all daemons up, doing startup-complete notify
Aug 17 06:36:10 router bgpd[5828]: [M59KS-A3ZXZ] bgp_update_receive: rcvd End-of-RIB for IPv4 Unicast from 192.168.10.100 in vrf default
Aug 17 06:36:10 router bgpd[5828]: [M59KS-A3ZXZ] bgp_update_receive: rcvd End-of-RIB for IPv4 Unicast from 192.168.20.100 in vrf default
Aug 17 06:36:10 router bgpd[5828]: [M59KS-A3ZXZ] bgp_update_receive: rcvd End-of-RIB for IPv4 Unicast from 192.168.10.101 in vrf default

# tcpdump 취소 후 termshark를 사용해 패킷 확인
# bgp.type == 2
termshark -r /tmp/bgp.pcap

# Routing 정보 확인
cilium bgp routes
...
(Defaulting to `available ipv4 unicast` routes, please see help for more options)

Node      VRouter   Prefix          NextHop   Age      Attrs
k8s-ctr   65001     172.20.0.0/24   0.0.0.0   14m49s   [{Origin: i} {Nexthop: 0.0.0.0}]
k8s-w0    65001     172.20.2.0/24   0.0.0.0   43m41s   [{Origin: i} {Nexthop: 0.0.0.0}]
k8s-w1    65001     172.20.1.0/24   0.0.0.0   43m41s   [{Origin: i} {Nexthop: 0.0.0.0}]

# Routing Table 확인 (BGP로 추가가 되어야할 IP가 추가가 안됨 172.20.2.0/24, 172.20.1.0/24)
ip -c route
...
default via 10.0.2.2 dev eth0 proto dhcp src 10.0.2.15 metric 100
10.0.2.0/24 dev eth0 proto kernel scope link src 10.0.2.15 metric 100
10.0.2.2 dev eth0 proto dhcp scope link src 10.0.2.15 metric 100
10.0.2.3 dev eth0 proto dhcp scope link src 10.0.2.15 metric 100
172.20.0.0/24 via 172.20.0.157 dev cilium_host proto kernel src 172.20.0.157
172.20.0.157 dev cilium_host proto kernel scope link
192.168.10.0/24 dev eth1 proto kernel scope link src 192.168.10.100
192.168.20.0/24 via 192.168.10.200 dev eth1 proto static

# Router 장비를 통해 BGP UPDATE로 받음을 확인. (아래 사진 참고)
```
![BGP Packet Termshark](/assets/img/kubernetes/cilium/5w-bgp-packet-termshark.webp)

### 3.7. 문제확인 및 설명 (By ChatGPT)

- Cilium의 BGP는 기본적으로 **외부 경로를 커널 라우팅 테이블에 주입하지 않음**.
  - 왜 Cilium이 받은 BGP 경로가 Kubernetes 노드 OS 커널 라우팅 테이블에 안 들어오나?
    - **Cilium의 BGP는 "컨트롤 플레인"만 동작**
      - Cilium BGP Speaker(GoBGP 기반)는 BGP 세션을 맺고 prefix를 광고하거나 수신합니다.
      - 하지만 **수신한 경로를 Linux 커널(FIB)** 에 바로 주입하지 않음.
      - 대신 Cilium 내부에서 **LoadBalancer 서비스 광고**, **PodCIDR 전파** 같은 용도로만 사용.
    - **Pod/Service 네트워크 경로는 Cilium eBPF가 처리**
      - Cilium은 kube-proxy 대체 모드에서 eBPF datapath로 패킷을 라우팅합니다.
      - 외부 경로 학습이 커널 라우팅 테이블에 없어도, eBPF map에 저장된 다음 홉 정보로 처리 가능.
    - **GoBGP 기본 설정도 FIB 설치 비활성화**
      - Cilium이 사용하는 GoBGP 라이브러리는 `disable-telemetry`, **`disable-fib`** 상태로 빌드됨.
      - 즉, 외부 라우터에서 들어온 BGP NLRI는 커널에 반영되지 않고, Cilium 내부 정책/광고 로직에서만 사용.

- **문제 해결** 후 통신 확인 : 결론은 Cilium 으로 BGP 사용 시, 2개 이상의 NIC 사용할 경우에는 Node에 직접 라우팅 설정 및 관리가 필요
  - 현재 실습 환경은 2개의 NIC(eth0, eth1)을 사용하고 있는 상황으로, default GW가 eth0 경로로 설정 되어 있음
  - eth1은 k8s 통신 용도로 사용 중. 즉, 현재 k8s 파드 사용 대역 통신 전체는 eth1을 통해서 라우팅 설정하면 됨
  - 해당 라우팅을 상단에 네트워크 장비가 받게 되고, 해당 장비는 Cilium Node를 통해 모든 PodCIDR 정보를 알고 있기에, 목적지로 전달 가능

> 결론: Cilium 으로 BGP 사용 시, 2개 이상의 NIC 사용할 경우에는 Node에 직접 라우팅 설정 및 관리가 필요  
{: .prompt-tip}

### 3.8. 문제해결 후 통신 확인

```shell
# k8s 파드 사용 대역 통신 전체는 eth1을 통해서 라우팅 설정
ip route add 172.20.0.0/16 via 192.168.10.200
sshpass -p 'vagrant' ssh vagrant@k8s-w1 sudo ip route add 172.20.0.0/16 via 192.168.10.200
sshpass -p 'vagrant' ssh vagrant@k8s-w0 sudo ip route add 172.20.0.0/16 via 192.168.20.200

# router 가 bgp로 학습한 라우팅 정보 한번 더 확인 : 
sshpass -p 'vagrant' ssh vagrant@router ip -c route | grep bgp
...
172.20.0.0/24 nhid 64 via 192.168.10.100 dev eth1 proto bgp metric 20 
172.20.1.0/24 nhid 60 via 192.168.10.101 dev eth1 proto bgp metric 20 
172.20.2.0/24 nhid 62 via 192.168.20.100 dev eth2 proto bgp metric 20 

# 정상 통신 확인
kubectl exec -it curl-pod -- sh -c 'while true; do curl -s --connect-timeout 1 webpod | grep Hostname; echo "---" ; sleep 1; done'
...
Hostname: webpod-697b545f57-47tbm
---
Hostname: webpod-697b545f57-smfjd
---
Hostname: webpod-697b545f57-47tbm
---
Hostname: webpod-697b545f57-47tbm
---
Hostname: webpod-697b545f57-smfjd
---
Hostname: webpod-697b545f57-dmcqr

# hubble relay 포트 포워딩 실행
cilium hubble port-forward&
hubble status

# flow log 모니터링
hubble observe -f --protocol tcp --pod curl-pod
...
Aug 16 21:58:48.481: default/curl-pod (ID:17401) <> 10.96.19.99:80 (world) pre-xlate-fwd TRACED (TCP)
Aug 16 21:58:48.481: default/curl-pod (ID:17401) <> default/webpod-697b545f57-smfjd:80 (ID:7945) post-xlate-fwd TRANSLATED (TCP)
Aug 16 21:58:48.481: default/curl-pod:56560 (ID:17401) -> default/webpod-697b545f57-smfjd:80 (ID:7945) to-endpoint FORWARDED (TCP Flags: SYN)
Aug 16 21:58:48.481: default/curl-pod:56560 (ID:17401) <- default/webpod-697b545f57-smfjd:80 (ID:7945) to-endpoint FORWARDED (TCP Flags: SYN, ACK)
Aug 16 21:58:48.481: default/curl-pod:56560 (ID:17401) -> default/webpod-697b545f57-smfjd:80 (ID:7945) to-endpoint FORWARDED (TCP Flags: ACK)
Aug 16 21:58:48.482: default/curl-pod:56560 (ID:17401) <> default/webpod-697b545f57-smfjd (ID:7945) pre-xlate-rev TRACED (TCP)
Aug 16 21:58:48.483: default/curl-pod:56560 (ID:17401) -> default/webpod-697b545f57-smfjd:80 (ID:7945) to-endpoint FORWARDED (TCP Flags: ACK, PSH)
Aug 16 21:58:48.483: default/curl-pod:56560 (ID:17401) <> default/webpod-697b545f57-smfjd (ID:7945) pre-xlate-rev TRACED (TCP)
Aug 16 21:58:48.484: default/curl-pod:56560 (ID:17401) <> default/webpod-697b545f57-smfjd (ID:7945) pre-xlate-rev TRACED (TCP)
Aug 16 21:58:48.485: default/curl-pod:56560 (ID:17401) <> default/webpod-697b545f57-smfjd (ID:7945) pre-xlate-rev TRACED (TCP)
Aug 16 21:58:48.486: default/curl-pod:56560 (ID:17401) <> default/webpod-697b545f57-smfjd (ID:7945) pre-xlate-rev TRACED (TCP)
Aug 16 21:58:48.487: default/curl-pod:56560 (ID:17401) <- default/webpod-697b545f57-smfjd:80 (ID:7945) to-endpoint FORWARDED (TCP Flags: ACK, PSH)
Aug 16 21:58:48.488: default/curl-pod:56560 (ID:17401) -> default/webpod-697b545f57-smfjd:80 (ID:7945) to-endpoint FORWARDED (TCP Flags: ACK, FIN)
Aug 16 21:58:48.489: default/curl-pod:56560 (ID:17401) <- default/webpod-697b545f57-smfjd:80 (ID:7945) to-endpoint FORWARDED (TCP Flags: ACK, FIN)
Aug 16 21:58:48.489: default/curl-pod:56560 (ID:17401) -> default/webpod-697b545f57-smfjd:80 (ID:7945) to-endpoint FORWARDED (TCP Flags: ACK)
Aug 16 21:58:49.503: default/curl-pod (ID:17401) <> 10.96.19.99:80 (world) pre-xlate-fwd TRACED (TCP)
Aug 16 21:58:49.503: default/curl-pod (ID:17401) <> default/webpod-697b545f57-smfjd:80 (ID:7945) post-xlate-fwd TRANSLATED (TCP)
Aug 16 21:58:49.503: default/curl-pod:56564 (ID:17401) -> default/webpod-697b545f57-smfjd:80 (ID:7945) to-endpoint FORWARDED (TCP Flags: SYN)
Aug 16 21:58:49.503: default/curl-pod:56564 (ID:17401) <- default/webpod-697b545f57-smfjd:80 (ID:7945) to-endpoint FORWARDED (TCP Flags: SYN, ACK)
Aug 16 21:58:49.503: default/curl-pod:56564 (ID:17401) -> default/webpod-697b545f57-smfjd:80 (ID:7945) to-endpoint FORWARDED (TCP Flags: ACK)
Aug 16 21:58:49.504: default/curl-pod:56564 (ID:17401) -> default/webpod-697b545f57-smfjd:80 (ID:7945) to-endpoint FORWARDED (TCP Flags: ACK, PSH)
Aug 16 21:58:49.504: default/curl-pod:56564 (ID:17401) <> default/webpod-697b545f57-smfjd (ID:7945) pre-xlate-rev TRACED (TCP)
```

---

## 4. 결론

1. **Cilium BGP Control Plane은 컨트롤 플레인 중심으로 동작**
   - Node의 PodCIDR, ServiceCIDR을 외부 라우터로 광고하는 역할
   - 내부 Pod 간 라우팅을 `eBPF datapath`로 자체 처리

2. **BGP 세션은 GoBGP 기반으로 관리**
   - 세션은 `OPEN`, `KEEPALIVE`, `UPDATE` 단계를 거쳐 성립

3. 다중 NIC 환경에서는 추가 설계가 필요함
   - 실습에서는 ip route add로 경로를 보정했으나 운영 환경에서는 ToR 등 라우터에서 경로를 집약 관리하는 방식이 더 안정적
   - Node 단위 라우팅 수정은 장애 위험이 있어 지양하고, 필요 시 정책 라우팅(ip rule, 분리 테이블)로 NIC별 경로를 명시

4. BGP 패킷 캡처 분석은 핵심 검증 수단임
   - `tcpdump`와 `termshark`로 세션 수립과 업데이트 흐름을 확인함
   - `UPDATE` 메시지의 NLRI를 통해 실제 광고 프리픽스 확인 가능

- **ToR (Top-of-Rack)** : 서버 랙 상단에 설치되는 네트워크 스위치로, 해당 랙 내 서버들과 외부 네트워크를 연결하는 장비

---

## 5. Reference

- [Cilium Docs - BGP Control Plane Resources](https://docs.cilium.io/en/stable/network/bgp-control-plane/bgp-control-plane-v2/)
- [Cilium GitHub - BGP Code](https://github.com/cilium/cilium/tree/main/operator/pkg/bgpv2)
- [ISOVALENT Blog - Connecting your Kubernetes island to your network with Cilium BGP](https://isovalent.com/blog/post/connecting-your-kubernetes-island-to-your-network-with-cilium-bgp)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
