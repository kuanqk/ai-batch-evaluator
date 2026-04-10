"""Evaluator multi-config: rubrics, prompts, system-wide limits."""

from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Sum

NITEC_LLM_CHOICES = [
    ("openai/gpt-oss-120b", "gpt-oss-120b (основная)"),
    ("deepseek-ai/DeepSeek-V3.2", "DeepSeek-V3.2 (рус/каз)"),
    ("moonshotai/Kimi-K2.5", "Kimi-K2.5 (резерв #1)"),
    ("meta-llama/Llama-4-Maverick-17B-128E-Instruct", "Llama-4-Maverick (резерв #2)"),
    ("astanahub/alemllm", "AlemLLM (казахстанская)"),
]

NITEC_VISION_CHOICES = [
    ("Qwen/Qwen3-VL-235B-A22B-Instruct", "Qwen3-VL (рекомендуется)"),
    ("none", "Отключить Vision OCR"),
]

NITEC_WHISPER_CHOICES = [
    ("openai/whisper-large-v3-turbo", "Whisper turbo (быстрый)"),
    ("openai/whisper-large-v3", "Whisper large-v3"),
    ("none", "Отключить"),
]

LANGUAGE_MODE_CHOICES = [
    ("auto", "Определять автоматически (langdetect)"),
    ("ru", "Всегда русский"),
    ("kk", "Всегда казахский"),
]


class Rubric(models.Model):
    name = models.CharField(max_length=255)
    version = models.CharField(max_length=20, default="v1")
    file_ru = models.FileField(upload_to="rubrics/", blank=True)
    file_kk = models.FileField(upload_to="rubrics/", blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Рубрика"
        verbose_name_plural = "Рубрики"

    def __str__(self) -> str:
        return f"{self.name} ({self.version})"

    def get_text(self, lang: str) -> str:
        """Return rubric file contents for language code (ru / kk)."""
        lang = (lang or "ru").lower()
        field = self.file_kk if lang.startswith("kk") else self.file_ru
        if not field:
            return ""
        try:
            with field.open("r", encoding="utf-8") as fh:
                return fh.read()
        except OSError:
            return ""


class PromptTemplate(models.Model):
    name = models.CharField(max_length=255)
    body = models.TextField(help_text="Плейсхолдеры: {rubric}, {student_work}")
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Шаблон промпта"
        verbose_name_plural = "Шаблоны промптов"

    def __str__(self) -> str:
        return self.name

    def render(self, rubric: str, student_work: str) -> str:
        return self.body.replace("{rubric}", rubric).replace("{student_work}", student_work)


class SystemSettings(models.Model):
    """
    Singleton (pk=1): global concurrency caps vs sum of per-config evaluation_slots.
    """

    max_evaluation_slots = models.PositiveIntegerField(default=8)
    max_llm_calls = models.PositiveIntegerField(default=50)
    max_downloads = models.PositiveIntegerField(default=100)
    max_concurrent_vision = models.PositiveIntegerField(default=3)

    class Meta:
        verbose_name = "Системные настройки"
        verbose_name_plural = "Системные настройки"

    def __str__(self) -> str:
        return "Системные настройки"

    def save(self, *args, **kwargs) -> None:
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get(cls) -> SystemSettings:
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def slots_used(self) -> int:
        s = (
            EvaluatorConfig.objects.filter(is_active=True).aggregate(s=Sum("evaluation_slots"))["s"]
            or 0
        )
        return int(s)

    def slots_available(self) -> int:
        return max(0, int(self.max_evaluation_slots) - self.slots_used())


class EvaluatorConfig(models.Model):
    DELIVERY_BELES = "beles"
    DELIVERY_WEBHOOK = "webhook"
    DELIVERY_DB_ONLY = "db_only"
    DELIVERY_CHOICES = [
        (DELIVERY_BELES, "Beles API"),
        (DELIVERY_WEBHOOK, "Webhook (POST)"),
        (DELIVERY_DB_ONLY, "Только БД"),
    ]

    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=80, unique=True, db_index=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="evaluator_configs",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    llm_model = models.CharField(max_length=120, choices=NITEC_LLM_CHOICES, default=NITEC_LLM_CHOICES[0][0])
    vision_model = models.CharField(
        max_length=120, choices=NITEC_VISION_CHOICES, default=NITEC_VISION_CHOICES[0][0]
    )
    whisper_model = models.CharField(
        max_length=80,
        choices=NITEC_WHISPER_CHOICES,
        default="none",
        blank=True,
    )
    temperature = models.FloatField(default=0.1)
    max_tokens = models.PositiveIntegerField(default=4096)
    evaluation_slots = models.PositiveIntegerField(default=1)

    rubric = models.ForeignKey(
        Rubric,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="evaluator_configs",
    )
    language_mode = models.CharField(
        max_length=10,
        choices=LANGUAGE_MODE_CHOICES,
        default="auto",
    )

    enable_doc_fix = models.BooleanField(default=True)
    enable_google_docs = models.BooleanField(default=True)
    enable_python_docx = models.BooleanField(default=True)
    enable_pymupdf_fallback = models.BooleanField(default=True)
    enable_vision_ocr = models.BooleanField(default=True)
    enable_audio = models.BooleanField(default=False)
    enable_validation = models.BooleanField(default=True)
    min_text_chars = models.PositiveIntegerField(default=50)
    vision_max_pages = models.PositiveIntegerField(default=10)
    vision_dpi = models.PositiveIntegerField(default=150)

    delivery_type = models.CharField(
        max_length=20,
        choices=DELIVERY_CHOICES,
        default=DELIVERY_DB_ONLY,
    )
    beles_base_url = models.URLField(blank=True)
    beles_api_key = models.CharField(max_length=512, blank=True)
    beles_endpoint_tpl = models.CharField(
        max_length=500,
        default="/postcourse/materials/{id}/ai-analysis/",
        blank=True,
    )
    beles_http_method = models.CharField(max_length=10, default="PATCH")

    webhook_url = models.URLField(blank=True)

    enable_retry = models.BooleanField(default=True)
    retry_attempts = models.PositiveIntegerField(default=5)

    api_key = models.CharField(max_length=255, blank=True, help_text="X-API-Key для /api/ev/<slug>/…")

    prompt_template = models.ForeignKey(
        PromptTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="evaluator_configs",
    )

    class Meta:
        ordering = ["slug"]
        verbose_name = "Конфигурация оценщика"
        verbose_name_plural = "Конфигурации оценщиков"

    def __str__(self) -> str:
        return f"{self.name} ({self.slug})"

    def clean(self) -> None:
        sys = SystemSettings.get()
        used = 0
        qs = EvaluatorConfig.objects.filter(is_active=True)
        if self.pk:
            qs = qs.exclude(pk=self.pk)
        agg = qs.aggregate(s=Sum("evaluation_slots"))["s"]
        used = int(agg or 0)
        if self.is_active:
            if used + int(self.evaluation_slots) > int(sys.max_evaluation_slots):
                avail = max(0, int(sys.max_evaluation_slots) - used)
                raise ValidationError(
                    {
                        "evaluation_slots": (
                            f"Доступно только {avail} слотов из {sys.max_evaluation_slots}. "
                            "Уменьшите значение или увеличьте лимит в системных настройках."
                        )
                    }
                )
