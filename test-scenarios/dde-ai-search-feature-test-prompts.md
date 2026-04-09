# 场景三：DDE 文件管理器 AI 搜索功能开发 - 测试提示词文档

## 测试目标

验证 ClawTeam 与 Trellis 结合实现复杂功能（DDE AI 搜索）的完整开发流程，包括多模块依赖管理、跨组件协作、和知识累积。

---

## 测试环境准备

```bash
# 1. 克隆 DDE 文件管理器项目（mock 或真实）
git clone https://github.com/linuxdeepin/dde-file-manager.git
cd dde-file-manager

# 2. 初始化开发环境
# 安装依赖（Qt 5/6, DTK, CMake, glib, etc.)
sudo apt-get install qtbase5-dev libdtkwidget-dev cmake glib2.0-dev

# 3. 配置构建环境
mkdir -p build
cd build
cmake -DCMAKE_BUILD_TYPE=Debug ..
cd ..

# 4. 初始化 Trellis developer
python3 .trellis/scripts/init_developer.py test-developer

# 5. 初始化 Leader
export CLAWTEAM_AGENT_ID="feature-leader-001"
export CLAWTEAM_AGENT_NAME="leader"
export CLAWTEAM_AGENT_TYPE="leader"
```

---

## 测试用例 1：完整 AI 搜索功能开发流程

### Step 1: 使用 Trellis Plan Agent 规划功能

```bash
# 启动 Plan Agent 规划 AI 搜索功能
python3 .trellis/scripts/multi_agent/plan.py \
    --name ai-file-search \
    --type fullstack \
    --requirement "Add AI-powered semantic search to DDE file manager. Users can search files by natural language queries (e.g., 'find presentations from last week about marketing'). Use local embeddings + RAG. Priority: P1." \
    --platform claude

# 验证点：Plan Agent 创建 task 目录
ls -la .trellis/tasks/
# 预期：显示新目录 04-XX-ai-file-search/

# 验证：task.json 生成
cat .trellis/tasks/04-XX-ai-file-search/task.json
# 预期：包含 name, dev_type, status 等字段

# 验证：prd.md 生成
cat .trellis/tasks/04-XX-ai-file-search/prd.md
# 预期：包含详细设计（架构、技术栈、实现计划）

# 预期 prd.md 内容结构：
# - Feature Overview
# - User Stories
# - Architecture (Backend, Frontend, Database)
# - Technical Stack (Qt, onnxruntime, sentence-transformers)
# - Implementation Plan (子任务列表)
# - Success Criteria
```

### Step 2: 创建 ClawTeam 团队和依赖任务

