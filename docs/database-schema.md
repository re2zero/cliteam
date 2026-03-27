# ClawTeam Database Schema Design

## Overview

This document defines the database schema for the ClawTeam multi-agent coordination system, supporting the RESTful API endpoints defined in [api-design.md](./api-design.md).

## Database Requirements

**Target Database:** PostgreSQL 14+
- Supports JSONB for flexible metadata storage
- Full-text search capabilities for task searching
- ACID compliance for data integrity
- Connection pooling for high concurrency

## Naming Conventions

- Tables: `snake_case`, plural nouns (e.g., `teams`, `team_members`)
- Columns: `snake_case`
- Primary Keys: `id` (UUID)
- Foreign Keys: `<table>_id`
- Timestamps: `created_at`, `updated_at`
- Soft Deletes: `deleted_at` (nullable)

---

## ER Diagram

```
┌─────────────────┐       ┌─────────────────┐
│     teams       │       │   team_members  │
├─────────────────┤       ├─────────────────┤
│ id (PK)         │◄──────│ id (PK)         │
│ name (UQ)       │       │ team_id (FK)    │
│ description    │       │ name (UQ)       │
│ lead_agent_id  │──────►│ user            │
│ created_at     │       │ agent_id (UQ)   │
│ updated_at     │       │ agent_type      │
│ deleted_at     │       │ joined_at       │
└─────────────────┘       │ status          │
                          │ last_seen_at    │
                          └─────────────────┘
                                   │
                                   │
                                   │
         ┌─────────────────────────┴─────────────────────────┐
         │                                                   │
         │                                                   │
┌─────────────────────┐                            ┌─────────────────────┐
│     tasks          │                            │    messages        │
├─────────────────────┤                            ├─────────────────────┤
│ id (PK)            │                            │ id (PK)            │
│ team_id (FK)    ───┼────────────────────────────────► team_id (FK)    │
│ subject            │                            │ type               │
│ description        │                            │ from_agent         │
│ status             │                            │ to_agent           │
│ priority           │                            │ content            │
│ owner              │                            │ request_id         │
│ locked_by          │                            │ timestamp          │
│ locked_at          │                            │ metadata (JSONB)  │
│ created_at         │                            │ read_at            │
│ updated_at         │                            └─────────────────────┘
│ started_at         │
│ completed_at       │                            ┌─────────────────────┐
│ metadata (JSONB)   │                            │     plans          │
└─────────────────────┘                            ├─────────────────────┤
                                                   │ id (PK)            │
                                                   │ team_id (FK)       │
            ┌──────────────────────────────────────┤ from_agent         │
            │                                      │ summary            │
            │                                      │ plan               │
            │                                      │ plan_file          │
            │                                      │ status             │
            │                                      │ feedback           │
            │                                      │ created_at         │
            │                                      │ updated_at         │
┌─────────────────────┐                            │ approved_at        │
│      costs         │                            │ rejected_at        │
├─────────────────────┤                            └─────────────────────┘
│ id (PK)            │
│ team_id (FK)       │                            ┌─────────────────────┐
│ agent              │◄─────────────────────────── │    sessions        │
│ task_id (FK)       │                            ├─────────────────────┤
│ input_tokens       │                            │ id (PK)            │
│ output_tokens      │                            │ team_id (FK)       │
│ cost_cents         │                            │ session_id (UQ)    │
│ reported_at        │                            │ agent              │
└─────────────────────┘                            │ state (JSONB)      │
                                                   │ created_at         │
                                                   │ updated_at         │
                                                   │ last_accessed_at   │
                                                   └─────────────────────┘

┌─────────────────────┐
│   workspaces       │                            ┌─────────────────────┐
├─────────────────────┤                            │   shutdown_reqs    │
│ id (PK)            │                            ├─────────────────────┤
│ team_id (FK)       │                            │ id (PK)            │
│ agent_name         │                            │ team_id (FK)       │
│ path               │                            │ agent              │
│ branch             │                            │ request_id (UQ)    │
│ status             │                            │ reason             │
│ status_since       │                            │ status             │
│ created_at         │                            │ created_at         │
│ updated_at         │                            │ updated_at         │
│ checkpoint_at      │                            │ processed_at       │
│ processed_by       │                            │ processed_by       │
└─────────────────────┘                            └─────────────────────┘

┌─────────────────────┐                            ┌─────────────────────┐
│    webhooks        │                            │   event_logs       │
├─────────────────────┤                            ├─────────────────────┤
│ id (PK)            │                            │ id (PK)            │
│ team_id (FK)       │                            │ team_id (FK)       │
│ url (UQ)           │                            │ event_type         │
│ events (JSONB)     │──┐                         │ entity_type        │
│ secret             │  │                         │ entity_id          │
│ created_at         │  │                         │ payload (JSONB)    │
│ updated_at         │  │                         │ created_at         │
│ active             │  │                         └─────────────────────┘
│ last_triggered_at  │  │
└─────────────────────┘  │
                          │
                          └──────────────────────────────► ┌─────────────────────┐
                                                          │  webhook_deliveries│
                                                          ├─────────────────────┤
                                                          │ id (PK)            │
                                                          │ webhook_id (FK)    │
                                                          │ event_type         │
                                                          │ payload (JSONB)    │
                                                          │ response_code      │
                                                          │ response_body      │
                                                          │ attempts           │
                                                          │ delivered_at       │
                                                          │ succeeded_at       │
                                                          └─────────────────────┘

┌─────────────────────┐
│    profiles        │
├─────────────────────┤
│ id (PK)            │
│ name (UQ)          │
│ agent              │
│ provider           │
│ model              │
│ config (JSONB)     │
│ last_tested_at     │
│ created_at         │
│ updated_at         │
└─────────────────────┘
```

