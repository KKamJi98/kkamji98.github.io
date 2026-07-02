import argparse
import time
from pathlib import Path

import boto3


def s3_key(prefix: str, root: Path, path: Path) -> str:
    rel = path.relative_to(root).as_posix()
    return f"{prefix.rstrip('/')}/{rel}"


def upload_tree(pdf_dir: Path, bucket: str, prefix: str) -> None:
    s3 = boto3.client("s3")
    for path in pdf_dir.rglob("*"):
        if not path.is_file():
            continue
        if not (path.name.endswith(".pdf") or path.name.endswith(".metadata.json")):
            continue
        key = s3_key(prefix, pdf_dir, path)
        content_type = "application/pdf" if path.name.endswith(".pdf") else "application/json"
        s3.upload_file(
            str(path),
            bucket,
            key,
            ExtraArgs={"ContentType": content_type},
        )
        print(f"s3://{bucket}/{key}")


def start_ingestion_job(knowledge_base_id: str, data_source_id: str) -> str:
    client = boto3.client("bedrock-agent")
    response = client.start_ingestion_job(
        knowledgeBaseId=knowledge_base_id,
        dataSourceId=data_source_id,
    )
    return response["ingestionJob"]["ingestionJobId"]


def wait_ingestion_job(knowledge_base_id: str, data_source_id: str, job_id: str, poll_seconds: int) -> None:
    client = boto3.client("bedrock-agent")
    terminal = {"COMPLETE", "FAILED", "STOPPED"}
    while True:
        response = client.get_ingestion_job(
            knowledgeBaseId=knowledge_base_id,
            dataSourceId=data_source_id,
            ingestionJobId=job_id,
        )
        job = response["ingestionJob"]
        status = job["status"]
        stats = job.get("statistics", {})
        print(f"ingestion job {job_id}: {status} {stats}")
        if status in terminal:
            if status != "COMPLETE":
                raise RuntimeError(f"ingestion job ended with {status}: {job}")
            return
        time.sleep(poll_seconds)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf-dir", required=True)
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--prefix", default="knowledge/")
    parser.add_argument("--knowledge-base-id", required=True)
    parser.add_argument("--data-source-id", required=True)
    parser.add_argument("--poll-seconds", type=int, default=15)
    parser.add_argument("--no-wait", action="store_true")
    args = parser.parse_args()

    pdf_dir = Path(args.pdf_dir)
    upload_tree(pdf_dir, args.bucket, args.prefix)
    job_id = start_ingestion_job(args.knowledge_base_id, args.data_source_id)
    print(f"started ingestion job: {job_id}")
    if not args.no_wait:
        wait_ingestion_job(args.knowledge_base_id, args.data_source_id, job_id, args.poll_seconds)


if __name__ == "__main__":
    main()
