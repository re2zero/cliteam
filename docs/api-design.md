# ClawTeam RESTful API Design

## Overview

This document defines the RESTful API endpoints for the ClawTeam multi-agent coordination system. The API follows RESTful conventions and supports JSON for both requests and responses.

### Base URL

```
http://localhost:8080/api/v1
```

### Common Headers

```http
Content-Type: application/json
Accept: application/json
```

### Response Format

All responses follow this structure:

```json
{
  "success": true,
  "data": { ... },
  "error": null,
  "timestamp": "2026-03-27T12:00:00Z"
}
```

Error responses:

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "details": { ... }
  },
  "timestamp": "2026-03-27T12:00:00Z"
}
```

---

## Authentication (Future)

```
Authorization: Bearer <token>
```

---

## Teams API

### List All Teams

```http
GET /teams
```

**Query Parameters:**
| Parameter | Type   | Required | Description |
|-----------|--------|----------|-------------|
| user      | string | No       | Filter by user |

**Response:**

```json
{
  "teams": [
    {
      "name": "my-team",
      "description": "Building the auth module",
      "leadAgentId": "abc123",
      "memberCount": 5,
      "createdAt": "2026-03-27T10:00:00Z"
    }
  ]
}
```

### Get Team Details

```http
GET /teams/{team_name}
```

**Response:**

```json
{
  "name": "my-team",
  "description": "Building the auth module",
  "leadAgentId": "abc123",
  "createdAt": "2026-03-27T10:00:00Z",
  "members": [...],
  "stats": {
    "totalTasks": 10,
    "completedTasks": 5
  }
}
```

### Create Team

```http
POST /teams
```

**Request Body:**

```json
{
  "name": "new-team",
  "description": "Team description",
  "leaderName": "leader",
  "leaderId": "agent-id-here",
  "user": "optional-user"
}
```

### Update Team

```http
PATCH /teams/{team_name}
```

**Request Body:**

```json
{
  "description": "Updated description",
  "budgetCents": 10000
}
```

### Delete Team

```http
DELETE /teams/{team_name}?force=true
```

---

## Members API

### List Team Members

```http
GET /teams/{team_name}/members
```

**Response:**

```json
{
  "members": [
    {
      "name": "alice",
      "user": "",
      "agentId": "xyz789",
      "agentType": "general-purpose",
      "joinedAt": "2026-03-27T10:05:00Z"
    }
  ]
}
```

### Get Team Leader

```http
GET /teams/{team_name}/leader
```

**Response:**

```json
{
  "name": "leader",
  "agentId": "abc123",
  "agentType": "leader"
}
```

### Add Member to Team

```http
POST /teams/{team_name}/members
```

**Request Body:**

```json
{
  "name": "bob",
  "agentId": "def456",
  "agentType": "general-purpose",
  "user": "optional-user"
}
```

### Remove Member from Team

```http
DELETE /teams/{team_name}/members/{member_name}
```

---

## Tasks API

### List Tasks

```http
GET /teams/{team_name}/tasks
```

**Query Parameters:**
| Parameter     | Type          | Required | Description |
|---------------|---------------|----------|-------------|
| status        | TaskStatus    | No       | Filter by status (pending, in_progress, completed, blocked) |
| owner         | string        | No       | Filter by owner |
| priority      | TaskPriority  | No       | Filter by priority (low, medium, high, urgent) |
| sortByPriority| boolean       | No       | Sort by priority first |

**Response:**

```json
{
  "tasks": [
    {
      "id": "a1b2c3d4",
      "subject": "Implement OAuth2",
      "description": "Add OAuth2 authentication flow",
      "status": "pending",
      "priority": "high",
      "owner": "alice",
      "lockedBy": "",
      "createdAt": "2026-03-27T10:00:00Z",
      "updatedAt": "2026-03-27T10:00:00Z",
      "metadata": {}
    }
  ]
}
```

### Get Task

```http
GET /teams/{team_name}/tasks/{task_id}
```

### Create Task

```http
POST /teams/{team_name}/tasks
```

**Request Body:**

```json
{
  "subject": "Implement JWT auth",
  "description": "Add JWT token generation and validation",
  "owner": "bob",
  "priority": "high",
  "blockedBy": ["a1b2c3d4"],
  "metadata": {
    "estimated_hours": 4
  }
}
```

### Update Task

```http
PATCH /teams/{team_name}/tasks/{task_id}
```

**Request Body:**

```json
{
  "status": "in_progress",
  "owner": "alice",
  "caller": "alice"
}
```

Or set dependencies:

```json
{
  "addBlockedBy": ["a1b2c3d4"],
  "addBlocks": ["e5f6g7h8"]
}
```

### Delete Task

```http
DELETE /teams/{team_name}/tasks/{task_id}
```

### Get Task Statistics

```http
GET /teams/{team_name}/tasks/stats
```

**Response:**

```json
{
  "total": 10,
  "completed": 5,
  "in_progress": 2,
  "pending": 2,
  "blocked": 1,
  "timed_completed": 4,
  "avg_duration_seconds": 3600.5
}
```

### Wait for Tasks

```http
GET /teams/{team_name}/tasks/wait?task_ids=a1b2c3d4,e5f6g7h8&timeout=300
```

---

## Messages API

### Send Message

```http
POST /teams/{team_name}/messages
```

**Request Body:**

```json
{
  "from": "alice",
  "to": "leader",
  "type": "message",
  "content": "Task completed successfully",
  "requestId": "optional-custom-id"
}
```

Supported message types:
- `message` - Normal message
- `broadcast` - Broadcast to all members
- `join_request` - Request to join team
- `idle` - Report idle status
- `plan_approval_request` - Submit plan for approval
- `shutdown_request` - Request graceful shutdown

### Receive Messages

```http
GET /teams/{team_name}/messages/{agent_name}
```

**Query Parameters:**
| Parameter | Type    | Required | Description |
|-----------|---------|----------|-------------|
| limit     | integer | No       | Max messages (default: 10) |

**Response:**

```json
{
  "messages": [
    {
      "type": "message",
      "from": "leader",
      "to": "alice",
      "content": "Start working on the API design",
      "timestamp": "2026-03-27T11:00:00Z",
      "requestId": "req123456"
    }
  ]
}
```

### Peek Messages (Non-consumptive)

```http
GET /teams/{team_name}/messages/{agent_name}/peek
```

### Broadcast Message

```http
POST /teams/{team_name}/messages/broadcast
```

**Request Body:**

```json
{
  "from": "leader",
  "content": "Team meeting at 3pm",
  "exclude": ["bob"]
}
```

### Get Message Count

```http
GET /teams/{team_name}/messages/{agent_name}/count
```

### Get Event Log

```http
GET /teams/{team_name}/messages/events?limit=100
```

---

## Workspaces API

### List Workspaces

```http
GET /teams/{team_name}/workspaces
```

**Response:**

```json
{
  "workspaces": [
    {
      "agent": "alice",
      "path": "/path/to/worktree",
      "branch": "clawteam/my-team/alice",
      "status": "active"
    }
  ]
}
```

### Create Workspace

```http
POST /teams/{team_name}/workspaces/{agent_name}
```

### Get Workspace Status

```http
GET /teams/{team_name}/workspaces/{agent_name}
```

### Checkpoint Workspace

```http
POST /teams/{team_name}/workspaces/{agent_name}/checkpoint
```

**Request Body:**

```json
{
  "message": "Checkpoint: implemented auth flow"
}
```

### Merge Workspace

```http
POST /teams/{team_name}/workspaces/{agent_name}/merge
```

**Request Body:**

```json
{
  "targetBranch": "main",
  "message": "Merge Alice's work"
}
```

### Cleanup Workspace

```http
DELETE /teams/{team_name}/workspaces/{agent_name}
```

---

## Plans API

### Submit Plan

```http
POST /teams/{team_name}/plans
```

**Request Body:**

```json
{
  "from": "alice",
  "summary": "Implement REST API endpoints",
  "plan": "1. Design models\n2. Implement endpoints\n3. Add tests\n4. Documentation",
  "planFile": "/path/to/plan.md"
}
```

**Response:**

```json
{
  "planId": "plan123456"
}
```

### Approve Plan

```http
POST /teams/{team_name}/plans/{plan_id}/approve
```

**Request Body:**

```json
{
  "from": "leader",
  "feedback": "LGTM, proceed with implementation"
}
```

### Reject Plan

```http
POST /teams/{team_name}/plans/{plan_id}/reject
```

**Request Body:**

```json
{
  "from": "leader",
  "feedback": "Please reconsider the caching strategy"
}
```

### Get Pending Plans

```http
GET /teams/{team_name}/plans?status=pending
```

---

## Lifecycle API

### Request Shutdown

```http
POST /teams/{team_name}/lifecycle/shutdown/request
```

**Request Body:**

```json
{
  "agent": "alice",
  "reason": "All tasks completed"
}
```

**Response:**

```json
{
  "requestId": "shutdown123456"
}
```

### Approve Shutdown

```http
POST /teams/{team_name}/lifecycle/shutdown/approve/{request_id}
```

**Request Body:**

```json
{
  "agent": "leader"
}
```

### Reject Shutdown

```http
POST /teams/{team_name}/lifecycle/shutdown/reject/{request_id}
```

**Request Body:**

```json
{
  "agent": "leader",
  "reason": "Pending tasks must be completed first"
}
```

### Report Idle

```http
POST /teams/{team_name}/lifecycle/idle
```

**Request Body:**

```json
{
  "agent": "alice",
  "lastTask": "task-abc123",
  "status": "Waiting for new assignments"
}
```

### Get Team Status

```http
GET /teams/{team_name}/lifecycle/status
```

**Response:**

```json
{
  "members": [
    {
      "name": "alice",
      "status": "active",
      "lastSeen": "2026-03-27T12:00:00Z"
    }
  ],
  "overall": "active"
}
```

---

## Board/Monitoring API

### Get Board Overview

```http
GET /teams/{team_name}/board
```

**Response:**

```json
{
  "team": {
    "name": "my-team",
    "description": "Building the auth module"
  },
  "members": [...],
  "tasks": {
    "pending": [...],
    "in_progress": [...],
    "completed": [...],
    "blocked": [...]
  },
  "stats": {
    "totalTasks": 10,
    "completed": 5
  }
}
```

### Get Live Updates

```http
GET /teams/{team_name}/board/live
```

This endpoint supports Server-Sent Events (SSE) for real-time updates.

**Response (SSE stream):**

```
event: task_update
data: {"task": {...}, "change": "status", "old": "pending", "new": "in_progress"}

