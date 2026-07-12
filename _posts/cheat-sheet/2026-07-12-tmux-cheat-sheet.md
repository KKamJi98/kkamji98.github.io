---
title: tmux Command Cheat Sheet
date: 2026-07-12 02:30:00 +0900
author: kkamji
categories: [System, Linux]
tags: [tmux, terminal, shell, zsh, macos, linux, devops, cli, cheat-sheet] # TAG names should always be lowercase
comments: true
image:
  path: /assets/img/kkam-img/kkam.webp
---

`tmux`는 하나의 터미널에서 여러 터미널을 만들고, 실행 중인 프로그램을 화면에서 분리했다가 다시 연결할 수 있게 하는 터미널 멀티플렉서입니다. 이 글에서는 macOS와 Linux에서 장시간 실행되는 대화형 AI 코딩 에이전트를 안전하게 다루는 데 필요한 명령과 기본 단축키를 정리합니다.

---

## 1. 핵심 개념

tmux는 다음 계층으로 동작합니다.

| 구성 요소 | 역할 |
|---|---|
| Server | 세션, 창, 패널과 그 안의 프로세스를 관리하는 백그라운드 프로세스 |
| Client | 현재 터미널을 특정 세션에 연결하는 화면 |
| Session | 하나 이상의 창을 묶는 작업 단위 |
| Window | 세션 안의 전체 화면 단위이며 하나 이상의 패널을 포함 |
| Pane | 셸이나 대화형 프로그램이 실행되는 개별 pseudo-terminal(PTY) |

`detach`는 client만 session에서 분리합니다. session과 pane 안의 프로세스는 tmux server가 살아 있는 동안 계속 실행되며, 나중에 다시 `attach`할 수 있습니다. 반면 `kill-session`, 호스트 재부팅, tmux server 종료는 같은 의미가 아닙니다. tmux는 프로세스 체크포인트나 재부팅 복구 도구가 아니므로 중요한 상태는 애플리케이션 자체 파일이나 로그에도 남겨야 합니다.

tmux는 Claude Code, Codex, Hermes 같은 대화형 프로그램에 지속적인 PTY를 제공할 뿐입니다. 작업을 분해하거나 subagent를 생성하고, 권한을 통제하거나, 여러 에이전트의 파일 수정을 조정하는 관리자는 아닙니다. 이러한 책임은 각 에이전트 도구와 사용자의 작업 절차에 남습니다.

---

## 2. 설치 및 확인

### 2.1. 설치 여부와 버전 확인

```shell
command -v tmux
tmux -V
man 1 tmux
```

`command -v tmux`가 경로를 출력하지 않으면 운영체제의 패키지 관리자로 설치합니다.

### 2.2. macOS

```shell
brew install tmux
```

### 2.3. Debian/Ubuntu

```shell
sudo apt update
sudo apt install tmux
```

### 2.4. Fedora

```shell
sudo dnf install tmux
```

배포판 저장소의 버전은 최신 tmux 릴리스보다 오래될 수 있습니다. 사용 가능한 기능은 `tmux -V`, `man 1 tmux`, `tmux list-commands`로 현재 설치본을 기준으로 확인하는 것이 안전합니다.

---

## 3. Session 생명주기

```shell
# 이름을 지정하여 session 생성 후 바로 attach
tmux new-session -s ai-work

# 현재 디렉터리에서 detached session 생성
tmux new-session -d -s ai-work -c "$PWD"

# 같은 이름이 있으면 attach하고, 없으면 생성
tmux new-session -A -s ai-work

# session 목록 확인
tmux list-sessions
tmux ls

# 지정한 session에 attach
tmux attach-session -t ai-work
tmux attach -t ai-work

# 현재 client를 session에서 detach
tmux detach-client

# 특정 session에 연결된 모든 client를 detach
tmux detach-client -s ai-work

# session 이름 변경
tmux rename-session -t ai-work incident-review

# 지정한 session 종료
tmux kill-session -t incident-review
```

tmux 내부에서는 기본 prefix인 `Ctrl-b`를 누른 뒤 `d`를 눌러 detach하는 방법이 가장 간단합니다. `Ctrl-b d`는 동시에 누르는 chord가 아니라 `Ctrl-b`를 놓고 `d`를 누르는 순차 입력입니다.

