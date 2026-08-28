---
title: AWS WAF Self-Managed Rule 알아보기 - ASN Match, Rate Limit, IP Set 운영
date: 2026-07-15 09:39:00 +0900
author: kkamji
categories: [Cloud, AWS]
tags: [aws, waf, cloudfront, security, firewall, asn, rate-limit, ip-set]
comments: true
image:
  path: /assets/img/aws/aws.webp
---

[이전 글](/posts/aws-waf/)에서는 AWS WAF의 Web ACL, Managed Rule Group, 비용과 공통 rollout을 다뤘습니다.

조직이 직접 근거와 만료를 관리해야 하는 self-managed rule을 `AsnMatchStatement`, IP set match, rate-based rule 세 가지를 중심으로 다룹니다. 각 수단의 선택 기준, ASN Match의 동작, Count에서 Block까지의 전환, ASN 차단의 한계를 정리합니다. 모든 예시는 일반화한 가상 값과 AWS 공식 문서만 사용합니다.

---

## 1. TL;DR

> - Self-managed rule은 AWS Managed Rules를 **대체하는 것이 아니라 보완**합니다. Managed Rule Group으로 공통 공격을 막고, 조직이 직접 근거를 관리해야 하는 좁은 조건만 self-managed rule로 다루는 조합이 안전합니다.  
> - `AsnMatchStatement`는 요청 IP가 속한 network 조직(ASN)을 기준으로 검사합니다. datacenter/hosting network 차단에 적합하며, bot 여부나 악성 의도를 증명하는 수단이 아닙니다.  
> - IP set match는 좁은 CIDR이나 긴급 임시 예외에, rate-based rule은 특정 고비용 path의 aggregate abuse 완화에 적합합니다. rate limit은 엄밀한 quota가 아니라 근사치 기반 탐지입니다.  
> - ASN Match는 rule당 최대 100개 ASN, 1 WCU이며 기본적으로 요청 origin IP를 사용합니다. forwarded IP 사용은 신뢰할 수 있는 proxy 전제에서만 안전합니다.  
> - 기존 Web ACL에 일반 custom ASN rule 하나를 추가하는 증분 비용은 rule당 월 $1이며, 그 rule 때문에 별도의 per-request 요금이 추가되지는 않습니다. 다만 Web ACL 단위 request 요금, WCU 초과, logging, Bot Control/CAPTCHA/Challenge 같은 유료 기능은 별개입니다.  
> - 안전한 전개 순서는 `Count -> 근거/metric/log 수집 -> 예외 조정 -> Block`이며, 명시적 만료일과 빠른 Count rollback을 항상 함께 둡니다.  
{: .prompt-info}

---

## 2. Self-managed rule은 언제 필요한가?

self-managed rule은 Managed Rule Group, 애플리케이션 인증과 권한 검사, 입력 검증, origin 보호를 대체하지 않습니다. 조직 고유의 traffic 근거가 있고 차단 사유와 재검토 시점을 직접 설명할 수 있을 때만 추가합니다.

| 구분 | Managed Rule Group | Self-managed rule |
| :--- | :--- | :--- |
| 작성과 갱신 주체 | AWS 또는 Marketplace 공급자 | 조직 본인 |
| 주 대상 | 공통 exploit, 알려진 악성 input, IP 평판, bot | 조직 고유 조건, 임시 차단, 특정 path 완화 |
| 근거와 만료 | 공급자 문서와 version 정책 | 조직이 차단 사유와 재검토 시점을 기록 |
| 변경 통제 | version pin과 update 감시 | priority, scope, action을 직접 소유 |

예를 들어 log에서 특정 hosting network에만 반복 abuse가 관찰되거나, 좁은 CIDR 예외와 특정 고비용 path의 완화가 필요할 때 self-managed rule을 검토합니다.

---

## 3. 세 가지 핵심 수단 비교

self-managed rule에서 가장 자주 쓰는 세 가지 statement는 목적과 정책 단위가 서로 다릅니다. 하나로 모든 문제를 풀기보다 조건에 맞는 수단을 고르는 것이 중요합니다.

| 항목 | ASN Match | IP set match | Rate-based rule |
| :--- | :--- | :--- | :--- |
| 정책 단위 | network 조직(ASN) | 개별 IP 또는 CIDR | 시간당 aggregate 요청량 |
| 적합한 용도 | datacenter/hosting network 차단, partner network 허용 | 좁은 CIDR 상시 차단, 긴급 임시 예외 | 특정 고비용 path의 abuse 완화 |
| 안정성 | ASN은 IP 대역보다 덜 바뀜 | IP는 자주 바뀌어 유지보수 필요 | window 기반 근사치, 주기적 갱신 |
| False positive 위험 | 대역이 넓어 collateral damage 큼 | 좁게 쓰면 낮음, 넓으면 높음 | threshold가 낮으면 정상 사용자 영향 |
| Lifecycle | 근거 기반으로 좁게, 만료 필요 | 임시 항목은 만료 필수 | threshold 재조정 주기 필요 |

