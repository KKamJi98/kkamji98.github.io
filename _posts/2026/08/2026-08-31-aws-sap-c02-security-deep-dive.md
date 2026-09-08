---
title: "SAP-C02 박살내기 9 - 보안 심화"
author: kkamji
categories: [Certification, AWS SAP-C02]
tags: [aws, sap-c02, certification, kms, cloudhsm, secrets-manager, acm, waf, shield, guardduty, config, security-hub]
comments: true
image:
  path: /assets/img/aws/aws.webp
date: 2026-08-31 10:00:00 +0900
---

S3 버킷을 암호화하고 WAF를 붙인 뒤에도 보안 사고의 원인은 하나의 서비스에서 끝나지 않습니다. 키 정책이 교차 계정 호출을 막고, WAF가 본문을 일부만 검사하며, GuardDuty가 위협을 찾고, Config가 설정 위반을 교정해야 전체 통제가 닫힙니다. 어느 서비스가 무엇을 보장하는지 분리하지 않으면 보안 도구를 많이 켜도 빈틈이 남습니다.

이 글은 암호화 키의 소유와 위치를 정하는 선택에서 시작해 탐지 결과를 자동 교정과 보존 증적으로 연결합니다. 서비스별 기능 나열 대신 요구사항, 경계, 실패 지점을 기준으로 설계를 좁혀 갑니다. AWS 문서의 현재 표기인 `Security Hub CSPM`과 WAF의 `web ACL`을 사용하며, 가격과 리전별 제공 여부처럼 변할 수 있는 값은 확인일을 함께 적습니다.

> **TL;DR**  
> - KMS key의 origin과 key type은 생성 후 바꿀 수 없고, 자동 rotation은 `AWS_KMS` origin 대칭 암호화 customer managed key에만 적용한다.  
> - CloudHSM key store는 전용 HSM의 256-bit AES 대칭 키만 KMS와 연결한다. 비대칭 서명이나 imported material은 CloudHSM API를 직접 사용한다.  
> - multi-Region key는 애플리케이션의 client-side 암호화에서 리전 간 같은 ciphertext를 다루게 하지만, S3 CRR을 재암호화 없이 만들지는 않는다.  
> - KMS 교차 계정 호출은 key policy와 호출 계정 IAM policy가 모두 허용해야 한다. S3 Bucket Key는 비용을 줄이지만 encryption context를 bucket ARN으로 바꾼다.  
> - 자동 교체와 8 KB를 넘는 값이 필요하면 Secrets Manager를 선택한다. 단순 설정값은 Parameter Store가 더 단순하다.  
> - ACM 인증서는 리전 리소스이며 CloudFront용은 `us-east-1`에 있어야 한다. exportable public certificate는 갱신 알림까지 ACM이 하고 서버 재배포는 사용자가 한다.  
> - ALB와 AppSync의 WAF body 검사 한도는 8 KB로 고정이다. 64 KB 검사가 필요하면 CloudFront 같은 지원 리소스에서 검사한다.  
> - GuardDuty는 foundational 로그를 독립 스트림으로 읽고, Extended Threat Detection은 24시간 안의 신호를 묶는다. Inspector는 취약점, Macie는 S3 민감 데이터, Detective는 원인 조사를 담당한다.  
> - Security Hub CSPM은 표준 준수 결과를 모으고, Config rule의 remediation은 SSM Automation이 실행한다.  
> - Object Lock은 S3 객체 버전, Vault Lock은 AWS Backup recovery point를 보호한다. compliance mode는 되돌릴 수 없는 시점을 만든다.  
{: .prompt-info}

---

## 1. 보안 요구사항을 키 소유, 경계, 증적으로 나눈다

보안 설계 문항에서 먼저 해야 할 일은 서비스 이름을 떠올리는 것이 아니라 보호 대상과 실패 시 영향 범위를 적는 것입니다. 다음 세 질문을 순서대로 답하면 선지가 빠르게 좁혀집니다.

1. 키와 원문을 누가 통제해야 하는가?
2. 요청이 어느 경계를 넘어가며, 어느 정책이 그 경계를 강제하는가?
3. 사고 또는 위반을 어떤 증적으로 발견하고 어떻게 닫을 것인가?

예를 들어 온프레미스 HSM에서 만든 소재를 AWS에 가져와야 한다면 `EXTERNAL` origin을 검토합니다. AWS가 생성한 소재를 쓰되 애플리케이션에서 매년 재암호화하지 않으려면 자동 rotation을 지원하는 `AWS_KMS` origin 대칭 키가 간단합니다. AWS 서비스가 직접 사용하는 키가 아니라 서명 알고리즘과 단일 테넌시를 함께 요구한다면 CloudHSM을 KMS와 같은 것으로 취급하면 안 됩니다.

요청 경계도 같은 방식으로 구분합니다. KMS key policy와 S3 bucket policy는 리소스에 붙는 정책이고, IAM policy는 principal에 붙습니다. AWS Organizations의 SCP는 계정 트리의 상한이며 Config rule은 이미 만들어진 리소스의 상태를 평가합니다. Config aggregator와 Security Hub CSPM은 데이터를 모으지만 원본 계정의 설정을 대신 고치지 않습니다.

IAM Access Analyzer의 external access와 unused access 판정은 2편에서 다룬 정책 감사 영역입니다. 이 편에서는 해당 결과가 Security Hub CSPM에 집계되어 remediation 우선순위의 입력이 될 수 있다는 연결만 기억합니다.

탐지와 조사는 다른 단계입니다. GuardDuty가 위협 finding을 만들고 Inspector가 CVE와 노출 경로를 찾습니다. Detective는 이미 수집한 사건을 시간축과 엔터티 그래프로 연결합니다. Security Hub CSPM은 이 결과와 구성 준수 결과를 한 화면에 모으고, EventBridge 또는 Config remediation이 실제 실행으로 넘깁니다.

아래 그림은 키 소재를 어디에서 만들지 선택하면 rotation, multi-Region, 비대칭 키 사용 가능성이 함께 고정되는 경계를 보여줍니다.

{% include diagrams/static/sap-c02/kms-key-material-origin.html %}
{% include diagrams/download.html png="/assets/img/diagrams/static/sap-c02/kms-key-material-origin--1dfa3aa5755dafe5.png" %}

그림의 핵심은 origin을 나중에 바꾸는 설정 항목으로 보지 않는 것입니다. 처음 선택이 잘못되면 기존 ciphertext와 애플리케이션 호출을 그대로 둔 채 기능만 추가할 수 없습니다.

---

## 2. KMS key type과 origin이 이후 선택지를 잠근다

KMS에서 `KeySpec` 또는 사용 목적과 key material origin을 별개의 축으로 기억해야 합니다. 대칭 암호화 키는 `Encrypt`와 `Decrypt`에 쓰고, 비대칭 키는 공개 키를 배포해 `Sign`, `Verify`, `Encrypt`, `Decrypt` 같은 용도에 씁니다. HMAC 키는 공유 비밀을 이용한 메시지 인증에 쓰며, 세 종류를 rotation 규칙이 같다고 가정하면 안 됩니다.

origin은 소재의 생성 위치를 뜻합니다.

| origin | 소재를 만드는 주체 | 자동 rotation | on-demand rotation | 핵심 제약 |
| :--- | :--- | :--- | :--- | :--- |
| `AWS_KMS` | AWS KMS가 관리형 HSM에서 생성 | 대칭 암호화 customer managed key에서 지원 | 대칭 암호화에서 지원 | 가장 넓은 KMS 통합 |
| `EXTERNAL` | 사용자가 만든 소재를 import | 지원하지 않음 | 대칭 암호화에서 지원 | 소재 만료와 삭제를 사용자가 관리 |
| CloudHSM key store | 계정 소유 HSM cluster 안에서 KMS가 생성 | 지원하지 않음 | 지원하지 않음 | 256-bit AES 대칭 키만 지원 |

AWS 관리형 키와 AWS 소유 키도 customer managed key의 하위 유형이 아닙니다. AWS managed key는 서비스가 만들고 약 365일 주기로 자동 rotation하지만 key policy를 사용자가 편집할 수 없습니다. AWS owned key는 서비스가 rotation 방식을 정하고 사용자 계정에서 키가 보이지 않을 수 있습니다. 교차 계정 정책이나 직접 삭제 일정이 요구되면 customer managed key가 필요합니다.

`EXTERNAL` 키는 소재의 수명까지 설계해야 합니다. 하나라도 만료되거나 삭제되면 그 KMS key를 사용할 수 없습니다. 반대로 `AWS_KMS` origin은 rotation을 꺼도 이전 소재를 KMS가 보관하며, 키 삭제 대기 기간이 끝날 때까지 소재가 없어지지 않습니다. rotation은 소재를 바꾸는 작업이지 data key로 이미 암호화한 객체를 재암호화하는 작업이 아닙니다.

---

## 3. rotation은 소재만 바꾸고 논리적 키는 유지한다

자동 rotation을 켤 수 있는 조건을 먼저 외웁니다. 대칭 암호화, customer managed key, `AWS_KMS` origin 세 가지가 모두 맞아야 합니다. 기간은 `RotationPeriodInDays`로 지정하며 90일부터 2,560일까지 설정할 수 있고 기본값은 365일입니다. 이 기간은 활성화 시점부터 첫 rotation까지의 일수이자 이후 rotation 사이의 간격입니다.

```text
대칭 암호화 + customer managed + AWS_KMS
  -> 자동 rotation 90-2560일
대칭 암호화 + EXTERNAL
  -> on-demand rotation 또는 새 key를 만드는 수동 rotation
비대칭, HMAC, custom key store
  -> 새 key 생성 후 alias를 옮기는 수동 rotation
```

on-demand rotation은 자동 rotation이 켜져 있는지와 관계없이 즉시 소재를 바꾸는 경로입니다. `AWS_KMS` origin과 `EXTERNAL` origin의 대칭 암호화 키에서 사용할 수 있지만, 키 하나당 최대 25회라는 조정 불가 quota가 있습니다. 규제 증적이나 계획되지 않은 긴급 교체에 유용하지만, 정기 교체는 자동 rotation을 우선합니다.

rotation 후에도 key ID와 ARN, 리전, key policy, 권한은 그대로입니다. Encrypt 또는 GenerateDataKey는 현재 소재를 사용하고, Decrypt는 ciphertext를 만든 이전 소재를 KMS가 자동으로 선택합니다. 따라서 애플리케이션이 ARN을 하드코딩했어도 일반적인 KMS rotation에는 코드 수정이나 기존 데이터 재암호화가 필요하지 않습니다. 다만 키가 노출된 사고라면 rotation만으로 data key의 피해를 되돌릴 수 없으므로 별도의 재암호화와 폐기 절차가 필요합니다.

rotation 상태는 KMS 콘솔과 `GetKeyRotationStatus`, `ListKeyRotations`로 확인하고, CloudTrail의 `RotateKey`와 EventBridge의 `KMS CMK Rotation` 이벤트를 감사 증적으로 남길 수 있습니다. 리전이 여러 개인 multi-Region key는 primary에서만 rotation을 시작하고 KMS가 replica로 소재를 동기화합니다. 새 소재가 모든 관련 리전에 준비되기 전에는 그 소재로 암호화하지 않습니다.

---

## 4. multi-Region key는 암호문 이동을 단순하게 만들지만 global key는 아니다

multi-Region key는 같은 key ID와 key material을 공유하는 primary 및 replica 집합입니다. 같은 AWS partition 안에서 리전별 replica를 만들 수 있고, 리전마다 primary 또는 replica 하나만 둘 수 있습니다. 리전 전체에서 하나의 global policy를 공유하는 키는 아닙니다. key policy, grant, alias, tag, enabled 상태는 각 리전에서 독립적입니다.

client-side 암호화 애플리케이션이 us-east-1에서 만든 ciphertext를 ap-northeast-2에서 처리해야 한다고 가정해 보겠습니다. 두 리전에 related key가 있으면 ap-northeast-2의 KMS endpoint가 같은 소재로 복호화할 수 있어 애플리케이션이 원문을 먼저 옮기거나 교차 리전 KMS 호출을 할 필요가 줄어듭니다. 단일 리전 key를 나중에 multi-Region으로 승격할 수는 없으므로 기존 ciphertext는 새 키로 한 번 재암호화해야 합니다.

반대로 AWS 서비스가 서버측 복제에서 multi-Region key를 쓴다고 해서 항상 재암호화가 사라지는 것은 아닙니다. S3 Cross-Region Replication은 목적지 리전의 키로 data key를 다시 암호화합니다. 이 경우 MRK는 키 관리의 일관성을 줄 수 있지만 CRR 데이터 경로의 재암호화 요구를 없애지 않습니다.

CloudHSM key store에는 multi-Region key를 만들 수 없습니다. `EXTERNAL` origin의 multi-Region 대칭 키는 만들 수 있지만, primary와 각 replica에 같은 소재를 개별 import한 뒤 primary에서 on-demand rotation을 시작해야 합니다. 한 replica의 소재만 만료시키면 관련 키 중 그 replica는 사용할 수 없게 됩니다.

