---
title: "Foundry 컨트랙트 기초 - forge, Counter, 배포 [Blockchain 5]"
date: 2026-08-23 02:17:00 +0900
author: kkamji
categories: [Blockchain]
tags: [blockchain, ethereum, foundry, solidity, counter, anvil, study]
comments: true
image:
  path: /assets/img/blockchain/blockchain.webp
---

이더리움 계정에 코드를 조회했을 때 `0x`가 나오면 그 주소는 EOA입니다. 같은 명령을 방금 배포한 주소에 치면 바이트코드가 나옵니다. 상태 트리의 그 칸에 실행할 프로그램이 올라갔다는 뜻입니다.

[이전 글](https://kkamji.net/posts/ethereum-account-nonce-gas/)에서 nonce와 21000 가스 이체를 관측했습니다. 이번에는 Foundry 1.7.1로 Counter를 테스트하고 Anvil에 배포합니다. 실습은 로컬 체인만 사용합니다.

---

## 1. 테스트가 통과한 뒤에 배포한다

Foundry 기본 Counter는 `number` 저장값과 `increment`, `setNumber`만 가집니다. `forge test` 결과는 다음이었습니다.

```text
[PASS] test_Increment()
[PASS] testFuzz_SetNumber(uint256) (runs: 256)
2 passed; 0 failed
Solc 0.8.35
```

퍼즈 테스트는 `setNumber`에 난수 256개를 넣어 저장값이 그대로인지 확인합니다. 배포 전에 스토리지 규칙을 깨지 못했다는 증적입니다. 배포 후에는 코드를 고쳐서 되돌리기 어렵습니다.

---

## 2. 배포 주소에는 코드가 있다

`forge create`로 배포한 주소는 `0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512`였습니다. `cast code`는 빈 값이 아니라 964자의 hex였습니다.

```text
deployer     0xf39Fd6e5...
deployedTo   0xe7f1725E...
cast code    964 hex characters
number()     0
```

![EOA가 Counter를 배포하면 주소에 바이트코드가 생기고 increment가 number를 1로 바꾸는 흐름](/assets/img/blockchain/foundry-counter-deploy.webp)
_EOA의 code는 0x다. Counter 주소에는 바이트코드가 있고, increment 호출 후 number는 1이다._

같은 노드에서 EOA를 조회하면 여전히 `0x`입니다. 주소 형식이 같아서 헷갈리지만, 코드 유무가 계정 종류를 가릅니다.

---

## 3. 호출은 스토리지를 바꾼다

배포 직후 `number()`는 0이었습니다. `increment()` receipt는 `status=0x1`, `gasUsed=43482`였고, 다시 읽으면 1이었습니다. 단순 이체 21000보다 큰 이유는 스토리지 쓰기가 들어가기 때문입니다.

`increment`는 `public`이라 권한 검사가 없습니다. 누가 호출해도 숫자가 올라갑니다. 다음 글의 보안 실습이 필요한 지점입니다.

---

## 4. 정리

Foundry는 테스트, 배포, 호출을 같은 도구 세트로 묶습니다. `forge test`로 규칙을 확인하고, `forge create`로 코드를 주소에 올리며, `cast code`와 `cast call`로 결과를 읽습니다. 이 관측은 Anvil(chainId 31337)에서만 나왔고 실제 자산은 움직이지 않았습니다.

---

## 5. Reference

- [Foundry Book](https://book.getfoundry.sh/)
- [Foundry Book - Forge](https://book.getfoundry.sh/forge/)
- [Ethereum Docs - Smart contracts](https://ethereum.org/en/developers/docs/smart-contracts/)

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