---

## Table Definitions

### 1. teams

Stores team configuration and metadata.

```sql
CREATE TABLE teams (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL UNIQUE,
    description TEXT,
    lead_agent_id VARCHAR(64),
    budget_cents DECIMAL(12, 2) DEFAULT 0.00,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);

-- Indexes
CREATE INDEX idx_teams_name ON teams(name) WHERE deleted_at IS NULL;
CREATE INDEX idx_teams_leader ON teams(lead_agent_id) WHERE deleted_at IS NULL;

-- Trigger for updated_at
CREATE TRIGGER teams_updated_at
    BEFORE UPDATE ON teams
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

### 2. team_members

Stores agent membership information for each team.

```sql
CREATE TABLE team_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id UUID NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    user VARCHAR(255) DEFAULT '',
    agent_id VARCHAR(64) NOT NULL UNIQUE,
    agent_type VARCHAR(64) DEFAULT 'general-purpose',
    joined_at TIMESTAMPTZ DEFAULT NOW(),
    status VARCHAR(32) DEFAULT 'active', -- active, idle, shutdown
    last_seen_at TIMESTAMPTZ,
    UNIQUE(team_id, name),
    CONSTRAINT check_member_status CHECK (status IN ('active', 'idle', 'shutdown'))
);

-- Indexes
CREATE INDEX idx_team_members_team_id ON team_members(team_id);
CREATE INDEX idx_team_members_agent_id ON team_members(agent_id);
CREATE INDEX idx_team_members_status ON team_members(status);
CREATE INDEX idx_team_members_name ON team_members(name);

-- Full-text search for member lookup
CREATE INDEX idx_team_members_name_fts
    ON team_members USING gin(to_tsvector('english', name));
```

### 3. tasks

Stores task items with dependencies and metadata.

```sql
CREATE TABLE tasks (
    id VARCHAR(16) PRIMARY KEY, -- Short 8-char hex UUID
    team_id UUID NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    subject VARCHAR(500) NOT NULL,
    description TEXT,
    status VARCHAR(32) DEFAULT 'pending',
    priority VARCHAR(16) DEFAULT 'medium',
    owner VARCHAR(255) DEFAULT '',
    locked_by VARCHAR(255) DEFAULT '',
    locked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}',

    -- Dependency tracking
    blocks JSONB DEFAULT '[]',  -- Array of task IDs this task blocks
    blocked_by JSONB DEFAULT '[]', -- Array of task IDs blocking this task

    CONSTRAINT check_task_status
        CHECK (status IN ('pending', 'in_progress', 'completed', 'blocked', 'deleted')),
    CONSTRAINT check_task_priority
        CHECK (priority IN ('low', 'medium', 'high', 'urgent'))
);

