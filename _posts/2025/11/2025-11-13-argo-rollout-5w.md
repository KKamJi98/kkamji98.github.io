---
title: Argo CD Rollout 소개 및 실습
date: 2025-11-13 22:18:29 +0900
author: kkamji
categories: [CI/CD, ArgoCD]
tags: [devops, ci-cd-study, ci-cd-study-5w, gitops, kubernetes, argocd, argo-rollouts, blue-green, canary]
comments: true
image:
  path: /assets/img/ci-cd/ci-cd-study/ci-cd-study.webp
---

`CloudNet@` Gasida님이 진행하는 `CI/CD + ArgoCD + Vault Study`를 진행하며 학습한 내용을 공유합니다.

**Argo Rollouts**를 다루겠습니다.

> **TL;DR**  
> - 기본 Deployment의 `RollingUpdate`는 롤아웃 속도를 제어하기 어렵고, 새 버전으로 가는 트래픽 비중을 조절할 수 없으며, 외부 메트릭으로 검증하거나 자동 롤백할 수단이 없습니다.  
> - Argo Rollouts는 Deployment를 대체하는 `Rollout` CRD로 Blue-Green과 Canary를 지원하고, 가중치 기반 트래픽 전환을 세분화해 다룹니다.  
> - Ingress Controller나 Service Mesh와 연동해 트래픽을 나누고, 메트릭 분석 결과에 따라 자동으로 승격하거나 롤백할 수 있습니다.  
{: .prompt-info}

---

## 1. Argo Rollouts란?

**Argo Rollouts**는 쿠버네티스 컨트롤러와 커스텀 리소스(CRD) 세트로, 기본 Deployment 객체를 대체해 고급 배포 기능을 제공하는 툴입니다. 쿠버네티스의 Deployment로는 구현하기 어려운 다양한 배포 전략(ex: Blue-Green 배포, Canary 배포)을 **Rollout**이라는 새 리소스로 지원합니다. **Argo Rollouts**를 사용하면 배포 과정에서 **Ingress Controller나 Service Mesh(Istio, NGINX 등)**와 연동한 트래픽 분배 조정, 메트릭 기반 모니터링 및 자동 롤백/프로모션과 같은 기능을 활용할 수 있습니다.

### 1.1. Why Argo Rollouts?

`Native Kubernetes Deployment Object`는 업데이트 시 기본적인 안전 장치(`readiness probes`)를 제공하는 `RollingUpdate` 전략을 지원합니다. 하지만 `RollingUpdate` 전략은 다음과 같은 한계가 많습니다.

- 롤아웃 속도를 제어할 수단이 거의 없음
- 새 버전으로 흐르는 트래픽을 제어할 수 없음
- 준비 프로브(`Readiness probes`)는 심층 검사, 스트레스 검사 또는 일회성 검사에는 적합하지 않음
- 업데이트를 검증하기 위해 외부 메트릭을 쿼리할 수 있는 기능이 없음
- 진행을 중지할 수 있지만, 업데이트를 자동으로 중단하고 롤백할 수 없음

이런 한계 때문에 대규모 트래픽을 처리하는 프로덕션 환경에서 `RollingUpdate`는 종종 너무 위험한 업데이트 절차로 간주됩니다. 영향 범위(`blast radius`)를 제어할 수 없고 롤아웃이 너무 공격적으로 진행되며 실패해도 자동 롤백이 없기 때문입니다.  

### 1.2. Controller Features

- Blue-Green 업데이트 전략
- Canary 업데이트 전략
- 세분화된 가중치 기반 트래픽 전환
- 자동 롤백 및 프로모션
- 수동 승인 (Manual judgement)
- 사용자 정의 메트릭 쿼리 및 비즈니스 KPI 분석
- Ingress Controller 연동: NGINX, ALB, Apache APISIX
- Service Mesh 연동: Istio, Linkerd, SMI
- 여러 공급자 동시 사용: SMI + NGINX, Istio + ALB 등
- Metric Provider 연동: Prometheus, Wavefront, Kayenta, Web, Kubernetes Jobs, Datadog, New Relic, Graphite, InfluxDB

---

## 2. Argo Rollout Deployment Strategies

