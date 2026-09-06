---
title: "SAP-C02 박살내기 7 - 데이터 계층 선택"
author: kkamji
categories: [Certification, AWS SAP-C02]
tags: [aws, sap-c02, certification, rds, aurora, dynamodb, elasticache, s3, ebs, efs, fsx, caching]
comments: true
image:
  path: /assets/img/aws/aws.webp
date: 2026-08-29 10:00:00 +0900
---

운영 중인 DynamoDB 테이블에 새 조회 패턴이 생겨서 global secondary index를 붙였습니다. 담당자가 상태를 바꾼 직후 같은 화면을 다시 열면 이전 값이 보인다는 제보가 들어와서 `Query`에 `ConsistentRead`를 `true`로 넣었더니, 이번에는 응답이 오지 않고 요청이 유효성 검사에서 거부됩니다.

GSI는 eventually consistent 읽기만 지원하고 `ConsistentRead`를 받지 않습니다. 필요한 것은 local secondary index인데, LSI는 `CreateTable` 시점에만 정의할 수 있어서 이미 운영 중인 테이블에는 붙지 않습니다. 남는 경로는 LSI를 포함한 새 테이블을 만들고 데이터를 이관하는 것뿐입니다. 인덱스를 하나 더 만드는 작업으로 보였던 요청이 테이블 재설계로 바뀝니다.

SAP-C02 Domain 2가 데이터 계층에서 내는 문항이 이런 모양입니다. 지문은 요구사항을 액세스 패턴과 일관성 수준과 비용 조건으로 적어 두고, 선지 네 개는 그럴듯한 서비스 이름을 하나씩 답니다. 답을 가르는 것은 서비스 이름이 아니라 그 서비스가 **할 수 없는** 일입니다. LSI는 나중에 못 붙이고, EBS Multi-Attach는 AZ를 못 넘고, Glacier Deep Archive는 Expedited 복원을 못 받고, Memcached는 failover를 못 합니다. 이 글은 그 제약들을 모아 놓은 목록입니다.

> **TL;DR**  
> - gp3는 볼륨 크기와 무관하게 최대 80,000 IOPS와 2,000 MiB/s를 낸다. 16,000 IOPS는 gp2의 값이고, 이 둘을 섞으면 io 계열을 과잉 선택하게 된다.  
> - EBS Multi-Attach는 io1과 io2 전용이고 같은 AZ의 Nitro 인스턴스 최대 16대다. 부팅 볼륨으로 못 쓰고 clustered file system이 필요하며 I/O fencing은 io2만 지원한다.  
> - EFS Archive 스토리지 클래스는 Elastic throughput에서만 동작한다. Archive lifecycle 정책이 걸려 있으면 Bursting이나 Provisioned로 바꿀 수 없다.  
> - S3 최소 저장 기간은 Standard-IA와 One Zone-IA 30일, Glacier Instant Retrieval과 Flexible Retrieval 90일, Deep Archive 180일이다. 2024년 9월부터 128 KB 미만 객체는 기본 동작에서 전환되지 않는다.  
> - lifecycle 전환은 단방향이다. Deep Archive에서 나오는 lifecycle 경로는 없고 `RestoreObject` 후 copy로 덮어써야 한다.  
> - live replication은 규칙 설정 이후 객체만 복제한다. 기존 객체와 복제본의 복제는 S3 Batch Replication만 처리하고 여기에는 RTC의 15분 SLA가 적용되지 않는다.  
> - RDS Multi-AZ DB instance의 standby는 읽기를 받지 못한다. 읽기 가능한 대기 노드는 Multi-AZ DB cluster이고, NVMe 로컬 스토리지 계열 인스턴스만 지원한다.  
> - RDS 암호화는 생성 시점에만 켠다. 미암호화 인스턴스의 암호화 read replica도, 그 반대 조합도 만들 수 없다.  
> - Aurora Global Database의 switchover는 RPO 0이고 failover는 비영값이다. secondary 클러스터에는 Aurora Auto Scaling과 Backtrack이 지원되지 않는다.  
> - LSI는 `CreateTable` 시점에만 만들고 strongly consistent read가 가능하다. GSI는 나중에 추가할 수 있고 eventually consistent만 지원한다.  
> - DAX는 eventually consistent 읽기를 가속한다. strongly consistent read는 DynamoDB로 그대로 통과하고 캐시되지 않는다.  
> - Memcached에는 복제도 자동 failover도 노드 기반 백업도 없다. 세션 스토어와 pub/sub과 복합 자료구조는 Valkey나 Redis OSS다.  
{: .prompt-info}

---

## 1. 액세스 패턴에서 데이터스토어로 가는 길

purpose-built 데이터스토어를 고르는 문항은 지문 앞부분에 답의 절반을 깔아 둡니다. 데이터가 어떤 단위로 읽히는지, 일관성이 얼마나 필요한지, 여러 인스턴스가 동시에 붙는지가 그것입니다.

{% include diagrams/static/sap-c02/data-store-access-pattern-matrix.html %}

그림은 한쪽에 지문에서 만나는 액세스 패턴을, 다른 쪽에 그 패턴이 지목하는 서비스를 두고 여덟 쌍을 나란히 놓은 것입니다. 각 상자의 부제에는 그 선택을 성립시키거나 무너뜨리는 제약이 적혀 있습니다. 패턴만 읽으면 어느 쌍이든 그럴듯해 보이고, 부제까지 읽어야 선지가 걸러집니다.

| 지문에 나오는 표현 | 지목하는 계층 | 확인해야 할 제약 |
| :--- | :--- | :--- |
| 키 하나로 아이템을 조회한다, 스키마가 유동적이다 | DynamoDB | 아이템 400 KB, `Query`와 `Scan` 결과 1 MB, 일관성 요구가 있으면 인덱스 종류가 갈린다 |
| 마이크로초 지연, 소수 아이템에 읽기 집중 | DAX | eventually consistent 읽기만 가속한다 |
| 세션 스토어, 리더보드, pub/sub | ElastiCache Valkey 또는 Redis OSS | Memcached에는 복제와 failover가 없다 |
| 관계형 스키마와 조인, 읽기 확장, 빠른 failover | Aurora | reader 최대 15개, Global Database의 secondary는 읽기 전용 |
| 관계형이면서 엔진을 그대로 유지 | RDS | 대기 노드에 읽기가 필요하면 Multi-AZ DB cluster |
| 여러 AZ의 Linux 인스턴스가 같은 디렉터리를 쓴다 | EFS | throughput mode와 스토리지 클래스가 서로를 제약한다 |
| Windows ACL과 도메인 인증이 필요한 파일 공유 | FSx for Windows File Server | 생성 시 Active Directory 조인이 필수다 |
| S3 데이터셋을 파일로 읽는 HPC와 ML 학습 | FSx for Lustre | scratch는 장애 시 데이터가 남지 않는다 |
| 인스턴스 하나가 붙는 블록 I/O, IOPS 수치 요구 | EBS | gp3의 상한을 먼저 확인한다 |
| 객체 보관, 접근 빈도가 시간에 따라 떨어진다 | S3 | 최소 저장 기간과 최소 과금 크기가 비용을 뒤집는다 |

지문에 두 가지가 함께 적혀 있으면 더 좁은 쪽이 이깁니다. "여러 인스턴스가 같은 데이터를 쓰면서 표준 POSIX 인터페이스를 쓴다"에서 답을 가르는 것은 뒤의 조건입니다. 앞의 조건만 보면 EBS Multi-Attach도 후보에 남지만, clustered file system을 도입할 수 없다는 문장이 하나 붙는 순간 탈락합니다.

---

## 2. EBS 볼륨 타입 여섯 종이 각각 답이 되는 조건

볼륨 타입 문항은 지문에 IOPS와 처리량 수치가 그대로 나옵니다. 그 수치를 상한과 대조하면 후보가 두 개로 줄고, 남은 두 개는 비용으로 갈립니다.

| 타입 | 크기 | 최대 IOPS | 최대 처리량 | 답이 되는 조건 |
| :--- | :--- | :--- | :--- | :--- |
| gp3 | 1 GiB - 64 TiB | 80,000 | 2,000 MiB/s | 크기와 무관하게 IOPS와 처리량을 따로 프로비저닝한다. 대부분의 범용 워크로드 |
| gp2 | 1 GiB - 16 TiB | 16,000 | 250 MiB/s | 크기에 비례해 성능이 정해진다. 신규 설계에서 고를 이유가 없다 |
| io1 | 4 GiB - 16 TiB | 64,000 | 1,000 MiB/s | Multi-Attach가 필요한데 io2를 쓸 수 없는 리전 |
| io2 Block Express | 4 GiB - 64 TiB | 256,000 | 4,000 MiB/s | 80,000 IOPS 초과, 2,000 MiB/s 초과, 99.999% 내구성, 500 microseconds 미만 일관 지연, NVMe reservations |
| st1 | 125 GiB - 16 TiB | 500 | 500 MiB/s | 대용량 순차 읽기. 부팅 볼륨 불가 |
| sc1 | 125 GiB - 16 TiB | 250 | 250 MiB/s | 접근 빈도가 낮은 대용량 콜드 데이터. 부팅 볼륨 불가 |

가장 자주 갈리는 지점은 gp3와 io 계열의 경계입니다. **gp3의 상한이 80,000 IOPS와 2,000 MiB/s라는 사실이 답을 뒤집습니다.** 지문이 45,000 IOPS와 900 MiB/s를 요구하면 gp3 하나로 끝나고, 여기서 io2 Block Express를 고르면 요구를 충족하되 비용이 더 드는 오답이 됩니다. `MOST cost-effective`가 붙은 문항에서 이 차이가 정답과 오답을 만듭니다.

io2 Block Express를 골라야 하는 조건은 좁습니다. 위 표의 다섯 가지 중 하나가 지문에 명시적으로 적혀 있을 때입니다. 내구성 99.999%는 연간 실패율 0.001%를 뜻하고, 다른 볼륨 타입의 99.8-99.9%와 자릿수가 다릅니다. 16 KiB I/O 기준 평균 지연 500 microseconds 미만도 io2 Block Express의 설계값입니다.

인스턴스 쪽 제약도 함께 걸립니다. **256,000 IOPS는 Nitro 인스턴스에서만 나옵니다.** 비Nitro 인스턴스는 최대 64,000 IOPS 볼륨을 붙일 수는 있으나 실제로는 32,000 IOPS까지만 냅니다. 지문이 인스턴스 세대를 명시하지 않은 채 고성능 볼륨을 요구하면 인스턴스 교체가 함께 필요한 선지를 봐야 합니다.

io1의 1,000 MiB/s도 조건부입니다. 64,000 IOPS를 프로비저닝하고 Nitro 인스턴스에 붙였을 때 도달하는 값이라, 처리량만 필요해서 io1을 고르면 쓰지 않는 IOPS 비용을 함께 냅니다.

---

## 3. Multi-Attach가 성립하는 좁은 조건

같은 볼륨을 여러 인스턴스가 동시에 붙는 구성은 조건이 아주 좁습니다. 공유 스토리지가 필요한 문항에서 Multi-Attach 선지는 대부분 이 조건 중 하나에 걸려 탈락합니다.

{% include diagrams/static/sap-c02/shared-storage-az-boundary.html %}

그림은 AZ 두 개를 상자로 나누고, 한쪽 AZ 안에만 존재하는 io2 Multi-Attach 볼륨과 두 AZ 모두에서 마운트할 수 있는 Regional EFS를 함께 그린 것입니다. 각 상자의 부제에 Multi-Attach의 상한과 EFS의 접근 범위가 적혀 있습니다.

Multi-Attach의 조건을 모으면 이렇습니다.

