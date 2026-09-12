---
title: Docs index
updated: 2026-09-13
type: architecture
status: current
---

# Docs index

문서 하나당 한 줄. 여기 없는 `docs/**/*.md`는 CI가 막는다.

## Architecture

- [Theme overrides registry](THEME_OVERRIDES.md) - gem 테마 위에 얹은 override 레지스트리. `_includes/`나 chirpy scss를 고치면 여기도 고친다.
- [Blog content-quality harness](blog-content-quality-harness.md) - `kkamji_scripts/blog/audit_content_depth.py`의 설계 의도와 사용법.

## Rules

- [Static diagrams](static-diagrams.md) - 정적 다이어그램 제작 기준, 검증과 원본 매핑.

- [Technical post template](blog-post-template.md) - 신규 기술 글의 기본 구조와 유지해야 하는 섹션.

- [First-person experience posts](first-person-experience-posts.md) - 겪은 일을 다룬 글에서 화자를 지우지 않기 위한 체크리스트. 자동 게이트가 못 잡는 사각지대.

- [Emphasis and bold](emphasis-and-bold.md) - 본문 강조를 붙이는 자리와 붙이지 않는 자리. `check_emphasis.py` 기준.

## Evidence

- [Blog refresh backlog](blog-refresh-backlog.md) - `audit_blog_quality.py` 결과 기반 리프레시 우선순위.
