# 场景二：并行代码审查 - 测试提示词文档

## 测试目标

验证 ClawTeam 与 Trellis 结合实现并行代码审查的完整流程，包括多角度专业化审查、审查报告收集和决策综合。

---

## 测试环境准备

```bash
# 1. 克隆待审查项目
git clone https://github.com/test/code-to-review.git
cd code-to-review

# 2. 检查 PR 或分支
# 方式 1：审查 GitHub PR
gh pr view 123 --json title,headRefName,baseRefName,files,commits

# 方式 2：审查本地分支
git checkout feature/new-feature
git diff main...feature/new-feature > /tmp/pr-diff.txt

# 3. 安装必要工具
# GitHub CLI for test automation
apt-get install gh

# 4. 初始化 Leader
export CLAWTEAM_AGENT_ID="review-leader-001"
export CLAWTEAM_AGENT_NAME="leader"
export CLAWTEAM_AGENT_TYPE="leader"
```

---

## 测试用例 1：单个 PR 并行审查

### 测试步骤

```bash
# Step 1: 获取 PR 信息
gh pr view 123 \
    --json title,body,headRefName,baseRefName,files,commits \
    > /tmp/pr-123-info.json

title=$(jq -r '.title' /tmp/pr-123-info.json)
head_ref=$(jq -r '.headRefName' /tmp/pr-123-info.json)
base_ref=$(jq -r '.baseRefName' /tmp/pr-123-info.json)

echo "Reviewing PR: $title"
echo "Branch: $head_ref -> $base_ref"

# Step 2: 创建审查团队
TEAM_NAME="review-pr-123-$(date +%Y%m%d%H%M%S)"
clawteam team spawn-team $TEAM_NAME \
    -d "Code review for PR #123: $title" \
    -n leader

# 验证点：团队创建成功
clawteam team status $TEAM_NAME
# 预期：显示 leader 成员

# Step 3: 创建 4 个专业化审查任务

# Task 1: Security Review
clawteam task create $TEAM_NAME \
    "Security Review: Check for vulnerabilities, auth issues, sensitive data exposure" \
    -o security-reviewer \
    -d "Review PR #123 for security issues:
- Input validation and sanitization
- Authentication and authorization
- Password handling and hashing
- SQL injection, XSS, CSRF vulnerabilities
- Encryption of sensitive data
- Error messages that leak info
Branch: $head_ref vs $base_ref

Use tools: grep -r 'password\|secret\|token', ast-grep for patterns."

# Task 2: Performance Review
clawteam task create $TEAM_NAME \
    "Performance Review: Check for bottlenecks, algorithms, database queries" \
    -o performance-reviewer \
    -d "Review PR #123 for performance issues:
- Nested loops or O(n²) algorithms
- Unoptimized database queries (N+1 problems)
- Memory leaks or excessive allocations
- Unnecessary computations or redundant work
- API response times
- Caching opportunities
Branch: $head_ref vs $base_ref

Use tools: ast-grep for loops, grep for SQL queries, pytest-benchmark."

# Task 3: Logic Review
clawteam task create $TEAM_NAME \
    "Logic Review: Check functionality correctness, edge cases, error handling" \
    -o logic-reviewer \
    -d "Review PR #123 for logic issues:
- Business logic correctness
- Edge cases (empty input, null values, boundaries)
- Error handling and exceptions
- Race conditions
- Type safety
- Data consistency
- Feature completeness (matches requirements)
Branch: $head_ref vs $base_ref"

# Task 4: Style Review
clawteam task create $TEAM_NAME \
    "Style Review: Check code quality, naming, comments, maintainability" \
    -o style-reviewer \
    -d "Review PR #123 for style issues:
- Code style consistency (ruff/flake8, eslint)
- Naming conventions (variables, functions, classes)
- Comments and documentation
- Code complexity (cyclomatic complexity)
- Dead code or commented-out code
- Magic numbers and strings
- Line length and formatting
Branch: $head_ref vs $base_ref

Use tools: ruff check, eslint, pylint."

# 验证点：创建 4 个并行任务
task_count=$(clawteam task list $TEAM_NAME --json | jq '. | length')
echo "Review tasks created: $task_count"
# 预期：task_count = 4

# Step 4: Checkout PR branch 并准备 shared worktree
WORKTREE_BASE="/tmp/code-review-worktrees"
mkdir -p $WORKTREE_BASE

# 获取 PR branch
gh pr checkout 123

# 为每个 reviewer 创建独立 worktree（相同代码快照）
for aspect in security performance logic style; do
    reviewer_name="${aspect}-reviewer"
    
    git worktree add $WORKTREE_BASE/$reviewer_name $head_ref
    
    # 标记 reviewer 所属的 aspect
    echo "$aspect" > $WORKTREE_BASE/$reviewer_name/.aspect-marker
    
    echo "Created worktree for $reviewer_name"
done

# 验证点：创建 4 个 worktrees
ls $WORKTREE_BASE/
# 预期：显示 4 个 reviewer 目录

# Step 5: 并行 Spawn 4 个专业化 reviewers

for aspect in security performance logic style; do
    reviewer_name="${aspect}-reviewer"
    
    specialized_prompt="You are a ${aspect} reviewer specialist. 

Your task: Review the code in your worktree ($WORKTREE_BASE/$reviewer_name) for ${aspect} issues.

Workflow:
1. Read the diff: git diff $base_ref...$head_ref
2. Use appropriate analysis tools:
   - Security: grep for 'password|secret|token', 'eval('
   - Performance: ast-grep for nested loops, 'for.*for'
   - Logic: analyze business logic and error paths
   - Style: run linter (ruff/eslint), check naming
3. Create a review report: ./review-report-${aspect}.md
4. Report summary to leader via inbox

Report format:
- Critical issues (must fix)
- High priority issues (should fix)
- Medium/Low issues (nice to fix)
- Each issue with: file:line, severity, description, suggestion
- Overall assessment

Focus deeply on ${aspect} - don't duplicate reviews from other aspects."

    clawteam spawn \
        --team $TEAM_NAME \
        --agent-name $reviewer_name \
        --task "$specialized_prompt" \
        --cwd $WORKTREE_BASE/$reviewer_name \
        wsh claude
    
    echo "Spawned $reviewer_name"
done

# 验证点：4 个 reviewers 启动
ps aux | grep "reviewer"
# 预期：4 个进程运行

# Step 6: 监控并行审查进度
echo "=== Monitoring parallel code review ==="
monitor_reviews() {
    for iteration in {1..20}; do
        echo "=== Iteration $iteration ==="
        
        # 统计各状态
        pending=$(clawteam task list $TEAM_NAME --status pending --json | jq '. | length')
        in_progress=$(clawteam task list $TEAM_NAME --status in_progress --json | jq '. | length')
        completed=$(clawteam task list $TEAM_NAME --status completed --json | jq '. | length')
        
        echo "Pending: $pending | In Progress: $in_progress | Completed: $completed"
        
        # 收集 reviewer 消息
        messages=$(clawteam inbox receive $TEAM_NAME --agent leader)
        if [ -n "$messages" ]; then
            echo "=== Reviewer Messages ==="
            echo "$messages"
        fi
        
        if [ $completed -eq 4 ]; then
            echo "=== All reviewers completed! ==="
            break
        fi
        
        sleep 60
    done
}

monitor_reviews

# 验证点：所有 4 个综述任务完成
final_completed=$(clawteam task list $TEAM_NAME --status completed --json | jq '. | length')
echo "Final completed reviews: $final_completed"
# 预期：final_completed = 4

# Step 7: 收集并综合审查报告
echo "=== Synthesizing review reports ==="

synthesis_report="/tmp/review-synthesis-$(date +%Y%m%d%H%M%S).md"

cat > "$synthesis_report" << EOF
# Code Review Synthesis - PR #123

**PR Title**: $title
**Branch**: $head_ref -> $base_ref
**Reviewers**: 4 specialized reviewers (security, performance, logic, style)

## Summary

EOF

# 收集每个 aspect 的报告
for aspect in security performance logic style; do
    reviewer_name="${aspect}-reviewer"
    report_path="$WORKTREE_BASE/$reviewer_name/review-report-${aspect}.md"
    
    if [ -f "$report_path" ]; then
        echo "### $aspect Review" >> "$synthesis_report"
        echo "" >> "$synthesis_report"
        echo "<details>" >> "$synthesis_report"
        echo "<summary>Click to expand</summary>" >> "$synthesis_report"
        echo "" >> "$synthesis_report"
        cat "$report_path" >> "$synthesis_report"
        echo "" >> "$synthesis_report"
        echo "</details>" >> "$synthesis_report"
        echo "" >> "$synthesis_report"
    fi
done

# 综合分析和决策
cat >> "$synthesis_report" << EOF

## Synthesis

### Critical Issues Overview
$(grep -h "### Critical" $WORKTREE_BASE/*/review-report-*.md | sed 's/^/- /' | sort -u)

### High Priority Issues Overview
$(grep -h "### High" $WORKTREE_BASE/*/review-report-*.md | sed 's/^/- /' | sort -u)

### Disagreements
(如果有不同 reviewers 对同一问题有不同意见，列在这里)

### Final Decision

$(total_critical=$(grep -c "### Critical" $WORKTREE_BASE/*/review-report-*.md)
if [ $total_critical -gt 0 ]; then
    echo "**REQUEST CHANGES** - $total_critical critical issues found. Must be fixed before merge."
else
    echo "**APPROVE** - No critical issues. Ready to merge."
fi)

### Approval Condition

$(if [ $total_critical -gt 0 ]; then
    echo "All critical issues must be addressed and verified."
else
    echo "None required. All reviewers approve."
fi)

---

**Reviewed by**: ClawTeam + Trellis Integration Test
**Date**: $(date)
EOF

echo "=== Review synthesis ==="
cat "$synthesis_report"

# 验证点：综合报告生成
# 预期：显示完整的审查综合（包含 4 个 aspect 的发现）

# Step 8: 如果使用 GitHub，将报告作为 comment 发送到 PR
# (仅在测试真实 PR 时执行)
if [ "1" = "0" ]; then  # 默认关闭
    gh pr comment 123 --body-file "$synthesis_report"
fi

# Step 9: 清理
echo "=== Cleanup ==="

# 移除 worktrees
for aspect in security performance logic style; do
    reviewer_name="${aspect}-reviewer"
    
    cd /path/to/code-to-review
    git worktree remove $WORKTREE_BASE/$reviewer_name
done

# 清理团队
clawteam team cleanup $TEAM_NAME --force

echo "Review test completed. Synthesis report: $synthesis_report"
```