- **볼륨 타입은 io1과 io2뿐이다.** gp3와 gp2는 Multi-Attach를 지원하지 않는다.
- **같은 AZ의 인스턴스만 붙는다.** AZ를 넘는 공유는 성립하지 않는다.
- **Nitro 인스턴스 최대 16개다.**
- **부팅 볼륨으로 쓸 수 없고 인스턴스당 block device mapping은 1개다.**
- **인스턴스 시작 시점에는 활성화할 수 없다.**
- **clustered file system이 필요하다.** XFS나 EXT4 같은 표준 파일시스템은 다중 서버 동시 접근용으로 설계되지 않았다.
- **I/O fencing(NVMe reservations)은 io2만 지원한다.** io1에는 없다.

리전 제약도 붙습니다. io1 Multi-Attach는 us-east-1, us-west-2, ap-northeast-2 세 리전에서만 쓸 수 있고, io2는 io2를 지원하는 전 리전에서 됩니다. Windows 인스턴스는 io2 Multi-Attach만 지원합니다.

그래서 "두 AZ에 걸친 인스턴스 120대가 같은 디렉터리를 읽고 쓴다"는 지문에서 Multi-Attach는 세 번 탈락합니다. AZ를 넘고, 16대를 넘고, 클러스터 파일시스템 도입 인력이 없다는 조건까지 걸립니다. 남는 답은 EFS입니다.

---

## 4. 스냅샷과 Amazon Data Lifecycle Manager

EBS 스냅샷은 증분 백업이고 S3에 저장되지만 S3 콘솔이나 API로 직접 접근할 수 없습니다. 스냅샷 데이터는 리전 안의 모든 AZ에 자동으로 복제되므로 스냅샷 자체가 AZ 장애에 대한 복구 수단이 됩니다.

Amazon Data Lifecycle Manager는 EBS 스냅샷과 EBS 기반 AMI의 생성, 보존, 삭제를 자동화합니다. 확인해야 할 성질은 세 가지입니다.

- **다른 수단으로 만든 스냅샷과 AMI는 관리하지 않는다.** 콘솔이나 스크립트로 직접 만든 스냅샷에는 DLM 정책이 적용되지 않는다.
- **instance store 기반 AMI의 생성과 보존과 삭제는 자동화하지 않는다.**
- **추가 요금이 없다.** EventBridge, CloudTrail과 결합해 백업 체계를 구성한다.

쿼터는 리전당 custom lifecycle policy 100개, EBS 스냅샷 기본 정책 1개, EBS 기반 AMI 기본 정책 1개, 리소스당 태그 45개입니다.

AWS Backup과의 역할 분담이 문항으로 나옵니다. **DLM이 다루는 대상은 EBS 스냅샷과 EBS 기반 AMI로 한정됩니다.** 지문에 RDS나 DynamoDB나 EFS가 함께 나와 하나의 백업 정책으로 묶어야 하면 DLM 선지는 대상 범위에서 걸립니다.

---

## 5. EBS 암호화는 생성 시점에만 결정된다

EBS 암호화는 계정 단위 리전별 설정으로 기본값을 켤 수 있습니다. 켜면 그 리전에서 새로 만드는 볼륨이 자동으로 암호화됩니다. 답을 가르는 것은 그다음 문장들입니다.

- **기존 미암호화 볼륨을 직접 암호화할 수 없다.** 스냅샷을 뜬 뒤 암호화 볼륨으로 생성하는 경로만 유효하다.
- **기존 미암호화 스냅샷도 직접 암호화할 수 없다.** 암호화 복사본을 만든다.
- **암호화를 되돌릴 수 없다.**
- **기존 볼륨과 스냅샷의 KMS 키를 바꿀 수 없다.** 다른 키를 지정하는 시점은 스냅샷을 복사할 때뿐이다.
- **암호화 볼륨의 public snapshot은 지원되지 않는다.** 특정 계정 공유만 가능하다.
- **모든 EC2 인스턴스 타입이 지원한다.** 인스턴스 타입 때문에 암호화를 못 쓰는 경우는 없다.

암호화 범위는 저장 데이터와, 인스턴스에서 볼륨으로 가는 구간의 전송 데이터를 함께 덮습니다. "전송 구간 암호화를 위해 별도 설정이 필요하다"는 선지는 성립하지 않습니다.

이 규칙은 RDS에서 그대로 반복됩니다. 저장 암호화를 나중에 켜는 시나리오는 EBS든 RDS든 스냅샷 경유가 유일한 답입니다.

---

## 6. EFS 성능 모드와 throughput 모드가 서로를 막는다

EFS는 파일시스템 타입(Regional, One Zone), 성능 모드(General Purpose, Max I/O), throughput 모드(Elastic, Provisioned, Bursting), 스토리지 클래스(Standard, IA, Archive)라는 네 축을 갖고 있고 이 축들이 서로를 제약합니다. 문항은 그 조합 중 성립하지 않는 것을 선지에 넣습니다.

성능 수치부터 정리합니다.

| 항목 | 값 |
| :--- | :--- |
| Regional과 Elastic 조합의 읽기 지연 | 약 1 ms |
| Regional과 Elastic 조합의 쓰기 지연 | 약 2.7 ms |
| 파일시스템당 읽기 처리량 | 20-60 GiBps |
| 파일시스템당 쓰기 처리량 | 1-5 GiBps |
| 클라이언트당 읽기와 쓰기 합산 | 1,500 MiBps. amazon-efs-utils 또는 EFS CSI Driver 2.0 이상에서만 나오고 그 외에는 500 MiBps |
| Provisioned throughput IOPS | 읽기 55,000, 쓰기 25,000 |
| Bursting throughput IOPS | 읽기 35,000, 쓰기 7,000 |
| One Zone IOPS | throughput mode와 무관하게 읽기 35,000, 쓰기 7,000 |

Bursting 모드의 기준 처리량은 Standard 클래스 저장량에 비례합니다. GiB당 50 KiBps가 기준이고, 크레딧이 있으면 TiB당 100 MiBps(최소 100 MiBps)까지 버스트하며, 크레딧이 없으면 TiB당 50 MiBps(최소 1 MiBps)로 떨어집니다. 읽기는 쓰기의 3분의 1 비율로 계량되므로 읽기 중심 워크로드는 같은 크레딧으로 더 오래 버팁니다.

성립하지 않는 조합이 여기서 나옵니다.

- **Max I/O는 previous generation이다.** 작업당 지연이 더 크고, One Zone 파일시스템과 Elastic throughput에서는 지원되지 않는다. "대규모 병렬 워크로드니까 Max I/O"는 현재 문서 기준으로 성능을 올리는 선택이 아니다.
- **Provisioned로 전환하거나 프로비저닝 양을 바꾸면 24시간 잠금이 걸린다.** 그동안 Elastic이나 Bursting으로 되돌릴 수 없고 감액도 못 한다.
- **Archive 스토리지 클래스는 Elastic throughput에서만 지원된다.** Archive로 전환하는 lifecycle 정책이 걸려 있으면 throughput mode를 Bursting이나 Provisioned로 바꿀 수 없다.

내구성은 Regional과 One Zone 모두 설계값 99.999999999%로 같고 가용성이 갈립니다. Regional은 99.99%이고 One Zone은 그보다 낮은 SLA를 가지며, 무엇보다 One Zone은 AZ 손실에 견디지 못합니다. 연구 데이터나 원본 자산을 One Zone에 두는 선지는 이 지점에서 걸립니다. EFS replication은 RPO와 RTO를 분 단위로 설계한 기능입니다.

---

## 7. EFS lifecycle이 파일을 옮기는 규칙과 옮기지 않는 것

EFS lifecycle의 기본값은 Standard에서 30일 미접근 시 IA, 90일 미접근 시 Archive입니다. 반대 방향인 Transition into Standard의 기본값은 되돌리지 않음이고, 필요하면 `On first access`를 선택합니다.

| 클래스 | 최소 과금 단위 | 최소 저장 기간 | 비고 |
| :--- | :--- | :--- | :--- |
| Standard | 없음 | 없음 | 메타데이터는 항상 여기에 남는다 |
| IA | 파일당 128 KiB | 없음 | 30일 미접근이 기본 전환 조건 |
| Archive | 파일당 128 KiB | 90일 | Elastic throughput 전용, 가용성 SLA Regional 99.9% |

동작에서 놓치기 쉬운 것이 세 가지입니다.

- **IA와 Archive 파일에 대한 쓰기는 먼저 Standard에 기록된다.** 그 파일은 24시간이 지나야 다시 전환 대상이 된다.
- **파일명과 디렉터리 구조 같은 메타데이터는 항상 Standard에 남는다.** 그래서 IA로 다 내려도 메타데이터 몫의 Standard 과금은 남는다.
- **디렉터리 조회 같은 메타데이터 연산은 파일 접근으로 계산되지 않는다.** `ls`를 돌린다고 콜드 파일이 Standard로 돌아오지 않는다.

파일당 최소 과금 단위 128 KiB는 작은 파일이 많은 파일시스템에서 IA 전환의 효과를 지웁니다. 로그 조각이나 썸네일처럼 수 KB 파일이 수백만 개인 경우 IA로 내려도 128 KiB씩 과금되므로 오히려 비싸질 수 있습니다.

---

## 8. FSx 네 제품이 프로토콜과 데이터 리포지토리로 갈린다

FSx 문항은 프로토콜과 클라이언트 OS를 먼저 봅니다. 그 두 가지로 후보가 하나나 둘로 줄고, 남으면 데이터 리포지토리 연동 여부로 갈립니다.

| 제품 | 프로토콜 | 전제 조건 | 특징 |
| :--- | :--- | :--- | :--- |
| FSx for Windows File Server | SMB 2.0-3.1.1 | 생성 시 Microsoft Active Directory 조인 필수 | Single-AZ와 Multi-AZ. SSD와 HDD에서 스토리지 용량, SSD IOPS, throughput capacity를 각각 독립 프로비저닝 |
| FSx for Lustre | POSIX 병렬 파일시스템 | 없음 | S3 버킷을 데이터 리포지토리로 연결하면 객체가 파일로 보인다. 생성 시점에 파일 목록을 임포트 |
| FSx for NetApp ONTAP | NFS, SMB, iSCSI, NVMe | 없음 | 다중 프로토콜 동시 접근, 자동 데이터 티어링, 압축과 중복 제거, SnapMirror 복제, SnapLock WORM |
| FSx for OpenZFS | NFS v3, v4.0, v4.1, v4.2 | 없음 | 스냅샷과 데이터 클로닝, Multi-AZ(HA)와 Single-AZ(HA)와 Single-AZ(non-HA) |

지문에서 다음 표현을 만나면 후보가 바로 좁혀집니다.

- **Windows ACL, 도메인 인증, 기존 SMB 공유 이전:** FSx for Windows File Server. Active Directory 운영 부담이 함께 온다는 점이 오답 유도에 쓰인다.
- **HPC, ML 학습, S3에 있는 데이터셋을 파일로 읽어야 함:** FSx for Lustre.
- **Linux와 Windows 클라이언트가 같은 데이터를 각자의 프로토콜로 봐야 함:** FSx for NetApp ONTAP. 다중 프로토콜 접근을 하는 제품은 여기뿐이다.
- **온프레미스 ZFS 파일 서버 이전, 애플리케이션 코드 변경 없이:** FSx for OpenZFS.

Lustre의 배포 타입 선택도 문항이 됩니다. **scratch 파일시스템은 데이터를 복제하지 않고 파일 서버 장애 시 데이터가 남지 않습니다.** persistent는 복제하고 장애 서버를 교체합니다. 지문에 장기 보관이나 장애 후 데이터 유지가 있으면 scratch는 탈락하고, 재생성 가능한 중간 처리 데이터라고 명시되면 scratch가 답이 됩니다.

Lustre 스토리지 클래스는 SSD, Intelligent-Tiering, HDD 세 가지이고, HDD는 선택적으로 HDD 용량의 20% 크기 SSD read cache를 붙일 수 있습니다.

FSx for OpenZFS의 가용성 계층은 복구 시간이 서로 다릅니다. Multi-AZ(HA)와 Single-AZ(HA)는 failover가 통상 60초 안에 끝나고, Single-AZ(non-HA)는 자가 복구가 통상 30분 걸립니다. 이 차이가 RTO 요구가 붙은 지문에서 답을 가릅니다.

