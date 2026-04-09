# 场景一：并行 BUG 修复 - 测试提示词文档

## 测试目标

验证 ClawTeam 与 Trellis 结合实现并行 BUG 修复的完整流程。

---

## 测试环境准备

```bash
# 1. 克隆测试仓库
git clone https://github.com/test/bug-repo.git
cd bug-repo

# 2. 切换到包含 BUG 的分支
git checkout buggy-branch

# 3. 验证 BUG 存在
pytest tests/  # 应该有 5-10 个失败的测试

# 4. 初始化 Leader 身份
export CLAWTEAM_AGENT_ID="test-leader-001"
export CLAWTEAM_AGENT_NAME="leader"
export CLAWTEAM_AGENT_TYPE="leader"
```

---

## 测试用例 1：单个 BUG 修复流程

### 测试步骤

```bash
# Step 1: 从 GitHub Issues 获取 BUG
cat > /tmp/test-bug.json << 'EOF'
[
  {
    "id": "101",
    "title": "JWT token validation fails with timezone-aware datetime",
    "description": "AuthMiddleware raises ValueError when comparing JWT exp claim with timezone-aware datetime.",
    "priority": "P1",
    "url": "https://github.com/test/bug-repo/issues/101"
  }
]
EOF

# Step 2: 创建团队
TEAM_NAME="test-bugfix-$(date +%Y%m%d%H%M%S)"
clawteam team spawn-team $TEAM_NAME -d "Test bug fix" -n leader

# 验证点：团队创建成功
clawteam team status $TEAM_NAME
# 预期：显示 leader 成员

# Step 3: 创建任务
clawteam task create $TEAM_NAME \
    "Fix BUG #101: JWT token validation" \
    -o bugfix-0 \
    -d "URL: https://github.com/test/bug-repo/issues/101
Priority: P1
Description: JWT exp claim comparison fails with timezone-aware datetime.
Expected fix: Use datetime.utcnow() instead of datetime.now() for JWT comparison."

# 验证点：任务创建成功
clawteam board show $TEAM_NAME
# 预期：显示 1 个 pending 任务

# Step 4: Spawn worker
clawteam spawn \
    --team $TEAM_NAME \
    --agent-name bugfix-0 \
    --task "Fix the JWT timezone bug in AuthMiddleware. Test with pytest tests/test_auth.py. Report completion." \
    wsh claude

# 验证点：Worker 成功启动
ps aux | grep "bugfix-0"
# 预期：显示进程运行

# Step 5: 等待修复完成
timeout 300 bash -c "while true; do
  status=$(clawteam task list $TEAM_NAME --owner bugfix-0 --json | jq -r '.[0].status')
  if [ \"$status\" == \"completed\" ]; then
    echo \"Bug fixed!\"
    break
  fi
  sleep 10
done"

# 验证点：任务完成
clawteam task list $TEAM_NAME --owner bugfix-0 --json
# 预期：status = "completed"

# Step 6: 合并 worktree
clawteam workspace merge $TEAM_NAME bugfix-0

# Step 7: 运行测试验证修复
pytest tests/test_auth.py::test_jwt_validation -v

# 验证点：测试通过
# 预期：PASSED

# Step 8: 检查修复内容
git diff HEAD origin/buggy-branch -- tests/test_auth.py src/auth/middleware.py

# 验证点：修复正确
# 预期：使用 datetime.utcnow() 替换 datetime.now()

# Step 9: 清理
clawteam team cleanup $TEAM_NAME --force
```

### 验证点清单

- [ ] 团队创建成功
- [ ] Worker agent 启动并接收到任务
- [ ] Worker 完成修复并报告完成
- [ ] Worktree 合并成功
- [ ] 修复后的测试通过
- [ ] 代码修复符合预期

---

## 测试用例 2：多个 BUG 并行修复

### 测试步骤

