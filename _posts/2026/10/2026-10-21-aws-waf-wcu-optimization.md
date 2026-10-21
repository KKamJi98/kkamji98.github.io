---
title: "AWS WAF WCU 아끼기 - 1,500 WCU 안에서 봇 대응 룰을 설계하는 방법"
date: 2026-10-21 23:30:00 +0900
author: kkamji
categories: [Cloud, AWS]
tags: [aws, waf, wcu, bot, regex, label, terraform, security, cost]
comments: true
image:
  path: /assets/img/aws/aws.webp
---

봇 트래픽은 사람의 트래픽과 모양이 다릅니다. 사람의 요청은 하루 주기를 따라 완만하게 오르내리지만, 봇은 몇 분 만에 요청을 평소의 몇 배로 올렸다가 내려놓는 경우가 흔합니다. 또 봇은 캐시에 잘 걸리지 않는 페이지와 로그인, 검색처럼 비싼 엔드포인트를 반복해서 두드리므로, 같은 요청 수라도 오리진이 치르는 비용은 사람 트래픽보다 큽니다.

이런 트래픽을 AWS WAF로 막다 보면 rule이 하나씩 늘어납니다. **AWS WAF는 Web ACL이 1,500 WCU를 넘으면 그 Web ACL이 검사하는 모든 요청의 단가를 올립니다.** 새 rule 하나의 비용이 그 rule에 매칭된 요청이 아니라 트래픽 전체에 붙습니다. 같은 판정을 더 적은 WCU로 쓰는 방법을 정리했고, 방법마다 WCU를 `CheckCapacity` API로 직접 재서 확인했습니다. 측정은 2026년 10월 21일에 AWS CLI 2.38.3으로 `ap-northeast-2` 리전의 `REGIONAL` scope에서 했습니다. 예시 rule은 설명을 위해 만든 것입니다.

> **TL;DR**  
>
> - WCU는 rule 평가 비용의 단위다. Web ACL 기본 요금에 1,500 WCU가 포함되고, 넘으면 500 WCU 구간마다 요청 100만 건당 $0.20이 모든 요청에 붙는다.  
> - AWS 관리형 룰 그룹 6개(CRS, Known bad inputs, SQLi, Linux, Amazon IP reputation, Anonymous IP)만 넣어도 1,375 WCU다. custom rule에 남는 예산은 125 WCU다.  
> - 비싼 것은 `CONTAINS`(10), text transformation(10), JSON body(2배), 사용자 rule group에 예약한 capacity다. 정규식은 3, label match는 1이다.  
> - 같은 request component에 같은 변환 순서를 쓰면 변환 비용은 Web ACL 전체에서 한 번만 잡혔다. 변환 순서, component, header 이름 표기 중 하나라도 다르면 따로 잡혔다.  
> - 예시 Web ACL은 판정을 바꾸지 않고 1,505 WCU에서 1,429~1,430 WCU로 내려갔다. 요청 단가는 100만 건당 $0.80에서 $0.60으로 돌아왔다.  
{: .prompt-info}

---

## 1. 봇 트래픽은 요청 수보다 비용이 큽니다

봇이 문제가 되는 이유는 요청이 많아서만이 아닙니다. 봇 트래픽에는 사람 트래픽과 다른 특징이 몇 가지 있고, 특징마다 서버에 주는 영향과 WAF에 늘어나는 rule이 다릅니다.

| 봇 트래픽의 특징 | 서버에 주는 영향 | WAF에서 늘어나는 rule |
| :--- | :--- | :--- |
| 몇 분 단위의 급격한 스파이크 | 오토스케일링이 따라가기 전에 오리진이 포화되고 5XX와 지연이 늘어난다 | rate-based rule |
| 캐시에 없는 페이지와 비싼 엔드포인트 반복 | CDN 캐시 적중률이 떨어지고 렌더링과 DB 부하가 커진다 | 경로별 rule |
| IP를 자주 바꾸는 분산 요청 | IP당 한도에 걸리지 않는다 | 헤더, TLS 지문 기반 rule |
| 브라우저처럼 보이려는 헤더 | 단순한 UA 차단을 피한다 | 탐지 rule과 예외 rule |

IP와 ASN 기반 대응은 [AWS WAF Self-Managed Rule 글](/posts/aws-waf-self-managed-rule/)에서, Challenge의 동작은 [AWS WAF Challenge Action 글](/posts/aws-waf-javascript-challenge/)에서 다뤘습니다. 어느 쪽이든 대응이 쌓일수록 rule이 늘고, rule이 늘수록 WCU가 쌓입니다.

---

## 2. 1,500 WCU를 넘으면 모든 요청의 단가가 오릅니다

**WCU(Web ACL Capacity Unit)** 는 AWS WAF가 rule, rule group, Web ACL을 평가하는 데 드는 계산 비용을 나타내는 단위입니다. 초당 처리량이 아니고, AWS 문서도 WCU가 검사 방식에 영향을 주지 않는다고 설명합니다. 대신 가격과 한도에 직접 연결됩니다.

- Web ACL 기본 요금에는 1,500 WCU까지 포함된다.
- 1,500을 넘으면 500 WCU 구간마다 요청 100만 건당 $0.20이 더해진다.
- Web ACL 하나와 rule group 하나의 최대 용량은 각각 5,000 WCU다.

