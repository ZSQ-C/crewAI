# 阶段 D：Crew 调度引擎实现逻辑详解

## 1. 模块定位与架构图

### 1.1 模块定位

Crew 调度引擎是 CrewAI 框架的 **顶层编排器（Orchestrator）**，负责：

- 组装 Agent 团队（`agents`）和任务队列（`tasks`）
- 按策略（`Process.sequential` / `Process.hierarchical`）调度任务执行
- 管理任务间的上下文传递（`context` 依赖）
- 支持异步任务、条件任务、检查点恢复、流式输出
- 汇总所有任务的输出为统一的 `CrewOutput`

### 1.2 涉及的核心源码文件

| 文件 | 行数 | 核心职责 |
|------|------|----------|
| `lib/crewai/src/crewai/crew.py` | ~2217 行 | `Crew` 主类（Pydantic 模型），kickoff 入口、任务调度、Agent 组装、工具注入 |
| `lib/crewai/src/crewai/process.py` | ~11 行 | `Process` 枚举，定义 Sequential / Hierarchical 两种执行策略 |
| `lib/crewai/src/crewai/crews/crew_output.py` | ~74 行 | `CrewOutput` 输出封装类，聚合 raw / pydantic / json_dict / token_usage |
| `lib/crewai/src/crewai/crews/utils.py` | ~493 行 | 工具函数：`prepare_kickoff`、`prepare_task_execution`、`check_conditional_skip`、`run_for_each_async`、`StreamingContext` |

### 1.3 架构图

```
用户代码
    │
    ▼
┌──────────────────────────────────────────────────────────────────┐
│                     Crew.kickoff(inputs)                          │
│  crew.py 第 978-1068 行                                           │
│                                                                   │
│  ┌─────────────────────────────────────────────────┐             │
│  │  prepare_kickoff() — crews/utils.py 第 249-358 行 │             │
│  │  ├── before_kickoff_callbacks                    │             │
│  │  ├── CrewKickoffStartedEvent 事件发射             │             │
│  │  ├── 存储输入文件                                  │             │
│  │  ├── _interpolate_inputs() 变量插值                │             │
│  │  ├── setup_agents() Agent 初始化                   │             │
│  │  └── _handle_crew_planning() 规划生成              │             │
│  └─────────────────────────────────────────────────┘             │
│                           │                                       │
│          ┌────────────────┼────────────────┐                      │
│          ▼                                 ▼                      │
│  Process.sequential              Process.hierarchical              │
│  _run_sequential_process()       _run_hierarchical_process()       │
│  crew.py 第 1487-1489 行         crew.py 第 1491-1494 行           │
│          │                                 │                      │
│          ▼                                 ▼                      │
│  _execute_tasks()                   _create_manager_agent()        │
│  crew.py 第 1536-1605 行            crew.py 第 1496-1526 行        │
│          │                          _execute_tasks()               │
│          │                          crew.py 第 1536-1605 行        │
│          ▼                                 │                      │
│  ┌──────────────────────────────────────────┐                     │
│  │ for task in tasks:                       │                     │
│  │   prepare_task_execution()  ← utils.py  │                     │
│  │   ConditionalTask? → should_execute()?   │                     │
│  │   async? → execute_async() / execute_sync()│                   │
│  │   _get_context() → 上下文聚合            │                     │
│  │   _store_execution_log()                 │                     │
│  └──────────────────────────────────────────┘                     │
│                           │                                       │
│                           ▼                                       │
│               _create_crew_output()                                │
│               crew.py 第 1897-1933 行                              │
│                           │                                       │
│                           ▼                                       │
│                     CrewOutput                                     │
│  crews/crew_output.py 第 13-74 行                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## 2. 核心实现逻辑详解

### 2.1 Crew 类 — 字段定义与 kickoff 流程

**源码位置**：`lib/crewai/src/crewai/crew.py`，第 159-413 行（字段定义），第 978-1068 行（`kickoff` 方法）。

`Crew` 继承自 `FlowTrackable` 和 `BaseModel`（Pydantic），这使得它同时具备追踪能力和严格的类型校验。

#### 2.1.1 核心字段分类

**（A）执行配置字段**（第 221-237 行）：

```python
# crew.py 第 221-237 行
name: str | None = Field(default="crew")          # Crew 名称，影响记忆作用域命名
cache: bool = Field(default=False)                 # 工具结果缓存开关
tasks: list[Task] = Field(default_factory=list)    # 任务列表
agents: list[BaseAgent] = Field(default_factory=list)  # Agent 团队成员
process: Process = Field(default=Process.sequential)   # 执行策略
verbose: bool = Field(default=False)               # 详细日志
```

**大白话**：`name` 不仅是标识，还会影响记忆系统的命名空间（如 `/crew/research-crew`，见第 648 行）。`cache=True` 时，Agent 的工具调用结果会被缓存，相同参数复用结果（第 746-749 行）。

**（B）LLM 配置字段**（第 261-343 行）：

```python
# crew.py 第 261-343 行
manager_llm: str | BaseLLM | None = None      # 第 261-265 行：Manager Agent 的 LLM
manager_agent: BaseAgent | None = None         # 第 266-269 行：自定义 Manager Agent
function_calling_llm: str | LLM | None = None  # 第 270-278 行：函数调用 LLM（已废弃）
planning_llm: str | BaseLLM | None = None      # 第 334-343 行：规划 LLM
chat_llm: str | BaseLLM | None = None          # 第 362-368 行：聊天 LLM
```

**大白话**：`manager_llm` 和 `manager_agent` 是互斥的两种方式——要么指定 LLM 自动创建 Manager，要么传入自定义 Agent。`planning_llm` 用于 `planning=True` 时，在 kickoff 前自动生成任务执行计划并追加到 `task.description`。

**（C）功能开关字段**（第 238-340 行）：

```python
# crew.py 第 238-258 行
memory: bool | Memory | MemoryScope | MemorySlice | None = Field(default=False)
embedder: EmbedderConfig | None = None         # 嵌入器配置
usage_metrics: UsageMetrics | None = None       # 用量统计
# crew.py 第 330-333 行
planning: bool | None = Field(default=False)    # 是否启用执行规划
# crew.py 第 304-307 行
stream: bool = Field(default=False)             # 是否流式输出
```

**（D）回调与钩子字段**（第 282-303 行）：

```python
# crew.py 第 282-303 行
step_callback: SerializableCallable | None = None   # 每个 Agent 步骤回调
task_callback: SerializableCallable | None = None   # 每个 Task 完成回调
before_kickoff_callbacks: list[SerializableCallable] = Field(default_factory=list)
after_kickoff_callbacks: list[SerializableCallable] = Field(default_factory=list)
```

**大白话**：`before_kickoff_callbacks`（第 289-296 行）在 kickoff 准备阶段执行，可用于修改 `inputs`；`after_kickoff_callbacks`（第 297-303 行）在任务执行完毕后、返回结果前执行。`task_callback`（第 286-288 行）通过 `_set_tasks_callbacks`（第 2109-2113 行）注入到每个 Task 上。

**（E）高级功能字段**（第 352-413 行）：

```python
# crew.py 第 352-360 行
knowledge_sources: list[BaseKnowledgeSource] | None = None  # 知识源
knowledge: Knowledge | None = None                           # 知识检索实例
# crew.py 第 379-382 行
security_config: SecurityConfig = Field(default_factory=SecurityConfig)
# crew.py 第 383-390 行
checkpoint: CheckpointConfig | bool | None = None    # 检查点配置
# crew.py 第 391-394 行
token_usage: UsageMetrics | None = None              # Token 用量
# crew.py 第 395-398 行
tracing: bool | None = None                          # 追踪开关
```

#### 2.1.2 kickoff() 方法详解

**源码位置**：`crew.py` 第 978-1068 行。

```python
def kickoff(self, inputs=None, input_files=None, from_checkpoint=None):
    # 第 996-998 行：检查点恢复
    restored = apply_checkpoint(self, from_checkpoint)
    if restored is not None:
        return restored.kickoff(inputs=inputs, input_files=input_files)

    # 第 1000-1024 行：流式模式
    if self.stream:
        enable_agent_streaming(self.agents)
        ctx = StreamingContext()
        def run_crew():
            # 设置 self.stream = False 防止递归
            self.stream = False
            crew_result = self.kickoff(inputs=inputs, input_files=input_files)
            ...
        streaming_output = CrewStreamingOutput(
            sync_iterator=create_chunk_generator(ctx.state, run_crew, ctx.output_holder)
        )
        return streaming_output

    # 第 1026-1029 行：OpenTelemetry 追踪上下文
    baggage_ctx = baggage.set_baggage("crew_context", CrewContext(...))
    token = attach(baggage_ctx)

    # 第 1031 行：进入运行时作用域
    runtime_scope = crewai_event_bus._enter_runtime_scope()

    try:
        # 第 1033 行：准备阶段
        inputs = prepare_kickoff(self, inputs, input_files)

        # 第 1035-1042 行：策略分发
        if self.process == Process.sequential:
            result = self._run_sequential_process()
        elif self.process == Process.hierarchical:
            result = self._run_hierarchical_process()

        # 第 1044-1047 行：后处理
        for after_callback in self.after_kickoff_callbacks:
            result = after_callback(result)
        result = self._post_kickoff(result)
        self.usage_metrics = self.calculate_usage_metrics()
        return result

    except Exception as e:
        # 第 1053-1061 行：发射失败事件
        crewai_event_bus.emit(self, CrewKickoffFailedEvent(...))
        raise
    finally:
        # 第 1065-1068 行：资源清理
        self._drain_memory_writes()  # 排空记忆写入
        clear_files(self.id)          # 清理文件存储
        detach(token)                 # 脱离追踪上下文
        crewai_event_bus._exit_runtime_scope(runtime_scope)
