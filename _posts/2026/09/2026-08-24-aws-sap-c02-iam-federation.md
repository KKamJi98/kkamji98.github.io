---
title: "SAP-C02 박살내기 2 - IAM과 페더레이션"
date: 2026-08-24 10:00:00 +0900
author: kkamji
categories: [Certification, AWS SAP-C02]
tags: [aws, sap-c02, certification, iam, sts, saml, federation, permission-boundary, abac, directory-service]
comments: true
image:
  path: /assets/img/aws/aws.webp
---

같은 계정 안에서 정책 구성을 똑같이 맞춰 놓고 secret 하나를 읽게 했는데 principal 종류에 따라 결과가 갈리는 상황이 있습니다. permission boundary에는 Secrets Manager 액션이 한 줄도 없고, identity-based policy에도 없으며, secret의 resource policy만 `secretsmanager:GetSecretValue`를 허용합니다. principal이 IAM user면 호출이 성공하고, 같은 구성을 IAM role로 바꾸면 `AccessDenied`가 납니다.

정책 문서 세 개는 글자 하나 바뀌지 않았습니다. 달라진 것은 resource policy가 권한을 준 ARN의 종류뿐입니다. boundary의 implicit deny가 resource-based policy를 제한하는지가 그 ARN에 달려 있고, IAM user ARN에 직접 준 권한은 제한하지 않지만 role ARN에 준 권한은 제한합니다.

SAP-C02 Domain 1은 이 층에서 답이 갈리는 문항을 냅니다. 하나의 API 호출에는 identity-based policy, resource-based policy, permission boundary, SCP, RCP, session policy 여섯 종류가 함께 걸리고, 각각이 평가되는 순서와 각각이 통제하지 **못하는** 대상이 따로 있습니다. 여기에 외부 신원이 STS를 거쳐 그 경로로 들어오는 방식이 얹힙니다. 서비스 이름을 아는 것으로는 선지가 좁혀지지 않습니다.

> **TL;DR**  
> - 평가 순서는 Deny evaluation, RCP, SCP, resource-based policy, identity-based policy, permissions boundary, session policy 일곱 단계다.  
> - 요청은 기본적으로 implicit deny다. root user의 기본 권한은 이 기본 거부의 예외이며, 요청에 적용되는 explicit Deny가 있으면 거부된다. member account의 root user도 SCP의 제한을 받는다.  
> - 같은 계정에서 identity-based policy와 resource-based policy는 합집합이고, identity-based policy와 permissions boundary는 교집합이다.  
> - boundary의 implicit deny는 resource-based policy가 role ARN에 권한을 준 경우만 제한한다. IAM user ARN, role session ARN, federated user ARN에 직접 주면 제한하지 않는다.  
> - role trust policy와 KMS key policy는 principal에 대한 explicit Allow가 반드시 있어야 접근이 성립한다.  
> - `AssumeRole`의 상한은 12시간이고 role chaining은 CLI와 API 세션을 1시간으로 자른다. 36시간은 `GetFederationToken`과 `GetSessionToken`의 상한이다.  
> - session policy는 role 권한과의 교집합이라 권한을 넓히지 못한다. plaintext 2,048자를 지켜도 packed size 때문에 실패할 수 있다.  
> - external ID는 서드파티가 고객마다 유일하게 생성한다. 비밀이 아니고 값의 통제 주체가 방어 원리다.  
> - session tag를 넘기려면 trust policy에 `sts:TagSession`이 필요하고 콘솔 Switch Role로는 넘길 수 없다.  
> - unused access analyzer는 리전마다 만들 필요가 없다. 리전마다 필요한 것은 external access analyzer다.  
{: .prompt-info}

---

## 1. 하나의 요청에 여섯 종류의 정책이 걸린다

AWS가 요청을 인가할 때 보는 정책은 여섯 종류입니다. 각각 부착 대상과 역할이 다르고, 권한을 실제로 부여하는 것은 그중 둘뿐입니다.

| 정책 타입 | 부착 대상 | 권한 부여 | 평가에서의 역할 | 결정적 제약 |
| :--- | :--- | :--- | :--- | :--- |
| identity-based policy | user, group, role | 부여한다 | 5단계에서 allow가 있어야 한다 | group에 부착할 수 있는 유일한 타입 |
| resource-based policy | S3, SQS, KMS, Secrets Manager 등 리소스 | 부여한다 | 4단계. principal 종류에 따라 이후 단계를 우회한다 | role trust policy와 KMS key policy는 explicit Allow 필수 |
| permissions boundary | user와 role만 | 부여하지 않는다 | 6단계에서 상한을 건다 | group을 지원하지 않는다 |
| SCP | root, OU, account | 부여하지 않는다 | 3단계. 계정 안 principal에 적용된다 | management account에는 적용되지 않는다 |
| RCP | root, OU, account | 부여하지 않는다 | 2단계. 계정이 소유한 리소스에 적용된다 | `RCPFullAWSAccess`가 항상 붙어 있고 분리할 수 없다 |
| session policy | 세션 자체(런타임 파라미터) | 부여하지 않는다 | 7단계 | inline 1개와 managed ARN 10개, 합쳐 2,048자 |

SCP와 RCP가 조직 트리의 어디에 붙고 OU를 어떻게 설계하는지는 [멀티 계정 거버넌스 편](/posts/aws-sap-c02-multi-account-governance/)에서 다뤘습니다. 여기서는 그 두 가지를 조직 설계의 대상이 아니라 하나의 요청을 판정하는 항으로만 봅니다.

권한을 부여하는 것은 identity-based policy와 resource-based policy 둘뿐입니다. 나머지 넷은 상한만 정합니다. "permission boundary를 붙였으니 그 범위의 권한이 생겼다"는 서술은 성립하지 않고, 같은 이유로 SCP만 붙여서는 어떤 접근도 생기지 않습니다.

---

## 2. 평가 순서 일곱 단계와 요청이 탈락하는 지점

요청이 들어오면 AWS는 인증을 마친 뒤 request context를 만들고, 그 컨텍스트에 적용되는 정책들을 평가합니다. 기본값은 implicit deny이고 필요한 Allow가 있어야 접근이 성립합니다. AWS account root user는 별도 IAM 정책 없이 기본 권한을 갖지만, 요청에 적용되는 explicit Deny가 있으면 거부됩니다. 예를 들어 Organizations member account의 root user도 해당 계정에 적용되는 SCP의 제한을 받습니다.

{% include diagrams/static/sap-c02/iam-policy-evaluation-order.html %}

그림은 좌상단의 API 요청에서 출발한 일곱 단계를 오른쪽으로 갔다가 아래에서 되돌아오는 형태로 접어 놓은 배치입니다. 윗줄은 왼쪽에서 오른쪽으로 1. Deny evaluation, 2. RCP, 3. SCP 순으로 가고, 3에서 아래로 꺾여 아랫줄로 내려온 다음 진행 방향이 반대가 됩니다. 아랫줄은 오른쪽에서 왼쪽으로 4. resource-based policy, 5. identity-based policy, 6. permissions boundary 순으로 돌아오고, 6에서 다시 아래로 내려가 7. session policy를 지나 오른쪽의 초록색 허용 상자에 도달합니다. 일곱 단계를 모두 통과한 요청만 이 상자에 도착합니다.

빠져나가는 경로는 점선 하나입니다. 1. Deny evaluation 상자 아래에서 시작한 점선이 두 줄을 가로질러 내려간 뒤 오른쪽으로 꺾여 오른쪽 아래의 거부 상자로 향합니다. 첫 단계에서 explicit Deny를 만난 요청이 나머지 여섯 단계를 보지 않고 끝나는 경로입니다. 다만 거부 상자에 적힌 사유는 두 가지이고, explicit Deny 말고도 어느 단계에서든 필요한 Allow가 없으면 implicit deny로 같은 자리에 도달합니다. 상자 안의 부제도 함께 읽을 값입니다. 2. RCP에는 `RCPFullAWSAccess`가 항상 붙어 있다는 사실이, 4. resource-based policy에는 그 정책이 지목한 ARN 종류가 뒤 단계를 바꾼다는 사실이 적혀 있고 각각 아래 두 절에서 다룹니다.

순서를 문장으로 옮기면 다음과 같습니다.

1. **Deny evaluation.** 여섯 타입 전부에서 explicit Deny를 찾는다. 있으면 즉시 거부다.
2. **RCP.** 리소스를 소유한 계정 경로의 RCP를 본다. RCP를 활성화하면 AWS managed policy `RCPFullAWSAccess`가 root, 각 OU, 각 계정에 자동으로 붙고 분리할 수 없으므로 이 단계에는 항상 Allow statement가 존재한다.
3. **SCP.** 요청을 보낸 principal이 속한 계정 경로의 SCP를 본다. Allow가 경로의 모든 레벨에 있어야 통과한다.
4. **resource-based policy.** 대상 리소스에 붙은 정책을 본다. 여기서 principal에게 권한이 성립하면 이후 단계의 처리가 달라진다.
5. **identity-based policy.** principal에 붙은 정책에 Allow가 있는지 본다.
6. **permissions boundary.** boundary가 있으면 그 안에 Allow가 있어야 한다. 세션 principal이 아니면 이 단계를 통과한 시점에 최종 Allow다.
7. **session policy.** 세션 principal만 평가한다. 세션을 만들 때 session policy를 넘기지 않았다면 기본 session policy가 만들어져 Allow가 된다.

시험에서 실제로 답을 가르는 것은 순서 자체보다 두 가지입니다. 첫째, explicit Deny는 어느 타입에 있든 이깁니다. "하위 OU에서 허용했으니 상위의 Deny를 뒤집는다"나 "버킷 정책이 허용하니 boundary의 Deny를 넘는다"는 성립하지 않습니다. 둘째, 6단계까지 온 요청이 세션인지 아닌지에 따라 마지막 처리가 갈립니다.

---

## 3. 합집합이 되는 조합과 교집합이 되는 조합

정책 타입 여섯 개가 결합할 때 어떤 조합은 합집합이고 어떤 조합은 교집합입니다. 이 규칙이 문항의 계산식입니다.

| 조합 | 결과 권한 | 의미 |
| :--- | :--- | :--- |
| identity-based policy + resource-based policy (같은 계정) | 합집합 | 둘 중 하나만 allow해도 허용된다 |
| identity-based policy + permissions boundary | 교집합 | 둘 다 allow해야 허용된다 |
| identity-based policy + SCP + RCP (resource-based policy 없음) | 교집합 | 세 타입 모두가 allow해야 허용된다 |
| role 권한 + session policy | 교집합 | session policy는 권한을 넓히지 못한다 |

같은 계정에서 identity와 resource 두 정책이 합집합이라는 점은 오답 선지를 만드는 재료가 됩니다. "버킷 정책에서 principal을 지웠으니 접근이 끊긴다"는 판단은 그 principal의 identity policy에 같은 권한이 있으면 틀립니다.

여기에 예외가 두 개 있습니다. **IAM role trust policy와 KMS key policy는 principal에 대한 explicit Allow가 반드시 있어야 접근이 성립합니다.** identity policy가 `sts:AssumeRole`을 아무리 넓게 허용해도 대상 role의 trust policy가 그 principal을 명시적으로 신뢰하지 않으면 가정이 되지 않습니다. IAM과 KMS 외 서비스의 resource-based policy도 같은 계정 안에서 explicit Allow를 요구할 수 있습니다.

교차 계정 요청은 규칙이 다릅니다. 계정 경계를 넘는 접근은 호출자 계정의 identity-based policy와 대상 계정의 resource-based policy가 **둘 다** 허용해야 성립합니다. 한쪽만으로는 계정 경계를 넘지 못합니다.

---

## 4. resource-based policy가 어떤 ARN에 권한을 주었는지가 결과를 바꾼다

같은 계정 안에서 resource-based policy가 권한을 주면, 그 권한이 permissions boundary와 session policy의 implicit deny에 걸리는지가 **정책이 지목한 ARN의 종류**에 따라 달라집니다. 도입부의 IAM user와 role 차이가 여기서 나옵니다.

| resource-based policy가 지목한 ARN | 예시 | boundary와 session policy의 implicit deny |
| :--- | :--- | :--- |
| IAM user ARN | `arn:aws:iam::111122223333:user/exampleuser` | 제한하지 않는다 |
| role session ARN | `arn:aws:sts::111122223333:assumed-role/examplerole/examplerolesessionname` | 제한하지 않는다 |
| federated user ARN | `arn:aws:sts::111122223333:federated-user/exampleuser` | 제한하지 않는다 |
| role ARN | `arn:aws:iam::111122223333:role/examplerole` | **제한한다** |
| `Principal: "*"` + `aws:PrincipalArn` wildcard | 조건 키로 범위 지정 | 제한하지 않는다. identity-based policy의 explicit deny만 막는다 |