```bash
# Step 1: 准备多个 BUG
cat > /tmp/test-bugs.json << 'EOF'
[
  {
    "id": "201",
    "title": "Memory leak in image processing",
    "description": "ImageProcessor fails to release QImage memory in batch processing, causing 50MB memory leak per 100 images.",
    "priority": "P1",
    "url": "https://github.com/test/bug-repo/issues/201"
  },
  {
    "id": "202",
    "title": "Race condition in file upload queue",
    "description": "UploadQueue has race condition when multiple threads call upload() simultaneously, causing duplicate uploads.",
    "priority": "P2",
    "url": "https://github.com/test/bug-repo/issues/202"
  },
  {
    "id": "203",
    "title": "SQL injection in user search",
    "description": "UserSearchDao concatenates user input directly into SQL query, allowing SQL injection.",
    "priority": "P0",
    "url": "https://github.com/test/bug-repo/issues/203"
  },
  {
    "id": "204",
    "title": "Unhandled exception in network timeout",
    "description": "HttpClient raises uncaught TimeoutError instead of returning None on network timeout.",
    "priority": "P2",
    "url": "https://github.com/test/bug-repo/issues/204"
  }
]
EOF

# Step 2: 创建团队
TEAM_NAME="test-parallel-bugfix-$(date +%Y%m%d%H%M%S)"
clawteam task spawn-team $TEAM_NAME -d "Parallel bug fix test" -n leader

# Step 3: 创建并行任务（无依赖）
bugs_json=$(cat /tmp/test-bugs.json)
bug_count=$(echo $bugs_json | jq '. | length')

for i in $(seq 0 $((bug_count-1))); do
    i_formatted=$(printf "%03d" $i)  # 000, 001, 002, 003
    bug=$(echo $bugs_json | jq ".[$i]")
    bug_id=$(echo $bug | jq -r '.id')
    bug_title=$(echo $bug | jq -r '.title')
    priority=$(echo $bug | jq -r '.priority')
    
    clawteam task create $TEAM_NAME \
        "Fix BUG #${bug_id}: ${bug_title}" \
        -o bugfix-${i_formatted} \
        -d "Priority: ${priority}

Description: $(echo $bug | jq -r '.description')

Instructions:
1. Analyze the bug
2. Implement fix
3. Run relevant tests
4. Report completion via inbox"

    echo "Created task for bugfix-${i_formatted}"
done

# 验证点：创建 4 个任务
task_count=$(clawteam task list $TEAM_NAME --json | jq '. | length')
echo "Tasks created: $task_count"
# 预期：task_count = 4

# Step 4: 并行 Spawn 4 个 workers
for i in $(seq 0 $((bug_count-1))); do
    i_formatted=$(printf "%03d" $i)
    
    clawteam spawn \
        --team $TEAM_NAME \
        --agent-name bugfix-${i_formatted} \
        --task "Fix your assigned bug. Use 'clawteam task list $TEAM_NAME --owner bugfix-${i_formatted}' to see details. Test and report." \
        wsh claude
    
    echo "Spawned bugfix-${i_formatted}"
done

# Step 5: 监控并行进度
echo "=== Monitoring parallel bug fix ==="
monitor_parallel() {
    for iteration in {1..30}; do
        echo "=== Iteration $iteration ==="
        
        # 统计各状态
        pending=$(clawteam task list $TEAM_NAME --status pending --json | jq '. | length')
        in_progress=$(clawteam task list $TEAM_NAME --status in_progress --json | jq '. | length')
        completed=$(clawteam task list $TEAM_NAME --status completed --json | jq '. | length')
        
        echo "Pending: $pending | In Progress: $in_progress | Completed: $completed"
        
        # 收集 inbox 消息
        messages=$(clawteam inbox receive $TEAM_NAME --agent leader)
        if [ -n "$messages" ]; then
            echo "=== Messages ==="
            echo "$messages"
        fi
        
        if [ $completed -eq $bug_count ]; then
            echo "=== All bugs fixed! ==="
            break
        fi
        
        sleep 30
    done
}

monitor_parallel

# 验证点：所有 4 个任务完成
final_completed=$(clawteam task list $TEAM_NAME --status completed --json | jq '. | length')
echo "Final completed: $final_completed"
# 预期：final_completed = 4

# Step 6: 合并所有 worktrees
for i in $(seq 0 $((bug_count-1))); do
    i_formatted=$(printf "%03d" $i)
    clawteam workspace merge $TEAM_NAME bugfix-${i_formatted}
    echo "Merged bugfix-${i_formatted}"
done

# Step 7: 运行完整测试套件
pytest tests/ -v --tb=short

# 验证点：所有相关测试通过
# 预期：之前失败的测试现在 PASSED

# Step 8: 清理
clawteam team cleanup $TEAM_NAME --force
```

