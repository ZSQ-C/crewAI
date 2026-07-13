# 阶段四：Crew 调度引擎 — 源码深度解析

---

## 1. 模块定位

### 1.1 一句话概括

**Crew 调度引擎是 CrewAI 的「总指挥中心」，负责组装 Agent 团队、管理任务队列、按策略（顺序/层级）调度执行、汇总输出，是整个框架的顶层入口和编排器。**

### 1.2 在整体架构中的位置

```
用户代码
    │
    ▼
Crew.kickoff(inputs)  ← 本阶段核心
    │
    ├── Process.sequential → _run_sequential_process()
    │       └── _execute_tasks(tasks) → 逐个执行 Task
    │
    └── Process.hierarchical → _run_hierarchical_process()
            └── _create_manager_agent() → 创建管理者 Agent
            └── _execute_tasks(tasks) → Manager 分配任务
                    │
                    ▼
            Agent.execute_task() → CrewAgentExecutor.invoke()
```

### 1.3 本阶段涉及的核心源码文件

| 文件 | 行数 | 核心职责 |
|------|------|----------|
| `crew.py` | ~2100+ 行 | Crew 主类，kickoff 入口、任务调度、Agent 组装 |
| `process.py` | ~11 行 | 执行策略枚举（Sequential / Hierarchical） |
| `crews/crew_output.py` | ~74 行 | Crew 输出封装类 |
| `crews/utils.py` | ~493 行 | 工具函数：Agent 初始化、任务准备、条件跳过、流式支持 |

---

## 2. 源码分层拆解

### 2.1 第一层：Process（执行策略枚举）

**文件：** `lib/crewai/src/crewai/process.py`

```python
class Process(str, Enum):
    """Crew 中任务执行的不同策略"""
    sequential = "sequential"      # 顺序执行：Task 按顺序逐个执行
    hierarchical = "hierarchical"  # 层级执行：Manager Agent 自动分配任务
    # TODO: consensual = 'consensual'  # 未来可能：共识模式
```

**大白话解释：**
- `sequential`：像流水线一样，Task 1 做完 → Task 2 开始 → Task 3 开始，每个 Task 由指定的 Agent 执行
- `hierarchical`：有一个 Manager Agent，它自己决定把哪个 Task 分配给哪个 Agent，类似项目经理

---

### 2.2 第二层：CrewOutput（输出封装）

**文件：** `lib/crewai/src/crewai/crews/crew_output.py`

```python
class CrewOutput(BaseModel):
    raw: str = ""                              # 原始输出文本
    pydantic: BaseModel | None = None           # Pydantic 结构化输出
    json_dict: dict[str, Any] | None = None     # JSON 字典输出
    tasks_output: list[TaskOutput] = []         # 每个 Task 的独立输出
    token_usage: UsageMetrics = UsageMetrics()  # Token 用量统计

    @property
    def usage_metrics(self) -> dict:  # 兼容 LiteAgentOutput 的接口
        return self.token_usage.model_dump()

    def __str__(self) -> str:
        """智能字符串转换：优先 Pydantic → JSON → raw"""
        if self.pydantic: return str(self.pydantic)
        if self.json_dict: return str(self.json_dict)
        return self.raw

    def __getitem__(self, key: str) -> Any:
        """支持字典式访问 crew_output['field_name']"""
        if self.pydantic and hasattr(self.pydantic, key):
            return getattr(self.pydantic, key)
        if self.json_dict and key in self.json_dict:
            return self.json_dict[key]
        raise KeyError(f"Key '{key}' not found in CrewOutput.")
```

**设计亮点：** `CrewOutput` 同时保留 `raw`、`pydantic`、`json_dict` 三种输出格式，`__str__` 和 `__getitem__` 实现了智能路由，外部代码无需关心底层格式。

---

### 2.3 第三层：Crew 主类（核心字段）

**文件：** `lib/crewai/src/crewai/crew.py`

