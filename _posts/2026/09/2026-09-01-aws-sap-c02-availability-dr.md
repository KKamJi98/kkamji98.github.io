---
title: "SAP-C02 박살내기 10 - 가용성과 재해복구"
author: kkamji
categories: [Certification, AWS SAP-C02]
tags: [aws, sap-c02, certification, disaster-recovery, rto, rpo, multi-region, aurora-global, aws-backup, resilience]
comments: true
image:
  path: /assets/img/aws/aws.webp
date: 2026-09-01 10:00:00 +0900
---

DR 리전을 warm standby로 구성해 두고 첫 전환 훈련을 돌렸습니다. 데이터는 Aurora Global Database가 초 단위로 따라오고 있었고, DR 리전에는 프로덕션의 4분의 1 규모가 상시 떠 있었으며, Route 53 failover record와 health check도 걸려 있었습니다. 서류상 RTO 15분은 충분해 보였습니다.

훈련에서 실제로 걸린 시간은 1시간 40분이었습니다. 세 군데서 막혔습니다. 첫째, DR 리전의 EC2 vCPU quota가 상시 규모 기준으로만 올라가 있어서 Auto Scaling이 프로덕션 용량까지 확장하다가 중간에 멈췄습니다. 둘째, secondary Aurora 클러스터의 마이너 엔진 버전이 primary와 달라 managed failover가 거부됐습니다. 셋째, 운영자가 primary 쪽 Route 53 health check를 콘솔에서 disable했는데 트래픽이 계속 primary로 갔습니다.

세 가지 모두 DR 전략을 잘못 고른 문제가 아닙니다. 전략은 맞았고, 그 전략이 실제로 동작하기 위해 필요한 제약을 사전에 채우지 않은 문제입니다. quota는 리전마다 따로 관리되고, Aurora managed failover는 엔진 버전 일치를 요구하며, Route 53 health check를 disable하면 Route 53은 그 엔드포인트를 항상 healthy로 간주합니다.

SAP-C02는 이 층에서 답을 가릅니다. `RTO 15분, RPO 5분` 같은 숫자가 지문에 나오고, 선지 네 개가 전부 그럴듯한 DR 구성이며, 어느 하나만 그 숫자를 실제로 만족시킵니다. 서비스 이름을 아는 것으로는 좁혀지지 않고, 각 복제 수단이 만드는 RPO의 실제 상한과 각 전환 수단이 리전 장애 중에도 동작하는지를 알아야 합니다.

> **TL;DR**  
> - RPO는 재해 이전 구간이고 RTO는 재해 이후 구간이다. 목표값이지만 실제 상한은 복제 수단과 복구 절차가 정한다.  
> - DR 전략 4종이 갈리는 지점은 비용이 아니라 추가 조치 없이 요청을 처리할 수 있는가다. pilot light는 못 하고 warm standby는 한다.  
> - failover 절차는 data plane operation만으로 짜야 한다. weight 변경과 Global Accelerator traffic dial 조정은 control plane이다.  
> - DR 리전의 service quota를 프로덕션 용량까지 미리 올리지 않으면 확장 자체가 막힌다. Auto Scaling 의존은 control plane 의존이다.  
> - Aurora Global Database의 switchover는 RPO 0이고 healthy 상태 전용이다. managed failover는 리전 장애용이고 RPO가 초 단위 non-zero이며 write fencing이 best effort다.  
> - Multi-AZ DB instance는 failover 60초에서 120초이고 standby가 읽기를 못 받는다. Multi-AZ DB cluster는 35초 미만이고 reader 2개가 읽기를 처리한다.  
> - S3 live replication은 설정 이후 객체만 복제한다. 기존 객체는 Batch Replication이고 RTC는 Batch Replication에 적용되지 않는다.  
> - AWS Backup continuous backup은 최대 35일이고 cold storage로 내려갈 수 없다. 장기 보존은 snapshot backup rule을 따로 둔다.  
> - Route 53 health check를 disable하면 항상 healthy로 간주된다. 트래픽을 끊으려면 invert한다.  
> - zonal shift는 최대 72시간 만료를 갖는 임시 완화책이고, zonal autoshift는 AWS 텔레메트리가 시작하며 주 1회 practice run이 필수다.  
> - 설계가 동작하는지는 FIS 실험과 AWS Backup restore testing으로 확인한다. 문서가 아니라 실행 결과가 격차를 만든다.  
{: .prompt-info}

---

## 1. RPO는 재해 이전 구간이고 RTO는 재해 이후 구간이다

두 값은 시간축의 서로 다른 쪽을 가리킵니다. RPO는 재해 시점을 기준으로 과거 방향의 구간이고 데이터 손실을 얼마나 감수할지를 말합니다. RTO는 재해 시점에서 미래 방향의 구간이고 서비스가 중단된 채로 얼마나 있을 수 있는지를 말합니다.

{% include diagrams/static/sap-c02/rto-rpo-timeline.html %}

그림은 RPO와 RTO가 각각 시간축의 어느 구간을 차지하는지, 그리고 두 구간의 실제 상한을 무엇이 정하는지를 보여줍니다.

시험에서 이 정의 자체를 묻는 문항은 드뭅니다. 대신 지문이 `RPO 5분`을 요구하고 선지에는 복제 수단이 나열됩니다. 그러면 목표값을 각 복제 수단이 실제로 만들어내는 값과 대조해야 합니다.

| 복제 수단 | 문서가 진술하는 RPO 특성 |
| :--- | :--- |
| Aurora Global Database | secondary 리전 복제 지연이 통상 1초 미만. managed failover의 RPO는 그 시점의 복제 지연에 비례 |
| Aurora switchover | RPO 0. 완전 동기화 후 승격 |
| RDS cross-Region read replica | 비동기 복제. promotion에 몇 분과 reboot이 필요 |
| DynamoDB global tables | MREC는 비동기 복제와 last-writer-wins를 사용하고, MRSC는 동기 복제와 `ReplicatedWriteConflictException`을 사용한다 |
| S3 Replication Time Control | 15분 임계값을 SLA로 보장 |
| S3 기본 replication | SLA 없는 best effort |
| EFS replication | 대부분 파일시스템에서 15분 유지 |
| AWS Backup continuous backup | 1초 정밀도, 복원 가능한 최신 시점은 RDS 최근 5분, Aurora 통상 5분 미만, S3 최근 15분 |
| AWS Backup snapshot backup | 최소 1시간 주기 |

RTO 쪽도 마찬가지입니다. 목표 숫자만 보고 전략을 고르면 안 되고, 그 전략에서 재해 이후에 실제로 수행해야 하는 단계의 합을 봐야 합니다. 탐지와 판단에 걸리는 시간, DNS 전파 시간, 인스턴스 기동 시간, 프로덕션 용량까지의 확장 시간이 전부 RTO 안에 들어갑니다. 도입부 훈련에서 1시간 40분이 나온 이유가 여기 있습니다.

한 가지 예외를 기억해야 합니다. multi-site active/active는 대부분의 재해에 대해 복구 시간을 near zero로 줄이지만, 데이터 손상이나 삭제나 난독화로 인한 재해는 예외입니다. 이 유형의 재해에서 복구 시간은 항상 0보다 크고 recovery point는 항상 재해를 발견하기 이전 시점이 됩니다. 손상된 데이터가 모든 리전으로 즉시 복제되기 때문입니다. 그래서 active/active 구성에서도 백업은 별도로 필요합니다.

---

## 2. DR 전략 4종은 추가 조치 없이 요청을 처리할 수 있는가에서 갈린다

AWS는 DR 전략을 backup and restore, pilot light, warm standby, multi-site active/active 네 가지로 분류합니다. 앞의 세 가지는 active/passive이고 passive site는 failover 이벤트 전까지 트래픽을 처리하지 않습니다. multi-site active/active만 두 사이트가 모두 트래픽을 받습니다.

{% include diagrams/static/sap-c02/dr-strategy-four-tiers.html %}

그림은 네 전략을 왼쪽에서 오른쪽으로 놓고, 각 전략이 DR 리전에 무엇을 유지하는지와 그 상태가 어느 그룹에 속하는지를 보여줍니다.

**pilot light와 warm standby의 결정적 차이는 추가 조치 없이 요청을 처리할 수 있는가입니다.** pilot light는 서버를 켜고 비핵심 인프라를 배포하고 확장하는 단계를 거쳐야 요청을 받습니다. warm standby는 축소된 용량으로 이미 트래픽을 받고 있고 확장만 남습니다. 문항이 `RTO 15분` 같은 짧은 목표를 제시하면 이 차이가 답을 가릅니다.

| 전략 | DR 리전 상태 | 전환 시 남은 작업 |
| :--- | :--- | :--- |
| backup and restore | 백업 사본만 있다 | 복원, 배포, 확장을 전부 재해 이후에 한다 |
| pilot light | 데이터가 복제되고 코어 인프라가 꺼진 채 있다 | 서버 기동, 비핵심 인프라 배포, 확장 |
| warm standby | 축소 규모가 상시 가동된다 | 프로덕션 용량까지 확장 |
| multi-site active/active | 프로덕션 전량이 상시 가동된다 | 없다. failover라는 개념 자체가 없다 |

전략 선택이 항상 위로 올라가야 하는 것은 아닙니다. 단일 데이터센터 소실 수준의 재해라면 well-architected 고가용성 워크로드는 backup and restore로도 충분할 수 있습니다. 리전 단위 재해를 상정하거나 규제가 특정 복구 목표를 요구할 때 pilot light 이상을 고려합니다.

**hot standby는 별도의 다섯 번째 전략이 아닙니다.** multi-site active/active와 같은 규모를 배포하되 active/passive로 운영하는 형태입니다. 프로덕션 부하 전량을 미리 프로비저닝해 두었기 때문에 statically stable하고, 전환 시점에 확장할 필요가 없습니다.

여기서 자주 틀리는 지점이 하나 있습니다. **DR 리전 확장을 Auto Scaling에 의존하면 그 자체가 control plane 의존입니다.** 리전 장애 상황에서 control plane API가 정상 동작한다는 보장이 없고, 전체 복구 전략의 복원력이 그만큼 내려갑니다. statically stable하다는 것은 재해 시점에 새로 만들어야 하는 리소스가 없다는 뜻이고, 그 구성이 hot standby입니다. `Auto Scaling으로 확장하니 statically stable하다`는 서술은 성립하지 않습니다.

---

## 3. failover 절차는 data plane operation만으로 짠다

AWS DR 백서가 반복해서 강조하는 원칙입니다. **failover 절차에 data plane operation만 쓰는 것이 최대 복원력입니다.** 근거는 단순합니다. data plane이 control plane보다 높은 가용성 설계 목표를 가지기 때문입니다. 리전이 손상된 상황에서 control plane API를 호출해야 전환이 되는 구조라면, 그 API가 응답하지 않을 때 전환도 되지 않습니다.

시험에서 이 원칙은 선지 네 개 중 셋을 걸러내는 도구로 쓰입니다.

| 전환 수단 | plane | 결과 |
| :--- | :--- | :--- |
| Route 53 health check 기반 자동 DNS failover | data plane | 신뢰할 수 있다 |
| ARC routing control 상태 전환 | data plane | 신뢰할 수 있다. 사람이 판단하되 조작 경로는 data plane이다 |
| weighted routing policy의 weight 변경 | control plane | 리전 장애 중 신뢰할 수 없다 |
| Global Accelerator traffic dial 조정 | control plane | 리전 장애 중 신뢰할 수 없다 |
| 백업에서의 복원 | control plane | 재해 시 불가능할 수 있어 주기적 사전 복원을 권고한다 |

`운영자가 판단해서 전환하고 싶다`는 요구와 `리전 장애 중에도 동작해야 한다`는 요구가 함께 나오면 답은 ARC routing control입니다. ARC routing control은 실제 health를 검사하지 않고 on/off 스위치로만 동작하는 Route 53 health check를 만듭니다. 이 health check의 타입이 `RECOVERY_CONTROL`이고, routing control 상태가 ON이면 healthy, OFF면 unhealthy로 취급됩니다. 상태 변경은 data plane API로 수행하므로 사람의 판단과 data plane 조작을 동시에 만족시킵니다.

Global Accelerator는 DNS 캐시 문제를 피하고 edge에서 AWS 백본에 조기 진입해 지연이 낮다는 장점이 있습니다. 그러나 traffic dial을 조정하는 조작 자체는 control plane입니다. `클라이언트가 DNS 응답을 캐시해서 전환이 늦다`가 문제로 서술되면 Global Accelerator가 답이지만, `리전 장애 중 control plane 의존을 없애라`가 요구면 아닙니다. 두 요구를 구분해서 읽어야 합니다.

CloudFront origin failover도 자주 오답 선지로 나옵니다. **origin failover는 요청 단위입니다.** 실패한 요청만 secondary origin으로 가고 이후 요청은 다시 primary로 갑니다. 리전 전체를 secondary로 넘기는 수단이 아닙니다.

---

## 4. DR 리전의 service quota를 미리 올리지 않으면 확장이 막힌다

warm standby와 pilot light는 전환 후 프로덕션 용량까지 확장하는 것을 전제로 합니다. 이 확장이 성립하려면 DR 리전의 service quota가 프로덕션 용량 이상이어야 합니다. **DR 리전에서 상시 가동하는 규모만큼만 quota가 올라가 있으면 scale up 자체가 막힙니다.**

Service Quotas 도구를 다룰 때 기억할 성질이 몇 가지 있습니다.

- quota는 계정 단위이거나 리전 단위다. 한 리전에서 올린 값이 다른 리전에 적용되지 않는다.
- global quota의 증설 요청은 파티션마다 지정된 리전에서만 가능하다. 상용 파티션은 us-east-1, GovCloud는 us-gov-west-1, 중국은 cn-north-1이다.
- 콘솔이 조정 가능 여부(Adjustable)와 조정 가능한 레벨(account 또는 resource)을 표시한다.
- 계정이 일정 기간 활성이면 utilization 그래프를 제공한다. utilization은 quota 대비 사용량 비율이다.

