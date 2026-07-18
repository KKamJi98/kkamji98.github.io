---
title: AWS에서 도메인 구매하기 (Route53)
date: 2024-06-06 21:33:31 +0900
author: kkamji
categories: [Cloud, AWS]
tags: [route53, domain, aws]     # TAG names should always be lowercase
comments: true
content_kind: announcement
image:
    path: /assets/img/aws/aws.webp
---

GitHub 아이디를 변경하면서 블로그 주소도 `war-oxi.github.io`에서 `kkamji.net`으로 바꾸게 되었습니다. 이 글은 당시 Route 53에서 개인 도메인을 등록한 기록을 현재 console 흐름과 함께 다시 정리한 것입니다. 도메인 등록은 주소의 소유권을 얻는 단계이며, GitHub Pages 연결과 HTTPS 설정은 별도의 후속 작업입니다.

> **TL;DR**  
> - Route 53에서 도메인을 등록하면 해당 도메인의 public hosted zone도 자동으로 만들어집니다.  
> - 등록 기간, 자동 갱신, 등록자 연락처, WHOIS privacy와 등록자 email 검증을 결제 전에 확인합니다.  
> - 도메인 등록과 DNS record 생성은 다른 단계입니다. 등록이 완료된 뒤 hosted zone의 name server와 필요한 record를 확인합니다.  
{: .prompt-info}

---

## 1. 등록 전에 정할 것

도메인은 등록 뒤 이름을 수정하거나 잘못 등록한 비용을 환불받을 수 없습니다. 원하는 이름과 TLD를 먼저 확정하고, 등록 가격과 갱신 가격, 소유할 AWS account, 등록자 연락처를 함께 확인합니다. 등록자 contact는 domain의 Registered Name Holder 권리에 영향을 주므로 개인 도메인이라도 실제로 관리할 수 있는 정보를 입력해야 합니다.

자동 갱신은 만료로 인한 서비스 중단을 줄이지만, 갱신 후에는 환불받을 수 없습니다. 장기간 유지할 도메인이라면 자동 갱신을 켜고, 결제 수단과 만료 알림을 정기적으로 점검하는 편이 안전합니다. TLD마다 지원되는 privacy protection과 추가 등록 정보가 다를 수 있으므로 checkout 화면의 요구사항을 그대로 확인합니다.

```text
domain search
    |
registration and registrant contact
    |
Route 53 registered domain + public hosted zone
    |
name server and DNS records
    |
blog hosting configuration
```

---

## 2. Route 53에서 도메인 등록하기

1. Route 53 console에서 **Domains > Registered domains**로 이동한 뒤 **Register domains**를 선택합니다.
   ![Route 53 Registered domains 화면](https://github.com/KKamJi98/kkamji98.github.io/assets/72260110/128de451-b3d6-4dd9-8a92-d5bc5a3720fc)
2. 등록하려는 도메인을 검색합니다. 여기서는 `kkamji.net`을 선택했습니다. 이미 등록된 이름이면 비슷한 이름이 제안되더라도, 기억하기 쉽고 오입력 가능성이 낮은 이름인지 다시 확인합니다.
   ![Route 53 domain search 결과](https://github.com/KKamJi98/kkamji98.github.io/assets/72260110/25ce37fa-32ec-4d3a-9d04-9cf209cb9cbb)
3. checkout에서 등록 기간과 자동 갱신 여부를 선택합니다. 이어서 registrant, administrative, technical, billing contact를 확인하고, 가능한 TLD에서는 WHOIS privacy protection도 선택합니다.
   ![Route 53 domain registration checkout 화면](https://github.com/KKamJi98/kkamji98.github.io/assets/72260110/3b4b2fd8-cb26-4a78-9a98-c910962a710f)
4. 약관과 최종 가격을 검토한 후 submit합니다. request가 바로 완료되지 않을 수 있으므로 **Domains > Requests**에서 상태와 registrant email verification 요청을 확인합니다.

---

## 3. 등록 후 확인할 것

Route 53에 새 도메인을 등록하면 public hosted zone이 자동으로 생성됩니다. 이 hosted zone에는 DNS query 비용이 별도로 발생할 수 있으므로, 당장 사용하지 않을 도메인이라면 hosted zone을 유지할 이유가 있는지 판단합니다. 반대로 hosted zone을 새로 만들었다면 등록된 domain의 name server도 새 hosted zone의 값으로 바꿔야 합니다.

다음 항목을 확인한 뒤에 DNS record를 추가합니다.

| 확인 항목 | 이유 |
| --- | --- |
| Registered domain 상태 | 등록 요청이 완료되었는지 확인합니다. |
| registrant email | 검증 메일을 기한 내 처리하지 않으면 domain이 suspend될 수 있습니다. |
| hosted zone name server | registrar가 가리키는 authoritative name server와 일치해야 합니다. |
| renewal과 contact 정보 | 만료와 연락처 변경에 대비합니다. |

이 글의 다음 단계인 GitHub Pages 연결에서는 hosted zone에 GitHub가 요구하는 DNS record와 custom domain 설정을 추가해야 합니다. 도메인이 등록되었다는 사실만으로 블로그 traffic이 새 주소로 전달되지는 않습니다.

---

## 4. 정리

개인 도메인을 등록할 때는 이름 선택보다 소유권과 갱신 관리가 더 오래 남습니다. Route 53 registration request와 email verification을 완료하고, 자동 생성된 hosted zone과 name server를 확인한 뒤 hosting provider의 DNS 요구사항을 적용하면 도메인 등록과 서비스 연결을 혼동하지 않을 수 있습니다.

---

## 5. Reference

- [AWS Docs - Registering a new domain](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/domain-register.html)
- [AWS Docs - Domains that you can register with Amazon Route 53](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/registrar-tld-list.html)
- [AWS Docs - Enabling or disabling privacy protection for contact information](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/domain-privacy-protection.html)

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