{% include diagrams/static/aws/waf-wcu/waf-wcu-billing-tiers.html %}
{% include diagrams/download.html png="/assets/img/diagrams/static/aws/waf-wcu/waf-wcu-billing-tiers--8ba0797692af5346.png" %}

**가산 요금은 새 rule에 매칭된 요청이 아니라 Web ACL이 검사하는 전체 요청에 붙습니다.** 기본 요청 단가가 100만 건당 $0.60이므로, 1,500을 1 WCU만 넘어도 요청 요금이 3분의 1만큼 늘어납니다. Web ACL이 월 3억 건을 검사한다고 가정하고 계산하면 다음과 같습니다.

| Web ACL 용량 | 요청 단가 (100만 건당) | 월 3억 건 요청 요금 | 1,500 이하 대비 |
| :--- | ---: | ---: | ---: |
| 1,500 WCU 이하 | $0.60 | $180 | - |
| 1,501~2,000 WCU | $0.80 | $240 | +$60 |
| 2,001~2,500 WCU | $1.00 | $300 | +$120 |

Web ACL 월 $5와 rule당 월 $1는 별도입니다. 단가는 2026년 10월의 AWS WAF Pricing 페이지 기준입니다.

1,500은 생각보다 빨리 찹니다. 흔히 함께 쓰는 AWS 관리형 룰 그룹이 이미 대부분을 씁니다. 아래 값은 `DescribeManagedRuleGroup`으로 확인했고, 6개를 한 번에 넣은 `CheckCapacity` 결과도 1,375였습니다.

| 관리형 룰 그룹 | WCU |
| :--- | ---: |
| `AWSManagedRulesCommonRuleSet` (CRS) | 700 |
| `AWSManagedRulesKnownBadInputsRuleSet` | 200 |
| `AWSManagedRulesSQLiRuleSet` | 200 |
| `AWSManagedRulesLinuxRuleSet` | 200 |
| `AWSManagedRulesAmazonIpReputationList` | 25 |
| `AWSManagedRulesAnonymousIpList` | 50 |
| 합계 | 1,375 |

이 구성이면 custom rule에 쓸 수 있는 예산은 125 WCU입니다. 관리형 룰 그룹의 WCU는 버전에 따라 바뀔 수 있으므로 실제 값은 `DescribeManagedRuleGroup`으로 확인합니다.

---

## 3. WCU는 이렇게 계산됩니다

### 3.1. statement 단가표

rule의 WCU는 statement 종류별 기본값에 옵션 비용을 더해 정해집니다. AWS 문서의 값과, 같은 statement를 `CheckCapacity`로 잰 값을 함께 적었습니다. IP set과 regex pattern set은 실제 리소스의 ARN이 있어야 잴 수 있어서 문서 값만 적었습니다.

| Statement | 문서 WCU | 실측 WCU | 추가 비용 |
| :--- | ---: | ---: | :--- |
| Label match | 1 | 1 | - |
| ASN match, Geo match | 1 | 1 | - |
| Size constraint | 1 | 1 | - |
| IP set match | 1 | - | forwarded IP의 position이 `ANY`면 +4 |
| String match `EXACTLY`, `STARTS_WITH`, `ENDS_WITH` | 2 | 2 | - |
| String match `CONTAINS`, `CONTAINS_WORD` | 10 | 10 | - |
| Regex match | 3 | 3 | - |
| Regex pattern set match | 25 | - | - |
| SQL injection (LOW / HIGH) | 20 / 30 | 20 / 30 | - |
| XSS | 40 | 40 | - |
| Rate-based | 2 | 2 | custom aggregation key마다 +30, scope-down statement 비용 |
| AND, OR, NOT | - | - | 안에 넣은 statement의 WCU를 더한다 |

match statement에는 공통 옵션 비용이 붙습니다.

| 옵션 | 문서 | 실측 (Regex match 기준) |
| :--- | :--- | ---: |
| text transformation | 하나에 +10 | 변환 1개 13, 2개 23 |
| request component `All query parameters` | +10 | 13 |
| request component `JSON body` | 기본값 2배 | 6 |
| request component `Query string` | 추가 없음 | 3 |

### 3.2. rule group은 만들 때 정한 capacity로 잡힙니다

직접 만든 rule group은 만들 때 정한 capacity가 있고, 이 값은 바꿀 수 없습니다. 관리형 룰 그룹은 버전마다 AWS가 정한 capacity가 있습니다. **Web ACL은 rule group 안의 rule이 실제로 쓰는 WCU가 아니라 이 capacity 값을 그대로 셉니다.** 그래서 관리형 룰 그룹에서 일부 rule을 `Count`로 override해도 WCU는 줄지 않습니다. 실측에서도 CRS는 override 전후 모두 700이었습니다. 반대로 관리형 룰 그룹에 scope-down statement를 붙이면 그 statement 비용이 더해집니다. CRS에 URI path 정규식 scope-down을 붙이자 703이 됐습니다.

### 3.3. 합계는 rule별 값의 단순 합보다 작을 수 있습니다

AWS 문서는 Web ACL이 쓰는 WCU가 rule별 WCU의 합과 같거나 그보다 작다고 설명합니다. 여러 rule이 같은 request component에 같은 변환을 걸면 AWS WAF가 변환 비용을 한 번만 셀 수 있기 때문입니다. 이 최적화가 실제로 어떻게 적용되는지는 6장에서 쟀습니다. 결론부터 말하면, **WCU를 확인할 때는 rule 하나씩이 아니라 Web ACL에 들어갈 rule 목록 전체로 `CheckCapacity`를 호출해야 합니다.**

