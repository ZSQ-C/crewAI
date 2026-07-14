# 阶段 L：mcp/ — MCP 协议实现逻辑详解

## 1. 模块定位与架构图

MCP（Model Context Protocol）模块是 CrewAI 与外部 MCP 服务器通信的桥梁。它负责管理 MCP 客户端连接、工具发现、工具调用，以及将 MCP 工具注册为 CrewAI Agent 可用的 `BaseTool`。该模块位于 `lib/crewai/src/crewai/mcp/`，包含 10 个文件，按职责分为 5 层：

```
┌──────────────────────────────────────────────────────────────────────┐
│                     MCPServerConfig (config.py)                       │
│  MCPServerStdio | MCPServerHTTP | MCPServerSSE                       │
│  用户配置入口：定义 MCP 服务器的连接参数、认证、工具过滤                  │
└──────────────────────────────┬───────────────────────────────────────┘
                               │ 输入
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│                     MCPToolResolver (tool_resolver.py)                │
│  工具解析器：将 MCP 配置/引用转换为 CrewAI BaseTool 列表                │
│  支持三种引用：Native Config | HTTPS URL | AMP Slug                   │
└──────────────┬───────────────────────────────┬───────────────────────┘
               │ 使用                           │ 使用
               ▼                               ▼
┌──────────────────────────────┐  ┌────────────────────────────────────┐
│      MCPClient (client.py)   │  │   ToolFilter (filters.py)           │
│  客户端会话管理：              │  │  工具过滤器：                       │
│  - 连接/断开                  │  │  - StaticToolFilter (白名单/黑名单)  │
│  - list_tools() / call_tool() │  │  - create_dynamic_tool_filter()     │
│  - list_prompts() / get_prompt│  │  - ToolFilterContext               │
│  - 重试与超时                 │  │                                    │
│  - 事件发射                   │  │                                    │
└──────────────┬───────────────┘  └────────────────────────────────────┘
               │ 依赖
               ▼
┌──────────────────────────────────────────────────────────────────────┐
│                 Transport 层 (transports/)                            │
│  ┌───────────────────┐  ┌──────────────────┐  ┌────────────────────┐ │
│  │  StdioTransport    │  │  HTTPTransport   │  │  SSETransport      │ │
│  │  (stdio.py)        │  │  (http.py)       │  │  (sse.py)          │ │
│  │  子进程 + stdin/stdout│  │  Streamable HTTP │  │  Server-Sent Events│ │
│  └───────────────────┘  └──────────────────┘  └────────────────────┘ │
│                        BaseTransport (base.py)                        │
│                        TransportType 枚举                              │
└──────────────────────────────────────────────────────────────────────┘
```

**核心设计理念**：MCP 模块采用**传输层抽象**（Transport）分离通信细节，**MCPClient** 提供高层会话管理，**MCPToolResolver** 负责将 MCP 工具映射为 CrewAI 原生工具。每个工具调用都创建独立的 Transport + Client 实例，确保并发安全。

---

## 2. 核心实现逻辑详解

### 2.1 MCP Client — 客户端

**文件**：`lib/crewai/src/crewai/mcp/client.py`

MCPClient 是整个 MCP 模块的核心，负责管理 MCP 服务器的连接、会话、工具发现和工具调用。它封装了底层 MCP SDK 的 `ClientSession`，并提供超时、重试、缓存和事件发射等企业级能力。

#### 2.1.1 类定义与常量

**关键代码**（第 43-54 行）：

```python
MCP_CONNECTION_TIMEOUT = 30  # Increased for slow servers
MCP_TOOL_EXECUTION_TIMEOUT = 30
MCP_DISCOVERY_TIMEOUT = 30  # Increased for slow servers
MCP_MAX_RETRIES = 3

_mcp_schema_cache: dict[str, tuple[list[dict[str, Any]], float]] = {}
_cache_ttl = 300  # 5 minutes
```

模块级常量定义了三种超时时间（连接、工具执行、工具发现），以及全局缓存和默认 5 分钟 TTL。`_MCPToolResult`（第 36-40 行）是一个 NamedTuple，携带 `content`（工具返回内容）和 `is_error`（是否为错误响应）两个字段。

#### 2.1.2 构造函数

**关键代码**（第 70-101 行）：

```python
def __init__(
    self,
    transport: BaseTransport,
    connect_timeout: int = MCP_CONNECTION_TIMEOUT,
    execution_timeout: int = MCP_TOOL_EXECUTION_TIMEOUT,
    discovery_timeout: int = MCP_DISCOVERY_TIMEOUT,
    max_retries: int = MCP_MAX_RETRIES,
    cache_tools_list: bool = False,
    logger: logging.Logger | None = None,
) -> None:
```

构造函数接收一个 `BaseTransport` 实例和多个超时/重试参数。关键内部状态包括：
- `_session`：MCP SDK 的 `ClientSession` 实例（第 97 行）
- `_initialized`：标记会话是否已初始化（第 98 行）
- `_exit_stack`：`AsyncExitStack` 用于统一管理 Transport 和 Session 的上下文生命周期（第 99 行）
- `_was_connected`：标记是否曾经连接过，用于区分首次连接和重连（第 100 行），会传递给事件

#### 2.1.3 连接流程 — connect()

**关键代码**（第 139-321 行）：

`connect()` 是最复杂的方法，完整流程如下：

