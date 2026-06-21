from django.urls import path

from . import views

app_name = "curriculum"

urlpatterns = [
    path("courses/", views.course_list, name="course_list"),
    path("courses/import/", views.import_courses, name="import_courses"),
    path("courses/template/", views.course_import_template, name="course_import_template"),
    path("student-groups/", views.student_group_list, name="student_group_list"),
    path("student-groups/import/", views.import_student_groups, name="import_student_groups"),
    path("student-groups/template/", views.student_group_import_template, name="student_group_import_template"),
    path("sections/", views.section_list, name="section_list"),
    path("sections/generate/", views.generate_sections, name="generate_sections"),
]
