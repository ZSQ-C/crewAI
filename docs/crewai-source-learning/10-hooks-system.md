# 阶段十：Hooks 钩子系统 — 源码深度解析

---

## 1. 模块定位

### 1.1 一句话概括

**Hooks 钩子系统是 CrewAI 的 AOP（面向切面编程）拦截层，通过「装饰器注册 + 全局/局部钩子 + 过滤器链」架构，在 LLM 调用和工具执行的前后插入自定义逻辑，支持修改消息、拦截执行、人工审批、内容过滤等企业级场景。**

### 1.2 在整体架构中的位置

```
                    ┌──────────────────────┐
                    │   Hooks 钩子系统      │
                    │   (装饰器 + 全局注册)  │
                    └──────────┬───────────┘
                               │
          ┌────────────────────┼────────────────────┐
          │                    │                    │
          ▼                    ▼                    ▼
   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
   │ before_llm   │    │ after_llm    │    │ before_tool  │
   │ _call        │    │ _call        │    │ _call        │
   │              │    │              │    │              │
   │ 修改 messages │    │ 修改 response │    │ 修改 tool_input│
   │ 拦截调用      │    │ 修改历史      │    │ 拦截执行      │
   └──────────────┘    └──────────────┘    └──────────────┘
                               │
                               ▼
                      ┌──────────────┐
                      │ after_tool   │
                      │ _call        │
                      │              │
                      │ 修改 result  │
                      │ 人工审批      │
                      └──────────────┘
```

### 1.3 本阶段涉及的核心源码文件

| 文件 | 核心职责 |
|------|----------|
| `hooks/llm_hooks.py` | LLM 钩子：LLMCallHookContext、注册函数、触发逻辑 |
| `hooks/tool_hooks.py` | 工具钩子：ToolCallHookContext、注册函数、触发逻辑 |
| `hooks/decorators.py` | 装饰器工厂：`@before_llm_call`、`@after_llm_call`、`@before_tool_call`、`@after_tool_call` |
| `hooks/types.py` | 类型定义：Hook Protocol、BeforeLLMCallHook、AfterToolCallHook 等 |
| `hooks/wrappers.py` | 包装器：钩子执行包装逻辑 |

---

## 2. 源码分层拆解

### 2.1 第一层：Hook Protocol（钩子协议）

**文件：** `lib/crewai/src/crewai/hooks/types.py`

```python
@runtime_checkable
class Hook(Protocol, Generic[ContextT, ReturnT]):
    """通用钩子协议。"""
    def __call__(self, context: ContextT) -> ReturnT:
        """执行钩子，接收上下文，可选返回修改后的结果。"""

class BeforeLLMCallHook(Hook["LLMCallHookContext", bool | None], Protocol):
    """LLM 调用前钩子。返回 False 阻止执行，True/None 允许。"""

class AfterLLMCallHook(Hook["LLMCallHookContext", str | None], Protocol):
    """LLM 调用后钩子。返回 str 替换响应，None 保持原样。"""

class BeforeToolCallHook(Hook["ToolCallHookContext", bool | None], Protocol):
    """工具调用前钩子。返回 False 阻止执行。"""

class AfterToolCallHook(Hook["ToolCallHookContext", str | None], Protocol):
    """工具调用后钩子。返回 str 修改结果。"""
```

**四种钩子一览：**

| 钩子类型 | 触发时机 | 可修改内容 | 拦截能力 |
|----------|----------|-----------|----------|
| `before_llm_call` | LLM 调用前 | messages（就地修改） | 返回 False 阻止 |
| `after_llm_call` | LLM 调用后 | response、messages | 返回新字符串替换 |
| `before_tool_call` | 工具执行前 | tool_input（就地修改） | 返回 False 阻止 |
| `after_tool_call` | 工具执行后 | tool_result | 返回新字符串替换 |

---

### 2.2 第二层：LLMCallHookContext（LLM 钩子上下文）

**文件：** `lib/crewai/src/crewai/hooks/llm_hooks.py`

```python
class LLMCallHookContext:
    """LLM 调用的钩子上下文，提供完整的执行状态访问。"""

    executor: CrewAgentExecutor | LiteAgent | None  # 执行器引用
    messages: list[LLMMessage]  # 消息列表（可修改）
    agent: Any                  # 当前 Agent
    task: Any                   # 当前 Task
    crew: Any                   # 当前 Crew
    llm: BaseLLM | None         # LLM 实例
    iterations: int             # 当前迭代次数
    response: str | None        # LLM 响应（仅 after 钩子）

    def request_human_input(self, prompt, default_message) -> str:
        """在钩子中请求人工输入（暂停输出 → 显示提示 → 等待输入 → 恢复）。"""
        event_listener.formatter.pause_live_updates()
        try:
            PRINTER.print(content=f"\n{prompt}", color="bold_yellow")
            return input().strip()
        finally:
            event_listener.formatter.resume_live_updates()
```

