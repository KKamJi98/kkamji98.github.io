---
title: Argo CD App of Apps & ApplicationSet
date: 2025-11-21 22:19:02 +0900
author: kkamji
categories: [DevOps]
tags: [devops, ci-cd-study, ci-cd-study-5w, gitops, kubernetes, argocd, applicationset]
comments: true
image:
  path: /assets/img/ci-cd/ci-cd-study/ci-cd-study.webp
---

`CloudNet@` Gasida님이 진행하는 `CI/CD + ArgoCD + Vault Study`를 진행하며 학습한 내용을 공유합니다.

이번 포스팅에서는 Argo CD의 App of Apps와 ApplicationSet 리소스에 대해 알아보고, [이전 포스팅]({% post_url 2025/2025-11-18-argocd-cluster-management-6w %})에서 구축한 `kind-mgmt`, `kind-dev`, `kind-prd` 3개의 클러스터에 ApplicationSet 리소스를 활용해 애플리케이션을 배포하는 과정을 정리해보겠습니다.

---

## 1. 실습 환경 구성

![Argo CD Multi-Cluster Architecture](/assets/img/ci-cd/ci-cd-study/argo-multi-cluster-architecture.webp)

- **kind-mgmt**: Argo CD가 설치되는 **제어(Control) 클러스터**
- **kind-prd**: 실제 서비스가 운영된다고 가정한 **운영 클러스터**
- **kind-dev**: 개발 및 테스트가 이루어지는 **개발 클러스터**

`kind-mgmt`에 설치된 Argo CD는 `kind-prd`와 `kind-dev` 클러스터의 자격 증명을 등록받아, Git 저장소의 변경 사항을 각 대상 클러스터로 동기화(Sync)하는 역할을 수행합니다.

---

## 2. App of Apps Pattern이란?

**App of Apps 패턴은 ‘하나의 Root Application이 여러 Child Application을 생성·관리’하도록 구성하는 Argo CD 구조적 패턴입니다.**

다시 말해, Root Application 하나만 배포해도 Root Application 내부에서 정의한 모든 하위 Application이 자동 생성됩니다.

### 2.1. App of Apps 패턴이 유용한 경우

- 디렉터리 구조 기반으로 환경별/도메인별 앱을 자동 묶고 싶을 때  
- 공통적인 설정을 하나의 Root Application에서 통일하고 싶을 때  
- 팀별, 서비스별 앱 구조를 일관적으로 유지해야 할 때  
- GitOps를 처음 도입하는 팀에서 **정적 관리가 필요한 경우**

### 2.2. 주요 특징 요약

- **선언적 구조**: Root YAML 파일에서만 전체 애플리케이션 정의  
- **그룹화**: 환경/도메인 단위의 논리적 그룹 관리  
- **일관성 유지**: 동일한 패턴을 여러 환경에 확장 가능  
- **통합 모니터링**: Root를 통해 전체 앱의 Sync/Health 상태 확인  
- **재사용성**: 공통 spec 또는 설정 재사용 가능  

---

## 3. App of Apps Pattern 실습

