---
title: EKS Karpenter 적용기
date: 2024-08-06 21:51:43 +0900
author: kkamji
categories: [Kubernetes]
tags: [kubernetes, aws, eks, karpenter, autoscaling, hpa, ca]     # TAG names should always be lowercase
comments: true
image:
  path: /assets/img/kubernetes/karpenter.png
---

## 1. Karpenter란?

최근 **Weasel** 프로젝트를 진행하면서 **Elastic Kubernetes Service(EKS)**를 사용하게 되었고. **Horizontal Pod Autoscaler(HPA)**를 사용해 고가용성을 보완하려 노력했습니다. 하지만 **HPA**만 사용해서는 트래픽이 급증하고 Node의 리소스 사용량이 한계치에 다다르게 되면 더 이상 사용자에게 서비스를 원활하게 제공할 수 없을 것입니다. 따라서 **Weasel** 프로젝트에 AWS에서 개발한 오픈 소스의 고성능 **Kubernetes Cluster Autoscaler**인 **Karpenter**를 도입을 결정짓게 되었습니다.

해당 포스트에서는 **Karpenter**를 **Weasel**에 어떻게 적용했고, 어떤 문제를 겪었으며 어떻게 해결했는지에 대해 다뤄보겠습니다.

---

## 2. Cluster Autoscaler(CA) VS Karpenter

Kubernetes의 클러스터 오토스케일링은 클러스터 내의 리소스를 자동으로 관리하여 애플리케이션의 가용성과 성능을 유지하는 데 중요한 역할을 합니다. AWS에서는 두 가지 주요 오토스케일링 도구를 제공합니다. **Cluster Autoscaler(CA)**와 **Karpenter**입니다.

### 2.1. Cluster Autoscaler(CA)

**Cluster Autoscaler(CA)**는 Kubernetes 생태계에서 널리 사용되고 있습니다. 또한 안정성과 신뢰성이 높으며 **Auto Scaling Group(ASG)**과 통합되어 사용할 수 있다는 장점이 있습니다. **CA**는 **ASG** 기반으로 동작하며 Pod가 지속적으로 할당에 실패하면 **ASG**의 Desired Capacity 값을 수정하여 Worker Node의 개수를 증가시키는 방식으로 Auto Scaling이 이루어집니다. 하지만 **ASG**를 기반으로 동작하기 때문에 사전에 정의된 노드 그룹의 인스턴스 타입만을 사용해야 하며, 노드를 추가하거나 제거하는 데 시간이 오래 걸린다는 단점이 있습니다.

### 2.2. Karpenter

**Karpenter**는 AWS에서 제공하는 Kubernetes Cluster의 자동 노드 프로비저닝 도구입니다. **Karpenter**는 Pod가 스케줄링에 실패할 시 즉시 새로운 노드를 프로비저닝하며 다양한 인스턴스 타입을 지원하며, 클러스터의 리소스 요구사항에 맞는 최적의 인스턴스 타입을 선택하여 비용 효율성을 높일 수 있습니다. 또한 필요에 따라 Spot 인스턴스, On-Demand 인스턴스를 선택할 수 있습니다. 하지만 **Karpenter**는 AWS에 종속적이며, **CA**에 비해 상대적으로 성숙도와 안정성이 부족할 수 있다는 단점이 있습니다.

---

## 3. Karpenter 선택 이유

**Weasel** 프로젝트에서는 현재 **EKS**를 사용하고 있으며 그 외 ECR, RDS, S3, Route53, CloudFront, NAT Gateway 등의 AWS 서비스를 사용하고 있습니다. 고가용성을 고려한 아키텍처 설계 및 구축도 중요하지만 고가용성을 고집하게 되면 계획보다 많은 클라우드 인프라 유지 비용이 발생하게 됩니다. 따라서 고가용성은 향상시키며 추가로 지출되는 비용을 최소로 해야 했고, Karpenter의 장점인 다양한 인스턴스 타입 지원, 클러스터의 리소스 요구사항에 맞는 최적의 인스턴스 타입 선택은 매력적으로 다가왔습니다. 추가로 안정적으로 서비스를 제공하기 위해서는 트래픽이 급증했을 때 무엇보다 노드가 확장되는 속도가 중요했기 때문에 **Cluster Autoscaler(CA)**와 **Karpenter** 중 **Karpenter를** 선택하게 되었습니다.

---

