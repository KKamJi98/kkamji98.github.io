---
title: 여러 AI 코딩 에이전트를 위한 Agentic Development Environment 구축하기
date: 2026-07-12 02:31:00 +0900
author: kkamji
categories: [AI, Development Environment]
tags: [ai-agent, agentic-development, cmux, ghostty, tmux, claude-code, codex, hermes-agent, macos, devsecops]
comments: true
image:
  path: /assets/img/kkam-img/kkam.webp
---

Claude Code, Codex, Hermes처럼 터미널에서 동작하는 AI 코딩 에이전트를 동시에 사용하면 실행 능력은 빠르게 늘어납니다. 그러나 작업 수가 늘어날수록 더 큰 병목은 모델 성능이 아니라 사람이 현재 상황을 파악하고 안전하게 개입하는 과정에서 생깁니다. 어느 저장소에서 어떤 에이전트가 일하는지, 승인을 기다리는 작업이 무엇인지, 같은 파일을 두 에이전트가 수정하고 있지는 않은지를 계속 기억해야 하기 때문입니다.

이 글에서는 MacBook 로컬 환경만을 대상으로, DevSecOps 엔지니어가 여러 AI 코딩 에이전트를 운영하기 위한 Agentic Development Environment를 설계한 과정을 정리합니다. 최종 구성은 cmux를 workspace와 attention cockpit으로 사용하고, Ghostty는 fallback terminal로 남기며, tmux는 cmux 종료 후에도 살아 있어야 하는 장기 interactive process에만 제한적으로 적용하는 구조입니다.

> **TL;DR**  
> - 문제의 핵심은 터미널 개수가 아니라 task location, status, ownership을 한눈에 파악하기 어렵다는 점입니다.  
> - cmux는 macOS에서 workspace sidebar, split pane, notification panel을 한곳에 제공하므로 primary workspace와 attention cockpit으로 사용합니다.  
> - Ghostty는 빠르고 네이티브한 fallback terminal로 유지하지만, 병렬 에이전트의 상태판 역할까지 맡기지는 않습니다.  
> - tmux는 cmux가 닫혀도 계속 실행되어야 하는 장기 interactive process에만 사용합니다. native subagent와 one-shot worker에는 tmux가 필요하지 않습니다.  
> - cmux session restore는 layout과 metadata를 복원하며, 지원되는 에이전트는 native session ID로 resume할 수 있습니다. 임의의 live process state를 보존하는 기능은 아닙니다.  
> - 로컬 tmux도 MacBook reboot 후에는 종료됩니다. 에이전트의 native resume은 대화와 작업 맥락을 다시 여는 recovery path이지, 실행 중이던 프로세스의 checkpoint가 아닙니다.  
> - workspace group은 정리 기능일 뿐 보안 경계가 아닙니다. 권한과 secret 격리는 별도 계정, sandbox, container, VM 같은 실행 경계에서 설계해야 합니다.  
{: .prompt-info}

---

## 1. 문제 정의: 실행 창보다 attention routing이 어렵다

처음에는 Ghostty 창과 tab을 여러 개 열고 Claude Code, Codex, Hermes를 각각 실행했습니다. 작업이 두세 개일 때는 충분했습니다. Ghostty는 macOS native tab과 split을 제공하고 window state recovery도 지원하므로 일반 terminal로서는 완성도가 높습니다.

문제는 병렬 작업이 늘어난 뒤 나타났습니다.

- 어떤 tab이 어떤 repository와 worktree를 가리키는지 기억해야 합니다.
- 에이전트가 실행 중인지, 입력을 기다리는지, 완료했는지 직접 순회해야 합니다.
- 같은 이름의 shell과 agent process가 여러 창에 흩어집니다.
- Claude Code와 Codex desktop app을 함께 열면 terminal, editor, chat surface가 더 분리됩니다.
- Hermes Desktop은 개인 작업 방식에 맞는 primary cockpit이 아니었습니다.
- 승인 요청과 완료 알림이 여러 앱에 흩어져 중요한 신호가 묻힙니다.

