"""
scripts/setup_vector_store.py

One-time setup script — run ONCE before starting the server if you want to use
OpenAI's hosted FileSearchTool in addition to local embedding RAG.

What it does:
    1. Creates an OpenAI Vector Store named "3D Digital Showroom Knowledge Base"
    2. Uploads the three knowledge-base files from data/
    3. Attaches the files and polls for indexing completion (up to 120 s)
    4. Writes VECTOR_STORE_ID to .env automatically

Usage (from project root):
    python scripts/setup_vector_store.py
"""

import os
import sys
import time

sys.path.insert(0, ".")

from dotenv import load_dotenv, set_key
from openai import OpenAI

load_dotenv()

_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))
_DATA_FILES = ["vehicle_catalog.txt", "dealership_faq.txt", "showroom_layouts.txt"]


def setup_vector_store() -> str:
    print("Creating OpenAI Vector Store...")
    vector_store = _client.vector_stores.create(name="3D Digital Showroom Knowledge Base")
    print(f"  Created: {vector_store.id}")

    for filename in _DATA_FILES:
        path = os.path.join("data", filename)
        with open(path, "rb") as f:
            uploaded = _client.files.create(file=f, purpose="assistants")
        print(f"  Uploaded {filename} → {uploaded.id}")
        _client.vector_stores.files.create(
            vector_store_id=vector_store.id, file_id=uploaded.id
        )
        print(f"  Attached {filename} to Vector Store")

    print("Waiting for indexing (up to 120 s)...")
    for elapsed in range(0, 121, 5):
        vs = _client.vector_stores.retrieve(vector_store.id)
        counts = vs.file_counts
        print(f"  [{elapsed}s] completed={counts.completed} in_progress={counts.in_progress} failed={counts.failed}")
        if counts.in_progress == 0:
            break
        time.sleep(5)

    set_key(".env", "VECTOR_STORE_ID", vector_store.id)
    print(f"\nDone. VECTOR_STORE_ID={vector_store.id} saved to .env")
    return vector_store.id


if __name__ == "__main__":
    setup_vector_store()