`GetFederationToken`으로 만든 세션도 같은 규칙을 따릅니다. federated user ARN에 직접 권한을 주면 제한되지 않지만, 연합을 수행한 IAM user ARN에 권한을 주면 boundary와 session policy의 implicit deny에 걸립니다.

**explicit deny는 이 표와 무관합니다.** boundary가 특정 액션을 명시적으로 Deny하면 resource-based policy가 어떤 ARN에 무엇을 허용했든 차단됩니다. 표가 다루는 것은 boundary가 그 액션을 **언급하지 않았을 때**의 implicit deny입니다.

공식 문서가 드는 예시로 정리하면 이렇습니다. 주체는 IAM user이고 boundary는 S3 로그 버킷 ARN에 `s3:*`를 explicit Deny합니다. Secrets Manager는 boundary에 언급이 없고 identity policy에도 없습니다. 이 상태에서 로그 버킷의 버킷 정책이 이 user ARN에 `s3:GetObject`를 허용해도 boundary의 explicit deny가 이겨 차단됩니다. 반면 secret의 resource policy가 같은 user ARN에 `secretsmanager:GetSecretValue`를 허용하면 boundary의 implicit deny에 걸리지 않아 호출이 성공합니다. 같은 시나리오에서 주체를 role로 바꾸면 `GetSecretValue`도 차단됩니다.

여기서 파생되는 함정이 하나 더 있습니다. resource-based policy에서 `NotPrincipal`과 `Deny`를 함께 쓰면, boundary가 붙은 IAM principal은 `NotPrincipal`에 무엇을 적었든 항상 deny됩니다. 특정 principal만 예외로 두려면 `ArnNotEquals` 연산자와 `aws:PrincipalArn` 조건 키를 씁니다.

---

## 5. permission boundary는 권한을 주지 않고 상한만 정한다

permissions boundary는 IAM user와 role에 붙여 그 principal이 가질 수 있는 최대 권한을 정하는 managed policy입니다. 세 가지를 정확히 기억해야 합니다.

- **부착 대상은 user와 role뿐이다.** group은 지원하지 않는다.
- **권한을 부여하지 않는다.** identity-based policy가 별도로 필요하고 결과는 교집합이다.
- **SCP와는 층이 다르다.** SCP는 조직 트리에 붙어 계정 전체에 걸리고 management account에는 적용되지 않는다. boundary는 개별 principal에 붙고 조직과 무관하다. 둘이 함께 있으면 boundary, SCP, identity-based policy가 모두 허용해야 통과한다.

"개발팀 그룹에 boundary를 붙여 팀 전체의 상한을 정한다"는 선지는 그래서 성립하지 않습니다. group에는 붙지 않고, 붙는다 해도 그것은 그 사람들의 상한일 뿐 그들이 **만드는** role의 상한이 아닙니다.

---

## 6. boundary 위임 패턴은 iam:PermissionsBoundary 조건 키로 강제한다

boundary가 실무에서 쓰이는 대표 형태는 권한 위임입니다. 플랫폼팀이 각 서비스팀에게 IAM role 생성 권한을 주되, 만들어지는 role이 지정한 boundary 범위를 넘지 못하게 하는 구조입니다. 이 강제는 `iam:PermissionsBoundary` 조건 키가 담당합니다.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "CreateRoleOnlyWithBoundary",
      "Effect": "Allow",
      "Action": [
        "iam:CreateRole",
        "iam:PutRolePolicy",
        "iam:AttachRolePolicy",
        "iam:PutRolePermissionsBoundary"
      ],
      "Resource": "arn:aws:iam::111122223333:role/team/*",
      "Condition": {
        "StringEquals": {
          "iam:PermissionsBoundary": "arn:aws:iam::111122223333:policy/TeamBoundary"
        }
      }
    },
    {
      "Sid": "DenyBoundaryRemoval",
      "Effect": "Deny",
      "Action": "iam:DeleteRolePermissionsBoundary",
      "Resource": "*"
    }
  ]
}
```

위 정책이 만드는 결과는 두 가지입니다. 지정한 boundary가 붙는 경우에만 role 생성과 정책 부착이 성립하고, 위임받은 사람이 그 boundary를 떼어낼 수 없습니다. user 위임이면 `iam:CreateUser`, `iam:PutUserPolicy`, `iam:AttachUserPolicy`, `iam:PutUserPermissionsBoundary`를 같은 조건과 묶고 `iam:DeleteUserPermissionsBoundary`를 Deny합니다.

이 구조가 시험에서 답이 되는 이유는 강제 시점입니다. AWS Config 규칙으로 boundary 없는 role을 탐지해 삭제하는 방식은 사후 조치라 그 사이에 넓은 권한을 가진 role이 존재합니다. 지문에 "생성 시점에 보장" 또는 "위임은 유지"가 들어 있으면 조건 키 방식이 답입니다.

---

## 7. 교차 계정에서 trust policy와 permission policy가 각각 정하는 것

계정 A의 principal이 계정 B의 리소스에 접근하는 가장 일반적인 경로는 계정 B의 role을 가정하는 것입니다. 이 경로에는 정책이 세 개 관여하고 각각이 결정하는 질문이 다릅니다.

{% include diagrams/static/sap-c02/sts-assume-role-cross-account.html %}

그림은 왼쪽의 계정 A 컨테이너와 오른쪽의 계정 B 컨테이너, 그리고 두 계정 어느 쪽에도 속하지 않고 사이에 놓인 AWS STS로 나뉩니다. 실선은 계정 A의 principal에서 STS로, STS에서 계정 B의 trust policy로 이어집니다. 교차 계정 role 가정이 STS를 거치는 호출이고, 그 호출을 받아 판정하는 첫 정책이 trust policy라는 뜻입니다.

계정 B 안에서는 trust policy에서 아래로 대상 role, 대상 role에서 오른쪽으로 permission policy, permission policy에서 오른쪽 위로 꺾여 대상 리소스로 이어집니다. 두 정책이 답하는 질문이 이 순서에서 갈립니다. **trust policy는 누가 이 role을 가정할 수 있는가**를 정하고, **permission policy는 가정한 세션이 무엇을 할 수 있는가**를 정합니다. 대상 role 상자에 붙은 maximum session duration 1시간에서 12시간이 세션 길이의 상한이고, 대상 리소스 쪽에 적힌 대로 그 세션의 권한은 session policy로 더 좁힐 수 있습니다.

계정 A 안의 `sts:AssumeRole` 권한 상자에는 화살표가 닿지 않습니다. 흐름의 한 단계가 아니라 호출 측이 미리 갖추고 있어야 하는 전제이기 때문입니다. 이 권한이 계정 A principal의 identity-based policy에 없으면 그림의 첫 화살표 자체가 성립하지 않습니다.

세 정책이 각각 없을 때 실패하는 지점이 다릅니다.

| 빠진 것 | 실패 지점 |
| :--- | :--- |
| 계정 A principal의 `sts:AssumeRole` 권한 | `AssumeRole` 호출이 거부된다 |
| 계정 B role의 trust policy에 계정 A 지정 | `AssumeRole` 호출이 거부된다. trust policy는 explicit Allow가 필수다 |
| 계정 B role의 permission policy | 가정은 성공하고 이후 API 호출이 거부된다 |

`AssumeRole`로 얻은 세션은 **가정한 role의 권한**으로 동작합니다. 원래 principal의 권한이 세션에 합쳐지지는 않습니다. 계정 B의 role을 가정한 세션으로 계정 A의 버킷도 읽으려면, 그 role의 정책과 계정 A의 버킷 정책이 교차 계정 접근을 허용해야 합니다. 이 권한과 계정 B 큐 접근 권한이 함께 성립하면 같은 role 세션으로 두 계정의 리소스를 다룰 수 있습니다. role chaining은 이 세션이 다른 role을 다시 가정할 때 발생하고, 그때 뒤에서 볼 1시간 제약이 적용됩니다.

CloudTrail 기록도 갈립니다. role을 가정하면 대상 계정의 로그에 role session name이 남고, 원래 누구였는지는 `sts:SourceIdentity`를 강제하지 않는 한 별도로 추적해야 합니다.

---

## 8. role 가정과 resource-based policy 중 무엇을 고를 것인가

교차 계정 접근의 다른 경로는 대상 리소스의 resource-based policy에 상대 계정 principal을 직접 적는 것입니다. 두 경로의 차이가 문항의 축입니다.

| 축 | role 가정 (AssumeRole) | resource-based policy |
| :--- | :--- | :--- |
| 원래 권한 | 잃는다. role의 권한만 가진다 | 유지한다. principal이 자기 권한을 포기하지 않는다 |
| 두 계정 리소스 동시 접근 | 한 세션에서 불가능하다. chaining이 필요하다 | 가능하다 |
| 지원 범위 | 모든 서비스 | resource-based policy를 지원하는 서비스만 |
| CloudTrail 기록 | 대상 계정에 role session name이 남는다 | 호출자 principal이 그대로 남는다 |
| 세션 길이 | 900초에서 43,200초, chaining 시 1시간 | 해당 없음 |

지문에서 원래 principal의 권한을 그대로 사용하면서 상대 계정의 공유 리소스에도 접근해야 한다면 resource-based policy가 자연스러운 선택입니다. 가정한 role에 필요한 권한을 모아 관리하는 설계도 두 계정의 리소스를 함께 다룰 수 있으므로, 원래 권한을 유지해야 하는지가 판단 기준입니다. 해당 작업이 리소스 정책을 통한 위임을 지원하지 않으면 대상 계정의 role을 가정하는 경로를 검토합니다.

resource-based policy를 지원하지 않는 서비스에서는 선택지가 아예 없습니다. EC2, RDS, Auto Scaling처럼 리소스 정책이 없는 서비스에 교차 계정 접근이 필요하면 role 가정이 유일한 경로입니다.

---

## 9. STS API 다섯 종류와 세션 길이

STS가 임시 자격 증명을 발급하는 API는 다섯 가지입니다. 호출자, AWS 자격 증명 필요 여부, 유효 기간이 각각 다르고 이 표가 그대로 오답 선지의 재료가 됩니다.

| API | 호출자 | AWS 자격 증명 | 기본 유효 기간 | 유효 기간 범위 | MFA 파라미터 | session tag |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `AssumeRole` | IAM user 또는 세션 | 필요 | 3,600초 | 900초에서 43,200초, role 설정 종속, chaining 시 1시간 | `SerialNumber`, `TokenCode` | `Tags`, `TransitiveTagKeys` |
| `AssumeRoleWithSAML` | SAML IdP 인증 사용자 | 불필요(unsigned) | 3,600초 | 900초에서 43,200초, `SessionNotOnOrAfter`와 짧은 쪽 | 없다 | SAML `PrincipalTag` attribute |
| `AssumeRoleWithWebIdentity` | OIDC 또는 OAuth 2.0 인증 사용자 | 불필요 | 3,600초 | 900초에서 43,200초 | 없다 | JWT claim |
| `GetFederationToken` | IAM user 또는 root | 필요 | 43,200초(12시간) | 900초에서 129,600초, root는 1시간 | 없다 | `Tags`만, transitive 불가 |
| `GetSessionToken` | IAM user 또는 root | 필요 | 43,200초(12시간) | 900초에서 129,600초, root는 1시간 | `SerialNumber`, `TokenCode` | 없다 |

세션 길이에서 자주 갈리는 지점이 세 개입니다.

**첫째, 12시간과 36시간의 주체가 다릅니다.** `AssumeRole` 계열의 상한은 12시간이고, 36시간은 `GetFederationToken`과 `GetSessionToken`의 상한입니다. "장기 배치 작업에 36시간 세션이 필요하다"는 지문에서 `AssumeRole`을 고르면 틀립니다. 다만 root user가 호출하면 두 API 모두 1시간으로 잘립니다.

**둘째, role의 maximum session duration이 상한을 결정합니다.** role마다 1시간에서 12시간 사이로 설정하고, `DurationSeconds`로 그 값을 넘을 수 없습니다.

**셋째, role chaining은 CLI와 API 세션을 최대 1시간으로 제한합니다.** chaining 상태에서 1시간을 넘는 `DurationSeconds`를 주면 값이 잘리는 것이 아니라 operation 자체가 실패합니다. role의 maximum session duration을 12시간으로 올려도 이 제한은 그대로입니다. 8시간 세션이 필요하면 chaining을 제거하고 대상 role을 직접 가정해야 합니다.

호출 자격에도 제약이 있습니다. `AssumeRole*`로 얻은 임시 자격 증명으로는 `GetFederationToken`과 `GetSessionToken`을 호출할 수 없습니다. "세션에서 `GetFederationToken`을 불러 36시간을 얻는다"는 경로는 존재하지 않습니다.

파라미터 자체의 길이 제약도 문항에 나옵니다. `RoleSessionName`은 2자에서 64자, `ExternalId`는 2자에서 1,224자, `TokenCode`는 정확히 6자리 숫자, `SerialNumber`는 9자에서 256자입니다. `ExternalId`에 허용되는 문자는 영숫자와 `+`, `=`, `,`, `.`, `@`, `:`, `/`, `-`이고 공백은 쓸 수 없습니다.

---

## 10. session policy는 권한을 줄이기만 하고 PackedPolicySize로 실패한다

session policy는 세션을 만들 때 요청 파라미터로 넘기는 정책입니다. 문서로 저장되지 않고 그 세션에만 붙습니다.

- inline JSON 문서 **1개**와 managed policy ARN **최대 10개**를 넘길 수 있다.
- 둘을 합친 plaintext가 **2,048자**를 넘을 수 없다.
- 결과 권한은 role의 identity-based policy와의 **교집합**이다. 권한을 확대할 수 없다.

권한을 확대할 수 없다는 점이 핵심입니다. "role에 없는 권한을 session policy로 임시 부여한다"는 선지는 항상 틀립니다. session policy의 용도는 반대입니다. 넓은 권한을 가진 role 하나를 두고, 호출할 때마다 그 세션이 다룰 범위를 좁히는 데 씁니다. 멀티테넌트 애플리케이션이 테넌트별 prefix로 S3 접근을 좁히는 구성이 대표적입니다.

2,048자를 지켜도 실패할 수 있습니다. 응답의 `PackedPolicySize`는 session policy와 session tag를 압축한 크기의 퍼센트 값이고, 100을 넘으면 `PackedPolicyTooLarge`로 실패합니다. plaintext 제한과 packed 제한이 별개이므로 "글자 수를 셌으니 안전하다"는 판단이 성립하지 않습니다.

`AssumeRoleWithSAML`에는 별도의 권고가 붙습니다. 이 API는 AWS 자격 증명 없이 호출하는 unsigned 요청이라, 신뢰할 수 있는 중개자를 거치지 않으면 session policy를 넘기지 말라고 문서가 명시합니다. 중간에서 제약을 제거해버릴 수 있기 때문입니다.

---

## 11. sts:SourceIdentity와 STS 요청 쿼터

교차 계정 접근에서 "이 세션의 실제 사람이 누구인가"를 대상 계정 로그로 추적해야 하는 요구가 자주 나옵니다. `RoleSessionName`은 호출자가 자유롭게 정할 수 있어 신뢰할 수 없고, 이 자리를 `sts:SourceIdentity`가 담당합니다.

- role trust policy로 설정을 **강제**할 수 있다.
- 한 번 설정하면 세션 중 **변경할 수 없다**.
- chained role 세션 **전체에 유지**된다.
- 길이는 2자에서 64자이고 `aws:` 접두사는 예약어다.

chaining 전체에 유지된다는 점이 `RoleSessionName`과 갈리는 지점입니다. 여러 계정을 거쳐 들어온 요청에서도 최초 신원이 그대로 남습니다.

STS 요청 쿼터도 대규모 조직 문항의 재료입니다. AWS 자격 증명으로 보내는 STS 요청은 **계정당 리전당 기본 600 requests per second**이고, `AssumeRole`, `DecodeAuthorizationMessage`, `GetAccessKeyInfo`, `GetCallerIdentity`, `GetFederationToken`, `GetSessionToken`이 이 쿼터를 공유합니다. 두 가지가 헷갈립니다. 교차 계정 `AssumeRole`은 **호출 계정의 쿼터만** 소비하고 대상 계정 쿼터는 소비하지 않으며, AWS service principal이 보내는 호출은 쿼터를 소비하지 않습니다.

---

## 12. confused deputy를 external ID가 막는 지점

서드파티 SaaS가 고객 계정의 role을 가정해 작업하는 구조에는 confused deputy 위험이 있습니다. 공격자가 다른 고객의 role ARN을 알아내 서드파티에 자기 계정 정보로 등록하면, 서드파티가 그 role을 대신 가정해버리는 경로입니다.

{% include diagrams/static/sap-c02/confused-deputy-external-id.html %}

그림 가운데의 서드파티 서비스가 여러 고객의 role을 대신 가정하는 대리인(deputy) 위치에 있습니다. 정상 경로는 실선입니다. 좌상단의 고객 A가 서드파티에 role ARN을 주고, 서드파티가 그 role을 가정하려 하면 가운데 노란 상자인 external ID 조건을 지나 오른쪽 위의 고객 A의 role에 도달합니다. 고객 A의 role 상자에 적힌 대로 그 trust policy가 external ID 일치를 요구합니다.

공격 경로는 점선입니다. 좌하단의 제3자는 같은 서드파티를 쓰는 다른 고객이고 고객 A의 role ARN을 알고 있습니다. 이 상자에서 나온 점선이 서드파티 서비스로 합류합니다. 정상 고객과 똑같이 서드파티를 매개로 삼는 데까지는 막을 수단이 없다는 뜻입니다. 갈리는 곳은 그 다음이고, external ID 조건 상자에서 아래로 내려가는 두 번째 점선이 오른쪽 아래의 가정 실패로 향합니다. 제3자는 고객 A에게 발급된 값을 제시할 수 없으므로 여기서 끊깁니다. 노란 상자에 적힌 `sts:ExternalId`의 2자에서 1,224자와 secret이 아니라는 표기가 이 값의 성격입니다.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "AWS": "arn:aws:iam::444455556666:root" },
      "Action": "sts:AssumeRole",
      "Condition": {
        "StringEquals": {
          "sts:ExternalId": "customer-unique-value-generated-by-vendor"
        }
      }
    }
  ]
}
```

