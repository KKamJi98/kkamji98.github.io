---
title: AWS Bedrock Knowledge Base로 관리형 RAG 구축하기 - 데이터 소스부터 Retrieve API, 접근제어까지
date: 2026-07-02 09:00:00 +0900
author: kkamji
categories: [Cloud, AWS]
tags: [aws, bedrock, knowledge-base, rag, opensearch-serverless, pgvector, guardrails, ai]     # TAG names should always be lowercase
comments: true
image:
  path: /assets/img/aws/aws.webp
---

[RAG 시리즈](/posts/rag-overview-concept-and-pipeline/)에서 chunking, 임베딩, 벡터 DB, hybrid search, 보안까지 RAG 파이프라인을 직접 구성하는 관점으로 다뤘습니다. Amazon Bedrock Knowledge Bases는 이 중 데이터 수집, 파싱, 청킹, 임베딩, 색인, 검색을 서비스 API로 연결해 주는 선택지입니다. 현재 Bedrock은 저장소와 검색 인프라까지 Bedrock이 운영하는 **Managed Knowledge Base**와, 사용자가 벡터스토어를 선택하고 운영하는 **Customer-managed Knowledge Base**를 구분합니다. 이 글의 OpenSearch Serverless, Aurora, S3 Vectors 예시는 후자입니다. ingestion과 retrieval API는 Bedrock이 관리하지만 벡터스토어의 선택, 용량, 접근 정책은 사용자가 책임집니다.

이 글은 Bedrock Knowledge Base 자체를 이해하기 위한 기본편입니다. Google Docs 파싱, S3 Vectors, n8n workflow, Slack 멘션 봇까지 묶어 실제로 구축하며 밟은 함정들은 [Bedrock Knowledge Bases와 n8n으로 Slack RAG 챗봇 운영하기](/posts/bedrock-kb-slack-rag-chatbot/)에서 이어서 다룹니다.

---

## 1. TL;DR

> - Bedrock Knowledge Bases는 Managed Knowledge Base와 Customer-managed Knowledge Base로 나뉩니다. 이 글은 벡터스토어를 고르는 Customer-managed 구성을 다루며, ingestion과 retrieval API를 관리형으로 제공합니다.  
> - chunking은 `FIXED_SIZE / SEMANTIC / HIERARCHICAL / NONE`을 지원하고, 벡터스토어는 OpenSearch 계열, Aurora PostgreSQL(pgvector), Neptune, S3 Vectors, Pinecone, Redis Enterprise Cloud, MongoDB Atlas 등에서 고릅니다.  
> - 질의는 검색만 하는 **Retrieve**와 검색+생성을 함께 하는 **RetrieveAndGenerate** 두 API로 나뉘며, 후자는 citation을 반환합니다.  
> - 접근제어는 **metadata filtering**(문서별 권한/멀티테넌시)과 IAM service role로, PII/유해 콘텐츠는 **Bedrock Guardrails**로 처리합니다.  
> - 매니지드는 빠르게 시작할 수 있지만 파이프라인 세부 제어는 제한되므로, 통제 수준과 운영 부담의 trade-off로 선택합니다.  
{: .prompt-info}

---

## 2. Bedrock Knowledge Base란

Bedrock Knowledge Bases는 foundation model(FM)을 사내 데이터에 연결해 RAG를 수행하도록 해주는 기능입니다. 동작은 [RAG 1편](/posts/rag-overview-concept-and-pipeline/)에서 본 파이프라인과 같지만, ingestion과 retrieval을 서비스 API로 연결합니다. 이 글에서 다루는 Customer-managed 구성에서는 벡터스토어를 직접 선택하고 그 저장소의 운영 책임을 집니다.