### 验证点清单

- [ ] 团队创建成功
- [ ] 4 个专业化任务创建（无依赖，并行）
- [ ] 4 个 reviewer worktrees 创建（相同代码）
- [ ] 4 个 reviewers 并行启动
- [ ] Reviewers 生成独立报告
- [ ] Leader 收集并综合报告
- [ ] 决策正确（有 critical → REQUEST CHANGES；无 → APPROVE）
- [ ] 清理成功（无残留）

---

## 测试用例 2：审查决策 - 多种场景

### 场景 2.1：所有 reviewers APPROVE（无 critical issues）

```bash
# 准备一个"干净"的 PR（无明显问题）
# 方法：审查一个已经通过 code review 的 PR

TEAM_NAME="test-approve-$(date +%Y%m%d%H%M%S)"
clawteam team spawn-team $TEAM_NAME -d "Test approve scenario" -n leader

# 创建审查任务
for aspect in security performance logic style; do
    clawteam task create $TEAM_NAME \
        "Review clean PR for ${aspect}" \
        -o "${aspect}-reviewer" \
        -d "Review PR #999 for ${aspect} issues. This is a clean PR with minimal changes."
done

# Spawn reviewers（创建 dummy 报告）
for aspect in security performance logic style; do
    WORKTREE="/tmp/review-approve-${aspect}"
    mkdir -p $WORKTREE
    cd /path/to/clean-pr
    git worktree add $WORKTREE feature/clean
    
    # 创建"无问题"报告
    cat > $WORKTREE/review-report-${aspect}.md << EOF
### ${aspect} Review

No critical issues found.

### High Priority Issues
None.

### Medium/Low Priority Issues
None.

### Overall Assessment
The code is well-written and follows best practices for ${aspect} considerations.
EOF
    
    clawteam spawn \
        --team $TEAM_NAME \
        --agent-name "${aspect}-reviewer" \
        --task "Review and report. Pre-generated report exists in worktree." \
        --cwd $WORKTREE \
        wsh claude
done

# 等待完成
timeout 300 bash -c "
while true; do
  completed=\$(clawteam task list $TEAM_NAME --status completed --json | jq '. | length')
  if [ \"\$completed\" -eq 4 ]; then
    break
  fi
  sleep 10
done"

# 验证决策：应该 APPROVE
synthesis_check=$(grep "APPROVE" /tmp/review-synthesis-*.md 2>/dev/null | wc -l)
echo "Approve decisions: $synthesis_check"
# 预期：synthesis_check >= 1

clawteam team cleanup $TEAM_NAME --force
```

