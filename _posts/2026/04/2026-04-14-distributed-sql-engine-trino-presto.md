---
title: 분산 SQL 엔진이란 - Trino/Presto와 단일 노드 SQL 엔진의 차이
date: 2026-04-14 09:00:00 +0900
author: kkamji
categories: [Cloud, AWS]
tags: [aws, athena, trino, presto, distributed-sql, query-engine, mpp]
comments: true
image:
  path: /assets/img/aws/analytics-stack-03-distributed-sql-mpp.webp
---

데이터 레이크나 레이크하우스에 쌓인 대규모 데이터를 SQL로 빠르게 조회하는 일의 중심에는 **분산 SQL 엔진**이 있습니다. Amazon Athena가 데이터를 옮기지 않고도 여러 소스를 한 쿼리로 조인하고 빠르게 응답하는 것도, 그 바탕에 분산 SQL 엔진이 있기 때문입니다. 이번 글에서는 SQL 엔진이 무엇이고, 단일 노드 엔진과 분산 SQL 엔진(Trino/Presto)이 어떻게 다른지, 그리고 Athena가 그것을 어떻게 활용하는지를 알아봅니다.

> **TL;DR**  
> - **SQL 엔진(쿼리 엔진)** 은 데이터를 저장하지 않고 쿼리를 실행하는 컴퓨트 계층입니다. 저장과 분리돼 외부 스토리지를 읽습니다.  
> - **단일 노드 엔진**은 한 프로세스가 모든 일을 하므로 한 대의 자원에 묶입니다.  
> - **분산 SQL 엔진(MPP)** 은 **coordinator + worker** 구조로 쿼리를 여러 worker에 쪼개 병렬 처리합니다.  
> - **Presto**(Facebook, 2012)가 이 계보를 열었고, 2019년 분기 후 **Trino**(2020년 리브랜드)로 이어집니다.  
> - **Amazon Athena**는 이 엔진을 서버리스로 감싼 관리형 서비스입니다. engine v3는 **Trino** 기반입니다.  
{: .prompt-info}

---

## 1. SQL 엔진과 데이터베이스는 다르다

흔히 SQL을 떠올리면 MySQL, PostgreSQL 같은 데이터베이스를 생각합니다. 하지만 분석 스택에서 말하는 **SQL 엔진(query engine)** 은 그것과 결이 다릅니다.

- **데이터베이스**: 데이터를 **저장**하면서 동시에 쿼리를 **실행**합니다. 저장(storage)과 엔진(compute)이 한 시스템에 묶여 있습니다.
- **쿼리 엔진**: 데이터를 직접 저장하지 않습니다. **외부 스토리지(S3 등)에 있는 데이터를 읽어 쿼리만 실행**하는 컴퓨트 계층입니다.

즉 쿼리 엔진은 storage와 compute가 분리된 모델입니다. Athena가 S3의 데이터를 적재 없이 조회할 수 있는 것도, 엔진이 스토리지와 분리돼 있기 때문입니다. Trino/Presto가 바로 이런 쿼리 엔진이고, Athena는 그것을 관리형으로 제공합니다.

---

## 2. 단일 노드 SQL 엔진의 한계

쿼리를 실행하는 가장 단순한 형태는 **단일 노드(single-node)** 엔진입니다. 한 프로세스가 쿼리를 파싱하고, 데이터를 읽고, 집계까지 모두 수행합니다. SQLite나 한 대로 운영하는 데이터베이스 인스턴스가 여기에 가깝습니다.

이 방식은 단순하지만, 처리량이 **한 대의 CPU/메모리/디스크**에 묶입니다. 데이터가 수 TB로 커지거나 무거운 집계가 들어오면, 한 프로세스가 모든 데이터를 순차적으로 스캔하느라 한계에 부딪힙니다. 더 큰 장비로 바꾸는 수직 확장(scale-up)에는 물리적 상한이 있습니다.

분석 워크로드는 많은 행을 스캔해 집계하는 특성이 있어, 이 한계가 특히 두드러집니다. 그래서 작업을 여러 대에 나눠 병렬로 처리하는 방식이 필요해졌습니다.

---

## 3. 분산 SQL 엔진 = MPP

분산 SQL 엔진은 **MPP(Massively Parallel Processing)** 구조로 이 한계를 풉니다. 하나의 쿼리를 여러 노드에 쪼개 동시에 처리하는 방식입니다.

![분산 SQL 엔진의 coordinator-worker MPP 구조](/assets/img/aws/analytics-stack-03-distributed-sql-mpp.webp)

