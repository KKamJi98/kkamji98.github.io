---
title: Jenkins + ArgoCD 실습 환경 구축
date: 2025-10-26 23:25:51 +0900
author: kkamji
categories: [DevOps]
tags: [devops, ci-cd-study, ci-cd-study-3w, jenkins, gogs, kind, docker]
comments: true
image:
  path: /assets/img/ci-cd/ci-cd-study/ci-cd-study.webp
---

`CloudNet@` Gasida님이 진행하는 `CI/CD + ArgoCD + Vault Study` 를 진행하며 학습한 내용을 공유합니다.

이번 3주차 내용에서는 **Jenkins 와 ArgoCD를 사용한 CI/CD**에 대한 내용을 다룹니다. 이번 포스트에서는 **실습 환경 구축**에 대한 내용을 다룹니다.

---

## 1. 실습 환경 구성

실습 환경은 Windows 11의 **WSL2 Ubuntu**에서 진행했습니다.

### 1.1. Kind Kubernetes Cluster 배포

```shell
##############################################################
# 클러스터 배포 전 확인
##############################################################
docker ps
mkdir ./cicd-labs
cd ./cicd-labs

##############################################################
# Kind Cluster 생성
##############################################################
kind create cluster --name myk8s --image kindest/node:v1.32.8 --config - <<EOF
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
networking:
  apiServerAddress: "0.0.0.0"
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
- role: worker
EOF

##############################################################
# Kind Cluster 생성 확인
##############################################################
kind get nodes --name myk8s
kubens default

# 컨트롤플레인/워커 노드(컨테이너) 확인 : 도커 컨테이너 이름은 myk8s-control-plane , myk8s-worker 임을 확인
docker ps
# CONTAINER ID   IMAGE                  COMMAND                  CREATED              STATUS              PORTS                                                           NAMES
# e3913205c104   kindest/node:v1.32.8   "/usr/local/bin/entr…"   About a minute ago   Up About a minute   0.0.0.0:30000-30003->30000-30003/tcp, 0.0.0.0:32795->6443/tcp   myk8s-control-plane
# af5b95c58e50   kindest/node:v1.32.8   "/usr/local/bin/entr…"   About a minute ago   Up About a minute                                                                   myk8s-worker
docker images

# 디버그용 내용 출력에 ~/.kube/config 권한 인증 로드
kubectl get pod -v6

# kube config 파일 확인
cat ~/.kube/config | grep "0.0.0.0"
  # server: https://0.0.0.0:32795  # << 포트 정보 메모

# k8s api 호출을 위한 IP 확인
ifconfig eth0
# eth0: flags=4163<UP,BROADCAST,RUNNING,MULTICAST>  mtu 1500
#         inet 172.28.8.232  netmask 255.255.240.0  broadcast 172.28.15.255
#         inet6 fe80::215:5dff:fe0e:9f82  prefixlen 64  scopeid 0x20<link>
#         ether 00:15:5d:0e:9f:82  txqueuelen 1000  (Ethernet)
#         RX packets 482066  bytes 501702394 (501.7 MB)
#         RX errors 0  dropped 0  overruns 0  frame 0
#         TX packets 213845  bytes 56001324 (56.0 MB)
#         TX errors 0  dropped 0 overruns 0  carrier 0  collisions 0

## 위 메모한 IP:Port 호출 확인
curl -k https://172.28.8.232:32795/version
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

### 1.2. Kind Kubernetes Cluster에 kube-ops-view 배포

`kube-ops-view`는 여러 Kubernetes 클러스터를 대상으로 읽기 전용(Read-only) 대시보드를 제공하는 오픈소스 도구입니다. 클러스터의 현재 상태(노드, 파드, 네임스페이스 등)를 시각적으로 확인하고 운영팀이 빠르게 전반 구조 및 이상 상태를 파악할 수 있습니다.

> [kube-ops-view - GitHub](https://github.com/hjacobs/kube-ops-view)  

![kube-ops-view](/assets/img/ci-cd/ci-cd-study/kube-ops-view.webp)
> [ec2spotworkshops - Install Kube-ops-view](https://ec2spotworkshops.com/using_ec2_spot_instances_with_eks/030_k8s_tools.html)  

```shell
# kube-ops-view
# helm show values geek-cookbook/kube-ops-view
helm repo add geek-cookbook https://geek-cookbook.github.io/charts/
helm install kube-ops-view geek-cookbook/kube-ops-view --version 1.2.2 --set service.main.type=NodePort,service.main.ports.http.nodePort=30001 --set env.TZ="Asia/Seoul" --namespace kube-system

