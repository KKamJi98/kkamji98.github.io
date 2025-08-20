---
title: External Secrets와 AWS Secrets Manager, SSM Parameter Store 연동하기
date: 2025-03-01 15:39:01 +0900
author: kkamji
categories: [Kubernetes]
tags: [kubernetes, secrets-manager, ssm, parameter-store, rbac, on-premise]     # TAG names should always be lowercase
comments: true
image:
  path: /assets/img/kubernetes/kubernetes.webp
---

**External Secrets**는 쿠버네티스 클러스터에서 외부 시크릿 관리 시스템과 통합하여 시크릿을 관리해주는 오픈소스 도구입니다. AWS Secrets Manager, AWS SSM Parameter Store, HashiCorp Vault, Google Secret Manager 등의 **외부 시크릿 관리 서비스의 값을 가져와 Kubernetes Secret에 주입**하고 **주기적으로 외부 API를 호출하여 시크릿 값을 읽어오고 동기화** 할 수 있습니다.

이를 통해 Application에서 사용하는 API URL이나 DB 정보 등의 변화가 생겼을 때 코드를 수정하지 않고, 외부에 저장된 시크릿을 가져와 환경변수나 볼륨으로 사용할 수 있습니다. 이를 통해 **운영 우수성**과 **보안성**을 높일 수 있고, 휴먼 에러의 가능성을 낮출 수 있습니다.

---

## 1. External Secrets CRDs

External Secrets 외부 시크릿 관리 시스템에 접근하기 위해 **CRD(Custom Resource Definition)**를 사용합니다. 주요 CRD로 **특정 네임스페이스 범위에서 동작**하는 **SecretStore**, **ExternalSecret**과 **클러스터 범위로 동작**하는 **ClusterSecretStore**, **ClusterExternalSecret**이 있습니다. 다음 다이어그램을 확인한 뒤, 아래 각 CRD에 대한 설명을 보시면 이해에 도움이 될 수 있습니다.

![external-secret-diagram](/assets/img/kubernetes/external-secrets-diagram.webp)

### 1.1 SecretStore, ClusterSecretStore

**SecretStore** - **외부 시크릿 서비스에 접근하기 위한 정보를 저장**하는 CRD입니다. 어떤 제공자(provider)를 사용할지, 인증 방식은 어떻게 할지 정의합니다. **SecretStore는 네임스페이스 범위에서 동작하며, 동일한 네임스페이스의 ExternalSecret만 참조**할 수 있습니다.  

**ClusterSecretStore** - **SecretStore**와 유사하지만 **클러스터 전역에서 사용할 수 있는 ClusterStore**입니다. 즉 **하나의 ClusterSecretStore를 생성하면 모든 네임스페이스의 ExternalSecret**에서 참조할 수 있습니다.

> **SecretStore**는 주로 개별 팀/애플리케이션별로 격리된 자격증명을 갖도록 할 때 쓰이고, **ClusterSecretStore**는 모든 네임스페이스에서 공통으로 접근해야 하는 중앙 시크릿 관리 창구를 만들 때 사용합니다.  
>
> 예를 들어 여러 네임스페이스에서 같은 AWS Secrets Manager 자격 증명을 사용해야 한다면 **ClusterSecretStore**로 한 번 정의해두고 재사용할 수 있고, 반대로 네임스페이스를 팀별로 따로 사용하고, AWS IAM 자격 증명을 따로 사용해야 한다면 각 팀 네임스페이스에 SecretStore를 생성하여 사용할 수 있습니다.  
{: .prompt-tip}

### 1.2 ExternalSecret, ClusterExternalSecret

**ExternalSecret** - **외부 시크릿으로부터 실제 쿠버네티스 Secret을 동기화**하기 위한 설정을 담은 CRD입니다. 어떤 **SecretStore**을 참고할지, 외부 시크릿 관리 시스템에서 가져올 시크릿의 키/경로는 무엇인지, 생성될 Kubernetes Secret의 이름은 무엇인지 등을 정의합니다. **ExternalSecret**는 **네임스페이스 범위에서 동작**하며, 생성된 **ExternalSecret은 자신이 속한 네임스페이스에서만 Secret을 생성**합니다.  

