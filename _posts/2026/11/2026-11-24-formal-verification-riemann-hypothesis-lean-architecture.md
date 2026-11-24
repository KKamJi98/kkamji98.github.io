---
title: "Formal Verification - AI 리만 가설 1700만 줄 Lean 증명과 검증 아키텍처의 이동"
description: "1700만 줄 AI 리만 가설 Lean 4 증명을 인간 통독 없이 하루 만에 인증한 다중 커널과 명제 격리 검증 아키텍처를 분석하고, Alexandr Wang 에세이의 한계와 DevSecOps 시사점을 짚습니다."
date: 2026-11-24 10:30:00 +0900
author: kkamji
categories: [AI, Infra]
tags: [formal-verification, lean4, riemann-hypothesis, ai, devsecops, security, architecture]
comments: true
published: true
image:
  path: /assets/img/ai/formal-verification/riemann-lean-verification-cover.webp
  width: 1920
  height: 1080
  alt: AI 리만 가설 1700만 줄 Lean 4 공식 증명과 다중 커널 검증 아키텍처
---

2026년 11월 20일, Anthropic 소속 수학자 Levent Alpoge가 Claude와 함께 완성한 리만 가설(Riemann Hypothesis)과 Dirichlet L-함수 일반화 리만 가설(GRH)의 Lean 4 형식 증명을 14분할 아카이브(`alpo.ge`)로 공개했습니다. 전체 코드 규모는 약 1,700만 줄, 175,187개 모듈에 달합니다. Alpoge 본인이 4쪽짜리 공개 메모(`remark.pdf`)에 적었듯 이를 자연어 문서로 풀어내면 25만 페이지가 넘어 인간 수학자가 처음부터 끝까지 읽을 수 없는 분량입니다.

그런데 불과 하루 뒤인 11월 21일, Lean FRO와 Mathlib Initiative는 공동 성명을 내고 리만 가설의 명제와 증명이 모두 형식적으로 옳다고 인증했습니다. **인간이 1,700만 줄을 통독하지 않고도 24시간 만에 수학적 정당성을 인증할 수 있었던 이유는 증명 본문이 아니라 검증 아키텍처에 있습니다.** 이 사건은 11월 23일 Meta CAIO Alexandr Wang이 X에 "Superintelligence is Arriving"을 게시하며 AI 역량 논쟁의 중심으로 번졌습니다.

| 시점 | 주체 | 핵심 사건과 공개 범위 |
| --- | --- | --- |
| 2026-11-12 | Kevin Buzzard (Xena Project) | AI 생성 Lean 증명을 신뢰하기 위한 4대 검증 기준(명제, 컴파일, 명제 일치, 다중 커널) 정리 |
| 2026-11-20 | Levent Alpoge (Anthropic) | `alpo.ge/remark.pdf`와 14분할 Lean 4 아카이브(`lean.tar.gz.part01` - `part14`) 공개 |
| 2026-11-21 | Lean FRO & Mathlib Initiative | 공동 성명으로 Xena 4대 기준 충족 및 리만 가설 명제/증명 형식 정당성 인증 |
| 2026-11-20 - 11-23 | Andrew Sutherland (MIT) | 샌드박스 독립 재빌드, 61.6 GB export 해시 대조, 6종 커널과 `Robin1984` 산술 교차 검증 공개 |
| 2026-11-23 (KST) | Alexandr Wang (Meta CAIO) | X에 "Superintelligence is Arriving" 게시, 사회 이양(handover) 거부와 인간 주체성 촉구 |

---

## 1. 기계 형식 인증과 인간 수학계의 이해를 구분하기

이 사건을 기술적으로 정확히 읽으려면 먼저 완료된 것과 진행 중인 것의 경계를 분리해야 합니다. 2026년 11월 21일 Lean FRO와 Mathlib Initiative의 공동 성명, 그리고 11월 23일 23:45 UTC 기준 MIT Andrew Sutherland의 공개 검증 로그가 확정한 범위는 **기계 커널 수준의 형식 정당성(formal correctness)** 입니다.

