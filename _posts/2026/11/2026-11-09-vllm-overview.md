---
title: vLLM - LLM 추론과 서빙의 원리
description: "vLLM이 LLM 추론 요청을 실행하고 서비스하는 구조를 설명합니다. Prefill과 decode, KV cache의 블록 관리, continuous batching 및 OpenAI 호환 API의 역할과 운영상 한계를 구분합니다."
date: 2026-11-09 01:04:22 +0900
author: kkamji
categories: [AI, LLM]
tags: [llm, vllm, inference, serving, kv-cache, pagedattention]
comments: true
published: true
image:
  path: /assets/img/ai/vllm/vllm-overview-cover.webp
  width: 1920
  height: 1080
  alt: vLLM의 모델 실행과 요청 처리, KV cache 및 API 서빙
---

LLM 모델 하나를 불러와 질문 하나에 답하게 할 때는 입력을 넣고 출력을 기다리면 됩니다. 그런데 짧은 질문과 긴 문서 요약 요청이 동시에 들어오면 어떻게 실행해야 할까요? 요청마다 생성 길이가 다르고, 생성 중에 보관해야 할 정보도 계속 늘어납니다. vLLM은 이런 추론 요청을 제한된 연산 자원과 메모리 안에서 실행하고 서비스로 제공하는 오픈소스 프로젝트입니다.

**모델 가중치를 메모리에 올리는 것과 여러 사용자의 요청을 안정적으로 처리하는 것은 다른 문제입니다.** vLLM의 역할은 이 차이에서 시작합니다.

---

## 1. 모델 가중치, 추론 엔진과 API 서버

모델의 weights는 학습으로 얻은 매개변수입니다. 모델 구조에 따라 이 수치를 사용해 입력을 처리하고 다음 토큰의 확률을 계산합니다. 가중치 파일 자체가 HTTP 요청을 받거나 여러 사용자의 실행 순서를 정하는 것은 아닙니다.

| 구성 | 맡는 일 |
| --- | --- |
| 모델 가중치와 구조 | 입력에서 다음 토큰을 예측하는 계산을 정의 |
| 추론 엔진 | 모델 계산을 실행하고 요청 순서, 배치와 중간 상태를 관리 |
| API 서버 | HTTP 입력을 받아 처리하고 결과를 클라이언트에 전달 |

vLLM은 추론 엔진과 온라인 서빙 인터페이스를 함께 제공합니다. 현재 V1의 GPU 실행 구조에서는 API server가 입력 처리와 응답 streaming을 맡고, engine core가 scheduler와 KV cache를 관리하며, worker가 가중치를 로드하고 모델 계산을 실행합니다. 역할이 나뉘어 있다는 설명이지, 모든 환경에 같은 수의 프로세스나 서버를 배치한다는 뜻은 아닙니다.

HTTP 서버 없이 Python의 `LLM` 클래스로 추론하는 방식도 있습니다. 따라서 API 서버는 vLLM을 사용하는 진입점 중 하나이고, 엔진의 핵심은 그 뒤에서 요청과 계산을 관리하는 부분입니다.

---

## 2. 첫 토큰을 만드는 prefill과 그다음 decode

일반적인 decoder-only Transformer의 텍스트 생성을 기준으로 보겠습니다. 사용자가 보낸 문자열은 먼저 tokenization을 거쳐 토큰으로 바뀝니다. 대화형 모델이라면 chat template을 사용해 역할과 메시지를 모델이 이해할 입력 형식으로 구성합니다.

Prefill은 이미 주어진 입력 토큰을 처리하는 단계입니다. 각 attention 계층에서 key와 value를 만들고, 첫 출력 토큰을 선택할 logits도 계산합니다. 입력 토큰을 알고 있으므로 여러 위치의 계산을 병렬화할 수 있습니다. Prefill은 캐시만 채우고 기다리는 준비 작업이 아니라 첫 토큰을 만드는 계산에도 참여합니다.

이후 기본적인 autoregressive decode에서는 직전까지의 문맥을 바탕으로 다음 토큰을 순차적으로 생성합니다. 앞에서 처리한 토큰의 key와 value는 KV cache에 보관해 다시 사용합니다. 매번 과거 토큰의 K와 V를 처음부터 계산하지 않도록 하는 것입니다.

**KV cache는 과거 K와 V의 재계산을 줄이지만, 현재 토큰이 과거 문맥을 참고하는 attention 계산까지 없애지는 않습니다.** 현재 query와 캐시된 key의 관계를 계산하고 value를 결합하는 작업은 계속 필요합니다.

캐시는 계산을 줄이는 대신 메모리를 차지합니다. 일반적인 full attention에서는 문맥이 길어질수록 저장할 KV가 늘어납니다. 동시에 처리하는 요청이 많아지면 그 요청들의 KV도 함께 유지해야 합니다. 모델 가중치가 들어갈 공간이 있어도 원하는 문맥 길이와 동시성을 감당하지 못할 수 있는 이유입니다.