```bash
# 读取 Plan Agent 生成的 task.json
TASK_DIR=".trellis/tasks/04-XX-ai-file-search"
cd $TASK_DIR

# 读取 task.json 并提取子任务列表
# 假设 task.json 包含：
# {
#   "name": "ai-file-search",
#   "dev_type": "fullstack",
#   "status": "planned",
#   "subtasks": [
#     {"id": "T1", "name": "Database schema", "owner": "db-agent", "blocked_by": []},
#     {"id": "T2", "name": "Embedding service", "owner": "backend-agent", "blocked_by": ["T1"]},
#     {"id": "T3", "name": "Search API", "owner": "backend-agent", "blocked_by": ["T2"]},
#     {"id": "T4", "name": "Search UI", "owner": "frontend-agent", "blocked_by": ["T3"]},
#     {"id": "T5", "name": "Tests", "owner": "test-agent", "blocked_by": ["T4"]}
#   ]
# }

# 创建 ClawTeam 团队
TEAM_NAME="ai-search-dev-$(date +%Y%m%d%H%M%S)"
clawteam team spawn-team $TEAM_NAME \
    -d "AI file search feature development" \
    -n leader

# 任务创建脚本（从 task.json 读取）
cat > /tmp/create-tasks.sh << 'EOF'
#!/bin/bash
TEAM_NAME=$1
TASK_DIR=$2

# 创建 T1: Database schema (无依赖)
T1=$(clawteam --json task create $TEAM_NAME \
    "Design database schema for file embeddings" \
    -o db-agent \
    -d "Create tables:
- files (id, path, size, mtime, indexed)
- embeddings (id, file_id, vector, model_version)
- fts_index (path, content for full-text search)

Use SQLite for portability. Add migration script: migrations/003_add_ai_search.sql" | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")

echo "T1=$T1"

# 创建 T2: Embedding service (依赖 T1)
T2=$(clawteam --json task create $TEAM_NAME \
    "Implement backend embedding service" \
    -o backend-agent \
    --blocked-by $T1 \
    -d "Create C++/Qt service with:
1. Indexing: Extract file metadata and content
2. Embedding: Generate vectors using onnxruntime (all-MiniLM-L6-v2)
3. Storage: Store embeddings in SQLite

Classes:
- IndexService (scan files, extract metadata)
- EmbeddingService (generate vectors)
- EmbeddingStorage (CRUD for embed table)

Use QThreadPool for background indexing." | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")

echo "T2=$T2"

# 创建 T3: Search API (依赖 T2)
T3=$(clawteam --json task create $TEAM_NAME \
    "Implement semantic search API endpoint" \
    -o backend-agent \
    --blocked-by $T2 \
    -d "Create REST API endpoint:
POST /api/search
Request: { "query": "marketing presentations", "limit": 20 }
Response: [ { "path": "/path/to/file", "score": 0.95, "file_type": "xlsx" } ]

Implementation:
- Use faiss or sqlite-builtin for vector similarity
- Implement query expansion (synonyms)
- Add search history table

Class: SearchService with search(query) method." | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")

echo "T3=$T3"

# 创建 T4: Search UI (依赖 T3)
T4=$(clawteam --json task create $TEAM_NAME \
    "Design and implement AI search UI" \
    -o frontend-agent \
    --blocked-by $T3 \
    -d "Create UI components in DDE file manager:
- AISearchBar.qml (search input with natural language placeholder)
- SearchResultsListView.qml (sorted by relevance with color-coded badges)
- AISearchModel.cpp (QAbstractListModel connecting to API)

Features:
- Debounced input (300ms QTimer)
- Progressive results (show as available)
- Relevance badges (high/green, medium/yellow, low/gray)
- Search history suggestion (from UI cache)

Use DTK components: DLineEdit, DListView, DLabel." | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")

echo "T4=$T4"

# 创建 T5: Tests (依赖 T4)
T5=$(clawteam --json task create $TEAM_NAME \
    "Write end-to-end tests" \
    -o test-agent \
    --blocked-by $T4 \
    -d "Write comprehensive tests:
1. Unit tests: EmbeddingService, SearchService
2. Integration tests: API endpoint + UI
3. Performance tests:
   - Indexing speed (>500 files/sec)
   - Search latency (<500ms)
   - Memory usage (<200MB for 10k files)

Use Qt Test + pytest. Mock embedding in unit tests." | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")

echo "T5=$T5"

echo "Task IDs: T1=$T1, T2=$T2, T3=$T3, T4=$T4, T5=$T5"
EOF

chmod +x /tmp/create-tasks.sh
bash /tmp/create-tasks.sh $TEAM_NAME $TASK_DIR

# 验证点：5 个任务创建，依赖关系正确
clawteam board show $TEAM_NAME
# 预期：
# - T1: pending
# - T2: blocked (by T1)
# - T3: blocked (by T2)
# - T4: blocked (by T3)
# - T5: blocked (by T4)
```

### Step 3: 使用 Trellis start.py 启动 worktree

```bash
# Plan Agent 完成后，启动 worktree agent
# 这会创建 git worktree 并启动 dispatch agent

python3 .trellis/scripts/multi_agent/start.py $TASK_DIR --platform claude

# 验证点：Worktree 创建
ls -la .trellis/workspaces/.trellis/workspaces/worktrees/
# 预期：显示 feature/ai-file-search/ 目录

# 验证 agent 注册
cat /tmp/registry.json
# 预期：包含 agent entry (id, worktree_path, pid, task_dir)

# 注意：这里使用的是 Trellis 的 multi_agent pipeline，它会自动：
# 1. 创建 git worktree
# 2. 复制环境变量
# 3. 启动 dispatch agent
# 4. Agent 会按照 task.json 中的 next_action 数组执行

# 但为了演示 ClawTeam 的多 agent 协调，我们手动 spawn 专业化 agents
```

### Step 4: Spawn 专业化 Agents (替代 dispatch agent)

