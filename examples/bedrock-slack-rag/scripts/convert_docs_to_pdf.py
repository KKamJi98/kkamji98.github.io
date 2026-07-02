"""Local smoke-test fallback for DOCX to PDF conversion.

Production document sync uses n8n with Google Drive API PDF export from
Google Docs. Keep this script only for local experiments or offline tests.
"""

import argparse
import subprocess
from pathlib import Path


def convert_docx_to_pdf(src: Path, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "libreoffice",
            "--headless",
            "--convert-to",
            "pdf",
            "--outdir",
            str(out_dir),
            str(src),
        ],
        check=True,
    )
    pdf = out_dir / f"{src.stem}.pdf"
    if not pdf.exists() or pdf.stat().st_size == 0:
        raise RuntimeError(f"PDF conversion failed: {src}")
    return pdf


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("docs_dir")
    parser.add_argument("out_dir")
    args = parser.parse_args()

    docs_dir = Path(args.docs_dir)
    out_dir = Path(args.out_dir)
    for src in docs_dir.rglob("*.docx"):
        pdf = convert_docx_to_pdf(src, out_dir / src.parent.relative_to(docs_dir))
        print(pdf)


if __name__ == "__main__":
    main()