---

### 2.3 第三层：装饰器工厂（Decorator Factory）

**文件：** `lib/crewai/src/crewai/hooks/decorators.py`

```python
def _create_hook_decorator(hook_type, register_function, marker_attribute):
    """创建钩子装饰器的工厂函数，消除四种装饰器的重复代码。"""

    def decorator_factory(func=None, *, tools=None, agents=None):
        """支持 @before_llm_call 和 @before_llm_call(agents=[...]) 两种用法。"""

        def decorator(f):
            setattr(f, marker_attribute, True)  # 标记函数

            if tools or agents:
                @wraps(f)
                def filtered_hook(context):
                    # 工具过滤：只对指定工具触发
                    if tools and hasattr(context, "tool_name"):
                        if context.tool_name not in tools:
                            return None
                    # Agent 过滤：只对指定 Agent 触发
                    if agents and hasattr(context, "agent"):
                        if context.agent.role not in agents:
                            return None
                    return f(context)  # 通过过滤，执行原始钩子

                register_function(filtered_hook)  # 注册过滤后的钩子
                return f

            register_function(f)  # 无过滤，直接注册
            return f

        return decorator(func) if func else decorator

    return decorator_factory
```

**使用方式：**

```python
# 无过滤：对所有 LLM 调用生效
@before_llm_call
def log_all_calls(context):
    print(f"LLM 调用: {context.agent.role}")

# Agent 过滤：只对 Researcher 和 Analyst 生效
@before_llm_call(agents=["Researcher", "Analyst"])
def log_specific(context):
    print(f"特定 Agent 调用: {context.agent.role}")

# 工具过滤：只对 search_web 和 calculator 生效
@before_tool_call(tools=["search_web", "calculator"])
def log_tools(context):
    print(f"工具调用: {context.tool_name}")
```

---

### 2.4 第四层：全局钩子注册

```python
# llm_hooks.py — 全局钩子列表
_before_llm_call_hooks: list[BeforeLLMCallHookType] = []
_after_llm_call_hooks: list[AfterLLMCallHookType] = []

def register_before_llm_call_hook(hook):
    """注册全局 before_llm_call 钩子（对所有 LLM 调用生效）。"""
    _before_llm_call_hooks.append(hook)

# tool_hooks.py — 全局钩子列表
_before_tool_call_hooks: list[BeforeToolCallHookType] = []
_after_tool_call_hooks: list[AfterToolCallHookType] = []

def register_before_tool_call_hook(hook):
    """注册全局 before_tool_call 钩子（对所有工具调用生效）。"""
    _before_tool_call_hooks.append(hook)
```

**大白话：** 使用 `@before_llm_call` 装饰器后，函数会被自动添加到全局钩子列表。也可以手动调用 `register_before_llm_call_hook(hook)` 函数式注册。

---

## 3. 完整调用时序图

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        Hooks 钩子执行时序                                 │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  1. 注册阶段                                                               │
│     @before_llm_call                                                       │
│     def my_hook(context): ...                                              │
│         │                                                                  │
│         └── register_before_llm_call_hook(my_hook)                        │
│             └── _before_llm_call_hooks.append(my_hook)                    │
│                                                                           │
│  2. LLM 调用前                                                             │
│     CrewAgentExecutor._invoke_loop()                                       │
│         │                                                                  │
│         ├── 构建 LLMCallHookContext(executor=self)                         │
│         │                                                                  │
│         ├── for hook in _before_llm_call_hooks:                            │
│         │   ├── 检查过滤条件（tools/agents）                                │
│         │   │   └── 不匹配 → 跳过                                          │
│         │   ├── result = hook(context)                                     │
│         │   │   ├── hook 修改 context.messages（就地修改）                  │
│         │   │   └── 返回 None/True → 继续                                  │
│         │   └── result == False → 阻止 LLM 调用 ⛔                         │
│         │                                                                  │
│         ├── [所有钩子通过] → 实际调用 LLM                                   │
│         │                                                                  │
│         └── 获取 LLM response                                              │
│                                                                           │
│  3. LLM 调用后                                                             │
│         ├── 更新 context.response = llm_response                           │
│         │                                                                  │
│         ├── for hook in _after_llm_call_hooks:                             │
│         │   ├── result = hook(context)                                     │
│         │   │   ├── hook 修改 context.response                             │
│         │   │   └── 返回 str → 替换 response                              │
│         │   └── 返回 None → 保持原 response                                │
│         │                                                                  │
│         └── 返回最终 response（可能被钩子修改）                             │
│                                                                           │
│  4. 工具调用前                                                              │
│     ToolUsage._use()                                                       │
│         ├── 构建 ToolCallHookContext(tool_name, tool_input, tool, ...)     │
│         │                                                                  │
│         ├── for hook in _before_tool_call_hooks:                           │
│         │   ├── 检查过滤条件（tools/agents）                                │
│         │   ├── hook 修改 context.tool_input（就地修改）                    │
│         │   └── result == False → 阻止工具执行 ⛔                           │
│         │                                                                  │
│         └── [所有钩子通过] → 实际执行工具                                   │
│                                                                           │
│  5. 工具调用后                                                              │
│         ├── for hook in _after_tool_call_hooks:                            │
│         │   ├── result = hook(context)                                     │
│         │   └── 返回 str → 替换 tool_result                                │
│         │                                                                  │
│         └── 返回最终 tool_result（可能被钩子修改）                          │
│                                                                           │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 4. 核心设计亮点