검증을 통과한 대상은 제출 저장소의 `Main.lean`에 담긴 핵심 정리 5개입니다.

1. `riemannHypothesis`: Mathlib(`Mathlib/NumberTheory/LSeries/RiemannZeta.lean`)에 이미 존재하던 표준 `RiemannHypothesis` 정의에 대한 증명.
2. `riemannZeta_eq_zero_re`: 동일한 리만 제타 함수 영점 명제를 직접 전개한 형태. Lean 커널은 위 정의와 정의적 동치(definitional equality)로 인식한다.
3. `LFunction_ne_zero_of_half_lt_re`: 모든 법(modulus)과 Dirichlet 지표에 대해 실수부가 `1/2`보다 큰 영역에서 L-함수가 0이 되지 않음(자명 지표의 `s = 1` 극점 제외).
4. `LFunction_eq_zero_re`: 임계 띠(`0 < Re s < 1`) 안의 모든 Dirichlet L-함수 영점의 실수부가 `1/2`임.
5. `LFunction_eq_zero_re_of_isPrimitive`: 원시(primitive) Dirichlet 지표에 대한 통상적 GRH 진술.

검증 범위의 한계도 분명합니다. MIT 검증 페이지가 명시하듯 여기서 확인된 GRH는 Dirichlet L-함수에 한정되며, Dedekind 제타 함수, Hecke L-함수, 일반 보형(automorphic) L-함수는 이번 검증 대상에 포함되지 않았습니다.

무엇보다 **기계 검증이 보장하는 것은 표준 공리에서 정리까지의 논리적 무결성이지, 인간 수학계가 그 증명 아이디어를 완전히 소화했다는 뜻이 아닙니다.** Alpoge 역시 `remark.pdf`에서 자신조차 이 증명의 거대한 주변 수학을 아직 완전히 장악하지 못했다고 밝혔습니다. 함수체에서의 Stepanov 행렬식 논증을 정수로 옮겨, 길이 `X`의 von Mangoldt 합에 대해 길이 `sqrt(X)`의 연쇄 theta lift를 구성하는 착상을 Claude와 함께 끌어냈지만, 산문으로 25만 쪽이 넘는 읽기 어려운 문서를 내놓는 대신 Lean 코드만 먼저 공개했다는 설명입니다. 전통적 동료 심사와 개념 단순화는 이제 막 시작되었고, Clay Mathematics Institute의 Millennium Prize 공식 상태 역시 2026년 11월 24일 기준 미해결 상태로 남아 있습니다.

---

## 2. 아무도 읽지 못하는 1700만 줄을 하루 만에 인증한 검증 아키텍처

전통적인 자연어 수학 논문에서는 수백 쪽짜리 증명의 빈틈을 검증하는 데 수개월에서 수년이 걸립니다. 반면 1,700만 줄짜리 Lean 4 코드는 인간 통독 없이 하루 만에 인증되었습니다. 이 비대칭을 가능하게 하는 핵심 원리가 **de Bruijn criterion** 입니다. 증명 탐색과 생성에는 수천만 줄의 비신뢰 코드나 AI 모델을 자유롭게 동원하되, 최종 정당성 판정은 극도로 작고 단순한 신뢰 컴퓨팅 기반(TCB, Trusted Computing Base)인 타입 체커 커널이 모든 추론 규칙을 기계적으로 재검사하도록 분리하는 구조입니다.

그러나 AI가 생성한 1,700만 줄 코드를 다룰 때는 단순히 "Lean이 컴파일되었다"는 문장만으로 충분하지 않습니다. Kevin Buzzard가 2026년 11월 12일 Xena 블로그에서 정리하고 Lean FRO가 이번 인증의 근거로 채택한 4대 기준은 보상 해킹(reward hacking)과 컴파일러 결함까지 겨냥한 심층 방어(defense-in-depth) 체크리스트입니다.

### 2.1. 명제 격리, 공리 감사, 산술 귀결 교차 검증

