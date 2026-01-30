---
title: Kubernetes Pod로 Jenkins Agent 구성하기
date: 2024-10-21 00:30:21 +0900
author: kkamji
categories: [CI/CD, Jenkins]
tags: [kubernetes, jenkins, pod, agent, jnlp, jenkins-agent]     # TAG names should always be lowercase
comments: true
image:
  path: /assets/img/ci-cd/jenkins/jenkins.webp
---

WhaTap과 [Kubernetes Pod로 Jenkins Agent 동적 생성하기](https://www.whatap.io/bbs/board.php?bo_table=blog&wr_id=34&page=9) 인프랩의 [EC2 Spot Instance를 활용한 Jenkins 기반의 CI/CD 구축 사례](https://aws.amazon.com/ko/blogs/tech/inflab-ec2-spot-instance/) 사례를 통해 Jenkins **Master-Agent** 구성에 대해 접하게 되었습니다.

**Master-Agent** 구성이란 **빌드와 배포 작업을 분리**하고 **리소스 분산**을 통한 효율적이고 확장 가능한 CI/CD 환경을 제공하는 방식입니다. 이를 통해 **Jenkins Master**가 병목 현상을 피하고, 여러 작업을 동시에 병렬로 수행할 수 있게 되어 성능이 크게 향상될 수 있습니다.

특히 고가용성(HA)을 요구하는 환경에서 **Master-Agent** 구성은 필수적이라고 생각합니다. 최근 기술 면접에서 Jenkins Agent 구성에 대한 질문을 받게 되었습니다. 이 경험을 통해 Jenkins Master-Agent 구성의 중요성을 다시 한번 깨닫게 되었습니다. 이에 따라 Jenkins **Master-Agent** 환경을 직접 구축하고 정리하는 과정을 통해 여러분께 효율적이고 확장 가능한 Jenkins 환경을 구축하는 방법에 대한 제 경험과 배움을 공유하고자 합니다.

---

## 1. 사전 준비 사항

- Kubernetes Cluster
- Jenkins Server
- Jenkins Server에서 Kubernetes Cluster에 접근

---

## 2. Jenkins에 Kubernetes Plugin 설치

> Dashboard -> Jenkins 관리 -> Plugins -> Available plugins에 접속후 Kubernetes Plugin을 설치합니다.
{: .prompt-tip}

![Install Kubernetes Plugin](/assets/img/ci-cd/jenkins/kubernetes-plugin.png)

> 의존성에 포함된 Kubernetes Client API, Authentication Tokens API 등의 플러그인도 함께 설치된 것을 확인할 수 있습니다.
{: .prompt-tip}

![Kubernetes Plugin Dependency](/assets/img/ci-cd/jenkins/kubernetes-plugin-dependency.png)

---

## 3. Jenkins에 kubeconfig 파일 등록

> Jenkins가 Kubernetes에 접근하기 위해서는 접근 권한이 있는 Service Account 또는 kubeconfig가 Jenkins Credential에 등록되어 있어야 합니다.
> Dashboard -> Jenkins 관리 -> Credentials 에 접속 후 kubeconfig 파일을 Jenkins Credential에 등록해줍니다.
> 보통 대부분의 경우 kubeconfig 파일은 `~/.kube/kubeconfig` 혹은 `~/.kube/config`에 위치합니다.
{: .prompt-tip}

![kubeconfig](/assets/img/ci-cd/jenkins/kube-config-credential.png)

---

## 4. Jenkins에서 Kubernetes 클라우드 설정

> Dashboard -> Jenkins 관리 -> Clouds -> New cloud에 접속 후 Kubernetes Type의 Cloud를 생성합니다.
{: .prompt-tip}

![New Cloud](/assets/img/ci-cd/jenkins/new-cloud.png)

> Jenkins Master가 Kubernetes Api-Server에 접근할 수 있도록 생성한 Jenkins Credential과 Kubernetes Cluster에 대한 정보를 기입합니다.
{: .prompt-tip}

![Jenkins Connect Kubernetes](/assets/img/ci-cd/jenkins/jenkins-connect-kubernetes.png)

> Test Connection을 눌러 기입한 정보를 기반으로 Jenkins가 Kubernetes와 통신이 가능한지 확인합니다.
> Jenkins URL에는 Agent들이 Jenkins Master와 통신하기 위한 URL을 적어줍니다.
{: .prompt-tip}
> **주의사항**
> Jenkins Agent는 Jenkins Master와 통신을 위해 `JNLP(Java Network Launching Protocol)` 포트인 **50000번 포트**가 열려 있어야 합니다.
> 이 부분을 그냥 지나치신다면.. 저와 같이 많은 시간을 트러블 슈팅에 사용하시게 될 수도 있습니다...
{: .prompt-danger}

![Jenkins Test Connection](/assets/img/ci-cd/jenkins/test-connection.png)

> Connection Timeout, Concurrency Limit 등의 다른 옵션은 목적과 요구사항에 맞는 정보를 채워 넣고 Save 버튼을 클릭해 설정을 저장합니다.
{: .prompt-tip}

![Save](/assets/img/ci-cd/jenkins/kubernetes-cloud-save.png)

---

## 5. Pod Template 추가

> Jenkins가 Kubernetes Cluster 내에서 Agent를 Pod 형태로 동적 생성할 수 있도록 Pod Template를 생성해야합니다.
> Dashboard -> Clouds -> Kubernetes -> Pod Templates에 접속 후 Add a pod template를 누릅니다.
{: .prompt-tip}

![Add Pod a Template](/assets/img/ci-cd/jenkins/add-pod-template.png)

### 5.1. Pod Template 설정

> 요구사항에 따라 Agent로 실행되는 Pod에 대한 설정을 해줍니다. 각각의 옵션에 대한 자세한 설명은 옵션을 기입하는 오른쪽 **?(물음표)** 표시를 클릭하면 확인할 수 있습니다.
> Usage 옵션을 통해 특정 라벨과 일치하는 노드에서만 Agent Pod가 생성되도록 할 수도 있으며 Container를 추가해 하나의 Pod에 여러 Container가 포함되도록 설정할 수도 있습니다.
{: .prompt-tip}

![New Pod Template Setting 1](/assets/img/ci-cd/jenkins/new-pod-template-setting-1.png)
![New Pod Template Setting 2](/assets/img/ci-cd/jenkins/new-pod-template-setting-2.png)

---

## 6. 테스트

> Kubernetes Agent를 사용하도록 테스트 파이프라인을 생성해 정상 동작 여부를 해보겠습니다.
{: .prompt-tip}

![Test Pipeline Script](/assets/img/ci-cd/jenkins/test-pipeline-script.png)

> 위의 파이프라인을 동작시켜 보겠습니다.
{: .prompt-tip}

![Check Generate Agent](/assets/img/ci-cd/jenkins/check-generate-agent.png)

```bash
❯ k get pods --watch
NAME        READY   STATUS    RESTARTS        AGE
jenkins-0   1/1     Running   1 (7h55m ago)   32h
jnlp-agent-qzw70   0/1     Pending   0               0s
jnlp-agent-qzw70   0/1     Pending   0               0s
jnlp-agent-qzw70   0/1     ContainerCreating   0               1s
jnlp-agent-qzw70   0/1     ContainerCreating   0               2s
jnlp-agent-qzw70   1/1     Running             0               4s
jnlp-agent-qzw70   1/1     Terminating         0               16s
jnlp-agent-qzw70   1/1     Terminating         0               18s
jnlp-agent-qzw70   0/1     Terminating         0               19s
jnlp-agent-qzw70   0/1     Terminating         0               19s
jnlp-agent-qzw70   0/1     Terminating         0               20s
jnlp-agent-qzw70   0/1     Terminating         0               20s
```
> 파이프라인이 동작 여부에 따라 jnlp agent pod가 동적으로 생성되고 제거되는 것을 확인할 수 있습니다.
{: .prompt-tip}

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
