---
title: Cilium & Hubble Command Cheat Sheet [Cilium Study 2주차]
date: 2025-07-23 20:41:55 +0900
author: kkamji
categories: [Kubernetes, Cilium]
tags: [kubernetes, devops, hubble, cilium, cilium-study, cloudnet, cheat-sheet]     # TAG names should always be lowercase
comments: true
image:
  path: /assets/img/kubernetes/cilium/cilium.webp
---

Cilium과 Hubble을 공부하며 알게된 CLI 명령어들을 공유합니다.

### 관련 글

1. [Vagrant와 VirtualBox로 Kubernetes Cluster 구축하기 [Cilium Study 1주차]]({% post_url 2025/2025-07-14-deploy-kubernetes-vagrant-virtualbox %})
2. [Flannel CNI 배포하기 [Cilium Study 1주차]]({% post_url 2025/2025-07-15-deploy-flannel-cni %})
3. [Cilium CNI 알아보기 [Cilium Study 1주차]]({% post_url 2025/2025-07-16-cilium-cni-basic %})
4. [Cilium 구성요소 & 배포하기 (kube-proxy replacement) [Cilium Study 1주차]]({% post_url 2025/2025-07-18-deploy-cilium %})
5. [Cilium Hubble 알아보기 [Cilium Study 2주차]]({% post_url 2025/2025-07-21-hubble-basic %})
6. [Cilium & Hubble Command Cheat Sheet [Cilium Study 2주차] (현재 글)]({% post_url cheat-sheet/2025-07-23-cilium-hubble-commands %})
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

## 1. 편의성 설정

```shell
hubble {command} -P                                  # 단발성: 명령 실행 시 자동 포트포워드
hubble config set port-forward true                  # 모든 hubble 명령에 -P 기본 적용
cilium hubble port-forward &                         # 지속적 포워드: 로컬 4245 유지
export HUBBLE_SERVER=localhost:4245                  # hubble 기본 서버 주소 설정(환경 변수)
```

---

## 2. 확인 명령어

```shell
cilium status                                        # Cilium 상태 요약
cilium status --verbose                              # 상세 상태 및 버전/오류 출력
cilium config view                                   # Cilium 런타임 설정 확인
kubectl get ciliumnodes.cilium.io -A                 # 노드별 CiliumNode 리소스 조회
kubectl get ciliumnode -o json | grep podCIDRs -A2   # 각 노드 PodCIDR 확인
kubectl get ciliumendpoints.cilium.io -A             # SECURITY IDENTITY 포함 CEP 목록
```

### 2.1 cilium-dbg commands

```shell
kubectl exec -n kube-system -c cilium-agent -it ds/cilium -- cilium-dbg status --verbose  # 상세 상태/헬스 체크
kubectl exec -n kube-system -c cilium-agent -it ds/cilium -- cilium-dbg metrics list      # Prometheus 메트릭 목록
kubectl exec -n kube-system -c cilium-agent -it ds/cilium -- cilium-dbg config           # 런타임 설정 조회

# 실시간 패킷/이벤트 모니터
kubectl exec -n kube-system -c cilium-agent -it ds/cilium -- cilium-dbg monitor           # 기본 모니터
kubectl exec -n kube-system -c cilium-agent -it ds/cilium -- cilium-dbg monitor -v        # 상세 출력(라벨 등)
kubectl exec -n kube-system -c cilium-agent -it ds/cilium -- cilium-dbg monitor -v -v     # 페이로드 디섹션 포함
kubectl exec -n kube-system -c cilium-agent -it ds/cilium -- cilium-dbg monitor --related-to=<id>  # 특정 Endpoint 관련 이벤트만
kubectl exec -n kube-system -c cilium-agent -it ds/cilium -- cilium-dbg monitor --type drop         # 드롭 패킷만 표시
kubectl exec -n kube-system -c cilium-agent -it ds/cilium -- cilium-dbg monitor -v -v --hex         # 페이로드를 Hex로 출력
kubectl exec -n kube-system -c cilium-agent -it ds/cilium -- cilium-dbg monitor -v --type l7         # L7(HTTP/gRPC 등) 이벤트만
```

---

## 3. Hubble Commands

```shell
hubble status                                        # Relay/Agent 헬스 체크, 플로우 카운트 확인
hubble config view                                   # 현재 hubble CLI 설정 확인
hubble config set server <addr:port>                 # 기본 서버 주소 설정
hubble observe                                       # 실시간 플로우 출력(기본)
hubble observe -f                                    # follow 모드(스트림)
hubble observe --type drop                           # 드롭 이벤트만 출력 (`--verdict DROPPED`와 동일)
hubble observe --verdict DROPPED --verdict ERROR     # 드롭되거나 오류가 발생한 플로우 필터링
hubble observe --protocol http                       # HTTP 이벤트만 출력
hubble observe --http-status "500"                   # 특정 HTTP 상태 코드(500) 필터링
hubble observe --http-status "4.."                   # 4xx 범위의 HTTP 상태 코드 필터링
hubble observe --since 5m                            # 지난 5분 동안의 플로우 조회
hubble observe --from-pod ns/pod --to-pod ns/pod     # 특정 Pod 간 흐름 필터링
hubble observe -f --pod {namespace}/{podname}        # 특정 Pod가 포함된 흐름 필터링 (source or destination)
hubble observe -f --label {k8s:class}={classname}    # 특정 라벨을 가진 Pod 간의 흐름 필터링
hubble observe -f --from-identity {IDENTITY_ID}      # 특정 ID에서 시작되는 흐름 필터링
hubble observe -f --identity {IDENTITY_ID}           # 특정 Security Identity 간의 흐름 필터링
hubble observe --to-fqdn cilium.io                   # 특정 FQDN으로 향하는 플로우 필터링
hubble observe -o json                               # JSON 형식으로 플로우 출력
hubble observe --print-raw-filters                   # 적용된 필터가 gRPC API에서 어떻게 해석되는지 출력 (디버깅용)
hubble observe -h                                    # observe 옵션 도움말
hubble ui                                            # Hubble UI 로컬 실행(포트포워드 필요 시 -P)
```

