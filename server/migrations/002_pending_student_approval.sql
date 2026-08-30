ALTER TABLE students
  ADD COLUMN approval_status VARCHAR(20) NOT NULL DEFAULT 'approved'
  CHECK (approval_status IN ('pending', 'approved'));

CREATE INDEX students_approval_status_idx ON students (approval_status);
