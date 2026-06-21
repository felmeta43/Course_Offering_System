"""The course-assignment engine.

Given all unassigned Sections owned by a department for a term, assigns an
instructor to each one, balancing total load across instructors while
factoring in: instructor preference (top 3, set before the deadline),
academic rank, overall teaching experience, and experience with that
specific course. Regular-student sections and extension sections are load
balanced in two independent pools (per requirement #10), and common/service
courses taught to other departments are pooled together with the
department's own major/common courses for load-balancing purposes (per
requirement #5) - they are simply sections like any other, owned by this
department's instructors.
"""
from collections import defaultdict
from decimal import Decimal

from accounts.models import User
from curriculum.models import Course, Section
from preferences.models import InstructorPreference, PreferenceWindow

from .models import Assignment, AssignmentRun, CourseExperience

MAX_EXPERIENCE_NORM = Decimal("20")  # years, for normalizing the experience score
MAX_COURSE_EXPERIENCE_NORM = Decimal("10")  # times taught, for normalizing course-experience score
MAX_RANK_WEIGHT = Decimal(max(User.RANK_WEIGHTS.values()))


class AssignmentError(Exception):
    pass


def _preference_map(instructors, academic_term):
    """instructor_id -> {course_id: rank}"""
    prefs = InstructorPreference.objects.filter(
        instructor__in=instructors, academic_term=academic_term
    ).values_list("instructor_id", "course_id", "rank")
    out = defaultdict(dict)
    for instructor_id, course_id, rank in prefs:
        out[instructor_id][course_id] = rank
    return out


def _course_experience_map(instructors, courses):
    """(instructor_id, course_id) -> times_taught"""
    rows = CourseExperience.objects.filter(
        instructor__in=instructors, course__in=courses
    ).values_list("instructor_id", "course_id", "times_taught")
    return {(i, c): t for i, c, t in rows}


def _previous_term_load_map(instructors, academic_term):
    """instructor_id -> total load (regular + extension) carried in the term
    immediately before `academic_term`. Used so this run can compensate -
    instructors who were overloaded last semester are favored less this
    time, and previously under-loaded instructors are favored more."""
    previous_term = academic_term.previous_term()
    if previous_term is None:
        return {}, Decimal("0")

    rows = Assignment.objects.filter(
        instructor__in=instructors, section__academic_term=previous_term
    ).values_list("instructor_id", "load")

    totals = defaultdict(lambda: Decimal("0"))
    for instructor_id, load in rows:
        totals[instructor_id] += load

    # Average across *all* candidate instructors (including those with zero
    # previous load) so someone with no prior assignment still counts as
    # under-loaded relative to the group, not silently ignored.
    if instructors:
        average = sum(totals.values(), Decimal("0")) / len(instructors)
    else:
        average = Decimal("0")
    return dict(totals), average


class _InstructorState:
    __slots__ = (
        "instructor", "regular_load", "extension_load", "major_courses", "previous_term_deviation",
    )

    def __init__(self, instructor):
        self.instructor = instructor
        self.regular_load = Decimal("0")
        self.extension_load = Decimal("0")
        self.major_courses = set()  # course_ids of MAJOR courses already assigned
        self.previous_term_deviation = 0.0  # (prev_load - prev_average) / prev_average, clamped to [-1, 1]


def _score(instructor, course, state, weights, pref_rank, course_experience_count, current_load):
    """Returns a plain float score - this is a ranking heuristic, not money
    math, so we avoid Decimal/float mixing headaches here."""
    pref_bonus = 0.0
    if pref_rank:
        pref_bonus = float(weights.weight_preference) * ((4 - pref_rank) / 3)

    rank_score = float(weights.weight_academic_rank) * (
        instructor.rank_weight / float(MAX_RANK_WEIGHT)
    )

    exp_years = min(instructor.overall_experience_years, float(MAX_EXPERIENCE_NORM))
    exp_score = float(weights.weight_overall_experience) * (exp_years / float(MAX_EXPERIENCE_NORM))

    course_exp = min(course_experience_count, float(MAX_COURSE_EXPERIENCE_NORM))
    course_exp_score = float(weights.weight_course_experience) * (
        course_exp / float(MAX_COURSE_EXPERIENCE_NORM)
    )

    load_penalty = float(weights.load_balance_penalty) * float(current_load)

    # Cross-semester fairness: a positive deviation means this instructor
    # carried more than the group's average load last semester, so they are
    # penalized this semester; a negative deviation (under-loaded last time)
    # becomes a bonus, per the "previously overloaded instructors should
    # become comparatively less loaded" requirement.
    previous_term_adjustment = -float(weights.previous_term_balance_weight) * state.previous_term_deviation

    return (
        pref_bonus + rank_score + exp_score + course_exp_score
        - load_penalty + previous_term_adjustment
    )