### 验证点清单

- [ ] 批量创建审查任务
- [ ] Reviewers 发现无问题
- [ ] 综合决策为 APPROVE
- [ ] 无 critical issues

---

### 场景 2.2：有 critical issues → REQUEST CHANGES

```bash
# 准备一个"有问题"的 PR（包含安全漏洞）

TEAM_NAME="test-request-changes-$(date +%Y%m%d%H%M%S)"
clawteam team spawn-team $TEAM_NAME -d "Test request changes scenario" -n leader

# 创建 security review 任务（会发现问题）
clawteam task create $TEAM_NAME \
    "Security Review: Find vulnerabilities" \
    -o security-reviewer \
    -d "Review PR #1000 for security issues. This PR intentionally contains security problems:
- Hardcoded password
- SQL injection vulnerability
- Missing input validation"

# 创建其他 reviewers（可能无问题）
for aspect in performance logic style; do
    clawteam task create $TEAM_NAME \
        "Clean ${aspect} review" \
        -o "${aspect}-reviewer" \
        -d "Review for ${aspect} issues. This PR should have minimal ${aspect} problems."
done

# Spawn security reviewer（模拟发现 critical）
WORKTREE="/tmp/review-insecure"
mkdir -p $WORKTREE
cd /path/to/insecure-pr
git worktree add $WORKTREE feature/insecure

cat > $WORKTREE/review-report-security.md << 'EOF'
### Security Review

### Critical Issues

- **src/auth.py:42**: Hardcoded password - `"admin_password = 'secret123'"` must use environment variables
- **src/api/login.py:15**: SQL injection - Direct string concatenation in query: `"SELECT * FROM users WHERE username = '" + username + "'"`

### High Priority Issues

- **src/utils/crypto.py:8**: Weak encryption - Using MD5 for password hashing instead of bcrypt

### Medium/Low Priority Issues

None.

### Overall Assessment
CRITICAL VULNERABILITIES FOUND. Cannot merge without fixes.
EOF

clawteam spawn \
    --team $TEAM_NAME \
    --agent-name security-reviewer \
    --task "Review and find security issues." \
    --cwd $WORKTREE \
    wsh claude

# Spawn other reviewers（clean）
for aspect in performance logic style; do
    WORKTREE="/tmp/review-clean-${aspect}"
    mkdir -p $WORKTREE
    cd /path/to/insecure-pr
    git worktree add $WORKTREE feature/insecure
    
    cat > $WORKTREE/review-report-${aspect}.md << EOF
### ${aspect} Review

No issues found.
EOF
    
    clawteam spawn \
        --team $TEAM_NAME \
        --agent-name "${aspect}-reviewer" \
        --task "Review and report." \
        --cwd $WORKTREE \
        wsh claude
done

# 综合决策
# 应该 REQUEST CHANGES（发现 critical）

# 验证决策：应该 REQUEST CHANGES
critical_count=$(grep -c "### Critical" /tmp/review-synthesis-*.md 2>/dev/null)
echo "Critical issues count: $critical_count"
# 预期：critical_count > 0

decision_made=$(grep "REQUEST CHANGES" /tmp/review-synthesis-*.md 2>/dev/null | wc -l)
echo "Request changes decisions: $decision_made"
# 预期：decision_made >= 1

clawteam team cleanup $TEAM_NAME --force
```

