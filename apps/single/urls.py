from django.urls import path

from . import views

app_name = "single"

urlpatterns = [
    path("", views.submit, name="submit"),
    path("<int:eval_id>/", views.result, name="result"),
]