event: message
data: {"from": "alice", "content": "Done with task 1"}
```

### Get Agent Session Info

```http
GET /teams/{team_name}/agents/{agent_name}/session
```

---

## Config API

### Get Configuration

```http
GET /config
```

**Response:**

```json
{
  "data_dir": "/home/user/.clawteam",
  "transport": "file",
  "workspace": "auto",
  "default_backend": "tmux",
  "skip_permissions": true,
  "user": ""
}
```

### Update Configuration

```http
PATCH /config
```

**Request Body:**

```json
{
  "transport": "p2p",
  "user": "alice"
}
```

### Health Check

```http
GET /config/health
```

**Response:**

```json
{
  "healthy": true,
  "checks": {
    "data_dir": "ok",
    "tmux": "available",
    "git": "available"
  }
}
```

---

## Cost Tracking API

### Report Cost

```http
POST /teams/{team_name}/costs
```

**Request Body:**

```json
{
  "agent": "alice",
  "inputTokens": 5000,
  "outputTokens": 2000,
  "costCents": 15.5,
  "taskId": "task-abc123"
}
```

### Get Cost Summary

```http
GET /teams/{team_name}/costs/summary
```

**Query Parameters:**
| Parameter | Type   | Required | Description |
|-----------|--------|----------|-------------|
| agent     | string | No       | Filter by agent |
| task      | string | No       | Filter by task |

**Response:**

```json
{
  "totalInputTokens": 50000,
  "totalOutputTokens": 20000,
  "totalCents": 150.0,
  "byAgent": {
    "alice": {"input": 30000, "output": 10000, "cents": 90.0},
    "bob": {"input": 20000, "output": 10000, "cents": 60.0}
  }
}
```

---

## Profiles API

### List Profiles

```http
GET /profiles
```

### Get Profile

```http
GET /profiles/{profile_name}
```

### Create Profile

```http
POST /profiles
```

**Request Body:**

```json
{
  "name": "claude-kimi",
  "agent": "claude",
  "provider": "moonshot",
  "model": "claude-3-5-sonnet",
  "envVars": {
    "MOONSHOT_API_KEY": "your-key"
  }
}
```

### Test Profile

```http
POST /profiles/{profile_name}/test
```

---

## Presets API

### List Presets

```http
GET /presets
```

### Get Preset

```http
GET /presets/{preset_name}
```

### Generate Profile from Preset

```http
POST /presets/{preset_name}/generate-profile
```

**Request Body:**

```json
{
  "agent": "claude",
  "name": "my-custom-profile"
}
```

---

## Sessions API

### Save Session

```http
POST /teams/{team_name}/sessions
```

**Request Body:**

```json
{
  "sessionId": "session123456",
  "agent": "alice",
  "state": {...}
}
```

### List Sessions

```http
GET /teams/{team_name}/sessions
```

### Get Session

```http
GET /teams/{team_name}/sessions/{session_id}
```

### Delete Session

```http
DELETE /teams/{team_name}/sessions/{session_id}
```

---

## Webhooks API (Optional)

### Create Webhook

```http
POST /teams/{team_name}/webhooks
```

**Request Body:**

```json
{
  "url": "https://example.com/webhook",
  "events": ["task.created", "task.updated", "message.received"],
  "secret": "webhook-secret"
}
```

### List Webhooks

```http
GET /teams/{team_name}/webhooks
```

### Delete Webhook

```http
DELETE /teams/{team_name}/webhooks/{webhook_id}
```

---

## Error Codes

| Code   | Description                          |
|--------|--------------------------------------|
| 400    | Bad Request - Invalid input          |
| 401    | Unauthorized - Authentication failed |
| 404    | Not Found - Resource doesn't exist   |
| 409    | Conflict - Resource already exists   |
| 422    | Unprocessable Entity - Validation error |
| 423    | Locked - Resource is locked          |
| 500    | Internal Server Error               |
| TEAM_NOT_FOUND | Team does not exist           |
| MEMBER_NOT_FOUND | Member not in team          |
| TASK_NOT_FOUND | Task does not exist           |
| TASK_LOCKED | Task is locked by another agent |
| INVALID_DEPENDENCY | Circular dependency   |
| TRANSPORT_ERROR | Message delivery failed    |

---

## Rate Limiting (Future)

- Default: 100 requests per minute per IP
- Burst: 10 requests per second

Headers included in responses:
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1711536000
```

---

## Pagination

For list endpoints that support pagination:

**Query Parameters:**
- `page` (default: 1)
- `limit` (default: 50, max: 200)
- `cursor` - For cursor-based pagination

**Response:**

```json
{
  "items": [...],
  "pagination": {
    "page": 1,
    "limit": 50,
    "total": 150,
    "totalPages": 3,
    "nextCursor": "abc123"
  }
}
```
