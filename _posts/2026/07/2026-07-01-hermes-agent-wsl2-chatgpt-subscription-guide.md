---
title: WSL2에서 Hermes Agent로 개인 ChatGPT 구독 기반 자율 AI Agent 구축하기
date: 2026-07-01 09:00:00 +0900
author: kkamji
categories: [AI, Agent]
tags: [hermes-agent, wsl2, ai-agent, openai-codex, chatgpt, automation, self-hosted]
comments: true
image:
  path: /assets/img/ai/hermes.webp
---

Hermes Agent는 터미널과 메시징 환경에서 동작하는 self-hosted open-source agent입니다. 단순한 CLI 챗봇이 아니라 memory, `SOUL.md` persona, skills, cron, messaging gateway를 함께 사용해 개인 작업 환경에 상주하는 자율 AI agent로 구성할 수 있습니다. 이번 글에서는 WSL2 위에 Hermes Agent를 설치하고, 개인 ChatGPT Plus/Pro 구독 기반의 `openai-codex` provider를 연결해 zero-to-100 형태로 구축하는 흐름을 정리합니다.

> **TL;DR**  
> - Hermes Agent는 `github.com/NousResearch/hermes-agent`에서 제공되는 self-hosted open-source agent입니다.  
> - WSL2에서는 `curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash`로 설치하며, installer가 `uv`, Python 3.11, Node, ripgrep까지 준비합니다.  
> - 핵심은 provider와 runtime을 분리해 이해하는 것입니다. `hermes model`에서 `openai-codex` provider를 선택하되, `codex_app_server` runtime은 켜지 않습니다.  
> - 기본 runtime과 `openai-codex` provider 조합은 Hermes tool loop를 유지하면서 개인 ChatGPT Plus/Pro 구독으로 과금됩니다.  
> - 항상 켜 두려면 Telegram gateway, systemd user service, `loginctl enable-linger`, Windows 로그인 시 WSL 시작 구성을 함께 잡아야 합니다.  
{: .prompt-info}

---

## 1. 목표 아키텍처

목표는 WSL2 안에 Hermes Agent를 설치하고, 개인 ChatGPT 구독을 LLM provider로 사용하며, Telegram 같은 messaging gateway를 통해 언제든 접근 가능한 개인 agent를 만드는 것입니다.

구성 요소는 다음과 같이 나눌 수 있습니다.

| 구성 요소 | 역할 |
| :--- | :--- |
| WSL2 | Windows 위에서 Linux 환경을 제공하는 실행 기반 |
| Hermes Agent | memory, skills, cron, gateway를 갖춘 self-hosted agent |
| `openai-codex` provider | 개인 ChatGPT Plus/Pro 구독 기반 OAuth provider |
| 기본 Hermes runtime | memory, session_search, delegate_task, todo를 포함한 tool loop |
| Telegram gateway | 터미널 밖에서도 agent에 접근하기 위한 messaging gateway |
| systemd user service | WSL 세션과 독립적으로 gateway를 유지하기 위한 서비스 |

이 구조에서 가장 중요한 결정은 `openai-codex`를 **runtime이 아니라 provider로만** 사용한다는 점입니다. provider는 어떤 모델 계정으로 추론 비용을 낼지 결정하고, runtime은 agent loop와 tool 실행 방식을 결정합니다. 둘을 섞어서 이해하면 Hermes의 핵심 기능을 잃을 수 있습니다.

---

## 2. WSL2 사전 준비

Hermes를 항상 켜 두는 agent로 쓰려면 WSL2에서 systemd가 동작해야 합니다. systemd가 있어야 user service를 통해 gateway를 안정적으로 실행할 수 있습니다.

`/etc/wsl.conf`에 다음 내용을 둡니다.

```ini
[boot]
systemd=true
```

이 설정은 WSL2 부팅 시 systemd를 활성화하기 위한 설정입니다. 이후 WSL2를 다시 시작하면 systemd 기반 user service를 사용할 수 있는 상태가 됩니다.

> WSL2에서 systemd가 비활성화되어 있으면 gateway를 장기 실행 서비스로 관리하기 어렵습니다. Hermes Agent를 단발성 CLI가 아니라 항상 켜진 개인 agent로 쓰려면 이 단계를 먼저 확인해야 합니다.  
{: .prompt-warning}

---

## 3. Hermes Agent 설치

WSL2 환경에서 설치는 공식 installer를 사용합니다.

```bash
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
```

이 installer는 Hermes 실행에 필요한 구성 요소를 함께 준비합니다.

- `uv`
- Python 3.11
- Node
- ripgrep

설치가 끝나면 Hermes는 self-hosted agent로 동작할 준비를 갖춥니다. 이후의 작업은 단순히 바이너리를 실행하는 단계가 아니라, provider, runtime, memory, skills, gateway를 어떤 방식으로 묶을지 결정하는 구성 단계입니다.

