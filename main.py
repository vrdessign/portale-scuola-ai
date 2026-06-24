"""
main.py — Portale Scuola AI
Architettura D-RAG-E (Dual RAG Educativo) — Dessign Innovation © 2025
Deploy: SuperPOD locale con vLLM + sentence-transformers + Qdrant
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Request
from fastapi.responses import HTMLResponse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup e shutdown dell'applicazione."""
    logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    logger.info("  Portale Scuola AI — D-RAG-E Engine")
    logger.info("  © 2025 Dessign Innovation — Cristian Dessi")
    logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    # 1. Inizializza database
    from app.database.session import init_db
    await init_db()
    logger.info("✓ Database inizializzato")

    # 2. Carica modello embeddings (singleton — solo una volta)
    from app.rag.embeddings import embedder
    logger.info(f"✓ Embeddings locali caricati: {embedder.vector_size}d")

    # 3. Inizializza Qdrant collection L1
    from app.rag.vectorstore import vectorstore
    vectorstore.init_collection_l1()
    logger.info("✓ Qdrant pronto (collection RAG L1 attiva)")

    # 4. Verifica LLM locale
    from app.rag.llm_local import llm
    llm_ok = await llm.health_check()
    if llm_ok:
        logger.info(f"✓ vLLM online: {llm.model}")
    else:
        logger.warning(f"⚠ vLLM non raggiungibile su {llm.base_url} — avvia vLLM prima di fare query")

    logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    logger.info("  Sistema pronto")
    logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    yield  # ← l'app è in esecuzione

    logger.info("Shutdown Portale Scuola AI")


# ── Applicazione FastAPI ──────────────────────────────────────────────────────
app = FastAPI(
    title="Portale Scuola AI",
    description="Sistema D-RAG-E (Dual RAG Educativo) — Architettura proprietaria Dessign Innovation",
    version="2.0.0",
    lifespan=lifespan
)

# CORS — in produzione limitare ai domini specifici
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # cambia in produzione con il dominio reale
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# File statici e template
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# ── Router ────────────────────────────────────────────────────────────────────
from app.auth.routes import router as auth_router
from app.api.routes.studente import router as studente_router
from app.api.routes.docente import router as docente_router
from app.api.routes.dirigente import router as dirigente_router
from app.api.routes.admin import router as admin_router

app.include_router(auth_router)
app.include_router(studente_router, prefix="/api")
app.include_router(docente_router, prefix="/api")
app.include_router(dirigente_router, prefix="/api")
app.include_router(admin_router, prefix="/api")


# ── Pagine HTML ───────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/studente", response_class=HTMLResponse)
async def portale_studente(request: Request):
    return templates.TemplateResponse("studente/index.html", {"request": request})

@app.get("/docente", response_class=HTMLResponse)
async def portale_docente(request: Request):
    return templates.TemplateResponse("docente/index.html", {"request": request})

@app.get("/dirigente", response_class=HTMLResponse)
async def portale_dirigente(request: Request):
    return templates.TemplateResponse("dirigente/index.html", {"request": request})


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    from app.rag.llm_local import llm
    from app.rag.vectorstore import vectorstore
    return {
        "status": "ok",
        "version": "2.0.0",
        "vllm": await llm.health_check(),
        "qdrant": bool(vectorstore.client)
    }


# ── Avvio diretto ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    from config import APP_HOST, APP_PORT, APP_DEBUG
    uvicorn.run(
        "main:app",
        host=APP_HOST,
        port=APP_PORT,
        reload=APP_DEBUG,
        workers=1  # 1 worker: il modello embeddings è un singleton in memoria
    )
