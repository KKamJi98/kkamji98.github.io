---
title: "SAP-C02 박살내기 12 - 비용 최적화"
author: kkamji
categories: [Certification, AWS SAP-C02]
tags: [aws, sap-c02, certification, cost-optimization, savings-plans, reserved-instances, data-transfer, budgets, trusted-advisor]
comments: true
image:
  path: /assets/img/aws/aws.webp
date: 2026-09-03 10:00:00 +0900
---

Savings Plans 커버리지를 98퍼센트까지 올려 놓고 다음 달 청구서를 열었는데 총액이 기대만큼 내려가지 않는 경우가 있습니다. Cost Explorer 에서 usage type 으로 쪼개 보면 이유가 나옵니다. 상위 항목이 `BoxUsage` 가 아니라 `NatGateway-Bytes` 와 `DataTransfer-Regional-Bytes` 이고, 이 둘의 합이 EC2 인스턴스 시간 요금과 비슷합니다.

커버리지 지표는 거짓말을 하지 않았습니다. Savings Plans 가 덮을 수 있는 사용분 중 98퍼센트가 덮였을 뿐이고, NAT Gateway 처리 요금과 리전 간 데이터 전송은 애초에 그 분모에 들어가지 않습니다. 커밋을 아무리 더 사도 이 항목은 1원도 줄지 않습니다.

SAP-C02 Domain 3 의 비용 문항은 이 층에서 갈립니다. 지문은 "MOST cost-effective" 를 묻지만 정답을 가르는 것은 단가가 아니라 **어떤 요금이 어떤 수단에 반응하는가**입니다. 커밋 할인이 닿는 항목과 닿지 않는 항목, 용량을 주는 수단과 할인을 주는 수단, 태그로 배분되는 라인 아이템과 규칙으로만 묶이는 라인 아이템이 각각 다르고, 선지는 그 경계를 한 칸씩 어긋나게 만들어 놓습니다.

> **TL;DR**  
> - 커밋 할인은 EC2 RI, EC2 Instance SP, Compute SP 순으로 사용분을 채운다. Spot 사용분과 데이터 전송과 NAT 처리 요금에는 닿지 않는다.  
> - Savings Plans 는 capacity reservation 을 주지 않는다. 용량은 ODCR 또는 Zonal RI 다.  
> - Standard RI 는 exchange 불가에 Marketplace 매각 가능, Convertible RI 는 exchange 가능에 매각 불가다. SP 는 취소도 교환도 없다.  
> - Regional RI 는 용량을 예약하지 않는다. size 유연성은 Amazon Linux/Unix 에 default tenancy 인 경우에만 붙는다.  
> - Intelligent-Tiering 은 최소 보관 기간도 최소 과금 객체 크기도 retrieval fee 도 없다. 대신 객체당 monitoring 요금이 붙고 128 KB 미만 객체는 계층 이동 대상이 아니다.  
> - 2024년 9월부터 lifecycle 기본 동작은 128 KB 미만 객체를 어떤 클래스로도 전환하지 않는 것이다.  
> - lifecycle 전환은 단방향이다. Deep Archive 에서 나가는 lifecycle 경로는 없고 restore 후 copy 로 덮어써야 한다.  
> - Glacier 계열 restore 는 임시 사본만 만들고 객체의 storage class 는 그대로다. Intelligent-Tiering 의 archive 계층 restore 는 객체를 실제로 Frequent Access 로 옮긴다.  
> - cost allocation tag 는 리소스에 태그가 붙어 있어야 배분되고, Cost Categories 는 라인 아이템에 규칙으로 붙어 당월 1일부터 소급된다.  
> - budget action 은 IAM policy 적용, OU 에 SCP 적용, EC2 와 RDS 인스턴스 중지 셋이다. 다른 계정의 인스턴스는 타깃할 수 없다.  
> - Cost Anomaly Detection 은 AWS Marketplace 의 제3자 제품과 서비스를 분석하지 않으며 Amazon Bedrock 의 제3자 모델과 Bedrock Marketplace 모델도 포함한다. Billing entity 필터를 건 cost budget 이 그 자리를 대신한다.  
> - gateway endpoint 는 S3 와 DynamoDB 만 지원하고 추가 요금이 없다. prefix list 가 리전 한정이라 교차 리전 트래픽은 여기로 타지 않는다.  
{: .prompt-info}

---

## 1. 커밋 할인이 덮는 항목과 애초에 닿지 않는 항목

비용 문항을 읽을 때 가장 먼저 나눠야 하는 것은 **청구서의 어느 줄이 커밋 할인에 반응하는가**입니다. Savings Plans 와 Reserved Instances 는 컴퓨트 사용 시간에 붙는 요금을 낮추는 수단이고, 그 밖의 요금 축은 전혀 다른 수단으로 다뤄야 합니다.

| 청구 항목 | 커밋 할인 반응 | 실제로 줄이는 수단 |
| :--- | :--- | :--- |
| EC2 인스턴스 시간 | 반응한다 | Savings Plans, Reserved Instances, Spot, rightsizing |
| Fargate 와 Lambda 사용분 | Compute SP 만 반응한다 | Compute Savings Plans, 메모리 rightsizing |
| Aurora, RDS, DynamoDB, ElastiCache 등 | Database SP 가 반응한다 | Database Savings Plans, rightsizing |
| Spot 사용분 | 반응하지 않는다 | 이미 할인된 요율이다 |
| Dedicated Instance 의 리전당 시간당 $2 | 반응하지 않는다 | tenancy 를 바꾼다 |
| NAT Gateway 처리 GB | 반응하지 않는다 | VPC endpoint, AZ 배치 |
| 리전 간과 AZ 간 데이터 전송 | 반응하지 않는다 | 아키텍처 배치, CloudFront |
| S3 저장과 요청 | 반응하지 않는다 | 스토리지 클래스, lifecycle, Requester Pays |
| EKS 클러스터 자체 요금 | 반응하지 않는다 | 클러스터 수 통합 |

Compute Savings Plans 가 EMR, EKS, ECS 클러스터의 기반 EC2 사용분을 커버한다는 문장과 EKS 자체 요금을 커버하지 않는다는 문장은 함께 외워야 합니다. 지문이 "컨테이너 플랫폼 비용" 이라고 뭉뚱그리면 이 둘을 분리해서 읽어야 선지가 좁혀집니다.

---

## 2. Savings Plans 네 종류가 각각 고정하는 축

Savings Plans 는 시간당 지출액을 약정하는 방식입니다. 1년 또는 3년 기간에 대해 시간당 금액을 약속하고, 그 금액만큼의 사용분이 할인 요율로 계산됩니다. 기간 정의는 1년이 365일 31,536,000초, 3년이 1,095일 94,608,000초이고 결제는 All upfront, Partial upfront, No upfront 중에 고릅니다.

| 유형 | 최대 할인 | 고정하는 축 | 유연한 축 | 커버 대상 |
| :--- | :--- | :--- | :--- | :--- |
| Compute Savings Plans | 66% | 없음 | family, size, Region, OS, tenancy | EC2, Fargate, Lambda |
| EC2 Instance Savings Plans | 72% | Region, instance family | size, OS, tenancy | 해당 Region 의 해당 family EC2 |
| SageMaker AI Savings Plans | 64% | 없음 | instance family, size, Region, 구성 요소 | SageMaker AI |
| Database Savings Plans | 35% | 없음 | 엔진과 인스턴스 구성 | Aurora, RDS, DynamoDB, ElastiCache, DocumentDB, Timestream, Neptune, Keyspaces, DMS, OpenSearch Service |

Database Savings Plans 는 serverless 사용분에도 적용되고 최신 provisioned 세대가 대상입니다. 강의 자료나 오래된 정리에서 Savings Plans 를 3종으로 세는 경우가 있는데 현재는 이 유형을 포함해 4종입니다.

**Dedicated Instance 를 쓸 때 Region 당 시간당 $2 가 별도로 붙고 이 요금은 Savings Plans 로 할인되지 않습니다.** tenancy 자체가 유연한 축에 들어 있다는 점과 이 요금이 할인 대상이 아니라는 점은 다른 이야기입니다.

Savings Plans 는 기간 중 취소할 수 없습니다. 교환이나 수정이라는 개념도 없습니다. 약정한 것이 구성이 아니라 시간당 금액이기 때문이고, 이 성질이 뒤에서 볼 Reserved Instance 와의 가장 큰 차이입니다.

---

## 3. 할인이 사용분을 채우는 순서

한 시간의 사용분에 여러 종류의 커밋이 걸려 있으면 적용 순서가 정해져 있습니다. 이 순서를 모르면 "커밋을 추가로 샀는데 절감액이 예상과 다르다" 는 상황을 설명할 수 없습니다.

![EC2 Reserved Instances 부터 Compute Savings Plans 까지 커밋 할인이 사용분을 채우는 순서와 할인이 닿지 않는 항목](/assets/img/sap-c02/savings-plans-discount-order.webp)

그림은 한 시간의 사용분이 세 단계의 커밋을 거쳐 남은 만큼만 On-Demand 요율로 계산되는 과정과, 그 과정에 처음부터 들어오지 않는 항목을 함께 담고 있습니다. 각 상자의 부제에 그 단계가 고정하는 축과 최대 할인율이 적혀 있습니다.

순서는 다음과 같습니다.

1. **EC2 Reserved Instances 가 먼저 적용됩니다.** 구성이 일치하는 사용분을 RI 가 가져갑니다.
2. **그다음이 Savings Plans 이고, SP 안에서는 EC2 Instance SP 가 Compute SP 보다 먼저 적용됩니다.** Compute SP 가 더 넓은 범위에 적용될 수 있으므로 좁은 것을 먼저 소진시키는 순서입니다.
3. 같은 종류의 SP 안에서는 절감률이 높은 사용분부터 채우고, 절감률이 같으면 SP rate 가 낮은 사용분부터 채웁니다.

여기에 두 가지 성질이 붙습니다. 첫째, **시간당 commitment 는 그 시간 안에서만 쓰이고 다음 시간으로 이월되지 않습니다.** 사용량이 시간마다 크게 출렁이면 어떤 시간에는 커밋이 남고 어떤 시간에는 초과분이 On-Demand 로 나갑니다. 커버리지가 낮게 나오는 흔한 원인입니다. 둘째, **Savings Plans 는 Spot 사용분과 RI 가 이미 커버한 사용분에는 적용되지 않습니다.**

Consolidated Billing Family 안에서는 SP 가 소유 계정의 사용분에 먼저 적용된 뒤 다른 계정으로 넘어갑니다. 이 동작은 sharing 이 켜져 있을 때만 일어나고, 자세한 조건은 8절에서 다룹니다.

---

## 4. Reserved Instance 는 취소할 수 없고 출구가 세 개다

Reserved Instance 는 구매 후 취소가 불가능합니다. 대신 조건부로 modify, exchange, sell 세 가지 출구가 있고 어떤 출구가 열려 있는지가 유형에 따라 갈립니다. 만료되면 자동 갱신되지 않고 그대로 On-Demand 로 되돌아갑니다. No Upfront RI 는 결제 이력이 있어야 구매할 수 있습니다.

| 항목 | Standard RI | Convertible RI |
| :--- | :--- | :--- |
| modify | 가능 | 가능 |
| exchange | 불가능 | 가능. instance family, type, platform, scope, tenancy 변경 |
| RI Marketplace 판매 | 가능 | 불가능 |
| RI Marketplace 구매 | 가능 | 불가능 |
| 할인율 | 더 높다 | 유연성의 대가로 더 낮다 |

시험에서 이 표는 두 방향으로 쓰입니다. "약정이 남았는데 워크로드가 바뀐다" 는 지문에는 Convertible RI 의 exchange 또는 Compute SP 가 후보로 올라오고, "쓰지 않게 된 약정을 회수한다" 는 지문에는 Standard RI 의 Marketplace 매각만 남습니다. 두 선지를 뒤바꿔 놓은 오답이 자주 나옵니다.

Savings Plans 와 나란히 놓으면 성질이 분명해집니다. RI 는 **구성**을 약정하므로 구성이 달라지면 exchange 나 매각이라는 절차가 필요하고, SP 는 **시간당 금액**을 약정하므로 구성이 달라져도 절차 없이 적용이 따라갑니다. 대신 SP 에는 되팔거나 물리는 출구가 없습니다.

---

## 5. Regional RI 와 Zonal RI 가 갈리는 네 가지

RI 의 scope 는 가격에 영향을 주지 않습니다. 두 scope 의 가격은 동일하고, 갈리는 것은 용량과 유연성입니다.

| 항목 | Regional RI | Zonal RI |
| :--- | :--- | :--- |
| 용량 예약 | 하지 않는다 | 지정한 AZ 에 예약한다 |
| AZ 유연성 | 있다 | 없다 |
| instance size 유연성 | Amazon Linux/Unix 에 default tenancy 인 경우에만 있다 | 없다 |
| purchase queuing | 가능하다 | 불가능하다 |
| 기본 한도 | Region 당 20개 | AZ 당 20개 |

