---
title: AWS Lake Formation 권한 Deep Dive - CATALOG_NOT_FOUND / TABLE_NOT_FOUND 진단과 해소
date: 2026-06-16 09:00:00 +0900
author: kkamji
categories: [Cloud, AWS]
tags: [aws, lake-formation, s3-tables, athena, troubleshooting, iam]
comments: true
image:
  path: /assets/img/aws/aws.webp
---

이 글은 AWS 데이터 분석 스택 시리즈의 마지막 편입니다. 앞선 [AWS Lake Formation](/posts/aws-lake-formation/) 글에서 Lake Formation이 IAM 위에 얹히는 별도의 데이터 권한 게이트라는 점과 grant 모델, credential vending을 정리했습니다. 이번 글에서는 그 개념을 실제 트러블슈팅에 적용합니다.

상황은 이렇습니다. S3 Tables 레이크하우스로 옮겨진 데이터베이스를 IAM role로 Athena에서 쿼리하려는데, IAM 정책에서 Glue와 Athena 권한을 충분히 열어 줬는데도 테이블이 `TABLE_NOT_FOUND` 또는 `CATALOG_NOT_FOUND`로 보이지 않습니다. 관리자(admin) 계정으로 같은 쿼리를 실행하면 정상 동작합니다. 이 글에서는 세 가지 증상이 사실 하나의 뿌리에서 나온다는 점, 그리고 IAM 두 축과 Lake Formation 세 계층을 어떻게 진단하고 단계적으로 해소하는지를 다룹니다.

> **TL;DR**  
> - `TABLE_NOT_FOUND`와 `CATALOG_NOT_FOUND`는 쿼리 표기 방식만 다를 뿐, 보통 **catalog 레벨 권한 부재**라는 같은 원인입니다.  
> - federated 데이터는 **IAM(2축의 한 축) + Lake Formation grant(다른 축)** 가, 그리고 각각 **catalog / database / table 세 계층**이 모두 갖춰져야 쿼리됩니다.  
> - **admin 계정으로는 진단할 수 없습니다.** admin은 모든 것이 보이므로 누락이 드러나지 않습니다. 반드시 **대상 role 본인으로 boto3**를 호출해 실제 `AccessDenied` 메시지로 누락 지점을 찾아야 합니다.  
> - 권한을 한 계층씩 채울 때마다 증상이 한 칸씩 전진합니다. 모두 갖춰지면 **short name 그대로** 쿼리됩니다.  
{: .prompt-info}

---

## 1. 상황 - 권한을 다 줬는데 테이블이 안 보인다

분석 워크로드용 IAM role(`analytics-workload-role`)에 다음을 부여했다고 가정합니다.

- `athena:*` (전용 workgroup 한정)
- `glue:GetDatabase`, `glue:GetTable` 등 메타데이터 조회
- 일반 Glue 테이블의 S3 데이터/결과 버킷 read

이 구성으로 일반 Glue 테이블(S3 + Glue Catalog)은 잘 쿼리됩니다. 그런데 레이크하우스로 이전된 `sales_db.orders`를 쿼리하면 다음과 같이 막힙니다.

```text
TABLE_NOT_FOUND: line 1:15: Table 'awsdatacatalog.sales_db.orders' does not exist
```

분명히 테이블은 존재하고, admin 계정으로는 같은 SQL이 동작합니다. 권한 문제 같은데, IAM 정책에는 `glue:GetTable`이 들어 있습니다. 여기서 [6편](/posts/aws-s3-tables-catalog-federation/)에서 정리한 사실을 떠올려야 합니다. `sales_db`는 일반 Glue 데이터베이스가 아니라 `s3tablescatalog` 아래 **federated 카탈로그**에 중첩돼 있고, [7편](/posts/aws-lake-formation/)에서 본 대로 **Lake Formation 거버넌스 대상**입니다. 즉 일반 테이블과는 권한 모델 자체가 다릅니다.

---

## 2. 세 가지 증상, 하나의 뿌리

레이크하우스 데이터 접근이 막힐 때 나타나는 대표 증상은 세 가지입니다. 표기만 다를 뿐, 대부분 권한 계층의 어딘가가 비어 있다는 같은 신호입니다.

### 2.1. TABLE_NOT_FOUND vs CATALOG_NOT_FOUND

