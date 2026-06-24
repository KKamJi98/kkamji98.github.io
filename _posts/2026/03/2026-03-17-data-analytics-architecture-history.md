---
title: 데이터 분석 아키텍처의 역사와 변천사
date: 2026-03-17 09:00:00 +0900
author: kkamji
categories: [Cloud, AWS]
tags: [aws, data-warehouse, data-lake, data-lakehouse, data-mesh, big-data, history]
comments: true
image:
  path: /assets/img/aws/aws.webp
---

이 글은 AWS 데이터 분석 스택 시리즈의 출발점입니다. 데이터 웨어하우스, 데이터 레이크, 레이크하우스 같은 용어는 어느 날 동시에 등장한 것이 아니라, 각각 직전 방식의 한계를 풀면서 **순서대로 진화**한 결과입니다. 이번 글에서는 그 변천사를 시간 축으로 따라가며, 왜 이런 흐름이 생겼는지를 정리합니다. 세 패러다임의 정적인 비교는 이어지는 글에서 따로 다룹니다.

큰 줄기는 두 개의 축으로 볼 수 있습니다. 하나는 **저장/엔진의 기술 축**(먼저 정제하는 웨어하우스 -> 일단 적재하는 레이크 -> 둘을 합친 레이크하우스)이고, 다른 하나는 **조직/처리 방식의 축**(중앙집중 -> 분산 거버넌스, 배치 -> 스트리밍)입니다.

> **TL;DR**  
> - **1세대(1990s) 데이터 웨어하우스**: 적재 전에 정제하는 schema-on-write. Inmon(top-down)과 Kimball(dimensional) 두 학파가 정립했습니다.  
> - **2세대(2006~) 빅데이터/데이터 레이크**: Hadoop이 열고, schema-on-read로 원본을 일단 적재. "Data Lake" 용어는 James Dixon이 2010년에 만들었습니다.  
> - **클라우드 전환(2012~)**: Redshift/Snowflake가 스토리지와 컴퓨트를 분리했고, 2015년경부터 S3 같은 클라우드 오브젝트 스토리지가 HDFS를 대체했습니다.  
> - **3세대(2017~2021) 레이크하우스**: 오픈 테이블 포맷(Iceberg/Delta/Hudi)이 레이크에 ACID를 부여했고, "Lakehouse" 개념은 Databricks의 CIDR 2021 논문이 정립했습니다.  
> - 직교 축으로 **스트리밍**(Lambda 2011, Kappa 2014)과 **조직**(Data Mesh 2019) 흐름이 있습니다.  
{: .prompt-info}

아래 타임라인이 전체 흐름을 한눈에 보여 줍니다. 오른쪽이 저장/엔진의 기술 축, 왼쪽이 스트리밍/조직 축입니다.

![데이터 분석 아키텍처 변천사 타임라인](/assets/img/aws/analytics-stack-01-architecture-history.webp)

---

## 1. 분석은 운영과 다르다

변천사의 출발점에는 두 종류의 워크로드가 있습니다. **OLTP(Online Transaction Processing)** 는 주문 생성처럼 짧고 빈번한 트랜잭션을 처리하는 운영 DB의 영역이고, **OLAP(Online Analytical Processing)** 는 대량의 행을 스캔해 집계하는 분석의 영역입니다. 운영 DB에 분석 쿼리를 그대로 돌리면 성능이 나오지 않고 서비스에도 영향을 줍니다.

이 간극을 메우기 위해 분석 전용 저장소가 필요해졌고, 그 저장소를 어떻게 구성하느냐가 시대별로 달라지면서 지금의 변천사가 만들어졌습니다.

---

## 2. 1세대: 데이터 웨어하우스 (1990s)

가장 먼저 자리 잡은 것은 **데이터 웨어하우스**입니다. 여러 운영 시스템의 데이터를 통합해 분석에 최적화된 형태로 저장하는 "단일 진실 공급원"을 목표로 했습니다.

이 시기를 정립한 두 인물이 있습니다.

- **Bill Inmon**: 1992년 저서 『Building the Data Warehouse』에서 **top-down** 접근을 제시했습니다. 정규화된 전사 데이터 웨어하우스(EDW)를 먼저 구축하고, 거기서 부서별 **데이터 마트(data mart)** 를 파생시키는 방식입니다.
- **Ralph Kimball**: 1996년 저서 『The Data Warehouse Toolkit』에서 **bottom-up** 접근과 **dimensional modeling**(star schema)을 제시했습니다. 분석 주제별 데이터 마트를 먼저 만들어 통합하는 방식입니다.

