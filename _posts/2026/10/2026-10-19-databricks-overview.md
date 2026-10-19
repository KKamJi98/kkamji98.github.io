---
title: Databricks란 무엇인가 - SQL 한 줄로 따라가는 계정, 컴퓨트, 권한 구조 [Databricks 1]
date: 2026-10-19 00:30:00 +0900
author: kkamji
categories: [Data, Databricks]
tags: [databricks, lakehouse, unity-catalog, delta-lake, photon, sql-warehouse, aws, data-platform]     # TAG names should always be lowercase
comments: true
image:
  path: /assets/img/data/databricks/databricks.webp
---

Databricks 화면에서 `SELECT * FROM main.sales.orders LIMIT 10`을 실행하면 몇 초 뒤 결과가 나옵니다. 인프라를 맡은 사람에게는 이 몇 초 사이에 일어난 일이 궁금합니다. 쿼리는 어느 계정의 서버에서 실행됐는지, 누가 이 테이블을 읽어도 된다고 판단했는지, S3의 Parquet 파일은 어떤 IAM role로 읽었는지, 그리고 비용과 감사 기록은 어디에 남았는지입니다. Databricks 공식 문서(2026년 9~10월 갱신본)를 기준으로 이 쿼리 한 줄을 따라가며 Databricks의 구조를 정리합니다.

> **TL;DR**  
>
> - Databricks는 고객 클라우드 스토리지의 데이터를 Unity Catalog라는 하나의 거버넌스 아래에서 SQL, ETL, ML로 처리하는 레이크하우스 플랫폼이다.  
> - 관리 화면과 API(control plane)는 Databricks 계정에 있다. 쿼리를 실행하는 compute는 serverless면 Databricks 계정, classic이면 고객 VPC에서 돈다.  
> - 사용자의 데이터 권한은 IAM이 아니라 Unity Catalog GRANT가 결정한다. S3는 storage credential(IAM role)과 external location으로만 연결하고, 비용과 감사 기록은 system tables에서 SQL로 확인한다.  
{: .prompt-info}

---

## 1. Databricks는 데이터를 가져가지 않는 분석 플랫폼입니다

공식 문서는 Databricks를 엔터프라이즈 규모의 데이터, 분석, AI 솔루션을 만들고 배포하고 유지하기 위한 **통합된 오픈 분석 플랫폼**으로 설명합니다. 인프라 관점에서 이 정의의 핵심은 "오픈"입니다. Databricks는 데이터를 자체 저장소로 옮겨 가두지 않고, 고객 클라우드 계정의 스토리지와 보안 체계에 연결되는 방식을 기본으로 합니다.

### 1.1. 레이크하우스와 Delta Lake

Databricks가 내세우는 아키텍처는 레이크하우스(lakehouse)입니다. 공식 문서는 레이크하우스를 데이터 레이크와 데이터 웨어하우스의 장점을 결합한 데이터 관리 시스템으로 정의합니다. object storage에 표준 포맷으로 데이터를 두면서, 웨어하우스처럼 트랜잭션과 스키마 검증, 빠른 BI 쿼리를 제공하는 구조입니다. 레이크하우스가 등장한 배경은 [데이터 분석 아키텍처의 역사](/posts/data-analytics-architecture-history/)에서 다뤘습니다.

이 구조를 받치는 저장 계층이 Delta Lake입니다. Delta Lake는 Parquet 데이터 파일에 파일 기반 transaction log를 더해 ACID 트랜잭션과 스키마 강제를 제공합니다. 문서에 따르면 **별도로 지정하지 않으면 Databricks의 모든 테이블은 Delta Lake 테이블입니다.** transaction log는 공개 프로토콜이라 다른 엔진도 같은 log를 읽을 수 있습니다. 앞의 `main.sales.orders`도 결국 S3 어딘가에 놓인 Parquet 파일과 `_delta_log` 디렉터리입니다.

### 1.2. 한 workspace에 모인 기능

공식 소개 문서가 나열하는 영역과 대표 기능은 다음과 같습니다.

