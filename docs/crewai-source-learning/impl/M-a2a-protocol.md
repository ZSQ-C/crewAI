# 阶段 M：a2a/ — A2A协议实现逻辑详解

## 1. 模块定位与架构图

A2A（Agent-to-Agent）模块是 CrewAI 实现跨 Agent 通信的核心组件，基于 Google A2A 协议规范。它允许 CrewAI Agent 通过标准化的 A2A 协议与远程 Agent 进行委托式对话，支持多轮交互、多种传输协议（JSON-RPC、gRPC、HTTP+JSON）、多种更新机制（流式、轮询、推送通知）以及认证安全。

该模块位于 `lib/crewai/src/crewai/a2a/`，包含约 20+ 个文件，按职责分为 5 层：

```
┌──────────────────────────────────────────────────────────────────────────┐
│                     Config 层 (config.py)                                 │
│  用户配置入口：A2AClientConfig | A2AServerConfig | A2AConfig（已废弃）       │
│  传输配置、认证配置、签名配置、轮数限制、扩展配置                              │
└──────────────────────────────┬───────────────────────────────────────────┘
                               │ 输入
                               ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                     Wrapper 层 (wrapper.py)                               │
│  Agent 包装器：wrap_agent_with_a2a_instance()                              │
│  - 动态替换 execute_task / kickoff 方法                                    │
│  - 提示增强（注入可用Agent列表、对话历史）                                    │
│  - 多轮对话状态管理与委托循环                                               │
│  - LLM 响应解析与事件发射                                                   │
└──────────────┬───────────────────────────────┬───────────────────────────┘
               │ 调用                           │ 使用
               ▼                               ▼
┌──────────────────────────────┐  ┌────────────────────────────────────────┐
│  Delegation 层 (utils/       │  │  AgentCard 层 (utils/agent_card.py)      │
│  delegation.py)              │  │  服务发现：                              │
│  - execute_a2a_delegation()  │  │  - fetch_agent_card() / afetch_agent_card│
│  - aexecute_a2a_delegation() │  │  - 双重缓存（LRU + aiocache TTL）       │
│  - A2A Client 创建与管理     │  │  - Agent/Crew → AgentCard 转换          │
│  - 传输协商（Transport）     │  │  - AgentCard 签名验证                   │
│  - 内容类型协商               │  │  - 服务端方法注入                       │
│  - 认证与TLS                  │  │                                        │
└──────────────┬───────────────┘  └────────────────────────────────────────┘
               │ 依赖
               ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                 底层支撑层                                                │
│  ┌──────────────────┐  ┌──────────────────┐  ┌────────────────────────┐  │
│  │  Types (types.py) │  │  Extensions      │  │  Updates               │  │
│  │  TransportType    │  │  (extensions/)   │  │  (updates/)            │  │
│  │  ProtocolVersion  │  │  A2UI / 自定义   │  │  Streaming / Polling   │  │
│  │  AgentResponse    │  │                  │  │  Push Notifications    │  │
│  └──────────────────┘  └──────────────────┘  └────────────────────────┘  │
│  ┌──────────────────┐  ┌──────────────────┐  ┌────────────────────────┐  │
│  │  Auth (auth/)     │  │  Templates       │  │  DelegateWorkTool      │  │
│  │  ClientAuthScheme │  │  (templates.py)  │  │  (tools/agent_tools/)  │  │
│  │  ServerAuthScheme │  │  XML 提示模板    │  │  Schema + _run 方法    │  │
│  └──────────────────┘  └──────────────────┘  └────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────┘
```

**核心设计理念**：A2A 模块采用**元类钩子模式**（Wrapper 层）拦截 Agent 的 `execute_task` 和 `kickoff` 方法，在 LLM 推理前注入 A2A 上下文（可用远程 Agent 列表、对话历史），由 LLM 自行决定是否委托。委托流程通过独立的 Delegation 层实现，支持多轮对话、传输协商和认证。

---

## 2. 核心实现逻辑详解

### 2.1 Wrapper — Agent 包装器

**文件**：`lib/crewai/src/crewai/a2a/wrapper.py`

Wrapper 是整个 A2A 模块的入口。它通过 `wrap_agent_with_a2a_instance()` 函数（第 97-237 行）动态替换 Agent 实例的四个核心方法，使 Agent 具备 A2A 委托能力。

#### 2.1.1 入口函数：wrap_agent_with_a2a_instance

**源码位置**：wrapper.py 第 97-237 行

```python
def wrap_agent_with_a2a_instance(
    agent: Agent, extension_registry: ExtensionRegistry | None = None
) -> None:
```

该函数接收一个 Agent 实例和可选的扩展注册表，执行以下操作：

1. **注入扩展工具**（第 113 行）：调用 `extension_registry.inject_all_tools(agent)`，将扩展注册表中的所有工具注入到 Agent 中。