`tmux attach-session -d -t ai-work`는 다른 client를 먼저 detach하고 현재 터미널을 연결합니다. 다른 터미널에서 같은 session을 보고 있을 수 있으므로 의도적으로 화면을 가져와야 할 때만 `-d`를 사용합니다.

---

## 4. Window와 Pane 관리

### 4.1. 명령어

```shell
# window 생성, 목록, 이름 변경, 종료
tmux new-window -t ai-work: -n logs -c "$PWD"
tmux list-windows -t ai-work
tmux rename-window -t ai-work:1 agent
tmux kill-window -t ai-work:1

# 현재 pane을 좌우로 분할
tmux split-window -h

# 현재 pane을 위아래로 분할
tmux split-window -v

# 모든 pane과 현재 명령 확인
tmux list-panes -a -F '#{session_name}:#{window_index}.#{pane_index} pid=#{pane_pid} cmd=#{pane_current_command}'

# 지정한 pane 선택, 확대 전환, 종료
tmux select-pane -t ai-work:0.1
tmux resize-pane -Z -t ai-work:0.1
tmux kill-pane -t ai-work:0.1
```

대상은 일반적으로 `session:window.pane` 형식으로 지정합니다. 스크립트나 삭제 명령에서는 `ai-work:0.1`처럼 가능한 한 완전한 대상을 사용해야 이름과 인덱스의 모호성을 줄일 수 있습니다.

### 4.2. 필수 기본 단축키

아래 표의 키는 먼저 `Ctrl-b`를 누른 뒤 입력합니다.

| 키 | 동작 |
|---|---|
| `c` | 새 window 생성 |
| `,` | 현재 window 이름 변경 |
| `&` | 현재 window 종료 확인 |
| `n` / `p` | 다음 / 이전 window로 이동 |
| `0`부터 `9` | 해당 인덱스의 window 선택 |
| `w` | session과 window를 트리에서 선택 |
| `"` | pane을 위아래로 분할 |
| `%` | pane을 좌우로 분할 |
| 방향키 | 인접 pane 선택 |
| `o` | 다음 pane 선택 |
| `q` | pane 인덱스 표시 |
| `z` | 현재 pane 확대 상태 전환 |
| `x` | 현재 pane 종료 확인 |
| `Space` | 미리 정의된 pane layout 순환 |
| `d` | 현재 client detach |
| `s` | session을 대화형으로 선택 |
| `[` | copy-mode 진입 |
| `]` | 최근 tmux paste buffer 붙여넣기 |
| `:` | tmux command prompt 열기 |
| `?` | 현재 key binding 목록 보기 |

애플리케이션에 prefix 자체를 보내야 하거나 중첩된 tmux의 안쪽 server에 명령하려면 `Ctrl-b Ctrl-b`를 사용합니다.

---

## 5. Copy-mode와 검색

`Ctrl-b [`로 copy-mode에 들어가면 현재 화면뿐 아니라 pane history를 탐색할 수 있습니다. 기본 키 표는 `mode-keys` 옵션에 따라 emacs 또는 vi 방식으로 달라집니다.

```shell
# 현재 설정과 실제 key binding 확인
tmux show-options -gw mode-keys
tmux list-keys -T copy-mode
tmux list-keys -T copy-mode-vi

# tmux paste buffer 확인과 출력
tmux list-buffers
tmux show-buffer
```

| 작업 | emacs key table | vi key table |
|---|---|---|
| 앞으로 검색 | `Ctrl-s` | `/` |
| 뒤로 검색 | `Ctrl-r` | `?` |
| 같은 방향으로 다시 검색 | `n` | `n` |
| 반대 방향으로 다시 검색 | `N` | `N` |
| 선택 시작 | `Ctrl-Space` | `Space` |
| 선택 복사 후 종료 | `Alt-w` | `Enter` |
| copy-mode 종료 | `q` | `q` |

복사한 내용은 tmux paste buffer에 들어가며, `Ctrl-b ]`로 pane에 붙여넣을 수 있습니다. 운영체제 clipboard 연동 여부는 tmux 옵션과 터미널 지원에 따라 달라지므로 tmux buffer 복사를 곧바로 시스템 clipboard 복사로 가정하면 안 됩니다.

pane history는 무제한 감사 로그가 아닙니다. 현재 제한은 다음 명령으로 확인할 수 있으며, 장기 보존이 필요하면 에이전트 자체 기록이나 별도 로그를 사용합니다.

```shell
tmux show-options -gv history-limit
```

---

