# WshBackend 实施计划

**状态**: 待实施  
**创建日期**: 2026-03-25  
**目标**: 为 ClawTeam 添加 wsh (TideTerm/WaveTerm) 后端支持，实现与 tmux 等价的功能

---

## 1. 概述

### 1.1 背景

ClawTeam 目前支持两种 spawn 后端：
- `tmux` - 在 tmux 窗口中启动 agent，支持交互式监控
- `subprocess` - 作为独立进程启动 agent，fire-and-forget

本计划添加第三种后端 `wsh`，支持 TideTerm/WaveTerminal 的 block 系统。

### 1.2 目标

1. 实现与 `TmuxBackend` 功能对等的 `WshBackend`
2. 自动检测环境：存在 `wsh` 命令时优先使用
3. 支持内容捕获、输入注入、存活检测等核心功能
4. 保持与现有代码架构的一致性

### 1.3 范围

**包含**：
- `WshBackend` 类实现
- RPC 通信封装
- 内容捕获和输入注入
- 自动检测和后端选择逻辑
- 注册表集成
- 单元测试

**不包含**：
- 平铺显示（依赖 TideTerm GUI）
- Attach 功能（依赖 TideTerm GUI）
- 远程 SSH 连接管理

---

## 2. 技术设计

### 2.1 文件结构

```
clawteam/spawn/
├── __init__.py          # 修改: get_backend() 添加 wsh 支持
├── base.py              # 不变
├── tmux_backend.py      # 不变
├── subprocess_backend.py # 不变
├── wsh_backend.py       # 新增: WshBackend 实现
├── wsh_rpc.py           # 新增: RPC 通信封装
└── registry.py          # 修改: 添加 wsh 后端存活检测
```

### 2.2 类设计

#### 2.2.1 WshBackend

```python
class WshBackend(SpawnBackend):
    """Spawn agents in TideTerm/WaveTerminal blocks.
    
    Each agent gets its own block with isolated terminal session.
    Terminal output is captured via wavefile protocol.
    Input is injected via JSON-RPC over Unix socket.
    """
    
    def __init__(self):
        self._blocks: dict[str, str] = {}  # agent_name -> block_id
        self._adapter = NativeCliAdapter()
        self._rpc_client: WshRpcClient | None = None
    
    def spawn(self, command, agent_name, agent_id, agent_type, 
              team_name, prompt=None, env=None, cwd=None, 
              skip_permissions=False) -> str:
        """Spawn a new agent in a TideTerm block."""
        ...
    
    def list_running(self) -> list[dict[str, str]]:
        """List currently running agents."""
        ...
```

#### 2.2.2 WshRpcClient

```python
class WshRpcClient:
    """JSON-RPC client for TideTerm server communication.
    
    Communicates over Unix socket at ~/.local/share/tideterm/tideterm.sock
    """
    
    SOCKET_PATH = Path.home() / ".local/share/tideterm/tideterm.sock"
    
    def __init__(self):
        self._socket_path = self._resolve_socket_path()
    
    def send_input(self, block_id: str, data: str, is_base64: bool = False) -> bool:
        """Send input to a terminal block.
        
        Args:
            block_id: Target block UUID
            data: Input data (string or base64)
            is_base64: If True, data is already base64 encoded
        """
        ...
    
    def send_signal(self, block_id: str, signal: str) -> bool:
        """Send signal to a terminal block (e.g., SIGINT, SIGTERM)."""
        ...
    
    def get_block_info(self, block_id: str) -> dict | None:
        """Get block metadata."""
        ...
    
    def is_connected(self) -> bool:
        """Check if TideTerm server is reachable."""
        ...
```

### 2.3 命名策略

| 实体 | tmux 命名 | wsh 命名 |
|------|----------|----------|
| Session | `clawteam-{team_name}` | workspace (使用现有或新建) |
| Window/Pane | `{session}:{agent_name}` | block (UUID，通过 metadata 关联) |
| Block 标题 | 窗口名 | 通过 `frame:title` metadata 设置 |

