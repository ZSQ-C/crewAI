# 阶段三：Agent 执行层引擎 — 源码深度解析

---

## 1. 模块定位

### 1.1 一句话概括

**Agent 执行层引擎是 CrewAI 中「Agent 如何思考→行动→观察→输出」的核心事件循环，负责将 LLM 的文本输出解析为可执行动作、调用工具、收集结果、循环迭代直至产生最终答案。**

### 1.2 在整体架构中的位置

```
用户定义 Crew → Crew 调度引擎 → 为每个 Task 创建 AgentExecutor
                                       ↓
                                【Agent 执行层引擎】← 本阶段
                                       ↓
                                LLM 调用 → 解析输出 → 工具执行 → 循环
                                       ↓
                                AgentFinish（最终答案）
```

### 1.3 本阶段涉及的核心源码文件

| 文件 | 行数 | 核心职责 |
|------|------|----------|
| `agents/crew_agent_executor.py` | ~1671 行 | Agent 执行器主类，ReAct/Native 双模式循环 |
| `agents/step_executor.py` | ~648 行 | Plan-and-Act 模式下的单步执行器 |
| `agents/parser.py` | ~179 行 | LLM 输出解析器，提取 Action/Thought/Final Answer |
| `agents/tools_handler.py` | ~52 行 | 工具调用缓存与记录 |
| `agents/agent_builder/base_agent_executor.py` | ~65 行 | 执行器抽象基类 |
| `agents/cache/cache_handler.py` | ~51 行 | 工具结果缓存（读写锁） |
| `agents/constants.py` | ~26 行 | 解析器正则常量 |

---

## 2. 源码分层拆解

### 2.1 第一层：BaseAgentExecutor（抽象基类）

**文件：** `lib/crewai/src/crewai/agents/agent_builder/base_agent_executor.py`

```python
class BaseAgentExecutor(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    executor_type: str = "base"                          # 执行器类型标识
    crew: Crew | None = Field(default=None, exclude=True) # 所属 Crew 引用
    agent: BaseAgent | None = Field(default=None, exclude=True) # 所属 Agent 引用
    task: Task | None = Field(default=None, exclude=True) # 当前 Task 引用
    iterations: int = Field(default=0)                   # 当前迭代次数
    max_iter: int = Field(default=25)                    # 最大迭代次数限制
    messages: list[LLMMessage] = Field(default_factory=list) # LLM 对话历史
    _resuming: bool = PrivateAttr(default=False)         # 是否为恢复执行
```

**大白话解释：**
- `BaseAgentExecutor` 是所有执行器的「骨架」，定义了一个 Agent 执行任务时需要的通用属性。
- `iterations` 和 `max_iter` 是防止无限循环的「安全阀」——Agent 最多只能跑 25 轮。
- `messages` 是 LLM 的对话历史，每次调用 LLM 都会带上历史消息列表。
- `_resuming` 是 PrivateAttr，不会被序列化到外部，用于标记从检查点恢复执行。

**关键方法：`_save_to_memory()`**

```python
def _save_to_memory(self, output: AgentFinish) -> None:
    """将任务结果保存到统一记忆系统（memory 或 crew._memory）。"""
    if self.agent is None:
        return
    memory = getattr(self.agent, "memory", None) or (
        getattr(self.crew, "_memory", None) if self.crew else None
    )
    if memory is None or not self.task or memory.read_only:
        return
    # 如果是委托任务，不保存到记忆（避免重复）
    if f"Action: {sanitize_tool_name('Delegate work to coworker')}" in output.text:
        return
    try:
        raw = (
            f"Task: {self.task.description}\n"
            f"Agent: {self.agent.role}\n"
            f"Expected result: {self.task.expected_output}\n"
            f"Result: {output.text}"
        )
        extracted = memory.extract_memories(raw)  # 从结果中提取关键记忆
        if extracted:
            memory.remember_many(extracted, agent_role=self.agent.role)
    except Exception as e:
        self.agent._logger.log("error", f"Failed to save to memory: {e}")
```

**设计目的：** 每次 Agent 执行完成后，自动将结果写入记忆系统，供后续 Agent 或跨会话使用。

---

### 2.2 第二层：CrewAgentExecutor（主执行器）⚠️ 已标记废弃

