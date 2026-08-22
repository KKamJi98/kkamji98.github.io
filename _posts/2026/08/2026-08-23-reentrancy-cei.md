---
title: "스마트 컨트랙트 보안 기초 - 재진입, CEI [Blockchain 6]"
date: 2026-08-23 03:08:00 +0900
author: kkamji
categories: [Blockchain]
tags: [blockchain, ethereum, security, reentrancy, foundry, study]
comments: true
image:
  path: /assets/img/blockchain/blockchain.webp
---

지난 Counter의 `increment`는 권한이 없었습니다. 숫자가 틀려도 돈은 움직이지 않습니다. 같은 실수가 이더를 들고 있는 금고에서 나면, 출금 함수가 끝나기 전에 다시 출금이 들어옵니다.

[이전 글](https://kkamji.net/posts/foundry-counter-deploy/)에서 배포 주소에 코드가 생긴다는 점을 확인했습니다. 이번에는 그 코드의 호출 순서를 Foundry 테스트로 깨 봅니다. 실습은 로컬 `forge test`만 사용합니다.

---

## 1. 취약 금고는 보내고 나서 잔액을 지운다

예제 금고는 입금액을 `balances`에 적고, 출금 때 그 이더를 `msg.sender.call`로 보낸 뒤에야 잔액을 0으로 만듭니다. 받는 쪽이 `receive`에서 다시 `withdraw`를 호출하면, 아직 잔액이 남아 있으므로 두 번째 송금이 통과합니다.

```solidity
uint256 amount = balances[msg.sender];
(bool ok,) = msg.sender.call{value: amount}("");
require(ok);
balances[msg.sender] = 0;
```

테스트에서 피해자 주소가 10 ETH를 넣고, 공격 컨트랙트가 1 ETH를 넣은 뒤 출금을 시작했습니다. 결과는 금고 잔액 0이었습니다. 피해자 자금까지 빠져나갔습니다.

```text
[PASS] test_insecureVaultIsDrained()
vault.balance == 0
attacker.balance > 10 ether
```

---

## 2. 스토리지를 먼저 바꾸면 중첩 출금이 막힌다

같은 금고에서 두 줄의 순서만 바꿨습니다. 잔액을 0으로 만든 뒤에 보냅니다.

```solidity
uint256 amount = balances[msg.sender];
balances[msg.sender] = 0;
(bool ok,) = msg.sender.call{value: amount}("");
require(ok);
```

공격 컨트랙트의 `receive`가 다시 `withdraw`를 호출하면 잔액은 이미 0입니다. `require(amount > 0)`가 실패하고, 바깥 `call`도 실패로 돌아옵니다. 테스트는 이 전체 공격을 revert로 기대했고, 피해자 10 ETH는 금고에 남았습니다.

```text
[PASS] test_secureVaultKeepsVictimFunds()
vm.expectRevert()
vault.balance == 10 ether
```

![출금이 이더를 먼저 보내면 공격자가 receive에서 다시 withdraw하고, CEI는 잔액을 먼저 0으로 만드는 흐름](/assets/img/blockchain/reentrancy-cei.webp)
_외부 호출 전에 잔액을 지우지 않으면 같은 withdraw가 반복된다. CEI는 스토리지를 먼저 바꾼다._

이 순서를 Checks-effects-interactions라고 부릅니다. 검사, 상태 변경, 외부 호출입니다. `nonReentrant` 락은 같은 실수를 한 번 더 막는 장치이지, 이 순서를 대체하지는 않습니다.

---

## 3. 정리

재진입은 권한이 없는 함수의 문제가 아니라, 아직 끝나지 않은 출금이 같은 잔액을 다시 읽는 문제입니다. Foundry로 공격 컨트랙트를 붙이면 그 순서가 테스트에서 드러납니다. 수정은 잔액을 먼저 지우는 한 줄 이동이었습니다. 이 관측은 로컬 테스트에서만 나왔고 실제 자산은 움직이지 않았습니다.

---

## 4. Reference

- [Solidity Docs - Re-entrancy](https://docs.soliditylang.org/en/latest/security-considerations.html#re-entrancy)
- [Ethereum Docs - Smart contract security](https://ethereum.org/en/developers/docs/smart-contracts/security/)
- [Foundry Book - Tests](https://book.getfoundry.sh/forge/tests)

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