**Block 追踪**：
- 使用 `wsh blocks list --json` 获取所有 blocks
- 在 block metadata 中存储 `clawteam:team` 和 `clawteam:agent` 标识
- 注册表中记录 `block_id` 替代 `tmux_target`

---

## 3. 核心功能实现

### 3.1 内容捕获

**实现方式**：`wsh file cat wavefile://{block_id}/term`

```python
def capture_terminal_output(block_id: str, tail_lines: int = 100) -> str:
    """Capture terminal output from a block.
    
    Equivalent to: tmux capture-pane -p -t <target>
    """
    result = subprocess.run(
        ["wsh", "file", "cat", f"wavefile://{block_id}/term"],
        capture_output=True,
        text=True,
        timeout=10
    )
    if result.returncode != 0:
        return ""
    
    # Return last N lines if tail_lines specified
    if tail_lines > 0:
        lines = result.stdout.splitlines()
        return "\n".join(lines[-tail_lines:])
    return result.stdout
```

### 3.2 输入注入

**实现方式**：JSON-RPC `ControllerInputCommand`

```python
def inject_prompt(block_id: str, prompt: str) -> bool:
    """Inject prompt into a terminal block.
    
    Equivalent to: tmux send-keys -t <target> "<prompt>" Enter
    """
    import base64
    
    # Add newline if not present
    if not prompt.endswith("\n"):
        prompt = prompt + "\n"
    
    # Encode to base64
    data_b64 = base64.b64encode(prompt.encode("utf-8")).decode("ascii")
    
    # Send RPC
    client = WshRpcClient()
    return client.send_input(block_id, data_b64, is_base64=True)
```

**RPC 消息格式**：

```json
{
  "jsonrpc": "2.0",
  "method": "ControllerInputCommand",
  "params": {
    "blockid": "bdb2d9e8-ff7a-4a56-9ac5-c708b3050ca6",
    "inputdata64": "bHMgLWxhCg=="
  },
  "id": 1
}
```

### 3.3 信号发送

```python
def send_signal(block_id: str, signal_name: str) -> bool:
    """Send signal to a terminal block.
    
    Equivalent to: tmux send-keys -t <target> C-c
    Supported signals: SIGINT, SIGTERM, SIGHUP, etc.
    """
    client = WshRpcClient()
    return client.send_signal(block_id, signal_name)
```

### 3.4 Block 创建

```python
def spawn_agent(command: list[str], agent_name: str, team_name: str,
                cwd: str, env: dict) -> str:
    """Create a new block for the agent."""
    
    # Build full command with environment
    env_exports = "; ".join(f"export {k}={shlex.quote(v)}" for k, v in env.items())
    cmd_str = " ".join(shlex.quote(c) for c in command)
    
    # Add exit hook
    exit_hook = f"clawteam lifecycle on-exit --team {shlex.quote(team_name)} --agent {shlex.quote(agent_name)}"
    full_cmd = f"{env_exports}; {cmd_str}; {exit_hook}"
    
    # Create block
    result = subprocess.run(
        ["wsh", "run", "--cwd", cwd, "--", "sh", "-c", full_cmd],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        return f"Error: failed to create block: {result.stderr}"
    
    # Parse block ID from output: "run block created: block:xxx-xxx-xxx"
    match = re.search(r"block:([a-f0-9-]+)", result.stdout)
    if not match:
        return "Error: could not parse block ID from wsh output"
    
    block_id = match.group(1)
    
    # Set metadata for tracking
    subprocess.run([
        "wsh", "setmeta", "-b", block_id,
        f"clawteam:team={team_name}",
        f"clawteam:agent={agent_name}",
        f"frame:title={agent_name}"
    ], capture_output=True)
    
    return f"Agent '{agent_name}' spawned in wsh block ({block_id})"
```

### 3.5 存活检测

