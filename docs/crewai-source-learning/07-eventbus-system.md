# 阶段七：EventBus 事件系统 — 源码深度解析

---

## 1. 模块定位

### 1.1 一句话概括

**EventBus 事件系统是 CrewAI 的神经中枢，通过「单例事件总线 + 依赖图拓扑排序 + 线程池/异步事件循环双通道」架构，实现了事件发射、处理器注册、依赖排序、流式事件发布等功能，所有 LLM 调用、工具执行、Agent 决策、Crew 调度均通过 EventBus 进行解耦通信。**

### 1.2 在整体架构中的位置

```
                    ┌──────────────┐
                    │  CrewAIEventsBus  │  ← 单例事件总线
                    │  (Singleton)      │
                    └──────┬───────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
        ▼                  ▼                  ▼
   ┌─────────┐      ┌──────────┐      ┌──────────┐
   │  Sync   │      │  Async   │      │  Stream  │
   │Handlers │      │ Handlers │      │  Events  │
   │(线程池)  │      │(事件循环) │      │(同步执行) │
   └─────────┘      └──────────┘      └──────────┘

  发射源（emit source）:
  ┌─────────────────────────────────────────────┐
  │ LLM.call() → LLMCallStartedEvent             │
  │ ToolUsage._use() → ToolUsageStartedEvent     │
  │ Crew.kickoff() → CrewKickoffStartedEvent     │
  │ Agent.execute() → AgentExecutionStartedEvent │
  │ Memory → MemoryQueryEvent / MemorySaveEvent  │
  └─────────────────────────────────────────────┘
```

### 1.3 本阶段涉及的核心源码文件

| 文件 | 核心职责 |
|------|----------|
| `events/event_bus.py` | 事件总线核心：单例模式、注册、发射、依赖调度 |
| `events/base_events.py` | 事件基类：BaseEvent、发射序列号 |
| `events/handler_graph.py` | 处理器依赖图：拓扑排序、循环依赖检测 |
| `events/event_context.py` | 事件上下文：作用域管理、父子事件关系 |
| `events/stream_context.py` | 流式事件上下文：流式 chunk 发布 |
| `events/depends.py` | 依赖声明：Depends 类型 |
| `events/types/` | 事件类型定义（LLM、Tool、Agent、Crew 等 20+ 种） |
| `events/listeners/tracing/` | 追踪监听器：TraceListener、Batch 管理 |

---

## 2. 源码分层拆解

### 2.1 第一层：BaseEvent（事件基类）

**文件：** `lib/crewai/src/crewai/events/base_events.py`

```python
class BaseEvent(BaseModel):
    """所有事件的基类。"""
    timestamp: datetime          # 事件时间戳（UTC）
    type: str                    # 事件类型字符串
    event_id: str                # 事件唯一 ID（UUID）
    parent_event_id: str | None  # 父事件 ID（用于作用域嵌套）
    previous_event_id: str | None  # 前一个事件 ID
    triggered_by_event_id: str | None  # 触发者事件 ID
    started_event_id: str | None  # 启动事件 ID
    emission_sequence: int | None  # 发射序号（单调递增）

    # 指纹信息（用于追踪）
    source_fingerprint: str | None
    source_type: str | None  # "agent", "task", "crew", "memory" 等
    fingerprint_metadata: dict[str, Any] | None

    # 关联实体
    task_id: str | None
    task_name: str | None
    agent_id: str | None
    agent_role: str | None
```

**发射序号机制：**

```python
_emission_counter: contextvars.ContextVar[Iterator[int]] = ...

def get_next_emission_sequence() -> int:
    """获取下一个发射序号，使用 itertools.count 实现单调递增。"""
    seq = next(_get_or_create_counter())
    _last_emitted.set(seq)
    return seq
```

**大白话：** 每个事件有一个全局递增的序号，可以用于事件重放、断点恢复、调试排查。

---

### 2.2 第二层：CrewAIEventsBus（事件总线单例）

**文件：** `lib/crewai/src/crewai/events/event_bus.py`

#### 2.2.1 单例模式

