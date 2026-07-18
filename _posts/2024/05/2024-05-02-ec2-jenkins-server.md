---
title: EC2 위에 Jenkins Server 구축하기
date: 2024-05-02 22:42:36 +0900
author: kkamji
categories: [CI/CD, Jenkins]
tags: [jenkins, agent, ec2, aws, microk8s]     # TAG names should always be lowercase
comments: true
content_kind: lab
image:
  path: /assets/img/ci-cd/jenkins/jenkins.webp
---

Jenkins controller를 EC2에 두고 build 실행은 이후 Kubernetes agent에 맡기면 controller의 상태와 build workload를 분리할 수 있습니다. 이 글은 Ubuntu 24.04에서 Jenkins LTS를 설치하고, 외부 노출과 초기 administrator 설정에서 놓치기 쉬운 보안 항목을 함께 정리합니다.

> **TL;DR**  
> - 현재 Jenkins Debian/Ubuntu 설치 안내는 Java 21을 먼저 설치한 뒤 LTS apt repository를 추가하는 흐름입니다.  
> - package는 systemd service와 `jenkins` 사용자, 기본 8080 listener를 만듭니다.  
> - 8080을 Internet에 직접 공개하지 말고, HTTPS reverse proxy 또는 VPN 뒤에 두며 administrator password와 Jenkins home을 보호합니다.  
{: .prompt-info}

---

## 1. 구성과 용어

| 용어 | 의미 |
| --- | --- |
| controller | pipeline 정의, credential, queue, plugin을 관리하는 Jenkins server입니다. |
| agent | controller가 할당한 build와 test를 실행하는 worker입니다. Kubernetes Pod agent도 이 역할입니다. |
| `JENKINS_HOME` | job 설정, build metadata, plugin, credential 관련 데이터를 보관하는 Jenkins data directory입니다. |

작은 팀 기준으로 Jenkins는 4 GiB 이상의 memory와 충분한 persistent disk를 권장합니다. EC2 instance type은 build를 controller에서 실행할지, agent에서 실행할지에 따라 달라집니다. controller 자체에는 build cache와 대량 artifact를 쌓지 않는 편이 운영과 backup에 유리합니다.

```text
developer
    |
HTTPS reverse proxy or VPN
    |
Jenkins controller on EC2 ----- schedules ----- Kubernetes agent Pod
    |                                            |
JENKINS_HOME and backups                        build, test, artifact upload
```

controller는 pipeline의 제어와 상태를 맡고, 신뢰하지 않는 repository code를 실행하는 build는 agent에 격리하는 것이 핵심입니다. Jenkins도 built-in node에서 build를 실행하지 않는 controller isolation을 권장합니다.

---

## 2. Java 21 설치

Jenkins 설치보다 Java를 먼저 설치합니다. Jenkins 공식 설치 문서는 현재 Java 21 이상을 요구하며, Java를 나중에 설치하면 service가 유효한 Java runtime을 찾지 못할 수 있다고 안내합니다.

```bash
sudo apt update
sudo apt install -y fontconfig openjdk-21-jre
java -version
```

지원 Java version은 Jenkins release에 따라 바뀔 수 있습니다. controller와 agent image를 upgrade할 때는 Jenkins Java support policy와 plugin compatibility를 함께 확인합니다.

---

## 3. Jenkins LTS 설치

LTS repository를 사용하면 12주 주기의 장기 지원 release stream을 받습니다. weekly repository는 새 기능을 더 빨리 제공하지만 운영 환경에서는 plugin 검증 부담이 커질 수 있습니다.

```bash
sudo install -d -m 0755 /etc/apt/keyrings
sudo wget -O /etc/apt/keyrings/jenkins-keyring.asc \
  https://pkg.jenkins.io/debian-stable/jenkins.io-2026.key
echo "deb [signed-by=/etc/apt/keyrings/jenkins-keyring.asc]" \
  https://pkg.jenkins.io/debian-stable binary/ | sudo tee \
  /etc/apt/sources.list.d/jenkins.list > /dev/null
sudo apt update
sudo apt install -y jenkins
sudo systemctl enable --now jenkins
```

설치 후에는 process 상태와 log를 확인합니다.

```bash
sudo systemctl status jenkins --no-pager
sudo journalctl -u jenkins.service -n 100 --no-pager
```

기본 listener는 8080입니다. 이미 사용 중인 port가 있다면 systemd drop-in으로 `JENKINS_PORT`를 바꾸고 daemon reload 후 재시작합니다. package가 제공하는 unit file을 직접 수정하면 package upgrade에서 덮어쓸 수 있습니다.

---

## 4. 안전하게 초기 설정 열기

최초 unlock password는 server의 다음 파일에 있습니다.

```bash
sudo cat /var/lib/jenkins/secrets/initialAdminPassword
```

이 값은 one-time administrator setup에만 사용하고 chat, source repository, terminal capture에 남기지 않습니다. setup wizard에서는 필요한 plugin만 설치하고, administrator 계정에는 개인 계정과 강력한 password 또는 조직의 identity provider를 사용합니다.

EC2 security group은 다음을 기준으로 설계합니다.

- SSH는 bastion 또는 관리자 CIDR로만 제한합니다.
- Jenkins 8080은 reverse proxy, load balancer, VPN subnet 등 필요한 caller만 허용합니다.
- 일반 사용자는 HTTPS endpoint로 접속하고, TLS certificate와 HTTP to HTTPS redirect는 edge proxy에서 강제합니다.
- controller에서 Kubernetes API, source control, artifact registry로 나가는 egress도 필요한 host와 port로 제한합니다.

---

## 5. 운영 준비

Jenkins는 controller state가 사라지면 job 설정과 credential 운영에 큰 영향을 받습니다. 다음 항목을 설치 직후 준비합니다.

- EBS volume 또는 동등한 persistent disk에 `JENKINS_HOME`을 두고, backup과 restore 절차를 실제로 점검합니다.
- plugin은 update center에서 무분별하게 올리지 말고 staging에서 core LTS와 함께 검증합니다.
- credential은 Jenkins credential store와 외부 secret manager를 사용합니다. Jenkinsfile, console log, agent image에 token을 넣지 않습니다.
- build는 가능한 ephemeral agent에서 실행하고, controller executor는 0으로 두는 운영 모델을 검토합니다.
- administrator 권한, audit log, security advisory, backup retention을 정기적으로 검토합니다.

---

## 6. 정리

EC2에 Jenkins를 설치하는 작업은 package 설치에서 끝나지 않습니다. Java와 LTS repository를 확인한 뒤 controller의 영속 데이터, HTTPS 접근 경로, administrator 계정, build agent 격리를 함께 준비해야 복구와 권한 관리가 가능한 CI 기반이 됩니다.

---

## 7. Reference

- [Jenkins Docs - Installing Jenkins on Linux](https://www.jenkins.io/doc/book/installing/linux/)
- [Jenkins Docs - Java Support Policy](https://www.jenkins.io/doc/book/platform-information/support-policy-java/)
- [Jenkins Docs - Securing Jenkins](https://www.jenkins.io/doc/book/security/)

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