```python
def is_block_alive(block_id: str) -> bool:
    """Check if a block is still running.
    
    Equivalent to: tmux list-panes -t <target>
    """
    result = subprocess.run(
        ["wsh", "blocks", "list", "--json"],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        return False
    
    blocks = json.loads(result.stdout)
    for block in blocks:
        if block.get("blockid") == block_id:
            # Check if block has a running process
            meta = block.get("meta", {})
            # If controller is "shell", block is running
            return meta.get("controller") in ("shell", "cmd")
    
    return False
```

### 3.6 工作区信任检测

```python
def check_workspace_trust(block_id: str, command: list[str], timeout: float = 5.0) -> bool:
    """Check and auto-confirm workspace trust prompts.
    
    Polls block output for trust dialog patterns and sends Enter to confirm.
    """
    if not (is_claude_command(command) or is_codex_command(command)):
        return False
    
    start_time = time.monotonic()
    while time.monotonic() - start_time < timeout:
        output = capture_terminal_output(block_id, tail_lines=20)
        output_lower = output.lower()
        
        if _looks_like_trust_prompt(command, output_lower):
            # Send Enter to confirm
            inject_prompt(block_id, "")
            return True
        
        time.sleep(0.2)
    
    return False
```

---

## 4. 实现步骤

### Phase 1: 基础框架 (Day 1)

#### 任务 1.1: 创建 WshRpcClient

**文件**: `clawteam/spawn/wsh_rpc.py`

**内容**：
- Unix socket 连接管理
- JSON-RPC 消息发送/接收
- 错误处理和重试逻辑
- 连接状态检测

**验收标准**：
- [ ] 能够连接到 TideTerm socket
- [ ] 能够发送 RPC 请求并接收响应
- [ ] 有完善的错误处理

#### 任务 1.2: 创建 WshBackend 骨架

**文件**: `clawteam/spawn/wsh_backend.py`

**内容**：
- 类定义和 `__init__`
- `spawn()` 方法骨架
- `list_running()` 方法骨架
- 辅助方法占位

**验收标准**：
- [ ] 类结构完整
- [ ] 方法签名与 `SpawnBackend` 一致
- [ ] 导入无错误

### Phase 2: 核心功能 (Day 2-3)

#### 任务 2.1: 实现 spawn()

**关键步骤**：
1. 检查 wsh 可用性
2. 构建命令行（环境变量、退出钩子）
3. 调用 `wsh run` 创建 block
4. 解析返回的 block ID
5. 设置 metadata
6. 注册到 registry

**依赖**：任务 1.1, 1.2

#### 任务 2.2: 实现内容捕获

**关键步骤**：
1. 调用 `wsh file cat wavefile://{block_id}/term`
2. 处理输出格式
3. 支持行数限制

**依赖**：任务 2.1

#### 任务 2.3: 实现输入注入

**关键步骤**：
1. 封装 `ControllerInputCommand` RPC
2. Base64 编码输入数据
3. 支持信号发送（SIGINT 等）

**依赖**：任务 1.1

#### 任务 2.4: 实现存活检测

**关键步骤**：
1. 调用 `wsh blocks list --json`
2. 检查 block 状态
3. 更新 registry 集成

**依赖**：任务 2.1

### Phase 3: 高级功能 (Day 4)

#### 任务 3.1: CLI 就绪检测

**内容**：
- 轮询终端输出
- 检测提示符模式
- 实现超时和回退

**依赖**：任务 2.2, 2.3

#### 任务 3.2: 工作区信任自动确认

**内容**：
- 检测 Claude/Codex/Gemini 信任对话框
- 自动发送确认

**依赖**：任务 3.1

#### 任务 3.3: Prompt 注入

**内容**：
- 实现 `_inject_prompt_via_rpc()` 
- 支持多行 prompt
- 支持特殊字符

**依赖**：任务 2.3, 3.1

### Phase 4: 集成和测试 (Day 5)

#### 任务 4.1: 更新 get_backend()

**文件**: `clawteam/spawn/__init__.py`

