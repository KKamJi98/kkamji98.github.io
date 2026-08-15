---
title: "JA4 TLS Fingerprinting 알아보기 - 봇 트래픽 식별과 차단"
date: 2026-08-09 19:00:00 +0900
author: kkamji
categories: [Cloud, Security]
tags: [ja4, tls, fingerprinting, waf, bot, aws, cloudflare, security]
comments: true
image:
  path: /assets/img/aws/aws.webp
---

WAF에서 IP 기반 rate limit, managed rules, JavaScript Challenge를 차례로 배치했는데도 curl이나 Python requests로 만든 단순 스크래핑 봇이 계속 들어온다면, TLS 핸드셰이크 단계에서 클라이언트의 정체를 식별하는 방법을 검토할 시점이다. JA4는 TLS Client Hello 패킷을 기반으로 클라이언트 소프트웨어의 핑거프린트를 생성하는 기법으로, IP 주소나 User-Agent 없이도 클라이언트가 어떤 TLS 라이브러리를 사용하는지 구별할 수 있다.

AWS WAF는 2025년 3월부터 JA4 fingerprint를 request component로 지원하며, rate-based rule의 aggregation key로도 사용할 수 있다. Cloudflare, CloudFront, Google Cloud Armor 등 주요 플랫폼에서도 JA4를 지원한다. 이 글에서는 JA4가 어떻게 핑거프린트를 생성하고, 기존 봇 완화 기법과 어떻게 조합하는지를 공식 문서와 실제 설정 기준으로 정리한다.

---

## 1. JA3에서 JA4로: 왜 새로운 핑거프린팅이 필요했는가

TLS 클라이언트 핑거프린팅은 Client Hello 패킷에 포함된 cipher suite, extension, TLS 버전 등의 조합으로 클라이언트를 식별하는 기법이다. 최초의 널리 쓰인 구현체는 JA3로, 2017년 Salesforce의 John Althouse가 개발했다. JA3는 Client Hello의 cipher, extension, elliptic curve, elliptic curve point format을 나타나는 순서대로 이어 붙이고 MD5 해시를 생성했다.

JA3가 동작하던 시절에는 브라우저와 TLS 라이브러리가 Client Hello 필드를 일관된 순서로 배치했다. 하지만 2023년 Google Chrome은 Client Hello의 extension 순서를 난수화하는 변경을 적용했다. 이 변경으로 동일한 Chrome 브라우저가 연결할 때마다 다른 JA3 해시를 생성하게 됐고, JA3 기반의 핑거프린트 데이터베이스와 WAF 규칙이 무력화됐다. Cipher suite 순서를 의도적으로 섞는 cipher stunting 기법도 같은 문제를 일으켰다.

JA4는 같은 원작자가 FoxIO에서 2023년 9월에 발표한 후속 표준이다. 핵심 차이는 cipher와 extension을 Client Hello에 나타나는 순서가 아닌 hex 값 기준으로 정렬한 뒤 해시를 생성한다는 점이다. Chrome이 extension 순서를 난수화하더라도 정렬 후 해시하면 동일한 핑거프린트가 나온다. 해시 알고리즘도 MD5에서 SHA-256으로 변경하고, 해시 결과를 12자리로 truncate한다.

| 구분 | JA3 | JA4 |
| :--- | :--- | :--- |
| 발표 | 2017 (Salesforce) | 2023-09 (FoxIO) |
| 정렬 | Client Hello 순서 보존 | cipher, extension hex 기준 정렬 |
| 해시 | MD5 | SHA-256 (truncate 12 chars) |
| 포맷 | 단일 해시 문자열 | human-readable prefix + 두 해시 segment |
| 유지보수 | archived (중단) | 활발 (2026-07 기준 2,038 stars) |
| Chrome extension 랜덤화 | 우회 불가 | 정렬로 우회 |

JA3 저장소는 현재 "no longer being actively maintained"로 표시되어 있으며, 원작자가 FoxIO에서 JA4로 개발을 이어가고 있다.

---

## 2. JA4 핑거프린트 구조

JA4 핑거프린트는 사람이 읽을 수 있는 prefix와 두 개의 해시 segment로 구성된다. 다음은 실제 핑거프린트의 예시다.

