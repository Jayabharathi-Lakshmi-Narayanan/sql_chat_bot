import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from rag_utils.schema_chunker import chunk_schema
from rag_utils.schema_indexer import build_schema_index


with open("rich_metadata.txt", "r", encoding="utf-8") as f:
    raw_schema = f.read()

chunks = chunk_schema(raw_schema)
build_schema_index(chunks)
print("✅ FAISS index built successfully.")