```bash
# Agent 1: Database Specialist (C++/Qt)
clawteam spawn \
    --team $TEAM_NAME \
    --agent-name db-agent \
    --task "You are a database specialist for C++/Qt applications.

Your tasks:
1. Complete T1 (Database schema) when unblocked
2. Read existing DDE file manager DB code: src/db/database.{h,cpp}
3. Design new tables for AI search schema
4. Write migration script: migrations/003_add_ai_search.sql
5. Update DatabaseManager class

Tools:
- sqlite3 for testing
- Read: src/db/*.cpp

Follow DDE patterns:
- Use glib for DB abstraction
- Migration scripts in migrations/ directory
- Schema versioning with version table.

Report completion via inbox each task." \
    wsh codex

# Agent 2: Backend Specialist (C++/Qt + AI)
clawteam spawn \
    --team $TEAM_NAME \
    --agent-name backend-agent \
    --task "You are a C++/Qt backend developer with AI integration expertise.

Your tasks:
1. Wait for T1 (Database schema) to complete
2. Complete T2 (Embedding service)
3. Complete T3 (Search API)

Implementation notes:
- Use onnxruntime for model inference (cross-platform)
- Model: all-MiniLM-L6-v2 (384-dim, balance of speed/accuracy)
- Use QThreadPool for background indexing (don't block UI)
- SQLite BLOB for vector storage (portability > raw performance)
- FTS5 for full-text search complement

Classes to create:
- src/services/IndexService.{h,cpp}
- src/services/EmbeddingService.{h,cpp} (uses ONNX session)
- src/services/SearchService.{h,cpp} (implements API)

Tools:
- ONNX Runtime C++ API
- Qt SQL module (QSqlDatabase)
- glib (gio for file watching)

Follow DTE patterns:
- DTK widgets signals/slots
- glib GSettings for config
- Error handling: qDebug for dev, user-facing messages via signal.

Report progress via inbox for T2 and T3." \
    wsh claude

# Agent 3: Frontend Specialist (QML/DTK)
clawteam spawn \
    --team $TEAM_NAME \
    --agent-name frontend-agent \
    --task "You are a Qt/QML UI developer specializing in DTE applications.

Your tasks:
1. Wait for T3 (Search API) to complete
2. Complete T4 (Search UI)

Implementation notes:
- Create QML components: AISearchBar.qml, SearchResultsListView.qml
- Create C++ model: src/models/AISearchModel.{h,cpp}
- Connect to backend SearchService via signals/slots
- Use DTK components: DLineEdit, DListView, DLabel

Features:
- Debounced input: QTimer with 300ms delay
- Progressive results: update model as API returns data
- Relevance badges: color-coded (green/yellow/gray)
- Search history: store最近10次搜索 in DSettings

UI Layout:
```
[AISearchBar]  (top bar)
──────────────
[List View     (results)
 with badges]
──────────────
[History       (suggestions
 suggestions]  dropdown)
```

DTE Guidelines:
- Follow DWidget theme (dark/light mode)
- Use DFontSizeManager for consistent typography
- Keyboard shortcuts: Ctrl+F focus search, Esc clear
- Accessibility: support screen readers

Tools:
- QML Designer
- Qt Quick 2.12+
- DTKWidget DLineEdit, DListView

Report completion via inbox." \
    wsh claude

# Agent 4: Testing Specialist (pytest + Qt Test)
clawteam spawn \
    --team $TEAM_NAME \
    --agent-name test-agent \
    --task "You are a QA engineer with expertise in Qt and Python testing.

Your tasks:
1. Wait for T4 (UI) to complete
2. Complete T5 (Tests)

Test strategy:
- Unit tests: pytest for Python backend (if any), Qt Test for C++ classes
- Integration tests: Test API endpoint + UI interaction
- Performance tests: Measure indexing speed and search latency

Tests to write:

1. Unit tests (tests/unit/):
   - test_embedding_service.cpp: Test vector generation, storage
   - test_search_service.cpp: Test query processing, ranking
   - Mock embedding service (avoid loading ONNX model in unit tests)

2. Integration tests (tests/integration/):
   - test_search_api.cpp: Test POST /api/search with various queries
   - test_search_ui.py: Test UI interaction with real backend

3. Performance tests (tests/performance/):
   - test_indexing_speed.cpp: Index 1000 files, measure time (>500/sec target)
   - test_search_latency.cpp: 100 queries, measure avg/95th percentile (<500ms target)
   - test_memory_usage.cpp: Index 10k files, measure peak memory (<200MB target)

Tools:
- Qt Test framework
- pytest
- pytest-benchmark for Python tests
- valgrind for memory leak detection

Coverage goal: >80% for core classes (EmbeddingService, SearchService)

Test execution:
- Run on CI: GitHub Actions or similar
- Use mock data for offline testing
- Regression test for known bugs

Report completion via inbox." \
    wsh claude

# 验证点：4 个 agents 并行启动
ps aux | grep -E "db-agent|backend-agent|frontend-agent|test-agent"
# 预期：4 个进程运行
```

### Step 5: 监控依赖解析和任务执行

