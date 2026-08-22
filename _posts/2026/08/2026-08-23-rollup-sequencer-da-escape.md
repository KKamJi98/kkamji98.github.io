---
title: "롤업과 L2 운영 기초 - sequencer, DA, 탈출창 [Blockchain 12]"
date: 2026-08-23 05:41:00 +0900
author: kkamji
categories: [Blockchain]
tags: [blockchain, l2, rollup, sequencer, da, optimistic, zk, study]
comments: true
image:
  path: /assets/img/blockchain/blockchain.webp
---

L2 explorer의 confirmation 1은 L1의 `finalized`가 아닙니다. 거래를 받은 쪽이 sequencer이고, 그 결과를 Ethereum에 올리는 쪽이 batch이며, 정착 시계는 L1 합의입니다.

[이전 글](https://kkamji.net/posts/hd-wallet-signer-ops/)에서 공개 니모닉을 운영키로 쓰지 않는 이유를 봤습니다. 이번에는 그 키가 붙는 RPC가 한 체인이 아닐 수 있음을 봅니다. 로컬 sequencer는 띄우지 않았습니다. ethereum.org의 optimistic / ZK rollup 문서와, Sepolia L1 tag 한 장만 사용합니다.

---

## 1. sequencer가 순서를 정한다

ethereum.org는 optimistic rollup에서 사용자가 거래를 operator에게 보낸다고 적습니다. 그 operator가 sequencer이면 오프체인에서 실행하고, 여러 거래를 batch로 묶어 L1에 올립니다. ZK-rollup 문서도 같은 역할을 말합니다. 어떤 설계에서는 sequencer만 L2 block을 만들 수 있습니다.

![사용자 거래가 sequencer를 거쳐 L1 batch가 되는 흐름](/assets/img/blockchain/rollup-sequencer-to-l1.webp)
_순서는 sequencer가 정한다. L1에 남는 것은 실행 결과가 아니라 batch다._

운영자가 먼저 물을 질문은 “이 RPC의 `latest`가 누구의 순서인가”입니다. 그 값은 L1 validator 집합의 머리가 아니라, 지금 batch를 만들고 있는 sequencer의 머리일 수 있습니다. 이번 랩은 L2 RPC를 조회하지 않았습니다. 그 차이를 숫자로 교차 검증하지 않았다는 뜻입니다.

---

## 2. DA가 있어야 탈출할 수 있다

optimistic rollup은 거래를 Ethereum에 calldata 또는 blob으로 씁니다. 계산은 L2에서 하고, 데이터는 L1에서 꺼내 볼 수 있어야 합니다. 문서가 적는 공격은 명확합니다. sequencer가 오프라인이거나 특정 거래를 빼면 검열이고, 상태 데이터를 숨기면 사용자가 Merkle proof로 잔고를 증명하지 못합니다.

그래서 탈출 경로는 sequencer RPC가 아닙니다. ethereum.org는 사용자가 거래를 L1에 직접 넣을 수 있다고 적습니다. 그 거래는 별도 inbox에 쌓이고, sequencer는 제한 시간 안에 포함해야 계속 유효한 block을 만들 수 있습니다.

![사용자가 L1 inbox로 제출하면 sequencer가 제한 시간 안에 포함해야 하는 흐름](/assets/img/blockchain/rollup-l1-inbox-escape.webp)
_탈출창의 입구는 L1이다. sequencer RPC가 침묵해도 inbox는 남는다._

데이터를 L1 밖에만 두는 설계는 같은 문서가 rollup과 구분해 적습니다. 그 경우 검증 가능한 탈출에 필요한 입력이 L1에 없을 수 있습니다. 이번 글은 rollup, 즉 데이터를 Ethereum에 쓰는 쪽만 다룹니다.

---

## 3. 정착 시계는 L1 finalized다

optimistic batch가 L1에 올라가면 challenge period가 열립니다. 그 창 안에서 누구나 실행 결과를 재계산해 fraud proof를 넣을 수 있습니다. 창이 지나도록 반박이 없으면 그 batch는 유효로 받아들여집니다. 문서가 고정한 것은 “기간”이지, 모든 체인이 같은 시각 길이를 쓴다는 숫자가 아닙니다. 7일을 여기서 관측하지 않았습니다.

ZK-rollup은 상태 갱신에 validity proof를 붙입니다. 문서의 문장은, L1이 그 증명을 검증하면 되고, L2에서 L1으로 자금을 옮길 때 optimistic 같은 반박 대기 없이 진행할 수 있다는 쪽입니다. 증명을 만드는 비용과 하드웨어는 이 랩에서 재현하지 않았습니다.

정착을 말할 때 봐야 하는 높이는 L2 confirmation이 아니라 L1의 `finalized`입니다. 2026-08-23 05:42 KST에 Sepolia 공개 RPC를 읽으면 `latest 11545427`, `finalized 11545342`였습니다. 간격 85입니다. 이 숫자는 롤업 batch가 아직 challenge 중인지가 아니라, 그 batch가 붙을 L1 머리가 얼마나 굳었는지를 말합니다.

---

## 4. 정리

롤업의 운영 질문은 세 층입니다. 누가 순서를 정하는가(sequencer), 그 순서를 누가 다시 계산할 수 있는가(DA), 그리고 그 결과가 어느 L1 머리에 붙는가(`finalized`). sequencer RPC의 confirmation은 그 세 층을 한 숫자로 압축합니다. 압축을 풀지 않으면 검열과 데이터 은닉과 L1 reorg를 같은 사고로 취급하게 됩니다.

---

## 5. Reference

- [Ethereum Docs - Optimistic rollups](https://ethereum.org/en/developers/docs/scaling/optimistic-rollups/)
- [Ethereum Docs - Zero-knowledge rollups](https://ethereum.org/en/developers/docs/scaling/zk-rollups/)
- [Ethereum Docs - Data availability](https://ethereum.org/en/developers/docs/data-availability/)

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
