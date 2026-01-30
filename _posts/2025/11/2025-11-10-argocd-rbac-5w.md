---
title: Argo CD in Practice (4) - 접근제어
date: 2025-11-10 23:51:44 +0900
author: kkamji
categories: [DevOps]
tags: [devops, ci-cd-study, ci-cd-study-5w, gitops, kubernetes, argocd, rbac]
comments: true
image:
  path: /assets/img/ci-cd/ci-cd-study/ci-cd-study.webp
---

`CloudNet@` Gasida님이 진행하는 `CI/CD + ArgoCD + Vault Study`를 진행하며 학습한 내용을 공유합니다.

이번 포스트에서는 **예제로 배우는 Argo CD** 책의 4장 `접근 제어`에 대해 다루겠습니다.

##### 다룰 내용

1. Argo CD에서 어떻게 사용자의 접근을 제어하는지
2. 터미널이나 CI/CD 파이프라인에서 CLI를 통해 연결하기 위한 옵션에는 어떤 것들이 있는지, 어떻게 RBAC가 적용되는지
3. SSO(Single Sign-On) 옵션에는 어떤 것들이 있는지

---

## 1. 선언적 사용자

오픈 웹 애플리케이션 보안 프로젝트(OWASP, Open Web Application Security Project)의 가장 유명한 프로젝트에는 웹 애플리케이션 보안에 중요하게 고려해야 할 위험 목록인 OWASP TOP 10(<https://owasp.org/www-project-top-ten/>)입니다. 해당 목록은 몇 년에 한 번씩 업데이트 되는데 현재 최신 버전인 2021년 버전에는 **취약한 접근제어**(Broken Access Control)가 1위를 차지했습니다. 이를 통해 사용자의 액세스 종류에 대해 적절하게 설정해 최소 권한 원칙을 위반하지 않도록 하는 것은 매우 중요하다는 것을 알 수 있습니다.

### 1.1. 관리자와 로컬 사용자

클러스터에 Argo CD를 설치하면 admin 사용자만 생성됩니다. Argo CD `2.0.0` 이후 버전에서는 해당 admin 사용자 계정에 대한 비밀번호가 `argocd-initial-admin-secret`이라는 시크릿에 저장됩니다.

```shell
##############################################################
# Argo CD admin 사용자 계정 초기 비밀번호 확인
##############################################################
kubectl -n argocd get secrets argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d; echo
# -rr7fA7IYGCrdZQX
```

배포 직후에는 해당 Password를 사용해 Web UI나 CLI에서 admin 계정에 로그인 할 수 있습니다. Admin 계정은 초기 구성 시에만 사용하고, 이후에는 로컬 사용자 계정으로 전환하거나 SSO 통합을 구성하는 것을 권장합니다. 초기 비밀번호를 변경하기 위해서는 Web UI의 `User Info` 탭의 `UPDATE PASSWORD` 버튼이나 `argocd account update-password` 명령어를 사용할 수 있습니다.

관리자 비밀번호를 잊어버린 경우에는 초기화하거나 Argo CD의 bcrypt 해시 저장소인 메인 시크릿 리소스에서 직접 수정할 수 있습니다.

- [Argo CD GitHub - I forgot the admin password, how do I reset it?](https://github.com/argoproj/argo-cd/blob/master/docs/faq.md#i-forgot-the-admin-password-how-do-i-reset-it)

클러스터 배포 직후 해야할 일은 `admin` 관리자 계정을 비활성화하는 것입니다. 관리자 계정은 막강한 권한을 갖고 있어 일에 필요한 최소한의 권한만 줘야 한다는 최소 권한 원칙(<https://en.wikipedia.org/wiki/Principle_of_least_privilege>)을 지키기 위해서 비활성화해야 합니다. 비활성화 전, 시스템에 접근과 일상적인 작업을 위한 최소 권한의 로컬 사용자를 만들어야합니다. Argo CD에 그룹이나 팀이 아니라 그냥 접근해야 하는 경우를 위해 항상 모두를 위한 전용 사용자 계정을 만들어 두는 것이 좋습니다. 만약 누군가 팀을 떠나 시스템 접근 권한이 없어지게 될 경우 해당 계정을 비활성화하거나 삭제해야 하기 때문입니다. 아래와 같이 `argocd-cm`이라는 ConfigMap 리소스를 수정해 `alice`라는 이름으로 사용자를 생성하고 UI와 CLI 접근을 모두 허용하도록 할 수 있습니다.

```shell
##############################################################
# argocd-cm ConfigMap 리소스 수정 (alice 계정 추가)
##############################################################
# https://github.com/AcornPublishing/argo-cd-in-practice/blob/main/ch04/kustomize-installation/patches/argocd-cm.yaml
kubectl edit cm -n argocd argocd-cm

# 아래와 같이 account.alice 추가
apiVersion: v1 
kind: ConfigMap 
metadata: 
  name: argocd-cm 
data:
  accounts.alice: apiKey, login # (추가) alice 계정 설정

##############################################################
# alice 계정 확인
##############################################################
argocd account list
# NAME   ENABLED  CAPABILITIES
# admin  true     login
# alice  true     apiKey, login

##############################################################
# alice 계정 Password 설정 (current-password에는 admin 계정의 비밀번호 넣기)
##############################################################
argocd account update-password --account alice --current-password qwe12345 --new-password alice12345
# Password updated

# 혹은 argocd account update-password --account alice : 대화형 셸 사용 , 비밀번호가 셸 히스토리에 저장되지 않음.


##############################################################
# 변경된 내용 확인 : argocd-secret 에 새로운 사용자에 대한 값 추가 확인
##############################################################
kubectl get secret -n argocd argocd-secret -o jsonpath='{.data}' | jq
# {
#   "accounts.alice.password": "JDJhJDEwJHJXRE51WXlHYjBuZ0tGbmhYaWtNWmUuRk5jaWI3ek5lc1Z0NVJ1WThvSFZJVjduUVkzWU5H",
#   "accounts.alice.passwordMtime": "MjAyNS0xMS0xNVQxNTo1MDowM1o=",
#   "accounts.alice.tokens": "bnVsbA==",
#   "admin.password": "JDJhJDEwJE53aDhCTzV0N3A2WTdPMDVpZFRua2U0VHFkWmdEVXB0NTV2THZlY2JiU0hwSHY2cTBHU09x",
#   "admin.passwordMtime": "MjAyNS0xMS0xNVQxNTo0OToxNVo=",
#   "server.secretkey": "dDBEaitmT1UxWHQwMnVrZHcxUHRhNlhoTGpoSEV2dEdaekpOcjVMWlNUYz0="
# }

# account.alice.token 부분에서 생성된 사용자 토큰은 아직 생성된 것이 없기 때문에 실제 값은 null임
kubectl get secret -n argocd argocd-secret -o jsonpath='{.data.accounts\.alice\.tokens}' | base64 -d; echo
# null

##############################################################
# 원활한 확인을 위해 Sample Application 배포
##############################################################
# guestbook helm 차트 애플리케이션 생성
cat <<EOF | kubectl apply -f -
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: guestbook
  namespace: argocd
  finalizers:
  - resources-finalizer.argocd.argoproj.io
spec:
  project: default
  source:
    helm:
      valueFiles:
      - values.yaml
    path: helm-guestbook
    repoURL: https://github.com/argoproj/argocd-example-apps
    targetRevision: HEAD
  syncPolicy:
    automated:
      enabled: true
      prune: true
      selfHeal: true
    syncOptions:
    - CreateNamespace=true
  destination:
    namespace: guestbook
    server: https://kubernetes.default.svc
EOF

#
kubectl get applications -n argocd guestbook
kubectl get applications -n argocd guestbook -o yaml | kubectl neat | yq
kubectl get pod,svc,ep -n guestbook
```

![Admin User Main](/assets/img/ci-cd/ci-cd-study/argocd-admin-user-main-page.webp)
> Admin 계정에서 Application 확인  

![Alice User Main](/assets/img/ci-cd/ci-cd-study/argocd-alice-user-main-page.webp)
> Alice 계정에서 Application 확인  

현재 alice 계정은 아무런 권한을 갖고 있지 않아 로그인은 할 수 있지만 애플리케이션이나 클러스터 목록을 조회해도 볼 수 없고, 빈 내용만 표시됩니다. 권한을 부여하는 방법에는 아래 두 가지 방법이 있습니다.

1. 사용자에게 특정 권한을 부여
2. 사용자에게 권한이 부여되어 있지 않거나 부여된 권한을 찾을 수 없는 경우 부여할 기본 정책 설정

기본 정책을 읽기 전용으로 설정하고 액세스 토큰을 사용할 때 특정 권한을 부여받기 위해서는 `argocd-rbac-cm` ConfigMap 리소스에 대한 수정이 필요합니다.

```shell
##############################################################
# 현재 argocd-rbac-cm 내용 확인
##############################################################
kubectl get cm -n argocd argocd-rbac-cm -o jsonpath='{.data}' | jq
# {
#   "policy.csv": "",
#   "policy.default": "",
#   "policy.matchMode": "glob",
#   "scopes": "[groups]"
# }

##############################################################
# 현재 argocd-rbac-cm 내용 수정
##############################################################
kubectl edit cm -n argocd argocd-rbac-cm
# data:
#   policy.csv: ""
#   policy.default: role.readonly # 변경
#   policy.matchMode: glob
#   scopes: '[groups]'
```

![Alice User Main - default policy](/assets/img/ci-cd/ci-cd-study/argocd-alice-user-main-page-readonly.webp)
> Alice 계정에서 Application 확인 (default 정책으로 Application이 보이는 상태)  

이제 마지막으로 admin 사용자를 비활성화 하도록 하겠습니다. `argocd-cm` ConfigMap 에서 `admin.enabled` 필드를 `false` 로 변경하면 됩니다.

```shell
##############################################################
# argocd-cm ConfigMap 리소스 수정 (admin 계정 비활성화)
##############################################################
kubectl edit cm -n argocd argocd-cm
# data:
#   accounts.alice: apiKey,login
#   admin.enabled: "false" # 수정

##############################################################
# admin 계정 비활성화 확인
##############################################################
argocd account list                                                                                 
NAME   ENABLED  CAPABILITIES
admin  false    login
alice  true     apiKey, login
```

---

## 2. 서비스 어카운트

> [Argo CD Docs - RBAC Configuration](https://argo-cd.readthedocs.io/en/stable/operator-manual/rbac/)  

서비스 어카운트는 CI/CD 파이프라인과 같은 자동화 프로세스를 시스템에 인증하는 데 사용하는 계정입니다. 개인 사용자 계정이 비활성화되거나 권한이 변경되면 파이프라인이 실패할 수 있으므로, 서비스 어카운트는 개인 사용자 계정에 종속되어서는 안 됩니다. 또한 서비스 어카운트는 엄격하게 최소 권한 원칙을 적용해야 하며, 파이프라인에서 수행하는 작업 범위를 초과하는 권한을 가져서는 안 됩니다.

Argo CD에서는 서비스 어카운트를 생성하는 방식이 다음 두 가지로 구분됩니다.

1. 로그인 기능은 제거하고 API 키만을 사용하는 로컬 사용자(Local User) 방식
    이 방식은 Argo CD 내에서 별도의 로컬 계정을 생성한 뒤, UI 로그인을 비활성화하고 API 토큰만 발급받아 사용합니다. 주로 CI/CD 파이프라인 또는 자동화 스크립트가 Argo CD API에 접근할 때 사용하며, 불필요한 로그인 권한을 제거함으로써 보안성을 강화할 수 있습니다.

2. 프로젝트 역할(Project Role)을 생성하고 해당 역할에 토큰(Token)을 할당하는 방식
    Argo CD의 Project는 각 애플리케이션 그룹에 대한 RBAC(Role-Based Access Control)을 제공하며, 특정 Project 내에 역할(Role)을 정의하고, 그 역할에 인증 토큰을 발급할 수 있습니다. 이 방식은 멀티테넌시(Multi-tenancy) 환경에서 프로젝트 단위로 권한을 분리하거나, 특정 애플리케이션 그룹에 대해 제한된 권한만 필요한 파이프라인에서 적합합니다.

두 방식 모두 공통적으로 사용자 계정과 분리된 독립적 서비스 계정 생성을 가능하게 하며, 자동화 파이프라인이 요구하는 권한 범위에 따라 적절한 모델을 선택해야 합니다. 특히 Argo CD는 RBAC가 강력하므로 서비스 어카운트를 설계할 때 애플리케이션 단위 또는 Project 단위로 권한을 세분화하여, 불필요한 접근 권한이 부여되지 않도록 주의해야 합니다.

### 2.1. 로컬 서비스 어카운트

API Key만 활성화된 별도의 로컬 계정을 만들어 보겠습니다. 해당 경우 사용자는 UI나 CLI에 대한 암호가 없고 API 키를 생성한 후에만 접근이 가능합니다. 특정 애플리케이션에 대한 동기화를 시작할 수 있는 권한과 같은 특정 권한을 부여하겠습니다.

먼저 아래와 같이 `argocd-cm` ConfigMap을 수정해 `gitops-ci` 라는 서비스 어카운트사용자를 추가하겠습니다.

```shell
##############################################################
# gitops-ci 계정 추가
##############################################################
kubectl edit cm -n argocd argocd-cm
# data:
#   accounts.alice: apiKey,login
#   accounts.gitops-ci: apiKey # 추가

##############################################################
# gitops-ci 계정 확인
##############################################################
argocd account list 
# NAME       ENABLED  CAPABILITIES
# admin      false    login
# alice      true     apiKey, login
# gitops-ci  true     apiKey

##############################################################
# gitops-ci 계정 토큰 생성 시도
##############################################################
argocd account generate-token -a gitops-ci
# {"level":"fatal","msg":"rpc error: code = PermissionDenied desc = permission denied: accounts, update, gitops-ci, sub: alice, iat: 2025-11-15T16:25:36Z","time":"2025-11-16T01:39:39+09:00"}
```

`gitops-ci` 계정 생성은 원활하게 진행이 되었지만, 액세스 토큰 생성 시도 시, 권한 부족으로 인해 permission denied 가 발생했습니다. admin 계정을 다시 활성화하는 방법도 있지만, 다시 비활성화하는 것을 잊어버리거나 오랫동안 admin 계정이 활성화 상태로 머물 수 있기 때문에 좋은 방법은 아닙니다. 따라서 alice 사용자에게 계정 업데이트 권한을 할당하도록 하겠습니다. 권한은 `argocd-rbac-cm` ConfigMap에 `user-update` 라는 새 역할을 정의한 후, 해당 역할을 사용자에게 할당하는 방식으로 부여할 수 있습니다.

> `argocd-rbac-cm`의 policy.csv에서 p의 경우 정책을 정의할 때 사용하고, g의 경우 사용자 또는 그룹에 역할을 연결할 때 사용합니다.  
{: .prompt-tip}

```shell
##############################################################
# argo-rbac-cm ConfigMap 수정 (policy.csv 수정)
##############################################################
kubectl edit cm -n argocd argocd-rbac-cm
# data:
#   policy.csv: | 
#     p, role:user-update, accounts, update, *, allow
#     p, role:user-update, accounts, get, *, allow
#     g, alice, role:user-update

##############################################################
# 서비스 어카운트 토큰 생성 시도
##############################################################
argocd account generate-token -a gitops-ci
# eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJhcmdvY2QiLCJzdWIiOiJnaXRvcHMtY2k6YXBpS2V5IiwibmJmIjoxNzYzMjI1MjkyLCJpYXQiOjE3NjMyMjUyOTIsImp0aSI6IjRkMTE3M2ZjLTQ0MDgtNGU3MC05MGRkLWRhZDBjZjhhNGNjYyJ9.EnzXyrfRzCkQeNuaJVU_78IOCTRYIMaSJDcxE3-MV54

##############################################################
# 서비스 어카운트 토큰 동작 확인
##############################################################
argocd account get-user-info --auth-token eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJhcmdvY2QiLCJzdWIiOiJnaXRvcHMtY2k6YXBpS2V5IiwibmJmIjoxNzYzMjI1MjkyLCJpYXQiOjE3NjMyMjUyOTIsImp0aSI6IjRkMTE3M2ZjLTQ0MDgtNGU3MC05MGRkLWRhZDBjZjhhNGNjYyJ9.EnzXyrfRzCkQeNuaJVU_78IOCTRYIMaSJDcxE3-MV54
# Logged In: true
# Username: gitops-ci
# Issuer: argocd
# Groups: 
```

새로 생성된 서비스 어카운트는 별도로 권한을 부여하지 않는 한 기본적으로 읽기 전용 권한만 가집니다. 읽기 전용 토큰은 실질적인 자동화 작업을 수행하기 어렵기 때문에 실용성이 거의 없습니다. 일반적으로 새 클러스터 등록 또는 등록 해제, 사용자 생성 또는 삭제, 애플리케이션 생성 또는 동기화와 같은 작업을 수행해야 하므로 적절한 역할(Role)을 부여해야 합니다.

> 로컬 계정은 RBAC 그룹에 포함될 수 없으며, 특정 역할을 직접 사용자 단위로 할당하는 방식으로만 권한을 부여할 수 있습니다.  
{: .prompt-tip}

### 2.2. 프로젝트 역할과 토큰

프로젝트 역할(Project Role)은 서비스 어카운트가 사용할 수 있는 두 번째 옵션입니다. Argo CD의 애플리케이션 프로젝트는 역할(Role)을 활용하여 애플리케이션 정의에 다양한 제약 조건을 적용할 수 있습니다. 예를 들어 애플리케이션이 상태를 가져오는 리포지터리, 배포 대상 클러스터, 허용된 네임스페이스를 지정할 수 있으며, 배포가 가능한 리소스 유형을 제한할 수도 있습니다. 이를 통해 특정 프로젝트에서는 애플리케이션이 Secret 리소스를 생성하거나 수정하지 못하도록 설정하는 것도 가능합니다. 이 외에도 프로젝트 단위로 새로운 역할을 생성하고, 해당 역할에 수행 가능한 작업 범위를 정의한 뒤 토큰을 발급하여 서비스 어카운트 또는 자동화 파이프라인에서 사용할 수 있습니다.

Argo CD를 설치하면 기본적으로 `default`라는 프로젝트가 제공되며, 이 기본 프로젝트는 애플리케이션에 대한 제한이 전혀 설정되어 있지 않습니다. (`*` 설정을 통해 모든 리포지터리, 모든 네임스페이스, 모든 리소스 유형을 허용)

```shell
kubectl get appprojects.argoproj.io -n argocd default -o yaml | k neat | yq
# apiVersion: argoproj.io/v1alpha1
# kind: AppProject
# metadata:
#   name: default
#   namespace: argocd
# spec:
#   clusterResourceWhitelist:
#     - group: '*'
#       kind: '*'
#   destinations:
#     - namespace: '*'
#       server: '*'
#   sourceRepos:
#     - '*'
```

이제 프로젝트 기반 토큰 사용 방식을 확인하기 위해 새 프로젝트를 생성하고, 기존 Argo CD 애플리케이션 일부를 이 프로젝트에 연결해 보겠습니다. 새로운 프로젝트를 생성한 후에는 프로젝트 내에서 사용할 역할을 정의하고, 역할에 필요한 권한을 부여한 뒤 토큰을 생성하는 순서로 진행하게 됩니다.

```shell
##############################################################
# AppProject 신규 생성
##############################################################
cat <<EOF | kubectl apply -f -
apiVersion: argoproj.io/v1alpha1
kind: AppProject
metadata:
  name: sample-apps
  namespace: argocd
spec:
  roles:
    - name: read-sync
      description: read and sync privileges
      policies:
        - p, proj:sample-apps:read-sync, applications, get, sample-apps/*, allow
        - p, proj:sample-apps:read-sync, applications, sync, sample-apps/*, allow
  clusterResourceWhitelist:
    - group: '*'
      kind: '*'
  description: Project to configure argocd self-manage application
  destinations:
    - namespace: test
      server: https://kubernetes.default.svc
  sourceRepos:
    - https://github.com/argoproj/argocd-example-apps.git
EOF

kubectl get appproject -n argocd
# NAME          AGE
# default       79m
# sample-apps   0s
```

![Argo CD Project - sample-apps](/assets/img/ci-cd/ci-cd-study/argocd-project-sample-apps.webp)
> 대상 네임스페이스와 클러스터를 제한하고, 정해진 리포지터리로부터 상태 파일을 가져오도록 설정  

![Argo CD Project - sample-apps Roles](/assets/img/ci-cd/ci-cd-study/argocd-project-sample-apps-roles.webp)
> 대상 네임스페이스와 클러스터를 제한하고, 정해진 리포지터리로부터 상태 파일을 가져오도록 설정  

이제 생성한 `sample-apps` 프로젝트에 애플리케이션을 배포 해보겠습니다.

```shell
##############################################################
# 애플리케이션 생성
##############################################################
cat <<EOF | kubectl apply -f -
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: pre-post-sync
  namespace: argocd
  finalizers:
  - resources-finalizer.argocd.argoproj.io
spec:
  project: sample-apps
  source:
    path: pre-post-sync
    repoURL: https://github.com/argoproj/argocd-example-apps
    targetRevision: master
  destination:
    namespace: test
    server: https://kubernetes.default.svc
  syncPolicy:
    automated:
      enabled: false
    syncOptions:
    - CreateNamespace=true
EOF

##############################################################
# 애플리케이션 생성 확인
##############################################################
argocd app list
# NAME                  CLUSTER                         NAMESPACE  PROJECT      STATUS     HEALTH   SYNCPOLICY  CONDITIONS  REPO                                             PATH           TARGET
# argocd/pre-post-sync  https://kubernetes.default.svc  sync-test  sample-apps  OutOfSync  Missing  Manual      <none>      https://github.com/argoproj/argocd-example-apps  pre-post-sync  master

##############################################################
# 동기화 실행 시 실패
##############################################################
argocd app sync argocd/pre-post-sync
# {"level":"fatal","msg":"rpc error: code = PermissionDenied desc = permission denied: applications, sync, sample-apps/pre-post-sync, sub: alice, iat: 2025-11-09T05:41:55Z","time":"2025-11-09T16:12:09+09:00"}
```

alice 사용자 계정으로 생성한 어플리케이션 `sync`를 진행하려 했지만 권한 부족으로 인해 PermissionDenied 에러가 발생했습니다. `argocd-rbac-cm` ConfigMap을 수정에 필요한 권한을 추가하고, 역할에 대한 토큰을 생성한 뒤, 해당 토큰을 사용해 Sync 재시도를 진행해보겠습니다.

```shell
##############################################################
# user-update 역할에 권한 추가
##############################################################
data:
  policy.csv: |
    p, role:user-update, accounts, update, *, allow
    p, role:user-update, accounts, get, *, allow
    p, role:user-update, projects, update, sample-apps, allow # 추가
    g, alice, role:user-update


argocd proj role create-token sample-apps read-sync
# Create token succeeded for proj:sample-apps:read-sync.
#   ID: 1f83b927-fc2b-4b1b-ba2a-26392ccaffa7
#   Issued At: 2025-11-16T02:14:39+09:00
#   Expires At: Never
#   Token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJhcmdvY2QiLCJzdWIiOiJwcm9qOnNhbXBsZS1hcHBzOnJlYWQtc3luYyIsIm5iZiI6MTc2MzIyNjg3OSwiaWF0IjoxNzYzMjI2ODc5LCJqdGkiOiIxZjgzYjkyNy1mYzJiLTRiMWItYmEyYS0yNjM5MmNjYWZmYTcifQ.LphrYhdZkb7nCNgNzIMXunXnZD6BqyykwpqhkbykBG0

##############################################################
# 동기화 재시도 (계정 권한)
##############################################################
argocd app sync argocd/pre-post-sync
# {"level":"fatal","msg":"rpc error: code = PermissionDenied desc = permission denied: applications, sync, sample-apps/pre-post-sync, sub: alice, iat: 2025-11-15T16:25:36Z","time":"2025-11-16T02:16:04+09:00"}

##############################################################
# 동기화 재시도 (발급한 프로젝트 역할 권한)
##############################################################
TOKEN=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJhcmdvY2QiLCJzdWIiOiJwcm9qOnNhbXBsZS1hcHBzOnJlYWQtc3luYyIsIm5iZiI6MTc2MzIyNjg3OSwiaWF0IjoxNzYzMjI2ODc5LCJqdGkiOiIxZjgzYjkyNy1mYzJiLTRiMWItYmEyYS0yNjM5MmNjYWZmYTcifQ.LphrYhdZkb7nCNgNzIMXunXnZD6BqyykwpqhkbykBG0
argocd app sync argocd/pre-post-sync --auth-token $TOKEN
# ...
# Name:               argocd/pre-post-sync
# Project:            sample-apps
# Server:             https://kubernetes.default.svc
# Namespace:          test
# URL:                https://argocd.example.com/applications/argocd/pre-post-sync
# Source:
# - Repo:             https://github.com/argoproj/argocd-example-apps
#   Target:           master
#   Path:             pre-post-sync
# SyncWindow:         Sync Allowed
# Sync Policy:        Manual
# Sync Status:        Synced to master (0d521c6)
# Health Status:      Healthy

# Operation:          Sync
# Sync Revision:      0d521c6e049889134f3122eb32d7ed342f43ca0d
# Phase:              Succeeded
# Start:              2025-11-16 02:18:37 +0900 KST
# Finished:           2025-11-16 02:19:12 +0900 KST
# Duration:           35s
# Message:            successfully synced (no more tasks)
# ...
```

![ArgoCD Application Sync Result](/assets/img/ci-cd/ci-cd-study/argocd-application-sync-result.webp)
> ArgoCD Application Sync 결과  

![ArgoCD Events](/assets/img/ci-cd/ci-cd-study/argocd-application-sync-events.webp)
> ArgoCD Application Sync Events 확인  

프로젝트 역할(Project Role) 기반으로 생성되는 모든 토큰은 해당 역할 내에 저장되며, 토큰이 마지막으로 사용된 시점과 교체가 필요한 시기를 확인할 수 있습니다. 필요한 경우 토큰에 만료 일자를 지정하여 일정 기간 동안만 사용하도록 구성할 수도 있습니다. 다만 만료 주기를 지나치게 짧게 설정하면 관리자가 주기적으로 토큰을 재발급해야 하기 때문에 운영 부담이 증가할 수 있습니다.

```shell
##############################################################
# 토큰 정보 확인
##############################################################
argocd account get --account gitops-ci
# Name:               gitops-ci
# Enabled:            true
# Capabilities:       apiKey

# Tokens:
# ID                                    ISSUED AT                  EXPIRING AT
# 4d1173fc-4408-4e70-90dd-dad0cf8a4ccc  2025-11-16T01:48:12+09:00  never

##############################################################
# 토큰으로 확인 iat: 발급 시각, exp: 만료 시각 (Unix time)
##############################################################
TOKEN=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJhcmdvY2QiLCJzdWIiOiJwcm9qOnNhbXBsZS1hcHBzOnJlYWQtc3luYyIsIm5iZiI6MTc2MzIyNjg3OSwiaWF0IjoxNzYzMjI2ODc5LCJqdGkiOiIxZjgzYjkyNy1mYzJiLTRiMWItYmEyYS0yNjM5MmNjYWZmYTcifQ.LphrYhdZkb7nCNgNzIMXunXnZD6BqyykwpqhkbykBG0
echo "$TOKEN" | cut -d '.' -f2 | base64 -d 2>/dev/null | jq .
# {
#   "iss": "argocd",
#   "sub": "proj:sample-apps:role:read-sync",
#   "iat": 1763225292,
#   "exp": 1765827292,
#   "jti": "...."
# }

##############################################################
# Unix time -> UTC 변환
##############################################################
date -d @1763225292 -u
# Sat Nov 15 16:48:12 UTC 2025

##############################################################
# Unix time -> KST 변환
##############################################################
TZ='Asia/Seoul' date -d @1763225292
# Sun Nov 16 01:48:12 KST 2025
```

프로젝트 역할 기반으로 생성된 토큰에는 만료 시각(exp)을 설정할 수 있으며, 이를 기준으로 교체(로테이션) 시점을 관리할 수 있습니다. 토큰의 실제 사용 여부나 마지막 사용 시점은 `argocd-server`의 접근 로그, Kubernetes Audit 로그, 혹은 Argo CD 앞단에서 동작하는 프록시,게이트웨이(NGINX Ingress, Envoy, API Gateway 등)의 Access 로그를 통해 확인할 수 있습니다. 이러한 로그에는 요청에 사용된 토큰의 식별 정보(sub 또는 jti)가 기록되므로, 이를 기반으로 특정 토큰이 언제 마지막으로 사용되었는지를 추적할 수 있습니다. 이렇게 확보한 사용 기록과 함께 사전에 정의한 만료 정책을 적용하여 주기적인 토큰 로테이션 전략을 운영하는 것이 일반적으로 권장됩니다.

---

## 3. SSO (Single Sign-On)

SSO를 사용하면 중앙 인증(central authentication)을 통해 한 번 로그인한 후, 이를 기반으로 여러 독립적인 애플리케이션에 대한 권한을 부여받을 수 있습니다. 예를 들어 `argocd.mycompany.com`에 접근하려는 경우, `argocd.mycompany.com`은 외부 공급자를 신뢰해 사용자의 신원을 확인합니다. 또한 `argocd.mycompany.com`에 대한 접근 유형은 외부 마스터 시스템에서 사용자의 소속 그룹 또는 계정 설정에 따라 제어할 수 있습니다.

SSO를 사용하게 되면 사용하는 모든 애플리케이션마다 각각의 암호가 필요하지 않고 하나의 대시보드에서 모든 것을 제어하며 구성원을 쉽게 추가/삭제(onboarding/offboarding) 할 수 있어 보안적인 이점이 있습니다.

Argo CD는 아래와 같은 두 가지 방법으로 SSO 기능을 제공합니다.

1. 기본적으로 설치되는 Dex OIDC 공급자 사용
2. Dex 설치 없이 다른 OIDC 공급자를 통해 Argo CD를 직접 사용

SSO를 활성화한 상태에서 로그인 할수 있는 로컬 계정이 없고 관리자가 비활성화된 경우, 사용자/비밀번호 입력 양식이 UI에서 자동으로 제거되고 SSO를 통한 로그인 버튼만 남게 됩니다.

![ArgoCD SSO Main Page](/assets/img/ci-cd/ci-cd-study/argocd-sso-main-page.webp)

### 3.1. Keycloak을 사용한 SSO 연동

#### 3.1.1. Keycloak 소개

Keycloak은 애플리케이션에 초점을 맞춘 **오픈 소스 ID 및 접근(권한) 관리 도구**입니다. 사용자는 Keycloak을 통해 인증을 수행하고, 애플리케이션은 Keycloak이 발급하는 토큰을 기반으로 권한을 검증합니다. 이를 통해 애플리케이션은 직접 사용자 자격 증명(아이디/비밀번호)을 관리하지 않고도 안전한 인증·인가 기능을 제공할 수 있습니다.  
> [Keycloak Docs](https://www.keycloak.org/)  

Keycloak의 주요 특징은 다음과 같습니다.

- **강력한 로그인/인증 기능 제공**
  - Keycloak은 완전히 커스터마이징 가능한 로그인 페이지를 제공하며, 암호 복구, 주기적인 암호 변경, 이용 약관 동의, MFA(다단계 인증) 등 다양한 기능을 제공합니다.
  - 이 기능들을 애플리케이션마다 직접 구현할 필요가 없고, Keycloak 쪽 설정만으로 공통 로그인 UX를 구성할 수 있습니다.
- **애플리케이션이 자격 증명을 직접 다루지 않음**
  - Keycloak을 통해 인증을 수행하면 각 애플리케이션은 서로 다른 인증 메커니즘을 구현할 필요가 없고, 비밀번호 저장·관리의 보안 이슈에서도 자유로워집니다.
  - 애플리케이션은 사용자 자격 증명에 직접 접근하지 않고, 필요한 정보에만 접근할 수 있는 **보안 토큰(JWT 등)**을 사용합니다.
- **Single Sign-On(SSO) 및 세션 관리**
  - Keycloak은 SSO 기능을 제공하여 사용자가 한 번만 인증하면 여러 애플리케이션에 접근할 수 있습니다.
  - 사용자와 관리자 모두 “현재 사용자가 어디에 로그인되어 있는지”를 확인할 수 있고, 필요 시 원격으로 세션을 종료할 수도 있습니다.
- **표준 프로토콜 기반**
  - Keycloak은 **OAuth 2.0**, **OpenID Connect**, **SAML 2.0**과 같은 업계 표준 프로토콜을 기반으로 동작합니다.
  - 덕분에 다양한 언어·프레임워크·플랫폼에서 제공하는 표준 클라이언트 라이브러리를 활용해 쉽게 연동할 수 있습니다.
- **유연한 사용자 저장소 및 연동 기능**
  - Keycloak은 자체 사용자 데이터베이스를 기본으로 제공하지만, 기존 인증 인프라와도 손쉽게 통합할 수 있습니다.
  - **Identity Brokering** 기능을 통해 소셜 로그인(구글, 깃허브 등)이나 다른 엔터프라이즈 ID 공급자의 계정을 그대로 연동할 수 있습니다.

    ![Identity Brokering and Social Login](/assets/img/ci-cd/ci-cd-study/keyclaok-identity-brokering-and-social-login.webp)
    > Identity Brokering and Social Login
  
  - 또한 Active Directory 및 LDAP 서버와 같은 기존 사용자 디렉터리와 통합하는 **User Federation** 기능을 제공합니다.

    ![User Federation](/assets/img/ci-cd/ci-cd-study/keyclaok-user-federation.webp)
    > User Federation
- **경량, 고가용성, 확장성**
  - Keycloak은 비교적 가볍고 설치가 쉬운 솔루션이며, 클러스터링 기능을 통해 고가용성을 제공합니다.
  - 여러 데이터 센터에 대한 클러스터링도 지원하여 좀 더 고도화된 이중화 구성을 만들 수 있습니다.
  - 커스텀 코드(확장 포인트)를 통해 사용자 정의 인증 메커니즘, 사용자 저장소, 토큰 연동 로직 등 다양한 부분을 확장할 수 있습니다.

#### 3.1.2. OpenID Connect의 권한 부여 코드 흐름

Argo CD를 Keycloak과 직접 연동하면 다음과 같은 구조를 가지게 됩니다.

- **User** — (브라우저) → **Application(Argo CD, OAuth Client 역할)** —→ **Keycloak (Authorization Server, OpenID Provider)**

OpenID Connect의 **Authorization Code Flow**를 사용하면 다음과 같은 흐름으로 인증이 이루어집니다.

![OpenID Connect authorization code flow simplied](/assets/img/ci-cd/ci-cd-study/openid-connect-authorization-code-flow-simplied.webp)

1. **Argo CD**는 인증 요청을 준비하고, 사용자의 브라우저를 Keycloak으로 리디렉션합니다.
2. 브라우저는 사용자를 Keycloak의 Authorization Endpoint로 보냅니다.
3. 사용자가 아직 Keycloak에 로그인하지 않았다면, Keycloak은 사용자 인증을 진행합니다.
4. 인증이 완료되면 Keycloak은 **Authorization Code**를 Argo CD로 전달합니다.
5. Argo CD는 이 Authorization Code를 사용해 Keycloak의 Token Endpoint에서 **ID Token + Access Token**을 발급받습니다.
6. Argo CD는 ID Token을 사용해 사용자의 신원을 확인하고, 내부 세션을 설정합니다.

#### 3.1.3. Argo CD - Keycloak 연동

앞에서 살펴본 것처럼 Keycloak은 OAuth 2.0 / OpenID Connect 기반의 ID 및 접근 관리 도구이며, Argo CD는 OIDC를 통해 Keycloak과 직접 연동할 수 있습니다.  
이 연동 구성을 통해 Argo CD는 Keycloak을 **외부 인증 서버(IdP)** 로 사용하고, 사용자는 Keycloak 계정(또는 연동된 사내 디렉터리/소셜 계정)을 통해 Argo CD에 로그인할 수 있습니다.

Argo CD와 Keycloak을 연동하는 전체 절차(클라이언트 생성, 리다이렉트 URI 설정, OIDC 설정, 그룹 기반 RBAC 연동 등)는 아래 공식 문서를 따르는 것을 권장합니다.

- [Argo CD Docs - User Management / Keycloak](https://argo-cd.readthedocs.io/en/stable/operator-manual/user-management/keycloak/)
- [Keycloak & ArgoCD SSO 구현하기]({% post_url 2025/02/2025-02-23-keycloak-argocd-sso %})
- [Keycloak 개념, Helm으로 배포하기]({% post_url 2025/02/2025-02-22-keycloak %})

---

## 4. Reference

- [OWASP - OWASP Top 10 2021](https://owasp.org/www-project-top-ten/)
- [Argo CD FAQ - Admin Password Reset](https://github.com/argoproj/argo-cd/blob/master/docs/faq.md#i-forgot-the-admin-password-how-do-i-reset-it)
- [예제로 배우는 Argo CD](https://product.kyobobook.co.kr/detail/S000212377128)
- [Wiki - Principle of least privilege](https://en.wikipedia.org/wiki/Principle_of_least_privilege)
- [GitHub - argocd-example-apps](https://github.com/argoproj/argocd-example-apps)
- [Argo CD Docs - User Management / Overview](https://argo-cd.readthedocs.io/en/stable/operator-manual/user-management/)
- [Argo CD Docs - Operator Manual / RBAC Configuration](https://argo-cd.readthedocs.io/en/stable/operator-manual/rbac/)
- [Argo CD Docs - User Management / Keycloak](https://argo-cd.readthedocs.io/en/stable/operator-manual/user-management/keycloak/)
- [Keycloak Docs](https://www.keycloak.org/)
- [Kubernetes Default Service Endpoint](https://kubernetes.default.svc)
- [[10분 테코톡] 홍실의 Oauth 2.0](https://youtu.be/Mh3LaHmA21I?si=upaUrBNdzOZR_tBl)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