**修改**：
```python
def get_backend(name: str = "auto") -> SpawnBackend:
    """Factory function to get a spawn backend.
    
    Args:
        name: Backend name ("auto", "tmux", "wsh", "subprocess")
              "auto" selects wsh > tmux > subprocess by availability
    """
    if name == "auto":
        if shutil.which("wsh") and _wsh_is_connected():
            from clawteam.spawn.wsh_backend import WshBackend
            return WshBackend()
        elif shutil.which("tmux"):
            from clawteam.spawn.tmux_backend import TmuxBackend
            return TmuxBackend()
        else:
            from clawteam.spawn.subprocess_backend import SubprocessBackend
            return SubprocessBackend()
    elif name == "wsh":
        from clawteam.spawn.wsh_backend import WshBackend
        return WshBackend()
    elif name == "subprocess":
        from clawteam.spawn.subprocess_backend import SubprocessBackend
        return SubprocessBackend()
    elif name == "tmux":
        from clawteam.spawn.tmux_backend import TmuxBackend
        return TmuxBackend()
    else:
        raise ValueError(f"Unknown spawn backend: {name}. Available: auto, tmux, wsh, subprocess")

def _wsh_is_connected() -> bool:
    """Check if TideTerm server is reachable."""
    socket_path = Path.home() / ".local/share/tideterm/tideterm.sock"
    if not socket_path.exists():
        return False
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(1.0)
        sock.connect(str(socket_path))
        sock.close()
        return True
    except (socket.error, socket.timeout):
        return False
```

#### 任务 4.2: 更新 registry.py

**修改**：
- `is_agent_alive()` 添加 wsh 后端检测
- `stop_agent()` 添加 wsh block 终止逻辑

```python
def is_agent_alive(team_name: str, agent_name: str) -> bool | None:
    registry = get_registry(team_name)
    info = registry.get(agent_name)
    if not info:
        return None

    backend = info.get("backend", "")
    if backend == "tmux":
        return _tmux_pane_alive(info.get("tmux_target", ""))
    elif backend == "wsh":
        return _wsh_block_alive(info.get("block_id", ""))
    elif backend == "subprocess":
        return _pid_alive(info.get("pid", 0))
    return None

def _wsh_block_alive(block_id: str) -> bool:
    """Check if a wsh block is still alive."""
    if not block_id:
        return False
    result = subprocess.run(
        ["wsh", "blocks", "list", "--json"],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        return False
    try:
        blocks = json.loads(result.stdout)
        for block in blocks:
            if block.get("blockid") == block_id:
                return True
    except json.JSONDecodeError:
        pass
    return False
```

#### 任务 4.3: 单元测试

**文件**: `tests/test_wsh_backend.py`

**测试用例**：
- `test_wsh_not_available` - wsh 不存在时的行为
- `test_spawn_creates_block` - spawn 创建 block
- `test_capture_output` - 内容捕获
- `test_inject_input` - 输入注入
- `test_is_alive` - 存活检测
- `test_registry_integration` - 注册表集成
- `test_backend_selection` - 后端选择逻辑

---

## 5. 接口规范

### 5.1 注册表数据结构

```python
# registry entry for wsh backend
{
    "backend": "wsh",
    "block_id": "bdb2d9e8-ff7a-4a56-9ac5-c708b3050ca6",
    "workspace_id": "6754ea6a-878f-4904-a1ae-abcb24a09938",
    "tab_id": "234c3051-fd56-4ead-9995-9b25c4852038",
    "pid": 12345,  # 如果可获取
    "command": ["claude", "--dangerously-skip-permissions"]
}
```

### 5.2 CLI 接口变更

```bash
# 新增后端选择
clawteam spawn wsh claude --team my-team --agent-name alice --task "..."

# 自动选择（优先 wsh）
clawteam spawn auto claude --team my-team --agent-name bob --task "..."

# 强制使用 tmux
clawteam spawn tmux claude --team my-team --agent-name carol --task "..."

# 查看当前后端
clawteam spawn --help
# 输出: Backend: auto (wsh > tmux > subprocess)
```