같은 테이블을 어떤 표기로 쿼리하느냐에 따라 에러가 달라집니다.

```sql
-- short name으로 조회
SELECT * FROM sales_db.orders;
-- TABLE_NOT_FOUND: Table 'awsdatacatalog.sales_db.orders' does not exist

-- federated 카탈로그를 명시(fully-qualified)
SELECT * FROM "s3tablescatalog/amzn-s3-demo-bucket".sales_db.orders;
-- CATALOG_NOT_FOUND: Catalog 's3tablescatalog/amzn-s3-demo-bucket' does not exist
```

두 에러는 다른 문제처럼 보이지만 원인은 같습니다. **principal이 catalog 자체를 볼 권한(catalog 레벨 DESCRIBE)이 없기 때문**입니다. catalog가 보이지 않으니, short name으로 접근하면 그 아래 테이블을 못 찾아 `TABLE_NOT_FOUND`가 나고, 카탈로그를 직접 지정하면 카탈로그 자체가 없는 것으로 취급돼 `CATALOG_NOT_FOUND`가 납니다.

> `TABLE_NOT_FOUND`를 보고 "테이블 이름이 틀렸나" "SQL 문법이 잘못됐나"를 의심하기 쉽지만, federated 데이터에서는 **catalog 레벨 권한 부재**가 이런 모습으로 위장되는 경우가 많습니다. 같은 테이블이 admin에게는 보인다면, 이름이나 문법이 아니라 권한을 의심해야 합니다.  
{: .prompt-warning}

### 2.2. AccessDenied

catalog는 보이지만 그 아래 데이터에 대한 grant가 없으면, 이번에는 권한 부족이 명시적으로 드러납니다.

```text
AccessDeniedException: Insufficient Lake Formation permission(s): Required Describe
```

이 메시지에 `Lake Formation permission(s)`가 들어 있다는 점이 결정적인 단서입니다. IAM이 아니라 **Lake Formation 게이트에서 막혔다**는 뜻입니다. IAM 정책을 아무리 들여다봐도 이 증상은 풀리지 않습니다.

### 2.3. 왜 admin 콘솔에서는 다 보이나

진단을 어렵게 만드는 가장 큰 함정이 이것입니다. Lake Formation의 **data lake admin**은 별도 grant 없이도 모든 카탈로그/데이터베이스/테이블을 봅니다. 따라서 admin 계정으로 콘솔이나 Athena를 열면, short name이든 fully-qualified든 모두 정상 동작합니다.

이 때문에 "admin은 되는데 특정 role만 안 된다"는 상황이 만들어지고, admin 시점에서 보면 카탈로그도 테이블도 멀쩡히 보이므로 **무엇이 빠졌는지 알 수 없습니다.** 진단은 반드시 막히는 role 본인의 시점에서 해야 합니다. 이 부분은 4절에서 자세히 다룹니다.

---

## 3. 권한 지도 - 2축 x 3계층

증상의 뿌리를 잡으려면, federated 데이터에 필요한 권한의 전체 지도를 갖고 있어야 합니다. 핵심은 **두 개의 축과 세 개의 계층**입니다.

![Lake Formation 권한 매트릭스와 디버깅 타임라인](/assets/img/aws/analytics-stack-08-lf-permissions.webp)

- **축 1 - IAM (API authorization)**: Glue/Athena API를 호출할 수 있는가. federated 리소스의 ARN과 glue action이 여기에 해당합니다.
- **축 2 - Lake Formation (data authorization)**: 그 데이터에 실제로 접근할 grant가 있는가. catalog/database/table에 대한 DESCRIBE/SELECT grant입니다.

그리고 각 축은 **catalog -> database -> table** 세 계층으로 나뉩니다. federated 카탈로그는 상위 계층을 거쳐야 하위로 내려갈 수 있으므로(navigation), 어느 한 계층이라도 비면 그 지점에서 막힙니다. 위 매트릭스의 여섯 칸(2축 x 3계층)에 더해, IAM 측에 `lakeformation:GetDataAccess`(credential vending을 승인하는 권한)가 함께 있어야 합니다.

