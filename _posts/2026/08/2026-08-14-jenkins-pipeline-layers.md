---
title: "Jenkins 파이프라인 알아보기 - Jenkinsfile, Multibranch, Shared Library [Jenkins 4]"
date: 2026-08-14 21:30:00 +0900
author: kkamji
categories: [DevOps]
tags: [devops, ci-cd, jenkins, jenkinsfile, pipeline, multibranch, shared-library, seed-job]
comments: true
image:
  path: /assets/img/ci-cd/jenkins/jenkins.webp
---

Jenkins Item을 만들면서 Pipeline script 박스에 Groovy를 붙여넣은 적이 있다면, 그 스크립트가 지금 어디에 있는지 한 번 생각해 보아야 합니다. Jenkins 컨테이너 안의 설정 파일 안에 있습니다. git으로 관리되지 않고, 코드 리뷰를 거치지 않으며, Jenkins를 재구축하면 사라집니다. 파이프라인을 고치려면 Jenkins UI에 들어가야 하고, 같은 수정을 서비스 30개에 적용하려면 30번 붙여넣어야 합니다. 이 글은 파이프라인 정의를 Jenkins 안에서 꺼내 리포지토리로 옮기는 계층별 방법을 정리합니다.

---

## 1. Declarative와 Scripted, 두 가지 파이프라인 문법

Jenkins Pipeline에는 두 문법이 있습니다. Scripted Pipeline은 Groovy 그 자체입니다. 변수, 조건문, 반복문을 그대로 쓸 수 있고 유연하지만, 그만큼 임의 코드 실행과 같아 통제가 어렵습니다. Declarative Pipeline은 그 위에 정의된 구조화된 문법입니다. `pipeline` 블록 안에 `agent`, `stages`, `post` 같은 예약된 섹션을 선언하는 형태로, 가독성과 도구 지원이 좋습니다.

```groovy
pipeline {
    agent any
    stages {
        stage('Build') {
            steps {
                sh './gradlew build'
            }
        }
    }
    post {
        always {
            junit '**/test-results/**/*.xml'
        }
    }
}
```

둘 다 실행 시에는 CPS(Continuation-Passing Style)로 직렬화되어 Jenkins 마스터에서 해석됩니다. 새로 시작하는 파이프라인은 Declarative가 기본 선택입니다. 구조가 강제되어 유지보수가 쉽고, 선언된 stage 구조가 UI에 그대로 시각화됩니다. Declarative로 표현하기 어려운 복잡한 로직은 `script` 블록 안에 Scripted 코드를 섞어 쓸 수 있습니다.

이 문법 자체는 어디에 저장하든 같습니다. 차이를 만드는 것은 다음 섹션의 저장 위치입니다.

---

## 2. Pipeline script에서 Pipeline script from SCM으로

Freestyle이 아닌 Pipeline 잡을 만들 때 Definition 항목에서 두 가지 중 하나를 고릅니다.

**Pipeline script**는 스크립트를 UI 텍스트 박스에 직접 입력하는 방식입니다. Jenkins가 잡 설정 안에 저장합니다. 빠르게 시험해 보기에는 편하지만 버전 관리가 되지 않고, 변경 이력이 git이 아니라 Jenkins 설정에 남습니다.

**Pipeline script from SCM**은 리포지토리에서 스크립트를 읽어오는 방식입니다. SCM(Git 등)과 리포지토리 주소, credential, 브랜치를 지정하고, Script Path에 파일 경로를 씁니다. 기본값이 `Jenkinsfile`입니다. 잡이 실행될 때마다 해당 브랜치를 checkout해 그 파일을 실행합니다.

이 전환으로 파이프라인이 코드가 됩니다. 변경은 PR로 리뷰하고, 히스토리는 git이 관리하고, 롤백은 revert로 합니다. Jenkins를 재구축해도 잡 정의만 다시 만들면 파이프라인은 리포지토리에 그대로 있습니다. 파일 이름이 꼭 Jenkinsfile일 필요는 없습니다. Script Path에 `deploy/Jenkinsfile.prod` 같은 경로를 지정할 수 있습니다.

---

## 3. Multibranch Pipeline: 브랜치마다 잡을 만들어 주는 잡

여기까지가 잡 하나에 브랜치 하나짜리 구성입니다. 리포지토리의 모든 브랜치와 PR에 대해 빌드를 돌리려면 Multibranch Pipeline 잡을 씁니다.