### 验证点清单

- [ ] Security reviewer 发现 critical vulnerabilities
- [ ] 其他 reviewers 发现无问题或 low issues
- [ ] 综合决策为 REQUEST CHANGES
- [ ] Critical issues 明确列出

---

### 场景 2.3：Reviewers 有分歧（需要 Oracle 决策）

```bash
# 准备一个 PR：某个功能实现，reviewers 对设计有不同意见

TEAM_NAME="test-disagreement-$(date +%Y%m%d%H%M%S)"
clawteam team spawn-team $TEAM_NAME -d "Test reviewer disagreement" -n leader

# 创建 tasks
clawteam task create $TEAM_NAME \
    "Logic Review: Functionality correctness" \
    -o logic-reviewer \
    -d "Review complex algorithm implementation. Verify correctness and edge cases."

clawteam task create $TEAM_NAME \
    "Performance Review: Algorithm efficiency" \
    -o performance-reviewer \
    -d "Review algorithm complexity. Consider performance trade-offs."

# Spawn reviewers（模拟分歧）
WORKTREE_LOGIC="/tmp/review-logic"
mkdir -p $WORKTREE_LOGIC
cd /path/to/disagreement-pr
git worktree add $WORKTREE_LOGIC feature/disagreement

cat > $WORKTREE_LOGIC/review-report-logic.md << 'EOF'
### Logic Review

### Critical Issues
None.

### High Priority Issues

- **src/algorithms/sort_special.py:23**: Logic error - Edge case not handled when input array is empty → returns None instead of []
- **src/algorithms/sort_special.py:45**: Incorrect comparison - Using `<=` instead of `<` causes off-by-one error

### Overall Assessment
The core algorithm has logic bugs that must be fixed. The approach is sound but implementation has errors.
RECOMMENDATION: REQUEST CHANGES - Fix logic bugs before merge.

---

**Design Opinion**: The algorithm design is correct for the problem statement.
EOF

clawteam spawn \
    --team $TEAM_NAME \
    --agent-name logic-reviewer \
    --task "Review logic and report bugs." \
    --cwd $WORKTREE_LOGIC \
    wsh claude

WORKTREE_PERF="/tmp/review-perf"
mkdir -p $WORKTREE_PERF
git worktree add $WORKTREE_PERF feature/disagreement

cat > $WORKTREE_PERF/review-report-performance.md << 'EOF'
### Performance Review

### Critical Issues
None.

### High Priority Issues

- **src/algorithms/sort_special.py:23**: Unnecessary copying - Creates temporary array copy on each iteration → O(n²) memory

### Overall Assessment
Performance is acceptable (O(n log n) time complexity), but memory usage could be improved.
RECOMMENDATION: APPROVE with minor optimization suggestion for next iteration.

---

**Design Opinion**: The current design is a good balance of simplicity and performance. Alternative design (different algorithm) would be over-engineering for this use case.
EOF

clawteam spawn \
    --team $TEAM_NAME \
    --agent-name performance-reviewer \
    --task "Review performance and report." \
    --cwd $WORKTREE_PERF \
    wsh claude

综合决策：有分歧
- Logic reviewer: REQUEST CHANGES（有 bugs）
- Performance reviewer: APPROVE（无 critical）

但关键：logic bugs 是 critical 必须修复，所以最终决策仍为 REQUEST CHANGES

模拟分歧场景（不同选择）：两个发现都无 critical，但对设计有不同看法

# 真正的分歧场景：
TEAM_NAME="test-real-disagreement-$(date +%Y%m%d%H%M%S)"

# 两个 reviewer 对同一个设计选择有不同意见
# 例：security vs UX

# Security reviewer: "This feature requires users to re-authenticate → good security posture"
# UX reviewer: "Re-authentication interrupts workflow → bad UX"

# 这种分歧需要 Human 或 Oracle 决策

```

