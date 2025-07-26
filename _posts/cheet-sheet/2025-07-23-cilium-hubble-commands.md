---
title: Cilium & Hubble Command Cheet Sheet [Cilium Study 2주차]
date: 2025-07-23 20:41:55 +0900
author: kkamji
categories: [Kubernetes]
tags: [kubernetes, devops, hubble, cilium, cilium-study, cloudnet]     # TAG names should always be lowercase
comments: true
image:
  path: /assets/img/kubernetes/cilium/cilium.webp
---

Cilium과 Hubble을 공부하며 알게된 CLI 명령어들을 공유합니다.

### 관련 글

1. [Vagrant와 VirtualBox로 Kubernetes 클러스터 구축하기 [Cilium Study 1주차]]({% post_url 2025/2025-07-14-deploy-kubernetes-vagrant-virtualbox %})
2. [Flannel CNI 배포하기 [Cilium Study 1주차]]({% post_url 2025/2025-07-15-deploy-flannel-cni %})
3. [Cilium CNI 알아보기 [Cilium Study 1주차]]({% post_url 2025/2025-07-16-cilium-cni-basic %})
4. [Cilium 구성요소 & 배포하기 (kube-proxy replacement) [Cilium Study 1주차]]({% post_url 2025/2025-07-18-deploy-cilium %})
5. [Cilium Hubble 알아보기 [Cilium Study 2주차]]({% post_url 2025/2025-07-21-hubble-basic %})
6. [Cilium & Hubble Command Cheet Sheet [Cilium Study 2주차] (현재 글)]({% post_url cheet-sheet/2025-07-23-cilium-hubble-commands %})
7. [Start Wars Demo와 함께 Cilium 동작방식 이해하기 [Cilium Study 2주차]]({% post_url 2025/2025-07-24-hubble-demo %})

## 편의성 설정

```shell
hubble {command} -P                                  # 단발성: 명령 실행 시 자동 포트포워드
hubble config set port-forward true                  # 모든 hubble 명령에 -P 기본 적용
cilium hubble port-forward &                         # 지속적 포워드: 로컬 4245 유지
export HUBBLE_SERVER=localhost:4245                  # hubble 기본 서버 주소 설정(환경 변수)
```

## 확인 명령어

```shell
cilium status                                        # Cilium 상태 요약
cilium status --verbose                              # 상세 상태 및 버전/오류 출력
cilium config view                                   # Cilium 런타임 설정 확인
kubectl get ciliumnodes.cilium.io -A                 # 노드별 CiliumNode 리소스 조회
kubectl get ciliumnode -o json | grep podCIDRs -A2   # 각 노드 PodCIDR 확인
kubectl get ciliumendpoints.cilium.io -A             # SECURITY IDENTITY 포함 CEP 목록
```

### cilium-dbg commands

```shell
kubectl exec -n kube-system -c cilium-agent -it ds/cilium -- cilium-dbg status --verbose  # 상세 상태/헬스 체크
kubectl exec -n kube-system -c cilium-agent -it ds/cilium -- cilium-dbg metrics list      # Prometheus 메트릭 목록

# 실시간 패킷/이벤트 모니터
kubectl exec -n kube-system -c cilium-agent -it ds/cilium -- cilium-dbg monitor           # 기본 모니터
kubectl exec -n kube-system -c cilium-agent -it ds/cilium -- cilium-dbg monitor -v        # 상세 출력(라벨 등)
kubectl exec -n kube-system -c cilium-agent -it ds/cilium -- cilium-dbg mkubectl exec -n kube-system -c cilium-agent -it ds/cilium -- cilium-dbg config # 런타임 설정 조회
onitor -v -v     # 페이로드 디섹션 포함
kubectl exec -n kube-system -c cilium-agent -it ds/cilium -- cilium-dbg monitor --related-to=<id>  # 특정 Endpoint 관련 이벤트만
kubectl exec -n kube-system -c cilium-agent -it ds/cilium -- cilium-dbg monitor --type drop         # 드롭 패킷만 표시
kubectl exec -n kube-system -c cilium-agent -it ds/cilium -- cilium-dbg monitor -v -v --hex         # 페이로드를 Hex로 출력
kubectl exec -n kube-system -c cilium-agent -it ds/cilium -- cilium-dbg monitor -v --type l7         # L7(HTTP/gRPC 등) 이벤트만
```

## Hubble Commands

```shell
hubble status                                        # Relay/Agent 헬스 체크, 플로우 카운트 확인
hubble config view                                   # 현재 hubble CLI 설정 확인
hubble config set server <addr:port>                 # 기본 서버 주소 설정
hubble observe                                       # 실시간 플로우 출력(기본)
hubble observe -f                                    # follow 모드(스트림)
hubble observe --type drop                           # 드롭 이벤트만 출력
hubble observe --protocol http                       # HTTP 이벤트만 출력
hubble observe --from-pod ns/pod --to-pod ns/pod     # 특정 Pod 간 흐름 필터링
hubble observe -f --pod {namespace}/{podname}        # 특정 Pod가 포함된 흐름 필터링 (source or destination)
hubble observe -f --label {k8s:class}={classname}    # 특정 라벨을 가진 Pod 간의 흐름 필터링
hubble observe -f --from-identity {IDENTITY_ID}      # 특정 ID에서 시작되는 흐름 필터링
hubble observe -f --identity {IDENTITY_ID}           # 특정 Security Identity 간의 흐름 필터링
hubble observe -h                                    # observe 옵션 도움말
hubble ui                                            # Hubble UI 로컬 실행(포트포워드 필요 시 -P)
```