1. **幂等检查**（第 149-150 行）：如果已连接，直接返回 self
2. **获取服务器信息**（第 152 行）：调用 `_get_server_info()` 根据 Transport 类型推测 server_name 和 server_url
3. **发射连接开始事件**（第 156-165 行）：通过 `crewai_event_bus` 发射 `MCPConnectionStartedEvent`
4. **延迟导入 MCP SDK**（第 168 行）：`from mcp import ClientSession` — 确保 MCP 库可用时才导入
5. **进入 Transport 上下文**（第 173 行）：通过 `_exit_stack` 管理 Transport 生命周期。`AsyncExitStack` 能确保 Transport 和 Session 在同一个 async scope 中
6. **创建 ClientSession**（第 175-180 行）：用 Transport 的 `read_stream` 和 `write_stream` 初始化会话
7. **初始化会话**（第 183-187 行）：`session.initialize()` 是 MCP 协议要求的第一步，必须在任何其他请求之前完成
8. **错误处理**（第 188-321 行）：分层处理多种异常：
   - `asyncio.CancelledError`（第 188-192 行）：清理后重新抛出，不抑制取消信号
   - `BaseExceptionGroup`（第 193-215 行）：处理 anyio 任务组抛出的异常组，提取真实错误（排除 GeneratorExit），特别识别 401/unauthorized 错误
   - `ImportError`（第 236-249 行）：提示用户安装 `pip install mcp`
   - `asyncio.TimeoutError`（第 250-261 行）：连接超时
   - 外层 `BaseExceptionGroup`（第 274-310 行）：再次处理异常组，分类为 authentication 或 network
   - 通用 `Exception`（第 311-321 行）：同样分类为 authentication 或 network

9. **发射连接完成事件**（第 222-233 行）：记录连接耗时（毫秒）

#### 2.1.4 工具发现 — list_tools()

**关键代码**（第 374-421 行）：

```python
async def list_tools(self, use_cache: bool | None = None) -> list[dict[str, Any]]:
    if not self.connected:
        await self.connect()
    # ...
    tools = await self._retry_operation(
        self._list_tools_impl,
        timeout=self.discovery_timeout,
    )
```

`list_tools()` 自动检查连接状态，支持缓存（通过 `_get_cache_key()` 生成以传输类型+地址为键的缓存键）。`_list_tools_impl()`（第 406-421 行）调用 `session.list_tools()` 获取原始工具列表，然后对每个工具进行 `sanitize_tool_name()` 处理，并保留 `original_name` 字段，返回 `{name, original_name, description, inputSchema}` 字典列表。

#### 2.1.5 工具调用 — call_tool()

**关键代码**（第 423-518 行）：

```python
async def call_tool(
    self, tool_name: str, arguments: dict[str, Any] | None = None
) -> Any:
```

流程：
1. 自动连接检查（第 435-436 行）
2. **参数清洗**（第 439 行）：调用 `_clean_tool_arguments()` 移除 None 值、规范化格式
3. **发射工具执行开始事件**（第 444-453 行）
4. **执行工具调用**（第 456-459 行）：通过 `_call_tool_impl()` 调用 `session.call_tool()`
5. **结果解析**（第 569-588 行）：从 `result.content` 列表中提取第一个元素的 `text` 属性，如果结果有 `isError` 标记则记录
6. **发射完成/失败事件**（第 464-517 行）：根据 `is_error` 发射不同事件，记录执行耗时

#### 2.1.6 参数清洗 — _clean_tool_arguments()

**关键代码**（第 520-567 行）：

参数清洗递归处理嵌套字典和列表，核心逻辑：
- 移除所有 `None` 值（第 532-533 行）
- **规范化 sources 字段**（第 536-547 行）：将 `["web"]` 转为 `[{"type": "web"}]`，这是对常见 MCP 服务器参数格式的兼容处理
- 递归清理嵌套字典（第 549-552 行）
- 递归清理嵌套列表（第 553-563 行）

#### 2.1.7 重试机制 — _retry_operation()

**关键代码**（第 663-714 行）：

```python
async def _retry_operation(self, operation, timeout=None) -> _T:
    for attempt in range(self.max_retries):
        try:
            return await asyncio.wait_for(operation(), timeout=timeout)
        except asyncio.TimeoutError as e:
            # 指数退避：2^attempt 秒
            wait_time = 2**attempt
```

重试策略：
- 默认最多重试 3 次（`MCP_MAX_RETRIES`）
- 指数退避：`2^0=1s` → `2^1=2s` → `2^2=4s`
- **不可重试的错误**直接抛出（第 698-702 行）：authentication/unauthorized 错误直接抛出 `ConnectionError`；not found 错误直接抛出 `ValueError`
- 超时错误和一般网络错误是可重试的
- 超过最大重试次数后抛出 `ConnectionError`

#### 2.1.8 缓存机制

**关键代码**（第 50-51 行，第 716-735 行）：

```python
_mcp_schema_cache: dict[str, tuple[list[dict[str, Any]], float]] = {}
_cache_ttl = 300  # 5 minutes
```

缓存键生成逻辑（`_get_cache_key()`，第 716-735 行）：
- StdioTransport：`mcp:stdio:{command}:{args}:{resource_type}`
- HTTPTransport：`mcp:http:{url}:{resource_type}`
- SSETransport：`mcp:sse:{url}:{resource_type}`

缓存以 (数据, 时间戳) 元组存储，5 分钟内有效。

#### 2.1.9 事件系统集成

**关键代码**（第 20-28 行导入，第 155-165 行使用）：

MCPClient 通过 `crewai_event_bus` 发射 6 种事件：
- `MCPConnectionStartedEvent`：连接开始
- `MCPConnectionCompletedEvent`：连接成功，含耗时
- `MCPConnectionFailedEvent`：连接失败，含错误类型（timeout/authentication/network/cancelled/import_error）
- `MCPToolExecutionStartedEvent`：工具执行开始
- `MCPToolExecutionCompletedEvent`：工具执行成功，含耗时
- `MCPToolExecutionFailedEvent`：工具执行失败，含错误类型

