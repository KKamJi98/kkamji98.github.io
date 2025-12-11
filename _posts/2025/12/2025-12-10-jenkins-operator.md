---
title: Jenkins Operator란?
date: 2025-12-10 19:50:12 +0900
author: kkamji
categories: [DevOps]
tags: [devops, ci-cd, jenkins, jenkins-operator, kubernetes]
comments: true
image:
  path: /assets/img/ci-cd/jenkins/jenkins.webp
---

**Jenkins Operator는 Kubernetes 환경에서 Jenkins 인스턴스를 관리하고 운영하기 위한 도구**입니다. Jenkins는 오픈 소스 자동화 서버로, 소프트웨어 개발 프로세스를 자동화하는 데 널리 사용됩니다. Jenkins Operator는 Kubernetes의 Operator 패턴을 활용하여 Jenkins의 배포, 구성, 업그레이드 및 유지 관리를 간소화합니다.

일반적으로 Jenkins를 Kubernetes에 배포하려면 Pod, Service, PVC, ConfigMap 등을 각각 정의하고 관리해야 하는데, Jenkins Operator는 이 모든 과정을 자동화해서 사용자는 원하는 Jenkins 설정만 CRD(Custom Resource Definition)로 선언적으로 정의하면 됩니다. Jenkins Operator는 이러한 선언적 정의를 기반으로 Jenkins 인스턴스를 생성하고 관리합니다.

---

## 1. Architecture & Design

Jenkins Operator 설계에는 다음과 같은 개념이 포함되어 있습니다.

- 매니페스트의 모든 변경 사항을 감시하고, 배포된 커스텀 리소스 매니페스트에 정의된 원하는(desired) 상태를 유지
- 베이스(Base) 루프와 사용자(User) 루프라는 두 개의 더 작은 조정(Reconciliation) 루프로 구성된 메인 조정 루프를 구현

![Jenkins Operator Reconcile Process](/assets/img/ci-cd/jenkins/jenkins-operator/jenkins-operator-reconcile-process.webp)
> Jenkins Operator Reconcile Process

![Detailed Jenkins Operator Reconcile Process](/assets/img/ci-cd/jenkins/jenkins-operator/jenkins-operator-reconcile-process-detailed.webp)
> Detailed Jenkins Operator Reconcile Process

### 1.1. Base Reconciliation Loop

**Base reconciliation loop**는 Jenkins의 기본(Basic) 구성 요소를 원하는 상태로 유지(Reconcile)하는 역할을 담당하며, 다음을 포함합니다.

- **Ensure Manifests**: Manifests의 변경 사항을 지속적으로 감시하고 일관된 상태 유지
- **Ensure Jenkins Pod**: Jenkins 마스터 Pod를 생성하고 해당 Pod가 정상적으로 동작하는지 상태 검증
- **Ensure Jenkins Configuration**: Jenkins 인스턴스를 설정하고 보안 강화(Hardening), 플러그인의 초기 설정 등 Jenkins가 기본적으로 동작하기 위한 초기 구성 적용
- **Ensure Jenkins API Token**: Jenkins API 토큰을 생성하고 Jenkins API Client를 초기화

### 1.2. User Reconciliation Loop

**User Reconciliation Loop**는 사용자가 제공한 설정(User-provided configuration)을 원하는 상태로 유지(Reconcile) 하는 역할을 담당하며, 다음을 포함합니다.

- **Ensure Restore Job**: Restore Job을 생성하고 복구가 정상적으로 완료되었는지 확인
- **Ensure Seed Jobs**: Seed Job(초기 job 생성 작업)을 생성하고, 모든 Seed Job이 정상적으로 실행되었는지 확인
- **Ensure User Configuration**: Groovy Script나 Configuration as Code, 플러그인 설정 등 사용자가 제공한 설정을 실행
- **Ensure Backup Job**: Backup Job을 생성하고 백업이 정상적으로 수행되었는지 확인

### 1.3. Operator State

Operator의 상태를 Custom Resource(CR)의 status 필드에 저장되며, 여기에는 Operator가 관리하는 각종 설정 이벤트(configuration events) 또는 작업(Job)들의 상태가 기록됩니다. 이를 통해 Operator나 Jenkins가 재시작되더라도, 원래 의도한 Desired State를 유지하거나 복구할 수 있습니다.