### 验证点清单（真实分歧）

- [ ] Reviewers 对设计选择有不同看法
- [ ] 无 critical technical issues
- [ ] 需要 Human/Oracle 权衡
- [ ] 综合报告标注"Needing human decision"

---

## 测试用例 3：Trellis 集成 - 记录审查结果

### 测试步骤

```bash
# Step 1: 创建 Trellis task for code review
python3 .trellis/scripts/task.py create \
    "Code Review: PR #123 AI search feature" \
    --slug "review-pr-123" \
    --assignee "$USER"

# 验证点：Task 目录创建
ls -la .trellis/tasks/
# 预期：显示 task-XX-XX-review-pr-123/

# Step 2: 执行并行审查（使用测试用例 1 的流程）
TEAM_NAME="trellis-review-test-$(date +%Y%m%d%H%M%S)"

# ... (完整的审查流程，同测试用例 1) ...

# Step 3: 审查完成后，记录 session 到 Trellis
COMMIT_SHA=$(git rev-parse HEAD)
SYNTHESIS_REPORT="/tmp/review-synthesis-latest.md"

python3 .trellis/scripts/add_session.py \
    --title "Code Review Session - PR #123" \
    --commit "$COMMIT_SHA" \
    --summary "Reviewed PR #123 with 4 specialized reviewers:
- Security: 2 critical issues (hardcoded password, SQL injection)
- Performance: 1 high issue (unnecessary array copying)
- Logic: 0 issues
- Style: 3 medium issues (naming, line length, magic numbers)

Decision: REQUEST CHANGES - Must fix critical security vulnerabilities before merge."

# 验证点：Session 记录成功
cat .trellis/workspace/$USER/journal-*.md | grep -A 10 "Code Review Session"
# 预期：显示审查 session 记录

# Step 4: 更新 spec/ 文档（记录发现的问题模式）

# 如果发现了常见的错误模式，更新 guidelines
cat >> .trellis/spec/backend/security-patterns.md << 'EOF'
## Common Security Anti-Patterns Found in Reviews

### Hardcoded Passwords

**Issue**: Code contains plaintext passwords or API keys.

**Example**:
\`\`\`python
password = "secret123"  # BAD
\`\`\`

**Correct Pattern**:
\`\`\`python
import os
password = os.environ.get("APP_PASSWORD")  # GOOD
\`\`\`

**Discovery**: PR #123 review - Found hardcoded password in auth.py.

Prevention: Tooling - Use pre-commit hooks (detect-secrets) to scan code.
EOF

cat >> .trellis/spec/backend/performance-patterns.md << 'EOF'
## Anti-Pattern: Unnecessary Copying in Loops

**Issue**: Creating temporary copies inside loops increases memory overhead.

**Example**:
\`\`\`python
for item in items:
    temp = items.copy()  # BAD - copies entire list each iteration
    temp.remove(item)
\`\`\`

**Correct Pattern**:
\`\`\`python
for idx, item in enumerate(items):
    # Use index directly without copying
    result.append(items[:idx] + items[idx+1:])  # Only copy needed slice
\`\`\`

**Discovery**: PR #123 review - Found unnecessary copying in sort_special.py.

Impact: O(n²) memory → should be optimized to O(n) if possible.
EOF

# 验证点：Spec 文档更新
cat .trellis/spec/backend/security-patterns.md | grep -A 5 "PR #123"
# 预期：显示相关模式记录

# Step 5: 清理
clawteam team cleanup $TEAM_NAME --force
```

