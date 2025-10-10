---
title: Cilium Native Routing 통신 확인 및 문제 해결 – Static Route & BGP [Cilium Study 4주차]
date: 2025-08-10 07:14:41 +0900
author: kkamji
categories: [Kubernetes, Cilium]
tags: [kubernetes, devops, cilium, cilium-study, cloudnet, routing]
comments: true
image:
  path: /assets/img/kubernetes/cilium/cilium.webp
---

지난 글 [Cilium Network Routing 이해하기 – Encapsulation과 Native Routing 비교 [Cilium Study 3주차]]({% post_url 2025/2025-08-03-cilium-routing %})에서는 Native Routing 모드에서 **각 노드/라우터가 다른 노드의 PodCIDR 경로를 알고 있어야 한다**는 점을 살펴봤습니다.  

이번 시간에는 실제로 **PodCIDR 간 라우팅이 설정되지 않았을 때 어떤 문제가 발생하는지**를 실습 환경에서 확인하고, `tcpdump`로 그 흐름을 분석한 뒤 **Static Route와 BGP를 통한 해결 방법**을 다뤄보겠습니다.

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
14. [Cilium Native Routing 통신 확인 및 문제 해결 – Static Route & BGP [Cilium Study 4주차] (현재 글)]({% post_url 2025/2025-08-10-cilium-native-routing %})
15. [Cilium BGP Control Plane [Cilium Study 5주차]]({% post_url 2025/2025-08-11-cilium-bgp-control-plane %})
16. [Cilium Service LoadBalancer BGP Advertisement & ExternalTrafficPolicy [Cilium Study 5주차]]({% post_url 2025/2025-08-12-cilium-lb-ipam %})
17. [Kind로 Kubernetes Cluster 배포하기 [Cilium Study 5주차]]({% post_url 2025/2025-08-13-kind %})
18. [Cilium Cluster Mesh [Cilium Study 5주차]]({% post_url 2025/2025-08-14-cilium-cluster-mesh %})
19. [Cilium Service Mesh [Cilium Study 6주차]]({% post_url 2025/2025-08-18-cilium-service-mesh %})
20. [Kube-burner 소개 및 실습 [Cilium Study 7주차]]({% post_url 2025/2025-08-25-kube-burner %})
21. [Cilium Network Security [Cilium Study 8주차]]({% post_url 2025/2025-09-03-cilium-network-security %})

---

## 1. 실습 환경

![4W Lab Environment](/assets/img/kubernetes/cilium/4w-lab-environment.webp)

- ControlPlane: `k8s-ctr`
- Worker Node: `k8s-w0`, `k8s-w1` (서로 다른 네트워크 대역)
- Router: VM (PodCIDR 라우팅 설정 X)
- Cilium: Native Routing 모드 활성화
- PodCIDR: `172.20.0.0/16` (노드별 /24 분리)

---

## 2. PodCIDR 라우팅을 설정하지 않았을 때 문제 확인

### 2.1. Sample Application 배포

```shell
# 샘플 애플리케이션 배포
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

# Sample Application 배포 확인
(⎈|HomeLab:N/A) root@k8s-ctr:~# k get po,svc -o wide
NAME                          READY   STATUS    RESTARTS   AGE   IP             NODE      NOMINATED NODE   READINESS GATES
pod/curl-pod                  1/1     Running   0          55s   172.20.0.95    k8s-ctr   <none>           <none>
pod/webpod-697b545f57-85dkh   1/1     Running   0          55s   172.20.0.238   k8s-ctr   <none>           <none>
pod/webpod-697b545f57-9lpt4   1/1     Running   0          55s   172.20.2.249   k8s-w0    <none>           <none>
pod/webpod-697b545f57-zjp55   1/1     Running   0          55s   172.20.1.154   k8s-w1    <none>           <none>

NAME                 TYPE        CLUSTER-IP    EXTERNAL-IP   PORT(S)   AGE     SELECTOR
service/kubernetes   ClusterIP   10.96.0.1     <none>        443/TCP   5h19m   <none>
service/webpod       ClusterIP   10.96.54.60   <none>        80/TCP    56s     app=webpod
```

### 2.2. curl-pod -> webpod 통신 확인