**ClusterExternalSecret** - **ExternalSecret**와 유사하지만 **클러스터 전역에서 사용할 수 있는 ExternalSecret**입니다. 즉 **하나의 ClusterExternalSecret은 다수의 네임스페이스에 동일한 ExternalSecret을 생성**해 줄 수 있습니다. `spec.namespaceSelector` 등을 사용하여 대상으로 할 네임스페이스들을 지정하면, 해당 네임스페이스마다 ExternalSecret이 자동 생성되어 동일한 시크릿이 배포됩니다.

> **ExternalSecret**은 특정 애플리케이션 네임스페이스에서만 필요한 DB 비밀번호, API 키 등을 동기화할 때 사용하고, **ClusterExternalSecret**은 모든 네임스페이스에 공통으로 필요한 인증서, 공용 API 키 등을 배포할 때 유용합니다.  
{: .prompt-tip}

---

## 2. External Secrets Operator Helm으로 배포하기

```bash
# Helm Chart Repository 추가
❯ helm repo add external-secrets https://charts.external-secrets.io

# Helm Chart Repository 업데이트
❯ helm repo update

# External Secrets 설치
❯ helm install external-secrets external-secrets/external-secrets \
  -n external-secrets --create-namespace

# 설치 확인 (1) - Pod 정상 동작 확인
❯ kubectl get po -n external-secrets
NAME                                                READY   STATUS    RESTARTS   AGE
external-secrets-6cddc7bb75-8484n                   1/1     Running   0          67s
external-secrets-cert-controller-64f8978956-t77dk   1/1     Running   0          67s
external-secrets-webhook-868d7b5756-wdsw6           1/1     Running   0          67s

# 설치 확인 (2) - crd 확인
❯ kubectl get crds | grep external-secrets.io
acraccesstokens.generators.external-secrets.io          2025-03-02T05:13:57Z
clusterexternalsecrets.external-secrets.io              2025-03-02T05:13:57Z
clustergenerators.generators.external-secrets.io        2025-03-02T05:13:57Z
clustersecretstores.external-secrets.io                 2025-03-02T05:13:57Z
ecrauthorizationtokens.generators.external-secrets.io   2025-03-02T05:13:57Z
externalsecrets.external-secrets.io                     2025-03-02T05:13:57Z
fakes.generators.external-secrets.io                    2025-03-02T05:13:57Z
gcraccesstokens.generators.external-secrets.io          2025-03-02T05:13:57Z
generatorstates.generators.external-secrets.io          2025-03-02T05:13:57Z
githubaccesstokens.generators.external-secrets.io       2025-03-02T05:13:57Z
grafanas.generators.external-secrets.io                 2025-03-02T05:13:57Z
passwords.generators.external-secrets.io                2025-03-02T05:13:57Z
pushsecrets.external-secrets.io                         2025-03-02T05:13:57Z
quayaccesstokens.generators.external-secrets.io         2025-03-02T05:13:57Z
secretstores.external-secrets.io                        2025-03-02T05:13:57Z
stssessiontokens.generators.external-secrets.io         2025-03-02T05:13:57Z
uuids.generators.external-secrets.io                    2025-03-02T05:13:57Z
vaultdynamicsecrets.generators.external-secrets.io      2025-03-02T05:13:57Z
webhooks.generators.external-secrets.io                 2025-03-02T05:13:57Z
```

---

## 3. AWS 접근을 위한 Access Key, Secret Access Key 설정

> 간단한 테스트를 위해 `external-secret`이라는 IAM 유저를 생성하고 해당 유저에 AWS Secrets Manager, SSM Parameter Store에 접근할 수 있는 권한을 부여하여 사용했습니다. 실제 운영환경에서는 최소권한을 갖는 IAM Role을 사용하여 IRSA를 통해 접근하는 것이 좋습니다.  
> \[[IRSA (IAM Role for Service Account)란? 사용 방법]({% post_url 2024/2024-07-17-irsa %})\]
{: .prompt-tip}

```bash
# AWS 액세스 키와 시크릿 키 값으로 쿠버네티스 Secret 생성 (namespace - 'external-secrets')
kubectl create secret generic aws-credentials \
  -n external-secrets \
  --from-literal=aws_access_key_id={Access Key} \
  --from-literal=aws_secret_access_key={Secret Access Key}
```
---

## 4. ClusterSecretStore 생성 - \[AWS Secrets Manager\]

