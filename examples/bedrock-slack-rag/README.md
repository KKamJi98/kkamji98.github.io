# Bedrock Slack RAG Chatbot Example

This example supports the blog post about building a Slack RAG chatbot with Amazon Bedrock Knowledge Bases.

## Primary automation path

The preferred automation layer is n8n:

```text
Google Docs update
  |
n8n Google Drive export as PDF
  |
n8n generates metadata sidecar
  |
n8n uploads PDF and metadata to S3
  |
n8n calls a Bedrock sync Lambda
  |
Slack notification
```

See `n8n-workflow-design.md`.

## Slack chatbot runtime

```text
Slack Slash Command
  |
Receiver Lambda ack within 3 seconds
  |
Async worker Lambda invocation
  |
Bedrock RetrieveAndGenerate
  |
Slack response_url
```

## Files

```text
n8n-workflow-design.md
scripts/convert_docs_to_pdf.py
scripts/generate_metadata.py
scripts/upload_and_sync.py
src/app.py
requirements.txt
```

The Python scripts are kept as a local fallback and smoke-test path. The production document sync path should be implemented in n8n. The sample Lambda reinvokes itself asynchronously for simplicity; for production, prefer SQS or a dedicated worker Lambda and grant `lambda:InvokeFunction` only to the required target function.

## Environment variables

```text
SLACK_SIGNING_SECRET
BEDROCK_KB_ID
BEDROCK_MODEL_ARN
AWS_REGION
NUMBER_OF_RESULTS
```

## Notes

Use a normal S3 bucket for Knowledge Base source files. Use S3 Tables or Iceberg tables for logs and evaluation results, not as the direct Knowledge Base source.
