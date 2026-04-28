"""Load plain-text filing documents into the filing_chunk table.

Place converted text files in seed/filings/text/ with this naming convention:
  {platform}-{doc_type}-{date}.txt

Examples:
  swiggy-drhp-2023.txt
  zomato-annual_report-2024.txt
  zomato-investor_call-2024.txt

Convert PDFs first:
  pdftotext swiggy-drhp.pdf seed/filings/text/swiggy-drhp-2023.txt

Run after the API server is up:
  python seed/load_filings.py
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import httpx


FILINGS_TEXT_DIR = Path(__file__).resolve().parent / "filings" / "text"
WORDS_MIN = 200
WORDS_MAX = 400


def _parse_filename(stem: str) -> tuple[str, str, str]:
    """Return (platform, doc_type, doc_date) from a filename stem like 'swiggy-drhp-2023'."""
    parts = stem.split("-", 2)
    if len(parts) < 3:
        raise ValueError(
            f"Filename stem {stem!r} must follow {{platform}}-{{doc_type}}-{{date}} "
            "(e.g. swiggy-drhp-2023)"
        )
    platform, doc_type, raw_date = parts[0], parts[1], parts[2]
    doc_date = f"{raw_date}-01-01" if re.fullmatch(r"\d{4}", raw_date) else raw_date
    return platform, doc_type, doc_date


def _chunk_text(text: str) -> list[str]:
    """Split text into 200–400 word chunks, breaking only on paragraph boundaries."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]

    chunks: list[str] = []
    current_parts: list[str] = []
    current_words = 0

    for para in paragraphs:
        para_words = len(para.split())
        if current_words + para_words > WORDS_MAX and current_words >= WORDS_MIN:
            chunks.append("\n\n".join(current_parts))
            current_parts = [para]
            current_words = para_words
        else:
            current_parts.append(para)
            current_words += para_words

    if current_parts:
        chunks.append("\n\n".join(current_parts))

    return chunks


def _load_file(client: httpx.Client, base_url: str, path: Path) -> tuple[int, int]:
    """Chunk and POST one text file. Returns (loaded, skipped)."""
    platform, doc_type, doc_date = _parse_filename(path.stem)
    text = path.read_text(encoding="utf-8")
    chunks = _chunk_text(text)

    loaded = skipped = 0
    word_offset = 0

    for idx, chunk in enumerate(chunks):
        page_approx = word_offset // 300
        chunk_id = f"{platform}-{doc_type}-p{page_approx}-c{idx}"
        payload = {
            "id": chunk_id,
            "platform": platform,
            "doc_type": doc_type,
            "doc_date": doc_date,
            "page": page_approx if page_approx > 0 else None,
            "text": chunk,
        }
        response = client.post(f"{base_url}/filing-chunks", json=payload)
        if response.status_code == 409:
            print(f"  Skipped {chunk_id} (already exists)")
            skipped += 1
        else:
            response.raise_for_status()
            print(f"  Loaded  {chunk_id}")
            loaded += 1
        word_offset += len(chunk.split())

    return loaded, skipped


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Chunk and load filing documents into the API.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="API base URL")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    base_url = args.base_url.rstrip("/")

    txt_files = sorted(FILINGS_TEXT_DIR.glob("*.txt"))
    if not txt_files:
        print(f"No .txt files found in {FILINGS_TEXT_DIR}")
        print("Convert your PDFs/HTML to plain text and place them there.")
        print("  pdftotext swiggy-drhp.pdf seed/filings/text/swiggy-drhp-2023.txt")
        return

    with httpx.Client(timeout=30.0) as client:
        health = client.get(f"{base_url}/health")
        health.raise_for_status()

        total_loaded = total_skipped = 0
        for path in txt_files:
            print(f"\nProcessing {path.name} ...")
            loaded, skipped = _load_file(client, base_url, path)
            total_loaded += loaded
            total_skipped += skipped

    print(f"\nDone. Loaded {total_loaded} chunks, skipped {total_skipped} duplicates.")
    print("Run GET /filing-chunks to verify.")


if __name__ == "__main__":
    main()
