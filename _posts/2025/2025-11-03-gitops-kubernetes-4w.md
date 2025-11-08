---
title: GitOps와 Kubernetes
date: 2025-11-03 11:40:31 +0900
author: kkamji
categories: [DevOps]
tags: [devops, ci-cd-study, ci-cd-study-4w, gitops, kubernetes, argocd]
comments: true
image:
  path: /assets/img/ci-cd/ci-cd-study/ci-cd-study.webp
---

`CloudNet@` Gasida님이 진행하는 `CI/CD + ArgoCD + Vault Study`를 진행하며 학습한 내용을 공유합니다.

이번 포스트에서는 **예제로 배우는 Argo CD** 책의 1장 `GitOps와 Kubernetes`에 대해 다루겠습니다.

##### 내용

1. Kubernetes가 어떻게 GitOps 개념을 도입할 수 있었는지
2. 선언적 API와 파일, 폴더, Git Repository에서 리소스를 어떻게 적용할 수 있는지

---

## 1. GitOps란 무엇인가?

- GitOps라는 용어는 플럭스(Flux)라는 GitOps 도구를 만든 웨이브웍스(Weaveworks) 직원들이 2017년에 처음 사용했다.
- GitOps의 정의는 정말 다양하다. 풀 리퀘스트(PR, Pull Request)를 통한 운영으로 정의하기도 하고, 개발 관행(버전 제어, 협업, 규정 준수, CI/CD)을 인프라 자동화에 적용하는 것으로 정의하기도 한다. - [GitLab - What is GitOps?](https://about.gitlab.com/topics/gitops/)
- 가장 중요한 정의는 **CNCF**의 Application Delivery TAG에 속한 그룹인 **GitOps 워킹 그룹**(GitOps Working Group)에서 정의한 것이다. - [OpenGitOps - What is OpenGitOps?](https://opengitops.dev/)
- 이 그룹은 GitOps에 대해 특정 벤더에 종속되지 않고 원칙에 입각한 정의를 구축할 목적으로 다양한 회사 사람들로 구성돼 있다.

### 1.1. GitOps Principles

![GitOps Principles](/assets/img/ci-cd/ci-cd-study/gitops-principles.webp)
> <https://opengitops.dev/>

- **Declarative 선언적 구성**
  - 엔지니어가 원하는 의도와 **완료된 상태를 명시**하지만, 이를 위해 실행하기 위한 **구체적인 행동을 명시하지 않는다**.
  - 예를 들어 “컨테이너 3개를 만들어라”와 같이 명령적인 방식이 아니라, 이 애플리케이션에 3개의 컨테이너를 사용하겠다고 선언하면 에이전트가 3이라는 숫자를 맞춰준다.
  - 만약 지금 컨테이너가 5개 동작 중이라면 에이전트가 2개의 컨테이너를 종료시킨다.
- **Versioned and Immutable 버전이 제어되는 불변의 저장소**
  - 깃은 버전이 제어되는 불변의 저장소로, 현재 가장 많이 사용되는 소스 제어 시스템이다.
  - 유일한 것은 아니기 때문에 다른 소스 제어 시스템도 GitOps를 구현할 수 있다.
- **Pulled Automatically 자동화된 배포**
  - 변경 사항이 버전 제어 시스템 VCS(Version Control System)에 반영되면 **어떠한 수동 작업도 수행하지 말아야 한다**는 것이다.
- **Continuously Reconciled 폐쇄 루프**
  - 설정이 **업데이트**된 이후에는 새롭게 설정한 값이 잘 **반영**됐는지 확인한다.
  - 원하는 상태를 표현하면 이를 맞추기 위해 필요한 **조치**가 무엇인지 계산해야 한다.
  - 현재 시스템 상태와 버전 제어에서 원하는 상태의 차이를 비교해 알 수 있으며 이를 통해 폐쇄 **루프**를 설명할 수 있다.
  - 일종의 관리를 위한 컨트롤 루프로 애플리케이션의 라이프 사이클 동안 발생하는 ‘배포 - 모니터링 - 수정’ 등의 전체 수명 주기를 자동화하는 것을 말한다.

  ![GitOps Control Loop](/assets/img/ci-cd/ci-cd-study/gitops-control-loop.webp)

---

## 2. Kubernetes와 GitOps

- 쿠버네티스는 2014년경에 구글 엔지니어들이 **Borg**란 이름의 구글 내부용 오케스트레이터(Orchestrator) 시스템을 구축할 때 쌓인 경험을 바탕으로 컨테이너 오케스트레이터를 만들기 시작하면서 처음 등장했다.
- 쿠버네티스는 2014년에 오픈 소스로 공개됐고, 2015년에 버전 1.0.0이 출시돼 많은 회사가 관심을 가졌다. 또 커뮤니티에서 빠르게 주목받은 이유는 **CNCF**가 있었기 때문이다.
- 쿠버네티스를 오픈 소스 프로젝트로 만든 이후, 구글은 리눅스 재단 Linux Foundation과 오픈 소스 클라우드 네이티브 기술의 적용을 주도하는 비영리 재단을 만들고자 했다.
- 이것이 쿠버네티스가 초기 시드 프로젝트일 때 **CNCF**가 등장하게 된 배경이자, KubeCon이 주요 개발자 컨퍼런스가 된 이유다.
- CNCF 내의 모든 프로젝트나 단체는 유지 관리 구조가 매우 잘 돼 있고, 그들이 어떻게 결정하고 선정하는지에 대해서 잘 설명하고 있다.
- 그리고 어떠한 회사도 결정에 과반수를 차지할 수 없다.
- CNCF는 커뮤니티의 참여 없이는 어떠한 결정도 내리지 않으며, 전체 커뮤니티가 프로젝트의 전반에 중요한 역할을 한다.

### 2.1. Architecture

- 쿠버네티스는 매우 유연하게 확장 가능하기 때문에 ‘플랫폼 구축을 위한 플랫폼’이란 말처럼 추상적인 개념으로 접근하지 않고서는 정의하기가 어렵다.
- 왜냐하면 수많은 기능 중에 자신이 필요한 방식대로 골라 조합해 사용하기 때문이다. (깃옵스 역시 그런 기능들 중 하나다)

- 쿠버네티스 컴포넌트는 크게 두 가지로 나뉜다.
- 첫 번째는 **컨트롤 플레인**이다. 클러스터를 관리하는 역할.
  - 컨트롤 플레인은 REST **API 서버**와 **데이터베이스** etcd, 다중 컨트롤 루프 multiple control loops를 사용하는 **컨트롤러 매니저**, 노드에 파드를 할당하는 **스케줄러**로 구성된다.
- 둘째는 **데이터 플레인**이다. 노드에서 사용자 워크로드를 실행하는 역할.
  - 노드는 쿠버네티스 클러스터의 일부분으로 컨테이너 런타임 containerd 등, 노드의 컨테이너 런타임과 REST API와 소통을 담당하는 kubelet 그리고 노드 수준의 네트워크 추상화를 담당하는 kube-proxy로 구성된다.

![Kubernetes Architecture Overview](/assets/img/ci-cd/ci-cd-study/kubernetes-architecture-overview.webp)

### 2.2. HTTP REST API Server

- **HTTP**(HyperText Transfer Protocol) **REST API** 서버의 관점에서 Kubernetes를 보면 REST API Endpoint와 상태를 저장하는 데이터베이스(etcd)를 가진 전형적인 애플리케이션이다.
- 고가용성을 위해 여러 웹 서버 레플리카를 둔다. 쿠버네티스에서 수행되는 작업은 모두 API를 사용하기 때문에 API 서버는 매우 중요하다.
- 쿠버네티스의 다른 구성요소들은 **직접 통신하지 않고**, 반드시 **API 서버를 매개로 상호작용한다.**

- 클라이언트 입장에서 `curl`과 같은 도구를 사용해 API를 직접적으로 쿼리하기에는 매우 어렵기 때문에 `kubectl`을 사용해 인증 헤더, `Request Body` 준비, `API Response` 값 파싱 등 복잡한 것들을 쉽게 간편화할 수 있다.
- `kubectl get pods`와 같은 명령을 실행할 때 **HTTPS**로 API 서버를 호출한다. 그러면 서버가 데이터베이스에서 파드에 대한 정보를 가져온 뒤 응답값을 생성해 클라이언트에게 다시 반환한다.
- `kubectl` 클라이언트 애플리케이션은 이 응답을 받아 파싱해 사람이 읽기 편한 형식으로 변환해 출력해준다.

- API 서버는 그 자체로 클러스터의 상태 변화를 만들지는 못한다. 대신 새로운 값을 데이터베이스에 반영하고 이를 기반으로 다른 작업이 진행된다.
- 실제로 상태 변화를 만드는 것은 **스케줄러(Scheduler)**나 **kubelet**과 같은 컴포넌트와 컨트롤러가 수행한다.

### 2.3. Controller Manager

- 쿠버네티스는 많은 컨트롤러가 있다. 레플리카셋 컨트롤러는 파드의 수를 일정하게 유지하는 역할을 한다.
- 컨트롤러의 역할은 실제 상태(live state)와 원하는 상태(desired state)가 일치하는지 관찰하고, **최종 상태에 도달하기 위해 지속적으로 조정**하는 것이다.
- 이렇게 각각의 컨트롤러는 클러스터에서 각자 맡은 부분을 관리하는 데 특화돼 있다. 직접 컨트롤러를 만들 수도 있다.
- **Argo CD** 또한 컨트롤 루프를 통해 **깃 리포지터리**에서 **선언된 상태**와 **클러스터의 상태**를 일치시키면서 **컨트롤러**로 동작한다.
- 다만 Argo CD는 컨트롤러보다 오퍼레이터에 가깝다.
- 이 둘의 차이점은 컨트롤러는 쿠버네티스 내부 오브젝트에서 작동하는 반면, 오퍼레이터는 쿠버네티스와 그 외의 것들까지 다룰 수 있다.
- Argo CD의 경우, 깃 리포지터리는 오퍼레이터가 처리하는 외부 구성 요소이고, 이는 커스텀 리소스를 사용해 수행한다.

---

## 3. 명령형 API와 선언형 API

### 3.1. 명령형 방식

- 명확하게 수행할 작업을 지정하는 것으로, 예를 들면 '3개의 파드를 시작하라'라고 명시하는 것.
- 리소스를 새로 생성하는 경우 `kubectl create`를 사용하고, 이미 리소스가 존재하는 경우 `kubectl replace`를 사용해 명확한 의도를 전달할 수 있다.
- 다만 `kubectl replace` 명령은 리소스를 모두 수정하기 때문에 만약 중간에 누군가(다른 방식으로) 네임스페이스에 어노테이션을 추가하는 등 변경한 것이 있다면 손실될 수 있다.
- 절차적 방식으로 진행돼 일련의 명령어를 순서대로 적용해야 함.
- 명령형 방식은 수행하는 작업이 명확하고 네임스페이스 같이 작은 리소스를 다룰 때 의미가 있음.

##### 명령형 방식 - 직접 명령

```bash
##############################################################
# 네임스페이스 생성
##############################################################
kubectl create namespace test-imperative

##############################################################
# 확인
##############################################################
kubectl get namespace test-imperative

##############################################################
# 네임스페이스 삭제
##############################################################
kubectl delete namespace test-imperative
```

##### 명령형 방식 - 구성 파일 사용

- Deployment와 같이 복잡한 리소스의 경우 명령형 커맨드를 사용한 직접 명령 방식은 명령어에 컨테이너 이미지, 이미지 태그, 이미지 풀 정책 등에 대한 수많은 정보를 플래그 옵션으로 지정해야 하는 불편함이 있다.
- 이러한 경우 아래와 같이 구성 파일(Configuration File)을 만들어 사용할 수도 있다. 이런 방식은 명령에 전달하는 플래그의 수가 많이 줄어들기 때문에 작업을 더 쉽게할 수 있다.

```bash
# namespace.yaml
apiVersion: v1 
kind: Namespace 
metadata: 
  name: imperative-config-test

kubectl create -f namespace.yaml
```

### 3.2. 선언형 방식

- 구성 파일 사용: 파일을 사용하여 생성하고, 파일 수정 후 업데이트/동기화 명령을 실행한다. 신규/수정 파일 모두 `kubectl apply` 명령을 사용한다.
- 구성 폴더와 함께: `kubectl apply` 명령으로 폴더에 존재하는 모든 파일에서 찾은 리소스를 각각 계산해 변경 사항을 API 서버로 호출할 수 있다.
- 따라서 파일을 수정하고 폴더를 apply하면 모든 변경 사항이 적용된다.

```shell
# namespace.yaml
apiVersion: v1 
kind: Namespace 
metadata: 
  name: declarative-files
  labels:
    namespace: declarative-files

# namespace.yaml 적용
kubectl apply -f namespace.yaml
```

### 3.3. 실습 환경 배포 (Kind Kubernetes)

```bash
##############################################################
# kind k8s 배포
##############################################################
kind create cluster --name myk8s --image kindest/node:v1.32.8 --config - <<EOF
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
- role: control-plane
  extraPortMappings:
  - containerPort: 30000
    hostPort: 30000
  - containerPort: 30001
    hostPort: 30001
  - containerPort: 30002
    hostPort: 30002
  - containerPort: 30003
    hostPort: 30003
EOF

##############################################################
# kube-ops-view
##############################################################
helm repo add geek-cookbook https://geek-cookbook.github.io/charts/
helm install kube-ops-view geek-cookbook/kube-ops-view --version 1.2.2 --set service.main.type=NodePort,service.main.ports.http.nodePort=30001 --set env.TZ="Asia/Seoul" --namespace kube-system

##############################################################
# kube-ops-view 접속 URL 확인 (1.5, 2 배율)
##############################################################
open "http://127.0.0.1:30001/#scale=1.5"
open "http://127.0.0.1:30001/#scale=2"
```

---

## 4. 간단한 GitOps Operator 구축

### 4.1. GitOps Operator의 3가지 주요 기능

1. 깃 리포지터리를 복제한다. 만약 이미 복제했다면 가져오기를 수행해 깃 리포지터리 최신 내용을 동기화한다.
2. 깃 리포지터리 내용을 적용한다.
3. 앞의 1, 2 과정을 반복해 깃 리포지터리 변경 사항을 지속적으로 적용한다.

### 4.2. GitOps Operator 실습

```shell
##############################################################
# Go 설치
##############################################################
brew install go           # macOS
apt install golang-go -y  # Windows WSL2 (Ubuntu)

##############################################################
# GitOps Operator 소스 코드 Clone 및 경로 이동
##############################################################
git clone https://github.com/PacktPublishing/ArgoCD-in-Practice.git
cd ArgoCD-in-Practice/ch01/

##############################################################
# ArgoCD-in-Practice/ch01
##############################################################
tree basic-gitops-operator
# basic-gitops-operator
# ├── go.mod
# ├── go.sum
# └── main.go

##############################################################
# 배포할 매니페스트 파일
##############################################################
tree basic-gitops-operator-config
# basic-gitops-operator-config
# ├── deployment.yaml
# └── namespace.yaml

##############################################################
# 실행: tmp 폴더를 생성하고 클러스터에 적용할 매니페스트를 관리.
##############################################################
# 맨 처음 sync 시 nginx namespace가 없어 에러가 발생하지만 다음 sync부터 정상 동작
cd basic-gitops-operator
go run main.go
# start repo sync
# Enumerating objects: 1261, done.
# Counting objects: 100% (125/125), done.
# Compressing objects: 100% (32/32), done.
# Total 1261 (delta 99), reused 97 (delta 93), pack-reused 1136 (from 1)
# start manifests apply
# namespace/nginx created
# Error from server (NotFound): error when creating "/home/kkamji/Code/kkamji-lab/study/ci-cd-study/4w/ArgoCD-in-Practice/ch01/basic-gitops-operator/tmp/ch01/basic-gitops-operator-config/deployment.yaml": namespaces "nginx" not found
# manifests apply error: exit status 1
# next sync in 5s
# start repo sync
# start manifests apply
# deployment.apps/nginx created
# namespace/nginx unchanged

#  next sync in 5s 
# start repo sync
# start manifests apply
# deployment.apps/nginx unchanged
# namespace/nginx unchanged

##############################################################
# 신규 터미널: 생성 확인
##############################################################
kubectl get deploy,pod -n nginx
# NAME                    READY   UP-TO-DATE   AVAILABLE   AGE
# deployment.apps/nginx   1/1     1            1           77s

# NAME                         READY   STATUS    RESTARTS   AGE
# pod/nginx-5869d7778c-g85xb   1/1     Running   0          77s

##############################################################
# 강제로 deploy 삭제 해보기
##############################################################
kubectl delete deploy -n nginx nginx
# deployment.apps "nginx" deleted from nginx namespace

##############################################################
# 확인 - GitOps Operator가 지속적으로 동기화하기 때문에 다시 생성됨
##############################################################
kubectl get deploy,pod -n nginx

NAME                    READY   UP-TO-DATE   AVAILABLE   AGE
deployment.apps/nginx   1/1     1            1           3s

NAME                         READY   STATUS    RESTARTS   AGE
pod/nginx-5869d7778c-6658k   1/1     Running   0          3s

##############################################################
# 실습 내용 정리 (GitOps Operator 중지 후)
##############################################################
kubectl delete ns nginx
```

---

## 5. Reference

- [예제로 배우는 Argo CD](https://product.kyobobook.co.kr/detail/S000212377128)
- [GitLab - What is GitOps?](https://about.gitlab.com/topics/gitops/)
- [OpenGitOps - What is OpenGitOps?](https://opengitops.dev/)
- [Kubernetes Docs - Controllers](https://kubernetes.io/docs/concepts/architecture/controller/)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
