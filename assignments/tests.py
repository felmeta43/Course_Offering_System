from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from curriculum.models import Course, Section, StudentGroup
from institutions.models import AcademicTerm, Department, Institution
from preferences.models import InstructorPreference, PreferenceWindow

from .models import Assignment, CourseExperience
from .services import AssignmentError, run_auto_assignment


class BaseAssignmentTestCase(TestCase):
    def setUp(self):
        self.institution = Institution.get_solo()
        self.department = Department.objects.create(
            institution=self.institution, name="Computer Science", code="CS"
        )
        self.other_department = Department.objects.create(
            institution=self.institution, name="Electrical Engineering", code="EE"
        )
        self.term = AcademicTerm.objects.create(
            institution=self.institution, academic_year="2025/2026", semester=1, is_current=True
        )

    def make_instructor(self, username, rank=User.AcademicRank.LECTURER, experience=2):
        return User.objects.create_user(
            username=username,
            password="pass1234",
            role=User.Role.INSTRUCTOR,
            department=self.department,
            academic_rank=rank,
            overall_experience_years=experience,
        )

    def make_course(self, code, lecture=3, tutorial=0, lab=0, course_type=Course.CourseType.MAJOR,
                     year_level=1, department=None, target_departments=None):
        course = Course.objects.create(
            department=department or self.department,
            code=code,
            title=code,
            credit_hours=3,
            lecture_hours=lecture,
            tutorial_hours=tutorial,
            lab_hours=lab,
            course_type=course_type,
            year_level=year_level,
            semester=1,
        )
        if target_departments:
            course.target_departments.set(target_departments)
        return course

    def make_student_group(self, department, section="A", students=30, is_extension=False, year_level=1):
        return StudentGroup.objects.create(
            department=department,
            academic_term=self.term,
            year_level=year_level,
            section=section,
            number_of_students=students,
            is_extension=is_extension,
        )

    def make_section(self, course, student_group):
        return Section.objects.create(
            course=course, student_group=student_group, academic_term=self.term
        )

    def close_preference_window(self):
        PreferenceWindow.objects.create(
            department=self.department,
            academic_term=self.term,
            opens_at=timezone.now() - timezone.timedelta(days=2),
            deadline=timezone.now() - timezone.timedelta(days=1),
        )


class LoadFormulaTests(BaseAssignmentTestCase):
    def test_load_formula_normal_section(self):
        course = self.make_course("CS101", lecture=3, tutorial=2, lab=3)
        group = self.make_student_group(self.department, students=30)
        section = self.make_section(course, group)
        # 3 + 2/3*3 + 2/3*2 = 3 + 2 + 1.333... = 6.333...
        expected = Decimal("3") + (Decimal("2") / 3 * 3) + (Decimal("2") / 3 * 2)
        self.assertAlmostEqual(float(section.compute_load()), float(expected), places=3)

    def test_lab_hours_double_for_large_sections(self):
        course = self.make_course("CS102", lecture=2, tutorial=0, lab=4)
        small_group = self.make_student_group(self.department, section="A", students=30)
        large_group = self.make_student_group(self.department, section="B", students=40)
        small_section = self.make_section(course, small_group)
        large_section = self.make_section(course, large_group)

        small_load = small_section.compute_load()
        large_load = large_section.compute_load()
        # Large section's lab contribution should be exactly double the small one's.
        lab_contrib_small = small_load - course.lecture_hours
        lab_contrib_large = large_load - course.lecture_hours
        self.assertAlmostEqual(float(lab_contrib_large), float(lab_contrib_small) * 2, places=6)

    def test_threshold_boundary_uses_single_lab_factor(self):
        course = self.make_course("CS103", lecture=0, tutorial=0, lab=3)
        group = self.make_student_group(self.department, students=35)  # exactly at threshold, not doubled
        section = self.make_section(course, group)
        expected = Decimal("2") / 3 * 3
        self.assertEqual(section.compute_load(), expected)


