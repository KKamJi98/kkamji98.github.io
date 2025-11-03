---
title: Jenkins CD with Kubernetes
date: 2025-10-29 01:30:31 +0900
author: kkamji
categories: [DevOps]
tags: [devops, ci-cd-study, ci-cd-study-3w, jenkins, gogs, kind, docker, jenkins-cd, blue-green]
comments: true
image:
  path: /assets/img/ci-cd/ci-cd-study/ci-cd-study.webp
---

`CloudNet@` Gasida님이 진행하는 `CI/CD + ArgoCD + Vault Study` 를 진행하며 학습한 내용을 공유합니다.

이번 포스트에서는 **Jenkins 를 사용한 CD**(Continuous Delivery)과정에 대해 실습 중심으로 정리하겠습니다.

실습 환경은 [Jenkins + ArgoCD 실습 환경 구축]({% post_url 2025/2025-10-26-jenkins-ci-cd-env-3w %}) 의 실습환경을 사용합니다.

---

## 1. Jenkins 컨테이너 내부에 툴 설치 (kubectl, helm)

```shell
##############################################################
# Jenkins Container 쉘 접근 (docker-compose.yaml 파일이 위치한 경로에서)
##############################################################
docker compose exec --privileged -u root jenkins bash
--------------------------------------------

##############################################################
# Install kubectl, helm
##############################################################
# kubectl download
#curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/arm64/kubectl"  # macOS
#curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"  # Windows
curl -LO "https://dl.k8s.io/release/v1.32.8/bin/linux/arm64/kubectl"  # macOS
curl -LO "https://dl.k8s.io/release/v1.32.8/bin/linux/amd64/kubectl"  # Windows

install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
kubectl version --client=true

#
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
helm version

exit
--------------------------------------------
docker compose exec jenkins kubectl version --client=true
docker compose exec jenkins helm version
```

---

## 2. Jenkins 자격 증명 설정 (k8s-crd)

### 2.1. myk8s-control-plane 컨테이너 IP 확인

```shell
# myk8s-control-plane 컨테이너 (api-server) IP 확인
docker inspect myk8s-control-plane | grep IPAddress
# "IPAddress": "172.18.0.3",

# Jenkins 컨테이너에서 myk8s-control-plane api 호출 확인
docker exec -it jenkins curl https://172.18.0.3:6443/version -k  
# {
#   "major": "1",
#   "minor": "32",
#   "gitVersion": "v1.32.8",
#   "gitCommit": "2e83bc4bf31e88b7de81d5341939d5ce2460f46f",
#   "gitTreeState": "clean",
#   "buildDate": "2025-08-13T14:21:22Z",
#   "goVersion": "go1.23.11",
#   "compiler": "gc",
#   "platform": "linux/amd64"
# }
```

### 2.2. Kind Kubernetes 자격증명 설정 (k8s-crd)

- 자격증명 설정 : Jenkins 관리 -> Credentials -> System -> Globals -> Add Credentials

#### 2.2.1. kubeconfig 파일 수정