```bash
# rule 목록 전체의 WCU (CloudFront용 Web ACL은 --scope CLOUDFRONT --region us-east-1)
aws wafv2 check-capacity \
  --scope REGIONAL --region ap-northeast-2 \
  --rules file://rules.json

# 관리형 룰 그룹의 capacity
aws wafv2 describe-managed-rule-group \
  --scope REGIONAL --region ap-northeast-2 \
  --vendor-name AWS --name AWSManagedRulesCommonRuleSet \
  --query Capacity

# 이미 만든 Web ACL이 쓰는 WCU
aws wafv2 get-web-acl \
  --scope REGIONAL --region ap-northeast-2 \
  --name <web-acl-name> --id <web-acl-id> \
  --query WebACL.Capacity
```

`CheckCapacity`는 rule을 만들지 않고 계산만 하므로 리소스도 비용도 생기지 않습니다.

---

## 4. 같은 판정이면 싼 statement를 고릅니다

같은 판정을 여러 statement로 쓸 수 있는 경우가 많고, 단가표를 보면 그 사이의 WCU 차이가 큽니다. 무엇을 찾느냐에 따라 고를 statement를 정리하면 다음과 같습니다.

{% include diagrams/static/aws/waf-wcu/waf-wcu-statement-choice.html %}
{% include diagrams/download.html png="/assets/img/diagrams/static/aws/waf-wcu/waf-wcu-statement-choice--a4d3b83ef8d0d9c2.png" %}

- 값 전체, 앞부분, 뒷부분이 정해져 있으면 정규식(3)보다 `EXACTLY`, `STARTS_WITH`, `ENDS_WITH`(2)가 싸다.
- 부분 문자열 하나는 `CONTAINS`(10)보다 앵커 없는 정규식(3)이 싸다.
- 단어 단위 일치는 `CONTAINS_WORD`(10) 대신 단어 경계를 문자 클래스로 쓴 정규식(3)으로 바꿀 수 있다.
- 패턴이 여러 개면 statement를 여러 개 두지 않고 `|`로 이은 정규식 하나(3)에 담는다.

AWS 문서는 `CONTAINS_WORD`가 매칭되는 경우를 네 가지로 정의합니다. 값 전체가 단어와 같거나, 단어 앞뒤가 값의 처음과 끝이거나 영숫자와 `_`가 아닌 문자여야 합니다. 이 정의를 정규식으로 옮기면 다음과 같습니다.

```text
(^|[^A-Za-z0-9_])curl([^A-Za-z0-9_]|$)
```

괄호는 대안을 묶는 용도로만 씁니다. AWS WAF는 backreference와 캡처한 값을 다시 쓰는 기능을 지원하지 않습니다.

regex pattern set은 25 WCU이고 set 하나에 패턴을 10개까지 넣을 수 있습니다. AWS quotas 문서의 정규식 길이 한도는 200자입니다. `CheckCapacity`는 512자 정규식까지 받아들였지만, 계산 API가 받아들인 길이를 rule 생성에서도 받는다는 보장은 없으므로 200자를 기준으로 둡니다. 패턴이 200자 안에 들어가면 regex match 하나(3)가 훨씬 쌉니다. 200자를 넘어 정규식 두 개로 나눠도 6입니다. 정규식 8개(1,600자, 24 WCU)까지는 regex match가 싸고, 9개(27 WCU)부터는 패턴을 최대 2,000자(200자 x 10개)까지 담는 regex pattern set(25)이 쌉니다. WCU와 별개로, 같은 목록을 여러 rule과 Web ACL에서 함께 쓰고 목록만 따로 갱신해야 하면 regex pattern set이 관리하기 쉽습니다. 이때도 참조할 때마다 25가 듭니다.

---

## 5. CONTAINS 7개를 정규식 1개로 바꾸면 80 WCU가 13 WCU가 됩니다

예를 들어 스크립트와 HTTP 라이브러리의 기본 UA 토큰 7개를 차단하는 rule을 생각해 봅니다. 대소문자만 바꾼 UA도 잡으려고 `LOWERCASE` 변환을 걸고, 토큰마다 `CONTAINS` statement를 하나씩 둔 모양입니다.

```text
OR
  User-Agent (LOWERCASE)  CONTAINS "python-requests/"     10
  User-Agent (LOWERCASE)  CONTAINS "aiohttp/"             10
  ... go-http-client/, curl/, wget/, scrapy/, libwww-perl/ 50
  LOWERCASE 변환 (7개 statement가 같은 변환)               10
                                       CheckCapacity      80
```

변환을 statement마다 세면 7 x 20 = 140이어야 하지만 `CheckCapacity`는 80을 돌려줬습니다. 7개 statement의 `LOWERCASE`가 10 WCU 하나로 잡혔습니다. 같은 판정을 정규식 하나로 바꾸면 다음과 같습니다.

```text
User-Agent (LOWERCASE)  REGEX
  python-requests/|aiohttp/|go-http-client/|curl/|wget/|scrapy/|libwww-perl/
                                                           3
LOWERCASE 변환                                            10
                                       CheckCapacity      13
```

{% include diagrams/static/aws/waf-wcu/waf-wcu-regex-merge.html %}
{% include diagrams/download.html png="/assets/img/diagrams/static/aws/waf-wcu/waf-wcu-regex-merge--0f315a2d4120fdeb.png" %}

