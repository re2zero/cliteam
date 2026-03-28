# ClawTeam Coordination Workflows

## Join Request Protocol

```bash
# Agent requests to join (blocks until response)
clawteam team request-join dev-team bob --capabilities "frontend specialist" --timeout 120

# Leader checks inbox and approves
clawteam inbox peek dev-team --agent leader
clawteam team approve-join dev-team join-abc123
```

## Plan Approval Flow

```bash
# Worker submits plan (inline text or file path)
clawteam plan submit dev-team coder "1. Refactor auth\n2. Add OAuth2" --summary "Auth upgrade"
# Leader reviews and decides
clawteam plan approve dev-team <plan-id> coder --feedback "Looks good"
# or: clawteam plan reject dev-team <plan-id> coder --feedback "Add error handling"
```

## Graceful Shutdown

```bash
clawteam lifecycle request-shutdown dev-team leader coder --reason "All tasks complete"
# Worker finishes current work, then:
clawteam lifecycle approve-shutdown dev-team shut-xyz coder
# Leader cleans up
clawteam team cleanup dev-team --force
```

## Worker Loop Protocol

Workers must not exit after the first task. Expected loop:

```bash
clawteam task list my-team --owner worker1       # check assigned tasks
clawteam inbox receive my-team --agent worker1    # check instructions
# ... do work, update task status ...
clawteam lifecycle idle my-team                   # notify leader when idle
```

Repeat until leader explicitly shuts the worker down.

## Monitoring

```bash
clawteam board overview                           # all teams summary
clawteam board show dev-team                      # kanban + messages
clawteam board live dev-team --interval 3         # auto-refresh
clawteam --json task list dev-team --status blocked | jq '.[].subject'
```