따라서 목표는 terminal emulator를 하나 더 고르는 것이 아닙니다. 다음 질문에 빠르게 답할 수 있는 운영 화면을 만드는 것입니다.

1. 지금 어떤 task가 실행 중입니까?
2. 각 task의 repository, branch, worktree는 어디입니까?
3. 어떤 agent가 다음 입력이나 승인을 기다리고 있습니까?
4. 어느 task가 파일을 쓸 권한을 갖고 있습니까?
5. 앱이 닫히거나 MacBook이 재시작되면 무엇이 살아남고 무엇을 복구해야 합니까?

이 관점에서는 Agentic Development Environment를 세 층으로 나누는 편이 명확합니다.

| 계층 | 책임 | 이번 선택 |
| :--- | :--- | :--- |
| Workspace와 attention | task 위치, 상태, 알림, 이동 | cmux |
| Terminal rendering | shell, TUI, text rendering | cmux의 Ghostty 기반 terminal, Ghostty fallback |
| Process lifetime | terminal app 종료와 process 수명 분리 | 필요한 경우에만 tmux |

---

## 2. 설계 원칙

도구 비교 전에 운영 원칙을 먼저 고정했습니다. 원칙이 없으면 모든 terminal feature가 필수처럼 보이고, 결국 multiplexing layer만 중복됩니다.

### 2.1. Task가 workspace의 기본 단위다

agent 종류가 아니라 task를 기준으로 workspace를 만듭니다. 하나의 task workspace 안에서 필요한 agent, test shell, log pane을 함께 둡니다. Claude Code workspace와 Codex workspace를 별도로 만드는 방식은 도구 중심 분류이므로, 같은 task의 context가 다시 흩어질 수 있습니다.

### 2.2. Attention 신호는 사람이 행동해야 할 때만 보낸다

모든 command completion을 알림으로 보내면 attention cockpit이 log viewer로 변합니다. 알림은 승인 필요, 사용자 입력 필요, 실패, 최종 완료처럼 사람이 실제로 판단해야 하는 상태로 제한합니다.

### 2.3. Process persistence와 context recovery를 구분한다

tmux detach는 tmux server가 살아 있는 동안 내부 process를 계속 실행합니다. 반면 agent resume은 저장된 agent session을 다시 여는 기능입니다. 둘은 다음처럼 목적이 다릅니다.

| 기능 | 보존 대상 | 보존하지 않는 것 |
| :--- | :--- | :--- |
| cmux layout restore | window, workspace, pane, working directory, best-effort scrollback | 임의 process memory와 실행 지점 |
| agent native resume | 지원 agent의 session ID와 대화 맥락 | 실행 중 child process의 memory와 open file descriptor |
| tmux detach와 attach | 살아 있는 tmux server 내부의 terminal process | MacBook reboot 이후의 local process |

### 2.4. Organization과 isolation을 구분한다

workspace, group, tab, pane은 사람이 context를 정리하기 위한 UI 단위입니다. 이 이름이나 색상은 filesystem permission, network policy, credential boundary를 만들지 않습니다. 보안 통제는 실행 계정, worktree, container, VM, sandbox, cloud IAM처럼 실제 권한을 강제하는 계층에서 수행해야 합니다.

---

## 3. 후보 도구와 trade-off

이번 비교에서는 MacBook local environment만 다룹니다. Warp, JetBrains 계열 도구, iTerm2는 개인 선호에 따라 후보에서 제외했습니다. 이 제외는 기능의 우열에 대한 평가가 아니라 탐색 범위를 줄이기 위한 제약입니다.

### 3.1. Ghostty 단독

Ghostty는 macOS native UI, tab, split, window state recovery, secure input API를 지원합니다. 일상 shell과 fallback terminal로 사용하기에 적합합니다. 이미 Ghostty에 익숙하다면 별도의 terminal syntax를 학습하지 않고도 빠르게 작업할 수 있습니다.