# 설치 확인
kubectl get deploy,pod,svc,ep -n kube-system -l app.kubernetes.io/instance=kube-ops-view

# eth0번 IP 변수 저장
IP=$(ip addr show eth0 | grep 'inet ' | awk '{print $2}' | cut -d'/' -f1)

# Mac의 open 명령어와 비슷한 동작을 위한 alias 설정
alias open='powershell.exe -NoProfile -Command Start-Process'

# kube-ops-view 접속 URL 확인 (1.5 , 2 배율)
open "http://$IP:30001/#scale=1.5"
open "http://$IP:30001/#scale=2"
```

![Kube Ops View Deploy Check](/assets/img/ci-cd/ci-cd-study/kube-ops-view-deploy-check.webp)

### 1.3. Jenkins 및 Gogs 배포 (Docker Compose)

`Jenkins`, `gogs`를 Docker Compose로 묶어서 띄웁니다. (`kind network`를 공유 함)

```shell
##############################################################
# 사전 환경 확인
##############################################################
# kind 설치를 먼저 진행하여 docker network(kind) 생성 후 아래 Jenkins,gogs 생성
# docker network 확인 : kind 를 사용
docker network ls | grep kind       
# aeeabbb3f70f   kind                     bridge    local

##############################################################
# jenkins, gogs 배포
##############################################################
# docker compose 파일 생성
cat <<EOT > docker-compose.yaml
services:

  jenkins:
    container_name: jenkins
    image: jenkins/jenkins
    restart: unless-stopped
    networks:
      - kind
    ports:
      - "8080:8080"
      - "50000:50000"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - jenkins_home:/var/jenkins_home

  gogs:
    container_name: gogs
    image: gogs/gogs
    restart: unless-stopped
    networks:
      - kind
    ports:
      - "10022:22"
      - "3000:3000"
    volumes:
      - gogs-data:/data

volumes:
  jenkins_home:
  gogs-data:

networks:
  kind:
    external: true
EOT

# docker compose 배포
docker compose up -d
docker compose ps
docker inspect kind

# 기본 정보 확인
for i in gogs jenkins ; do echo ">> container : $i <<"; docker compose exec $i sh -c "whoami && pwd"; echo; done

# 도커를 이용하여 각 컨테이너로 접속 확인
docker compose exec jenkins bash
exit

docker compose exec gogs bash
exit
```

#### 1.3.1. Jenkins 초기 설정

```shell
# eth0번 IP 변수 저장
IP=$(ip addr show eth0 | grep 'inet ' | awk '{print $2}' | cut -d'/' -f1)

# Mac의 open 명령어와 비슷한 동작을 위한 alias 설정
alias open='powershell.exe -NoProfile -Command Start-Process'

# Jenkins 초기 암호 확인
docker compose exec jenkins cat /var/jenkins_home/secrets/initialAdminPassword
# 08622edeaacb491fbbac096cd74059b0

# Jenkins 웹 접속 주소 및 로그인 계정 / 암호 입력 >> admin / qwe123
open http://$IP:8080