**Argo Rollouts**는 Blue-Green 및 Canary 전략을 지원합니다.

### 2.1. Blue-Green Deployment Strategies

블루-그린 배포는 애플리케이션의 새 버전과 이전 버전이 동시에 배포되는 방식입니다. 이 기간 동안에는 이전 버전의 애플리케이션만 프로덕션 트래픽을 받습니다. 개발자는 라이브 트래픽을 새 버전으로 전환하기 전에 새 버전을 테스트할 수 있습니다.

![Argo Rollouts Blue Green Deployment Strategy](/assets/img/ci-cd/ci-cd-study/argo-rollout-blue-green-deployment-strategy.webp)

### 2.2. Canary Deployment Strategies

카나리 배포는 애플리케이션의 새 버전에 사용자 하위 집합을 노출하는 동시에 나머지 트래픽은 이전 버전으로 서비스하는 방식입니다. 새 버전이 올바르다고 확인되면 새 버전이 점진적으로 이전 버전을 대체할 수 있습니다. NGINX나 Istio 같은 인그레스 컨트롤러와 서비스 메시는 기본 기능보다 정교한 카나리 트래픽 쉐이핑 패턴을 지원합니다(ex: 세분화된 트래픽 분할, HTTP 헤더 기반 분할).

![Argo Rollouts Canary Deployment Strategy](/assets/img/ci-cd/ci-cd-study/argo-rollouts-canary-deployment-strategies.webp)

---

## 3. Argo Rollouts Architecture

![Argo Rollouts Architecture](/assets/img/ci-cd/ci-cd-study/argo-rollouts-architecture.webp)

### 3.1. Argo Rollouts Controller

클러스터의 이벤트를 모니터링하고 **Rollout** 타입의 리소스가 변경될 때마다 반응하는 메인 컨트롤러입니다. 컨트롤러는 롤아웃의 모든 세부 정보를 읽고 클러스터를 롤아웃 정의에 적힌 상태와 같게 맞춥니다.

**Argo Rollouts**는 일반적인 Deployment 리소스에서 발생하는 변경 사항을 조작하거나 반응하지 않습니다. 다른 방법으로 애플리케이션을 배포하는 클러스터에도 **Argo Rollouts**를 설치할 수 있습니다.

### 3.2. Rollout Resource

**Rollout** 리소스는 **Argo Rollouts**가 도입하고 관리하는 커스텀 쿠버네티스 리소스입니다. 기본 쿠버네티스 Deployment 리소스와 대부분 호환되지만, 카나리 및 블루-그린 배포와 같은 고급 배포 방법의 단계, 임계값 및 방법을 제어하는 추가 필드가 있습니다.

**Argo Rollouts** 컨트롤러는 **Rollout** 소스에서 발생하는 변경 사항에만 반응합니다. 일반적인 배포 리소스에는 아무 작업도 하지 않습니다. 즉, **Argo Rollouts**로 관리하려면 Deployment를 **Rollout**으로 마이그레이션해야 합니다.

### 3.3. Replica sets for old and new version

이들은 표준 쿠버네티스 ReplicaSet 리소스의 인스턴스입니다. **Argo Rollouts**는 애플리케이션의 일부인 다양한 버전을 추적하기 위해 여기에 추가 메타데이터를 넣습니다.

**Rollout**에 참여하는 ReplicaSet은 컨트롤러가 자동으로 전부 관리합니다. 외부 도구로 조작해서는 안 됩니다.

### 3.4. Ingress/Service

라이브 사용자의 트래픽이 클러스터로 들어와 적절한 버전으로 리디렉션되는 메커니즘입니다. **Argo Rollouts**는 표준 쿠버네티스 Service 리소스를 사용하지만 관리를 위해 몇 가지 추가 메타데이터가 필요합니다.

**Argo Rollouts**는 네트워킹 옵션이 유연합니다. 롤아웃 중에 새 버전으로만 가는 서비스, 이전 버전으로만 가는 서비스, 둘 다로 가는 서비스를 따로 둘 수 있습니다. 특히 카나리 배포에서는 단순히 파드 수에 기반한 밸런싱 대신 특정 비율로 트래픽을 분할하는 여러 서비스 메시와 인그레스 솔루션을 지원하고, 여러 라우팅 공급자를 동시에 사용할 수 있습니다.