## 4. Karpenter 사전 작업

[Migrating from Cluster Autoscaler](https://karpenter.sh/docs/getting-started/migrating-from-cas/)

Karpenter 공식 문서를 참고하여 최신버전의 0.37.0 버전을 설치하는 과정을 공유하겠습니다.

### 4.1. 준비 도구

- AWS CLI
- kubectl
- eksctl(v0.180.0 이상)
- helm

### 4.2. 환경 변수 설정

```bash
KARPENTER_NAMESPACE="karpenter"
CLUSTER_NAME="weasel-eks"
```

```bash
AWS_PARTITION="aws" # if you are not using standard partitions, you may need to configure to aws-cn / aws-us-gov
AWS_REGION="$(aws configure list | grep region | tr -s " " | cut -d" " -f3)"
OIDC_ENDPOINT="$(aws eks describe-cluster --name "${CLUSTER_NAME}" \
    --query "cluster.identity.oidc.issuer" --output text)"
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query 'Account' \
    --output text)
K8S_VERSION=1.30.2
ARM_AMI_ID="$(aws ssm get-parameter --name /aws/service/eks/optimized-ami/${K8S_VERSION}/amazon-linux-2-arm64/recommended/image_id --query Parameter.Value --output text)"
AMD_AMI_ID="$(aws ssm get-parameter --name /aws/service/eks/optimized-ami/${K8S_VERSION}/amazon-linux-2/recommended/image_id --query Parameter.Value --output text)"
GPU_AMI_ID="$(aws ssm get-parameter --name /aws/service/eks/optimized-ami/${K8S_VERSION}/amazon-linux-2-gpu/recommended/image_id --query Parameter.Value --output text)"
```

### 4.3. IAM Role 생성

```bash
echo '{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "Service": "ec2.amazonaws.com"
            },
            "Action": "sts:AssumeRole"
        }
    ]
}' > node-trust-policy.json

aws iam create-role --role-name "KarpenterNodeRole-${CLUSTER_NAME}" \
    --assume-role-policy-document file://node-trust-policy.json
```

### 4.4. 정책 추가

```bash
aws iam attach-role-policy --role-name "KarpenterNodeRole-${CLUSTER_NAME}" \
    --policy-arn "arn:${AWS_PARTITION}:iam::aws:policy/AmazonEKSWorkerNodePolicy"

aws iam attach-role-policy --role-name "KarpenterNodeRole-${CLUSTER_NAME}" \
    --policy-arn "arn:${AWS_PARTITION}:iam::aws:policy/AmazonEKS_CNI_Policy"

aws iam attach-role-policy --role-name "KarpenterNodeRole-${CLUSTER_NAME}" \
    --policy-arn "arn:${AWS_PARTITION}:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"

aws iam attach-role-policy --role-name "KarpenterNodeRole-${CLUSTER_NAME}" \
    --policy-arn "arn:${AWS_PARTITION}:iam::aws:policy/AmazonSSMManagedInstanceCore"
```

### 4.5. Karpenter Controller IAM Role 생성

> Karpenter Controller가 새 인스턴스를 프로비저닝하는 데 사용할 IAM 역할을 생성합니다. Controller는 OIDC Endpoint를 사용해서 IAM Roles for Service Account(IRSA)를 사용해야 합니다. 따라서 OIDC Provider가 필요합니다.
{: .prompt-info}

```bash
cat << EOF > controller-trust-policy.json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "Federated": "arn:${AWS_PARTITION}:iam::${AWS_ACCOUNT_ID}:oidc-provider/${OIDC_ENDPOINT#*//}"
            },
            "Action": "sts:AssumeRoleWithWebIdentity",
            "Condition": {
                "StringEquals": {
                    "${OIDC_ENDPOINT#*//}:aud": "sts.amazonaws.com",
                    "${OIDC_ENDPOINT#*//}:sub": "system:serviceaccount:${KARPENTER_NAMESPACE}:karpenter"
                }
            }
        }
    ]
}
EOF

aws iam create-role --role-name "KarpenterControllerRole-${CLUSTER_NAME}" \
    --assume-role-policy-document file://controller-trust-policy.json

cat << EOF > controller-policy.json
{
    "Statement": [
        {
            "Action": [
                "ssm:GetParameter",
                "ec2:DescribeImages",
                "ec2:RunInstances",
                "ec2:DescribeSubnets",
                "ec2:DescribeSecurityGroups",
                "ec2:DescribeLaunchTemplates",
                "ec2:DescribeInstances",
                "ec2:DescribeInstanceTypes",
                "ec2:DescribeInstanceTypeOfferings",
                "ec2:DescribeAvailabilityZones",
                "ec2:DeleteLaunchTemplate",
                "ec2:CreateTags",
                "ec2:CreateLaunchTemplate",
                "ec2:CreateFleet",
                "ec2:DescribeSpotPriceHistory",
                "pricing:GetProducts"
            ],
            "Effect": "Allow",
            "Resource": "*",
            "Sid": "Karpenter"
        },
        {
            "Action": "ec2:TerminateInstances",
            "Condition": {
                "StringLike": {
                    "ec2:ResourceTag/karpenter.sh/nodepool": "*"
                }
            },
            "Effect": "Allow",
            "Resource": "*",
            "Sid": "ConditionalEC2Termination"
        },
        {
            "Effect": "Allow",
            "Action": "iam:PassRole",
            "Resource": "arn:${AWS_PARTITION}:iam::${AWS_ACCOUNT_ID}:role/KarpenterNodeRole-${CLUSTER_NAME}",
            "Sid": "PassNodeIAMRole"
        },
        {
            "Effect": "Allow",
            "Action": "eks:DescribeCluster",
            "Resource": "arn:${AWS_PARTITION}:eks:${AWS_REGION}:${AWS_ACCOUNT_ID}:cluster/${CLUSTER_NAME}",
            "Sid": "EKSClusterEndpointLookup"
        },
        {
            "Sid": "AllowScopedInstanceProfileCreationActions",
            "Effect": "Allow",
            "Resource": "*",
            "Action": [
            "iam:CreateInstanceProfile"
            ],
            "Condition": {
            "StringEquals": {
                "aws:RequestTag/kubernetes.io/cluster/${CLUSTER_NAME}": "owned",
                "aws:RequestTag/topology.kubernetes.io/region": "${AWS_REGION}"
            },
            "StringLike": {
                "aws:RequestTag/karpenter.k8s.aws/ec2nodeclass": "*"
            }
            }
        },
        {
            "Sid": "AllowScopedInstanceProfileTagActions",
            "Effect": "Allow",
            "Resource": "*",
            "Action": [
            "iam:TagInstanceProfile"
            ],
            "Condition": {
            "StringEquals": {
                "aws:ResourceTag/kubernetes.io/cluster/${CLUSTER_NAME}": "owned",
                "aws:ResourceTag/topology.kubernetes.io/region": "${AWS_REGION}",
                "aws:RequestTag/kubernetes.io/cluster/${CLUSTER_NAME}": "owned",
                "aws:RequestTag/topology.kubernetes.io/region": "${AWS_REGION}"
            },
            "StringLike": {
                "aws:ResourceTag/karpenter.k8s.aws/ec2nodeclass": "*",
                "aws:RequestTag/karpenter.k8s.aws/ec2nodeclass": "*"
            }
            }
        },
        {
            "Sid": "AllowScopedInstanceProfileActions",
            "Effect": "Allow",
            "Resource": "*",
            "Action": [
            "iam:AddRoleToInstanceProfile",
            "iam:RemoveRoleFromInstanceProfile",
            "iam:DeleteInstanceProfile"
            ],
            "Condition": {
            "StringEquals": {
                "aws:ResourceTag/kubernetes.io/cluster/${CLUSTER_NAME}": "owned",
                "aws:ResourceTag/topology.kubernetes.io/region": "${AWS_REGION}"
            },
            "StringLike": {
                "aws:ResourceTag/karpenter.k8s.aws/ec2nodeclass": "*"
            }
            }
        },
        {
            "Sid": "AllowInstanceProfileReadActions",
            "Effect": "Allow",
            "Resource": "*",
            "Action": "iam:GetInstanceProfile"
        }
    ],
    "Version": "2012-10-17"
}
EOF

aws iam put-role-policy --role-name "KarpenterControllerRole-${CLUSTER_NAME}" \
    --policy-name "KarpenterControllerPolicy-${CLUSTER_NAME}" \
    --policy-document file://controller-policy.json
```

### 4.6. Subnet, Security Group에 Tag 추가

> Karpenter가 사용할 Subnet을 식별할 수 있도록 Node Group의 Subnet에 Tag를 추가합니다.
{: .prompt-info}

```bash
for NODEGROUP in $(aws eks list-nodegroups --cluster-name "${CLUSTER_NAME}" --query 'nodegroups' --output text); do
    aws ec2 create-tags \
        --tags "Key=karpenter.sh/discovery,Value=${CLUSTER_NAME}" \
        --resources $(aws eks describe-nodegroup --cluster-name "${CLUSTER_NAME}" \
        --nodegroup-name "${NODEGROUP}" --query 'nodegroup.subnets' --output text )
done

```

> 보안 그룹에 태그를 추가합니다. 해당 명령어는 클러스터의 첫 번째 노드 그룹에 대한 보안 그룹에만 태그를 지정합니다. 노드 그룹이나 보안 그룹이 여러 개 있는 경우 Karpenter가 어떤 것을 사용해야 할지 결정해야 합니다.
{: .prompt-info}

```bash
NODEGROUP=$(aws eks list-nodegroups --cluster-name "${CLUSTER_NAME}" \
    --query 'nodegroups[0]' --output text)

LAUNCH_TEMPLATE=$(aws eks describe-nodegroup --cluster-name "${CLUSTER_NAME}" \
    --nodegroup-name "${NODEGROUP}" --query 'nodegroup.launchTemplate.{id:id,version:version}' \
    --output text | tr -s "\t" ",")

SECURITY_GROUPS=$(aws eks describe-cluster \
    --name "${CLUSTER_NAME}" --query "cluster.resourcesVpcConfig.clusterSecurityGroupId" --output text)


SECURITY_GROUPS="$(aws ec2 describe-launch-template-versions \
    --launch-template-id "${LAUNCH_TEMPLATE%,*}" --versions "${LAUNCH_TEMPLATE#*,}" \
    --query 'LaunchTemplateVersions[0].LaunchTemplateData.[NetworkInterfaces[0].Groups||SecurityGroupIds]' \
    --output text)"

aws ec2 create-tags \
    --tags "Key=karpenter.sh/discovery,Value=${CLUSTER_NAME}" \
    --resources "${SECURITY_GROUPS}"
```

### 4.7. aws_auth ConfigMap 업데이트

> 앞에서 생성한 IAM 역할을 사용하는 노드가 클러스터에 가입할 수 있도록 허용해야 합니다. 이를 위해 클러스터의 aws-auth ConfigMap을 수정합니다.
{: .prompt-info}

```bash
kubectl edit configmap aws-auth -n kube-system
```

> mapRoles에 다음과 같은 섹션을 추가합니다. ${AWS_PARTITION} 변수에는 계정 파티션을, ${AWS_ACCOUNT_ID}에는 계정 넘버를 ${CLUSTER_NAME} 변수에는 클러스터 이름을 넣어줍니다.{{EC2PrivateDNSName}}은 변경하지 않습니다.
{: .prompt-info}

```bash
- groups:
  - system:bootstrappers
  - system:nodes
  rolearn: arn:${AWS_PARTITION}:iam::${AWS_ACCOUNT_ID}:role/KarpenterNodeRole-${CLUSTER_NAME}
  username: system:node:{{EC2PrivateDNSName}}
```

---

## 5. Karpenter 설치

> 현재 가장 최신버전인 **0.37.0** 버전을 설치하겠습니다.
{: .prompt-info}

### 5.1. Helm template을 사용한 manifest 파일 생성

```bash
export KARPENTER_VERSION="0.37.0"

helm template karpenter oci://public.ecr.aws/karpenter/karpenter --version "${KARPENTER_VERSION}" --namespace "${KARPENTER_NAMESPACE}" \
    --set "settings.clusterName=${CLUSTER_NAME}" \
    --set "serviceAccount.annotations.eks\.amazonaws\.com/role-arn=arn:${AWS_PARTITION}:iam::${AWS_ACCOUNT_ID}:role/KarpenterControllerRole-${CLUSTER_NAME}" \
    --set controller.resources.requests.cpu=1 \
    --set controller.resources.requests.memory=1Gi \
    --set controller.resources.limits.cpu=1 \
    --set controller.resources.limits.memory=1Gi > karpenter.yaml
```

### 5.2. node affinity 설정

> Karpenter가 기존 노드 그룹 중 하나에서 실행되도록 manifest 파일을 수정합니다. ${NODEGROUP}에는 Karpenter가 실행될 EKS Node Group의 이름을 넣어줍니다.
{: .prompt-info}

```bash
affinity:
  nodeAffinity:
    requiredDuringSchedulingIgnoredDuringExecution:
      nodeSelectorTerms:
      - matchExpressions:
        - key: karpenter.sh/nodepool
          operator: DoesNotExist
        - key: eks.amazonaws.com/nodegroup
          operator: In
          values:
          - ${NODEGROUP}
  podAntiAffinity:
    requiredDuringSchedulingIgnoredDuringExecution:
      - topologyKey: "kubernetes.io/hostname"
```

### 5.3. karpenter 리소스 배포

> Namespace 생성 및 NodePool CRD를 만든 뒤, Karpenter 리소스를 배포합니다
{: .prompt-info}

```bash
kubectl create namespace "${KARPENTER_NAMESPACE}" || true
kubectl create -f \
    "https://raw.githubusercontent.com/aws/karpenter-provider-aws/v${KARPENTER_VERSION}/pkg/apis/crds/karpenter.sh_nodepools.yaml"
kubectl create -f \
    "https://raw.githubusercontent.com/aws/karpenter-provider-aws/v${KARPENTER_VERSION}/pkg/apis/crds/karpenter.k8s.aws_ec2nodeclasses.yaml"
kubectl create -f \
    "https://raw.githubusercontent.com/aws/karpenter-provider-aws/v${KARPENTER_VERSION}/pkg/apis/crds/karpenter.sh_nodeclaims.yaml"
kubectl apply -f karpenter.yaml
```

---

## 6. NodePool 및 EC2NodeClass 생성

> **NodePool**은 **Karpenter**에서 관리되는 Kubernetes 노드의 집합입니다. 이 **NodePool**은 정의된 사항에 따라 EC2 인스턴스를 자동으로 생성하고 조정합니다. **EC2NodeClass**는 **Karpenter**가 사용할 EC2 인스턴스의 세부 사항을 정의합니다. 현재 사용하고 있는 인스턴스 타입으로 `t3.medium`을 지정했습니다. 주석된 부분처럼 `karpenter.k8s.aws/instance-category` 항목에 인스턴스 타입을, `karpenter.k8s.aws/instance-cpu` 항목에 사용할 vCPU 크기를 나열할 수도 있습니다. 현재는 t3.medium 인스턴스 외에 다른 인스턴스를 사용하지 않기 때문에 `karpenter.sh/capacity-type` 옵션을 사용해 지정해주었습니다.
{: .prompt-info}

```bash
apiVersion: karpenter.sh/v1beta1
kind: NodePool
metadata:
  name: default
spec:
  template:
    spec:
      requirements:
        - key: kubernetes.io/arch
          operator: In
          values: ["amd64"]
        - key: kubernetes.io/os
          operator: In
          values: ["linux"]
        - key: karpenter.sh/capacity-type
          operator: In
          values: ["spot"]
        # - key: karpenter.k8s.aws/instance-category
        #   operator: In
        #   values: ["c", "m", "r", "t"]
        - key: node.kubernetes.io/instance-type
          operator: In
          values: ["t3.medium"]
        # - key: "karpenter.k8s.aws/instance-cpu"
        #   operator: In
        #   values: ["2", "4", "8"]
        # - key: karpenter.k8s.aws/instance-generation
        #   operator: Gt
        #   values: ["2"]
      nodeClassRef:
        apiVersion: karpenter.k8s.aws/v1beta1
        kind: EC2NodeClass
        name: default
  limits:
    cpu: 1000
  disruption:
    consolidationPolicy: WhenUnderutilized
    expireAfter: 720h # 30 * 24h = 720h
---
apiVersion: karpenter.k8s.aws/v1beta1
kind: EC2NodeClass
metadata:
  name: default
spec:
  amiFamily: AL2 # Amazon Linux 2
  role: "KarpenterNodeRole-weasel-eks"
  subnetSelectorTerms:
    - tags:
        karpenter.sh/discovery: "weasel-eks"
  securityGroupSelectorTerms:
    - tags:
        karpenter.sh/discovery: "weasel-eks"
  amiSelectorTerms:
    - id: "ami-09c00c2e93ce7bd23"
```

---

## 7. 확인

- `kubectl logs -f -n karpenter -c controller -l app.kubernetes.io/name=karpenter`
    ```bash
    {"level":"INFO","time":"2024-08-07T19:23:07.084Z","logger":"controller","message":"found provisionable pod(s)","commit":"490ef94","controller":"provisioner","Pods":"monitoring/grafana-867556d6f5-2lpdh, monitoring/prometheus-server-5d8d4b9d9b-kmhld, monitoring/prometheus-alertmanager-0","duration":"37.301795ms"}
    {"level":"INFO","time":"2024-08-07T19:23:07.085Z","logger":"controller","message":"computed new nodeclaim(s) to fit pod(s)","commit":"490ef94","controller":"provisioner","nodeclaims":1,"pods":3}
    {"level":"INFO","time":"2024-08-07T19:23:07.100Z","logger":"controller","message":"created nodeclaim","commit":"490ef94","controller":"provisioner","NodePool":{"name":"default"},"NodeClaim":{"name":"default-gqq5d"},"requests":{"cpu":"430m","memory":"870Mi","pods":"8"},"instance-types":"t3.medium"}
    {"level":"INFO","time":"2024-08-07T19:23:10.043Z","logger":"controller","message":"launched nodeclaim","commit":"490ef94","controller":"nodeclaim.lifecycle","controllerGroup":"karpenter.sh","controllerKind":"NodeClaim","NodeClaim":{"name":"default-gqq5d"},"namespace":"","name":"default-gqq5d","reconcileID":"d86c917e-7ff6-4309-afdc-f7cc4b65cf29","provider-id":"aws:///us-east-1b/i-0cf1182591adb49e6","instance-type":"t3.medium","zone":"us-east-1b","capacity-type":"spot","allocatable":{"cpu":"1930m","ephemeral-storage":"17Gi","memory":"3246Mi","pods":"17"}}
    {"level":"INFO","time":"2024-08-07T19:23:44.052Z","logger":"controller","message":"registered nodeclaim","commit":"490ef94","controller":"nodeclaim.lifecycle","controllerGroup":"karpenter.sh","controllerKind":"NodeClaim","NodeClaim":{"name":"default-gqq5d"},"namespace":"","name":"default-gqq5d","reconcileID":"34f52f10-0570-4601-b4da-4db8900c2eae","provider-id":"aws:///us-east-1b/i-0cf1182591adb49e6","Node":{"name":"ip-10-10-210-178.ec2.internal"}}
    {"level":"INFO","time":"2024-08-07T19:23:56.783Z","logger":"controller","message":"initialized nodeclaim","commit":"490ef94","controller":"nodeclaim.lifecycle","controllerGroup":"karpenter.sh","controllerKind":"NodeClaim","NodeClaim":{"name":"default-gqq5d"},"namespace":"","name":"default-gqq5d","reconcileID":"b66732cf-5049-460e-887d-843893d425c7","provider-id":"aws:///us-east-1b/i-0cf1182591adb49e6","Node":{"name":"ip-10-10-210-178.ec2.internal"},"allocatable":{"cpu":"1930m","ephemeral-storage":"18242267924","hugepages-1Gi":"0","hugepages-2Mi":"0","memory":"3388300Ki","pods":"17"}}
    ```
    > 로그를 통해 karpenter가 정상적으로 동작하는 것을 확인할 수 있으며, 다음과 같이 Karpenter가 노드를 프로비저닝하는 방식을 확인할 수 있습니다.
    {: .prompt-info}

    1. 프로비저닝 가능한 Pod 발견
    2. NodeClaim 계산
    3. NodeClaim 생성
    4. NodeClaim 실행
    5. NodeClaim 등록
    6. NodeClaim 초기화

---

## 8. 마무리

블로그, 과거 문서들을 참고하며 Karpenter를 구축하려 했지만, 해당 내용은 Helm Chart의 변수, Karpenter가 사용하는 정책 등이 달랐기 때문에 최신버전의 Karpenter구축에는 적합하지 않아 생각보다 많은 우여곡절이 있었습니다. 간편하게 누군가가 정리해놓은 글을 참고하여 원하는 작업을 수행할 수도 있지만, 가장 확실한 정답은 공식문서에 있다는 것을 다시 한번 상기시키게 되는 계기가 되었습니다. 무엇보다 해당 경험을 통해 Karpenter가 동작하는데에는 어떤 구성요소가 필요한지, Karpenter는 어떤 방식으로 노드를 Scaling하는지 확인할 수 있었습니다.

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
