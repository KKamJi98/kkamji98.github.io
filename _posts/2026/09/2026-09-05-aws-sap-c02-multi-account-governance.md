---
title: "AWS SAP-C02 박살내기 - 멀티 계정 거버넌스: Organizations, SCP, Control Tower, IAM Identity Center"
date: 2026-09-05 21:30:00 +0900
author: kkamji
categories: [Certification, AWS SAP-C02]
tags: [aws, sap-c02, certification, organizations, scp, control-tower, iam-identity-center, ram, governance]
comments: true
image:
  path: /assets/img/aws/aws.webp
---

계정이 100개인 조직에서 개발팀이 승인되지 않은 리전에 리소스를 만드는 일이 반복된다고 해보겠습니다. 가장 먼저 떠오르는 조치는 조직 root에 리전을 제한하는 Service Control Policy를 붙이는 것입니다. 그런데 같은 조치가 조건에 따라 세 갈래로 갈립니다.

조직이 consolidated billing features 모드라면 SCP 메뉴 자체가 없습니다. all features 모드라 해도 Deny 문만 남기고 자동 부착된 `FullAWSAccess`를 떼어내면 그 아래 모든 계정이 전 서비스에서 차단됩니다. 정확히 붙였다 해도 management account의 관리자는 여전히 아무 리전에나 리소스를 만들 수 있습니다. SCP가 management account의 사용자와 역할에 적용되지 않기 때문입니다.

SAP-C02의 Domain 1은 이런 판단을 26% 비중으로 묻습니다. 계정 경계를 어디에 그을 것인가, 그 경계 위에서 권한 차단과 로그 집계와 비용 배분이 각각 어떤 정책 타입으로 강제되는가가 문항의 축입니다. 서비스 이름을 아는 것으로는 선지가 좁혀지지 않고, 각 정책 타입이 통제하지 **못하는** 대상을 알아야 답이 갈립니다.

> **TL;DR**  
> - SCP는 권한을 부여하지 않는다. 유효 권한은 SCP와 RCP가 허용하는 것과 identity 및 resource policy가 허용하는 것의 교집합이다.  
> - SCP는 management account의 사용자와 역할에 적용되지 않는다. delegated administrator로 지정된 멤버 계정에는 그대로 적용된다.  
> - SCP와 RCP는 service-linked role을 통제하지 못한다. SLR까지 통제하는 정책 타입은 declarative policy 하나다.  
> - SCP는 조직 안 principal을, RCP는 조직 계정이 소유한 리소스를 막는다. 방향이 반대다.  
> - Allow는 root부터 계정까지 모든 레벨에 있어야 통과하고, Deny는 어느 한 레벨만 있어도 차단된다.  
> - Control Tower의 behavior(preventive/detective/proactive)와 guidance(mandatory/strongly recommended/elective)는 독립된 두 축이다. Landing Zone 4.0부터 mandatory control이 기본 적용되지 않는다.  
> - RAM에서 subnet과 security group은 같은 조직 안으로만 공유되고, transit gateway와 prefix list는 조직 밖 계정과도 공유된다.  
> - consolidated billing features에서 all features로 가는 전환은 단방향이다.  
{: .prompt-info}

---

## 1. root와 management account와 member account가 각각 무엇인가

AWS Organizations는 여러 AWS 계정을 하나의 트리로 묶어 정책과 결제를 중앙에서 관리하는 서비스입니다. 트리의 최상단은 root이고, root 아래에 Organizational Unit(OU)이 놓이며, OU 안에 계정이 들어갑니다. 계정을 OU에 넣지 않고 root 바로 아래에 둘 수도 있습니다.

용어 세 개를 정확히 구분해야 합니다.

| 구성 요소 | 정의 | 시험에서 갈리는 지점 |
| :--- | :--- | :--- |
| root | 조직의 모든 OU와 계정을 담는 최상위 컨테이너. 조직당 1개 | OU가 아니다. 삭제할 수 없고 Control Tower가 Root 레벨에서 enrolled 계정을 governance하지 않는다 |
| management account | 조직을 만든 계정. 정책 부착, 계정 생성과 초대, 통합 결제의 payer | SCP와 RCP가 이 계정의 principal에 적용되지 않는다 |
| member account | 조직에 속한 나머지 계정 | delegated administrator로 지정되어도 SCP 적용 대상이다 |

![Root에서 Security OU와 Workloads OU를 거쳐 계정까지 SCP가 상속되고 management account만 적용 대상에서 빠지는 구조](/assets/img/sap-c02/organizations-scp-hierarchy.webp)

그림 가운데 위의 Root에서 아래로 갈라지는 두 선이 OU 계층입니다. Root에서 Security OU와 Workloads OU로 내려가고, Security OU에서 다시 Audit 계정과 Log archive 계정으로, Workloads OU에서 Prod 계정으로 이어집니다. 파란색으로 표시된 Root와 두 OU가 SCP 부착 지점이고, 초록색 계정 박스는 부착 지점이면서 동시에 위에서 내려온 정책을 상속받는 쪽입니다. 계정 하나의 유효 SCP는 그 계정에 직접 붙은 것뿐 아니라 Root부터 그 계정까지 경로에 있는 모든 엔티티의 SCP를 교집합으로 합친 결과입니다. Prod 계정 아래에 적힌 대로 멤버 계정에서는 root user까지 SCP를 받습니다. 왼쪽으로 빠지는 점선 화살표가 가리키는 회색 상자가 management account입니다. 점선인 이유는 정책 부착 자체는 가능하지만 그 계정의 사용자와 역할에는 효력이 없기 때문입니다.

조직 트리의 하드 리밋은 다음과 같습니다.

- root는 조직당 1개, OU는 조직당 2,000개다
- OU 중첩은 root 아래 5단계까지다
- 조직당 기본 계정 수 상한은 10개다. Service Quotas로 증액하며 고객 자격에 따라 최대 50,000까지 승인된다. 증액 요청은 management account만 제출할 수 있다
- 보낸 초대도 계정 쿼터를 소모한다. 거절, 취소, 만료되면 반환되고, 닫은 계정은 영구 종료 전까지 계속 소모한다
- Organizations는 글로벌 서비스이고 물리적으로 us-east-1에 호스팅된다. Service Quotas 콘솔이나 CLI로 쿼터를 다룰 때 us-east-1을 지정해야 한다

계정 수 상한이 기본 10이라는 점은 실무에서 자주 걸립니다. Control Tower를 기존 조직에 도입할 때 Audit 계정과 Log archive 계정 두 개가 새로 만들어지므로, 최소 두 계정을 더 만들 수 있는 여유가 필요합니다.

---

## 2. feature mode 두 가지와 되돌릴 수 없는 전환

Organizations의 feature set은 all features와 consolidated billing features 두 가지입니다. 조직을 새로 만들면 all features가 기본값입니다.

| 구분 | consolidated billing features | all features |
| :--- | :--- | :--- |
| 통합 결제 | 지원 | 지원 |
| SCP, RCP | 사용 불가 | 사용 가능 |
| tag policy, backup policy, AI services opt-out policy | 사용 불가 | 사용 가능 |
| declarative policy | 사용 불가 | 사용 가능 |
| 전환 방향 | all features로 이동 가능 | consolidated billing으로 되돌릴 수 없다 |

시험에서 가장 자주 나오는 지점은 전환의 비대칭입니다. consolidated billing features에서 all features로 가는 이동은 가능하지만 반대 방향은 없습니다. "정책 통제를 도입했다가 문제가 생기면 원래대로 돌린다"는 요구 조건이 지문에 들어 있으면 all features 전환은 답이 될 수 없습니다.

전환 절차 자체에도 제약이 있습니다.

- 초대로 들어온 계정은 **전원이** all features 활성화 요청을 수락해야 전환이 완료된다. 하나라도 거절하면 그 계정을 조직에서 제거하거나 요청을 재발송해야 한다
- Organizations로 생성한 계정은 요청을 받지 않는다. 수락 절차가 면제된다
- 모든 멤버 계정에 `AWSServiceRoleForOrganizations` service-linked role이 있어야 한다. 삭제한 계정이 있으면 초대 수락 과정에서 재생성된다
- all features 활성화 요청 handshake의 만료는 90일이다. 조직 참여 초대 handshake는 15일이다
- Enterprise Support plan 고객은 AWS에 전환 대행을 요청하는 assisted migration 경로를 쓸 수 있다. 시작하면 롤백할 수 없고 표준 절차로 돌아가려면 90일 만료를 기다려야 한다

---

## 3. OU 계층은 조직도가 아니라 정책 경계로 나눈다

OU 설계에서 흔한 실수는 회사 조직도를 그대로 옮기는 것입니다. AWS 공식 백서는 기능을 기준으로 그룹화하라고 권고합니다. 같은 정책을 받아야 하는 계정을 같은 OU에 두는 것이 목적이기 때문입니다.

백서가 제시하는 foundational OU는 두 개입니다.

| OU | 권장 계정 | 역할 |
| :--- | :--- | :--- |
| Security OU | Log Archive, Security Tooling(Audit) | 로그 중앙 집계와 보안 서비스 delegated admin 집계 |
| Infrastructure OU | Network, Backup, Identity, Operations Tooling, Monitoring, Shared Services | 공유 인프라와 위임 관리 지점 |

Security OU의 Log Archive 계정은 CloudTrail, Config, 그 밖의 보안 관련 로그를 모으는 지점입니다. 로그 데이터만 두고 접근을 최소화하며, Security OU에 붙인 SCP로 중앙 로깅 S3 버킷의 수정과 삭제를 막고 S3 versioning으로 이력을 남기라는 것이 문서의 권고입니다. Security Tooling(Audit) 계정은 Security Hub CSPM, GuardDuty, Macie, Firewall Manager, Detective, Inspector, IAM Access Analyzer의 delegated admin 집계 지점입니다.

Infrastructure OU에서는 Identity 계정에 IAM Identity Center를, Backup 계정에 AWS Backup과 Organizations backup policy 관리를, Network 계정에 IPAM과 Network Manager를 위임하는 구성이 문서 권장입니다.

조직이 커지면 다음 OU가 추가로 권장됩니다.

- Security_Prod, Infrastructure_Test와 Infrastructure_Prod, Workloads_Test와 Workloads_Prod
- PolicyStaging: 새 정책을 프로덕션에 걸기 전에 시험하는 OU
- Suspended: 사용을 중단한 계정을 격리하는 OU

OU 중첩은 root 아래 5단계까지입니다. 조직도를 그대로 반영하려다 6단계가 필요해지는 설계는 애초에 성립하지 않습니다.

---

## 4. SCP가 정하는 것은 권한이 아니라 상한이다

Service Control Policy를 한 문장으로 정의하면 조직 트리에 붙어서 그 아래 계정의 principal이 가질 수 있는 **최대 권한의 경계**를 정하는 정책입니다. 권한을 부여하지 않습니다.

![SCP와 permission boundary와 identity policy가 모두 허용한 것만 유효 권한으로 남아 API 호출이 수행되는 구조](/assets/img/sap-c02/scp-iam-effective-permissions.webp)