### 3.5. AnalysisTemplate and AnalysisRun

Analysis는 롤아웃을 메트릭 공급자에 연결하고 업데이트 성공 여부를 가를 메트릭 임계값을 정의하는 기능입니다. 분석마다 하나 이상의 메트릭 쿼리와 예상 결과를 정의합니다. 메트릭 쿼리가 양호하면 롤아웃이 알아서 진행되고 메트릭이 실패를 표시하면 자동으로 롤백되며, 성공과 실패를 판단할 수 없으면 롤아웃을 일시 중지합니다.

분석을 수행하기 위해 **Argo Rollouts**에는 `AnalysisTemplate`과 `AnalysisRun`이라는 두 가지 커스텀 쿠버네티스 리소스가 포함되어 있습니다.

`AnalysisTemplate`에는 쿼리할 메트릭에 대한 지침이 포함되어 있습니다. 롤아웃에 연결되는 실제 결과는 `AnalysisRun` 커스텀 리소스입니다. 특정 롤아웃에 대해 `AnalysisTemplate`을 정의하거나 `ClusterAnalysisTemplate`으로 여러 롤아웃에서 공유되도록 클러스터 전체에 정의할 수 있습니다. `AnalysisRun` 리소스는 특정 롤아웃으로 범위가 지정됩니다.

**Rollout**에서 분석과 메트릭은 선택 사항입니다. API나 CLI로 롤아웃을 직접 일시 중지하고 승격하거나, 스모크 테스트 같은 외부 방법을 쓸 수도 있습니다. **Argo Rollouts**에 메트릭 솔루션이 반드시 필요하지는 않습니다. 한 **Rollout** 안에서 자동화된(즉, 분석 기반) 단계와 수동 단계를 섞어 써도 됩니다.

메트릭 외에도 Kubernetes Job을 실행하거나 웹훅을 실행하여 롤아웃의 성공 여부를 결정할 수도 있습니다.

### 3.6. Metric providers

**Argo Rollouts**에는 널리 쓰이는 메트릭 공급자 몇 곳의 기본 통합이 들어 있습니다. Analysis 리소스에서 이 통합을 써서 롤아웃을 자동으로 승격하거나 롤백합니다. 설정 옵션은 각 공급자의 문서를 참조하세요.

### 3.7. CLI and UI (Not shown in the diagram)

**Argo Rollouts** CLI 또는 통합 UI를 사용하여 **Rollout**을 조회하고 관리할 수 있습니다. 두 가지 모두 선택 사항입니다.

---

## 4. Argo Rollouts 설치 및 Sample 테스트

### 4.1. Argo Rollouts 설치

```shell
##############################################################
# 네임스페이스 생성 및 파라미터 파일 작성
##############################################################
kubectl create ns argo-rollouts
cat <<EOT > argorollouts-values.yaml
dashboard:
  enabled: true
  service:
    type: NodePort
    nodePort: 30004
EOT

##############################################################
# 설치
##############################################################
helm install argo-rollouts argo/argo-rollouts --version 2.40.5 -f argorollouts-values.yaml --namespace argo-rollouts

##############################################################
# 확인
##############################################################
kubectl get all -n argo-rollouts
kubectl get crds

##############################################################
# Argo rollouts 대시보드 접속 주소 확인
##############################################################
open "http://<NODE_URL>:30004"
```

![Argo Rollout Main Page](/assets/img/ci-cd/ci-cd-study/argo-rollouts-main-page.webp)

### 4.2. Argo CD Extension 설치

**Argo CD**의 **Rollout Extension**으로 기본 기능을 확장하면 **Argo Rollouts** 대시보드를 **Argo CD**에서도 확인할 수 있습니다.

![Argo Rollouts Argo CD Extension](/assets/img/ci-cd/ci-cd-study/argo-rollouts-argo-cd-extension.webp)

