---
title: "Smart contract 보안 기초 - 재진입, CEI [Blockchain 6]"
date: 2026-08-23 03:08:00 +0900
author: kkamji
categories: [Blockchain]
tags: [blockchain, ethereum, security, reentrancy, foundry, study]
comments: true
image:
  path: /assets/img/blockchain/blockchain.webp
---

지난 Counter의 `increment`는 권한이 없었습니다. 숫자가 틀려도 돈은 움직이지 않습니다. 같은 실수가 이더를 들고 있는 금고에서 나면, 출금 함수가 끝나기 전에 다시 출금이 들어옵니다.

[이전 글](https://kkamji.net/posts/foundry-counter-deploy/)에서 deploy address에 코드가 생긴다는 점을 확인했습니다. 이번에는 그 코드의 호출 순서를 Foundry 테스트로 깨 봅니다. 취약 경로와 Checks-effects-interactions 경로를 같은 공격 contract로 비교합니다. 실습은 로컬 `forge test`만 사용합니다.

---

## 1. 취약 금고는 이더를 보낸 뒤에 balance를 지운다

`InsecureVault`는 입금액을 `balances`에 적습니다. 출금은 그 이더를 `msg.sender.call`로 보낸 뒤에야 mapping을 0으로 만듭니다.

```solidity
function deposit() external payable {
    balances[msg.sender] += msg.value;
}

function withdraw() external {
    uint256 amount = balances[msg.sender];
    require(amount > 0, "empty");
    (bool ok,) = msg.sender.call{value: amount}("");
    require(ok, "send failed");
    balances[msg.sender] = 0;
}
```

`call`은 수신자가 contract이면 `receive` 또는 `fallback`을 실행합니다. 그 함수가 다시 `withdraw`를 호출하면, 아직 `balances[msg.sender]`가 남아 있으므로 `require(amount > 0)`를 통과합니다. 두 번째 송금이 나갑니다.

테스트는 피해자 address `0xBEEF`에 10 ETH를 넣고 `vm.prank`로 입금합니다. 공격 contract는 1 ETH를 넣은 뒤 `attack()`에서 `withdraw`를 시작합니다. Solc 0.8.35에서 결과는 금고 balance 0이었습니다. 피해자 자금까지 빠져나갔습니다.

```text
[PASS] test_insecureVaultIsDrained()
vault.balance == 0
attacker.balance > 10 ether
```

11 ETH가 금고에 있었고, 공격자는 자기 1 ETH보다 많은 금액을 들고 나왔습니다. 반복 횟수를 로그로 세지는 않았습니다. 관측은 끝 상태뿐입니다.

---

## 2. 공격 contract는 receive에서 같은 withdraw를 다시 부른다

공격 경로는 별도 contract입니다. `attack`이 입금과 첫 출금을 열고, `receive`가 금고에 1 ETH 이상이 남아 있는 동안 `withdraw`를 다시 호출합니다.

```solidity
contract Attacker {
    InsecureVault public vault;

    receive() external payable {
        if (address(vault).balance >= 1 ether) {
            vault.withdraw();
        }
    }

    function attack() external payable {
        vault.deposit{value: 1 ether}();
        vault.withdraw();
    }
}
```

호출 순서는 한 줄입니다. `withdraw`가 `call`로 이더를 보내고, `receive`가 그 `call` 안에서 다시 `withdraw`에 들어갑니다. 바깥 `withdraw`의 `balances[msg.sender] = 0`은 아직 실행되지 않았습니다.

![출금이 이더를 먼저 보내면 공격자의 receive가 같은 withdraw를 다시 호출하는 흐름](/assets/img/blockchain/reentrancy-insecure-loop.webp)
_call이 끝나기 전에 balance가 남아 있으면 같은 출금이 반복된다. 테스트 끝 상태는 vault 0이다._

`receive`의 정지 조건은 mapping이 아니라 `address(vault).balance`입니다. 금고 이더가 1 ETH 아래로 떨어질 때까지 재진입합니다. 피해자 10 ETH는 그 조건에 포함됩니다.

---

## 3. 스토리지를 먼저 바꾸면 중첩 출금이 되돌아온다

`SecureVault`는 같은 `deposit`과 같은 `require`를 씁니다. 바뀐 것은 두 줄의 순서입니다. mapping을 0으로 만든 뒤에 보냅니다.

```solidity
function withdraw() external {
    uint256 amount = balances[msg.sender];
    require(amount > 0, "empty");
    balances[msg.sender] = 0;
    (bool ok,) = msg.sender.call{value: amount}("");
    require(ok, "send failed");
}
```

공격 contract도 같습니다. `SecureAttacker.receive`는 금고에 1 ETH 이상이 있으면 다시 `withdraw`를 호출합니다. 중첩 호출이 읽는 `balances[attacker]`는 이미 0입니다. `require(amount > 0, "empty")`가 revert합니다.

그 revert는 안쪽 `withdraw`만의 실패가 아닙니다. 바깥 `call`이 `(false, ...)`를 돌려주고, `require(ok, "send failed")`가 바깥 `withdraw`를 되돌립니다. `attack()` 전체가 revert합니다. 공격자의 1 ETH 입금도 같이 되돌아갑니다. 피해자 10 ETH만 금고에 남습니다.

```text
[PASS] test_secureVaultKeepsVictimFunds()
vm.expectRevert()
vault.balance == 10 ether
vault.balances(attacker) == 0
```

![CEI 출금은 balance를 먼저 0으로 만들어 중첩 withdraw가 empty로 revert하는 흐름](/assets/img/blockchain/reentrancy-cei-secure.webp)
_스토리지를 먼저 바꾸면 receive가 다시 들어와도 amount는 0이다. 바깥 call도 실패한다._

이 순서를 Checks-effects-interactions라고 부릅니다. 검사, 상태 변경, 외부 호출입니다. Solidity 문서의 re-entrancy 절이 같은 순서를 권고합니다.

`nonReentrant` 락은 이번 랩의 소스에 없습니다. 락은 같은 실수를 한 번 더 막는 장치에 가깝고, 이 순서 자체를 대체하는 관측은 하지 않았습니다.

---

## 4. 두 테스트가 같은 공격을 다른 결과로 고정한다

두 테스트의 준비는 같습니다. 피해자 10 ETH를 먼저 넣고, 공격자가 1 ETH로 `attack()`을 엽니다. 갈라지는 지점은 `withdraw`가 `call`보다 먼저 mapping을 지우는가입니다.

```text
[PASS] test_insecureVaultIsDrained()
[PASS] test_secureVaultKeepsVictimFunds()
2 passed; 0 failed
Solc 0.8.35
```

재진입은 권한이 없는 함수의 문제가 아닙니다. 아직 끝나지 않은 출금이 같은 balance를 다시 읽는 문제입니다. 수정은 접근 제어를 추가한 것이 아니라, 외부 호출 전에 스토리지를 바꾼 한 줄 이동이었습니다.

이 관측은 로컬 테스트에서만 나왔고 실제 자산은 움직이지 않았습니다.

---

## 5. 정리

취약 금고는 이더를 보낸 뒤에야 balance를 지웁니다. 공격 contract의 `receive`는 그 창에서 `withdraw`를 반복하고, 테스트 끝 상태는 vault 0입니다. 같은 공격을 스토리지 먼저 지우는 금고에 넣으면 중첩 출금이 `empty`로 되돌아가고, 바깥 `call`도 실패하며, 피해자 10 ETH는 남습니다. Checks-effects-interactions는 그 순서의 이름입니다.

---

## 6. Reference

- [Solidity Docs - Re-entrancy](https://docs.soliditylang.org/en/latest/security-considerations.html#re-entrancy)
- [Ethereum Docs - Smart contract security](https://ethereum.org/en/developers/docs/smart-contracts/security/)
- [Foundry Book - Tests](https://book.getfoundry.sh/forge/tests)

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
