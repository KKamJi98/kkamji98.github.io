---
title: TCP & UDP 개념
date: 2023-10-11 21:44:32 +0900
author: kkamji
categories: [Network]
tags: [network, osi, tcp, udp, control flow, congestion control, packet]     # TAG names should always be lowercase
comments: true
# image:
#   path: https://github.com/kkamji98/kkamji98.github.io/assets/72260110/fce002d4-2ca7-4d74-9990-6b3da63d41f5
---

> 전송계층에서 어플리케이션 간 데이터 송수신을 위해 사용하는 프로토콜
{: .prompt-info}
<aside>
🔥 TCP와 UDP는 전송계층에서 애플리케이션 간 데이터 전송 방식을 정리한 규약입니다
두 개의 차이점으로는 TCP는 데이터 송수신 전 상대와 3-way-handsahke를 통해 연결을 설정하고 신뢰성 있는 전송을 보장합니다. 그에반해 UDP는 비연결형 통신으로 상대와의 연결이 수립되어 있지 않아도 데이터를 전송하며 신뢰성 있는 전송기능을 보장하지 않습니다

</aside>

### TCP의 특징 

> TCP - 연속성보다 신뢰성있는 전송이 중요할 때 사용합니다
{: .prompt-tip}
- 신뢰성 있는 데이터 전송을 지원합니다
    - 데이터가 목적지에 순서대로, 에러 없이 도달하도록 합니다
    - 송신자와 수신자 사이에 연결을 설정하고 데이터가 손실되거나 손상될 경우 재전송을 수행합니다
- 연결 지향 방식으로 패킷 교환 방식을 지원합니다
    - 통신을 시작하기 전에 3-way handshaking과정을 통해 연결을 설정하고 4-way handshaking을 통해 해제한다
- 흐름 제어 및 혼잡 제어 기능을 통해 높은 신뢰성을 보장합니다
    - TCP는 네트워크의 혼잡 상황이나 수신 측의 처리 능력을 고려하여 데이터 전송 속도를 조절합니다
- 단점
    - UDP보다 속도가 느립니다
    - 서버와 클라이언트는 1대1로 연결됩니다

### UDP의 특징

> UDP - 신뢰성보다 연속성이 중요한 서비스에 사용합니다
{: .prompt-tip}

- 비연결 지향적
    - 송신자와 수신자 간에 사전 연결을 하지 않습니다
    - 정보를 주고 받을 때 정보를 보내거나 받는다는 신호절차를 거치지 않습니다
    - UDP헤더의 CheckSum 필드를 통해 최소한의 오류만 검출합니다
    - 신뢰성이 낮습니다
- 경량 프로토콜
    - UDP는 TCP보다 헤더가 간단하며 오버헤드가 적습니다
    - TCP 보다 속도가 빠릅니다
- 실시가 통신에 적합
- Connect 개념이 존재 하지 않아 서버 소켓과 클라이언트 소켓의 구분이 없습니다

### 알아보기

- 패킷(Packet)이란?
    - 인터넷 내에서 데이터를 보내기 위한 경로배정(라우팅)을 효율적으로 하기 위해서 데이터를 여러 개의 조객들로 나누어 전송하는 데 이 조각을 패킷이라고 합니다
- 3-way-handshake란?
    - 두 호스트 간의 연결을 시작할 때 사용되는 절차
    - SYN -> SYN-ACK -> ACK 이렇게 총 3개의 단계로 이루어집니다
        1. SYN(Synchronize) 단계
            
            > 클라이언트가 서버에게 연결하고자 하는 의사를 알림
            {: .prompt-tip}
            
            
            - 클라이언트는 서버에게 SYN 플래그가 설정된 연결 요청 메시지를 보냅니다
            - 클라이언트는 자신의 초기 시퀀스 번호(ISN)를 임의로 설정하여 전송합니다
        2. SYN-ACK(Synchronize-Acknowlegement) 단계
            
            > 서버가 클라이언트의 SYN 요청을 확인(ACK)하고, 자신의 SYN 요청을 함께 보내 양방향 연결의 준비가 되었음을 알림
            {: .prompt-tip}
                
            
            - 서버는 크라이언트의 연결 요청을 받고, 연결을 수락할 준비가 되었다는 의미로 SYN-ACK 메시지를 클라리언트에게 보냅니다
            - 이 메시지에는 서버의 초기 시퀀스 번호와 클라이언트 시퀀스 번호에 1을 더한 값(ACK 번호)가 포함됩니다
        3. ACK(Acknowlegement) 단계
            
            > 연결 수립 -> 클라이언트가 서버의 SYN 요청을 확인하고, 연결이 성립
            {: .prompt-tip}

            
            - 클라이언트는 서버로부터 SYN-ACK 메시지를 받은 후, 서버의 SYN 요청을 확인하는 ACK 메시지를 보냅니다. 이때 ACK 번호는 서버의 시퀀스 번호에 1을 더한 값입니다
- 흐름제어(Flow Control)와 혼잡제어(Congestion Control)
    - 흐름제어
        - 데이터를 송신하는 곳과 수신하는 곳의 데이터 처리 속도를 조절하여 수신자의 버퍼 오버플로우를 방지합니다
    - 혼잡제어
        - 네트워크 내의 패킷 수가 넘치게 증가하지 않도록 방지합니다
        - 정보의 소통량이 과다하다면 패킷 전송량을 줄여 혼잡 붕괴 현상이 일어나는 것을 막습니다

<br><br>

> **궁금하신 점이나 추가해야할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKam.\_\.Ji](https://www.linkedin.com/in/taejikim/)**
{: .prompt-info}