### 3.1. coordinator와 worker

분산 SQL 엔진은 두 종류의 노드로 구성됩니다.

- **Coordinator**: 클라이언트의 쿼리를 받아 파싱하고, 분석/최적화해 실행 계획을 세우고, 작업을 worker에 분배하고 스케줄링합니다.
- **Worker**: coordinator가 나눠 준 작업을 실제로 실행합니다. 데이터 소스에서 데이터를 읽어 처리합니다.

다이어그램처럼, 한 쿼리가 들어오면 coordinator가 그것을 잘게 나눠 여러 worker에 분배하고, worker들이 **동시에 병렬로** 데이터를 스캔/처리한 뒤 결과를 모아 클라이언트에 돌려줍니다. 노드를 늘리면 처리량이 늘어나는 **수평 확장(scale-out)** 이 가능합니다.

### 3.2. stage, task, split

쿼리는 여러 단계로 쪼개집니다. coordinator는 실행 계획을 **stage**로 나누고, 각 stage를 worker에서 실행할 **task**로, 데이터를 다시 **split**(읽을 데이터 조각) 단위로 나눕니다. 여러 worker가 여러 split을 동시에 처리하므로, 데이터가 커져도 worker를 늘려 대응할 수 있습니다.

### 3.3. 메모리 파이프라인 실행

Trino/Presto가 빠른 또 다른 이유는 **메모리 기반 파이프라인 실행**입니다. 초기 빅데이터 엔진인 Hive는 MapReduce 위에서 동작해, 단계마다 중간 결과를 디스크에 쓰고 다음 단계가 그것을 다시 읽었습니다. 이 디스크 왕복이 대화형 쿼리에는 큰 지연으로 작용했습니다.

분산 SQL 엔진은 이를 다르게 처리합니다. stage 사이의 데이터를 디스크에 쓰지 않고 **메모리에서 worker 간으로 흘려보내며(streaming/pipelining)** 처리합니다. 한 stage의 결과가 만들어지는 대로 다음 stage가 이어받아, 디스크 왕복 없이 파이프라인처럼 흐릅니다. 이 구조 덕분에 분산 SQL 엔진은 storage와 compute가 분리된 채로, 외부 스토리지의 대규모 데이터를 병렬로 빠르게 조회합니다.

---

## 4. Presto에서 Trino로

이 계보의 출발점은 **Presto**입니다.

### 4.1. Presto (Facebook, 2012)

Presto는 Facebook(현 Meta)에서 2012년에 개발됐고, 2013년 11월 오픈소스로 공개됐습니다. 당시 Facebook은 거대한 데이터 웨어하우스를 Apache Hive로 조회했는데, Hive(MapReduce 기반)가 대화형 분석에는 너무 느려 더 빠른 대안이 필요했습니다. 앞서 본 메모리 파이프라인 실행이 바로 이 문제를 푼 핵심이었습니다. Presto는 "빅데이터를 위한 분산 SQL 쿼리 엔진"으로, 여러 데이터 소스를 한 쿼리로 조회할 수 있도록 설계됐습니다. 창시자는 Martin Traverso, Dain Sundstrom, David Phillips, Eric Hwang입니다.

### 4.2. 분기와 Trino 리브랜드 (2019~2020)

Presto는 2019년에 갈라집니다. 2019년 1월 Presto Software Foundation이 만들어지면서 개발이 두 갈래로 나뉘었습니다.

- **PrestoDB**: Facebook이 유지. 2019년 9월 Linux Foundation에 기부되어 Presto Foundation으로 이관됐습니다.
- **PrestoSQL**: 원 창시자들(Martin Traverso, Dain Sundstrom, David Phillips 등)이 유지하던 갈래로, 2020년 12월 **Trino**로 리브랜드됐습니다.

오늘날 "Trino"와 "Presto"는 같은 뿌리에서 갈라진 두 프로젝트입니다. 둘 다 분산 SQL 쿼리 엔진이라는 정체성은 같습니다.

---

## 5. connector 모델 - federation

분산 SQL 엔진의 강력한 특징 중 하나가 **connector** 모델입니다. 엔진 자체는 데이터를 저장하지 않으므로, 어떤 데이터 소스든 **connector**를 통해 연결해 읽을 수 있습니다.

Trino/Presto는 S3 같은 객체 스토리지뿐 아니라 MySQL, PostgreSQL, Cassandra, Kafka, MongoDB, Elasticsearch 등 다양한 소스용 connector를 제공합니다. 덕분에 **서로 다른 소스의 데이터를 한 쿼리로 조인**하는 federation(연합 쿼리)이 가능합니다. 데이터를 한곳으로 옮기지 않고도, 엔진이 각 소스에서 필요한 데이터를 읽어 합칩니다.

