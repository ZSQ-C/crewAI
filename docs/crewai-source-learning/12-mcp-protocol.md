# 阶段十二：MCP 协议（Model Context Protocol）— 源码深度解析

---

## 1. 模块定位

### 1.1 一句话概括

**MCP（Model Context Protocol）是 CrewAI 的外部工具协议适配层，通过「多传输层 + 客户端会话管理 + 工具发现 + 按需连接 + 工具过滤」架构，让 Agent 可以无缝调用任何 MCP 兼容服务器提供的工具，实现跨服务工具编排。**

### 1.2 在整体架构中的位置

```
Agent 配置 mcp_servers:
    │
    ├── MCPToolResolver.resolve(mcps)
    │   ├── 原生配置: MCPServerStdio / MCPServerHTTP / MCPServerSSE
    │   ├── HTTPS URL: "https://mcp.example.com/api"
    │   └── AMP 引用: "notion" / "notion#search"
    │
    ├── MCPClient.connect() → 会话建立
    │   ├── StdioTransport  ← 本地进程 stdin/stdout
    │   ├── HTTPTransport   ← HTTP 远程 API
    │   └── SSETransport    ← SSE 实时流
    │
    ├── MCPClient.list_tools() → 工具发现
    │   ├── ToolFilter 过滤
    │   └── MCPToolWrapper 包装为 CrewAI BaseTool
    │
    └── Agent 调用 MCP 工具
        └── MCPToolWrapper._run() → MCPClient.call_tool()
```

### 1.3 本阶段涉及的核心源码文件

| 文件 | 核心职责 |
|------|----------|
| `mcp/client.py` | MCPClient：会话管理、连接、工具列表、工具调用 |
| `mcp/config.py` | MCPServerStdio/HTTP/SSE：三种服务端配置模型 |
| `mcp/tool_resolver.py` | MCPToolResolver：将 MCP 配置解析为 CrewAI BaseTool |
| `mcp/filters.py` | ToolFilter：StaticToolFilter + 动态过滤 |
| `mcp/transports/base.py` | BaseTransport：传输层抽象基类 |
| `mcp/transports/stdio.py` | StdioTransport：本地进程 stdio 传输 |
| `mcp/transports/http.py` | HTTPTransport：HTTP 远程传输 |
| `mcp/transports/sse.py` | SSETransport：SSE 服务端推送传输 |
| `tools/mcp_tool_wrapper.py` | MCPToolWrapper：将 MCP 工具包装为 BaseTool |
| `tools/mcp_native_tool.py` | MCPNativeTool：原生 MCP 工具包装 |

---

## 2. 源码分层拆解

### 2.1 第一层：MCPServerConfig（服务端配置）

**文件：** `lib/crewai/src/crewai/mcp/config.py`

```python
# 三种传输方式对应三种配置类型

class MCPServerStdio(BaseModel):
    """本地进程 Stdio 传输。"""
    command: str            # 命令: "python", "node", "npx", "uvx"
    args: list[str] = []    # 参数: ["server.py"]
    env: dict[str, str] | None = None  # 环境变量
    tool_filter: ToolFilter | None = None
    cache_tools_list: bool = False

class MCPServerHTTP(BaseModel):
    """HTTP/HTTPS 远程传输。"""
    url: str                          # 服务端 URL
    headers: dict[str, str] | None = None  # 认证头
    streamable: bool = True           # 是否使用流式 HTTP
    tool_filter: ToolFilter | None = None
    cache_tools_list: bool = False

class MCPServerSSE(BaseModel):
    """SSE 服务端推送传输。"""
    url: str
    headers: dict[str, str] | None = None
    tool_filter: ToolFilter | None = None
    cache_tools_list: bool = False

# 联合类型
MCPServerConfig = MCPServerStdio | MCPServerHTTP | MCPServerSSE
```

---

### 2.2 第二层：MCPClient（客户端会话管理）

**文件：** `lib/crewai/src/crewai/mcp/client.py`