---

## 3. PagedAttention으로 KV cache를 블록에 나눕니다

요청마다 최대 생성 길이만큼 큰 연속 공간을 미리 예약하는 단순한 방식을 생각해 보겠습니다. 짧게 끝나는 요청은 예약한 공간을 남기고, 긴 요청의 최종 길이는 미리 정확하게 알기 어렵습니다. PagedAttention은 이런 메모리 관리 문제를 KV cache의 블록 단위 배치로 다룹니다.

KV cache를 일정한 토큰 수의 블록으로 나누고, 요청의 논리적 블록을 실제 메모리의 물리적 블록에 대응시킵니다. 논리적으로 이웃한 블록이 실제 메모리에서도 붙어 있을 필요는 없습니다. Attention 계산은 이 대응 관계를 통해 필요한 KV를 읽습니다.

아래는 주소 대응만 보여 주는 설명용 예시입니다. 실제 메모리 주소나 실행 로그는 아닙니다.

| 요청의 논리적 순서 | 배정된 물리 블록 |
| --- | --- |
| 요청 A의 첫 블록 | P |
| 요청 A의 다음 블록 | R |
| 요청 B의 첫 블록 | Q |

요청 A의 토큰은 순서대로 처리하지만, 그 KV가 들어 있는 P와 R은 서로 인접할 필요가 없습니다. 요청이 자라면 필요한 블록을 추가 배정할 수 있습니다. 다만 마지막 블록의 남은 공간까지 항상 0이 된다는 뜻은 아닙니다.

요청별 배정이 점진적이라는 설명과 GPU 메모리 전체를 매번 운영체제에서 조금씩 얻는다는 설명도 다릅니다. 현재 V1의 KV 관리 설계는 block pool과 free queue를 사용합니다. 요청이 끝난 블록의 재사용에는 다른 요청의 참조와 prefix cache 상태도 관계됩니다.

이때 paging은 OS의 디스크 swap과 같은 기능이라는 뜻이 아닙니다. 블록 단위 관리와 주소 대응이라는 아이디어를 빌린 것입니다. 별도의 KV offloading이나 공간 부족 시 재계산 정책은 이 블록 배치 원리와 구분해야 합니다.

2023년 PagedAttention 논문은 원리를 이해하는 출처입니다. 현재의 모든 모델과 attention backend가 원논문의 커널 하나로 실행된다는 명세는 아닙니다. 공식 Paged Attention 페이지도 역사적 문서이며 현재 코드를 설명하지 않는다고 경고합니다.

---

## 4. Continuous batching으로 실행 요청을 바꿉니다

여러 요청을 한 번에 묶어도 그 묶음이 모두 끝나야 다음 요청을 넣는다면, 먼저 끝난 요청의 자리를 바로 활용하지 못합니다. Continuous batching은 실행 iteration 사이에 완료한 요청을 빼고, 자원이 허용하면 새 요청을 추가하는 방식입니다.

아래 표는 합류와 종료만 단순화한 개념 예시입니다. 실제 scheduler trace나 성능 측정값이 아닙니다.

| 실행 시점 | 함께 처리하는 요청 | 다음 실행 전 변화 |
| --- | --- | --- |
| 첫 iteration | A, B | C가 실행 대상으로 합류 |
| 다음 iteration | A, B, C | 완료된 A가 빠짐 |
| 그다음 iteration | B, C | 남은 요청을 계속 처리 |

모든 요청이 같은 길이로 생성하거나 동시에 끝나는 방식이 아닙니다. 실행 중에 배치의 구성원이 달라집니다.

**PagedAttention은 KV 메모리를 어떻게 배정하고 읽을지, continuous batching은 어떤 요청을 함께 실행할지에 관한 원리입니다.** 두 기능은 서로 연결되지만 같은 기능은 아닙니다.

현재 V1은 프롬프트와 출력 토큰을 통합된 토큰 예산으로 스케줄링합니다. 긴 prefill을 여러 조각으로 나누는 chunked prefill도 이 구조에 연결됩니다. Prefill과 decode는 계산을 이해하기 위한 구분이지, 엔진이 반드시 둘 중 한 모드만 실행한다는 뜻은 아닙니다.

---

## 5. OpenAI 호환 API가 보장하는 범위

vLLM의 OpenAI 호환 서버를 사용하면 익숙한 HTTP 요청 형식으로 자체 서빙 모델을 호출할 수 있습니다. 지원 endpoint와 parameter의 호환이지, OpenAI의 모델을 실행하거나 모든 API 동작을 그대로 재현한다는 뜻은 아닙니다.

다음은 서버가 이미 실행 중이라고 가정한 미실행 요청 예시입니다. `served-model-name`은 서버에 등록된 실제 모델 이름으로 바꿔야 합니다. 모델을 준비하거나 요청의 응답과 속도를 확인한 실습 기록은 아닙니다.

