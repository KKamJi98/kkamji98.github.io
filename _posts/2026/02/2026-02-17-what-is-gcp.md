---
title: GCP (Google Cloud Platform) 개요
date: 2026-02-17 09:00:00 +0900
author: kkamji
categories: [Cloud, GCP]
tags: [gcp, google-cloud, cloud, iaas, paas, gke, bigquery]
comments: true
image:
  path: /assets/img/gcp/gcp.webp
---

GCP를 처음부터 공부해 보기로 마음먹고 가장 먼저 정리한 것은 "GCP가 도대체 무엇인가"였습니다. 개별 서비스나 명령어를 외우기 전에, 이 플랫폼이 어떤 성격을 가졌고 무엇을 잘하는지 큰 그림을 그려두면 이후 학습이 훨씬 수월하기 때문입니다.
이번 포스트는 GCP 학습 시리즈의 출발점으로, GCP가 무엇이고 어떤 특징이 있으며 어떤 서비스들로 구성되는지, 그리고 GCP를 다루는 방법에는 무엇이 있는지를 개요 수준에서 정리합니다. 개요를 잡은 뒤에는 [리소스 계층(Organization/Folder/Project) 글](/posts/gcp-resource-hierarchy/)과 [IAM 글](/posts/gcp-iam/)로 이어집니다.

> **TL;DR**  
> - GCP(Google Cloud Platform)는 Google이 제공하는 퍼블릭 클라우드로, Google 서비스가 동작하는 동일한 글로벌 인프라 위에서 실행됩니다.  
> - 데이터 분석/AI(BigQuery, Vertex AI)와 Kubernetes(GKE)에 강점이 있고, 사용한 만큼 과금하는 모델을 따릅니다.  
> - Compute, Storage, Database, Networking, Data,AI, 운영 등 카테고리별 서비스로 구성됩니다.  
> - Console, gcloud CLI, Cloud Shell, API/Client Library로 다룰 수 있습니다.  
{: .prompt-info}

---

## 1. GCP란 무엇인가

**GCP(Google Cloud Platform)** 는 Google이 제공하는 퍼블릭 클라우드 서비스입니다. Google 검색, YouTube, Gmail 등을 운영하는 것과 **동일한 글로벌 인프라** 위에서 동작하며, 사용자는 이 인프라를 빌려 가상 머신, 스토리지, 데이터베이스, 네트워크 등을 필요한 만큼 사용할 수 있습니다.

- **IaaS**(가상 머신,네트워크 등 인프라)부터 **PaaS**(관리형 런타임,DB), **서버리스**, **데이터/AI** 서비스까지 폭넓게 제공합니다.
- **사용한 만큼 과금(pay-as-you-go)** 하는 모델이 기본이며, 미리 큰 자원을 사두지 않아도 됩니다.
- 전 세계에 배치된 **리전(Region)** 과 그 안의 **존(Zone)** 으로 인프라가 구성되어, 사용자와 가까운 위치에 리소스를 배포할 수 있습니다.

![GCP Region과 Zone 구조](/assets/img/gcp/gcp-region-zone.webp)
_Region은 독립된 지리적 영역, Zone은 그 안의 격리된 장애 도메인. Region 간은 Premium Tier 백본으로 연결되고, 가용성을 위해 여러 Zone에 분산 배치한다._

GCP는 AWS, Microsoft Azure와 함께 대표적인 메이저 퍼블릭 클라우드로 꼽힙니다. 이 시리즈에서는 GCP 자체의 개념과 사용법에 집중합니다.

---

## 2. GCP의 특징과 강점

GCP가 다른 클라우드와 구별되는 대표적인 강점은 다음과 같습니다.