-- Indexes
CREATE INDEX idx_tasks_team_id ON tasks(team_id);
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_owner ON tasks(owner);
CREATE INDEX idx_tasks_priority ON tasks(priority);
CREATE INDEX idx_tasks_created_at ON tasks(created_at DESC);

-- Full-text search for task description
CREATE INDEX idx_tasks_subject_fts
    ON tasks USING gin(to_tsvector('english', subject));

-- GIN index for metadata queries
CREATE INDEX idx_tasks_metadata ON tasks USING gin(metadata);

-- Composite index for dashboard queries
CREATE INDEX idx_tasks_dashboard ON tasks(team_id, status, priority)
    WHERE status != 'deleted';

-- Trigger for updated_at
CREATE TRIGGER tasks_updated_at
    BEFORE UPDATE ON tasks
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

### 4. messages

Stores inter-agent messages with mailbox semantics.

```sql
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id UUID NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    type VARCHAR(64) DEFAULT 'message',
    from_agent VARCHAR(255) NOT NULL,
    to_agent VARCHAR(255), -- NULL for broadcasts
    content TEXT,
    request_id VARCHAR(128),
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}',
    read_at TIMESTAMPTZ, -- When message was consumed
    key VARCHAR(128), -- For deduplication

    CONSTRAINT check_message_type
        CHECK (type IN (
            'message', 'broadcast', 'join_request',
            'join_approved', 'join_rejected',
            'plan_approval_request', 'plan_approved', 'plan_rejected',
            'shutdown_request', 'shutdown_approved', 'shutdown_rejected',
            'idle'
        ))
);

-- Indexes
CREATE INDEX idx_messages_team_id ON messages(team_id);
CREATE INDEX idx_messages_to_agent ON messages(team_id, to_agent) WHERE read_at IS NULL;
CREATE INDEX idx_messages_from_agent ON messages(team_id, from_agent);
CREATE INDEX idx_messages_type ON messages(type);
CREATE INDEX idx_messages_timestamp ON messages(timestamp DESC);
CREATE INDEX idx_messages_request_id ON messages(request_id);

-- GIN index for metadata
CREATE INDEX idx_messages_metadata ON messages USING gin(metadata);
```

### 5. plans

Stores approval workflow plans.

```sql
CREATE TABLE plans (
    id VARCHAR(16) PRIMARY KEY DEFAULT substr(md5(random()::text), 1, 12),
    team_id UUID NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    from_agent VARCHAR(255) NOT NULL,
    summary VARCHAR(500),
    plan TEXT,
    plan_file VARCHAR(1024),
    status VARCHAR(32) DEFAULT 'pending', -- pending, approved, rejected
    feedback TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    approved_at TIMESTAMPTZ,
    rejected_at TIMESTAMPTZ,
    approved_by VARCHAR(255),

    CONSTRAINT check_plan_status
        CHECK (status IN ('pending', 'approved', 'rejected'))
);

-- Indexes
CREATE INDEX idx_plans_team_id ON plans(team_id);
CREATE INDEX idx_plans_status ON plans(status);
CREATE INDEX idx_plans_agent ON plans(team_id, from_agent);

-- Trigger for updated_at
CREATE TRIGGER plans_updated_at
    BEFORE UPDATE ON plans
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

### 6. workspaces

Stores git worktree management information.

```sql
CREATE TABLE workspaces (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id UUID NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    agent_name VARCHAR(255) NOT NULL,
    path VARCHAR(1024) NOT NULL UNIQUE,
    branch VARCHAR(255),
    status VARCHAR(32) DEFAULT 'active', -- active, merged, stale
    status_since TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    checkpoint_at TIMESTAMPTZ,
    processed_at TIMESTAMPTZ,
    processed_by VARCHAR(255),
    metadata JSONB DEFAULT '{}',

    CONSTRAINT check_workspace_status
        CHECK (status IN ('active', 'merged', 'stale'))
);

-- Indexes
CREATE INDEX idx_workspaces_team_id ON workspaces(team_id);
CREATE INDEX idx_workspaces_agent ON workspaces(team_id, agent_name);
CREATE INDEX idx_workspaces_status ON workspaces(status);
CREATE INDEX idx_workspaces_branch ON workspaces(branch);