def _assign_pool(sections, states, weights, pref_map, course_exp_map, max_major_courses, pool_attr):
    """Greedily assign instructors to `sections`, balancing `pool_attr`
    ('regular_load' or 'extension_load') across `states`. Mutates states in
    place and returns list of (section, instructor, load) assigned plus list
    of unassigned sections."""

    instructors_by_id = {s.instructor.id: s for s in states}

    def eligible_for(section):
        course = section.course
        result = []
        for state in states:
            if course.is_major and course.id not in state.major_courses:
                if len(state.major_courses) >= max_major_courses:
                    continue
            result.append(state)
        return result

    # Most-constrained-first: sections with fewer eligible instructors go first.
    pending = list(sections)
    pending.sort(key=lambda sec: (len(eligible_for(sec)), -sec.compute_load()))

    assigned = []
    unassigned = []

    for section in pending:
        course = section.course
        candidates = eligible_for(section)
        if not candidates:
            unassigned.append(section)
            continue

        load_value = section.compute_load()
        best_state = None
        best_score = None
        for state in candidates:
            current_load = getattr(state, pool_attr)
            pref_rank = pref_map.get(state.instructor.id, {}).get(course.id)
            course_exp = course_exp_map.get((state.instructor.id, course.id), 0)
            score = _score(
                state.instructor, course, state, weights, pref_rank, course_exp, current_load
            )
            if best_score is None or score > best_score or (
                score == best_score and current_load < getattr(best_state, pool_attr)
            ):
                best_score = score
                best_state = state

        setattr(best_state, pool_attr, getattr(best_state, pool_attr) + load_value)
        if course.is_major:
            best_state.major_courses.add(course.id)
        assigned.append((section, best_state.instructor, load_value))

    return assigned, unassigned


def run_auto_assignment(department, academic_term, run_by):
    from institutions.models import Institution

    institution = Institution.get_solo()

    window = PreferenceWindow.objects.filter(
        department=department, academic_term=academic_term
    ).first()
    if window is not None and window.is_open:
        raise AssignmentError(
            "The preference submission deadline has not passed yet for this department/term."
        )

    instructors = list(
        User.objects.filter(department=department, role=User.Role.INSTRUCTOR)
    )
    if not instructors:
        raise AssignmentError("This department has no instructors to assign courses to.")

    sections = list(
        Section.objects.filter(
            academic_term=academic_term, course__department=department, assignment__isnull=True
        ).select_related("course", "student_group")
    )
    if not sections:
        raise AssignmentError("There are no unassigned sections for this department/term.")

    states = [_InstructorState(i) for i in instructors]
    pref_map = _preference_map(instructors, academic_term)
    courses = Course.objects.filter(id__in={s.course_id for s in sections})
    course_exp_map = _course_experience_map(instructors, courses)

    previous_loads, previous_average = _previous_term_load_map(instructors, academic_term)
    for state in states:
        prev_load = previous_loads.get(state.instructor.id, Decimal("0"))
        if previous_average > 0:
            deviation = float((prev_load - previous_average) / previous_average)
            state.previous_term_deviation = max(-1.0, min(1.0, deviation))

    regular_sections = [s for s in sections if not s.is_extension]
    extension_sections = [s for s in sections if s.is_extension]

    regular_assigned, regular_unassigned = _assign_pool(
        regular_sections, states, institution, pref_map, course_exp_map,
        institution.max_major_courses_per_instructor, "regular_load",
    )
    extension_assigned, extension_unassigned = _assign_pool(
        extension_sections, states, institution, pref_map, course_exp_map,
        institution.max_major_courses_per_instructor, "extension_load",
    )

    all_assigned = regular_assigned + extension_assigned
    all_unassigned = regular_unassigned + extension_unassigned

    status = AssignmentRun.Status.SUCCESS if not all_unassigned else AssignmentRun.Status.PARTIAL
    log_lines = [f"Assigned {len(all_assigned)} section(s)."]
    if all_unassigned:
        log_lines.append(
            "Could not assign (no eligible instructor under the major-course cap): "
            + ", ".join(str(s) for s in all_unassigned)
        )

    run = AssignmentRun.objects.create(
        department=department,
        academic_term=academic_term,
        run_by=run_by,
        status=status,
        log="\n".join(log_lines),
    )

    created_assignments = []
    for section, instructor, load_value in all_assigned:
        assignment = Assignment.objects.create(
            section=section,
            instructor=instructor,
            load=load_value,
            method=Assignment.Method.AUTO,
            run=run,
        )
        created_assignments.append(assignment)

    _update_experience_after_run(created_assignments, academic_term)

    return run, created_assignments, all_unassigned


def _update_experience_after_run(created_assignments, academic_term):
    """Once an assignment run has happened for an instructor, their
    course-experience and overall-experience figures move from
    department-head-entered to system-calculated, per requirement #11."""
    counts = defaultdict(int)
    instructors_touched = set()
    for assignment in created_assignments:
        instructor = assignment.instructor
        course = assignment.section.course
        counts[(instructor.id, course.id)] += 1
        instructors_touched.add(instructor.id)

    for (instructor_id, course_id), count in counts.items():
        exp, _ = CourseExperience.objects.get_or_create(
            instructor_id=instructor_id, course_id=course_id
        )
        exp.times_taught += count
        exp.last_taught_term = academic_term
        exp.save()

    for instructor in User.objects.filter(id__in=instructors_touched):
        terms_taught = (
            Assignment.objects.filter(instructor=instructor)
            .values_list("section__academic_term_id", flat=True)
            .distinct()
            .count()
        )
        instructor.overall_experience_years = max(instructor.overall_experience_years, terms_taught)
        instructor.experience_auto_calculated = True
        instructor.save(update_fields=["overall_experience_years", "experience_auto_calculated"])
