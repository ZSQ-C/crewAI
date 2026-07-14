# 阶段 G：events/ — 事件系统实现逻辑详解

## 1. 模块定位与架构图

### 1.1 模块定位

`events/` 模块是 CrewAI 框架的**核心事件基础设施**，负责管理整个系统中的事件发布、订阅、分发和生命周期管理。它采用**发布-订阅模式**，实现了以下关键能力：

- **全局单例事件总线**：通过 `CrewAIEventsBus` 单例统一管理所有事件的注册、分发和生命周期。
- **同步/异步双通道处理**：同时支持同步 handler（线程池执行）和异步 handler（独立事件循环执行）。
- **依赖注入式执行顺序**：通过 `Depends` 机制 + `HandlerGraph` 拓扑排序，实现 handler 间的依赖声明和有序执行。
- **事件作用域追踪**：通过 `event_context` 维护事件父子关系栈，实现事件链路的因果追踪。
- **运行时状态集成**：通过 `RuntimeState` 将事件与运行时实体（Crew、Agent、Task）关联，支持事件回放。

### 1.2 整体架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                         events/ 模块架构                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────┐    ┌──────────────────┐    ┌───────────────────┐  │
│  │  event_types │    │   base_events    │    │   event_context   │  │
│  │  事件类型汇聚 │    │  BaseEvent 基类   │    │  事件作用域栈管理   │  │
│  └──────┬───────┘    └────────┬─────────┘    └────────┬──────────┘  │
│         │                     │                       │              │
│         └─────────────────────┼───────────────────────┘              │
│                               │                                      │
│                               ▼                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                  CrewAIEventsBus (单例)                        │   │
│  │  ┌──────────────┐  ┌───────────────┐  ┌──────────────────┐   │   │
│  │  │ ThreadPool   │  │ Async Event   │  │  Handler         │   │   │
│  │  │ Executor     │  │ Loop (daemon) │  │  Registry        │   │   │
│  │  │ (sync)       │  │ (async)       │  │  (sync + async)  │   │   │
│  │  └──────────────┘  └───────────────┘  └──────────────────┘   │   │
│  └──────────────┬───────────────────────────────────────────────┘   │
│                 │                                                     │
│    ┌────────────┼────────────┐                                       │
│    ▼            ▼            ▼                                       │
│  ┌────────┐ ┌────────┐ ┌──────────┐                                 │
│  │Depends │ │Handler │ │ Event    │                                 │
│  │依赖声明 │ │ Graph  │ │ Listener │                                 │
│  └────────┘ │拓扑排序 │ │ 监听器   │                                 │
│             └────────┘ └──────────┘                                 │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.3 核心文件清单

| 文件 | 职责 |
|------|------|
| `event_bus.py` | 事件总线单例，核心调度引擎 |
| `event_types.py` | 所有事件类型的联合类型汇总 |
| `base_events.py` | `BaseEvent` 基类 + 发射序号管理 |
| `handler_graph.py` | 依赖图拓扑排序，生成执行计划 |
| `event_listener.py` | 全局事件监听器，注册所有内置 handler |
| `depends.py` | `Depends` 依赖声明类 |
| `event_context.py` | 事件作用域栈管理（父子关系追踪） |
| `base_event_listener.py` | 监听器抽象基类 |

---

## 2. 核心实现逻辑详解

### 2.1 EventBus — 事件总线单例

#### 2.1.1 单例模式实现

`CrewAIEventsBus` 采用**双重检查锁定**模式实现线程安全的单例（`event_bus.py` 第 118-143 行）：

```python
# 第 118-143 行
_instance: Self | None = None          # 类级别实例引用
_instance_lock: threading.RLock = threading.RLock()  # 类级别可重入锁

def __new__(cls) -> Self:
    if cls._instance is None:           # 第一重检查（无锁，快速路径）
        with cls._instance_lock:        # 加锁
            if cls._instance is None:   # 第二重检查（锁内，安全）
                cls._instance = super().__new__(cls)
                cls._instance._initialize()
    return cls._instance
```

**设计要点**：
- 使用 `RLock`（可重入锁）而非普通 `Lock`，因为 `_ensure_executor_initialized()` 方法（第 166 行）也使用同一把锁，在类初始化时可能发生嵌套加锁。
- 第一重检查避免每次调用都加锁的性能开销；第二重检查确保只有一个实例被创建。
- 模块底部（第 952 行）创建全局单例：`crewai_event_bus: Final[CrewAIEventsBus] = CrewAIEventsBus()`，并注册 `atexit` 钩子（第 954 行）确保程序退出时优雅关闭。

#### 2.1.2 内部状态初始化

`_initialize()` 方法（第 145-164 行）初始化所有内部数据结构：

| 属性 | 类型 | 用途 |
|------|------|------|
| `_sync_handlers` | `dict[type[BaseEvent], SyncHandlerSet]` | 同步 handler 注册表 |
| `_async_handlers` | `dict[type[BaseEvent], AsyncHandlerSet]` | 异步 handler 注册表 |
| `_handler_dependencies` | `dict[type[BaseEvent], dict[Handler, list[Depends]]]` | 依赖关系注册表 |
| `_execution_plan_cache` | `dict[type[BaseEvent], ExecutionPlan]` | 执行计划缓存 |
| `_rwlock` | `RWLock` | 读写锁，保护 handler 注册表 |
| `_pending_futures` | `set[Future]` | 跟踪待完成的 Future |
| `_shutting_down` | `bool` | 关闭标志 |