-- Trigger for updated_at
CREATE TRIGGER workspaces_updated_at
    BEFORE UPDATE ON workspaces
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

### 7. sessions

Stores agent session state for recovery.

```sql
CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id UUID NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    session_id VARCHAR(64) NOT NULL UNIQUE,
    agent VARCHAR(255) NOT NULL,
    state JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_accessed_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(team_id, session_id, agent)
);

-- Indexes
CREATE INDEX idx_sessions_team_id ON sessions(team_id);
CREATE INDEX idx_sessions_agent ON sessions(team_id, agent);
CREATE INDEX idx_sessions_session_id ON sessions(session_id);
-- Cleanup sessions older than 30 days
CREATE INDEX idx_sessions_last_accessed ON sessions(last_accessed_at);

-- Trigger for updated_at and last_accessed_at
CREATE TRIGGER sessions_updated_at
    BEFORE UPDATE ON sessions
    FOR EACH ROW EXECUTE FUNCTION
    BEGIN
        NEW.updated_at = NOW();
        NEW.last_accessed_at = NOW();
    END;
```

### 8. costs

Tracks agent costs for billing and analytics.

```sql
CREATE TABLE costs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id UUID NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    agent VARCHAR(255) NOT NULL,
    task_id VARCHAR(16),
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    cost_cents DECIMAL(10, 4) DEFAULT 0.00,
    reported_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

-- Indexes
CREATE INDEX idx_costs_team_id ON costs(team_id);
CREATE INDEX idx_costs_agent ON costs(team_id, agent);
CREATE INDEX idx_costs_task_id ON costs(task_id);
CREATE INDEX idx_costs_reported_at ON costs(reported_at DESC);

-- Composite index for summary queries
CREATE INDEX idx_costs_summary ON costs(team_id, agent, reported_at);
```

### 9. shutdown_requests

Handles graceful shutdown workflow.

```sql
CREATE TABLE shutdown_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id UUID NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    agent VARCHAR(255) NOT NULL,
    request_id VARCHAR(64) NOT NULL UNIQUE,
    reason TEXT,
    status VARCHAR(32) DEFAULT 'pending', -- pending, approved, rejected
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    processed_at TIMESTAMPTZ,
    processed_by VARCHAR(255),
    reject_reason TEXT,

    CONSTRAINT check_shutdown_status
        CHECK (status IN ('pending', 'approved', 'rejected'))
);

-- Indexes
CREATE INDEX idx_shutdown_team_id ON shutdown_requests(team_id);
CREATE INDEX idx_shutdown_request_id ON shutdown_requests(request_id);
CREATE INDEX idx_shutdown_status ON shutdown_requests(status);

-- Trigger for updated_at
CREATE TRIGGER shutdown_requests_updated_at
    BEFORE UPDATE ON shutdown_requests
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

### 10. event_logs

Audit log for all team events.

```sql
CREATE TABLE event_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id UUID NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    event_type VARCHAR(64) NOT NULL,
    entity_type VARCHAR(64), -- task, member, message, etc.
    entity_id VARCHAR(255),
    payload JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    agent VARCHAR(255)
);

-- Indexes
CREATE INDEX idx_event_logs_team_id ON event_logs(team_id);
CREATE INDEX idx_event_logs_event_type ON event_logs(event_type);
CREATE INDEX idx_event_logs_entity ON event_logs(team_id, entity_type, entity_id);
CREATE INDEX idx_event_logs_created_at ON event_logs(created_at DESC);

-- GIN index for payload
CREATE INDEX idx_event_logs_payload ON event_logs USING gin(payload);
```

### 11. webhooks

Webhook configuration for external integrations.

```sql
CREATE TABLE webhooks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id UUID NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    events JSONB NOT NULL DEFAULT '[]', -- Array of event types
    secret VARCHAR(255),
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_triggered_at TIMESTAMPTZ,

    UNIQUE(team_id, url)
);

-- Indexes
CREATE INDEX idx_webhooks_team_id ON webhooks(team_id);
CREATE INDEX idx_webhooks_active ON webhooks(active);

