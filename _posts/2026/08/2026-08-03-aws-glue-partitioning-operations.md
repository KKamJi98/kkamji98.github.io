---
title: "AWS Glue 파티셔닝 운영하기 - Catalog, Projection, S3 스캔 최소화"
date: 2026-08-03 02:20:00 +0900
author: kkamji
categories: [Cloud, AWS]
tags: [aws, glue, athena, partitioning, partition-projection, s3, query-optimization]
comments: true
image:
  path: /assets/img/aws/aws.webp
---

`WHERE dt BETWEEN '2026-07-10' AND '2026-07-11'`를 넣었는데도 Athena의 DataScannedInBytes가 기대만큼 줄지 않는 경우가 있습니다. SQL 문법은 맞아도, 조건이 partition column에 직접 적용되고 그 값이 등록된 partition location 또는 projection의 location template과 대응하지 않으면 S3 scan 후보는 거의 그대로 남습니다.

앞선 [Athena와 Glue Data Catalog 글](/posts/aws-athena-glue-catalog/)은 Athena가 Catalog에서 테이블 정의를 받고 S3를 읽는 큰 흐름을 다뤘습니다. 여기서는 같은 흐름을 파티션 운영자의 시선으로 좁힙니다. 파티션 디렉터리, Catalog metadata, projection 규칙, 쿼리 predicate가 어떤 계약을 맺어야 실제 S3 scan 후보가 줄어드는지 살펴봅니다.

---

## 1. `WHERE` 절이 S3 scan 후보를 줄이는 조건

이 글에서 다루는 Hive style 파티셔닝은 query predicate가 읽을 partition location을 선택하게 하는 metadata와 layout의 계약입니다. 예를 들어 주문 데이터를 날짜, 리전, 시간으로 나누면 물리 경로는 다음처럼 쌓일 수 있습니다.

```text
s3://example-analytics-lake/orders/
  dt=2026-07-10/region=ap-northeast-2/hour=00/part-000.parquet
  dt=2026-07-10/region=ap-northeast-2/hour=01/part-001.parquet
  dt=2026-07-11/region=us-east-1/hour=00/part-002.parquet
```

위 경로는 Hive style 예시입니다. `MSCK REPAIR TABLE`을 쓸 때에는 partition key와 `key=value` 경로가 대응해야 합니다. 등록형 metadata에서는 `ALTER TABLE ADD PARTITION ... LOCATION`으로 partition value와 location을 연결할 수 있고, 이 location이 Hive style 이름을 꼭 따를 필요는 없습니다. projection table에서는 `storage.location.template`이 같은 역할을 합니다. 핵심은 `dt`, `region`, `hour` predicate가 table의 partition definition과 location mapping을 함께 좁히는 것입니다.

![Athena partition pruning에서 Catalog metadata와 projection 규칙이 S3 prefix 선택으로 이어지는 흐름](/assets/img/aws/aws-glue-partitioning-pruning-flow.webp)

파티션 predicate가 만든 후보 수를 아주 작은 local fixture로 계산해 보겠습니다. 이 계산은 Athena engine이 실제로 pruning했다는 증명이 아닙니다. query predicate와 S3 layout이 일치할 때 선택 공간이 얼마나 줄어드는지 확인하는 장치입니다.

```python
from datetime import date, timedelta

regions = ("ap-northeast-2", "us-east-1")
start = date(2026, 7, 1)
days = [start + timedelta(days=i) for i in range(31)]

all_prefixes = {
    f"dt={day:%Y-%m-%d}/region={region}/hour={hour:02d}/"
    for day in days
    for region in regions
    for hour in range(24)
}
selected = {
    prefix
    for prefix in all_prefixes
    if prefix.startswith((
        "dt=2026-07-10/region=ap-northeast-2/",
        "dt=2026-07-11/region=ap-northeast-2/",
    ))
}

assert len(all_prefixes) == 1488
assert len(selected) == 48
print(f"layout-level selection ratio: {len(selected) / len(all_prefixes):.2%}")
```