- **데이터 위치만 지정**: S3 등에 문서를 두고 데이터 소스로 연결하면, Bedrock이 문서를 fetch하고 chunking, embedding, 벡터스토어 저장까지 자동 수행합니다.
- **출처 제공**: 검색으로 생성된 응답에 source attribution이 따라붙어, 어떤 문서에서 나온 답인지 확인할 수 있습니다. 이는 [RAG 7편](/posts/rag-llm-api-and-advanced/)에서 다룬 citation/grounding을 서비스가 기본 제공하는 형태입니다.
- **공통 API**: 벡터스토어 종류가 달라도 동일한 Retrieve / RetrieveAndGenerate API로 질의합니다.

즉 RAG 시리즈에서 다룬 개념을 그대로 두되, ingestion과 retrieval 구현 부담을 서비스로 넘기고 저장소 운영 책임의 범위를 선택하는 것이 핵심입니다.

Managed Knowledge Base는 Bedrock이 저장소, 인덱싱, retrieval 최적화까지 관리하는 별도 선택지입니다. 반면 다음 섹션의 OpenSearch Serverless, Aurora, Neptune, S3 Vectors 연결은 Customer-managed 구성입니다. 두 유형의 차이를 먼저 구분해야 "관리형"이라는 말이 벡터스토어 운영까지 대신한다는 뜻으로 오해되지 않습니다.

![Amazon Bedrock Knowledge Base 전체 구조 - 관리형 ingestion은 S3와 connector의 문서를 fetch, parse, chunk, embed해 vector store에 색인합니다. 질의는 Agent Runtime에서 IAM과 metadata filter를 적용한 뒤 top-k chunk를 검색하고, foundation model이 출처 기반 Answer와 Citation을 생성합니다.](/assets/img/aws/bedrock-kb-architecture.webp)

---

## 3. 구성 요소

### 3.1. 데이터 소스와 파싱

데이터 소스는 S3를 비롯한 위치를 가리킵니다. 하나의 Knowledge Base에 데이터 소스를 여러 개(최대 5개) 연결할 수 있습니다. 표/레이아웃이 복잡한 문서는 **advanced parsing**(FM 기반 파싱) 옵션으로 구조를 더 잘 추출할 수 있습니다.

### 3.2. Chunking 전략

Bedrock은 [RAG 2편](/posts/rag-chunking-embedding-contextual-retrieval/)에서 다룬 청킹 전략을 옵션으로 제공합니다(`ChunkingConfiguration`).

| 전략           | 설명                                                        |
| :------------- | :---------------------------------------------------------- |
| `FIXED_SIZE`   | 지정한 근사 크기로 균등 분할                                |
| `SEMANTIC`     | NLP로 의미가 유사한 내용을 묶어 분할                        |
| `HIERARCHICAL` | parent/child 계층 분할. 검색은 child, 생성엔 parent로 확장  |
| `NONE`         | 파일 하나를 청크 하나로 취급(사전 분할 전제)                |

`HIERARCHICAL`은 2편에서 본 parent-child(small-to-big)와 같은 개념으로, parent/child 토큰 크기와 overlap을 설정합니다. 단 S3 Vectors를 벡터스토어로 쓸 때는 권장되지 않습니다(메타데이터 크기 제한).

### 3.3. 임베딩 모델과 벡터스토어

임베딩 모델은 Amazon Titan Embeddings, Cohere 등에서 고릅니다([RAG 2편](/posts/rag-chunking-embedding-contextual-retrieval/)의 임베딩 선택 기준이 그대로 적용됩니다). 벡터스토어는 데이터 소스 유형에 따라 다음에서 선택합니다([RAG 3편](/posts/rag-vector-database-and-index/)의 벡터 DB 선택과 대응).

| 벡터스토어                         | 특징                                        |
| :--------------------------------- | :------------------------------------------ |
| OpenSearch Serverless              | 콘솔의 quick create 또는 기존 collection 연결 |
| OpenSearch Service Managed Clusters | 관리형 OpenSearch domain 연결               |
| Aurora PostgreSQL (pgvector)       | 관계형 DB + 벡터, SQL/트랜잭션과 함께        |
| Amazon Neptune                     | 그래프와 벡터 검색을 함께 다루는 선택지      |
| S3 Vectors                         | 저빈도 semantic search에 적합한 벡터 저장    |
| Pinecone / Redis Enterprise Cloud / MongoDB Atlas | 기존 외부 벡터 DB를 연결          |

