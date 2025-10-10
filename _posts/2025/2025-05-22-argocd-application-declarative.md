---
title: ArgoCD Application 선언적으로 구성하기
date: 2025-05-22 22:35:43 +0900
author: kkamji
categories: [CI/CD, ArgoCD]
tags: [kubernetes, argocd, argocd-cli, metrics-server, gitops, declarative, application]
comments: true
image:
  path: /assets/img/ci-cd/argocd/argocd.webp
---

최근 Kubernetes 환경에서 ArgoCD를 사용한 GitOps가 주목받고 있습니다. ArgoCD를 처음 접하는 경우, ArgoCD Web UI를 통해 배포하는 방식을 가장 먼저 배우는 경우가 많습니다. 하지만 배포할 애플리케이션이 많아질수록 Web UI를 통해 모든 Application을 생성하게 되면 Human Error의 발생 가능성이 증가하고, 관리가 어렵다는 문제가 발생합니다.  

이를 해결하기 위해 선언적 구성 방식을 활용하여 자동화를 구현할 수 있습니다. 이번 글에서는 ArgoCD를 활용하여 애플리케이션을 선언적으로 구성하고 배포하는 방법에 대해 소개하겠습니다.

---

## 1. ArgoCD Application이란?

ArgoCD는 GitOps 원칙에 기반하여 Kubernetes Cluster에 애플리케이션 배포 및 관리를 자동화하는 오픈소스 도구입니다.  

ArgoCD에서 관리하는 주요 단위는 Application으로, Kubernetes 리소스를 특정 상태로 유지하도록 합니다. Application은 Git 저장소에 저장된 매니페스트를 Kubernetes Cluster의 실제 상태와 동기화하는 역할을 수행합니다.

ArgoCD Application의 주요 특징은 다음과 같습니다

- Git 저장소를 소스로 사용
- 선언적 구성으로 상태 관리
- 지속적인 모니터링과 자동 동기화

---

## 2. ArgoCD Application 생성 방법

ArgoCD Application을 생성하는 방법은 크게 세 가지가 있습니다. 선언적으로 Application의 장점을 직접 느껴보기 위해 세 가지 방법을 모두 사용해 Application을 생성해보도록 하겠습니다.

### 2.1. WEB UI를 사용하는 방식

WEB UI에서 "NEW APP" 버튼을 클릭하여 Application을 생성하는 방법입니다.  

1. ArgoCD WEB UI 접속 후, 아래 사진에 보이는 `NEW APP` 버튼 클릭
2. Application 이름, `Git Repository URL`, `Path`, `Destination` 설정 입력
3. 설정 확인 후 "CREATE" 버튼을 클릭하여 생성

#### 2.1.1. WEB UI 버튼

![New App](/assets/img/ci-cd/argocd/new-app.png)

#### 2.1.2. WEB UI 설정 예시

사진과 같이 Application과 관련된 정보를 입력 한 뒤, Create 버튼을 클릭하여 생성합니다. 사진에는 포함되어 있지 않지만, 아래로 스크롤하여 Application이 실제 배포될 `Destination`도 입력해주셔야 합니다.

![ArgoCD New App](/assets/img/ci-cd/argocd/argocd-web-ui-new-app.png)

#### 2.1.3. 결과 (WEB UI)

![ArgoCD Application Create Web UI](/assets/img/ci-cd/argocd/argocd-create-application-using-web-ui-result.png)

```shell
❯ k get all -n argocd-test   
NAME                                READY   STATUS    RESTARTS   AGE
pod/guestbook-ui-7cf4fd7cb9-9mfn9   1/1     Running   0          3m59s

NAME                   TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)   AGE
service/guestbook-ui   ClusterIP   10.233.34.122   <none>        80/TCP    3m59s

NAME                           READY   UP-TO-DATE   AVAILABLE   AGE
deployment.apps/guestbook-ui   1/1     1            1           3m59s

NAME                                      DESIRED   CURRENT   READY   AGE
replicaset.apps/guestbook-ui-7cf4fd7cb9   1         1         1       3m59s
```

### 2.2. CLI를 사용하는 명령형 방식

ArgoCD CLI 명령어를 통해 Application을 생성하는 방식입니다.

1. ArgoCD CLI를 사용해 로그인
2. ArgoCD CLI를 통해 Application 생성

```shell
## 1. ArgoCD Login
❯ argocd login argocd.kkamji.net   
Username: xxxx
Password: xxxx
'xxxx:login' logged in successfully

## 2. Create ArgoCD Application
❯ argocd app create guestbook-cli \
  --repo https://github.com/argoproj/argocd-example-apps.git \
  --path guestbook \
  --dest-server https://kubernetes.default.svc \
  --dest-namespace argocd-test-cli \
  --sync-policy auto \
  --sync-option CreateNamespace=true

application 'guestbook-cli' created
```