---

### 2.2 MCP Config — 配置

**文件**：`lib/crewai/src/crewai/mcp/config.py`

config 模块使用 Pydantic 定义了三种 MCP 服务器配置模型，以及它们的联合类型。

#### 2.2.1 MCPServerStdio — 标准输入输出配置

**关键代码**（第 12-51 行）：

```python
class MCPServerStdio(BaseModel):
    command: str          # 必填：要执行的命令，如 "python"、"node"、"npx"
    args: list[str]       # 默认 []：命令参数，如 ["server.py"]
    env: dict[str, str] | None  # 默认 None：进程环境变量
    tool_filter: ToolFilter | None  # 默认 None：工具过滤器
    cache_tools_list: bool  # 默认 False：是否缓存工具列表
```

用于连接本地 MCP 服务器，通过子进程的 stdin/stdout 通信。`env` 字段可以传递 API Key 等环境变量给子进程。

#### 2.2.2 MCPServerHTTP — HTTP 配置

**关键代码**（第 53-88 行）：

```python
class MCPServerHTTP(BaseModel):
    url: str              # 必填：服务器 URL
    headers: dict[str, str] | None  # 默认 None：HTTP 请求头（含认证）
    streamable: bool      # 默认 True：是否使用 Streamable HTTP
    tool_filter: ToolFilter | None
    cache_tools_list: bool
```

用于连接远程 MCP 服务器，使用 Streamable HTTP 传输。`streamable=True` 时使用 `streamablehttp_client`，这是 MCP 协议推荐的传输方式。`headers` 通常用于传递 Bearer Token 等认证信息。

#### 2.2.3 MCPServerSSE — SSE 配置

**关键代码**（第 90-121 行）：

```python
class MCPServerSSE(BaseModel):
    url: str              # 必填：服务器 URL
    headers: dict[str, str] | None  # 默认 None：HTTP 请求头
    tool_filter: ToolFilter | None
    cache_tools_list: bool
```

用于连接支持 Server-Sent Events 的 MCP 服务器。与 HTTP 配置的区别在于没有 `streamable` 参数（SSE 本身就是流式传输），且内部使用 `mcp.client.sse.sse_client`。

#### 2.2.4 联合类型

**关键代码**（第 123 行）：

```python
MCPServerConfig = MCPServerStdio | MCPServerHTTP | MCPServerSSE
```

`MCPServerConfig` 是三种配置的联合类型，用于函数签名中接受任意一种 MCP 配置。

---

### 2.3 Stdio 传输层

**文件**：`lib/crewai/src/crewai/mcp/transports/stdio.py`

StdioTransport 通过启动子进程并与其 stdin/stdout 通信来连接本地 MCP 服务器。

#### 2.3.1 类定义与构造函数

**关键代码**（第 23-63 行）：

```python
class StdioTransport(BaseTransport):
    def __init__(self, command, args=None, env=None, **kwargs):
        super().__init__(**kwargs)
        self.command = command
        self.args = args or []
        self.env = env or {}
        self._process: subprocess.Popen[bytes] | None = None
        self._transport_context: Any = None
```

继承了 `BaseTransport`（base.py 第 25-114 行），后者定义了 `_read_stream`、`_write_stream`、`_connected` 三个内部状态，以及 `read_stream`、`write_stream`、`connected` 三个只读属性，和 `_set_streams()`、`_clear_streams()` 两个辅助方法。

#### 2.3.2 连接流程 — connect()

**关键代码**（第 69-122 行）：

```python
async def connect(self) -> Self:
    if self._connected:
        return self
    # 1. 延迟导入 MCP SDK
    from mcp import StdioServerParameters
    from mcp.client.stdio import get_default_environment, stdio_client
    # 2. 合并环境变量
    process_env = get_default_environment()
    process_env.update(self.env)
    # 3. 可选的环境过滤钩子
    if _env_filter_hook is not None:
        process_env = _env_filter_hook(process_env)
    # 4. 创建 StdioServerParameters 并启动 stdio_client
    server_params = StdioServerParameters(
        command=self.command, args=self.args, env=process_env,
    )
    self._transport_context = stdio_client(server_params)
    # 5. 进入上下文获取读写流
    read, write = await self._transport_context.__aenter__()
    self._set_streams(read=read, write=write)
```

流程说明：
1. 调用 MCP SDK 的 `get_default_environment()` 获取默认环境变量，然后合并用户提供的 `env`
2. 环境过滤钩子 `_env_filter_hook`（第 13-20 行）是一个模块级变量，允许企业扩展在子进程启动前过滤敏感环境变量
3. 使用 `StdioServerParameters` 封装命令参数，交给 `stdio_client()` 创建传输上下文
4. 进入上下文后获取 `(read, write)` 流，通过 `_set_streams()` 设置到基类

#### 2.3.3 断开连接 — disconnect()

**关键代码**（第 124-157 行）：

```python
async def disconnect(self) -> None:
    if not self._connected:
        return
    self._clear_streams()
    if self._transport_context is not None:
        await self._transport_context.__aexit__(None, None, None)
    if self._process is not None:
        self._process.terminate()
        # 等待 5 秒，超时则 kill
        await asyncio.wait_for(
            loop.run_in_executor(None, self._process.wait), timeout=5.0
        )
```

断开流程：
1. 清除读写流（第 130 行）
2. 退出传输上下文（第 132-133 行）
3. 优雅终止子进程（第 135-149 行）：先 `terminate()`，等待 5 秒，超时则 `kill()` 强制结束
4. 所有异常都被捕获并记录日志，不影响清理流程（第 151-156 行）