2. **保存原始方法引用**（第 115-116 行）：通过 `agent.execute_task.__func__` 获取原始的未绑定函数，而非绑定方法。使用 `__func__` 是因为 `agent.execute_task` 此时已是绑定方法，需要通过 `__func__` 提取原始函数对象。

3. **创建包装函数并绑定**（第 118-235 行）：创建四个包装函数：
   - `execute_task_with_a2a`（第 118-140 行）— 同步 execute_task 包装
   - `aexecute_task_with_a2a`（第 142-164 行）— 异步 execute_task 包装
   - `kickoff_with_a2a`（第 174-199 行）— 同步 kickoff 包装
   - `kickoff_async_with_a2a`（第 201-230 行）— 异步 kickoff_async 包装

4. **动态绑定**（第 166-237 行）：使用 `object.__setattr__` + `MethodType` 将包装函数绑定到 Agent 实例：
   ```python
   object.__setattr__(agent, "execute_task", MethodType(execute_task_with_a2a, agent))
   ```
   使用 `object.__setattr__` 而非 `setattr` 是为了绕过 Pydantic 模型的属性验证逻辑，直接修改底层对象。`MethodType` 将包装函数绑定为实例方法，使得 `self` 参数能正确传递。

5. **注入服务端方法**（第 237 行）：调用 `inject_a2a_server_methods(agent)`，为 Agent 注入 `to_agent_card()` 方法。

#### 2.1.2 包装函数的核心逻辑

以 `execute_task_with_a2a`（第 126-140 行）为例：

```python
if not self.a2a:
    return original_execute_task(self, task, context, tools)

a2a_agents, agent_response_model = get_a2a_agents_and_response_model(self.a2a)
return _execute_task_with_a2a(...)
```

- **A2A 未配置**：如果 `self.a2a` 为 None/空，直接调用原始方法，零开销。
- **A2A 已配置**：调用 `get_a2a_agents_and_response_model()` 解析配置，提取客户端 Agent 列表和动态创建的响应模型（`agent_card.py` 第 87-100 行），然后委托给 `_execute_task_with_a2a()`。

#### 2.1.3 提示增强：_augment_prompt_with_a2a

**源码位置**：wrapper.py 第 639-743 行

这是 A2A 的核心提示工程函数。它将原始任务描述增强为包含 A2A 委托指令的完整提示。返回三元组：
- `augmented_prompt`：增强后的提示
- `disable_structured_output`：是否禁用结构化输出
- `extension_states`：扩展状态字典

增强后的提示结构（第 730-736 行）：
```
{task_description}

IMPORTANT: You have the ability to delegate this task to remote A2A agents.
<AVAILABLE_A2A_AGENTS>
    {agents_text}
</AVAILABLE_A2A_AGENTS>
<PREVIOUS_A2A_CONVERSATION>
    {history_text}
</PREVIOUS_A2A_CONVERSATION>
<CONVERSATION_PROGRESS turn="2" max_turns="10">
    WARNING: Next turn will be the last.
</CONVERSATION_PROGRESS>
<REMOTE_AGENT_STATUS>...</REMOTE_AGENT_STATUS>
```

关键细节：
- **Agent 信息注入**（第 672-691 行）：遍历 `agent_cards`，提取每个 Agent 的 `description`、`url`、`skills` 字段，通过 `AVAILABLE_AGENTS_TEMPLATE` (templates.py 第 7-8 行) 包装为 XML 标签。
- **对话历史注入**（第 695-701 行）：将 A2A 消息历史序列化为 JSON，通过 `PREVIOUS_A2A_CONVERSATION_TEMPLATE` 包装。
- **轮次信息**（第 713-728 行）：显示当前轮次和最大轮数，接近上限时添加 CRITICAL 或 WARNING 提示。
- **扩展增强**（第 738-741 行）：如果有扩展注册表，调用 `augment_prompt_with_all()` 进一步增强提示。

#### 2.1.4 委托流程：_delegate_to_a2a

**源码位置**：wrapper.py 第 1231-1418 行

这是同步委托的核心循环。流程如下：

1. **准备上下文**（第 1261-1263 行）：调用 `_prepare_delegation_context()` 创建 `DelegationContext` NamedTuple（第 61-78 行），包含目标 Agent ID、配置、最大轮数等。
2. **初始化状态**（第 1264 行）：调用 `_init_delegation_state()` 创建 `DelegationState` NamedTuple（第 81-94 行），包含当前请求、对话历史、Agent Card 等可变状态。
3. **多轮循环**（第 1272-1415 行）：
   - 获取轮次上下文（第 1273 行）：`_get_turn_context()` 获取 agent_branch 和 accepted_output_modes。
   - 合并扩展元数据（第 1275-1282 行）：如果扩展注册表存在且已有对话历史，提取并合并扩展状态。
   - 调用委托执行（第 1284-1307 行）：调用 `execute_a2a_delegation()` 发送请求到远程 Agent。
   - 更新状态（第 1309-1316 行）：从返回结果中更新 `conversation_history`、`task_id`、`context_id`。
   - 处理完成状态（第 1318-1365 行）：如果任务状态为 `completed` 或 `input_required`：
     - `_handle_task_completion()`：处理任务完成逻辑，包括 `trust_remote_completion_status` 信任模式。
     - `_handle_agent_response_and_continue()`：让 CrewAI Agent 分析远程响应并决定下一步。
   - 处理错误状态（第 1367-1405 行）：调用同样的响应处理函数，失败时发送事件并返回错误。
