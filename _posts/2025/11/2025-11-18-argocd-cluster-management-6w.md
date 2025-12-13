---
title: Argo CD Multi Cluster Management
date: 2025-11-18 21:33:18 +0900
author: kkamji
categories: [DevOps]
tags: [devops, ci-cd-study, ci-cd-study-6w, gitops, kubernetes, argocd, cluster-management]
comments: true
image:
  path: /assets/img/ci-cd/ci-cd-study/ci-cd-study.webp
---

`CloudNet@` Gasida님이 진행하는 `CI/CD + ArgoCD + Vault Study`를 진행하며 학습한 내용을 공유합니다.

이번 포스팅에서는 로컬 환경에서 `kind`를 사용하여 관리용(Management), 운영용(Production), 개발용(Development) 클러스터를 구축하고, `Argo CD`를 이용해 중앙에서 멀티 클러스터에 애플리케이션을 배포하는 과정을 정리해보겠습니다.

---

## 1. Overview

![Argo CD Multi-Cluster Architecture](/assets/img/ci-cd/ci-cd-study/argo-multi-cluster-architecture.webp)

- **kind-mgmt**: Argo CD가 설치되는 **제어(Control) 클러스터**
- **kind-prd**: 실제 서비스가 운영된다고 가정한 **운영 클러스터**
- **kind-dev**: 개발 및 테스트가 이루어지는 **개발 클러스터**

`kind-mgmt`에 설치된 Argo CD는 `kind-prd`와 `kind-dev` 클러스터의 자격 증명을 등록받아, Git 저장소의 변경 사항을 각 대상 클러스터로 동기화(Sync)하는 역할을 수행합니다.

---

## 2. 실습 환경 준비

### 2.1. kind-mgmt Cluster 배포 및 세팅

```shell
##############################################################
# kind-mgmt Cluster 배포 (Argo CD 30000번 포트 노출)
##############################################################
kind create cluster --name mgmt --image kindest/node:v1.32.8 --config - <<EOF
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
- role: control-plane
  labels:
    ingress-ready: true
  extraPortMappings:
  - containerPort: 30000 # ArgoCD UI 접근을 위한 포트
    hostPort: 30000
  - containerPort: 31001
    hostPort: 31001
EOF

##############################################################
# argocd namespace 생성
##############################################################
kubectl create ns argocd

##############################################################
# argocd-values.yaml 생성
##############################################################
cat <<EOF > argocd-values.yaml
server:
  service:
    type: NodePort
    nodePortHttps: 30000
  extraArgs:
    - --insecure
EOF

##############################################################
# Argo CD 설치 v3.1.9
##############################################################
helm repo add argo https://argoproj.github.io/argo-helm
helm install argocd argo/argo-cd --version 9.0.5 -f argocd-values.yaml --namespace argocd



##############################################################
# 접속 확인
##############################################################
curl -vk http://localhost:30000/

##############################################################
# 최초 접속 암호 확인
##############################################################
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d ;echo
# pOHBR5nTi2hx6RvY

ARGOPW=<최초 접속 암호>
ARGOPW=pOHBR5nTi2hx6RvY

##############################################################
# argocd 서버 cli 로그인
##############################################################
argocd login localhost:30000 --insecure --username admin --password $ARGOPW
# WARNING: server is not configured with TLS. Proceed (y/n)? y
# 'admin:login' logged in successfully
# Context 'localhost:30000' updated

##############################################################
# 확인
##############################################################
argocd cluster list
argocd proj list
argocd account list

##############################################################
# admin 계정 암호 변경 : qwe12345
##############################################################
argocd account update-password --current-password $ARGOPW --new-password qwe12345

##############################################################
# Argo CD 웹 접속 주소 확인 : admin 계정 / qwe12345
##############################################################
open "http://localhost:30000/"
```

![Argo CD Main Login Check kind-mgmt](/assets/img/ci-cd/ci-cd-study/argo-main-login-check-kind-mgmt.webp)

### 2.2. kind-prd, kind-dev Cluster 배포 및 kubeconfig 파일 수정

