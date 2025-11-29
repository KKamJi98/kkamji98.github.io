---
title: EKS Pod Identity 개념, PoC
date: 2025-04-16 22:49:55 +0900
author: kkamji
categories: [Kubernetes]
tags: [kubernetes, eks, irsa, pod-identity, iam]
comments: true
image:
  path: /assets/img/kubernetes/kubernetes.webp
---

지난 글([IRSA (IAM Role for Service Account)란? 사용 방법]({% post_url 2024/07/2024-07-17-irsa %}))에서 **IRSA**를 통해 AWS 리소스 권한을 위임하는 방법을 설명했었습니다. **Amazon EKS Pod Identity**는 Pod 단위로 IAM 자격 증명을 제공하는 새로운 기능입니다. 기존 **IRSA**(IAM Role for Service Account)에서는 OIDC Provider 설정과 클러스터별 신뢰 정책 관리가 필수였지만, **Pod Identity**에서는 이를 없애 배포와 운영이 훨씬 간단해졌습니다.

**Pod Identity**를 사용하려면 신뢰 주체가 `pods.eks.amazonaws.com`인 IAM Role을 만들고, Service Account(SA)와 1:1로 연결(Association)하면 끝입니다. EKS Auth API가 Role을 한 번만 Assume하고, 각 노드에 설치된 Pod Identity Agent가 Pod에 임시 자격 증명을 전달하기 때문에 STS 호출 수가 크게 줄어들어 대규모 클러스터에서도 안정적으로 동작합니다.

| 구분      | IRSA                                               | Pod Identity                                    |
| --------- | -------------------------------------------------- | ----------------------------------------------- |
| 신뢰 주체 | `oidc.eks.<cluster‑id>.amazonaws.com` (클러스터별) | `pods.eks.amazonaws.com` (계정 전체 재사용)     |
| 필수 구성 | OIDC Provider, SA Annotation                       | Pod Identity Agent(add‑on)                      |
| STS 호출  | Pod 내 SDK가 직접 `AssumeRoleWithWebIdentity` 사용 | EKS Auth API가 노드당 1회 호출                  |
| 장점      | 클라우드 네이티브, Fargate 지원                    | 구성 간소화, 대규모 성능, Role Session Tag 지원 |
| 제약      | OIDC Provider 관리 필요                            | Linux EC2 노드만 지원, SA당 Role 1개            |

---

## 1. Pod Identity 장점, 단점

### 1.1. 장점

**단일 신뢰 주체**: 모든 클러스터에서 `pods.eks.amazonaws.com`만 지정하면 되기 때문에 IAM Role 재사용이 쉬워졌습니다.  
**운영 분리**: IAM Role 관리자는 IAM만, 클러스터 관리자는 EKS만 관리하면 됩니다. OIDC Provider 생성 권한이 없어도 되기 때문에 권한 위임 체계가 분리됩니다.  
**확장성**: STS를 Pod마다 호출하지 않고 노드당 1회 호출하여, 대규모 배치나 ML 워크로드에도 안정적입니다.  
**추가 기능**: Role Session Tag, EKS 콘솔 내 권한 제안(Suggested Policy) 기능 등 운영 및 감사 측면에서도 유용합니다.  

### 1.2. 단점

**지원 제한**: 현재는 Linux EC2 노드에서만 사용 가능하며, Fargate나 Windows는 지원되지 않습니다.  
**Agent 필요**: 모든 노드에 eks-pod-identity-agent DaemonSet이 설치되어 있어야 합니다.  

---

## 2. Pod Identity 동작 원리

![pod-identity-workflow]({{ "/assets/img/kubernetes/pod-identity-workflow.jpg" | relative_url }})

1. 서비스 어카운트와 IAM Role을 연결하는 SA-Role Association을 만들면, ***EKS Auth API**가 이 정보를 메타데이터로 저장합니다.
2. Pod가 연결된 SA를 사용해 배포되면, **EKS API가 자동으로 Pod Manifest에 다음 두 환경 변수(ENV)**를 삽입하고 Credential 볼륨을 생성
   - `AWS_CONTAINER_CREDENTIALS_FULL_URI`: Pod에 연결된 IAM Role ARN
   - `AWS_CONTAINER_AUTHORIZATION_TOKEN_FILE`: Pod에 연결된 IAM Role의 OIDC 토큰 파일 경로
3. 각 노드의 Pod Identity Agent가 AssumeRoleForPodIdentity API를 호출하여 얻은 임시 자격 증명을 로컬 엔드포인트에 저장
4. Pod 내부에서 실행되는 AWS SDK/CLI는 컨테이너 Credential Provider를 통해 이 로컬 엔드포인트에서 IAM 자격 증명을 안전하게 얻어 사용