external ID에서 시험이 묻는 것은 값의 성격 두 가지입니다.

**값을 만드는 주체는 서드파티입니다.** 서드파티가 고객마다 유일한 값을 생성해 전달하고, 고객은 그 값을 trust policy에 넣습니다. 고객이 임의로 정하면 두 고객이 같은 값을 쓸 수 있고 공격자가 자기 값을 등록해 맞출 수 있으므로, 문서는 고객이 정하지 말라고 명시합니다.

**external ID는 비밀이 아닙니다.** AWS는 이 값을 secret으로 취급하지 않고, role을 볼 권한이 있는 사람은 값을 볼 수 있습니다. Secrets Manager에 넣어 관리한다는 선지는 방어 원리를 잘못 짚은 것입니다. 방어가 성립하는 이유는 값이 비밀이어서가 아니라 서드파티가 값을 통제하기 때문입니다.

문서는 서드파티 쪽 검증 절차도 권고합니다. 고객이 준 role ARN에 대해 올바른 external ID 없이도 가정이 되는지 시험하고, 가정이 된다면 그 ARN을 저장하지 않는 것입니다.

---

## 13. cross-service confused deputy는 SourceArn 계열 조건 키로 막는다

confused deputy에는 방향이 다른 두 번째 형태가 있습니다. AWS 서비스가 고객을 대신해 다른 리소스에 접근하는 cross-service 경로입니다. CloudTrail이 로그를 중앙 S3 버킷에 쓰는 구성이 대표적입니다.

버킷 정책이 `cloudtrail.amazonaws.com` service principal만 허용하고 조건이 없으면, 버킷 이름을 아는 다른 계정이 자기 trail의 대상으로 이 버킷을 지정할 수 있습니다. 방어 수단은 조건 키 네 가지입니다.

| 조건 키 | 한정 단위 | 쓰는 상황 |
| :--- | :--- | :--- |
| `aws:SourceArn` | 개별 리소스 | 특정 trail, 특정 topic 하나만 허용할 때 |
| `aws:SourceAccount` | 계정 | 그 계정의 리소스 전부를 허용할 때 |
| `aws:SourceOrgID` | 조직 | 조직 안 계정의 요청만 허용할 때 |
| `aws:SourceOrgPaths` | OU 경로 | 특정 OU 아래 계정만 허용할 때 |

리소스 정책을 계정마다 고치는 대신 조직 레벨에서 한 번에 강제하는 방법이 RCP입니다. 공식 예시는 `aws:PrincipalIsAWSService`가 true이고 `aws:SourceAccount`가 존재할 때만 `aws:SourceOrgID` 일치를 요구합니다.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "EnforceOrgIdForServicePrincipals",
      "Effect": "Deny",
      "Principal": "*",
      "Action": "*",
      "Resource": "*",
      "Condition": {
        "StringNotEqualsIfExists": { "aws:SourceOrgID": "o-exampleorgid" },
        "Bool": { "aws:PrincipalIsAWSService": "true" },
        "Null": { "aws:SourceAccount": "false" }
      }
    }
  ]
}
```

`aws:PrincipalIsAWSService` 조건이 있어 사용자가 직접 보내는 요청은 이 Deny에 걸리지 않습니다. 지문에 "각 팀의 리소스 정책을 수정하는 절차는 배제되었다"와 "AWS 서비스가 대신 보내는 요청만 대상"이 함께 있으면 RCP가 답입니다. 같은 요구에 SCP를 고르면 방향이 틀립니다. SCP는 조직 계정 안의 principal을 제한하는 정책이라 AWS 서비스 주체가 리소스에 접근하는 방향을 통제하지 못합니다.

---

## 14. session tag가 aws:PrincipalTag로 들어가는 경로

ABAC은 principal의 속성과 리소스의 태그를 조건으로 비교해 접근을 결정하는 방식입니다. 계정과 팀이 늘어날 때 role을 계속 만드는 대신 태그 매칭 하나로 확장하는 것이 목적입니다.

{% include diagrams/static/sap-c02/session-tags-abac.html %}

윗줄이 태그가 전달되는 경로입니다. 왼쪽의 IdP 속성에서 출발해 `sts:TagSession`, session tag, `aws:PrincipalTag` 순으로 오른쪽으로 이어집니다. 두 번째 상자가 경로 위에 놓인 이유가 있습니다. `sts:TagSession`이 role trust policy에 없으면 태그만 누락되는 것이 아니라 `AssumeRole` 호출 자체가 실패하기 때문에, 이 상자를 통과하지 못하면 뒤가 전부 성립하지 않습니다. 세 번째 상자의 최대 50개와 key 128자, value 256자가 session tag의 한도이고, 네 번째 상자가 그 값이 request context의 `aws:PrincipalTag`로 들어가는 지점입니다.

`aws:PrincipalTag`에서 아래로 내려온 선과 아랫줄 왼쪽의 리소스 태그에서 오른쪽으로 온 선이 가운데의 정책 Condition에서 만납니다. ABAC의 실제 판정이 여기서 일어납니다. 정책이 `aws:PrincipalTag`와 `aws:ResourceTag`를 비교하고, 오른쪽 끝의 접근 허용에 적힌 대로 두 태그가 일치할 때만 요청이 통과합니다.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["ec2:StartInstances", "ec2:StopInstances"],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "aws:ResourceTag/team": "${aws:PrincipalTag/team}"
        }
      }
    }
  ]
}
```

전달 경로는 API마다 다릅니다.

| API | 전달 경로 |
| :--- | :--- |
| `AssumeRole` | `Tags` 파라미터, transitive는 `TransitiveTagKeys` |
| `AssumeRoleWithSAML` | SAML attribute `https://aws.amazon.com/SAML/Attributes/PrincipalTag:{TagKey}`, transitive는 `https://aws.amazon.com/SAML/Attributes/TransitiveTagKeys` |
| `AssumeRoleWithWebIdentity` | JWT의 `https://aws.amazon.com/tags` nested claim 또는 `https://aws.amazon.com/tags/principal_tags/{TagKey}` flattened claim |
| `GetFederationToken` | `Tags` 파라미터. transitive 지정은 불가능하다 |

flattened claim 형식은 nested object를 지원하지 않는 IdP를 위한 것이고, 문서는 Microsoft Entra ID를 예로 듭니다.

동작 제약이 여섯 개 있고 전부 문항 재료입니다.

- session tag는 최대 **50개**, key **128자**, value **256자**다.
- 세션 태그를 넘기려면 API action 권한에 더해 role trust policy에 **`sts:TagSession`** permissions-only action이 있어야 한다. 없으면 `AssumeRole` 호출 자체가 실패한다.
- **AWS Management Console의 Switch Role로는 session tag를 넘길 수 없다.** CLI나 API 경로가 필요하다.
- session tag는 키가 같은 role tag를 **override**한다. 태그 키와 값은 대소문자를 구분하지 않으므로 `Department`와 `department`를 별도 키로 둘 수 없다.
- `TransitiveTagKeys`는 최대 50개이고, transitive로 지정한 태그만 role chaining의 다음 세션으로 상속된다. **role에 붙은 태그는 transitive로 지정할 수 없다.** 상속된 transitive 태그와 같은 키를 다음 세션에서 다시 넘기면 operation이 실패한다.
- session tag는 **multi-valued를 지원하지 않는다.** 키마다 단일 값만 넘길 수 있다.

