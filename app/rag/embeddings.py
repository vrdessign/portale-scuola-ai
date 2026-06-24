"""
app/rag/embeddings.py — Embeddings locali con sentence-transformers
Gira interamente su GPU (H100) senza chiamate API esterne.
"""
import logging
from typing import List
import torch
from sentence_transformers import SentenceTransformer
from config import EMBED_MODEL, EMBED_DEVICE, EMBED_BATCH_SIZE

logger = logging.getLogger(__name__)

class LocalEmbedder:
    """
    Embedder locale basato su sentence-transformers.
    Usa multilingual-e5-large per supporto italiano e arabo.
    """

    _instance = None  # singleton

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        logger.info(f"Caricamento modello embeddings: {EMBED_MODEL}")
        device = EMBED_DEVICE if torch.cuda.is_available() else "cpu"
        self.model = SentenceTransformer(EMBED_MODEL, device=device)
        self.dimension = self.model.get_sentence_embedding_dimension()
        logger.info(f"Modello caricato su {device} — dimensione vettori: {self.dimension}")
        self._initialized = True

    def embed(self, texts: List[str]) -> List[List[float]]:
        """
        Genera embedding per una lista di testi.
        Usa il prefisso 'query:' / 'passage:' richiesto da E5.
        """
        if not texts:
            return []
        # multilingual-e5 richiede prefisso 'passage:' per i documenti
        prefixed = [f"passage: {t}" for t in texts]
        vecs = self.model.encode(
            prefixed,
            batch_size=EMBED_BATCH_SIZE,
            normalize_embeddings=True,
            show_progress_bar=len(texts) > 100
        )
        return vecs.tolist()

    def embed_query(self, text: str) -> List[float]:
        """
        Genera embedding per una singola query.
        Usa il prefisso 'query:' per E5.
        """
        vec = self.model.encode(
            f"query: {text}",
            normalize_embeddings=True
        )
        return vec.tolist()

    @property
    def vector_size(self) -> int:
        return self.dimension


# Istanza globale (singleton)
embedder = LocalEmbedder()
