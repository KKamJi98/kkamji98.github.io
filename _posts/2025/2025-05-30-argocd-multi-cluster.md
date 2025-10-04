---
title: ArgoCD로 Multi-Cluster Application 배포하기
date: 2025-05-30 20:19:03 +0900
author: kkamji
categories: [CI/CD, ArgoCD]
tags: [kubernetes, argocd, argocd-cli, metrics-server, gitops, declarative, application]
comments: true
image:
  path: /assets/img/argocd/argocd.webp
---

이번 글에서는 ArgoCD를 활용해 여러 Kubernetes Cluster에 애플리케이션을 배포하는 방법을 살펴보겠습니다.

---

## 1. 사전 준비사항

- 2개 이상의 Kubernetes Cluster
- ArgoCD가 설치된 관리용 클러스터
- Git 저장소 접근 권한
- `kubectl`, `argocd` CLI Tool 설치

---

## 2. ArgoCD Multi-Cluster 아키텍처

ArgoCD의 Multi-Cluster 배포 구조는 다음과 같은 단계를 거칩니다.

- 중앙 관리용 클러스터에 ArgoCD 설치
- 배포 대상 클러스터를 ArgoCD에 등록
- Git 저장소에서 Application 정의 관리
- ArgoCD를 통한 멀티 클러스터 동시 배포

---

## 3. 클러스터 등록하기

먼저 대상 클러스터를 ArgoCD에 등록합니다. 실습을 위해 배포된 EKS Cluster를 사용했습니다.

```shell
# EKS Cluster 접속을 위한 kubeconfig 설정
❯ aws eks update-kubeconfig --region ap-northeast-2 --name kkamji-al2023 --alias kkamji-al2023

# 대상 클러스터의 kubeconfig 컨텍스트 이름 확인
❯ kubectl config get-contexts
CURRENT   NAME                 CLUSTER                                                              AUTHINFO                                                             NAMESPACE
          kkamji               cluster.local                                                        kubernetes-admin                                                     default
*         kkamji-al2023        arn:aws:eks:ap-northeast-2:xxxxxxxxxxx:cluster/kkamji-al2023         arn:aws:eks:ap-northeast-2:xxxxxxxxxxx:cluster/kkamji-al2023   

# ArgoCD CLI Login
❯ argocd login <YOUR_ARGOCD_DOMAIN> --username <YOUR_USERNAME> --password <YOUR_PASSWORD>

# ArgoCD CLI를 사용하여 클러스터 추가
❯ argocd cluster add kkamji-al2023
WARNING: This will create a service account `argocd-manager` on the cluster referenced by context `kkamji-al2023` with full cluster level privileges. Do you want to continue [y/N]? y
{"level":"info","msg":"ServiceAccount \"argocd-manager\" created in namespace \"kube-system\"","time":"2025-05-30T00:21:42+09:00"}
{"level":"info","msg":"ClusterRole \"argocd-manager-role\" created","time":"2025-05-30T00:21:42+09:00"}
{"level":"info","msg":"ClusterRoleBinding \"argocd-manager-role-binding\" created","time":"2025-05-30T00:21:42+09:00"}
{"level":"info","msg":"Created bearer token secret for ServiceAccount \"argocd-manager\"","time":"2025-05-30T00:21:42+09:00"}
Cluster 'https://F9B06D6BAF4D073065E9EE06283344FA.sk1.ap-northeast-2.eks.amazonaws.com' added

# 클러스터 상태 확인
❯ argocd cluster list

SERVER                                                                         NAME                VERSION  STATUS      MESSAGE  PROJECT
https://F9B06D6BAF4D073065E9EE06283344FA.sk1.ap-northeast-2.eks.amazonaws.com  kkamji-al2023       1.32     Successful           
https://kubernetes.default.svc                                                 in-cluster          1.32     Successful           
```