---

## 9. S3 스토리지 클래스는 최소 조건 두 개로 구분한다

스토리지 클래스 문항의 비용 계산은 단가가 아니라 최소 저장 기간과 최소 과금 객체 크기에서 뒤집힙니다.

| 클래스 | 설계 가용성 | 최소 저장 기간 | 최소 과금 객체 크기 | AZ |
| :--- | :--- | :--- | :--- | :--- |
| S3 Standard | 99.99% | 없음 | 없음 | 다중 |
| S3 Intelligent-Tiering | 99.9% | 없음 | 없음 | 다중 |
| S3 Standard-IA | 99.9% | 30일 | 128 KB | 다중 |
| S3 One Zone-IA | 99.5% | 30일 | 128 KB | 단일 |
| S3 Express One Zone | 99.95% | 없음 | 없음 | 단일 |
| S3 Glacier Instant Retrieval | 99.9% | 90일 | 128 KB | 다중 |
| S3 Glacier Flexible Retrieval | 복원 후 99.99% | 90일 | 없음 | 다중 |
| S3 Glacier Deep Archive | 복원 후 99.99% | 180일 | 없음 | 다중 |

단일 AZ인 클래스는 One Zone-IA와 Express One Zone 둘뿐입니다. 나머지는 모두 다중 AZ에 저장됩니다.

Intelligent-Tiering은 검색 요금이 없고 최소 저장 기간이 없는 대신 객체당 모니터링 요금이 붙습니다. 자동 계층 이동은 30일 미접근 시 Infrequent Access, 90일 미접근 시 Archive Instant Access입니다. 그 아래 Archive Access(90일 이상)와 Deep Archive Access(180일 이상)는 선택형이고 `RestoreObject`가 필요합니다. **128 KB 미만 객체는 모니터링 대상이 아니고 항상 Frequent Access 티어에 남습니다.**

여기서 답이 갈리는 짝이 두 개 나옵니다.

**Standard-IA와 Glacier Instant Retrieval.** 둘 다 밀리초 액세스이고 최소 과금 객체 크기도 128 KB로 같습니다. 차이는 최소 저장 기간 30일 대 90일과, 접근 빈도 설계 기준 월 1회 대 분기 1회입니다. 지문이 "밀리초 응답이 필요하지만 분기에 한 번 정도만 조회한다"라고 적으면 Glacier Instant Retrieval이 답입니다.

**Intelligent-Tiering과 lifecycle 규칙.** Intelligent-Tiering은 액세스 패턴을 모를 때의 선택입니다. 지문이 30일까지 자주 열리고 이후에는 분기 1회라고 패턴을 명시하면 그 패턴에 맞춘 lifecycle 전환이 더 쌉니다. 이때 Intelligent-Tiering을 고르면 모니터링 요금이 추가되고, 자동 계층만으로는 Deep Archive까지 내려가지 않아 장기 보관 비용도 최적이 아닙니다.

Glacier Flexible Retrieval과 Deep Archive에는 객체당 메타데이터 40 KB가 추가 과금됩니다. 8 KB는 S3 Standard 요율로, 32 KB는 해당 Glacier 요율로 계산되므로 작은 객체를 대량으로 아카이브하면 계산이 어긋납니다.

---

## 10. lifecycle 전환은 단방향이고 되돌리는 경로가 따로 있다

lifecycle 규칙은 waterfall 모델입니다. 위에서 아래로만 흐르고 거슬러 올라가지 않습니다.

{% include diagrams/static/sap-c02/s3-lifecycle-waterfall.html %}

그림은 lifecycle 규칙에서 시작해 S3 Standard부터 Glacier Deep Archive까지 이어지는 전환 사슬과, 그 사슬을 벗어나는 별도 경로를 함께 그린 것입니다. 각 클래스 상자의 부제에 최소 저장 기간이 적혀 있고, 사슬 밖의 상자에는 상위 클래스로 되돌릴 때 쓰는 수단이 적혀 있습니다.

규칙을 쓸 때 걸리는 제약이 네 가지입니다.

1. **Glacier Flexible Retrieval에서는 Deep Archive로만 전환할 수 있다.** 다른 클래스로 가는 lifecycle 경로가 없다.
2. **Deep Archive는 lifecycle로 어떤 클래스로도 나가지 못한다.** 되돌리려면 `RestoreObject`로 복원한 뒤 copy로 덮어써야 한다.
3. **최소 저장 기간을 위반하는 연쇄 전환은 규칙 하나로 쓸 수 없다.** 공식 문서 예시는 4일에 Glacier Instant Retrieval(최소 90일)로 보내면 Deep Archive 전환은 최소 94일 이후여야 한다고 적는다.
4. **2024년 9월부터 lifecycle 기본 동작은 128 KB 미만 객체를 어떤 클래스로도 전환하지 않는다.** 전환하려면 `ObjectSizeGreaterThan` 같은 object size filter를 명시하거나 `x-amz-transition-default-minimum-object-size` 헤더를 쓴다.

세 번째 항목이 문항에서 자주 나옵니다. "업로드 7일 뒤 Standard-IA로 내려 비용을 줄인다"는 선지는 Standard-IA의 최소 저장 기간 30일에 걸려 잔여 기간이 과금되므로 절감 효과가 사라집니다. 30일에 Glacier Instant Retrieval로 내리고 365일에 Deep Archive로 보내는 조합은 그 사이가 335일이라 90일 조건을 넘겨 정상 동작합니다.

---

## 11. Glacier 복원 옵션 세 가지와 걸리는 시간

아카이브 클래스의 데이터는 복원 요청 후 사용할 수 있습니다. 복원 옵션과 클래스 조합에서 성립하지 않는 것이 답을 가릅니다.

| 옵션 | Glacier Flexible Retrieval | Glacier Deep Archive |
| :--- | :--- | :--- |
| Expedited | 250 MB 미만 객체 1-5분 | **제공되지 않는다** |
| Standard | 3-5시간 | 12시간 이내 |
| Bulk | 5-12시간 | 48시간 이내 |

**Expedited는 Deep Archive에 제공되지 않습니다.** "Deep Archive 객체를 Expedited로 5분 안에 꺼낸다"는 선지는 이 한 줄로 탈락합니다. Deep Archive에서 가장 빠른 경로는 Standard의 12시간이고, 그래서 지문이 몇 시간 안의 복원을 요구하면 Deep Archive 자체가 답에서 빠집니다.

Expedited 요청이 급증하는 상황에 대비하려면 provisioned capacity를 삽니다. 1 단위가 5분마다 최소 3건의 Expedited 복원과 최대 300 MB/s 처리량을 보장합니다.

대규모 복원에는 계정 단위 상한도 걸립니다. 하루 1-2 PB 처리량 상한이 있고 restore 요청은 초당 1,000건입니다. 페타바이트 규모 복원이 필요한 지문에서 이 상한이 일정 계산의 입력값이 됩니다.

---

## 12. S3 기준 성능은 prefix 단위이고 업로드 경계는 파트 수다

S3 성능 문항은 두 가지 오해를 노립니다. 버킷 단위로 성능이 정해진다는 오해와, 객체 크기 상한이 5 GB라는 오해입니다.

기준 성능은 **partitioned prefix당 최소 초당 3,500 PUT/COPY/POST/DELETE와 5,500 GET/HEAD**입니다. **prefix 수에는 제한이 없습니다.** prefix 10개를 병렬로 쓰면 초당 55,000 읽기까지 확장됩니다. 그래서 "S3 성능이 부족하니 버킷을 여러 개로 나눈다"는 선지는 확장 단위를 잘못 짚은 것이고, 같은 버킷 안에서 prefix를 늘리는 쪽이 답입니다. 확장이 진행되는 동안에는 503 Slow Down이 나올 수 있습니다. 소형 객체의 첫 바이트 지연은 대략 100-200 ms입니다.

업로드 경계는 이렇습니다.

| 항목 | 값 |
| :--- | :--- |
| 단일 `PUT` 최대 크기 | 5 GB |
| 콘솔 업로드 최대 크기 | 160 GB |
| 멀티파트 파트 번호 | 1-10,000 |
| 파트 크기 | 5 MiB-5 GiB. 마지막 파트는 하한 없음 |
| 최대 객체 크기 | 문서 표기가 48.8 TiB와 50 TB로 갈린다 |

실제로 걸리는 경계는 단일 `PUT`의 5 GB와 파트 10,000개입니다. 최대 객체 크기는 문서 페이지마다 표기가 달라 답의 근거로 삼지 않습니다. 객체가 100 MB에 이르면 멀티파트를 쓰라는 것이 문서 권고이고, 불안정한 네트워크에서는 실패한 파트만 다시 올릴 수 있다는 점이 선택 근거가 됩니다.

멀티파트에는 비용 함정이 따라옵니다. **완료되지 않은 멀티파트 업로드의 파트는 스토리지 요금이 계속 나갑니다.** 그래서 멀티파트를 쓰는 설계에는 미완료 업로드를 정리하는 lifecycle abort 규칙이 항상 붙습니다.

---

## 13. 복제가 대상으로 삼지 않는 객체

복제 문항은 대부분 "복제되지 않는 것"을 묻습니다. 규칙을 켠 시점이 경계이고, 그 경계 밖의 객체를 옮기는 수단은 따로 있습니다.

{% include diagrams/static/sap-c02/s3-replication-scope.html %}

그림은 원본 버킷과 대상 버킷 사이에 live replication과 Batch Replication 두 경로를 나란히 두고, 어느 경로로도 대상 버킷에 도달하지 않는 항목을 따로 묶은 것입니다. 각 상자의 부제에 그 경로가 다루는 객체 범위와 전제 조건이 적혀 있습니다.

전제 조건부터 봅니다.

- **원본과 대상 양쪽에 versioning이 켜져 있어야 한다.** 원본에서 versioning을 끄려면 복제 설정을 먼저 지워야 하고, 대상에서 끄면 복제가 `FAILED`가 된다.
- **원본에 Object Lock이 켜져 있으면 대상에도 켜야 한다.**
- **live replication은 설정 이전에 존재하던 객체를 복제하지 않는다.**

기존 객체 마이그레이션, 복제 실패 객체 재시도, 복제본의 복제는 **S3 Batch Replication**이 유일한 경로입니다. S3 Replication Time Control은 15분 SLA를 제공하지만 Batch Replication에는 적용되지 않습니다. SRR은 데이터 전송 요금이 없고 CRR은 리전 쌍에 따라 요금이 다릅니다.

복제되지 않는 항목 목록은 그대로 오답 선지가 됩니다.

- 다른 복제 규칙이 만든 복제본. **복제 체이닝이 되지 않는다.**
- 이미 다른 대상으로 복제된 객체
- version ID를 지정한 DELETE
- lifecycle이 수행한 액션과 그 액션이 만든 delete marker
- 버킷 레벨 서브리소스(lifecycle 설정, 알림 설정)
- Glacier Flexible Retrieval, Deep Archive, Intelligent-Tiering의 Archive Access와 Deep Archive Access 티어 객체
- 교차 계정 복제에서의 delete marker

delete marker 복제는 설정 형식에 따라 다르게 동작합니다. `Filter` 요소를 쓰는 최신 설정은 delete marker를 기본 복제하지 않고, 비태그 기반 규칙에 한해 켤 수 있습니다. `Filter`가 없는 V1 설정은 사용자 액션으로 생긴 delete marker를 복제합니다. 태그 기반 규칙은 `PutObject` 시점에 태그가 붙어 있어야 하고, 나중에 붙인 태그는 Batch Replication으로만 반영됩니다.

암호화 객체 쪽에는 오래된 자료가 만든 오해가 하나 있습니다. **현재 복제 문서는 SSE-C, SSE-S3, SSE-KMS로 암호화한 객체를 모두 기본 복제 대상으로 명시합니다.** "SSE-C 객체는 복제되지 않으니 SSE-KMS로 다시 올린다"는 서술은 현재 문서와 어긋납니다.

---

