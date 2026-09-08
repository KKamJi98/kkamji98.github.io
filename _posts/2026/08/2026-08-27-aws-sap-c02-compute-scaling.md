---
title: "SAP-C02 박살내기 5 - 컴퓨트 선택과 확장"
author: kkamji
categories: [Certification, AWS SAP-C02]
tags: [aws, sap-c02, certification, ec2, auto-scaling, spot, savings-plans, placement-group, graviton]
comments: true
image:
  path: /assets/img/aws/aws.webp
date: 2026-08-27 10:00:00 +0900
---

분기 실적 발표일마다 투자자 포털을 300대 규모로 확장하는 팀이 있습니다. 상시 baseline은 40대이고 3년 Compute Savings Plans를 이미 사 두었으니 비용 쪽은 정리되었다고 판단했는데, 발표일 오전에 확장이 `InsufficientInstanceCapacity`로 실패했습니다. 두 번째 분기에도 같은 자리에서 같은 오류가 났습니다.

Savings Plans는 시간당 지출 금액을 약정하고 그 금액만큼 요금을 깎는 수단입니다. 용량에 대해서는 아무것도 약속하지 않습니다. 필요한 것은 지정 AZ에 인스턴스 자리를 잡아 두는 On-Demand Capacity Reservation이었고, 그 위에 이미 산 Savings Plans 요금이 그대로 적용됩니다. 두 축이 분리되어 있다는 사실 하나가 이 팀이 두 분기를 놓친 이유입니다.

SAP-C02 Domain 2는 이 층에서 답이 갈리는 문항을 냅니다. 구매 옵션 일곱 가지 중 무엇이 할인이고 무엇이 용량인지, placement group 전략 중 무엇이 어떤 경계를 넘지 못하는지, 스케일링 정책 네 가지 중 무엇이 축소를 담당하는지가 선지를 가릅니다. 서비스 이름을 아는 것으로는 좁혀지지 않고, 각 수단이 **하지 않는 일**을 알아야 좁혀집니다.

> **TL;DR**  
> - 구매 옵션은 On-Demand, Savings Plans, Reserved Instances, Spot, Dedicated Hosts, Dedicated Instances, Capacity Reservations 일곱 가지다.  
> - Savings Plans와 regional RI는 용량을 예약하지 않는다. ODCR은 요금을 깎지 않는다. 두 축을 모두 가진 것은 zonal RI 하나다.  
> - Compute SP 최대 66%, EC2 Instance SP 최대 72%. Compute SP만 Fargate와 Lambda에 적용된다.  
> - Standard RI는 exchange가 불가능하고 Marketplace 매도가 가능하다. Convertible RI는 정반대다.  
> - 소켓과 코어 단위 BYOL은 Dedicated Host다. Dedicated Instance의 BYOL은 SQL Server License Mobility와 Windows VDA로 한정된다.  
> - cluster는 단일 AZ를 넘지 못한다. partition은 AZ당 7개, rack-level spread는 AZ당 running 7대다.  
> - placement group 안의 Capacity Reservation은 cluster 또는 precision time에 만들 수 있고, spread와 partition에는 만들 수 없다. 일반 ODCR은 placement group 없이도 만든다.  
> - Spot 가격은 입찰이 아니다. 최대 가격을 지정하면 지정하지 않을 때보다 중단이 잦아진다.  
> - 2분 중단 통지는 stop과 terminate에 2분 전에 발행된다. hibernate도 통지는 발행되지만 즉시 시작되어 2분 경고가 없다.  
> - predictive scaling은 scale in을 하지 않는다. 축소는 dynamic scaling 정책이 담당한다.  
> - target tracking 지표는 인스턴스 수에 비례해야 한다. SQS 큐 길이와 ELB `RequestCount`와 `Latency`는 문서가 직접 배제한다.  
> - cooldown은 simple scaling에만 적용된다. target tracking과 step scaling은 instance warmup을 쓴다.  
> - instance refresh 기본값은 minimum healthy percentage 90%라 교체 중 용량이 10%까지 줄어든다.  
> - `AWS/EC2` 기본 메트릭에 메모리와 디스크 여유 공간이 없다. 자동 복구는 system status check 실패에만 동작한다.  
{: .prompt-info}

---

## 1. 인스턴스 타입 이름에 들어 있는 네 조각

인스턴스 타입 이름은 series, generation, options, size 네 조각으로 이루어집니다. `c7gn.xlarge`라면 `c`가 series, `7`이 generation, `gn`이 options, `xlarge`가 size입니다. 시험 지문은 타입 이름을 그대로 주고 그 워크로드에 맞는지 판단하게 만드는 경우가 많아서, 문자 하나하나가 무엇을 뜻하는지 읽을 수 있어야 합니다.

| series 문자 | 의미 |
| :--- | :--- |
| `C` | compute optimized |
| `M` | general purpose |
| `R` | memory optimized |
| `T` | burstable |
| `X`, `Z`, `U` | memory intensive, high memory |
| `I`, `Im`, `Is`, `D` | storage optimized, dense storage. `Im`은 vCPU 대 메모리 1 대 4, `Is`는 1 대 6 |
| `P`, `G`, `VT` | GPU accelerated, graphics intensive, video transcoding |
| `Inf`, `Trn` | Inferentia, Trainium |
| `Hpc` | high performance computing |
| `F` | FPGA |
| `Mac` | macOS |
| `A` | Arm 기반 Graviton |

옵션 문자는 하드웨어와 부가 능력을 나타냅니다.

| options 문자 | 의미 |
| :--- | :--- |
| `a` | AMD 프로세서 |
| `g` | AWS Graviton 프로세서 |
| `i` | Intel 프로세서 |
| `q` | Qualcomm 프로세서 |
| `b` | block storage optimization |
| `d` | instance store 볼륨 포함 |
| `e` | extra storage 또는 extra memory 또는 extra GPU memory |
| `n` | network and EBS optimized |
| `z` | high CPU frequency |
| `flex` | flex instance |
| `*tb` | high memory 인스턴스의 메모리 용량 |

`c7gn.xlarge`를 다시 읽으면 compute optimized 7세대이면서 Graviton 프로세서에 네트워크와 EBS가 강화된 타입입니다. 지문에 `노드 간 통신량이 많은 계산 집약 워크로드`가 있으면 이 조합이 답이 되고, `메모리 집약`이 있으면 `r` 계열로 옮겨 갑니다.

Graviton은 Arm 기반 AWS 자체 프로세서이고 타입 이름의 `g` 옵션 문자로 식별합니다. 공식 문서가 명시하는 수치 중 확인되는 것은 버스터블 계열 비교입니다. T4g는 Graviton2 기반이고 T3 대비 최대 40% 높은 price/performance와 20% 낮은 비용을 제공한다고 문서가 적습니다. Graviton 세대 전반의 x86 대비 성능 비율은 인스턴스 패밀리마다 다르므로, 지문에 수치가 나오면 그 수치를 판단 근거로 쓰기보다 `x86 전용 바이너리나 상용 에이전트 의존성이 있는가`를 먼저 봅니다. 아키텍처가 바뀌므로 재컴파일이 필요하고, 이 제약이 마이그레이션 문항에서 Graviton 선지를 탈락시키는 실제 이유입니다.

---

## 2. 버스터블 인스턴스의 credit 회계와 launch template 제약

버스터블은 baseline 성능을 CPU credit으로 관리하는 계열입니다. 현행 세대는 T4g, T3a, T3이고 T2는 previous generation입니다. T4g는 Graviton2, T3a는 AMD EPYC, T3는 Intel Xeon Scalable 기반입니다.

credit specification 두 가지가 동작을 가릅니다.

| 모드 | 동작 |
| :--- | :--- |
| `standard` | 쌓인 credit을 다 쓰면 baseline 성능으로 떨어진다. 추가 과금이 없다 |
| `unlimited` | credit이 고갈되어도 성능을 유지하고 초과분만 추가 과금된다 |

기본값이 세대마다 다릅니다. **T4g, T3a, T3은 `unlimited`가 기본이고 T2만 `standard`가 기본입니다.** 그런데 예외가 두 개 있고 시험은 이 예외를 노립니다.

- Dedicated Host 위의 T3는 `standard`로만 시작할 수 있다.
- Auto Scaling group에서 `unlimited`로 띄우려면 launch template이 필요하다. **launch configuration은 `unlimited`를 지원하지 않는다.**

평균 CPU 사용률이 10% 안팎인데 하루 두어 번 급증하면서 credit이 고갈되는 그룹이 있고 그 그룹이 launch configuration으로 만들어져 있다면, 답은 인스턴스 타입 교체가 아니라 launch template 전환입니다. 계정 레벨 기본 credit specification은 리전별로 바꿀 수 있지만 변경 빈도에 제한이 있어서 rolling 5분에 1회, rolling 24시간에 4회까지만 가능합니다.

T 계열이 지원하는 구매 옵션도 좁습니다. On-Demand, Reserved, Spot은 전부 되지만 Dedicated Instances와 Dedicated Hosts는 T3만 지원하고, Dedicated Host 위에서는 `standard` 모드만 됩니다.

---

## 3. 구매 옵션 일곱 가지가 갈리는 세 질문

AWS 문서가 나열하는 EC2 구매 옵션은 On-Demand Instances, Savings Plans, Reserved Instances, Spot Instances, Dedicated Hosts, Dedicated Instances, Capacity Reservations 일곱 가지입니다. 이 일곱 개를 한 줄에 세워 놓고 비교하면 답이 안 나옵니다. 서로 배타적인 선택지가 아니라 층이 다른 수단이 섞여 있기 때문입니다.

{% include diagrams/static/sap-c02/ec2-purchase-option-decision.html %}
{% include diagrams/download.html png="/assets/img/diagrams/static/sap-c02/ec2-purchase-option-decision--6cd35e91f559e3e7.png" %}

그림은 왼쪽의 워크로드 요구에서 출발해 두 질문으로 갈라지는 구조입니다. 하나는 물리 소켓과 코어 단위 라이선스인지를 묻는 가지이고 Dedicated Host와 Dedicated Instance로 이어집니다. 다른 하나는 2분 통지로 중단을 견디는지를 묻는 가지이고, 견디면 Spot으로, 견디지 못하면 약정 가능 여부를 묻는 다음 질문으로 이어져 Savings Plans 계열과 On-Demand로 나뉩니다. 오른쪽에 따로 놓인 붉은 상자가 용량 보장 축이고, 다른 가지 위에 겹쳐 쓰는 수단이라는 뜻입니다.

질문 순서가 중요합니다.

1. **중단을 견디는가.** stateless이고 체크포인트가 있으면 Spot이다. 아니면 Spot은 탈락한다.
2. **1년 또는 3년 지출을 약정할 수 있는가.** 가능하면 Savings Plans 또는 Reserved Instances, 아니면 On-Demand다.
3. **물리 소켓과 코어 단위 라이선스인가.** 그렇다면 tenancy를 Dedicated Host로 올린다.

세 질문 어디에도 용량 보장이 없습니다. 용량 보장은 위 세 질문의 답 위에 겹치는 별도 축이고, 다음 두 절이 그 축을 다룹니다.

---

## 4. Savings Plans 두 종류가 덮는 범위

Savings Plans는 1년 또는 3년 동안 시간당 일정 금액을 쓰겠다고 약정하고 그 사용량에 할인 요금을 받는 모델입니다. 약정 기간은 1년이 365일(31,536,000초), 3년이 1,095일(94,608,000초)이고 결제는 All upfront, Partial upfront, No upfront 세 가지입니다. **약정 조건은 구매 후 변경할 수 없고 기간 중 취소할 수 없습니다.**

종류별 최대 할인율은 다음과 같습니다.

| 종류 | 최대 할인 | 적용 범위 |
| :--- | :--- | :--- |
| Compute Savings Plans | 66% | instance family, size, Region, OS, tenancy 무관. Fargate와 Lambda 포함 |
| EC2 Instance Savings Plans | 72% | 리전과 인스턴스 패밀리 고정. size, OS, tenancy만 유연 |
| SageMaker AI Savings Plans | 64% | SageMaker AI 사용량 |
| Database Savings Plans | 35% | 대상 데이터베이스 사용량 |

시험에서 갈리는 지점은 유연성과 할인율의 교환입니다. 리전 이동이나 패밀리 전환이 예정되어 있으면 EC2 Instance Savings Plans는 그 시점에 무용지물이 됩니다. Fargate와 Lambda 지출이 섞여 있으면 Compute Savings Plans가 유일하게 세 서비스를 한 약정으로 덮습니다.

적용 대상에서 빠지는 것들도 정확히 알아야 합니다.