### 验证点清单

- [ ] 4 个任务创建成功（所有状态为 pending）
- [ ] 4 个 workers 并行启动
- [ ] Workers 按预期分配任务（无冲突）
- [ ] 所有 BUG 在合理时间内修复（< 30 分钟）
- [ ] Worktrees 合并无冲突
- [ ] 测试套件全部通过
- [ ] 无 regression（新 BUG 未引入）

---

## 测试用例 3：Trellis 集成 - 记录 BUG 修复

### 测试步骤

```bash
# Step 1: 使用 Trellis 创建 bug fix task
python3 .trellis/scripts/task.py create \
    "BUG Fix: Memory leak in image processing" \
    --slug "bug-memory-leak" \
    --priority P1

# 验证点：Task 目录创建
ls -la .trellis/tasks/
# 预期：显示新创建的 task-XX-XX-bug-memory-leak/ 目录

# Step 2: 在工作修复流程中使用 ClawTeam
TEAM_NAME="trellis-integration-$(date +%Y%m%d%H%M%S)"
clawteam team spawn-team $TEAM_NAME -d "Trellis integration test" -n leader

clawteam task create $TEAM_NAME \
    "Fix memory leak: ImageProcessor" \
    -o fixer \
    -d "Fix memory leak in ImageProcessor.batch_process()"

clawteam spawn \
    --team $TEAM_NAME \
    --agent-name fixer \
    --task "Fix the memory leak and report completion." \
    wsh claude

# Step 3: 等待修复完成
timeout 300 bash -c "
while true; do
  status=\$(clawteam task list $TEAM_NAME --owner fixer --json | jq -r '.[0].status')
  if [ \"\$status\" == \"completed\" ]; then
    break
  fi
  sleep 10
done"

# Step 4: 合并 worktree
clawteam workspace merge $TEAM_NAME fixer

# Step 5: 测试验证
pytest tests/test_image_processor.py -v

# Step 6: 记录 session 到 Trellis
COMMIT_HASH=$(git rev-parse HEAD)

python3 .trellis/scripts/add_session.py \
    --title "Memory Leak Fix - ImageProcessor" \
    --commit "$COMMIT_HASH" \
    --summary "Fixed memory leak in ImageProcessor.batch_process() by ensuring QImage cleanup with RAII pattern. Before: 50MB leak per 100 images. After: No leak detected with valgrind."

# 验证点：Session 记录成功
cat .trellis/workspace/$USER/journal-1.md | tail -20
# 预期：显示新的 session 条目

# Step 7: 更新 spec/ 文档（如果 BUG 揭示了模式）
cat >> .trellis/spec/backend/memory-management.md << 'EOF'
## QImage Memory Management Pattern

**Issue**: Memory leak when processing batch images.

**Pattern**: Use RAII with std::unique_ptr<QImage> instead of raw pointers.

**Code**:
\`\`\`cpp
auto img = std::make_unique<QImage>(filename);
// img automatically deleted when out of scope
\`\`\`

**Discovery**: Bug #201 - ImageProcessor memory leak.
EOF

# 验证点：Spec 文档更新
cat .trellis/spec/backend/memory-management.md
# 预期：包含新添加的模式文档

# Step 8: 清理
clawteam team cleanup $TEAM_NAME --force
```