## Cilium Pod 변수/별칭 설정

```shell
# Cilium 파드 이름 변수 설정
export CILIUMPOD0=$(kubectl get -l k8s-app=cilium pods -n kube-system --field-selector spec.nodeName=k8s-m1 -o jsonpath='{.items[0].metadata.name}') # spec.nodeName={Node Name}
export CILIUMPOD1=$(kubectl get -l k8s-app=cilium pods -n kube-system --field-selector spec.nodeName=k8s-w1  -o jsonpath='{.items[0].metadata.name}')
export CILIUMPOD2=$(kubectl get -l k8s-app=cilium pods -n kube-system --field-selector spec.nodeName=k8s-w2  -o jsonpath='{.items[0].metadata.name}')
echo $CILIUMPOD0 $CILIUMPOD1 $CILIUMPOD2             # 변수 확인

# 단축키(alias) 지정 (cilium / bpftool)
alias c0="kubectl exec -it $CILIUMPOD0 -n kube-system -c cilium-agent -- cilium"          # m1 노드 에이전트 접속
alias c1="kubectl exec -it $CILIUMPOD1 -n kube-system -c cilium-agent -- cilium"          # w1 노드 에이전트 접속
alias c2="kubectl exec -it $CILIUMPOD2 -n kube-system -c cilium-agent -- cilium"          # w2 노드 에이전트 접속

alias c0bpf="kubectl exec -it $CILIUMPOD0 -n kube-system -c cilium-agent -- bpftool"       # m1 bpftool 사용
alias c1bpf="kubectl exec -it $CILIUMPOD1 -n kube-system -c cilium-agent -- bpftool"       # w1 bpftool 사용
alias c2bpf="kubectl exec -it $CILIUMPOD2 -n kube-system -c cilium-agent -- bpftool"       # w2 bpftool 사용
```

## Endpoint / Identity / IP / Policy 관련 (별칭 사용)

```shell
# Endpoint 목록/세부정보
c0 endpoint list                                     # m1 노드 엔드포인트 목록
c0 endpoint list -o json                             # JSON 형식 출력
c1 endpoint get <id>                                 # 특정 엔드포인트 상세
c1 endpoint log <id>                                 # 엔드포인트 로그 출력
c1 endpoint config <id> Debug=true                   # 특정 엔드포인트 Debug 출력 활성화

# IDENTITY 관리/조회
c0 identity list                                     # 모든 아이덴티티 목록
c0 identity list --endpoints                         # 엔드포인트 매핑 기준 출력

# IP / IPCache
c0 ip list                                           # IP 목록 및 연결 정보
c0 ip list -n                                        # IDENTITY 번호 정보 포함 출력
c0 bpf ipcache list                                  # IP/CIDR <-> Identity 매핑(IPCache)
```

## BPF / CT / NAT / Map / cgroups / StateDB

```shell
# BPF Filesystem
c0 bpf fs show                                       # BPF 파일시스템 마운트 정보 출력
sudo tree /sys/fs/bpf                                # 노드 내부 BPF 마운트 경로 구조 확인

# Service / LoadBalancer 정보
c0 service list                                      # 로드밸런서 서비스 목록
c1 service list
c2 service list
c0 bpf lb list                                       # BPF LB 맵 내용 조회
c1 bpf lb list --revnat                              # RevNAT 엔트리 조회

# Connection Tracking
c0 bpf ct list global                                # Conntrack 엔트리 리스트
c1 bpf ct flush                                      # Conntrack 엔트리 전체 플러시

# NAT
c2 bpf nat list                                      # NAT 매핑 엔트리 확인
c2 bpf nat flush                                     # NAT 매핑 초기화

# cgroups & maps
c0 cgroups list                                      # Cilium이 관리하는 cgroup 메타데이터 출력
c0 map list                                          # 열려 있는 BPF 맵 목록
c1 map list --verbose                                # 맵 상세 정보
c1 map events cilium_lb4_services_v2                 # 특정 맵 변경 이벤트 스트림
c1 map events cilium_lb4_reverse_nat
c1 map events cilium_lxc
c1 map events cilium_ipcache

# Policy 맵 덤프
c0 bpf policy get --all                              # 모든 정책 맵 덤프
c1 bpf policy get --all -n                           # 번호(Identity) 포함 출력

# StateDB
c0 statedb dump                                      # StateDB 전체를 JSON으로 덤프
```

## Trouble Shooting

```shell
cilium sysdump --output /tmp/sysdump.tgz              # 문제 발생 시 전체 진단 번들 수집
cilium connectivity test                              # 기본 연결성 테스트(테스트 리소스 생성 후 검증)
```

## Reference

- [Cilium Docs - Command Cheatsheet](https://docs.cilium.io/en/stable/cheatsheet/)
- [Cilium Docs - Command Reference](https://docs.cilium.io/en/stable/cmdref/)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKam.\_\.Ji](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