## 14. RDS 배포 세 가지가 대기 노드를 다르게 쓴다

RDS 고가용성 문항은 요구사항을 세 줄로 적어 놓고 그 셋을 동시에 만족하는 배포를 고르게 합니다. 자동 failover가 필요한지, 커밋 손실을 막아야 하는지, 대기 노드가 읽기를 받아야 하는지입니다.

{% include diagrams/static/sap-c02/rds-deployment-topologies.html %}

그림은 세 가지 배포를 각각 상자로 묶어 나란히 놓고, 각 배포의 writer와 대기 노드를 그린 것입니다. 각 노드의 부제에 복제 방식과 그 노드가 읽기를 받는지 여부, 그리고 배포마다 붙는 제약이 적혀 있습니다.

| 배포 | 복제 | 자동 failover | 대기 노드 읽기 | 제약 |
| :--- | :--- | :--- | :--- | :--- |
| Multi-AZ DB instance | 동기 | 있다 | **받지 못한다** | standby는 대기만 한다 |
| Multi-AZ DB cluster | semisynchronous | 있다 | **reader 2개가 받는다** | NVMe 로컬 스토리지 계열 인스턴스 클래스만 지원 |
| read replica | 비동기 | **없다** | 받는다 | 승격은 수동, 순환 복제 불가 |

Multi-AZ DB cluster는 writer 1개와 읽기 가능한 reader 2개를 3개 AZ에 배치하고, semisynchronous 복제로 reader 최소 1개의 확인 응답을 요구합니다. 세 요구를 동시에 충족하는 유일한 RDS 배포 형태라서 그 조합이 지문에 나오면 답이 하나로 정해집니다.

인스턴스 클래스 제약이 함께 걸립니다. Multi-AZ DB cluster가 지원하는 클래스는 db.c6gd, db.m5d, db.m6gd, db.m6id, db.m6idn, db.m8gd, db.r5d, db.r6gd, db.r6id, db.r6idn, db.r8gd, db.x2iedn입니다. medium 사이즈는 c6gd만 지원합니다. 기존 인스턴스가 NVMe 계열이 아니면 인스턴스 클래스 변경이 함께 필요합니다.

read replica의 성질도 문항에 그대로 쓰입니다.

- **비동기 복제이고 오토스케일링이 없다.** 부하에 따라 replica 수가 자동으로 늘지 않는다.
- **순환 복제를 지원하지 않는다.**
- **source DB instance를 지우면 같은 리전 replica는 standalone으로 승격된다.**
- **상한은 프라이머리당 15개다.** 조정 가능한 쿼터이고 Aurora는 조정할 수 없다. RDS for Oracle은 15개까지 만들 수 있으나 복제 지연을 줄이려면 5개로 제한하라는 것이 문서 권고다.

Multi-AZ DB cluster의 백업은 인스턴스가 아니라 클러스터 볼륨 스냅샷입니다. **그 스냅샷은 Single-AZ 배포나 Multi-AZ DB instance 배포로도 복원할 수 있습니다.** "Multi-AZ DB cluster 스냅샷은 같은 형태로만 복원된다"는 선지는 여기서 틀립니다.

flow control도 함께 알아 둘 값입니다. MySQL에서는 `rpl_semi_sync_master_target_apply_lag`가 기본 120초로 켜져 있고, PostgreSQL에서는 확장으로 배포되어 replica lag이 2분을 넘으면 커밋 끝에 지연을 넣습니다. RDS Proxy를 붙이면 minor 버전 업그레이드 다운타임이 1초 이하로 줄어듭니다.

failover 시간을 묻는 문항에는 주의가 필요합니다. 공식 문서는 Multi-AZ DB cluster의 failover 시간을 replica lag에 의존한다고만 적고 초 단위 값을 주지 않습니다. 흔히 인용되는 수치는 근거가 없습니다.

---

## 15. RDS 암호화와 read replica 조합에서 성립하지 않는 것

RDS 저장 암호화는 EBS와 같은 규칙을 따릅니다. **생성 시점에만 켤 수 있고, 켜면 끌 수 없습니다.** 미암호화 인스턴스를 암호화하려면 스냅샷을 만들고 암호화 복사본을 만든 뒤 복원해야 합니다. 미암호화 인스턴스의 암호화 스냅샷을 바로 만들 수도 없습니다.

read replica와의 조합에는 규칙이 더 붙습니다.

- **미암호화 인스턴스의 암호화 read replica를 만들 수 없고 그 반대도 안 된다.** 소스와 replica의 암호화 상태가 같아야 한다.
- **같은 리전 read replica는 소스와 같은 KMS 키를 써야 한다.**
- **다른 리전 read replica는 그 리전의 키로 암호화한다.**
- **암호화 스냅샷을 다른 리전으로 복사하려면 대상 리전 KMS 키를 지정해야 한다.**

암호화된 DB instance의 KMS 키를 비활성화하면, 백업이 켜진 인스턴스는 감지 2시간 뒤 `inaccessible-encryption-credentials-recoverable` 상태로 7일간 정지됩니다. 그 안에 키를 되살리지 못하면 `inaccessible-encryption-credentials` 종단 상태가 되고 남는 선택지는 백업 복원뿐입니다. 따라서 암호화 상태와 키 접근 권한을 함께 점검해야 합니다.

계정 쿼터도 설계 문항의 입력값이 됩니다. 기본값은 DB instance 40개(ap-south-1은 20개), Aurora DB cluster 40개, 클러스터당 custom endpoint 5개, RDS Proxy 20개, 수동 스냅샷 100개, 전체 RDS DB instance의 EBS 스토리지 합계 100,000 GB입니다. license-included SQL Server는 에디션당 10개, license-included Oracle은 10개 제한이 따로 걸립니다.

---

## 16. Aurora 클러스터 볼륨과 엔드포인트 네 종

Aurora의 스토리지는 컴퓨트와 분리되어 있고 3개 AZ에 걸쳐 다중 복제본을 유지합니다. **복제량은 DB 인스턴스 수와 무관합니다.** reader를 늘려도 스토리지 복제 부담이 늘지 않는다는 것이 read replica와의 구조적 차이입니다.

볼륨은 사용한 공간만 과금하고 데이터를 지우면 할당 공간도 줄어듭니다. 최대 크기는 문서 페이지에 따라 128 TiB와 256 TiB로 다르게 적혀 있으므로, 엔진 버전에 따라 갈린다는 선에서 이해하고 단일 수치를 답의 근거로 쓰지 않습니다.

인스턴스 구성은 writer 1개와 Aurora Replica 최대 15개입니다. replica는 읽기 전용이고 writer 장애 시 자동 failover 대상이며, replica마다 failover 우선순위를 지정할 수 있습니다. I/O는 writer와 reader를 구분하지 않고 같은 방식으로 계량됩니다.

엔드포인트는 네 종류에 Global Database용 하나가 더 있습니다.

| 엔드포인트 | 대상 | failover 시 동작 |
| :--- | :--- | :--- |
| cluster(writer) endpoint | 현재 primary 인스턴스 | 새 primary로 자동 전환된다 |
| reader endpoint | Aurora Replica 전체 | 연결을 자동 분산한다. 승격 직후 짧은 동안 새 primary로 연결이 갈 수 있다 |
| instance endpoint | 특정 인스턴스 하나 | 전환하지 않는다. 진단과 튜닝용 |
| custom endpoint | 지정한 인스턴스 집합 | 인스턴스 용량이나 설정이 다른 그룹을 나눌 때 쓴다. 클러스터당 기본 5개 |
| Global writer endpoint | 현재 primary 클러스터 | switchover와 failover 후에도 값이 유지된다 |

고가용성이 중요한 구성에서는 instance endpoint를 직접 쓰지 않습니다. **writer와 reader endpoint만 인스턴스 장애 시 연결 대상을 자동으로 바꿉니다.** "애플리케이션이 인스턴스 엔드포인트 목록을 들고 있다가 장애 시 다른 것으로 붙는다"는 설계는 그 전환 로직을 직접 만들어야 한다는 뜻이고, 선지에 나오면 관리 부담 쪽에서 걸립니다.

---

## 17. Aurora Global Database와 두 가지 승격

Aurora Global Database는 primary 1개 리전에 읽기 전용 secondary 최대 10개 리전을 붙입니다. 전용 인프라로 복제하고 지연은 통상 1초 미만입니다. secondary 클러스터는 읽기 전용이라는 이유로 reader를 예외적으로 16개까지 둘 수 있습니다.

{% include diagrams/static/sap-c02/aurora-global-switchover-failover.html %}

그림은 primary 클러스터에서 secondary 클러스터로 이어지는 복제와, secondary가 primary가 되는 두 가지 경로를 나란히 그린 것입니다. 각 경로 상자의 부제에 그 경로를 쓰는 상황과 RPO 특성이 적혀 있고, 두 경로가 공유하는 Global writer endpoint가 함께 있습니다.

두 승격의 차이가 문항의 핵심입니다.

| 항목 | switchover | managed failover |
| :--- | :--- | :--- |
| 쓰는 상황 | 모든 클러스터가 정상, 계획된 전환 | 리전 장애 대응 |
| secondary 동기화 | 기다린다 | 기다리지 않는다 |
| RPO | 0 | 초 단위 비영값 |
| RTO | 분 단위 | 분 단위 |
| write fencing | 해당 없음 | best-effort. split-brain 가능성이 남는다 |

둘 다 primary와 secondary의 major와 minor 엔진 버전이 같아야 합니다. managed failover 후 AWS는 이전 primary의 장애 시점 볼륨 스냅샷 `rds:unplanned-global-failover-...`를 남기려 시도합니다. write fencing이 best-effort이므로 DNS TTL을 5초 수준으로 낮추라는 것이 문서 권고입니다.

Aurora PostgreSQL에는 RPO 상한을 강제하는 파라미터가 있습니다. `rds.global_db_rpo`를 20초에서 2,147,483,647초 사이로 설정하면, 모든 secondary의 RPO lag이 목표를 넘는 순간 primary의 커밋이 차단됩니다. 리전이 2개인 구성에서는 기본값 유지가 권고입니다. 데이터 손실을 절대 허용할 수 없다는 요구가 있으면 이 파라미터가 답의 일부가 됩니다.

Global Database에 걸리는 제약은 그대로 오답 선지가 됩니다.

- **Backtrack을 지원하지 않는다.**
- **secondary 클러스터에 Aurora Auto Scaling이 지원되지 않는다.**
- **Secrets Manager 통합이 지원되지 않는다.**
- **global database에 속한 클러스터는 개별 stop과 start를 할 수 없다.**
- **자동 minor 버전 업그레이드가 적용되지 않는다.**

---

## 18. Aurora Serverless v2의 ACU와 그 범위를 정하는 것

Aurora Serverless v2의 용량 단위는 ACU입니다. **1 ACU는 약 2 GiB 메모리와 그에 대응하는 CPU와 네트워킹**이고, 용량 범위는 0에서 256 ACU 사이에서 0.5 단위로 조정합니다. 최소 0 ACU는 auto-pause를 지원하는 엔진 버전에서만 쓸 수 있습니다.

실제로 지정할 수 있는 범위는 엔진 버전과 platform version 중 더 낮은 쪽이 결정합니다.

| 조건 | 가능한 범위 |
| :--- | :--- |
| Aurora MySQL 3.02.0 이상 | 0.5-128 ACU |
| Aurora MySQL 3.06.0 이상 | 0.5-256 ACU |
| Aurora MySQL 3.08.0 이상 | 0-256 ACU |
| platform version 1 | 0-128 ACU |
| platform version 2 이상 | 0-256 ACU |

구성에서 걸리는 조건도 있습니다. serverless 클러스터는 `db.serverless` 인스턴스를 붙이기 전에 `ServerlessV2ScalingConfiguration` 속성이 있어야 합니다. PostgreSQL 호환에서 최소 용량을 0이나 0.5로 두면 `max_connections` 최대값이 2,000으로 제한됩니다. **Database Activity Streams, cluster cache management, Aurora Auto Scaling은 serverless에서 지원되지 않습니다.**

