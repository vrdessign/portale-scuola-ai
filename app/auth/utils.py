"""
app/auth/utils.py — JWT, hashing password, verifica ruoli
"""
import uuid
from datetime import datetime, timedelta
from typing import Optional
from passlib.context import CryptContext
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from config import SECRET_KEY, ACCESS_TOKEN_EXPIRE
from app.database.session import get_db
from app.database.models import Utente, RuoloUtente

ALGORITHM = "HS256"
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_token(data: dict, expires_minutes: int = ACCESS_TOKEN_EXPIRE) -> str:
    payload = {**data, "exp": datetime.utcnow() + timedelta(minutes=expires_minutes)}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> Utente:
    cred_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenziali non valide",
        headers={"WWW-Authenticate": "Bearer"}
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise cred_exc
    except JWTError:
        raise cred_exc

    result = await db.execute(select(Utente).where(Utente.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.attivo:
        raise cred_exc
    return user


def require_role(*roles: RuoloUtente):
    """Dependency: verifica che l'utente abbia uno dei ruoli richiesti."""
    async def checker(user: Utente = Depends(get_current_user)):
        if user.ruolo not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Accesso negato. Ruoli richiesti: {[r.value for r in roles]}"
            )
        return user
    return checker
