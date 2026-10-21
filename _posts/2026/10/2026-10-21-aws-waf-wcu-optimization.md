---
title: "AWS WAF WCU 아끼기 - 1,500 WCU 안에서 UA 위장 봇을 막는 룰 설계"
date: 2026-10-21 22:00:00 +0900
author: kkamji
categories: [Cloud, AWS]
tags: [aws, waf, wcu, bot, regex, label, client-hints, terraform, security]
comments: true
image:
  path: /assets/img/aws/aws.webp
---

봇 트래픽은 사람의 트래픽과 모양이 다릅니다. 사람의 요청은 하루 주기를 따라 완만하게 오르내립니다. 제가 최근 대응한 봇은 몇 시간 간격으로 분당 요청을 평소의 수십 배까지 올렸다가 몇 분 뒤 내려놓았습니다. 그 사이 오리진은 5XX를 냈고 p90 응답 시간은 수 초까지 늘었습니다. IP는 주거용 프록시를 통해 수십만 개로 흩어져 있어서 IP당 rate limit에 걸리지 않았습니다. 실제 Chromium 엔진을 띄우는 자동화라서 JavaScript Challenge도 대부분 풀었습니다.

남은 단서는 헤더 사이의 모순이었습니다. UA 문자열만 바꾼 자동화는 `User-Agent`와 `Sec-CH-UA`가 서로 다른 버전을 말합니다. 이 모순을 검사하는 custom rule을 하나씩 더하면 다른 문제가 생깁니다. **AWS WAF는 Web ACL이 1,500 WCU를 넘으면 그 Web ACL을 지나는 모든 요청의 단가를 올립니다.** 같은 판정을 더 적은 WCU로 표현하려고 제가 바꾼 룰과 그 근거를 정리합니다. 룰과 수치는 일반화했고, 특정 서비스의 트래픽 값은 싣지 않았습니다.

> **TL;DR**  
>
> - WCU는 rule 평가 비용의 단위다. Web ACL 기본 요금에 1,500 WCU가 포함되고, 넘으면 500 WCU마다 요청 100만 건당 $0.20이 모든 요청에 붙는다.  
> - AWS 관리형 룰 그룹 6개(CRS, Known bad inputs, SQLi, Linux, Amazon IP reputation, Anonymous IP)만 넣어도 1,375 WCU다. custom rule에 남는 예산은 125 WCU다.  
> - 단가표에서 비싼 것은 `CONTAINS` 문자열 검색(10 WCU)과 text transformation(10 WCU)이다. 정규식은 3 WCU, label match는 1 WCU다. `CONTAINS` 7개를 정규식 1개로 합치면 82 WCU 룰이 15 WCU가 된다.  
> - WAF 정규식은 두 헤더의 값을 서로 비교하지 못한다. 버전마다 룰을 나열하는 대신 버전 뒤 두 자리를 7비트로 보고 비트마다 정규식 쌍을 두면, 187 WCU 룰이 97 WCU로 줄고 Chrome 100~199 전체를 덮는다.  
{: .prompt-info}

---

## 1. 봇 트래픽이 서버에 주는 부담은 요청 수보다 큽니다

봇이 문제인 이유는 요청이 많아서만이 아닙니다. 제가 본 봇은 상품 상세 페이지 문서를 요청한 뒤 장바구니, 회원가입, 로그인 화면으로 내부 이동 요청을 반복했습니다. 문서 요청 하나는 서버 렌더링과 여러 개의 React Server Components(RSC) 요청, 정적 자원 요청을 함께 끌고 옵니다. 봇이 여는 상품 상세 페이지는 사람이 자주 보지 않는 페이지가 많아서 CDN 캐시에도 잘 걸리지 않습니다. 그래서 같은 요청 수라도 오리진이 치르는 비용은 사람 트래픽보다 큽니다.

처음에는 이미 알고 있는 수단부터 꺼냈습니다. 결과는 아래와 같았습니다.

| 관측한 봇의 특징 | 먼저 검토한 대응 | 통하지 않은 이유 |
| :--- | :--- | :--- |
| IP 수십만 개, IP 하나당 몇 시간에 수 건에서 수십 건 | IP 기준 rate-based rule | IP당 한도에 닿지 않는다 |
| 상위 국가와 ASN이 각국의 가정용, 모바일 회선 | 국가, ASN 차단 | 실사용자 피해가 크고 봇은 일부만 줄어든다 |
| 평판 목록에 없는 주거용 IP | IP reputation 관리형 룰 그룹 | 거의 잡히지 않는다 |
| 실제 Chromium 엔진으로 동작 | JavaScript Challenge | challenge를 대부분 푼다 |

