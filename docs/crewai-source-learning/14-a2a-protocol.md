# 阶段十四：A2A 协议（Agent-to-Agent）— 源码深度解析

---

## 1. 模块定位

### 1.1 一句话概括

**A2A（Agent-to-Agent）是 CrewAI 的跨 Agent 通信协议层，基于 Google Agent-to-Agent 协议（A2A SDK），通过「Agent Card 服务发现 + 多传输层协商 + 异步对话管理 + 并行委托 + 推送通知」架构，实现了异构建 Agent 之间的远程协作、任务委托和结果交换。**

### 1.2 在整体架构中的位置

```
┌──────────────────────────────────────────────────────────────────┐
│                      A2A 协议架构                                │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Agent A (本地)                     Agent B (远程)                │
│  ┌─────────────────┐              ┌─────────────────┐            │
│  │ execute_task()   │  委托任务   │ A2A Server      │            │
│  │   ↓              │ ──────────▶ │   ↓              │            │
│  │ wrap_agent_with  │  HTTP/JSON  │ execute_task()  │            │
│  │ _a2a_instance()  │ ◀────────── │   ↓              │            │
│  │   ↓              │   结果返回   │ Agent 执行       │            │
│  │ execute_a2a_     │             │   ↓              │            │
│  │ delegation()     │  Agent Card │ 返回结果          │            │
│  └─────────────────┘  ◀────────  └─────────────────┘            │
│                                                                   │
│  核心组件:                                                        │
│  ├── AgentCard     : Agent 身份/能力描述（类似名片）              │
│  ├── A2AConfig     : 客户端配置（远程 Agent 列表）               │
│  ├── A2AServerConfig: 服务端配置（暴露本地 Agent）               │
│  ├── Delegation    : 委托执行逻辑（多轮对话、并行）              │
│  └── Transport     : JSONRPC / gRPC / HTTP 传输层               │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

### 1.3 本阶段涉及的核心源码文件

| 文件 | 核心职责 |
|------|----------|
| `a2a/wrapper.py` | A2A 包装器：将 Agent 的 execute_task/kickoff 方法注入 A2A 委托能力 |
| `a2a/config.py` | A2AConfig / A2AServerConfig / A2AClientConfig：A2A 配置模型 |
| `a2a/utils/delegation.py` | execute_a2a_delegation：实际多轮对话委托逻辑 |
| `a2a/utils/agent_card.py` | AgentCard 获取/缓存/签名：服务发现 |
| `a2a/templates.py` | A2A 对话模板：系统提示词 |
| `a2a/extensions/` | A2A 扩展：A2UI 等 |
| `a2a/auth/` | A2A 认证：API Key / Digest / TLS |
| `a2a/updates/` | 更新机制：Polling / Streaming / Push Notification |
| `tools/agent_tools/delegate_work_tool.py` | DelegateWorkTool：Local Agent 委托工具 |

---

## 2. 源码分层拆解

### 2.1 第一层：A2A 配置模型

**文件：** `lib/crewai/src/crewai/a2a/config.py`

```python
# ===== 客户端配置：连接到远程 Agent =====
class A2AClientConfig(BaseModel):
    """连接远程 A2A Agent 的配置。"""
    url: str                              # 远程 Agent URL
    agent_card: AgentCard | None = None   # Agent Card（缓存）
    auth: ClientAuthScheme | None = None  # 认证方案
    transport: ClientTransportConfig | None = None  # 传输配置
    extensions: list[ValidatedA2AExtension] = []
    context_id: str | None = None         # 对话上下文 ID

# ===== 服务端配置：暴露本地 Agent =====
class A2AServerConfig(BaseModel):
    """暴露本地 Agent 为 A2A 服务端的配置。"""
    agent_card: AgentCard                 # Agent 名片
    transport: ServerTransportConfig      # 服务端传输
    auth: ServerAuthScheme | None = None  # 服务端认证
    update_config: UpdateConfig           # 更新配置（Streaming/Polling/Push）
    extensions: list[ServerExtension] = []