```shell
##############################################################
# argocd-values.yaml 수정 후 재배포 (server.extensions 부분 추가)
##############################################################
cat <<EOF > argocd-values.yaml
global:
  domain: argocd.example.com

certificate:
  enabled: true

server:
  ingress:
    enabled: true
    ingressClassName: nginx
    annotations:
      nginx.ingress.kubernetes.io/force-ssl-redirect: "true"
      nginx.ingress.kubernetes.io/ssl-passthrough: "true"
    tls: true
  extensions: # 추가
    enabled: true
    extensionList:
      - name: rollout-extension
        env:
          - name: EXTENSION_URL
            value: https://github.com/argoproj-labs/rollout-extension/releases/download/v0.3.7/extension.tar
EOF
helm upgrade -i argocd argo/argo-cd --version 9.0.5 -f argocd-values.yaml --namespace argocd


# argo cd extension의 경우 initContainer 환경변수 EXTENSION_URL에 설치할 extension을 명시하면 됨
# mainContainer는 initContainer가 설치한 extension을 가져오기 위해 volumeMount로 가져옴
k describe deploy -n argocd argocd-server
# ...
#   Init Containers:
#    rollout-extension:
#     Image:           quay.io/argoprojlabs/argocd-extension-installer:v0.0.8
#     Port:            <none>
#     Host Port:       <none>
#     SeccompProfile:  RuntimeDefault
#     Environment:
#       EXTENSION_URL:  https://github.com/argoproj-labs/rollout-extension/releases/download/v0.3.7/extension.tar
#     Mounts:
#       /tmp from tmp (rw)
#       /tmp/extensions/ from extensions (rw)
# ...
#   Volumes:
#    extensions:
#     Type:       EmptyDir (a temporary directory that shares a pod's lifetime)
#     Medium:     
#     SizeLimit:  <unset>
```

### 4.3. Argo Rollouts Resource 배포

먼저 **Rollout** 리소스와 해당 **Rollout**을 대상으로 하는 Kubernetes Service를 배포합니다. 예제 **Rollout**은 카나리 업데이트 전략을 사용합니다. 트래픽의 20%를 먼저 카나리로 보내고 수동 승격(manual promotion)을 거친 뒤, 남은 업그레이드 구간에서 트래픽을 자동으로 점진 증가시킵니다.

```shell
##############################################################
# Argo Rollouts 리소스 github push
##############################################################
mkdir argo-rollouts && cd argo-rollouts
wget https://raw.githubusercontent.com/argoproj/argo-rollouts/master/docs/getting-started/basic/rollout.yaml
wget https://raw.githubusercontent.com/argoproj/argo-rollouts/master/docs/getting-started/basic/service.yaml
git add . && git commit -m "Add sample yaml" && git push -u origin main

##############################################################
# Argo CD Application 생성
##############################################################
cat << EOF > argo-rollouts-application.yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: rollout-test
  namespace: argocd
  finalizers:
    - resources-finalizer.argocd.argoproj.io
spec:
  project: default
  source:
    repoURL: https://github.com/KKamJi98/kkamji-lab # 각자 repo로 수정
    targetRevision: HEAD
    path: study/ci-cd-study/5w-2-of-3-argo-cd-in-practice/argo-rollouts
  destination:
    server: https://kubernetes.default.svc
    namespace: test
  syncPolicy:
    syncOptions:
      - CreateNamespace=true
EOF

kubectl apply -f argo-rollouts-application.yaml
argocd app sync rollout-test

##############################################################
# 확인
##############################################################
kubectl get rollout -n test
kubectl describe rollout -n test

kubectl get pod -l app=rollouts-demo -n test
kubectl get svc,ep rollouts-demo -n test
kubectl get rollouts rollouts-demo -n test -o json | grep rollouts-demo
...
   "image": "argoproj/rollouts-demo:blue"
...
```

![Argo CD Extension Check](/assets/img/ci-cd/ci-cd-study/argo-rollouts-argo-cd-extension-check.webp)

### 4.4. Argo Rollouts를 사용한 Canary 배포

위에서 배포한 blue 버전 리소스를 yellow로 업데이트해 보겠습니다.

