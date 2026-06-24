"""
app/database/models.py — Modelli SQLAlchemy
"""
from datetime import datetime
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, ForeignKey, Enum
from sqlalchemy.orm import declarative_base, relationship
import enum

Base = declarative_base()


class RuoloUtente(str, enum.Enum):
    studente  = "studente"
    docente   = "docente"
    dirigente = "dirigente"
    admin     = "admin"


class GradoScolastico(str, enum.Enum):
    primaria  = "primaria"
    media     = "media"
    superiore = "superiore"


class Utente(Base):
    __tablename__ = "utenti"
    id              = Column(String, primary_key=True)
    email           = Column(String, unique=True, nullable=False, index=True)
    nome            = Column(String, nullable=False)
    cognome         = Column(String, nullable=False)
    password_hash   = Column(String, nullable=False)
    ruolo           = Column(Enum(RuoloUtente), nullable=False)
    codice_istituto = Column(String, ForeignKey("istituti.codice"), nullable=True)
    grado           = Column(Enum(GradoScolastico), nullable=True)
    classe          = Column(String, nullable=True)   # es. "3A"
    attivo          = Column(Boolean, default=True)
    consenso_minore = Column(Boolean, default=False)  # per under 14
    data_creazione  = Column(DateTime, default=datetime.utcnow)
    ultimo_accesso  = Column(DateTime, nullable=True)

    istituto        = relationship("Istituto", back_populates="utenti")
    sessioni        = relationship("SessioneAI", back_populates="utente")


class Istituto(Base):
    __tablename__ = "istituti"
    codice          = Column(String, primary_key=True)  # codice meccanografico
    nome            = Column(String, nullable=False)
    tipo            = Column(String, nullable=False)    # IC, liceo, tecnico...
    citta           = Column(String, nullable=False)
    provincia       = Column(String, nullable=False)
    email_dirigente = Column(String, nullable=False)
    piano_attivo    = Column(String, default="starter") # starter|professional|enterprise
    dpia_completata = Column(Boolean, default=False)
    data_attivazione= Column(DateTime, nullable=True)
    attivo          = Column(Boolean, default=True)

    utenti          = relationship("Utente", back_populates="istituto")
    documenti       = relationship("DocumentoRAG", back_populates="istituto")


class DocumentoRAG(Base):
    """Traccia i documenti caricati nel sistema RAG."""
    __tablename__ = "documenti_rag"
    id              = Column(String, primary_key=True)
    codice_istituto = Column(String, ForeignKey("istituti.codice"), nullable=True)
    livello_rag     = Column(String, nullable=False)    # L1 | L2
    tipo            = Column(String, nullable=False)    # libro_testo | curricola | dispensa
    materia         = Column(String, nullable=False)
    titolo          = Column(String, nullable=False)
    autore          = Column(String, nullable=True)
    anno_scolastico = Column(String, nullable=True)     # es. "2025-2026"
    classe          = Column(String, nullable=True)
    n_chunks        = Column(Integer, default=0)
    caricato_da     = Column(String, ForeignKey("utenti.id"), nullable=True)
    data_caricamento= Column(DateTime, default=datetime.utcnow)
    attivo          = Column(Boolean, default=True)

    istituto        = relationship("Istituto", back_populates="documenti")


class SessioneAI(Base):
    """Log anonimizzato delle sessioni AI (GDPR: zero dati personali nel testo)."""
    __tablename__ = "sessioni_ai"
    id              = Column(String, primary_key=True)
    utente_id       = Column(String, ForeignKey("utenti.id"), nullable=False)
    codice_istituto = Column(String, nullable=False)
    materia         = Column(String, nullable=True)
    n_messaggi      = Column(Integer, default=0)
    n_token_llm     = Column(Integer, default=0)
    rag_l1_hits     = Column(Integer, default=0)
    rag_l2_hits     = Column(Integer, default=0)
    data_inizio     = Column(DateTime, default=datetime.utcnow)
    data_fine       = Column(DateTime, nullable=True)

    utente          = relationship("Utente", back_populates="sessioni")


class AlertAI(Base):
    """Alert per anomalie di utilizzo — visibili al dirigente."""
    __tablename__ = "alert_ai"
    id              = Column(String, primary_key=True)
    codice_istituto = Column(String, nullable=False)
    tipo            = Column(String, nullable=False)  # fuori_contesto | utilizzo_anomalo | data_breach
    descrizione     = Column(Text, nullable=False)
    risolto         = Column(Boolean, default=False)
    data            = Column(DateTime, default=datetime.utcnow)
