---
title: AWS Lake Formation 알아보기 - IAM 위의 데이터 접근 권한
date: 2026-06-09 09:00:00 +0900
author: kkamji
categories: [Cloud, AWS]
tags: [aws, lake-formation, iam, glue, data-governance, security]
comments: true
image:
  path: /assets/img/aws/analytics-stack-07-lake-formation.webp
---

앞선 [S3 Tables & Catalog Federation](/posts/aws-s3-tables-catalog-federation/) 글에서 관리형 Iceberg 레이크하우스가 `s3tablescatalog` 아래에 어떻게 중첩되는지, 그래서 ARN이 왜 깊어지는지를 정리했습니다. 이번 글에서는 이 federated 데이터에 한 겹 더 얹히는 권한 계층, **AWS Lake Formation**을 알아봅니다.

Lake Formation이 까다로운 이유는, IAM 정책에서 모든 권한을 Allow로 열어 줘도 쿼리가 `AccessDenied`로 막힐 수 있기 때문입니다. IAM 위에 데이터 접근을 따로 통제하는 게이트가 하나 더 있고, 그 게이트는 IAM과 전혀 다른 방식(grant)으로 동작합니다. 이번 글에서는 그 두 번째 게이트가 무엇이고, IAM과 어떻게 결합해 동작하는지를 정리합니다.

> **TL;DR**  
> - **Lake Formation(LF)**은 Glue Data Catalog 리소스와 그 실데이터에 대한 **중앙 집중 fine-grained 접근 권한** 서비스입니다.  
> - LF는 IAM을 대체하지 않습니다. **IAM(API 권한) + LF(데이터 권한)** 두 게이트를 모두 통과해야 LF 등록 데이터를 쿼리할 수 있습니다.  
> - 권한은 IAM 정책이 아니라 **grant 모델**(principal에게 DB/Table에 SELECT/DESCRIBE 등을 부여)로 관리합니다.  
> - 쿼리마다 LF가 권한을 검증하고, 통과하면 **등록된 role을 assume해 임시 자격증명을 vending**합니다. 이때 호출자에게는 `lakeformation:GetDataAccess` IAM 권한이 필요합니다.  
{: .prompt-info}

---

## 1. AWS Lake Formation이란

Lake Formation은 데이터 레이크의 접근 권한을 **한 곳에서 fine-grained로 관리**하는 서비스입니다. Glue Data Catalog의 데이터베이스, 테이블, 컬럼, 행 같은 리소스와 그것이 가리키는 S3 위치의 실데이터에 대해, 누가 무엇을 할 수 있는지를 중앙에서 통제합니다.

### 1.1. 왜 IAM만으로는 부족한가

IAM은 AWS API 호출 권한을 다루는 데 강력하지만, 데이터 레이크의 거버넌스 요구를 그대로 담기에는 결이 맞지 않는 부분이 있습니다.

- **테이블/컬럼/행 단위 통제**: IAM 정책으로 특정 테이블의 일부 컬럼만, 또는 특정 조건의 행만 허용하려면 정책이 복잡해지고 관리가 어렵습니다.
- **중앙 집중 거버넌스**: 데이터 자산이 여러 데이터베이스와 계정에 흩어져 있을 때, 권한을 자산 중심으로 한곳에서 부여하고 회수하는 모델이 필요합니다.
- **분석 엔진과의 통합**: Athena, Redshift Spectrum, EMR 등 여러 엔진이 동일한 권한 모델을 공유해야 일관성이 유지됩니다.

Lake Formation은 이 요구를 데이터베이스의 `GRANT` / `REVOKE`와 유사한 **grant 모델**로 풀어냅니다.

### 1.2. 정책이 아니라 grant

IAM이 "이 principal에게 이런 action을 허용한다"는 **정책(policy)** 으로 권한을 표현한다면, Lake Formation은 "이 principal에게 이 데이터베이스/테이블에 SELECT를 부여한다"는 **grant** 로 표현합니다.

