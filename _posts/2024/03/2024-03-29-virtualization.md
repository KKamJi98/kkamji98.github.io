---
title: 가상화(Virtualization)의 종류와 개념
date: 2024-03-29 21:53:31 +0900
author: kkamji
categories: [CS, Virtualization]
tags: [virtualization, docker, k8s, container, vm, vmware]     # TAG names should always be lowercase
comments: true
# image:
# path: /assets/img/kkam-img/kkam.webp
---

![Virtualization model](/assets/img/virtualization/virtualization-model.webp)

가상화라는 말은 대개 서버 가상화를 가리키는 말로 쓰이지만, 실제로는 하드웨어부터 네트워크, 스토리지, 데스크탑, 애플리케이션, 데이터까지 계층마다 각각의 가상화가 있습니다. 계층이 다르면 얻는 것과 잃는 것도 달라집니다. 어떤 종류가 있고 각각 무엇을 추상화하는지 정리합니다.

---

## 1. 가상화란?

가상화란 IT 인프라의 여러 측면을 추상화해서 최적화하는 기술입니다.  
자원 활용도를 높이고, 운영 비용을 절감하며, 시스템의 유연성과 확장성을 강화합니다.
{: .prompt-info}

---

## 2. 가상화의 종류

### 2.1. 서버 가상화

하나의 물리적 서버를 여러 개의 독립적인 가상 서버로 분할합니다. 각 서버는 고유의 운영 체제와 애플리케이션을 실행하며, 물리적 자원을 동적으로 할당받습니다.  
자원 활용도가 올라가고, 서버 관리와 배포도 더 효율적입니다.

### 2.2. 네트워크 가상화

물리적 네트워크 리소스를 추상화해서 여러 개의 독립된 가상 네트워크를 만듭니다.  
이 가상 네트워크는 물리적 네트워크의 제약 없이 구성되고, 보안, 속도, 자원 할당을 개별적으로 관리합니다. 멀티테넌시 환경과 복잡한 데이터 센터 관리에 유용합니다.

### 2.3. 스토리지 가상화

물리적 스토리지 자원을 하나의 가상 스토리지 풀로 묶어 관리합니다.  
스토리지 자원의 할당과 관리가 유연해지고, 데이터 마이그레이션, 백업, 복구 작업도 간소화됩니다.

### 2.4. 데스크탑 가상화

사용자의 데스크탑 환경을 서버에서 가상화해 제공합니다. 사용자는 어느 위치에서든, 어떤 장치를 쓰든 자신의 데스크탑 환경에 접근합니다.  
원격 근무 지원, IT 자원의 중앙 관리, 디바이스 독립성이 여기서 나옵니다.

### 2.5. 애플리케이션 가상화

애플리케이션을 클라이언트 머신에 직접 설치하지 않고 실행합니다. 애플리케이션은 서버에서 실행되고, 사용자는 네트워크로 애플리케이션에 접근합니다.  
배포와 관리가 간단해지고, 소프트웨어 호환성 문제도 함께 해결합니다.

### 2.6. 데이터 가상화

데이터 가상화는 여러 소스의 데이터를 단일 인터페이스나 "가상" 데이터베이스로 통합해 관리합니다.  
사용자는 여러 데이터 소스를 직접 연결하지 않고 필요한 정보에 접근합니다. 데이터 통합, 실시간 데이터 액세스, 데이터 품질 관리에 유용합니다.

---

## 3. Reference

- [Red Hat - What is virtualization?](https://www.redhat.com/en/topics/virtualization/what-is-virtualization)
- [IBM - What is virtualization?](https://www.ibm.com/think/topics/virtualization)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