```bash
curl 'http://localhost:8000/v1/chat/completions' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "served-model-name",
    "messages": [
      {"role": "user", "content": "KV cache의 역할을 설명해 주세요."}
    ]
  }'
```

Chat Completions에는 해당 모델의 chat template이 필요합니다. 현재 문서에는 Completions의 `suffix`가 미지원이고 Chat의 `user`는 무시된다고 명시되어 있습니다. 이 차이를 확인하지 않고 기존 클라이언트의 주소만 바꾸면 API 호출이 성공해도 기대한 의미와 다르게 동작할 수 있습니다.

생성 기본값도 확인해야 합니다. 모델 저장소에 `generation_config.json`이 있으면 일부 샘플링 기본값에 영향을 줍니다. 도구 호출, 구조화 출력과 필요한 옵션은 선택한 모델 및 서버의 지원 조건을 각각 점검해야 합니다.

---

## 6. 도입 여부는 요청 특성과 운영 책임으로 판단합니다

자체 모델을 서비스하면서 길이가 다른 요청이 겹치고, KV cache와 실행 순서를 관리해야 한다면 vLLM을 검토할 이유가 있습니다. 반대로 외부 관리형 API를 호출하는 애플리케이션이라면 그 호출을 위해 vLLM을 추가할 필요는 없습니다. 모델 실행을 직접 운영할지에 대한 선택입니다.

메모리는 weights만 기준으로 잡지 않습니다. KV cache와 실행 중 임시 공간이 필요하며 GPU 구성에서는 CUDA graph 같은 실행 최적화의 메모리도 고려해야 합니다. 문맥 길이와 동시성을 늘릴 때의 비용을 함께 봐야 합니다.

| 확인할 지점 | 운영 판단 |
| --- | --- |
| 첫 토큰까지의 시간과 전체 요청 지연 | 입력 처리, 대기와 생성 중 어디에서 시간이 늘어나는지 구분 |
| 토큰 사이의 지연과 처리량 | 응답을 빠르게 시작하는 것과 지속적으로 생성하는 성능을 구분 |
| 대기 요청, KV cache 사용률과 preemption | 동시성 증가가 대기나 재계산으로 돌아오는지 확인 |
| 인증, 접근 제어와 요청 제한 | 모델 계산을 제공하는 것 외에 API 운영 책임도 확인 |

서버 내부 지표와 클라이언트 체감 지연은 측정의 시작 및 종료 시점이 다를 수 있습니다. 특히 첫 토큰 지연을 비교할 때 대기, 네트워크와 입력 처리가 포함되는지 확인해야 합니다. 단일 처리량 수치만으로 사용자 경험을 판단하기 어렵습니다.

vLLM은 GPU 전용 도구는 아닙니다. CPU backend도 제공하지만 하드웨어, 정밀도, 모델 구조와 기능의 지원 조합을 확인해야 합니다. CPU로 API 흐름을 익히는 기능 실습과 GPU 환경의 처리량 및 메모리 효율을 비교하는 실험은 목적과 전제가 다릅니다.

[RAG]({% post_url 2026/06/2026-06-22-rag-overview-concept-and-pipeline %})가 검색한 문서를 입력에 보태고 [LoRA]({% post_url 2026/11/2026-11-03-lora-overview %})가 모델의 변경분을 조정해도, 그 입력과 모델을 실행하는 엔진은 필요합니다. vLLM은 검색 시스템이나 adapter 자체를 대신하기보다 모델의 실행과 서빙을 담당하는 층으로 이해하면 됩니다.

---

## 7. Reference

- [vLLM Docs - Introduction](https://docs.vllm.ai/en/latest/)
- [vLLM Docs - Architecture Overview](https://docs.vllm.ai/en/latest/design/arch_overview/)
- [PagedAttention Paper - Efficient Memory Management for Large Language Model Serving](https://arxiv.org/html/2309.06180v1)
- [Hugging Face Docs - How Caching Works](https://huggingface.co/docs/transformers/main/cache_explanation)
- [vLLM Docs - Automatic Prefix Caching Design](https://docs.vllm.ai/en/latest/design/prefix_caching/)
- [vLLM Docs - V1 Guide](https://docs.vllm.ai/en/latest/usage/v1_guide/)
- [vLLM Docs - Historical Paged Attention Document](https://docs.vllm.ai/en/latest/design/paged_attention/)
- [vLLM Docs - OpenAI-Compatible Online Serving](https://docs.vllm.ai/en/latest/serving/online_serving/)
- [vLLM Docs - Conserving Memory](https://docs.vllm.ai/en/latest/configuration/conserving_memory/)
- [vLLM Docs - Production Metrics](https://docs.vllm.ai/en/latest/usage/metrics/)
- [vLLM Docs - CPU Installation](https://docs.vllm.ai/en/stable/getting_started/installation/cpu/)
- [vLLM Docs - GPU Installation](https://docs.vllm.ai/en/stable/getting_started/installation/gpu/)

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
