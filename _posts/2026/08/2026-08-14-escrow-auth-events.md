---
title: "Escrow 컨트랙트 기초 - 권한, event, runbook [Blockchain 9]"
date: 2026-08-14 02:44:00 +0900
author: kkamji
categories: [Blockchain]
tags: [blockchain, ethereum, escrow, foundry, anvil, event, study]
comments: true
image:
  path: /assets/img/blockchain/blockchain.webp
---

숫자를 올리는 Counter와 달리, Escrow는 이더를 잠급니다. 누가 `deposit`을 호출할 수 있는지, 누가 `release`를 호출할 수 있는지가 곧 돈의 경로입니다.

[이전 글](https://kkamji.net/posts/ethereum-node-rpc-ops/)에서 HTTP 200이 chain head가 아님을 확인했습니다. 이번에는 같은 로컬 Anvil에서 3자 Escrow를 올리고, 권한과 event를 receipt로 확인합니다. Sepolia에는 배포하지 않았습니다. 전용 testnet wallet이 없습니다.

---

## 1. forge test가 권한 표를 고정한다

Escrow는 buyer, seller, arbiter 세 address를 constructor에서 받습니다. 입금은 buyer만, 판매자에게 풀기는 buyer 또는 arbiter, 구매자에게 돌려주기는 seller 또는 arbiter입니다.

```solidity
function deposit() external payable {
    if (msg.sender != buyer) revert NotBuyer();
    if (funded) revert AlreadyFunded();
    if (msg.value == 0) revert ZeroDeposit();
    amount = msg.value;
    funded = true;
    emit Deposited(msg.sender, msg.value);
}
```

`forge test`는 Anvil 없이 이 표를 깨 봅니다. Solc 0.8.35에서 6개가 통과했습니다.

```text
[PASS] test_depositEmitsAndLocks()
[PASS] test_strangerCannotDeposit()
[PASS] test_buyerReleasePaysSeller()
[PASS] test_sellerRefundPaysBuyer()
[PASS] test_strangerCannotRelease()
[PASS] test_strangerCannotRefund()
6 passed; 0 failed
```

테스트 통과는 체인 기록이 아닙니다. 권한 규칙이 프로세스 안 EVM에서 한 번도 깨지지 않았다는 뜻입니다.

---

## 2. 낯선 주소의 deposit는 receipt가 없다

Anvil 8547에 `forge create`로 올린 address는 `0x5FbDB2315678afecb367f032d93F642f64180aa3`입니다. constructor 인자는 Anvil 기본 계정 0, 1, 2입니다. 공개 테스트 키이며 공개망에 쓰지 않습니다. `cast code`는 5234자의 hex였습니다.

같은 체인에서 계정 3이 `deposit()`에 1 ETH를 넣으려 하면, 전송 전 estimate가 멈춥니다.

```text
Error: Failed to estimate gas
execution reverted: NotBuyer
```

![낯선 주소의 deposit가 estimate에서 NotBuyer로 막혀 receipt가 없는 흐름](/assets/img/blockchain/escrow-auth-deny.webp)
_권한 실패는 체인을 갱신하지 않는다. funded는 false로 남는다._

이 실패는 이전 글의 `boom()`과 같은 층입니다. revert가 예상되면 node는 gas를 배정하지 않습니다. explorer에 올라갈 hash도 없습니다. 권한이 없는 호출은 "실패한 거래"가 아니라 "거래가 되지 않은 호출"입니다.

---

## 3. buyer deposit는 event 하나를 남긴다

buyer 계정으로 1 ETH를 넣으면 receipt는 성공이었습니다.

```text
status     0x1
gasUsed    69398
logs       1
funded     true
amount     1000000000000000000
balance    1 ETH
```

`logs`가 1인 이유는 `Deposited`를 emit했기 때문입니다. 금고 address의 이더는 1 ETH입니다. seller의 잔액은 아직 10000 ETH입니다. 잠긴 것이지, 전달된 것이 아닙니다.

`release`와 `refund`는 외부 `call` 전에 `funded=false`와 `amount=0`을 먼저 씁니다. 재진입 락은 이 소스에 없습니다. 순서는 Checks-effects-interactions입니다.

---

## 4. release는 seller 잔액을 1 ETH 올린다

buyer가 `release()`를 호출한 뒤의 상태입니다.

```text
status        0x1
gasUsed       37725
logs          1
funded        false
escrow        0
seller        10000 ETH -> 10001 ETH
```

![buyer deposit가 Escrow를 잠그고 release가 seller에게 1 ETH를 보내는 흐름](/assets/img/blockchain/escrow-deposit-release.webp)
_locked 이더는 Escrow address에 있다. release 뒤에야 seller 잔액이 1 ETH 오른다._

`Released` event 하나가 receipt에 남습니다. 운영자가 나중에 추적할 때는 탐색기 잔액보다 이 log와 `funded()`를 먼저 봅니다. Anvil에서 `cast call funded()(bool)`이 false이면, 그 금고는 이미 비었습니다.

arbiter의 `release`/`refund`는 테스트에서만 확인했습니다. 이 Anvil 세션에서는 buyer 경로만 전송했습니다.

---

## 5. 로컬 runbook

다시 재현하는 순서는 짧습니다. 공개망 키는 쓰지 않습니다.

1. `forge test`가 6개 통과하는지 본다.
2. 로컬 Anvil에 `forge create`로 buyer, seller, arbiter를 넣는다.
3. `cast code`가 `0x`가 아닌지 확인한다.
4. buyer가 아닌 키로 `deposit`을 넣어 estimate revert를 본다.
5. buyer로 1 ETH를 넣고 `funded()`가 true인지 본다.
6. `release` 또는 `refund` 뒤 `funded()`가 false인지, 상대 잔액이 1 ETH 늘었는지 본다.

이 순서는 Anvil의 머리에서만 성립합니다. 이전 글에서 본 것처럼 이 block은 peer에 전파되지 않습니다. 프로세스를 끄면 금고와 event도 사라집니다.

---

## 6. 정리

Escrow의 핵심은 이더를 잠근 뒤, 누가 어느 방향으로 푸는지를 address로 고정하는 일입니다. 테스트 6개가 그 표를 깨지 못했고, Anvil에서는 stranger `deposit`이 receipt 없이 거절되었으며, buyer `deposit`과 `release`는 event 하나씩과 seller +1 ETH를 남겼습니다. Sepolia에는 올리지 않았습니다.

---

## 7. Reference

- [Solidity Docs - Events](https://docs.soliditylang.org/en/latest/contracts.html#events)
- [Solidity Docs - Error handling](https://docs.soliditylang.org/en/latest/control-structures.html#error-handling)
- [Foundry Book - Forge](https://book.getfoundry.sh/forge/)
- [Foundry Book - Cast](https://book.getfoundry.sh/cast/)

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