### 验证点清单

- [ ] Trellis task 创建成功
- [ ] ClawTeam 修复 BUG
- [ ] Session 记录到 workspace/journal.md
- [ ] Spec 文档更新（BUG 模式记录）
- [ ] 知识持久化成功

---

## 测试用例 4：Leader 协调 - 卡住的 Worker 恢复

### 测试步骤

```bash
# Step 1: 创建故意会卡住的 worker
TEAM_NAME="stuck-worker-test-$(date +%Y%m%d%H%M%S)"
clawteam team spawn-team $TEAM_NAME -d "Test stuck worker recovery" -n leader

clawteam task create $TEAM_NAME \
    "Fix BUG that will cause worker to get stuck" \
    -o stubborn-worker \
    -d "This bug requires manual intervention. Worker will get stuck analyzing complex code. Leader should detect and nudge."

clawteam spawn \
    --team $TEAM_NAME \
    --agent-name stubborn-worker \
    --task "Analyze this code: $(git rev-parse HEAD). This will take a long time. Wait for leader's nudge." \
    wsh claude

# 验证点：Worker 启动
ps aux | grep stubborn-worker
# 预期：进程存在

# Step 2: 等待 worker 卡住（无进度更新）
sleep 120

# 检查 worker 状态
clawteam board show $TEAM_NAME
# 预期：任务仍在 in_progress，但长时间无更新

# Step 3: Leader 检测并 nudge worker
echo "=== Leader detects stuck worker ==="

# 查看 worker 的 tmux pane
tmux capture-pane -p -t clawteam-$TEAM_NAME:stubborn-worker | tail -20

# 发送 nudge 消息
clawteam inbox send $TEAM_NAME stubborn-worker "I see you've been stuck for 2 minutes. Please continue. Try reading the inbox and resuming analysis."

# 验证点：Nudge 消息发送成功
clawteam inbox peek $TEAM_NAME stubborn-worker
# 预期：显示 nudge 消息

# Step 4: Worker 恢复工作（模拟 worker 响应 nudge）
# Worker protocol: 每 30 秒检查一次 inbox
sleep 40

# 检查 worker 是否有进展
clawteam board show $TEAM_NAME
# 预期：worker 继续工作（可能仍 in_progress，但有新日志）

# Step 5: 手动标记完成（测试目的）
clawteam task update $TEAM_NAME \
    $(clawteam task list $TEAM_NAME --json | jq -r '.[0].id') \
    --status completed

# Step 6: 清理
clawteam team cleanup $TEAM_NAME --force
```

### 验证点清单

- [ ] Worker 启动并接收到任务
- [ ] Worker 卡住（长时间无进度）
- [ ] Leader 检测到卡住状态
- [ ] Leader 通过 inbox 发送 nudge
- [ ] Worker 接收 nudge 并恢复工作
---

## 性能测试：并行 vs 串行

### 测试步骤