| 계층 | IAM (API authz) | Lake Formation (data authz) |
| :--- | :--- | :--- |
| **catalog** | `glue:GetCatalog(s)` + `catalog/s3tablescatalog/{bucket}` ARN | `DESCRIBE` on `s3tablescatalog/{bucket}` |
| **database** | `glue:GetDatabase(s)` + `database/s3tablescatalog/{bucket}/{db}` ARN | `DESCRIBE` on `{db}` |
| **table** | `glue:GetTable(s)` + `table/s3tablescatalog/{bucket}/{db}/*` ARN | `SELECT` / `DESCRIBE` on table |

여기서 IAM action을 **단수와 복수 모두**(`GetCatalog`/`GetCatalogs`, `GetDatabase`/`GetDatabases`, `GetTable`/`GetTables`) 부여하는 점에 주의해야 합니다. 목록 조회(복수)와 단건 조회(단수)가 서로 다른 action으로 검사되므로, 한쪽만 있으면 특정 단계에서 막힙니다.

---

## 4. 진단 - admin이 아니라 대상 role로 직접 찍는다

권한 지도를 손에 쥐었으니, 이제 비어 있는 칸을 찾아야 합니다. 핵심 원칙은 하나입니다.

> **admin이 아니라 막히는 role 본인으로 호출한다.** admin은 모든 것이 통과되므로 누락이 보이지 않습니다. 대상 role로 직접 호출해야 실제 `AccessDenied` 메시지가 어느 action/resource에서 나는지 정확히 드러납니다.  
{: .prompt-tip}

대상 role이 assume된 환경(또는 그 role로 assume한 세션)에서 boto3로 다음을 단계적으로 호출합니다.

```python
import boto3

# 1. 어떤 자격증명으로 호출되는지부터 확인한다
sts = boto3.client("sts")
print(sts.get_caller_identity()["Arn"])
# arn:aws:sts::<account-id>:assumed-role/analytics-workload-role/...
# 의도한 role이 맞는지 먼저 확정한다. 엉뚱한 role(인스턴스 role 등)로
# 호출되고 있으면 그 자체가 원인이다.

# 2. federated 카탈로그를 대상 role 본인으로 조회한다
glue = boto3.client("glue", region_name="ap-northeast-2")
catalog_id = "<account-id>:s3tablescatalog/amzn-s3-demo-bucket"

# 2a. database 목록 (catalog/database 계층 권한 확인)
print(glue.get_databases(CatalogId=catalog_id))

# 2b. 단건 테이블 (table 계층 권한 확인)
print(glue.get_table(CatalogId=catalog_id, DatabaseName="sales_db", Name="orders"))
```

각 호출은 빠진 권한을 **그 자리에서 에러로** 알려 줍니다. 예를 들어 `get_databases`가 다음과 같이 거부되면, database 계층의 IAM action 또는 LF grant가 비어 있다는 뜻입니다.

```text
AccessDeniedException: ... is not authorized to perform: glue:GetDatabases
on resource: arn:aws:glue:ap-northeast-2:<account-id>:database/s3tablescatalog/amzn-s3-demo-bucket/sales_db
```

이 방식의 장점은, 추측 없이 **누락된 계층과 action을 정확히 지목**할 수 있다는 점입니다. admin 콘솔에서 "다 보이는데 왜 안 되지"를 반복하는 대신, 막히는 지점을 한 번에 특정합니다.

---

## 5. 단계적 해소 - 증상이 한 칸씩 전진한다

진단으로 빈 칸을 찾았다면, 두 축을 계층 순서대로 채웁니다. 권한을 한 계층씩 추가할 때마다 증상이 다음 단계로 전진하는 것이 정상입니다. 다이어그램 하단의 타임라인이 이 진전을 보여줍니다.

`CATALOG_NOT_FOUND` -> (catalog 권한 추가) -> `GetDatabases` 거부 -> (database 권한 추가) -> `GetTable` 거부 -> (table 권한 추가) -> 정상 동작

### 5.1. IAM - federated ARN과 단복수 action

먼저 IAM 정책에 federated 카탈로그의 ARN을 계층별로 넣고, glue action을 단수/복수 모두 부여합니다. default 카탈로그 ARN(`database/sales_db`)만으로는 federated 실접근에 부족합니다.