Multibranch Pipeline은 고정된 스크립트 경로가 아니라 리포지토리 전체를 대상으로 동작합니다. 주기적으로 또는 webhook로 브랜치를 색인(branch indexing)하고, 발견된 브랜치마다 하위 잡을 자동으로 생성합니다. 각 브랜치의 잡은 그 브랜치의 Jenkinsfile을 읽어 실행합니다. 브랜치가 삭제되면 대응하는 잡도 정리됩니다. PR 빌드도 여기에 포함됩니다. GitHub Branch Source나 Bitbucket Branch Source 플러그인이 PR을 발견해 `PR-번호` 형태의 잡으로 만듭니다.

브랜치별 Jenkinsfile이 다를 수 있다는 점이 핵심입니다. `main` 브랜치는 배포까지 포함하고, `feature/*` 브랜치는 빌드와 테스트만 하는 구성을 브랜치 안의 Jenkinsfile 수정으로 만들 수 있습니다. `when { branch 'main' }` 같은 조건으로 하나의 Jenkinsfile 안에서 분기할 수도 있습니다.

빌드 트리거는 webhook가 권장됩니다. GitHub나 Bitbucket이 push 시 Jenkins에 알리고, Jenkins는 즉시 색인을 돌립니다. webhook를 구성할 수 없는 환경에서는 주기적 색인(polling)으로 폴백하지만, 감지 지연과 불필요한 폴링 비용이 있습니다.

---

## 4. Shared Library: 파이프라인 간 코드 재사용

서비스가 늘면 같은 패턴이 반복됩니다. 빌드하고, 스캔하고, 배포하는 단계가 서비스마다 거의 같습니다. 이 공통 로직을 각 Jenkinsfile에 복붙하는 대신 Shared Library로 뺍니다.

Shared Library는 별도 Git 리포지토리로, 정해진 디렉터리 구조를 가집니다.

```text
(root)
+-- vars/
|   +-- buildService.groovy      -- 전역 변수/단계 정의
|   +-- deployService.groovy
+-- src/
|   +-- org/foo/Utilities.groovy -- Groovy 클래스
+-- resources/
    +-- org/foo/config.yaml      -- 라이브러리가 쓰는 리소스
```

`vars/` 아래의 `.groovy` 파일 하나가 파이프라인에서 호출 가능한 전역 단계가 됩니다. 파일 이름이 곧 호출 이름이고, `call` 메서드가 본체입니다.

```groovy
// vars/sayHello.groovy
def call(String name = 'world') {
    echo "Hello, ${name}"
}
```

Jenkinsfile에서는 로드 선언 후 단계처럼 호출합니다.

```groovy
@Library('my-shared-lib') _

pipeline {
    agent any
    stages {
        stage('Greet') {
            steps {
                sayHello('jenkins')
            }
        }
    }
}
```

라이브러리 등록은 Manage Jenkins 화면의 Global Pipeline Libraries에서 합니다. 이름, 기본 버전(브랜치나 태그), SCM 주소를 등록하면 모든 잡에서 `@Library`로 불러 쓸 수 있습니다. 버전을 명시해 특정 태그를 고정할 수도 있습니다. `library` 스텝으로 실행 중에 동적으로 로드하는 방법도 있습니다.

폴더 단위로 등록하면 같은 Jenkins에서 조직마다 다른 라이브러리를 쓰게 할 수 있습니다. 신뢰하는(trusted) 라이브러리로 등록하면 샌드박스 밖에서 실행되어 강력한 API를 쓸 수 있지만, 그만큼 신중하게 관리해야 합니다. 일반 라이브러리는 Groovy 샌드박스 안에서 실행되고, 제한된 API만 호출할 수 있습니다.

`@NonCPS` 표시는 직렬화 예외를 피하는 실무 지식으로 알아 둡니다. CPS 변환이 어려운 복잡한 Groovy 코드는 `@NonCPS`로 표시해 일반 Groovy로 실행되게 하면 파이프라인이 멈추는 현상을 예방할 수 있습니다.

---

## 5. Seed Job과 Job DSL: 잡 자체를 코드로 만들기

지금까지의 계층은 파이프라인 내용을 코드화했습니다. 마지막 계층은 잡 정의 자체를 코드화합니다. 서비스가 30개면 Multibranch 잡도 30개 만들어야 하는데, 이걸 UI로 하나씩 만들지 않고 Job DSL로 생성합니다.

Job DSL 플러그인은 Groovy DSL로 Jenkins 잡을 정의합니다. Seed job은 이 DSL을 실행하는 잡입니다.