**关键设计**：线程池和事件循环采用**延迟初始化**（`_ensure_executor_initialized`，第 166-191 行），仅在首次 `emit()` 调用时才创建，避免不需要事件时产生不必要的开销。

#### 2.1.3 双通道处理架构

事件总线维护两个执行通道：

**同步通道**（第 179-181 行）：使用 `ThreadPoolExecutor(max_workers=10)`，每个同步 handler 在线程池中执行，通过 `contextvars.copy_context()` 保留上下文。

**异步通道**（第 184-190 行）：创建独立的 `asyncio` 事件循环，运行在守护线程 `CrewAIEventsLoop` 中。异步 handler 通过 `asyncio.run_coroutine_threadsafe()` 跨线程调度到此循环。

```python
# 第 179-190 行
self._sync_executor = ThreadPoolExecutor(
    max_workers=10,
    thread_name_prefix="CrewAISyncHandler",
)
self._loop = asyncio.new_event_loop()
self._loop_thread = threading.Thread(
    target=self._run_loop,
    name="CrewAIEventsLoop",
    daemon=True,
)
```

#### 2.1.4 emit — 核心发射方法

`emit()` 方法（第 572-647 行）是事件系统的核心入口，完整流程如下：

```
emit(source, event)
  │
  ├─ 1. _prepare_event(source, event)           # 准备事件元数据
  │     ├─ _register_source(source)              # 注册源实体到 RuntimeState
  │     ├─ 设置 event.previous_event_id          # 前驱事件 ID
  │     ├─ 设置 event.triggered_by_event_id      # 触发事件 ID
  │     ├─ 设置 event.emission_sequence          # 全局发射序号
  │     ├─ 设置 event.parent_event_id            # 父事件 ID（作用域栈）
  │     ├─ publish_stream_event(source, event)   # 发布流事件
  │     └─ _record_event(event)                  # 记录到 RuntimeState
  │
  ├─ 2. 检查 handler 注册表                      # 获取 sync/async handler
  │
  ├─ 3. _ensure_executor_initialized()           # 延迟初始化（首次）
  │
  └─ 4. 根据 handler 类型分发执行
        ├─ 有依赖 → _emit_with_dependencies()    # 依赖感知分发
        ├─ 仅 sync + LLMStreamChunk → 同步调用   # 流事件保持顺序
        ├─ 仅 sync → ThreadPoolExecutor          # 线程池分发
        └─ 有 async → asyncio.run_coroutine_threadsafe()  # 事件循环分发
```

**关键设计细节**：

1. **流事件特殊处理**（第 629-630 行）：`LLMStreamChunkEvent` 类型的同步 handler 直接在调用线程执行，不使用线程池，确保流式数据的有序性。

2. **上下文传递**（第 633 行）：通过 `contextvars.copy_context()` 将当前 `ContextVar` 状态（包括 `_replaying`、`_runtime_state_var` 等）传递给线程池中的 handler。

3. **Future 跟踪**（第 193-210 行）：所有提交的 Future 通过 `_track_future()` 添加到 `_pending_futures`，并在完成时自动清理。`flush()` 方法（第 734-769 行）利用此机制等待所有 pending handler 完成。

#### 2.1.5 依赖感知分发

`_emit_with_dependencies()` 方法（第 458-522 行）实现了基于依赖关系的分层执行：

```python
# 第 476-522 行（核心逻辑）
# 1. 从缓存获取执行计划（双检查锁模式）
with self._rwlock.r_locked():
    cached_plan = self._execution_plan_cache.get(event_type)

if cached_plan is None:
    with self._rwlock.w_locked():  # 写锁内构建执行计划
        # 合并 sync + async handler，调用 build_execution_plan
        cached_plan = build_execution_plan(all_handlers, dependencies)
        self._execution_plan_cache[event_type] = cached_plan

# 2. 按层级顺序执行
for level in cached_plan:
    # 每层内：sync 线程池执行，async 并发执行
    # 当前层完成才进入下一层
```

**执行计划缓存**：每次修改 handler 注册表时（`_register_handler` 第 243 行、`off` 第 399 行），对应事件类型的缓存被清除。下次 emit 时重建。

#### 2.1.6 on/off — 注册与注销

**`on()` 装饰器**（第 245-280 行）：支持可选的 `depends_on` 参数：

```python
@crewai_event_bus.on(CrewKickoffStartedEvent)  # 无依赖
def handler1(source, event): ...

@crewai_event_bus.on(CrewKickoffStartedEvent, depends_on=Depends(handler1))  # 有依赖
def handler2(source, event): ...
```

**`off()` 方法**（第 368-399 行）：从同步/异步 handler 集合中移除，同时清理依赖关系和执行计划缓存。空集合被自动删除。

**`_register_handler()` 方法**（第 217-243 行）：handler 注册到对应类型的 `frozenset` 中，使用 `frozenset` 的不可变性保证线程安全（写操作创建新 frozenset，读操作拿到一致快照）。