다만 이번 문제는 terminal rendering이 아니라 여러 agent의 task status와 attention routing입니다. Ghostty의 tab과 split만으로도 배치할 수 있지만, task가 늘면 tab 이름과 창 위치를 사람이 계속 관리해야 합니다. 따라서 Ghostty를 버리는 것이 아니라 역할을 fallback terminal로 좁혔습니다.

### 3.2. cmux

cmux는 Ghostty 기반 terminal에 vertical workspace sidebar, split pane, notification panel, CLI와 socket API를 결합한 macOS app입니다. workspace sidebar에서 working directory와 branch 같은 context를 보고, unread notification이 있는 workspace로 이동할 수 있다는 점이 이번 문제와 직접 맞닿아 있습니다.

선택 이유는 모든 기능이 더 우수해서가 아닙니다. task location과 attention signal을 한 화면에서 연결하는 비용이 가장 낮았기 때문입니다. 반대로 다음 trade-off도 있습니다.

- macOS 전용이므로 cross-platform configuration을 그대로 재사용하기 어렵습니다.
- 빠르게 개발되는 도구이므로 behavior와 shortcut은 version에 따라 달라질 수 있습니다.
- workspace hierarchy와 session restore 개념을 정확히 이해하지 않으면 process persistence를 과대평가할 수 있습니다.
- notification hook과 project-local command는 편리하지만, 실행되는 command와 노출되는 text를 검토해야 합니다.

즉 cmux는 process supervisor나 security sandbox가 아니라 workspace와 attention을 관리하는 cockpit으로 채택합니다.

### 3.3. tmux

tmux는 terminal multiplexer server와 client를 분리합니다. client를 detach해도 server와 그 안의 program이 계속 실행되므로, terminal app을 닫아도 유지해야 하는 interactive process에 적합합니다.

그러나 모든 agent를 tmux 안에 넣으면 cmux와 tmux 양쪽에 session, window, pane 개념이 생깁니다. shortcut layer가 겹치고 현재 위치를 파악하는 비용도 늘어납니다. 따라서 tmux는 다음 질문에 `yes`라고 답할 때만 사용합니다.

> cmux를 지금 완전히 종료해도 이 interactive process가 반드시 계속 살아 있어야 합니까?  

예를 들어 장시간 관찰해야 하는 local log tail, REPL, test watch, foreground dev server가 이에 해당할 수 있습니다. 반대로 native subagent, agent가 내부적으로 생성한 worker, 몇 분 안에 끝나는 one-shot analysis는 parent agent의 lifecycle과 task model로 관리하면 되므로 tmux가 필요하지 않습니다.

tmux server도 local process입니다. MacBook이 reboot되거나 tmux server가 종료되면 session은 사라집니다. tmux는 app close boundary를 넘기기 위한 도구이지 reboot checkpoint가 아닙니다.

### 3.4. Zellij

Zellij는 session manager와 session resurrection을 기본 제공하고, layout, pane, tab, command를 serialize합니다. 종료된 session을 복원할 때 command를 자동 실행하지 않고 확인을 요구하는 기본 동작도 안전 측면에서 의미가 있습니다.

그러나 resurrection은 process memory를 되살리는 것이 아니라 layout과 command를 기반으로 재구성하는 방식입니다. 이번 목표에서는 cmux의 macOS native sidebar와 agent attention 흐름을 우선했기 때문에 primary tool로 고르지 않았습니다. terminal 내부에서 더 풍부한 session UI와 declarative layout을 원하는 경우에는 충분히 검토할 대안입니다.

### 3.5. WezTerm

WezTerm은 Lua configuration과 multiplexing domain을 제공합니다. local 또는 SSH domain에 연결해 window와 tab을 관리할 수 있어 terminal automation과 cross-platform consistency를 중시하면 강력한 선택입니다.

