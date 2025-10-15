---
title: GitOps 소개 - [CI/CD Study 1주차]
date: 2025-10-16 06:22:31 +0900
author: kkamji
categories: [DevOps]
tags: [devops, argocd, gitops, ci-cd, vault, cloudnet, gasida, ci-cd-study, ci-cd-study-1w]
comments: true
image:
  path: /assets/img/ci-cd/ci-cd-study/ci-cd-study.webp
---

이번 포스트에서는 GitOps에 대해 알아보겠습니다.

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

## 2. Reference

- [CNCF - Introduce OpenGitOps](https://www.cncf.io/projects/opengitops/)
- [OpenGitOps](https://opengitops.dev/)
- [RedHat Developer - GitOps Cookbook: Kubernetes automation in practice](https://developers.redhat.com/articles/2022/12/20/gitops-cookbook-kubernetes-automation-practice)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
