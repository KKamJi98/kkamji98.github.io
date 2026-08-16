---
title: "AWS WAF Challenge Action - 브라우저 토큰과 SPA 요청 경계"
date: 2026-07-23 18:00:00 +0900
author: kkamji
categories: [Cloud, AWS]
tags: [aws, waf, challenge, javascript, spa, cloudfront, security]
comments: true
image:
  path: /assets/img/aws/aws.webp
---

로그인, 계정 생성, 쿠폰 발급처럼 자동화 요청이 실제 피해로 이어질 수 있는 browser flow에서는 정상 사용자를 매번 CAPTCHA에 통과시키지 않고도 의심스러운 client를 한 번 더 확인하고 싶을 때가 있습니다. AWS WAF Challenge는 이때 사용할 수 있는 WAF rule action입니다. browser가 background에서 WAF token을 획득할 수 있는지 확인하고, 유효한 token을 가진 request만 남은 Web ACL rule 평가로 진행시킵니다.

핵심은 Challenge가 authentication이나 authorization이 아니라는 점입니다. token은 로그인한 사용자나 사람을 식별하는 application credential이 아닙니다. JavaScript를 실행할 수 있는 browser flow에 한정해 자동화 요청을 구분하는 신호이며, token을 얻기 전과 얻은 뒤 request가 어떻게 달라지는지 이해해야 rule scope를 안전하게 잡을 수 있습니다.

> **TL;DR**  
> - Challenge는 authentication이 아니다. 유효 token이 있으면 `Count`처럼 다음 rule로 넘길 뿐이고, 뒤 priority의 Block rule과 default action은 그대로 적용된다.  
> - token이 없거나 immunity time이 지나면 Web ACL 평가가 끝나고 `202`와 `x-amzn-waf-action: challenge`가 돌아온다. JSON API가 받은 `202`를 파싱해 복구하려 하면 안 된다.  
> - Web ACL의 **token domain list는 cookie의 `Domain` 속성이 아니다.** WAF가 그 token을 받아들일지 판단하는 별도 allowlist다.  
> - token을 얻는 HTML `GET` route와 보호 API route를 분리하고, 새 rule은 HTML navigation으로 scope를 좁혀 `Count`부터 관찰한다. rollback도 action을 `Count`로 되돌리는 쪽이 안전하다.  
{: .prompt-info}

---

## 1. Challenge는 조용한 browser 검증을 위한 WAF rule action입니다

Challenge rule에 매칭된 request는 AWS WAF가 token 상태를 먼저 확인합니다. 유효하고 만료되지 않은 token이 있으면 `Count` action처럼 다음 rule로 평가가 이어집니다. token이 없거나, 무효이거나, immunity time이 지났다면 AWS WAF는 해당 request의 Web ACL 평가를 끝내고 `202 Request Accepted`와 `x-amzn-waf-action: challenge`를 반환합니다. request가 `Accept: text/html`을 보낸 경우에는 challenge script가 포함된 HTML interstitial도 함께 반환합니다.

| action | browser에 요구하는 동작 | token이 유효할 때 | token이 없거나 무효일 때 |
| :--- | :--- | :--- | :--- |
| Challenge | JavaScript 기반의 silent verification | 다음 WAF rule 평가로 진행 | `202` challenge response |
| CAPTCHA | 사용자의 puzzle 응답 | 다음 WAF rule 평가로 진행 | `405` CAPTCHA response |
| Block | 별도 browser 검증 없음 | 해당 없음 | rule 평가 종료, 기본 `403` |

Challenge는 "사람임을 증명"하거나 access 권한을 부여하지 않습니다. 뒤 priority의 Block rule, managed rule group, Web ACL default action은 유효 token이 있어도 계속 적용됩니다.

Challenge를 우선 검토할 만한 경우는 다음과 같습니다.

- browser에서 시작하는 로그인, 계정 생성, password reset 같은 민감한 HTML entry flow
- JavaScript integration과 CSP(Content Security Policy)를 제어할 수 있고, protected request보다 먼저 token을 획득할 수 있는 SPA
- Challenge token 상태를 검토하는 managed rule group 또는 좁은 custom Challenge rule을 이미 Count로 관찰한 경우