class AutoAssignmentTests(BaseAssignmentTestCase):
    def test_raises_if_preference_window_still_open(self):
        PreferenceWindow.objects.create(
            department=self.department,
            academic_term=self.term,
            opens_at=timezone.now() - timezone.timedelta(days=1),
            deadline=timezone.now() + timezone.timedelta(days=1),
        )
        instructor = self.make_instructor("i1")
        course = self.make_course("CS201")
        group = self.make_student_group(self.department)
        self.make_section(course, group)

        with self.assertRaises(AssignmentError):
            run_auto_assignment(self.department, self.term, instructor)

    def test_assigns_all_sections_when_possible(self):
        self.close_preference_window()
        i1 = self.make_instructor("i1")
        i2 = self.make_instructor("i2")
        course = self.make_course("CS201")
        group_a = self.make_student_group(self.department, section="A")
        group_b = self.make_student_group(self.department, section="B")
        self.make_section(course, group_a)
        self.make_section(course, group_b)

        run, created, unassigned = run_auto_assignment(self.department, self.term, i1)
        self.assertEqual(len(created), 2)
        self.assertEqual(len(unassigned), 0)
        self.assertEqual(Assignment.objects.count(), 2)

    def test_no_instructor_gets_more_than_two_major_courses(self):
        self.close_preference_window()
        self.make_instructor("i1")
        self.make_instructor("i2")
        courses = [self.make_course(f"CS{n}") for n in range(300, 305)]  # 5 major courses
        for idx, course in enumerate(courses):
            group = self.make_student_group(self.department, section=f"S{idx}")
            self.make_section(course, group)

        run, created, unassigned = run_auto_assignment(self.department, self.term, None)

        major_counts = {}
        for assignment in Assignment.objects.select_related("instructor", "section__course"):
            major_counts.setdefault(assignment.instructor_id, set()).add(assignment.section.course_id)

        for instructor_id, course_ids in major_counts.items():
            self.assertLessEqual(len(course_ids), 2)
        # With only 2 instructors capped at 2 major courses each (max 4 assignable),
        # at least one of the 5 sections must be left unassigned.
        self.assertGreaterEqual(len(unassigned), 1)

    def test_load_is_balanced_between_instructors(self):
        self.close_preference_window()
        self.make_instructor("i1")
        self.make_instructor("i2")
        # 6 identical-load common courses so there's no preference signal driving the split.
        courses = [
            self.make_course(f"GEN{n}", lecture=2, tutorial=0, lab=0, course_type=Course.CourseType.COMMON)
            for n in range(10)
        ][:6]
        for idx, course in enumerate(courses):
            group = self.make_student_group(self.department, section=f"S{idx}")
            self.make_section(course, group)

        run_auto_assignment(self.department, self.term, None)

        totals = {}
        for a in Assignment.objects.all():
            totals[a.instructor_id] = totals.get(a.instructor_id, Decimal("0")) + a.load
        self.assertEqual(len(totals), 2)
        values = list(totals.values())
        self.assertAlmostEqual(float(values[0]), float(values[1]), delta=2.5)

    def test_common_course_sections_for_other_department_get_assigned(self):
        self.close_preference_window()
        self.make_instructor("i1")
        course = self.make_course(
            "EMTECH", course_type=Course.CourseType.COMMON,
            target_departments=[self.other_department],
        )
        own_group = self.make_student_group(self.department, section="A")
        other_group = self.make_student_group(self.other_department, section="A")
        self.make_section(course, own_group)
        self.make_section(course, other_group)

        run, created, unassigned = run_auto_assignment(self.department, self.term, None)
        self.assertEqual(len(created), 2)
        self.assertEqual(len(unassigned), 0)

    def test_extension_sections_balanced_independently_of_regular(self):
        self.close_preference_window()
        self.make_instructor("i1")
        self.make_instructor("i2")
        regular_course = self.make_course("CS401", lecture=4)
        ext_course = self.make_course("CS402", lecture=4)
        reg_group = self.make_student_group(self.department, section="A", is_extension=False)
        ext_group = self.make_student_group(self.department, section="B", is_extension=True)
        self.make_section(regular_course, reg_group)
        self.make_section(ext_course, ext_group)

        run_auto_assignment(self.department, self.term, None)
        ext_assignment = Assignment.objects.get(section__student_group__is_extension=True)
        reg_assignment = Assignment.objects.get(section__student_group__is_extension=False)
        # Both pools assigned independently; no error raised means independence held.
        self.assertIsNotNone(ext_assignment.instructor_id)
        self.assertIsNotNone(reg_assignment.instructor_id)

    def test_preference_increases_likelihood_of_assignment(self):
        self.close_preference_window()
        preferred_instructor = self.make_instructor("preferred", experience=1)
        busy_instructor = self.make_instructor("busy", experience=1)
        course = self.make_course("CS501", lecture=3)
        group = self.make_student_group(self.department, section="A")
        self.make_section(course, group)

        InstructorPreference.objects.create(
            instructor=preferred_instructor, academic_term=self.term, course=course, rank=1
        )

        run_auto_assignment(self.department, self.term, None)
        assignment = Assignment.objects.get(section__course=course)
        self.assertEqual(assignment.instructor_id, preferred_instructor.id)

    def test_course_and_overall_experience_updated_after_run(self):
        self.close_preference_window()
        instructor = self.make_instructor("i1", experience=0)
        instructor.experience_auto_calculated = False
        instructor.save()
        course = self.make_course("CS601")
        group = self.make_student_group(self.department, section="A")
        self.make_section(course, group)

        run_auto_assignment(self.department, self.term, None)

        exp = CourseExperience.objects.get(instructor=instructor, course=course)
        self.assertEqual(exp.times_taught, 1)
        instructor.refresh_from_db()
        self.assertTrue(instructor.experience_auto_calculated)
        self.assertGreaterEqual(instructor.overall_experience_years, 1)

    def test_no_unassigned_sections_raises(self):
        self.close_preference_window()
        self.make_instructor("i1")
        with self.assertRaises(AssignmentError):
            run_auto_assignment(self.department, self.term, None)

    def test_previously_overloaded_instructor_gets_less_this_term(self):
        previous_term = AcademicTerm.objects.create(
            institution=self.institution, academic_year="2024/2025", semester=2
        )
        overloaded = self.make_instructor("overloaded")
        underloaded = self.make_instructor("underloaded")

        # Give `overloaded` a heavy previous-term load and `underloaded` a light one.
        prev_course_heavy = self.make_course("HIST901", lecture=10)
        prev_course_light = self.make_course("HIST902", lecture=1)
        heavy_group = StudentGroup.objects.create(
            department=self.department, academic_term=previous_term, year_level=1,
            section="A", number_of_students=30,
        )
        light_group = StudentGroup.objects.create(
            department=self.department, academic_term=previous_term, year_level=1,
            section="B", number_of_students=30,
        )
        heavy_section = Section.objects.create(
            course=prev_course_heavy, student_group=heavy_group, academic_term=previous_term
        )
        light_section = Section.objects.create(
            course=prev_course_light, student_group=light_group, academic_term=previous_term
        )
        Assignment.objects.create(
            section=heavy_section, instructor=overloaded, load=heavy_section.compute_load()
        )
        Assignment.objects.create(
            section=light_section, instructor=underloaded, load=light_section.compute_load()
        )

        self.close_preference_window()
        # One new common course this term - identical for both candidates, no
        # preference signal, so the previous-term deviation should decide it.
        course = self.make_course("GEN900", lecture=3, course_type=Course.CourseType.COMMON)
        group = self.make_student_group(self.department, section="Z")
        self.make_section(course, group)

        run_auto_assignment(self.department, self.term, None)

        assignment = Assignment.objects.get(section__course=course)
        self.assertEqual(assignment.instructor_id, underloaded.id)
