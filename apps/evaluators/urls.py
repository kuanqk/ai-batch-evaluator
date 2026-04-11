from django.urls import path

from apps.evaluators import views

app_name = "evaluators"

urlpatterns = [
    path("", views.EvaluatorListView.as_view(), name="list"),
    path("create/", views.EvaluatorCreateView.as_view(), name="create"),
    path("<int:pk>/edit/", views.EvaluatorUpdateView.as_view(), name="edit"),
    path("<int:pk>/dashboard/", views.EvaluatorDashboardView.as_view(), name="dashboard"),
    path("<int:pk>/delete/", views.EvaluatorDeleteView.as_view(), name="delete"),
    path("<int:pk>/toggle/", views.EvaluatorToggleView.as_view(), name="toggle"),
    path("system-settings/", views.SystemSettingsView.as_view(), name="system-settings"),
    path("rubrics/", views.RubricListView.as_view(), name="rubric-list"),
    path("rubrics/upload/", views.RubricCreateView.as_view(), name="rubric-upload"),
    path("prompt-templates/", views.PromptTemplateListView.as_view(), name="prompt-list"),
    path("prompt-templates/create/", views.PromptTemplateCreateView.as_view(), name="prompt-create"),
]
