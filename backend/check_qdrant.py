from qdrant_client import QdrantClient
client = QdrantClient(path="./qdrant_storage")
points, _ = client.scroll(collection_name="study_messages", limit=1000, with_payload=True)
remaining = [p for p in points if p.payload["topic_id"] == 2]
print(f"Remaining points for deleted topic: {len(remaining)}")