```text
t13d1516h2_8daaf6152771_b186095e22b6
```

이 문자열을 분해하면 각 부분이 의미를 갖는다.

### 2.1. Prefix: `t13d1516h2`

| 위치 | 값 | 의미 |
| :--- | :--- | :--- |
| 첫 글자 | `t` | 프로토콜 (q=QUIC, d=DTLS, t=TLS over TCP) |
| 두 번째 | `13` | TLS 버전 (10=1.0, 11=1.1, 12=1.2, 13=1.3) |
| 세 번째 | `d` | SNI 있음 (d=domain present, i=IP absent) |
| 네 번째 | `15` | cipher 개수 (GREASE 제외) |
| 다섯 번째 | `16` | extension 개수 (GREASE, SNI, ALPN 제외) |
| 여섯 번째 | `h2` | 첫 번째 ALPN 값 (h2, http/1.1, spdy/3.1 등) |

### 2.2. Cipher hash: `8daaf6152771`

cipher suite 목록을 hex 값 기준으로 정렬한 뒤 연결하고, SHA-256 해시의 앞 12자리를 취한다. GREASE 값은 제거한다.

### 2.3. Extension hash: `b186095e22b6`

extension 목록에서 SNI(0x0000)와 ALPN(0x0010)을 제거한 뒤 hex 기준으로 정렬한다. 여기에 정렬하지 않은 signature algorithms extension 목록을 그대로 append한 후 SHA-256 해시의 앞 12자리를 취한다.

SNI와 ALPN을 extension 해시에서 제외하는 이유는, 같은 애플리케이션이 다른 도메인이나 IP로 연결할 때 핑거프린트가 변하지 않도록 하기 위해서다. 핑거프린트는 클라이언트 소프트웨어의 정체를 식별하는 것이 목적이지, 연결 대상을 식별하는 것이 아니기 때문이다.

---

## 3. JA4+ 제품군: TLS 너머의 핑거프린팅

FoxIO는 JA4(TLS Client) 외에도 TLS 이외의 계층을 핑거프린팅하는 JA4+ 제품군을 제공한다.

| 핑거프린트 | 대상 | 설명 |
| :--- | :--- | :--- |
| JA4 | TLS Client Hello | 클라이언트 TLS 핑거프린트 |
| JA4S | TLS Server Hello | 서버 응답 핑거프린트, session 특성 식별 |
| JA4H | HTTP Client | HTTP 요청 헤더 기반 핑거프린트 (Cookie, Referer 제외) |
| JA4L | Latency | 클라이언트-서버 간 지연 시간 측정, VPN/Proxy 탐지 |
| JA4X | X.509 Certificate | TLS 인증서 핑거프린팅 |
| JA4SSH | SSH Traffic | SSH 세션 핑거프린팅 |
| JA4T | TCP Client | TCP 특성 기반 OS 핑거프린팅 |

라이선스는 JA4(TLS Client)만 BSD 3-Clause 오픈소스이며, JA4+ 제품군(JA4S, JA4H, JA4L, JA4X, JA4SSH, JA4T, JA4D)은 FoxIO License 1.1을 따른다. 상업적 OEM 사용은 별도 라이선스가 필요하며, detection logic은 patent pending이다.

---

## 4. AWS WAF에서 JA4 활용하기

AWS WAF는 2023년 9월에 JA3 fingerprint match를 지원한 데 이어, 2025년 3월에 JA4 fingerprinting을 추가했다. 같은 업데이트에서 rate-based rule의 aggregation key로 JA3와 JA4 fingerprint를 사용할 수 있게 됐다.

### 4.1. fingerprint request component

AWS WAF rule statement에서 JA3 fingerprint와 JA4 fingerprint를 request component로 사용할 수 있다. fingerprint 값은 byte match statement의 match inspect 대상으로 지정한다.

```text
Match statement:
  Inspect: JA4 fingerprint
  Match type: Starts with string
  Match string: t13d
  Text transformation: None
```

위 예시는 TLS 1.3 Client Hello를 보내는 클라이언트를 매칭한다. 핑거프린트의 prefix는 사람이 읽을 수 있으므로, 특정 TLS 버전이나 프로토콜을 가진 클라이언트를 조건으로 사용할 수 있다.

