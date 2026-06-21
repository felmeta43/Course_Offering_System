from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", RedirectView.as_view(pattern_name="dashboard", permanent=False)),
    path("", include("accounts.urls")),
    path("curriculum/", include("curriculum.urls")),
    path("preferences/", include("preferences.urls")),
    path("assignments/", include("assignments.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