```shell
##############################################################
# 설치 전 확인
##############################################################
kubectl config get-contexts
# CURRENT   NAME        CLUSTER         AUTHINFO           NAMESPACE
# *         kind-mgmt   kind-mgmt       kind-mgmt          

##############################################################
# 도커 네트워크 확인 : mgmt 컨테이너 IP 확인
##############################################################
docker network ls
docker network inspect kind | jq

##############################################################
# kind k8s 배포
##############################################################
kind create cluster --name dev --image kindest/node:v1.32.8 --config - <<EOF
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
- role: control-plane
  extraPortMappings:
  - containerPort: 31002
    hostPort: 31002
EOF

kind create cluster --name prd --image kindest/node:v1.32.8 --config - <<EOF
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
- role: control-plane
  extraPortMappings:
  - containerPort: 31003
    hostPort: 31003
EOF


##############################################################
# 설치 후 확인
##############################################################
kubectl config get-contexts
CURRENT   NAME        CLUSTER     AUTHINFO    NAMESPACE
          kind-dev    kind-dev    kind-dev    
          kind-mgmt   kind-mgmt   kind-mgmt   
*         kind-prd    kind-prd    kind-prd  

##############################################################
# mgmt k8s 자격증명 변경
##############################################################
kubectl config use-context kind-mgmt
kubectl config get-contexts
# CURRENT   NAME        CLUSTER         AUTHINFO           NAMESPACE
#           kind-dev    kind-dev        kind-dev           
# *         kind-mgmt   kind-mgmt       kind-mgmt          
#           kind-prd    kind-prd        kind-prd           

##############################################################
# kubectl 접근 여부 확인 (node 및 pod 확인)
##############################################################
kubectl get node -v=6 --context kind-mgmt
kubectl get node -v=6 --context kind-dev
kubectl get node -v=6 --context kind-prd
cat ~/.kube/config

kubectl get pod -A --context kind-mgmt
kubectl get pod -A --context kind-dev
kubectl get pod -A --context kind-prd

##############################################################
# alias 설정
##############################################################
alias k8s1='kubectl --context kind-mgmt'
alias k8s2='kubectl --context kind-dev'
alias k8s3='kubectl --context kind-prd'

##############################################################
# alias 확인
##############################################################
k8s1 get node -o wide
k8s2 get node -o wide
k8s3 get node -o wide


##############################################################
# 도커 네트워크 확인 : 컨테이너 IP 확인
##############################################################
docker network inspect kind | grep -E 'Name|IPv4Address'
        # "Name": "kind",
        #         "Name": "dev-control-plane",
        #         "IPv4Address": "172.18.0.3/16",
        #         "Name": "mgmt-control-plane",
        #         "IPv4Address": "172.18.0.2/16",
        #         "Name": "prd-control-plane",
        #         "IPv4Address": "172.18.0.4/16",

##############################################################
# 도메인 통신 확인 : 물론 IP 통신도 가능
##############################################################
docker ps # k8s-api 6443 포트 포워딩 확인
docker exec -it mgmt-control-plane curl -sk https://dev-control-plane:6443/version
docker exec -it mgmt-control-plane curl -sk https://prd-control-plane:6443/version
```

### 2.3. Argo CD에 다른 Kubernetes 클러스터 추가

#### 2.3.1. Cluster Add Script (`register-cluster.sh`)