4. **超限处理**（第 1407-1415 行）：超过最大轮数时调用 `_handle_max_turns_exceeded()`，尝试从历史中提取最后一条 Agent 消息作为结果，否则抛出异常。

#### 2.1.5 响应解析：_parse_agent_response

**源码位置**：wrapper.py 第 746-758 行

将 LLM 原始输出解析为 `AgentResponseProtocol` 结构（types.py 第 60-67 行），该 Protocol 要求三个字段：
- `a2a_ids`：目标 Agent ID 元组
- `message`：消息内容
- `is_a2a`：是否继续委托

#### 2.1.6 异步版本

异步版本（`_adelegate_to_a2a`，第 1603-1771 行）与同步版本结构完全对称，区别在于：
- 使用 `await aexecute_a2a_delegation()` 替代 `execute_a2a_delegation()`
- 使用 `await _ahandle_agent_response_and_continue()` 替代同步版本
- Agent Card 获取使用 `await _afetch_agent_cards_concurrently()` (asyncio.gather) 替代 `ThreadPoolExecutor`

---

### 2.2 Config — 配置模型

**文件**：`lib/crewai/src/crewai/a2a/config.py`

#### 2.2.1 A2AClientConfig — 客户端配置

**源码位置**：config.py 第 465-549 行

```python
class A2AClientConfig(BaseModel):
    endpoint: Url
    auth: ClientAuthScheme | None = None
    timeout: int = 120
    max_turns: int = 10
    response_model: type[BaseModel] | None = None
    fail_fast: bool = True
    trust_remote_completion_status: bool = False
    updates: UpdateConfig = StreamingConfig()
    accepted_output_modes: list[str] = ["application/json"]
    extensions: list[str] = []
    client_extensions: list[ValidatedA2AExtension] = []
    transport: ClientTransportConfig = ClientTransportConfig()
```

关键字段说明：
- `endpoint`（第 485 行）：远程 Agent 的 URL，类型为 `Url`（types.py 第 52-57 行），经过 `HttpUrl` 严格验证。
- `max_turns`（第 491-493 行）：默认 10，控制多轮对话的最大轮数，防止无限循环。
- `fail_fast`（第 503-506 行）：默认 True，Agent 不可达时抛出异常；False 时静默跳过。
- `trust_remote_completion_status`（第 507-510 行）：默认 False，为 True 时远程 Agent 返回 `completed` 状态后直接返回结果，不再让本地 Agent 进行二次分析。
- `updates`（第 511-514 行）：更新机制，默认 `StreamingConfig()`，支持三种模式：Streaming（流式）、Polling（轮询）、PushNotification（推送）。
- `response_model`（第 494-498 行）：可选的 Pydantic 模型，用于结构化远程 Agent 的响应输出。
- `_parallel_delegation`（第 541 行）：`PrivateAttr`，默认 False，控制是否并行委托到多个 Agent。

#### 2.2.2 A2AServerConfig — 服务端配置

**源码位置**：config.py 第 552-706 行

```python
class A2AServerConfig(BaseModel):
    name: str | None = None
    description: str | None = None
    version: str = "1.0.0"
    skills: list[AgentSkill] = []
    protocol_version: ProtocolVersion = "0.3.0"
    capabilities: AgentCapabilities = AgentCapabilities(...)
    signing_config: AgentCardSigningConfig | None = None
    transport: ServerTransportConfig = ServerTransportConfig()
    auth: ServerAuthScheme | None = None
```

关键字段：
- `name` / `description`（第 585-596 行）：如果未提供，会自动从 Crew/Agent 的属性派生。
- `skills`（第 597-600 行）：如果未提供，会自动从 Agent 的 tools 或 Task 列表派生。
- `signing_config`（第 656-659 行）：AgentCard 签名配置，用于 JWS（JSON Web Signature）签名。
- `auth`（第 684-687 行）：服务端认证方案，默认使用 `SimpleTokenAuth` 并读取 `AUTH_TOKEN` 环境变量。

#### 2.2.3 传输配置

**ServerTransportConfig**（第 270-300 行）：支持三种传输协议：
- `jsonrpc`（默认）：JSON-RPC 服务端配置，路径为 `/a2a` 和 `/.well-known/agent-card.json`
- `grpc`：gRPC 服务端配置，支持 TLS、反射、线程池
- `http_json`：HTTP+JSON 传输配置