두 학파 모두 공통적으로 **schema-on-write**를 따릅니다. 데이터를 적재하기 전에 스키마를 확정하고 ETL로 정제한 뒤 넣으므로, 저장 시점에 이미 정돈돼 있어 조회가 빠릅니다. 대신 정형 데이터에 한정되고 스키마 변경이 경직적입니다.

---

## 3. OLAP과 MPP 어플라이언스 (2000s)

웨어하우스 위에서 분석을 빠르게 하기 위한 기술도 발전했습니다. **OLAP**은 데이터를 미리 다차원 큐브(cube)로 집계해 두고 차원을 바꿔 가며 빠르게 조회하는 방식입니다. 저장 방식에 따라 다차원 저장(MOLAP)과 관계형 기반(ROLAP)으로 나뉩니다.

규모가 커지면서 **MPP(Massively Parallel Processing)** 어플라이언스도 등장했습니다. Teradata, Netezza, Greenplum 같은 제품은 데이터를 여러 노드에 분산하고 쿼리를 병렬 처리해, 대량 집계를 빠르게 수행했습니다. 다만 이 시기의 시스템은 대체로 **컴퓨트와 스토리지가 한 어플라이언스에 묶여** 있어, 둘을 따로 늘릴 수 없다는 한계가 있었습니다. 이 한계는 뒤의 클라우드 전환에서 풀립니다.

---

## 4. 2세대: 빅데이터와 데이터 레이크 (2006~)

2000년대 후반, 웹 규모의 비정형 데이터가 폭증하면서 정형 웨어하우스만으로는 감당하기 어려워졌습니다. 여기서 **빅데이터** 시대가 열립니다.

### 4.1. Hadoop

**Hadoop**은 Doug Cutting과 Mike Cafarella가 만들었고, 첫 릴리스는 2006년입니다(Cutting은 당시 Yahoo 소속). Google의 GFS/MapReduce 논문(2003~2004)에서 영향을 받아, **HDFS**(분산 파일 시스템) + **MapReduce**(분산 처리) 조합으로 commodity 하드웨어 위에서 대규모 데이터를 처리했습니다. 정형 스키마를 강제하지 않고 원본을 그대로 담을 수 있다는 점이 결정적이었습니다.

### 4.2. "Data Lake" 용어와 schema-on-read

"Data Lake"라는 용어는 Pentaho의 창립자 **James Dixon**이 2010년 블로그 글에서 만들었습니다. 그는 데이터 마트를 "병에 담긴 물(정제된 데이터)"에, 데이터 레이크를 "더 자연 상태의 큰 물 덩어리(원본 데이터)"에 비유했습니다. 미래에 어떤 질문을 던질지 미리 알 수 없으니 원본을 그대로 저장해 두자는 것이 핵심입니다.

이것이 웨어하우스와 반대되는 **schema-on-read**입니다. 적재할 때는 스키마를 강제하지 않고, 읽는 시점에 구조를 부여합니다. 저장이 싸고 유연하지만, 관리가 없으면 무엇이 믿을 만한지 추적되지 않는 **데이터 늪(data swamp)** 이 되고, 파일 더미 위에서는 ACID 트랜잭션 같은 기능이 어렵다는 약점이 있었습니다.

---

## 5. 클라우드 전환과 스토리지-컴퓨트 분리 (2012~)

다음 변화는 클라우드에서 왔습니다. **Amazon Redshift**는 2012년 re:Invent에서 preview로 공개되고 2013년 초 GA되며, 관리형 클라우드 데이터 웨어하우스를 대중화했습니다. 뒤이어 **Snowflake**는 SIGMOD 2016 논문 「The Snowflake Elastic Data Warehouse」에서 멀티클러스터 구조를 기술하며 등장했습니다.

이 시기의 핵심 키워드는 **스토리지-컴퓨트 분리(separation of storage and compute)** 입니다. 이전 MPP 어플라이언스가 둘을 묶어 두었던 것과 달리, 클라우드 웨어하우스는 데이터를 저비용 스토리지에 두고 컴퓨트를 독립적으로 늘리거나 줄일 수 있게 했습니다. 워크로드별로 컴퓨트를 격리하고 탄력적으로 확장하는 것이 가능해졌습니다.