```python
class CrewAIEventsBus:
    _instance: Self | None = None
    _instance_lock: threading.RLock = threading.RLock()

    def __new__(cls) -> Self:
        """双重检查锁定（DCL）实现线程安全单例。"""
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialize()
        return cls._instance
```

#### 2.2.2 核心数据结构

```python
class CrewAIEventsBus:
    _rwlock: RWLock                          # 读写锁
    _sync_handlers: dict[type[BaseEvent], frozenset]   # 同步处理器
    _async_handlers: dict[type[BaseEvent], frozenset]  # 异步处理器
    _handler_dependencies: dict[type[BaseEvent], dict]  # 处理器依赖
    _execution_plan_cache: dict[type[BaseEvent], ExecutionPlan]  # 执行计划缓存
    _sync_executor: ThreadPoolExecutor       # 线程池（max_workers=10）
    _loop: asyncio.AbstractEventLoop         # 异步事件循环
    _loop_thread: threading.Thread           # 后台守护线程
```

#### 2.2.3 处理器注册（on 装饰器）

```python
def on(self, event_type, depends_on=None):
    """装饰器：注册事件处理器。"""
    def decorator(handler):
        deps = [depends_on] if isinstance(depends_on, Depends) else depends_on
        self._register_handler(event_type, handler, dependencies=deps)
        return handler
    return decorator

def _register_handler(self, event_type, handler, dependencies=None):
    """内部注册方法。"""
    with self._rwlock.w_locked():  # 写锁保护
        if is_async_handler(handler):
            self._async_handlers[event_type] = existing | {handler}
        else:
            self._sync_handlers[event_type] = existing | {handler}
        self._execution_plan_cache.pop(event_type, None)  # 清除缓存
```

#### 2.2.4 事件发射（emit 方法）

```python
def emit(self, source: Any, event: BaseEvent) -> Future[None] | None:
    """发射事件到所有注册的处理器。"""
    # 1. 准备事件（设置元数据、父子关系、发射序号）
    self._prepare_event(source, event)

    # 2. 获取处理器
    event_type = type(event)
    sync_handlers = self._sync_handlers.get(event_type, frozenset())
    async_handlers = self._async_handlers.get(event_type, frozenset())

    # 3. 无处理器 → 直接返回
    if not sync_handlers and not async_handlers:
        return None

    # 4. 流式事件 → 同步执行（保证顺序）
    if event_type is LLMStreamChunkEvent:
        self._call_handlers(source, event, sync_handlers, state)
        return None

    # 5. 有依赖 → 异步调度执行计划
    if self._handler_dependencies.get(event_type):
        return self._schedule_async_emit(source, event, state)

    # 6. 无依赖 → 直接分发
    if sync_handlers:
        ctx = contextvars.copy_context()  # 复制 contextvars
        future = self._sync_executor.submit(
            ctx.run, self._call_handlers, source, event, sync_handlers, state
        )
        return future
```

**关键设计：** `contextvars.copy_context()` 确保线程池中的处理器能访问到发射时的上下文变量（如 `stop_sequences` 覆盖）。

---

### 2.3 第三层：HandlerGraph（依赖图拓扑排序）

**文件：** `lib/crewai/src/crewai/events/handler_graph.py`

```python
class HandlerGraph:
    """将处理器的依赖关系解析为并行执行层级。"""
    def _resolve(self) -> None:
        """拓扑排序（Kahn 算法）"""
        # 构建依赖图
        dependents: dict[Handler, set[Handler]] = defaultdict(set)
        in_degree: dict[Handler, int] = {}

        for handler, deps in self.handlers.items():
            in_degree[handler] = len(deps)
            for dep in deps:
                dependents[dep.handler].add(handler)

        # BFS 拓扑排序
        queue = deque([h for h, deg in in_degree.items() if deg == 0])
        while queue:
            current_level = set()
            for _ in range(len(queue)):
                handler = queue.popleft()
                current_level.add(handler)
                for dependent in dependents[handler]:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        queue.append(dependent)
            if current_level:
                self.levels.append(current_level)

        # 循环依赖检测
        remaining = [h for h, deg in in_degree.items() if deg > 0]
        if remaining:
            raise CircularDependencyError(remaining)
```