- Dedicated Instances에 붙는 리전당 시간당 2 USD 요금은 Savings Plans 할인 대상이 아니다.
- EMR, EKS, ECS 클러스터의 하부 EC2 인스턴스에는 적용되지만 **EKS 자체 요금에는 적용되지 않는다.**
- Spot 사용분에는 적용되지 않고, Spot 지출은 Compute Savings Plans 약정 소진에 기여하지도 않는다.

마지막 항목이 오답 선지를 만듭니다. Spot과 Savings Plans를 함께 써서 절감을 겹치려는 구성은 성립하지 않습니다.

---

## 5. Reserved Instance의 scope와 exchange와 매각

Reserved Instance는 인스턴스 구성 자체를 약정하는 모델이고 두 가지 축으로 나뉩니다. 하나는 Standard와 Convertible이라는 유형 축이고, 다른 하나는 regional과 zonal이라는 scope 축입니다. 두 축이 독립적이라는 점이 자주 섞입니다.

| 유형 | exchange | Marketplace 매도 |
| :--- | :--- | :--- |
| Standard RI | 불가능 | 가능 |
| Convertible RI | instance family, instance type, platform, scope, tenancy를 바꿀 수 있다 | 불가능 |

정확히 반대입니다. 남는 예약을 회수할 여지를 남기려면 Standard RI, 구성 변경을 예상하면 Convertible RI입니다. 둘 다 일부 속성의 modify는 가능하지만 modify와 exchange는 다른 동작입니다.

scope 축은 용량 예약 여부를 가릅니다.

| scope | 용량 예약 | 유연성 | 구매 queue |
| :--- | :--- | :--- | :--- |
| regional | **없다** | AZ 유연성과 instance size 유연성 | 가능 |
| zonal | 지정 AZ에 예약한다 | 없다 | 불가능 |

size 유연성에는 조건이 붙습니다. **Amazon Linux와 Unix 플랫폼에 default tenancy인 RI만 size 유연성을 가집니다.** Windows RI나 Dedicated tenancy RI는 size 유연성이 없습니다. scope 자체는 가격에 영향을 주지 않으므로, 같은 값을 내면서 유연성을 택할지 용량을 택할지 고르는 구조입니다.

---

## 6. 용량 확보는 요금 할인과 다른 층이다

도입부의 실패가 여기서 나옵니다. 요금 할인 수단과 용량 확보 수단은 층이 다르고, 하나가 다른 하나를 대신하지 못합니다.

{% include diagrams/static/sap-c02/capacity-and-discount-layers.html %}
{% include diagrams/download.html png="/assets/img/diagrams/static/sap-c02/capacity-and-discount-layers--53bb4fece5abf95e.png" %}

그림은 세 개의 층 상자로 나뉩니다. 하나는 요금 할인만 하는 수단들이고 Compute와 EC2 Instance Savings Plans, Convertible과 Standard Reserved Instance, regional scope RI가 들어 있습니다. 다른 하나는 용량만 확보하는 수단이고 On-Demand Capacity Reservation과 Capacity Blocks for ML이 들어 있습니다. 점선으로 표시한 세 번째 층에 zonal scope RI 하나만 놓여 있고, 두 축을 동시에 가진 유일한 수단이라는 뜻입니다. 붉은 상자에는 겹쳐 쓸 때의 조건이 적혀 있습니다.

On-Demand Capacity Reservation의 성격을 문서 표현 그대로 옮기면 `Reserve capacity for your EC2 instances in a specific Availability Zone`이고 비교표에는 `No billing discount`로 적혀 있습니다. 즉시 사용 유형이면 term commitment가 없고 언제든 수정과 취소가 가능합니다. 할인은 Savings Plans 또는 regional RI를 겹쳐서 얻습니다. **zonal RI 할인은 ODCR에 적용되지 않습니다.** 이미 zonal RI로 그 AZ에 용량을 잡았다면 ODCR을 또 잡을 이유가 없기 때문입니다.

ODCR이 인스턴스를 매칭하는 속성은 네 가지입니다.

| 속성 | 값 |
| :--- | :--- |
| instance type | 정확히 일치해야 한다 |
| platform | 정확히 일치해야 한다 |
| Availability Zone | 정확히 일치해야 한다 |
| tenancy | 정확히 일치해야 한다 |

open이면 속성이 맞는 실행 중 인스턴스가 자동으로 들어가고, targeted면 명시적으로 지정한 워크로드만 들어갑니다. 특정 워크로드를 위해 잡아 둔 용량을 다른 워크로드가 먹어 버리는 상황을 막으려면 targeted입니다.

운영에서 걸리는 제약도 정리해 둡니다.

- **active 상태의 미사용 ODCR도 계정의 On-Demand 인스턴스 한도를 소모한다.** 인스턴스를 띄우지 않았는데 한도가 차는 이유가 여기 있다.
- Dedicated Hosts와는 함께 쓸 수 없고 Dedicated Instances와는 쓸 수 있다.
- Windows BYOL과는 쓸 수 없고 Red Hat BYOL과는 쓸 수 있다.
- hibernate한 인스턴스의 재시작을 보장하지 않는다.

기본 쿼터 비교도 문항 재료입니다. zonal RI는 AZ당 20개, regional RI는 리전당 20개이고 Savings Plans에는 개수 한도가 없습니다.

미래 시점 용량을 잡는 수단이 두 가지 더 있습니다. future-dated Capacity Reservation은 최소 32 vCPU 규모로만 요청할 수 있어서 `m5.xlarge`라면 8대 이상이어야 하고, 지원 패밀리는 C, G, I, M, R, T, U, X입니다. commitment 기간 중에는 인스턴스 수와 기간을 초기 약정 아래로 줄일 수 없습니다. Capacity Blocks for ML은 미래의 특정 날짜부터 정해진 기간 동안 GPU 인스턴스 클러스터를 확보하는 별도 유형이고 placement group을 지원하지 않습니다. **ODCR은 기간 제약 없는 용량 확보, Capacity Blocks는 날짜가 정해진 GPU 확보**로 구분합니다.

---

## 7. Dedicated Host와 Dedicated Instance는 라이선스 단위에서 갈린다

둘 다 물리 서버를 다른 고객과 공유하지 않는 단일 테넌시입니다. 그런데 노출되는 정보와 배치 제어 능력이 달라서 라이선스 요건이 있는 문항에서 답이 갈립니다.

| 축 | Dedicated Host | Dedicated Instance |
| :--- | :--- | :--- |
| 과금 단위 | 호스트 | 인스턴스 |
| 소켓과 코어 가시성 | 있다 | 없다 |
| host ID | 보인다 | 보이지 않는다 |
| host affinity | 지원한다 | 지원하지 않는다 |
| targeted placement | 지원한다 | 지원하지 않는다 |
| BYOL | per-socket, per-core, per-VM 전면 지원 | SQL Server License Mobility와 Windows VDA만 |
| Capacity Reservations | 불가능 | 가능 |
| placement group | 넣을 수 없다 | cluster 가능, partition 최대 2개, spread 불가 |
| 계정 간 host 공유 | 가능 | 불가능 |

판정 규칙은 짧습니다. **지문에 소켓 또는 코어 단위 라이선스가 나오면 Dedicated Host이고, 단일 테넌시만 필요하고 배치 제어가 필요 없으면 Dedicated Instance입니다.** 재기동 후에도 같은 물리 서버에 올라가야 한다는 요건도 host affinity를 가진 Dedicated Host로만 충족됩니다.

Dedicated Host에는 별도 제약이 붙습니다.

- RHEL과 SUSE는 자체 AMI를 가져와야 한다. 고메모리 `u-*.metal` 계열은 예외다.
- RDS 인스턴스를 지원하지 않는다.
- Free tier가 없다.
- 가상화 타입으로 할당한 host를 `.metal` 타입으로 바꿀 수 없고 반대도 안 된다.
- Auto Scaling group에서 쓰려면 launch template이 host resource group을 지정해야 한다.

Dedicated Host Reservations는 On-Demand Dedicated Host 대비 최대 70% 할인이고, **이미 할당된 host가 있어야 구매할 수 있습니다.** 예약을 먼저 사고 host를 나중에 할당하는 순서는 성립하지 않습니다.

---

## 8. Spot 가격은 입찰이 아니고 최대 가격 지정은 중단을 늘린다

Spot을 입찰 모델로 기억하고 있으면 이 절의 문항을 전부 틀립니다. **Spot 가격은 EC2가 정하고 장기 수급에 따라 점진적으로 조정됩니다.** 사용자가 제시한 값이 경매에서 이기는 구조가 아닙니다.

최대 가격을 지정하지 않는 것이 문서 권장입니다. 지정하지 않으면 현재 Spot 가격으로 실행되고 그 가격은 On-Demand 가격을 넘지 않습니다. 최대 가격을 지정하면 세 가지가 달라집니다.

- 값은 USD 0.001을 초과해야 한다.
- **그 값과 무관하게 청구는 항상 현재 Spot 가격이다.** 높게 잡아도 더 내지 않는다.
- **지정하지 않을 때보다 중단이 더 자주 발생한다고 문서가 명시한다.**

세 번째가 핵심입니다. 최대 가격을 낮게 잡아 비용을 아끼겠다는 선지도, 높게 잡아 중단을 줄이겠다는 선지도 둘 다 틀립니다. 현재 Spot 가격보다 낮게 지정하면 아예 launch되지 않습니다.

중단 사유는 세 가지입니다.

| 사유 | 내용 |
| :--- | :--- |
| capacity | On-Demand 수요가 늘어 EC2가 용량을 회수한다 |
| price | Spot 가격이 지정한 최대 가격을 넘어선다 |
| constraints | launch group 또는 AZ group 제약을 위반해 그룹 단위로 종료된다 |

중단 동작은 terminate, stop, hibernate 세 가지이고 요청 유형에 따라 유효한 값이 다릅니다.

| 요청 유형 | 기본값 | 유효한 interruption behavior |
| :--- | :--- | :--- |
| one-time (기본) | `Terminate` | `Terminate`만 |
| persistent | 없음 | `Stop` 또는 `Hibernate` |

**interruption behavior 기본값 `Terminate`는 persistent 요청에서 유효하지 않습니다.** 기본값을 그대로 두고 persistent 요청을 띄우면 에러가 납니다. `Valid to`도 persistent 요청에만 적용되고, one-time 요청은 인스턴스가 전부 뜨거나 요청을 취소할 때까지 유지됩니다.

API 경로도 짚어 둡니다. `request-spot-instances`는 legacy API이고 문서가 사용을 강하게 비권장합니다. 권장 경로는 EC2 Fleet이나 Spot Fleet, 또는 `run-instances`의 `--instance-market-options`입니다.

---

## 9. Spot이 보내는 신호 두 개와 그에 맞는 대응

Spot 워크로드를 설계할 때 받는 신호는 두 개이고, 도착 시점과 대응 방식이 다릅니다.

{% include diagrams/static/sap-c02/spot-interruption-signals.html %}
{% include diagrams/download.html png="/assets/img/diagrams/static/sap-c02/spot-interruption-signals--275e237ed6cd0710.png" %}

그림은 EC2가 Spot 용량을 회수하기로 결정한 지점에서 두 갈래로 갈립니다. 한쪽은 rebalance recommendation을 받아 ASG Capacity Rebalancing이 선제 교체를 수행하는 경로이고, 다른 한쪽은 2분 중단 통지를 받아 EventBridge와 메타데이터로 정리 작업을 하고 설정한 중단 동작으로 끝나는 경로입니다. 두 신호를 잇는 점선은 동시에 도착할 수도 있다는 뜻이고, 아래쪽 상자는 신호 대응과 별개로 중단 빈도 자체를 줄이는 수단을 가리킵니다.

**2분 중단 통지**는 stop 또는 terminate 2분 전에 발행됩니다. hibernate도 interruption notice는 발행되지만 즉시 시작되므로 2분 전 경고가 없습니다. 통지가 오는 경로는 두 가지입니다.

- EventBridge의 `EC2 Spot Instance Interruption Warning` 이벤트
- 인스턴스 메타데이터 `/latest/meta-data/spot/instance-action`

문서는 메타데이터를 5초 주기로 폴링하라고 권장하고, **통지가 best effort라 도착하지 않을 수 있음을 전제하라**고 명시합니다. 체크포인트를 2분 통지에만 의존하는 설계가 위험한 이유입니다.

**EC2 instance rebalance recommendation**은 중단 위험이 높아졌다는 별도 신호입니다. 보통 2분 통지보다 먼저 오지만 동시에 도착할 수도 있습니다. Auto Scaling group에서 Capacity Rebalancing을 켜면 이 신호를 받아 선제 교체를 시작하고, **새 인스턴스가 health check를 통과한 뒤에 기존 인스턴스를 종료합니다.** 이 과정에서 그룹 크기가 desired capacity의 최대 10%까지 일시적으로 초과할 수 있습니다.