다만 이번 의사결정의 우선순위는 programmable terminal 자체보다 여러 coding agent의 attention을 macOS native sidebar에서 추적하는 것이었습니다. Lua 기반으로 원하는 status와 notification을 직접 구성할 수 있지만, 그만큼 초기 설계와 유지 관리 비용을 부담해야 합니다.

### 3.6. kitty

kitty는 tab, window, remote control API, desktop notification 기능을 제공합니다. script로 window를 제어하거나 notification을 세밀하게 다루려는 경우 유연합니다. remote control을 활성화할 때는 허용 범위와 password policy를 함께 검토해야 합니다.

이번에는 agent task를 workspace 단위로 보여 주는 기본 UX와 macOS cockpit을 우선했기 때문에 선택하지 않았습니다. 기존 kitty automation 자산이 많다면 cmux로 옮기는 비용보다 kitty 구성을 확장하는 편이 더 나을 수 있습니다.

### 3.7. 비교 결과

| 후보 | 강점 | 이번 범위의 제약 | 역할 |
| :--- | :--- | :--- | :--- |
| Ghostty | native macOS UI, 빠른 terminal, tab과 split | agent attention을 task 단위로 모으는 상태판은 직접 운영 | fallback terminal |
| cmux | vertical workspace, notification panel, Ghostty 기반 terminal | macOS 전용, session restore 범위 이해 필요 | primary cockpit |
| tmux | client 종료 후에도 server 내부 process 유지 | reboot persistence 없음, 중첩 multiplexing 비용 | 선택적 persistence layer |
| Zellij | session manager, layout과 command resurrection | 현재 목표보다 terminal 내부 session 관리에 초점 | 대안 |
| WezTerm | Lua automation, multiplexing domain | 직접 구성하고 유지할 범위가 큼 | 대안 |
| kitty | remote control, notification, scriptability | task cockpit을 별도로 설계해야 함 | 대안 |

---

## 4. 최종 아키텍처

```text
MacBook local environment
|
+-- cmux: primary workspace and attention cockpit
|   |
|   +-- Workspace Group: project or operating context
|       |
|       +-- Workspace: one task and one worktree
|       |   +-- Pane: primary writer agent
|       |   +-- Pane: tests, diff, logs
|       |   +-- Native subagent or one-shot worker
|       |
|       +-- Workspace: another task and another worktree
|           +-- Claude Code, Codex, or Hermes
|           +-- tmux only when a live interactive process
|               must survive cmux closing
|
+-- Ghostty: fallback terminal
    +-- recovery, troubleshooting, or cmux-independent shell
```

핵심은 cmux와 tmux의 책임을 겹치지 않는 것입니다.

- cmux는 사람이 task를 찾고 attention을 배분하는 control plane입니다.
- 각 workspace는 하나의 task와 하나의 worktree를 가리킵니다.
- agent CLI는 기본적으로 cmux terminal에서 직접 실행합니다.
- tmux는 명시적인 process lifetime 요구가 있을 때만 한 단계 아래에 둡니다.
- Ghostty는 cmux 장애, 설정 오류, 복구 작업에 사용할 독립 terminal입니다.

이 구조에서는 Claude Code, Codex, Hermes desktop app을 primary surface로 사용하지 않습니다. agent interaction을 cmux terminal로 모아 app switching과 notification fragmentation을 줄입니다. 단, 각 agent의 native session과 resume 기능은 그대로 활용합니다.

---

## 5. Workspace와 session 운영 규칙

도구를 설치하는 것보다 이름과 소유권 규칙을 일관되게 적용하는 일이 더 중요합니다. 다음 규칙은 sidebar만 보고도 task identity와 write ownership을 판단할 수 있게 만드는 최소 규칙입니다.

### 5.1. 이름 규칙

| 대상 | 형식 | 예시 |
| :--- | :--- | :--- |
| Workspace Group | `<project>-<context>` | `platform-prod-readonly` |
| Workspace | `<type>-<task>-<agent>-<state>` | `fix-auth-codex-waiting` |
| Worktree path | `<type>-<short-description>` | `fix-auth-timeout` |
| Branch | `<type>/<short-description>` | `fix/auth-timeout` |
| tmux session | `<project>-<task>-<process>` | `api-auth-test-watch` |