```yaml
# clustersecretstore-secretsmanager.yaml 
apiVersion: external-secrets.io/v1beta1
kind: ClusterSecretStore
metadata:
  name: aws-secretsmanager-store
spec:
  provider:
    aws:
      service: SecretsManager # AWS Secrets Manager 사용
      region: ap-northeast-2 # 시크릿이 존재하는 리전 (서울 리전 예시)
      auth:
        secretRef: # 쿠버네티스 Secret 기반 인증
          accessKeyIDSecretRef:
            name: aws-credentials # AWS 액세스 키가 들어있는 Secret 이름
            namespace: external-secrets # Secret 존재 네임스페이스 (ClusterSecretStore이므로 필요)
            key: aws_access_key_id # Secret에서 액세스 키 ID에 해당하는 키 이름
          secretAccessKeySecretRef:
            name: aws-credentials
            namespace: external-secrets
            key: aws_secret_access_key
```

```bash
❯ kubectl apply -f clustersecretstore-secretsmanager.yaml
❯ kubectl get clustersecretstore
NAME                       AGE   STATUS   CAPABILITIES   READY
aws-secretsmanager-store   15s   Valid    ReadWrite      True
```

---

## 5. ExternalSecret 생성 및 Kubernetes Secret 동기화 - \[AWS Secrets Manager\]

```yaml
# externalsecret-secretsmanager.yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: sample-secretsmanager-secret
  namespace: default
spec:
  refreshInterval: 1h # 주기적 동기화 간격 (예: 1시간)
  secretStoreRef:
    name: aws-secretsmanager-store # 참조할 (Cluster)SecretStore 이름
    kind: ClusterSecretStore # ClusterSecretStore 사용 (전역 스토어)
  target:
    name: basic-auth-secret-manager # 생성될 Kubernetes Secret 이름
    creationPolicy: Owner # Secret 생성 정책 (Owner: 외부 변경 시 덮어씌움)
  data:
    - secretKey: auth # 만들 Kubernetes Secret의 키 이름
      remoteRef:
        key: basic-auth # AWS Secrets Manager 상의 시크릿 이름
        property: basic-auth # (선택사항) AWS 시크릿 JSON에서 가져올 필드
```

```bash
# ExternalSecret 생성
❯ kubectl apply -f externalsecret-secretsmanager.yaml                           
externalsecret.external-secrets.io/sample-secretsmanager-secret created

# ExternalSecret 확인
❯ k get externalsecrets                        
NAME                           STORETYPE            STORE                      REFRESH INTERVAL   STATUS         READY
sample-secretsmanager-secret   ClusterSecretStore   aws-secretsmanager-store   1h                 SecretSynced   True

# 생성된 Kubernetes Secret 확인
❯ k get secrets        
NAME                        TYPE     DATA   AGE
basic-auth-secret-manager   Opaque   1      13s
```

---

## 6. ClusterSecretStore 생성 - \[AWS SSM Parameter Store\]

```yaml
# clustersecretstore-ssm.yaml
apiVersion: external-secrets.io/v1beta1
kind: ClusterSecretStore
metadata:
  name: aws-ssm-store
spec:
  provider:
    aws:
      service: ParameterStore # AWS SSM Parameter Store 사용
      region: ap-northeast-2 # 파라미터가 존재하는 리전
      auth:
        secretRef: # AWS 액세스 키/시크릿 키로 인증
          accessKeyIDSecretRef:
            name: aws-credentials
            namespace: external-secrets
            key: aws_access_key_id
          secretAccessKeySecretRef:
            name: aws-credentials
            namespace: external-secrets
            key: aws_secret_access_key
```

```bash
❯ kubectl apply -f clustersecretstore-ssm.yaml
❯ kubectl get clustersecretstore
NAME                       AGE     STATUS   CAPABILITIES   READY
aws-ssm-store              8s      Valid    ReadWrite      True
```

---

## 7. ExternalSecret 생성 및 Kubernetes Secret 동기화 - \[AWS SSM Parameter Store\]

```yaml
# externalsecret-ssm.yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: sample-ssm-secret
  namespace: default
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-ssm-store # 참조할 ClusterSecretStore 이름
    kind: ClusterSecretStore 
  target:
    name: basic-auth-secret-ssm # 생성될 Kubernetes Secret 이름
    creationPolicy: Owner
  data:
  - secretKey: auth # Kubernetes Secrets의 Key
    remoteRef:
      key: basic-auth # SSM Parameter Store의 파라미터 경로 (키)
# JSON 값: 만약 파라미터 값이 JSON 객체라면, property 필드를 사용해 특정 속성만 추출할 수 있음
# https://external-secrets.io/latest/provider/aws-parameter-store/#json-secret-values
```

