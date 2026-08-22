---
title: "Claude plugin 기초 - skill, marketplace, prompt"
date: 2026-08-23 06:12:00 +0900
author: kkamji
categories: [AI, Agent]
tags: [claude, plugin, skill, eli5, marketplace, prompt]
comments: true
image:
  path: /assets/img/ai/eli5-plugin-three-files.webp
---

공개된 ELI5 plugin의 `SKILL.md`는 10줄입니다. 그중 본문은 한 문장과 `Topic: $ARGUMENTS`입니다. 트윗이 말하는 사용량과, Claude Code가 실제로 읽는 파일은 같은 층이 아닙니다.

이 글은 `anthropics/claude-plugins-community`의 `eli5/` 디렉터리와 marketplace 등록, 작성자 트윗을 같은 날짜에 대조한 기록입니다. 내부 사용 로그는 없습니다.

---

## 1. plugin은 파일 세 개다

2026-08-23에 받은 트리는 아래가 전부입니다.

```text
eli5/
  .claude-plugin/plugin.json
  README.md
  skills/eli5/SKILL.md
```

scripts, references, templates는 없습니다. `plugin.json`은 이름 `eli5`, 버전 `1.0.0`, author `Thariq Shihipar`, license MIT입니다. README는 `/eli5 how does DNS work` 한 예와, HTML artifact를 만든다는 한 문장입니다.

![plugin.json, README, SKILL.md 세 파일이 한 줄로 이어진 구조](/assets/img/ai/eli5-plugin-three-files.webp)
_동작의 거의 전부는 세 번째 파일에 있다._

marketplace.json의 `claude-community` 목록에는 같은 이름이 `source: ./eli5`, category `learning`, `strict: false`로 들어가 있습니다. 설치 명령의 `@claude-community`는 그 목록 이름입니다.

---

## 2. 본문은 한 줄과 $ARGUMENTS다

`SKILL.md` 정본은 이렇습니다.

```text
Explain like I'm someone who knows nothing about this topic, using a HTML artifact with big pictures and few words.

Topic: $ARGUMENTS
```

frontmatter description은 여전히 "like I'm a 5 year old"입니다. 본문은 5살을 말하지 않습니다. git 이력도 같습니다. 처음 문장은 `idiot`과 `HTML page`였고, `e086c443`가 artifact로, `794af9e6`가 `someone who knows nothing`으로 바꿨습니다.

![슬래시 명령이 SKILL.md를 거쳐 HTML artifact가 되는 흐름](/assets/img/ai/eli5-slash-to-artifact.webp)
_명령을 채우는 값은 Topic 한 칸이다. 모듈 분석 절차는 파일에 없다._

작성자 `@trq212`의 후속 트윗도 같은 경계를 말합니다. 이름은 ELI5가 clickbait에 가깝고, 중요한 부분은 big pictures / few words라는 것입니다. `/eli5 how does this module work` 같은 예시는 트윗에 있고, 스킬 파일에는 없습니다. 그 예시는 사용자가 넣는 `$ARGUMENTS`입니다.

---

## 3. 사용량 주장은 파일이 증명하지 않는다

같은 날 syndication으로 읽은 원문은 이 문장입니다. `a skill people at Anthropic have been using a lot recently: ELI5`. 작성자 GitHub `ThariqS`의 bio는 `Claude Code @anthropics`입니다. 직원이 그렇게 말한 것은 1차 출처입니다.

그 문장은 사용자 수나 빈도를 주지 않습니다. 같은 스레드의 설치 안내와 "official plugin으로 올릴지 고민 중"도 파일 밖 발화입니다. 레포에 올라온 것은 community marketplace 항목이지, Claude Code에 기본으로 실리는 skill이 아닙니다.

조회수 128만, 북마크 1.5만 같은 숫자는 이 대조에서 확인하지 않았습니다. 확인한 숫자는 likes 10907, conversation 308입니다.

Hermes나 kkamji-settings의 skill은 절차, pitfalls, verification, scripts를 가집니다. ELI5는 그 층이 없습니다. plugin wrapper가 한 줄 prompt를 슬래시 명령에 붙인 형태입니다. 구조를 베낄 내용은 거의 없고, 베낄 수 있는 것은 "모르는 사람 + 그림 많고 글 적게"라는 출력 제약뿐입니다.

---

## 4. Reference

- [claude-plugins-community / eli5](https://github.com/anthropics/claude-plugins-community/tree/main/eli5)
- [eli5 SKILL.md](https://github.com/anthropics/claude-plugins-community/blob/main/eli5/skills/eli5/SKILL.md)
- [Thariq / ELI5](https://x.com/trq212/status/2090884854590382515)
- [ThariqS on GitHub](https://github.com/ThariqS)

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
