"""Verify the working catalog against the untouched, nested source archive."""
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

root = Path(__file__).resolve().parents[2]
with ZipFile(root / "Bolu-s-Wall-Engine-main.zip") as outer:
    with ZipFile(BytesIO(outer.read("Bolu-s-Wall-Engine-main/Front End Project.zip"))) as inner:
        original = inner.read("Front End Project/src/data/wallpapers.js")
current = (root / "Front End Project/src/data/wallpapers.js").read_bytes()
assert current == original, "Catalog differs from original archive"
print(f"PASS: Catalog is byte-for-byte identical. SHA-256: {sha256(current).hexdigest()}")