reader의 promotion tier가 스케일링 동작을 바꾸는 점도 알아 둘 값입니다. tier 0과 1은 최소 용량이 현재 writer 용량에 묶여 failover 대비가 되고, tier 2에서 15까지는 writer와 독립적으로 스케일합니다. writer가 커진 상태에서 failover가 나도 성능이 유지되어야 한다면 reader를 tier 0이나 1에 둡니다.

Aurora Serverless v1은 지원 종료 단계입니다. v1에서 v2로 직접 전환할 수 없고 provisioned 클러스터를 경유해야 합니다. v1을 신규 도입하는 선지는 이 경로 제약과 지원 상태에서 걸립니다.

---

## 19. Backtrack은 백업 복원이 아니고 MySQL 전용이다

Backtrack은 DB 클러스터를 지정한 시각으로 되감는 기능입니다. 새 클러스터를 만들지 않고 몇 분 안에 되감기 때문에, `WHERE` 절 없는 `DELETE` 같은 실수를 되돌리는 용도로 point-in-time restore보다 빠릅니다. 앞뒤로 반복해서 되감을 수 있어 데이터 변경 시점을 찾는 데도 씁니다.

제약이 촘촘합니다.

- **Aurora PostgreSQL에는 제공되지 않는다.** Aurora MySQL 버전 2, 3, 8.4에서만 지원한다.
- **생성 시점에 Backtrack을 켠 클러스터만 쓸 수 있다.** 운영 중인 클러스터를 modify로 켤 수 없고, 새로 만들거나 스냅샷을 복원할 때만 켠다.
- **backtrack window 상한은 72시간이다.**
- **클러스터 전체에 적용된다.** 테이블 하나나 업데이트 하나만 골라 되감을 수 없다.
- **Backtrack이 켜진 클러스터에서는 cross-Region read replica를 만들 수 없다.**
- **되감는 동안 짧은 중단이 생긴다.** Aurora가 데이터베이스를 일시 정지하고 열린 연결을 닫으며 커밋되지 않은 읽기와 쓰기를 버린다.
- **리전 가용성이 제한된다.** 지원하지 않는 리전이 있고, Backtrack이 켜진 클러스터의 교차 리전 스냅샷은 Backtrack을 지원하지 않는 리전에 복원할 수 없다.

target backtrack window와 actual backtrack window가 다르다는 점도 시험 소재입니다. 쓰기 부하가 아주 높으면 change record를 다 보관하지 못해 실제 되감을 수 있는 시간이 목표보다 짧아지고, 이때 알림이 발생합니다. "72시간을 지정했으니 항상 72시간 전으로 되감을 수 있다"는 서술은 성립하지 않습니다.

Global Database와의 조합도 앞 절에서 본 대로 성립하지 않습니다. **Global Database는 Backtrack을 지원하지 않습니다.**

---

## 20. DynamoDB 용량 단위와 두 가지 용량 모드

DynamoDB 문항은 용량 계산을 직접 시키기보다, 용량 모드의 전환 제약과 즉시 흡수 범위를 묻습니다. 계산의 기준값부터 정리합니다.

| 항목 | 값 |
| :--- | :--- |
| 1 RCU | 4 KB 이하 아이템에 대해 초당 strongly consistent read 1회 또는 eventually consistent read 2회 |
| 1 WCU | 1 KB 이하 아이템 초당 쓰기 1회 |
| 트랜잭션 읽기와 쓰기 | 각각 2배를 소비한다 |
| 아이템 최대 크기 | 400 KB. 속성 이름 바이트를 포함한다 |
| `Query`와 `Scan` 결과 | 호출당 1 MB |
| `BatchGetItem` | 100개 아이템, 16 MB |
| `BatchWriteItem` | 25개 요청, 16 MB |
| 트랜잭션 | 100개 아이템, 4 MB |

트랜잭션에는 경계 제약이 하나 더 있습니다. **여러 계정이나 리전에 걸칠 수 없고, global table 사이에서는 ACID를 보장하지 않습니다.** 멀티 리전 구성에서 트랜잭션 일관성을 요구하는 지문은 이 지점에서 답이 갈립니다.

용량 모드는 이렇게 갈립니다.

| 항목 | on-demand | provisioned |
| :--- | :--- | :--- |
| 테이블 기본 쿼터 | 40,000 RCU/WCU | 40,000 RCU/WCU |
| 계정 쿼터 | 없다 | 80,000 RCU/WCU |
| 즉시 흡수 범위 | 이전 피크의 2배 | 프로비저닝한 값 |
| 신규 테이블 초기값 | 초당 쓰기 4,000, 읽기 12,000 | 지정한 값 |
| 감액 제한 | 해당 없음 | 하루 4회로 시작해 매시간 1회씩 충전, 최대 27회 |
| 전환 제한 | provisioned로는 언제든 | on-demand로는 24시간 롤링 윈도에 4회 |

**on-demand가 무제한으로 즉시 확장된다는 서술은 틀립니다.** 즉시 수용 범위는 이전 피크의 2배이고, 그 이상을 30분 안에 요구하면 스로틀될 수 있습니다. 예측 가능한 급증이 있는 워크로드에서는 사전 웜업이나 provisioned + auto scaling이 답이 되는 경우가 있습니다.

Streams가 켜진 provisioned 테이블의 쓰기 용량 기본 상한도 40,000 WCU입니다.

---

## 21. DynamoDB Streams와 Global Tables의 복제 경계

DynamoDB Streams는 테이블의 아이템 단위 변경을 거의 실시간으로 기록합니다. 레코드는 최대 24시간 동안만 보존되며, 같은 아이템에 대한 변경은 실제 변경 순서로 나타나고 각 레코드는 스트림에 정확히 한 번 나타납니다. 며칠 뒤 재처리할 요구라면 Streams만으로는 부족하므로 Kinesis Data Streams for DynamoDB 같은 장기 보존 경로를 별도로 둡니다.

`StreamViewType`은 `KEYS_ONLY`, `NEW_IMAGE`, `OLD_IMAGE`, `NEW_AND_OLD_IMAGES` 네 가지입니다. 스트림이 만들어진 뒤에는 이 값을 수정할 수 없고, 바꾸려면 기존 스트림을 끈 뒤 새 스트림을 만들어야 합니다. 값이 실제로 바뀌지 않은 `PutItem`이나 `UpdateItem`은 변경 레코드를 만들지 않습니다. 샤드 하나를 동시에 읽는 리더는 두 개 이하로 제한하고 global table에서는 하나를 권장합니다.

### 21.1. Global Tables는 리전 간 일관성 모드로 갈린다

DynamoDB Global Tables는 여러 리전에 같은 테이블을 두고 각 replica에서 읽기와 쓰기를 수행하는 multi-active 구성입니다. 새로 고르는 일관성 모드에 따라 지연과 충돌 처리 방식이 달라집니다.

| 모드 | 복제와 읽기 | 설계 제약 |
| :--- | :--- | :--- |
| MREC | 기본 모드. 비동기 복제로 보통 1초 이내 전파하고 리전 간 읽기는 eventual consistency다. 동시 수정은 item 단위 last-writer-wins로 수렴한다 | DynamoDB가 제공되는 리전에 replica를 둘 수 있고 multi-account도 가능하다 |
| MRSC | 쓰기가 성공하기 전에 다른 리전에 동기 복제하고 replica의 strongly consistent read가 최신 값을 반환한다 | 생성 시 세 리전이 필요하다. 세 replica 또는 두 replica와 한 witness 조합이며 multi-account 구성은 지원하지 않는다 |

MREC에서 strongly consistent read를 요구하면 해당 아이템의 쓰기와 읽기를 같은 리전에서 수행해야 합니다. global table 간 트랜잭션은 리전 간 ACID를 보장하지 않으며, TTL 삭제는 원본 테이블 쓰기 단위를 쓰지 않아도 replica에는 replicated write 비용이 발생합니다. MRSC에서는 TTL을 사용할 수 없습니다. Global Table을 provisioned로 운영하려면 auto scaling을 켜야 하고, 새 replica를 추가할 때는 각 대상 리전의 처리량 쿼터가 호환되는지 확인해야 합니다.

---

## 22. DAX와 ElastiCache는 캐시 대상과 운영 모델이 다르다

DAX는 DynamoDB API와 호환되는 VPC 전용 캐시입니다. 애플리케이션은 DAX endpoint를 사용하고, DAX가 처리할 수 없는 요청은 DynamoDB로 통과시킵니다. 클러스터는 primary 한 개와 read replica 0-10개로 구성하며, 리전당 계정 전체 노드 합계는 50개, 클러스터당 접근 가능한 DynamoDB 테이블은 500개입니다.

item cache의 기본 TTL은 5분이고 `GetItem`과 `BatchGetItem` 결과를 키로 저장합니다. `Query`와 `Scan` 결과는 파라미터를 키로 하는 query cache에 저장합니다. strongly consistent read는 DynamoDB로 통과하고 캐시하지 않습니다. DAX는 반복 읽기와 eventually consistent 지연 단축에 맞고, 쓰기 집중 워크로드나 캐시 적중률이 낮은 워크로드에는 맞지 않습니다. 문서 기준으로 캐시 적중률이 90%를 넘는 조건에서 효과가 큽니다. `PutItem`, `UpdateItem`, `DeleteItem`, `BatchWriteItem`의 write-through는 DAX와 DynamoDB 양쪽 쓰기가 성공해야 완료됩니다.

ElastiCache는 DynamoDB 외의 데이터와 세션을 캐시하는 선택지입니다.

| 선택지 | 맞는 조건 | 빠지는 기능 또는 제약 |
| :--- | :--- | :--- |
| Memcached | 단순 객체 캐시, 멀티코어 노드, 노드 추가와 제거 중심의 scale-out | node-based 구성에서 복제, 자동 failover, 백업과 복원, pub/sub, sorted set, geospatial index가 없다 |
| Valkey 또는 Redis OSS, cluster mode disabled | 복합 자료구조와 복제, 백업, pub/sub가 필요하고 단일 샤드 중심으로 운영한다 | 온라인 resharding과 샤드 파티셔닝을 사용할 수 없다 |
| Valkey 또는 Redis OSS, cluster mode enabled | 샤드 파티셔닝과 온라인 resharding, 자동 failover가 필요하다 | 클라이언트가 cluster mode를 지원해야 한다 |
| ElastiCache Serverless | 용량과 트래픽이 예측하기 어렵고 노드 용량 관리를 위임한다 | Valkey와 Redis OSS는 cluster mode enabled만 지원하며 세 엔진 모두 지원 버전 조건을 확인한다 |

Serverless 캐시는 세 AZ에 데이터를 중복 저장하고 99.99% 가용성 SLA를 제공합니다. 저장과 전송 암호화가 켜진 상태로 동작하며 GB-hours와 ECPU를 기준으로 과금합니다. 예측 가능한 용량과 노드 배치 제어가 필요하거나 Valkey 9.0 이상에서 Multi-AZ transaction log durability를 선택하려면 node-based cluster가 맞습니다. 데이터 티어링은 Redis OSS 6.2 이상 node-based cluster의 r6gd에서만 지원합니다.

---

## 23. 검색과 분석을 위한 OpenSearch 선택

OpenSearch Service domain은 사용자가 instance type, node 수, 스토리지와 배치를 정하는 관리형 클러스터입니다. AWS가 장애 노드를 교체하고 자동 스냅샷과 VPC 보안 그룹을 제공하므로 로그 분석, 실시간 모니터링, clickstream 검색처럼 색인과 검색을 계속 운영해야 하는 요구에 맞습니다. Multi-AZ 배치는 같은 리전의 두 개 또는 세 개 AZ에 노드를 둡니다. S3, Kinesis, DynamoDB에서 스트리밍 데이터를 넣고 OpenSearch Dashboards와 CloudWatch로 조회와 관측을 연결할 수 있습니다. index-level, document-level, field-level 보안도 지원합니다.