---

## 4. Provider와 runtime을 분리해서 이해하기

이 글의 핵심입니다. Hermes에서 provider와 runtime은 독립적인 개념입니다.

| 구분 | 의미 | 이번 구성의 선택 |
| :--- | :--- | :--- |
| Provider | 어떤 계정과 모델 경로로 LLM을 호출할지 결정 | `openai-codex` provider |
| Runtime | agent loop와 tool 실행 방식을 결정 | 기본 Hermes runtime |

개인 ChatGPT Plus/Pro 구독을 사용하려면 `hermes model`에서 `openai-codex` provider를 선택합니다.

```bash
hermes model
```

`openai-codex` provider는 OAuth 기반입니다. API key를 직접 넣는 방식이 아니라 개인 ChatGPT Plus/Pro 구독을 통해 인증합니다. 단, 회사 또는 workspace 계정으로 진행하면 phone verification에 걸릴 수 있으므로 개인 구독 계정을 사용하는 것이 중요합니다.

반대로 `codex_app_server` runtime은 활성화하지 않습니다. 이 runtime을 켜면 Hermes의 기본 tool loop가 아니라 Codex app server 방식으로 실행되며, 다음 기능들이 비활성화됩니다.

- memory
- session_search
- delegate_task
- todo

개인 agent를 만드는 목적에서는 이 기능들이 핵심입니다. 따라서 원하는 조합은 **기본 Hermes runtime과 `openai-codex` provider**입니다. 이 조합은 Hermes의 tool loop와 memory 기반 동작을 유지하면서, 추론 비용은 개인 ChatGPT 구독으로 처리합니다.

---

## 5. API mode와 reasoning effort

`openai-codex` provider를 사용할 때는 `api_mode` 관점도 함께 이해해야 합니다. 구성은 `chat_completions`와 `codex_responses` 흐름으로 나뉠 수 있습니다. 여기서 중요한 점은 어떤 API mode를 쓰더라도 runtime 선택과 provider 선택을 혼동하지 않는 것입니다.

reasoning effort는 `~/.hermes/config.yaml`의 `agent.reasoning_effort`에서 조정합니다.

```yaml
agent:
  reasoning_effort: medium
```

사용 가능한 값은 다음과 같습니다.

- `minimal`
- `low`
- `medium`
- `high`

높은 reasoning effort는 더 깊게 생각하게 만들 수 있지만, 개인 ChatGPT 구독의 rate limit을 더 빠르게 소모합니다. 장시간 자동화나 Telegram 기반 상시 사용을 염두에 둔다면 기본값을 무조건 높이기보다 작업 성격에 맞춰 조절해야 합니다.

> 개인 구독 기반 구성에서는 "더 높은 reasoning effort가 항상 더 좋다"가 아닙니다. quota와 latency를 함께 고려해야 합니다.  
{: .prompt-tip}

---

## 6. Memory, SOUL.md, skills, cron으로 agent화하기

Hermes Agent를 단순한 LLM wrapper가 아니라 개인 agent로 만드는 핵심은 상태와 절차를 누적하는 기능입니다.

### 6.1. Memory

memory는 세션을 넘어 유지되는 사용자 정보, 환경 정보, 선호를 저장합니다. 개인 agent가 매번 같은 배경 설명을 요구하지 않도록 만드는 기반입니다. 구축 후에는 headless 실행으로 memory가 실제로 쓰이는지 확인해야 합니다.

확인 대상 파일은 다음과 같습니다.

```text
~/.hermes/memories/USER.md
```

`hermes -z` headless run을 실행한 뒤, 사용자 관련 memory가 위 파일에 기록되는지 확인하면 memory 경로가 정상 동작하는지 검증할 수 있습니다.

### 6.2. SOUL.md persona

`SOUL.md`는 agent의 persona를 정의하는 파일입니다. memory가 사실과 선호를 저장한다면, `SOUL.md`는 agent가 어떤 정체성과 톤으로 동작할지를 정합니다.

### 6.3. Skills

skills는 반복 가능한 절차를 문서화해 agent가 다음 세션에서도 재사용할 수 있게 합니다. 예를 들어 블로그 작성, 배포 점검, incident triage 같은 작업은 skills로 만들면 agent의 작업 품질이 누적됩니다.

### 6.4. Cron

cron은 정해진 시각이나 주기에 agent 작업을 실행하는 기능입니다. 개인 agent를 "질문을 받으면 답하는 도구"에서 "주기적으로 상태를 확인하고 보고하는 도구"로 확장하는 축입니다.

---

## 7. Telegram gateway와 항상 켜짐 구성