토큰이 7개에서 20개로 늘어도 정규식 하나의 비용은 3 그대로입니다. 늘어나는 것은 길이뿐이고, 200자 한도만 지키면 됩니다. 위 정규식은 74자입니다.

### 5.1. 판정이 같다는 근거

이미 차단에 쓰고 있는 rule을 바꿀 때는 판정이 하나도 달라지면 안 됩니다. 두 조건이 같은 이유는 세 가지입니다.

- `CONTAINS`는 부분 문자열 검색이다. `^`, `$` 앵커가 없는 정규식도 부분 문자열 검색이다.
- 점(`.`) 같은 정규식 특수문자는 `\.`로 이스케이프해 글자 그대로 비교한다.
- `LOWERCASE` 변환은 그대로 둔다. 빼면 WCU는 더 줄지만 `Curl/`과 `curl/`을 다르게 본다.

부분 문자열 검색이라는 성질은 과하게 잡는 경우까지 똑같이 보존됩니다. `curl/`은 `libcurl/`에도 매칭되는데, 원래의 `CONTAINS`도 같은 요청을 잡았습니다. 토큰을 넣거나 대소문자를 섞은 무작위 문자열 20만 개로 두 조건을 비교했고, 판정이 다른 경우는 0건이었습니다. 검증은 Python `re`로 했습니다. 리터럴과 `|`만 쓰는 정규식은 PCRE와 Python `re`에서 같은 의미입니다.

### 5.2. Terraform에서 토큰 목록을 정규식으로 렌더링하기

사람이 정규식을 직접 관리하면 이스케이프를 빠뜨리기 쉽습니다. 입력은 기존처럼 토큰 목록으로 두고, 모듈이 정규식을 만들게 합니다.

```hcl
variable "ua_tokens" {
  type = list(string)

  validation {
    condition     = length(var.ua_tokens) > 0 && alltrue([for s in var.ua_tokens : length(s) > 0 && s == lower(s)])
    error_message = "빈 토큰은 모든 요청에 매칭되고, 대문자가 섞인 토큰은 LOWERCASE 뒤의 값에 영원히 매칭되지 않는다."
  }
}

locals {
  # CONTAINS 의미를 유지하려고 앵커 없이 잇고, 정규식 특수문자는 이스케이프한다
  ua_escaped = [for s in var.ua_tokens : replace(s, "/([.^$|?*+()\\[\\]{}\\\\])/", "\\$1")]
  ua_regex   = join("|", local.ua_escaped)
}

resource "aws_wafv2_web_acl" "this" {
  # ...

  lifecycle {
    precondition {
      condition     = length(local.ua_regex) <= 200
      error_message = "정규식 하나는 200자를 넘을 수 없다. 토큰을 두 정규식으로 나눈다."
    }
  }
}
```

**목록에 빈 문자열이 하나 섞이면 합친 정규식은 `curl/|`처럼 빈 대안을 갖고, 빈 대안은 모든 문자열에 매칭되므로 이 rule이 모든 요청을 차단합니다.** validation은 이 사고를 plan 단계에서 막습니다. 같은 validation이 대문자가 섞인 토큰도 막습니다. rule이 `LOWERCASE` 뒤의 값과 비교하므로 `Go-http-client/`처럼 대문자가 섞인 토큰은 오류 없이 아무것도 잡지 못합니다. Terraform 1.13.5에서 위 코드는 7개 토큰으로 74자 정규식을 만들었습니다. `a.b`, `(x)`, `z|w` 같은 특수문자 토큰은 `a\.b`, `\(x\)`, `z\|w`로 바뀌었고, 빈 토큰은 validation에서, 223자가 되는 목록은 precondition에서 plan이 실패했습니다.

---

## 6. 변환 비용은 같은 조합끼리 한 번만 잡힙니다

5장에서 7개 statement의 `LOWERCASE`가 한 번만 잡혔습니다. AWS 문서는 이 최적화를 "할 수 있다"고만 설명하므로, 어떤 조합에서 적용되는지 직접 쟀습니다. 비교한 정규식은 3 WCU이고, `URL_DECODE`와 `LOWERCASE`를 함께 걸면 하나가 23 WCU입니다.

{% include diagrams/static/aws/waf-wcu/waf-wcu-transform-sharing.html %}
{% include diagrams/download.html png="/assets/img/diagrams/static/aws/waf-wcu/waf-wcu-transform-sharing--0c117bdf6cb0a3a1.png" %}

| 조합 | 실측 | 변환을 따로 셀 때 | 공유 |
| :--- | ---: | ---: | :--- |
| 같은 path 정규식과 같은 변환(`URL_DECODE`, `LOWERCASE`)을 rule 3개에 | 29 | 69 | 공유 |
| 같은 User-Agent 변환을 rule 3개의 `CONTAINS`에 | 40 | 60 | 공유 |
| 한쪽만 `LOWERCASE` 하나 (`URL_DECODE`, `LOWERCASE`와 `LOWERCASE`) | 36 | 36 | 따로 |
| 변환 순서만 반대 (`URL_DECODE`, `LOWERCASE`와 `LOWERCASE`, `URL_DECODE`) | 46 | 46 | 따로 |
| header 이름 표기만 다름 (`user-agent`와 `User-Agent`) | 26 | 26 | 따로 |
| component가 다름 (`User-Agent`와 `Referer`) | 26 | 26 | 따로 |

