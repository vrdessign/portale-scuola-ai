"""
app/api/routes/admin.py — API Amministratore di Sistema
Indicizzazione curricola ministeriali (RAG L1) e gestione istituti.
"""
import uuid
import shutil
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database.session import get_db
from app.database.models import Utente, RuoloUtente, Istituto, DocumentoRAG
from app.auth.utils import require_role
from app.rag.dual_rag import indexer
from app.rag.vectorstore import vectorstore
from config import MINISTERIALE_DIR, COLLECTION_L1

router = APIRouter(prefix="/admin", tags=["Admin"])
AdminOnly = require_role(RuoloUtente.admin)


@router.post("/carica-curricola")
async def carica_curricola_ministeriale(
    file: UploadFile = File(...),
    materia: str = Form(...),
    tipo: str = Form("indicazioni_nazionali"),
    titolo: str = Form(None),
    user: Utente = Depends(AdminOnly),
    db: AsyncSession = Depends(get_db)
):
    """
    Carica un documento ministeriale nel RAG L1 (curricola nazionali).
    Solo l'amministratore di sistema può farlo.
    """
    ext = Path(file.filename).suffix.lower()
    if ext not in [".txt", ".pdf", ".docx"]:
        raise HTTPException(status_code=400, detail="Formato non supportato")

    # Inizializza collection L1 se necessario
    vectorstore.init_collection_l1()

    # Salva il file
    file_path = MINISTERIALE_DIR / f"{uuid.uuid4()}_{file.filename}"
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        result = await indexer.index_ministeriale(
            file_path=file_path,
            materia=materia,
            tipo=tipo,
            titolo=titolo or file.filename
        )
    except Exception as e:
        file_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=str(e))

    # Registra nel DB
    doc = DocumentoRAG(
        id=str(uuid.uuid4()),
        codice_istituto=None,
        livello_rag="L1",
        tipo=tipo,
        materia=materia,
        titolo=titolo or file.filename,
        n_chunks=result["indicizzati"],
        caricato_da=user.id
    )
    db.add(doc)
    await db.commit()

    return {
        "messaggio": "Curricola ministeriale indicizzata",
        "chunks": result["indicizzati"],
        "materia": materia,
        "tipo": tipo
    }


@router.get("/statistiche-rag")
async def statistiche_rag(user: Utente = Depends(AdminOnly)):
    """Statistiche globali del sistema RAG."""
    stats_l1 = vectorstore.collection_stats(COLLECTION_L1)
    collections = [c.name for c in vectorstore.client.get_collections().collections]
    istituti_con_l2 = [c for c in collections if c.startswith("rag_istituto_")]
    return {
        "rag_l1": stats_l1,
        "rag_l2_istituti": len(istituti_con_l2),
        "collections_l2": istituti_con_l2
    }


class IstitutoCreate(BaseModel):
    codice: str
    nome: str
    tipo: str
    citta: str
    provincia: str
    email_dirigente: str
    piano_attivo: str = "starter"


@router.post("/istituti", status_code=201)
async def crea_istituto(
    req: IstitutoCreate,
    user: Utente = Depends(AdminOnly),
    db: AsyncSession = Depends(get_db)
):
    """Registra un nuovo istituto nel sistema."""
    istituto = Istituto(**req.model_dump())
    db.add(istituto)
    await db.commit()
    # Inizializza collection L2 vuota
    vectorstore.init_collection_l2(req.codice)
    return {"messaggio": "Istituto registrato", "codice": req.codice}


@router.get("/istituti")
async def lista_istituti(
    user: Utente = Depends(AdminOnly),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Istituto).where(Istituto.attivo == True))
    istituti = result.scalars().all()
    return [
        {
            "codice": i.codice,
            "nome": i.nome,
            "tipo": i.tipo,
            "citta": i.citta,
            "piano": i.piano_attivo,
            "dpia": i.dpia_completata
        }
        for i in istituti
    ]


@router.get("/llm-status")
async def llm_status(user: Utente = Depends(AdminOnly)):
    """Verifica che il server vLLM sia raggiungibile."""
    from app.rag.llm_local import llm
    ok = await llm.health_check()
    return {"vllm_online": ok, "model": llm.model, "endpoint": llm.base_url}
