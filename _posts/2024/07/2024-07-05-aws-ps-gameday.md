---
title: AWS PS GameDay 후기 및 느낀점
date: 2024-07-05 20:41:14 +0900
author: kkamji
categories: [Cloud, AWS]
tags: [aws, public-sector-day, bedrock, party-rock, lambda, gameday]     # TAG names should always be lowercase
comments: true
image:
  path: /assets/img/project/ps-gameday/ps-gameday-final.png
---

7월 4일 열린 [AWS Public Sector Day Seoul 2024](https://pages.awscloud.com/public-sector-day-seoul-2024.html#about)에서 [Generative AI Unicorn Party GameDay](https://aws.amazon.com/ko/gameday/)에 참가하였습니다.

---

## 1. 준비 과정

Generative AI 라는 주제에 맞게 생성형 AI를 사용할 것이라 생각했고, 사전 공지된 자료를 확인해보니 다음과 같은 단서를 구할 수 있었습니다.

### 1.1. 관련 서비스

- Amazon Bedrock
- Amazon Transcribe
- Amazon S3
- Amazon API Gateway
- Amazon DynamoDB
- AWS Lambda
- AWS Cloud9
- AWS Step Functions
- PartyRock

### 1.2. 예상 시나리오

1. S3와 Transcribe, Bedrock이 포함되어 있어, S3에 저장된 음성 파일을 텍스트로 변환하는 작업이 있을 것이라 예상했습니다.
2. DynamoDB, Bedrock, Lambda를 활용하여 특정 회사나 기술에 대한 정보를 DynamoDB에 저장하고, LangChain이나 RAG를 사용해 챗봇을 구현할 수 있을 것이라 생각했습니다.
3. API Gateway를 통해 여러 개의 서비스를 연동해야 할 가능성이 높다고 판단했습니다.

따라서 이 시나리오에 사용될 기술들을 중심으로 학습하려 했고, 외부에 공개되어있는 AWS 워크샵 자료를 통해 실습을 하며 대회를 준비했습니다.

---

## 2. 대회 진행

![alt text]({{ "/assets/img/project/ps-gameday/winners.jpg" | relative_url }})
![alt text]({{ "/assets/img/project/ps-gameday/winners2.jpg" | relative_url }})

[김지우](https://www.linkedin.com/in/kim-jiwoo-3b4828184/), [김진우](https://www.linkedin.com/in/jinwoo-kim-2aa0362a6/), [최보현](https://www.linkedin.com/in/bohyunchoi/), [김태지](https://www.linkedin.com/in/taejikim/) 이렇게 4인이서 **'자 드가자'** 팀을 이뤘고, '꼴등만 면하자'라는 마음가짐으로 대회에 임했습니다. 초반부터 실무 경험이 풍부한 실무진으로 구성된 팀들이 빠르게 상위권으로 치고 올라갔습니다. 우리는 다른 팀 신경쓰지말고 차분하게 현재 문제에만 집중하려 노력했습니다.

![GameDay 진행 사진]({{ "/assets/img/project/ps-gameday/ps-gameday.png" | relative_url }})  
그 결과 중반에는 3등까지 올라갈 수 있었고, 현재 순위를 지키고 싶다는 욕심이 생겨 더욱 열심히 했습니다. 그 때부터 시간이 엄청 빠르게 흐르는 것 같은 느낌을 받았습니다.

---

## 3. 마무리

![GameDay 최종 결과 사진]({{ "/assets/img/project/ps-gameday/ps-gameday-final.png" | relative_url }})  

결국 5등으로 마무리하게 되었고, 대회의 시나리오를 통해 Bedrock 서비스를 사용해 결과물을 도출해내는 과정이 되게 재미있었습니다. 다음에 또 기회가 생긴다면 꼭 다시 참가하고 싶습니다.

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