결과에서 규칙이 보입니다. **변환 비용은 같은 request component와 같은 변환 목록, 같은 순서의 조합마다 한 번 잡혔고, 하나라도 다르면 따로 잡혔습니다.** header 이름 비교는 대소문자를 가리지 않는데도, 표기가 다르면 비용 계산에서는 다른 component로 취급됐습니다. 여기서 운영 규칙 세 가지가 나옵니다.

- 변환 순서를 팀 규칙으로 고정한다. 예를 들어 URI path는 항상 `URL_DECODE` 다음 `LOWERCASE`로 둔다.
- header 이름은 모듈에서 소문자 한 가지로만 쓴다.
- 같은 component에 같은 변환이 이미 있으면, 그 변환을 쓰는 statement를 더해도 statement 기본값만 늘어난다.

문서가 보장하는 동작이 아니므로 이 결과는 2026년 10월 21일의 실측으로만 읽어야 합니다. 3장의 결론처럼 최종 확인은 rule 목록 전체로 합니다.

### 6.1. 변환을 아예 빼는 방법

같은 component에 `LOWERCASE`를 쓰는 rule이 이 rule 하나뿐이면, 변환 10 WCU가 이 rule의 몫입니다. 이럴 때는 영문자마다 대문자와 소문자를 문자 클래스로 쓰면 변환 없이 대소문자를 무시할 수 있습니다.

```text
[Cc][Uu][Rr][Ll]/|[Ww][Gg][Ee][Tt]/|...
```

7개 토큰을 이렇게 쓰면 245자라 200자를 넘습니다. 두 정규식(140자, 104자)으로 나누면 3 + 3 = 6 WCU로, `LOWERCASE`를 쓴 13보다 7 적습니다. 무작위 문자열 20만 개에서 `LOWERCASE` 뒤 소문자 정규식과 판정이 다른 경우는 0건이었습니다. 다만 아래 조건을 함께 따져야 합니다.

- 같은 component에 같은 `LOWERCASE`를 쓰는 rule이 이미 있으면 변환은 추가 비용이 없다. 이때는 그냥 `LOWERCASE`를 쓴다.
- 비교는 ASCII 영문자 기준이다. 비 ASCII 문자에 대한 `LOWERCASE`의 동작은 문서에 없다.
- 정규식을 사람이 읽기 어려워진다. Terraform이 만들게 한다.

```hcl
locals {
  # LOWERCASE 변환 없이 대소문자를 무시하려면 영문자마다 [Xx] 문자 클래스로 바꾼다
  ua_folded = [
    for s in local.ua_escaped : join("", [
      for c in split("", s) : upper(c) != lower(c) ? "[${upper(c)}${lower(c)}]" : c
    ])
  ]
}
```

Terraform 1.13.5에서 위 코드를 7개 토큰에 적용하고 결과를 `|`로 이으면, Python으로 만든 것과 같은 245자 정규식이 나왔습니다.

`(?i)` 같은 인라인 플래그도 생각할 수 있습니다. `CheckCapacity`는 `(?i)`가 붙은 정규식을 3 WCU로 받아들였습니다. 그러나 AWS 문서는 지원하는 PCRE 문법의 전체 목록이 없다고 밝히고 있고, AWS re:Post의 채택 답변은 인라인 플래그를 지원하지 않으니 위와 같은 문자 클래스로 쓰라고 안내합니다. 어느 쪽도 실제 요청으로 매칭을 확인한 근거는 아닙니다. API가 받아들인다는 것과 요청에 그렇게 매칭된다는 것은 다른 이야기이므로, 실제 요청으로 확인하기 전에는 `(?i)`를 판정에 쓰지 않습니다.

---

## 7. label로 탐지와 판정을 나눕니다

헤더 조건으로 봇을 탐지하는 rule이 여러 개라고 해 봅니다. 탐지 rule마다 Block을 걸면 검증된 크롤러 같은 예외 조건을 rule마다 반복해야 합니다. 예시의 크롤러 예외는 WCU 계산을 보여 주려고 UA 정규식(3)과 ASN match(1)를 `AND`로 묶은 4 WCU 조건입니다. 실제 크롤러 검증 방법은 11장에서 다룹니다.

```text
4개 rule 각각:
AND
  NOT  Size(<헤더>) >= 0      헤더가 없으면 참                 1
  NOT  AND
         User-Agent REGEX Googlebot/|bingbot/                  3
         ASN match 15169, 8075                                 1
                                       rule당                  5
                                       CheckCapacity (4개)    20
```

탐지와 판정을 나누면 예외는 한 번만 평가합니다. 탐지 rule은 `Count` action에 label만 붙이고, 판정은 마지막 rule 하나가 label을 읽어서 합니다.

{% include diagrams/static/aws/waf-wcu/waf-wcu-label-decision.html %}
{% include diagrams/download.html png="/assets/img/diagrams/static/aws/waf-wcu/waf-wcu-label-decision--bd2227de92c1c55f.png" %}

```text
Count  헤더 조건 4개, 각각 label example:bot:<조건>            4 x 1
Count  크롤러 예외, label example:allow:crawler                    4
Block  namespace "example:bot:" label이 있음
       AND NOT label "example:allow:crawler"                       2
                                       CheckCapacity              11
```