**文件：** `lib/crewai/src/crewai/agents/crew_agent_executor.py`

> **重要提示：** `CrewAgentExecutor` 已被标记为 `DeprecationWarning`，官方推荐使用新的 `AgentExecutor`（位于 `crewai.experimental`）。但源码中大部分逻辑仍在此类中，理解它对理解整个框架至关重要。

#### 2.2.1 核心字段详解

```python
class CrewAgentExecutor(BaseAgentExecutor):
    executor_type: Literal["crew"] = "crew"
    llm: BaseLLM | str | None = None          # 大模型实例（支持字符串引用）
    prompt: SystemPromptResult | StandardPromptResult | None = None  # 提示词模板
    tools: list[CrewStructuredTool] = []       # 结构化工具列表
    tools_names: str = ""                      # 工具名称列表（逗号分隔）
    tools_description: str = ""                # 工具描述文本
    tools_handler: ToolsHandler | None = None  # 工具调用处理器
    stop: list[str] = []                       # 停止词列表
    step_callback: SerializableCallable | None = None  # 每步回调
    original_tools: list[BaseTool] = []        # 原始工具（未结构化的）
    function_calling_llm: BaseLLM | str | None = None  # 函数调用专用 LLM
    respect_context_window: bool = False        # 是否尊重上下文窗口
    request_within_rpm_limit: Callable | None = None  # RPM 限流函数
    response_model: type[BaseModel] | None = None  # 结构化输出模型
    ask_for_human_input: bool = False           # 是否请求人工输入
    log_error_after: int = 3                    # 多少次错误后开始记录日志
    before_llm_call_hooks: list[Callable] = []  # LLM 调用前钩子
    after_llm_call_hooks: list[Callable] = []   # LLM 调用后钩子
```

#### 2.2.2 初始化逻辑

```python
def __init__(self, **kwargs) -> None:
    super().__init__(**kwargs)
    warnings.warn(
        "CrewAgentExecutor is deprecated...",
        DeprecationWarning,
        stacklevel=2,
    )
    # 自动注入全局 LLM 钩子
    if not self.before_llm_call_hooks:
        self.before_llm_call_hooks.extend(get_before_llm_call_hooks())
    if not self.after_llm_call_hooks:
        self.after_llm_call_hooks.extend(get_after_llm_call_hooks())
```

**设计亮点：** 钩子系统在初始化时自动从全局注册表中加载，无需手动配置，实现了「即插即用」的钩子注入。

---

### 2.3 第三层：Parser（LLM 输出解析器）

**文件：** `lib/crewai/src/crewai/agents/parser.py`

#### 2.3.1 数据结构

```python
@dataclass
class AgentAction:
    """Agent 要执行的工具调用"""
    thought: str             # 思考过程："我需要搜索天气信息"
    tool: str                # 工具名称："search"
    tool_input: str          # 工具输入："北京今天天气"
    text: str                # 原始 LLM 输出文本
    result: str | None = None  # 工具执行结果

@dataclass
class AgentFinish:
    """Agent 最终答案"""
    thought: str                  # 思考过程
    output: str | BaseModel       # 最终输出内容
    text: str                     # 原始 LLM 输出文本
```

#### 2.3.2 核心解析函数 `parse()`

```python
def parse(text: str) -> AgentAction | AgentFinish:
    """
    解析 LLM 输出文本，识别两种格式：
    
    格式1 — 工具调用（返回 AgentAction）：
        Thought: 需要搜索天气
        Action: search
        Action Input: 北京今天天气
    
    格式2 — 最终答案（返回 AgentFinish）：
        Thought: 已完成搜索
        Final Answer: 北京今天晴，25°C
    """
    thought = _extract_thought(text)           # 提取 Thought 部分
    includes_answer = FINAL_ANSWER_ACTION in text  # "Final Answer:" 在文本中
    action_match = ACTION_INPUT_REGEX.search(text) # 正则匹配 Action/Action Input

    if includes_answer:
        # 提取 Final Answer 后面的内容
        final_answer = text.split(FINAL_ANSWER_ACTION)[-1].strip()
        return AgentFinish(thought=thought, output=final_answer, text=text)

    if action_match:
        action = action_match.group(1)          # 工具名称
        action_input = action_match.group(2).strip()  # 工具参数
        safe_tool_input = _safe_repair_json(tool_input)  # JSON 修复
        return AgentAction(
            thought=thought, tool=action, tool_input=safe_tool_input, text=text
        )
    # 格式不匹配 → 抛出 OutputParserError
    raise OutputParserError("格式错误：缺少 Action 或 Action Input")
```