# (참고) 로그 확인 : 플러그인 설치 과정 확인
docker compose logs jenkins -f
```

![Jenkins Setup](/assets/img/ci-cd/ci-cd-study/jenkins-setup.webp)
> Jenkins 초기 암호 입력 -> Install Suggested Plugins 클릭  

![Jenkins Create First Admin User](/assets/img/ci-cd/ci-cd-study/jenkins-create-first-admin-user.webp)
> 사용할 계정 정보 입력 후 Save and Continue 클릭 해 계정 생성  

![Jenkins Instance Configuration](/assets/img/ci-cd/ci-cd-study/jenkins-instance-configuration.webp)
> Jenkins URL -> Host OS의 eth0 인터페이스의 IP 입력  

![Jenkins Main](/assets/img/ci-cd/ci-cd-study/jenkins-main.webp)
> Jenkins 접속 완료 확인  

#### 1.3.2. Jenkins 컨테이너에서 호스트에 도커 데몬 설정 (Docker-out-of-Docker)

![DinD vs DooD](/assets/img/ci-cd/ci-cd-study/d-in-d_vs_d-out-d.webp)
> <https://daniel00324.tistory.com/17>  

```shell
##############################################################
# Jenkins 컨테이너 내부에 도커 실행 파일 설치
##############################################################
docker compose exec --privileged -u root jenkins bash

-----------------------------------------------------
# jenkins container 내부
id
# uid=0(root) gid=0(root) groups=0(root)

curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  tee /etc/apt/sources.list.d/docker.list > /dev/null
apt-get update && apt install docker-ce-cli curl tree jq yq -y

docker info
docker ps
which docker

# Jenkins 컨테이너 내부에서 root가 아닌 jenkins 유저도 docker를 실행할 수 있도록 권한을 부여
groupadd -g 989 -f docker  # Windows WSL2(Container) >> cat /etc/group 에서 docker 그룹ID를 지정

chgrp docker /var/run/docker.sock
ls -l /var/run/docker.sock
usermod -aG docker jenkins
cat /etc/group | grep docker

exit
--------------------------------------------

# Jenkins 컨테이너 재기동으로 위 설정 내용을 Jenkins app 에도 적용 필요
sudo docker compose restart jenkins

# jenkins user로 docker 명령 실행 확인
sudo docker compose exec jenkins id
sudo docker compose exec jenkins docker info
sudo docker compose exec jenkins docker ps
sudo docker compose exec jenkins cat /etc/group
```

### 1.4. Gogs 초기 세팅

Gogs is a painless self-hosted Git service

- [gogs github](https://github.com/gogs/gogs)
- [gogs docs](https://gogs.io/docs)

```shell
# Mac의 open 명령어와 비슷한 동작을 위한 alias 설정
alias open='powershell.exe -NoProfile -Command Start-Process'

# eth0번 IP 변수 저장
IP=$(ip addr show eth0 | grep 'inet ' | awk '{print $2}' | cut -d'/' -f1)

# 초기 설정 웹 접속
open "http://$IP:3000/install"
```

- 데이터베이스 유형 : **SQLite3**
- 애플리케이션 URL :  `http://<각자 자신의 IP>:3000/`
- 기본 브랜치 : **main**
- **관리자 계정 설정** 클릭 : 이름(**계정명 - 닉네임 사용 (devops)**), 비밀번호, 이메일 입력
- `Install Gogs` 클릭

![gogs initial setting](/assets/img/ci-cd/ci-cd-study/gogs-initial-setting.webp)

### 1.5. Gogs Token 생성

1. 로그인
2. Your Settings -> Applications : Generate New Token 클릭
3. Token Name(devops) ⇒ Generate Token 클릭 (Token 메모해두기)

![Gogs Generate Token](/assets/img/ci-cd/ci-cd-study/gogs-generate-token.webp)
> <https://daniel00324.tistory.com/17>  

```shell
# 실습에 사용할 Gogs Token
48bf0caa1c0eeaf85eea28858c3dd472c16d9103
```

### 1.6. Gogs Repository 생성

![Gogs Create Repository](/assets/img/ci-cd/ci-cd-study/gogs-create-repository.webp)
> Gogs Repository 생성  

![Gogs Repository Setting Screen](/assets/img/ci-cd/ci-cd-study/gogs-repository-setting-screen.webp)
> Gogs Repository 설정 화면  