## 6. zsh 함수와 별칭

이 글의 명령은 모두 `tm`으로 시작하도록 통일합니다. 아래를 `~/.zshrc` 또는 `~/.zsh_functions`처럼 zsh가 source하는 파일에 추가합니다. session 이름은 task ID로 사용하고, 기존 session에 잘못 연결하거나 같은 task에 writer를 중복으로 만들지 않도록 생성·attach 경로를 분리합니다.

```zsh
__tmux_task_id_valid() {
  [[ -n "$1" && "$1" =~ '^[A-Za-z0-9][A-Za-z0-9._-]*$' ]]
}

# 생성 또는 기존 task session에 재접속
tm() {
  local task="$1"
  __tmux_task_id_valid "$task" || { print -u2 -- 'Usage: tm <task-id>'; return 2; }
  tmux new-session -A -s "$task" -c "$PWD"
}

# 고정 열 task dashboard: tmux의 prose list보다 빠르게 훑을 수 있습니다.
tml() {
  local rows
  rows="$(tmux list-sessions -F $'#{session_name}\t#{session_windows}\t#{?session_attached,attached,detached}\t#{session_path}' 2>/dev/null)" \
    || { print -u2 -- 'No tmux sessions.'; return 1; }
  [[ -n "$rows" ]] || { print -u2 -- 'No tmux sessions.'; return 0; }
  {
    print -r -- $'SESSION\tWINDOWS\tSTATUS\tPATH'
    print -r -- "$rows"
  } | column -t -s $'\t'
}

# 새 session만 생성: 기존 이름이면 중복 writer 방지를 위해 거부
tmn() {
  local task="$1"
  __tmux_task_id_valid "$task" || { print -u2 -- 'Usage: tmn <task-id>'; return 2; }
  tmux has-session -t "$task" 2>/dev/null && { print -u2 -- "Session already exists: $task"; return 1; }
  tmux new-session -s "$task" -c "$PWD"
}

# 기존 session에만 attach: 빈 session을 암묵적으로 만들지 않음
tma() {
  local task="$1"
  [[ -n "$task" ]] || { print -u2 -- 'Usage: tma <task-id>'; return 2; }
  tmux has-session -t "$task" 2>/dev/null || { print -u2 -- "Session not found: $task"; return 1; }
  tmux attach-session -t "$task"
}

# detached 장기 worker 시작. 한 task에는 한 writer만 둠
tmw() {
  local task="$1"
  shift || true
  __tmux_task_id_valid "$task" && (( $# > 0 )) || { print -u2 -- 'Usage: tmw <task-id> <command...>'; return 2; }
  tmux has-session -t "$task" 2>/dev/null && { print -u2 -- "Session already exists: $task"; return 1; }
  tmux new-session -d -s "$task" -c "$PWD" "$@"
}

# 확인 후 session 종료
tmk() {
  local task="$1" reply
  tmux has-session -t "$task" 2>/dev/null || { print -u2 -- "Session not found: $task"; return 1; }
  printf "Kill tmux session '%s'? [y/N] " "$task"
  read -r reply
  [[ "$reply" == [yY] ]] || { print -- 'Canceled.'; return 1; }
  tmux kill-session -t "$task"
}

# fzf로 session을 고르는 fuzzy switcher: tmux 안에서는 switch, 밖에서는 attach
tms() {
  local rows pick
  rows="$(tmux list-sessions -F '#{session_name}' 2>/dev/null)"
  [[ -n "$rows" ]] || { print -u2 -- 'No tmux sessions.'; return 1; }
  pick="$(print -r -- "$rows" | fzf --height=40% --reverse --prompt='tmux session> ')" || return 1
  [[ -n "$pick" ]] || return 1
  if [[ -n "$TMUX" ]]; then
    tmux switch-client -t "$pick"
  else
    tmux attach-session -t "$pick"
  fi
}

# 현재 session 또는 지정한 session의 이름 변경. task ID 규칙을 그대로 검증
tmrn() {
  local old new
  if (( $# == 2 )); then old="$1"; new="$2"; else new="$1"; fi
  __tmux_task_id_valid "$new" || { print -u2 -- 'Usage: tmrn [old-name] <new-name>'; return 2; }
  if [[ -n "$old" ]]; then
    tmux rename-session -t "$old" "$new"
  else
    tmux rename-session "$new"
  fi
}

# 짧은 읽기/설정 alias
alias tls='tml'
alias tmr='tmux source-file ~/.tmux.conf'
```

