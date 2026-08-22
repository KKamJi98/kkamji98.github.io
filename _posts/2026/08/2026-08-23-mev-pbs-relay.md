---
title: "MEV와 블록 빌드 기초 - searcher, PBS, relay [Blockchain 14]"
date: 2026-08-23 05:53:00 +0900
author: kkamji
categories: [Blockchain]
tags: [blockchain, mev, pbs, relay, searcher, anvil, study]
comments: true
image:
  path: /assets/img/blockchain/blockchain.webp
---

공개 mempool에 들어간 거래는 아직 block이 아닙니다. 그 거래를 누가 어떤 순서로 묶는지가 한 칸의 가치가 됩니다. ethereum.org는 그 가치를 Maximal extractable value, MEV라고 부릅니다.

[이전 글](https://kkamji.net/posts/bridge-oracle-trust/)에서 RPC 잔액이 node마다 다름을 봤습니다. 이번에는 같은 체인 안에서, 아직 확정되지 않은 거래 목록을 누가 조립하는지를 봅니다. 봇을 돌리거나 다른 사람의 거래를 복사하지 않았습니다.

---

## 1. Anvil에는 이 시장이 없다

로컬 Anvil 8547을 읽었습니다. `txpool_status`는 `pending 0`, `queued 0`이었습니다. latest block의 `miner`는 `0x000...000`이고, 거래는 1건이었습니다. builder API도, relay도, MEV-Boost도 없습니다.

![로컬 송신이 Anvil을 거쳐 miner가 0인 block이 되는 흐름](/assets/img/blockchain/anvil-no-pbs.webp)
_개발 체인은 보낸 순서에 가깝게 한 프로세스가 바로 캔다. 경매가 없다._

이 관측이 중요한 이유는, 테스트에서 본 포함 순서를 공개망 순서로 옮기면 안 되기 때문입니다. Anvil의 receipt는 실행 결과입니다. 공개망의 포함 순서는 다른 주체가 팝니다.

---

## 2. searcher와 공개 mempool은 다른 층이다

ethereum.org는 MEV를 찾는 독립 참가자를 searcher라고 적습니다. searcher는 체인 데이터를 보고 수익이 되는 묶음을 찾아 제출합니다. 같은 문서는 공개 mempool을 지켜보다가 이득이 될 거래를 가로채려는 generalized frontrunner와, 서로 포함되려고 gas를 올리는 gas-price auction을 네트워크 계층의 혼잡으로 설명합니다.

그 경매를 온체인에서 하면 일반 사용자의 gas가 같이 올라갑니다. 문서가 적는 대응은 공개 mempool을 우회하는 경로입니다. Flashbots 계열 relay는 bundle을 검증한 뒤 proposer에게 넘기고, 그 과정에서 공개 mempool에 내용을 먼저 뿌리지 않습니다. 이 글은 그 경로를 재현하지 않습니다. 운영자가 알아야 하는 것은, 공개 RPC로 보낸 거래가 곧 비공개 bundle이 아니라는 점입니다.

---

## 3. PBS는 만드는 쪽과 제안하는 쪽을 가른다

ethereum.org는 proof-of-work와 proof-of-stake 모두에서, block을 만드는 노드가 그 block을 제안한다고 적습니다. 그 결합이 MEV 관련 유인의 상당 부분을 만든다고 같은 문서가 말합니다. Proposer-Builder Separation, PBS는 그 두 역할을 나눕니다.

validator는 여전히 block을 제안하고 투표합니다. payload를 조립하는 쪽은 builder입니다. searcher의 bundle은 builder로 들어가고, proposer는 완성된 payload를 받아 체인에 올립니다.

![searcher bundle이 builder payload를 거쳐 proposer가 제안하는 흐름](/assets/img/blockchain/pbs-builder-proposer.webp)
_실행 순서를 정하는 주체와, 그 block에 투표하는 주체가 갈라진다._

인덱서와 입금 확인은 이 경로의 바깥에 있습니다. builder가 순서를 바꾼 뒤의 receipt를 “사용자가 보낸 순서”로 저장하면, 운영 로그와 체인 로그가 어긋납니다. Anvil에서는 그 어긋남이 거의 보이지 않습니다.

---

## 4. 정리

MEV는 봇 이름이 아니라, 미포함 거래를 누가 어떤 순서로 block에 넣는가 하는 인프라 문제입니다. Anvil은 그 시장이 없어서 `miner`가 0입니다. 공개망에서는 searcher, relay, builder, proposer가 층을 나눕니다. PBS는 만드는 쪽과 제안하는 쪽을 갈라 합의 노드가 모든 순서를 혼자 정하지 않게 하려는 설계입니다.

---

## 5. Reference

- [Ethereum Docs - Maximal extractable value (MEV)](https://ethereum.org/en/developers/docs/mev/)

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
