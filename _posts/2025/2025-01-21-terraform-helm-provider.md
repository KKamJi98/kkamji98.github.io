---
title: Terraform Helm Provider 사용 방법
date: 2025-01-21 23:11:55 +0900
author: kkamji
categories: [IaC, Terraform]
tags: [terraform, kubernetes, helm, helm-provider, devops, bitnami, nginx]     # TAG names should always be lowercase
comments: true
image:
  path: /assets/img/iac/terraform/terraform.webp
---

Helm은 Kubernetes의 패키지 매니저로, 애플리케이션의 배포 및 관리를 간편하게 해주는 도구입니다. Kubernetes의 리소스를 정의하는 Manifest 파일을 템플릿화하여 **재사용성**과 **유지보수성**을 높이는 데 도움을 줍니다.

일반적으로 패키지 매니저를 사용하지 않고 Dev, Stage, Prod 등의 다양한 환경에서 Kubernetes Manifest 파일만을 사용해 운영할 경우, 각 환경에 맞춘 `Replicas`, `ConfigMap`, `Secrets` 등의 설정을 개별적으로 관리해야 합니다. 이로 인해 **운영의 복잡성 증가**, **구성의 일관성 유지 어려움**, **수작업에 의한 오류 가능성 증가**와 같은 문제점이 발생할 수 있습니다.

Terraform 환경에서 Helm을 활용하면, Kubernetes 애플리케이션의 배포 자동화가 가능하며, **인프라 및 애플리케이션을 일관되게** 관리하기가 쉬워집니다. Terraform의 Helm Provider를 사용하면 Helm Chart의 설치, 업데이트, 삭제를 코드로 정의할 수 있으며, 이를 통해 **운영 효율성을 높이고 CI/CD 파이프라인과의 연동**도 원활해집니다.

이번 포스트에서는 Terraform Helm Provider를 활용해 Kubernetes 애플리케이션을 배포하는 방법에 대해 다뤄보도록 하겠습니다.

---

## 1. 실습 환경

- Terraform (v1.10.4)
- Helm Provider(hashicorp/helm) (v2.17.0)
- Helm (v3.16.2)
- kubectl (v1.32.0)
- Kubernetes Cluster (v1.32.0)

> 위 버전은 현재 실습 환경이며, 실제 운영 환경에서는 다른 버전을 사용하셔도 무방합니다. 다만, Terraform Helm Provider 버전에 따라 일부 설정이나 문법이 달라질 수 있습니다.
{: .prompt-tip}

---

## 2. Terraform Helm Provider 설정

Helm Provider를 사용하기 위해서는 크게 다음 두 가지 방법이 있습니다.

1. `config_path`를 사용해 kubeconfig 파일로 접근  
2. Kubernetes Cluster Credentials를 직접 설정

### 2.1 `config_path` 사용

> `terraform` 명령어를 실행하는 환경에서 `~/.kube/config` 경로의 kubeconfig 파일이 정상적으로 Kubernetes Cluster에 접근할 수 있어야 합니다.
{: .prompt-tip}

```hcl
provider "helm" {
  kubernetes {
    config_path = "~/.kube/config"
  }
}
```

### 2.2 Kubernetes Cluster Credentials 사용

> Kubernetes Cluster Credentials를 직접 설정하여 Helm Provider를 사용할 수도 있습니다.  
> `kubectl config view --raw` 명령어를 사용하면 `client-certificate-data`, `client-key-data`, `cluster-ca-certificate-data` 값을 확인할 수 있습니다.
{: .prompt-tip}

```hcl
provider "helm" {
  kubernetes {
    host     = "https://cluster_endpoint:port"

    client_certificate     = base64decode("LS0tLS1CRUdJTiBDRVJUSUZJQ0FURS0tLS0...생략...")
    client_key             = base64decode("LS0tLS1CRUdJTiBSU0EgUFJJVkFURSBLRVk...생략...")
    cluster_ca_certificate = base64decode("LS0tLS1CRUdJTiBDRVJUSUZJQ0FURS0tLS0...생략...")
  }
}
```

> **주의**  
> 위 정보를 코드에 직접 하드코딩하면 보안적으로 취약할 수 있습니다. 실제 운영 환경에서는 Terraform 변수나 `data` 리소스, 외부 시크릿 저장소 등을 사용해 안전하게 주입하는 방식을 권장합니다.
{: .prompt-danger}

---

