# College0 - Phase II Application + Design Report

This repository contains the Phase II Design Report and a runnable project application that implements the main workflows described in the report.

## Contents

- `College0_Phase_II_Final.pdf` - finalized Phase II design report
- `app.py` - Flask application (role-based college management system)
- `schema.sql` - SQLite schema aligned with report entities
- `templates/` - major GUI screens by role
- `static/styles.css` - basic UI styling

## Run locally

1. Create and activate a virtual environment.
2. Install dependencies:
   - `pip install -r requirements.txt`
3. Start the app:
   - `python app.py`
4. Open:
   - `http://127.0.0.1:5000/`

## Demo accounts

- Registrar: `registrar@college0.edu` / `registrar123`
- Student: `student@college0.edu` / `student123`
- Instructor: `instructor@college0.edu` / `instructor123`

## Implemented use-case coverage

- UC-01 Browse Public Info (`/`)
- UC-02 Apply as Student (`/apply/student`)
- UC-03 Apply as Instructor (`/apply/instructor`)
- UC-04 Manage Semester Phases (`/registrar/semester`)
- UC-05 Register Courses (`/student/register`)
- UC-06 Admit Waitlisted Student (`/instructor/waitlist`)
- UC-07 Submit Review + taboo moderation (`/student/review`)
- UC-08 Submit Grades (`/instructor/grades`)
- UC-09 File/Resolve Complaint (`/complaints`)
- UC-10 Ask AI Assistant (`/ai`)

## Notes

- The app uses SQLite (`college0.db`) and auto-seeds starter data on first run.
- The implementation follows the document's role model (Visitor, Student, Instructor, Registrar), semester lifecycle, and disciplinary logic (warnings/suspension).
