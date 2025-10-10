---
title: Flannel CNI 배포하기 [Cilium Study 1주차]
date: 2025-07-15 19:41:29 +0900
author: kkamji
categories: [Kubernetes, Cilium]
tags: [kubernetes, devops, flannel, cilium, cilium-study, cloudnet]     # TAG names should always be lowercase
comments: true
image:
  path: /assets/img/kubernetes/kubernetes.webp
---

이번 포스트에서는 `Flannel CNI`를 Kubernetes Cluster에 배포해보도록 하겠습니다.

### 관련 글

1. [Vagrant와 VirtualBox로 Kubernetes Cluster 구축하기 [Cilium Study 1주차]]({% post_url 2025/2025-07-14-deploy-kubernetes-vagrant-virtualbox %})
2. [Flannel CNI 배포하기 [Cilium Study 1주차] (현재 글)]({% post_url 2025/2025-07-15-deploy-flannel-cni %})
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
18. [Cilium Cluster Mesh [Cilium Study 5주차]]({% post_url 2025/2025-08-14-cilium-cluster-mesh %})
19. [Cilium Service Mesh [Cilium Study 6주차]]({% post_url 2025/2025-08-18-cilium-service-mesh %})
20. [Kube-burner 소개 및 실습 [Cilium Study 7주차]]({% post_url 2025/2025-08-25-kube-burner %})

---

## 1. Flannel 배포 전 확인

```bash
#################################
# 클러스터 네트워크 대역 정보 확인
#################################
❯ kubectl cluster-info dump | grep -m 2 -E "cluster-cidr|service-cluster-ip-range" 
                            "--service-cluster-ip-range=10.96.0.0/16",
                            "--cluster-cidr=10.244.0.0/16",   

#################################
# 코어DNS 파드 상태 및 스케줄링 노드 확인 
#################################
# 현재 cni가 존재하지 않기 때문에 coredns가 pod ip를 할당 받지 못해 Pending 상태
❯ kubectl get pod -n kube-system -l k8s-app=kube-dns -o wide 
NAME                       READY   STATUS    RESTARTS   AGE   IP       NODE     NOMINATED NODE   READINESS GATES
coredns-674b8bbfcf-mrnbj   0/1     Pending   0          61m   <none>   <none>   <none>           <none>
coredns-674b8bbfcf-mx96v   0/1     Pending   0          61m   <none>   <none>   <none>           <none>

#################################
# 네트워크 확인 명령어들
#################################
# 네트워크 인터페이스 상태 출력
ip -c link   # 모든 네트워크 인터페이스 목록과 상태(UP/DOWN) 확인

# 라우팅 테이블 출력
ip -c route   # 현재 노드의 라우팅 테이블(네트워크 경로) 확인

# Linux 브리지 정보 출력
brctl show   # 브리지 인터페이스 및 연결된 포트 확인

# 현재 iptables 전체 룰 덤프
iptables-save   # filter, nat, mangle 등 모든 테이블의 룰을 일괄 덤프

# NAT 테이블 규칙 확인
iptables -t nat -S   # NAT 테이블의 SNAT/DNAT 규칙 목록 출력

# FILTER 테이블 규칙 확인
iptables -t filter -S   # 필터링 테이블의 INPUT, FORWARD, OUTPUT 체인 룰 출력

# MANGLE 테이블 규칙 확인
iptables -t mangle -S   # 패킷 마킹이나 TTL 조작 등의 MANGLE 테이블 규칙 출력

# CNI 설정 파일 구조 확인
tree /etc/cni/net.d/   # 설치된 CNI 플러그인 설정 파일 목록 및 디렉터리 구조 확인 (비어있음)
```

---

## 2. Flannel CNI 배포하기

이전 글에서 확인한 바와 같이 eth0 Interface는 VirtualBox의 NAT 네트워크 모드로 동작하기 위해 사용되기 때문에, flannel이 eth1을 사용하도록 수정했습니다.