## 3. Terraform Helm Provider를 사용한 리소스 배포

실습을 위해 `Bitnami`에서 제공하는 **Nginx 웹 서버** Helm Chart를 간단히 배포해보겠습니다.  
자세한 설정값 및 옵션은 [공식 문서](https://registry.terraform.io/providers/hashicorp/helm/latest/docs)에서 참고하실 수 있습니다.

```hcl
resource "helm_release" "nginx" {
  name       = "my-nginx"                                 # K8s 내 Release 이름
  repository = "oci://registry-1.docker.io/bitnamicharts" # 차트 레포지토리
  chart      = "nginx"                                    # 차트명
  version    = "18.3.5"                                   # 차트 버전 (원하는 버전)

  namespace        = "helm-provider-practice" # 배포할 네임스페이스
  create_namespace = true                     # 네임스페이스가 없을 경우 생성

  # values = [
  #   file("nginx-values.yaml")  # 차트 설정(Values) 파일을 넣을 수도 있음
  # ]

  # 단순 key-value 형식 설정 (set)
  set {
    name  = "service.type"
    value = "LoadBalancer"
  }

  set {
    name  = "service.port"
    value = "80"
  }

  set {
    name  = "replicaCount"
    value = "3"
  }

  # 예시) Atomic, Timeout 등 옵션 설정 가능
  atomic  = true
  timeout = 300
} 
```

### 3.1 핵심 옵션

- **name**: K8s 내 Helm Release 이름
- **repository**: 차트가 있는 Helm Repo URL
- **chart**: 사용할 차트 이름
- **version**: 차트 버전 (생략 시 최신 버전 사용)
- **namespace**: 배포할 네임스페이스 (자동 생성 옵션 있음)
- **values** 또는 `set {}`: Helm Chart의 Values.yaml 설정

---

### 3.2 Nginx Helm Chart 배포

```shell
❯ terraform apply

Terraform used the selected providers to generate the following execution plan. Resource actions are indicated with the following symbols:
  + create

Terraform will perform the following actions:

  # helm_release.nginx will be created
  + resource "helm_release" "nginx" {
      + atomic                     = true
      + chart                      = "nginx"
      + cleanup_on_fail            = false
      + create_namespace           = true
      ...
      ...
      + version                    = "18.3.5"
      + wait                       = true
      + wait_for_jobs              = false

      + set {
          + name  = "replicaCount"
          + value = "3"
        }
      + set {
          + name  = "service.port"
          + value = "80"
        }
      + set {
          + name  = "service.type"
          + value = "LoadBalancer"
        }
    }

Plan: 1 to add, 0 to change, 0 to destroy.

Do you want to perform these actions?
  Terraform will perform the actions described above.
  Only 'yes' will be accepted to approve.

  Enter a value: yes

helm_release.nginx: Creating...
helm_release.nginx: Still creating... [10s elapsed]
helm_release.nginx: Creation complete after 15s [id=my-nginx]

Apply complete! Resources: 1 added, 0 changed, 0 destroyed.

❯ kubectl get all -n helm-provider-practice
NAME                            READY   STATUS    RESTARTS   AGE
pod/my-nginx-6c44c9689c-5rv9v   1/1     Running   0          2m31s
pod/my-nginx-6c44c9689c-kwl7x   1/1     Running   0          2m31s
pod/my-nginx-6c44c9689c-nds94   1/1     Running   0          2m31s

NAME               TYPE           CLUSTER-IP     EXTERNAL-IP   PORT(S)                      AGE
service/my-nginx   LoadBalancer   10.233.41.62   10.0.1.101    80:30805/TCP,443:30766/TCP   2m31s

NAME                       READY   UP-TO-DATE   AVAILABLE   AGE
deployment.apps/my-nginx   3/3     3            3           2m31s

NAME                                  DESIRED   CURRENT   READY   AGE
replicaset.apps/my-nginx-6c44c9689c   3         3         3       2m31s
```

---

## 4. 마무리

이상으로 Terraform Helm Provider를 사용해 간단히 Nginx 웹 서버를 배포하는 과정을 살펴보았습니다.  
AWS EKS 환경에서 `aws eks get-token` 등을 통해 동적 토큰을 발행하고, Terraform의 exec 플러그인이나 `data "aws_eks_cluster_auth"`와 연동하여 사용하는 방법도 있으니 참고하시기 바랍니다.

---
> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**
{: .prompt-info}