실행 결과는 `3.23%`였습니다. 모든 월, 리전, 시간 prefix를 후보로 두는 대신 이틀과 리전 하나만 고르면 1,488개 중 48개가 남습니다. 실제 Athena에서는 query details의 DataScannedInBytes와 execution plan을 함께 봐야 합니다. 이 fixture의 역할은 그 전에 prefix naming과 SQL 조건의 결합이 맞는지 먼저 드러내는 것입니다.

---

## 2. S3 layout과 Glue partition metadata를 같이 설계하기

Athena의 `MSCK REPAIR TABLE`은 Hive style의 `key=value` 경로를 따라 partition metadata를 발견할 수 있습니다. `MSCK`를 쓸 table이라면 S3 layout, table DDL, partition key를 같은 규칙으로 맞춰야 합니다. 반면 `ADD PARTITION ... LOCATION` 또는 projection을 쓰는 table까지 모든 경로를 Hive style로 고정할 필요는 없습니다.

```sql
CREATE EXTERNAL TABLE IF NOT EXISTS analytics.orders (
    order_id bigint,
    buyer_id bigint,
    amount double
)
PARTITIONED BY (
    dt string,
    region string,
    hour string
)
STORED AS PARQUET
LOCATION 's3://example-analytics-lake/orders/';
```

이 DDL은 S3 파일을 이동하지 않습니다. Catalog에 table schema와 partition key를 등록할 뿐입니다. 새 partition을 인식시키는 전략은 데이터 생성 방식에 맞춰 골라야 합니다.

| 방식 | metadata의 주인 | 적합한 상황 | 운영상 주의점 |
| --- | --- | --- | --- |
| `ALTER TABLE ADD PARTITION` | deploy 또는 ingest pipeline | 새 partition 생성 시점이 명확함 | 데이터 write와 metadata 등록이 분리되면 누락될 수 있음 |
| `MSCK REPAIR TABLE` | S3 directory layout | backfill, 기존 Hive style prefix 복구 | 큰 prefix tree를 매번 탐색하는 운영 루프가 되지 않게 범위를 관리해야 함 |
| Glue Crawler | crawler configuration | schema와 partition discovery를 함께 자동화해야 함 | schema drift를 자동 승인하지 않도록 변경 정책이 필요함 |
| partition projection | table property | 가능한 partition 값의 규칙이 작고 예측 가능함 | projection 규칙이 실제 S3 layout과 어긋나면 빈 prefix를 계속 계산할 수 있음 |

`MSCK REPAIR TABLE`은 recovery tool로는 유용하지만, 매 ingestion마다 전 prefix를 재발견하는 기본 운영 방식으로 두기에는 비용과 시간의 경계를 따져야 합니다. `MSCK`는 Hive style partition에만 쓰고, table root 아래에 다른 table의 partition hierarchy를 섞지 않습니다. `MSCK`로 발견할 partition key는 소문자로 유지합니다. 반대로 partition 생성 시점이 pipeline에 분명하면 `ADD PARTITION`을 함께 commit하는 방식이 누락 원인을 좁히기 쉽습니다.

Glue Crawler는 발견을 자동화하지만, schema나 partition path가 예상과 다르게 바뀌었을 때도 Catalog가 변할 수 있습니다. crawler가 편하다는 이유만으로 schema change를 무검토로 받아들이지 말고, table update 정책과 change detection을 별도로 두는 편이 안전합니다.

---

## 3. Partition projection은 metadata 등록을 계산으로 바꾼다

partition projection은 Catalog에 partition row를 계속 적재하는 대신 table property에 값의 범위와 S3 location template을 둡니다. Athena는 쿼리의 partition predicate를 바탕으로 가능한 partition location을 계산합니다.

다음 table은 날짜와 리전이 예측 가능한 경우의 예시입니다.

```sql
ALTER TABLE analytics.orders SET TBLPROPERTIES (
    'projection.enabled' = 'true',
    'projection.dt.type' = 'date',
    'projection.dt.range' = '2026-01-01,NOW',
    'projection.dt.format' = 'yyyy-MM-dd',
    'projection.region.type' = 'enum',
    'projection.region.values' = 'ap-northeast-2,us-east-1',
    'projection.hour.type' = 'integer',
    'projection.hour.range' = '0,23',
    'projection.hour.digits' = '2',
    'storage.location.template' =
      's3://example-analytics-lake/orders/dt=${dt}/region=${region}/hour=${hour}/'
);
```