```shell
# ==========================================
# 1. 환경 변수 설정
# ==========================================
# 대상 클러스터 (Argo CD에 등록될 클러스터 및 주소)
TARGET_CONTEXT="kind-dev"
TARGET_INTERNAL_URL="https://dev-control-plane:6443" # ArgoCD가 접속할 내부 주소
CLUSTER_NAME_IN_ARGO="dev-cluster"

# ArgoCD가 설치된 클러스터
ARGOCD_CONTEXT="kind-mgmt"
ARGOCD_NAMESPACE="argocd"

echo "[${TARGET_CONTEXT}] 클러스터를 [${ARGOCD_CONTEXT}]의 ArgoCD에 등록을 시작합니다..."

# ==========================================
# 2. 대상 클러스터에 ServiceAccount 및 RBAC 생성
# ==========================================
cat <<EOF | kubectl --context="${TARGET_CONTEXT}" apply -f -
apiVersion: v1
kind: ServiceAccount
metadata:
  name: argocd-manager
  namespace: kube-system
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: argocd-manager-role
rules:
- apiGroups: ["*"]
  resources: ["*"]
  verbs: ["*"]
- nonResourceURLs: ["*"]
  verbs: ["*"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: argocd-manager-role-binding
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: argocd-manager-role
subjects:
- kind: ServiceAccount
  name: argocd-manager
  namespace: kube-system
EOF

# ==========================================
# 3. 토큰 시크릿 생성 (Long Live Token)
# ==========================================
cat <<EOF | kubectl --context="${TARGET_CONTEXT}" apply -f -
apiVersion: v1
kind: Secret
metadata:
  name: argocd-manager-token
  namespace: kube-system
  annotations:
    kubernetes.io/service-account.name: argocd-manager
type: kubernetes.io/service-account-token
EOF

echo "⏳ 토큰 생성을 대기 중..."
sleep 2

# ==========================================
# 4. 토큰 및 CA 인증서 추출
# ==========================================
BEARER_TOKEN=$(kubectl --context="${TARGET_CONTEXT}" -n kube-system get secret argocd-manager-token -o jsonpath='{.data.token}' | base64 -d)
CA_DATA=$(kubectl --context="${TARGET_CONTEXT}" -n kube-system get secret argocd-manager-token -o jsonpath='{.data.ca\.crt}')

# ==========================================
# 5. ArgoCD 클러스터(mgmt)에 Secret 등록
# ==========================================
cat <<EOF | kubectl --context="${ARGOCD_CONTEXT}" apply -f -
apiVersion: v1
kind: Secret
metadata:
  name: cluster-${CLUSTER_NAME_IN_ARGO}
  namespace: ${ARGOCD_NAMESPACE}
  labels:
    argocd.argoproj.io/secret-type: cluster
    name: ${CLUSTER_NAME_IN_ARGO}
type: Opaque
stringData:
  name: ${CLUSTER_NAME_IN_ARGO}
  server: ${TARGET_INTERNAL_URL}
  config: |
    {
      "bearerToken": "${BEARER_TOKEN}",
      "tlsClientConfig": {
        "insecure": false,
        "caData": "${CA_DATA}"
      }
    }
EOF

echo "등록 완료! ArgoCD에서 확인해주세요."
```

#### 2.3.2. Dev Cluster 추가

