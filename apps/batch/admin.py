from django.contrib import admin

from .models import Evaluation, EvaluationJob


@admin.register(EvaluationJob)
class EvaluationJobAdmin(admin.ModelAdmin):
    list_display = (
        "id", "name", "status", "evaluator_config", "total", "processed", "failed", "paused", "created_at",
    )
    list_filter = ("status", "paused")
    search_fields = ("name",)
    readonly_fields = ("created_at", "updated_at")
    raw_id_fields = ("evaluator_config",)
    actions = ["mark_paused", "mark_resumed"]

    @admin.action(description="Поставить на паузу")
    def mark_paused(self, request, queryset):
        queryset.update(paused=True)

    @admin.action(description="Снять с паузы")
    def mark_resumed(self, request, queryset):
        queryset.update(paused=False)


@admin.register(Evaluation)
class EvaluationAdmin(admin.ModelAdmin):
    list_display = (
        "id", "job_id", "evaluator_config", "city", "trainer", "status",
        "score_level", "score_percentage", "created_at",
    )
    list_filter = ("status", "score_level", "doc_lang")
    search_fields = ("city", "trainer", "file_name", "teacher_name")
    readonly_fields = ("created_at", "updated_at", "started_at", "processed_at")
    raw_id_fields = ("evaluator_config",)