```groovy
// 중앙 리포지토리의 DSL 스크립트
multibranchPipelineJob('my-service') {
    branchSources {
        git {
            remote('https://github.com/org/my-service.git')
        }
    }
}
```

이 스크립트를 실행하면 `my-service`라는 Multibranch 잡이 생성됩니다. 서비스 목록이 늘면 DSL에 한 줄 추가하고 seed job을 돌리면 됩니다. 잡 설정의 드리프트도 없습니다. 잡의 원본이 중앙 리포지토리의 DSL이므로, 잡을 지웠다가 seed job을 다시 돌리면 같은 잡이 다시 만들어집니다.

이 구성이 모이면 다음 그림이 됩니다.

![Pipeline layers](/assets/img/ci-cd/jenkins/jenkins-pipeline-layers.webp)
> 파이프라인 정의가 사는 세 곳  

중앙 리포지토리의 Job DSL이 seed job을 통해 Multibranch 잡을 만들고, 각 Multibranch 잡은 서비스 리포지토리의 Jenkinsfile을 읽고, Jenkinsfile은 Shared Library를 로드합니다. 파이프라인 정의 전부가 git 안에 있습니다. Jenkins UI에서 잡을 만들고 스크립트를 붙여넣던 초기 상태와 비교하면, Jenkins는 실행 환경일 뿐이고 정의는 전부 리포지토리에 있는 구조입니다.

서비스 리포지토리에 Jenkinsfile을 두는 per-repo 방식과, 파이프라인 코드를 중앙 리포지토리에 모두 두는 중앙 집중 방식은 트레이드오프가 있습니다. per-repo는 서비스 팀이 자기 파이프라인을 자율적으로 바꿀 수 있지만 공통 정책 적용이 느슨해집니다. 중앙 집중은 보안 게이트와 표준을 일괄 적용할 수 있지만 변경마다 중앙 리포지토리를 거쳐야 합니다. 규모와 팀 구조에 따라 섞어 쓰게 됩니다. 예를 들어 잡 생성은 중앙 DSL로 하되 파이프라인 본문은 서비스 Jenkinsfile에 두고, 공통 단계는 Shared Library로 공유하는 식입니다.

---

## 6. Script Security: 임의 Groovy가 위험한 이유

이 모든 계층이 Groovy라는 점은 보안 관점을 함께 요구합니다. Jenkins에서 임의 Groovy 실행은 임의 코드 실행과 같습니다. Script Security 플러그인이 이를 통제합니다.

파이프라인 스크립트는 기본적으로 Groovy 샌드박스에서 실행됩니다. 화이트리스트에 없는 메서드 호출은 관리자 승인을 기다립니다. In-process Script Approval 화면에서 서명별로 승인하면 그제야 실행됩니다. 샌드박스를 아예 끄는 것도 가능하지만, 그 경우 스크립트 전문을 관리자가 검토하고 승인해야 합니다.

Shared Library의 trusted 등급은 이 체계의 일부입니다. 신뢰 라이브러리는 샌드박스 밖에서 실행되므로, 라이브러리 리포지토리의 쓰기 권한이 곧 강력한 권한이라는 점을 인식하고 관리해야 합니다.

---

## 7. Reference

- [Jenkins Docs - Pipeline Syntax](https://www.jenkins.io/doc/book/pipeline/syntax/)
- [Jenkins Docs - Using a Jenkinsfile](https://www.jenkins.io/doc/book/pipeline/using-jenkinsfile/)
- [Jenkins Docs - Branches and Pull Requests](https://www.jenkins.io/doc/book/pipeline/multibranch/)
- [Jenkins Docs - Shared Libraries](https://www.jenkins.io/doc/book/pipeline/shared-libraries/)
- [Jenkins Docs - Pipeline Steps](https://www.jenkins.io/doc/pipeline/steps/)
- [Jenkins Docs - Securing Jenkins](https://www.jenkins.io/doc/book/security/)
- [Jenkins Docs - In-process Script Approval](https://www.jenkins.io/doc/book/managing/script-approval/)
- [Job DSL Plugin Wiki](https://github.com/jenkinsci/job-dsl-plugin/wiki)
- [Job DSL Plugin - Script Security](https://github.com/jenkinsci/job-dsl-plugin/wiki/Script-Security)
- [Job DSL API Viewer](https://jenkinsci.github.io/job-dsl-plugin/)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
