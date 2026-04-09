# ClawTeam WSH Backend Functionality Verification Test

You are running a comprehensive end-to-end test of ClawTeam with the WSH (WaveShell) backend. This test validates ALL major functionality.

## Prerequisites

1. Verify wsh is installed: `wsh --version`
2. Verify clawteam is installed: `clawteam --version`
3. Set your leader identity:
   ```bash
   export CLAWTEAM_AGENT_ID="test-leader-001"
   export CLAWTEAM_AGENT_NAME="test-leader"
   export CLAWTEAM_AGENT_TYPE="leader"
   ```

---

## Test Scenario: Building a Simple Calculator

You are building a calculator application with multiple features. Use ClawTeam to coordinate 4 workers.

### Phase 1: Team Setup

1. Create a new team called `calc-test-wsh` with description "Building a calculator app with WSH backend"
2. Set the leader name to `test-leader`

### Phase 2: Task Creation with Dependencies

Create the following tasks in order:

**Task 1** (independent):
- Subject: "Add addition feature"
- Owner: `worker1`
- Description: "Create a function `add(a, b)` that returns the sum of two numbers. Save as `src/addition.py`. Include a docstring and error handling for non-numeric inputs."
- Acceptance criteria: Function exists, works correctly, handles errors

**Task 2** (independent):
- Subject: "Add subtraction feature"
- Owner: `worker2`
- Description: "Create a function `sub(a, b)` that returns the difference of two numbers. Save as `src/subtraction.py`. Include a docstring."
- Acceptance criteria: Function exists, works correctly

**Task 3** (independent):
- Subject: "Add multiplication feature"
- Owner: `worker3`
- Description: "Create a function `mul(a, b)` that returns the product of two numbers. Save as `src/multiplication.py`. Include a docstring."
- Acceptance criteria: Function exists, works correctly

**Task 4** (dependent on tasks 1, 2, 3):
- Subject: "Create calculator CLI"
- Owner: `worker4`
- Blocked by: Task IDs of tasks 1, 2, 3
- Description: "Create a CLI command-line interface that uses the three calculator functions. The CLI should accept arguments like `python3 calc.py add 5 3` and output the result. Save as `calc.py`."
- Acceptance criteria: CLI works, integrates all three functions, provides clear help

**Task 5** (dependent on task 4):
- Subject: "Write unit tests"
- Owner: `worker4`
- Blocked by: Task ID of task 4
- Description: "Write comprehensive unit tests for all calculator functions using pytest. Save as `tests/test_calc.py`. Include edge cases."
- Acceptance criteria: Tests pass, cover all functions

### Phase 3: Spawn Workers

Spawn 4 workers using the WSH backend with `--backend wsh` and `--skip-worktree` for speed:

**Worker 1**: `clawteam spawn --backend wsh --skip-worktree --team calc-test-wsh --agent-name worker1 --agent-type general-purpose --task "You are worker1. Check your tasks and complete them."`

**Worker 2**: `clawteam spawn --backend wsh --skip-worktree --team calc-test-wsh --agent-name worker2 --agent-type general-purpose --task "You are worker2. Check your tasks and complete them."`

**Worker 3**: `clawteam spawn --backend wsh --skip-worktree --team calc-test-wsh --agent-name worker3 --agent-type general-purpose --task "You are worker3. Check your tasks and complete them."`

**Worker 4**: `clawteam spawn --backend wsh --skip-worktree --team calc-test-wsh --agent-name worker4 --agent-type general-purpose --task "You are worker4. Check your tasks and complete them."`

### Phase 4: Monitor Progress

As the leader, continuously monitor progress:

1. **Check task board**: `clawteam board show calc-test-wsh`
2. **Check team status**: `clawteam team status calc-test-wsh`
3. **Check leader inbox**: `clawteam inbox receive calc-test-wsh --agent test-leader`

When a worker sends a message about task completion:
- Reply to acknowledge and provide feedback if needed
- Check if new tasks become unblocked
- Continue monitoring

### Phase 5: Task Dependency Verification

Verify that the dependency system is working:
1. Task 4 should NOT start until tasks 1, 2, 3 are all completed
2. Task 5 should NOT start until task 4 is completed
3. Observe the kanban board moving tasks through: pending → in_progress → completed

### Phase 6: Result Verification

Once all tasks are complete, verify:

**Artifacts created**:
```bash
ls -la ~/.clawteam/workspaces/calc-test-wsh/
```
Expected:
- `src/addition.py`
- `src/subtraction.py`
- `src/multiplication.py`
- `calc.py` (CLI)
- `tests/test_calc.py`

**Test the calculator CLI**:
```bash
python3 ~/.clawteam/workspaces/calc-test-wsh/worker4/calc.py add 5 3
python3 ~/.clawteam/workspaces/calc-test-wsh/worker4/calc.py sub 10 4
python3 ~/.clawteam/workspaces/calc-test-wsh/worker4/calc.py mul 6 7
```

### Phase 7: Cleanup

After verification, clean up:
```bash
clawteam team cleanup calc-test-wsh --force
```

---

## Functionality Checklist

Mark each item as ✅ PASS or ❌ FAIL after testing:

**Core Features**:
- [ ] Team creation with leader
- [ ] Task creation with owners
- [ ] Task dependencies (blocked-by)
- [ ] Worker spawn with WSH backend
- [ ] Task status updates (pending → in_progress → completed)
- [ ] Task blocking/unblocking

**Communication Features**:
- [ ] Worker sends messages to leader inbox
- [ ] Leader receives and can reply to messages
- [ ] Message timestamps and from field

**Visualization**:
- [ ] Kanban board shows correct task states
- [ ] Team status shows members and activity
- [ ] Task list with filtering

**Workspace**:
- [ ] Workers have their own workspace directories
- [ ] Files created by workers persist
- [ ] Workspace accessible post-execution

**Task Wait**:
- [ ] `clawteam task wait` blocks until completion
- [ ] Shows progress during wait
- [ ] Returns success when all complete

**Advanced Features** (if applicable):
- [ ] Task locking mechanism
- [ ] Cost tracking
- [ ] Session persistence
- [ ] Snapshots

---

## Success Criteria

The test is successful if:
1. All 5 tasks complete within reasonable time (under 5 minutes)
2. Dependency blocking works correctly (tasks 4,5 wait)
3. All expected files are created
4. Calculator CLI functions correctly
5. All checklist items pass

Report your findings in this format:

```
## Test Report

### Overall Status: [PASS/ FAIL]

### Tests Results:
- [Feature]: [PASS/FAIL] - [Notes]
...

### Issues Found:
- [Any bugs or unexpected behavior]

### Recommendations:
- [Suggestions for improvement]
```