```shell
cp ~/.kube/config .

## 현재 클러스터의 ip 내용을 아래와 같이 수정
apiVersion: v1
clusters:
- cluster:
    certificate-authority-data: LS0tLS1CRUdJTiBDRVJUSUZJQ0FURS0tLS0tCk1JSURCVENDQWUyZ0F3SUJBZ0lJQTdOSnBqU3NlRm93RFFZSktvWklodmNOQVFFTEJRQXdGVEVUTUJFR0ExVUUKQXhNS2EzVmlaWEp1WlhSbGN6QWVGdzB5TlRFd01qVXdPVEUyTlRGYUZ3MHpOVEV3TWpNd09USXhOVEZhTUJVeApFekFSQmdOVkJBTVRDbXQxWW1WeWJtVjBaWE13Z2dFaU1BMEdDU3FHU0liM0RRRUJBUVVBQTRJQkR3QXdnZ0VLCkFvSUJBUURTOEcyMDVUeXQzYm1jMGtKQmtWMjMvdmV3VWp2MFlCb29yeDNhVk00UUtXdzVuWDVZOHFVSmNSa2IKUkJSc2dYaGRTWXU1RkpOblFlcE1xcEVRZjQwQXErSlZGanF4RElSL2xVejUrSWRyU2lpQ1NicGZPbHB5OU51NQoxTGNWY3JzY2VaMkpMUEovRjNIcGZPR2FROTczRXRUR3pTYkhIUVNlN0RDazBzZEN2d0xLMFQ4S1pvb240dTIrCnpsTG5BalIwcUFhTkFyWWtRdUVNaUpBb1BSMW94Sjd0TnZEaXhYNlF6R2RKOEZWYkRFQkFTUmlYcysrdzZMOVMKSzhJRTZnN2k4ZXFmSHVFM3ZWUG0xRmt3enFxcURyTXB6dEFLV2JQYlhzZEt0VERWQTdsUHdNRXNNWUF1eFpDVwpIRkFjUDRLYkZyRGNxVlY1V0ppVWRLRXdjcDU5QWdNQkFBR2pXVEJYTUE0R0ExVWREd0VCL3dRRUF3SUNwREFQCkJnTlZIUk1CQWY4RUJUQURBUUgvTUIwR0ExVWREZ1FXQkJRVDNvMkJKUHFLYXJlMmJoVVRqYTFtOWxNSDlUQVYKQmdOVkhSRUVEakFNZ2dwcmRXSmxjbTVsZEdWek1BMEdDU3FHU0liM0RRRUJDd1VBQTRJQkFRQW9nMEN0ZlgzSwpzU0pIblo3Vkgvai9CUnNCUEY2Z1hieUtJTEtNeU8vblgxejF1UEJGbklPZ0QvME4zUnJiVStYVVRQc2djTGgrCjZMY0xJSUhmNWpzRlRkL0prVDI0VXZkVzRxcnZqSWRWYU5GbS9Gcm91YkFoU1Y0UEhSMHFBaCtWODY5U1llMisKMHBUL1REVDkwNklqRzVGb2NhZlFBZkVrWUVQNEptMXhXdloxVXNFNlp3ZVVWNVUvUzZNWmVDZC9UZU1SQ0cybApwMTVLNEVWTGdlVGwzK1dCUENBYnBIK0hTa0grdi96OFY2byszYmlrMFdKOVBJZGZuUjZXeENMRDhnaTFzNGZICnpiMm9iYmt0SnlsZEpUUGNyU0wwUGhZMml3ZWtad3R3WWFJNk84aytRckdnUW5PNGp4Q0VUWVN6OVc5ekdoWGcKVW9lU09mdXBGM0hZCi0tLS0tRU5EIENFUlRJRklDQVRFLS0tLS0K
    server: https://<myk8s-control-plane 컨테이너 IP>:6443 # 자신의 환경에 맞게 변경
```

#### 2.2.2. 수정한 kubeconfig 파일로 secret 생성

- Kind : **Secret file**
- File : ***<kubeconfig 파일 업로드>***
- **ID** : **k8s-crd**

![Jenkins Kind Kubeconfig Setup](/assets/img/ci-cd/ci-cd-study/jenkins-kind-kubeconfig-setup.webp)

---

## 3. Jenkins Item 생성(Pipeline)

> Item name(k8s-cmd) -> 아래의 Pipeline script 입력 후 Item 생성 -> Save -> 지금 빌드
{: .prompt-tip}

```shell
## Pipeline script 내용
pipeline {
    agent any
    environment {
        KUBECONFIG = credentials('k8s-crd')
    }
    stages {
        stage('List Pods') {
            steps {
                sh '''
                # Fetch and display Pods
                kubectl get pods -A --kubeconfig "$KUBECONFIG"
                '''
            }
        }
    }
}
```

### 3.1. Console Output 확인

![Jenkins k8s-cmd Console Output](/assets/img/ci-cd/ci-cd-study/jenkins-k8s-cmd-console-output.webp)

---

## 4. Jenkins 를 이용한 blue-green 배포 준비

### 4.1. 이전 실습에 사용된 deployment, service가 남아있는 경우 삭제

```shell
kubectl delete deploy,svc timeserver
```

### 4.2. Deployment, Service YAML 파일 작성 - [http-echo](https://hub.docker.com/r/hashicorp/http-echo) 및 코드 push

