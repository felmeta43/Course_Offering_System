from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "ADMIN", "System Admin"
        DEPT_HEAD = "DEPT_HEAD", "Department Head"
        INSTRUCTOR = "INSTRUCTOR", "Instructor"

    class AcademicRank(models.TextChoices):
        GRADUATE_ASSISTANT = "GA", "Graduate Assistant"
        ASSISTANT_LECTURER = "ASST_LECTURER", "Assistant Lecturer"
        LECTURER = "LECTURER", "Lecturer"
        ASSISTANT_PROFESSOR = "ASST_PROF", "Assistant Professor"
        ASSOCIATE_PROFESSOR = "ASSOC_PROF", "Associate Professor"
        PROFESSOR = "PROF", "Professor"

    # Rank weight used directly by the assignment engine's scoring.
    RANK_WEIGHTS = {
        AcademicRank.GRADUATE_ASSISTANT: 1,
        AcademicRank.ASSISTANT_LECTURER: 2,
        AcademicRank.LECTURER: 3,
        AcademicRank.ASSISTANT_PROFESSOR: 4,
        AcademicRank.ASSOCIATE_PROFESSOR: 5,
        AcademicRank.PROFESSOR: 6,
    }

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.INSTRUCTOR)
    department = models.ForeignKey(
        "institutions.Department",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="members",
    )

    # --- Instructor-only fields ---
    academic_rank = models.CharField(
        max_length=20, choices=AcademicRank.choices, blank=True
    )
    overall_experience_years = models.PositiveSmallIntegerField(
        default=0,
        help_text="Total years of teaching experience. Set manually at first; "
        "once the system has run terms it can be recalculated automatically.",
    )
    experience_auto_calculated = models.BooleanField(
        default=False,
        help_text="Once true, overall_experience_years is maintained by the "
        "system instead of being edited by the department head.",
    )

    def __str__(self):
        return self.get_full_name() or self.username

    @property
    def rank_weight(self):
        return self.RANK_WEIGHTS.get(self.academic_rank, 0)

    @property
    def is_instructor(self):
        return self.role == self.Role.INSTRUCTOR

    @property
    def is_department_head(self):
        return self.role == self.Role.DEPT_HEAD