```python
class Crew(FlowTrackable, BaseModel):
    # ===== 核心配置 =====
    name: str | None = "crew"                # Crew 名称
    tasks: list[Task] = []                   # 任务列表
    agents: list[BaseAgent] = []             # Agent 团队成员
    process: Process = Process.sequential    # 执行策略
    verbose: bool = False                    # 详细日志开关

    # ===== LLM 配置 =====
    manager_llm: str | BaseLLM | None = None     # 管理者 LLM
    manager_agent: BaseAgent | None = None        # 自定义管理者 Agent
    function_calling_llm: str | LLM | None = None # 函数调用 LLM（已废弃）
    planning_llm: str | BaseLLM | None = None     # 规划 LLM

    # ===== 功能开关 =====
    memory: bool | Memory | None = False     # 记忆系统开关
    cache: bool = False                      # 工具结果缓存
    planning: bool = False                   # 是否启用执行规划
    stream: bool = False                     # 是否流式输出
    share_crew: bool = False                 # 是否分享数据给 crewAI 团队

    # ===== 回调与钩子 =====
    step_callback: Callable | None = None    # 每个 Agent 步骤回调
    task_callback: Callable | None = None    # 每个 Task 完成回调
    before_kickoff_callbacks: list = []      # 启动前回调
    after_kickoff_callbacks: list = []       # 启动后回调

    # ===== 高级功能 =====
    knowledge_sources: list | None = None    # 知识源
    knowledge: Knowledge | None = None        # 知识检索实例
    security_config: SecurityConfig = ...    # 安全配置（指纹）
    checkpoint: CheckpointConfig | None = None  # 检查点配置
    tracing: bool | None = None              # 追踪开关
    max_rpm: int | None = None               # 每分钟最大请求数
    id: UUID4 = uuid.uuid4()                 # 唯一标识
```

---

### 2.4 第四层：kickoff() — 核心入口方法

```python
def kickoff(self, inputs=None, input_files=None, from_checkpoint=None):
    """
    启动 Crew 执行的入口方法，整个执行流程的起点。
    """
    # 1. 检查点恢复（断点续传）
    restored = apply_checkpoint(self, from_checkpoint)
    if restored is not None:
        return restored.kickoff(inputs=inputs, input_files=input_files)

    # 2. 流式输出模式
    if self.stream:
        enable_agent_streaming(self.agents)
        # 创建流式上下文，在后台线程执行...
        return CrewStreamingOutput(...)

    # 3. OpenTelemetry 追踪上下文
    baggage_ctx = baggage.set_baggage("crew_context", CrewContext(id=str(self.id)))

    # 4. 进入运行时作用域
    runtime_scope = crewai_event_bus._enter_runtime_scope()

    try:
        # 5. 准备阶段：回调、事件、文件、Agent 初始化、规划
        inputs = prepare_kickoff(self, inputs, input_files)

        # 6. 按策略执行
        if self.process == Process.sequential:
            result = self._run_sequential_process()
        elif self.process == Process.hierarchical:
            result = self._run_hierarchical_process()
        else:
            raise NotImplementedError(...)

        # 7. 后处理回调
        for after_callback in self.after_kickoff_callbacks:
            result = after_callback(result)

        result = self._post_kickoff(result)
        return result

    except Exception as e:
        crewai_event_bus.emit(self, CrewKickoffFailedEvent(...))
        raise
    finally:
        self._drain_memory_writes()  # 排空记忆写入
        clear_files(self.id)          # 清理文件存储
        crewai_event_bus._exit_runtime_scope(runtime_scope)
```

**关键设计：**
- `prepare_kickoff()` 在 `crews/utils.py` 中，负责 Agent 初始化、技能加载、规划生成等所有准备工作
- `finally` 块确保无论成功失败都清理资源（文件存储、记忆写入）

---

### 2.5 第五层：_execute_tasks() — 任务调度核心

