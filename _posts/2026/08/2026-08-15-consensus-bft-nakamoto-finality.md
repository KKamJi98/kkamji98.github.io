---
title: "분산 합의 기초 - BFT, Nakamoto, finality [Blockchain 10]"
date: 2026-08-15 04:18:00 +0900
author: kkamji
categories: [Blockchain]
tags: [blockchain, consensus, bft, nakamoto, finality, pos, study]
comments: true
image:
  path: /assets/img/blockchain/blockchain.webp
---

indexer가 `confirmations >= 1`을 보면 입금을 끝낸 것처럼 움직입니다. 같은 숫자를 Bitcoin node와 Ethereum node에 물으면, 돌아오는 객체가 다릅니다. 하나는 지금 활성 팁까지의 깊이이고, 다른 하나는 checkpoint 투표가 만든 finalized 높이입니다.

[이전 글](https://kkamji.net/posts/escrow-auth-events/)에서 권한과 event로 이더를 잠갔습니다. 그 잠금이 어느 머리에 붙는지는 합의가 정합니다. 수식 증명을 나열하지 않습니다. 운영자가 만나는 실패 모양만 로컬 Bitcoin 팁과 Sepolia tag, 그리고 ethereum.org의 PoS 문서로 고정합니다.

---

## 1. confirmation은 활성 팁을 센 값이다

Bitcoin Core 31.1 regtest에서 `getchaintips`를 다시 읽었습니다. W3에서 `invalidateblock`으로 만든 분기가 아직 남아 있습니다.

```text
active    height=114  branchlen=0
invalid   height=112  branchlen=1
```

invalid 팁에 들어 있던 거래의 confirmation은 0입니다. 그 거래가 사라지지 않았습니다. 이 node가 따르는 활성 체인 조상에 없을 뿐입니다. Nakamoto 합의에서 정본은 더 많은 작업을 쌓은 쪽이고, 짧은 쪽의 확인은 철회됩니다.

실무의 6 confirmation 관행은 이 깊이를 확률적으로 키우는 운영 규칙입니다. 이번 랩은 로컬 1-block 무효화입니다. 메인넷의 6 confirmation을 여기서 재현한 것은 아닙니다.

---

## 2. finalized는 다른 질문이다

Ethereum proof-of-stake에서 시간은 slot 12초, epoch 32 slot입니다. ethereum.org는 checkpoint 쌍이 전체 stake의 two-thirds 투표를 받으면, 더 최근 target이 justified가 되고 이전 checkpoint가 finalized가 된다고 적습니다. 거래가 finalized 체인에 들어가면, 그 상태를 되돌리려면 다수의 staker가 slashing을 감수해야 한다고 같은 문서가 말합니다.

공개 Sepolia endpoint를 2026-08-23 05:26 KST에 읽었습니다.

```text
latest      11545353
safe        11545310    (latest - 43)
finalized   11545279    (latest - 74)
```

같은 URL을 같은 날 이미 세 번 읽었습니다. 간격은 33/64, 56/88, 33/64였고, 이번에는 43/74입니다. 상수가 아닙니다.

![regtest의 invalid 팁과 Sepolia finalized tag는 다른 머리를 가리킨다](/assets/img/blockchain/nakamoto-vs-pos-heads.webp)
_Bitcoin confirmation은 활성 팁까지의 깊이다. finalized는 two-thirds checkpoint다._

두 그림을 한 질문에 넣으면 사고가 납니다. Bitcoin explorer의 confirmation 1과 Ethereum의 `finalized`를 같은 “확정”으로 번역하면, reorg 창과 checkpoint 창을 같은 타이머로 취급하게 됩니다.

---

## 3. finalize가 멈추면 체인은 투표를 말린다

ethereum.org는 체인이 네 epoch보다 길게 finalize하지 못하면 inactivity leak이 켜진다고 적습니다. 투표를 못 하는 stake의 잔액이 줄어듭니다. 목적은 남은 활성 validator의 비율을 다시 two-thirds 위로 올리는 것입니다.

운영 화면에서는 이렇게 보입니다. `eth_syncing`은 `false`일 수 있고 HTTP는 200입니다. 그런데 `latest`와 `finalized` 간격이 평소보다 벌어지고, 그 상태가 epoch 단위로 유지됩니다. 이전 글의 운영 사다리에서 tag 칸이 실패한 것과 같습니다. 그 실패의 합의 쪽 이름이 inactivity leak입니다.

![checkpoint 투표가 two-thirds를 못 채우면 finalized가 멈추고 네 epoch 뒤 leak이 켜진다](/assets/img/blockchain/pos-inactivity-leak.webp)
_이번 Sepolia 조회는 leak 구간이 아니다. 문서는 4 epoch 규칙을 적는다._

이번 스냅샷의 74 block 간격은 leak을 관측한 값이 아닙니다. 공개 RPC 한 곳의 지연과 빈 slot이 섞인 숫자입니다. leak 자체를 로컬에서 재현하지 않았습니다.

---

## 4. 고전 BFT는 두 번째 commit 대신 멈춘다

Stanford CS 251과 Shi의 합의 교재는 Bitcoin 앞에 Byzantine broadcast와 state machine replication을 둡니다. 고전 BFT 계열은 충돌하는 두 commit을 동시에 인정하지 않는 쪽으로 안전성을 잡습니다. 정족수가 안 모이면 새 commit이 나오지 않습니다. 운영자에게는 “체인이 갈라졌다”가 아니라 “높이가 멈췄다”로 보입니다.

이 문단은 클러스터를 띄운 관측이 아닙니다. 로컬에 Tendermint나 Istanbul BFT를 올리지 않았습니다. 가져갈 운영 문장만 고정합니다. Nakamoto는 팁이 둘 생기고, Gasper는 finalized가 늦어지며, 고전 BFT는 진행이 멈춥니다. 같은 “합의 장애”라도 runbook의 첫 검사가 다릅니다.

---

## 5. 정리

합의 이름을 외우는 것보다, 실패했을 때 어떤 객체가 움직이는지를 먼저 봅니다. Bitcoin regtest는 active 114와 invalid 112를 동시에 들고 있고, confirmation은 활성 팁 기준입니다. Sepolia의 `finalized`는 two-thirds checkpoint이고, 같은 날 간격이 33에서 88 사이로 움직였습니다. finalize가 오래 멈추면 ethereum.org가 적는 inactivity leak이 켜집니다. 고전 BFT는 그 자리에서 두 이력을 만들기보다 높이를 멈춥니다.

---

## 6. Reference

- [Ethereum Docs - Proof-of-stake](https://ethereum.org/en/developers/docs/consensus-mechanisms/pos/)
- [Bitcoin Developer Guide - Block Chain](https://developer.bitcoin.org/devguide/block_chain.html)
- [Stanford CS 251](https://cs251.stanford.edu/)
- [Shi - Foundations of Distributed Consensus and Blockchains](https://elaineshi.com/docs/blockchain-book.pdf)

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