### 4.2. rate-based rule aggregation key

rate-based rule에서 aggregation key를 IP가 아닌 JA4 fingerprint로 지정하면, 동일한 TLS 핑거프린트를 가진 요청을 하나의 그룹으로 묶어 rate limit을 적용할 수 있다. NAT나 프로xy 뒤에서 여러 IP로 분산되는 봇 팜을 IP 기반 rate limit로 잡기 어려울 때 특히 유용하다.

IP 기반 rate limit가 "하나의 IP에서 100 req/min"을 감지한다면, JA4 기반 aggregation은 "알려진 봇 도구 핑거프린트에서 오는 모든 요청이 100 req/min"을 감지한다. 봇이 IP를 순환하더라도 핑거프린트가 같으면 같은 그룹으로 집계된다.

### 4.3. CloudFront에서 JA4 헤더 받기

Amazon CloudFront는 2024년 10월부터 JA4 fingerprinting을 지원한다. CloudFront 로그의 `tls_client_ja4` 필드에서 핑거프린트를 확인할 수 있으며, origin으로 전달하는 HTTP 헤더에도 포함된다.

CloudFront 앞에 AWS WAF를 배치한 구조라면, WAF rule에서 JA4 fingerprint를 직접 inspect할 수 있다. CloudFront에서 WAF로 전달되는 요청에 fingerprint가 이미 계산되어 있기 때문에 별도 전처리가 필요 없다.

---

## 5. 다른 플랫폼에서의 JA4 지원

| 플랫폼 | 지원 범위 | 비고 |
| :--- | :--- | :--- |
| AWS WAF | JA3, JA4 request component + rate aggregation | 2025-03 추가 |
| Amazon CloudFront | JA4 로그 필드, HTTP 헤더 | 2024-10 추가 |
| Cloudflare | JA3/JA4 + JA4 Signals | Enterprise + Bot Management 필요 |
| Google Cloud Armor | JA4 기반 allow/deny rule | |
| Azure Front Door | JA4 HTTP 헤더 | |
| Vercel | JA4 fingerprint | |
| Fastly | VCL 변수 `tls.client.ja4` | 요청 시 활성화 필요 |
| Akamai | JA4 설정 API | |
| NGINX | FoxIO 공식 모듈 (개발 중단) | known bugs, 프로덕션 비권장 |
| HAProxy | 커뮤니티 Lua 플러그인 | HAProxy 3.1+ 필요 |

Cloudflare의 경우 JA4를 Enterprise 플랜과 Bot Management 구독자에게만 제공한다. Free, Pro, Business 플랜에서는 JA3/JA4 fingerprint 필드를 사용할 수 없다. Cloudflare Workers 환경에서는 JA4 Signals라는 inter-request 통계 배열을 통해 핑거프린트 기반 분석이 가능하다.

NGINX 모듈은 FoxIO 공식 저장소에 있으나 README에 "Development for JA4 on Nginx has been on pause"라고 명시되어 있으며, known bugs가 존재해 프로덕션 환경에서 사용하기 어렵다.

---

## 6. 기존 봇 완화 기법과 JA4의 관계

이 블로그의 WAF 연재에서 다룬 JavaScript Challenge, CAPTCHA, managed rules와 JA4는 서로 다른 계층에서 클라이언트를 검증한다. JA4는 이 계층 구조에서 TLS 레이어의 신호를 추가한다.

| 기법 | 검증 계층 | JA4와의 관계 |
| :--- | :--- | :--- |
| IP rate limit | L3/L4 (요청 빈도) | JA4 aggregation이 IP 순환 봇에 더 정확 |
| Managed Rules | L7 (시그니처) | JA4는 managed rules가 탐지하지 못하는 미확인 도구 식별 |
| JavaScript Challenge | L7 (실행 검증) | 보완적. JS Challenge를 통과한 봇도 TLS 핑거프린트로 추가 식별 |
| CAPTCHA | L7 (사람 검증) | JA4는 사전 필터. 의심 핑거프린트에만 CAPTCHA를 제시해 UX 개선 |