#### 2.2.1. 결과 (CLI)

```shell
## 결과 확인
❯ k get all -n argocd-test-cli                                     
NAME                                READY   STATUS    RESTARTS   AGE
pod/guestbook-ui-7cf4fd7cb9-9bm5m   1/1     Running   0          28s

NAME                   TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)   AGE
service/guestbook-ui   ClusterIP   10.233.29.246   <none>        80/TCP    28s

NAME                           READY   UP-TO-DATE   AVAILABLE   AGE
deployment.apps/guestbook-ui   1/1     1            1           28s

NAME                                      DESIRED   CURRENT   READY   AGE
replicaset.apps/guestbook-ui-7cf4fd7cb9   1         1         1       28s
```

![ArgoCD Application Create CLI](/assets/img/ci-cd/argocd/argocd-create-application-using-cli-result.png)

### 2.3. YAML을 통한 선언적 방식

YAML Manifest 파일을 통해 Application을 정의하고 생성하는 방식입니다.

```yaml
# application.yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: guestbook
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/argoproj/argocd-example-apps.git
    path: guestbook
    targetRevision: HEAD
  destination:
    server: https://kubernetes.default.svc
    namespace: argocd-test
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
    - CreateNamespace=true
    - ServerSideApply=true
```

```shell
## 생성
❯ k apply -f application.yaml
application.argoproj.io/guestbook-yaml created
```

#### 2.3.1. 결과 (YAML)

```shell
❯ k get all -n argocd-test
NAME                                READY   STATUS    RESTARTS   AGE
pod/guestbook-ui-7cf4fd7cb9-sk7wh   1/1     Running   0          3m27s

NAME                   TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)   AGE
service/guestbook-ui   ClusterIP   10.233.16.182   <none>        80/TCP    3m27s

NAME                           READY   UP-TO-DATE   AVAILABLE   AGE
deployment.apps/guestbook-ui   1/1     1            1           3m28s

NAME                                      DESIRED   CURRENT   READY   AGE
replicaset.apps/guestbook-ui-7cf4fd7cb9   1         1         1       3m28s

## application 정보 확인
❯ k get application -n argocd
NAME                    SYNC STATUS   HEALTH STATUS
cert-manager            Synced        Healthy
guestbook               Synced        Healthy
guestbook-cli           Synced        Healthy
guestbook-yaml          Synced        Healthy
```

![ArgoCD Application Create YAML](/assets/img/ci-cd/argocd/argocd-create-application-using-yaml-result.png)

---

## 3. 선언적 방식의 장점

위에서 3가지 방식을 통해 Application을 생성해보았습니다. 차이가 느껴지시나요? `Web UI` 방식은 직관적이지만, 애플리케이션이 많아질수록 반복 작업이 늘어나 관리가 어렵고, 사람의 실수가 발생할 가능성이 큽니다. `CLI`를 사용하는 방식은 빠르게 배포할 수 있지만, 여전히 수동적이며 여러 환경에서 일관된 배포를 보장하기 어렵습니다.  

반면 YAML을 통한 선언적 방식은 설정과 배포가 코드로 관리되어, 특히 `Prometheus`, `Metrics-Server` 등 다양한 애플리케이션을 여러 환경(개발, 테스트, 운영)에 동일하게 배포할 때 매우 유용합니다. 한 번 작성된 YAML 파일을 Git에 저장하고 관리하면, 이후 동일한 배포 작업을 여러 환경에 손쉽게 반복할 수 있어 효율적입니다. 따라서 자동화, 추적 가능성, 일관성 측면에서 선언적 방식이 가장 우수하며, 장기적으로 지속 가능한 배포 프로세스를 구축하는 데 필수적입니다.

- Application의 상태가 코드로 관리되어, 추적 및 복구가 용이
- 모든 변경사항이 Git을 통해 관리되므로 투명성이 높음
- 지속적인 동기화와 자동 복구를 통한 안정성 확보
- 코드 리뷰 및 협업이 용이
- 복제 가능한 환경 구성으로 환경 간 일관성 유지
- Git을 통한 변경 이력 관리 및 감사 가능

---

## 4. 마무리

ArgoCD Application의 다양한 생성 방법과 선언적 구성 방법에 대해 알아봤습니다. ArgoCD는 선언적 배포를 통해 Kubernetes 관리의 복잡성을 줄이고, GitOps 방식의 자동화 및 모니터링을 효율적으로 수행할 수 있게 도와줍니다.  
  
GitOps의 장점을 극대화하기 위해서는 ArgoCD Application을 선언적으로 구성하고 지속적으로 관리하는 것이 중요합니다. 간단한 예시부터 시작하여 점진적으로 복잡한 환경에 적용해 나가는 것을 추천합니다.

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
