"""
app/auth/routes.py — Endpoint autenticazione
"""
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database.session import get_db
from app.database.models import Utente, RuoloUtente, GradoScolastico
from app.auth.utils import hash_password, verify_password, create_token, get_current_user

router = APIRouter(prefix="/auth", tags=["Autenticazione"])


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    nome: str
    cognome: str
    ruolo: RuoloUtente
    codice_istituto: str
    grado: GradoScolastico = None
    classe: str = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    ruolo: str
    nome: str


@router.post("/login", response_model=TokenResponse)
async def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Utente).where(Utente.email == form.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(form.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o password errati"
        )
    if not user.attivo:
        raise HTTPException(status_code=403, detail="Account disattivato")

    # Aggiorna ultimo accesso
    user.ultimo_accesso = datetime.utcnow()
    await db.commit()

    token = create_token({"sub": user.id, "ruolo": user.ruolo.value})
    return TokenResponse(
        access_token=token,
        ruolo=user.ruolo.value,
        nome=f"{user.nome} {user.cognome}"
    )


@router.post("/register", status_code=201)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    # Controlla duplicati
    result = await db.execute(select(Utente).where(Utente.email == req.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email già registrata")

    user = Utente(
        id=str(uuid.uuid4()),
        email=req.email,
        nome=req.nome,
        cognome=req.cognome,
        password_hash=hash_password(req.password),
        ruolo=req.ruolo,
        codice_istituto=req.codice_istituto,
        grado=req.grado,
        classe=req.classe
    )
    db.add(user)
    await db.commit()
    return {"message": "Registrazione completata", "id": user.id}


@router.get("/me")
async def me(user: Utente = Depends(get_current_user)):
    return {
        "id": user.id,
        "email": user.email,
        "nome": user.nome,
        "cognome": user.cognome,
        "ruolo": user.ruolo.value,
        "codice_istituto": user.codice_istituto,
        "grado": user.grado.value if user.grado else None,
        "classe": user.classe
    }