IP와 ASN 기반 수단은 [AWS WAF Self-Managed Rule 글](/posts/aws-waf-self-managed-rule/)에서, Challenge의 동작은 [AWS WAF Challenge Action 글](/posts/aws-waf-javascript-challenge/)에서 다뤘습니다. 이번 봇에는 둘 다 맞지 않았습니다.

봇이 바꾸지 못한 것은 브라우저 엔진이 자동으로 채우는 값이었습니다. `Sec-CH-UA`는 스크립트가 쓰는 값이 아니라 Chromium이 요청마다 실제 브랜드와 major 버전으로 붙이는 헤더입니다. UA 문자열만 바꾼 자동화는 다음 두 헤더를 함께 보냅니다.

```http
User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36
Sec-CH-UA: "Chromium";v="146", "Not?A_Brand";v="24"
```

이런 모순을 찾는 룰은 정확도가 높습니다. 다만 검사할 모순이 늘수록 룰이 늘고, 룰이 늘수록 WCU가 쌓입니다.

---

## 2. 1,500 WCU를 넘으면 모든 요청의 단가가 오릅니다

**WCU(Web ACL Capacity Unit)** 는 AWS WAF가 rule, rule group, Web ACL을 평가하는 데 드는 계산 비용을 나타내는 단위입니다. 초당 처리량이 아니고, WCU가 많다고 검사가 느려지지도 않습니다. 대신 가격과 한도에 직접 연결됩니다.

- Web ACL 기본 요금에는 1,500 WCU까지 포함된다.
- 1,500을 넘으면 500 WCU 구간마다 요청 100만 건당 $0.20이 더해진다.
- Web ACL 하나의 최대 용량은 5,000 WCU다.

{% include diagrams/static/aws/waf-wcu/waf-wcu-billing-tiers.html %}
{% include diagrams/download.html png="/assets/img/diagrams/static/aws/waf-wcu/waf-wcu-billing-tiers--8ba0797692af5346.png" %}

**가산 요금은 새 룰에 매칭된 요청이 아니라 Web ACL이 검사하는 전체 요청에 붙습니다.** 기본 요청 단가가 100만 건당 $0.60이므로, 1,500을 1 WCU만 넘어도 요청 요금이 3분의 1만큼 늘어납니다. 월 3억 건을 검사하는 Web ACL로 계산하면 다음과 같습니다.

| Web ACL 용량 | 요청 단가 (100만 건당) | 월 3억 건 요청 요금 | 1,500 이하 대비 |
| :--- | ---: | ---: | ---: |
| 1,500 WCU 이하 | $0.60 | $180 | - |
| 1,501~2,000 WCU | $0.80 | $240 | +$60 |
| 2,001~2,500 WCU | $1.00 | $300 | +$120 |

Web ACL 월 $5와 rule당 월 $1는 별도입니다. 단가는 2026년 10월의 AWS WAF Pricing 페이지 기준입니다.

1,500은 생각보다 빨리 찹니다. 흔히 함께 쓰는 AWS 관리형 룰 그룹 몇 개가 이미 대부분을 씁니다.

| 관리형 룰 그룹 | WCU |
| :--- | ---: |
| `AWSManagedRulesCommonRuleSet` (CRS) | 700 |
| `AWSManagedRulesKnownBadInputsRuleSet` | 200 |
| `AWSManagedRulesSQLiRuleSet` | 200 |
| `AWSManagedRulesLinuxRuleSet` | 200 |
| `AWSManagedRulesAmazonIpReputationList` | 25 |
| `AWSManagedRulesAnonymousIpList` | 50 |
| 합계 | 1,375 |

이 구성이면 custom rule에 쓸 수 있는 예산은 125 WCU입니다. 관리형 룰 그룹의 WCU는 버전에 따라 바뀔 수 있으므로 실제 값은 `DescribeManagedRuleGroup` 결과로 확인합니다.

---

## 3. WCU 단가표에서 비싼 것은 문자열 검색과 텍스트 변환입니다

룰의 WCU는 statement 종류별 기본값에 옵션 비용을 더해 정해집니다. AWS 문서의 값을 statement별로 모으면 다음과 같습니다.

| Statement | 기본 WCU | 추가 비용 |
| :--- | ---: | :--- |
| Label match | 1 | - |
| ASN match | 1 | - |
| IP set match | 1 | forwarded IP의 position이 `ANY`면 +4 |
| String match `EXACTLY`, `STARTS_WITH`, `ENDS_WITH` | 2 | text transformation마다 +10 |
| String match `CONTAINS`, `CONTAINS_WORD` | 10 | text transformation마다 +10 |
| Regex match | 3 | text transformation마다 +10 |
| Regex pattern set match | 25 | text transformation마다 +10 |
| Rate-based | 2 | custom aggregation key마다 +30, scope-down statement 비용 |
| AND, OR, NOT | - | 안에 넣은 statement의 WCU를 따른다 |

