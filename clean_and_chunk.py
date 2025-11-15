# ingestion/processors/clean_and_chunk.py
#!/usr/bin/env python3

import argparse
import re
import json
import time
from pathlib import Path
from typing import List

try:
    import PyPDF2
except Exception:
    PyPDF2 = None

def load_text(path: Path) -> str:
    """Loads text from PDF or raw text files."""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        if PyPDF2 is None:
            raise RuntimeError("PyPDF2 not installed. Install with: pip install PyPDF2")
        
        # Robustly extract text, tagging each page
        with open(path, "rb") as fh:
            reader = PyPDF2.PdfReader(fh)
            pages = []
            for i, p in enumerate(reader.pages):
                try:
                    t = p.extract_text() or ""
                except Exception:
                    t = ""
                if t:
                    pages.append(f"[PAGE {i+1}]\n" + t.strip()) 
            return "\n\n".join(pages)
    else:
        # read text files robustly and strip BOM if present
        raw = path.read_text(encoding="utf-8", errors="ignore")
        if raw.startswith("\ufeff"):
            raw = raw.lstrip("\ufeff")
        return raw

def clean_text(text: str) -> str:
    """Performs general text cleanup for legal documents."""
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()

def chunk_text_by_paragraphs(text: str, max_chars: int = 2048, overlap: int = 150) -> List[str]:
    """
    Splits text into chunks, prioritizing paragraph breaks to maintain context.
    Uses a larger max_chars default for legal documents.
    """
    if not text:
        return []
    
    paragraphs = text.split("\n\n")
    chunks = []
    current_chunk = ""
    
    for paragraph in paragraphs:
        if not paragraph.strip():
            continue

        # If adding the new paragraph exceeds the max_chars, finalize the current chunk
        if len(current_chunk) + len(paragraph) + 2 > max_chars and current_chunk:
            chunks.append(current_chunk.strip())
            
            # Start the new chunk using the overlap portion of the previous chunk
            overlap_text = current_chunk[len(current_chunk) - overlap:].strip()
            current_chunk = overlap_text + "\n\n" + paragraph
        else:
            # Continue extending the current chunk
            if current_chunk:
                current_chunk += "\n\n" + paragraph
            else:
                current_chunk = paragraph

    # Add the final chunk
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
        
    return chunks

def minimal_meta(path: Path):
    return {
        "source_id": path.stem,
        "title": path.stem,
        "path": str(path),
    }

def process_file(path: Path, out_dir: Path, max_chars: int, overlap: int, dry_run: bool):
    print(f"[INFO] Processing file: {path}")
    text = load_text(path)
    if not text:
        print(f"[WARN] No extractable text found in {path.name}. Skipping chunking.")
        return 0

    text = clean_text(text)
    chunks = chunk_text_by_paragraphs(text, max_chars=max_chars, overlap=overlap)
    
    meta = minimal_meta(path)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{meta['source_id']}.jsonl"

    if dry_run:
        print(f"[DRY RUN] Would write {len(chunks)} chunks to {out_path}")
        return len(chunks)

    written = 0
    with out_path.open("w", encoding="utf-8") as fh:
        for i, c in enumerate(chunks):
            c = c.strip() 
            if not c:
                continue

            rec = {
                "id": f"{meta['source_id']}_chunk_{i}",
                "source_id": meta["source_id"],
                "title": meta["title"],
                "chunk_index": i,
                "text": c
            }
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            written += 1
            fh.flush()
    print(f"[OK] Wrote {written} chunks to {out_path}")
    return written

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", "-f", required=True, help="Single file to process (pdf/txt/html)")
    parser.add_argument("--output", "-o", required=True, help="Output folder")
    parser.add_argument("--max_chars", type=int, default=2048) 
    parser.add_argument("--overlap", type=int, default=150)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--sleep", type=float, default=0.0, help="Seconds to sleep after processing (throttle)")
    args = parser.parse_args()

    p = Path(args.file)
    if not p.exists():
        print(f"[ERROR] File not found: {p}")
        return

    try:
        n = process_file(p, Path(args.output), args.max_chars, args.overlap, args.dry_run)
    except Exception as e:
        print(f"[ERROR] Exception while processing {p.name}: {e}")
        return

    if args.sleep and not args.dry_run:
        print(f"[INFO] Sleeping {args.sleep} seconds to avoid resource spikes...")
        time.sleep(float(args.sleep))

if __name__ == "__main__":
    main()