### 5.3 配置项

```toml
# ~/.config/clawteam/config.toml

[spawn]
# 默认后端选择策略
# "auto" - 按可用性自动选择 (wsh > tmux > subprocess)
# "wsh" - 强制使用 wsh
# "tmux" - 强制使用 tmux
# "subprocess" - 强制使用 subprocess
default_backend = "auto"

# wsh 特定配置
[spawn.wsh]
# RPC 超时（秒）
rpc_timeout = 10
# 终端输出捕获超时（秒）
capture_timeout = 5
# 输入注入后等待时间（秒）
input_delay = 0.3
```

---

## 6. 测试计划

### 6.1 单元测试

| 测试用例 | 描述 | 预期结果 |
|---------|------|---------|
| `test_wsh_detection` | 检测 wsh 可用性 | 正确返回 True/False |
| `test_block_creation` | 创建 block | 返回有效 block ID |
| `test_metadata_setting` | 设置 metadata | metadata 正确设置 |
| `test_output_capture` | 捕获终端输出 | 返回正确内容 |
| `test_input_injection` | 注入输入 | 输入正确发送 |
| `test_signal_sending` | 发送信号 | 信号正确发送 |
| `test_liveness_check` | 存活检测 | 正确判断状态 |
| `test_block_cleanup` | 清理 block | block 正确删除 |

### 6.2 集成测试

| 测试场景 | 描述 | 验证点 |
|---------|------|-------|
| `test_spawn_claude` | 启动 Claude agent | block 创建、输出捕获 |
| `test_spawn_codex` | 启动 Codex agent | block 创建、输出捕获 |
| `test_multi_agent` | 多 agent 并行 | 独立 block、正确追踪 |
| `test_exit_hook` | 退出钩子执行 | lifecycle on-exit 调用 |
| `test_backend_switch` | 后端切换 | 正确切换后端 |

### 6.3 E2E 测试

使用 `clawteam-dev` 技能运行完整测试：

```bash
# 1. 创建测试团队
clawteam team spawn-team test-wsh -d "Test wsh backend"

# 2. 使用 wsh 后端启动 agent
clawteam spawn wsh claude --team test-wsh --agent-name tester --task "echo hello"

# 3. 验证 block 创建
wsh blocks list --json | jq '.[] | select(.meta["clawteam:team"]=="test-wsh")'

# 4. 验证输出捕获
wsh file cat wavefile://<block_id>/term

# 5. 清理
clawteam team cleanup test-wsh --force
```

---

## 7. 风险和限制

### 7.1 已知限制

| 限制 | 影响 | 缓解措施 |
|------|------|---------|
| 无平铺显示 CLI | 无法通过命令行实现 `tile_panes()` | 文档说明需要在 TideTerm GUI 中操作 |
| 无 attach CLI | 无法通过命令行 attach | 文档说明需要在 TideTerm GUI 中查看 |
| 依赖 TideTerm 运行 | wsh 需要 TideTerm 后端 | 检测连接状态，失败时 fallback |
| RPC 超时 | 大量输出时可能超时 | 设置合理超时，添加重试 |

### 7.2 风险矩阵

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| RPC 接口变更 | 低 | 高 | 版本检测、兼容性处理 |
| Socket 连接失败 | 中 | 高 | 自动重连、fallback |
| Block ID 解析失败 | 低 | 中 | 多种解析方式 |
| 环境变量注入失败 | 低 | 中 | 多种注入方式 |

---

## 8. 文档更新

### 8.1 需要更新的文档

- [ ] `README.md` - 添加 wsh 后端说明
- [ ] `docs/spawn.md` - 添加 wsh 使用示例
- [ ] `AGENTS.md` - 更新 spawn 模块说明
- [ ] `CHANGELOG.md` - 记录新功能

### 8.2 新增文档

- [ ] `docs/wsh-backend.md` - WshBackend 详细文档
- [ ] `docs/troubleshooting-wsh.md` - 常见问题排查

---

## 9. 时间估算

