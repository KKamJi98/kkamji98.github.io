---
title: GitHub Actions 소개 및 구성 요소
date: 2025-04-27 23:01:05 +0900
author: kkamji
categories: [CI/CD, GitHub Actions]
tags: [github-actions, git, github, action, workflow, event, job, step, runner]
comments: true
image:
  path: /assets/img/github/github.webp
---

**GitHub Actions**는 GitHub Repository 내에서 **CI/CD 파이프라인**과 다양한 자동화 작업을 쉽게 구축할 수 있도록 도와주는 도구입니다. 기존에는 Jenkins와 같은 별도의 CI 서버를 설치하고 웹훅(Webhook)을 연동해야 했지만, **GitHub Actions**는 소스 코드와 동일한 Repository 내의 특정 디렉토리에 YAML 파일로 정의한 Workflow를 추가하는 것만으로도 빌드, 테스트, 배포 등 일련의 작업을 자동화할 수 있습니다.

특히, **GitHub Actions**는 GitHub와 깊게 통합되어 있어 Push, Pull Request 생성, Issue 등록 등의 GitHub 이벤트를 트리거로 삼아 Workflow를 실행할 수 있습니다. **Workflow**는 여러 개의 Job으로 구성되며, 각 **Job**은 다시 개별적인 **Step**들로 구성됩니다. **Step**은 하나 이상의 **Action**이나 **run**을 실행하며, Actions는 GitHub Marketplace에서 손쉽게 가져다 쓸 수 있는 다양한 미리 정의된 작업 단위입니다.

실행 환경을 제공하는 Runner는 GitHub에서 기본적으로 제공하는 가상 머신을 사용할 수도 있고, 필요에 따라 조직의 내부 인프라에 직접 설치하여(Self-Hosted Runner) 사용할 수도 있습니다. 이를 통해 별도의 서버 구축 없이도 손쉽게 안정적인 CI/CD 환경을 운영할 수 있는 것이 **GitHub Actions**의 큰 장점입니다.

---

## GitHub Actions의 주요 이점

### 설정 간소화

저장소에 **YAML** 파일 하나로 CI/CD 파이프라인 설정이 가능하며, 별도의 서버 관리나 웹훅 설정이 불필요합니다. 하드웨어 준비나 보안 패치와 같은 유지보수를 신경 쓸 필요 없이, **GitHub**에서 제공하는 **Hosted Runner**를 그대로 활용할 수 있습니다.

### 이벤트 기반 트리거

**GitHub**과 완전히 통합되어 커밋 푸시, 풀 리퀘스트 생성, 이슈 등록 등 GitHub 이벤트에 자동으로 응답하여 워크플로우를 실행할 수 있습니다. 예를 들어, "커밋이 푸시되면 자동으로 빌드와 테스트를 실행하거나, 릴리스 태그가 생성되면 자동 배포를 수행하고, 새로운 이슈가 생성되면 자동으로 라벨을 붙이는" 등의 작업을 **GitHub Actions** 워크플로우로 손쉽게 구현할 수 있습니다.

### 풍부한 액션 생태계

수천 개가 넘는 커뮤니티 액션들이 **GitHub Marketplace**에 공개되어 있어, 이를 워크플로우에 가져다 써서 손쉽게 기능을 구현할 수 있습니다. 예를 들어 코드 체크아웃, 특정 언어 환경 세팅, 클라우드 배포 등 흔한 작업들은 검증된 액션을 사용해 간단히 수행할 수 있고, 직접 커스텀 액션을 만들어 사용할 수도 있습니다.

### 다양한 플랫폼 지원

리눅스(Ubuntu), 윈도우, macOS 등 다양한 OS 환경과 언어, 클라우드에 구애받지 않고 동작합니다. 필요에 따라 자체 호스팅 러너를 연결해 특정 하드웨어나 OS에서 작업을 실행할 수도 있습니다.

> 위와 같은 장점으로 인해 **GitHub Actions**는 인기있는 CI/CD 도구로 자리 잡았습니다.  
> 실제로 **GitHub Actions** 워크플로우를 통해 커밋이 푸시되면 자동으로 빌드/테스트를 돌리고, 릴리스 태그가 생성되면 배포를 수행하며, 새로운 이슈가 열리면 라벨을 붙이는 등의 작업을 설정할 수 있습니다
{: .prompt-tip}