`sts:TagSession`과 함께 쓰는 조건 키는 `aws:PrincipalTag`, `aws:RequestTag`, `aws:ResourceTag`, `aws:TagKeys`, `sts:TransitiveTagKeys` 다섯 가지입니다.

---

## 15. SAML 2.0 페더레이션에서 API 경로와 콘솔 경로가 갈린다

사내 IdP를 SAML 2.0으로 AWS에 연결하면 사용자는 AWS에 자격 증명을 만들지 않고도 리소스에 접근할 수 있습니다. 이 연동에서 접근 경로가 둘로 갈리고, 각 경로가 다른 API를 씁니다.

{% include diagrams/static/sap-c02/saml-federation-paths.html %}

그림은 왼쪽의 사내 사용자에서 시작합니다. 사용자가 SAML 2.0 IdP에 인증하면 IdP가 assertion에 서명하고, 그 SAML assertion 상자에서 선이 둘로 갈라집니다. 갈라지기 전까지는 두 경로가 완전히 같습니다.

위로 올라가는 선이 콘솔 경로입니다. assertion이 AWS sign-in 엔드포인트로 가고 거기서 관리 콘솔 세션이 만들어져 브라우저로 리다이렉트됩니다. 아래로 내려가는 선이 API 경로입니다. assertion이 `AssumeRoleWithSAML` 호출로 들어가고, 상자에 적힌 대로 이 호출은 unsigned 요청입니다. 결과로 나오는 임시 자격 증명의 유효 기간이 오른쪽 아래 상자의 문구이고 `DurationSeconds`와 assertion의 `SessionNotOnOrAfter` 중 짧은 쪽이 이깁니다. 두 선 모두 실선이고 조건 분기가 아닙니다. 같은 assertion을 어느 엔드포인트로 보내느냐가 경로를 정합니다. 두 경로가 공유하는 사전 설정은 계정에 등록한 SAML identity provider와 그 provider를 신뢰하는 IAM role입니다.

`AssumeRoleWithSAML`에서 알아야 할 것이 네 가지입니다.

- **AWS 자격 증명 없이 호출하는 unsigned 요청이다.** 호출자에게 AWS 계정이 없어도 된다.
- **세션 길이는 `DurationSeconds`와 SAML assertion의 `SessionNotOnOrAfter` 중 짧은 쪽이다.** 여기에 role의 maximum session duration 상한도 함께 걸린다. "IdP가 8시간을 주었으니 8시간"이라는 판단은 세 값 중 가장 짧은 것이 이긴다는 규칙을 놓친 것이다.
- `SAMLAssertion`은 base64 인코딩 기준 4자에서 100,000자다.
- **IAM Identity Center가 관리하는 role에는 동작하지 않는다.** 이름이 `AWSReservedSSO_`로 시작하는 role이 여기에 해당한다.

마지막 항목이 답을 가르는 지점입니다. Identity Center를 쓰면서 동시에 SAML 직접 연동으로 그 permission set role을 가정하겠다는 구성은 성립하지 않습니다.

콘솔 접근 경로에는 세 번째 형태가 있습니다. 사내 인증 시스템이 SAML을 지원하지 않을 때 쓰는 custom identity broker입니다. 브로커가 사용자를 자체 방식으로 인증한 뒤 `GetFederationToken` 또는 `AssumeRole`로 임시 자격 증명을 얻고, 그 자격 증명을 AWS federation endpoint에 제출해 sign-in token을 받아 콘솔 로그인 URL을 만들어 줍니다. `GetFederationToken`을 쓸 때 `Policy`를 넘기지 않으면 그 세션에는 어떤 권한도 없고 resource-based policy로만 접근이 성립한다는 점이 함정입니다.

---

## 16. web identity federation과 Cognito identity pool

모바일 앱과 웹 앱이 최종 사용자 신원으로 AWS 리소스에 접근하는 경로는 `AssumeRoleWithWebIdentity`입니다. 여기서도 AWS 자격 증명이 필요 없습니다.

- `WebIdentityToken`은 4자에서 20,000자이고 **RS256, RS384, RS512 또는 ES256, ES384, ES512**로 서명해야 한다.
- `SubjectFromWebIdentityToken`은 6자에서 255자다.
- `ProviderId` 파라미터는 **OAuth 2.0 access token 전용**이고 `www.amazon.com`과 `graph.facebook.com`만 지원한다. OIDC ID token에는 지정하지 않는다.

앱이 이 API를 직접 부르는 대신 Amazon Cognito를 두는 구성이 일반적입니다. 여기서 user pool과 identity pool을 혼동하면 문항이 틀립니다.

| 축 | user pool | identity pool |
| :--- | :--- | :--- |
| 산출물 | JWT(ID token, access token) | AWS 임시 자격 증명 |
| 역할 | 인증과 사용자 디렉터리, 앱에 대한 OIDC IdP | AWS 자격 증명 브로커 |
| 미인증 사용자 | 개념이 없다 | guest role로 발급할 수 있다 |
| 뒤에서 부르는 STS API | 없다 | `AssumeRoleWithWebIdentity` |
| IAM 연결 | 없다 | authenticated role과 unauthenticated role, claim 기반 role 선택 |

**AWS 자격 증명을 발급하는 것은 identity pool입니다.** user pool은 JWT까지만 만듭니다. identity pool은 SAML assertion, OIDC ID token, 소셜 OAuth token, user pool token, developer-authenticated identity를 받아 `AssumeRoleWithWebIdentity` 요청으로 변환하고, 사용자 claim에 따라 role을 선택하거나 claim을 IAM session tag로 변환할 수 있습니다.

교차 계정 구성에는 조건 키가 하나 더 필요합니다. identity pool이 다른 계정의 role을 가정하려면 그 role의 trust policy가 `cognito-identity.amazonaws.com` service principal을 신뢰하고 **`cognito-identity.amazonaws.com:aud` 조건 키로 identity pool을 한정**해야 합니다. 이 조건이 없으면 다른 identity pool의 사용자가 같은 role을 가정할 수 있습니다.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "Federated": "cognito-identity.amazonaws.com" },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "cognito-identity.amazonaws.com:aud": "us-east-1:example-identity-pool-id"
        },
        "ForAnyValue:StringLike": {
          "cognito-identity.amazonaws.com:amr": "authenticated"
        }
      }
    }
  ]
}
```

---

## 17. IAM Identity Center permission set과 SCIM과 ABAC

IAM Identity Center는 신원 소스를 한 곳에 두고 여러 계정에 접근 권한을 배포합니다. permission set이 대상 계정에서 IAM role이 되는 구조는 [멀티 계정 거버넌스 편](/posts/aws-sap-c02-multi-account-governance/)에서 다뤘고, 여기서는 세션 길이와 속성 전달만 봅니다.

세션 길이는 두 층으로 나뉩니다.

- permission set의 session duration은 신규 생성 시 **기본 1시간**이고 범위는 **1시간에서 12시간**이다.
- Identity Center는 할당된 계정마다 permission set별 IAM role을 자동 생성하고 그 role의 maximum session duration을 **12시간**으로 설정한다. 실제 세션 길이를 결정하는 것은 permission set 설정이다.
- Identity Center가 만든 role은 기본적으로 Identity Center 사용자만 가정할 수 있어 permission set의 session duration이 강제된다.

role 쪽 값이 12시간이라고 세션이 12시간이 되는 것이 아니고, permission set 값이 상한을 24시간으로 올릴 수 있는 것도 아닙니다.

ABAC 경로는 두 가지가 있고 우선순위가 정해져 있습니다.

| 축 | STS session tag | Identity Center attributes for access control |
| :--- | :--- | :--- |
| 진입점 | `AssumeRole` 계열 API 파라미터, SAML attribute, JWT claim | Identity Center 콘솔 속성 선택 또는 IdP SAML assertion |
| 필요 권한 | role trust policy의 `sts:TagSession` | 해당 없음 |
| SAML attribute 이름 | `https://aws.amazon.com/SAML/Attributes/PrincipalTag:{TagKey}` | `https://aws.amazon.com/SAML/Attributes/AccessControl:{TagKey}` |
| 정책 참조 키 | `aws:PrincipalTag/{key}` | `aws:PrincipalTag/{key}`로 동일하다 |
| 충돌 시 | session tag가 같은 키의 role tag를 override한다 | Identity Center 디렉터리 매핑이 IdP SAML 값을 대체한다 |
| chaining 상속 | transitive 지정 시 상속된다 | 해당 없음 |

Identity Center에서 선택한 속성은 대상 계정으로 session tag로 전달되고, 모든 IAM policy 타입에서 `aws:PrincipalTag/{tag-key}`로 참조합니다. SAML attribute 이름이 두 경로에서 다르다는 점을 주의해야 합니다. `PrincipalTag:`는 IAM role 직접 연동 경로이고 `AccessControl:`은 Identity Center 경로입니다.

속성 값을 채우는 방법도 갈립니다. **SCIM**을 쓰면 IdP가 사용자와 속성을 Identity Center로 자동 동기화하고, SCIM을 쓰지 않으면 사용자와 속성을 수동으로 만들어야 합니다. 그리고 SAML assertion으로 넘어온 속성은 Attributes for access control 페이지에 표시되지 않으므로, 정책을 쓸 때 속성 이름을 미리 알고 있어야 합니다.

---

## 18. AWS Directory Service 세 가지가 갈리는 기준

온프레미스 Active Directory가 있는 조직이 워크로드를 AWS로 옮길 때 디렉터리 선택 문항이 나옵니다. 선택지는 세 가지이고 기능 차이가 답을 가릅니다.

{% include diagrams/static/sap-c02/directory-service-selection.html %}

왼쪽의 온프레미스 Active Directory가 출발점이고 거기서 나가는 선이 두 갈래입니다. 실선은 오른쪽의 AD Connector로 갑니다. 사용자를 온프레미스에 그대로 두고 인증만 프록시하는 경로이고, 상자에 적힌 대로 캐싱이 없고 사용자는 온프레미스에만 존재합니다. 그 실선 도중에 위로 갈라져 나온 점선이 AWS Managed Microsoft AD로 향합니다. 실선이 아닌 이유는 온프레미스 저장소를 그대로 쓰는 관계가 아니라 trust로 연결하는 선택이기 때문이고, 세 선택지 중 온프레미스 포리스트와 trust를 맺을 수 있는 것은 이것 하나입니다.

오른쪽 끝의 두 종착점이 기능 차이를 드러냅니다. RDS for SQL Server로 가는 선은 AWS Managed Microsoft AD에서만 나옵니다. 반면 EC2 Windows domain join으로는 AD Connector와 아래쪽 Simple AD에서 나온 선이 모두 모이고, 상자에 적힌 대로 세 방식 모두 가능합니다. 아래쪽의 Simple AD는 온프레미스 Active Directory와 선으로 이어지지 않습니다. 온프레미스 AD 없이 AWS 안에 독립된 저규모 디렉터리를 두는 선택이기 때문이고, Samba 4 기반이며 신규 고객 온보딩이 중단되었다는 표기가 함께 붙어 있습니다.

| 축 | AWS Managed Microsoft AD | AD Connector | Simple AD |
| :--- | :--- | :--- | :--- |
| 실체 | 실제 Windows Server Active Directory | 프록시(directory gateway) | Samba 4 기반 AD 호환 |
| 사용자 저장 위치 | AWS 또는 온프레미스와 trust | 온프레미스에만 | AWS |
| 온프레미스 trust | 지원한다(one-way 2종, two-way forest trust) | 불가능하다 | 불가능하다 |
| 캐싱 | 해당 없음 | 없다 | 해당 없음 |
| 규모 | Standard 약 30,000 객체, Enterprise 약 500,000 객체 | Small과 Large 사이즈 | 저규모 |
| RDS for SQL Server | 지원한다 | 비호환 | 비호환 |
| schema extension, LDAPS | 지원한다 | 해당 없음 | 미지원 |
| MFA | 지원한다 | RADIUS 연동으로 지원한다 | 미지원 |
| 신규 도입 | 가능하다 | 가능하다 | 신규 고객 온보딩 중단 |

객체 수는 문서가 근사치로 명시한 값입니다. 12만 개 규모 지문이 나오면 Standard의 약 30,000을 넘고 Enterprise의 약 500,000 안에 들어가므로 Enterprise Edition이 답입니다.