```shell
##############################################################
# ArgoCD cluster list 확인
##############################################################
argocd cluster list
argocd cluster list -o json | jq

kubectl get secret -n argocd
# NAME                           TYPE                 DATA   AGE
# argocd-initial-admin-secret    Opaque               1      43m
# argocd-notifications-secret    Opaque               0      43m
# argocd-redis                   Opaque               1      43m
# argocd-secret                  Opaque               3      43m
# sh.helm.release.v1.argocd.v1   helm.sh/release.v1   1      43m
kubectl get secret -n argocd argocd-secret -o jsonpath='{.data}' | jq

##############################################################
# argocd-manager service account 확인
##############################################################
k8s2 get sa -n kube-system
k8s2 get sa -n kube-system | grep argo | wc -l
# 0
k8s3 get sa -n kube-system
k8s3 get sa -n kube-system | grep argo | wc -l
# 0

##############################################################
# ArgoCD cluster 등록
##############################################################
bash register-cluster.sh
# [kind-dev] 클러스터를 [kind-mgmt]의 ArgoCD에 등록을 시작합니다...
# Warning: resource serviceaccounts/argocd-manager is missing the kubectl.kubernetes.io/last-applied-configuration annotation which is required by kubectl apply. kubectl apply should only be used on resources created declaratively by either kubectl create --save-config or kubectl apply. The missing annotation will be patched automatically.
# serviceaccount/argocd-manager configured
# Warning: resource clusterroles/argocd-manager-role is missing the kubectl.kubernetes.io/last-applied-configuration annotation which is required by kubectl apply. kubectl apply should only be used on resources created declaratively by either kubectl create --save-config or kubectl apply. The missing annotation will be patched automatically.
# clusterrole.rbac.authorization.k8s.io/argocd-manager-role configured
# Warning: resource clusterrolebindings/argocd-manager-role-binding is missing the kubectl.kubernetes.io/last-applied-configuration annotation which is required by kubectl apply. kubectl apply should only be used on resources created declaratively by either kubectl create --save-config or kubectl apply. The missing annotation will be patched automatically.
# clusterrolebinding.rbac.authorization.k8s.io/argocd-manager-role-binding configured
# secret/argocd-manager-token unchanged
# ⏳ 토큰 생성을 대기 중...
# secret/cluster-dev-cluster created
# 등록 완료! ArgoCD에서 확인해주세요.

##############################################################
# argocd-manager 권한 확인
##############################################################
k8s2 get sa -n kube-system argocd-manager
kubectl rolesum -n kube-system argocd-manager --context kind-dev
# • [CRB] */argocd-manager-role-binding ⟶  [CR] */argocd-manager-role
#   Resource  Name  Exclude  Verbs  G L W C U P D DC  
#   *.*       [*]     [-]     [-]   ✔ ✔ ✔ ✔ ✔ ✔ ✔ ✔ 

##############################################################
# ArgoCD에 등록된 클러스터 확인 (Label을 이용하여 필터링)
##############################################################
# 클러스터 자격증명은 시크릿에 저장되고, 해당 시크릿에 반드시 argocd.argoproj.io/secret-type=cluster Label이 필요함
kubectl get secret -n argocd -l argocd.argoproj.io/secret-type=cluster

##############################################################
# k9s 에서 data 내용 확인
##############################################################
# k9s -> : secret argocd -> 아래 secret 에서 d (Describe) -> x (Toggle Decode) 로 확인

Name:         cluster-dev-cluster
Namespace:    argocd
Labels:       argocd.argoproj.io/secret-type=cluster
              name=dev-cluster
Annotations:  <none>

Type:  Opaque

Data
====
config: {
  "bearerToken": "eyJhbGciOiJSUzI1NiIsImtpZCI6Ild3Y05sWkVLeEl4czN0djFsUHFzOEd2ZUhQb0ZMeTJJLWpGVkpOZExuYW8ifQ.eyJpc3MiOiJrdWJlcm5ldGVzL3NlcnZpY2VhY2NvdW50Iiwia3ViZXJuZXRlcy5pby9zZXJ2aWNlYWNjb3VudC9uYW1lc3BhY2UiOiJrdWJlLXN5c3RlbSIsImt1YmVybmV0ZXMuaW8vc2VydmljZWFjY291bnQvc2VjcmV0Lm5hbWUiOiJhcmdvY2QtbWFuYWdlci10b2tlbiIsImt1YmVybmV0ZXMuaW8vc2VydmljZWFjY291bnQvc2VydmljZS1hY2NvdW50Lm5hbWUiOiJhcmdvY2QtbWFuYWdlciIsImt1YmVybmV0ZXMuaW8vc2VydmljZWFjY291bnQvc2VydmljZS1hY2NvdW50LnVpZCI6ImJkM2VhYWJkLTc3MzItNDEyMi1iZmZiLTZjNjNkMjkwMjJjNCIsInN1YiI6InN5c3RlbTpzZXJ2aWNlYWNjb3VudDprdWJlLXN5c3RlbTphcmdvY2QtbWFuYWdlciJ9.UQvopJ2aoc-g9hdcN9HYLQOm3iUb-lufnS68Vn-pNIBxq0gztp3qhIM7A61-bN7VNcb22aiuKw6LnaWGkwyj8Qrngc8K3NUoU6XGi7VWHG1ORsTiPsucOqxjfbpIC30Dvmz2L8XDSEg44EC3_puBBTt_EvyT5ZMUn525GrfvicLQgRyzbZNsRfB41WpwThLzp4_3mfF5kEGz-Z8uiMt43g3u5q0xFUwryhUG0s9MtB2N9-5YuFpoyboSVCjYR376Ga1awAh7JexyajWbLOfS992E8viRC9NjveDIwlQyA3Nlf4IW2YR-k7i-XKvYE9gBRn5gySgiDcWUR76fiEiXoQ",
  "tlsClientConfig": {
    "insecure": false,
    "caData": "LS0tLS1CRUdJTiBDRVJUSUZJQ0FURS0tLS0tCk1JSURCVENDQWUyZ0F3SUJBZ0lJS245SWNCV2cwZHN3RFFZSktvWklodmNOQVFFTEJRQXdGVEVUTUJFR0ExVUUKQXhNS2EzVmlaWEp1WlhSbGN6QWVGdzB5TlRFeE1qSXdNakkxTWpGYUZ3MHpOVEV4TWpBd01qTXdNakZhTUJVeApFekFSQmdOVkJBTVRDbXQxWW1WeWJtVjBaWE13Z2dFaU1BMEdDU3FHU0liM0RRRUJBUVVBQTRJQkR3QXdnZ0VLCkFvSUJBUUM5R1gxVERiOVZIRCtsSmR4d0hsOVpkTGYrRURza0NDMWdGMmdPbkxKQ3NyQlhLR0Y1ZjhXZDZxejUKYTg3N1J2US9iazBUZ1pyOFZBdWUzOFM1WEtwVU4wOEFTU0ExRTgvcEtleS9pMHRjYStZY29YWFJSN1pVM0l1ago2SGhxdy9RdU93eDVLMGNDRmd4TVZpSE1kcjNmYzNqVTRpb0ZOUURwN24rbXpyZDBVTTVRR09WVUU3Q0JGeFg1CkpOTWZvQlRxYldLdjlhQVVrZW0vS0dKMisxR2JrU01wUXpnQVREaVJ0ekhxQitQMEV1UEdiSGhyWCs5WkNEMGgKQmpkcmVDSHY1eWQzVWhWbkx4eHhXbFMwNHFTT0hGZTBWdGh4dk9rOFRXeE9zS3c0Q0xqY2ovYjN3SmYwKzNGcApVdXF4ZmkvTEhhcTFsQWNveFV2U0U1T0lUWjNMQWdNQkFBR2pXVEJYTUE0R0ExVWREd0VCL3dRRUF3SUNwREFQCkJnTlZIUk1CQWY4RUJUQURBUUgvTUIwR0ExVWREZ1FXQkJUYkdUMnNvenBWOTdrNS96clpBaXFXdUw2ZWpUQVYKQmdOVkhSRUVEakFNZ2dwcmRXSmxjbTVsZEdWek1BMEdDU3FHU0liM0RRRUJDd1VBQTRJQkFRQWxwbHF3WWQwRwpncTd1ZFMvZmFpWmh0YmprV0gyaDZRWWpqOXg3cXByelp3UmRHMDdvMGVzV0F0ZkF4YmhuaEtZaXVrdDBLN2hQCmtFQVIwcjhGS0d2aStEdmliTzVLSjkrOTB2bkRMQ1haV0FLc2NleG11N0VwNENwWVZ4eFNDZmhYQUZSdUdlanMKVXBTeXp5RnZ4a3VGMEhuSk1heHJmMmJPNERnV21PVlRvSHdwa3ZYQngvUXdSeERlblRHUkZiN0lrTWJhaFJZRgo5aFI4cXExNkJZbTJ0TVhpTzI1NDV3QjQrOEtYNFEzSjQwMkxoZjhTVEM5Y3R6bEw5OHpiL3h1TTV4bndzZDF2CjF2MDlIU1R5eWt6dlhPQXgxYlMxaHFzKzdEaHIrNW9WbTY1dGNpbXhNc24wMHZnSURaQzY3VmZqNTFQYURsNWIKY0JNdk5lS0FSRndMCi0tLS0tRU5EIENFUlRJRklDQVRFLS0tLS0K"
  }
}
name: dev-cluster
server: https://dev-control-plane:6443

##############################################################
# Cluster 등록 확인
##############################################################
argocd cluster list -o json | jq
argocd cluster list 
# SERVER                          NAME         VERSION  STATUS   MESSAGE                                                  PROJECT
# https://dev-control-plane:6443  dev-cluster           Unknown  Cluster has no applications and is not being monitored.  
# https://kubernetes.default.svc  in-cluster            Unknown  Cluster has no applications and is not being monitored.   
```

