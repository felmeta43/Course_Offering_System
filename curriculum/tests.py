import io

import openpyxl
from django.test import TestCase

from institutions.models import AcademicTerm, Department, Institution

from .excel_io import import_courses_from_workbook, import_student_groups_from_workbook
from .models import Course, StudentGroup
from .services import generate_sections_for_term


def _workbook_file(headers, rows):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(headers)
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


class CourseImportTests(TestCase):
    def setUp(self):
        self.institution = Institution.get_solo()
        self.cs = Department.objects.create(institution=self.institution, name="Computer Science", code="CS")
        self.ee = Department.objects.create(institution=self.institution, name="Electrical Eng", code="EE")

    def test_import_creates_courses_with_target_departments_and_prereqs(self):
        headers = [
            "department_code", "course_code", "course_title", "credit_hours", "lecture_hours",
            "tutorial_hours", "lab_hours", "course_type", "year_level", "semester",
            "target_department_codes", "prerequisite_codes",
        ]
        rows = [
            ["CS", "CS101", "Intro to Programming", 3, 3, 0, 2, "MAJOR", 1, 1, "", ""],
            ["CS", "CS301", "Emerging Tech", 3, 2, 0, 3, "COMMON", 3, 1, "EE", "CS101"],
        ]
        f = _workbook_file(headers, rows)
        created, updated, errors = import_courses_from_workbook(f)
        self.assertEqual(created, 2)
        self.assertEqual(errors, [])

        emtech = Course.objects.get(code="CS301")
        self.assertIn(self.ee, emtech.target_departments.all())
        self.assertIn(Course.objects.get(code="CS101"), emtech.prerequisites.all())

    def test_unknown_department_reports_error(self):
        headers = ["department_code", "course_code", "course_title", "credit_hours", "lecture_hours",
                   "tutorial_hours", "lab_hours", "course_type", "year_level", "semester",
                   "target_department_codes", "prerequisite_codes"]
        rows = [["ZZ", "X101", "Mystery", 3, 3, 0, 0, "MAJOR", 1, 1, "", ""]]
        f = _workbook_file(headers, rows)
        created, updated, errors = import_courses_from_workbook(f)
        self.assertEqual(created, 0)
        self.assertEqual(len(errors), 1)


class StudentGroupImportTests(TestCase):
    def setUp(self):
        self.institution = Institution.get_solo()
        self.cs = Department.objects.create(institution=self.institution, name="Computer Science", code="CS")

    def test_import_creates_student_groups_and_term(self):
        headers = ["department_code", "academic_year", "semester", "year_level", "section",
                   "number_of_students", "is_extension"]
        rows = [
            ["CS", "2025/2026", 1, 2, "A", 45, "NO"],
            ["CS", "2025/2026", 1, 2, "B", 20, "YES"],
        ]
        f = _workbook_file(headers, rows)
        created, updated, errors = import_student_groups_from_workbook(f, self.institution)
        self.assertEqual(created, 2)
        self.assertEqual(errors, [])
        self.assertEqual(StudentGroup.objects.filter(is_extension=True).count(), 1)
        self.assertEqual(AcademicTerm.objects.count(), 1)


class SectionGenerationTests(TestCase):
    def setUp(self):
        self.institution = Institution.get_solo()
        self.cs = Department.objects.create(institution=self.institution, name="Computer Science", code="CS")
        self.ee = Department.objects.create(institution=self.institution, name="Electrical Eng", code="EE")
        self.term = AcademicTerm.objects.create(institution=self.institution, academic_year="2025/2026", semester=1)

    def test_common_course_generates_sections_for_target_departments_too(self):
        course = Course.objects.create(
            department=self.cs, code="CS301", title="Emerging Tech", year_level=3, semester=1,
            course_type=Course.CourseType.COMMON,
        )
        course.target_departments.add(self.ee)
        StudentGroup.objects.create(
            department=self.cs, academic_term=self.term, year_level=3, section="A", number_of_students=30
        )
        StudentGroup.objects.create(
            department=self.ee, academic_term=self.term, year_level=3, section="A", number_of_students=30
        )

        created = generate_sections_for_term(self.term)
        self.assertEqual(len(created), 2)