**ClientTransportConfig**（第 325-360 行）：客户端传输配置，支持传输协商：
1. 如果 `preferred` 已设置且服务端支持 → 使用客户端首选
2. 否则，如果服务端首选在客户端 `supported` 列表中 → 使用服务端首选
3. 否则，在 `supported` 列表中寻找第一个匹配

**gRPC 配置**：`GRPCServerConfig`（第 134-174 行）和 `GRPCClientConfig`（第 177-204 行）分别管理服务端和客户端的 gRPC 参数，包括消息大小限制、keepalive 设置。

#### 2.2.4 AgentCard 签名配置

**源码位置**：config.py 第 73-131 行

```python
class AgentCardSigningConfig(BaseModel):
    private_key_path: FilePath | None = None
    private_key_pem: SecretStr | None = None
    key_id: str | None = None
    algorithm: SigningAlgorithm = "RS256"
```

支持两种密钥来源：文件路径（`private_key_path`）或 PEM 字符串（`private_key_pem`），通过 `@model_validator`（第 106-119 行）确保二者互斥。`get_private_key()` 方法（第 121-131 行）统一返回密钥内容。

#### 2.2.5 废弃迁移

`A2AConfig`（第 370-463 行）已被标记为废弃，推荐使用 `A2AClientConfig`。废弃字段（`transport_protocol`、`supported_transports`、`use_client_preference`）通过 `@model_validator` 自动迁移到新的 `transport` 配置中。

---

### 2.3 Delegation — 委托执行

**文件**：`lib/crewai/src/crewai/a2a/utils/delegation.py`

#### 2.3.1 核心入口：aexecute_a2a_delegation

**源码位置**：delegation.py 第 239-372 行

这是异步委托的公开入口。它包装了内部实现 `_aexecute_a2a_delegation_impl()`，并添加了事件发射：

```python
async def aexecute_a2a_delegation(...) -> TaskStateResult:
    try:
        result = await _aexecute_a2a_delegation_impl(...)
    except Exception as e:
        crewai_event_bus.emit(None, A2ADelegationCompletedEvent(status="failed", ...))
        raise
    # 成功时发送完成事件
    crewai_event_bus.emit(None, A2ADelegationCompletedEvent(status=result["status"], ...))
    return result
```

#### 2.3.2 同步包装器：execute_a2a_delegation

**源码位置**：delegation.py 第 135-236 行

同步版本通过 `asyncio.run()` 包装异步实现。特殊处理了已存在运行中事件循环的情况（第 226-235 行）：

```python
if has_running_loop:
    ctx = contextvars.copy_context()
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(ctx.run, asyncio.run, coro).result()
return asyncio.run(coro)
```

如果当前线程已有运行中的事件循环（如在 Jupyter notebook 中），则在独立线程中创建新的事件循环来执行异步代码，避免 `asyncio.run()` 的嵌套冲突。

#### 2.3.3 内部实现：_aexecute_a2a_delegation_impl

**源码位置**：delegation.py 第 375-653 行

这是委托执行的核心实现，包含以下步骤：

**步骤 1：获取 AgentCard**（第 418-419 行）
```python
agent_card = await _afetch_agent_card_cached(
    endpoint=endpoint, auth_hash=auth_hash, timeout=timeout
)
```
使用缓存机制获取远程 Agent 的 AgentCard，包含其能力、技能、传输协议等信息。

**步骤 2：认证验证**（第 422 行）
```python
validate_auth_against_agent_card(agent_card, auth)
```
验证客户端提供的认证方案是否与 AgentCard 声明的安全要求兼容。

**步骤 3：扩展验证**（第 424-429 行）
```python
unsupported_exts = validate_required_extensions(agent_card, client_extensions)
```
检查远程 Agent 要求的扩展是否被客户端支持，不支持的扩展会抛出异常。

**步骤 4：传输协商**（第 431-463 行）
```python
negotiated = negotiate_transport(
    agent_card=agent_card,
    client_supported_transports=client_transports,
    client_preferred_transport=transport.preferred,
    ...
)
```
协商双方都支持的传输协议。协商失败时使用 fallback。

**步骤 5：内容类型协商**（第 465-475 行）
```python
content_negotiated = negotiate_content_types(
    agent_card=agent_card,
    client_output_modes=accepted_output_modes,
    ...
)
```
协商输出格式的 MIME 类型。

**步骤 6：构建消息**（第 526-564 行）
```python
message = Message(
    role=Role.user,
    message_id=str(uuid.uuid4()),
    parts=parts_list,
    context_id=context_id,
    task_id=task_id,
    reference_task_ids=reference_task_ids,
    ...
)
```
构建 A2A 协议消息，包含文本内容和可选的 FilePart（文件附件）。

