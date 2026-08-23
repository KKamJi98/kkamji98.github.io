---
title: "im-not-ai 스킬 알아보기"
date: 2026-08-23 14:10:00 +0900
author: kkamji
categories: [AI, Claude Code]
tags: [claude-code, agent-skills, plugin, im-not-ai, humanizer, korean, technical-writing]
comments: true
image:
  path: /assets/img/kkam-img/kkam.webp
---

`im-not-ai`는 AI가 쓴 한글 텍스트에서 내용은 건드리지 않고 문체와 리듬만 자연스러운 한국어로 되돌리는 스킬입니다. 저장소 이름은 `im-not-ai`이고 설치되는 플러그인 이름은 `humanize-korean`입니다. Claude Code, GitHub Copilot CLI, Codex CLI, Gemini CLI를 지원합니다.

---

## 1. 설치

저장소 자체가 마켓플레이스라 클론 없이 설치합니다.

```bash
claude plugin marketplace add epoko77-ai/im-not-ai
claude plugin install humanize-korean@im-not-ai
```

```text
  humanize-korean@im-not-ai
    Version: 2.3.2
    Scope: user
    Status: enabled
```

스킬 3개(`humanize-korean`, `humanize`, `humanize-redo`)와 서브에이전트 9개가 함께 설치됩니다. 실체는 `~/.claude/plugins/cache/im-not-ai/humanize-korean/2.3.2/` 아래에 놓입니다.

클론해서 심링크로 쓰는 방법도 있습니다. 저장소를 직접 수정하면서 쓰고 싶을 때 유용합니다.

```bash
git clone https://github.com/epoko77-ai/im-not-ai.git
cd im-not-ai
./install.sh --claude-only
```

---

## 2. 사용법

새 세션에서 `/humanize-korean`을 호출하거나 자연어로 요청합니다.

```text
/humanize-korean <윤문할 텍스트>
이 글 AI 티 없애줘
번역투 고쳐줘
```

인자 끝에 자연어로 옵션을 붙입니다.

| 옵션 | 효과 |
|---|---|
| `장르: 칼럼\|리포트\|블로그\|공적` | 장르 명시. 생략하면 자동 추정 |
| `강도: 보수\|기본\|적극` | 윤문 강도. 기본값은 기본 |
| `--strict` 또는 `정밀 모드` | 가장 무거운 3콜 경로로 고정 |
| `가볍게` 또는 `빠르게만` | 가장 가벼운 1콜 경로로 고정 |

`/humanize-redo`는 앞선 결과를 다시 윤문합니다. "이 문단만", "이 카테고리만 다시" 같은 후속 요청도 같은 스킬이 받습니다.

---

## 3. 왜 한글 전용인가

영어권 humanizer가 한국어에 약한 이유는 한글 AI 글의 티가 대부분 영어 번역투에서 나오기 때문입니다. 영어 문장 구조를 한글 조사로 옮긴 흔적이 남습니다.

| 번역투 | 자연스러운 한국어 |
|---|---|
| AI 기술을 통해 효율을 높일 수 있다 | AI로 효율을 높인다 |
| 이에 있어서 중요한 점은 | 여기서 중요한 건 |
| ~에 의해 생성된 | ~가 만든 |
| 결론적으로, 이는 시사하는 바가 크다 | (삭제) |

이 패턴을 10대 카테고리 아래 70개 서브 패턴으로 정리해 저장소의 SSOT 파일 하나로 관리합니다.

| ID | 대분류 | 대표 패턴 |
|---|---|---|
| A | 번역투 | ~를 통해, ~에 있어서, 이중 피동 ~되어진다, 이중 조사 ~에서의 |
| B | 영어 인용 과다 | 과도한 괄호 병기, 번역 가능한 영어를 그대로 둠 |
| C | 구조적 AI 패턴 | 기계적 첫째 둘째 셋째, 과도한 불릿과 이모지, 대구 병렬 |
| D | AI 특유 관용구 | 결론적으로, 시사하는 바가 크다, 주목할 만하다 |
| E | 리듬 균일성 | 문장 길이 편차 낮음, 동일 종결어미 반복 |
| F | 수식 중복 | 매우, 정말, 동의어 이중 수식 |
| G | Hedging 남용 | ~할 수 있을 것으로 보인다 |
| H | 접속사 남발 | 문두 또한, 따라서, 즉의 연속 |
| I | 형식명사 과다 | 것이다, 점, 수, ~할 필요가 있다 |
| J | 시각 장식 남용 | 과도한 볼드, 대시 남발 |

패턴마다 심각도가 붙습니다.

- S1은 한 번만 나와도 AI로 확신하는 것이라 무조건 제거한다
- S2는 1회에서 2회까지 허용하고, 3회 이상 반복되면 제거한다
- S3는 다른 패턴과 겹칠 때만 문제로 본다

