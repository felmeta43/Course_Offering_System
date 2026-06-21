from django.contrib import messages
from django.shortcuts import redirect, render

from accounts.decorators import dept_head_required, instructor_required
from institutions.models import AcademicTerm

from .forms import PreferenceSubmissionForm, PreferenceWindowForm
from .models import InstructorPreference, PreferenceWindow


@dept_head_required
def manage_deadlines(request):
    department = request.user.department
    windows = PreferenceWindow.objects.filter(department=department) if department else []

    if request.method == "POST":
        form = PreferenceWindowForm(request.POST)
        if form.is_valid():
            window = form.save(commit=False)
            window.department = department
            window.save()
            messages.success(request, f"Preference deadline set for {window.academic_term}.")
            return redirect("preferences:manage_deadlines")
    else:
        form = PreferenceWindowForm()

    return render(request, "preferences/manage_deadlines.html", {
        "form": form, "windows": windows,
    })


@instructor_required
def submit_preferences(request):
    user = request.user
    current_term = AcademicTerm.objects.filter(is_current=True).first()
    window = None
    if current_term and user.department:
        window = PreferenceWindow.objects.filter(
            department=user.department, academic_term=current_term
        ).first()

    if not current_term or not window:
        return render(request, "preferences/submit_preferences.html", {
            "window": None, "current_term": current_term,
        })

    existing = InstructorPreference.objects.filter(
        instructor=user, academic_term=current_term
    ).order_by("rank")
    initial = {}
    for pref in existing:
        initial[f"choice_{pref.rank}"] = pref.course_id

    if request.method == "POST" and window.is_open:
        form = PreferenceSubmissionForm(request.POST, department=user.department)
        if form.is_valid():
            InstructorPreference.objects.filter(instructor=user, academic_term=current_term).delete()
            for rank in (1, 2, 3):
                course = form.cleaned_data[f"choice_{rank}"]
                InstructorPreference.objects.create(
                    instructor=user, academic_term=current_term, course=course, rank=rank
                )
            messages.success(request, "Your preferences were submitted.")
            return redirect("preferences:submit_preferences")
    else:
        form = PreferenceSubmissionForm(department=user.department, initial=initial)

    return render(request, "preferences/submit_preferences.html", {
        "form": form, "window": window, "current_term": current_term, "existing": existing,
    })