#### 2.1.7 事件回放机制

`replay()` 方法（第 673-732 行）用于重放已记录的事件（如从 checkpoint 恢复）：

- 与 `emit()` 的关键区别：**不调用 `_prepare_event()`**，保持事件的原始 `event_id`、`parent_event_id`、`emission_sequence` 等字段不变。
- 设置 `_replaying` ContextVar 为 `True`（第 704 行），handler 可通过 `is_replaying()` 函数（第 73-81 行）检查此标志，决定是否跳过副作用操作（如 checkpoint 写入、外部 API 调用）。

#### 2.1.8 作用域处理器

`scoped_handlers()` 上下文管理器（第 832-895 行）用于测试场景：

1. 进入时保存当前所有 handler 快照，然后移除所有 handler。
2. 退出时清除上下文中新增的 handler，恢复原始 handler。

#### 2.1.9 优雅关闭

`shutdown()` 方法（第 897-949 行）：
1. 调用 `flush()` 等待所有 pending handler 完成。
2. 设置 `_shutting_down = True` 阻止新事件处理。
3. 等待事件循环中所有任务完成（或取消）。
4. 停止事件循环，关闭线程池，清空所有 handler 注册表。

---

### 2.2 事件类型体系

#### 2.2.1 BaseEvent 基类

`BaseEvent`（`base_events.py` 第 66-116 行）继承自 Pydantic 的 `BaseModel`，是所有事件的数据模型基类：

```python
# 第 66-87 行（核心字段）
class BaseEvent(BaseModel):
    timestamp: datetime          # 事件时间戳（UTC）
    type: str                    # 事件类型字符串标识
    source_fingerprint: str | None    # 源实体 UUID 指纹
    source_type: str | None           # 源类型：agent/task/crew/memory...
    fingerprint_metadata: dict | None # 指纹元数据

    task_id: str | None          # 关联 Task ID
    task_name: str | None        # 关联 Task 名称
    agent_id: str | None         # 关联 Agent ID
    agent_role: str | None       # 关联 Agent 角色

    event_id: str                # 事件唯一 ID（UUID4）
    parent_event_id: str | None  # 父事件 ID（作用域追踪）
    previous_event_id: str | None      # 前一个事件 ID（线性链）
    triggered_by_event_id: str | None  # 触发事件 ID（因果链）
    started_event_id: str | None       # 对应开始事件 ID
    emission_sequence: int | None      # 全局发射序号
```

**设计要点**：

- `type` 字段是字符串类型标识（如 `"crew_kickoff_started"`），用于事件作用域匹配（`event_context.py` 中的 `SCOPE_STARTING_EVENTS` / `SCOPE_ENDING_EVENTS`）。
- `event_id` 使用 `uuid.uuid4()` 自动生成（第 82 行），确保全局唯一。
- `emission_sequence` 通过 `ContextVar` 管理的全局计数器赋值（第 33-41 行），同一个执行上下文中的事件序号递增。

#### 2.2.2 发射序号管理

`base_events.py` 第 13-63 行实现了基于 `ContextVar` 的发射序号管理：

```python
# 第 13-14 行
_emission_counter: contextvars.ContextVar[Iterator[int]] = contextvars.ContextVar("_emission_counter")

# 第 33-41 行
def get_next_emission_sequence() -> int:
    seq = next(_get_or_create_counter())  # itertools.count(start=1)
    _last_emitted.set(seq)
    return seq
```

**设计要点**：使用 `itertools.count` 而非简单整数，因为 `ContextVar` 在拷贝时能正确保持迭代器状态。`reset_emission_counter()`（第 49-56 行）和 `set_emission_counter(start)`（第 59-63 行）支持从 checkpoint 恢复时的序号重建。

#### 2.2.3 事件类型分类

`event_types.py`（第 1-222 行）定义了 `EventTypes` 联合类型，汇总了所有子系统的事件类型，按功能域分为 12 大类：

| 分类 | 事件数量 | 来源模块 | 代表事件 |
|------|---------|---------|---------|
| **Crew 事件** | 9 | `crew_events` | `CrewKickoffStartedEvent`, `CrewKickoffCompletedEvent` |
| **Agent 事件** | 3 | `agent_events` | `AgentExecutionStartedEvent`, `AgentExecutionCompletedEvent` |
| **Task 事件** | 3 | `task_events` | `TaskStartedEvent`, `TaskCompletedEvent` |
| **Flow 事件** | 10 | `flow_events` | `FlowStartedEvent`, `MethodExecutionStartedEvent` |
| **LLM 事件** | 4 | `llm_events` | `LLMCallStartedEvent`, `LLMStreamChunkEvent` |
| **LLM Guardrail 事件** | 2 | `llm_guardrail_events` | `LLMGuardrailStartedEvent` |
| **Tool 事件** | 3 | `tool_usage_events` | `ToolUsageStartedEvent`, `ToolUsageErrorEvent` |
| **Memory 事件** | 9 | `memory_events` | `MemorySaveStartedEvent`, `MemoryQueryStartedEvent` |
| **Knowledge 事件** | 6 | `knowledge_events` | `KnowledgeQueryStartedEvent`, `KnowledgeRetrievalStartedEvent` |
| **A2A 事件** | 22 | `a2a_events` | `A2ADelegationStartedEvent`, `A2AConversationStartedEvent` |
| **MCP 事件** | 7 | `mcp_events` | `MCPConnectionStartedEvent`, `MCPToolExecutionStartedEvent` |
| **Checkpoint 事件** | 9 | `checkpoint_events` | `CheckpointStartedEvent`, `CheckpointRestoreStartedEvent` |
| **Observation 事件** | 2 | `observation_events` | `PlanStepStartedEvent`, `PlanStepCompletedEvent` |
| **Reasoning 事件** | 3 | `reasoning_events` | `AgentReasoningStartedEvent` |