```python
def _execute_tasks(self, tasks, start_index=0, was_replayed=False):
    """顺序执行任务列表，返回 CrewOutput。"""
    task_outputs: list[TaskOutput] = []
    futures: list[tuple[Task, Future, int]] = []  # 异步任务 Future 列表
    last_sync_output: TaskOutput | None = None

    for task_index, task in enumerate(tasks):
        # 1. 准备任务：获取 Agent、工具、检查是否跳过
        exec_data, task_outputs, last_sync_output = prepare_task_execution(
            self, task, task_index, start_index, task_outputs, last_sync_output
        )
        if exec_data.should_skip:
            continue  # 从检查点恢复时跳过已完成的任务

        # 2. 条件任务检查
        if isinstance(task, ConditionalTask):
            skipped = self._handle_conditional_task(task, task_outputs, futures, ...)
            if skipped:
                task_outputs.append(skipped)
                continue

        # 3. 异步任务 vs 同步任务
        if task.async_execution:
            # 异步：提交 Future，不等待结果
            future = task.execute_async(agent=exec_data.agent, context=..., tools=...)
            futures.append((task, future, task_index))
        else:
            # 同步：先等待所有 pending 异步任务完成
            if futures:
                task_outputs.extend(self._process_async_tasks(futures, was_replayed))
                futures.clear()

            # 执行同步任务
            context = self._get_context(task, task_outputs)
            task_output = task.execute_sync(
                agent=exec_data.agent, context=context, tools=exec_data.tools
            )
            task_outputs.append(task_output)
            self._process_task_result(task, task_output)
            self._store_execution_log(task, task_output, task_index, was_replayed)

    # 4. 处理剩余的异步任务
    if futures:
        task_outputs.extend(self._process_async_tasks(futures, was_replayed))

    # 5. 组装最终输出
    return self._create_crew_output(task_outputs)
```

**核心设计要点：**
- **异步任务延迟收集**：`async_execution=True` 的 Task 会提交 Future 但不立即等待，直到遇到下一个同步 Task 时才 `_process_async_tasks()` 收集结果
- **条件任务跳过**：`ConditionalTask.should_execute(previous_output)` 根据上一个 Task 的输出决定是否执行
- **上下文传递**：`_get_context(task, task_outputs)` 将前面 Task 的输出作为上下文传给后续 Task

---

### 2.6 第六层：Hierarchical 模式 — Manager Agent

```python
def _run_hierarchical_process(self):
    """创建 Manager Agent 来管理任务执行。"""
    self._create_manager_agent()
    return self._execute_tasks(self.tasks)

def _create_manager_agent(self):
    if self.manager_agent is not None:
        # 用户自定义了 Manager
        self.manager_agent.allow_delegation = True
        if manager.tools:
            raise Exception("Manager agent should not have tools")
    else:
        # 自动创建默认 Manager Agent
        manager = Agent(
            role=i18n.retrieve("hierarchical_manager_agent", "role"),
            goal=i18n.retrieve("hierarchical_manager_agent", "goal"),
            backstory=i18n.retrieve("hierarchical_manager_agent", "backstory"),
            tools=AgentTools(agents=self.agents).tools(),  # 只有委托工具
            allow_delegation=True,
            llm=self.manager_llm,
        )
        self.manager_agent = manager
    manager.crew = self
```

**关键设计：**
- Manager Agent 的工具只有 `AgentTools`（包含 `DelegateWorkTool` 和 `AskQuestionTool`），不能有其他工具
- Hierarchical 模式下，`_get_agent_to_use()` 始终返回 `self.manager_agent`，由 Manager 决定如何分配

---

### 2.7 第七层：_prepare_tools() — 工具注入链

```python
def _prepare_tools(self, agent, task, tools):
    """为 Agent 准备工具集，按需注入各种工具。"""
    # 1. 委托工具（层级模式）
    if agent.allow_delegation:
        if self.process == Process.hierarchical:
            tools = self._update_manager_tools(task, tools)
        else:
            tools = self._add_delegation_tools(task, tools)

    # 2. 代码执行工具
    if agent.allow_code_execution:
        tools = self._add_code_execution_tools(agent, tools)

    # 3. 多模态工具（如果 LLM 不支持多模态）
    if agent.multimodal and not agent.llm.supports_multimodal():
        tools = self._add_multimodal_tools(agent, tools)

    # 4. 平台工具（apps）
    if agent.apps:
        tools = self._add_platform_tools(task, tools)

    # 5. MCP 工具
    if agent.mcps:
        tools = self._add_mcp_tools(task, tools)

    # 6. 记忆工具
    if resolved_memory := (agent.memory or self._memory):
        tools = self._add_memory_tools(tools, resolved_memory)

    # 7. 文件工具（非 LLM 原生支持的文件类型）
    if files := get_all_files(self.id, task.id):
        tools = self._add_file_tools(tools, files_needing_tool)

    return tools
```