**大白话：** 如果 Handler A 依赖 Handler B，则 B 在 Level 0 执行，A 在 Level 1 执行。同 Level 的处理器可以并行执行。

---

### 2.4 第四层：事件作用域（Event Context）

**文件：** `lib/crewai/src/crewai/events/event_context.py`

```python
SCOPE_STARTING_EVENTS = {
    "crew_kickoff_started", "agent_execution_started",
    "task_execution_started", "llm_call_started", ...
}
SCOPE_ENDING_EVENTS = {
    "crew_kickoff_completed", "agent_execution_completed",
    "task_execution_completed", "llm_call_completed", ...
}
VALID_EVENT_PAIRS = {
    "crew_kickoff_completed": "crew_kickoff_started",
    "agent_execution_completed": "agent_execution_started",
    "task_execution_completed": "task_execution_started",
    "llm_call_completed": "llm_call_started",
    # ...
}
```

**作用域机制：** 当 `LLMCallStartedEvent` 发射时，推入作用域栈；当 `LLMCallCompletedEvent` 发射时，弹出作用域栈。这样 `parent_event_id` 自动指向外层事件。

---

## 3. 完整调用时序图

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        EventBus 完整调用时序                              │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  1. 启动阶段                                                              │
│     crewai_event_bus = CrewAIEventsBus()  ← 单例初始化                    │
│         ├── _initialize()                                                 │
│         │   ├── 创建 RWLock                                               │
│         │   ├── 创建空 handler 字典                                       │
│         │   └── 创建执行计划缓存                                          │
│         └── 懒加载线程池和事件循环（首次 emit 时）                        │
│                                                                           │
│  2. 注册处理器                                                             │
│     @crewai_event_bus.on(LLMCallStartedEvent)                             │
│     def handle_llm_call(source, event):  ...                              │
│         │                                                                  │
│         └── _register_handler(LLMCallStartedEvent, handle_llm_call)       │
│             ├── 获取写锁（_rwlock.w_locked()）                            │
│             ├── 判断同步/异步 → 加入对应 handler 集合                     │
│             └── 清除执行计划缓存                                          │
│                                                                           │
│  3. 发射事件                                                               │
│     crewai_event_bus.emit(source, event)                                  │
│         │                                                                  │
│         ├── _prepare_event(source, event)                                 │
│         │   ├── 注册 source 实体（register_entity）                      │
│         │   ├── 设置 previous_event_id / triggered_by_event_id           │
│         │   ├── 设置 emission_sequence（递增序号）                        │
│         │   ├── 处理作用域（parent_event_id、push/pop scope）            │
│         │   ├── 发布流式事件（publish_stream_event）                      │
│         │   └── 记录事件到 RuntimeState                                  │
│         │                                                                  │
│         ├── 获取 handler 集合（读锁）                                     │
│         │   sync_handlers = _sync_handlers.get(event_type)                │
│         │   async_handlers = _async_handlers.get(event_type)              │
│         │                                                                  │
│         ├── 无 handler → 返回 None                                        │
│         │                                                                  │
│         ├── 流式事件 → 同步执行（保证顺序）                               │
│         │                                                                  │
│         ├── 有依赖 → _emit_with_dependencies()                            │
│         │   ├── 获取/构建执行计划（缓存）                                 │
│         │   │   └── HandlerGraph._resolve() → 拓扑排序                   │
│         │   ├── 按 Level 顺序执行                                         │
│         │   │   ├── Level 0: sync → 线程池 | async → asyncio.gather     │
│         │   │   ├── 等待 Level 0 完成                                     │
│         │   │   ├── Level 1: sync → 线程池 | async → asyncio.gather     │
│         │   │   └── ... 直到所有 Level 完成                               │
│         │   └── 返回 Future                                               │
│         │                                                                  │
│         └── 无依赖 → 直接分发                                             │
│             ├── sync → ThreadPoolExecutor.submit(ctx.run, handler)        │
│             └── async → asyncio.run_coroutine_threadsafe(handler)         │
│                                                                           │
│  4. 优雅关闭                                                               │
│     atexit.register(crewai_event_bus.shutdown)                            │
│         ├── 等待所有 pending futures 完成                                 │
│         ├── 关闭线程池（_sync_executor.shutdown()）                       │
│         └── 停止事件循环（_loop.stop()）                                  │
│                                                                           │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 4. 核心设计亮点