**命名规范**：所有事件类型遵循 `{Domain}{Action}{Status}Event` 模式，如 `ToolUsageStartedEvent`、`LLMCallFailedEvent`。

---

### 2.3 HandlerGraph — 处理器图

#### 2.3.1 核心算法：拓扑排序

`HandlerGraph`（`handler_graph.py` 第 34-102 行）使用 **Kahn 算法**（BFS 拓扑排序）将 handler 依赖关系分解为并行执行层级：

```python
# 第 60-92 行（核心算法）
def _resolve(self) -> None:
    # 1. 构建邻接表和入度
    dependents: dict[Handler, set[Handler]] = defaultdict(set)
    in_degree: dict[Handler, int] = {}

    for handler, deps in self.handlers.items():
        in_degree[handler] = len(deps)
        for dep in deps:
            dependents[dep.handler].add(handler)  # dep.handler → handler

    # 2. 入度为 0 的 handler 入队（Level 0）
    queue = deque([h for h, deg in in_degree.items() if deg == 0])

    # 3. BFS 逐层处理
    while queue:
        current_level = set()
        for _ in range(len(queue)):
            handler = queue.popleft()
            current_level.add(handler)
            for dependent in dependents[handler]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)
        self.levels.append(current_level)

    # 4. 检测循环依赖
    remaining = [h for h, deg in in_degree.items() if deg > 0]
    if remaining:
        raise CircularDependencyError(remaining)
```

**算法示例**：假设 handler A、B、C 注册了 `LLMCallStartedEvent`，依赖关系为 `C → Depends(A)`, `C → Depends(B)`：

```
Level 0: {A, B}   ← 无依赖，可并行执行
Level 1: {C}      ← 依赖 A 和 B 都完成
```

#### 2.3.2 执行计划构建

`build_execution_plan()` 函数（第 105-127 行）是外部调用的入口：

```python
def build_execution_plan(
    handlers: Sequence[Handler],
    dependencies: dict[Handler, list[Depends[Any]]],
) -> ExecutionPlan:
    handler_dict = {h: dependencies.get(h, []) for h in handlers}
    graph = HandlerGraph(handler_dict)
    return graph.get_execution_plan()
```

**缓存策略**：`CrewAIEventsBus._execution_plan_cache`（`event_bus.py` 第 124 行）缓存每个事件类型的执行计划，避免每次 emit 都重新计算。缓存失效条件：handler 注册/注销时（`_register_handler` 第 243 行、`off` 第 399 行）。

#### 2.3.3 循环依赖检测

`CircularDependencyError`（第 15-31 行）在拓扑排序结束后检测仍在 `in_degree` 中且入度 > 0 的 handler，这些 handler 形成了循环依赖。错误信息包含涉及的 handler 名称（最多 5 个）。

`validate_dependencies()` 方法（`event_bus.py` 第 810-829 行）在 `BaseEventListener.__init__()` 中调用（`base_event_listener.py` 第 17 行），提前验证所有依赖，在 emit 前发现循环依赖问题。

---

### 2.4 EventListener — 事件监听器

#### 2.4.1 监听器架构

`EventListener`（`event_listener.py` 第 132-853 行）继承自 `BaseEventListener`（`base_event_listener.py`），是 CrewAI 的**全局内置监听器**。

```python
# base_event_listener.py 第 8-25 行
class BaseEventListener(ABC):
    def __init__(self) -> None:
        super().__init__()
        self.setup_listeners(crewai_event_bus)   # 注册所有 handler
        crewai_event_bus.validate_dependencies()  # 验证依赖

    @abstractmethod
    def setup_listeners(self, crewai_event_bus: CrewAIEventsBus) -> None: ...
```

`EventListener` 本身也是单例（`event_listener.py` 第 133-147 行），在模块底部创建全局实例（第 854 行）：

```python
event_listener = EventListener()
```

#### 2.4.2 监听器职责

`EventListener.setup_listeners()` 注册了约 **60+ 个事件 handler**，覆盖三大职责：

| 职责 | 涉及组件 | 说明 |
|------|---------|------|
| **控制台输出格式化** | `ConsoleFormatter` | 通过 `self.formatter.handle_*()` 方法输出彩色日志 |
| **遥测数据上报** | `Telemetry` | 通过 `self._telemetry.*_span()` 方法上报匿名使用统计 |
| **执行跨度管理** | `execution_spans` | 跟踪 Task 执行跨度，关联开始/结束事件 |

#### 2.4.3 典型 handler 实现模式

以 Crew 生命周期事件为例（`event_listener.py` 第 178-203 行）：

