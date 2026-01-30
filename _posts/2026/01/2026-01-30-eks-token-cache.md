---
title: EKS kubectl 토큰 캐싱으로 응답 속도 개선하기
date: 2026-01-30 12:00:00 +0900
author: kkamji
categories: [Kubernetes]
tags: [kubernetes, eks, kubectl, aws, token, cache, performance]
comments: true
image:
  path: /assets/img/kubernetes/kubernetes.webp
---

On-Premise와 연결된 Kubernetes Cluster를 사용하는 것과 EKS 환경에서 kubectl 명령어를 실행할 때 체감되는 지연 시간에 차이가 있어, aws eks update-kubeconfig로 가져온 클러스터 인증 정보를 통해 kubectl에 EKS Cluster에 접근하는 방법에 대해 알아봤습니다.
해당 지연 문제는 여러 클러스터를 오가며 작업하거나, 스크립트에서 kubectl을 반복 호출할 때 더욱 두드러지게 되며 이로 인해 소중한 시간을 빼앗기게 됩니다.
이번 포스트에서는 이 문제의 원인을 파악하고, 토큰 캐싱 스크립트를 통해 해결하는 방법을 다뤄보겠습니다.

---

## 1. 문제 상황

### 1.1. kubeconfig exec 인증 방식

EKS 클러스터에 접근하기 위해 `aws eks update-kubeconfig` 명령으로 kubeconfig를 설정하면, 다음과 같은 exec 인증 방식이 구성됩니다.

```yaml
users:
  - name: arn:aws:eks:ap-northeast-2:123456789012:cluster/my-cluster
    user:
      exec:
        apiVersion: client.authentication.k8s.io/v1beta1
        command: aws
        args:
          - eks
          - get-token
          - --cluster-name
          - my-cluster
          - --region
          - ap-northeast-2
```

이 설정은 **kubectl 명령을 실행할 때마다** `aws eks get-token`을 호출하여 Bearer 토큰을 발급받습니다.

### 1.2. 발생하는 문제점

매번 토큰을 새로 발급받는 방식은 다음과 같은 문제를 야기합니다.

| 문제                   | 설명                                                  |
| ---------------------- | ----------------------------------------------------- |
| **응답 지연**          | 명령어마다 500ms~2초 이상의 추가 지연 발생            |
| **네트워크 의존성**    | 네트워크 불안정 시 타임아웃으로 명령 실패             |
| **API 호출 급증**      | 스크립트에서 kubectl 반복 호출 시 AWS API 호출량 급증 |
| **Rate Limiting 위험** | 대량 호출 시 AWS API Rate Limit에 도달할 가능성       |

실제로 간단한 `kubectl get nodes` 명령도 토큰 발급 시간이 포함되어 체감 속도가 느려집니다.

```bash
# 토큰 발급 시간 포함
❯ time kubectl get nodes
NAME                                              STATUS   ROLES    AGE   VERSION
ip-10-0-1-100.ap-northeast-2.compute.internal     Ready    <none>   5h   v1.33.0-eks-xxxxx

real    0m1.847s
user    0m0.523s
sys     0m0.089s
```

---

## 2. 해결 방안 - 토큰 캐싱 전략

### 2.1. 핵심 아이디어

EKS 토큰은 **발급 후 15분간 유효**합니다. 이 특성을 활용하면 다음과 같은 캐싱 전략을 적용할 수 있습니다.

1. 토큰을 파일에 캐싱
2. kubectl 호출 시 캐시된 토큰의 유효성 확인
3. 유효하면 캐시 사용, 만료 임박 시 새로 발급
4. 만료 60초 전에 미리 갱신하여 안전 마진 확보

### 2.2. 토큰 구조

`aws eks get-token` 명령의 출력은 다음과 같은 JSON 구조입니다.

```json
{
  "kind": "ExecCredential",
  "apiVersion": "client.authentication.k8s.io/v1beta1",
  "spec": {},
  "status": {
    "expirationTimestamp": "2026-01-30T12:15:00Z",
    "token": "k8s-aws-v1.aHR0cHM6Ly9zdHMuYX..."
  }
}
```

`status.expirationTimestamp` 필드를 파싱하여 토큰 만료 시간을 확인할 수 있습니다.

---

## 3. 토큰 캐싱 스크립트

### 3.1. 스크립트 전체 코드

다음 스크립트를 `~/.kube/eks-token-cache.sh`로 저장합니다.

