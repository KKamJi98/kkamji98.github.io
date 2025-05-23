---
title: Type 1 & Type 2 가상화의 개념
date: 2024-04-01 21:54:36 +0900
author: kkamji
categories: [CS, Virtualization]
tags: [virtualization, docker, k8s, container, vm, vmware, type-1-virtualization, type-2-virtualization, hypervisor]     # TAG names should always be lowercase
comments: true
image:
  path: https://github.com/kkamji98/kkamji98.github.io/assets/72260110/0794e0e2-b08e-4cc5-b640-c975f5a1a7b7
---


> Type 1과 Type 2 가상화는 하이퍼바이저 기반의 가상화 접근 방식을 구분짓는 두 가지 주요 유형입니다. 이 두 가지 유형은 각각 다른 방식으로 하드웨어 상에서 가상 머신(VM)을 실행합니다.  
> 이러한 차이점은 성능, 사용 용도, 그리고 보안 측면에서 중요한 영향을 미칩니다.
{: .prompt-info}

---

## Type 1 가상화(베어 메탈 가상화)

- 정의
  - 하드웨어 상에 직접 설치되며, 운영 체제 위에 구축되지 않습니다.
- 특징
  - 높은 성능과 효율성을 제공합니다. 직접 하드웨어를 관리하므로, 오버헤드가 적고 가상 머신 간의 성능 격리가 우수합니다.
- 사용 사례
  - 서버 가상화 및 고성능이 요구되는 엔터프라이즈 환경에서 사용도비니다.
  - VMware ESXi, Microsoft Hyper-V, Xen 등이 있습니다.

---

## Type 2 가상화(호스트된 가상화)

- 정의
  - 기존 운영 체제 위에 소프트웨어로 설치되어 실행됩니다.
  - 호스트 운영 체제상에서 작동하며, 가상 머신을 관리합니다.
- 특징
  - 설치와 관리가 비교적 쉽지만, Type 1에 비해 성능 오버헤드가 큽니다.
  - 호스트 OS를 통해 하드웨어 자원에 접근하기 때문에, 성능이 저해될 수 있습니다.
- 사용 사례
  - 테스트 환경, 개발 환경, 교육 목적
  - VMware Workstation, Oracle VirtualBox, Parallels Desktop 등이 있습니다.

---

## 정리

> Type 1 가상화와 Type 2 가상화의 가장 큰 차이점은 하이퍼바이저의 작동 방식에 있습니다.  
>  
> Type 1 가상화에서 하이퍼바이저는 하드웨어 위에 직접 설치되고, 이로 인해 운영 체제(OS) 없이 독립적으로 실행됩니다.  
>  
> Type 2 가상화에서 하이퍼바이저는 호스트 운영 체제 위에 소프트웨어로 설치됩니다. 따라서 호스트 OS의 서비스와 자원을 사용하여 가상 머신을 실행합니다.  
{: .prompt-info}
> **궁금하신 점이나 추가해야할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKam.\_\.Ji](https://www.linkedin.com/in/taejikim/)**
{: .prompt-tip}