| 영역 | 대표 기능 |
| :--- | :--- |
| ETL, 데이터 엔지니어링 | Lakeflow pipelines, Auto Loader |
| 머신러닝, AI | MLflow, Databricks Runtime for Machine Learning |
| 데이터 웨어하우스, BI | SQL warehouse, notebook, metric view, AI/BI dashboard, Genie Agents |
| 거버넌스, 데이터 공유 | Unity Catalog, OpenSharing |
| 오케스트레이션, CI/CD | Lakeflow Jobs, Declarative Automation Bundles, Git folders |
| 스트리밍 | Structured Streaming |
| 트랜잭션 처리(OLTP) | Lakebase |

기능 목록은 넓지만 인프라 관점에서 봐야 할 축은 세 가지로 줄어듭니다. 권한을 관리하는 Unity Catalog, 쿼리와 작업을 실행하는 compute, 그리고 Databricks 계정과 고객 계정 사이의 경계입니다. 이 세 축이 쿼리 한 줄 안에서 모두 드러납니다.

---

## 2. 쿼리를 실행하기 전에 잡아야 할 세 계층

Databricks는 관리 범위를 세 단계로 나눕니다.

- **Account**: 조직 전체의 최상위 단위다. 사용자, group, service principal, workspace, metastore, billing을 관리한다.
- **Workspace**: 사용자가 notebook, query, job을 실행하는 협업 환경이다. account 하나에 여러 개를 만들 수 있다.
- **Metastore**: Unity Catalog의 최상위 객체다. region당 1개이고, 같은 region의 여러 workspace에 연결된다.

`main.sales.orders`라는 이름은 이 계층 위에서 읽힙니다. `main`은 catalog, `sales`는 schema, `orders`는 table이고, 셋 모두 metastore 안에 있습니다. metastore가 workspace 위에 걸쳐 있다는 점이 중요합니다. **한 workspace에서 준 GRANT는 같은 metastore를 쓰는 모든 workspace에서 유효합니다.** dev workspace에서 prod 데이터를 막으려면 catalog를 특정 workspace에만 묶는 workspace-catalog binding을 걸어야 하고, binding이 걸린 catalog는 다른 workspace에서 GRANT가 있어도 접근이 거부됩니다.

### 2.1. AWS 분석 스택으로 바꿔 읽기

Athena, Glue, Lake Formation을 운영해 봤다면 익숙한 개념에 대응시켜 읽는 편이 빠릅니다. AWS 쪽 구성은 [AWS 데이터 분석 스택 Overview](/posts/aws-analytics-stack-overview/)에 정리했습니다.

| Databricks | AWS로 비유하면 | 차이 |
| :--- | :--- | :--- |
| Account | Organizations 관리 계정 | identity, workspace, metastore, billing을 한곳에서 관리 |
| Workspace | 팀이나 환경별 AWS 계정 | 여러 workspace가 metastore 하나를 공유 |
| Unity Catalog metastore | Glue Data Catalog + Lake Formation | region당 1개, 같은 region의 여러 workspace에 연결 |
| Storage credential | cross-account trust가 걸린 IAM role | 반드시 자기 자신을 assume할 수 있어야 함 |
| External location | S3 prefix와 그 prefix를 쓰는 IAM role의 묶음 | S3 경로 단위로 GRANT |
| SQL warehouse | Athena workgroup, Redshift Serverless | serverless, pro, classic 3종 |
| Photon | Redshift와 Athena의 native 실행 엔진 | Spark JVM 실행을 대체, DBU 단가가 다름 |
| Service principal | 자동화용 IAM role | OAuth client ID와 secret으로 인증 |
| system tables | CUR + CloudTrail Lake를 SQL로 조회 | `system.billing.usage`, `system.access.audit` |

**가장 큰 차이는 권한이 걸리는 위치입니다.** AWS 분석 스택에서 사용자는 IAM과 [Lake Formation](/posts/aws-lake-formation/)을 모두 통과해야 데이터를 읽습니다. Databricks에서 사용자의 데이터 접근은 Unity Catalog GRANT가 결정하고, IAM role은 Unity Catalog가 S3에 접근할 때 쓰는 자격증명으로 storage credential 안에 감싸집니다.

---

## 3. SQL 한 줄이 지나가는 다섯 단계

