---
title: "TDD 알아보기 - 테스트가 먼저 실패하는 개발 루프"
date: 2026-08-17 20:40:00 +0900
author: kkamji
categories: [Development]
tags: [tdd, testing, pytest, red-green-refactor, software-engineering, study]
comments: true
image:
  path: /assets/img/kkam-img/kkam.webp
---

기능을 다 만들고 나서 테스트를 쓰다 보면, 테스트가 한 번도 실패하지 않고 바로 통과하는 경험이 있습니다. 코드를 고치기 전에도 통과하고, 일부러 버그를 넣어도 여전히 통과한다면 그 테스트는 아무것도 증명하지 않습니다. 반대로 구현보다 테스트를 먼저 쓰면, 테스트는 반드시 한 번은 실패합니다. 이 실패가 정확히 무엇을 증명하는지가 TDD(Test-Driven Development, 테스트 주도 개발)의 출발점입니다.

TDD는 Kent Beck이 익스트림 프로그래밍(XP) 시절 정리한 방법론으로, 코드를 작성하기 전에 테스트를 먼저 작성하고 그 테스트를 통과시키는 최소한의 코드만 쓰는 짧은 사이클을 반복합니다. 이 글에서는 그 사이클을 Python과 pytest로 직접 돌려 보면서, 왜 순서가 중요한지, 그리고 실증 연구가 이 방법론을 어떻게 평가하는지 확인합니다.

---

## 1. RED, GREEN, REFACTOR 사이클

TDD의 작업 루프는 세 단계로 구성됩니다.

| 단계 | 하는 일 | 끝나는 조건 |
|---|---|---|
| RED | 다음에 만들 동작 하나에 대한 테스트를 쓰고 실행한다 | 테스트가 실패하는 것을 눈으로 확인한다 |
| GREEN | 그 테스트를 통과시키는 가장 작은 구현을 쓴다 | 테스트 전체가 통과한다 |
| REFACTOR | 테스트를 녹색으로 유지하면서 코드를 정리한다 | 동작이 같고 구조가 나아진다 |

![TDD는 동작 하나마다 RED-GREEN-REFACTOR 짧은 루프를 반복한다](/assets/img/dev/tdd-loop.webp)
_RED 단계에서 실패를 확인하고, GREEN에서 통과시키고, REFACTOR에서 정리한 뒤 다음 동작으로 넘어간다._

사이클의 단위는 시스템 전체가 아니라 동작 하나입니다. PIN 번호가 4자리 숫자인지 검증하는 함수 하나, HTTP 응답에서 마지막 홉의 클라이언트 주소를 꺼내는 파싱 하나. 이 정도 크기의 동작마다 루프를 한 바퀴 돌리므로, 한 사이클은 길어야 몇 분입니다.

여기서 GREEN 단계가 "가장 작은 구현"인 점이 의도적입니다. 테스트가 요구하는 것보다 미리 만들어 두는 코드는 아직 실패한 적 없는 코드, 즉 필요하다는 증거가 없는 코드입니다. TDD는 요구되는 것만 만들고, 다음 요구는 다음 RED가 가져온다는 원칙으로 범위가 늘어나는 것을 억제합니다.

---

## 2. pytest로 돌리는 첫 사이클

4자리 PIN의 일치 여부를 검증하는 가장 단순한 함수로 사이클을 돌려 봅니다. PIN 입력이 올바른 형식인지 확인하고 기대값과 비교하는, 실제 서비스라면 로그인 화면 뒤에 있을 법한 검증 로직입니다.

먼저 RED입니다. 구현은 만들지 않고 테스트만 작성합니다.

```python
import pytest
from pin_verifier import verify_pin


def test_accepts_a_correct_pin():
    assert verify_pin("4821", "4821") is True


def test_rejects_a_wrong_pin():
    assert verify_pin("4821", "9999") is False


@pytest.mark.parametrize("bad", ["482", "48215", "abcd", ""])
def test_rejects_a_malformed_pin(bad):
    assert verify_pin(bad, "4821") is False
```