AI가 증명 파일 중간에서 표준 수학 정의를 슬쩍 약화시키거나 가짜 공리를 몰래 선언해 버리면, 컴파일은 통과해도 정작 원래 문제를 증명하지 않은 셈이 됩니다. 이를 막기 위해 검증 커뮤니티는 **명세(Challenge)와 구현(Solution)의 신뢰 경계를 물리적으로 분리** 했습니다.

먼저 Mathlib에 이미 존재하고 수년간 정수론과 Lean 전문가들이 검증한 표준 리만 가설 정의만 단독으로 임포트하는 격리된 `Challenge.lean`을 구성합니다. 아래는 Mathlib `RiemannZeta.lean`의 표준 명제를 ASCII 표기로 옮긴 핵심 구조입니다(실제 Lean 소스에서는 유니코드 논리 기호를 사용합니다).

```text
-- Mathlib/NumberTheory/LSeries/RiemannZeta.lean (ASCII 표기 요약)
def RiemannHypothesis : Prop :=
  forall (s : Complex),
    riemannZeta s = 0 ->
    (not exists n : Nat, s = -2 * (n + 1)) ->
    s != 1 ->
    s.re = 1 / 2
```

이후 독립 검증 도구인 `Comparator`와 `con-leche --compare`, `con-ron --compare`를 실행해 두 가지를 기계적으로 대조합니다.

```json
{
  "challenge_module": "Challenge",
  "solution_module": "Main",
  "theorem_names": ["riemannHypothesis"],
  "permitted_axioms": ["propext", "Quot.sound", "Classical.choice"]
}
```

- **명제 동치 확인**: Mathlib만 임포트한 챌린지(51,692개 선언)의 정리 타입과 1,700만 줄 솔루션(1,468,418개 선언)이 증명한 정리 타입이 완전히 일치하는지 비교한다. 제출 코드가 중간에 기호나 정의를 바꿨다면 이 단계에서 즉시 탈락한다.
- **공리 감사 (`#print axioms`)**: `Main.lean`의 5개 정리 모두 표준 Lean 공리 3종(`propext`, `Classical.choice`, `Quot.sound`)에만 의존한다. `sorry`나 사용자 정의 외부 공리는 0건이며, 환경 전체에 선언된 15개 공리는 모두 Lean 코어 `Init` 내부에 있다.
- **Mathlib 정의 자체에 대한 산술 교차 검증**: 혹시 Mathlib의 `riemannZeta` 정의 자체에 미묘한 버그가 있을 가능성까지 점검하기 위해, Andrew Sutherland는 제출 증명을 독립 저장소 `kimihiro64/Robin1984`(커밋 `acab1a3`)와 결합했다. 그 결과 제타 함수를 전혀 언급하지 않는 초등 약수 합 부등식 두 개(`robin_inequality`, `lagarias_inequality`)가 추가 가설 없이 도출되었다. `set_option pp.all true`로 펼친 `lagariasStmt`는 직접 상수 27개와 누적 Mathlib/코어 선언 1,801개에만 의존하며, 결합된 61,752,134,938바이트 export(1,472,825개 선언) 역시 `con-leche`, `con-ron`, `nanoda`를 모두 통과했다.

### 2.2. 샌드박스 재빌드와 불활성 Export의 다중 커널 검증

명제가 일치하더라도 또 다른 공격 면이 남습니다. AI가 작성한 1,700만 줄 코드 속에 악성 메타프로그램이 숨어 호스트 파일을 건드리거나, Lean 공식 C++ 커널의 미발견 건전성(soundness) 버그를 악용할 가능성입니다. 실제로 과거 Lean 커널에서도 건전성 버그가 발견되어 수정된 전례가 있습니다.