**AD Connector는 프록시입니다.** 캐싱이 없고 디렉터리 데이터를 AWS로 복제하거나 동기화하지 않으며, 사용자 관리는 온프레미스 AD에서만 합니다. 그래서 trust를 설정할 수 없고 RDS for SQL Server와도 호환되지 않습니다. 할 수 있는 것은 seamless domain join으로 EC2 Windows 인스턴스를 온프레미스 도메인에 조인시키는 것과 RADIUS 기반 MFA 연결입니다.

**Simple AD는 지원하지 않는 목록이 깁니다.** MFA, trust relationship, DNS dynamic update, schema extension, LDAPS 통신, PowerShell AD cmdlet, FSMO role transfer를 지원하지 않고 RDS for SQL Server와도 호환되지 않습니다. 다만 "단종되어 못 쓴다"는 서술은 틀립니다. 중단된 것은 **신규 고객 온보딩**뿐이고 기존 고객은 전체 기능을 유지하며 새 디렉터리도 계속 만들 수 있습니다. 권장 대안은 AWS Managed Microsoft AD와 AD Connector입니다.

AWS Managed Microsoft AD는 실제 AD이므로 schema extension, password policy 관리, LDAPS, MFA, 온프레미스 AD와의 trust, 다중 리전 복제, RDS for SQL Server 연동을 모두 지원합니다. directory 자체를 여러 AWS 계정에 공유해 교차 계정 EC2 domain join을 구성할 수도 있습니다.

---

## 19. IAM Access Analyzer 세 종류와 policy generation

IAM Access Analyzer는 이름 하나에 성격이 다른 analyzer 세 종류가 들어 있고, 여기에 policy validation, custom policy check, policy generation이 별도 기능으로 붙습니다.

| 축 | external access | internal access | unused access |
| :--- | :--- | :--- | :--- |
| 묻는 질문 | zone of trust 밖에 열려 있는가 | 조직 안 어떤 principal이 접근 가능한가 | 쓰이지 않는 권한과 자격 증명은 무엇인가 |
| 분석 대상 | 리소스 15종의 resource-based policy | 리소스 6종 | 모든 IAM role과 user |
| 리전 | **리전마다 analyzer가 필요하다** | 리소스 기준 | **리전과 무관하다. 하나면 충분하다** |
| 과금 기준 | 별도 과금이 없다 | 모니터링 리소스 수 | 분석 대상 role과 user 수 |
| 제외 대상 | 해당 없음 | 해당 없음 | service-linked role |

리전 규칙이 반대라는 점이 비용 문항의 축입니다. external access analyzer는 활성화한 리전의 리소스만 분석하므로 리전마다 만들어야 하고, unused access analyzer는 finding이 리전에 따라 달라지지 않으므로 리전마다 만들면 커버리지는 그대로인 채 과금만 리전 수만큼 늘어납니다.

zone of trust는 계정 또는 조직 단위로 지정하고, 그 밖의 principal에게 열린 접근이 finding이 됩니다. external access 분석 대상은 S3 bucket, S3 directory bucket, IAM role, KMS key, Lambda function과 layer, SQS queue, Secrets Manager secret, SNS topic, EBS volume snapshot, RDS DB snapshot, RDS DB cluster snapshot, ECR repository, EFS file system, DynamoDB stream, DynamoDB table 15종입니다. internal access는 S3 bucket, S3 directory bucket, RDS DB snapshot, RDS DB cluster snapshot, DynamoDB stream, DynamoDB table 6종으로 더 좁습니다.

재분석 주기도 확인해 둘 값입니다. 정책을 추가하거나 변경하면 약 30분 안에 재분석하고, 알림이 유실되면 24시간 이내 주기 스캔에서 처리하며, S3 multi-region access point 관련 변경은 최대 6시간이 걸립니다.

**policy generation**은 CloudTrail 이벤트를 근거로 최소 권한 정책 초안을 만드는 기능이고 제약이 많습니다.

- 최대 **90일** 범위의 CloudTrail 이벤트를 분석한다. 계정에 trail이 활성화되어 있어야 하고, Access Analyzer에 trail과 service last accessed 정보 접근을 주는 service role이 필요하다.
- 생성된 정책은 IAM 콘솔에서 **최대 7일**간 확인할 수 있고 **동시에 1개만** 유지된다. 새로 생성하면 기존 것이 대체된다.
- S3 data event 같은 data event를 action 수준으로 식별하지 않는다.
- **`iam:PassRole`은 CloudTrail이 추적하지 않아 생성 정책에 포함되지 않는다.** 생성 결과에 없다고 해서 그 role이 PassRole을 쓰지 않았다고 결론지을 수 없다.
- **감사 용도로 쓰면 안 된다.** denied action까지 포함해 모든 CloudTrail 이벤트를 검토하기 때문이고, 문서가 감사에는 CloudTrail을 쓰라고 명시한다.
- **AWS Control Tower가 만든 trail을 지원하지 않는다.** 로그가 Log Archive 계정에 쌓이고 그 S3 버킷 권한이 Control Tower SCP로 잠겨 재구성할 수 없기 때문이다.
- 교차 계정 trail로 정책을 생성하려면 로그 버킷의 Object Ownership이 `Bucket owner enforced` 또는 `Bucket owner preferred`여야 한다. `Bucket owner preferred`를 고르면 소유권 변경 이후 기간에 대해서만 생성된다.

**policy validation**은 policy grammar와 AWS best practice를 검사해 security warning, error, general warning, suggestion을 냅니다. **custom policy check**는 새 정책이 기존 버전 대비 새로운 접근을 부여하는지, 지정한 critical action이 허용되는지를 검사하고 API 요청 수 기준으로 과금합니다. CI 파이프라인에서 정책 변경을 게이트로 막는 요구가 지문에 나오면 custom policy check가 답입니다.

---

## 20. policy simulator가 평가하는 것과 평가하지 않는 것

IAM policy simulator는 실제 요청을 보내지 않고 정책 평가 결과만 확인하는 도구입니다. 결과는 액션과 리소스 조합마다 allow 또는 deny 이진값이고, allow나 explicit deny인 경우 어느 정책이 그 결과를 냈는지도 보여줍니다.

모드는 두 가지입니다. **Principal mode**는 기존 IAM user, role, group에 붙어 있는 정책을 시뮬레이션하고, **Custom mode**는 아직 붙이지 않은 정책 문서를 직접 넣어 시험합니다. 어느 쪽이든 계정의 실제 정책은 바뀌지 않습니다.

평가 범위에 경계가 있습니다.

| 대상 | simulator에서 |
| :--- | :--- |
| identity-based policy | 평가한다 |
| permissions boundary | 평가한다. 한 번에 하나만 넣을 수 있다 |
| SCP | 평가한다. 다만 보안상 매칭된 statement를 보여주지 않는다 |
| resource-based policy | 사용자가 제공한 것만 평가한다. 콘솔이 아니면 리소스의 정책을 대신 가져오지 않는다 |
| **RCP** | **지원하지 않는다** |

조건 키 처리에도 규칙이 있습니다. simulator가 자동으로 채우는 것은 `aws:PrincipalAccount`, `aws:PrincipalId`, `aws:PrincipalType`, `aws:Type`, `aws:UserId`, `aws:UserName`과 조직 컨텍스트인 `aws:PrincipalOrgID`, `aws:PrincipalOrgMasterAccountId`, `aws:PrincipalOrgPaths`입니다. 나머지 조건 키 값은 직접 넣어야 하고, 값이 조건을 만족하지 못하면 deny로 나옵니다.

콘솔과 CLI가 갈리는 지점도 있습니다. 콘솔에서는 identity-based policy, permissions boundary, resource-based policy에 등장하는 조건 키에만 값을 넣을 수 있어서, SCP에만 등장하는 조건 키는 값을 지정할 수 없습니다. CLI와 API에서는 SCP가 참조하는 조건 키에도 값을 줄 수 있습니다.

문서가 명시하는 한계가 두 가지 더 있습니다. identity-based policy와 resource-based policy를 평가할 때 simulator는 특정 서비스가 어떤 global condition key를 지원하는지 판별하지 않습니다. 예를 들어 어떤 서비스가 `aws:TagKeys`를 지원하지 않는다는 사실을 반영하지 못합니다. 반면 SCP는 service-aware 로직으로 평가합니다. 그리고 VPC endpoint policy, role chaining, 한 리소스에 여러 resource-based policy가 붙은 구성 같은 고급 설정에서는 결과가 실제 환경과 다를 수 있습니다. 그래서 문서는 simulator 결과를 확인한 뒤 실제 환경에서 다시 검증하라고 권고합니다.

---

## 21. 암기해야 하는 하드 리밋과 동작 제약

시험에서 선지를 직접 가르는 수치와 동작입니다.

**STS 세션과 파라미터**

| 항목 | 값 |
| :--- | :--- |
| `AssumeRole` `DurationSeconds` | 900초에서 43,200초, 기본 3,600초 |
| role의 maximum session duration | 1시간에서 12시간 |
| role chaining 시 CLI와 API 세션 | 최대 1시간. 초과 지정 시 operation 실패 |
| `GetFederationToken` | 900초에서 129,600초, 기본 12시간, root는 1시간 |
| `GetSessionToken` | 15분에서 36시간, 기본 12시간, root는 1시간 |
| `AssumeRoleWithSAML` 세션 | `DurationSeconds`와 `SessionNotOnOrAfter` 중 짧은 쪽 |
| session policy | inline 1개 + managed ARN 10개, 합쳐 plaintext 2,048자 |
| `PackedPolicySize` | 100 초과 시 `PackedPolicyTooLarge` |
| `RoleSessionName` | 2자에서 64자 |
| `ExternalId` | 2자에서 1,224자, 공백 불가 |
| `SerialNumber` | 9자에서 256자 |
| `TokenCode` | 정확히 6자리 숫자 |
| `sts:SourceIdentity` | 2자에서 64자, 설정 후 변경 불가, chaining 전체 유지 |
| `SAMLAssertion` | base64 기준 4자에서 100,000자 |
| `WebIdentityToken` | 4자에서 20,000자 |
| `SubjectFromWebIdentityToken` | 6자에서 255자 |
| STS 요청 쿼터 | 계정당 리전당 기본 600 rps |

**session tag**

| 항목 | 값 |
| :--- | :--- |
| session tag 수 | 최대 50 |
| tag key / value | 128자 / 256자 |
| `TransitiveTagKeys` | 최대 50 |
| 필요 권한 | role trust policy의 `sts:TagSession` |
| 콘솔 Switch Role | session tag 전달 불가 |
| multi-valued | 지원하지 않는다 |

**IAM 쿼터**

| 항목 | 값 |
| :--- | :--- |
| inline policy 총합 | user 2,048자, role 10,240자, group 5,120자. 공백 제외 |
| customer managed policy | 개당 6,144자, 계정당 기본 1,500개, 최대 10,000개 |
| managed policy 부착 | role 기본 20(최대 25), user 기본 10(최대 20), group 10(증설 불가) |
| role trust policy 길이 | 기본 2,048자, 최대 8,192자 |
| role 이름 | 64자. 콘솔 Switch Role은 `Path` + `RoleName` 합이 64자 이내 |
| 계정당 role | 기본 1,000, 최대 10,000 |
| 계정당 group | 기본 300, 최대 500 |
| 계정당 instance profile | 기본 1,000, 최대 10,000 |
| 계정당 OIDC provider | 기본 100, 최대 700 |
| 계정당 server certificate | 20 |
| 이름 유일성 | user, group, role, instance profile 이름은 계정 안에서 유일하고 대소문자를 구별하지 않는다 |

**IAM Identity Center와 Access Analyzer**

| 항목 | 값 |
| :--- | :--- |
| permission set session duration | 기본 1시간, 범위 1시간에서 12시간 |
| Identity Center 생성 role의 max session duration | 12시간 |
| Access Analyzer 재분석 | 정책 변경 후 약 30분, 주기 스캔 24시간, S3 MRAP 최대 6시간 |
| policy generation 분석 범위 | 최대 90일 CloudTrail 이벤트 |
| 생성된 정책 보관 | 최대 7일, 동시에 1개 |
| external access 분석 대상 | 리소스 15종 |
| internal access 분석 대상 | 리소스 6종 |

**Directory Service**

| 항목 | 값 |
| :--- | :--- |
| AWS Managed Microsoft AD Standard | 약 30,000 directory object |
| AWS Managed Microsoft AD Enterprise | 약 500,000 directory object |
| AD Connector 사이즈 | Small, Large |
| Simple AD 신규 도입 | 신규 고객 온보딩 중단 |

---

## 22. 답이 갈리는 짝 비교