이제 `SELECT * FROM main.sales.orders LIMIT 10`을 SQL Editor에서 serverless SQL warehouse로 실행했다고 가정하고 따라가 봅니다. 아래 표는 각 단계가 어느 계정에서 일어나는지와, 문제가 생겼을 때 무엇을 확인하면 되는지를 함께 정리한 것입니다.

| 단계 | 일어나는 곳 | 하는 일 | 확인 방법 |
| :--- | :--- | :--- | :--- |
| 1. 로그인과 요청 | Databricks 계정(control plane) | SSO로 사용자를 확인하고 workspace의 web application이 쿼리를 받음 | `databricks current-user me` |
| 2. compute 선택 | serverless: Databricks 계정, classic: 고객 VPC | SQL warehouse가 쿼리를 실행. 이때 Photon 엔진을 씀 | `databricks warehouses list` |
| 3. 권한 판정 | Unity Catalog | `USE CATALOG`, `USE SCHEMA`, `SELECT`와 workspace binding을 확인 | `SHOW GRANTS ON TABLE ...` |
| 4. 데이터 읽기 | 고객 AWS 계정의 S3 | storage credential의 IAM role로 table 경로의 파일을 읽음 | `DESCRIBE EXTERNAL LOCATION ...` |
| 5. 결과와 기록 | workspace storage, system tables | 결과를 반환하고 사용량과 감사 이벤트를 남김 | `system.billing.usage`, `system.access.audit` |

### 3.1. 로그인과 요청: control plane

Databricks 아키텍처 문서의 첫 문장은 경계를 정합니다. **control plane은 고객 클라우드 계정이 아니라 Databricks 계정에 있습니다.** web application, REST API, 각종 backend 서비스가 여기에 있고, 사용자는 SSO로 로그인한 뒤 workspace URL로 접근합니다. 인프라 담당자가 control plane을 직접 볼 수는 없으므로, 이 단계에서 확인할 수 있는 것은 "누가 어떤 identity로 들어왔는가"입니다.

### 3.2. compute 선택: 쿼리가 실행되는 계정

compute plane은 데이터가 처리되는 곳이고, 실행 위치에 따라 둘로 나뉩니다.

- **Serverless compute plane**: Databricks 계정 안에서 실행된다. workspace와 같은 region에 만들어지고, 네트워크 통제는 account 수준의 NCC(network connectivity configuration)로 한다.
- **Classic compute plane**: 고객 AWS 계정의 workspace VPC 안에서 실행된다. Databricks가 cross-account IAM role을 assume해서 EC2를 띄운다.

serverless SQL warehouse로 실행한 이 쿼리는 고객 VPC가 아니라 Databricks 계정에서 돌았습니다. 같은 쿼리를 classic SQL warehouse로 실행하면 EC2가 고객 계정에서 뜨고 비용도 AWS 청구서에 함께 잡힙니다. **"Databricks의 서버가 우리 VPC 안에 있다"는 말은 classic compute에만 맞습니다.**

### 3.3. 권한 판정: Unity Catalog

Unity Catalog에서는 처음에 아무에게도 권한이 없습니다. 테이블 하나를 읽으려면 상위 객체의 사용 권한까지 세 가지가 모두 필요합니다.

```sql
GRANT USE CATALOG ON CATALOG main TO `data-readers`;
GRANT USE SCHEMA ON SCHEMA main.sales TO `data-readers`;
GRANT SELECT ON SCHEMA main.sales TO `data-readers`;

SHOW GRANTS ON TABLE main.sales.orders;
```

catalog나 schema에 준 권한은 그 아래의 현재 객체와 앞으로 만들어질 객체에 모두 상속됩니다. 위 예시처럼 schema에 `SELECT`를 주면 나중에 추가되는 테이블도 같은 group이 읽게 됩니다. `ALL PRIVILEGES`조차 `MANAGE`, `EXTERNAL USE SCHEMA`, `EXTERNAL USE LOCATION`은 포함하지 않는다는 점도 기억해 둘 만합니다. 데이터 유출 경로가 되는 권한을 일부러 분리한 설계입니다.