```json
{
  "Sid": "GlueCatalogReadOnly",
  "Effect": "Allow",
  "Action": [
    "glue:GetCatalog", "glue:GetCatalogs",
    "glue:GetDatabase", "glue:GetDatabases",
    "glue:GetTable", "glue:GetTables",
    "glue:GetPartition", "glue:GetPartitions"
  ],
  "Resource": [
    "arn:aws:glue:ap-northeast-2:<account-id>:catalog",
    "arn:aws:glue:ap-northeast-2:<account-id>:catalog/s3tablescatalog",
    "arn:aws:glue:ap-northeast-2:<account-id>:catalog/s3tablescatalog/amzn-s3-demo-bucket",
    "arn:aws:glue:ap-northeast-2:<account-id>:catalog/s3tablescatalog/amzn-s3-demo-bucket/sales_db",
    "arn:aws:glue:ap-northeast-2:<account-id>:database/s3tablescatalog/amzn-s3-demo-bucket/sales_db",
    "arn:aws:glue:ap-northeast-2:<account-id>:table/s3tablescatalog/amzn-s3-demo-bucket/sales_db/*"
  ]
}
```

여기에 credential vending을 승인할 `lakeformation:GetDataAccess`와, federated 카탈로그를 참조할 `athena:GetDataCatalog`를 더합니다.

```json
{
  "Sid": "LakeFormationDataAccess",
  "Effect": "Allow",
  "Action": "lakeformation:GetDataAccess",
  "Resource": "*"
},
{
  "Sid": "AthenaFederatedCatalog",
  "Effect": "Allow",
  "Action": ["athena:GetDataCatalog", "athena:GetDatabase"],
  "Resource": "arn:aws:athena:ap-northeast-2:<account-id>:datacatalog/AwsDataCatalog"
}
```

federated 카탈로그를 참조하는 쿼리에는 `athena:GetDataCatalog`가 필수입니다. AWS 공식 문서의 federated query 권한 예시도 이 action을 가장 먼저 명시합니다.

> The `GetDataCatalog` action is required for views.  
>
> Athena permissions that are required to run federated queries.  
{: .prompt-info}

같은 예시 정책은 federated 쿼리 실행에 필요한 Athena action 묶음으로 `athena:GetDataCatalog`, `athena:GetQueryExecution`, `athena:GetQueryResults`, `athena:GetWorkGroup`, `athena:StartQueryExecution`, `athena:StopQueryExecution`를 함께 제시합니다. 위 정책에는 workgroup/쿼리 실행 권한(`athena:*` workgroup 한정)이 이미 1절에서 부여됐다고 가정해 catalog 참조 action만 추렸습니다.

### 5.2. Lake Formation grant - catalog/database/table

IAM만으로는 끝이 아닙니다. Lake Formation 축에서 catalog -> database -> table 순으로 grant를 부여합니다. grant는 data lake admin(또는 위임받은 principal)만 실행할 수 있습니다.

여기서 핵심은 `--resource`에 넣는 catalog 식별자 형식입니다. federated S3 Tables 리소스는 일반 Glue 테이블처럼 12자리 account ID만 쓰는 것이 아니라, `CatalogId`에 **`<account-id>:s3tablescatalog/<bucket>` 경로 전체**를 넣어야 합니다. AWS 공식 문서의 S3 Tables grant 예시가 이 형식을 그대로 보여줍니다.

{% raw %}
```json
"Resource": {
    "Table": {
        "CatalogId":"{{111122223333}}:{{s3tablescatalog}}/{{amzn-s3-demo-bucket1}}",
        "DatabaseName":"{{S3 table bucket namespace <example_namespace>}}",
        "Name":"{{S3 table bucket table name <example_table>}}"
    }
}
```
{% endraw %}

즉 `Database.CatalogId`, `Table.CatalogId`(그리고 catalog 레벨의 `Catalog.Id`)에는 모두 이 federated 경로를 채워야 하며, account ID만 넣으면 default 카탈로그를 가리켜 federated 데이터에는 닿지 않습니다.