**注意**：`_process` 字段在构造函数中初始化为 `None`（第 61 行），但实际子进程的创建在 `stdio_client()` 内部，所以 `_process` 在 StdioTransport 中始终为 `None`，子进程的生命周期由 `stdio_client` 上下文管理。

---

### 2.4 HTTP/SSE 传输层

**文件**：`lib/crewai/src/crewai/mcp/transports/http.py` 和 `sse.py`

#### 2.4.1 HTTPTransport

**文件**：`lib/crewai/src/crewai/mcp/transports/http.py`

**关键代码**（第 18-55 行）：

```python
class HTTPTransport(BaseTransport):
    def __init__(self, url, headers=None, streamable=True, **kwargs):
        super().__init__(**kwargs)
        self.url = url
        self.headers = headers or {}
        self.streamable = streamable
        self._transport_context: Any = None
```

`transport_type` 属性（第 57-59 行）根据 `streamable` 返回 `STREAMABLE_HTTP` 或 `HTTP`。

**连接流程**（第 61-107 行）：

```python
async def connect(self) -> Self:
    from mcp.client.streamable_http import streamablehttp_client
    self._transport_context = streamablehttp_client(
        self.url,
        headers=self.headers if self.headers else None,
        terminate_on_close=True,
    )
    read, write, _ = await asyncio.wait_for(
        self._transport_context.__aenter__(), timeout=30.0
    )
    self._set_streams(read=read, write=write)
```

使用 `streamablehttp_client` 创建传输上下文，`terminate_on_close=True` 确保关闭时终止连接。连接超时固定为 30 秒。

**断开连接**（第 109-159 行）：
- 先清除流，等待 0.1 秒让后台任务完成
- 退出传输上下文时特别处理了 `RuntimeError`（cancel scope 错误）和 `CancelledError`——这些在 asyncio 事件循环关闭时的后台任务清理中常见，需要安全忽略
- `BaseExceptionGroup`（第 136-146 行）：遍历异常组，如果所有异常都是 cancel scope / task 相关错误，则忽略；否则重新抛出

#### 2.4.2 SSETransport

**文件**：`lib/crewai/src/crewai/mcp/transports/sse.py`

SSETransport 与 HTTPTransport 结构类似，但更简洁。

**连接流程**（第 50-83 行）：

```python
async def connect(self) -> Self:
    from mcp.client.sse import sse_client
    self._transport_context = sse_client(
        self.url,
        headers=self.headers if self.headers else None,
    )
    read, write = await self._transport_context.__aenter__()
    self._set_streams(read=read, write=write)
```

与 HTTPTransport 的区别：
- 使用 `mcp.client.sse.sse_client` 而非 `streamablehttp_client`
- 没有 `streamable` 参数（SSE 本身就是流式传输）
- 没有额外的超时包装（信任 `sse_client` 自身的超时处理）
- 断开连接时更简洁，直接清除流并退出上下文（第 85-99 行）

#### 2.4.3 BaseTransport 基类

**文件**：`lib/crewai/src/crewai/mcp/transports/base.py`

**关键代码**（第 12-13 行，第 16-23 行）：

```python
MCPReadStream = MemoryObjectReceiveStream[SessionMessage | Exception]
MCPWriteStream = MemoryObjectSendStream[SessionMessage]

class TransportType(str, Enum):
    STDIO = "stdio"
    HTTP = "http"
    STREAMABLE_HTTP = "streamable-http"
    SSE = "sse"
```

`MCPReadStream` 和 `MCPWriteStream` 都是 anyio 的 `MemoryObjectStream`，泛型参数为 `SessionMessage`。这意味着所有传输层最终都通过内存对象流交换 MCP 协议的 `SessionMessage`。

`_set_streams()`（第 100-109 行）和 `_clear_streams()`（第 111-114 行）是子类共用的流管理方法，设置流的同时更新 `_connected` 状态。

---

### 2.5 ToolResolver — 工具解析

**文件**：`lib/crewai/src/crewai/mcp/tool_resolver.py`

`MCPToolResolver` 是整个 MCP 模块的入口，负责将用户的 MCP 配置（Config / URL / AMP Slug）转换为 CrewAI 的 `BaseTool` 列表。它管理 MCP 客户端连接的生命周期。

#### 2.5.1 类定义与构造函数

**关键代码**（第 45-62 行）：

```python
class MCPToolResolver:
    def __init__(self, agent: Any, logger: Logger) -> None:
        self._agent = agent
        self._logger = logger
        self._clients: list[Any] = []
```

维护一个 `_clients` 列表，用于跟踪所有创建的 MCP 客户端连接，以便在 `cleanup()` 时统一断开。

#### 2.5.2 入口方法 — resolve()

**关键代码**（第 68-88 行）：

```python
def resolve(self, mcps: list[str | MCPServerConfig]) -> list[BaseTool]:
    all_tools: list[BaseTool] = []
    amp_refs: list[tuple[str, str | None]] = []

    for mcp_config in mcps:
        if isinstance(mcp_config, str) and mcp_config.startswith("https://"):
            all_tools.extend(self._resolve_external(mcp_config))
        elif isinstance(mcp_config, str):
            amp_refs.append(self._parse_amp_ref(mcp_config))
        else:
            tools, clients = self._resolve_native(mcp_config)
            all_tools.extend(tools)
            self._clients.extend(clients)

    if amp_refs:
        tools, clients = self._resolve_amp(amp_refs)
        all_tools.extend(tools)
        self._clients.extend(clients)

    return all_tools
```

