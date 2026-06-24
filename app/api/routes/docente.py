"""
app/api/routes/docente.py — API Portale Docenti
"""
import uuid
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database.session import get_db
from app.database.models import Utente, RuoloUtente, SessioneAI
from app.auth.utils import require_role
from app.rag.dual_rag import dual_rag, indexer
from config import UPLOADS_DIR
import shutil

router = APIRouter(prefix="/docente", tags=["Portale Docente"])
DocenteOnly = require_role(RuoloUtente.docente, RuoloUtente.dirigente)


class AssistenteRequest(BaseModel):
    domanda: str
    materia: Optional[str] = None
    history: Optional[List[dict]] = None


class GeneraLezioneRequest(BaseModel):
    argomento: str
    materia: str
    classe: str
    obiettivi: Optional[str] = None
    durata_minuti: int = 50


@router.post("/chiedi")
async def chiedi_assistente(
    req: AssistenteRequest,
    user: Utente = Depends(DocenteOnly),
    db: AsyncSession = Depends(get_db)
):
    """Assistente AI per docenti: accesso completo al contesto didattico."""
    result = await dual_rag.query(
        domanda=req.domanda,
        codice_istituto=user.codice_istituto,
        user_type="docente",
        materia=req.materia,
        history=req.history
    )
    return result


@router.post("/genera-lezione")
async def genera_lezione(
    req: GeneraLezioneRequest,
    user: Utente = Depends(DocenteOnly)
):
    """
    Genera una struttura di lezione coerente con il libro di testo adottato
    e gli obiettivi ministeriali.
    """
    prompt = f"""Crea una struttura di lezione per i seguenti parametri:
- Argomento: {req.argomento}
- Materia: {req.materia}
- Classe: {req.classe}
- Durata: {req.durata_minuti} minuti
{f"- Obiettivi specifici: {req.obiettivi}" if req.obiettivi else ""}

Struttura richiesta:
1. Obiettivi di apprendimento (collegati alle Indicazioni Nazionali)
2. Prerequisiti necessari
3. Sequenza didattica (con tempi)
4. Attività principali
5. Verifica degli apprendimenti
6. Materiali necessari
7. Note per la differenziazione (studenti con BES/DSA)"""

    result = await dual_rag.query(
        domanda=prompt,
        codice_istituto=user.codice_istituto,
        user_type="docente",
        materia=req.materia
    )
    return result


@router.get("/sessioni")
async def sessioni_studenti(
    user: Utente = Depends(DocenteOnly),
    db: AsyncSession = Depends(get_db)
):
    """Statistiche aggregate delle sessioni degli studenti (anonimizzate)."""
    result = await db.execute(
        select(SessioneAI)
        .where(SessioneAI.codice_istituto == user.codice_istituto)
        .order_by(SessioneAI.data_inizio.desc())
        .limit(100)
    )
    sessioni = result.scalars().all()
    return {
        "totale_sessioni": len(sessioni),
        "totale_messaggi": sum(s.n_messaggi for s in sessioni),
        "media_rag_l1_hits": sum(s.rag_l1_hits for s in sessioni) / max(len(sessioni), 1),
        "media_rag_l2_hits": sum(s.rag_l2_hits for s in sessioni) / max(len(sessioni), 1),
    }