같은 흐름에서 데이터 레이크의 저장 계층도 바뀝니다. 2015년경부터 **S3, ADLS, GCS 같은 클라우드 오브젝트 스토리지가 HDFS를 대체**하기 시작했습니다. 많은 조직이 원본은 클라우드 레이크에 두고, 그중 일부를 다운스트림 웨어하우스(Redshift, Snowflake 등)로 옮겨 분석하는 **2계층(two-tier) 구조**를 갖게 됩니다. 이 구조의 중복과 복잡성이 다음 세대의 동기가 됩니다.

---

## 6. 3세대: 테이블 포맷과 레이크하우스 (2017~2021)

2계층 구조는 같은 데이터를 레이크와 웨어하우스에 이중으로 두고 동기화해야 하는 부담이 있었습니다. 이를 풀기 위해, **레이크의 저장 위에 웨어하우스의 기능을 직접 얹으려는** 시도가 나옵니다.

### 6.1. 오픈 테이블 포맷

그 열쇠가 **오픈 테이블 포맷**입니다. S3 같은 객체 스토리지의 파일 더미(Parquet/ORC) 위에 메타데이터 계층을 얹어, 파일을 "진짜 테이블"처럼 다루게 합니다.

- **Apache Iceberg**: Netflix에서 시작됐으며(Ryan Blue, Dan Weeks), 기존 파일 위에 atomicity, snapshot isolation, 안전한 스키마 진화를 부여합니다.
- **Delta Lake**: Databricks가 2019년 4월 24일 Apache 2.0으로 오픈소스화했습니다. 트랜잭션 로그 기반으로 ACID 트랜잭션과 데이터 버저닝(시간여행)을 제공합니다.
- **Apache Hudi**: Uber에서 시작된 또 다른 테이블 포맷으로, 같은 계열의 기능을 제공합니다.

이들 덕분에 레이크에서도 ACID 트랜잭션, 스키마 진화, 시간여행, 행 단위 수정이 가능해졌습니다.

### 6.2. Lakehouse 개념의 정립

이 결합을 하나의 아키텍처로 정립한 것이 Databricks의 **CIDR 2021 논문** 「Lakehouse: A New Generation of Open Platforms that Unify Data Warehousing and Advanced Analytics」입니다. 논문은 레이크하우스를 "저비용·직접접근 스토리지 위에 ACID 트랜잭션, 데이터 버저닝, 인덱싱, 쿼리 최적화 같은 전통적 분석 DBMS 기능을 더한 시스템"으로 정의합니다.

흥미롭게도 이 논문은 역사를 **3세대로 명시적으로 프레이밍**합니다. 1세대는 schema-on-write 웨어하우스(온프레미스 어플라이언스, 컴퓨트/스토리지 결합), 2세대는 Hadoop/HDFS로 시작해 클라우드 오브젝트 스토리지로 옮겨 간 schema-on-read 레이크(+다운스트림 웨어하우스), 3세대가 둘을 통합한 레이크하우스입니다. 앞 절들에서 따라온 흐름이 1차 출처의 서사와 그대로 맞아떨어집니다.

> "Lakehouse"라는 단어 자체는 2021년 이전에도 산발적인 마케팅 용례가 있었습니다. 다만 데이터 레이크와 웨어하우스를 통합하는 아키텍처 **개념을 정립**한 것은 위 CIDR 2021 논문으로 보는 것이 정확합니다.  
{: .prompt-tip}

---

## 7. 또 다른 축: 스트리밍 아키텍처

지금까지가 저장 방식의 축이라면, 직교하는 축으로 **처리 방식**의 변화가 있습니다. 배치에서 실시간으로 넘어가는 흐름입니다.

- **Lambda 아키텍처**: Nathan Marz가 2011년 글에서 제시했습니다. 전체 데이터를 정확히 처리하는 **batch layer**와 최근 데이터를 빠르게 처리하는 **speed layer**를 함께 두고, batch 결과가 speed 결과를 결국 덮어쓰는 구조입니다. 정확성과 실시간성을 둘 다 잡지만, 두 계층의 로직을 따로 작성해야 하는 부담이 있습니다.
- **Kappa 아키텍처**: Jay Kreps가 2014년 글 「Questioning the Lambda Architecture」에서 제안했습니다. batch 계층을 없애고 **단일 스트림 처리** 하나로 통합합니다. 재처리가 필요하면 Kafka 같은 로그에 보관된 데이터를 처음부터 다시 흘려보내는 방식으로, 두 시스템을 따로 유지하는 복잡성을 줄입니다.

---

## 8. 또 다른 축: 조직과 거버넌스

