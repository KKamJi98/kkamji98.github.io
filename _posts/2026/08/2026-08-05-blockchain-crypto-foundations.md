---
title: "암호학 기초 - hash, signature, Merkle Tree [Blockchain 1]"
date: 2026-08-05 03:53:00 +0900
author: kkamji
categories: [Blockchain]
tags: [blockchain, cryptography, hash, digital-signature, merkle-tree, secp256k1, study]
comments: true
image:
  path: /assets/img/blockchain/blockchain.webp
---

"blockchain은 암호화되어서 안전하다"는 설명을 자주 봅니다. 그런데 Bitcoin transaction을 block explorer에서 열어보면 송금액, 수신자, 합계가 전부 평문으로 보입니다. 암호화가 핵심이라면 이 내용은 왜 숨겨져 있지 않을까요?

blockchain이 암호학으로 푸는 문제는 기밀성이 아닙니다. 무결성과 인증입니다. 누가 자산을 이동시켰는지(signature), 기록이 이후에 바뀌지 않았는지(hash pointer), 수천 건의 transaction이 정말 이 block에 들어 있는지(Merkle Tree). 이 세 가지를 Python으로 실행하면서 확인합니다.

---

## 1. hash는 암호가 아니다

SHA-256은 임의 길이 입력을 32바이트 고정 길이 출력으로 바꿉니다. NIST FIPS 180-4가 그 길이를 정의합니다. 출력은 메시지가 아니라 digest입니다. 파일을 기억하는 대신 32바이트를 기억하고, 나중에 같은 입력이 왔는지만 대조합니다.

```python
import hashlib

a = hashlib.sha256(b"Send 100 BTC to Alice").hexdigest()
b = hashlib.sha256(b"Send 100 BTC to Alise").hexdigest()  # 1글자만 변경
diff = sum(x != y for x, y in zip(a, b))
print("hash A:", a)
print("hash B:", b)
print(f"64자 중 다른 자리: {diff}/64 ({diff*100//64}%)")
```

실행 결과입니다.

```
hash A: 02e8531307e01fc898b8040dd94775339328d73e935b18f6e920fd45f804d318
hash B: 22cd2b2c93dfdbef9963d41465fecdad870e7b6549f1b0765184b83847a25eda
64자 중 다른 자리: 60/64 (93%)
```

수신자 이름 한 글자를 바꿨을 뿐인데 출력의 93% 자리가 바뀝니다. 같은 입력은 항상 같은 출력이 나오고, 입력 크기와 무관하게 길이가 고정입니다. 이 눈사태 효과 때문에 hash는 "내용이 조금이라도 다른지"를 32바이트 비교 한 번으로 판별합니다.

눈사태는 성질이지 공격 분류가 아닙니다. 공격은 세 가지로 나눕니다. preimage는 digest만 보고 원래 입력을 찾는 일입니다. second preimage는 이미 아는 입력과 같은 digest를 내는 다른 입력을 찾는 일입니다. collision은 아무 두 입력을 골라 같은 digest를 내는 일입니다. SHA-256에서 세 가지 모두 현실적인 계산으로는 찾지 못한다고 봅니다. collision은 이론상 존재합니다. 출력 공간이 유한하고 입력 공간은 무한에 가깝기 때문입니다. 찾는 비용이 막대하다는 점과, 존재한다는 점은 다른 문장입니다.

단방향성은 이 중 preimage에 가깝습니다. 출력을 보고 입력을 되돌리는 방법이 알려져 있지 않다는 뜻입니다. 약속(commitment)은 그 위에 한 겹을 더 얹습니다. 값을 공개하지 않은 채 hash만 먼저 보여주고, 나중에 값을 열면 처음에 약속한 값인지 누구나 확인합니다. 이번 실습은 그 commitment를 새로 구현하지 않았습니다. 눈사태 숫자 60/64만 관측값입니다.

---

## 2. hash pointer가 체인을 만든다

일반 pointer는 데이터가 어디에 있는지만 말합니다. hash pointer는 위치와 그 데이터의 digest를 같이 들고 있습니다. 가리킨 바이트가 바뀌면 digest가 더 이상 맞지 않습니다. Princeton의 1장은 이 구조를 hash pointer라고 부릅니다.

