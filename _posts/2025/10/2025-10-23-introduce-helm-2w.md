---
title: Helm 소개
date: 2025-10-25 23:42:31 +0900
author: kkamji
categories: [DevOps]
tags: [devops, ci-cd-study, ci-cd-study-2w, helm]
comments: true
image:
  path: /assets/img/ci-cd/ci-cd-study/ci-cd-study.webp
---

`CloudNet@` Gasida님이 진행하는 `CI/CD + ArgoCD + Vault Study` 를 진행하며 학습한 내용을 공유합니다.

이번 포스트에서는 *O'Reilly GitOps Cookbook* 의 4장에 해당 하는 **Helm**에 대해 알아보겠습니다.

---

## 1. Helm 소개

**Helm**은 Go Template 언어를 사용하여 **Kubernetes Application**을 설치하고 관리하는 과정을 더 편리하게 돕는 솔루션입니다. **Helm**은 **Kustomize**와 유사하지만 **Chart**라는 개념이 존재합니다. **Chart**는 패키지 매니저처럼 동작하며 여러 개의 Kubernetes Manifest를 패키지 형태로 묶고, 다른 차트에 대한 의존성, 버전 관리, 배포 가능한 **Artifact**와 같은 요소를 포함합니다.

---

## 2. Helm Project의 구조와 구성 요소

Helm Project는 아래와 같은 구성 요소와 구조를 갖습니다.

![What is a Helm Chart?](/assets/img/ci-cd/ci-cd-study/what-is-a-helm-chart.webp)
> SimplyBlock - What is a Helm Chart? - <https://www.simplyblock.io/glossary/what-is-a-helm-chart>

### 2.1. Helm Project의 구조

{% raw %}

```shell
##############################################################
# Helm Chart생성
##############################################################
helm create myapp                            
# Creating myapp

##############################################################
# Helm Chart 구조 확인
##############################################################
tree myapp 
# myapp
# ├── Chart.yaml
# ├── charts
# ├── templates
# │   ├── NOTES.txt
# │   ├── _helpers.tpl
# │   ├── deployment.yaml
# │   ├── hpa.yaml
# │   ├── ingress.yaml
# │   ├── service.yaml
# │   ├── serviceaccount.yaml
# │   └── tests
# │       └── test-connection.yaml
# └── values.yaml

# 4 directories, 10 files
```

{% endraw %}

### 2.2. Helm Project의 구성 요소