이 표에서 제가 룰을 고칠 때 쓴 기준은 네 가지입니다.

- 부분 문자열 검색은 `CONTAINS`(10)보다 앵커 없는 정규식(3)이 싸다.
- 여러 패턴은 regex pattern set(25)보다 `|`로 이은 regex match 하나(3)가 싸다. 정규식 하나의 길이는 200자까지다.
- text transformation은 하나에 10이라 statement 기본값보다 비쌀 때가 많다. 꼭 필요한 곳에만 둔다.
- 앞에서 내린 판정을 뒤에서 다시 쓸 때는 조건을 반복하지 않고 label match(1)로 읽는다.

AWS 문서는 같은 request component에 같은 transformation을 거는 rule이 여럿이면 transformation 비용을 한 번만 셀 수 있다고 설명합니다. 다만 "할 수 있다"이지 보장은 아닙니다. 그래서 계산값을 믿지 않고 `CheckCapacity` API로 rule 목록의 실제 WCU를 확인했습니다.

```bash
aws wafv2 check-capacity \
  --scope CLOUDFRONT --region us-east-1 \
  --rules file://rules.json
```

---

## 4. CONTAINS 7개를 정규식 1개로 바꾸면 82 WCU가 15 WCU가 됩니다

공격 초기에 급하게 넣은 차단 룰이 있었습니다. 봇이 쓰는 TLS 지문(JA4)이 일치하고, UA에 구버전 Chrome, Edge, Firefox 토큰 7개 중 하나가 들어 있으면 차단하는 룰입니다. JA4 자체는 [JA4 TLS Fingerprinting 글](/posts/ja4-tls-fingerprinting-bot-mitigation/)에서 다뤘습니다. 처음 모양은 다음과 같았습니다.

```text
AND
  JA4 fingerprint  EXACTLY  "<봇 JA4>"                      2
  OR
    User-Agent (LOWERCASE)  CONTAINS "chrome/118."         10
    User-Agent (LOWERCASE)  CONTAINS "chrome/119."         10
    ... 같은 모양 5개 더 ...                                50
  LOWERCASE 변환 (7개 statement가 같은 변환, 1회로 계산)    10
                                                   합계    82
```

7개 statement가 모두 `User-Agent`에 `LOWERCASE`를 걸었는데, `CheckCapacity`는 변환 비용을 한 번만 세어 82를 돌려줬습니다. 문서의 최적화 설명과 맞는 값입니다. 같은 판정을 정규식 하나로 바꾸면 다음과 같습니다.

```text
AND
  JA4 fingerprint  EXACTLY  "<봇 JA4>"                      2
  User-Agent (LOWERCASE)  REGEX
    chrome/118\.|chrome/119\.|chrome/120\.|edg/119\.|edg/120\.|firefox/120\.|firefox/121\.
                                                            3
  LOWERCASE 변환                                           10
                                                   합계    15
```

{% include diagrams/static/aws/waf-wcu/waf-wcu-contains-to-regex.html %}
{% include diagrams/download.html png="/assets/img/diagrams/static/aws/waf-wcu/waf-wcu-contains-to-regex--01c9c543597e4c20.png" %}

패턴이 7개에서 20개로 늘어도 정규식 하나의 비용은 3 그대로입니다. 늘어나는 것은 길이뿐이고, 200자 안에서만 지키면 됩니다.

### 4.1. 판정이 같다는 근거

이 룰은 이미 실제로 차단하고 있던 룰이라 판정이 하나라도 달라지면 안 됐습니다. 두 조건이 같은 이유는 세 가지입니다.

- `CONTAINS`는 부분 문자열 검색이다. `^`, `$` 앵커가 없는 정규식도 부분 문자열 검색이다.
- 점(`.`) 같은 정규식 특수문자는 `\.`로 이스케이프해 글자 그대로 비교한다.
- 소문자 변환은 그대로 둔다. 변환을 빼면 WCU는 더 줄지만 `Chrome/118.`과 `chrome/118.`을 다르게 본다.

이론만으로 넘어가지 않았습니다. 바꾸기 전에 며칠치 WAF 로그에서 해당 JA4 요청 전체에 두 조건을 각각 적용했고, 한쪽만 매칭된 요청은 0건이었습니다. 적용 직후에는 CloudWatch `BlockedRequests`에서 이 룰의 차단량이 바꾸기 전 같은 시간대와 비슷한지 확인했습니다. 무작위 문자열 20만 개로 돌린 비교에서도 차이는 0건이었습니다.