```shell
(⎈|HomeLab:N/A) root@k8s-ctr:~# kubectl exec -it curl-pod -- sh -c 'while true; do curl -s --connect-timeout 1 webpod | grep Hostname; echo "---"; sleep 1; done'
Hostname: webpod-697b545f57-85dkh
---
Hostname: webpod-697b545f57-zjp55
---
Hostname: webpod-697b545f57-zjp55
---
---
```

- 동일 네트워크(`192.168.10.0/24`)에 존재하는 Pod와 **통신 가능**
- 다른 네트워크(`192.168.20.0/24`)에 존재하는 Pod와 **통신 실패**

---

## 3. tcpdump를 사용해 패킷 흐름 확인

### 3.1. 통신 테스트 및 패킷 캡처

Router에서 `tcpdump`를 사용해, **curl-pod -> 다른 네트워크 대역의 노드에 존재하는 webpod** 통신이 왜 실패하는지 확인해보겠습니다.

```shell
# 통신 확인
(⎈|HomeLab:N/A) root@k8s-ctr:~# kubectl exec -it curl-pod -- sh -c 'while true; do curl -s --connect-timeout 1 webpod | grep Hostname; echo "---" ; sleep 1; done'
Hostname: webpod-697b545f57-85dkh
---
---
...

# k8s-w0 노드에 배포된 webpod 파드 IP 지정
(⎈|HomeLab:N/A) root@k8s-ctr:~# export WEBPOD=$(kubectl get pod -l app=webpod --field-selector spec.nodeName=k8s-w0 -o jsonpath='{.items[0].status.podIP}')
(⎈|HomeLab:N/A) root@k8s-ctr:~# echo $WEBPOD
172.20.2.249

# 신규 터미널로 Router VM 접속 후 tcpdump를 사용해 모든 인터페이스의 ICMP 패킷 캡처
root@router:~# tcpdump -i any icmp -nn
tcpdump: data link type LINUX_SLL2
tcpdump: verbose output suppressed, use -v[v]... for full protocol decode
listening on any, link-type LINUX_SLL2 (Linux cooked v2), snapshot length 262144 bytes
07:43:25.829375 eth1  In  IP 172.20.0.95 > 172.20.2.249: ICMP echo request, id 151, seq 1, length 64
07:43:25.829391 eth0  Out IP 172.20.0.95 > 172.20.2.249: ICMP echo request, id 151, seq 1, length 64

# k8s-w0 노드에 배포된 webpod로 ping (아래에서 tcpdump를 켜둔 상태에서)
(⎈|HomeLab:N/A) root@k8s-ctr:~# kubectl exec -it curl-pod -- ping -c 2 -w 1 -W 1 $WEBPOD
PING 172.20.2.249 (172.20.2.249) 56(84) bytes of data.

--- 172.20.2.249 ping statistics ---
1 packets transmitted, 0 received, 100% packet loss, time 0ms

command terminated with exit code 1
```

### 3.2. 패킷 캡처 분석

```shell
22:08:20.123415 eth1  In  IP 172.20.0.89 > 172.20.2.36: ICMP echo request, id 345, seq 1, length 64
22:08:20.123495 eth0  Out IP 172.20.0.89 > 172.20.2.36: ICMP echo request, id 345, seq 1, length 64
```

1. eth1 In: 클러스터 내부망 인터페이스(eth1)로 패킷이 유입됨
2. eth0 Out: 하지만 목적지 PodCIDR(172.20.2.0/24)에 대한 라우팅 경로가 없어, Router는 기본 경로(default route)를 사용 -> eth0(public NIC)로 패킷 송출
3. 이 경로는 클러스터 외부망(public)으로 연결되므로, 대상 Pod까지 도달 불가 -> **응답 실패**

### 3.3. Routing Table 확인

아래와 같이 `ip -c route` 명령어를 통해 Router VM의 Routing Table 정보를 확인하고 `ip route get 172.20.2.36` 명령어로 해당 라우팅 경로를 확인했을 때, PodCIDR 트래픽이 public 경로로 나가는 구조임을 알 수 있습니다. (`10.0.2.15`는 Router의 외부 Gateway 주소임)

