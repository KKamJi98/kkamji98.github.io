---
title: "온체인 디버깅 기초 - receipt, trace, finality [Blockchain 7]"
date: 2026-08-23 03:41:00 +0900
author: kkamji
categories: [Blockchain]
tags: [blockchain, ethereum, rpc, receipt, trace, finality, anvil, sepolia, study]
comments: true
image:
  path: /assets/img/blockchain/blockchain.webp
---

JSON-RPC가 HTTP 200을 돌려줘도 그 거래는 성공이 아닐 수 있습니다. receipt의 `status`가 `0x0`이면 실행은 되돌려졌고, 가스는 이미 소비되었습니다. explorer 화면의 빨간 실패 표시가 가리키는 값이 바로 그 필드입니다.

[이전 글](https://kkamji.net/posts/reentrancy-cei/)에서 출금 순서가 자금을 비울 수 있음을 확인했습니다. 이번에는 실패한 호출을 node가 어떻게 기록하는지를 봅니다. 배포와 실패 재현은 로컬 Anvil에서 했고, Sepolia 공개 RPC는 읽기만 했습니다. Anvil 기본 키로 공개망에 보내지 않았습니다. 전용 testnet 지갑이 없기 때문입니다.

---

## 1. estimate가 막으면 receipt가 생기지 않는다

Anvil에 `Probe` 컨트랙트를 배포했습니다. 주소는 `0xCf7Ed3AccA5a467e9e704C703E8D87F634fB0Fc9`입니다. `ping()`은 `1`을 반환합니다. `boom()`은 `revert("boom")`입니다.

처음 `cast send boom()`은 전송 전에 gas를 추정하다 멈췄습니다. node가 그 호출을 시뮬레이트한 뒤, 실행이 되돌려질 거래에는 가스를 배정하지 않은 것입니다. 이 단계에서는 receipt가 없습니다. explorer에 올라갈 tx hash도 없습니다.

```text
Error: Failed to estimate gas
execution reverted: boom
```

`--gas-limit 100000`을 주면 추정 단계를 건너뛰고 실제로 체인을 갱신합니다. 이때부터 receipt가 생깁니다. 실패를 관측하려면 실패를 블록에 넣어야 합니다.

---

## 2. receipt.status가 실행 결과다

강제 전송 뒤 receipt는 다음이었습니다.

```text
status              0x0
gasUsed             0x53f4   (21492)
blockNumber         0x5
type                0x2
logs                []
revertReason        boom
transactionHash     0x5e5d58bb...
```

`status=0x0`은 상태 트리가 그 호출 이전으로 되돌아갔다는 뜻입니다. 그래도 `gasUsed`는 21492입니다. revert도 EVM 실행이고, 실행한 만큼 가스를 걷습니다. `logs`가 빈 배열인 이유는 이벤트를 emit하기 전에 되돌려졌기 때문입니다.

같은 hash를 `cast run`으로 다시 실행하면 opcode 단위가 아니라 호출 단위 트레이스가 나옵니다.

```text
[428] 0xCf7Ed3Ac...::boom()
  └─ ← [Revert] boom
Gas used: 21492
```

explorer의 실패 화면이 보여주는 세 가지는 이 관측과 같습니다. 실패 여부(`status`), 소비 가스, revert 문자열입니다. HTTP 상태 코드는 여기 없습니다.

---

## 3. latest와 finalized는 다른 머리다

Anvil은 거래마다 블록을 만들고, `safe`/`finalized` 태그를 블록 JSON에 실어 주지 않았습니다. 공개 Sepolia node에 읽기만 요청하면 태그가 갈라집니다. 2026-08-23 관측값입니다.

```text
latest      11545002
safe        11544969    (latest - 33)
finalized   11544938    (latest - 64)
```

![JSON-RPC가 receipt status 0x0과 Sepolia finalized 높이를 서로 다른 답으로 돌려주는 구조](/assets/img/blockchain/receipt-finality-tags.webp)
_receipt.status는 그 거래의 실행 결과다. finalized는 그 node가 되돌리기 어렵다고 보는 블록 높이다._

`latest`는 지금 이 node가 보고 있는 끝입니다. `finalized`는 합의 관점에서 더 굳은 높이입니다. 64블록 차이는 reorg 창이 아직 남아 있다는 뜻입니다. indexer나 입금 confirmation 수를 `latest`에만 걸면, 그 창 안에서 같은 receipt가 다른 분기에 속할 수 있습니다.

이 숫자는 공개 RPC 한 곳의 한 시점입니다. 다른 node, 다른 시각이면 간격이 달라집니다. 변하지 않는 것은 태그 세 개가 같은 질문이 아니라는 점입니다.

---

## 4. 정리

실패한 거래는 estimate 단계에서 막히거나, 블록에 들어가 `status=0x0`으로 남습니다. 후자라야 receipt와 trace를 읽을 수 있습니다. 가스는 실패해도 소비되고, explorer가 보여주는 실패는 이 필드들입니다. 공개망 머리는 `latest`와 `finalized`가 다릅니다. HTTP 200은 둘 중 아무것도 보증하지 않습니다.

Sepolia에 컨트랙트를 올리지는 않았습니다. 배포와 faucet은 전용 testnet 지갑이 생긴 뒤에 이어서 합니다.

---

## 5. Reference

- [Ethereum Docs - JSON-RPC](https://ethereum.org/en/developers/docs/apis/json-rpc/)
- [Ethereum Docs - Blocks](https://ethereum.org/en/developers/docs/blocks/)
- [Foundry Book - Cast](https://book.getfoundry.sh/cast/)

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