### 4.1 单例模式 + 双重检查锁定

```python
def __new__(cls):
    if cls._instance is None:
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
    return cls._instance
```

**面试高频考点：** 双重检查锁定（DCL）是线程安全单例的经典模式，第一个 `if` 避免不必要的锁竞争，第二个 `if` 保证只创建一次。

### 4.2 读写锁保护 Handler 集合

```python
_rwlock: RWLock  # 自定义读写锁

# 注册时：写锁（独占）
with self._rwlock.w_locked():
    self._sync_handlers[event_type] = ...

# 发射时：读锁（共享）
with self._rwlock.r_locked():
    sync_handlers = self._sync_handlers.get(event_type)
```

**大白话：** 多个事件可以同时发射（读锁共享），但注册处理器时需要独占（写锁），保证线程安全且不阻塞并发发射。

### 4.3 依赖图拓扑排序

通过 `HandlerGraph` 将处理器按依赖关系分组为多个 Level，同 Level 内并行执行，不同 Level 顺序执行。这允许用户定义：
- "先写日志，再发追踪" → Level 0: 日志, Level 1: 追踪
- "先保存到缓存，再通知外部系统" → 依赖链

### 4.4 contextvars 上下文传递

```python
ctx = contextvars.copy_context()  # 复制当前上下文
future = self._sync_executor.submit(
    ctx.run, self._call_handlers, source, event, sync_handlers, state
)
```

**面试高频考点：** `contextvars.copy_context()` 将当前线程的上下文变量（如 `_call_stop_override_var`）传递给线程池中的工作线程，保持跨线程的上下文一致性。

### 4.5 执行计划缓存

```python
_execution_plan_cache: dict[type[BaseEvent], ExecutionPlan] = {}

# 首次计算执行计划后缓存
cached_plan = build_execution_plan(all_handlers, dependencies)
self._execution_plan_cache[event_type] = cached_plan

# 处理器变更时清除缓存
self._execution_plan_cache.pop(event_type, None)
```

**设计目的：** 拓扑排序有 O(V+E) 的开销，缓存后每次事件发射只需 O(1) 查找。

---

## 5. 生产落地拓展改造

### 5.1 事件持久化到 Kafka

```python
from kafka import KafkaProducer
import json

class KafkaEventHandler:
    def __init__(self, bootstrap_servers: str, topic: str):
        self.producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode("utf-8")
        )
        self.topic = topic

    def __call__(self, source, event: BaseEvent):
        self.producer.send(self.topic, event.to_json())

# 注册
@crewai_event_bus.on(LLMCallCompletedEvent)
def persist_to_kafka(source, event):
    kafka_handler = KafkaEventHandler("localhost:9092", "crewai-events")
    kafka_handler(source, event)
```

### 5.2 分布式追踪（OpenTelemetry）

```python
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

@crewai_event_bus.on(LLMCallStartedEvent)
def start_span(source, event: LLMCallStartedEvent):
    span = tracer.start_span(
        "llm_call",
        attributes={
            "model": event.model,
            "call_type": event.call_type,
            "emission_sequence": event.emission_sequence,
        }
    )
    # 存储 span 以便后续结束
    _active_spans[event.event_id] = span

@crewai_event_bus.on(LLMCallCompletedEvent)
def end_span(source, event: LLMCallCompletedEvent):
    span = _active_spans.pop(event.started_event_id, None)
    if span:
        span.set_attribute("tokens", event.total_tokens)
        span.end()
```

### 5.3 事件重放引擎

```python
class EventReplayer:
    def __init__(self, events: list[BaseEvent]):
        self.events = sorted(events, key=lambda e: e.emission_sequence)

    def replay(self, bus: CrewAIEventsBus):
        """按发射序号重放事件。"""
        with replay_context():
            for event in self.events:
                bus.emit(event.source, event)
```