시험에서 이 항목은 `quota 증설을 재해 발생 후에 요청한다`는 선지로 나옵니다. 증설 요청은 즉시 승인되지 않으므로 그 선지는 RTO를 지키지 못합니다. DR 설계에서 quota 증설은 사전 준비 항목입니다.

---

## 5. Elastic Disaster Recovery는 pilot light를 서비스로 구현한 것이다

AWS Elastic Disaster Recovery(DRS)는 pilot light 전략을 사용합니다. staging area subnet에 데이터 사본과 꺼진 리소스를 유지하다가, failover 시 target VPC에 full-capacity 배포를 만듭니다. 블록 레벨 복제로 소스 서버를 계속 복제하고, 최신 상태 또는 과거 특정 시점으로 복구 인스턴스를 launch합니다. 비중단 drill을 지원하므로 프로덕션 복제를 멈추지 않고 훈련할 수 있습니다.

**DRS의 대상은 EC2에 호스팅된 애플리케이션과 데이터베이스입니다. RDS는 대상이 아닙니다.** 이 경계가 오답 선지의 재료가 됩니다. `DRS로 RDS 인스턴스를 다른 리전에 복제한다`는 선지는 성립하지 않고, RDS의 리전 간 복제는 cross-Region read replica나 cross-Region snapshot copy나 Aurora Global Database입니다.

DRS의 RTO는 문서가 `launch recovery instances on AWS within minutes`라고 진술하는 수준까지만 확인됩니다. 그보다 구체적인 RPO 수치는 서비스 문서 본문에 없으므로 시험 대비 지식으로 외울 값이 아닙니다.

---

## 6. Aurora Global Database의 switchover와 managed failover는 다른 절차다

Aurora Global Database는 primary 1개 리전과 read-only secondary 최대 10개 리전으로 구성됩니다. secondary 리전 복제 지연은 통상 1초 미만이고, 리전 내부는 100밀리초보다 훨씬 작습니다. secondary cluster는 read-only이므로 단일 Aurora 클러스터의 통상 한도 15개가 아니라 read-only DB instance를 16개까지 붙일 수 있습니다.

전환 절차는 두 가지이고 용도가 다릅니다.

{% include diagrams/static/sap-c02/aurora-global-switchover-failover.html %}

그림은 두 전환 절차가 어떤 사전 조건을 공유하고 각각 어떤 결과에 도달하는지를 보여줍니다.

**switchover는 계획된 절차 전용입니다.** 예전 명칭은 managed planned failover였습니다. secondary를 primary와 완전히 동기화한 뒤 승격하므로 RPO가 0입니다. 대신 모든 클러스터가 healthy할 때만 동작하도록 설계됐습니다. primary 리전에 접근할 수 없는 장애 상황에서는 쓸 수 없습니다.

**managed failover는 계획되지 않은 장애용입니다.** 데이터 동기화를 기다리지 않고 승격하므로 RPO가 통상 0이 아닌 초 단위이고, 손실량이 장애 시점의 복제 지연에 비례합니다. Aurora가 write fencing을 best-effort로 시도하지만 성공이 보장되지 않아 split brain 가능성이 남습니다. 문서는 Aurora Global Database의 RTO를 minutes, RPO를 seconds로 명시합니다.

managed failover 이후에 벌어지는 일도 알아야 합니다. Aurora가 옛 primary의 스토리지 볼륨 스냅샷을 시도하고 이름은 `rds:unplanned-global-failover-`로 시작합니다. 그리고 나머지 secondary 클러스터를 rebuild하는데, 이 작업은 몇 분에서 수 시간이 걸립니다. 전환 직후 곧바로 원래의 다중 리전 복원력이 회복되는 것이 아닙니다.

두 절차가 공유하는 사전 조건이 두 개 있습니다.

- **primary와 secondary의 major와 minor 엔진 버전이 같아야 한다.** 다르면 managed switchover도 managed failover도 쓸 수 없고, detach-and-promote 방식의 manual failover만 남습니다. 이 경로는 RTO가 크게 늘어납니다.
- **headless secondary 클러스터로는 전환할 수 없다.** 먼저 DB instance를 추가해야 합니다. 비용을 아끼려고 secondary를 headless로 둔 구성이 여기서 걸립니다.

복제 지연은 `AuroraGlobalDBRPOLag` 메트릭으로 감시합니다. 단위는 밀리초입니다. 낮은 마이너 버전의 Aurora MySQL에서는 `AuroraGlobalDBReplicationLag`을 봅니다.

Aurora PostgreSQL에는 `rds.global_db_rpo` 파라미터가 있습니다. 설정 범위는 20초에서 2,147,483,647초이고, 모든 secondary의 RPO lag이 이 목표를 넘으면 primary의 커밋이 블록됩니다. RPO를 강제하는 대신 쓰기 가용성을 희생하는 장치입니다. 2개 리전 구성에서는 secondary 파라미터 그룹의 기본값을 유지하도록 문서가 권고합니다. 0을 지정할 수 없다는 점도 함께 기억해야 합니다.

애플리케이션 쪽에서는 global writer endpoint를 쓰면 failover 후에도 연결 설정을 바꾸지 않아도 됩니다. 이때 DNS 캐시 TTL을 5초 수준으로 낮추도록 권고합니다.

마지막으로 Aurora Global Database가 지원하지 않는 것 세 가지가 오답 선지의 단골입니다. **Backtrack, secondary 클러스터의 Aurora Auto Scaling, Secrets Manager 통합을 지원하지 않습니다.**

---

## 7. RDS의 Multi-AZ 두 종류는 failover 시간과 읽기 처리에서 갈린다

RDS에는 이름이 비슷한 두 가지 Multi-AZ 구성이 있고 시험은 이 둘을 자주 붙여 놓습니다.

| 항목 | Multi-AZ DB instance | Multi-AZ DB cluster |
| :--- | :--- | :--- |
| 구성 | primary 1개 + 다른 AZ의 동기 standby 1개 | writer 1개 + reader 2개를 3개 AZ에 배치 |
| 복제 | 동기 | semisynchronous. 커밋에 최소 1개 reader의 ack가 필요 |
| standby와 reader의 읽기 | standby는 읽기 트래픽을 서비스할 수 없다 | reader가 읽기 트래픽을 처리한다 |
| failover 시간 | typically 60초에서 120초 | typically under 35 seconds |
| 인스턴스 클래스 | 제한 없음 | 로컬 NVMe를 가진 클래스로 제한 |

Multi-AZ DB instance의 failover 시간은 큰 트랜잭션이나 긴 복구 과정이 있으면 늘어납니다. `typically`가 붙어 있다는 점을 그대로 기억해야 합니다.

Multi-AZ DB cluster의 인스턴스 클래스 제한은 구체적으로 db.c6gd, db.m5d, db.m6gd, db.m6id, db.m6idn, db.m8gd, db.r5d, db.r6gd, db.r6id, db.r6idn, db.r8gd, db.x2iedn입니다. medium 크기는 c6gd만 지원합니다. 목록을 통째로 외울 필요는 없지만 `로컬 NVMe가 있는 클래스로 제한된다`는 성질은 선지를 가릅니다.

semisynchronous 구성에는 flow control이 붙습니다. MySQL은 `rpl_semi_sync_master_target_apply_lag` 파라미터의 기본값이 120초이고, 끄려면 최대값 86,400초로 설정합니다. PostgreSQL은 lag이 2분을 넘으면 writer가 지연을 주입합니다. reader가 따라오지 못하면 writer가 느려지는 구조입니다.

`읽기 부하를 분산하면서 동시에 failover를 35초 미만으로 줄여라`는 요구가 나오면 Multi-AZ DB cluster가 유일한 답입니다. read replica를 추가하는 선지는 읽기 부하만 해결하고 failover 시간을 바꾸지 못합니다.

read replica의 성질도 정리해 둡니다.

- 비동기 복제다. cross-Region read replica를 지원한다.
- promote는 몇 분이 걸리고 reboot을 포함한다.
- RDS는 read replica의 autoscaling을 지원하지 않고 순환 복제도 지원하지 않는다.
- source DB instance를 삭제하면 같은 리전의 read replica는 standalone으로 승격된다.
- RDS for Db2의 standby mode replica와 RDS for Oracle의 mounted mode replica는 사용자 연결을 받지 않는다. 주 용도가 cross-Region disaster recovery다.

---

## 8. Aurora Backtrack은 되감기이고 PITR 복원은 새 클러스터 생성이다

Aurora의 백업 성질부터 확정합니다. 자동 백업 보존 기간은 1일에서 35일이고 기본값은 1일입니다. **자동 백업을 끌 수 없고 백업이 성능에 영향을 주지 않습니다.** latest restorable time은 활성 클러스터 기준으로 통상 현재 시각의 5분 이내입니다.

Backtrack은 그와 다른 기능입니다.

| 항목 | Aurora Backtrack | PITR 복원 |
| :--- | :--- | :--- |
| 결과물 | 같은 클러스터를 되감는다 | 새 클러스터를 만든다 |
| 최대 범위 | 72시간 | 보존 기간 최대 35일 |
| 엔진 | Aurora MySQL 전용 | Aurora MySQL과 PostgreSQL |
| 활성화 시점 | 클러스터 생성 시 또는 스냅샷 복원 시에만 | 별도 활성화가 필요 없다 |
| 소요 | 분 단위 | 클러스터 생성 시간 |

**Backtrack은 기존 클러스터를 modify해서 켤 수 없습니다.** 이미 운영 중인 클러스터에 Backtrack을 켜라는 선지는 항상 오답입니다. 그리고 Backtrack이 켜진 클러스터에서는 cross-Region read replica를 만들 수 없습니다. Backtrack은 클러스터 전체에 작용하므로 테이블 단위 선택도 불가능합니다.

`새 클러스터를 만들지 않고 분 단위로 되감아라`가 요구면 Backtrack이지만, 지문이 이미 운영 중인 클러스터를 전제하면 그 선지는 성립하지 않습니다. 두 조건을 함께 읽어야 합니다.

---

## 9. DynamoDB global tables는 consistency mode에 따라 동작이 갈린다

Aurora Global Database와 DynamoDB global tables의 근본적인 차이가 여기 있습니다. Aurora는 primary 1개만 쓰기를 받고 secondary는 read-only입니다. DynamoDB global tables의 모든 replica는 읽기와 쓰기를 처리할 수 있지만, consistency mode에 따라 복제와 충돌 처리가 달라집니다. MREC에서는 비동기 복제와 last-writer-wins로 동시 갱신을 조정합니다. MRSC에서는 item 변경을 다른 리전에 동기 복제한 뒤 쓰기를 성공시키며, 이미 다른 리전에서 갱신 중인 item을 수정하면 `ReplicatedWriteConflictException`이 발생합니다.

consistency mode는 두 가지입니다.

| mode | 성질 | 제약 |
| :--- | :--- | :--- |
| multi-Region eventual consistency (MREC) | 기본값. 비동기 복제와 충돌 시 last-writer-wins | 강한 일관성을 리전 간에 보장하지 않으며 RPO는 replica 간 복제 지연에 해당한다 |
| multi-Region strong consistency (MRSC) | 리전 간 강한 일관성. item 변경을 다른 리전에 동기 복제하고 충돌 시 `ReplicatedWriteConflictException`을 반환한다 | same-account 구성만 지원하고 정확히 3개 리전이 필요하다. 세 replica 또는 두 replica와 하나의 witness 조합이며, 지원되는 Region set을 넘을 수 없다 |

**생성 후 변경할 수 없고 한 global table 안에서 두 mode를 혼용할 수 없습니다.** 운영 중인 global table을 MREC에서 MRSC로 바꾸겠다는 선지는 성립하지 않습니다.

계정 모델도 버전 지원이 갈립니다. same-account 모델은 global tables version 2019.11.21과 legacy 2017.11.29를 모두 지원하고, multi-account 모델은 2019.11.21만 지원합니다.

DynamoDB의 PITR도 정리해 둡니다.

- 복구 기간(`RecoveryPeriodInDays`)은 1일에서 35일 사이로 설정한다.
- `LatestRestorableDateTime`은 통상 현재 시각 5분 전이다.
- **PITR 복원은 항상 새 테이블을 만든다.** 기존 테이블을 제자리에서 되돌리지 않는다.
- 복구 기간을 줄이면 `EarliestRestorePoint`가 즉시 줄어들고 그 밖의 연속 백업은 복구할 수 없게 된다. 늘리면 즉시 반영되지 않고 롤링 윈도가 채워질 때까지 기다린다.
- PITR이 켜진 테이블을 삭제하면 `{table-name}$DeletedTableBackup` system backup이 35일간 무료로 보존된다.
- 과금은 테이블 크기 기준이고 설정한 복구 기간 길이는 가격에 영향을 주지 않는다.

마지막 항목은 설계 판단에 직접 쓰입니다. 복구 기간을 7일로 줄여도 비용이 줄지 않으므로, 비용을 이유로 기간을 줄이는 선지는 근거가 없습니다.

---

## 10. S3 복제는 설정 이후 객체만 다루고 RTC가 예측 가능성을 만든다

가장 자주 나오는 함정부터 확정합니다. **live replication은 설정 이후 새로 쓰이거나 갱신된 객체만 복제합니다.** 설정 전에 존재하던 객체는 S3 Batch Replication으로 따로 처리해야 합니다. 이미 데이터가 쌓인 버킷을 DR 리전에 맞추라는 문항이 나오면 두 가지를 함께 써야 답이 됩니다.

live replication에는 리전 간 복제(CRR)와 같은 리전 복제(SRR) 두 형태가 있습니다. SRR은 리전을 넘지 않으므로 리전 장애 대비가 아니라 계정 분리나 로그 집계나 데이터 주권 요건에 씁니다.

S3 Replication Time Control(RTC)은 예측 가능성을 SLA로 만드는 기능입니다.

- 대부분 객체를 수초 안에 복제하고 **15분 임계값을 SLA로 보장한다.**
- `Metrics:EventThreshold:Minutes`와 `ReplicationTime:Time:Minutes`는 15만 유효한 값이다. 다른 값을 넣을 수 없다.
- `OperationMissedThreshold`와 `OperationReplicatedAfterThreshold` 이벤트를 발생시킨다. 이벤트와 메트릭은 RTC를 켠 뒤 15분 안에 사용 가능해진다.
- **RTC는 Batch Replication에 적용되지 않는다.**
- SLA는 복제 데이터 전송률이 기본 1 Gbps 쿼터를 넘는 구간과 S3 request rate 가이드라인을 넘는 구간에는 적용되지 않는다.