三种 MCP 引用判定逻辑：
1. **HTTPS URL**（第 74 行）：以 `https://` 开头的字符串 → `_resolve_external()`
2. **AMP Slug**（第 76-77 行）：其他字符串（如 `"notion"`、`"notion#search"`、`"crewai-amp:notion"`）→ 先解析再批量 `_resolve_amp()`
3. **Native Config**（第 78-81 行）：`MCPServerStdio` / `MCPServerHTTP` / `MCPServerSSE` 实例 → `_resolve_native()`

#### 2.5.3 Native Config 解析 — _resolve_native()

**关键代码**（第 313-463 行）：

这是最核心的解析方法，流程如下：

1. **创建发现用 Transport**（第 327 行）：调用 `_create_transport()` 根据配置类型创建对应的 Transport 实例
2. **创建发现用 Client**（第 328-331 行）：用发现 Transport 创建临时 MCPClient
3. **异步连接 + 列出工具**（第 333-353 行）：`_setup_client_and_list_tools()` 是内部 async 函数，负责连接、列出工具、断开连接
4. **事件循环适配**（第 356-381 行）：处理三种场景：
   - 已在运行中的事件循环中：使用 `ThreadPoolExecutor` 在独立线程中运行 `asyncio.run()`（第 357-365 行）
   - 无运行中的事件循环：直接 `asyncio.run()`（第 367 行）
   - 处理 cancel scope 错误（第 369-376 行）
5. **工具过滤**（第 383-402 行）：如果配置了 `tool_filter`，迭代工具列表：
   - 尝试创建 `ToolFilterContext`（含 agent、server_name、run_context）调用过滤器（第 388-396 行）
   - 如果过滤器不接受 context 参数，则直接传入 tool 字典（第 397-399 行）
6. **创建 MCPNativeTool**（第 418-457 行）：为每个工具定义创建 `MCPNativeTool`：
   - 使用 `_json_schema_to_pydantic()` 将 JSON Schema 转为 Pydantic 模型（第 426-430 行）
   - 传入 `_client_factory` 闭包（第 411-416 行）：每次工具调用时创建全新的 Transport + Client，确保并发安全
   - 保留 `original_tool_name` 字段（第 421 行）

#### 2.5.4 外部 URL 解析 — _resolve_external()

**关键代码**（第 219-276 行）：

```python
def _resolve_external(self, mcp_ref: str) -> list[BaseTool]:
    if "#" in mcp_ref:
        server_url, specific_tool = mcp_ref.split("#", 1)
    else:
        server_url, specific_tool = mcp_ref, None
```

支持 URL 中带 `#` 指定特定工具（如 `https://example.com/mcp#read_file`）。使用 `MCPToolWrapper` 而非 `MCPNativeTool`（第 250 行），这两种工具的区别在于：
- `MCPNativeTool`：用于 native config 解析，每个工具调用创建独立客户端
- `MCPToolWrapper`：用于外部 URL 解析，通过 `server_params` 字典传递配置

#### 2.5.5 AMP 解析 — _resolve_amp()

**关键代码**（第 118-180 行）：

```python
def _resolve_amp(self, amp_refs) -> tuple[list[BaseTool], list[Any]]:
    unique_slugs = list(dict.fromkeys(slug for slug, _ in amp_refs))
    amp_configs_map = self._fetch_amp_mcp_configs(unique_slugs)
```

AMP（CrewAI+ Marketplace）解析流程：
1. 去重 slug（第 129 行）
2. 通过 CrewAI+ API 批量获取配置（第 130 行）：`_fetch_amp_mcp_configs()` 调用 `PlusAPI.get_mcp_configs()`（第 200-201 行）
3. 为每个 slug 创建 MCP 配置并调用 `_resolve_native()`（第 152-153 行）
4. 结果缓存到 `resolved_cache`（第 154 行），同一个 slug 只连接一次
5. 应用特定工具过滤（第 166-178 行）：`notion#search` 只返回名称以 `_search` 结尾的工具

#### 2.5.6 Transport 工厂 — _create_transport()

**关键代码**（第 278-311 行）：

```python
@staticmethod
def _create_transport(mcp_config) -> tuple[Transport, str]:
    if isinstance(mcp_config, MCPServerStdio):
        transport = StdioTransport(command=mcp_config.command, args=mcp_config.args, env=mcp_config.env)
        server_name = f"{mcp_config.command}_{'_'.join(mcp_config.args)}"
    elif isinstance(mcp_config, MCPServerHTTP):
        transport = HTTPTransport(url=mcp_config.url, headers=mcp_config.headers, streamable=mcp_config.streamable)
        server_name = MCPToolResolver._extract_server_name(mcp_config.url)
    elif isinstance(mcp_config, MCPServerSSE):
        transport = SSETransport(url=mcp_config.url, headers=mcp_config.headers)
        server_name = MCPToolResolver._extract_server_name(mcp_config.url)
```

每次调用都返回**全新的 Transport 实例**（文档注释强调 "independent transport so that parallel tool executions never share state"），这是确保并发工具调用安全的关键设计。

#### 2.5.7 JSON Schema 转 Pydantic — _json_schema_to_pydantic()

**关键代码**（第 630-639 行）：

```python
@staticmethod
def _json_schema_to_pydantic(tool_name: str, json_schema: dict[str, Any]) -> type:
    from crewai.utilities.pydantic_schema_utils import create_model_from_schema
    model_name = f"{tool_name.replace('-', '_').replace(' ', '_')}Schema"
    return create_model_from_schema(json_schema, model_name=model_name, enrich_descriptions=True)
```

将 MCP 工具返回的 JSON Schema 转换为 Pydantic 模型，用于工具调用的参数校验。`enrich_descriptions=True` 会在生成的模型字段上添加描述信息。

#### 2.5.8 清理 — cleanup()

**关键代码**（第 90-105 行）：