**设计亮点：** 工具按优先级分层注入，每层独立判断条件，避免了重复添加（`_merge_tools` 按名称去重）。

---

## 3. 完整调用时序图

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          Crew.kickoff(inputs)                              │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  1. 检查点恢复                                                             │
│     └── apply_checkpoint() → 有检查点? → 恢复到上次状态继续执行            │
│                                                                           │
│  2. 流式模式检查                                                           │
│     └── stream=True? → 创建 StreamingContext → 后台线程执行               │
│                                                                           │
│  3. prepare_kickoff() 准备阶段                                             │
│     ├── 执行 before_kickoff_callbacks                                      │
│     ├── 发射 CrewKickoffStartedEvent                                       │
│     ├── 存储输入文件到文件系统                                              │
│     ├── 插值输入变量到 Task 描述中 (_interpolate_inputs)                    │
│     ├── 设置 Task 回调 (_set_tasks_callbacks)                               │
│     ├── 初始化所有 Agent (setup_agents)                                     │
│     │   ├── agent.crew = self                                              │
│     │   ├── agent.set_knowledge()  ← 知识库注入                             │
│     │   ├── agent.set_skills()     ← 技能注入                               │
│     │   └── agent.create_agent_executor()  ← 创建执行器                    │
│     └── planning=True? → _handle_crew_planning()  ← 生成执行计划           │
│                                                                           │
│  4. 策略分发                                                               │
│     ├── Sequential → _run_sequential_process()                             │
│     │       └── _execute_tasks(self.tasks)                                 │
│     │                                                                      │
│     └── Hierarchical → _run_hierarchical_process()                         │
│             ├── _create_manager_agent()  ← 创建/配置 Manager Agent         │
│             └── _execute_tasks(self.tasks)                                 │
│                     │                                                      │
│                     ▼                                                      │
│  5. _execute_tasks() 详细流程                                              │
│     ┌──────────────────────────────────────────────────────┐             │
│     │  for task in tasks:                                   │             │
│     │    ├── prepare_task_execution()                       │             │
│     │    │   ├── 获取 Agent (_get_agent_to_use)             │             │
│     │    │   │   ├── Hierarchical → manager_agent           │             │
│     │    │   │   └── Sequential → task.agent                │             │
│     │    │   ├── 准备工具 (_prepare_tools)                  │             │
│     │    │   └── 发射 TaskStartedEvent                      │             │
│     │    │                                                   │             │
│     │    ├── ConditionalTask? → should_execute()?            │             │
│     │    │   └── NO → 跳过，记录 SkippedTaskOutput          │             │
│     │    │                                                   │             │
│     │    ├── task.async_execution?                           │             │
│     │    │   ├── YES → task.execute_async() → 存入 futures   │             │
│     │    │   └── NO  → task.execute_sync()                   │             │
│     │    │       ├── agent.execute_task()                    │             │
│     │    │       │   └── CrewAgentExecutor.invoke()          │             │
│     │    │       │       └── ReAct Loop / Native Tool Loop   │             │
│     │    │       └── 返回 TaskOutput                         │             │
│     │    │                                                   │             │
│     │    └── _store_execution_log()  ← 记录执行日志          │             │
│     │                                                        │             │
│     └── 收集所有异步 Future 结果                             │             │
│     └── _create_crew_output(task_outputs)  ← 组装最终输出     │             │
│     └──────────────────────────────────────────────────────┘             │
│                                                                           │
│  6. 后处理                                                                │
│     ├── after_kickoff_callbacks 逐个执行                                   │
│     ├── 计算 usage_metrics                                                 │
│     └── 返回 CrewOutput                                                    │
│                                                                           │
│  7. finally 清理                                                           │
│     ├── _drain_memory_writes()  ← 确保记忆写入完成                         │
│     ├── clear_files(self.id)    ← 清理临时文件                             │
│     └── _exit_runtime_scope()   ← 退出运行时作用域                         │
│                                                                           │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 4. 核心设计亮点