ASN Match는 IP 대역을 일일이 관리하지 않고도 network 조직 단위로 제어할 수 있어 유지보수가 상대적으로 단순합니다. IP set은 대상 범위가 좁고 명확할 때 결과를 예측하기 쉽고, 긴급 대응에서 빠르게 적용하고 회수하기 좋습니다. rate-based rule은 특정 IP나 network를 겨냥하는 것이 아니라 "짧은 시간에 지나치게 많은 요청"이라는 행위 자체를 완화하는 수단입니다.

세 수단은 배타적이지 않습니다. 예를 들어 rate-based rule의 scope-down statement에 특정 path 조건을 넣어 집계 대상을 좁히고, 동시에 ASN Match로 알려진 hosting network를 별도 rule에서 관찰하는 식으로 함께 사용할 수 있습니다.

---

## 4. ASN Match Deep Dive

### 4.1. ASN이란 무엇인가

**ASN(Autonomous System Number)** 는 internet service provider, 대기업, 대학, 정부기관처럼 대규모 network를 운영하는 조직에 부여되는 고유 식별자입니다. AWS WAF의 ASN Match는 요청 IP가 어떤 ASN에 속하는지 판별해, 개별 IP를 관리하지 않고도 network 조직 단위로 traffic을 허용하거나 차단합니다. IP 대역보다 ASN이 덜 바뀌기 때문에 IP 기반 rule보다 안정적이고 효율적으로 운영할 수 있습니다.

대표적인 활용은 알려진 문제 network 차단과 신뢰하는 partner network 허용입니다. 다만 뒤에서 다루듯 ASN이 곧 "악성"을 뜻하지는 않으므로, 근거가 뒷받침되는 datacenter/hosting network에 좁게 적용해야 합니다.

### 4.2. 동작 방식과 forwarded IP 주의점

AWS WAF는 요청의 IP 주소로 ASN을 판별하며, **기본적으로 web request origin의 IP**를 사용합니다. CDN이나 reverse proxy 뒤에 있어 실제 client IP가 `X-Forwarded-For` 같은 header에 담기는 구성이라면, forwarded IP configuration을 켜서 header의 first, last, any 중 어떤 주소를 쓸지 지정할 수 있습니다.

forwarded IP를 사용할 때는 두 가지를 반드시 확인해야 합니다.

- **신뢰 경계**: header를 신뢰할 수 있는 proxy만 덮어쓰는지 확인해야 합니다. 공격자가 임의의 `X-Forwarded-For`를 주입할 수 있으면 ASN 판별과 다른 IP 기반 검사가 우회될 수 있습니다.
- **fallback behavior**: header의 IP가 malformed이거나 없을 때 적용할 결과를 `Match` 또는 `No match`로 지정합니다. `Match`로 두면 header가 깨진 요청이 모두 차단될 수 있고, `No match`로 두면 검사를 통과시키므로 정책 목적에 맞게 선택해야 합니다.

### 4.3. Unmapped ASN과 ASN 0

AWS WAF가 유효한 IP 주소에 대해 ASN을 판별하지 못하면 **ASN 0**을 할당합니다. 즉 ASN 0은 "매핑되지 않은 ASN"을 뜻하는 특수 값입니다. rule의 ASN list에 0을 포함하면 이런 unmapped 요청을 명시적으로 다룰 수 있습니다. 다만 unmapped라는 사실만으로 악성으로 단정할 수는 없으므로, ASN 0을 차단 대상에 넣을 때는 Count로 충분히 관찰한 뒤 결정해야 합니다.

### 4.4. 제약과 WCU

ASN Match statement의 특성은 다음과 같습니다.

| 항목 | 값 |
| :--- | :--- |
| ASN list 유효 범위 | 0 ~ 4294967295 |
| rule당 최대 ASN 수 | 100개 |
| WCU | 1 WCU |
| Nestable | 가능(다른 statement와 조합 가능) |
| 기본 IP 기준 | web request origin IP |
| forwarded IP | 선택, fallback behavior(`Match`/`No match`) 지정 |

rule당 ASN을 최대 100개까지만 지정할 수 있으므로, 차단 대상 network가 많다면 근거를 기준으로 우선순위를 정하거나 rule을 나눠야 합니다. 1 WCU로 매우 가벼운 statement이므로 WCU 예산 부담은 거의 없습니다.

### 4.5. Terraform 예시

