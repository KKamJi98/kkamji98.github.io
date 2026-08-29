---
title: "CNCF 첫 기여 가이드 - 이슈 발굴부터 istio PR 머지까지"
date: 2026-08-30 00:40:00 +0900
author: kkamji
categories: [DevOps, OpenSource]
tags: [cncf, istio, open-source, contribution, github, prow, cla]
comments: true
image:
  path: /assets/img/kubernetes/istio/02_envoy_duration_log.webp
---

"오픈소스에 기여하고 싶은데 뭘 해야 할지 모르겠다"는 고민은 대부분 두 지점에서 막힙니다. 어느 저장소의 어느 이슈가 실제로 머지될 만한가, 그리고 첫 PR을 어떤 형식으로 써야 리뷰어가 읽어주는가입니다. 이 글은 istio/istio에 테스트 실행 시간을 절반으로 줄이는 PR을 넣어 머지된 실제 과정을 처음부터 끝까지 정리한 것입니다. 이슈 발굴, 패턴 리서치, 측정 증거, 그리고 CLA부터 prow까지 첫 기여자가 만나는 관문을 전부 다룹니다.

> **TL;DR**  
> - 기여 대상은 "최근 30일 머지 수"로 활동도를 측정하고, 경쟁 PR 유무로 중복을 걸러서 고른다  
> - 머지된 유사 PR의 제목, 본문 구조, 증거 형식을 베끼는 것이 리뷰 통과 확률을 높인다  
> - 첫 PR은 CLA 서명, `/ok-to-test`, `release-notes-none` 라벨처럼 코드 밖의 관문이 더 많다  

---

## 1. 어느 저장소를 노릴 것인가: 머지 속도로 측정하기

기여할 저장소를 고를 때 가장 흔한 실수는 "유명한 저장소"를 고르는 것입니다. 유명한 저장소일수록 이슈 하나에 경쟁 PR이 여러 개 붙어 있고, 첫 기여자의 PR은 리뷰 큐에서 밀립니다. 대신 확인할 지표는 최근 30일간 실제로 머지된 PR 수입니다.

CNCF 주요 프로젝트 13개를 대상으로 측정한 결과는 다음과 같습니다.

| 프로젝트 | 최근 30일 머지 수 |
|---|---|
| grafana/loki | 38 |
| cert-manager/cert-manager | 36 |
| kubernetes-sigs/gateway-api | 36 |
| argoproj/argo-workflows | 34 |
| istio/istio | 32 |
| cilium/cilium | 32 |
| kubernetes-sigs/external-dns | 32 |
| open-telemetry/opentelemetry-go | 31 |
| jaegertracing/jaeger | 27 |
| prometheus/prometheus | 26 |
| envoyproxy/envoy | 24 |
| argoproj/argo-cd | 16 |
| flux2 | 5 |

이 수치는 "GitHub Search API로 후보 이슈를 수집한 뒤, 각 이슈마다 `gh pr list --search`로 경쟁 PR을 확인하고, 최근 머지된 PR 목록으로 활동도를 재는" 스크립트로 산출했습니다. 측정 기준일은 2026년 8월 29일입니다.

활동도만으로는 부족하고, 세 가지 필터를 더 적용합니다. 첫 번째는 `good first issue`와 `help wanted` 라벨이 붙은 이슈만 모으는 것입니다. 두 번째는 각 이슈에 이미 열려 있는 PR을 검색해서 경쟁이 있으면 버리는 것입니다. 실제로 argo-cd의 후보 이슈 여덟 개 중 다섯 개가 이미 PR 두 개에서 네 개씩 붙어 있어서 탈락했습니다. 세 번째는 이슈 본문을 읽고 "문서 수정, 오타, 작은 버그 수정, validation 누락"처럼 작은 diff로 끝나는지 판단하는 것입니다. Cilium의 최근 이슈들이 전부 eBPF 데이터패스 심층 작업이라 제외된 것이 그 예입니다.