```python
class MCPClient:
    """MCP 客户端，管理会话生命周期。"""

    def __init__(self, transport, connect_timeout=30, execution_timeout=30,
                 max_retries=3, cache_tools_list=False):
        self.transport = transport          # 传输层实例
        self._session = None                # MCP 会话（ClientSession）
        self._initialized = False           # 是否已初始化
        self._exit_stack = AsyncExitStack()  # 异步上下文管理器栈

    async def connect(self) -> Self:
        """连接 MCP 服务器并初始化会话。"""
        # 1. 发射 MCPConnectionStartedEvent
        crewai_event_bus.emit(self, MCPConnectionStartedEvent(...))

        # 2. 进入传输层上下文
        await self._exit_stack.enter_async_context(self.transport)

        # 3. 创建 ClientSession（MCP SDK）
        self._session = ClientSession(
            self.transport.read_stream,
            self.transport.write_stream,
        )
        await self._exit_stack.enter_async_context(self._session)

        # 4. MCP 协议要求先 session.initialize()
        await self._session.initialize()

        # 5. 发射 MCPConnectionCompletedEvent
        crewai_event_bus.emit(self, MCPConnectionCompletedEvent(...))
        return self

    async def list_tools(self) -> list[dict]:
        """列出服务器提供的所有工具。"""
        result = await self._session.list_tools()
        return [tool.model_dump() for tool in result.tools]

    async def call_tool(self, tool_name, arguments) -> _MCPToolResult:
        """调用 MCP 工具。"""
        # 1. 发射 MCPToolExecutionStartedEvent
        result = await self._session.call_tool(tool_name, arguments)
        # 2. 发射 MCPToolExecutionCompletedEvent
        return _MCPToolResult(content=result.content, is_error=result.isError)
```

**大白话：** MCPClient 封装了 MCP 协议的完整生命周期：连接 → 初始化 → 发现工具 → 调用工具 → 断开。内部使用 `AsyncExitStack` 管理嵌套的异步上下文，保证资源正确释放。

---

### 2.3 第三层：MCPToolResolver（工具解析器）

**文件：** `lib/crewai/src/crewai/mcp/tool_resolver.py`

```python
class MCPToolResolver:
    """将 MCP 配置解析为 CrewAI BaseTool 实例。"""

    def resolve(self, mcps: list[str | MCPServerConfig]) -> list[BaseTool]:
        """解析三种 MCP 引用格式。"""
        all_tools = []

        for mcp_config in mcps:
            if isinstance(mcp_config, str) and mcp_config.startswith("https://"):
                # HTTPS URL → 自动创建 HTTPTransport
                all_tools.extend(self._resolve_external(mcp_config))
            elif isinstance(mcp_config, str):
                # AMP 引用 → "notion" 或 "notion#search"
                all_tools.extend(self._resolve_amp_ref(mcp_config))
            else:
                # 原生配置 → MCPServerStdio/HTTP/SSE
                all_tools.extend(self._resolve_native(mcp_config))
        return all_tools

    def _resolve_native(self, config: MCPServerConfig):
        """解析原生 MCP 配置。"""
        # 1. 根据配置类型创建对应的 Transport
        if isinstance(config, MCPServerStdio):
            transport = StdioTransport(config.command, config.args)
        elif isinstance(config, MCPServerHTTP):
            transport = HTTPTransport(config.url, config.headers)
        elif isinstance(config, MCPServerSSE):
            transport = SSETransport(config.url, config.headers)

        # 2. 创建 MCPClient
        client = MCPClient(transport)

        # 3. 连接并获取工具列表
        asyncio.run(client.connect())
        tools = client.list_tools()

        # 4. 应用过滤器
        if config.tool_filter:
            tools = [t for t in tools if config.tool_filter(t)]

        # 5. 包装为 MCPToolWrapper
        return [MCPToolWrapper(
            mcp_server_params=config_params,
            tool_name=t["name"],
            tool_schema=t,
            server_name=server_name,
        ) for t in tools]
```

---

### 2.4 第四层：MCPToolWrapper（工具包装器）

**文件：** `lib/crewai/src/crewai/tools/mcp_tool_wrapper.py`