### 2.4. Prod Cluster 추가

```shell
##############################################################
# register-cluster.sh 파일 수정 아래와 같이 수정 후 실행
##############################################################
# ==========================================
# 1. 환경 변수 설정
# ==========================================
# 대상 클러스터 (Argo CD에 등록될 클러스터 및 주소)
TARGET_CONTEXT="kind-prd"
TARGET_INTERNAL_URL="https://prd-control-plane:6443" # ArgoCD가 접속할 내부 주소
CLUSTER_NAME_IN_ARGO="prd-cluster"

# ArgoCD가 설치된 클러스터
ARGOCD_CONTEXT="kind-mgmt"
ARGOCD_NAMESPACE="argocd"

echo "[${TARGET_CONTEXT}] 클러스터를 [${ARGOCD_CONTEXT}]의 ArgoCD에 등록을 시작합니다..."

##############################################################
# register-cluster.sh 파일 수정 아래와 같이 수정 후 실행
##############################################################
bash register-cluster.sh
# [kind-prd] 클러스터를 [kind-mgmt]의 ArgoCD에 등록을 시작합니다...
# serviceaccount/argocd-manager created
# clusterrole.rbac.authorization.k8s.io/argocd-manager-role created
# clusterrolebinding.rbac.authorization.k8s.io/argocd-manager-role-binding created
# secret/argocd-manager-token created
# ⏳ 토큰 생성을 대기 중...
# secret/cluster-prd-cluster created
# 등록 완료! ArgoCD에서 확인해주세요.

##############################################################
# argocd-manager service account 확인
##############################################################
k8s3 get sa -n kube-system argocd-manager
# NAME             SECRETS   AGE
# argocd-manager   0         2m9s

##############################################################
# ArgoCD에 등록된 클러스터 확인 (Label을 이용하여 필터링)
##############################################################
kubectl get secret -n argocd -l argocd.argoproj.io/secret-type=cluster
# NAME                  TYPE     DATA   AGE
# cluster-dev-cluster   Opaque   3      18m
# cluster-prd-cluster   Opaque   3      116s

##############################################################
# Cluster 등록 확인
##############################################################
argocd cluster list
# SERVER                          NAME         VERSION  STATUS   MESSAGE                                                  PROJECT
# https://dev-control-plane:6443  dev-cluster           Unknown  Cluster has no applications and is not being monitored.
# https://prd-control-plane:6443  prd-cluster           Unknown  Cluster has no applications and is not being monitored.
# https://kubernetes.default.svc  in-cluster            Unknown  Cluster has no applications and is not being monitored.
```