규모가 커지면서 기술뿐 아니라 **누가 데이터를 소유하고 책임지느냐**도 문제가 됐습니다. 중앙 팀 하나가 모든 데이터를 책임지는 모델이 병목이 되자, 분산 거버넌스 흐름이 나옵니다.

- **Data Mesh**: Zhamak Dehghani(ThoughtWorks)가 2019년에 처음 제안하고 2020년 글에서 **4원칙**으로 정리했습니다. (1) 도메인 중심의 분산 데이터 소유(domain-oriented decentralized ownership), (2) 데이터를 product로(data as a product), (3) 셀프서비스 데이터 플랫폼(self-serve data infrastructure as a platform), (4) 연합 거버넌스(federated computational governance). 중앙집중 대신 도메인 팀이 각자의 데이터를 product로 책임지는 모델입니다.
- **Data Fabric**: Gartner 등이 제시한 개념으로, 메타데이터를 기반으로 흩어진 데이터를 통합 조회하는 기술 계층에 가깝습니다. Data Mesh가 **조직/소유권**의 분산이라면, Data Fabric은 **기술/통합**의 자동화라는 점에서 결이 다릅니다.

---

## 9. 최근 흐름

레이크하우스 이후로도 변화는 이어지고 있습니다. 자주 언급되는 두 가지를 짚어 둡니다.

- **Medallion architecture**: 레이크/레이크하우스에서 데이터를 품질 단계별로 계층화하는 패턴입니다. 원본을 그대로 받는 **bronze**, 정제/검증한 **silver**, 분석/집계용으로 가공한 **gold**의 3단계로 나눠, 같은 저장소 안에서 데이터를 점진적으로 다듬습니다. 레이크의 "일단 적재"와 웨어하우스의 "정제된 결과"를 한 흐름으로 잇는 실용적 구성입니다.
- **Zero-ETL**: 소스와 분석 저장소 사이의 ETL 파이프라인을 직접 구축하는 부담을 줄이려는 흐름입니다. 운영 DB의 변경을 분석 측으로 자동 반영해, 복제 파이프라인을 별도로 운영하지 않고도 최신 데이터를 분석하려는 시도입니다.

두 흐름 모두 앞선 변천사의 연장선에 있습니다. 정제와 적재의 경계를 더 매끄럽게 잇고, 파이프라인 운영 부담을 줄이는 방향입니다.

---

## 10. 정리

두 축으로 변천사를 요약하면 다음과 같습니다.

- **기술 축(저장/엔진)**: 먼저 정제(웨어하우스, schema-on-write) -> 일단 적재(레이크, schema-on-read) -> 둘을 합침(레이크하우스). 그 사이에 클라우드 전환과 스토리지-컴퓨트 분리가 있었습니다.
- **조직/처리 축**: 배치 -> 스트리밍(Lambda/Kappa), 그리고 중앙집중 -> 분산 거버넌스(Data Mesh).

각 단계는 직전 방식의 한계를 풀면서 등장했습니다. 웨어하우스의 경직성을 레이크가, 레이크의 통제 부재를 레이크하우스가, 중앙 병목을 데이터 메시가 풀어 온 흐름입니다. 새 패러다임이 옛 것을 완전히 대체했다기보다, 각자의 트레이드오프를 이해하고 상황에 맞게 선택하거나 함께 쓰는 것이 현실적인 접근입니다.

AWS 스택에서 이 흐름이 어떤 서비스로 구현되는지는 이 시리즈의 이어지는 글들에서 다룹니다.

---

## 11. Reference

- [James Dixon - Pentaho, Hadoop, and Data Lakes (2010)](https://jamesdixon.wordpress.com/2010/10/14/pentaho-hadoop-and-data-lakes/)
- [Apache Hadoop](https://hadoop.apache.org/)
- [Amazon Redshift - ten years of continuous reinvention](https://www.amazon.science/latest-news/amazon-redshift-ten-years-of-continuous-reinvention)
- [Databricks - Open Sourcing Delta Lake (2019)](https://www.databricks.com/blog/2019/04/24/open-sourcing-delta-lake.html)
- [Lakehouse: A New Generation of Open Platforms (CIDR 2021)](https://www.cidrdb.org/cidr2021/papers/cidr2021_paper17.pdf)
- [Zhamak Dehghani - Data Mesh Principles (2020)](https://martinfowler.com/articles/data-mesh-principles.html)
- [Jay Kreps - Questioning the Lambda Architecture (2014)](https://www.oreilly.com/radar/questioning-the-lambda-architecture/)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
