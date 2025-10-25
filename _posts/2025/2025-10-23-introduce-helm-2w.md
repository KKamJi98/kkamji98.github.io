---
title: Helm 소개
date: 2025-10-25 23:42:31 +0900
author: kkamji
categories: [DevOps]
tags: [devops, ci-cd-study, ci-cd-study-1w, helm]
comments: true
image:
  path: /assets/img/ci-cd/ci-cd-study/ci-cd-study.webp
---

`CloudNet@` Gasida님이 진행하는 `CI/CD + ArgoCD + Vault Study` 를 진행하며 학습한 내용을 공유합니다.

이번 포스트에서는 *O'Reilly GitOps Cookbook* 의 4장에 해당 하는 **Helm**에 대해 알아보겠습니다.

---

## 1. Helm 소개

**Helm**은 유사하지만 Go Template 언어를 사용하여 **Kubernetes Application**을 설치하고 관리하고 관리하는 과정을 좀 더 편리하게 도움을 주는 솔루션입니다. **Helm**은 **Kustomize**와 유사하지만 **Chart**라는 개념이 존재합니다. **Chart**는 Package Manager 처럼 동작하며 여러 개의 Kubernetes Manifest들을 Package 형태로 묶는 기능을 제공하며 다른 차트에 대한 의존성, 버전 관리 그리고 배포 가능한 **Artifact**와 같은 다양한 요소를 포함합니다.

---

## 2. Helm Project의 구조와 구성요소

Helm Chart는 아래와 같은 구성요소와 구조를 갖습니다.

![What is a Helm Chart?](/assets/img/ci-cd/ci-cd-study/what-is-a-helm-chart.webp)
> SimplyBlock - What is a Helm Chart? - <https://www.simplyblock.io/glossary/what-is-a-helm-chart>

### Helm Project의 구조

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

### Helm Project의 구성 요소

| 항목             | 설명                                                                         |
| ---------------- | ---------------------------------------------------------------------------- |
| **Chart.yaml**   | Chart의 이름, 버전, 의존성 등 메타데이터가 정의된 파일                       |
| **values.yaml**  | 템플릿에서 참조하는 기본 값이 정의되어 있으며, `-f` 옵션으로 오버라이드 가능 |
| **charts/**      | 의존성으로 포함된 서브 차트가 위치                                           |
| **templates/**   | Kubernetes Manifest 템플릿이 위치하며, Go Template(&#123;&#123; &#125;&#125;) 문법 사용 |
| **_helpers.tpl** | 공통 함수와 템플릿 헬퍼가 정의된 파일                                        |
| **NOTES.txt**    | 설치 완료 후 출력되는 안내 메시지가 정의                                     |
| **tests/**       | Chart 테스트 리소스가 포함되어 있으며, `helm test`로 검증에 사용             |

## 3. Helm Chart 생성하기 실습

### Helm Chart 생성

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
# Helm Chart 구성요소 생성
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
    app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}     # appVersion 값을 가져와 지정하고 따움표 처리
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

# 차트 기본값 default vales 이 담긴 파일 작성 : 애플리케이션 배포 시점에 다른 값으로 대체될 수 있는, 기본 설정을 담아두는 곳
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

# (참고) securityContext의 값을 채우기 위해 toYaml 함수를 사용하였으므로 values.yaml 의 보안 컨텍스트 속성값은 YAML 객채여야 한다.
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

### Helm Chart Rendering (Template)

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
    app.kubernetes.io/version: "1.0.0"     # Chart.yaml  appVersion 값을 가져와 지정하고 따움표 처리
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

### Helm Chart 배포 및 확인

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
# Helm 자체가 배포 릴리스 메타데이터를 저장하기 위해 자동으로 Sercet 리소스 생성 : Helm이 차트의 상태를 복구하거나 rollback 할 때 이 데이터를 이용
kubectl get secret
# NAME                           TYPE                 DATA   AGE
# sh.helm.release.v1.pacman.v1   helm.sh/release.v1   1      5m17s
```

### Helm Chart Upgrade, Metadata 확인

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
helm get notes pacman    # chart nodes

# 삭제 후 secret 확인
helm uninstall pacman
kubectl get secret
# No resources found in default namespace.
```

## 4. Template 간 코드 공유

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
# _helpers.tpl 파일을 사용해 기존 코드를 디렉터링
##############################################################
## _helpers.tpl 파일 작성
cat << EOF > templates/_helpers.tpl
{{- define "pacman.selectorLabels" -}}   # stetement 이름을 정의
app.kubernetes.io/name: {{ .Chart.Name}} # 해당 stetement 가 하는 일을 정의
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

> Template 함수를 정의하는 파일명으로는 `_helpers.tpl`을 사용하는 것이 일반적이지만, 사실 `_`로 시작하지만 하면 됩니다. 이와 같은 파일들은 Kubernetes Manifest 파일로 취급되지 않습니다.  
{: .prompt-tip}

## Reference

- [SimplyBlock - What is a Helm Chart?](https://www.simplyblock.io/glossary/what-is-a-helm-chart/)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