**size 유연성의 조건을 정확히 기억해야 합니다.** Windows 나 다른 상용 OS, 또는 Dedicated tenancy 인 Regional RI 에는 size 유연성이 적용되지 않습니다. "같은 family 의 RI 를 샀으니 크기가 달라도 커버된다" 는 서술은 OS 와 tenancy 조건을 확인하기 전까지 성립하지 않습니다.

purchase queuing 은 만료 시점에 맞춰 다음 RI 구매를 예약해 두는 기능입니다. 갱신 공백을 없애는 운용 수단이고 Regional 에서만 됩니다.

---

## 6. 용량과 할인은 다른 메커니즘이고 겹쳐야 둘 다 얻는다

비용 문항에서 가장 많이 틀리는 축이 여기입니다. **Savings Plans 는 capacity reservation 을 제공하지 않습니다.** 커밋을 늘려도 특정 AZ 에서 인스턴스가 뜬다는 보장은 생기지 않습니다.

![용량 확보와 요금 할인을 각각 담당하는 수단과 둘을 겹쳐 쓰는 구성](/assets/img/sap-c02/capacity-versus-discount-matrix.webp)

그림은 워크로드 요구를 용량 보장과 요금 할인 두 갈래로 나눈 뒤 각 갈래에 어떤 수단이 놓이는지, 그리고 두 갈래를 모두 만족시키려면 무엇을 겹쳐야 하는지를 보여줍니다. Zonal Reserved Instance 만 두 갈래 모두에 걸쳐 있습니다.

On-Demand Capacity Reservation 의 성질은 다음과 같습니다.

- **즉시 사용형은 term commitment 가 없고 언제든 취소할 수 있습니다.**
- **자체로는 billing discount 가 없습니다.** 할인은 Savings Plans 나 Regional RI 와 결합해야 붙습니다.
- **Zonal RI 의 billing discount 는 Capacity Reservation 에 적용되지 않습니다.**
- 계정의 On-Demand instance 한도를 소진하며, 인스턴스가 뜨지 않은 미사용 상태에서도 한도를 차지하고 과금됩니다.
- Dedicated Host 와 함께 쓸 수 없고 Dedicated Instance 와는 함께 쓸 수 있습니다. placement group 안의 Capacity Reservation은 cluster 또는 precision time을 지원하고 spread와 partition은 지원하지 않습니다.

future-dated Capacity Reservation 은 조건이 더 붙습니다. 최소 32 vCPU 단위로 요청해야 하고 지원 family 는 C, G, I, M, R, T, U, X 입니다. commitment 기간 중 취소하면 cancellation charge 가 붙을 수 있습니다.

정리하면 용량과 할인을 동시에 원할 때 선택지는 두 가지입니다. Zonal RI 하나로 둘 다 받거나, ODCR 로 용량을 잡고 그 위에 Savings Plans 또는 Regional RI 를 겹치는 것입니다. 후자가 유연성이 크고 문항에서 정답이 되는 경우가 많습니다.

---

## 7. Spot 을 비용 축에서 고를 때 확인하는 값

Spot 은 할인 수단이 아니라 중단 가능성을 감수하는 대신 낮은 요율을 쓰는 구매 옵션입니다. 비용 문항에서는 중단 특성이 요구 조건과 충돌하는지가 판정 기준이 됩니다.

- **interruption notice 는 stop 또는 terminate 2분 전에 발행됩니다.** hibernate 도 interruption notice가 오지만 2분 전 경고 없이 즉시 시작됩니다.
- 전달 경로는 EventBridge 의 `EC2 Spot Instance Interruption Warning` 이벤트와 IMDS 의 `/latest/meta-data/spot/instance-action` 이고, 둘 다 best effort 입니다. AWS 는 5초 간격 폴링을 권고합니다.
- 중단 사유는 capacity 회수, Spot price 가 지정한 maximum price 를 넘음, launch group 이나 AZ group 제약 위반 셋입니다.
- **maximum price 를 지정하면 지정하지 않을 때보다 중단이 잦아집니다.**

allocation strategy 선택도 문항에 나옵니다.

| 전략 | 성질 |
| :--- | :--- |
| `price-capacity-optimized` | 대부분의 워크로드에 권장된다. 용량 가용성과 가격을 함께 본다 |
| `lowest-price` | 중단 위험이 가장 높아 비권장이다. CLI 기본값이므로 명시적으로 덮어써야 한다 |
| `diversified` | Spot price 가 On-Demand price 이상인 pool 에는 인스턴스를 띄우지 않는다 |

`lowest-price` 가 CLI 기본값이라는 사실이 함정입니다. "기본값을 그대로 썼더니 중단이 잦다" 는 지문의 원인이 여기입니다.

---

## 8. 조직 안에서 커밋을 공유하는 세 가지 모드

management account 가 조직 내 계정별로 RI 와 Savings Plans 할인 공유를 켜고 끕니다. 공유 모드는 세 가지입니다.

| 모드 | 동작 |
| :--- | :--- |
| organization-wide sharing | 조직 전체에서 커밋을 공유한다 |
| prioritized group sharing | 지정한 그룹에 우선 적용한 뒤 나머지로 넘긴다 |
| restricted group sharing | 지정한 그룹 안에서만 공유한다 |

**모든 모드에서 커밋은 소유 계정의 사용분에 먼저 적용됩니다.** 그룹 정의에는 AWS Cost Categories 를 쓰는데 여기에 제약이 셋 있습니다. 그룹 정의에는 Accounts dimension 만 쓸 수 있고, 한 계정은 그룹 하나에만 속하며, payer 계정은 그룹에 들어갈 수 없습니다.

운용에서 걸리는 점이 두 가지 더 있습니다. 공유 설정은 언제든 바꿀 수 있지만 그 달의 최종 청구는 **그 달 마지막 날 23:59:59 UTC 시점의 설정**으로 계산됩니다. 그리고 **구매 계정과 수혜 계정 양쪽 모두 sharing 이 켜져 있어야** 공유가 성립합니다. Savings Plans 소유 계정이 조직을 떠나면 그 SP 는 통합 청구에 더 이상 적용되지 않습니다.

---

## 9. 커버리지와 사용률은 다른 값을 재고 예산 유형도 따로 있다

커밋을 산 다음에 봐야 하는 지표가 둘이고, 이름이 비슷해 뒤바뀐 선지가 자주 나옵니다.

| 지표 | 재는 것 | 낮을 때의 의미 |
| :--- | :--- | :--- |
| utilization | 구매한 커밋이 실제로 쓰이는 비율 | 커밋을 과하게 샀다. 쓰이지 않는 약정이 있다 |
| coverage | 대상 사용분 중 커밋이 덮은 비율 | 커밋이 부족하다. On-Demand 로 새는 사용분이 있다 |

AWS Budgets 의 유형이 이 두 축을 그대로 따릅니다. 현재 유형은 여섯 가지입니다.

| budget 유형 | 알림 조건 |
| :--- | :--- |
| Cost budgets | 비용이 임계값에 접근하거나 초과할 때 |
| Usage budgets | 사용량이 임계값에 접근하거나 초과할 때 |
| RI utilization budgets | RI 사용률이 지정 수준 아래로 떨어질 때 |
| RI coverage budgets | RI 가 덮은 instance 시간 비율이 지정 수준 아래로 떨어질 때 |
| Savings Plans utilization budgets | SP 사용률이 지정 수준 아래로 떨어질 때 |
| Savings Plans coverage budgets | SP 가 덮은 적격 사용분 비율이 지정 수준 아래로 떨어질 때 |

Budgets 는 하루 최대 3회 갱신되고 갱신 간격은 보통 8시간에서 12시간입니다. blended, unblended, net unblended, amortized, net amortized 비용을 추적할 수 있고 할인, 환불, support 요금, 세금을 포함하거나 제외할 수 있습니다. 회계연도나 프로젝트 기간에 맞춘 custom period budget 도 만들 수 있습니다.

구매 추천은 Cost Explorer 의 Savings Plans Recommendations 에서 봅니다. 이 화면이 주는 값은 세 가지입니다. 선택한 기간의 사용량에 기반한 monthly On-Demand spend, 추천 커밋을 샀을 때의 estimated monthly spend, 그 차이인 estimated monthly savings 입니다. **On-Demand spend 값에는 계산 시점에 보유 중인 활성 Savings Plans 가 이미 반영되어 있습니다.** 같은 추천을 Cost Explorer API 의 `GetSavingsPlansPurchaseRecommendation` 으로도 받을 수 있습니다.

---

## 10. Intelligent-Tiering 이 계층을 옮기는 조건

접근 패턴을 예측할 수 없는 데이터에 대한 기본 답이 S3 Intelligent-Tiering 입니다. 다만 언제 내려가고 언제 올라오는지, 그리고 **무엇이 접근으로 인정되는지**가 문항의 재료입니다.

![Intelligent-Tiering 의 자동 계층과 선택 계층, 계층 이동 조건, restore 후의 복귀 지점](/assets/img/sap-c02/s3-intelligent-tiering-tiers.webp)

그림은 Frequent Access 에서 시작한 객체가 미접근 일수에 따라 이동하는 계층들과, 선택 계층에서 restore 했을 때 객체가 도착하는 지점을 담고 있습니다. 128 KB 미만 객체가 이 이동에서 빠지는 것도 함께 표시했습니다.

계층 구성은 이렇습니다.

| 계층 | 이동 조건 | 활성화 |
| :--- | :--- | :--- |
| Frequent Access | 기본 계층 | 자동 |
| Infrequent Access | 30일 연속 미접근 | 자동 |
| Archive Instant Access | 90일 연속 미접근 | 자동 |
| Archive Access | 최소 90일부터 설정, 최대 730일 | 선택 |
| Deep Archive Access | 최소 180일부터 설정, 최대 730일 | 선택 |

Intelligent-Tiering 의 경제성은 세 가지 사실에서 나옵니다.

- **최소 보관 기간이 없습니다.** 조기 삭제 수수료 노출이 없습니다.
- **최소 과금 객체 크기가 없고 retrieval fee 도 없습니다.**
- **대신 객체당 monitoring 과 automation 요금이 붙습니다.** 객체 수가 많고 개별 크기가 작을수록 불리해집니다.

**128 KB 미만 객체는 모니터링되지 않고 auto-tiering 대상에서도 제외되어 항상 Frequent Access 에 남습니다.** 로그 조각처럼 작은 객체가 대량으로 쌓이는 버킷에 Intelligent-Tiering 을 걸면 계층은 그대로인 채 monitoring 요금만 늘어납니다.

접근으로 인정되는 동작과 인정되지 않는 동작의 구분도 정확해야 합니다.

| 접근으로 인정 | 인정하지 않음 |
| :--- | :--- |
| 콘솔 다운로드와 복사, `CopyObject`, `UploadPartCopy`, Batch Replication, `GetObject`, `PutObject`, `RestoreObject`, `CompleteMultipartUpload` | `HeadObject`, `GetObjectTagging`, `PutObjectTagging`, `ListObjects` 계열 |

`SelectObjectContent` 는 중간 위치에 있습니다. **선택 계층인 Archive Access 와 Deep Archive Access 로의 하향만 막고, Frequent Access 로 되돌리지는 않으며, Frequent 에서 Infrequent Access 를 거쳐 Archive Instant Access 로 내려가는 자동 하향도 막지 않습니다.**

운용 지표도 있습니다. Archive Access 와 Deep Archive Access 의 restore 요청은 계정당 리전당 최대 1,000 TPS 입니다. 아카이브 상태는 `HeadObject` 응답의 `x-amz-archive-status` 헤더로 확인하고 `s3:IntelligentTiering` 이벤트 알림을 SNS, SQS, Lambda 로 받을 수 있습니다.

---

## 11. lifecycle 전환의 경제성은 세 가지 비용으로 계산한다

접근 패턴을 알고 있으면 lifecycle 로 직접 내리는 쪽이 저장 단가가 낮습니다. 대신 최소 보관 기간, 최소 과금 객체 크기, 전환 요청 비용 세 가지를 떠안습니다.

![S3 스토리지 클래스 사이의 lifecycle 전환 방향과 클래스별 최소 보관 기간](/assets/img/sap-c02/s3-lifecycle-transition-paths.webp)

그림은 lifecycle 규칙이 만들 수 있는 전환 방향과 각 클래스의 최소 보관 기간을 함께 보여줍니다. Deep Archive 에서 나가는 lifecycle 경로가 없다는 것도 이 그림의 내용입니다.

먼저 클래스별 수치입니다.

