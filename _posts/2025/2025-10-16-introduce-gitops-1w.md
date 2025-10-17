---
title: GitOps를 활용한 Kubernetes CI/CD
date: 2025-10-16 06:22:31 +0900
author: kkamji
categories: [DevOps]
tags: [devops, argocd, gitops, ci-cd, vault, cloudnet, gasida, ci-cd-study, ci-cd-study-1w]
comments: true
image:
  path: /assets/img/ci-cd/ci-cd-study/ci-cd-study.webp
---

`CloudNet@` Gasida님이 진행하는 `CI/CD + ArgoCD + Vault Study` 를 진행하며 학습한 내용을 공유합니다.

이번 포스트에서는 *O'Reilly GitOps Cookbook* 의 1장에 해당 하는 **GitOps**에 대해 알아보겠습니다.

---

## 1. GitOps란?

**GitOps**란 Git 저장소를 단일 소스로 사용하여 선언적(Declarative)으로 인프라 및 애플리케이션의 상태를 지속적으로 동기화하며 관리하는 운영 방식입니다. **GitOps**는 Git, Kubernetes 및 CI/CD 솔루션 등으로 구축할 수 있습니다.

### 1.1. GitOps의 장점

- **표준 워크플로 (Standard workflow)**  
  애플리케이션 개발팀이 이미 익숙한 **Git 도구와 워크플로**(Branch, Pull Request, Merge 등)를 그대로 활용할 수 있습니다. 이를 통해 개발과 운영 간의 경계가 줄어들고, CI/CD 파이프라인이 자연스럽게 Git 기반으로 통합됩니다.

- **강화된 보안 (Enhanced security)**  
  모든 변경 사항은 **Git Commit과 Pull Request**를 통해 미리 검토되고 승인됩니다. 또한, 클러스터의 **예기치 않은 구성 변경(Drift)** 을 감지해 자동으로 복구(Reconcile)함으로써 보안성을 높입니다.

- **가시성 및 감사 (Visibility and audit)**  
  Git 저장소의 변경 이력이 곧 시스템의 변경 이력이므로, 누가 언제 어떤 리소스를 수정했는지 한눈에 파악할 수 있습니다. 따라서 **감사(Audit)** 와 **문제 추적(RCA)** 이 용이합니다.

- **멀티클러스터 일관성 (Multicluster consistency)**  
  여러 환경(개발·스테이징·운영)과 다수의 Kubernetes 클러스터에 대해, **동일한 선언적 정의를 반복 적용**함으로써 일관되고 안정적인 배포를 유지할 수 있습니다.

### 1.2. GitOps 3가지 원칙 (*O'Reilly GitOps Cookbook*)

- Git을 신뢰할 수 있는 단일 소스로 취급
- 모든 것을 코드로 표현
- 작업은 Git 워크플로(workflow)를 통해 수행