```text
# IAM (정책 기반)
Allow: glue:GetTable on arn:aws:glue:...:table/sales_db/orders

# Lake Formation (grant 기반)
GRANT SELECT, DESCRIBE ON TABLE sales_db.orders TO analytics-workload-role
```

이 둘은 서로를 대체하지 않습니다. 다음 절에서 보듯이, LF 등록 데이터는 두 표현이 **모두** 충족돼야 접근이 허용됩니다.

---

## 2. IAM과 Lake Formation - 2층 게이트

Lake Formation을 이해하는 핵심은, 그것이 IAM 위에 얹히는 **별도의 데이터 권한 게이트**라는 점입니다. 다음 다이어그램은 쿼리가 두 게이트를 차례로 통과하는 흐름을 보여줍니다.

![AWS Lake Formation 2층 권한 게이트와 credential vending](/assets/img/aws/analytics-stack-07-lake-formation.webp)

### 2.1. 역할 분리

두 게이트는 각각 다른 영역을 책임집니다.

| 게이트 | 검사 대상 | 책임 |
| :--- | :--- | :--- |
| **IAM** | Lake Formation / Glue **API와 리소스** 호출 | API authorization |
| **Lake Formation** | **Data Catalog 리소스와 실데이터** 접근 | data authorization |

즉 IAM은 "이 role이 `glue:GetTable` API를 호출해도 되는가"를 판단하고, Lake Formation은 "이 role이 `sales_db.orders`라는 데이터에 실제로 접근해도 되는가"를 판단합니다. 둘은 검사하는 층위가 다릅니다.

### 2.2. 둘 다 통과해야 한다

LF에 등록된 데이터는 **IAM 검사와 LF 검사를 모두 통과**해야 접근할 수 있습니다.

- IAM은 Allow인데 LF grant가 없으면 -> **AccessDenied**
- LF grant는 있는데 IAM에서 `glue:Get*`이나 `lakeformation:GetDataAccess`가 빠지면 -> **AccessDenied**

특히 첫 번째 경우가 혼동을 일으킵니다. IAM 정책에서 모든 Glue/Athena 권한을 열어 줬는데도 다음과 같은 에러가 나오면, 그것은 IAM 문제가 아니라 LF 게이트에서 막힌 것입니다.

```text
AccessDeniedException: Insufficient Lake Formation permission(s): Required Describe
```

이 메시지에 `Lake Formation permission(s)`가 들어 있다는 점이 단서입니다. IAM이 아니라 LF가 별도의 게이트로 작동하고 있다는 증거입니다.

### 2.3. LF 미등록 데이터는 IAM만으로 동작

반대로, Lake Formation에 등록되지 않은 데이터(일반 S3 + 일반 Glue 테이블)는 LF 게이트를 거치지 않습니다. 이 경우에는 IAM 정책과 Glue action만으로 접근이 결정되고, LF grant는 무관합니다.

> 같은 Athena를 쓰더라도, **일반 Glue 테이블은 IAM만으로**, **LF 등록 테이블(레이크하우스 등)은 IAM + LF grant로** 접근이 결정됩니다. 테이블이 어느 쪽인지에 따라 필요한 권한이 달라지므로, 접근이 막혔을 때 가장 먼저 확인할 것은 "이 데이터가 LF에 등록돼 있는가"입니다.  
{: .prompt-tip}

---

## 3. Lake Formation 권한 모델

게이트의 구조를 봤으니, Lake Formation이 실제로 어떤 권한을 어떻게 부여하는지를 살펴봅니다.

### 3.1. 두 종류의 접근 - metadata vs underlying data

Lake Formation 권한은 크게 두 종류로 나뉩니다.

| 종류 | 대상 | 예 |
| :--- | :--- | :--- |
| **Metadata access** | Data Catalog의 DB/Table **메타데이터** | 테이블 목록 조회, 스키마 읽기, DB 생성/삭제 |
| **Underlying data access** | Catalog가 가리키는 **실제 S3 위치의 데이터** | 행 read/write |