| 클래스 | 최소 보관 기간 | 최소 과금 객체 크기 | 설계 가용성 |
| :--- | :--- | :--- | :--- |
| S3 Standard | 없음 | 없음 | 99.99% |
| Intelligent-Tiering | 없음 | 없음 | 99.9% |
| Standard-IA | 30일 | 128 KB | 99.9% |
| One Zone-IA | 30일 | 128 KB | 99.5% |
| Express One Zone | 없음 | 없음 | 99.95% |
| Glacier Instant Retrieval | 90일 | 128 KB | 99.9% |
| Glacier Flexible Retrieval | 90일 | 객체당 40 KB 메타데이터 오버헤드 | restore 후 99.99% |
| Glacier Deep Archive | 180일 | 객체당 40 KB 메타데이터 오버헤드 | restore 후 99.99% |

내구성은 전 클래스가 99.999999999퍼센트로 동일합니다. **가용성이 갈리는 것이지 내구성이 갈리는 것이 아닙니다.** One Zone-IA 를 배제해야 하는 근거도 내구성이 아니라 단일 AZ 구성과 99.5퍼센트 가용성입니다.

Glacier Flexible Retrieval 과 Deep Archive 의 40 KB 오버헤드는 구성이 둘로 나뉩니다. 32 KB 는 해당 Glacier 요율로, 8 KB 는 S3 Standard 요율로 계산됩니다. 40 KB 짜리 로그 객체를 여기로 보내면 메타데이터 오버헤드가 객체 크기와 맞먹어 단가 이점이 사라집니다.

전환 규칙 자체에도 제약이 붙습니다.

- **2024년 9월부터 lifecycle 기본 동작은 128 KB 미만 객체를 어떤 클래스로도 전환하지 않는 것입니다.** 전환하려면 `ObjectSizeGreaterThan` 필터를 넣거나 `PutBucketLifecycleConfiguration` 에 `x-amz-transition-default-minimum-object-size` 헤더를 씁니다. 2024년 9월 이전에 만든 구성은 규칙을 손대기 전까지 이전 동작을 유지합니다.
- **최소 보관 기간을 위반하는 전환은 단일 lifecycle rule 로 표현할 수 없습니다.** Glacier Instant Retrieval 로 4일에 보낸 뒤 Deep Archive 로 20일에 보내는 규칙은 만들 수 없고, 최소 94일이어야 합니다.
- **전환은 waterfall 단방향입니다.** Glacier Flexible Retrieval 에서는 Deep Archive 로만 갈 수 있고, Deep Archive 에서는 어떤 클래스로도 lifecycle 전환이 되지 않습니다.
- **전환 과금은 물리적 전환 전이라도 규칙 충족일부터 목적지 클래스 요율로 시작됩니다.** 예외는 Intelligent-Tiering 으로의 전환뿐이고 이때만 물리 전환 완료 후 요율이 바뀝니다.

전체 전환 경로는 다음과 같습니다.

| 출발 | 갈 수 있는 곳 |
| :--- | :--- |
| Standard | Standard-IA, Intelligent-Tiering, One Zone-IA, Glacier Instant Retrieval, Glacier Flexible Retrieval, Deep Archive |
| Standard-IA | Intelligent-Tiering, One Zone-IA, GIR, GFR, GDA |
| Intelligent-Tiering, Frequent 와 Infrequent Access 계층 | One Zone-IA, GIR, GFR, GDA |
| Intelligent-Tiering, Archive Instant Access 계층 | GIR, GFR, GDA |
| Intelligent-Tiering, Archive Access 계층 | GFR, GDA |
| Intelligent-Tiering, Deep Archive Access 계층 | GDA |
| One Zone-IA | GFR, GDA |
| Glacier Instant Retrieval | GFR, GDA |
| Glacier Flexible Retrieval | GDA |
| Glacier Deep Archive | 없음 |

조기 삭제와 규칙 운용에도 함정이 있습니다. **최소 보관 기간 안에 삭제하거나 덮어쓰면 prorated early deletion fee 가 붙습니다.** 최소 기간이 있는 클래스에서 그 기간 전에 다른 클래스로 전환해도 남은 기간분을 과금합니다. 그리고 **tag 기반 필터는 하루 단위로 평가하고 실행 시점에 객체의 현재 태그를 다시 봅니다.** rule 정책 변경의 전파에는 최대 15분이 걸리므로, 전환을 확실히 막아야 한다면 rule 을 끄는 것보다 트리거 태그를 제거하는 쪽이 확실합니다.

---

## 12. Glacier restore 와 Intelligent-Tiering archive restore 는 다른 일을 한다

이름이 같은 restore 인데 결과가 다릅니다. 비용 계산이 갈리므로 문항에 자주 나옵니다.

| 항목 | Glacier Flexible Retrieval, Deep Archive | Intelligent-Tiering 의 Archive Access, Deep Archive Access |
| :--- | :--- | :--- |
| restore 결과 | 임시 사본이 생긴다 | 객체가 실제로 Frequent Access 계층으로 이동한다 |
| 객체의 storage class | 그대로 유지된다. `HeadObject` 와 `GetObject` 가 계속 GFR 또는 GDA 를 반환한다 | Intelligent-Tiering 그대로이고 계층만 바뀐다 |
| restore 기간의 과금 | archive 요율과 임시 사본의 S3 Standard 요율을 함께 낸다 | Frequent Access 계층 요율 |
| 이후 동작 | 임시 사본이 만료되면 사라진다 | 30일 미접근에 Infrequent Access, 최소 90일에 Archive Access, 최소 180일에 Deep Archive Access 로 다시 내려간다 |
| 클래스를 실제로 바꾸려면 | restore 후 copy 로 덮어쓴다 | 별도 조치가 필요 없다 |

Glacier 계열은 객체당 동시에 처리되는 restore 요청이 1개입니다. 같은 객체에 restore 를 중복으로 넣어도 병렬로 처리되지 않습니다.

---

## 13. Requester Pays 로 과금 주체를 옮길 때 남는 것

대용량 데이터셋을 외부에 공개할 때 다운로드 비용을 요청자에게 넘기는 수단이 Requester Pays 입니다. 옮겨지는 항목과 옮겨지지 않는 항목이 명확합니다.

- **요청자가 request 비용과 데이터 다운로드 비용을 냅니다.**
- **소유자는 항상 저장 비용을 냅니다.** 이 항목은 옮겨지지 않습니다.
- 익명 요청과 SOAP 요청은 불가능합니다.
- 요청에 `x-amz-request-payer` 헤더나 `RequestPayer` 파라미터가 필요하고 CLI 는 `--request-payer` 를 씁니다.
- **IAM role 을 assume 하면 그 role 이 속한 계정이 과금됩니다.**
- `AccessDenied` 로 HTTP 403 이 나고 그 요청이 소유자 계정이나 조직 내부에서 시작됐다면 소유자가 과금됩니다.
- **`RestoreObject` 는 요청자가 request 비용만 내고 retrieval 비용은 소유자가 냅니다.**

마지막 항목이 함정입니다. 아카이브된 대용량 데이터셋을 Requester Pays 로 공개하면 restore 검색 비용은 여전히 소유자 부담입니다.

---

## 14. Storage Lens 의 free 와 advanced 가 답하는 질문이 다르다

버킷이 수백 개인 조직에서 "어디에 무엇이 쌓여 있는가" 를 답하는 도구가 S3 Storage Lens 입니다.

| 항목 | free | advanced |
| :--- | :--- | :--- |
| 지표 조회 기간 | 14일 | 15개월 |
| activity metrics | 없다 | 있다 |
| detailed status code metrics | 없다 | 있다 |
| advanced cost optimization 과 data protection metrics | 없다 | 있다 |
| prefix aggregation | 없다 | 있다 |
| contextual recommendations | 없다 | 있다 |
| CloudWatch publishing | 없다 | 있다 |

지표 자체는 두 계층 모두 15개월 보관됩니다. 갈리는 것은 조회 가능 기간입니다. home Region 당 대시보드는 최대 50개입니다.

**"어느 prefix 가 오래 미접근인가" 를 묻는 지문이면 advanced 가 필요합니다.** activity metrics 와 prefix aggregation 이 둘 다 advanced 에만 있기 때문입니다.

---

## 15. 청구서를 분해하는 두 축은 태그와 카테고리다

비용을 줄이기 전에 누가 무엇에 얼마를 쓰는지부터 나눠야 합니다. 나누는 수단이 두 가지이고 동작 원리가 다릅니다.

| 항목 | cost allocation tag | Cost Categories |
| :--- | :--- | :--- |
| 붙는 대상 | 리소스 | 청구 라인 아이템 |
| 태깅되지 않은 리소스 | 배분되지 않는다 | 규칙으로 묶을 수 있다 |
| 소급 | backfill 을 별도 요청해야 한다 | 당월 1일부터 자동 소급된다 |
| 관리 주체 | management account 와 조직에 속하지 않은 단독 계정 | management account 와 단독 계정 |

cost allocation tag 는 AWS-generated 와 user-defined 두 종류이고 각각 따로 활성화해야 리포트에 나타납니다. 접두사가 `aws:` 와 `user:` 로 다릅니다. 활성화 반영까지 최대 24시간이 걸립니다. 쿼터는 payer 계정당 활성 태그 키 최대 500개이고, 한 번의 API 또는 콘솔 요청으로 활성화나 비활성화할 수 있는 태그는 20개입니다. `awsApplication` 처럼 자동 활성화되는 태그는 쿼터에 포함되지 않습니다.

backfill 의 동작은 정확히 알아야 오답을 피합니다.

- management account 가 **최대 12개월까지** 소급 요청합니다.
- **소급되는 것은 태그의 현재 활성화 상태입니다.** 비활성 상태도 그대로 소급되어 이전 달 데이터에서 태그가 사라질 수 있습니다.
- **리소스에 태그가 실제로 붙어 있던 기간만 값이 채워집니다.** 지금 태깅한 리소스의 지난달 비용이 채워지지는 않습니다.
- 진행 중인 backfill 이 있으면 새 요청을 넣을 수 없고 요청은 24시간에 1회입니다.
- Cost Explorer, Data Exports, CUR 이 자동으로 갱신되지만 이들이 24시간 주기로 새로고침하므로 즉시 반영되지는 않습니다.

Cost Categories 는 지원 dimension 이 정해져 있습니다. Account, Charge type, Cost category, Region, Service, Tag key, Usage Type, Billing Entity 여덟 가지이고 **resource ID 는 없습니다.** rule type 은 Regular Rule 과 Inherited Value 둘입니다. 월 중간에 만들거나 수정해도 당월 1일부터 소급 적용되며 처리에 최대 24시간이 걸립니다. Cost Explorer, Budgets, CUR, Cost Anomaly Detection 에서 쓸 수 있습니다. 쿼터는 management account 당 50개, 카테고리당 rule 은 API 500개와 UI 100개, split charge rule 은 카테고리당 10개입니다.

---

## 16. Cost Explorer 와 CUR 과 Data Exports 중 무엇을 여는가

세 도구는 대체재가 아니라 답할 수 있는 질문의 해상도가 다릅니다.

| 도구 | 데이터 범위 | 갱신 | 요금 | 답할 수 있는 질문 |
| :--- | :--- | :--- | :--- | :--- |
| Cost Explorer | 과거 13개월, 미래 18개월 예측 | 최소 24시간마다 | 콘솔 무료, API 는 paginated 요청당 $0.01 | 추세, 서비스별 비중, 커밋 추천 |
| Cost and Usage Report | 시간, 일, 월 단위 라인 아이템 | 하루 최대 3회, 최소 1회 | S3 저장과 쿼리 비용 | resource ID 수준 조사, SQL 집계 |
| Data Exports | CUR 2.0 과 FOCUS 등 5종 export | CUR 과 동일 | S3 저장과 쿼리 비용 | 표준 스키마 기반 분석 |

Cost Explorer 는 활성화 후 당월 데이터가 약 24시간, 나머지는 며칠 더 걸립니다. **한 번 활성화하면 비활성화할 수 없습니다.**

CUR 은 사용자 소유 S3 버킷으로 배달되고 첫 배달까지 최대 24시간이 걸립니다. CSV 로 나오며 약 100만 행을 넘으면 파일이 분할됩니다. Support 요금은 다음 달 6일 또는 7일에 반영됩니다.

Data Exports 의 export 유형은 다섯 가지입니다. Standard data export 의 테이블은 CUR 2.0, Cost optimization recommendations, FOCUS 1.2 with AWS columns, FOCUS 1.0 with AWS columns, Carbon emissions 이고 나머지는 cost and usage dashboard 와 legacy data export 입니다. Cost optimization recommendations 테이블의 출처는 Cost Optimization Hub 입니다. **신규 구성에서는 CUR 2.0 이 권장 경로입니다.**