**步骤 7：创建 Client 并执行**（第 631-653 行）
```python
async with _create_a2a_client(...) as client:
    result = await handler.execute(
        client=client,
        message=message,
        new_messages=new_messages,
        agent_card=agent_card,
        ...
    )
```
通过 `_create_a2a_client()` 创建 A2A 客户端（支持 JSON-RPC、gRPC、HTTP+JSON），然后由 handler 执行（支持 Streaming、Polling、PushNotification 三种模式）。

#### 2.3.4 Handler 调度

**源码位置**：delegation.py 第 121-132 行

```python
def get_handler(config: UpdateConfig | None) -> HandlerType:
    if config is None:
        return StreamingHandler
    return HANDLER_REGISTRY.get(type(config), StreamingHandler)
```

`HANDLER_REGISTRY`（types.py 第 99-103 行）将三种 UpdateConfig 类型映射到对应的 Handler：
- `StreamingConfig` → `StreamingHandler`
- `PollingConfig` → `PollingHandler`
- `PushNotificationConfig` → `PushNotificationHandler`

#### 2.3.5 gRPC Channel 工厂

**源码位置**：delegation.py 第 751-892 行

`_create_grpc_channel_factory()` 创建 gRPC 通道工厂，支持：
- TLS 安全连接（grpcs://）
- 多种认证方案注入（BearerToken、HTTPBasic、APIKey、OAuth2）
- HTTPDigest 不支持 gRPC（第 784-788 行，主动抛出异常）
- 自定义拦截器（第 669-748 行）用于元数据标准化和认证注入

#### 2.3.6 文件附件支持

**源码位置**：delegation.py 第 89-118 行

```python
def _create_file_parts(input_files: dict[str, Any] | None) -> list[Part]:
    # 将 FileInput 字典转换为 FilePart 对象
    for name, file_input in input_files.items():
        content_bytes = file_input.read()
        content_base64 = base64.b64encode(content_bytes).decode()
        file_with_bytes = FileWithBytes(bytes=content_base64, ...)
        parts.append(Part(root=FilePart(file=file_with_bytes)))
```

需要 `crewai_files` 包支持，文件内容以 Base64 编码传输。

---

### 2.4 AgentCard — 服务发现

**文件**：`lib/crewai/src/crewai/a2a/utils/agent_card.py`

#### 2.4.1 AgentCard 获取：fetch_agent_card

**源码位置**：agent_card.py 第 103-154 行

同步入口，支持缓存。缓存策略：
- 使用 `ttl_hash = int(time.time() // cache_ttl)` 作为时间窗口标识（默认 300 秒）
- 通过 `@lru_cache()` 装饰器实现内存缓存（第 202-223 行）
- 同时使用 `aiocache` 的 `@cached(ttl=300)` 装饰器实现异步缓存（第 226-234 行）

双重缓存机制：
1. **同步缓存**：`_fetch_agent_card_cached`（第 202-223 行）使用 `@lru_cache()`，基于 `(endpoint, auth_hash, timeout, ttl_hash)` 参数缓存。
2. **异步缓存**：`_afetch_agent_card_cached`（第 226-234 行）使用 `aiocache.cached` 装饰器，TTL=300 秒，使用 Pickle 序列化。

#### 2.4.2 内部实现：_afetch_agent_card_impl

**源码位置**：agent_card.py 第 237-398 行

核心 HTTP 请求逻辑：

1. **URL 解析**（第 245-255 行）：智能解析 endpoint URL，区分 `/.well-known/agent-card.json` 标准路径和自定义路径。
2. **认证头部**（第 257 行）：调用 `_prepare_auth_headers()` 准备认证头。
3. **401 重试**（第 271-278 行）：`retry_on_401()` 支持自动重试，最多重试 2 次。
4. **响应解析**（第 280 行）：`AgentCard.model_validate(response.json())` 将 JSON 响应解析为 AgentCard 模型。
5. **事件发射**（第 284-295 行）：成功获取后发送 `A2AAgentCardFetchedEvent`。
6. **错误处理**（第 299-398 行）：分类处理 HTTPStatusError（401/其他）、TimeoutException、ConnectError、RequestError，每种错误发送对应的事件。

#### 2.4.3 Agent → AgentCard 转换

**源码位置**：agent_card.py 第 485-576 行

`_agent_to_agent_card()` 将 CrewAI Agent 转换为 A2A 标准 AgentCard：

```python
def _agent_to_agent_card(agent: Agent, url: str) -> AgentCard:
    server_config = _get_server_config(agent) or A2AServerConfig()
    name = server_config.name or agent.role
    description = server_config.description or " ".join([agent.goal, agent.backstory])
    # 技能：从 server_config.skills 或 agent.tools 派生
    skills = server_config.skills.copy() if server_config.skills else []
    if not skills and agent.tools:
        for tool in agent.tools:
            skills.append(_tool_to_skill(tool_name, tool_desc))
    # 构建 AgentCard
    card = AgentCard(name=name, description=description, url=url, skills=skills, ...)
    # 签名
    if server_config.signing_config:
        signature = sign_agent_card(card, private_key=..., ...)
        card = card.model_copy(update={"signatures": [signature]})
    return card
```