```shell
##############################################################
# Gogs Container 쉘 접근 (docker-compose.yaml 파일이 위치한 경로에서)
##############################################################
docker compose exec --privileged -u root gogs bash
--------------------------------------------

##############################################################
# Deployment, Service Yaml 파일 작성 후 코드 git push
##############################################################
# dev-app 디렉토리 접근
cd /data/dev-app/

# deploy 폴더 생성
mkdir deploy

# Deployment Manifest 생성 (Blue)
cat > deploy/echo-server-blue.yaml <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: echo-server-blue
spec:
  replicas: 2
  selector:
    matchLabels:
      app: echo-server
      version: blue
  template:
    metadata:
      labels:
        app: echo-server
        version: blue
    spec:
      containers:
      - name: echo-server
        image: hashicorp/http-echo
        args:
        - "-text=Hello from Blue"
        ports:
        - containerPort: 5678
EOF

# Service Manifest 생성
cat > deploy/echo-server-service.yaml <<EOF
apiVersion: v1
kind: Service
metadata:
  name: echo-server-service
spec:
  selector:
    app: echo-server
    version: blue
  ports:
  - protocol: TCP
    port: 80
    targetPort: 5678
    nodePort: 30000
  type: NodePort
EOF

# Deployment Manifest 생성 (Green)
cat > deploy/echo-server-green.yaml <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: echo-server-green
spec:
  replicas: 2
  selector:
    matchLabels:
      app: echo-server
      version: green
  template:
    metadata:
      labels:
        app: echo-server
        version: green
    spec:
      containers:
      - name: echo-server
        image: hashicorp/http-echo
        args:
        - "-text=Hello from Green"
        ports:
        - containerPort: 5678
EOF

# 확인 후 git(gogs) push
tree
git add . && git commit -m "Add echo server yaml" && git push -u origin main

## 쉘 탈출
exit
```

### 4.3. 참고 - 직접 블루-그린 업데이트 실행 시 절차 (수동)

현재 `gogs` 컨테이너에 `kubeconfig`와 `kubectl` 설정이 되어있지 않아, 아래 내용은 진행이 어려우나, 설정이 되어있는 경우 아래와 같이 수동으로 `blue-green` 업데이트도 할 수 있습니다.

```shell
#
cd deploy
kubectl delete deploy,svc --all
kubectl apply -f .

#
kubectl get deploy,svc,ep -owide
curl -s http://127.0.0.1:30000

#
kubectl patch svc echo-server-service -p '{"spec": {"selector": {"version": "green"}}}'
kubectl get deploy,svc,ep -owide
curl -s http://127.0.0.1:30000

#
kubectl patch svc echo-server-service -p '{"spec": {"selector": {"version": "blue"}}}'
kubectl get deploy,svc,ep -owide
curl -s http://127.0.0.1:30000

# 삭제
kubectl delete -f .
cd ..
```

---

## 5. Jenkins blue-green 배포 Item 생성(Pipeline)

> Item name(k8s-bluegreen) -> 아래의 Pipeline script 입력 후 Item 생성 -> Save
{: .prompt-tip}

### 5.1. Pipeline Script (Blue-Green)

```shell
pipeline {
    agent any

    environment {
        KUBECONFIG = credentials('k8s-crd')
    }

    stages {
        stage('Checkout') {
            steps {
                git branch: 'main',
                    credentialsId: 'gogs-crd',
                    url: 'http://172.28.8.232:3000/devops/dev-app.git'  // Git에서 코드 체크아웃
            }
        }

        stage('container image build') {
            steps {
                echo "container image build"
            }
        }

        stage('container image upload') {
            steps {
                echo "container image upload"
            }
        }

        stage('k8s deployment blue version') {
            steps {
                sh "kubectl apply -f ./deploy/echo-server-blue.yaml --kubeconfig $KUBECONFIG"
                sh "kubectl apply -f ./deploy/echo-server-service.yaml --kubeconfig $KUBECONFIG"
            }
        }

        stage('approve green version') {
            steps {
                input message: 'approve green version', ok: "Yes"
            }
        }

        stage('k8s deployment green version') {
            steps {
                sh "kubectl apply -f ./deploy/echo-server-green.yaml --kubeconfig $KUBECONFIG"
            }
        }

        stage('approve version switching') {
            steps {
                script {
                    def switchApproved = input message: 'Green switching?', ok: "Yes", parameters: [booleanParam(defaultValue: true, name: 'IS_SWITCHED')]
                    if (switchApproved) {
                        sh "kubectl patch svc echo-server-service -p '{\"spec\": {\"selector\": {\"version\": \"green\"}}}' --kubeconfig $KUBECONFIG"
                    }
                }
            }
        }

        stage('Blue Rollback') {
            steps {
                script {
                    def rollbackDecision = input message: 'Blue Rollback?', parameters: [choice(choices: ['done', 'rollback'], name: 'IS_ROLLBACK')]
                    if (rollbackDecision == "done") {
                        sh "kubectl delete -f ./deploy/echo-server-blue.yaml --kubeconfig $KUBECONFIG"
                    }
                    if (rollbackDecision == "rollback") {
                        sh "kubectl patch svc echo-server-service -p '{\"spec\": {\"selector\": {\"version\": \"blue\"}}}' --kubeconfig $KUBECONFIG"
                    }
                }
            }
        }
    }
}
```

---

## 6. Jenkins blue-green 배포

