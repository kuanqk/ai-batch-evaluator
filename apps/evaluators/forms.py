"""Forms for evaluator configs, system settings, rubrics, prompts."""

from __future__ import annotations

from django import forms

from apps.evaluators.models import EvaluatorConfig, PromptTemplate, Rubric, SystemSettings


def _bootstrap_field_classes(form: forms.ModelForm) -> None:
    for _name, field in form.fields.items():
        w = field.widget
        if isinstance(w, (forms.CheckboxInput, forms.CheckboxSelectMultiple)):
            w.attrs.setdefault("class", "form-check-input")
        elif isinstance(w, forms.Select):
            w.attrs.setdefault("class", "form-select")
        else:
            w.attrs.setdefault("class", "form-control")


class SystemSettingsForm(forms.ModelForm):
    class Meta:
        model = SystemSettings
        fields = ("max_evaluation_slots", "max_llm_calls", "max_downloads", "max_concurrent_vision")

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        _bootstrap_field_classes(self)


class RubricForm(forms.ModelForm):
    class Meta:
        model = Rubric
        fields = ("name", "version", "description", "is_active", "file_ru", "file_kk")
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        _bootstrap_field_classes(self)


class PromptTemplateForm(forms.ModelForm):
    class Meta:
        model = PromptTemplate
        fields = ("name", "body", "is_default")
        widgets = {
            "body": forms.Textarea(attrs={"rows": 18, "class": "form-control font-monospace small"}),
        }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        _bootstrap_field_classes(self)


class EvaluatorConfigForm(forms.ModelForm):
    class Meta:
        model = EvaluatorConfig
        exclude = ("created_at", "updated_at", "created_by")
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "beles_api_key": forms.TextInput(attrs={"autocomplete": "off"}),
            "api_key": forms.TextInput(attrs={"autocomplete": "off"}),
            "temperature": forms.NumberInput(attrs={"step": "0.05", "min": "0", "max": "2"}),
        }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        _bootstrap_field_classes(self)
        self.fields["slug"].help_text = "Используется в URL вида /api/ev/<slug>/…"
        self.fields["evaluation_slots"].help_text = "Лимит параллельных оценок для этого конфига (сумма по активным не выше системного лимита)."
