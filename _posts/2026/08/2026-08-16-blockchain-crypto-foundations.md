---
title: "Blockchain 암호학 기초 - 해시, 디지털 signature, Merkle Tree [Blockchain 1]"
date: 2026-08-16 13:10:00 +0900
author: kkamji
categories: [Security]
tags: [blockchain, cryptography, hash, digital-signature, merkle-tree, secp256k1, study]
comments: true
image:
  path: /assets/img/blockchain/blockchain.webp
---

"blockchain은 암호화되어서 안전하다"는 설명을 자주 봅니다. 그런데 Bitcoin transaction을 block explorer에서 열어보면 송금액, 수신자, balance가 전부 평문으로 보입니다. 암호화가 핵심이라면 이 내용은 왜 숨겨져 있지 않을까요?

blockchain이 실제로 암호학으로 해결하는 문제는 기밀성이 아니라 무결성과 인증입니다. 누가 자산을 이동시켰는지(signature), 기록이 이후에 바뀌지 않았는지(해시 체인), 수천 건의 거래가 정말 이 block에 들어 있는지(Merkle Tree). 이 세 가지를 Python으로 직접 실행하면서 확인합니다.

---

## 1. 해시 - 지문의 성질

SHA-256은 임의 길이 입력을 32바이트 고정 길이 출력으로 바꾸는 해시 함수입니다. blockchain의 모든 검증 구조가 이 함수의 성질 위에 서 있습니다.

```python
import hashlib

a = hashlib.sha256(b"Send 100 BTC to Alice").hexdigest()
b = hashlib.sha256(b"Send 100 BTC to Alise").hexdigest()  # 1글자만 변경
diff = sum(x != y for x, y in zip(a, b))
print("해시 A:", a)
print("해시 B:", b)
print(f"64자 중 다른 자리: {diff}/64 ({diff*100//64}%)")
```

실행 결과입니다.

```
해시 A: 02e8531307e01fc898b8040dd94775339328d73e935b18f6e920fd45f804d318
해시 B: 22cd2b2c93dfdbef9963d41465fecdad870e7b6549f1b0765184b83847a25eda
64자 중 다른 자리: 60/64 (93%)
```

수신자 이름 한 글자를 바꿨을 뿐인데 출력의 93% 자리가 바뀝니다. 이런 눈사태 효과 때문에 해시는 "내용이 조금이라도 다른지"를 32바이트 비교 한 번으로 판별하는 지문 역할을 합니다. 같은 입력은 항상 같은 출력이 나오고(결정론), 입력 크기와 무관하게 길이가 고정이며, 출력에서 입력을 되돌리는 방법은 알려져 있지 않습니다(단방향성).

block은 이 성질을 이용해 연결됩니다. 각 block의 헤더는 직전 block의 해시를 포함하고, block의 해시는 다시 그 다음 block 헤더에 포함됩니다.

```python
block0 = hashlib.sha256(b"genesis").hexdigest()
block1 = hashlib.sha256(("prev=" + block0 + ";txs=AA->BB:5").encode()).hexdigest()
block2 = hashlib.sha256(("prev=" + block1 + ";txs=BB->CC:3").encode()).hexdigest()

# 과거 블록의 송금액을 5에서 500으로 변조하면
tampered = hashlib.sha256(("prev=" + block0 + ";txs=AA->BB:500").encode()).hexdigest()
print(tampered == block1)  # False
```

과거 block 한 건을 바꾸면 그 block의 해시가 바뀌고, 그 해시를 포함하는 다음 block의 해시도 바뀌며, 이후 전체 체인의 해시가 연쇄적으로 바뀝니다. 변조를 감지하는 비용은 해시 비교 한 번이지만, 변조를 은폐하려면 이후 모든 block을 다시 계산해야 합니다. 이 비용 비대칭이 해시 체인의 핵심입니다.

---

## 2. 디지털 signature - 소유 증명

Bitcoin과 Ethereum은 secp256k1이라는 타원곡선으로 signature합니다. 개인키는 1 이상 곡선 차수 n 미만의 정수 하나이고(n은 2^256보다 약간 작습니다), 공개키는 그 정수를 곡선의 기준점에 곱해 얻습니다. wallet를 만든다는 것의 실체는 이 난수 하나를 안전하게 생성하고 보관하는 일입니다.

