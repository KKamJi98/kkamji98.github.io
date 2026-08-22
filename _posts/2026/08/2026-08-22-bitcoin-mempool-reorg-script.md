---
title: "비트코인 시스템 기초 - 멤풀, 리오그, Script [Blockchain 3]"
date: 2026-08-22 01:41:00 +0900
author: kkamji
categories: [Blockchain]
tags: [blockchain, bitcoin, mempool, reorg, script, p2wpkh, regtest, study]
comments: true
image:
  path: /assets/img/blockchain/blockchain.webp
---

탐색기에서 컨펌 1이 뜨면 그 거래는 끝난 것처럼 보입니다. 같은 노드에서 그 블록을 무효화하면 거래는 다시 멤풀로 돌아옵니다. 확인 횟수는 잔액처럼 저장되는 플래그가 아니라, 지금 활성 체인 팁에 그 거래가 들어 있는지를 센 값입니다.

[이전 글](https://kkamji.net/posts/bitcoin-utxo-transactions/)에서 돈은 미사용 출력으로만 존재한다는 점을 확인했습니다. 그 출력이 멤풀에 머무르는 동안, 블록에 들어가는 순간, 그리고 체인이 갈라질 때 어떻게 움직이는지를 Bitcoin Core 31.1 regtest에서 관측합니다. 실습은 로컬 테스트 체인에서만 진행하므로 실제 비용은 발생하지 않습니다.

---

## 1. 거래는 블록보다 멤풀에 먼저 들어간다

지갑이 서명한 거래를 보내는 즉시 잔액이 바뀌는 것이 아닙니다. 노드는 유효성만 검사한 뒤 아직 블록에 넣지 않은 거래 집합, 멤풀에 올려 둡니다. 관측한 거래는 1.25 BTC를 보내는 P2WPKH 출력이었고, 캐기 전에는 `confirmations`가 0이었습니다.

```text
txid   b50a5a25...
conf   0
vsize  141
mempool.size       1
mempool.total_fee  0.0000141 BTC
unbroadcastcount   1
```

이 노드에는 피어가 없습니다. `networkactive`는 true이고 `getpeerinfo`는 빈 배열입니다. 멤풀은 P2P 전파와 별개로, 이 노드가 아직 블록에 넣지 않은 거래를 보관하는 공간입니다. `unbroadcastcount`가 1인 이유는 전달할 이웃이 없기 때문입니다.

---

## 2. 출력은 Script로 잠긴다

멤풀에 올라간 거래의 출력 유형은 `witness_v0_keyhash`였습니다. 기본 지갑 주소 `bcrt1q...`가 가리키는 잠금입니다. scriptPubKey의 asm은 `0`과 20바이트 해시이고, 입력 쪽 `scriptSig`는 비어 있습니다. 서명과 공개키는 `txinwitness`에 있습니다.

```text
vout[0]  1.25 BTC      type=witness_v0_keyhash
vout[1] 47.4999718 BTC type=witness_v0_keyhash   (change)
vin[0].scriptSig       (empty)
vin[0].txinwitness     [signature, pubkey]
```

잠금 스크립트가 곧 그 출력을 쓸 수 있는 조건입니다. 같은 노드에서 `createmultisig 2`를 호출하면 레거시 P2SH 주소 `2Mwmk...`가 나옵니다. 기본 송금 주소와 멀티시그 주소의 형식이 다른 것은 주소가 잔액 상자가 아니라, 어떤 Script를 쓰는지에 대한 짧은 이름이기 때문입니다.

---

## 3. 가벼운 증명은 헤더와 Merkle 경로면 된다

블록 하나를 캐자 같은 거래의 `confirmations`는 1이 되었고, 블록 높이는 112, 거래 수는 2(코인베이스와 우리 거래)였습니다. 이 포함 관계를 전체 블록 없이 검증하는 값이 `gettxoutproof`입니다.

```text
gettxoutproof     151 bytes
verifytxoutproof  [b50a5a25...]
block nTx         2
header.merkleroot 38990380...
```

헤더에는 이전 블록 해시와 Merkle 루트가 들어 있습니다. 증명이 151바이트인 이유는 전체 거래 목록이 아니라 해당 거래가 루트에 연결되는 경로만 담기 때문입니다. 라이트 클라이언트가 전체 체인을 들고 다니지 않아도 포함 여부를 따질 수 있는 지점입니다.

---

## 4. 확인된 거래도 멤풀로 돌아올 수 있다

확인 블록 `20fcf935...`를 `invalidateblock`으로 무효화했습니다. 같은 거래의 `confirmations`는 다시 0이 되었고, 멤풀 크기는 1로 돌아왔습니다. 그 상태에서 블록 두 개를 더 캐면 체인 팁은 이렇게 갈라집니다.

![멤풀의 거래가 블록에 들어갔다가 무효화되면 다시 멤풀로 돌아오고, 이전 팁은 invalid로 남는 흐름](/assets/img/blockchain/bitcoin-mempool-reorg.webp)
_블록 112를 무효화하면 거래는 멤풀로 돌아가고, 새로 캔 체인이 active 팁(높이 113)이 된다. 옛 팁은 invalid로 남는다._

```text
tips:
  active   height=113  branchlen=0  6d72f32e...
  invalid  height=112  branchlen=1  20fcf935...
```

확인은 "이 출력이 영원히 확정됐다"가 아닙니다. 지금 이 노드가 따르는 활성 팁의 조상에 그 거래가 있는지를 센 값입니다. 더 긴 쪽이 정본이 되면 짧은 쪽의 확인은 철회됩니다. 실무에서 여러 컨펌을 기다리는 이유는 이 교체가 깊어질수록 비용이 커지기 때문입니다. 관측한 값은 로컬에서 만든 1블록 무효화이며, 메인넷의 6컨펌 관행을 여기서 재현한 것은 아닙니다.

---

## 5. 정리

비트코인 노드는 거래를 바로 장부에 새기지 않습니다. 먼저 멤풀에 올리고, 블록에 담아 확인 횟수를 만들고, 체인이 갈라지면 그 확인을 되돌릴 수 있습니다. 출력을 잠그는 것은 주소 문자열이 아니라 Script이고, 기본 지갑은 P2WPKH를 씁니다. 포함 여부는 헤더와 Merkle 경로만으로도 검증할 수 있습니다.

이 관측은 피어가 없는 로컬 regtest에서 나왔습니다. 난이도는 `4.656542373906925e-10`이라 퍼즐은 거의 없지만, 멤풀, Script, 증명, 리오그의 규칙은 메인넷과 같습니다. 실제 자산은 움직이지 않았습니다.

---

## 6. Reference

- [Bitcoin Developer Guide - P2P Network](https://developer.bitcoin.org/devguide/p2p_network.html)
- [Bitcoin Developer Guide - Block Chain](https://developer.bitcoin.org/devguide/block_chain.html)
- [Bitcoin Developer Guide - Transactions](https://developer.bitcoin.org/devguide/transactions.html)
- [Mastering Bitcoin - The Bitcoin Network (ch10)](https://github.com/bitcoinbook/bitcoinbook/blob/develop/ch10_network.adoc)
- [Mastering Bitcoin - Mining and Consensus (ch12)](https://github.com/bitcoinbook/bitcoinbook/blob/develop/ch12_mining.adoc)

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