### 4.2. Terraform에서 목록을 정규식으로 렌더링하기

사람이 정규식을 직접 관리하면 이스케이프를 빠뜨리기 쉽습니다. 저는 입력은 기존처럼 문자열 목록으로 두고, 모듈이 정규식을 만들게 했습니다.

```hcl
variable "ua_contains" {
  type = list(string)

  validation {
    condition     = length(var.ua_contains) > 0 && alltrue([for s in var.ua_contains : length(s) > 0])
    error_message = "빈 패턴은 합친 정규식을 모든 요청에 매칭시킨다."
  }
}

locals {
  # CONTAINS 의미를 유지하려고 앵커 없이 잇고, 정규식 특수문자는 이스케이프한다
  ua_regex = join("|", [
    for s in var.ua_contains : replace(s, "/([.^$|?*+()\\[\\]{}\\\\])/", "\\$1")
  ])
}
```

validation은 리뷰에서 나온 지적으로 넣었습니다. 목록에 빈 문자열이 하나 섞이면 합친 정규식은 `chrome/118\.|`처럼 빈 대안을 갖게 되고, **빈 대안은 모든 문자열에 매칭되므로 이 룰이 모든 요청을 차단합니다.** Terraform 1.13.5에서 위 코드는 `chrome/118\.|chrome/119\.|...|firefox/121\.`(86자)를 만들고, 빈 문자열을 넣으면 plan 단계에서 실패합니다.

같은 방법을 UA 블랙리스트 룰(`CONTAINS` 2개 + `LOWERCASE`, 30 WCU)에도 적용해 13 WCU로 줄였습니다.

---

## 5. 탐지와 차단을 나누면 예외 처리도 한 곳에 모입니다

헤더 모순은 한 가지가 아닙니다. UA와 `Sec-CH-UA`의 버전이 다를 수도 있고, UA의 OS와 `Sec-CH-UA-Platform`이 다를 수도 있고, 브랜드에 `HeadlessChrome`이 보일 수도 있습니다. 모순마다 Block 룰을 따로 만들면 검증된 크롤러 예외 같은 조건을 룰마다 반복해야 합니다. 반복한 조건은 그만큼 WCU를 씁니다.

그래서 탐지와 차단을 나눴습니다. 탐지 룰은 모두 `Count` action에 label만 붙입니다. 차단은 마지막에 있는 룰 하나가 label을 읽어서 합니다.

{% include diagrams/static/aws/waf-wcu/waf-wcu-label-funnel.html %}
{% include diagrams/download.html png="/assets/img/diagrams/static/aws/waf-wcu/waf-wcu-label-funnel--b50f0843e45aad18.png" %}

```text
priority 40~52  Block      IP set, UA 블랙리스트, JA4, 관리형 룰 그룹      (요청 종결)
priority 80     Challenge  의심 ASN                                       (토큰 없으면 종결)
priority 91~95  Count      ua-spoof:version, ua-spoof:platform, ...       (label만 붙임)
priority 97     Count      allow:crawler (검증된 크롤러)                  (label만 붙임)
priority 99     Block      namespace "ua-spoof:" label 있음
                           AND NOT label "allow:crawler"                  (1 + 1 WCU)
```

이 구조에서 WCU가 줄어드는 지점은 마지막 룰입니다. label match는 1 WCU이고, scope를 `NAMESPACE`로 두면 `ua-spoof:` 아래 label 전체를 statement 하나로 읽습니다. 크롤러 예외도 이 룰 한 곳에만 둡니다.

운영에서 얻은 이점이 WCU보다 컸습니다.

- label마다 CloudWatch 지표가 나와 탐지 룰별 매칭 수를 따로 볼 수 있다.
- Block 전환이 룰 하나의 action 변경이다. 되돌리기도 같은 한 번의 변경이다.
- 탐지 룰을 Block, Challenge 룰 뒤에 두면 이미 종결된 요청은 세지 않는다. 남은 매칭은 끝까지 통과한 요청이라 오탐 검토 대상이 바로 나온다.

마지막 항목은 제가 순서를 한 번 틀린 뒤 바꾼 것입니다. 처음에는 탐지 룰을 Block 룰보다 앞에 두었습니다. 그러자 매칭 수에 뒤에서 차단될 공격 요청이 모두 섞여서, 오탐을 보려면 로그에서 차단 여부를 다시 걸러야 했습니다. label match statement는 같은 Web ACL에서 먼저 평가된 rule이 붙인 label만 볼 수 있으므로, label을 붙이는 룰은 읽는 룰보다 priority 숫자가 작아야 합니다.

---