block header는 직전 header의 hash pointer를 포함합니다. 지금 header의 digest는 다시 다음 header에 들어갑니다. 검증자가 기억해야 하는 값은 맨 끝 header의 digest 하나입니다. 그 하나에서 거꾸로 내려가면 각 칸의 내용이 그 pointer와 맞는지 확인할 수 있습니다.

![각 block header가 직전 header의 hash pointer를 저장하는 체인](/assets/img/blockchain/hash-pointer-chain.webp)
_block 1 header는 genesis digest를 들고, block 2 header는 block 1 digest를 든다. 한 payload를 바꾸면 이후 pointer가 전부 깨진다._

```python
block0 = hashlib.sha256(b"genesis").hexdigest()
block1 = hashlib.sha256(("prev=" + block0 + ";txs=AA->BB:5").encode()).hexdigest()
block2 = hashlib.sha256(("prev=" + block1 + ";txs=BB->CC:3").encode()).hexdigest()

tampered = hashlib.sha256(("prev=" + block0 + ";txs=AA->BB:500").encode()).hexdigest()
print(tampered == block1)  # False
```

과거 block 한 건을 바꾸면 그 block의 digest가 바뀌고, 그 digest를 포함하는 다음 header도 바뀌며, 이후 전체 체인이 연쇄적으로 바뀝니다. 변조를 감지하는 비용은 digest 비교 한 번입니다. 변조를 은폐하려면 이후 모든 header를 다시 계산해야 합니다. 이 비용 비대칭이 hash pointer 체인의 핵심입니다.

이 실험의 hash는 한 번의 SHA-256입니다. Bitcoin header의 실제 proof-of-work digest는 double SHA-256입니다. 여기서는 pointer의 성질만 확인하고, 난이도 숫자는 재지 않았습니다.

---

## 3. signature는 개인키를 보여 주지 않는다

Bitcoin과 Ethereum은 secp256k1 곡선으로 signature합니다. 개인키는 1 이상 곡선 차수 n 미만의 정수 하나입니다. n은 2^256보다 약간 작습니다. 공개키는 그 정수를 곡선의 기준점에 곱해 얻습니다. wallet을 만든다는 일의 실체는 이 난수 하나를 안전하게 생성하고 보관하는 일입니다.

API는 세 함수입니다. keygen, sign, verify. 검증에 쓰이는 정보는 공개키와 signature뿐입니다. 개인키는 검증자에게 노출되지 않습니다. 누구나 검증할 수 있고, 개인키 소유자만 sign할 수 있습니다. 이 성질을 unforgeability라고 부릅니다.

```python
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes

priv = ec.generate_private_key(ec.SECP256K1())
pub = priv.public_key()

msg = b"Send 100 BTC to Alice"
sig = priv.sign(msg, ec.ECDSA(hashes.SHA256()))
pub.verify(sig, msg, ec.ECDSA(hashes.SHA256()))  # 통과
```

공개키는 개인키에서 파생되지만 역방향 계산 방법이 알려져 있지 않습니다. 이 이산대수 문제의 어려움이 소유 증명의 안전성을 지탱합니다.

검증 실패는 반환값이 아니라 `InvalidSignature` 예외로 나옵니다.

```python
from cryptography.exceptions import InvalidSignature

def verifies(signature, message):
    try:
        pub.verify(signature, message, ec.ECDSA(hashes.SHA256()))
        return True
    except InvalidSignature:
        return False

print(verifies(sig, b"Send 100 BTC to Alise"))  # False

other_sig = ec.generate_private_key(ec.SECP256K1()).sign(msg, ec.ECDSA(hashes.SHA256()))
print(verifies(other_sig, msg))  # False

sig2 = priv.sign(msg, ec.ECDSA(hashes.SHA256()))
print(sig == sig2)  # False
```

수신자를 1글자 바꾸면 signature가 무효가 됩니다. 남의 signature도 내 공개키로는 검증되지 않습니다. 같은 키로 같은 메시지를 다시 sign해도 결과가 매번 다릅니다. ECDSA가 signature마다 무작위 nonce를 쓰기 때문입니다. 이 nonce가 바뀌는 것은 정상입니다. 같은 nonce가 재사용되는 순간 개인키가 노출됩니다. RFC 6979는 난수 대신 개인키와 메시지 digest에서 nonce를 결정론적으로 유도해 그 경로를 막습니다.