```python
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes

priv = ec.generate_private_key(ec.SECP256K1())
pub = priv.public_key()

msg = b"Send 100 BTC to Alice"
sig = priv.sign(msg, ec.ECDSA(hashes.SHA256()))
pub.verify(sig, msg, ec.ECDSA(hashes.SHA256()))  # 통과
```

여기서 검증에 쓰이는 정보는 공개키와 signature뿐입니다. 개인키는 검증자에게 전혀 노출되지 않습니다. 그래서 누구나 언제든 검증할 수 있으면서 signature자만 signature할 수 있습니다.

공개키는 개인키에서 파생되지만 역방향 계산 방법이 알려져 있지 않습니다. 이 이산대수 문제의 어려움이 소유 증명의 안전성을 지탱합니다.

### 2.1. 변조와 위조는 어떻게 걸리는가

검증 실패는 반환값이 아니라 `InvalidSignature` 예외로 나옵니다. 세 가지 실험을 이어서 실행하려면 예외를 받아야 합니다.

```python
from cryptography.exceptions import InvalidSignature

def verifies(signature, message):
    try:
        pub.verify(signature, message, ec.ECDSA(hashes.SHA256()))
        return True
    except InvalidSignature:
        return False

# 실험 1: 서명 후 수신자 이름 1글자 변경
print(verifies(sig, b"Send 100 BTC to Alise"))  # False

# 실험 2: 같은 메시지를 다른 키로 서명
other_sig = ec.generate_private_key(ec.SECP256K1()).sign(msg, ec.ECDSA(hashes.SHA256()))
print(verifies(other_sig, msg))  # False

# 실험 3: 같은 키로 같은 메시지를 다시 서명
sig2 = priv.sign(msg, ec.ECDSA(hashes.SHA256()))
print(sig == sig2)  # False
```

수신자를 1글자 바꾸면 signature가 무효화됩니다. 남의 signature도 내 공개키로는 검증되지 않습니다. 같은 키로 같은 메시지를 signature해도 결과가 매번 다른데, ECDSA가 signature마다 무작위 nonce를 사용하기 때문입니다. 이 nonce가 signature의 변화를 만들지만, 재사용되는 순간 개인키가 노출되는 것으로 유명한 함정이기도 합니다. signature 라이브러리의 난수 품질이 실제 사고로 이어진 사례가 있는 이유입니다. RFC 6979는 난수 대신 개인키와 메시지 해시에서 nonce를 결정론적으로 유도해 이 위험을 제거하는 방식을 규정합니다.

정리하면 신원은 공개키(address), 소유 증명은 signature, 비밀은 개인키입니다. 개인키가 유출되면 자산을 이동할 권한 전체가 유출되며, 백업해야 할 대상도 개인키 하나입니다.

---

## 3. Merkle Tree - 수천 건의 요약과 경량 증명

block 하나에는 수천 건의 transaction이 들어갑니다. 그런데 block 헤더가 개별 transaction 해시를 전부 저장하지 않습니다. transaction 해시들을 짝지어 합치고 다시 해싱하는 과정을 반복해 하나의 32바이트 값, Merkle Root만 헤더에 남깁니다.

```python
import hashlib

def h(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()

def merkle_root(tx_hashes: list[bytes]) -> bytes:
    level = tx_hashes[:]
    while len(level) > 1:
        if len(level) % 2 == 1:
            level.append(level[-1])  # 홀수개면 마지막 해시 복제
        level = [h(level[i] + level[i+1]) for i in range(0, len(level), 2)]
    return level[0]

txs = [f"tx{i}: Alice->Bob:{i+1} BTC".encode() for i in range(6)]
root = merkle_root([h(t) for t in txs])

# 4번째 트랜잭션(인덱스 3)의 송금액을 변조
txs[3] = b"tx3: Alice->Bob:999999 BTC"
root_tampered = merkle_root([h(t) for t in txs])
print(root == root_tampered)  # False
```

transaction 한 건의 금액을 바꾸면 Root가 완전히 달라집니다. block 해시는 헤더(Root 포함)의 해시이므로, block 해시 하나만 비교해도 이 block의 모든 transaction이 원본 그대로인지 알 수 있습니다.

### 3.1. 포함 증명 - 전체를 다운로드하지 않고 확인하기

Merkle Tree가 단순 요약 이상으로 쓰이는 이유는 특정 transaction의 포함 여부를 전체 없이 증명할 수 있기 때문입니다. 증명하려는 transaction에서 Root까지 가는 경로의 형제 해시들만 있으면 됩니다.