문항에서 갈리는 지점은 두 개입니다. 지문에 "granular", "line item", "SQL", "Athena", "resource ID" 가 나오면 CUR 쪽이고, **13개월을 넘는 기간을 요구하면 Cost Explorer 는 그 시점에 탈락합니다.**

---

## 17. Budgets 와 budget action 이 실제로 할 수 있는 통제

Budgets 는 알림에서 끝나지 않고 action 으로 통제까지 갑니다. 다만 action 의 종류와 적용 대상에 경계가 있습니다.

budget action 유형은 셋입니다.

| action | 대상 |
| :--- | :--- |
| IAM policy 적용 | 계정 안의 IAM user, group, role |
| SCP 적용 | 조직의 OU |
| EC2 또는 RDS 인스턴스 중지 | budget 이 정의된 계정의 인스턴스 |

**management account 에서 다른 계정의 OU 에 SCP 를 적용할 수는 있지만, 다른 계정의 EC2 나 RDS 인스턴스를 타깃할 수는 없습니다.** 조직 차원에서 초과 시 실행 중인 인스턴스까지 멈춰야 한다면 member 계정 안의 자동화가 따로 필요합니다.

같은 threshold 에 여러 action 을 동시에 걸 수 있고, 각 action 은 자동 실행과 수동 승인 중에 고릅니다. **SCP 는 신규 API 호출을 막을 뿐 이미 실행 중인 리소스를 중지하지 않습니다.** 이 문장이 오답 선지의 핵심 재료입니다.

접근 범위에도 제약이 있습니다. management account 가 특정 member 계정을 필터로 만든 budget 은 management account 접근 권한이 있어야 보이고, **budget 의 cross-account 사용은 지원되지 않습니다.**

쿼터는 다음과 같습니다. 계정당 action 이 붙은 무료 budget 2개, budget 당 action 10개, 계정당 budget action 100개, management account 당 budget 총 20,000개입니다. budget report 는 최대 50개, report 당 budget 50개, 이메일 수신자 50명입니다.

---

## 18. Cost Anomaly Detection 이 보는 범위와 보지 않는 범위

Budgets 가 사람이 정한 임계값을 보는 도구라면 Cost Anomaly Detection 은 임계값 없이 이상 패턴을 잡는 도구입니다. 대신 통제 기능이 없고 분석 대상에 구멍이 있습니다.

- **net unblended cost 를 대상으로 하루 약 3회 돕니다.** Usage charge type 과 NetUnblendedCost 만 분석합니다.
- Cost Explorer 데이터를 쓰므로 사용 발생 후 이상 탐지까지 최대 24시간이 걸립니다.
- 새 monitor 는 동작까지 24시간이 필요하고, 새로 구독한 서비스는 이상 탐지에 10일치 이력이 필요합니다.
- root cause 는 service, account, Region, usage type 네 차원으로 쪼개 금액 순으로 제시합니다.

미지원 대상 목록이 문항의 재료입니다. **AWS Marketplace, AWS Support, WorkSpaces, Cost Explorer, Budgets, Shield, Route 53, ACM** 이 분석되지 않습니다. AWS Marketplace 의 제3자 제품과 서비스에는 Amazon Bedrock 의 제3자 모델과 Bedrock Marketplace 모델도 포함됩니다.

Marketplace 서드파티 소프트웨어 구독이 갑자기 뛰는 상황은 Cost Anomaly Detection 으로 잡을 수 없습니다. **Billing entity 를 필터로 건 cost budget 이 그 자리를 대신합니다.** Billing Entity 가 Cost Categories 의 dimension 목록에도 들어 있는 이유가 여기 있습니다.

쿼터는 계정당 alert subscription 100개, subscription 당 이메일 수신자 10명과 SNS topic 1개, customer managed monitor 는 management account 당 500개입니다.

---

## 19. rightsizing 권고가 비어 보이는 세 가지 이유

Compute Optimizer 를 켰는데 권고가 부실하다는 상황에는 원인이 정해져 있습니다. 각각 다른 전제 조건에 대응합니다.

![Compute Optimizer 와 Cost Explorer rightsizing 과 Cost Optimization Hub 사이의 입력과 출력 관계](/assets/img/sap-c02/cost-recommendation-sources.webp)

그림은 세 권고 도구가 각각 무엇을 입력으로 받고 결과가 어디로 모이는지를 보여줍니다. Cost Explorer 활성화가 두 도구의 공통 전제라는 것과, Cost Explorer rightsizing 결과와 Compute Optimizer 결과 사이의 포함 관계도 여기에 있습니다.

Compute Optimizer 의 지원 대상은 EC2 instance, EC2 Auto Scaling group, EBS volume, Lambda function, ECS service on Fargate, commercial software license, Aurora 와 RDS database, NAT Gateway, DynamoDB, ElastiCache, MemoryDB, DocumentDB, WorkSpaces, SageMaker 입니다. 오래된 정리는 EC2, ASG, EBS, Lambda 네 종으로 적는 경우가 있는데 현재는 훨씬 넓습니다.

데이터 요건은 다음과 같습니다.

| 항목 | 값 |
| :--- | :--- |
| 기본 lookback | 14일 |
| enhanced infrastructure metrics 활성화 시 | 93일. 유료 기능이다 |
| EC2 와 ASG 최소 데이터 | 최근 14일 중 최소 30시간의 CloudWatch 지표 |
| 분석 소요 | 최대 24시간 |
| 사용률 집계 구간 | EC2, ASG, EBS, Lambda, license 는 5분 구간 최대치. ECS on Fargate 는 1분 구간 최대치 |
| Lambda 메모리 권고 조건 | 설정 메모리 1,792 MB 이하이고 최근 14일간 최소 50회 호출 |

메모리 지표는 별도 조건이 붙습니다. **CloudWatch agent 가 있어야 수집됩니다.** Linux 는 `CWAgent` 네임스페이스의 `mem_used_percent` 를 쓰고 레거시로 `System/Linux` 의 `MemoryUtilization` 도 인정됩니다. Windows 는 `CWAgent` 의 `Available MBytes` 를 우선하고 `Memory % Committed Bytes In Use` 보다 앞세웁니다. **네임스페이스에 `InstanceId` dimension 이 없으면 수집되지 않습니다.** 외부 수집으로는 Datadog, Dynatrace, Instana, New Relic 을 지원합니다.

절감액과 커밋 반영에도 전제가 있습니다. **Compute Optimizer 가 절감액을 계산하려면 Cost Explorer 가 활성화되어 있어야 하고**, RI 와 SP 가격을 반영한 권고를 받으려면 Cost Optimization Hub opt-in 이 추가로 필요합니다.

세 도구의 관계는 다음과 같습니다.

| 도구 | 범위 | 성질 |
| :--- | :--- | :--- |
| Compute Optimizer | 14종 리소스 | 성능까지 고려한 권고를 내고 비용이 늘어나는 권고도 포함한다 |
| Cost Explorer rightsizing recommendation | EC2 한정 | 14일 lookback. 최대 CPU 1% 이하는 idle 로 보고 종료를 권고하고, 1% 초과이면서 타입 변경으로 절감이 가능하면 수정을 권고한다. 추정 절감액 $0 이상만 제시하므로 Compute Optimizer 결과의 부분집합이다 |
| Cost Optimization Hub | rightsizing, idle 삭제, SP, RI 권고 | 계정과 리전에 걸쳐 모으고 중복 절감액을 제거한다. 계정의 실제 RI 와 SP 조건을 반영한다. rightsizing 과 idle 권고의 실제 출처는 Compute Optimizer 다 |

---

## 20. Trusted Advisor 는 조회만 하고 support plan 이 범위를 정한다

Trusted Advisor 는 비용, 성능, 보안, 내결함성, 서비스 한도 카테고리의 check 를 제공합니다. 시험에서 갈리는 것은 두 가지입니다.

**첫째, Trusted Advisor 는 한도를 조회할 뿐 변경하지 못합니다.** 한도 증설은 Service Quotas 또는 Support case 입니다.

**둘째, 접근 가능한 check 범위가 support plan 에 따라 다릅니다.**

| plan | Trusted Advisor 범위 |
| :--- | :--- |
| Basic | Service Limits 카테고리 전체와 Security, Fault tolerance 의 일부 check 만. 자동 갱신이 없어 Security check 는 수동 refresh 가 필요하다 |
| Business Support+ 이상 | 500개가 넘는 check 와 AWS Support API |

현재 support plan 라인업은 Basic, AWS Business Support+, AWS Enterprise Support, AWS Unified Operations 입니다. **Developer, Business, Enterprise On-Ramp 는 2027-01-01 에 종료되고** AWS GovCloud US 에서는 유지됩니다. Business Support+ 는 계정당 월 최소 $29 이고, Enterprise 는 최소 $5,000 에 15분 응답과 전담 TAM 을 제공합니다.

"Basic support 계정에서 Trusted Advisor 의 비용 최적화 check 로 미사용 EBS 볼륨을 찾는다" 는 선지가 성립하지 않는 이유가 이 표입니다.

---

## 21. 데이터 전송은 경로마다 다른 요금이 붙는다

커밋 할인이 닿지 않는 축 중 가장 큰 것이 데이터 전송입니다. 같은 바이트라도 어느 경로를 지나느냐에 따라 붙는 요금이 달라집니다.

![private subnet 에서 출발한 트래픽이 지나는 경로별 과금 항목](/assets/img/sap-c02/data-transfer-charge-points.webp)

그림은 private subnet 의 컴퓨트에서 출발한 트래픽이 통과할 수 있는 다섯 가지 경로와 각 경로에 붙는 요금 항목을 담고 있습니다. 무과금 경로와 유료 경로가 함께 있습니다.

먼저 **과금되지 않는 구간**입니다.

- 모든 리전 모든 서비스의 inbound 데이터 전송
- 같은 AZ 안의 private IP 통신
- 같은 리전의 S3 와 DynamoDB 로 가는 gateway endpoint 트래픽
- RDS Multi-AZ 의 primary 와 standby 복제
- CloudFront 와 AWS origin 사이의 전송

그다음이 과금 지점입니다.

| 지점 | 요금 구조 |
| :--- | :--- |
| NAT Gateway | 시간당 요금과 처리 GB 당 요금이 함께 붙는다. US East (Ohio) 기준 시간당 $0.045, GB 당 $0.045. Regional NAT gateway 는 AZ 당 시간당 $0.045 |
| interface endpoint | AZ 마다 provisioned 시간만큼 과금되고 처리 GB 당 요금이 별도로 붙는다 |
| gateway endpoint | 추가 요금이 없다 |
| 같은 리전 AZ 간 VPC peering | In 과 Out 양방향 모두 $0.01/GB |
| 리전 간 전송 | 전송 요금이 붙는다 |
| 인터넷 egress | 매월 100 GB 무료. 모든 AWS 서비스와 리전을 합산해 적용되고 중국과 GovCloud 는 제외된다 |
| CloudFront | AWS origin 에서 가져오는 전송은 면제된다. Free plan 은 월 100 GB 전송과 100만 요청을 포함한다 |

interface endpoint 의 데이터 처리 요금은 **리전 내 모든 interface endpoint 합산 기준 누진**입니다. 첫 1 PB 는 $0.01/GB, 다음 4 PB 는 $0.006/GB, 5 PB 초과는 $0.004/GB 입니다. 시간당 요금은 요금 페이지가 endpoint ENI 당 시간당 $0.01 을 예시로 들지만 리전별 표를 확인하지 못했으므로 리전 무관 단가로 단정하지 않습니다.

interface endpoint 구성 권고도 함께 나옵니다. AZ 당 서브넷 하나를 설정하며, 프로덕션에서는 AZ 2개 이상 구성과 private DNS 활성화와 Regional DNS 이름 사용이 권고됩니다. 같은 AZ 경로를 강제하려면 zonal endpoint 이름이나 ENI IP 를 직접 씁니다.

---

## 22. NAT Gateway 트래픽을 endpoint 로 빼는 계산

NAT Gateway 처리 요금이 청구서 상위로 올라오면 조치는 두 방향입니다. AWS 문서가 명시한 절감법이 정확히 이 둘입니다.

1. **트래픽이 많으면 리소스를 NAT gateway 와 같은 AZ 에 두거나 AZ 마다 NAT gateway 를 만듭니다.**
2. **NAT 를 통과하는 트래픽 대부분이 endpoint 를 지원하는 AWS 서비스로 간다면 interface endpoint 나 gateway endpoint 를 만듭니다.**

첫 번째 항목이 직관과 반대로 읽히는 지점입니다. NAT Gateway 를 한 AZ 로 통합하면 시간당 요금은 줄지만, 다른 AZ 리소스의 트래픽이 AZ 경계를 넘으면서 교차 AZ 전송 요금이 새로 붙습니다. **처리 GB 요금은 그대로이므로 트래픽이 많을수록 통합이 손해입니다.**

두 번째 항목에서 endpoint 종류를 고르는 기준은 서비스입니다.