---

## 6. 面试深挖问题清单

| # | 问题 | 考察点 |
|---|------|--------|
| 1 | CrewAIEventsBus 为什么使用单例模式？ | 设计模式、全局事件管理 |
| 2 | `contextvars.copy_context()` 在 emit 中的作用是什么？ | 线程安全、上下文传递 |
| 3 | HandlerGraph 的拓扑排序算法是什么？ | Kahn 算法、循环依赖检测 |
| 4 | 同步处理器和异步处理器的执行方式有何区别？ | ThreadPoolExecutor vs asyncio |
| 5 | 为什么流式事件（LLMStreamChunkEvent）要同步执行？ | 顺序保证、实时性 |
| 6 | 执行计划缓存何时失效？ | 缓存策略、写时失效 |
| 7 | `VALID_EVENT_PAIRS` 的作用是什么？ | 事件作用域、配对校验 |
| 8 | `emission_sequence` 的设计目的是什么？ | 事件排序、重放支持 |
| 9 | event_bus 如何优雅关闭？ | atexit、Future 等待 |
| 10 | 如何在事件处理器中访问 RuntimeState？ | 参数注入、3 参数 handler |

---

## 7. 简易可运行 Demo

```python
"""Demo: EventBus 注册、发射、依赖排序"""
from crewai.events.event_bus import crewai_event_bus
from crewai.events.types.llm_events import (
    LLMCallStartedEvent, LLMCallCompletedEvent, LLMCallType
)
from crewai.events.depends import Depends
import time

# 1. 注册处理器（无依赖）
@crewai_event_bus.on(LLMCallStartedEvent)
def log_llm_start(source, event):
    print(f"[LOG] LLM 调用开始: {event.model}")

# 2. 注册处理器（依赖 log_llm_start 先执行）
@crewai_event_bus.on(LLMCallCompletedEvent, depends_on=Depends(log_llm_start))
def log_llm_end(source, event):
    print(f"[LOG] LLM 调用完成: tokens={event.total_tokens}")

# 3. 注册异步处理器
@crewai_event_bus.on(LLMCallCompletedEvent)
async def metrics_collector(source, event):
    await asyncio.sleep(0.1)  # 模拟异步操作
    print(f"[METRICS] 记录到监控系统: {event.model}")

# 4. 发射事件
event = LLMCallStartedEvent(
    type="llm_call_started",
    model="gpt-4o",
    call_type=LLMCallType.LLM_CALL,
    messages_count=5,
    agent_role="研究员",
    task_name="搜索任务",
)
future = crewai_event_bus.emit(source=None, event=event)
if future:
    future.result(timeout=5)  # 等待处理器完成

print("所有事件处理器已执行完毕")
```

---

**下一阶段解析指令：**

```
# 当前解析目标
模块名称：Knowledge 知识检索
对应源码文件路径：
- lib/crewai/src/crewai/knowledge/knowledge.py（Knowledge 主类）
- lib/crewai/src/crewai/knowledge/source/base_knowledge_source.py（知识源基类）
- lib/crewai/src/crewai/knowledge/source/string_knowledge_source.py（字符串知识源）
- lib/crewai/src/crewai/knowledge/source/docling_source.py（文档解析知识源）
- lib/crewai/src/crewai/knowledge/storage/knowledge_storage.py（知识存储）
- lib/crewai/src/crewai/rag/（RAG 检索模块）

# 本次输出硬性要求，缺一不可
1. 模块定位（一句话 + 架构位置 + 核心文件清单）
2. 源码分层拆解（文件→类→方法→关键代码行）
3. 完整调用时序图（知识加载 → 分块 → 向量化 → 存储 → 检索）
4. 核心设计亮点（多源支持、文档解析、Embedding 抽象、查询重写）
5. 生产落地拓展改造（多模态知识库、混合检索 BM25+向量、知识图谱）
6. 面试深挖问题清单（10 题）
7. 简易可运行 Demo 代码
```