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

비트코인에서는 balance를 구하려면 미사용 출력을 모두 더해야 했습니다. 이더리움 node에 같은 질문을 하면 계정 객체에서 `balance`와 `nonce`를 읽습니다. 합계를 다시 계산하지 않습니다.

[이전 글](https://kkamji.net/posts/bitcoin-mempool-reorg-script/)에서 확인은 활성 팁에 상대적이라는 점을 봤습니다. 이더리움은 그 위에 계정 상태와 gas라는 실행 비용을 올립니다. Foundry Anvil 1.7.1 로컬 체인(chainId 31337)에서 관측합니다. Anvil 기본 키는 공개 테스트 값이며 실제 네트워크에 재사용하지 않습니다.

---

## 1. 계정은 balance와 nonce를 들고 있다

깨끗한 Anvil에서 계정 0의 코드를 조회하면 `0x`입니다. 이 address는 EOA입니다. contract 계정이 아닙니다. 같은 시점의 nonce는 0이었고, `cast balance`는 `10000000000000000000000` wei, 즉 10000 ETH였습니다. 계정 1도 같은 시작 balance를 갖고 있었습니다.

```text
address  0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266
code     0x
nonce    0
balance  10000000000000000000000
```

비트코인의 address가 Script 잠금의 짧은 이름인 것과 달리, 이더리움 address는 상태 트리의 키입니다. ethereum.org 문서는 그 키 아래에 nonce, balance, codeHash, storageRoot가 있다고 적습니다. 이 랩이 RPC로 읽은 값은 nonce, balance, code입니다. codeHash와 storageRoot 바이트는 따로 덤프하지 않았습니다.

![address가 계정 객체를 가리키고 관측된 필드가 nonce 0, code 0x, 10000 ETH인 구조](/assets/img/blockchain/ethereum-account-fields.webp)
_address는 상태 트리의 키다. 이 실습이 확인한 필드는 nonce 0, 빈 코드, 시작 balance 10000 ETH다._

---

## 2. 거래는 nonce를 하나 소비한다

계정 0에서 계정 1로 1 ETH를 보냈습니다. receipt는 성공이었고, 같은 계정의 nonce는 1이 되었습니다.

```text
from    0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266
to      0x70997970C51812dc3A010C7d01b50e0d17dc79C8
hash    0xce09985d94caad02fc26f64a68a95d3ae7ec58fa0ef5208c672d4f42052488dc
nonce   0 -> 1
type    0x2
status  0x1
gasUsed 21000 (0x5208)
block   0 -> 1
```

송신 뒤 balance는 이렇게 갈라졌습니다. 수신 계정은 정확히 1 ETH가 늘었습니다. 송신 계정은 1 ETH에다 gas fee만큼 더 줄었습니다.

```text
to    10001000000000000000000
from  9998999978999999979000
```

같은 nonce 0을 다시 넣으면 Anvil은 적용하지 않습니다. 응답은 `error code -32003: nonce too low`였습니다. UTXO를 두 번 쓰는 이중지출과 같은 자리를, 이더리움은 nonce 카운터로 막습니다.

nonce를 2 건너뛴 값 3을 넣어 보면 계정 nonce는 그대로 1이었습니다. `txpool_status`는 `pending=0x0`, `queued=0x1`이었습니다. 구멍 난 nonce는 당장 상태에 반영되지 않고, 대기열에 남았습니다.

![EOA가 nonce 0 거래를 보내면 receipt가 21000 gas를 기록하고 nonce가 1이 되는 흐름](/assets/img/blockchain/ethereum-account-nonce.webp)
_계정은 balance와 nonce를 저장한다. 단순 이체는 gas를 21000 쓰고 nonce를 하나 올린다._

---

## 3. gas는 실행의 계량 단위다

`gasUsed=21000`은 이 단순 이체의 소비량입니다. ethereum.org는 이 값을 기본 이체의 하한으로 적습니다. gas는 이더의 별칭이 아니라, 연산과 저장에 매기는 계량입니다.

이 receipt의 `effectiveGasPrice`는 `0x3b9aca01`, 십진수 1000000001 wei입니다. fee는 `21000 * 1000000001 = 21000000021000` wei입니다. 송신 계정 감소분에서 1 ETH를 빼면 같은 숫자가 나옵니다. 수신 계정은 fee를 받지 않습니다.

Anvil의 `type=0x2` receipt는 EIP-1559 거래입니다. 같은 block의 `baseFeePerGas`는 `0x3b9aca00`, 십진수 1000000000 wei였습니다. effective 값이 base보다 1 wei 큽니다. 소각분과 우선순위 fee를 필드 단위로 더 쪼개지는 않았습니다.

![type 0x2 이체가 21000 gas를 쓰고 성공 receipt를 남기는 흐름](/assets/img/blockchain/ethereum-gas-meter.webp)
_단순 이체의 gasUsed는 21000이다. 이 거래의 fee는 21000에 effectiveGasPrice를 곱한 값이다._

로컬 Anvil은 거래마다 block을 만듭니다. 이 송신 뒤 `latest`는 block 1이었습니다. block JSON에 `baseFeePerGas`는 있고 `safe`/`finalized` 키는 없습니다. 세 태그가 다른 머리를 가리키는 장면은 이 로컬 체인에 없습니다.

---

## 4. 정리

이더리움의 돈과 순서는 계정 필드입니다. EOA는 코드가 없고 nonce로 거래를 줄 세웁니다. 같은 nonce는 `nonce too low`로 거절되고, 구멍을 만든 nonce는 queued에 남습니다. 단순 이체는 21000 gas를 쓰며, 수신자는 value만 받고 fee는 송신 계정이 냅니다. 이 관측은 피어가 없는 Anvil에서 나왔고 실제 자산은 움직이지 않았습니다.

---

## 5. Reference

- [Ethereum Docs - Accounts](https://ethereum.org/en/developers/docs/accounts/)
- [Ethereum Docs - Transactions](https://ethereum.org/en/developers/docs/transactions/)
- [Ethereum Docs - Gas](https://ethereum.org/en/developers/docs/gas/)
- [Foundry Book - Anvil](https://book.getfoundry.sh/anvil/)

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