OpenSearch Serverless collection은 클러스터 노드와 스토리지를 직접 프로비저닝하지 않는 on-demand 선택지입니다. 인제스트와 검색 용량을 각각 OpenSearch Compute Unit(OCU)으로 측정하고, OCU 하나는 6 GiB 메모리와 대응하는 vCPU 및 S3 전송으로 구성됩니다. 트래픽이 불규칙하고 용량 계획을 운영팀이 맡지 않아야 하면 Serverless를 고르고, 노드 타입과 샤드와 스토리지를 세밀하게 조정하거나 예측 가능한 비용을 관리해야 하면 domain을 고릅니다. OpenSearch Serverless를 선택해도 컬렉션의 인덱스 설계와 접근 정책은 별도로 관리해야 합니다.

---

## 24. 암기해야 하는 하드 리밋과 동작 제약

앞 절의 원리를 숫자와 지원 경계로 다시 대조하면 선지의 유효성을 빠르게 판정할 수 있습니다.

| 영역 | 하드 리밋 또는 동작 제약 |
| :--- | :--- |
| EBS gp3 | 1 GiB-64 TiB, 최대 80,000 IOPS와 2,000 MiB/s |
| EBS io2 Block Express | 4 GiB-64 TiB, 최대 256,000 IOPS와 4,000 MiB/s. Nitro 인스턴스 필요 |
| EBS Multi-Attach | io1과 io2만 지원, 같은 AZ의 Nitro 인스턴스 최대 16개, 부팅 볼륨 불가 |
| DLM | 리전당 custom lifecycle policy 100개, 기본 스냅샷 정책 1개와 기본 AMI 정책 1개 |
| EFS | 클라이언트당 읽기와 쓰기 합산 1,500 MiBps는 amazon-efs-utils 또는 EFS CSI Driver 2.0 이상에서만 지원 |
| EFS Archive | Elastic throughput에서만 지원. Archive lifecycle 정책이 있으면 Bursting과 Provisioned로 변경 불가 |
| S3 lifecycle | Standard-IA와 One Zone-IA 30일, Glacier Instant와 Flexible 90일, Deep Archive 180일. 128 KB 미만 객체는 기본 전환하지 않음 |
| S3 업로드 | 단일 PUT 5 GB, multipart 최대 10,000 파트, 파트 5 MiB-5 GiB |
| S3 성능 | partitioned prefix당 최소 3,500 PUT 계열과 5,500 GET 계열 per second |
| S3 Glacier | Flexible Retrieval의 250 MB 미만 객체 Expedited는 1-5분, Deep Archive에는 제공하지 않음. Deep Archive Standard는 12시간 이내 |
| DynamoDB item과 응답 | item 400 KB, `Query`와 `Scan` 결과 1 MB, 트랜잭션 100개 item과 4 MB |
| DynamoDB index | LSI 테이블당 5개와 partition key당 10 GB item collection. GSI 기본 20개이며 strongly consistent read 불가 |
| DynamoDB capacity | 테이블 기본 40,000 RCU/WCU, provisioned 계정 기본 80,000 RCU/WCU, on-demand 신규 테이블 4,000 write와 12,000 read per second |
| DynamoDB Streams | 레코드 보존 24시간, `StreamViewType` 생성 후 변경 불가, 샤드 동시 리더 최대 2개 |
| DynamoDB Global Tables | MREC는 eventual consistency와 last-writer-wins. MRSC는 세 리전 구성과 strong consistency를 사용하며 multi-account는 지원하지 않음 |
| DAX | primary 1개와 read replica 0-10개, 리전당 계정 노드 50개, 클러스터당 테이블 500개, item cache 기본 TTL 5분 |
| RDS | read replica 기본 쿼터는 primary당 15개. Multi-AZ DB instance standby는 읽기를 받지 않음 |
| Aurora | 일반 클러스터 reader 최대 15개, Global Database secondary 최대 10개 리전, Backtrack은 MySQL 계열 전용 |
| ElastiCache | Memcached node-based 구성에는 복제, 자동 failover, 백업과 복원이 없음. Serverless는 세 AZ 중복과 99.99% SLA |
| OpenSearch | domain은 2개 또는 3개 AZ 배치 가능. Serverless OCU 하나는 6 GiB 메모리와 대응 vCPU 및 S3 전송 |

---

## 25. 답이 갈리는 짝 비교

같은 요구를 만족해 보이는 서비스는 보장 범위와 변경 가능성을 나란히 놓으면 구분됩니다.

| 짝 | 차이를 만드는 제약 |
| :--- | :--- |
| gp3 대 io2 Block Express | gp3는 80,000 IOPS와 2,000 MiB/s까지 독립 설정하고, 그 이상 처리량이나 99.999% 내구성이 필요할 때 io2 Block Express를 검토 |
| EBS Multi-Attach 대 Regional EFS | Multi-Attach는 같은 AZ의 Nitro 최대 16개와 clustered file system이 필요하고, EFS는 여러 AZ의 NFS 공유를 제공 |
| S3 Standard-IA 대 Glacier Instant Retrieval | 둘 다 밀리초 접근이지만 최소 저장 기간이 30일 대 90일이고, 접근 빈도와 조기 삭제 비용이 선택을 가름 |
| S3 Intelligent-Tiering 대 lifecycle | 접근 패턴을 모르면 Intelligent-Tiering, 패턴이 예측되면 lifecycle 전환으로 모니터링 비용을 피함 |
| S3 live replication 대 Batch Replication | live는 규칙 이후 신규와 갱신 객체, Batch는 기존 객체와 복제 실패 객체 및 복제본 복제를 담당 |
| DynamoDB LSI 대 GSI | LSI는 같은 partition key와 strongly consistent read를 제공하지만 생성 시점과 10 GB item collection 제약이 있고, GSI는 운영 중 추가 가능하지만 eventual read만 지원 |
| Global Tables MREC 대 MRSC | MREC는 리전 간 비동기와 eventual read, MRSC는 세 리전 동기 복제와 strong read를 사용하며 구성 가능한 계정 모델이 다름 |
| DAX 대 ElastiCache | DAX는 DynamoDB API와 eventually consistent read cache를 제공하고, ElastiCache는 세션과 임의 데이터 구조를 cache-aside로 다룸 |
| Memcached 대 Valkey와 Redis OSS | Memcached는 단순 객체와 멀티스레드 scale-out, Valkey와 Redis OSS는 복제, failover, 백업과 복합 자료구조를 제공 |
| RDS Multi-AZ 대 read replica | Multi-AZ는 자동 failover용 대기이고 read replica는 비동기 읽기 확장과 수동 승격용 |
| OpenSearch domain 대 Serverless | domain은 노드와 샤드와 스토리지를 직접 조정하고, Serverless는 OCU 기반으로 인프라 용량을 위임 |

---

## 26. 그럴듯하지만 성립하지 않는 조합

다음 조합은 한 가지 장점만 보고 다른 제약을 놓친 선지입니다.

| 조합 | 성립하지 않는 이유 |
| :--- | :--- |
| io2 Multi-Attach 볼륨을 두 AZ의 인스턴스에 연결한다 | Multi-Attach는 같은 AZ에서만 동작하고 Nitro 인스턴스 최대 16개다 |
| EFS Archive lifecycle과 Provisioned throughput을 함께 설정한다 | Archive는 Elastic throughput 전용이고 Archive 정책이 있으면 Provisioned로 바꿀 수 없다 |
| Deep Archive 객체를 Expedited로 복원한다 | Expedited는 Glacier Flexible Retrieval 전용이다 |
| 복제 규칙을 켜면 기존 S3 객체도 자동으로 복제된다 | 규칙 이후 객체는 live replication, 기존 객체는 Batch Replication 대상이다 |
| 운영 중 DynamoDB 테이블에 LSI를 추가한다 | LSI는 `CreateTable` 시점에만 만들 수 있다 |
| GSI에 `ConsistentRead=true`를 지정한다 | GSI는 eventually consistent read만 지원한다 |
| DynamoDB Streams에서 7일 전 변경을 재생한다 | Streams 레코드는 24시간 뒤 삭제되므로 장기 재처리 경로가 아니다 |
| MREC Global Table에서 다른 리전 strong read로 즉시 최신값을 확인한다 | MREC의 리전 간 복제와 읽기는 eventual consistency다 |
| DAX로 strongly consistent read와 write-heavy 처리를 동시에 가속한다 | strongly consistent read는 DynamoDB로 통과하고, write-heavy workload는 DAX의 적합 조건이 아니다 |
| Memcached node-based cluster에 자동 failover와 백업을 기대한다 | Memcached는 복제, 자동 failover, 백업과 복원을 제공하지 않는다 |
| RDS Multi-AZ DB instance standby를 읽기 전용 endpoint로 사용한다 | standby는 대기 전용이고 읽기 확장은 read replica 또는 Multi-AZ DB cluster가 담당한다 |
| OpenSearch Serverless에서 노드 타입과 샤드를 직접 지정한다 | Serverless는 OCU 기반 on-demand 모델이고 노드 기반 조정은 domain의 책임이다 |

---

## 27. 예상 문제 10문항

**Q1.** 한 물류 회사가 운영 중인 Amazon DynamoDB 테이블은 partition key가 `customerId`, sort key가 `shipmentId`이고 데이터 양은 수억 건입니다. 새 요구사항으로 고객 상세 화면에서 그 고객의 배송 건을 배송 상태(`status`, 비키 속성)별로 조회해야 합니다. 담당자가 상태를 갱신한 직후 같은 화면을 다시 열면 반드시 갱신된 값이 보여야 합니다. Choose the solution that meets the strong consistency requirement.

- A. 기존 테이블에 `customerId`를 partition key, `status`를 sort key로 하는 local secondary index를 추가한다.
- B. 기존 테이블에 `status`를 partition key, `customerId`를 sort key로 하는 global secondary index를 추가한다.
- C. 기존 테이블에 global secondary index를 추가하고 `Query` 시 `ConsistentRead`를 `true`로 지정한다.
- D. `customerId` partition key와 `status` sort key를 갖는 local secondary index를 `CreateTable` 시점에 정의한 새 테이블을 만들고 데이터를 이관한다.

<details markdown="1">
<summary>정답과 해설</summary>

**정답: D**

strongly consistent read를 지원하는 secondary index는 LSI뿐입니다. LSI는 partition key가 base table과 같아야 하는데 이 조회는 `customerId` 하나를 고정한 뒤 `status`로 좁히는 패턴이라 제약을 만족합니다. 다만 LSI는 `CreateTable` 시점에만 정의할 수 있으므로 운영 중 테이블에는 붙일 수 없고, LSI를 포함한 새 테이블을 만들어 이관하는 경로만 남습니다.

- A가 틀린 이유: 인덱스 정의 자체는 타당하지만 LSI는 `CreateTable` 시점에만 생성됩니다. 운영 중 테이블에 나중에 추가할 수 없습니다.
- B가 틀린 이유: GSI는 eventually consistent 읽기만 지원합니다. 갱신 직후 조회에서 이전 값이 보일 수 있어 요구를 충족하지 못합니다.
- C가 틀린 이유: GSI에 대한 `Query`와 `Scan`은 `ConsistentRead`를 지원하지 않습니다. `true`로 지정하면 요청이 유효성 검사에서 거부됩니다.

</details>

**Q2.** 한 게임 회사가 플레이어 프로필을 Amazon DynamoDB에 저장합니다. 초당 수십만 건의 읽기가 몰리고 그중 95%가 같은 소수 아이템에 집중됩니다. 팀은 응답 시간을 마이크로초 수준으로 낮추려 하며, 프로필 갱신이 수 밀리초 늦게 반영되어도 게임 로직에 문제가 없다고 확인했습니다. 애플리케이션 코드 변경은 최소화해야 합니다. Choose the MOST appropriate solution.

- A. DynamoDB Accelerator 클러스터를 VPC에 배치하고 DAX 클라이언트로 엔드포인트만 교체한다.
- B. Amazon ElastiCache for Valkey 클러스터를 두고 cache-aside 로직을 애플리케이션에 구현한다.
- C. 자주 조회되는 속성을 투영한 global secondary index를 추가한다.
- D. 테이블을 on-demand 용량 모드로 전환한다.