모듈이 없으니 첫 실행은 `ModuleNotFoundError`로 끝납니다. 다만 이 실패는 "기능이 없어서"가 아니라 "파일이 없어서"이므로, 검증하려는 동작의 부재를 증명하기에는 부족합니다. 동작 수준의 실패를 보기 위해 구현 파일을 만들고 함수 몸체를 비워 둡니다.

```python
def verify_pin(input_pin, expected_pin):
    raise NotImplementedError
```

다시 실행하면 테스트 6건 전부가 실패합니다.

```text
FAILED test_pin_verifier.py::test_accepts_a_correct_pin - NotImplementedError
FAILED test_pin_verifier.py::test_rejects_a_wrong_pin - NotImplementedError
FAILED test_pin_verifier.py::test_rejects_a_malformed_pin[482] - NotImplement...
FAILED test_pin_verifier.py::test_rejects_a_malformed_pin[48215] - NotImplement...
FAILED test_pin_verifier.py::test_rejects_a_malformed_pin[abcd] - NotImplemen...
FAILED test_pin_verifier.py::test_rejects_a_malformed_pin[] - NotImplementedE...
6 failed in 0.03s
```

이제 GREEN입니다. 조건을 만족하는 가장 짧은 구현을 씁니다.

```python
def verify_pin(input_pin, expected_pin):
    if len(input_pin) != 4 or not input_pin.isdigit():
        return False
    return input_pin == expected_pin
```

```text
test_pin_verifier.py::test_accepts_a_correct_pin PASSED
test_pin_verifier.py::test_rejects_a_wrong_pin PASSED
test_pin_verifier.py::test_rejects_a_malformed_pin[482] PASSED
test_pin_verifier.py::test_rejects_a_malformed_pin[48215] PASSED
test_pin_verifier.py::test_rejects_a_malformed_pin[abcd] PASSED
test_pin_verifier.py::test_rejects_a_malformed_pin[] PASSED
6 passed in 0.01s
```

REFACTOR 단계에서는 동작을 바꾸지 않고 표현을 정리합니다. 형식 검증을 정규식으로 바꿔 봅니다.

```python
import re

_PIN_PATTERN = re.compile(r"^\d{4}$")


def verify_pin(input_pin, expected_pin):
    if not _PIN_PATTERN.fullmatch(input_pin):
        return False
    return input_pin == expected_pin
```

```text
6 passed in 0.01s
```

정리 전과 정리 후에 테스트 결과가 완전히 같습니다. 이것이 REFACTOR를 안전하게 수행할 수 있는 근거입니다. 동작을 고정하는 테스트가 있으니, 변경이 실수로 동작을 바꿨다면 빨간불이 즉시 켜집니다.

---

## 3. 실패를 먼저 확인하는 이유

RED 단계에서 굳이 실패를 눈으로 확인하는 이유는, 그 테스트가 실패할 수 있는 테스트인지 검증하기 위해서입니다. 이 논리는 테스트 자체에도 적용할 수 있습니다. 방금 만든 테스트가 정말 결함을 잡아내는지 확인하려면, 의도적으로 결함을 넣어 보면 됩니다.

형식 검증의 반환값을 뒤집는 변형을 넣어 실행합니다.

```python
def verify_pin(input_pin, expected_pin):
    if not _PIN_PATTERN.fullmatch(input_pin):
        return True  # 결함: 거절해야 할 입력을 승인한다
    return input_pin == expected_pin
```

```text
FAILED test_pin_verifier.py::test_rejects_a_malformed_pin[482] - AssertionError: assert True is False
FAILED test_pin_verifier.py::test_rejects_a_malformed_pin[48215] - AssertionError
FAILED test_pin_verifier.py::test_rejects_a_malformed_pin[abcd] - AssertionError
FAILED test_pin_verifier.py::test_rejects_a_malformed_pin[] - AssertionError
4 failed, 2 passed in 0.02s
```