### 4.1 Sequential vs Hierarchical 双模式

| 维度 | Sequential | Hierarchical |
|------|-----------|-------------|
| 任务分配 | 每个 Task 指定 Agent | Manager Agent 自动分配 |
| 适用场景 | 流水线式、确定性任务 | 复杂、需要动态决策 |
| 额外成本 | 无额外 LLM 调用 | Manager 自身消耗 LLM 调用 |
| 工具系统 | Agent 使用自己的工具 | Manager 只有委托工具 |
| 代码复杂度 | 简单直接 | 需要 Manager 推理 |

### 4.2 异步任务混合执行

```python
# 关键逻辑：异步任务在遇到同步任务时才收集结果
if task.async_execution:
    futures.append((task, future, task_index))  # 不等待
else:
    if futures:
        task_outputs.extend(self._process_async_tasks(futures))  # 等待所有异步
        futures.clear()
```

**大白话：** 如果 Task A 和 Task B 都标记为异步，它们可以并行执行；直到遇到同步 Task C 时，Crew 才等待 A 和 B 都完成，然后拿它们的结果作为上下文传给 C。

### 4.3 检查点恢复（Checkpoint Resume）

```python
restored = apply_checkpoint(self, from_checkpoint)
if restored is not None:
    return restored.kickoff(inputs=inputs, input_files=input_files)
```

**设计亮点：** 检查点恢复是「透传」的——从检查点重建 Crew 实例后，再次调用 `kickoff()`，内部通过 `_get_execution_start_index()` 跳过已完成的 Task，从断点继续。

### 4.4 工具分层注入链

```
委托工具 → 代码执行工具 → 多模态工具 → 平台工具 → MCP工具 → 记忆工具 → 文件工具
```

每个工具层独立判断条件，`_merge_tools` 按名称去重，避免重复注入。

### 4.5 上下文传递机制

```python
context = self._get_context(task, task_outputs)
```

`_get_context()` 将前面所有 Task 的输出格式化为上下文字符串，传给当前 Task 的 Agent 执行器。这使得后续 Task 可以「看到」前面 Task 的执行结果。

---

## 5. 生产落地拓展改造

### 5.1 分布式执行（Celery/RQ）

```python
# 当前：单进程内执行所有 Task
# 改造：将每个 Task 提交到消息队列

from celery import Celery
app = Celery('crew_tasks')

class DistributedCrew(Crew):
    def _execute_tasks(self, tasks, ...):
        for task in tasks:
            if task.async_execution:
                # 提交到 Celery 队列
                result = app.send_task('execute_task', args=[task.id, context])
                futures.append(result)
            else:
                # 同步等待
                task_output = app.send_task('execute_task', ...).get()
```

### 5.2 持久化检查点（SQLite/PostgreSQL）

```python
# 当前：检查点支持 JSON/SQLite，但需要手动配置
# 改造：自动在每个 Task 完成后保存检查点

def _store_execution_log(self, task, task_output, task_index, was_replayed):
    super()._store_execution_log(task, task_output, task_index, was_replayed)
    if self.checkpoint:
        self._save_checkpoint_snapshot()  # 自动保存快照
```

### 5.3 任务重试与死信队列

```python
from tenacity import retry, stop_after_attempt

@retry(stop=stop_after_attempt(3))
def _execute_task_with_retry(self, task, agent, context, tools):
    try:
        return task.execute_sync(agent=agent, context=context, tools=tools)
    except Exception as e:
        if self._is_retryable(e):
            raise  # tenacity 会重试
        raise  # 不可重试的错误直接抛出
```

### 5.4 流式输出增强

```python
# 当前：stream=True 返回 CrewStreamingOutput
# 改造：支持 SSE (Server-Sent Events) 推送

from fastapi import FastAPI
from sse_starlette.sse import EventSourceResponse

@app.get("/crew/{crew_id}/stream")
async def stream_crew(crew_id: str):
    async def event_generator():
        crew = load_crew(crew_id)
        crew.stream = True
        output = crew.kickoff(inputs)
        async for chunk in output:
            yield {"data": chunk}
    return EventSourceResponse(event_generator())
```

