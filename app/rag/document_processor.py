"""
app/rag/document_processor.py — Caricamento e chunking documenti
Supporta .txt, .pdf, .docx per RAG L1 (ministeriale) e RAG L2 (libri di testo).
"""
import logging
import re
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from config import CHUNK_SIZE, CHUNK_OVERLAP

logger = logging.getLogger(__name__)


def load_text_file(path: Path) -> str:
    """Carica file .txt con gestione encoding."""
    for enc in ["utf-8", "latin-1", "cp1252"]:
        try:
            return path.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Impossibile leggere {path}")


def load_pdf(path: Path) -> str:
    """Estrae testo da PDF con pymupdf."""
    try:
        import fitz  # pymupdf
        doc = fitz.open(str(path))
        text = "\n".join(page.get_text() for page in doc)
        doc.close()
        return text
    except ImportError:
        raise ImportError("Installa pymupdf: pip install pymupdf")


def load_docx(path: Path) -> str:
    """Estrae testo da .docx."""
    try:
        import docx2txt
        return docx2txt.process(str(path))
    except ImportError:
        raise ImportError("Installa docx2txt: pip install docx2txt")


def load_document(path: Path) -> str:
    """Dispatcher: carica il documento in base all'estensione."""
    ext = path.suffix.lower()
    if ext == ".txt":
        return load_text_file(path)
    elif ext == ".pdf":
        return load_pdf(path)
    elif ext in (".docx", ".doc"):
        return load_docx(path)
    else:
        raise ValueError(f"Formato non supportato: {ext}. Usa .txt, .pdf o .docx")


def clean_text(text: str) -> str:
    """Pulisce il testo rimuovendo artefatti e spazi multipli."""
    text = re.sub(r'\s+', ' ', text)            # spazi multipli
    text = re.sub(r'\n{3,}', '\n\n', text)      # righe vuote eccessive
    text = re.sub(r'[^\S\n]+', ' ', text)       # whitespace laterali
    return text.strip()


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """
    Divide il testo in chunk con overlap.
    Cerca di spezzare su frasi complete (punto + spazio).
    """
    text = clean_text(text)
    chunks = []
    start = 0
    length = len(text)

    while start < length:
        end = min(start + chunk_size, length)

        # Se non siamo alla fine, cerca un punto di rottura naturale
        if end < length:
            # Cerca l'ultimo punto/newline nel range [end-overlap, end]
            search_from = max(end - overlap, start + 1)
            break_pos = max(
                text.rfind('. ', search_from, end),
                text.rfind('\n', search_from, end),
                text.rfind('? ', search_from, end),
                text.rfind('! ', search_from, end),
            )
            if break_pos > start:
                end = break_pos + 1  # includi il punto

        chunk = text[start:end].strip()
        if len(chunk) > 50:  # ignora chunk troppo corti
            chunks.append(chunk)

        # Avanza con overlap
        start = end - overlap if end < length else length

    return chunks


def process_document(
    path: Path,
    metadata: Dict,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP
) -> Tuple[List[str], List[Dict]]:
    """
    Carica, pulisce e chunka un documento.
    Restituisce (chunks, metadati_per_chunk).
    """
    text = load_document(path)
    chunks = chunk_text(text, chunk_size, overlap)

    # Arricchisci i metadati con info sul chunk
    metadatas = [
        {
            **metadata,
            "chunk_index": i,
            "total_chunks": len(chunks),
            "source": str(path.name),
            "char_count": len(c)
        }
        for i, c in enumerate(chunks)
    ]

    logger.info(f"Processato '{path.name}': {len(chunks)} chunk")
    return chunks, metadatas


def process_directory(
    directory: Path,
    base_metadata: Dict,
    extensions: List[str] = [".txt", ".pdf", ".docx"]
) -> Tuple[List[str], List[Dict]]:
    """
    Processa tutti i documenti in una cartella.
    Utile per caricare i curricola ministeriali (RAG L1).
    """
    all_chunks = []
    all_metas = []

    files = [f for f in directory.rglob("*") if f.suffix.lower() in extensions]
    logger.info(f"Trovati {len(files)} file in '{directory}'")

    for file_path in sorted(files):
        try:
            meta = {**base_metadata, "documento_id": file_path.stem}
            chunks, metas = process_document(file_path, meta)
            all_chunks.extend(chunks)
            all_metas.extend(metas)
        except Exception as e:
            logger.error(f"Errore processando '{file_path}': {e}")
            continue

    logger.info(f"Totale: {len(all_chunks)} chunk da {len(files)} documenti")
    return all_chunks, all_metas