- New Repository 1 : **개발팀용**
  - Repository Name : **dev-app**
  - Visibility : (**Check**) This repository is **Private** *← 가시성 위에것 체크*
  - .gitignore : **Python**
  - Readme : Default → (Check) initialize this repository with selected files and template
  
  ⇒ Create Repository 클릭 : Repo 주소 확인

- New Repository 2 : **데브옵스팀용**
  - Repository Name : **ops-deploy**
  - Visibility : (**Check**) This repository is **Private**
  - .gitignore : **Python**
  - Readme : Default → (Check) initialize this repository with selected files and template
  
  ⇒ Create Repository 클릭 : Repo 주소 확인

![Gogs Repository Setting Dev App](/assets/img/ci-cd/ci-cd-study/gogs-repository-setting-dev-app.webp)
> dev-app repository 예시  

### 1.7. Gogs 실습을 위한 저장소 설정

실습 환경의 깔끔한 마무리를 위해 `Gogs` 컨테이너 내부에서 실습 진행했습니다. 로컬 IDE 내에서 진행해도 실습에는 영향 없습니다.

```shell
##############################################################
# gogs 컨테이너 내부 진입
##############################################################
sudo docker exec -it gogs bash
----------------------------------------------

##############################################################
# gogs 컨테이너 내부에 저장소 설정
##############################################################
# (옵션) GIT 인증 정보 초기화
git credential-cache exit

# 
TMOUT=0
pwd
ls
cd /data # 호스트 mount 볼륨 공유 경로

#
git config --list --show-origin

# TOKEN=<각자 Gogs Token>
TOKEN=48bf0caa1c0eeaf85eea28858c3dd472c16d9103

# MyIP=<각자 자신의 IP> # mac(PC IP), windows(ubuntu eth0)
MyIP=172.28.8.232

# git clone <각자 Gogs dev-app repo 주소>
git clone http://devops:$TOKEN@$MyIP:3000/devops/dev-app.git
# Cloning into 'dev-app'...
# ...

# 저장소로 이동
cd /data/dev-app

# git config 설정
git --no-pager config --local --list
git config --local user.name "devops"
git config --local user.email "a@a.com"
git config --local init.defaultBranch main
git config --local credential.helper store
git --no-pager config --local --list
cat .git/config
# [core]
#         repositoryformatversion = 0
#         filemode = true
#         bare = false
#         logallrefupdates = true
# [remote "origin"]
#         url = http://devops:48bf0caa1c0eeaf85eea28858c3dd472c16d9103@172.28.8.232:3000/devops/dev-app.git
#         fetch = +refs/heads/*:refs/remotes/origin/*
# [branch "main"]
#         remote = origin
#         merge = refs/heads/main
# [user]
#         name = devops
#         email = a@a.com
# [init]
#         defaultBranch = main
# [credential]
#         helper = store

#
git --no-pager branch
git remote -v
# origin  http://devops:48bf0caa1c0eeaf85eea28858c3dd472c16d9103@172.28.8.232:3000/devops/dev-app.git (fetch)
# origin  http://devops:48bf0caa1c0eeaf85eea28858c3dd472c16d9103@172.28.8.232:3000/devops/dev-app.git (push)

##############################################################
# server.py 파일 작성
##############################################################
cat > server.py <<EOF
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from datetime import datetime
import socket

class RequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        match self.path:
            case '/':
                now = datetime.now()
                hostname = socket.gethostname()
                response_string = now.strftime("The time is %-I:%M:%S %p, VERSION 0.0.1\n")
                response_string += f"Server hostname: {hostname}\n"                
                self.respond_with(200, response_string)
            case '/healthz':
                self.respond_with(200, "Healthy")
            case _:
                self.respond_with(404, "Not Found")

    def respond_with(self, status_code: int, content: str) -> None:
        self.send_response(status_code)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(bytes(content, "utf-8")) 

def startServer():
    try:
        server = ThreadingHTTPServer(('', 80), RequestHandler)
        print("Listening on " + ":".join(map(str, server.server_address)))
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()

if __name__== "__main__":
    startServer()
EOF

# (참고) python 실행 확인 (python 이 깔려 있으면 가능하나 현재 깔려 있지 않음으로 진행 X)
python3 server.py
curl localhost
curl localhost/healthz


##############################################################
# Dockerfile 생성
##############################################################
cat > Dockerfile <<EOF
FROM python:3.12
ENV PYTHONUNBUFFERED 1
COPY . /app
WORKDIR /app 
CMD python3 server.py
EOF


##############################################################
# VERSION 파일 생성
##############################################################
echo "0.0.1" > VERSION

# Gogs 에 Python Project Push
tree
# .
# ├── Dockerfile
# ├── README.md
# ├── VERSION
# └── server.py
git status
git add .
git commit -m "Add dev-app"
git push -u origin main
```