### 4.1 装饰器工厂模式（DRY）

```python
def _create_hook_decorator(hook_type, register_function, marker_attribute):
    """一个工厂函数生成四种装饰器，消除重复代码。"""
```

**面试高频考点：** 四种钩子（before/after × llm/tool）共享相同的过滤逻辑，通过工厂函数 + 参数化消除重复，遵循 DRY 原则。

### 4.2 过滤器链（Filters）

```python
@before_tool_call(tools=["search_web", "calculator"])
def log_tools(context):
    ...
```

支持 `tools` 和 `agents` 两种过滤维度，装饰器内部自动生成过滤包装函数。

### 4.3 就地修改策略

```python
# 钩子修改 messages 时，必须就地修改，不能替换引用
context.messages.append({"role": "system", "content": "额外提示"})
# ❌ 错误: context.messages = new_list  # 会断开执行器引用
```

### 4.4 人工审批集成

```python
context.request_human_input(
    prompt="是否允许此操作？",
    default_message="输入 'yes' 继续:"
)
```

暂停终端输出，显示提示，等待人工输入，然后恢复——实现审批流。

### 4.5 返回值控制执行

| 钩子类型 | 返回值 | 含义 |
|----------|--------|------|
| `before_llm_call` | `False` | 阻止 LLM 调用 |
| `before_llm_call` | `True` / `None` | 允许继续 |
| `after_llm_call` | `str` | 替换 LLM 响应 |
| `after_llm_call` | `None` | 保持原响应 |
| `before_tool_call` | `False` | 阻止工具执行 |
| `after_tool_call` | `str` | 替换工具结果 |

---

## 5. 生产落地拓展改造

### 5.1 AOP 日志注入

```python
@before_llm_call
def inject_request_id(context):
    """在每个 LLM 调用前注入请求 ID 和追踪信息。"""
    import uuid
    context.messages.append({
        "role": "system",
        "content": f"[RequestID: {uuid.uuid4()}] [Timestamp: {datetime.now()}]"
    })

@after_llm_call
def log_response(context):
    """记录 LLM 响应到日志系统。"""
    logger.info(f"Agent={context.agent.role}, "
                f"Iter={context.iterations}, "
                f"ResponseLen={len(context.response)}")
```

### 5.2 敏感内容过滤

```python
SENSITIVE_PATTERNS = [r"\b\d{16}\b", r"\bpassword\b"]

@before_llm_call
def filter_sensitive_data(context):
    """在发送给 LLM 前过滤敏感信息。"""
    import re
    for msg in context.messages:
        if isinstance(msg.get("content"), str):
            for pattern in SENSITIVE_PATTERNS:
                msg["content"] = re.sub(pattern, "[REDACTED]", msg["content"])
```

### 5.3 断路器模式

```python
class CircuitBreaker:
    def __init__(self, failure_threshold=5, reset_timeout=60):
        self.failures = 0
        self.threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.last_failure_time = None
        self.open = False

circuit_breaker = CircuitBreaker()

@before_llm_call
def check_circuit(context):
    if circuit_breaker.open:
        if time.time() - circuit_breaker.last_failure_time > circuit_breaker.reset_timeout:
            circuit_breaker.open = False  # 半开状态
        else:
            return False  # 阻止调用

@after_llm_call
def update_circuit(context):
    if "error" in (context.response or "").lower():
        circuit_breaker.failures += 1
        if circuit_breaker.failures >= circuit_breaker.threshold:
            circuit_breaker.open = True
            circuit_breaker.last_failure_time = time.time()
    else:
        circuit_breaker.failures = 0
```

