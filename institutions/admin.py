from django.contrib import admin

from .models import AcademicTerm, Department, Institution


@admin.register(Institution)
class InstitutionAdmin(admin.ModelAdmin):
    list_display = ("name", "short_name", "max_major_courses_per_instructor", "large_section_threshold")

    def has_add_permission(self, request):
        return not Institution.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "head", "institution")
    search_fields = ("code", "name")


@admin.register(AcademicTerm)
class AcademicTermAdmin(admin.ModelAdmin):
    list_display = ("academic_year", "semester", "institution", "is_current", "start_date", "end_date")
    list_filter = ("institution", "is_current")