```

**关键设计点**：

1. **流式模式递归**（第 1000-1024 行）：当 `stream=True` 时，`kickoff` 先创建 `StreamingContext`，然后将 `self.stream = False` 后递归调用自身，在后台线程中执行实际逻辑。这样避免了维护两套完全不同的执行路径。

2. **检查点优先**（第 996-998 行）：`apply_checkpoint` 如果返回一个恢复的 Crew 实例，则直接递归调用该实例的 `kickoff`，确保从断点继续。

3. **finally 保证清理**（第 1065-1068 行）：无论成功还是失败，都会排空记忆写入、清理文件存储、脱离追踪上下文。

#### 2.1.3 kickoff_async() 与 akickoff() 的区别

| 方法 | 源码行号 | 实现方式 | 使用场景 |
|------|----------|----------|----------|
| `kickoff()` | 978-1068 | 同步执行 | 标准同步调用 |
| `kickoff_async()` | 1109-1161 | `asyncio.to_thread(self.kickoff, ...)` 包装 | 在 async 上下文中调用同步 kickoff |
| `akickoff()` | 1189-1281 | 原生 async/await，使用 `_arun_sequential_process()` 和 `_aexecute_tasks()` | 全链路异步执行 |

**关键区别**：`kickoff_async`（第 1161 行）只是把同步 `kickoff` 放到线程池中执行，而 `akickoff`（第 1248-1255 行）使用原生异步方法 `_arun_sequential_process()` 和 `_aexecute_tasks()`，后者内部使用 `asyncio.create_task` 和 `await` 实现真正的异步任务调度。

---

### 2.2 Process 枚举 — Sequential vs Hierarchical

**源码位置**：`lib/crewai/src/crewai/process.py`，第 1-11 行。

```python
class Process(str, Enum):
    """Class representing the different processes that can be used to tackle tasks"""
    sequential = "sequential"
    hierarchical = "hierarchical"
    # TODO: consensual = 'consensual'
```

#### 2.2.1 Sequential 模式

**触发路径**：`kickoff()` → `_run_sequential_process()`（第 1487-1489 行）→ `_execute_tasks()`（第 1536-1605 行）。

**核心逻辑**：按 `self.tasks` 列表的顺序，逐个执行任务。每个 Task 由它的 `task.agent` 字段指定的 Agent 执行。

```python
# crew.py 第 1487-1489 行
def _run_sequential_process(self) -> CrewOutput:
    """Executes tasks sequentially and returns the final output."""
    return self._execute_tasks(self.tasks)