state는 `running`, `waiting`, `review`, `done`, `blocked`처럼 작은 집합으로 제한합니다. 이름이 길어지면 issue number를 넣고 설명을 줄입니다.

```text
fix-142-codex-running
feat-207-claude-review
docs-agent-env-hermes-waiting
```

workspace 이름은 dashboard label입니다. 신뢰할 수 있는 실제 identity는 working directory, Git branch, worktree status입니다. agent에게 mutation을 허용하기 전 다음 세 값을 확인합니다.

```shell
pwd
git branch --show-current
git status --short
```

### 5.2. Single-writer rule

동일한 task와 worktree에는 동시에 한 명의 primary writer만 둡니다.

1. primary writer만 source file을 수정합니다.
2. reviewer agent는 diff와 test result를 읽고 제안만 작성합니다.
3. subagent가 file을 수정해야 한다면 서로 겹치지 않는 file ownership을 사전에 지정합니다.
4. ownership을 나누기 어렵다면 별도 worktree와 branch를 만듭니다.
5. writer가 바뀔 때는 현재 diff, 검증 결과, 남은 작업을 handoff한 뒤 기존 writer의 mutation을 중지합니다.

native subagent는 parent agent가 관리하는 실행 단위입니다. 별도 tmux session을 강제하지 않습니다. one-shot worker도 결과를 반환하고 종료하는 것이 정상 lifecycle이므로 tmux를 추가하지 않습니다. tmux 사용 여부는 agent 종류가 아니라 process가 cmux 종료 이후에도 살아 있어야 하는지로 결정합니다.

### 5.3. Workspace group은 보안 경계가 아니다

cmux 공식 문서의 workspace group은 sidebar에서 workspace를 접고 펼치는 organization 기능입니다. 이름, icon, color, membership이 저장되지만 별도 filesystem namespace나 credential boundary를 제공한다고 보아서는 안 됩니다.

예를 들어 `company` group과 `personal` group을 나누어도 같은 macOS user로 실행한 process는 해당 user가 가진 파일과 credential에 접근할 수 있습니다. 다음 통제는 별도로 적용해야 합니다.

- 회사와 개인 credential의 profile, keychain item, environment variable 분리
- production 접근은 read-only profile을 기본값으로 사용
- mutation 전 account, cluster context, target repository 확인
- 민감 작업은 container, VM, sandbox 또는 별도 OS account로 실행
- agent가 읽을 필요가 없는 secret은 environment와 working directory에서 제거

group은 실수를 줄이는 시각적 guardrail로는 유용하지만, 공격이나 권한 오용을 막는 security control은 아닙니다.

---

## 6. Session restore와 process lifetime을 정확히 이해하기

cmux는 relaunch 시 window, workspace, pane layout, working directory, best-effort terminal scrollback, browser state를 복원합니다. 지원되는 coding agent는 hook이 native session ID를 기록한 경우 해당 agent의 resume command로 session을 다시 열 수 있습니다.

여기서 `resume`이라는 단어를 process checkpoint로 해석하면 안 됩니다.

```text
Before cmux closes
  agent process + child processes + terminal state

After cmux relaunch
  restored layout + new terminal process
  + optional native agent resume command
```

임의의 shell, vim, tmux, 기타 TUI process가 실행 중이던 instruction과 memory state를 cmux가 저장하는 것은 아닙니다. terminal scrollback도 best-effort이므로 source of truth로 사용하지 않습니다. 중요한 결정, command, test result는 repository 문서나 task note에 남겨야 합니다.

지원 agent의 resume도 recovery path입니다. 대화 history와 agent context를 다시 열 수는 있지만, 종료 순간 실행 중이던 build process, network connection, foreground command가 이어서 실행된다고 가정해서는 안 됩니다. 복구 후에는 다음 순서로 상태를 재확인합니다.