# ===== 联合类型 =====
A2AConfig = A2AClientConfig | A2AServerConfig

# Agent 使用方式
agent = Agent(
    role="Orchestrator",
    a2a=[
        A2AClientConfig(url="https://agent-b.example.com/a2a"),  # 远程 Agent
        A2AServerConfig(agent_card=..., transport=...)           # 暴露自己
    ],
)
```

---

### 2.2 第二层：Agent Wrapper（A2A 注入）

**文件：** `lib/crewai/src/crewai/a2a/wrapper.py`

```python
def wrap_agent_with_a2a_instance(agent, extension_registry=None):
    """将 A2A 委托能力注入到 Agent 实例。"""

    # 保存原始方法
    original_execute_task = agent.execute_task.__func__

    @wraps(original_execute_task)
    def execute_task_with_a2a(self, task, context=None, tools=None):
        """带 A2A 委托的 execute_task。"""
        if not self.a2a:
            # 没有 A2A 配置 → 走原始流程
            return original_execute_task(self, task, context, tools)

        # 解析 A2A 配置
        a2a_agents, agent_response_model = get_a2a_agents_and_response_model(self.a2a)

        # 执行 A2A 委托（多轮对话）
        return _execute_task_with_a2a(
            self=self,
            a2a_agents=a2a_agents,
            original_fn=original_execute_task,
            task=task,
            agent_response_model=agent_response_model,
            context=context,
            tools=tools,
            extension_registry=extension_registry,
        )

    # 替换方法（使用 MethodType 绑定到实例）
    object.__setattr__(agent, "execute_task", MethodType(execute_task_with_a2a, agent))
```

**大白话：** `wrap_agent_with_a2a_instance` 是 A2A 的"注入器"——它把 Agent 原始的 `execute_task` 方法替换为带 A2A 委托能力的新方法。如果 Agent 没有配置 `a2a`，就原样执行；如果有，就尝试委托给远程 Agent。

---

### 2.3 第三层：委托执行（Delegation）

**文件：** `lib/crewai/src/crewai/a2a/utils/delegation.py`

```python
def execute_a2a_delegation(
    delegation_context: DelegationContext,
    task: Task,
    get_llm_response: Callable,
    get_agent_output: Callable,
    extension_registry: ExtensionRegistry,
) -> str:
    """执行 A2A 委托的多轮对话。"""

    # 1. 获取远程 Agent Card
    agent_card = fetch_agent_card(config.url, config.auth)

    # 2. 创建 A2A Client
    client = ClientFactory.create(agent_card, ClientConfig(...))

    # 3. 发送任务
    task_id = client.send_task(
        message=task.description,
        context_id=context_id,
        extensions=extensions,
    )

    # 4. 多轮对话循环
    for turn in range(max_turns):
        # 获取 Agent 响应
        response = client.get_task(task_id)

        if response.state == TaskState.COMPLETED:
            return response.result

        elif response.state == TaskState.INPUT_REQUIRED:
            # 远程 Agent 需要更多信息 → 本地 LLM 决定
            new_message = get_llm_response(response)
            client.send_message(task_id, new_message)

        elif response.state == TaskState.FAILED:
            raise DelegationError(response.error)

    raise MaxTurnsExceededError(max_turns)

# 异步版本
async def aexecute_a2a_delegation(...):
    """异步委托执行。"""
```

---

### 2.4 第四层：Agent Card（服务发现）

**文件：** `lib/crewai/src/crewai/a2a/utils/agent_card.py`

```python
def fetch_agent_card(url, auth=None) -> AgentCard:
    """获取远程 Agent 的 Agent Card（同步）。"""
    headers = _prepare_auth_headers(auth)
    response = httpx.get(f"{url}/.well-known/agent-card.json", headers=headers)
    return AgentCard.model_validate(response.json())

@cached(ttl=300)  # 5 分钟缓存
async def afetch_agent_card_cached(url, auth=None) -> AgentCard:
    """获取并缓存 Agent Card（异步 + 缓存）。"""
    ...