```

**验证规则**（第 753-763 行）：在 Sequential 模式下，每个 Task 都必须有 `agent` 字段：

```python
# crew.py 第 753-763 行
@model_validator(mode="after")
def validate_tasks(self) -> Self:
    if self.process == Process.sequential:
        for task in self.tasks:
            if task.agent is None:
                raise PydanticCustomError(
                    "missing_agent_in_task",
                    "Sequential process error: Agent is missing in the task with the following description: {description}",
                    {"description": task.description},
                )
    return self
```

#### 2.2.2 Hierarchical 模式

**触发路径**：`kickoff()` → `_run_hierarchical_process()`（第 1491-1494 行）→ `_create_manager_agent()` → `_execute_tasks()`。

**核心逻辑**：先创建/配置 Manager Agent，然后执行任务。在 Hierarchical 模式下，`_get_agent_to_use()`（第 1692-1695 行）始终返回 Manager Agent，而不是 Task 自己的 Agent：

```python
# crew.py 第 1692-1695 行
def _get_agent_to_use(self, task: Task) -> BaseAgent | None:
    if self.process == Process.hierarchical:
        return self.manager_agent
    return task.agent
```

**验证规则**（第 708-729 行）：Hierarchical 模式必须提供 `manager_llm` 或 `manager_agent`，且 Manager Agent 不能同时出现在 `agents` 列表中：

```python
# crew.py 第 708-729 行
@model_validator(mode="after")
def check_manager_llm(self) -> Self:
    if self.process == Process.hierarchical:
        if not self.manager_llm and not self.manager_agent:
            raise PydanticCustomError(
                "missing_manager_llm_or_manager_agent",
                "Attribute `manager_llm` or `manager_agent` is required when using hierarchical process.",
            )
        if (self.manager_agent is not None) and (
            self.agents.count(self.manager_agent) > 0
        ):
            raise PydanticCustomError(
                "manager_agent_in_agents",
                "Manager agent should not be included in agents list.",
            )
```

#### 2.2.3 两种模式的 Actor 差异

| 维度 | Sequential | Hierarchical |
|------|------------|--------------|
| 执行者 | 每个 Task 的 `task.agent` | 统一的 `manager_agent` |
| 任务分配 | 静态：Task 在创建时指定 Agent | 动态：Manager Agent 通过工具决定分配给谁 |
| Manager 工具 | 无 | `AgentTools`（`DelegateWorkTool` + `AskQuestionTool`） |
| 适用场景 | 明确的流水线工作流 | 需要动态决策的复杂工作流 |

---

### 2.3 依赖图构建与上下文传递

**重要说明**：CrewAI 当前版本 **不构建显式的依赖图或进行拓扑排序**。任务的执行顺序完全由 `self.tasks` 列表的顺序决定（Sequential 模式）或由 Manager Agent 动态决定（Hierarchical 模式）。`Task.context` 字段用于声明**上下文依赖**（即一个 Task 需要哪些前序 Task 的输出作为输入），但不改变执行顺序。

#### 2.3.1 Task.context 字段

**源码位置**：`lib/crewai/src/crewai/task.py`，第 161-164 行。

```python
# task.py 第 161-164 行
context: list[Task] | None | _NotSpecified = Field(
    description="Other tasks that will have their output used as context for this task.",
    default=NOT_SPECIFIED,
)
```

**大白话**：`context` 是一个 Task 列表，声明了当前 Task 依赖哪些前序 Task 的输出。例如：

```python
analysis_task = Task(
    description="分析研究结果",
    expected_output="分析报告",
    agent=analyst,
    context=[research_task]  # 依赖 research_task 的输出
)
```

#### 2.3.2 上下文聚合逻辑

**源码位置**：`crew.py` 第 1843-1852 行。

```python
# crew.py 第 1843-1852 行
@staticmethod
def _get_context(task: Task, task_outputs: list[TaskOutput]) -> str:
    if not task.context:
        return ""

    return (
        aggregate_raw_outputs_from_task_outputs(task_outputs)
        if task.context is NOT_SPECIFIED
        else aggregate_raw_outputs_from_tasks(task.context)
    )
```

这里有两个分支：

1. **`task.context is NOT_SPECIFIED`**（默认值）：使用 `aggregate_raw_outputs_from_task_outputs(task_outputs)`，即**聚合所有已执行任务**的 raw 输出，用 `\n\n----------\n\n` 分隔（见 `formatter.py` 第 13 行和第 26 行）。

2. **`task.context` 是明确的 Task 列表**：使用 `aggregate_raw_outputs_from_tasks(task.context)`，即**只聚合 context 列表中指定的那些 Task** 的输出。

**formatter.py 完整源码**（第 1-45 行）：

```python
# formatter.py 第 13 行
DIVIDERS: Final[str] = "\n\n----------\n\n"

# formatter.py 第 16-26 行
def aggregate_raw_outputs_from_task_outputs(task_outputs: list[TaskOutput]) -> str:
    """Generate string context from the task outputs."""
    return DIVIDERS.join(output.raw for output in task_outputs)

# formatter.py 第 29-45 行
def aggregate_raw_outputs_from_tasks(tasks: list[Task] | _NotSpecified) -> str:
    """Generate string context from the tasks."""
    task_outputs = (
        [task.output for task in tasks if task.output is not None]
        if isinstance(tasks, list)
        else []
    )
    return aggregate_raw_outputs_from_task_outputs(task_outputs)
```

#### 2.3.3 上下文在 _execute_tasks 中的使用

**源码位置**：`crew.py` 第 1575-1598 行。

在 `_execute_tasks` 循环中，上下文通过两种方式传递：

**异步任务**（第 1575-1584 行）：只传递最后一个同步 Task 的输出作为上下文：

```python
# crew.py 第 1575-1584 行
if task.async_execution:
    context = self._get_context(
        task, [last_sync_output] if last_sync_output else []
    )
    future = task.execute_async(
        agent=exec_data.agent,
        context=context,
        tools=exec_data.tools,
    )
    futures.append((task, future, task_index))
