from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path("", RedirectView.as_view(url="/batch/", permanent=False)),
    path("admin/", admin.site.urls),
    path("accounts/", include("apps.accounts.urls")),
    path("batch/", include("apps.batch.urls")),
    path("evaluators/", include("apps.evaluators.urls")),
    path("api/", include("apps.batch.api_urls")),
    path("single/", include("apps.single.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
