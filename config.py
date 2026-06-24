"""
config.py — Configurazione centralizzata Portale Scuola AI
Tutti i parametri modificabili in un unico posto.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).parent

# ── LLM Locale (vLLM) ────────────────────────────────────────────────────────
LLM_BASE_URL        = os.getenv("LLM_BASE_URL", "http://localhost:8000/v1")
LLM_MODEL           = os.getenv("LLM_MODEL", "meta-llama/Llama-3.1-70B-Instruct")
LLM_MAX_TOKENS      = int(os.getenv("LLM_MAX_TOKENS", "2048"))
LLM_TEMPERATURE     = float(os.getenv("LLM_TEMPERATURE", "0.3"))
LLM_TIMEOUT         = int(os.getenv("LLM_TIMEOUT", "60"))

# ── Embeddings Locali (sentence-transformers) ─────────────────────────────────
EMBED_MODEL         = os.getenv("EMBED_MODEL", "intfloat/multilingual-e5-large")
EMBED_DEVICE        = os.getenv("EMBED_DEVICE", "cuda")   # cuda | cpu
EMBED_BATCH_SIZE    = int(os.getenv("EMBED_BATCH_SIZE", "64"))

# ── Qdrant (Vector DB) ────────────────────────────────────────────────────────
QDRANT_URL          = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY      = os.getenv("QDRANT_API_KEY", None)
COLLECTION_L1       = "rag_ministeriale"      # RAG L1 — curricola nazionali
COLLECTION_L2_PREFIX= "rag_istituto_"         # RAG L2 — prefisso + codice istituto

# ── Chunking ──────────────────────────────────────────────────────────────────
CHUNK_SIZE          = int(os.getenv("CHUNK_SIZE", "800"))
CHUNK_OVERLAP       = int(os.getenv("CHUNK_OVERLAP", "150"))

# ── Retrieval ─────────────────────────────────────────────────────────────────
RAG_L1_TOP_K        = int(os.getenv("RAG_L1_TOP_K", "5"))
RAG_L2_TOP_K        = int(os.getenv("RAG_L2_TOP_K", "5"))
RAG_L1_THRESHOLD    = float(os.getenv("RAG_L1_THRESHOLD", "0.70"))
RAG_L2_THRESHOLD    = float(os.getenv("RAG_L2_THRESHOLD", "0.65"))

# ── Database (PostgreSQL) ─────────────────────────────────────────────────────
DATABASE_URL        = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://portale:portale@localhost:5432/portale_scuola"
)

# ── Auth / Sicurezza ──────────────────────────────────────────────────────────
SECRET_KEY          = os.getenv("SECRET_KEY", "CAMBIA_QUESTA_CHIAVE_IN_PRODUZIONE")
ACCESS_TOKEN_EXPIRE = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))  # 8 ore

# ── App ───────────────────────────────────────────────────────────────────────
APP_HOST            = os.getenv("APP_HOST", "0.0.0.0")
APP_PORT            = int(os.getenv("APP_PORT", "5000"))
APP_DEBUG           = os.getenv("APP_DEBUG", "false").lower() == "true"

# ── Percorsi dati ─────────────────────────────────────────────────────────────
DATA_DIR            = BASE_DIR / "data"
MINISTERIALE_DIR    = DATA_DIR / "ministeriale"
ISTITUTI_DIR        = DATA_DIR / "istituti"
UPLOADS_DIR         = DATA_DIR / "uploads"

# Crea cartelle se non esistono
for d in [DATA_DIR, MINISTERIALE_DIR, ISTITUTI_DIR, UPLOADS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ── Gradi scolastici supportati ───────────────────────────────────────────────
GRADI_SCOLASTICI = {
    "primaria":    {"anni": [1,2,3,4,5],    "eta_max": 11},
    "media":       {"anni": [6,7,8],         "eta_max": 14},
    "superiore":   {"anni": [9,10,11,12,13],"eta_max": 19},
}

# ── Materie supportate ────────────────────────────────────────────────────────
MATERIE = [
    "matematica", "italiano", "storia", "geografia", "scienze",
    "fisica", "chimica", "biologia", "inglese", "filosofia",
    "arte", "musica", "educazione_fisica", "informatica", "latino",
    "greco", "economia", "diritto", "tecnologia"
]