```python
def merkle_proof(tx_hashes: list[bytes], index: int) -> list[tuple[bytes, str]]:
    proof, level, idx = [], tx_hashes[:], index
    while len(level) > 1:
        if len(level) % 2 == 1:
            level.append(level[-1])
        sibling = idx ^ 1
        direction = "L" if sibling < idx else "R"
        proof.append((level[sibling], direction))
        level = [h(level[i] + level[i+1]) for i in range(0, len(level), 2)]
        idx //= 2
    return proof

def verify_proof(tx_hash: bytes, proof: list[tuple[bytes, str]], root: bytes) -> bool:
    cur = tx_hash
    for sibling, direction in proof:
        cur = h(cur + sibling) if direction == "R" else h(sibling + cur)
    return cur == root

txs = [f"tx{i}: Alice->Bob:{i+1} BTC".encode() for i in range(6)]  # 앞 절의 변조 복원
tx_hashes = [h(t) for t in txs]
root = merkle_root(tx_hashes)

proof = merkle_proof(tx_hashes, 3)
print(len(proof))  # 3단계
print(verify_proof(h(txs[3]), proof, root))  # True
```

6건 transaction 예제에서는 3단계, 형제 해시 3개(96바이트)만으로 Root와 대조 검증이 됩니다. transaction이 4,000건인 block이라도 경로는 12단계, 384바이트로 늘어날 뿐입니다. transaction 전체를 내려받지 않고 block 헤더 80바이트와 증명 경로만으로 자기 거래의 포함 여부를 확인하는 방식이 Bitcoin 라이트 wallet(SPV)의 동작 원리입니다.

같은 경로에 변조된 transaction을 넣으면 검증이 실패합니다.

```python
print(verify_proof(h(b"tx3: Alice->Bob:999999 BTC"), proof, root))  # False
```

경로의 형제 해시들은 원본 transaction 기준으로 계산된 값입니다. 다른 transaction을 끼워 넣으면 재계산된 Root가 헤더의 Root와 맞을 수 없습니다.

---

## 4. 세 조각이 맞물리는 지점

여기까지 확인한 세 요소를 block 수준에서 합치면 다음과 같습니다.

| 요소 | 역할 | 깨는 방법 |
|---|---|---|
| 해시 체인 | block 순서와 내용 고정 | 과거 변경 시 이후 전체 재계산 필요 |
| 디지털 signature | transaction 승인 권한 증명 | 개인키 탈취 또는 이산대수 문제 해법 |
| Merkle Root | block 내 transaction 전체 요약 | 1건 변경으로 Root 불일치 |

transaction은 signature으로 승인되고, block은 그 transaction들의 Merkle Root를 해시 체인으로 묶습니다. 각 요소가 서로를 검증 가능하게 만들기 때문에 중앙 기관의 승인 없이 임의의 참여자가 전체 기록을 검증할 수 있습니다.

마지막으로 흔한 오해로 돌아가면, blockchain은 데이터를 숨기지 않습니다. 오히려 누구나 읽을 수 있게 공개하고, 그 대신 누가 승인했는지(signature)와 바뀌지 않았는지(해시)를 수학적으로 검증 가능하게 만듭니다. 기밀성이 필요한 영역은 별도의 계층(영지식 증명, 프라이버시 체인 등)이 담당합니다.

위 코드는 Python 3 표준 라이브러리와 cryptography 하나만 있으면 그대로 재현됩니다. 해시 부분은 표준 라이브러리만으로 돌아가고, signature 부분만 `pip install cryptography`가 필요합니다. 세 절을 합쳐 100줄이 되지 않는 분량으로 blockchain의 검증 구조를 손으로 확인할 수 있습니다.

---

## 5. Reference

- [NIST FIPS 180-4 - Secure Hash Standard (SHA-256)](https://nvlpubs.nist.gov/nistpubs/FIPS/NIST.FIPS.180-4.pdf)
- [SEC 2 - Recommended Elliptic Curve Domain Parameters (secp256k1)](https://www.secg.org/sec2-v2.pdf)
- [Bitcoin Developer Reference - Block Chain](https://developer.bitcoin.org/reference/block_chain.html)
- [Bitcoin Developer Reference - Merkle Trees](https://developer.bitcoin.org/reference/block_chain.html#merkle-trees)
- [RFC 6979 - Deterministic DSA/ECDSA](https://datatracker.ietf.org/doc/html/rfc6979)
- [Python cryptography library](https://cryptography.io/)

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