`predictable`, `SLA`, `compliance` 같은 단어가 지문에 나오면 RTC입니다. 다만 그 SLA를 기존 객체 복제에 적용하겠다는 선지는 성립하지 않습니다.

복제의 요청량과 과금 구조도 알아 두면 비용 관련 선지를 거를 수 있습니다. 객체 1개를 복제할 때 source 버킷에 최대 5회 GET/HEAD와 1회 PUT이, 각 destination 버킷에 1회 PUT이 발생합니다. 과금은 객체당 PUT 1회입니다. SSE-KMS로 암호화된 객체를 복제하면 KMS request rate 쿼터를 소비합니다. 초당 1,000객체 복제를 예상한다면 KMS 쿼터에서 2,000 요청을 빼고 계산해야 합니다.

DR 관점에서 중요한 동작이 하나 더 있습니다. **source 버킷의 객체를 삭제하면 기본적으로 source 버킷에만 delete marker가 추가됩니다.** 이 동작이 DR 리전을 source 리전의 악의적 삭제나 실수로부터 보호합니다.

양방향 복제도 지원합니다. 두 리전 사이 양방향 복제를 구성할 수 있고, ACL과 태그와 object lock 같은 replica metadata 변경까지 복제하려면 replica modification sync를 양쪽 버킷에 켜야 합니다.

**S3 Multi-Region Access Point failover control을 쓰기 전에는 two-way replication rule을 먼저 구성해야 합니다.** 그래야 failover 대상 버킷에 쓰인 데이터가 원래 버킷으로 되돌아옵니다. failover control만 켜면 동기화가 자동으로 되는 것이 아닙니다.

---

## 11. EFS 복제본은 시점 정합성이 없고 ECR 복제는 연쇄되지 않는다

EFS replication은 초기 sync 이후 대부분 파일시스템에서 RPO 15분을 유지합니다. 파일이 1억 개를 넘거나, 100 GB를 넘는 파일이 있고 변경이 잦으면 15분을 넘길 수 있습니다.

**destination 파일시스템은 point-in-time consistent가 아닙니다.** Last synced time 기준으로 전달되므로 특정 시점의 일관된 스냅샷으로 취급할 수 없습니다. 상태는 CloudWatch `TimeSinceLastSync` 메트릭으로 감시합니다. cross-account replication에는 service-linked role을 쓸 수 없고 IAM role을 지정해야 합니다.

컨테이너 이미지 쪽에는 ECR private registry replication이 있습니다. cross-Region과 cross-account를 모두 지원하지만 제약이 뚜렷합니다.

- **복제 설정 이후 push되거나 restore된 콘텐츠만 복제한다.** 설정 전 기존 이미지는 복제되지 않는다. S3 live replication과 같은 성질이다.
- **연쇄되지 않는다.** us-west-2에서 us-east-1로, us-east-1에서 us-east-2로 규칙을 걸어도 us-west-2에 push한 이미지는 us-east-1까지만 간다.
- 파티션을 넘는 복제는 지원하지 않는다.
- 쿼터는 registry당 rule 최대 25개, 전체 rule에 걸친 고유 destination 25개, rule당 filter 100개다. 대부분 이미지가 30분 안에 복제된다.
- cross-account replication은 destination 계정에만 registry permission policy가 필요하고 `ecr:ReplicateImage`와 `ecr:CreateRepository`를 허용해야 한다. source repository에는 정책이 필요 없다.
- 삭제와 아카이브 동작을 복제하지 않고 repository policy와 lifecycle policy도 복제하지 않는다. repository 설정을 함께 옮기려면 repository creation template을 쓴다.

DR 리전에서 컨테이너 워크로드를 띄우려면 이미지가 그 리전에 있어야 합니다. `복제 규칙만 켜면 기존 이미지도 채워진다`고 가정한 설계는 전환 시점에 이미지 pull 실패로 나타납니다.

---

## 12. AWS Backup의 두 rule은 보존 기간에서 갈라져 다시 만나지 않는다

AWS Backup의 backup plan에는 continuous backup rule과 snapshot backup rule을 둘 수 있고, 둘의 역할이 다릅니다.

{% include diagrams/static/sap-c02/aws-backup-continuous-vs-snapshot.html %}

그림은 두 rule이 각각 어떤 보존 경로로 이어지고 어디서 막히는지를 보여줍니다.

| 항목 | continuous backup | snapshot backup |
| :--- | :--- | :--- |
| 정밀도 | 1초 | 최소 1시간 주기 |
| 최대 보존 | 35일 | 100년 |
| cold storage 전환 | 불가능 | 지원 리소스에서만 가능 |
| 리소스당 개수 | 1개 | 제한 없음 |
| 구조 | 전체 백업 1회 후 트랜잭션 로그를 계속 백업 | 시점 스냅샷 |

**continuous backup이 cold storage로 갈 수 없는 이유는 계산으로 나옵니다.** cold 전환은 최소 90일 보관을 요구하는데 continuous backup의 최대 보존은 35일이므로 구조적으로 성립하지 않습니다.

cold storage 지원 여부는 리소스 유형별로 갈립니다. feature availability 표에서 지원 표시가 있는 것은 EBS, EFS, FSx for OpenZFS, DynamoDB with advanced features, Timestream, SAP HANA on EC2, virtual machines, CloudFormation, Aurora DSQL입니다. **Amazon RDS, Amazon Aurora, Amazon EC2, Amazon S3는 지원 표시가 없습니다.** `RDS 월말 스냅샷을 cold storage로 내려 장기 보존 비용을 줄인다`는 설계는 그래서 성립하지 않습니다.

리소스 1개는 continuous backup을 1개만 가집니다. 중복 규칙은 snapshot backup으로 대체되며 `Completed with issues` 상태와 `PITR already configured in backup plan` 오류가 붙습니다.

복원 가능한 최신 시점은 리소스마다 다릅니다. RDS가 최근 5분, Aurora가 `LatestRestorableTime`(통상 5분 미만), S3가 최근 15분입니다.

리소스별 지원 경계도 시험 대상입니다.

- Amazon RDS DB instance(single-AZ와 Multi-AZ instance)는 continuous backup과 PITR을 지원한다.
- **RDS Multi-AZ DB cluster는 continuous backup과 PITR을 지원하지 않는다.**
- S3 continuous backup은 EventBridge 이벤트에 의존한다. 버킷 알림 설정에서 이를 끄면 continuous backup이 멈춘다. cross-Region이나 cross-account 사본은 PITR을 갖지 않고 생성 시점 snapshot으로 복원된다.
- **RDS continuous backup의 사본은 만들 수 없다.** 트랜잭션 로그 복사를 허용하지 않기 때문에 대신 snapshot을 만들어 복사한다.
- Aurora continuous backup의 RPO는 통상 5분 미만이고, Vault Lock 보호 vault는 지원하지만 logically air-gapped vault는 지원하지 않는다.

---

## 13. cross-Region copy와 Vault Lock과 조직 backup policy

DR 관점에서 백업은 다른 리전이나 다른 계정에 사본이 있어야 의미가 있습니다. AWS Backup의 copy 동작에는 비용과 성공 여부를 가르는 성질이 있습니다.

- **첫 복사가 full이고, 이후 같은 vault와 같은 키로 복사하면 incremental이다.**
- **EBS는 다른 KMS 키를 쓰는 vault로 복사하면 항상 full copy가 된다.** 비용 최적화 문항에서 이 조건이 답을 가릅니다.
- **cold tier에 있는 백업은 cross-Region copy를 지원하지 않는다.** cold storage 전환분은 최소 90일 보관해야 하고 retention은 cold 전환값보다 90일 이상 커야 한다.
- RDS cross-Region copy는 custom option group을 전달하지 않고 default option group을 복사한다. persistent option을 쓰면 대상 리전에 같은 option group을 미리 만들어야 copy job이 성공한다.

Vault Lock은 백업이 지워지지 않도록 잠그는 장치입니다. vault당 1개만 걸 수 있습니다.

| mode | 해제 가능성 | grace time |
| :--- | :--- | :--- |
| governance mode | 충분한 IAM 권한이 있으면 해제할 수 있다 | 없다 |
| compliance mode | grace time 종료 후 사용자도 AWS도 변경하거나 삭제할 수 없다 | `ChangeableForDays`로 지정. 최소 3일(72시간), 최대 36,500일 |

**`ChangeableForDays` 파라미터를 넣으면 compliance mode, 빼면 governance mode로 생성됩니다.** `root user조차 지울 수 없어야 한다`는 요구가 나오면 compliance mode이고, `설정 실수를 되돌릴 시간을 남겨라`가 함께 나오면 grace time을 최소값보다 넉넉하게 잡습니다. 최소값이 3일이라는 점을 모르면 1일을 지정하는 선지에 걸립니다.

`MinRetentionDays`의 최소값은 1일이고 `MaxRetentionDays`의 최대값은 36,500일(약 100년)입니다. 두 값은 vault lock 이전에 이미 들어 있던 recovery point에는 적용되지 않습니다.

여기에 Vault Lock으로도 막지 못하는 경계가 하나 있습니다. **계정을 닫으면 AWS가 90일간 백업을 유지한 뒤 삭제합니다. Vault Lock이 걸려 있어도 삭제됩니다.** 계정 폐쇄는 백업 보존 정책의 상위에 있습니다.

조직 단위로 백업을 강제할 때는 Organizations backup policy를 씁니다. root, OU, 개별 계정에 붙고 상속 규칙으로 계정별 effective backup policy가 만들어집니다. 상위에서 기본 주기를 주고 하위 OU에서 override하는 구조가 가능합니다.

두 가지 함정이 있습니다. **effective policy가 필수 요소를 전부 갖추지 못하면 AWS Backup이 유효하지 않은 정책으로 보고 백업하지 않습니다.** 부분 정책만 상위에 붙이고 하위에서 채우는 전략은 어느 계정에서 요소가 빠지는 순간 그 계정의 백업이 통째로 멈춥니다. 그리고 정책으로 만들어진 backup plan은 member 계정 콘솔에서 immutable로 보입니다. 조회만 되고 변경할 수 없으며 태그만 추가하거나 제거할 수 있습니다.

---

## 14. restore testing은 복원 가능성을 스케줄로 증명한다

백업이 존재한다는 사실과 그 백업으로 복원할 수 있다는 사실은 다릅니다. AWS Backup restore testing은 후자를 스케줄로 증명하는 기능입니다. 복원을 수행하고, 검증 후 리소스를 삭제하며, Backup Audit Manager 컨트롤로 목표 복원 시간 충족 여부를 평가합니다.

지원 리소스는 Aurora, DocumentDB, DynamoDB, EBS, EC2, EFS, FSx(Lustre, ONTAP, OpenZFS, Windows), Neptune, RDS, S3입니다.

운용 제약이 시험 대상입니다.

| 항목 | 값 |
| :--- | :--- |
| restore testing plan | 계정당 100개 |
| plan당 tag | 50개 |
| plan당 selection | 30개 |
| selection당 ARN | 30개 |
| selection당 조건 | 30개 |
| selection당 vault selector | 30개 |
| selection window | 최대 365일 |
| start window | 1시간에서 168시간(7일) |
| validation 대기 시간 | 1시간에서 168시간 |

**검증은 API로만 가능하고 콘솔에서는 실행할 수 없습니다.** 그리고 각 실행에서 선택된 protected resource 1개당 최대 1개 recovery point만 복원합니다. tag 조건은 protected resource 선택에만 적용되고 recovery point 선택에는 적용되지 않습니다.

정리 동작에도 함정이 있습니다. restore testing은 테스트 후 리소스를 삭제하는데, `awsbackup-restore-test` 태그를 지우면 자동 삭제가 실패해 수동으로 지워야 합니다. DynamoDB, S3, SAP HANA on EC2, virtual machine, Timestream은 tag-on-restore를 지원하지 않아 이름 기준으로 삭제합니다.

`백업이 실제로 복원 가능한지 주기적으로 검증하라`는 요구가 나오면 restore testing입니다. Config rule로 백업 존재 여부만 확인하는 선지나 사람이 분기마다 수동 복원하는 선지는 요구를 만족시키지 못합니다.

EBS만 대상으로 삼는 경우에는 더 가벼운 선택지가 있습니다. Amazon Data Lifecycle Manager는 EBS snapshot과 EBS-backed AMI의 생성과 보존을 자동화하고 추가 비용이 없습니다. **다른 수단으로 만든 snapshot이나 AMI는 관리할 수 없고 instance store-backed AMI도 대상이 아닙니다.** 쿼터는 리전당 custom lifecycle policy 100개, EBS snapshot default policy 1개, EBS-backed AMI default policy 1개, 리소스당 tag 45개입니다.

`RDS나 EFS 백업을 DLM으로 자동화한다`는 선지는 그래서 성립하지 않습니다. 교차 서비스 일관성과 규제 보존과 restore testing이 필요하면 AWS Backup입니다.

---

## 15. 리전 전환 트리거를 어느 계층에서 만들 것인가

전환 수단은 네 가지가 자주 함께 등장하고, 그중 둘만 리전 단위 전환을 만듭니다.

{% include diagrams/static/sap-c02/regional-failover-trigger-layers.html %}

그림은 네 전환 수단을 리전 단위 전환을 만드는 것과 만들지 못하는 것으로 나누어 보여줍니다.

Route 53 health check 기반 failover는 data plane 동작이라 리전 장애 중에도 신뢰할 수 있습니다. 다만 클라이언트가 DNS 응답을 캐시하는 시간만큼 전환이 늦습니다. record TTL을 낮춰 두는 것이 사전 준비 항목입니다.

ARC routing control은 사람의 판단으로 전환하면서도 조작 경로가 data plane인 유일한 선택지입니다. 애플리케이션 헬스 엔드포인트가 부분 손상 상태에서도 200을 반환해 자동 판정이 오탐과 미탐을 반복하는 상황이면 이 방식이 답이 됩니다.

