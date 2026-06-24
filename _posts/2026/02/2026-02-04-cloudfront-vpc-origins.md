---
title: Amazon CloudFront VPC Origins 알아보기
date: 2026-02-04 18:00:00 +0900
author: kkamji
categories: [Cloud, AWS]
tags: [aws, cloudfront, vpc, cdn, security, alb, nlb, ec2]
comments: true
image:
  path: /assets/img/aws/aws.webp
---

CloudFront를 ALB나 EC2 앞단에 두려고 하면, 정작 오리진(origin)은 퍼블릭 서브넷에 두고 퍼블릭 IP를 부여해야 했습니다. 그러면서도 "CloudFront만 들어오게" 하려고 Security Group에 CloudFront managed prefix list를 걸거나, 커스텀 헤더를 검증하는 등 추가 작업이 필요했고, 결국 오리진이 인터넷에 노출되는 구조 자체는 그대로 남았습니다.
**Amazon CloudFront VPC Origins**는 이 문제를 정면으로 해결합니다. 프라이빗 서브넷에 있는 ALB/NLB/EC2를 CloudFront 오리진으로 직접 연결해, 오리진을 인터넷에 노출하지 않고도 CloudFront를 유일한 진입점으로 만들 수 있습니다.
이번 포스트에서는 VPC Origins가 무엇이고, 기존 방식과 무엇이 다르며, 어떻게 동작하고 어떤 준비물과 제약이 있는지를 개요 수준에서 정리합니다.

> **TL;DR**  
> - VPC Origins는 프라이빗 서브넷의 ALB/NLB/EC2를 CloudFront 오리진으로 직접 연결하는 관리형 기능입니다.  
> - 오리진에 **퍼블릭 IP가 필요 없고**, CloudFront가 유일한 진입점이 되어 공격 표면이 줄어듭니다.  
> - 트래픽은 CloudFront -> 서비스 관리형 ENI -> 오리진으로 AWS 백본망을 통해 사설 경로로 흐릅니다.  
> - 기능 자체는 **추가 비용 없이** 제공되며, Seoul(ap-northeast-2) 리전을 포함해 다수 리전에서 지원됩니다.  
{: .prompt-info}

---

## 1. CloudFront VPC Origins란?

**CloudFront VPC Origins**는 VPC 프라이빗 서브넷에서 호스팅하는 애플리케이션을 CloudFront 오리진으로 직접 지정할 수 있게 해주는 기능입니다. 오리진으로 사용할 수 있는 리소스는 다음과 같습니다.

- **Application Load Balancer (ALB)**
- **Network Load Balancer (NLB)**
- **EC2 인스턴스**

이 리소스들을 프라이빗 서브넷에 둔 채로 CloudFront에 연결하면, 사용자 요청은 CloudFront 엣지에서 출발해 AWS 백본 네트워크를 거쳐 오리진까지 **사설(private) 경로**로 전달됩니다. 오리진은 퍼블릭 IP나 퍼블릭 DNS 없이도 동작하며, CloudFront가 사실상 유일한 수신 지점이 됩니다.

ECS/Fargate처럼 직접 지정할 수 없는 워크로드도 앞단에 ALB를 두면 ALB를 VPC Origin으로 등록해 동일한 구조로 보호할 수 있습니다.

---

## 2. 기존 방식의 한계와 VPC Origins

VPC Origins 이전에는 ALB/EC2 같은 오리진을 CloudFront 뒤에 두려면 오리진을 퍼블릭하게 노출한 뒤, "CloudFront에서 온 요청만" 통과시키도록 별도 장치를 직접 구성해야 했습니다.

| 항목                | 기존 퍼블릭 오리진 방식                                   | VPC Origins 방식                                  |
| :------------------ | :------------------------------------------------------- | :------------------------------------------------ |
| **오리진 위치**     | 퍼블릭 서브넷 + 퍼블릭 IP 필요                            | 프라이빗 서브넷, 퍼블릭 IP 불필요                 |
| **접근 제어**       | SG에 prefix list, 커스텀 헤더 검증 등 직접 구현           | CloudFront가 유일 진입점, 관리형으로 처리          |
| **인터넷 노출**     | 오리진이 인터넷에 노출된 채로 남음                        | 오리진이 인터넷에서 발견되지 않음                  |
| **운영 부담**       | ACL/방화벽/헤더 검증 로직 유지보수 필요                   | 별도 차별화되지 않는(undifferentiated) 작업 제거   |