def inject_a2a_server_methods(agent, server_config):
    """将 Agent 暴露为 A2A 服务端。"""
    # 绑定到 Agent 实例，让外部可以通过 A2A 协议调用
```

**AgentCard 结构：**

```json
{
    "name": "Research Agent",
    "description": "专业研究 Agent",
    "url": "https://agent.example.com/a2a",
    "skills": [
        {"id": "web_search", "name": "Web Search", "description": "..."}
    ],
    "capabilities": {
        "streaming": true,
        "pushNotifications": false
    },
    "defaultInputModes": ["text"],
    "defaultOutputModes": ["text"]
}
```

---

### 2.5 第五层：并行委托（Parallel Delegation）

```python
def _execute_parallel_delegations(
    tasks: list[tuple[str, A2AConfig]],
    context_id: str,
    max_workers: int = 10,
) -> list[TaskStateResult]:
    """并行委托多个任务给远程 Agent。"""
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(execute_a2a_delegation, task, config): task
            for task, config in tasks
        }
        results = []
        for future in as_completed(futures):
            results.append(future.result())
        return results
```

---

## 3. 完整调用时序图

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         A2A 协议完整时序                                  │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  Agent A (本地 Orchestrator)              Agent B (远程 Researcher)       │
│  ─────────────────────────                ──────────────────────────      │
│                                                                           │
│  1. 初始化阶段                                                             │
│     agent = Agent(                                                        │
│         role="Orchestrator",                                              │
│         a2a=[                                                             │
│             A2AClientConfig(                                              │
│                 url="https://agent-b/a2a",                                │
│                 auth=APIKeyAuth(api_key="xxx"),                           │
│             ),                                                            │
│         ],                                                                │
│     )                                                                     │
│         │                                                                  │
│         └── wrap_agent_with_a2a_instance(agent)                           │
│             ├── 获取原始 execute_task                                     │
│             └── 替换为 execute_task_with_a2a                              │
│                                                                           │
│  2. 任务执行阶段                                                            │
│     agent.execute_task(task)                                              │
│         │                                                                  │
│         ├── [a2a 已配置] → 进入 A2A 委托流程                               │
│         │                                                                  │
│         ├── get_a2a_agents_and_response_model()                            │
│         │   └── 解析 A2A 配置: [A2AClientConfig(url="agent-b")]           │
│         │                                                                  │
│         ├── 发射 A2ADelegationStartedEvent                                 │
│         │                                                                  │
│         ├── execute_a2a_delegation(config, task)                           │
│         │   │                                                              │
│         │   ├── fetch_agent_card("https://agent-b/a2a")                   │
│         │   │   ─────────────────────────────────────────▶                │
│         │   │   GET /.well-known/agent-card.json                          │
│         │   │   ◀─────────────────────────────────────────                │
│         │   │   {                                                          │
│         │   │     "name": "Research Agent",                               │
│         │   │     "skills": [{"id": "web_search"}],                       │
│         │   │   }                                                          │
│         │   │                                                              │
│         │   ├── create_client(agent_card, config)                         │
│         │   │   └── 协商传输层 (JSONRPC / gRPC)                            │
│         │   │                                                              │
│         │   ├── 发射 A2AConversationStartedEvent                           │
│         │   │                                                              │
│         │   ├── send_task(message=task.description)                       │
│         │   │   ─────────────────────────────────────────▶                │
│         │   │   POST /tasks {message: "研究 AI 最新进展"}                 │
│         │   │                                                              │
│         │   │   Agent B 收到请求，开始执行                                  │
│         │   │   │                                                          │
│         │   │   │   Agent B.execute_task(task)                            │
│         │   │   │       ├── LLM 推理                                       │
│         │   │   │       ├── 工具调用                                       │
│         │   │   │       └── 生成结果                                       │
│         │   │   │                                                          │
│         │   │   ◀─────────────────────────────────────────                │
│         │   │   {task_id: "123", state: "completed"}                      │
│         │   │                                                              │
│         │   ├── [多轮对话] state == "input_required"                       │
│         │   │   ├── 本地 LLM 分析需要什么信息                               │
│         │   │   └── send_message(task_id, additional_info)                │
│         │   │                                                              │
│         │   └── state == "completed" → 返回结果                             │
│         │                                                                  │
│         ├── 发射 A2ADelegationCompletedEvent                               │
│         │                                                                  │
│         └── 返回结果给 Agent A                                              │
│                                                                           │
│  3. 并行委托                                                                │
│     agent.delegate_to_multiple([task1, task2, task3])                     │
│         │                                                                  │
│         ├── ThreadPoolExecutor(max_workers=10)                             │
│         │   ├── future1: execute_a2a_delegation(task1, agent_x)           │
│         │   ├── future2: execute_a2a_delegation(task2, agent_y)           │
│         │   └── future3: execute_a2a_delegation(task3, agent_z)           │
│         │                                                                  │
│         └── as_completed → 收集所有结果                                    │
│                                                                           │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 4. 核心设计亮点

### 4.1 Agent Card 服务发现

```python
# 标准端点: GET /.well-known/agent-card.json
{
    "name": "Research Agent",
    "url": "https://agent.example.com/a2a",
    "skills": [{"id": "web_search", ...}],
    "capabilities": {"streaming": true, "pushNotifications": false},
}
```

通过标准 HTTP 端点发现 Agent 的能力、技能和传输方式，类似 REST API 的 OpenAPI Spec。

### 4.2 多传输层协商

```python
# 自动协商: JSONRPC → gRPC → HTTP
from crewai.a2a.utils.transport import negotiate_transport