## 6. 두 헤더의 버전이 같은지 WAF로 검사하는 방법

### 6.1. WAF 정규식은 두 헤더를 서로 비교하지 못합니다

Chrome은 UA의 major 버전과 `Sec-CH-UA`의 Chromium 버전을 같은 값으로 채웁니다. 두 값이 다르면 UA만 바꾼 클라이언트입니다. 문제는 WAF가 두 헤더의 숫자를 서로 비교하지 못한다는 점입니다. 정규식은 헤더 하나 안에서만 동작하고, 캡처한 값을 다른 헤더에 넘길 수 없습니다. AWS WAF는 backreference도 지원하지 않습니다.

### 6.2. 버전마다 룰을 나열하면 31개 버전에 187 WCU가 듭니다

첫 번째 구현은 버전마다 "`Sec-CH-UA`가 N인데 UA는 N이 아니다"를 한 쌍씩 적었습니다.

```text
OR
  AND  Sec-CH-UA REGEX "Chromium";v="130"   NOT User-Agent REGEX Chrome/130\.
  AND  Sec-CH-UA REGEX "Chromium";v="131"   NOT User-Agent REGEX Chrome/131\.
  ... 160까지 ...
```

한 쌍은 정규식 2개라 3 + 3 = 6 WCU입니다. 130~160의 31개 버전이면 186이고, `CheckCapacity` 실측은 187이었습니다. 이 구조에는 비용 말고도 문제가 두 개 있었습니다.

- 범위 밖 버전은 보지 못한다. Chrome은 약 4주마다 major 버전을 올리므로 사람이 범위를 계속 늘려야 하고, 늘릴 때마다 6 WCU가 붙는다.
- `NOT`은 헤더가 없을 때도 참이다. UA 헤더가 없는 요청도 이 쌍에 걸린다.

{% include diagrams/static/aws/waf-wcu/waf-wcu-version-pairs-vs-bits.html %}
{% include diagrams/download.html png="/assets/img/diagrams/static/aws/waf-wcu/waf-wcu-version-pairs-vs-bits--0537c0ef393e3f03.png" %}

### 6.3. 두 수가 다르면 어딘가 한 비트가 다릅니다

생각을 바꿨습니다. "두 수가 같은가"를 직접 물을 수 없다면, 두 수를 작은 조각으로 나눠 조각마다 물으면 됩니다.

Chrome 100~199는 앞자리 `1`이 같으니 뒤 두 자리 00~99만 비교하면 됩니다. 0~99는 7비트(0~127) 안에 들어가고, 값마다 비트 조합이 하나씩입니다. 그래서 **비트 7개 중 하나라도 두 헤더에서 다르면 버전이 다르고, 모두 같으면 버전이 같습니다.**

비트 하나마다 두 방향의 쌍을 둡니다.

- `Sec-CH-UA` 쪽 비트가 1이고 UA 쪽 비트가 0이다 (1/0)
- `Sec-CH-UA` 쪽 비트가 0이고 UA 쪽 비트가 1이다 (0/1)

비트 7개에 2방향이면 14쌍이고, 14쌍을 OR로 묶으면 100~199의 모든 조합을 판정합니다. UA 118과 `Sec-CH-UA` 146을 대입하면 다음과 같습니다.

{% include diagrams/static/aws/waf-wcu/waf-wcu-bit-compare.html %}
{% include diagrams/download.html png="/assets/img/diagrams/static/aws/waf-wcu/waf-wcu-bit-compare--6ab6f4548606dcdf.png" %}

18은 `0010010`, 46은 `0101110`입니다. b5, b4, b3, b2가 다르므로 그 비트의 쌍 4개가 매칭되고, 하나만 매칭돼도 label이 붙습니다. 정상 Chrome은 두 헤더의 버전이 같아서 14쌍 중 어느 것도 매칭되지 않습니다. 버전이 몇까지 올라가도 쌍의 수는 14개 그대로입니다.

`NOT`도 쓰지 않았습니다. 0인 비트도 "이 비트가 0인 값"을 맞추는 양성 정규식으로 쓰면, 두 헤더에 모두 1xx 버전이 있을 때만 매칭됩니다. 헤더가 없는 요청은 이 룰의 대상이 아니게 됩니다.

### 6.4. 비트 조건을 정규식으로 바꾸기

남은 일은 "b4가 1인 두 자리 값"을 정규식으로 쓰는 것입니다. b4(16)가 1인 값은 16~31, 48~63, 80~95의 48개입니다. 하나씩 나열하면 `16|17|...|95`로 143자입니다. 이것을 십의 자리 기준으로 다시 봅니다.

