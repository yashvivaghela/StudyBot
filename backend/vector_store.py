from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from qdrant_client.models import Filter, FieldCondition, MatchValue

from langchain_google_genai import GoogleGenerativeAIEmbeddings
from dotenv import load_dotenv
import os
import uuid
from pathlib import Path

load_dotenv(dotenv_path=Path(__file__).parent / ".env")

# Running fully local — no Docker, no server, just a folder on your machine
client = QdrantClient(path="./qdrant_storage")

embeddings_model = GoogleGenerativeAIEmbeddings(
    model="models/gemini-embedding-001",
    google_api_key=os.getenv("GEMINI_API_KEY")
)


COLLECTION_NAME = "study_messages"


def init_vector_store():
    """Creates the Qdrant collection if it doesn't exist yet."""
    existing = [c.name for c in client.get_collections().collections]
    if COLLECTION_NAME not in existing:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(
    size=3072,
    distance=Distance.COSINE
)
        )
        print(f"Collection '{COLLECTION_NAME}' created.")
    else:
        print(f"Collection '{COLLECTION_NAME}' already exists.")


def embed_and_store(text: str, topic_id: int, message_id: int, role: str):
    """
    Takes a single message, embeds it, and stores it in Qdrant
    with metadata (topic_id, message_id, role) attached as payload.
    """
    vector = embeddings_model.embed_query(text)

    client.upsert(
        collection_name=COLLECTION_NAME,
        points=[
            PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload={
                    "topic_id": topic_id,
                    "message_id": message_id,
                    "role": role,
                    "text": text
                }
            )
        ]
    )


def retrieve_similar(query: str, topic_id: int, top_k: int = 3):
    """
    Given a query string and a topic_id, returns the top_k most
    semantically similar past messages within that topic only.
    """
    query_vector = embeddings_model.embed_query(query)

    results = client.search(
    collection_name=COLLECTION_NAME,
    query_vector=query_vector,
    query_filter=Filter(
        must=[
            FieldCondition(
                key="topic_id",
                match=MatchValue(value=topic_id)
            )
        ]
    ),
    limit=top_k
)

    return [
        {
            "text": r.payload["text"],
            "role": r.payload["role"],
            "score": round(r.score, 3)
        }
        for r in results
    ]


if __name__ == "__main__":
    init_vector_store()
    print("Vector store ready.")