-- Trigger for updated_at
CREATE TRIGGER webhooks_updated_at
    BEFORE UPDATE ON webhooks
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

### 12. webhook_deliveries

Webhook delivery tracking with retry support.

```sql
CREATE TABLE webhook_deliveries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    webhook_id UUID NOT NULL REFERENCES webhooks(id) ON DELETE CASCADE,
    event_type VARCHAR(64) NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}',
    response_code INTEGER,
    response_body TEXT,
    attempts INTEGER DEFAULT 0,
    delivered_at TIMESTAMPTZ DEFAULT NOW(),
    succeeded_at TIMESTAMPTZ,
    next_retry_at TIMESTAMPTZ
);

-- Indexes
CREATE INDEX idx_webhook_deliveries_webhook_id ON webhook_deliveries(webhook_id);
CREATE INDEX idx_webhook_deliveries_next_retry ON webhook_deliveries(next_retry_at)
    WHERE succeeded_at IS NULL;
CREATE INDEX idx_webhook_deliveries_event_type ON webhook_deliveries(event_type);
```

### 13. profiles

Agent profile configurations (global, not team-specific).

```sql
CREATE TABLE profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL UNIQUE,
    agent VARCHAR(64) NOT NULL, -- claude, openai, etc.
    provider VARCHAR(64),
    model VARCHAR(255),
    config JSONB NOT NULL DEFAULT '{}', -- env_vars, settings
    last_tested_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_profiles_name ON profiles(name);
CREATE INDEX idx_profiles_agent ON profiles(agent);

-- Trigger for updated_at
CREATE TRIGGER profiles_updated_at
    BEFORE UPDATE ON profiles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

---

## Common Functions

### Updated At Trigger Function

```sql
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';
```

---

## Views

### Task Statistics View

```sql
CREATE OR REPLACE VIEW task_statistics AS
SELECT
    team_id,
    COUNT(*) as total,
    COUNT(*) FILTER (WHERE status = 'pending') as pending,
    COUNT(*) FILTER (WHERE status = 'in_progress') as in_progress,
    COUNT(*) FILTER (WHERE status = 'completed') as completed,
    COUNT(*) FILTER (WHERE status = 'blocked') as blocked,
    COUNT(*) FILTER (WHERE status = 'completed' AND completed_at IS NOT NULL) as timed_completed,
    AVG(EXTRACT(EPOCH FROM (completed_at - started_at))) FILTER (
        WHERE completed_at IS NOT NULL AND started_at IS NOT NULL
    ) as avg_duration_seconds
FROM tasks
WHERE status != 'deleted'
GROUP BY team_id;
```

### Teams with Members View

```sql
CREATE OR REPLACE VIEW teams_with_members AS
SELECT
    t.id,
    t.name,
    t.description,
    t.lead_agent_id,
    t.created_at,
    m.member_count,
    ts.total_tasks,
    ts.completed_tasks
FROM teams t
LEFT JOIN LATERAL (
    SELECT COUNT(*) as member_count
    FROM team_members tm
    WHERE tm.team_id = t.id
) m ON TRUE
LEFT JOIN LATERAL (
    SELECT COUNT(*) as total_tasks,
           COUNT(*) FILTER (WHERE status = 'completed') as completed_tasks
    FROM tasks task
    WHERE task.team_id = t.id AND task.status != 'deleted'
) ts ON TRUE
WHERE t.deleted_at IS NULL;
```

---

## Stored Procedures

### Create Team with Leader

```sql
CREATE OR REPLACE PROCEDURE create_team_with_leader(
    p_name VARCHAR(255),
    p_description TEXT DEFAULT '',
    p_leader_name VARCHAR(255),
    p_leader_agent_id VARCHAR(64),
    p_leader_agent_type VARCHAR(64) DEFAULT 'leader'
)
LANGUAGE plpgsql AS $$
DECLARE
    v_team_id UUID;
    v_member_id UUID;
BEGIN
    -- Create team
    INSERT INTO teams (name, description, lead_agent_id)
    VALUES (p_name, p_description, p_leader_agent_id)
    RETURNING id INTO v_team_id;

    -- Add leader as member
    INSERT INTO team_members (
        team_id, name, agent_id, agent_type, status
    ) VALUES (
        v_team_id, p_leader_name, p_leader_agent_id,
        p_leader_agent_type, 'active'
    ) RETURNING id INTO v_member_id;

    RAISE NOTICE 'Team % created with leader % (member_id: %)', v_team_id, p_leader_name, v_member_id;