```bash
#!/bin/bash
set -euo pipefail

# 사용법: eks-token-cache.sh <cluster-name> <region> [profile]
CLUSTER_NAME="${1:?cluster name required}"
REGION="${2:?region required}"
PROFILE="${3:-default}"

# 캐시 디렉토리 설정
CACHE_DIR="${HOME}/.kube/eks-token-cache"
mkdir -p "$CACHE_DIR"
chmod 700 "$CACHE_DIR"

# 캐시 파일명: 클러스터명 + 프로파일 조합으로 고유 키 생성
CACHE_KEY="${CLUSTER_NAME}_${PROFILE}"
CACHE_FILE="${CACHE_DIR}/${CACHE_KEY}.json"

# Safety Margin: 만료 60초 전에 갱신
SAFETY_MARGIN=60

# 디버그 모드 (EKS_TOKEN_DEBUG=1 설정 시 활성화)
debug() {
    if [[ "${EKS_TOKEN_DEBUG:-0}" == "1" ]]; then
        echo "[DEBUG] $*" >&2
    fi
}

# 현재 시간을 Unix timestamp로 반환 (macOS/Linux 호환)
get_current_timestamp() {
    if [[ "$(uname)" == "Darwin" ]]; then
        date +%s
    else
        date +%s
    fi
}

# ISO 8601 시간을 Unix timestamp로 변환 (macOS/Linux 호환)
parse_timestamp() {
    local iso_time="$1"
    if [[ "$(uname)" == "Darwin" ]]; then
        # macOS: GNU date가 없으면 Python 사용
        if command -v gdate &>/dev/null; then
            gdate -d "$iso_time" +%s
        else
            python3 -c "from datetime import datetime; print(int(datetime.fromisoformat('${iso_time}'.replace('Z', '+00:00')).timestamp()))"
        fi
    else
        # Linux
        date -d "$iso_time" +%s
    fi
}

# 캐시 유효성 검증
is_cache_valid() {
    if [[ ! -f "$CACHE_FILE" ]]; then
        debug "Cache file not found"
        return 1
    fi

    # jq로 expirationTimestamp 추출
    local exp_time
    exp_time=$(jq -r '.status.expirationTimestamp // empty' "$CACHE_FILE" 2>/dev/null)

    if [[ -z "$exp_time" ]]; then
        debug "Invalid cache format"
        return 1
    fi

    local exp_ts current_ts
    exp_ts=$(parse_timestamp "$exp_time")
    current_ts=$(get_current_timestamp)

    # 만료 시간에서 Safety Margin을 뺀 값과 현재 시간 비교
    local valid_until=$((exp_ts - SAFETY_MARGIN))

    if [[ $current_ts -lt $valid_until ]]; then
        local remaining=$((valid_until - current_ts))
        debug "Cache valid, ${remaining}s remaining"
        return 0
    else
        debug "Cache expired or expiring soon"
        return 1
    fi
}

# 새 토큰 발급 및 캐싱
refresh_token() {
    debug "Fetching new token from AWS"
    local token_json

    if [[ "$PROFILE" == "default" ]]; then
        token_json=$(aws eks get-token --cluster-name "$CLUSTER_NAME" --region "$REGION")
    else
        token_json=$(aws eks get-token --cluster-name "$CLUSTER_NAME" --region "$REGION" --profile "$PROFILE")
    fi

    echo "$token_json" > "$CACHE_FILE"
    chmod 600 "$CACHE_FILE"
    echo "$token_json"
}

# 메인 로직
main() {
    if is_cache_valid; then
        debug "Using cached token"
        cat "$CACHE_FILE"
    else
        refresh_token
    fi
}

main
```

### 3.2. 스크립트 주요 구성 요소

| 구성 요소            | 설명                                                 |
| -------------------- | ---------------------------------------------------- |
| **인자 처리**        | 클러스터명(필수), 리전(필수), AWS 프로파일(선택)     |
| **캐시 키 생성**     | `클러스터명_프로파일` 조합으로 고유한 캐시 파일 생성 |
| **유효성 검증**      | jq로 expirationTimestamp 파싱 후 현재 시간과 비교    |
| **Safety Margin**    | 만료 60초 전 자동 갱신으로 토큰 만료 방지            |
| **macOS/Linux 호환** | 시간 파싱 시 OS별 분기 처리                          |
| **디버그 모드**      | `EKS_TOKEN_DEBUG=1` 환경변수로 상세 로그 출력        |

---

## 4. 적용 방법

### 4.1. 스크립트 설치

```bash
# 스크립트 저장
mkdir -p ~/.kube
cat > ~/.kube/eks-token-cache.sh << 'EOF'
# 위 스크립트 내용 붙여넣기
EOF

# 실행 권한 부여
chmod +x ~/.kube/eks-token-cache.sh

# jq 설치 확인 (필수 의존성)
which jq || brew install jq  # macOS
# which jq || sudo apt install jq  # Ubuntu/Debian
```

