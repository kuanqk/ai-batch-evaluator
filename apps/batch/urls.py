from django.urls import path

from . import views

app_name = "batch"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("upload/", views.upload, name="upload"),
    path("results/", views.results, name="results"),
    path("results/export/", views.export_excel, name="export"),
]