---

## GitHub Actions의 구성 요소

![GitHub Actions Component](/assets/img/github/github_actions_component.webp)

### 워크플로우 (Workflow)

하나 이상의 잡(Job)으로 구성된 자동화 프로세스입니다. 저장소 내 `.github/workflows` 디렉터리에 **YAML** 파일로 정의되며, 저장소에서 특정 이벤트가 발생하면 트리거되어 실행됩니다. 예를 들어 “코드 푸시 시 테스트 수행”이나 “릴리스 생성 시 배포”와 같은 작업 흐름을 워크플로우로 작성할 수 있습니다.

### 이벤트 (Event)

워크플로우 실행을 트리거하는 **GitHub** 활동을 의미합니다. 푸시(push), 풀 리퀘스트 열림/병합, 이슈 생성, 일정(cron) 등 다양한 이벤트를 감지하여 해당 워크플로우가 시작됩니다. 이벤트 정의에 따라 워크플로우가 자동으로 필요한 시점에 실행됩니다.

### 잡 (Job)

워크플로우를 구성하는 개별 작업 단위입니다. 각 잡은 병렬 또는 순차적으로 실행될 수 있으며, 하나의 잡 안에서는 여러 스텝(step)이 순서대로 실행됩니다. 기본적으로 잡들은 서로 독립적으로 병렬 실행되지만, needs 키워드를 통해 특정 잡이 다른 잡의 완료를 기다리도록 의존성을 설정할 수도 있습니다. 또한 각각의 잡은 격리된 자체 가상환경(러너)에서 실행되므로, 잡 간에는 파일시스템이나 환경이 공유되지 않습니다.

### 스텝 (Step)

잡 내부에서 순차적으로 수행되는 단계를 뜻합니다. 각 스텝은 실제로 실행될 단일 작업을 나타내며, 쉘 스크립트 명령을 직접 실행하거나 또는 **액션(Action)**을 호출할 수 있습니다. 모든 스텝은 정의된 순서대로 동일한 러너 환경 내에서 실행되기 때문에, 이전 스텝에서 생성된 산출물(예: 빌드 결과)을 다음 스텝에서 바로 활용할 수 있습니다.

### 액션 (Action)

재사용 가능한 작업 명령 세트로, 반복적으로 쓰이는 스크립트나 애플리케이션을 캡슐화한 것입니다. 예를 들어 코드 체크아웃, 특정 언어 환경 설정, 클라우드 인증 등 자주 쓰이는 작업들을 액션으로 만들어 두고 워크플로우의 스텝에서 호출해서 사용합니다. 액션은 GitHub Marketplace에서 공개된 것을 가져다 쓸 수도 있고, 필요하면 자신만의 커스텀 액션을 작성하여 사용할 수도 있습니다. 액션을 활용하면 복잡한 스크립트 내용을 숨기고 워크플로우 파일을 보다 간결하게 유지할 수 있습니다.

### 러너 (Runner)

잡을 실행하는 **호스트 머신**을 지칭합니다. 러너는 **GitHub Actions** 워크플로우가 실행될 때 할당되는 가상 머신 또는 컨테이너로, 각 잡은 격리된 러너 환경에서 수행됩니다. **GitHub**에서 **Ubuntu Linux**, **Windows**, **macOS** 러너를 기본 제공하며, 사용자는 호스트 러너의 이미지(runs-on)만 지정하면 됩니다. 매 워크플로우 실행마다 새로운 VM이 프로비저닝되므로 깨끗한 환경이 보장됩니다. 또한 고유한 요구 사항이 있을 경우 **자체 호스팅(self-hosted) 러너**를 등록하여 사용할 수도 있습니다.

> 이벤트 -> 워크플로우 -> 잡 -> 스텝/액션의 계층적인 구조로 서로 연결됩니다. 즉, 특정 이벤트가 발생하면 대응하는 워크플로우가 시작되고, 그 안의 각 잡이 순서대로 혹은 병렬로 실행되며, 잡은 다시 여러 스텝으로 이루어져 차례차례 작업을 수행하게 됩니다.
{: .prompt-tip}

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKam.\_\.Ji](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
