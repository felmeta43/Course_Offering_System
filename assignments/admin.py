from django.contrib import admin

from .models import Assignment, AssignmentRun, CourseExperience


@admin.register(CourseExperience)
class CourseExperienceAdmin(admin.ModelAdmin):
    list_display = ("instructor", "course", "times_taught", "last_taught_term")
    list_filter = ("course__department",)


@admin.register(AssignmentRun)
class AssignmentRunAdmin(admin.ModelAdmin):
    list_display = ("department", "academic_term", "run_by", "run_at", "status")
    list_filter = ("department", "academic_term", "status")
    readonly_fields = ("department", "academic_term", "run_by", "run_at", "status", "log")


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ("section", "instructor", "load", "method", "created_at")
    list_filter = ("method", "section__academic_term", "section__course__department")
    search_fields = ("instructor__username", "section__course__code")
