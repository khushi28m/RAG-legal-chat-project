from pathlib import Path
p = Path("data/emb_test/sample.jsonl")
text = p.read_text(encoding="utf-8-sig")    # reads & removes BOM if present
p.write_text(text, encoding="utf-8")
print("Rewrote without BOM:", p)