실제 다층 방어 배치를 구성한다면 다음 순서를 고려할 수 있다.

```text
IP rate limit -> Managed Rules -> JA4 fingerprint filter -> JS Challenge -> CAPTCHA
(L3/L4)         (L7 signature)   (L7 TLS signal)           (L7 execution)  (L7 human)
```

JA4 fingerprint filter가 앞단에서 알려진 봇 도구의 핑거프린트를 rate limit이나 차단하고, 통과한 요청은 JS Challenge와 CAPTCHA로 추가 검증한다. 각 계층이 서로 다른 신호를 사용하므로 한 계층을 우회해도 다른 계층이 보완한다.

---

## 7. 한계와 운영 주의사항

JA4 핑거프린팅은 봇 완화 도구 중 하나의 신호일 뿐, 단독으로 사용하면 안 된다. 운영에서 반드시 고려해야 할 한계가 있다.

**핑거프린트 가변성**: 클라이언트의 TLS 라이브러리가 업데이트되면 핑거프린트가 변한다. Chrome, Firefox 등 주요 브라우저는 대략 연 1회 TLS 스택을 업데이트하며, 이때 cipher나 extension 구성이 바뀌어 새 핑거프린트가 생성된다. 핑거프린트를 정적 블록리스트로 관리한다면 주기적인 갱신이 필요하다.

**Session Resumption**: TLS 세션 재개(session resumption, session ticket)를 사용하는 연결에서는 두 번째 요청부터 Client Hello가 생략된다. 이 경우 핑거프린트가 계산되지 않아 WAF rule에서 빈 값으로 처리된다. Cloudflare 문서에서도 session resumption 시 fingerprint가 absent됨을 명시하고 있다.

**비암호화 트래픽**: HTTP(평문) 연결에서는 TLS 핸드셰이크 자체가 없으므로 핑거프린트가 존재하지 않는다. HTTPS 리다이렉트 전의 첫 요청이나 HTTP-to-HTTPS 업그레이드 시나리오에서는 주의가 필요하다.

**정상 트래픽과의 중복**: cURL, Python requests, Go net/http 같은 정상적인 프로그래밍 도구와 봇 도구가 같은 TLS 라이브러리를 사용하면 동일한 핑거프린트를 갖는다. 핑거프린트가 같다고 해서 무조건 봇으로 차단하면 정상 사용자의 API 클라이언트나 모니터링 도구도 차단된다.

**uTLS 등 위조 기법**: 정교한 봇은 실제 브라우저의 Client Hello를 모방하는 uTLS 라이브러리를 사용해 핑거프린트를 위조할 수 있다. 이 경우 브라우저와 동일한 핑거프린트를 가지므로 JA4만으로 구별이 불가능하다.

이러한 한계 때문에 JA4는 rate limit, JS Challenge, behavioral 분석과 조합해 사용해야 한다. 핑거프린트는 하나의 신호(signal)이며, 단독으로 봇 여부를 판단하는 판정 기준이 아니다.

---

## 8. 분석 도구

JA4 핑거프린트를 직접 관찰하려면 다음 도구를 사용할 수 있다.

| 도구 | 지원 범위 | 설치 |
| :--- | :--- | :--- |
| Wireshark | JA4+ 전체 (JA4, JA4S, JA4H, JA4L, JA4X, JA4SSH, JA4T) | Wireshark 4.4.0+, FoxIO plugin |
| Zeek | JA4+ 전체 | Zeek 5+ (`zkg install zeek/foxio/ja4`), QUIC은 6+ |
| Arkime | JA4+ | 기본 지원 |
| tshark | JA4+ | Wireshark CLI, `tshark -T fields -e tls.handshake.ja4` |
| GreyNoise | JA4+ | threat intelligence 플랫폼 |
| Censys | JA4+ | 인터넷 스캔 데이터 |

FoxIO는 앱별 핑거프린트 데이터베이스인 JA4DB(ja4db.com)를 운영한다. 관측한 핑거프린트가 어떤 클라이언트 소프트웨어에 해당하는지 조회할 수 있다.

---

## 9. 정리: 다층 봇 완화 전략에서 JA4의 위치

