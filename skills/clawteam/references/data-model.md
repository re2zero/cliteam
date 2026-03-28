# ClawTeam Data Model Reference

## Task Statuses

| Status | Description |
|--------|-------------|
| `pending` | Not yet started |
| `in_progress` | Currently being worked on |
| `completed` | Done (auto-unblocks dependents) |
| `blocked` | Waiting on other tasks (auto-set via `--blocked-by`) |

## Message Types

| Type | Description |
|------|-------------|
| `message` | Point-to-point |
| `broadcast` | To all members |
| `join_request` / `join_approved` / `join_rejected` | Join protocol |
| `plan_approval_request` / `plan_approved` / `plan_rejected` | Plan review |
| `shutdown_request` / `shutdown_approved` / `shutdown_rejected` | Shutdown |
| `idle` | Agent idle notification |

## File Storage Layout

```
~/.clawteam/
├── teams/{team}/
│   ├── config.json          # TeamConfig (name, members, leader)
│   └── inboxes/{agent}/     # msg-{timestamp}-{uuid}.json files
├── tasks/{team}/
│   └── task-{id}.json       # Individual task files
└── plans/
    └── {agent}-{id}.md      # Plan documents
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `CLAWTEAM_AGENT_ID` | Unique agent identifier |
| `CLAWTEAM_AGENT_NAME` | Human-readable name |
| `CLAWTEAM_AGENT_TYPE` | Role: `leader`, `general-purpose`, `researcher` |
| `CLAWTEAM_TEAM_NAME` | Team name |
| `CLAWTEAM_DATA_DIR` | Override data directory (default: `~/.clawteam`) |

For CLI usage, run `clawteam <command> --help` for full options and examples.
