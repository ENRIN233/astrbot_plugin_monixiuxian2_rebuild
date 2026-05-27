"""Sync config JSON files to docs/data/ for GitHub Pages.

Usage: python sync_data.py
"""
import shutil
import os

BASE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(BASE, "config")
DST = os.path.join(BASE, "docs", "data")

os.makedirs(DST, exist_ok=True)

count = 0
for f in os.listdir(SRC):
    if f.endswith(".json"):
        src_path = os.path.join(SRC, f)
        dst_path = os.path.join(DST, f)
        shutil.copy2(src_path, dst_path)
        count += 1
        print(f"  {f}")

print(f"\nSynced {count} files to docs/data/")