hash pointer에 signature를 붙이면, 그 pointer가 가리키는 구조 전체를 승인한 것이 됩니다. 헤더 digest 하나에 서명하면 그 헤더가 가리키는 이전 칸까지 묶입니다. 이번 코드는 메시지 바이트에만 서명했습니다. pointer 위 서명은 같은 verify 경로입니다.

---

## 4. address는 공개키가 아니다

신원은 공개키에서 시작합니다. Bitcoin address는 그 공개키 자체가 아닙니다. 공개키를 SHA-256으로 한 번 해시한 뒤 RIPEMD-160으로 줄인 값, 흔히 HASH160이라고 부르는 digest 위에 version과 checksum을 얹습니다. explorer에 보이는 `1...` 또는 `bc1...` 문자열은 그 인코딩입니다.

이 파이프라인의 구체 digest는 이번 실습에서 찍지 않았습니다. 관측 없이 숫자를 만들지 않습니다. 중요한 구분은 하나입니다. 개인키는 비밀이고, 공개키는 검증키이며, address는 공개키의 digest입니다. 예전 문장처럼 "신원은 공개키(address)"라고 쓰면 두 층이 붙습니다.

공개키를 만드는 비용은 난수 하나입니다. 그래서 값싼 신원을 대량으로 만들 수 있습니다. Sybil resistance가 따로 필요한 이유가 여기 있습니다. hash와 signature는 "이 메시지가 이 키의 승인인가"만 답합니다. "이 키가 사람 한 명인가"는 답하지 않습니다. Byzantine fault는 이미 참여한 노드가 거짓말하는 문제이고, Sybil은 참여 자체를 값싸게 복제하는 문제입니다. 합의 알고리즘 이름은 나중에 따로 다룹니다. 여기서는 값싼 공개키가 그 두 문제를 자동으로 풀어 주지 않는다는 점만 남깁니다.

프라이버시도 자동이 아닙니다. address는 가명이지만, 같은 address를 반복해 쓰면 explorer에서 흐름이 붙습니다. 기밀성은 이 계층의 목표가 아닙니다.

---

## 5. Merkle Tree는 포함 증명이다

block 하나에는 수천 건의 transaction이 들어갑니다. header는 개별 transaction hash를 전부 저장하지 않습니다. leaf hash를 짝지어 합치고 다시 해시하는 과정을 반복해 32바이트 Merkle Root만 header에 남깁니다. 이 나무는 hash pointer의 이진 트리입니다. 각 부모는 자식 두 개의 digest를 가리킵니다.

```python
import hashlib

def h(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()

def merkle_root(tx_hashes: list[bytes]) -> bytes:
    level = tx_hashes[:]
    while len(level) > 1:
        if len(level) % 2 == 1:
            level.append(level[-1])  # 홀수개면 마지막 hash 복제
        level = [h(level[i] + level[i+1]) for i in range(0, len(level), 2)]
    return level[0]

txs = [f"tx{i}: Alice->Bob:{i+1} BTC".encode() for i in range(6)]
root = merkle_root([h(t) for t in txs])

txs[3] = b"tx3: Alice->Bob:999999 BTC"
root_tampered = merkle_root([h(t) for t in txs])
print(root == root_tampered)  # False
```

transaction 한 건의 금액을 바꾸면 Root가 완전히 달라집니다. block hash는 header(Root 포함)의 hash이므로, block hash 하나만 비교해도 이 block의 모든 transaction이 원본인지 알 수 있습니다.

포함 여부는 전체 없이 증명합니다. 증명하려는 transaction에서 Root까지 가는 경로의 형제 hash만 있으면 됩니다.

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

txs = [f"tx{i}: Alice->Bob:{i+1} BTC".encode() for i in range(6)]
tx_hashes = [h(t) for t in txs]
root = merkle_root(tx_hashes)

