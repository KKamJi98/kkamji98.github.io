---
title: "AWS WAF Challenge Action: 브라우저 토큰과 SPA 요청 경계를 이해하기"
date: 2026-07-23 18:00:00 +0900
author: kkamji
categories: [Cloud, AWS]
tags: [aws, waf, challenge, javascript, spa, cloudfront, security]
comments: true
image:
  path: /assets/img/aws/aws.webp
---

`/api` 요청에 AWS WAF Challenge를 바로 붙였는데 browser application이 `202`만 받고 멈춘다면, rule이 고장 난 것이 아니라 request 경계를 잘못 잡았을 가능성이 큽니다. Challenge는 일반 API authentication도, 무조건 차단하는 Block action도 아닙니다. browser가 JavaScript를 실행해 WAF token을 획득할 수 있다는 전제에서 동작합니다.

Challenge action은 rule에 매칭된 각 web request를 평가합니다. 다만 token이 없는 browser가 challenge를 실행할 수 있도록 Challenge rule은 일반적으로 `GET` `text/html` navigation에 적용하고, 보호 API request는 token 획득이 끝난 뒤 전송되도록 구성합니다. ASN, IP set, rate-based rule처럼 조직이 직접 유지하는 network policy는 [AWS WAF Self-Managed Rule](/posts/aws-waf-self-managed-rule/)에 따로 정리했습니다.

---

## 1. Challenge는 token이 없거나 유효하지 않을 때 평가를 끝냅니다

Challenge rule에 매칭된 요청의 결과는 request가 WAF token을 가지고 있는지에 따라 달라집니다.

| token 상태 | Challenge action 결과 | rule 평가 |
| :--- | :--- | :--- |
| 유효하고 immunity time 안 | `Count`처럼 처리 | 다음 rule로 진행 |
| 없음, 만료, 무효 | `202`와 `x-amzn-waf-action: challenge` 반환 | 여기서 종료 |

Challenge는 CAPTCHA와 달리 일반적으로 사람이 puzzle을 푸는 화면보다 browser background verification을 목표로 합니다. token이 유효하면 pass 자체가 allow를 뜻하지 않습니다. 뒤 priority의 Block rule이나 Web ACL default action은 계속 평가됩니다.

![AWS WAF Challenge token flow](/assets/img/aws/aws-waf-challenge-token-flow.webp)
_token이 없거나 만료 또는 무효일 때 WAF가 202 response를 반환합니다. browser가 유효한 token을 얻어 재시도한 요청은 다음 rule 평가로 진행합니다._

Challenge와 CAPTCHA는 모두 default immunity time이 300초입니다. Challenge의 최소값은 300초이고 CAPTCHA의 최소값은 60초이며, 최대값은 3일입니다. 이 값은 Web ACL의 token domain, browser behavior, attack pattern에 맞춰 정해야 합니다. 짧다고 더 강한 방어가 되지는 않으며 token refresh와 추가 비용을 늘릴 수 있습니다.

---

## 2. HTML navigation과 JSON API request를 같은 rule로 다루면 안 됩니다

Challenge response의 interstitial은 HTML을 기대하는 request에 적합합니다. `POST /api/orders`, CORS preflight `OPTIONS`, mobile app 또는 server-to-server client에 Challenge를 직접 적용하면 JavaScript interstitial을 실행할 document가 없거나, client가 202를 정상 protocol response로 처리하지 못할 수 있습니다.

다음 경계를 먼저 정합니다.

| request 종류 | Challenge 적용 판단 |
| :--- | :--- |
| browser의 `GET /signin` 같은 HTML navigation | 적합한 후보 |
| HTML page에서 시작하는 browser flow | token 확보 지점으로 적합 |
| authenticated JSON API `POST` | 직접 interstitial 적용을 피함 |
| CORS preflight `OPTIONS` | 적용하지 않음 |
| mobile app, webhook, partner API | WAF Challenge가 아닌 인증과 rate policy를 검토 |