```sql
-- 개념 예시: 객체 스토리지의 테이블과 관계형 DB의 테이블을 한 쿼리로 조인
SELECT o.id, c.grade
FROM lake.sales.orders o
JOIN mysql.crm.customers c ON c.id = o.customer_id;
```

connector는 단순히 데이터를 읽어 오기만 하는 것이 아닙니다. 가능한 경우 필터와 컬럼 선택을 데이터 소스 쪽으로 내려보내는 **pushdown**(predicate/projection pushdown)을 수행합니다. 예를 들어 관계형 DB connector는 `WHERE` 조건을 소스 DB에서 먼저 거르게 하고, 컬럼 기반 파일에서는 필요한 컬럼만 읽습니다. 엔진으로 가져오는 데이터 양 자체를 줄여, 네트워크와 처리 비용을 함께 낮춥니다.

이 connector 기반 federation이 분산 SQL 엔진을 단순한 쿼리 실행기를 넘어 **여러 데이터 소스를 통합하는 계층**으로 만들어 줍니다.

---

## 6. Amazon Athena는 관리형 Trino/Presto

Athena가 "서버리스 쿼리 엔진"인 이유가 여기서 분명해집니다. Athena는 이 분산 SQL 엔진을 **서버리스로 감싼 관리형 서비스**입니다. 사용자는 coordinator/worker 클러스터를 직접 운영하지 않고, 쿼리만 던지면 AWS가 그 아래에서 엔진을 실행합니다. Athena 자체의 쿼리 흐름과 메타스토어는 이 시리즈의 뒤쪽 글에서 자세히 다룹니다.

Athena의 엔진 버전은 오픈소스 프로젝트와 직접 연결됩니다.

- **engine version 1/2**: Presto 기반
- **engine version 3**: Trino 기반. AWS 문서에 따르면 engine version 3는 Trino, Presto 프로젝트와의 연속적 통합(CI) 방식을 도입해, 커뮤니티 개선을 더 빠르게 반영합니다.

다만 차이도 있습니다. Athena는 Trino/Presto의 native connector를 그대로 쓰지 않고, 외부 소스 연결에는 **Amazon Athena Federated Query**(Lambda 기반 커넥터)를 사용합니다. 즉 federation의 개념은 같지만 구현 방식이 AWS 환경에 맞춰져 있습니다.

> 정리하면, Athena로 쿼리를 던질 때 그 아래에서는 Trino(engine v3) 엔진이 쿼리를 stage/task/split으로 나눠 병렬 처리하고 있습니다. "서버리스"는 이 엔진 클러스터를 사용자가 운영하지 않아도 된다는 의미입니다.  
{: .prompt-tip}

---

## 7. Spark SQL, Redshift와는 무엇이 다른가

분산 처리를 한다는 점에서 비슷해 보이는 다른 시스템과 간단히 구분해 둡니다.

| 구분 | 성격 |
| :--- | :--- |
| **Trino / Presto** | 대화형 분석에 최적화된 분산 SQL 쿼리 엔진. 저장과 분리, 여러 소스 federation |
| **Spark SQL** | 범용 분산 처리 프레임워크(Spark) 위의 SQL. ETL/배치/ML까지 포함하는 넓은 워크로드 |
| **Amazon Redshift** | 컬럼형 MPP 데이터 웨어하우스. 자체 스토리지에 적재한 정형 데이터 분석에 강함 |

Trino/Presto는 "이미 어딘가에 있는 데이터를 빠르게 조회/조인"하는 대화형 쿼리에 강하고, Spark는 더 넓은 데이터 처리 파이프라인에, Redshift는 적재된 정형 데이터의 고성능 분석에 적합합니다. 셋은 경쟁하기도 하지만 역할이 겹치면서도 달라, 환경에 따라 함께 쓰이는 경우가 많습니다.

---

## 8. Reference

- [Trino - Overview](https://trino.io/docs/current/overview.html)
- [Presto](https://prestodb.io/)
- [Trino concepts (coordinator, worker, connector)](https://trino.io/docs/current/overview/concepts.html)
- [Amazon Athena engine version 3](https://docs.aws.amazon.com/athena/latest/ug/engine-versions-reference-0003.html)
- [Using Amazon Athena Federated Query](https://docs.aws.amazon.com/athena/latest/ug/connect-to-a-data-source.html)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
