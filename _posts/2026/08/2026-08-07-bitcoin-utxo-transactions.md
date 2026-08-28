---
title: "비트코인 transaction 기초 - UTXO, fee, confirmation [Blockchain 2]"
date: 2026-08-07 09:49:00 +0900
author: kkamji
categories: [Blockchain]
tags: [blockchain, bitcoin, utxo, transaction, fee, regtest, study]
comments: true
image:
  path: /assets/img/blockchain/blockchain.webp
---

block explorer에서 비트코인 wallet을 열면 balance가 딱 붙어 나옵니다. 그런데 비트코인의 데이터 구조 어디에도 balance라는 필드는 없습니다. `balance`라는 저장된 값을 읽어온다면 어디에 들어 있을까요. 답은 없음입니다. balance는 저장되지 않고, 미사용 출력(UTXO)을 전부 모아 합한 값을 매번 계산해서 보여줄 뿐입니다.

hash pointer, signature, Merkle Tree가 기록의 무결성을 담당한다는 것은 [이전 글](https://kkamji.net/posts/blockchain-crypto-foundations/)에서 확인했습니다. 그 기록 위에서 돈은 미사용 output이라는 형태로 존재합니다. wallet의 balance가 왜 파생값인지, transaction이 미사용 output을 어떻게 소비하는지, fee가 어디로 사라지는지를 Python 시뮬레이터와 Bitcoin Core regtest node로 확인합니다. 실습은 로컬 regtest에서 진행하므로 실제 비용은 발생하지 않습니다.

---

## 1. balance는 어디에도 저장되어 있지 않다

은행은 계좌라는 상자에 balance 숫자를 넣어두고 이체마다 숫자를 더하고 뺍니다. 비트코인은 반대입니다. 장부에는 transaction의 output만 있고, 아직 소비되지 않은 output의 목록이 곧 돈입니다.

물리 현금은 지폐를 건네는 일입니다. 비트코인에는 건넬 토큰이 없습니다. 모든 풀 node가 같은 소유 데이터베이스를 들고 있고, Alice는 그 데이터베이스를 갱신하라고 설득하는 데이터 덩어리를 만듭니다. 그 덩어리가 transaction입니다.

UTXO(Unspent Transaction Output)는 한 transaction이 만든 output 중 아직 다른 transaction의 input으로 쓰이지 않은 것을 말합니다. 어떤 address의 balance를 알고 싶으면 그 address가 받을 수 있는 UTXO를 전부 찾아 금액을 합칩니다. Bitcoin Core의 `getbalance`는 `listunspent`의 합입니다. explorer가 보여주는 숫자도 같은 종류의 파생값입니다.

![alice의 UTXO를 순서대로 더해 파생 balance 75를 얻는 스캔](/assets/img/blockchain/utxo-balance-scan.webp)
_50, 20, 5를 더하면 75다. 계좌 행을 수정하는 단계가 없다. 이 세 숫자는 스캔을 설명하는 예시이며 regtest 관측값이 아니다._

새 transaction이 도착하면 node는 참조하는 output이 UTXO 집합에 존재하는지만 확인하면 됩니다. 이중 지출은 이미 소비된 output을 다시 가리키는 순간 거부됩니다. 같은 outpoint를 쓰는 두 transaction은 충돌하며, 유효한 체인에는 둘 중 하나만 들어갑니다. balance를 따로 보관하는 시스템이라면 모든 계좌의 정합성을 별도로 증명해야 하지만, UTXO 모델에서는 장부와 UTXO 집합 하나로 끝납니다.

금액의 최소 단위는 satoshi입니다. 1 BTC는 100,000,000 sat입니다. 아래 관측의 fee 0.0000141 BTC는 1,410 sat입니다.

---

## 2. transaction은 outpoint로 이전 output을 가리킨다

input 하나가 가리키는 값은 이전 transaction의 hash와, 그 안의 output 번호입니다. 이 쌍을 outpoint라고 부릅니다. 표기는 `txid:vout`입니다. 관측한 소비는 `7396e66d...:0`이었습니다. `:0`은 그 transaction의 첫 번째 output입니다.

node는 그 outpoint로 이전 output을 찾습니다. 거기서 세 가지를 읽습니다.

- 금액. 이 값은 통째로 이동한다. 일부를 남긴 채 쓸 수 없다.
- 잠금 조건. 누가 이 output을 쓸 수 있는지를 정한다. 기본 wallet은 공개키 hash에 대응하는 signature를 요구한다.
- 아직 소비되지 않았다는 사실. 이미 UTXO 집합에서 빠졌다면 그 input은 무효다.

coinbase transaction은 예외입니다. 이전 output이 없고, outpoint의 txid는 0으로 채워지며 index는 `0xffffffff`입니다. 채굴자는 이 특별한 input으로 block 보조금과 그 block에 담긴 fee를 한 번에 청구합니다. coinbase가 만든 output은 100 block이 지난 뒤에야 쓸 수 있습니다. 실습의 50 BTC 입력은 그렇게 성숙한 coinbase UTXO였습니다. 성숙이 풀린 높이는 이 노트에 없습니다.

serialized transaction에는 version과 locktime도 있습니다. version 1 규칙을 모든 transaction이 따르고, version 2는 상대 시간잠금에 쓰입니다. locktime은 특정 높이 또는 시각 이전에는 확정되지 않게 막는 필드입니다. 아래 관측은 기본 wallet이 만든 단순 이체라, 두 필드의 값을 따로 기록하지 않았습니다.

---

## 3. 거래는 output을 통째로 소비한다

UTXO는 부분적으로 쓸 수 없습니다. 50 BTC짜리 output에서 1.5 BTC만 보내는 것이 아니라, 50 BTC output 전체를 input으로 소비하고 두 개의 새 output을 만듭니다. 수신자에게 가는 1.5 BTC와 나에게 돌아오는 잔돈 48.5 BTC입니다.

![transaction이 UTXO를 통째로 소비하고 payment와 change 두 output을 만드는 구조](/assets/img/blockchain/utxo-reference-structure.webp)
_입력 50 BTC가 통째로 소비되고, payment 1.5 BTC와 change 48.4999859 BTC라는 두 개의 새 UTXO가 만들어진다. fee 0.0000141 BTC는 어떤 output에도 존재하지 않는다._

Bitcoin Core 31.1을 regtest 모드로 로컬에 띄우고 block을 채워 만든 coinbase UTXO 50 BTC에서 1.5 BTC를 송금했습니다.

```text
vin 1:
  prevout 7396e66d1971c020...:0   <- 50 BTC output을 통째로 소비
vout 2:
  [0]        1.5 BTC -> bcrt1qtvhq...   (수신자)
  [1] 48.4999859 BTC -> bcrt1qemaw...   (잔돈, 내 address로)
size 222 vsize 141
```

소비된 output은 `gettxout` 조회에 null을 반환합니다. output이 UTXO 집합에서 제거된 것입니다. 잔돈 48.4999859 BTC는 기존 balance에서 깎이는 게 아니라 새로운 txid:vout 쌍의 UTXO로 등장합니다. wallet의 50 BTC가 48.5 BTC로 수정된 것이 아니라, 낡은 50 BTC 지폐가 회수되고 새 48.5 BTC 지폐가 발행된 것에 가깝습니다.

한 번에 쓸 UTXO가 하나보다 많으면 wallet은 여러 개를 고릅니다. 이 선택이 coin selection입니다. 고른 UTXO마다 vin이 하나씩 생기고, 각 vin은 자기 outpoint를 통째로 소비합니다. 수신 output과 잔돈 output은 그 합에서 다시 쪼개집니다.

![두 개의 선택된 UTXO가 두 vin이 되고 payment와 change로 다시 나뉘는 선택](/assets/img/blockchain/coin-select-two-inputs.webp)
_30과 25를 고르면 입력이 둘이다. 쓰지 않은 UTXO는 장부에 그대로 남는다. 30과 25는 선택 규칙을 설명하는 예시이며, regtest에서 vin 2개는 아직 관측하지 않았다._

시뮬레이터는 같은 규칙을 50+50 입력으로 재현합니다. 아래 테스트 `test_spend_consumes_whole_utxo_and_returns_change`가 그 경우입니다.

---

## 4. fee는 어떤 output에도 존재하지 않는다

input의 합에서 output의 합을 빼면 fee입니다. 관측한 거래에서 입력은 50 BTC, 출력은 1.5 + 48.4999859 = 49.9999859 BTC, 따라서 fee는 0.0000141 BTC입니다.

이 0.0000141 BTC는 어느 wallet에도 속하지 않습니다. fee를 담은 UTXO는 존재하지 않습니다. 거래 직후 전체 UTXO 합계를 계산하면 정확히 fee만큼 줄어 있습니다. fee는 일단 장부에서 사라지고, 그 거래를 block에 담은 채굴자가 coinbase transaction을 통해 회수합니다. 채굴 보상(block reward)이 보조금(subsidy)과 fee의 합인 이유가 여기에 있습니다. 별도 수신 address가 없습니다.

fee는 금액이 아니라 크기에 비례합니다. 관측한 거래는 size 222, vsize 141이었습니다. fee 1,410 sat을 141 vB로 나누면 10 sat/vB입니다. 같은 1.5 BTC라도 입력이 많거나 Script가 길면 vsize가 커지고 fee도 올라갑니다.

vsize는 레거시 바이트와 다릅니다. 오늘날 block 한도는 weight 4,000,000이고, 4 weight가 1 vbyte입니다. witness 데이터는 더 작은 계수로 셉니다. 그래서 같은 거래의 size 222와 vsize 141이 갈라집니다. fee 시장이 쓰는 단위는 보통 sat/vB입니다.

소액 UTXO가 쌓이면 이 산술이 운영 문제가 됩니다. output을 나중에 쓰려면 그 input이 차지하는 vsize만큼 fee를 더 내야 합니다. output 가치가 그 추가 fee보다 작으면 경제적이지 않은 output, 흔히 dust라고 부릅니다. 풀 node는 모든 UTXO를 추적해야 하므로, 아무도 쓰지 않을 먼지는 검증 비용을 영구히 남깁니다. Bitcoin Core는 그런 output을 만드는 미확인 거래를 기본으로 중계하지 않습니다. 많은 wallet이 546 sat 미만을 dust로 간주합니다. 546은 정책 관례이지, 이번 regtest node에서 거절을 관측한 값은 아닙니다.

---

## 5. wallet에서 confirmation까지

돈의 이동은 explorer 숫자가 바뀌는 한 순간이 아닙니다. wallet이 키로 signature하기 전에 UTXO를 고르고, node가 그 transaction을 받아 mempool에 올리며, 채굴자가 그것을 block에 넣을 때 UTXO 집합이 바뀝니다.

![wallet이 UTXO를 고르고 signature한 뒤 mempool을 거쳐 block에서 확정되는 경로](/assets/img/blockchain/wallet-to-confirmation.webp)
_signature가 붙은 transaction은 바로 장부에 기록되지 않는다. mempool에 있는 동안 confirmation은 0이다._

mempool에 있는 동안에도 wallet UI의 balance 계산은 동작할 수 있습니다. 다만 그 거래가 소비하려는 UTXO는 잠긴 상태가 됩니다. 셀프 전송 transaction을 mempool에 넣어두면 잔돈으로 받을 UTXO가 아직 확정되지 않았기 때문에 그다음 전송이 그 UTXO를 쓰지 못합니다. 실습 중 0.5 BTC를 자신에게 보내는 거래를 만들었을 때, 확정 전까지 wallet의 잔돈 UTXO가 사용 불가 상태로 잠기는 것을 관찰했습니다.

block 하나를 더 채굴하자 잠금이 풀렸습니다. 수신 output 0.5 BTC와 잔돈 output이 각각 별도의 UTXO로 확정되어 목록에 나타납니다. confirmation이란 이 거래가 만드는 UTXO 변경이 체인 합의에 편입되었음을 뜻합니다. confirmation 수가 쌓일수록 되돌리기 어려워지는 reorg 가능성을 고려하면, 실무에서 6 confirmation을 기다리는 관행은 이 확정의 신뢰도를 확률적으로 높이는 절차입니다. 로컬에서 관측한 값은 1 block 편입이며, 6 confirmation 관행을 여기서 재현한 것은 아닙니다.

---

## 6. Python 미니 장부로 규칙 재현하기

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

        # 2) 수신자 output + 잔돈 output을 "새 UTXO"로 발행한다
        outputs = [(recipient, amount)]
        change = round(total - amount - fee, 8)
        if change > 0:
            outputs.append((sender, change))
        ...
```

동작 검증은 테스트로 남겼습니다. balance가 UTXO 스캔의 파생값인 것, 50 BTC에서 30 BTC를 보내면 잔돈 20 BTC가 새 UTXO로 돌아오는 것, fee만큼 전체 UTXO 합계가 감소하고 그 값을 담은 UTXO는 없는 것, balance 부족 시 원자적으로 롤백되는 것까지 5개 테스트가 전부 통과합니다.

```text
02_utxo_behavior_test.py::test_balance_is_derived_from_utxos PASSED
02_utxo_behavior_test.py::test_spend_consumes_whole_utxo_and_returns_change PASSED
02_utxo_behavior_test.py::test_fee_is_lost_by_sender_and_no_partial_spend PASSED
02_utxo_behavior_test.py::test_overspend_is_rejected_and_rolls_back PASSED
02_utxo_behavior_test.py::test_dust_edge_zero_change_has_single_output PASSED
5 passed in 0.02s
```

마지막 테스트는 50 BTC UTXO를 정확히 50 BTC 보낼 때 change output이 생기지 않는 경우입니다. 잔돈이 0이면 vout은 수신자 하나뿐입니다.

시뮬레이터가 비트코인 규칙을 따르는지는 regtest 관측과 대조했습니다. 통째로 소비, 잔돈의 새 UTXO 발행, fee의 비존재, 파생되는 balance까지 네 규칙이 실제 node의 동작과 일치했습니다. 시뮬레이터 코드는 표준 라이브러리만 사용하므로 설치 없이 재현할 수 있습니다.

---

## 7. 이 모델에서 보이는 운영 증상

비트코인의 돈은 계좌가 아니라 미사용 output이라는 사실에서 나머지가 따라옵니다. balance는 저장값이 아니라 UTXO 집합의 합계라는 파생값입니다. transaction은 outpoint로 이전 output을 통째로 소비하고 잔돈을 새 output으로 발행합니다. fee는 입력과 출력의 차이로 정의되며 어떤 output에도 존재하지 않다가 채굴자가 회수합니다. confirmation은 이 모든 UTXO 변경이 합의에 편입되는 과정입니다.

그래서 wallet이 balance는 있는데 전송이 안 되는 상황은 이상 현상이 아닙니다. 사용 가능한 UTXO가 없거나, mempool에서 잠겼거나, 남은 조각이 dust에 가깝기 때문입니다. fee가 송금액이 아니라 vsize에 비례하는 것도 같은 모델의 직접 결과입니다. explorer 숫자와 node의 `listunspent`가 어긋나면, 먼저 어느 쪽 UTXO 집합을 보고 있는지부터 보면 됩니다.

이더리움은 같은 문제를 계정 객체에 `balance`와 `nonce`를 저장하는 방식으로 다르게 풉니다. 두 설계의 트레이드오프는 UTXO를 이해한 다음에 비교해야 선이 보입니다.

---

## 8. Reference

- [Bitcoin Developer Reference - Transactions](https://developer.bitcoin.org/reference/transactions.html)
- [Bitcoin Developer Reference - Block Chain](https://developer.bitcoin.org/reference/block_chain.html)
- [Bitcoin Core - Regtest mode](https://developer.bitcoin.org/examples/testing.html)
- [Mastering Bitcoin - Transactions (ch06)](https://github.com/bitcoinbook/bitcoinbook/blob/develop/ch06_transactions.adoc)
- [Mastering Bitcoin - Transaction Fees (ch09)](https://github.com/bitcoinbook/bitcoinbook/blob/develop/ch09_fees.adoc)
- [Bitcoin Wiki - Protocol documentation (tx)](https://en.bitcoin.it/wiki/Protocol_documentation#tx)

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
