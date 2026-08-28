---
title: "비트코인 시스템 기초 - mempool, reorg, Script [Blockchain 3]"
date: 2026-08-08 05:19:00 +0900
author: kkamji
categories: [Blockchain]
tags: [blockchain, bitcoin, mempool, reorg, script, p2wpkh, regtest, study]
comments: true
image:
  path: /assets/img/blockchain/blockchain.webp
---

explorer에서 confirmation 1이 뜨면 그 거래는 끝난 것처럼 보입니다. 같은 node에서 그 block을 무효화하면 거래는 다시 mempool로 돌아옵니다. 확인 횟수는 balance처럼 저장되는 플래그가 아니라, 지금 활성 체인 팁에 그 거래가 들어 있는지를 센 값입니다.

[이전 글](https://kkamji.net/posts/bitcoin-utxo-transactions/)에서 돈은 미사용 출력으로만 존재한다는 점을 확인했습니다. 그 출력이 mempool에 머무르는 동안, block에 들어가는 순간, 그리고 체인이 갈라질 때 어떻게 움직이는지를 Bitcoin Core 31.1 regtest에서 관측합니다. 실습은 로컬 테스트 체인에서만 진행하므로 실제 비용은 발생하지 않습니다.

---

## 1. 피어가 없어도 mempool은 있다

Bitcoin Core 31.1(`subversion` `/Satoshi:31.1.0/`, `protocolversion` 70016)을 regtest로 띄웠습니다. `networkactive`는 true이고 `connections`는 0이며 `getpeerinfo`는 빈 배열입니다. `localservicesnames`는 `NETWORK`, `WITNESS`, `NETWORK_LIMITED`, `P2P_V2`입니다. P2P 스택은 살아 있고 이웃만 없습니다.

이 시점의 chain은 `regtest`, 높이는 111, `difficulty`는 `4.656542373906925e-10`, `size_on_disk`는 33604바이트였습니다. 빈 mempool은 `loaded=true`, `size=0`, `usage=64`, `maxmempool=300000000`, `fullrbf=true`, `minrelaytxfee=1e-06`이었습니다. mempool은 전파 버퍼가 아닙니다. 이 node가 아직 block에 넣지 않은 거래를 보관하는 공간입니다.

![피어가 없는 node가 wallet 송신을 받아 mempool에 올리는 흐름](/assets/img/blockchain/bitcoin-isolated-mempool.webp)
_wallet이 1.25 BTC를 보내면 이 node가 유효성만 검사한 뒤 mempool에 둔다. 전달할 피어가 없어 unbroadcast가 true다._

---

## 2. 거래는 block보다 mempool에 먼저 들어간다

wallet이 bob address `bcrt1qkdt5xkps9ptcu9ff47yj4r9etmzgzxs3zdfn5n`으로 1.25 BTC를 보냈습니다. 송신 인자는 `fee_rate=10`이었습니다. 캐기 전 거래는 다음이었습니다.

```text
txid     b50a5a254dc489c13c8e259b863e88c0979cfc60f1ff6152b20ce86c8daf327d
wtxid    4888c647e656c910c6a526a0396e82b2286642dfb87a08c2a09fabe5bb034e2c
conf     0
vsize    141
weight   561
vin[0]   13348fcf...:1
sequence 4294967293
vout[0]  1.25 BTC
vout[1]  47.4999718 BTC
mempool.size       1
mempool.bytes      141
mempool.usage      1224
mempool.total_fee  0.0000141 BTC
unbroadcast        true
bip125-replaceable true
entry.height       111
```

fee 0.0000141 BTC는 1410 sat입니다. vsize 141로 나누면 10 sat/vB이고, 송신 때 넣은 `fee_rate=10`과 같습니다. 출력 합 48.7499718에 이 fee를 더하면 입력은 48.7499859 BTC입니다. `minrelaytxfee` 1e-06보다 커서 이 node의 mempool에 들어갔습니다.

`unbroadcastcount`가 1인 이유는 전달할 이웃이 없기 때문입니다. `bip125-replaceable`이 true였지만, 이 실습에서는 교체 거래를 보내지 않았습니다.

---

## 3. 출력은 Script로 잠긴다

mempool에 올라간 거래의 출력 유형은 둘 다 `witness_v0_keyhash`였습니다. 기본 wallet address `bcrt1q...`가 가리키는 잠금입니다. 수신 출력의 scriptPubKey asm은 `0 b35743583028578e1529af892a8cb95ec4811a11`입니다. `0`과 20바이트 hash입니다. 입력 쪽 `scriptSig`는 비어 있습니다. signature와 공개키는 `txinwitness`에 있습니다.

```text
vout[0]  1.25 BTC      type=witness_v0_keyhash
         addr=bcrt1qkdt5xkps9ptcu9ff47yj4r9etmzgzxs3zdfn5n
vout[1] 47.4999718 BTC type=witness_v0_keyhash
         addr=bcrt1qfwf6y2l8szrpy2xpwm559plgjmwfr95yvdg040
vin[0].scriptSig       (empty)
vin[0].txinwitness     [signature, pubkey 027adbdb86...]
```

잔돈 address `bcrt1qfwf6y...`는 새로 만든 alice(`bcrt1qnucjj...`)도 bob도 아닙니다. wallet이 고른 잔돈 출력입니다.

![P2WPKH 출력이 witness 스택으로 열리는 흐름](/assets/img/blockchain/bitcoin-p2wpkh-witness.webp)
_잠금은 scriptPubKey의 0과 20바이트 hash다. 잠금 해제는 빈 scriptSig가 아니라 txinwitness의 signature와 공개키다._

잠금 스크립트가 곧 그 출력을 쓸 수 있는 조건입니다. 같은 node에서 `createmultisig 2`를 호출하면 레거시 P2SH address `2MwmkSC41uzy1QjUzUczpPRHJ8y33zwtvHT`가 나옵니다. RPC의 `type` 필드는 null이었고, `redeemScript` 길이는 142였습니다. 기본 송금 address와 멀티시그 address의 형식이 다른 것은 address가 balance 상자가 아니라, 어떤 Script를 쓰는지에 대한 짧은 이름이기 때문입니다.

---

## 4. 가벼운 증명은 헤더와 Merkle 경로면 된다

block 하나를 캐자 같은 거래의 `confirmations`는 1이 되었습니다. 확인 block은 `20fcf9356f54f944393db00af07c1b59f7b2ecf9d6b4a19f7362bf53e5bc7e54`이고 높이는 112, 거래 수는 2(코인베이스와 우리 거래)였습니다. 이 포함 관계를 전체 block 없이 검증하는 값이 `gettxoutproof`입니다.

```text
gettxoutproof     151 bytes
verifytxoutproof  [b50a5a254dc489c1...]
block nTx         2
header.height     112
header.merkleroot 38990380955e16093d384cb634689a165e34ba5a642827fbe345714490368d3e
```

![block 헤더의 Merkle 루트와 151바이트 증명으로 txid를 확인하는 흐름](/assets/img/blockchain/bitcoin-spv-proof.webp)
_증명이 151바이트인 이유는 전체 거래 목록이 아니라 해당 거래가 루트에 연결되는 경로만 담기 때문이다._

헤더에는 이전 block hash와 Merkle 루트가 들어 있습니다. 라이트 클라이언트가 전체 체인을 들고 다니지 않아도 포함 여부를 따질 수 있는 지점입니다. 이 값은 nTx=2인 로컬 block의 증명입니다. 메인넷 대형 block의 증명 크기를 여기서 재현한 것은 아닙니다.

---

## 5. 확인된 거래도 mempool로 돌아올 수 있다

확인 block `20fcf935...`를 `invalidateblock`으로 무효화했습니다. 같은 거래의 `confirmations`는 다시 0이 되었고, mempool 크기는 1로 돌아왔습니다. 그 상태에서 block 두 개를 더 캐면 체인 팁은 이렇게 갈라집니다.

![mempool의 거래가 block에 들어갔다가 무효화되면 다시 mempool로 돌아오고, 이전 팁은 invalid로 남는 흐름](/assets/img/blockchain/bitcoin-mempool-reorg.webp)
_block 112를 무효화하면 거래는 mempool로 돌아가고, 새로 캔 체인이 active 팁(높이 113)이 된다. 옛 팁은 invalid로 남는다._

```text
invalidated  20fcf9356f54f944393db00af07c1b59f7b2ecf9d6b4a19f7362bf53e5bc7e54
new blocks   42bd65f71aa756c6...
             6d72f32e4dc02d37...
tips:
  active   height=113  branchlen=0  6d72f32e4dc02d375f33313d7298d40a4b9ac6cc803279071fe1812b6ad23ab6
  invalid  height=112  branchlen=1  20fcf9356f54f944393db00af07c1b59f7b2ecf9d6b4a19f7362bf53e5bc7e54
```

확인은 "이 출력이 영원히 확정됐다"가 아닙니다. 지금 이 node가 따르는 활성 팁의 조상에 그 거래가 있는지를 센 값입니다. 더 긴 쪽이 정본이 되면 짧은 쪽의 확인은 철회됩니다. 실무에서 여러 confirmation을 기다리는 이유는 이 교체가 깊어질수록 비용이 커지기 때문입니다.

관측한 값은 로컬에서 만든 1block 무효화입니다. 메인넷의 6 confirmation 관행을 여기서 재현한 것은 아닙니다. generate 2 이후 그 거래가 새 체인에 다시 들어갔는지는 이 덤프에 없습니다. 무효화 직후의 `confirmations=0`과 그다음 tips만 기록했습니다. 지갑을 맞추려고 block을 하나 더 캔 뒤 `getmininginfo`는 `blocks=114`, `pooledtx=0`이었습니다.

---

## 6. 정리

비트코인 node는 거래를 바로 장부에 새기지 않습니다. 먼저 mempool에 올리고, block에 담아 확인 횟수를 만들고, 체인이 갈라지면 그 확인을 되돌릴 수 있습니다. 출력을 잠그는 것은 address 문자열이 아니라 Script이고, 기본 wallet은 P2WPKH를 씁니다. 포함 여부는 헤더와 Merkle 경로만으로도 검증할 수 있습니다.

이 관측은 피어가 없는 로컬 regtest에서 나왔습니다. 난이도는 `4.656542373906925e-10`이라 퍼즐은 거의 없지만, mempool, Script, 증명, reorg의 규칙은 메인넷과 같습니다. 실제 자산은 움직이지 않았습니다.

---

## 7. Reference

- [Bitcoin Developer Guide - P2P Network](https://developer.bitcoin.org/devguide/p2p_network.html)
- [Bitcoin Developer Guide - Block Chain](https://developer.bitcoin.org/devguide/block_chain.html)
- [Bitcoin Developer Guide - Transactions](https://developer.bitcoin.org/devguide/transactions.html)
- [Mastering Bitcoin - The Bitcoin Network (ch10)](https://github.com/bitcoinbook/bitcoinbook/blob/develop/ch10_network.adoc)
- [Mastering Bitcoin - Mining and Consensus (ch12)](https://github.com/bitcoinbook/bitcoinbook/blob/develop/ch12_mining.adoc)

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