关键逻辑：
- 优先使用 `A2AServerConfig` 中的显式配置，否则从 Agent 属性派生（第 502-507 行）
- 技能（skills）自动从 tools 或 tasks 派生（第 509-528 行）
- 扩展能力（capabilities）从 `server_config.server_extensions` 注入（第 531-543 行）
- 如果配置了签名（signing_config），调用 `sign_agent_card()` 生成 JWS 签名（第 565-572 行）

#### 2.4.4 Crew → AgentCard 转换

**源码位置**：agent_card.py 第 446-482 行

`_crew_to_agent_card()` 将 Crew 实例转换为 AgentCard：

```python
def _crew_to_agent_card(crew: Crew, url: str) -> AgentCard:
    crew_name = getattr(crew, "name", None) or crew.__class__.__name__
    description = f"A crew of {len(crew.agents)} agents: {', '.join(agent_roles)}"
    skills = [_task_to_skill(task) for task in crew.tasks]
    return AgentCard(name=crew_name, description=description, url=url, skills=skills, ...)
```

#### 2.4.5 服务端方法注入

**源码位置**：agent_card.py 第 579-596 行

```python
def inject_a2a_server_methods(agent: Agent) -> None:
    if _get_server_config(agent) is None:
        return
    def _to_agent_card(self: Agent, url: str) -> AgentCard:
        return _agent_to_agent_card(self, url)
    object.__setattr__(agent, "to_agent_card", MethodType(_to_agent_card, agent))
```

当 Agent 配置了 `A2AServerConfig` 时，注入 `to_agent_card(url)` 方法，使其能作为 A2A 服务端暴露自己的能力。

---

### 2.5 DelegateWorkTool — 委托工具

**文件**：`lib/crewai/src/crewai/tools/agent_tools/delegate_work_tool.py`

#### 2.5.1 Schema 定义

**源码位置**：delegate_work_tool.py 第 8-13 行

```python
class DelegateWorkToolSchema(BaseModel):
    task: str = Field(..., description="The task to delegate")
    context: str = Field(..., description="The context for the task")
    coworker: str = Field(..., description="The role/name of the coworker to delegate to")
```

三个必填字段：`task`（委托任务）、`context`（上下文）、`coworker`（目标协作者角色/名称）。

#### 2.5.2 工具类

**源码位置**：delegate_work_tool.py 第 16-30 行

```python
class DelegateWorkTool(BaseAgentTool):
    name: str = "Delegate work to coworker"
    args_schema: type[BaseModel] = DelegateWorkToolSchema

    def _run(self, task: str, context: str, coworker: str | None = None, **kwargs: Any) -> str:
        coworker = self._get_coworker(coworker, **kwargs)
        return self._execute(coworker, task, context)
```

`DelegateWorkTool` 继承自 `BaseAgentTool`，核心逻辑委托给父类的 `_get_coworker()` 和 `_execute()` 方法：
- `_get_coworker()`：根据 `coworker` 参数查找对应的 Agent 实例
- `_execute()`：在目标 Agent 上执行任务

---

## 3. 完整调用时序图

```
User / Crew              Agent.wrapper           Delegation              Remote A2A Agent
    |                        |                       |                         |
    |--- kickoff(task) ----->|                       |                         |
    |                        |                       |                         |
    |   wrap_agent_with_a2a  |                       |                         |
    |   已替换 execute_task   |                       |                         |
    |                        |                       |                         |
    |                        |-- fetch_agent_cards -->|                         |
    |                        |  (并发获取所有AgentCard)|                         |
    |                        |<-- agent_cards -------|                         |
    |                        |                       |                         |
    |                        |-- augment_prompt_with_a2a()                    |
    |                        |  (注入可用Agent列表)    |                         |
    |                        |                       |                         |
    |                        |-- LLM 推理 --------->|                          |
    |                        |  (AgentResponse{     |                         |
    |                        |   is_a2a=true,       |                         |
    |                        |   a2a_ids=[...],     |                         |
    |                        |   message="委托内容"}) |                         |
    |                        |                       |                         |
    |                        |-- _delegate_to_a2a -->|                         |
    |                        |                       |                         |
    |                        |                  [多轮循环开始]                  |
    |                        |                       |                         |
    |                        |                       |-- negotiate_transport -->|
    |                        |                       |-- negotiate_content ---->|
    |                        |                       |                         |
    |                        |                       |-- send Message ------>  |
    |                        |                       |   (task + context)      |
    |                        |                       |                         |
    |                        |                       |                 [远程Agent处理]
    |                        |                       |                         |
    |                        |                       |<-- TaskState ---------- |
    |                        |                       |   (completed/           |
    |                        |                       |    input_required/      |
    |                        |                       |    working)             |
    |                        |                       |                         |
    |                        |<-- a2a_result --------|                         |
    |                        |                       |                         |
    |                        |-- _handle_agent_response_and_continue()        |
    |                        |  (LLM 分析远程响应)     |                         |
    |                        |                       |                         |
    |                        |-- LLM 推理 --------->|                          |
    |                        |  is_a2a=false?        |                         |
    |                        |  → 返回最终结果        |                         |
    |                        |  is_a2a=true?          |                         |
    |                        |  → 继续下一轮循环       |                         |
    |                        |                       |                         |
    |                  [多轮循环结束]                  |                         |
    |                        |                       |                         |
    |<-- LiteAgentOutput ----|                       |                         |
    |                        |                       |                         |
```