콘솔에서 지원하는 스토어는 quick create를 선택할 수 있고, 이미 준비한 스토어도 연결할 수 있습니다. 어떤 스토어가 quick create 대상인지는 리전과 콘솔 옵션을 생성 시점에 확인합니다.

---

## 4. 콘솔로 구축하기

가장 빠른 경로는 콘솔입니다.

1. Bedrock 콘솔에서 **Orchestration -> Knowledge bases -> Create knowledge base**.
2. 이름과 설명을 입력하고, **IAM Permissions**에서 기본 옵션을 선택합니다(S3 등 접근용 service role이 자동 생성됩니다).
3. **데이터 소스**를 S3 버킷으로 지정합니다(최대 5개).
4. **임베딩 모델**(예: Titan Embeddings)과 **벡터스토어**를 선택합니다. 기본은 `Quick create a new vector store`(OpenSearch Serverless)입니다.
5. 검토 후 생성하면 Bedrock이 embedding 생성과 저장(ingestion)을 진행하고, 상태가 **Ready**가 되면 준비 완료입니다.

문서가 갱신되면 데이터 소스를 다시 **sync**해 재색인합니다.

---

## 5. IaC로 구축하기

반복/버전관리가 필요하면 IaC로 정의합니다. CloudFormation 기준 핵심 리소스는 `AWS::Bedrock::KnowledgeBase`와 `AWS::Bedrock::DataSource`입니다.

```yaml
Resources:
  PolicyKB:
    Type: AWS::Bedrock::KnowledgeBase
    Properties:
      Name: policy-kb
      RoleArn: !GetAtt KbServiceRole.Arn          # S3/모델 접근 권한을 가진 service role
      KnowledgeBaseConfiguration:
        Type: VECTOR
        VectorKnowledgeBaseConfiguration:
          EmbeddingModelArn: arn:aws:bedrock:ap-northeast-2::foundation-model/amazon.titan-embed-text-v2:0
      StorageConfiguration:
        Type: OPENSEARCH_SERVERLESS              # 또는 RDS(pgvector), PINECONE 등
        # OpensearchServerlessConfiguration: { ... }

  PolicyDataSource:
    Type: AWS::Bedrock::DataSource
    Properties:
      KnowledgeBaseId: !Ref PolicyKB
      Name: policy-docs
      DataSourceConfiguration:
        Type: S3
        S3Configuration:
          BucketArn: arn:aws:s3:::my-policy-bucket
      VectorIngestionConfiguration:
        ChunkingConfiguration:
          ChunkingStrategy: HIERARCHICAL         # FIXED_SIZE | SEMANTIC | HIERARCHICAL | NONE
```

CDK를 쓴다면 `aws-bedrock` 계열 construct로, Terraform이라면 `aws_bedrockagent_knowledge_base` / `aws_bedrockagent_data_source` 리소스로 동일한 구조를 표현합니다. 어떤 방식이든 개념 축(임베딩 모델, 벡터스토어, chunking, 데이터 소스)은 같습니다.

---

## 6. 질의: Retrieve와 RetrieveAndGenerate

질의는 목적에 따라 두 API로 나뉩니다. 컨트롤 플레인(생성/설정)은 `bedrock-agent`, 런타임 질의는 `bedrock-agent-runtime` 엔드포인트를 사용합니다.

- **Retrieve**: 검색만 수행해 관련 청크를 반환합니다. 결과를 직접 다루거나 별도 모델로 넘길 때 씁니다.

```bash
aws bedrock-agent-runtime retrieve \
  --knowledge-base-id "KB123456" \
  --retrieval-query '{"text": "출장 숙박비 한도가 얼마인가"}' \
  --retrieval-configuration '{"vectorSearchConfiguration": {"numberOfResults": 5}}'
```

