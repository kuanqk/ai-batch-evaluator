from django.conf import settings
from django.db import models


class EvaluationJob(models.Model):
    STATUS_PENDING = "pending"
    STATUS_RUNNING = "running"
    STATUS_DONE = "done"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Ожидает"),
        (STATUS_RUNNING, "В работе"),
        (STATUS_DONE, "Завершён"),
        (STATUS_FAILED, "Ошибка"),
    ]

    name = models.CharField(max_length=255)
    source_file = models.CharField(max_length=255)
    total = models.IntegerField(default=0)
    processed = models.IntegerField(default=0)
    failed = models.IntegerField(default=0)
    paused = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    webhook_url = models.URLField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="evaluation_jobs",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Батч-задание"
        verbose_name_plural = "Батч-задания"
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["-created_at"]),
        ]

    def __str__(self) -> str:
        return f"Job #{self.pk} — {self.name} ({self.status})"

    @property
    def progress_percent(self) -> float:
        if not self.total:
            return 0.0
        return round((self.processed + self.failed) / self.total * 100, 1)


class Evaluation(models.Model):
    STATUS_PENDING = "pending"
    STATUS_PROCESSING = "processing"
    STATUS_DONE = "done"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Ожидает"),
        (STATUS_PROCESSING, "Обрабатывается"),
        (STATUS_DONE, "Готово"),
        (STATUS_FAILED, "Ошибка"),
    ]

    job = models.ForeignKey(
        EvaluationJob,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="evaluations",
    )
    material_id = models.IntegerField(null=True, blank=True, db_index=True)
    file_path = models.TextField(null=True, blank=True)
    file_url = models.TextField()
    city = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    trainer = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    group_name = models.CharField(max_length=255, null=True, blank=True)
    file_name = models.CharField(max_length=255, null=True, blank=True)
    teacher_name = models.TextField(null=True, blank=True)
    topic = models.TextField(null=True, blank=True)
    scores = models.JSONField(null=True, blank=True)
    total_score = models.FloatField(null=True, blank=True)
    score_percentage = models.FloatField(null=True, blank=True)
    score_level = models.IntegerField(null=True, blank=True, db_index=True)
    feedback = models.TextField(null=True, blank=True)
    llm_result = models.JSONField(null=True, blank=True)
    report_path = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    current_step = models.IntegerField(default=0)
    error = models.TextField(null=True, blank=True)
    extraction_method = models.CharField(max_length=50, null=True, blank=True)
    doc_lang = models.CharField(max_length=10, null=True, blank=True)
    file_size_bytes = models.BigIntegerField(null=True, blank=True)
    doc_chars = models.IntegerField(null=True, blank=True)
    prompt_tokens = models.IntegerField(default=0)
    completion_tokens = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Оценка"
        verbose_name_plural = "Оценки"
        indexes = [
            models.Index(fields=["job", "status"]),
            models.Index(fields=["-created_at"]),
        ]

    def __str__(self) -> str:
        return f"Eval #{self.pk} — {self.file_name or self.file_url[:60]} ({self.status})"
