---
title: "체인 비교와 장애 런북 - 계층 대조, commitment [Blockchain 16]"
date: 2026-08-21 01:07:00 +0900
author: kkamji
categories: [Blockchain]
tags: [blockchain, runbook, commitment, solana, ethereum, bitcoin, study]
comments: true
image:
  path: /assets/img/blockchain/blockchain.webp
---

새 체인 공지를 받으면 토큰 이름보다 먼저 물을 것이 있습니다. 머리는 어떤 객체인가, 실행은 어디에 있는가, 그 답을 어느 RPC가 주고 있는가. 이 글은 Solana 노드를 띄우지 않습니다. Solana 공식 RPC 문서의 commitment와, 이 시리즈가 이미 관측한 Bitcoin/Ethereum 실패를 같은 검사 순서로 맞춥니다.

[이전 글](https://kkamji.net/posts/compiler-pin-repro-build/)에서 같은 소스가 컴파일러만 달라도 다른 프로그램이 됨을 봤습니다. 런북의 마지막 칸이 그 해시입니다.

---

## 1. 머리의 이름이 다르다

Bitcoin Core regtest에서 confirmation은 활성 팁까지의 깊이였습니다. invalid 팁 112는 남아 있어도 그 안의 거래 확인은 0이었습니다.

Ethereum 공개 Sepolia는 `latest`, `safe`, `finalized`를 줬습니다. 같은 날 간격이 33에서 88 사이로 움직였습니다. `finalized`는 two-thirds checkpoint입니다.

Solana RPC 문서는 commitment를 세 단계로 적습니다. `processed`는 노드가 가장 최근에 처리한 block이고 롤백될 수 있습니다. `confirmed`는 활성 stake의 2/3 초과가 직접 투표한 block입니다. `finalized`는 cluster가 maximum lockout으로 인정한, 그 네트워크가 쓰는 가장 강한 확인입니다. 인자를 생략하면 기본값은 보통 `finalized`입니다.

![Bitcoin confirmation, Ethereum tag, Solana commitment가 나란히 놓인 구조](/assets/img/blockchain/commitment-tag-compare.webp)
_세 이름이 같은 시계가 아니다. 각각 다른 객체다._

운영자가 하면 안 되는 번역은 “confirmation 1 = finalized = confirmed”입니다. 입금 정책은 체인마다 다른 필드를 고르고, 그 필드가 무엇을 센 값인지 적어야 합니다.

---

## 2. 실행 계층은 비어 있을 수 있다

Bitcoin을 먼저 본 이유는 실행이 Script로 얇아서 합의와 데이터 모델을 분리하기 쉽기 때문입니다. Ethereum은 Account와 EVM이 그 위에 있습니다. Solana는 이 랩에서 실행 계층을 열지 않았습니다. program/account 모델을 숫자 없이 일반화하지 않습니다.

개발 체인도 계층입니다. Anvil은 chainId 31337에 builder와 peer가 없었습니다. regtest는 피어 없이 mempool을 가졌습니다. 그 환경에서 통과한 테스트를 공개망 순서로 읽으면 안 됩니다.

---

## 3. 장애는 이 순서로 본다

시리즈가 남긴 검사는 아래 사다리입니다. 새 도구가 아닙니다.

1. HTTP 200인가, JSON-RPC `error`인가. Anvil은 peer 메서드에 200과 `-32601`을 같이 줬습니다.
2. receipt `status`인가, estimate revert인가. `NotBuyer`와 `boom`은 체인을 갱신하지 않았습니다.
3. 어느 tip 또는 tag인가. invalid 112와 `finalized` 지연은 다른 실패입니다.
4. 어느 RPC인가. 같은 키의 balance가 8545, 8547, Sepolia에서 갈라졌습니다.
5. bytecode 해시가 pin과 같은가. solc 0.8.35와 0.8.28은 길이 5234로 다른 sha256을 만들었습니다.
6. 그 키가 공개 니모닉인가. Anvil 12단어의 index 0은 누구나 다시 계산합니다.

![HTTP에서 시작해 receipt, tip, RPC, 해시, 키로 내려가는 점검 사다리](/assets/img/blockchain/incident-runbook-ladder.webp)
_한 칸이 통과해도 다음 칸이 실패할 수 있다. Anvil은 아래 칸 여러 개를 생략한다._

---

## 4. 정리

체인을 비교하는 단위는 코인이 아니라 계층입니다. 머리 객체, 실행 유무, 개발 체인이 숨기는 시장, 그리고 그 답을 주는 RPC가 검사 항목입니다. Solana의 `processed`/`confirmed`/`finalized`는 Ethereum tag와 이름이 비슷하고 정의는 문서가 따로 적습니다. 이 시리즈의 런북은 그 정의를 외우기 전에, 이미 관측한 여섯 칸을 같은 순서로 다시 묻는 일입니다.

---

## 5. Reference

- [Solana Docs - RPC](https://solana.com/docs/rpc)
- [Ethereum Docs - Proof-of-stake](https://ethereum.org/en/developers/docs/consensus-mechanisms/pos/)
- [Bitcoin Developer Guide - Block Chain](https://developer.bitcoin.org/devguide/block_chain.html)

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