```shell
# Routing Table 정보 확인
root@router:~# ip -c route
default via 10.0.2.2 dev eth0 proto dhcp src 10.0.2.15 metric 100
10.0.2.0/24 dev eth0 proto kernel scope link src 10.0.2.15 metric 100
10.0.2.2 dev eth0 proto dhcp scope link src 10.0.2.15 metric 100
10.0.2.3 dev eth0 proto dhcp scope link src 10.0.2.15 metric 100
10.10.1.0/24 dev loop1 proto kernel scope link src 10.10.1.200
10.10.2.0/24 dev loop2 proto kernel scope link src 10.10.2.200
192.168.10.0/24 dev eth1 proto kernel scope link src 192.168.10.200
192.168.20.0/24 dev eth2 proto kernel scope link src 192.168.20.200

# 라우팅 경로 확인
root@router:~# ip route get 172.20.2.36
172.20.2.36 via 10.0.2.2 dev eth0 src 10.0.2.15 uid 0
    cache
```

---

## 4. Hubble을 사용해 Flow Log 확인

아래의 Flow Log를 확인했을 때, 다음과 같은 내용을 확인할 수 있습니다.

1. 동일 네트워크에 존재하는 Pod로 보낸 요청 -> `TCP 3-way handshake` 정상 완료
2. 다른 네트워크에 존재하는 Pod로 보낸 요청 -> SYN 송신 후 응답 없음