**正则常量定义（`constants.py`）：**

```python
ACTION_INPUT_REGEX = re.compile(
    r"Action\s*\d*\s*:\s*(.*?)\s*Action\s*\d*\s*Input\s*\d*\s*:\s*(.*)", re.DOTALL
)
# 匹配：Action: search  Action Input: 北京天气
# group(1) = "search", group(2) = "北京天气"

FINAL_ANSWER_ACTION: Final[str] = "Final Answer:"
```

#### 2.3.3 JSON 自动修复机制 `_safe_repair_json()`

```python
def _safe_repair_json(tool_input: str) -> str:
    """使用 json_repair 库自动修复 LLM 输出的不完美 JSON。"""
    if tool_input.startswith("[") and tool_input.endswith("]"):
        return tool_input  # 列表格式保持原样
    tool_input = tool_input.replace('"""', '"')  # 三重引号转换
    result = repair_json(tool_input)  # json_repair 库的修复函数
    if result in UNABLE_TO_REPAIR_JSON_RESULTS:  # ['""', '{}']
        return tool_input  # 无法修复则返回原样
    return str(result)
```

**面试高频考点：** LLM 输出的 JSON 常常格式不完美（缺少引号、多余逗号），`json_repair` 库是生产环境中的关键容错设计。

---

### 2.4 第四层：ToolsHandler（工具调用处理器）

**文件：** `lib/crewai/src/crewai/agents/tools_handler.py`

```python
class ToolsHandler(BaseModel):
    cache: CacheHandler | None = None           # 工具结果缓存
    last_used_tool: ToolCalling | None = None   # 最近使用的工具

    def on_tool_use(self, calling, output, should_cache=True):
        """工具执行完成后的回调，负责缓存结果。"""
        self.last_used_tool = calling
        if self.cache and should_cache and calling.tool_name != CacheTools().name:
            input_str = json.dumps(calling.arguments) if isinstance(calling.arguments, dict) else str(calling.arguments)
            self.cache.add(tool=calling.tool_name, input=input_str, output=output)
```

**CacheHandler（线程安全缓存）：**

```python
class CacheHandler(BaseModel):
    _cache: dict[str, Any] = PrivateAttr(default_factory=dict)
    _lock: RWLock = PrivateAttr(default_factory=RWLock)  # 读写锁

    def add(self, tool: str, input: str, output: Any) -> None:
        with self._lock.w_locked():           # 写锁（互斥）
            self._cache[f"{tool}-{input}"] = output

    def read(self, tool: str, input: str) -> Any | None:
        with self._lock.r_locked():           # 读锁（共享）
            return self._cache.get(f"{tool}-{input}")
```

**设计亮点：** 使用 `RWLock`（读写锁）而非普通锁，允许多个读操作并发执行，只有写操作互斥——这是高性能缓存的标准实现模式。

---

### 2.5 第五层：StepExecutor（Plan-and-Act 单步执行器）

**文件：** `lib/crewai/src/crewai/agents/step_executor.py`