```python
@crewai_event_bus.on(CrewKickoffStartedEvent)
def on_crew_started(source: Any, event: CrewKickoffStartedEvent) -> None:
    self.formatter.handle_crew_started(event.crew_name or "Crew", source.id)
    source._execution_span = self._telemetry.crew_execution_span(source, event.inputs)

@crewai_event_bus.on(CrewKickoffCompletedEvent)
def on_crew_completed(source: Any, event: CrewKickoffCompletedEvent) -> None:
    final_string_output = event.output.raw
    self._telemetry.end_crew(source, final_string_output)
    self.formatter.handle_crew_status(event.crew_name, source.id, "completed", final_string_output)

@crewai_event_bus.on(CrewKickoffFailedEvent)
def on_crew_failed(source: Any, event: CrewKickoffFailedEvent) -> None:
    self.formatter.handle_crew_status(event.crew_name, source.id, "failed")
```

**模式特点**：
- `source` 参数是发出事件的对象（如 `Crew` 实例），handler 可访问其属性和方法。
- 开始事件创建 span / 初始化状态，结束事件清理 span / 输出结果。
- 同一事件类型可注册多个 handler（如 `CrewKickoffStartedEvent` 在第 178 行和第 831 行各有一个 handler）。

#### 2.4.4 LLM 流式事件处理

LLM 流式 chunk 处理（第 442-468 行）展示了特殊的事件处理模式：

```python
@crewai_event_bus.on(LLMCallStartedEvent)
def on_llm_call_started(_: Any, event: LLMCallStartedEvent) -> None:
    self.text_stream = StringIO()    # 重置文本缓冲区
    self.next_chunk = 0              # 重置读取位置

@crewai_event_bus.on(LLMStreamChunkEvent)
def on_llm_stream_chunk(_: Any, event: LLMStreamChunkEvent) -> None:
    self.text_stream.write(event.chunk)
    self.text_stream.seek(self.next_chunk)
    self.text_stream.read()          # 仅读取新增部分
    self.next_chunk = self.text_stream.tell()
    accumulated_text = self.text_stream.getvalue()
    self.formatter.handle_llm_stream_chunk(accumulated_text, event.call_type)
```

`StringIO` + `next_chunk` 指针组合实现了增量流式输出：每次只格式化新增的 chunk，避免重复渲染已输出的内容。

#### 2.4.5 知识检索去重

`KnowledgeRetrievalStartedEvent` handler（第 511-534 行）实现了去重逻辑：

```python
@crewai_event_bus.on(KnowledgeRetrievalStartedEvent)
def on_knowledge_retrieval_started(_: Any, event: KnowledgeRetrievalStartedEvent) -> None:
    if self.knowledge_retrieval_in_progress:  # 已在进行中，跳过
        return
    self.knowledge_retrieval_in_progress = True
    self.formatter.handle_knowledge_retrieval_started()
```

当多个 Agent 同时触发知识检索时，`knowledge_retrieval_in_progress` 标志位（第 140 行）防止重复输出。

---

## 3. 完整调用时序图

以下时序图展示了一个 Crew Kickoff 的完整事件流：

```
用户代码              CrewAIEventsBus        EventListener        ConsoleFormatter
  │                       │                      │                     │
  │  crew.kickoff()       │                      │                     │
  │──────────────────────►│                      │                     │
  │                       │                      │                     │
  │                       │  _prepare_event()    │                     │
  │                       │  ┌─────────────────┐ │                     │
  │                       │  │ set seq/scope    │ │                     │
  │                       │  │ record event     │ │                     │
  │                       │  └─────────────────┘ │                     │
  │                       │                      │                     │
  │                       │  emit(crew,          │                     │
  │                       │   CrewKickoffStarted)│                     │
  │                       │─────────────────────►│                     │
  │                       │                      │ on_crew_started()   │
  │                       │                      │────────────────────►│
  │                       │                      │                     │ handle_crew_started
  │                       │                      │                     │───────────────────►
  │                       │                      │                     │◄───────────────────
  │                       │                      │◄────────────────────│
  │                       │◄─────────────────────│                     │
  │                       │                      │                     │
  │  ... agent execute    │                      │                     │
  │                       │                      │                     │
  │                       │  emit(agent,         │                     │
  │                       │   AgentExecutionStart)                     │
  │                       │─────────────────────►│                     │
  │                       │                      │ ...                 │
  │                       │                      │                     │
  │                       │  emit(task,          │                     │
  │                       │   TaskStarted)       │                     │
  │                       │─────────────────────►│                     │
  │                       │                      │ on_task_started()   │
  │                       │                      │────────────────────►│
  │                       │                      │                     │ handle_task_started
  │                       │                      │                     │───────────────────►
  │                       │                      │                     │
  │  ... LLM call ...     │                      │                     │
  │                       │                      │                     │
  │                       │  emit(llm,           │                     │
  │                       │   LLMCallStarted)    │                     │
  │                       │─────────────────────►│                     │
  │                       │                      │ on_llm_call_started │
  │                       │                      │ (reset StringIO)    │
  │                       │                      │                     │
  │                       │  emit(llm,           │                     │
  │                       │   LLMStreamChunk)    │                     │
  │                       │─────────────────────►│                     │
  │                       │                      │ on_llm_stream_chunk │
  │                       │                      │────────────────────►│
  │                       │                      │   (同步执行，不排队)  │ handle_llm_stream_chunk
  │                       │                      │                     │───────────────────►
  │                       │                      │                     │
  │  ... task done ...    │                      │                     │
  │                       │                      │                     │
  │                       │  emit(task,          │                     │
  │                       │   TaskCompleted)     │                     │
  │                       │─────────────────────►│                     │
  │                       │                      │ on_task_completed   │
  │                       │                      │────────────────────►│
  │                       │                      │                     │ handle_task_status
  │                       │                      │                     │───────────────────►
  │                       │                      │                     │
  │                       │  emit(crew,          │                     │
  │                       │   CrewKickoffCompleted)                    │
  │                       │─────────────────────►│                     │
  │                       │                      │ on_crew_completed   │
  │                       │                      │────────────────────►│
  │                       │                      │                     │ handle_crew_status
  │                       │                      │                     │───────────────────►
  │                       │                      │                     │
  │                       │  flush()             │                     │
  │                       │  ┌─────────────────┐ │                     │
  │                       │  │ wait all futures │ │                     │
  │                       │  └─────────────────┘ │                     │
  │                       │                      │                     │
  │◄──────────────────────│                      │                     │
```