| 대상 | 수단 | 요금 |
| :--- | :--- | :--- |
| 같은 리전의 S3, DynamoDB | gateway endpoint | 없다 |
| 다른 리전의 S3, DynamoDB | 리전별 gateway endpoint에는 매칭되지 않는다. 지원 조건에 따라 S3 cross-Region interface endpoint 또는 DynamoDB interface endpoint와 peering/TGW 같은 별도 경로를 검토한다 | 실제 경로에 따라 NAT, internet gateway, Transit Gateway 또는 interface endpoint 처리 요금 |
| ECR, Secrets Manager, KMS, SSM 등 | interface endpoint | AZ 당 시간 요금과 처리 GB 요금 |

**gateway endpoint 는 S3 와 DynamoDB 만 지원하고 PrivateLink 를 쓰지 않습니다.** route table 의 리전별 prefix list 로 라우팅되므로 다른 리전의 S3 나 DynamoDB 트래픽에는 매칭되지 않습니다. 그렇다고 경로가 항상 internet gateway로 고정되는 것은 아닙니다. S3는 지원되는 경우 cross-Region interface endpoint를 사용할 수 있고, DynamoDB는 다른 리전 VPC에서 interface endpoint를 peering 또는 Transit Gateway 경로로 사용할 수 있습니다. 이런 별도 경로가 없으면 실제 route table의 0.0.0.0/0 대상에 따라 NAT, internet gateway, Transit Gateway 등이 선택됩니다.

대량의 S3 트래픽이 NAT 를 통과하고 있다면 gateway endpoint 도입이 가장 큰 절감입니다. 추가 요금이 0 이므로 절감액이 그대로 NAT 처리 요금 전액이 됩니다. 반면 ECR 이나 Secrets Manager 를 gateway endpoint 로 처리하겠다는 선지는 서비스 지원 범위에서 이미 탈락합니다.

---

## 23. 암기해야 하는 하드 리밋과 쿼터

시험에서 선지를 직접 가르는 수치입니다.

**커밋과 예약**

| 항목 | 값 |
| :--- | :--- |
| Savings Plans 기간 | 1년 = 365일 = 31,536,000초, 3년 = 1,095일 = 94,608,000초 |
| Savings Plans 최대 할인 | Compute 66%, EC2 Instance 72%, SageMaker AI 64%, Database 35% |
| Savings Plans 취소 | 불가능 |
| Savings Plans 수량 한도 | 제한 없음 |
| Zonal RI 기본 한도 | AZ 당 20개 |
| Regional RI 기본 한도 | Region 당 20개 |
| Dedicated Instance 추가 요금 | Region 당 시간당 $2, 할인 대상 아님 |
| future-dated Capacity Reservation 최소 단위 | 32 vCPU |
| future-dated Capacity Reservation 지원 family | C, G, I, M, R, T, U, X |
| Spot interruption notice | stop 또는 terminate는 2분 전. hibernate는 interruption notice가 오지만 2분 전 경고 없이 즉시 시작 |
| Spot 폴링 권고 주기 | 5초 |

**S3**

| 항목 | 값 |
| :--- | :--- |
| Intelligent-Tiering 자동 하향 | 30일 미접근에 Infrequent Access, 90일 미접근에 Archive Instant Access |
| Intelligent-Tiering 선택 계층 | Archive Access 최소 90일, Deep Archive Access 최소 180일, 둘 다 최대 730일 |
| Intelligent-Tiering 제외 크기 | 128 KB 미만 |
| Intelligent-Tiering restore TPS | 계정당 리전당 1,000 |
| 최소 보관 기간 | Standard-IA 30일, One Zone-IA 30일, GIR 90일, GFR 90일, GDA 180일 |
| 최소 과금 객체 크기 | Standard-IA, One Zone-IA, GIR 은 128 KB |
| Glacier 메타데이터 오버헤드 | GFR 과 GDA 는 객체당 40 KB (32 KB Glacier 요율 + 8 KB S3 Standard 요율) |
| lifecycle 기본 최소 전환 크기 | 128 KB (2024년 9월 이후) |
| lifecycle rule 정책 변경 전파 | 최대 15분 |
| 객체당 동시 restore 요청 | 1개 |
| Storage Lens 조회 기간 | free 14일, advanced 15개월 |
| Storage Lens 대시보드 | home Region 당 50개 |

**가시화와 통제**

| 항목 | 값 |
| :--- | :--- |
| Cost Explorer 과거 데이터 | 13개월 |
| Cost Explorer 예측 | 18개월 |
| Cost Explorer API 요금 | paginated 요청당 $0.01 |
| Cost Explorer 비활성화 | 불가능 |
| CUR 갱신 | 하루 최대 3회, 최소 1회. 첫 배달까지 최대 24시간 |
| CUR 파일 분할 기준 | 약 100만 행 |
| cost allocation tag 활성 키 | payer 계정당 500개 |
| 한 요청의 태그 활성화 개수 | 20개 |
| cost allocation tag 반영 | 최대 24시간 |
| backfill 소급 범위 | 최대 12개월, 24시간에 1회 |
| Cost Categories | management account 당 50개, 카테고리당 rule API 500개 UI 100개, split charge rule 10개 |
| Budgets 갱신 | 하루 최대 3회, 간격 8시간에서 12시간 |
| Budgets 쿼터 | action 이 붙은 무료 budget 2개, budget 당 action 10개, 계정당 action 100개, management account 당 budget 20,000개 |
| budget report | 최대 50개, report 당 budget 50개, 이메일 수신자 50명 |
| Cost Anomaly Detection 실행 | 하루 약 3회, 탐지까지 최대 24시간 |
| Cost Anomaly Detection 준비 기간 | 새 monitor 24시간, 새 서비스 10일치 이력 |
| Cost Anomaly Detection 쿼터 | 계정당 subscription 100개, subscription 당 이메일 10명과 SNS topic 1개, monitor 500개 |

**권고와 지원**

| 항목 | 값 |
| :--- | :--- |
| Compute Optimizer 기본 lookback | 14일 |
| enhanced infrastructure metrics lookback | 93일 |
| Compute Optimizer 최소 데이터 | 최근 14일 중 30시간 |
| Compute Optimizer 분석 소요 | 최대 24시간 |
| Lambda 메모리 권고 조건 | 1,792 MB 이하, 최근 14일 최소 50회 호출 |
| Cost Explorer rightsizing idle 기준 | 최대 CPU 1% 이하 |
| Business Support+ 최소 요금 | 계정당 월 $29 |
| Enterprise Support 최소 요금 | $5,000 |
| Developer, Business, Enterprise On-Ramp 종료 | 2027-01-01 |

**데이터 전송**

| 항목 | 값 |
| :--- | :--- |
| NAT Gateway (US East Ohio) | 시간당 $0.045, 처리 GB 당 $0.045 |
| 같은 리전 AZ 간 VPC peering | 양방향 각각 $0.01/GB |
| 인터넷 egress 무료량 | 월 100 GB, 중국과 GovCloud 제외 |
| interface endpoint 처리 요금 누진 | 첫 1 PB $0.01/GB, 다음 4 PB $0.006/GB, 5 PB 초과 $0.004/GB |
| CloudFront Free plan | 월 100 GB 전송과 100만 요청 |

---

## 24. 답이 갈리는 짝 비교

| 짝 | 차이를 만드는 제약 |
| :--- | :--- |
| Compute SP 대 EC2 Instance SP | Compute SP 는 family, size, Region, OS, tenancy 전부 유연하고 Fargate 와 Lambda 까지 커버하지만 최대 66% 다. EC2 Instance SP 는 Region 과 family 를 고정하는 대신 최대 72% 이고 Fargate 와 Lambda 에 적용되지 않는다. 적용 순서도 EC2 Instance SP 가 먼저다 |
| Savings Plans 대 Reserved Instances | SP 는 시간당 금액 약정이라 exchange 나 modify 개념이 없고 취소도 불가능하다. RI 는 구성 약정이라 Convertible 이면 exchange, Standard 면 Marketplace 매각이라는 출구가 있다 |
| Standard RI 대 Convertible RI | Standard 는 exchange 불가에 Marketplace 판매와 구매가 가능하다. Convertible 은 exchange 가능에 Marketplace 판매와 구매가 불가능하다. modify 는 둘 다 된다 |
| Regional RI 대 Zonal RI | Regional 은 용량 예약이 없고 AZ 유연성과 조건부 size 유연성과 purchase queuing 이 있다. Zonal 은 지정 AZ 에 용량을 예약하는 대신 유연성과 queuing 이 없다. 가격 차이는 없다 |
| ODCR 대 RI 또는 SP | ODCR 은 용량만 주고 할인은 주지 않으며 즉시형은 약정이 없다. SP 와 Regional RI 는 할인만 주고 용량은 주지 않는다. 둘 다 필요하면 겹친다 |
| utilization 대 coverage | utilization 은 산 커밋이 얼마나 쓰였는지를 재고 낮으면 과잉 구매다. coverage 는 사용분 중 얼마가 덮였는지를 재고 낮으면 구매 부족이다 |
| Cost Explorer 대 CUR 과 Data Exports | Cost Explorer 는 13개월 시각화와 18개월 예측이고 API 는 요청당 $0.01 이다. resource ID 와 라인 아이템 수준 조사가 필요하면 CUR 을 S3 로 받아 Athena 로 쿼리한다 |
| Budgets 대 Cost Anomaly Detection | Budgets 는 사람이 정한 임계값 대비 초과 또는 초과 예상을 알리고 action 으로 통제까지 간다. Anomaly Detection 은 임계값 없이 이상 패턴을 잡지만 action 이 없고 Marketplace 등 미지원 영역이 있다 |
| cost allocation tag 대 Cost Categories | 태그는 리소스에 붙는 key-value 라 태깅하지 않으면 배분되지 않는다. Cost Categories 는 라인 아이템에 규칙으로 붙어 태깅되지 않은 리소스도 계정, 서비스, 사용 유형으로 묶고 당월 1일로 소급된다. 대신 resource ID dimension 이 없다 |
| Compute Optimizer 대 Cost Explorer rightsizing 대 Cost Optimization Hub | Compute Optimizer 는 14종 리소스에 성능까지 고려한 권고를 내고 비용 증가 권고도 포함한다. Cost Explorer rightsizing 은 EC2 한정에 절감액 $0 이상만 내는 부분집합이다. Cost Optimization Hub 는 두 권고와 SP, RI 권고를 계정과 리전에 걸쳐 모아 중복을 제거한다 |
| Trusted Advisor 대 Service Quotas | Trusted Advisor 는 한도를 조회만 한다. 증설은 Service Quotas 또는 Support case 다. 전체 check 는 Business Support+ 이상이 필요하다 |
| gateway endpoint 대 interface endpoint 대 NAT Gateway | gateway endpoint 는 S3 와 DynamoDB 전용이고 요금이 없다. interface endpoint 는 다른 서비스를 커버하지만 AZ 당 시간 요금과 GB 요금이 붙는다. NAT 는 시간당 요금 위에 처리 GB 요금이 또 붙는다 |
| Intelligent-Tiering 대 lifecycle 수동 전환 | 접근 패턴을 모르면 Intelligent-Tiering 이다. 최소 보관 기간과 retrieval fee 가 없고 대신 객체당 monitoring 요금이 붙어 작은 객체가 많으면 불리하다. 패턴을 알면 lifecycle 이 저장 단가가 낮지만 최소 보관 기간과 전환 요청 비용을 떠안는다 |
| Glacier 계열 restore 대 Intelligent-Tiering archive 계층 restore | Glacier 계열은 임시 사본만 만들고 객체 클래스가 그대로라 archive 요율과 S3 Standard 요율을 이중으로 낸다. Intelligent-Tiering 의 archive 계층은 restore 하면 객체가 실제로 Frequent Access 로 이동한다 |
| Standard-IA 대 One Zone-IA | 최소 보관 기간 30일과 최소 과금 128 KB 는 같다. 갈리는 것은 AZ 구성과 설계 가용성 99.9% 대 99.5% 다. 내구성은 동일하다 |
| Storage Lens free 대 advanced | free 는 14일 조회에 요약과 비용 최적화와 데이터 보호 지표까지다. advanced 는 15개월 조회에 activity metrics, detailed status code metrics, prefix aggregation, 권고, CloudWatch publishing 을 더한다 |
| Requester Pays 로 옮겨지는 비용 대 남는 비용 | request 와 다운로드 비용은 요청자가 낸다. 저장 비용은 항상 소유자가 내고 `RestoreObject` 의 retrieval 비용도 소유자가 낸다 |
| SCP budget action 대 인스턴스 중지 budget action | SCP 는 OU 에 걸어 신규 API 호출을 막는다. 실행 중 인스턴스 중지는 별도 action 이고 budget 이 정의된 계정의 리소스만 타깃한다 |