Capacity Rebalancing에 대한 오해가 두 개 있습니다.

- **Spot 중단율 자체를 낮추지 않는다.** 교체 횟수는 오히려 늘어난다.
- 새 인스턴스의 가용성이 기존과 같거나 나을 때만 교체를 시도한다.
- lowest-price 전략과 함께 쓰면 교체된 인스턴스도 곧 중단될 위험이 커서, 문서가 price-capacity-optimized를 강하게 권장한다.

lifecycle hook으로 Spot 중단을 안전하게 처리하겠다는 구성도 한계가 명확합니다. **hook은 Spot 중단을 막지 못하고**, 용량이 사라지면 2분 통지와 함께 언제든 종료됩니다. custom action은 2분 안에 끝나도록 설계해야 합니다.

---

## 10. Fleet과 mixed instances group의 할당 전략

Spot pool을 어떻게 고르는지가 중단 빈도를 좌우합니다. EC2 Fleet과 Spot Fleet의 Spot 할당 전략은 다섯 가지입니다.

| 전략 | 동작 |
| :--- | :--- |
| `price-capacity-optimized` | 가격과 가용 용량을 함께 본다. 문서 권장 |
| `capacity-optimized` | 가용 용량이 가장 많은 pool을 고른다 |
| `capacity-optimized-prioritized` | 용량을 우선하되 지정한 우선순위를 최선으로 반영한다 |
| `diversified` | 여러 pool에 고르게 분산한다 |
| `lowest-price` | 가격만 본다. CLI 기본값이며 문서가 명시적으로 비권장한다 |

`InstancePoolsToUseCount`는 `lowest-price`에서만 유효합니다. `diversified`는 Spot 가격이 On-Demand 가격 이상인 pool에는 인스턴스를 띄우지 않습니다.

On-Demand 할당 전략은 두 가지뿐입니다. lowest price가 기본이고 prioritized가 있습니다. **prioritized는 attribute-based instance type selection과 함께 쓸 수 없습니다.** `capacity-optimized-prioritized`로 지정한 우선순위는 On-Demand 전략이 prioritized일 때 On-Demand에도 그대로 적용됩니다.

Auto Scaling group의 mixed instances group에도 같은 전략이 들어갑니다. 콘솔에서 만들 때 Spot 할당 전략의 기본 선택은 price capacity optimized이고, **attribute-based instance type selection을 쓰면 On-Demand 할당 전략은 Lowest price로 고정되어 바꿀 수 없습니다.**

attribute-based instance type selection은 인스턴스 타입 목록 대신 vCPU와 메모리 같은 속성으로 후보를 정하는 방식입니다. pool 수를 자동으로 넓히므로 Spot 회복력의 첫 수단이 됩니다. 제약이 몇 가지 있습니다.

| 항목 | 값 |
| :--- | :--- |
| 인스턴스 타입과 속성 동시 지정 | 불가능 |
| `InstanceRequirements` 구조 | 요청당 최대 4개 |
| `DesiredCapacityType` | `units`(기본), `vcpu`, `memory-mib` |
| On-Demand price protection 기본값 | 식별된 On-Demand 가격 대비 20% 초과까지 |
| Spot price protection | 기본적으로 자동 적용된다 |

price protection의 기준 가격은 지정한 속성을 만족하는 최저가 현세대 C, M, R 인스턴스 가격입니다.

On-Demand base capacity는 그룹 초기 용량 중 On-Demand로 채워야 하는 최소량이고, 그 위 용량은 instances distribution 비율을 따릅니다. baseline은 On-Demand로 고정하고 초과분만 Spot으로 받는 구성이 이 값으로 표현됩니다.

---

## 11. 배치 전략마다 넘지 못하는 경계가 다르다

placement group은 인스턴스를 물리적으로 어떻게 배치할지 지정하는 논리 그룹입니다. 전략은 cluster, partition, spread, precision time 네 가지이고 **생성 비용이 없습니다.** precision time은 지원 하드웨어에서 AWS 인프라의 고정밀 시간 소스에 직접 접근하게 하며, placement-group Capacity Reservation은 cluster와 precision time에서 만들 수 있습니다. 아래 표는 시험에서 자주 비교하는 cluster, partition, rack-level spread 세 가지를 정리합니다.

{% include diagrams/static/sap-c02/placement-group-boundaries.html %}
{% include diagrams/download.html png="/assets/img/diagrams/static/sap-c02/placement-group-boundaries--cdc5a9aebf633cff.png" %}

그림은 두 개의 Availability Zone 상자 안에 세 전략을 나란히 놓은 배치입니다. 왼쪽 열은 요구 세 가지이고 각각 저지연과 고대역, 랙 단위 장애 격리, 인스턴스 단위 하드웨어 분리입니다. cluster는 한쪽 AZ 상자 안에만 있고, 그 옆의 붉은 상자가 AZ 경계를 넘지 못한다는 사실을 표시합니다. partition과 rack-level spread는 두 AZ 상자에 각각 놓여 여러 AZ에 걸칠 수 있다는 뜻입니다.

세 전략의 한도를 표로 고정합니다.

| 축 | cluster | partition | rack-level spread |
| :--- | :--- | :--- | :--- |
| AZ 범위 | **단일 AZ를 넘지 못한다** | 여러 AZ 가능 | 여러 AZ 가능 |
| 규모 한도 | 계정 한도. 단 용량 확보가 어렵다 | AZ당 7 파티션, 인스턴스는 계정 한도 | **AZ당 running 인스턴스 7대** |
| 목적 | 저지연 고대역 | 랙 단위 장애 격리 | 인스턴스 단위 하드웨어 격리 |
| Capacity Reservation | **가능** | 불가능 | 불가능 |
| Dedicated Instances | 해당 없음 | 최대 2 파티션 | 지원하지 않는다 |
| 대표 워크로드 | HPC, MPI, 대형 배치 | HDFS, HBase, Cassandra, Kafka | 소수의 핵심 인스턴스 |

cluster는 같은 리전의 peered VPC는 걸칠 수 있습니다. AZ 경계만 넘지 못합니다. 네트워크 성능은 enhanced networking 인스턴스 기준으로 그룹 안 single-flow가 최대 10 Gbps, 그룹 밖이 최대 5 Gbps이고, 인터넷과 Direct Connect 방향 트래픽은 5 Gbps로 제한됩니다.

cluster에는 지원하지 않는 타입이 있습니다. burstable(T2 등), Mac1, M7i-flex는 넣을 수 없습니다. 여러 인스턴스 타입을 섞으면 insufficient capacity 확률이 올라가므로 단일 launch request와 동일 타입이 권장이고, 용량 에러가 나면 그룹의 모든 인스턴스를 stop 후 start해 다른 하드웨어로 이동시키라고 문서가 안내합니다.

spread에는 rack-level과 host-level 두 가지가 있고 **host-level spread는 AWS Outposts에서만 지원됩니다.** 시험에서 말하는 AZ당 7대 상한은 rack-level 기준입니다. AZ 3개 리전이면 그룹 전체로 21대입니다.

partition은 인스턴스가 자기 파티션 번호를 메타데이터로 읽을 수 있어서, 애플리케이션이 복제본을 서로 다른 파티션에 배치하도록 스스로 조정할 수 있습니다.

**partition과 spread는 고유 하드웨어가 부족하면 launch 또는 start 요청 자체가 실패합니다.** 조용히 같은 랙에 몰아넣지 않습니다.

---

## 12. placement group에 겹칠 수 있는 것과 없는 것

배치 전략을 고른 다음 그 위에 무엇을 겹칠 수 있는지가 두 번째 판정입니다.

| 겹치려는 것 | 가능 여부 |
| :--- | :--- |
| Capacity Reservation | placement group 안에서는 cluster 또는 precision time에 만들 수 있다. spread와 partition에는 용량이 예약되지 않으며, 일반 ODCR은 placement group 없이도 만들 수 있다 |
| zonal Reserved Instance | placement group 안에 용량을 명시적으로 예약하지 못한다 |
| Capacity Blocks | placement group을 지원하지 않는다 |
| Dedicated Host | placement group에 띄울 수 없다 |
| Dedicated Instances | partition은 최대 2개, spread는 지원하지 않는다 |
| 중단 시 stop 또는 hibernate로 설정한 Spot | placement group에 띄울 수 없다 |

마지막 줄이 Spot과 placement group을 엮는 선지를 통째로 무효로 만듭니다. 그리고 애초에 placement group은 중단 확률과 아무 관계가 없습니다.

인스턴스는 한 번에 하나의 placement group에만 속하고 group끼리 병합할 수 없습니다. 이미 실행 중인 인스턴스를 그룹에 넣거나 다른 그룹으로 옮기려면 **인스턴스가 `stopped` 상태여야 합니다.**

```bash
aws ec2 modify-instance-placement --instance-id i-1234567890abcdef0 --group-name my-cluster-pg
aws ec2 modify-instance-placement --instance-id i-1234567890abcdef0 --group-name ""
```

빈 문자열을 넘기는 것이 그룹에서 제거하는 방법입니다.

---

## 13. EC2 기본 메트릭에 없는 값과 자동 복구가 살리지 못하는 장애

`AWS/EC2` 네임스페이스가 인스턴스에 대해 제공하는 메트릭은 정해져 있습니다.

| 분류 | 메트릭 |
| :--- | :--- |
| CPU | `CPUUtilization` |
| 디스크 | `DiskReadOps`, `DiskWriteOps`, `DiskReadBytes`, `DiskWriteBytes` |
| 네트워크 | `NetworkIn`, `NetworkOut`, `NetworkPacketsIn`, `NetworkPacketsOut` |
| 메타데이터 | `MetadataNoToken`, `MetadataNoTokenRejected` |

**메모리 사용률과 디스크 여유 공간은 이 목록에 없습니다.** 두 값이 필요하면 CloudWatch agent로 custom metric을 올려야 합니다. 메모리 기준 target tracking을 추가 구성 없이 설정하겠다는 선지는 여기서 탈락합니다.

디스크 메트릭에도 함정이 있습니다. `DiskReadOps`와 `DiskWriteOps`는 **instance store 볼륨만 집계합니다.** instance store가 없으면 값이 0이거나 아예 보고되지 않습니다. EBS 트래픽은 Nitro 인스턴스 한정으로 `EBSReadOps`, `EBSWriteOps`, `EBSReadBytes`, `EBSWriteBytes`가 따로 나옵니다.

수집 주기도 문항 재료입니다.

| 대상 | 주기 |
| :--- | :--- |
| 기본 모니터링 | 5분 |
| 상세 모니터링 | 1분 |
| status check 메트릭 | 기본 1분, 추가 비용 없음 |
| CPU credit 메트릭 | 5분만 제공 |

status check 메트릭은 `StatusCheckFailed`와 `StatusCheckFailed_Instance`, `StatusCheckFailed_System`, `StatusCheckFailed_AttachedEBS`입니다.

자동 복구는 두 가지 방식이 있습니다. **simplified automatic recovery는 지원 인스턴스에서 기본으로 켜져 있고**, CloudWatch action based recovery는 수동 구성이 필요합니다. 결정적인 제약은 하나입니다.

**자동 복구는 system status check 실패에만 동작합니다.** instance status check만 실패하면 동작하지 않습니다. 애플리케이션 계층 장애를 자동 복구가 되살린다는 선지는 그래서 틀리고, 그 자리는 ELB health check와 Auto Scaling group의 교체가 담당합니다.

복구 후 보존되는 것과 소실되는 것도 정리해 둡니다.

| 구분 | 항목 |
| :--- | :--- |
| 보존된다 | instance ID, public과 private과 Elastic IP, instance metadata, placement group, 연결된 EBS 볼륨, Availability Zone |
| 소실된다 | RAM 데이터, OS uptime. CloudWatch action based recovery에서는 instance store 데이터도 소실된다 |

simplified automatic recovery는 metal 사이즈를 지원하지 않고, 시작 시 instance store 볼륨을 붙이는 인스턴스도 지원하지 않습니다. CloudWatch action based recovery는 이 두 경우를 일부 지원합니다.

---

## 14. 스케일링 정책 네 종류와 desired capacity가 정해지는 방식

Auto Scaling group의 스케일링 정책은 네 가지이고 서로 배타적이지 않습니다.