계산하면 4 + 4 + 2 = 10인데 `CheckCapacity`는 11을 돌려줬습니다. rule에 label을 붙이는 구성을 넣으면 1 WCU가 더 잡혔고, label을 붙이는 rule 수를 늘려도 이 1은 늘지 않았습니다. 문서에 없는 동작이라 전체 목록으로 재야 하는 이유가 하나 더 생깁니다. 그래도 20이 11로 줄었고, 탐지 조건이 늘수록 차이는 커집니다. 탐지 rule 하나를 더하면 나누기 전에는 5, 나눈 뒤에는 1이 늘어납니다.

label match는 1 WCU이고, scope를 `NAMESPACE`로 두면 `example:bot:` 아래 label 전체를 statement 하나로 읽습니다. 운영에서 얻는 이점은 WCU보다 큽니다.

- label마다 CloudWatch 지표가 나와 탐지 조건별 매칭 수를 따로 볼 수 있다.
- Block 전환이 rule 하나의 action 변경이다. 되돌리기도 같은 한 번의 변경이다.
- 예외 조건을 고칠 때 한 rule만 고친다.

label을 쓸 때 지켜야 할 순서가 있습니다. **label match statement는 같은 Web ACL에서 먼저 평가된 rule이 붙인 label만 볼 수 있으므로, label을 붙이는 rule은 읽는 rule보다 priority 숫자가 작아야 합니다.** AWS WAF는 rule의 평가가 끝날 때 label을 붙이므로, 같은 rule 안에서는 자기가 붙인 label을 읽을 수 없습니다. 또 탐지 rule을 IP set, 관리형 룰 그룹 같은 종결 rule 뒤에 두면 이미 차단된 요청은 세지 않습니다. 그러면 남은 매칭은 앞의 종결 rule을 모두 통과한 요청이므로 그대로 오탐 검토 대상이 됩니다. 탐지 rule을 앞에 두면 뒤에서 어차피 차단될 요청이 매칭 수에 섞입니다.

---

## 8. rate-based rule은 집계 키가 비쌉니다

rate-based rule은 기본값 2에 custom aggregation key마다 30이 붙습니다. scope-down statement를 쓰면 그 비용도 더해집니다.

| 구성 | 실측 WCU |
| :--- | ---: |
| IP 기준 집계 | 2 |
| custom key 2개 (IP, `User-Agent` header) | 62 |
| IP 기준 + scope-down path 정규식 (`URL_DECODE`, `LOWERCASE`) | 25 |
| IP 기준 + scope-down label match | 3 |

custom key는 꼭 필요할 때만 씁니다. 키를 하나 더할 때마다 30이 들고, 집계 단위도 잘게 나뉘어 판정이 바뀝니다. IP와 UA로 나눠 세면 같은 IP에서 UA를 돌려 쓰는 요청은 UA마다 따로 세어져 한도에 늦게 닿습니다. 회선을 여러 사용자가 공유해서 IP 하나로 묶으면 오탐이 나는 경우처럼, 판정 단위를 바꿔야 할 이유가 있을 때 키를 더합니다.

scope-down에 쓸 조건이 다른 rule에도 있으면 label로 읽는 방법도 있습니다. 다만 6장의 결과대로 같은 path 정규식과 같은 변환을 다른 rule이 이미 쓰고 있다면, scope-down에 정규식을 그대로 둬도 추가 비용은 정규식 기본값 3뿐입니다. 이때 label로 바꿔서 줄어드는 것은 2입니다. rate-based rule은 Web ACL 하나에 10개까지 둘 수 있다는 한도도 함께 봅니다.

---

## 9. 직접 만든 rule group은 capacity를 크게 잡으면 손해입니다

3.2에서 본 것처럼 Web ACL은 rule group의 capacity 값을 그대로 셉니다. 나중에 rule을 더할 생각으로 capacity를 넉넉하게 잡으면, 쓰지 않는 WCU까지 Web ACL 예산에서 빠집니다.

{% include diagrams/static/aws/waf-wcu/waf-wcu-rule-group-capacity.html %}
{% include diagrams/download.html png="/assets/img/diagrams/static/aws/waf-wcu/waf-wcu-rule-group-capacity--23b5ac229ddd7437.png" %}

예를 들어 실제 rule이 60 WCU인 rule group을 capacity 300으로 만들었다고 해 봅니다. 관리형 룰 그룹 6개와 함께 쓰면 Web ACL은 1,375 + 300 = 1,675 WCU가 되어 두 번째 구간에 들어갑니다. 같은 rule group을 capacity 80으로 다시 만들면 1,455로 1,500 아래에 남습니다. **capacity는 rule group을 만든 뒤 바꿀 수 없으므로, 줄이려면 새 rule group을 만들고 Web ACL의 참조를 옮겨야 합니다.** Terraform AWS provider에서도 `aws_wafv2_rule_group`의 `capacity`는 바꾸면 리소스를 새로 만드는 인자입니다.

```hcl
resource "aws_wafv2_rule_group" "shared" {
  # capacity를 바꾸면 새 rule group이 만들어진다.
  # 이름이 겹치지 않게 name_prefix를 쓰고, 새 그룹을 먼저 만든 뒤 Web ACL 참조를 옮긴다.
  name_prefix = "shared-bot-rules-"
  scope       = "REGIONAL"
  capacity    = 80 # CheckCapacity로 잰 60에 여유분을 더한 값

  # rule, visibility_config ...

  lifecycle {
    create_before_destroy = true
  }
}
```

