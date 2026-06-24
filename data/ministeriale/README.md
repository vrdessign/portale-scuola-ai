# Corpus RAG L1 — Curricola Ministeriali

Questa cartella contiene i documenti ministeriali indicizzati nel **RAG Layer 1** del sistema D-RAG-E.

## Documenti da caricare

Inserire in questa cartella (in formato `.txt`, `.pdf` o `.docx`):

| Documento | Fonte ufficiale |
|---|---|
| Indicazioni Nazionali per il Curricolo — Primo Ciclo (DM 254/2012) | miur.gov.it |
| Linee Guida per i Licei (DPR 89/2010) | miur.gov.it |
| Linee Guida Istituti Tecnici | miur.gov.it |
| Linee Guida Istituti Professionali | miur.gov.it |
| DM 184/2023 — Obiettivi STEM | mim.gov.it |
| Linee Guida MIM 2025 per l'AI | mim.gov.it |

## Come indicizzare

Una volta inseriti i file, usa l'endpoint admin:

```bash
curl -X POST http://localhost:5000/api/admin/carica-curricola \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@indicazioni_nazionali.pdf" \
  -F "materia=matematica" \
  -F "tipo=indicazioni_nazionali"
```

I documenti ministeriali italiani sono pubblici e liberamente scaricabili dai siti istituzionali MIM/MIUR.