4건이 빨간불로 바뀌었습니다. 이 테스트 묶음은 형식 검증이 잘못되면 실패한다는 것이 증명됐고, 결함을 제거하면 다시 6건 통과합니다. 변형을 주입해 결함을 잡는지 확인하는 이 절차는 변이 테스트(mutation testing)의 핵심 아이디어이기도 합니다.

정리하면 두 가지 방향의 증명이 성립합니다.

- 구현 전 실패: 아직 기능이 없다는 증거. 이후 통과는 구현이 그 동작을 만들어냈다는 증거가 된다.
- 구현 후 변이: 테스트가 결함을 잡아낸다는 증거. 통과 상태가 우연이 아님을 보장한다.

구현 다음에 테스트를 쓰면 이 증명 쌍을 얻기 어렵습니다. 테스트가 처음부터 녹색이면 그 테스트가 빨간불이 될 수 있는지 알 방법이 없고, 운이 나쁘면 아무것도 검증하지 않는 테스트가 커버리지만 채운 채 남습니다.

---

## 4. 실증 연구는 무엇을 말하나

TDD의 효과를 검증한 연구들은 한 가지 주의할 점을 공유합니다. 방법론의 효과를 측정한다는 것 자체가 어렵고, 연구마다 참가자의 숙련도, 과업의 크기, 대조 조건이 다르다는 점입니다. 대표적인 세 연구를 조건과 함께 나열하면 스펙트럼이 보입니다.

Nagappan 연구진의 2008년 논문은 Microsoft와 IBM 계열의 산업 현장 4개 팀을 대상으로 TDD 도입 전후의 결함 밀도를 비교하고, 팀에 따라 결함 밀도가 크게 감소한 사례가 보고됐다고 결론지었습니다. 다만 이 연구는 네 팀의 사례 연구이며 통제된 실험이 아니라는 한계가 있습니다. 생산성은 팀에 따라 증가와 감소가 갈렸습니다.

Rafique와 Mišić는 2013년에 27개 연구를 통합한 메타분석을 발표했습니다. 요약하면 품질에는 작은 긍정 효과가 있고 생산성에는 구별할 수 있는 효과가 거의 없으며, 산업 연구에서 효과가 더 크게 나타났다는 것입니다. 마법 같은 개선은 아니라는 냉정한 결론입니다.

가장 흥미로운 결과는 Fucci 연구진의 2017년 논문에서 나옵니다. 전문가 39명의 82개 작업 데이터를 회귀 분석한 결과, 품질과 생산성의 향상은 세분성(작업을 잘게 쪼개는 정도)과 균일성(주기가 일정한 정도)과 연관이 있었고, 테스트를 먼저 쓰는지 나중에 쓰는지라는 순서 자체는 중요한 영향이 없었다는 것입니다. TDD의 효과가 순서가 아니라 짧고 균일한 개발 주기에서 온다는 해석이 가능합니다.

세 연구를 나란히 놓으면 TDD 실천에 대한 실용적인 결론이 그려집니다. "테스트를 먼저 써야만 하는가"라는 형식 논쟁보다, 동작 단위로 잘게 나누고 매 사이클 즉각적인 피드백을 받는 리듬이 효과의 본질에 가깝습니다. RED를 먼저 확인하는 습관은 그 리듬을 강제하는 장치로 이해하는 것이 근거에 맞습니다.

---

## 5. 어디에 잘 맞고 어디에 안 맞나

TDD가 힘을 발휘하는 영역은 입력과 기대 출력이 명확한 검증 로직입니다. 형식 검증, 파싱, 상태 전이, 금액 계산, 권한 검사 같은 곳에서는 테스트가 곧 실행 가능한 명세가 되므로, 테스트를 먼저 쓰는 것이 자연스럽고 실패 사례를 표로 만드는 일이 그대로 테스트 묶음이 됩니다.