그림 왼쪽의 세 상자가 하나의 API 호출에 함께 걸리는 정책들입니다. 맨 위 SCP는 조직이 정한 최대 한도, 가운데 permission boundary는 그 principal에 걸린 최대 한도, 맨 아래 identity policy는 실제로 권한을 부여하는 정책입니다. 세 상자에서 나온 선이 가운데 유효 권한 상자로 모입니다. 세 정책이 **모두** 허용한 작업만 여기 남습니다. 유효 권한 상자에서 오른쪽 위로 향하는 실선은 그 교집합에 들어간 호출이 수행되는 경로이고, 오른쪽 아래로 향하는 점선은 셋 중 하나라도 허용하지 않은 호출이 암묵적 거부로 차단되는 경로입니다. SCP 상자에서 유효 권한으로 선이 이어진다고 해서 SCP가 권한을 만드는 것으로 읽으면 안 됩니다. 권한을 부여하는 것은 identity policy 하나뿐이고 나머지 둘은 한도만 정합니다.

이 구조에서 파생되는 규칙들입니다.

- 최종 유효 권한은 SCP와 RCP가 허용하는 것과 identity-based 및 resource-based policy가 허용하는 것의 논리적 교집합이다
- permission boundary가 함께 있으면 boundary, SCP, identity-based policy가 **모두** 허용해야 통과한다
- SCP만 붙여서는 어떤 권한도 생기지 않는다. IAM policy가 없으면 SCP가 전부 허용해도 접근이 없다

SCP가 통제하지 못하는 대상이 시험의 핵심입니다.

| 대상 | SCP 적용 여부 |
| :--- | :--- |
| management account의 사용자와 역할 | 적용되지 않는다 |
| delegated administrator로 지정된 멤버 계정 | 그대로 적용된다 |
| 멤버 계정의 root user | 적용된다. 예외는 아래 제한 불가 목록뿐이다 |
| service-linked role | 적용되지 않는다 |
| 조직 밖 계정의 사용자와 역할 | 적용되지 않는다 |

마지막 항목은 방향을 헷갈리기 쉽습니다. 조직 안 계정 A의 S3 버킷 정책이 조직 밖 계정 B에 접근을 허용하고 있다면, A에 걸린 SCP는 B의 사용자에게 적용되지 않습니다. 이 방향을 막는 것이 뒤에서 다룰 RCP입니다.

SCP로 아예 제한할 수 없는 작업도 문서에 명시되어 있습니다. management account가 수행하는 모든 작업, service-linked role 권한으로 수행하는 모든 작업, root user의 Enterprise Support plan 등록, CloudFront private content의 trusted signer 기능 제공, root user로 하는 Lightsail 이메일 서버와 EC2 인스턴스의 reverse DNS 설정이 여기에 들어갑니다.

---

## 5. Allow는 모든 레벨에서, Deny는 한 레벨에서

SCP의 평가 규칙은 Allow와 Deny가 비대칭입니다.

**Allow 판정.** root부터 대상 계정까지 경로의 **모든 레벨**에 명시적 Allow가 있어야 작업이 허용됩니다. 이 규칙 때문에 SCP를 활성화하면 `FullAWSAccess` 정책이 모든 root, OU, 계정에 자동으로 부착됩니다. 어느 한 레벨에서 이 정책을 제거하고 대체 Allow를 넣지 않으면 그 아래 전부가 차단됩니다.

**Deny 판정.** 경로의 **어느 한 레벨**의 SCP라도 Deny하면 차단됩니다. 하위 OU에서 Allow를 붙여도 상위의 Deny를 뒤집을 수 없습니다.

공식 문서의 시나리오에서 뽑은 결과입니다.

| 구성 | 결과 |
| :--- | :--- |
| root에 Deny SCP만 있고 Allow가 없다 | 모든 멤버 계정이 전 서비스 차단 |
| root에 서비스 allowlist SCP, 하위 OU에 FullAWSAccess | 교집합 때문에 root의 목록으로 제한 |
| 상위 OU에 Deny, 하위 OU에 그 서비스 Allow | Deny가 이긴다. 차단 |

여기서 두 가지 전략이 갈립니다.

**deny list 전략.** `FullAWSAccess`를 그대로 두고 Deny 문으로 금지 항목만 빼는 방식입니다. 새 서비스가 나오면 자동으로 허용되므로 운영 부담이 낮고, 대부분의 조직이 이 전략을 씁니다.

**allow list 전략.** `FullAWSAccess`를 제거하고 허용할 서비스만 나열하는 방식입니다. 규제 환경에서 승인된 서비스만 쓰게 할 때 선택하지만, 새 서비스를 쓸 때마다 정책을 갱신해야 하고 경로의 모든 레벨에서 Allow가 유지되어야 합니다.

정책 타입 자체를 껐다 켜는 경우도 알아둘 필요가 있습니다. root에서 SCP 정책 타입을 비활성화하면 그 root의 모든 엔티티에서 SCP가 자동으로 분리됩니다. 다시 활성화하면 `FullAWSAccess`만 남고 이전 부착 관계는 복구되지 않습니다.

---

## 6. SCP 구문에서 쓸 수 없는 것들

SCP는 IAM policy와 문법이 비슷하지만 쓸 수 없는 요소가 있습니다. 이 제약이 그대로 오답 선지가 됩니다.

| 요소 | SCP에서 |
| :--- | :--- |
| `Effect`, `Action`, `NotAction`, `Resource`, `NotResource`, `Condition`, `Sid`, `Version`, `Statement` | 지원 |
| `Principal`, `NotPrincipal` | **지원하지 않는다** |
| `Effect: Allow` 문의 `Resource` | `"*"`만 쓸 수 있다 |
| `Effect: Deny` 문의 `Resource` | 개별 ARN 지정 가능 |
| `Version` | `"2012-10-17"`이어야 한다 |