| 축 | target tracking | step scaling | simple scaling | predictive scaling |
| :--- | :--- | :--- | :--- | :--- |
| 트리거 | 목표 지표값 | CloudWatch 알람 구간 | CloudWatch 알람 1개 | 시계열 예측 |
| cooldown | 쓰지 않는다 | 쓰지 않는다 | 쓴다. 기본 300초 | 해당 없음 |
| 대기 제어 | instance warmup | instance warmup | cooldown | default instance warmup 권장 |
| scale in | 가능. 비활성화 옵션 있음 | 가능 | 가능 | **하지 않는다** |
| 선행 데이터 | 필요 없음 | 필요 없음 | 필요 없음 | 최소 24시간 |
| 문서 권장도 | 최우선 권장 | 세밀 제어가 필요할 때 | 비권장 | dynamic과 병행 전제 |

여러 정책이 동시에 활성이면 **각 정책이 독립적으로 desired capacity를 계산하고 그중 최댓값이 채택됩니다.** target tracking이 10대를 계산하고 predictive가 8대를 계산했다면 결과는 10대입니다. 이 규칙 때문에 predictive scaling을 추가해도 기존 target tracking이 무력화되지 않고, 예측을 벗어난 실제 부하는 target tracking이 그대로 처리합니다.

기본적으로 스케일링 정책은 그룹 최대 용량을 넘지 못합니다. `MaxCapacityBreachBehavior`와 `MaxCapacityBuffer`로 자동 상향을 허용할 수 있는데, **올라간 최대 용량은 자동으로 되돌아오지 않습니다.**

---

## 15. predictive scaling이 하는 일과 하지 않는 일

predictive scaling은 과거 메트릭을 분석해 앞으로의 용량을 예측하고 미리 확장합니다. 부팅과 워밍이 긴 애플리케이션에서 반응형 정책만으로는 따라잡지 못하는 급경사 구간을 메우는 수단입니다.

| 항목 | 값 |
| :--- | :--- |
| 예측 시작에 필요한 데이터 | 최소 24시간 |
| 분석 기간 | 과거 최대 14일 |
| 예측 범위 | 향후 48시간, 시간 단위 |
| 예측 갱신 주기 | 6시간 |
| 정확도 | 2주치 데이터가 있을 때 더 좋다 |
| 사전 기동 | `SchedulingBufferTime`(콘솔의 Pre-launch instances) |

**초기 모드는 forecast only입니다.** 예측만 만들고 실제로 스케일하지 않습니다. forecast and scale로 바꿔도 하지 않는 일이 하나 남습니다.

**predictive scaling은 부하 감소 예측에 대해 scale in을 하지 않습니다.** 야간 축소는 dynamic scaling 정책이 담당합니다. predictive만 붙여 놓고 축소까지 자동화했다고 판단하는 것이 전형적인 오답입니다.

기본 동작은 매 정시에 그 시간대 예측에 맞춰 스케일하는 것이고, 워밍에 6분이 걸린다면 `SchedulingBufferTime`으로 그만큼 앞당겨 띄웁니다.

적용 조건에도 제약이 있습니다. predictive scaling은 **그룹이 균질하다고 가정합니다.** 인스턴스 타입마다 vCPU 수나 네트워크 대역이 다른 mixed instances group에서는 예측 용량이 부정확해질 수 있습니다. 지원 리전도 목록으로 한정되어 있습니다.

새 그룹에 predictive scaling을 걸고 다음 피크부터 효과를 보겠다는 계획도 성립하지 않습니다. 최소 24시간이 쌓여야 예측이 시작되고, 기존 그룹을 교체하면 이력이 초기화되므로 custom metric으로 이어 붙여야 합니다.

---

## 16. target tracking이 받아들이는 메트릭의 조건

target tracking은 지정한 지표를 목표값 근처로 유지하도록 용량을 조절합니다. 사전 정의 메트릭은 네 가지입니다.

| 메트릭 | 비고 |
| :--- | :--- |
| `ASGAverageCPUUtilization` | 가장 흔한 기본값 |
| `ASGAverageNetworkIn` | |
| `ASGAverageNetworkOut` | |
| `ALBRequestCountPerTarget` | `ResourceLabel`로 대상 타깃 그룹을 지정해야 한다 |

여기서 답이 갈리는 규칙은 하나입니다. **메트릭 값이 인스턴스 수에 비례해 변해야 합니다.** 인스턴스를 늘리면 값이 내려가야 수렴합니다. 이 조건을 만족하지 않는 지표를 쓰면 최대치까지 확장했다가 급격히 축소하는 진동이 생깁니다.

문서가 직접 지목해 배제하는 메트릭이 셋 있습니다.

- ELB `RequestCount`
- ELB `Latency`
- SQS `ApproximateNumberOfMessagesVisible`

큐 기반 워커를 확장할 때의 정답은 **큐 길이를 InService 인스턴스 수로 나눈 backlog per instance custom metric**입니다. 인스턴스를 늘리면 값이 내려가므로 비례 조건을 만족합니다.

동작에 관한 제약도 몇 가지 있습니다.

- target tracking은 지표가 목표값보다 **높을 때 확장하는** 모델이다. 목표값보다 낮을 때 확장하도록 쓸 수 없다.
- scale-in 부분만 일시 비활성화할 수 있다.
- 여러 target tracking 정책이 있으면 하나라도 확장 조건이면 확장하고, 전부 축소 조건일 때만 축소한다.
- 정책이 만드는 CloudWatch 알람을 직접 생성, 수정, 삭제하면 안 된다.
- 메트릭에 데이터가 없으면 알람이 `INSUFFICIENT_DATA`가 되고 스케일링이 멈춘다.

마지막 항목은 custom metric으로 스케일하는 구성에서 실제로 만나는 장애입니다. 지표 게시가 끊기면 축소도 확장도 일어나지 않습니다.

---

## 17. grace period와 instance warmup과 cooldown은 서로 다른 시계다

이름이 비슷한 대기 시간 개념이 셋 있고 각각 다른 것을 늦춥니다.

| 축 | health check grace period | instance warmup | cooldown |
| :--- | :--- | :--- | :--- |
| 무엇을 늦추나 | unhealthy 판정 | 신규 인스턴스의 메트릭 반영 | 다음 simple scaling 활동 |
| 기본값 | 콘솔 300초, CLI와 SDK 0초 | default instance warmup 값 | 300초 |
| 적용 정책 | 전 정책 공통 | target tracking과 step scaling | simple scaling |

**cooldown은 simple scaling 정책에만 적용됩니다.** target tracking과 step scaling은 cooldown을 기다리지 않고 즉시 확장하며 대신 instance warmup을 씁니다. scheduled action도 cooldown을 기다리지 않고, unhealthy 인스턴스 교체도 기다리지 않습니다.

cooldown의 시작 시점도 함정입니다. ELB의 기본 deregistration delay가 300초이고, **ASG는 종료 대상이 deregister를 시작한 시점부터 cooldown을 셉니다.** 두 값이 겹쳐 축소 반응이 예상보다 느려지는 구성이 여기서 나옵니다.

문서는 simple scaling과 scaling cooldown 자체를 쓰지 말라고 권고하고 target tracking을 우선 권장합니다. cooldown을 짧게 줘서 반응 속도를 높이겠다는 선지는 문서 권장과 반대 방향입니다.

health check grace period는 CLI와 SDK에서 만들면 기본값이 0이고, 0은 grace period를 끄는 값입니다. 신규 launch, standby에서 복귀한 인스턴스, 수동 attach한 인스턴스에 적용됩니다. 그리고 grace period 중이라도 **인스턴스가 EC2 `running` 상태를 벗어나면 즉시 `Unhealthy`로 표시되고 교체됩니다.** grace period가 모든 판정을 유예하지는 않습니다.

launch lifecycle hook을 쓰면 초기화 완료를 hook이 보증하므로 grace period를 0으로 둘 수 있습니다.

---

## 18. warm pool부터 종료까지 인스턴스가 지나는 상태

Auto Scaling group 안에서 인스턴스는 정해진 상태를 지나갑니다. lifecycle hook은 그 경로의 두 자리에만 대기를 만들 수 있습니다.

{% include diagrams/static/sap-c02/asg-instance-lifecycle-hooks.html %}
{% include diagrams/download.html png="/assets/img/diagrams/static/sap-c02/asg-instance-lifecycle-hooks--ff141a18d4ef0097.png" %}

그림은 warm pool에서 출발해 Pending, Pending:Wait, InService를 지나고 Terminating, Terminating:Wait, Terminated로 이어지는 상태 경로입니다. Pending:Wait과 Terminating:Wait 두 자리에서 각각 lifecycle hook 결과 상자로 점선이 나가고, 결과가 CONTINUE인지 ABANDON이나 timeout인지에 따라 다음 행선지가 갈립니다. Spot 중단 상자에서 나오는 점선은 hook 자리를 거치지 않고 종료로 직행합니다. unhealthy 신호 소스 상자는 Terminating으로 들어가는 입력입니다.

**lifecycle hook**의 기본값과 제약입니다.

| 항목 | 값 |
| :--- | :--- |
| 기본 heartbeat timeout | 1시간(3600초) |
| 전체 대기 상한 | 48시간과 heartbeat timeout의 100배 중 작은 값 |
| 결과값 | `CONTINUE`, `ABANDON` |
| termination hook 기본 성격 | best effort. timeout되거나 abandon되면 즉시 종료로 진행한다 |
| 적용되지 않는 동작 | attach와 detach, standby 이동, force delete |

**warm pool**은 부팅과 초기화를 미리 끝낸 인스턴스를 대기시켜 확장 지연을 줄이는 수단입니다.

| 항목 | 값 |
| :--- | :--- |
| 상태 | `Stopped`, `Running`, `Hibernated` |
| 기본 크기 | 그룹 max capacity 빼기 desired capacity |
| 크기 조정 | `MaxGroupPreparedCapacity`, `MinSize` |
| 권장 상태 | `Stopped`. `Running`은 문서가 강하게 비권장한다 |

warm pool의 제약이 문항을 만듭니다.

- instance weighting을 쓰는 mixed instances group에는 붙일 수 없다.
- **mixed instances group에서 Spot을 지원하지 않으므로 On-Demand 전용으로 구성해야 한다.**
- 루트 장치가 instance store인 인스턴스는 stop과 hibernate가 불가능하다.
- instance refresh는 InService 인스턴스를 먼저 교체하고 warm pool을 나중에 교체한다.

부팅이 긴 Spot 워크로드를 warm pool로 가속하겠다는 구성은 두 번째 항목에서 막힙니다.

**unhealthy 신호**의 소스는 다섯 가지입니다. Amazon EC2 status check, Elastic Load Balancing, VPC Lattice, Amazon EBS, 그리고 사용자 정의 custom health check입니다. 모든 인스턴스는 `Healthy`로 시작하고 통지가 오기 전까지 healthy로 가정됩니다.

---

## 19. instance refresh 기본값이 용량을 10% 깎는다

instance refresh는 launch template 변경을 그룹 전체에 순차 적용하는 기능입니다. 별도 배포 도구 없이 AMI 교체를 굴릴 때 쓰는 경로이고, 기본값을 알아야 답이 갈립니다.

instance maintenance policy가 없을 때의 기본값입니다.

| 항목 | 기본값 |
| :--- | :--- |
| minimum healthy percentage | **90%** |
| maximum healthy percentage | 100% |
| auto rollback | 비활성 |
| bake time | 0 |
| checkpoints | 비활성 |
| checkpoint delay | 3600초 |
| instance warmup | default instance warmup. 없으면 health check grace period |

**minimum healthy percentage 90%는 교체 중 용량이 10%까지 줄어든다는 뜻입니다.** 배포 중에도 용량을 유지해야 한다는 요건이 있으면 기본값으로는 충족되지 않습니다. minimum healthy percentage를 100%로 올려 launch before terminate 동작으로 바꾸고, maximum healthy percentage로 일시 초과분을 허용해야 합니다.

auto rollback도 기본이 비활성입니다. 지표 악화 시 자동으로 이전 launch template 버전으로 되돌리려면 auto rollback을 켜고 CloudWatch 알람을 지정합니다.

콘솔과 CLI의 기본값이 서로 다른 항목이 있습니다.

| 항목 | CLI와 SDK | 콘솔 |
| :--- | :--- | :--- |
| skip matching | 비활성 | 활성 |
| standby와 scale-in protected 인스턴스 처리 | `Wait`(1시간 기다린 뒤 실패) | `Ignore` |

콘솔에서 성공하던 refresh가 자동화 스크립트에서 1시간 뒤 실패하는 구성이 여기서 나옵니다.

---

## 20. instance maintenance policy가 지켜주지 못하는 세 경우

instance maintenance policy는 유지보수 이벤트 중 그룹 용량이 어디까지 흔들려도 되는지를 정합니다. 콘솔 옵션은 Launch before terminating, Terminate and launch, Custom policy 세 가지입니다.

| 항목 | 유효 범위 | 어디서 설정하나 |
| :--- | :--- | :--- |
| minimum healthy percentage | 0-100% | Terminate and launch, Custom |
| maximum healthy percentage | 100-200% | Launch before terminating, Custom |