핵심 차이는 **공격 표면**입니다. 기존 방식은 오리진이 결국 인터넷에 열려 있고 "필터링으로 막는" 구조였다면, VPC Origins는 오리진 자체를 프라이빗으로 두고 CloudFront 외에는 도달 경로를 없애는 방식입니다.

> VPC Origins는 그 자체로 WAF나 Shield를 대체하지 않습니다. 웹 공격 방어(AWS WAF), DDoS 방어(AWS Shield)는 여전히 별도로 구성하는 계층 방어 관점에서 함께 사용하는 것이 권장됩니다.  
{: .prompt-warning}

---

## 3. 작동 방식

VPC Origin을 만들면 CloudFront가 대상 프라이빗 서브넷에 **서비스 관리형 ENI(elastic network interface)** 를 생성하고, 이 ENI를 통해 오리진으로 트래픽을 라우팅합니다. 전체 흐름을 정리하면 다음과 같습니다.

![CloudFront VPC Origins 트래픽 흐름](/assets/img/aws/cloudfront-vpc-origins-flow.webp)
_CloudFront 엣지 -> 서비스 관리형 ENI(프라이빗 서브넷) -> 오리진. AWS 백본망을 통한 사설 경로_

- **서비스 관리형 ENI**: CloudFront가 VPC Origin 정의 시 프라이빗 서브넷에 자동 생성합니다. 그래서 서브넷에 사용 가능한 IPv4 주소가 최소 1개 있어야 합니다.
- **서비스 관리형 Security Group**: VPC Origin을 만들면 `CloudFront-VPCOrigins-Service-SG` 패턴의 SG가 AWS에 의해 자동 생성·관리됩니다. 이 SG는 사용자가 직접 편집하지 않습니다.
- **오리진 SG 인바운드 허용**: 오리진(ALB/NLB/EC2)에 붙은 Security Group에서 CloudFront 트래픽을 받도록 다음 중 하나로 인바운드를 허용합니다.
  - **CloudFront managed prefix list 허용**: VPC Origin 생성 전에도 설정할 수 있습니다. 다만 이 prefix list는 모든 CloudFront 엣지의 IP 범위를 포함하므로 "CloudFront 전체"를 허용하는 넓은 규칙입니다.
  - **서비스 관리형 SG(`CloudFront-VPCOrigins-Service-SG`) 허용**: VPC Origin 생성 후에만 가능합니다. 트래픽을 "본인의 CloudFront 배포로만" 제한하므로 prefix list보다 더 좁고 안전합니다.

  빠르게 시작하려면 prefix list로 열고, 최소 권한으로 좁히려면 VPC Origin 생성 후 서비스 관리형 SG로 전환하는 흐름이 자연스럽습니다.

> 여기서 트래픽이 도는 경로는 인터넷이 아니라 VPC 내부입니다. CloudFront가 만든 ENI가 프라이빗 서브넷 안에 있고, 그 ENI를 통해 오리진에 닿기 때문입니다. 그래서 Internet Gateway는 "이 VPC가 인터넷 트래픽을 받을 수 있음"을 표시하기 위해 필요할 뿐 오리진으로의 라우팅에는 사용되지 않고, route table을 따로 수정할 필요도 없습니다. 같은 이유로 서브넷 레벨 규칙인 **NACL도 이 트래픽에는 평가되지 않습니다**(6절 참고).  
{: .prompt-tip}

---

## 4. 사용 전 준비사항

VPC Origin을 만들기 전에 다음이 갖춰져 있어야 합니다.

| 구분            | 준비 내용                                                                       |
| :-------------- | :------------------------------------------------------------------------------ |
| **VPC**         | 지원 리전에 VPC 생성, **Internet Gateway** 연결                                  |
| **서브넷**      | **사용 가능한 IPv4 주소가 1개 이상 있는 프라이빗 서브넷** (IPv6-only 서브넷 미지원) |
| **오리진 리소스** | ALB/NLB/EC2가 완전히 배포되어 **Active** 상태                                  |
| **Security Group** | 오리진 리소스에 SG 연결 (NLB도 SG가 반드시 부착되어 있어야 함)                |

ENI 생성을 위해 프라이빗 IP 한 개를 사용하지만, 이 IPv4 주소에 대한 추가 비용은 없습니다.

---

## 5. 설정 흐름

CloudFront 콘솔 또는 AWS CLI/SDK(`CreateVpcOrigin`, `CreateDistribution` 등)로 설정할 수 있습니다. 콘솔 기준 큰 흐름은 다음과 같습니다.

