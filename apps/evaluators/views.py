"""Staff UI: evaluator configs, system settings, rubrics, prompt templates."""

from __future__ import annotations

import statistics
from typing import Any

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import ValidationError
from django.db.models import Avg, Count
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, DeleteView, FormView, ListView, TemplateView, UpdateView

from apps.batch.models import Evaluation
from apps.evaluators.forms import (
    EvaluatorConfigForm,
    PromptTemplateForm,
    RubricForm,
    SystemSettingsForm,
)
from apps.evaluators.models import EvaluatorConfig, PromptTemplate, Rubric, SystemSettings


class StaffRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    login_url = reverse_lazy("accounts:login")

    def test_func(self) -> bool:
        return self.request.user.is_staff


class SystemSettingsView(StaffRequiredMixin, FormView):
    template_name = "evaluators/system_settings.html"
    form_class = SystemSettingsForm
    success_url = reverse_lazy("evaluators:system-settings")

    def get_form_kwargs(self) -> dict[str, Any]:
        kw = super().get_form_kwargs()
        kw["instance"] = SystemSettings.get()
        return kw

    def form_valid(self, form):
        form.save()
        messages.success(self.request, "Системные настройки сохранены.")
        return super().form_valid(form)


class EvaluatorListView(StaffRequiredMixin, ListView):
    model = EvaluatorConfig
    template_name = "evaluators/list.html"
    context_object_name = "configs"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        sys = SystemSettings.get()
        used = sys.slots_used()
        mx = max(int(sys.max_evaluation_slots), 1)
        ctx["system_settings"] = sys
        ctx["slots_used"] = used
        ctx["slots_max"] = sys.max_evaluation_slots
        ctx["slots_pct"] = min(100, int(100 * used / mx))
        return ctx


class EvaluatorCreateView(StaffRequiredMixin, CreateView):
    model = EvaluatorConfig
    form_class = EvaluatorConfigForm
    template_name = "evaluators/form.html"
    success_url = reverse_lazy("evaluators:list")

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, "Конфигурация создана.")
        return super().form_valid(form)


class EvaluatorUpdateView(StaffRequiredMixin, UpdateView):
    model = EvaluatorConfig
    form_class = EvaluatorConfigForm
    template_name = "evaluators/form.html"
    success_url = reverse_lazy("evaluators:list")

    def form_valid(self, form):
        messages.success(self.request, "Конфигурация сохранена.")
        return super().form_valid(form)


class EvaluatorDeleteView(StaffRequiredMixin, DeleteView):
    model = EvaluatorConfig
    template_name = "evaluators/evaluator_confirm_delete.html"
    success_url = reverse_lazy("evaluators:list")

    def delete(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        messages.success(request, "Конфигурация удалена.")
        return super().delete(request, *args, **kwargs)


class EvaluatorToggleView(StaffRequiredMixin, View):
    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        cfg = get_object_or_404(EvaluatorConfig, pk=pk)
        cfg.is_active = not cfg.is_active
        try:
            cfg.full_clean()
            cfg.save()
        except ValidationError as e:
            messages.error(request, " ".join(e.messages))
            return redirect("evaluators:list")
        messages.success(
            request,
            f"Конфиг «{cfg.name}» {'включён' if cfg.is_active else 'выключен'}.",
        )
        return redirect("evaluators:list")


class EvaluatorDashboardView(StaffRequiredMixin, TemplateView):
    template_name = "evaluators/dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        pk = self.kwargs["pk"]
        cfg = get_object_or_404(EvaluatorConfig.objects.select_related("rubric", "prompt_template"), pk=pk)
        ctx["config"] = cfg

        evs = Evaluation.objects.filter(evaluator_config_id=pk)
        total = evs.count()
        ctx["total"] = total
        ctx["done"] = evs.filter(status=Evaluation.STATUS_DONE).count()
        ctx["failed"] = evs.filter(status=Evaluation.STATUS_FAILED).count()
        ctx["processing"] = evs.filter(status=Evaluation.STATUS_PROCESSING).count()
        ctx["pending"] = evs.filter(status=Evaluation.STATUS_PENDING).count()

        done_qs = evs.filter(status=Evaluation.STATUS_DONE)
        level_rows = (
            done_qs.exclude(score_level__isnull=True)
            .values("score_level")
            .annotate(c=Count("id"))
            .order_by("score_level")
        )
        level_map = {row["score_level"]: row["c"] for row in level_rows}
        ctx["level_counts"] = level_map
        done_cnt = max(done_qs.count(), 1)
        ctx["level_bars"] = [
            {
                "level": lv,
                "count": level_map.get(lv, 0),
                "pct": round(100 * level_map.get(lv, 0) / done_cnt, 1),
            }
            for lv in (1, 2, 3, 4)
        ]

        tok = evs.aggregate(
            pt=Avg("prompt_tokens"),
            ct=Avg("completion_tokens"),
        )
        ctx["avg_prompt_tokens"] = int(tok["pt"] or 0)
        ctx["avg_completion_tokens"] = int(tok["ct"] or 0)

        durations = []
        for e in done_qs.filter(started_at__isnull=False, processed_at__isnull=False)[:500]:
            durations.append((e.processed_at - e.started_at).total_seconds())
        ctx["avg_seconds"] = round(statistics.mean(durations), 1) if durations else None

        ctx["vision_count"] = evs.filter(used_vision_ocr=True).count()
        ctx["fix_docx_count"] = evs.filter(used_fix_docx=True).count()
        ctx["empty_doc_count"] = evs.filter(was_empty_doc=True).count()

        ctx["recent"] = evs.order_by("-created_at")[:30]
        return ctx


class RubricListView(StaffRequiredMixin, ListView):
    model = Rubric
    template_name = "evaluators/rubric_list.html"
    context_object_name = "rubrics"


class RubricCreateView(StaffRequiredMixin, CreateView):
    model = Rubric
    form_class = RubricForm
    template_name = "evaluators/rubric_form.html"
    success_url = reverse_lazy("evaluators:rubric-list")

    def form_valid(self, form):
        messages.success(self.request, "Рубрика добавлена.")
        return super().form_valid(form)


class PromptTemplateListView(StaffRequiredMixin, ListView):
    model = PromptTemplate
    template_name = "evaluators/prompt_list.html"
    context_object_name = "templates"


class PromptTemplateCreateView(StaffRequiredMixin, CreateView):
    model = PromptTemplate
    form_class = PromptTemplateForm
    template_name = "evaluators/prompt_form.html"
    success_url = reverse_lazy("evaluators:prompt-list")

    def form_valid(self, form):
        messages.success(self.request, "Шаблон промпта создан.")
        return super().form_valid(form)