- **RetrieveAndGenerate**: 검색 + FM 생성을 한 번에 수행하고, 응답과 함께 인용(retrievedReferences)을 반환합니다.

```bash
aws bedrock-agent-runtime retrieve-and-generate \
  --input '{"text": "출장 숙박비 한도가 얼마인가"}' \
  --retrieve-and-generate-configuration '{
    "type": "KNOWLEDGE_BASE",
    "knowledgeBaseConfiguration": {
      "knowledgeBaseId": "KB123456",
      "modelArn": "arn:aws:bedrock:ap-northeast-2::foundation-model/anthropic.claude-3-5-sonnet-20240620-v1:0"
    }
  }'
```

두 API 모두 `retrievalConfiguration`에서 벡터 검색을 커스터마이즈합니다. 특히 `rerankingConfiguration`으로 기본 랭킹 위에 별도 reranking 모델을 얹을 수 있는데, 이는 [RAG 4편](/posts/rag-hybrid-search-and-reranking/)의 reranking을 서비스 옵션으로 제공하는 것입니다. query decomposition은 `RetrieveAndGenerate`의 orchestration 설정에서 복합 질의를 하위 질의로 나누는 옵션입니다. 멀티턴 문맥은 `RetrieveAndGenerate` 첫 응답에서 발급된 `sessionId`를 같은 세션의 후속 요청에 재사용할 때 유지됩니다.

---

## 7. 보안과 접근제어

[RAG 5편](/posts/rag-security-and-access-control/)에서 다룬 보안 원칙이 Bedrock에서 어떻게 구현되는지가 실무에서 가장 중요합니다.

### 7.1. Metadata filtering (문서별 권한 / 멀티테넌시)

기본적으로 Knowledge Base 질의는 벡터스토어 전체를 대상으로 합니다. 문서에 메타데이터를 붙여 두면, Retrieve/RetrieveAndGenerate의 `filter`로 검색 범위를 제한할 수 있습니다. 이는 문서별 접근제어와 멀티테넌시를 구현하는 검색 범위 제한 수단입니다.

```json
{
  "vectorSearchConfiguration": {
    "numberOfResults": 5,
    "filter": {
      "andAll": [
        { "equals":   { "key": "department", "value": "hr" } },
        { "greaterThanOrEquals": { "key": "effective_year", "value": 2025 } }
      ]
    }
  }
}
```

`equals`, `notEquals`, `greaterThan(OrEquals)`, `lessThan(OrEquals)`, `in`, `startsWith`, `andAll`, `orAll` 등의 연산자를 조합합니다. 애플리케이션 서버가 인증된 사용자 권한(role/tenant)에서 filter를 **서버 측에서 생성하고 강제**하면, [RAG 5편](/posts/rag-security-and-access-control/)에서 강조한 "권한 검사는 LLM 앞단(retrieval)에서 deny-by-default"를 구현할 수 있습니다. 클라이언트가 filter 값을 임의로 정하게 두거나 IAM만으로 이 조건을 강제할 수는 없으므로, filter는 독립된 인가 체계를 대체하지 않습니다.

### 7.2. IAM service role

Knowledge Base는 S3 데이터 소스와 임베딩 모델에 접근할 service role이 필요합니다. 최소 권한 원칙으로, 해당 버킷과 사용할 모델로만 권한을 좁힙니다.

### 7.3. Guardrails (PII / injection / 유해 콘텐츠)

[RAG 5편](/posts/rag-security-and-access-control/)의 PII 처리와 prompt injection 방어는 **Bedrock Guardrails**로 상당 부분 대응됩니다. Knowledge Base 질의(RetrieveAndGenerate)에 guardrail을 연결하면, 사용자 입력과 LLM 생성 응답에 다음을 적용합니다. 검색으로 가져온 reference 자체에는 guardrail이 적용되지 않습니다.

