---
title: "Foundry contract 기초 - forge, Counter, deploy [Blockchain 5]"
date: 2026-08-10 12:06:00 +0900
author: kkamji
categories: [Blockchain]
tags: [blockchain, ethereum, foundry, solidity, counter, anvil, study]
comments: true
image:
  path: /assets/img/blockchain/blockchain.webp
---

이더리움 계정에 코드를 조회했을 때 `0x`가 나오면 그 address는 EOA입니다. 같은 명령을 방금 deploy한 address에 치면 바이트코드가 나옵니다. 상태 트리의 그 칸에 실행할 프로그램이 올라갔다는 뜻입니다.

[이전 글](https://kkamji.net/posts/ethereum-account-nonce-gas/)에서 nonce와 21000 gas 이체를 관측했습니다. 이번에는 Foundry 1.7.1로 Counter를 테스트하고 Anvil에 deploy합니다. 같은 바이너리라도 `forge test`, `forge create`, `cast`는 서로 다른 대상에 붙습니다. 실습은 로컬 체인만 사용합니다.

---

## 1. forge test는 체인을 건드리지 않는다

Foundry 기본 Counter는 `number` 저장값과 `increment`, `setNumber`만 가집니다.

```solidity
contract Counter {
    uint256 public number;

    function setNumber(uint256 newNumber) public {
        number = newNumber;
    }

    function increment() public {
        number++;
    }
}
```

`forge test`는 이 규칙을 Anvil 없이 검사합니다. 테스트 프로세스가 자체 EVM을 띄우고, `setUp`에서 `new Counter()`로 인스턴스를 만든 뒤 함수를 호출합니다. 그 address는 테스트가 끝나면 사라집니다. receipt도 없고, 나중에 `cast code`로 다시 열 칸도 없습니다.

```solidity
function setUp() public {
    counter = new Counter();
    counter.setNumber(0);
}

function test_Increment() public {
    counter.increment();
    assertEq(counter.number(), 1);
}

function testFuzz_SetNumber(uint256 x) public {
    counter.setNumber(x);
    assertEq(counter.number(), x);
}
```

2026-08-23 결과는 다음이었습니다. Solc는 0.8.35입니다.

```text
[PASS] test_Increment()
[PASS] testFuzz_SetNumber(uint256) (runs: 256)
2 passed; 0 failed
Solc 0.8.35
```

퍼즈 테스트는 `setNumber`에 난수 256개를 넣어 저장값이 그대로인지 확인합니다. 통과는 "이 소스의 스토리지 규칙을 256번 깨지 못했다"는 뜻이지, Anvil 상태 트리에 코드가 올라갔다는 뜻이 아닙니다.

프로젝트에 `script/Counter.s.sol`도 있습니다. `vm.startBroadcast()` 안에서 `new Counter()`를 호출하는 스크립트입니다. 이번 랩의 deploy 관측은 `forge create`로 남겼고, 스크립트 실행 로그는 없습니다.

---

## 2. forge create는 address에 코드를 남긴다

테스트를 통과한 소스를 Anvil(chainId 31337)에 올리려면 거래가 필요합니다. `forge create`는 contract-creation transaction을 node에 보냅니다. 돌아온 address는 `0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512`였습니다. deployer는 Anvil 기본 계정 `0xf39Fd6e5...`입니다.

`cast code`는 그 address의 코드를 읽습니다. 값은 빈 `0x`가 아니라 964자의 hex였습니다. 같은 node에서 EOA를 조회하면 여전히 `0x`입니다. address 형식이 같아서 헷갈리지만, 코드 유무가 계정 종류를 가릅니다.

```text
deployer     0xf39Fd6e5...
deployedTo   0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512
cast code    964 hex characters
```

![forge test는 임시 EVM에서 끝나고, forge create는 Anvil address에 바이트코드를 남기며, cast가 그 address를 읽고 호출하는 흐름](/assets/img/blockchain/foundry-test-create-cast.webp)
_forge test는 통과만 남긴다. forge create가 코드를 address에 올리고, cast가 그 칸을 읽는다._

`forge test`의 `new Counter()`와 `forge create`의 `deployedTo`는 같은 소스를 써도 같은 객체가 아닙니다. 한쪽은 테스트 러너의 메모리이고, 다른 쪽은 Anvil이 유지하는 상태 트리입니다. deploy 후에 소스를 고치면 이미 올라간 바이트코드는 그대로입니다.

---

## 3. cast는 그 address를 읽고 바꾼다

deploy 직후 `cast call`로 `number()`를 읽으면 0이었습니다. 이 호출은 상태를 바꾸지 않습니다. 값을 바꾸려면 `cast send`로 `increment()` 거래를 넣어야 합니다.

```text
number()     0
increment()  status=0x1  gasUsed=43482 (0xa9da)
number()     1
```

![EOA가 Counter를 deploy하면 address에 바이트코드가 생기고 increment가 number를 1로 바꾸는 흐름](/assets/img/blockchain/foundry-counter-deploy.webp)
_EOA의 code는 0x다. Counter address에는 바이트코드가 있고, increment 호출 후 number는 1이다._

receipt의 `status=0x1`은 실행이 되돌려지지 않았다는 뜻입니다. `gasUsed=43482`는 단순 이체 21000보다 큽니다. `increment`가 `number++`로 스토리지를 쓰기 때문입니다. 이 숫자 하나를 opcode 표로 분해하지는 않았습니다.

정리하면 도구 세 개의 경계는 다음과 같습니다.

- `forge test`: 프로세스 안 EVM. 통과/실패만 남긴다. Anvil address가 없다.
- `forge create`: node에 생성 거래를 보낸다. `cast code`가 비어 있지 않은 address가 생긴다.
- `cast call` / `cast send`: 그 address의 view와 상태 변경을 RPC로 다룬다.

---

## 4. increment는 권한이 없다

`increment`와 `setNumber`는 `public`이고 `msg.sender`를 보지 않습니다. Anvil 기본 키가 아니어도, 그 함수를 넣을 gas만 있으면 `number`가 바뀝니다.

테스트가 검사한 것은 "호출하면 1이 되는가", "넣은 값이 그대로인가"입니다. "누가 호출해도 되는가"는 검사하지 않았습니다. 숫자가 틀려도 이더는 움직이지 않습니다. 같은 권한이 이더를 들고 있는 출금 함수에 있으면 결과가 다릅니다.

이 관측은 Anvil에서만 나왔고 실제 자산은 움직이지 않았습니다.

---

## 5. 정리

Foundry는 테스트와 deploy와 호출을 한 설치로 묶지만, 세 명령의 대상은 다릅니다. `forge test`로 스토리지 규칙을 확인하고, `forge create`로 코드를 address에 올리며, `cast`로 그 칸을 읽고 바꿉니다. 테스트 통과는 체인 기록이 아니고, `cast code`가 `0x`가 아닐 때가 deploy의 증적입니다.

---

## 6. Reference

- [Foundry Book](https://book.getfoundry.sh/)
- [Foundry Book - Forge](https://book.getfoundry.sh/forge/)
- [Foundry Book - Cast](https://book.getfoundry.sh/cast/)
- [Ethereum Docs - Smart contracts](https://ethereum.org/en/developers/docs/smart-contracts/)

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