### 6.1. blue green 전환 확인을 위한 반복 접속 요청 (다른 터미널)

```shell
while true; do curl -s --connect-timeout 1 http://127.0.0.1:30000 ; echo ; sleep 1  ; kubectl get deploy -owide ; echo ; kubectl get svc,ep echo-server-service -owide ; echo "------------" ; done
# Or
while true; do curl -s --connect-timeout 1 http://127.0.0.1:30000 ; date ; echo "------------" ; sleep 1 ; done
```

### 6.2. Pipeline 실행 (Blue-Green)

위에서 생성한 Pipeline 즉시 실행 클릭

#### 6.2.1. Blue 배포 확인

![Jenkins Blue Green Deploy - Blue](/assets/img/ci-cd/ci-cd-study/jenkins-blue-green-deploy-blue.webp)

```shell
Hello from Blue

NAME               READY   UP-TO-DATE   AVAILABLE   AGE   CONTAINERS    IMAGES                SELECTOR
echo-server-blue   2/2     2            2           19s   echo-server   hashicorp/http-echo   app=echo-server,version=blue

NAME                          TYPE       CLUSTER-IP     EXTERNAL-IP   PORT(S)        AGE   SELECTOR
service/echo-server-service   NodePort   10.96.85.241   <none>        80:30000/TCP   14m   app=echo-server,version=blue

NAME                            ENDPOINTS                          AGE
endpoints/echo-server-service   10.244.1.10:5678,10.244.1.9:5678   14m
------------
Hello from Blue

NAME               READY   UP-TO-DATE   AVAILABLE   AGE   CONTAINERS    IMAGES                SELECTOR
echo-server-blue   2/2     2            2           20s   echo-server   hashicorp/http-echo   app=echo-server,version=blue

NAME                          TYPE       CLUSTER-IP     EXTERNAL-IP   PORT(S)        AGE   SELECTOR
service/echo-server-service   NodePort   10.96.85.241   <none>        80:30000/TCP   14m   app=echo-server,version=blue

NAME                            ENDPOINTS                          AGE
endpoints/echo-server-service   10.244.1.10:5678,10.244.1.9:5678   14m
```

#### 6.2.2. Green 배포 확인

![Jenkins Blue Green Deploy - Green](/assets/img/ci-cd/ci-cd-study/jenkins-blue-green-deploy-green.webp)

```shell
Hello from Blue

NAME                READY   UP-TO-DATE   AVAILABLE   AGE   CONTAINERS    IMAGES                SELECTOR
echo-server-blue    2/2     2            2           49s   echo-server   hashicorp/http-echo   app=echo-server,version=blue
echo-server-green   2/2     2            2           5s    echo-server   hashicorp/http-echo   app=echo-server,version=green

NAME                          TYPE       CLUSTER-IP     EXTERNAL-IP   PORT(S)        AGE   SELECTOR
service/echo-server-service   NodePort   10.96.85.241   <none>        80:30000/TCP   14m   app=echo-server,version=blue

NAME                            ENDPOINTS                          AGE
endpoints/echo-server-service   10.244.1.10:5678,10.244.1.9:5678   14m
------------
Hello from Blue

NAME                READY   UP-TO-DATE   AVAILABLE   AGE   CONTAINERS    IMAGES                SELECTOR
echo-server-blue    2/2     2            2           51s   echo-server   hashicorp/http-echo   app=echo-server,version=blue
echo-server-green   2/2     2            2           7s    echo-server   hashicorp/http-echo   app=echo-server,version=green

NAME                          TYPE       CLUSTER-IP     EXTERNAL-IP   PORT(S)        AGE   SELECTOR
service/echo-server-service   NodePort   10.96.85.241   <none>        80:30000/TCP   14m   app=echo-server,version=blue

NAME                            ENDPOINTS                          AGE
endpoints/echo-server-service   10.244.1.10:5678,10.244.1.9:5678   14m
```

#### 6.2.3. Blue -> Green Traffic 전환

![Jenkins Blue Green Deploy - Traffic Switch](/assets/img/ci-cd/ci-cd-study/jenkins-blue-green-deploy-traffic-switch.webp)

