---
title: "컨트랙트 공급망 기초 - compiler pin, 재현 빌드 [Blockchain 15]"
date: 2026-08-23 05:58:00 +0900
author: kkamji
categories: [Blockchain]
tags: [blockchain, supply-chain, solc, foundry, bytecode, study]
comments: true
image:
  path: /assets/img/blockchain/blockchain.webp
---

같은 Solidity 파일이라도 컴파일러 버전이 바뀌면 체인에 올라가는 프로그램이 바뀝니다. 9편 Escrow 소스를 Foundry 1.7.1에서 solc 0.8.35와 0.8.28로 각각 빌드했습니다. deployedBytecode 길이는 둘 다 5234 hex였고, sha256은 달랐습니다.

[이전 글](https://kkamji.net/posts/mev-pbs-relay/)에서 Anvil에는 builder 시장이 없음을 봤습니다. 이번에는 배포 직전에 무엇을 고정해야 같은 바이너리가 나오는지를 봅니다. 공개망 배포는 하지 않았습니다.

---

## 1. 길이가 같아도 해시가 다르다

명령은 `foundry.toml`의 `solc` 한 줄만 바꿨습니다. 소스는 week9 `Escrow.sol` 그대로입니다.

```text
solc 0.8.35  hex 5234  sha256 d8f49804b7f3b17ed610eccaf115ceb07773f7ac1e1ed4950d9a61039a3a7cae
solc 0.8.28  hex 5234  sha256 98a49743f98699656707b37a4af24680cd357d59412d6bfb0e0e2927e9ecfa69
equal False
```

![같은 소스가 solc 0.8.35와 0.8.28에서 서로 다른 bytecode 해시가 되는 구조](/assets/img/blockchain/solc-pin-two-hashes.webp)
_바이트 수는 같다. 내용은 다르다. 길이만 보고 동일 프로그램이라고 하면 안 된다._

9편 Anvil 배포본의 `cast code` 길이도 5234 hex였습니다. 그 길이만 맞춰 놓고 컴파일러를 바꾸면, explorer에 보이는 코드 길이는 같고 실행은 다른 프로그램입니다. 검증은 길이가 아니라 해시입니다.

---

## 2. pin은 파일에 적는다

week9 `foundry.toml`은 `solc = "0.8.35"`입니다. 이 한 줄이 없으면 CI와 노트북이 다른 solc를 받아 다른 해시를 만듭니다. 배포 runbook은 그 해시를 릴리스 산출물로 저장하고, `forge create` 전에 다시 빌드해 같은지 봅니다.

![foundry.toml pin이 forge build를 거쳐 해시 대조로 이어지는 흐름](/assets/img/blockchain/supply-pin-then-deploy.webp)
_배포 게이트는 소스 diff가 아니라 bytecode 해시다._

RPC gateway가 여러 backend를 로드밸런싱하면, 같은 address 조회가 다른 체인을 볼 수 있습니다. 13편에서 8545와 8547이 같은 `chainId`로 다른 잔액을 줬습니다. 공급망 게이트를 통과한 바이너리를, 확인도 안 된 RPC에 올리면 그 게이트가 무의미해집니다. 이번 랩은 컴파일 해시만 대조했고 재배포하지 않았습니다.

---

## 3. 정리

재현 빌드는 소스와 컴파일러와 해시가 한 묶음입니다. Escrow 한 파일이 solc 두 버전에서 길이 같은 다른 bytecode를 만들었습니다. 운영 고정값은 `foundry.toml`의 solc pin과, 그 pin으로 나온 sha256입니다. 길이만 같으면 같은 컨트랙트라는 검사는 이 관측에서 실패합니다.

---

## 4. Reference

- [Foundry Book - Config](https://book.getfoundry.sh/config/)
- [Solidity Docs - Using the compiler](https://docs.soliditylang.org/en/latest/using-the-compiler.html)

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