```bash
#!/bin/bash
# Leader 协调循环脚本

TEAM_NAME="ai-search-dev-$(date +%Y%m%d%H%M%S)"

monitor_workflow() {
    echo "=== Monitoring AI Search Development Workflow ==="
    
    for iteration in {1..60}; do
        echo "=== Iteration $iteration ==="
        
        # 显示当前任务状态
        clawteam board show $TEAM_NAME
        
        # 检查 inbox 消息
        messages=$(clawteam inbox receive $TEAM_NAME --agent leader)
        if [ -n "$messages" ]; then
            echo "=== Agent Messages ==="
            echo "$messages"
            
            # 分析消息
            # - "T1 completed" → T2 应该 auto-unblock
            # - "T2 completed" → T3 应该 auto-unblock
            # - "T3 completed" → T4 应该 auto-unblock
            # - "T4 completed" → T5 应该 auto-unblock
        fi
        
        # 统计各状态
        pending=$(clawteam task list $TEAM_NAME --status pending --json | jq '. | length')
        in_progress=$(clawteam task list $TEAM_NAME --status in_progress --json | jq '. | length')
        completed=$(clawteam task list $TEAM_NAME --status completed --json | jq '. | length')
        
        echo "Pending: $pending | In Progress: $in_progress | Completed: $completed"
        
        # 检查是否所有任务完成
        if [ $completed -eq 5 ]; then
            echo "=== All tasks completed! ==="
            break
        fi
        
        # 如果某个任务卡住太久（超过 20 分钟），nudge
        # (简化：这里只做演示)
        
        sleep 60
    done
}

# 启动监控（在后台）
monitor_workflow > /tmp/ai-search-monitor.log 2>&1 &
MONITOR_PID=$!

# 同时查看 live board
clawteam board live $TEAM_NAME --interval 10

# 监控完成后，kill 进程
kill $MONITOR_PID
```

### 验证点清单（步骤 1-5）

- [ ] Plan Agent 创建 task 目录和 prd.md
- [ ] 5 个子任务创建（T1-T5），依赖链正确
- [ ] Worktree 创建成功
- [ ] 4 个专业化 agents 并行启动
- [ ] T1 完成 → T2 auto-unblock
- [ ] T2 完成 → T3 auto-unblock
- [ ] T3 完成 → T4 auto-unblock
- [ ] T4 完成 → T5 auto-unblock
- [ ] T5 完成 → 所有任务完成

---

### Step 6: 验证各部分实现

```bash
# 验证 T1: Database schema
echo "=== Verifying T1: Database Schema ==="

# 检查 migration script
cat migrations/003_add_ai_search.sql
# 预期包含：
# CREATE TABLE files (...);
# CREATE TABLE embeddings (...);
# CREATE VIRTUAL TABLE fts_index USING fts5(...);

# 测试 schema
sqlite3 test.db < migrations/003_add_ai_search.sql
sqlite3 test.db ".schema"
# 验证：tables created

# 验证 T2: Embedding service
echo "=== Verifying T2: Embedding Service ==="

# 检查 C++ 类
cat src/services/EmbeddingService.h
# 预期：
class EmbeddingService : public QObject {
    Q_OBJECT
public:
    explicit EmbeddingService(QObject *parent = nullptr);
    QStringList generateEmbeddings(const QStringList &files);
private:
    ONNXSession *m_onnxSession;  // ONNX runtime session
};

# 检查集成
cat src/services/EmbeddingService.cpp | grep "onnxruntime"
# 验证：使用 ONNX Runtime API

# 验证 T3: Search API
echo "=== Verifying T3: Search API ==="

# 检查 API endpoint
cat src/api/search.cpp
# 预期：
// POST /api/search
// Request: { "query": "..." }
// Response: JSON array with files and scores

# 测试 API（mock backend 后）
curl -X POST http://localhost:8080/api/search \
    -H "Content-Type: application/json" \
    -d '{"query": "test query"}'
# 预期：返回 JSON 数据

# 验证 T4: Search UI
echo "=== Verifying T4: Search UI ==="

# 检查 QML 文件
cat com.deepin.ddeFileManager/views/AISearchBar.qml
# 预期：
import DTK 1.0 as D
D.DLineEdit {
    placeholder: "Search naturally (e.g., 'find presentations last week')"
}

# 检查 model
cat src/models/AISearchModel.cpp
# 预期：QAbstractListModel 实现，连接到 API

# 验证 T5: Tests
echo "=== Verifying T5: Tests ==="

# 运行单元测试
ctest --test-dir build/tests/unit -V

# 预期：所有 tests PASSED

# 运行集成测试
pytest tests/integration/ -v

# 运行性能测试
build/tests/performance/test_indexing_speed
build/tests/performance/test_search_latency

# 预期：
# - Indexing speed > 500 files/sec
# - Search latency avg < 500ms
# - Memory usage < 200MB for 10k files
```

---

