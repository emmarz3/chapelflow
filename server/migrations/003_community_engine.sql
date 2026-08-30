ALTER TABLE users DROP CONSTRAINT IF EXISTS users_role_check;
ALTER TABLE users ADD CONSTRAINT users_role_check CHECK (
  role IN (
    'super_admin', 'chapel_admin', 'chaplain', 'student_chaplain',
    'treasurer', 'chapel_official', 'pastor', 'worker',
    'attendance_usher', 'member'
  )
);

CREATE TABLE user_global_roles (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  role_key VARCHAR(40) NOT NULL CHECK (
    role_key IN (
      'super_admin', 'chapel_admin', 'chaplain', 'student_chaplain',
      'treasurer', 'chapel_official', 'pastor', 'worker',
      'attendance_usher', 'member'
    )
  ),
  assigned_by UUID REFERENCES users(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (user_id, role_key)
);
CREATE INDEX user_global_roles_user_idx ON user_global_roles (user_id);

CREATE TABLE communities (
  id UUID PRIMARY KEY,
  name VARCHAR(160) NOT NULL UNIQUE,
  slug VARCHAR(120) NOT NULL UNIQUE CHECK (slug = LOWER(slug)),
  type VARCHAR(32) NOT NULL CHECK (type IN ('unit', 'campus_fellowship', 'hostel_fellowship', 'other')),
  description TEXT NOT NULL DEFAULT '',
  status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive')),
  requires_approval BOOLEAN NOT NULL DEFAULT TRUE,
  members_can_post BOOLEAN NOT NULL DEFAULT TRUE,
  chat_enabled BOOLEAN NOT NULL DEFAULT TRUE,
  created_by UUID REFERENCES users(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX communities_type_status_idx ON communities (type, status, name);

CREATE TABLE community_memberships (
  id UUID PRIMARY KEY,
  community_id UUID NOT NULL REFERENCES communities(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  status VARCHAR(20) NOT NULL CHECK (status IN ('pending', 'active', 'rejected', 'suspended', 'left')),
  is_primary BOOLEAN NOT NULL DEFAULT FALSE,
  joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  approved_at TIMESTAMPTZ,
  approved_by UUID REFERENCES users(id) ON DELETE SET NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (user_id, community_id)
);
CREATE INDEX community_memberships_user_status_idx ON community_memberships (user_id, status, community_id);
CREATE INDEX community_memberships_community_status_idx ON community_memberships (community_id, status, joined_at DESC);

CREATE TABLE leadership_positions (
  id UUID PRIMARY KEY,
  name VARCHAR(160) NOT NULL,
  scope_type VARCHAR(24) NOT NULL CHECK (scope_type IN ('global', 'community')),
  capabilities JSONB NOT NULL DEFAULT '[]'::JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (name, scope_type)
);

CREATE TABLE leadership_assignments (
  id UUID PRIMARY KEY,
  position_id UUID NOT NULL REFERENCES leadership_positions(id) ON DELETE RESTRICT,
  user_id UUID REFERENCES users(id) ON DELETE SET NULL,
  assignee_name VARCHAR(160),
  community_id UUID REFERENCES communities(id) ON DELETE CASCADE,
  starts_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  ends_at TIMESTAMPTZ,
  active BOOLEAN NOT NULL DEFAULT TRUE,
  assigned_by UUID REFERENCES users(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CHECK (user_id IS NOT NULL OR assignee_name IS NOT NULL),
  CHECK (ends_at IS NULL OR ends_at >= starts_at)
);
CREATE INDEX leadership_assignments_user_active_idx ON leadership_assignments (user_id, active);
CREATE INDEX leadership_assignments_community_active_idx ON leadership_assignments (community_id, active, position_id);

CREATE TABLE conversations (
  id UUID PRIMARY KEY,
  community_id UUID NOT NULL REFERENCES communities(id) ON DELETE CASCADE,
  type VARCHAR(24) NOT NULL DEFAULT 'community' CHECK (type IN ('community', 'leadership')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (community_id, type)
);

CREATE TABLE messages (
  id UUID PRIMARY KEY,
  conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  sender_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  body TEXT NOT NULL CHECK (body <> ''),
  reply_to_id UUID REFERENCES messages(id) ON DELETE SET NULL,
  pinned BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  edited_at TIMESTAMPTZ,
  deleted_at TIMESTAMPTZ
);
CREATE INDEX messages_conversation_created_idx ON messages (conversation_id, created_at DESC, id);

CREATE TABLE conversation_read_states (
  conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  last_read_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (conversation_id, user_id)
);

CREATE TABLE announcements (
  id UUID PRIMARY KEY,
  community_id UUID REFERENCES communities(id) ON DELETE CASCADE,
  author_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  title VARCHAR(180) NOT NULL,
  content TEXT NOT NULL CHECK (content <> ''),
  pinned BOOLEAN NOT NULL DEFAULT FALSE,
  priority VARCHAR(20) NOT NULL DEFAULT 'normal' CHECK (priority IN ('normal', 'important', 'urgent')),
  published_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  expires_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX announcements_community_created_idx ON announcements (community_id, published_at DESC);

CREATE TABLE community_events (
  id UUID PRIMARY KEY,
  community_id UUID NOT NULL REFERENCES communities(id) ON DELETE CASCADE,
  title VARCHAR(180) NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  venue VARCHAR(240) NOT NULL,
  starts_at TIMESTAMPTZ NOT NULL,
  ends_at TIMESTAMPTZ NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'upcoming' CHECK (status IN ('upcoming', 'ongoing', 'completed', 'cancelled')),
  created_by UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CHECK (ends_at > starts_at)
);
CREATE INDEX community_events_community_start_idx ON community_events (community_id, starts_at DESC);

CREATE TABLE notifications (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  community_id UUID REFERENCES communities(id) ON DELETE CASCADE,
  type VARCHAR(60) NOT NULL,
  title VARCHAR(180) NOT NULL,
  body TEXT NOT NULL,
  href TEXT,
  read_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX notifications_user_unread_idx ON notifications (user_id, read_at, created_at DESC);

CREATE TABLE account_setup_tokens (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash CHAR(64) NOT NULL UNIQUE,
  expires_at TIMESTAMPTZ NOT NULL,
  used_at TIMESTAMPTZ,
  created_by UUID REFERENCES users(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX account_setup_tokens_user_idx ON account_setup_tokens (user_id, expires_at DESC);