```bash
ROLE='arn:aws:iam::<account-id>:role/analytics-workload-role'
CAT='<account-id>:s3tablescatalog/amzn-s3-demo-bucket'

# catalog 레벨 DESCRIBE - 이것이 없으면 TABLE_NOT_FOUND / CATALOG_NOT_FOUND
aws lakeformation grant-permissions \
  --principal "{\"DataLakePrincipalIdentifier\":\"$ROLE\"}" \
  --resource "{\"Catalog\":{\"Id\":\"$CAT\"}}" \
  --permissions DESCRIBE

# database 레벨 DESCRIBE
aws lakeformation grant-permissions \
  --principal "{\"DataLakePrincipalIdentifier\":\"$ROLE\"}" \
  --resource "{\"Database\":{\"CatalogId\":\"$CAT\",\"Name\":\"sales_db\"}}" \
  --permissions DESCRIBE

# table 레벨 SELECT + DESCRIBE
aws lakeformation grant-permissions \
  --principal "{\"DataLakePrincipalIdentifier\":\"$ROLE\"}" \
  --resource "{\"Table\":{\"CatalogId\":\"$CAT\",\"DatabaseName\":\"sales_db\",\"Name\":\"orders\"}}" \
  --permissions SELECT DESCRIBE
```

table 레벨은 필요한 테이블 단위로 좁히는 것이 최소 권한 원칙에 맞습니다. 공용 환경에서 와일드카드로 데이터베이스 전체를 열면, 그 role로 워크플로우를 만들 수 있는 모든 사용자가 전체 테이블에 접근하게 되므로 주의해야 합니다.

### 5.3. 전파 지연

권한을 추가한 직후 곧바로 쿼리하면, 변경이 아직 전파되지 않아 일시적으로 거부가 남을 수 있습니다. IAM 정책 변경은 수십 초의 전파 지연이 있을 수 있으므로, 추가 직후 한 번 실패했다고 권한 구성이 틀렸다고 단정하지 말고 잠시 뒤 다시 확인합니다.

---

## 6. 결론 - short name 그대로 동작

두 축(IAM, Lake Formation)과 세 계층(catalog, database, table)이 모두 채워지면, federated 데이터도 일반 테이블과 다를 바 없이 쿼리됩니다.

```sql
-- 카탈로그 명시 없이 short name 그대로
SELECT dt, count(*) AS cnt
FROM sales_db.orders
GROUP BY dt;

-- 일반 Glue 테이블과의 cross-catalog JOIN도 동작
SELECT o.id, e.event_type
FROM sales_db.orders o
JOIN logs_db.app_event e ON e.order_id = o.id;
```

권한이 갖춰진 뒤에는 사용자가 `s3tablescatalog/...` 같은 긴 카탈로그 경로를 의식할 필요가 없습니다. catalog 명시는 가능하지만 불필요하고, default 카탈로그의 일반 테이블과 섞어 조인해도 short name으로 동작합니다.

정리하면, federated 레이크하우스 데이터의 접근 문제는 거의 언제나 **2축 x 3계층 매트릭스의 빈 칸**으로 환원됩니다. 그 빈 칸은 admin이 아니라 대상 role 본인의 boto3 호출로 찾고, IAM과 Lake Formation 양쪽을 계층 순서대로 채우면, 증상이 한 칸씩 전진하다 마침내 사라집니다.

이것으로 AWS 데이터 분석 스택 시리즈를 마칩니다. S3에 쌓인 데이터를 적재 없이 SQL로 다루는 큰 그림에서 출발해, Athena와 Glue Data Catalog, S3 Tables와 Catalog Federation, Lake Formation의 권한 모델을 거쳐, 이번 편에서 그 모든 것을 실제 트러블슈팅으로 엮었습니다.

---

## 7. Reference

- [Using Lake Formation with Amazon Athena](https://docs.aws.amazon.com/athena/latest/ug/security-athena-lake-formation.html)
- [Granting permissions on S3 Tables catalog resources](https://docs.aws.amazon.com/lake-formation/latest/dg/s3-tables-grant-permissions.html)
- [Fine-grained access to Glue Data Catalog resources](https://docs.aws.amazon.com/athena/latest/ug/fine-grained-access-to-glue-resources.html)
- [Running federated queries in Athena](https://docs.aws.amazon.com/athena/latest/ug/running-federated-queries.html)
- [Allow access to Athena Federated Query - Example policies](https://docs.aws.amazon.com/athena/latest/ug/federated-query-iam-access.html)
- [Lake Formation - access to underlying data](https://docs.aws.amazon.com/lake-formation/latest/dg/access-control-underlying-data.html)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