정책이 없을 때의 기본 동작은 이벤트마다 다릅니다.

| 이벤트 | 기본 동작 |
| :--- | :--- |
| health check 실패 | terminate and launch |
| instance refresh | terminate and launch |
| maximum instance lifetime | terminate and launch |
| rebalancing | **launch before terminating** |

rebalancing만 예외라는 점이 자주 틀립니다. 그리고 rebalancing의 초과 허용치는 기준값이 둘로 갈립니다.

| 종류 | 초과 허용치 |
| :--- | :--- |
| AZ rebalancing | **maximum capacity**의 최대 10% |
| Capacity Rebalancing | **desired capacity**의 최대 10% |

max와 desired 차이가 큰 그룹에서는 두 값이 크게 벌어집니다.

정책을 걸어도 하한이 깨지는 경우가 셋 있습니다.

- 사람이 인스턴스를 직접 종료한 경우
- EC2 scheduled event로 reboot, stop, retire가 먼저 일어난 경우
- **Spot 중단으로 강제 종료된 경우**

세 경우 모두 terminate and launch로 떨어집니다. Spot 그룹에서 minimum healthy percentage로 용량 하한을 보장하겠다는 설계는 그래서 성립하지 않습니다.

warm pool이 있으면 min과 max healthy percentage가 ASG와 warm pool에 각각 따로 적용됩니다. desired 100에 warm pool 10인 그룹에 90%와 120% 정책이면 그룹은 90대에서 120대, warm pool은 9대에서 12대 범위에서 움직입니다.

instance maintenance policy는 유지보수 이벤트에만 적용되고 수동 스케일링과 자동 스케일링을 막지 않습니다. 스케일링 정책과 scheduled action은 유지보수 이벤트와 병렬로 돕니다.

max instance lifetime도 같은 층의 기능입니다. 최소값이 86,400초(1일)이고 0으로 해제합니다. 지정 값이 개별 교체에 충분하지 않으면 현재 용량의 최대 10%까지 동시에 교체될 수 있습니다. scale-in protection이 걸린 인스턴스는 수명이 지나도 종료되지 않고, 인스턴스가 1대인 그룹은 기본 동작이 종료 후 기동이라 공백이 생깁니다.

---

## 21. 어떤 인스턴스가 먼저 종료되는가

축소할 때 어느 인스턴스가 없어지는지는 termination policy가 정합니다. 기본 정책의 평가 순서는 다음과 같습니다.

1. AZ 사이 균형을 먼저 맞춘다.
2. 오래된 구성을 순서대로 고른다. launch configuration을 쓰는 인스턴스, 현재 template이 아닌 다른 launch template을 쓰는 인스턴스, 현재 template의 가장 오래된 버전 순이다.
3. 다음 과금 시간에 가장 가까운 인스턴스를 고른다.
4. 동률이면 무작위로 고른다.

mixed instances group에서는 앞에 두 단계가 더 붙습니다. 먼저 Spot과 On-Demand 중 어느 구매 옵션을 줄일지 정하고, 그다음 allocation strategy 정렬을 개선하는 인스턴스를 고릅니다.

**unhealthy로 표시된 인스턴스는 termination policy 평가를 건너뜁니다.** 정책이 무엇이든 먼저 없어집니다.

사전 정의 정책은 `Default`, `AllocationStrategy`, `OldestLaunchTemplate`, `OldestLaunchConfiguration`, `ClosestToNextInstanceHour`, `NewestInstance`, `OldestInstance` 일곱 가지입니다.

---

## 22. scaling process를 멈추면 다른 process가 어떻게 반응하는가

Auto Scaling group의 process는 개별로 일시중지할 수 있고 지원 대상은 아홉 가지입니다.

`Launch`, `Terminate`, `AddToLoadBalancer`, `AlarmNotification`, `AZRebalance`, `HealthCheck`, `InstanceRefresh`, `ReplaceUnhealthy`, `ScheduledActions`.

시험이 노리는 것은 목록이 아니라 **하나를 멈췄을 때 다른 process가 어떻게 반응하는가**입니다.

| 멈춘 process | 나타나는 결과 |
| :--- | :--- |
| `Launch` | `ReplaceUnhealthy`가 unhealthy 인스턴스를 종료하되 교체를 띄우지 않는다. 재개하면 그동안 종료된 인스턴스가 즉시 교체된다. `AZRebalance`는 멈추고 `InstanceRefresh`는 교체하지 않는다 |
| `Terminate` | `AZRebalance`가 그대로 활성이라 기존 인스턴스를 종료하지 않고 새로 띄운다. 그룹이 최대 크기보다 최대 10% 큰 상태로 재개 시점까지 유지될 수 있다. `HealthCheck`는 계속 동작해 unhealthy 표시가 쌓이고 재개 즉시 일괄 교체된다 |
| `HealthCheck` | EC2와 ELB 기반 unhealthy 표시만 멈춘다. **custom health check는 계속 동작한다** |
| `AddToLoadBalancer` | 중지 기간에 뜬 인스턴스는 재개 후에도 자동 등록되지 않는다. 수동 등록이 필요하다 |

축소를 막으려고 `Terminate`를 중지하는 구성이 전형적인 오답입니다. 실제로는 `AZRebalance`가 인스턴스를 계속 띄워 그룹이 커집니다. 축소를 막으려면 scale-in protection이나 target tracking의 scale-in 비활성화입니다. unhealthy 교체 자체를 막으려면 `HealthCheck`가 아니라 `ReplaceUnhealthy`를 중지합니다. `ReplaceUnhealthy`는 내부적으로 `Terminate`를 먼저 호출하고 `Launch`를 나중에 호출합니다.

Spot이 섞여 있으면 결과가 또 달라집니다. **`Terminate`를 중지해도 Spot 용량이 사라지면 Spot 인스턴스는 그대로 종료됩니다.** `Launch`를 중지하면 다른 Spot pool에서 대체 인스턴스를 띄우지 못합니다. `Launch`나 `Terminate`가 중지되면 max instance lifetime도 교체를 수행하지 못합니다.

사용자가 걸지 않은 administrative suspension도 있습니다. **24시간 넘게 인스턴스 launch를 시도했는데 한 대도 성공하지 못한 그룹**에 주로 적용되고 사용자가 resume할 수 있습니다. 인스턴스가 하나도 뜨지 않는데 그룹이 아무 시도도 하지 않는 상황이면 이 상태를 의심합니다.

---

## 23. EFA와 cluster placement group과 AWS Batch multi-node parallel job

HPC 워크로드는 노드 간 통신 지연이 전체 실행 시간을 좌우합니다. 이 구간에 쓰는 수단이 셋 있고 각각 넘지 못하는 경계가 있습니다.

**Elastic Fabric Adapter**는 Libfabric API로 커널을 우회하는 OS-bypass 장치이고 SRD 프로토콜을 씁니다. 지원 스택은 Open MPI 4.1 이상, Intel MPI 2019 Update 5 이상, NCCL 2.4.2 이상, NIXL 1.0.0 이상, AWS Neuron SDK 2.3 이상이고 **추가 비용이 없습니다.**

결정적인 제약은 하나입니다. **EFA 트래픽은 Availability Zone과 VPC를 넘을 수 없고 라우팅되지 않습니다.** 같은 인터페이스의 ENA 장치를 통한 일반 IP 트래픽은 정상적으로 라우팅됩니다. AZ를 걸친 MPI 클러스터를 EFA로 구성하겠다는 선지는 여기서 탈락하고, 그래서 EFA와 단일 AZ cluster placement group이 한 쌍으로 나옵니다. EFA는 AWS Outposts에서 지원되지 않습니다.

인터페이스 형태가 두 가지입니다.

| 축 | ENA | EFA with ENA | EFA-only |
| :--- | :--- | :--- | :--- |
| IP 네트워킹 | 지원한다 | 지원한다 | 지원하지 않는다 |
| IPv4와 IPv6 주소 | 가능 | 가능 | 불가능 |
| primary network interface | 가능 | 가능 | 불가능 |
| AZ 간 통신 | 가능 | ENA 경로만 가능 | 불가능 |

지원 OS는 Amazon Linux 2023, RHEL 8과 9와 10, Debian 11과 12와 13, Rocky Linux 8과 9, Ubuntu 22.04와 24.04와 26.04, SLES 15 SP2 이상입니다. Windows에서는 AWS CDI SDK 기반 애플리케이션에만 EFA 장치가 동작하고 그 외에는 ENA로만 동작합니다.

다중 network card를 지원하는 인스턴스는 카드당 EFA 1개를 붙일 수 있고 나머지는 인스턴스당 1개입니다. `c7g.16xlarge`, `m7g.16xlarge`, `r7g.16xlarge`는 EFA를 붙이면 Dedicated Instances와 Dedicated Hosts를 쓸 수 없습니다.

**AWS Batch multi-node parallel job**은 단일 job이 여러 EC2 인스턴스에 걸쳐 실행되는 gang scheduling입니다. 노드는 single-tenant라 인스턴스당 job 컨테이너 하나만 돕니다. 최종 상태는 main node 상태로 결정되고 main node가 끝나면 child node가 모두 정지합니다.

제약이 문항을 만듭니다.

- **`UNMANAGED` compute environment에서 지원되지 않는다.**
- **Spot Instances를 쓰는 compute environment에서 지원되지 않는다.**
- 단일 AZ에 cluster placement group을 만들어 compute resource에 연결하라고 문서가 권고한다.
- ECS `awsvpc` 네트워크 모드를 쓰고 ENI에 공인 IP가 붙지 않는다. 아웃바운드가 필요하면 NAT gateway가 있는 private subnet에 둔다. public subnet의 compute resource는 아웃바운드 접근이 없다.
- compute environment의 보안 그룹은 최대 5개이고 launch template의 보안 그룹은 무시된다.

multi-node parallel job을 Spot으로 돌려 비용을 줄이겠다는 구성은 두 번째 항목에서 성립하지 않습니다.

네트워크 대역폭 수치에 대해서는 주의가 필요합니다. 현행 ENA 문서는 단일 Gbps 상한을 제시하지 않고 Nitro 버전별로 능력이 다르다고만 적으면서 실제 대역폭을 인스턴스 패밀리별 network specification 페이지로 넘깁니다. 특정 숫자를 기억해 두고 그 숫자로 선지를 고르는 접근은 위험합니다. ENA의 전제 조건이 Nitro 기반 인스턴스라는 사실이 더 안전한 판단 근거입니다.

---

## 24. 암기해야 하는 하드 리밋과 동작 제약

시험에서는 서비스 이름보다 아래의 값과 예외가 선지를 자릅니다.

**구매와 배치**

| 항목 | 값 또는 제약 |
| :--- | :--- |
| 구매 옵션 | On-Demand, Savings Plans, Reserved Instances, Spot, Dedicated Hosts, Dedicated Instances, Capacity Reservations |
| Savings Plans 약정 | 1년 또는 3년. All upfront, Partial upfront, No upfront |
| Savings Plans 최대 할인 | Compute 66%, EC2 Instance 72% |
| regional RI | 용량 예약 없음. AZ와 size 유연성 있음 |
| zonal RI | 지정 AZ 용량 예약. AZ와 size 유연성 없음 |
| ODCR | 지정 AZ 용량 예약. 자체 할인 없음. 즉시 사용형은 term commitment 없음 |
| future-dated Capacity Reservation | 최소 32 vCPU. C, G, I, M, R, T, U, X 패밀리 |
| Capacity Blocks for ML | 미래의 특정 날짜부터 GPU 클러스터를 정한 기간 동안 확보 |
| partition placement group | AZ당 최대 7개 partition |
| rack-level spread | AZ당 running 인스턴스 최대 7대 |
| cluster placement group | 단일 AZ. Capacity Reservation 연계 가능 |

**Spot과 Auto Scaling**

| 항목 | 값 또는 제약 |
| :--- | :--- |
| Spot 중단 통지 | stop 또는 terminate는 2분 전. hibernate도 통지는 오지만 2분 전 경고 없이 즉시 시작 |
| Spot 신호 | EventBridge interruption warning, 인스턴스 메타데이터, rebalance recommendation |
| Capacity Rebalancing | 새 인스턴스가 health check를 통과한 뒤 기존 인스턴스를 종료. desired capacity의 최대 10%까지 일시 초과 |
| predictive scaling | 최소 24시간 데이터, 최대 14일 분석, 향후 48시간 예측, 6시간마다 갱신. scale-in 없음 |
| target tracking | 지표가 인스턴스 수에 비례해야 함. SQS 큐 길이와 ELB RequestCount와 Latency는 부적합 |
| simple scaling | 기본 cooldown 300초. 문서는 target tracking을 우선 권장 |
| health check grace period | 콘솔 생성 기본 300초, CLI와 SDK 생성 기본 0초 |
| lifecycle hook | heartbeat 기본 1시간. 전체 대기는 48시간과 heartbeat 100배 중 작은 값 |
| instance refresh 기본 | minimum healthy 90%, maximum healthy 100%, auto rollback 비활성 |
| warm pool | Stopped, Running, Hibernated. mixed instances group의 Spot과 instance weighting은 미지원 |
| max instance lifetime | 최소 86,400초, 0으로 해제 |

