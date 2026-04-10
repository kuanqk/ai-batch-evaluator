from django.contrib import admin

from apps.evaluators.models import EvaluatorConfig, PromptTemplate, Rubric, SystemSettings


@admin.register(Rubric)
class RubricAdmin(admin.ModelAdmin):
    list_display = ("name", "version", "is_active", "created_at")
    list_filter = ("is_active",)


@admin.register(PromptTemplate)
class PromptTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "is_default", "created_at")


@admin.register(SystemSettings)
class SystemSettingsAdmin(admin.ModelAdmin):
    list_display = (
        "max_evaluation_slots",
        "max_llm_calls",
        "max_downloads",
        "max_concurrent_vision",
    )

    def has_add_permission(self, request) -> bool:
        return not SystemSettings.objects.exists()


@admin.register(EvaluatorConfig)
class EvaluatorConfigAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "llm_model", "evaluation_slots", "delivery_type")
    list_filter = ("is_active", "delivery_type")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name", "slug")
    raw_id_fields = ("created_by", "rubric", "prompt_template")