capacity는 `CheckCapacity`로 rule group 안의 rule 목록을 잰 값에 앞으로 더할 rule만큼의 여유를 더해서 정합니다. rule group을 여러 Web ACL에서 함께 쓸 일이 없다면, rule을 Web ACL에 직접 두는 편이 낫습니다. Web ACL에 직접 둔 rule은 계산된 WCU만큼만 쓰고 6장의 변환 공유도 받습니다.

Terraform은 적용된 Web ACL의 WCU를 `capacity` 속성으로 읽을 수 있습니다. `check` 블록으로 apply 뒤 1,500을 넘었는지 경고를 띄울 수 있습니다.

```hcl
check "wcu_budget" {
  assert {
    condition     = aws_wafv2_web_acl.this.capacity <= 1500
    error_message = "Web ACL이 1,500 WCU를 넘어 요청 단가가 올라간다."
  }
}
```

위 두 코드는 Terraform 1.13.5와 AWS provider 6.69.1에서 `terraform validate`를 통과했습니다. `check` 블록은 plan과 apply를 막지 않고 경고만 남깁니다. 1,500을 넘는 변경을 막으려면 apply 전에 rule 목록으로 `CheckCapacity`를 호출하는 단계가 필요합니다.

---

## 10. 예시 Web ACL에 적용한 결과

관리형 룰 그룹 6개에 custom rule을 더한 예시 Web ACL에 5장과 7장의 변경을 적용하고, 전후를 `CheckCapacity`로 쟀습니다.

| rule | 바꾸기 전 | 바꾼 뒤 | 바꾼 방법 |
| :--- | ---: | ---: | :--- |
| UA 도구 토큰 차단 | 80 | 13 | `CONTAINS` 7개를 정규식 1개로 |
| 인증 경로 rate-based (scope-down path 정규식) | 25 | 25 | 그대로 둔다 |
| 인증 경로 POST Challenge (path 정규식 + method) | 25 | 25 | 그대로 둔다 |
| 헤더 조건 탐지 4개 + 크롤러 예외 | 20 | 11 | label로 탐지와 판정을 나눈다 |
| rule별 값의 합 | 150 | 74 | - |
| custom rule 목록 전체 (실측) | 130 | 54~55 | - |
| 관리형 룰 그룹 6개 포함 Web ACL (실측) | 1,505 | 1,429~1,430 | - |

rule별 값의 합보다 전체 실측이 작은 것은 두 인증 경로 rule이 같은 path 정규식과 같은 변환을 써서 변환 비용 20이 한 번만 잡혔기 때문입니다.

바꾼 뒤의 값이 범위로 적힌 데는 이유가 있습니다. **같은 rule 목록으로 `CheckCapacity`를 여러 번 호출하자 결과가 1 WCU씩 달라졌습니다.** 바꾼 뒤의 custom rule 목록은 호출에 따라 54 또는 55였고, 관리형 룰 그룹을 포함한 Web ACL은 1,429 또는 1,430이었습니다. 바꾸기 전 목록은 매번 130과 1,505로 같았습니다. 같은 목록을 4~6번씩 호출한 결과입니다. 변동은 label을 붙이는 rule이 다른 rule과 함께 있는 목록에서만 보였고, label 구성만 있는 목록(11)이나 인증 경로 rule 두 개만 있는 목록(30)은 매번 같았습니다. 원인은 AWS 문서에 없고 확인하지 못했습니다. 그래서 1,500 경계에 바짝 붙는 구성은 피하고 여유를 둡니다.

바꾸기 전 Web ACL은 1,500을 5 WCU 넘어 요청 단가가 100만 건당 $0.80이었습니다. 월 3억 건이면 요청 요금은 $240입니다. 바꾼 뒤에는 1,430으로 $0.60 구간에 돌아와 $180이 됩니다. **5 WCU를 넘긴 대가가 월 $60이었고, 판정을 바꾸지 않고 그 비용을 되찾았습니다.** UA 정규식은 무작위 문자열 비교로, label 분리는 "헤더 조건 중 하나가 참이고 예외가 아니면 차단"이라는 같은 논리식으로 판정이 같습니다. 다만 차단하는 rule 이름이 `block-no-*` 4개에서 판정 rule 1개로 바뀌므로, 로그의 `terminatingRuleId`, 대시보드와 알림은 함께 고쳐야 합니다. 6.1의 문자 클래스 방식까지 적용하면 1,422~1,423이 됩니다.

---

## 11. 줄이면 안 되는 것

WCU를 줄이는 방법 중에는 판정을 바꾸는 것도 있습니다. 아래는 WCU가 줄어도 판정이나 운영이 나빠지는 변경입니다.

- text transformation 제거: `LOWERCASE`를 빼면 10이 줄지만 대소문자를 바꾼 요청을 놓친다. 같은 판정을 지키려면 6.1처럼 문자 클래스로 옮긴다.
- 조건을 짧게 쓰려고 `NOT`으로 뒤집기: 대상 component가 없는 요청까지 매칭된다. 7장의 "헤더 없음" 조건처럼 그 동작이 의도일 때만 쓴다.
- CloudFront Functions로 옮기기: WCU는 0이지만 WAF 로그, label, WAF 지표에 남지 않아 관찰과 롤백이 어려워진다.
- 관리형 룰 그룹 빼기: 700 WCU인 CRS를 빼면 예산은 크게 남지만, 그 그룹이 막던 요청이 그대로 들어온다. 빼기 전에 그룹이 실제로 차단하는 요청이 있는지 지표로 확인한다.
- 예외 문자열만 믿기: 크롤러 UA는 위조할 수 있고, 검색엔진 회사의 ASN에서도 크롤러가 아닌 트래픽이 나온다. 검색엔진이 공개한 크롤러 IP 범위로 만든 IP set이나 Bot Control의 검증된 봇 label을 우선한다.
- capacity를 빠듯하게 잡기: rule group에 여유가 없으면 rule 하나를 더할 때마다 rule group을 다시 만들어야 한다.