---

## 4. 세 가지 경로

![결정적 점수가 경로를 고르고 경로가 LLM 콜 수를 정하는 흐름](/assets/img/ai/humanize/humanize-route-hint.webp)

입력이 들어오면 LLM이 아니라 파이썬 스크립트가 먼저 글을 읽습니다. `prepare_monolith_input.py`가 카운트형 지표와 위험 등급을 산출하고, 그 점수로 `route_hint`를 결정합니다.

| 경로 | LLM 콜 수 | 조건 | 파이프라인 |
|---|---|---|---|
| light | 1 | 카운트형 티 2건 이하, 위험 등급 낮음 | 진단과 finalize 생략, 보수적 윤문 한 번 |
| standard | 2 | 티가 섞여 있거나 구조 지표로 위험 높음 | 진단 한 번, 겨냥 윤문 한 번 |
| heavy | 3 이상 | 티 8건 이상 밀집, 또는 15000자 초과 | 진단, 윤문, finalize |

판정에 쓰는 지표는 전부 정수 카운트입니다. 마무리 관용구 수, 이중 피동 수, `가지고 있다` 같은 직역 표현 수, 이중 조사 수를 셉니다. 밀도나 z-score 같은 상대 지표는 판정에서 빼두었는데, 저장소가 밝힌 이유는 v2 baseline이 아직 placeholder라 불안정하다는 것입니다.

절감은 모델을 싼 것으로 바꿔서 나오지 않습니다. 콜 수를 줄여서 나옵니다. 잘 쓴 글에 최중량 파이프라인을 돌리던 낭비를 `route_hint`가 차단합니다.

청킹에 관한 실측도 공개돼 있습니다. 1만자 글을 7개 청크로 쪼개면 610K 토큰, 단일 콜로 돌리면 134K 토큰이었고 품질은 동등했습니다. 청크마다 룰북과 진단을 다시 로드하는 비용이 병렬화 이득을 전부 먹었기 때문입니다. 그래서 청킹은 heavy 경로 전용이고 15000자 이하에는 권장하지 않습니다.

---

## 5. 의미를 지키는 장치

윤문 도구에서 실제 위험은 티를 못 잡는 쪽이 아니라 문장을 다듬다가 주장을 바꿔버리는 쪽입니다. 이 스킬은 네 가지 제약을 걸어둡니다.

- 의미 불변: 사실, 수치, 고유명사, 직접 인용은 원문 그대로 보존한다
- 근거 기반: 탐지된 구간에만 수정한다. 탐지 없는 구간은 건드리지 않는다
- 장르 유지: 칼럼을 문학으로, 리포트를 에세이로 옮기지 않는다
- 과윤문 금지: 변경률 30%를 넘으면 경고하고 50%를 넘으면 강제 중단한다

마지막 항목의 판정을 모델의 자기 보고가 아니라 파이썬 스크립트가 합니다. `verify_gates.py`가 문자 기준 변경률, S1 목표 달성, 대구 전멸 여부, 수치와 고정 문구 보존 네 축을 검사하고 종료 코드로 결과를 냅니다.

축을 네 개 둔 이유도 실측에서 나왔습니다. 문자 변경률 2.77% 뒤에 문장 터치율 29.7%와 대구 75% 감소가 숨어 있던 사례가 있었습니다. 문자 diff만 보면 구조 편집을 놓칩니다.

---

## 6. 쓸 때 알아둘 것

- **어휘 카운트라 인용을 구분하지 못한다.** AI 티 예시를 본문에 적어둔 글은 스스로 티 판정을 받는다.
- **heavy는 심각도가 아니라 분량이다.** 15000자 초과 조건이 먼저 걸리므로 티가 1건인 글도 heavy로 나온다.
- **짧은 글은 위험 등급이 튄다.** 문장 수가 적어 리듬 지표의 분산이 커진다.
- **사람이 직접 쓴 글은 대상에서 뺀다.** 개인 회고나 구어체 메모는 리듬이 불규칙한데, 그 불규칙성이 사람이 쓴 증거다.
- **저장소별 문체 규칙이 있으면 룰북보다 위에 둔다.** 존댓말 고정이나 금지 문자 같은 규칙은 룰북에 없으니 윤문 지시에 직접 넣어야 한다.

---

## 7. Reference

- [epoko77-ai - im-not-ai](https://github.com/epoko77-ai/im-not-ai)
- [im-not-ai - INSTALL.md](https://github.com/epoko77-ai/im-not-ai/blob/main/INSTALL.md)
- [Claude Docs - Plugins](https://docs.claude.com/en/docs/claude-code/plugins)
- [Claude Docs - Agent Skills](https://docs.claude.com/en/docs/claude-code/skills)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
