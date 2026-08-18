---
title: "비트코인 트랜잭션과 UTXO 알아보기 - 잔액의 실체, 수수료, 컨펌 [Blockchain 2]"
date: 2026-08-19 02:40:00 +0900
author: kkamji
categories: [Blockchain]
tags: [blockchain, bitcoin, utxo, transaction, fee, regtest, study]
comments: true
image:
  path: /assets/img/blockchain/blockchain.webp
---

블록 탐색기에서 비트코인 지갑을 열면 잔액이 딱 붙어 나옵니다. 그런데 비트코인의 데이터 구조 어디에도 잔액이라는 필드는 없습니다. `balance`라는 저장된 값을 읽어온다면 어디에 들어 있을까요. 답은 없음입니다. 잔액은 저장되지 않고, 미사용 출력(UTXO)을 전부 모아 합한 값을 매번 계산해서 보여줄 뿐입니다.

해시 체인, 서명, Merkle Tree가 기록의 무결성을 담당한다는 것은 [이전 글](https://kkamji.net/posts/blockchain-crypto-foundations/)에서 확인했습니다. 그 기록 위에서 돈은 미사용 출력이라는 형태로 존재합니다. 지갑의 잔액이 왜 파생값인지, 거래가 미사용 출력을 어떻게 소비하는지, 수수료가 어디로 사라지는지를 Python 시뮬레이터와 Bitcoin Core regtest 노드로 직접 확인합니다. 실습은 로컬 테스트넷인 regtest에서 진행하므로 실제 비용은 발생하지 않습니다.

---

## 1. 잔액은 어디에도 저장되어 있지 않다

은행은 계좌라는 상자에 잔액 숫자를 넣어두고 이체마다 숫자를 더하고 뺍니다. 비트코인은 반대입니다. 장부에는 트랜잭션의 출력(output)만 있고, 아직 소비되지 않은 출력의 목록이 곧 돈입니다.

UTXO(Unspent Transaction Output)는 한 트랜잭션이 만든 출력 중 아직 다른 트랜잭션의 입력으로 쓰이지 않은 것을 말합니다. 어떤 주소의 잔액을 알고 싶으면 그 주소가 받을 수 있는 UTXO를 전부 찾아 금액을 합칩니다. 잔액 조회가 읽기 연산이 아니라 계산이라는 점이 은행 모델과 근본적으로 다릅니다.

이 구조의 이점은 검증의 단순함입니다. 새 트랜잭션이 도착하면 노드는 참조하는 출력이 UTXO 집합에 존재하는지만 확인하면 됩니다. 이중지출은 짝이 없는 출력, 즉 이미 소비된 출력을 참조하는 순간 그 자체로 거부됩니다. 잔액을 따로 보관하는 시스템이라면 모든 계좌의 정합성을 별도로 증명해야 하지만, UTXO 모델에서는 장부와 UTXO 집합 하나로 끝납니다.

---

## 2. 거래는 출력을 통째로 소비한다

가장 자주 잘못 이해되는 규칙이 이것입니다. UTXO는 부분적으로 쓸 수 없습니다. 50 BTC짜리 출력에서 1.5 BTC만 보내는 것이 아니라, 50 BTC 출력 전체를 입력으로 소비하고 두 개의 새 출력을 만듭니다. 수신자에게 가는 1.5 BTC와 나에게 돌아오는 잔돈 48.5 BTC입니다.

![트랜잭션이 UTXO를 통째로 소비하고 payment와 change 두 출력을 만드는 구조](/assets/img/blockchain/utxo-reference-structure.webp)
_입력 50 BTC가 통째로 소비되고, payment 1.5 BTC와 change 48.4999859 BTC라는 두 개의 새 UTXO가 만들어진다. fee 0.0000141 BTC는 어떤 출력에도 존재하지 않는다._

실제 관측으로 확인했습니다. Bitcoin Core 31.1을 regtest 모드로 로컬에 띄우고 블록을 채워 만든 코인베이스 UTXO 50 BTC에서 1.5 BTC를 송금했습니다.

```text
vin 1:
  prevout 7396e66d1971c020...:0   <- 50 BTC 출력을 통째로 소비
vout 2:
  [0]        1.5 BTC -> bcrt1qtvhq...   (수신자)
  [1] 48.4999859 BTC -> bcrt1qemaw...   (잔돈, 내 주소로)
size 222 vsize 141
```

거래 뒤의 상태 변화가 이 모델을 더 명확히 보여줍니다. 소비된 출력은 `gettxout` 조회에 null을 반환합니다. 출력이 UTXO 집합에서 제거된 것입니다. 잔돈 48.4999859 BTC는 기존 잔액에서 깎이는 게 아니라 아예 새로운 txid:vout 쌍의 UTXO로 등장합니다. 지갑의 50 BTC가 48.5 BTC로 수정된 것이 아니라, 낡은 50 BTC 지폐가 회수되고 새 48.5 BTC 지폐가 발행된 것에 가깝습니다.

---

## 3. 수수료는 어떤 출력에도 존재하지 않는다

입력의 합에서 출력의 합을 빼면 수수료입니다. 관측한 거래에서 입력은 50 BTC, 출력은 1.5 + 48.4999859 = 49.9999859 BTC, 따라서 수수료는 0.0000141 BTC입니다.

여기서 흥미로운 점은 이 0.0000141 BTC가 어느 누구의 지갑에도 속하지 않는다는 것입니다. 수수료를 담은 UTXO는 존재하지 않습니다. 거래 직후 전체 UTXO 합계를 계산하면 정확히 수수료만큼 줄어 있습니다. 수수료는 일단 장부에서 사라지고, 그 거래를 블록에 담은 채굴자가 코인베이스 거래를 통해 회수합니다. 채굴 보상이 블록 생성 보상과 수수료의 합으로 구성되는 이유가 여기에 있습니다.

수수료는 크기에 비례합니다. 관측한 거래는 vsize 141 vB였고 수수료 1410 sat, 즉 10 sat/vB입니다. 같은 금액이라도 입력이 많거나 스크립트가 복잡하면 vsize가 커지고 수수료도 올라갑니다. 이것이 소액 UTXO가 쌓이면 잔액은 있는데 이체 수수료가 부담되는 먼지(dust) 문제로 이어지는 구조적 이유입니다.

---

## 4. Python 미니 장부로 규칙 재현하기

지금까지의 규칙을 표준 라이브러리만으로 재현하는 시뮬레이터를 만들어 확인했습니다. 핵심 자료구조는 딕셔너리 하나입니다. 키가 txid:vout 쌍이고 값이 소유자와 금액입니다.

```python
class UtxoLedger:
    def __init__(self):
        self.utxos = {}  # (txid, vout) -> {"owner": str, "amount": float}

    def balance(self, owner):
        """잔액은 UTXO를 전부 훑어 계산하는 파생값이다."""
        return sum(u["amount"] for u in self.utxos.values()
                   if u["owner"] == owner)

    def spend(self, sender, recipient, amount, fee=0.0):
        # 1) 금액을 채울 때까지 UTXO를 "통째로" 꺼낸다
        picked, total = [], 0.0
        for (tid, vout), u in list(self.utxos.items()):
            if u["owner"] != sender:
                continue
            picked.append((tid, vout, u["amount"]))
            total += u["amount"]
            del self.utxos[(tid, vout)]
            if total >= amount + fee:
                break
        if total < amount + fee:
            raise ValueError("insufficient")  # 부족하면 롤백

        # 2) 수신자 출력 + 잔돈 출력을 "새 UTXO"로 발행한다
        outputs = [(recipient, amount)]
        change = round(total - amount - fee, 8)
        if change > 0:
            outputs.append((sender, change))
        ...
```

동작 검증은 테스트로 남겼습니다. 잔액이 UTXO 스캔의 파생값인 것, 50 BTC에서 30 BTC를 보내면 잔돈 20 BTC가 새 UTXO로 돌아오는 것, 수수료만큼 전체 UTXO 합계가 감소하고 그 값을 담은 UTXO는 없는 것, 잔액 부족 시 원자적으로 롤백되는 것까지 5개 테스트가 전부 통과합니다.

```text
02_utxo_behavior_test.py::test_balance_is_derived_from_utxos PASSED
02_utxo_behavior_test.py::test_spend_consumes_whole_utxo_and_returns_change PASSED
02_utxo_behavior_test.py::test_fee_is_lost_by_sender_and_no_partial_spend PASSED
02_utxo_behavior_test.py::test_overspend_is_rejected_and_rolls_back PASSED
02_utxo_behavior_test.py::test_dust_edge_zero_change_has_single_output PASSED
5 passed in 0.02s
```

시뮬레이터가 진짜 비트코인 규칙을 따르는지는 regtest 관측과 대조했습니다. 통째로 소비, 잔돈의 새 UTXO 발행, 수수료의 비존재, 파생되는 잔액까지 네 규칙이 실제 노드의 동작과 일치했습니다. 시뮬레이터 코드는 표준 라이브러리만 사용하므로 설치 없이 재현할 수 있습니다.

---

## 5. 컨펌은 UTXO 집합의 확정이다

거래를 보내고 블록에 담기 전, 즉 mempool에 있는 동안에도 잔액 계산은 동작하지만 그 거래가 소비하려는 UTXO는 잠긴 상태가 됩니다. 셀프 전송 트랜잭션을 mempool에 넣어두면 잔돈으로 받을 UTXO가 아직 확정되지 않았기 때문에 그다음 전송이 그 UTXO를 쓰지 못합니다. 실습 중 0.5 BTC를 자신에게 보내는 거래를 만들었을 때, 확정 전까지 지갑의 잔돈 UTXO가 사용 불가 상태로 잠기는 것을 관찰했습니다.

블록 하나를 더 채굴하자 잠금이 풀렸습니다. 수신 출력 0.5 BTC와 잔돈 출력이 각각 별도의 UTXO로 확정되어 목록에 나타납니다. 컨펌이란 달리 말하면 이 거래가 만드는 UTXO 변경이 체인 합의에 편입되었음을 뜻합니다. 컨펌 수가 쌓일수록 되돌리기 어려워지는 리오그 전파 가능성까지 고려하면, 실무에서 6컨펌을 기다리는 관행은 이 확정의 신뢰도를 확률적으로 높이는 절차입니다.

---

## 6. 정리

비트코인의 돈은 계좌가 아니라 미사용 출력이라는 사실에서 나머지가 따라옵니다. 잔액은 저장값이 아니라 UTXO 집합의 합계라는 파생값입니다. 거래는 출력을 통째로 소비하고 잔돈을 새 출력으로 발행합니다. 수수료는 입력과 출력의 차이로 정의되며 어떤 출력에도 존재하지 않다가 채굴자가 회수합니다. 컨펌은 이 모든 UTXO 변경이 합의에 편입되는 과정입니다.

이 구조를 알면 실무에서 만나는 현상이 자연스럽게 읽힙니다. 지갑이 잔액은 있는데 전송이 안 되는 것은 사용 가능한 UTXO가 없거나 잠겼기 때문이고, 수수료가 금액이 아니라 크기에 비례하는 것도 이 모델의 직접적인 결과입니다. 이더리움은 같은 문제를 계정 기반 모델로 다르게 풀었는데, 두 설계의 트레이드오프는 UTXO를 이해한 다음에 비교해야 선이 보입니다.

---

## 7. Reference

- [Bitcoin Developer Reference - Transactions](https://developer.bitcoin.org/reference/transactions.html)
- [Bitcoin Developer Reference - Block Chain](https://developer.bitcoin.org/reference/block_chain.html)
- [Bitcoin Core - Regtest mode](https://developer.bitcoin.org/examples/testing.html)
- [Mastering Bitcoin - Transactions (ch06)](https://github.com/bitcoinbook/bitcoinbook/blob/develop/ch06_transactions.adoc)
- [Bitcoin Wiki - Protocol documentation (tx)](https://en.bitcoin.it/wiki/Protocol_documentation#tx)

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