### Step 7: Trellis 集成 - 记录开发过程

```bash
# 每个 agent 完成任务后记录 session

# db-agent 完成
python3 .trellis/scripts/add_session.py \
    --title "AI Search: Database Schema Design" \
    --commit $(git rev-parse HEAD) \
    --summary "Designed SQLite schema for AI search. Tables: files, embeddings, fts_index. Migration script: 003_add_ai_search.sql. Key decision: Use SQLite BLOB for vectors (portability > performance). Issue: Vector indexing not efficient, but acceptable for <100k files."

# backend-agent 完成 T2
python3 .trellis/scripts/add_session.py \
    --title "AI Search: Embedding Service Implementation" \
    --commit $(git rev-parse HEAD) \
    --summary "Implemented EmbeddingService using ONNX Runtime. Model: all-MiniLM-L6-v2 (384-dim). Indexing speed: 1200 files/sec (target: >500/sec). Key classes: IndexService (scan files), EmbeddingService (generate vectors). Performance: QThreadPool for parallel file processing. Memory: 50MB for 10k files. Integration with glib gio for file watching."

# backend-agent 完成 T3
python3 .trellis/scripts/add_session.py \
    --title "AI Search: Search API Implementation" \
    --commit $(git rev-parse HEAD) \
    --summary "Implemented Search API endpoint at POST /api/search. Response time: avg 200ms (target: <500ms). Features: vector similarity search (sqlite custom function), FTS5 full-text backup, query expansion. Classes: SearchService with search(query) method. Return format: JSON array with path, score, file_type."

# frontend-agent 完成 T4
python3 .trellis/scripts/add_session.py \
    --title "AI Search: UI Implementation" \
    --commit $(git rev-parse HEAD) \
    --summary "Built AI search UI with DTK components. Components: AISearchBar.qml (debounced 300ms), SearchResultsListView.qml (relevance badges), AISearchModel.cpp (QAbstractListModel). Performance: UI responds in <100ms to API results. UX: Search history (last 10 queries stored in DSettings). Accessibility: Screen reader support, keyboard shortcuts (Ctrl+F, Esc)."

# test-agent 完成 T5
python3 .trellis/scripts/add_session.py \
    --title "AI Search: Test Suite" \
    --commit $(git rev-parse HEAD) \
    --summary "Wrote comprehensive test suite: Unit tests (EmbeddingService, SearchService), Integration tests (API + UI), Performance tests (indexing: 1200 fi/s, search: 200ms avg, memory: 50MB/10k files). Coverage: 82% for core classes. Tools: Qt Test, pytest, pytest-benchmark. CI: GitHub Actions configured."

# 验证点：所有 sessions 记录
cat .trellis/workspace/$USER/journal-*.md | grep -A 5 "AI Search"
# 预期：显示 5 个 session 记录
```

---

### Step 8: 更新 Spec 文档（知识累积）

```bash
# 更新 backend AI integration patterns

cat >> .trellis/spec/backend/ai-integration.md << 'EOF'
# AI Integration Patterns for DTE Applications

## File Indexing with Embeddings

**Pattern**: Background service using QThreadPool

**Implementation**:
\`\`\`cpp
class IndexService : public QObject {
    QThreadPool m_threadPool;
    void indexFiles(const QStringList &paths) {
        // Don't block UI - use thread pool
        for (const QString &path : paths) {
            QRunnable *task = new IndexFileTask(path);
            m_threadPool.start(task);
        }
    }
};
\`\`\`

**Libraries**:
- ONNX Runtime (cross-platform model execution)
- Sentence-Transformers models (all-MiniLM-L6-v2 recommended)
- SQLite BLOB (vector storage, portability > performance)

**Performance Targets**:
- Indexing speed: >500 files/sec
- Search latency: <500ms (95th percentile)
- Memory usage: <200MB for 10k files

**Discovery**: DDE AI Search feature development
EOF

# 更新 frontend AI UI patterns

cat >> .trellis/spec/frontend/ai-ui-patterns.md << 'EOF'
# AI-Powered UI Patterns in DTK

## Natural Language Search UI

**Components**:
- DLineEdit for search input (debounced 300ms via QTimer)
- DListView for results (custom delegate for relevance badges)
- DPopup for search history suggestions

**Debouncing**:
\`\`\`qml
Timer {
    id: searchTimer
    interval: 300
    onTriggered: performSearch()
}

onTextChanged: {
    searchTimer.restart()
}
\`\`\`

**Relevance Indicators**:
- High (score >0.8): Green badge (DColorScheme.highlight)
- Medium (0.5-0.8): Yellow badge (DColorScheme.warning)
- Low (<0.5): Gray badge (DColorScheme.placeholderText)

**UX Best Practices**:
- Progressive results (show as available, no blocking)
- Search history (last 10 queries in DSettings)
- Keyboard shortcuts (Ctrl+F focus, Esc clear)
- Accessibility (screen reader support, keyboard navigation)

**Discovery**: DDE AI Search feature development
EOF

# 更新 performance guidelines

cat >> .trellis/spec/backend/performance-optimization.md << 'EOF'
# Performance Optimization for AI Features

## Vector Database Trade-offs

**Options**:
| Approach | Pros | Cons | Use Case |
|----------|------|------|----------|
| SQLite + BLOB | Portable, simple | Slow for 100k+ files | Small-medium scale (<100k) |
| PostgreSQL + pgvector | Fast, scalable | Complex setup, requires DB server | Large scale (100k-1M files) |
| Faiss (in-memory) | Fastest | Memory-intensive, no persistence | Real-time, small batch |

**Decision for DDE AI Search**:
- Use SQLite + BLOB (portability critical for desktop apps)
- Add FTS5 for full-text search complement
- Performance acceptable for <100k files (<90% users)

**Discovery**: DTE AI Search feature - evaluated 3 options
EOF

# 验证点：Spec 文档更新
cat .trellis/spec/backend/ai-integration.md | grep "DDE AI Search"
# 预期：显示相关段落
```