반대로 정답이 아직 없는 탐색 작업에는 맞지 않습니다. 데이터의 분포를 확인하면서 그래프를 조정하는 분석 코드, 프레임워크의 동작을 확인하는 스파이크 코드, UI의 배치를 다듬는 작업은 결과가 무엇인지 알기 전에 테스트를 쓸 수 없으므로, 테스트가 나중에 붙는 것이 정상입니다. Martin Fowler는 테스트 더블을 쓰는 관점의 차이로 고전파(state verification)와 목객체파(interaction verification)로 나뉘는 전통이 있다고 정리한 바 있는데, 이 논쟁 역시 정답이 하나가 아니라 검증 대상과 팀의 선호에 따라 선택이 갈리는 문제입니다.

2014년에는 DHH가 TDD의 단위 테스트 중심 주장이 설계를 왜곡한다고 비판하며 논쟁이 붙었고, Kent Beck과 Martin Fowler가 참여한 패널 토론으로 이어졌습니다. 결론은 교리의 승패가 아니라 실제 코드를 놓고 맥락에 따라 판단하자는 쪽으로 수렴했습니다. Kent Beck 본인도 2023년 에세이에서 자신이 정리한 절차를 정답으로 복제하지 말고 자기 작업의 품질에 책임지는 방식을 찾으라고 쓰고 있습니다.

---

## 6. 정리

TDD의 사이클 자체는 단순합니다. 실패하는 테스트를 먼저 보고, 통과시키고, 정리한다. 그러나 그 단순한 순서가 만드는 증명 구조는 명확합니다. 구현 전의 실패는 기능의 부재를, 구현 후의 통과는 동작의 존재를, 변이 주입 후의 실패는 테스트의 검증력을 각각 증명합니다.

실증 연구는 순서의 강박보다 짧고 균일한 주기가 효과의 원천이라고 말하므로, 실천에서도 형식보다 리듬을 지키는 것이 중요합니다. 검증 로직을 다음에 만질 때 동작 하나를 골라 테스트를 먼저 쓰고 실패를 직접 확인해 보면, 이 글의 사이클이 몇 분 안에 한 바퀴 도는 것을 체감할 수 있습니다.

---

## 7. Reference

- [Kent Beck - Test-Driven Development: By Example (Addison-Wesley, 2002)](https://www.pearson.com/en-us/subject-catalog/p/test-driven-development-by-example/P200000009438)
- [Wikipedia - Test-driven development](https://en.wikipedia.org/wiki/Test-driven_development)
- [Martin Fowler - Mocks Aren't Stubs](https://martinfowler.com/articles/mocksArentStubs.html)
- [Martin Fowler - Is TDD Dead? (패널 시리즈)](https://martinfowler.com/articles/is-tdd-dead/)
- [DHH - TDD is dead. Long live testing. (2014, Internet Archive)](https://web.archive.org/web/2014*/david.heinemeierhansson.com/2014/tdd-is-dead-long-live-testing.html)
- [Kent Beck - Canon TDD (2023)](https://tidyfirst.substack.com/p/canon-tdd)
- [Nagappan et al. - Realizing quality improvement through test driven development (EMSE 2008)](https://doi.org/10.1007/s10664-008-9062-z)
- [Rafique & Mišić - The Effects of TDD on External Quality and Productivity: A Meta-Analysis (IEEE TSE 2013)](https://doi.org/10.1109/TSE.2012.28)
- [Fucci et al. - A Dissection of the Test-Driven Development Process (IEEE TSE 2017)](https://doi.org/10.1109/TSE.2016.2616877)
- [Dan North - Introducing BDD](https://dannorth.net/introducing-bdd/)
- [pytest 공식 문서](https://docs.pytest.org/)

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
