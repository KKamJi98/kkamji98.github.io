---
title: "Jenkins Operator 심화 - Reconcile 루프와 소스 코드 [Jenkins 5]"
date: 2026-07-31 02:12:00 +0900
author: kkamji
categories: [CI/CD, Jenkins]
tags: [devops, ci-cd, jenkins, jenkins-operator, kubernetes, controller-runtime]
comments: true
image:
  path: /assets/img/ci-cd/jenkins/jenkins.webp
---

Jenkins Operator를 운영하다 보면 이런 상황을 만납니다. JCasC 설정을 변경했는데 Jenkins에 반영되지 않습니다. Operator 로그를 보면 같은 에러가 반복되다가 어느 순간 조용해집니다. CR을 지우고 다시 만들면 동작합니다. 왜 그런지 이해하려면 Operator가 한 패스(pass)에서 무엇을 어떤 순서로 수행하는지 소스 코드 수준에서 볼 필요가 있습니다. 이 글은 jenkinsci/kubernetes-operator의 reconcile 루프를 jenkins_controller.go부터 따라가는 심화 편입니다.

> **TL;DR**  
> - 한 패스는 `base.Validate`, `base.Reconcile`, `waitForJenkins`, `user.ReconcileCasc`, `user.ReconcileOthers` 순서다. **CR status의 타임스탬프가 어디까지 찍혔는지** 보면 실패 지점이 좁혀진다.  
> - `reconcileFailLimit = 10`이라 같은 에러가 10번 쌓이면 조정을 멈춘다. **로그가 조용해진 것은 해결이 아니라 포기 신호**일 수 있고, 이때는 Operator Pod를 재시작해야 한다.  
> - Groovy 스크립트는 해시로 추적되어 변경된 것만 다시 적용된다. master가 bare Pod인 덕분에 Operator가 Pod를 직접 조정 대상으로 삼는다.  
> - pvc 백업은 workspace와 최상위 `config.xml`을 제외하므로 전체 복제가 아니라 상태 복구용이다. 플러그인 데이터 호스트가 2026-02에 바뀌어 구버전이 403으로 크래시 루프에 빠진 사례(#1162)가 있다.  
{: .prompt-info}

---

## 1. reconcile 진입점: 함수 호출 순서

Operator의 심장은 `internal/controller/jenkins_controller.go`의 reconcile 함수입니다. watch 이벤트가 도착하면 다음 순서로 진행합니다.

![reconcile walkthrough](/assets/img/ci-cd/jenkins/jenkins-operator/jenkins-operator-reconcile-walkthrough.webp)
> One pass through reconcile  

1. **base.Validate** - CR spec의 유효성을 검사합니다. 잘못된 spec은 이 단계에서 거부됩니다.
2. **base.Reconcile** - namespace, RBAC, Secret, master Pod, API 토큰, 7개 보안 강화 Groovy 스크립트를 적용합니다.
3. **waitForJenkins** - master Pod가 Jenkins REST API를 응답할 때까지 폴링합니다. 준비되지 않았으면 5초 후 재큐(requeue)하고 현재 패스를 종료합니다. 컨테이너 종료를 감지하면 Pod를 재시작합니다.
4. **user.ReconcileCasc** - JCasC YAML과 사용자 Groovy 스크립트를 적용합니다.
5. **user.ReconcileOthers** - seed job, backup/restore job을 생성하고 확인합니다.
6. **status 업데이트** - 각 단계 완료 시각(ProvisionStartTime, BaseConfigurationCompletedTime, UserConfigurationCompletedTime)을 CR status에 기록합니다.

이 순서가 디버깅의 첫 번째 지침이 됩니다. JCasC가 반영되지 않는 문제는 4단계 문제이지만, 2단계나 3단계에서 이미 실패하고 있다면 4단계는 아예 실행되지 않습니다. CR status의 어느 타임스탬프까지 찍혀 있는지 확인하면 실패 지점이 몇 단계인지 즉시 좁힐 수 있습니다.

---

## 2. 10회 실패 포기 로직

reconcile은 같은 에러가 반복되면 무한히 도는 것이 아니라 멈춥니다. jenkins_controller.go에는 reconcileFailLimit = 10이 정의되어 있고, 동일한 에러가 10번 누적되면 status에 ReconcileLoopFailed를 남기고 조정을 중단합니다.

"로그가 조용해졌다"는 것은 해결된 것이 아니라 Operator가 포기했다는 신호일 수 있습니다. 이 상태에서 CR을 고쳐도 아무 일도 일어나지 않습니다. Operator Pod를 재시작하면 reconcile이 재트리거됩니다. Operator Pod 재시작은 master Pod와 무관하므로 실행 중인 빌드에 영향을 주지 않습니다.

---

## 3. Groovy 스크립트의 멱등성: AppliedGroovyScripts

Operator가 Jenkins에 적용하는 설정은 상당 부분 Groovy 스크립트로 실행됩니다. base 단계의 보안 강화 스크립트 7종(basic-settings, csrf, usage-stats, insecure-features, kubernetes-plugin, views, job-dsl-approval)이 대표적입니다. reconcile이 반복될 때마다 같은 스크립트를 다시 실행하면 안 되므로, Operator는 적용 완료된 스크립트의 해시를 기록해 둡니다. 해시가 바뀌지 않으면 재실행하지 않습니다.

이 설계는 reconcile 루프의 멱등성(idempotency)을 담보합니다. Kubernetes 컨트롤러는 언제든 재실행될 수 있으므로, 같은 입력에 같은 결과를 내는 것이 기본 요건입니다. 스크립트를 수정하면 해시가 달라지고, Operator는 변경된 스크립트만 다시 적용합니다.

---

## 4. master는 왜 bare Pod인가

Operator가 관리하는 Jenkins master는 기본으로 Deployment가 아닌 bare Pod로 실행됩니다. 이 선택의 결과는 운영에 그대로 나타납니다. 롤링 업데이트가 없고, 재시작은 Pod 삭제 후 재생성이며, 노드 장애 시 재스케줄링은 다른 워크로드와 동일하게 kubelet의 Pod 라이프사이클을 따릅니다.

Deployment로 전환할 수 있습니다. Jenkins CR의 master에 `jenkins.io/use-deployment: "true"` 어노테이션을 추가하면 Operator가 Deployment로 관리합니다. 다만 Operator의 reconcile이 직접 Pod를 제어하는 설계와 Deployment의 replica 관리가 완전히 같은 모델은 아니므로, 전환 시 Operator 버전별 동작 차이를 테스트하고 적용해야 합니다.

왜 기본이 bare Pod인가에 대한 설계 배경은 공식 문서에 명시적으로 설명되어 있지 않지만, Operator가 Pod를 직접 조정 대상으로 삼으면 상태 추적이 단순해진다는 이점은 코드에서 읽을 수 있습니다. Deployment를 사이에 두면 Operator가 보는 Pod 상태와 Deployment가 관리하는 replica 상태가 어긋나는 지점이 생깁니다.

---

## 5. seed-job-agent: Job DSL 실행 구조

user 단계의 seed job 처리는 별도 컨테이너로 분리되어 있습니다. seed-job-agent Deployment가 job-dsl 스크립트를 실행하고, Operator는 에이전트가 준비될 때까지 기다린 뒤 진행합니다. master Pod 안에서 직접 실행하지 않는 이유는 Job DSL 실행이 Jenkins 프로세스와 독립적인 작업이기 때문입니다. 에이전트가 실패해도 master의 가용성과 분리됩니다.

이 구조는 앞선 글에서 다룬 "중앙 파이프라인 저장소" 패턴과 만납니다. CR에 선언한 seed job이 중앙 저장소의 Job DSL을 실행하면, Operator 입장에서는 CR이 곧 Job 목록의 선언적 원본이 됩니다.

---

## 6. backup-pvc 내부

기본 백업 provider인 pvc의 내부를 뜯어보면 운영 판단에 필요한 세부 사항이 보입니다. backup은 별도 Pod에서 실행되며, jenkins-home을 tar로 압축할 때 zstd 압축을 사용합니다. 백업 중 다른 백업이 겹치지 않도록 lock 파일로 직렬화하고, 백업 파일을 원자적으로(atomic mv) 이동해 불완전한 파일이 남지 않게 합니다.

제외 규칙도 있습니다. workspace 디렉터리와 최상위 config.xml은 백업에서 제외됩니다. 즉 pvc 백업은 빌드 산출물이 아니라 Jenkins 상태(잡 정의, credential, 플러그인 설정)의 복구를 목적으로 합니다. workspace가 필요하면 별도 보존 전략을 세워야 합니다.

---

## 7. 플러그인 데이터 소스와 #1162 사건

Operator는 플러그인 보안 경고 데이터를 다운로드해 설치할 플러그인을 검증합니다. 이 데이터의 호스트가 2026년 2월에 ci.jenkins.io에서 reports.jenkins.io로 전환되었습니다. 구버전 Operator는 여전히 이전 호스트를 호출하다 403을 받고, reconcile이 실패하는 크래시 루프에 빠집니다. 이슈 #1162로 보고된 사건입니다.

이 사건이 시사하는 것은 Operator가 외부 데이터 소스에 의존한다는 사실입니다. Jenkins 인프라 쪽 변경이 Operator 버전과 무관하게 운영에 영향을 줄 수 있으므로, 플러그인 설치 실패로 reconcile이 반복될 때는 Operator 로그의 다운로드 에러를 확인하고 최신 버전 업그레이드를 검토해야 합니다.

---

## 8. 버전과 문서 현황 (2026-08 기준)

| 항목 | 값 |
| :--- | :--- |
| 최신 stable 릴리스 | v0.8.1 (2024-07-05) |
| 최신 prerelease | v0.9.0-beta2 (2025-12-21) |
| master 마지막 커밋 | 2026-03-07 (LTS bump bot) |
| 마지막 human 커밋 | 2026-02-07 |
| API 버전 | v1alpha2 (2019년 이후) |
| 기본 Jenkins 이미지 | jenkins/jenkins:2.541.2-lts |

운영 도입 판단의 재료로 정리하면 다음과 같습니다. 저장소는 archived가 아니고 이슈 응답도 이어지고 있어 서비스는 유지되고 있습니다. 그러나 릴리스 간격이 길고(stable이 2024년 7월 이후 없음) 핵심 기여자가 사실상 한 명입니다. 문서 사이트의 버전 라벨이나 chart appVersion 불일치 같은 잔잔한 정합성 문제도 남아 있습니다. 신규 도입 시 v0.8.1을 기준으로 하되, 업스트림 활동 모니터링을 전제로 하는 것이 현실적입니다.

---

## 9. Reference

- [Source - jenkins_controller.go](https://github.com/jenkinsci/kubernetes-operator/blob/master/internal/controller/jenkins_controller.go)
- [Source - base reconciler](https://github.com/jenkinsci/kubernetes-operator/blob/master/pkg/configuration/base/reconciler.go)
- [Source - base configuration configmap](https://github.com/jenkinsci/kubernetes-operator/blob/master/pkg/configuration/base/resources/base_configuration_configmap.go)
- [Source - groovy Ensure/EnsureSingle](https://github.com/jenkinsci/kubernetes-operator/blob/master/pkg/groovy/groovy.go)
- [Source - seedjobs](https://github.com/jenkinsci/kubernetes-operator/blob/master/pkg/configuration/user/seedjobs/seedjobs.go)
- [Source - backup pvc scripts](https://github.com/jenkinsci/kubernetes-operator/tree/master/backup/pvc)
- [Issue #1162 - plugin data download 403](https://github.com/jenkinsci/kubernetes-operator/issues/1162)
- [Releases - jenkinsci/kubernetes-operator](https://github.com/jenkinsci/kubernetes-operator/releases)
- [Jenkins Operator Docs - Architecture and Design](https://jenkinsci.github.io/kubernetes-operator/docs/how-it-works/architecture-and-design/)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