| 항목             | 설명                                                                                    |
| ---------------- | --------------------------------------------------------------------------------------- |
| **Chart.yaml**   | Chart의 이름, 버전, 의존성 등 메타데이터가 정의된 파일                                  |
| **values.yaml**  | 템플릿에서 참조하는 기본 값이 정의되어 있으며, `-f` 옵션으로 오버라이드 가능            |
| **charts/**      | 의존성으로 포함된 서브 차트가 위치                                                      |
| **templates/**   | Kubernetes Manifest 템플릿이 위치하며, Go Template(&#123;&#123; &#125;&#125;) 문법 사용 |
| **_helpers.tpl** | 공통 함수와 템플릿 헬퍼가 정의된 파일                                                   |
| **NOTES.txt**    | 설치 완료 후 출력되는 안내 메시지가 정의                                                |
| **tests/**       | Chart 테스트 리소스가 포함되어 있으며, `helm test`로 검증에 사용                        |

---

## 3. Creating a Helm Project

### 3.1. Helm Chart 생성

{% raw %}

```shell
##############################################################
# 실습을 위한 Kind Kubernetes Cluster 배포
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
EOF


##############################################################
# 헬름 차트 디렉터리 레이아웃 생성
##############################################################
mkdir pacman
mkdir pacman/templates
cd pacman

##############################################################
# 루트 디렉터리에 차트 정의 파일 작성 : 버전, 이름 등 정보
##############################################################
cat << EOF > Chart.yaml
apiVersion: v2
name: pacman
description: A Helm chart for Pacman
type: application
version: 0.1.0        # 차트 버전, 차트 정의가 바뀌면 업데이트한다
appVersion: "1.0.0"   # 애플리케이션 버전
EOF

##############################################################
# Helm Chart 구성 요소 생성
##############################################################
# templates 디렉터리에 Go 템플릿 언어와 Sprig 라이브러리의 템플릿 함수를 사용해 정의한 배포 템플릿 파일 작성 : 애플리케이션 배포
## deployment.yaml 파일에서 템플릿화 : dp 이름, app 버전, replicas 수, 이미지/태그, 이미지 풀 정책, 보안 컨텍스트, 포트 
cat << EOF > templates/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ .Chart.Name}}            # Chart.yaml 파일에 설정된 이름을 가져와 설정
  labels:
    app.kubernetes.io/name: {{ .Chart.Name}}
    {{- if .Chart.AppVersion }}     # Chart.yaml 파일에 appVersion 여부에 따라 버전을 설정
    app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}     # appVersion 값을 가져와 지정하고 따옴표 처리
    {{- end }}
spec:
  replicas: {{ .Values.replicaCount }}     # replicaCount 속성을 넣을 자리 placeholder
  selector:
    matchLabels:
      app.kubernetes.io/name: {{ .Chart.Name}}
  template:
    metadata:
      labels:
        app.kubernetes.io/name: {{ .Chart.Name}}
    spec:
      containers:
        - image: "{{ .Values.image.repository }}:{{ .Values.image.tag | default .Chart.AppVersion}}"   # 이미지 지정 placeholder, 이미지 태그가 있으면 넣고, 없으면 Chart.yaml에 값을 설정
          imagePullPolicy: {{ .Values.image.pullPolicy }}
          securityContext:
            {{- toYaml .Values.securityContext | nindent 14 }} # securityContext의 값을 YAML 객체로 지정하며 14칸 들여쓰기
          name: {{ .Chart.Name}}
          ports:
            - containerPort: {{ .Values.image.containerPort }}
              name: http
              protocol: TCP
EOF

## service.yaml 파일에서 템플릿화 : service 이름, 컨테이너 포트
cat << EOF > templates/service.yaml
apiVersion: v1
kind: Service
metadata:
  labels:
    app.kubernetes.io/name: {{ .Chart.Name }}
  name: {{ .Chart.Name }}
spec:
  ports:
    - name: http
      port: {{ .Values.image.containerPort }}
      targetPort: {{ .Values.image.containerPort }}
  selector:
    app.kubernetes.io/name: {{ .Chart.Name }}
EOF

# 차트 기본값(default values)이 담긴 파일 작성 : 애플리케이션 배포 시점에 다른 값으로 대체될 수 있는 기본 설정을 담아두는 곳
cat << EOF > values.yaml
image:     # image 절 정의
  repository: quay.io/gitops-cookbook/pacman-kikd
  tag: "1.0.0"
  pullPolicy: Always
  containerPort: 8080

replicaCount: 1
securityContext: {}     # securityContext 속성의 값을 비운다
EOF

# 디렉터리 레이아웃 확인
tree
├── Chart.yaml    # 차트를 설명하며, 차트 관련 메타데이터를 포함
├── templates     # 차트 설치에 사용되는 모든 템플릿 파일
│   ├── deployment.yaml  # 애플리케이션 배포에 사용되는 헬름 템플릿 파일들
│   └── service.yaml
└── values.yaml   # 차트 기본값

# (참고) securityContext의 값을 채우기 위해 toYaml 함수를 사용하였으므로 values.yaml 의 보안 컨텍스트 속성값은 YAML 객체여야 한다.
# 예를 들면 다음과 같다.
securityContext:
  capabilities:
    drop:
    - ALL
  readOnlyRootFilesystem: true
  runAsNonRoot: true
  runAsUser: 1000
```

{% endraw %}

### 3.2. Helm Chart Rendering (Template)

```shell
#
helm template .
---
# Source: pacman/templates/service.yaml
apiVersion: v1
kind: Service
metadata:
  labels:
    app.kubernetes.io/name: pacman
  name: pacman           # Chart.yaml 파일에 설정된 이름을 가져와 설정
spec:
  ports:
    - name: http
      port: 8080         # values.yaml 파일에서 가져옴
      targetPort: 8080
  selector:
    app.kubernetes.io/name: pacman
---
# Source: pacman/templates/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: pacman            # Chart.yaml 파일에 설정된 이름을 가져와 설정
  labels:
    app.kubernetes.io/name: pacman
    app.kubernetes.io/version: "1.0.0"     # Chart.yaml appVersion 값을 가져와 지정하고 따옴표 처리
spec:
  replicas: 1     # replicaCount 속성을 넣을 자리 placeholder
  selector:
    matchLabels:
      app.kubernetes.io/name: pacman
  template:
    metadata:
      labels:
        app.kubernetes.io/name: pacman
    spec:
      containers:
        - image: "quay.io/gitops-cookbook/pacman-kikd:1.0.0"  # 두 속성의 내용이 하나로 연결
          imagePullPolicy: Always
          securityContext: # 보안 컨텍스트는 빈 값
              {} # securityContext의 값을 YAML 객체로 지정하며 14칸 들여쓰기
          name: pacman
          ports:
            - containerPort: 8080
              name: http
              protocol: TCP

# --set 파라미터를 사용하여 기본값을 재정의
helm template --set replicaCount=3 .
...
spec:
  replicas: 3     # replicaCount 속성을 넣을 자리 placeholder
... 
```

### 3.3. Helm Chart 배포 및 확인

```shell
##############################################################
# Helm Chart 배포
##############################################################
helm install pacman .
# NAME: pacman
# LAST DEPLOYED: Sun Oct 26 02:39:32 2025
# NAMESPACE: default
# STATUS: deployed
# REVISION: 1
# TEST SUITE: None

##############################################################
# 배포된 Helm Chart 및 리소스 확인
##############################################################
helm list
# NAME    NAMESPACE       REVISION        UPDATED                                 STATUS          CHART           APP VERSION
# pacman  default         1               2025-10-26 02:39:32.102294317 +0900 KST deployed        pacman-0.1.0    1.0.0      

kubectl get deploy,pod,svc,ep
kubectl get pod -o yaml | kubectl neat | yq  # kubectl krew install neat 
kubectl get pod -o json | grep securityContext -A1

##############################################################
# Helm Release의 배포 이력 확인 (History)
##############################################################
helm history pacman
# REVISION        UPDATED                         STATUS          CHART           APP VERSION     DESCRIPTION     
# 1               Sun Oct 26 02:39:32 2025        deployed        pacman-0.1.0    1.0.0           Install complete

##############################################################
# Helm Secret 확인
##############################################################
# Helm 자체가 배포 릴리스 메타데이터를 저장하기 위해 자동으로 Secret 리소스 생성 : Helm이 차트의 상태를 복구하거나 rollback 할 때 이 데이터를 이용
kubectl get secret
# NAME                           TYPE                 DATA   AGE
# sh.helm.release.v1.pacman.v1   helm.sh/release.v1   1      5m17s
```

### 3.4. Helm Chart Upgrade, Metadata 확인

```shell
##############################################################
# 특정 Value 값에 대한 설정 값을 오버라이드 하며 Helm Chart Upgrade
##############################################################
helm upgrade pacman --reuse-values --set replicaCount=2 .


##############################################################
# 배포 리소스 및 Secret 정보 확인
##############################################################

kubectl get pod
# NAME                      READY   STATUS              RESTARTS   AGE
# pacman-576769bb86-bkgfc   0/1     ContainerCreating   0          0s
# pacman-576769bb86-lfzkf   1/1     Running             0          5m26s

kubectl get secret
# NAME                           TYPE                 DATA   AGE
# sh.helm.release.v1.pacman.v1   helm.sh/release.v1   1      11m
# sh.helm.release.v1.pacman.v2   helm.sh/release.v1   1      20s

# helm 배포 정보 확인
helm get all pacman      # 모든 정보
helm get values pacman   # values 적용 정보
helm get manifest pacman # 실제 적용된 manifest
helm get notes pacman    # chart notes

# 삭제 후 secret 확인
helm uninstall pacman
kubectl get secret
# No resources found in default namespace.
```

---

## 4. Reusing Statements Between Templates

`_helpers.tpl`에 재사용 가능한 Code Block을 정의함으로써, 여러 파일에서 같은 `Template Code`를 재사용할 수 있습니다.

{% raw %}

```shell
##############################################################
# deployment.yaml, service.yaml 에 selector 필드가 동일
##############################################################
## deployment.yaml
spec:
  replicas: {{ .Values.replicaCount }}
  selector:
    matchLabels:
      app.kubernetes.io/name: {{ .Chart.Name}}
  template:
    metadata:
      labels:
        app.kubernetes.io/name: {{ .Chart.Name}}

## service.yaml
  selector:
    app.kubernetes.io/name: {{ .Chart.Name }}

## 위와 같이 중복되는 selector 필드를 업데이트하려면(selector 필드에 새 레이블 추가 등) 3곳을 똑같이 업데이트 해야함

##############################################################
# _helpers.tpl 파일을 사용해 기존 코드를 리펙터링
##############################################################
## _helpers.tpl 파일 작성
cat << EOF > templates/_helpers.tpl
{{- define "pacman.selectorLabels" -}}   # statement 이름을 정의
app.kubernetes.io/name: {{ .Chart.Name}} # 해당 statement 가 하는 일을 정의
{{- end }}
EOF

## deployment.yaml 수정
spec:
  replicas: {{ .Values.replicaCount }}
  selector:
    matchLabels:
      {{- include "pacman.selectorLabels" . | nindent 6 }}   # pacman.selectorLabels를 호출한 결과를 6만큼 들여쓰기하여 주입
  template:
    metadata:
      labels:
        {{- include "pacman.selectorLabels" . | nindent 8 }} # pacman.selectorLabels를 호출한 결과를 8만큼 들여쓰기하여 주입
        
## service.yaml 수정
  selector:
    {{- include "pacman.selectorLabels" . | nindent 6 }}


# 변경된 차트를 로컬에서 YAML 렌더링 : _helpers.tpl 설정된 값으로 갱신 확인
helm template .

# _helpers.tpl 파일 수정 : 새 속성 추가
cat << EOF > templates/_helpers.tpl
{{- define "pacman.selectorLabels" -}}
app.kubernetes.io/name: {{ .Chart.Name}}
app.kubernetes.io/version: {{ .Chart.AppVersion}}
{{- end }}
EOF

# 변경된 차트를 로컬에서 YAML 렌더링 : _helpers.tpl 설정된 값으로 갱신 확인
helm template .
```

{% endraw %}

> Template 함수를 정의하는 파일명으로는 `_helpers.tpl`을 사용하는 것이 일반적이지만, 실제로는 `_`로 시작하기만 하면 됩니다. 이와 같은 파일들은 Kubernetes Manifest 파일로 취급되지 않습니다.  
{: .prompt-tip}

---

## 5. Updating a Container Image in Helm

`helm upgrade` 명령을 사용해 배포 파일에서 컨테이너 이미지를 갱신하고 실행 중인 인스턴스를 업그레이드 할 수 있고, `helm rollback` 명령어를 통해 이전 버전으로 롤백할 수 있습니다.

{% raw %}

```shell
##############################################################
# _helpers.tpl 파일 초기 설정으로 수정
##############################################################
cat << EOF > templates/_helpers.tpl
{{- define "pacman.selectorLabels" -}}
app.kubernetes.io/name: {{ .Chart.Name}}
{{- end }}
EOF

# helm 배포
helm install pacman .

# 확인 : 리비전 번호, 이미지 정보 확인
helm history pacman
# REVISION        UPDATED                         STATUS          CHART           APP VERSION     DESCRIPTION     
# 1               Sun Oct 26 13:16:31 2025        deployed        pacman-0.1.0    1.0.0           Install complete
kubectl get deploy -owide
# NAME     READY   UP-TO-DATE   AVAILABLE   AGE   CONTAINERS   IMAGES                                      SELECTOR
# pacman   1/1     1            1           11s   pacman       quay.io/gitops-cookbook/pacman-kikd:1.0.0   app.kubernetes.io/name=pacman

##############################################################
# 1.0.0 -> 1.1.0 으로 업그레이드
##############################################################
# Chart.yaml 파일에 appVersion 필드 갱신
cat << EOF > Chart.yaml
apiVersion: v2
name: pacman
description: A Helm chart for Pacman
type: application
version: 0.1.0
appVersion: "1.1.0"
EOF

# values.yaml 에 이미지 태그 업데이트
cat << EOF > values.yaml
image:
  repository: quay.io/gitops-cookbook/pacman-kikd
  tag: "1.1.0"
  pullPolicy: Always
  containerPort: 8080

replicaCount: 1
securityContext: {}
EOF

# 배포 업그레이드
helm upgrade pacman .
# Release "pacman" has been upgraded. Happy Helming!
# NAME: pacman
# LAST DEPLOYED: Sun Oct 26 13:19:01 2025
# NAMESPACE: default
# STATUS: deployed
# REVISION: 2  # 새 Revision 번호
# TEST SUITE: None

# 확인
helm history pacman
# REVISION        UPDATED                         STATUS          CHART           APP VERSION     DESCRIPTION     
# 1               Sun Oct 26 13:16:31 2025        superseded      pacman-0.1.0    1.0.0           Install complete
# 2               Sun Oct 26 13:19:01 2025        deployed        pacman-0.1.0    1.1.0           Upgrade complete
kubectl get secret
# NAME                           TYPE                 DATA   AGE
# sh.helm.release.v1.pacman.v1   helm.sh/release.v1   1      2m56s
# sh.helm.release.v1.pacman.v2   helm.sh/release.v1   1      26s
kubectl get deploy,replicaset -owide

##############################################################
# 이전 버전으로 롤백
##############################################################
# history 확인
helm history pacman
# REVISION        UPDATED                         STATUS          CHART           APP VERSION     DESCRIPTION     
# 1               Sun Oct 26 13:16:31 2025        superseded      pacman-0.1.0    1.0.0           Install complete
# 2               Sun Oct 26 13:19:01 2025        deployed        pacman-0.1.0    1.1.0           Upgrade complete

# 현재 (2) -> 이전 (1) 롤백
helm rollback pacman 1 && kubectl get pod -w

# 확인
helm history pacman
# REVISION        UPDATED                         STATUS          CHART           APP VERSION     DESCRIPTION     
# 1               Sun Oct 26 13:16:31 2025        superseded      pacman-0.1.0    1.0.0           Install complete
# 2               Sun Oct 26 13:19:01 2025        superseded      pacman-0.1.0    1.1.0           Upgrade complete
# 3               Sun Oct 26 13:21:52 2025        deployed        pacman-0.1.0    1.0.0           Rollback to 1   
kubectl get secret
# NAME                           TYPE                 DATA   AGE
# sh.helm.release.v1.pacman.v1   helm.sh/release.v1   1      6m24s
# sh.helm.release.v1.pacman.v2   helm.sh/release.v1   1      3m54s
# sh.helm.release.v1.pacman.v3   helm.sh/release.v1   1      63s

kubectl get deploy,replicaset -owide

##############################################################
# 리소스 정리
##############################################################
helm uninstall pacman
```

{% endraw %}

---

## 6. Packaging and Distributing a Helm Chart

`helm package` 명령을 사용해 Helm Chart를 패키징하고 공개하여 다른 차트의 의존성으로 이용될 수 있도록 하거나, 다른 사용자가 시스템에 배포할 수 있도록 할 수 있습니다.

helm package로 패키징한 차트는 차트 저장소(Repository) 에 게시할 수 있습니다. 차트 저장소는 `Package`(`.tgz` 파일) 와 해당 차트들의 메타데이터 정보를 담은 `index.html` 파일을 포함한 HTTP 서버 형태로 구성됩니다.

새로운 차트를 저장소에 게시할 때는, `index.yaml` 파일에 새 메타데이터 정보를 갱신한 뒤 패키지 아티팩트를 함께 업로드해야 합니다.

```shell
##############################################################
# 현재 
##############################################################
tree
.
├── Chart.yaml
├── templates
│   ├── _helpers.tpl
│   ├── deployment.yaml
│   └── service.yaml
└── values.yaml

2 directories, 5 files

##############################################################
# Helm Chart Packaging
##############################################################
helm package .
# Successfully packaged chart and saved it to: /home/kkamji/Code/kkamji-lab/study/ci-cd-study/2w/pacman/pacman-0.1.0.tgz

# 확인
ls
# drwxr-xr-x    - kkamji 26 Oct 02:55 -N  templates
# .rw-r--r--  118 kkamji 26 Oct 13:18 -N  Chart.yaml
# .rw-r--r-- 1.2k kkamji 26 Oct 13:29 -N  pacman-0.1.0.tgz
# .rw-r--r--  152 kkamji 26 Oct 13:18 -N  values.yaml

# index.html 파일 생성
helm repo index .
cat index.yaml
# apiVersion: v1
# entries:
#   pacman:
#   - apiVersion: v2
#     appVersion: 1.1.0
#     created: "2025-10-18T18:33:41.240749+09:00"
#     description: A Helm chart for Pacman
#     digest: 1a68e0069016d96ab64344e2d4c2fde2b7368e410f93da90bf19f6ed8ca9495a
#     name: pacman
#     type: application
#     urls:
#     - pacman-0.1.0.tgz
#     version: 0.1.0
# generated: "2025-10-18T18:33:41.239645+09:00"
```

---

## 7. Deploying a Chart From a Repository

`helm repo add` 명령을 사용하여 원격 저장소를 추가하고, `helm install` 명령을 사용해 해당 저장소에 저장되어있는 Helm Chart를 배포할 수 있습니다.

```shell
##############################################################
# bitnami/postgresql 배포 실습
##############################################################
# helm repository add
helm repo add bitnami https://charts.bitnami.com/bitnami

# 현재 추가된 helm repository 확인
helm repo list

# postgresql chart 찾기 및 확인
helm search repo postgresql
helm search repo postgresql -o json | jq

# 배포
helm install my-db bitnami/postgresql \
  --set postgresql.postgresqlUsername=my-default \
  --set postgresql.postgresqlPassword=postgres \
  --set postgresql.postgresqlDatabase=mydb \
  --set postgresql.persistence.enabled=false

# 확인
helm list
# NAME    NAMESPACE       REVISION        UPDATED                                 STATUS          CHART                   APP VERSION
# my-db   default         1               2025-10-26 14:41:54.131687554 +0900 KST deployed        postgresql-18.0.8       18.0.0     

# 배포 리소스 확인
kubectl get sts,pod,svc,ep,secret

# 서드 파티 차트 사용 시, 기본값(default value)나 override 파라미터를 직접 확인 할 수 없고, helm show 로 확인 가능
helm show values bitnami/postgresql

# 실습 후 삭제
helm uninstall my-db
```

---

## 8. Deploying a Chart with Dependency

`Chart.yaml` 파일의 `dependencies` 섹션에 다른 차트에 대한 의존성을 추가할 수 있습니다. 위에서 차트를 통해 배포한 서비스들은 간단했지만, 일반적으로 서비스는 데이터베이스, 메일 서버, 분산 캐시 등에 의존하는 경우가 많습니다.

아래 실습에서 PostgreSQL 데이터베이스에 저장된 노래 목록을 반환하는 Java 서비스를 배포해 보겠습니다.

![Music application overview](/assets/img/ci-cd/ci-cd-study/music-application-overview.webp)

> [O’Reilly GitOps Cookbook: Kubernetes Automation in Practice](https://product.kyobobook.co.kr/detail/S000214781090)  
> Music application overview - 5.6. Deploying a Chart with Dependency p.111  

{% raw %}

```shell
##############################################################
# 의존성을 가진 Helm Chart 생성
##############################################################
mkdir music
mkdir music/templates
cd music

# deployment.yaml
cat << EOF > templates/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ .Chart.Name}}
  labels:
    app.kubernetes.io/name: {{ .Chart.Name}}
    {{- if .Chart.AppVersion }}
    app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
    {{- end }}
spec:
  replicas: {{ .Values.replicaCount }}
  selector:
    matchLabels:
      app.kubernetes.io/name: {{ .Chart.Name}}
  template:
    metadata:
      labels:
        app.kubernetes.io/name: {{ .Chart.Name}}
    spec:
      containers:
        - image: "{{ .Values.image.repository }}:{{ .Values.image.tag | default .Chart.AppVersion}}"
          imagePullPolicy: {{ .Values.image.pullPolicy }}
          name: {{ .Chart.Name}}
          ports:
            - containerPort: {{ .Values.image.containerPort }}
              name: http
              protocol: TCP
          env:
            - name: QUARKUS_DATASOURCE_JDBC_URL
              value: {{ .Values.postgresql.server | default (printf "%s-postgresql" ( .Release.Name )) | quote }}
            - name: QUARKUS_DATASOURCE_USERNAME
              value: {{ .Values.postgresql.postgresqlUsername | default (printf "postgres" ) | quote }}
            - name: QUARKUS_DATASOURCE_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: {{ .Values.postgresql.secretName | default (printf "%s-postgresql" ( .Release.Name )) | quote }}
                  key: {{ .Values.postgresql.secretKey }}
EOF

##############################################################
# service.yaml 생성
##############################################################
cat << EOF > templates/service.yaml
apiVersion: v1
kind: Service
metadata:
  labels:
    app.kubernetes.io/name: {{ .Chart.Name }}
  name: {{ .Chart.Name }}
spec:
  ports:
    - name: http
      port: {{ .Values.image.containerPort }}
      targetPort: {{ .Values.image.containerPort }}
  selector:
    app.kubernetes.io/name: {{ .Chart.Name }}
EOF

##############################################################
# Chart.yaml 생성 (책에 존재하는 14.2.3 버전의 postgresql dependencies 사용)
##############################################################
cat << EOF > Chart.yaml
apiVersion: v2
name: music
description: A Helm chart for Music service
type: application
version: 0.1.0
appVersion: "1.0.0"
dependencies:
  - name: postgresql
    version: 14.2.3
    repository: "https://charts.bitnami.com/bitnami"
EOF

##############################################################
# 책에 존재하는 해당 차트 버전이 존재하는지 확인
##############################################################
helm search repo postgresql
# NAME                                                    CHART VERSION   APP VERSION     DESCRIPTION                                       
# bitnami/postgresql                                      18.0.8          18.0.0          PostgreSQL (Postgres) is an open source object-...
# bitnami/postgresql-ha                                   16.3.2          17.6.0          This PostgreSQL cluster solution includes the P...
# ...

helm search repo bitnami/postgresql --versions
# NAME                    CHART VERSION   APP VERSION     DESCRIPTION                                       
# bitnami/postgresql      18.0.8          18.0.0          PostgreSQL (Postgres) is an open source object-...
# bitnami/postgresql      18.0.7          18.0.0          PostgreSQL (Postgres) is an open source object-...
# ...
# bitnami/postgresql      14.2.3          16.2.0          PostgreSQL (Postgres) is an open source object-...

##############################################################
# value.yaml 파일 생성
##############################################################
cat << EOF > values.yaml
image:
  repository: quay.io/gitops-cookbook/music
  tag: "1.0.0"
  pullPolicy: Always
  containerPort: 8080

replicaCount: 1

postgresql:
  server: jdbc:postgresql://music-db-postgresql:5432/mydb
  postgresqlUsername: my-default
  postgresqlPassword: postgres
  postgresqlDatabase: mydb  
  secretName: music-db-postgresql
  secretKey: postgresql-password
EOF

##############################################################
# 프로젝트 구조 확인 (결과)
##############################################################
tree  
.
├── Chart.yaml
├── templates
│   ├── deployment.yaml
│   └── service.yaml
└── values.yaml

##############################################################
# 의존성으로 선언된 차트를 현재 차트에 다운로드 후 확인
##############################################################
# 의존성 업데이트
helm dependency update
# Hang tight while we grab the latest from your chart repositories...
# ...Successfully got an update from the "aws-observability" chart repository
# ...
# ...Successfully got an update from the "bitnami" chart repository
# Update Complete. ⎈Happy Helming!⎈
# Saving 1 charts
# Downloading postgresql from repo https://charts.bitnami.com/bitnami
# Deleting outdated charts

# 재확인
tree
.
├── Chart.lock
├── Chart.yaml
├── charts
│   └── postgresql-14.2.3.tgz
├── templates
│   ├── deployment.yaml
│   └── service.yaml
└── values.yaml


##############################################################
# Helm Chart 배포
##############################################################
helm install music-db .
# NAME: music-db
# LAST DEPLOYED: Sun Oct 26 14:58:53 2025
# NAMESPACE: default
# STATUS: deployed
# REVISION: 1
# TEST SUITE: None

##############################################################
# 배포 확인 (Trouble Shooting 필요)
##############################################################
kubectl get sts,pod,svc,ep,secret,pv,pvc
# NAME                                   READY   AGE
# statefulset.apps/music-db-postgresql   0/1     85s
# statefulset.apps/my-db-postgresql      1/1     18m

# NAME                         READY   STATUS                       RESTARTS   AGE
# pod/music-6c45d566f4-9qdlr   0/1     CreateContainerConfigError   0          85s
# pod/music-db-postgresql-0    0/1     ImagePullBackOff             0          85s
# ...
```

{% endraw %}

### 8.1. Trouble Shooting 1 (music-db-postgresql-0 - ImagePullBackOff)

```shell
##############################################################
# 문제 확인 (music-db-postgresql-0)
##############################################################
## Bitnami 유료화에 따른 docker.io/bitnami 공개 카탈로그 삭제로 인해 이미지 pull 실패
## GeekNews - docker.io/Bitnami 삭제
# https://news.hada.io/topic?id=22803
## Broadcom Introduces Bitnami Secure Images For Production-Ready Containerized Applications 
# - https://news.broadcom.com/app-dev/broadcom-introduces-bitnami-secure-images-for-production-ready-containerized-applications
kubectl describe po music-db-postgresql-0
# ...
# Events:
#   Type     Reason     Age                   From               Message
#   ----     ------     ----                  ----               -------
#   Normal   Scheduled  4m49s                 default-scheduler  Successfully assigned default/music-db-postgresql-0 to myk8s-control-plane
#   Normal   Pulling    104s (x5 over 4m49s)  kubelet            Pulling image "docker.io/bitnami/postgresql:16.2.0-debian-12-r5"
#   Warning  Failed     102s (x5 over 4m42s)  kubelet            Failed to pull image "docker.io/bitnami/postgresql:16.2.0-debian-12-r5": rpc error: code = NotFound desc = failed to pull and unpack image "docker.io/bitnami/postgresql:16.2.0-debian-12-r5": failed to resolve reference "docker.io/bitnami/postgresql:16.2.0-debian-12-r5": docker.io/bitnami/postgresql:16.2.0-debian-12-r5: not found
#   Warning  Failed     102s (x5 over 4m42s)  kubelet            Error: ErrImagePull
#   Warning  Failed     44s (x15 over 4m42s)  kubelet            Error: ImagePullBackOff
#   Normal   BackOff    7s (x18 over 4m42s)   kubelet            Back-off pulling image "docker.io/bitnami/postgresql:16.2.0-debian-12-r5"

##############################################################
# 임시 해결책으로 PostgreSQL 최신 차트 사용
##############################################################
# bitnami/postgresql 최신 차트 버전 확인 확인 (18.1.1)
helm search repo bitnami/postgresql
# NAME                    CHART VERSION   APP VERSION     DESCRIPTION                                       
# bitnami/postgresql      18.1.1          18.0.0          PostgreSQL (Postgres) is an open source object-...

# Dependency 업데이트
cat << EOF > Chart.yaml
apiVersion: v2
name: music
description: A Helm chart for Music service
type: application
version: 0.1.0
appVersion: "1.0.0"
dependencies:
  - name: postgresql
    version: 18.1.1 # 수정
    repository: "https://charts.bitnami.com/bitnami"
EOF

##############################################################
# 최신 버전의 postgresql 차트로 재배포
##############################################################
# 의존성 업데이트 및 확인
helm dependency update

tree
# .
# ├── Chart.lock
# ├── Chart.yaml
# ├── charts
# │   └── postgresql-18.1.1.tgz
# ├── templates
# │   ├── deployment.yaml
# │   └── service.yaml
# └── values.yaml

# 기존 차트 삭제 (upgrade)
helm uninstall music-db

# 재배포
helm install music-db .

NAME: music-db
LAST DEPLOYED: Sun Oct 26 15:27:27 2025
NAMESPACE: default
STATUS: deployed
REVISION: 1
TEST SUITE: None

##############################################################
# 배포 확인 (postgresql Running, Log 정상)
##############################################################
kubectl get sts,pod,svc,ep,secret,pv,pvc
# NAME                                   READY   AGE
# statefulset.apps/music-db-postgresql   1/1     25s

# NAME                         READY   STATUS                       RESTARTS   AGE
# pod/music-6c45d566f4-9qdlr   0/1     CreateContainerConfigError   0          25s
# pod/music-db-postgresql-0    1/1     Running                      0          25s
# ...

kubectl logs music-db-postgresql-0
```

### 8.2. Trouble Shooting 2 (music-6c45d566f4-9qdlr)

```shell
##############################################################
# 문제 확인 (music-6c45d566f4-9qdlr) 
##############################################################
# values.yaml 에서 secretName과 secretKey를 지정했으나 시크릿 키 값이 맞지 않음
kubectl describe po music-6c45d566f4-9qdlr
# ...
# Events:
#   Type     Reason     Age                   From               Message
#   ----     ------     ----                  ----               -------
#   Normal   Scheduled  3m35s                 default-scheduler  Successfully assigned default/music-6c45d566f4-9qdlr to myk8s-control-plane
#   Normal   Pulled     3m26s                 kubelet            Successfully pulled image "quay.io/gitops-cookbook/music:1.0.0" in 8.791s (8.791s including waiting). Image size: 94836428 bytes.
#   Normal   Pulled     3m23s                 kubelet            Successfully pulled image "quay.io/gitops-cookbook/music:1.0.0" in 684ms (1.242s including waiting). Image size: 94836428 bytes.
#   Normal   Pulled     3m7s                  kubelet            Successfully pulled image "quay.io/gitops-cookbook/music:1.0.0" in 750ms (1.156s including waiting). Image size: 94836428 bytes.
#   Normal   Pulled     2m51s                 kubelet            Successfully pulled image "quay.io/gitops-cookbook/music:1.0.0" in 730ms (730ms including waiting). Image size: 94836428 bytes.
#   Normal   Pulled     2m36s                 kubelet            Successfully pulled image "quay.io/gitops-cookbook/music:1.0.0" in 752ms (752ms including waiting). Image size: 94836428 bytes.
#   Normal   Pulled     2m20s                 kubelet            Successfully pulled image "quay.io/gitops-cookbook/music:1.0.0" in 668ms (668ms including waiting). Image size: 94836428 bytes.
#   Normal   Pulled     2m7s                  kubelet            Successfully pulled image "quay.io/gitops-cookbook/music:1.0.0" in 685ms (685ms including waiting). Image size: 94836428 bytes.
#   Normal   Pulled     115s                  kubelet            Successfully pulled image "quay.io/gitops-cookbook/music:1.0.0" in 1.048s (1.048s including waiting). Image size: 94836428 bytes.
#   Normal   Pulled     101s                  kubelet            Successfully pulled image "quay.io/gitops-cookbook/music:1.0.0" in 769ms (769ms including waiting). Image size: 94836428 bytes.
#   Normal   Pulled     56s (x3 over 85s)     kubelet            (combined from similar events): Successfully pulled image "quay.io/gitops-cookbook/music:1.0.0" in 715ms (715ms including waiting). Image size: 94836428 bytes.
#   Normal   Pulling    45s (x13 over 3m34s)  kubelet            Pulling image "quay.io/gitops-cookbook/music:1.0.0"
#   Warning  Failed     16s (x15 over 3m26s)  kubelet            Error: couldn't find key postgresql-password in Secret default/music-db-postgresql

##############################################################
# 시크릿 확인 (key 값이 postgres-password임 => 불일치 발생)
##############################################################
kubectl get secret music-db-postgresql -o yaml
kubectl get secret music-db-postgresql -o yaml | yq '.data | ...|path|join(".")'
# data
# data.postgres-password
# data.postgres-password

##############################################################
# 시크릿 수정 
##############################################################
kubectl edit secret music-db-postgresql
# data.postgres-password -> data.postgresql-password로 수정

##############################################################
# 시크릿 재 확인
##############################################################
kubectl get secret music-db-postgresql -o yaml
kubectl get secret music-db-postgresql -o yaml | yq '.data | ...|path|join(".")'
# data
# data.postgresql-password
# data.postgresql-password

##############################################################
# 배포 확인 (CreateContainerConfigError -> CrashLoopBackOff)
##############################################################
kubectl get sts,pod,svc,ep,secret,pv,pvc
# NAME                                   READY   AGE
# statefulset.apps/music-db-postgresql   1/1     16m

# NAME                         READY   STATUS             RESTARTS        AGE
# pod/music-6c45d566f4-9qdlr   0/1     CrashLoopBackOff   6 (4m37s ago)   16m
# pod/music-db-postgresql-0    1/1     Running            0               16m

##############################################################
# 바뀐 문제 확인 (로그 및 이벤트 확인)
##############################################################
kubectl describe po music-6c45d566f4-9qdlr
# Events:
#   Type     Reason     Age                   From               Message
#   ----     ------     ----                  ----               -------
# ...
#   Normal   Pulled     15m (x2 over 15m)     kubelet            (combined from similar events): Successfully pulled image "quay.io/gitops-cookbook/music:1.0.0" in 725ms (725ms including waiting). Image size: 94836428 bytes.
#   Warning  Failed     11m (x26 over 17m)    kubelet            Error: couldn't find key postgresql-password in Secret default/music-db-postgresql
#   Warning  BackOff    2m28s (x41 over 11m)  kubelet            Back-off restarting failed container music in pod music-6c45d566f4-9qdlr_default(8a0a07b0-a93a-45ea-8ba0-64c37a020411)
#   Normal   Pulling    32s (x34 over 17m)    kubelet            Pulling image "quay.io/gitops-cookbook/music:1.0.0"

kubectl logs music-6c45d566f4-9qdlr  
# 2025-10-26 06:44:34,957 WARN  [io.agr.pool] (agroal-11) Datasource '<default>': FATAL: password authentication failed for user "my-default"
# 2025-10-26 06:44:34,957 WARN  [org.hib.eng.jdb.spi.SqlExceptionHelper] (JPA Startup Thread: <default>) SQL Error: 0, SQLState: 28P01
# 2025-10-26 06:44:34,957 ERROR [org.hib.eng.jdb.spi.SqlExceptionHelper] (JPA Startup Thread: <default>) FATAL: password authentication failed for user "my-default"
# 2025-10-26 06:44:35,031 ERROR [io.qua.run.Application] (main) Failed to start application (with profile prod): org.postgresql.util.PSQLException: FATAL: password authentication failed for user "my-default"
#         at org.postgresql.core.v3.ConnectionFactoryImpl.doAuthentication(ConnectionFactoryImpl.java:623)
#         at org.postgresql.core.v3.ConnectionFactoryImpl.tryConnect(ConnectionFactoryImpl.java:163)
#         at org.postgresql.core.v3.ConnectionFactoryImpl.openConnectionImpl(ConnectionFactoryImpl.java:215)
#         at org.postgresql.core.ConnectionFactory.openConnection(ConnectionFactory.java:51)
#         at org.postgresql.jdbc.PgConnection.<init>(PgConnection.java:225)
#         at org.postgresql.Driver.makeConnection(Driver.java:466)
#         at org.postgresql.Driver.connect(Driver.java:265)
#         at io.agroal.pool.ConnectionFactory.createConnection(ConnectionFactory.java:210)
#         at io.agroal.pool.ConnectionPool$CreateConnectionTask.call(ConnectionPool.java:513)
#         at io.agroal.pool.ConnectionPool$CreateConnectionTask.call(ConnectionPool.java:494)
#         at java.base/java.util.concurrent.FutureTask.run(FutureTask.java:264)
#         at io.agroal.pool.util.PriorityScheduledExecutor.beforeExecute(PriorityScheduledExecutor.java:75)
#         at java.base/java.util.concurrent.ThreadPoolExecutor.runWorker(ThreadPoolExecutor.java:1126)
#         at java.base/java.util.concurrent.ThreadPoolExecutor$Worker.run(ThreadPoolExecutor.java:628)
#         at java.base/java.lang.Thread.run(Thread.java:834)

##############################################################
# 문제 진단
##############################################################
# 신규 차트의 values 확인
helm show values bitnami/postgresql --version="18.1.1"

# 위에서 지정한 postgresqlUsername이 -> auth.username으로 바뀐 것을 확인
helm show values bitnami/postgresql --version="18.1.1" | yq '...|path|join(".")' | grep -i username
# global.postgresql.auth.username
# global.postgresql.auth.username
# auth.username
# auth.username

# 위의 내용을 기반으로 신규 차트에서 바뀐 옵션 값 확인
# https://artifacthub.io/packages/helm/bitnami/postgresql/18.1.1
```

![Bitnami Postgresql Global Parameters](/assets/img/ci-cd/ci-cd-study/bitnami-postgresql-global-value.webp)

{% raw %}

```shell
##############################################################
# 문제 해결 (차트 및 템플릿 수정)
##############################################################

# 차트 수정 전 values를 참조하는 곳 확인 (deployment.yaml 수정하면 될 듯)
grep -R "postgresqlUsername" .                                                                              
# ./values.yaml:  postgresqlUsername: my-default
# ./templates/deployment.yaml:              value: {{ .Values.postgresql.postgresqlUsername | default (printf "postgres" ) | quote }}

grep -R "postgresqlPassword" .       
# ./values.yaml:  postgresqlPassword: postgres

grep -R "postgresqlDatabase" . 
# ./values.yaml:  postgresqlDatabase: mydb

grep -R "secretName"          
values.yaml:  secretName: music-db-postgresql
templates/deployment.yaml:                  name: {{ .Values.postgresql.secretName | default (printf "%s-postgresql" ( .Release.Name )) | quote }}

grep -R "secretKey" 
values.yaml:  secretKey: postgresql-password
templates/deployment.yaml:                secretKeyRef:
templates/deployment.yaml:                  key: {{ .Values.postgresql.secretKey }}

# values.yaml 수정
cat << EOF > values.yaml
image:
  repository: quay.io/gitops-cookbook/music
  tag: "1.0.0"
  pullPolicy: Always
  containerPort: 8080

replicaCount: 1

postgresql:
  server: jdbc:postgresql://music-db-postgresql:5432/mydb
  auth:
    username: my-default # 사용자 username
    password: postgres   # 사용자 password
    database: mydb       # 사용자 db name
  secretName: music-db-postgresql
  secretKey: password    # postgresql-password는 관리자 계정 password
EOF

# 수정
cat << EOF > templates/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ .Chart.Name}}
  labels:
    app.kubernetes.io/name: {{ .Chart.Name}}
    {{- if .Chart.AppVersion }}
    app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
    {{- end }}
spec:
  replicas: {{ .Values.replicaCount }}
  selector:
    matchLabels:
      app.kubernetes.io/name: {{ .Chart.Name}}
  template:
    metadata:
      labels:
        app.kubernetes.io/name: {{ .Chart.Name}}
    spec:
      containers:
        - image: "{{ .Values.image.repository }}:{{ .Values.image.tag | default .Chart.AppVersion}}"
          imagePullPolicy: {{ .Values.image.pullPolicy }}
          name: {{ .Chart.Name}}
          ports:
            - containerPort: {{ .Values.image.containerPort }}
              name: http
              protocol: TCP
          env:
            - name: QUARKUS_DATASOURCE_JDBC_URL
              value: {{ .Values.postgresql.server | default (printf "%s-postgresql" ( .Release.Name )) | quote }}
            - name: QUARKUS_DATASOURCE_USERNAME
              value: {{ .Values.postgresql.auth.username | default (printf "postgres" ) | quote }}
            - name: QUARKUS_DATASOURCE_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: {{ .Values.postgresql.secretName | default (printf "%s-postgresql" ( .Release.Name )) | quote }}
                  key: {{ .Values.postgresql.secretKey }}
EOF

##############################################################
# 문제 해결 확인
##############################################################
helm uninstall music-db
helm install music-db .

kubectl get sts,pod,svc,ep,secret,pv,pvc
# NAME                                   READY   AGE
# statefulset.apps/music-db-postgresql   1/1     7m1s

# NAME                         READY   STATUS    RESTARTS   AGE
# pod/music-7cb6dd76c7-9wqkq   1/1     Running   0          4m19s
# pod/music-db-postgresql-0    1/1     Running   0          7m1s

# 포트포워딩
kubectl port-forward service/music 8080:8080

# 확인 
curl -s http://localhost:8080/song
# [{"id":1,"artist":"DT","name":"Quiero Munchies"},{"id":2,"artist":"Lin-Manuel Miranda","name":"We Don't Talk About Bruno"},{"id":3,"artist":"Imagination","name":"Just An Illusion"},{"id":4,"artist":"Txarango","name":"Tanca Els Ulls"},{"id":5,"artist":"Halsey","name":"Could Have Been Me"}]%


##############################################################
# 해결 확인, 자원 정리
##############################################################
helm uninstall music-db
kubectl delete pvc --all
```

{% endraw %}

---

## 9. Triggering a Rolling Update Automatically

일반적으로 `ConfigMap`이 변경되더라도 이미 실행 중인 Pod에는 자동으로 반영되지 않습니다. 즉, `Pod`는 `ConfigMap`의 변경 사실을 인식하지 못하고, 수동으로 재배포(`kubectl rollout restart`)를 수행해야만 최신 설정이 반영됩니다. 이와 같이, `ConfigMap` 값이 수정되어도 `Pod`가 재시작되지 않으면, 애플리케이션은 여전히 구 버전의 설정으로 동작하기 때문에, `ConfigMap` 에 설정된 내용에 의존하며 동작하는 서비스에서는 장애나 일관성 문제를 야기할 수 있습니다.

이러한 문제를 해결하기 위해 **Helm**의 `sha256sum` 템플릿 함수를 사용하여 `ConfigMap` 파일의 해시를 **Pod Annotation**에 주입할 수 있습니다. 해당 방식은 `ConfigMap` 내용이 바뀔 때마다 해시 값이 달라져 `Deployment` 템플릿의 스펙이 자동으로 변경되므로, **Kubernetes는 이를 새로운 버전의 Deployment로 인식하고 자동으로 `Rolling Update`를 수행**합니다.

### 9.1. greetings Helm Chart 생성 및 배포

{% raw %}

```shell
##############################################################
# 프로젝트 초기 설정
##############################################################
mkdir -p greetings/templates
cd greetings


# deployment.yaml
cat << EOF > templates/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ .Chart.Name }}
  labels:
    app.kubernetes.io/name: {{ .Chart.Name }}
    {{- if .Chart.AppVersion }}
    app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
    {{- end }}
spec:
  replicas: {{ .Values.replicaCount }}
  selector:
    matchLabels:
      app.kubernetes.io/name: {{ .Chart.Name }}
  template:
    metadata:
      labels:
        app.kubernetes.io/name: {{ .Chart.Name }}
    spec:
      containers:
        - image: "{{ .Values.image.repository }}:{{ .Values.image.tag | default .Chart.AppVersion }}"
          imagePullPolicy: {{ .Values.image.pullPolicy }}
          name: {{ .Chart.Name }}
          ports:
            - containerPort: {{ .Values.image.containerPort}}
              name: http
              protocol: TCP
          env:
            - name: GREETING
              valueFrom:
                configMapKeyRef:
                  name: {{ .Values.configmap.name }}
                  key: greeting
EOF

# configmap.yaml
cat << EOF > templates/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: greeting-config
data:
  greeting: Aloha
EOF

# service.yaml
cat << EOF > templates/service.yaml
apiVersion: v1
kind: Service
metadata:
  labels:
    app.kubernetes.io/name: {{ .Chart.Name }}
  name: {{ .Chart.Name }}
spec:
  ports:
    - name: http
      port: {{ .Values.image.containerPort }}
      targetPort: {{ .Values.image.containerPort }}
  selector:
    app.kubernetes.io/name: {{ .Chart.Name }}
EOF

# values.yaml
cat << EOF > values.yaml
image:
  repository: quay.io/gitops-cookbook/greetings
  tag: "1.0.0"
  pullPolicy: Always
  containerPort: 8080

replicaCount: 1

configmap:
  name: greeting-config
EOF

# Chart.yaml
cat << EOF > Chart.yaml
apiVersion: v2
name: greetings
description: A Helm chart for greetings
type: application
version: 0.1.0
appVersion: "1.0.0"
EOF

##############################################################
# Helm 배포
##############################################################
helm install greetings .

##############################################################
# 리소스 확인
##############################################################
kubectl get deploy,pod,svc,cm 
# NAME                        READY   UP-TO-DATE   AVAILABLE   AGE
# deployment.apps/greetings   1/1     1            1           37s

# NAME                             READY   STATUS    RESTARTS   AGE
# pod/greetings-6b869f6d54-4wqrr   1/1     Running   0          37s

# NAME                 TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)    AGE
# service/greetings    ClusterIP   10.96.155.175   <none>        8080/TCP   37s
# service/kubernetes   ClusterIP   10.96.0.1       <none>        443/TCP    18h

# NAME                         DATA   AGE
# configmap/greeting-config    1      37s
# configmap/kube-root-ca.crt   1      18h

##############################################################
# 포트포워딩으로 확인
##############################################################
kubectl port-forward service/greetings 8080:8080

curl localhost:8080;echo 
# Aloha Alexandra
```

{% endraw %}

### 9.2. greetings Helm Chart ConfigMap 수정 후 확인

```shell
##############################################################
# ConfigMap 및 appVersions 수정
##############################################################
# configmap.yaml
cat << EOF > templates/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: greeting-config
data:
  greeting: Hola
EOF

# Chart.yaml
cat << EOF > Chart.yaml
apiVersion: v2
name: greetings
description: A Helm chart for greetings
type: application
version: 0.1.0
appVersion: "1.0.1"
EOF

##############################################################
# 변경된 차트로 업그레이드
##############################################################
helm upgrade greetings .

# pod 상태 확인 (재시작 X)
kubectl get pods                                 
# NAME                         READY   STATUS    RESTARTS   AGE
# greetings-6b869f6d54-4wqrr   1/1     Running   0          7m52s

##############################################################
# 포트포워딩 후 바뀌었는지 다시 확인
##############################################################
kubectl port-forward service/greetings 8080:8080

curl localhost:8080;echo 
# Aloha Alexandra # 바뀌지 않음 (Hola로 바뀌어야 함)
```

> 아래와 같이 ConfigMap Object가 변경되어도 Deployment 리소스에는 변경된 부분이 존재하지 않으므로, Pod는 재시작하지 않습니다. 따라서, 환경 변수의 값도 갱신되지 않습니다.  
{: .prompt-tip}

![Greetings application with new configuration value](/assets/img/ci-cd/ci-cd-study/greetings-application-with-new-configuration-value.webp)
> [O’Reilly GitOps Cookbook: Kubernetes Automation in Practice](https://product.kyobobook.co.kr/detail/S000214781090)  
> Greetings application with new configuration value - 5.7. Triggering a Rolling Update Automatically p.121

### 9.3. sha256sum 함수를 사용해 ConfigMap 에 대한 변경사항 Rolling Update Triggering

위와 같은 문제를 해결하기 위해 **Helm Chart**의 `sha256sum` 함수를 사용할 수 있습니다. `configmap.yaml` 파일 내용에 대한 `SHA-256` 값을 계산하고 이를 **Pod Annotation**으로 설정하면 `ConfigMap`의 내용이 바뀔 때마다 `Pod Manifest`도 바뀌므로, `Rolling Update`가 자동으로 시작됩니다.

{% raw %}

```shell
##############################################################
# Deployment의 pod annotation에 sha256sum 함수 추가
##############################################################
# deployment.yaml (spec.template.metadata.annotation 추가)
cat << EOF > templates/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ .Chart.Name }}
  labels:
    app.kubernetes.io/name: {{ .Chart.Name }}
    {{- if .Chart.AppVersion }}
    app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
    {{- end }}
spec:
  replicas: {{ .Values.replicaCount }}
  selector:
    matchLabels:
      app.kubernetes.io/name: {{ .Chart.Name }}
  template:
    metadata:
      labels:
        app.kubernetes.io/name: {{ .Chart.Name }}
      annotations: # 추가 
        checksum/config: {{ include (print $.Template.BasePath "/configmap.yaml") . | sha256sum }} # 추가
    spec:
      containers:
        - image: "{{ .Values.image.repository }}:{{ .Values.image.tag | default .Chart.AppVersion }}"
          imagePullPolicy: {{ .Values.image.pullPolicy }}
          name: {{ .Chart.Name }}
          ports:
            - containerPort: {{ .Values.image.containerPort}}
              name: http
              protocol: TCP
          env:
            - name: GREETING
              valueFrom:
                configMapKeyRef:
                  name: {{ .Values.configmap.name }}
                  key: greeting
EOF

##############################################################
# ConfigMap 변경 후 Rolling Update 가 되는지 확인
##############################################################
# 현재 Helm Chart 삭제
helm uninstall greetings

# Chart.yaml (appVersion: "1.0.0" 으로 되돌린 뒤 배포)
cat << EOF > Chart.yaml
apiVersion: v2
name: greetings
description: A Helm chart for greetings
type: application
version: 0.1.0
appVersion: "1.0.0"
EOF

##############################################################
# Helm Chart 배포 및 확인
##############################################################
helm install greetings .

# 배포 확인
kubectl get deploy,pod,svc,cm 
# NAME                        READY   UP-TO-DATE   AVAILABLE   AGE
# deployment.apps/greetings   1/1     1            1           6s

# NAME                            READY   STATUS    RESTARTS   AGE
# pod/greetings-dcd6dbddf-dfmls   1/1     Running   0          6s

# NAME                 TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)    AGE
# service/greetings    ClusterIP   10.96.214.104   <none>        8080/TCP   6s
# service/kubernetes   ClusterIP   10.96.0.1       <none>        443/TCP    18h

# NAME                         DATA   AGE
# configmap/greeting-config    1      6s

##############################################################
# 포트포워딩 후 현재 적용된 Config 내용 확인
##############################################################
kubectl port-forward service/greetings 8080:8080

curl localhost:8080;echo 
# Aloha Ada

##############################################################
# Chart.yaml & ConfigMap 수정 후 helm upgrade 진행
##############################################################
# configmap.yaml
cat << EOF > templates/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: greeting-config
data:
  greeting: Namaste
EOF

# Chart.yaml
cat << EOF > Chart.yaml
apiVersion: v2
name: greetings
description: A Helm chart for greetings
type: application
version: 0.1.0
appVersion: "1.0.1"
EOF

# Helm Upgrade
helm upgrade greetings .

# 배포 확인 (기존 pod -> Terminating, 신규 pod 생성 중)
kubectl get deploy,pod,svc,cm 
# NAME                        READY   UP-TO-DATE   AVAILABLE   AGE
# deployment.apps/greetings   1/1     1            1           3m27s

# NAME                             READY   STATUS        RESTARTS   AGE
# pod/greetings-6c5c98bb7c-vwcpr   1/1     Running       0          25s
# pod/greetings-dcd6dbddf-dfmls    1/1     Terminating   0          3m27s

# NAME                 TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)    AGE
# service/greetings    ClusterIP   10.96.214.104   <none>        8080/TCP   3m27s
# service/kubernetes   ClusterIP   10.96.0.1       <none>        443/TCP    18h

# NAME                         DATA   AGE
# configmap/greeting-config    1      3m58s

##############################################################
# 포트포워딩 후 현재 적용된 Config 내용 확인 (Aloha -> Namaste로 잘 변경됨)
##############################################################
kubectl port-forward service/greetings 8080:8080

curl localhost:8080;echo 
# Namaste Ada


##############################################################
# 실습 마무리 (자원 삭제)
##############################################################
kind delete cluster --name myk8s
```

{% endraw %}

---

## 10. 마무리

이번 글에서는 `Helm`의 기본 구조부터 의존성 관리, 그리고 `ConfigMap` 변경을 체크섬 기반 롤링 업데이트로 자동화하는 패턴에 대해 알아봤습니다. `Kustomize`가 원본 YAML을 유지하며 템플릿 없이 변경을 적용하는 데 중점을 둔다면, `Helm`은 **Chart**라는 패키징 개념과 **Release**라는 버전 관리, 그리고 **Go Template**을 통한 강력한 동적 구성 기능을 제공합니다.

---

## 11. Reference

- [SimplyBlock - What is a Helm Chart?](https://www.simplyblock.io/glossary/what-is-a-helm-chart/)
- [Helm Docs](https://helm.sh/docs/)
- [Helm GitHub](https://github.com/helm/helm)
- [Helm Docs - The Chart Chart Best Practices Guide](https://helm.sh/docs/chart_best_practices/)
- [Helm Docs - The Chart Template Developer's Guide](https://helm.sh/docs/chart_template_guide/)
- [Helm Docs - The Chart Repository Guide](https://helm.sh/docs/topics/chart_repository/)
- [Kubernetes Docs - ConfigMap](https://kubernetes.io/docs/concepts/configuration/configmap/)
- [Kubernetes Docs - Configure a Pod to Use a ConfigMap](https://kubernetes.io/docs/tasks/configure-pod-container/configure-pod-configmap/)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