---

## 6. 面试深挖问题清单

| # | 问题 | 考察点 |
|---|------|--------|
| 1 | 四种钩子类型的触发时机和返回值含义是什么？ | 钩子生命周期、返回值控制 |
| 2 | `_create_hook_decorator` 工厂函数的设计目的是什么？ | DRY 原则、装饰器模式 |
| 3 | 钩子如何实现 Agent 和 Tool 级别的过滤？ | 过滤器链、闭包 |
| 4 | `request_human_input` 的实现原理是什么？ | 暂停/恢复输出、I/O 阻塞 |
| 5 | 为什么钩子修改 messages 要就地修改而不是替换？ | 引用传递、Python 内存模型 |
| 6 | 全局钩子和装饰器钩子的注册机制有何区别？ | 全局注册表、装饰器语法糖 |
| 7 | Hook Protocol 的泛型设计有什么优势？ | 类型安全、Protocol 协议 |
| 8 | `before_llm_call` 返回 False 后，after 钩子还会执行吗？ | 短路逻辑、执行流控制 |
| 9 | 如何在钩子中实现请求级别的上下文传递？ | contextvars、ThreadLocal |
| 10 | 钩子系统与 EventBus 的关系是什么？ | 同步拦截 vs 异步事件 |

---

## 7. 简易可运行 Demo

```python
"""Demo: Hooks 钩子系统 — 日志、过滤、审批"""
from crewai import Agent, Task, Crew
from crewai.hooks.decorators import before_llm_call, after_llm_call
from crewai.hooks.decorators import before_tool_call, after_tool_call

# 1. 注册 LLM 调用前钩子（记录日志）
@before_llm_call
def log_llm_start(context):
    print(f"[HOOK] Agent '{context.agent.role}' 第 {context.iterations} 次 LLM 调用")

# 2. 注册 LLM 调用后钩子（修改响应）
@after_llm_call
def add_safety_note(context):
    """在 LLM 响应后追加安全提示。"""
    if context.response:
        context.response += "\n\n[注意：此回答由 AI 生成，仅供参考]"
    return context.response  # 返回修改后的响应

# 3. 注册工具调用前钩子（只对特定 Agent 生效）
@before_tool_call(agents=["Researcher"])
def log_researcher_tools(context):
    print(f"[HOOK] Researcher 正在调用工具: {context.tool_name}")

# 4. 注册工具调用后钩子（审批敏感操作）
@after_tool_call(tools=["delete_file", "execute_code"])
def approve_dangerous_ops(context):
    response = context.request_human_input(
        prompt=f"确认执行 '{context.tool_name}'?",
        default_message="输入 'yes' 继续，其他键取消:",
    )
    if response.lower() != "yes":
        return f"操作被用户拒绝: {context.tool_name}"
    return None  # 保持原结果

# 5. 创建 Agent 和 Task
agent = Agent(
    role="Researcher",
    goal="搜索信息",
    llm="gpt-4o-mini",
    tools=[search_tool],
)

task = Task(
    description="搜索 CrewAI 最新版本",
    expected_output="版本号",
    agent=agent,
)

crew = Crew(agents=[agent], tasks=[task])
result = crew.kickoff()
print(f"最终结果: {result}")
```

---

**下一阶段解析指令：**

```
# 当前解析目标
模块名称：State & Checkpoint 状态持久化
对应源码文件路径：
- lib/crewai/src/crewai/state/runtime.py（RuntimeState 运行时状态）
- lib/crewai/src/crewai/state/checkpoint.py（Checkpoint 检查点）
- lib/crewai/src/crewai/state/persistence.py（持久化存储）
- lib/crewai/src/crewai/state/state_manager.py（状态管理器）
- lib/crewai/src/crewai/state/utils.py（状态工具函数）

# 本次输出硬性要求，缺一不可
1. 模块定位（一句话 + 架构位置 + 核心文件清单）
2. 源码分层拆解（文件→类→方法→关键代码行）
3. 完整调用时序图（状态创建 → 快照 → 序列化 → 持久化 → 恢复）
4. 核心设计亮点（快照机制、增量更新、多后端支持、断点续传）
5. 生产落地拓展改造（PostgreSQL 持久化、分布式状态共享、状态版本管理）
6. 面试深挖问题清单（10 题）
7. 简易可运行 Demo 代码
```