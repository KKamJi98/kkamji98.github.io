---
title: S3 Tables & Catalog Federation 알아보기 - 관리형 Iceberg 레이크하우스
date: 2026-05-26 09:00:00 +0900
author: kkamji
categories: [Cloud, AWS]
tags: [aws, s3-tables, iceberg, glue, catalog-federation, data-lakehouse]
comments: true
image:
  path: /assets/img/aws/analytics-stack-06-catalog-federation.webp
---

앞선 [Amazon Athena & Glue Data Catalog](/posts/aws-athena-glue-catalog/) 글에서 일반 Glue 테이블(S3 + Glue Catalog)을 기준으로 쿼리 흐름과 권한을 정리했습니다. 이번 글에서는 한 단계 더 들어가, 데이터 레이크하우스의 핵심인 **Amazon S3 Tables**와, 그것이 Glue Data Catalog에 연결되는 방식인 **Catalog Federation**을 알아봅니다.

이 편을 이해하면, 같은 Athena 쿼리인데도 `db_service1.orders`처럼 평범해 보이는 테이블이 사실은 `s3tablescatalog` 아래 깊은 경로에 있고, 그래서 권한 ARN이 왜 길어지는지가 보입니다. 다음 편(Lake Formation)의 권한 이야기를 위한 토대이기도 합니다.

> **TL;DR**  
> - **S3 Tables**는 관리형 Apache Iceberg 테이블 버킷입니다. compaction/스냅샷 관리를 AWS가 맡고, ACID/스키마 진화/시간여행을 제공합니다.  
> - S3 Tables를 Glue Data Catalog에 통합하면 기본 카탈로그(default) 안에 **`s3tablescatalog`라는 federated 카탈로그**가 생깁니다.  
> - 매핑: **table bucket -> catalog, namespace -> database, table -> table**. 즉 카탈로그가 중첩됩니다.  
> - 그래서 federated 테이블의 ARN은 `catalog/s3tablescatalog/{bucket}/{db}`처럼 일반 테이블보다 **경로가 깊어집니다**.  
{: .prompt-info}

---

## 1. Amazon S3 Tables - 관리형 Iceberg

### 1.1. 왜 Iceberg인가

1편에서 짚었듯이, 초기 데이터 레이크(S3 + Parquet 파일 더미)는 트랜잭션이 없고 부분 수정이 어렵습니다. **Apache Iceberg**는 S3 위에 테이블 포맷을 얹어 이 한계를 해결합니다. ACID 트랜잭션, 스키마 진화(컬럼 추가/삭제), 시간여행(과거 스냅샷 조회) 같은 기능을 파일 더미가 아닌 "진짜 테이블" 수준으로 제공합니다.

### 1.2. S3 Tables가 더하는 것

Iceberg를 직접 운영하려면 메타데이터 파일 관리, compaction(작은 파일 병합), 스냅샷 정리(garbage collection) 같은 유지보수를 직접 해야 합니다. **Amazon S3 Tables**는 이 유지보수를 관리형으로 처리하는 전용 스토리지(**table bucket**)입니다.

일반 S3 버킷과의 차이는 다음과 같습니다.

| 항목 | 일반 S3 버킷 | S3 Tables (table bucket) |
| :--- | :--- | :--- |
| 저장 단위 | 객체(파일) | 테이블(Iceberg) |
| 테이블 관리 | 직접(또는 Glue) | 관리형(compaction/스냅샷 자동) |
| 트랜잭션 | 없음 | ACID |
| 접근 | S3 객체 API | 테이블 API + 분석 엔진 |

table bucket 안에는 **namespace**(논리적 그룹)가 있고, 그 안에 **table**이 있습니다. 이 구조가 곧 Glue Catalog에 매핑되는 단위입니다.

> S3 Tables의 실데이터는 관리형 스토리지에 보관됩니다. 일반 S3 객체 ARN으로 직접 다루는 모델이 아니라, 분석 엔진이 카탈로그를 통해 접근한다는 점이 일반 S3와 다릅니다.  
{: .prompt-tip}

### 1.3. Iceberg가 주는 것 - 스키마 진화와 시간여행

Iceberg 테이블이라, 일반 파일 테이블에서는 까다롭던 작업이 SQL로 가능합니다.

