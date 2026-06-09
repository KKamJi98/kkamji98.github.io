---
title: GCP (Google Cloud Platform) 이란?
date: 2026-02-17 09:00:00 +0900
author: kkamji
categories: [Cloud, GCP]
tags: [gcp, google-cloud, cloud, iaas, paas, gke, bigquery]
comments: true
image:
  path: /assets/img/gcp/gcp.webp
---

GCP를 처음부터 공부해 보기로 마음먹고 가장 먼저 정리한 것은 "GCP가 도대체 무엇인가"였습니다. 개별 서비스나 명령어를 외우기 전에, 이 플랫폼이 어떤 성격을 가졌고 무엇을 잘하는지 큰 그림을 그려두면 이후 학습이 훨씬 수월하기 때문입니다.
이번 포스트는 GCP 학습 시리즈의 출발점으로, GCP가 무엇이고 어떤 특징이 있으며 어떤 서비스들로 구성되는지, 그리고 GCP를 다루는 방법에는 무엇이 있는지를 개요 수준에서 정리합니다.

> **TL;DR**  
> - GCP(Google Cloud Platform)는 Google이 제공하는 퍼블릭 클라우드로, Google 서비스가 동작하는 동일한 글로벌 인프라 위에서 실행됩니다.  
> - 데이터 분석/AI(BigQuery, Vertex AI)와 Kubernetes(GKE)에 강점이 있고, 사용한 만큼 과금하는 모델을 따릅니다.  
> - Compute, Storage, Database, Networking, Data·AI, 운영 등 카테고리별 서비스로 구성됩니다.  
> - Console, gcloud CLI, Cloud Shell, API/Client Library로 다룰 수 있습니다.  
{: .prompt-info}

---

## 1. GCP란 무엇인가

**GCP(Google Cloud Platform)** 는 Google이 제공하는 퍼블릭 클라우드 서비스입니다. Google 검색, YouTube, Gmail 등을 운영하는 것과 **동일한 글로벌 인프라** 위에서 동작하며, 사용자는 이 인프라를 빌려 가상 머신, 스토리지, 데이터베이스, 네트워크 등을 필요한 만큼 사용할 수 있습니다.

- **IaaS**(가상 머신·네트워크 등 인프라)부터 **PaaS**(관리형 런타임·DB), **서버리스**, **데이터/AI** 서비스까지 폭넓게 제공합니다.
- **사용한 만큼 과금(pay-as-you-go)** 하는 모델이 기본이며, 미리 큰 자원을 사두지 않아도 됩니다.
- 전 세계에 배치된 **리전(Region)** 과 그 안의 **존(Zone)** 으로 인프라가 구성되어, 사용자와 가까운 위치에 리소스를 배포할 수 있습니다.

GCP는 AWS, Microsoft Azure와 함께 대표적인 메이저 퍼블릭 클라우드로 꼽힙니다. 이 시리즈에서는 GCP 자체의 개념과 사용법에 집중합니다.

---

## 2. GCP의 특징과 강점

GCP가 다른 클라우드와 구별되는 대표적인 강점은 다음과 같습니다.

- **글로벌 네트워크**: Google이 직접 소유·운영하는 전용 백본 네트워크를 사용해, 리전 간 트래픽이 공용 인터넷이 아닌 Google 내부망을 통해 전달됩니다.
- **데이터 분석과 AI/ML**: 서버리스 데이터 웨어하우스인 **BigQuery**, 머신러닝 플랫폼인 **Vertex AI** 등 데이터·AI 분야에서 강점을 가집니다.
- **Kubernetes**: Kubernetes는 본래 Google이 개발해 오픈소스로 공개한 프로젝트이며, **GKE(Google Kubernetes Engine)** 는 대표적인 관리형 Kubernetes 서비스입니다.
- **과금 모델**: 초 단위 과금, 일정 기간 이상 사용 시 자동 적용되는 **지속 사용 할인(Sustained Use Discount)**, 약정 기반 **약정 사용 할인(Committed Use Discount)** 등 비용 최적화 옵션을 제공합니다.

---

## 3. 주요 서비스 한눈에 보기

GCP의 서비스는 용도별 카테고리로 나뉩니다. 입문 단계에서 자주 마주치는 대표 서비스만 추려 정리하면 다음과 같습니다.

| 카테고리      | 대표 서비스                                       | 설명                                  |
| :------------ | :------------------------------------------------ | :------------------------------------ |
| Compute       | Compute Engine(GCE), GKE, Cloud Run               | 가상 머신, 관리형 Kubernetes, 서버리스 컨테이너 |
| Storage       | Cloud Storage(GCS)                                | 오브젝트 스토리지                     |
| Database      | Cloud SQL, Spanner, Firestore, Bigtable           | 관계형 / 글로벌 분산 / NoSQL          |
| Networking    | VPC, Cloud Load Balancing, Cloud DNS              | 가상 네트워크, 로드 밸런싱, DNS       |
| Data & AI     | BigQuery, Dataflow, Pub/Sub, Vertex AI            | 분석, 스트리밍/배치 처리, ML          |
| 운영 / 관측   | Cloud Logging, Cloud Monitoring, IAM              | 로깅, 모니터링, 권한 관리             |

> 위 표는 전체 서비스의 일부입니다. GCP에는 수백 개의 서비스가 있으며, 이 시리즈에서는 입문에 필요한 핵심 서비스부터 차례로 다룹니다.  
{: .prompt-info}

---

## 4. GCP를 다루는 방법

GCP 리소스는 여러 인터페이스로 제어할 수 있습니다. 상황에 맞게 골라 쓰면 됩니다.

| 방법                   | 설명                                                            |
| :--------------------- | :-------------------------------------------------------------- |
| Google Cloud Console   | 웹 기반 GUI. 리소스를 시각적으로 탐색·생성·관리                 |
| gcloud CLI (Cloud SDK) | 터미널에서 명령어로 리소스를 관리. 자동화·스크립팅에 적합       |
| Cloud Shell            | 브라우저에 내장된 터미널. gcloud, kubectl 등이 미리 설치되어 있음 |
| Client Library / API   | REST·gRPC API와 각 언어용 라이브러리로 코드에서 직접 제어       |

입문 단계에서는 Console로 전체 구조를 눈으로 익히고, 반복 작업이나 자동화는 gcloud CLI로 넘어가는 흐름이 일반적입니다.

---

## 5. Reference

- [Google Cloud Docs - Google Cloud overview](https://cloud.google.com/docs/overview)
- [Google Cloud Docs - Geography and regions](https://cloud.google.com/docs/geography-and-regions)
- [Google Cloud Docs - Google Cloud products](https://cloud.google.com/products)
- [Google Cloud Docs - gcloud CLI overview](https://cloud.google.com/sdk/gcloud)
- [Google Cloud Docs - Cloud Shell](https://cloud.google.com/shell/docs)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