---

## 4. Cilium Pod 변수/별칭 설정

```shell
# Cilium 파드 이름 변수 설정 (환경에 맞게 노드 이름 수정)
export CILIUMPOD0=$(kubectl get -l k8s-app=cilium pods -n kube-system --field-selector spec.nodeName=k8s-m1 -o jsonpath='{.items[0].metadata.name}')
export CILIUMPOD1=$(kubectl get -l k8s-app=cilium pods -n kube-system --field-selector spec.nodeName=k8s-w1  -o jsonpath='{.items[0].metadata.name}')
export CILIUMPOD2=$(kubectl get -l k8s-app=cilium pods -n kube-system --field-selector spec.nodeName=k8s-w2  -o jsonpath='{.items[0].metadata.name}')
echo $CILIUMPOD0 $CILIUMPOD1 $CILIUMPOD2

# 단축키(alias) 지정 (cilium / bpftool)
alias c0="kubectl exec -it $CILIUMPOD0 -n kube-system -c cilium-agent -- cilium"
alias c1="kubectl exec -it $CILIUMPOD1 -n kube-system -c cilium-agent -- cilium"
alias c2="kubectl exec -it $CILIUMPOD2 -n kube-system -c cilium-agent -- cilium"

alias c0bpf="kubectl exec -it $CILIUMPOD0 -n kube-system -c cilium-agent -- bpftool"
alias c1bpf="kubectl exec -it $CILIUMPOD1 -n kube-system -c cilium-agent -- bpftool"
alias c2bpf="kubectl exec -it $CILIUMPOD2 -n kube-system -c cilium-agent -- bpftool"
```

---

## 5. Cilium Agent Commands (별칭 사용)

### 5.1 Endpoint

```shell
# 각 노드의 Endpoint 목록 확인
c0 endpoint list
c1 endpoint list

# Endpoint 목록을 JSON 형식으로 출력
c0 endpoint list -o json

# 특정 Endpoint의 상세 정보 확인
c0 endpoint get <id>

# 특정 Endpoint의 로그 확인
c0 endpoint log <id>

# 특정 Endpoint의 디버그 모드 활성화
c1 endpoint config <id> Debug=true
```

### 5.2 Monitor

```shell
# 실시간 이벤트 모니터링
c1 monitor

# 상세 정보와 함께 모니터링 (L3/L4 정보 포함)
c1 monitor -v

# 가장 상세한 정보와 함께 모니터링 (파싱된 페이로드 포함)
c1 monitor -v -v

# 특정 Endpoint와 관련된 이벤트만 필터링
c1 monitor --related-to <id>

# Drop된 패킷 이벤트만 필터링
c1 monitor --type drop

# 페이로드를 Hex 형식으로 출력
c1 monitor -v -v --hex

# L7(HTTP, Kafka 등) 트래픽 정보 필터링
c1 monitor -v --type l7
```

### 5.3 Service & LoadBalancer

```shell
# LoadBalancer 서비스 목록 확인
c0 service list
c1 service list

# BPF 레벨의 LoadBalancer 정보 확인
c0 bpf lb list
c1 bpf lb list

# Reverse NAT (SNAT) 항목 확인
c0 bpf lb list --revnat
c1 bpf lb list --revnat
```

### 5.4 Connection Tracking (CT)

```shell
# Connection Tracking 항목 확인
c0 bpf ct list global
c1 bpf ct list global

# 모든 Connection Tracking 항목 삭제
c0 bpf ct flush global
```

### 5.5 NAT

```shell
# NAT 테이블 매핑 항목 확인
c0 bpf nat list
c1 bpf nat list
c2 bpf nat list

# 모든 NAT 테이블 매핑 항목 삭제
c0 bpf nat flush
c1 bpf nat flush
c2 bpf nat flush
```

### 5.6 IP / Identity / Policy

```shell
# IP와 연결된 Endpoint/Identity 정보 확인
c0 ip list

# IPCache (IP <-> Identity 매핑) 확인
c0 bpf ipcache list

# 모든 Security Identity 목록 확인
c0 identity list

# 적용된 모든 Policy 확인
c0 bpf policy get --all
```

### 5.7 BPF Maps & Cgroups

```shell
# 관리 중인 cgroup 메타데이터 확인
c0 cgroups list
c1 cgroups list
c2 cgroups list

# 열려있는 BPF map 목록 확인
c0 map list
c1 map list --verbose

# 특정 BPF map의 실시간 이벤트 확인
c1 map events cilium_lb4_services_v2
c1 map events cilium_lxc
c1 map events cilium_ipcache
```

### 5.8 StateDB

```shell
# StateDB 전체를 JSON으로 덤프
c0 statedb dump
```

---

## 6. Trouble Shooting

```shell
cilium sysdump --output /tmp/sysdump.tgz              # 문제 발생 시 전체 진단 번들 수집
cilium connectivity test                              # 기본 연결성 테스트(테스트 리소스 생성 후 검증)
```

---

## 7. Reference

- [Cilium Docs - Command Cheatsheet](https://docs.cilium.io/en/stable/cheatsheet/)
- [Cilium Docs - Command Reference](https://docs.cilium.io/en/stable/cmdref/)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