---

### Step 9: 集成测试和手动验证

```bash
# 编译完整项目
mkdir -p build && cd build
cmake -DCMAKE_BUILD_TYPE=Release ..
make -j$(nproc)

# 运行单元测试
ctest --test-dir build/tests/unit --output-on-failure

# 运行集成测试
pytest tests/integration/ -v

# 手动验证 UI
echo "=== Manual UI Verification ==="
export QT_DEBUG_PLUGINS=1
export DISPLAY=:0

# 运行 DDE file manager
./dde-file-manager

# 测试步骤：
# 1. 按 Ctrl+F 聚焦搜索栏
# 2. 输入查询："marketing presentations last week"
# 3. 观察：300ms 后开始显示结果
# 4. 检查：结果按相关性排序（绿/黄/灰 badge）
# 5. 点击结果：文件管理器导航到文件位置
# 6. 按 Esc 清空搜索
# 7. 再次按 Ctrl+F：显示最近搜索历史

# 预期行为：
# - 搜索栏显示 "Search naturally..." placeholder
# - 实时更新结果（无延迟卡顿）
# - Relevance badge 颜色正确
# - 搜索历史建议显示
# - 键盘快捷键生效

# 性能监控（外部工具）
# 使用 perf/profiler 测量：
# - 索引 1000 个文件的耗时
# - 搜索查询的平均延迟
# - 内存峰值使用

# 预期：
# - 索引: <2 秒 for 1000 files
# - 搜索: <500ms 95th percentile
# - 内存: <100MB for 1k files
```

---

### Step 10: 创建 PR

```bash
# 使用 Trellis create_pr.py
TASK_DIR=".trellis/tasks/04-XX-ai-file-search"
python3 .trellis/scripts/multi_agent/create_pr.py $TASK_DIR --dry-run

# 验证 PR 内容（dry-run 显示）
# 预期：
# - Commit message: feat(core): AI file search feature
# - PR title: feat(core): AI file search feature
# - Body: 来自 prd.md 的内容

# 真实创建 PR（在验证所有测试后）
python3 .trellis/scripts/multi_agent/create_pr.py $TASK_DIR

# PR URL: https://github.com/linuxdeepin/dde-file-manager/pull/XXX

# 验证：PR 创建成功
gh pr view XXX
# 预期：显示 PR 状态（draft）

# Step 11: 清理
clawteam team cleanup $TEAM_NAME --force

# 归档 Trellis task
python3 .trellis/scripts/task.py archive ai-file-search
```

---

### 测试用例完整验证清单