### 3.4. 데이터 읽기: storage credential과 external location

권한 판정을 통과하면 compute가 S3의 파일을 읽습니다. 이때 쓰는 자격증명이 Unity Catalog의 두 객체입니다.

- **Storage credential**: 장기 클라우드 자격증명이다. AWS에서는 IAM role ARN이다.
- **External location**: S3 경로와 storage credential을 묶은 객체다. 여러 external location이 credential 하나를 공유할 수 있다.

공식 문서의 원칙은 분명합니다. Unity Catalog가 관리하는 데이터에 접근하는 identity는 Unity Catalog가 쓰는 identity 하나여야 하고, 사용자나 service principal에게 S3 bucket 직접 접근을 주지 말아야 합니다. 이 IAM role의 trust policy는 Databricks의 Unity Catalog master role과 role 자기 자신을 principal로 가집니다.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": [
          "arn:aws:iam::<DATABRICKS-ACCOUNT>:role/<UC-MASTER-ROLE>",
          "arn:aws:iam::<YOUR-AWS-ACCOUNT-ID>:role/<THIS-ROLE-NAME>"
        ]
      },
      "Action": "sts:AssumeRole",
      "Condition": {
        "StringEquals": { "sts:ExternalId": "<STORAGE-CREDENTIAL-EXTERNAL-ID>" }
      }
    }
  ]
}
```

**2025년 1월 20일부터 자기 자신을 assume하지 못하는 role로 만든 storage credential은 차단됩니다.** role이 먼저 존재해야 자기 ARN을 principal에 넣을 수 있으므로, 처음에는 master role과 임시 external ID로 role을 만들고, storage credential을 생성해 받은 실제 external ID와 자기 ARN으로 trust를 갱신합니다. Terraform으로 구성할 때도 이 순환 참조 때문에 role ARN을 문자열로 조립하는 패턴을 씁니다.

Databricks 밖의 엔진이 Unity Catalog 테이블을 읽는 경로도 있습니다. credential vending은 Unity REST API나 Iceberg REST catalog로 들어온 외부 엔진에 table이나 path 범위의 짧은 수명 자격증명을 발급합니다. 이 경로는 metastore에서 external access를 켜고 요청 주체에 `EXTERNAL USE SCHEMA`를 줘야 열립니다.

예전에는 EC2 instance profile을 cluster에 붙여 S3에 접근했지만 지금은 legacy 방식입니다. instance profile은 그 compute를 쓰는 모든 사용자가 role 권한을 그대로 갖는 반면, external location은 사용자와 group 단위 GRANT, audit, lineage가 붙습니다.

### 3.5. 결과와 기록: workspace storage와 system tables

쿼리 결과는 사용자에게 돌아가고, 그 과정은 두 군데에 남습니다. classic workspace라면 쿼리 결과, job 결과, notebook revision, cluster log 같은 workspace system data가 고객 계정의 workspace storage bucket에 저장됩니다. **이 bucket을 지우거나 다른 bucket으로 바꾸면 workspace를 복구할 수 없습니다.** 일반 데이터 bucket과 같은 수명주기 정책을 걸지 않도록 분리해서 관리해야 합니다.

사용량과 감사 이벤트는 system tables에 남습니다. 앞의 쿼리가 쓴 DBU는 `system.billing.usage`에서 warehouse 단위로 볼 수 있습니다.

```sql
SELECT
  usage_date,
  usage_metadata.warehouse_id,
  sku_name,
  product_features.is_photon,
  product_features.is_serverless,
  SUM(usage_quantity) AS dbu
FROM system.billing.usage
WHERE usage_date >= current_date() - INTERVAL 7 DAYS
  AND usage_metadata.warehouse_id IS NOT NULL
GROUP BY ALL
ORDER BY usage_date, dbu DESC;
```

누가 어떤 Unity Catalog 작업을 했는지는 `system.access.audit`(Public Preview)에서 확인합니다. 문서는 성능을 위해 `event_time`보다 `event_date`로 거르라고 권합니다.

```sql
SELECT
  event_time,
  user_identity.email,
  action_name,
  request_params