```sql
-- 컬럼 추가(스키마 진화) - 기존 데이터를 다시 쓰지 않아도 된다
ALTER TABLE sales_db.orders ADD COLUMNS (coupon_id bigint);

-- 시간여행(time travel) - 과거 스냅샷 조회
SELECT * FROM sales_db.orders FOR TIMESTAMP AS OF (current_timestamp - interval '1' day);
```

스키마를 바꿔도 과거 데이터를 재적재할 필요가 없고, 특정 시점의 스냅샷을 그대로 조회할 수 있습니다. 이런 기능이 S3 Tables(관리형 Iceberg)를 단순한 파일 더미와 구분 짓는 지점입니다.

---

## 2. Catalog Federation - default vs federated

### 2.1. 기본 카탈로그(default)

지금까지 다룬 일반 Glue 테이블은 **기본 카탈로그(default Data Catalog)** 에 있습니다. 이 카탈로그의 ID는 계정 ID이며, Athena에서는 **`AwsDataCatalog`** 라는 이름으로 보입니다. `logs_db` 같은 일반 데이터베이스가 여기에 직접 속합니다.

### 2.2. federated 카탈로그(s3tablescatalog)

S3 Tables를 Glue Data Catalog에 통합하면, 기본 카탈로그 **안에 `s3tablescatalog`라는 federated 카탈로그**가 만들어집니다. 그리고 S3 Tables의 리소스가 다음과 같이 매핑됩니다.

- **table bucket -> 카탈로그**(multi-level)
- **namespace -> 데이터베이스**
- **table -> 테이블**

즉 카탈로그 안에 카탈로그가 들어가는 **중첩 구조**가 됩니다. 그림으로 보면 다음과 같습니다.

![카탈로그 중첩 구조 - Default Catalog 안에 s3tablescatalog(federated)와 table bucket, namespace, table이 중첩](/assets/img/aws/analytics-stack-06-catalog-federation.webp)

왼쪽의 `logs_db`는 기본 카탈로그에 직접 속한 일반 데이터베이스입니다. 오른쪽은 `s3tablescatalog` -> table bucket -> namespace -> table 순으로 중첩된 S3 Tables 경로입니다. 같은 "테이블"이지만 한쪽은 평면, 한쪽은 깊은 계층에 있습니다.

---

## 3. ARN이 깊어지는 이유

이 중첩이 실무에서 체감되는 지점이 바로 **ARN**입니다. 2편에서 본 일반 테이블 ARN과 비교해 봅니다.

```text
# 일반 Glue 테이블 (default catalog)
arn:aws:glue:<region>:<account-id>:database/logs_db
arn:aws:glue:<region>:<account-id>:table/logs_db/app_events

# S3 Tables (federated catalog)
arn:aws:glue:<region>:<account-id>:catalog/s3tablescatalog/{bucket}/{db}
arn:aws:glue:<region>:<account-id>:table/{bucket}/{db}/orders
```

federated 카탈로그는 `catalog > database > table` 단계가 `s3tablescatalog/{bucket}` 아래로 한 겹 더 들어갑니다. 그래서 IAM 정책에서 S3 Tables 테이블에 권한을 줄 때는, 일반 테이블보다 **카탈로그 레벨 ARN까지 함께** 지정해야 합니다. 이 부분은 권한을 다루는 다음 편에서 더 구체적으로 이어집니다.

---

## 4. Athena에서 federated 테이블 쿼리

Athena에서 S3 Tables 테이블을 쿼리할 때는 카탈로그를 지정해야 합니다. 콘솔의 쿼리 에디터라면 **Catalog** 필드를 `s3tablescatalog/{bucket}` 형태로 선택하고, Database에 namespace를 지정합니다.

SQL에서 명시적으로 카탈로그를 적을 수도 있습니다. 일반 카탈로그와 federated 카탈로그를 함께 조인할 때 특히 유용합니다.

```sql
SELECT o.order_id, o.amount
FROM "s3tablescatalog/amzn-s3-demo-bucket".sales_db.orders o
WHERE o.dt = '2026-04-14'
LIMIT 100;
```