![ArgoCD Cluster Add Check](/assets/img/ci-cd/ci-cd-study/argo-cd-cluster-add-check-dev-prd.webp)

---

## 3. nginx helm chart 생성 후 GitHub에 Push

{% raw %}
```shell
##############################################################
# 디렉토리 생성
##############################################################
mkdir nginx-chart
cd nginx-chart

mkdir templates

##############################################################
# ConfigMap 생성
##############################################################
cat > templates/configmap.yaml <<EOF
apiVersion: v1
kind: ConfigMap
metadata:
  name: {{ .Release.Name }}
data:
  index.html: |
{{ .Values.indexHtml | indent 4 }}
EOF

##############################################################
# Deployment 생성
##############################################################
cat > templates/deployment.yaml <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ .Release.Name }}
spec:
  replicas: {{ .Values.replicaCount }}
  selector:
    matchLabels:
      app: {{ .Release.Name }}
  template:
    metadata:
      labels:
        app: {{ .Release.Name }}
    spec:
      containers:
      - name: nginx
        image: {{ .Values.image.repository }}:{{ .Values.image.tag }}
        ports:
        - containerPort: 80
        volumeMounts:
        - name: index-html
          mountPath: /usr/share/nginx/html/index.html
          subPath: index.html
      volumes:
      - name: index-html
        configMap:
          name: {{ .Release.Name }}
EOF

##############################################################
# Service 생성
##############################################################
cat > templates/service.yaml <<EOF
apiVersion: v1
kind: Service
metadata:
  name: {{ .Release.Name }}
spec:
  selector:
    app: {{ .Release.Name }}
  ports:
  - protocol: TCP
    port: 80
    targetPort: 80
    nodePort: {{ .Values.nodePort }}
  type: NodePort
EOF

##############################################################
# values.yaml 생성 (Mgmt Cluster 용)
##############################################################
cat > values.yaml <<EOF
indexHtml: |
  <!DOCTYPE html>
  <html>
  <head>
    <title>Welcome to Nginx!</title>
  </head>
  <body>
    <h1>Hello, Kubernetes!</h1>
    <p>Nginx version 1.26.1</p>
  </body>
  </html>

image:
  repository: nginx
  tag: 1.26.1

replicaCount: 1

nodePort: 31001
EOF

##############################################################
# values-dev.yaml 생성 (Dev Cluster 용)
##############################################################
cat > values-dev.yaml <<EOF
indexHtml: |
  <!DOCTYPE html>
  <html>
  <head>
    <title>Welcome to Nginx!</title>
  </head>
  <body>
    <h1>Hello, Dev - Kubernetes!</h1>
    <p>Nginx version 1.26.1</p>
  </body>
  </html>

image:
  repository: nginx
  tag: 1.26.1

replicaCount: 1

nodePort: 31002
EOF

##############################################################
# values-prd.yaml 생성 (Prd Cluster 용)
##############################################################
cat > values-prd.yaml <<EOF
indexHtml: |
  <!DOCTYPE html>
  <html>
  <head>
    <title>Welcome to Nginx!</title>
  </head>
  <body>
    <h1>Hello, Prd - Kubernetes!</h1>
    <p>Nginx version 1.26.1</p>
  </body>
  </html>

image:
  repository: nginx
  tag: 1.26.1

replicaCount: 2

nodePort: 31003
EOF

##############################################################
# Chart.yaml 생성
##############################################################
cat > Chart.yaml <<EOF
apiVersion: v2
name: nginx-chart
description: A Helm chart for deploying Nginx with custom index.html
type: application
version: 1.0.0
appVersion: "1.26.1"
EOF

##############################################################
# GitHub Push
##############################################################
git add . && git commit -m "Add sample yaml" && git push -u origin main


##############################################################
# 헬름 렌더링 확인
##############################################################
helm template mgmt-nginx . -f values.yaml
helm template dev-nginx . -f values-dev.yaml
helm template prd-nginx . -f values-prd.yaml
```
{% endraw %}

