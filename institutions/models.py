from django.core.exceptions import ValidationError
from django.db import models


class Institution(models.Model):
    """Singleton holding the customizable identity & policy settings for the
    college/University running this system. Keeping these as data (rather
    than code constants) is what makes the system reusable across schools."""

    name = models.CharField(max_length=255)
    short_name = models.CharField(max_length=50, blank=True)
    address = models.CharField(max_length=255, blank=True)
    logo = models.ImageField(upload_to="institution_logos/", blank=True, null=True)

    # ---- Policy knobs (tunable per institution, not hard-coded) ----
    max_major_courses_per_instructor = models.PositiveSmallIntegerField(
        default=2,
        help_text="No instructor may be assigned more major courses than this in a term.",
    )
    large_section_threshold = models.PositiveSmallIntegerField(
        default=35,
        help_text="Sections with more students than this get doubled lab-hour load.",
    )

    # Weights used by the auto-assignment scoring engine.
    weight_preference = models.FloatField(default=40.0)
    weight_academic_rank = models.FloatField(default=20.0)
    weight_overall_experience = models.FloatField(default=15.0)
    weight_course_experience = models.FloatField(default=25.0)
    load_balance_penalty = models.FloatField(
        default=10.0,
        help_text="How strongly the engine penalizes assigning more load to an "
        "already-loaded instructor. Higher = stronger load balancing.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Institution Settings"
        verbose_name_plural = "Institution Settings"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.pk and Institution.objects.exists():
            raise ValidationError("Only one Institution settings record is allowed.")
        super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(
            pk=1, defaults={"name": "My College / University"}
        )
        return obj


class Department(models.Model):
    institution = models.ForeignKey(
        Institution, on_delete=models.CASCADE, related_name="departments"
    )
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=20, unique=True)
    head = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="headed_department",
        limit_choices_to={"role": "DEPT_HEAD"},
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.code} - {self.name}"


class AcademicTerm(models.Model):
    SEMESTER_CHOICES = [(1, "Semester 1"), (2, "Semester 2"), (3, "Summer")]

    institution = models.ForeignKey(
        Institution, on_delete=models.CASCADE, related_name="terms"
    )
    academic_year = models.CharField(
        max_length=20, help_text="e.g. 2025/2026"
    )
    semester = models.PositiveSmallIntegerField(choices=SEMESTER_CHOICES)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    is_current = models.BooleanField(default=False)

    class Meta:
        unique_together = ("institution", "academic_year", "semester")
        ordering = ["-academic_year", "-semester"]

    def __str__(self):
        return f"{self.academic_year} - {self.get_semester_display()}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.is_current:
            AcademicTerm.objects.filter(institution=self.institution).exclude(
                pk=self.pk
            ).update(is_current=False)