---

## 5. CloudHSM과 KMS의 책임 경계

KMS는 AWS 서비스와의 통합이 넓고 key policy와 IAM으로 권한을 관리하는 관리형 서비스입니다. CloudHSM은 계정의 전용 HSM cluster를 운영자가 관리하며, 표준 라이브러리와 직접 통합할 수 있습니다. 두 서비스를 고르는 기준은 성능보다 키 소재와 운영 책임의 경계입니다.

| 요구 | KMS | CloudHSM |
| :--- | :--- | :--- |
| AWS 서비스가 직접 SSE 키를 사용 | 대부분 바로 통합 | KMS custom key store를 통해 통합 |
| 키 소재 단일 테넌시 | AWS 관리형 HSM에서 처리 | 계정 소유 cluster에 보관 |
| RSA 서명, PKCS#11, Oracle TDE | KMS가 지원하는 key spec 범위 | 표준 라이브러리로 직접 사용 |
| HSM 사용자와 백업을 직접 관리 | 불필요 | 운영자가 책임짐 |
| 자동 rotation | 지원되는 KMS key에서 가능 | KMS custom key store에서는 불가 |

CloudHSM key store는 CloudHSM cluster와 KMS API를 이어 주는 선택지입니다. KMS가 cluster에 `kmsuser` crypto user로 로그인해 256-bit persistent non-exportable AES 대칭 키를 만들고, 암호 연산은 HSM에서 수행합니다. cluster가 disconnected 상태면 키 속성 조회와 관리 일부는 가능하지만 새 키 생성과 암호 연산은 불가능합니다.

초기 cluster에는 서로 다른 AZ에 active HSM이 최소 두 개 있어야 custom key store에서 KMS key를 만들 수 있습니다. 다른 관리 작업은 HSM 하나로도 가능하지만, 가용성을 위해 두 AZ 이상을 유지해야 합니다. CloudHSM이 지원하는 일반 키 종류가 많아도 KMS custom key store가 지원하는 것은 대칭 AES 하나라는 차이를 놓치지 마십시오. 비대칭 서명 요구가 함께 있으면 S3와 EBS 암호화용 KMS key와 CloudHSM 직접 서명용 키를 분리합니다.

CloudHSM을 선택해도 KMS custom key store를 호출하는 권한 검사는 남습니다. HSM 내부 사용자를 직접 관리하는 책임이 추가될 뿐 key policy와 IAM policy를 건너뛸 수 있는 별도 경로가 생기는 것은 아닙니다.

---

## 6. key policy, IAM policy, grant를 함께 평가한다

모든 KMS key에는 key policy가 있습니다. 일반적인 resource-based policy처럼 계정에 권한을 자동 위임한다고 생각하면 틀립니다. KMS key policy에 `Enable IAM User Permissions` 문장처럼 계정 root principal을 통한 계정 위임이 없으면, 호출자 IAM policy의 `Allow`만으로 KMS 호출이 열리지 않습니다. 반대로 IAM policy의 `Deny`는 key policy가 위임하지 않아도 유효합니다.

교차 계정 SSE-KMS 요청은 다음 네 요소를 확인합니다.

1. S3 bucket policy가 상대 계정 principal의 `GetObject`를 허용하는가?
2. 호출 role의 IAM policy가 `s3:GetObject`와 `kms:Decrypt`를 허용하는가?
3. KMS key policy가 상대 계정 또는 role을 허용하는가?
4. key policy, IAM policy, SCP, VPC endpoint policy 중 명시적 Deny가 있는가?

{% include diagrams/static/sap-c02/kms-cross-account-key-access.html %}
{% include diagrams/download.html png="/assets/img/diagrams/static/sap-c02/kms-cross-account-key-access--973f36691907d441.png" %}

예를 들어 데이터 계정의 key policy가 분석 계정에 위임하지 않으면 분석 role에 `kms:Decrypt`를 추가해도 `AccessDenied`가 납니다. AWS managed key인 `aws/s3`는 key policy를 편집할 수 없고 교차 계정 공유에 쓸 수 없으므로 customer managed key로 전환해야 합니다.

grant는 key policy와 IAM policy를 대체하는 만능 우회가 아닙니다. KMS key에 특정 principal이 일시적으로 암호 연산을 하도록 권한을 위임하는 별도 객체이며, AWS 서비스가 사용자를 대신해 grant를 만들 때 `kms:GrantIsForAWSResource` 조건을 걸어 직접 grant 생성을 막는 패턴이 자주 사용됩니다. 키 하나의 grant quota는 50,000개이며, 많은 EBS 볼륨이나 서비스 통합을 하나의 키에 몰아넣으면 이 한도에 도달할 수 있습니다.

customer managed key quota는 계정과 리전당 100,000개, 키당 alias는 50개, custom key store는 10개입니다. on-demand rotation 25회를 제외한 수치는 조정 가능한지 확인하고, 조정 요청을 보안 경계 설계의 대체 수단으로 사용하지 않습니다.

---

## 7. Parameter Store와 Secrets Manager는 수명주기가 다르다

Parameter Store는 경로 기반 설정값과 런타임 플래그를 저장하기에 단순합니다. Standard tier는 값 4 KB, 계정과 리전당 10,000개, parameter policy와 교차 계정 공유를 지원하지 않으며 추가 요금이 없습니다. Advanced tier는 값 8 KB, 100,000개, parameter policy와 교차 계정 공유를 지원하지만 유료입니다. Standard에서 Advanced로 올릴 수는 있어도 되돌리기는 삭제 후 재생성이 필요합니다.

Parameter policy의 만료 알림은 교체 시점을 알리는 기능입니다. 비밀번호나 인증서를 새 값으로 바꾸는 rotation을 대신 실행하지 않습니다. 특히 8 KB를 넘는 인증서 번들과 파트너 API 호출이 필요한 교체는 Parameter Store의 tier를 바꾸는 것으로 해결되지 않습니다.

Secrets Manager는 secret value 최대 65,536 bytes와 리전당 secret 500,000개를 제공합니다. rotation은 세 경로로 나뉩니다.

| rotation 유형 | 적합한 상황 | 운영 책임 |
| :--- | :--- | :--- |
| managed rotation | 지원되는 AWS managed secret | AWS가 rotation Lambda와 흐름을 관리 |
| managed external secrets rotation | 지원되는 외부 파트너 secret | 파트너 시스템과의 교체 흐름을 연결 |
| Lambda 기반 rotation | 사용자 정의 API와 데이터베이스 | 사용자가 단계별 Lambda와 롤백을 구현 |

`PutSecretValue` 또는 `UpdateSecret`을 10분에 한 번보다 자주 지속 호출하지 않는 것이 좋습니다. 호출마다 새 버전이 생기고, 라벨이 없는 버전은 100개를 넘을 때 정리되지만 최근 24시간 이내 버전은 즉시 정리되지 않아 quota에 걸릴 수 있습니다. 교차 계정 읽기에서는 throttling이 secret 소유 계정이 아니라 호출 신원의 계정에 적용됩니다.

비용만 보면 작은 설정값에는 Parameter Store Standard가 간단합니다. 자동 rotation, 교차 계정 읽기, 큰 번들 중 하나라도 요구되면 Secrets Manager의 수명주기 기능을 기준으로 판단합니다. 단순히 S3에 파일을 넣고 bucket policy로 공유하면 버전 교체, 실패 시 이전 값 복구, 애플리케이션의 `AWSPENDING`과 `AWSCURRENT` 전환을 직접 구현해야 합니다.

---

## 8. ACM 인증서는 발급 경로와 설치 위치를 함께 본다

ACM 인증서는 리전 리소스입니다. 같은 FQDN을 여러 리전의 ELB에 연결하려면 리전마다 요청하거나 임포트하고 도메인 검증을 다시 해야 합니다. CloudFront 배포에 사용할 인증서는 `us-east-1`에서 요청하거나 임포트해야 하며, 해당 인증서가 배포에 설정한 엣지 위치로 배포됩니다.

일반 ACM public certificate는 AWS가 private key를 만들고 관리하며 AWS 통합 서비스에 바인딩합니다. ACM 관리형 인증서 자체에는 추가 요금이 없고, 연결한 AWS 리소스 요금만 발생합니다. EC2나 컨테이너나 온프레미스 서버에 같은 공인 인증서를 설치해야 하는 경우에는 요청할 때 exportable public certificate를 선택합니다.

exportable public certificate는 198일 유효하고 ACM이 만료 45일 전에 갱신합니다. export할 때 인증서, 체인, passphrase로 암호화된 private key를 함께 받습니다. ACM은 새 인증서가 준비됐다는 EventBridge 알림을 보낼 뿐 서버 파일 교체와 프로세스 reload까지 해 주지 않습니다. 갱신 배포 파이프라인과 private key 저장 권한을 별도로 설계해야 합니다. 2025년 6월 17일 이전에 만든 일반 ACM public certificate는 export 대상으로 바꿀 수 없으므로 새 exportable 인증서를 발급해야 합니다.

ACM과 ACME, Private CA의 경계는 다음과 같습니다.

| 경로 | 신뢰 체계 | private key 보유 | 갱신과 배포 | AWS 통합 서비스 바인딩 |
| :--- | :--- | :--- | :--- | :--- |
| ACM 일반 | 공인 또는 Private CA | AWS가 관리 | ACM 자동 갱신과 자동 바인딩 | 가능 |
| ACM exportable public | 공인 | ACM에서 export 후 사용자 | ACM 갱신 알림, 사용자가 재배포 | AWS 통합과 자체 서버 모두 가능 |
| ACM with ACME | 공인 | ACME client가 생성하고 보유 | client가 갱신과 설치 | ACM inventory에는 보이지만 불가 |
| Private CA 직접 발급 | 사설 | 사용자가 CSR과 키를 보유 | `IssueCertificate` 재호출 | 사설 용도 |

{% include diagrams/static/sap-c02/acm-certificate-issuance-paths.html %}
{% include diagrams/download.html png="/assets/img/diagrams/static/sap-c02/acm-certificate-issuance-paths--951f64dd164147e7.png" %}

ACME는 Certbot이나 cert-manager 같은 표준 client를 사용해 자체 인프라를 자동화하려는 경로입니다. ACM API 대신 client가 키를 만들고, ACME로 발급된 인증서는 AWS 통합 서비스에 바인딩할 수 없습니다. 공인 신뢰와 AWS 서비스 바인딩을 모두 요구하면 exportable public certificate의 재배포 책임까지 감수하는지 확인합니다.

---

## 9. S3 서버측 암호화와 Bucket Key의 경계

S3는 2023년 1월 5일부터 신규 객체 업로드를 SSE-S3로 자동 암호화합니다. AES-256 소재는 S3가 관리하고 추가 비용이 없으며 신규 업로드에서 암호화를 끌 수 없습니다. 이미 저장된 객체가 자동으로 다시 암호화되는 것은 아니므로 기존 객체는 CopyObject나 Batch Operations로 별도 처리합니다.

S3 서버측 암호화 선택지는 다음처럼 목적을 분리합니다.

| 방식 | 키 소재 | 언제 고르는가 | 주의점 |
| :--- | :--- | :--- | :--- |
| SSE-S3 | S3 관리 키 | 기본 보호와 운영 단순성 | key policy를 직접 통제할 수 없음 |
| SSE-KMS | AWS KMS key | 감사, 교차 계정, 키 사용 권한 제어 | KMS API와 key policy 비용 및 quota |
| DSSE-KMS | 두 계층의 KMS 기반 암호화 | 이중 암호화 요구 | S3 Bucket Key를 지원하지 않음 |
| SSE-C | 요청자가 제공한 키 | 키를 AWS 밖에서 직접 관리 | 모든 요청에 키 제공과 운영 부담 |

SSE-KMS 객체가 많아 KMS 요청 비용이 커지면 S3 Bucket Key를 검토합니다. S3가 bucket 수준의 짧은 수명 키를 잠시 보관해 객체별 data key를 만들기 때문에 KMS `Encrypt`, `GenerateDataKey`, `Decrypt` 요청을 최대 99%까지 줄일 수 있습니다. 절감률은 요청자 수와 요청 패턴에 따라 달라지고, SSE-KMS 전체 비용이 99% 줄어든다는 뜻은 아닙니다.

Bucket Key는 보안 조건을 바꾸는 설정입니다. 기존 policy가 object ARN을 encryption context로 검사했다면 Bucket Key를 켠 뒤에는 bucket ARN이 들어와 조건이 실패합니다. KMS CloudTrail 이벤트도 object ARN 대신 bucket ARN을 기록하고 이벤트 수가 줄어듭니다. 기존 객체에는 자동 적용되지 않아 CopyObject가 필요합니다.