MIT 검증 팀은 이 위험을 두 단계로 차단했습니다. 첫째, 네트워크가 차단된 읽기 전용 샌드박스 머신에서 `lake build Main`을 독립 재실행했습니다. Mathlib 8,322개와 의존성 378개 `.olean` 파일이 공식 캐시와 바이트 단위로 일치함을 확인했고, 재빌드로 생성한 `lean4export` 파일이 정확히 61,570,595,788바이트(약 61.6 GB, `sha256: 5ea74b91...244e`)로 원본 공개 export와 바이트 단위 동일함을 입증했습니다. 175,187개 모듈 중 175,186개가 완전히 동일한 `.olean`을 생성했고 나머지 1개는 비결정적 컴파일 특성을 보였으나 최종 export는 동일했습니다.

둘째, **실행 가능한 Lean 소스가 아니라 순수 데이터인 불활성(inert) 61.6 GB export만 여러 언어로 독립 구현된 커널들에 투입했습니다.** 이렇게 하면 증명 소스에 숨은 메타프로그램이나 컴파일러 플러그인이 커널 검사 과정에 개입할 수 없습니다.

| 검증기 / 커널 | 구현 언어와 설계 특징 | MIT 실측 결과 (61.6 GB export 기준) |
| --- | --- | --- |
| `con-leche` | Lean 작성. 집합론 모델 기반 일관성 증명(`main_no_False`) 보유, `Lean.Expr` C++ 미사용 | 1,468,418개 선언 `--verified` 통과 (64스레드 3분 15초); `--compare` 5개 정리 통과 |
| `con-ron` | Rust 포팅. 생성자별 배열 hash-consing DAG, Aeneas 경유 Lean 트윈 동치 증명 | `--compare` `--verified` 통과 (64스레드 7분 6초) |
| `nanoda` | Chris Bailey가 Rust로 독립 구현한 외부 타입 체커 | 전체 export 통과 (80스레드 27분 42초) |
| `lean4lean` | Lean으로 작성된 독립 커널 (컴파일된 모듈별 검사) | 175,187/175,187 모듈 통과 (5개는 `decide +kernel` 스텝 상한 상향) |
| Lean 기본 커널 | 공식 C++ 커널 (`leanchecker --from-export`, v4.36.0) | 통과 (단일 스레드 48시간 3분, 82.6 GiB; `MIMALLOC_GENERIC_COLLECT=1000000` 시 9시간 8분) |
| Lean paranoid 커널 | 엄격 검증 모드 (`leanchecker-paranoid --from-export`, v4.36.0) | 통과 (단일 스레드 72시간 20분, 98.8 GiB; allocator 조정 시 10시간 0분) |
| `Comparator v4.33.0` | 명제 비교 + 공리 감사 + `nanoda` + Lean 기본 커널 통합 실행 | 64시간 8분 만에 `"Your solution is okay!"` 통과 (`lake comparator` v4.36.0은 paranoid 및 `nanoda` 통과 후 기본 커널 진행 중) |

여기서 주목할 설계 디테일이 하나 더 있습니다. `con-leche` README에 따르면 `con-leche`와 `con-ron` 역시 Lean FRO의 Joachim Breitner 감독 아래 Claude의 도움을 받아 구현되었으며, `con-ron`의 Rust 코드 동치 증명은 Aeneas 번역기에 의존합니다. 따라서 **단일 검증기에 모든 신뢰를 몰아주는 대신, 서로 다른 언어와 개발 계보를 가진 `con-leche`, `con-ron`, `nanoda`, `lean4lean`, Lean C++ 기본/paranoid 커널이 모두 같은 불활성 export를 통과하게 만든 병렬 구조** 가 검증 신뢰도의 핵심입니다. 어느 한 구현체의 미발견 버그를 뚫더라도, 계보가 다른 여러 커널의 미발견 버그를 동시에 뚫지 못하면 거짓 증명이 살아남을 수 없습니다.

{% include diagrams/static/ai/formal-verification/lean-rh-tcb-verification.html %}
{% include diagrams/download.html png="/assets/img/diagrams/static/ai/formal-verification/lean-rh-tcb-verification--ead3b5ebc5ab6168.png" %}

---