```

**同步任务**（第 1592-1600 行）：传递所有已完成的 Task 输出作为上下文：

```python
# crew.py 第 1592-1600 行
context = self._get_context(task, task_outputs)
task_output = task.execute_sync(
    agent=exec_data.agent,
    context=context,
    tools=exec_data.tools,
)
```

**设计原因**：异步任务在提交时，后续同步任务可能还未执行，因此只能传递 `last_sync_output`（最后一个同步任务的输出）。同步任务则能获取所有已完成的 `task_outputs`。

#### 2.3.4 依赖约束验证

Crew 在初始化时通过多个 `model_validator` 验证依赖关系的合法性：

**（A）禁止依赖未来任务**（第 850-866 行）：

```python
# crew.py 第 850-866 行
@model_validator(mode="after")
def validate_context_no_future_tasks(self) -> Self:
    """Validates that a task's context does not include future tasks."""
    task_indices = {id(task): i for i, task in enumerate(self.tasks)}
    for task in self.tasks:
        if isinstance(task.context, list):
            for context_task in task.context:
                if id(context_task) not in task_indices:
                    continue
                if task_indices[id(context_task)] > task_indices[id(task)]:
                    raise ValueError(
                        f"Task '{task.description}' has a context dependency "
                        f"on a future task '{context_task.description}', "
                        f"which is not allowed."
                    )
```

**（B）禁止异步任务依赖其他异步任务**（第 826-848 行）：

```python
# crew.py 第 826-848 行
@model_validator(mode="after")
def validate_async_task_cannot_include_sequential_async_tasks_in_context(self) -> Self:
    """异步任务不能在其 context 中包含其他连续异步任务（除非被同步任务分隔）"""
```

**（C）禁止 ConditionalTask 为异步**（第 813-824 行）：条件任务必须同步执行，因为需要根据前一个任务的结果即时判断。

**（D）禁止第一个任务为 ConditionalTask**（第 801-810 行）：条件任务需要前序任务的输出，所以不能是第一个。

**（E）必须至少有一个非条件任务**（第 785-799 行）。

---

### 2.4 Hierarchical 模式 — Manager Agent

**源码位置**：`crew.py` 第 1496-1526 行（`_create_manager_agent`），`tools/agent_tools/agent_tools.py` 第 1-36 行，`tools/agent_tools/delegate_work_tool.py` 第 1-30 行。

#### 2.4.1 Manager Agent 的创建

```python
# crew.py 第 1496-1526 行
def _create_manager_agent(self) -> None:
    if self.manager_agent is not None:
        # 用户自定义了 Manager
        self.manager_agent.allow_delegation = True
        manager = self.manager_agent
        if manager.tools is not None and len(manager.tools) > 0:
            self._logger.log("warning", "Manager agent should not have tools", ...)
            manager.tools = []
            raise Exception("Manager agent should not have tools")
    else:
        # 自动创建默认 Manager Agent
        self.manager_llm = create_llm(self.manager_llm)
        i18n = get_i18n(prompt_file=self.prompt_file)
        manager = Agent(
            role=i18n.retrieve("hierarchical_manager_agent", "role"),
            goal=i18n.retrieve("hierarchical_manager_agent", "goal"),
            backstory=i18n.retrieve("hierarchical_manager_agent", "backstory"),
            tools=AgentTools(agents=self.agents).tools(),
            allow_delegation=True,
            llm=self.manager_llm,
            verbose=self.verbose,
        )
        self.manager_agent = manager
    manager.crew = self
    if self.cache:
        manager.set_cache_handler(self._cache_handler)
```

**关键设计**：

1. **工具限制**（第 1500-1507 行）：Manager Agent **不能有自己的工具**，只能使用 `AgentTools`（`DelegateWorkTool` + `AskQuestionTool`）。如果用户传入了自定义 Manager Agent 且带有工具，会直接抛异常。

2. **国际化角色**（第 1510-1519 行）：自动创建的 Manager Agent 的 role/goal/backstory 来自 i18n 系统，支持多语言。

3. **自动委托**（第 1498 行）：`allow_delegation = True` 确保 Manager 可以委托工作。

#### 2.4.2 AgentTools — Manager 的工具集

**源码位置**：`lib/crewai/src/crewai/tools/agent_tools/agent_tools.py`，第 16-36 行。

```python
# agent_tools.py 第 16-36 行
class AgentTools:
    """Manager class for agent-related tools"""
    def __init__(self, agents: Sequence[BaseAgent]) -> None:
        self.agents = agents

    def tools(self) -> list[BaseTool]:
        coworkers = ", ".join([f"{agent.role}" for agent in self.agents])
        delegate_tool = DelegateWorkTool(
            agents=self.agents,
            description=I18N_DEFAULT.tools("delegate_work").format(coworkers=coworkers),
        )
        ask_tool = AskQuestionTool(
            agents=self.agents,
            description=I18N_DEFAULT.tools("ask_question").format(coworkers=coworkers),
        )
        return [delegate_tool, ask_tool]
```

**两个工具**：

| 工具 | 功能 | 参数 |
|------|------|------|
| `DelegateWorkTool` | 将任务委托给指定的 coworker | `task`, `context`, `coworker` |
| `AskQuestionTool` | 向指定的 coworker 提问 | `question`, `context`, `coworker` |

#### 2.4.3 DelegateWorkTool 详解

**源码位置**：`lib/crewai/src/crewai/tools/agent_tools/delegate_work_tool.py`，第 1-30 行。

```python
# delegate_work_tool.py 第 8-13 行
class DelegateWorkToolSchema(BaseModel):
    task: str = Field(..., description="The task to delegate")
    context: str = Field(..., description="The context for the task")
    coworker: str = Field(..., description="The role/name of the coworker to delegate to")

# delegate_work_tool.py 第 16-30 行
class DelegateWorkTool(BaseAgentTool):
    name: str = "Delegate work to coworker"
    args_schema: type[BaseModel] = DelegateWorkToolSchema

    def _run(self, task: str, context: str, coworker: str | None = None, **kwargs: Any) -> str:
        coworker = self._get_coworker(coworker, **kwargs)
        return self._execute(coworker, task, context)
