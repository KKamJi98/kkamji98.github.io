---
title: Istioctl Command Cheat Sheet
date: 2026-01-06 22:30:00 +0900
author: kkamji
categories: [Kubernetes, Istio]
tags: [kubernetes, istio, istioctl, service-mesh, devops, cheat-sheet, envoy, traffic-management]     # TAG names should always be lowercase
comments: true
image:
  path: /assets/img/kubernetes/istio/istio.webp
---

Istio를 운영하면서 숙지해야 할 istioctl 명령어들을 정리합니다.

---

## 1. 기본 설정 및 상태 확인

```shell
istioctl version                                     # istioctl 및 클러스터 Istio 버전 확인
istioctl version --remote=false                      # 클라이언트 버전만 확인
istioctl proxy-status                                # 모든 프록시의 동기화 상태 확인 (ps로 축약 가능)
istioctl ps                                          # proxy-status 축약형
istioctl ps -o json                                  # JSON 형식으로 프록시 상태 출력
istioctl verify-install                              # Istio 설치 상태 검증
istioctl operator dump                               # IstioOperator 설정 덤프
```

---

## 2. 설치 및 업그레이드

```shell
# 설치
istioctl install                                     # 기본 프로파일로 설치
istioctl install --set profile=demo                  # demo 프로파일로 설치
istioctl install --set profile=minimal               # minimal 프로파일로 설치
istioctl install --set profile=default               # default 프로파일(프로덕션 권장) 설치
istioctl install -f custom-istio.yaml                # 커스텀 IstioOperator 매니페스트로 설치
istioctl install --dry-run                           # 실제 설치 없이 매니페스트 확인 (dry-run)
istioctl install --set values.global.proxy.resources.requests.cpu=100m  # 리소스 설정과 함께 설치

# 프로파일 확인
istioctl profile list                                # 사용 가능한 설치 프로파일 목록
istioctl profile dump default                        # 특정 프로파일의 설정 덤프
istioctl profile diff demo default                   # 두 프로파일 간 차이 비교

# 매니페스트 생성 (GitOps용)
istioctl manifest generate --set profile=default > istio.yaml  # 설치 매니페스트 생성
istioctl manifest generate -f custom-istio.yaml > istio.yaml   # 커스텀 설정으로 매니페스트 생성
istioctl manifest diff manifest1.yaml manifest2.yaml  # 두 매니페스트 비교

# 업그레이드
istioctl upgrade                                     # Istio 업그레이드 (In-Place)
istioctl upgrade --dry-run                           # 업그레이드 시뮬레이션
istioctl x precheck                                  # 업그레이드 전 사전 점검

# 제거
istioctl uninstall --purge                           # Istio 완전 제거
istioctl uninstall -f custom-istio.yaml              # 특정 설정으로 설치된 Istio 제거
istioctl uninstall --revision canary                 # 특정 리비전 제거
```

---

## 3. 사이드카 프록시 관리

```shell
# 네임스페이스 라벨 기반 자동 주입
kubectl label namespace <namespace> istio-injection=enabled      # 자동 주입 활성화
kubectl label namespace <namespace> istio-injection=disabled     # 자동 주입 비활성화
kubectl label namespace <namespace> istio-injection-             # 라벨 제거

# 수동 사이드카 주입
istioctl kube-inject -f deployment.yaml | kubectl apply -f -     # 사이드카 주입 후 적용
istioctl kube-inject -f deployment.yaml -o injected.yaml         # 주입된 매니페스트 파일로 저장
istioctl kube-inject -f deployment.yaml --revision canary        # 특정 리비전으로 주입

# 주입 상태 확인
kubectl get namespace -L istio-injection             # 네임스페이스별 주입 설정 확인
kubectl get pods -n <namespace> -o jsonpath='{.items[*].spec.containers[*].name}' | tr ' ' '\n' | grep istio-proxy  # 사이드카 주입 여부 확인
```

---

## 4. 구성 분석 및 검증