```bash
# 运行完整验证脚本
cat > /tmp/verify-ai-search-feature.sh << 'EOF'
#!/bin/bash

echo "=== Verification Script for AI Search Feature ==="

# 1. 验证 Plan Agent 输出
echo "1. Verifying plan output..."
if [ -f ".trellis/tasks/04-XX-ai-file-search/task.json" ]; then
    echo "   ✓ task.json exists"
elif [ -f ".trellis/tasks/*-ai-file-search/task.json" ]; then
    echo "   ✓ task.json exists (found)"
else
    echo "   ✗ task.json NOT found"
    exit 1
fi

if [ -f ".trellis/tasks/*/ai-file-search/prd.md" ] || [ -f ".trellis/tasks/*-ai-file-search/prd.md" ]; then
    echo "   ✓ prd.md exists"
else
    echo "   ✗ prd.md NOT found"
    exit 1
fi

# 2. 验证 ClawTeam task structure
echo "2. Verifying ClawTeam tasks..."
# (假设 TEAM_NAME 已设置)
task_count=$(clawteam task list $TEAM_NAME --json | jq '. | length')
if [ $task_count -eq 5 ]; then
    echo "   ✓ 5 tasks created"
else
    echo "   ✗ Expected 5 tasks, found $task_count"
    exit 1
fi

# 3. 验证依赖链
echo "3. Verifying dependency chain..."
t1_status=$(clawteam task list $TEAM_NAME --json | jq '.[0].status')
# T1 should be completed (假设已完成)
if [ "$t1_status" = "completed" ]; then
    echo "   ✓ T1 completed"
fi

# 4. 验证代码实现
echo "4. Verifying code implementation..."

if [ -f "migrations/003_add_ai_search.sql" ]; then
    echo "   ✓ Migration script exists"
else
    echo "   ✗ Migration script NOT found"
fi

if [ -f "src/services/EmbeddingService.h" ]; then
    echo "   ✓ EmbeddingService.h exists"
else
    echo "   ✗ EmbeddingService.h NOT found"
fi

if [ -f "src/api/search.cpp" ]; then
    echo "   ✓ Search API exists"
else
    echo "   ✗ Search API NOT found"
fi

if [ -f "com.deepin.ddeFileManager/views/AISearchBar.qml" ]; then
    echo "   ✓ Search UI QML exists"
else
    echo "   ✗ Search UI QML NOT found"
fi

# 5. 验证测试
echo "5. Verifying tests..."

if [ -d "tests/unit/" ]; then
    test_count=$(find tests/unit/ -name "*.cpp" | wc -l)
    if [ $test_count -gt 0 ]; then
        echo "   ✓ $test_count unit tests exist"
    fi
fi

# 6. 验证 Trellis sessions
echo "6. Verifying Trellis sessions..."

session_count=$(grep -c "AI Search:" .trellis/workspace/*/journal-*.md 2>/dev/null)
if [ $session_count -ge 5 ]; then
    echo "   ✓ $session_count sessions recorded"
else
    echo "   ✗ Expected >=5 sessions, found $session_count"
fi

# 7. 验证 spec 更新
echo "7. Verifying spec updates..."

if grep -q "DDE AI Search" .trellis/spec/backend/ai-integration.md 2>/dev/null; then
    echo "   ✓ AI integration spec updated"
else
    echo "   ℹ AI integration spec may not be updated (first feature)"
fi

echo "=== Verification Complete ==="
EOF

chmod +x /tmp/verify-ai-search-feature.sh
bash /tmp/verify-ai-search-feature.sh
```

---

## 测试用例 2：依赖链异常处理

### 测试场景：T2 失败，T3/T4/T5 被阻塞

```bash
# 模拟：T2 (Embedding service) 失败（无法加载 ONNX 模型）
# 验证：T3/T4/T5 保持 blocked 状态，Leader 介入

TEAM_NAME="dep-failure-test-$(date +%Y%m%d%H%M%S)"
clawteam team spawn-team $TEAM_NAME -d "Dependency failure test" -n leader

# 创建任务（同测试用例 1，但 T2 会失败）
# ... (创建 T1, T2, T3, T4, T5) ...

# Spawn agents
# ... (与测试用例 1 相同) ...

# 等待 T1 完成，T2 开始但失败
sleep 300

# 检查状态
clawteam board show $TEAM_NAME
# 预期：
# - T1: completed
# - T2: in_progress (but marked as failed via inbox)
# - T3: blocked (by T2)
# - T4: blocked (by T2)
# - T5: blocked (by T2)

# 检查 inbox
messages=$(clawteam inbox receive $TEAM_NAME --agent leader)
echo "$messages"
# 预期：包含 "T2 FAILED: Unable to load ONNX model" 消息

# Leader 介入：修复 T2 依赖项
# (模拟：提供模拟 ONNX 模型或配置替代方案)

clawteam inbox send $TEAM_NAME backend-agent "T2 intervention: Use mock ONNX session for testing. Set environment variable DTE_USE_MOCK_EMBEDDING=1."

# T2 恢复并完成
# 预期：T2 标记为 completed
# 预期：T3 auto-unblock

cleawteam team cleanup $TEAM_NAME --force
```

### 验证点清单

- [ ] T2 失败后报告错误
- [ ] T3/T4/T5 保持 blocked
- [ ] Leader 收到失败消息
- [ ] Leader 发送修复指令
- [ ] T2 恢复并完成
- [ ] T3 auto-unblock