이 table에서는 `dt`, `region`, `hour` 값을 Catalog partition row에서 읽지 않습니다. 날짜 range, enum, integer range와 storage template이 location 계산의 기준이 됩니다. custom template을 쓸 때에는 모든 partition column의 placeholder가 들어가고 각 partition location이 slash로 끝나야 합니다.

`projection.enabled=true`인 table을 Athena로 조회하면 Athena는 기존 Glue Catalog 또는 Hive metastore에 등록된 partition metadata를 무시합니다. 따라서 Athena query에서는 crawler나 `MSCK REPAIR TABLE` 결과를 projection의 보조 source로 기대하면 안 됩니다. 이 동작은 Athena에만 적용됩니다. 같은 table을 Redshift Spectrum, Athena for Spark, EMR에서도 읽는다면 등록형 partition metadata를 별도로 유지하거나 소비자별 table 설계를 분리합니다.

projection은 partition 수가 많다는 이유만으로 항상 이득이 되지는 않습니다. 가능한 날짜, 리전, 시간 조합은 넓은데 실제 S3 prefix가 드문 sparse layout이라면, Athena가 존재하지 않는 location도 후보로 계산할 수 있습니다. AWS 가이드도 projected partition의 절반을 넘게 비어 있다면 전통적인 Glue partition을 고려하라고 안내합니다. query가 늘 partition key를 충분히 좁히는지, projection range와 실제 데이터 보존 기간이 맞는지 확인한 뒤 선택해야 합니다.

---

## 4. Query predicate는 partition key를 끝까지 유지해야 한다

파티션이 `dt`, `region`, `hour`일 때 scan 후보를 줄이는 query는 이 key를 직접 조건에 남깁니다.

```sql
SELECT
    dt,
    region,
    count(*) AS order_count,
    sum(amount) AS revenue
FROM analytics.orders
WHERE dt BETWEEN '2026-07-10' AND '2026-07-11'
  AND region = 'ap-northeast-2'
  AND hour BETWEEN '09' AND '18'
GROUP BY dt, region
ORDER BY dt, region;
```

`hour`는 문자열이므로 이 범위 조건은 S3 경로와 등록된 partition 값이 모두 `00`부터 `23`까지 zero-padding됐다는 전제에서만 올바릅니다. ingest 단계에서 `hour=9` 같은 비정규 값을 차단합니다.

반대로 event timestamp 같은 일반 column에만 조건을 걸면, 파일 안의 row filtering은 가능해도 partition location 선택 범위는 충분히 줄지 않을 수 있습니다. 시간 단위 partition을 운영하면서 query가 항상 timestamp function으로만 표현된다면, predicate와 partition key가 만나는 지점을 설계에서 다시 확인해야 합니다.

`SELECT *`를 피하고 Parquet 같은 columnar format을 쓰는 일도 여전히 중요합니다. 다만 column pruning과 partition pruning은 대체 관계가 아닙니다. 하나는 파일 내부에서 읽을 column을 줄이고, 다른 하나는 S3에서 열어 볼 prefix와 file set을 줄입니다.

검증 순서는 단순합니다.

1. query 조건에 partition column이 직접 들어 있는지 확인합니다.
2. query details에서 DataScannedInBytes와 partition 수를 같은 workload의 이전 실행과 비교합니다.
3. projection table이면 `projection.*` 속성과 `storage.location.template`이 실제 S3 prefix와 같은지 확인합니다.
4. 등록형 metadata table이면 새 partition이 Catalog에 실제로 보이는지 확인합니다.

`GetQueryExecution` 또는 콘솔 Query details의 DataScannedInBytes를 같은 workload와 비교하고, partition predicate와 등록된 location 또는 projection template의 대응을 따로 확인합니다. DataScannedInBytes가 줄지 않는다고 단일 실행 시간이나 지표만 보고 Athena engine 병목으로 단정하면 안 됩니다. partition filter, S3 layout, file size, column selection, join shape를 분리해서 확인해야 합니다.