```shell
# 구성 분석
istioctl analyze                                     # 현재 네임스페이스의 구성 분석
istioctl analyze --all-namespaces                    # 모든 네임스페이스 분석
istioctl analyze -n <namespace>                      # 특정 네임스페이스 분석
istioctl analyze -f virtual-service.yaml             # YAML 파일 분석 (적용 전 검증)
istioctl analyze --use-kube=false -f config/         # 클러스터 연결 없이 로컬 파일만 분석
istioctl analyze --suppress "IST0102=*"              # 특정 메시지 코드 무시
istioctl analyze -o json                             # JSON 형식으로 분석 결과 출력

# 구성 검증
istioctl validate -f virtual-service.yaml            # 리소스 YAML 검증
istioctl validate -f config/ --warnings              # 디렉토리 내 모든 파일 검증 (경고 포함)
```

---

## 5. 프록시 구성 디버깅 (proxy-config)

```shell
# 기본 프록시 구성 확인
istioctl proxy-config cluster <pod-name>.<namespace>   # 클러스터 구성 확인 (upstream)
istioctl proxy-config listener <pod-name>.<namespace>  # 리스너 구성 확인 (inbound/outbound)
istioctl proxy-config route <pod-name>.<namespace>     # 라우팅 구성 확인
istioctl proxy-config endpoint <pod-name>.<namespace>  # 엔드포인트 구성 확인
istioctl proxy-config bootstrap <pod-name>.<namespace> # 부트스트랩 구성 확인
istioctl proxy-config secret <pod-name>.<namespace>    # 시크릿(TLS 인증서) 구성 확인

# 축약형 (pc)
istioctl pc cluster <pod-name>.<namespace>
istioctl pc listener <pod-name>.<namespace>
istioctl pc route <pod-name>.<namespace>
istioctl pc endpoint <pod-name>.<namespace>

# 상세 출력 옵션
istioctl pc cluster <pod-name>.<namespace> -o json     # JSON 형식으로 출력
istioctl pc cluster <pod-name>.<namespace> -o yaml     # YAML 형식으로 출력
istioctl pc listener <pod-name>.<namespace> --port 80  # 특정 포트 리스너만 확인
istioctl pc route <pod-name>.<namespace> --name 80     # 특정 라우트 이름만 확인
istioctl pc endpoint <pod-name>.<namespace> --cluster "outbound|80||reviews.default.svc.cluster.local"  # 특정 클러스터의 엔드포인트만
istioctl pc endpoint <pod-name>.<namespace> --status healthy  # 건강한 엔드포인트만 표시

# 전체 Envoy 구성 덤프
istioctl proxy-config all <pod-name>.<namespace>       # 모든 프록시 구성 출력
istioctl proxy-config all <pod-name>.<namespace> -o json  # JSON으로 전체 구성 덤프
```

---

## 6. 트래픽 디버깅

```shell
# 요청 경로 추적
istioctl x describe pod <pod-name>.<namespace>         # Pod의 트래픽 구성 요약 (인바운드/아웃바운드)
istioctl x describe service <service-name>.<namespace>  # 서비스의 트래픽 구성 요약

# 실시간 트래픽 모니터링 (Envoy Access Log)
kubectl logs -n <namespace> <pod-name> -c istio-proxy -f  # 사이드카 프록시 로그 실시간 확인
kubectl logs -n <namespace> <pod-name> -c istio-proxy --tail=100  # 최근 100줄 로그

# Envoy Admin API 직접 접근
kubectl exec -n <namespace> <pod-name> -c istio-proxy -- pilot-agent request GET /config_dump  # 전체 Envoy 구성 덤프
kubectl exec -n <namespace> <pod-name> -c istio-proxy -- pilot-agent request GET /stats        # Envoy 통계
kubectl exec -n <namespace> <pod-name> -c istio-proxy -- pilot-agent request GET /clusters     # 클러스터 상태
kubectl exec -n <namespace> <pod-name> -c istio-proxy -- pilot-agent request GET /listeners    # 리스너 상태
kubectl exec -n <namespace> <pod-name> -c istio-proxy -- pilot-agent request POST /logging?level=debug  # 로그 레벨 변경

# Envoy 포트포워드로 Admin UI 접근
kubectl port-forward -n <namespace> <pod-name> 15000:15000  # Envoy Admin 포트 포워딩
# 이후 http://localhost:15000 에서 Envoy Admin UI 접근
```