---

## 4. 完整可运行示例

### 4.1 示例 1：基础事件发布与订阅

```python
"""示例 1：演示 EventBus 的基本 on/emit/off 功能"""
import time
from dataclasses import dataclass
from typing import Any

from crewai.events.base_events import BaseEvent
from crewai.events.event_bus import crewai_event_bus


# 自定义事件类型
class PizzaOrderedEvent(BaseEvent):
    type: str = "pizza_ordered"
    pizza_type: str = ""
    size: str = ""


class PizzaReadyEvent(BaseEvent):
    type: str = "pizza_ready"
    pizza_type: str = ""


# 模拟一个披萨店
@dataclass
class PizzaShop:
    name: str = "Tony's Pizza"

    def order(self, pizza_type: str, size: str = "medium") -> None:
        print(f"\n[PizzaShop] 收到订单: {size} {pizza_type} 披萨")
        event = PizzaOrderedEvent(pizza_type=pizza_type, size=size)
        crewai_event_bus.emit(self, event)

    def bake(self, pizza_type: str) -> None:
        time.sleep(0.5)  # 模拟烘焙时间
        print(f"[PizzaShop] {pizza_type} 披萨烤好了!")
        event = PizzaReadyEvent(pizza_type=pizza_type)
        crewai_event_bus.emit(self, event)


# 注册事件处理器
@crewai_event_bus.on(PizzaOrderedEvent)
def chef_prepare(source: Any, event: PizzaOrderedEvent) -> None:
    print(f"[Chef] 开始准备 {event.size} {event.pizza_type} 披萨...")
    # 获取 source 信息
    if hasattr(source, "name"):
        print(f"[Chef] 订单来自: {source.name}")


@crewai_event_bus.on(PizzaOrderedEvent)
def cashier_record(source: Any, event: PizzaOrderedEvent) -> None:
    print(f"[Cashier] 记录销售: {event.size} {event.pizza_type} 披萨 - {event.timestamp}")


@crewai_event_bus.on(PizzaReadyEvent)
def waiter_deliver(source: Any, event: PizzaReadyEvent) -> None:
    print(f"[Waiter] 上菜: {event.pizza_type} 披萨!")


# 运行
shop = PizzaShop()
shop.order("pepperoni", "large")
shop.bake("pepperoni")

# 等待异步 handler 完成
crewai_event_bus.flush()

# 输出:
# [PizzaShop] 收到订单: large pepperoni 披萨
# [Chef] 开始准备 large pepperoni 披萨...
# [Chef] 订单来自: Tony's Pizza
# [Cashier] 记录销售: large pepperoni 披萨 - ...
# [PizzaShop] pepperoni 披萨烤好了!
# [Waiter] 上菜: pepperoni 披萨!
```

### 4.2 示例 2：Handler 依赖关系

```python
"""示例 2：演示 Depends 依赖注入和有序执行"""
import time
from typing import Any

from crewai.events.base_events import BaseEvent
from crewai.events.depends import Depends
from crewai.events.event_bus import crewai_event_bus


class DataPipelineEvent(BaseEvent):
    type: str = "data_pipeline"
    raw_data: str = ""


result_log: list[str] = []


@crewai_event_bus.on(DataPipelineEvent)
def step1_extract_data(source: Any, event: DataPipelineEvent) -> None:
    time.sleep(0.1)
    result_log.append("step1: 数据提取完成")
    print("[Step1] 提取原始数据")


@crewai_event_bus.on(DataPipelineEvent)
def step2_validate_data(source: Any, event: DataPipelineEvent) -> None:
    time.sleep(0.1)
    result_log.append("step2: 数据验证完成")
    print("[Step2] 验证数据格式")


# step3 依赖 step1 和 step2，必须等它们完成后才执行
@crewai_event_bus.on(
    DataPipelineEvent,
    depends_on=[Depends(step1_extract_data), Depends(step2_validate_data)],
)
def step3_transform_data(source: Any, event: DataPipelineEvent) -> None:
    result_log.append("step3: 数据转换完成")
    print("[Step3] 转换数据格式")
    # 验证 step1 和 step2 确实先执行了
    assert "step1" in result_log[-3] or "step1" in result_log[-2], "step1 未先执行!"
    assert "step2" in result_log[-3] or "step2" in result_log[-2], "step2 未先执行!"


# step4 依赖 step3
@crewai_event_bus.on(DataPipelineEvent, depends_on=Depends(step3_transform_data))
def step4_load_data(source: Any, event: DataPipelineEvent) -> None:
    result_log.append("step4: 数据加载完成")
    print("[Step4] 加载数据到目标存储")
    assert "step3" in result_log[-2], "step3 未先执行!"


# 触发事件
crewai_event_bus.emit("pipeline", DataPipelineEvent(raw_data="hello"))
crewai_event_bus.flush(timeout=10.0)

print(f"\n执行顺序: {result_log}")
# 输出:
# [Step1] 提取原始数据
# [Step2] 验证数据格式
# [Step3] 转换数据格式
# [Step4] 加载数据到目标存储
# 执行顺序: ['step1: ...', 'step2: ...', 'step3: ...', 'step4: ...']
```