```sql
-- 일반 테이블(logs_db)과 S3 Tables(sales_db)를 함께 조인
SELECT e.user_id, sum(o.amount) AS spent
FROM logs_db.app_events e
JOIN "s3tablescatalog/amzn-s3-demo-bucket".sales_db.orders o
  ON e.user_id = o.buyer_id
WHERE e.dt = '2026-04-14'
GROUP BY e.user_id;
```

`logs_db`는 기본 카탈로그라 짧은 이름으로, `sales_db.orders`는 federated 카탈로그라 `"s3tablescatalog/{bucket}"` 접두어로 참조합니다.

> 카탈로그가 Athena 데이터 소스로 인식되지 않으면 `CATALOG_NOT_FOUND`가 납니다. 이는 단순 오타일 수도, 권한 문제일 수도 있습니다. 권한 쪽 원인은 다음 편에서 자세히 다룹니다.  
{: .prompt-warning}

---

## 5. 실습 - S3 Tables 만들고 쿼리하기

S3 table bucket이 Glue Data Catalog에 통합돼 있다는 전제 아래, Athena에서 namespace와 테이블을 만들고 쿼리해 봅니다. 콘솔이라면 **Catalog** 필드를 `s3tablescatalog/{bucket}`로 선택한 뒤 아래를 실행합니다.

### 5.1. namespace와 테이블 생성

```sql
-- namespace(=database) 생성
CREATE DATABASE sales_db;

-- Iceberg 테이블 생성 (S3 Tables는 LOCATION을 지정하지 않는다 - 관리형)
CREATE TABLE sales_db.orders (
    order_id bigint,
    buyer_id bigint,
    amount   double,
    dt       date
)
TBLPROPERTIES ('table_type' = 'iceberg');
```

일반 외부 테이블과 달리 **`LOCATION`을 적지 않습니다.** S3 Tables가 스토리지 위치를 관리하기 때문입니다.

### 5.2. 데이터 적재와 조회

```sql
INSERT INTO sales_db.orders VALUES
    (1, 1001, 12000.0, DATE '2026-04-14'),
    (2, 1002,  8000.0, DATE '2026-04-14');

SELECT dt, count(*) AS cnt, sum(amount) AS revenue
FROM sales_db.orders
GROUP BY dt;
```

### 5.3. 방금 무슨 일이 일어났나

- `CREATE DATABASE` / `CREATE TABLE` -> **`s3tablescatalog` 아래 namespace/table**이 만들어지고 Glue Catalog에 federated로 노출됩니다.
- `LOCATION` 없음 -> S3 Tables가 관리하는 스토리지에 데이터가 저장됩니다.
- `INSERT` / `SELECT` -> Iceberg 테이블이라 트랜잭션과 스냅샷이 적용됩니다.
- SQL 자체는 일반 Glue 테이블과 거의 같지만, **카탈로그 경로(federated)와 관리형 스토리지**라는 점이 다릅니다.

---

## 6. 다음 글

이번 편에서는 S3 Tables가 무엇이고, Catalog Federation으로 기본 카탈로그 안에 어떻게 중첩되는지, 그래서 ARN이 왜 깊어지는지를 정리했습니다.

다음 글에서는 이 federated 데이터에 한 겹 더 얹히는 권한 계층, **AWS Lake Formation**을 다룹니다. S3 Tables 레이크하우스 데이터는 IAM만으로는 접근할 수 없고, Lake Formation의 grant가 함께 있어야 합니다. 왜 그런지, 어떻게 부여하는지를 이어서 풀어갑니다.

---

## 7. Reference

- [Amazon S3 Tables](https://docs.aws.amazon.com/AmazonS3/latest/userguide/s3-tables.html)
- [Querying Amazon S3 tables with Athena](https://docs.aws.amazon.com/AmazonS3/latest/userguide/s3-tables-integrating-athena.html)
- [Register S3 table bucket catalogs and query Tables from Athena](https://docs.aws.amazon.com/athena/latest/ug/gdc-register-s3-table-bucket-cat.html)
- [Amazon S3 Tables integration with AWS Glue Data Catalog and Lake Formation](https://docs.aws.amazon.com/lake-formation/latest/dg/create-s3-tables-catalog.html)
- [Apache Iceberg](https://iceberg.apache.org/)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