### 4.2. kubeconfig 수정

기존 kubeconfig의 exec 설정을 캐싱 스크립트로 변경합니다.

```yaml
# 변경 전 (기본 exec)
users:
- name: arn:aws:eks:ap-northeast-2:123456789012:cluster/my-cluster
  user:
    exec:
      apiVersion: client.authentication.k8s.io/v1beta1
      command: aws
      args:
        - eks
        - get-token
        - --cluster-name
        - my-cluster
        - --region
        - ap-northeast-2

# 변경 후 (캐싱 적용)
users:
- name: arn:aws:eks:ap-northeast-2:123456789012:cluster/my-cluster
  user:
    exec:
      apiVersion: client.authentication.k8s.io/v1beta1
      command: /Users/username/.kube/eks-token-cache.sh
      args:
        - my-cluster
        - ap-northeast-2
        - default  # AWS 프로파일 (선택)
      interactiveMode: Never
```

> `interactiveMode: Never`를 추가하면 토큰 발급 시 프롬프트가 표시되지 않습니다.
> {: .prompt-tip}

---

## 5. 성능 비교

### 5.1. 캐싱 전후 응답 시간 비교

**캐싱 적용 전 (매번 토큰 발급)**

```bash
❯ time kubectl get nodes
NAME                                              STATUS   ROLES    AGE   VERSION
ip-10-0-1-100.ap-northeast-2.compute.internal     Ready    <none>   30d   v1.29.0-eks

real    0m1.847s
user    0m0.523s
sys     0m0.089s
```

**캐싱 적용 후 (캐시 히트)**

```bash
❯ time kubectl get nodes
NAME                                              STATUS   ROLES    AGE   VERSION
ip-10-0-1-100.ap-northeast-2.compute.internal     Ready    <none>   30d   v1.29.0-eks

real    0m0.312s
user    0m0.098s
sys     0m0.045s
```

**약 83% 응답 시간 감소** (1.847s → 0.312s)

### 5.2. 디버그 모드로 동작 확인

```bash
# 디버그 모드 활성화
export EKS_TOKEN_DEBUG=1

# 첫 번째 호출 (캐시 미스 → 새 토큰 발급)
❯ kubectl get nodes
[DEBUG] Cache file not found
[DEBUG] Fetching new token from AWS
NAME                                              STATUS   ROLES    AGE   VERSION
...

# 두 번째 호출 (캐시 히트)
❯ kubectl get nodes
[DEBUG] Cache valid, 847s remaining
[DEBUG] Using cached token
NAME                                              STATUS   ROLES    AGE   VERSION
...
```

---

## 6. 주의사항 및 팁

### 6.1. 의존성

- **jq**: JSON 파싱을 위해 필수로 설치되어 있어야 합니다
- **Python3**: macOS에서 GNU date가 없는 경우 시간 파싱에 사용됩니다

### 6.2. 보안

- 캐시 디렉토리는 `700` 권한으로 생성되어 소유자만 접근 가능합니다
- 캐시 파일은 `600` 권한으로 저장됩니다
- 토큰은 15분간만 유효하므로 유출되어도 피해가 제한적입니다

### 6.3. 멀티 클러스터 / 멀티 프로파일

- 클러스터명과 프로파일 조합으로 캐시 키가 생성되어 충돌이 발생하지 않습니다
- 여러 클러스터를 오가며 작업해도 각각 독립적으로 캐싱됩니다

```bash
# 캐시 파일 확인
❯ ls ~/.kube/eks-token-cache/
my-cluster_default.json
prod-cluster_prod-profile.json
staging-cluster_default.json
```

### 6.4. 캐시 강제 갱신

토큰을 강제로 갱신하려면 캐시 파일을 삭제하면 됩니다.

```bash
# 특정 클러스터 캐시 삭제
rm ~/.kube/eks-token-cache/my-cluster_default.json

# 전체 캐시 삭제
rm -rf ~/.kube/eks-token-cache/
```

---

## 7. Reference

- [AWS Docs - AWS CLI EKS get-token](https://docs.aws.amazon.com/cli/latest/reference/eks/get-token.html)
- [AWS Docs - Learn how access control works in Amazon EKS](https://docs.aws.amazon.com/eks/latest/userguide/cluster-auth.html)
- [AWS Docs - Grant Kubernetes workloads access to AWS using Kubernetes Service Accounts](https://docs.aws.amazon.com/eks/latest/userguide/service-accounts.html)
- [Kubernetes Docs - Authenticating(client-go-credential-plugins)](https://kubernetes.io/docs/reference/access-authn-authz/authentication/#client-go-credential-plugins)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**
> {: .prompt-info}