| 짝 | 차이를 만드는 제약 |
| :--- | :--- |
| identity-based policy 대 resource-based policy | identity policy는 principal에 붙고 group에 붙일 수 있는 유일한 타입이다. resource policy는 리소스에 붙고 `Principal` 요소를 가진다. 같은 계정에서는 합집합이고 교차 계정에서는 양쪽 다 필요하다 |
| permissions boundary 대 SCP | boundary는 개별 user와 role에 붙고 group을 지원하지 않는다. SCP는 조직 트리에 붙고 management account의 principal에 적용되지 않는다. 둘 다 권한을 부여하지 않는다 |
| permissions boundary 대 session policy | boundary는 정책으로 저장되어 principal에 지속 부착된다. session policy는 세션 생성 시 넘기는 런타임 파라미터라 그 세션에만 살아 있고 새로 만드는 principal에 상속되지 않는다 |
| explicit deny 대 implicit deny | explicit deny는 어느 타입에 있든 이긴다. implicit deny는 resource-based policy가 지목한 ARN 종류에 따라 boundary와 session policy의 제한 여부가 갈린다 |
| role 가정 대 resource-based policy | role 가정은 원래 권한을 잃고 모든 서비스에서 쓸 수 있으며 대상 계정 로그에 세션 이름이 남는다. resource-based policy는 원래 권한을 유지해 두 계정 리소스를 한 작업에서 다룰 수 있지만 지원 서비스가 한정된다 |
| `AssumeRole` 대 `GetFederationToken` | `AssumeRole`은 상한 12시간이고 role의 권한을 가진다. `GetFederationToken`은 상한 36시간이고 IAM user 또는 root만 호출하며 `Policy`를 넘기지 않으면 권한이 없다. 세션 자격 증명으로 `GetFederationToken`을 부를 수 없다 |
| `GetSessionToken` 대 `AssumeRole` | `GetSessionToken`은 호출한 IAM user와 같은 권한의 세션을 주고 MFA 강제 용도로 쓴다. 권한을 바꾸려면 `AssumeRole`이다 |
| `AssumeRoleWithSAML` 대 `AssumeRoleWithWebIdentity` | 전자는 SAML 2.0 assertion, 후자는 OIDC ID token 또는 OAuth 2.0 access token을 받는다. 후자의 `ProviderId`는 OAuth 2.0 전용이고 `www.amazon.com`과 `graph.facebook.com`만 지원한다 |
| Cognito user pool 대 identity pool | user pool은 JWT를 발급하는 인증과 디렉터리다. identity pool은 그 JWT나 외부 토큰을 AWS 임시 자격 증명으로 바꾸는 브로커이고 미인증 사용자에게도 발급할 수 있다 |
| cross-account confused deputy 대 cross-service confused deputy | 전자는 서드파티가 role을 가정하는 경로이고 external ID로 막는다. 후자는 AWS 서비스가 리소스에 접근하는 경로이고 `aws:SourceArn` 계열 조건 키나 RCP로 막는다 |
| STS session tag 대 Identity Center attributes for access control | SAML attribute 이름이 `PrincipalTag:`와 `AccessControl:`로 다르다. 전자는 trust policy에 `sts:TagSession`이 필요하고 transitive 상속을 지정할 수 있다. 정책에서 참조하는 키는 둘 다 `aws:PrincipalTag`다 |
| session tag 대 role tag | session tag는 같은 키의 role tag를 override한다. role tag는 transitive로 지정할 수 없다 |
| SAML 직접 연동 대 IAM Identity Center | 직접 연동은 계정마다 IdP를 등록하고 role을 따로 만든다. Identity Center는 permission set을 여러 계정에 배포한다. `AssumeRoleWithSAML`은 `AWSReservedSSO_` role에 동작하지 않는다 |
| AWS Managed Microsoft AD 대 AD Connector | 전자는 실제 AD라 trust, schema extension, LDAPS, RDS SQL Server를 지원한다. 후자는 프록시라 캐싱과 trust가 없고 사용자 관리를 온프레미스에서만 한다 |
| AD Connector 대 Simple AD | AD Connector는 온프레미스 AD가 이미 있고 그 계정을 그대로 쓸 때다. Simple AD는 온프레미스 AD 없이 AWS 안에 저규모 디렉터리가 필요할 때이고 신규 고객 온보딩이 중단되었다 |
| external access analyzer 대 unused access analyzer | 전자는 zone of trust 밖의 접근을 찾고 리전마다 만들어야 한다. 후자는 미사용 권한과 자격 증명을 찾고 리전과 무관하며 role과 user 수로 과금한다 |
| policy validation 대 custom policy check | validation은 grammar와 best practice를 검사한다. custom policy check는 새 정책이 기존 대비 새 접근을 부여하는지와 지정한 critical action 허용 여부를 검사하고 API 요청 수로 과금한다 |
| policy generation 대 CloudTrail 감사 | generation은 최대 90일 이벤트로 정책 초안을 만들고 denied action도 포함하므로 감사에 쓰지 않는다. 감사는 CloudTrail이다 |
| policy simulator 대 실제 환경 검증 | simulator는 identity policy, boundary, SCP, 제공한 resource policy를 평가하고 RCP는 지원하지 않는다. 실제 요청을 보내지 않으므로 VPC endpoint policy나 role chaining이 걸린 구성은 결과가 다를 수 있다 |

---

## 23. 그럴듯하지만 성립하지 않는 조합

| 조합 | 성립하지 않는 이유 |
| :--- | :--- |
| permission boundary를 group에 붙여 개발팀 전체의 권한 상한을 정한다 | boundary는 user와 role만 지원한다 |
| permission boundary만 붙이면 그 범위의 권한이 생긴다 | boundary는 권한을 부여하지 않는다. identity-based policy가 별도로 필요하고 결과는 교집합이다 |
| boundary에 없는 액션이면 bucket policy로 허용해도 항상 막힌다 | resource-based policy가 IAM user ARN, role session ARN, federated user ARN에 직접 권한을 주면 boundary의 implicit deny가 막지 못한다. 확실히 막으려면 boundary에 explicit deny를 넣는다 |
| boundary는 resource-based policy를 전혀 제한하지 못한다 | role ARN에 준 권한은 제한한다. explicit deny는 어떤 ARN이든 제한한다 |
| resource-based policy를 role ARN에 부여했으니 session policy 제약을 우회한다 | role ARN 부여는 boundary와 session policy의 implicit deny에 제한된다. 우회되는 것은 role session ARN, IAM user ARN, federated user ARN이다 |
| resource-based policy에서 `NotPrincipal`과 `Deny`로 특정 principal만 예외로 둔다 | boundary가 붙은 IAM principal은 `NotPrincipal`에 무엇을 적었든 항상 deny된다. `ArnNotEquals`와 `aws:PrincipalArn`을 쓴다 |
| identity policy가 `sts:AssumeRole`을 허용하니 대상 role을 가정할 수 있다 | role trust policy는 principal에 대한 explicit Allow가 반드시 있어야 한다 |
| session policy로 role에 없는 권한을 임시로 더한다 | session policy는 role의 identity-based policy와의 교집합이라 권한을 확대할 수 없다 |
| session policy plaintext가 2,048자 미만이니 요청이 성공한다 | session policy와 session tag를 합쳐 압축한 packed size에 별도 한도가 있어 `PackedPolicyTooLarge`로 실패할 수 있다 |
| role chaining으로 12시간 세션을 유지한다 | chaining은 CLI와 API 세션을 최대 1시간으로 제한하고 초과 지정 시 operation 자체가 실패한다 |
| chaining 실패는 role의 maximum session duration을 올리면 해결된다 | role 설정과 무관하다. chaining을 제거하고 대상 role을 직접 가정해야 한다 |
| `AssumeRole`로 36시간 세션을 받아 배치 작업을 돌린다 | 36시간은 `GetFederationToken`과 `GetSessionToken`의 상한이고 `AssumeRole`은 12시간이 상한이다 |
| 세션 자격 증명으로 `GetFederationToken`을 불러 긴 세션을 얻는다 | `AssumeRole*`로 얻은 임시 자격 증명으로는 `GetFederationToken`과 `GetSessionToken`을 호출할 수 없다 |
| 콘솔에서 Switch Role로 ABAC용 session tag를 넘긴다 | 콘솔 Switch Role은 session tag를 넘길 수 없다. CLI나 API를 쓴다 |
| session tag만 넘기면 ABAC이 동작한다 | role trust policy에 `sts:TagSession`이 없으면 `AssumeRole` 자체가 실패한다 |
| role에 붙인 태그를 transitive로 지정해 체인 전체에 전파한다 | role tag는 transitive로 지정할 수 없다. 같은 값을 session tag로 다시 넘긴다 |
| `GetFederationToken` 세션에 transitive tag를 걸어 다음 role로 전달한다 | transitive 지정을 지원하지 않고, 그 자격 증명으로는 role을 가정할 수 없어 chaining이 성립하지 않는다 |
| 같은 속성을 `Department`와 `department` 두 키로 나눠 관리한다 | 태그 키는 대소문자를 구분하지 않는다. 두 키를 동시에 둘 수 없다 |
| SAML 연합으로 Identity Center permission set role을 직접 가정한다 | `AssumeRoleWithSAML`은 `AWSReservedSSO_`로 시작하는 role에 동작하지 않는다 |
| IdP가 SessionDuration을 8시간으로 주면 SAML 세션이 8시간이다 | `DurationSeconds`, assertion의 `SessionNotOnOrAfter`, role의 maximum session duration 중 가장 짧은 값이 이긴다 |
| unsigned `AssumeRoleWithSAML` 요청에 session policy를 넘겨 권한을 좁힌다 | 신뢰할 수 있는 중개자가 없으면 중간에서 제약이 제거될 수 있어 문서가 권고하지 않는다 |
| `GetFederationToken`으로 세션만 만들면 콘솔에서 리소스를 볼 수 있다 | `Policy`를 넘기지 않은 세션에는 어떤 권한도 없다. resource-based policy로만 접근이 성립한다 |
| 고객이 external ID를 정해 서드파티에 알려준다 | external ID는 서드파티가 고객마다 유일하게 생성해야 방어가 성립한다 |
| external ID를 Secrets Manager에 넣어 비밀로 관리한다 | AWS는 external ID를 비밀로 취급하지 않는다. 방어 원리는 비밀성이 아니라 값의 통제 주체다 |
| role ARN을 비공개로 유지해 confused deputy를 막는다 | ARN은 계정 ID와 role 이름으로 구성되어 비밀 유지가 방어 수단이 되지 못한다 |
| CloudTrail 중앙 버킷 정책에 `cloudtrail.amazonaws.com`만 허용하면 안전하다 | 조건 키가 없으면 버킷 이름을 아는 다른 계정의 로그도 들어온다. `aws:SourceArn`, `aws:SourceAccount`, `aws:SourceOrgID` 중 하나가 필요하다 |
| SCP로 AWS 서비스가 리소스에 접근하는 방향을 통제한다 | SCP는 조직 계정 안의 principal을 제한한다. 그 방향은 RCP나 resource-based policy 조건 키다 |
| Cognito user pool이 AWS 자격 증명을 발급한다 | user pool은 JWT를 발급하고 AWS 자격 증명은 identity pool이 `AssumeRoleWithWebIdentity`로 발급한다 |
| 교차 계정 role trust policy에 `cognito-identity.amazonaws.com`만 넣으면 된다 | `cognito-identity.amazonaws.com:aud` 조건으로 identity pool을 한정하지 않으면 다른 identity pool의 사용자가 role을 가정할 수 있다 |
| OIDC ID token으로 `AssumeRoleWithWebIdentity`를 부르며 `ProviderId`를 지정한다 | `ProviderId`는 OAuth 2.0 access token 전용이다. OIDC ID token에는 지정하지 않는다 |
| permission set session duration을 24시간으로 늘려 장기 작업을 돌린다 | 상한은 12시간이다 |
| SCIM 없이도 IdP 속성이 Identity Center에 자동으로 채워진다 | SCIM을 쓰지 않으면 사용자와 속성을 수동으로 만들어야 한다 |
| SAML로 넘어온 속성 이름을 Attributes for access control 페이지에서 확인한다 | SAML assertion으로 넘어온 속성은 그 페이지에 표시되지 않는다. 이름을 미리 알아야 한다 |
| AD Connector로 온프레미스 AD와 forest trust를 맺는다 | AD Connector는 프록시라 trust를 설정할 수 없다 |
| Simple AD로 RDS for SQL Server 인증을 붙인다 | Simple AD와 AD Connector 모두 RDS SQL Server와 호환되지 않는다. AWS Managed Microsoft AD만 지원한다 |
| Simple AD는 단종되어 기존 디렉터리도 만들 수 없다 | 신규 고객 온보딩만 중단되었고 기존 고객은 전체 기능을 유지하며 새 디렉터리도 만들 수 있다 |
| AWS Managed Microsoft AD Standard Edition으로 12만 객체를 담는다 | Standard는 약 30,000 객체 규모다. 12만이면 Enterprise Edition이다 |
| unused access analyzer를 리전마다 만들어 커버리지를 확보한다 | unused access finding은 리전에 따라 달라지지 않는다. 리전마다 필요한 것은 external access analyzer다 |
| external access analyzer를 하나만 만들어 전 리전을 본다 | external access analyzer는 활성화한 리전의 리소스만 분석한다 |
| policy generation으로 90일치 로그를 분석해 감사 보고서를 만든다 | 문서가 감사 용도 사용을 금지하고 CloudTrail을 쓰라고 명시한다. denied action까지 포함해 검토하기 때문이다 |
| Control Tower 조직 trail로 policy generation을 돌린다 | Control Tower가 만든 trail은 지원되지 않는다. 로그가 Log Archive 계정에 있고 버킷 권한이 SCP로 잠겨 있다 |
| 생성된 정책에 `iam:PassRole`이 없으니 그 role은 PassRole을 쓰지 않았다 | `iam:PassRole`은 CloudTrail이 추적하지 않아 생성 정책에 포함되지 않는다 |
| policy simulator로 RCP 적용 결과를 확인한다 | simulator는 RCP를 지원하지 않는다 |
| policy simulator가 대상 리소스의 정책을 자동으로 가져와 평가한다 | 콘솔이 아니면 리소스 정책을 대신 가져오지 않는다. 직접 제공해야 한다 |
| IAM group에 managed policy 20개를 붙인다 | group의 부착 상한은 10개이고 증설되지 않는다. role은 25개, user는 20개까지 늘릴 수 있다 |
| 계정에 `ADMINS`와 `admins` role을 각각 만든다 | user, group, role, instance profile 이름은 대소문자로 구별되지 않는다 |
| 교차 계정 `AssumeRole`이 대상 계정의 STS 쿼터를 소진한다 | 교차 계정 `AssumeRole`은 호출 계정의 쿼터만 소비한다 |

