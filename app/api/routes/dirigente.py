"""
app/api/routes/dirigente.py — API Portale Dirigenti
Upload libri di testo (RAG L2), dashboard, statistiche istituto.
"""
import uuid
import shutil
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database.session import get_db
from app.database.models import Utente, RuoloUtente, DocumentoRAG, SessioneAI, AlertAI
from app.auth.utils import require_role
from app.rag.dual_rag import indexer
from config import UPLOADS_DIR

router = APIRouter(prefix="/dirigente", tags=["Portale Dirigente"])
DirigenteOnly = require_role(RuoloUtente.dirigente, RuoloUtente.admin)


@router.post("/carica-libro-testo")
async def carica_libro_testo(
    file: UploadFile = File(...),
    materia: str = Form(...),
    anno_scolastico: str = Form(...),
    classe: Optional[str] = Form(None),
    titolo: Optional[str] = Form(None),
    autore: Optional[str] = Form(None),
    user: Utente = Depends(DirigenteOnly),
    db: AsyncSession = Depends(get_db)
):
    """
    Il dirigente carica un libro di testo nel RAG L2 del proprio istituto.
    Formati supportati: .txt, .pdf, .docx
    """
    # Valida formato
    ext = Path(file.filename).suffix.lower()
    if ext not in [".txt", ".pdf", ".docx"]:
        raise HTTPException(
            status_code=400,
            detail=f"Formato '{ext}' non supportato. Usa .txt, .pdf o .docx"
        )

    # Salva il file temporaneamente
    upload_dir = UPLOADS_DIR / user.codice_istituto
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / f"{uuid.uuid4()}_{file.filename}"

    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Indicizza nel RAG L2
    try:
        result = await indexer.index_libro_testo(
            file_path=file_path,
            codice_istituto=user.codice_istituto,
            materia=materia,
            anno_scolastico=anno_scolastico,
            classe=classe,
            titolo=titolo or file.filename,
            autore=autore
        )
    except Exception as e:
        file_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Errore indicizzazione: {str(e)}")

    # Registra nel DB
    doc = DocumentoRAG(
        id=str(uuid.uuid4()),
        codice_istituto=user.codice_istituto,
        livello_rag="L2",
        tipo="libro_testo",
        materia=materia,
        titolo=titolo or file.filename,
        autore=autore,
        anno_scolastico=anno_scolastico,
        classe=classe,
        n_chunks=result["indicizzati"],
        caricato_da=user.id
    )
    db.add(doc)
    await db.commit()

    return {
        "messaggio": "Libro di testo caricato e indicizzato con successo",
        "documento_id": doc.id,
        "chunks_indicizzati": result["indicizzati"],
        "materia": materia
    }


@router.get("/dashboard")
async def dashboard(
    user: Utente = Depends(DirigenteOnly),
    db: AsyncSession = Depends(get_db)
):
    """Dashboard principale del dirigente: statistiche istituto."""
    codice = user.codice_istituto

    # Conteggi utenti
    utenti_result = await db.execute(
        select(Utente.ruolo, func.count(Utente.id))
        .where(Utente.codice_istituto == codice)
        .group_by(Utente.ruolo)
    )
    utenti_per_ruolo = {r: c for r, c in utenti_result.all()}

    # Sessioni ultimo 30 giorni
    from datetime import datetime, timedelta
    data_limite = datetime.utcnow() - timedelta(days=30)
    sessioni_result = await db.execute(
        select(func.count(SessioneAI.id), func.sum(SessioneAI.n_messaggi))
        .where(
            SessioneAI.codice_istituto == codice,
            SessioneAI.data_inizio >= data_limite
        )
    )
    n_sessioni, n_messaggi = sessioni_result.one()

    # Documenti RAG L2 caricati
    docs_result = await db.execute(
        select(func.count(DocumentoRAG.id), func.sum(DocumentoRAG.n_chunks))
        .where(DocumentoRAG.codice_istituto == codice, DocumentoRAG.attivo == True)
    )
    n_docs, n_chunks = docs_result.one()

    # Alert aperti
    alert_result = await db.execute(
        select(func.count(AlertAI.id))
        .where(AlertAI.codice_istituto == codice, AlertAI.risolto == False)
    )
    n_alert = alert_result.scalar()

    # Statistiche RAG
    from app.rag.vectorstore import vectorstore
    stats_l2 = vectorstore.collection_stats(f"rag_istituto_{codice}")

    return {
        "codice_istituto": codice,
        "utenti": {
            "studenti": utenti_per_ruolo.get("studente", 0),
            "docenti": utenti_per_ruolo.get("docente", 0)
        },
        "utilizzo_30gg": {
            "sessioni": n_sessioni or 0,
            "messaggi": int(n_messaggi or 0)
        },
        "rag_l2": {
            "documenti_caricati": n_docs or 0,
            "chunks_nel_vectorstore": stats_l2.get("total_chunks", 0)
        },
        "alert_aperti": n_alert or 0
    }


@router.get("/documenti")
async def lista_documenti(
    user: Utente = Depends(DirigenteOnly),
    db: AsyncSession = Depends(get_db)
):
    """Lista dei libri di testo caricati nell'istituto."""
    result = await db.execute(
        select(DocumentoRAG)
        .where(
            DocumentoRAG.codice_istituto == user.codice_istituto,
            DocumentoRAG.attivo == True
        )
        .order_by(DocumentoRAG.data_caricamento.desc())
    )
    docs = result.scalars().all()
    return [
        {
            "id": d.id,
            "titolo": d.titolo,
            "materia": d.materia,
            "classe": d.classe,
            "anno_scolastico": d.anno_scolastico,
            "n_chunks": d.n_chunks,
            "data": d.data_caricamento.isoformat()
        }
        for d in docs
    ]


@router.delete("/documenti/{doc_id}")
async def rimuovi_documento(
    doc_id: str,
    user: Utente = Depends(DirigenteOnly),
    db: AsyncSession = Depends(get_db)
):
    """Rimuove un libro di testo dal RAG L2 dell'istituto."""
    result = await db.execute(
        select(DocumentoRAG).where(
            DocumentoRAG.id == doc_id,
            DocumentoRAG.codice_istituto == user.codice_istituto
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Documento non trovato")

    # Rimuovi dal vectorstore
    documento_id = f"{user.codice_istituto}_{doc.materia}_{doc.titolo}"
    await indexer.rimuovi_documento_l2(user.codice_istituto, documento_id)

    # Disattiva nel DB
    doc.attivo = False
    await db.commit()

    return {"messaggio": "Documento rimosso con successo"}


@router.get("/alert")
async def alert_istituto(
    user: Utente = Depends(DirigenteOnly),
    db: AsyncSession = Depends(get_db)
):
    """Alert di utilizzo anomalo per l'istituto."""
    result = await db.execute(
        select(AlertAI)
        .where(AlertAI.codice_istituto == user.codice_istituto)
        .order_by(AlertAI.data.desc())
        .limit(50)
    )
    alerts = result.scalars().all()
    return [
        {
            "id": a.id,
            "tipo": a.tipo,
            "descrizione": a.descrizione,
            "risolto": a.risolto,
            "data": a.data.isoformat()
        }
        for a in alerts
    ]
