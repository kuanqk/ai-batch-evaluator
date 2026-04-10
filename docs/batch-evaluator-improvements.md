# Orleu Batch Evaluator — План улучшений

> Документ описывает все новые фичи и изменения для объединённой платформы.
> Основа: `github.com/kuanqk/ai-batch-evaluator`
> Контекст: переносим лучшее из AI Evaluator (FastAPI), убираем зависимость от ApeRAG, добавляем мультиконфиг.

---

## Содержание

1. [Фича 1 — Новый pipeline без ApeRAG](#фича-1--новый-pipeline-без-aperag)
2. [Фича 2 — Усиление extractor из AI Evaluator](#фича-2--усиление-extractor-из-ai-evaluator)
3. [Фича 3 — Усиление LLM парсинга из AI Evaluator](#фича-3--усиление-llm-парсинга-из-ai-evaluator)
4. [Фича 4 — EvaluatorConfig — мультиконфиг инстансы](#фича-4--evaluatorconfig--мультиконфиг-инстансы)
5. [Фича 5 — SystemSettings — глобальные лимиты](#фича-5--systemsettings--глобальные-лимиты)
6. [Фича 6 — Django UI для управления конфигами](#фича-6--django-ui-для-управления-конфигами)
7. [Фича 7 — Динамические API endpoints per-config](#фича-7--динамические-api-endpoints-per-config)
8. [Фича 8 — Дашборд per-config](#фича-8--дашборд-per-config)
9. [Фича 9 — Перенос AI Evaluator в платформу](#фича-9--перенос-ai-evaluator-в-платформу)
10. [Затронутые файлы — сводная таблица](#затронутые-файлы--сводная-таблица)
11. [Порядок реализации](#порядок-реализации)

---

## Контекст проекта

### Текущий стек (не меняется)
- Django 4.2 + DRF + Celery + Redis + PostgreSQL
- Gunicorn :8502, Docker Compose
- NITEC LLM API (`llm.nitec.kz/v1`), OpenAI-совместимый, AsyncOpenAI
- PyMuPDF (`fitz`) для извлечения текста из PDF
- `tasks/evaluate.py` — `process_file`, `process_job`
- `pipeline/orchestrator.py` — `run_pipeline()`
- `apps/batch/models.py` — `EvaluationJob`, `Evaluation`

### Что убираем
- Зависимость от ApeRAG (upload → indexing → preview → markdown_content)
- ApeRAG коллекции `reports` и `criteri` больше не используются
- `aperag_semaphore` и все вызовы `http://172.17.0.1:8000`

### Что переносим из AI Evaluator (FastAPI)
- `fix_broken_docx()` — исправление NULL image refs
- Проверка truncated ZIP (повреждённый docx)
- `build_empty_result()` — структурированный ответ при ошибке
- Google Docs URL → export format конвертация
- Vision OCR страница-за-страницей через Qwen3-VL
- Двухуровневая проверка текста перед LLM
- `character_count` в `brief_report_json`
- Разворачивание `{"raw_response": "..."}` wrapper от LLM

---

## Фича 1 — Новый pipeline без ApeRAG

### Что меняется
Полностью заменяем блок ApeRAG (шаги 2–4 в AI Evaluator) на прямое извлечение текста из файла.

### Файл: `pipeline/extractor.py`

**Было (через ApeRAG):**
```
upload docx → wait indexing → GET /preview → markdown_content
```

**Станет — новая цепочка с тремя уровнями:**
```
Уровень 1: python-docx
    └── Document(BytesIO(file_content))
        ├── параграфы → plain text
        └── таблицы → markdown (| col | col | col |)

Уровень 2: PyMuPDF (если python-docx вернул < MIN_CHARS)
    └── fitz.open(pdf_path) → page.get_text() для каждой страницы

Уровень 3: Vision OCR — Qwen3-VL (если PyMuPDF вернул < MIN_CHARS)
    └── fitz → PNG per page (dpi=150, max 10 страниц)
        └── Qwen3-VL per page → concatenate text
```

### Новые функции в `pipeline/extractor.py`

```python
def extract_text_with_python_docx(file_content: bytes) -> str:
    """
    Извлекает текст из docx через python-docx.
    Таблицы конвертируются в markdown формат.
    Возвращает структурированный текст с сохранением таблиц.
    """

def _table_to_markdown(table) -> str:
    """
    Конвертирует таблицу python-docx в markdown.
    Первая строка → заголовок с разделителем |---|
    """

async def extract_text_via_vision_qwen(
    pdf_content: bytes,
    nitec_api_key: str,
    nitec_base_url: str,
    vision_model: str,
    max_pages: int = 10,
    dpi: int = 150,
) -> str:
    """
    OCR через Qwen3-VL: PDF → PNG страницы → base64 → NITEC API.
    Параметры vision_model, max_pages, dpi берутся из EvaluatorConfig.
    """
```

### Новый файл: `pipeline/validator.py`

```python
def check_truncated_zip(file_content: bytes, filename: str) -> bool:
    """
    Проверяет не повреждён ли ZIP (docx = ZIP архив).
    Возвращает True если файл повреждён.
    """

def fix_broken_docx(path: str) -> bool:
    """
    Исправляет NULL image references в .rels файлах docx.
    Перезаписывает файл без NULL Relationship элементов.
    Возвращает True если были исправления.
    Перенесено из AI Evaluator api_evaluator.py.
    """

def build_empty_result(reason: str) -> dict:
    """
    Структурированный JSON результат с нулевыми оценками.
    Используется вместо status=failed для пустых/повреждённых документов.
    Документ получает status=done с is_valid=False.
    """

def is_text_sufficient(text: str, min_chars: int = 50) -> bool:
    """Проверяет достаточно ли текста для оценки."""
```

### Новый порядок в `pipeline/orchestrator.py`

```
run_pipeline(file_url, file_path, config: EvaluatorConfig)
    │
    ├── 1. download_file(url)
    │       └── + convert_google_docs_url()  ← НОВОЕ
    │
    ├── 2. Валидация файла                   ← НОВОЕ
    │       ├── check_truncated_zip()
    │       ├── convert_doc_to_docx() если .doc
    │       └── fix_broken_docx() если .docx
    │
    ├── 3. Извлечение текста                 ← НОВОЕ (без ApeRAG)
    │       ├── extract_text_with_python_docx()
    │       ├── fallback: PyMuPDF
    │       └── fallback: extract_text_via_vision_qwen()
    │
    ├── 4. Проверка текста                   ← НОВОЕ
    │       └── если пусто → build_empty_result() → выход
    │
    ├── 5. Определить язык → загрузить рубрику
    │
    └── 6. evaluate_with_llm(rubric, text, config)
```

### Новая зависимость

```
# requirements.txt — добавить:
python-docx>=1.1.0
```

### Переменные окружения — новые

```env
# Уже есть:
NITEC_VISION_MODEL=Qwen/Qwen3-VL-235B-A22B-Instruct
MAX_CONCURRENT_VISION=3

# Новые:
MIN_TEXT_CHARS=50          # минимум символов для валидного текста
VISION_MAX_PAGES=10        # максимум страниц для Vision OCR
VISION_DPI=150             # разрешение PNG для Vision OCR
```

---

## Фича 2 — Усиление extractor из AI Evaluator

### Что переносим

**2.1 Google Docs URL конвертация** → `pipeline/downloader.py`

```python
def convert_google_docs_url(url: str) -> str:
    """
    Конвертирует Google Docs sharing URL в export URL.
    https://docs.google.com/document/d/{id}/... 
        → https://docs.google.com/document/d/{id}/export?format=pdf
    Если не Google Docs — возвращает как есть.
    """
```

**2.2 Vision OCR per-page** → `pipeline/extractor.py`

Текущая реализация в Batch использует `DeepSeek-OCR` который возвращает bounding boxes, а не текст. Заменяем на логику из AI Evaluator:

```python
# Было (Batch — неправильно):
model='deepseek-ai/DeepSeek-OCR'  # возвращает bbox, не текст

# Станет (из AI Evaluator — правильно):
# PDF → fitz → PNG per page (dpi=150) → Qwen3-VL → text per page → join
model='Qwen/Qwen3-VL-235B-A22B-Instruct'
```

**2.3 fix_broken_docx()** → `pipeline/validator.py`

Перенести из `api_evaluator.py` (строки 660–716). Исправляет `Target="../NULL"` в `.rels` файлах docx.

**2.4 Truncated ZIP проверка** → `pipeline/validator.py`

```python
# Перенести из ai_evaluator.py строки 840–852
if filename.endswith('.docx') and file_content[:2] == b'PK':
    try:
        zipfile.ZipFile(io.BytesIO(file_content)).namelist()
    except zipfile.BadZipFile:
        return build_empty_result("файл повреждён или обрезан")
```

---

## Фича 3 — Усиление LLM парсинга из AI Evaluator

### Файл: `pipeline/llm.py`

Текущий `parse_llm_response()` в Batch уже хороший (обрабатывает `<think>` блоки, три уровня fallback). Добавляем только то чего не хватает:

**3.1 Разворачивание `raw_response` wrapper**

```python
def unwrap_raw_response(result: dict) -> dict:
    """
    Если LLM вернул {"raw_response": "..."} без full_report —
    пробует распарсить вложенный JSON из raw_response.
    Перенесено из api_evaluator.py строки 982–989.
    """
    if "raw_response" in result and "full_report" not in result:
        try:
            raw = result["raw_response"]
            raw = re.sub(r'^```json\s*', '', raw.strip())
            raw = re.sub(r'\s*```\s*$', '', raw).strip()
            return json.loads(raw)
        except Exception:
            pass
    return result
```

**3.2 `character_count` в `brief_report_json`**

```python
def add_character_count(result: dict) -> dict:
    """
    Считает суммарную длину текста в brief_report_json.
    Beles API ожидает это поле.
    Перенесено из api_evaluator.py строки 973–977.
    """
    if "brief_report_json" in result:
        brief = result["brief_report_json"]
        total = sum(len(s.get("recommendation", "")) for s in brief.get("sections", []))
        total += len(brief.get("overall_recommendation", ""))
        result["brief_report_json"]["character_count"] = total
    return result
```

**3.3 Применить оба в orchestrator**

```python
# В run_pipeline() после parse_llm_response():
parsed = unwrap_raw_response(parsed)
parsed = add_character_count(parsed)
```

---

## Фича 4 — EvaluatorConfig — мультиконфиг инстансы

### Новое Django приложение: `apps/evaluators/`

```
apps/evaluators/
├── __init__.py
├── models.py      ← EvaluatorConfig, Rubric, PromptTemplate
├── views.py       ← CRUD + дашборд
├── forms.py       ← EvaluatorConfigForm (вкладки)
├── admin.py
├── urls.py
├── serializers.py ← DRF
└── templates/
    ├── evaluators/
    │   ├── list.html        ← список всех конфигов
    │   ├── form.html        ← создать/редактировать (вкладки)
    │   └── dashboard.html   ← дашборд конкретного конфига
    └── ...
```

### Модель `EvaluatorConfig`

```python
class EvaluatorConfig(models.Model):

    # Основное
    name             # CharField(255)       — "Beles Production"
    slug             # SlugField(unique)    — "beles-prod" → /api/ev/beles-prod/evaluate/
    description      # TextField(blank)
    is_active        # BooleanField         — включён/выключен
    created_by       # FK(CustomUser)
    created_at       # DateTimeField
    updated_at       # DateTimeField

    # LLM настройки
    llm_model        # CharField            — выбор из NITEC_MODEL_CHOICES
    vision_model     # CharField            — выбор из NITEC_VISION_CHOICES
    whisper_model    # CharField(null)      — если нужна транскрипция аудио
    temperature      # FloatField(0.1)
    max_tokens       # IntegerField(4096)
    evaluation_slots # IntegerField(1)      — лимит evaluation_semaphore

    # Рубрика
    rubric           # FK(Rubric)
    language_mode    # CharField choices:
                     #   "auto"    — langdetect
                     #   "ru"      — всегда русский
                     #   "kk"      — всегда казахский

    # Pipeline — галочки
    enable_doc_fix          # BooleanField(True)  — fix_broken_docx
    enable_google_docs      # BooleanField(True)  — Google Docs URL конвертация
    enable_python_docx      # BooleanField(True)  — python-docx extraction
    enable_pymupdf_fallback # BooleanField(True)  — PyMuPDF fallback
    enable_vision_ocr       # BooleanField(True)  — Qwen3-VL Vision OCR
    enable_audio            # BooleanField(False) — Whisper транскрипция
    enable_validation       # BooleanField(True)  — is_valid / is_substantive
    min_text_chars          # IntegerField(50)
    vision_max_pages        # IntegerField(10)
    vision_dpi              # IntegerField(150)

    # Интеграция — куда отправлять результат
    DELIVERY_BELES   = "beles"
    DELIVERY_WEBHOOK = "webhook"
    DELIVERY_DB_ONLY = "db_only"
    delivery_type    # CharField choices

    # Beles
    beles_base_url        # URLField(null)
    beles_api_key         # CharField(null)   — зашифровано
    beles_endpoint_tpl    # CharField         — "/postcourse/materials/{id}/ai-analysis/"
    beles_http_method     # CharField         — "PATCH"

    # Webhook
    webhook_url      # URLField(null)

    # Retry
    enable_retry     # BooleanField(True)
    retry_attempts   # IntegerField(5)

    # Входящий API ключ
    api_key          # CharField            — X-API-Key для этого endpoint

    # Промпт
    prompt_template  # FK(PromptTemplate, null) — null = стандартный

    class Meta:
        verbose_name = "Конфигурация оценщика"
```

### Модель `Rubric`

```python
class Rubric(models.Model):
    name         # CharField(255)    — "Стандартная ПКС (5×5, 75б)"
    version      # CharField(20)     — "v1", "v2"
    file_ru      # FileField         — rubric_rus.md
    file_kk      # FileField         — rubric_kaz.md
    description  # TextField(blank)
    is_active    # BooleanField
    created_at   # DateTimeField

    def get_text(self, lang: str) -> str:
        """Возвращает текст рубрики по языку."""
```

### Модель `PromptTemplate`

```python
class PromptTemplate(models.Model):
    name         # CharField(255)    — "Стандартный", "Компактный"
    body         # TextField         — текст промпта с {rubric} и {student_work}
    is_default   # BooleanField
    created_at   # DateTimeField

    def render(self, rubric: str, student_work: str) -> str:
        """Подставляет рубрику и текст работы в шаблон."""
```

### Изменения в существующих моделях

```python
# apps/batch/models.py — добавить поле:
class EvaluationJob(models.Model):
    ...
    evaluator_config  # FK(EvaluatorConfig, null=True)
    # null=True для обратной совместимости со старыми Job без конфига

class Evaluation(models.Model):
    ...
    evaluator_config  # FK(EvaluatorConfig, null=True)
```

### Choices для LLM моделей

```python
# apps/evaluators/models.py

NITEC_LLM_CHOICES = [
    ("openai/gpt-oss-120b",                        "gpt-oss-120b (основная)"),
    ("deepseek-ai/DeepSeek-V3.2",                  "DeepSeek-V3.2 (рус/каз)"),
    ("moonshotai/Kimi-K2.5",                       "Kimi-K2.5 (резерв #1)"),
    ("meta-llama/Llama-4-Maverick-17B-128E-Instruct", "Llama-4-Maverick (резерв #2)"),
    ("astanahub/alemllm",                          "AlemLLM (казахстанская)"),
]

NITEC_VISION_CHOICES = [
    ("Qwen/Qwen3-VL-235B-A22B-Instruct",           "Qwen3-VL (рекомендуется)"),
    ("none",                                        "Отключить Vision OCR"),
]

NITEC_WHISPER_CHOICES = [
    ("openai/whisper-large-v3-turbo",              "Whisper turbo (быстрый)"),
    ("openai/whisper-large-v3",                    "Whisper large-v3"),
    ("none",                                        "Отключить"),
]
```

---

## Фича 5 — SystemSettings — глобальные лимиты

### Новая модель: `apps/evaluators/models.py`

```python
class SystemSettings(models.Model):
    """
    Singleton модель — одна запись на всю систему.
    Редактируется в Django Admin или через отдельную страницу настроек.
    """
    max_evaluation_slots   # IntegerField(8)   — общий лимит всех evaluation_semaphore
    max_llm_calls          # IntegerField(50)  — глобальный лимит LLM параллельности
    max_downloads          # IntegerField(100) — лимит одновременных скачиваний
    max_concurrent_vision  # IntegerField(3)   — лимит Vision OCR запросов

    class Meta:
        verbose_name = "Системные настройки"

    @classmethod
    def get(cls) -> "SystemSettings":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def slots_used(self) -> int:
        """Сумма evaluation_slots всех активных конфигов."""
        return EvaluatorConfig.objects.filter(is_active=True)\
            .aggregate(s=Sum('evaluation_slots'))['s'] or 0

    def slots_available(self) -> int:
        return self.max_evaluation_slots - self.slots_used()
```

### Валидация при сохранении конфига

```python
# apps/evaluators/models.py — EvaluatorConfig.clean()
def clean(self):
    settings = SystemSettings.get()
    used = settings.slots_used()
    
    # Вычесть слоты текущего конфига (при редактировании)
    if self.pk:
        current = EvaluatorConfig.objects.get(pk=self.pk)
        used -= current.evaluation_slots
    
    if used + self.evaluation_slots > settings.max_evaluation_slots:
        available = settings.max_evaluation_slots - used
        raise ValidationError({
            'evaluation_slots': (
                f"Доступно только {available} слотов из {settings.max_evaluation_slots}. "
                f"Уменьшите значение или увеличьте глобальный лимит в Системных настройках."
            )
        })
```

---

## Фича 6 — Django UI для управления конфигами

### URL структура

```python
# apps/evaluators/urls.py
urlpatterns = [
    path('evaluators/',                    views.EvaluatorListView.as_view(),    name='evaluator-list'),
    path('evaluators/create/',             views.EvaluatorCreateView.as_view(),  name='evaluator-create'),
    path('evaluators/<int:pk>/edit/',      views.EvaluatorUpdateView.as_view(),  name='evaluator-edit'),
    path('evaluators/<int:pk>/dashboard/', views.EvaluatorDashboardView.as_view(), name='evaluator-dashboard'),
    path('evaluators/<int:pk>/delete/',    views.EvaluatorDeleteView.as_view(),  name='evaluator-delete'),
    path('evaluators/<int:pk>/toggle/',    views.EvaluatorToggleView.as_view(),  name='evaluator-toggle'),
    path('system-settings/',               views.SystemSettingsView.as_view(),   name='system-settings'),

    # Рубрики
    path('rubrics/',                       views.RubricListView.as_view(),       name='rubric-list'),
    path('rubrics/upload/',                views.RubricUploadView.as_view(),     name='rubric-upload'),

    # Промпты
    path('prompt-templates/',              views.PromptTemplateListView.as_view(), name='prompt-list'),
    path('prompt-templates/create/',       views.PromptTemplateCreateView.as_view(), name='prompt-create'),
]
```

### Страница списка конфигов (`evaluators/list.html`)

```
┌─────────────────────────────────────────────────────────────────┐
│  AI Evaluator Configs                       [+ Новый конфиг]    │
│                                                                  │
│  Слоты: [████████░░░░░░░░░░] 6/8 занято  [⚙ Системные настройки]│
├──────────────┬───────────────────────┬──────────┬───────────────┤
│ Название     │ Endpoint              │ Модель   │ Слоты │ Статус │
├──────────────┼───────────────────────┼──────────┼───────┼───────┤
│ Beles Prod   │ /api/ev/beles/eval... │ gpt-oss  │  3    │ 🟢    │
│ ПКС Тест     │ /api/ev/pks/evaluat  │ DeepSeek │  2    │ 🟡    │
│ Аудио ПКС    │ /api/ev/audio/evalua │ gpt-oss  │  1    │ 🔴    │
└──────────────┴───────────────────────┴──────────┴───────┴───────┘
```

### Форма создания/редактирования — вкладки (`evaluators/form.html`)

```
[Основное] [LLM] [Рубрика] [Pipeline] [Интеграция] [Промпт]
```

**Вкладка Основное:**
```
Название          [                              ]
Slug              [beles-prod                    ]
                  → /api/ev/beles-prod/evaluate/
Описание          [                              ]
Активен           [☑]
```

**Вкладка LLM:**
```
Основная модель   [▼ gpt-oss-120b (основная)     ]
Vision модель     [▼ Qwen3-VL (рекомендуется)    ]
Whisper модель    [▼ Отключить                   ]

Temperature       [━━━●──────────────────────] 0.1
Max tokens        [━━━━━━━━━●─────────────────] 4096

Параллельность    [━━━●──────────────────────] 3
(evaluation_slots) Доступно: 2 из 8 свободных слотов
```

**Вкладка Рубрика:**
```
Рубрика           [▼ Стандартная ПКС (5×5, 75б) ]
                  [+ Загрузить новую рубрику     ]

Язык документа
  ● Определять автоматически (langdetect)
  ○ Всегда русский
  ○ Всегда казахский

[Предпросмотр рубрики ▼]
```

**Вкладка Pipeline:**
```
Шаги обработки документа:
  ☑ Исправление повреждённых .docx (fix_broken_docx)
  ☑ Конвертация Google Docs URL в export format
  ☑ Извлечение текста через python-docx (таблицы как markdown)
  ☑ Fallback: PyMuPDF если текст < MIN символов
  ☑ Fallback: Vision OCR (Qwen3-VL) если PyMuPDF пустой
  ☐ Транскрипция аудио (Whisper)
  ☑ Валидация документа перед оценкой (is_valid)

Мин. символов для валидного документа  [50    ]
Макс. страниц для Vision OCR           [10    ]
DPI для Vision OCR                     [150   ]
```

**Вкладка Интеграция:**
```
Тип доставки результата
  ● Beles API
  ○ Webhook (POST)
  ○ Только в БД (без отправки)

── Beles ─────────────────────────────────────
Base URL          [https://beles.orleu.edu.kz/api/v1]
API Key           [••••••••••••••••] [👁] [Тест ▶]
Endpoint шаблон   [/postcourse/materials/{id}/ai-analysis/]
HTTP метод        [▼ PATCH]

── Retry ─────────────────────────────────────
  ☑ Retry при ошибке
Попыток           [5]

── Входящий ключ ─────────────────────────────
API Key           [••••••••••••] [👁] [Сгенерировать 🔄]
```

**Вкладка Промпт:**
```
Шаблон            [▼ Стандартный (get_evaluation_prompt)]
                     Компактный
                     [ + Создать новый шаблон... ]

☑ Показывать редактор

┌────────────────────────────────────────────────────┐
│ Ты — эксперт по оценке учебных планов...           │
│ ## Рубрика                                         │
│ {rubric}                                           │
│ ## Текст плана урока                               │
│ {student_work}                                     │
│ Верни ТОЛЬКО валидный JSON...                      │
└────────────────────────────────────────────────────┘

[Сохранить как новый шаблон] [Сбросить до стандартного]
```

---

## Фича 7 — Динамические API endpoints per-config

### Файл: `api/evaluator_views.py` (новый)

```python
class ConfigEvaluateView(APIView):
    """
    Единый view для всех конфигов.
    URL: /api/ev/<slug>/evaluate/
    
    Аналог POST /evaluate из AI Evaluator FastAPI.
    Принимает {material_id, file_url}, возвращает "accepted",
    запускает process_file.delay() с привязкой к конфигу.
    """

class ConfigBatchUploadView(APIView):
    """
    URL: /api/ev/<slug>/batch/
    Загрузить CSV/Excel и запустить батч через конкретный конфиг.
    """

class ConfigHealthView(APIView):
    """URL: /api/ev/<slug>/health/"""

class ConfigStatsView(APIView):
    """
    URL: /api/ev/<slug>/stats/
    Возвращает статистику семафоров конфига (аналог /stats из AI Evaluator).
    """
```

### Файл: `api/urls.py` — дополнение

```python
urlpatterns += [
    # Per-config endpoints
    path('api/ev/<slug:slug>/evaluate/',  ConfigEvaluateView.as_view()),
    path('api/ev/<slug:slug>/batch/',     ConfigBatchUploadView.as_view()),
    path('api/ev/<slug:slug>/health/',    ConfigHealthView.as_view()),
    path('api/ev/<slug:slug>/stats/',     ConfigStatsView.as_view()),
]
```

### Аутентификация per-config

```python
class ConfigAPIKeyPermission(BasePermission):
    """
    Проверяет X-API-Key против EvaluatorConfig.api_key
    (не глобальный EVALUATOR_API_KEY).
    """
    def has_permission(self, request, view):
        slug = view.kwargs.get('slug')
        config = EvaluatorConfig.objects.get(slug=slug, is_active=True)
        return request.headers.get('X-API-Key') == config.api_key
```

### Передача конфига в pipeline

```python
# tasks/evaluate.py — process_file получает config_id
@celery_app.task(...)
def process_file(eval_id: int, config_id: int = None) -> None:
    config = EvaluatorConfig.objects.get(pk=config_id) if config_id else None
    ...
    result = asyncio.run(run_pipeline(file_url, file_path, config=config))
```

```python
# pipeline/orchestrator.py
async def run_pipeline(file_url, file_path, config: EvaluatorConfig = None):
    # Все параметры берутся из config:
    # config.llm_model, config.vision_model, config.min_text_chars,
    # config.enable_vision_ocr, config.enable_python_docx, ...
    # Если config=None — используются глобальные settings
```

---

## Фича 8 — Дашборд per-config

### Страница: `evaluators/dashboard.html`

```
┌─ Beles Production ────────────────── 🟢 Активен ──────────────┐
│  /api/ev/beles-prod/evaluate/          [⚙ Редактировать конфиг]│
│                                                                  │
│  ┌────────┬──────────┬────────┬─────────┬──────────────────┐   │
│  │ Всего  │ Успешно  │ Ошибки │ Retry   │ Среднее время    │   │
│  │  1247  │  1243    │   3    │   1     │    47 сек        │   │
│  └────────┴──────────┴────────┴─────────┴──────────────────┘   │
│                                                                  │
│  Токены сегодня                                                  │
│  Prompt:     2 400 000  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░    │
│  Completion:   890 000  ░░░░░░░░░░░                             │
│                                                                  │
│  Семафоры (сейчас)                                               │
│  Evaluation  [█████████████░░░░░░░░░] 2/3 — нагрузка 66%       │
│                                                                  │
│  Распределение уровней                                           │
│  Уровень 1  ████░░░░░░░░░░░░░░░░░░  18%                        │
│  Уровень 2  ████████░░░░░░░░░░░░░░  32%                        │
│  Уровень 3  ██████████████░░░░░░░░  38%                        │
│  Уровень 4  ████░░░░░░░░░░░░░░░░░░  12%                        │
│                                                                  │
│  Диагностика pipeline (за всё время)                             │
│  Vision OCR потребовался:    89 из 1247  (7%)                   │
│  fix_broken_docx сработал:   12 из 1247  (1%)                   │
│  Пустые документы:            4 из 1247  (0.3%)                 │
│                                                                  │
├──────────────────────────────────────────────────────────────────┤
│ ID   │ Статус │ Шаг │ Файл        │ Время │ Уровень │ Ошибка    │
│ 1247 │ ✅     │  8  │ plan.docx   │  43с  │  Ур.3   │           │
│ 1246 │ 🔄     │  6  │ urok.docx   │  31с  │  —      │           │
│ 1245 │ ❌     │  2  │ broken.docx │  —    │  —      │ BadZipFile│
└──────────────────────────────────────────────────────────────────┘
```

### Новые поля в модели `Evaluation` для диагностики

```python
# apps/batch/models.py — добавить:
used_vision_ocr    # BooleanField(default=False) — был ли Vision OCR
used_fix_docx      # BooleanField(default=False) — был ли fix_broken_docx
was_empty_doc      # BooleanField(default=False) — пустой документ
```

---

## Фича 9 — Перенос AI Evaluator в платформу

### Суть

Текущий FastAPI сервис (`api_evaluator.py` на порту 8081) полностью заменяется Django endpoint-ом через `EvaluatorConfig` с slug `beles-prod`.

### Что создаётся в интерфейсе при первом запуске

```
EvaluatorConfig:
  name            = "Beles Production"
  slug            = "beles-prod"
  llm_model       = "openai/gpt-oss-120b"
  temperature     = 0.1
  evaluation_slots = 3
  enable_vision_ocr = True
  enable_doc_fix   = True
  delivery_type   = "beles"
  beles_base_url  = "https://beles.orleu.edu.kz/api/v1"
  beles_endpoint_tpl = "/postcourse/materials/{id}/ai-analysis/"
  beles_http_method  = "PATCH"
  enable_retry    = True
  retry_attempts  = 5
```

### Новый endpoint заменяет FastAPI

```
Было:   POST https://evaluator.orleu.edu.kz/evaluate
Станет: POST https://evaluator.orleu.edu.kz/api/ev/beles-prod/evaluate/

# Payload тот же:
{
    "material_id": 362,
    "file_url": "https://cdn.orleu.edu.kz/..."
}

# Ответ тот же:
{
    "material_id": 362,
    "status": "accepted",
    "message": "File accepted for evaluation..."
}
```

### Nginx — обновить routing

```nginx
# Было: весь трафик → FastAPI :8081
location /evaluate {
    proxy_pass http://localhost:8081;
}

# Станет: весь трафик → Django :8502
location /api/ev/ {
    proxy_pass http://localhost:8502;
}

# Обратная совместимость (редирект старого URL):
location = /evaluate {
    return 301 /api/ev/beles-prod/evaluate/;
}
```

### Отключение FastAPI сервиса

```bash
systemctl stop orleu-evaluator
systemctl disable orleu-evaluator
# Docker контейнер orleu-evaluator тоже останавливается
```

---

## Затронутые файлы — сводная таблица

| Файл | Действие | Фича |
|------|----------|------|
| `pipeline/extractor.py` | Изменить: добавить python-docx, заменить Vision OCR на Qwen3-VL per-page | 1, 2 |
| `pipeline/downloader.py` | Изменить: добавить Google Docs URL конвертацию | 2 |
| `pipeline/orchestrator.py` | Изменить: новый порядок шагов, убрать ApeRAG, принимать config | 1, 7 |
| `pipeline/llm.py` | Изменить: добавить unwrap_raw_response, add_character_count | 3 |
| `pipeline/validator.py` | Создать: fix_broken_docx, check_truncated_zip, build_empty_result | 1, 2 |
| `apps/evaluators/` | Создать: новое приложение целиком | 4, 5, 6 |
| `apps/evaluators/models.py` | Создать: EvaluatorConfig, Rubric, PromptTemplate, SystemSettings | 4, 5 |
| `apps/evaluators/views.py` | Создать: CRUD views + дашборд | 6, 8 |
| `apps/evaluators/forms.py` | Создать: EvaluatorConfigForm с вкладками | 6 |
| `apps/evaluators/urls.py` | Создать | 6, 7 |
| `apps/batch/models.py` | Изменить: FK → EvaluatorConfig, новые bool поля диагностики | 4, 8 |
| `tasks/evaluate.py` | Изменить: принимать config_id, передавать в pipeline | 7 |
| `api/evaluator_views.py` | Создать: ConfigEvaluateView, ConfigBatchUploadView, stats, health | 7 |
| `api/urls.py` | Изменить: добавить /api/ev/<slug>/... маршруты | 7 |
| `config/urls.py` | Изменить: подключить apps/evaluators/urls.py | 6 |
| `config/settings.py` | Изменить: добавить apps.evaluators в INSTALLED_APPS | 4 |
| `requirements.txt` | Изменить: добавить python-docx>=1.1.0 | 1 |
| `nginx.conf` | Изменить: routing /api/ev/ + редирект /evaluate | 9 |

---

## Порядок реализации

### Этап 1 — Pipeline без ApeRAG (независимо, можно сразу)
1. `pipeline/validator.py` — создать (`fix_broken_docx`, `check_truncated_zip`, `build_empty_result`)
2. `pipeline/extractor.py` — заменить Vision OCR + добавить python-docx
3. `pipeline/downloader.py` — добавить Google Docs
4. `pipeline/llm.py` — добавить `unwrap_raw_response`, `add_character_count`
5. `pipeline/orchestrator.py` — новый порядок шагов без ApeRAG
6. Тест на реальных файлах

### Этап 2 — Модели мультиконфига
1. `apps/evaluators/models.py` — `EvaluatorConfig`, `Rubric`, `PromptTemplate`, `SystemSettings`
2. Миграции
3. `apps/batch/models.py` — добавить FK и diagnostic поля
4. Миграции

### Этап 3 — Django UI
1. `apps/evaluators/forms.py` — форма с вкладками
2. `apps/evaluators/views.py` — CRUD
3. Шаблоны
4. `apps/evaluators/urls.py` + подключить в `config/urls.py`

### Этап 4 — API endpoints
1. `api/evaluator_views.py`
2. `api/urls.py`
3. `tasks/evaluate.py` — принимать config_id

### Этап 5 — Перенос AI Evaluator
1. Создать конфиг "Beles Production" через UI
2. Тест нового endpoint
3. Обновить Nginx
4. Остановить FastAPI сервис
