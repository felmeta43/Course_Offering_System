from collections import defaultdict
from decimal import Decimal

from django.contrib import messages
from django.shortcuts import redirect, render

from accounts.decorators import dept_head_required, instructor_required
from institutions.models import AcademicTerm

from .models import Assignment
from .services import AssignmentError, run_auto_assignment


@dept_head_required
def run_assignment(request):
    department = request.user.department
    current_term = AcademicTerm.objects.filter(is_current=True).first()

    if request.method == "POST" and department and current_term:
        try:
            run, created, unassigned = run_auto_assignment(department, current_term, request.user)
            messages.success(request, f"Assigned {len(created)} section(s).")
            if unassigned:
                messages.warning(request, f"{len(unassigned)} section(s) could not be assigned.")
        except AssignmentError as exc:
            messages.error(request, str(exc))
        return redirect("assignments:results")

    return render(request, "assignments/run_assignment.html", {
        "department": department, "current_term": current_term,
    })


@dept_head_required
def results(request):
    department = request.user.department
    current_term = AcademicTerm.objects.filter(is_current=True).first()
    assignments = Assignment.objects.none()
    load_rows = []

    if department and current_term:
        assignments = Assignment.objects.filter(
            section__course__department=department, section__academic_term=current_term
        ).select_related("instructor", "section__course", "section__student_group")

        regular_load = defaultdict(lambda: Decimal("0"))
        extension_load = defaultdict(lambda: Decimal("0"))
        major_courses = defaultdict(set)
        instructors = {}
        for a in assignments:
            instructors[a.instructor_id] = a.instructor
            if a.section.is_extension:
                extension_load[a.instructor_id] += a.load
            else:
                regular_load[a.instructor_id] += a.load
            if a.section.course.is_major:
                major_courses[a.instructor_id].add(a.section.course_id)

        for instructor_id, instructor in instructors.items():
            load_rows.append({
                "instructor": instructor,
                "regular_load": regular_load[instructor_id],
                "extension_load": extension_load[instructor_id],
                "major_course_count": len(major_courses[instructor_id]),
            })
        load_rows.sort(key=lambda r: r["regular_load"], reverse=True)

    return render(request, "assignments/results.html", {
        "assignments": assignments, "load_rows": load_rows,
        "department": department, "current_term": current_term,
    })


@instructor_required
def my_assignments(request):
    assignments = Assignment.objects.filter(instructor=request.user).select_related(
        "section__course", "section__student_group", "section__academic_term"
    )
    total_regular = sum((a.load for a in assignments if not a.section.is_extension), Decimal("0"))
    total_extension = sum((a.load for a in assignments if a.section.is_extension), Decimal("0"))
    return render(request, "assignments/my_assignments.html", {
        "assignments": assignments, "total_regular": total_regular, "total_extension": total_extension,
    })
