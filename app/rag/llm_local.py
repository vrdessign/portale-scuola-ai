"""
app/rag/llm_local.py — Client LLM locale via vLLM
vLLM espone un endpoint compatibile OpenAI — zero API esterne.
Ottimizzato per LLaMA 3.1 70B su H100.
"""
import logging
import httpx
import json
from typing import Optional, AsyncIterator
from config import LLM_BASE_URL, LLM_MODEL, LLM_MAX_TOKENS, LLM_TEMPERATURE, LLM_TIMEOUT

logger = logging.getLogger(__name__)

# ── System prompt pedagogico ──────────────────────────────────────────────────

SYSTEM_PROMPT_STUDENTE = """Sei un assistente educativo scolastico italiano chiamato PortaleAI.
Rispondi SOLO in base ai documenti forniti nel contesto (curricola ministeriali e libro di testo dell'istituto).
Non inventare informazioni non presenti nel contesto.
Adatta il linguaggio all'età dello studente.
Non svolgere mai i compiti direttamente: guida lo studente con domande socratiche.
Cita sempre la fonte (libro di testo o documento ministeriale) alla fine della risposta.
Se la domanda non riguarda le materie scolastiche, rispondi che puoi aiutare solo su argomenti scolastici.
Ogni risposta deve terminare con: [Generato con AI — Portale Scuola AI]"""

SYSTEM_PROMPT_DOCENTE = """Sei un assistente pedagogico per docenti scolastici italiani chiamato PortaleAI.
Hai accesso ai curricola ministeriali italiani e ai libri di testo adottati dall'istituto.
Aiuta i docenti a creare materiali didattici, lezioni, esercizi e valutazioni coerenti con i programmi.
Fornisci sempre riferimenti alle Indicazioni Nazionali o ai documenti ministeriali quando pertinente.
Ogni risposta deve terminare con: [Generato con AI — Portale Scuola AI]"""

SYSTEM_PROMPT_DIRIGENTE = """Sei un assistente per la governance scolastica chiamato PortaleAI.
Fornisci informazioni sulla conformità normativa (MIM 2025, AI Act, GDPR), sulla gestione dell'istituto
e sull'utilizzo del sistema AI da parte di docenti e studenti.
Ogni risposta deve terminare con: [Generato con AI — Portale Scuola AI]"""


class LocalLLM:
    """
    Client per il modello LLM locale (vLLM).
    Usa l'endpoint compatibile OpenAI esposto da vLLM.
    """

    def __init__(self):
        self.base_url = LLM_BASE_URL.rstrip("/")
        self.model = LLM_MODEL
        self.headers = {"Content-Type": "application/json"}
        logger.info(f"LLM locale configurato: {self.model} @ {self.base_url}")

    def _build_messages(
        self,
        query: str,
        context_l1: str,
        context_l2: str,
        user_type: str = "studente",
        history: Optional[list] = None
    ) -> list:
        """Costruisce la lista messaggi per il modello."""
        system_map = {
            "studente": SYSTEM_PROMPT_STUDENTE,
            "docente": SYSTEM_PROMPT_DOCENTE,
            "dirigente": SYSTEM_PROMPT_DIRIGENTE
        }
        system = system_map.get(user_type, SYSTEM_PROMPT_STUDENTE)

        # Contesto aumentato
        context_block = ""
        if context_l1:
            context_block += f"\n--- CURRICOLA MINISTERIALI (RAG L1) ---\n{context_l1}\n"
        if context_l2:
            context_block += f"\n--- LIBRO DI TESTO ADOTTATO (RAG L2) ---\n{context_l2}\n"

        messages = [{"role": "system", "content": system}]

        if history:
            messages.extend(history[-6:])  # max 6 turni di storico

        user_content = query
        if context_block:
            user_content = f"{context_block}\n---\nDomanda: {query}"

        messages.append({"role": "user", "content": user_content})
        return messages

    async def generate(
        self,
        query: str,
        context_l1: str = "",
        context_l2: str = "",
        user_type: str = "studente",
        history: Optional[list] = None,
        temperatura: Optional[float] = None
    ) -> str:
        """Genera una risposta completa (non streaming)."""
        messages = self._build_messages(query, context_l1, context_l2, user_type, history)

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": LLM_MAX_TOKENS,
            "temperature": temperatura if temperatura is not None else LLM_TEMPERATURE,
            "stream": False
        }

        async with httpx.AsyncClient(timeout=LLM_TIMEOUT) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=payload
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    async def generate_stream(
        self,
        query: str,
        context_l1: str = "",
        context_l2: str = "",
        user_type: str = "studente",
        history: Optional[list] = None
    ) -> AsyncIterator[str]:
        """Genera una risposta in streaming (token per token)."""
        messages = self._build_messages(query, context_l1, context_l2, user_type, history)

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": LLM_MAX_TOKENS,
            "temperature": LLM_TEMPERATURE,
            "stream": True
        }

        async with httpx.AsyncClient(timeout=LLM_TIMEOUT) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=payload
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            delta = data["choices"][0]["delta"].get("content", "")
                            if delta:
                                yield delta
                        except json.JSONDecodeError:
                            continue

    async def health_check(self) -> bool:
        """Verifica che il server vLLM sia raggiungibile."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self.base_url}/models")
                return resp.status_code == 200
        except Exception:
            return False


# Istanza globale
llm = LocalLLM()
