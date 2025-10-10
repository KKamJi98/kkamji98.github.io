---
title: EKS에서 AWS Secret Manager Secret 사용하기
date: 2024-07-27 04:42:41 +0900
author: kkamji
categories: [Kubernetes]
tags: [kubernetes, aws, eks, secrets-manager, secrets store, helm, secret-provider-class]     # TAG names should always be lowercase
comments: true
image:
  path: /assets/img/kubernetes/kubernetes.webp
---

Secrets Manager의 시크릿을 Amazon EKS의 Pod에 마운트된 파일로 표시하려면, **Kubernetes Secrets Store CSI Driver**와 함께 **AWS Secrets and Configuration Provider(ASCP**)를 사용해야 합니다. 해당 기능은 Parameter Store parameters도 사용할 수 있습니다. Fargate 노드 그룹에는 지원되지 않습니다.

---

## 1. Helm을 사용해 ASCP 설치

### 1.1. Helm 레포지토리 업데이트

```bash
helm repo update
```

### 1.2. Secrets Store CSI Driver 차트 추가

```bash
helm repo add secrets-store-csi-driver https://kubernetes-sigs.github.io/secrets-store-csi-driver/charts
```

### 1.3. Secrets Store CSI Driver 설치

```bash
helm install -n kube-system csi-secrets-store secrets-store-csi-driver/secrets-store-csi-driver
```

### 1.4. ACSP 차트 추가

```bash
helm repo add aws-secrets-manager https://aws.github.io/secrets-store-csi-driver-provider-aws
```

### 1.5. ACSP 설치

```bash
helm install -n kube-system secrets-provider-aws aws-secrets-manager/secrets-store-csi-driver-provider-aws
```

---

## 2. 마운트할 시크릿 식별

- SecretProviderClass에는 마운트할 비밀과 마운트할 파일 이름이 나열되어있으며, 사용할 EKS Pod와 동일한 네임스페이스에 있어야 합니다

### 2.1. SecretProviderClass 생성

```yaml
apiVersion: secrets-store.csi.x-k8s.io/v1
kind: SecretProviderClass
metadata:
  name: test-secrets
  namespace: weasel
spec:
  provider: aws
  secretObjects:
    - secretName: weasel-pod-secret
      type: Opaque
      data:
        - objectName: HOST  # Kubernetes Secret에서 사용할 키 이름
          key: HOST
        - objectName: PORT
          key: PORT
        - objectName: DATABASE
          key: DATABASE
        - objectName: USERNAME
          key: USERNAME
        - objectName: PASSWORD
          key: PASSWORD
  parameters:
    objects: |
      - objectName: "arn:aws:secretsmanager:us-east-1:393035689023:secret:/secret/prod/weasel-I4AhIF"
        jmesPath:
          - path: HOST
            objectAlias: HOST
          - path: PORT
            objectAlias: PORT
          - path: DATABASE
            objectAlias: DATABASE
          - path: USERNAME
            objectAlias: USERNAME
          - path: PASSWORD
            objectAlias: PASSWORD
```

---

## 3. EKS Pod에 Secret을 File로 마운트

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  labels:
    app: test
  name: test
  namespace: weasel
spec:
  replicas: 1
  selector:
    matchLabels:
      app: test
  template:
    metadata:
      labels:
        app: test
    spec:
      serviceAccountName: weasel-eks-pod-sa
      containers:
      - image: amazon/aws-cli:2.0.30
        name: test
        command: ["/bin/bash", "-c", "while true; do sleep infinity; done;"]
        volumeMounts:
        - name: secrets-store-inline
          mountPath: "/mnt/secrets-store"
          readOnly: true
      volumes:
      - name: secrets-store-inline
        csi:
          driver: secrets-store.csi.k8s.io
          readOnly: true
          volumeAttributes:
            secretProviderClass: "test-secrets"
```

---

## 4. 확인

```bash
❯ k exec -it test-5d6df6c995-6phfj -- /bin/bash
bash-4.2# cd /mnt/secrets-store/
bash-4.2# ls
DATABASE  HOST  PASSWORD  PORT  USERNAME
bash-4.2# cat PORT
53306
bash-4.2# cat DATABASE
weasel
```

---

## 5. Reference

<https://secrets-store-csi-driver.sigs.k8s.io> - [Introduction - Secrets Store CSI Driver]

<https://docs.aws.amazon.com/ko_kr/eks/latest/userguide/manage-secrets.html> - [Kubernetes가 있는 AWS Secrets Manager 비밀 사용 - Amazon EKS]

<https://docs.aws.amazon.com/ko_kr/secretsmanager/latest/userguide/integrating_csi_driver.html> - [아마존 엘라스틱 쿠버네티스 서비스에서 AWS Secrets Manager 시크릿 사용하기 - AWS Secrets Manager]

---
> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**
{: .prompt-info}