---

## 24. 예상 문제 10문항

**Q1.** 플랫폼팀이 서비스팀 개발자에게 IAM role 생성 권한을 위임하려 합니다. 개발자가 만든 role은 지정된 boundary 정책의 범위 안에서만 동작해야 하고, 개발자가 그 boundary를 떼어내거나 다른 정책으로 바꿀 수 없어야 합니다. 위임 자체는 유지해야 하며 플랫폼팀이 role 생성 요청을 대신 처리하는 방식은 배제되었습니다. MOST appropriate 구성은 무엇입니까?

- A. 개발자 그룹에 boundary 정책을 permission boundary로 부착하고 role 생성 권한을 부여한다
- B. 개발자에게 role 생성 권한을 주고 boundary 미부착 role을 AWS Config 규칙으로 탐지해 삭제한다
- C. `iam:CreateRole`과 `iam:PutRolePolicy`를 `iam:PermissionsBoundary` 조건과 묶어 지정 정책이 부착된 경우에만 허용하고, `iam:DeleteRolePermissionsBoundary`는 Deny한다
- D. 개발자 role에 session policy로 상한을 지정하고 role 생성 시 그 session policy를 상속시킨다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: C**

boundary 위임 패턴의 강제 수단은 `iam:PermissionsBoundary` 조건 키입니다. role과 user 생성 및 정책 부착 액션을 이 조건과 묶으면 지정한 boundary 정책이 붙은 경우에만 생성이 성립하고, boundary 제거 액션을 Deny하면 위임받은 개발자가 상한을 풀 수 없습니다.

- A가 틀린 이유: permission boundary는 IAM user와 role만 지원하고 group에는 부착할 수 없다. 부착이 가능하더라도 개발자 자신의 상한일 뿐 개발자가 만드는 role의 상한이 아니다.
- B가 틀린 이유: 탐지와 삭제는 사후 조치라 그 사이에 권한이 확대된 role이 존재한다. 요구는 생성 시점 강제다.
- D가 틀린 이유: session policy는 그 세션에만 적용되는 런타임 파라미터이고 새로 만들어지는 role에 상속되지 않는다.

</details>

**Q2.** 배치 처리를 담당하는 IAM user에 permission boundary가 부착되어 있습니다. boundary는 로그 버킷 ARN에 `s3:*`를 명시적으로 Deny하고 Secrets Manager 액션은 언급하지 않으며, 이 user의 identity-based policy에도 Secrets Manager 액션이 없습니다. secret의 resource policy와 로그 버킷 정책은 이 IAM user ARN에 각각 `secretsmanager:GetSecretValue`와 `s3:GetObject`를 허용합니다. 두 요청 모두 같은 계정 안에서 일어납니다. MOST accurate 결과는 무엇입니까?

- A. `s3:GetObject`는 차단되고 `secretsmanager:GetSecretValue`는 성공한다
- B. 두 요청 모두 성공한다
- C. 두 요청 모두 차단된다
- D. `s3:GetObject`는 성공하고 `secretsmanager:GetSecretValue`는 차단된다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: A**

permission boundary의 explicit deny는 resource-based policy를 항상 제한합니다. 반면 boundary의 implicit deny는 resource-based policy가 IAM user ARN에 직접 권한을 준 경우에는 그 접근을 제한하지 않습니다. 그래서 boundary가 명시적으로 Deny한 S3 요청은 버킷 정책이 허용해도 막히고, boundary가 언급하지 않은 Secrets Manager 요청은 secret의 resource policy만으로 성립합니다.

- B가 틀린 이유: boundary의 explicit deny는 어떤 경로로 부여된 권한이든 이긴다. S3 요청이 통과할 수 없다.
- C가 틀린 이유: 같은 계정에서 resource-based policy가 IAM user ARN에 직접 권한을 주면 identity-based policy와 boundary의 implicit deny에 걸리지 않는다.
- D가 틀린 이유: 두 요청의 결과가 뒤바뀌었다. 주체가 IAM user가 아니라 role이었다면 Secrets Manager 요청도 boundary의 implicit deny에 걸려 차단된다.

</details>

**Q3.** 배치 파이프라인이 계정 A의 실행 role을 가정한 뒤 그 세션 자격 증명으로 계정 B의 데이터 role을 다시 가정해 8시간 동안 데이터를 처리합니다. `DurationSeconds`를 28800으로 지정했더니 `AssumeRole` 호출 자체가 실패합니다. 파이프라인은 계정 B 리소스에 접근해야 하고 처리 도중 자격 증명을 갱신하는 로직은 넣지 않기로 결정되었습니다. MOST appropriate 해결책은 무엇입니까?

- A. 계정 B role의 maximum session duration을 12시간으로 올리면 chaining 상태에서도 8시간 세션을 받을 수 있다
- B. chaining을 없애고 파이프라인의 원래 자격 증명으로 계정 B role을 직접 가정하며, 그 role의 maximum session duration을 8시간 이상으로 설정한다
- C. 계정 A 세션에서 `GetFederationToken`을 호출해 36시간 자격 증명을 받는다
- D. `AssumeRole` 요청에 session policy를 넘겨 세션 길이 제한을 완화한다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: B**

role chaining은 CLI와 API 세션을 최대 1시간으로 제한하고, 1시간을 넘는 `DurationSeconds`를 주면 operation 자체가 실패합니다. chaining을 제거하고 계정 B role을 직접 가정하면 `AssumeRole`의 상한인 12시간 범위 안에서 role의 maximum session duration 설정에 따라 8시간 세션을 받을 수 있습니다.

- A가 틀린 이유: role의 maximum session duration을 올려도 chaining 상태의 1시간 제한은 그대로다. 실패 원인이 role 설정이 아니다.
- C가 틀린 이유: `AssumeRole` 계열로 얻은 임시 자격 증명으로는 `GetFederationToken`과 `GetSessionToken`을 호출할 수 없다.
- D가 틀린 이유: session policy는 role의 identity-based policy와 교집합을 만드는 권한 축소 수단이고 세션 길이와 무관하다.

</details>

**Q4.** SaaS 모니터링 업체가 고객 AWS 계정의 읽기 전용 role을 가정해 지표를 수집합니다. 보안 검토에서 다른 고객의 role ARN을 알아낸 제3자가 업체를 매개로 그 role을 가정하게 만들 수 있다는 confused deputy 위험이 지적되었습니다. 고객은 자기 계정에서만 설정을 바꿀 수 있고 업체 코드를 고칠 수는 없습니다. MOST appropriate 조치는 무엇입니까?

- A. 고객이 임의의 문자열을 external ID로 정해 업체 등록 화면에 입력하고 role trust policy의 `sts:ExternalId` 조건에 같은 값을 넣는다
- B. 업체가 생성한 external ID를 고객이 AWS Secrets Manager에 저장해 비밀로 관리한다
- C. 고객이 role ARN을 비공개로 유지하고 업체와 암호화 채널로만 교환한다
- D. 업체가 고객마다 유일한 external ID를 생성해 전달하고, 고객이 role trust policy의 `sts:ExternalId` 조건에 그 값을 넣는다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: D**

cross-account confused deputy 방어는 external ID입니다. 값을 서드파티가 고객마다 유일하게 생성해야 방어가 성립합니다. 서드파티가 값을 통제하므로 다른 고객의 role ARN만 아는 제3자는 올바른 external ID를 제시할 수 없습니다.

- A가 틀린 이유: 고객이 값을 정하면 두 고객이 같은 값을 쓸 수 있고 공격자가 자기 값을 등록해 맞출 수 있다. 문서는 고객이 정하지 말라고 명시한다.
- B가 틀린 이유: AWS는 external ID를 secret으로 취급하지 않는다. role을 볼 권한이 있는 사람은 값을 볼 수 있으므로 방어 원리가 비밀성이 아니다.
- C가 틀린 이유: role ARN은 계정 ID와 role 이름으로 구성되어 비밀 유지가 방어 수단이 되지 못한다. 문서도 ARN 비공개를 대책으로 제시하지 않는다.

</details>

**Q5.** 보안팀이 조직 전 계정의 S3 버킷과 SQS 큐에서 cross-service confused deputy 위험을 없애려 합니다. 각 팀이 소유한 resource-based policy를 하나씩 수정하는 절차는 배제되었고, AWS 서비스가 다른 서비스를 대신해 호출하는 요청만 대상으로 삼아야 하며, 사용자가 직접 보내는 요청은 영향을 받으면 안 됩니다. MOST appropriate 조치는 무엇입니까?

- A. 조직 root에 `aws:PrincipalOrgID` 조건으로 조직 밖 principal을 Deny하는 SCP를 부착한다
- B. IAM Access Analyzer external access analyzer를 조직 zone of trust로 만들어 finding을 교정한다
- C. `aws:PrincipalIsAWSService`가 true이고 `aws:SourceAccount`가 존재할 때 `aws:SourceOrgID` 일치를 요구하는 RCP를 조직 root에 부착한다
- D. 각 계정의 버킷 정책에 `aws:SourceArn` 조건을 추가하는 StackSets를 배포한다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: C**

RCP는 개별 resource-based policy를 고치지 않고 조직, OU, 계정 단위로 cross-service confused deputy 통제를 일괄 적용하는 수단입니다. `aws:PrincipalIsAWSService` 조건으로 AWS 서비스가 대신 보내는 요청만 골라내고, `aws:SourceOrgID` 일치를 요구해 다른 조직의 리소스를 대신한 호출을 막습니다. 사용자가 직접 보내는 요청은 조건에 걸리지 않습니다.

- A가 틀린 이유: SCP는 조직 계정 안의 principal을 제한하는 정책이라 AWS 서비스 주체가 리소스에 접근하는 방향을 통제하지 못한다.
- B가 틀린 이유: Access Analyzer는 탐지 도구다. 조건 키를 강제하지 않는다.
- D가 틀린 이유: 팀이 소유한 정책을 계정마다 수정하는 방식이라 배제된 전제와 충돌하고, 팀이 정책을 갱신하면 조건이 사라진다.

</details>

**Q6.** 회사가 외부 IdP를 SAML 2.0으로 연동하고 ABAC을 도입합니다. IdP가 보내는 `department` 속성을 세션 태그로 넘겨 `aws:PrincipalTag/department`로 접근을 제어하려 합니다. 테스트에서 IdP를 통한 로그인은 `AssumeRole` 단계에서 실패하고, 관리자가 AWS Management Console의 Switch Role로 같은 role에 들어가면 로그인은 되지만 태그가 request context에 나타나지 않습니다. MOST accurate 원인 설명은 무엇입니까?

