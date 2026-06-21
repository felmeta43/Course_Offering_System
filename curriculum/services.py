from .models import Course, Section, StudentGroup


def generate_sections_for_term(academic_term):
    """Create the Section rows that need an instructor for this term.

    For every StudentGroup in the term, find every Course whose year_level,
    semester and target departments match that group, and ensure a Section
    exists linking them. This is how common/service courses (e.g. Emerging
    Technology) end up generating sections for every consuming department,
    not just the owning one.
    """
    created = []
    groups = StudentGroup.objects.filter(academic_term=academic_term)
    courses = Course.objects.filter(semester=academic_term.semester).prefetch_related(
        "target_departments"
    )

    for group in groups:
        for course in courses:
            if course.year_level != group.year_level:
                continue
            if group.department_id not in course.all_target_departments():
                continue
            section, was_created = Section.objects.get_or_create(
                course=course, student_group=group, defaults={"academic_term": academic_term}
            )
            if was_created:
                created.append(section)
    return created
