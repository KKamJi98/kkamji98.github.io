---
title: Git Command Cheat Sheet
date: 2025-04-12 01:22:42 +0900
author: kkamji
categories: [DevOps, Git]
tags: [git, version-control, devops, cli, github, gitlab, cheat-sheet]     # TAG names should always be lowercase
comments: true
image:
  path: /assets/img/github/github.webp
---

Git을 사용하며 알게된 CLI 명령어들을 공유합니다.

---

## 1. 사전 준비 (권장)

`git-delta`는 `git diff`, `git log`, `git show` 등의 출력을 더 읽기 쉽게 만들어주는 도구입니다.

### 1.1. Ubuntu/Debian

```shell
sudo apt-get update
sudo apt-get install git-delta
```

### 1.2. macOS (Homebrew)

```shell
brew install git-delta
```

### 1.3. 기타

다른 운영체제나 설치 방법은 [공식 문서](https://dandavison.github.io/delta/installation.html)를 참고하세요.

---

## 2. 기본 설정

```shell
# Git 초기 설정
git config --global user.name "Your Name"           # 사용자 이름 설정
git config --global user.email "your.email@example.com"  # 이메일 설정
git config --global init.defaultBranch main         # 기본 브랜치를 main으로 설정
git config --global core.editor "code --wait"       # 기본 에디터 설정 (VS Code)

# 설정 확인
git config --list                                   # 모든 설정 확인
git config --global --list                          # 글로벌 설정만 확인
git config user.name                                # 특정 설정 값 확인
git config --show-origin user.name                  # 설정 파일 위치와 함께 확인

# SSH 키 설정 (GitHub/GitLab)
ssh-keygen -t ed25519 -C "your.email@example.com"   # SSH 키 생성
eval "$(ssh-agent -s)"                              # SSH 에이전트 시작
ssh-add ~/.ssh/id_ed25519                           # SSH 키 추가
```

### 2.1. 현재 환경 기반 Git 전역 설정 명령

```shell
# 사용자
git config --global user.name "{USERNAME}"
git config --global user.email "{USER_EMAIL}"

# 브랜치

# 줄바꿈
git config --global core.autocrlf input      # Windows에서는 true 권장

# 성능
git config --global core.untrackedCache keep # 강제 true 대신 keep
git config --global core.fsmonitor true
git fsmonitor--daemon start

# delta
git config --global core.pager "delta"
git config --global interactive.diffFilter "delta --color-only"
git config --global delta.syntax-theme Dracula
git config --global delta.line-numbers true
git config --global delta.side-by-side true

# 안전 디렉토리
git config --global safe.directory "{PATH}"

# 자격증명 헬퍼(PATH 사용, 절대경로 지양)
git config --global credential.helper manager-core
git config --global credential.https://github.com.helper ''
git config --global credential.https://github.com.helper '!gh auth git-credential'
git config --global credential.https://gist.github.com.helper ''
git config --global credential.https://gist.github.com.helper '!gh auth git-credential'

# UI, 정렬, diff, push/fetch
git config --global column.ui auto
git config --global branch.sort -committerdate
git config --global tag.sort version:refname
git config --global diff.algorithm histogram
git config --global diff.colorMoved zebra
git config --global diff.mnemonicPrefix true
git config --global diff.renames true
git config --global push.default simple
git config --global push.autoSetupRemote true
git config --global push.followTags true
git config --global fetch.prune true
git config --global fetch.pruneTags true
git config --global help.autocorrect -1
git config --global commit.verbose true
git config --global rebase.autoSquash true
git config --global rebase.autoStash true
git config --global rebase.updateRefs true
git config --global merge.conflictstyle zdiff3
git config --global color.ui auto
git config --global color.diff auto
```

---

### 2.2. 글로벌 .gitignore 설정

`core.excludesFile` 을 설정하면 모든 Git 저장소에 공통 적용되는 `.gitignore` 를 유지할 수 있습니다. [git-scm 공식 문서의 gitignore 섹션](https://git-scm.com/docs/gitignore#_external_ignores)에서 권장하는 방법으로, 홈 디렉터리에 별도 파일을 두는 구성이 가장 단순합니다.

- Linux/macOS: `~/.gitignore_global`
- Windows: `%USERPROFILE%\.gitignore_global`

```shell
# 글로벌 .gitignore 파일 생성
touch ~/.gitignore_global

# Git 전역 설정에 등록
git config --global core.excludesFile '~/.gitignore_global'

# 설정 확인
git config --global --get core.excludesFile
```

```powershell
# Windows PowerShell 예시
New-Item -ItemType File -Force "$env:USERPROFILE\.gitignore_global" | Out-Null
git config --global core.excludesFile "$env:USERPROFILE\.gitignore_global"
git config --global --get core.excludesFile
```

Git 은 경로 문자열의 `~` 를 홈 디렉터리로 해석하므로 단일 인용부호를 사용해도 문제 없습니다. 필요하면 `~/.config/git/ignore` 와 같이 다른 경로를 지정해도 무방합니다. 글로벌 `.gitignore` 파일에는 OS 캐시, IDE 설정 파일 등 저장소와 무관한 항목을 두고, 저장소별 `.gitignore` 에는 프로젝트 특화 규칙만 유지하는 것을 권장합니다.

---

## 3. 유용한 별칭 설정

```shell
# 자주 사용하는 별칭 설정
git config --global alias.st status
git config --global alias.co checkout
git config --global alias.br branch
git config --global alias.ci commit
git config --global alias.unstage 'reset HEAD --'
git config --global alias.last 'log -1 HEAD'
git config --global alias.visual '!gitk'
git config --global alias.cmp '!f() { git add -A && git commit -m "$@" && git push; }; f'
git config --global alias.lg "log --graph --pretty=format:'%C(yellow)%h%Creset %C(blue)%ad%Creset %C(green)%an%Creset %s%C(red)%d%Creset' --date=short"

# 사용 예시
git st                                              # git status
git co main                                         # git checkout main
git lg                                              # 예쁜 로그 출력
```

---

## 4. 저장소 초기화 및 복제

```shell
# 저장소 생성 및 복제
git init                                            # 현재 디렉토리를 Git 저장소로 초기화
git init my-project                                 # 새 디렉토리에 Git 저장소 생성
git clone https://github.com/user/repo.git         # 원격 저장소 복제
git clone https://github.com/user/repo.git my-folder  # 특정 폴더명으로 복제
git clone --depth 1 https://github.com/user/repo.git  # 최신 커밋만 복제 (shallow clone)
git clone -b develop https://github.com/user/repo.git  # 특정 브랜치 복제

# 원격 저장소 관리
git remote -v                                       # 원격 저장소 목록 확인
git remote add origin https://github.com/user/repo.git  # 원격 저장소 추가
git remote set-url origin https://github.com/user/new-repo.git  # 원격 저장소 URL 변경
git remote remove origin                            # 원격 저장소 제거
git remote rename origin upstream                   # 원격 저장소 이름 변경
```

---

## 5. 기본 작업 흐름

```shell
# 파일 상태 확인
git status                                          # 작업 디렉토리 상태 확인
git status -s                                       # 간단한 형태로 상태 확인
git status --porcelain                              # 스크립트에서 사용하기 좋은 형태

# 파일 추가 및 커밋
git add file.txt                                    # 특정 파일 스테이징
git add .                                           # 모든 변경사항 스테이징
git add -A                                          # 모든 변경사항 스테이징 (삭제 포함)
git add -u                                          # 수정된 파일만 스테이징
git add -p                                          # 대화형으로 부분 스테이징

git commit -m "commit message"                      # 커밋 생성
git commit -am "commit message"                     # 스테이징과 커밋을 한번에
git commit --amend                                  # 마지막 커밋 수정
git commit --amend -m "new message"                 # 마지막 커밋 메시지만 수정
git commit --amend --no-edit                        # 커밋 메시지 변경 없이 파일만 추가

# 변경사항 확인
git diff                                            # 작업 디렉토리와 스테이징 영역 비교
git diff --staged                                   # 스테이징 영역과 마지막 커밋 비교
git diff --cached                                   # --staged와 동일
git diff HEAD                                       # 작업 디렉토리와 마지막 커밋 비교
git diff HEAD~1                                     # 이전 커밋과 비교
git diff branch1..branch2                           # 두 브랜치 비교
```

---

## 6. 브랜치 관리

```shell
# 브랜치 생성 및 전환
git branch                                          # 로컬 브랜치 목록
git branch -a                                       # 모든 브랜치 목록 (원격 포함)
git branch -r                                       # 원격 브랜치 목록
git branch feature-branch                           # 새 브랜치 생성
git checkout feature-branch                         # 브랜치 전환
git checkout -b feature-branch                      # 브랜치 생성과 전환을 한번에
git switch feature-branch                           # 브랜치 전환 (Git 2.23+)
git switch -c feature-branch                        # 브랜치 생성과 전환 (Git 2.23+)

# 브랜치 삭제
git branch -d feature-branch                        # 브랜치 삭제 (병합된 경우만)
git branch -D feature-branch                        # 브랜치 강제 삭제
git push origin --delete feature-branch             # 원격 브랜치 삭제

# 브랜치 정보
git branch -v                                       # 브랜치와 마지막 커밋 정보
git branch --merged                                 # 현재 브랜치에 병합된 브랜치들
git branch --no-merged                              # 병합되지 않은 브랜치들
git branch --contains <commit>                      # 특정 커밋을 포함하는 브랜치들
```

---

## 7. 병합과 리베이스

```shell
# 병합 (Merge)
git merge feature-branch                            # feature-branch를 현재 브랜치에 병합
git merge --no-ff feature-branch                    # Fast-forward 없이 병합
git merge --squash feature-branch                   # 커밋들을 하나로 합쳐서 병합
git merge --abort                                   # 병합 중단

# 리베이스 (Rebase)
git rebase main                                     # 현재 브랜치를 main 위로 리베이스
git rebase -i HEAD~3                                # 최근 3개 커밋을 대화형으로 리베이스
git rebase --continue                               # 리베이스 계속 진행
git rebase --abort                                  # 리베이스 중단
git rebase --skip                                   # 현재 커밋 건너뛰기

# 충돌 해결
git status                                          # 충돌 파일 확인
git add <resolved-file>                             # 충돌 해결 후 파일 추가
git commit                                          # 병합 커밋 생성
git mergetool                                       # 병합 도구 실행
```

---

## 8. 원격 저장소 작업

```shell
# 가져오기와 푸시
git fetch                                           # 원격 저장소에서 변경사항 가져오기
git fetch origin                                    # 특정 원격 저장소에서 가져오기
git pull                                            # fetch + merge
git pull --rebase                                   # fetch + rebase
git pull origin main                                # 특정 브랜치에서 pull

git push                                            # 현재 브랜치를 원격으로 푸시
git push origin main                                # 특정 브랜치 푸시
git push -u origin feature-branch                   # 새 브랜치 푸시 및 업스트림 설정
git push --force                                    # 강제 푸시 (위험!)
git push --force-with-lease                         # 안전한 강제 푸시

# 업스트림 설정
git branch --set-upstream-to=origin/main main       # 업스트림 브랜치 설정
git push -u origin main                             # 푸시와 동시에 업스트림 설정
```

---

## 9. 히스토리 조회

```shell
# 로그 확인
git log                                             # 커밋 히스토리 확인
git log --oneline                                   # 한 줄로 간단히 표시
git log --graph                                     # 그래프 형태로 표시
git log --graph --oneline --all                     # 모든 브랜치의 그래프
git log -p                                          # 각 커밋의 변경사항 표시
git log --stat                                      # 파일별 변경 통계
git log -n 5                                        # 최근 5개 커밋만 표시

# 특정 조건으로 로그 필터링
git log --author="John Doe"                         # 특정 작성자의 커밋
git log --since="2023-01-01"                        # 특정 날짜 이후 커밋
git log --until="2023-12-31"                        # 특정 날짜 이전 커밋
git log --grep="fix"                                # 커밋 메시지에 "fix" 포함
git log --all --grep="bug" --author="John"          # 복합 조건

# 파일별 히스토리
git log -- file.txt                                # 특정 파일의 히스토리
git log -p -- file.txt                             # 특정 파일의 변경사항 히스토리
git blame file.txt                                 # 파일의 각 줄 작성자 확인
git show HEAD:file.txt                             # 특정 커밋의 파일 내용 확인
```

---

## 10. 변경사항 되돌리기

```shell
# 작업 디렉토리 변경사항 되돌리기
git checkout -- file.txt                           # 특정 파일의 변경사항 되돌리기
git checkout .                                      # 모든 변경사항 되돌리기
git restore file.txt                                # 파일 복원 (Git 2.23+)
git restore .                                       # 모든 파일 복원

# 스테이징 취소
git reset HEAD file.txt                             # 특정 파일 스테이징 취소
git reset HEAD                                      # 모든 스테이징 취소
git restore --staged file.txt                      # 스테이징 취소 (Git 2.23+)

# 커밋 되돌리기
git reset --soft HEAD~1                            # 마지막 커밋 취소 (변경사항 유지)
git reset --mixed HEAD~1                           # 마지막 커밋과 스테이징 취소
git reset --hard HEAD~1                            # 마지막 커밋과 모든 변경사항 삭제
git revert HEAD                                     # 마지막 커밋을 되돌리는 새 커밋 생성
git revert <commit-hash>                            # 특정 커밋을 되돌리는 새 커밋 생성
```

---

## 11. 스태시 (Stash)

```shell
# 임시 저장
git stash                                           # 현재 변경사항 임시 저장
git stash save "work in progress"                   # 메시지와 함께 임시 저장
git stash -u                                        # 추적되지 않는 파일도 포함
git stash -a                                        # 모든 파일 포함 (무시된 파일도)

# 스태시 관리
git stash list                                      # 스태시 목록 확인
git stash show                                      # 최근 스태시 내용 확인
git stash show -p                                   # 최근 스태시 변경사항 상세 확인
git stash show stash@{1}                            # 특정 스태시 확인

# 스태시 적용 및 삭제
git stash apply                                     # 최근 스태시 적용
git stash apply stash@{1}                           # 특정 스태시 적용
git stash pop                                       # 최근 스태시 적용 후 삭제
git stash drop                                      # 최근 스태시 삭제
git stash drop stash@{1}                            # 특정 스태시 삭제
git stash clear                                     # 모든 스태시 삭제
```

---

## 12. 태그 관리

```shell
# 태그 생성
git tag v1.0.0                                      # 라이트웨이트 태그 생성
git tag -a v1.0.0 -m "Version 1.0.0"                # 어노테이트된 태그 생성
git tag -a v1.0.0 <commit-hash> -m "Version 1.0.0"  # 특정 커밋에 태그 생성

# 태그 조회
git tag                                             # 모든 태그 목록
git tag -l "v1.*"                                   # 패턴으로 태그 검색
git show v1.0.0                                     # 태그 정보 확인

# 태그 푸시 및 삭제
git push origin v1.0.0                              # 특정 태그 푸시
git push origin --tags                              # 모든 태그 푸시
git tag -d v1.0.0                                   # 로컬 태그 삭제
git push origin --delete v1.0.0                     # 원격 태그 삭제
```

---

## 13. 고급 기능

```shell
# Cherry-pick
git cherry-pick <commit-hash>                       # 특정 커밋을 현재 브랜치에 적용
git cherry-pick <commit1>..<commit2>                # 커밋 범위 적용
git cherry-pick --no-commit <commit-hash>           # 커밋하지 않고 변경사항만 적용

# Bisect (이진 탐색으로 버그 찾기)
git bisect start                                    # 이진 탐색 시작
git bisect bad                                      # 현재 커밋이 나쁨
git bisect good <commit-hash>                       # 특정 커밋이 좋음
git bisect reset                                    # 이진 탐색 종료

# Submodule
git submodule add https://github.com/user/repo.git path/to/submodule  # 서브모듈 추가
git submodule init                                  # 서브모듈 초기화
git submodule update                                # 서브모듈 업데이트
git submodule update --init --recursive             # 모든 서브모듈 초기화 및 업데이트

# Worktree (여러 작업 디렉토리)
git worktree add ../feature-branch feature-branch   # 새 작업 디렉토리 생성
git worktree list                                   # 작업 디렉토리 목록
git worktree remove ../feature-branch               # 작업 디렉토리 제거
```

---

## 14. 파일 및 디렉토리 관리

```shell
# 파일 추적 관리
git rm file.txt                                     # 파일 삭제 및 스테이징
git rm --cached file.txt                            # 추적 중단 (파일은 유지)
git mv old-name.txt new-name.txt                    # 파일 이름 변경

# .gitignore
echo "*.log" >> .gitignore                          # 로그 파일 무시
echo "node_modules/" >> .gitignore                  # 디렉토리 무시
git check-ignore -v file.txt                        # 파일이 무시되는 이유 확인
git clean -n                                        # 삭제될 파일 미리보기
git clean -f                                        # 추적되지 않는 파일 삭제
git clean -fd                                       # 추적되지 않는 파일과 디렉토리 삭제
```

---

## 15. 문제 해결 및 디버깅

```shell
# 상태 확인
git status                                          # 현재 상태 확인
git log --oneline -10                               # 최근 10개 커밋 확인
git reflog                                          # 모든 참조 로그 확인
git fsck                                            # 저장소 무결성 검사

# 설정 문제 해결
git config --list --show-origin                     # 설정과 파일 위치 확인
git config --global --unset user.name               # 설정 제거
git config --global --edit                          # 설정 파일 직접 편집

# 원격 저장소 문제
git remote -v                                       # 원격 저장소 확인
git ls-remote origin                                # 원격 브랜치 확인
git fetch --prune                                   # 삭제된 원격 브랜치 정리

# 병합 충돌 해결
git status                                          # 충돌 파일 확인
git diff                                            # 충돌 내용 확인
git add <resolved-file>                             # 해결된 파일 추가
git commit                                          # 병합 완료

# 커밋 히스토리 정리
git rebase -i HEAD~3                                # 최근 3개 커밋 대화형 리베이스
git commit --fixup <commit-hash>                    # 특정 커밋 수정용 커밋 생성
git rebase -i --autosquash HEAD~5                   # fixup 커밋 자동 정리
```

---

## 16. Git 플로우 및 협업

```shell
# Git Flow 기본 패턴
git checkout main                                   # main 브랜치로 이동
git pull origin main                                # 최신 상태로 업데이트
git checkout -b feature/new-feature                 # 새 기능 브랜치 생성
# ... 작업 수행 ...
git add .                                           # 변경사항 스테이징
git commit -m "Add new feature"                     # 커밋
git push -u origin feature/new-feature              # 브랜치 푸시
# ... Pull Request/Merge Request 생성 ...
git checkout main                                   # main으로 돌아가기
git pull origin main                                # 병합된 변경사항 가져오기
git branch -d feature/new-feature                   # 로컬 브랜치 삭제

# 포크 저장소 작업
git remote add upstream https://github.com/original/repo.git  # 원본 저장소 추가
git fetch upstream                                  # 원본 저장소에서 가져오기
git checkout main                                   # main 브랜치로 이동
git merge upstream/main                             # 원본의 변경사항 병합
git push origin main                                # 포크에 푸시
```

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