```python
class MCPToolWrapper(BaseTool):
    """按需连接 MCP 服务器的轻量工具包装器。"""

    def __init__(self, mcp_server_params, tool_name, tool_schema, server_name):
        prefixed_name = f"{server_name}_{tool_name}"  # 防冲突前缀
        super().__init__(
            name=prefixed_name,
            description=tool_schema.get("description", ""),
            args_schema=tool_schema.get("args_schema"),
        )
        self._original_tool_name = tool_name
        self._server_name = server_name

    def _run(self, **kwargs) -> str:
        """同步入口 → 委托给异步实现。"""
        return asyncio.run(self._run_async(**kwargs))

    async def _run_async(self, **kwargs) -> str:
        """异步执行，支持指数退避重试。"""
        return await self._retry_with_exponential_backoff(
            self._execute_tool_with_timeout, **kwargs
        )

    async def _execute_tool_with_timeout(self, **kwargs):
        """实际执行 MCP 工具调用。"""
        client = MCPClient(self._transport)
        async with client:
            result = await client.call_tool(self._original_tool_name, kwargs)
            return result.content
```

**大白话：** MCPToolWrapper 是一个"按需连接"的包装器——每次调用 `_run()` 时，它会：
1. 创建 MCP 连接
2. 调用远程工具
3. 断开连接
4. 返回结果

支持指数退避重试（最多 3 次），超时控制（60 秒）。

---

### 2.5 第五层：ToolFilter（工具过滤器）

**文件：** `lib/crewai/src/crewai/mcp/filters.py`

```python
class StaticToolFilter:
    """静态工具过滤器（白名单/黑名单）。"""

    def __init__(self, allowed_tool_names=None, blocked_tool_names=None):
        self.allowed_tool_names = set(allowed_tool_names or [])
        self.blocked_tool_names = set(blocked_tool_names or [])

    def __call__(self, tool: dict) -> bool:
        """黑名单优先 → 白名单过滤。"""
        if tool["name"] in self.blocked_tool_names:
            return False
        if self.allowed_tool_names:
            return tool["name"] in self.allowed_tool_names
        return True

# 动态过滤器：接收 ToolFilterContext（agent, server_name, run_context）
ToolFilter = Callable[[ToolFilterContext, dict], bool] | Callable[[dict], bool]
```

---

## 3. 完整调用时序图

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          MCP 协议完整时序                                 │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  1. 配置阶段                                                               │
│     agent = Agent(                                                        │
│         role="Researcher",                                                │
│         mcp_servers=[                                                     │
│             MCPServerStdio(                                               │
│                 command="python",                                         │
│                 args=["mcp_server.py"],                                   │
│                 tool_filter=StaticToolFilter(                             │
│                     allowed_tool_names=["search", "read"]                 │
│                 ),                                                        │
│             ),                                                            │
│             MCPServerHTTP(                                                │
│                 url="https://api.example.com/mcp",                        │
│                 headers={"Authorization": "Bearer xxx"},                  │
│             ),                                                            │
│         ],                                                                │
│     )                                                                     │
│                                                                           │
│  2. 工具解析阶段                                                            │
│     MCPToolResolver.resolve(agent.mcp_servers)                             │
│         │                                                                  │
│         ├── [MCPServerStdio] → StdioTransport                             │
│         │   ├── MCPClient(transport)                                      │
│         │   ├── client.connect()                                          │
│         │   │   ├── 启动子进程: python mcp_server.py                      │
│         │   │   ├── ClientSession(transport.read, transport.write)        │
│         │   │   └── session.initialize()  ← MCP 协议握手                 │
│         │   │                                                              │
│         │   ├── client.list_tools()                                       │
│         │   │   └── → [{"name": "search", "description": "...", ...}]    │
│         │   │                                                              │
│         │   ├── tool_filter(tool) → 过滤                                   │
│         │   │                                                              │
│         │   └── MCPToolWrapper(tool_name="search", server_name="my_server")│
│         │       └── 最终工具名: "my_server_search"                         │
│         │                                                                  │
│         └── [MCPServerHTTP] → HTTPTransport                               │
│             └── 同上流程                                                    │
│                                                                           │
│  3. 工具调用阶段                                                            │
│     Agent 调用 "my_server_search"(query="CrewAI")                          │
│         │                                                                  │
│         ├── MCPToolWrapper._run(query="CrewAI")                            │
│         │         │                                                        │
│         │         ├── _retry_with_exponential_backoff()                    │
│         │         │   ├── 第 1 次尝试                                       │
│         │         │   │   ├── MCPClient.connect()                         │
│         │         │   │   ├── 发射 MCPToolExecutionStartedEvent           │
│         │         │   │   ├── client.call_tool("search", {"query": "..."})│
│         │         │   │   ├── 发射 MCPToolExecutionCompletedEvent         │
│         │         │   │   └── client.disconnect()                         │
│         │         │   │                                                    │
│         │         │   ├── 失败？→ 等待 2^0 秒                               │
│         │         │   ├── 第 2 次尝试 → 等待 2^1 秒                         │
│         │         │   └── 第 3 次尝试 → 等待 2^2 秒（最多 3 次）           │
│         │         │                                                        │
│         │         └── 返回结果字符串                                        │
│         │                                                                  │
│         └── Agent 将结果作为工具输出传递给 LLM                               │
│                                                                           │
│  4. 清理阶段                                                               │
│     MCPToolResolver.cleanup()                                              │
│         └── 断开所有 MCPClient 连接                                        │
│                                                                           │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 4. 核心设计亮点