---

## 12. rule을 바꿀 때 지킬 순서

1. 바꾸기 전과 바꾼 뒤의 rule 목록 전체로 `CheckCapacity`를 호출해 WCU를 확인한다. 결과가 호출마다 1 WCU씩 다를 수 있으므로 1,500에 바짝 붙이지 않는다.
2. 실제 차단 중인 rule을 바꾸면 WAF 로그에 새 조건과 기존 조건을 함께 적용해 판정 차이가 0건인지 본다.
3. 새 탐지 rule은 `Count` + label로 넣고 label 지표와 통과한 요청을 며칠 관찰한다.
4. 오탐을 예외로 정리한 뒤 마지막 판정 rule 하나만 `Block`으로 바꾼다.
5. 적용 직후 차단 rule의 `BlockedRequests`가 바꾸기 전 같은 시간대와 비슷한지 확인한다. 여러 rule을 하나로 합쳤다면 기존 rule들의 합과 비교한다.
6. 문제가 생기면 이전 커밋으로 되돌려 다시 apply한다. Web ACL 업데이트는 rule 전체를 한 번에 교체하므로 롤백도 한 번이다. 9장처럼 rule group을 새로 만든 변경은 rule group과 Web ACL 참조를 함께 되돌린다.

---

## 13. 마치며

WCU는 rule을 쓰는 방식만 바꿔도 줄일 수 있는 비용입니다. 요청 수는 봇이 정하지만, 같은 판정을 몇 WCU로 표현할지는 rule을 쓰는 사람이 정합니다. 단가표에서 비싼 statement를 싼 statement로 바꾸고, 변환은 같은 조합끼리 모으고, 반복되는 예외는 label로 한 번만 평가하고, rule group capacity는 필요한 만큼만 잡으면 됩니다. 어느 방법이든 마지막 확인은 rule 목록 전체로 호출한 `CheckCapacity`와 WAF 로그 재생입니다.

---

## 14. Reference

- [AWS Docs - Web ACL capacity units (WCUs) in AWS WAF](https://docs.aws.amazon.com/waf/latest/developerguide/aws-waf-capacity-units.html)
- [AWS - AWS WAF Pricing](https://aws.amazon.com/waf/pricing/)
- [AWS Docs - AWS WAF quotas](https://docs.aws.amazon.com/waf/latest/developerguide/limits.html)
- [AWS Docs - String match rule statement](https://docs.aws.amazon.com/waf/latest/developerguide/waf-rule-statement-type-string-match.html)
- [AWS Docs - Regex match rule statement](https://docs.aws.amazon.com/waf/latest/developerguide/waf-rule-statement-type-regex-match.html)
- [AWS Docs - Regex pattern set match rule statement](https://docs.aws.amazon.com/waf/latest/developerguide/waf-rule-statement-type-regex-pattern-set-match.html)
- [AWS Docs - Supported regular expression syntax in AWS WAF](https://docs.aws.amazon.com/waf/latest/developerguide/waf-regex-pattern-support.html)
- [AWS Docs - Request components in AWS WAF](https://docs.aws.amazon.com/waf/latest/developerguide/waf-rule-statement-fields-list.html)
- [AWS Docs - Label match rule statement](https://docs.aws.amazon.com/waf/latest/developerguide/waf-rule-statement-type-label-match.html)
- [AWS Docs - Geographic match rule statement](https://docs.aws.amazon.com/waf/latest/developerguide/waf-rule-statement-type-geo-match.html)
- [AWS Docs - IP set match rule statement](https://docs.aws.amazon.com/waf/latest/developerguide/waf-rule-statement-type-ipset-match.html)
- [AWS Docs - Using rate-based rule statements in AWS WAF](https://docs.aws.amazon.com/waf/latest/developerguide/waf-rule-statement-type-rate-based.html)
- [AWS Docs - Using managed rule group statements in AWS WAF](https://docs.aws.amazon.com/waf/latest/developerguide/waf-rule-statement-type-managed-rule-group.html)
- [AWS Docs - Baseline rule groups](https://docs.aws.amazon.com/waf/latest/developerguide/aws-managed-rule-groups-baseline.html)
- [AWS API Reference - CheckCapacity](https://docs.aws.amazon.com/waf/latest/APIReference/API_CheckCapacity.html)
- [AWS re:Post - aws waf rule match regular expression](https://repost.aws/questions/QUglpzFvZJSSm1r-65Ag-LEQ/aws-waf-rule-match-regular-expression)
- [Terraform Registry - aws_wafv2_rule_group](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/wafv2_rule_group)
- [Terraform Registry - aws_wafv2_web_acl](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/wafv2_web_acl)
- [Terraform Docs - Checks](https://developer.hashicorp.com/terraform/language/checks)

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