![Gogs dev-app Repo Check](/assets/img/ci-cd/ci-cd-study/gogs-dev-app-repo-check.webp)

### 1.8. Docker Hub Personal Access Token 발급

1. 계정 -> Account settings
   ![Docker Hub - Account Settings](/assets/img/ci-cd/ci-cd-study/docker-hub-account-settings.webp)
2. Settings -> Security -> Personal access tokens -> Generate new token
   ![Docker Hub - Generate new token](/assets/img/ci-cd/ci-cd-study/docker-hub-generate-new-token.webp)
3. Create access token (Access permissions -> Read, Write, Delete)
   ![Docker Hub - Create Personal Access Token](/assets/img/ci-cd/ci-cd-study/docker-hub-create-pat.webp)
4. Generate 클릭 후 발급된 token 메모 (예시)
   ![Docker Hub - Personal Access Token](/assets/img/ci-cd/ci-cd-study/docker-hub-personal-access-token.webp)

### 1.9. Docker Hub Private Repository 생성 (dev-app)

- Repositories -> Create a repository
![Docker Hub - Create Private Repository](/assets/img/ci-cd/ci-cd-study/docker-hub-create-private-repository.webp)

---

## 2. 실습 환경 정리

### 2.1. Jenkins + gogs 정리

- (참고) 실습 완료 후 해당 컨테이너 중지 상태로 둘 경우 -> 재부팅 및 이후에 다시 실습을 위해 컨테이너 시작 시

  ```bash
  # 실습 완료 후 해당 컨테이너 중지 상태로 둘 경우
  docker compose stop
  docker compose ps
  docker compose ps -a
  
  # 재부팅 및 이후에 다시 실습을 위해 컨테이너 시작 시
  docker compose start
  docker compose ps
  ```

- (참고) 특정 컨테이너만 삭제 후 다시 초기화 상태로 기동 시

  ```bash
  (방안1) 호스트 mount 볼륨 공유 사용 시
  # gogs : 볼륨까지 삭제
  docker compose stop gogs
  docker compose rm -f gogs
  rm -rf gogs-data

  docker compose up gogs -d

  # jenkins : 볼륨까지 삭제
  docker compose stop jenkins
  docker compose rm -f jenkins
  rm -rf jenkins_home

  docker compose up jenkins -d
  ```
  
  ```bash
  (방안) 도커 불륨 사용 시
  # gogs : 볼륨까지 삭제
  docker compose rm -f -v gogs
  docker compose up gogs -d

  # jenkins : 볼륨까지 삭제
  docker compose rm -f -v jenkins
  docker compose up jenkins -d
  ```

- (참고) 모든 실습 후 삭제 시(방안1) : **`docker compose down --remove-orphans && rm -rf gogs-data jenkins_home`**
- (참고) 모든 실습 후 삭제 시(방안2) : **`docker compose down --volumes --remove-orphans`**

### 2.2. Kind Cluster 정리

```shell
#- (참고) 모든 실습 후 삭제 시(방안1) : 
sudo docker compose down --remove-orphans && rm -rf gogs-data jenkins_home
#- (참고) 모든 실습 후 삭제 시(방안2) : 
sudo docker compose down --volumes --remove-orphans

# 클러스터 삭제
kind delete cluster --name myk8s
sudo docker ps

# kubeconfig 파일 확인
cat ~/.kube/config
```

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