- **글로벌 네트워크**: Google이 직접 소유,운영하는 전용 백본 네트워크를 사용해, 기본값인 Premium Tier에서는 트래픽이 공용 인터넷이 아닌 Google 내부망을 통해 전달됩니다. [Network Service Tiers 문서](https://cloud.google.com/network-tiers/docs/overview)는 Premium Tier를 다음과 같이 설명합니다.

> Premium Tier delivers traffic from external systems to Google Cloud resources by using Google's low latency, highly reliable global network. This network consists of an extensive private fiber network with over 200 points of presence (PoPs) around the globe.  

- **데이터 분석과 AI/ML**: 서버리스 데이터 웨어하우스인 **BigQuery**, 머신러닝 플랫폼인 **Vertex AI** 등 데이터,AI 분야에서 강점을 가집니다.
- **Kubernetes**: Kubernetes는 본래 Google이 개발해 오픈소스로 공개한 프로젝트이며, **GKE(Google Kubernetes Engine)** 는 대표적인 관리형 Kubernetes 서비스입니다.
- **과금 모델**: 초 단위 과금, 일정 기간 이상 사용 시 자동 적용되는 **지속 사용 할인(Sustained Use Discount, SUD)**, 약정 기반 **약정 사용 할인(Committed Use Discount, CUD)** 등 비용 최적화 옵션을 제공합니다.
  - SUD는 별도 신청 없이 사용량에 따라 자동 적용됩니다. [Sustained use discounts 문서](https://cloud.google.com/compute/docs/sustained-use-discounts)는 다음과 같이 설명합니다.

    > Whenever you use an applicable resource for more than a fourth of a billing month, you automatically receive a discount for every incremental hour that you continue to use that resource.

  - CUD는 1년 또는 3년 약정을 맺고 할인된 가격을 적용받는 방식입니다. [Committed use discounts 문서](https://cloud.google.com/compute/docs/instances/committed-use-discounts-overview)의 설명은 다음과 같습니다.

    > When you purchase a commitment, you commit either to a minimum amount of resource usage or to a minimum spend amount for a specified term duration of one or three years.

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
| Google Cloud Console   | 웹 기반 GUI. 리소스를 시각적으로 탐색,생성,관리                 |
| gcloud CLI (Cloud SDK) | 터미널에서 명령어로 리소스를 관리. 자동화,스크립팅에 적합       |
| Cloud Shell            | 브라우저에 내장된 터미널. gcloud, kubectl 등이 미리 설치되어 있음 |
| Client Library / API   | REST,gRPC API와 각 언어용 라이브러리로 코드에서 직접 제어       |

입문 단계에서는 Console로 전체 구조를 눈으로 익히고, 반복 작업이나 자동화는 gcloud CLI로 넘어가는 흐름이 일반적입니다.

![GCP 접근 방법 스택](/assets/img/gcp/gcp-access-stack.webp)
_Console / gcloud / Cloud Shell / Client Library는 모두 동일한 Google Cloud API(REST/gRPC) 위의 프런트엔드다. 어떤 도구로 다루든 결국 같은 API를 호출한다._

gcloud CLI를 처음 쓸 때 가장 먼저 마주치는 명령은 인증과 기본 설정입니다. 아래는 로그인하고 작업 대상 프로젝트와 기본 리전을 지정하는 예시입니다.

```bash
# 사용자 계정으로 로그인 (브라우저 인증)
gcloud auth login

# 이후 명령에 사용할 기본 프로젝트 지정
gcloud config set project my-project-id

# Compute Engine 기본 리전 지정
gcloud config set compute/region asia-northeast3

# 현재 설정 확인
gcloud config list
```

각 명령의 옵션과 더 많은 사용 예시는 별도 정리한 [gcloud 치트시트](/posts/gcloud-cheat-sheet/)에서 다룹니다.

> **리전 선택 시 주의**  
> 리전은 한 번 정하면 바꾸기 번거로운 결정이므로 처음에 신중히 고릅니다. 두 가지를 같이 봐야 합니다.  
> - **지연 시간(latency)**: 사용자(또는 호출하는 다른 서비스)와 가까운 리전을 골라야 왕복 지연이 줄어듭니다. 예를 들어 한국 사용자 대상 서비스라면 `asia-northeast3`(서울)가 유리합니다.  
> - **가격**: 동일한 리소스라도 리전마다 단가가 다릅니다. 가까운 리전이 항상 가장 저렴하지는 않으므로, 지연 시간과 비용을 함께 따져 결정합니다.  
{: .prompt-warning}

---

## 5. 다음 글

이 개요에서 잡은 큰 그림을 바탕으로, 시리즈는 다음 순서로 이어집니다.

1. [GCP 리소스 계층 알아보기 - Organization, Folder, Project](/posts/gcp-resource-hierarchy/): 리소스가 어떤 계층으로 묶이고 권한/정책/결제가 어디에 적용되는지 정리합니다.
2. [GCP IAM 알아보기 - Principal, Role, Policy, Service Account](/posts/gcp-iam/): 리소스 계층 위에서 동작하는 권한 체계를 다룹니다.

---

## 6. Reference

- [Google Cloud Docs - Google Cloud overview](https://cloud.google.com/docs/overview)
- [Google Cloud Docs - Geography and regions](https://cloud.google.com/docs/geography-and-regions)
- [Google Cloud Docs - Google Cloud products](https://cloud.google.com/products)
- [Google Cloud Docs - gcloud CLI overview](https://cloud.google.com/sdk/gcloud)
- [Google Cloud Docs - Cloud Shell](https://cloud.google.com/shell/docs)
- [Google Cloud Docs - Network Service Tiers overview](https://cloud.google.com/network-tiers/docs/overview)
- [Google Cloud Docs - Sustained use discounts](https://cloud.google.com/compute/docs/sustained-use-discounts)
- [Google Cloud Docs - Committed use discounts](https://cloud.google.com/compute/docs/instances/committed-use-discounts-overview)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