---

## 4. 完整可运行示例

### 示例 1：基本 A2A 客户端委托（同步）

```python
"""示例 1：配置本地 Agent 作为 A2A 客户端，委托任务到远程 Agent"""
from crewai import Agent, Task, Crew
from crewai.a2a.config import A2AClientConfig

# 配置远程 A2A Agent
a2a_client = A2AClientConfig(
    endpoint="http://localhost:8080/.well-known/agent-card.json",
    timeout=60,
    max_turns=5,
    fail_fast=True,
    trust_remote_completion_status=False,
)

# 创建本地 Agent，绑定 A2A 客户端配置
agent = Agent(
    role="Research Coordinator",
    goal="Coordinate research tasks with remote agents",
    backstory="You are a coordinator that delegates tasks to specialized remote agents.",
    a2a=[a2a_client],
    verbose=True,
)

task = Task(
    description="Research the latest AI trends in 2026 and provide a summary.",
    expected_output="A detailed summary of AI trends in 2026.",
    agent=agent,
)

crew = Crew(agents=[agent], tasks=[task])
result = crew.kickoff()
print(f"Result: {result.raw}")
```

### 示例 2：多远程 Agent 委托

```python
"""示例 2：配置多个远程 Agent，LLM 自行选择委托目标"""
from crewai import Agent, Task, Crew
from crewai.a2a.config import A2AClientConfig

# 配置多个远程 A2A Agent
coder_agent = A2AClientConfig(
    endpoint="http://localhost:8081/.well-known/agent-card.json",
    timeout=60,
    max_turns=5,
)

analyst_agent = A2AClientConfig(
    endpoint="http://localhost:8082/.well-known/agent-card.json",
    timeout=60,
    max_turns=5,
)

coordinator = Agent(
    role="Project Manager",
    goal="Coordinate coding and analysis tasks",
    backstory="You manage a team of remote agents for coding and analysis.",
    a2a=[coder_agent, analyst_agent],
    verbose=True,
)

task = Task(
    description="We need to analyze user data and generate a Python script for visualization. "
                "Delegate the analysis to the analyst and the coding to the coder.",
    expected_output="Complete analysis report and visualization script.",
    agent=coordinator,
)

crew = Crew(agents=[coordinator], tasks=[task])
result = crew.kickoff()
print(f"Result: {result.raw}")
```

### 示例 3：A2A 服务端 — 暴露 Agent 为 A2A 服务

```python
"""示例 3：将 CrewAI Agent 暴露为 A2A 服务器"""
from crewai import Agent, Task
from crewai.a2a.config import A2AServerConfig, ServerTransportConfig, JSONRPCServerConfig

# 配置服务端
server_config = A2AServerConfig(
    name="Data Analysis Agent",
    description="Specialized in data analysis and visualization",
    version="1.0.0",
    skills=[],  # 留空则自动从 agent.tools 派生
    transport=ServerTransportConfig(
        preferred="JSONRPC",
        jsonrpc=JSONRPCServerConfig(
            rpc_path="/a2a",
            agent_card_path="/.well-known/agent-card.json",
        ),
    ),
)

# 创建 Agent
analyst = Agent(
    role="Data Analyst",
    goal="Analyze data and create insightful visualizations",
    backstory="Expert data analyst with 10 years of experience in Python and pandas.",
    a2a=server_config,
    verbose=True,
)

# 注意：此示例中 Agent 被包装后，agent.to_agent_card("http://localhost:8080")
# 可以生成标准 A2A AgentCard，用于注册到 A2A 服务发现。
print(f"Agent configured as A2A server, ready to receive delegations")
```

### 示例 4：异步委托（async/await）

