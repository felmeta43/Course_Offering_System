from django.contrib import admin

from .models import Course, Section, StudentGroup


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = (
        "code", "title", "department", "course_type", "year_level", "semester",
        "credit_hours", "lecture_hours", "tutorial_hours", "lab_hours",
    )
    list_filter = ("department", "course_type", "year_level", "semester")
    search_fields = ("code", "title")
    filter_horizontal = ("target_departments", "prerequisites")


@admin.register(StudentGroup)
class StudentGroupAdmin(admin.ModelAdmin):
    list_display = (
        "department", "academic_term", "year_level", "section",
        "number_of_students", "is_extension",
    )
    list_filter = ("department", "academic_term", "is_extension", "year_level")


@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = ("course", "student_group", "academic_term", "load_display")
    list_filter = ("academic_term", "course__department")
    search_fields = ("course__code",)

    @admin.display(description="Load")
    def load_display(self, obj):
        return obj.compute_load()
