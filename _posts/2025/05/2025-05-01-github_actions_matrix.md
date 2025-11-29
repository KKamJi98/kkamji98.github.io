---
title: GitHub Actions Matrix Strategy & Multi Architecture Build
date: 2025-05-01 22:21:01 +0900
author: kkamji
categories: [CI/CD, GitHub Actions]
tags: [github-actions, git, github, action, matrix, runner, buildx, ecr, multi-architecture, multi-platform, docker]
comments: true
image:
  path: /assets/img/github/github.webp
---

지난 글([GitHub Actions 소개 및 구성 요소]({% post_url 2025/04/2025-04-27-github_actions_basic %}))에서 **GitHub Actions의 기본 개념과 구성 요소**에 대해 살펴보았습니다. 이번에는 **Matrix Strategy**라는 기능에 대해 알아보고 해당 기능을 활용해 여러 플랫폼 또는 환경에서 병렬로 작업을 수행하여 CI/CD 파이프라인의 성능을 향상시키는 방법에 대해 알아보도록 하겠습니다.

---

## 1. Matrix Strategy란?

**GitHub Actions**의 **Matrix Strategy**는 동일한 작업(**Job**)을 다양한 환경이나 변수의 조합으로 병렬 실행할 때 사용됩니다. 예를 들어 여러 운영체제(OS)나 아키텍처(arm64, amd64) 환경에서 병렬적으로 테스트하거나 빌드할 수 있습니다. 이를 통해 여러 잡을 순차적으로 진행하거나 하나의 아키텍처에서 QEMU를 사용해 Multi-Architecture Build를 수행하는 방식보다 전체 워크플로우의 수행 시간을 크게 단축시킬 수 있습니다.

### 1.1. 언제 유용할까?

- Cross‑Platform 테스트: macOS, Windows, Linux 전부 지원해야 할 때.
- 멀티 아키텍처 빌드: x86과 ARM 이미지를 동시에 만들어야 할 때.
- 다양한 언어/버전 검증: Node.js 18/20처럼 여러 런타임 버전을 테스트할 때.

---

## 2. PoC - Matrix 전략을 사용한 병렬 빌드 성능 비교

amd64와 arm64 이미지를 빌드 해 ECR에 Push하는 Workflow를 **Matrix Strategy**를 사용하지 않고, 하나의 러너(amd64)에서 진행했을 때와, **Matrix Strategy**를 사용해 두 개의 러너에서 병렬로 진행했을 때 빌드 시간을 비교해보며 PoC를 진행했습니다.

> **비교 대상**  
> - 단일 러너(amd64)에서 QEMU 에뮬레이션으로 멀티 아키텍처 빌드.  
> - Matrix Strategy로 amd64·arm64 전용 러너에서 네이티브 빌드 후 Manifest 병합.  
{: .prompt-info}

