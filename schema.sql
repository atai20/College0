PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
  user_id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL CHECK(role IN ('visitor','student','instructor','registrar')),
  status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','suspended','terminated','graduated')),
  warnings INTEGER NOT NULL DEFAULT 0,
  first_login_reset INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS student_profiles (
  student_id INTEGER PRIMARY KEY,
  overall_gpa REAL NOT NULL DEFAULT 0.0,
  semester_gpa REAL NOT NULL DEFAULT 0.0,
  total_credits INTEGER NOT NULL DEFAULT 0,
  honors_available INTEGER NOT NULL DEFAULT 0,
  honors_used INTEGER NOT NULL DEFAULT 0,
  FOREIGN KEY(student_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS instructor_profiles (
  instructor_id INTEGER PRIMARY KEY,
  department TEXT DEFAULT 'General',
  avg_rating REAL NOT NULL DEFAULT 0.0,
  FOREIGN KEY(instructor_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS applications (
  application_id INTEGER PRIMARY KEY AUTOINCREMENT,
  applicant_email TEXT NOT NULL,
  role TEXT NOT NULL CHECK(role IN ('student','instructor')),
  status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','approved','rejected')),
  prior_gpa REAL DEFAULT 0.0,
  rejection_justification TEXT,
  decided_by INTEGER,
  FOREIGN KEY(decided_by) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS semesters (
  semester_id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  phase TEXT NOT NULL CHECK(phase IN ('setup','registration','running','grading','closed'))
);

CREATE TABLE IF NOT EXISTS courses (
  course_id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  credits INTEGER NOT NULL DEFAULT 3,
  is_required INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS class_sections (
  section_id INTEGER PRIMARY KEY AUTOINCREMENT,
  course_id INTEGER NOT NULL,
  semester_id INTEGER NOT NULL,
  instructor_id INTEGER,
  capacity INTEGER NOT NULL DEFAULT 30,
  enrolled_count INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','cancelled')),
  FOREIGN KEY(course_id) REFERENCES courses(course_id),
  FOREIGN KEY(semester_id) REFERENCES semesters(semester_id),
  FOREIGN KEY(instructor_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS enrollments (
  enrollment_id INTEGER PRIMARY KEY AUTOINCREMENT,
  student_id INTEGER NOT NULL,
  section_id INTEGER NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('enrolled','waitlisted','dropped','completed')),
  waitlist_position INTEGER,
  FOREIGN KEY(student_id) REFERENCES users(user_id),
  FOREIGN KEY(section_id) REFERENCES class_sections(section_id)
);

CREATE TABLE IF NOT EXISTS reviews (
  review_id INTEGER PRIMARY KEY AUTOINCREMENT,
  enrollment_id INTEGER NOT NULL,
  stars INTEGER NOT NULL CHECK(stars BETWEEN 1 AND 5),
  text TEXT NOT NULL,
  published INTEGER NOT NULL DEFAULT 1,
  taboo_count INTEGER NOT NULL DEFAULT 0,
  FOREIGN KEY(enrollment_id) REFERENCES enrollments(enrollment_id)
);

CREATE TABLE IF NOT EXISTS taboo_words (
  taboo_id INTEGER PRIMARY KEY AUTOINCREMENT,
  word TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS grade_records (
  grade_id INTEGER PRIMARY KEY AUTOINCREMENT,
  enrollment_id INTEGER NOT NULL,
  letter_grade TEXT NOT NULL,
  grade_points REAL NOT NULL,
  FOREIGN KEY(enrollment_id) REFERENCES enrollments(enrollment_id)
);

CREATE TABLE IF NOT EXISTS complaints (
  complaint_id INTEGER PRIMARY KEY AUTOINCREMENT,
  filed_by INTEGER NOT NULL,
  target_id INTEGER NOT NULL,
  description TEXT NOT NULL,
  requested_action TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','resolved')),
  resolution TEXT,
  resolved_by INTEGER,
  FOREIGN KEY(filed_by) REFERENCES users(user_id),
  FOREIGN KEY(target_id) REFERENCES users(user_id),
  FOREIGN KEY(resolved_by) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS warning_events (
  warning_id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  reason TEXT NOT NULL,
  source TEXT NOT NULL,
  FOREIGN KEY(user_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS ai_knowledge_documents (
  doc_id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  content TEXT NOT NULL,
  role_scope TEXT NOT NULL CHECK(role_scope IN ('public','student','instructor','registrar'))
);
