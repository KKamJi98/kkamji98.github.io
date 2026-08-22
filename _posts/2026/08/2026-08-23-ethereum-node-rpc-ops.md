---
title: "이더리움 노드 운영 기초 - sync, peer, Engine JWT [Blockchain 8]"
date: 2026-08-23 04:27:00 +0900
author: kkamji
categories: [Blockchain]
tags: [blockchain, ethereum, rpc, node, sync, peer, jwt, anvil, sepolia, study]
comments: true
image:
  path: /assets/img/blockchain/blockchain.webp
---

로컬 Anvil에 `net_peerCount`를 보내면 HTTP는 200입니다. 본문은 peers 숫자가 아니라 JSON-RPC 오류입니다.

```text
HTTP/1.1 200 OK
{"jsonrpc":"2.0","id":1,"error":{"code":-32601,"message":"Method not found"}}
```

같은 포트에서 `eth_syncing`은 `false`이고 `net_listening`은 `true`입니다. 프로세스도 살아 있고, 소켓도 열려 있습니다. 그래도 이 endpoint는 네트워크의 머리가 아닙니다. chainId는 31337이고, `safe`와 `finalized`는 genesis에 붙어 있습니다.

[이전 글](https://kkamji.net/posts/receipt-trace-finality/)에서는 receipt의 실행 결과와 공개망 block tag가 다른 질문임을 확인했습니다. 이번에는 그 tag를 다시 외우지 않습니다. node 운영자가 HTTP 200 뒤에서 무엇을 보는지, Anvil이 그 검사 중 몇 개를 생략하는지를 봅니다. 거래는 보내지 않았습니다. 로컬 Anvil과 Sepolia 공개 RPC만 읽었습니다.

---

## 1. HTTP 200은 소켓의 답이다

JSON-RPC는 transport에 묶이지 않습니다. ethereum.org 문서는 같은 개념을 HTTP, socket, 같은 프로세스 안에서 쓸 수 있다고 적습니다. HTTP로 붙이면 응답 코드는 그 transport의 상태입니다. JSON-RPC의 `result`와 `error`는 그 위에 얹힌 또 다른 층입니다.

2026-08-22 19:25 UTC에 `http://127.0.0.1:8545`로 보낸 읽기 요청은 모두 HTTP 200이었습니다. 성공한 호출과 실패한 호출이 같은 상태 코드를 공유했습니다.

| method | HTTP | JSON-RPC |
| --- | --- | --- |
| `web3_clientVersion` | 200 | `anvil/v1.7.1` |
| `eth_syncing` | 200 | `false` |
| `net_listening` | 200 | `true` |
| `eth_blockNumber` | 200 | `0x5` |
| `net_peerCount` | 200 | error `-32601` |

load balancer나 컨테이너 probe가 `GET /` 또는 아무 POST의 200만 보면, 이 표를 한 줄로 압축합니다. "살아 있다." 운영자가 묻는 질문은 다릅니다. 이 프로세스가 지금 어느 chain의 어느 머리를 보고 있는가.

공개 Sepolia endpoint `https://ethereum-sepolia-rpc.publicnode.com`도 같은 시각에 HTTP 200이었습니다. 이쪽은 `net_peerCount`를 구현합니다. 값이 `0x1c`, 십진수 28이었습니다. 수 분 앞선 같은 URL의 관측은 `0x2d`, 십진수 45였습니다. 공개 RPC 한 주소가 항상 같은 프로세스, 같은 peer set을 가리키지는 않습니다. HTTP 200은 그 차이도 숨깁니다.

`web3_clientVersion`은 그 endpoint를 돌리는 소프트웨어를 말합니다. 같은 Sepolia URL을 같은 날 두 번 읽으면 client가 바뀌었습니다. 이전 조회는 `reth/v2.4.1-8eb2101/x86_64-unknown-linux-gnu`였고, 2026-08-22T20:12:03Z 조회는 `Geth/v1.17.1-stable-16783c16/linux-amd64/go1.25.7`이었습니다. 공개 RPC 한 주소가 항상 같은 프로세스를 가리키지는 않습니다. 운영 대시보드에 client 버전 하나를 올려 두고 "네트워크가 이 버전이다"라고 읽으면, 그 숫자는 그 순간의 문패입니다.

---

## 2. eth_syncing false는 따라잡았다가 아니다

ethereum.org JSON-RPC 문서는 `eth_syncing`이 sync 상태 객체 또는 `false`를 반환한다고 적습니다. 객체가 오면 최소한 `startingBlock`, `currentBlock`, `highestBlock`이 있습니다. Geth는 snap healing 같은 필드를 더 붙이고, Besu는 `pulledStates`와 `knownStates`를 붙입니다. client마다 본문은 달라도, 따라잡지 않았을 때 객체를 주고 따라잡았을 때 `false`를 주는 계약은 같습니다.

Execution API 명세의 요약도 같습니다. `eth_syncing`은 "sync status 또는 false"입니다.

Anvil 1.7.1은 `false`를 줍니다. Sepolia 공개 endpoint도 `false`를 줍니다. 같은 단어가 같은 운영 사실을 가리키지는 않습니다.

Anvil은 로컬 개발 체인입니다. Foundry Book은 이를 fast local Ethereum development node로 소개합니다. peer에게 header를 받아 state를 재구성할 대상이 없습니다. `false`는 "이미 네트워크 머리에 있다"가 아니라 "sync할 원격 머리가 없다"에 가깝습니다. 같은 프로세스의 `net_peerCount`가 method 자체를 모르는 것과 맞물립니다.

실제 노드에서 `false`는 더 좁은 뜻입니다. 그 client가 스스로 따라잡았다고 판단한다는 뜻입니다. 그 판단의 기준은 client와 sync mode에 달려 있습니다. ethereum.org는 execution layer sync를 full, fast, snap, light로 나눕니다. Geth 문서는 snap sync가 Mainnet 기본이며, 최근 머리 근처의 trusted checkpoint에서 시작해 최근 128 block state를 유지한다고 적습니다. 따라잡은 뒤에는 block-by-block import로 전환합니다.

따라잡는 동안 consensus client는 optimistic sync로 beacon block을 먼저 받을 수 있습니다. Geth 문서는 이 구간에서 노드가 attest하거나 propose하면 안 된다고 못 박습니다. 아직 자기 머리가 맞다고 보증하지 못하기 때문입니다. JSON-RPC 이용자에게 이 구간은 `eth_syncing` 객체, 오래된 `latest` timestamp, 비정상적으로 벌어진 tag 간격으로 보입니다. HTTP 200과 `eth_blockNumber` 숫자는 계속 나옵니다. 숫자는 증가할 수 있고, 그래도 네트워크의 끝이 아닐 수 있습니다.

이번 실습에서는 따라잡는 중인 객체를 직접 보지 못했습니다. Anvil과 공개 Sepolia가 둘 다 `false`를 줬기 때문입니다. 운영 규칙만 문서와 대조합니다. `false`를 "최신이다"로 번역하지 말고, "이 client는 더 이상 import 중이라고 표시하지 않는다"로 읽습니다.

---

## 3. 노드 하나는 클라이언트가 둘이다

ethereum.org는 The Merge 이후 노드를 execution client와 consensus client의 쌍으로 정의합니다. execution client는 거래를 검증하고, EVM을 돌리고, state와 txpool을 들고, 사용자 JSON-RPC를 엽니다. consensus client는 peer에게 beacon block과 attestation을 받아 fork choice를 돌리고, justification과 finality를 추적합니다. validator는 선택입니다. 32 ETH를 스테이킹해야 propose와 attest에 참여합니다. RPC만 제공하는 노드는 validator 없이 두 client만으로도 머리를 따라갑니다.

두 client는 서로 다른 P2P 네트워크를 봅니다. execution layer는 거래를 gossip하고, consensus layer는 block과 투표를 gossip합니다. 사용자 지갑이 붙는 포트는 보통 execution client의 JSON-RPC입니다. 기본값은 8545입니다. 머리가 앞으로 가는 동력은 그 포트가 아닙니다.

두 client를 잇는 내부 인터페이스가 Engine API입니다. 명세는 execution-apis 저장소의 authentication 문서에 있습니다. Engine API는 기존 JSON-RPC와 다른 포트에 열려야 하고, 기본값은 8551입니다. HTTP 요청마다 JWT를 붙입니다. 알고리즘은 HMAC-SHA256입니다. `alg=none`은 거절합니다. 필수 claim은 `iat`뿐이며, execution client는 현재 시각에서 앞뒤 60초를 벗어난 token을 받지 않아야 합니다. WebSocket은 handshake만 인증하고, 같은 머신의 IPC는 파일 접근 권한을 이미 가진 것으로 보고 추가 인증을 요구하지 않습니다.

이 인증이 막으려는 공격은 분명합니다. Engine 포트가 인터넷에 노출되거나, 브라우저가 그 포트에 메시지를 넣는 경우입니다. 막지 않는 것도 분명합니다. 네트워크를 읽을 수 있는 공격자의 도청과 replay입니다. JWT 파일은 hex로 인코딩된 256 bit 비밀입니다. 운영자가 경로를 지정하지 않으면 client가 실행 중에 `jwt.hex`를 만들고, 상대 client에게 그 파일을 넘깁니다. 파일을 읽지 못하거나 길이가 맞지 않으면 authenticated port를 열지 않거나 기동을 중단해야 합니다.

Prysm 문서는 beacon node가 execution node에 HTTP로 붙을 때만 이 절차가 필요하다고 적습니다. IPC면 JWT를 건너뜁니다. Geth 예시는 `--authrpc.jwtsecret`으로 같은 파일을 가리키고, Besu는 `--engine-jwt-secret`을 씁니다. 운영 사고의 전형적인 모양은 JSON-RPC 8545는 응답하는데 Engine 8551의 비밀이 어긋난 상태입니다. 지갑은 balance를 읽고, consensus client는 payload를 실행시키지 못합니다. `latest`는 멈추거나, 아주 천천히만 움직입니다. HTTP health는 여전히 200입니다.

Anvil에는 이 경계가 없습니다. 같은 시각에 `engine_exchangeCapabilities`와 `engine_getClientVersionV1`은 `-32601 Method not found`였습니다. `parentBeaconBlockRoot`는 32바이트 0이었습니다. 로컬 개발 노드는 consensus client를 옆에 두지 않습니다. 그래서 `safe`와 `finalized`를 받아도 합의 머리를 따라가지 않습니다.

![사용자 JSON-RPC는 8545로 들어가고, consensus client는 JWT로 보호된 8551에서 execution client를 구동한다](/assets/img/blockchain/el-cl-engine-jwt.webp)
_지갑이 보는 포트와 머리를 밀어 주는 포트는 다릅니다. Anvil은 후자를 구현하지 않습니다._

---

## 4. peer 수와 listening은 다른 층이다

ethereum.org는 `net_listening`을 "네트워크 연결을 듣고 있으면 true"로, `net_peerCount`를 "지금 붙은 peer 수"로 정의합니다. 둘 다 execution client JSON-RPC의 gossip 층입니다. consensus client의 peer는 Beacon API 쪽에 있습니다. 한쪽이 충분하고 다른 쪽이 비면, 거래는 들어오는데 새 block이 안 오거나, 그 반대가 됩니다.

Anvil은 `net_listening=true`를 줍니다. 8545에서 HTTP를 받고 있다는 뜻으로 읽히면 과합니다. 같은 프로세스가 peer 수 조회 자체를 모릅니다. `admin_peers`와 `admin_nodeInfo`도 `-32601`입니다. 개발 노드는 P2P mesh의 일원이 아닙니다. listening 플래그만으로 "네트워크에 붙어 있다"고 쓰면, Anvil과 실제 노드를 같은 문장에 넣게 됩니다.

Sepolia 공개 endpoint는 listening true와 peer 28을 함께 줬습니다. 이 숫자는 그 순간의 그 backend입니다. 공개 제공자는 앞단에 여러 노드를 둘 수 있고, 같은 URL이 다음 요청에서 다른 인스턴스로 갈 수 있습니다. peer 45에서 28로 바뀐 관측을 "네트워크가 갑자기 고립됐다"로 읽으면 안 됩니다. 자기 집 노드를 운영할 때는 그 해석이 맞을 수 있습니다. 공개 RPC를 빌려 쓸 때는 그 숫자가 자기 운영 지표가 아닙니다.

실행 계층 peer가 0에 가까워지면 `eth_syncing`이 `false`여도 머리가 멈춥니다. 이미 따라잡은 노드가 고립되면, client는 더 이상 import 중이라고 표시하지 않습니다. 표시할 상대가 없기 때문입니다. 이때 봐야 하는 값은 peer 수와 `latest`의 timestamp입니다. block 높이는 어제 숫자 그대로일 수 있고, HTTP는 오늘도 200입니다.

---

## 5. head와 safe, finalized의 간격은 상수가 아니다

ethereum.org는 block parameter를 이렇게 나눕니다. `latest`는 가장 최근에 제안된 block, `safe`는 가장 최근의 safe head, `finalized`는 가장 최근에 finalized된 block입니다. 이 정의 자체는 이전 글에서 이미 썼습니다. 운영자가 가져가야 하는 것은 정의가 아니라 간격의 움직임입니다.

같은 Sepolia 공개 endpoint를 같은 날 세 번 읽었습니다. 이전 글의 관측은 `latest 11545002`, `safe 11544969`, `finalized 11544938`이었습니다. 간격은 33과 64였습니다. 같은 날 두 번째 조회는 간격이 56과 88로 벌어졌고 client는 reth였습니다. 2026-08-22T20:12:03Z의 세 번째 조회는 다음이었습니다.

```text
client      Geth/v1.17.1-stable
latest      11545282
safe        11545249    (latest - 33)
finalized   11545218    (latest - 64)
peerCount   37
```

간격이 33/64에서 56/88로 벌어졌다가 다시 33/64로 돌아왔습니다. proof-of-stake에서 slot은 12초, epoch는 32 slot입니다. 그 자리수와 비슷한 간격이 나오기도 하지만, 이 숫자를 운영 상수로 외우면 안 됩니다. 공개 RPC의 지연, 빈 slot, 관측 시각, 그리고 그 URL이 가리키는 인스턴스가 간격을 바꿉니다.

Anvil은 같은 호출을 다른 방식으로 붕괴시킵니다.

```text
latest      5     0x2b20b981...
safe        0     0xd42a17af...
finalized   0     0xd42a17af...
```

tag 이름은 받습니다. 합의 머리는 없습니다. `safe`와 `finalized`는 같은 genesis hash입니다. `latest`만 로컬에서 만든 block 5를 가리킵니다. 개발 테스트가 `finalized`를 쓰면, 방금 보낸 거래가 보이지 않습니다. HTTP는 200이고 본문은 유효한 block JSON입니다. 틀린 머리를 정확한 형식으로 돌려준 것입니다.

indexer나 입금 확인을 `latest`에만 걸면, 공개망에서는 reorg 창 안의 receipt를 확정으로 취급합니다. Anvil에서는 그 창이 존재하지 않거나, 반대로 `finalized`가 영원히 genesis에 남습니다. 같은 메서드, 같은 tag, 다른 운영 의미입니다.

![HTTP 200 뒤에는 syncing, peer 오류, latest와 finalized 간격이 서로 다른 답으로 갈라진다](/assets/img/blockchain/http-200-is-not-chain-head.webp)
_소켓이 살아 있는 것과 이 노드가 네트워크 머리를 보고 있는 것은 다른 검사입니다._

---

## 6. Anvil은 노드의 모양만 빌려 온다

한 시각의 읽기만으로도 개발 노드와 공개망 노드의 차이가 표로 떨어집니다. 거래는 없습니다. 상태 조회뿐입니다.

| 검사 | Anvil 1.7.1 | Sepolia publicnode |
| --- | --- | --- |
| HTTP | 200 | 200 |
| `web3_clientVersion` | `anvil/v1.7.1` | `Geth/v1.17.1-...` (직전 같은 URL은 reth) |
| `eth_chainId` | 31337 | 11155111 |
| `eth_syncing` | `false` | `false` |
| `net_listening` | `true` | `true` |
| `net_peerCount` | method not found | 37 |
| `latest` | 5 | 11545282 |
| `safe` / `finalized` | 둘 다 0, 같은 genesis | 11545249 / 11545218 |
| Engine API | method not found | 이 endpoint에서 확인하지 않음 |
| `admin_*` | method not found | 호출하지 않음 |

Anvil이 대신하는 것은 EVM과 JSON-RPC의 일부입니다. account, nonce, gas, receipt, `eth_call`은 로컬에서 재현할 수 있습니다. 운영자가 보는 나머지, 즉 peer, sync 진행, Engine JWT, beacon root, 살아 움직이는 finality는 빠져 있습니다. `txpool_status`는 `pending 0`, `queued 0`을 줬습니다. 로컬에서 거래를 넣지 않았으니 그 값은 맞습니다. 그 값이 "네트워크 mempool이 비어 있다"는 뜻은 아닙니다.

Foundry의 `--fork-url`은 이 경계를 더 흐립니다. fork된 Anvil은 원격 상태를 가져와 로컬에서 실행하지만, 그 순간부터 원격 합의를 따라가지 않습니다. fork 높이 위의 `latest`는 다시 로컬 머리가 됩니다. HTTP 200과 `eth_syncing false`는 그대로입니다. fork를 운영 노드의 대체재로 쓰면, 배포 대상 네트워크의 peer와 finality를 검증했다고 착각하게 됩니다.

이번 실습의 Anvil `latest` hash `0x2b20b981...`에는 이전 글에서 남긴 로컬 거래가 들어 있습니다. 그 거래의 실행 결과는 여기서 다시 풀지 않습니다. 운영 관점에서 중요한 것은, 그 block이 누구의 peer에도 전파되지 않았다는 점입니다. 같은 머신의 다음 Anvil 프로세스가 뜨면 그 머리는 사라집니다.

---

## 7. 운영자가 실제로 보는 순서

노드를 띄운 뒤 운영자가 묻는 질문은 애플리케이션 개발자의 질문과 순서가 다릅니다. 개발자는 "이 호출이 revert인가"를 먼저 봅니다. 운영자는 "이 프로세스가 지금 어느 네트워크의 어느 머리를 말하는가"를 먼저 봅니다.

첫 검사는 transport입니다. 포트가 열려 있고 HTTP 200이 나오는지. 여기서 멈추면 Anvil의 `net_peerCount` 오류도 정상으로 보입니다. 본문의 `error` 필드를 읽어야 합니다.

둘째는 `eth_syncing`입니다. 객체가 오면 아직 import 중입니다. `currentBlock`과 `highestBlock`의 차이를 봐야 합니다. `false`면 따라잡았거나, 따라잡을 대상이 없거나, 고립되어 표시할 상대가 없는 것입니다. 세 경우를 이 필드 하나로 구분하지 않습니다.

셋째는 peer입니다. execution client의 `net_peerCount`와, 가능하면 consensus client의 peer를 따로 봅니다. 한쪽만 보면 거래만 들어오거나 block만 들어오는 장애를 놓칩니다. Anvil처럼 메서드가 없으면 그 노드는 mesh의 일원이 아닙니다.

넷째는 머리의 나이입니다. `latest`의 timestamp가 slot 간격보다 훨씬 오래됐으면, 높이가 커 보여도 멈춘 머리입니다. 12초 slot을 기준으로 수 분 이상 멈춰 있으면 공개망 노드로서는 이미 사건입니다.

다섯째는 tag 간격입니다. `latest`, `safe`, `finalized`를 같은 endpoint, 같은 시각에 읽습니다. 간격이 평소보다 벌어지면 합의가 늦거나, 그 노드가 합의 머리를 못 따라가거나, 공개 RPC가 지연되는 것입니다. 간격을 상수로 저장해 두고 비교하지 않습니다. 직전 관측과 비교합니다.

여섯째는 Engine 경로입니다. 자기 집 노드라면 JWT 파일 권한, 8551의 수신, consensus client 로그의 authentication 실패를 봅니다. 공개 RPC를 빌려 쓰는 쪽은 이 경로를 직접 보지 못합니다. 보지 못한다는 사실 자체가 신뢰 경계입니다. 남이 굴리는 execution client의 Engine 포트가 살아 있는지는 `eth_blockNumber`가 증명하지 않습니다.

![운영 점검은 HTTP 200에서 시작해 sync, peer, timestamp, tag 간격, Engine JWT 순으로 내려간다](/assets/img/blockchain/operator-health-ladder.webp)
_한 칸이 통과해도 다음 칸이 실패할 수 있습니다. Anvil은 아래 칸 여러 개를 구현하지 않습니다._

디스크와 sync mode는 이 사다리의 배경입니다. ethereum.org는 full node가 최근 데이터를 남기고 오래된 state를 지운다고 적습니다. archive node는 genesis부터 지운 적이 없습니다. snap sync는 빠르고 디스크를 덜 쓰지만, 오래된 높이의 `eth_getBalance`가 로컬에 없을 수 있습니다. HTTP 200에 `null`이나 오류가 오면, 네트워크가 죽은 것이 아니라 그 노드의 보존 범위 밖일 수 있습니다. 이번 실습은 현재 머리만 읽었고, archive 여부를 확인하지 않았습니다.

---

## 8. 공개 RPC는 남의 노드다

자기 노드를 돌리는 이유는 ethereum.org가 짧게 적습니다. 데이터를 스스로 검증하고, 주소와 잔액을 중개자에게 넘기지 않고, 필요한 서비스를 자기 RPC 위에 올립니다. 그 대가는 디스크와 대역폭과 두 client의 유지입니다. 최소 사양 숫자는 해마다 바뀌므로 ethereum.org의 run-a-node 페이지를 그 시점 기준으로 봐야 합니다.

공개 RPC는 그 비용을 대신 냅니다. 그 대가로 운영 사다리의 아래칸을 잃습니다. peer 수는 제공자의 backend이고, Engine JWT는 보이지 않으며, `eth_syncing false`는 그 인스턴스의 자기 신고입니다. 같은 URL의 client가 reth에서 Geth로 바뀐 관측이 그 한계를 보여 줍니다. 이번 실습은 제공자 하나를 읽었고, 다른 제공자와 교차 비교는 하지 않았습니다.

읽기만 하는 실습에서는 그 한계를 그대로 수용합니다. 쓰기를 열면 한계가 사고가 됩니다. Anvil 기본 키를 공개망에 재사용하지 않는 이유와 같습니다. 남의 노드에 보내는 거래는 그 노드의 mempool과 그 노드의 peer 집합을 통과합니다. HTTP 200은 그 경로를 보증하지 않습니다.

---

## 9. 정리

JSON-RPC의 HTTP 200은 소켓이 본문을 돌려줬다는 뜻입니다. `eth_syncing false`는 그 client가 import 중이라고 표시하지 않는다는 뜻입니다. `net_listening true`는 네트워크 mesh의 일원이라는 뜻이 아닙니다. Anvil은 이 세 값을 동시에 주면서 peer 메서드와 Engine API를 갖지 않습니다. 공개 Sepolia 노드는 같은 세 값 위에 실제 peer와 움직이는 `safe`/`finalized` 간격을 올립니다. 그 간격은 같은 날에도 33/64에서 56/88로 변했습니다.

운영자의 점검은 이 순서를 내려갑니다. transport, sync 표시, peer, 머리의 나이, tag 간격, 그리고 자기 노드라면 Engine JWT. 한 칸의 성공을 다음 칸의 성공으로 옮기지 않습니다. 개발 체인은 위칸만으로도 충분할 때가 많습니다. 그 충분함을 공개망 노드의 건강으로 읽지 않으면 됩니다.

---

## 10. Reference

- [Ethereum Docs - Nodes and clients](https://ethereum.org/en/developers/docs/nodes-and-clients/)
- [Ethereum Docs - Node architecture](https://ethereum.org/en/developers/docs/nodes-and-clients/node-architecture/)
- [Ethereum Docs - JSON-RPC](https://ethereum.org/en/developers/docs/apis/json-rpc/)
- [Ethereum Docs - Spin up your own Ethereum node](https://ethereum.org/en/developers/docs/nodes-and-clients/run-a-node/)
- [Ethereum Docs - Proof-of-stake](https://ethereum.org/en/developers/docs/consensus-mechanisms/pos/)
- [Execution APIs - Engine authentication](https://github.com/ethereum/execution-apis/blob/main/src/engine/authentication.md)
- [Execution APIs - eth_syncing](https://github.com/ethereum/execution-apis/blob/main/src/eth/client.yaml)
- [Geth Docs - Sync modes](https://geth.ethereum.org/docs/fundamentals/sync-modes)
- [Prysm Docs - Configure JWT authentication](https://docs.prylabs.network/docs/execution-node/authentication)
- [Foundry Book - Anvil](https://book.getfoundry.sh/reference/anvil/)

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
