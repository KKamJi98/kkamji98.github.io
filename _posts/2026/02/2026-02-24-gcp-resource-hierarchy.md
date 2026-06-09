---
title: GCP 리소스 계층 알아보기 - Organization, Folder, Project
date: 2026-02-24 12:00:00 +0900
author: kkamji
categories: [Cloud, GCP]
tags: [gcp, google-cloud, organization, folder, project, iam, resource-hierarchy]
comments: true
image:
  path: /assets/img/gcp/gcp.webp
---

GCP를 처음 공부하기 시작하면서 가장 먼저 마주친 개념이 리소스 계층(Resource Hierarchy)이었습니다. 클라우드 콘솔에 들어가 프로젝트를 만들려는 순간부터 `Organization`, `Folder`, `Project`라는 단어가 등장하는데, 이 구조를 이해하지 못하면 IAM 권한이나 결제(Billing), 조직 정책이 어디에 어떻게 적용되는지 감을 잡기 어렵습니다.
GCP에서는 거의 모든 리소스와 권한이 이 계층에 상속(Inheritance) 형태로 붙기 때문에, 이 골격을 먼저 정리하는 것이 GCP 학습의 출발점이라고 생각합니다.
이번 포스트에서는 GCP 리소스 계층의 4단계 구조와 각 단계의 역할, 권한이 상속되는 방식을 정리하고, gcloud로 프로젝트를 다뤄보는 것까지 알아보겠습니다.

> **TL;DR**  
> - GCP 리소스 계층은 `Organization > Folder > Project > Resource` 4단계로 구성됩니다.  
> - IAM 정책과 조직 정책(Organization Policy)은 상위 노드에서 하위로 상속됩니다.  
> - 모든 리소스는 반드시 하나의 Project에 속하며, Project가 결제/권한/API의 기본 경계입니다.  
> - Folder는 Organization이 있어야만 생성할 수 있어, 개인 Gmail 계정에는 독립 Project만 존재합니다.  
{: .prompt-info}

---

## 1. GCP 리소스 계층 한눈에 보기

GCP의 모든 리소스는 트리(Tree) 형태의 계층 안에 배치됩니다. 최상위부터 `Organization > Folder > Project > Resource` 순서이며, 위에서 아래로 권한과 정책이 흘러내려 갑니다.

![GCP 리소스 계층 - Organization, Folder, Project, Resource](/assets/img/gcp/gcp-resource-hierarchy.webp)

| 계층         | 필수 여부              | 역할                                      |
| :----------- | :--------------------- | :---------------------------------------- |
| Organization | 선택 (조직 계정 시 자동) | 회사/도메인 단위의 최상위 노드            |
| Folder       | 선택, 중첩 가능        | 부서/팀/환경 단위 그룹화                  |
| Project      | 필수                   | 모든 리소스/결제/권한의 기본 경계         |
| Resource     | -                      | 실제 서비스 리소스 (GCE, GCS, GKE 등)     |

핵심은 **모든 리소스가 반드시 하나의 Project에 속한다**는 점과, **상위 노드에 적용한 권한/정책이 하위로 상속된다**는 점입니다. 이 두 가지만 기억하면 나머지 개념은 자연스럽게 따라옵니다.

---

## 2. Organization - 계층의 최상위 노드

`Organization`은 리소스 계층의 가장 위에 있는 노드로, 회사나 도메인 전체를 대표합니다. 예를 들어 `example.com` 도메인을 사용하는 조직이라면 그 도메인에 대응하는 하나의 Organization이 생성됩니다.

Organization은 직접 "만드는" 것이 아니라, **Google Workspace** 또는 **Cloud Identity** 계정이 GCP와 연결될 때 자동으로 생성됩니다. 따라서 개인 Gmail 계정만으로는 Organization 노드가 존재하지 않습니다.

- 조직 전체에 공통으로 적용할 IAM 정책이나 조직 정책을 이 레벨에 설정합니다.
- 여기에 설정한 권한은 산하의 모든 Folder와 Project로 상속됩니다.
- 조직 관리자(Organization Admin)는 계층 전체에 대한 통제권을 가집니다.

> Organization 레벨에 부여한 권한은 하위 전체에 영향을 미치므로, 최소 권한 원칙(Least Privilege)에 따라 신중하게 부여해야 합니다.  
{: .prompt-warning}

---

## 3. Folder - 그룹화 단위

`Folder`는 Organization 아래에서 여러 Project나 다른 Folder를 묶는 그룹화 단위입니다. AWS의 조직 구조에 익숙하다면 "묶음을 만들고 그 묶음 단위로 정책을 거는" 개념이 익숙할 텐데, GCP에서는 그 역할을 Folder가 담당합니다.

- 부서(`engineering`, `finance`)나 환경(`prod`, `staging`, `dev`) 단위로 구성하는 경우가 많습니다.
- Folder는 다른 Folder를 포함할 수 있어 **중첩(Nesting)이 가능**합니다 (최대 10단계).
- Folder에 설정한 정책은 그 안의 모든 하위 Folder와 Project로 상속됩니다.

