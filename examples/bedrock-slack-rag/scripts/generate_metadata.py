import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path


def infer_category(path: Path) -> str:
    parts = path.parts
    if "hr" in parts:
        return "hr"
    if "security" in parts:
        return "security"
    if "engineering" in parts:
        return "engineering"
    return "general"


def string_attr(value: str, include_for_embedding: bool = True) -> dict:
    return {
        "value": {"type": "STRING", "stringValue": value},
        "includeForEmbedding": include_for_embedding,
    }


def number_attr(value: int | float, include_for_embedding: bool = False) -> dict:
    return {
        "value": {"type": "NUMBER", "numberValue": value},
        "includeForEmbedding": include_for_embedding,
    }


def string_list_attr(values: list[str], include_for_embedding: bool = True) -> dict:
    return {
        "value": {"type": "STRING_LIST", "stringListValue": values},
        "includeForEmbedding": include_for_embedding,
    }


def metadata_for(pdf: Path) -> dict:
    category = infer_category(pdf)
    title = pdf.stem.replace("-", " ")
    today = date.today().isoformat()
    updated_epoch = int(datetime.now(timezone.utc).timestamp())
    return {
        "metadataAttributes": {
            "doc_id": string_attr(pdf.stem),
            "title": string_attr(title),
            "category": string_attr(category),
            "team": string_attr(category),
            "visibility": string_attr("internal", include_for_embedding=False),
            "owner": string_attr(f"{category}-team", include_for_embedding=False),
            "doc_type": string_attr("policy"),
            "source_type": string_attr("pdf", include_for_embedding=False),
            "updated_at": string_attr(today, include_for_embedding=False),
            "updated_epoch": number_attr(updated_epoch),
            "tags": string_list_attr([category, "google-docs", "pdf"]),
        }
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf_dir")
    args = parser.parse_args()

    pdf_dir = Path(args.pdf_dir)
    for pdf in pdf_dir.rglob("*.pdf"):
        meta_path = pdf.with_name(pdf.name + ".metadata.json")
        meta_path.write_text(json.dumps(metadata_for(pdf), ensure_ascii=False, indent=2), encoding="utf-8")
        print(meta_path)


if __name__ == "__main__":
    main()