---

## 2. Installing the Jenkins Operator

```shell
##############################################################
# Jenkins Namespace 생성
##############################################################
kubectl create namespace jenkins

##############################################################
# Jenkins Operator 설치
##############################################################
helm repo add jenkins https://raw.githubusercontent.com/jenkinsci/kubernetes-operator/master/chart
helm repo update
helm pull jenkins/jenkins-operator --version 0.8.1
tar -xvf jenkins-operator-0.8.1.tgz
cd jenkins-operator

cat <<EOF > custom_values.yaml
jenkins:
  enabled: true
  name: jenkins
  namespace: jenkins
  image: jenkins/jenkins:2.528.3-lts

  basePlugins:
  - name: kubernetes
    version: 4392.v19cea_fdb_5913
  - name: workflow-job
    version: 1546.v62a_c59c112dd
  - name: workflow-aggregator
    version: 608.v67378e9d3db_1
  - name: git
    version: 5.7.0
  - name: job-dsl
    version: "1.93"
  - name: configuration-as-code
    version: "1985.vdda_32d0c4ea_b_"
  - name: kubernetes-credentials-provider
    version: 1.299.v610fa_e76761a_

  service:
    type: NodePort
    port: 8080
    nodePort: 30003
EOF
helm upgrade -i -n jenkins jenkins . -f custom_values.yaml 

# NAME: jenkins
# LAST DEPLOYED: Wed Dec 10 23:18:32 2025
# NAMESPACE: jenkins
# STATUS: deployed
# REVISION: 1
# TEST SUITE: None
# NOTES:
# 1. Watch Jenkins instance being created:
# $ kubectl --namespace jenkins get pods -w

# 2. Get Jenkins credentials:
# $ kubectl --namespace jenkins get secret jenkins-operator-credentials-jenkins -o 'jsonpath={.data.user}' | base64 -d
# $ kubectl --namespace jenkins get secret jenkins-operator-credentials-jenkins -o 'jsonpath={.data.password}' | base64 -d

# 3. Connect to Jenkins (actual Kubernetes cluster):
# $ kubectl --namespace jenkins port-forward jenkins-jenkins 8080:8080

# Now open the browser and enter http://localhost:8080

##############################################################
# Jenkins Operator 설치 확인
##############################################################
# get-all krew 미설치시 설치 (kubectl krew install get-all)
kubectl get-all | grep -i jenkins
kubectl get crds | grep -i jenkins
# jenkins.jenkins.io                             2025-12-10T14:02:11Z

kubectl get pods,svc -n jenkins
# NAME                                            READY   STATUS    RESTARTS   AGE
# pod/jenkins-jenkins                             2/2     Running   0          10m
# pod/jenkins-jenkins-operator-5679c97c76-6v62p   1/1     Running   0          36m

# NAME                                     TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)          AGE
# service/jenkins-operator-http-jenkins    NodePort    10.43.171.181   <none>        8080:30003/TCP   36m
# service/jenkins-operator-slave-jenkins   ClusterIP   10.43.142.76    <none>        50000/TCP        36m

##############################################################
# Jenkins Instance 접속
##############################################################
# Username 확인
kubectl --namespace jenkins get secret jenkins-operator-credentials-jenkins -o 'jsonpath={.data.user}' | base64 -d

# 초기 Password 확인
kubectl --namespace jenkins get secret jenkins-operator-credentials-jenkins -o 'jsonpath={.data.password}' | base64 -d

open http://localhost:30003
```

![Jenkins Instance Login Page](/assets/img/ci-cd/jenkins/jenkins-operator/jenkins-instance-login-page.webp)
![Jenkins Instance Main Page](/assets/img/ci-cd/jenkins/jenkins-operator/jenkins-instance-main-page.webp)

---

## 3. References

- [Jenkins GitHub - kubernetes-operator](https://github.com/jenkinsci/kubernetes-operator)
- [Jenkins Docs - Architecture and Design](https://jenkinsci.github.io/kubernetes-operator/docs/how-it-works/architecture-and-design/)
- [Jenkins Docs - Installing the Operator](https://jenkinsci.github.io/kubernetes-operator/docs/getting-started/latest/installing-the-operator/)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