```bash
# 准备 8 个类似的 BUG（相同复杂度）
cat > /tmp/perf-bugs.json << 'EOF'
[
  {"id": "301", "title": "Import error in module A", "priority": "P1"},
  {"id": "302", "title": "TypeError in function B", "priority": "P1"},
  {"id": "303", "title": "KeyError in dict C", "priority": "P1"},
  {"id": "304", "title": "ValueError in parser D", "priority": "P1"},
  {"id": "305", "title": "AttributeError in class E", "priority": "P1"},
  {"id": "306", "title": "IndexError in list F", "priority": "P1"},
  {"id": "307", "title": "OSError in file G", "priority": "P1"},
  {"id": "308", "title": "RuntimeError in thread H", "priority": "P1"}
]
EOF

# 测试并行修复
echo "=== Parallel with 4 workers ==="
START_TIME=$(date +%s)

TEAM_NAME="perf-parallel-$(date +%Y%m%d%H%M%S)"
clawteam team spawn-team $TEAM_NAME -d "Perf test parallel" -n leader

bugs_json=$(cat /tmp/perf-bugs.json)
bug_count=8

# 创建 8 个任务
for i in $(seq 0 $((bug_count-1))); do
    i_formatted=$(printf "%03d" $i)
    bug=$(echo $bugs_json | jq ".[$i]")
    bug_id=$(echo $bug | jq -r '.id')
    
    # 分配到 4 个 workers（循环分配）
    worker_idx=$((i % 4))
    worker_name="perf-worker-${worker_idx}"
    
    clawsim task create $TEAM_NAME \
        "Fix BUG #${bug_id}" \
        -o $worker_name \
        -d "Fix this simple bug."
done

# Spawn 4 workers
for i in {0..3}; do
    clawteam spawn \
        --team $TEAM_NAME \
        --agent-name perf-worker-${i} \
        --task "Fix your assigned bugs from task list. Work sequentially." \
        wsh claude
done

# 等待所有完成
timeout 3600 bash -c "
completed=0
while [ \$completed -lt 8 ]; do
  completed=\$(clawteam task list $TEAM_NAME --status completed --json | jq '. | length')
  sleep 5
done
"

END_TIME=$(date +%s)
PARALLEL_TIME=$((END_TIME - START_TIME))

echo "Parallel time: ${PARALLEL_TIME} seconds (4 workers, 8 bugs)"

clawteam team cleanup $TEAM_NAME --force

# 测试串行修复（1 个 worker）
echo "=== Sequential with 1 worker ==="
START_TIME=$(date +%s)

TEAM_NAME="perf-sequential-$(date +%Y%m%d%H%M%S)"
clawteam team spawn-team $TEAM_NAME -d "Perf test sequential" -n leader

# 创建 8 个任务，分配给 1 个 worker
for i in $(seq 0 $((bug_count-1))); do
    i_formatted=$(printf "%03d" $i)
    bug=$(echo $bugs_json | jq ".[$i]")
    bug_id=$(echo $bug | jq -r '.id')
    
    clawteam task create $TEAM_NAME \
        "Fix BUG #${bug_id}" \
        -o perf-worker-single \
        -d "Fix this simple bug."
done

# Spawn 1 个 worker
clawteam spawn \
    --team $TEAM_NAME \
    --agent-name perf-worker-single \
    --task "Fix all 8 bugs from task list. Work sequentially." \
    wsh claude

# 等待所有完成
timeout 3600 bash -c "
completed=0
while [ \$completed -lt 8 ]; do
  completed=\$(clawteam task list $TEAM_NAME --status completed --json | jq '. | length')
  sleep 5
done
"

END_TIME=$(date +%s)
SEQUENTIAL_TIME=$((END_TIME - START_TIME))

echo "Sequential time: ${SEQUENTIAL_TIME} seconds (1 worker, 8 bugs)"

clawteam team cleanup $TEAM_NAME --force

# 计算加速比
ACCELERATION=$(echo "scale=2; $SEQUENTIAL_TIME / $PARALLEL_TIME" | bc)
echo "Acceleration: ${ACCELERATION}x"

# 验证点：并行快于串行
# 预期：ACCELERATION > 2（理想是 4x，但有开销）
```

### 验证点清单

- [ ] 并行修复 8 个 BUG
- [ ] 串行修复 8 个 BUG
- [ ] 并行加速比 > 1.5（2x 更理想）
- [ ] 代码质量同等（都是正确修复）

---

## 边界条件测试

### 测试用例：网络故障时的 Worker 行为

