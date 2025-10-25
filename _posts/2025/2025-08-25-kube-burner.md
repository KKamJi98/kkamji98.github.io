---
title: Kube-burner 소개 및 실습 [Cilium Study 7주차]
date: 2025-08-25 00:25:11 +0900
author: kkamji
categories: [Kubernetes]
tags: [kubernetes, devops, cilium, cilium-study, cilium-7w, kube-burner, performance, cloudnet, gasida]
comments: true
image:
  path: /assets/img/kubernetes/kubernetes.webp
---

Cilium은 Kubernetes 내부에서 동작합니다. 따라서 Cilium이 본래의 성능을 내기 위해서는 Kubernetes Cluster 자체의 탄탄한 퍼포먼스 뒷받침되어야 합니다.  

이번 글에서는 Kubernetes Cluster의 Performance를 정량적으로 측정하고 비교 가능한 기준선을 만드는 도구인 `Kube-burner`에 대해 알아보고, 로컬 Kind Kubernetes Cluster에서 해당 툴에 대한 실습내용에 대해 공유하도록 하겠습니다.

> [Kube-burner Docs](https://kube-burner.github.io/kube-burner/v1.17.1/)
> [Kube-burner GitHub](https://github.com/kube-burner/kube-burner)

---

## 1. Kube-burner 소개

Kube-burner는 Kubernetes Performance, Scale Test Orchestration toolset입니다.
Kube-burner가 제공하는 주요 기능은 아래와 같습니다.

- Create, delete, read, and patch Kubernetes resources at scale
- Prometheus metric collection and indexing
- Measurements
- Alerting

---

## 2. 실습 환경 구성

Kube-burner로 부하 테스트를 실행하기 전에, 실습 환경인 Kind Kubernetes Cluster와 Monitoring에 사용되는 아래 구성요소들을 배포하도록 하겠습니다.

### 2.1. Kubernetes Cluster 생성 (Kind)

```shell
########################################################
# kind를 사용해 myk8s Cluster 배포
########################################################
# Prometheus Target connection refused bind-address 설정 : kube-controller-manager , kube-scheduler , etcd , kube-proxy
kind create cluster --name myk8s --image kindest/node:v1.33.2 --config - <<EOF
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
  kubeadmConfigPatches: # Prometheus Target connection refused bind-address 설정
  - |
    kind: ClusterConfiguration
    controllerManager:
      extraArgs:
        bind-address: 0.0.0.0
    etcd:
      local:
        extraArgs:
          listen-metrics-urls: http://0.0.0.0:2381
    scheduler:
      extraArgs:
        bind-address: 0.0.0.0
  - |
    kind: KubeProxyConfiguration
    metricsBindAddress: 0.0.0.0
EOF

kind get clusters
# myk8s

########################################################
# kube-ops-view 설치
########################################################
helm repo add geek-cookbook https://geek-cookbook.github.io/charts/
helm install kube-ops-view geek-cookbook/kube-ops-view --version 1.2.2 --set service.main.type=NodePort,service.main.ports.http.nodePort=30003 --set env.TZ="Asia/Seoul" --namespace kube-system

# 접속 확인
http://localhost:30003/#scale=1.5
http://localhost:30003/#scale=2

########################################################
# metrics-server 설치
########################################################
helm repo add metrics-server https://kubernetes-sigs.github.io/metrics-server/
helm upgrade --install metrics-server metrics-server/metrics-server --set 'args[0]=--kubelet-insecure-tls' -n kube-system

# 확인
kubectl top node
kubectl top pod -A --sort-by='cpu'
kubectl top pod -A --sort-by='memory'
```

---

### 2.2. Kube-Prometheus-Stack 설치

```shell
########################################################
# Kube Prometheus Stack Helm Chart Value 파일 생성
########################################################
cat <<EOT > monitor-values.yaml
prometheus:
  prometheusSpec:
    scrapeInterval: "15s"
    evaluationInterval: "15s"
  service:
    type: NodePort
    nodePort: 30001

grafana:
  defaultDashboardsTimezone: Asia/Seoul
  adminPassword: prom-operator
  service:
    type: NodePort
    nodePort: 30002

alertmanager:
  enabled: false
defaultRules:
  create: false
prometheus-windows-exporter:
  prometheus:
    monitor:
      enabled: false
EOT
cat monitor-values.yaml

########################################################
# Kube Prometheus Stack Helm Chart Repository 추가 및 배포
########################################################
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

# 배포
helm install kube-prometheus-stack prometheus-community/kube-prometheus-stack --version 75.15.1 \
-f monitor-values.yaml --create-namespace --namespace monitoring

########################################################
# Prometheus + Grafana 접속 확인
########################################################
http://127.0.0.1:30001 # prometheus 웹 접속
http://127.0.0.1:30002 # grafana 웹 접속 ( admin , prom-operator )


########################################################
# 대시보드 추가 (15661, 12006)
########################################################
1. K8S Dashboard (15661) 
  link: https://grafana.com/grafana/dashboards/15661-k8s-dashboard-en-20250125/
2. Kubernetes apiserver (12006)
  link: https://grafana.com/grafana/dashboards/12006-kubernetes-apiserver/
```

- K8S Dashboard 확인
![K8S Dashboard](/assets/img/kubernetes/cilium/7w-k8s-dashboard.webp)

- Kubernetes apiserver Dashboard 확인
![Kubernetes apiserver Dashboard](/assets/img/kubernetes/cilium/7w-k8s-apiserver-dashboard.webp)

---

## 3. Kube-burner 설치

```shell
# 바이너리 설치 mac M (arm)
curl -LO https://github.com/kube-burner/kube-burner/releases/download/v1.17.3/kube-burner-V1.17.3-darwin-arm64.tar.gz # mac M
tar -xvf kube-burner-V1.17.3-darwin-arm64.tar.gz

# 바이너리 설치 linux (amd)
curl -LO https://github.com/kube-burner/kube-burner/releases/download/v1.17.3/kube-burner-V1.17.3-linux-x86_64.tar.gz # Windows
tar -xvf kube-burner-V1.17.3-linux-x86_64.tar.gz

sudo cp kube-burner /usr/local/bin

kube-burner -h
  check-alerts Evaluate alerts for the given time range
  completion   Generates completion scripts for bash shell
  destroy      Destroy old namespaces labeled with the given UUID.
  health-check Check for Health Status of the cluster
  help         Help about any command
  import       Import metrics tarball
  index        Index kube-burner metrics
  init         Launch benchmark
  measure      Take measurements for a given set of resources without running workload
  version      Print the version number of kube-burner

# 버전 확인 : 혹은 go run cmd/kube-burner/kube-burner.go -h
kube-burner version
Version: 1.17.3
```

---

## 4. Kube-burner Job Type 정리

| 키                 | 타입     |  기본값 | 설명                                                                                  |
| ------------------ | -------- | ------: | ------------------------------------------------------------------------------------- |
| `jobIterations`    | Integer  |     `0` | 해당 Job을 몇 번 반복 실행할지 지정                                                   |
| `qps`              | Integer  |     `0` | 초당 API 요청 상한치                                                                  |
| `burst`            | Integer  |     `0` | 짧은 구간에서 허용되는 최대 버스트 요청 수                                            |
| `namespace`        | String   |    `""` | 객체가 생성될 기본 네임스페이스 이름. 비어 있으면 `namespace-<iteration>` 형태로 생성 |
| `namespaceLabels`  | Object   |    `{}` | kube-burner가 생성하는 네임스페이스에 추가할 라벨 집합                                |
| `waitWhenFinished` | Boolean  |  `true` | Job 종료 시 객체 준비 완료를 기다릴지 여부                                            |
| `verifyObjects`    | Boolean  |  `true` | 반복별 생성된 객체 수를 검증할지 여부                                                 |
| `preLoadImages`    | Boolean  | `false` | Job 실행 전 DaemonSet으로 이미지 프리로드 수행 여부                                   |
| `preLoadPeriod`    | Duration |    `1m` | 프리로드 대기 시간 설정                                                               |

> [Kube-burner Docs - Jobs](https://kube-burner.github.io/kube-burner/latest/reference/configuration/#jobs)

---

## 5. 실습

### 5.1. 시나리오 1. 디플로이먼트 1개 생성 후 삭제하며 qps·burst 의미 확인

{% raw %}
```shell
########################################################
# s1-config.yaml
########################################################
cat << EOF > s1-config.yaml
global:
  measurements:
    - name: none

jobs:
  - name: create-deployments
    jobType: create
    jobIterations: 1  # How many times to execute the job , 해당 값이 5면 5번 반복 실행
    qps: 1            # Limit object creation queries per second , 	초당 최대 요청 수 (평균 속도 제한) - qps: 10이면 초당 10개 요청
    burst: 1          # Maximum burst for throttle , 순간적으로 처리 가능한 요청 최대치 (버퍼) - burst: 20이면 한순간에 최대 20개까지 처리 가능
    namespace: kube-burner-test
    namespaceLabels: {kube-burner-job: delete-me}
    waitWhenFinished: true # false
    verifyObjects: false
    preLoadImages: true # false
    preLoadPeriod: 30s # default 1m
    objects:
      - objectTemplate: s1-deployment.yaml
        replicas: 1
EOF

########################################################
# s1-deployment.yaml
########################################################
cat << EOF > s1-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: deployment-{{ .Iteration}}-{{.Replica}}
  labels:
    app: test-{{ .Iteration }}-{{.Replica}}
    kube-burner-job: delete-me
spec:
  replicas: 1
  selector:
    matchLabels:
      app: test-{{ .Iteration}}-{{.Replica}}
  template:
    metadata:
      labels:
        app: test-{{ .Iteration}}-{{.Replica}}
    spec:
      containers:
        - name: nginx
          image: nginx:alpine
          ports:
            - containerPort: 80
EOF

########################################################
# 모니터링을 위해 ns, pod 새 터미널에서 실행
########################################################
watch -d 'kubectl get ns,pod -A'

########################################################
# 부하 실행
########################################################
kube-burner init -c s1-config.yaml --log-level debug

########################################################
# 생성 확인
########################################################
kubectl get deploy -A -l kube-burner-job=delete-me
# NAMESPACE            NAME             READY   UP-TO-DATE   AVAILABLE   AGE
# kube-burner-test-0   deployment-0-1   1/1     1            1           4m6s
kubectl get pod -A -l kube-burner-job=delete-me
# NAME                 STATUS   AGE
# kube-burner-test-0   Active   4m12s
kubectl get ns -l kube-burner-job=delete-me
# NAME                 STATUS   AGE
# kube-burner-test-0   Active   5m50s

########################################################
# 로그 확인
########################################################
ls kube-burner-*.log
cat kube-burner-*.log
time="2025-08-26 01:44:53" level=info msg="🔥 Starting kube-burner (1.17.3@917540ff45a89386bb25de45af9b96c9fc360e93) with UUID 52b2e718-ef14-41fc-be48-354dc946faeb" file="job.go:91"
time="2025-08-26 01:44:53" level=warning msg="Measurement [none] is not supported" file="factory.go:101"
time="2025-08-26 01:44:53" level=debug msg="job.MaxWaitTimeout is zero in create-deployments, override by timeout: 4h0m0s" file="job.go:361"
time="2025-08-26 01:44:53" level=info msg="QPS: 1" file="job.go:371"
time="2025-08-26 01:44:53" level=info msg="Burst: 1" file="job.go:378"
time="2025-08-26 01:44:53" level=debug msg="Preparing create job: create-deployments" file="create.go:46"
time="2025-08-26 01:44:53" level=debug msg="Rendering template: s1-deployment.yaml" file="create.go:52"
time="2025-08-26 01:44:53" level=info msg="Job create-deployments: 1 iterations with 1 Deployment replicas" file="create.go:84"
time="2025-08-26 01:44:53" level=info msg="Pre-load: images from job create-deployments" file="pre_load.go:73"
time="2025-08-26 01:44:53" level=debug msg="Created namespace: preload-kube-burner" file="namespaces.go:55"
time="2025-08-26 01:44:53" level=info msg="Pre-load: Creating DaemonSet using images [nginx:alpine] in namespace preload-kube-burner" file="pre_load.go:195"
time="2025-08-26 01:44:53" level=info msg="Pre-load: Sleeping for 30s" file="pre_load.go:86"
time="2025-08-26 01:45:25" level=info msg="Deleting 1 namespaces with label: kube-burner-preload=true" file="namespaces.go:67"
time="2025-08-26 01:45:25" level=debug msg="Waiting for 1 namespaces labeled with kube-burner-preload=true to be deleted" file="namespaces.go:90"
time="2025-08-26 01:45:26" level=debug msg="Waiting for 1 namespaces labeled with kube-burner-preload=true to be deleted" file="namespaces.go:90"
time="2025-08-26 01:45:27" level=debug msg="Waiting for 1 namespaces labeled with kube-burner-preload=true to be deleted" file="namespaces.go:90"
time="2025-08-26 01:45:28" level=debug msg="Waiting for 1 namespaces labeled with kube-burner-preload=true to be deleted" file="namespaces.go:90"
time="2025-08-26 01:45:29" level=debug msg="Waiting for 1 namespaces labeled with kube-burner-preload=true to be deleted" file="namespaces.go:90"
time="2025-08-26 01:45:30" level=debug msg="Waiting for 1 namespaces labeled with kube-burner-preload=true to be deleted" file="namespaces.go:90"
time="2025-08-26 01:45:31" level=info msg="Triggering job: create-deployments" file="job.go:122"
time="2025-08-26 01:45:31" level=info msg="0/1 iterations completed" file="create.go:119"
time="2025-08-26 01:45:31" level=debug msg="Creating object replicas from iteration 0" file="create.go:122"
time="2025-08-26 01:45:32" level=debug msg="Created namespace: kube-burner-test-0" file="namespaces.go:55"
time="2025-08-26 01:45:32" level=debug msg="Created Deployment/deployment-0-1 in namespace kube-burner-test-0" file="create.go:288"
time="2025-08-26 01:45:32" level=info msg="Waiting up to 4h0m0s for actions to be completed" file="create.go:169"
time="2025-08-26 01:45:33" level=debug msg="Waiting for replicas from Deployment in ns kube-burner-test-0 to be ready" file="waiters.go:152"
time="2025-08-26 01:45:34" level=info msg="Actions in namespace kube-burner-test-0 completed" file="waiters.go:74"
time="2025-08-26 01:45:34" level=info msg="Job create-deployments took 3s" file="job.go:191"
time="2025-08-26 01:45:34" level=info msg="Finished execution with UUID: 52b2e718-ef14-41fc-be48-354dc946faeb" file="job.go:264"
time="2025-08-26 01:45:34" level=info msg="👋 Exiting kube-burner 52b2e718-ef14-41fc-be48-354dc946faeb" file="kube-burner.go:90"

########################################################
# 삭제
########################################################
## deployment 는 s1-deployment.yaml 에 metadata.labels 에 추가한 labels 로 지정
## namespace 는 config.yaml 에 job.name 값을 labels 로 지정
cat << EOF > s1-config-delete.yaml
# global:
#   measurements:
#     - name: none

jobs:
  - name: delete-deployments-namespace
    qps: 500
    burst: 500
    namespace: kube-burner-test
    jobType: delete
    waitWhenFinished: true
    objects:
    - kind: Deployment
      labelSelector: {kube-burner-job: delete-me}
      apiVersion: apps/v1
    - kind: Namespace
      labelSelector: {kube-burner-job: delete-me}
EOF

kube-burner init -c s1-config-delete.yaml --log-level debug
```
{% endraw %}

### 5.2. 시나리오 2. 노드 1대에 pod 100개 배포 시도 (max_pods limit보다 더 많은 pod 생성)

위에서 사용한 `s1-config.yaml` 파일의 설정을 아래와 같이 변경 후 실행 (max_pods limit 보다 더 많은 pod를 생성하도록)

- `jobIterations: 100`
- `qps: 300`
- `burst: 300`
- `objects.replicas: 1`

{% raw %}
```shell
########################################################
# s1-config.yaml
########################################################
cat << EOF > s1-config.yaml
global:
  measurements:
    - name: none

jobs:
  - name: create-deployments
    jobType: create
    jobIterations: 100  # How many times to execute the job
    qps: 300            # Limit object creation queries per second
    burst: 300          # Maximum burst for throttle
    namespace: kube-burner-test
    namespaceLabels: {kube-burner-job: delete-me}
    waitWhenFinished: true # false
    verifyObjects: false
    preLoadImages: true # false
    preLoadPeriod: 30s # default 1m
    objects:
      - objectTemplate: s1-deployment.yaml
        replicas: 1
EOF

########################################################
# s1-deployment.yaml
########################################################
cat << EOF > s1-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: deployment-{{ .Iteration}}-{{.Replica}}
  labels:
    app: test-{{ .Iteration }}-{{.Replica}}
    kube-burner-job: delete-me
spec:
  replicas: 1
  selector:
    matchLabels:
      app: test-{{ .Iteration}}-{{.Replica}}
  template:
    metadata:
      labels:
        app: test-{{ .Iteration}}-{{.Replica}}
    spec:
      containers:
        - name: nginx
          image: nginx:alpine
          ports:
            - containerPort: 80
EOF

########################################################
# 모니터링을 위해 ns, pod 새 터미널에서 실행
########################################################
watch -d 'kubectl get ns,pod -A'
watch -d 'kubectl get pod -A | grep -v " Running"'

########################################################
# 부하 실행 (문제 발생 max_pods limit)
########################################################
kube-burner init -c s1-config.yaml --log-level debug
...
time="2025-08-26 02:25:54" level=debug msg="Waiting for replicas from Deployment in ns kube-burner-test-96 to be ready" file="waiters.go:152"
time="2025-08-26 02:25:55" level=debug msg="Waiting for replicas from Deployment in ns kube-burner-test-99 to be ready" file="waiters.go:152"
time="2025-08-26 02:25:55" level=debug msg="Waiting for replicas from Deployment in ns kube-burner-test-94 to be ready" file="waiters.go:152"
time="2025-08-26 02:25:55" level=debug msg="Waiting for replicas from Deployment in ns kube-burner-test-96 to be ready" file="waiters.go:152"
time="2025-08-26 02:25:55" level=debug msg="Waiting for replicas from Deployment in ns kube-burner-test-98 to be ready" file="waiters.go:152"
time="2025-08-26 02:25:55" level=debug msg="Waiting for replicas from Deployment in ns kube-burner-test-95 to be ready" file="waiters.go:152"
time="2025-08-26 02:25:55" level=debug msg="Waiting for replicas from Deployment in ns kube-burner-test-97 to be ready" file="waiters.go:152"

########################################################
# Pending pod 확인 
########################################################
watch -d 'kubectl get pod -A | grep -v " Running"' # 해당 터미널
# NAMESPACE             NAME                                                        READY   STATUS    RESTARTS   AGE
# kube-burner-test-94   deployment-94-1-77c4dd5748-gbnmx                            0/1     Pending   0          6m25s
# kube-burner-test-95   deployment-95-1-8648f64d9d-mtsnw                            0/1     Pending   0          6m25s
# kube-burner-test-96   deployment-96-1-775c7ccb4d-xxrdw                            0/1     Pending   0          6m25s
# kube-burner-test-97   deployment-97-1-b6d9d8874-kh2bn                             0/1     Pending   0          6m24s
# kube-burner-test-98   deployment-98-1-6c577b4588-55bjr                            0/1     Pending   0          6m24s
# kube-burner-test-99   deployment-99-1-b6f7fccd-jz4b6                              0/1     Pending   0          6m24s

########################################################
# 이벤트 확인
########################################################
kubectl describe pod -n kube-burner-test-99 | grep Events: -A5
# Events:
#   Type     Reason            Age   From               Message
#   ----     ------            ----  ----               -------
#   Warning  FailedScheduling  57s   default-scheduler  0/1 nodes are available: 1 Too many pods. preemption: 0/1 nodes are available: 1 No preemption victims found for incoming pod.

########################################################
# max_pods limit 확인
########################################################
kubectl describe node | grep Capacity -A13
# Capacity:
#   cpu:                4
#   ephemeral-storage:  1055762868Ki
#   hugepages-1Gi:      0
#   hugepages-2Mi:      0
#   memory:             12250356Ki
#   pods:               110
# Allocatable:
#   cpu:                4
#   ephemeral-storage:  1055762868Ki
#   hugepages-1Gi:      0
#   hugepages-2Mi:      0
#   memory:             12250356Ki
#   pods:               110

########################################################
# 현재 pod 개수 확인
########################################################
kubectl get pod -A --no-headers | wc -l
116
```
{% endraw %}

![Grafana Dashboard Pod Number and Nodes](/assets/img/kubernetes/cilium/7w-grafana-110-pod-limit.webp)

#### 5.2.1. 해결 (max_pods limit 증가)

위에서 max_pods limit이 110에 걸려 6개의 pod가 Pending 상태임을 확인했습니다. max_pods limit을 증가 시켜 위의 문제를 해결해보겠습니다.

{% raw %}
```shell
########################################################
# Kind Kubernetes Cluster의 Control Plane Shell 접근
########################################################
docker exec -it myk8s-control-plane bash

########################################################
# kubelet config 확인 (maxPods 설정이 없으면 default 값으로 100 적용)
########################################################
cat /var/lib/kubelet/config.yaml | grep maxPods

########################################################
# maxPods 설정을 통해 limit 향상
########################################################
apt update && apt install vim -y
vim /var/lib/kubelet/config.yaml

## 추가
maxPods: 150

########################################################
# kubelet 재시작
########################################################
systemctl restart kubelet
systemctl status kubelet
exit


########################################################
# maxPods 설정 확인 (110 -> 150)
########################################################
kubectl describe node | grep Capacity -A13
# Capacity:
#   cpu:                4
#   ephemeral-storage:  1055762868Ki
#   hugepages-1Gi:      0
#   hugepages-2Mi:      0
#   memory:             12250356Ki
#   pods:               150
# Allocatable:
#   cpu:                4
#   ephemeral-storage:  1055762868Ki
#   hugepages-1Gi:      0
#   hugepages-2Mi:      0
#   memory:             12250356Ki
#   pods:               150

########################################################
# Pending Pod 존재 확인
########################################################
kubectl get pod -A --no-headers | grep -v " Running" | wc -l
# 0

########################################################
# Running Pod 개수 확인
########################################################
kubectl get pod -A --no-headers | grep " Running" | wc -l
# 116

########################################################
# 삭제
########################################################
## deployment 는 s1-deployment.yaml 에 metadata.labels 에 추가한 labels 로 지정
## namespace 는 config.yaml 에 job.name 값을 labels 로 지정
cat << EOF > s1-config-delete.yaml
# global:
#   measurements:
#     - name: none

jobs:
  - name: delete-deployments-namespace
    qps: 500
    burst: 500
    namespace: kube-burner-test
    jobType: delete
    waitWhenFinished: true
    objects:
    - kind: Deployment
      labelSelector: {kube-burner-job: delete-me}
      apiVersion: apps/v1
    - kind: Namespace
      labelSelector: {kube-burner-job: delete-me}
EOF

kube-burner init -c s1-config-delete.yaml --log-level debug
```
{% endraw %}

### 5.3. 시나리오 3. 노드 1대에 pod 300개 배포 시도 (PodCIDR 사이즈보다 많은 pod 생성)

위에서 사용한 `s1-config.yaml` 파일의 설정을 아래와 같이 변경 후 실행 (부하가 많이 들어가도록)

- `jobIterations: 300`
- `qps: 300`
- `burst: 300`
- `objects.replicas: 1`

{% raw %}
```shell
########################################################
# s1-config.yaml
########################################################
cat << EOF > s1-config.yaml
global:
  measurements:
    - name: none

jobs:
  - name: create-deployments
    jobType: create
    jobIterations: 300  # How many times to execute the job
    qps: 300            # Limit object creation queries per second
    burst: 300          # Maximum burst for throttle
    namespace: kube-burner-test
    namespaceLabels: {kube-burner-job: delete-me}
    waitWhenFinished: true # false
    verifyObjects: false
    preLoadImages: true # false
    preLoadPeriod: 30s # default 1m
    objects:
      - objectTemplate: s1-deployment.yaml
        replicas: 1
EOF

########################################################
# s1-deployment.yaml
########################################################
cat << EOF > s1-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: deployment-{{ .Iteration}}-{{.Replica}}
  labels:
    app: test-{{ .Iteration }}-{{.Replica}}
    kube-burner-job: delete-me
spec:
  replicas: 1
  selector:
    matchLabels:
      app: test-{{ .Iteration}}-{{.Replica}}
  template:
    metadata:
      labels:
        app: test-{{ .Iteration}}-{{.Replica}}
    spec:
      containers:
        - name: nginx
          image: nginx:alpine
          ports:
            - containerPort: 80
EOF

########################################################
# 모니터링을 위해 ns, pod 새 터미널에서 실행
########################################################
watch -d 'kubectl get ns,pod -A'
watch -d 'kubectl get pod -A | grep -v " Running"'

########################################################
# Kind Kubernetes Cluster의 Control Plane Shell 접근
########################################################
docker exec -it myk8s-control-plane bash

########################################################
# kubelet config 확인 (maxPods 설정이 없으면 default 값으로 100 적용)
########################################################
cat /var/lib/kubelet/config.yaml | grep maxPods

########################################################
# maxPods 설정을 통해 limit 향상 (400)
########################################################
apt update && apt install vim -y
vim /var/lib/kubelet/config.yaml

## 추가
maxPods: 400

########################################################
# kubelet 재시작
########################################################
systemctl restart kubelet
systemctl status kubelet
exit


########################################################
# maxPods 설정 확인 (400)
########################################################
kubectl describe node | grep Capacity -A13
# Capacity:
#   cpu:                4
#   ephemeral-storage:  1055762868Ki
#   hugepages-1Gi:      0
#   hugepages-2Mi:      0
#   memory:             12250356Ki
#   pods:               400
# Allocatable:
#   cpu:                4
#   ephemeral-storage:  1055762868Ki
#   hugepages-1Gi:      0
#   hugepages-2Mi:      0
#   memory:             12250356Ki
#   pods:               400

########################################################
# 부하 실행 (문제 발생 PodCIDR 초과)
########################################################
kube-burner init -c s1-config.yaml --log-level debug

########################################################
# Pending pod 확인 
########################################################
watch -d 'kubectl get pod -A | grep -v " Running"' # 해당 터미널
NAMESPACE              NAME                                                        READY   STATUS              RESTARTS   AGE
kube-burner-test-235   deployment-235-1-75d767bcdf-t5hdv                           0/1     ContainerCreating   0          3m49s
kube-burner-test-236   deployment-236-1-66d877bd57-nvqj2                           0/1     ContainerCreating   0          3m49s
kube-burner-test-237   deployment-237-1-65f747f57c-zthvs                           0/1     ContainerCreating   0          3m49s
kube-burner-test-238   deployment-238-1-897f6c6b9-ffgn6                            0/1     ContainerCreating   0          3m48s
kube-burner-test-240   deployment-240-1-d44bcd9b5-gblmb                            0/1     ContainerCreating   0          3m48s
...

########################################################
# 이벤트 확인
########################################################
kubectl describe pod -n kube-burner-test-299 | grep Events: -A5
# Events:
#   Type     Reason                  Age   From               Message
#   ----     ------                  ----  ----               -------
#   Normal   Scheduled               3m2s  default-scheduler  Successfully assigned kube-burner-test-299/deployment-299-1-55c9c9d7c7-bdsj4 to myk8s-control-plane
#   Warning  FailedCreatePodSandBox  59s   kubelet            Failed to create pod sandbox: rpc error: code = Unknown desc = failed to setup network for sandbox "489d15778ddab9adc6195a13476da3ab3dfdb36beb13f3c090177106ed7f8482": plugin type="ptp" failed (add): failed to allocate for range 0: no IP addresses available in range set: 10.244.0.1-10.244.0.254
#   Warning  FailedCreatePodSandBox  44s   kubelet            Failed to create pod sandbox: rpc error: code = Unknown desc = failed to setup network for sandbox "dfd0bd687e074e805ff246c0f0ed45a22164b361e52e14bd551c21d3288ac711": plugin type="ptp" failed (add): failed to allocate for range 0: no IP addresses available in range set: 10.244.0.1-10.244.0.254

########################################################
# PodCIDR 확인 (254개)
########################################################
kubectl describe node myk8s-control-plane | grep -i podcidr

PodCIDR:                      10.244.0.0/24
PodCIDRs:                     10.244.0.0/24

########################################################
# pod Status 별 개수 확인 
########################################################
kubectl get pod -A -o jsonpath='{range .items[*]}{.status.phase}{"\n"}{end}' | sort | uniq -c

    #  56 Pending
    # 260 Running

########################################################
# hostNetwork를 사용하는 Pod 확인
########################################################
kubectl get pods -A -o jsonpath='{range .items[?(@.spec.hostNetwork==true)]}{.metadata.namespace}{"\t"}{.metadata.name}{"\n"}{end}'
# kube-system     etcd-myk8s-control-plane
# kube-system     kindnet-bz85p
# kube-system     kube-apiserver-myk8s-control-plane
# kube-system     kube-controller-manager-myk8s-control-plane
# kube-system     kube-proxy-vfbn7
# kube-system     kube-scheduler-myk8s-control-plane
# monitoring      kube-prometheus-stack-prometheus-node-exporter-kznm9

kubectl get pods -A -o jsonpath='{range .items[?(@.spec.hostNetwork==true)]}{.metadata.namespace}{"\t"}{.metadata.name}{"\n"}{end}' | wc -l
# 7

########################################################
# 삭제
########################################################
## deployment 는 s1-deployment.yaml 에 metadata.labels 에 추가한 labels 로 지정
## namespace 는 config.yaml 에 job.name 값을 labels 로 지정
cat << EOF > s1-config-delete.yaml
# global:
#   measurements:
#     - name: none

jobs:
  - name: delete-deployments-namespace
    qps: 500
    burst: 500
    namespace: kube-burner-test
    jobType: delete
    waitWhenFinished: true
    objects:
    - kind: Deployment
      labelSelector: {kube-burner-job: delete-me}
      apiVersion: apps/v1
    - kind: Namespace
      labelSelector: {kube-burner-job: delete-me}
EOF

kube-burner init -c s1-config-delete.yaml --log-level debug
```

> /24 대역에서 위 3개는 할당 불가이므로 사용 가능한 Pod IP는 253개입니다. (hostNetwork 파드는 이 계산에서 제외)  
> - 10.244.0.0  (첫 번째 주소: /24 네트워크의 네트워크 주소. 라우팅 식별용)
> - 10.244.0.1  (두 번째 주소: CNI Bridge Gateway가 사용하는 주소)
> - 10.244.0.255 (마지막 주소: /24의 브로드캐스트 주소)
{: .prompt-tip}

---

## 6. 마무리

`Kube-burner`로 단시간에 1개, 150개, 300개의 Pod를 생성해 클러스터에 부하를 가해 보았습니다. 그 과정에서 단일 노드 환경에서는 `maxPods` 상한과 PodCIDR 크기가 병목이 되어 일부 파드가 `Pending`에 머무를 수 있음을 확인했습니다.

---

## 7. Reference

- [Kube-burner Docs](https://kube-burner.github.io/kube-burner/v1.17.1/)
- [Kube-burner GitHub](https://github.com/kube-burner/kube-burner)
- [Kube-burner Docs - Jobs](https://kube-burner.github.io/kube-burner/latest/reference/configuration/#jobs)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