---

## 测试用例 3：并发冲突处理

### 测试场景：Frontend 和 Backend 同时修改同一文件

```bash
# 模拟：Frontend 改 API URL，Backend 也改 API URL
# 验证：Git 合并时正确处理冲突

TEAM_NAME="conflict-test-$(date +%Y%m%d%H%M%S)"
clawteam team spawn-team $TEAM_NAME -d "Merge conflict test" -n leader

# 简化：只有 2 个任务（T3: Backend API, T4: Frontend UI，都依赖 T2）
# ... (创建 T3, T4) ...

# Spawn 2 个 agents（在同一 worktree 不同文件，但有潜在冲突）
# ... (spawn backend-agent, frontend-agent) ...

# 等待完成后
# ... (等待 T3, T4 completed) ...

# 合并 worktrees
clawteam workspace merge $TEAM_NAME backend-agent
clawteam workspace merge $TEAM_NAME frontend-agent

# 如果有冲突，手动解决
# 预期：如果冲突，Git 会提示

# 验证点：
# - 如果无冲突：合并成功
# - 如果有冲突：需要手动干预（leader 决策）

# 清理
clawteam team cleanup $TEAM_NAME --force
```

### 验证点清单

- [ ] 并发修改被检测
- [ ] Git 合并正确处理冲突
- [ ] Leader 介入决策冲突
- [ ] 最终合并成功

---

## 边界条件测试

### 测试用例：大文件搜索性能

```bash
# 测试：搜索 10k+ 文件
# 验证：性能在可接受范围内

TEAM_NAME="large-file-test-$(date +%Y%m%d%H%M%S)"

# ... (创建完整功能，同测试用例 1) ...

# 测试性能：
# 1. 索引 10k 文件
# 2. 执行 100 次搜索查询
# 3. 测量资源使用

# 预期：
# - 索引时间: <20 秒（10k files）
# - 搜索延迟: <500ms 95th percentile
# - 内存峰值: <200MB

# 如果超出目标：
# - 优化索引批处理
# - 使用更高效的数据结构
# - 限制搜索结果数量

clawteam team cleanup $TEAM_NAME --force
```

---

## 清理和验证清单

### 测试后清理

```bash
# 清理所有 development teams
for team in $(ls ~/.clawteam/teams/ | grep "^ai-search-"); do
    clawteam team cleanup $team --force
done

# 清理 worktrees
git worktree prune

# 清理测试 reports
rm -f /tmp/ai-search-*.md

# 清理 Trellis tasks
for task in $(ls -d .trellis/tasks/*/ai-* 2>/dev/null); do
    python3 .trellis/scripts/task.py archive $(basename $task)
done
```

### 最终验证清单

- [ ] 所有测试用例通过
- [ ] 功能完整实现（DB, Backend, UI, 测试）
- [ ] 性能目标达成（索引速度、搜索延迟）
- [ ] Trellis 集成正常（sessions 记录, spec 更新）
- [ ] 依赖链正常（auto-unblock）
- [ ] PR 创建成功
- [ ] 清理后无残留

---

## 预期测试结果

| 测试用例 | 预期结果 | 成功标准 |
|---------|---------|---------|
| 完整功能开发 | 5 个任务完成依赖链 | 通过 |
| 依赖异常处理 | T2 失败后恢复，T3 auto-unblock | 通过 |
| 并发冲突 | Git 合并正确或 Leader 决策 | 通过 |
| 大文件性能 | 10k files <20s 索引, <500ms 搜索 | 通过 |

---

## 测试失败处理

如果任何测试失败：

1. **查看 agent logs**：
   ```bash
   ~/.clawteam/workspaces/.trellis/workspaces/worktrees/<branch>/.agent-log
   ```

2. **检查依赖状态**：
   ```bash
   clawteam task list $TEAM_NAME --status blocked --json
   ```

3. **手动 unblock**：
   ```bash
   # 如果 auto-unblock 失败
   clawteam task update $TEAM_NAME <T3-id> --status pending
   ```

4. **清理重试**：
   ```bash
   clawteam team cleanup $TEAM_NAME --force
   # 重新运行测试
   ```

---

## 测试执行命令（一键运行）

```bash
# 运行所有测试
./run-ai-search-feature-tests.sh

# 运行单个测试
./test-complete-ai-search-feature.sh
./test-dependency-failure.sh
./test-conflict-resolution.sh
./test-large-file-performance.sh
```

---

**文档版本**: 1.0
**最后更新**: 2026-04-07
**测试环境**: ClawTeam v0.3.0 + Trellis latest