> [RedHat Developer - GitOps Cookbook: Kubernetes automation in practice](https://developers.redhat.com/articles/2022/12/20/gitops-cookbook-kubernetes-automation-practice)

### 1.3. GitOps 4가지 원칙 (*OpenGitOps* GitOps Principles v1.0.0)

- **1. Declarative**  
  GitOps로 관리되는 시스템은 원하는 상태(Desired State)를 선언적으로(Declaratively) 표현해야 합니다.

- **2. Versioned and Immutable**  
  원하는 상태는 변경 불가능(Immutable)하고 버전 관리가 가능한 방식으로 저장되어야 하며, 전체 변경 이력을 유지해야 합니다.

- **3. Pulled Automatically**  
  소프트웨어 에이전트는 원본(Source)으로부터 선언된 원하는 상태를 자동으로 가져와(Pull) 적용해야 합니다.

- **4. Continuously Reconciled**  
  에이전트는 실제 시스템 상태를 지속적으로 관찰하고(Observe), 원하는 상태로 일치하도록(Apply) 조정(Reconcile)해야 합니다.

> [OpenGitOps](https://opengitops.dev/)

---

## 2. Kubernetes에서 CI/CD

CI(Continuous Integration, 지속적 통합)와 CD(Continuous Delivery, 지속적 배포)는 앱 개발의 각 단계를 자동화하여 더 빠르고 안정적인 배포를 가능하게 하는 방법론입니다. CI/CD 파이프라인은 GitOps의 대표적인 활용 사례 중 하나입니다.

일반적인 CI/CD 파이프라인에서 CI 프로세스는 제출된 코드를 빌드하고 테스트하여 검증하며, CD 프로세스는 보안 정책, IaC(Infrastructure as Code), 애플리케이션 설정 등의 요구 사항을 자동으로 적용합니다. 이 과정에서 모든 변경 사항은 Git을 통해 버전 관리되므로, 변경 이력 추적과 롤백이 용이합니다. 이러한 Workflow는 아래와 같이 표현될 수 있습니다.

![CI/CD Workflow text](/assets/img/ci-cd/ci-cd-study/ci-cd-workflow.webp)
> CI/CD Workflow

Kubernetes를 활용하면 클러스터 내부에 CI/CD 파이프라인을 아래와 같은 구조로 쉽게 구현할 수 있습니다. CI 과정에서는 애플리케이션을 나타내는 컨테이너 이미지(Container Image)를 생성하여 컨테이너 이미지 저장소(Container Image Registry)에 저장하고, Pull-Request 등의 Git Workflow를 통해 배포할 앱의 명세(Manifest)파일을 변경한 후 CD 동기화 루프를 개시합니다.

![Application Deployment Model In Kubernetes](/assets/img/ci-cd/ci-cd-study/application-deploy-model-in-kubernetes.webp)
> Application Deployment Model In Kubernetes

---

## 3. Kubernetes에서 GitOps를 접목한 앱 배포

GitOps의 애플리케이션 배포 모델(Application Deployment Model)은 클러스터 내부(in-cluster)에 구축될 수도 있고 여러 클러스터(multi-cluster)에 걸친 공통 플랫폼 형태로 구축될 수 있습니다. GitOps 엔진은 CI/CD 파이프라인의 CD(Continuous Delivery)부분을 담당하여 네 가지 주요 작업으로 구성된 GitOps Lifecycle을 구현합니다,

### 3.1. Kubernetes에서 GitOps Lifecycle

Kubernetes GitOps Lifecycle은 다음과 같은 순서로 구성되며, 모든 단계는 Git 저장소를 단일 신뢰 소스(Single Source of Truth) 로 사용하고 Git 워크플로(Git Workflow)를 통해 수행됩니다.

![GitOps Lifecycle](/assets/img/ci-cd/ci-cd-study/gitops-lifecycle.webp)
> GitOps Lifecycle

1. Deploy
  Git에 저장된 Manifest를 배포
2. Monitoring
  Git 저장소나 클러스터의 상태 모니터링
3. Drift Detection
  Git에 저장된 내용과 클러스터 상태 차이 감지
4. Take Action
  Git에 저장된 내용을 클러스터에 반영 (Rollback or 3-way-diff)

> **3-way-diff**  
> Git에 저장된 선언적 상태, 현재 클러스터 상태, 그리고 직전 배포 시점의 상태 세 가지를 비교하여 어떤 변경이 발생했는지를 정확히 판별하고, 충돌 없이 안전하게 클러스터를 Git 상태로 되돌리는 방식  
{: .prompt-tip}

### 3.2. Kubernetes에서 GitOps Project의 구조

Kubernetes에서 GitOps 접근법을 사용해 애플리케이션을 배포하기 위해서는 최소 2개의 Git Repository가 필요합니다.

하나는 애플리케이션 소스 코드를 보관하기 위해 사용하고, 다른 하나는 앱의 배포 형상을 기술하는 Kubernetes Manifest 파일들을 보관하기 위해 사용합니다.

![Kubernetes GitOps Loop](/assets/img/ci-cd/ci-cd-study/kubernetes-gitops-loop.webp)
> Kubernetes GitOps Loop


> **Kubernetes GitOps Loop의 중요 항목 5 가지**  
>
> 1. 앱 소스 코드 저장소 App source code repository  
> 2. 컨테이너 이미지를 만드는 CI 파이프라인 CI pipeline creating a container image  
> 3. 컨테이너 이미지 저장소 Container image registry  
> 4. 쿠버네티스 매니페스트 저장소 Kubernetes manifests repository  
> 5. 매니페스트를 하나 이상의 클러스터에 동기화하고 변화를 감지하는 GitOps 엔진  
{: .prompt-tip}

---

## 4. 데브옵스 및 기민성(Agility)

GitOps는 지속적 배포 및 인프라 운영을 위한 개발자 중심의 접근법이며, 프로세스 자동화를 위해 Git을 사용하는 개발자 Workflow 입니다. DevOps가 Agile Software Develop Process를 보완한다면, GitOps는 인프라 자동화 및 애플리케이션 Lifecycle 관리 측면에서 DevOps를 보완합니다.

Agile 방법론의 가장 중요한 점 가운데 하나는 납기(lead time)을 줄이는 것입니다. 납기란 요구 사항을 식별하고 이를 충족하는데까지 걸리는 시간을 말하며, 납기를 줄이기 위해서는 IT 조직 문화와 개발 문화는 DevOps 및 GitOps 환경에 친화적으로 변화해야 합니다.

- 애플리케이션을 실시간으로 배포하고 관찰할 수 있을 때, 개발자는 피드백 루프를 통해 코드를 빠르게 개선할 수 있습니다.
- DevOps가 문화적 변화로 자리 잡았듯이, GitOps 역시 조직 문화 전반에 스며들어야 합니다.
- 모든 애플리케이션 배포와 인프라 변경은 Git 워크플로를 통한 코드 기반 변경으로 수행되어야 하며,
이를 통해 신뢰성과 재현성을 확보할 수 있습니다.

---

## 5. 마무리

GitOps는 단순한 배포 자동화 도구가 아니라, 개발과 운영 전반을 Git 기반으로 통합하는 문화적 접근 방식입니다. 모든 변경 사항을 Git으로 관리하고 선언적 상태를 지속적으로 동기화함으로써, 조직은 더 빠르고 안정적이며 감사 가능한 운영 체계를 구축할 수 있습니다.

DevOps가 협업과 자동화를 중심으로 소프트웨어 개발을 진화시켰다면, GitOps는 그 철학을 인프라와 애플리케이션 운영 전반으로 확장시킨 모델이라 할 수 있습니다.

---

## 6. Reference

- [O’Reilly GitOps Cookbook: Kubernetes Automation in Practice](https://product.kyobobook.co.kr/detail/S000214781090)
- [RedHat Developer - GitOps Cookbook: Kubernetes automation in practice](https://developers.redhat.com/articles/2022/12/20/gitops-cookbook-kubernetes-automation-practice)
- [CNCF - Introduce OpenGitOps](https://www.cncf.io/projects/opengitops/)
- [OpenGitOps](https://opengitops.dev/)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
