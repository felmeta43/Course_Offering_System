from django.db import models


class CourseExperience(models.Model):
    """How many times an instructor has taught a given course. Seeded
    manually by the department head initially; after that the assignment
    engine increments it automatically whenever a new assignment is made."""

    instructor = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="course_experiences"
    )
    course = models.ForeignKey(
        "curriculum.Course", on_delete=models.CASCADE, related_name="instructor_experiences"
    )
    times_taught = models.PositiveIntegerField(default=0)
    last_taught_term = models.ForeignKey(
        "institutions.AcademicTerm", on_delete=models.SET_NULL, null=True, blank=True
    )

    class Meta:
        unique_together = ("instructor", "course")

    def __str__(self):
        return f"{self.instructor} x {self.course.code}: {self.times_taught}"


class AssignmentRun(models.Model):
    """An audit record of one click of 'Assign Automatically'."""

    class Status(models.TextChoices):
        SUCCESS = "SUCCESS", "Completed"
        PARTIAL = "PARTIAL", "Completed with unassigned sections"

    department = models.ForeignKey(
        "institutions.Department", on_delete=models.CASCADE, related_name="assignment_runs"
    )
    academic_term = models.ForeignKey(
        "institutions.AcademicTerm", on_delete=models.CASCADE, related_name="assignment_runs"
    )
    run_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, related_name="triggered_runs"
    )
    run_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.SUCCESS)
    log = models.TextField(blank=True)

    class Meta:
        ordering = ["-run_at"]

    def __str__(self):
        return f"Run for {self.department.code} {self.academic_term} at {self.run_at:%Y-%m-%d %H:%M}"


class Assignment(models.Model):
    """The final instructor -> section assignment."""

    class Method(models.TextChoices):
        AUTO = "AUTO", "Automatic"
        MANUAL = "MANUAL", "Manual override"

    section = models.OneToOneField(
        "curriculum.Section", on_delete=models.CASCADE, related_name="assignment"
    )
    instructor = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="assignments"
    )
    load = models.DecimalField(max_digits=6, decimal_places=2)
    method = models.CharField(max_length=10, choices=Method.choices, default=Method.AUTO)
    run = models.ForeignKey(
        AssignmentRun, on_delete=models.SET_NULL, null=True, blank=True, related_name="assignments"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.section} -> {self.instructor}"
