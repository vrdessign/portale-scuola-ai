"""
app/rag/vectorstore.py — Gestione Qdrant per RAG L1 e RAG L2
RAG L1: una collection globale per i curricola ministeriali
RAG L2: una collection per ogni istituto (isolamento dei dati)
"""
import logging
import uuid
from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct,
    Filter, FieldCondition, MatchValue, SearchRequest
)
from config import (
    QDRANT_URL, QDRANT_API_KEY,
    COLLECTION_L1, COLLECTION_L2_PREFIX,
    RAG_L1_TOP_K, RAG_L2_TOP_K,
    RAG_L1_THRESHOLD, RAG_L2_THRESHOLD
)
from app.rag.embeddings import embedder

logger = logging.getLogger(__name__)


class VectorStore:
    """Client Qdrant con helper per le operazioni RAG."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.client = QdrantClient(
            url=QDRANT_URL,
            api_key=QDRANT_API_KEY,
            timeout=30
        )
        self.vector_size = embedder.vector_size
        logger.info(f"Qdrant connesso: {QDRANT_URL}")
        self._initialized = True

    # ── Inizializzazione collection ───────────────────────────────────────────

    def init_collection_l1(self):
        """Crea la collection RAG L1 (curricola ministeriali) se non esiste."""
        self._ensure_collection(COLLECTION_L1)
        logger.info(f"Collection L1 pronta: {COLLECTION_L1}")

    def init_collection_l2(self, codice_istituto: str):
        """Crea la collection RAG L2 per un istituto specifico."""
        name = f"{COLLECTION_L2_PREFIX}{codice_istituto}"
        self._ensure_collection(name)
        logger.info(f"Collection L2 pronta: {name}")
        return name

    def _ensure_collection(self, name: str):
        existing = [c.name for c in self.client.get_collections().collections]
        if name not in existing:
            self.client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(
                    size=self.vector_size,
                    distance=Distance.COSINE
                )
            )

    # ── Indicizzazione documenti ──────────────────────────────────────────────

    def index_chunks(
        self,
        collection: str,
        chunks: List[str],
        metadatas: List[Dict[str, Any]]
    ) -> int:
        """
        Indicizza una lista di chunk testuali nel vectorstore.
        Restituisce il numero di chunk indicizzati.
        """
        if not chunks:
            return 0

        vectors = embedder.embed(chunks)
        points = [
            PointStruct(
                id=str(uuid.uuid4()),
                vector=vec,
                payload={"text": chunk, **meta}
            )
            for chunk, vec, meta in zip(chunks, vectors, metadatas)
        ]

        # Upload a batch da 100
        batch_size = 100
        for i in range(0, len(points), batch_size):
            self.client.upsert(
                collection_name=collection,
                points=points[i:i+batch_size]
            )

        logger.info(f"Indicizzati {len(chunks)} chunk in '{collection}'")
        return len(chunks)

    def delete_document(self, collection: str, documento_id: str):
        """Rimuove tutti i chunk di un documento dal vectorstore."""
        self.client.delete(
            collection_name=collection,
            points_selector=Filter(
                must=[FieldCondition(
                    key="documento_id",
                    match=MatchValue(value=documento_id)
                )]
            )
        )

    # ── Ricerca ───────────────────────────────────────────────────────────────

    def search_l1(
        self,
        query: str,
        materia: Optional[str] = None,
        top_k: int = RAG_L1_TOP_K,
        threshold: float = RAG_L1_THRESHOLD
    ) -> List[Dict[str, Any]]:
        """Ricerca nel RAG L1 (curricola ministeriali)."""
        return self._search(
            collection=COLLECTION_L1,
            query=query,
            filters={"materia": materia} if materia else None,
            top_k=top_k,
            threshold=threshold
        )

    def search_l2(
        self,
        query: str,
        codice_istituto: str,
        materia: Optional[str] = None,
        top_k: int = RAG_L2_TOP_K,
        threshold: float = RAG_L2_THRESHOLD
    ) -> List[Dict[str, Any]]:
        """Ricerca nel RAG L2 (libri di testo dell'istituto)."""
        collection = f"{COLLECTION_L2_PREFIX}{codice_istituto}"
        existing = [c.name for c in self.client.get_collections().collections]
        if collection not in existing:
            logger.warning(f"Collection L2 non trovata: {collection}")
            return []
        return self._search(
            collection=collection,
            query=query,
            filters={"materia": materia} if materia else None,
            top_k=top_k,
            threshold=threshold
        )

    def _search(
        self,
        collection: str,
        query: str,
        filters: Optional[Dict] = None,
        top_k: int = 5,
        threshold: float = 0.65
    ) -> List[Dict[str, Any]]:
        """Ricerca vettoriale con filtri e threshold."""
        query_vec = embedder.embed_query(query)

        qdrant_filter = None
        if filters:
            conditions = [
                FieldCondition(key=k, match=MatchValue(value=v))
                for k, v in filters.items() if v
            ]
            if conditions:
                qdrant_filter = Filter(must=conditions)

        results = self.client.search(
            collection_name=collection,
            query_vector=query_vec,
            query_filter=qdrant_filter,
            limit=top_k,
            score_threshold=threshold,
            with_payload=True
        )

        return [
            {
                "text": r.payload.get("text", ""),
                "score": r.score,
                "metadata": {k: v for k, v in r.payload.items() if k != "text"}
            }
            for r in results
        ]

    def collection_stats(self, collection: str) -> Dict[str, Any]:
        """Statistiche di una collection."""
        try:
            info = self.client.get_collection(collection)
            return {
                "name": collection,
                "total_chunks": info.points_count,
                "vector_size": info.config.params.vectors.size
            }
        except Exception:
            return {"name": collection, "total_chunks": 0}


# Istanza globale
vectorstore = VectorStore()
