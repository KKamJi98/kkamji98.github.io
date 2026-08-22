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

JSON-RPC가 HTTP 200을 돌려줘도 그 거래는 성공이 아닐 수 있습니다. receipt의 `status`가 `0x0`이면 실행은 되돌려졌고, gas는 이미 소비되었습니다. explorer 화면의 빨간 실패 표시가 가리키는 값이 바로 그 필드입니다.

[이전 글](https://kkamji.net/posts/reentrancy-cei/)에서 출금 순서가 자금을 비울 수 있음을 확인했습니다. 이번에는 실패한 호출을 node가 어떻게 기록하는지를 봅니다. deploy와 실패 재현은 로컬 Anvil에서 했고, Sepolia 공개 RPC는 읽기만 했습니다. Sepolia에 contract를 올리지 않았습니다. Anvil 기본 키로 공개망에 보내지 않았습니다. 전용 testnet wallet이 없기 때문입니다.

---

## 1. estimate가 막으면 receipt가 없다

Anvil에 `Probe` contract를 deploy했습니다. address는 `0xCf7Ed3AccA5a467e9e704C703E8D87F634fB0Fc9`입니다.

```solidity
contract Probe {
    function ping() external pure returns (uint256) {
        return 1;
    }

    function boom() external pure {
        revert("boom");
    }
}
```

`ping()`은 `1`을 반환합니다. deploy가 깨진 것이 아니라, `boom()`만 의도적으로 되돌아갑니다.

처음 `cast send boom()`은 전송 전에 gas를 추정하다 멈췄습니다. node가 그 호출을 시뮬레이트한 뒤, 실행이 되돌려질 거래에는 gas를 배정하지 않은 것입니다. 이 단계에서는 receipt가 없습니다. explorer에 올라갈 tx hash도 없습니다.

```text
Error: Failed to estimate gas
execution reverted: boom
```

실패를 시뮬레이트한 것과 실패를 block에 넣는 것은 다른 객체입니다. 전자는 에러 문자열만 남고, 후자라야 `status`와 `gasUsed`를 읽을 수 있습니다.

![cast send가 gas를 추정하다 boom으로 멈추면 receipt와 tx hash가 생기지 않는 흐름](/assets/img/blockchain/receipt-estimate-blocked.webp)
_estimate 실패는 체인을 갱신하지 않는다. 읽을 receipt가 없다._

---

## 2. gas-limit을 주면 실패한 거래가 block에 남는다

`--gas-limit 100000`을 주면 추정 단계를 건너뛰고 실제로 체인을 갱신합니다. 강제 전송 뒤 receipt는 다음이었습니다.

```text
status              0x0
gasUsed             0x53f4   (21492)
blockNumber         0x5
type                0x2
logs                []
revertReason        boom
transactionHash     0x5e5d58bb...
```

`status=0x0`은 상태 트리가 그 호출 이전으로 되돌아갔다는 뜻입니다. 그래도 `gasUsed`는 21492입니다. revert도 EVM 실행이고, 실행한 만큼 gas를 걷습니다. `logs`가 빈 배열인 이유는 이벤트를 emit하기 전에 되돌려졌기 때문입니다. `blockNumber=0x5`는 그 실패가 Anvil block 5에 들어갔다는 뜻입니다.

![gas-limit을 준 boom 호출이 Anvil block에 들어가 receipt status 0x0을 남기는 흐름](/assets/img/blockchain/receipt-forced-status.webp)
_강제 전송이라야 실패가 block에 남는다. status 0x0이어도 gasUsed는 21492다._

같은 hash를 `cast run`으로 다시 실행하면 opcode 단위가 아니라 호출 단위 트레이스가 나옵니다. 이건 새 거래가 아닙니다. 이미 있는 receipt를 로컬에서 재생한 것입니다.

```text
[428] 0xCf7Ed3Ac...::boom()
  └─ ← [Revert] boom
Gas used: 21492
```

explorer의 실패 화면이 보여주는 세 가지는 이 관측과 같습니다. 실패 여부(`status`), 소비 gas, revert 문자열입니다. HTTP 상태 코드는 여기 없습니다.

---

## 3. latest와 finalized는 다른 머리다

Anvil은 거래마다 block을 만들고, `safe` / `finalized` 태그를 block JSON에 실어 주지 않았습니다. 공개 Sepolia node에 읽기만 요청하면 태그가 갈라집니다. 2026-08-23, `https://ethereum-sepolia-rpc.publicnode.com` 한 시점의 값입니다.

```text
latest      11545002
safe        11544969    (latest - 33)
finalized   11544938    (latest - 64)
```

이 세 숫자는 Sepolia에 무엇을 deploy해서 얻은 값이 아닙니다. `eth_getBlockByNumber`에 태그 세 개를 읽은 결과입니다. faucet도 쓰지 않았고, 전용 testnet wallet도 없습니다.

![같은 Sepolia node에서 latest 11545002, safe 11544969, finalized 11544938이 서로 다른 높이인 구조](/assets/img/blockchain/sepolia-head-tags.webp)
_latest는 지금 이 node의 끝이다. finalized는 그보다 64block 뒤다. 이 간격은 그 시점의 공개 RPC 한 곳이다._

`latest`는 지금 이 node가 보고 있는 끝입니다. `safe`는 그 node가 더 덜 흔들린다고 보는 높이입니다. `finalized`는 합의 관점에서 더 굳은 높이입니다. 64block 차이는 reorg 창이 아직 남아 있다는 뜻으로 읽습니다. indexer나 입금 confirmation 수를 `latest`에만 걸면, 그 창 안에서 같은 receipt가 다른 분기에 속할 수 있습니다.

33과 64는 위 세 높이의 뺄셈입니다. 다른 node, 다른 시각이면 간격이 달라집니다. 변하지 않는 것은 태그 세 개가 같은 질문이 아니라는 점입니다.

---

## 4. 정리

실패한 거래는 estimate 단계에서 막히거나, block에 들어가 `status=0x0`으로 남습니다. 후자라야 receipt와 trace를 읽을 수 있습니다. gas는 실패해도 소비되고, explorer가 보여주는 실패는 이 필드들입니다. 공개망 머리는 `latest`와 `safe`와 `finalized`가 다릅니다. HTTP 200은 둘 중 아무것도 보증하지 않습니다.

Sepolia에 contract를 올리지는 않았습니다. 태그 숫자는 읽기 전용 조회입니다.

---

## 5. Reference

- [Ethereum Docs - JSON-RPC](https://ethereum.org/en/developers/docs/apis/json-rpc/)
- [Ethereum Docs - Blocks](https://ethereum.org/en/developers/docs/blocks/)
- [Foundry Book - Cast](https://book.getfoundry.sh/cast/)

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