END;
$$;
```

### Get Tasks with Dependencies Resolved

```sql
CREATE OR REPLACE FUNCTION get_tasks_with_dependencies(
    p_team_id UUID,
    p_status VARCHAR DEFAULT NULL
)
RETURNS TABLE (
    task_id VARCHAR,
    subject VARCHAR,
    description TEXT,
    status VARCHAR,
    priority VARCHAR,
    owner VARCHAR,
    created_at TIMESTAMPTZ,
    is_blocked BOOLEAN,
    blocked_by_names TEXT[]
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        t.id,
        t.subject,
        t.description,
        t.status,
        t.priority,
        t.owner,
        t.created_at,
        CASE WHEN jsonb_array_length(t.blocked_by) > 0 THEN TRUE ELSE FALSE END as is_blocked,
        ARRAY(
            SELECT m.name
            FROM jsonb_array_elements_text(t.blocked_by) AS task_id
            JOIN tasks t2 ON t2.id = task_id
            JOIN team_members m ON m.agent_id = t2.owner
        ) as blocked_by_names
    FROM tasks t
    WHERE t.team_id = p_team_id
      AND (p_status IS NULL OR t.status = p_status)
      AND t.status != 'deleted'
    ORDER BY
        CASE t.priority
            WHEN 'urgent' THEN 1
            WHEN 'high' THEN 2
            WHEN 'medium' THEN 3
            WHEN 'low' THEN 4
        END,
        t.created_at;
END;
$$ LANGUAGE plpgsql;
```

### cleanup_old_sessions

```sql
CREATE OR REPLACE PROCEDURE cleanup_old_sessions(p_days INTEGER DEFAULT 30)
LANGUAGE plpgsql AS $$
BEGIN
    DELETE FROM sessions
    WHERE last_accessed_at < NOW() - (p_days || ' days')::INTERVAL;
    RAISE NOTICE 'Deleted % old sessions', ROW_COUNT;
END;
$$;
```

---

## Migration Strategy

### Initial Setup Script

```sql
-- Run once to set up the database

BEGIN;

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For trigram matching

-- Create updated_at trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create all tables in order
-- (Tables defined above)

-- Create indexes
-- (Indexes defined above)

-- Create views
-- (Views defined above)

-- Create procedures
-- (Procedures defined above)

COMMIT;
```

---

## Performance Considerations

### Connection Pooling

- Use PgBouncer or similar for production
- Recommended pool size: 20-50 connections per server

### Partitioning

For high-volume teams (>1M tasks), consider partitioning `tasks` table:

```sql
-- Example: Partition tasks by team_id
CREATE TABLE tasks (
    -- Column definitions
) PARTITION BY HASH (team_id);

-- Create partitions
CREATE TABLE tasks_p0 PARTITION OF tasks FOR VALUES WITH (MODULUS 4, REMAINDER 0);
CREATE TABLE tasks_p1 PARTITION OF tasks FOR VALUES WITH (MODULUS 4, REMAINDER 1);
CREATE TABLE tasks_p2 PARTITION OF tasks FOR VALUES WITH (MODULUS 4, REMAINDER 2);
CREATE TABLE tasks_p3 PARTITION OF tasks FOR VALUES WITH (MODULUS 4, REMAINDER 3);
```

### Caching

- Cache team metadata in Redis with TTL 300s
- Cache task lists with conditional ETag headers
- Use PostgreSQL prepared statements

### Monitoring

Set up queries for monitoring:

```sql
-- Connection count
SELECT count(*) FROM pg_stat_activity WHERE datname = current_database();

-- Table sizes
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename))
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Slow queries
SELECT query, mean_exec_time, calls
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;
```

---

## Security

### Row-Level Security (RLS)

Enable RLS for team isolation:

```sql
-- Enable RLS on team-related tables
ALTER TABLE teams ENABLE ROW LEVEL SECURITY;
ALTER TABLE team_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;