## 3. 왜 AI는 형식 수학에서 먼저 돌파했는가 - 닫힌 검증 루프

리만 가설 증명이 돌발 사건처럼 보이지만, 지난 2년간 AI 역량이 뻗어 나간 경로를 보면 일관된 패턴이 드러납니다. 2024년 12월 `o3`가 고난도 수학 경시대회 AIME를 석권한 뒤, 2025년에서 2026년 사이 소프트웨어 코딩, 취약점 분석과 사이버 보안, 그리고 자율 에이전트 도구 활용이 급격히 성숙했고 2026년 11월 1,700만 줄 Lean 증명으로 이어졌습니다.

이 영역들이 공통으로 가진 구조적 조건은 **닫힌 검증 가능 피드백 루프(Closed Verifiable Feedback Loop)** 입니다.

- **노이즈 없는 0/1 오라클**: Lean 커널, 정적 타입 컴파일러, 단위 테스트 스위트, 익스플로잇 재현 샌드박스는 후보 해답이 맞는지 틀린지 결정론적으로 즉시 판정한다.
- **무제한 탐색과 RLVR**: 인간 평가자의 주관을 기다리지 않고, 실패 오류 메시지를 그대로 다음 탐색의 입력으로 되먹이며 대규모 테스트타임 탐색과 RLVR(Reinforcement Learning with Verifiable Rewards)을 반복할 수 있다.
- **생성과 검증의 극단적 비용 비대칭**: 1,700만 줄 증명을 찾아내는 데는 막대한 탐색과 인간 수학자의 방향 설정이 필요했지만, 그 결과를 `con-leche`로 재검증하는 데는 64스레드 기준 3분 15초면 충분했다.

Alpoge의 `remark.pdf`는 이 협업의 실제 분업 구조도 투명하게 보여 줍니다. 인간 수학자가 토이 문제의 푸리에 해석적 착상과 함수체 Stepanov 논증 사이의 유추를 잡고 보형 형식 쪽으로 방향을 틀어 주자, Claude가 연쇄 theta lift의 길이를 `sqrt(X)`로 잡는 구체적 구성을 제안하고 거대한 형식화 탐색 공간을 밀어붙였습니다. **AI가 돌파력을 발휘한 지점은 모호한 세계 전체가 아니라, 정확한 기계 오라클이 즉시 틀림을 잡아내는 닫힌 형식 공간이었습니다.**

---

## 4. Alexandr Wang의 "Superintelligence is Arriving" 비판적 해부

리만 가설 인증 이틀 뒤인 2026년 11월 22일 22:50 UTC(한국 시간 11월 23일 07:50 KST), Meta CAIO Alexandr Wang은 X에 8개 문단 분량의 글 "Superintelligence is Arriving"을 게시했습니다. 그의 논증은 2024년 12월 전환점과 2026년 11월 전환점을 평행선으로 놓는 구조입니다.

| 구분 | 2024년 12월 전환점 (AIME / `o3`) | 2026년 11월 전환점 (Riemann Hypothesis) |
| --- | --- | --- |
| 지적 기준선 | 고난도 청소년 수학 경시대회 (일상 엔지니어링/비즈니스 난이도 상회) | 150년 미해결 인류 최고 난제 (전 학문 최상위 이론 난이도 상회) |
| 해소된 병목 | 실무 추론에 필요한 원천 지능 | 프론티어 과학과 AI 연구에 필요한 원천 지능 |
| 남은 병목 | 도메인 맥락, 전술적 제약, 도구 연동 | 도메인 노하우, 연결 배관(plumbing), 실험 및 피드백 루프 |
| 파급 결과 | 코딩 사실상 해결, 고성능 사이버 역량, 범용 에이전트 조력자 | AI 연구 자체 자동화(RSI), 생물/무기/경제 연구의 인간 이해 속도 초과 |
| 핵심 질문 | 어떻게 실무 워크플로에 연결할 것인가 | 사회 이양(handover)을 막고 인간 주체성(agency)을 어떻게 지킬 것인가 |

