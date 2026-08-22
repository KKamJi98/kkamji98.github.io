---
title: "브리지와 오라클 기초 - 신뢰경계, DA [Blockchain 13]"
date: 2026-08-23 05:47:00 +0900
author: kkamji
categories: [Blockchain]
tags: [blockchain, bridge, oracle, trust, rpc, study]
comments: true
image:
  path: /assets/img/blockchain/blockchain.webp
---

탐색기 한 칸의 balance는 그 사이트가 고른 node의 답입니다. 같은 address를 다른 RPC에 물으면 숫자가 갈라집니다. 브리지가 그 숫자 하나를 다른 체인에 mint하면, 옮기는 것은 자산이 아니라 그 node를 믿겠다는 결정입니다.

[이전 글](https://kkamji.net/posts/rollup-sequencer-da-escape/)에서 sequencer RPC의 confirmation이 L1 `finalized`가 아님을 봤습니다. 이번에는 체인 사이, 그리고 체인 밖으로 숫자가 건너갈 때 누가 그 숫자를 보증하는지를 봅니다. 브리지를 직접 배포하지 않았습니다.

---

## 1. 같은 address의 balance는 node마다 다르다

Anvil 기본 계정 `0xf39Fd6e5...`는 공개 테스트 키입니다. 2026-08-23에 같은 `eth_getBalance`를 세 endpoint에 보냈습니다. `chainId` 31337인 로컬 프로세스 두 개와 Sepolia 공개 RPC입니다.

```text
Anvil :8545   chainId 31337  latest 5  balance 9998999704446202059432
Anvil :8547   chainId 31337  latest 3  balance 9998999219286062346196
Sepolia RPC   chainId 11155111         balance 0
```

![한 EOA를 세 node에 물으면 balance가 세 갈래로 갈라지는 구조](/assets/img/blockchain/rpc-balance-is-local.webp)
_같은 키다. 각 RPC는 자기 상태 트리만 읽는다._

두 Anvil은 둘 다 개발 체인이고 둘 다 31337입니다. 그래도 latest와 잔액이 다릅니다. 프로세스가 다르기 때문입니다. Sepolia에서 이 키의 잔액은 0입니다. 로컬 숫자를 보고 “이 계정에 만 ETH가 있다”고 쓰면, 그 문장은 그 node 밖에서는 거짓입니다.

---

## 2. lock-and-mint는 숫자를 복사한다

ethereum.org는 자산 이동을 세 가지로 나눕니다. lock-and-mint, burn-and-mint, atomic swap입니다. lock-and-mint는 출발 체인에서 자산을 잠그고 도착 체인에서 새 자산을 찍습니다. 도착 체인의 토큰은 출발 체인의 잠금을 누군가가 봤다는 증표입니다.

그 누군가를 문서는 trusted와 trustless로 나눕니다. trusted 브리지는 외부 verifier입니다. 멀티시그 연합, MPC, oracle network가 그 예입니다. trustless 브리지는 연결하는 체인의 validator 외에 새 신뢰 가정을 더하지 않는다고 적습니다. 이름이 신뢰를 없앤다는 뜻이 아니라, 추가 가정을 더하지 않는다는 뜻입니다.

![출발 체인 lock이 verifier를 거쳐 도착 체인 mint가 되는 흐름](/assets/img/blockchain/lock-and-mint-trust.webp)
_mint의 진실은 lock이 아니라, lock을 봤다고 주장하는 verifier다._

운영 사고는 탐색기 잔액을 verifier 입력으로 쓰는 순간에 납니다. 1절의 8545 숫자를 보고 다른 체인에 mint하면, 그 mint는 8545 프로세스의 상태를 담보로 합니다. 프로세스를 끄면 담보는 사라집니다. 공개망 브리지도 같은 모양입니다. 담보는 출발 체인의 잠금과, 그 잠금을 읽는 집합입니다.

---

## 3. 오라클은 체인 밖 숫자를 넣는다

ethereum.org는 oracle을 오프체인 데이터 소스를 스마트 컨트랙트가 쓰게 만드는 feed로 정의합니다. 이더리움 컨트랙트는 기본적으로 체인 밖 정보에 접근하지 못합니다. 가격, 선거 결과, 날씨는 그 밖에 있습니다.

문서가 적는 oracle problem은 세 질문입니다. 출처가 맞는가, 값이 변조되지 않았는가, 그 값이 계속 갱신되는가. 중앙화 oracle은 한 주체가 feed를 갱신합니다. 효율은 높고, 그 주체가 틀린 숫자를 넣으면 컨트랙트는 틀린 숫자를 진실로 실행합니다.

브리지의 외부 verifier와 오라클은 같은 자리에 있습니다. 둘 다 체인 합의가 보지 못한 사실을 온체인 상태로 바꿉니다. DA가 없는 숫자, 즉 L1에서 다시 계산할 수 없는 입력은 그 verifier의 정직함에 기대는 입력입니다.

---

## 4. 정리

RPC 잔액은 그 node의 답입니다. 같은 키를 8545, 8547, Sepolia에 물으면 세 답이 나옵니다. 브리지의 lock-and-mint는 그중 하나를 다른 체인에 복사하고, 오라클은 체인 밖 숫자를 같은 방식으로 넣습니다. 탐색기 칸을 진실로 쓰지 않는 이유는 그 칸이 합의가 아니라, 그 칸을 채운 endpoint의 상태이기 때문입니다.

---

## 5. Reference

- [Ethereum Docs - Bridges](https://ethereum.org/en/developers/docs/bridges/)
- [Ethereum Docs - Oracles](https://ethereum.org/en/developers/docs/oracles/)

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
