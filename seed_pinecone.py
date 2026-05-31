"""
Seed Pinecone index with knowledge_base.json
Usage: python seed_pinecone.py
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

PINECONE_API_KEY = os.environ.get("PINECONE_API_KEY", "")
PINECONE_INDEX   = os.environ.get("PINECONE_INDEX", "vip-numbers-knowledge")
NVIDIA_API_KEY   = os.environ.get("NVIDIA_API_KEY", "")

if not PINECONE_API_KEY or not NVIDIA_API_KEY:
    print("❌ Missing PINECONE_API_KEY or NVIDIA_API_KEY in .env")
    sys.exit(1)

from pinecone import Pinecone, ServerlessSpec
from openai import OpenAI

# Initialize Pinecone
pc = Pinecone(api_key=PINECONE_API_KEY)

# Create index if not exists
if PINECONE_INDEX not in pc.list_indexes().names():
    print(f"📦 Creating index '{PINECONE_INDEX}'...")
    pc.create_index(
        name=PINECONE_INDEX,
        dimension=768,
        metric="cosine",
        spec=ServerlessSpec(cloud="aws", region="us-east-1")
    )
    print("✅ Index created")
else:
    print(f"✅ Index '{PINECONE_INDEX}' already exists")

index = pc.Index(PINECONE_INDEX)

# Load knowledge base
kb_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "knowledge_base.json")
if not os.path.exists(kb_path):
    print(f"❌ knowledge_base.json not found at {kb_path}")
    sys.exit(1)

with open(kb_path, "r", encoding="utf-8") as f:
    kb = json.load(f)

print(f"📚 Loading {len(kb)} knowledge items...")

# Initialize NVIDIA NIM for embeddings
nim = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=NVIDIA_API_KEY
)

# Embed and upsert
vectors = []
for i, item in enumerate(kb):
    emb = nim.embeddings.create(model="nvidia/embed-qa-4", input=[item["text"]])
    vectors.append((str(i), emb.data[0].embedding, {
        "text": item["text"],
        "category": item.get("category", "general")
    }))
    if (i + 1) % 5 == 0:
        print(f"  ⏳ Embedded {i+1}/{len(kb)}...")

# Upsert in batches
batch_size = 10
for i in range(0, len(vectors), batch_size):
    batch = vectors[i:i + batch_size]
    index.upsert(vectors=batch)
    print(f"  ✅ Upserted {min(i+batch_size, len(vectors))}/{len(vectors)}")

print(f"\n🎉 Done! {len(vectors)} items seeded to Pinecone index '{PINECONE_INDEX}'")