### 4.1. 논거가 성립하는 지점

엔지니어링 관점에서 이 에세이가 정확히 짚은 대목은 세 가지입니다.

첫째, **비지능 병목으로의 이동** 입니다. 실제로 2024년 말 이후 코딩과 보안 에이전트의 실무 체감 성능을 끌어올린 동력은 모델 가중치 향상만이 아니라, 컨텍스트 파이프라인, 샌드박스 도구 연동, 자동 테스트 하네스 같은 연결 배관(plumbing)의 정비였습니다.

둘째, **이해 격차(Comprehension Gap)** 의 현실화입니다. 에세이가 짚었듯 수학계가 아직 리만 가설 증명을 소화하지 못한 것과 마찬가지로, AI가 생성하는 코드와 분석의 속도가 인간의 검토와 감시 속도를 넘어서면 통제 사각지대가 생깁니다. 이는 이미 대규모 AI 생성 PR을 다루는 소프트웨어 팀들이 매일 마주하는 현상입니다.

셋째, **프레임 전환** 입니다. 업계 일각에서 초지능(ASI)을 필연으로 받아들이고 "어떻게 안전하게 사회를 AI에 넘겨줄 것인가(handover)"만 고민하는 태도를 게으른 사고라고 비판하며, 모든 인간의 주체성(agency)과 역량 강화를 보존하는 방향으로 설계를 틀어야 한다고 제기한 지점은 정렬(alignment) 논쟁의 핵심을 건드립니다.

### 4.2. 반론과 구조적 한계

그러나 시스템 아키텍처 관점에서 보면 이 논증에는 세 가지 중요한 비약과 빈틈이 있습니다.

첫째, **닫힌 형식 체계와 열린 물리/운영 세계의 구조적 단절** 입니다. 에세이는 MIT 교수들의 평가를 인용해 다른 학문 분야의 최고 난제도 리만 가설보다 지적으로 "쉽다"고 전제한 뒤, 남은 간극을 도메인 노하우, 배관, 실험으로 묶습니다. 하지만 리만 가설은 공리가 완결되어 있고 물리적 지연이나 관측 노이즈가 전혀 없는 닫힌 형식 공간입니다. 반면 생물학 wet lab, 반도체 공정, 분산 프로덕션 인프라, 경제와 정치 제도는 물리적 지연 시간, 불완전한 관측, 예측 불가능한 외부 행위자, 정의되지 않은 요구사항이 지배하는 열린 세계입니다. **형식 커널에서 0/1 오라클을 통과했다고 해서 열린 현실 세계의 병목이 단순 배관 작업으로 선형 환원되지는 않습니다.**

둘째, **실행 가능한 거버넌스 메커니즘의 부재** 입니다. 에세이는 "향후 1년"의 중대성과 "기본 경로(default path)와는 의미 있게 다른 업계 전체의 행동"을 강조하지만, 정작 구속력 있는 수단(연산량 상한, 재귀적 자기 개선 중단 기준, 제3자 독립 감사 의무, 본인 및 소속 조직의 구체적 실행 약속)은 제시하지 않았습니다. 선언만으로는 경쟁 압력 속의 기본 경로를 바꾸기 어렵습니다.

셋째, **단일 사건의 과도한 시간축 외삽** 입니다. 이번 리만 가설 증명에서도 핵심 방향 설정과 문제 틀 짜기는 정수론 전문가 Levent Alpoge가 주도했고, 1,700만 줄의 형식화는 Lean 4와 Mathlib라는 수십 년 축적된 인간 검증 인프라 위에서 가능했습니다. 이를 곧바로 "1년 내 모든 AI 연구의 완전 자동화"로 등치시키는 해석은 검증된 1차 증거를 넘어선 추정입니다.

{% include diagrams/static/ai/formal-verification/closed-loop-vs-devsecops-boundary.html %}
{% include diagrams/download.html png="/assets/img/diagrams/static/ai/formal-verification/closed-loop-vs-devsecops-boundary--030a22d6d5555987.png" %}