---

## 7. 프록시 동기화 및 xDS 디버깅

```shell
# 프록시 동기화 상태 상세 확인
istioctl proxy-status                                  # 모든 프록시 상태 (SYNCED/NOT SENT/STALE)
istioctl proxy-status <pod-name>.<namespace>           # 특정 Pod의 상태 상세

# xDS 구성 비교 (istiod vs proxy)
istioctl proxy-status <pod-name>.<namespace> --diff    # istiod에 있는 구성과 프록시 구성 비교

# istiod 디버깅
istioctl remote-clusters                               # 멀티클러스터 환경에서 원격 클러스터 확인
kubectl logs -n istio-system -l app=istiod -f          # istiod 로그 확인
kubectl logs -n istio-system -l app=istiod --tail=200  # istiod 최근 로그

# 디버그 정보 수집
istioctl bug-report                                    # 디버그 정보 수집 (지원 요청 시 유용)
istioctl bug-report --include <namespace>              # 특정 네임스페이스 포함하여 수집
istioctl bug-report --duration 30m                     # 최근 30분 데이터만 수집
```

---

## 8. 보안 및 인증 디버깅

```shell
# mTLS 상태 확인
istioctl x authz check <pod-name>.<namespace>          # AuthorizationPolicy 적용 상태 확인
istioctl pc secret <pod-name>.<namespace>              # TLS 인증서 상태 확인
istioctl pc secret <pod-name>.<namespace> -o json | jq '.dynamicActiveSecrets'  # 활성 시크릿 상세

# 인증서 정보 확인
istioctl proxy-config secret <pod-name>.<namespace> -o json | jq -r '.dynamicActiveSecrets[0].secret.tlsCertificate.certificateChain.inlineBytes' | base64 -d | openssl x509 -text -noout  # 인증서 상세 정보

# PeerAuthentication 및 AuthorizationPolicy 적용 확인
kubectl get peerauthentication -A                      # 모든 PeerAuthentication 확인
kubectl get authorizationpolicy -A                     # 모든 AuthorizationPolicy 확인
istioctl analyze -n <namespace>                        # 보안 정책 구성 문제 분석
```

---

## 9. Waypoint 프록시 관리 (Ambient Mesh)

```shell
# Waypoint 프록시 배포 (Ambient Mesh 환경)
istioctl waypoint generate --namespace <namespace>     # Waypoint 매니페스트 생성
istioctl waypoint apply --namespace <namespace>        # Waypoint 배포
istioctl waypoint delete --namespace <namespace>       # Waypoint 삭제
istioctl waypoint list                                 # Waypoint 목록 확인
istioctl waypoint status --namespace <namespace>       # Waypoint 상태 확인

# Ambient Mesh 네임스페이스 설정
kubectl label namespace <namespace> istio.io/dataplane-mode=ambient  # Ambient 모드 활성화
```

---

## 10. 멀티클러스터 관리

```shell
# 멀티클러스터 설정
istioctl create-remote-secret --name <cluster-name> --context <kubeconfig-context>  # 원격 클러스터 시크릿 생성
istioctl remote-clusters --context <kubeconfig-context>  # 원격 클러스터 목록 확인

# 크로스 클러스터 서비스 디버깅
istioctl proxy-status --context <kubeconfig-context>   # 특정 클러스터의 프록시 상태
istioctl analyze --context <kubeconfig-context>        # 특정 클러스터 분석
```

---

## 11. 대시보드 접근