[GitHub Repository Link](https://github.com/KKamJi98/github-actions/tree/main/.github/workflows)

> **[Environment]**  
> OS                  - Ubuntu 24.04 (amd64, arm64)  
> Language            - Go  
> Framework           - Gin-Gonic  
> Build-Tool          - Docker Buildx  
> Virtual Environment - QEMU  
> Container Registry  - ECR(Elastic Container Registry)  
{: .prompt-tip}

### 2.1. Workflow - 단일 러너(amd64), Build & Push Multi-Arch Using QEMU to ECR

```yaml
# .github/workflows/go-multi-architecture-build.yaml
name: "[Go] Gin Project Build & Push Multi-Arch Using QEMU to ECR"

# main 브랜치의 go path에 푸시될 때 실행
on:
  push:
    paths:
      - go/**
    branches:
      - main
  workflow_dispatch:

# OIDC를 이용해 AWS 역할을 가져오기 위해 id-token 권한 필요
permissions:
  contents: read
  id-token: write

jobs:
  build-and-push:
    name: Build & Push to ECR
    runs-on: ubuntu-24.04

    steps:
      # 1. 코드 체크아웃
      - name: Checkout code
        uses: actions/checkout@v3

      # 2. QEMU 에뮬레이션 등록 (Multi Architecture, Buildx 사용 시 필요)
      - name: Set up QEMU
        uses: docker/setup-qemu-action@v3

      # 3. Buildx 빌더 세팅
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      # 4. AWS 자격 증명 구성 (OIDC 방식)
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v2
        with:
          role-to-assume: ${{ secrets.AWS_ROLE_TO_ASSUME_ARN }}
          aws-region:    ${{ secrets.AWS_REGION }}

      # 5. ECR 로그인
      - name: Login to Amazon ECR
        id: login-ecr
        run: |
          aws ecr get-login-password \
            --region ${{ secrets.AWS_REGION }} \
          | docker login \
            --username AWS \
            --password-stdin ${{ secrets.AWS_ACCOUNT_ID }}.dkr.ecr.${{ secrets.AWS_REGION }}.amazonaws.com

      # 6. 멀티 아키텍처 이미지 빌드 & 푸시
      - name: Build and push multi-arch image
        uses: docker/build-push-action@v5
        with:
          context: ./go
          file: ./go/Dockerfile
          platforms: linux/amd64,linux/arm64
          push: true
          tags: |
            ${{ secrets.AWS_ACCOUNT_ID }}.dkr.ecr.${{ secrets.AWS_REGION }}.amazonaws.com/${{ secrets.ECR_REPOSITORY }}:latest
            ${{ secrets.AWS_ACCOUNT_ID }}.dkr.ecr.${{ secrets.AWS_REGION }}.amazonaws.com/${{ secrets.ECR_REPOSITORY }}:${{ github.sha }}
```

### 2.2. 결과 확인 - 단일 러너(amd64), Build & Push Multi-Arch Using QEMU to ECR

Container Image 빌드 및 ECR Push 등 전체 Workflow가 완료되기까지 총 4분 57초가 소요되었습니다.

![Multi-Architecture-Build-Using-QEMU](/assets/img/github/multi-architecture-build-using-qemu-result.png)

자세히 확인해보니 amd64 아키텍처 빌드는 25.8초가 걸린 반면, arm64 아키텍처 빌드는 무려 241.4초가 걸려 약 9배 이상의 차이가 있었습니다.

```shell
#16 [linux/amd64 builder 6/6] RUN CGO_ENABLED=0     GOOS=${TARGETOS}     GOARCH=${TARGETARCH}     go build -ldflags="-s -w" -o server .
#16 DONE 25.8s

#19 [linux/amd64 stage-1 1/1] COPY --from=builder /app/server /server
#19 DONE 0.0s

#18 [linux/arm64 builder 6/6] RUN CGO_ENABLED=0     GOOS=${TARGETOS}     GOARCH=${TARGETARCH}     go build -ldflags="-s -w" -o server .
#18 DONE 241.4s

#20 [linux/arm64 stage-1 1/1] COPY --from=builder /app/server /server
#20 DONE 0.0s
```

#### 2.2.1. QEMU 사용 시 빌드 속도가 느린 이유

**QEMU**를 사용한 **Multi-Architecture Build** 방식은 다른 아키텍처의 바이너리를 에뮬레이션하여 실행하기 때문에 **Native** 환경에서 빌드하는 것보다 성능이 크게 저하됩니다. 특히 ARM64 바이너리를 AMD64 환경에서 에뮬레이션할 때 CPU 명령어 및 메모리 처리 속도가 현저히 낮아져 빌드 시간이 대폭 증가합니다.

<https://docs.docker.com/build/building/multi-platform/#qemu>

### 2.3. Workflow - 다중 러너(amd64, arm64), Build & Push Multi-Arch Using Matrix to ECR

```yaml
name: "[Go] Gin Project Build & Push Multi-Arch Using Matrix to ECR"

on:
  push:
    paths:
      - go/**
  workflow_dispatch:

permissions:
  contents: read
  id-token: write

jobs:
  # ──────────────────────────────────────────────────────────────
  # 1) 아키텍처별 이미지 Build & Push
  # ──────────────────────────────────────────────────────────────
  build-and-push:
    name: Build & Push (${{ matrix.arch }})
    strategy:
      matrix:
        include:
          # AMD64용 러너
          - arch: amd64
            runner: ubuntu-24.04
          # ARM64용 러너
          - arch: arm64
            runner: ubuntu-24.04-arm
    runs-on: ${{ matrix.runner }}

    steps:
      - name: Checkout code
        uses: actions/checkout@v3

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Configure AWS credentials (OIDC)
        uses: aws-actions/configure-aws-credentials@v2
        with:
          role-to-assume: ${{ secrets.AWS_ROLE_TO_ASSUME_ARN }}
          aws-region:    ${{ secrets.AWS_REGION }}

      - name: Login to Amazon ECR
        run: |
          aws ecr get-login-password --region ${{ secrets.AWS_REGION }} \
          | docker login --username AWS --password-stdin \
            ${{ secrets.AWS_ACCOUNT_ID }}.dkr.ecr.${{ secrets.AWS_REGION }}.amazonaws.com
            # 0. 이번 실행의 **버전 번호(0-base)** 계산
      
      # 버전 태그 설정
      - name: Set version tag
        id: ver
        run: echo "VER=$((GITHUB_RUN_NUMBER-1))" >> "$GITHUB_OUTPUT"

      # 아키텍처별 단일 이미지 빌드 & 푸시
      - name: Build & push image (${{ matrix.arch }})
        uses: docker/build-push-action@v5
        with:
          context: ./go
          file:    ./go/Dockerfile
          platforms: linux/${{ matrix.arch }} # Native 단일 플랫폼 빌드
          push: true
          tags: |
            ${{ secrets.AWS_ACCOUNT_ID }}.dkr.ecr.${{ secrets.AWS_REGION }}.amazonaws.com/${{ secrets.ECR_REPOSITORY }}:${{ matrix.arch }}-v${{ steps.ver.outputs.VER }}
          
  # ──────────────────────────────────────────────────────────────
  # 2) 다중 아키텍처 Manifest 생성
  # ──────────────────────────────────────────────────────────────
  create-manifest:
    name: Create & Push Multi-Arch Manifest
    needs: build-and-push
    runs-on: ubuntu-24.04   # manifest 작업은 아무 러너에서나 가능 (x64 사용 예시)

    steps:
      - name: Set version tag
        id: ver
        run: echo "VER=$((GITHUB_RUN_NUMBER-1))" >> "$GITHUB_OUTPUT"
        
      - name: Configure AWS credentials (OIDC)
        uses: aws-actions/configure-aws-credentials@v2
        with:
          role-to-assume: ${{ secrets.AWS_ROLE_TO_ASSUME_ARN }}
          aws-region:    ${{ secrets.AWS_REGION }}

      - name: Login to Amazon ECR
        run: |
          aws ecr get-login-password --region ${{ secrets.AWS_REGION }} \
          | docker login --username AWS --password-stdin \
            ${{ secrets.AWS_ACCOUNT_ID }}.dkr.ecr.${{ secrets.AWS_REGION }}.amazonaws.com

      - name: Create & push multi-arch manifest
        run: |
          IMAGE=${{ secrets.AWS_ACCOUNT_ID }}.dkr.ecr.${{ secrets.AWS_REGION }}.amazonaws.com/${{ secrets.ECR_REPOSITORY }}
          VER=${{ steps.ver.outputs.VER }}

          docker buildx imagetools create \
            --tag $IMAGE:latest \
            --tag $IMAGE:v$VER \
            $IMAGE:amd64-v$VER \
            $IMAGE:arm64-v$VER
```

### 2.4. 결과 확인 - 다중 러너(amd64, arm64), Build & Push Multi-Arch Using Matrix to ECR

![Multi-Architecture-Build-Using-Matrix](/assets/img/github/multi-architecture-build-using-matrix-result.png)

단일 러너(amd64)에서 Multi-Architecture Build 하는 Workflow를 실행했을 때 **4분 57초**가 소요된 반면, **Matrix Strategy**를 사용해 다중 러너(amd64, arm64)에서 각각 **Native**하게 빌드 했을 때, 각각의 Manifest를 합치는 Job이 추가되었음에도 불구하고 Workflow 실행 시간이 **1분 32초** 밖에 소요되지 않았습니다. 결과적으로 약 70%정도 빌드 시간을 단축시킬 수 있었습니다.

---

## 3. 마무리

GitHub Actions의 Matrix Strategy를 활용하면 Multi-Architecture, Multi-Platform 빌드가 포함된 워크플로우의 **실행 시간을 효과적으로 단축**할 수 있습니다.  
Multi-Architecture 또는 Multi-Platform을 지원하는 컨테이너 이미지를 사용하거나, 꼭 순차적으로 실행되어야하지 않아도 되는 OS 및 패키지 조합별 취약점 스캔 등의 시간을 줄이고자 할 때 **도입을 고려해보는건 어떨까요?**.

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