---

## 5. DevSecOps와 시스템 아키텍처로 옮겨오는 4가지 설계 원칙

리만 가설 증명과 Alexandr Wang의 에세이가 실무 DevSecOps와 SRE 엔지니어에게 던지는 질문은 매우 구체적입니다. 앞으로 AI 에이전트가 하루에 수만 줄의 애플리케이션 코드, Terraform 모듈, Kubernetes 매니페스트를 쏟아낼 때, 인간 리뷰어가 모든 diff를 줄 단위로 읽어 안전을 보장하는 모델은 더 이상 작동하지 않습니다.

그렇다고 검증을 포기하고 AI에 프로덕션 통제권을 넘겨줄 수도 없습니다. 해법은 Lean 커뮤니티가 1,700만 줄 증명을 인증한 아키텍처를 그대로 소프트웨어와 인프라 전달 파이프라인으로 이식하는 것입니다. **엔지니어링의 핵심 레버리지는 수동 코드 통독에서 신뢰할 수 있는 검증 경계(Verification Boundary) 설계로 이동합니다.**

| Lean 4 리만 가설 검증 계층 | DevSecOps / SRE 아키텍처 대응물 | 차단하는 실패 모드 |
| --- | --- | --- |
| `Challenge.lean` (Mathlib 단독 격리 명제) | 별도 신뢰 저장소의 보안 불변량 (IAM SCP, OPA/Kyverno 정책, NetworkPolicy, 스키마 계약) | AI 에이전트가 테스트나 정책까지 함께 느슨하게 고쳐 통과시키는 보상 해킹 |
| `Comparator` + `#print axioms` | 변경 범위 정책 검사, 권한 확대 감지, 시크릿 스캔(`gitleaks`), 금지 API 정적 차단 | 의도하지 않은 권한 상승, 숨은 의존성 주입, 자격증명 유출 |
| 네트워크 차단 샌드박스 재빌드 + `.olean` 해시 일치 | 격리된 에페메랄 CI 러너, digest 고정 의존성, 재현 빌드와 SLSA/SBOM 증명 | 빌드 스크립트 악성 실행, 공급망 오염, 환경 차이로 인한 검증 불일치 |
| 4계열 독립 다중 커널 (`con-leche`, `con-ron`, `nanoda`, Lean C++) | 생성 에이전트와 분리된 결정론적 검증 파이프라인 (타입 체커, `terraform plan`, 통합/퍼즈 테스트) | AI의 자기 평가 환각과 단일 도구 오탐/미탐으로 인한 결함 통과 |
| 기계 인증과 인간 개념 소화의 분리 | 자동 게이트 통과 이후 비가역 프로덕션 apply 및 권한 변경의 명시적 인간 승인선 | Comprehension Gap 상태에서 발생하는 무인 장애와 통제 상실(handover) |

실무 팀이 당장 적용할 수 있는 설계 원칙은 네 가지로 정리됩니다.

1. **명세와 정책의 물리적 격리 (Specification Auditing)**: AI가 애플리케이션 코드나 IaC를 작성할 때, 그 변경을 평가하는 정책과 불변량(예: Kubernetes Admission 정책, AWS IAM Permission Boundary, 핵심 계약 테스트)은 에이전트가 같은 PR에서 수정할 수 없는 분리된 소유권 경계에 둔다. 인간 리뷰어는 1만 줄 구현 diff보다 50줄짜리 명세와 정책 변경을 가장 엄격하게 감사한다.
2. **생성기와 분리된 작은 TCB 검증기 (Small Independent TCB)**: 코드를 만든 LLM에게 "이 코드가 안전한지 검토해 달라"고 묻는 것은 같은 모델의 실패 모드를 복제하는 일이다. 최종 게이트는 컴파일러, 정적 타입, 정책 엔진, `terraform plan`/`kubectl diff`, 결정론적 회귀 테스트처럼 작고 재현 가능한 비AI 검증기가 맡고, 가능하면 서로 다른 검사 계층을 교차 배치한다.
3. **불활성 아티팩트와 격리 샌드박스 배관 (Hermetic Plumbing)**: AI가 생성한 PR을 권한이 있는 호스트나 네트워크가 열린 러너에서 바로 실행하지 않는다. 의존성 digest 고정, 읽기 전용 소스 마운트, 네트워크 차단 샌드박스 빌드, 산출물 해시 대조를 파이프라인의 기본값으로 고정해 메타프로그램이나 빌드 스크립트 오염을 차단한다.
4. **비가역 경계의 인간 주체성 고정 (Explicit Human Approval Boundaries)**: 자동 검증이 인간이 읽어야 할 범위를 줄여 주는 만큼, 확보된 인간 판단력은 비가역 작업의 경계에 집중한다. 프로덕션 인프라 실변경, IAM 권한 확대, 영구 데이터 삭제, 외부 공개 게시 같은 고위험 경계에는 자동화 루프가 우회할 수 없는 명시적 인간 승인선을 유지한다.