---

## 4. Argo CD로 3개의 Kubernetes Cluster에 각각 Nginx 배포

```shell

##############################################################
# Cluster IP(FQDN) 변수 설정
##############################################################
DEVK8SIP=dev-control-plane
PRDK8SIP=prd-control-plane
echo $DEVK8SIP $PRDK8SIP

##############################################################
# argocd app 배포
##############################################################
cat <<EOF | kubectl apply -f -
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: mgmt-nginx
  namespace: argocd
  finalizers:
  - resources-finalizer.argocd.argoproj.io
spec:
  project: default
  source:
    helm:
      valueFiles:
      - values.yaml
    path: study/ci-cd-study/6w-3-of-3-argocd/nginx-chart
    repoURL: https://github.com/KKamJi98/kkamji-lab
    targetRevision: HEAD
  syncPolicy:
    automated:
      prune: true
    syncOptions:
    - CreateNamespace=true
  destination:
    namespace: mgmt-nginx
    server: https://kubernetes.default.svc
EOF

cat <<EOF | kubectl apply -f -
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: dev-nginx
  namespace: argocd
  finalizers:
  - resources-finalizer.argocd.argoproj.io
spec:
  project: default
  source:
    helm:
      valueFiles:
      - values-dev.yaml
    path: study/ci-cd-study/6w-3-of-3-argocd/nginx-chart
    repoURL: https://github.com/KKamJi98/kkamji-lab
    targetRevision: HEAD
  syncPolicy:
    automated:
      prune: true
    syncOptions:
    - CreateNamespace=true
  destination:
    namespace: dev-nginx
    server: https://$DEVK8SIP:6443
EOF

cat <<EOF | kubectl apply -f -
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: prd-nginx
  namespace: argocd
  finalizers:
  - resources-finalizer.argocd.argoproj.io
spec:
  project: default
  source:
    helm:
      valueFiles:
      - values-prd.yaml
    path: study/ci-cd-study/6w-3-of-3-argocd/nginx-chart
    repoURL: https://github.com/KKamJi98/kkamji-lab
    targetRevision: HEAD
  syncPolicy:
    automated:
      prune: true
    syncOptions:
    - CreateNamespace=true
  destination:
    namespace: prd-nginx
    server: https://$PRDK8SIP:6443
EOF

##############################################################
# ArgoCD App 확인
##############################################################
argocd app list
# NAME               CLUSTER                         NAMESPACE   PROJECT  STATUS  HEALTH   SYNCPOLICY  CONDITIONS  REPO                                    PATH                                            TARGET
# argocd/dev-nginx   https://dev-control-plane:6443  dev-nginx   default  Synced  Healthy  Auto-Prune  <none>      https://github.com/KKamJi98/kkamji-lab  study/ci-cd-study/6w-3-of-3-argocd/nginx-chart  HEAD
# argocd/mgmt-nginx  https://kubernetes.default.svc  mgmt-nginx  default  Synced  Healthy  Auto-Prune  <none>      https://github.com/KKamJi98/kkamji-lab  study/ci-cd-study/6w-3-of-3-argocd/nginx-chart  HEAD
# argocd/prd-nginx   https://prd-control-plane:6443  prd-nginx   default  Synced  Healthy  Auto-Prune  <none>      https://github.com/KKamJi98/kkamji-lab  study/ci-cd-study/6w-3-of-3-argocd/nginx-chart  HEAD
kubectl get applications -n argocd dev-nginx
kubectl get applications -n argocd dev-nginx -o yaml
kubectl get applications -n argocd dev-nginx -o yaml | kubectl neat | yq
kubectl describe applications -n argocd dev-nginx
kubectl get applications -n argocd
# NAME         SYNC STATUS   HEALTH STATUS
# dev-nginx    Synced        Healthy
# mgmt-nginx   Synced        Healthy
# prd-nginx    Synced        Healthy

##############################################################
# mgmt
##############################################################
kubectl get pod,svc,ep,cm -n mgmt-nginx
curl -s http://127.0.0.1:31001

##############################################################
# dev
##############################################################
kubectl get pod,svc,ep,cm -n dev-nginx --context kind-dev
curl -s http://127.0.0.1:31002

##############################################################
# prd
##############################################################
kubectl get pod,svc,ep,cm -n prd-nginx --context kind-prd
curl -s http://127.0.0.1:31003

##############################################################
# Argo CD App 삭제
##############################################################
kubectl delete applications -n argocd mgmt-nginx dev-nginx prd-nginx
```

