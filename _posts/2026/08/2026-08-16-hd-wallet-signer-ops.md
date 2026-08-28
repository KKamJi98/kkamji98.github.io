---
title: "블록체인 키 관리 기초 - HD wallet, signer, 운영키 [Blockchain 11]"
date: 2026-08-16 12:26:00 +0900
author: kkamji
categories: [Blockchain]
tags: [blockchain, keys, hd-wallet, signer, anvil, bitcoin, study]
comments: true
image:
  path: /assets/img/blockchain/blockchain.webp
---

Anvil을 켜면 계정 0의 address는 항상 `0xf39Fd6e5...`입니다. 그 값은 마법이 아닙니다. Foundry가 문서에 적어 둔 12단어 니모닉의 인덱스 0입니다. 그 문구를 아는 사람은 같은 개인키를 다시 계산할 수 있습니다.

[이전 글](https://kkamji.net/posts/consensus-bft-nakamoto-finality/)에서 머리가 갈라지거나 멈추는 모양을 봤습니다. 이번에는 그 머리에 서명을 넣는 키를 로컬에서만 다룹니다. 개인키와 전체 signature는 글에 적지 않습니다. 공개망 송신은 없습니다.

---

## 1. 공개 니모닉은 공개 키다

Anvil 기본 니모닉은 다음 12단어입니다.

```text
test test test test test test test test test test test junk
```

`cast wallet address --mnemonic`으로 인덱스를 바꿔 주소를 계산했습니다.

```text
index 0  0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266
index 1  0x70997970C51812dc3A010C7d01b50e0d17dc79C8
index 2  0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC
```

이 세 address는 4편, 9편에서 쓴 buyer, seller, arbiter와 같습니다. HD wallet는 한 시드에서 인덱스로 여러 키를 뽑습니다. 시드가 공개되면 인덱스를 숨겨도 소용이 없습니다.

![공개 니모닉에서 인덱스 0, 1, 2 address가 차례로 유도되는 구조](/assets/img/blockchain/hd-mnemonic-three-addresses.webp)
_같은 12단어다. 인덱스만 바꾸면 address가 바뀐다. 누구나 같은 계산을 할 수 있다._

운영 사고의 전형적인 모양은 이 문구를 Sepolia faucet에 넣는 일입니다. 로컬 실습용 키가 공개망 잔액을 갖게 되면, 그 잔액은 튜토리얼을 읽은 사람 모두의 것이 됩니다. 이번 랩은 그 키로 공개망에 보내지 않았습니다.

---

## 2. signer는 메시지와 address를 묶는다

일회성 키쌍을 만들어 메시지 `kkamji-week11-local-only`에 서명했습니다. signature 길이는 132자였습니다. `cast wallet verify --address`는 원문에서 성공했고, 메시지 끝에 `x`를 붙이면 종료 코드 1이었습니다.

```text
verify original   succeeded
verify tampered   exit 1
```

![원문 서명은 검증되고, 한 글자 변조는 실패하는 흐름](/assets/img/blockchain/sign-verify-tamper.webp)
_signature는 메시지 전체를 덮는다. 한 글자가 바뀌면 같은 키가 아니다._

1편의 InvalidSignature와 같은 층입니다. 여기서 추가된 것은 운영 절차입니다. 검증에 쓰는 것은 개인키가 아니라 address와 메시지와 signature입니다. 개인키는 signer 프로세스 안에만 있어야 합니다.

Bitcoin regtest에서 `getnewaddress week11`은 `bcrt1qn8cjsu25v4jc826h5lsy8v92g3fc0jmfswgg67`를 만들었습니다. 주소만 남기고 `dumpprivkey`는 실행하지 않았습니다. 백업이 필요하면 wallet 파일을 암호화해 옮기고, 화면에 개인키를 찍지 않습니다.

---

## 3. 운영키와 시드는 역할이 다르다

실습 체인에서 쓰는 키와, 나중에 노드나 배포 스크립트가 쓰는 키는 같은 시드에 두면 안 됩니다. Anvil 니모닉은 개발용입니다. 배포 signer는 그 문구와 분리된 키여야 하고, 가능하면 호스트에 니모닉 전체를 두지 않습니다.

구분만 적습니다.

- 개발키: 공개되어도 되는 잔액만. Anvil 기본 계정.
- 운영 signer: 한 역할만. 배포 또는 출금. 니모닉을 서버 디스크에 풀어 두지 않음.
- 백업 시드: 오프라인. 개발 노트북과 같은 곳에 두지 않음.

이번 랩은 개발키 유도와 일회성 서명만 했습니다. 하드웨어 signer나 원격 KMS는 붙이지 않았습니다.

---

## 4. 정리

HD wallet는 시드와 인덱스로 address를 계산합니다. Anvil 기본 12단어는 그 계산이 공개라는 뜻입니다. signer는 개인키를 밖으로 내지 않은 채 메시지에 서명하고, 검증은 address만으로 합니다. 메시지 한 글자가 바뀌면 검증은 실패합니다. 공개망에 그 개발키를 쓰지 않는 이유는 수학이 아니라, 그 시드를 아는 사람이 너무 많기 때문입니다.

---

## 5. Reference

- [Foundry Book - cast wallet](https://book.getfoundry.sh/reference/cast/cast-wallet)
- [Bitcoin Developer Guide - Wallets](https://developer.bitcoin.org/devguide/wallets.html)
- [Ethereum Docs - Accounts](https://ethereum.org/en/developers/docs/accounts/)

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