반대로 webhook, partner API, mobile app, server-to-server client처럼 JavaScript document를 실행하지 않는 client에는 적합하지 않습니다. `POST /api/orders`, CORS(Cross-Origin Resource Sharing) preflight `OPTIONS`, JSON-only API를 token 획득용 interstitial endpoint로 쓰는 것도 피해야 합니다. Challenge는 rule에 매칭된 각 request에서 동작하지만, token을 얻는 entry point는 browser가 HTML과 JavaScript를 처리할 수 있는 `GET` route로 분리하는 편이 안전합니다.

![AWS WAF Challenge token flow](/assets/img/aws/aws-waf-challenge-token-flow.webp)
_token이 없거나 만료 또는 무효일 때 WAF는 `202` response를 반환합니다. browser가 token을 획득해 재시도한 request는 남은 rule 평가로 진행합니다._

---

## 2. token은 integration script에서 얻어 `aws-waf-token` cookie에 저장됩니다

AWS WAF JavaScript integration을 사용하는 browser application은 Web ACL에서 제공하는 integration URL의 `/challenge.js` script를 page의 `<head>`에 넣을 수 있습니다. 이 script는 page load 중 background token retrieval을 시작합니다. application이 직접 시점을 제어해야 하면 `AwsWafIntegration.getToken()`을 호출합니다.

`getToken()`은 asynchronous API입니다. 현재 page에 만료되지 않은 token이 있으면 즉시 반환하고, 없으면 token provider에서 새 token을 가져옵니다. 이 acquisition workflow는 최대 2초를 기다린 뒤 timeout이면 error를 발생시키므로, application은 error와 retry UI를 자신이 다루는 request error model에 포함해야 합니다. `AwsWafIntegration.hasToken()`은 현재 `aws-waf-token` cookie에 만료되지 않은 token이 있는지만 확인합니다.

성공한 token은 현재 page의 `aws-waf-token` cookie에 저장됩니다. AWS 문서는 token이 암호화되어 있고 아래와 같은 성질을 가진다고 설명하지만, 전체 contents와 encryption process의 상세는 공개하지 않습니다.

- client의 가장 최근 successful silent challenge timestamp
- CAPTCHA를 사용한 경우 가장 최근 successful CAPTCHA timestamp
- unwanted automated activity를 구분하는 데 쓰이는 client identifier와 client-side behavior signal

따라서 application은 token을 opaque value로 취급해야 합니다. 이 signal은 unique identifier가 아니며 특정 사람에게 mapping할 수 있는 정보로 설명되지 않습니다. 그렇더라도 token 값을 application authorization claim으로 해석하거나, 로그와 analytics event에 그대로 남기면 안 됩니다. token lifecycle, CSP allowlist, log redaction과 privacy notice는 별도 security 및 privacy review 대상입니다.

Challenge와 CAPTCHA의 default immunity time은 300초입니다. Challenge는 300초부터 3일, CAPTCHA는 60초부터 3일까지 설정할 수 있습니다. immunity time이 끝나면 browser는 새 token을 얻어야 하므로, 짧은 값이 항상 더 강한 방어를 의미하지는 않습니다.

---

## 3. request delivery와 WAF token domain은 서로 다른 경계입니다

같은 host browser request는 보통 `aws-waf-token` cookie를 자동으로 보냅니다. 다만 cookie가 모든 client call에 자동으로 붙는 것은 아닙니다. AWS 문서는 host domain을 넘는 call이 대표적인 예라고 설명합니다. 가장 단순한 integration은 일반 `fetch()` 대신 AWS WAF wrapper를 사용하는 방식입니다.

여기서 Web ACL의 token domain list는 browser cookie의 `Domain` 속성이 아닙니다. token을 받은 뒤 AWS WAF가 해당 token을 받아들일지 판단하는 별도 allowlist입니다. AWS는 `aws-waf-token` cookie의 정확한 `Domain`, `SameSite`, `HttpOnly` 설정을 공개하지 않으므로 application이 그 값을 추정해 transport 동작을 설계하면 안 됩니다.

```javascript
async function loadProtectedProfile() {
  await AwsWafIntegration.getToken();

  const response = await AwsWafIntegration.fetch('/api/me', {
    headers: { Accept: 'application/json' },
  });

  if (!response.ok) {
    throw new Error(`protected request failed: ${response.status}`);
  }

  return response.json();
}
```

