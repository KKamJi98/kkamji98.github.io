# n8n workflow design for Google Docs to Bedrock Knowledge Base sync

## Goal

Use n8n as the automation layer for this flow:

```text
Google Docs update
  |
PDF export
  |
S3 upload
  |
Bedrock Knowledge Base ingestion
  |
Slack notification
```

## Recommended nodes

1. Schedule Trigger or Google Drive Trigger
2. Google Drive node to list changed documents
3. Google Drive or HTTP Request node to export each document as PDF
4. Code node to build `file.pdf.metadata.json`
5. AWS S3 node to upload the PDF
6. AWS S3 node to upload metadata sidecar
7. HTTP Request node or Lambda node to start Bedrock ingestion
8. Wait and polling loop for ingestion status
9. Slack node to notify success or failure

## Safer Bedrock sync pattern

Prefer a small Lambda wrapper for Bedrock ingestion:

```text
n8n
  |
Lambda start-kb-sync
  |
bedrock-agent StartIngestionJob
  |
bedrock-agent GetIngestionJob
```

This keeps AWS SigV4 details and IAM scoping outside the visual workflow.
