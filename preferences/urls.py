from django.urls import path

from . import views

app_name = "preferences"

urlpatterns = [
    path("deadlines/", views.manage_deadlines, name="manage_deadlines"),
    path("submit/", views.submit_preferences, name="submit_preferences"),
]
