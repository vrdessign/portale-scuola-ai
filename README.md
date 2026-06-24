# EduRAG — Dual RAG Educativo (D-RAG-E)

[![License: CC BY-NC 4.0](https://img.shields.io/badge/License-CC%20BY--NC%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-nc/4.0/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green.svg)](https://fastapi.tiangolo.com/)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.20826793.svg)](https://doi.org/10.5281/zenodo.20826793)

> **DOI:** `10.5281/zenodo.20826793` — [View on Zenodo](https://doi.org/10.5281/zenodo.20826793)

---

**EduRAG** (commercially: *Portale Scuola AI*) is a SaaS platform implementing the **Dual RAG Educativo (D-RAG-E)** architecture — an original technical contribution for the structured and compliant integration of artificial intelligence into national education systems.

The system introduces a two-tier hierarchical Retrieval-Augmented Generation system that simultaneously guarantees:
- **RAG Layer 1** — conformity with national ministerial curricula
- **RAG Layer 2** — per-institution narrative personalisation based on adopted textbooks

Compliant with **EU AI Act**, **GDPR**, and **Italian MIM 2025 Guidelines**.

📄 **White Paper (EN):** [EduRAG: A Dual RAG Architecture for Sovereign AI in National Education Systems](https://doi.org/10.5281/zenodo.20826793)
📄 **White Paper (IT):** Portale Scuola AI — L'Intelligenza Artificiale Sovrana al Servizio dell'Istruzione *(DOI pending — publishing soon on Zenodo)*

---

## Architecture — D-RAG-E Pipeline

```
Student/Teacher query
        │
        ▼
Subject auto-detection (keyword matching)
        │
        ▼
RAG L1 — Ministerial curricula search
        │     (cosine similarity ≥ 0.75)
        ▼
RAG L2 — Institution textbook search
        │     (per-school isolated collection)
        ▼
Hierarchical merge: L1 has absolute priority over L2
        │
        ▼
Augmented prompt → Local LLM (vLLM / LLaMA 3.1 70B)
        │
        ▼
Post-processing: AI Act Art. 50 watermark + source citation
        │
        ▼
Response to user (streaming SSE or full JSON)
```

---

## Technology Stack (100% local, zero external APIs)

| Layer | Technology | Notes |
|---|---|---|
| LLM | vLLM + LLaMA 3.1 70B | OpenAI-compatible endpoint on H100 |
| Embeddings | sentence-transformers (multilingual-e5-large) | Italian + Arabic MSA support |
| Vector DB | Qdrant | Per-school isolated collections |
| Backend | FastAPI + asyncio | Native SSE streaming |
| Database | PostgreSQL + SQLAlchemy async | GDPR-compliant anonymised logs |
| Deploy | Docker + docker-compose | SuperPOD ready |

---

## Quick Start (SuperPOD / Local GPU)

### Prerequisites
- NVIDIA GPU (H100 or A100) with driver 535+
- Docker + docker-compose
- nvidia-container-toolkit

### 1. Clone and configure
```bash
git clone https://github.com/vrdessign/portale-scuola-ai.git
cd portale-scuola-ai
cp .env.example .env
# Edit .env — set a strong SECRET_KEY
```

### 2. Start all services
```bash
docker compose up -d
```
This starts in order: PostgreSQL → Qdrant → vLLM (loads LLaMA 70B, ~5 min) → EduRAG Portal

### 3. Verify
```bash
curl http://localhost:5000/health
# Expected: {"status":"ok","vllm":true,"qdrant":true}
```

### 4. Create admin user
```bash
curl -X POST http://localhost:5000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@school.it",
    "password": "change_me",
    "nome": "Admin",
    "cognome": "Sistema",
    "ruolo": "admin",
    "codice_istituto": "SISTEMA"
  }'
```

---

## Project Structure

```
portale-scuola-ai/
├── main.py                    # FastAPI entry point
├── config.py                  # Centralised configuration
├── docker-compose.yml         # SuperPOD deploy
├── Dockerfile
├── requirements.txt
├── CITATION.cff               # How to cite this software
│
├── app/
│   ├── rag/
│   │   ├── embeddings.py      # Local embeddings (sentence-transformers)
│   │   ├── vectorstore.py     # Qdrant client + per-school isolation
│   │   ├── llm_local.py       # vLLM client (OpenAI-compatible)
│   │   ├── dual_rag.py        ★ D-RAG-E orchestrator (core IP)
│   │   └── document_processor.py  # Document chunking
│   │
│   ├── api/routes/
│   │   ├── studente.py        # /api/studente/* (student portal)
│   │   ├── docente.py         # /api/docente/* (teacher portal)
│   │   ├── dirigente.py       # /api/dirigente/* (principal portal)
│   │   └── admin.py           # /api/admin/* (RAG L1 management)
│   │
│   ├── auth/
│   │   ├── utils.py           # JWT + bcrypt + role checking
│   │   └── routes.py          # /auth/login, /auth/register
│   │
│   └── database/
│       ├── models.py          # Users, Schools, Documents, Sessions, Alerts
│       └── session.py         # PostgreSQL async session
│
└── data/
    ├── ministeriale/          # RAG L1 corpus (ministerial documents)
    │   └── README.md          # Instructions for loading curricula
    └── uploads/               # Temporary upload folder
```

---

## API Reference

| Method | Endpoint | Role | Description |
|---|---|---|---|
| POST | /auth/login | All | Login → JWT token |
| POST | /auth/register | Admin | Create user |
| POST | /api/studente/chiedi | Student | Ask D-RAG-E |
| POST | /api/docente/chiedi | Teacher | Didactic assistant |
| POST | /api/docente/genera-lezione | Teacher | Generate lesson structure |
| POST | /api/dirigente/carica-libro-testo | Principal | Upload textbook → RAG L2 |
| GET | /api/dirigente/dashboard | Principal | School statistics |
| GET | /api/dirigente/alert | Principal | Usage anomaly alerts |
| POST | /api/admin/carica-curricola | Admin | Upload curricula → RAG L1 |
| GET | /api/admin/statistiche-rag | Admin | Global Qdrant stats |
| GET | /api/admin/llm-status | Admin | Check vLLM online |
| GET | /health | All | System health check |

---

## Regulatory Compliance

| Requirement | Implementation |
|---|---|
| AI Act Art. 50 — Transparency | Automatic non-bypassable watermark on every AI response |
| GDPR Art. 5 — Data minimisation | Zero conversation retention post-session |
| GDPR Art. 8 — Minor consent | Age gate + parental email verification for under-14 |
| GDPR Art. 35 — DPIA | Integrated DPIA wizard in Principal Portal |
| MIM 2025 — 5-phase framework | Complete onboarding pipeline with digital tools |
| AI Act Art. 5 — Prohibited practices | Architectural exclusion of sentiment analysis, profiling, emotion detection |

---

## Citing This Work

If you use EduRAG in your research, please cite:

```bibtex
@software{dessi2026edurag,
  author       = {Dessi, Cristian},
  title        = {EduRAG — Dual RAG Educativo (D-RAG-E)},
  year         = 2026,
  publisher    = {Zenodo},
  version      = {2.0.0},
  doi          = {10.5281/zenodo.20826793},
  url          = {https://github.com/vrdessign/portale-scuola-ai}
}

@techreport{dessi2026edurag_wp,
  author       = {Dessi, Cristian},
  title        = {EduRAG: A Dual Retrieval-Augmented Generation Architecture
                  for Sovereign AI in National Education Systems},
  institution  = {Dessign Innovation},
  year         = 2026,
  type         = {White Paper},
  doi          = {10.5281/zenodo.20826793}
}
```

---

## License

**Software:** This repository is published under [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/).
You may use, adapt and share for non-commercial purposes with attribution.
Commercial use requires written authorisation from Dessign Innovation.

**Architecture:** The D-RAG-E (Dual RAG Educativo) architecture is an original intellectual
contribution of Cristian Dessi / Dessign Innovation (VAT IT02619650909).
It is protected under Italian copyright law (L. 633/1941) and trade secret law
(D.Lgs. 63/2018). Deposited with SIAE and UIBM.

---

## Contact

**Cristian Dessi** — Founder & CEO, Dessign Innovation
- Email: vrdessign@gmail.com
- Commercial: commerciale@tourvirtuale.digital
- Web: www.dessign.it
- LinkedIn: linkedin.com/in/cristian-dessi

© 2026 Dessign Innovation — Cristian Dessi. All rights reserved.
