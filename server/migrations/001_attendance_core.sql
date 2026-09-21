CREATE TABLE IF NOT EXISTS schema_migrations (
  name TEXT PRIMARY KEY,
  applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE users (
  id UUID PRIMARY KEY,
  username VARCHAR(80) NOT NULL UNIQUE CHECK (username = LOWER(username)),
  email VARCHAR(320) NOT NULL UNIQUE CHECK (email = LOWER(email)),
  password_hash TEXT NOT NULL,
  full_name VARCHAR(160) NOT NULL,
  role VARCHAR(32) NOT NULL CHECK (role IN ('super_admin', 'chapel_admin', 'pastor', 'worker', 'attendance_usher', 'member')),
  status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'locked')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE students (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
  matric_number VARCHAR(80) NOT NULL UNIQUE,
  programme VARCHAR(160),
  academic_level VARCHAR(40),
  photo_url TEXT,
  qr_pass_id UUID NOT NULL UNIQUE,
  pass_status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (pass_status IN ('active', 'revoked')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE attendance_sessions (
  id UUID PRIMARY KEY,
  title VARCHAR(180) NOT NULL,
  service_type VARCHAR(80) NOT NULL,
  service_date DATE NOT NULL,
  starts_at TIMESTAMPTZ NOT NULL,
  ends_at TIMESTAMPTZ NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'scheduled' CHECK (status IN ('scheduled', 'active', 'closed')),
  created_by UUID NOT NULL REFERENCES users(id),
  opened_at TIMESTAMPTZ,
  closed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CHECK (ends_at > starts_at)
);

CREATE UNIQUE INDEX attendance_sessions_one_active_idx
  ON attendance_sessions ((status)) WHERE status = 'active';
CREATE INDEX attendance_sessions_date_idx ON attendance_sessions (service_date DESC);
CREATE INDEX attendance_sessions_status_idx ON attendance_sessions (status);

CREATE TABLE attendance_records (
  id UUID PRIMARY KEY,
  attendance_session_id UUID NOT NULL REFERENCES attendance_sessions(id) ON DELETE RESTRICT,
  student_id UUID NOT NULL REFERENCES students(id) ON DELETE RESTRICT,
  recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  recorded_by_usher_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  method VARCHAR(20) NOT NULL CHECK (method IN ('qr_scan', 'manual', 'admin_override')),
  scanner_metadata JSONB NOT NULL DEFAULT '{}'::JSONB,
  status VARCHAR(20) NOT NULL DEFAULT 'present' CHECK (status IN ('present', 'late', 'excused')),
  exception_reason TEXT,
  idempotency_key UUID,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT attendance_records_session_student_unique UNIQUE (attendance_session_id, student_id),
  CONSTRAINT attendance_records_actor_idempotency_unique UNIQUE (recorded_by_usher_id, idempotency_key)
);

CREATE INDEX attendance_records_session_time_idx
  ON attendance_records (attendance_session_id, recorded_at DESC);
CREATE INDEX attendance_records_student_time_idx
  ON attendance_records (student_id, recorded_at DESC);

CREATE TABLE auth_sessions (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash CHAR(64) NOT NULL UNIQUE,
  expires_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX auth_sessions_user_idx ON auth_sessions (user_id);
CREATE INDEX auth_sessions_expiry_idx ON auth_sessions (expires_at);

CREATE TABLE audit_events (
  id UUID PRIMARY KEY,
  actor_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
  action VARCHAR(100) NOT NULL,
  entity_type VARCHAR(80) NOT NULL,
  entity_id UUID,
  metadata JSONB NOT NULL DEFAULT '{}'::JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX audit_events_entity_idx ON audit_events (entity_type, entity_id, created_at DESC);
CREATE INDEX audit_events_actor_idx ON audit_events (actor_user_id, created_at DESC);