개인 agent의 사용성을 높이려면 터미널에 붙어 있을 필요가 없어야 합니다. Hermes는 messaging gateway를 제공하므로 Telegram을 연결해 모바일에서도 agent에게 작업을 맡길 수 있습니다.

gateway 설정은 다음 명령으로 시작합니다.

```bash
hermes gateway setup
```

항상 켜짐 구성을 위해서는 네 가지가 함께 필요합니다.

1. Telegram gateway 설정
2. systemd user service 구성
3. `loginctl enable-linger` 적용
4. Windows 로그인 시 WSL 시작 구성

`loginctl enable-linger`는 사용자가 로그인하지 않은 상태에서도 user service가 유지되도록 하는 설정입니다. WSL2에서는 여기에 Windows 로그인 시 WSL이 시작되도록 하는 구성이 더해져야 실제로 재부팅 이후에도 agent가 살아납니다.

이 단계까지 완료하면 Hermes Agent는 WSL2 내부에서 장기 실행되고, Telegram을 통해 호출 가능한 개인 assistant가 됩니다.

---

## 8. 검증 체크리스트

구성이 끝났다면 다음 항목을 순서대로 확인합니다.

### 8.1. Headless run 확인

`hermes -z` headless run으로 터미널 UI 없이 agent가 작업을 처리하는지 확인합니다. 이 검증은 gateway와 cron처럼 비대화형 실행 경로를 신뢰하기 위한 기본 확인입니다.

### 8.2. Memory write 확인

headless run 이후 다음 파일에 memory가 기록되는지 확인합니다.

```text
~/.hermes/memories/USER.md
```

memory가 기록된다면 기본 Hermes runtime이 유지되고 있다는 강한 신호입니다. 반대로 memory가 동작하지 않는다면 `codex_app_server` runtime을 잘못 활성화했는지 다시 확인해야 합니다.

### 8.3. 핵심 tool 유지 확인

개인 agent 구성에서 반드시 유지해야 하는 기능은 다음과 같습니다.

- memory
- session_search
- delegate_task
- todo

이 기능들이 유지되어야 Hermes가 세션 기억, 과거 대화 검색, 하위 agent 위임, 작업 목록 관리를 모두 수행할 수 있습니다.

---

## 9. 운영 거버넌스와 guardrails

Hermes Agent는 사용자의 계정으로 실행됩니다. 따라서 WSL2 안에서 사용자가 접근 가능한 파일과 shell 권한을 agent도 사용할 수 있습니다. 이는 강력한 자동화 능력이지만 동시에 운영 리스크입니다.

특히 다음 성질을 명확히 인식해야 합니다.

- agent는 사용자의 shell 권한으로 명령을 실행할 수 있습니다.
- agent는 자신의 config를 수정할 수 있습니다.
- agent는 self-upgrade를 수행할 수 있습니다.
- gateway를 연결하면 터미널 밖에서도 작업 요청이 들어올 수 있습니다.

따라서 개인 agent라도 guardrails가 필요합니다. destructive command 승인, config 변경 범위, self-upgrade 정책, Telegram 접근 권한, memory에 저장할 정보의 범위를 명확히 정해야 합니다.

> 자율 AI agent의 핵심은 "자동으로 많이 하게 만들기"만이 아니라 "어디까지 자동으로 하게 둘지 정하기"입니다. Hermes는 강력한 shell access를 갖기 때문에 운영 규칙을 먼저 정해 두는 편이 안전합니다.  
{: .prompt-warning}

---

## 10. 마치며

WSL2 위의 Hermes Agent는 개인 개발 환경에 상주하는 self-hosted agent로 구성하기 좋습니다. 설치 자체는 간단하지만, 실제로 중요한 부분은 provider와 runtime을 분리해 이해하는 것입니다.

개인 ChatGPT Plus/Pro 구독을 쓰려면 `hermes model`에서 `openai-codex` provider를 선택합니다. 그러나 `codex_app_server` runtime은 활성화하지 않습니다. 기본 Hermes runtime을 유지해야 memory, session_search, delegate_task, todo가 살아 있고, 이 기능들이 있어야 Hermes가 단순한 채팅 도구가 아니라 장기 기억과 작업 위임을 가진 개인 agent가 됩니다.

마지막으로 Telegram gateway, systemd user service, `loginctl enable-linger`, Windows 로그인 시 WSL 시작 구성을 더하면 항상 접근 가능한 개인 agent에 가까워집니다. 이때 agent가 사용자의 shell 권한으로 실행된다는 점을 잊지 말고, guardrails를 함께 설계해야 합니다.

---

## 11. References

- [NousResearch - Hermes Agent GitHub](https://github.com/NousResearch/hermes-agent)
- [Hermes Agent Installer](https://hermes-agent.nousresearch.com/install.sh)

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