Global Accelerator는 anycast IP를 쓰므로 클라이언트 DNS 캐시 문제를 아예 만들지 않고 edge에서 AWS 백본에 조기 진입해 지연이 낮습니다. 그러나 traffic dial 조정은 control plane operation이라 `control plane 의존 제거`가 요구인 문항에서는 답이 아닙니다.

CloudFront origin failover는 요청 단위 폴백이므로 리전 전환 수단이 아닙니다. 특정 오리진이 5xx를 반환할 때 그 요청만 살리는 장치입니다.

---

## 16. Route 53 health check의 판정 규칙과 disable의 함정

전환 트리거를 Route 53에 두기로 했다면 health check가 어떻게 판정하는지를 정확히 알아야 합니다.

| 항목 | 값 |
| :--- | :--- |
| 요청 간격 | 10초 또는 30초. 기본값 30초 |
| 10초 간격 | 추가 과금. **생성 후 변경할 수 없다** |
| `FailureThreshold` | 기본값 3, 범위 1에서 10 |
| healthy 판정 기준 | 전체 health checker 중 18%를 초과하는 비율이 healthy로 보고하면 healthy |
| HTTP와 HTTPS 연결 | TCP 연결 4초 안에, 연결 후 2초 안에 2xx 또는 3xx |
| TCP health check | 10초 안에 연결 |
| health checker Region | 최소 3개, 최대 64개 |

18%라는 숫자가 낯설게 보이지만 의미는 단순합니다. 소수의 checker가 네트워크 문제로 실패해도 엔드포인트를 unhealthy로 판정하지 않겠다는 규칙입니다. health checker Region을 제거해도 최대 1시간 동안 그 리전에서 체크가 계속됩니다.

동작 함정이 여러 개 있습니다.

- **HTTPS health check는 SSL/TLS 인증서를 검증하지 않습니다.** 인증서가 만료돼도 health check는 실패하지 않습니다. 인증서 만료를 이걸로 잡겠다는 설계는 동작하지 않습니다.
- string matching은 응답 본문의 앞 5,120바이트 안에서만 검색합니다. search string 최대 길이는 255자이고 대소문자를 구분합니다. 지원 압축 알고리즘은 gzip과 deflate뿐입니다.
- **health check를 disable하면 Route 53이 항상 healthy로 간주해 트래픽을 계속 보냅니다.** 트래픽을 끊으려면 invert해야 하고, disable 상태에서도 과금은 계속됩니다. 도입부 훈련에서 트래픽이 넘어가지 않은 원인이 이것입니다.
- failover record에 health check를 아예 연결하지 않으면 항상 healthy로 간주됩니다. disable과 결과가 같습니다.

calculated health check는 여러 health check를 묶어 판정합니다. child health check를 약 255개까지 가질 수 있고, **calculated health check가 다른 calculated health check를 감시할 수 없습니다.** 계층 구조를 만들 수 없다는 뜻입니다.

`at least x of y` 계산에는 경계값 규칙이 있습니다. x가 등록된 health check 수보다 크면 항상 unhealthy이고, x가 0이면 항상 healthy입니다. 그리고 감시 대상 health check를 disable하면 그 대상을 healthy로 계산합니다. 여기서도 unhealthy로 만들려면 invert입니다.

CloudWatch alarm 기반 health check는 별도의 규칙 집합을 가집니다.

- **alarm의 상태가 아니라 alarm이 참조하는 데이터 스트림을 봅니다.** `SetAlarmState` API로 alarm 상태를 강제해도 health check가 따라오지 않습니다.
- 고해상도 메트릭, M out of N alarm, metric math 기반 alarm, 교차 계정 alarm을 지원하지 않습니다.
- 지원 통계는 Average, Minimum, Maximum, Sum, SampleCount입니다. extended statistic은 미지원이고 alarm은 health check와 같은 계정에 있어야 합니다.
- CloudWatch 데이터가 insufficient일 때의 상태를 healthy, unhealthy, last known status 중에서 고릅니다. last known status가 없는 신규 health check의 기본값은 healthy입니다. 메트릭이 몇 시간 이상 비는 환경에서는 last known status를 권고하지 않습니다.

쿼터도 한 번은 봐 두는 것이 좋습니다. 계정당 active health check 기본 200개(증설 가능), health check 응답 헤더 총 길이 상한 16,384바이트, traffic policy 계정당 50개, traffic policy record 계정당 5개, hosted zone 계정당 초기 500개, record는 hosted zone당 10,000개입니다.

---

## 17. ARC의 zonal shift와 zonal autoshift와 routing control은 층이 다르다

Amazon Application Recovery Controller(ARC)에는 성격이 다른 세 가지가 들어 있습니다. 예전 명칭은 Route 53 Application Recovery Controller였고, 강의 자료나 오래된 문서에서는 그 이름으로 나옵니다.

| 기능 | 단위 | 시작 주체 | 지속 |
| :--- | :--- | :--- | :--- |
| zonal shift | AZ | 사용자 | 최소 1분에서 최대 3일(72시간). 연장 가능 |
| zonal autoshift | AZ | AWS 텔레메트리 | AWS가 판단해 시작하고 되돌린다 |
| routing control | 리전 | 사용자 | 상태를 바꿀 때까지 유지 |

**모든 zonal shift는 임시 완화책입니다.** 최대 72시간 만료를 가지고 연장할 수 있지만 영구 조치로 둘 수 없습니다. 시작하기 전에 리소스를 opt-in해야 하고, 남은 AZ가 트래픽을 감당하도록 애플리케이션을 prescale해야 합니다.

zonal autoshift는 AWS 내부 텔레메트리가 AZ 장애 가능성을 감지하면 AWS가 대신 트래픽을 옮기는 기능입니다. 여기서 자주 오해하는 지점이 있습니다. **ARC는 개별 리소스의 health를 검사하지 않습니다.** AZ 단위 텔레메트리로 판단하므로 영향받지 않는 리소스의 트래픽도 함께 옮겨질 수 있습니다.

zonal autoshift에는 practice run이 필수입니다. 주 1회 수행되고 리소스 1개의 트래픽을 약 30분 동안 옮겼다가 되돌립니다. 결과는 `SUCCEEDED` 또는 `FAILED`로 남습니다. 실제 상황에서 동작하는지를 평시에 검증하도록 강제하는 구조입니다.

한 가지 더 있습니다. **zonal autoshift는 auto scaling 완료를 기다리지 않고 독립적으로 동작합니다.** 트래픽을 먼저 옮기고 나면 남은 AZ가 그 부하를 받아야 하는데, 그때 on-demand scaling에 의존하는 구성이면 확장이 끝날 때까지 성능 저하가 이어집니다. prescale 권고가 여기서 나옵니다.

routing control은 리전 단위 on/off 스위치입니다. `RECOVERY_CONTROL` 타입 health check와 연결되고, 이 타입에서는 `FailureThreshold`, `RequestInterval`, `MeasureLatency`를 지원하지 않습니다. 실제 검사를 하지 않으니 검사 파라미터가 의미가 없기 때문입니다.

---

## 18. EC2 자동 복구와 lifecycle hook과 ELB fail open이 만드는 자가 치유

리전과 AZ 아래 층에는 인스턴스 단위 복구가 있습니다. 세 가지 장치가 각각 다른 실패를 다룹니다.

EC2 automatic recovery부터 봅니다. simplified automatic recovery는 지원 인스턴스에서 launch 시 기본 활성화됩니다. 별도로 켤 필요가 없습니다.

**automatic recovery는 system status check 실패에만 동작합니다. instance status check만 실패하면 동작하지 않습니다.** 두 status check의 차이가 이 절의 핵심입니다. system status check는 호스트나 네트워크 같은 AWS 측 인프라 문제를, instance status check는 게스트 OS 수준 문제를 가리킵니다. 커널 패닉이나 파일시스템 손상 같은 게스트 문제는 automatic recovery 대상이 아니고, `StatusCheckFailed_Instance` 메트릭 알람에 reboot action을 걸어 대응합니다.

복구 시 유지되는 것과 잃는 것을 구분해야 합니다.

| 유지 | 잃음 |
| :--- | :--- |
| instance ID | RAM의 데이터 |
| public IPv4, private IP, Elastic IP | instance store 볼륨의 데이터(CloudWatch action based recovery에 한해) |
| instance metadata | OS uptime 리셋 |
| placement group | |
| 연결된 EBS 볼륨 | |
| Availability Zone | |

두 방식의 지원 범위도 다릅니다. **simplified automatic recovery는 metal 인스턴스 크기와 launch 시 instance store 볼륨을 붙인 인스턴스를 지원하지 않습니다.** CloudWatch action based recovery는 이 둘을 일부 지원하고 복구 시도가 더 빠르며 SNS 알림을 붙일 수 있습니다. 대신 instance store 데이터를 잃습니다.

수동 stop/start와도 구분해야 합니다. 수동 stop/start는 Elastic IP가 없으면 새 public IPv4를 받지만 automatic recovery는 public IPv4를 유지합니다. `StatusCheckFailed_System` 메트릭이 1이면 system status check 실패이고, 복구 시도 결과는 Health Dashboard에 `AWS_EC2_SIMPLIFIED_AUTO_RECOVERY_SUCCESS` 같은 이벤트로 남습니다.

Auto Scaling 층에는 lifecycle hook이 있습니다. 인스턴스가 서비스에 들어가기 전과 종료되기 전에 작업을 끼워 넣는 장치입니다.

- 기본 heartbeat timeout은 1시간이다. global timeout은 48시간과 heartbeat timeout의 100배 중 작은 값이다.
- lifecycle action 결과는 abandon 또는 continue다. launch 중 abandon이면 인스턴스를 종료하고 교체한다. terminate 중에는 둘 다 종료로 이어지되 abandon은 남은 hook을 중단한다.
- **termination lifecycle hook은 기본적으로 best-effort다.** timeout되거나 abandon되면 ASG가 즉시 종료를 진행한다. 인스턴스 보존이 필요하면 instance lifecycle policy를 함께 쓴다.
- `CreateAutoScalingGroup`으로 여러 hook을 한 번에 만들면 모든 hook이 같은 notification target과 IAM role을 써야 한다. 서로 다른 대상이 필요하면 `PutLifecycleHook`을 개별 호출한다.
- launch lifecycle hook이 있으면 health check grace period는 인스턴스가 `InService`에 도달한 시점부터 시작한다.
- **lifecycle hook은 Spot Instance의 용량 회수 종료를 막지 못한다.**

`종료 전에 로그를 회수하도록 termination hook으로 무기한 지연시킨다`는 설계는 성립하지 않습니다. heartbeat timeout이 지나면 종료가 진행됩니다.

로드밸런서 층에는 반직관적인 동작이 하나 있습니다. ALB target group의 기본값부터 정리합니다.

| 항목 | 기본값 | 범위 |
| :--- | :--- | :--- |
| `HealthCheckIntervalSeconds` | 30초(target type이 lambda면 35초) | 5에서 300초 |
| `HealthCheckTimeoutSeconds` | 5초(lambda는 30초) | 2에서 120초 |
| `HealthyThresholdCount` | 5 | 2에서 10 |
| `UnhealthyThresholdCount` | 2 | 2에서 10 |
| `Matcher` | HTTP/1.1과 HTTP/2에서 200, gRPC에서 12 | |

**target group의 등록 대상이 전부 unhealthy가 되면 ALB는 fail open으로 동작해 모든 AZ의 모든 대상에 요청을 계속 보냅니다.** health check가 전멸했다고 트래픽이 차단되지 않습니다. 이 동작 때문에 `ALB가 전부 unhealthy가 되면 트래픽이 끊겨 Route 53 failover가 확실히 발동한다`는 판단은 틀립니다. 리전 전환 트리거는 ALB가 아니라 Route 53 health check나 ARC 쪽에 두어야 합니다.

세 층의 역할을 나누면 이렇습니다. ELB와 ASG health check는 인스턴스 교체를 트리거하고, EC2 automatic recovery는 호스트 문제를 복구하며, Route 53 health check와 ARC는 리전 전환을 트리거합니다.

---

## 19. 멀티 AZ와 멀티 리전의 경계, 그리고 split brain

어디까지가 멀티 AZ로 해결되고 어디부터 멀티 리전이 필요한지는 fault isolation boundary로 나뉩니다. AZ 하나의 소실은 멀티 AZ 구성으로 흡수되고, 리전 전체를 대상으로 하는 재해나 규제 요건은 멀티 리전을 요구합니다.

경계를 넘을 때 새로 생기는 문제가 데이터 일관성입니다. 리전 간 복제는 물리적 거리 때문에 동기 복제를 선택지에서 사실상 제외합니다. 그래서 리전 간 구성은 세 가지 중 하나를 고르게 됩니다.

| 모델 | 쓰기 | 일관성 | 예 |
| :--- | :--- | :--- | :--- |
| single writer, multi reader | 한 리전만 | 승격 전까지 정합성 유지 | Aurora Global Database, RDS cross-Region read replica |
| multi writer, 충돌 해소 | 모든 리전 | last-writer-wins | DynamoDB global tables MREC |
| multi writer, 강한 일관성 | 모든 리전 | 동기 복제와 RPO 0 | DynamoDB global tables MRSC(same-account, 정확히 3개 리전) |

split brain은 첫 번째 모델에서 발생합니다. primary가 살아 있는데 네트워크 분단으로 secondary가 승격되면 두 리전이 동시에 쓰기를 받는 상태가 됩니다. Aurora managed failover가 write fencing을 시도하는 이유가 이것이고, **그 시도가 best-effort라 성공이 보장되지 않습니다.** 그래서 리전 장애로 managed failover를 수행한 뒤에는 데이터 정합성 확인이 복구 절차의 일부가 되어야 합니다.

두 번째 모델은 split brain이 발생하지 않는 대신 충돌 해소 규칙을 받아들여야 합니다. last-writer-wins는 두 리전에서 같은 항목을 거의 동시에 갱신하면 나중 쓰기가 이깁니다. 애플리케이션이 이 규칙으로 정확성을 유지할 수 있는지를 설계 시점에 판단해야 하고, 판단하지 않은 채 `global table을 쓰니 일관성이 보장된다`고 가정하면 조용히 데이터를 잃습니다.

