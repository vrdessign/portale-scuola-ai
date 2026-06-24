"""
app/api/routes/studente.py — API Portale Studenti
"""
import uuid
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.session import get_db
from app.database.models import Utente, RuoloUtente, SessioneAI
from app.auth.utils import require_role
from app.rag.dual_rag import dual_rag

router = APIRouter(prefix="/studente", tags=["Portale Studente"])

# Solo studenti accedono a queste route
StudenteOnly = require_role(RuoloUtente.studente)


class DomandaRequest(BaseModel):
    domanda: str
    materia: Optional[str] = None
    history: Optional[List[dict]] = None
    stream: bool = False


@router.post("/chiedi")
async def chiedi(
    req: DomandaRequest,
    user: Utente = Depends(StudenteOnly),
    db: AsyncSession = Depends(get_db)
):
    """
    Endpoint principale: lo studente pone una domanda.
    Il sistema risponde usando il D-RAG-E con watermark AI Act Art. 50.
    Non salva il testo della conversazione (privacy by default).
    """
    if not user.codice_istituto:
        raise HTTPException(status_code=400, detail="Istituto non configurato")

    if req.stream:
        result = await dual_rag.query(
            domanda=req.domanda,
            codice_istituto=user.codice_istituto,
            user_type="studente",
            materia=req.materia,
            grado=user.grado.value if user.grado else None,
            history=req.history,
            stream=True
        )

        async def event_stream():
            async for token in result["stream"]:
                yield f"data: {token}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    # Risposta completa (non streaming)
    result = await dual_rag.query(
        domanda=req.domanda,
        codice_istituto=user.codice_istituto,
        user_type="studente",
        materia=req.materia,
        grado=user.grado.value if user.grado else None,
        history=req.history
    )

    # Log anonimizzato della sessione (zero testo salvato)
    sessione = SessioneAI(
        id=str(uuid.uuid4()),
        utente_id=user.id,
        codice_istituto=user.codice_istituto,
        materia=result.get("materia"),
        n_messaggi=1,
        rag_l1_hits=result.get("rag_l1_count", 0),
        rag_l2_hits=result.get("rag_l2_count", 0),
        data_fine=datetime.utcnow()
    )
    db.add(sessione)
    await db.commit()

    return result


@router.get("/materie")
async def materie_disponibili(
    user: Utente = Depends(StudenteOnly),
    db: AsyncSession = Depends(get_db)
):
    """Materie per cui esistono documenti RAG L2 nell'istituto dello studente."""
    from app.rag.vectorstore import vectorstore
    stats = vectorstore.collection_stats(f"rag_istituto_{user.codice_istituto}")
    return {
        "codice_istituto": user.codice_istituto,
        "documenti_disponibili": stats.get("total_chunks", 0) > 0,
        "stats": stats
    }