![GCP Organization, Folder, Project 구성 예시](/assets/img/gcp/gcp-org-tree.webp)

> Folder는 **Organization이 존재할 때만** 생성할 수 있습니다. 개인 계정에는 Organization이 없으므로 Folder도 만들 수 없습니다.  
{: .prompt-tip}

---

## 4. Project - 모든 것의 기본 단위

`Project`는 GCP에서 가장 핵심적인 단위입니다. GCE 인스턴스, GCS 버킷, GKE 클러스터 등 **모든 리소스는 반드시 하나의 Project에 속하며**, API 활성화, 결제 계정 연결, 권한 부여가 모두 Project 단위로 이루어집니다.

Project는 서로 다른 세 가지 식별자를 가집니다. 이 셋의 차이를 헷갈리기 쉬우니 정리하고 넘어가겠습니다.

| 식별자         | 설명                              | 변경 가능        | 예시                      |
| :------------- | :-------------------------------- | :--------------- | :------------------------ |
| Project name   | 사람이 읽기 쉬운 표시 이름        | 가능             | `My First Project`        |
| Project ID     | 전역에서 고유, CLI/API에서 사용   | 불가 (생성 후 고정) | `my-first-project-461203` |
| Project number | GCP가 자동 부여하는 고유 숫자     | 불가             | `123456789012`            |

- **Project ID**는 전역(Global)에서 유일해야 하며, 6자 이상 30자 이하의 소문자/숫자/하이픈으로 구성됩니다. 한 번 정하면 바꿀 수 없으므로 생성 시 신중하게 정해야 합니다.
- **Project number**는 사용자가 지정하지 않으며 GCP가 자동으로 발급합니다. 일부 API나 IAM 바인딩에서 내부적으로 사용됩니다.
- **Project name**은 콘솔에 표시되는 이름으로, 언제든 변경할 수 있고 고유할 필요도 없습니다.

---

## 5. IAM과 정책 상속 (맛보기)

리소스 계층을 이해해야 하는 가장 큰 이유는 **권한과 정책이 이 계층을 따라 상속되기 때문**입니다. 이 절에서는 핵심 개념만 짚고, 자세한 IAM 내용은 다음 포스트에서 다루겠습니다.

### 5.1. IAM 정책 상속

IAM 정책(누가 무엇을 할 수 있는가)은 Organization, Folder, Project, 그리고 일부 리소스 레벨에 부여할 수 있습니다. 상위 노드에 부여한 정책은 하위로 상속되며, 특정 리소스에 실제로 적용되는 권한은 **자기 자신의 정책 + 모든 상위 노드의 정책을 합집합(Union)** 한 결과입니다.

![GCP IAM 정책 상속 - 상위 권한과 하위 권한의 합집합](/assets/img/gcp/gcp-iam-inheritance.webp)

GCP의 기본 IAM은 **허용(Allow) 기반이며 누적(Additive)** 됩니다. 즉 상위에서 부여된 권한을 하위에서 일반적인 방법으로 회수할 수는 없습니다. (별도의 IAM Deny 정책으로 차단하는 기능은 있지만, 입문 단계에서는 "상위 권한은 하위로 상속된다" 정도만 기억하면 됩니다.)

### 5.2. Organization Policy (조직 정책)

IAM이 "누가 무엇을 할 수 있는가"를 다룬다면, **Organization Policy**는 "어떤 구성이 허용되는가"를 제한하는 가드레일(Guardrail)입니다. 예를 들어 "특정 리전에만 리소스 생성 허용", "외부 IP 부여 금지" 같은 제약을 설정합니다.

Organization Policy 역시 상위 노드에 설정하면 하위로 상속되므로, 조직 전체에 일관된 보안/규정 정책을 강제할 때 사용합니다.

---

## 6. gcloud로 프로젝트 다뤄보기

개념을 정리했으니 `gcloud` CLI로 Project를 직접 다뤄보겠습니다. 개인 계정에서도 Project 생성/조회/전환은 그대로 따라 할 수 있습니다.

### 6.1. 프로젝트 생성과 조회

```bash
# 프로젝트 생성 (PROJECT_ID 는 전역 고유해야 함)
❯ gcloud projects create my-first-project-461203 --name="My First Project"
Create in progress for [https://cloudresourcemanager.googleapis.com/v1/projects/my-first-project-461203].
Waiting for [operations/cp...] to finish...done.

# 내 프로젝트 목록 확인
❯ gcloud projects list
PROJECT_ID                 NAME              PROJECT_NUMBER
my-first-project-461203    My First Project  123456789012
```

### 6.2. 프로젝트 상세 정보와 식별자 확인

```bash
❯ gcloud projects describe my-first-project-461203
createTime: '2026-06-09T12:00:00.000Z'
lifecycleState: ACTIVE
name: My First Project
projectId: my-first-project-461203
projectNumber: '123456789012'
```