```shell
# Terminal-1 (Hubble)

## 1. Hubble 명령어 사용을 위한 포트포워딩 및 status 확인
cilium hubble port-forward &
hubble status

## 2. hubble observe 를 사용한 flow log 확인
(⎈|HomeLab:N/A) root@k8s-ctr:~# hubble observe -f --protocol tcp --pod curl-pod
Aug  9 22:59:28.481 [hubble-relay-5b48c999f9-mcd7l]: 1 nodes are unavailable: k8s-w0
Aug  9 22:59:32.196: default/curl-pod (ID:31109) <> 10.96.54.60:80 (world) pre-xlate-fwd TRACED (TCP)
Aug  9 22:59:32.196: default/curl-pod (ID:31109) <> default/webpod-697b545f57-9lpt4:80 (ID:9214) post-xlate-fwd TRANSLATED (TCP)
Aug  9 22:59:32.198: default/curl-pod:39306 (ID:31109) -> default/webpod-697b545f57-9lpt4:80 (ID:9214) to-network FORWARDED (TCP Flags: SYN)
Aug  9 22:59:34.202: default/curl-pod (ID:31109) <> 10.96.54.60:80 (world) pre-xlate-fwd TRACED (TCP)
Aug  9 22:59:34.202: default/curl-pod (ID:31109) <> default/webpod-697b545f57-9lpt4:80 (ID:9214) post-xlate-fwd TRANSLATED (TCP)
Aug  9 22:59:34.203: default/curl-pod:39316 (ID:31109) -> default/webpod-697b545f57-9lpt4:80 (ID:9214) to-network FORWARDED (TCP Flags: SYN)
Aug  9 22:59:35.907: default/curl-pod:38926 (ID:31109) -> default/webpod-697b545f57-zjp55:80 (ID:9214) to-endpoint FORWARDED (TCP Flags: SYN)
Aug  9 22:59:35.908: default/curl-pod:38926 (ID:31109) <- default/webpod-697b545f57-zjp55:80 (ID:9214) to-network FORWARDED (TCP Flags: SYN, ACK)
Aug  9 22:59:35.910: default/curl-pod:38926 (ID:31109) -> default/webpod-697b545f57-zjp55:80 (ID:9214) to-endpoint FORWARDED (TCP Flags: ACK)
Aug  9 22:59:35.910: default/curl-pod:38926 (ID:31109) -> default/webpod-697b545f57-zjp55:80 (ID:9214) to-endpoint FORWARDED (TCP Flags: ACK, PSH)
Aug  9 22:59:35.910: default/curl-pod:38926 (ID:31109) <> default/webpod-697b545f57-zjp55 (ID:9214) pre-xlate-rev TRACED (TCP)
Aug  9 22:59:35.911: default/curl-pod:38926 (ID:31109) <> default/webpod-697b545f57-zjp55 (ID:9214) pre-xlate-rev TRACED (TCP)
Aug  9 22:59:35.911: default/curl-pod:38926 (ID:31109) <> default/webpod-697b545f57-zjp55 (ID:9214) pre-xlate-rev TRACED (TCP)
Aug  9 22:59:35.912: default/curl-pod:38926 (ID:31109) <> default/webpod-697b545f57-zjp55 (ID:9214) pre-xlate-rev TRACED (TCP)
Aug  9 22:59:35.913: default/curl-pod:38926 (ID:31109) <> default/webpod-697b545f57-zjp55 (ID:9214) pre-xlate-rev TRACED (TCP)
Aug  9 22:59:35.913: default/curl-pod:38926 (ID:31109) <- default/webpod-697b545f57-zjp55:80 (ID:9214) to-network FORWARDED (TCP Flags: ACK, PSH)
Aug  9 22:59:35.916: default/curl-pod:38926 (ID:31109) -> default/webpod-697b545f57-zjp55:80 (ID:9214) to-endpoint FORWARDED (TCP Flags: ACK, FIN)
Aug  9 22:59:35.916: default/curl-pod:38926 (ID:31109) <- default/webpod-697b545f57-zjp55:80 (ID:9214) to-network FORWARDED (TCP Flags: ACK, FIN)
Aug  9 22:59:35.918: default/curl-pod:38926 (ID:31109) -> default/webpod-697b545f57-zjp55:80 (ID:9214) to-endpoint FORWARDED (TCP Flags: ACK)
Aug  9 22:59:36.214: default/curl-pod (ID:31109) <> 10.96.54.60:80 (world) pre-xlate-fwd TRACED (TCP)
Aug  9 22:59:36.214: default/curl-pod (ID:31109) <> default/webpod-697b545f57-zjp55:80 (ID:9214) post-xlate-fwd TRANSLATED (TCP)
Aug  9 22:59:36.214: default/curl-pod:38926 (ID:31109) -> default/webpod-697b545f57-zjp55:80 (ID:9214) to-network FORWARDED (TCP Flags: SYN)
Aug  9 22:59:36.216: default/curl-pod:38926 (ID:31109) <- default/webpod-697b545f57-zjp55:80 (ID:9214) to-endpoint FORWARDED (TCP Flags: SYN, ACK)
Aug  9 22:59:36.217: default/curl-pod:38926 (ID:31109) -> default/webpod-697b545f57-zjp55:80 (ID:9214) to-network FORWARDED (TCP Flags: ACK)
Aug  9 22:59:36.217: default/curl-pod:38926 (ID:31109) -> default/webpod-697b545f57-zjp55:80 (ID:9214) to-network FORWARDED (TCP Flags: ACK, PSH)
Aug  9 22:59:36.222: default/curl-pod:38926 (ID:31109) <- default/webpod-697b545f57-zjp55:80 (ID:9214) to-endpoint FORWARDED (TCP Flags: ACK, PSH)
Aug  9 22:59:36.223: default/curl-pod:38926 (ID:31109) -> default/webpod-697b545f57-zjp55:80 (ID:9214) to-network FORWARDED (TCP Flags: ACK, FIN)
Aug  9 22:59:36.225: default/curl-pod:38926 (ID:31109) <- default/webpod-697b545f57-zjp55:80 (ID:9214) to-endpoint FORWARDED (TCP Flags: ACK, FIN)
Aug  9 22:59:36.225: default/curl-pod:38926 (ID:31109) -> default/webpod-697b545f57-zjp55:80 (ID:9214) to-network FORWARDED (TCP Flags: ACK)
Aug  9 22:59:36.934: default/curl-pod:38936 (ID:31109) -> default/webpod-697b545f57-zjp55:80 (ID:9214) to-endpoint FORWARDED (TCP Flags: SYN)
Aug  9 22:59:36.934: default/curl-pod:38936 (ID:31109) <- default/webpod-697b545f57-zjp55:80 (ID:9214) to-network FORWARDED (TCP Flags: SYN, ACK)
Aug  9 22:59:36.936: default/curl-pod:38936 (ID:31109) -> default/webpod-697b545f57-zjp55:80 (ID:9214) to-endpoint FORWARDED (TCP Flags: ACK, PSH)
Aug  9 22:59:36.936: default/curl-pod:38936 (ID:31109) <> default/webpod-697b545f57-zjp55 (ID:9214) pre-xlate-rev TRACED (TCP)
Aug  9 22:59:36.936: default/curl-pod:38936 (ID:31109) <> default/webpod-697b545f57-zjp55 (ID:9214) pre-xlate-rev TRACED (TCP)
Aug  9 22:59:36.937: default/curl-pod:38936 (ID:31109) <> default/webpod-697b545f57-zjp55 (ID:9214) pre-xlate-rev TRACED (TCP)
Aug  9 22:59:36.937: default/curl-pod:38936 (ID:31109) <> default/webpod-697b545f57-zjp55 (ID:9214) pre-xlate-rev TRACED (TCP)
Aug  9 22:59:36.938: default/curl-pod:38936 (ID:31109) <> default/webpod-697b545f57-zjp55 (ID:9214) pre-xlate-rev TRACED (TCP)
Aug  9 22:59:36.938: default/curl-pod:38936 (ID:31109) <- default/webpod-697b545f57-zjp55:80 (ID:9214) to-network FORWARDED (TCP Flags: ACK, PSH)
Aug  9 22:59:36.940: default/curl-pod:38936 (ID:31109) -> default/webpod-697b545f57-zjp55:80 (ID:9214) to-endpoint FORWARDED (TCP Flags: ACK, FIN)
Aug  9 22:59:36.941: default/curl-pod:38936 (ID:31109) <- default/webpod-697b545f57-zjp55:80 (ID:9214) to-network FORWARDED (TCP Flags: ACK, FIN)
Aug  9 22:59:36.942: default/curl-pod:38936 (ID:31109) -> default/webpod-697b545f57-zjp55:80 (ID:9214) to-endpoint FORWARDED (TCP Flags: ACK)
Aug  9 22:59:37.240: default/curl-pod (ID:31109) <> 10.96.54.60:80 (world) pre-xlate-fwd TRACED (TCP)
Aug  9 22:59:37.240: default/curl-pod (ID:31109) <> default/webpod-697b545f57-zjp55:80 (ID:9214) post-xlate-fwd TRANSLATED (TCP)
Aug  9 22:59:37.241: default/curl-pod:38936 (ID:31109) -> default/webpod-697b545f57-zjp55:80 (ID:9214) to-network FORWARDED (TCP Flags: SYN)
Aug  9 22:59:37.242: default/curl-pod:38936 (ID:31109) <- default/webpod-697b545f57-zjp55:80 (ID:9214) to-endpoint FORWARDED (TCP Flags: SYN, ACK)
Aug  9 22:59:37.242: default/curl-pod:38936 (ID:31109) -> default/webpod-697b545f57-zjp55:80 (ID:9214) to-network FORWARDED (TCP Flags: ACK, PSH)
Aug  9 22:59:37.246: default/curl-pod:38936 (ID:31109) <- default/webpod-697b545f57-zjp55:80 (ID:9214) to-endpoint FORWARDED (TCP Flags: ACK, PSH)
Aug  9 22:59:37.247: default/curl-pod:38936 (ID:31109) -> default/webpod-697b545f57-zjp55:80 (ID:9214) to-network FORWARDED (TCP Flags: ACK, FIN)
Aug  9 22:59:37.251: default/curl-pod:38936 (ID:31109) <- default/webpod-697b545f57-zjp55:80 (ID:9214) to-endpoint FORWARDED (TCP Flags: ACK, FIN)
Aug  9 22:59:37.251: default/curl-pod:38936 (ID:31109) -> default/webpod-697b545f57-zjp55:80 (ID:9214) to-network FORWARDED (TCP Flags: ACK)

# Terminal-2 (트래픽 발생)
## Pod Status 확인
(⎈|HomeLab:N/A) root@k8s-ctr:~# k get po -o wide
NAME                      READY   STATUS    RESTARTS   AGE   IP             NODE      NOMINATED NODE   READINESS GATES
curl-pod                  1/1     Running   0          29m   172.20.0.95    k8s-ctr   <none>           <none>
webpod-697b545f57-85dkh   1/1     Running   0          29m   172.20.0.238   k8s-ctr   <none>           <none>
webpod-697b545f57-9lpt4   1/1     Running   0          29m   172.20.2.249   k8s-w0    <none>           <none>
webpod-697b545f57-zjp55   1/1     Running   0          29m   172.20.1.154   k8s-w1    <none>           <none>

## 트래픽 발생
(⎈|HomeLab:N/A) root@k8s-ctr:~# kubectl exec -it curl-pod -- sh -c 'while true; do curl -s --connect-timeout 1 webpod | grep Hostname; echo "---" ; sleep 1; done'
---
---
Hostname: webpod-697b545f57-zjp55
---
Hostname: webpod-697b545f57-zjp55
---
```