```

**大白话**：Manager Agent 调用 `DelegateWorkTool` 时，需要提供三个参数：要执行的任务描述（`task`）、上下文（`context`）、以及目标 coworker 的角色名（`coworker`）。`_get_coworker` 方法根据角色名从 `self.agents` 列表中匹配对应的 Agent，然后调用 `_execute` 让其执行任务。

#### 2.4.4 Hierarchical 模式下的工具注入

**源码位置**：`crew.py` 第 1831-1841 行。

```python
# crew.py 第 1831-1841 行
def _update_manager_tools(self, task: Task, tools: list[BaseTool]) -> list[BaseTool]:
    if self.manager_agent:
        if task.agent:
            tools = self._inject_delegation_tools(tools, task.agent, [task.agent])
        else:
            tools = self._inject_delegation_tools(
                tools, self.manager_agent, self.agents
            )
    return tools
```

当 Task 有指定 Agent 时，只注入该 Agent 的委托工具；当 Task 没有指定 Agent 时，注入所有 Agent 的委托工具，让 Manager 自行选择。

---

### 2.5 CrewOutput — 输出封装

**源码位置**：`lib/crewai/src/crewai/crews/crew_output.py`，第 1-74 行。

#### 2.5.1 数据结构

```python
# crew_output.py 第 13-32 行
class CrewOutput(BaseModel):
    """Class that represents the result of a crew."""
    raw: str = Field(description="Raw output of crew", default="")
    pydantic: BaseModel | None = Field(description="Pydantic output of Crew", default=None)
    json_dict: dict[str, Any] | None = Field(description="JSON dict output of Crew", default=None)
    tasks_output: list[TaskOutput] = Field(description="Output of each task", default_factory=list)
    token_usage: UsageMetrics = Field(description="Processed token summary", default_factory=UsageMetrics)
```

#### 2.5.2 属性与方法

**（A）`usage_metrics` 属性**（第 34-42 行）：

```python
# crew_output.py 第 34-42 行
@property
def usage_metrics(self) -> dict[str, Any]:
    """Token usage as a plain dict."""
    return self.token_usage.model_dump()
```

**（B）`json` 属性**（第 44-51 行）：只有当最后一个 Task 的输出格式是 `OutputFormat.JSON` 时才返回 JSON 字符串：

```python
# crew_output.py 第 44-51 行
@property
def json(self) -> str | None:
    if self.tasks_output[-1].output_format != OutputFormat.JSON:
        raise ValueError(
            "No JSON output found in the final task. Please make sure to set the output_json property in the final task in your crew."
        )
    return json.dumps(self.json_dict)
```

**（C）`to_dict()` 方法**（第 53-60 行）：优先返回 `json_dict`，其次是 `pydantic.model_dump()`：

```python
# crew_output.py 第 53-60 行
def to_dict(self) -> dict[str, Any]:
    output_dict = {}
    if self.json_dict:
        output_dict.update(self.json_dict)
    elif self.pydantic:
        output_dict.update(self.pydantic.model_dump())
    return output_dict
```

**（D）`__getitem__` 支持**（第 62-67 行）：支持字典式访问 `crew_output['field_name']`：

```python
# crew_output.py 第 62-67 行
def __getitem__(self, key: str) -> Any:
    if self.pydantic and hasattr(self.pydantic, key):
        return getattr(self.pydantic, key)
    if self.json_dict and key in self.json_dict:
        return self.json_dict[key]
    raise KeyError(f"Key '{key}' not found in CrewOutput.")
```

**（E）`__str__` 智能输出**（第 69-74 行）：优先级：Pydantic → JSON → raw：

```python
# crew_output.py 第 69-74 行
def __str__(self) -> str:
    if self.pydantic:
        return str(self.pydantic)
    if self.json_dict:
        return str(self.json_dict)
    return self.raw
```

#### 2.5.3 CrewOutput 的创建时机

**源码位置**：`crew.py` 第 1897-1933 行。

```python
# crew.py 第 1897-1933 行
def _create_crew_output(self, task_outputs: list[TaskOutput]) -> CrewOutput:
    if not task_outputs:
        raise ValueError("No task outputs available to create crew output.")
    valid_outputs = [t for t in task_outputs if t.raw]
    if not valid_outputs:
        raise ValueError("No valid task outputs available to create crew output.")
    final_task_output = valid_outputs[-1]  # 取最后一个有效输出

    final_string_output = final_task_output.raw
    self._finish_execution(final_string_output)
    self.token_usage = self.calculate_usage_metrics()
    self._drain_memory_writes()
    crewai_event_bus.flush()
    crewai_event_bus.emit(self, CrewKickoffCompletedEvent(...))

    return CrewOutput(
        raw=final_task_output.raw,
        pydantic=final_task_output.pydantic,
        json_dict=final_task_output.json_dict,
        tasks_output=task_outputs,
        token_usage=self.token_usage,
    )
```

**关键设计**：

1. **以最后一个有效输出为准**（第 1904 行）：`valid_outputs[-1]` 的 `raw`/`pydantic`/`json_dict` 成为 CrewOutput 的顶层属性。
2. **保留所有任务输出**（第 1931 行）：`tasks_output` 字段包含所有 Task 的 `TaskOutput`，方便回溯。
3. **事件发射前先排空记忆**（第 1912 行）：确保 `CrewKickoffCompletedEvent` 发射前，所有背景记忆写入已完成。

#### 2.5.4 Token 用量统计

**源码位置**：`crew.py` 第 2131-2155 行。

```python
# crew.py 第 2131-2155 行
def calculate_usage_metrics(self) -> UsageMetrics:
    total_usage_metrics = UsageMetrics()
    for agent in self.agents:
        if isinstance(agent.llm, BaseLLM):
            llm_usage = agent.llm.get_token_usage_summary()
            total_usage_metrics.add_usage_metrics(llm_usage)
        else:
            if hasattr(agent, "_token_process"):
                token_sum = agent._token_process.get_summary()
                total_usage_metrics.add_usage_metrics(token_sum)
    if self.manager_agent and hasattr(self.manager_agent, "_token_process"):
        token_sum = self.manager_agent._token_process.get_summary()
        total_usage_metrics.add_usage_metrics(token_sum)
    if self.manager_agent:
        if isinstance(self.manager_agent.llm, BaseLLM):
            llm_usage = self.manager_agent.llm.get_token_usage_summary()
            total_usage_metrics.add_usage_metrics(llm_usage)
    self.usage_metrics = total_usage_metrics
    return total_usage_metrics