> 위 명령어를 실행하면, ArgoCD가 대상 클러스터에 필요한 권한을 가진 ServiceAccount를 생성하고, 해당 클러스터를 ArgoCD에 등록합니다. 이 과정에서 `argocd-manager`라는 이름의 ServiceAccount가 대상 클러스터에 생성됩니다.
{: .prompt-tip}

```shell
## kkamji-al2023 클러스터에 생성된 ServiceAccount 확인
❯ kubectl get sa -n kube-system 
NAME                                          SECRETS   AGE
argocd-manager                                1         70s
attachdetach-controller                       0         73m
```

---

## 4. ArgoCD Application 배포 및 확인

이전 글에서도 사용한 `guestbook` 애플리케이션을 예시로 사용하겠습니다.  
주목할 부분 => 다른 클러스터에 배포될 Application을 정의할 때는 `destination`이 `https://kubernetes.default.svc`가 아닌 위에서 등록한 클러스터의 이름 `kkamji-al2023`을 사용

```yaml
# application-target.yaml
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
    name: kkamji-al2023 # 중요
    namespace: argocd-test
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
    - CreateNamespace=true
    - ServerSideApply=true
```

위의 `application-target.yaml` 파일을 사용하여 `kkamji-al2023` 클러스터에 `guestbook` 애플리케이션을 배포합니다.

> `kubectl apply` 명령어를 ArgoCD가 존재하는 클러스터에서 사용해야 하며, `destination`의 `name` 필드에 등록한 클러스터 이름을 정확히 입력해야 합니다.  
{: .prompt-danger}

```shell
## Argocd Application 배포
❯ kubectl apply -f application-target.yaml
application.argoproj.io/guestbook created

## 배포된 Application 확인
❯ argocd app list
NAME                                     CLUSTER                         NAMESPACE         PROJECT  STATUS     HEALTH   SYNCPOLICY  CONDITIONS        REPO                                                 PATH                            TARGET
...
argocd/guestbook                         kkamji-al2023                   argocd-test       default  Synced     Healthy  Auto-Prune  <none>      https://github.com/argoproj/argocd-example-apps.git  guestbook                       HEAD...

## Application 상태 확인
❯ argocd app get guestbook
Name:               argocd/guestbook
Project:            default
Server:             kkamji-al2023
Namespace:          argocd-test
URL:                https://argocd.kkamji.net/applications/guestbook
Source:
- Repo:             https://github.com/argoproj/argocd-example-apps.git
  Target:           HEAD
  Path:             guestbook
SyncWindow:         Sync Allowed
Sync Policy:        Automated (Prune)
Sync Status:        Synced to HEAD (6865767)
Health Status:      Healthy

GROUP  KIND        NAMESPACE    NAME          STATUS   HEALTH   HOOK  MESSAGE
       Namespace                argocd-test   Running  Synced         namespace/argocd-test serverside-applied
       Service     argocd-test  guestbook-ui  Synced   Healthy        service/guestbook-ui serverside-applied
apps   Deployment  argocd-test  guestbook-ui  Synced   Healthy        deployment.apps/guestbook-ui serverside-applied

## Application 로그 확인
❯ argocd app logs guestbook
Hi
```

---

## 5. 결론

ArgoCD를 활용한 Multi-Cluster 애플리케이션 배포는 GitOps 방식의 효율적이고 일관된 관리를 제공합니다. 적절한 보안과 설정 관리를 통해 멀티 클러스터 환경에서도 안정적으로 운영할 수 있으며, 대규모 환경일 경우 `ApplicationSet`을 사용하면 더욱 간편하고 유용하게 활용될 수 있습니다.

---

## 6. 참고 자료

- **Cluster Bootstrapping** - <https://argo-cd.readthedocs.io/en/stable/operator-manual/cluster-bootstrapping>
- **Declarative Setup** <https://argo-cd.readthedocs.io/en/stable/operator-manual/declarative-setup>
- **Cluster Management** - <https://argo-cd.readthedocs.io/en/stable/operator-manual/cluster-management>

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
