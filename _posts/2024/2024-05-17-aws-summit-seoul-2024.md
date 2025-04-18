---
title: AWS Summit Seoul 2024
date: 2024-05-17 21:53:31 +0900
author: kkamji
categories: [AWS]
tags: [aws summit seoul, aws, summit, karpenter, region, ha, ft, monitoring, vectordb, opensearch, llm, rag]     # TAG names should always be lowercase
comments: true
image:
    path: /assets/img/aws/aws.webp
---

AWS Summit은 AWS에서 주최하는 국내 최대의 IT 클라우드 행사입니다. 클라우드 기술을 선도하는 다양한 회사들이 참여하며, 다양한 성공 사례와 최신 기술 트렌드를 접할 수 있습니다.

내가 중요하다고 생각하는 기술과 현재 산업에서 사용하는 기술은 다를 수 있습니다. 따라서 나의 현재 생각만을 고집하지 않고, 다양한 성공 사례를 접하여 더 나은 전략을 고려해야 한다고 생각합니다. 이 때문에 AWS Summit Seoul 2024에 참석하기로 마음먹었습니다. 이 포스트에서는 제가 어떤 강연을 듣고 어떤 생각을 하게 되었는지, 느낀 점을 이야기해 보려 합니다.

---

## 드라마앤컴퍼니 채용의 혁신: Amazon OpenSearch로 열어가는 미래
> AWS 현진환 SA와 드라마앤컴퍼니 황호현 AI/ML 연구원님께서 발표를 진행하셨습니다.
{: .prompt-tip}

현진환 SA님은 2025년까지 생성될 데이터의 약 80%가 이미지, 비디오, 오디오와 같은 비정형 데이터가 될 것으로 예측된다고 했습니다. 생성형 AI 모델로 비정형 데이터를 벡터화하여 저장하면 데이터 유형에 관계없이 다양한 검색 기법을 적용할 수 있을 것이라 이야기했습니다. 많은 기업들이 검색과 생성형 AI를 융합한 챗봇을 통한 대화형 검색 서비스 개발에 주력하고 있다는 점도 강조하셨습니다.

황호현 연구원님은 드라마앤컴퍼니의 명함관리 서비스인 리멤버에 OpenSearch Service를 도입한 후 텍스트 분석, 머신러닝 기반 분석, 머신러닝 기반 검색을 통해 채용에 적합한 인재풀을 효율적으로 탐색한 성공 사례를 발표하셨습니다.

해당 강연을 듣고 LLM, RAG, Machine Learning의 중요성에 대해 다시 한번 생각해보게 되었고, 특히 VectorDB의 사용 사례를 통해 VectorDB에 대해 학습해보자는 계기를 갖게 되었습니다.

---

## 삼성계정은 DR에 진심, 글로벌 리전 장애 조치 아키텍처 사례
> 삼성전자 김재민 엔지니어님께서 발표를 진행하셨습니다.
{: .prompt-tip}

삼성계정은 17억 명 이상의 사용자가 사용하는 계정으로, 계획되지 않은 다운타임은 재무적 손실과 브랜드 이미지에 큰 피해를 줄 수 있기에 고가용성(HA)과 내결함성(FT)이 중요하다고 하셨습니다. 삼성계정은 낮은 RTO(Recovery Time Objective)를 실현하기 위해 글로벌 Active/Active 아키텍처로 2개의 리전에서 3개의 리전으로 늘려서 사용하고 있으며, 리전 단위 장애가 발생했을 때 대용량 트래픽을 저비용으로 효율적으로 전환하기 위해 DNS 기반 트래픽 전환 제어 방법을 선택했다고 했습니다. 또한 트래픽 분산을 위해 지리적 라우팅 방법을 선택했다고 하셨습니다. 새로 도입할 1개의 리전이 정상적으로 동작하는지 확인하기 위해 가중치 기반 라우팅을 사용하여 새로운 리전으로 유입되는 트래픽 양을 점점 늘려가며 테스트했다고 합니다. 마지막으로 조 리자드의 명언으로 발표를 마무리하셨습니다:

> "성공으로 가는 엘리베이터는 고장입니다. 당신은 계단을 이용해야만 합니다. 한 계단, 한 계단씩."  
{: .prompt-info}

해당 강연을 듣기 전에는 Multi Region 구성이 웬만한 대기업이 아닌 이상 운영유지 비용이 많이 들어 약간의 다운타임을 감안하고 비용적인 측면에서 이점을 가져가는 것이 낫다고 생각했지만, 이번 사례를 통해 삼성의 기술력과 자본력, 그리고 삼성의 시스템에 대한 HA와 FT에 대한 진심을 알 수 있었습니다.

추가 강연
- AWS로 실현하는 철저한 보안 전략
- Karpenter로 클러스터 최적화
- 하시코프의 Vault 서비스와 클라우드 시크릿의 보안 생명주기 관리

해당 강연들을 통해 **Karpenter와 HashiCorp의 Vault, DataDog** 서비스에 대해 깊게 공부해봐야겠다는 생각을 하게 되었습니다. 또한, 행사에서 메가존, DataDog, 와탭랩스, GS 네오텍, LG CNS 등 평소에 관심이 있고 취업을 희망하는 회사들의 부스를 방문해 자사 서비스에 대한 설명을 들으니 더 가고 싶어졌습니다.

AWS Summit에 함께 참가해준 AWS Cloud School 1기 동기들에게 감사하며, 다음에는 회사의 이름을 대표하여 AWS Summit에서 만나자는 약속을 지키기 위해 노력해보겠습니다.

> **궁금하신 점이나 추가해야할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKam.\_\.Ji](https://www.linkedin.com/in/taejikim/)**
{: .prompt-info}