### 验证点清单

- [ ] Trellis task 创建成功
- [ ] 并行审查完成
- [ ] Session 记录到 workspace/journal.md
- [ ] Spec 更新（记录发现的反模式）
- [ ] 知识累积（未来的审查可以利用这些 pattern）

---

## 测试用例 4：大规模 PR 审查（多个 Files）

### 测试场景

审查一个大型 PR（100+ files changed），验证并行处理能力。

```bash
# 模拟：审查一个大型 feature branch

TEAM_NAME="large-pr-review-$(date +%Y%m%d%H%M%S)"
clawteam team spawn-team $TEAM_NAME \
    -d "Review large PR with 100+ files" \
    -n leader

# 获取 PR 信息
gh pr view 456 \
    --json title,headRefName,baseRefName,files \
    > /tmp/large-pr-info.json

file_count=$(jq -r '.files | length' /tmp/large-pr-info.json)
echo "Files changed: $file_count"
# 预期：file_count > 100

# 创建 tasks（将 files 分配给不同 reviewers）
# 策略：将文件按类型/模块分组

files_json=$(jq -r '.files[].path' /tmp/large-pr-info.json)

# Group 1: Backend files (*.py, API, DB)
backend_files=$(echo "$files_json" | grep -E 'src/(api|db|backend).*\.py$')

# Group 2: Frontend files (*.vue, *.js, components)
frontend_files=$(echo "$files_json" | grep -E 'src/(ui|frontend|components).*\.(vue|js|ts)$')

# Group 3: Config/Build files (*.json, *.yaml, Dockerfile)
config_files=$(echo "$files_json" | grep -E '\.(json|yaml|yml|Dockerfile)$')

# Group 4: Test files (*_test.py, *.test.ts)
test_files=$(echo "$files_json" | grep -E '.*test.*\.(py|ts|js)$')

# 为每个组创建 specialized review task
clawteam task create $TEAM_NAME \
    "Backend Review (Python, API, DB) - Review $(echo "$backend_files" | wc -l) files" \
    -o backend-reviewer \
    -d "Review backend changes for security, performance, logic. Files: $(echo "$backend_files" | head -10 | tr '\n' ' ')... ($(echo "$backend_files" | wc -l) total)"

clawteam task create $TEAM_NAME \
    "Frontend Review (Vue, JS) - Review $(echo "$frontend_files" | wc -l) files" \
    -o frontend-reviewer \
    -d "Review frontend changes for security, UX, performance. Files: $(echo "$frontend_files" | head -10 | tr '\n' ' ')... ($(echo "$frontend_files" | wc -l) total)"

clawteam task create $TEAM_NAME \
    "Config/Build Review - Review $(echo "$config_files" | wc -l) files" \
    -o config-reviewer \
    -d "Review config and build files for security (secrets, exposure), correctness. Files: $(echo "$config_files" | head -10 | tr '\n' ' ')... ($(echo "$config_files" | wc -l) total)"

clawteam task create $TEAM_NAME \
    "Test Review - Review $(echo "$test_files" | wc -l) files" \
    -o test-reviewer \
    -d "Review test files for coverage, edge cases, assertions. Files: $(echo "$test_files" | head -10 | tr '\n' ' ')... ($(echo "$test_files" | wc -l) total)"

# 验证点：4 个任务，每个处理不同类型的 files
task_count=$(clawteam task list $TEAM_NAME --json | jq '. | length')
echo "Review tasks: $task_count"
# 预期：task_count = 4

# Spawn reviewers（每个 reviewer 处理一组 files）
for reviewer in backend-reviewer frontend-reviewer config-reviewer test-reviewer; do
    clawteam spawn \
        --team $TEAM_NAME \
        --agent-name $reviewer \
        --task "Review your assigned file group. Create comprehensive report. Use git diff --stat to see file changes." \
        wsh claude
done

# 验证点：4 个 reviewers 并行启动

# 监控进度（大型 PR 需要更长时间）
echo "Monitoring large PR review (may take 10+ minutes)..."
timeout 600 bash -c "
while true; do
  completed=\$(clawteam task list $TEAM_NAME --status completed --json | jq '. | length')
  echo \"Completed: \$completed/4\"
  if [ \"\$completed\" -eq 4 ]; then
    break
  fi
  sleep 60
done"

# 综合 4 个 reviewer 的发现
# (同测试用例 1 的综合逻辑)

# 验证点：大型 PR 审查完成
# 预期：所有 files 被覆盖，报告完整

clawteam team cleanup $TEAM_NAME --force
```