### 4.3 示例 3：异步 Handler

```python
"""示例 3：演示异步事件处理器"""
import asyncio
from typing import Any

from crewai.events.base_events import BaseEvent
from crewai.events.event_bus import crewai_event_bus


class AsyncTaskEvent(BaseEvent):
    type: str = "async_task"
    task_name: str = ""


# 同步 handler
@crewai_event_bus.on(AsyncTaskEvent)
def sync_logger(source: Any, event: AsyncTaskEvent) -> None:
    print(f"[Sync] 任务 '{event.task_name}' 已触发")


# 异步 handler - 模拟 I/O 操作
@crewai_event_bus.on(AsyncTaskEvent)
async def async_notifier(source: Any, event: AsyncTaskEvent) -> None:
    print(f"[Async] 开始发送通知: {event.task_name}")
    await asyncio.sleep(0.5)  # 模拟异步 HTTP 请求
    print(f"[Async] 通知发送完成: {event.task_name}")


# 另一个异步 handler
@crewai_event_bus.on(AsyncTaskEvent)
async def async_logger(source: Any, event: AsyncTaskEvent) -> None:
    print(f"[Async Logger] 记录任务: {event.task_name}")
    await asyncio.sleep(0.2)
    print(f"[Async Logger] 记录完成: {event.task_name}")


# 触发事件
print("=== 发射事件 ===")
future = crewai_event_bus.emit("source", AsyncTaskEvent(task_name="备份数据库"))
crewai_event_bus.flush(timeout=10.0)

# 输出（sync 先完成，async 两个并发执行）:
# === 发射事件 ===
# [Sync] 任务 '备份数据库' 已触发
# [Async] 开始发送通知: 备份数据库
# [Async Logger] 记录任务: 备份数据库
# [Async Logger] 记录完成: 备份数据库
# [Async] 通知发送完成: 备份数据库
```

### 4.4 示例 4：scoped_handlers 测试上下文

```python
"""示例 4：演示 scoped_handlers 用于测试隔离"""
from typing import Any

from crewai.events.base_events import BaseEvent
from crewai.events.event_bus import crewai_event_bus


class TestEvent(BaseEvent):
    type: str = "test_event"


# 全局 handler（始终存在）
@crewai_event_bus.on(TestEvent)
def global_handler(source: Any, event: TestEvent) -> None:
    print("[Global] 全局 handler 被调用")


# 在作用域内注册临时 handler
print("=== 进入作用域 ===")
with crewai_event_bus.scoped_handlers():

    @crewai_event_bus.on(TestEvent)
    def temp_handler(source: Any, event: TestEvent) -> None:
        print("[Temp] 临时 handler 被调用")

    # 发射事件 - 只有临时 handler 会响应
    crewai_event_bus.emit("test", TestEvent())
    crewai_event_bus.flush()
    # 输出:
    # [Temp] 临时 handler 被调用

print("\n=== 离开作用域 ===")
# 作用域外 - 全局 handler 恢复，临时 handler 已注销
crewai_event_bus.emit("test", TestEvent())
crewai_event_bus.flush()
# 输出:
# [Global] 全局 handler 被调用
```

### 4.5 示例 5：事件回放与 RuntimeState