-- Policy: Only members can see their team's data
CREATE POLICY team_members_policy ON team_members
    USING (
        team_id IN (
            SELECT team_id FROM team_members WHERE agent_id = current_setting('app.agent_id')
        )
    );
```

### Audit Logging

`event_logs` table provides comprehensive audit trail of all system events.

---

## Backup and Recovery

### Backup Strategy

```bash
# Full backup
pg_dump -h localhost -U clawteam -d clawteam > backup_$(date +%Y%m%d).sql

# Schema only
pg_dump -h localhost -U clawteam -d clawteam --schema-only > schema.sql

-- Point-in-time recovery requires WAL archiving
```

### Critical Tables for Backup

1. `teams` - Core team configuration
2. `tasks` - All task data
3. `messages` - Communication history
4. `event_logs` - Audit trail

---

## Testing Schema

### Sample Data Insertion

```sql
-- Create test team
CALL create_team_with_leader(
    'test-team',
    'A test team for unit testing',
    'leader',
    'leader-abc123',
    'leader'
);

-- Add test members
INSERT INTO team_members (team_id, name, agent_id, agent_type)
VALUES
    ((SELECT id FROM teams WHERE name = 'test-team'), 'alice', 'alice-def456', 'general-purpose'),
    ((SELECT id FROM teams WHERE name = 'test-team'), 'bob', 'bob-ghi789', 'general-purpose');

-- Add test tasks
INSERT INTO tasks (id, team_id, subject, description, owner, priority)
VALUES
    ('abc12345', (SELECT id FROM teams WHERE name = 'test-team'), 'Write tests', 'Write unit tests for API', 'alice', 'high'),
    ('def67890', (SELECT id FROM teams WHERE name = 'test-team'), 'Design DB', 'Design database schema', 'bob', 'high'),
    ('ghi13579', (SELECT id FROM teams WHERE name = 'test-team'), 'Implement API', 'Implement REST endpoints', 'alice', 'medium');

-- Add task dependency (ghi13579 blocked by def67890)
UPDATE tasks SET blocked_by = '["def67890"]' WHERE id = 'ghi13579';
UPDATE tasks SET blocks = '["ghi13579"]' WHERE id = 'def67890';
```

---

## API Mapping

| API Endpoint | Supported Tables |
|-------------|------------------|
| `GET/POST/PATCH/DELETE /teams` | `teams` |
| `GET/POST/DELETE /teams/{team}/members` | `team_members` |
| `GET/POST/PATCH/DELETE /teams/{team}/tasks` | `tasks`, `task_statistics` (via view) |
| `GET/POST /teams/{team}/messages` | `messages` |
| `POST /teams/{team}/plans` | `plans` |
| `GET/POST /teams/{team}/workspaces` | `workspaces` |
| `GET/POST /teams/{team}/sessions` | `sessions` |
| `POST /teams/{team}/costs` | `costs` |
| `POST /teams/{team}/lifecycle/*` | `shutdown_requests`, `team_members` |
| `GET /teams/{team}/board` | `teams`, `team_members`, `tasks` via views |
| `GET/POST /teams/{team}/webhooks` | `webhooks`, `webhook_deliveries` |
| `GET/POST/DELETE /profiles` | `profiles` |
| `GET /teams/{team}/messages/events` | `event_logs` |

---

## Notes

1. **JSONB Fields**: All metadata fields use JSONB for extensibility. This allows future API additions without schema changes.

2. **Soft Deletes**: `teams`, `tasks` tables use `deleted_at` for soft deletion. Other tables use hard deletion via foreign key CASCADE.

3. **Task Dependencies**: The `blocked_by` and `blocks` fields in `tasks` store JSONB arrays of task IDs for efficient circular dependency checking.

4. **Message Ordering**: Messages are ordered by timestamp descending for recent-first display.

5. **Timezone**: All timestamps use `TIMESTAMPTZ` (timezone-aware) and default to UTC.

6. **UUID Handling**: PostgreSQL's `gen_random_uuid()` is used for primary keys, while tasks use short 8-char hex IDs for API readability.

7. **Full-Text Search**: GIN indexes on member names and task subjects enable fast search functionality.

8. **Event Ordering**: Event logs append only - no updates, enabling efficient tail queries for real-time monitoring.