분석 쿼리 한 번에는 두 종류가 모두 관여합니다. 테이블의 스키마와 위치를 읽으려면 metadata access가, 그 위치의 데이터를 실제로 스캔하려면 underlying data access가 필요합니다.

### 3.2. grant 가능한 권한

S3 Tables 같은 카탈로그 객체에 부여할 수 있는 LF 권한은 데이터베이스의 권한과 유사합니다.

| 권한 | 의미 |
| :--- | :--- |
| `SELECT` | 데이터 조회 |
| `INSERT` / `DELETE` | 데이터 삽입 / 삭제 |
| `DESCRIBE` | 메타데이터(스키마, 테이블 목록) 조회 |
| `ALTER` / `DROP` | 테이블 변경 / 삭제 |
| `ALL` / `SUPER` | 전체 권한 |

읽기 전용 분석 워크로드에는 보통 **`SELECT` + `DESCRIBE`** 조합이면 충분합니다. `DESCRIBE`가 빠지면 테이블 자체가 목록에 보이지 않아, 마치 테이블이 존재하지 않는 것처럼 동작하기도 합니다.

### 3.3. 누가 grant하는가

LF 권한은 아무나 부여할 수 없습니다.

- **data lake admin**(또는 admin이 권한을 위임한 principal)만 grant할 수 있습니다.
- LF 권한은 **grant한 리전에서만** 유효합니다. 다른 리전의 동일 자산에는 별도로 grant해야 합니다.

따라서 운영 현장에서는 보통 인프라/보안 담당자가 **IAM 측 권한**(API, `GetDataAccess`)을 보강하고, 데이터 자산을 관리하는 **data lake admin이 LF grant**를 부여하는 식으로 책임이 나뉩니다. 한쪽만으로는 쿼리가 동작하지 않으므로, 권한 요청 시 두 축을 함께 확인하는 것이 좋습니다.

---

## 4. credential vending과 GetDataAccess

마지막으로, LF 게이트를 통과한 뒤 실데이터를 읽는 과정을 봅니다. 여기서 Lake Formation의 가장 독특한 동작인 **credential vending**이 등장합니다.

### 4.1. 쿼리마다 검증

principal이 LF 등록 데이터를 쿼리할 때마다, Lake Formation은 그 principal이 해당 DB/Table/데이터 위치에 적절한 LF 권한을 갖는지 **매번 검증**합니다. 권한이 없으면 그 자리에서 `AccessDenied`로 막습니다.

### 4.2. 등록된 role을 assume해 임시 자격증명 발급

권한 검증을 통과하면, Lake Formation은 실데이터에 접근할 **임시 자격증명(temporary credentials)을 발급(vending)** 해 분석 엔진에 전달합니다. 이 자격증명은 LF가 임의로 만드는 것이 아니라, **S3 위치를 LF에 등록할 때 지정한 IAM role을 assume**해서 만들어집니다.

여기서 중요한 결과가 따라옵니다.

> 실데이터가 있는 S3 위치를 읽고 쓰는 권한은 **등록된 role(registered role)** 이 제공합니다. 따라서 쿼리를 실행하는 호출자(principal)는 **그 S3 위치에 대한 직접적인 s3 권한을 가질 필요가 없습니다**. LF가 등록 role의 자격증명을 대신 vending하기 때문입니다.  
{: .prompt-info}

이 구조 덕분에, 분석 사용자에게 데이터 버킷의 S3 권한을 일일이 부여하지 않고도, LF grant만으로 접근을 통제할 수 있습니다. 다이어그램의 4~5번 단계가 바로 이 과정입니다. LF가 registered role을 assume(4)하고, 그 자격증명으로 S3 Tables 데이터를 읽어(5) 결과를 엔진에 돌려줍니다.

### 4.3. lakeformation:GetDataAccess

credential vending이 동작하려면, 호출자 측에 **`lakeformation:GetDataAccess` IAM 권한**이 있어야 합니다. 이 권한이 있어야 LF가 임시 자격증명 발급 요청을 승인합니다. LF grant(SELECT/DESCRIBE)와는 별개의, IAM 측 조건입니다.