transport = negotiate_transport(
    agent_card=agent_card,
    client_config=client_config,
    preferred=["JSONRPC", "gRPC"],
)
```

### 4.3 方法注入模式（Wrapper）

```python
# 通过 MethodType 动态替换实例方法
object.__setattr__(agent, "execute_task", MethodType(execute_task_with_a2a, agent))
```

不修改 Agent 类定义，而是在实例化时动态注入 A2A 能力，保持 Agent 类的纯净。

### 4.4 多轮对话管理

```python
for turn in range(max_turns):
    response = client.get_task(task_id)
    if response.state == COMPLETED: break
    if response.state == INPUT_REQUIRED:
        new_msg = llm.decide(response)  # LLM 决定下一步
        client.send_message(task_id, new_msg)
```

### 4.5 更新机制三选一

| 机制 | 适用场景 |
|------|----------|
| **Polling** | 轮询任务状态，简单但延迟高 |
| **Streaming** | 实时流式推送进度 |
| **Push Notification** | 服务端主动推送，Webhook 回调 |

---

## 5. 生产落地拓展改造

### 5.1 A2A 网关（统一入口）

```python
class A2AGateway:
    """统一 A2A 网关，管理所有远程 Agent 连接。"""

    def __init__(self):
        self._registry: dict[str, A2AClientConfig] = {}

    def register(self, name, config):
        self._registry[name] = config

    def delegate(self, agent_name, task):
        config = self._registry[agent_name]
        return execute_a2a_delegation(config, task)
```

### 5.2 Agent 发现注册中心

```python
class AgentRegistry:
    """集中式 Agent 注册中心（类似 Consul/Eureka）。"""

    def register(self, agent_card):
        self._store[agent_card.name] = agent_card

    def discover(self, skill=None, capabilities=None):
        return [card for card in self._store.values()
                if (not skill or skill in card.skills)]
```

### 5.3 负载均衡

```python
class LoadBalancedA2AClient:
    def __init__(self, urls: list[str]):
        self._urls = urls
        self._index = 0

    def delegate(self, task):
        url = self._urls[self._index % len(self._urls)]
        self._index += 1
        return execute_a2a_delegation(A2AClientConfig(url=url), task)