```shell
# 내장 대시보드 접근 (포트포워딩 자동 설정)
istioctl dashboard kiali                               # Kiali 대시보드 (서비스 메시 시각화)
istioctl dashboard prometheus                          # Prometheus 대시보드 (메트릭)
istioctl dashboard grafana                             # Grafana 대시보드 (시각화)
istioctl dashboard jaeger                              # Jaeger 대시보드 (분산 트레이싱)
istioctl dashboard zipkin                              # Zipkin 대시보드 (분산 트레이싱)
istioctl dashboard envoy <pod-name>.<namespace>        # 특정 Pod의 Envoy Admin UI
istioctl dashboard controlz <pod-name>.<namespace>     # istiod ControlZ UI

# 대시보드 접근 옵션
istioctl dashboard kiali --browser=false               # 브라우저 자동 열기 비활성화
istioctl dashboard kiali --address 0.0.0.0             # 모든 인터페이스에서 접근 허용
istioctl dashboard kiali --port 20001                  # 커스텀 포트 지정
```

---

## 12. 트러블슈팅 명령어

```shell
# 일반적인 문제 진단
istioctl analyze --all-namespaces                      # 전체 클러스터 구성 문제 분석
istioctl proxy-status                                  # 프록시 동기화 상태 확인 (STALE 확인)
istioctl verify-install                                # 설치 무결성 검증

# 특정 Pod 문제 진단
istioctl x describe pod <pod-name>.<namespace>         # Pod 트래픽 구성 요약
istioctl pc all <pod-name>.<namespace> -o json > envoy-config.json  # 전체 Envoy 구성 저장
istioctl proxy-config log <pod-name>.<namespace> --level debug  # 프록시 로그 레벨 변경

# 연결 문제 진단
istioctl pc cluster <pod-name>.<namespace> | grep <target-service>  # 대상 서비스 클러스터 존재 확인
istioctl pc endpoint <pod-name>.<namespace> | grep <target-service>  # 대상 서비스 엔드포인트 확인
istioctl pc listener <pod-name>.<namespace> | grep <port>  # 리스너 바인딩 확인

# 버그 리포트 생성
istioctl bug-report                                    # 전체 디버그 정보 수집
istioctl bug-report --include <namespace1>,<namespace2>  # 특정 네임스페이스만 포함
istioctl bug-report --exclude <namespace>              # 특정 네임스페이스 제외

# istiod 상태 확인
kubectl get pods -n istio-system -l app=istiod         # istiod Pod 상태
kubectl describe pod -n istio-system -l app=istiod     # istiod Pod 상세 정보
kubectl logs -n istio-system -l app=istiod --tail=500  # istiod 로그
```

---

## 13. 유용한 별칭 및 환경 설정

```shell
# istioctl 별칭 설정
alias ic=istioctl
alias ips='istioctl proxy-status'
alias ipc='istioctl proxy-config'
alias ia='istioctl analyze'

# 자주 사용하는 조합
istioctl ps | grep -v SYNCED                           # 동기화되지 않은 프록시만 표시
istioctl analyze 2>&1 | grep -E "Error|Warning"        # 에러와 경고만 필터링
istioctl pc cluster <pod>.<ns> | grep -E "outbound.*<service>"  # 특정 서비스로의 아웃바운드 클러스터 확인

# 네임스페이스 환경 변수 설정
export ISTIO_NAMESPACE=istio-system                    # Istio 시스템 네임스페이스 설정
```

---

## 14. 실험적 명령어 (istioctl x)

```shell
# 실험적 기능 (experimental)
istioctl x describe pod <pod-name>.<namespace>         # Pod 구성 설명
istioctl x describe service <service-name>.<namespace>  # 서비스 구성 설명
istioctl x authz check <pod-name>.<namespace>          # 인가 정책 확인
istioctl x precheck                                    # 설치/업그레이드 전 사전 점검
istioctl x uninstall --purge                           # Istio 완전 제거 (실험적)

# Workload Entry 자동 등록
istioctl x workload entry configure                    # VM Workload Entry 설정
istioctl x workload group create --name <name> --namespace <namespace>  # WorkloadGroup 생성
```

---

## 15. Reference

- [Istio Docs - istioctl Reference](https://istio.io/latest/docs/reference/commands/istioctl/)
- [Istio Docs - Debugging Envoy and Istiod](https://istio.io/latest/docs/ops/diagnostic-tools/)
- [Istio Docs - Traffic Management Debugging](https://istio.io/latest/docs/ops/diagnostic-tools/proxy-cmd/)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**
{: .prompt-info}