다음은 이해를 돕기 위한 일반화된 예시입니다. ASN 값(`64496`, `64500`)은 문서 예약 대역의 placeholder이며, 실제 운영에서는 로그 근거로 확인한 network에 맞게 바꿔야 합니다. 처음에는 반드시 `count {}`로 시작합니다.

```hcl
resource "aws_wafv2_web_acl" "example" {
  name  = "example-web-acl"
  scope = "CLOUDFRONT" # CloudFront는 us-east-1 provider, Regional은 "REGIONAL"

  default_action {
    allow {}
  }

  rule {
    name     = "observe-hosting-asn"
    priority = 10

    # 최초 도입 시 count로 관찰, 근거 확보 후 block {} 으로 전환
    action {
      count {}
    }

    statement {
      asn_match_statement {
        # 예시 placeholder ASN. 실제 값은 근거 기반으로 교체
        asn_list = [64496, 64500]
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "observeHostingAsn"
      sampled_requests_enabled   = true
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "exampleWebAcl"
    sampled_requests_enabled   = true
  }
}
```

> `asn_match_statement`는 비교적 최근 AWS provider에 추가된 속성이므로, 적용 전 사용 중인 provider version과 schema에서 지원 여부를 확인해야 합니다. Terraform 예시는 개념 이해용이며 실제 account, distribution, ARN, hostname, 내부 ASN/IP를 포함하지 않습니다.  
{: .prompt-warning}

특정 path나 조건과 결합하려면 `asn_match_statement`를 `and_statement` 안에 nest해 scope를 좁힐 수 있습니다. 넓은 ASN 차단을 그대로 두기보다, 영향을 받는 path와 예외 대역을 함께 설계하는 편이 collateral damage를 줄입니다.

---

## 5. IP Set과 Rate-based Rule

### 5.1. IP set match

IP set은 여러 rule에서 재사용할 수 있는 별도 resource로, CIDR 목록을 담습니다. 대상이 명확하고 좁을 때 가장 예측 가능한 수단이며, 긴급 상황에서 빠르게 추가하고 제거하기 좋습니다. IP는 ASN보다 자주 바뀌므로, 넓은 대역을 상시 차단 목적으로 쌓아 두기보다 좁은 CIDR이나 임시 예외 중심으로 관리하는 것이 유지보수에 유리합니다.

임시로 넣은 IP set 항목은 반드시 만료 기준을 함께 기록해야 합니다. 근거 없이 오래 남은 차단 항목은 나중에 원인을 추적하기 어렵고 정상 사용자를 막을 위험이 커집니다.

WCU 관점에서 IP set match statement는 대부분의 사용에서 1 WCU입니다. 다만 forwarded IP를 사용하면서 header 내 position을 `ANY`로 지정하면 여기에 4 WCU가 추가됩니다.

### 5.2. Rate-based rule

self-managed rate-based rule은 scope-down statement로 대상 path를 좁히고, aggregation key와 threshold를 traffic 근거에 맞춰 선택합니다.

다음은 특정 고비용 path에만 rate limit을 적용하는 일반화 예시입니다. `limit`과 path 값은 workload마다 반드시 재검증해야 하는 placeholder입니다.

```hcl
  rule {
    name     = "rate-limit-expensive-path"
    priority = 20

    action {
      count {} # 관찰 후 block {} 전환
    }

    statement {
      rate_based_statement {
        limit                 = 2000 # 예시 threshold, 실제 traffic으로 재조정
        aggregate_key_type    = "IP"
        evaluation_window_sec = 300

        scope_down_statement {
          byte_match_statement {
            search_string         = "/expensive-path" # 예시 path
            positional_constraint = "STARTS_WITH"

            field_to_match {
              uri_path {}
            }

            text_transformation {
              priority = 0
              type     = "NONE"
            }
          }
        }
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "rateLimitExpensivePath"
      sampled_requests_enabled   = true
    }
  }
```

scope-down으로 집계 대상을 좁히면 정상 traffic이 threshold 계산에 섞이는 것을 줄여 false positive를 낮출 수 있습니다.

WCU 관점에서 rate-based rule statement의 기본 비용은 2 WCU입니다. 여기에 scope-down statement를 사용하면 그 statement 자체의 WCU가 더해지고, custom aggregation key를 지정하면 key 하나당 30 WCU가 추가됩니다. 위 예시는 `aggregate_key_type = "IP"`처럼 aggregation key로 source IP만 사용하므로 key당 30 WCU 가산이 적용되지 않고, 기본 2 WCU에 scope-down으로 넣은 `byte_match_statement`의 WCU만 더해집니다. 여러 field를 조합한 custom key를 쓰는 경우에만 key 개수만큼 30 WCU씩 늘어난다는 점을 예산 계산 시 구분해야 합니다.

---

## 6. 안전한 운영 - self-managed rule에 추가할 것

self-managed rule에는 다음 운영 정보가 필요합니다.