```bash
# ExternalSecret 생성
❯ kubectl apply -f externalsecret-ssm.yaml

# ExternalSecret 확인
❯ kubectl get externalsecrets
NAME                           STORETYPE            STORE                      REFRESH INTERVAL   STATUS         READY
sample-ssm-secret              ClusterSecretStore   aws-ssm-store              1h                 SecretSynced   True

# 생성된 Kubernetes Secret 확인
❯ kubectl get secrets           
NAME                        TYPE     DATA   AGE
basic-auth-secret-ssm       Opaque   1      2m53s
```

---

## 8. ClusterExternalSecret으로 여러 네임스페이스에 Secret 배포하기

```yaml
# clusterexternalsecret-ssm.yaml
apiVersion: external-secrets.io/v1beta1
kind: ClusterExternalSecret
metadata:
  name: secretsmanager-clusterexternalsecret
spec:
  externalSecretName: clusterexternalsecret # 생성될 ExternalSecret 이름 (각 네임스페이스에서 이 이름으로 생성됨)
  namespaceSelector:
    # matchLabels:
    #   kubernetes.io/metadata.name: kube-system # kubernetes.io/metadata.name=kube-system 라벨을 가진 네임스페이스에만 배포
    matchExpressions:
      - key: kubernetes.io/metadata.name
        operator: In
        values:
          - kube-system
          - monitoring
  refreshTime: 1h # ClusterExternalSecret 자체의 재평가 주기
  externalSecretSpec: # 생성할 ExternalSecret의 사양 정의 (ExternalSecret spec과 동일)
    secretStoreRef:
      name: aws-secretsmanager-store
      kind: ClusterSecretStore
    target:
      name: clusterexternalsecret-secret # 생성될 Secret 이름
      creationPolicy: Owner
    refreshInterval: 1h # 각 ExternalSecret의 동기화 주기
    data:
      - secretKey: auth
        remoteRef:
          key: basic-auth # AWS Secrets Manager 시크릿 이름 (예시)
          property: basic-auth # 특정 필드명 (예를 들어 JSON 형태일 경우)
```

```bash
❯ kubectl apply -f clusterexternalsecret-ssm.yaml
clusterexternalsecret.external-secrets.io/secretsmanager-clusterexternalsecret created

❯ kubectl get clusterexternalsecrets                   
NAME                                   STORE                      REFRESH INTERVAL   READY
secretsmanager-clusterexternalsecret   aws-secretsmanager-store   1h                 True

❯ kubectl get secrets -A            
NAMESPACE          NAME                                     TYPE                 DATA   AGE
kube-system        clusterexternalsecret-secret             Opaque               1      15s
monitoring         clusterexternalsecret-secret             Opaque               1      15s
```

---

## 9. 마무리

이번 글에서는 External Secrets Operator를 활용하여 쿠버네티스에서 AWS Secrets Manager와 SSM Parameter Store의 시크릿을 동기화하는 방법을 다뤄보았습니다. 이를 통해 Application에서 사용하는 민감한 값을 Git 등에 직접 노출하지 않고도 참조할 수 있게 되어 보안성과 편의성을 크게 향상시킬 수 있습니다.

실무에서 적용할 때는 IRSA를 사용하는 것을 추천드리며 `auth.jwt` 필드나 `serviceAccountRef`를 빼먹지 않도록 주의해야합니다. 또한 복잡하거나 많은 키를 가진 시크릿을 사용해야할 경우 `.data[]` 형식 외에도 `.dataFrom`, `.template` 형식을 사용해 여러 키를 가진 시크릿을 통째로 가져와 사용할 수도 있습니다.

---

## 10. 참고 자료

- <https://external-secrets.io/>
- <https://external-secrets.io/latest/provider/aws-secrets-manager/>
- <https://external-secrets.io/latest/provider/aws-parameter-store/>
- <https://cloudhero.io/getting-started-with-external-secrets-operator-on-kubernetes-using-aws-secrets-manager/>
- <https://www.devopsschool.com/blog/external-secrets-operator-difference-between-clusterexternalsecret-vs-externalsecret/>
- <https://blog.omoknooni.me/150>

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**
{: .prompt-info}