Athena의 경우, 이 권한은 **쿼리를 실행하는 사용자나 role 본인**이 가져야 합니다(다른 통합 서비스는 해당 execution role에 부여). 따라서 LF 등록 데이터를 Athena로 쿼리하려는 role에는 다음 IAM 권한이 함께 필요합니다.

```text
athena:*                       # 쿼리 실행 API
glue:Get*                      # 대상 + 조상(catalog/database) 메타데이터 조회
lakeformation:GetDataAccess    # 임시 자격증명 발급 승인
```

여기에 더해 Lake Formation 측에서 SELECT/DESCRIBE grant가 부여돼야 비로소 쿼리가 성공합니다.

---

## 5. Access control mode - IAM vs Lake Formation

지금까지 설명한 "IAM + LF" 모델이 항상 적용되는 것은 아닙니다. S3 Tables를 Glue Data Catalog에 통합할 때 **권한 모드를 선택**하며, 이 선택에 따라 게이트의 구성이 달라집니다(나중에 전환 가능).

| 모드 | 권한 결정 | 특징 |
| :--- | :--- | :--- |
| **IAM access control** | IAM 정책만 | S3 Tables 리소스와 Data Catalog 객체 **양쪽에 IAM 권한** 필요. LF grant 불필요 |
| **Lake Formation access control** | Glue IAM 권한 + **LF grant** | principal은 Catalog 상호작용용 IAM 권한을 갖고, **어느 리소스에 접근할지는 LF grant가 결정** |

**Lake Formation access control mode**에서는 앞서 본 2층 게이트가 작동합니다. principal은 Data Catalog와 상호작용할 IAM 권한만 가지면 되고, 실제 어떤 DB/Table/Column/Row에 접근할 수 있는지는 LF grant가 통제합니다. coarse-grained(DB/Table)부터 fine-grained(Column/Row)까지 모두 지원합니다.

registered role과 credential vending이 켜져 있으면, principal은 **S3 Tables에 대한 IAM 권한을 따로 가질 필요가 없습니다**(4.2에서 본 대로 LF가 등록 role로 자격증명을 vending). 서드파티 분석 엔진도 동일하게 vending을 통해 접근할 수 있습니다.

레이크하우스 데이터가 Lake Formation access control mode로 구성돼 있다면, IAM만 아무리 열어도 LF grant 없이는 접근할 수 없습니다. 다음 글의 트러블슈팅이 정확히 이 상황을 다룹니다.

---

## 6. 다음 글

이번 편에서는 Lake Formation이 IAM 위에 얹히는 별도의 데이터 권한 게이트라는 점, grant 모델과 두 종류의 접근(metadata/underlying), credential vending과 `GetDataAccess`, 그리고 access control mode를 정리했습니다.

다음 글에서는 이 모든 것을 실제 문제 상황에 적용합니다. 레이크하우스의 federated 데이터베이스가 Athena에서 `CATALOG_NOT_FOUND` / `TABLE_NOT_FOUND` / `AccessDenied`로 보이지 않을 때, IAM 두 축과 LF 세 계층(catalog/database/table)을 어떻게 진단하고 단계적으로 해소하는지를 다룹니다.

---

## 7. Reference

- [AWS Lake Formation Developer Guide](https://docs.aws.amazon.com/lake-formation/latest/dg/what-is-lake-formation.html)
- [Lake Formation - access to underlying data](https://docs.aws.amazon.com/lake-formation/latest/dg/access-control-underlying-data.html)
- [Using Lake Formation with Amazon Athena](https://docs.aws.amazon.com/athena/latest/ug/security-athena-lake-formation.html)
- [Amazon S3 Tables integration with AWS Glue Data Catalog and Lake Formation](https://docs.aws.amazon.com/lake-formation/latest/dg/create-s3-tables-catalog.html)
- [Granting permissions on Data Catalog resources](https://docs.aws.amazon.com/lake-formation/latest/dg/granting-catalog-permissions.html)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