MRSC는 강한 일관성과 RPO 0을 제공하지만 쓰기와 강한 일관성 읽기에 리전 간 통신 지연이 붙습니다. 정확히 3개 리전 구성이 필요하고, witness는 읽기와 쓰기를 처리하지 않습니다. TTL, LSI, transaction API도 지원하지 않으므로 애플리케이션 제약을 먼저 확인해야 합니다. 또한 **same-account 구성만 지원하고 생성 후 mode를 바꿀 수 없습니다.**

---

## 20. 장애를 주입해 설계가 동작하는지 확인한다

DR 설계는 문서 위에서 완성되지 않습니다. 실제로 전환하고 복원해 봐야 격차가 드러납니다. 도입부의 quota, 엔진 버전, health check 세 가지는 전부 훈련에서만 발견되는 종류입니다.

{% include diagrams/static/sap-c02/dr-verification-loop.html %}

그림은 복구 목표가 실험과 복원 검증을 거쳐 격차와 교정으로 이어지는 순환을 보여줍니다.

AWS Fault Injection Service(FIS)가 장애 주입을 담당합니다. 예전 명칭은 AWS Fault Injection Simulator이고 약어 FIS는 유지됩니다.

실험 템플릿은 actions, targets, stop conditions로 구성됩니다. **stop condition은 CloudWatch alarm 임계값이고, 실험 중 트리거되면 FIS가 실험을 중단합니다.** 실험이 실제 장애로 번지는 것을 막는 장치입니다.

**FIS는 실제 AWS 리소스에 실제 액션을 수행합니다.** 시뮬레이션이 아닙니다. 그래서 문서가 프로덕션 실행 전 계획 단계와 pre-production 실행을 강하게 권고합니다. 과금은 action이 실행된 분과 대상 계정 수 기준입니다. single-account 실험의 대상 리소스는 실험과 같은 계정에 있어야 하고, 다른 계정을 대상으로 하려면 multi-account experiment를 씁니다.

DR 훈련에 쓰는 액션은 범위별로 갈립니다.

| 범위 | 액션 |
| :--- | :--- |
| AZ 단위 차단 | `aws:network:disrupt-connectivity`의 scope `availability-zone`. VPC당 최대 30개 subnet, action duration 1분에서 12시간 |
| 리전 격리 | `aws:network:route-table-disrupt-cross-region-connectivity`(subnet 대상), `aws:network:transit-gateway-disrupt-cross-region-connectivity`(TGW peering attachment 대상) |
| DB failover | `aws:rds:failover-db-cluster`, `aws:rds:reboot-db-instances`(`forceFailover` 기본 false) |
| ElastiCache AZ 정전 | `aws:elasticache:replicationgroup-interrupt-az-power`. Multi-AZ가 켜진 replication group에서 replication lag이 가장 작은 read replica를 primary로 승격. serverless 배포 옵션은 미지원 |

두 가지를 정확히 기억해야 합니다. 첫째, **액션 레퍼런스에 EC2 대상 AZ power interruption 액션은 없습니다.** AZ power interruption이라는 이름은 ElastiCache 쪽에 있고, 일반적인 AZ 격리는 `disrupt-connectivity`의 `availability-zone` scope입니다. 둘째, route table 기반 리전 격리 액션을 쓰려면 VPC의 `routes per route table` 쿼터를 250까지, 대상이 us-east-1이면 350에 기존 라우트 수를 더한 값까지 올려야 합니다. 준비 없이 실행하면 액션 자체가 실패합니다.

복원 쪽 검증은 앞 절의 AWS Backup restore testing이 담당합니다. 장애 주입이 전환 경로를 확인한다면 restore testing은 데이터 복구 경로를 확인합니다. 두 가지를 함께 돌려야 DR 계획 전체가 검증됩니다.

AWS Resilience Hub는 이 루프의 앞단을 맡습니다. resilience goal을 정의하고, 목표 대비 현재 구성을 평가하며, Well-Architected 기반 개선을 권고하고, FIS 실험 생성과 실행을 한 곳에서 제공합니다.

백서가 남기는 마지막 조언 하나도 함께 기억할 값입니다. **백업에서의 복원 자체가 control plane operation이므로 재해 시 불가능할 수 있습니다.** 그래서 주기적으로 미리 복원해 두는 방식이 권고됩니다. 복원 가능성을 재해 시점에 처음 확인하는 구조를 만들지 않는 것이 원칙입니다.

---

## 21. 암기해야 하는 하드 리밋과 동작 제약

시험에서 선지를 직접 가르는 수치와 동작입니다.

**Aurora Global Database와 RDS**

| 항목 | 값 |
| :--- | :--- |
| Aurora Global Database secondary 리전 | 최대 10개 |
| secondary 리전 복제 지연 | 통상 1초 미만 |
| secondary 클러스터의 read-only DB instance | 최대 16개(통상 클러스터 한도 15개가 아니다) |
| Aurora Global Database RTO / RPO | minutes / seconds |
| switchover RPO | 0 |
| managed failover RPO | 초 단위 non-zero, 복제 지연에 비례 |
| managed failover 후 secondary rebuild | 몇 분에서 수 시간 |
| `rds.global_db_rpo` | 20초에서 2,147,483,647초. Aurora PostgreSQL 전용 |
| global writer endpoint DNS TTL 권고 | 5초 |
| Aurora 자동 백업 보존 | 1일에서 35일, 기본 1일. 끌 수 없다 |
| Aurora latest restorable time | 통상 현재 시각의 5분 이내 |
| Aurora Backtrack 최대 창 | 72시간. Aurora MySQL 전용 |
| Multi-AZ DB instance failover | typically 60초에서 120초 |
| Multi-AZ DB cluster failover | typically under 35 seconds |
| Multi-AZ DB cluster 구성 | writer 1 + reader 2, 3개 AZ, semisynchronous |
| `rpl_semi_sync_master_target_apply_lag` | 기본 120초, 끄려면 최대값 86,400초 |
| PostgreSQL Multi-AZ DB cluster lag 임계 | 2분 초과 시 writer가 지연을 주입 |

**DynamoDB, S3, EFS, ECR**

| 항목 | 값 |
| :--- | :--- |
| DynamoDB PITR 복구 기간 | 1일에서 35일 |
| `LatestRestorableDateTime` | 통상 현재 시각 5분 전 |
| 삭제된 PITR 테이블의 system backup | 35일 무료 보존 |
| S3 RTC 임계값 | 15분. `Minutes` 필드는 15만 유효 |
| S3 RTC 메트릭과 이벤트 사용 가능 시점 | RTC 활성화 후 15분 이내 |
| S3 RTC SLA 미적용 구간 | 복제 전송률 기본 1 Gbps 쿼터 초과, S3 request rate 가이드라인 초과 |
| 객체 1개 복제 시 요청 | source에 최대 5회 GET/HEAD와 1회 PUT, destination마다 1회 PUT. 과금은 객체당 PUT 1회 |
| SSE-KMS 복제 쿼터 계산 | 초당 1,000객체면 KMS 쿼터에서 2,000 요청 차감 |
| EFS replication RPO | 대부분 파일시스템에서 15분 |
| EFS 15분 초과 조건 | 파일 1억 개 초과, 또는 100 GB 초과 파일의 잦은 변경 |
| ECR replication 쿼터 | registry당 rule 25개, 고유 destination 25개, rule당 filter 100개 |
| ECR 복제 소요 | 대부분 이미지가 30분 이내 |

**AWS Backup**

| 항목 | 값 |
| :--- | :--- |
| continuous backup 정밀도와 최대 보존 | 1초, 35일 |
| snapshot backup 최소 주기와 최대 보존 | 1시간, 100년 |
| cold storage 최소 보관 | 90일. retention은 cold 전환값보다 90일 이상 커야 한다 |
| 리소스당 continuous backup | 1개 |
| 복원 가능한 최신 시점 | RDS 최근 5분, Aurora `LatestRestorableTime`(통상 5분 미만), S3 최근 15분 |
| Vault Lock | vault당 1개 |
| compliance mode grace time | 최소 3일(72시간), 최대 36,500일 |
| `MinRetentionDays` 최소 / `MaxRetentionDays` 최대 | 1일 / 36,500일 |
| 계정 폐쇄 후 백업 보존 | 90일 뒤 삭제. Vault Lock도 막지 못한다 |
| restore testing plan | 계정당 100개 |
| restore testing start window | 1시간에서 168시간(7일) |
| restore testing validation 대기 | 1시간에서 168시간 |
| restore testing 실행당 복원 | protected resource 1개당 recovery point 최대 1개 |
| DLM 쿼터 | 리전당 custom policy 100개, EBS snapshot default policy 1개, AMI default policy 1개, 리소스당 tag 45개 |

**Route 53과 ARC**

| 항목 | 값 |
| :--- | :--- |
| health check 요청 간격 | 10초 또는 30초, 기본 30초. 생성 후 변경 불가 |
| `FailureThreshold` | 기본 3, 범위 1에서 10 |
| healthy 판정 | 전체 checker 중 18% 초과가 healthy로 보고 |
| HTTP/HTTPS 연결 | TCP 4초, 응답 2초 안에 2xx 또는 3xx |
| TCP health check 연결 | 10초 |
| string matching 검색 범위 | 응답 본문 앞 5,120바이트, search string 최대 255자 |
| calculated health check child | 약 255개. 다른 calculated health check는 감시 불가 |
| health checker Region | 최소 3개, 최대 64개. 제거 후 최대 1시간 잔여 |
| 계정당 active health check | 기본 200개, 증설 가능 |
| health check 응답 헤더 총 길이 | 16,384바이트 |
| hosted zone / record | 계정당 초기 500개 / hosted zone당 10,000개 |
| traffic policy / traffic policy record | 계정당 50개 / 5개 |
| zonal shift 만료 | 최소 1분에서 최대 3일(72시간), 연장 가능 |
| zonal autoshift practice run | 주 1회, 약 30분 |

**EC2, ASG, ELB, FIS**

| 항목 | 값 |
| :--- | :--- |
| automatic recovery 트리거 | system status check 실패만 |
| simplified automatic recovery 미지원 | metal 인스턴스, launch 시 instance store 부착 인스턴스 |
| 복구 시 유지 | instance ID, public/private/Elastic IP, metadata, placement group, EBS 볼륨, AZ |
| 복구 시 손실 | RAM 데이터, OS uptime 리셋, instance store 데이터(CloudWatch action based) |
| ASG lifecycle hook heartbeat timeout | 기본 1시간 |
| ASG lifecycle hook global timeout | 48시간과 heartbeat timeout의 100배 중 작은 값 |
| ALB `HealthCheckIntervalSeconds` | 기본 30초(lambda 35초), 범위 5에서 300초 |
| ALB `HealthCheckTimeoutSeconds` | 기본 5초(lambda 30초), 범위 2에서 120초 |
| ALB `HealthyThresholdCount` / `UnhealthyThresholdCount` | 기본 5 / 2, 범위 2에서 10 |
| ALB 전 대상 unhealthy | fail open. 모든 AZ의 모든 대상에 계속 전송 |
| FIS `disrupt-connectivity` AZ scope | VPC당 최대 30개 subnet, duration 1분에서 12시간 |
| FIS route table 리전 격리 사전 조건 | `routes per route table` 쿼터를 250(us-east-1 대상이면 350 + 기존 라우트 수)까지 증설 |
| Service Quotas global quota 증설 리전 | 상용 us-east-1, GovCloud us-gov-west-1, 중국 cn-north-1 |

---

## 22. 답이 갈리는 짝 비교