```python
"""示例 5：演示事件回放和 is_replaying 标志"""
from dataclasses import dataclass
from typing import Any

from crewai.events.base_events import BaseEvent
from crewai.events.event_bus import crewai_event_bus, is_replaying


class WorkflowStepEvent(BaseEvent):
    type: str = "workflow_step"
    step_name: str = ""


side_effect_count: int = 0


# 实际业务 handler - 检查 is_replaying 避免重复副作用
@crewai_event_bus.on(WorkflowStepEvent)
def business_handler(source: Any, event: WorkflowStepEvent) -> None:
    global side_effect_count
    if is_replaying():
        print(f"[Business] 跳过副作用 (回放中): {event.step_name}")
        return
    side_effect_count += 1
    print(f"[Business] 执行副作用: {event.step_name} (count={side_effect_count})")


# 追踪 handler - 无论是否回放都要处理
@crewai_event_bus.on(WorkflowStepEvent)
def trace_handler(source: Any, event: WorkflowStepEvent) -> None:
    mode = "回放" if is_replaying() else "正常"
    print(f"[Trace] {mode}模式: 记录事件 {event.step_name} (id={event.event_id})")


# 1. 正常发射
print("=== 第一次发射 ===")
event = WorkflowStepEvent(step_name="初始化")
crewai_event_bus.emit("source", event)
crewai_event_bus.flush()
# 输出:
# [Business] 执行副作用: 初始化 (count=1)
# [Trace] 正常模式: 记录事件 初始化 (id=...)

# 2. 回放同一事件
print("\n=== 回放同一事件 ===")
crewai_event_bus.replay("source", event)
crewai_event_bus.flush()
# 输出:
# [Business] 跳过副作用 (回放中): 初始化
# [Trace] 回放模式: 记录事件 初始化 (id=...)

print(f"\n副作用执行次数: {side_effect_count}")  # 输出: 1
```

---

## 5. 设计亮点与注意事项

### 5.1 设计亮点

#### 5.1.1 读写锁优化并发

`CrewAIEventsBus` 实例级使用 `RWLock`（`event_bus.py` 第 153 行）保护 handler 注册表。`emit()` 使用读锁（第 477、602 行），`on()` / `off()` 使用写锁（第 230、379 行）。多个并发 emit 可同时持有读锁，性能优异。

#### 5.1.2 执行计划缓存

`_execution_plan_cache`（第 124 行）缓存每个事件类型的拓扑排序结果。只有在 handler 注册/注销时才使缓存失效（第 243、399 行），大幅减少重复排序开销。

#### 5.1.3 ContextVar 传递上下文

通过 `contextvars.copy_context()`（第 633 行）将 `_replaying`、`_runtime_state_var` 等 `ContextVar` 状态传递到线程池中的 handler，无需手动传递参数。

#### 5.1.4 frozenset 不可变集合

Handler 注册表使用 `frozenset`（第 232-236 行），每次修改创建新 frozenset 对象。读操作不需要加锁也能拿到一致快照，配合 RWLock 实现高效读写分离。

#### 5.1.5 延迟初始化

线程池和事件循环在首次 `emit()` 时才初始化（`_ensure_executor_initialized`，第 166-191 行），避免不触发事件时的资源浪费。

#### 5.1.6 流事件同步处理

`LLMStreamChunkEvent` 的同步 handler 直接在调用线程执行（第 629-630 行），不使用线程池，确保流式数据的顺序性和低延迟。

#### 5.1.7 事件作用域栈

`event_context.py` 通过 `ContextVar` 维护事件作用域栈，自动匹配开始/结束事件对（`VALID_EVENT_PAIRS`，第 321-369 行），支持嵌套事件追踪和异常检测。

#### 5.1.8 事件回放支持

`replay()` + `is_replaying()` 机制让 handler 能区分首次发射和回放，避免 checkpoint 恢复时重复执行副作用操作。

### 5.2 注意事项

#### 5.2.1 线程安全边界

- **同步 handler 中的状态修改**：同步 handler 在线程池中执行，多个 handler 可能并发运行。如果 handler 修改共享状态（如 `EventListener` 的 `text_stream`），需要自行加锁。
- **`ContextVar` 的作用域**：`ContextVar` 的修改只影响当前线程/协程上下文。跨线程传递时使用 `contextvars.copy_context()`。

#### 5.2.2 异步 handler 的执行顺序

- 同一层级内的异步 handler 通过 `asyncio.gather` 并发执行（`event_bus.py` 第 451 行），不保证顺序。
- 需要顺序保证时，使用 `Depends` 声明依赖关系。

#### 5.2.3 事件循环生命周期

- 异步事件循环运行在守护线程中（`event_bus.py` 第 188 行），主线程退出时守护线程会被强制终止。
- 必须在程序退出前调用 `flush()` 或 `shutdown()` 确保异步 handler 完成。

#### 5.2.4 事件类型注册

- 所有 handler 必须使用 `@crewai_event_bus.on(EventClass)` 装饰器注册，事件类型必须继承自 `BaseEvent`。
- 同一事件类型可注册多个 handler，它们将按依赖层级执行。

#### 5.2.5 性能考量

- `ThreadPoolExecutor` 默认 10 个工作线程（第 180 行），大量同步 handler 时可能成为瓶颈。
- `flush()` 默认超时 30 秒（第 734 行），长时间运行的任务可能需要调整超时。
- 事件发射时会立即执行 `_prepare_event()` 中的 `publish_stream_event` 和 `_record_event`（第 569-570 行），这些操作在调用线程同步执行，路径较长。

#### 5.2.6 内存管理

- `_pending_futures` 集合（第 127 行）跟踪所有未完成的 Future，handler 泄露会导致此集合持续增长。
- `_execution_plan_cache` 缓存基于事件类型，如果动态创建大量事件类型，缓存可能膨胀。

#### 5.2.7 关闭状态

- 设置 `_shutting_down = True` 后（第 908 行），所有新的 `emit()` 调用将被忽略（第 604-607 行）。
- `shutdown()` 只应在程序退出时调用一次，重复调用可能导致异常。