FROM system.access.audit
WHERE event_date >= current_date() - INTERVAL 1 DAY
  AND service_name = 'unityCatalog'
ORDER BY event_time DESC
LIMIT 50;
```

system tables는 account admin이면서 metastore admin인 사용자에게 기본으로 열립니다. 다른 사용자가 보려면 `system` catalog의 `USE CATALOG`와 각 schema의 `USE SCHEMA`, `SELECT`를 따로 줘야 합니다.

---

## 4. 고객 AWS 계정에 생기는 리소스

쿼리 경로에서 고객 계정이 등장한 곳은 S3 데이터, classic compute, workspace storage였습니다. workspace 유형은 두 가지이고, 공식 문서는 대부분의 경우 serverless workspace를 권장합니다. serverless workspace는 compute와 default storage를 Databricks가 미리 구성합니다. classic workspace를 수동으로 구성하면 고객 계정에 다음 리소스가 생깁니다.

| 구성 요소 | 내용 |
| :--- | :--- |
| Credential configuration | Databricks AWS 계정을 신뢰하는 cross-account IAM role. external ID는 Databricks account ID |
| Storage configuration | workspace storage bucket(S3)과 bucket policy |
| Network configuration | customer-managed VPC를 쓰면 서로 다른 AZ의 subnet 2개 이상, security group, NAT egress |
| Private access settings | 선택 사항. PrivateLink용 VPC endpoint |
| Unity Catalog storage | 선택 사항. metastore나 catalog의 managed storage용 S3 bucket과 IAM role |

cross-account role은 EC2를 띄우는 데 쓰이고, Unity Catalog용 IAM role은 데이터를 읽는 데 쓰입니다. 공식 구성 절차도 두 role을 따로 만듭니다. **compute 기동 권한과 데이터 접근 권한을 한 role에 합치지 않아야 합니다.** 분리해 두면 어느 한쪽 role이 잘못 쓰였을 때의 피해 범위가 그 용도로 한정됩니다.

---

## 5. compute와 Photon, 그리고 비용 단위

Databricks에서 비용과 성능을 좌우하는 것은 compute 선택입니다. 공식 compute 문서는 다음 종류를 나열합니다.

| 종류 | 용도 |
| :--- | :--- |
| Serverless compute for notebooks | notebook의 Python, SQL을 인프라 관리 없이 실행 |
| Serverless compute for jobs | Lakeflow Jobs를 인프라 설정 없이 실행 |
| Standard compute | 여러 사용자가 사용자 간 데이터 격리 상태로 공유하는 classic compute |
| Dedicated compute | 한 사용자나 group에 할당하는 classic compute |
| Instance pools | 미리 준비한 instance로 기동 시간을 줄임 |
| SQL warehouses | SQL, 분석, BI 쿼리 전용. serverless, pro, classic |

classic compute의 access mode는 문서 권장대로 기능 제약이 없다면 standard를 기본으로 둡니다.

### 5.1. Photon

Photon은 Databricks의 C++ vectorized query engine입니다. 실행 계획은 Spark Catalyst가 세우고, 지원되는 연산의 실행만 Photon이 수천 행 단위의 columnar batch로 처리합니다. UDF나 RDD API처럼 지원하지 않는 연산을 만나면 남은 부분은 Spark로 자동 fallback하므로 코드를 바꿀 필요가 없습니다.

Photon은 serverless compute와 모든 SQL warehouse에서 항상 켜져 있고, classic compute에서는 기본으로 켜지되 끌 수 있습니다. 그래서 앞의 쿼리도 Photon으로 실행됐습니다. **Clusters API나 Jobs API로 compute를 만들 때는 `runtime_engine = "PHOTON"`을 명시해야 합니다.** UI 체크박스의 기본값이 API 호출에는 적용되지 않기 때문입니다.

비용 단위는 DBU(Databricks Unit)입니다. 문서는 같은 instance type이라도 Photon을 쓰면 DBU 소비율이 다르다고만 적고 배수는 pricing 페이지로 넘깁니다. Photon 사용분은 3.5절의 쿼리처럼 `product_features.is_photon`으로 분리해 볼 수 있습니다. classic compute는 EC2가 고객 계정에서 뜨므로 Databricks의 DBU 청구와 별도로 AWS 청구서에 EC2 비용이 잡힙니다.

---

## 6. 처음 접속했을 때 구조를 읽는 명령

새로 Databricks를 넘겨받았다면 콘솔을 돌아다니기 전에 CLI로 구조부터 읽는 편이 빠릅니다. 아래 명령은 Databricks CLI 공식 레퍼런스에 있는 명령이고, 모두 읽기 전용입니다. 사람은 OAuth U2M으로 로그인합니다.

```bash
# 사람 계정으로 OAuth 로그인(U2M)
databricks auth login --host https://<workspace-url>