`AwsWafIntegration.fetch()`는 standard `fetch` option을 지원하면서 integration의 token handling을 추가합니다. plain `fetch()`와 wrapper를 섞으면 일부 request만 token 없이 먼저 나갈 수 있으므로 protected endpoint의 request path를 일관되게 정해야 합니다.

wrapper를 사용할 수 없고 cross-host request에 token을 명시해야 한다면, `getToken()`이 반환한 값을 `x-aws-waf-token` request header에 넣을 수 있습니다. AWS WAF는 `aws-waf-token` cookie와 이 header 모두에서 token을 읽습니다.

```javascript
async function requestAcrossHosts(url) {
  const token = await AwsWafIntegration.getToken();

  return fetch(url, {
    headers: {
      Accept: 'application/json',
      'x-aws-waf-token': token,
    },
  });
}
```

이 header는 token domain 검증을 우회하지 않습니다. 이 검증은 browser의 cookie 전달 규칙과 별개입니다. 기본적으로 AWS WAF는 protected resource의 host domain과 정확히 일치하는 token domain만 허용합니다. cross-host token을 쓸 경우에는 Web ACL token domain list에 필요한 domain을 명시해야 합니다. list에 parent domain을 넣으면 그 prefix subdomain도 허용될 수 있으므로 편의를 위해 넓은 parent domain을 넣기보다 실제 browser trust boundary에 필요한 값만 추가해야 합니다.

CloudFront와 ALB를 함께 쓴다고 항상 cookie forwarding이 필요한 것은 아닙니다. Web ACL을 ALB에 연결하고 그 ALB를 CloudFront distribution의 origin으로 두어 ALB-side WAF도 token을 검사하는 구성에서만 이 조건이 생깁니다. 이때 CloudFront는 기본적으로 cookie를 origin으로 전달하지 않으므로 cache behavior에서 `aws-waf-token` 또는 필요한 cookie를 forwarding해야 합니다. browser는 CloudFront domain을 보지만 ALB-side WAF는 origin host를 기준으로 token domain을 검사하므로, ALB-side Web ACL token domain list에서 CloudFront distribution domain을 허용해야 합니다.

---

## 4. `202`는 browser가 token을 얻기 전 request가 종료됐다는 신호입니다

Challenge response는 application의 정상 API response가 아닙니다. token 상태에 따른 rule evaluation을 분리하면 first request와 retry request를 혼동하지 않을 수 있습니다.

| request token 상태 | Challenge action 결과 | 이후 rule 평가 |
| :--- | :--- | :--- |
| 유효하고 immunity time 안 | `Count`처럼 처리 | 다음 rule로 진행 |
| 없음, 만료, 무효 | `202`, `x-amzn-waf-action: challenge` 반환 | 여기서 종료 |

HTML navigation에서 받은 interstitial은 browser가 challenge workflow를 수행할 수 있게 합니다. 반면 JSON API `POST`가 `202`를 받았다고 해서 application이 response body를 파싱해 복구하려 하면 안 됩니다. browser application은 protected fetch보다 token retrieval이 먼저 끝나도록 하고, token acquisition timeout이나 network failure는 application error path로 처리해야 합니다.

`x-amzn-waf-action` header는 cross-domain JavaScript retrieval에서 사용할 수 없습니다. 이 header를 보고 cross-origin API client를 복구하는 구조 대신, document host, token domain, API host가 실제로 같은 token trust boundary에 있는지 먼저 확인해야 합니다.

---

## 5. token을 얻는 HTML route와 보호 API route를 분리합니다

browser origin과 같은 site에 protected API가 있다면, 먼저 HTML document에서 token을 얻고 그 뒤 API call을 시작합니다. token을 받고 있는 중에 initial render가 `fetch('/api/me')`를 먼저 보내면 첫 request가 `202`가 되는 race가 발생할 수 있습니다.

| request 종류 | Challenge 적용 판단 |
| :--- | :--- |
| browser의 `GET /signin` 같은 HTML navigation | token 획득 entry point로 적합한 후보 |
| HTML page에서 시작하는 browser flow | token 확보 뒤 protected request를 시작 |
| authenticated JSON API `POST` | direct interstitial 적용을 피하고 기존 token을 검증 |
| CORS preflight `OPTIONS` | Challenge를 적용하지 않음 |
| mobile app, webhook, partner API | Challenge 대신 authentication과 rate policy를 검토 |

