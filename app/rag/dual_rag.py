"""
app/rag/dual_rag.py — D-RAG-E: Dual RAG Educativo
Architettura originale Portale Scuola AI (© Cristian Dessi, Dessign Innovation 2025)

Flusso:
  1. Query utente
  2. Recupero RAG L1 (curricola ministeriali) — priorità assoluta
  3. Recupero RAG L2 (libri di testo istituto) — personalizzazione narrativa
  4. Fusione gerarchica: L1 ha priorità su L2 in caso di conflitto
  5. Generazione risposta con LLM locale
  6. Post-processing: watermark AI Act Art. 50, citazione fonti
"""
import logging
from typing import Dict, Any, Optional, List, AsyncIterator
from app.rag.vectorstore import vectorstore
from app.rag.llm_local import llm
from config import MATERIE

logger = logging.getLogger(__name__)

# Watermark obbligatorio ex AI Act Art. 50
WATERMARK = "\n\n---\n⚠️ *Contenuto generato con intelligenza artificiale — Portale Scuola AI*"


class DualRAGEngine:
    """
    Motore D-RAG-E (Dual RAG Educativo).
    Implementa l'architettura a due livelli gerarchici descritta nel White Paper.
    """

    async def query(
        self,
        domanda: str,
        codice_istituto: str,
        user_type: str = "studente",
        materia: Optional[str] = None,
        grado: Optional[str] = None,
        history: Optional[List[Dict]] = None,
        stream: bool = False
    ) -> Dict[str, Any]:
        """
        Elabora una domanda attraverso il flusso D-RAG-E completo.

        Args:
            domanda:          Testo della domanda dell'utente
            codice_istituto:  Codice univoco dell'istituto (per RAG L2)
            user_type:        studente | docente | dirigente
            materia:          Materia scolastica (opzionale, auto-rilevata)
            grado:            Grado scolastico (primaria|media|superiore)
            history:          Storico della conversazione
            stream:           Se True, ritorna un async generator

        Returns:
            Dict con risposta, fonti L1, fonti L2, metadati
        """

        # ── Step 1: Auto-rilevamento materia ─────────────────────────────────
        if not materia:
            materia = self._detect_subject(domanda)

        # ── Step 2: Recupero RAG L1 (curricola ministeriali) ─────────────────
        risultati_l1 = vectorstore.search_l1(
            query=domanda,
            materia=materia
        )
        context_l1 = self._format_context(risultati_l1, "Curricola Ministeriale")
        logger.debug(f"RAG L1: {len(risultati_l1)} risultati")

        # ── Step 3: Recupero RAG L2 (libri di testo istituto) ────────────────
        risultati_l2 = vectorstore.search_l2(
            query=domanda,
            codice_istituto=codice_istituto,
            materia=materia
        )
        context_l2 = self._format_context(risultati_l2, "Libro di testo adottato")
        logger.debug(f"RAG L2: {len(risultati_l2)} risultati")

        # ── Step 4: Adatta la query al grado scolastico ───────────────────────
        domanda_adattata = self._adapt_query(domanda, grado, user_type)

        # ── Step 5: Generazione risposta ──────────────────────────────────────
        if stream:
            return {
                "stream": self._generate_stream(
                    domanda_adattata, context_l1, context_l2, user_type, history
                ),
                "fonti_l1": self._extract_sources(risultati_l1),
                "fonti_l2": self._extract_sources(risultati_l2),
                "materia": materia,
                "rag_l1_count": len(risultati_l1),
                "rag_l2_count": len(risultati_l2)
            }

        risposta = await llm.generate(
            query=domanda_adattata,
            context_l1=context_l1,
            context_l2=context_l2,
            user_type=user_type,
            history=history
        )

        # ── Step 6: Post-processing ───────────────────────────────────────────
        risposta_finale = risposta + WATERMARK

        return {
            "risposta": risposta_finale,
            "fonti_l1": self._extract_sources(risultati_l1),
            "fonti_l2": self._extract_sources(risultati_l2),
            "materia": materia,
            "rag_l1_count": len(risultati_l1),
            "rag_l2_count": len(risultati_l2),
            "ha_contesto_ministeriale": len(risultati_l1) > 0,
            "ha_contesto_istituto": len(risultati_l2) > 0
        }

    async def _generate_stream(
        self,
        domanda: str,
        context_l1: str,
        context_l2: str,
        user_type: str,
        history: Optional[List]
    ) -> AsyncIterator[str]:
        """Wrapper stream con watermark finale."""
        async for token in llm.generate_stream(
            query=domanda,
            context_l1=context_l1,
            context_l2=context_l2,
            user_type=user_type,
            history=history
        ):
            yield token
        yield WATERMARK

    def _format_context(self, risultati: List[Dict], label: str) -> str:
        """Formatta i risultati RAG in un blocco di contesto per il LLM."""
        if not risultati:
            return ""
        blocks = []
        for i, r in enumerate(risultati, 1):
            source = r["metadata"].get("source", "documento")
            score = r.get("score", 0)
            blocks.append(f"[{label} — Fonte {i}: {source} (rilevanza: {score:.2f})]\n{r['text']}")
        return "\n\n".join(blocks)

    def _extract_sources(self, risultati: List[Dict]) -> List[Dict]:
        """Estrae le informazioni sulle fonti per la risposta al frontend."""
        return [
            {
                "source": r["metadata"].get("source", "documento"),
                "materia": r["metadata"].get("materia", ""),
                "score": round(r.get("score", 0), 3),
                "tipo": r["metadata"].get("tipo_documento", "documento")
            }
            for r in risultati
        ]

    def _detect_subject(self, testo: str) -> Optional[str]:
        """Rileva la materia dalla domanda (keyword matching semplice)."""
        testo_lower = testo.lower()
        keywords = {
            "matematica": ["equazion", "frazione", "geometri", "calcol", "algebr", "numero"],
            "italiano": ["grammatica", "analisi", "poesia", "testo", "verbo", "autore", "libro"],
            "storia": ["guerra", "impero", "rivoluzion", "storia", "secolo", "civiltà", "evento"],
            "scienze": ["cellula", "organismo", "ecosistema", "chimica", "fisica", "energia"],
            "fisica": ["forza", "velocità", "accelerazion", "gravità", "elettr", "magneti"],
            "chimica": ["molecola", "atomo", "elemento", "reazion", "formula", "composto"],
            "geografia": ["continente", "paese", "clima", "montagna", "fiume", "capitale"],
            "inglese": ["english", "grammar", "verb", "present", "past", "vocabulary"],
            "filosofia": ["filosofo", "pensiero", "etica", "platone", "aristotele", "kant"],
        }
        for materia, kw_list in keywords.items():
            if any(kw in testo_lower for kw in kw_list):
                return materia
        return None

    def _adapt_query(self, domanda: str, grado: Optional[str], user_type: str) -> str:
        """Adatta la query aggiungendo contesto sul grado scolastico."""
        if user_type != "studente" or not grado:
            return domanda
        adattamenti = {
            "primaria":  "Rispondi in modo molto semplice, con parole facili, per bambini della scuola primaria. ",
            "media":     "Rispondi in modo chiaro e diretto per studenti della scuola media (11-14 anni). ",
            "superiore": "Rispondi in modo approfondito per studenti della scuola superiore (14-19 anni). "
        }
        prefisso = adattamenti.get(grado, "")
        return prefisso + domanda if prefisso else domanda


