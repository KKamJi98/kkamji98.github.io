---
title: Jenkins CI + K8s
date: 2025-10-28 01:32:51 +0900
author: kkamji
categories: [DevOps]
tags: [devops, ci-cd-study, ci-cd-study-3w, jenkins, gogs, kind, docker]
comments: true
image:
  path: /assets/img/ci-cd/ci-cd-study/ci-cd-study.webp
---

`CloudNet@` Gasida님이 진행하는 `CI/CD + ArgoCD + Vault Study` 를 진행하며 학습한 내용을 공유합니다.

이번 포스트에서는 **Jenkins** 란 무엇인지, **Jenkins를 사용한 CI**(Continuous Integration) 과정에 대해 다루겠습니다.

실습 환경은 [Jenkins + ArgoCD 실습 환경 구축]({% post_url 2025/2025-10-26-jenkins-ci-cd-env-3w %}) 의 실습환경을 사용합니다.

---

## 1. Jenkins 란?

**Jenkins**는 오픈소스 자동화 서버입니다. 프로젝트의 Build, Test, Deploy 및 자동화를 지원하는 수백 개의 플러그인을 제공하고, 각 파이프라인의 단계별 동작에 대한 내용을 **코드로 정의**하여 사용할 수 있습니다.

> [Jenkins Home](https://www.jenkins.io/)
> [Jenkins Docs](https://www.jenkins.io/doc/)

### 1.1. Jenkins 핵심 특징

- **Continuous Integration and Continuous Delivery**  
  확장 가능한 자동화 서버로 단순 CI 서버로도, 어느 프로젝트든 CD 허브로도 활용할 수 있습니다.

- **Easy installation**  
  Windows, Linux, macOS 및 기타 Unix 계열 운영체제를 위한 패키지를 갖추고 있어 바로 실행 가능한 독립형 Java 기반 프로그램입니다.

- **Easy configuration**  
  웹 인터페이스로 손쉽게 설정 및 구성할 수 있으며, 즉석 오류 검사와 내장 도움말을 포함합니다.

- **Plugins**  
  업데이트 센터의 수백 개 플러그인으로 CI/CD 툴체인의 거의 모든 도구와 통합됩니다.

- **Extensible**  
  플러그인 아키텍처를 통해 다양한 기능으로 확장이 가능합니다.

- **Distributed**  
  여러 머신으로 작업을 분산해 다양한 플랫폼에서 Build, Test, Deploy를 더 빠르게 수행할 수 있습니다.

---

## 2. Jenkins Pipeline 이란?

**Jenkins Pipeline**(이하 “Pipeline”)은 Jenkins에서 **지속적 통합(Continuous Integration)** 과 **지속적 전달(Continuous Delivery)** 프로세스를 구현하기 위해 제공되는 **플러그인 모음(Suite of Plugins)** 입니다.

즉, 애플리케이션의 **빌드(Build) -> 테스트(Test) -> 배포(Deploy)** 과정을 코드 형태로 정의하고 자동화할 수 있는 도구 세트입니다.

![Jenkins Pipeline](/assets/img/ci-cd/ci-cd-study/jenkins-pipeline.webp)

> [Jenkins Docs - What is Jenkins Pipeline?](https://www.jenkins.io/doc/book/pipeline/)

### 2.1. Jenkins Pipeline 장점

- **코드** : 애플리케이션 CI/CD 프로세스를 코드 형식으로 작성할 수 있고, 해당 코드를 중앙 리포지터리에 저장하여 팀원과 공유 및 작업 가능
- **내구성** : 젠킨스 서비스가 의도적으로 또는 우발적으로 재시작되더라도 문제없이 유지됨
- **일시 중지 가능** : 파이프라인을 실행하는 도중 사람의 승인이나 입력을 기다리기 위해 중단하거나 기다리는 것이 가능
- **다양성** : 분기나 반복, 병렬 처리와 같은 다양한 CI/CD 요구 사항을 지원

### 2.2. Jenkins Pipeline 용어

![Jenkins Pipeline Term](/assets/img/ci-cd/ci-cd-study/jenkins-pipeline-term.webp)

- **Pipeline** : 전체 빌드 프로세스를 정의하는 코드.
- **Node == Agent** : 파이프라인을 실행하는 시스템
- **stages** : 순차 작업 명세인 stage 들의 묶음
- **stage** : 특정 단계에서 수행되는 작업들의 정의. (옵션) agents 설정
- **steps** : 파이프라인의 특정 단계에서 수행되는 단일 작업을 의미.
- **post** : 빌드 후 조치, 일반적으로 stages 작업이 끝난 후 추가적인 steps/step
- **Directive** : **environment**, **parameters**, triggers, input, **when** - [Docs](https://www.jenkins.io/doc/book/pipeline/syntax/#declarative-directives)
  - **environment (key=value)** : 파이프라인 내부에서 사용할 환경변수
  - **parameters** : 입력 받아야할 변수를 정의 - Type(string, text, choice, password …)
  - **when** : stage 를 실행 할 조건 설정

### 2.3. Jenkins Pipeline의 3가지 구성 형태

- Pipeline **script** : 일반적인 방식으로 Jenkins 파이프라인을 생성하여 Shell Script를 직접 생성하여 빌드하는 방식
  - [Through the classic UI](https://www.jenkins.io/doc/book/pipeline/getting-started/#through-the-classic-ui) - you can enter a basic Pipeline directly in Jenkins through the classic UI.
- Pipeline script from **SCM** : 사전 작성한 JenkinsFile을 형상관리 저장소에 보관하고, 빌드 시작 시 파이프라인 프로젝트에서 호출 실행하는 방식
  - [In SCM](https://www.jenkins.io/doc/book/pipeline/getting-started/#defining-a-pipeline-in-scm) - you can write a `Jenkinsfile` manually, which you can commit to your project’s source control repository.

![Jenkins Pipeline From SCM](/assets/img/ci-cd/ci-cd-study/jenkins-pipeline-from-scm.webp)

- **Blue Ocean** 기반 : UI기반하여 시각적으로 파이프라인을 구성하면, JenkinsFile이 자동으로 생성되어 실행되는 방식
  - [Through Blue Ocean](https://www.jenkins.io/doc/book/pipeline/getting-started/#through-blue-ocean) - after setting up a Pipeline project in Blue Ocean, the Blue Ocean UI helps you write your Pipeline’s `Jenkinsfile` and commit it to source control.

![Blue Ocean](/assets/img/ci-cd/ci-cd-study/jenkins-pipeline-blue-ocean.webp)

> [Jenkins Docs - Pipeline Run Details View](https://www.jenkins.io/doc/book/blueocean/pipeline-run-details/)

### 2.4. 파이프라인 2가지 구문 : **선언형** 파이프라인(권장)과 **스크립트형** 파이프라인

- **선언형** 파이프라인 : 쉽게 작성 가능, 최근 문법이고 젠킨스에서 권장하는 방법, step 필수!
- **스크립트형** 파이프라인 : 커스텀 작업에 용이, 복잡하여 난이도가 높음, step은 필수 아님

![Scripted vs Declarative Pipeline](/assets/img/ci-cd/ci-cd-study/jenkins-scripted-vs-declarative.webp)
> [Scripted vs Declarative Pipeline](https://velog.io/@kku64r/pipeline)

#### 2.4.1. Declarative Pipeline 예시

```shell
pipeline {
    agent any     # Execute this Pipeline or any of its stages, on any available agent.
    stages {
        stage('Build') {   # Defines the "Build" stage.
            steps {
                //         # Perform some steps related to the "Build" stage.
            }
        }
        stage('Test') { 
            steps {
                // 
            }
        }
        stage('Deploy') { 
            steps {
                // 
            }
        }
    }
}
```

#### 2.4.2. Scripted Pipeline 예시

```shell
node {                  # Execute this Pipeline or any of its stages, on any available agent.
    stage('Build') {    # Defines the "Build" stage. stage blocks are optional in Scripted Pipeline syntax. However, implementing stage blocks in a Scripted Pipeline provides clearer visualization of each stage's subset of tasks/steps in the Jenkins UI.
        //              # Perform some steps related to the "Build" stage.
    }
    stage('Test') { 
        // 
    }
    stage('Deploy') { 
        // 
    }
}
```

---

## 3. Jenkins CI + Kubernetes

### 3.1. Jenkins Plugin 설치 및 자격증명 설정

#### 3.1.1. Jenkins Plugin 설치

![Jenkins Install Plugins](/assets/img/ci-cd/ci-cd-study/jenkins-install-plugins.webp)
> Jenkins 관리 -> Plugins

![Jenkins Install Plugins - 2](/assets/img/ci-cd/ci-cd-study/jenkins-install-plugins-2.webp)
> Available plugins -> Search available plugins -> 아래 3개 플러그인 선택 -> Install

1. [Pipeline Stage View](https://plugins.jenkins.io/pipeline-stage-view/)
2. [Docker Pipeline](https://plugins.jenkins.io/docker-workflow/)
3. [Gogs](https://plugins.jenkins.io/gogs-webhook/)

#### 3.1.2. Jenkins Credential 설정

> Jenkins 관리 -> Credentials -> System -> Global credentials -> Add Credentials

1. Gogs Repo 자격증명 설정 : **gogs-crd**
    - Kind : Username with password
    - Username : **devops**
    - Password : *<Gogs 토큰>*
    - ID : **gogs-crd**

![Jenkins Credential - gogs-crd](/assets/img/ci-cd/ci-cd-study/jenkins-credential-gogs-crd.webp)

2. 도커 허브 자격증명 설정 : **dockerhub-crd**
    - Kind : Username with password
    - Username : *<도커 계정명>*
    - Password : *<도커 계정 암호 혹은 토큰>*
    - **ID** : **dockerhub-crd**

![Jenkins Credential - dockerhub-crd](/assets/img/ci-cd/ci-cd-study/jenkins-credential-dockerhub-crd.webp)

### 3.2. Jenkins Item 생성(Pipeline)

> Jenkins Home -> 새로운 Item(New Item) -> item type(Pipeline)
> item name: `pipeline-ci`

```shell
pipeline {
    agent any
    environment {
        DOCKER_IMAGE = '<자신의 도커 허브 계정>/dev-app' // Docker 이미지 이름
    }
    stages {
        stage('Checkout') {
            steps {
                 git branch: 'main',
                 url: 'http://<자신의 IP>:3000/devops/dev-app.git',  // Git에서 코드 체크아웃
                 credentialsId: 'gogs-crd'  // Credentials ID
            }
        }
        stage('Read VERSION') {
            steps {
                script {
                    // VERSION 파일 읽기
                    def version = readFile('VERSION').trim()
                    echo "Version found: ${version}"
                    // 환경 변수 설정
                    env.DOCKER_TAG = version
                }
            }
        }
        stage('Docker Build and Push') {
            steps {
                script {
                    docker.withRegistry('https://index.docker.io/v1/', 'dockerhub-crd') {
                        // DOCKER_TAG 사용
                        def appImage = docker.build("${DOCKER_IMAGE}:${DOCKER_TAG}")
                        appImage.push()
                        appImage.push("latest")
                    }
                }
            }
        }
    }
    post {
        success {
            echo "Docker image ${DOCKER_IMAGE}:${DOCKER_TAG} has been built and pushed successfully!"
        }
        failure {
            echo "Pipeline failed. Please check the logs."
        }
    }
}
```

> 생성 후 지금 빌드 (클릭)  
{: .prompt-tip}

#### 3.2.1. 결과 확인 1 (Jenkins Stage View)

![Jenkins Stage View](/assets/img/ci-cd/ci-cd-study/jenkins-stage-view.webp)

#### 3.2.2. 결과 확인 2 (Docker Hub)

![Docker Hub Image Check](/assets/img/ci-cd/ci-cd-study/dockerhub-image-check.webp)

### 3.3. Kubernetes 에서 위 컨테이너 이미지를 사용하는 Deployment 배포

> Private Container Repository를 사용하는 경우 Repository에 대한 자격 증명이 없을 경우 아래와 같이 `ErrImagePull` 문제가 발생  
{: .prompt-danger}

```shell
# 디플로이먼트 오브젝트 배포 : 리플리카(파드 2개), 컨테이너 이미지 >> 아래 도커 계정 부분만 변경해서 배포해보자
DHUSER=<도커 허브 계정명>
DHUSER=kkankkandev

cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: timeserver
spec:
  replicas: 2
  selector:
    matchLabels:
      pod: timeserver-pod
  template:
    metadata:
      labels:
        pod: timeserver-pod
    spec:
      containers:
      - name: timeserver-container
        image: docker.io/$DHUSER/dev-app:0.0.1
        livenessProbe:
          initialDelaySeconds: 30
          periodSeconds: 30
          httpGet:
            path: /healthz
            port: 80
            scheme: HTTP
          timeoutSeconds: 5
          failureThreshold: 3
          successThreshold: 1
EOF
watch -d kubectl get deploy,rs,pod -o wide

# 배포 상태 확인 : kube-ops-view 웹 확인
kubectl get events -w --sort-by '.lastTimestamp'
kubectl get deploy,pod -o wide
kubectl describe pod
...
Events:
  Type     Reason     Age                From               Message
  ----     ------     ----               ----               -------
  Normal   Scheduled  53s                default-scheduler  Successfully assigned default/timeserver-7cf7db8f6c-mtvn7 to myk8s-worker
  Normal   BackOff    19s (x2 over 50s)  kubelet            Back-off pulling image "docker.io/gasida/dev-app:latest"
  Warning  Failed     19s (x2 over 50s)  kubelet            Error: ImagePullBackOff
  Normal   Pulling    4s (x3 over 53s)   kubelet            Pulling image "docker.io/gasida/dev-app:latest"
  Warning  Failed     3s (x3 over 51s)   kubelet            Failed to pull image "docker.io/gasida/dev-app:latest": failed to pull and unpack image "docker.io/gasida/dev-app:latest": failed to resolve reference "docker.io/gasida/dev-app:latest": pull access denied, repository does not exist or may require authorization: server message: insufficient_scope: authorization failed
  Warning  Failed     3s (x3 over 51s)   kubelet            Error: ErrImagePull
```

### 3.4. Kubernetes 에서 위 컨테이너 이미지를 사용하는 Deployment 배포 - 문제해결

```shell
# k8s secret : 도커 자격증명 설정 
kubectl get secret -A  # 생성 시 타입 지정

DHUSER=<도커 허브 계정>
DHPASS=<도커 허브 암호 혹은 토큰>
echo $DHUSER $DHPASS

kubectl create secret docker-registry dockerhub-secret \
  --docker-server=https://index.docker.io/v1/ \
  --docker-username=$DHUSER \
  --docker-password=$DHPASS

# 확인 : base64 인코딩 확인
kubectl get secret
kubectl get secrets -o yaml | kubectl neat  
kubectl get secret dockerhub-secret -o jsonpath='{.data.\.dockerconfigjson}' | base64 -d | jq

# Deployment Object Upgrade: imagePullSecrets 추가
cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: timeserver
spec:
  replicas: 2
  selector:
    matchLabels:
      pod: timeserver-pod
  template:
    metadata:
      labels:
        pod: timeserver-pod
    spec:
      containers:
      - name: timeserver-container
        image: docker.io/$DHUSER/dev-app:0.0.1
        livenessProbe:
          initialDelaySeconds: 30
          periodSeconds: 30
          httpGet:
            path: /healthz
            port: 80
            scheme: HTTP
          timeoutSeconds: 5
          failureThreshold: 3
          successThreshold: 1
      imagePullSecrets:
      - name: dockerhub-secret
EOF
watch -d kubectl get deploy,rs,pod -o wide

# 확인
kubectl get events -w --sort-by '.lastTimestamp'
kubectl get deploy,pod
# NAME                         READY   UP-TO-DATE   AVAILABLE   AGE
# deployment.apps/timeserver   2/2     2            2           8m39s

# NAME                              READY   STATUS    RESTARTS   AGE
# pod/timeserver-7cb6bcdf75-8tnx9   1/1     Running   0          29s
# pod/timeserver-7cb6bcdf75-cmwxx   1/1     Running   0          90s
```

### 3.5. 배포한 Deployment 외부 노출 (Publish)

```shell
##############################################################
# 서비스 생성
##############################################################
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Service
metadata:
  name: timeserver
spec:
  selector:
    pod: timeserver-pod
  ports:
  - port: 80
    targetPort: 80
    protocol: TCP
    nodePort: 30000
  type: NodePort
EOF

##############################################################
# 서비스 및 endpoint 확인
##############################################################
kubectl get service,ep timeserver -owide
# NAME                 TYPE       CLUSTER-IP      EXTERNAL-IP   PORT(S)        AGE   SELECTOR
# service/timeserver   NodePort   10.96.142.254   <none>        80:30000/TCP   9s    pod=timeserver-pod

# NAME                   ENDPOINTS                     AGE
# endpoints/timeserver   10.244.1.5:80,10.244.1.6:80   9s

##############################################################
# Service(NodePort)로 접속 확인 "노드IP:NodePort"
##############################################################
curl http://127.0.0.1:30000
# The time is 4:09:35 PM, VERSION 0.0.1
# Server hostname: timeserver-7cb6bcdf75-8tnx9
curl http://127.0.0.1:30000
# The time is 4:09:35 PM, VERSION 0.0.1
# Server hostname: timeserver-7cb6bcdf75-cmwxx
curl http://127.0.0.1:30000/healthz
# Healthy



# 반복 접속 해두기 : 부하분산 확인
while true; do curl -s --connect-timeout 1 http://127.0.0.1:30000 ; sleep 1 ; done
for i in {1..100};  do curl -s http://127.0.0.1:30000 | grep name; done | sort | uniq -c | sort -nr

# 파드 복제복 증가 : service endpoint 대상에 자동 추가
kubectl scale deployment timeserver --replicas 4
kubectl get service,ep timeserver -owide

# 반복 접속 해두기 : 부하분산 확인
while true; do curl -s --connect-timeout 1 http://127.0.0.1:30000 ; sleep 1 ; done
for i in {1..100};  do curl -s http://127.0.0.1:30000 | grep name; done | sort | uniq -c | sort -nr
```

### 3.6. 현재 Application Update (Kubernetes Deploying an application with Jenkins)

이번에는 현재 배포한 Sample Application을 새 버전(0.0.2) 태그로 컨테이너 이미지를 빌드 후 컨테이너 저장소(Docker Hub) Push -> Kubernetes Deployment 업데이트를 해보겠습니다. (수동)

![Jenkins CI Overview](/assets/img/ci-cd/ci-cd-study/jenkins-ci-overview.webp)

```shell
##############################################################
# gogs 컨테이너진입
##############################################################
sudo docker exec -it gogs bash

##############################################################
# 태그 변경
##############################################################
cd /data/dev-app

# 현재 버전 확인
grep -R "0.0.1" .
# ./VERSION:0.0.1
# ./server.py:                response_string = now.strftime("The time is %-I:%M:%S %p, VERSION 0.0.1\n")


# VERSION 변경 : 0.0.2
# server.py 변경 : 0.0.2
sed -i 's/0\.0\.1/0\.0\.2/g' ./*

# 버전 변경 확인 및 git add commit push
grep -R "0.0.2" VERSION server.py
# ./VERSION:0.0.2
# ./server.py:                response_string = now.strftime("The time is %-I:%M:%S %p, VERSION 0.0.2\n")

git add . && git commit -m "VERSION $(cat VERSION) Changed" && git push -u origin main

##############################################################
# Jenkins 접속 후 지금 빌드 실행 (수동)
##############################################################
# eth0번 IP 변수 저장
IP=$(ip addr show eth0 | grep 'inet ' | awk '{print $2}' | cut -d'/' -f1)

# Mac의 open 명령어와 비슷한 동작을 위한 alias 설정
alias open='powershell.exe -NoProfile -Command Start-Process'

# Jenkins 접속 -> 아까 생성한 pipeline-ci 에서 '지금 빌드' 실행
open http://$IP:8080

##############################################################
# Kubernetes Deployment 이미지 수정
##############################################################
# 반복 접속 해두기 : 부하분산 확인
while true; do curl -s --connect-timeout 1 http://127.0.0.1:30000 ; sleep 1 ; done
for i in {1..100};  do curl -s http://127.0.0.1:30000 | grep name; done | sort | uniq -c | sort -nr

# 이미지 변경
kubectl set image deployment timeserver timeserver-container=$DHUSER/dev-app:0.0.2 && watch -d "kubectl get deploy,ep timeserver -owide; echo; kubectl get rs,pod"

# 롤링 업데이트 확인
watch -d kubectl get deploy,rs,pod,svc,ep -owide
kubectl get deploy,rs,pod,svc,ep -owide

# kubectl get deploy $DEPLOYMENT_NAME
kubectl get deploy timeserver
kubectl get pods -l pod=timeserver-pod

# 변경 확인 (아까 실행한 명령어 0.0.1 -> 0.0.2)
while true; do curl -s --connect-timeout 1 http://127.0.0.1:30000 ; sleep 1 ; done
# Server hostname: timeserver-7cb6bcdf75-8tnx9
# The time is 5:27:49 PM, VERSION 0.0.1
# Server hostname: timeserver-7cb6bcdf75-cmwxx
# The time is 5:27:50 PM, VERSION 0.0.1
# Server hostname: timeserver-7cb6bcdf75-8tnx9
# The time is 5:27:51 PM, VERSION 0.0.2
# Server hostname: timeserver-86c98b478c-xt5gt
# The time is 5:27:52 PM, VERSION 0.0.2
```

### 3.7. Gogs Webhooks 설정: Jenkins Job Trigger

gogs 의 `/data/gogs/conf/app.ini` 파일 수정 후 컨테이너 재기동 - [issue](https://github.com/gogs/gogs/issues/7109)

```shell
##############################################################
# gogs 컨테이너 진입
##############################################################
sudo docker exec -it gogs bash

##############################################################
# /data/gogs/conf/app.ini 파일 편집
##############################################################
[security]
INSTALL_LOCK = true                         
SECRET_KEY   = 8Idn7RM0joCQ5Qa
LOCAL_NETWORK_ALLOWLIST = 172.28.8.232 # 각자 자신의 IP 추가

##############################################################
# gogs 컨테이너 탈출
##############################################################
exit

##############################################################
# gogs 컨테이너 재가동
##############################################################
sudo docker compose restart gogs
```

Jenkins job Trigger - [dev-app] - Setting → Webhooks → Gogs 클릭

- Payload URL : `http://172.28.8.232:8080/gogs-webhook/?job=**SCM-Pipeline**/`  *# 각자 자신의 IP*
- Content Type : `application/json`
- Secret : `asdasd123`
- When should this webhook be triggered? : **Just the push event**
- Active : **Check**

=> Add webhook 클릭 -> Test Delivery 시도 시, 현재는 Jenkins 미설정 상태로 404 실패

![Gogs - Add Webhook](/assets/img/ci-cd/ci-cd-study/gogs-add-webhook.webp)
> Webhook 설정

![Gogs - Check Webhook](/assets/img/ci-cd/ci-cd-study/gogs-check-webhook.webp)
> 생성한 Webhook 확인

### 3.8. Jenkins Item 생성(Pipeline Name - SCM-Pipeline)

- GitHub project : `http://***자신의 IP>***:3000/***<Gogs 계정명>***/dev-app` ← *.git 은 제거*
  - *GitHub project : `http://172.28.8.232:3000/devops/dev-app`*
- Use Gogs secret : **asdasd123**
- Triggers : **Build when a change is pushed to Gogs 체크**
- Pipeline script from SCM
  - SCM : Git
    - Repo URL(`http://***자신의 IP***:3000/***<Gogs 계정명>***/dev-app`)
    - Credentials(**devops/*****)
    - Branch(***/main**)
  - Script Path : **Jenkinsfile**

![Jenkins Item Configuration - GitHub project & Use Gogs Secret](/assets/img/ci-cd/ci-cd-study/jenkins-item-configuration-github-project-and-use-gogs-secret.webp)
![Jenkins Item Configuration - Triggers](/assets/img/ci-cd/ci-cd-study/jenkins-item-configuration-triggers.webp)
![Jenkins Item Configurtaion - Pipeline](/assets/img/ci-cd/ci-cd-study/jenkins-item-configuration-pipeline.webp)

### 3.9. Jenkinsfile 작성 후 git push

![Jenkins CI Workflow](/assets/img/ci-cd/ci-cd-study/jenkins-ci-workflow.webp)

```shell
##############################################################
# gogs 컨테이너 진입
##############################################################
sudo docker exec -it gogs bash

##############################################################
# 태그 변경
##############################################################
cd /data/dev-app

# 현재 버전 확인
grep -R "0.0.2" VERSION server.py
# ./VERSION:0.0.2
# ./server.py:                response_string = now.strftime("The time is %-I:%M:%S %p, VERSION 0.0.2\n")


# VERSION 변경 : 0.0.3
# server.py 변경 : 0.0.3
sed -i 's/0\.0\.2/0\.0\.3/g' VERSION server.py

# 버전 변경 확인 및 git add commit push
grep -R "0.0.3" VERSION server.py
# ./VERSION:0.0.3
# ./server.py:                response_string = now.strftime("The time is %-I:%M:%S %p, VERSION 0.0.3\n")

##############################################################
# Jenkinsfile 생성
##############################################################
# Jenkinsfile
pipeline {
  agent any
  environment {
    DOCKER_IMAGE = 'kkankkandev/dev-app'
  }
  stages {
    stage('Checkout') {
      steps {
        git branch: 'main',
            url: 'http://172.28.8.232:3000/devops/dev-app.git',
            credentialsId: 'gogs-crd'
      }
    }
    stage('Read VERSION') {
      steps {
        script {
          def version = readFile('VERSION').trim()
          if (!version) { error 'VERSION is empty' }
          env.DOCKER_TAG = version
          echo "IMAGE=${env.DOCKER_IMAGE}:${env.DOCKER_TAG}"
        }
      }
    }
    stage('Docker Build and Push') {
      steps {
        script {
          docker.withRegistry('https://index.docker.io/v1/', 'dockerhub-crd') {
            def imageRef = "${env.DOCKER_IMAGE}:${env.DOCKER_TAG}"
            def appImage = docker.build(imageRef)
            appImage.push()
            appImage.push('latest')
          }
        }
      }
    }
  }
  post {
    success { echo "Pushed ${env.DOCKER_IMAGE}:${env.DOCKER_TAG}" }
    failure { echo 'Pipeline failed. Check logs.' }
  }
}

##############################################################
# 변경된 내용 git push
##############################################################
git add . && git commit -m "VERSION $(cat VERSION) Changed" && git push -u origin main
```

### 3.10. WebHook 기록, Jenkins 트리거 빌드 확인 및 Container Image 확인

![Gogs Webhook History Check](/assets/img/ci-cd/ci-cd-study/gogs-webhook-histroy-check.webp)
> Gogs Webhook 기록

![Jenkins Trigger Build Check](/assets/img/ci-cd/ci-cd-study/jenkins-trigger-build-check.webp)
> Jenkins Trigger Build

![Docker Hub 0.0.3 Container Iamge](/assets/img/ci-cd/ci-cd-study/docker-hub-0-0-3-container-image.webp)
> Docker Hub 0.0.3 버전 컨테이너 이미지 확인

### 3.11. Kubernetes 에 신규 버전 컨테이너 이미지 적용

```shell
DHUSER=<도커 허브 계정>

DHUSER=kkankkandev

# 신규 버전 적용
kubectl set image deployment timeserver timeserver-container=$DHUSER/dev-app:0.0.3 && while true; do curl -s --connect-timeout 1 http://127.0.0.1:30000 ; sleep 1 ; done
# Server hostname: timeserver-86c98b478c-xt5gt
# The time is 6:29:39 PM, VERSION 0.0.2
# Server hostname: timeserver-86c98b478c-fqnrm
# The time is 6:29:40 PM, VERSION 0.0.2
# Server hostname: timeserver-86c98b478c-p9jfl 
# The time is 6:29:41 PM, VERSION 0.0.3          # 0.0.3 으로 변경 확인
# Server hostname: timeserver-75d88bc86d-9fxxb
# The time is 6:29:42 PM, VERSION 0.0.3


# 확인
watch -d "kubectl get deploy,ep timeserver; echo; kubectl get rs,pod"
```

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
