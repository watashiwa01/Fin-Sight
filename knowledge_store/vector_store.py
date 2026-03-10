"""
ChromaDB Vector Store wrapper for Intelli-Credit.
Stores document embeddings for semantic search across uploaded documents.
"""
import chromadb
from pathlib import Path
from config import CHROMA_DIR


class VectorStore:
    """ChromaDB-based vector store for document semantic search."""

    def __init__(self, collection_name: str = "intelli_credit_docs"):
        self.client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def add_document(self, doc_id: str, text: str, metadata: dict | None = None):
        """Add a document chunk to the vector store."""
        self.collection.upsert(
            ids=[doc_id],
            documents=[text],
            metadatas=[metadata or {}],
        )

    def add_documents(self, doc_ids: list[str], texts: list[str], metadatas: list[dict] | None = None):
        """Add multiple document chunks."""
        self.collection.upsert(
            ids=doc_ids,
            documents=texts,
            metadatas=metadatas or [{}] * len(doc_ids),
        )

    def search(self, query: str, n_results: int = 5) -> list[dict]:
        """Semantic search over stored documents."""
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results,
        )
        docs = []
        for i in range(len(results["ids"][0])):
            docs.append({
                "id": results["ids"][0][i],
                "text": results["documents"][0][i],
                "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                "distance": results["distances"][0][i] if results["distances"] else None,
            })
        return docs

    def get_context(self, query: str, n_results: int = 3) -> str:
        """Get concatenated context string for LLM prompts."""
        docs = self.search(query, n_results)
        return "\n\n---\n\n".join([d["text"] for d in docs])

    def clear(self):
        """Clear all documents from the collection."""
        self.client.delete_collection(self.collection.name)
        self.collection = self.client.get_or_create_collection(
            name="intelli_credit_docs",
            metadata={"hnsw:space": "cosine"},
        )

    @property
    def count(self) -> int:
        return self.collection.count()