<details markdown="1">
<summary>정답과 해설</summary>

**정답: A**

DAX는 DynamoDB API와 호환되는 인메모리 캐시라 클라이언트 엔드포인트만 바꾸면 되고 item cache와 query cache를 자동 관리합니다. eventually consistent 읽기를 마이크로초 단위로 가속하며 캐시 적중률이 높을수록 효과가 큽니다. 소수 아이템에 읽기가 집중되는 패턴은 DAX가 가장 잘 동작하는 조건입니다.

- B가 틀린 이유: 요구를 충족할 수는 있으나 cache-aside 로직, 무효화 처리, 직렬화를 애플리케이션이 직접 구현해야 해서 코드 변경 최소화 조건에 어긋납니다.
- C가 틀린 이유: GSI는 조회 패턴을 늘리는 수단이지 지연을 마이크로초로 낮추는 수단이 아닙니다. 자체 용량을 소비하며 읽기 집중 문제도 그대로 남습니다.
- D가 틀린 이유: on-demand 모드는 용량 관리 방식을 바꿀 뿐 응답 지연을 마이크로초로 줄이지 않습니다. 오히려 이전 피크의 2배를 30분 안에 넘기면 스로틀될 수 있습니다.

</details>

**Q3.** 한 보험사가 청구 서류 스캔본을 Amazon S3에 저장합니다. 객체 평균 크기는 5 MB이고, 업로드 후 30일 동안은 자주 열람되지만 이후에는 분기에 한 번 정도만 조회됩니다. 다만 조회 시에는 밀리초 단위 응답이 필요합니다. 1년이 지난 서류는 법적 보관 목적으로만 남기며 조회 요청이 사실상 없습니다. Choose the MOST cost-effective lifecycle configuration.

- A. 30일에 S3 Glacier Instant Retrieval로 전환하고 365일에 S3 Glacier Deep Archive로 전환한다.
- B. 30일에 S3 Glacier Flexible Retrieval로 전환하고 365일에 S3 Glacier Deep Archive로 전환한다.
- C. 30일에 S3 Standard-IA로 전환하고 120일에 S3 Glacier Instant Retrieval로, 365일에 S3 Glacier Deep Archive로 전환한다.
- D. 업로드 시점에 S3 Intelligent-Tiering으로 저장하고 별도 lifecycle 규칙을 두지 않는다.

<details markdown="1">
<summary>정답과 해설</summary>

**정답: A**

Glacier Instant Retrieval은 밀리초 액세스를 유지하면서 분기 1회 수준의 접근 빈도를 전제로 설계된 클래스이고 Standard-IA보다 저장 단가가 낮습니다. 최소 저장 기간이 90일이므로 30일에 전환한 뒤 365일에 Deep Archive로 넘기면 335일이 확보되어 조기 삭제 과금이 발생하지 않습니다.

- B가 틀린 이유: Glacier Flexible Retrieval은 복원 절차가 필요한 아카이브 클래스라 밀리초 조회 요구를 충족하지 못합니다. Expedited 복원도 250 MB 미만 객체 기준 1분에서 5분이 걸립니다.
- C가 틀린 이유: 요구를 충족하지만 30일에서 120일 구간을 Standard-IA에 두어 Glacier Instant Retrieval보다 비싼 단가를 90일간 더 부담합니다.
- D가 틀린 이유: Intelligent-Tiering은 액세스 패턴을 모를 때 쓰는 선택지입니다. 이 시나리오는 패턴이 명확하므로 객체당 모니터링 요금만 추가되고, 자동 계층으로는 Deep Archive까지 내려가지 않아 1년 이후 보관 비용도 최적이 아닙니다.

</details>

**Q4.** 한 회사가 규제 요건에 따라 ap-northeast-2 버킷의 객체를 us-west-2로 복제하도록 cross-Region replication을 설정했습니다. 설정 후 새로 업로드되는 객체는 정상 복제되지만, 설정 이전부터 있던 객체 2,000만 개는 대상 버킷에 나타나지 않습니다. 원본 버킷에는 Object Lock이 활성화되어 있습니다. Choose the solution that replicates the existing objects.

- A. S3 Batch Replication 작업을 만들어 기존 객체를 복제한다.
- B. 복제 규칙에 S3 Replication Time Control을 활성화한다.
- C. 대상 버킷의 versioning을 껐다가 다시 켜서 복제를 재동기화한다.
- D. 복제 규칙을 삭제하고 동일한 설정으로 다시 생성한다.

<details markdown="1">
<summary>정답과 해설</summary>

**정답: A**

live replication은 규칙 설정 이후에 생성되거나 갱신된 객체만 복제합니다. 기존 객체를 옮기는 경로는 S3 Batch Replication뿐이며, 복제 실패 객체 재시도와 복제본의 복제도 같은 수단을 씁니다.

- B가 틀린 이유: Replication Time Control은 새 객체의 복제 시간을 15분 SLA로 보장하는 기능이며 기존 객체를 대상으로 삼지 않습니다. Batch Replication에는 적용되지도 않습니다.
- C가 틀린 이유: 복제 대상 버킷에서 versioning을 끄면 복제가 `FAILED` 상태가 됩니다. 다시 켜도 기존 객체가 소급 복제되지 않습니다.
- D가 틀린 이유: 규칙을 다시 만들어도 기준은 여전히 규칙 설정 이후 객체입니다. 기존 객체는 복제되지 않습니다.

</details>

**Q5.** 한 회사가 RDS for PostgreSQL 단일 인스턴스로 주문 처리 시스템을 운영합니다. 요구사항은 세 가지입니다. 첫째, 인스턴스 장애 시 사람이 개입하지 않고 failover해야 합니다. 둘째, 커밋된 트랜잭션이 유실되지 않도록 동기 또는 준동기 복제여야 합니다. 셋째, 읽기 전용 리포트 쿼리를 대기 노드에서 처리해 writer 부하를 줄여야 합니다. 엔진은 그대로 유지합니다. Choose the MOST appropriate deployment.

- A. Multi-AZ DB instance 배포로 전환한다.
- B. Multi-AZ DB cluster 배포로 전환한다.
- C. Multi-AZ DB instance 배포로 전환하고 read replica 두 개를 추가한다.
- D. Amazon Aurora PostgreSQL로 마이그레이션하고 reader 인스턴스 두 개를 둔다.

<details markdown="1">
<summary>정답과 해설</summary>

**정답: B**

Multi-AZ DB cluster는 writer 한 개와 읽기 가능한 reader 두 개를 세 개의 Availability Zone에 배치하고, semisynchronous 복제로 reader 최소 한 개의 확인 응답을 요구합니다. 자동 failover, 커밋 손실 방지, 대기 노드의 읽기 처리라는 세 요구를 동시에 충족하는 유일한 RDS 배포 형태입니다. NVMe 로컬 스토리지 계열 인스턴스 클래스만 지원한다는 제약을 함께 확인해야 합니다.

- A가 틀린 이유: Multi-AZ DB instance의 standby는 읽기 트래픽을 받지 못합니다. 세 번째 요구를 충족하지 못합니다.
- C가 틀린 이유: read replica는 비동기 복제이며 자동 failover 대상이 아닙니다. 읽기는 분산되지만 리포트 쿼리 결과가 지연 반영될 수 있고 대기 노드 활용 요구와도 다릅니다.
- D가 틀린 이유: 요구를 충족할 수 있으나 엔진 마이그레이션이 따르며 지문이 엔진 유지를 조건으로 명시합니다.

</details>

**Q6.** 한 글로벌 서비스가 Amazon Aurora Global Database를 쓰며 primary는 us-east-1, secondary는 ap-northeast-2에 있습니다. 규제 변경으로 쓰기 리전을 ap-northeast-2로 옮겨야 하고, 모든 클러스터는 정상 동작 중이며 유지보수 창을 확보했습니다. 커밋된 데이터가 한 건도 유실되면 안 됩니다. Choose the operation that meets the RPO requirement.

- A. Aurora Global Database managed failover를 실행한다.
- B. Aurora Global Database switchover를 실행한다.
- C. secondary 클러스터를 global database에서 분리해 standalone 클러스터로 승격한다.
- D. primary 클러스터의 스냅샷을 ap-northeast-2로 복사해 새 클러스터로 복원한다.

<details markdown="1">
<summary>정답과 해설</summary>

**정답: B**

switchover는 secondary가 primary와 동기화될 때까지 기다린 뒤 승격하므로 RPO가 0입니다. 모든 클러스터가 정상이고 계획된 유지보수 창이 있는 상황에 쓰도록 설계된 절차이며, Global writer endpoint 값도 유지됩니다.

- A가 틀린 이유: managed failover는 리전 장애 대응 절차로 secondary 동기화를 기다리지 않습니다. RPO가 초 단위 비영값이고 write fencing이 best-effort라 split-brain 가능성도 남습니다.
- C가 틀린 이유: 분리 승격은 복제 지연 시점의 데이터로 클러스터가 독립하므로 커밋 손실 가능성이 있고, 이후 global database 구성을 처음부터 다시 만들어야 합니다.
- D가 틀린 이유: 스냅샷은 특정 시점 사본이라 스냅샷 이후 커밋이 전부 유실됩니다. 데이터 크기에 비례해 복원 시간도 깁니다.

</details>

**Q7.** 한 연구 조직이 Amazon EFS 파일시스템에 실험 데이터 200 TiB를 보관합니다. 분석 결과 데이터의 90%가 6개월 이상 접근되지 않았습니다. 팀은 이 콜드 데이터를 최저 단가 스토리지 클래스로 자동 이동시키면서, 활성 데이터에 대해서는 워크로드 증가에 맞춰 처리량이 자동으로 따라오기를 원합니다. Choose the MOST cost-effective configuration.

- A. lifecycle 정책으로 Archive 클래스 전환을 켜고 throughput mode를 Provisioned로 설정한다.
- B. lifecycle 정책으로 Archive 클래스 전환을 켜고 throughput mode를 Elastic으로 설정한다.
- C. throughput mode를 Bursting으로 두고 lifecycle 정책으로 Infrequent Access 전환만 켠다.
- D. 파일시스템을 One Zone으로 다시 만들고 Max I/O 성능 모드를 적용한다.

<details markdown="1">
<summary>정답과 해설</summary>

**정답: B**

EFS Archive 스토리지 클래스는 Elastic throughput 파일시스템에서만 지원되며, Archive 전환 lifecycle 정책이 걸려 있으면 throughput mode를 Bursting이나 Provisioned로 바꿀 수 없습니다. Elastic throughput은 워크로드에 맞춰 처리량이 자동으로 오르내리므로 두 요구가 정확히 맞물립니다.

- A가 틀린 이유: Provisioned throughput에서는 Archive 클래스를 쓸 수 없습니다. Provisioned는 고정 처리량을 사서 유지하는 모드라 자동 확장 요구와도 맞지 않습니다.
- C가 틀린 이유: Infrequent Access는 Archive보다 단가가 높아 최저 단가 요구를 충족하지 못합니다. Bursting은 저장량과 크레딧에 따라 처리량이 제한되어 자동 확장 요구도 만족하지 않습니다.
- D가 틀린 이유: One Zone은 AZ 손실을 견디지 못해 연구 데이터 보관 요건에 위험합니다. Max I/O는 previous generation이고 작업당 지연이 더 크며 Elastic throughput과 One Zone에서는 지원되지 않습니다.

</details>

**Q8.** 한 회사가 EC2에서 자체 운영하는 데이터베이스의 스토리지를 재설계합니다. 측정 결과 지속 45,000 IOPS와 900 MiB/s 처리량이 필요하고, 볼륨 크기는 4 TiB면 충분합니다. 지연 시간 변동에 대한 특별한 요구는 없고 인스턴스는 Nitro 기반입니다. Choose the MOST cost-effective volume configuration.