### 4.1 三种传输层统一抽象

```python
class BaseTransport(ABC):
    transport_type: TransportType  # stdio / http / sse

    @abstractmethod
    async def connect(self): ...
    @abstractmethod
    async def disconnect(self): ...
```

无论 MCP 服务器是本地进程、HTTP API 还是 SSE 流，上层 MCPClient 无需关心传输细节。

### 4.2 按需连接（On-Demand Connection）

MCPToolWrapper 在每次调用时独立建立连接 → 调用 → 断开，避免长连接资源占用。类似 HTTP 的短连接模式。

### 4.3 指数退避重试

```python
async def _retry_with_exponential_backoff(self, operation, **kwargs):
    for attempt in range(3):
        result, error, should_retry = await self._execute_single_attempt(operation, **kwargs)
        if not should_retry:
            return result
        await asyncio.sleep(2 ** attempt)  # 1s, 2s, 4s
    raise last_error
```

### 4.4 工具过滤（白名单/黑名单）

```python
# 静态过滤
StaticToolFilter(allowed_tool_names=["search", "read"])
StaticToolFilter(blocked_tool_names=["delete_file"])

# 动态过滤（基于 Agent 上下文）
def dynamic_filter(ctx: ToolFilterContext, tool: dict) -> bool:
    return tool["name"] not in ctx.agent.restricted_tools
```

### 4.5 工具名冲突处理

```python
prefixed_name = f"{server_name}_{tool_name}"
# "notion" 服务器的 "search" 工具 → "notion_search"
```

---

## 5. 生产落地拓展改造

### 5.1 企业 MCP 网关

```python
class MCPGateway:
    """统一 MCP 网关，集中管理所有 MCP 服务器连接。"""

    def __init__(self):
        self._clients: dict[str, MCPClient] = {}
        self._connection_pool = ConnectionPool(max_size=10)

    async def register_server(self, name, config):
        client = await self._connection_pool.acquire(config)
        self._clients[name] = client

    async def call_tool(self, server_name, tool_name, **kwargs):
        client = self._clients[server_name]
        return await client.call_tool(tool_name, kwargs)
```

### 5.2 工具聚合（多服务器同名工具）

```python
class AggregatedTool:
    """聚合多个 MCP 服务器的同名工具。"""

    def __init__(self, tool_name, servers):
        self._tool_name = tool_name
        self._servers = servers  # [client1, client2, ...]

    async def _run(self, **kwargs):
        # 并行调用所有服务器
        tasks = [s.call_tool(self._tool_name, kwargs) for s in self._servers]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return "\n---\n".join(str(r) for r in results if not isinstance(r, Exception))
```