| 십의 자리 | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 묶은 조각 |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| 0 | . | . | . | . | . | . | . | . | . | . | 없음 |
| 1 | . | . | . | . | . | . | 16 | 17 | 18 | 19 | `[1][6789]` |
| 2 | 20 | 21 | 22 | 23 | 24 | 25 | 26 | 27 | 28 | 29 | `[258][0123456789]` |
| 3 | 30 | 31 | . | . | . | . | . | . | . | . | `[3][01]` |
| 4 | . | . | . | . | . | . | . | . | 48 | 49 | `[4][89]` |
| 5 | 50 | 51 | 52 | 53 | 54 | 55 | 56 | 57 | 58 | 59 | `[258][0123456789]` |
| 6 | 60 | 61 | 62 | 63 | . | . | . | . | . | . | `[6][0123]` |
| 7 | . | . | . | . | . | . | . | . | . | . | 없음 |
| 8 | 80 | 81 | 82 | 83 | 84 | 85 | 86 | 87 | 88 | 89 | `[258][0123456789]` |
| 9 | 90 | 91 | 92 | 93 | 94 | 95 | . | . | . | . | `[9][012345]` |

십의 자리마다 맞는 일의 자리를 모으고, 일의 자리 집합이 같은 십의 자리끼리 문자 클래스로 묶습니다. 2, 5, 8행은 일의 자리가 모두 같으므로 `[258][0123456789]` 하나가 됩니다. 결과는 65자입니다.

```text
[1][6789]|[258][0123456789]|[3][01]|[4][89]|[6][0123]|[9][012345]
```

이 조각을 `"Chromium";v="1(조각)"`과 `Chrome/1(조각)\.`의 괄호 안에 넣어 쌍을 만듭니다. 비트별 조각은 b0이 19자로 가장 짧고 b3이 89자로 가장 깁니다. 앞뒤 고정 문자열을 붙인 완성 정규식은 가장 긴 것이 107자라 200자 한도 안에 들어옵니다. 값을 하나씩 나열하는 방식으로 정규식을 만들면 가장 긴 것이 209자가 되어 한도를 넘습니다. 문자 클래스 압축은 길이 한도 때문에 필요했습니다.

### 6.5. 조각은 Terraform이 계산합니다

조각 14개를 손으로 관리하면 비트 하나를 틀려도 알아채기 어렵습니다. 그래서 Terraform `locals`가 계산하게 했습니다.

```hcl
locals {
  # 비트 b, 값 want(0/1) -> 두 자리 값 00~99 중 그 비트가 want인 값을 "[십][일]|..."로 압축
  version_bit_fragments = {
    for b in range(7) : b => {
      for want in [0, 1] : want => join("|", [
        for units, tens in {
          for t in range(10) : join("", [
            for u in range(10) : tostring(u)
            if floor((t * 10 + u) / pow(2, b)) % 2 == want
          ]) => tostring(t)...
        } : "[${join("", tens)}][${units}]" if units != ""
      ])
    }
  }

  # 비트마다 (Sec-CH-UA, UA) = (1, 0)과 (0, 1)
  version_pairs = flatten([
    for b in range(7) : [
      for ch in [1, 0] : {
        ch_regex = "\"Chromium\";v=\"1(${local.version_bit_fragments[b][ch]})\""
        ua_regex = "Chrome/1(${local.version_bit_fragments[b][1 - ch]})\\."
      }
    ]
  ])
}
```

`for` 식의 `...`은 같은 키의 값을 리스트로 모으는 grouping 문법입니다. 일의 자리 집합 문자열을 키로 쓰면 같은 집합을 가진 십의 자리가 한 리스트에 모입니다. 괄호는 묶음 용도로만 쓰고 캡처한 값을 다시 쓰지 않습니다.

### 6.6. 모든 조합을 대입해 확인했습니다

규칙이 맞다는 설명만으로는 부족합니다. 위 `locals`의 출력을 `terraform console`로 뽑아서, UA 10~199와 `Sec-CH-UA` 100~199의 모든 조합을 Python 정규식에 대입했습니다. UA가 두 자리인 경우는 아래 6.7의 별도 쌍을 함께 넣었습니다.

```python
import json, re
from itertools import product

pairs = json.loads(json.loads(open("out.json").read()))  # terraform console 출력
rules = [(p["ch_regex"], p["ua_regex"]) for p in pairs]
rules.append(('"Chromium";v="1[0-9][0-9]"', r'Chrome/[1-9][0-9]\.'))  # UA 10~99

errors = 0
for ua, ch in product(range(10, 200), range(100, 200)):
    ch_header = f'"Chromium";v="{ch}", "Not?A_Brand";v="24"'
    ua_header = f"Mozilla/5.0 (X11; Linux x86_64) Chrome/{ua}.0.0.0 Safari/537.36"
    matched = any(re.search(c, ch_header) and re.search(u, ua_header) for c, u in rules)
    errors += matched != (ua != ch)
print(errors)  # 0
```