### 验证点清单

- [ ] 大型 PR（100+ files）拆分为 4 个 review 组
- [ ] 每个 reviewer 负责不同类型的 files
- [ ] 并行审查在合理时间内完成（< 20 分钟）
- [ ] 综合报告覆盖所有 changes
- [ ] 清理成功

---

## 边界条件测试

### 测试用例：Reviewer 报告格式错误

```bash
# 模拟：一个 reviewer 生成的报告格式不正确
# 验证：Leader 仍能综合（容错性）

TEAM_NAME="malformed-report-$(date +%Y%m%d%H%M%S)"
clawteam team spawn-team $TEAM_NAME -d "Test malformed report handling" -n leader

# 创建 2 个 tasks
clawteam task create $TEAM_NAME \
    "Good reviewer" \
    -o good-reviewer \
    -d "Review and create properly formatted report."

clawteam task create $TEAM_NAME \
    "Bad reviewer" \
    -o bad-reviewer \
    -d "Review but create malformed report (missing sections)."

# Spawn reviewers
WORKTREE_GOOD="/tmp/review-good"
WORKTREE_BAD="/tmp/review-bad"

# Good reviewer
mkdir -p $WORKTREE_GOOD
cd /path/to/pr
git worktree add $WORKTREE_GOOD feature/pr
cat > $WORKTREE_GOOD/review-report-good.md << 'EOF'
### Good Review

### Critical Issues
None.

### High Priority Issues
None.

### Overall Assessment
Code is good. APPROVE.
EOF
clawteam spawn \
    --team $TEAM_NAME \
    --agent-name good-reviewer \
    --task "Review and generate report." \
    --cwd $WORKTREE_GOOD \
    wsh claude

# Bad reviewer (malformed report)
mkdir -p $WORKTREE_BAD
git worktree add $WORKTREE_BAD feature/pr
cat > $WORKTREE_BAD/review-report-bad.md << 'EOF'
### Bad Review

This report is malformed - missing "Critical Issues" and "High Priority Issues" sections.

### Overall Assessment
Code needs work. REQUEST CHANGES.

(No proper structure)
EOF
clawteam spawn \
    --team $TEAM_NAME \
    --agent-name bad-reviewer \
    --task "Generate a malformed report on purpose." \
    --cwd $WORKTREE_BAD \
    wsh claude

# 综合时应该容错
# 预期：Leader 仍能综合（即使部分报告格式错误）

```