---

## 25. 그럴듯하지만 성립하지 않는 조합

| 조합 | 성립하지 않는 이유 |
| :--- | :--- |
| Savings Plans 를 사서 특정 AZ 의 용량을 확보한다 | SP 는 capacity reservation 을 제공하지 않는다. 용량은 ODCR 또는 Zonal RI 다 |
| Savings Plans 를 사면 Spot 사용분도 더 싸진다 | SP 는 Spot 사용분과 RI 가 이미 커버한 사용분에 적용되지 않는다 |
| Compute Savings Plans 를 사면 EKS 클러스터 요금도 줄어든다 | 클러스터의 기반 EC2 사용분은 커버하지만 EKS 자체 요금은 커버하지 않는다 |
| Dedicated Instance 로 옮기고 SP 로 전체 요금을 낮춘다 | Region 당 시간당 $2 요금은 SP 로 할인되지 않는다 |
| 남는 Convertible RI 를 Reserved Instance Marketplace 에 팔아 회수한다 | Marketplace 판매는 Standard RI 만 가능하다 |
| Standard RI 를 exchange 해서 새 family 로 바꾼다 | exchange 는 Convertible RI 만 가능하다 |
| Regional RI 로 특정 AZ 의 용량을 미리 잡는다 | Regional RI 는 용량을 예약하지 않는다 |
| instance size flexibility 가 있으니 Windows RI 도 같은 family 의 큰 사이즈를 커버한다 | size flexibility 는 Amazon Linux/Unix 에 default tenancy 인 Regional RI 에만 적용된다 |
| Zonal RI 를 사면 그 할인이 Capacity Reservation 에도 적용된다 | Zonal RI 의 billing discount 는 Capacity Reservation 에 적용되지 않는다 |
| Capacity Reservation 은 인스턴스를 띄우지 않으면 과금되지 않는다 | 미사용 상태에서도 과금되고 계정의 On-Demand instance 한도를 차지한다 |
| Capacity Reservation 을 Dedicated Host 와 함께 쓴다 | Dedicated Host 와는 함께 쓸 수 없다. Dedicated Instance 와는 가능하다 |
| 이번 시간에 남은 SP commitment 가 다음 시간으로 넘어간다 | 시간당 commitment 는 그 시간 안에서만 쓰이고 이월되지 않는다 |
| Spot 에 maximum price 를 지정해 비용과 안정성을 함께 잡는다 | maximum price 를 지정하면 지정하지 않을 때보다 중단이 잦아진다 |
| CLI 기본 allocation strategy 를 그대로 쓰면 균형 잡힌 선택이 된다 | CLI 기본값은 `lowest-price` 이고 중단 위험이 가장 높다. 권장은 `price-capacity-optimized` 다 |
| SP 커버리지가 낮은 계정에 커밋을 몰아주려고 sharing 을 끈다 | sharing 을 끄면 그 계정은 다른 계정의 커밋 혜택도 받지 못하고, SP 는 어차피 소유 계정 사용분에 먼저 적용된다 |
| 그룹 공유에서 payer 계정을 그룹에 넣어 우선순위를 준다 | payer 계정은 그룹에 들어갈 수 없고 계정은 그룹 하나에만 속한다 |
| 월말에 sharing 을 켜면 그달 전체가 소급 적용된다 | 최종 청구는 그 달 마지막 날 23:59:59 UTC 시점의 설정으로 계산된다 |
| management account 의 budget action 으로 초과한 member 계정의 EC2 인스턴스를 중지한다 | 다른 계정에는 SCP 만 적용할 수 있고 EC2 와 RDS 인스턴스 타깃은 불가능하다 |
| budget action 으로 SCP 를 걸면 이미 떠 있는 인스턴스가 멈춘다 | SCP 는 신규 API 호출을 막을 뿐이다. 실행 중 인스턴스 중지는 별도 action 이다 |
| member 계정이 management account 가 만든 자기 계정 budget 을 조회한다 | budget 은 만든 계정에 접근 권한이 있어야 보이고 cross-account 사용은 지원되지 않는다 |
| Cost Anomaly Detection 으로 AWS Marketplace 서드파티 구독의 급증을 잡는다 | AWS Marketplace의 제3자 제품과 서비스는 분석되지 않으며 Bedrock의 제3자 모델과 Bedrock Marketplace 모델도 포함된다. Billing entity 필터를 건 cost budget 이 답이다 |
| Cost Anomaly Detection 에 action 을 붙여 초과 시 리소스를 정지한다 | Anomaly Detection 에는 action 기능이 없고 알림만 보낸다 |
| Cost Explorer 에서 24개월 추세를 뽑아 연간 비교를 한다 | Cost Explorer 는 과거 13개월까지다 |
| Cost Explorer 를 잠시 켜서 비용을 확인한 뒤 다시 끈다 | 한 번 활성화하면 비활성화할 수 없다 |
| Cost Categories 규칙으로 인스턴스 ID 단위 비용을 쪼갠다 | 지원 dimension 에 resource ID 가 없다 |
| cost allocation tag 를 지금 활성화하면 지난달 리포트에도 값이 채워진다 | backfill 을 따로 요청해야 하고 최대 12개월 소급에 24시간당 1회이며, 그 기간에 리소스에 태그가 실제로 붙어 있던 구간만 값이 나온다 |
| CUR 을 실시간 대시보드 소스로 쓴다 | 하루 최대 3회 갱신이고 첫 배달까지 최대 24시간이 걸린다 |
| 지금 만든 CUR 2.0 export 로 지난 18개월을 소급해 분석한다 | export 는 생성 시점부터 데이터를 채운다 |
| 128 KB 미만 로그 객체를 lifecycle 로 Glacier Deep Archive 에 보내 저장비를 줄인다 | 2024년 9월 이후 기본 동작이 128 KB 미만 전환 차단이고, 전환 요청 비용이 절감을 넘어선다 |
| Deep Archive 에 잘못 보낸 객체를 lifecycle rule 로 Standard 로 되돌린다 | lifecycle 역방향 전환은 불가능하고 restore 후 copy 로 덮어써야 한다 |
| Archive Access 계층의 Intelligent-Tiering 객체를 lifecycle 로 Glacier Instant Retrieval 에 보낸다 | Archive Access 계층에서 갈 수 있는 곳은 GFR 과 GDA 뿐이고 Deep Archive Access 계층은 GDA 로만 간다 |
| Intelligent-Tiering 은 30일 최소 보관 기간이 있어 단명 객체에 불리하다 | 최소 보관 기간과 최소 과금 객체 크기가 없다. 불리한 쪽은 128 KB 미만 객체의 monitoring 요금과, 최소 보관 기간이 있는 Standard-IA 와 Glacier 계열이다 |
| Intelligent-Tiering 을 걸면 작은 로그 객체도 자동으로 아카이브된다 | 128 KB 미만 객체는 모니터링과 auto-tiering 대상이 아니어서 항상 Frequent Access 에 남는다 |
| `ListObjects` 로 목록을 훑었으니 객체가 Frequent Access 로 올라온다 | `HeadObject`, `GetObjectTagging`, `PutObjectTagging`, `ListObjects` 계열은 접근으로 인정되지 않는다 |
| 최소 보관 기간 전에 지워도 스토리지 요금만 일할로 끊긴다 | 남은 기간분이 prorated early deletion fee 로 청구된다 |
| lifecycle 전환을 막으려면 rule 을 비활성화하면 된다 | 정책 변경 전파에 최대 15분이 걸린다. 태그 기반 rule 이면 트리거 태그를 제거하는 쪽이 확실하다 |
| Glacier Deep Archive 객체를 restore 하면 storage class 가 Standard 로 돌아온다 | restore 는 임시 사본만 만들고 `HeadObject` 는 계속 Deep Archive 를 반환한다 |
| Intelligent-Tiering Archive Access 에서 restore 한 객체는 다시 90일을 기다려야 Frequent Access 로 올라온다 | restore 즉시 Frequent Access 로 되돌아가고 그 뒤 미접근 30일에 Infrequent Access 로 내려간다 |
| Requester Pays 를 켜면 저장 비용도 요청자가 낸다 | 저장 비용은 항상 소유자가 낸다 |
| Requester Pays 버킷이면 아카이브 객체의 retrieval 비용도 요청자 부담이다 | `RestoreObject` 는 요청자가 request 비용만 내고 retrieval 비용은 소유자가 낸다 |
| Storage Lens free 계층으로 prefix 별 미접근 데이터를 찾는다 | activity metrics 와 prefix aggregation 은 advanced 계층에만 있다 |
| Trusted Advisor 에서 서비스 한도를 올린다 | 조회만 한다. 증설은 Service Quotas 나 Support case 다 |
| Basic support 계정에서 Trusted Advisor cost optimization check 로 미사용 EBS 를 찾는다 | Basic 은 Service Limits 전체와 Security, Fault tolerance 일부만 열린다 |
| Compute Optimizer 를 켜면 메모리 기준 rightsizing 권고가 자동으로 나온다 | CloudWatch agent 나 지원되는 외부 관측 도구가 없으면 메모리 지표가 수집되지 않는다 |
| CloudWatch agent 를 깔았으니 네임스페이스 구성과 무관하게 메모리가 반영된다 | 네임스페이스에 `InstanceId` dimension 이 없으면 수집되지 않는다 |
| Compute Optimizer 만 켜면 예상 절감액이 표시된다 | 절감액 계산에는 Cost Explorer 활성화가 필요하고, RI 와 SP 가격 반영에는 Cost Optimization Hub opt-in 이 필요하다 |
| Cost Explorer rightsizing 이 Compute Optimizer 보다 넓은 권고를 준다 | EC2 한정에 추정 절감액 $0 이상만 제시하는 부분집합이다 |
| gateway endpoint 를 만들어 KMS 나 ECR 호출의 NAT 비용을 없앤다 | gateway endpoint 는 S3 와 DynamoDB 만 지원한다 |
| 다른 리전의 S3 버킷 접근도 gateway endpoint 로 태운다 | gateway endpoint의 리전별 prefix list에는 매칭되지 않는다. S3 cross-Region interface endpoint 같은 별도 경로를 지원 조건에 따라 검토하고, 그 경로가 없으면 route table의 0.0.0.0/0 대상에 따라 NAT, internet gateway 또는 Transit Gateway로 나간다 |
| NAT Gateway 를 AZ 하나에 통합해 시간당 요금을 줄인다 | 처리 GB 요금은 그대로이고 다른 AZ 트래픽이 AZ 를 넘으면서 교차 AZ 전송 요금이 붙는다 |
| CloudFront 를 붙이면 origin 에서 CloudFront 로 가는 전송에도 요금이 붙는다 | CloudFront 와 AWS origin 사이의 전송은 면제된다 |
| 인터넷 무료 100 GB 는 서비스마다 따로 적용된다 | 모든 AWS 서비스와 리전을 합산해 월 100 GB 다 |

---

## 26. 예상 문제 10문항

**Q1.** 향후 3년간 EC2 사용량이 안정적으로 유지되고, 동시에 Fargate 와 Lambda 사용이 빠르게 늘고 있습니다. 워크로드 개편으로 EC2 instance family 는 약 6개월마다 바뀔 전망이며 리전도 한 곳이 추가될 수 있습니다. 재구매나 교환 절차 없이 커버리지를 유지해야 합니다. 기존 약정은 이번 달에 만료됩니다. MOST appropriate 구매 옵션은 무엇입니까?

- A. Compute Savings Plans 를 3년 약정으로 구매한다
- B. EC2 Instance Savings Plans 를 현재 주력 family 에 3년 약정으로 구매한다
- C. Standard Reserved Instances 를 3년 약정으로 구매한다
- D. Convertible Reserved Instances 를 3년 약정으로 구매하고 필요할 때 exchange 한다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: A**

Compute Savings Plans 는 instance family, size, Region, OS, tenancy 와 무관하게 EC2 에 적용되고 Fargate 와 Lambda 사용분도 커버합니다. family 가 바뀌고 리전이 추가되어도 교환 절차 없이 커밋이 그대로 적용되므로 세 제약을 모두 만족합니다. 최대 할인율이 66퍼센트로 EC2 Instance SP 보다 낮다는 것이 대가입니다.

- B가 틀린 이유: EC2 Instance SP 는 특정 Region 의 특정 instance family 에 commit 한다. family 가 바뀌거나 리전이 추가되면 커버리지가 깨지고 SP 는 기간 중 취소할 수 없다.
- C가 틀린 이유: Standard RI 는 exchange 가 불가능하고 Fargate 와 Lambda 를 커버하지 않는다. 출구는 Marketplace 매각뿐이다.
- D가 틀린 이유: Convertible RI 는 exchange 가 가능하지만 그 절차 자체가 요구에서 제외됐고, Fargate 와 Lambda 사용분도 커버하지 않는다.

