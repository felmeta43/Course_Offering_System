# Course Offering System

A Django-based web app for automatically assigning courses to instructors
each semester, configurable for any college or university.

## Features

- **Customizable institution settings** (`institutions.Institution`): name/branding
  plus tunable policy knobs - max major courses per instructor, the large-section
  threshold for doubled lab load, and the scoring weights used by the
  assignment engine. No code changes needed to retune the system for a
  different school.
- **Department-set preference deadlines** (`preferences.PreferenceWindow`):
  each department head opens a window per term; instructors submit their
  top-3 course preferences (`preferences.InstructorPreference`) only while
  it's open.
- **One-click automatic assignment** (`assignments.services.run_auto_assignment`):
  once the deadline passes, the department head clicks "Assign
  Automatically" and the engine assigns every unassigned section, scoring
  each instructor/course pair on preference rank, academic rank, overall
  experience, and course-specific experience, while penalizing instructors
  who already carry more load - this is what keeps the load balanced.
- **Common/service courses** (e.g. "Emerging Technology") are modelled as a
  `Course` with `target_departments` pointing at every department that
  consumes it. Section generation creates one section per consuming
  department's student group, and the owning department's instructors are
  balanced across all of them exactly like their own major courses.
- **Major-course cap**: `Institution.max_major_courses_per_instructor`
  (default 2) is enforced in the engine - an instructor already at the cap
  is simply excluded from candidacy for another major course.
- **Load formula** (`curriculum.Section.compute_load`):
  `load = lecture_hours + 2/3*lab_hours + 2/3*tutorial_hours`, with the lab
  contribution doubled when the section's student count exceeds
  `Institution.large_section_threshold` (default 35). Computed per section.
- **Extension sections balanced independently**: sections on a
  `StudentGroup` flagged `is_extension=True` are load-balanced in their own
  pool, never compared against regular-student load.
- **Bulk Excel import** for curriculum (`curriculum.excel_io`) and student
  groups (year/section/headcount per department per term), with
  downloadable templates pre-filled with the expected columns and a sample
  row.
- **Experience auto-calculation**: `CourseExperience.times_taught` and
  `User.overall_experience_years` start as department-head-entered values;
  after the first automatic assignment run touches an instructor, the
  engine flips `experience_auto_calculated=True` and maintains both figures
  from then on based on actual assignment history.

## Project layout

- `accounts` - custom `User` model with roles (Admin / Department Head /
  Instructor), academic rank, and experience fields.
- `institutions` - `Institution` (singleton settings), `Department`,
  `AcademicTerm`.
- `curriculum` - `Course`, `StudentGroup`, `Section` (auto-generated per
  term from courses x student groups), Excel import/export helpers.
- `preferences` - `PreferenceWindow`, `InstructorPreference`.
- `assignments` - `CourseExperience`, `Assignment`, `AssignmentRun`, and the
  `services.py` auto-assignment engine.

## Getting started

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Then, as the superuser (role ADMIN) via `/admin/`:

1. Edit the **Institution** record (auto-created on first access) to set
   your school's name and policy weights.
2. Create **Departments** and an **Academic Term**.
3. Create department head and instructor **Users**, assigning each a
   department and role; set instructors' initial academic rank and
   experience.
4. Import **Courses** and **Student Groups** via
   `/curriculum/courses/import/` and `/curriculum/student-groups/import/`
   (download the templates from those pages first).
5. Generate **Sections** for the term at `/curriculum/sections/generate/`.

Then, as a **Department Head**:

6. Set the preference deadline at `/preferences/deadlines/`.
7. After instructors submit preferences and the deadline passes, click
   **Assign Automatically** at `/assignments/run/` and review the load
   report at `/assignments/results/`.

Instructors submit their top-3 preferences at `/preferences/submit/` and
view their assigned load at `/assignments/my-assignments/`.

## Running tests

```bash
python manage.py test
```

Tests cover the load formula (including the large-section lab-hour
doubling), the major-course cap, load balancing across instructors,
common-course section generation/assignment across departments,
independent balancing of extension sections, preference-driven assignment,
post-run experience updates, and the Excel import paths.