---

## 5. Static Routing을 추가해 문제 해결

아래와 같이 Router VM에서 PodCIDR에 대한 Routing 경로를 수동으로 추가한 뒤, 통신을 확인해보겠습니다.

```shell
# Routing 경로 추가
root@router:~# ip route add 172.20.2.0/24 via 192.168.20.100

# Routing Table 확인
root@router:~# ip -c route
default via 10.0.2.2 dev eth0 proto dhcp src 10.0.2.15 metric 100
10.0.2.0/24 dev eth0 proto kernel scope link src 10.0.2.15 metric 100
10.0.2.2 dev eth0 proto dhcp scope link src 10.0.2.15 metric 100
10.0.2.3 dev eth0 proto dhcp scope link src 10.0.2.15 metric 100
10.10.1.0/24 dev loop1 proto kernel scope link src 10.10.1.200
10.10.2.0/24 dev loop2 proto kernel scope link src 10.10.2.200
172.20.2.0/24 via 192.168.20.100 dev eth2
192.168.10.0/24 dev eth1 proto kernel scope link src 192.168.10.200
192.168.20.0/24 dev eth2 proto kernel scope link src 192.168.20.200

# 통신 확인 (k8s-w0 노드에 존재하는 Pod -> webpod-697b545f57-9lpt4)
(⎈|HomeLab:N/A) root@k8s-ctr:~# kubectl exec -it curl-pod -- sh -c 'while true; do curl -s --connect-timeout 1 webpod | grep Hostname; echo "---" ; sleep 1; done'
Hostname: webpod-697b545f57-9lpt4
---
Hostname: webpod-697b545f57-9lpt4
---
Hostname: webpod-697b545f57-9lpt4
---
Hostname: webpod-697b545f57-9lpt4
---
Hostname: webpod-697b545f57-85dkh
---
Hostname: webpod-697b545f57-zjp55
---
Hostname: webpod-697b545f57-zjp55
---
Hostname: webpod-697b545f57-zjp55
---
Hostname: webpod-697b545f57-85dkh
---
Hostname: webpod-697b545f57-85dkh
---
Hostname: webpod-697b545f57-9lpt4
---
Hostname: webpod-697b545f57-zjp55
---
Hostname: webpod-697b545f57-85dkh
---
Hostname: webpod-697b545f57-zjp55
---
Hostname: webpod-697b545f57-9lpt4
---
```