proof = merkle_proof(tx_hashes, 3)
print(len(proof))  # 3단계
print(verify_proof(h(txs[3]), proof, root))  # True
print(verify_proof(h(b"tx3: Alice->Bob:999999 BTC"), proof, root))  # False
```

6건 예제에서는 형제 hash 3개, 96바이트만으로 Root와 대조됩니다. transaction이 4,000건인 block이라도 경로는 12단계, 384바이트로 늘어날 뿐입니다. SPV wallet이 header 80바이트와 이 경로만으로 자기 거래의 포함 여부를 확인하는 이유가 여기 있습니다.

![tx hash와 sibling hash가 parent를 만들고, parent가 Merkle Root까지 올라가는 포함 증명](/assets/img/blockchain/merkle-inclusion-path.webp)
_header는 Root만 저장한다. 포함 증명은 leaf에서 Root까지 sibling을 따라간다._

경로의 형제 hash는 원본 leaf 기준으로 계산된 값입니다. 다른 transaction을 끼워 넣으면 재계산된 Root가 header의 Root와 맞을 수 없습니다. Bitcoin SPV가 쓰는 것은 이 포함 증명입니다.

---

## 6. 같은 동전을 두 번 쓰면

hash pointer와 signature를 갖춰도 이중 지출은 남습니다. Princeton 1장의 GoofyCoin이 그 구멍입니다. 발행자가 자기 공개키로 "이 동전은 Alice 것이다"라고 서명하면 Alice는 소유자가 됩니다. Alice는 같은 문장에 Bob의 이름을 넣어 다시 서명할 수 있고, Carol의 이름을 넣어 한 번 더 서명할 수도 있습니다. 두 signature는 각각 유효합니다. 검증자는 어느 쪽이 먼저인지 hash pointer만으로는 고를 수 없습니다.

append-only 장부에 이체 이력을 한 줄로 붙이면, 이미 쓰인 동전을 다시 쓰는 줄은 거절할 수 있습니다. 그 장부를 누가 하나만 유지하는지가 다음 문제입니다. 중앙 Scrooge가 그 장부를 쓰면 이중 지출은 막히고, Scrooge를 신뢰해야 합니다. Bitcoin이 UTXO 집합과 합의로 그 장부를 나눈 이야기는 다음 편입니다. 여기서 확인할 것은 하나입니다. 암호 프리미티브는 위조와 변조를 막습니다. 어떤 이력이 정본인지는 답하지 않습니다.

---

## 7. 세 조각이 맞물리는 지점

| 요소 | 역할 | 깨는 방법 |
|---|---|---|
| hash pointer 체인 | block 순서와 내용 고정 | 과거 변경 시 이후 전체 재계산 |
| digital signature | transaction 승인 권한 증명 | 개인키 탈취 또는 이산대수 해법 |
| Merkle Root | block 안 transaction 요약 | 1건 변경으로 Root 불일치 |

transaction은 signature로 승인되고, block은 그 transaction들의 Merkle Root를 hash pointer 체인으로 묶습니다. 각 요소가 서로를 검증 가능하게 만들기 때문에 중앙 기관의 승인 없이 임의의 참여자가 전체 기록을 검증할 수 있습니다.

다시 처음 문장으로 돌아가면, blockchain은 데이터를 숨기지 않습니다. 누구나 읽을 수 있게 공개하고, 누가 승인했는지와 바뀌지 않았는지를 검증 가능하게 만듭니다. 기밀성이 필요한 영역은 영지식 증명이나 프라이버시 체인처럼 별도 계층이 담당합니다.

위 코드는 Python 3 표준 라이브러리와 cryptography 하나만 있으면 재현됩니다. hash 부분은 표준 라이브러리만으로 돌아가고, signature 부분만 `pip install cryptography`가 필요합니다.

---

## 8. Reference

- [NIST FIPS 180-4 - Secure Hash Standard (SHA-256)](https://nvlpubs.nist.gov/nistpubs/FIPS/NIST.FIPS.180-4.pdf)
- [SEC 2 - Recommended Elliptic Curve Domain Parameters (secp256k1)](https://www.secg.org/sec2-v2.pdf)
- [Bitcoin Developer Reference - Block Chain](https://developer.bitcoin.org/reference/block_chain.html)
- [Bitcoin Developer Reference - Merkle Trees](https://developer.bitcoin.org/reference/block_chain.html#merkle-trees)
- [RFC 6979 - Deterministic DSA/ECDSA](https://datatracker.ietf.org/doc/html/rfc6979)
- [Python cryptography library](https://cryptography.io/)
- [Princeton Bitcoin Book draft - Chapter 1](https://bitcoinbook.cs.princeton.edu/)

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