`projectId`, `projectNumber`, `name`이 앞서 설명한 세 가지 식별자에 그대로 대응하는 것을 확인할 수 있습니다.

### 6.3. 작업 대상 프로젝트 설정

이후 실행하는 `gcloud` 명령이 어떤 프로젝트를 대상으로 하는지 기본값으로 지정합니다.

```bash
# 기본 프로젝트 설정
❯ gcloud config set project my-first-project-461203
Updated property [core/project].

# 현재 설정된 프로젝트 확인
❯ gcloud config get-value project
my-first-project-461203
```

### 6.4. Organization / Folder 조회 (조직 계정 한정)

Organization과 Folder는 조직 계정에서만 조회됩니다. 개인 계정에서는 결과가 비어 있게 됩니다.

```bash
# 조직 목록 (조직 계정에서만 결과 표시)
❯ gcloud organizations list
DISPLAY_NAME   ID            DIRECTORY_CUSTOMER_ID
example.com    111111111111  C00abcdef

# 특정 조직 하위 폴더 목록
❯ gcloud resource-manager folders list --organization=111111111111
DISPLAY_NAME  PARENT_NAME              ID
engineering   organizations/111111111111  222222222222
```

---

## 7. 주의사항 및 팁

### 7.1. 개인 계정에는 Organization / Folder가 없다

개인 Gmail 계정으로 GCP를 사용하면 Organization 노드가 없으므로, 생성한 Project는 모두 **조직에 속하지 않은 독립 Project**가 됩니다. 따라서 Folder도 만들 수 없습니다. 조직 단위 기능을 실습하려면 무료인 **Cloud Identity** 또는 **Google Workspace**를 연결해 Organization을 확보해야 합니다.

> 학습 단계에서 Folder/Organization 실습이 막힌다면, 계정이 개인 계정이라 Organization이 없는 것이 원인일 가능성이 큽니다.  
{: .prompt-warning}

### 7.2. Project ID는 변경할 수 없다

Project ID는 생성 후 변경이 불가능하고, 삭제하더라도 한동안 재사용할 수 없습니다. 따라서 처음 만들 때 의미 있는 네이밍 규칙(예: `회사-서비스-환경`)을 정해두는 것이 좋습니다.

### 7.3. 프로젝트 삭제는 30일 유예가 있다

`gcloud projects delete`로 프로젝트를 삭제하면 즉시 영구 삭제되지 않고, 약 30일간 복구 가능한 상태로 유지됩니다. 실수로 삭제했다면 이 기간 안에 복구할 수 있습니다.

```bash
# 프로젝트 삭제 예약 (30일 후 영구 삭제)
❯ gcloud projects delete my-first-project-461203

# 삭제 예약 취소 (복구)
❯ gcloud projects undelete my-first-project-461203
```

---

## 8. 참고: AWS 리소스 계층 대응

AWS Organizations에 익숙하다면, 아래 대응표로 GCP 계층을 빠르게 매핑할 수 있습니다. 개념은 비슷하지만 GCP는 권한 상속 모델이 더 강하게 작동한다는 점이 다릅니다.

| GCP                 | AWS                              | 비고                                  |
| :------------------ | :------------------------------- | :------------------------------------ |
| Organization        | Organizations (관리 계정 루트)   | 계정 체계의 최상위                    |
| Folder              | Organizational Unit (OU)         | 중첩 가능                             |
| Project             | Account                          | GCP Project가 생성/삭제가 훨씬 가볍다 |
| IAM 정책 상속       | (계정 경계로 격리, 상속 개념 약함) | GCP는 상위 -> 하위로 allow 상속       |
| Organization Policy | Service Control Policy (SCP)     | 둘 다 가드레일, 메커니즘은 다르다     |
| Resource            | Resource                         | 실제 서비스 리소스                    |

가장 큰 차이는 **Project의 가벼움**과 **권한 상속**입니다. AWS에서는 워크로드 분리를 위해 Account를 늘리는 일이 부담스럽지만, GCP에서는 Project를 손쉽게 만들고 지울 수 있어 워크로드 단위로 Project를 분리하는 패턴이 일반적입니다.

---

## 9. Reference

- [Google Cloud Docs - Resource hierarchy](https://cloud.google.com/resource-manager/docs/cloud-platform-resource-hierarchy)
- [Google Cloud Docs - Creating and managing projects](https://cloud.google.com/resource-manager/docs/creating-managing-projects)
- [Google Cloud Docs - Creating and managing folders](https://cloud.google.com/resource-manager/docs/creating-managing-folders)
- [Google Cloud Docs - Creating and managing organization resources](https://cloud.google.com/resource-manager/docs/creating-managing-organization)
- [Google Cloud Docs - IAM overview](https://cloud.google.com/iam/docs/overview)
- [Google Cloud Docs - Organization Policy Service overview](https://cloud.google.com/resource-manager/docs/organization-policy/overview)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