| 짝 | 차이를 만드는 제약 |
| :--- | :--- |
| pilot light 대 warm standby | pilot light는 서버 기동과 비핵심 인프라 배포와 확장을 거쳐야 요청을 받는다. warm standby는 축소 용량으로 이미 요청을 받는다. 짧은 RTO 요구가 이 둘을 가른다 |
| warm standby 대 hot standby | warm standby는 축소 규모라 전환 후 확장이 필요하다. hot standby는 프로덕션 전량을 미리 프로비저닝한 statically stable 구성이라 확장이 필요 없다 |
| hot standby 대 multi-site active/active | 배포 규모는 같다. hot standby는 active/passive로 운영하고 multi-site는 두 사이트가 모두 트래픽을 받아 failover 개념이 없다 |
| Aurora switchover 대 managed failover | switchover는 완전 동기화 후 승격이라 RPO 0이고 모든 클러스터가 healthy할 때만 동작한다. failover는 동기화를 기다리지 않아 RPO가 초 단위 non-zero이고 split brain 가능성이 남는다 |
| Aurora Global Database 대 RDS cross-Region read replica | Aurora는 전용 인프라로 복제해 primary 성능 영향이 작고 지연이 1초 미만이며 승격이 분 단위다. RDS read replica promotion은 몇 분이 걸리고 reboot을 포함한다 |
| Multi-AZ DB instance 대 Multi-AZ DB cluster | instance는 standby 1개이고 읽기 불가, failover 60초에서 120초다. cluster는 reader 2개가 읽기를 처리하고 failover 35초 미만이며 로컬 NVMe 인스턴스 클래스로 제한된다 |
| Aurora Backtrack 대 PITR 복원 | Backtrack은 새 클러스터를 만들지 않고 분 단위로 되감으며 최대 72시간, Aurora MySQL 전용, 생성 시점에만 활성화된다. PITR 복원은 새 클러스터를 만들고 보존 기간 안의 어느 시점이든 간다 |
| DynamoDB global tables 대 Aurora Global Database | DynamoDB는 모든 리전이 읽기와 쓰기를 처리한다. MREC는 비동기 복제와 last-writer-wins를 사용하고 MRSC는 동기 복제와 충돌 오류를 사용한다. Aurora는 primary 1개만 쓰기를 받는다 |
| DynamoDB MREC 대 MRSC | MREC가 기본값이고 RPO는 복제 지연에 해당하며 충돌은 last-writer-wins다. MRSC는 동기 복제, `ReplicatedWriteConflictException`, RPO 0을 제공하지만 정확히 3개 리전과 same-account 구성이 필요하고 생성 후 변경할 수 없다 |
| S3 기본 CRR 대 S3 RTC | 기본 CRR은 SLA 없는 best effort다. RTC는 15분 임계값을 SLA로 보장하고 메트릭과 이벤트를 낸다. RTC는 Batch Replication에 적용되지 않는다 |
| live replication 대 S3 Batch Replication | live replication은 설정 이후 객체만 복제한다. 기존 객체 복제는 Batch Replication 전용이다 |
| S3 CRR 대 SRR | CRR은 리전을 넘어 재해 대비와 지연 단축에 쓴다. SRR은 같은 리전 안이라 계정 분리, 로그 집계, 데이터 주권 요건에 쓴다 |
| AWS Backup continuous backup 대 snapshot backup | continuous는 최대 35일, 1초 정밀도, cold 전환 불가, 리소스당 1개다. snapshot은 최소 1시간 주기, 최장 100년이고 cold 전환은 지원 리소스에서만 가능하다 |
| Vault Lock governance mode 대 compliance mode | governance는 IAM 권한이 있으면 해제할 수 있다. compliance는 grace time 종료 후 사용자도 AWS도 해제할 수 없다 |
| AWS Backup restore testing 대 수동 복원 | restore testing은 스케줄 기반이고 복원 후 리소스를 자동 삭제하며 Backup Audit Manager 컨트롤로 목표 복원 시간 충족 여부를 평가한다 |
| Amazon Data Lifecycle Manager 대 AWS Backup | DLM은 EBS snapshot과 EBS-backed AMI만 자동화하고 추가 비용이 없다. AWS Backup은 다중 서비스 통합, backup vault, Vault Lock, Organizations backup policy, restore testing을 제공한다 |
| Route 53 DNS failover 대 Global Accelerator | Route 53 health check 기반 failover는 data plane이지만 DNS 캐시 영향을 받는다. Global Accelerator는 anycast IP라 DNS 캐시 문제가 없지만 traffic dial 조정은 control plane이다 |
| ARC routing control 대 weighted routing weight 변경 | routing control 상태 전환은 data plane API다. weight 변경은 control plane operation이라 리전 장애 중 신뢰할 수 없다 |
| CloudFront origin failover 대 리전 failover | origin failover는 실패한 요청 단위이고 이후 요청은 다시 primary로 간다. 리전 전체 전환 수단이 아니다 |
| zonal shift 대 zonal autoshift | zonal shift는 사용자가 시작하고 최대 72시간 만료를 갖는 임시 조치다. autoshift는 AWS 텔레메트리가 시작하고 주 1회 30분 practice run이 필수다 |
| zonal shift 계열 대 routing control | 전자는 AZ 단위 완화이고 후자는 리전 단위 전환이다 |
| Route 53 health check disable 대 invert | disable하면 항상 healthy로 간주해 트래픽이 계속 간다. 트래픽을 끊으려면 invert한다. disable 중에도 과금은 계속된다 |
| Route 53 health check 대 ELB target group health check | Route 53은 전역 checker가 공인 엔드포인트를 보고 DNS 응답을 바꾼다. ELB는 target group 내부 대상을 보고 라우팅에서 제외하며 전부 unhealthy면 fail open한다 |
| EC2 simplified automatic recovery 대 CloudWatch action based recovery | simplified는 기본 활성이지만 metal과 launch 시 instance store 부착 인스턴스를 지원하지 않는다. CloudWatch 기반은 수동 설정이 필요하고 SNS 알림과 더 빠른 복구를 제공하되 instance store 데이터를 잃는다 |
| system status check 대 instance status check | automatic recovery는 system status check 실패에만 동작한다. instance status check 실패는 reboot action으로 대응한다 |
| Elastic Disaster Recovery 대 Aurora Global Database | DRS는 EC2에 호스팅된 애플리케이션과 데이터베이스를 블록 레벨로 복제하고 RDS는 대상이 아니다. 관리형 데이터베이스의 리전 간 복제는 Aurora Global Database나 cross-Region read replica다 |
| FIS 대 Resilience Hub | FIS는 실제 리소스에 실제 액션을 주입한다. Resilience Hub는 목표 정의와 평가와 권고를 담당하고 FIS 실험 생성과 실행을 통합한다 |

---

## 23. 그럴듯하지만 성립하지 않는 조합

| 조합 | 성립하지 않는 이유 |
| :--- | :--- |
| Aurora Global Database의 switchover로 리전 장애를 복구한다 | switchover는 모든 클러스터가 healthy할 때만 동작하는 계획된 절차다. 장애 복구는 managed failover다 |
| Aurora Global Database에 Backtrack을 붙여 되감기와 리전 DR을 동시에 만족시킨다 | Global Database는 Backtrack을 지원하지 않는다 |
| 운영 중인 Aurora MySQL 클러스터를 modify해 Backtrack을 켠다 | Backtrack은 클러스터 생성 시점이나 스냅샷 복원 시점에만 활성화된다 |
| Aurora Global Database의 secondary에 Auto Scaling을 걸어 승격 후 자동 확장되게 한다 | secondary 클러스터에 Aurora Auto Scaling을 지원하지 않는다 |
| headless secondary 클러스터로 managed failover를 수행한다 | 먼저 DB instance를 추가해야 한다 |
| 엔진 마이너 버전이 다른 상태로 managed failover를 표준 절차로 삼는다 | major와 minor 버전이 모두 같아야 한다. 다르면 detach-and-promote 방식의 manual failover만 남는다 |
| `rds.global_db_rpo`를 0으로 설정해 데이터 손실을 없앤다 | 설정 범위가 20초에서 2,147,483,647초다. 0을 지정할 수 없다 |
| RDS Multi-AZ standby로 리포팅 읽기 부하를 분산한다 | Multi-AZ DB instance의 standby는 읽기 트래픽을 서비스할 수 없다 |
| read replica를 추가해 failover 시간을 35초 미만으로 줄인다 | read replica는 읽기 부하만 해결한다. Multi-AZ DB instance의 failover는 여전히 통상 60초에서 120초다 |
| RDS Multi-AZ DB cluster에 AWS Backup continuous backup을 걸어 PITR을 얻는다 | AWS Backup은 Multi-AZ DB cluster의 continuous backup과 PITR을 지원하지 않는다 |
| S3 replication 규칙을 켜면 기존 객체까지 DR 버킷에 채워진다 | live replication은 설정 이후 객체만 다룬다. 기존 객체는 Batch Replication이다 |
| Batch Replication에 RTC를 적용해 기존 객체도 15분 SLA로 옮긴다 | RTC는 Batch Replication에 적용되지 않는다 |
| MRAP failover control만 켜면 failover 후 쓰인 데이터가 원래 버킷과 동기화된다 | two-way replication rule을 먼저 구성해야 한다 |
| EFS replication의 destination을 특정 시점의 일관된 사본으로 취급한다 | Last synced time 기준이라 point-in-time consistent가 아니다 |
| ECR replication 규칙을 켜면 기존 이미지까지 DR 리전 registry에 채워진다 | 복제 설정 이후 push되거나 restore된 것만 복제된다 |
| ECR replication을 연쇄 구성해 리전 A에서 B로, B에서 C로 이미지를 전파한다 | replication은 연쇄되지 않는다. 파티션을 넘는 복제도 지원하지 않는다 |
| AWS Backup continuous backup을 90일 이상 보존하거나 cold storage로 전환한다 | 최대 보존이 35일이고 cold 전환은 최소 90일을 요구해 구조적으로 성립하지 않는다 |
| RDS나 Aurora의 월말 snapshot을 cold storage로 내려 장기 보존 비용을 줄인다 | cold storage 전환은 리소스 유형별 지원 항목이고 RDS와 Aurora는 지원 대상이 아니다 |
| RDS continuous backup 자체를 DR 리전으로 복사한다 | 트랜잭션 로그를 복사할 수 없다. snapshot을 만들어 복사한다 |
| S3의 cross-Region backup 사본에서도 PITR로 복원한다 | cross-Region이나 cross-account 사본은 PITR을 갖지 않고 생성 시점으로만 복원된다 |
| cold tier로 내린 백업을 DR 리전으로 복사한다 | cold tier에 있는 백업은 cross-Region copy를 지원하지 않는다 |
| governance mode Vault Lock으로 변경 불가 보존을 만족시킨다 | governance mode는 IAM 권한이 있으면 해제된다. immutability가 필요하면 compliance mode다 |
| compliance mode Vault Lock을 만들면 즉시 immutable해진다 | 최소 3일(72시간)의 grace time이 지나야 한다 |
| Vault Lock을 걸었으니 계정을 닫아도 백업이 남는다 | 계정 폐쇄 시 AWS가 90일간 유지한 뒤 삭제한다 |
| Organizations backup policy를 상위 OU에 부분 정책으로만 붙여도 백업이 돈다 | effective policy가 필수 요소를 갖추지 못하면 유효하지 않은 정책이 되어 백업하지 않는다 |
| Data Lifecycle Manager로 RDS나 EFS 백업을 자동화한다 | DLM 대상은 EBS snapshot과 EBS-backed AMI뿐이다 |
| Config rule로 백업 존재를 확인해 복원 가능성을 증명한다 | 존재 확인과 복원 가능성은 다르다. 복원 가능성은 restore testing이 증명한다 |
| weighted routing policy의 weight를 0으로 바꿔 리전 장애 시 자동 failover를 구현한다 | weight 변경은 control plane operation이라 리전 장애 중 신뢰할 수 없다. data plane 방식은 ARC routing control이다 |
| Global Accelerator traffic dial을 0으로 낮춰 control plane 의존을 없앤다 | traffic dial 조정 자체가 control plane operation이다 |
| CloudFront origin failover로 리전 전체 전환을 구현한다 | origin failover는 실패한 요청 단위이고 이후 요청은 다시 primary로 간다 |
| Route 53 health check를 disable해 트래픽을 끊는다 | disable하면 항상 healthy로 간주해 트래픽이 계속 간다. 끊으려면 invert한다 |
| failover record에서 health check 연결을 제거해 트래픽을 넘긴다 | health check가 없는 record는 항상 healthy로 간주된다 |
| metric math로 계산한 CloudWatch alarm을 Route 53 health check에 연결한다 | metric math alarm, M out of N alarm, 고해상도 메트릭, 교차 계정 alarm은 지원되지 않는다 |
| `SetAlarmState`로 CloudWatch 기반 health check를 강제 failover 시킨다 | Route 53은 alarm 상태가 아니라 데이터 스트림을 본다 |
| calculated health check로 다른 calculated health check를 묶어 계층 구조를 만든다 | calculated health check는 다른 calculated health check를 감시할 수 없다 |
| HTTPS health check로 인증서 만료를 탐지한다 | HTTPS health check는 SSL/TLS 인증서를 검증하지 않는다 |
| health check 요청 간격을 30초에서 10초로 바꿔 감지를 앞당긴다 | 요청 간격은 생성 후 변경할 수 없다 |
| zonal autoshift가 특정 리소스의 health를 보고 그 리소스만 옮긴다 | ARC는 개별 리소스 health를 검사하지 않고 AZ 단위 텔레메트리로 판단한다 |
| zonal shift를 영구 조치로 둔다 | 최대 3일(72시간) 만료를 갖는 임시 완화책이다 |
| zonal autoshift가 트래픽을 옮긴 뒤 on-demand scaling으로 용량을 맞춘다 | autoshift는 auto scaling 완료를 기다리지 않는다. prescale이 전제다 |
| pilot light 구성에서 DR 리전이 즉시 트래픽을 처리한다 | pilot light는 추가 조치 없이 요청을 처리할 수 없다. 즉시 처리하는 것은 warm standby다 |
| Auto Scaling으로 DR 리전을 확장하니 statically stable하다 | Auto Scaling 의존은 control plane 의존이다. statically stable 구성은 hot standby다 |
| DR 리전 용량 계획만 세우고 quota 증설은 장애 발생 후에 요청한다 | quota가 프로덕션 용량 미만이면 확장이 막히고 증설 요청은 즉시 승인되지 않는다 |
| DRS로 RDS 인스턴스를 다른 리전에 복제한다 | DRS는 EC2에 호스팅된 애플리케이션과 데이터베이스만 대상이다 |
| multi-site active/active면 백업이 필요 없다 | 데이터 손상, 삭제, 난독화 재해는 복구 시간이 항상 0보다 크고 recovery point가 발견 이전 시점이 된다 |
| instance status check 실패에서 EC2 automatic recovery가 인스턴스를 옮긴다 | automatic recovery는 system status check 실패에만 동작한다 |
| instance store 볼륨을 붙여 launch한 인스턴스에서 simplified automatic recovery가 동작한다 | 이 구성은 simplified automatic recovery 미지원이다 |
| EC2 automatic recovery가 instance store 데이터를 보존한다 | CloudWatch action based recovery에서는 instance store 데이터를 잃고, 어떤 방식이든 RAM 데이터는 잃는다 |
| ASG termination lifecycle hook이 종료를 무기한 지연시켜 로그 회수를 보장한다 | 기본은 best-effort이고 heartbeat timeout(기본 1시간) 후 즉시 종료로 진행한다 |
| lifecycle hook으로 Spot Instance의 용량 회수 종료를 막는다 | lifecycle hook은 Spot 용량 회수 종료를 막지 못한다 |
| ALB 대상이 전부 unhealthy가 되면 트래픽이 끊겨 Route 53 failover가 확실히 발동한다 | ALB는 fail open이라 unhealthy 대상에도 계속 요청을 보낸다 |
| FIS의 EC2용 AZ power interruption 액션으로 AZ 정전을 재현한다 | 액션 레퍼런스의 AZ power interruption은 ElastiCache 전용이고, AZ 격리는 `aws:network:disrupt-connectivity`의 `availability-zone` scope다 |
| FIS 실험은 시뮬레이션이라 프로덕션에서 안전하다 | FIS는 실제 리소스에 실제 액션을 수행한다. 계획 단계와 pre-production 실행이 권고된다 |
| 운영 중인 global table의 consistency mode를 MREC에서 MRSC로 바꾼다 | 생성 후 변경할 수 없다 |
| DynamoDB PITR 복원이 기존 테이블을 제자리에서 되돌린다 | PITR 복원은 항상 새 테이블을 만든다 |
| DynamoDB PITR 복구 기간을 7일로 줄여 비용을 아낀다 | 과금은 테이블 크기 기준이고 복구 기간 길이는 가격에 영향을 주지 않는다 |