> 这是 CrewAI 从 ReAct 模式进化到 Plan-and-Act 模式的关键组件。基于论文 [arxiv 2503.09572](https://arxiv.org/abs/2503.09572)。

#### 核心设计理念

```
传统 ReAct（CrewAgentExecutor）：
    LLM 调用 → 解析 → 执行工具 → 观察结果 → LLM 调用 → ...（循环直到 Final Answer）

Plan-and-Act（StepExecutor）：
    Planner 生成计划 → 对每个 Step 调用 StepExecutor
    StepExecutor: 单次 LLM 调用 → 执行工具 → 返回结果（无内部循环）
```

#### 关键代码

```python
class StepExecutor:
    def execute(self, todo, context, max_step_iterations=15, step_timeout=None):
        """
        执行单个 todo 项。
        - 不访问外部 AgentExecutor 状态
        - 独立的 messages 列表
        - 结果通过 StepResult 返回
        """
        enforce_rpm_limit(self.request_within_rpm_limit)
        messages = self._build_isolated_messages(todo, context)  # 构建独立消息

        if self._use_native_tools:
            result_text = self._execute_native(messages, ...)
        else:
            result_text = self._execute_text_parsed(messages, ...)

        return StepResult(success=True, result=result_text, ...)
```

**关键设计决策：**
- `StepExecutor` 拥有一套**完全独立**的消息列表，不读取也不写入 AgentExecutor 的状态
- 失败恢复由 `PlannerObserver` 和 `AgentExecutor` 负责，StepExecutor 本身「只管执行」
- 支持 `step_timeout` 超时控制，防止单个步骤卡死

---

## 3. 完整调用时序图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        CrewAgentExecutor.invoke()                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  1. 初始化                                                               │
│     ├── messages = [] (新对话) 或 _resuming (从检查点恢复)                │
│     ├── iterations = 0                                                   │
│     └── _setup_messages(inputs)  ← 格式化 System Prompt + User Prompt   │
│                                                                          │
│  2. 判断工具调用模式                                                      │
│     ├── LLM 支持 Native Function Calling?                                │
│     │   ├── YES → _invoke_loop_native_tools()                            │
│     │   └── NO  → _invoke_loop_react()                                   │
│     └── 无工具 → _invoke_loop_native_no_tools()                          │
│                                                                          │
│  3. ReAct 循环 (_invoke_loop_react)                                      │
│     ┌──────────────────────────────────────────────────────┐            │
│     │  while not AgentFinish:                               │            │
│     │    ├── 检查 max_iter 超限? → handle_max_iter          │            │
│     │    ├── 检查 RPM 限制? → enforce_rpm_limit             │            │
│     │    ├── 调用 LLM → get_llm_response(messages)          │            │
│     │    ├── 解析输出 → process_llm_response(answer)        │            │
│     │    │   ├── AgentAction? → 执行工具 → 结果回填 messages │            │
│     │    │   └── AgentFinish? → 跳出循环                    │            │
│     │    ├── 异常处理                                       │            │
│     │    │   ├── OutputParserError → 重试（格式修正提示）    │            │
│     │    │   ├── ContextLengthError → 上下文裁剪             │            │
│     │    │   └── UnknownError → 记录日志并抛出               │            │
│     │    └── iterations += 1                                │            │
│     └──────────────────────────────────────────────────────┘            │
│                                                                          │
│  4. Native Function Calling 循环 (_invoke_loop_native_tools)             │
│     ┌──────────────────────────────────────────────────────┐            │
│     │  while True:                                          │            │
│     │    ├── 检查 max_iter 超限                              │            │
│     │    ├── 调用 LLM (带 tools schema)                      │            │
│     │    ├── 返回是 tool_calls?                              │            │
│     │    │   ├── YES → _handle_native_tool_calls()           │            │
│     │    │   │   ├── 单工具? → 执行 → 结果回填 + 推理提示    │            │
│     │    │   │   └── 多工具? → ThreadPoolExecutor 并行执行   │            │
│     │    │   └── result_as_answer? → 直接返回 AgentFinish    │            │
│     │    └── 返回是文本? → 封装为 AgentFinish 返回            │            │
│     └──────────────────────────────────────────────────────┘            │
│                                                                          │
│  5. 后处理                                                               │
│     ├── _save_to_memory(formatted_answer) ← 写入记忆系统                 │
│     └── return {"output": formatted_answer.output}                       │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Native Tool Calls 并行执行时序

```
LLM 返回 3 个 tool_calls: [search, read_file, calculate]
    │
    ├── _handle_native_tool_calls()
    │   ├── 检查：是否有 result_as_answer 或 max_usage_count? 
    │   │   ├── YES → 改为串行执行（逐个处理）
    │   │   └── NO  → 构建并行执行计划
    │   │
    │   ├── _append_assistant_tool_calls_message()  ← 记录 assistant 消息
    │   │
    │   ├── ThreadPoolExecutor(max_workers=min(8, len(calls)))
    │   │   ├── Thread-1: _execute_single_native_tool_call(search)
    │   │   ├── Thread-2: _execute_single_native_tool_call(read_file)
    │   │   └── Thread-3: _execute_single_native_tool_call(calculate)
    │   │
    │   ├── as_completed() → 按完成顺序收集结果
    │   │
    │   └── _append_tool_result_and_check_finality()
    │       └── 检查 result_as_answer? → 是则直接返回 AgentFinish
    │
    └── 追加推理提示: "Please reflect on the tool results..."
```

---

## 4. 核心设计亮点

### 4.1 双模式架构（ReAct vs Native Function Calling）

| 维度 | ReAct 模式 | Native Function Calling 模式 |
|------|-----------|---------------------------|
| 工具定义方式 | 嵌入 Prompt 文本 | OpenAI 格式的 tools schema |
| 解析方式 | 正则解析 "Action: xxx" | 直接返回结构化 tool_calls |
| 适用场景 | 旧模型、不支持 function calling | GPT-4、Claude 等新模型 |
| 容错设计 | 正则匹配失败 → 重试提示 | 不支持 → 自动降级为 ReAct |

**自动降级代码：**

```python
except Exception as e:
    if is_native_tool_calling_unsupported_error(e):
        self._append_text_tool_calling_fallback_message()  # 追加文本工具说明
        return self._invoke_loop_react()  # 降级到 ReAct 模式
```

### 4.2 并行工具执行（ThreadPoolExecutor）

Native 模式下，LLM 可以一次返回多个 tool_calls，CrewAgentExecutor 使用 `ThreadPoolExecutor` 并行执行：

```python
max_workers = min(8, len(execution_plan))  # 最多 8 个并发线程
with ThreadPoolExecutor(max_workers=max_workers) as pool:
    futures = {
        pool.submit(
            contextvars.copy_context().run,  # 复制上下文变量
            self._execute_single_native_tool_call, ...
        ): idx
        for idx, (...) in enumerate(execution_plan)
    }
```

**面试重点：** `contextvars.copy_context().run` 确保每个线程有独立的上下文变量副本，避免线程间状态污染。

### 4.3 三层异常处理体系

```
Layer 1 — OutputParserError（输出格式错误）
    → 发送修正提示 → 重试 → 超过 log_error_after 次后记录日志

Layer 2 — ContextLengthError（上下文超长）
    → 裁剪消息历史 → 保留 system prompt + 最近 N 条消息

Layer 3 — UnknownError（未知错误）
    → 记录日志 → 重新抛出
```

### 4.4 钩子注入链

```
LLM 调用前钩子:  before_llm_call_hooks  → 修改 prompt、注入上下文
    ↓
LLM 调用
    ↓
LLM 调用后钩子:  after_llm_call_hooks   → 修改输出、注入额外信息
    ↓
工具调用前钩子:  before_tool_call_hooks → 可以阻止工具调用（返回 False）
    ↓
工具执行
    ↓
工具调用后钩子:  after_tool_call_hooks  → 修改工具结果
```

### 4.5 工业级内存优化

```python
# 缓存断点标记：利用 LLM 的 KV-Cache 实现跨轮次复用
self.messages.append(
    mark_cache_breakpoint(format_message_for_llm(system_prompt, role="system"))
)
self.messages.append(
    mark_cache_breakpoint(format_message_for_llm(user_prompt))
)
```

**大白话：** `mark_cache_breakpoint` 标记了 system prompt 和 user prompt 的边界，LLM 提供商会缓存这些前缀的 KV 值，后续 ReAct 循环中不再重复计算，节省 token 和延迟。

---

## 5. 生产落地拓展改造

### 5.1 持久化检查点（Checkpointer）

**现状：** `_resuming` 属性存在但未实现完整的断点续传。

**改造方案：**

```python
# 在每次迭代后保存状态
def _save_checkpoint(self):
    import json
    checkpoint = {
        "iterations": self.iterations,
        "messages": self.messages,
        "task_id": self.task.id if self.task else None,
    }
    self.crew.checkpointer.save(
        agent_id=self.agent.id, checkpoint=checkpoint
    )
```

### 5.2 工具调用超时控制

**现状：** 工具调用没有超时机制。

**改造方案：**

```python
from concurrent.futures import TimeoutError

def _execute_single_native_tool_call_with_timeout(self, ..., timeout=30):
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(self._execute_single_native_tool_call, ...)
        try:
            return future.result(timeout=timeout)
        except TimeoutError:
            return {"error": f"Tool {func_name} timed out after {timeout}s"}
```

### 5.3 工具调用重试策略

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def _execute_with_retry(self, func_name, func_args, available_functions):
    return available_functions[func_name](**(func_args or {}))
```

### 5.4 执行日志可观测性

**改造方案：** 在每个关键节点发送结构化日志事件。

```python
crewai_event_bus.emit(self, event=AgentExecutionStepEvent(
    agent_key=self.agent.key,
    iteration=self.iterations,
    action_type=type(formatted_answer).__name__,
    tool_name=getattr(formatted_answer, 'tool', None),
    timestamp=datetime.now(),
))
```

---

## 6. 面试深挖问题清单

| # | 问题 | 考察点 |
|---|------|--------|
| 1 | ReAct 模式和 Native Function Calling 模式的区别是什么？CrewAI 如何自动切换？ | 双模式架构、自动降级 |
| 2 | `AgentAction` 和 `AgentFinish` 的区别是什么？解析器如何区分？ | Parser 设计、正则解析 |
| 3 | CrewAI 如何防止 Agent 无限循环？ | max_iter 限制、迭代计数 |
| 4 | 当 LLM 输出格式错误时，CrewAI 如何处理？ | OutputParserError、容错设计 |
| 5 | Native 模式下多工具并行执行的实现原理是什么？ | ThreadPoolExecutor、contextvars |
| 6 | `mark_cache_breakpoint` 的作用是什么？ | LLM KV-Cache 优化 |
| 7 | StepExecutor 和 CrewAgentExecutor 的设计差异是什么？ | Plan-and-Act vs ReAct |
| 8 | 钩子系统如何在执行器中注入？初始化时还是运行时？ | 钩子注入时机、before/after 链 |
| 9 | `ToolsHandler.cache` 为什么使用读写锁？ | 并发安全、RWLock |
| 10 | 如果 LLM 不支持 Native Function Calling，CrewAI 如何降级？ | 异常捕获、降级策略 |

---

## 7. 简易可运行 Demo

```python
"""Demo: 手动模拟 CrewAgentExecutor 的核心执行流程"""
from crewai.agents.parser import parse, AgentAction, AgentFinish

# 模拟 LLM 返回的 ReAct 格式文本
llm_output_1 = """
Thought: 我需要搜索北京的天气信息
Action: search
Action Input: 北京今天天气
"""

llm_output_2 = """
Thought: 已经获取到天气信息
Final Answer: 北京今天晴，气温 25°C，适合出行
"""

# 解析第一轮输出
result_1 = parse(llm_output_1.strip())
print(f"类型: {type(result_1).__name__}")
print(f"思考: {result_1.thought}")
if isinstance(result_1, AgentAction):
    print(f"工具: {result_1.tool}")
    print(f"参数: {result_1.tool_input}")
    # 在真实场景中，这里会调用工具并获取结果

# 模拟工具执行结果
tool_result = "北京今天晴，气温 25°C"

# 解析第二轮输出
result_2 = parse(llm_output_2.strip())
print(f"\n类型: {type(result_2).__name__}")
if isinstance(result_2, AgentFinish):
    print(f"最终答案: {result_2.output}")

"""
输出:
类型: AgentAction
思考: 我需要搜索北京的天气信息
工具: search
参数: 北京今天天气

类型: AgentFinish
最终答案: 北京今天晴，气温 25°C，适合出行
"""
```

---

**下一阶段解析指令：**

```
# 当前解析目标
模块名称：Crew 调度引擎
对应源码文件路径：
- lib/crewai/src/crewai/crew.py（Crew 主类）
- lib/crewai/src/crewai/process.py（执行策略枚举）
- lib/crewai/src/crewai/crews/crew_output.py（Crew 输出封装）

# 本次输出硬性要求，缺一不可
1. 模块定位（一句话 + 架构位置 + 核心文件清单）
2. 源码分层拆解（文件→类→方法→关键代码行）
3. 完整调用时序图（Crew.kickoff() → Agent 执行 → 结果汇总）
4. 核心设计亮点（Sequential vs Hierarchical、Agent 路由、任务依赖图）
5. 生产落地拓展改造（持久化 Checkpointer、分布式执行）
6. 面试深挖问题清单（10 题）
7. 简易可运行 Demo 代码
```