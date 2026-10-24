---
title: Code block rendering
updated: 2026-10-24
type: rule
status: current
---

# Code block rendering

코드 원문의 정확성과 화면의 문법 강조는 별도 검증 대상이다. 빌드 성공이나 Rouge의 색칠 결과만으로 예제 코드의 실행 가능성을 판단하지 않는다.

## 작성

- 실행할 코드만 해당 언어로 표시한다. 명령과 출력이 섞인 콘솔 기록, 디렉터리 목록, 오류 로그는 `text`로 표시하거나 실행 코드와 별도 블록으로 나눈다.
- 언어 이름은 설치한 Rouge가 실제로 지원해야 한다. `hcl`과 `terraform`의 이름만 바꾸는 것은 해결책이 아니다. 두 lexer는 구현을 공유하며 각각 회귀 검사가 필요하다.
- JSON의 여러 객체는 하나의 배열이나 `Statement`를 포함한 문서로 표현한다. 완성된 JSON이 아닌 조각이면 조각임을 설명하고 `text`를 선택한다.
- 문자열의 backslash, 정규식 escape, Liquid의 raw 경계와 원문의 공백을 보존한다. 빨간 배경을 없애려고 escape를 지우거나 `.err` 색상을 숨기지 않는다.
- LLM Wiki의 Markdown도 코드, 로그, 조각의 언어를 구분한다. Obsidian과 Jekyll은 다른 렌더러이므로 Wiki 표시 성공을 블로그 표시의 증거로 사용하지 않는다. Wiki에서 블로그로 옮긴 예제는 아래 블로그 검사도 통과해야 한다.

## 검사

저장소 root에서 실행한다. 의존성은 `bundle install`로 준비한다.

```bash
bundle exec ruby tools/test_code_highlighting.rb
bundle exec ruby kkamji_scripts/blog/check_code_blocks.rb _posts/YYYY/MM/YYYY-MM-DD-post.md
bundle exec ruby kkamji_scripts/blog/check_code_blocks.rb
bash tools/test.sh
```

- 파일 인수는 작성 중인 글을 검사한다. 인수가 없으면 `_posts`, `_tabs`, `docs`, `kkamji_scripts`의 Markdown과 root `README.md`, `AGENTS.md`를 검사한다. 예제 템플릿과 내부 작성 문서도 같은 지원 언어 검사를 통과해야 한다.
- Kramdown GFM AST로 실제 codeblock을 찾는다. 더 긴 fence 안의 예제 fence는 별도 블록으로 세지 않는다.
- 알 수 없는 언어, 닫히지 않은 fence, 같은 길이 이상의 fence에 다른 언어를 붙여 블록을 합친 경우, Rouge `Error` token과 token 결합 결과의 원문 불일치는 실패다. 보고서에는 경로, 행과 오류 종류만 기록하고 코드 값을 출력하지 않는다.
- pre-commit은 관련 변경이 있을 때 전체 index의 코드 블록을 `--staged`로 검사한다. 검사기와 lexer의 부분 staging은 거부한다. 산문 formatter가 바꾼 최종 index도 검사한다.
- `tools/test.sh`, PR과 Pages build는 회귀 테스트, source 검사와 production HTML 검사를 실행한다. PR은 site artifact 업로드와 deploy를 실행하지 않는다. production 결과의 `.err` token은 배포를 막는다. pre-publish 검사는 source를 검사하며 production HTML 검사를 대신하지 않는다.
- `--report FILE`은 JSON 증적을 만든다. `--site DIR`은 이미 생성한 HTML을 검사한다. 본문 코드와 inline code의 실제 실행 의미, 컴파일 및 외부 서비스 권한까지 검증하는 도구는 아니다.
- 배포 후에는 해당 permalink의 HTML과 실제 화면을 확인한다. Aside를 쓸 수 없으면 DOM 확인과 화면 미검증을 구분해 기록한다.

## Lexer 유지보수

`_plugins/code-highlighting.rb`는 gem을 직접 수정하지 않는 저장소 소유 보정이다.

- HCL의 정상 escape, 함수 인자 구두점과 중첩 구분자를 처리한다. 잘못된 `\q`는 계속 오류로 남긴다.
- Markdown의 backslash hard line break를 처리한다.
- Rouge 4.7에 없는 Solidity는 전용 lexical rule로 등록한다. Solidity 문자열과 `$` 식별자, keyword와 정수 및 bytes type을 구분한다. 이것은 Solidity compiler가 아니다.
- Rouge와 Chirpy를 갱신하면 회귀 테스트, 전체 source 검사와 production build를 다시 실행한다. upstream이 같은 기능을 제공하면 로컬 보정 제거 후보를 검증한다. 테스트 없이 override를 중복 유지하거나 제거하지 않는다.
- rollback은 이 수정 commit을 revert하고 이전 source와 build를 다시 배포한다. 예제의 escape를 되돌리거나 테마 전체의 error 스타일을 변경하지 않는다.

관련 구조와 override 등록은 [Theme overrides registry](THEME_OVERRIDES.md)를 따른다.