**EC2 관측과 복구**

| 항목 | 값 또는 제약 |
| :--- | :--- |
| 기본 모니터링 | 5분 주기. 상세 모니터링은 1분 |
| 기본 메트릭에 없는 값 | 메모리 사용률, 디스크 여유 공간 |
| instance store 디스크 메트릭 | DiskReadOps, DiskWriteOps, DiskReadBytes, DiskWriteBytes |
| 자동 복구 | system status check 실패에만 동작. instance status check 실패에는 동작하지 않음 |
| 복구 후 보존 | instance ID, IP, EBS, placement group, AZ |
| 복구 후 소실 | RAM과 OS uptime. action based recovery에서는 instance store도 소실 |

수치가 비슷해 보여도 기준이 다릅니다. Capacity Rebalancing의 10%는 desired capacity 기준이고 AZ rebalancing의 10%는 maximum capacity 기준입니다. regional RI의 유연성은 zonal RI의 용량 예약과 교환 관계이며, ODCR을 선택하면 할인은 별도로 겹쳐야 합니다.

---

## 25. 답이 갈리는 짝 비교

| 짝 | 차이를 만드는 제약 |
| :--- | :--- |
| Compute Savings Plans 대 EC2 Instance Savings Plans | 전자는 리전과 패밀리와 Fargate와 Lambda에 유연하고, 후자는 리전과 패밀리를 고정하며 EC2만 덮는다 |
| Savings Plans 대 ODCR | 전자는 사용량 요금을 할인하고 용량을 예약하지 않는다. 후자는 용량을 예약하고 자체 할인은 없다 |
| regional RI 대 zonal RI | regional은 AZ와 size 유연성이 있고 용량을 예약하지 않는다. zonal은 지정 AZ 용량을 예약하고 유연성이 없다 |
| Standard RI 대 Convertible RI | Standard는 exchange 불가지만 Marketplace 매각 가능. Convertible은 exchange 가능하지만 Marketplace 거래 불가 |
| Dedicated Host 대 Dedicated Instance | Host는 소켓과 코어와 host affinity를 노출하고 BYOL 범위가 넓다. Instance는 물리 정보와 affinity가 없다 |
| On-Demand Capacity Reservation 대 Capacity Blocks for ML | ODCR은 기간 제약 없는 AZ 용량 예약. Capacity Blocks는 날짜가 정해진 GPU 클러스터 예약 |
| cluster 대 partition placement group | cluster는 한 AZ에서 저지연을 얻고 partition은 랙 단위 장애를 격리한다 |
| partition 대 rack-level spread | partition은 AZ당 7개 파티션과 계정 한도 인스턴스를 갖고, spread는 AZ당 running 7대 상한이다 |
| price-capacity-optimized 대 lowest-price | 전자는 가격과 용량을 함께 보고, 후자는 싼 pool을 골라 Capacity Rebalancing과 함께 쓰면 재중단 위험이 커진다 |
| rebalance recommendation 대 interruption notice | 전자는 중단 위험 증가를 미리 알리는 신호이고, 후자는 stop 또는 terminate 2분 전 통지다 |
| target tracking 대 simple scaling | 전자는 목표 지표와 instance warmup을 쓰고, 후자는 알람과 cooldown을 쓴다 |
| predictive scaling 대 dynamic scaling | 전자는 예측에 따라 사전 확장만 하고, 후자는 실제 메트릭에 따라 확장과 축소를 한다 |
| health check grace period 대 instance warmup | 전자는 unhealthy 판정을 늦추고, 후자는 신규 인스턴스 메트릭 반영을 늦춘다 |
| lifecycle hook 대 instance refresh | hook은 상태 전이에 대기 지점을 만들고, refresh는 launch template 구성을 그룹 전체에 교체한다 |
| instance refresh 대 max instance lifetime | refresh는 지금 시작하는 구성 교체이고, lifetime은 수명 만료 인스턴스를 위생적으로 교체하는 기능이다 |
| warm pool 대 Capacity Rebalancing | warm pool은 일반적인 기동 시간을 줄이고, Capacity Rebalancing은 Spot 중단 전에 대체 인스턴스를 띄운다 |
| EFA 대 ENA | EFA는 Libfabric과 SRD 기반 저지연 통신이고 AZ와 VPC 경계를 넘지 않는다. ENA의 일반 IP 트래픽은 라우팅된다 |

---

## 26. 그럴듯하지만 성립하지 않는 조합

| 조합 | 성립하지 않는 이유 |
| :--- | :--- |
| Compute Savings Plans로 특정 AZ 용량을 보장한다 | Savings Plans는 요금 약정이고 용량 예약이 아니다. ODCR 또는 zonal RI가 필요하다 |
| regional RI로 발표일 특정 AZ의 capacity error를 막는다 | regional RI는 용량을 예약하지 않는다. 지정 AZ 용량이면 ODCR 또는 zonal RI다 |
| ODCR 하나로 요금 할인과 용량 예약을 동시에 얻는다 | ODCR에는 billing discount가 없다. Savings Plans나 regional RI를 별도로 적용한다 |
| zonal RI와 ODCR을 겹쳐 같은 인스턴스 용량을 두 번 예약한다 | zonal RI가 이미 지정 AZ 용량을 예약하므로 ODCR을 다시 잡을 이유가 없다. zonal RI 할인은 ODCR에 적용되지 않는다 |
| Dedicated Instance로 물리 코어 단위 BYOL을 추적한다 | Dedicated Instance는 소켓과 코어와 host affinity를 노출하지 않는다. Dedicated Host가 필요하다 |
| Dedicated Host를 placement group에 넣어 랙 배치를 제어한다 | Dedicated Host는 placement group을 지원하지 않는다 |
| 중단에 취약한 DB를 Spot으로 구성하고 lifecycle hook으로 보호한다 | hook은 중단을 막지 못하고 2분 안에 끝나야 한다. 중단 허용이 없으면 Spot 자체가 후보가 아니다 |
| Spot 최대 가격을 낮게 지정해 중단을 줄인다 | 최대 가격을 지정하면 지정하지 않을 때보다 중단이 잦아진다. pool 선택 전략으로 비용과 용량을 다룬다 |
| rack-level spread에 수백 대를 넣어 하드웨어를 분산한다 | AZ당 running 인스턴스가 7대까지라 규모가 맞지 않는다 |
| cluster placement group을 여러 AZ에 걸쳐 만든다 | cluster는 단일 AZ만 지원한다. AZ 장애 격리는 partition 또는 spread다 |
| predictive scaling만 붙여 야간 인스턴스를 줄인다 | predictive scaling은 scale-in을 하지 않는다. dynamic scaling 정책이 축소를 맡아야 한다 |
| SQS 전체 큐 길이를 target tracking 지표로 쓴다 | 인스턴스 수에 비례하지 않아 문서가 부적합하다고 지목한다. backlog per instance custom metric을 쓴다 |
| cooldown을 30초로 줄여 target tracking을 빠르게 만든다 | target tracking은 cooldown이 아니라 instance warmup을 쓴다. cooldown은 simple scaling에만 적용된다 |
| instance refresh 기본값으로 무중단 교체를 보장한다 | minimum healthy percentage 기본값이 90%라 용량이 10%까지 줄 수 있다 |
| Spot mixed instances group에 warm pool을 붙인다 | mixed instances group의 Spot과 instance weighting에서는 warm pool이 지원되지 않는다 |
| EC2 자동 복구가 애플리케이션 장애를 고친다 | 자동 복구는 system status check 실패에만 동작한다. 애플리케이션 장애는 health check와 ASG 교체가 처리한다 |
| EFA MPI 클러스터를 AZ 여러 곳에 나눈다 | EFA 트래픽은 AZ와 VPC를 넘지 못한다. 단일 AZ cluster placement group이 필요하다 |
| AWS Batch multi-node parallel job을 Spot compute environment에서 실행한다 | MNP는 Spot compute environment와 UNMANAGED compute environment에서 지원되지 않는다 |
| launch configuration에서 T3 unlimited를 설정한다 | launch configuration은 unlimited를 지원하지 않는다. launch template으로 전환해야 한다 |

---

## 27. 예상 문제 10문항

**Q1.** 한 상장사가 분기 실적 발표 당일 3시간 동안 투자자 포털 트래픽을 처리하기 위해 특정 Availability Zone에 `m6i.4xlarge` 300대를 확보해야 한다. 나머지 기간에는 같은 리전에서 시간당 40대 수준의 안정적인 baseline 사용량이 유지되며, 앞으로 3년간 이 baseline은 변하지 않을 전망이다. 과거 두 차례 발표일에 `InsufficientInstanceCapacity` 오류로 확장이 실패한 이력이 있다. 발표일 용량을 보장하면서 전체 컴퓨트 비용을 최소화하는 방법은 무엇인가. Choose the MOST cost-effective solution.

- A. baseline 40대 규모로 3년 Compute Savings Plans를 구매하고, 발표일에는 필요한 만큼 On-Demand 인스턴스를 시작한다.
- B. baseline 40대 규모로 3년 Compute Savings Plans를 구매하고, 발표일 시간대에 대해 대상 AZ에 targeted On-Demand Capacity Reservation을 생성한다.
- C. 발표일 최대 규모인 300대에 맞춰 3년 regional Reserved Instances를 구매한다.
- D. baseline과 발표일 용량을 모두 price-capacity-optimized 전략의 Spot Fleet으로 구성한다.

<details markdown="1">
<summary>정답과 해설</summary>

**정답: B**

Savings Plans와 Reserved Instances는 요금 할인 수단이고, 용량을 예약하는 수단은 zonal RI와 On-Demand Capacity Reservation입니다. 두 축이 분리되어 있으므로 baseline 할인은 Compute Savings Plans로, 발표일 AZ 용량은 targeted ODCR로 각각 확보합니다. ODCR 자체에는 할인이 없지만 그 위에 Savings Plans 요금이 적용됩니다.

- A가 틀린 이유: Savings Plans는 어떤 형태로도 용량을 예약하지 않습니다. 발표일에 On-Demand로 시작하면 과거에 겪은 `InsufficientInstanceCapacity`가 그대로 재현됩니다.
- C가 틀린 이유: regional RI는 AZ 유연성과 size 유연성을 주는 대신 용량을 예약하지 않습니다. 게다가 300대를 3년 약정하면 사용하지 않는 시간에 대한 약정 비용이 발생합니다.
- D가 틀린 이유: Spot 인스턴스는 EC2가 용량 회수를 위해 언제든 중단할 수 있어 용량 보장 요구를 충족하지 못합니다. Spot 사용분에는 Savings Plans도 적용되지 않습니다.

</details>

**Q2.** 한 이커머스 회사가 6개월간 운영해 온 Auto Scaling group에서 매일 오전 8시 50분부터 9시 10분 사이에 응답 지연이 발생한다고 보고한다. 애플리케이션 부팅과 캐시 워밍에 약 6분이 걸린다. 현재는 `ASGAverageCPUUtilization` target tracking 정책 하나만 붙어 있다. 일일 피크 규모는 마케팅 캠페인에 따라 매일 다르고, 야간에는 인스턴스를 최소 수준으로 줄여야 한다. Choose the MOST effective solution.

- A. 기존 target tracking 정책을 제거하고 predictive scaling 정책만 forecast and scale 모드로 구성한다.
- B. 기존 target tracking 정책을 유지한 채 predictive scaling 정책을 forecast and scale 모드로 추가하고, `SchedulingBufferTime`으로 사전 기동 시간을 확보한다.
- C. 기존 정책을 simple scaling으로 바꾸고 cooldown을 60초로 낮춘다.
- D. 매일 오전 8시 45분에 desired capacity를 고정 수치로 올리는 scheduled action을 추가한다.

<details markdown="1">
<summary>정답과 해설</summary>

**정답: B**

predictive scaling은 대상 메트릭의 과거 데이터를 분석해 시간 단위로 용량을 예측하고 매 정시에 미리 확장합니다. `SchedulingBufferTime`으로 예측 시점보다 이르게 인스턴스를 띄워 6분의 워밍 시간을 흡수할 수 있습니다. 여러 스케일링 정책이 동시에 활성이면 각 정책이 계산한 값 중 최댓값이 채택되므로, 예측을 벗어난 실제 부하는 기존 target tracking이 처리합니다.