```

---

## 6. 面试深挖问题清单

| # | 问题 | 考察点 |
|---|------|--------|
| 1 | Agent Card 的作用是什么？包含哪些关键字段？ | 服务发现、能力描述 |
| 2 | `wrap_agent_with_a2a_instance` 是如何注入 A2A 能力的？ | MethodType、动态方法替换 |
| 3 | A2A 的多轮对话是如何管理的？ | send_task → get_task → send_message |
| 4 | 三种更新机制（Polling/Streaming/Push）各自适用什么场景？ | 实时性、资源消耗 |
| 5 | A2AClientConfig 和 A2AServerConfig 的区别？ | 客户端 vs 服务端 |
| 6 | 传输层协商（JSONRPC/gRPC）是如何实现的？ | negotiate_transport |
| 7 | Agent Card 的缓存策略（TTL=300s）是如何实现的？ | @cached 装饰器、aiocache |
| 8 | 并行委托（ThreadPoolExecutor）的并发控制？ | max_workers、as_completed |
| 9 | 认证方案的扩展点在哪里？ | ClientAuthScheme 抽象 |
| 10 | A2A 与 MCP 的区别是什么？ | Agent 通信 vs 工具调用 |

---

## 7. 简易可运行 Demo

```python
"""Demo: A2A 协议 — 跨 Agent 委托协作"""
from crewai import Agent, Task, Crew
from crewai.a2a.config import A2AClientConfig, A2AServerConfig
from a2a.types import AgentCard, AgentSkill, AgentCapabilities

# ===== Agent B: 远程 Researcher（暴露为 A2A 服务端）=====
agent_b = Agent(
    role="Research Specialist",
    goal="专业研究",
    llm="gpt-4o-mini",
    tools=[search_tool],
    a2a=A2AServerConfig(
        agent_card=AgentCard(
            name="Research Specialist",
            description="专业研究 Agent",
            url="https://agent-b.example.com/a2a",
            skills=[
                AgentSkill(id="web_search", name="Web Search",
                           description="搜索互联网信息"),
            ],
            capabilities=AgentCapabilities(streaming=True),
        ),
        transport=ServerTransportConfig(http=HTTPServerConfig(port=8080)),
    ),
)

# ===== Agent A: 本地 Orchestrator（委托给 Agent B）=====
agent_a = Agent(
    role="Orchestrator",
    goal="协调多个 Agent 完成任务",
    llm="gpt-4o-mini",
    a2a=[
        A2AClientConfig(
            url="https://agent-b.example.com/a2a",
            auth=APIKeyAuth(api_key="secret-key"),
        ),
    ],
)

# 执行时，Agent A 会自动将任务委托给 Agent B
task = Task(
    description="研究 AI Agent 框架的最新进展",
    expected_output="研究报告",
    agent=agent_a,
)

crew = Crew(agents=[agent_a, agent_b], tasks=[task])
result = crew.kickoff()
print(f"结果: {result}")
```

---

**下一阶段解析指令：**

```
# 当前解析目标
模块名称：Project 声明式定义
对应源码文件路径：
- lib/crewai/src/crewai/project/annotations.py（注解/装饰器）
- lib/crewai/src/crewai/project/crew_definition.py（Crew 声明式定义）
- lib/crewai/src/crewai/project/crew_base.py（CrewBase 基类）
- lib/crewai/src/crewai/project/declarative_refs.py（声明式引用解析）
- lib/crewai/src/crewai/project/pipeline.py（Pipeline 流水线）

# 本次输出硬性要求，缺一不可
1. 模块定位（一句话 + 架构位置 + 核心文件清单）
2. 源码分层拆解（文件→类→方法→关键代码行）
3. 完整调用时序图（@CrewBase → @agent → @task → YAML 配置 → Crew 实例化）
4. 核心设计亮点（声明式 YAML、装饰器注册、延迟解析、引用注入）
5. 生产落地拓展改造（YAML 配置中心、环境变量注入、多环境管理）
6. 面试深挖问题清单（10 题）
7. 简易可运行 Demo 代码
```