Bucket Key가 켜진 뒤에는 이후 요청이 bucket key를 재사용해 KMS key policy를 매번 검증하지 않을 수 있습니다. 따라서 누가 어떤 객체를 읽을 수 있는지 object ARN 조건에만 의존하던 정책은 bucket ARN 조건과 S3 authorization을 함께 검토해야 합니다. DSSE-KMS에는 Bucket Key를 적용할 수 없습니다.

---

## 10. S3 bucket policy와 access point로 데이터 경계를 나눈다

S3 access point는 버킷 하나에 여러 애플리케이션별 endpoint와 정책을 붙이는 방법입니다. 각 access point는 계정과 리전당 최대 10,000개이며 정책 크기는 20 KB입니다. 생성할 때 연결 버킷과 VPC 및 Block Public Access를 정하고 나면 이 속성을 바꿀 수 없습니다.

access point 정책만으로 교차 계정 접근이 완성되지 않습니다. 버킷 소유자의 bucket policy가 해당 access point ARN에 대한 요청을 승인해야 합니다. access point 정책은 prefix나 VPC 조건을 좁히고, bucket policy는 버킷 소유자가 허용할 수 있는 전체 경계를 정합니다.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowAnalyticsAccessPoint",
      "Effect": "Allow",
      "Principal": { "AWS": "arn:aws:iam::222222222222:role/Analytics" },
      "Action": ["s3:GetObject"],
      "Resource": "arn:aws:s3:::data-bucket/reports/*",
      "Condition": {
        "StringEquals": {
          "s3:DataAccessPointArn": "arn:aws:s3:us-east-1:111111111111:accesspoint/analytics"
        }
      }
    }
  ]
}
```

access point는 virtual-host-style 주소와 HTTPS를 사용하고 익명 접근을 지원하지 않습니다. S3 Replication의 목적지로 지정할 수 없으며, 교차 계정에서는 access point 계정과 버킷 계정의 정책을 모두 확인해야 합니다. 객체 수준 호출을 감사하려면 CloudTrail data event를 별도로 켜야 하며, bucket policy나 Config가 객체 읽기 이력을 대신 기록하지 않습니다.

---

## 11. Object Lock은 객체 버전의 삭제 경로를 잠근다

7년 보존 문항에서 먼저 확인할 값은 저장 클래스가 아니라 versioning과 Object Lock입니다. Object Lock은 S3 객체의 특정 버전을 WORM 상태로 만들며, 버킷을 만들 때 Object Lock을 활성화하려면 versioning도 함께 켜야 합니다. 보존 기간 중 새 버전을 만드는 작업까지 막는 기능은 아니므로, 같은 key에 새 버전이나 delete marker가 추가될 수 있다는 사실도 정책과 감사 설계에 반영합니다.

| 통제 | 만료 조건 | 권한으로 우회 가능 여부 | 사용 시점 |
| :--- | :--- | :--- | :--- |
| Governance mode | retain-until-date 또는 기간 | `s3:BypassGovernanceRetention`과 bypass header를 가진 권한자가 가능 | 운영자가 예외를 처리해야 하는 WORM |
| Compliance mode | retain-until-date 또는 기간 | 보존 기간을 줄이거나 버전을 지우는 우회가 불가 | 계정 관리자와 root도 삭제하지 못해야 하는 규제 보존 |
| Legal hold | 명시적으로 해제할 때까지 | `s3:PutObjectLegalHold` 등 별도 권한으로 해제 | 조사나 소송이 끝날 때까지 기간을 모를 때 |

Compliance mode에서 retain-until-date 전에는 version ID를 알고 있어도 삭제와 overwrite가 거절됩니다. 계정 자체를 삭제하는 경우는 서비스의 별도 예외이므로, 계정 폐쇄를 일상적인 삭제 통제로 사용해서는 안 됩니다. Governance mode는 예외 운영자가 bypass 권한을 가지고 요청 header를 함께 보내야 하며, 두 조건 중 하나라도 빠지면 삭제가 실패합니다. Legal hold는 날짜가 없고, 별도의 API 호출로 해제하기 전에는 retention period가 지나도 계속 유지됩니다.

보존 기간을 일수로 지정할 때는 요청 시각을 기준으로 만료 시점을 계산합니다. `s3:object-lock-remaining-retention-days` 조건 키로 최소 보존 일수를 강제하면 애플리케이션이 실수로 짧은 retention을 설정하는 것을 막을 수 있습니다. 이미 잠긴 버전의 retention을 줄이는 것은 mode와 권한에 따라 제한되므로, 규정의 최소 기간을 bucket policy와 조직 정책 양쪽에서 검증합니다.

{% include diagrams/static/sap-c02/worm-retention-decision.html %}
{% include diagrams/download.html png="/assets/img/diagrams/static/sap-c02/worm-retention-decision--adb015c71ac0c850.png" %}

Object Lock은 S3 데이터 경계입니다. S3 access point, bucket policy, KMS key policy는 누가 객체를 읽고 새 버전을 쓸 수 있는지를 결정하고, Object Lock은 이미 기록된 특정 버전의 삭제 시점을 제한합니다. 따라서 "root도 삭제할 수 없음"이라는 요구에는 bucket policy의 `Deny`만 추가하지 말고 versioning, compliance mode, 최소 retention 조건을 함께 제시해야 합니다.

---

## 12. Vault Lock은 백업 recovery point를 잠근다

AWS Backup Vault Lock은 S3 Object Lock과 이름이 비슷하지만 보호 대상이 다릅니다. Vault Lock은 backup vault의 recovery point에 적용되고, Object Lock은 S3 object version에 적용됩니다. 시험에서 S3 버킷의 WORM을 요구하면 Object Lock을, AWS Backup copy의 조기 삭제 방지를 요구하면 Vault Lock을 선택합니다.

Vault Lock에는 compliance mode와 governance mode가 있습니다. compliance mode는 설정한 grace period가 끝난 뒤 vault 설정과 recovery point를 변경하거나 삭제할 수 없게 만듭니다. grace period는 3일부터 36,500일까지 지정할 수 있고, lock 이후의 최소 보존 기간은 1일 이상 36,500일 이하로 둡니다. governance mode는 권한이 있는 운영자가 lock을 제거할 수 있으므로 테스트와 운영의 단계적 전환에 적합합니다. grace period 전에 기록된 recovery point에는 이후의 lock 규칙이 자동으로 소급되지 않습니다.

API 설계에서는 `ChangeableForDays`를 함께 봅니다. 이 값을 지정하면 compliance lock이 grace period를 지나 immutable 상태로 전환되고, 생략하면 governance lock이 됩니다. 운영자가 grace period 동안 보존 기간과 삭제 경로를 검증한 뒤 최종 lock을 기다리는 형태로 설계합니다. 계정 폐쇄 후에도 recovery point가 영구 보존된다고 가정하면 안 됩니다. AWS Backup 문서의 post-closure period 동안에는 MPA로 복구할 수 있지만, 그 기간이 끝나면 백업에 접근할 수 없으므로 법적 보존이 계정 생명주기까지 넘어가면 별도 계정과 조직 통제를 사용합니다.

논리적으로 air-gapped vault는 공격받은 계정의 일반 vault와 분리된 백업 사본을 위한 특수 vault입니다. compliance lock을 항상 사용하고 AWS owned key 또는 customer managed key를 선택하며, AWS RAM으로 다른 계정과 공유하거나 Multi-party approval(MPA)로 vault 소유 계정이 접근 불가할 때 복구할 수 있습니다. 일반 vault의 운영 기능을 대체하는 저장소가 아니라 격리된 recovery point를 보관하는 마지막 방어선입니다. 생성 시 recovery point의 최소 보존 기간이 7일이므로, 하루짜리 시험 백업을 air-gapped vault의 정책으로 설명하면 조건이 맞지 않습니다.

| 요구사항 | 올바른 통제 | 흔한 오답 |
| :--- | :--- | :--- |
| S3 객체를 7년 WORM으로 보존 | S3 versioning + Object Lock compliance | Backup Vault Lock |
| AWS Backup recovery point의 조기 삭제 방지 | Backup Vault Lock compliance 또는 governance | S3 Object Lock |
| 침해된 계정에서 백업을 지우지 못하게 별도 사본 보관 | logically air-gapped vault | 일반 vault에 IAM deny만 추가 |

---

## 13. WAF는 검사 위치와 WCU를 먼저 계산한다

AWS WAF web ACL은 요청이 통과하는 보호 리소스에 연결하고, rule과 rule group의 합산 용량을 WCU로 계산합니다. web ACL과 rule group 각각의 최대 용량은 5,000 WCU이며, web ACL이 1,500 WCU를 넘으면 기본 보호 팩 가격을 넘어서는 비용이 발생합니다. managed rule group을 여러 개 추가할 때는 룰의 이름보다 WCU 합계와 제외할 rule의 범위를 먼저 확인합니다.

본문 검사에서 가장 자주 나오는 함정은 ALB와 AppSync의 8 KB 고정 한도입니다. CloudFront, API Gateway, Cognito, App Runner, Verified Access는 기본 16 KB에서 최대 64 KB까지 설정할 수 있습니다. ALB 뒤 애플리케이션을 그대로 두고 40 KB JSON payload의 악성 값을 WAF에서 검사해야 한다면 ALB web ACL만으로는 요구를 만족하지 못합니다. CloudFront 같은 앞단 리소스에서 검사하거나 애플리케이션의 별도 검증을 추가해야 합니다.

| WAF 항목 | 기본 또는 고정 한도 | 설계 포인트 |
| :--- | :--- | :--- |
| web ACL 용량 | 5,000 WCU, 1,500 WCU 초과 시 추가 비용 | managed rule group을 넣기 전에 합산 |
| rate-based rule | web ACL당 10개, rule group당 4개 | 한 rule이 제한할 수 있는 고유 IP는 10,000개 |
| 최소 rate limit | 10 requests | 너무 낮은 값은 정상 사용자를 함께 제한할 수 있음 |
| IP set | set당 CIDR 10,000개 | 대량 목록은 여러 set과 rule로 분리 |
| body inspection | ALB/AppSync 8 KB, 일부 리소스 최대 64 KB | payload 크기에 맞는 검사 위치 선택 |
| web ACL 수 | 계정과 리전당 기본 100개 | 조직 배포 시 quota 증가와 naming 계획 |
| 처리율 | web ACL당 기본 100,000 RPS | CloudFront RPS는 CloudFront 쪽 한도도 확인 |

rate-based rule은 일정 시간 동안 동일한 aggregation key의 요청을 세는 통제입니다. 로그인 실패처럼 사용자 ID를 기준으로 세려면 IP만 aggregation key로 삼는 기본 rate rule이 충분하지 않을 수 있습니다. 반대로 전체 API에 낮은 rate limit 하나를 걸면 NAT 뒤의 정상 사용자까지 같이 제한됩니다. managed rule group은 탐지 규칙의 업데이트 책임을 줄이지만, false positive를 줄일 예외와 scope-down statement는 서비스 소유자가 관리합니다.

WAF logging은 CloudWatch Logs, S3, Kinesis Data Firehose 중 하나로 보낼 수 있습니다. CloudWatch 로그 그룹 이름은 `aws-waf-logs-` 접두사를 사용해야 하며, 로그 목적지는 web ACL과 같은 리전과 계정에 있어야 합니다. 로그 자체가 요청 body 전체를 항상 보존하는 것은 아니므로, 포렌식에 필요한 필드를 별도 애플리케이션 로그와 연결합니다. web ACL 로그를 켜는 일은 rule을 적용하는 것과 별개이며, 비용과 민감정보 마스킹도 함께 검토합니다.

---

## 14. Shield와 Firewall Manager는 WAF의 대체재가 아니다

Shield Standard는 AWS 리소스에 무료로 제공되는 일반적인 네트워크와 전송 계층 DDoS 방어입니다. Shield Advanced는 보호할 리소스와 공격 가시성, 대응 지원, 애플리케이션 계층 자동 완화를 확장하는 유료 서비스입니다. 두 서비스 모두 악성 HTTP body의 비즈니스 의미를 판별하는 WAF rule을 대신 작성해 주지는 않습니다.

Shield Advanced에서 automatic application layer DDoS mitigation을 켜면 자동 완화가 web ACL에 연결되고 150 WCU를 사용합니다. 기존 WAF rule과 managed rule group의 동작을 검토하지 않고 켜면 WCU와 false positive가 함께 증가할 수 있습니다. AWS WAF 비용을 Shield Advanced가 일부 흡수하는 조건이 있어도 Bot 또는 Fraud Control, CAPTCHA, Marketplace managed rule fee, 기본 body size 초과, 1,500 WCU 초과, 50B requests 초과분까지 모두 무료가 되는 것은 아닙니다. 2026년 9월 AWS 가격 페이지 기준으로 Shield Advanced는 1년 약정 시 월 3,000 USD 항목이 표시되며, 실제 계약과 데이터 전송 비용은 계정의 요금 페이지에서 다시 확인합니다. 가격 숫자 하나만으로 Standard와 Advanced를 고르지 말고 보호 대상, 응답 지원, 비용 보호 요구를 함께 비교합니다.

Firewall Manager는 Organizations의 여러 계정과 리전에 WAF, Shield Advanced, security group, Network Firewall 같은 정책을 중앙 배포하는 조정 서비스입니다. Organizations와 delegated administrator 구성이 필요하고, 정책 종류에 따라 AWS Config, AWS Resource Access Manager, AWS Marketplace 구독이 추가로 필요할 수 있습니다. FMS 정책은 새 리소스에 자동으로 연결할 수 있지만, 해당 리소스가 정책 scope에 들어오는지와 Config recording이 최신 상태인지 확인해야 합니다.

| 질문 | Shield | WAF | Firewall Manager |
| :--- | :--- | :--- | :--- |
| 대규모 L3/L4 DDoS 흡수 | Standard와 Advanced | 직접 담당하지 않음 | Shield 정책을 여러 계정에 배포 |
| HTTP header, URI, body 검사 | 직접 담당하지 않음 | web ACL rule | WAF 정책을 중앙 배포 |
| 계정 전체의 새 ALB에 동일 rule 적용 | 직접 담당하지 않음 | 리소스별 연결 | Organizations 범위 자동 적용 |
| 애플리케이션 계층 자동 완화 | Advanced 기능 | WAF rule과 함께 동작 | Advanced 설정을 조직 정책으로 관리 |

DDoS 대응 설계는 "Shield를 켰으니 WAF가 필요 없다" 또는 "FMS를 켜면 모든 리소스가 즉시 보호된다"처럼 한 단계로 끝나지 않습니다. 리소스 발견과 정책 배포는 FMS, 네트워크 공격 흡수와 대응은 Shield, 요청 의미와 rate limit은 WAF로 나누어 acceptance criteria를 작성합니다.

---

## 15. GuardDuty는 신호를 모으고 보호 계획이 관측 범위를 넓힌다

GuardDuty의 foundational data sources는 CloudTrail management events, VPC Flow Logs, Route 53 Resolver DNS query logs입니다. 이 로그는 GuardDuty가 독립 스트림으로 읽으므로 사용자가 별도 저장 버킷을 만들거나 로그 수집 권한을 부여해야 하는 구조가 아닙니다. 각 데이터 소스의 원본 로그를 사용자가 이미 다른 곳에 보관하는지와 관계없이 GuardDuty 비용과 보존 정책은 GuardDuty 설정에서 따로 봅니다. 첫 활성화 리전에는 30일 무료 trial이 적용됩니다.

VPC Flow Logs와 DNS 로그는 서로 대체되지 않습니다. VPC Flow Logs만 켜면 DNS query의 도메인 이름을 확인할 수 없고, VPC의 DNS resolver를 쓰지 않는 환경에서는 Route 53 Resolver 기반 관측이 비어 있을 수 있습니다. Outposts에서는 DNS monitoring을 사용할 수 없는 제약도 있으므로 하이브리드 경로의 로그 공백을 threat model에 적습니다. global service의 management event는 활성화된 리전에 복제될 수 있어 finding이 생성된 리전과 원래 API 호출 리전이 다를 수 있습니다.

요즘 GuardDuty API에서는 데이터 소스 자체보다 `features` 설정을 기준으로 보호 계획을 확인합니다. S3 Protection을 켜야 S3 data event 기반 신호와 S3를 포함하는 공격 sequence를 볼 수 있습니다. EKS Protection은 EKS audit log 신호를, Runtime Monitoring은 노드와 컨테이너 런타임 신호를 확장합니다. ECS Runtime Monitoring은 ECS task의 요구사항이 별도로 있으므로 EKS 설정을 켰다고 ECS가 자동으로 같은 범위가 되지 않습니다.

Extended Threat Detection은 여러 단계의 finding을 24시간 rolling window에서 묶어 attack sequence로 보여 주는 기능입니다. 기본 활성화되는 시나리오가 있고 별도 추가 비용 없이 제공되며, attack sequence의 심각도는 Critical로 표시됩니다. archived 또는 suppressed finding은 sequence 입력에서 제외되므로 자동 suppression 규칙이 탐지 결과를 비우지 않는지 확인합니다. EventBridge와 Security Hub로 finding을 전달할 때는 sequence의 원래 finding, 계정, 리전, 생성 시간을 보존해야 합니다.

Malware Protection for S3는 업로드된 객체를 별도 검사하는 보호 계획입니다. GuardDuty의 기본 CloudTrail management events만 켜 둔 조직에서 대량 S3 다운로드나 악성 객체 검사를 기대하면 관측 범위가 모자랍니다. S3 Protection과 Malware Protection을 각각 어떤 데이터와 위협에 사용하는지, 중앙 delegated administrator가 멤버 계정에 실제로 활성화했는지 확인합니다.

| 서비스 경로 | 주로 답하는 질문 | 필요한 추가 확인 |
| :--- | :--- | :--- |
| Foundational sources | 계정, 네트워크, DNS에서 의심 행위가 있었는가 | 세 로그가 독립적으로 수집되는가 |
| S3 Protection | S3 data event와 데이터 탈취 sequence가 있는가 | 멤버 계정의 S3 보호 계획과 리전 |
| EKS Protection | EKS audit log와 클러스터 행위가 의심스러운가 | audit log, add-on, 리전 범위 |
| Runtime Monitoring | EC2, ECS, EKS 런타임에서 프로세스가 의심스러운가 | 에이전트 배포와 운영체제 지원 |
| Extended Threat Detection | 짧은 시간의 여러 finding이 하나의 공격인가 | suppression, 24시간 window, 원래 finding |

GuardDuty finding은 조사 결론이 아니라 triage 입력입니다. Detective가 시간축과 엔터티 관계를 확장하고, Security Hub CSPM이 통제 상태와 finding을 묶고, EventBridge가 티켓 또는 격리 자동화로 전달하는 식으로 다음 단계를 연결합니다.

---

## 16. Inspector는 취약점과 노출 경로를 우선순위로 만든다

Amazon Inspector는 EC2, ECR container image, Lambda function의 취약점 스캔을 서로 다른 수명주기로 제공합니다. EC2는 SSM 관리형 인스턴스와 EBS snapshot을 이용한 agentless 방법을 함께 고려하고, hybrid 환경에서는 어떤 인스턴스가 SSM inventory에 보이는지를 먼저 확인합니다. Inspector가 발견한 CVE를 보고도 패치 실행 권한과 유지보수 창은 별도로 운영합니다.

ECR 스캔은 이미지가 push된 지 30일 이내이거나 최근 90일 안에 pull된 경우처럼 활성 상태의 이미지를 대상으로 하며, 활성화된 이미지의 취약점 결과는 90일 동안 모니터링됩니다. 오래된 이미지가 실제 배포에 남아 있어도 이 조건을 벗어나면 현재 상태가 갱신되지 않을 수 있으므로, registry lifecycle과 배포 태그를 함께 관리합니다.

Lambda 표준 스캔은 패키지 의존성 취약점을 대상으로 합니다. Lambda code scanning은 애플리케이션 코드의 취약 패턴을 별도 옵션으로 다루며, Code Security는 보안 분석 범위가 더 넓은 별도 기능입니다. 선지에서 "Lambda가 켜져 있으니 소스 코드의 모든 취약점을 자동으로 찾는다"는 표현은 스캔 유형을 확인하지 않은 주장입니다.

Inspector는 NVD의 CVSS만 그대로 보여 주지 않고 AWS 환경의 네트워크 노출, 인스턴스 경로, 실행 가능성을 반영해 risk score를 조정합니다. 결과는 EventBridge와 Security Hub로 전달할 수 있으므로, 조직 표준으로 심각도만 필터링할 때는 risk score의 산정 근거와 예외 만료를 함께 저장합니다.

| 질문 | Inspector가 답하는 범위 | 다음 담당 |
| :--- | :--- | :--- |
| 이 EC2가 취약한가 | 패키지, OS, 노출 경로, risk score | SSM 기반 패치와 검증 |
| 이 ECR 이미지가 취약한가 | 이미지 레이어와 패키지 CVE | 이미지 재빌드와 배포 교체 |
| 이 Lambda dependency가 취약한가 | 함수 package 의존성 | 새 artifact 배포 |
| 소스 코드의 보안 패턴이 문제인가 | Lambda code scanning 또는 Code Security 선택 시 | 개발팀 수정과 재스캔 |

Inspector finding을 자동으로 "패치 완료"로 닫는 것은 안전하지 않습니다. 새 AMI, 새 컨테이너 이미지, 새 Lambda artifact가 실제 환경에 배포되었고 재스캔에서 finding이 사라졌는지를 확인한 뒤 예외나 remediation 상태를 갱신합니다.

---

## 17. Security Hub CSPM과 Config는 평가와 교정을 나눈다

현재 AWS 문서의 표기는 Security Hub CSPM입니다. CSPM 표준의 많은 control은 AWS Config rule로 리소스 상태를 평가하고, Security Hub는 그 결과와 다른 보안 서비스 finding을 표준 형식으로 모읍니다. Security Hub CSPM을 켰다고 Config recording 범위가 모든 리소스에 자동으로 맞춰지는 것은 아닙니다. Security Hub CSPM과 Security Hub를 모두 활성화한 계정과 리전에서는 service-linked recorder인 `AWSConfigurationRecorderForSecurityHubCSPM`과 service-linked rule이 자동으로 관리되고, 이 경로의 `Config.1` 결과는 항상 PASSED로 표시됩니다. 이를 애플리케이션 리소스가 모두 기록된다는 뜻으로 해석하면 안 되며, Security Hub CSPM만 켠 경우에는 Config와 resource recording을 직접 구성해야 합니다.

Config의 continuous recording은 변경 트리거 평가가 빠른 대신 기록 비용과 데이터 양이 늘어납니다. daily recording은 비용을 줄일 수 있지만 Security Hub CSPM의 변경 트리거 control과 FMS의 새 리소스 적용이 최대 하루 늦어질 수 있습니다. 규제 대상 리소스와 WAF 자동 연결을 daily로 바꾸는 경우에는 평가 지연을 acceptance criteria에 기록하고, 필요한 리소스만 continuous로 남기는 방식을 검토합니다.

Security Hub central configuration은 delegated administrator가 home Region에서 정책을 만들고 home 또는 linked Region에 적용하는 구조입니다. custom configuration policy는 최대 20개이며, 2019년 3월 20일 이후에 opt-in한 리전은 home Region으로 선택할 수 없는 제약이 있습니다. 계정이 중앙 관리 대상이 된 뒤에는 멤버 계정의 로컬 API로 설정을 덮어쓰지 못할 수 있으므로, 계정 온보딩과 리전 확장을 central policy 변경으로 추적합니다.

Config rule은 한 조건을 평가하는 단위이고, conformance pack은 여러 rule과 remediation을 묶어 계정과 리전에 배포하는 단위입니다. noncompliant 결과의 remediation은 Systems Manager Automation 문서로 실행할 수 있으며, AWS managed document와 custom Automation runbook을 선택합니다. Config는 상태를 평가하고 실행을 요청할 뿐, 모든 수정이 성공했는지와 서비스별 rollback을 대신 보장하지 않습니다.

{% include diagrams/static/sap-c02/config-evaluation-remediation.html %}
{% include diagrams/download.html png="/assets/img/diagrams/static/sap-c02/config-evaluation-remediation--f7def977bc7f6b6c.png" %}

자동 교정에는 세 가지 식별자를 함께 남깁니다. 어느 Config rule 또는 control이 실패했는지, 어떤 Automation document와 파라미터로 실행했는지, 그리고 실행 후 재평가에서 compliant가 되었는지입니다. EventBridge에서 remediation을 직접 호출할 때도 동일한 correlation ID를 ticket, SSM execution, 후속 Config evaluation에 전파하면 반복 실행과 수동 예외를 구분할 수 있습니다.

---

## 18. Detective, Macie, Security Lake, Audit Manager의 역할을 겹치지 않게 둔다

보안 서비스의 이름을 목적별로 분리하면 한 서비스의 빈 입력을 다른 서비스가 채워 줄 것이라고 잘못 기대하지 않게 됩니다.

| 서비스 | 강점 | 입력과 저장 경계 | 답하지 않는 질문 |
| :--- | :--- | :--- | :--- |
| Detective | GuardDuty finding의 시간축과 엔터티 관계 조사 | CloudTrail, VPC Flow Logs, GuardDuty finding으로 behavior graph 구성, 최대 1년 | 예방 rule이나 CVE 패치가 되었는가 |
| Macie | S3 민감 데이터 발견과 데이터 보안 상태 | S3 general purpose bucket, 자동 샘플링 또는 deep discovery job | EC2 패키지 취약점이나 API 호출 원인 |
| Security Lake | 여러 소스의 raw security log를 표준화 | 고객 S3 data lake, OCSF와 Parquet, rollup Region과 retention | 법적 의미의 compliance 판정 |
| Audit Manager | 감사 프레임워크용 evidence 수집과 보고서 | CloudTrail, Config, Security Hub, Artifact 등의 증적과 수동 evidence | 조직이 실제로 법을 준수하는지에 대한 최종 판단 |

Detective behavior graph는 CloudTrail과 VPC Flow Logs, GuardDuty finding을 이미 관측한 뒤 조사에 쓰는 데이터 모델입니다. Security Lake가 원본을 OCSF와 Parquet로 보존한다고 해서 Detective graph가 자동으로 모든 보존 기간을 따라가는 것은 아닙니다. Detective를 켜는 목적은 사건의 주체와 연결 자원을 추적하는 것이며, 오랜 기간의 raw log 보존이 필요하면 Security Lake나 별도 로그 저장소를 함께 설계합니다.

Macie는 S3 general purpose bucket의 객체를 대상으로 합니다. 자동 discovery는 샘플링으로 비용을 조절하고, 전체 객체 또는 특정 prefix를 확인하려면 deep discovery job을 사용합니다. managed data identifiers, custom data identifiers, allow list를 조합해 주민번호 같은 패턴과 조직 내부 예외를 나눕니다. 무료 trial에는 discovery job 비용이 포함되지 않는 조건이 있으므로, 시험 기간에 job을 대량 실행하고 무료라고 예산을 잡지 않습니다.

Security Lake는 소스별 로그를 OCSF schema와 Apache Parquet 형식으로 고객 소유 S3 data lake에 저장합니다. CloudTrail management와 data events, S3/Lambda, EKS audit, Route 53 Resolver, VPC Flow Logs, WAFv2, Security Hub CSPM 같은 source를 선택하고 rollup Region과 retention 또는 tiering을 정합니다. subscriber는 Lake Formation 권한으로 쿼리하거나 알림을 받으며, S3 Select로 Security Lake 객체를 직접 조회하는 방식은 지원되지 않습니다. lake를 만들었다고 source가 자동으로 모두 활성화되는 것이 아니므로 계정과 리전별 source 상태를 확인합니다.

Audit Manager는 선택한 framework와 control에 맞는 evidence를 수집해 assessment report를 만드는 서비스입니다. AWS managed framework를 복제해 custom control과 수동 evidence를 추가할 수 있지만, 보고서를 만들었다고 규제기관을 대신해 compliance 판정을 내리는 것은 아닙니다. Audit Manager, Security Hub CSPM, Config의 결과는 control ID와 수집 시각, 원본 로그 위치를 연결해 사람이 검토할 수 있는 증적으로 보존합니다.

---

## 19. CloudTrail data event와 log integrity는 별도 경계다

CloudTrail Event history와 management event trail만 켜 둔 상태에서는 S3 객체 읽기나 Lambda 함수 호출 같은 data event가 기본으로 기록되지 않습니다. 객체 수준 접근을 감사해야 하면 trail 또는 CloudTrail Lake event data store에서 data event를 명시적으로 선택하고 advanced event selector로 bucket, prefix, API type을 좁힙니다. data event는 호출량과 저장량에 따른 추가 비용이 있으므로 전 계정의 모든 객체를 무조건 기록하기보다 보호 데이터와 incident path를 먼저 선정합니다.

로그 파일 integrity validation은 로그 파일과 digest 파일에 SHA-256 hash와 RSA 서명을 붙이고, digest를 시간 순서로 연결해 삭제나 변경을 탐지하는 통제입니다. validation을 켜면 이후 전달되는 digest가 생기지만, 과거 로그의 무결성을 자동으로 고쳐 주지는 않습니다. CLI의 `validate-logs`는 원래 S3 위치의 로그와 digest를 검증하므로, 로그를 다른 버킷으로 복사한 뒤 원본을 지운 경우에는 동일한 검증 경로가 남지 않습니다.

CloudTrail Lake event data store는 category별 immutable event collection을 만들고 Trino SQL로 조회하는 경로입니다. 2026년 5월 31일부터 신규 고객에게 더 이상 열리지 않으며 기존 고객은 계속 사용할 수 있다는 현재 공지가 있으므로, 새 조직 설계에서 Lake를 당연한 기본값으로 적지 않습니다. One-year extendable retention pricing option은 최대 3,653일, Seven-year retention pricing option은 최대 2,557일을 보관할 수 있고, 쿼리 결과는 최대 7일 동안 조회합니다. API 직후 평균 약 5분에 이벤트가 보인다는 설명은 평균값이며 전달 시간을 보장하는 SLA가 아닙니다.

감사 증적은 세 층으로 나누어 보관합니다. 어떤 API와 객체에 접근했는지는 data event selector, 로그가 전달 중 변조되지 않았는지는 integrity validation, 장기적인 분석과 cross-account 조회는 event data store 또는 Security Lake가 담당합니다. 한 층을 켰다고 나머지 두 요구가 자동으로 충족되지 않습니다.

---

## 20. 취약점 finding을 교정과 재평가까지 닫는다

탐지 결과를 보안 통제로 완성하려면 finding 생성에서 끝내지 말고 다음 네 단계를 연결합니다.

1. **탐지**: GuardDuty, Inspector, Macie, Config rule, Security Hub CSPM이 finding 또는 noncompliant 결과를 만듭니다.
2. **우선순위**: 자산 노출, 데이터 민감도, 공격 경로, risk score, 예외 만료를 기준으로 심각도를 조정합니다.
3. **실행**: EventBridge로 티켓과 승인 흐름을 만들고, Config remediation 또는 SSM Automation으로 되돌릴 수 있는 변경을 실행합니다.
4. **재평가**: 대상 리소스의 실제 상태, 새 이미지 또는 설정의 배포 여부, Config 재평가와 서비스 재스캔을 확인한 뒤 finding을 닫습니다.

{% include diagrams/static/sap-c02/detection-to-remediation-path.html %}
{% include diagrams/download.html png="/assets/img/diagrams/static/sap-c02/detection-to-remediation-path--50b7a2ca5829a4f8.png" %}

예를 들어 Inspector가 인터넷에 노출된 EC2의 취약 패키지를 찾으면, risk score와 업무 owner를 기준으로 ticket을 만들고 SSM Automation 또는 새 AMI 배포를 선택합니다. 실행이 성공해도 이전 인스턴스가 아직 target group에 남아 있거나 새 AMI가 취약한 패키지를 그대로 포함할 수 있으므로, deployment 상태와 Inspector 재스캔을 함께 확인합니다. SSM Patch Manager의 상세 운영과 유지보수 창은 운영 runbook으로 관리하고, 이 루프에서는 교정 실행 결과를 증적으로 남깁니다.

Config의 S3 public access control이 실패한 경우에는 managed remediation document를 사용하거나 custom Automation runbook으로 bucket policy를 되돌릴 수 있습니다. runbook이 권한을 넓히거나 데이터 경로를 끊을 수 있으므로, 파라미터 allow list와 dry-run 단계, 실패 시 rollback, 재평가 대상을 문서화합니다. compliance pack은 rule 묶음을 배포하지만 모든 remediation이 자동으로 안전하게 실행된다는 뜻은 아닙니다.

WAF managed rule의 false positive, GuardDuty suppression, Macie allow list, Security Hub workflow status는 모두 예외 통제입니다. 예외를 만들 때 owner, 이유, 만료일, 대체 탐지, 재검토 이벤트를 함께 기록하면 "finding이 없어졌다"와 "위험이 수용되었다"를 구분할 수 있습니다.

---

## 21. 보안 서비스의 hard limit을 설계 표에 고정한다

시험 선지는 기능 이름보다 숫자와 변경 가능 여부로 틀리게 만드는 경우가 많습니다. 다음 표는 이 글에서 사용하는 2026년 9월 기준의 대표 한도입니다. quota가 조정 가능한지와 서비스 자체에 고정된 값인지를 함께 기억합니다.

### 21.1. KMS와 HSM 한도

| 항목 | 값 | 의미 |
| :--- | :--- | :--- |
| 자동 rotation 기간 | 90-2,560일, 기본 365일 | `AWS_KMS` origin 대칭 customer managed key만 해당 |
| on-demand rotation | 키당 최대 25회 | 조정 불가, `AWS_KMS`와 `EXTERNAL` 대칭 키에서 사용 |
| customer managed key | 계정과 리전당 100,000개 | quota 증가 가능 여부를 계정에서 확인 |
| alias | 키당 50개 | alias 개수와 key ARN의 안정성을 혼동하지 않음 |
| grant | 키당 50,000개 | EBS와 서비스 통합을 한 키에 몰아넣을 때 병목 |
| CloudHSM custom key store | 계정과 리전당 10개 | key store마다 별도 cluster 운영 |
| custom key 생성 조건 | 서로 다른 AZ의 active HSM 최소 2개 | KMS key 생성 시점에만 필요한 조건과 운영 가용성을 구분 |
| CloudHSM KMS key | 256-bit AES symmetric만 지원 | asymmetric, HMAC, imported material, MRK는 KMS key store에서 불가 |

### 21.2. Secrets, ACM, S3 한도

| 항목 | 값 또는 조건 | 선택 기준 |
| :--- | :--- | :--- |
| Parameter Store Standard | 값 4 KB, 계정과 리전당 10,000개 | policy와 cross-account 불가, 무료 tier |
| Parameter Store Advanced | 값 8 KB, 계정과 리전당 100,000개 | policy와 cross-account 가능, 유료 tier |
| Secrets Manager secret value | 65,536 bytes | 큰 credential bundle과 rotation에 사용 |
| Secrets Manager secret 수 | 리전당 500,000개 | resource policy는 20,480 characters |
| Secrets Manager version | secret당 100 versions | 10분보다 잦은 지속 update는 version quota 위험 |
| exportable public certificate | 유효 기간 198일, 만료 45일 전 갱신 | ACM은 갱신 알림까지, 서버 재배포는 사용자 책임 |
| CloudFront ACM certificate | `us-east-1` 필수 | 다른 리전 인증서를 같은 배포에 연결할 수 없음 |
| S3 Bucket Key | KMS 요청 최대 99% 감소 가능 | DSSE-KMS에는 적용 불가, encryption context가 bucket ARN으로 바뀜 |
| S3 Object Lock | versioning 필수 | compliance는 root도 retention 전 삭제 불가 |
| S3 access point | 계정과 리전당 기본 10,000개, policy 20 KB | 생성 후 버킷, VPC, Block Public Access 속성 변경 불가 |

### 21.3. WAF와 탐지 한도

| 항목 | 값 또는 조건 | 설계 기준 |
| :--- | :--- | :--- |
| WAF web ACL과 rule group | 각각 최대 5,000 WCU | web ACL 1,500 WCU 초과분은 추가 비용 |
| rate-based rule | web ACL당 10개, rule group당 4개 | 최소 rate 10, 고유 IP 제한 10,000개 |
| body inspection | ALB/AppSync 8 KB, 일부 리소스 최대 64 KB | 리소스 유형이 상한을 결정 |
| web ACL 처리율 | 기본 100,000 RPS | CloudFront는 CloudFront quota도 확인 |
| GuardDuty trial | 첫 활성화 리전 30일 | trial이 모든 보호 계획 비용을 포함하지 않음 |
| GuardDuty Extended Threat Detection | 24시간 rolling window | suppression 또는 archive finding은 sequence에서 제외 |
| Inspector ECR 활성 이미지 | 최근 push 30일 또는 pull 90일 등 | 90일 monitoring 조건과 registry lifecycle을 함께 관리 |
| Security Hub central policy | custom configuration policy 최대 20개 | delegated administrator의 home Region에서 관리 |
| Detective graph | 최대 1년의 behavior history | 장기 raw log 보존은 Security Lake 등 별도 설계 |

### 21.4. 감사와 백업 한도

| 항목 | 값 또는 조건 | 놓치기 쉬운 경계 |
| :--- | :--- | :--- |
| CloudTrail data event | 기본 비활성, 추가 비용 | management event가 객체 API를 대신 기록하지 않음 |
| CloudTrail Lake retention | 3,653일 또는 2,557일 pricing option | 2026-05-31부터 신규 고객에게 개방되지 않음 |
| CloudTrail Lake query 결과 | 최대 7일 조회 | API 후 평균 5분 전달은 보장값이 아님 |
| Vault Lock grace period | 3-36,500일 | compliance lock 뒤에는 사용자와 AWS도 변경 불가 |
| Vault Lock retention | 최소 1일, 최대 36,500일 | grace 이전 recovery point에는 소급되지 않음 |
| logically air-gapped vault | recovery point 최소 보존 7일 | 일반 vault나 S3 Object Lock을 대체하지 않음 |

숫자를 외울 때는 먼저 리소스 범위를 붙입니다. "100개"가 web ACL인지 rule group인지, "7년"이 Object Lock 날짜인지 CloudTrail Lake pricing option인지, "두 개"가 CloudHSM 생성 조건인지 replica 수인지 문장 안에서 다시 확인합니다.

---

## 22. 혼동하는 서비스 쌍은 책임과 입력으로 비교한다

### 22.1. KMS key policy, IAM policy, grant

| 비교 | key policy | IAM policy | grant |
| :--- | :--- | :--- | :--- |
| 붙는 대상 | KMS key | user, role, group, 일부 resource | 특정 KMS key와 grantee principal |
| 교차 계정 역할 | 대상 계정 또는 principal을 허용하고 IAM도 허용 | 호출 계정에서 API를 허용 | 제한된 암호 연산을 위임하는 객체 |
| 기본 동작 | 계정 자동 위임이 아님 | key policy의 계정 위임이 있어야 allow가 실효 | key policy와 IAM policy를 대체하지 않음 |
| 시험 단서 | 다른 계정 KMS `AccessDenied` | 명시적 `Deny`는 항상 차단 | `kms:GrantIsForAWSResource`는 AWS 통합 경로 제한 |

### 22.2. KMS와 CloudHSM

| 요구 | KMS | CloudHSM 또는 custom key store |
| :--- | :--- | :--- |
| AWS 통합 서비스의 SSE | 광범위한 직접 통합 | KMS custom key store에서 AES key 사용 |
| 키 소재 전용성 | AWS 관리형 HSM 책임 | 계정 소유 HSM cluster 책임 |
| RSA 서명과 PKCS#11 | KMS asymmetric API 범위 | HSM API와 표준 라이브러리 직접 호출 |
| 자동 rotation | 지원되는 `AWS_KMS` 대칭 key | custom key store에서는 불가 |
| 운영 장애 | KMS가 HSM fleet 관리 | cluster, HSM user, backup, 연결 상태 관리 |

### 22.3. Parameter Store와 Secrets Manager

| 질문 | Parameter Store | Secrets Manager |
| :--- | :--- | :--- |
| 일반 설정값과 feature flag | Standard 또는 Advanced | 가능하지만 기능이 과함 |
| 8 KB 초과 값 | 불가 | 65,536 bytes까지 가능 |
| partner API나 DB 자격 증명 rotation | 알림과 schedule을 직접 조합 | managed 또는 Lambda rotation 제공 |
| cross-account | Advanced만 resource policy로 가능 | resource policy로 가능 |
| 비용과 운영 | Standard는 단순하고 무료 | secret별 비용과 version lifecycle 관리 |

### 22.4. ACM, ACME, Private CA

| 경로 | private key와 갱신 주체 | AWS 통합 서비스 연결 |
| :--- | :--- | :--- |
| ACM managed | ACM이 key와 갱신을 관리 | 지원 서비스에 자동 바인딩 |
| ACM exportable public | ACM 갱신 후 사용자가 export와 재배포 | AWS 통합과 자체 서버 모두 고려 |
| ACM with ACME | ACME client가 key, 갱신, 설치를 관리 | ACM inventory에는 있으나 통합 바인딩 불가 |
| Private CA | CSR 생성자와 CA 정책이 관리 | 사설 trust domain, 통합 범위 별도 확인 |

### 22.5. S3 Object Lock과 Backup Vault Lock

| 항목 | Object Lock | Vault Lock |
| :--- | :--- | :--- |
| 보호 대상 | S3 object version | AWS Backup recovery point |
| 사전 조건 | S3 versioning | backup vault와 recovery point |
| mode | governance, compliance, legal hold | governance, compliance grace period |
| root 우회 | compliance retention 중 불가 | compliance lock 이후 불가 |
| 계정 폐쇄 | S3 계정 삭제 예외 존재 | post-closure period 동안 MPA 복구, 이후 접근 불가 |

### 22.6. WAF, Shield, Firewall Manager

| 관점 | WAF | Shield | Firewall Manager |
| :--- | :--- | :--- | :--- |
| 검사 또는 방어 | HTTP header, URI, body, rate rule | DDoS 흡수와 Advanced 대응 | 조직 정책의 중앙 배포 |
| 적용 범위 | web ACL을 리소스에 연결 | 보호 리소스와 Advanced 설정 | Organizations 계정과 리전 |
| 새 리소스 자동 적용 | 개별 연결 또는 FMS 사용 | 자체 배포 기능 아님 | policy scope와 Config 전제 |
| 40 KB ALB body | ALB에서 불가 | 해결하지 않음 | CloudFront WAF 정책 배포 가능 |

### 22.7. GuardDuty, Inspector, Macie, Detective, Security Hub CSPM

| 질문 | 담당 서비스 | 결과의 성격 |
| :--- | :--- | :--- |
| 의심스러운 API, 네트워크, DNS 행위 | GuardDuty | threat finding 또는 attack sequence |
| 패키지와 이미지의 취약점 | Inspector | CVE, 노출 경로, risk score |
| S3에 민감정보가 있는가 | Macie | data discovery와 bucket 상태 |
| finding의 주체와 관계는 무엇인가 | Detective | behavior graph와 조사 컨텍스트 |
| control 준수와 finding을 한 화면에 모으기 | Security Hub CSPM | 표준 control 상태와 통합 finding |

### 22.8. CloudTrail, Config, Security Lake, Audit Manager

| 서비스 | 기록 또는 평가 단위 | 잘못 맡기기 쉬운 역할 |
| :--- | :--- | :--- |
| CloudTrail | API activity, data event, integrity digest | Config 상태나 WAF rule을 평가하지 않음 |
| Config | resource configuration item과 rule 결과 | 객체 read API와 장기 raw log를 기록하지 않음 |
| Security Lake | OCSF raw security log lake | 법적 compliance 판정과 자동 remediation을 하지 않음 |
| Audit Manager | framework control evidence와 report | 조직 대신 감사 결론을 확정하지 않음 |

---

## 23. 그럴듯하지만 성립하지 않는 조합을 먼저 제거한다

| 잘못된 조합 | 왜 성립하지 않는가 | 바꿀 방향 |
| :--- | :--- | :--- |
| `EXTERNAL` key에 automatic rotation | 자동 rotation 조건이 `AWS_KMS` origin 대칭 customer managed key임 | on-demand rotation 또는 새 key와 재암호화 |
| key material origin을 `AWS_KMS`로 변경 | origin은 생성 후 변경할 수 없음 | 새 key를 만들고 data key를 전환 |
| CloudHSM key store에 RSA KMS key 생성 | KMS custom key store는 256-bit AES symmetric만 지원 | HSM PKCS#11 직접 서명 |
| CloudHSM key store에서 MRK 생성 | custom key store key는 multi-Region 지원 안 함 | 리전별 KMS key 또는 일반 MRK |
| single-Region key를 MRK로 승격 | 기존 key의 Region 유형은 바꿀 수 없음 | 새 MRK와 일회성 재암호화 |
| MRK가 global policy를 공유한다고 가정 | key policy, grant, alias, tag, enabled가 리전별 독립 | 각 replica policy와 grant 배포 |
| AWS managed `aws/s3` key로 cross-account SSE-KMS | key policy를 편집할 수 없고 cross-account 공유 불가 | customer managed key |
| Parameter Store Advanced에 30 KB secret 저장 | Advanced 값 상한은 8 KB | Secrets Manager |
| Parameter policy가 secret을 자동 교체한다고 가정 | policy는 만료 알림과 조건이지 rotation 실행이 아님 | Secrets Manager rotation 또는 Lambda |
| Object Lock을 versioning 없이 활성화 | Object Lock은 versioned object에 적용 | versioning과 Object Lock을 함께 구성 |
| bucket policy `Deny`만으로 root 삭제를 막음 | 정책은 소유자가 변경할 수 있음 | Object Lock compliance |
| S3 Object Lock으로 AWS Backup point를 잠금 | 보호 대상이 서로 다름 | Backup Vault Lock |
| ALB WAF body 한도를 64 KB로 설정 | ALB와 AppSync 상한은 8 KB 고정 | CloudFront 등 앞단 검사 |
| WAF rate limit을 5로 설정 | 최소 rate limit은 10 | 정상 트래픽을 고려한 rate rule |
| Shield Advanced가 body SQL injection을 검사 | Shield는 WAF rule을 대체하지 않음 | WAF web ACL과 Shield를 함께 사용 |
| 조직 CloudTrail data event를 켜면 GuardDuty S3 finding 생성 | GuardDuty는 계정 trail이 아닌 독립 스트림을 읽음 | GuardDuty S3 Protection 활성화 |
| Detective가 새 threat finding을 생성 | Detective는 조사 그래프를 만드는 서비스 | GuardDuty 또는 Inspector 탐지 |
| Macie가 access key를 이용한 대량 다운로드를 탐지 | Macie는 S3 민감 데이터 발견 중심 | GuardDuty S3 Protection과 CloudTrail data event |
| Config aggregator가 source 계정에 rule을 배포 | aggregator는 read-only 집계 | source 계정 rule 또는 conformance pack |
| Security Hub CSPM만 켜면 모든 Config resource가 기록됨 | recorder와 resource recording 범위를 따로 확인해야 함 | 필요한 Config recording을 명시 |
| Config daily recording으로 FMS 신규 WAF 적용을 유지 | 변경 트리거가 최대 하루 지연될 수 있음 | continuous recording과 기록 범위 최적화 |
| CloudTrail management event로 S3 object read를 감사 | data event가 기본 비활성이고 management와 단위가 다름 | advanced data event selector |
| Object Lock을 켜면 object access log가 생김 | Object Lock은 보존 통제이지 로그 생성이 아님 | CloudTrail data event와 별도 보존 |
| 2026년 6월에 새 계정으로 CloudTrail Lake 생성 | 2026-05-31부터 신규 고객 개방 중단 공지 | 기존 계정 자격 확인 또는 다른 저장소 설계 |
| Inspector finding을 생성 즉시 patched로 닫음 | finding은 취약점 관측이고 패치 성공을 보장하지 않음 | 배포, 재스캔, 예외 만료 확인 |
| Audit Manager report가 법적 compliance 인증서임 | Audit Manager는 evidence 수집과 보고 기능 | 감사인이 control evidence를 검토 |
| Security Lake 데이터를 S3 Select로 조회 | Security Lake의 저장 형식과 권한 경로가 별도임 | Lake Formation subscriber 또는 지원 쿼리 |
| logically air-gapped vault를 governance lock으로 생성 | air-gapped vault는 compliance lock을 사용 | 격리 계정과 최소 보존을 설계 |
| Vault Lock을 걸면 이전 recovery point에도 소급 | pre-lock recovery point는 새 lock 규칙 영향 밖 | lock 전 point의 별도 lifecycle 확인 |

이 표의 오답은 기능이 전혀 없는 서비스가 아니라, 요구사항의 입력이나 보호 대상이 다른 서비스를 선택한 경우입니다. 선지에서 "자동", "모든", "root", "객체 수준", "교차 계정" 같은 단어가 보이면 해당 서비스의 경계와 고정 한도를 먼저 대조합니다.

---

## 24. 예상 문제 10개로 경계를 확인한다

아래 문제는 서비스 이름을 맞히는 연습보다 요구사항의 제약, 고정 한도, 운영 책임을 먼저 읽는 연습에 초점을 둡니다. 다답형은 정답 조건이 모두 충족되어야 합니다.

**Q1.** 금융 회사가 온프레미스 HSM에서 생성한 key material을 AWS KMS에 임포트해(origin이 `EXTERNAL`) 문서 저장소를 암호화합니다. 내부 규정은 key material을 연 1회 이상 교체하도록 요구합니다. 콘솔에서 자동 rotation을 켜려 하자 옵션이 비활성입니다. 애플리케이션은 key ARN을 하드코딩하고 있어 수정할 수 없고, 이미 저장된 ciphertext는 재암호화 없이 계속 읽혀야 합니다. LEAST operational overhead로 요구를 충족하는 방법은 무엇입니까?

- A. 매년 새 key material을 준비해 같은 KMS key에 on-demand rotation을 실행한다.
- B. 매년 새 customer managed key를 만들어 alias를 옮기고 기존 데이터를 전부 재암호화한다.
- C. 이 키를 AWS CloudHSM key store로 옮기고 자동 rotation 주기를 365일로 설정한다.
- D. key material origin을 `AWS_KMS`로 변경한 뒤 자동 rotation을 활성화한다.

<details markdown="1">
<summary>정답과 해설</summary>

**정답: A**

on-demand rotation은 `AWS_KMS` origin과 `EXTERNAL` origin의 symmetric encryption key 양쪽에서 지원됩니다. rotation은 key ID, key ARN, 리전, 정책, 권한을 바꾸지 않고, 복호화 시 KMS가 해당 ciphertext를 암호화한 key material 버전을 자동으로 고릅니다. 따라서 하드코딩된 ARN과 기존 ciphertext가 모두 그대로 유지됩니다. 키당 on-demand rotation 25회 한도만 유의하면 됩니다.

- B가 틀린 이유: 요구를 만족시키기는 하지만 기존 데이터 전량 재암호화가 필요하고 매년 반복되므로 운영 부담이 가장 큽니다. rotation은 재암호화를 요구하지 않습니다.
- C가 틀린 이유: CloudHSM key store의 KMS key는 자동 rotation을 지원하지 않습니다. imported key material도 custom key store에서 지원되지 않으므로 이전 자체가 성립하지 않습니다.
- D가 틀린 이유: key material origin은 키 생성 시 결정되는 속성이고 자동 rotation은 `AWS_KMS` origin에서만 지원됩니다. `EXTERNAL` origin에 남겨둔 교체 경로는 on-demand rotation과 수동 교체뿐입니다.

</details>

---

**Q2.** 규제 대상 워크로드가 단일 테넌트 HSM에서 키 소재를 조직이 직접 통제할 것을 요구합니다. 현재 S3와 EBS는 KMS customer managed key로 암호화하고 있고, 추가로 파트너에게 전달하는 문서에 RSA 서명이 필요합니다. 팀은 모든 키를 CloudHSM key store에 만든 KMS key로 통일하는 안을 검토 중입니다. 요구를 모두 만족하는 MOST appropriate 구성은 무엇입니까?

- A. S3와 EBS용 symmetric key는 CloudHSM key store의 KMS key로 만들고, RSA 서명 키는 CloudHSM cluster에 직접 만들어 PKCS#11로 사용한다.
- B. CloudHSM key store에 RSA key pair를 만들고 KMS `Sign` API로 문서에 서명한다.
- C. 기본 KMS asymmetric key를 만들고 key policy로 서명 권한을 서명 서비스 role에만 부여한다.
- D. HSM 하나짜리 CloudHSM cluster를 만들어 key store에 연결하고 그 안에서 symmetric key와 asymmetric key를 모두 생성한다.

<details markdown="1">
<summary>정답과 해설</summary>

**정답: A**

CloudHSM key store에서 만들 수 있는 KMS key는 256-bit AES symmetric encryption key뿐입니다. 따라서 S3와 EBS의 서버측 암호화는 CloudHSM key store를 통해 단일 테넌트 HSM 요구를 만족시키고, asymmetric 서명은 KMS를 거치지 않고 CloudHSM cluster의 표준 라이브러리(PKCS#11 등)로 직접 수행하는 분리 구성이 유일하게 성립합니다.

- B가 틀린 이유: CloudHSM key store는 asymmetric key와 HMAC key를 지원하지 않습니다. RSA key pair를 그 안에 만들 수 없습니다.
- C가 틀린 이유: KMS의 일반 asymmetric key는 AWS가 관리하는 multi-tenant HSM 위에 있습니다. 조직이 키 소재를 단독 통제하라는 요구를 만족시키지 못합니다.
- D가 틀린 이유: CloudHSM key store에서 KMS key를 생성하려면 서로 다른 AZ에 active HSM이 2개 이상 있어야 합니다. HSM 하나로는 키 생성이 불가능하고 asymmetric key 미지원 제약도 그대로입니다.

</details>

---

**Q3.** 글로벌 SaaS가 us-east-1에서 애플리케이션 레벨(client-side)로 암호화한 데이터를 ap-northeast-2의 새 처리 계층에서도 복호화해야 합니다. 현재는 us-east-1의 단일 리전 customer managed key를 사용합니다. 요구는 두 리전에서 같은 ciphertext를 복호화하는 것이고, 리전 간 KMS 호출과 데이터 전송을 최소화해야 합니다. MOST appropriate 접근은 무엇입니까?

- A. 새 multi-Region primary key를 us-east-1에 만들고 ap-northeast-2에 replica key를 만든 뒤, 기존 데이터를 새 키로 재암호화한다.
- B. 기존 단일 리전 키를 multi-Region key로 승격하고 ap-northeast-2에 replica key를 만든다.
- C. ap-northeast-2에 별도 customer managed key를 만들고, 읽기 요청마다 us-east-1의 KMS를 호출해 복호화한 뒤 결과를 전달한다.
- D. S3 cross-Region replication을 켜고 양쪽 리전 키를 관련 multi-Region key로 지정해 재암호화 없이 복제한다.

<details markdown="1">
<summary>정답과 해설</summary>

**정답: A**

multi-Region key는 key ID와 key material을 공유하므로 한 리전에서 만든 ciphertext를 다른 리전의 related key로 재암호화 없이 복호화할 수 있습니다. 이 이득이 실제로 나타나는 지점이 client-side 암호화와 애플리케이션 레벨의 리전 간 데이터 이동입니다. 기존 데이터에 대한 1회 재암호화는 전환 비용으로 감수합니다.

- B가 틀린 이유: 기존 단일 리전 키를 multi-Region key로 전환할 수 없고 그 반대도 불가능합니다. multi-Region key는 처음부터 그렇게 생성해야 합니다.
- C가 틀린 이유: 읽기 경로마다 교차 리전 KMS 호출이 생겨 지연과 데이터 전송이 늘고, us-east-1 KMS에 대한 리전 간 의존이 남습니다. 요구가 명시한 최소화 조건과 반대입니다.
- D가 틀린 이유: S3 cross-Region replication은 두 리전 키가 관련 multi-Region key여도 목적지 리전 키로 data key를 재암호화합니다. 서버측 암호화 복제 요구를 multi-Region key로 푸는 선지는 성립하지 않습니다.

</details>

---

**Q4.** 데이터 계정(111111111111)의 S3 버킷이 customer managed key로 SSE-KMS 암호화되어 있습니다. 분석 계정(222222222222)의 IAM role이 `GetObject`를 호출하면 `AccessDenied`가 납니다. 관리자는 이미 222 계정 role의 IAM policy에 `kms:Decrypt`를 추가했고 버킷 정책에서도 그 role을 허용했습니다. 접근을 여는 MOST appropriate 조치는 무엇입니까?

- A. KMS key policy에 222 계정의 principal을 허용하는 문장을 추가한다.
- B. 버킷의 암호화를 AWS managed key(`aws/s3`)로 바꾼다.
- C. 222 계정 role에 대한 grant를 만들고 `kms:GrantIsForAWSResource` 조건을 붙인다.
- D. 버킷에 S3 Bucket Key를 활성화한다.

<details markdown="1">
<summary>정답과 해설</summary>

**정답: A**

KMS key policy는 다른 AWS resource policy와 달리 계정이나 그 계정의 principal에 권한을 자동으로 위임하지 않습니다. key policy가 대상 계정에 위임하지 않으면 그 계정 IAM policy의 allow는 효력이 없습니다. 교차 계정 KMS 접근은 key policy의 허용과 상대 계정 IAM policy의 허용이 둘 다 있어야 성립합니다.

- B가 틀린 이유: AWS managed key는 key policy를 편집할 수 없고 교차 계정 공유를 지원하지 않습니다. 상황이 더 나빠집니다.
- C가 틀린 이유: `kms:GrantIsForAWSResource` 조건은 사용자가 grant API를 직접 호출하는 것을 막고 통합 AWS 서비스가 대신 호출하는 경로만 허용합니다. 이 조건이 붙은 경로로는 분석 role이 grant를 만들 수 없습니다.
- D가 틀린 이유: S3 Bucket Key는 SSE-KMS의 KMS 요청 비용을 줄이는 기능이고 권한과 무관합니다. 오히려 encryption context가 object ARN에서 bucket ARN으로 바뀌어 object ARN을 조건으로 쓰던 정책을 깨뜨릴 수 있습니다.

</details>

---

**Q5.** 파트너 API 자격 증명을 90일마다 자동 교체해야 합니다. 자격 증명 번들에는 클라이언트 인증서가 포함되어 전체 크기가 약 30 KB입니다. 세 개의 워크로드 계정이 이 값을 읽어야 하고, 교체 로직은 파트너가 제공한 API를 호출해야 합니다. 현재는 SSM Parameter Store advanced tier에 저장하려다 실패했습니다. MOST appropriate 저장소 구성은 무엇입니까?

- A. AWS Secrets Manager에 저장하고 Lambda 기반 rotation을 90일 주기로 구성한 뒤 resource policy로 세 계정에 공유한다.
- B. Parameter Store advanced tier를 유지하고 parameter policy의 만료 알림으로 교체 시점을 통보받는다.
- C. Parameter Store standard tier로 내리고 EventBridge Scheduler가 호출하는 Lambda로 90일마다 값을 덮어쓴다.
- D. 값을 S3 객체로 두고 SSE-KMS로 암호화한 뒤 bucket policy로 세 계정에 공유한다.

<details markdown="1">
<summary>정답과 해설</summary>

**정답: A**

Secrets Manager의 secret value 상한은 65,536 bytes이므로 30 KB 번들을 담을 수 있습니다. 파트너 API 호출이 필요한 교체는 Lambda 기반 rotation으로 구현하고, resource policy로 교차 계정 읽기를 엽니다. 세 요구인 크기, 자동 교체, 교차 계정을 한 서비스가 모두 충족합니다.

- B가 틀린 이유: Parameter Store advanced tier의 값 상한은 8 KB라 30 KB를 저장할 수 없습니다. parameter policy는 만료 알림을 낼 뿐 값을 교체하지 않습니다.
- C가 틀린 이유: standard tier는 값 상한이 4 KB이고 교차 계정 공유를 지원하지 않습니다. 두 제약 모두에 걸립니다.
- D가 틀린 이유: S3에는 자동 교체 기능이 없어 rotation 스케줄과 버전 관리, 실패 롤백을 직접 구현해야 합니다. 자격 증명 수명주기 관리라는 요구의 핵심이 빠집니다.

</details>

---

**Q6.** 규제가 거래 문서를 7년간 변경 불가 상태로 보존하도록 요구합니다. 문서는 S3 버킷 하나에 쌓이고 있으며 versioning은 꺼져 있습니다. 문서는 하루 수만 건씩 새 객체로 추가되고 업로드 애플리케이션 코드는 수정할 수 없습니다. 운영 role은 `s3:*` 권한을 가지고 있고, 감사인은 account root user조차 보존 기간 안에 객체를 지울 수 없어야 한다고 명시했습니다. MOST appropriate 구성은 무엇입니까?

- A. 버킷에 versioning을 켜고 Object Lock을 활성화한 뒤 기본 보존 모드를 compliance, 기간을 7년으로 설정한다.
- B. 버킷에 versioning을 켜고 Object Lock을 governance mode 7년으로 설정한 뒤 `s3:BypassGovernanceRetention` 권한을 아무에게도 부여하지 않는다.
- C. 버킷 정책에 `s3:DeleteObject`와 `s3:DeleteObjectVersion`을 Deny하는 문장을 추가한다.
- D. S3 Glacier Vault Lock 정책을 만들어 이 버킷의 객체에 7년 보존을 강제한다.

<details markdown="1">
<summary>정답과 해설</summary>

**정답: A**

Object Lock은 versioning이 켜진 버킷에서만 동작하므로 versioning 활성화가 선행 조건입니다. compliance mode에서는 account root user를 포함해 누구도 보존 기간 안에 객체 버전을 덮어쓰거나 삭제할 수 없고, 모드 변경과 기간 단축도 불가능합니다. 문서가 명시한 유일한 예외 경로는 해당 AWS 계정을 삭제하는 것입니다.

- B가 틀린 이유: governance mode는 `s3:BypassGovernanceRetention` 권한과 `x-amz-bypass-governance-retention:true` header가 있으면 우회됩니다. root user는 IAM 정책을 바꿔 그 권한을 스스로 부여할 수 있으므로 감사 요구를 만족시키지 못합니다.
- C가 틀린 이유: 버킷 정책은 버킷 소유자가 언제든 수정하거나 제거할 수 있습니다. 정책 기반 통제는 WORM 보존의 증거가 되지 못합니다.
- D가 틀린 이유: S3 Glacier Vault Lock은 Glacier vault 전용 기능이고 S3 버킷의 객체에는 적용되지 않습니다. AWS Backup Vault Lock과도 다른 기능입니다.

</details>

---

**Q7.** Application Load Balancer 뒤의 주문 API가 최대 40 KB의 JSON body를 받습니다. 보안팀이 AWS WAF managed rule로 SQL injection을 막고 있는데, 8 KB를 넘는 위치에 payload를 배치한 요청이 검사를 통과합니다. 애플리케이션 코드는 수정할 수 없고 사용자 지연 증가는 최소화해야 합니다. MOST effective 조치는 무엇입니까?

- A. ALB 앞에 CloudFront distribution을 두고 web ACL을 CloudFront에 연결한 뒤 body 검사 한도를 상향한다.
- B. ALB에 연결된 web ACL의 request body 검사 한도를 64 KB로 올린다.
- C. rate-based rule의 rate limit을 5로 낮춰 대량 시도를 차단한다.
- D. Shield Advanced를 구독해 automatic application layer DDoS mitigation을 활성화한다.

<details markdown="1">
<summary>정답과 해설</summary>

**정답: A**

request body 검사 한도는 리소스 유형이 결정합니다. ALB와 AppSync는 8 KB 고정이고, CloudFront와 API Gateway와 Cognito와 App Runner와 Verified Access는 기본 16 KB에 설정으로 최대 64 KB까지 올릴 수 있습니다. 검사 지점을 CloudFront로 옮기면 코드 수정 없이 한도를 넓힐 수 있고 엣지 종단으로 지연도 개선됩니다.

- B가 틀린 이유: ALB의 body 검사 한도 8 KB는 고정값이라 설정으로 올릴 수 없습니다.
- C가 틀린 이유: rate-based rule에 지정할 수 있는 최소 rate는 10이라 5는 설정 자체가 불가능합니다. 또 rate 제한은 요청 빈도를 볼 뿐 body 내용을 검사하지 않습니다.
- D가 틀린 이유: Shield Advanced 구독은 표준 WAF 비용 일부를 흡수하고 L7 DDoS 완화 rule group을 추가하지만 body 검사 한도를 바꾸지 않습니다. 오히려 추가 rule group이 150 WCU를 소비합니다.

</details>

---

**Q8.** Organizations 전체 계정에 GuardDuty가 켜져 있고 CloudTrail organization trail은 management event만 기록합니다. 침해 사고 조사에서 유출된 access key로 특정 S3 버킷의 객체가 대량 다운로드된 사실이 확인됐지만 GuardDuty는 관련 finding을 내지 않았습니다. 같은 유형의 반출을 앞으로 탐지하려 합니다. LEAST operational overhead로 목표를 달성하는 방법은 무엇입니까?

- A. delegated administrator 계정에서 GuardDuty S3 Protection을 조직 전체에 활성화한다.
- B. 모든 계정에서 CloudTrail data event 로깅을 켜서 GuardDuty가 그 로그를 읽게 한다.
- C. Amazon Macie의 automated sensitive data discovery를 활성화한다.
- D. Amazon Detective를 활성화해 객체 접근 이력을 상시 감시한다.

<details markdown="1">
<summary>정답과 해설</summary>

**정답: A**

GuardDuty의 foundational data source는 CloudTrail management events, VPC Flow Logs, Route 53 Resolver DNS query logs이며 여기에는 S3 객체 수준 활동이 들어가지 않습니다. S3 데이터 반출을 탐지하려면 S3 Protection을 켜야 하고, delegated administrator에서 조직 전체에 한 번에 적용하는 것이 운영 부담이 가장 낮습니다.

- B가 틀린 이유: GuardDuty는 계정이 설정한 trail을 읽지 않고 독립된 복제 스트림을 읽습니다. 계정의 CloudTrail 설정이 GuardDuty의 처리 범위를 바꾸지 않으므로 data event를 켜도 finding이 생기지 않고 로그 비용만 늘어납니다.
- C가 틀린 이유: Macie는 S3 버킷의 민감 데이터 위치와 접근 통제 구성을 평가하는 도구입니다. 유출된 자격 증명에 의한 반출 행위 자체를 탐지하지 않습니다.
- D가 틀린 이유: Detective는 이미 발생한 finding의 원인을 behavior graph로 조사하는 도구입니다. 탐지 신호를 생성하지 않으므로 GuardDuty finding이 없으면 조사 출발점도 없습니다.

</details>

---

**Q9.** 비용 절감을 위해 팀이 AWS Config를 continuous recording에서 daily recording으로 바꿨습니다. 이후 Security Hub CSPM의 change-triggered control 결과가 위반 발생 후 최대 하루가 지나야 갱신되고, AWS Firewall Manager가 새로 만들어진 리소스에 WAF policy를 자동 적용하지 않는 문제가 함께 나타났습니다. MOST appropriate 조치는 무엇입니까?

- A. Config를 continuous recording으로 되돌리고 기록 대상 리소스 유형을 필요한 범위로 좁혀 비용을 관리한다.
- B. Security Hub CSPM을 central configuration으로 전환하고 configuration policy를 배포한다.
- C. 집계 계정에 Config aggregator를 만들어 거기서 rule을 배포하고 평가 주기를 앞당긴다.
- D. conformance pack의 배포 주기를 늘려 평가 부하를 분산한다.

<details markdown="1">
<summary>정답과 해설</summary>

**정답: A**

Config를 daily recording으로 두면 change-triggered control의 finding 생성이 최대 24시간 지연됩니다. 또 AWS Firewall Manager는 continuous recording에 의존하므로 daily로 두면 신규 리소스 자동 적용이 동작하지 않습니다. 두 증상의 원인이 같으므로 continuous recording 복원이 유일한 해결이고, 비용은 기록 대상 리소스 유형을 좁혀 조절합니다.

- B가 틀린 이유: central configuration은 위임 관리자가 표준과 control을 중앙에서 배포하는 기능입니다. 기록 빈도에서 오는 평가 지연을 해소하지 않고 Firewall Manager 문제와도 무관합니다.
- C가 틀린 이유: Config aggregator는 read-only 집계 도구입니다. aggregator를 통해 source 계정에 rule을 배포하거나 평가를 앞당길 수 없습니다.
- D가 틀린 이유: conformance pack은 rule과 remediation을 묶어 배포하는 단위이고 평가 트리거는 여전히 기록된 configuration item입니다. 배포 주기 조정으로 기록 빈도 문제를 우회할 수 없습니다.

</details>

---

**Q10.** 금융 규제 대응으로 특정 S3 버킷에 대한 객체 수준 접근 기록을 1년 동안 조사 가능한 상태로 보관해야 합니다. 감사인은 추가로 그 로그가 보관 기간 중 변조되지 않았음을 기술적으로 증명하라고 요구합니다. 현재는 management event만 기록하는 multi-Region trail 하나가 있습니다. 요구를 충족하는 조치 2개는 무엇입니까? (2개를 고르시오.)

- A. trail에 advanced event selector를 구성해 해당 버킷의 S3 data event를 기록하고, 로그를 S3에 두고 lifecycle로 1년간 보존한다.
- B. 그 trail의 log file integrity validation을 활성화하고 digest file로 로그 파일 무결성을 검증한다.
- C. CloudTrail Event history를 매월 CSV로 내려받아 별도 버킷에 보관한다.
- D. GuardDuty S3 Protection을 켜서 객체 접근 이력을 확보한다.
- E. AWS Config를 켜고 `AWS::S3::Bucket` 리소스 유형을 기록 대상에 넣는다.
- F. 로그 버킷에 Object Lock compliance mode를 설정해 객체 접근 기록을 자동 생성한다.

<details markdown="1">
<summary>정답과 해설</summary>

**정답: A, B**

trail과 event data store는 기본적으로 data event를 기록하지 않으므로, 객체 수준 접근을 남기려면 data event를 명시적으로 켜야 합니다. advanced event selector로 대상 버킷과 `eventName`을 좁히면 비용을 통제할 수 있습니다. 변조 증명은 log file integrity validation이 담당합니다. 매시간 생성되는 digest file이 직전 1시간치 로그 파일 목록과 각 파일의 SHA-256 hash를 담고, 각 digest가 이전 digest의 서명을 포함해 체인을 만듭니다.

- C가 틀린 이유: Event history는 리전별 최근 90일의 management event만 보여줍니다. data event를 담지 않고 1년 보관 요구도 만족시키지 못합니다.
- D가 틀린 이유: GuardDuty S3 Protection은 위협 finding을 생성할 뿐 원본 접근 로그를 계정에 남기지 않습니다. 감사 증적으로 쓸 수 없습니다.
- E가 틀린 이유: Config는 리소스 구성 상태의 변화를 기록합니다. 누가 어떤 객체를 읽었는지에 대한 API 호출 기록은 남기지 않습니다.
- F가 틀린 이유: Object Lock은 이미 저장된 객체의 보존을 강제하는 기능이고 접근 기록을 생성하지 않습니다. 로그 보호에는 도움이 되지만 요구된 두 축 중 어느 쪽도 단독으로 충족하지 못합니다.

</details>

---

## 25. Reference

- [AWS KMS key rotation](https://docs.aws.amazon.com/kms/latest/developerguide/rotate-keys.html)
- [AWS KMS key policies](https://docs.aws.amazon.com/kms/latest/developerguide/key-policy-default.html)
- [AWS KMS multi-Region keys](https://docs.aws.amazon.com/kms/latest/developerguide/multi-region-keys-overview.html)
- [AWS KMS custom key store with AWS CloudHSM](https://docs.aws.amazon.com/kms/latest/developerguide/keystore-cloudhsm.html)
- [AWS KMS quotas](https://docs.aws.amazon.com/kms/latest/developerguide/resource-limits.html)
- [AWS Systems Manager Parameter Store tiers](https://docs.aws.amazon.com/systems-manager/latest/userguide/parameter-store-advanced-parameters.html)
- [AWS Secrets Manager rotation](https://docs.aws.amazon.com/secretsmanager/latest/userguide/rotating-secrets.html)
- [AWS Secrets Manager quotas](https://docs.aws.amazon.com/secretsmanager/latest/userguide/reference_limits.html)
- [AWS Certificate Manager overview](https://docs.aws.amazon.com/acm/latest/userguide/acm-overview.html)
- [AWS Certificate Manager exportable public certificates](https://docs.aws.amazon.com/acm/latest/userguide/acm-exportable-certificates.html)
- [AWS Certificate Manager export public certificate procedure](https://docs.aws.amazon.com/acm/latest/userguide/export-public-certificate.html)
- [AWS Certificate Manager service options](https://docs.aws.amazon.com/acm/latest/userguide/service-options.html)
- [Amazon S3 default encryption FAQ](https://docs.aws.amazon.com/AmazonS3/latest/userguide/default-encryption-faq.html)
- [Amazon S3 Bucket Keys](https://docs.aws.amazon.com/AmazonS3/latest/userguide/bucket-key.html)
- [Amazon S3 Object Lock](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html)
- [Amazon S3 access point restrictions and limitations](https://docs.aws.amazon.com/AmazonS3/latest/userguide/access-points-restrictions-limitations.html)
- [AWS WAF quotas](https://docs.aws.amazon.com/waf/latest/developerguide/limits.html)
- [AWS WAF logging](https://docs.aws.amazon.com/waf/latest/developerguide/logging.html)
- [AWS Shield Advanced overview](https://docs.aws.amazon.com/waf/latest/developerguide/ddos-advanced-summary.html)
- [AWS Shield pricing](https://aws.amazon.com/shield/pricing/)
- [AWS Firewall Manager prerequisites](https://docs.aws.amazon.com/waf/latest/developerguide/fms-prereq.html)
- [Amazon GuardDuty data sources](https://docs.aws.amazon.com/guardduty/latest/ug/guardduty_data-sources.html)
- [Amazon GuardDuty Extended Threat Detection](https://docs.aws.amazon.com/guardduty/latest/ug/guardduty-extended-threat-detection.html)
- [Amazon GuardDuty Malware Protection for S3](https://docs.aws.amazon.com/guardduty/latest/ug/malware-protection-s3.html)
- [Amazon Inspector scanning resources](https://docs.aws.amazon.com/inspector/latest/user/scanning-resources.html)
- [Amazon Inspector score and severity](https://docs.aws.amazon.com/inspector/latest/user/findings-understanding-score.html)
- [AWS Security Hub CSPM prerequisites for AWS Config](https://docs.aws.amazon.com/securityhub/latest/userguide/securityhub-prereq-config.html)
- [AWS Security Hub central configuration](https://docs.aws.amazon.com/securityhub/latest/userguide/central-configuration-intro.html)
- [AWS Config remediation](https://docs.aws.amazon.com/config/latest/developerguide/remediation.html)
- [AWS Config conformance packs](https://docs.aws.amazon.com/config/latest/developerguide/conformance-packs.html)
- [Amazon Detective](https://docs.aws.amazon.com/detective/latest/userguide/what-is-detective.html)
- [Amazon Macie](https://docs.aws.amazon.com/macie/latest/user/what-is-macie.html)
- [Amazon Security Lake](https://docs.aws.amazon.com/security-lake/latest/userguide/what-is-security-lake.html)
- [AWS Audit Manager](https://docs.aws.amazon.com/audit-manager/latest/userguide/what-is.html)
- [AWS CloudTrail data events](https://docs.aws.amazon.com/awscloudtrail/latest/userguide/logging-data-events-with-cloudtrail.html)
- [AWS CloudTrail Event history](https://docs.aws.amazon.com/awscloudtrail/latest/userguide/view-cloudtrail-events.html)
- [AWS CloudTrail log file integrity validation](https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-log-file-validation-intro.html)
- [AWS CloudTrail Lake](https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-lake.html)
- [AWS Backup Vault Lock](https://docs.aws.amazon.com/aws-backup/latest/devguide/vault-lock.html)
- [AWS Backup logically air-gapped vault](https://docs.aws.amazon.com/aws-backup/latest/devguide/logicallyairgappedvault.html)

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