```shell
pwd
git branch --show-current
git status --short
git diff --check
```

이후 task note와 test result를 확인하고 필요한 command를 새로 실행합니다.

### 6.1. 언제 tmux를 사용하는가

| 상황 | tmux | 이유 |
| :--- | :---: | :--- |
| 10분 이상 실행되는 interactive test watcher를 cmux 종료 후에도 유지 | 사용 | app close와 process lifetime 분리 필요 |
| foreground dev server를 유지한 채 cmux를 재시작 | 사용 | tmux server가 process를 계속 관리 |
| Claude Code native subagent | 미사용 | parent agent lifecycle에서 관리 |
| Codex one-shot review | 미사용 | 결과 반환 후 종료가 정상 |
| 짧은 build 또는 lint | 미사용 | 재실행 비용이 낮음 |
| reboot 이후 local process 유지 | 해결 불가 | local tmux server도 reboot 시 종료 |

필요한 경우에만 이름이 있는 session을 만듭니다.

```shell
tmux new -As api-auth-test-watch
tmux ls
tmux attach -t api-auth-test-watch
```

cmux를 닫기 전 tmux client를 detach하면 tmux server 내부 process는 계속 실행됩니다. 그러나 MacBook reboot 뒤에는 `tmux attach`로 기존 local session에 돌아갈 수 없습니다. 이 경우 repository state와 task note, agent native resume을 이용해 작업을 재구성합니다.

---

## 7. Notification과 privacy boundary

attention cockpit은 알림이 정확할 때만 생산성을 높입니다. 동시에 notification title과 body는 lock screen, Notification Center, screen sharing 화면에 노출될 수 있으므로 secret과 고객 정보를 담지 않아야 합니다.

### 7.1. 알림 정책

| Event | Desktop notification | Sidebar unread | 권장 message |
| :--- | :---: | :---: | :--- |
| 승인 필요 | Yes | Yes | `Approval required` |
| 사용자 입력 필요 | Yes | Yes | `Input required` |
| 실패 또는 blocked | Yes | Yes | `Task blocked` |
| 최종 완료 | 선택 | Yes | `Task completed` |
| 개별 tool 완료 | No | No | 알림 없음 |
| 일반 progress | No | 선택 | 상태 이름만 갱신 |

cmux는 focused window, active workspace, notification panel이 열린 경우 desktop alert를 억제합니다. 이 기본 behavior에만 의존하지 않고 macOS Focus mode와 notification preview도 함께 조정합니다.

### 7.2. 알림에 넣지 않을 정보

- prompt 원문
- source code와 diff
- customer name, incident detail, internal hostname
- access token, credential path, secret value
- production resource identifier 전체
- agent가 읽은 file content

알림에는 `task ID`, `agent`, `action required` 정도만 넣고, 상세 내용은 해당 workspace를 열어 확인합니다. 예시는 다음과 같습니다.

```text
Title: fix-142-codex
Body: Approval required
```

### 7.3. 실행 권한 경계

notification hook과 automation command는 shell command를 실행할 수 있으므로 code와 동일하게 검토합니다. project-local configuration을 신뢰하기 전에 repository owner와 변경 diff를 확인하고, 외부 입력을 command string에 직접 연결하지 않습니다. remote control이나 socket API를 활성화하는 도구는 접근 범위와 credential policy를 최소화합니다.

Ghostty fallback에는 필요한 경우 macOS Secure Keyboard Entry를 사용합니다. 다만 secure input은 key event 보호 기능이지 agent가 이미 접근할 수 있는 file, environment variable, terminal output을 격리하는 기능은 아닙니다.

---

## 8. 1주 practical pilot

처음부터 모든 workflow를 이전하지 않고 1주 동안 실제 task로 검증합니다. pilot의 목적은 cmux 사용 시간을 늘리는 것이 아니라 task discovery time과 missed attention, writer collision을 줄이는지 측정하는 것입니다.