19,000개 조합에서 판정이 틀린 경우는 0건이었습니다. 실제 적용 전에는 몇 시간치 WAF 로그 수백만 건에 새 정규식과 정확한 숫자 비교를 함께 적용했고, 판정이 다른 요청은 없었습니다.

### 6.7. 결과와 한계

| 구성 요소 | 정규식 수 | WCU |
| :--- | ---: | ---: |
| 비트 쌍 b0~b6, 2방향 | 28 | 84 |
| UA 10~99 + `Sec-CH-UA` 1xx 쌍 | 2 | 6 |
| 예외 2개 (`NOT` 정규식) | 2 | 6 |
| 합계 (계산) | 32 | 96 |
| `CheckCapacity` 실측 | - | 97 |

UA 10~99 쌍은 리뷰에서 나온 구멍을 막으려고 넣었습니다. 1xx끼리만 비교하면 UA를 `Chrome/99`처럼 두 자리로 낮춘 요청을 놓칩니다. 예전 룰은 이런 요청을 잡고 있었습니다.

예외 두 개 중 하나는 운영에서 찾은 오탐입니다. Android WebView는 앱이 UA 문자열을 바꿀 수 있습니다. 어떤 앱은 UA를 `Chrome/142.0.7444.106`처럼 특정 빌드로 고정해 두었고, 그사이 WebView 엔진이 155로 올라가 `Sec-CH-UA`에는 155가 실렸습니다. 모양은 UA만 바꾼 봇과 같지만, 사용자는 실제 사람이었습니다. `"Android WebView"` 브랜드는 엔진이 채우는 값이고 데스크톱에서 도는 봇은 보내지 않으므로, 이 브랜드가 있으면 버전 판정에서만 뺐습니다.

결과적으로 187 WCU 룰이 97 WCU가 됐고, 판정 범위는 130~160에서 UA 10~199 전체로 넓어졌습니다. 범위를 갱신할 일도 없어졌습니다. 남은 한계는 두 가지입니다.

- 200 이상 버전은 보지 않는다. Chrome이 약 4주마다 major 버전을 올리면 200까지는 3년 넘게 남았다.
- `Sec-CH-UA`가 89~99이고 UA가 1xx인 조합은 보지 않는다. 예전 룰도 보지 않던 범위다.

---

## 7. 세 변경으로 줄인 WCU

| 룰 | 바꾸기 전 | 바꾼 뒤 | 바꾼 방법 |
| :--- | ---: | ---: | :--- |
| JA4 + 구버전 UA 차단 | 82 | 15 | `CONTAINS` 7개를 정규식 1개로 |
| UA 블랙리스트 | 30 | 13 | `CONTAINS` 2개를 정규식 1개로 |
| UA와 `Sec-CH-UA` 버전 비교 | 187 | 97 | 버전 쌍 31개를 비트 쌍 14개로 |
| 합계 | 299 | 125 | -174 |

**판정은 그대로 두고 174 WCU를 되찾았습니다.** 그 예산으로 OS 불일치, `HeadlessChrome` 브랜드, 헤더를 아예 보내지 않는 Chrome UA 같은 탐지 룰을 더 넣었고, Web ACL은 여전히 1,500 아래에 있습니다.

---

## 8. 줄이면 안 되는 것

WCU를 줄이는 방법 중에는 판정을 바꾸는 것도 있습니다. 제가 검토하고 넣지 않은 것들입니다.

- text transformation 제거: `LOWERCASE`를 빼면 10 WCU가 줄지만 대소문자가 다른 UA를 놓친다.
- `NOT`으로 조건 뒤집기: statement 수는 줄어도 헤더가 없는 요청까지 매칭된다.
- CloudFront Functions로 옮기기: WCU는 0이지만 WAF 로그, label, WAF 지표에 남지 않아 관찰과 롤백이 어려워진다.
- 관리형 룰 그룹 빼기: 700 WCU짜리 CRS를 빼면 예산은 크게 남는다. 저는 SQLi, Linux 룰 그룹이 일주일 동안 실제로 요청을 차단하고 있는 것을 확인하고 유지했다.
- 예외 문자열 믿기: `"Android WebView"` 브랜드나 크롤러 UA 토큰은 위조할 수 있다. 크롤러 예외는 UA 토큰만이 아니라 ASN이나 공개 크롤러 IP 목록과 함께 판단한다.