- A가 틀린 이유: predictive scaling은 부하 감소 예측에 대해 scale in을 하지 않습니다. dynamic scaling 정책을 제거하면 야간 축소가 사라져 비용이 늘어납니다.
- C가 틀린 이유: simple scaling은 cooldown이 끝날 때까지 다음 스케일링 활동을 시작하지 않습니다. AWS 문서는 simple scaling과 scaling cooldown 사용 자체를 권장하지 않고 target tracking을 우선합니다.
- D가 틀린 이유: scheduled action은 고정 수치를 적용하므로 피크 규모가 매일 다른 조건을 충족하지 못합니다. 과소 설정이면 지연이 남고 과대 설정이면 비용이 늘어납니다.

</details>

**Q3.** 한 미디어 회사가 사용자 업로드 영상 트랜스코딩을 EC2 Spot 인스턴스 fleet으로 처리한다. 작업은 stateless이고 중단되면 다른 인스턴스가 같은 작업을 다시 집는다. 최근 단일 인스턴스 타입만 지정한 mixed instances policy를 쓰면서 Spot 중단이 몰려 처리 지연이 발생했다. 팀은 인스턴스 타입 제약이 없고, 처리량을 안정적으로 유지하려 한다. Choose the MOST resilient solution.

- A. Spot 최대 가격을 On-Demand 요금의 50%로 명시해 비용이 급등한 pool을 피한다.
- B. 단일 인스턴스 타입을 유지하되 인스턴스를 spread placement group에 배치해 하드웨어 장애를 분산한다.
- C. attribute-based instance type selection으로 vCPU와 메모리 요건을 만족하는 여러 타입을 후보로 두고, Spot 할당 전략을 price-capacity-optimized로 두며 Capacity Rebalancing을 활성화한다.
- D. 여러 인스턴스 타입을 후보로 두고 Spot 할당 전략을 lowest-price로 두며 Capacity Rebalancing을 활성화한다.

<details markdown="1">
<summary>정답과 해설</summary>

**정답: C**

Spot 중단 위험을 줄이는 축은 pool 다변화와 pool 선택 전략입니다. attribute-based instance type selection은 요건을 만족하는 타입을 자동으로 넓혀 pool 수를 늘리고, price-capacity-optimized는 가격과 가용 용량을 함께 보고 pool을 고릅니다. Capacity Rebalancing은 rebalance recommendation을 받으면 새 인스턴스가 health check를 통과한 뒤 기존 인스턴스를 종료해 선제적으로 교체합니다.

- A가 틀린 이유: 최대 가격을 지정하면 지정하지 않을 때보다 중단이 더 자주 발생한다고 AWS 문서가 명시합니다. Spot 가격은 입찰이 아니라 장기 수급으로 조정됩니다.
- B가 틀린 이유: placement group은 배치 전략이지 Spot 중단 확률과 무관합니다. rack-level spread는 AZ당 running 인스턴스 7개가 상한이라 fleet 규모도 맞지 않습니다.
- D가 틀린 이유: lowest-price는 가용 용량을 보지 않으므로 교체된 인스턴스도 곧 중단될 위험이 큽니다. AWS 문서가 Capacity Rebalancing과 lowest-price 조합을 명시적으로 비권장합니다.

</details>

**Q4.** 한 연구소가 유체역학 시뮬레이션을 EC2에서 실행한다. MPI 기반 코드가 64개 노드에 걸쳐 매 반복마다 대량의 노드 간 메시지를 교환하며, 노드 간 지연이 전체 실행 시간을 좌우한다. 작업은 몇 시간 안에 끝나고 중간 결과는 공유 파일시스템에 주기적으로 기록된다. 팀은 Elastic Fabric Adapter를 쓰기로 결정했다. Choose the MOST performant placement design.

- A. 단일 Availability Zone의 cluster placement group에 64개 노드를 배치한다.
- B. 3개 Availability Zone의 spread placement group에 노드를 고르게 배치한다.
- C. 3개 Availability Zone에 걸친 partition placement group을 만들고 파티션마다 노드를 나눈다.
- D. 2개 Availability Zone에 걸친 cluster placement group을 만들어 저지연과 AZ 장애 내성을 함께 얻는다.

<details markdown="1">
<summary>정답과 해설</summary>

**정답: A**

cluster placement group은 저지연 고대역 노드 간 통신을 위해 인스턴스를 물리적으로 가깝게 배치합니다. EFA 트래픽은 Availability Zone과 VPC를 넘지 못하고 라우팅되지 않으므로 EFA를 쓰는 MPI 클러스터는 단일 AZ에 모아야 합니다.

- B가 틀린 이유: rack-level spread placement group은 AZ당 running 인스턴스 7개가 상한이라 64개 노드를 담을 수 없고, 인스턴스를 일부러 떨어뜨리므로 노드 간 지연 요구와 정반대입니다.
- C가 틀린 이유: partition은 랙 단위 장애 격리를 위한 전략이며 파티션 간 근접성을 보장하지 않습니다. AZ를 걸치면 EFA 통신 자체가 성립하지 않습니다.
- D가 틀린 이유: cluster placement group은 단일 AZ를 넘을 수 없습니다. 같은 리전의 peered VPC는 걸칠 수 있지만 AZ 경계는 넘지 못합니다.

</details>

**Q5.** 한 금융사가 온프레미스에서 실행하던 상용 데이터베이스를 EC2로 이전한다. 벤더 라이선스가 물리 소켓과 물리 코어 수를 기준으로 산정되며, 감사를 위해 워크로드가 어떤 물리 서버에서 실행되는지 추적할 수 있어야 한다. 재기동 후에도 같은 물리 서버에 배치되어야 하고, 기존 라이선스를 그대로 가져와 쓰려 한다. Choose the solution that meets these requirements with the LEAST licensing risk.

- A. Dedicated Instances로 실행하고 AWS License Manager로 사용량을 추적한다.
- B. Dedicated Hosts를 할당하고 host affinity를 지정해 targeted placement로 인스턴스를 시작한다.
- C. default tenancy 인스턴스를 partition placement group에 배치하고 파티션 번호를 라이선스 단위로 사용한다.
- D. default tenancy 인스턴스를 시작하고 On-Demand Capacity Reservation으로 물리 서버를 고정한다.

<details markdown="1">
<summary>정답과 해설</summary>

**정답: B**

Dedicated Host는 per-host 과금이며 소켓 수와 물리 코어 수, host ID가 노출됩니다. per-socket, per-core, per-VM BYOL을 전면 지원하고, host affinity와 targeted placement로 재기동 후에도 같은 호스트에 인스턴스를 배치할 수 있습니다.

- A가 틀린 이유: Dedicated Instance는 per-instance 과금이며 소켓과 코어 가시성이 없고 host affinity와 targeted placement를 지원하지 않습니다. BYOL 지원 범위도 Software Assurance License Mobility가 붙은 Microsoft SQL Server와 Windows VDA로 한정됩니다.
- C가 틀린 이유: partition placement group은 랙 단위 격리 단위일 뿐 물리 서버를 지정하거나 소켓과 코어를 노출하지 않습니다.
- D가 틀린 이유: Capacity Reservation은 instance type, platform, Availability Zone, tenancy 네 속성으로 용량을 예약하는 수단이며 특정 물리 서버를 고정하지 않습니다.

</details>

**Q6.** 한 스타트업이 `t3.medium` 20대로 구성된 Auto Scaling group에서 API 서버를 운영한다. 평소 CPU 사용률은 10% 안팎이지만 하루 두어 번 수십 분간 급증하고, 그때마다 CPU credit이 고갈되어 응답 지연이 급격히 나빠진다. 확인해 보니 인스턴스는 `standard` credit specification으로 동작 중이며, 해당 Auto Scaling group은 launch configuration으로 만들어졌다. 인스턴스 수를 늘리지 않고 이 문제를 해결하려 한다. Choose the MOST cost-effective solution.

- A. Auto Scaling group을 launch template 기반으로 재구성하고 launch template에서 credit specification을 `unlimited`로 지정한다.
- B. 모든 인스턴스를 `m6i.large`로 교체해 버스터블 인스턴스를 쓰지 않는다.
- C. 리전의 계정 레벨 기본 credit specification을 `unlimited`로 바꾼다.
- D. 루트 볼륨을 gp2에서 gp3로 교체해 I/O 병목을 제거한다.

<details markdown="1">
<summary>정답과 해설</summary>

**정답: A**

버스터블 인스턴스를 `unlimited` 모드로 두면 credit이 고갈된 뒤에도 성능을 유지하고 초과분만 추가 과금됩니다. 평상시 사용률이 낮고 급증이 짧으면 이 초과 과금이 상시 대형 인스턴스 비용보다 작습니다. 다만 launch configuration은 `unlimited`를 지원하지 않으므로 launch template으로 옮겨야 합니다.

- B가 틀린 이유: 평균 사용률이 10% 안팎인데 상시 범용 인스턴스로 바꾸면 유휴 시간대 비용이 크게 늘어납니다. 요구는 급증 구간의 성능 유지이지 상시 성능 보장이 아닙니다.
- C가 틀린 이유: T3의 계정 레벨 기본 credit specification은 이미 `unlimited`이므로 이 설정에는 바꿀 값이 없습니다. 그런데도 인스턴스가 `standard`로 떠 있다는 것은 launch configuration 경로 때문이며, AWS 문서는 Auto Scaling group에서 `unlimited`로 띄우려면 launch template이 필요하고 launch configuration은 `unlimited` 시작을 지원하지 않는다고 명시합니다.
- D가 틀린 이유: 증상은 CPU credit 고갈이고 볼륨 타입은 CPU credit 회계와 무관합니다. gp3로 바꿔도 vCPU 성능 상한은 그대로입니다.

</details>

**Q7.** 한 회사가 Amazon SQS 큐를 소비하는 워커를 EC2 Auto Scaling group으로 운영한다. 메시지 하나 처리에 평균 40초가 걸리고, 큐 적체가 5분 이상 지속되면 SLA를 위반한다. 팀이 `ApproximateNumberOfMessagesVisible`을 target tracking 지표로 설정했으나 인스턴스가 계속 최대치까지 확장되었다가 급격히 축소되는 진동이 발생한다. Choose the solution that produces the MOST stable scaling behavior.

- A. 같은 지표를 유지하되 목표값을 크게 올리고 scale in을 비활성화한다.
- B. 큐 길이를 InService 인스턴스 수로 나눈 backlog per instance custom metric을 CloudWatch에 게시하고 그 지표로 target tracking 정책을 구성한다.
- C. `ApproximateNumberOfMessagesVisible` 알람 구간을 여러 개 정의해 step scaling 정책으로 바꾼다.
- D. `ApproximateAgeOfOldestMessage`를 지표로 하는 simple scaling 정책으로 바꾸고 cooldown을 600초로 둔다.

<details markdown="1">
<summary>정답과 해설</summary>

**정답: B**

target tracking은 지표 값이 Auto Scaling group의 인스턴스 수에 비례해 변할 때만 안정적으로 수렴합니다. AWS 문서는 `ApproximateNumberOfMessagesVisible`을 target tracking에 부적합한 지표로 직접 지목하고, 큐 길이를 인스턴스 수로 나눈 custom metric을 쓰라고 안내합니다. backlog per instance는 인스턴스를 늘리면 값이 내려가므로 비례 조건을 만족합니다.

- A가 틀린 이유: 지표가 인스턴스 수에 비례하지 않는 문제는 목표값 조정으로 해결되지 않습니다. scale in을 끄면 진동은 줄지만 축소가 사라져 비용이 늘어납니다.
- C가 틀린 이유: step scaling으로 바꿔도 지표 자체가 인스턴스 수를 반영하지 않아 확장 후에도 값이 즉시 내려가지 않습니다. 구간을 세밀하게 나누는 것은 증상 완화일 뿐입니다.
- D가 틀린 이유: simple scaling은 cooldown이 끝날 때까지 다음 활동을 시작하지 않으므로 5분 SLA 조건에서 대응이 늦습니다. AWS 문서도 simple scaling과 cooldown 사용을 권장하지 않습니다.

</details>

**Q8.** 한 SaaS 회사가 200대 규모의 Auto Scaling group에 새 AMI를 배포하려 한다. 배포 중에도 요청 처리 용량이 줄면 안 되고, 새 AMI에서 오류율이 올라가면 사람이 개입하기 전에 이전 구성으로 되돌아가야 한다. 팀은 별도 배포 도구를 도입하지 않고 EC2 Auto Scaling 기능만으로 해결하려 한다. Choose the solution that meets these requirements with the LEAST operational overhead.