```shell
##############################################################
# 컨테이너 이미지 blue -> yellow로 수정
##############################################################
kubectl edit rollouts rollouts-demo -n test
# ...
#      - image: argoproj/rollouts-demo:yellow 수정
# ...


##############################################################
# 컨테이너 이미지 blue -> yellow로 수정
##############################################################
argocd app get argocd/rollout-test                                       
Name:               argocd/rollout-test
Project:            default
Server:             https://kubernetes.default.svc
Namespace:          test
URL:                https://argocd.kkamji.net/applications/rollout-test
Source:
- Repo:             https://github.com/KKamJi98/kkamji-lab
  Target:           HEAD
  Path:             study/ci-cd-study/5w-2-of-3-argo-cd-in-practice/argo-rollouts
SyncWindow:         Sync Allowed
Sync Policy:        Manual
Sync Status:        OutOfSync from HEAD (9e805a1)
Health Status:      Suspended

GROUP        KIND       NAMESPACE  NAME           STATUS     HEALTH     HOOK  MESSAGE
             Namespace             test           Running    Synced           namespace/test created
             Service    test       rollouts-demo  Synced     Healthy          service/rollouts-demo created
argoproj.io  Rollout    test       rollouts-demo  OutOfSync  Suspended        rollout.argoproj.io/rollouts-demo created

# 정보 확인

kubectl get -n test rollouts rollouts-demo -o json | grep '"image": "argoproj/rollouts-demo'
          # "image": "argoproj/rollouts-demo:yellow",

# 파드 label 정보 확인
watch -d kubectl get pod -l app=rollouts-demo -n test -owide --show-labels


# argo krew 설치 시
kubectl argo rollouts get rollout rollouts-demo --watch
```

#### 4.4.1. Phase 1: Canary 배포 시작 (Paused)

Set Weight를 `20%`로 설정해두었기 때문에 Pod 5개 중 1개만 먼저 배포되고 `Paused` 상태로 멈춰 있습니다. 이 단계에서 새 버전(Yellow)을 검증합니다.

![Argo Rollouts Blue-Green Phase 1](/assets/img/ci-cd/ci-cd-study/argo-rollouts-blue-green-phase1.webp)

`kubectl argo rollouts get rollout rollouts-demo --watch` 명령어로 CLI에서도 같은 상태를 확인할 수 있습니다.

![Argo Rollouts Checks](/assets/img/ci-cd/ci-cd-study/argo-rollouts-krew-check.webp)

#### 4.4.2. Phase 2: 승격 (Promote) 및 점진적 배포

우측 상단의 `Promote-Full` 버튼을 누르고 `OK`를 클릭하면 중단되었던 배포가 재개됩니다. 설정된 단계(`40` -> `60` -> `80` -> `100`)에 따라 Weight가 증가하며 점진적으로 `Yellow` 버전으로 트래픽이 전환됩니다.

![Argo Rollouts Blue-Green Phase 2](/assets/img/ci-cd/ci-cd-study/argo-rollouts-blue-green-phase2.webp)

#### 4.4.3. Phase 3: 배포 완료

모든 단계가 끝나면 `Yellow` 버전 Pod가 트래픽 100%를 처리하고 이전 버전(Blue)의 ReplicaSet은 축소(Scaled Down)됩니다.

![Argo Rollouts Blue-Green Phase 3](/assets/img/ci-cd/ci-cd-study/argo-rollouts-blue-green-phase3.webp)

---

## 5. 마무리

**Argo Rollouts**의 개념과 아키텍처를 살펴보고, 실제 **Rollout** 리소스를 배포하여 Canary 배포 전략을 실습해 보았습니다. 기존 Kubernetes Deployment로는 어려웠던 세밀한 트래픽 제어와 자동화된 배포 전략을 **Argo Rollouts**로 구현할 수 있었습니다.

---

## 6. Reference

- [Argo Rollouts Docs - Overview](https://argoproj.github.io/argo-rollouts/)
- [Argo Rollouts Docs - Concepts](https://argoproj.github.io/argo-rollouts/concepts/)
- [Argo Rollouts Docs - Architecture](https://argoproj.github.io/argo-rollouts/architecture/)
- [Argo Rollouts Docs - Getting Started](https://argoproj.github.io/argo-rollouts/getting-started/)
- [GitHub Repository - rollout extension](https://github.com/argoproj-labs/rollout-extension)
- [악분의 블로그 - Argo CD extension](https://malwareanalysis.tistory.com/688)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
