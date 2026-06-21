from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from institutions.models import AcademicTerm
from preferences.models import PreferenceWindow


@login_required
def dashboard(request):
    user = request.user
    current_term = AcademicTerm.objects.filter(is_current=True).first()

    if user.role == user.Role.ADMIN:
        return render(request, "accounts/dashboard_admin.html", {"current_term": current_term})

    if user.role == user.Role.DEPT_HEAD:
        window = None
        if current_term and user.department:
            window = PreferenceWindow.objects.filter(
                department=user.department, academic_term=current_term
            ).first()
        return render(
            request,
            "accounts/dashboard_dept_head.html",
            {"current_term": current_term, "window": window},
        )

    return render(request, "accounts/dashboard_instructor.html", {"current_term": current_term})
