---
title: DNS 레코드 설정하기 (Route 53)
date: 2024-06-07 08:31:44 +0900
author: kkamji
categories: [Cloud, AWS]
tags: [route53, domain, aws, github-pages, jekyll, blog, kkamji, cname, dns-record]     # TAG names should always be lowercase
comments: true
image:
    path: /assets/img/aws/aws.webp
---

Amazon Route 53에서 DNS record를 만들기 전에, record가 들어갈 hosted zone과 도메인 등록기관의 delegation이 먼저 맞아야 한다. record 하나를 생성해도 등록기관이 해당 hosted zone의 name server를 가리키지 않으면 인터넷 DNS 조회는 그 zone을 사용하지 않는다.

> **TL;DR**  
> - hosted zone은 특정 domain과 그 subdomain의 트래픽을 어디로 보낼지 정의하는 record의 컨테이너다.  
> - public hosted zone은 인터넷 DNS용이고, private hosted zone은 연결한 VPC 안의 DNS용이다.  
> - zone apex에는 CNAME을 만들 수 없다. Route 53 Alias는 일부 AWS 리소스에 한해 apex에서도 사용할 수 있는 Route 53 확장 기능이다.  
{: .prompt-info}

---

## 1. Route 53 hosted zone과 delegation

**Hosted zone**은 domain과 subdomain의 DNS routing 정보를 담는 record의 컨테이너다. Route 53에는 인터넷에서 조회되는 **public hosted zone**과 연결한 Amazon VPC에서 조회되는 **private hosted zone**이 있다. 두 종류는 같은 이름을 가질 수 있어도 조회 범위가 다르므로 만들기 전에 목적을 정해야 한다.

public hosted zone을 만들면 Route 53은 기본 NS(Name Server) record와 SOA(Start of Authority) record를 생성한다. NS record에 있는 name server들이 그 hosted zone의 authoritative name server다. Route 53이 도메인 등록기관이 아닌 경우에는 등록기관 콘솔에서 해당 도메인의 name server를 이 NS 값으로 변경해야 public hosted zone이 인터넷에서 권한을 갖는다.

1. public DNS가 필요한지, VPC 내부 DNS만 필요한지 결정한다.
2. 목적에 맞는 hosted zone을 만들고 기본 NS와 SOA record를 확인한다.
3. public hosted zone이라면 등록기관의 name server delegation을 hosted zone의 NS 값으로 변경한다.
4. delegation이 확인된 뒤에 애플리케이션용 record를 생성하고 응답을 검증한다.

---

## 2. record를 구성하는 항목

| 항목 | 의미 |
| --- | --- |
| Record name | hosted zone 안에서 record가 적용되는 이름 |
| Record type | A, AAAA, CNAME, TXT, MX, NS, SOA 등 DNS 데이터의 형식 |
| Value | type에 맞는 주소, 도메인 이름, 텍스트 등의 값 |
| TTL | recursive resolver가 값을 cache할 수 있는 시간(초) |
| Routing policy | Route 53이 여러 record 중 응답을 선택하는 방식 |

자주 쓰는 type은 다음과 같다.

- **A**: 이름을 IPv4 주소에 연결한다.
- **AAAA**: 이름을 IPv6 주소에 연결한다.
- **CNAME**: 한 이름을 다른 도메인 이름으로 연결한다. CNAME은 zone apex에 만들 수 없고, CNAME이 있는 이름에는 다른 record를 만들 수 없다.
- **TXT**: 도메인 소유 확인, 메일 정책 등 애플리케이션이 해석하는 텍스트를 저장한다.
- **MX**: 메일을 받을 서버를 지정한다.
- **NS**와 **SOA**: zone의 authoritative name server와 권한 정보를 나타낸다. Route 53이 생성한 public hosted zone의 기본 NS와 SOA record는 일반적으로 수정하지 않는다.

**Alias record**는 DNS 표준 record type이 아니라 Route 53의 확장 기능이다. CNAME과 비슷하게 선택한 AWS 리소스로 질의를 보낼 수 있으며, 지원되는 대상에는 zone apex에서도 Alias를 만들 수 있다. 외부 호스팅 서비스의 custom domain 연결에는 그 서비스가 요구하는 최신 A, AAAA, CNAME 또는 TXT 값을 해당 서비스의 공식 문서에서 확인해 사용한다. 과거에 기록한 IP 주소를 복사하는 방식은 대상 서비스의 변경에 취약하다.

---

## 3. 웹 서비스용 record 설정 순서

다음은 `example.com`과 `www.example.com`을 설정하는 일반적인 순서다. 값은 실제 서비스 제공자가 안내한 현재 값을 사용해야 한다.

1. Route 53 콘솔에서 hosted zone을 열고 기존 NS, SOA record를 먼저 확인한다.
2. apex인 `example.com`에는 서비스가 제공한 A 또는 AAAA 값을 만들거나, 대상이 지원되면 Alias를 선택한다. apex CNAME은 만들 수 없다.
3. `www.example.com`에는 서비스가 요구하는 방식으로 A, AAAA, CNAME 또는 Alias를 만든다. CNAME을 선택했다면 같은 이름의 다른 record를 만들지 않는다.
4. domain ownership 검증이 필요하면 서비스가 요구한 TXT 또는 CNAME record를 정확한 name과 value로 추가한다.
5. record의 TTL과 routing policy가 의도한 장애 조치, 가중치, 지리적 라우팅 요구 사항과 맞는지 검토한다. 단일 endpoint에는 단순한 정책이 운영하기 쉽다.

---

## 4. 검증과 변경 시 주의점

DNS 변경은 hosted zone에 저장된 즉시 모든 recursive resolver의 cache에서 바뀌는 것이 아니다. TTL이 만료되기 전에는 이전 응답이 남을 수 있으므로, 배포와 장애 대응에서는 현재 authoritative 응답과 resolver cache 영향을 구분해야 한다.

```bash
# delegation이 Route 53 name server를 가리키는지 확인
dig NS example.com

# authoritative name server에 직접 질의
dig @<route-53-name-server> example.com A +norecurse
dig @<route-53-name-server> www.example.com CNAME +norecurse

# 일반 resolver에서의 최종 응답 확인
dig example.com A
dig www.example.com A
```

검증할 때는 record가 존재하는지만 보지 말고, public/private hosted zone을 혼동하지 않았는지, registrar delegation이 맞는지, CNAME 제약을 지켰는지, HTTPS 인증서의 domain ownership 검증 record가 남아 있는지 함께 확인한다.

---

## 5. Reference

- [AWS Route 53 - Working with hosted zones](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/hosted-zones-working-with.html)
- [AWS Route 53 - NS and SOA records for a public hosted zone](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/SOA-NSrecords.html)
- [AWS Route 53 - Supported DNS record types](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/ResourceRecordTypes.html)
- [AWS Route 53 - Best practices for DNS](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/best-practices-dns.html)

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