봇 완화는 단일 기법으로 완료되는 문제가 아니다. IP rate limit, managed rules, JA4 fingerprint, JavaScript Challenge, CAPTCHA 각각이 서로 다른 계층에서 서로 다른 신호를 사용한다. JA4는 그중 TLS 핸드셰이크를 기반으로 클라이언트 소프트웨어의 정체를 식별하는 계층이다.

AWS WAF에서 JA4를 도입할 때 권장하는 접근은 차단부터 시작하지 않고 관찰부터 하는 것이다. WAF rule action을 `Count`로 설정해 며칠간 JA4 fingerprint 로그를 수집하고, 정상 트래픽의 핑거프린트 분포를 파악한 뒤 이상 패턴을 식별한다. 그 후 의심 핑거프린트에 대해서만 rate-based rule이나 challenge action을 적용한다.

핑거프린트는 클라이언트 소프트웨어가 업데이트되면 변하므로, 블록리스트를 만들었다면 정기적으로 갱신해야 한다. Session resumption, HTTP 평문 트래픽, uTLS 위조 등 핑거프린트가 계산되지 않거나 위조되는 시나리오를 WAF rule에 명시적으로 처리하는 것도 잊지 않아야 한다.

---

## 10. Reference

- [FoxIO JA4+ GitHub Repository](https://github.com/FoxIO-LLC/ja4)
- [FoxIO JA4 Technical Specification](https://github.com/FoxIO-LLC/ja4/blob/main/technical_details/JA4.md)
- [FoxIO JA4+ Suite Overview](https://github.com/FoxIO-LLC/ja4/blob/main/technical_details/README.md)
- [FoxIO JA4H HTTP Fingerprint Specification](https://github.com/FoxIO-LLC/ja4/blob/main/technical_details/JA4H.md)
- [FoxIO License FAQ (JA4=BSD, JA4+=FoxIO License 1.1)](https://github.com/FoxIO-LLC/ja4/blob/main/License%20FAQ.md)
- [JA4DB - JA4+ Fingerprint Database](https://ja4db.com/)
- [Salesforce JA3 Original Repository (archived)](https://github.com/salesforce/ja3)
- [Salesforce Engineering - TLS Fingerprinting with JA3 and JA3S](https://engineering.salesforce.com/tls-fingerprinting-with-ja3-and-ja3s-247362855967)
- [AWS WAF JA4 Fingerprinting and Rate-Based Rules (2025-03)](https://aws.amazon.com/about-aws/whats-new/2025/03/aws-waf-ja4-fingerprinting-aggregation-ja3-ja4-fingerprints-rate-based-rules/)
- [Amazon CloudFront JA4 Fingerprinting (2024-10)](https://aws.amazon.com/about-aws/whats-new/2024/10/amazon-cloudfront-ja4-fingerprinting/)
- [AWS WAF JA3 Fingerprint Match (2023-09)](https://aws.amazon.com/about-aws/whats-new/2023/09/aws-waf-ja3-fingerprint-match/)
- [AWS WAF Developer Guide - Request Components (JA3/JA4 fingerprint)](https://docs.aws.amazon.com/waf/latest/developerguide/waf-rule-statement-fields.html)
- [Cloudflare JA3/JA4 Fingerprint Documentation](https://developers.cloudflare.com/bots/additional-configurations/ja3-ja4-fingerprint/)
- [Cloudflare Blog - JA4 Signals](https://blog.cloudflare.com/ja4-signals/)
- [Google Cloud Armor Rules Language Reference](https://cloud.google.com/armor/docs/rules-language-reference)
- [FoxIO JA4 Wireshark Plugin](https://github.com/FoxIO-LLC/ja4/tree/main/wireshark)
- [FoxIO JA4 Zeek Package](https://github.com/FoxIO-LLC/ja4/tree/main/zeek)
- [FoxIO NGINX JA4 Module (dev paused)](https://github.com/FoxIO-LLC/ja4-nginx-module)
- [HAProxy JA4 Lua Plugin by OXL](https://github.com/O-X-L/haproxy-ja4-fingerprint)
- [Suricata JA Keywords Documentation](https://docs.suricata.io/en/latest/rules/ja-keywords.html)

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