class DocumentIndexer:
    """
    Gestisce l'indicizzazione dei documenti nel sistema D-RAG-E.
    RAG L1: amministratore di sistema (carica curricola ministeriali)
    RAG L2: dirigente scolastico (carica libri di testo dell'istituto)
    """

    def __init__(self):
        from app.rag.document_processor import process_document, process_directory
        self.process_document = process_document
        self.process_directory = process_directory

    async def index_ministeriale(
        self,
        file_path,
        materia: str,
        tipo: str = "indicazioni_nazionali",
        titolo: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Indicizza un documento ministeriale nel RAG L1.
        Solo l'amministratore di sistema può farlo.
        """
        from pathlib import Path
        path = Path(file_path)

        metadata = {
            "tipo_documento": tipo,
            "materia": materia,
            "titolo": titolo or path.stem,
            "documento_id": path.stem,
            "livello_rag": "L1"
        }

        chunks, metas = self.process_document(path, metadata)
        n = vectorstore.index_chunks(
            collection="rag_ministeriale",
            chunks=chunks,
            metadatas=metas
        )

        return {"indicizzati": n, "materia": materia, "file": path.name}

    async def index_libro_testo(
        self,
        file_path,
        codice_istituto: str,
        materia: str,
        anno_scolastico: str,
        classe: Optional[str] = None,
        titolo: Optional[str] = None,
        autore: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Indicizza un libro di testo nel RAG L2 dell'istituto.
        Solo il dirigente scolastico può farlo per il proprio istituto.
        """
        from pathlib import Path
        path = Path(file_path)

        # Assicura che la collection L2 esista
        collection = vectorstore.init_collection_l2(codice_istituto)

        metadata = {
            "tipo_documento": "libro_testo",
            "materia": materia,
            "classe": classe or "",
            "anno_scolastico": anno_scolastico,
            "titolo": titolo or path.stem,
            "autore": autore or "",
            "codice_istituto": codice_istituto,
            "documento_id": f"{codice_istituto}_{materia}_{path.stem}",
            "livello_rag": "L2"
        }

        chunks, metas = self.process_document(path, metadata)
        n = vectorstore.index_chunks(
            collection=collection,
            chunks=chunks,
            metadatas=metas
        )

        return {
            "indicizzati": n,
            "materia": materia,
            "codice_istituto": codice_istituto,
            "anno_scolastico": anno_scolastico,
            "file": path.name
        }

    async def rimuovi_documento_l2(
        self,
        codice_istituto: str,
        documento_id: str
    ) -> bool:
        """Rimuove un documento dalla collection L2 dell'istituto."""
        collection = f"rag_istituto_{codice_istituto}"
        try:
            vectorstore.delete_document(collection, documento_id)
            return True
        except Exception as e:
            logger.error(f"Errore rimozione documento: {e}")
            return False

    def statistiche_l1(self) -> Dict:
        return vectorstore.collection_stats("rag_ministeriale")

    def statistiche_l2(self, codice_istituto: str) -> Dict:
        return vectorstore.collection_stats(f"rag_istituto_{codice_istituto}")


# Istanze globali
dual_rag = DualRAGEngine()
indexer = DocumentIndexer()