```python
def cleanup(self) -> None:
    async def _disconnect_all() -> None:
        for client in self._clients:
            if client and hasattr(client, "connected") and client.connected:
                await client.disconnect()
    try:
        asyncio.run(_disconnect_all())
    except Exception as e:
        self._logger.log("error", f"Error during MCP client cleanup: {e}")
    finally:
        self._clients.clear()
```

遍历所有客户端，对每个已连接的客户端调用 `disconnect()`，最后清空客户端列表。

#### 2.5.9 工具过滤器（filters.py）

**文件**：`lib/crewai/src/crewai/mcp/filters.py`

提供两种过滤方式：

**StaticToolFilter**（第 38-88 行）：基于白名单/黑名单的静态过滤器
```python
class StaticToolFilter:
    def __init__(self, allowed_tool_names=None, blocked_tool_names=None):
        self.allowed_tool_names = set(allowed_tool_names or [])
        self.blocked_tool_names = set(blocked_tool_names or [])
    def __call__(self, tool: dict[str, Any]) -> bool:
        # 黑名单优先
        if self.blocked_tool_names and tool_name in self.blocked_tool_names:
            return False
        if self.allowed_tool_names:
            return tool_name in self.allowed_tool_names
        return True
```

**动态过滤器**（第 130-163 行）：接收 `ToolFilterContext` 和 tool 字典，支持基于 agent 角色、运行上下文等动态判断。

**ToolFilter 类型**（第 32-35 行）：
```python
ToolFilter = (
    Callable[[ToolFilterContext, dict[str, Any]], bool]
    | Callable[[dict[str, Any]], bool]
)
```

---

## 3. 完整调用时序图

以下时序图展示从 Agent 初始化到 MCP 工具被调用的完整流程：

```
Agent()                    MCPToolResolver         MCPClient          Transport         MCP Server
  │                             │                     │                   │                 │
  │  resolve(mcps=configs)       │                     │                   │                 │
  │─────────────────────────────>│                     │                   │                 │
  │                             │                     │                   │                 │
  │                             │─ _resolve_native()   │                   │                 │
  │                             │─ _create_transport()─>│                  │                 │
  │                             │                     │                   │                 │
  │                             │─ new MCPClient(transport)                │                 │
  │                             │────────────────────>│                   │                 │
  │                             │                     │                   │                 │
  │                             │  _setup_client_and_list_tools()          │                 │
  │                             │────────────────────>│                   │                 │
  │                             │                     │─ connect()         │                 │
  │                             │                     │──────────────────>│                 │
  │                             │                     │                   │─ connect()      │
  │                             │                     │                   │────────────────>│
  │                             │                     │                   │                 │
  │                             │                     │                   │  read/write     │
  │                             │                     │                   │<────────────────│
  │                             │                     │                   │  streams        │
  │                             │                     │                   │                 │
  │                             │                     │─ session.initialize()               │
  │                             │                     │─────────────────────────────────────>│
  │                             │                     │                     init response   │
  │                             │                     │<─────────────────────────────────────│
  │                             │                     │                   │                 │
  │                             │                     │─ session.list_tools()               │
  │                             │                     │─────────────────────────────────────>│
  │                             │                     │              tools list             │
  │                             │                     │<─────────────────────────────────────│
  │                             │                     │                   │                 │
  │                             │                     │─ disconnect()     │                 │
  │                             │                     │──────────────────>│                 │
  │                             │                     │                   │─ disconnect()  │
  │                             │                     │                   │────────────────>│
  │                             │                     │                   │                 │
  │                             │  [MCPNativeTool 列表]│                   │                 │
  │                             │<────────────────────│                   │                 │
  │                             │                     │                   │                 │
  │  [BaseTool 列表]            │                     │                   │                 │
  │<─────────────────────────────│                     │                   │                 │
  │                             │                     │                   │                 │
  │  ... Agent 执行任务 ...      │                     │                   │                 │
  │                             │                     │                   │                 │
  │  tool.run()                 │                     │                   │                 │
  │─────────────────────────────────────────────────────────────────────────────────────────>
  │                             │                     │                   │                 │
  │  [MCPNativeTool._run()]     │                     │                   │                 │
  │                             │                     │                   │                 │
  │                             │  _client_factory()   │                   │                 │
  │                             │─ _create_transport()─>│                  │                 │
  │                             │─ new MCPClient(transport)                │                 │
  │                             │────────────────────>│                   │                 │
  │                             │                     │─ connect()         │                 │
  │                             │                     │──────────────────>│                 │
  │                             │                     │─ session.initialize()               │
  │                             │                     │─────────────────────────────────────>│
  │                             │                     │─ session.call_tool(name, args)       │
  │                             │                     │─────────────────────────────────────>│
  │                             │                     │              tool result            │
  │                             │                     │<─────────────────────────────────────│
  │                             │                     │─ disconnect()     │                 │
  │                             │                     │──────────────────>│                 │
  │  tool result                │                     │                   │                 │
  │<─────────────────────────────────────────────────────────────────────────────────────────>
```

**关键时序说明**：
1. **发现阶段**：Agent 初始化时，`MCPToolResolver.resolve()` 为每个 MCP 配置创建临时连接，发现工具列表后立即断开
2. **执行阶段**：每次工具调用通过 `_client_factory` 创建全新的 Transport + Client，调用完成后断开
3. **清理阶段**：Agent 任务完成后，调用 `MCPToolResolver.cleanup()` 断开所有连接

---

## 4. 完整可运行示例

### 示例 1：Stdio 本地 MCP 服务器连接

