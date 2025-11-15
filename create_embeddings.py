# indexing/create_embeddings.py
import os
import json
import argparse
from pathlib import Path
from sentence_transformers import SentenceTransformer
import numpy as np

# Conditional import for FAISS
try:
    import faiss
except Exception:
    faiss = None

def load_jsonl_folder(folder: Path):
    """Loads all records from all .jsonl files in the given folder."""
    records = []
    for p in sorted(folder.glob("*.jsonl")):
        with p.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                records.append(rec)
    return records

def build_faiss_index(embs: np.ndarray, out_dir: Path, metric: str = "cosine"):
    """Creates, normalizes, and saves the FAISS index."""
    out_dir.mkdir(parents=True, exist_ok=True)
    d = embs.shape[1]
    
    if faiss is None:
        raise RuntimeError("faiss is not available. Install faiss-cpu or use alternative vector DB.")
        
    # Use IndexFlatIP on L2-normalized vectors for cosine similarity
    index = faiss.IndexFlatIP(d)
    faiss.normalize_L2(embs)
    index.add(embs)
    
    index_file = out_dir / "index.faiss"
    faiss.write_index(index, str(index_file))
    print(f"Saved FAISS index to {index_file} (total vectors: {index.ntotal})")
    return index_file

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input_dir", "-i", required=True, help="processed jsonl folder (e.g., data/processed)")
    parser.add_argument("--out_dir", "-o", required=True, help="output folder for faiss + metadata (e.g., data/faiss_test)")
    parser.add_argument("--model", default="all-MiniLM-L6-v2", help="sentence-transformers model for embedding")
    parser.add_argument("--batch_size", type=int, default=64)
    args = parser.parse_args()

    inp = Path(args.input_dir)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    print("Loading records from:", inp)
    records = load_jsonl_folder(inp)
    if not records:
        print("No records found. Ensure Step 2 (Chunking) was run successfully.")
        return

    texts = [r["text"] for r in records]
    print(f"Embedding {len(texts)} chunks with model {args.model} ...")
    model = SentenceTransformer(args.model)
    embs = model.encode(texts, batch_size=args.batch_size, convert_to_numpy=True, show_progress_bar=True)
    
    embs = embs.astype("float32")
    
    index_file = build_faiss_index(embs, out)
    
    meta_file = out / "metadata.json"
    with meta_file.open("w", encoding="utf-8") as fh:
        # Save minimal metadata aligned with vector ids
        minimal_meta = [{
            "id": rec.get("id"),
            "source_id": rec.get("source_id"),
            "title": rec.get("title"),
            "path": rec.get("path"),
            "chunk_index": rec.get("chunk_index"),
            "text": rec.get("text")[:1200]  # store excerpt for preview (truncate if huge)
        } for rec in records]
        json.dump(minimal_meta, fh, ensure_ascii=False, indent=2)
    print("Saved metadata to", meta_file)

if __name__ == "__main__":
    main()