```shell
# 설정 다시 읽기
source ~/.zshrc

# 사용 예시
tm hermes-review
tml
tma hermes-review
tms
tmrn hermes-review incident-review
tmw docs-build npm run build
tmk incident-review
```

`tm`은 기존 session이 있으면 그 session에 attach합니다. 현재 디렉터리에서 반드시 새 session을 시작해야 할 때는 `tmn`을 사용합니다. `tmw`는 긴 build, test watcher, interactive worker처럼 terminal app 종료 뒤에도 계속 살아야 하는 process에만 사용하며, native subagent와 one-shot worker를 무조건 tmux로 감싸지는 않습니다.

`tms`는 [fzf](https://github.com/junegunn/fzf)가 설치되어 있어야 하며, session이 늘어나 이름을 정확히 기억하기 어려울 때 유용합니다. tmux 내부에서 실행하면 `attach` 대신 `switch-client`를 사용하므로 중첩 attach 오류 없이 session을 전환할 수 있습니다. `tmrn`은 인자 하나면 현재 session의 이름을, 인자 둘이면 지정한 session의 이름을 변경하며, 생성 함수와 같은 task ID 규칙을 검증합니다.

---

## 7. 상태 확인과 점검 명령

```shell
# server가 관리하는 session, client, window, pane 확인
tmux list-sessions
tmux list-clients
tmux list-windows -a
tmux list-panes -a

# 읽기 쉬운 format으로 session 확인
tmux list-sessions -F '#{session_name} attached=#{session_attached} windows=#{session_windows}'

# 모든 window의 이름과 활성 상태 확인
tmux list-windows -a -F '#{session_name}:#{window_index} #{window_name} active=#{window_active} panes=#{window_panes}'

# 현재 위치와 실행 중인 명령 확인
tmux display-message -p '#S:#I.#P pid=#{pane_pid} cmd=#{pane_current_command}'

# 지원 명령과 실제 key binding 확인
tmux list-commands
tmux list-keys -T prefix

# global option과 server option 확인
tmux show-options -g
tmux show-options -s
```

`pane_current_command`는 pane의 현재 명령 이름을 보여주는 상태 정보입니다. 에이전트의 내부 작업 단계나 안전 상태를 증명하지 않으므로 종료 전에는 실제 화면과 애플리케이션 상태를 함께 확인해야 합니다.

---

## 8. 장시간 AI 코딩 세션 운영 예시

### 8.1. 시작

저장소마다 목적이 드러나는 session 이름을 사용하고, 작업 디렉터리를 명시해 detached 상태로 먼저 생성합니다.

```shell
cd ~/code/project
tmux new-session -d -s project-agent -c "$PWD"
tmux attach-session -t project-agent
```

한 window에는 하나의 주 작업 흐름을 두고, 빌드나 로그 확인은 별도 window 또는 pane으로 분리하면 문맥을 찾기 쉽습니다. 여러 에이전트가 같은 저장소를 동시에 수정할 때 tmux는 충돌을 방지하지 않습니다. 파일 소유권, branch 또는 worktree, 검증과 병합 순서는 별도로 정해야 합니다.

### 8.2. 자리를 비우기 전

1. 에이전트가 사용자 입력, 권한 승인, 충돌 해결을 기다리는지 확인합니다.
2. 저장소 상태와 다음 작업을 기록하고, 필요한 결과가 파일에 저장되었는지 확인합니다.
3. `Ctrl-b d`로 detach합니다.
4. 외부 셸에서 `tmux list-sessions`로 session이 남아 있는지 확인합니다.

detach는 현재 터미널 연결만 끊으므로 에이전트가 계속 명령을 실행할 수 있습니다. 승인 없이 계속 실행되면 안 되는 작업은 먼저 애플리케이션에서 안전하게 중단하거나 입력 대기 상태인지 확인합니다.

### 8.3. 다시 연결한 뒤

```shell
tmux attach-session -t project-agent
tmux display-message -p '#S:#I.#P pid=#{pane_pid} cmd=#{pane_current_command}'
```

화면 출력, prompt, 저장소 상태를 다시 확인한 뒤 입력을 이어갑니다. tmux가 PTY를 유지했다는 사실만으로 에이전트 요청이 성공했거나 저장소가 안전한 상태라고 판단하지 않습니다.

---

## 9. Compact Cheat Table

| 목적 | 명령 또는 키 |
|---|---|
| 생성 후 attach | `tmux new-session -s NAME` |
| 생성 또는 attach | `tmux new-session -A -s NAME` |
| 목록 | `tmux ls` |
| attach | `tmux attach -t NAME` |
| detach | `Ctrl-b d` |
| session 이름 변경 | `Ctrl-b $` |
| 새 window | `Ctrl-b c` |
| window 선택 | `Ctrl-b w` |
| 좌우 분할 | `Ctrl-b %` |
| 위아래 분할 | `Ctrl-b "` |
| pane 선택 | `Ctrl-b 방향키` |
| pane 확대 | `Ctrl-b z` |
| copy-mode | `Ctrl-b [` |
| buffer 붙여넣기 | `Ctrl-b ]` |
| session 종료 | `tmux kill-session -t NAME` |

---

## 10. 자주 발생하는 문제

### 10.1. `no server running` 메시지

실행 중인 session이 없으면 기본 설정에서 tmux server도 종료됩니다. `tmux new-session -s NAME`으로 새 session을 생성합니다.

### 10.2. 같은 이름의 session이 이미 존재함

`tmux new-session -s NAME`은 중복 이름에서 실패합니다. 기존 session을 재사용하려면 `tmux attach -t NAME` 또는 `tmux new-session -A -s NAME`을 사용합니다.

### 10.3. detach와 종료를 혼동함

`Ctrl-b d`는 프로세스를 유지하지만 `exit`, `Ctrl-d`, `kill-pane`, `kill-window`, `kill-session`은 범위에 따라 프로세스를 종료할 수 있습니다. 장시간 실행 작업을 보존하려면 detach를 사용합니다.

### 10.4. 재접속하면 새 환경 변수가 보이지 않음

이미 실행 중인 프로세스의 환경은 attach만으로 교체되지 않습니다. credential이나 환경 변수를 갱신했다면 기존 에이전트에 자동 반영된다고 가정하지 말고, 필요한 프로세스를 정상 종료한 뒤 새 pane에서 다시 시작합니다. 민감한 값은 명령행, pane 출력, tmux buffer에 남기지 않습니다.

### 10.5. 스크롤이 터미널처럼 동작하지 않음

`Ctrl-b [`로 copy-mode에 진입해 history를 탐색합니다. 실제 키 표는 `tmux show-options -gw mode-keys`와 `tmux list-keys -T copy-mode-vi` 또는 `tmux list-keys -T copy-mode`로 확인합니다.

### 10.6. 접속이 끊긴 뒤 session이 없음

tmux는 같은 호스트에서 tmux server가 계속 살아 있을 때만 재연결할 수 있습니다. 호스트 재부팅, server 강제 종료, 마지막 session 종료 뒤에는 기존 프로세스를 복구하지 못합니다.

---

## 11. 안전한 정리

먼저 대상과 실행 중인 명령을 확인합니다.

```shell
tmux list-sessions
tmux list-windows -a -F '#{session_name}:#{window_index} #{window_name} active=#{window_active}'
tmux list-panes -a -F '#{session_name}:#{window_index}.#{pane_index} pid=#{pane_pid} cmd=#{pane_current_command}'
```

종료할 에이전트가 작업 중이거나 입력을 기다리는지 확인하고, 애플리케이션이 제공하는 정상 종료 방법을 먼저 사용합니다. 이후 남은 범위에 맞는 tmux 명령을 실행합니다.

```shell
# pane 하나만 종료
tmux kill-pane -t project-agent:0.1

# window 하나만 종료
tmux kill-window -t project-agent:1

# session 하나만 종료
tmux kill-session -t project-agent

# 지정한 session을 제외한 나머지 session 종료
tmux kill-session -a -t keep-this
```

`tmux kill-session -a -t keep-this`와 `tmux kill-server`는 영향 범위가 큽니다. 특히 `tmux kill-server`는 해당 server의 모든 session과 client를 파괴하므로 일반적인 정리 명령으로 사용하지 않는 것이 안전합니다.

---

## 12. References

- [OpenBSD Manual Pages - tmux(1)](https://man.openbsd.org/tmux.1)
- [tmux Wiki - Getting Started](https://github.com/tmux/tmux/wiki/Getting-Started)
- [tmux Wiki - Installing](https://github.com/tmux/tmux/wiki/Installing)

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