보호할 API가 browser origin과 같은 site에 있다면, 먼저 HTML document에서 token을 확보하고 이후 fetch가 token을 갖도록 만드는 방식이 안전합니다. API만 별도 domain에 있고 page가 token domain에 포함되지 않으면 token cookie가 전달되지 않을 수 있습니다.

---

## 3. token domain과 HTTPS는 browser integration의 전제입니다

WAF token은 암호화된 `aws-waf-token` cookie로 browser에 저장됩니다. Challenge와 CAPTCHA JavaScript integration은 HTTPS secure context가 필요합니다. HTTP local development, origin이 다른 SPA, CDN과 ALB를 함께 쓰는 구성은 token domain을 먼저 검증해야 합니다.

CloudFront와 ALB가 같은 application flow에서 각각 WAF token을 사용한다면 CloudFront가 `aws-waf-token` cookie를 origin으로 전달해야 하며, ALB-side Web ACL은 CloudFront domain을 token domain으로 허용해야 합니다. 이는 "WAF를 두 번 붙이면 더 안전하다"는 일반 규칙이 아니라, 같은 browser token을 두 enforcement point가 읽어야 하는 특정 구성의 연동 조건입니다.

CSP도 확인 대상입니다. AWS WAF JavaScript integration endpoint를 CSP가 막으면 token acquisition이 실패할 수 있습니다. 문서가 안내하는 AWS WAF endpoint 범위만 `script-src`와 `connect-src`에 허용하고, wildcard를 다른 third-party domain까지 넓히지 않습니다.

---

## 4. SPA에서는 protected fetch보다 token 획득이 먼저 끝나야 합니다

SPA는 initial render 뒤 data fetch를 즉시 시작합니다. Challenge integration이 background token을 받는 동안 `fetch('/api/me')`가 먼저 나가면 첫 API request가 202가 될 수 있습니다. 이 race는 local network가 빠를 때 가끔만 재현되어 production에서 더 찾기 어렵습니다.

AWS WAF JavaScript API를 쓰는 경우, application bootstrap 단계에서 token retrieval을 기다린 뒤 protected request를 시작하는 경계를 둡니다. 아래 코드는 흐름만 보여 주는 pseudocode입니다. SDK script URL, token domain, error handling은 AWS 콘솔에서 얻은 integration endpoint와 application CSP에 맞춰야 합니다.

```javascript
async function startProtectedPage() {
  try {
    await window.AwsWafIntegration.getToken();
    const response = await window.AwsWafIntegration.fetch('/api/me');

    if (!response.ok) {
      throw new Error(`request failed: ${response.status}`);
    }

    render(await response.json());
  } catch (error) {
    renderRetryableError(error);
  }
}
```

plain `fetch()`를 wrapped API와 섞으면 일부 request만 token 없이 나갈 수 있습니다. token retrieval timeout, network failure, expired token refresh를 application error model에 넣고, user에게 raw 202 page가 보이지 않도록 처리해야 합니다.

cross-origin SPA는 한 단계 더 확인해야 합니다. AWS는 `x-amzn-waf-action` header를 cross-domain retrieval에 제공하지 않습니다. 이 header를 읽어 Challenge를 복구하는 방식에 의존하지 말고, protected API가 browser document와 같은 token trust boundary 안에 있는지 먼저 검토합니다.

---

## 5. Challenge rule은 HTML GET부터 Count로 관찰합니다

처음부터 broad Challenge rule을 켜면 token integration이 안 된 정상 browser와 non-browser client를 함께 끊을 수 있습니다. 아래처럼 HTML navigation 후보로 scope를 좁힌 다음 Count로 관찰합니다.

```text
AND
  URI path starts with /signin
  HTTP method equals GET
  Accept header contains text/html
```

Count 기간에는 WAF log와 application metric을 같은 시간 창에서 봅니다.

| 관측값 | 확인할 질문 |
| :--- | :--- |
| `CountedRequests` | 의도한 HTML route만 매칭되는가 |
| `ChallengeRequests` | Challenge 전환 뒤 token 없는 요청이 급증하는가 |
| `RequestsWithValidChallengeToken` | 정상 browser가 token을 받아 재시도하는가 |
| `ChallengeAttempts`, `ChallengeSolved` | browser verification 시도와 성공 비율이 유지되는가 |
| origin 4xx, 5xx, login success | WAF 전환이 service behavior를 악화시키지 않았는가 |

