---
title: Kubernetes 환경에서 TLS 인증서 적용하기 - (1)
date: 2024-10-19 23:44:21 +0900
author: kkamji
categories: [Kubernetes]
tags: [kubernetes, harbor, jenkins, tls, ssl, cert-manager, ingress-controller]     # TAG names should always be lowercase
comments: true
image:
  path: /assets/img/kubernetes/kubernetes.webp
---

현대 어플리케이션 운영에 있어 보안은 매우 중요합니다. 인터넷을 통한 데이터 전송이 증가함에 따라, 개인 정보와 민감한 데이터가 노출될 위험도 커지고 있습니다. 이러한 위험을 방지하기 위해 데이터 전송 과정에서의 암호화는 필수적입니다. TLS(Transport Layer Security) 인증서의 적용은 이러한 보안을 강화하는 핵심 요소입니다.

TLS는 애플리케이션과 사용자의 통신을 암호화하여 중간자 공격, 도청, 데이터 위변조 등의 위협으로부터 보호합니다. 특히 Kubernetes 환경에서는 다양한 서비스들이 네트워크를 통해 상호 작용하므로, TLS 인증서의 적용이 더욱 필수적입니다.

해당 포스트에서 **TLS**란 무엇인지, **TLS** 인증 과정에 대해 알아보고 다음 글에서는 Kubernetes에서 **TLS 인증서** 관리는 어떻게 하는지, **Nginx Ingress Controller**에 **TLS** 설정은 어떻게 하는지에 대해 다뤄보도록 하겠습니다.

---

## 1. TLS(Transport Layer Security) 개념

**TLS(Transport Layer Security)**란 **SSL(Secure Socket Layer)**의 보안 취약점을 개선하고 더 강력한 암호화 알고리즘을 도입한 후속 버전으로, 인터넷에서 안전한 통신을 제공하기 위한 암호화 프로토콜입니다.

TLS는 클라이언트와 서버 간의 데이터 전송 시 보안을 강화하여 데이터의 **기밀성**, **무결성**, 그리고 **인증**을 제공합니다. 이를 통해 중간자 공격, 도청, 데이터 위변조 등의 보안 위협으로부터 보호할 수 있습니다.

**SSL**은 **POODLE(Padding Oracle On Downgraded Legacy Encryption) Attack**, **Downgrade Attack**, 암호화 및 해시 알고리즘 취약점 문제 등과 같은 보안 취약점으로 인해 더 이상 사용되지 않으며, 현재 TLS가 SSL을 대체하고 있습니다.

---

## 2. TLS 인증 과정

TLS는 클라이언트와 서버 간의 통신 세션을 수립하기 위해 **Handshake** 과정을 거칩니다. 쉬운 이해를 위해 **TLS Handshake** 과정에 대해 이미지를 첨부하겠습니다. 아래 그림과 같습니다.
![tls-handshake](/assets/img/kubernetes/tls-ssl-handshake.png)

<p align="center">
  <a href="https://www.cloudflare.com/ko-kr/learning/ssl/what-happens-in-a-tls-handshake/">
    Cloudflare TLS Handshake 참고자료
  </a>
</p>

1. **Client Hello**

    > 클라이언트가 서버에 연결 요청을 보내 핸드셰이크를 시작
    {: .prompt-tip}

2. **Server Hello**

    > 서버가 클라이언트의 요청에 응답하고 필요한 정보를 전송
    {: .prompt-tip}

3. **서버 인증 및 키 교환 준비**

    > **클라이언트 인증서 검증**
    > - 클라이언트가 서버의 디지털 인증서를 확인하여 서버의 신원을 검증
    > - 인증 기관(CA)을 통해 인증서의 유효성 확인
    > **키 교환 준비(Optional)**
    > - 필요 여부에 따라 키 교환을 위한 추가 정보 전송
    {: .prompt-tip}

4. **클라이언트 키 교환 (Client Key Exchange)**

    > 예비 마스터 시크릿 생성 및 전송
    > - 클라이언트가 예비 마스터 시크릿이라는 무작위 바이트 문자열 생성
    > - 서버의 공개 키로 암호화된 예비 마스터 시크릿 전송
    {: .prompt-tip}

5. **세션 키 생성**

    > 서버에서 예비 마스터 시크릿 복호화
    > - 서버가 소유하고 있는 개인 키로 클라이언트가 보낸 예비 마스터 시크릿 복호화
    > 세션 키 계산
    > - 클라이언트와 서버는 클라이언트 랜덤 값, 서버 랜덤 값, 예비 마스터 시크릿을 사용하여 동일한 세션 키 생성
    {: .prompt-tip}

6. **변경 암호 명령 (Change Cipher Spec)**

    > 암호화 모드 전환
    > - 클라이언트와 서버가 이후 통신에서 사용할 암호화 알고리즘과 세션 키 적용
    > 알림 전송
    > - 클라이언트와 서버가 각각 Change Cipher Spec 메시지를 보내 암호화 설정 변경을 알립니다.
    {: .prompt-tip}

7. **Handshake 완료**

    > 인증 완료 메시지 전송
    > - 클라이언트와 서버가 세션 키로 암호화된 Finished 메시지 교환
    > - Handshake 과정이 성공적으로 완료되었음을 확인
    {: .prompt-tip}

8. **통신 시작**

    > 암호화된 데이터 교환
    > - Handshake가 완료되면, 세션 키를 사용하여 암호화된 데이터를 전송
    > 보안 통신 수립
    > - 클라이언트와 서버 간 안전한 대칭 암호화 통신 시작
    {: .prompt-tip}

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