### 验证点清单

- [ ] 处理格式错误的报告
- [ ] 不因单个报告错误而失败
- [ ] 综合报告仍生成（标注格式问题）
- [ ] 决策基于可用信息

---

## 性能测试：审查时间 vs files 数量

```bash
# 测试目标：测量审查时间与 PR size 的关系

# 测试不同规模的 PR：
# - 小型 PR（10 files）
# - 中型 PR（50 files）
# - 大型 PR（100 files）
# - 超大型 PR（500 files - mock）

# 记录：
# - Reviewer 启动时间
# - Review 完成时间
# - 综合时间
# - 总时间

# 绘制：review_time vs file_count 曲线

# 预期：时间接近线性（O(n))，因为并行处理

```

---

## 清理和验证清单

### 测试后清理

```bash
# 清理所有 review teams
for team in $(ls ~/.clawteam/teams/ | grep "^review-"); do
    clawteam team cleanup $team --force
done

# 清理 worktrees
git worktree prune

# 清理 test reports
rm -f /tmp/review-*.md

# 清理 Trellis test tasks
for task in $(ls -d .trellis/tasks/*/review-* 2>/dev/null); do
    python3 .trellis/scripts/task.py archive $(basename $task)
done
```

### 最终验证清单

- [ ] 所有测试用例通过
- [ ] 并行审查加速比合理（2-4x）
- [ ] Trellis 集成正常（积累知识）
- [ ] 容错性测试通过（报告格式错误）
- [ ] 大型 PR 处理正常（100+ files）
- [ ] 清理后无残留

---

## 预期测试结果

| 测试用例 | 预期结果 | 成功标准 |
|---------|---------|---------|
| 单个 PR 并行审查 | 4 个 specialized reviewers 完成审查 | 通过 |
| APPROVE 场景 | 所有关键 reviewers APPROVE，无 critical | 通过 |
| REQUEST CHANGES 场景 | 发现 critical，综合决策为 REQUEST | 通过 |
| Reviewer 分歧 | 标注需要 human 决策 | 通过 |
| Trellis 集成 | Session 记录，spec 更新 | 通过 |
| 大型 PR 审查 | 100+ files 并行审查完成 | 通过 |
| 格式容错 | 处理错误格式的报告 | 通过 |

---

## 测试失败处理

如果任何测试失败：

1. **查看 reviewer logs**：
   ```bash
   # Agent 日志
   ~/.clawteam/workspaces/.trellis/workspaces/worktrees/<branch>/.agent-log
   
   # Reviewer 报告
   /tmp/code-review-worktrees/<reviewer>/review-report-*.md
   ```

2. **手动综合**：
   ```bash
   # 如果自动综合失败，手动收集报告
   cat /tmp/code-review-worktrees/*/review-report-*.md > manual-synthesis.md
   gh pr comment <pr-number> --body-file manual-synthesis.md
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
./run-parallel-code-review-tests.sh

# 运行单个测试
./test-single-pr-review.sh
./test-approve-scenario.sh
./test-request-changes-scenario.sh
./test-disagreement-scenario.sh
./test-trellis-integration-review.sh
./test-large-pr-review.sh
```

---

**文档版本**: 1.0
**最后更新**: 2026-04-07
**测试环境**: ClawTeam v0.3.0 + Trellis latest
