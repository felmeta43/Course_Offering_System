from django.urls import path

from . import views

app_name = "assignments"

urlpatterns = [
    path("run/", views.run_assignment, name="run_assignment"),
    path("results/", views.results, name="results"),
    path("my-assignments/", views.my_assignments, name="my_assignments"),
]