```bash
# 模拟：Worker 需要 fetch 外部依赖时网络断开

TEAM_NAME="network-failure-test-$(date +%Y%m%d%H%M%S)"
clawteam team spawn-team $TEAM_NAME -d "Network failure test" -n leader

clawteam task create $TEAM_NAME \
    "Fix bug requiring network fetch" \
    -o network-worker \
    -d "This bug needs to download a test file from URL. Simulate network failure and verify recovery."

clawteam spawn \
    --team $TEAM_NAME \
    --agent-name network-worker \
    --task "Fix bug. If network fails, report via inbox and wait for leader's retry command." \
    wsh claude

# 等待 worker 尝试下载
sleep 60

# 检查 inbox 报告
messages=$(clawteam inbox receive $TEAM_NAME --agent leader)
echo "$messages"
# 预期：包含 "Network failed" 或 "Download failed" 消息

# Leader 响应：重试或提供离线方案
clawteam inbox send $TEAM_NAME network-worker "Network failure noted. Use local test file instead of download."

# 等待恢复
sleep 60

# 验证完成
clawteam task list $TEAM_NAME --status completed --json
```

### 验证点清单

- [ ] Worker 检测网络故障
- [ ] Worker 报告错误到 inbox
- [ ] Leader 发送替代方案指令
- [ ] Worker 使用替代方案完成任务

---

## 清理和验证清单

### 测试后清理

```bash
# 清理所有测试团队
for team in $(ls ~/.clawteam/teams/ | grep "^test-"); do
    clawteam team cleanup $team --force
done

# 清理测试 Trellis tasks
for task_dir in $(ls -d .trellis/tasks/*/test-* 2>/dev/null); do
    python3 .trellis/scripts/task.py archive $(basename $task_dir)
done

# 验证：无残留
ls ~/.clawteam/teams/ | wc -l
# 预期：0（或只有非测试团队）

ls ~/.clawteam/workspaces/ | wc -l
# 预期：0
```

### 最终验证清单

- [ ] 所有测试用例通过
- [ ] 性能测试显示并行优势（>1.5x 加速）
- [ ] Trellis 集成正常（session 记录、spec 更新）
- [ ] Leader 协调正常（检测卡住 worker、nudge 恢复）
- [ ] 边界条件处理正常（网络故障、竞态条件）
- [ ] 清理后无残留进程和文件

---

## 预期测试结果

| 测试用例 | 预期结果 | 成功标准 |
|---------|---------|---------|
| 单个 BUG 修复 | BUG 修复，测试通过 | 通过 |
| 多个 BUG 并行 | 所有 BUG 修复，<30 分钟 | 通过 |
| Trellis 集成 | Session 记录，spec 更新 | 通过 |
| Leader 协调 | 检测卡住 worker，恢复成功 | 通过 |
| 性能测试 | 并行加速 >1.5x | 通过 |
| 网络故障 | Worker 报告，Leader 指令，恢复 | 通过 |

---

## 测试失败处理

如果任何测试失败：

1. **查看日志**：
   ```bash
   # ClawaTeam 日志
   ~/.clawteam/teams/<team>/*.log
   
   # Worktree 日志
   ~/.clawteam/workspaces/.trellis/workspaces/worktrees/<branch>/.agent-log
   ```

2. **手动干预**：
   ```bash
   # Kill 卡住的 worker
   kill <pid>
   
   # 强制合并 worktree
   git merge --strategy-option theirs
   ```

3. **清理重试**：
   ```bash
   clawteam team cleanup <team> --force
   # 重新运行测试
   ```

---

## 测试执行命令（一键运行）

```bash
# 运行所有测试
./run-parallel-bug-fix-tests.sh

# 运行单个测试
./test-single-bug-fix.sh
./test-parallel-bug-fix.sh
./test-trellis-integration.sh
./test-leader-coordination.sh
./test-performance.sh
```

---

**文档版本**: 1.0
**最后更新**: 2026-04-07
**测试环境**: ClawTeam v0.3.0 + Trellis latest