이 필터를 통과하면 istio의 "Slow unit tests" 우산 이슈(#37555)가 후보로 남습니다. 이 이슈는 CI 시간을 줄이기 위해 느린 테스트를 찾아 최적화하는 작업을 모아둔 것이고, 이미 비슷한 PR 스무 개 이상이 머지된 검증된 패턴이 있었습니다.

---

## 2. 머지된 PR의 패턴을 리서치한다

이슈를 골랐으면 바로 코드를 고치지 않고, 같은 이슈에서 실제로 머지된 PR들을 분석합니다. 이번에는 우산 이슈에 연결된 머지 PR 열아홉 개 중 여섯 개를 정밀 분석했습니다.

형식에서 발견한 규칙은 다음과 같습니다.

제목은 `test: speed up <TestName>`처럼 Conventional Commits 형식을 따르고, 테스트 하나당 PR 하나를 유지합니다. 본문은 "Root cause(수치 포함), Fix 접근, before/after 측정표, `Tested with:` 명령 블록" 순서입니다. 우산 이슈는 `Fixes #37555`가 아니라 `Part of #37555`로 연결합니다. `Fixes` 키워드는 머지 시 우산 이슈까지 닫아버리기 때문입니다.

라벨은 `area/test and release`, `size/XS`, `release-notes-none` 조합이 표준입니다.

거꾸로 배운 것도 있습니다. 하나의 PR은 테스트에서 RSA-1024 키를 제거해 속도를 높였는데, "테스트라도 deprecated 서명 알고리즘은 꺼린다"는 리뷰로 거부됐습니다. 다른 PR은 프로덕션 코드에 헬퍼를 추가하고 무관한 버그 수정까지 끼얹어서 스코프 과다 판정을 받고 리뷰 없이 방치됐습니다. 요약하면 최적화 대상 선정에서 보안 자세를 약화시키지 말고, PR은 test-only로 좁게 유지하라는 것입니다.

---

## 3. 후보 선정: TestConvertResources 병렬화

2024년 8월 메인테이너 howardjohn이 정리한 "New slow list" 기준으로 아직 풀리지 않은 항목 다섯 개를 확인했습니다. 각 항목의 테스트 파일, 현재 소요 시간, 원인, 개선 방법을 정리하면 다음과 같습니다.

| 테스트 | CI 시간 | 원인 | 개선 방법 |
|---|---|---|---|
| TestConvertResources | 9~20s | 서브테스트 28개 직렬 실행 | `t.Parallel()` 병렬화 |
| TestWebhookSelector | 6.6s | helm 템플릿 3회 렌더링 | `sync.OnceValues` 캐시 |
| TestCRDs + FuzzCRDs | 11s | CRD validator 0.8s 중복 생성 | validator 캐시 |
| TestAnalyzers | 1.9s | 수백 개 analyzer 조합 | 후순위 |
| TestAgent | 8.0s | 실제 프로세스 기동 | 후순위 |

첫 PR로 TestConvertResources를 골랐습니다. 이유는 넷입니다. 단일 최대 시간을 절반 이하로 줄일 수 있고, 이슈에서 커뮤니티 멤버가 같은 접근으로 절반 단축을 이미 확인했으며, 순수 test-only 단일 파일 수정이고, 대기 시간을 줄이는 게 아니라 병렬화라 flake를 만들 위험이 낮습니다.

---

## 4. 구현과 측정

변경 자체는 한 줄입니다. `pilot/pkg/config/kube/gateway/conversion_test.go`의 서브테스트 클로저 첫 줄에 `t.Parallel()`을 추가합니다.

```go
for _, tt := range cases {
    t.Run(tt.name, func(t *testing.T) {
        t.Parallel()
        stop := test.NewStop(t)
        input := readConfig(t, fmt.Sprintf("testdata/%s.yaml", tt.name), validator, tt.validationIgnorer)
        // ...
```

병렬화가 안전한 이유를 PR 본문에 명시했습니다. 피처 플래그 두 개는 루프 시작 전에 `test.SetForTest`로 한 번만 설정되고 서브테스트는 읽기만 하고, 공유 `Validator`는 생성 후 읽기 전용이며, `ValidationIgnorer`는 자체 `sync.RWMutex`를 갖고, 각 서브테스트는 독립적인 `test.NewStop(t)` 채널과 fake client를 받습니다.

측정은 같은 머신에서 before와 after를 교차로 실행했습니다.

| 실행 | 시간 |
|---|---|
| before | 6.868s / 6.979s |
| after | 3.411s / 3.455s |

flake 방어 증거로 `-count=5 -race`(통과, 70.3초), `-count=50`(통과, 157.5초), 패키지 전체 `-count=1`(통과)을 함께 제출했습니다. 리뷰어들이 가장 많이 보는 것이 바로 이 부분입니다.

---

## 5. 첫 PR이 만나는 관문들

코드를 푸시하고 PR을 열면 코드 밖의 관문이 차례로 나타납니다. 실제로 만난 순서대로 정리합니다.

첫 번째는 CLA입니다. istio는 CNCF 산하라 Linux Foundation의 EasyCLA를 사용합니다. PR을 여는 순간 "CLA Not Signed" 체크가 실패하고, [EasyCLA 링크](https://api.easycla.lfx.linuxfoundation.org/v2/repository-provider/github/sign/34682364/74175805/61512/#/?version=2)에서 GitHub 로그인 후 서명하면 통과합니다. CNCF 프로젝트 전체에서 한 번 서명하면 재사용됩니다. 단, Grafana 계열은 cla-assistant.io라는 별도 시스템을 쓰므로 프로젝트마다 다시 서명이 필요합니다.

두 번째는 `/ok-to-test`입니다. 첫 기여자의 PR은 CI가 자동으로 돌지 않고 org 멤버가 `/ok-to-test`를 코멘트해야 실행됩니다. 이 PR에서는 리뷰어가 approve와 함께 직접 붙여줬습니다.

세 번째는 release notes 검사입니다. istio는 사용자에게 보이는 변경이 있으면 `releasenotes/notes/` 아래에 릴리즈노트 파일을 요구합니다. 없으면 `release-notes-none` 라벨로 대체해야 하는데, 이 라벨 추가는 org 멤버 권한이 필요합니다. `/retest-required` 코멘트로 재실행해도 라벨이 없으면 같은 실패가 반복되므로, PR 코멘트에 "test-only PR이라 라벨이 필요하다"고 명시해두면 메인테이너가 지나갈 때 처리해줍니다.

네 번째는 prow의 커밋 메시지 검사입니다. Kubernetes 계열 prow는 커밋 메시지에 `Fixes #N`처럼 자동 이슈 종료 키워드가 들어가면 거부합니다. external-dns PR에서 이 경고를 받고 새 브랜치로 재제출한 적이 있는데, 이때 force-push 없이 새 브랜치로 PR을 다시 여는 것이 안전한 처리 방법입니다.

다섯 번째는 CI에서 무관한 flake와의 조우입니다. 이 PR의 arm64 유닛테스트가 실패했는데, 실패한 테스트는 `pkg/kube/kclient` 패키지의 `TestSwappingClient/CRD_not_ready`로 이 PR이 건드리지 않은 패키지이며 2023년부터 flake로 추적된 이력(#45200)이 있는 테스트였습니다. 내가 수정한 `TestConvertResources`는 같은 실행에서 54개 서브테스트 전부 통과했습니다. 이런 경우 PR 코멘트에 "무관한 패키지의 알려진 flake"라는 근거와 함께 기록해두면 메인테이너 판단에 근거가 남습니다.

---

## 6. 결과

2026년 8월 29일, PR은 istio 멤버 ramaraochavali의 승인과 함께 머지됐습니다. merge commit은 `1d664989587a1284`입니다. 머지까지 걸린 시간은 PR 오픈 시점부터 약 31시간이었고, 이 중 대부분은 CLA 서명과 CI 실행 대기였습니다.

PR 링크는 [istio/istio#61512](https://github.com/istio/istio/pull/61512)이고, 우산 이슈인 [#37555](https://github.com/istio/istio/issues/37555)에는 `Part of`로 연결돼 있습니다.

같은 방법으로 external-dns #5151(dotted hostname의 TXT 레코드 변형 버그 수정)과 loki #5459(Ruler local storage 문서에 `fake` tenant ID 명시)에도 PR을 넣어 리뷰 대기 중입니다. 이슈 발굴부터 머지까지의 절차가 한 번 만들어지면 다음 기여는 훨씬 빨라집니다.

---

## 7. Reference

- [istio/istio PR #61512](https://github.com/istio/istio/pull/61512)
- [istio/istio Issue #37555 - Slow unit tests](https://github.com/istio/istio/issues/37555)
- [kubernetes-sigs/external-dns PR #6677](https://github.com/kubernetes-sigs/external-dns/pull/6677)
- [grafana/loki PR #24278](https://github.com/grafana/loki/pull/24278)
- [Linux Foundation EasyCLA](https://easycla.lfx.linuxfoundation.org/)
- [Prow Commands Documentation](https://docs.prow.k8s.io/docs/commands/)

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