---

## 6. 정리

2026년 11월 리만 가설 1,700만 줄 Lean 4 증명의 하루 만의 인증은 "AI가 얼마나 똑똑해졌는가"만큼이나 **"인간이 통독할 수 없는 거대한 AI 산출물을 어떤 구조로 신뢰할 것인가"** 에 대한 실전 해답을 보여 주었습니다. `Challenge.lean`으로 명제를 격리하고, 샌드박스 재빌드로 61.6 GB 불활성 export를 고정한 뒤, 서로 다른 언어와 계보의 다중 커널로 교차 검증한 아키텍처는 형식 수학만의 기술이 아닙니다.

닫힌 0/1 오라클이 있는 형식 세계와 달리, 우리가 운영하는 프로덕션 인프라는 지연과 노이즈가 가득한 열린 세계입니다. 그렇기에 AI 생성 속도가 인간의 이해 속도를 앞지르는 시대의 시스템 안전성은 더 많은 수동 코드 리뷰가 아니라, **격리된 명세, 작고 독립적인 검증 커널, 재현 가능한 샌드박스 배관, 그리고 비가역 경계에 고정된 인간 승인선** 위에서 지켜집니다.

---

## 7. Reference

- [Levent Alpoge - Remark (Official Release Note PDF)](https://alpo.ge/remark.pdf)
- [Lean Community Blog - Lean verification of the Riemann Hypothesis (Lean FRO & Mathlib Initiative Joint Statement)](https://leanprover-community.github.io/blog/posts/riemann-hypothesis/)
- [Andrew Sutherland (MIT) - RH Lean proof: verification files](https://math.mit.edu/~drew/grh/)
- [Xena Project - "...and the proof is checked in Lean" (Kevin Buzzard)](https://xenaproject.wordpress.com/2026/11/12/and-the-proof-is-checked-in-lean/)
- [Mathlib4 Docs - RiemannHypothesis Definition](https://leanprover-community.github.io/mathlib4_docs/Mathlib/NumberTheory/LSeries/RiemannZeta.html#RiemannHypothesis)
- [GitHub - leanprover/con-leche](https://github.com/leanprover/con-leche)
- [GitHub - leanprover/con-ron](https://github.com/leanprover/con-ron)
- [GitHub - leanprover/comparator](https://github.com/leanprover/comparator)
- [GitHub - ammkrn/nanoda_lib](https://github.com/ammkrn/nanoda_lib)
- [GitHub - digama0/lean4lean](https://github.com/digama0/lean4lean)
- [GitHub - leanprover/lean4export](https://github.com/leanprover/lean4export)
- [GitHub - kimihiro64/Robin1984](https://github.com/kimihiro64/Robin1984)
- [Clay Mathematics Institute - Riemann Hypothesis](https://www.claymath.org/millennium/riemann-hypothesis/)
- [Alexandr Wang on X - Superintelligence is Arriving](https://x.com/alexandr_wang/status/2124636606959345776)

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