</details>

**Q2.** 분기 마감마다 3일 동안 특정 AZ 에서 대량의 EC2 용량이 반드시 확보되어야 합니다. 나머지 기간에는 기본 부하만 돌아갑니다. 마감 작업은 중단되면 재실행 비용이 큽니다. 마감 부하는 특정 instance family 에 고정되어 있고 나머지 기간의 기본 부하는 연중 일정합니다. 사용하지 않은 예약에 대한 과금은 감수할 수 있습니다. 용량 확보와 할인을 동시에 얻는 MOST appropriate 구성은 무엇입니까?

- A. 해당 AZ 에 On-Demand Capacity Reservation 을 만들고, 기본 부하와 마감 부하 모두에 Compute Savings Plans 를 적용한다
- B. Savings Plans 커밋을 늘려 마감 기간의 용량을 확보한다
- C. Regional Reserved Instances 를 구매해 해당 리전의 용량을 예약한다
- D. Spot Fleet 을 `price-capacity-optimized` 전략으로 구성해 마감 작업을 처리한다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: A**

On-Demand Capacity Reservation 은 지정한 AZ 에 용량을 확보하며 즉시 사용형은 term commitment 없이 언제든 취소할 수 있습니다. 다만 그 자체로는 billing discount 가 없으므로 Savings Plans 나 Regional RI 와 결합해야 할인이 적용됩니다. 용량과 할인이 서로 다른 메커니즘이라는 점이 이 문항의 핵심입니다.

- B가 틀린 이유: Savings Plans 는 capacity reservation 을 제공하지 않는다. 커밋을 늘려도 용량이 확보되지 않는다.
- C가 틀린 이유: Regional RI 는 용량을 예약하지 않는다. 용량을 예약하는 것은 Zonal RI 와 Capacity Reservation 이다.
- D가 틀린 이유: Spot 인스턴스는 capacity 회수로 중단될 수 있고 중단 통지는 2분 전 best effort 다. 중단 시 재실행 비용이 큰 마감 작업에 맞지 않는다.

</details>

**Q3.** management account 의 FinOps 팀이 개발 OU 의 월 예산 초과에 자동으로 대응하려 합니다. 요구는 두 가지입니다. 초과 시 새 리소스 생성을 즉시 막고, 이미 실행 중인 개발용 EC2 인스턴스도 중지해야 합니다. AWS Budgets 의 budget action 을 쓰려 합니다. 개발 OU 에는 12개 member 계정이 있습니다. MOST appropriate 구성은 무엇입니까?

- A. budget action 으로 개발 OU 에 SCP 를 적용해 신규 생성을 막고, member 계정 안에서 EventBridge 와 SSM Automation 으로 인스턴스 중지를 실행한다
- B. budget action 두 개를 만들어 하나는 OU 에 SCP 를 적용하고 다른 하나는 member 계정의 EC2 인스턴스를 중지한다
- C. budget action 으로 SCP 만 적용한다. SCP 가 적용되면 실행 중인 인스턴스도 함께 중지된다
- D. Cost Anomaly Detection monitor 에 budget action 을 연결해 두 동작을 한 번에 수행한다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: A**

budget action 유형은 IAM policy 적용, OU 에 SCP 적용, EC2 또는 RDS 인스턴스 중지 셋입니다. management account 에서 다른 계정에 SCP 를 적용할 수는 있지만 다른 계정의 EC2 나 RDS 인스턴스를 타깃할 수는 없습니다. 따라서 인스턴스 중지는 member 계정 안에서 별도 자동화로 처리해야 합니다.

- B가 틀린 이유: budget action 의 EC2 및 RDS 중지 대상은 budget 이 정의된 계정의 리소스다. management account 에서 member 계정의 인스턴스를 타깃할 수 없다.
- C가 틀린 이유: SCP 는 신규 API 호출을 차단할 뿐 이미 실행 중인 리소스를 중지하지 않는다.
- D가 틀린 이유: Cost Anomaly Detection 에는 action 기능이 없다. 알림만 보낸다.

</details>

**Q4.** 지난달 AWS Marketplace 서드파티 소프트웨어 구독 요금이 평소의 3배로 뛰었는데 이미 구성해 둔 AWS Cost Anomaly Detection monitor 가 아무 알림도 보내지 않았습니다. 재무팀은 같은 유형의 급증을 다음 달부터 자동으로 통보받기를 원합니다. 알림 수신자와 임계값은 이미 정해져 있고 계정 구조는 바뀌지 않습니다. MOST appropriate 조치는 무엇입니까?

- A. Billing entity 를 필터로 지정한 cost budget 과 알림 임계값을 만든다
- B. Cost Anomaly Detection monitor 를 삭제하고 서비스 단위 monitor 로 다시 만든다
- C. Cost Explorer 에서 Marketplace 비용 리포트를 매일 확인하는 절차를 만든다
- D. CUR 을 Athena 로 매일 쿼리하는 스케줄 작업을 만들어 임계 초과 시 SNS 로 보낸다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: A**

Cost Anomaly Detection 은 AWS Marketplace 의 제3자 제품과 서비스를 분석 대상에서 제외하며 Amazon Bedrock 의 제3자 모델과 Bedrock Marketplace 모델도 포함합니다. 따라서 monitor 를 어떻게 구성해도 이 급증은 잡히지 않고, Billing entity 차원을 필터로 건 cost budget 과 알림이 남는 경로입니다.

- B가 틀린 이유: monitor 유형이 문제가 아니라 Marketplace 자체가 미지원 대상이다. 재생성해도 결과가 같다.
- C가 틀린 이유: 사람이 매일 확인하는 절차라 자동 통보 요구를 만족시키지 못하고 누락 위험이 크다.
- D가 틀린 이유: 동작은 하지만 쿼리와 알림 로직을 직접 만들고 유지해야 한다. 또 CUR 은 하루 최대 3회 갱신에 첫 배달까지 최대 24시간이 걸려 관리형 budget 알림보다 반응이 늦다.

</details>

**Q5.** 재무팀이 특정 EC2 인스턴스 ID 단위로 지난 18개월의 시간별 비용 추이를 SQL 로 분석해야 합니다. 회사는 2년 전부터 시간 단위 집계와 resource ID 포함 옵션을 켠 Cost and Usage Report 를 자체 S3 버킷으로 받아 왔고 그 파일이 전부 남아 있습니다. 팀은 새 ETL 파이프라인을 만들 여력이 없고 Cost Explorer 콘솔로는 인스턴스 단위 시간별 데이터를 얻지 못했습니다. 추가 개발을 최소화하면서 요구를 만족시키는 MOST appropriate 접근은 무엇입니까?

- A. S3 에 이미 쌓인 CUR 파일에 AWS Glue Data Catalog 테이블을 정의하고 Amazon Athena 로 쿼리한다
- B. Cost Explorer API 를 호출해 인스턴스 단위 시간별 비용을 가져온다
- C. Cost Categories 규칙으로 인스턴스별 카테고리를 만들고 Cost Explorer 에서 조회한다
- D. 지금 Data Exports 로 CUR 2.0 export 를 새로 만들고 그 결과를 Athena 로 쿼리한다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: A**

라인 아이템과 resource ID 수준의 조사는 CUR 의 영역이고, 요구된 18개월치가 이미 S3 에 시간 단위로 쌓여 있습니다. 빠진 것은 데이터가 아니라 쿼리 계층뿐이며 Glue 테이블 정의와 Athena 연결만으로 요구가 충족됩니다.

- B가 틀린 이유: Cost Explorer 는 과거 13개월 데이터만 보여준다. 18개월 요구를 만족시키지 못하고 API 는 paginated 요청당 0.01 USD 가 붙는다.
- C가 틀린 이유: Cost Categories 가 지원하는 dimension 은 Account, Charge type, Cost category, Region, Service, Tag key, Usage Type, Billing Entity 다. 리소스 ID 가 없으므로 인스턴스 단위로 쪼갤 수 없다.
- D가 틀린 이유: CUR 2.0 은 신규 export 의 권장 경로이지만 export 는 생성 시점부터 데이터를 채운다. 이미 확보된 데이터를 두고 새 파이프라인을 세우는 셈이 된다.

</details>

**Q6.** 태깅 정책 도입 전에 만들어진 리소스가 전체의 40퍼센트이고 이들에는 팀 태그가 없습니다. 재무팀은 이번 달 청구서부터 소급 적용된 팀별 비용 배분 리포트를 요구하고, 대상 계정은 30개이며, 리소스를 다시 태깅할 인력은 확보되지 않았습니다. 태그 없는 리소스도 계정과 서비스와 사용 유형 조합으로 소유 팀을 특정할 수 있습니다. MOST appropriate 접근은 무엇입니까?

- A. AWS Cost Categories 로 계정, 서비스, 사용 유형 기준 규칙을 만들어 팀에 매핑한다
- B. 누락된 리소스에 대해 user-defined cost allocation tag 를 활성화하고 리포트를 다시 생성한다
- C. Tag Editor 로 전체 리소스를 일괄 태깅한 뒤 cost allocation tag 를 활성화한다
- D. 팀별로 AWS 계정을 새로 만들고 워크로드를 옮겨 계정 단위로 비용을 구분한다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: A**

Cost Categories 는 라인 아이템에 규칙으로 key-value 를 붙이므로 태깅되지 않은 리소스도 계정, 서비스, 사용 유형 같은 dimension 으로 묶을 수 있습니다. 월 중간에 만들거나 수정해도 당월 1일부터 소급 적용되고 처리에 최대 24시간이 걸립니다. 이번 달 청구서부터 배분하라는 요구에 맞습니다.

- B가 틀린 이유: cost allocation tag 는 리소스에 태그가 붙어 있어야 배분된다. 태그가 없는 라인 아이템은 활성화만으로 배분되지 않는다.
- C가 틀린 이유: 인력 제약과 충돌하고, 태그 활성화 후 리포트 반영까지 최대 24시간이 걸리며 이미 발생한 라인 아이템에는 당월 배분이 보장되지 않는다.
- D가 틀린 이유: 워크로드 이전은 대규모 프로젝트라 이번 달 청구서 요구를 만족시킬 수 없다.

</details>

**Q7.** 애플리케이션이 하루 2천만 개의 로그 객체를 S3 Standard 에 씁니다. 객체 평균 크기는 40 KB 입니다. 팀이 4일 뒤 S3 Glacier Instant Retrieval 로, 20일 뒤 S3 Glacier Deep Archive 로 보내는 lifecycle 규칙을 만들었는데 전환이 일어나지 않고 규칙 생성 단계에서도 오류가 났습니다. MOST appropriate 진단과 조치는 무엇입니까?

- A. 128 KB 미만 객체는 기본적으로 전환되지 않고 Glacier Instant Retrieval 의 최소 보관 기간 90일 때문에 20일 뒤 Deep Archive 전환 규칙도 만들 수 없다. 로그를 더 큰 객체로 묶고 전환 일수를 최소 보관 기간에 맞춘다
- B. `x-amz-transition-default-minimum-object-size` 헤더로 최소 크기 기준을 낮추면 현재 규칙이 그대로 동작한다
- C. 두 전환을 하나로 합쳐 4일 뒤 바로 Glacier Deep Archive 로 보낸다
- D. lifecycle 대신 S3 Intelligent-Tiering 을 적용해 자동으로 아카이브 계층으로 내린다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: A**

2024년 9월부터 lifecycle 기본 동작은 128 KB 미만 객체를 어떤 클래스로도 전환하지 않는 것입니다. 또 최소 보관 기간을 위반하는 전환은 단일 lifecycle rule 로 표현할 수 없습니다. Glacier Instant Retrieval 의 최소 보관 기간이 90일이므로 4일과 20일 조합은 규칙 자체가 성립하지 않습니다.

- B가 틀린 이유: 헤더로 최소 크기 제약은 풀 수 있지만 Glacier Instant Retrieval 의 90일 최소 보관 기간 위반 문제는 그대로다. 게다가 40 KB 객체 2천만 개의 전환 요청 비용이 저장 비용 절감을 넘어선다.
- C가 틀린 이유: 128 KB 미만 전환 차단이 그대로 적용된다. Deep Archive 는 최소 보관 180일에 객체당 40 KB 메타데이터 오버헤드가 붙어 40 KB 로그 객체에서는 단가 이점이 사라진다.
- D가 틀린 이유: Intelligent-Tiering 은 128 KB 미만 객체를 모니터링하지 않고 auto-tiering 대상에서 제외해 항상 Frequent Access 에 둔다. 객체당 monitoring 요금만 늘어난다.

</details>