# 지금 어떤 identity로 붙었는가
databricks current-user me

# 이 workspace에 연결된 metastore와 catalog
databricks metastores current
databricks catalogs list
databricks schemas list main

# S3로 이어지는 경로
databricks storage-credentials list
databricks external-locations list

# 쿼리를 실행하는 compute
databricks warehouses list

# 특정 객체의 GRANT
databricks grants get table main.sales.orders
```

SQL로도 같은 내용을 확인할 수 있습니다.

```sql
SHOW STORAGE CREDENTIALS;
SHOW EXTERNAL LOCATIONS;
DESCRIBE EXTERNAL LOCATION `<location-name>`;
SHOW GRANTS ON EXTERNAL LOCATION `<location-name>`;
```

`DESCRIBE EXTERNAL LOCATION` 결과의 URL과 credential 이름을 따라가면 3.4절의 IAM role까지 이어집니다. 여기서 `READ FILES`가 넓은 group에 걸려 있다면 view로 컬럼을 감춘 설계를 경로 직접 조회로 우회할 수 있다는 뜻이므로 먼저 확인할 대상입니다.

---

## 7. 자주 하는 오해

구조를 알면 처음에 흔히 하는 오해 몇 가지가 정리됩니다.

| 오해 | 실제 | 근거 |
| :--- | :--- | :--- |
| Databricks가 데이터를 자기 저장소로 가져간다 | classic workspace의 데이터는 고객 계정 S3에 남는다. serverless workspace의 default storage는 Databricks가 구성한다 | High-level architecture |
| Databricks 서버는 모두 우리 VPC 안에서 돈다 | classic compute만 고객 VPC에서 돈다. serverless는 Databricks 계정에서 실행된다 | High-level architecture |
| 사용자에게 S3 IAM 권한을 줘야 데이터를 읽는다 | 사용자 권한은 Unity Catalog GRANT로 준다. 사용자에게 bucket 직접 접근을 주지 않는 것이 원칙이다 | Cloud storage 문서 |
| workspace마다 권한이 따로 관리된다 | GRANT는 metastore 범위다. 분리하려면 workspace-catalog binding을 건다 | Workspace-catalog binding |
| Budget을 걸면 비용이 넘지 않는다 | Budget은 기본적으로 알림만 보내고 알림은 최대 24시간 늦을 수 있다 | Budgets 문서 |

---

## 8. 운영 관점에서 먼저 확인할 것

Databricks를 운영하게 되면 기능보다 경계와 권한부터 확인하는 편이 사고를 줄입니다. 공식 보안 best practice와 운영 문서를 기준으로 정리하면 다음과 같습니다.

- **Admin 범위**: account admin, workspace admin, metastore admin이 누구인지 확인한다. 공식 권장은 account admin 2~3명이고, 운영 객체 owner는 개인이 아니라 group으로 둔다.
- **Identity 공급**: IdP에서 account 수준 SCIM이나 automatic identity management로 사용자와 group을 동기화한다. workspace 수준 SCIM은 legacy다.
- **자동화 인증**: 자동화는 service principal의 OAuth M2M을 쓴다. PAT는 기본 최대 수명이 730일이라 수명을 줄이거나 사용을 제한한다.
- **비용 통제**: Budget은 알림 도구다. 실제 상한은 compute policy, SQL warehouse의 크기와 최대 cluster 수, auto stop으로 건다.
- **감사**: `system.access.audit`나 S3 audit log delivery로 이벤트를 남긴다.
- **IaC**: Terraform provider는 account 수준과 workspace 수준 두 provider로 나눠 쓴다. `databricks_grants` 리소스는 대상 객체의 GRANT 전체를 덮어쓰므로 콘솔에서 준 권한은 다음 apply 때 사라진다.

**Budget이 사용을 막아 줄 것이라고 기대하면 안 됩니다.** 알림이 늦게 오는 동안에도 serverless warehouse는 계속 DBU를 소비합니다. 비용 상한은 compute 설정으로 거는 것이 실제 통제 수단입니다.

---

## 9. 마치며

`SELECT * FROM main.sales.orders` 한 줄은 Databricks 계정의 control plane에서 시작해, Unity Catalog의 권한 판정을 지나, 고객 계정 S3의 Parquet 파일을 읽고, system tables에 비용과 감사 기록을 남기고 끝납니다. 이 경로를 머리에 두면 Databricks의 많은 기능이 어디에 놓이는지 보입니다. notebook과 dashboard는 1단계의 입구이고, SQL warehouse와 Photon은 2단계의 엔진이며, Unity Catalog와 storage credential은 3, 4단계의 문지기입니다. AWS 분석 스택에 익숙하다면 Glue Data Catalog와 Lake Formation이 하던 일을 Unity Catalog가 한 계층에서 맡는다고 이해하면 출발점으로 충분합니다.

---

## 10. Reference

- [Databricks Docs - What is Databricks?](https://docs.databricks.com/aws/en/introduction/)
- [Databricks Docs - High-level architecture](https://docs.databricks.com/aws/en/getting-started/high-level-architecture)
- [Databricks Docs - What is a data lakehouse?](https://docs.databricks.com/aws/en/lakehouse/)
- [Databricks Docs - What is Delta Lake?](https://docs.databricks.com/aws/en/delta/)
- [Databricks Docs - Compute](https://docs.databricks.com/aws/en/compute/)
- [Databricks Docs - Compute configuration reference](https://docs.databricks.com/aws/en/compute/configure)
- [Databricks Docs - What is Photon?](https://docs.databricks.com/aws/en/compute/photon)
- [Databricks Docs - SQL warehouse types](https://docs.databricks.com/aws/en/compute/sql-warehouse/warehouse-types)
- [Databricks Docs - What is Unity Catalog?](https://docs.databricks.com/aws/en/data-governance/unity-catalog/)
- [Databricks Docs - Unity Catalog privileges reference](https://docs.databricks.com/aws/en/data-governance/unity-catalog/access-control/privileges-reference)
- [Databricks Docs - Workspace-catalog binding](https://docs.databricks.com/aws/en/data-governance/unity-catalog/access-control/workspace-catalog-binding)
- [Databricks Docs - Connect to cloud object storage using Unity Catalog](https://docs.databricks.com/aws/en/connect/unity-catalog/cloud-storage/)
- [Databricks Docs - Create a storage credential and external location for S3](https://docs.databricks.com/aws/en/connect/unity-catalog/cloud-storage/s3/s3-external-location-manual)
- [Databricks Docs - Unity Catalog credential vending for external system access](https://docs.databricks.com/aws/en/external-access/credential-vending)
- [Databricks Docs - Create a workspace with manual AWS configurations](https://docs.databricks.com/aws/en/admin/workspace/create-uc-workspace)
- [Databricks Docs - System tables reference](https://docs.databricks.com/aws/en/admin/system-tables/)
- [Databricks Docs - Billable usage system table](https://docs.databricks.com/aws/en/admin/system-tables/billing)
- [Databricks Docs - Audit log system table](https://docs.databricks.com/aws/en/admin/system-tables/audit-logs)
- [Databricks Docs - Databricks CLI commands](https://docs.databricks.com/aws/en/dev-tools/cli/commands)
- [Databricks Docs - Budgets](https://docs.databricks.com/aws/en/admin/account-settings/budgets)
- [Databricks Docs - Security best practices](https://docs.databricks.com/aws/en/lakehouse-architecture/security-compliance-and-privacy/best-practices)
- [Databricks Docs - Databricks Terraform provider](https://docs.databricks.com/aws/en/dev-tools/terraform/)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
