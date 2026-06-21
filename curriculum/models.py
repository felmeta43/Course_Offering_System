from decimal import Decimal

from django.db import models


class Course(models.Model):
    """A course in the curriculum. Imported in bulk from Excel by the admin.

    ``department`` is the *owning* department (the one whose instructors
    teach it). For a course shared with other departments (e.g. "Emerging
    Technology"), the owning department's instructors still teach it - the
    other departments that consume it are listed in ``target_departments``.
    """

    class CourseType(models.TextChoices):
        MAJOR = "MAJOR", "Major Course"
        COMMON = "COMMON", "Common / Service Course"
        EXTENSION = "EXTENSION", "Extension Course"

    department = models.ForeignKey(
        "institutions.Department", on_delete=models.CASCADE, related_name="owned_courses"
    )
    target_departments = models.ManyToManyField(
        "institutions.Department",
        related_name="consumed_courses",
        blank=True,
        help_text="Departments whose students take this course (besides the owning department).",
    )
    code = models.CharField(max_length=30, unique=True)
    title = models.CharField(max_length=255)
    credit_hours = models.DecimalField(max_digits=4, decimal_places=1, default=Decimal("0"))
    lecture_hours = models.DecimalField(max_digits=4, decimal_places=1, default=Decimal("0"))
    tutorial_hours = models.DecimalField(max_digits=4, decimal_places=1, default=Decimal("0"))
    lab_hours = models.DecimalField(max_digits=4, decimal_places=1, default=Decimal("0"))
    course_type = models.CharField(
        max_length=10, choices=CourseType.choices, default=CourseType.MAJOR
    )
    year_level = models.PositiveSmallIntegerField(help_text="Year of study this course targets, e.g. 1-5")
    semester = models.PositiveSmallIntegerField(
        choices=[(1, "Semester 1"), (2, "Semester 2"), (3, "Summer")], default=1
    )
    prerequisites = models.ManyToManyField("self", blank=True, symmetrical=False, related_name="dependents")

    class Meta:
        ordering = ["department__code", "year_level", "code"]

    def __str__(self):
        return f"{self.code} - {self.title}"

    @property
    def is_major(self):
        return self.course_type == self.CourseType.MAJOR

    @property
    def is_common(self):
        return self.course_type == self.CourseType.COMMON

    @property
    def is_extension(self):
        return self.course_type == self.CourseType.EXTENSION

    def all_target_departments(self):
        """Every department whose students take this course, owning dept included."""
        ids = {self.department_id}
        ids.update(self.target_departments.values_list("id", flat=True))
        return ids


class StudentGroup(models.Model):
    """A cohort of students: department + year + section, with headcount.

    Imported in bulk from Excel by the admin every term. Drives how many
    Sections get generated for each course (one Section per StudentGroup
    that takes that course).
    """

    department = models.ForeignKey(
        "institutions.Department", on_delete=models.CASCADE, related_name="student_groups"
    )
    academic_term = models.ForeignKey(
        "institutions.AcademicTerm", on_delete=models.CASCADE, related_name="student_groups"
    )
    year_level = models.PositiveSmallIntegerField()
    section = models.CharField(max_length=10, help_text="e.g. A, B, C")
    number_of_students = models.PositiveIntegerField()
    is_extension = models.BooleanField(
        default=False, help_text="Extension/evening program students, balanced separately from regular."
    )

    class Meta:
        unique_together = ("department", "academic_term", "year_level", "section", "is_extension")
        ordering = ["department__code", "year_level", "section"]

    def __str__(self):
        kind = "Ext" if self.is_extension else "Reg"
        return f"{self.department.code} Y{self.year_level}{self.section} ({kind}) - {self.academic_term}"


class Section(models.Model):
    """One course offered to one student group in one term: the unit that
    actually needs an instructor assigned to it."""

    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="sections")
    student_group = models.ForeignKey(
        StudentGroup, on_delete=models.CASCADE, related_name="sections"
    )
    academic_term = models.ForeignKey(
        "institutions.AcademicTerm", on_delete=models.CASCADE, related_name="sections"
    )

    class Meta:
        unique_together = ("course", "student_group")
        ordering = ["course__code", "student_group__section"]

    def __str__(self):
        return f"{self.course.code} -> {self.student_group}"

    @property
    def is_extension(self):
        return self.student_group.is_extension

    @property
    def is_common_for(self):
        """True if this section serves a department other than the course's own."""
        return self.student_group.department_id != self.course.department_id

    def compute_load(self, large_section_threshold=35):
        """Load = lecture_hours + 2/3*lab_hours + 2/3*tutorial_hours
        If number_of_students > threshold, lab hours portion is doubled.
        """
        course = self.course
        lab_factor = Decimal("2") / Decimal("3")
        if self.student_group.number_of_students > large_section_threshold:
            lab_factor *= 2
        load = course.lecture_hours + (lab_factor * course.lab_hours) + (
            Decimal("2") / Decimal("3") * course.tutorial_hours
        )
        return load