> ***EKS Auth API**란?  
> EKS의 신규 API(AssumeRoleForPodIdentity 등)로, 토큰 검증 및 임시 자격 증명 발급을 담당
{: .prompt-tip}

---

## 3. Pod Identity PoC(Proof of Concept)

### 3.1. pod-identity-agent 설치

EKS 콘솔에서 Add-on을 설치하거나 CLI를 통해 eks-pod-identity-agent DaemonSet을 설치합니다.

```bash
❯ aws eks create-addon \
  --cluster-name kkamji-al2023 \
  --addon-name eks-pod-identity-agent

❯ k get ds -n kube-system eks-pod-identity-agent
NAME                     DESIRED   CURRENT   READY   UP-TO-DATE   AVAILABLE   NODE SELECTOR   AGE
eks-pod-identity-agent   2         2         2       2            2           <none>          111s
```

### 3.2. IAM Policy 생성

테스트를 위해 S3에 접근할 수 있는 IAM Policy를 생성합니다.  

```bash
❯ cat >pod-identity-s3-bucket-policy.json <<EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": "s3:ListBucket",
            "Resource": "arn:aws:s3:::kkamji-eks-pod-identity-test-bucket"
        }
    ]
}
EOF


❯ aws iam create-policy --policy-name pod-identity-s3-bucket-policy --policy-document file://pod-identity-s3-bucket-policy.json

## 결과
{
    "Policy": {
        "PolicyName": "pod-identity-s3-bucket-policy",
        "PolicyId": "ANPAVPEYWCKI7G4QD2STO",
        "Arn": "arn:aws:iam::111111111111:policy/pod-identity-s3-bucket-policy",
        "Path": "/",
        "DefaultVersionId": "v1",
        "AttachmentCount": 0,
        "PermissionsBoundaryUsageCount": 0,
        "IsAttachable": true,
        "CreateDate": "2025-04-16T18:14:25+00:00",
        "UpdateDate": "2025-04-16T18:14:25+00:00"
    }
}
```

### 3.3. IAM Role 생성

IAM Role을 생성하고, 위에서 만든 Policy를 연결합니다. 해당 Role은 Pod Identity Agent가 AssumeRoleForPodIdentity API를 호출할 때 사용됩니다.  

```bash
❯ cat >pod-identity-s3-bucket-role.json <<EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "AllowEksAuthToAssumeRoleForPodIdentity",
            "Effect": "Allow",
            "Principal": {
                "Service": "pods.eks.amazonaws.com"
            },
            "Action": [
                "sts:AssumeRole",
                "sts:TagSession"
            ]
        }
    ]
}
EOF

❯ aws iam create-role --role-name pod-identity-s3-bucket-role --assume-role-policy-document file://pod-identity-s3-bucket-role.json --description "pod identity role for pod identity s3 bucket access"
```

### 3.4. Service Account 생성

```bash
cat >kkamji-service-account.yaml <<EOF
apiVersion: v1
kind: ServiceAccount
metadata:
  name: kkamji-service-account
  namespace: default
EOF

kubectl apply -f kkamji-service-account.yaml

```

### 3.5. Service Account와 IAM Role 연결 (pod-identity-association)

```bash
❯ aws eks create-pod-identity-association --cluster-name kkamji-al2023 --role-arn arn:aws:iam::111111111111:role/pod-identity-s3-bucket-role --namespace default --service-account kkamji-service-account

# 확인
{
    "association": {
        "clusterName": "kkamji-al2023",
        "namespace": "default",
        "serviceAccount": "kkamji-service-account",
        "roleArn": "arn:aws:iam::111111111111:role/pod-identity-s3-bucket-role",
        "associationArn": "arn:aws:eks:ap-northeast-2:111111111111:podidentityassociation/kkamji-al2023/a-z8rmaiobe2ur7999i",
        "associationId": "a-z8rmaiobe2ur7999i",
        "tags": {},
        "createdAt": "2025-04-17T03:21:11.751000+09:00",
        "modifiedAt": "2025-04-17T03:21:11.751000+09:00"
    }
}
```

### 3.6. Pod 배포

```bash
cat >kkamji-pod-identity-poc.yaml <<EOF
apiVersion: v1
kind: Pod
metadata:
  name: kkamji-pod-identity-poc
  namespace: default
spec:
  serviceAccountName: kkamji-service-account
  containers:
  - name: demo
    image: amazon/aws-cli:latest
    command: ["sleep", "3600"]
EOF

kubectl apply -f kkamji-pod-identity-poc.yaml

# 토큰 확인 
❯ k describe po kkamji-pod-identity-poc |  grep AWS_CONTAINER
      AWS_CONTAINER_CREDENTIALS_FULL_URI:      http://169.254.170.23/v1/credentials
      AWS_CONTAINER_AUTHORIZATION_TOKEN_FILE:  /var/run/secrets/pods.eks.amazonaws.com/serviceaccount/eks-pod-identity-token
```