### 8.1. Day 1: Baseline 수집

- 기존 Ghostty 중심 방식으로 3개 이상 병렬 task를 수행합니다.
- task 위치를 찾는 데 걸린 시간을 10회 측정합니다.
- 승인 또는 입력 대기 상태를 5분 넘게 놓친 횟수를 기록합니다.
- 잘못된 repository, branch, worktree에서 command를 실행한 횟수를 기록합니다.

### 8.2. Day 2: 최소 구조 적용

- cmux에 project별 workspace group을 만듭니다.
- task별 workspace와 worktree를 1:1로 연결합니다.
- workspace name에 task, agent, state를 표시합니다.
- Ghostty는 fallback window 하나만 유지합니다.

### 8.3. Day 3: Single-writer 검증

- 두 개 이상의 agent를 동시에 사용하되 task별 primary writer를 한 명으로 제한합니다.
- reviewer는 read-only prompt와 diff review만 수행합니다.
- file ownership 충돌과 예상치 못한 diff가 발생했는지 기록합니다.

### 8.4. Day 4: Attention tuning

- approval, input required, blocked, completed만 알림 대상으로 설정합니다.
- notification body에서 민감한 text를 제거합니다.
- 불필요한 notification 수와 놓친 notification 수를 각각 기록합니다.

### 8.5. Day 5: Failure drill

- 작업 state를 기록한 뒤 cmux를 정상 종료하고 다시 실행합니다.
- layout, working directory, scrollback, agent resume 결과를 구분해 확인합니다.
- native resume 이후 `pwd`, branch, status, diff를 재검증합니다.
- 임의의 live process가 복원되지 않는다는 전제로 recovery runbook을 점검합니다.

### 8.6. Day 6: tmux 경계 검증

- 장기 interactive process 하나만 tmux에서 실행합니다.
- tmux client를 detach한 뒤 cmux를 종료하고 process 생존을 확인합니다.
- 일반 agent task와 one-shot worker에는 tmux를 사용하지 않습니다.
- 중첩 shortcut과 navigation overhead를 기록합니다.

### 8.7. Day 7: 결과 평가

pilot 전후 지표를 비교하고 다음 기준으로 채택 여부를 결정합니다.

| 지표 | 성공 기준 | 실패 신호 |
| :--- | :--- | :--- |
| Task discovery time | median 10초 이하 | baseline 대비 개선 없음 |
| Missed attention | 5분 초과 대기 1회 이하 | 알림이 있어도 반복적으로 놓침 |
| Wrong-context command | 0회 | 다른 repository나 branch에서 실행 |
| Writer collision | 0회 | 같은 file에 동시 mutation 발생 |
| Notification precision | action이 필요한 알림 80% 이상 | progress 알림이 대부분을 차지 |
| Recovery clarity | 5분 안에 task state 재구성 | live process 복원 여부를 판단하지 못함 |
| tmux selectivity | 장기 process에만 사용 | 모든 agent에 관성적으로 적용 |

다음 중 하나라도 발생하면 pilot을 실패로 보고 구성을 축소하거나 대안을 재검토합니다.

- wrong-context command가 한 번이라도 발생했는데 naming과 preflight로 방지되지 않습니다.
- notification에 secret 또는 민감 정보가 노출됩니다.
- cmux와 tmux의 중첩이 task navigation을 더 느리게 만듭니다.
- session restore를 live process persistence로 오해해 작업 손실이 발생합니다.
- 1주 후에도 workspace state를 수동으로 유지하는 비용이 이득보다 큽니다.

실패 시 rollback은 단순합니다. agent CLI와 repository는 그대로 두고 primary terminal을 Ghostty로 되돌립니다. tmux는 실제 장기 process session만 유지하며, cmux 전용 workspace와 notification 설정은 비활성화합니다.

---

## 9. Daily operation cheat sheet

### 9.1. 작업 시작

