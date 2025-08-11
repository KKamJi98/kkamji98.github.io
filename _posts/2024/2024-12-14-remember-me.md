---
title: Remember Me 프로젝트 후기
date: 2024-12-14 14:36:37 +0900
author: kkamji
categories: [Project]
tags: [aws, lambda, elk, log-stash, elasticsearch, kibana, terraform, terraform-cloud, hcp-terraform, mongodb, github-actions]     # TAG names should always be lowercase
comments: true
image:
  path: /assets/img/rememberme/rememberme_app.webp
---

2024년 11월부터 12월까지 약 2개월간 **Remember Me** 프로젝트를 진행했습니다. 해당 서비스는 **AWS Lambda**와 **Amazon API Gateway**를 기반으로 동작하는 서버리스(Serverless) 환경에서, 사용자가 단어를 외우고 관리할 수 있는 웹 애플리케이션입니다.

인프라 팀원으로서 **HCP Terraform(Terraform Cloud)을 이용한 AWS 인프라 프로비저닝**, **GitHub Actions를 통한 CI/CD 파이프라인 구축**, 그리고 **로그 수집·분석 환경(ELK Stack) 설정**에 주력했습니다.

> **GitHub**: <https://github.com/vocaAppServerless>  
> **Application Demo**: <https://youtu.be/y15djTDnXYg>  
> **HCP Terraform Demo**: <https://youtu.be/zg9rhHcf8w0?si=A6rGs7k0rcp9nD0u>  
> **WAF Rule & Slack Alarm Demo**: <https://youtu.be/S6AAgXVevEw?si=OiLR3wfE36uTpHYU>  
{: .prompt-tip}

---

## 1. Feature

- **서버리스 아키텍처**: **Lambda** + **API Gateway**로 서버리스 구현  
- **단어 암기 서비스**: 사용자별 단어 리스트 관리 및 퀴즈 기능 제공  
- **로그 분석 환경**: **CloudWatch Logs** -> **Logstash** -> **Elasticsearch** -> **Kibana** 파이프라인 구축  
- **IaC 및 CI/CD**: **Terraform(HCP Terraform)**으로 인프라 코드화, **GitHub Actions**으로 빌드/배포 자동화  
- **AWS SAM**: `sam local` 명령어를 통해 **Lambda** 함수와 **API Gateway**를 로컬에서 실행하고 디버깅  

---

## 2. Tech Stack

> **Frontend**  - React  
> **Backend**   - Node.js, AWS SAM CLI  
> **Database**  - MongoDB  
> **CI/CD**     - GitHub Actions  
> **Cloud(AWS)**- Lambda, API Gateway, S3, CloudFront, Route53, WAF, Parameter Store, Secrets Manager, Budgets, Chatbot  
> **IaC**       - Terraform (HCP Terraform)  
> **Logging**   - CloudWatch, Logstash, Elasticsearch, Kibana  
> **ETC**       - Git/GitHub, Slack, Notion  
{: .prompt-tip}

---

## 3. Infra

HCP Terraform을 사용해 GitHub와 연동, Terraform Cloud 환경을 구축하여 Terraform 코드 변경 시 자동으로 인프라가 업데이트되도록 했습니다. 모든 AWS 리소스(VPC, Lambda, API Gateway, S3, CloudFront 등)를 코드로 정의해 관리 용이성과 일관성을 확보했습니다.

![Architecture](/assets/img/rememberme/architecture.webp)

### 3.1 Logging

CloudWatch Logs Subscription Filter를 활용해 Lambda 로그를 실시간으로 Logstash -> Elasticsearch로 전송한 뒤 Kibana 대시보드를 통해 상태별, 로그그룹별 로그를 분석할 수 있도록 구현했습니다. 이를 통해 여러 Lambda에서 생성되는 Log Data를 한곳에서 관리할 수 있었고, 문제 발생 시 신속한 진단과 대응이 가능했습니다.

![Logging Workflow](/assets/img/rememberme/log_monitoring.webp)

![Kibana Dashboard](/assets/img/rememberme/kibana_dashboard.webp)

### 3.2 Alarm

AWS WAF의 규칙을 활용하여 비정상적으로 과도한 트래픽(예: 동일 IP에서 분당 300회 이상 요청)을 차단하였습니다. 또한, AWS Budgets와 CloudWatch를 연계하여 비용 초과 알림을 설정하고, Amazon SNS와 AWS Chatbot을 통해 Slack으로 실시간 알림을 받을 수 있도록 구성하였습니다.

#### 3.2.1 WAF Alarm

![WAF Alarm Workflow](/assets/img/rememberme/waf_alarm_workflow.webp)
![WAF Alarm](/assets/img/rememberme/waf_alarm.webp)

#### 3.2.2 Budget Alarm

![Budget Alarm Workflow](/assets/img/rememberme/budget_alarm_workflow.webp)
![Budgets Alarm](/assets/img/rememberme/budgets_alarm.webp)

### 3.3 CI/CD

GitHub Actions를 사용해 코드 변경 시 자동으로 빌드 및 배포가 진행되도록 했습니다.

- Backend 코드 변경 -> GitHub Actions 실행 -> SAM 빌드 -> Lambda 배포
- Frontend 코드 변경 -> GitHub Actions 실행 -> React 빌드 -> S3/CloudFront 업데이트

#### 3.3.1 Backend CI/CD

![Backend CI/CD](/assets/img/rememberme/backend_ci_cd.webp)

#### 3.3.2 Frontend CI/CD

![Frontend CI/CD](/assets/img/rememberme/frontend_ci_cd.webp)

---

## 4. 회고

이번 Remember Me 프로젝트를 진행하면서 **서버리스 기반 MSA(Microservices Architecture)**를 채택한 경험은 많은 도전과 배움을 제공했습니다. AWS Lambda와 API Gateway를 활용한 서버리스 환경에서의 개발은 인프라 관리의 부담을 크게 줄이는 장점이 있었지만, 동시에 MSA의 복잡성과 서버리스 아키텍처 특유의 한계도 경험할 수 있었습니다.

특히, 각 Lambda 함수에서 생성되는 로그가 CloudWatch Logs의 Log Group에 개별적으로 저장됨에 따라, 통합 로그 모니터링 시스템의 필요성과 중요성을 실감하게 되었습니다. 이를 해결하기 위해 Logstash, Elasticsearch, Kibana를 활용한 로그 분석 환경을 구축하며, 단순히 로그를 저장하는 것을 넘어 실시간 분석과 시각화의 가치를 배울 수 있었습니다.

또한, 로그나 리소스 모니터링에 있어 **알림 시스템(Alarm)**이 단순한 선택이 아니라 필수적인 요소임을 깨달았습니다. 실시간 알림을 통해 문제가 발생했을 때 빠르게 대응할 수 있는 체계를 갖추는 것이 프로젝트의 안정성을 크게 향상시킨다는 것을 배웠습니다.

이번 프로젝트는 서버리스 아키텍처와 MSA의 장점뿐만 아니라 그 한계까지 체감할 수 있는 귀중한 경험이었습니다. 이를 통해 시스템 설계와 운영에서 더 깊이 있는 고민을 하게 되었고, 앞으로의 프로젝트에 적용할 중요한 교훈을 얻을 수 있었습니다.

---
> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**
{: .prompt-info}