```shell
Hello from Blue

NAME                READY   UP-TO-DATE   AVAILABLE   AGE   CONTAINERS    IMAGES                SELECTOR
echo-server-blue    2/2     2            2           63s   echo-server   hashicorp/http-echo   app=echo-server,version=blue
echo-server-green   2/2     2            2           19s   echo-server   hashicorp/http-echo   app=echo-server,version=green

NAME                          TYPE       CLUSTER-IP     EXTERNAL-IP   PORT(S)        AGE   SELECTOR
service/echo-server-service   NodePort   10.96.85.241   <none>        80:30000/TCP   15m   app=echo-server,version=green

NAME                            ENDPOINTS                           AGE
endpoints/echo-server-service   10.244.1.11:5678,10.244.1.12:5678   15m
------------
Hello from Green


NAME                READY   UP-TO-DATE   AVAILABLE   AGE   CONTAINERS    IMAGES                SELECTOR
echo-server-blue    2/2     2            2           64s   echo-server   hashicorp/http-echo   app=echo-server,version=blue
echo-server-green   2/2     2            2           20s   echo-server   hashicorp/http-echo   app=echo-server,version=green

NAME                          TYPE       CLUSTER-IP     EXTERNAL-IP   PORT(S)        AGE   SELECTOR
service/echo-server-service   NodePort   10.96.85.241   <none>        80:30000/TCP   15m   app=echo-server,version=green

NAME                            ENDPOINTS                           AGE
endpoints/echo-server-service   10.244.1.11:5678,10.244.1.12:5678   15m
------------
Hello from Green

NAME                READY   UP-TO-DATE   AVAILABLE   AGE   CONTAINERS    IMAGES                SELECTOR
echo-server-blue    2/2     2            2           66s   echo-server   hashicorp/http-echo   app=echo-server,version=blue
echo-server-green   2/2     2            2           22s   echo-server   hashicorp/http-echo   app=echo-server,version=green

NAME                          TYPE       CLUSTER-IP     EXTERNAL-IP   PORT(S)        AGE   SELECTOR
service/echo-server-service   NodePort   10.96.85.241   <none>        80:30000/TCP   15m   app=echo-server,version=green

NAME                            ENDPOINTS                           AGE
endpoints/echo-server-service   10.244.1.11:5678,10.244.1.12:5678   15m
```

#### 6.2.4. Blue Rollback

![Jenkins Blue Green Deploy - Rollback](/assets/img/ci-cd/ci-cd-study/jenkins-blue-green-deploy-rollback.webp)

```shell
Hello from Green

NAME                READY   UP-TO-DATE   AVAILABLE   AGE     CONTAINERS    IMAGES                SELECTOR
echo-server-blue    2/2     2            2           2m48s   echo-server   hashicorp/http-echo   app=echo-server,version=blue
echo-server-green   2/2     2            2           4m6s    echo-server   hashicorp/http-echo   app=echo-server,version=green

NAME                          TYPE       CLUSTER-IP     EXTERNAL-IP   PORT(S)        AGE   SELECTOR
service/echo-server-service   NodePort   10.96.85.241   <none>        80:30000/TCP   18m   app=echo-server,version=blue

NAME                            ENDPOINTS                           AGE
endpoints/echo-server-service   10.244.1.13:5678,10.244.1.14:5678   18m
------------
Hello from Blue

NAME                READY   UP-TO-DATE   AVAILABLE   AGE     CONTAINERS    IMAGES                SELECTOR
echo-server-blue    2/2     2            2           2m50s   echo-server   hashicorp/http-echo   app=echo-server,version=blue
echo-server-green   2/2     2            2           4m8s    echo-server   hashicorp/http-echo   app=echo-server,version=green

NAME                          TYPE       CLUSTER-IP     EXTERNAL-IP   PORT(S)        AGE   SELECTOR
service/echo-server-service   NodePort   10.96.85.241   <none>        80:30000/TCP   18m   app=echo-server,version=blue

NAME                            ENDPOINTS                           AGE
endpoints/echo-server-service   10.244.1.13:5678,10.244.1.14:5678   18m
------------
Hello from Blue

NAME                READY   UP-TO-DATE   AVAILABLE   AGE     CONTAINERS    IMAGES                SELECTOR
echo-server-blue    2/2     2            2           2m52s   echo-server   hashicorp/http-echo   app=echo-server,version=blue
echo-server-green   2/2     2            2           4m10s   echo-server   hashicorp/http-echo   app=echo-server,version=green

NAME                          TYPE       CLUSTER-IP     EXTERNAL-IP   PORT(S)        AGE   SELECTOR
service/echo-server-service   NodePort   10.96.85.241   <none>        80:30000/TCP   18m   app=echo-server,version=blue

NAME                            ENDPOINTS                           AGE
endpoints/echo-server-service   10.244.1.13:5678,10.244.1.14:5678   18m
```

---

## 7. 실습 리소스 정리

```shell
kubectl delete deploy echo-server-blue echo-server-green ; kubectl delete svc echo-server-service
```

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