- **Sensitive information filters**: Email/Phone/Name/SSN/Credit card 등 PII를 `Anonymize`(마스킹) 또는 `Block` 처리하고, custom regex로 사내 식별자 유형을 추가할 수 있습니다.
- **Content filters**: prompt attack(injection 포함), 혐오/폭력 등 유해 콘텐츠를 임계값 기반으로 차단합니다.

다만 Guardrails의 출력측 PII 마스킹은 [RAG 5편](/posts/rag-security-and-access-control/)에서 강조한 **ingestion 단계 redaction**을 완전히 대체하지 않습니다. 민감정보가 애초에 벡터스토어에 들어가지 않게 하려면, S3에 올리기 전 원본 정제를 병행하는 편이 안전합니다.

---

## 8. RAG 시리즈 개념과의 매핑

직접 구축(RAG 시리즈)과 Bedrock Knowledge Base의 대응을 정리하면 다음과 같습니다.

| RAG 시리즈 개념                     | Bedrock Knowledge Base                          |
| :---------------------------------- | :---------------------------------------------- |
| chunking 전략(2편)                  | `ChunkingConfiguration`(FIXED/SEMANTIC/HIERARCHICAL) |
| 임베딩 모델 선택(2편)               | Titan/Cohere 등 embedding model 선택            |
| 벡터 DB(3편)                        | OpenSearch Serverless / Aurora pgvector 등      |
| reranking(4편)                      | `rerankingConfiguration`                        |
| 권한 기반 retrieval(5편)            | metadata `filter` + IAM service role            |
| PII / injection 방어(5편)           | Bedrock Guardrails (+ ingestion redaction 병행) |
| citation / grounding(7편)           | RetrieveAndGenerate의 source attribution        |

---

## 9. 언제 매니지드를 선택하나

Bedrock Knowledge Base는 파이프라인 구현/운영을 크게 줄여 주지만, 대신 세부 제어가 제한됩니다.

- **매니지드가 유리**: 빠르게 RAG를 올려야 하고, chunking/embedding/벡터스토어 운영을 직접 하고 싶지 않으며, AWS 생태계(IAM, Guardrails, S3) 안에서 통합 관리하려는 경우.
- **직접 구축이 유리**: Contextual Retrieval 같은 커스텀 ingestion, 세밀한 hybrid search/reranking 튜닝, 특정 벡터스토어 최적화 등 파이프라인 단계를 세부 제어해야 하는 경우([RAG 시리즈](/posts/rag-overview-concept-and-pipeline/)의 접근).

결국 [RAG 시리즈](/posts/rag-overview-concept-and-pipeline/)에서 다룬 원리를 이해하고 있어야, 매니지드 서비스의 옵션(어떤 chunking을 고르고, 어떤 벡터스토어를 쓰고, filter를 어떻게 짤지)을 제대로 선택할 수 있습니다. 매니지드는 원리를 대체하는 게 아니라 구현을 대신해 줄 뿐입니다.

---

## 10. Reference

- [AWS Docs - How Amazon Bedrock knowledge bases work](https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base.html)
- [AWS Docs - Build a managed knowledge base](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-build-managed.html)
- [AWS Docs - How content chunking works for knowledge bases](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-chunking.html)
- [AWS Docs - Query a knowledge base and generate responses](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-test-retrieve-generate.html)
- [AWS Docs - Configure and customize knowledge base queries](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-test-config.html)
- [AWS Docs - AWS::Bedrock::KnowledgeBase (CloudFormation)](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-bedrock-knowledgebase.html)
- [AWS - Multi-tenancy in RAG with a single Bedrock knowledge base and metadata filtering](https://aws.amazon.com/blogs/machine-learning/multi-tenancy-in-rag-applications-in-a-single-amazon-bedrock-knowledge-base-with-metadata-filtering/)
- [AWS - Introducing guardrails in Amazon Bedrock Knowledge Bases](https://aws.amazon.com/blogs/machine-learning/introducing-guardrails-in-knowledge-bases-for-amazon-bedrock/)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