### 5.3 权限控制

```python
class PermissionAwareToolFilter:
    def __init__(self, agent_role, role_permissions):
        self._role = agent_role
        self._permissions = role_permissions

    def __call__(self, tool):
        return tool["name"] in self._permissions.get(self._role, [])
```

---

## 6. 面试深挖问题清单

| # | 问题 | 考察点 |
|---|------|--------|
| 1 | MCP 协议的三种传输方式分别适用什么场景？ | stdio/HTTP/SSE 选型 |
| 2 | MCPClient 为什么用 AsyncExitStack 管理资源？ | 异步上下文管理、嵌套清理 |
| 3 | `session.initialize()` 在 MCP 协议中的作用是什么？ | 协议握手、能力协商 |
| 4 | MCPToolWrapper 为什么采用"按需连接"模式？ | 短连接 vs 长连接、资源管理 |
| 5 | 指数退避重试的等待时间是如何计算的？ | 重试策略、拥塞控制 |
| 6 | StaticToolFilter 中黑名单为什么优先于白名单？ | 安全优先、冲突处理 |
| 7 | 工具名冲突如何解决？ | 前缀命名空间 |
| 8 | MCPToolResolver 如何区分 AMP 引用和 HTTPS URL？ | 字符串解析、Dispatcher |
| 9 | 工具发现的缓存策略（`_mcp_schema_cache`）是什么？ | TTL 缓存、工具列表缓存 |
| 10 | MCP 事件如何与 EventBus 集成？ | MCPEvent 类型、事件发射 |

---

## 7. 简易可运行 Demo

```python
"""Demo: MCP 协议 — 连接本地 MCP 服务器并调用工具"""
from crewai import Agent, Task, Crew
from crewai.mcp.config import MCPServerStdio, MCPServerHTTP
from crewai.mcp.filters import StaticToolFilter

# 1. 配置本地 Stdio MCP 服务器
agent = Agent(
    role="File Manager",
    goal="管理文件系统",
    llm="gpt-4o-mini",
    mcp_servers=[
        # 本地 MCP 服务器：通过子进程通信
        MCPServerStdio(
            command="python",
            args=["file_server.py"],
            env={"WORKSPACE": "/tmp"},
            tool_filter=StaticToolFilter(
                allowed_tool_names=["read_file", "write_file", "list_directory"],
            ),
        ),
        # 远程 HTTP MCP 服务器
        MCPServerHTTP(
            url="https://mcp.example.com/api",
            headers={"Authorization": "Bearer my-token"},
            cache_tools_list=True,
        ),
    ],
)

# 2. 创建任务
task = Task(
    description="读取 config.json 文件内容",
    expected_output="文件内容",
    agent=agent,
)

# 3. 执行
crew = Crew(agents=[agent], tasks=[task])
result = crew.kickoff()
print(f"结果: {result}")
```

---

**下一阶段解析指令：**

```
# 当前解析目标
模块名称：Flow 工作流引擎
对应源码文件路径：
- lib/crewai/src/crewai/flow/flow.py（Flow 主类）
- lib/crewai/src/crewai/flow/flow_events.py（Flow 事件）
- lib/crewai/src/crewai/flow/flow_trackers.py（Flow 追踪器）
- lib/crewai/src/crewai/flow/state.py（Flow 状态管理）
- lib/crewai/src/crewai/flow/visualization_utils.py（Flow 可视化）

# 本次输出硬性要求，缺一不可
1. 模块定位（一句话 + 架构位置 + 核心文件清单）
2. 源码分层拆解（文件→类→方法→关键代码行）
3. 完整调用时序图（@start → @listen → @router → 条件分支 → 状态流转）
4. 核心设计亮点（装饰器驱动、状态机、上下文管理、自动持久化）
5. 生产落地拓展改造（分布式 Flow、条件分支可视化、子 Flow 嵌套）
6. 面试深挖问题清单（10 题）
7. 简易可运行 Demo 代码
```