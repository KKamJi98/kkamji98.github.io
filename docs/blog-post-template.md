# kkamji.net Technical Post Template

이 문서는 신규 기술 글 작성 시 기본 구조로 사용한다. 실제 글에서는 주제 성격에 맞게 섹션명을 조정하되, 문제 의식, 핵심 요약, 운영 관점, Reference, footer는 유지한다.

```md
---
title: <검색 키워드가 포함된 한국어 기술 제목>
date: YYYY-MM-DD HH:MM:SS +0900
author: kkamji
categories: [Category]
tags: [tag-one, tag-two]
comments: true
image:
  path: /assets/img/<domain>/<image>.webp
---

<이 글에서 다루는 문제, 배경, 왜 중요한지 2-4문장으로 설명합니다.>

> **TL;DR**  
> - <핵심 요약 1>  
> - <핵심 요약 2>  
> - <핵심 요약 3>  
{: .prompt-info}

---

## 1. 왜 이 주제를 보는가

## 2. 핵심 개념

## 3. 내부 동작 또는 구조

## 4. 예시 또는 실습

## 5. 운영 관점에서 보면

- 장애 대응 시 먼저 확인할 지점은 무엇인가
- 비용, 성능, 보안 관점의 주의사항은 무엇인가
- 도입 전 확인해야 할 전제 조건은 무엇인가

## 6. 마치며

## 7. Reference

- [Source Name - Topic](https://example.com)

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
```

## 작성 원칙

- 공식 문서, release note, source code, issue를 우선 근거로 사용한다.
- 외부 링크는 하단 `Reference`에 모은다.
- 본문에서는 핵심 용어를 자연스럽게 영어로 유지해도 된다.
- 긴 글은 섹션 끝에 짧은 정리를 추가한다.
- `운영 관점에서 보면` 섹션에는 단순 요약이 아니라 실제 운영 판단 기준을 적는다.
- 기존 footer는 절대 수정하지 않는다.