- A. 기본값으로 instance refresh를 시작한다.
- B. minimum healthy percentage를 100%, maximum healthy percentage를 110%로 두는 instance maintenance policy를 적용하고, auto rollback을 활성화한 instance refresh를 시작하며 CloudWatch 알람을 rollback 트리거로 지정한다.
- C. max instance lifetime을 86,400초로 설정해 24시간에 걸쳐 인스턴스가 순차 교체되게 한다.
- D. 새 AMI로 두 번째 Auto Scaling group을 만들어 같은 target group에 등록하고, 안정화 후 기존 group을 삭제한다.

<details markdown="1">
<summary>정답과 해설</summary>

**정답: B**

instance maintenance policy의 minimum healthy percentage를 100%로 두면 새 인스턴스를 먼저 띄운 뒤 기존 인스턴스를 종료하는 launch before terminate 동작이 되어 용량이 유지됩니다. maximum healthy percentage 110%가 일시적 초과분을 허용합니다. instance refresh의 auto rollback을 켜고 CloudWatch 알람을 지정하면 지표 악화 시 이전 launch template 버전으로 자동 롤백됩니다.

- A가 틀린 이유: instance refresh 기본값은 minimum healthy percentage 90%, maximum healthy percentage 100%, auto rollback 비활성입니다. 기본값으로 시작하면 교체 중 용량이 10%까지 줄고 자동 롤백도 없습니다.
- C가 틀린 이유: max instance lifetime은 인스턴스 수명이 지난 뒤 교체를 유발하는 위생 기능이지 배포 제어 수단이 아닙니다. 롤백 개념이 없고 교체 진행 상황을 제어하지 못합니다.
- D가 틀린 이유: 목표는 달성할 수 있으나 group 두 개를 병행 운영하고 수동으로 전환하며 정리하는 절차가 붙어 운영 부담이 가장 큽니다. 스케일링 정책과 알람도 이중으로 관리해야 합니다.

</details>

**Q9.** (다답형) 한 광고 기술 회사가 야간 로그 집계를 EC2 Spot 인스턴스 수백 대로 처리한다. 각 인스턴스는 5분마다 진행 상황을 Amazon S3에 체크포인트로 남기고, 중단되면 다른 인스턴스가 마지막 체크포인트부터 이어받는다. 최근 Spot 중단으로 체크포인트가 유실되어 작업 전체를 다시 돌린 사고가 있었다. 중단 자체는 감수하되 진행 손실을 최소화하려 한다. Choose THREE actions that together provide the MOST resilient design.

- A. mixed instances policy에서 attribute-based instance type selection으로 vCPU와 메모리 요건을 만족하는 여러 인스턴스 타입을 후보로 둔다.
- B. Spot 최대 가격을 On-Demand 요금의 80%로 명시한다.
- C. Auto Scaling group에서 Capacity Rebalancing을 활성화한다.
- D. EventBridge의 `EC2 Spot Instance Interruption Warning` 이벤트와 인스턴스 메타데이터 `/latest/meta-data/spot/instance-action` 폴링을 함께 사용해 종료 전에 체크포인트를 강제로 기록한다.
- E. 인스턴스를 rack-level spread placement group에 배치한다.
- F. warm pool을 `Running` 상태로 구성해 교체 인스턴스를 미리 띄워 둔다.

<details markdown="1">
<summary>정답과 해설</summary>

**정답: A, C, D**

A는 Spot pool 수를 늘려 특정 pool의 용량 회수가 fleet 전체에 미치는 영향을 줄입니다. C는 rebalance recommendation을 받으면 새 인스턴스가 health check를 통과한 뒤 기존 인스턴스를 종료하므로 선제 교체가 가능하고, 이 과정에서 그룹 크기가 desired capacity의 최대 10%까지 일시 초과할 수 있습니다. D는 중단 통지가 stop 또는 terminate 2분 전에 발행되고 EventBridge 이벤트와 메타데이터 두 경로로 온다는 점을 이용해 그 2분 안에 체크포인트를 남깁니다. AWS 문서는 메타데이터를 5초 주기로 폴링하고 통지가 best effort임을 전제하라고 안내합니다.

- B가 틀린 이유: 최대 가격을 지정하면 지정하지 않을 때보다 중단이 더 자주 발생합니다. 비용은 pool 선택 전략으로 다루는 것이 문서 권장입니다.
- E가 틀린 이유: placement group은 Spot 중단 확률과 무관합니다. 중단 동작을 stop이나 hibernate로 설정한 Spot 인스턴스는 placement group에 아예 들어갈 수 없고, rack-level spread는 AZ당 7대가 상한이라 수백 대 규모에 맞지 않습니다.
- F가 틀린 이유: warm pool은 mixed instances group에서 Spot을 지원하지 않습니다. 게다가 `Running` 상태 warm pool은 비용 때문에 AWS 문서가 강하게 비권장합니다.

</details>

**Q10.** 한 회사의 컴퓨트 지출은 EC2 60%, AWS Fargate 25%, AWS Lambda 15%로 구성된다. 향후 1년 안에 일부 워크로드를 다른 리전으로 옮기고 인스턴스 패밀리도 Graviton 계열로 전환할 계획이지만 시점이 확정되지 않았다. 재무팀은 1년 약정으로 최대한 많은 지출을 할인 대상에 포함시키되, 약정 재조정 작업이 반복되지 않기를 원한다. Choose the MOST appropriate pricing model.

- A. EC2 Instance Savings Plans를 현재 리전과 인스턴스 패밀리 기준으로 1년 약정한다.
- B. Compute Savings Plans를 1년 약정한다.
- C. Convertible Reserved Instances를 1년 약정하고 전환 시점에 exchange한다.
- D. Standard Reserved Instances를 1년 약정하고 전환 시점에 Reserved Instance Marketplace에서 매각한다.

<details markdown="1">
<summary>정답과 해설</summary>

**정답: B**

Compute Savings Plans는 instance family, size, Region, OS, tenancy와 무관하게 적용되고 Fargate와 Lambda 사용량에도 적용됩니다. 리전 이동과 패밀리 전환이 일어나도 약정이 자동으로 따라가므로 재조정 작업이 없습니다. 세 서비스 지출을 하나의 약정으로 덮는 유일한 선택지입니다.

- A가 틀린 이유: EC2 Instance Savings Plans는 리전과 인스턴스 패밀리를 고정합니다. size, OS, tenancy만 유연하며 Fargate와 Lambda에는 적용되지 않아 지출의 40%가 할인 대상에서 빠집니다.
- C가 틀린 이유: Convertible RI는 exchange가 가능하지만 수동 절차이며 EC2에만 적용됩니다. Fargate와 Lambda 지출을 덮지 못하고 재조정 작업이 반복됩니다.
- D가 틀린 이유: Standard RI는 exchange가 불가능하며 EC2 전용입니다. Marketplace 매각은 가능하지만 매수자를 기다려야 하고 회수 금액도 보장되지 않습니다.

</details>

---

## 28. Reference

- [Amazon EC2 - Instance purchasing options](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/instance-purchasing-options.html)
- [Amazon EC2 - Instance types](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/instance-types.html)
- [Amazon EC2 - Instance type names](https://docs.aws.amazon.com/ec2/latest/instancetypes/instance-type-names.html)
- [Amazon EC2 - Burstable performance instances](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/burstable-performance-instances.html)
- [Amazon EC2 - Configure burstable performance instances](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/burstable-performance-instances-how-to.html)
- [Amazon EC2 - Placement groups](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/placement-groups.html)
- [Amazon EC2 - Use Capacity Reservations with placement groups](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/cr-cpg.html)
- [Amazon EC2 - Create a Capacity Reservation](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/capacity-reservations-create.html)
- [Amazon EC2 - Placement strategies](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/placement-strategies.html)
- [Amazon EC2 - Reserved Instances](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-reserved-instances.html)
- [Amazon EC2 - Reserved Instance types](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/reserved-instances-types.html)
- [Amazon EC2 - Reserved Instance scope](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/reserved-instances-scope.html)
- [Amazon EC2 - Modify Reserved Instances](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ri-convertible-exchange.html)
- [Amazon EC2 - Capacity Reservations](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-capacity-reservations.html)
- [Amazon EC2 - Capacity reservation overview](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/capacity-reservation-overview.html)
- [Amazon EC2 - Dedicated Hosts](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/dedicated-hosts-overview.html)
- [Amazon EC2 - Spot Instances](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/using-spot-instances.html)
- [Amazon EC2 - Spot interruptions](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/spot-interruptions.html)
- [Amazon EC2 - Spot Instance interruption notices](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/spot-instance-termination-notices.html)
- [Amazon EC2 - Spot Fleet allocation strategies](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/spot-fleet-allocation-strategy.html)
- [Amazon EC2 - Enhanced networking with ENA](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/enhanced-networking-ena.html)
- [Amazon EC2 - Elastic Fabric Adapter](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/efa.html)
- [Amazon EC2 - Recover your instance](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-instance-recover.html)
- [Amazon EC2 - Monitor your instances with CloudWatch](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/viewing_metrics_with_cloudwatch.html)
- [AWS Savings Plans - What are Savings Plans](https://docs.aws.amazon.com/savingsplans/latest/userguide/what-is-savings-plans.html)
- [AWS Savings Plans - Plan types](https://docs.aws.amazon.com/savingsplans/latest/userguide/plan-types.html)
- [AWS Savings Plans - Savings Plans and Reserved Instances](https://docs.aws.amazon.com/savingsplans/latest/userguide/sp-ris.html)
- [Amazon EC2 Auto Scaling - Predictive scaling policy overview](https://docs.aws.amazon.com/autoscaling/ec2/userguide/predictive-scaling-policy-overview.html)
- [Amazon EC2 Auto Scaling - Target tracking scaling](https://docs.aws.amazon.com/autoscaling/ec2/userguide/as-scaling-target-tracking.html)
- [Amazon EC2 Auto Scaling - Scaling cooldowns](https://docs.aws.amazon.com/autoscaling/ec2/userguide/ec2-auto-scaling-scaling-cooldowns.html)
- [Amazon EC2 Auto Scaling - Health checks](https://docs.aws.amazon.com/autoscaling/ec2/userguide/ec2-auto-scaling-health-checks.html)
- [Amazon EC2 Auto Scaling - Health check grace period](https://docs.aws.amazon.com/autoscaling/ec2/userguide/health-check-grace-period.html)
- [Amazon EC2 Auto Scaling - Lifecycle hooks](https://docs.aws.amazon.com/autoscaling/ec2/userguide/lifecycle-hooks.html)
- [Amazon EC2 Auto Scaling - Instance refresh](https://docs.aws.amazon.com/autoscaling/ec2/userguide/asg-instance-refresh.html)
- [Amazon EC2 Auto Scaling - Instance refresh default values](https://docs.aws.amazon.com/autoscaling/ec2/userguide/understand-instance-refresh-default-values.html)
- [Amazon EC2 Auto Scaling - Warm pools](https://docs.aws.amazon.com/autoscaling/ec2/userguide/ec2-auto-scaling-warm-pools.html)
- [Amazon EC2 Auto Scaling - Capacity Rebalancing](https://docs.aws.amazon.com/autoscaling/ec2/userguide/ec2-auto-scaling-capacity-rebalancing.html)
- [Amazon EC2 Auto Scaling - Termination policies](https://docs.aws.amazon.com/autoscaling/ec2/userguide/ec2-auto-scaling-termination-policies.html)
- [Amazon EC2 Auto Scaling - Maximum instance lifetime](https://docs.aws.amazon.com/autoscaling/ec2/userguide/asg-max-instance-lifetime.html)
- [Amazon EC2 Auto Scaling - Attribute-based instance type selection](https://docs.aws.amazon.com/autoscaling/ec2/userguide/create-mixed-instances-group-attribute-based-instance-type-selection.html)
- [Amazon EC2 Auto Scaling - Suspend and resume processes](https://docs.aws.amazon.com/autoscaling/ec2/userguide/as-suspend-resume-processes.html)
- [Amazon EC2 Auto Scaling - Effects of suspending processes](https://docs.aws.amazon.com/autoscaling/ec2/userguide/understand-how-suspending-processes-affects-other-processes.html)
- [Amazon EC2 Auto Scaling - Instance maintenance policy](https://docs.aws.amazon.com/autoscaling/ec2/userguide/instance-maintenance-policy-overview-and-considerations.html)
- [AWS Batch - Multi-node parallel jobs](https://docs.aws.amazon.com/batch/latest/userguide/multi-node-parallel-jobs.html)
- [AWS Batch - Multi-node parallel job compute environments](https://docs.aws.amazon.com/batch/latest/userguide/mnp-ce.html)
- [AWS EC2 - Change the placement of an instance](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/change-instance-placement-group.html)

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
