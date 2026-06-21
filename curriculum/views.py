from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse

from accounts.decorators import admin_required, dept_head_or_admin_required
from institutions.models import AcademicTerm, Institution

from . import excel_io
from .forms import ExcelUploadForm
from .models import Course, Section, StudentGroup
from .services import generate_sections_for_term


@login_required
def course_list(request):
    courses = Course.objects.select_related("department").prefetch_related("target_departments")
    if request.user.role == request.user.Role.INSTRUCTOR and request.user.department:
        courses = courses.filter(department=request.user.department)
    return render(request, "curriculum/course_list.html", {"courses": courses})


@admin_required
def course_import_template(request):
    return excel_io.course_import_template_response()


@admin_required
def student_group_import_template(request):
    return excel_io.student_group_import_template_response()


@admin_required
def import_courses(request):
    if request.method == "POST":
        form = ExcelUploadForm(request.POST, request.FILES)
        if form.is_valid():
            created, updated, errors = excel_io.import_courses_from_workbook(
                request.FILES["workbook"]
            )
            messages.success(request, f"Imported courses: {created} created, {updated} updated.")
            for err in errors:
                messages.warning(request, err)
            return redirect("curriculum:course_list")
    else:
        form = ExcelUploadForm()
    return render(request, "curriculum/import_form.html", {
        "form": form,
        "title": "Import Courses from Excel",
        "template_url": reverse("curriculum:course_import_template"),
    })


@admin_required
def import_student_groups(request):
    institution = Institution.get_solo()
    if request.method == "POST":
        form = ExcelUploadForm(request.POST, request.FILES)
        if form.is_valid():
            created, updated, errors = excel_io.import_student_groups_from_workbook(
                request.FILES["workbook"], institution
            )
            messages.success(request, f"Imported student groups: {created} created, {updated} updated.")
            for err in errors:
                messages.warning(request, err)
            return redirect("curriculum:student_group_list")
    else:
        form = ExcelUploadForm()
    return render(request, "curriculum/import_form.html", {
        "form": form,
        "title": "Import Student Groups from Excel",
        "template_url": reverse("curriculum:student_group_import_template"),
    })


@login_required
def student_group_list(request):
    groups = StudentGroup.objects.select_related("department", "academic_term")
    return render(request, "curriculum/student_group_list.html", {"groups": groups})


@dept_head_or_admin_required
def generate_sections(request):
    if request.method == "POST":
        term_id = request.POST.get("academic_term")
        term = AcademicTerm.objects.filter(id=term_id).first()
        if term:
            created = generate_sections_for_term(term)
            messages.success(request, f"Generated {len(created)} new section(s) for {term}.")
        else:
            messages.error(request, "Please choose a valid academic term.")
        return redirect("curriculum:section_list")
    terms = AcademicTerm.objects.all()
    return render(request, "curriculum/generate_sections.html", {"terms": terms})


@login_required
def section_list(request):
    sections = Section.objects.select_related("course", "student_group", "academic_term", "assignment__instructor")
    if request.user.role == request.user.Role.DEPT_HEAD and request.user.department:
        sections = sections.filter(course__department=request.user.department)
    term_id = request.GET.get("term")
    if term_id:
        sections = sections.filter(academic_term_id=term_id)
    return render(request, "curriculum/section_list.html", {
        "sections": sections,
        "terms": AcademicTerm.objects.all(),
    })