no-token Challenge request는 최초 202 response와 token 획득 뒤 retry request로 log와 metric에 두 번 보일 수 있습니다. Challenge count만으로 attack volume이나 unique user 수를 계산하면 안 됩니다.

CloudFront용 Web ACL은 control plane상 `us-east-1`에 만들고, ALB와 Amazon API Gateway REST API용 Web ACL은 보호 resource와 같은 Region에 만듭니다. API Gateway HTTP API도 같은 association 범위라고 추정하지 말고, 적용 전 현재 AWS WAF association 문서를 다시 확인해야 합니다.

---

## 6. rollout과 rollback은 action 변경을 빠르게 만들기 위한 절차입니다

Challenge를 적용하는 구성에서 가장 빠른 rollback은 보통 rule action을 `Count`로 되돌리는 것입니다. Web ACL association 전체를 제거하면 다른 Managed Rule과 Block rule까지 함께 사라질 수 있습니다.

1. disposable path 또는 narrow HTML route만 Count로 관찰합니다.
2. full WAF logging에서 URI, method, user agent, label, terminating rule을 확인합니다.
3. browser integration, CSP, token domain, CORS가 통과한 뒤 소수 route만 Challenge로 바꿉니다.
4. `ChallengeRequests`와 valid token metric, origin error, login conversion을 baseline과 비교합니다.
5. 정상 browser 영향이 보이면 action을 즉시 Count로 복귀하고 log를 보존합니다.
6. rule owner, scope, priority, immunity time, 검토일을 IaC review 기록에 남깁니다.

AWS WAF logging에는 authorization header, cookie, query string 같은 민감 정보가 들어갈 수 있습니다. data protection, redaction, retention, log destination 접근 권한을 Challenge rollout과 함께 검토해야 합니다.

---

## 7. browser integration에는 privacy 검토가 필요합니다

AWS WAF client integration은 silent browser challenge와 token acquisition을 수행합니다. AWS 문서는 integration 동작을 설명하지만, 특정 조직과 지역의 개인정보 처리 적법성까지 대신 판단하지는 않습니다. event-level browser signal의 수집과 전송 범위는 적용하는 integration, AWS 계약 문서, 조직의 privacy review에서 별도로 확인해야 합니다.

따라서 security team은 Challenge 적용 endpoint와 threat model을 정의하고, privacy와 legal 담당자는 수집 signal, notice, consent 필요성, retention과 third-party transfer를 조직 정책과 관할 규정으로 별도 검토해야 합니다. "silent" challenge라는 이름만으로 사용자 영향이나 privacy 영향이 없다고 단정하면 안 됩니다.

---

## 8. Reference

- [AWS Docs - CAPTCHA and Challenge actions](https://docs.aws.amazon.com/waf/latest/developerguide/waf-captcha-and-challenge-actions.html)
- [AWS Docs - CAPTCHA and Challenge best practices](https://docs.aws.amazon.com/waf/latest/developerguide/waf-captcha-and-challenge-best-practices.html)
- [AWS Docs - AWS WAF JavaScript API](https://docs.aws.amazon.com/waf/latest/developerguide/waf-js-challenge-api.html)
- [AWS Docs - Token immunity times](https://docs.aws.amazon.com/waf/latest/developerguide/waf-tokens-immunity-times.html)
- [AWS Docs - Token domains](https://docs.aws.amazon.com/waf/latest/developerguide/waf-tokens-domains.html)
- [AWS Docs - CAPTCHA and Challenge logs and metrics](https://docs.aws.amazon.com/waf/latest/developerguide/waf-captcha-and-challenge-logs-metrics.html)
- [AWS Docs - Associating an AWS resource with a web ACL](https://docs.aws.amazon.com/waf/latest/developerguide/web-acl-associating-aws-resource.html)
- [AWS WAF Pricing](https://aws.amazon.com/waf/pricing/)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