### 3.7. 정상 동작 확인

```bash
# Pod에 접속하여 S3 List 확인
❯ k exec -it kkamji-pod-identity-poc -- aws s3 ls s3://kkamji-eks-pod-identity-test-bucket
2025-04-16 18:39:56      96349 pod-identity-test.jpg
```

---

## 4. Terraform 예시

```hcl
# IAM Policy 생성 (S3 버킷 접근 권한)
resource "aws_iam_policy" "pod_identity_s3_policy" {
  name        = "pod-identity-s3-bucket-policy"
  description = "EKS Pod Identity S3 bucket access policy"

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect = "Allow",
      Action = ["s3:ListBucket"],
      Resource = ["arn:aws:s3:::kkamji-eks-pod-identity-test-bucket"]
    }]
  })
}

# IAM Role 생성 (Pod Identity용 신뢰 정책 설정)
resource "aws_iam_role" "pod_identity_s3_role" {
  name = "pod-identity-s3-bucket-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect = "Allow",
      Principal = {
        Service = "pods.eks.amazonaws.com"
      },
      Action = ["sts:AssumeRole", "sts:TagSession"]
    }]
  })

  description = "IAM Role for EKS Pod Identity to access S3 bucket"
}

# IAM Role에 정책 연결
resource "aws_iam_role_policy_attachment" "pod_identity_s3_attach" {
  role       = aws_iam_role.pod_identity_s3_role.name
  policy_arn = aws_iam_policy.pod_identity_s3_policy.arn
}

# Pod Identity Association 설정
resource "aws_eks_pod_identity_association" "kkamji_association" {
  cluster_name     = "kkamji-al2023"
  namespace        = "default"
  service_account  = "kkamji-service-account"
  role_arn         = aws_iam_role.pod_identity_s3_role.arn
}
```

---

## 5. 결론

Amazon EKS Pod Identity는 기존의 IRSA(IAM Roles for Service Accounts)가 가지고 있던 구성의 복잡성과 STS 호출 증가 문제를 획기적으로 개선한 기능입니다. 클러스터마다 별도의 OIDC Provider나 신뢰 정책을 관리하는 번거로움이 사라졌고, IAM Role을 Pod 단위로 간편하게 연결할 수 있어 운영 효율이 크게 향상되었습니다. 특히 EKS Auth API를 활용해 STS 호출 횟수를 최소화하여 대규모 클러스터에서도 안정적으로 동작하는 점이 매우 인상적입니다.

저 역시 기존에는 IRSA를 사용하며 각 클러스터마다 OIDC Provider를 설정하고 IAM Role을 일일이 관리하는 과정에서 많은 번거로움을 겪었는데, 이번에 Pod Identity를 직접 사용해 보니 설정이 매우 간단하고 편리했습니다. 앞으로 신규로 구축하는 EKS 클러스터는 물론 기존 환경도 단계적으로 Pod Identity로 전환하여 적극적으로 활용할 계획입니다.

기존의 IRSA 설정과 관리가 번거로우셨다면 꼭 한번 Pod Identity를 도입해 보시길 권장합니다.

---

## 6. Reference

- [EKS Pod Identity Documentation](https://docs.aws.amazon.com/ko_kr/eks/latest/userguide/pod-identities.html)
- [Amazon EKS Pod Identity, Amazon EKS 클러스터앱의 IAM 권한 단순화](https://aws.amazon.com/ko/blogs/korea/amazon-eks-pod-identity-simplifies-iam-permissions-for-applications-on-amazon-eks-clusters/)
- [EKS Pod Identity Addon PoC](https://techblog.uplus.co.kr/eks-pod-identity-addon-poc-3326b6adb23e)
- [Amazon EKS Pod Identity: EKS의 애플리케이션이 IAM 자격 증명을 얻는 새로운 방법](https://aws.amazon.com/ko/blogs/containers/amazon-eks-pod-identity-a-new-way-for-applications-on-eks-to-obtain-iam-credentials/)
- [EKS Auth API](https://docs.aws.amazon.com/ko_kr/general/latest/gr/eks.html)
- [EKS Pod Identity or IAM Roles for Service Accounts (IRSA) ?](https://awsmorocco.com/eks-pod-identity-or-iam-roles-for-service-accounts-irsa-e32ea9331f27)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