- A. io2 Block Express 볼륨 하나에 45,000 IOPS를 프로비저닝한다.
- B. gp3 볼륨 하나에 45,000 IOPS와 900 MiB/s를 프로비저닝한다.
- C. io1 볼륨 하나에 45,000 IOPS를 프로비저닝한다.
- D. gp2 볼륨 여러 개를 RAID 0으로 묶어 필요한 IOPS를 만든다.

<details markdown="1">
<summary>정답과 해설</summary>

**정답: B**

gp3는 볼륨 크기와 무관하게 IOPS와 처리량을 독립적으로 프로비저닝하며 최대 80,000 IOPS와 2,000 MiB/s까지 지원합니다. 45,000 IOPS와 900 MiB/s는 이 범위 안이므로 gp3로 충분하고, 프로비저닝 단가가 io 계열보다 낮아 비용이 가장 적습니다.

- A가 틀린 이유: io2 Block Express는 80,000 IOPS 초과, 2,000 MiB/s 초과, 99.999% 내구성, 일관된 저지연, Multi-Attach, NVMe reservations 중 하나가 필요할 때 고릅니다. 이 시나리오는 어느 조건에도 해당하지 않아 더 비싼 볼륨을 쓰게 됩니다.
- C가 틀린 이유: io1은 최대 64,000 IOPS로 요구를 만족하지만 프로비저닝 IOPS 단가가 gp3보다 높습니다. 처리량 1,000 MiB/s를 내려면 64,000 IOPS를 프로비저닝해야 해서 낭비가 더해집니다.
- D가 틀린 이유: gp2는 볼륨당 최대 16,000 IOPS와 250 MiB/s라 여러 볼륨을 묶어야 하고, RAID 구성과 스냅샷 정합성 관리 부담이 추가됩니다. 총 프로비저닝 용량도 커져 비용 이점이 없습니다.

</details>

**Q9.** 한 미디어 팀이 Linux 기반 렌더 팜을 구성합니다. 두 개 Availability Zone에 걸친 EC2 인스턴스 120대가 같은 에셋 디렉터리를 동시에 읽고 중간 산출물을 씁니다. 애플리케이션은 표준 POSIX 파일 인터페이스를 쓰고, 클러스터 파일시스템을 도입할 인력이 없습니다. Choose the MOST appropriate shared storage.

- A. io2 볼륨에 Multi-Attach를 활성화해 모든 인스턴스에 연결한다.
- B. Regional Amazon EFS 파일시스템을 Elastic throughput으로 만들어 모든 인스턴스에 마운트한다.
- C. Amazon FSx for Windows File Server 파일시스템을 Multi-AZ로 만들어 SMB로 마운트한다.
- D. 각 인스턴스에 gp3 볼륨을 붙이고 Amazon S3와 주기적으로 동기화한다.

<details markdown="1">
<summary>정답과 해설</summary>

**정답: B**

Regional EFS는 리전 내 여러 AZ에서 동시에 마운트할 수 있고 NFS 기반 POSIX 시맨틱을 제공하며 수천 개 클라이언트의 동시 접근을 전제로 설계됐습니다. Elastic throughput은 워크로드에 맞춰 처리량이 자동으로 조절되므로 렌더 작업의 변동 부하에 맞습니다.

- A가 틀린 이유: EBS Multi-Attach는 같은 Availability Zone의 Nitro 인스턴스 최대 16대까지만 지원합니다. 두 AZ에 걸친 120대 구성이 불가능하고, 표준 파일시스템으로는 동시 쓰기를 안전하게 처리할 수 없어 클러스터 파일시스템이 필요합니다.
- C가 틀린 이유: FSx for Windows File Server는 SMB 프로토콜이며 생성 시 Microsoft Active Directory 조인이 필수입니다. Linux POSIX 워크로드에 맞지 않고 디렉터리 서비스 운영 부담이 새로 생깁니다.
- D가 틀린 이유: 인스턴스별 로컬 볼륨과 주기 동기화는 동시 읽기 쓰기 일관성을 제공하지 않습니다. 중간 산출물이 인스턴스 간에 즉시 공유되어야 하는 요구를 충족하지 못합니다.

</details>

**Q10.** (다답형) 한 회사가 감사 대응을 위해 S3 버킷의 객체를 다른 리전으로 복제하는 설계를 검토합니다. 원본 버킷에는 이미 수천만 개 객체가 있고 Object Lock이 활성화되어 있으며, 복제 지연에 대한 내부 목표도 문서화하려 합니다. 아키텍트가 설계 문서에 적어야 할 사실은 무엇인가요? Choose THREE statements that are correct.

- A. 원본 버킷과 대상 버킷 양쪽에 versioning이 활성화되어 있어야 복제 규칙이 동작합니다.
- B. 복제 규칙 설정 이전에 존재하던 객체는 S3 Batch Replication으로 별도 복제해야 합니다.
- C. 원본 버킷에 Object Lock이 활성화되어 있으면 대상 버킷에도 Object Lock을 활성화해야 합니다.
- D. S3 Replication Time Control을 켜면 Batch Replication 작업에도 15분 SLA가 적용됩니다.
- E. 대상 버킷에서 versioning을 비활성화하면 복제가 일시 중지되었다가 다시 활성화하면 자동으로 재개됩니다.
- F. 같은 리전 복제(SRR)에는 리전 간 데이터 전송 요금이 부과됩니다.

<details markdown="1">
<summary>정답과 해설</summary>

**정답: A, B, C**

복제는 원본과 대상 양쪽 versioning을 전제로 하고, live replication은 규칙 설정 이후 객체만 대상으로 하며, 원본의 Object Lock 설정은 대상에도 동일하게 요구됩니다. 세 항목 모두 설계 문서에 반영해야 하는 사실입니다.

- D가 틀린 이유: Replication Time Control은 live replication에만 적용되고 Batch Replication에는 적용되지 않습니다.
- E가 틀린 이유: 대상 버킷에서 versioning을 끄면 복제가 `FAILED` 상태가 되며 다시 켠다고 자동으로 재개되지 않습니다. 원본에서 versioning을 끄려면 복제 설정을 먼저 삭제해야 합니다.
- F가 틀린 이유: 같은 리전 안의 복제인 SRR에는 리전 간 데이터 전송 요금이 없습니다. 리전 쌍에 따라 요금이 달라지는 것은 CRR입니다.

</details>

---

## 28. Reference

- [Amazon EBS - Volume types](https://docs.aws.amazon.com/ebs/latest/userguide/ebs-volume-types.html)
- [Amazon EBS - Use Amazon EBS Multi-Attach](https://docs.aws.amazon.com/ebs/latest/userguide/ebs-volumes-multi.html)
- [Amazon EBS - Amazon EBS snapshots](https://docs.aws.amazon.com/ebs/latest/userguide/ebs-snapshots.html)
- [Amazon Data Lifecycle Manager - Automate backups](https://docs.aws.amazon.com/ebs/latest/userguide/snapshot-lifecycle.html)
- [Amazon EBS - Amazon EBS encryption](https://docs.aws.amazon.com/ebs/latest/userguide/ebs-encryption.html)
- [Amazon EFS - Performance](https://docs.aws.amazon.com/efs/latest/ug/performance.html)
- [Amazon EFS - Features](https://docs.aws.amazon.com/efs/latest/ug/features.html)
- [Amazon EFS - Lifecycle management](https://docs.aws.amazon.com/efs/latest/ug/lifecycle-management-efs.html)
- [Amazon S3 - Storage classes](https://docs.aws.amazon.com/AmazonS3/latest/userguide/storage-class-intro.html)
- [Amazon S3 - Lifecycle transition considerations](https://docs.aws.amazon.com/AmazonS3/latest/userguide/lifecycle-transition-general-considerations.html)
- [Amazon S3 - Retrieval options](https://docs.aws.amazon.com/AmazonS3/latest/userguide/restoring-objects-retrieval-options.html)
- [Amazon S3 - Optimizing performance](https://docs.aws.amazon.com/AmazonS3/latest/userguide/optimizing-performance.html)
- [Amazon S3 - Replication](https://docs.aws.amazon.com/AmazonS3/latest/userguide/replication.html)
- [Amazon S3 - Replication requirements](https://docs.aws.amazon.com/AmazonS3/latest/userguide/replication-requirements.html)
- [Amazon S3 - Replication not supported](https://docs.aws.amazon.com/AmazonS3/latest/userguide/replication-what-is-isnot-replicated.html)
- [Amazon S3 - Upload objects](https://docs.aws.amazon.com/AmazonS3/latest/userguide/upload-objects.html)
- [Amazon S3 - Amazon S3 quotas](https://docs.aws.amazon.com/AmazonS3/latest/userguide/qfacts.html)
- [Amazon FSx for Windows File Server - What is Amazon FSx for Windows File Server](https://docs.aws.amazon.com/fsx/latest/WindowsGuide/what-is.html)
- [Amazon FSx for Lustre - What is Amazon FSx for Lustre](https://docs.aws.amazon.com/fsx/latest/LustreGuide/what-is.html)
- [Amazon FSx for NetApp ONTAP - What is Amazon FSx for NetApp ONTAP](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/what-is-fsx-ontap.html)
- [Amazon FSx for OpenZFS - What is Amazon FSx for OpenZFS](https://docs.aws.amazon.com/fsx/latest/OpenZFSGuide/what-is-fsx.html)
- [Amazon FSx for OpenZFS - Availability and durability](https://docs.aws.amazon.com/fsx/latest/OpenZFSGuide/availability-durability.html)
- [Amazon DynamoDB - Service quotas](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/ServiceQuotas.html)
- [Amazon DynamoDB - Constraints](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Constraints.html)
- [Amazon DynamoDB - Local secondary indexes](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/LSI.html)
- [Amazon DynamoDB - Global secondary indexes](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/GSI.html)
- [Amazon DynamoDB - On-demand capacity mode](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/on-demand-capacity-mode.html)
- [Amazon DynamoDB - Global table throughput](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/bp-global-table-design.prescriptive-guidance.throughput.html)
- [Amazon DynamoDB - Global tables](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/GlobalTables.html)
- [Amazon DynamoDB - How global tables work](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/V2globaltables_HowItWorks.html)
- [Amazon DynamoDB - DynamoDB Streams](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Streams.html)
- [Amazon DynamoDB Accelerator - DAX](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/DAX.html)
- [Amazon DynamoDB Accelerator - How DAX works](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/DAX.concepts.html)
- [Amazon ElastiCache - Choose an engine](https://docs.aws.amazon.com/AmazonElastiCache/latest/dg/SelectEngine.html)
- [Amazon ElastiCache - Deployment options](https://docs.aws.amazon.com/AmazonElastiCache/latest/dg/WhatIs.deployment.html)
- [Amazon RDS - Read replicas](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_ReadRepl.html)
- [Amazon RDS - Multi-AZ DB clusters](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/multi-az-db-clusters-concepts.html)
- [Amazon RDS - Encryption](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Overview.Encryption.html)
- [Amazon RDS - Limits](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_Limits.html)
- [Amazon Aurora - Storage reliability](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/Aurora.Overview.StorageReliability.html)
- [Amazon Aurora - Global Database](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/aurora-global-database.html)
- [Amazon Aurora - Global Database disaster recovery](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/aurora-global-database-disaster-recovery.html)
- [Amazon Aurora - Serverless v2](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/aurora-serverless-v2.how-it-works.html)
- [Amazon Aurora - Serverless v2 administration](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/aurora-serverless-v2-administration.html)
- [Amazon Aurora - Serverless v2 upgrade](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/aurora-serverless-v2.upgrade.html)
- [Amazon Aurora - Overview](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/Aurora.Overview.html)
- [Amazon OpenSearch Service - What is Amazon OpenSearch Service](https://docs.aws.amazon.com/opensearch-service/latest/developerguide/what-is.html)
- [Amazon OpenSearch Serverless - What is Amazon OpenSearch Serverless](https://docs.aws.amazon.com/opensearch-service/latest/developerguide/serverless-overview.html)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