```python
"""示例 4：使用异步 kickoff 进行 A2A 委托"""
import asyncio
from crewai import Agent, Task, Crew
from crewai.a2a.config import A2AClientConfig

async def main():
    a2a_client = A2AClientConfig(
        endpoint="http://localhost:8080/.well-known/agent-card.json",
        timeout=60,
        max_turns=5,
    )

    agent = Agent(
        role="Async Coordinator",
        goal="Coordinate tasks asynchronously",
        backstory="You coordinate tasks with remote agents using async communication.",
        a2a=[a2a_client],
        verbose=True,
    )

    task = Task(
        description="Fetch the latest stock prices for AAPL and TSLA.",
        expected_output="Stock prices report.",
        agent=agent,
    )

    crew = Crew(agents=[agent], tasks=[task])
    result = await crew.akickoff()
    print(f"Async Result: {result.raw}")

asyncio.run(main())
```

### 示例 5：使用 AgentCard 签名

```python
"""示例 5：配置 AgentCard 签名，确保服务发现的安全性"""
from crewai import Agent
from crewai.a2a.config import (
    A2AServerConfig,
    AgentCardSigningConfig,
    ServerTransportConfig,
)

# 配置签名
signing = AgentCardSigningConfig(
    private_key_pem="""-----BEGIN PRIVATE KEY-----
MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQ...
-----END PRIVATE KEY-----""",
    key_id="my-agent-key-2026",
    algorithm="RS256",
)

server_config = A2AServerConfig(
    name="Secure Agent",
    description="A security-hardened A2A agent with signed AgentCard",
    version="1.0.0",
    signing_config=signing,
    transport=ServerTransportConfig(preferred="JSONRPC"),
)

agent = Agent(
    role="Secure Service Agent",
    goal="Provide secure services with verified identity",
    backstory="A security-conscious agent that proves its identity via JWS signatures.",
    a2a=server_config,
    verbose=True,
)

# AgentCard 将自动包含 JWS 签名
# agent.to_agent_card("http://localhost:8080")
print("Agent configured with JWS signing for AgentCard verification")
```

---

## 5. 设计亮点与注意事项

### 5.1 设计亮点

1. **零侵入式包装**：`wrap_agent_with_a2a_instance()` 通过 `MethodType` 动态替换实例方法，Agent 无需修改任何代码即可获得 A2A 能力。A2A 未配置时零开销回退到原始方法。

2. **双重缓存机制**：AgentCard 获取使用 `@lru_cache()`（同步）+ `@cached(ttl=300)`（异步）双重缓存，大幅减少网络请求，同时通过 `ttl_hash` 支持时间窗口过期。

3. **传输协商**：客户端和服务端支持多种传输协议（JSON-RPC、gRPC、HTTP+JSON），自动协商双方都支持的协议，确保最大兼容性。

4. **LLM 驱动的委托决策**：不预先定义委托规则，而是将可用 Agent 列表注入 Prompt，由 LLM 自行判断是否委托、委托给谁、何时停止。这提供了最大的灵活性。

5. **多轮对话管理**：通过 `max_turns` 限制、轮次警告、`trust_remote_completion_status` 信任模式，确保多轮对话不会无限循环。

6. **事件驱动架构**：每个关键节点都通过 `crewai_event_bus` 发送事件，包括 `A2AConversationStartedEvent`、`A2AMessageSentEvent`、`A2ADelegationStartedEvent`、`A2ADelegationCompletedEvent` 等，便于监控和调试。

7. **类型安全**：通过 `AgentResponseProtocol`（Protocol 类）、`DelegationContext`（NamedTuple）、`DelegationState`（NamedTuple）等类型定义，确保复杂的状态传递在类型层面是安全的。

### 5.2 注意事项

1. **`__func__` 与 `MethodType`**：在获取原始方法时使用 `agent.execute_task.__func__`（wrapper.py 第 115 行），而非 `agent.execute_task`，因为后者在调用时是绑定方法。绑定时使用 `object.__setattr__` 绕过 Pydantic 的验证。

2. **同步/异步对称**：wrapper.py 和 delegation.py 都提供了完整的同步和异步版本，但同步版本通过 `asyncio.run()` 包装异步实现，在已有运行中事件循环时使用独立线程。

3. **fail_fast 模式**：`fail_fast=True`（默认）时，Agent Card 获取失败会直接抛出异常；`fail_fast=False` 时会静默跳过不可达的 Agent 并在 Prompt 中标注为不可用。

4. **trust_remote_completion_status**：当设为 True 时，远程 Agent 返回 `completed` 后直接返回结果，不再让本地 LLM 进行二次分析。适合明确知道远程 Agent 会返回最终答案的场景。

5. **gRPC 认证限制**：HTTPDigest 和 APIKey（query/cookie 模式）不支持 gRPC 传输（delegation.py 第 784-794 行），使用时会抛出异常。

6. **文件附件**：需要 `crewai_files` 包才能使用文件附件功能（delegation.py 第 102-105 行），否则静默跳过。

7. **A2AConfig 废弃**：`A2AConfig` 已被标记为废弃，推荐使用 `A2AClientConfig`，废弃字段通过 `@model_validator` 自动迁移（config.py 第 446-462 行）。