```

统计来源：所有 Agent 的 LLM 用量 + Manager Agent 的 LLM 用量。优先使用 `BaseLLM.get_token_usage_summary()`，退而求其次使用 `_token_process.get_summary()`。

---

## 3. 完整调用时序图

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                           Crew.kickoff(inputs)                                  │
│                           crew.py 第 978-1068 行                                │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  1. 检查点恢复 (第 996-998 行)                                                  │
│     └── apply_checkpoint(self, from_checkpoint)                                │
│         └── 有检查点? → 恢复 Crew 实例 → 递归调用 kickoff()                      │
│                                                                               │
│  2. 流式模式检查 (第 1000-1024 行)                                              │
│     └── stream=True? → 创建 StreamingContext → 后台线程执行 → 返回流式输出       │
│                                                                               │
│  3. prepare_kickoff() — crews/utils.py 第 249-358 行                           │
│     ├── 重置事件计数器 (第 268-279 行)                                          │
│     ├── 执行 before_kickoff_callbacks (第 289-292 行)                           │
│     ├── 发射 CrewKickoffStartedEvent (第 309-316 行)                            │
│     ├── 提取并存储文件 (第 321-336 行)                                           │
│     ├── _interpolate_inputs() 变量插值 (第 332 行)                              │
│     ├── _set_tasks_callbacks() 回调注入 (第 337 行)                             │
│     ├── setup_agents() Agent 初始化 (第 347-353 行)                             │
│     │   ├── agent.crew = self                                                  │
│     │   ├── agent.set_knowledge() 知识库注入                                    │
│     │   ├── agent.set_skills() 技能注入                                         │
│     │   └── agent.create_agent_executor() 创建执行器                            │
│     └── planning=True? → _handle_crew_planning() (第 355-356 行)                │
│                                                                               │
│  4. 策略分发 (第 1035-1042 行)                                                  │
│     ├── Sequential → _run_sequential_process() (第 1487-1489 行)               │
│     │       └── _execute_tasks(self.tasks) (第 1536-1605 行)                   │
│     │                                                                          │
│     └── Hierarchical → _run_hierarchical_process() (第 1491-1494 行)          │
│             ├── _create_manager_agent() (第 1496-1526 行)                      │
│             │   ├── 自定义 Manager? → 验证工具限制, allow_delegation=True       │
│             │   └── 自动创建? → Agent(role=..., tools=AgentTools(...))         │
│             └── _execute_tasks(self.tasks) (第 1536-1605 行)                   │
│                     │                                                          │
│                     ▼                                                          │
│  5. _execute_tasks() 详细流程 (第 1536-1605 行)                                 │
│     ┌──────────────────────────────────────────────────────────┐              │
│     │  for task_index, task in enumerate(tasks):                │              │
│     │                                                          │              │
│     │    ├── prepare_task_execution() (utils.py 第 124-183 行)  │              │
│     │    │   ├── _get_agent_to_use(task) 获取执行 Agent          │              │
│     │    │   │   ├── Hierarchical → manager_agent               │              │
│     │    │   │   └── Sequential → task.agent                    │              │
│     │    │   ├── _prepare_tools() 工具注入链 (第 1623-1690 行)   │              │
│     │    │   │   ├── 委托工具 (allow_delegation)                │              │
│     │    │   │   ├── 代码执行工具 (allow_code_execution)         │              │
│     │    │   │   ├── 多模态工具 (multimodal)                     │              │
│     │    │   │   ├── 平台工具 (apps)                             │              │
│     │    │   │   ├── MCP 工具 (mcps)                            │              │
│     │    │   │   ├── 记忆工具 (memory)                          │              │
│     │    │   │   └── 文件工具 (input_files)                     │              │
│     │    │   └── _log_task_start() 记录日志                      │              │
│     │    │                                                      │              │
│     │    ├── ConditionalTask? (第 1567-1573 行)                 │              │
│     │    │   └── should_execute(previous_output)?               │              │
│     │    │       └── NO → 跳过，记录 SkippedTaskOutput           │              │
│     │    │                                                      │              │
│     │    ├── task.async_execution? (第 1575-1584 行)            │              │
│     │    │   ├── YES → task.execute_async() → 存入 futures 列表  │              │
│     │    │   └── NO  → 先收集 pending 异步结果 (第 1586-1590 行) │              │
│     │    │       ├── task.execute_sync() (第 1593-1598 行)      │              │
│     │    │       │   ├── _get_context(task, task_outputs)       │              │
│     │    │       │   │   └── aggregate_raw_outputs_from_tasks() │              │
│     │    │       │   └── agent.execute_task()                   │              │
│     │    │       │       └── CrewAgentExecutor.invoke()         │              │
│     │    │       └── _store_execution_log() (第 1600 行)        │              │
│     │    │                                                      │              │
│     │  └── 收集所有异步 Future 结果 (第 1602-1603 行)           │              │
│     │  └── _create_crew_output(task_outputs) (第 1605 行)       │              │
│     └──────────────────────────────────────────────────────────┘              │
│                                                                               │
│  6. 后处理 (第 1044-1049 行)                                                    │
│     ├── after_kickoff_callbacks 逐个执行                                        │
│     ├── _post_kickoff(result)                                                  │
│     └── calculate_usage_metrics()                                              │
│                                                                               │
│  7. finally 清理 (第 1065-1068 行)                                              │
│     ├── _drain_memory_writes() 排空记忆写入                                     │
│     ├── clear_files(self.id) 清理文件存储                                       │
│     ├── detach(token) 脱离追踪上下文                                            │
│     └── crewai_event_bus._exit_runtime_scope() 退出运行时作用域                  │
│                                                                               │
│  返回 CrewOutput                                                               │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. 完整可运行示例

### 4.1 Sequential 模式 — 基础流水线

```python
"""示例 1：Sequential 模式 — 两个 Agent 顺序执行两个依赖任务"""
import os
from crewai import Agent, Task, Crew, Process