실습 코드 - [GitHub Link](https://github.com/KKamJi98/kkamji-lab/tree/main/study/ci-cd-study/6w-3-of-3-argocd/cicd-study/apps)

{% raw %}
```shell
# https://github.com/KKamJi98/kkamji-lab/blob/main/study/ci-cd-study/6w-3-of-3-argocd/cicd-study/apps/templates/applications.yaml
{{- range .Values.applications }}
{{- $config := $.Values.config -}}
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: {{ printf "example.%s" .name | quote }}
  namespace: argocd
  finalizers:
  - resources-finalizer.argocd.argoproj.io
spec:
  destination:
    namespace: {{ .namespace | default .name | quote }}
    server: {{ $config.spec.destination.server | quote }}
  project: default
  source:
    path: {{ .path | default .name | quote }}
    repoURL: {{ $config.spec.source.repoURL }}
    targetRevision: {{ $config.spec.source.targetRevision }}
    {{- with .tool }}
    {{- . | toYaml | nindent 4 }}
    {{- end }}
  syncPolicy:
    syncOptions:
      - CreateNamespace=true
    automated:
      prune: true
      selfHeal: true
---
{{ end -}}

# https://github.com/KKamJi98/kkamji-lab/blob/main/study/ci-cd-study/6w-3-of-3-argocd/cicd-study/apps/values.yaml
config:
  spec:
    destination:
      server: https://kubernetes.default.svc
    source:
      repoURL: https://github.com/KKamJi98/kkamji-lab
      targetRevision: main

applications:
  - name: helm-guestbook
    tool:
      helm:
        releaseName: helm-guestbook
  - name: kustomize-guestbook
  - name: sync-waves

##############################################################
# Root Application 하나에 여러 Application manifest를 넣어 관리
##############################################################
argocd app create apps \
  --dest-namespace argocd \
  --dest-server https://kubernetes.default.svc \
  --repo https://github.com/KKamJi98/kkamji-lab.git \
  --path study/ci-cd-study/6w-3-of-3-argocd/cicd-study/apps
# application 'apps' created

##############################################################
# Root Application을 sync하면 하위 앱들이 자동 생성됨
##############################################################
argocd app sync apps

##############################################################
# 배포 리소스 확인
##############################################################
argocd app list
# NAME                                CLUSTER                         NAMESPACE            PROJECT  STATUS     HEALTH       SYNCPOLICY  CONDITIONS  REPO                                        PATH                                                               TARGET
# argocd/apps                         https://kubernetes.default.svc  argocd               default  Synced     Healthy      Manual      <none>      https://github.com/KKamJi98/kkamji-lab.git  study/ci-cd-study/6w-3-of-3-argocd/cicd-study/apps                 
# argocd/example.helm-guestbook       https://kubernetes.default.svc  helm-guestbook       default  Synced     Progressing  Auto-Prune  <none>      https://github.com/KKamJi98/kkamji-lab      study/ci-cd-study/6w-3-of-3-argocd/cicd-study/helm-guestbook       main
# argocd/example.kustomize-guestbook  https://kubernetes.default.svc  kustomize-guestbook  default  Synced     Progressing  Auto-Prune  <none>      https://github.com/KKamJi98/kkamji-lab      study/ci-cd-study/6w-3-of-3-argocd/cicd-study/kustomize-guestbook  main
# argocd/example.sync-waves           https://kubernetes.default.svc  sync-waves           default  OutOfSync  Missing      Auto-Prune  <none>      https://github.com/KKamJi98/kkamji-lab      study/ci-cd-study/6w-3-of-3-argocd/cicd-study/sync-waves           main

kubectl get pod -A
# NAMESPACE             NAME                                                 READY   STATUS              RESTARTS   AGE
# argocd                argocd-application-controller-0                      1/1     Running             0          7d9h
# argocd                argocd-applicationset-controller-bbff79c6f-9k4zh     1/1     Running             0          7d9h
# argocd                argocd-dex-server-6877ddf4f8-5xqw4                   1/1     Running             0          7d9h
# argocd                argocd-notifications-controller-7b5658fc47-fqfj9     1/1     Running             0          7d9h
# argocd                argocd-redis-7d948674-nzsv4                          1/1     Running             0          7d9h
# argocd                argocd-repo-server-7679dc55f5-s478b                  1/1     Running             0          7d9h
# argocd                argocd-server-787fb5f956-x7smn                       1/1     Running             0          7d9h
# helm-guestbook        helm-guestbook-667dffd5cf-wntkf                      1/1     Running             0          73s
# kube-system           coredns-668d6bf9bc-v48nm                             1/1     Running             0          7d9h
# kube-system           coredns-668d6bf9bc-xkvn4                             1/1     Running             0          7d9h
# kube-system           etcd-mgmt-control-plane                              1/1     Running             0          7d9h
# kube-system           kindnet-h846b                                        1/1     Running             0          7d9h
# kube-system           kube-apiserver-mgmt-control-plane                    1/1     Running             0          7d9h
# kube-system           kube-controller-manager-mgmt-control-plane           1/1     Running             0          7d9h
# kube-system           kube-proxy-ldvgf                                     1/1     Running             0          7d9h
# kube-system           kube-scheduler-mgmt-control-plane                    1/1     Running             0          7d9h
# kustomize-guestbook   kustomize-guestbook-ui-85db984648-m8624              1/1     Running             0          73s
# local-path-storage    local-path-provisioner-7dc846544d-r4rm2              1/1     Running             0          7d9h
# sync-waves            backend-t862l                                        1/1     Running             0          58s
# sync-waves            maint-page-up-gtxwf                                  0/1     ContainerCreating   0          1s
# sync-waves            upgrade-sql-schemae5a62da-presync-1764416226-jgtmr   0/1     Completed           0          73s


##############################################################
# 삭제
##############################################################
argocd app delete argocd/apps --yes
```
{% endraw %}

1. `apps` Application 배포 후 (현재 Root App 만 배포 된 상태)
  ![apps Application 배포 후](/assets/img/ci-cd/ci-cd-study/argo-cd-app-of-apps-root-application-deploy.webp)
2. Root App을 Sync (하위 App이 자동으로 생성됨)
  ![apps Application Sync](/assets/img/ci-cd/ci-cd-study/argo-cd-app-of-apps-root-application-sync.webp)

---

## 4. App of Apps 패턴의 한계점

App of Apps 패턴은 여러 애플리케이션을 그룹화하여 일관된 방식으로 관리할 수 있다는 장점이 있지만, 실제 운영 환경에서는 다음과 같은 한계점이 존재합니다.

1. **앱 개수를 동적으로 생성할 수 없음**
   - Application 목록이 정적 YAML에 고정되어 있어, 예를 들어 고객 테넌트가 100개라면 Application을 100개 수동으로 생성해야 합니다. 폴더 수에 따라 Application을 자동으로 생성하는 기능이 없습니다.

2. **Git 구조와 Application 구조 간 결합도가 높음**
   - Git 폴더 구조가 변경되면 root app도 함께 수정해야 하며, 멀티 리포지토리나 템플릿 구조에서는 관리가 불편합니다.

3. **여러 클러스터/여러 namespace 자동 확장이 어려움**
   - 클러스터가 5개라면 App of Apps에 Application을 5개 수동으로 추가해야 하며, 자동 discovery가 불가능합니다.

4. **Multi-tenant 구조에서 스케일링 문제**
   - 테넌트가 증가할수록 root app YAML의 Application 목록이 비대해지고, Git 충돌 및 관리 복잡도가 증가합니다.

5. **정적(static) 구성의 한계**
   - App of Apps는 기본적으로 정적 YAML 집합이기 때문에, 동적으로 Application을 생성해야 하는 상황(예: Helm values에 따라 지역별 Application 생성, 특정 label을 가진 클러스터에만 app 자동 배포, 팀별 자동 Application 생성 등)에 적합하지 않습니다.

이러한 한계점을 해결하기 위해 Argo CD 팀은 **ApplicationSet** 컨트롤러를 별도의 프로젝트로 개발하여, 자동 생성 및 템플릿 기반의 동적 Application 관리가 가능하도록 지원하고 있습니다.

---

## 5. ApplicationSet이란?

- ApplicationSet 컨트롤러는 [CustomResourceDefinition](https://kubernetes.io/docs/tasks/extend-kubernetes/custom-resources/custom-resource-definitions/) (CRD) 지원을 추가하는 [쿠버네티스 컨트롤러](https://kubernetes.io/docs/concepts/architecture/controller/) 입니다.
- 이 컨트롤러/CRD는 다수의 클러스터와 모노리포 내에서 [Argo CD](https://argo-cd.readthedocs.io/en/stable/) 애플리케이션을 관리하는 자동화와 유연성을 제공합니다.


### 5.1. ApplicationSet이 제공하는 핵심 기능

- Argo CD를 사용하여 단일 Kubernetes 매니페스트를 사용하여 여러 Kubernetes 클러스터에 배포
- Argo CD를 사용하여 하나 이상의 Git 저장소에서 여러 애플리케이션을 배포하기 위해 단일 Kubernetes 매니페스트를 사용하는 기능
- 모노레포에 대한 지원 개선: Argo CD 컨텍스트에서 모노레포는 단일 Git 저장소 내에 정의된 여러 Argo CD 애플리케이션 리소스입니다.
- 다중 테넌트 클러스터 내에서 Argo CD를 사용하여 개별 클러스터 테넌트가 애플리케이션을 배포하는 기능을 향상시킵니다(대상 클러스터/네임스페이스를 활성화하는 데 권한이 있는 클러스터 관리자가 관여할 필요 없음)

![Argo CD ApplicationSet 구조](/assets/img/ci-cd/ci-cd-study/argo-cd-introduce-applicationset.webp)

- 위 그림처럼 **ApplicationSet Controller**(그림 중앙 맨 상단)는 **Argo CD**(그림 중간)와 통신하며, Argo CD 네임스페이스 내에서 **Application 리소스를 생성·수정·삭제하는 역할만 수행**합니다.
- 즉, ApplicationSet의 유일한 목표는 **ApplicationSet 리소스에 선언된 상태를 실제 Argo CD Application 리소스 상태와 일치시키는 것(Reconciliation)** 입니다.
- 클러스터 생성이나 Secret 생성 같은 작업은 다른 컴포넌트/관리자가 수행하고, ApplicationSet은 **이미 정의된 정보(클러스터, Git, SCM 등)를 조합해 Application을 자동으로 만들어주는 오케스트레이터**에 가깝습니다.

### 5.2. Generator 개념과 종류

ApplicationSet이 갖는 가장 큰 강점은 **다양한 데이터 소스를 통해 Application을 동적으로 생성할 수 있는 Generator**입니다.

- **Generator**  
  - ApplicationSet의 **핵심 구성 요소**로, "어떤 매개변수(parameter) 집합을 기반으로 Application 템플릿을 여러 개 찍어낼 것인가?"를 정의하는 역할을 합니다.
{% raw %}
  - 각 Generator는 서로 다른 데이터 소스를 사용해 `{{ .cluster }}`, `{{ .url }}`, `{{ .name }}` 등의 변수를 생성하고,  
    `template` 섹션에 정의된 Application 템플릿에 주입합니다.
{% endraw %}

주요 Generator는 다음과 같습니다.

- **List**  
  - 사용자가 정의한 **고정된 리스트**를 기반으로 파라미터를 생성
  - 보통 `cluster`, `url` 등의 필드를 사용하지만, 임의의 key/value도 지원
- **Cluster**  
  - Argo CD에 이미 등록된 **클러스터 Secret 목록**을 기반으로 동적으로 파라미터 생성
  - 클러스터 추가/삭제 이벤트에 자동으로 반응
- **Git**  
  - Git 리포지터리의 **파일/디렉터리 구조**를 기반으로 Application 생성
- **Matrix**  
  - 두 개의 서로 다른 Generator 결과를 **데카르트 곱(조합)**으로 생성
  - 예: `(클러스터 목록) × (서비스 목록)`
- **Merge**  
  - 두 개 이상의 Generator 결과를 **병합**하여 단일 파라미터 집합 생성
- **SCM Provider**  
  - GitHub/GitLab 등 **SCM Provider API**를 사용해 조직/그룹 내 리포지터리를 자동 검색
- **Pull Request**  
  - GitHub 등 SCM의 **PR 목록을 기준으로 임시 Preview Application** 생성
- **Cluster Decision Resource**  
  - 외부 커스텀 리소스를 참조해 "어떤 클러스터에 배포할지"를 결정
- **Plugin**  
  - 외부 HTTP RPC를 호출해 파라미터를 생성하는 **확장 가능한 Generator**

> **ApplicationSet = (Generator로 파라미터 생성) + (Template로 Application 정의)**  
{: .prompt-tip}

---

### 5.3. List Generator - [Docs](https://argo-cd.readthedocs.io/en/stable/operator-manual/applicationset/Generators-List/)

**List Generator**는 가장 단순하면서 직관적인 Generator로, **"고정된 목록을 기반으로 여러 개의 Application을 생성"**하는 데 사용됩니다.

#### 5.3.1. List Generator 예제

{% raw %}
```yaml
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: guestbook
  namespace: argocd
spec:
  goTemplate: true
  goTemplateOptions: ["missingkey=error"]
  generators:
    - list:
        elements:
          - cluster: engineering-dev
            url: https://1.2.3.4
          - cluster: engineering-staging
            url: https://2.4.6.8
          - cluster: engineering-prod
            url: https://9.8.7.6
  template:
    metadata:
      name: '{{ .cluster }}-guestbook'
    spec:
      project: "my-project"
      source:
        repoURL: https://github.com/argoproj/argo-cd.git
        targetRevision: HEAD
        path: applicationset/examples/list-generator/guestbook/{{ .cluster }}
      destination:
        server: '{{ .url }}'
        namespace: guestbook
```
{% endraw %}

- `elements` 아래에 클러스터 이름과 API 서버 URL 목록을 명시합니다.
{% raw %}
- ApplicationSet 컨트롤러는 각 요소에 대해 `{{ .cluster }}`, `{{ .url }}` 값을 템플릿에 주입하여 `engineering-dev-guestbook`, `engineering-staging-guestbook`, `engineering-prod-guestbook` 3개의 Application을 자동 생성합니다.
{% endraw %}
- 고정된 클러스터 목록에 동일한 애플리케이션을 배포할 때 매우 단순하고 직관적인 방식입니다.

> 다만, 새 클러스터가 추가되면 List에 항목을 직접 추가해야 하므로, "클러스터가 자주 바뀌는 환경"에서는 Cluster Generator가 더 적합합니다.  
{: .prompt-tip}

### 5.4. Cluster Generator - [Docs](https://argo-cd.readthedocs.io/en/stable/operator-manual/applicationset/Generators-Cluster/)

**Cluster Generator**는 Argo CD에 등록된 클러스터 Secret 정보를 기반으로 Application을 생성합니다.

- Argo CD는 관리 대상 클러스터를 Secret 리소스로 관리합니다.
- Cluster Generator는 해당 Secret을 읽어 `name`, `server`, `metadata.labels` 등을 파라미터로 넘겨줍니다.
- 따라서 새로운 클러스터를 Argo CD에 추가만 해도, ApplicationSet이 자동으로 해당 클러스터를 타깃으로 Application을 생성할 수 있습니다.

#### 5.4.1. 모든 클러스터 대상 예제

{% raw %}
```yaml
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: guestbook
  namespace: argocd
spec:
  goTemplate: true
  goTemplateOptions: ["missingkey=error"]
  generators:
    - clusters: {} # Argo CD에 정의된 모든 클러스터 자동 대상
  template:
    metadata:
      name: '{{ .name }}-guestbook' # Secret의 name 필드
    spec:
      project: "my-project"
      source:
        repoURL: https://github.com/argoproj/argocd-example-apps/
        targetRevision: HEAD
        path: guestbook
      destination:
        server: '{{ .server }}'      # Secret의 server 필드
        namespace: guestbook
```
{% endraw %}

- Argo CD에 새 클러스터가 등록되면 곧바로 Application이 자동 추가되고, 제거되면 해당 Application도 자동으로 정리됩니다.

#### 5.4.2. Label Selector 기반 필터링 예제 [GitHub](https://github.com/argoproj/argo-cd/blob/master/docs/operator-manual/applicationset/Generators-Cluster.md)

Cluster Generator는 **레이블 셀렉터(Label Selector)**를 사용하여, 특정 레이블이 붙은 클러스터만 선택할 수도 있습니다.

{% raw %}
```yaml
# 예시: Argo CD 클러스터 Secret
apiVersion: v1
kind: Secret
metadata:
  labels:
    argocd.argoproj.io/secret-type: cluster
    staging: "true" # 레이블 기반 매칭
data:
  # (... 생략 ...)
---
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: guestbook
  namespace: argocd
spec:
  goTemplate: true
  goTemplateOptions: ["missingkey=error"]
  generators:
    - clusters:
        selector:
          matchLabels:
            staging: "true" # 레이블 기반 매칭
        # matchExpressions도 지원
        # matchExpressions:
        #   - key: staging
        #     operator: In
        #     values:
        #       - "true"
  template:
    metadata:
      name: '{{ .name }}-guestbook'
    spec:
      project: "my-project"
      source:
        repoURL: https://github.com/argoproj/argocd-example-apps/
        targetRevision: HEAD
        path: guestbook
      destination:
        server: '{{ .server }}'
        namespace: guestbook
```
{% endraw %}

---

## 6. List Generator 실습 (dev/prd 멀티 클러스터 예제)

이제 List Generator를 이용해 두 개의 kind 클러스터(dev, prd)에 동시에 guestbook 앱을 배포해 보겠습니다.

### 6.1. 클러스터 IP 확인

```shell
##############################################################
# kind 네트워크 정보 확인 및 변수 할당
##############################################################
docker network inspect kind | grep -E 'Name|IPv4Address'

DEVK8SIP=dev-control-plane
PRDK8SIP=prd-control-plane
echo $DEVK8SIP $PRDK8SIP
```

### 6.2. ApplicationSet manifest 작성

{% raw %}
```shell
cat <<EOF | kubectl apply -f -
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: guestbook
  namespace: argocd
spec:
  goTemplate: true
  goTemplateOptions: ["missingkey=error"]
  generators:
    - list:
        elements:
          - cluster: dev-k8s
            url: https://$DEVK8SIP:6443
          - cluster: prd-k8s
            url: https://$PRDK8SIP:6443
  template:
    metadata:
      name: '{{ .cluster }}-guestbook'
      labels:
        environment: '{{ .cluster }}'
        managed-by: applicationset
    spec:
      project: default
      source:
        repoURL: https://github.com/gasida/cicd-study.git
        targetRevision: HEAD
        path: appset/list/{{ .cluster }}
      destination:
        server: '{{ .url }}'
        namespace: guestbook
      syncPolicy:
        syncOptions:
          - CreateNamespace=true
EOF
```
{% endraw %}

- dev-k8s, prd-k8s 두 개 클러스터에 대해 동일한 Guestbook 앱을 배포합니다.
- managed-by=applicationset 라벨을 추가해, 나중에 ApplicationSet이 생성한 앱만 필터링할 수 있게 했습니다.

### 6.3. ApplicationSet / Application 상태 확인

```shell
##############################################################
# ApplicationSet 리소스 확인
##############################################################
kubectl get applicationsets -n argocd guestbook -o yaml
kubectl get applicationsets -n argocd
# NAME        AGE
# guestbook   63s
##############################################################
# Argo CD CLI로 AppSet 확인
##############################################################
argocd appset list

##############################################################
# Application 목록 및 라벨 확인
##############################################################
argocd app list
argocd app list -l managed-by=applicationset
# NAME                      CLUSTER                         NAMESPACE  PROJECT  STATUS     HEALTH   SYNCPOLICY  CONDITIONS  REPO                                      PATH                 TARGET
# argocd/dev-k8s-guestbook  https://dev-control-plane:6443  guestbook  default  OutOfSync  Missing  Manual      <none>      https://github.com/gasida/cicd-study.git  appset/list/dev-k8s  HEAD
# argocd/prd-k8s-guestbook  https://prd-control-plane:6443  guestbook  default  OutOfSync  Missing  Manual      <none>      https://github.com/gasida/cicd-study.git  appset/list/prd-k8s  HEAD

kubectl get applications -n argocd
kubectl get applications -n argocd --show-labels
# NAME                SYNC STATUS   HEALTH STATUS   LABELS
# dev-k8s-guestbook   OutOfSync     Missing         environment=dev-k8s,managed-by=applicationset
# prd-k8s-guestbook   OutOfSync     Missing         environment=prd-k8s,managed-by=applicationset
```

- `dev-k8s-guestbook`, `prd-k8s-guestbook` 두 개의 Application이 자동으로 생성된 것을 확인할 수 있습니다.

### 6.4. Sync 및 결과 확인

```shell
##############################################################
# ApplicationSet이 관리하는 앱 전체 동기화
##############################################################
argocd app sync -l managed-by=applicationset

##############################################################
# 생성된 Application의 매니페스트 확인
##############################################################
kubectl get applications -n argocd dev-k8s-guestbook -o yaml | k neat | yq
# apiVersion: argoproj.io/v1alpha1
# kind: Application
# metadata:
#   labels:
#     environment: dev-k8s
#     managed-by: applicationset
#   name: dev-k8s-guestbook
#   namespace: argocd
# spec:
#   destination:
#     namespace: guestbook
#     server: https://dev-control-plane:6443
#   project: default
#   source:
#     path: appset/list/dev-k8s
#     repoURL: https://github.com/gasida/cicd-study.git
#     targetRevision: HEAD
#   syncPolicy:
#     syncOptions:
#       - CreateNamespace=true
kubectl get applications -n argocd prd-k8s-guestbook -o yaml | k neat | yq
# apiVersion: argoproj.io/v1alpha1
# kind: Application
# metadata:
#   labels:
#     environment: prd-k8s
#     managed-by: applicationset
#   name: prd-k8s-guestbook
#   namespace: argocd
# spec:
#   destination:
#     namespace: guestbook
#     server: https://prd-control-plane:6443
#   project: default
#   source:
#     path: appset/list/prd-k8s
#     repoURL: https://github.com/gasida/cicd-study.git
#     targetRevision: HEAD
#   syncPolicy:
#     syncOptions:
#       - CreateNamespace=true
```

### 6.5. 각 클러스터 실제로 파드가 배포되었는지 확인

```shell
k8s2 get pod -n guestbook
k8s3 get pod -n guestbook
```

### 6.6. 정리 (삭제)

```shell
argocd appset delete guestbook --yes
```

![ApplicationSet List Generator 실습 결과](/assets/img/ci-cd/ci-cd-study/argo-cd-applicationset-practice-list-generator.webp)

### 6.7. ApplicationSet **Cluster** 제너레이터 실습

이번에는 **Cluster Generator**를 활용해서 Argo CD에 등록된 **모든 클러스터에 일괄 배포**하고 **레이블 셀렉터(Label Selector)**를 이용해 **특정 클러스터(dev)** 대상으로 배포 범위를 좁히는 실습을 진행합니다.

---

#### 6.7.1. Cluster Generator – 모든 클러스터 대상 배포

{% raw %}
```bash
##############################################################
# ApplicationSet 생성 (모든 클러스터 대상)
##############################################################
cat <<EOF | kubectl apply -f -
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: guestbook
  namespace: argocd
spec:
  goTemplate: true
  goTemplateOptions: ["missingkey=error"]
  generators:
    - clusters: {}  # Argo CD에 등록된 모든 클러스터
  template:
    metadata:
      name: '{{ .name }}-guestbook'
      labels:
        managed-by: applicationset
    spec:
      project: "default"
      source:
        repoURL: https://github.com/gasida/cicd-study
        targetRevision: HEAD
        path: guestbook
      destination:
        server: '{{ .server }}'
        namespace: guestbook
      syncPolicy:
        syncOptions:
          - CreateNamespace=true
EOF

##############################################################
# ApplicationSet 리소스 확인
##############################################################
kubectl get applicationsets -n argocd guestbook -o yaml
kubectl get applicationsets -n argocd guestbook -o yaml | k neat | yq
# apiVersion: argoproj.io/v1alpha1
# kind: ApplicationSet
# metadata:
#   name: guestbook
#   namespace: argocd
# spec:
#   goTemplate: true
#   goTemplateOptions:
#     - missingkey=error
#   template:
#     metadata:
#       labels:
#         managed-by: applicationset
#       name: '{{ .name }}-guestbook'
#     spec:
#       destination:
#         namespace: guestbook
#         server: '{{ .server }}'
#       project: default
#       source:
#         path: guestbook
#         repoURL: https://github.com/gasida/cicd-study
#         targetRevision: HEAD
#       syncPolicy:
#         syncOptions:
#           - CreateNamespace=true

##############################################################
# ApplicationSet / Application 목록 확인
##############################################################
kubectl get applicationsets -n argocd
argocd appset list
argocd app list
# argocd app list -l managed-by=applicationset
# NAME                          CLUSTER                         NAMESPACE  PROJECT  STATUS     HEALTH   SYNCPOLICY  CONDITIONS  REPO                                  PATH       TARGET
# argocd/dev-cluster-guestbook  https://dev-control-plane:6443  guestbook  default  OutOfSync  Missing  Manual      <none>      https://github.com/gasida/cicd-study  guestbook  HEAD
# argocd/in-cluster-guestbook   https://kubernetes.default.svc  guestbook  default  OutOfSync  Missing  Manual      <none>      https://github.com/gasida/cicd-study  guestbook  HEAD
# argocd/prd-cluster-guestbook  https://prd-control-plane:6443  guestbook  default  OutOfSync  Missing  Manual      <none>      https://github.com/gasida/cicd-study  guestbook  HEAD
kubectl get applications -n argocd --show-labels

##############################################################
# ApplicationSet이 관리하는 Application 전체 동기화
##############################################################
argocd app sync -l managed-by=applicationset

##############################################################
# 생성된 Application 매니페스트 확인
##############################################################
kubectl get applications -n argocd in-cluster-guestbook -o yaml | k neat | yq
kubectl get applications -n argocd dev-cluster-guestbook -o yaml | k neat | yq
kubectl get applications -n argocd prd-cluster-guestbook -o yaml | k neat | yq

##############################################################
# 각 Kubernetes 클러스터에 배포된 파드 확인
##############################################################
k8s1 get pod -n guestbook
k8s2 get pod -n guestbook
k8s3 get pod -n guestbook
# NAME                            READY   STATUS    RESTARTS   AGE
# guestbook-ui-85db984648-lhh5r   1/1     Running   0          80s
# NAME                            READY   STATUS    RESTARTS   AGE
# guestbook-ui-85db984648-j88pl   1/1     Running   0          82s
# NAME                            READY   STATUS    RESTARTS   AGE
# guestbook-ui-85db984648-hg9z9   1/1     Running   0          80s

# 정리 (삭제)
argocd appset delete guestbook --yes
```
{% endraw %}

![ApplicationSet Cluster Generator 실습 결과](/assets/img/ci-cd/ci-cd-study/argo-cd-applicationset-practice-cluster-generator-all.webp)

#### 6.7.2. Cluster Generator – Label Selector로 특정 클러스터(dev)만 대상

이번에는 **dev 클러스터만 배포**되도록, Argo CD 클러스터 Secret에 레이블을 부여하고, Cluster Generator에서 해당 레이블만 선택하도록 구성합니다.

{% raw %}
```shell
##############################################################
# Argo CD에 등록된 클러스터 Secret 목록 확인
##############################################################
kubectl get secret -n argocd -l argocd.argoproj.io/secret-type=cluster
# NAME                  TYPE     DATA   AGE
# cluster-dev-cluster   Opaque   3      7d10h
# cluster-prd-cluster   Opaque   3      7d10h

##############################################################
# dev-k8s 클러스터 Secret 이름을 변수로 저장 (예시)
##############################################################
DEVK8S=cluster-dev-cluster

##############################################################
# dev 클러스터에만 env=stg 레이블 추가
##############################################################
kubectl label secrets $DEVK8S -n argocd env=stg

##############################################################
# 레이블이 잘 적용되었는지 확인
##############################################################
kubectl get secret -n argocd -l env=stg
# NAME                  TYPE     DATA   AGE
# cluster-dev-cluster   Opaque   3      7d10h

# env=stg 레이블을 가진 클러스터만 대상으로 하는 ApplicationSet 생성
cat <<EOF | kubectl apply -f -
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: guestbook
  namespace: argocd
spec:
  goTemplate: true
  goTemplateOptions: ["missingkey=error"]
  generators:
    - clusters:
        selector:
          matchLabels:
            env: "stg"
  template:
    metadata:
      name: '{{ .name }}-guestbook'
      labels:
        managed-by: applicationset
    spec:
      project: "default"
      source:
        repoURL: https://github.com/gasida/cicd-study
        targetRevision: HEAD
        path: guestbook
      destination:
        server: '{{ .server }}'
        namespace: guestbook
      syncPolicy:
        syncOptions:
          - CreateNamespace=true
        automated:
          prune: true
          selfHeal: true
EOF

# ApplicationSet / Application 상태 확인
kubectl get applicationsets -n argocd
argocd appset list
argocd app list -l managed-by=applicationset
kubectl get applications -n argocd --show-labels
# NAME                    SYNC STATUS   HEALTH STATUS   LABELS
# dev-cluster-guestbook   Synced        Healthy         managed-by=applicationset

# 정리 (삭제)
argocd appset delete guestbook --yes
```
{% endraw %}

![ApplicationSet Cluster Generator with Label Selector 실습 결과](/assets/img/ci-cd/ci-cd-study/argo-cd-applicationset-practice-cluster-generator-label-selector.webp)

---

## 7. 마무리

이번 포스팅에서는 Argo CD의 기본적인 관리 패턴인 App of Apps의 구조와 한계, 그리고 이를 극복하기 위한 ApplicationSet의 개념과 활용법을 알아보았습니다.

실습을 통해 확인했듯이, 초기 단계의 소규모 환경에서는 App of Apps 패턴이 직관적이고 유용합니다. 하지만 관리해야 할 클러스터가 늘어나고 테넌트가 복잡해지는 확장 단계에서는 ApplicationSet의 Generator를 활용한 동적 관리가 필수적임을 알 수 있었습니다.

특히 Cluster Generator와 Label Selector를 적절히 조합하면, 단순히 클러스터에 라벨을 붙이는 작업만으로도 수십, 수백 개의 애플리케이션 배포를 자동화할 수 있어 운영 리소스를 획기적으로 줄일 수 있습니다.

복잡한 멀티 클러스터 환경에서 GitOps를 통한 '진정한 자동화'를 꿈꾸신다면, ApplicationSet 도입을 적극 고려해보시길 바랍니다.

---

## 8. Reference

- [GitHub - kkamji-lab](https://github.com/KKamJi98/kkamji-lab)
- [GitHub - kkamji-lab Apps Directory](https://github.com/KKamJi98/kkamji-lab/tree/main/study/ci-cd-study/6w-3-of-3-argocd/cicd-study/apps)
- [GitHub - kkamji-lab applications.yaml](https://github.com/KKamJi98/kkamji-lab/blob/main/study/ci-cd-study/6w-3-of-3-argocd/cicd-study/apps/templates/applications.yaml)
- [GitHub - kkamji-lab values.yaml](https://github.com/KKamJi98/kkamji-lab/blob/main/study/ci-cd-study/6w-3-of-3-argocd/cicd-study/apps/values.yaml)
- [GitHub - gasida cicd-study](https://github.com/gasida/cicd-study)
- [ArgoCD Docs - Cluster Bootstrapping](https://argo-cd.readthedocs.io/en/stable/operator-manual/cluster-bootstrapping/)
- [ArgoCD Docs - Declarative Setup](https://argo-cd.readthedocs.io/en/stable/operator-manual/declarative-setup/)
- [ArgoCD Docs - ApplicationSet](https://argo-cd.readthedocs.io/en/stable/operator-manual/applicationset/)
- [ArgoCD Docs - ApplicationSet Generators (List)](https://argo-cd.readthedocs.io/en/stable/operator-manual/applicationset/Generators-List/)
- [ArgoCD Docs - ApplicationSet Generators (Cluster)](https://argo-cd.readthedocs.io/en/stable/operator-manual/applicationset/Generators-Cluster/)
- [ArgoCD Docs - How ApplicationSet controller interacts with Argo CD](https://argo-cd.readthedocs.io/en/stable/operator-manual/applicationset/Argo-CD-Integration/)
- [ArgoCD Docs - Generators](https://argo-cd.readthedocs.io/en/stable/operator-manual/applicationset/Generators/)
- [ArgoCD Docs - ApplicationSet Specification](https://argo-cd.readthedocs.io/en/stable/operator-manual/applicationset/applicationset-specification/)
- [GitHub - ApplicationSet Cluster Generator Docs (master)](https://github.com/argoproj/argo-cd/blob/master/docs/operator-manual/applicationset/Generators-Cluster.md)
- [ArgoCD Docs - Overview](https://argo-cd.readthedocs.io/en/stable/)
- [Kubernetes Docs - Controllers](https://kubernetes.io/docs/concepts/architecture/controller/)
- [Kubernetes Docs - Extend the Kubernetes API with CustomResourceDefinitions](https://kubernetes.io/docs/tasks/extend-kubernetes/custom-resources/custom-resource-definitions/)
- [GitHub - Argo CD](https://github.com/argoproj/argo-cd)
- [GitHub - Argo CD Example Apps](https://github.com/argoproj/argocd-example-apps/)
- [GitHub - ApplicationSet Examples](https://github.com/argoproj/argo-cd/tree/master/applicationset/examples)
- [KT Tech Blog - [기술가이드] Kubernetes 환경에서 App of Apps로 구현하는 GitOps 실전 전략](https://tech.ktcloud.com/entry/2025-05-ktcloud-kubernetes-gitops-appofapps-%EA%B5%AC%ED%98%84%ED%99%98%EA%B2%BD-%EC%A0%84%EB%9E%B5)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글로 알려주세요.**  
{: .prompt-info}