---

## 6. 面试深挖问题清单

| # | 问题 | 考察点 |
|---|------|--------|
| 1 | Sequential 和 Hierarchical 两种执行模式的核心区别是什么？ | 设计模式、适用场景 |
| 2 | `kickoff()` 方法的完整执行流程是怎样的？ | 入口方法、调用链 |
| 3 | Manager Agent 在 Hierarchical 模式下如何创建？为什么不能有工具？ | 层级管理、Agent 设计约束 |
| 4 | 异步任务（async_execution）和同步任务如何混合执行？ | 并发控制、Future 模式 |
| 5 | `ConditionalTask` 的条件跳过逻辑在哪个环节触发？ | 条件判断、任务编排 |
| 6 | 检查点恢复（Checkpoint Resume）的实现原理是什么？ | 状态持久化、断点续传 |
| 7 | `_prepare_tools()` 工具注入链的顺序和优先级是怎样的？ | 工具系统、分层设计 |
| 8 | Crew 如何将前序 Task 的输出传递给后续 Task？ | 上下文传递、TaskOutput |
| 9 | `before_kickoff_callbacks` 和 `after_kickoff_callbacks` 的执行时机？ | 钩子生命周期 |
| 10 | CrewOutput 同时支持 raw、pydantic、json_dict 三种输出，设计意图是什么？ | 多格式输出、向后兼容 |

---

## 7. 简易可运行 Demo

```python
"""Demo: Sequential 和 Hierarchical 两种模式的 Crew 执行"""
from crewai import Agent, Task, Crew, Process

# 定义 Agent
researcher = Agent(
    role="研究员",
    goal="收集最新信息",
    backstory="你是一个经验丰富的研究员",
    verbose=True,
)

writer = Agent(
    role="写手",
    goal="将信息整理成报告",
    backstory="你是一个专业的报告撰写者",
    verbose=True,
)

# 定义 Task
task1 = Task(
    description="研究人工智能在医疗领域的应用",
    expected_output="一份研究摘要",
    agent=researcher,
)

task2 = Task(
    description="基于研究结果，写一份 500 字的报告",
    expected_output="完整的报告",
    agent=writer,
)

# === Sequential 模式 ===
print("=" * 50)
print("Sequential 模式")
print("=" * 50)
crew_seq = Crew(
    agents=[researcher, writer],
    tasks=[task1, task2],
    process=Process.sequential,  # 任务按顺序执行
    verbose=True,
)

result_seq = crew_seq.kickoff()
print(f"\n最终输出: {result_seq}")

# === Hierarchical 模式 ===
print("\n" + "=" * 50)
print("Hierarchical 模式")
print("=" * 50)
crew_hier = Crew(
    agents=[researcher, writer],
    tasks=[task1, task2],
    process=Process.hierarchical,  # Manager 自动分配
    manager_llm="gpt-4o",         # 需要指定 Manager 的 LLM
    verbose=True,
)

result_hier = crew_hier.kickoff()
print(f"\n最终输出: {result_hier}")
```

---

**下一阶段解析指令：**

```
# 当前解析目标
模块名称：LLM 抽象层
对应源码文件路径：
- lib/crewai/src/crewai/llm.py（LLM 门面类）
- lib/crewai/src/crewai/llms/base_llm.py（LLM 抽象基类）
- lib/crewai/src/crewai/llms/cache.py（LLM 缓存层）
- lib/crewai/src/crewai/llms/_finish_reason_utils.py（完成原因处理）

# 本次输出硬性要求，缺一不可
1. 模块定位（一句话 + 架构位置 + 核心文件清单）
2. 源码分层拆解（文件→类→方法→关键代码行）
3. 完整调用时序图（LLM.call() → 缓存检查 → 实际调用 → 回调 → 返回）
4. 核心设计亮点（多 Provider 适配、KV-Cache 优化、Token 计数、流式支持）
5. 生产落地拓展改造（多模型路由、降级策略、速率限制）
6. 面试深挖问题清单（10 题）
7. 简易可运行 Demo 代码
```