# 设置 LLM（使用环境变量或直接指定）
os.environ["OPENAI_API_KEY"] = "sk-your-key-here"

researcher = Agent(
    role="研究员",
    goal="研究指定主题的最新进展",
    backstory="你是一位经验丰富的研究员，擅长搜集和整理信息。",
    verbose=True,
)

writer = Agent(
    role="撰稿人",
    goal="将研究结果撰写成易读的报告",
    backstory="你是一位专业的科技撰稿人，擅长将复杂信息转化为通俗易懂的文章。",
    verbose=True,
)

research_task = Task(
    description="研究 2024 年人工智能在医疗领域的最新应用进展",
    expected_output="一份包含至少 3 个具体应用案例的研究摘要",
    agent=researcher,
)

write_task = Task(
    description="根据研究结果，撰写一篇面向普通读者的科普文章",
    expected_output="一篇 500 字左右的科普文章，包含引言、正文和结论",
    agent=writer,
    context=[research_task],  # 依赖 research_task 的输出作为上下文
)

crew = Crew(
    agents=[researcher, writer],
    tasks=[research_task, write_task],
    process=Process.sequential,
    verbose=True,
)

result = crew.kickoff()
print("=== 最终输出 ===")
print(result.raw)
print(f"\nToken 用量: {result.token_usage}")
```

**运行说明**：设置 `OPENAI_API_KEY` 环境变量后即可运行。`research_task` 先执行，其输出作为 `write_task` 的上下文传入。

---

### 4.2 Hierarchical 模式 — Manager Agent 自动分配

```python
"""示例 2：Hierarchical 模式 — Manager Agent 自动决定任务分配"""
import os
from crewai import Agent, Task, Crew, Process

os.environ["OPENAI_API_KEY"] = "sk-your-key-here"

researcher = Agent(
    role="市场研究员",
    goal="研究市场趋势和竞争对手动态",
    backstory="你是一位资深市场研究员，擅长数据分析和趋势洞察。",
    verbose=True,
)

analyst = Agent(
    role="数据分析师",
    goal="对收集到的数据进行深度分析和建模",
    backstory="你是一位数据科学家，精通统计分析和机器学习。",
    verbose=True,
)

strategist = Agent(
    role="策略顾问",
    goal="基于分析结果制定商业策略建议",
    backstory="你是一位经验丰富的商业策略顾问，服务过多个 Fortune 500 企业。",
    verbose=True,
)

task1 = Task(
    description="研究 2024 年电动汽车市场的竞争格局",
    expected_output="一份包含主要品牌、市场份额、技术趋势的市场研究报告",
    # Hierarchical 模式下可以不指定 agent，由 Manager 分配
)

task2 = Task(
    description="对市场数据进行深度分析，找出增长最快的细分市场",
    expected_output="一份数据分析报告，包含关键指标和趋势预测",
)

task3 = Task(
    description="基于分析结果，制定公司进入电动汽车市场的策略建议",
    expected_output="一份策略建议书，包含市场切入点、风险分析和行动计划",
)

crew = Crew(
    agents=[researcher, analyst, strategist],
    tasks=[task1, task2, task3],
    process=Process.hierarchical,
    manager_llm="gpt-4o",  # Manager Agent 使用 GPT-4o
    verbose=True,
)

result = crew.kickoff()
print("=== 最终输出 ===")
print(result.raw)
```

**运行说明**：Hierarchical 模式下，Manager Agent 会自动分析每个 Task 的描述，然后使用 `DelegateWorkTool` 将任务分配给最合适的 Agent。`manager_llm` 是必填参数。

---

### 4.3 异步任务 + 条件任务

```python
"""示例 3：混合使用异步任务和条件任务"""
import os
from crewai import Agent, Task, Crew, Process, ConditionalTask

os.environ["OPENAI_API_KEY"] = "sk-your-key-here"

researcher = Agent(
    role="内容研究员",
    goal="高效研究指定主题",
    backstory="你是一位高效的内容研究员。",
    verbose=True,
)

fact_checker = Agent(
    role="事实核查员",
    goal="验证研究结果中事实的准确性",
    backstory="你是一位严谨的事实核查员。",
    verbose=True,
)

writer = Agent(
    role="内容撰稿人",
    goal="撰写高质量内容",
    backstory="你是一位经验丰富的内容撰稿人。",
    verbose=True,
)

# 任务 1：研究（同步执行）
research_task = Task(
    description="研究 AI 在金融科技领域的应用",
    expected_output="一份包含具体应用案例的研究摘要",
    agent=researcher,
)

# 任务 2：事实核查（条件任务 — 只有研究结果包含"区块链"时才执行）
def should_check(output) -> bool:
    """如果研究结果包含'区块链'关键词，则进行事实核查"""
    return "区块链" in output.raw

check_task = ConditionalTask(
    description="对研究结果中关于区块链的部分进行事实核查",
    expected_output="事实核查报告",
    agent=fact_checker,
    condition=should_check,
)

# 任务 3：撰写文章（异步执行）
write_task = Task(
    description="根据所有前序任务的结果，撰写一篇博客文章",
    expected_output="一篇 800 字的博客文章",
    agent=writer,
    async_execution=True,  # 异步执行
)

crew = Crew(
    agents=[researcher, fact_checker, writer],
    tasks=[research_task, check_task, write_task],
    process=Process.sequential,
    verbose=True,
)

result = crew.kickoff()
print("=== 最终输出 ===")
print(result.raw)
print(f"\n所有任务输出数: {len(result.tasks_output)}")
for i, to in enumerate(result.tasks_output):
    print(f"  Task {i+1}: {to.agent} — {to.raw[:50]}...")
```

**运行说明**：`check_task` 只有当 `research_task` 的输出包含"区块链"时才执行，否则跳过。`write_task` 被标记为异步执行。

---

### 4.4 流式输出模式

```python
"""示例 4：流式输出 — 实时获取 Crew 执行进展"""
import os
from crewai import Agent, Task, Crew, Process

os.environ["OPENAI_API_KEY"] = "sk-your-key-here"

researcher = Agent(
    role="快速研究员",
    goal="快速研究并汇报结果",
    backstory="你是一位高效的研究员。",
    verbose=True,
)

