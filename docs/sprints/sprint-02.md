# Sprint 2 — Pipeline

**Статус:** done

## Цель

Один файл проходит цепочку: URL → bytes → текст → рубрика → NITEC → JSON. Без батча и без Celery-оркестрации (ручной вызов или маленький скрипт).

## Задачи

- [x] `prompt_template.py` — промпт оценки (см. `docs/reference/pipeline.md`, старый `orleu-evaluator-main` при наличии)
- [x] `pipeline/parser.py` — парсинг `file_path` → city, trainer, group_name, file_name
- [x] `pipeline/downloader.py` — OneDrive / Google Docs / прямой URL → `(bytes, filename)`
- [x] `pipeline/converter.py` — doc→docx (LibreOffice async), docx→pdf
- [x] `pipeline/docx_utils.py` — `fix_broken_docx`, `extract_text_from_docx` (XML)
- [x] `pipeline/extractor.py` — текст из docx/pdf; fallback Vision OCR (Qwen, base64)
- [x] `pipeline/rubric_loader.py` — langdetect → `rubrics/rubric_rus.md` | `rubric_kaz.md`
- [x] `pipeline/llm.py` — NITEC `openai/gpt-oss-120b`, `parse_llm_response()`, извлечение scores
- [x] Зависимости: `langdetect`, `PyMuPDF`, `openai` — в `requirements.txt`
- [x] `Dockerfile`: LibreOffice (+ catdoc при необходимости)
- [x] Скрипт или endpoint-черновик: один URL → печать/возврат JSON

## Семафоры (заготовка в `main` lifespan)

`llm_semaphore`, `download_semaphore`, `vision_semaphore` — лимиты из `.env`.

Реализация: `config/concurrency.py` — `init_concurrency()` вызывается в `main.py` lifespan и в Celery `worker_process_init`.

## Проверка

Один публичный URL на `.docx` → валидный JSON ответа LLM (или понятная ошибка).

```bash
cp .env.example .env   # заполнить DATABASE_URL, NITEC_API_KEY
source .venv/bin/activate
pip install -r requirements.txt

# только извлечение + рубрика (без LLM)
DATABASE_URL=postgresql://... python scripts/run_pipeline.py \
  --url "https://..." \
  --file-path "ПКС2025/Астана/Иванов/Группа1/план.docx" \
  --extract-only

# полный прогон с LLM
DATABASE_URL=postgresql://... python scripts/run_pipeline.py \
  --url "https://..." \
  --file-path "ПКС2025/Астана/Иванов/Группа1/план.docx"
```

## Done (2026-04-05)

- Добавлены модули `pipeline/` (`parser`, `downloader`, `converter`, `docx_utils`, `extractor`, `rubric_loader`, `llm`, `orchestrator`), точка входа `run_pipeline()`.
- `prompt_template.py` — пользовательский промпт с ожидаемой схемой JSON (см. `docs/reference/pipeline.md`; исторический обзор — `docs/archive/orleu-batch-evaluator-knowledge-base.md`).
- `scripts/run_pipeline.py` — CLI: `--url`, опционально `--file-path`, `--extract-only`.
- `config/concurrency.py` + вызов `init_concurrency()` в FastAPI lifespan и Celery worker.
- `requirements.txt`: `openai`, `langdetect`, `PyMuPDF`; `Dockerfile`: `libreoffice-writer`, `libreoffice-calc`, `catdoc`.

## Следующий шаг

→ [sprint-03.md](sprint-03.md)