CSP가 AWS WAF JavaScript integration endpoint를 막으면 token acquisition은 실패합니다. AWS 문서가 안내하는 `https://*.awswaf.com` 범위를 `connect-src`, `script-src`, `script-src-elem`에 필요한 만큼만 허용하고, unrelated third-party domain까지 wildcard를 넓히지 않습니다.

---

## 6. Challenge rule은 HTML GET부터 Count로 관찰합니다

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

no-token Challenge request는 최초 `202` response와 token 획득 뒤 retry request로 log와 metric에 두 번 보일 수 있습니다. Challenge count만으로 attack volume이나 unique user 수를 계산하면 안 됩니다.

CloudFront용 Web ACL은 control plane상 `us-east-1`에 만들고, ALB와 Amazon API Gateway REST API용 Web ACL은 보호 resource와 같은 Region에 만듭니다. API Gateway HTTP API도 같은 association 범위라고 추정하지 말고, 적용 전 현재 AWS WAF association 문서를 다시 확인해야 합니다.

---

## 7. rollback은 rule action을 `Count`로 되돌리는 방식이 안전합니다

Challenge를 적용하는 구성에서 가장 빠른 rollback은 보통 rule action을 `Count`로 되돌리는 것입니다. Web ACL association 전체를 제거하면 다른 managed rule과 Block rule까지 함께 사라질 수 있습니다.

1. disposable path 또는 narrow HTML route만 Count로 관찰합니다.
2. full WAF logging에서 URI, method, user agent, label, terminating rule을 확인합니다.
3. browser integration, CSP, token domain, CORS가 통과한 뒤 소수 route만 Challenge로 바꿉니다.
4. `ChallengeRequests`, valid token metric, origin error, login conversion을 baseline과 비교합니다.
5. 정상 browser 영향이 보이면 action을 즉시 Count로 복귀하고 log를 보존합니다.
6. rule owner, scope, priority, immunity time, 검토일을 IaC review 기록에 남깁니다.

AWS WAF logging에는 authorization header, cookie, query string 같은 민감 정보가 들어갈 수 있습니다. data protection, redaction, retention, log destination 접근 권한을 Challenge rollout과 함께 검토해야 합니다.

---

## 8. Reference

- [AWS Docs - Rule actions](https://docs.aws.amazon.com/waf/latest/developerguide/waf-rule-action.html)
- [AWS Docs - CAPTCHA and Challenge actions](https://docs.aws.amazon.com/waf/latest/developerguide/waf-captcha-and-challenge-actions.html)
- [AWS Docs - CAPTCHA and Challenge best practices](https://docs.aws.amazon.com/waf/latest/developerguide/waf-captcha-and-challenge-best-practices.html)
- [AWS Docs - AWS WAF JavaScript API](https://docs.aws.amazon.com/waf/latest/developerguide/waf-js-challenge-api.html)
- [AWS Docs - Using the fetch wrapper](https://docs.aws.amazon.com/waf/latest/developerguide/waf-js-challenge-api-fetch-wrapper.html)
- [AWS Docs - Using getToken](https://docs.aws.amazon.com/waf/latest/developerguide/waf-js-challenge-api-get-token.html)
- [AWS Docs - AWS WAF token characteristics](https://docs.aws.amazon.com/waf/latest/developerguide/waf-tokens-details.html)
- [AWS Docs - Token immunity times](https://docs.aws.amazon.com/waf/latest/developerguide/waf-tokens-immunity-times.html)
- [AWS Docs - Token domains](https://docs.aws.amazon.com/waf/latest/developerguide/waf-tokens-domains.html)
- [AWS Docs - CloudFront and ALB token handling](https://docs.aws.amazon.com/waf/latest/developerguide/waf-tokens-with-alb-and-cf.html)
- [AWS Docs - CAPTCHA and Challenge logs and metrics](https://docs.aws.amazon.com/waf/latest/developerguide/waf-captcha-and-challenge-logs-metrics.html)
- [AWS Docs - Associating an AWS resource with a web ACL](https://docs.aws.amazon.com/waf/latest/developerguide/web-acl-associating-aws-resource.html)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
