from pathlib import Path

raw = Path("data/raw")

if not raw.exists():
    print("Folder not found:", raw)
    exit()

files = sorted(raw.iterdir())

print(f"Found {len(files)} files in data/raw:\n")
for f in files:
    size = f.stat().st_size
    print(f"- {f.name} ({size} bytes)")
