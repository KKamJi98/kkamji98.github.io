---
title: Remember Me 프로젝트 후기
date: 2024-12-14 14:36:37 +0900
author: kkamji
categories: [Project]
tags: [aws, lambda, elk, log-stash, elasticsearch, kibana, terraform, terraform-cloud, hcp-terraform, mongodb, github-actions]     # TAG names should always be lowercase
comments: true
image:
  path: /assets/img/project/rememberme/rememberme_app.webp
---

2024년 11월부터 12월까지 약 2개월간 **Remember Me** 프로젝트를 진행했습니다. 이 서비스는 AWS Lambda와 Amazon API Gateway 기반의 서버리스(Serverless) 웹 애플리케이션으로, 사용자가 단어를 외우고 관리합니다.

인프라 팀원으로서 HCP Terraform(Terraform Cloud)으로 AWS 인프라를 프로비저닝하고, GitHub Actions로 CI/CD 파이프라인을 만들고, 로그 수집과 분석 환경(ELK Stack)을 설정하는 일을 맡았습니다.

> **GitHub**: <https://github.com/vocaAppServerless>  
> **Application Demo**: <https://youtu.be/y15djTDnXYg>  
> **HCP Terraform Demo**: <https://youtu.be/zg9rhHcf8w0?si=A6rGs7k0rcp9nD0u>  
> **WAF Rule & Slack Alarm Demo**: <https://youtu.be/S6AAgXVevEw?si=OiLR3wfE36uTpHYU>  
{: .prompt-tip}

> **TL;DR**  
> - 2024년 11월부터 12월까지 진행한 서버리스 단어 암기 서비스 프로젝트 회고입니다. 인프라 담당으로 프로비저닝, CI/CD, 로그 분석 환경을 맡았습니다.  
> - HCP Terraform을 GitHub와 연동해 코드 변경이 곧 인프라 변경이 되도록 구성하고, VPC부터 Lambda, API Gateway, S3, CloudFront까지 코드로 정의했습니다.  
> - 서버리스 MSA에서 가장 크게 체감한 문제는 로그가 함수마다 흩어진다는 점이었고, CloudWatch Logs Subscription Filter로 Logstash와 Elasticsearch에 모아 Kibana에서 함께 보도록 해결했습니다.  
{: .prompt-info}

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

HCP Terraform을 GitHub와 연동해 Terraform Cloud 환경을 구축했고 Terraform 코드가 변경되면 인프라가 자동으로 업데이트됩니다. 모든 AWS 리소스(VPC, Lambda, API Gateway, S3, CloudFront 등)를 코드로 정의해 관리하기 쉽고 설정도 일관되게 유지했습니다.

![Architecture](/assets/img/project/rememberme/architecture.webp)

### 3.1. Logging

CloudWatch Logs Subscription Filter로 Lambda 로그를 실시간으로 Logstash -> Elasticsearch로 전송한 뒤 Kibana 대시보드에서 상태별, 로그그룹별로 로그를 분석하도록 구현했습니다. 여러 Lambda가 남기는 Log Data를 한곳에서 관리하니 문제가 생겼을 때 원인을 빠르게 찾고 대응할 수 있었습니다.

![Logging Workflow](/assets/img/project/rememberme/log_monitoring.webp)

![Kibana Dashboard](/assets/img/project/rememberme/kibana_dashboard.webp)

### 3.2. Alarm

AWS WAF 규칙으로 과도한 트래픽(예: 동일 IP에서 분당 300회 이상 요청)을 차단했습니다. AWS Budgets와 CloudWatch를 연계해 비용 초과 알림을 설정하고 Amazon SNS와 AWS Chatbot으로 Slack에 실시간 알림이 오도록 구성했습니다.

#### 3.2.1. WAF Alarm

![WAF Alarm Workflow](/assets/img/project/rememberme/waf_alarm_workflow.webp)
![WAF Alarm](/assets/img/project/rememberme/waf_alarm.webp)

#### 3.2.2. Budget Alarm

![Budget Alarm Workflow](/assets/img/project/rememberme/budget_alarm_workflow.webp)
![Budgets Alarm](/assets/img/project/rememberme/budgets_alarm.webp)

### 3.3. CI/CD

GitHub Actions를 사용해 코드 변경 시 자동으로 빌드 및 배포가 진행되도록 했습니다.

- Backend 코드 변경 -> GitHub Actions 실행 -> SAM 빌드 -> Lambda 배포
- Frontend 코드 변경 -> GitHub Actions 실행 -> React 빌드 -> S3/CloudFront 업데이트

#### 3.3.1. Backend CI/CD

![Backend CI/CD](/assets/img/project/rememberme/backend_ci_cd.webp)

#### 3.3.2. Frontend CI/CD

![Frontend CI/CD](/assets/img/project/rememberme/frontend_ci_cd.webp)

---

## 4. 회고

이번 Remember Me 프로젝트에서는 서버리스 기반 MSA(Microservices Architecture)를 채택했고 그 과정에서 많이 부딪히고 배웠습니다. AWS Lambda와 API Gateway를 쓰는 서버리스 환경에서 개발하니 인프라 관리 부담이 크게 줄었지만 MSA의 복잡함과 서버리스 아키텍처 특유의 한계도 함께 겪었습니다.

각 Lambda 함수의 로그가 CloudWatch Logs의 Log Group에 개별적으로 쌓이니 통합 로그 모니터링 시스템이 왜 필요한지 실감했습니다. Logstash, Elasticsearch, Kibana로 로그 분석 환경을 구축하면서 로그를 저장하는 데서 끝내지 않고 실시간 분석과 시각화까지 해 보며 그 가치를 배웠습니다.

로그와 리소스 모니터링에서 알림 시스템(Alarm)은 선택이 아니라 필수였습니다. 실시간 알림으로 문제를 바로 인지하고 대응하는 체계를 갖추면서 프로젝트 안정성이 크게 올라갔습니다.

서버리스 아키텍처와 MSA의 장점과 한계를 모두 직접 확인한 프로젝트였습니다. 시스템을 설계하고 운영할 때 무엇을 먼저 따져야 하는지 감이 잡혔고, 앞으로 진행할 프로젝트에도 적용할 교훈을 얻었습니다.

---

## 5. Reference

- [github.com - vocaAppServerless](https://github.com/vocaAppServerless)
- [youtu.be - y15djTDnXYg](https://youtu.be/y15djTDnXYg)
- [youtu.be - zg9rhHcf8w0](https://youtu.be/zg9rhHcf8w0?si=A6rGs7k0rcp9nD0u)
- [youtu.be - S6AAgXVevEw](https://youtu.be/S6AAgXVevEw?si=OiLR3wfE36uTpHYU)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