---

## 5. 실습 환경 정리

```shell
##############################################################
# kind 클러스터 삭제
##############################################################
kind delete cluster --name mgmt
kind delete cluster --name dev
kind delete cluster --name prd
```

---

## 6. 마무리

이번 포스팅에서는 **Argo CD**를 사용하여 멀티 클러스터 환경을 구축하고 관리하는 방법을 실습해 보았습니다. `kind`를 이용해 로컬에서 관리용(Mgmt), 운영용(Prod), 개발용(Dev) 클러스터를 구성하고, **Argo CD**에 외부 클러스터를 등록하여 중앙에서 애플리케이션을 배포하고 관리하는 과정을 경험했습니다. 이를 통해 **Argo CD**가 단일 클러스터뿐만 아니라 멀티 클러스터 환경에서도 강력한 GitOps 도구로 활용될 수 있음을 확인했습니다.

---

## 7. Reference

- [Argo CD Docs - Cluster Management](https://argo-cd.readthedocs.io/en/stable/operator-manual/cluster-management/)
- [Argo CD Docs - Declarative Setup/Clusters](https://argo-cd.readthedocs.io/en/stable/operator-manual/declarative-setup/#clusters)
- [Argo CD Docs - argocd cluster Command Reference](https://argo-cd.readthedocs.io/en/stable/user-guide/commands/argocd_cluster/)
- [LG유플러스 테크블로그 - 통합 ArgoCD 구축기](https://techblog.uplus.co.kr/%ED%86%B5%ED%95%A9-argocd-%EA%B5%AC%EC%B6%95%EA%B8%B0-3bd300074cb5?gi=1fefa9f04f21)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