task = Task(
    description="简要介绍量子计算的最新进展",
    expected_output="一段 200 字的介绍",
    agent=researcher,
)

crew = Crew(
    agents=[researcher],
    tasks=[task],
    process=Process.sequential,
    stream=True,  # 启用流式输出
    verbose=True,
)

streaming_result = crew.kickoff()

# 流式消费输出
print("=== 流式输出开始 ===")
for chunk in streaming_result:
    print(chunk, end="", flush=True)
print("\n=== 流式输出结束 ===")

# 流式结束后可以获取最终结果
final_result = streaming_result.result
print(f"\n最终结果: {final_result.raw}")
print(f"Token 用量: {final_result.token_usage}")
```

**运行说明**：`stream=True` 时，`kickoff()` 返回一个 `CrewStreamingOutput` 对象，可以迭代获取实时输出块。迭代结束后，通过 `.result` 属性获取最终的 `CrewOutput`。

---

### 4.5 kickoff_for_each — 批量输入处理

```python
"""示例 5：kickoff_for_each — 对多个输入批量执行同一个 Crew"""
import os
from crewai import Agent, Task, Crew, Process

os.environ["OPENAI_API_KEY"] = "sk-your-key-here"

analyst = Agent(
    role="话题分析师",
    goal="对指定话题进行简要分析",
    backstory="你是一位多领域的分析师。",
    verbose=True,
)

task = Task(
    description="分析话题：{topic}，提供 3 个关键要点",
    expected_output="3 个关键要点的列表",
    agent=analyst,
)

crew = Crew(
    agents=[analyst],
    tasks=[task],
    process=Process.sequential,
    verbose=True,
)

# 批量输入
inputs = [
    {"topic": "人工智能监管"},
    {"topic": "量子计算商业化"},
    {"topic": "可再生能源存储"},
]

results = crew.kickoff_for_each(inputs)

for i, (inp, result) in enumerate(zip(inputs, results)):
    print(f"\n=== 话题 {i+1}: {inp['topic']} ===")
    print(result.raw)

print(f"\n总计 Token 用量: {crew.usage_metrics}")
```

**运行说明**：`kickoff_for_each` 对每个输入字典创建 Crew 的副本并执行，最后汇总所有结果。`{topic}` 在 `task.description` 中会被自动替换为输入中的值。

---

## 5. 设计亮点与注意事项

### 5.1 设计亮点

| 亮点 | 说明 | 源码位置 |
|------|------|----------|
| **策略模式** | `Process` 枚举 + `_run_sequential_process` / `_run_hierarchical_process` 实现策略模式，扩展新策略只需添加枚举值和方法 | `process.py` 第 1-11 行, `crew.py` 第 1035-1042 行 |
| **流式递归** | `stream=True` 时 `kickoff` 递归调用自身（设 `self.stream=False`），避免维护两套执行路径 | `crew.py` 第 1000-1024 行 |
| **工具注入链** | `_prepare_tools` 按优先级分层注入（委托→代码→多模态→平台→MCP→记忆→文件），`_merge_tools` 按名称去重 | `crew.py` 第 1623-1690 行 |
| **Pydantic 模型验证器链** | 多个 `@model_validator(mode="after")` 组成验证链，确保 Crew 配置的合法性（依赖方向、异步约束、条件任务约束等） | `crew.py` 第 752-866 行 |
| **CrewOutput 多格式兼容** | 同时保留 `raw`/`pydantic`/`json_dict` 三种格式，`__str__` 和 `__getitem__` 实现智能路由 | `crew_output.py` 第 62-74 行 |
| **检查点恢复** | 通过 `apply_checkpoint` 和 `_restore_runtime` 支持断点续传，`_execute_tasks` 的 `start_index` 参数支持从中间任务恢复 | `crew.py` 第 414-437 行, 第 464-524 行 |
| **异步任务延迟收集** | 异步任务提交 Future 后不立即等待，直到遇到下一个同步任务时才批量收集，最大化并行度 | `crew.py` 第 1586-1590 行 |
| **资源清理保证** | `kickoff` 的 `finally` 块确保无论成功失败都清理资源（记忆排空、文件清理、追踪上下文脱离） | `crew.py` 第 1065-1068 行 |

### 5.2 注意事项

1. **没有显式的拓扑排序**：任务的执行顺序完全由 `self.tasks` 列表的顺序决定，`Task.context` 只注入上下文不改变执行顺序。如果 `context` 引用了尚未执行的任务，`validate_context_no_future_tasks`（第 850-866 行）会抛异常。

2. **Hierarchical 模式下的 task.agent**：虽然 Task 可以指定 `agent`，但在 Hierarchical 模式下，`_get_agent_to_use()` 始终返回 `manager_agent`（第 1692-1695 行）。`task.agent` 仅用于 `_update_manager_tools` 中决定注入哪些委托工具（第 1831-1841 行）。

3. **异步任务约束**：异步任务（`async_execution=True`）的 context 只能是 `last_sync_output`（第 1576-1578 行），不能依赖其他异步任务的结果。且 Crew 末尾最多只能有一个异步任务（第 766-783 行）。

4. **ConditionalTask 约束**：不能是第一个任务（第 801-810 行）、不能是异步任务（第 813-824 行）、Crew 中必须有至少一个非条件任务（第 785-799 行）。

5. **Manager Agent 工具限制**：Manager Agent 只能使用 `AgentTools`（`DelegateWorkTool` + `AskQuestionTool`），不能有其他自定义工具。如果用户传入带有工具的 Manager Agent，会直接抛异常（第 1500-1507 行）。

6. **`copy()` 方法的深拷贝**：`Crew.copy()`（第 2044-2107 行）对 agents、tasks、manager_agent 进行深拷贝，对 LLM 引用进行浅拷贝。`kickoff_for_each` 依赖 `copy()` 创建副本以避免状态污染（第 1095 行）。

7. **`crew.py` 文件长度**：`crew.py` 超过 2200 行，同时承担了 Crew 模型定义、任务调度、工具注入、记忆管理、检查点恢复、replay、训练、测试等多种职责。建议在阅读时按 `model_validator` → `kickoff` → `_execute_tasks` → `_prepare_tools` → `_create_crew_output` 的顺序追踪。