```bash
#################################
# flannel cni 배포 전 네임스페이스 및 privileged 정책을 허용하는 레이블 설정
#################################
kubectl create ns kube-flannel
kubectl label --overwrite ns kube-flannel pod-security.kubernetes.io/enforce=privileged

#################################
# Helm을 Repository 추가 및 최신 버전, value 확인
#################################
helm repo add flannel https://flannel-io.github.io/flannel/
helm repo list
helm search repo flannel
helm show values flannel/flannel

#################################
# k8s 관련 트래픽 통신 동작하는 NIC 지정 (eth1번 지정)
#################################
cat << EOF > flannel-values.yaml
podCidr: "10.244.0.0/16"

flannel:
  args:
  - "--ip-masq"
  - "--kube-subnet-mgr"
  - "--iface=eth1"  
EOF

#################################
# helm 설치
#################################
helm install flannel --namespace kube-flannel flannel/flannel -f flannel-values.yaml
helm list -A

# Pod Status 확인
kubectl get pod -n kube-flannel -l app=flannel
# NIC 지정 Argument와 event 확인
kubectl describe pod -n kube-flannel -l app=flannel

#################################
# flannel 확인 (Control Plane Node 에서)
#################################
tree /opt/cni/bin/ 
tree /etc/cni/net.d/
cat /etc/cni/net.d/10-flannel.conflist | jq
❯ kubectl describe cm -n kube-flannel kube-flannel-cfg
...
net-conf.json:
----
{
  "Network": "10.244.0.0/16",
  "EnableNFTables": false,
  "Backend": {
    "Type": "vxlan"
  }
}

#################################
# 설치 전과 비교
#################################
ip -c link # flannel interface 추가
❯ ip -c route | grep 10.244.
...
10.244.0.0/24 dev cni0 proto kernel scope link src 10.244.0.1 
10.244.1.0/24 via 10.244.1.0 dev flannel.1 onlink 
10.244.2.0/24 via 10.244.2.0 dev flannel.1 onlink 

# 통신 확인
ping -c 1 10.244.1.0 
ping -c 1 10.244.2.0

brctl show
iptables-save
iptables -t nat -S
iptables -t filter -S

# k8s-w1, k8s-w2 정보 확인 (NIC & bridge Network 확인)
for i in w1 w2 ; do echo ">> node : cilium-$i <<"; sshpass -p 'vagrant' ssh -o StrictHostKeyChecking=no vagrant@cilium-$i ip -c link ; echo; done
for i in w1 w2 ; do echo ">> node : cilium-$i <<"; sshpass -p 'vagrant' ssh -o StrictHostKeyChecking=no vagrant@cilium-$i ip -c route ; echo; done
for i in w1 w2 ; do echo ">> node : cilium-$i <<"; sshpass -p 'vagrant' ssh -o StrictHostKeyChecking=no vagrant@cilium-$i brctl show ; echo; done
for i in w1 w2 ; do echo ">> node : cilium-$i <<"; sshpass -p 'vagrant' ssh -o StrictHostKeyChecking=no vagrant@cilium-$i sudo iptables -t nat -S ; echo; done
```

---

## 3. Sample Application 배포 및 확인

```bash
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

## crictl로 현재 어떤 컨테이너가 떠있는지 확인
crictl ps
for i in w1 w2 ; do echo ">> node : cilium-$i <<"; sshpass -p 'vagrant' ssh vagrant@cilium-$i sudo crictl ps ; echo; done
```

---

## 4. 통신 확인

```bash
❯ kubectl get pod -l app=webpod -o wide
NAME                      READY   STATUS    RESTARTS   AGE   IP           NODE        NOMINATED NODE   READINESS GATES
webpod-697b545f57-5sx89   1/1     Running   0          10m   10.244.1.4   cilium-w1   <none>           <none>
webpod-697b545f57-gjl4j   1/1     Running   0          10m   10.244.2.2   cilium-w2   <none>           <none>

❯ POD1IP=10.244.1.4
❯ kubectl exec -it curl-pod -- curl $POD1IP
Hostname: webpod-697b545f57-5sx89
IP: 127.0.0.1
IP: ::1
IP: 10.244.1.4
IP: fe80::d0a5:c6ff:fea0:e861
RemoteAddr: 10.244.0.2:53908
GET / HTTP/1.1
Host: 10.244.1.4
User-Agent: curl/8.14.1
Accept: */*

❯ kubectl get svc,ep webpod
❯ kubectl exec -it curl-pod -- curl webpod
❯ kubectl exec -it curl-pod -- curl webpod | grep Hostname
❯ kubectl exec -it curl-pod -- sh -c 'while true; do curl -s webpod | grep Hostname; sleep 1; done'
Hostname: webpod-697b545f57-5sx89
Hostname: webpod-697b545f57-gjl4j
Hostname: webpod-697b545f57-5sx89
Hostname: webpod-697b545f57-5sx89
Hostname: webpod-697b545f57-gjl4j
Hostname: webpod-697b545f57-gjl4j

# Service 동작 처리에 iptables 규칙 활용 확인 >> Service 가 100개 , 1000개 , 10000개 증가 되면???
❯ kubectl get svc webpod -o jsonpath="{.spec.clusterIP}"
10.96.216.5
❯ SVCIP=$(kubectl get svc webpod -o jsonpath="{.spec.clusterIP}")
❯ iptables -t nat -S | grep $SVCIP
-A KUBE-SERVICES -d 10.96.216.58/32 -p tcp -m comment --comment "default/webpod cluster IP" -m tcp --dport 80 -j KUBE-SVC-CNZCPOCNCNOROALA
-A KUBE-SVC-CNZCPOCNCNOROALA ! -s 10.244.0.0/16 -d 10.96.216.58/32 -p tcp -m comment --comment "default/webpod cluster IP" -m tcp --dport 80 -j KUBE-MARK-MASQ
❯ for i in w1 w2 ; do echo ">> node : cilium-$i <<"; sshpass -p 'vagrant' ssh -o StrictHostKeyChecking=no vagrant@cilium-$i sudo iptables -t nat -S | grep $SVCIP ; echo; done
```

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
