from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class PreferenceWindow(models.Model):
    """The department head sets this deadline each term; instructors must
    submit their top-3 course preferences before it closes."""

    department = models.ForeignKey(
        "institutions.Department", on_delete=models.CASCADE, related_name="preference_windows"
    )
    academic_term = models.ForeignKey(
        "institutions.AcademicTerm", on_delete=models.CASCADE, related_name="preference_windows"
    )
    opens_at = models.DateTimeField(default=timezone.now)
    deadline = models.DateTimeField()
    closed_manually = models.BooleanField(default=False)

    class Meta:
        unique_together = ("department", "academic_term")

    def __str__(self):
        return f"{self.department.code} preferences for {self.academic_term} (due {self.deadline:%Y-%m-%d %H:%M})"

    @property
    def is_open(self):
        if self.closed_manually:
            return False
        now = timezone.now()
        return self.opens_at <= now <= self.deadline


class InstructorPreference(models.Model):
    """One ranked course preference (1=top choice .. 3=third choice)."""

    instructor = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="course_preferences"
    )
    academic_term = models.ForeignKey(
        "institutions.AcademicTerm", on_delete=models.CASCADE, related_name="instructor_preferences"
    )
    course = models.ForeignKey(
        "curriculum.Course", on_delete=models.CASCADE, related_name="preferred_by"
    )
    rank = models.PositiveSmallIntegerField(
        choices=[(1, "1st choice"), (2, "2nd choice"), (3, "3rd choice")]
    )

    class Meta:
        unique_together = [
            ("instructor", "academic_term", "rank"),
            ("instructor", "academic_term", "course"),
        ]
        ordering = ["rank"]

    def __str__(self):
        return f"{self.instructor}: #{self.rank} {self.course.code} ({self.academic_term})"

    def clean(self):
        if self.course.department_id != self.instructor.department_id:
            raise ValidationError("Instructors may only prefer courses owned by their own department.")
