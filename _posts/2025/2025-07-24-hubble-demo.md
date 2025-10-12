---
title: Star Wars Demo와 함께 Cilium Network Policy 알아보기 [Cilium Study 2주차]
date: 2025-07-24 02:02:50 +0900
author: kkamji
categories: [Kubernetes, Cilium]
tags: [kubernetes, devops, hubble, hubble-relay, cilium, star-wars, cilium-study, cloudnet, gasida]     # TAG names should always be lowercase
comments: true
image:
  path: /assets/img/kubernetes/cilium/cilium.webp
---

이번에는 Cilium 공식문서에서 제공하는 **Star Wars Demo**를 진행하며 **Cilium**이 어떻게 동작하는지 알아보도록 하겠습니다.

> - [Cilium Docs - Getting Started with the Star Wars Demo](https://docs.cilium.io/en/stable/gettingstarted/demo/)

### 관련 글

1. [Vagrant와 VirtualBox로 Kubernetes Cluster 구축하기 [Cilium Study 1주차]]({% post_url 2025/2025-07-14-deploy-kubernetes-vagrant-virtualbox %})
2. [Flannel CNI 배포하기 [Cilium Study 1주차]]({% post_url 2025/2025-07-15-deploy-flannel-cni %})
3. [Cilium CNI 알아보기 [Cilium Study 1주차]]({% post_url 2025/2025-07-16-cilium-cni-basic %})
4. [Cilium 구성요소 & 배포하기 (kube-proxy replacement) [Cilium Study 1주차]]({% post_url 2025/2025-07-18-deploy-cilium %})
5. [Cilium Hubble 알아보기 [Cilium Study 2주차]]({% post_url 2025/2025-07-21-hubble-basic %})
6. [Cilium & Hubble Command Cheat Sheet [Cilium Study 2주차]]({% post_url cheat-sheet/2025-07-23-cilium-hubble-cheat-sheet %})
7. [Star Wars Demo와 함께 Cilium Network Policy 알아보기 [Cilium Study 2주차] (현재 글)]({% post_url 2025/2025-07-24-hubble-demo %})
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

## 1. Application Topology 개요

![Star Wars Application Topology](/assets/img/kubernetes/cilium/star-wars-application-topology.webp)
> [Cilium Docs - Getting Started with the Star Wars Demo](https://docs.cilium.io/en/stable/gettingstarted/demo/)

- `deathstar`, `tiefighter`, `xwing` 세 가지 마이크로서비스로 구성됩니다.
- Cilium과 kube-dns가 정상 동작하면 Star Wars Demo 애플리케이션을 배포할 수 있습니다.
- `deathstar`는 80번 포트에서 HTTP 웹서버를 제공하며, Kubernetes Service를 통해 두 개의 pod replica로 트래픽이 로드밸런싱됩니다.
- `tiefighter`와 `xwing`은 각각 제국(Empire)과 동맹(Alliance) 우주선이 착륙 요청을 보내는 클라이언트 역할을 합니다.
- `tiefighter`와 `xwing`에 대해 서로 다른 보안 정책을 적용하고, `deathstar` 착륙 서비스에 대한 접근 제어를 실습할 수 있게 됩니다.

### 1.1. Demo를 통해 확인할 수 있는 내용

1. 서비스 디스커버리와 라벨 셀렉터 이해
   - Service가 Selector로 특정 라벨을 가진 pod만 선택해 트래픽을 전달하는 방식 이해

2. Cilium 네트워크 정책 실습
   - `tiefigher`는 허용되고 `xwing`은 차단되는 예시를 기반으로, `CiliumNetworkPolicy`를 사용한 `L3`/`L4`/`L7` Layer 수준의 접근 제어 확인

3. Observability 확인
   - **Hubble**을 사용해 요청 흐름을 추적, 어떤 정책에 의해 허용 또는 거부되는지 시각화

---

## 2. 편의성 설정

실습의 편의를 위해 아래와 같이 Alias를 생성한 뒤, 진행하도록 하겠습니다.

```bash
# cilium 파드 이름
export CILIUMPOD0=$(kubectl get -l k8s-app=cilium pods -n kube-system --field-selector spec.nodeName=k8s-m1 -o jsonpath='{.items[0].metadata.name}')
export CILIUMPOD1=$(kubectl get -l k8s-app=cilium pods -n kube-system --field-selector spec.nodeName=k8s-w1  -o jsonpath='{.items[0].metadata.name}')
export CILIUMPOD2=$(kubectl get -l k8s-app=cilium pods -n kube-system --field-selector spec.nodeName=k8s-w2  -o jsonpath='{.items[0].metadata.name}')
echo $CILIUMPOD0 $CILIUMPOD1 $CILIUMPOD2

# 단축키(alias) 지정
alias c0="kubectl exec -it $CILIUMPOD0 -n kube-system -c cilium-agent -- cilium"
alias c1="kubectl exec -it $CILIUMPOD1 -n kube-system -c cilium-agent -- cilium"
alias c2="kubectl exec -it $CILIUMPOD2 -n kube-system -c cilium-agent -- cilium"

alias c0bpf="kubectl exec -it $CILIUMPOD0 -n kube-system -c cilium-agent -- bpftool"
alias c1bpf="kubectl exec -it $CILIUMPOD1 -n kube-system -c cilium-agent -- bpftool"
alias c2bpf="kubectl exec -it $CILIUMPOD2 -n kube-system -c cilium-agent -- bpftool"
```

---

## 3. Star Wars Demo 배포

```shell
# 배포
❯ kubectl apply -f https://raw.githubusercontent.com/cilium/cilium/1.17.6/examples/minikube/http-sw-app.yaml
service/deathstar created
deployment.apps/deathstar created
pod/tiefighter created
pod/xwing created

# pod status & labels 확인
❯ kubectl get pod --show-labels
NAME                        READY   STATUS    RESTARTS   AGE   LABELS
deathstar-8c4c77fb7-b9qmw   1/1     Running   0          16s   app.kubernetes.io/name=deathstar,class=deathstar,org=empire,pod-template-hash=8c4c77fb7
deathstar-8c4c77fb7-vhj8x   1/1     Running   0          16s   app.kubernetes.io/name=deathstar,class=deathstar,org=empire,pod-template-hash=8c4c77fb7
tiefighter                  1/1     Running   0          16s   app.kubernetes.io/name=tiefighter,class=tiefighter,org=empire
xwing                       1/1     Running   0          16s   app.kubernetes.io/name=xwing,class=xwing,org=alliance

# deathstar deployment, service, endpoints 확인
❯ kubectl get deploy,svc,ep deathstar
NAME                        READY   UP-TO-DATE   AVAILABLE   AGE
deployment.apps/deathstar   2/2     2            2           55s

NAME                TYPE        CLUSTER-IP     EXTERNAL-IP   PORT(S)   AGE
service/deathstar   ClusterIP   10.233.25.94   <none>        80/TCP    55s

NAME                  ENDPOINTS                          AGE
endpoints/deathstar   10.233.64.96:80,10.233.65.155:80   55s

# ciliumendpoints 확인 (IPV4 -> Pod IP)
❯ kubectl get ciliumendpoints.cilium.io   
NAME                        SECURITY IDENTITY   ENDPOINT STATE   IPV4            IPV6
deathstar-8c4c77fb7-b9qmw   27476               ready            10.233.64.96    
deathstar-8c4c77fb7-vhj8x   27476               ready            10.233.65.155   
tiefighter                  22234               ready            10.233.65.163   
xwing                       42250               ready            10.233.65.156   

## cilium endpoint list 확인  * 현재 ingress/egress에 Policy가 존재 하지 않음
❯ kubectl exec -it -n kube-system ds/cilium -c cilium-agent -- cilium endpoint list
ENDPOINT   POLICY (ingress)   POLICY (egress)   IDENTITY   LABELS (source:key[=value])                                                       IPv6   IPv4            STATUS
           ENFORCEMENT        ENFORCEMENT
88         Disabled           Disabled          12050      k8s:app.kubernetes.io/component=core                                                     10.233.65.8     ready
                                                           k8s:app.kubernetes.io/instance=harbor
                                                           k8s:app.kubernetes.io/managed-by=Helm
                                                           k8s:app.kubernetes.io/name=harbor
                                                           k8s:app.kubernetes.io/part-of=harbor
                                                           k8s:app.kubernetes.io/version=2.12.2
                                                           k8s:app=harbor
                                                           k8s:chart=harbor
                                                           k8s:component=core
                                                           k8s:heritage=Helm
                                                           k8s:io.cilium.k8s.namespace.labels.kubernetes.io/metadata.name=harbor
                                                           k8s:io.cilium.k8s.policy.cluster=default
                                                           k8s:io.cilium.k8s.policy.serviceaccount=default
                                                           k8s:io.kubernetes.pod.namespace=harbor
                                                           k8s:release=harbor
268        Disabled           Disabled          2793       k8s:io.cilium.k8s.namespace.labels.kubernetes.io/metadata.name=kube-system               10.233.65.168   ready
                                                           k8s:io.cilium.k8s.policy.cluster=default
                                                           k8s:io.cilium.k8s.policy.serviceaccount=coredns
                                                           k8s:io.kubernetes.pod.namespace=kube-system
                                                           k8s:k8s-app=kube-dns
441        Disabled           Disabled          1          reserved:host                                                                                            ready
456        Disabled           Disabled          12733      k8s:app.kubernetes.io/instance=external-secrets                                          10.233.65.108   ready
                                                           k8s:app.kubernetes.io/managed-by=Helm
                                                           k8s:app.kubernetes.io/name=external-secrets-cert-controller
                                                           k8s:app.kubernetes.io/version=v0.14.3
                                                           k8s:helm.sh/chart=external-secrets-0.14.3
                                                           k8s:io.cilium.k8s.namespace.labels.kubernetes.io/metadata.name=external-secrets
                                                           k8s:io.cilium.k8s.namespace.labels.name=external-secrets
                                                           k8s:io.cilium.k8s.policy.cluster=default
                                                           k8s:io.cilium.k8s.policy.serviceaccount=external-secrets-cert-controller
                                                           k8s:io.kubernetes.pod.namespace=external-secrets
...
...


## 각 pod가 존재하는 Node의 endpoint list 확인
c0 endpoint list
c1 endpoint list
c2 endpoint list 
```

---

## 4. Check Current Access

**deathstar** 서비스는 `org=empire` 라벨이 붙은 함선만 착륙 요청을 허용해야 합니다.  

하지만 아직 CiliumNetworkPolicy 같은 정책을 적용하지 않았기 때문에, `org=alliance(xwing)`나 `org=empire(tiefighter)` 여부와 관계없이 모든 함선이 착륙을 요청할 수 있습니다.

```shell
## 아래 출력에서 xwing 와 tiefighter 의 IDENTITY 메모
❯ c1 endpoint list | grep -iE 'xwing|tiefighter|deathstar'
786        Disabled           Disabled          27476      k8s:app.kubernetes.io/name=deathstar                                                     10.233.65.155   ready
                                                           k8s:class=deathstar                                                            
1585       Disabled           Disabled          42250      k8s:app.kubernetes.io/name=xwing                                                         10.233.65.156   ready
                                                           k8s:class=xwing                                                                
2501       Disabled           Disabled          22234      k8s:app.kubernetes.io/name=tiefighter                                                    10.233.65.163   ready
                                                           k8s:class=tiefighter                                                           

❯ c2 endpoint list | grep -iE 'xwing|tiefighter|deathstar'
169        Disabled           Disabled          27476      k8s:app.kubernetes.io/name=deathstar                                                       10.233.64.96    ready
                                                           k8s:class=deathstar    

XWING_ID=42250
TIEFIGHTER_ID=22234
DEATHSTAR_ID=27476

# 모니터링 준비 : 터미널 1개
❯ hubble observe -f --identity 42250 --identity 22234 --identity 27476

## xwing -> deathstar
❯ kubectl exec xwing -- curl -s -XPOST deathstar.default.svc.cluster.local/v1/request-landing
Ship landed

## tiefighter -> deathstar
❯ kubectl exec tiefighter -- curl -s -XPOST deathstar.default.svc.cluster.local/v1/request-landing
Ship landed

## 확인 xwing(42250) -> deathstar(27476)
Jul 25 13:21:11.765: default/xwing:59516 (ID:42250) -> 169.254.25.10:53 (host) to-stack FORWARDED (UDP)
Jul 25 13:21:11.765: default/xwing:59516 (ID:42250) <- 169.254.25.10:53 (host) to-endpoint FORWARDED (UDP)
Jul 25 13:21:11.765: 169.254.25.10:53 (host) <> default/xwing (ID:42250) pre-xlate-rev TRACED (UDP)
Jul 25 13:21:11.766: 169.254.25.10:53 (host) <> default/xwing (ID:42250) pre-xlate-rev TRACED (UDP)
Jul 25 13:21:11.766: default/xwing:56675 (ID:42250) -> 169.254.25.10:53 (host) to-stack FORWARDED (UDP)
Jul 25 13:21:11.767: 169.254.25.10:53 (host) <> default/xwing (ID:42250) pre-xlate-rev TRACED (UDP)
Jul 25 13:21:11.767: default/xwing:56675 (ID:42250) <- 169.254.25.10:53 (host) to-endpoint FORWARDED (UDP)
Jul 25 13:21:11.767: 169.254.25.10:53 (host) <> default/xwing (ID:42250) pre-xlate-rev TRACED (UDP)
Jul 25 13:21:11.767: default/xwing:46192 (ID:42250) -> 169.254.25.10:53 (host) to-stack FORWARDED (UDP)
Jul 25 13:21:11.768: default/xwing:46192 (ID:42250) <- 169.254.25.10:53 (host) to-endpoint FORWARDED (UDP)
Jul 25 13:21:11.768: 169.254.25.10:53 (host) <> default/xwing (ID:42250) pre-xlate-rev TRACED (UDP)
Jul 25 13:21:11.769: 169.254.25.10:53 (host) <> default/xwing (ID:42250) pre-xlate-rev TRACED (UDP)
Jul 25 13:21:11.769: default/xwing:38587 (ID:42250) -> 169.254.25.10:53 (host) to-stack FORWARDED (UDP)
Jul 25 13:21:11.769: default/xwing:38587 (ID:42250) <- 169.254.25.10:53 (host) to-endpoint FORWARDED (UDP)
Jul 25 13:21:11.769: 169.254.25.10:53 (host) <> default/xwing (ID:42250) pre-xlate-rev TRACED (UDP)
Jul 25 13:21:11.770: 169.254.25.10:53 (host) <> default/xwing (ID:42250) pre-xlate-rev TRACED (UDP)
Jul 25 13:21:11.771: default/xwing (ID:42250) <> 10.233.25.94:80 (world) pre-xlate-fwd TRACED (TCP)
Jul 25 13:21:11.771: default/xwing (ID:42250) <> default/deathstar-8c4c77fb7-vhj8x:80 (ID:27476) post-xlate-fwd TRANSLATED (TCP)
Jul 25 13:21:11.771: default/xwing:55456 (ID:42250) -> default/deathstar-8c4c77fb7-vhj8x:80 (ID:27476) to-endpoint FORWARDED (TCP Flags: SYN)
Jul 25 13:21:11.771: default/xwing:55456 (ID:42250) <- default/deathstar-8c4c77fb7-vhj8x:80 (ID:27476) to-endpoint FORWARDED (TCP Flags: SYN, ACK)
Jul 25 13:21:11.771: default/xwing:55456 (ID:42250) -> default/deathstar-8c4c77fb7-vhj8x:80 (ID:27476) to-endpoint FORWARDED (TCP Flags: ACK)
Jul 25 13:21:11.771: default/deathstar-8c4c77fb7-vhj8x:80 (ID:27476) <> default/xwing (ID:42250) pre-xlate-rev TRACED (TCP)
Jul 25 13:21:11.771: 10.233.25.94:80 (world) <> default/xwing (ID:42250) post-xlate-rev TRANSLATED (TCP)
Jul 25 13:21:11.771: default/deathstar-8c4c77fb7-vhj8x:80 (ID:27476) <> default/xwing (ID:42250) pre-xlate-rev TRACED (TCP)
Jul 25 13:21:11.771: 10.233.25.94:80 (world) <> default/xwing (ID:42250) post-xlate-rev TRANSLATED (TCP)
Jul 25 13:21:11.771: default/xwing:55456 (ID:42250) -> default/deathstar-8c4c77fb7-vhj8x:80 (ID:27476) to-endpoint FORWARDED (TCP Flags: ACK, PSH)
Jul 25 13:21:11.771: default/xwing:55456 (ID:42250) <> default/deathstar-8c4c77fb7-vhj8x (ID:27476) pre-xlate-rev TRACED (TCP)
Jul 25 13:21:11.774: default/xwing:55456 (ID:42250) <> default/deathstar-8c4c77fb7-vhj8x (ID:27476) pre-xlate-rev TRACED (TCP)
Jul 25 13:21:11.774: default/xwing:55456 (ID:42250) <> default/deathstar-8c4c77fb7-vhj8x (ID:27476) pre-xlate-rev TRACED (TCP)
Jul 25 13:21:11.775: default/xwing:55456 (ID:42250) <> default/deathstar-8c4c77fb7-vhj8x (ID:27476) pre-xlate-rev TRACED (TCP)
Jul 25 13:21:11.775: default/xwing:55456 (ID:42250) <> default/deathstar-8c4c77fb7-vhj8x (ID:27476) pre-xlate-rev TRACED (TCP)
Jul 25 13:21:11.775: default/xwing:55456 (ID:42250) <- default/deathstar-8c4c77fb7-vhj8x:80 (ID:27476) to-endpoint FORWARDED (TCP Flags: ACK, PSH)
Jul 25 13:21:11.775: default/xwing:55456 (ID:42250) -> default/deathstar-8c4c77fb7-vhj8x:80 (ID:27476) to-endpoint FORWARDED (TCP Flags: ACK, FIN)
Jul 25 13:21:11.775: default/xwing:55456 (ID:42250) <- default/deathstar-8c4c77fb7-vhj8x:80 (ID:27476) to-endpoint FORWARDED (TCP Flags: ACK, FIN)
Jul 25 13:21:11.775: default/xwing:55456 (ID:42250) -> default/deathstar-8c4c77fb7-vhj8x:80 (ID:27476) to-endpoint FORWARDED (TCP Flags: ACK)

## 확인 tiefighter(ID:22234) -> deathstar(27476)
Jul 25 13:21:15.569: default/tiefighter:34076 (ID:22234) -> 169.254.25.10:53 (host) to-stack FORWARDED (UDP)
Jul 25 13:21:15.569: 169.254.25.10:53 (host) <> default/tiefighter (ID:22234) pre-xlate-rev TRACED (UDP)
Jul 25 13:21:15.569: 169.254.25.10:53 (host) <> default/tiefighter (ID:22234) pre-xlate-rev TRACED (UDP)
Jul 25 13:21:15.569: default/tiefighter:54684 (ID:22234) -> 169.254.25.10:53 (host) to-stack FORWARDED (UDP)
Jul 25 13:21:15.569: default/tiefighter:34076 (ID:22234) <- 169.254.25.10:53 (host) to-endpoint FORWARDED (UDP)
Jul 25 13:21:15.569: default/tiefighter:54684 (ID:22234) <- 169.254.25.10:53 (host) to-endpoint FORWARDED (UDP)
Jul 25 13:21:15.569: 169.254.25.10:53 (host) <> default/tiefighter (ID:22234) pre-xlate-rev TRACED (UDP)
Jul 25 13:21:15.569: 169.254.25.10:53 (host) <> default/tiefighter (ID:22234) pre-xlate-rev TRACED (UDP)
Jul 25 13:21:15.569: default/tiefighter:54126 (ID:22234) -> 169.254.25.10:53 (host) to-stack FORWARDED (UDP)
Jul 25 13:21:15.570: default/tiefighter:54126 (ID:22234) <- 169.254.25.10:53 (host) to-endpoint FORWARDED (UDP)
Jul 25 13:21:15.570: 169.254.25.10:53 (host) <> default/tiefighter (ID:22234) pre-xlate-rev TRACED (UDP)
Jul 25 13:21:15.570: 169.254.25.10:53 (host) <> default/tiefighter (ID:22234) pre-xlate-rev TRACED (UDP)
Jul 25 13:21:15.570: default/tiefighter:60542 (ID:22234) -> 169.254.25.10:53 (host) to-stack FORWARDED (UDP)
Jul 25 13:21:15.570: default/tiefighter:60542 (ID:22234) <- 169.254.25.10:53 (host) to-endpoint FORWARDED (UDP)
Jul 25 13:21:15.570: 169.254.25.10:53 (host) <> default/tiefighter (ID:22234) pre-xlate-rev TRACED (UDP)
Jul 25 13:21:15.570: 169.254.25.10:53 (host) <> default/tiefighter (ID:22234) pre-xlate-rev TRACED (UDP)
Jul 25 13:21:15.571: default/tiefighter (ID:22234) <> 10.233.25.94:80 (world) pre-xlate-fwd TRACED (TCP)
Jul 25 13:21:15.571: default/tiefighter (ID:22234) <> default/deathstar-8c4c77fb7-b9qmw:80 (ID:27476) post-xlate-fwd TRANSLATED (TCP)
Jul 25 13:21:15.571: default/tiefighter:53314 (ID:22234) -> default/deathstar-8c4c77fb7-b9qmw:80 (ID:27476) to-network FORWARDED (TCP Flags: SYN)
Jul 25 13:21:15.571: 10.0.0.201:53314 (remote-node) -> default/deathstar-8c4c77fb7-b9qmw:80 (ID:27476) to-endpoint FORWARDED (TCP Flags: SYN)
Jul 25 13:21:15.571: 10.0.0.201:53314 (remote-node) <- default/deathstar-8c4c77fb7-b9qmw:80 (ID:27476) to-network FORWARDED (TCP Flags: SYN, ACK)
Jul 25 13:21:15.571: default/tiefighter:53314 (ID:22234) <- default/deathstar-8c4c77fb7-b9qmw:80 (ID:27476) to-endpoint FORWARDED (TCP Flags: SYN, ACK)
Jul 25 13:21:15.571: default/tiefighter:53314 (ID:22234) -> default/deathstar-8c4c77fb7-b9qmw:80 (ID:27476) to-network FORWARDED (TCP Flags: ACK)
Jul 25 13:21:15.571: 10.0.0.201:53314 (remote-node) -> default/deathstar-8c4c77fb7-b9qmw:80 (ID:27476) to-endpoint FORWARDED (TCP Flags: ACK)
Jul 25 13:21:15.571: 10.0.0.201:53314 (remote-node) <> default/deathstar-8c4c77fb7-b9qmw (ID:27476) pre-xlate-rev TRACED (TCP)
Jul 25 13:21:15.571: default/deathstar-8c4c77fb7-b9qmw:80 (ID:27476) <> default/tiefighter (ID:22234) pre-xlate-rev TRACED (TCP)
Jul 25 13:21:15.571: 10.233.25.94:80 (world) <> default/tiefighter (ID:22234) post-xlate-rev TRANSLATED (TCP)
Jul 25 13:21:15.571: default/deathstar-8c4c77fb7-b9qmw:80 (ID:27476) <> default/tiefighter (ID:22234) pre-xlate-rev TRACED (TCP)
Jul 25 13:21:15.571: 10.233.25.94:80 (world) <> default/tiefighter (ID:22234) post-xlate-rev TRANSLATED (TCP)
Jul 25 13:21:15.571: default/tiefighter:53314 (ID:22234) -> default/deathstar-8c4c77fb7-b9qmw:80 (ID:27476) to-network FORWARDED (TCP Flags: ACK, PSH)
Jul 25 13:21:15.572: default/tiefighter:53314 (ID:22234) <- default/deathstar-8c4c77fb7-b9qmw:80 (ID:27476) to-endpoint FORWARDED (TCP Flags: ACK, PSH)
Jul 25 13:21:15.572: 10.0.0.201:53314 (remote-node) -> default/deathstar-8c4c77fb7-b9qmw:80 (ID:27476) to-endpoint FORWARDED (TCP Flags: ACK, PSH)
Jul 25 13:21:15.572: 10.0.0.201:53314 (remote-node) <> default/deathstar-8c4c77fb7-b9qmw (ID:27476) pre-xlate-rev TRACED (TCP)
Jul 25 13:21:15.572: 10.0.0.201:53314 (remote-node) <> default/deathstar-8c4c77fb7-b9qmw (ID:27476) pre-xlate-rev TRACED (TCP)
Jul 25 13:21:15.572: 10.0.0.201:53314 (remote-node) <> default/deathstar-8c4c77fb7-b9qmw (ID:27476) pre-xlate-rev TRACED (TCP)
Jul 25 13:21:15.572: 10.0.0.201:53314 (remote-node) <> default/deathstar-8c4c77fb7-b9qmw (ID:27476) pre-xlate-rev TRACED (TCP)
Jul 25 13:21:15.572: 10.0.0.201:53314 (remote-node) <- default/deathstar-8c4c77fb7-b9qmw:80 (ID:27476) to-network FORWARDED (TCP Flags: ACK, PSH)
Jul 25 13:21:15.573: default/tiefighter:53314 (ID:22234) -> default/deathstar-8c4c77fb7-b9qmw:80 (ID:27476) to-network FORWARDED (TCP Flags: ACK, FIN)
Jul 25 13:21:15.573: 10.0.0.201:53314 (remote-node) -> default/deathstar-8c4c77fb7-b9qmw:80 (ID:27476) to-endpoint FORWARDED (TCP Flags: ACK, FIN)
Jul 25 13:21:15.573: 10.0.0.201:53314 (remote-node) <- default/deathstar-8c4c77fb7-b9qmw:80 (ID:27476) to-network FORWARDED (TCP Flags: ACK, FIN)
Jul 25 13:21:15.573: default/tiefighter:53314 (ID:22234) <- default/deathstar-8c4c77fb7-b9qmw:80 (ID:27476) to-endpoint FORWARDED (TCP Flags: ACK, FIN)
Jul 25 13:21:15.573: default/tiefighter:53314 (ID:22234) -> default/deathstar-8c4c77fb7-b9qmw:80 (ID:27476) to-network FORWARDED (TCP Flags: ACK)
Jul 25 13:21:15.573: 10.0.0.201:53314 (remote-node) -> default/deathstar-8c4c77fb7-b9qmw:80 (ID:27476) to-endpoint FORWARDED (TCP Flags: ACK)
```

### 4.1. Traffic Flow 해석

| 시각     | 주체(엔드포인트 ID)                           | 행위                             | 의미                                                                       |
| -------- | --------------------------------------------- | -------------------------------- | -------------------------------------------------------------------------- |
| 13:21:11 | **xwing (42250)** -> `169.254.25.10:53`       | `to-stack / to‑endpoint` UDP     | xwing Pod가 **NodeLocal DNS**(169.254.25.10)로 A/AAAA 쿼리 전송, 응답 수신 |
| 13:21:11 | xwing (42250) -> `10.233.25.94:80`            | `pre‑xlate‑fwd TRACED`           | **Service IP**(deathstar)로 나가는 패킷을 캡처 (NAT 전)                    |
| 13:21:11 | xwing (42250) -> deathstar‑vhj8x (27476)      | `post‑xlate‑fwd TRANSLATED`      | 서비스 IP -> Pod IP로 **NAT** 완료                                         |
| 13:21:11 | xwing <-> deathstar                           | `FORWARDED` TCP(SYN,ACK,PSH,FIN) | 3‑way handshake, 데이터 전송, 종료까지 **정상 연결**                       |
| 13:21:15 | **tiefighter (22234)** -> `169.254.25.10:53`  | DNS 쿼리/응답                    | tiefighter도 동일                                                          |
| 13:21:15 | tiefighter (22234) -> deathstar‑b9qmw (27476) | `to-network / to-endpoint` TCP   | Worker Node1 (`10.0.0.201`) 경유 후 deathstar Pod까지 정상 통신            |

---

## 5. L3/L4 Network Policy 적용 및 테스트

Cilium을 사용하고 Network Policy를 정의할 때, Endpoint IP는 중요하지 않습니다. Cilium에서는 Endpoint IP가 아닌 Pod 레이블을 기준으로 트래픽을 식별합니다. `EndpointSelector`로 대상 Pod를 지정하고, `fromEndpoints`로 허용할 소스 Pod를 지정합니다.

이번에는 `org=empire` 레이블이 있는 `tiefighter`만 `deathstar`의 80/TCP 포트에 접근하도록 허용해보겠습니다. 해당 경우 `org=alliance` 레이블의 `xwing`은 차단됩니다.

Cilium은 stateful connection tracking을 수행합니다. Frontend -> Backend 방향이 허용되면, 같은 TCP/UDP 세션의 응답 패킷도 자동으로 허용됩니다. -> 리턴 패킷 자동 허용

### 5.1. Cilium 및 Kubernetes를 사용한 L4 Network Policy 생성

![L4 Layer Policy](/assets/img/kubernetes/cilium/l4_layer_policy.webp)
> [L4 Layer Policy](https://docs.cilium.io/en/stable/gettingstarted/demo/)

```shell
## Network Policy 생성
apiVersion: "cilium.io/v2"
kind: CiliumNetworkPolicy
metadata:
  name: "rule1"
spec:
  description: "L3-L4 policy to restrict deathstar access to empire ships only"
  endpointSelector:
    matchLabels:
      org: empire
      class: deathstar
  ingress:
  - fromEndpoints:
    - matchLabels:
        org: empire
    toPorts:
    - ports:
      - port: "80"
        protocol: TCP

❯ kubectl apply -f https://raw.githubusercontent.com/cilium/cilium/1.17.6/examples/minikube/sw_l3_l4_policy.yaml

## Network Policy 생성 확인
❯ kubectl get cnp
NAME    AGE   VALID
rule1   38s   True

## Network Policy 설정 확인
❯ k describe cnp rule1
Name:         rule1
Namespace:    default
Labels:       <none>
Annotations:  <none>
API Version:  cilium.io/v2
Kind:         CiliumNetworkPolicy
Metadata:
  Creation Timestamp:  2025-07-26T04:49:46Z
  Generation:          1
  Resource Version:    51853112
  UID:                 f4bf08f4-dd1b-4994-9490-579384037a74
Spec:
  Description:  L3-L4 policy to restrict deathstar access to empire ships only
  Endpoint Selector:
    Match Labels:
      Class:  deathstar
      Org:    empire
  Ingress:
    From Endpoints:
      Match Labels:
        Org:  empire
    To Ports:
      Ports:
        Port:      80
        Protocol:  TCP
Status:
  Conditions:
    Last Transition Time:  2025-07-26T04:49:46Z
    Message:               Policy validation succeeded
    Status:                True
    Type:                  Valid
Events:                    <none>

❯ c1 endpoint list

ENDPOINT   POLICY (ingress)   POLICY (egress)   IDENTITY   LABELS (source:key[=value])                                                       IPv6   IPv4            STATUS
...
786        Enabled            Disabled          27476      k8s:app.kubernetes.io/name=deathstar                                                     10.233.65.155   ready
                                                           k8s:class=deathstar                                                                      
                                                           k8s:io.cilium.k8s.namespace.labels.kubernetes.io/metadata.name=default                   
                                                           k8s:io.cilium.k8s.policy.cluster=default                                                 
                                                           k8s:io.cilium.k8s.policy.serviceaccount=default                                          
                                                           k8s:io.kubernetes.pod.namespace=default                                                  
                                                           k8s:org=empire                                                                           
#


## 모니터링
❯ hubble observe -f --type drop
Jul 26 06:30:51.003: default/xwing:35810 (ID:42250) <> default/deathstar-8c4c77fb7-vhj8x:80 (ID:27476) Policy denied DROPPED (TCP Flags: SYN)
Jul 26 06:30:52.030: default/xwing:35810 (ID:42250) <> default/deathstar-8c4c77fb7-vhj8x:80 (ID:27476) Policy denied DROPPED (TCP Flags: SYN)

## 접속 확인 (성공) tiefighter(22234) -> deathstar(27476))
❯ kubectl exec tiefighter -- curl -s -XPOST deathstar.default.svc.cluster.local/v1/request-landing
Ship landed

## 접속 확인 (실패) xwing(42250) -> deathstar(27476)
❯ kubectl exec xwing -- curl -s -XPOST deathstar.default.svc.cluster.local/v1/request-landing
command terminated with exit code 28
```

![XWing Dropped](/assets/img/kubernetes/cilium/xwing_dropped.webp)

---

## 6. L7 Network Policy(HTTP-aware) 적용 및 테스트

마이크로서비스 간 최소 권한 원칙을 지키기 위해서는 L3/L4 수준의 허용 여부만으로는 부족할 수 있습니다. 더 나은 보안을 위해서는 특정 HTTP 메서드와 경로까지 제한해야 합니다. 예시로 `deathstar` 서비스에는 관리 목적의 **API**(`/v1/exhaust-port` 등)가 존재하며, 임의의 함선이 호출해서는 안 됩니다.

> L7 동작 처리는 cilium-envoy 데몬셋이 담당 합니다.  
{: .prompt-danger}

![Life of a Packet](/assets/img/kubernetes/cilium/life_of_a_packet_intgress.webp)

> - [Cilium Docs - Life of a Packet](https://docs.cilium.io/en/stable/network/ebpf/lifeofapacket/)

### 6.1. 허용되지 않은 요청 확인

```shell
# tiefighter에서 허용되지 않은 PUT 요청 실행 (정책 적용 전)
❯ kubectl exec tiefighter -- curl -s -XPUT deathstar.default.svc.cluster.local/v1/exhaust-port
Panic: deathstar exploded

goroutine 1 [running]:
main.HandleGarbage(0x2080c3f50, 0x2, 0x4, 0x425c0, 0x5, 0xa)
        /code/src/github.com/empire/deathstar/
        temp/main.go:9 +0x64
main.main()
        /code/src/github.com/empire/deathstar/
        temp/main.go:5 +0x85
```

> 정책이 없을 때는 위와 같은 민감한 엔드포인트가 호출되어 문제가 발생할 수 있습니다.
{: .prompt-danger}

### 6.2. L7 정책 YAML

![L7 Layer Policy](/assets/img/kubernetes/cilium/cilium_l7_layer_policy.webp)
> [L7 Layer Policy](https://docs.cilium.io/en/stable/gettingstarted/demo/)

**Cilium**은 HTTP 계층(L7 Layer) 정책을 적용하여 `tiefighter`가 접근할 수 있는 URL을 제한할 수 있습니다. 아래 정책은 기존 L3/L4 정책(rule1)을 확장하여, `tiefighter`가 `POST /v1/request-landing` 요청만 보낼 수 있도록 제한합니다. 다른 모든 HTTP 호출(ex: `PUT /v1/exhaust-port`)은 차단됩니다.

```shell
apiVersion: "cilium.io/v2"
kind: CiliumNetworkPolicy
metadata:
  name: "rule1"
spec:
  description: "L7 policy to restrict access to specific HTTP call"
  endpointSelector:
    matchLabels:
      org: empire
      class: deathstar
  ingress:
  - fromEndpoints:
    - matchLabels:
        org: empire
    toPorts:
    - ports:
      - port: "80"
        protocol: TCP
      rules:
        http:
        - method: "POST"
          path: "/v1/request-landing"
## L7 Layer Network Policy 생성 (위와 동일)
❯ kubectl apply -f https://raw.githubusercontent.com/cilium/cilium/1.17.6/examples/minikube/sw_l3_l4_l7_policy.yaml
ciliumnetworkpolicy.cilium.io/rule1 configured

## Monitoring 
❯ hubble observe -f --pod deathstar --verdict DROPPED

## tiefighter -> deathstar/v1/request-landing (POST Request)
❯ kubectl exec tiefighter -- curl -s -XPOST deathstar.default.svc.cluster.local/v1/request-landing
Ship landed

## tiefighter -> deathstart/v1/exhaust-port (PUT Request)
❯ kubectl exec tiefighter -- curl -s -XPUT deathstar.default.svc.cluster.local/v1/exhaust-port
Access denied

## 모니터링 로그 (API 경로 & HTTP METHOD까지 확인 가능)
Jul 26 06:57:12.949: default/tiefighter:33338 (ID:22234) -> default/deathstar-8c4c77fb7-vhj8x:80 (ID:27476) http-request DROPPED (HTTP/1.1 PUT http://deathstar.default.svc.cluster.local/v1/exhaust-port)

❯ kubectl exec xwing -- curl -s -XPOST deathstar.default.svc.cluster.local/v1/request-landing
## ... Timeout

## 모니터링 로그 (계속 DROP)
Jul 26 06:57:33.511: default/xwing:56934 (ID:42250) <> default/deathstar-8c4c77fb7-vhj8x:80 (ID:27476) Policy denied DROPPED (TCP Flags: SYN)
Jul 26 06:57:34.526: default/xwing:56934 (ID:42250) <> default/deathstar-8c4c77fb7-vhj8x:80 (ID:27476) policy-verdict:none INGRESS DENIED (TCP Flags: SYN)
Jul 26 06:57:34.526: default/xwing:56934 (ID:42250) <> default/deathstar-8c4c77fb7-vhj8x:80 (ID:27476) Policy denied DROPPED (TCP Flags: SYN)
Jul 26 06:57:35.550: default/xwing:56934 (ID:42250) <> default/deathstar-8c4c77fb7-vhj8x:80 (ID:27476) policy-verdict:none INGRESS DENIED (TCP Flags: SYN)
Jul 26 06:57:35.550: default/xwing:56934 (ID:42250) <> default/deathstar-8c4c77fb7-vhj8x:80 (ID:27476) Policy denied DROPPED (TCP Flags: SYN)
...

## 정책 확인
❯ kubectl describe ciliumnetworkpolicies
Name:         rule1
Namespace:    default
Labels:       <none>
Annotations:  <none>
API Version:  cilium.io/v2
Kind:         CiliumNetworkPolicy
Metadata:
  Creation Timestamp:  2025-07-26T04:49:46Z
  Generation:          2
  Resource Version:    51872136
  UID:                 f4bf08f4-dd1b-4994-9490-579384037a74
Spec:
  Description:  L7 policy to restrict access to specific HTTP call
  Endpoint Selector:
    Match Labels:
      Class:  deathstar
      Org:    empire
  Ingress:
    From Endpoints:
      Match Labels:
        Org:  empire
    To Ports:
      Ports:
        Port:      80
        Protocol:  TCP
      Rules:
        Http:
          Method:  POST
          Path:    /v1/request-landing
Status:
  Conditions:
    Last Transition Time:  2025-07-26T04:49:46Z
    Message:               Policy validation succeeded
    Status:                True
    Type:                  Valid
Events:                    <none>

# cilium CLI로 확인 (cilium-dbg)
kubectl -n kube-system exec <cilium-pod> -- cilium-dbg policy get
```

![L7 Layer Hubble Dropped](/assets/img/kubernetes/cilium/l7_layer_hubble_dropped.webp)

---

## 7. 삭제

```shell
❯ kubectl delete -f https://raw.githubusercontent.com/cilium/cilium/1.17.6/examples/minikube/http-sw-app.yaml
service "deathstar" deleted
deployment.apps "deathstar" deleted
pod "tiefighter" deleted
pod "xwing" deleted

❯ kubectl delete cnp rule1
ciliumnetworkpolicy.cilium.io "rule1" deleted
```

---

## 8. 마무리

- L3/L4 정책은 IP, 포트, 프로토콜 수준만 제어합니다. L7 정책을 통해 HTTP 메서드와 경로까지 제한할 수 있습니다.
- 최소 권한 원칙을 적용하려면 서비스가 실제로 사용하는 엔드포인트만 허용해야 합니다.
- Cilium은 stateful connection tracking을 수행하므로 응답 패킷은 자동 허용됩니다.
- kubectl describe, cilium-dbg policy get, cilium-dbg monitor, hubble observe --verdict drop --http 등의 도구를 조합해 정책 적용 여부를 검증합니다.

---

## 9. Reference

- [Cilium Docs - Getting Started with the Star Wars Demo](https://docs.cilium.io/en/stable/gettingstarted/demo/)
- [Cilium Docs - Life of a Packet](https://docs.cilium.io/en/stable/network/ebpf/lifeofapacket/)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