| 阶段 | 任务 | 估算时间 |
|------|------|---------|
| Phase 1 | 基础框架 | 4 小时 |
| Phase 2 | 核心功能 | 8 小时 |
| Phase 3 | 高级功能 | 4 小时 |
| Phase 4 | 集成测试 | 4 小时 |
| 文档 | 文档更新 | 2 小时 |
| **总计** | | **22 小时** |

---

## 10. 验收标准

### 10.1 功能验收

- [ ] `wsh` 后端可正常启动 agent
- [ ] 内容捕获功能正常
- [ ] 输入注入功能正常
- [ ] 存活检测功能正常
- [ ] 注册表集成正常
- [ ] 后端自动选择正常

### 10.2 质量验收

- [ ] 单元测试覆盖率 > 80%
- [ ] 所有测试通过
- [ ] 代码通过 ruff 检查
- [ ] 类型注解完整

### 10.3 文档验收

- [ ] 使用文档完整
- [ ] API 文档完整
- [ ] 示例代码可运行

---

## 11. 参考资料

### 11.1 相关代码

- `clawteam/spawn/tmux_backend.py` - tmux 后端实现
- `clawteam/spawn/subprocess_backend.py` - subprocess 后端实现
- `clawteam/spawn/base.py` - 后端基类
- `clawteam/spawn/registry.py` - 注册表

### 11.2 外部文档

- [Wave Terminal Documentation](https://docs.waveterm.dev/)
- [wsh Command Reference](https://docs.waveterm.dev/wsh-reference)
- [Wave Terminal GitHub](https://github.com/wavetermdev/waveterm)

### 11.3 RPC 接口

关键 RPC 方法（来自 `pkg/wshrpc/wshrpctypes.go`）：

```go
// 输入注入
ControllerInputCommand(ctx context.Context, data CommandBlockInputData) error

type CommandBlockInputData struct {
    BlockId      string          `json:"blockid"`
    InputData64  string          `json:"inputdata64,omitempty"`
    SigName      string          `json:"signame,omitempty"`
    TermSize     *waveobj.TermSize `json:"termsize,omitempty"`
}

// Block 信息
BlockInfoCommand(ctx context.Context, blockId string) (*BlockInfoData, error)

// Block 列表
BlocksListCommand(ctx context.Context, data BlocksListRequest) ([]BlocksListEntry, error)
```

---

## 12. 附录

### 12.1 wsh 命令速查

| 功能 | 命令 |
|------|------|
| 创建 block | `wsh run --cwd <dir> -- <cmd>` |
| 列出 blocks | `wsh blocks list --json` |
| 删除 block | `wsh deleteblock -b <block_id>` |
| 获取 metadata | `wsh getmeta -v -b <block_id>` |
| 设置 metadata | `wsh setmeta -b <block_id> key=value` |
| 读取终端输出 | `wsh file cat wavefile://{block_id}/term` |
| 设置变量 | `wsh setvar -b <block_id> KEY=VALUE` |

### 12.2 tmux vs wsh 命令对照

| 功能 | tmux | wsh |
|------|------|-----|
| 检查可用性 | `shutil.which("tmux")` | `shutil.which("wsh")` |
| 创建会话 | `tmux new-session -d -s <name>` | `wsh run -- <cmd>` |
| 创建窗口 | `tmux new-window -t <session>` | `wsh run -- <cmd>` |
| 捕获输出 | `tmux capture-pane -p -t <target>` | `wsh file cat wavefile://{id}/term` |
| 发送输入 | `tmux send-keys -t <target> <keys>` | RPC: `ControllerInputCommand` |
| 列出窗口 | `tmux list-windows -t <session>` | `wsh blocks list --json` |
| 检查存活 | `tmux list-panes -F "#{pane_pid}"` | `wsh blocks list --json` |
| 终止进程 | `tmux kill-window -t <target>` | `wsh deleteblock -b <id>` |

---

**文档版本**: 1.0  
**最后更新**: 2026-03-25