---

## 24. 예상 문제 10문항

**Q1.** Aurora PostgreSQL Global Database가 primary us-east-1, secondary eu-west-1로 구성되어 있습니다. us-east-1 리전 장애로 primary 클러스터와 그 리전의 control plane 모두에 접근할 수 없습니다. 사업부는 RTO 10분을 요구하며 수 초 분량의 데이터 손실은 허용합니다. MOST appropriate 조치는 무엇입니까?

- A. eu-west-1 secondary에 managed failover를 수행하고, write fencing이 보장되지 않는 점을 감안해 복구 후 데이터 정합성을 확인한다.
- B. eu-west-1로 switchover를 수행해 데이터 손실 없이 승격한다.
- C. 최신 스냅샷을 eu-west-1에 복원하고 애플리케이션을 그 클러스터로 전환한다.
- D. Aurora Backtrack으로 장애 직전 시점까지 되감은 뒤 eu-west-1에서 서비스를 재개한다.

<details markdown="1">
<summary>정답과 해설</summary>

**정답: A**

managed failover는 계획되지 않은 장애를 위한 절차입니다. 데이터 동기화를 기다리지 않으므로 RPO는 장애 시점의 복제 지연에 비례하는 초 단위 값이 되고, 문서는 Global Database의 RTO를 분 단위로 기술합니다. 다만 Aurora가 시도하는 write fencing은 best effort라 split-brain 가능성이 남으므로 복구 후 정합성 확인이 필요합니다.

- B가 틀린 이유: switchover는 secondary를 primary와 완전히 동기화한 뒤 승격하는 계획된 절차라 모든 클러스터가 healthy할 때만 동작합니다. primary에 접근할 수 없는 리전 장애에서는 사용할 수 없습니다.
- C가 틀린 이유: 스냅샷 복원은 클러스터를 새로 만드는 작업이라 RTO 10분을 맞추기 어렵고, 복제본이 이미 존재하는 상황에서 데이터도 더 낡습니다.
- D가 틀린 이유: Aurora Global Database는 Backtrack을 지원하지 않습니다. 또 Backtrack은 Aurora MySQL 전용이라 PostgreSQL에서는 애초에 선택지가 아닙니다.

</details>

---

**Q2.** RDS for PostgreSQL을 Multi-AZ DB instance로 운영 중입니다. 리포팅 쿼리가 늘면서 writer의 CPU가 포화 상태이고, 사업부는 계획되지 않은 failover 시간을 35초 미만으로 줄이라고 요구합니다. 인스턴스 클래스 변경과 짧은 유지보수 창은 허용됩니다. 애플리케이션의 연결 문자열 변경도 가능합니다. MOST appropriate 조치는 무엇입니까?

- A. Multi-AZ DB cluster로 전환하고 지원되는 로컬 NVMe 인스턴스 클래스를 선택한다.
- B. 현재 Multi-AZ 구성의 standby 엔드포인트로 리포팅 쿼리를 보낸다.
- C. cross-Region read replica를 추가하고 리포팅을 그쪽으로 보낸다.
- D. 같은 리전에 read replica 2개를 추가하고 리포팅을 분산한다.

<details markdown="1">
<summary>정답과 해설</summary>

**정답: A**

Multi-AZ DB cluster는 writer 1개와 reader 2개를 3개 AZ에 두는 semisynchronous 구성입니다. reader가 읽기 트래픽을 처리하면서 동시에 자동 failover 대상이 되고, failover는 통상 35초 미만입니다. 두 요구(읽기 분산, failover 35초 미만)를 한 구성이 동시에 만족하는 유일한 선택지입니다. 지원 인스턴스 클래스가 로컬 NVMe를 가진 계열로 제한된다는 제약만 확인하면 됩니다.

- B가 틀린 이유: Multi-AZ DB instance의 standby는 읽기 트래픽을 서비스할 수 없습니다. 연결 가능한 엔드포인트 자체가 없습니다.
- C가 틀린 이유: cross-Region read replica는 비동기 복제이고 promotion에 몇 분과 reboot이 필요합니다. 리포팅 분산은 되지만 failover 35초 요구를 만족시키지 못하고 리전 간 데이터 전송 비용도 붙습니다.
- D가 틀린 이유: read replica는 읽기 부하만 해결합니다. Multi-AZ DB instance의 failover는 여전히 통상 60초에서 120초라 요구 미달입니다.

</details>

---

**Q3.** RDS for MySQL 데이터베이스에 두 가지 요구가 있습니다. 첫째, 최근 30일 안의 어느 시점으로든 복구할 수 있어야 합니다. 둘째, 월말 백업은 7년간 보존해야 합니다. 데이터베이스는 2 TB이고 백업 저장 비용을 최소화해야 하며 별도 스크립트를 만들어 운영하는 것은 피하려 합니다. 팀은 AWS Backup 하나로 두 요구를 처리하려 합니다. MOST appropriate 구성은 무엇입니까?

- A. 같은 backup plan에 continuous backup rule(보존 35일)과 월 1회 snapshot rule(보존 7년)을 함께 둔다.
- B. continuous backup rule 하나만 두고 보존 기간을 7년으로 설정한다.
- C. snapshot backup rule만 1시간 주기로 두고 7년 보존한다.
- D. continuous backup rule 하나만 두고, 월말에 그 recovery point를 cold storage로 전환해 7년 보존한다.

<details markdown="1">
<summary>정답과 해설</summary>

**정답: A**

continuous backup(PITR)은 1초 정밀도로 최대 35일까지 되감을 수 있어 첫 번째 요구를 만족시킵니다. snapshot backup은 최소 1시간 주기로 만들 수 있고 최장 100년까지 보존할 수 있어 두 번째 요구에 맞습니다. 하나의 backup plan에 두 rule을 함께 두는 구성이 표준 해법입니다.

- B가 틀린 이유: continuous backup의 최대 보존 기간은 35일입니다. 7년을 지정할 수 없습니다.
- C가 틀린 이유: snapshot은 최소 1시간 주기라 그 사이 임의 시점으로 되감을 수 없습니다. 30일 어느 시점이든 복구하라는 요구를 만족시키지 못하고 시간당 스냅샷을 7년 보관하는 비용도 큽니다.
- D가 틀린 이유: 두 번 틀립니다. continuous backup은 최대 보존이 35일이고 cold storage 전환은 최소 90일 보관을 요구하므로 구조적으로 cold로 갈 수 없습니다. 게다가 AWS Backup의 `Lifecycle to cold storage`는 리소스 유형별로 지원 여부가 갈리며 Amazon RDS는 지원 대상이 아닙니다.

</details>

---

**Q4.** 이미 4억 개 객체가 들어 있는 S3 버킷을 DR 리전으로 복제해야 합니다. 요구는 두 가지입니다. 기존 객체 전량이 DR 버킷에 존재해야 하고, 앞으로 들어오는 객체는 예측 가능한 시간 안에 복제되어야 합니다. 감사 대응을 위해 복제 지연을 지표로 증명해야 합니다. 원본 버킷은 versioning이 켜져 있고 애플리케이션 다운타임은 허용되지 않습니다. MOST appropriate 조합은 무엇입니까?

- A. S3 Replication Time Control을 켠 live replication rule을 만들고, 기존 객체는 S3 Batch Replication으로 처리한다.
- B. live replication rule을 만들면 기존 객체까지 순차적으로 복제되므로 rule 하나만 만든다.
- C. S3 Batch Replication job에 Replication Time Control을 적용해 기존 객체와 신규 객체를 같은 SLA로 처리한다.
- D. `aws s3 sync`를 매시간 실행하는 스케줄 작업을 만들어 두 버킷을 맞춘다.

<details markdown="1">
<summary>정답과 해설</summary>

**정답: A**

live replication은 설정 이후 새로 쓰이거나 갱신된 객체만 복제합니다. 설정 전에 존재하던 객체는 S3 Batch Replication으로 따로 처리해야 합니다. 신규 객체의 예측 가능한 복제와 지표 증명은 S3 RTC가 담당합니다. RTC는 15분 임계값을 SLA로 보장하고 `OperationMissedThreshold`와 `OperationReplicatedAfterThreshold` 이벤트를 냅니다.

- B가 틀린 이유: live replication은 기존 객체를 복제하지 않습니다. 4억 개가 영원히 DR 버킷에 나타나지 않습니다.
- C가 틀린 이유: S3 RTC는 Batch Replication에 적용되지 않습니다. 기존 객체 복제에 15분 SLA를 붙일 수 없습니다.
- D가 틀린 이유: 4억 개 객체를 매시간 LIST하는 비용이 크고 SLA도 지표도 없습니다. 복제 지연을 증명하라는 요구를 충족하지 못합니다.

</details>

---

**Q5.** Route 53 failover routing으로 primary와 secondary 리전을 운영합니다. primary 리전 유지보수 동안 트래픽을 secondary로 보내려고 운영자가 primary record에 연결된 health check를 콘솔에서 disable했는데, 트래픽이 계속 primary로 갑니다. 유지보수 창은 2시간이고 record 구성은 바꾸지 않는 것이 원칙입니다. MOST appropriate 조치는 무엇입니까?

- A. 그 health check의 invert 옵션을 활성화한다.
- B. health check가 참조하는 CloudWatch alarm을 `SetAlarmState`로 ALARM 상태로 만든다.
- C. primary record에서 health check 연결을 제거한다.
- D. health check의 요청 간격을 30초에서 10초로 바꿔 감지를 앞당긴다.

<details markdown="1">
<summary>정답과 해설</summary>

**정답: A**

health check를 disable하면 Route 53이 그 엔드포인트를 항상 healthy로 간주해 트래픽을 계속 보냅니다. 상태를 unhealthy로 만들려면 invert를 사용해야 합니다. disable 상태에서도 과금은 계속된다는 점도 함께 기억할 지점입니다.

- B가 틀린 이유: CloudWatch alarm 기반 health check는 alarm의 상태가 아니라 alarm이 참조하는 데이터 스트림을 봅니다. `SetAlarmState`로 상태를 강제해도 health check가 따라오지 않습니다. 게다가 이 문항의 health check는 엔드포인트 검사형입니다.
- C가 틀린 이유: health check가 연결되지 않은 failover record는 항상 healthy로 간주됩니다. disable과 결과가 같고 record 구성을 바꾸지 않는다는 원칙도 어깁니다.
- D가 틀린 이유: 요청 간격은 health check 생성 후 변경할 수 없습니다. 변경이 가능하더라도 감지 속도만 바뀔 뿐 엔드포인트가 healthy인 이상 failover는 일어나지 않습니다.

</details>

---

**Q6.** 멀티 리전 active/passive 아키텍처에서 애플리케이션 헬스 엔드포인트가 리전이 부분적으로 손상된 상황에서도 200을 반환하는 사례가 있어 자동 failover가 오탐과 미탐을 반복합니다. 운영팀은 사람이 판단해 전환하되, 리전 장애 중에도 신뢰할 수 있는 경로를 원하고 weight 수정 같은 control plane 조작 의존을 없애려 합니다. MOST resilient 접근은 무엇입니까?

- A. Amazon Application Recovery Controller의 routing control과 `RECOVERY_CONTROL` 타입 health check를 구성하고 data plane API로 상태를 전환한다.
- B. Route 53 엔드포인트 health check 기반 failover routing만 유지하고 임계값을 조정한다.
- C. 운영자가 weighted routing record의 weight를 0으로 바꿔 전환한다.
- D. Global Accelerator endpoint group의 traffic dial을 0으로 낮춰 전환한다.

<details markdown="1">
<summary>정답과 해설</summary>

**정답: A**

ARC routing control은 실제 health를 검사하지 않고 on/off 스위치로만 동작하는 Route 53 health check(`RECOVERY_CONTROL` 타입)를 만듭니다. routing control 상태가 ON이면 healthy, OFF면 unhealthy로 취급되고 상태 변경은 data plane API로 수행합니다. 사람이 판단해 전환하면서도 리전 장애 중 control plane에 의존하지 않는 유일한 선지입니다.

- B가 틀린 이유: 엔드포인트 health check는 오탐 원인인 헬스 엔드포인트 자체를 계속 신뢰합니다. 임계값 조정으로는 200을 반환하는 손상 상태를 구분할 수 없습니다.
- C가 틀린 이유: record의 weight 변경은 control plane operation입니다. 리전 장애 중에는 신뢰할 수 없다고 AWS DR 백서가 명시합니다.
- D가 틀린 이유: Global Accelerator의 traffic dial 조정도 control plane operation입니다. DNS 캐시 문제는 피하지만 이 문항이 제외하라고 명시한 의존이 그대로 남습니다.

</details>

---

**Q7.** EC2 인스턴스에서 커널 문제로 instance status check 실패가 주기적으로 발생합니다. 이 인스턴스는 launch 시 instance store 볼륨을 붙였고 Elastic IP를 사용하며, 팀은 EC2 automatic recovery에 의존하고 있었지만 복구가 일어나지 않았습니다. 근본 원인 수정 전까지 서비스 중단 시간을 줄여야 합니다. MOST appropriate 조치는 무엇입니까?

- A. `StatusCheckFailed_Instance` 메트릭에 알람을 걸고 reboot action을 연결한다.
- B. 인스턴스에서 simplified automatic recovery를 활성화한다.
- C. `StatusCheckFailed_System` 메트릭 알람에 recover action을 연결한다.
- D. 장애 시 운영자가 인스턴스를 stop 후 start 한다.

<details markdown="1">
<summary>정답과 해설</summary>

**정답: A**

automatic recovery는 system status check 실패에만 동작합니다. 이 문항의 실패는 instance status check이므로 자동 복구가 트리거되지 않은 것이 정상 동작입니다. 게스트 OS 수준 문제는 reboot으로 회복되는 경우가 많으므로 `StatusCheckFailed_Instance` 알람에 reboot action을 거는 것이 맞습니다.