특정 role만 예외로 두려면 `Principal` 요소 대신 `Condition`의 `aws:PrincipalArn`을 씁니다. 리전 제한은 `aws:RequestedRegion`에 `StringNotEquals`를 걸고 `NotAction`으로 글로벌 서비스를 빼는 형태가 문서 예시입니다.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DenyOutsideApprovedRegions",
      "Effect": "Deny",
      "NotAction": [
        "iam:*",
        "organizations:*",
        "route53:*",
        "cloudfront:*",
        "support:*"
      ],
      "Resource": "*",
      "Condition": {
        "StringNotEquals": {
          "aws:RequestedRegion": ["ap-northeast-2", "us-east-1"]
        },
        "ArnNotLike": {
          "aws:PrincipalArn": "arn:aws:iam::*:role/OrgBreakGlassRole"
        }
      }
    }
  ]
}
```

글로벌 서비스를 `NotAction`으로 빼는 이유는 IAM이나 Organizations 같은 서비스의 엔드포인트가 us-east-1에 있어서, 리전 조건을 그대로 걸면 조직 관리 자체가 막히기 때문입니다.

정책 문서 크기 제한도 정책 타입마다 다릅니다.

| 정책 타입 | 최대 크기 |
| :--- | :--- |
| SCP | 10,240자 |
| RCP | 5,120자 |
| declarative policy | 10,000자 |
| backup policy | 10,000자 |
| tag policy | 10,000자 |
| chat applications policy | 10,000자 |
| Security Hub policy | 10,000자 |
| AI services opt-out policy | 2,500자 |
| resource-based delegation policy | 40,000자 |

SCP 크기를 5,120자로 기억하고 있다면 갱신이 필요합니다. 현재 문서에서 5,120자는 RCP의 값입니다.

콘솔로 저장하면 JSON 요소 사이의 공백과 줄바꿈이 제거되어 크기에 세지 않지만, CLI나 SDK로 저장하면 준 그대로 저장되고 자동 제거가 없습니다. 같은 정책이 콘솔에서는 통과하고 CLI에서는 크기 초과로 실패할 수 있습니다.

---

## 7. RCP는 반대 방향을 막는다

Resource Control Policy(RCP)는 조직 멤버 계정이 **소유한 리소스**에 대해 접근 상한을 정하는 정책입니다. SCP가 조직 안 principal이 나가는 방향을 막는다면, RCP는 조직 밖 principal이 들어오는 방향을 막습니다.

| 항목 | SCP | RCP |
| :--- | :--- | :--- |
| 통제 대상 | 조직 멤버 계정 안의 principal | 조직 멤버 계정이 소유한 리소스 |
| 조직 밖 principal 차단 | 불가 | 가능 |
| 최대 크기 | 10,240자 | 5,120자 |
| 엔티티당 부착 상한 | 10개 | 5개 |
| 자동 부착 정책 | `FullAWSAccess` | `RCPFullAWSAccess`. 분리 불가이며 5개 쿼터를 소모한다 |
| 적용 서비스 | 전 서비스 | 지원 서비스 목록에 한정 |
| management account | 적용되지 않는다 | 리소스에 적용되지 않는다 |
| service-linked role | 적용되지 않는다 | 호출에 적용되지 않고 trust policy에도 영향이 없다 |

RCP에서 반드시 알아야 할 세 가지입니다.

첫째, RCP는 리소스를 **소유한 계정** 경로의 정책이 적용됩니다. 계정 A의 버킷을 계정 B가 접근하면 A의 RCP가 적용되고, B의 RCP는 그 요청에 적용되지 않습니다. 우리 조직 사용자가 파트너사 소유 버킷에 접근하는 것을 막고 싶다면 그것은 RCP가 아니라 SCP의 몫입니다.

둘째, RCP는 일부 서비스에만 적용됩니다. 확인된 목록에 s3, sts, kms, sqs, secretsmanager, logs, dynamodb, ecr, events, wafv2, cloudfront, opensearch, memorydb, dax, codebuild, codecommit, codepipeline, transfer, signin, support 등이 들어 있습니다. 지원 목록에 없는 서비스는 RCP로 통제할 수 없습니다.

셋째, RCP는 AWS managed KMS key에 적용되지 않습니다. customer managed key에만 걸립니다.

RCP의 대표 용례는 `aws:PrincipalOrgID` 조건으로 조직 밖 principal의 S3 접근을 전 계정에서 일괄 Deny하는 것입니다. 각 팀이 자기 버킷 정책을 계속 관리하더라도 조직 경계를 넘는 접근은 조직 레벨에서 막힙니다.

---

## 8. declarative policy는 control plane에서 강제된다

SCP와 RCP는 authorization policy입니다. API 호출이 들어왔을 때 허용할지 거부할지를 판정합니다. declarative policy는 층이 다릅니다. 서비스의 **control plane**에서 구성 자체를 강제합니다.

이 차이가 만드는 결과가 세 가지 있습니다.

- 서비스가 새 기능이나 새 API를 추가해도 선언한 baseline 구성이 유지된다. 조건식을 다시 쓸 필요가 없다
- **service-linked role도 통제한다.** 공식 문서의 비교표에서 SCP는 No, RCP는 No, declarative policy는 Yes다
- 정책을 분리하면 해당 속성 상태가 부착 이전 상태로 롤백된다

새 계정이 조직에 들어와도 상속됩니다. account status report로 범위 안 계정의 속성 현황을 확인할 수 있고, 강제로 실패한 요청에 대해 사용자에게 보여줄 커스텀 에러 메시지도 정의할 수 있습니다.

문서가 제시하는 대표 용례는 VPC 리소스의 퍼블릭 인터넷 접근 차단, VPC 트래픽의 전송 중 암호화 강제, EC2 Allowed Images Settings입니다. "허용된 AMI 목록으로 제한하되 service-linked role이 수행하는 작업에도 적용되어야 한다"는 요구가 지문에 있으면 SCP가 아니라 declarative policy입니다.

세 정책 타입의 층 차이를 정리하면 다음과 같습니다.

| 축 | SCP | RCP | declarative policy |
| :--- | :--- | :--- | :--- |
| 강제 지점 | API authorization | API authorization | 서비스 control plane |
| 대상 | 조직 안 principal | 조직 계정 소유 리소스 | 서비스 구성 속성 |
| service-linked role 통제 | 불가 | 불가 | 가능 |
| 새 API 추가 시 | 조건을 다시 써야 한다 | 조건을 다시 써야 한다 | baseline이 유지된다 |
| 분리 시 동작 | 상한이 사라진다 | 상한이 사라진다 | 속성이 이전 상태로 롤백된다 |

---

## 9. tag policy와 backup policy와 AI services opt-out policy

**tag policy**는 태그 키의 대소문자 처리와 허용 값을 표준화하는 정책입니다. 여기서 오해가 자주 생깁니다.

- **태그가 없는 리소스와 정책에 정의되지 않은 태그는 규정 준수 평가 대상이 아니다.** tag policy는 이미 붙는 태그의 형식을 다룬다
- enforcement 옵션은 지정한 리소스 타입에 대한 **비준수 태깅 작업**을 실패시키는 기능이다. 리소스 생성 자체를 막는 기능이 아니다
- all features 모드 전용이다
- 준수 여부 확인은 AWS Resource Groups와 Tag Editor로 한다. management account에서는 조직 전체 계정의 준수 정보를 본다

"태그 없이는 EC2 인스턴스를 만들지 못하게 하라"는 요구는 tag policy로 충족되지 않습니다. `aws:RequestTag`와 `aws:TagKeys` 조건을 쓴 SCP가 생성 시점 차단을 담당합니다. 두 정책을 함께 두면 표준화와 차단을 모두 얻습니다.

**backup policy**는 AWS Backup의 backup plan을 조직 트리에 붙이고 상속 규칙으로 합쳐 계정별 effective policy를 만드는 정책입니다.

- 부분 정책을 여러 레벨에 나눠 붙일 수 있다. 다만 합쳐진 effective policy가 필수 요소를 모두 갖추지 못하면 AWS Backup은 유효하지 않다고 보고 **백업하지 않는다**
- 정책으로 만들어진 backup plan은 멤버 계정의 AWS Backup 콘솔에 immutable로 보인다. 조회는 되고 변경은 안 된다. 태그 추가와 제거만 `TagResource`와 `UntagResource`로 가능하다

**AI services opt-out policy**는 AWS AI 서비스가 서비스 개선 목적으로 고객 콘텐츠를 저장하고 사용하는 것을 조직 단위로 거부하는 정책입니다. opt out하면 그 서비스가 서비스 개선 목적으로 저장했던 관련 과거 콘텐츠가 삭제됩니다. 서비스 제공에 필요한 콘텐츠는 삭제되지 않습니다.

정책 개수와 부착 상한도 타입마다 다릅니다.

| 정책 타입 | 조직당 개수 | 엔티티당 부착 상한 |
| :--- | :--- | :--- |
| SCP | 10,000 | 최대 10, 최소 1 |
| RCP | 2,000 | 최대 5, 최소 1 |
| declarative policy | 1,000 | 최대 10 |
| backup policy | 1,000 | 최대 10 |
| tag policy | 1,000 | 최대 10 |
| Security Hub policy | 1,000 | 최대 10 |
| AI services opt-out policy | 1,000 | 최대 5 |
| chat applications policy | 1,000 | 최대 5 |

부착 상한에서 두 가지를 놓치기 쉽습니다. SCP와 RCP는 **최소 1개**입니다. 마지막 정책은 제거할 수 없습니다. 그리고 **상속으로 영향을 주는 정책은 부착 쿼터에 세지 않습니다.** 부착 쿼터는 직접 붙인 정책만 세며 전부 hard limit입니다. 정책 하나를 붙일 수 있는 대상 수는 무제한입니다.

---

## 10. 계정을 만들고 옮기고 빼는 절차의 제약

계정 생애주기에는 시험에 자주 나오는 시간 제약과 전제 조건이 있습니다.

**생성.** 조직 안에서 생성한 계정에는 management account가 접근할 수 있는 IAM role이 자동으로 만들어집니다. 초대로 들어온 계정에는 자동 생성되지 않습니다. 이 role은 계정을 조직에서 제거해도 자동 삭제되지 않으므로 수동으로 지워야 합니다. 동시 계정 생성은 5건, 동시 계정 종료는 3건입니다.

**제거.** 조직에서 계정을 빼려면 그 계정이 standalone으로 동작할 정보를 갖춰야 합니다.

- support plan 선택, 연락처 정보 제공과 검증, 유효한 결제 수단이 필요하다
- 조직 안에서 생성한 계정은 생성 후 **최소 4일**이 지나야 제거할 수 있다. 초대로 들어온 계정에는 이 대기 기간이 없다
- 제거 대상 계정은 조직에서 활성화한 어떤 AWS 서비스의 **delegated administrator여서도 안 된다.** 먼저 다른 계정으로 지정을 옮겨야 한다
- 30일 동안 닫을 수 있는 멤버 계정 수는 250개 또는 멤버 계정의 20% 중 큰 값이며 최대 1,000이다. 이 값은 조정할 수 없다

**제거 이후.** 계정이 조직을 떠나면 SCP 제한이 사라져 그 계정의 사용자와 역할이 이전보다 **더 넓은 권한**을 갖게 될 수 있습니다. "계정을 조직에서 빼면 통제가 강해진다"는 직관과 반대입니다. 또 계정에 붙은 태그가 모두 삭제되고, 멤버였던 기간의 비용 및 사용량 데이터에 그 계정이 접근할 수 없게 됩니다. management account는 계속 볼 수 있고, 계정이 다시 합류하면 접근이 복구됩니다.

---

## 11. permission set이 대상 계정에서 IAM role이 되는 지점

AWS IAM Identity Center는 여러 AWS 계정과 애플리케이션에 대한 접근을 하나의 신원 소스로 관리하는 서비스입니다. 2022년 7월 26일에 AWS Single Sign-On에서 이름이 바뀌었고, `sso`와 `identitystore` API 네임스페이스와 `AWSServiceRoleForSSO` 역할 이름은 그대로입니다.

![구성원이 외부 IdP로 인증하고 IAM Identity Center의 permission set이 Prod와 Dev 계정의 IAM role로 provisioning되는 흐름](/assets/img/sap-c02/identity-center-login-flow.webp)

그림은 왼쪽에서 오른쪽으로 한 번의 로그인이 여러 계정의 role로 펼쳐지는 경로를 따라갑니다. 맨 왼쪽 구성원이 AWS access portal에 로그인하면 외부 IdP가 SAML 2.0으로 인증을 처리합니다. 사용자와 그룹 정보는 SCIM으로 미리 프로비저닝되어 있어 인증된 신원이 identity store의 사용자와 매칭됩니다. 그다음 IAM Identity Center를 거쳐 permission set에 도달합니다. permission set 상자는 정책 묶음의 정의일 뿐이고, 오른쪽으로 갈라지는 두 선이 그 정의가 대상 계정에서 실제 IAM role로 provisioning된 결과입니다. Prod 계정과 Dev 계정에 같은 permission set이 각각의 role로 찍혀 있습니다. 사용자가 실제로 assume하는 것은 permission set이 아니라 계정마다 만들어진 이 role입니다. 할당 하나는 사용자 또는 그룹, permission set, 대상 AWS 계정 세 요소의 조합입니다.

인스턴스 유형 구분이 시험에 나옵니다.

| 유형 | 배포 위치 | AWS 계정 접근 관리 |
| :--- | :--- | :--- |
| organization instance | Organizations management account | 가능 |
| account instance | 개별 계정 | **불가능**. 일부 AWS managed application의 격리 배포용 |

계정당 IAM Identity Center 인스턴스는 1개입니다.

permission set 관련 쿼터입니다.

| 항목 | 값 | 증액 |
| :--- | :--- | :--- |
| 인스턴스당 permission set | 3,500 | 가능 |
| AWS 계정당 provisioned permission set | 500 | 가능 |
| permission set당 inline policy | 1 | 불가 |
| permission set당 AWS managed + customer managed policy | 25 | 불가 |
| inline policy 최대 크기 | 32,768 바이트(공백 제외 10,240 바이트) | 불가 |
| 하나의 permission set에 계정당 할당 가능한 그룹 | 100 | 불가 |
| 동시에 업데이트 가능한 permission set(IAM role) | 계정당 1 | 불가 |
| 연결 가능한 Active Directory | 동시 1개 | 불가 |
| trusted token issuer | 10 | 불가 |
| 활성화 가능한 AWS 리전 | 6 | 가능 |
| identity store 사용자 | 200,000 | 가능 |
| identity store 그룹 | 100,000 | 가능 |
| 구성 가능한 AWS 계정 | 7,000 | 가능 |
| 구성 가능한 애플리케이션 | 7,000 | 가능 |

managed policy 25개에는 함정이 하나 더 있습니다. permission set은 대상 계정에 IAM role로 provisioning되므로 실제 상한은 그 계정의 IAM `Managed policies attached to an IAM role` 쿼터에 걸립니다. 이 IAM 쿼터는 기본 20이고 최대 25까지 자동 승인으로 증액됩니다. 25개를 실제로 붙이려면 계정마다 IAM 쿼터를 25로 올려야 합니다.

리전 관련해서도 통념이 갱신되었습니다. "IAM Identity Center는 단일 리전에서만 활성화된다"는 설명은 현재 문서와 맞지 않습니다. 인스턴스당 6개 리전까지 활성화할 수 있고 증액도 가능하며, 다중 리전 복제 시 throttle 한도는 리전마다 따로 적용됩니다.

운영 규모 관련 권고도 있습니다. AWS는 사용자 50,000명, 그룹 10,000개, permission set 500개, 애플리케이션 3,000개를 넘으면 콘솔 대신 CLI와 API로 관리할 것을 권고합니다. `ProvisionPermissionSet`의 `ALL_PROVISIONED_ACCOUNTS` 옵션은 최대 3,500개 계정까지 처리하고, 그 이상은 `AWS_ACCOUNT` 옵션으로 계정별 호출해야 하며 동시 호출은 3건까지입니다.

ABAC는 IdP가 보낸 속성을 session tag로 전달하고, permission set의 정책에서 `aws:PrincipalTag`로 참조해 리소스 태그와 대조하는 방식으로 구현합니다. 같은 permission set 하나로 팀별 리소스 격리를 만들 수 있어 permission set 개수 증가를 억제하는 효과가 있습니다. 세부 평가 로직은 IAM 심화 편의 영역입니다.

---

## 12. Control Tower의 landing zone과 control 두 축

AWS Control Tower는 AWS Organizations, AWS Service Catalog, AWS IAM Identity Center를 오케스트레이션해 landing zone을 1시간 이내에 구성하는 서비스입니다. Organizations가 정책과 계정 구조를 제공한다면, Control Tower는 그 위에 표준 계정 구성과 control 카탈로그와 drift 탐지를 얹습니다.

![Control Tower가 Security OU와 Log archive 및 Audit 계정을 자동 생성하고 Infrastructure와 Workloads OU는 직접 만들어야 하는 구성](/assets/img/sap-c02/control-tower-landing-zone.webp)

왼쪽 큰 상자가 Control Tower이고 여기서 나가는 선이 landing zone 배포 결과입니다. 실선은 Security OU로 이어지고 그 아래 점선은 Sandbox OU로 이어집니다. 실선과 점선의 차이가 자동 생성과 선택의 차이입니다. Security OU는 landing zone이 반드시 만들고, Sandbox OU는 landing zone을 만들 때 선택했을 때만 생깁니다. Security OU에서 오른쪽으로 갈라지는 두 선이 그 안에 자동으로 만들어지는 Log archive 계정과 Audit 계정입니다. 아래쪽 점선 테두리 영역은 Control Tower가 만들어 주지 않는 것들을 모아둔 것입니다. Infrastructure OU와 그 안의 Network, Backup, Identity 계정, Workloads OU와 그 안의 Prod, Staging 계정은 전부 직접 만들어야 합니다. 문서에 권장 구성으로 적혀 있을 뿐 landing zone 배포 결과물이 아닙니다.

landing zone이 만드는 것과 만들지 않는 것을 구분해야 합니다.

| 항목 | Control Tower가 |
| :--- | :--- |
| Security OU | 자동으로 만든다 |
| Audit 계정, Log archive 계정 | 자동으로 만든다. Security OU 안에 놓인다 |
| Sandbox OU | landing zone 생성 시 선택하면 만든다 |
| **Infrastructure OU, Workloads OU** | **만들어 주지 않는다.** 직접 만든다 |
| management account | 기존 조직에 도입하면 기존 것을 그대로 쓴다. 새로 만들지 않는다 |

조직당 landing zone은 1개입니다. Root는 OU가 아니라 management account와 모든 OU 및 계정을 담는 컨테이너이므로 Control Tower에서 Root 레벨로 enrolled 계정을 governance할 수 없습니다.

**Account Factory**는 Service Catalog provisioned product 위의 추상화로 구현된 계정 프로비저닝 기능입니다. 표준화된 계정 생성 요청을 받아 계정을 만들고 landing zone 구성과 control을 적용한 상태로 넘깁니다.

**control의 두 축**이 시험에서 가장 자주 갈리는 지점입니다. behavior와 guidance는 서로 독립된 축입니다.

| behavior | 구현 | 동작 리전 | 상태 값 |
| :--- | :--- | :--- | :--- |
| preventive | SCP, RCP, declarative policy | 모든 리전 | enforced, not enabled |
| detective | AWS Config rule | Control Tower 지원 리전만 | clear, in violation, not enabled |
| proactive | AWS CloudFormation hook | Control Tower 지원 리전만 | PASS, FAIL, SKIP |

| guidance | 의미 |
| :--- | :--- |
| mandatory | 필수로 분류된 control |
| strongly recommended | 강하게 권장되는 control |
| elective | 선택적으로 켜는 control |

behavior에서 세 가지를 구분해야 합니다. preventive는 정책 층이라 위반 자체가 발생하지 않습니다. detective는 Config rule 기반이라 리소스가 만들어진 뒤에 위반을 탐지합니다. proactive는 CloudFormation hook이라 **CloudFormation이 프로비저닝하는 리소스에만** 적용됩니다. 콘솔이나 CLI로 직접 만든 리소스는 proactive control을 거치지 않습니다.

Landing Zone 버전 4.0부터 mandatory control이 기본 적용되지 않습니다. "landing zone을 최신 버전으로 올리면 mandatory control이 자동으로 다 걸린다"는 설명은 현재 문서와 반대입니다.

또한 문서의 정식 명칭은 control입니다. guardrail은 괄호로 병기되는 옛 용어입니다.

**리전 취급**도 함정이 많은 영역입니다.

- landing zone을 만들 때 콘솔에 접속해 있던 리전이 home Region이 된다. **선택 후에는 변경할 수 없다**
- 어떤 리전을 governance에서 빼도 그 리전에 리소스를 배포하는 것 자체는 막히지 않는다. 그 리소스가 Control Tower governance 밖에 놓일 뿐이다
- 리전 배포를 실제로 차단하려면 Region deny control이나 `aws:RequestedRegion` 조건 SCP를 쓴다
- 새 리전을 추가하면 landing zone은 baseline되지만 OU 안 개별 계정은 갱신되지 않는다. **OU를 재등록해야** 계정이 갱신된다

**drift 감지**는 Control Tower가 landing zone 배포 이후 조직 구성이 기준에서 벗어났는지를 탐지하는 기능입니다. 누군가 Organizations 콘솔에서 직접 OU를 옮기거나 SCP를 떼면 drift로 표시되고, landing zone을 repair해서 기준 상태로 되돌립니다.

---

## 13. RAM에서 무엇을 누구에게 공유할 수 있는가

AWS Resource Access Manager(RAM)는 계정이 소유한 리소스를 다른 계정, OU, 조직 전체와 공유하는 서비스입니다. RAM 사용 자체와 resource share 생성에는 추가 요금이 없고, 리소스 사용 요금은 소유 서비스 기준으로 부과됩니다.

공유 방식의 기본 규칙입니다.

- 조직 안 공유를 활성화하면(enable sharing with AWS Organizations) 조직 내 계정 공유에 초대가 필요 없다
- **조직 밖 계정과 공유하면 초대 절차가 시작되고 수신자가 수락해야 접근할 수 있다**
- resource share는 리전 단위다. 리전 리소스는 같은 리전의 share에만 담을 수 있고, 글로벌 리소스는 홈 리전 us-east-1의 share에만 담을 수 있다
- RAM으로 공유하면 수신 계정 콘솔과 API에서 자기 계정 리소스처럼 보인다. resource-based policy로만 공유하면 ARN으로 직접 지정해야 하고 그렇게 보이지 않는다
- share에 붙인 managed permission은 수신 계정에 부여 가능한 **최대** 권한이다. 수신 계정 관리자가 identity-based policy로 개별 role과 user에 다시 부여해야 하며 share의 권한을 넘을 수 없다
- resource-based policy로 공유하던 리소스는 `PromoteResourceShareCreatedFromPolicy`로 완전한 RAM 관리 share로 승격할 수 있다

공유 대상 범위가 리소스마다 다릅니다. 이 표가 곧 오답 선지의 근거입니다.

| 공유 범위 | 리소스 |
| :--- | :--- |
| 조직 밖 계정과도 공유 가능 | Transit gateway, TGW multicast domain, Prefix list, Route 53 Resolver rule, License configuration, Aurora DB cluster, Capacity Reservation, Dedicated host, IPAM pool, IPAM resource discovery, EC2 Image Builder 리소스, Outposts Site |
| 조직 안 계정으로만 공유 가능 | **Subnet**, Security group, Outpost, Local gateway route table, S3 on Outposts, Customer-owned IPv4 pool, Capacity Block |
| IAM role과 user 단위로도 공유 가능 | IPAM pool, EC2 Image Builder Component/Image/ImageRecipe/ContainerRecipe, Security group, Placement group, Resolver DNS Firewall rule group, Resolver query logging configuration |
| 계정 및 OU 단위 공유만 가능 | Subnet, Transit gateway, Prefix list, Resolver rule, IPAM resource discovery |

Capacity Reservation은 조직 밖 공유가 되지만 Capacity Block은 조직 안으로 한정된다는 짝이 특히 헷갈립니다.

subnet 공유에는 조건이 하나 더 있습니다. **default VPC의 subnet은 공유할 수 없습니다.** 직접 만든 subnet만 공유됩니다. subnet을 share에 담으려면 `ram:CreateResourceShare` 외에 `ec2:DescribeSubnets`와 `ec2:DescribeVpcs` 권한이 필요합니다.

---

## 14. shared VPC에서 owner와 participant가 각각 할 수 있는 일

RAM으로 subnet을 공유하는 구성은 네트워크팀이 VPC를 소유하고 애플리케이션 팀이 그 안에서 워크로드를 운영하는 형태입니다. 책임 분할이 문서에 아주 세밀하게 규정되어 있고, 그 경계가 그대로 시험 문항이 됩니다.

![owner 계정의 route table과 NAT gateway는 그대로 두고 shared subnet만 RAM으로 넘어가 participant가 ENI와 security group과 flow log를 만드는 구조](/assets/img/sap-c02/ram-vpc-subnet-sharing.webp)

왼쪽 상자가 VPC owner 계정이고 오른쪽 상자가 participant 계정입니다. owner 계정 안에 route table, shared subnet, NAT gateway가 놓여 있는데 셋 다 owner 소유입니다. route table에는 participant가 조회만 가능하다고, NAT gateway에는 조회조차 불가능하다고 적혀 있습니다. 가운데를 가로지르는 선은 shared subnet이 RAM resource share를 거쳐 participant 계정으로 공유되는 경로입니다. 같은 조직 안 공유이므로 초대 없이 바로 적용되고, default VPC의 subnet은 애초에 이 경로에 올릴 수 없습니다. participant 계정 쪽에서 선이 도착하는 곳은 network interface입니다. participant가 공유 subnet 안에 만드는 것이 이 ENI이고 그 쿼터는 participant 계정에서 나갑니다. ENI에서 위로 올라가는 선은 participant가 직접 만드는 security group이며, 여기에 owner의 default security group은 쓸 수 없다고 적혀 있습니다. ENI에서 오른쪽으로 돌아 아래로 내려오는 선은 flow log이고 자기가 소유한 ENI에 대해서만 만들 수 있습니다. participant 상자에서 owner 상자로 되돌아가는 선이 하나도 없다는 점이 이 그림의 요지입니다.

owner의 책임 범위입니다.

- subnet, route table, NACL, peering connection, gateway endpoint와 interface endpoint, Route 53 Resolver endpoint, IGW, NAT gateway, VGW, transit gateway attachment를 만들고 관리한다
- **shared subnet에 transit gateway를 붙일 수 있는 것은 VPC owner뿐이다**
- participant가 만든 ENI와 security group을 describe만 할 수 있다. 그 외 조작은 못 한다
- participant가 만든 flow log를 describe하거나 삭제할 수 없다

participant의 범위입니다.

- network interface와 security group, 그리고 자기가 소유한 ENI의 flow log를 만들 수 있다
- participant가 만든 리소스는 **participant 계정의 VPC 쿼터**를 소모한다
- route table을 만들거나 삭제하거나 연결할 수 없다. 조회만 가능하다
- NACL은 만들거나 삭제하거나 교체할 수 없다. owner가 만든 것을 조회만 할 수 있다
- NAT gateway는 생성, 삭제, 조회가 전부 불가하다. IGW와 egress-only IGW는 생성, 연결, 삭제가 불가하고 IGW는 조회만 가능하다
- VPC의 default security group으로 인스턴스를 띄울 수 없다. owner 소유이기 때문이다. 별도로 공유받지 않은 owner 소유 non-default security group도 쓸 수 없다
- 자기 security group 규칙에서 다른 participant나 owner의 security group을 `account-number/security-group-id` 형식으로 참조할 수 있다
- subnet과 VPC의 속성을 수정할 수 없고 조회만 할 수 있다
- **VPC 태그와 shared VPC 안 리소스의 태그는 participant에게 공유되지 않는다**

여기서 shared VPC와 Transit Gateway의 선택 기준이 나옵니다. shared VPC는 하나의 VPC 안 implicit routing을 쓰므로 라우팅 구성이 필요 없지만, participant가 라우팅과 인터넷 경로를 전혀 통제할 수 없고 공유 범위가 같은 조직 안으로 한정됩니다. Transit Gateway는 조직 밖 계정과도 공유할 수 있고 route table 분리로 도달 범위를 제한할 수 있습니다. 파트너사 연결이 요구사항이면 subnet 공유는 애초에 성립하지 않습니다.

---

## 15. organization trail과 로그 아카이브 계정

멀티 계정 환경에서 API 활동 로그를 모으는 표준 구성은 organization trail입니다. 계정마다 trail을 만들어 중앙 버킷을 대상으로 지정하는 방식과 비교하면 차이가 분명합니다.

| 항목 | organization trail | 계정별 trail + 교차 계정 버킷 |
| :--- | :--- | :--- |
| 생성 권한 | management account 또는 CloudTrail delegated administrator | 각 계정 관리자 |
| 신규 계정 | 조직 합류 시 자동으로 trail이 추가되고 로깅이 시작된다 | 계정마다 구성 절차가 필요하다 |
| 멤버 계정의 변경 | 목록에서 볼 수는 있지만 삭제, 로깅 중지, 이벤트 타입 변경이 전부 불가하다 | 계정 관리자가 자유롭게 끄고 지울 수 있다 |

organization trail의 세부 동작입니다.

- 콘솔로 만든 organization trail은 전부 multi-Region이다. single-Region trail은 CLI로만 만들 수 있다
- 생성하면 `AWSServiceRoleForCloudTrail` service-linked role이 만들어진다. 계정이 조직에 추가되면 trail과 SLR이 그 계정에 추가되고, 제거되면 trail과 SLR이 삭제된다. 제거 전에 만들어진 로그 파일은 S3 버킷에 그대로 남는다
- S3 버킷 구조는 조직 ID 폴더 아래 계정 ID 하위 폴더다. 기본적으로 management account만 그 버킷과 로그에 접근한다
- organization trail을 만든 계정이 나중에 management account 자리에서 내려오면 그 trail은 organization trail이 아닌 일반 trail이 된다
- multi-Region organization trail의 home Region이 opt-in Region이면, 그 리전을 활성화한 멤버 계정만 활동을 그 trail로 보낸다

**Event history의 범위**는 별도로 기억해야 합니다. Event history는 로그인한 계정의 이벤트만 보여줍니다. management account로 로그인해도 멤버 계정 이벤트는 Event history에 나오지 않습니다. 조직 전체를 조회하려면 S3에 쌓인 organization trail 로그를 Athena 등으로 봐야 합니다.

**CloudTrail delegated administrator**는 조직당 최대 3개입니다. delegated administrator가 만든 organization trail과 event data store의 소유자는 여전히 management account이고, delegated administrator 지정을 해제해도 그 리소스는 삭제되지 않습니다. organization trail을 account-level trail로 전환하거나 그 반대로 전환하는 것은 management account만 할 수 있습니다.

로그가 모이는 곳은 Security OU의 Log Archive 계정입니다. 로그 데이터만 두어 접근을 최소화하고, Security OU에 붙인 SCP로 중앙 로깅 S3 버킷의 수정과 삭제를 막고 S3 versioning으로 이력을 남기는 것이 문서 권고입니다. 감사 요건이 "로그를 만든 계정의 관리자가 그 로그를 지울 수 없어야 한다"일 때, 계정 분리와 SCP와 versioning 셋이 함께 답을 구성합니다.

---

## 16. 조직 구조 위의 비용 배분

Domain 1이 묻는 비용은 조직 축입니다. 계정 구조 위에서 비용이 어떻게 합쳐지고 어떻게 나뉘는가입니다.

**통합 결제.** 조직의 management account가 payer가 되어 모든 멤버 계정의 사용량이 하나의 청구서로 합쳐집니다. 볼륨 할인 구간도 합산 기준으로 적용됩니다.

**RI와 Savings Plans 할인 공유.** 조직의 management account가 통제하고 계정 단위로 활성화와 비활성화가 가능합니다. 공유 모드는 세 가지입니다.

| 모드 | 동작 |
| :--- | :--- |
| organization-wide | 조직의 모든 계정이 남는 혜택을 공유한다 |
| prioritized group | 지정 그룹에 먼저 배정하고 남는 혜택은 조직의 다른 계정으로 흘러간다 |
| restricted group | 지정 그룹 밖으로는 남는 용량이 있어도 공유하지 않는다 |

어느 모드든 커밋먼트는 **소유 계정에 먼저 적용되고** 남은 혜택이 공유됩니다. group sharing의 그룹은 AWS Cost Categories로 정의하며 Accounts 차원만 쓸 수 있고, 계정은 그룹 하나에만 속할 수 있으며 **payer 계정은 sharing group에 들어갈 수 없습니다.**

공유 선호 설정은 언제든 바꿀 수 있지만, 월 최종 청구는 **그달 마지막 날 23:59:59 UTC 시점의 설정**으로 계산됩니다. 그리고 Savings Plans 소유 계정이 sharing preference에서 활성 상태여야 다른 계정에 할인이 적용되며, 소유 계정이 조직을 떠나면 그 Savings Plans는 consolidated bill에 더 이상 적용되지 않습니다.

**cost allocation tag.** 비용을 태그 기준으로 나눠 보려면 태그를 cost allocation tag로 활성화해야 합니다.

- AWS generated(`aws:` 접두사)와 user-defined(`user:` 접두사) 두 종류이고 **각각 따로 활성화해야** Cost Explorer와 cost allocation report에 나타난다
- Billing 콘솔의 cost allocation tags 관리자는 **조직의 management account와 조직에 속하지 않은 단독 계정만** 접근할 수 있다. 멤버 계정에서는 활성화할 수 없다
- 태그가 Billing and Cost Management 콘솔에 나타나기까지 최대 24시간이 걸린다
- cost allocation report는 태그가 붙은 리소스와 붙지 않은 리소스를 모두 포함하며 총액이 Bills 페이지 총액과 대사된다

태그 표준화는 tag policy가, 태그 없는 리소스 생성 차단은 `aws:RequestTag` 조건 SCP가, 비용 리포트 노출은 cost allocation tag 활성화가 담당합니다. 세 층이 각각 필요합니다.

---

## 17. delegated administrator와 StackSets

management account에 리소스를 두지 않으려면 조직 서비스의 관리 권한을 멤버 계정으로 위임해야 합니다. AWS 공식 문서가 management account에 리소스를 두지 말 것을 권고하는 근거로 드는 것이 바로 "SCP가 management account의 사용자와 역할을 제한하지 않는다"입니다.

Organizations는 정책 관리 자체를 멤버 계정에 위임할 수 있습니다. 기본적으로 management account만 할 수 있는 policy action을 지정 멤버 계정이 수행하도록 resource-based delegation policy를 붙이는 방식이고, 이 정책의 최대 크기는 40,000자입니다.

서비스별로 delegated administrator 개수가 다릅니다.

| 서비스 | delegated administrator |
| :--- | :--- |
| CloudTrail | 조직당 최대 3개 |
| GuardDuty, Macie, Security Hub CSPM | 조직당 1개 |
| AWS Health | 최대 5개 멤버 계정 등록 |
| CloudFormation StackSets | 여러 개 등록 가능. home Region 한 곳에서만 위임하면 된다 |
| Firewall Manager, S3 Storage Lens, Trusted Advisor | 글로벌이라 home Region에서만 위임한다 |

서비스별 계정 수 상한도 따로 있습니다. AWS Audit Manager 250, Amazon Detective 1,200, IAM Identity Center 7,000, AWS Security Hub 10,000, Amazon Macie 10,000, AWS Control Tower 10,000, Amazon Inspector 10,000, AWS Service Catalog 15,000입니다.

**CloudFormation StackSets**는 administrator 계정에서 정의한 템플릿을 여러 계정과 여러 리전의 스택으로 한 번에 생성, 수정, 삭제하는 기능입니다. 권한 모델이 두 가지입니다.

| 권한 모델 | 특징 |
| :--- | :--- |
| self-managed | 대상 계정마다 신뢰 관계 IAM role을 직접 만든다. 조직 밖 계정에도 배포할 수 있다 |
| service-managed | Organizations 연동. OU 단위 배포와 automatic deployment로 신규 계정 자동 배포가 가능하고 delegated administrator를 지원한다 |

organization trail과 StackSets의 차이를 구분해야 하는 문항이 나옵니다. StackSets의 automatic deployment는 신규 계정에 리소스를 자동으로 **배포**하지만, 배포된 리소스는 여전히 그 멤버 계정 소유라 계정 관리자가 바꿀 수 있습니다. 멤버 계정이 손댈 수 없어야 한다는 요구가 있으면 organization trail처럼 조직이 소유하는 리소스가 답입니다.

---

## 18. 암기해야 하는 하드 리밋과 동작 제약

시험에서 선지를 직접 가르는 수치와 동작입니다.

**Organizations 트리와 정책**

| 항목 | 값 |
| :--- | :--- |
| 조직당 root | 1 |
| 조직당 OU | 2,000 |
| OU 중첩 깊이 | root 아래 5단계 |
| 조직당 기본 계정 수 | 10 (증액 시 최대 50,000) |
| 엔티티당 SCP | 최대 10, 최소 1 |
| 엔티티당 RCP | 최대 5, 최소 1 |
| SCP 최대 크기 | 10,240자 |
| RCP 최대 크기 | 5,120자 |
| tag/backup/declarative policy 최대 크기 | 10,000자 |
| AI services opt-out policy 최대 크기 | 2,500자 |
| resource-based delegation policy 최대 크기 | 40,000자 |
| 정책 하나를 붙일 수 있는 대상 수 | 무제한 |
| 상속으로 영향을 주는 정책 | 부착 쿼터에 세지 않는다 |
| root/OU/account당 태그 | 각 50 |

**계정 생애주기**

| 항목 | 값 |
| :--- | :--- |
| 조직 안에서 생성한 계정의 제거 대기 | 최소 4일 |
| 초대로 들어온 계정의 제거 대기 | 없다 |
| 동시 계정 생성 | 5건 |
| 동시 계정 종료 | 3건 |
| 30일간 닫을 수 있는 멤버 계정 | 250개 또는 20% 중 큰 값, 최대 1,000. 조정 불가 |
| 조직 참여 초대 handshake 만료 | 15일 |
| all features 활성화 요청 handshake 만료 | 90일 |
| 완료된 handshake 목록 유지 | 30일 |

**Control Tower**

| 항목 | 값 |
| :--- | :--- |
| 조직당 landing zone | 1 |
| landing zone 구성 시간 | 1시간 이내 |
| 자동 생성 계정 | Audit, Log archive 2개 |
| 자동 생성 OU | Security OU |
| home Region 변경 | 불가 |
| preventive control 동작 리전 | 모든 리전 |
| detective와 proactive control 동작 리전 | Control Tower 지원 리전만 |
| mandatory control 기본 적용 | Landing Zone 4.0부터 적용되지 않는다 |

**IAM Identity Center**

| 항목 | 값 |
| :--- | :--- |
| 계정당 인스턴스 | 1 |
| 인스턴스당 permission set | 3,500 |
| 계정당 provisioned permission set | 500 |
| permission set당 inline policy | 1 |
| permission set당 managed policy | 25 (증액 불가) |
| IAM role당 managed policy 쿼터 | 기본 20, 최대 25 |
| permission set당 계정당 그룹 | 100 (증액 불가) |
| 활성화 가능 리전 | 6 |
| identity store 사용자 / 그룹 | 200,000 / 100,000 |
| API throttle | 20 TPS |
| SCIM throttle | write 25 TPS, read 40 TPS |
| SAML assertion 최대 | 50,000자 |

**CloudTrail과 RAM**

| 항목 | 값 |
| :--- | :--- |
| CloudTrail delegated administrator | 조직당 최대 3 |
| 콘솔로 만든 organization trail | 전부 multi-Region |
| RAM resource share 범위 | 리전 단위. 글로벌 리소스는 us-east-1 |
| RAM 요금 | 없다 |
| default VPC subnet 공유 | 불가 |

---

## 19. 답이 갈리는 짝 비교

| 짝 | 차이를 만드는 제약 |
| :--- | :--- |
| SCP 대 IAM policy | IAM policy는 권한을 부여하고 SCP는 상한만 정한다. SCP만으로는 접근이 생기지 않는다 |
| SCP 대 permission boundary | SCP는 조직 트리에 붙어 계정 전체의 상한을 정하고 management account에는 적용되지 않는다. permission boundary는 개별 IAM user와 role에 붙는다. 둘이 동시에 있으면 boundary, SCP, identity policy가 모두 허용해야 통과한다 |
| SCP 대 RCP | SCP는 조직 안 principal을, RCP는 조직 계정이 소유한 리소스를 막는다. RCP는 조직 밖 principal 차단이 가능하고 지원 서비스가 한정되며 AWS managed KMS key에 적용되지 않는다. 둘 다 management account와 service-linked role은 통제하지 못한다 |
| authorization policy 대 declarative policy | SCP와 RCP는 API 수준에서 판정하고 service-linked role을 통제하지 못한다. declarative policy는 control plane에서 구성을 강제하고 SLR도 통제하며 새 API가 추가돼도 baseline이 유지된다 |
| tag policy 대 태그 강제 SCP | tag policy는 이미 붙는 태그의 형식을 표준화하고 비준수 태깅 작업을 실패시킨다. 태그가 없는 리소스는 평가하지 않는다. 생성 차단은 `aws:RequestTag`와 `aws:TagKeys` 조건 SCP가 담당한다 |
| Control Tower 대 Organizations 직접 구성 | Organizations는 정책과 계정 구조를 준다. Control Tower는 그 위에 landing zone, Account Factory, control 카탈로그, drift 탐지를 얹는다. 대신 home Region을 바꿀 수 없고 조직당 landing zone은 1개다 |
| preventive 대 detective 대 proactive | preventive는 SCP/RCP/declarative로 모든 리전에서 사전 차단한다. detective는 Config rule이라 지원 리전에서 사후 탐지한다. proactive는 CloudFormation hook이라 CloudFormation이 프로비저닝하는 리소스만 사전 차단한다 |
| IAM Identity Center 대 SAML 직접 연동 | SAML 직접 연동은 계정마다 IdP를 신뢰 대상으로 등록하고 role을 따로 만든다. Identity Center는 신원 소스를 한 곳에 두고 permission set을 여러 계정에 provisioning한다. 다만 AWS 계정 접근 관리는 organization instance에서만 가능하다 |
| organization instance 대 account instance | organization instance만 AWS 계정 접근을 관리한다. account instance는 일부 AWS managed application의 격리 배포용이다 |
| RAM 공유 대 resource-based policy 공유 | RAM은 OU나 조직 전체를 대상으로 지정할 수 있고 수신 계정에서 자기 리소스처럼 보인다. resource-based policy 공유는 ARN으로 직접 지정하고 그 가시성이 없다 |
| shared VPC 대 Transit Gateway | shared VPC는 라우팅 구성이 없지만 participant가 route table, NACL, NAT gateway, IGW를 만들 수 없고 TGW attach도 owner만 한다. 공유 범위가 같은 조직 안으로 한정된다. TGW는 조직 밖 계정과도 공유되고 route table 분리로 격리를 만든다 |
| organization trail 대 계정별 trail | organization trail은 조직 합류 즉시 자동 로깅되고 멤버 계정이 끄거나 지울 수 없다. 계정별 trail은 계정 관리자가 끌 수 있고 신규 계정마다 구성이 필요하다 |
| all features 대 consolidated billing | 조직 정책 전부가 all features 전용이다. consolidated billing에서 all features로 가는 이동은 단방향이고 초대 계정 전원의 수락이 필요하다 |
| Organizations backup policy 대 계정 내 backup plan | backup policy는 조직 상속으로 effective plan을 만들고 그 plan은 멤버 계정에서 immutable이다. 부분 정책의 합이 필수 요소를 못 채우면 백업이 아예 실행되지 않는다 |
| restricted 대 prioritized 공유 모드 | restricted는 그룹 밖으로 남는 용량도 공유하지 않는다. prioritized는 그룹에 먼저 배정하고 남는 혜택은 조직의 다른 계정으로 흘러간다 |

---

## 20. 그럴듯하지만 성립하지 않는 조합

| 조합 | 성립하지 않는 이유 |
| :--- | :--- |
| management account에 SCP를 붙여 관리자 실수를 막는다 | SCP는 management account의 사용자와 역할에 영향을 주지 않는다. 그 계정에 리소스를 두지 않는 구조가 답이다 |
| SCP로 서비스가 자동 수행하는 작업을 차단한다 | SCP와 RCP 모두 service-linked role을 제한하지 못한다. SLR까지 통제하려면 declarative policy다 |
| SCP만 붙여 특정 팀에 S3 권한을 부여한다 | SCP는 권한을 부여하지 않는다 |
| root에 Deny SCP만 붙이고 나머지는 그대로 둔다 | Allow가 경로의 모든 레벨에 있어야 하므로 `FullAWSAccess`를 지우면 전 서비스가 차단된다 |
| 하위 OU에 Allow SCP를 붙여 상위 OU의 Deny를 예외 처리한다 | Deny는 경로의 어느 레벨에서든 이긴다 |
| SCP의 Allow 문에 특정 버킷 ARN을 적어 그 버킷만 허용한다 | Allow 문의 `Resource`는 `"*"`만 가능하다. 개별 ARN은 Deny 문에서만 쓴다 |
| SCP에 `Principal` 요소를 넣어 특정 role만 예외로 둔다 | SCP는 `Principal`과 `NotPrincipal`을 지원하지 않는다. `aws:PrincipalArn` 조건을 쓴다 |
| consolidated billing 조직에 SCP를 붙여 리전을 제한한다 | SCP, RCP, tag policy, backup policy는 all features 전용이다 |
| delegated administrator 계정은 SCP 적용에서 제외된다 | delegated administrator로 지정된 멤버 계정에도 SCP와 RCP가 그대로 적용된다 |
| RCP로 파트너 계정 소유 버킷에 대한 우리 조직 사용자의 접근을 막는다 | RCP는 리소스를 소유한 계정 경로의 정책만 적용된다. 그 방향은 SCP의 몫이다 |
| RCP로 AWS managed KMS key 접근 조건을 강제한다 | RCP는 AWS managed key에 적용되지 않는다 |
| tag policy를 enforce로 설정해 태그 없는 EC2 인스턴스 생성을 막는다 | tag policy는 태그가 없는 리소스를 평가하지 않는다. 생성 차단은 `aws:RequestTag` 조건 SCP다 |
| shared VPC의 participant가 자기 route table을 만들어 NAT gateway로 뺀다 | participant는 route table을 만들거나 연결할 수 없고 NAT gateway도 만들 수 없다 |
| shared VPC의 participant가 자기 transit gateway attachment를 만든다 | shared subnet에 TGW를 붙이는 것은 VPC owner만 가능하다 |
| RAM으로 서브넷을 조직 밖 파트너 계정과 공유한다 | subnet은 같은 조직 안 계정 및 OU에만 공유된다. default VPC subnet은 아예 공유되지 않는다 |
| RAM으로 서브넷을 특정 IAM role에게만 공유한다 | subnet, transit gateway, prefix list, Resolver rule은 계정과 OU 단위 공유만 가능하다 |
| 멤버 계정 관리자가 organization trail을 잠시 꺼서 로그 노이즈를 줄인다 | 멤버 계정은 organization trail을 보기만 하고 끄거나 바꾸거나 지울 수 없다 |
| management account에서 Event history로 전 조직 이벤트를 본다 | Event history는 로그인한 계정의 이벤트만 보여준다 |
| 규제 요건 때문에 Control Tower home Region을 옮긴다 | home Region은 선택 후 변경할 수 없다 |
| Control Tower governance에서 리전을 빼면 그 리전에 리소스를 만들 수 없다 | 배포는 계속 가능하고 governance 밖에 놓일 뿐이다. 차단은 Region deny control이나 `aws:RequestedRegion` SCP다 |
| Control Tower가 Infrastructure OU와 Workloads OU를 만들어 준다 | 자동 생성되는 것은 Security OU다. Sandbox OU는 선택이고 나머지는 직접 만든다 |
| detective control로 비준수 리소스 생성을 사전 차단한다 | detective는 Config rule 기반 사후 탐지다 |
| landing zone을 최신 버전으로 올리면 mandatory control이 자동으로 다 걸린다 | Landing Zone 4.0부터 mandatory control이 기본 적용되지 않는다 |
| OU를 6단계로 나눠 조직도를 그대로 반영한다 | OU 중첩은 root 아래 5단계까지다 |
| 어제 만든 계정을 조직에서 빼서 단독 계정으로 넘긴다 | 조직 안에서 생성한 계정은 4일이 지나야 제거할 수 있고 support plan과 연락처 검증과 결제 수단이 필요하다 |
| delegated administrator 계정을 조직에서 제거해 정리한다 | 지정을 다른 계정으로 옮기기 전에는 제거할 수 없다 |
| 계정을 조직에서 빼면 권한이 줄어드니 안전하다 | SCP 제한이 사라져 그 계정 principal의 권한이 오히려 넓어질 수 있다 |
| 비용 통제를 위해 all features에서 consolidated billing으로 되돌린다 | 되돌릴 수 없다 |
| 조직 안 계정 전체에 초대 없이 all features를 즉시 적용한다 | 초대로 들어온 계정은 전원이 요청을 수락해야 한다 |
| 멤버 계정에서 cost allocation tag를 활성화한다 | management account 또는 조직에 속하지 않은 단독 계정만 접근한다. 반영에 최대 24시간이 걸린다 |
| Savings Plans를 산 계정을 조직에서 빼도 할인은 유지된다 | 소유 계정이 조직을 떠나면 consolidated bill에 더 이상 적용되지 않는다 |
| payer 계정을 sharing group에 넣어 RI 할인을 우선 배정한다 | payer 계정은 sharing group에 들어갈 수 없고 계정은 그룹 하나에만 속한다 |
| IAM Identity Center account instance로 여러 계정 접근을 관리한다 | AWS 계정 접근 관리는 organization instance만 가능하다 |
| permission set 하나에 managed policy를 30개 붙인다 | 상한은 25개이고 증액할 수 없다. 실제로는 계정의 IAM role 쿼터도 25로 올려야 한다 |
| SCP 정책 타입을 껐다 켜면 원래 부착 상태로 돌아온다 | 재활성화 시 `FullAWSAccess`만 남고 이전 부착 관계는 복구되지 않는다 |

---

## 21. 예상 문제 10문항

**Q1.** 금융사가 AWS Organizations all features 조직에서 100개 계정을 운영합니다. 내부 감사에서 management account에 결제 시스템 EC2와 S3 버킷이 남아 있고, 이 계정의 관리자가 root에 부착한 Deny SCP와 무관하게 리소스를 만들고 지울 수 있다는 지적이 나왔습니다. 조직 정책 체계는 그대로 두어야 하고 구조 조정에 쓸 수 있는 기간은 한 분기입니다. 감사 지적을 해소하는 MOST effective approach는 무엇입니까?

- A. management account에 Deny SCP를 직접 부착하고 관리자 IAM user에 permission boundary를 건다
- B. management account를 조직 서비스의 delegated administrator로 지정해 SCP 적용 대상에 포함시킨다
- C. AWS Control Tower를 도입하고 mandatory control을 management account에 적용한다
- D. 결제 워크로드를 전용 멤버 계정으로 옮기고 management account에는 조직 관리 기능만 남긴다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: D**

SCP는 management account의 사용자와 역할에 영향을 주지 않습니다. 정책으로 막을 수 없는 계정이므로 그 계정에 통제 대상 리소스를 두지 않는 구조가 유일한 해법이고, AWS 공식 문서도 management account에 리소스를 두지 말라고 권고하면서 같은 이유를 근거로 듭니다.

- A가 틀린 이유: SCP를 management account에 붙여도 그 계정의 principal에는 적용되지 않는다. permission boundary는 관리자가 스스로 떼어낼 수 있으므로 감사 요구를 만족하지 못한다.
- B가 틀린 이유: delegated administrator는 멤버 계정에 부여하는 지정이다. management account를 자신의 delegated administrator로 지정하는 개념이 없고, 지정한다고 SCP 적용 예외가 사라지지도 않는다.
- C가 틀린 이유: Control Tower의 preventive control은 SCP, RCP, declarative policy로 구현되므로 management account 예외를 그대로 물려받는다. Landing Zone 4.0부터 mandatory control이 기본 적용되지도 않는다.

</details>

**Q2.** SaaS 기업이 조직 안 200개 계정에서 S3 버킷을 운영합니다. 각 팀이 자기 버킷 정책을 직접 관리하는데, 감사에서 조직 밖 계정 ARN이 principal로 들어간 버킷이 분기마다 반복 발견되었습니다. 팀의 버킷 정책 관리 권한은 회수하지 않은 채 조직 밖 principal의 접근만 조직 전체에서 일괄 차단해야 합니다. LEAST operational overhead 구성은 무엇입니까?

- A. 조직 root에 `aws:PrincipalOrgID` 조건으로 조직 밖 principal의 S3 접근을 Deny하는 resource control policy를 부착한다
- B. 조직 root에 같은 조건의 service control policy를 부착한다
- C. CloudFormation StackSets로 모든 계정의 버킷에 표준 버킷 정책을 배포하고 drift를 주기 점검한다
- D. IAM Access Analyzer external access analyzer를 계정마다 만들고 finding을 EventBridge로 받아 자동 교정한다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: A**

RCP는 조직 멤버 계정이 소유한 리소스에 적용되어 조직 밖 principal의 접근을 막습니다. 리소스를 소유한 계정 경로의 RCP가 적용되므로 팀이 버킷 정책을 어떻게 쓰든 조직 경계 밖 접근은 차단되고, 팀의 정책 관리 권한은 그대로 남습니다.

- B가 틀린 이유: SCP는 조직 멤버 계정 안의 principal을 제한한다. 조직 밖 계정의 사용자에게는 적용되지 않으므로 이 방향의 접근을 막지 못한다.
- C가 틀린 이유: 팀이 버킷 정책을 계속 관리하는 전제이므로 배포한 정책이 곧 덮어써진다. drift 점검은 사후 탐지라 차단이 아니다.
- D가 틀린 이유: external access analyzer는 열린 접근을 탐지할 뿐 차단하지 않는다. 리전마다 analyzer를 만들어야 해서 운영 부담도 가장 크다.

</details>

**Q3.** 제조사가 200개 계정에서 EC2 인스턴스가 사용할 수 있는 AMI를 표준 목록으로 제한하려 합니다. 요구는 세 가지입니다. service-linked role이 수행하는 작업에도 동일하게 적용되어야 하고, EC2가 새 API를 추가해도 선언한 baseline 구성이 유지되어야 하며, 정책을 분리하면 속성이 부착 이전 상태로 되돌아가야 합니다. 요구를 모두 만족하는 MOST appropriate Organizations 정책 타입은 무엇입니까?

- A. `ec2:RunInstances`에 `ec2:ImageId` 조건을 건 service control policy
- B. 허용 AMI ID를 값 목록으로 정의한 tag policy
- C. EC2 Allowed Images Settings를 선언하는 declarative policy
- D. AMI 공유 계정을 제한하는 resource control policy

<details markdown="1">
<summary>정답과 해설</summary>

**정답: C**

declarative policy는 서비스의 control plane에서 강제되는 정책 층입니다. 공식 문서의 비교표가 declarative policy만 service-linked role을 통제한다고 명시하고, 서비스가 새 API를 추가해도 선언한 구성이 유지되며, 정책을 분리하면 속성이 부착 이전 상태로 롤백된다고 설명합니다. EC2 Allowed Images Settings가 문서의 대표 용례입니다.

- A가 틀린 이유: SCP는 service-linked role이 수행하는 작업에 영향을 주지 않는다. 새 API가 추가되면 조건을 다시 써야 하므로 baseline 유지 요구도 만족하지 못한다.
- B가 틀린 이유: tag policy는 태그 키의 대소문자와 허용 값을 표준화하는 정책이다. AMI 선택을 통제하는 기능이 없다.
- D가 틀린 이유: RCP는 조직 밖 principal의 리소스 접근을 제한하는 정책이고 service-linked role의 호출에 적용되지 않는다. 자기 계정 안에서 어떤 AMI를 쓰는지와 무관하다.

</details>

**Q4.** 비용 배분을 위해 신규 리소스 전부에 `CostCenter` 태그를 강제하려 합니다. 조직 root에 tag policy를 부착하고 EC2 인스턴스 리소스 타입에 enforcement 옵션까지 켰는데도 태그 없이 생성된 인스턴스가 계속 나타납니다. 태그 키의 대소문자 표준화 효과는 유지하면서 태그 없는 생성을 실제로 차단해야 합니다. MOST appropriate 조치는 무엇입니까?

- A. tag policy의 enforcement 대상 리소스 타입을 EC2 volume과 network interface까지 넓힌다
- B. AWS Config의 `required-tags` 규칙과 자동 교정 액션을 조직 전체에 배포한다
- C. tag policy를 declarative policy로 교체해 control plane에서 태그를 강제한다
- D. tag policy는 그대로 두고 `aws:RequestTag`와 `aws:TagKeys` 조건으로 태그 없는 생성을 Deny하는 SCP를 함께 부착한다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: D**

tag policy는 태그가 없는 리소스와 정책에 정의되지 않은 태그를 아예 평가하지 않습니다. enforcement 옵션은 지정한 리소스 타입에 대한 비준수 태깅 작업을 실패시키는 기능이지 리소스 생성 자체를 막는 기능이 아닙니다. 생성 시점 차단은 `aws:RequestTag`와 `aws:TagKeys` 조건을 쓴 SCP의 몫이고, 두 정책을 함께 두면 표준화와 차단을 모두 얻습니다.

- A가 틀린 이유: 대상 리소스 타입을 넓혀도 태그가 없는 리소스는 평가 대상이 아니라는 제약이 그대로다.
- B가 틀린 이유: Config 규칙은 생성 이후 탐지와 교정이라 태그 없는 리소스가 일단 만들어진다. 요구는 생성 차단이다.
- C가 틀린 이유: declarative policy가 지원하는 baseline 항목에 범용 태그 강제가 없고, 태그 키 표준화 기능도 tag policy가 담당한다.

</details>

**Q5.** 60개 계정 조직의 중앙 보안팀이 전 계정 API 활동 로그를 단일 S3 버킷으로 모으려 합니다. 요구는 두 가지입니다. 멤버 계정 관리자가 로깅을 끄거나 trail을 삭제할 수 없어야 하고, 신규 계정이 조직에 합류하면 추가 작업 없이 로깅이 시작되어야 합니다. 계정마다 사람이 개입하는 절차는 허용되지 않습니다. LEAST operational overhead 구성은 무엇입니까?

- A. 계정마다 trail을 만들어 중앙 버킷을 대상으로 지정하고 신규 계정 온보딩 절차에 이 단계를 넣는다
- B. management account 또는 CloudTrail delegated administrator 계정에서 organization trail을 만들어 중앙 버킷에 기록한다
- C. CloudFormation StackSets의 service-managed 권한 모델로 계정별 trail을 배포하고 automatic deployment를 켠다
- D. management account에서 CloudTrail Event history를 조회하고 결과를 주기적으로 S3에 내보낸다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: B**

organization trail은 계정이 조직에 합류하는 순간 그 계정에 trail과 service-linked role이 추가되어 자동으로 로깅이 시작됩니다. 멤버 계정의 CloudTrail 권한 보유자는 organization trail을 목록에서 볼 수는 있어도 삭제하거나 로깅을 끄거나 기록 이벤트 타입을 바꿀 수 없습니다. 두 요구를 하나의 리소스로 동시에 만족합니다.

- A가 틀린 이유: 계정별 trail은 그 계정 관리자가 끄거나 지울 수 있고 신규 계정마다 구성 단계가 필요하다.
- C가 틀린 이유: automatic deployment로 배포는 자동화되지만 배포된 trail은 여전히 멤버 계정 소유라 계정 관리자가 변경할 수 있다.
- D가 틀린 이유: Event history는 로그인한 계정의 이벤트만 보여준다. management account로 로그인해도 멤버 계정 이벤트는 나오지 않는다.

</details>

**Q6.** 네트워크팀이 소유한 VPC의 서브넷을 AWS RAM으로 같은 조직 안 애플리케이션 팀 계정 다섯 개에 공유했습니다. 애플리케이션 팀은 공유 서브넷에서 워크로드를 운영해야 하고, 네트워크팀은 라우팅과 인터넷 경로를 계속 독점 관리해야 합니다. 이 구성에서 participant 계정이 스스로 수행할 수 있는 작업 두 가지는 무엇입니까? (Select TWO.)

- A. 공유 서브넷에 EC2 인스턴스와 ALB를 배포하고 자기 계정 소유의 security group을 만든다
- B. 자기 워크로드 전용 route table을 만들어 공유 서브넷에 연결한다
- C. 공유 서브넷에 NAT gateway를 만들어 자기 팀 아웃바운드 경로를 분리한다
- D. 자기 security group 규칙에서 owner 계정의 security group을 `account-number/security-group-id` 형식으로 참조한다
- E. 공유 서브넷을 대상으로 transit gateway attachment를 만든다
- F. VPC의 default security group을 그대로 사용해 인스턴스를 기동한다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: A, D**

participant가 공유 서브넷에서 만들 수 있는 것은 network interface와 security group, 그리고 자기가 소유한 ENI의 flow log입니다. 그 리소스는 participant 계정의 VPC 쿼터를 소비합니다. 또한 participant는 자기 security group 규칙에서 다른 participant나 owner의 security group을 `account-number/security-group-id` 형식으로 참조할 수 있습니다.

- B가 틀린 이유: participant는 route table을 만들거나 삭제하거나 연결할 수 없고 조회만 가능하다. 라우팅은 owner의 책임이다.
- C가 틀린 이유: participant는 NAT gateway를 생성, 삭제, 조회할 수 없다. IGW도 조회만 가능하다.
- E가 틀린 이유: 공유 서브넷에 transit gateway를 붙일 수 있는 것은 VPC owner뿐이다.
- F가 틀린 이유: default security group은 owner 소유이므로 participant가 그것으로 인스턴스를 띄울 수 없다. 별도로 공유받지 않은 owner 소유 non-default security group도 쓸 수 없다.

</details>

**Q7.** 파트너사와 공동 개발을 위해 자사 조직 밖에 있는 파트너 AWS 계정과 네트워크를 연결해야 합니다. 파트너는 자기 계정 VPC의 워크로드를 자사 워크로드와 통신시켜야 하고, 자사 네트워크팀은 경로 통제권을 계속 유지해야 합니다. 파트너 계정을 자사 조직에 편입시키는 선택지는 없고, 파트너가 자기 계정에서 리소스를 직접 관리해야 합니다. AWS RAM으로 성립하는 MOST appropriate 구성은 무엇입니까?

- A. 자사 VPC의 서브넷을 파트너 계정에 공유하고 파트너가 그 서브넷에 워크로드를 배포한다
- B. 자사 transit gateway를 파트너 계정에 공유하고 파트너가 자기 VPC attachment를 만들며, 자사는 TGW route table로 도달 범위를 제한한다
- C. 자사 VPC의 security group을 파트너 계정에 공유해 파트너 인스턴스가 그것을 참조하게 한다
- D. 자사 prefix list를 파트너 계정에 공유하면 그 목록의 CIDR로 통신 경로가 생성된다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: B**

transit gateway는 조직 밖 AWS 계정과도 공유할 수 있는 리소스입니다. 조직 밖 공유는 초대 절차가 시작되어 파트너가 수락해야 하고, 수락 후 파트너는 자기 VPC attachment를 만들 수 있습니다. 자사는 TGW route table을 분리해 파트너 attachment가 도달할 수 있는 범위를 제한하므로 경로 통제권이 유지됩니다.

- A가 틀린 이유: subnet은 같은 조직 안 계정과 OU에만 공유할 수 있다. 조직 밖 계정과는 공유 자체가 성립하지 않는다.
- C가 틀린 이유: security group도 조직 안으로 공유 대상이 한정되고, security group 공유만으로는 네트워크 경로가 생기지 않는다.
- D가 틀린 이유: prefix list는 조직 밖 공유가 가능하지만 CIDR 묶음일 뿐이라 그 자체로 연결을 만들지 않는다. 라우팅 대상이 별도로 필요하다.

</details>

**Q8.** 스타트업이 consolidated billing features 모드로만 운영하던 조직에 규제 대응으로 리전 제한과 태그 표준화를 도입하려 합니다. 조직에는 초대로 합류한 계정 12개와 Organizations로 생성한 계정 4개가 있습니다. 경영진은 도입 이후에도 언제든 이전 상태로 되돌릴 수 있어야 한다는 조건을 붙였습니다. 이 상황에 대한 MOST accurate 판단은 무엇입니까?

- A. all features로 전환하면 SCP와 tag policy를 쓸 수 있고 필요하면 consolidated billing으로 되돌릴 수 있다
- B. Organizations로 생성한 계정 4개만 수락하면 all features 전환이 완료되고 초대 계정은 자동 전환된다
- C. 초대로 합류한 12개 계정이 모두 요청을 수락해야 all features 전환이 완료되고, 전환은 단방향이므로 되돌릴 수 있어야 한다는 조건을 충족할 수 없다
- D. consolidated billing 모드에서도 SCP와 tag policy를 부착할 수 있으므로 전환 없이 요구를 만족한다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: C**

all features 활성화 요청은 초대로 들어온 계정 전원이 수락해야 완료됩니다. Organizations로 생성한 계정은 요청을 받지 않습니다. 그리고 consolidated billing features에서 all features로 가는 이동은 단방향이라 되돌릴 수 없으므로, 원복 가능성을 요구 조건으로 둔 채로는 이 전환을 승인할 수 없습니다.

- A가 틀린 이유: 되돌리기가 불가능하다. all features에서 consolidated billing features로 내려가는 경로가 없다.
- B가 틀린 이유: 수락이 필요한 쪽은 초대 계정이고, 생성 계정은 요청을 받지 않는다. 설명이 정반대다.
- D가 틀린 이유: SCP, RCP, tag policy, backup policy는 모두 all features 전용이다.

</details>

**Q9.** 조직의 management account가 Compute Savings Plans를 구매해 조직 전체에서 할인을 공유하고 있습니다. 재무팀은 프로덕션 계정 묶음에만 할인을 배정하고, 커밋먼트에 여유가 생기더라도 샌드박스 계정으로는 혜택이 흘러가지 않기를 원합니다. 계정별로 별도 Savings Plans를 사는 방식은 관리 부담 때문에 배제되었습니다. 요구를 만족하는 MOST appropriate 구성은 무엇입니까?

- A. AWS Cost Categories로 프로덕션 계정 그룹을 정의하고 restricted 공유 모드를 적용한다
- B. 같은 그룹을 정의하고 prioritized 공유 모드를 적용한다
- C. management account를 sharing group에 넣어 우선순위 최상단에 배치한다
- D. 샌드박스 계정을 조직에서 분리해 별도 조직으로 옮긴다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: A**

RI와 Savings Plans 할인 공유 모드는 organization-wide, prioritized group, restricted group 셋입니다. restricted 모드는 지정한 그룹 밖으로는 남는 용량이 있어도 공유하지 않으므로 샌드박스 계정 차단 요구를 만족합니다. 그룹은 AWS Cost Categories의 Accounts 차원으로 정의합니다.

- B가 틀린 이유: prioritized 모드는 지정 그룹에 먼저 배정할 뿐 남는 혜택은 조직의 다른 계정으로 흘러간다. 샌드박스 차단 요구를 만족하지 못한다.
- C가 틀린 이유: payer 계정은 sharing group에 들어갈 수 없다. 계정은 그룹 하나에만 속할 수 있다.
- D가 틀린 이유: 계정을 조직에서 빼면 consolidated billing 대상에서 벗어나 SCP 통제도 사라지고, 그 계정 principal의 권한이 오히려 넓어질 수 있다. 요구 대비 부작용이 크다.

</details>

**Q10.** AWS Control Tower로 landing zone을 운영하는 조직이 데이터 주권 요건 때문에 지정한 리전에서만 리소스를 운영해야 합니다. 담당자는 governance 대상 리전 목록에서 해당 리전들만 남겼습니다. 감사팀은 목록 밖 리전에 리소스가 만들어지는 것을 실제로 차단하라고 요구하고, 별도로 home Region을 규제 대상 리전으로 옮겨 달라는 요청도 들어왔습니다. MOST accurate 판단은 무엇입니까?

- A. governance 목록에서 제외하면 그 리전에 리소스를 만들 수 없고, home Region은 landing zone을 재배포하면 옮길 수 있다
- B. governance 목록 조정만으로 차단이 되지만 home Region은 옮길 수 없다
- C. 차단하려면 detective control을 추가해야 하고, home Region은 OU 재등록으로 옮길 수 있다
- D. governance에서 제외해도 배포 자체는 막히지 않으므로 Region deny control이나 `aws:RequestedRegion` 조건 SCP가 필요하고, home Region은 선택 후 변경할 수 없다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: D**

어떤 리전을 governance에서 빼도 그 리전에 리소스를 배포하는 것 자체는 막히지 않습니다. 그 리소스가 Control Tower governance 밖에 놓일 뿐입니다. 실제 차단은 preventive 층인 Region deny control이나 `aws:RequestedRegion` 조건을 쓴 SCP가 담당합니다. home Region은 landing zone을 만들 때 콘솔에 접속해 있던 리전으로 정해지고 이후 변경할 수 없습니다.

- A가 틀린 이유: 두 문장 모두 반대다. governance 제외는 차단이 아니고 home Region은 재배포 여부와 무관하게 변경 대상이 아니다.
- B가 틀린 이유: home Region 판단은 맞지만 governance 목록 조정이 차단이라는 전제가 틀렸다.
- C가 틀린 이유: detective control은 Config rule 기반 사후 탐지라 사전 차단이 아니다. OU 재등록은 새 리전을 추가했을 때 계정을 갱신하는 절차이지 home Region 변경 절차가 아니다.

</details>

---

## 22. Reference

- [AWS Organizations - What is AWS Organizations?](https://docs.aws.amazon.com/organizations/latest/userguide/orgs_introduction.html)
- [AWS Organizations - Quotas for AWS Organizations](https://docs.aws.amazon.com/organizations/latest/userguide/orgs_reference_limits.html)
- [AWS Organizations - Service control policies](https://docs.aws.amazon.com/organizations/latest/userguide/orgs_manage_policies_scps.html)
- [AWS Organizations - SCP evaluation](https://docs.aws.amazon.com/organizations/latest/userguide/orgs_manage_policies_scps_evaluation.html)
- [AWS Organizations - SCP syntax](https://docs.aws.amazon.com/organizations/latest/userguide/orgs_manage_policies_scps_syntax.html)
- [AWS Organizations - Resource control policies](https://docs.aws.amazon.com/organizations/latest/userguide/orgs_manage_policies_rcps.html)
- [AWS Organizations - Declarative policies](https://docs.aws.amazon.com/organizations/latest/userguide/orgs_manage_policies_declarative_policies.html)
- [AWS Organizations - Tag policies](https://docs.aws.amazon.com/organizations/latest/userguide/orgs_manage_policies_tag-policies.html)
- [AWS Organizations - Backup policies](https://docs.aws.amazon.com/organizations/latest/userguide/orgs_manage_policies_backup.html)
- [AWS Organizations - AI services opt-out policies](https://docs.aws.amazon.com/organizations/latest/userguide/orgs_manage_policies_ai-opt-out.html)
- [AWS Organizations - Enabling all features in your organization](https://docs.aws.amazon.com/organizations/latest/userguide/orgs_manage_org_support-all-features.html)
- [AWS Organizations - Removing a member account from your organization](https://docs.aws.amazon.com/organizations/latest/userguide/orgs_manage_accounts_remove.html)
- [AWS Organizations - Delegated administrator for policy management](https://docs.aws.amazon.com/organizations/latest/userguide/orgs_delegate_policies.html)
- [AWS Control Tower - What is AWS Control Tower?](https://docs.aws.amazon.com/controltower/latest/userguide/what-is-control-tower.html)
- [AWS Control Tower - Control behavior and guidance](https://docs.aws.amazon.com/controltower/latest/controlreference/control-behavior.html)
- [AWS Control Tower - How AWS Regions work with AWS Control Tower](https://docs.aws.amazon.com/controltower/latest/userguide/region-how.html)
- [AWS Control Tower - Planning your AWS Control Tower deployment](https://docs.aws.amazon.com/controltower/latest/userguide/planning-your-deployment.html)
- [AWS Control Tower - The AWS Control Tower landing zone](https://docs.aws.amazon.com/controltower/latest/userguide/aws-multi-account-landing-zone.html)
- [AWS Whitepapers - Foundational OUs](https://docs.aws.amazon.com/whitepapers/latest/organizing-your-aws-environment/foundational-ous.html)
- [AWS RAM - What is AWS Resource Access Manager?](https://docs.aws.amazon.com/ram/latest/userguide/what-is.html)
- [AWS RAM - Shareable AWS resources](https://docs.aws.amazon.com/ram/latest/userguide/shareable.html)
- [Amazon VPC - Share your VPC with other accounts](https://docs.aws.amazon.com/vpc/latest/userguide/vpc-sharing.html)
- [Amazon VPC - VPC sharing limitations](https://docs.aws.amazon.com/vpc/latest/userguide/vpc-share-limitations.html)
- [AWS CloudTrail - Creating a trail for an organization](https://docs.aws.amazon.com/awscloudtrail/latest/userguide/creating-trail-organization.html)
- [AWS CloudTrail - Delegated administrator](https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-delegated-administrator.html)
- [AWS IAM Identity Center - What is IAM Identity Center?](https://docs.aws.amazon.com/singlesignon/latest/userguide/what-is.html)
- [AWS IAM Identity Center - Quotas](https://docs.aws.amazon.com/singlesignon/latest/userguide/limits.html)
- [AWS IAM - IAM and AWS STS quotas](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_iam-quotas.html)
- [AWS CloudFormation - What is AWS CloudFormation StackSets?](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/what-is-cfnstacksets.html)
- [AWS Billing - Turning off shared reserved instances and Savings Plans discounts](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/ri-turn-off.html)
- [AWS Billing - Using AWS cost allocation tags](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/cost-alloc-tags.html)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