```text
1. task 전용 worktree와 branch 확인
2. cmux workspace 생성 및 이름 지정
3. pwd, branch, status 확인
4. primary writer 한 명 지정
5. agent 실행
```

### 9.2. 병렬 worker 추가

```text
1. 결과만 필요한 one-shot인지 확인
2. write가 필요하면 file ownership 분리
3. ownership이 겹치면 별도 worktree 사용
4. native subagent에는 tmux를 추가하지 않음
```

### 9.3. 장기 process 시작

```shell
# cmux 종료 후에도 살아 있어야 할 때만 사용
tmux new -As <project>-<task>-<process>

# detach: Ctrl-b d
tmux ls
```

### 9.4. 작업 복구

```text
1. cmux layout restore와 process restore를 구분
2. 지원 agent는 native session resume 확인
3. pwd, branch, status, diff 재확인
4. task note에서 마지막 검증 결과 확인
5. 종료된 command는 안전성을 검토한 뒤 재실행
```

### 9.5. 작업 종료

```text
1. test, lint, build 결과 기록
2. git diff와 status 확인
3. workspace state를 done 또는 blocked로 갱신
4. 불필요한 tmux session 종료
5. 민감한 notification과 scrollback 정리
```

---

## 10. 마치며

여러 AI 코딩 에이전트를 생산적으로 쓰기 위해 필요한 것은 더 많은 terminal pane이 아니라 명확한 task identity, attention routing, write ownership, recovery boundary입니다.

이번 MacBook local design에서는 cmux를 primary workspace와 attention cockpit으로 선택했습니다. Ghostty는 신뢰할 수 있는 fallback terminal로 남기고, tmux는 cmux 종료 후에도 유지해야 하는 장기 interactive process에만 사용합니다. native subagent와 one-shot worker에는 tmux를 요구하지 않습니다.

가장 중요한 운영 원칙은 복원 기능을 과대평가하지 않는 것입니다. cmux는 layout과 metadata를 되살리고, 지원되는 agent는 native session을 resume할 수 있습니다. 그러나 임의의 live process를 checkpoint하지 않습니다. tmux도 local server가 살아 있는 동안만 process를 유지하며 MacBook reboot를 넘지 못합니다. agent resume은 context recovery이고 live execution checkpoint가 아닙니다.

마지막으로 workspace group, 이름, 색상은 실수를 줄이는 organization layer입니다. 보안 경계는 아닙니다. DevSecOps 관점의 Agentic Development Environment는 보기 좋은 cockpit에서 끝나지 않고, 최소 권한, secret 분리, single-writer rule, 검증 가능한 recovery runbook까지 포함할 때 비로소 운영 가능한 환경이 됩니다.

---

## 11. References

- [Ghostty Docs - About Ghostty](https://ghostty.org/docs/about)
- [Ghostty Docs - macOS Secure Input](https://ghostty.org/docs/config/reference#macos-auto-secure-input)
- [cmux Docs - Getting Started](https://cmux.com/docs/getting-started)
- [cmux Docs - Concepts](https://cmux.com/docs/concepts)
- [cmux Docs - Workspace Groups](https://cmux.com/docs/workspace-groups)
- [cmux Docs - Session Restore](https://cmux.com/docs/session-restore)
- [cmux Docs - Notifications](https://cmux.com/docs/notifications)
- [tmux Wiki - Getting Started](https://github.com/tmux/tmux/wiki/Getting-Started)
- [tmux Wiki - FAQ](https://github.com/tmux/tmux/wiki/FAQ)
- [Zellij User Guide - Session Resurrection](https://zellij.dev/documentation/session-resurrection.html)
- [WezTerm Docs - Multiplexing](https://wezterm.org/multiplexing.html)
- [WezTerm Docs - Bell Event](https://wezterm.org/config/lua/window-events/bell.html)
- [kitty Docs - Remote Control](https://sw.kovidgoyal.net/kitty/remote-control/)
- [kitty Docs - Desktop Notifications](https://sw.kovidgoyal.net/kitty/kittens/notify/)

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