- A. role trust policy에 `sts:TagSession`이 없어 세션 태그 전달이 실패하고, 콘솔 Switch Role은 애초에 세션 태그를 넘길 수 없다
- B. role에 `department` 태그가 없어 세션 태그가 매칭되지 않는다
- C. `department` 속성이 multi-valued로 전달되어 태그 키 충돌이 발생한다
- D. IAM 정책이 `aws:ResourceTag`를 써야 하는데 `aws:PrincipalTag`를 썼다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: A**

세션 태그를 넘기려면 API action 권한에 더해 `sts:TagSession` permissions-only action이 role trust policy에 있어야 합니다. 없으면 IdP에 연결된 role의 `AssumeRole` 호출 자체가 실패합니다. 그리고 AWS Management Console의 Switch Role 기능으로는 세션 태그를 넘길 수 없으므로 콘솔 경로에서는 태그가 request context에 들어오지 않습니다. 두 증상이 각각 다른 제약에서 나옵니다.

- B가 틀린 이유: 세션 태그는 role tag가 없어도 독립적으로 전달된다. 키가 같은 role tag가 있으면 세션 태그가 그것을 override할 뿐이다.
- C가 틀린 이유: session tag는 multi-valued를 지원하지 않지만 그 경우 값 전달 문제이지 콘솔 경로에서 태그가 사라지는 이유를 설명하지 못한다.
- D가 틀린 이유: 세션 태그를 principal 속성으로 참조하는 조건 키는 `aws:PrincipalTag`가 맞다. `aws:ResourceTag`는 대상 리소스의 태그를 본다.

</details>

**Q7.** 회사가 외부 SAML IdP와 IAM role을 직접 연동해 ABAC을 구성합니다. IdP의 사용자 속성 `costcenter`를 세션 태그로 전달하고, role chaining으로 두 번째 계정 role을 가정할 때도 같은 태그가 유지되어야 합니다. 콘솔이 아닌 CLI 경로만 사용합니다. 이 요구를 만족하기 위해 반드시 필요한 작업 두 가지는 무엇입니까? (Select TWO.)

- A. role에 `costcenter` 태그를 붙이고 그 태그를 transitive로 지정한다
- B. role trust policy에 `sts:TagSession` 액션을 허용한다
- C. `GetFederationToken`으로 세션을 만들고 그 자격 증명으로 두 번째 role을 가정한다
- D. IdP가 `https://aws.amazon.com/SAML/Attributes/PrincipalTag:costcenter` attribute와 `https://aws.amazon.com/SAML/Attributes/TransitiveTagKeys` attribute를 함께 전송한다
- E. session policy 문서에 태그 키와 값을 기재해 `AssumeRole` 요청에 넘긴다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: B, D**

세션 태그 전달에는 role trust policy의 `sts:TagSession` 허용이 필요합니다. `AssumeRoleWithSAML` 경로에서는 태그를 `PrincipalTag:{TagKey}` SAML attribute로 보내고, chaining의 다음 세션까지 상속시키려면 `TransitiveTagKeys` attribute로 해당 키를 transitive로 지정해야 합니다.

- A가 틀린 이유: role에 붙은 태그는 transitive로 지정할 수 없다. 같은 값을 세션 태그로 다시 넘겨야 한다.
- C가 틀린 이유: `GetFederationToken`은 transitive 지정을 지원하지 않고, 반환된 자격 증명으로는 role을 가정할 수 없어 chaining 자체가 성립하지 않는다.
- E가 틀린 이유: session policy는 권한을 축소하는 정책 문서이고 세션 태그 전달 경로가 아니다. 태그는 `Tags` 파라미터나 IdP attribute로 넘긴다.

</details>

**Q8.** 온프레미스 Active Directory를 운영하는 회사가 워크로드를 AWS로 옮깁니다. 요구는 세 가지입니다. EC2 Windows 인스턴스를 도메인에 조인해야 하고, Amazon RDS for SQL Server의 Windows 인증을 사용해야 하며, 온프레미스 포리스트와 양방향 신뢰를 맺어 기존 사용자 계정을 그대로 써야 합니다. 디렉터리 객체는 약 12만 개이고 향후 증가가 예상됩니다. MOST appropriate 선택은 무엇입니까?

- A. AD Connector를 배포해 온프레미스 AD로 인증을 프록시한다
- B. Simple AD를 배포하고 온프레미스 AD와 신뢰를 설정한다
- C. AWS Managed Microsoft AD Standard Edition을 배포한다
- D. AWS Managed Microsoft AD Enterprise Edition을 배포한다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: D**

세 요구를 모두 만족하는 것은 AWS Managed Microsoft AD입니다. 실제 Microsoft Windows Server Active Directory이므로 도메인 조인, RDS for SQL Server 연동, 온프레미스 포리스트와의 양방향 신뢰를 지원합니다. 객체 수 12만 개는 Standard Edition의 약 30,000 객체 범위를 넘고 Enterprise Edition의 약 500,000 객체 범위에 들어갑니다.

- A가 틀린 이유: AD Connector는 프록시라 신뢰 관계를 설정할 수 없고 RDS for SQL Server와도 호환되지 않는다.
- B가 틀린 이유: Simple AD는 신뢰 관계, schema extension, LDAPS, MFA를 지원하지 않고 RDS for SQL Server와도 호환되지 않는다.
- C가 틀린 이유: 기능은 만족하지만 Standard Edition의 지원 규모가 약 30,000 객체라 12만 개 요구를 담지 못한다.

</details>

**Q9.** 보안팀이 조직 전체에서 사용되지 않는 IAM role과 user를 찾아 정리하려 합니다. 조직은 6개 리전을 사용합니다. 담당자가 리전마다 unused access analyzer를 하나씩 만들었더니 청구액이 예상의 6배가 되었고 finding 내용은 리전마다 동일했습니다. 커버리지는 그대로 유지해야 합니다. MOST cost-effective 조치는 무엇입니까?

- A. analyzer 수는 유지하고 분석 주기를 늘려 과금을 줄인다
- B. 조직을 zone of trust로 하는 unused access analyzer를 하나만 남기고 나머지 리전의 analyzer를 삭제한다
- C. unused access analyzer를 external access analyzer로 교체한다
- D. analyzer를 모두 삭제하고 IAM Access Analyzer policy generation으로 미사용 권한 보고서를 만든다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: B**

unused access finding은 리전에 따라 달라지지 않으므로 리전마다 analyzer를 만들 필요가 없습니다. 과금 기준이 analyzer당 분석 대상 IAM role과 user 수이므로 리전 수만큼 중복 과금이 발생합니다. 하나만 남겨도 커버리지가 동일합니다.

- A가 틀린 이유: 과금은 분석 대상 role과 user 수 기준이라 주기 조정으로 줄지 않는다. 사용자가 조정할 수 있는 분석 주기 설정도 아니다.
- C가 틀린 이유: external access analyzer는 zone of trust 밖에 열린 접근을 찾는 도구라 미사용 자격 증명을 식별하지 못한다. 게다가 external은 리전마다 만들어야 한다.
- D가 틀린 이유: policy generation은 CloudTrail 이벤트로 정책 초안을 만드는 기능이고, 문서가 감사 용도로 쓰지 말라고 명시한다. 미사용 role 식별 수단이 아니다.

</details>

**Q10.** 모바일 앱이 Amazon Cognito user pool로 로그인하고 identity pool을 통해 다른 AWS 계정에 있는 S3 버킷 접근용 IAM role을 가정합니다. 보안 검토에서 이 role의 trust policy가 `cognito-identity.amazonaws.com` 서비스 주체를 신뢰하기만 해서 다른 identity pool의 사용자도 같은 role을 가정할 수 있다는 지적이 나왔습니다. 앱 코드는 수정하지 않기로 했습니다. MOST appropriate 조치는 무엇입니까?

- A. trust policy의 Principal을 앱을 소유한 계정 root로 바꾼다
- B. identity pool에서 unauthenticated 액세스를 비활성화한다
- C. trust policy에 `cognito-identity.amazonaws.com:aud` 조건 키를 추가해 허용할 identity pool ID를 한정한다
- D. S3 버킷 정책에 `aws:SourceAccount` 조건을 추가한다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: C**

Cognito identity pool이 교차 계정 role을 가정하려면 그 role의 trust policy가 `cognito-identity.amazonaws.com` 서비스 주체를 신뢰하고 `cognito-identity.amazonaws.com:aud` 조건 키로 identity pool을 한정해야 합니다. 이 조건이 없으면 다른 identity pool의 사용자가 같은 role을 가정할 수 있습니다.

- A가 틀린 이유: Principal을 계정 root로 바꾸면 Cognito가 role을 가정하는 경로 자체가 끊겨 앱이 동작하지 않는다.
- B가 틀린 이유: unauthenticated 액세스 비활성화는 guest 사용자 발급을 막을 뿐 다른 identity pool의 인증된 사용자를 막지 못한다.
- D가 틀린 이유: `aws:SourceAccount`는 AWS 서비스가 대신 호출하는 cross-service 시나리오의 조건 키다. role 가정 주체를 identity pool 단위로 한정하지 못한다.

</details>

---

## 25. Reference

- [AWS IAM - Policy evaluation logic](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_evaluation-logic.html)
- [AWS Organizations - Service control policies](https://docs.aws.amazon.com/organizations/latest/userguide/orgs_manage_policies_scps.html)
- [AWS IAM - Cross-account resource access](https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies-cross-account-resource-access.html)
- [AWS IAM - Determining whether a request is allowed or denied within an account](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_evaluation-logic_policy-eval-denyallow.html)
- [AWS IAM - Request context](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_evaluation-logic_policy-eval-reqcontext.html)
- [AWS IAM - Permissions boundaries for IAM entities](https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies_boundaries.html)
- [AWS IAM - Policies and permissions in AWS Identity and Access Management](https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies.html)
- [AWS IAM - IAM and AWS STS quotas](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_iam-quotas.html)
- [AWS IAM - Requesting temporary security credentials](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_temp_request.html)
- [AWS STS - AssumeRole](https://docs.aws.amazon.com/STS/latest/APIReference/API_AssumeRole.html)
- [AWS STS - AssumeRoleWithSAML](https://docs.aws.amazon.com/STS/latest/APIReference/API_AssumeRoleWithSAML.html)
- [AWS STS - AssumeRoleWithWebIdentity](https://docs.aws.amazon.com/STS/latest/APIReference/API_AssumeRoleWithWebIdentity.html)
- [AWS IAM - Passing session tags in AWS STS](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_session-tags.html)
- [AWS IAM - Cross-service confused deputy prevention](https://docs.aws.amazon.com/IAM/latest/UserGuide/confused-deputy.html)
- [AWS IAM - Providing access to AWS accounts owned by third parties](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_common-scenarios_third-party.html)
- [AWS IAM - What is IAM Access Analyzer?](https://docs.aws.amazon.com/IAM/latest/UserGuide/what-is-access-analyzer.html)
- [AWS IAM - IAM Access Analyzer policy generation](https://docs.aws.amazon.com/IAM/latest/UserGuide/access-analyzer-policy-generation.html)
- [AWS IAM - IAM policy testing with the IAM policy simulator](https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies_testing-policies.html)
- [AWS IAM Identity Center - Set session duration](https://docs.aws.amazon.com/singlesignon/latest/userguide/howtosessionduration.html)
- [AWS IAM Identity Center - Attributes for access control](https://docs.aws.amazon.com/singlesignon/latest/userguide/attributesforaccesscontrol.html)
- [AWS IAM Identity Center - Attribute-based access control](https://docs.aws.amazon.com/singlesignon/latest/userguide/abac.html)
- [AWS IAM Identity Center - SCIM profile and SAML 2.0 implementation](https://docs.aws.amazon.com/singlesignon/latest/userguide/scim-profile-saml.html)
- [AWS Directory Service - What is AWS Directory Service?](https://docs.aws.amazon.com/directoryservice/latest/admin-guide/what_is.html)
- [AWS Directory Service - AWS Managed Microsoft AD](https://docs.aws.amazon.com/directoryservice/latest/admin-guide/directory_microsoft_ad.html)
- [AWS Directory Service - AD Connector](https://docs.aws.amazon.com/directoryservice/latest/admin-guide/directory_ad_connector.html)
- [AWS Directory Service - Simple AD](https://docs.aws.amazon.com/directoryservice/latest/admin-guide/directory_simple_ad.html)
- [AWS Directory Service - Simple AD availability change](https://docs.aws.amazon.com/directoryservice/latest/admin-guide/simple-ad-availability-change.html)
- [Amazon Cognito - Amazon Cognito identity pools](https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-identity.html)
- [Amazon Cognito - IAM roles](https://docs.aws.amazon.com/cognito/latest/developerguide/iam-roles.html)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