```python
"""使用 Stdio 传输连接本地 MCP 服务器并调用工具"""
import asyncio
from crewai.mcp.client import MCPClient
from crewai.mcp.transports.stdio import StdioTransport


async def main():
    # 创建 Stdio 传输：启动一个 Python MCP 服务器进程
    transport = StdioTransport(
        command="python",
        args=["path/to/your_mcp_server.py"],
        env={"API_KEY": "your-api-key"},
    )

    client = MCPClient(
        transport=transport,
        connect_timeout=30,
        execution_timeout=30,
        max_retries=3,
        cache_tools_list=True,
    )

    async with client:
        # 列出所有可用工具
        tools = await client.list_tools()
        print(f"发现 {len(tools)} 个工具:")
        for tool in tools:
            print(f"  - {tool['name']}: {tool['description'][:80]}...")

        # 调用工具
        if tools:
            result = await client.call_tool(
                tools[0]["name"],
                arguments={"path": "/tmp/test.txt"},
            )
            print(f"工具结果: {result}")

        # 列出 prompts
        prompts = await client.list_prompts()
        print(f"发现 {len(prompts)} 个 prompts")


asyncio.run(main())
```

### 示例 2：HTTP/Streamable HTTP 远程 MCP 服务器连接

```python
"""使用 HTTP 传输连接远程 MCP 服务器"""
import asyncio
from crewai.mcp.client import MCPClient
from crewai.mcp.transports.http import HTTPTransport


async def main():
    # 创建 HTTP 传输：连接远程 MCP 服务器
    transport = HTTPTransport(
        url="https://mcp-server.example.com/api",
        headers={"Authorization": "Bearer your-token-here"},
        streamable=True,  # 使用 Streamable HTTP（推荐）
    )

    client = MCPClient(
        transport=transport,
        cache_tools_list=True,
    )

    async with client:
        tools = await client.list_tools()
        print(f"远程服务器提供 {len(tools)} 个工具")

        for tool in tools:
            print(f"  工具: {tool['name']}")
            print(f"  描述: {tool['description']}")
            print(f"  参数 Schema: {tool['inputSchema']}")
            print()

        # 获取 prompt
        prompts = await client.list_prompts()
        if prompts:
            prompt_detail = await client.get_prompt(
                prompts[0]["name"],
                arguments={"topic": "AI"},
            )
            print(f"Prompt 消息: {prompt_detail['messages']}")


asyncio.run(main())
```

### 示例 3：通过 MCPToolResolver 注册工具到 Agent

```python
"""使用 MCPToolResolver 将 MCP 工具注册为 Agent 工具"""
import asyncio
from crewai.mcp.config import MCPServerStdio, MCPServerHTTP
from crewai.mcp.filters import create_static_tool_filter
from crewai.mcp.tool_resolver import MCPToolResolver


async def main():
    # 模拟一个 Agent 和 logger
    class MockAgent:
        role = "数据分析师"

    class MockLogger:
        def log(self, level, msg):
            print(f"[{level}] {msg}")

    agent = MockAgent()
    logger = MockLogger()

    # 配置 MCP 服务器
    mcp_configs = [
        # Stdio 本地服务器 + 工具过滤
        MCPServerStdio(
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
            env={"HOME": "/tmp"},
            tool_filter=create_static_tool_filter(
                allowed_tool_names=["read_file", "write_file"],
                blocked_tool_names=["delete_file"],
            ),
            cache_tools_list=True,
        ),
        # HTTP 远程服务器
        MCPServerHTTP(
            url="https://api.example.com/mcp",
            headers={"Authorization": "Bearer xxx"},
            streamable=True,
            cache_tools_list=True,
        ),
    ]

    resolver = MCPToolResolver(agent=agent, logger=logger)
    try:
        tools = resolver.resolve(mcp_configs)
        print(f"\n成功解析 {len(tools)} 个工具:")
        for tool in tools:
            print(f"  - {tool.name}: {tool.description[:80] if tool.description else 'N/A'}...")
    finally:
        resolver.cleanup()


asyncio.run(main())
```

### 示例 4：SSE 传输 + 动态工具过滤

```python
"""使用 SSE 传输连接 MCP 服务器，并使用动态工具过滤器"""
import asyncio
from crewai.mcp.client import MCPClient
from crewai.mcp.transports.sse import SSETransport
from crewai.mcp.filters import (
    create_dynamic_tool_filter,
    ToolFilterContext,
)
from crewai.mcp.config import MCPServerSSE


async def main():
    # 创建动态过滤器：根据 Agent 角色限制工具
    def context_aware_filter(
        context: ToolFilterContext, tool: dict
    ) -> bool:
        # 禁止 Reviewer 角色使用危险工具
        if hasattr(context.agent, "role") and context.agent.role == "Code Reviewer":
            if tool.get("name", "").startswith("danger_"):
                return False
        # 只允许名称以 "safe_" 开头的工具
        return tool.get("name", "").startswith("safe_")

    filter_fn = create_dynamic_tool_filter(context_aware_filter)

    # SSE 配置
    mcp_config = MCPServerSSE(
        url="https://mcp.example.com/sse",
        headers={"Authorization": "Bearer token"},
        tool_filter=filter_fn,
        cache_tools_list=True,
    )

    # 直接使用 Transport 进行底层连接
    transport = SSETransport(
        url=mcp_config.url,
        headers=mcp_config.headers,
    )

    client = MCPClient(transport=transport, cache_tools_list=True)

    async with client:
        tools = await client.list_tools()
        print(f"SSE 服务器提供 {len(tools)} 个工具")
        for tool in tools:
            print(f"  - {tool['name']}")


asyncio.run(main())
```

### 示例 5：带重试和超时的健壮工具调用