---

## 6. BGP Routing

앞서 설명한 Static Routing 방식은 노드 수가 늘어날수록 운영 부담이 커집니다. 특히 노드 교체나 네트워크 대역 변경 시 수동 라우트 추가·삭제가 필요하므로, 실제 운영 환경에서는 BGP(Border Gateway Protocol)를 통한 동적 라우팅을 사용하는 것이 좋습니다.  

Cilium은 BGP Control Plane 기능을 제공하여, 각 노드가 자신의 `PodCIDR`를 외부 라우터에 자동으로 광고(announce)할 수 있도록 지원합니다. 이를 통해 라우터가 모든 노드의 `PodCIDR`를 자동 학습하고, 경로를 최신 상태로 유지합니다.

### 6.1. BGP Control Plane 활성화

```shell
helm upgrade cilium cilium/cilium \
  --namespace kube-system \
  --set bgpControlPlane.enabled=true
```

### 6.2. BGP 설정 예시

```yaml
apiVersion: cilium.io/v2alpha1
kind: CiliumBGPClusterConfig
metadata:
  name: bgp-cluster
spec:
  virtualRouters:
    - localASN: 65001
      neighbors:
        - peerAddress: 192.168.10.200
          peerASN: 65002
      serviceSelector:
        matchExpressions:
          - { key: some-key, operator: Exists }
---
apiVersion: cilium.io/v2alpha1
kind: CiliumBGPNodeConfig
metadata:
  name: bgp-node-k8s-ctr
spec:
  node: k8s-ctr
  virtualRouters:
    - localASN: 65001
      neighbors:
        - peerAddress: 192.168.10.200
          peerASN: 65002
      exportPodCIDR: true
```

---

## 7. Reference

- [Cilium Docs - Routing](https://docs.cilium.io/en/stable/network/concepts/routing/)
- [BGP Control Plane Resources](https://docs.cilium.io/en/latest/network/bgp-control-plane/bgp-control-plane-v2/)
- [Cilium BGP Control Plane](https://docs.cilium.io/en/latest/network/bgp-control-plane/bgp-control-plane)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