- B가 틀린 이유: simplified automatic recovery는 launch 시 instance store 볼륨을 붙인 인스턴스를 지원하지 않습니다. 지원되더라도 system status check 실패에만 반응하므로 이 증상에는 동작하지 않습니다.
- C가 틀린 이유: 이번 실패는 instance status check라 `StatusCheckFailed_System` 알람이 울리지 않습니다. 또 CloudWatch action based recovery는 instance store 볼륨의 데이터를 잃습니다.
- D가 틀린 이유: 수동 개입이라 반복되는 장애에 자동 대응이 되지 않고 중단 시간이 사람의 반응 속도에 좌우됩니다. stop과 start는 instance store 데이터도 잃습니다.

</details>

---

**Q8.** 감사인이 백업 recovery point를 조직 구성원도 AWS도 삭제하거나 보존 기간을 줄일 수 없는 상태로 만들라고 요구합니다. 동시에 운영팀은 잘못 설정한 보존 규칙을 되돌릴 최소한의 시간을 원합니다. AWS Backup을 사용 중이며 vault는 리전마다 하나씩 있습니다. 과거에 보존 기간을 잘못 입력한 적이 있어 설정을 검토할 시간을 반드시 확보하려 합니다. MOST appropriate 구성은 무엇입니까?

- A. `ChangeableForDays`를 7로 지정해 compliance mode Vault Lock을 만들고 7일 grace time 안에 설정을 검토한다.
- B. governance mode Vault Lock을 만들고 lock 제거 권한을 보안팀 role에만 부여한다.
- C. `ChangeableForDays`를 1로 지정해 compliance mode Vault Lock을 만든다.
- D. backup vault의 recovery point에 S3 Object Lock compliance mode를 적용한다.

<details markdown="1">
<summary>정답과 해설</summary>

**정답: A**

`PutBackupVaultLockConfiguration` 호출에 `ChangeableForDays`를 넣으면 compliance mode가 됩니다. grace time은 최소 3일에서 최대 36,500일 범위이며, 그 기간이 끝나면 사용자도 AWS도 vault와 lock을 바꾸거나 지울 수 없습니다. 7일을 주면 감사 요구와 되돌릴 여유를 동시에 확보합니다.

- B가 틀린 이유: governance mode는 충분한 IAM 권한을 가진 사용자가 lock을 제거할 수 있습니다. 권한을 좁혀도 권한 자체를 다시 넓힐 수 있으므로 변경 불가 요구를 만족시키지 못합니다.
- C가 틀린 이유: grace time의 최소값은 3일(72시간)입니다. 1일은 API가 받지 않습니다.
- D가 틀린 이유: S3 Object Lock은 S3 객체 버전을 대상으로 하고 versioning이 켜진 버킷을 전제로 합니다. backup vault의 recovery point에는 적용할 수 없습니다.

</details>

---

**Q9.** 현재 DR 전략은 backup and restore입니다. 사업부가 RTO 15분, RPO 5분으로 목표를 올렸습니다. DR 리전에 축소된 용량을 상시 가동할 예산은 있지만 프로덕션 전량을 상시 가동할 예산은 없습니다. 전환 후에는 Auto Scaling으로 프로덕션 용량까지 확장할 계획입니다. DR 리전에는 데이터 복제가 이미 구성되어 있습니다. MOST appropriate 조합은 무엇입니까?

- A. warm standby를 구성하고 DR 리전의 service quota를 프로덕션 전량 기준으로 미리 증설한다.
- B. pilot light를 구성하고 전환 시 서버를 켠 뒤 Auto Scaling으로 확장한다.
- C. multi-site active/active로 전환해 failover 개념 자체를 없앤다.
- D. warm standby를 구성하고 리전 장애가 발생하면 그때 service quota 증설을 요청한다.

<details markdown="1">
<summary>정답과 해설</summary>

**정답: A**

warm standby는 축소된 용량으로 즉시 트래픽을 받을 수 있는 구성이라 추가 조치 없이 요청을 처리한다는 점에서 pilot light와 갈립니다. RTO 15분 목표에는 이 성질이 결정적입니다. 다만 DR 리전의 service quota를 프로덕션 용량까지 올려두지 않으면 확장 자체가 막히므로 사전 증설이 함께 필요합니다.

- B가 틀린 이유: pilot light는 서버를 켜고 비핵심 인프라를 배포하고 확장하는 단계를 거쳐야 요청을 처리합니다. RTO 15분 안에 이 단계를 마치는 것을 전제로 삼는 것은 위험합니다.
- C가 틀린 이유: multi-site active/active는 가장 복잡하고 비싼 접근이며 프로덕션 전량 상시 가동을 요구합니다. 명시된 예산 제약과 충돌합니다.
- D가 틀린 이유: quota 증설 요청은 즉시 승인되지 않습니다. 장애 발생 후 요청하면 확장이 막혀 RTO를 지킬 수 없습니다.

</details>

---

**Q10.** Aurora MySQL Global Database를 운영하며 비용을 아끼려고 secondary 리전 클러스터를 headless로 두었습니다. 지난달 primary 클러스터만 마이너 엔진 버전을 올렸습니다. 이제 팀은 리전 장애 시 managed failover로 secondary를 승격하는 절차를 표준화하려 합니다. 이 절차가 실제로 성공하려면 사전에 필요한 조치 2개는 무엇입니까? (2개를 고르시오.)

- A. secondary 클러스터에 DB instance를 최소 1개 추가한다.
- B. primary와 secondary 클러스터의 major와 minor 엔진 버전을 일치시킨다.
- C. Aurora Backtrack을 활성화해 승격 실패 시 되감을 수 있게 한다.
- D. secondary 클러스터에 Aurora Auto Scaling을 구성해 승격 후 자동 확장되게 한다.
- E. `rds.global_db_rpo`를 0으로 설정해 데이터 손실을 없앤다.
- F. secondary 리전에서 switchover를 미리 한 번 수행해 절차를 검증한다.

<details markdown="1">
<summary>정답과 해설</summary>

**정답: A, B**

headless secondary 클러스터로 switchover나 failover를 하려면 먼저 DB instance를 추가해야 합니다. 또 managed switchover와 managed failover 모두 primary와 secondary의 major 및 minor 엔진 버전이 같아야 합니다. 버전이 다르면 detach-and-promote 방식의 manual failover만 남고, 그 경로는 RTO가 크게 늘어납니다.

- C가 틀린 이유: Aurora Global Database는 Backtrack을 지원하지 않습니다.
- D가 틀린 이유: Aurora Global Database는 secondary 클러스터에 Aurora Auto Scaling을 지원하지 않습니다.
- E가 틀린 이유: `rds.global_db_rpo`는 Aurora PostgreSQL 파라미터이고 설정 범위는 20초에서 2,147,483,647초입니다. 0을 지정할 수 없고, 목표를 낮게 잡으면 secondary의 RPO lag이 목표를 넘을 때 primary의 커밋이 블록됩니다.
- F가 틀린 이유: switchover는 모든 클러스터가 healthy할 때만 동작하는 계획된 절차입니다. 리전 장애 시 사용할 절차의 검증으로 성립하지 않고, headless 상태에서는 애초에 실행되지 않습니다.

</details>

---

## 25. Reference

- [AWS Well-Architected Framework - Disaster recovery of workloads on AWS](https://docs.aws.amazon.com/whitepapers/latest/disaster-recovery-workloads-on-aws/disaster-recovery-workloads-on-aws.html)
- [AWS Well-Architected Framework - Disaster recovery options in the cloud](https://docs.aws.amazon.com/whitepapers/latest/disaster-recovery-workloads-on-aws/disaster-recovery-options-in-the-cloud.html)
- [AWS Well-Architected Framework - Reliability Pillar](https://docs.aws.amazon.com/wellarchitected/latest/reliability-pillar/welcome.html)
- [AWS Fault Isolation Boundaries](https://docs.aws.amazon.com/whitepapers/latest/aws-fault-isolation-boundaries/abstract-and-introduction.html)
- [AWS Elastic Disaster Recovery - What is DRS?](https://docs.aws.amazon.com/drs/latest/userguide/what-is-drs.html)
- [AWS Backup - What is AWS Backup?](https://docs.aws.amazon.com/aws-backup/latest/devguide/whatisbackup.html)
- [AWS Backup - Feature availability](https://docs.aws.amazon.com/aws-backup/latest/devguide/backup-feature-availability.html)
- [AWS Backup - Copying backups across AWS Regions](https://docs.aws.amazon.com/aws-backup/latest/devguide/cross-region-backup.html)
- [AWS Backup - Point-in-time recovery](https://docs.aws.amazon.com/aws-backup/latest/devguide/point-in-time-recovery.html)
- [AWS Backup - Restore testing](https://docs.aws.amazon.com/aws-backup/latest/devguide/restore-testing.html)
- [AWS Backup - Vault Lock](https://docs.aws.amazon.com/aws-backup/latest/devguide/vault-lock.html)
- [AWS Backup - Logically air-gapped vaults](https://docs.aws.amazon.com/aws-backup/latest/devguide/logicallyairgappedvault.html)
- [AWS Backup - Audit Manager](https://docs.aws.amazon.com/aws-backup/latest/devguide/aws-backup-audit-manager.html)
- [AWS Organizations - Backup policies](https://docs.aws.amazon.com/organizations/latest/userguide/orgs_manage_policies_backup.html)
- [Amazon EC2 - Amazon EBS snapshots](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/EBSSnapshots.html)
- [Amazon Aurora - Global databases](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/aurora-global-database.html)
- [Amazon Aurora - Global database disaster recovery](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/aurora-global-database-disaster-recovery.html)
- [Amazon Aurora - Backups](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/Aurora.Managing.Backups.html)
- [Amazon Aurora MySQL - Backtrack](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/AuroraMySQL.Managing.Backtrack.html)
- [Amazon RDS - Multi-AZ DB clusters](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/multi-az-db-clusters-concepts.html)
- [Amazon RDS - Multi-AZ DB cluster failover](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/multi-az-db-clusters-concepts-failover.html)
- [Amazon RDS - Multi-AZ deployments](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Concepts.MultiAZSingleStandby.html)
- [Amazon RDS - Multi-AZ failover](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Concepts.MultiAZ.Failover.html)
- [Amazon RDS - Read replicas](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_ReadRepl.html)
- [Amazon DynamoDB - Global tables](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/GlobalTables.html)
- [Amazon DynamoDB - Multi-account global tables](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/globaltables-MultiAccount.html)
- [Amazon DynamoDB - Global tables security](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/globaltables-security.html)
- [Amazon DynamoDB - Global tables design best practices](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/bp-global-table-design.html)
- [AWS Prescriptive Guidance - DynamoDB global tables](https://docs.aws.amazon.com/prescriptive-guidance/latest/dynamodb-global-tables/overview.html)
- [Amazon DynamoDB - Point-in-time recovery](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/PointInTimeRecovery.html)
- [Amazon DynamoDB - How point-in-time recovery works](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/PointInTimeRecovery_Howitworks.html)
- [Amazon S3 - Replicating objects](https://docs.aws.amazon.com/AmazonS3/latest/userguide/replication.html)
- [Amazon S3 - Replication Time Control](https://docs.aws.amazon.com/AmazonS3/latest/userguide/replication-time-control.html)
- [Amazon S3 - Multi-Region Access Point failover](https://docs.aws.amazon.com/AmazonS3/latest/userguide/MultiRegionAccessPointFailover.html)
- [Amazon EFS - Replicating file systems](https://docs.aws.amazon.com/efs/latest/ug/efs-replication.html)
- [Amazon Route 53 - DNS failover](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/dns-failover.html)
- [Amazon Route 53 - Determining endpoint health](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/dns-failover-determining-health-of-endpoints.html)
- [Amazon Route 53 - Creating and configuring health checks](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/health-checks-creating-values.html)
- [Amazon Route 53 - Disabling or enabling health checks](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/health-checks-disable.html)
- [Amazon Route 53 - HealthCheckConfig API](https://docs.aws.amazon.com/Route53/latest/APIReference/API_HealthCheckConfig.html)
- [Amazon Route 53 Application Recovery Controller - Recovery controls](https://docs.aws.amazon.com/r53recovery/latest/dg/what-is-route53-recovery.html)
- [Amazon Route 53 Application Recovery Controller - Zonal shift](https://docs.aws.amazon.com/r53recovery/latest/dg/arc-zonal-shift.html)
- [Amazon Route 53 Application Recovery Controller - Zonal autoshift](https://docs.aws.amazon.com/r53recovery/latest/dg/arc-zonal-autoshift.html)
- [Amazon EC2 - Automatic recovery](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-instance-recover.html)
- [Amazon EC2 - Configure simplified automatic recovery](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/instance-configuration-recovery.html)
- [Amazon EC2 Auto Scaling - Lifecycle hooks](https://docs.aws.amazon.com/autoscaling/ec2/userguide/lifecycle-hooks.html)
- [Elastic Load Balancing - Application Load Balancer health checks](https://docs.aws.amazon.com/elasticloadbalancing/latest/application/load-balancer-health-checks.html)
- [AWS Service Quotas - Getting started](https://docs.aws.amazon.com/servicequotas/latest/userguide/intro.html)
- [AWS Fault Injection Service - What is FIS?](https://docs.aws.amazon.com/fis/latest/userguide/what-is.html)
- [AWS Resilience Hub - What is Resilience Hub?](https://docs.aws.amazon.com/resilience-hub/latest/userguide/what-is.html)
- [Amazon Route 53 - DNS limitations](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/DNSLimitations.html)
- [Elastic Load Balancing - Target group health checks](https://docs.aws.amazon.com/elasticloadbalancing/latest/application/target-group-health-checks.html)
- [Amazon EBS - Snapshot lifecycle](https://docs.aws.amazon.com/ebs/latest/userguide/snapshot-lifecycle.html)
- [AWS Fault Injection Service - Actions reference](https://docs.aws.amazon.com/fis/latest/userguide/fis-actions-reference.html)
- [Amazon ECR - Private registry replication](https://docs.aws.amazon.com/AmazonECR/latest/userguide/replication.html)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