```python
"""演示 MCPClient 的重试机制和超时处理"""
import asyncio
from crewai.mcp.client import MCPClient
from crewai.mcp.transports.http import HTTPTransport


async def main():
    transport = HTTPTransport(
        url="https://mcp-server.example.com/api",
        headers={"Authorization": "Bearer token"},
    )

    # 自定义超时和重试参数
    client = MCPClient(
        transport=transport,
        connect_timeout=10,       # 连接超时 10 秒
        execution_timeout=15,     # 工具执行超时 15 秒
        discovery_timeout=20,     # 工具发现超时 20 秒
        max_retries=5,            # 最多重试 5 次
        cache_tools_list=True,    # 启用工具列表缓存
    )

    try:
        async with client:
            # 工具列表会被缓存 5 分钟（_cache_ttl = 300）
            tools = await client.list_tools()
            print(f"发现 {len(tools)} 个工具")

            # 第二次调用将使用缓存
            tools_cached = await client.list_tools()
            print(f"缓存命中，工具数: {len(tools_cached)}")

            # 调用工具（带重试：如果失败，自动重试最多 5 次）
            if tools:
                result = await client.call_tool(
                    tools[0]["name"],
                    arguments={
                        "query": "test",
                        # None 值会被 _clean_tool_arguments 自动移除
                        "optional_param": None,
                        # sources 字符串会被规范化
                        "sources": ["web", "database"],
                    },
                )
                print(f"结果: {result}")

    except ConnectionError as e:
        print(f"连接失败: {e}")
    except ValueError as e:
        print(f"资源未找到: {e}")
    except Exception as e:
        print(f"其他错误: {e}")


asyncio.run(main())
```

---

## 5. 设计亮点与注意事项

### 设计亮点

1. **每次调用创建独立 Transport（无状态共享）**
   `_create_transport()` 和 `_client_factory` 确保每次工具调用都创建全新的 Transport + Client 实例。这是 `tool_resolver.py` 第 411-416 行和文档注释中明确强调的设计，保证并行工具调用之间没有共享可变状态。

2. **AsyncExitStack 统一管理生命周期**
   `MCPClient` 使用 `AsyncExitStack`（client.py 第 99 行）管理 Transport 和 Session 的上下文，确保它们在同一个 async scope 中进入和退出，避免了 cancel scope 错误。这是对 MCP SDK 底层 anyio task group 问题的防御性处理。

3. **分层异常处理**
   `connect()` 方法（client.py 第 139-321 行）包含 6 层异常捕获，每层都处理了 `BaseExceptionGroup`（anyio 的异常组），提取真实错误并忽略 `GeneratorExit` 等噪音异常。特别识别 401/unauthorized 错误并分类为 authentication 类型。

4. **指数退避重试**
   `_retry_operation()`（client.py 第 663-714 行）实现了智能重试：区分可重试错误（网络、超时）和不可重试错误（认证失败、资源未找到），使用指数退避（1s → 2s → 4s）。

5. **事件驱动架构集成**
   所有关键操作（连接、断开、工具执行）都通过 `crewai_event_bus` 发射事件（client.py 第 20-28 行），包含耗时、错误类型等详细信息，便于监控和调试。

6. **环境过滤钩子**
   `_env_filter_hook`（stdio.py 第 13-20 行）是一个模块级变量，允许企业扩展在子进程启动前过滤敏感环境变量，无需修改源码。

7. **三种 MCP 引用统一入口**
   `MCPToolResolver.resolve()` 统一处理 Native Config、HTTPS URL、AMP Slug 三种引用方式，对外暴露简洁的 API。

### 注意事项

1. **MCP SDK 依赖**
   所有模块都使用延迟导入（如 `from mcp import ClientSession`），如果 MCP SDK 未安装，会抛出清晰的 `ImportError` 提示 `pip install mcp`。

2. **事件循环适配**
   `_resolve_native()` 中的异步执行（tool_resolver.py 第 356-381 行）需要处理三种场景：无事件循环、运行中事件循环、嵌套事件循环。使用 `ThreadPoolExecutor` 在独立线程中运行 `asyncio.run()` 解决了嵌套事件循环问题。

3. **Cancel Scope 错误处理**
   HTTPTransport 的 `disconnect()`（http.py 第 126-146 行）和 MCPClient 的 `connect()` 都特别处理了 cancel scope 错误。这些错误在 asyncio 事件循环关闭时常见，需要安全忽略而非抛出。

4. **参数清洗的局限性**
   `_clean_tool_arguments()` 只处理了 `sources` 字段的规范化（client.py 第 536-547 行），其他 MCP 服务器的特殊参数格式可能需要额外处理。

5. **缓存线程安全**
   模块级缓存 `_mcp_schema_cache`（client.py 第 50 行，tool_resolver.py 第 41 行）是普通字典，在并发场景下可能存在竞态条件。适用于单线程 Agent 场景，多线程环境需要额外同步。

6. **StdioTransport 的 _process 字段**
   `_process` 在构造函数中初始化为 `None`（stdio.py 第 61 行），且始终为 `None`，因为子进程由 `stdio_client` 上下文管理。disconnect 中的 `_process.terminate()` 逻辑（第 135-149 行）实际不会执行，进程终止由 `stdio_client` 上下文负责。

7. **SSE vs HTTP 差异**
   SSETransport 没有超时包装（sse.py 第 71 行），而 HTTPTransport 有 30 秒超时（http.py 第 84-86 行）。此外，SSETransport 的 disconnect 更简洁，没有处理 cancel scope 等异常。

8. **AMP 配置的错误处理**
   `_fetch_amp_mcp_configs()`（tool_resolver.py 第 182-217 行）在 API 调用失败时返回空字典，每个失败的 slug 会通过 `MCPConfigFetchFailedEvent` 事件通知，不会中断整体流程。