1. **근거와 policy owner**: 어떤 log 근거로 어떤 network 또는 path를 대상으로 하는지, 소유자와 재검토 시점을 기록합니다.
2. **명시적 만료**: 임시 ASN 또는 CIDR 차단은 만료일을 둡니다. 근거 없이 남은 항목은 false positive를 추적하기 어렵습니다.
3. **좁은 예외와 빠른 rollback**: false positive는 넓은 차단을 새로 추가하기보다 IP set 예외 또는 scope-down으로 좁게 처리하고, 문제가 생기면 우선 `Count`로 되돌립니다.
4. **전파 지연**: CloudFront Web ACL 변경은 global edge에 반영될 시간이 필요합니다. Block과 rollback의 효과를 같은 관찰 창에서 성급하게 판단하지 않습니다.

값, 근거, 만료, owner는 IaC와 review 기록으로 관리합니다. 다만 실제 운영의 ASN, IP, 내부 log와 traffic 수치는 공개 저장소에 넣지 않습니다.

![WAF rule rollout flow](/assets/img/aws/waf-rule-rollout-flow.webp)

---

## 7. 한계와 결합 전략

ASN Match는 강력하지만 오용하기 쉬운 수단입니다. 다음 한계를 분명히 이해해야 합니다.

- **ASN은 bot이나 악성 의도의 증거가 아니다**: 특정 ASN에서 왔다는 사실만으로 그 요청이 bot이거나 악의적이라고 단정할 수 없습니다. datacenter/hosting network에서도 정상적인 monitoring, 정당한 API client, 검색 엔진 crawler가 나올 수 있습니다. ASN Match는 "network 조직 단위 정책"이지 "identity 판별기"가 아닙니다.
- **residential, mobile, CGNAT, enterprise NAT 대역은 부적합하다**: 가정용 ISP, 모바일 통신망, CGNAT, 기업 NAT은 수많은 정상 사용자가 소수의 ASN과 IP를 공유합니다. 이런 대역을 ASN으로 넓게 차단하면 대규모 정상 사용자를 함께 막게 됩니다. ASN 차단은 근거가 뒷받침되는 datacenter/hosting network에 좁게 한정해야 합니다.
- **residential proxy를 막지 못한다**: 공격자가 residential proxy를 경유하면 정상 가정용 ASN으로 위장하므로 ASN Match만으로는 걸러지지 않습니다.

ASN Match는 단독 방어선이 아닙니다. self-managed rule은 조직 고유의 network 정책을 좁게 보완하는 수단이며, 적용 근거와 만료 조건을 계속 검토해야 합니다.

---

## 8. 마무리

Self-managed rule의 핵심은 rule을 많이 만드는 것이 아니라, **조직이 근거를 설명하고 만료시킬 수 있는 좁은 정책을 안전하게 운영하는 것**입니다. ASN Match는 network 조직 단위로 datacenter/hosting traffic을 다루기에 유용하고, IP set은 좁고 명확한 대상에, rate-based rule은 특정 path의 aggregate abuse 완화에 적합합니다.

세 수단 모두 Managed Rule Group을 대체하지 않으며 bot 여부를 증명하지도 않습니다. 근거를 기록하고 Count로 관찰한 뒤 예외를 좁혀 Block으로 전환하고, 명시적 만료와 빠른 rollback을 갖추는 절차가 도구 자체보다 중요합니다.

---

## 9. Reference

- [AWS Docs - Autonomous System Number (ASN) match rule statement](https://docs.aws.amazon.com/waf/latest/developerguide/waf-rule-statement-type-asn-match.html)
- [AWS Docs - AsnMatchStatement API](https://docs.aws.amazon.com/waf/latest/APIReference/API_AsnMatchStatement.html)
- [AWS Docs - IP set match rule statement](https://docs.aws.amazon.com/waf/latest/developerguide/waf-rule-statement-type-ipset-match.html)
- [AWS Docs - Rate-based rule statement](https://docs.aws.amazon.com/waf/latest/developerguide/waf-rule-statement-type-rate-based.html)
- [AWS Docs - Using forwarded IP addresses](https://docs.aws.amazon.com/waf/latest/developerguide/waf-rule-statement-forwarded-ip-address.html)
- [AWS Docs - Testing and tuning AWS WAF protections](https://docs.aws.amazon.com/waf/latest/developerguide/web-acl-testing.html)
- [AWS Docs - AWS WAF web ACL capacity units (WCU)](https://docs.aws.amazon.com/waf/latest/developerguide/aws-waf-capacity-units.html)
- [AWS Docs - AWS WAF quotas](https://docs.aws.amazon.com/waf/latest/developerguide/limits.html)
- [AWS - AWS WAF Pricing](https://aws.amazon.com/waf/pricing/)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