---

## 5. Partition index와 권한은 대규모 table의 메타데이터 경계다

등록형 partition metadata가 많은 Glue table에서는 `GetPartitions` 호출 자체가 query planning이나 metadata operation의 병목이 될 수 있습니다. Glue partition index는 특정 partition key 조합의 filter lookup을 빠르게 하도록 만든 index입니다. Athena에서 index를 활용하려면 index를 만든 뒤 다음 table property도 설정합니다.

```sql
ALTER TABLE analytics.orders
SET TBLPROPERTIES ('partition_filtering.enabled' = 'true');
```

GetPartitions filter에는 index의 첫 key가 포함돼야 하며, index 적용은 best effort입니다. index가 없거나 연산자가 지원되지 않으면 전체 partition loading 방식으로 fallback될 수 있습니다. index 생성은 metadata access path를 바꾸는 일이지, S3 file layout이나 Athena scan 자체를 자동으로 재배치하는 기능은 아닙니다.

index를 먼저 만들기보다 다음을 확인하는 편이 낫습니다.

- table에 등록된 partition 수가 실제 운영 부담인지 확인합니다.
- query의 대표 filter가 index key 순서와 맞는지 확인합니다.
- projection이 더 단순한 source of truth인지 비교합니다.
- index 생성과 backfill 기간에 metadata update가 어떤 상태를 보이는지 runbook에 남깁니다.

권한도 함께 점검해야 합니다. partition을 읽거나 관리하는 principal에는 table만이 아니라 Catalog, database, table 계층에 필요한 Glue action이 있어야 합니다. 특히 `glue:GetPartitions`가 빠지면 S3 read 권한이 있어도 metadata 단계에서 실패할 수 있습니다. Lake Formation을 쓰는 table은 IAM만으로 data authorization이 끝나지 않는다는 점도 별도로 확인해야 합니다.

---

## 6. Iceberg에는 Hive style partition key를 그대로 옮기지 않는다

이 글의 DDL과 projection은 일반 Glue external table을 기준으로 합니다. Apache Iceberg table은 hidden partitioning과 partition transform을 사용하므로, query가 항상 `dt`, `hour` 같은 물리 partition key를 직접 알 필요는 없습니다.

예를 들어 Iceberg의 `month(order_time)` transform은 query의 원본 timestamp predicate에서 적절한 partition을 추론할 수 있습니다. partition spec을 바꾸는 partition evolution도 일반 Hive style directory contract와 다른 방식으로 다뤄집니다. Iceberg에 projection property를 그대로 붙여 해결하려 하기보다 [Iceberg table format 글](/posts/apache-iceberg-table-format/)의 hidden partitioning과 metadata layer를 기준으로 별도 설계를 하는 편이 맞습니다.

---

## 7. Reference

- [Amazon Athena User Guide - Partition your data](https://docs.aws.amazon.com/athena/latest/ug/partitions.html)
- [Amazon Athena User Guide - Partition projection](https://docs.aws.amazon.com/athena/latest/ug/partition-projection.html)
- [Amazon Athena User Guide - Set up partition projection](https://docs.aws.amazon.com/athena/latest/ug/partition-projection-setting-up.html)
- [AWS Glue User Guide - Managing partitions for ETL output](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-partitions.html)
- [AWS Glue User Guide - Working with partition indexes](https://docs.aws.amazon.com/glue/latest/dg/partition-indexes.html)
- [Amazon Athena User Guide - Fine-grained access to Glue Data Catalog resources](https://docs.aws.amazon.com/athena/latest/ug/fine-grained-access-to-glue-resources.html)
- [AWS Lake Formation Developer Guide - Permissions reference](https://docs.aws.amazon.com/lake-formation/latest/dg/lf-permissions-reference.html)
- [Amazon Athena User Guide - Query Apache Iceberg tables](https://docs.aws.amazon.com/athena/latest/ug/querying-iceberg.html)
- [Amazon Athena User Guide - Create Apache Iceberg tables](https://docs.aws.amazon.com/athena/latest/ug/querying-iceberg-creating-tables.html)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
