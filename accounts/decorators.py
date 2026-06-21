from django.contrib.auth.decorators import user_passes_test


def role_required(*roles):
    def check(user):
        return user.is_authenticated and user.role in roles

    return user_passes_test(check, login_url="login")


admin_required = role_required("ADMIN")
dept_head_required = role_required("DEPT_HEAD")
instructor_required = role_required("INSTRUCTOR")
dept_head_or_admin_required = role_required("ADMIN", "DEPT_HEAD")