헤더 검사에도 한계가 있습니다. UA, `Sec-CH-UA`, `Sec-CH-UA-Platform`, TLS 지문을 모두 실제 Chrome과 맞춘 도구는 이 방식으로 구분할 수 없습니다. 이 영역은 Bot Control Targeted(요청 100만 건당 $10) 같은 행동 기반 탐지나 애플리케이션 단 대응이 필요합니다. 헤더 룰은 UA만 바꾼 자동화를 싸고 정확하게 걸러내는 층입니다.

---

## 9. 룰을 바꿀 때 지킨 순서

1. 바꿀 rule 목록으로 `CheckCapacity`를 호출해 WCU를 먼저 확인한다.
2. 실제 차단 중인 룰을 바꾸면 WAF 로그에 새 조건과 기존 조건을 함께 적용해 판정 차이가 0건인지 본다.
3. 새 탐지 룰은 `Count` + label로 넣고 label 지표와 통과한 요청을 며칠 관찰한다.
4. 오탐을 예외로 정리한 뒤 마지막 label 판정 룰 하나만 `Block`으로 바꾼다.
5. 적용 직후 해당 룰의 `BlockedRequests`가 같은 시간대와 비슷한지 확인한다.
6. 문제가 생기면 이전 커밋으로 되돌려 다시 apply한다. Web ACL 업데이트는 룰 전체를 한 번에 교체하므로 롤백도 한 번이다.

---

## 10. 마치며

WCU는 룰을 쓰는 방식만 바꿔도 줄일 수 있는 비용입니다. 요청 수는 공격자가 정하지만, 같은 판정을 몇 WCU로 표현할지는 룰을 쓰는 사람이 정합니다. 이번에 제가 쓴 방법은 단가표를 읽고 비싼 연산을 싼 연산으로 바꾸는 것, 판정을 label로 모으는 것, WAF가 직접 못 하는 비교를 할 수 있는 조각으로 나누는 것이었습니다. 세 방법 모두 바꾸기 전에 `CheckCapacity`와 로그 재생으로 판정이 같은지 확인한 뒤에 적용했습니다.

---

## 11. Reference

- [AWS Docs - Web ACL capacity units (WCUs) in AWS WAF](https://docs.aws.amazon.com/waf/latest/developerguide/aws-waf-capacity-units.html)
- [AWS - AWS WAF Pricing](https://aws.amazon.com/waf/pricing/)
- [AWS Docs - AWS WAF quotas](https://docs.aws.amazon.com/waf/latest/developerguide/limits.html)
- [AWS Docs - String match rule statement](https://docs.aws.amazon.com/waf/latest/developerguide/waf-rule-statement-type-string-match.html)
- [AWS Docs - Regex match rule statement](https://docs.aws.amazon.com/waf/latest/developerguide/waf-rule-statement-type-regex-match.html)
- [AWS Docs - Regex pattern set match rule statement](https://docs.aws.amazon.com/waf/latest/developerguide/waf-rule-statement-type-regex-pattern-set-match.html)
- [AWS Docs - Supported regular expression syntax in AWS WAF](https://docs.aws.amazon.com/waf/latest/developerguide/waf-regex-pattern-support.html)
- [AWS Docs - Label match rule statement](https://docs.aws.amazon.com/waf/latest/developerguide/waf-rule-statement-type-label-match.html)
- [AWS Docs - NOT rule statement](https://docs.aws.amazon.com/waf/latest/developerguide/waf-rule-statement-type-not.html)
- [AWS Docs - Using rate-based rule statements in AWS WAF](https://docs.aws.amazon.com/waf/latest/developerguide/waf-rule-statement-type-rate-based.html)
- [AWS Docs - Baseline rule groups](https://docs.aws.amazon.com/waf/latest/developerguide/aws-managed-rule-groups-baseline.html)
- [AWS Docs - Use-case specific rule groups](https://docs.aws.amazon.com/waf/latest/developerguide/aws-managed-rule-groups-use-case.html)
- [AWS Docs - IP reputation rule groups](https://docs.aws.amazon.com/waf/latest/developerguide/aws-managed-rule-groups-ip-rep.html)
- [AWS API Reference - CheckCapacity](https://docs.aws.amazon.com/waf/latest/APIReference/API_CheckCapacity.html)
- [MDN - Sec-CH-UA](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Sec-CH-UA)
- [Chrome for Developers - User-Agent Client Hints](https://developer.chrome.com/docs/privacy-security/user-agent-client-hints)
- [Chromium Blog - Speeding up Chrome's release cycle](https://blog.chromium.org/2021/03/speeding-up-release-cycle.html)
- [Terraform Docs - for Expressions](https://developer.hashicorp.com/terraform/language/expressions/for)

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