1. CloudFront 콘솔에서 **VPC origins -> Create VPC origin** 선택
2. **Origin ARN**에 대상 ALB/NLB/EC2의 ARN을 선택(또는 붙여넣기)하고 생성
3. VPC Origin 상태가 **Deployed**가 될 때까지 대기 (최대 약 15분 소요)
4. 배포(Distribution)를 새로 만들거나 기존 배포에 해당 VPC Origin을 오리진으로 연결
   - EC2를 오리진으로 쓰는 경우, Origin domain에는 인스턴스의 **Private IP DNS name**을 사용
5. (마이그레이션 시) 검증 후 서브넷을 프라이빗으로 전환해 오리진의 퍼블릭 접근 제거

기존 배포에 무중단으로 적용하려면 CloudFront **continuous deployment(staging distribution)** 로 먼저 검증한 뒤 프로모션하는 방식을 사용할 수 있습니다.

AWS CLI로 VPC Origin을 만들 때는 `create-vpc-origin`에 엔드포인트 설정을 전달합니다.

```bash
# VPC Origin 생성 예시
❯ aws cloudfront create-vpc-origin \
  --vpc-origin-endpoint-config '{
    "Name": "my-alb-vpc-origin",
    "Arn": "arn:aws:elasticloadbalancing:ap-northeast-2:111122223333:loadbalancer/app/my-alb/abc123",
    "HTTPPort": 80,
    "HTTPSPort": 443,
    "OriginProtocolPolicy": "https-only"
  }'
```

| 필드                   | 설명                                                       |
| :--------------------- | :--------------------------------------------------------- |
| `Name`                 | VPC Origin 식별용 이름                                     |
| `Arn`                  | 오리진으로 쓸 ALB/NLB/EC2의 ARN                            |
| `HTTPPort`/`HTTPSPort` | 오리진과 통신할 포트 (기본 80 / 443)                       |
| `OriginProtocolPolicy` | `http-only` / `https-only` / `match-viewer` 중 선택        |

---

## 6. 제약 사항 및 주의점

도입 전에 확인해 두면 좋은 제약들입니다.

**오리진 리소스 제약**

- Gateway Load Balancer(GWLB)는 오리진으로 사용할 수 없음
- Dual-stack NLB는 오리진으로 사용할 수 없음
- TLS 리스너를 가진 NLB는 오리진으로 사용할 수 없음
- NLB를 VPC Origin으로 쓰려면 NLB에 Security Group이 부착되어 있어야 함

**프로토콜/기능 제약**

- gRPC 트래픽 미지원
- Lambda@Edge의 origin request / origin response 트리거 미지원
- NACL(Network ACL) 미평가: 이 트래픽에는 서브넷 레벨 allow/deny 규칙이 적용되지 않음 (SG와 NACL의 차이는 [Stateful과 Stateless (NACL vs Security Group)](/posts/stateless-vs-stateful/) 참고)

**리전 / 계정 / 비용**

- Seoul(ap-northeast-2)을 포함한 다수 상용 리전에서 지원되며, 일부 리전은 특정 AZ가 제외됨
- VPC Origin은 AWS RAM을 통해 **계정 간 공유**가 가능 (조직 내/외 모두)
- VPC Origins **기능 자체는 추가 비용 없음**. 단, CloudFront 배포 기본 요금과 데이터 전송 비용은 평소처럼 별도 청구됨

> 서비스 관리형 SG와 동일하게 `CloudFront-VPCOrigins-Service-SG`로 시작하는 이름의 SG를 직접 만들지 마세요. AWS가 예약한 네이밍 패턴입니다.  
{: .prompt-warning}

---

## 7. Reference

- [AWS Docs - Restrict access with VPC origins](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-vpc-origins.html)
- [AWS Docs - CreateVpcOrigin API](https://docs.aws.amazon.com/cloudfront/latest/APIReference/API_CreateVpcOrigin.html)
- [AWS Docs - Introducing Amazon CloudFront VPC origins](https://aws.amazon.com/blogs/aws/introducing-amazon-cloudfront-vpc-origins-enhanced-security-and-streamlined-operations-for-your-applications/)
- [AWS Docs - Migrate CloudFront public origins to private VPC origins](https://aws.amazon.com/blogs/networking-and-content-delivery/migrate-amazon-cloudfront-public-origins-to-private-vpc-origins/)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
