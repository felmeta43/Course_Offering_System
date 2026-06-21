from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = (
        "username", "first_name", "last_name", "role", "department",
        "academic_rank", "overall_experience_years", "experience_auto_calculated",
        "is_active",
    )
    list_filter = ("role", "department", "academic_rank", "experience_auto_calculated")
    fieldsets = UserAdmin.fieldsets + (
        ("Course Offering System", {
            "fields": (
                "role", "department", "academic_rank",
                "overall_experience_years", "experience_auto_calculated",
            )
        }),
    )
