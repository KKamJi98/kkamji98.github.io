---
title: "이더리움 상태 머신 기초 - Account, Nonce, Gas [Blockchain 4]"
date: 2026-08-23 01:33:00 +0900
author: kkamji
categories: [Blockchain]
tags: [blockchain, ethereum, account, nonce, gas, anvil, study]
comments: true
image:
  path: /assets/img/blockchain/blockchain.webp
---

비트코인에서는 잔액을 구하려면 미사용 출력을 모두 더해야 했습니다. 이더리움 노드에 같은 질문을 하면 계정 객체에서 `balance`와 `nonce`를 읽습니다. 합계를 다시 계산하지 않습니다.

[이전 글](https://kkamji.net/posts/bitcoin-mempool-reorg-script/)에서 확인은 활성 팁에 상대적이라는 점을 봤습니다. 이더리움은 그 위에 계정 상태와 가스라는 실행 비용을 올립니다. Foundry Anvil 1.7.1 로컬 체인(chainId 31337)에서 관측합니다. Anvil 기본 키는 공개 테스트 값이며 실제 네트워크에 재사용하지 않습니다.

---

## 1. 계정은 잔액과 nonce를 들고 있다

Anvil 계정 0의 코드를 조회하면 `0x`입니다. 이 주소는 EOA입니다. 컨트랙트 계정이 아닙니다. 같은 시점의 nonce는 0이었습니다.

비트코인의 주소가 Script 잠금의 짧은 이름인 것과 달리, 이더리움 주소는 상태 트리의 키입니다. 그 키 아래에는 최소한 nonce, balance, codeHash, storageRoot가 있습니다. 잔액을 구하려고 옛 거래를 다시 훑지 않습니다.

---

## 2. 거래는 nonce를 하나 소비한다

계정 0에서 계정 1로 1 ETH를 보냈습니다. receipt는 성공이었고, 같은 계정의 nonce는 1이 되었습니다.

```text
from    0xf39Fd6e5...
to      0x70997970...
nonce   0 -> 1
type    0x2
status  0x1
gasUsed 21000 (0x5208)
block   0 -> 1
```

![EOA가 nonce 0 거래를 보내면 receipt가 21000 가스를 기록하고 nonce가 1이 되는 흐름](/assets/img/blockchain/ethereum-account-nonce.webp)
_계정은 잔액과 nonce를 저장한다. 단순 이체는 가스를 21000 쓰고 nonce를 하나 올린다._

같은 nonce를 다시 쓰면 노드는 그 거래를 새 상태로 적용하지 않습니다. UTXO를 두 번 쓰는 이중지출과 같은 자리를, 이더리움은 nonce 카운터로 막습니다.

---

## 3. 가스는 실행의 계량 단위다

`gasUsed=21000`은 단순 이체의 하한입니다. 컨트랙트 호출은 이보다 큽니다. 가스는 이더의 별칭이 아니라, 연산과 저장에 매기는 계량입니다. 수수료는 `gasUsed * effectiveGasPrice`로 정해지고, 그 이더는 소각분과 우선순위 수수료로 나뉩니다. Anvil의 `type=0x2` receipt는 EIP-1559 거래입니다.

로컬 Anvil은 거래마다 블록을 만듭니다. `latest` 블록에는 `baseFeePerGas`가 있지만 `safe`/`finalized` 태그는 없습니다. 세 태그의 차이는 합의 클라이언트가 있는 네트워크에서 Week 8에 관측합니다.

---

## 4. 정리

이더리움의 돈과 순서는 계정 필드입니다. EOA는 코드가 없고 nonce로 거래를 줄 세웁니다. 단순 이체는 21000 가스를 쓰며, 가스는 실행을 계량합니다. 이 관측은 피어가 없는 Anvil에서 나왔고 실제 자산은 움직이지 않았습니다.

다음 실습은 같은 로컬 체인에서 컨트랙트 코드를 배포해 `cast code`가 `0x`가 아닌 주소를 만드는 것입니다.

---

## 5. Reference

- [Ethereum Docs - Accounts](https://ethereum.org/en/developers/docs/accounts/)
- [Ethereum Docs - Transactions](https://ethereum.org/en/developers/docs/transactions/)
- [Ethereum Docs - Gas](https://ethereum.org/en/developers/docs/gas/)
- [Foundry Book - Anvil](https://book.getfoundry.sh/anvil/)

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
