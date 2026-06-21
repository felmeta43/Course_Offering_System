from django.contrib import admin

from .models import InstructorPreference, PreferenceWindow


@admin.register(PreferenceWindow)
class PreferenceWindowAdmin(admin.ModelAdmin):
    list_display = ("department", "academic_term", "opens_at", "deadline", "closed_manually", "is_open")
    list_filter = ("department", "academic_term")


@admin.register(InstructorPreference)
class InstructorPreferenceAdmin(admin.ModelAdmin):
    list_display = ("instructor", "academic_term", "course", "rank")
    list_filter = ("academic_term", "course__department")