**Q8.** 데이터 레이크 버킷에 평균 8 MB 객체가 쌓입니다. 접근 패턴은 예측할 수 없고, 수개월 동안 조회되지 않던 객체가 규제 조사로 갑자기 대량 조회되는 사례가 있습니다. 팀은 조기 삭제 수수료와 검색 요금 노출을 피하면서 저장 비용을 낮추려 합니다. 객체는 삭제 없이 최소 5년간 보관되고 조회 시 밀리초 단위 응답이 필요합니다. MOST cost-effective 선택은 무엇입니까?

- A. S3 Intelligent-Tiering 을 적용한다
- B. lifecycle 로 30일 뒤 S3 Standard-IA, 90일 뒤 S3 Glacier Flexible Retrieval 로 전환한다
- C. lifecycle 로 30일 뒤 S3 One Zone-IA 로 전환한다
- D. lifecycle 로 30일 뒤 S3 Glacier Deep Archive 로 전환한다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: A**

Intelligent-Tiering 은 최소 보관 기간과 최소 과금 객체 크기가 없고 retrieval fee 도 없습니다. 접근이 없으면 30일 뒤 Infrequent Access, 90일 뒤 Archive Instant Access 로 자동으로 내려가고 접근이 발생하면 Frequent Access 로 되돌아옵니다. 8 MB 객체는 128 KB 기준을 넘으므로 auto-tiering 대상이며 객체당 monitoring 요금 부담도 상대적으로 작습니다.

- B가 틀린 이유: Standard-IA 는 최소 보관 30일, Glacier Flexible Retrieval 은 최소 보관 90일과 retrieval fee 가 있다. 갑작스러운 대량 조회에서 검색 요금과 복원 지연이 발생해 제약과 충돌한다.
- C가 틀린 이유: One Zone-IA 는 단일 AZ 에 저장해 설계 가용성이 99.5퍼센트로 낮고 최소 보관 30일과 retrieval fee 가 있다.
- D가 틀린 이유: Deep Archive 는 최소 보관 180일이고 복원에 시간이 걸린다. 규제 조사에 즉시 응답해야 하는 상황과 맞지 않는다.

</details>

**Q9.** private subnet 의 ECS 태스크가 하루 40 TB 를 S3 에 쓰고, 배포마다 ECR 에서 이미지를 pull 하며 실행 중 Secrets Manager 를 호출합니다. 이 트래픽이 전부 NAT Gateway 를 통과해 데이터 처리 요금이 청구서 상위 항목이 됐습니다. 애플리케이션은 수정할 수 없습니다. MOST cost-effective 조치는 무엇입니까?

- A. S3 에는 gateway endpoint 를 만들고 ECR 과 Secrets Manager 에는 interface endpoint 를 만든다
- B. S3, ECR, Secrets Manager 모두에 interface endpoint 를 만든다
- C. NAT Gateway 를 여러 AZ 에서 한 AZ 로 통합해 시간당 요금을 줄인다
- D. NAT Gateway 를 자체 관리 NAT instance 로 교체한다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: A**

gateway endpoint 는 S3 와 DynamoDB 만 지원하지만 추가 요금이 없습니다. 하루 40 TB 가 이동하는 S3 트래픽을 NAT Gateway 처리 요금에서 완전히 빼내는 효과가 가장 큽니다. ECR 과 Secrets Manager 는 gateway endpoint 대상이 아니므로 interface endpoint 로 처리하며, 이 경우에도 NAT 처리 요금 대신 상대적으로 낮은 endpoint 처리 요금이 적용됩니다.

- B가 틀린 이유: interface endpoint 는 AZ 당 시간 요금과 처리 GB 당 요금이 붙는다. 40 TB 규모에서는 요금이 없는 gateway endpoint 를 두고 굳이 유료 경로를 선택하는 셈이다.
- C가 틀린 이유: NAT Gateway 시간당 요금은 줄지만 처리 GB 당 요금은 그대로이고, 다른 AZ 의 태스크 트래픽이 AZ 를 넘으면서 교차 AZ 데이터 전송 비용이 추가된다. AWS 문서 권고는 오히려 AZ 마다 NAT gateway 를 두거나 리소스를 같은 AZ 에 배치하는 것이다.
- D가 틀린 이유: 패치와 가용성 구성을 직접 떠안게 되고 인스턴스 대역폭이 병목이 된다. 하루 40 TB 규모에서 운영 위험이 크다.

</details>

**Q10.** 회사가 EC2 rightsizing 을 시작하려고 AWS Compute Optimizer 를 활성화했습니다. 그런데 권고에 메모리 기준이 반영되지 않고, 예상 절감액이 표시되지 않으며, 이미 보유한 Reserved Instances 와 Savings Plans 조건도 반영되지 않습니다. 대상 인스턴스는 전부 Amazon Linux 입니다. 세 문제를 해결하기 위해 필요한 조치 3개는 무엇입니까? (3개를 고르시오.)

- A. 대상 인스턴스에 CloudWatch agent 를 배포해 `CWAgent` 네임스페이스의 `mem_used_percent` 를 `InstanceId` dimension 과 함께 발행한다
- B. AWS Cost Explorer 를 활성화한다
- C. Cost Optimization Hub 에 opt-in 한다
- D. enhanced infrastructure metrics 를 활성화해 lookback 기간을 93일로 늘린다
- E. Business Support+ 플랜으로 올려 Trusted Advisor 전체 check 를 연다
- F. S3 Storage Lens advanced 계층을 활성화한다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: A, B, C**

메모리 사용률은 CloudWatch agent 가 있어야 수집되며, Linux 에서는 `CWAgent` 네임스페이스의 `mem_used_percent` 를 사용하고 `InstanceId` dimension 이 없으면 수집되지 않습니다. Compute Optimizer 가 절감액을 계산하려면 Cost Explorer 가 활성화되어 있어야 하고, RI 와 SP 가격을 반영한 권고를 받으려면 Cost Optimization Hub opt-in 이 필요합니다. 세 증상이 각각 다른 전제 조건에 대응합니다.

- D가 틀린 이유: enhanced infrastructure metrics 는 분석 lookback 을 14일에서 93일로 늘리는 유료 기능이다. 메모리 지표 수집이나 가격 반영과 무관하다.
- E가 틀린 이유: Trusted Advisor 는 별개의 권고 도구다. 플랜을 올려도 Compute Optimizer 의 메모리 지표나 절감액 계산이 달라지지 않는다.
- F가 틀린 이유: S3 Storage Lens 는 S3 스토리지 사용과 활동 지표를 다룬다. EC2 rightsizing 과 관련이 없다.

</details>

---

## 27. Reference

- [AWS Savings Plans - What are Savings Plans?](https://docs.aws.amazon.com/savingsplans/latest/userguide/what-is-savings-plans.html)
- [AWS Savings Plans - Plan types](https://docs.aws.amazon.com/savingsplans/latest/userguide/plan-types.html)
- [AWS Savings Plans - How Savings Plans apply to your AWS usage](https://docs.aws.amazon.com/savingsplans/latest/userguide/sp-applying.html)
- [AWS Savings Plans - Savings Plans compared to Reserved Instances](https://docs.aws.amazon.com/savingsplans/latest/userguide/sp-ris.html)
- [AWS Savings Plans - Understanding Savings Plans recommendations](https://docs.aws.amazon.com/savingsplans/latest/userguide/sp-recommendations.html)
- [Amazon EC2 - Reserved Instances](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-reserved-instances.html)
- [Amazon EC2 - Types of Reserved Instances](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/reserved-instances-types.html)
- [Amazon EC2 - Scope of Reserved Instances](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/reserved-instances-scope.html)
- [Amazon EC2 - On-Demand Capacity Reservations](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-capacity-reservations.html)
- [Amazon EC2 - Capacity Reservations in placement groups](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/cr-cpg.html)
- [Amazon EC2 - Spot Instance interruptions](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/spot-interruptions.html)
- [Amazon EC2 - Spot Instance interruption notices](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/spot-instance-termination-notices.html)
- [Amazon EC2 - Allocation strategies for Spot Instances](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-fleet-allocation-strategy.html)
- [Amazon S3 - Understanding and managing Amazon S3 storage classes](https://docs.aws.amazon.com/AmazonS3/latest/userguide/storage-class-intro.html)
- [Amazon S3 - What is S3 Intelligent-Tiering?](https://docs.aws.amazon.com/AmazonS3/latest/userguide/intelligent-tiering-overview.html)
- [Amazon S3 - Managing S3 Intelligent-Tiering](https://docs.aws.amazon.com/AmazonS3/latest/userguide/intelligent-tiering-managing.html)
- [Amazon S3 - Supported lifecycle transitions and related constraints](https://docs.aws.amazon.com/AmazonS3/latest/userguide/lifecycle-transition-general-considerations.html)
- [Amazon S3 - Using Requester Pays buckets](https://docs.aws.amazon.com/AmazonS3/latest/userguide/RequesterPaysBuckets.html)
- [Amazon S3 - Assessing storage activity and usage with S3 Storage Lens](https://docs.aws.amazon.com/AmazonS3/latest/userguide/storage_lens.html)
- [Amazon S3 - S3 Storage Lens metrics glossary](https://docs.aws.amazon.com/AmazonS3/latest/userguide/storage_lens_basics_metrics_recommendations.html)
- [AWS Billing - What is AWS Cost Explorer?](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/ce-what-is.html)
- [AWS Billing - Using AWS cost allocation tags](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/cost-alloc-tags.html)
- [AWS Billing - Backfilling cost allocation tags](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/cost-allocation-backfill.html)
- [AWS Billing - Managing your costs with AWS Cost Categories](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/manage-cost-categories.html)
- [AWS Billing - Managing your costs with AWS Budgets](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/budgets-managing-costs.html)
- [AWS Billing - Configuring AWS Budgets actions](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/budgets-controls.html)
- [AWS Billing - Billing and Cost Management quotas and restrictions](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/billing-limits.html)
- [AWS Billing - Turning off shared reserved instances and Savings Plans discounts](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/ri-turn-off.html)
- [AWS Cost Management - Detecting unusual spend with AWS Cost Anomaly Detection](https://docs.aws.amazon.com/cost-management/latest/userguide/manage-ad.html)
- [AWS Cost Management - Quotas and restrictions](https://docs.aws.amazon.com/cost-management/latest/userguide/management-limits.html)
- [AWS Cost Management - Rightsizing recommendations](https://docs.aws.amazon.com/cost-management/latest/userguide/ce-rightsizing.html)
- [AWS Cost Management - Understanding rightsizing recommendation calculations](https://docs.aws.amazon.com/cost-management/latest/userguide/understanding-rr-calc.html)
- [AWS Cost Management - Cost Optimization Hub](https://docs.aws.amazon.com/cost-management/latest/userguide/cost-optimization-hub.html)
- [AWS Data Exports - What is AWS Cost and Usage Report?](https://docs.aws.amazon.com/cur/latest/userguide/what-is-cur.html)
- [AWS Data Exports - What is AWS Data Exports?](https://docs.aws.amazon.com/cur/latest/userguide/what-is-data-exports.html)
- [AWS Compute Optimizer - What is AWS Compute Optimizer?](https://docs.aws.amazon.com/compute-optimizer/latest/ug/what-is-compute-optimizer.html)
- [AWS Compute Optimizer - Requirements](https://docs.aws.amazon.com/compute-optimizer/latest/ug/requirements.html)
- [AWS Compute Optimizer - Metrics analyzed](https://docs.aws.amazon.com/compute-optimizer/latest/ug/metrics.html)
- [AWS Compute Optimizer - Amazon EC2 metrics analyzed](https://docs.aws.amazon.com/compute-optimizer/latest/ug/ec2-metrics-analyzed.html)
- [AWS Support - AWS Trusted Advisor](https://docs.aws.amazon.com/awssupport/latest/user/trusted-advisor.html)
- [AWS Support - Compare AWS Support plans](https://docs.aws.amazon.com/awssupport/latest/user/aws-support-plans.html)
- [Amazon VPC - NAT gateways](https://docs.aws.amazon.com/vpc/latest/userguide/vpc-nat-gateway.html)
- [Amazon VPC - NAT gateway pricing and billing](https://docs.aws.amazon.com/vpc/latest/userguide/nat-gateway-pricing.html)
- [AWS PrivateLink - Gateway endpoints](https://docs.aws.amazon.com/vpc/latest/privatelink/gateway-endpoints.html)
- [AWS PrivateLink - Access an AWS service using an interface VPC endpoint](https://docs.aws.amazon.com/vpc/latest/privatelink/privatelink-access-aws-services.html)
- [AWS PrivateLink - AWS services that support cross-Region access](https://docs.aws.amazon.com/vpc/latest/privatelink/aws-services-cross-region-privatelink-support.html)
- [Amazon DynamoDB - Accessing DynamoDB from another Region using interface endpoints](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/privatelink-interface-endpoints.html)
- [AWS Well-Architected Framework - Cost Optimization Pillar](https://docs.aws.amazon.com/wellarchitected/latest/cost-optimization-pillar/welcome.html)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
