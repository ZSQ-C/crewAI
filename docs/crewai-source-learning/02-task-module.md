# CrewAI 源码深度学习文档 — 阶段二：Task 任务调度模块

---

## 1. 模块定位

```
┌─────────────────────────────────────────────────────────────────┐
│                      CrewAI 架构全景                             │
├─────────────────────────────────────────────────────────────────┤
│                       Crew (调度层)                              │
│              ┌──────────────────────────────┐                    │
│              │  Process (sequential /       │                    │
│              │  hierarchical) 执行策略       │                    │
│              └──────────┬───────────────────┘                    │
│                         │ 调度 & 编排                            │
│              ┌──────────▼───────────────────┐                    │
│              │    ★ Task (任务描述层) ★      │  ← 本次解析模块    │
│              │  - 描述任务目标                │                    │
│              │  - 指定执行 Agent              │                    │
│              │  - 定义输出格式                │                    │
│              │  - 配置护栏校验                │                    │
│              │  - 管理上下文依赖              │                    │
│              └──────────┬───────────────────┘                    │
│                         │ 委托执行                              │
│              ┌──────────▼───────────────────┐                    │
│              │   Agent (执行层)              │                    │
│              │   execute_task(task, ...)      │                    │
│              └──────────────────────────────┘                    │
└─────────────────────────────────────────────────────────────────┘
```

**核心职责**：Task 是 CrewAI 中「任务描述」与「执行控制」的统一抽象。它同时承担两个角色：

| 角色 | 说明 |
|------|------|
| **声明式任务描述** | 用自然语言描述要做什么（`description`）、期望产出什么（`expected_output`） |
| **执行控制中心** | 指定 Agent、输出格式、护栏校验、上下文依赖、文件存储、回调等 |

**上下游依赖**：
- **上游**：Crew（调度 Task 列表）、Process（决定执行顺序）
- **下游**：Agent（`execute_task()` 实际执行）、TaskOutput（封装结果）
- **横向**：ConditionalTask（条件执行子类）、Guardrail（输出校验）

---

## 2. 源码分层拆解

### 2.1 文件结构一览

| 文件路径 | 核心内容 | 行数 |
|----------|----------|------|
| `lib/crewai/src/crewai/task.py` | Task 主类（Pydantic 模型） | ~1463 |
| `lib/crewai/src/crewai/tasks/task_output.py` | TaskOutput 结果封装类 | 104 |
| `lib/crewai/src/crewai/tasks/output_format.py` | OutputFormat 枚举（JSON/PYDANTIC/RAW） | 17 |
| `lib/crewai/src/crewai/tasks/conditional_task.py` | ConditionalTask 条件跳过子类 | 68 |
| `lib/crewai/src/crewai/tasks/llm_guardrail.py` | LLMGuardrail 基于 LLM 的输出校验 | 119 |
| `lib/crewai/src/crewai/tasks/hallucination_guardrail.py` | HallucinationGuardrail（开源版占位） | 103 |
| `lib/crewai/src/crewai/utilities/guardrail.py` | process_guardrail + GuardrailResult | 187 |
| `lib/crewai/src/crewai/utilities/guardrail_types.py` | 护栏类型别名 | 18 |

---

### 2.2 Task 类 — Pydantic 字段完整拆解

```python
# 文件: lib/crewai/src/crewai/task.py 第 117 行
class Task(BaseModel):
    model_config = {"arbitrary_types_allowed": True}
```

> **大白话**：Task 继承自 Pydantic 的 `BaseModel`，这意味着所有字段都有自动类型校验、序列化/反序列化能力。`arbitrary_types_allowed=True` 允许字段接受非标准 Pydantic 类型（如 `Callable`、`BaseTool` 等）。

#### 2.2.1 核心必填字段

| 字段名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `description` | `str` | 必填 | 任务描述，告诉 Agent 具体要做什么。支持 `{变量名}` 模板插值 |
| `expected_output` | `str` | 必填 | 期望输出的明确定义，指导 Agent 产出什么格式/内容 |

```python
# 源码 第 137-141 行
description: str = Field(description="Description of the actual task.")
expected_output: str = Field(
    description="Clear definition of expected output for the task."
)
```

**底层校验**（第 370-378 行）：通过 `model_validator(mode="after")` 在模型初始化后二次校验，两者不能为 `None`：

```python
@model_validator(mode="after")
def validate_required_fields(self) -> Self:
    if self.description is None:
        raise ValueError("description must be provided either directly or through config")
    if self.expected_output is None:
        raise ValueError("expected_output must be provided either directly or through config")
    return self
```

> **面试考点**：这里用了 `mode="after"` 而非 `mode="before"`。`before` 在字段校验前执行，`after` 在所有字段校验完成后执行。因为 `config` 中的值可能在 `mode="before"` 的 `process_model_config` 中被注入，所以 `after` 才能拿到最终值。

---

#### 2.2.2 Agent 关联字段

| 字段名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `agent` | `BaseAgent \| None` | `None` | 执行此任务的 Agent。使用 `BeforeValidator(_resolve_agent)` 支持延迟解析 |

```python
# 源码 第 149-152 行
agent: Annotated[
    BaseAgent | None,
    BeforeValidator(_resolve_agent),  # 允许传入字符串/role 后延迟解析为 Agent 实例
] = Field(description="Agent responsible for execution the task.", default=None)
```

> **`_resolve_agent` 的作用**：如果传入的是字符串（role 名），会自动查找 Crew 中匹配的 Agent。这是声明式配置的关键能力。

---

#### 2.2.3 上下文依赖字段（context）

| 字段名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `context` | `list[Task] \| None \| _NotSpecified` | `NOT_SPECIFIED` | 依赖的前置 Task 列表，其输出会作为本 Task 的上下文传入 |

```python
# 源码 第 153-156 行
context: list[Task] | None | _NotSpecified = Field(
    description="Other tasks that will have their output used as context for this task.",
    default=NOT_SPECIFIED,
)
```

> **`NOT_SPECIFIED` vs `None` 的区别**：`NOT_SPECIFIED` 是一个特殊哨兵值（`_NotSpecified` 类的单例），表示"用户没有设置此字段"。`None` 表示"用户明确设置为空"。这影响 `copy()` 方法的行为——哨兵值不会被复制。

---

#### 2.2.4 输出格式控制字段

| 字段名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `output_json` | `type[BaseModel] \| None` | `None` | 指定一个 Pydantic 模型类，强制输出为 JSON 字典 |
| `output_pydantic` | `type[BaseModel] \| None` | `None` | 指定一个 Pydantic 模型类，强制输出为 Pydantic 实例 |
| `response_model` | `type[BaseModel] \| None` | `None` | 使用 LLM 原生结构化输出能力（如 OpenAI 的 `response_format`） |
| `output_file` | `str \| None` | `None` | 输出文件路径，支持 `{变量}` 模板 |
| `create_directory` | `bool \| None` | `True` | 是否自动创建 `output_file` 所在目录 |
| `markdown` | `bool \| None` | `False` | 是否要求 Agent 以 Markdown 格式返回 |

```python
# 源码 第 157-192 行
output_json: Annotated[
    type[BaseModel] | None,
    BeforeValidator(_deserialize_model_class),  # 从字典反序列化为 Pydantic 模型
    PlainSerializer(_serialize_model_class, ...),  # 序列化为 JSON Schema
] = Field(description="A Pydantic model to be used to create a JSON output.", default=None)

output_pydantic: Annotated[
    type[BaseModel] | None,
    BeforeValidator(_deserialize_model_class),
    PlainSerializer(_serialize_model_class, ...),
] = Field(description="A Pydantic model to be used to create a Pydantic output.", default=None)
```

**互斥校验**（源码第 522-528 行）：

```python
@model_validator(mode="after")
def check_output(self) -> Self:
    """Check if an output type is set."""
    output_types = [self.output_json, self.output_pydantic]
    if len([type for type in output_types if type]) > 1:
        raise PydanticCustomError(
            "output_type",
            "Only one output type can be set, either output_pydantic or output_json.",
            {},
        )
    return self
```

> **面试考点**：`output_json` 和 `output_pydantic` 不能同时设置。`response_model` 是独立的——它使用 LLM 提供商的原生 JSON Mode（如 OpenAI 的 `response_format={"type": "json_schema"}`），性能更高但兼容性受限。

---

#### 2.2.5 护栏校验字段（Guardrail）

| 字段名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `guardrail` | `GuardrailType \| None` | `None` | 单个护栏：函数 或 字符串描述（自动转为 LLMGuardrail） |
| `guardrails` | `GuardrailsType \| None` | `None` | 多个护栏列表，可混用函数和字符串 |
| `guardrail_max_retries` | `int` | `3` | 护栏失败后最大重试次数 |
| `retry_count` | `int` | `0` | 当前重试计数 |
| `max_retries` | `int \| None` | `None` | **[已废弃]** 旧版重试参数，用 `guardrail_max_retries` 替代 |

**私有属性**（运行时赋值，不参与序列化）：

```python
# 源码 第 279-288 行
_guardrail: GuardrailCallable | None = PrivateAttr(default=None)      # 解析后的单个护栏函数
_guardrails: list[GuardrailCallable] = PrivateAttr(default_factory=list)  # 解析后的护栏函数列表
_guardrail_retry_counts: dict[int, int] = PrivateAttr(default_factory=dict)  # 每个护栏的独立重试计数
```

**护栏函数签名**（[guardrail_types.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/utilities/guardrail_types.py)）：

```python
GuardrailCallable: TypeAlias = Callable[
    [TaskOutput | LiteAgentOutput],  # 入参：任务输出
    tuple[bool, Any]                 # 返回：(是否通过, 通过时返回结果/失败时返回错误信息)
]
```

---

#### 2.2.6 其他控制字段

| 字段名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `async_execution` | `bool \| None` | `False` | 是否异步执行（Crew 中可并行调度） |
| `human_input` | `bool \| None` | `False` | 是否需要人类审核 Agent 的最终答案 |
| `tools` | `list[BaseTool] \| None` | `[]` | 该 Task 专用的工具列表（覆盖 Agent 默认工具） |
| `callback` | `SerializableCallable \| None` | `None` | 任务完成后的回调函数 |
| `config` | `dict[str, Any] \| None` | `None` | 任务级配置字典 |
| `id` | `UUID` | `uuid4()` | 不可变的唯一标识（`frozen=True`） |
| `name` | `str \| None` | `None` | 任务名称 |
| `input_files` | `dict[str, FileInput]` | `{}` | 命名输入文件 |
| `security_config` | `SecurityConfig` | `SecurityConfig()` | 安全配置（指纹等） |
| `allow_crewai_trigger_context` | `bool \| None` | `None` | 控制是否注入 `crewai_trigger_payload` |

---

### 2.3 Task 类 — 核心方法详解

#### 2.3.1 `execute_sync()` — 同步执行入口

```python
# 源码 第 572-578 行
def execute_sync(
    self,
    agent: BaseAgent | None = None,      # 可选覆盖默认 Agent
    context: str | None = None,           # 前置任务的上下文字符串
    tools: list[BaseTool] | None = None,  # 可选覆盖默认工具
) -> TaskOutput:
    """Execute the task synchronously."""
    self.start_time = datetime.datetime.now()  # 记录开始时间
    return self._execute_core(agent, context, tools)  # 委托核心方法
```

#### 2.3.2 `execute_async()` — 异步执行入口

```python
# 源码 第 596-608 行
def execute_async(
    self,
    agent: BaseAgent | None = None,
    context: str | None = None,
    tools: list[BaseTool] | None = None,
) -> Future[TaskOutput]:
    """Execute the task asynchronously."""
    future: Future[TaskOutput] = Future()  # 创建 Future 对象
    ctx = contextvars.copy_context()       # 复制上下文变量（线程安全）
    threading.Thread(                       # 在独立线程中执行
        daemon=True,
        target=ctx.run,
        args=(self._execute_task_async, agent, context, tools, future),
    ).start()
    return future  # 立即返回 Future，不阻塞
```

> **设计要点**：`contextvars.copy_context()` 确保新线程能访问当前上下文中的 `task_id` 等变量。`daemon=True` 保证主线程退出时子线程自动回收。

#### 2.3.3 `_execute_core()` — 同步核心执行引擎（最关键的方法）

```python
# 源码 第 762-860 行
def _execute_core(
    self,
    agent: BaseAgent | None,
    context: str | None,
    tools: list[Any] | None,
) -> TaskOutput:
```

**执行流程逐行解析**：

```
Step 1: 设置当前 Task ID 到上下文变量
─────────────────────────────────────────
task_id_token = set_current_task_id(str(self.id))
# 通过 contextvars 设置当前 Task ID，使下游代码（如日志、事件）能感知"当前正在执行哪个 Task"
# 返回一个 token，用于后续恢复

Step 2: 存储输入文件
────────────────────
self._store_input_files()
# 将 input_files 存入 file_store，供 Agent 工具调用

Step 3: 确定 Agent 并校验
─────────────────────────
agent = agent or self.agent         # 优先使用传入的 agent，否则用默认
self.agent = agent                   # 回写 self.agent（确保后续引用一致）
if not agent:
    raise Exception(
        f"The task '{self.description}' has no agent assigned..."
    )

Step 4: 设置上下文 & 工具
─────────────────────────
self.prompt_context = context        # 存前置任务上下文
tools = tools or self.tools or []    # 工具优先级：传入 > 任务级 > 空列表

Step 5: 记录已处理 Agent
────────────────────────
self.processed_by_agents.add(agent.role)
# 用于追踪哪些 Agent 处理过此任务（委托场景）

Step 6: 检查点恢复判断 & 事件发射
────────────────────────────────
executor = agent.agent_executor
if not (
    executor and executor._resuming and resume_task_scope(str(self.id))
):
    crewai_event_bus.emit(
        self, TaskStartedEvent(context=context, task=self)
    )
# 如果是从检查点恢复且该 Task 已在恢复范围内，跳过 TaskStarted 事件
# 避免重复事件干扰外部监听

Step 7: 委托 Agent 执行
───────────────────────
result = agent.execute_task(
    task=self,       # 传入自身的 Task 对象
    context=context, # 前置上下文
    tools=tools,     # 可用工具
)
# 这是核心调用！Agent 根据 Task 的 description/expected_output 生成 prompt 并执行

Step 8: 后置处理（钩子方法，子类可覆盖）
───────────────────────────────────────
self._post_agent_execution(agent)

Step 9: 结果格式解析
────────────────────
if isinstance(result, BaseModel):
    # Agent 直接返回了 Pydantic 模型（使用 response_model 时）
    raw = result.model_dump_json()
    if self.output_pydantic:
        pydantic_output = result
        json_output = None
    elif self.output_json:
        pydantic_output = None
        json_output = result.model_dump()
    else:
        pydantic_output = None
        json_output = None
elif not self._guardrails and not self._guardrail:
    # 无护栏：直接导出结构化输出
    raw = result
    pydantic_output, json_output = self._export_output(result)
else:
    # 有护栏：先保留原始字符串，护栏校验后再导出
    raw = result
    pydantic_output, json_output = None, None

Step 10: 封装 TaskOutput
────────────────────────
task_output = TaskOutput(
    name=self.name or self.description,
    description=self.description,
    expected_output=self.expected_output,
    raw=raw,
    pydantic=pydantic_output,
    json_dict=json_output,
    agent=agent.role,
    output_format=self._get_output_format(),
    messages=agent.last_messages,
)

Step 11: 护栏校验循环
─────────────────────
if self._guardrails:
    for idx, guardrail in enumerate(self._guardrails):
        task_output = self._invoke_guardrail_function(
            task_output=task_output,
            agent=agent,
            tools=tools,
            guardrail=guardrail,
            guardrail_index=idx,
        )
if self._guardrail:
    task_output = self._invoke_guardrail_function(
        task_output=task_output,
        agent=agent,
        tools=tools,
        guardrail=self._guardrail,
    )
# 每个护栏校验失败 → 重试（Agent 重新执行）→ 再次校验，直到通过或超过 max_retries

Step 12: 保存结果 & 回调
────────────────────────
self.output = task_output
self.end_time = datetime.datetime.now()

if self.callback:
    cb_result = self.callback(self.output)
    if inspect.iscoroutine(cb_result):
        asyncio.run(cb_result)  # 支持异步回调

# Crew 级别的 task_callback（全局回调，不重复触发）
crew = self.agent.crew
if (
    crew
    and not isinstance(crew, str)
    and crew.task_callback
    and crew.task_callback != self.callback  # 避免重复
):
    cb_result = crew.task_callback(self.output)
    if inspect.iscoroutine(cb_result):
        asyncio.run(cb_result)

Step 13: 文件输出
─────────────────
if self.output_file:
    content = (
        json_output
        if json_output
        else (pydantic_output.model_dump_json() if pydantic_output else result)
    )
    self._save_file(content)

Step 14: 完成事件 & 异常处理
────────────────────────────
crewai_event_bus.emit(
    self, TaskCompletedEvent(output=task_output, task=self)
)
return task_output

except Exception as e:
    self.end_time = datetime.datetime.now()
    crewai_event_bus.emit(self, TaskFailedEvent(error=str(e), task=self))
    raise e
finally:
    clear_task_files(self.id)          # 清理临时文件
    reset_current_task_id(task_id_token)  # 恢复上下文变量
```

---

#### 2.3.4 `prompt()` — 生成任务提示词

```python
# 源码 第 890-980 行
def prompt(self) -> str:
```

**拼接逻辑**：

```
description
  + (可选) Trigger Payload 注入
  + (可选) 输入文件列表
  + expected_output 格式化
  + (可选) Markdown 格式化指令
= 最终 prompt
```

```python
# 核心拼接代码
tasks_slices = [description]
output = I18N_DEFAULT.slice("expected_output").format(
    expected_output=self.expected_output
)
tasks_slices = [description, output]

if self.markdown:
    markdown_instruction = """Your final answer MUST be formatted in Markdown syntax.
Follow these guidelines:
- Use # for headers
- Use ** for bold text
..."""
    tasks_slices.append(markdown_instruction)
return "\n".join(tasks_slices)
```

> **设计意图**：`prompt()` 只负责生成文本，不涉及执行。Agent 在执行时会调用 `task.prompt()` 获取完整的任务描述。

---

#### 2.3.5 `interpolate_inputs_and_add_conversation_history()` — 模板插值

```python
# 源码 第 982-1058 行
def interpolate_inputs_and_add_conversation_history(
    self, inputs: dict[str, str | int | float | dict[str, Any] | list[Any]]
) -> None:
```

**执行流程**：

```
1. 保存原始值（用于后续重新插值）
   _original_description = self.description
   _original_expected_output = self.expected_output
   _original_output_file = self.output_file

2. 对 description 进行模板插值
   self.description = interpolate_only(
       input_string=self._original_description, inputs=inputs
   )
   # 将 {variable_name} 替换为 inputs 中的值

3. 对 description 进行内容处理
   self.description = process_content(self.description, {"task": self})
   # process_content 处理 CrewAI 特有的内容标记（如 crewai 指令）

4. 对 expected_output 进行模板插值
   self.expected_output = interpolate_only(
       input_string=self._original_expected_output, inputs=inputs
   )

5. 对 output_file 路径进行模板插值
   self.output_file = interpolate_only(
       input_string=self._original_output_file, inputs=inputs
   )

6. 注入对话历史（如果存在）
   if inputs.get("crew_chat_messages"):
       # 解析 JSON 格式的聊天消息
       # 追加到 description 末尾
       self.description += f"\n\n{conversation_instruction}\n\n{conversation_history}"
```

> **面试考点**：`interpolate_only` 仅替换 `{var}` 模板，不处理 `{{` 转义。`process_content` 是 CrewAI 特有的内容预处理管道。

---

#### 2.3.6 `_invoke_guardrail_function()` — 护栏重试循环

```python
# 源码 第 1318-1400 行
def _invoke_guardrail_function(
    self,
    task_output: TaskOutput,
    agent: BaseAgent,
    tools: list[BaseTool],
    guardrail: GuardrailCallable | None,
    guardrail_index: int | None = None,  # 多护栏时用于独立计数
) -> TaskOutput:
```

**执行流程**：

```
max_attempts = guardrail_max_retries + 1  # 默认 4 次机会

for attempt in range(max_attempts):
    ┌─ 调用 process_guardrail(output, guardrail, retry_count, ...)
    │   └─ 发射 LLMGuardrailStartedEvent
    │   └─ 执行 guardrail(output) → (bool, Any)
    │   └─ 发射 LLMGuardrailCompletedEvent
    │
    ├─ 如果 success == True:
    │   ├─ 如果 result 是字符串 → 更新 task_output.raw + 重新导出结构化输出
    │   ├─ 如果 result 是 TaskOutput → 直接替换
    │   └─ return task_output  ← 校验通过！
    │
    ├─ 如果 attempt >= guardrail_max_retries（已达上限）:
    │   └─ raise Exception("Task failed guardrail validation after N retries")
    │
    └─ 未通过且未达上限:
        ├─ retry_count += 1（独立计数）
        ├─ 构造错误上下文 → agent.execute_task(task, context=error_context, tools)
        │   └─ Agent 被要求根据错误信息修正输出
        ├─ 重新封装 TaskOutput
        └─ 进入下一轮循环
```

> **关键设计**：多护栏场景下，每个护栏有独立的 `_guardrail_retry_counts[guardrail_index]` 计数，互不干扰。

---

#### 2.3.7 `copy()` — 深拷贝机制

```python
# 源码 第 1070-1108 行
def copy(self, agents: Sequence[BaseAgent], task_mapping: dict[str, Task]) -> Task:
```

**用途**：在 Crew 执行前，对 Task 列表进行深拷贝，避免原始对象被修改。这在多 Crew 复用同一 Task 定义时尤其重要。

**拷贝策略**：
- `id`、`agent`、`context`、`tools` 等字段不直接复制，而是通过 `task_mapping` 和 Agent 列表重新映射
- `context` 中的 Task 引用通过 `task_mapping` 查找对应的拷贝
- 保持了原始 Task 的类类型（`self.__class__`），使 `ConditionalTask` 子类也能正确拷贝

---

### 2.4 TaskOutput 类 — 结果封装

```python
# 文件: lib/crewai/src/crewai/tasks/task_output.py
class TaskOutput(BaseModel):
    description: str                              # 任务描述
    name: str | None = None                       # 任务名称
    expected_output: str | None = None             # 期望输出
    summary: str | None = None                    # 自动摘要（前10个词的描述）
    raw: str = ""                                 # 原始输出字符串
    pydantic: BaseModel | None = None             # Pydantic 结构化输出
    json_dict: dict[str, Any] | None = None       # JSON 字典输出
    agent: str                                    # 执行 Agent 的 role
    output_format: OutputFormat = OutputFormat.RAW # 输出格式标记
    messages: list[LLMMessage] = []               # Agent 对话消息历史
```

**关键方法**：

| 方法 | 返回值 | 说明 |
|------|--------|------|
| `set_summary()` | `TaskOutput` | `model_validator` 自动从 `description` 前 10 个词生成摘要 |
| `json` (property) | `str \| None` | 仅当 `output_format == JSON` 时返回 `json.dumps(json_dict)` |
| `to_dict()` | `dict` | 优先返回 `json_dict`，否则返回 `pydantic.model_dump()` |
| `__str__()` | `str` | 优先级：`pydantic` > `json_dict` > `raw` |

---

### 2.5 OutputFormat 枚举

```python
# 文件: lib/crewai/src/crewai/tasks/output_format.py
class OutputFormat(str, Enum):
    JSON = "json"          # 输出为 JSON 字典
    PYDANTIC = "pydantic"  # 输出为 Pydantic 模型实例
    RAW = "raw"            # 输出为原始字符串
```

**判定逻辑**（`_get_output_format()`）：

```python
def _get_output_format(self) -> OutputFormat:
    if self.output_json:
        return OutputFormat.JSON
    if self.output_pydantic:
        return OutputFormat.PYDANTIC
    return OutputFormat.RAW
```

---

### 2.6 ConditionalTask — 条件执行子类

```python
# 文件: lib/crewai/src/crewai/tasks/conditional_task.py
class ConditionalTask(Task):
    condition: SerializableCallable | None = Field(
        default=None,
        description="Function that determines whether the task should be executed..."
    )
```

**核心方法**：

```python
def should_execute(self, context: TaskOutput) -> bool:
    """根据前置任务输出判断是否执行"""
    if self.condition is None:
        raise ValueError("No condition function set for conditional task")
    return bool(self.condition(context))

def get_skipped_task_output(self) -> TaskOutput:
    """当任务被跳过时，生成一个空的 TaskOutput"""
    return TaskOutput(
        description=self.description,
        raw="",
        agent=self.agent.role if self.agent else "",
        output_format=OutputFormat.RAW,
    )
```

**使用约束**：
- 不能是 Crew 中唯一的 Task
- 不能是第一个 Task（需要前置任务提供上下文）

---

### 2.7 LLMGuardrail — 基于 LLM 的护栏校验

```python
# 文件: lib/crewai/src/crewai/tasks/llm_guardrail.py
class LLMGuardrail:
    def __init__(self, description: str, llm: BaseLLM):
        self.description = description  # 护栏规则的自然语言描述
        self.llm = llm                  # 用于校验的 LLM 实例

    def __call__(self, task_output: TaskOutput) -> tuple[bool, Any]:
```

**执行流程**：

```
1. 创建一个内部 Agent（"Guardrail Agent"）
   role="Guardrail Agent"
   goal="Validate the output of the task"
   backstory="You are a expert at validating..."

2. 构造校验 prompt:
   - 包含 task_output.raw（任务输出）
   - 包含 self.description（护栏规则描述）
   - 要求输出 LLMGuardrailResult（valid: bool, feedback: str）

3. 调用 agent.kickoff(query, response_format=LLMGuardrailResult)
   └─ 使用 LLM 原生结构化输出

4. 解析结果:
   if result.pydantic.valid:
       return True, task_output.raw
   else:
       return False, result.pydantic.feedback
```

> **面试亮点**：`LLMGuardrail` 实现了 `__call__`，使其可以作为 `GuardrailCallable` 传入。它内部使用 `response_format` 实现结构化输出，而非正则解析。

---

### 2.8 HallucinationGuardrail — 幻觉检测（开源版占位）

```python
# 文件: lib/crewai/src/crewai/tasks/hallucination_guardrail.py
class HallucinationGuardrail:
    def __call__(self, task_output: TaskOutput) -> tuple[bool, Any]:
        if callable(_validate_output_hook):
            return _validate_output_hook(self, task_output)
        # 开源版：永远返回 True（跳过检测）
        self._logger.log("warning", "Premium hallucination detection skipped...")
        return True, task_output.raw
```

> **设计模式**：通过 `_validate_output_hook` 全局钩子，允许商业版注入真实的幻觉检测逻辑，开源版保持接口兼容。

---

### 2.9 GuardrailResult — 护栏结果标准化

```python
# 文件: lib/crewai/src/crewai/utilities/guardrail.py
class GuardrailResult(BaseModel):
    success: bool                                # 是否通过
    result: Any | None = None                    # 通过时的结果
    error: str | None = None                     # 失败时的错误信息

    @classmethod
    def from_tuple(cls, result: tuple[bool, Any | str]) -> Self:
        """从 (bool, Any) 元组创建 GuardrailResult"""
        success, data = result
        return cls(
            success=success,
            result=data if success else None,
            error=data if not success else None,
        )
```

**互斥校验**：`result` 和 `error` 不能同时有值——`success=True` 时 `error` 必须为空，反之亦然。

---

## 3. 完整调用时序

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  Crew    │     │  Task    │     │  Agent   │     │ Guardrail│     │  Event   │
│(调度层)  │     │(任务层)  │     │(执行层)  │     │(校验层)  │     │  Bus     │
└────┬─────┘     └────┬─────┘     └────┬─────┘     └────┬─────┘     └────┬─────┘
     │                 │               │                 │                 │
     │  1. kickoff()   │               │                 │                 │
     │────────────────►│               │                 │                 │
     │                 │               │                 │                 │
     │                 │ 2. copy() + interpolate()       │                 │
     │                 │────┐          │                 │                 │
     │                 │    │ 深拷贝   │                 │                 │
     │                 │◄───┘          │                 │                 │
     │                 │               │                 │                 │
     │  3. execute_sync(agent, context, tools)           │                 │
     │────────────────►│               │                 │                 │
     │                 │               │                 │                 │
     │                 │ 4. TaskStartedEvent             │                 │
     │                 │──────────────────────────────────────────────────►│
     │                 │               │                 │                 │
     │                 │ 5. execute_task(task, context, tools)             │
     │                 │──────────────►│                 │                 │
     │                 │               │                 │                 │
     │                 │               │ 6. prompt()     │                 │
     │                 │◄──────────────│                 │                 │
     │                 │               │                 │                 │
     │                 │               │ 7. LLM 调用     │                 │
     │                 │               │────┐            │                 │
     │                 │               │    │ 推理       │                 │
     │                 │               │◄───┘            │                 │
     │                 │               │                 │                 │
     │                 │  8. result    │                 │                 │
     │                 │◄──────────────│                 │                 │
     │                 │               │                 │                 │
     │                 │ 9. 封装 TaskOutput              │                 │
     │                 │────┐          │                 │                 │
     │                 │    │ raw +    │                 │                 │
     │                 │    │ pydantic │                 │                 │
     │                 │    │ + json   │                 │                 │
     │                 │◄───┘          │                 │                 │
     │                 │               │                 │                 │
     │                 │ 10. Guardrail 循环 (如有)       │                 │
     │                 │──────────────────────────────►│                 │
     │                 │               │                 │                 │
     │                 │               │    11a. 校验通过                 │
     │                 │◄──────────────────────────────│                 │
     │                 │               │                 │                 │
     │                 │               │    11b. 校验失败 → 重试          │
     │                 │◄──────────────────────────────│                 │
     │                 │               │                 │                 │
     │                 │ 12. agent.execute_task(error_context)            │
     │                 │──────────────►│                 │                 │
     │                 │               │                 │                 │
     │                 │    (循环直到通过或超限)         │                 │
     │                 │               │                 │                 │
     │                 │ 13. callback(self.output)      │                 │
     │                 │────┐          │                 │                 │
     │                 │◄───┘          │                 │                 │
     │                 │               │                 │                 │
     │                 │ 14. _save_file() (如有)        │                 │
     │                 │────┐          │                 │                 │
     │                 │◄───┘          │                 │                 │
     │                 │               │                 │                 │
     │                 │ 15. TaskCompletedEvent          │                 │
     │                 │──────────────────────────────────────────────────►│
     │                 │               │                 │                 │
     │  16. TaskOutput │               │                 │                 │
     │◄────────────────│               │                 │                 │
     │                 │               │                 │                 │
```

---

## 4. 核心设计亮点（可写进简历）

### 4.1 Pydantic 声明式任务定义

**简历话术**：基于 Pydantic v2 实现声明式 Task 定义，利用 `model_validator`/`field_validator` 实现多层校验链（配置注入→必填校验→工具继承→输出互斥→护栏解析），支持运行时类型安全与 JSON 序列化/反序列化。

### 4.2 双模式护栏架构（函数式 + LLM 驱动）

**简历话术**：设计双模式护栏系统——支持自定义 Python 函数护栏和自然语言描述驱动 LLM 护栏，配合独立重试计数与事件总线通知，实现输出质量闭环校验。

### 4.3 Context 依赖传递与条件跳过

**简历话术**：实现声明式 Task 间上下文依赖（`context: list[Task]`），支持 `ConditionalTask` 基于前置输出动态决定是否执行，配合 `NOT_SPECIFIED` 哨兵值实现精确的未设置 vs 显式空值区分。

### 4.4 多输出格式与自动转换

**简历话术**：统一 TaskOutput 模型支持 RAW/JSON/PYDANTIC 三种输出格式，通过 `Converter` 管道自动将 LLM 自然语言输出转换为 Pydantic 模型实例或 JSON 字典。

### 4.5 事件驱动架构

**简历话术**：基于 EventBus 实现 Task 生命周期事件（TaskStarted/TaskCompleted/TaskFailed），支持同步/异步回调链，与检查点恢复机制无缝集成。

---

## 5. 生产落地拓展改造

### 5.1 自定义 Task 输出处理器

```python
# 场景：需要在 Task 完成后自动将结果写入数据库
from crewai import Task, TaskOutput
from crewai.tasks.output_format import OutputFormat

class DatabasePersistTask(Task):
    """扩展 Task，自动将结果持久化到数据库"""

    def _post_agent_execution(self, agent):
        """重写钩子方法，在 Agent 执行后、护栏校验前触发"""
        if hasattr(self, 'output') and self.output:
            self._log_to_monitoring(self.output)

    def _save_file(self, result):
        """重写文件保存，同时写入数据库"""
        super()._save_file(result)
        import sqlite3
        conn = sqlite3.connect("task_outputs.db")
        conn.execute(
            "INSERT INTO outputs (task_id, result) VALUES (?, ?)",
            (str(self.id), str(result))
        )
        conn.commit()
```

### 5.2 LLM 护栏集成（生产级）

```python
from crewai import Task, Agent
from crewai.tasks.llm_guardrail import LLMGuardrail

# 方案1：字符串描述模式（自动创建 LLMGuardrail）
task = Task(
    description="分析用户评论的情感倾向",
    expected_output="返回 JSON: {sentiment: 'positive'|'negative'|'neutral', score: 0-1}",
    agent=agent,
    output_json=SentimentOutput,
    guardrail="输出必须包含 sentiment 和 score 两个字段，且 score 必须在 0-1 之间",
    guardrail_max_retries=2,
)

# 方案2：自定义函数护栏（更精确的控制）
def validate_sentiment(task_output: TaskOutput) -> tuple[bool, any]:
    import json
    try:
        data = json.loads(task_output.raw)
        if "sentiment" not in data or "score" not in data:
            return False, "缺少 sentiment 或 score 字段"
        if data["sentiment"] not in ("positive", "negative", "neutral"):
            return False, f"非法的 sentiment 值: {data['sentiment']}"
        if not 0 <= data["score"] <= 1:
            return False, f"score 超出范围: {data['score']}"
        return True, task_output.raw
    except json.JSONDecodeError:
        return False, "输出不是有效的 JSON"

task = Task(
    description="分析用户评论的情感倾向",
    expected_output="返回 JSON: {sentiment: 'positive'|'negative'|'neutral', score: 0-1}",
    agent=agent,
    guardrail=validate_sentiment,  # 直接传入函数
)
```

### 5.3 JSON Schema 结构化输出（生产级）

```python
from pydantic import BaseModel, Field
from typing import Literal
from crewai import Task

class SentimentOutput(BaseModel):
    sentiment: Literal["positive", "negative", "neutral"] = Field(
        description="情感分类结果"
    )
    score: float = Field(description="置信度分数 0-1", ge=0, le=1)
    keywords: list[str] = Field(description="关键情感词", default_factory=list)

# 使用 response_model（LLM 原生结构化输出，性能最优）
task = Task(
    description="分析以下评论的情感倾向: {comment}",
    expected_output="结构化的情感分析结果",
    agent=agent,
    response_model=SentimentOutput,  # 使用 OpenAI 原生 JSON Schema
)
```

### 5.4 工程化优化点清单

| 优化项 | 当前状态 | 生产建议 |
|--------|----------|----------|
| 结果持久化 | 仅文件写入 | 集成数据库 + 对象存储（S3/MinIO） |
| 护栏重试 | 同步 inline 重试 | 提取为独立的 RetryPolicy 配置，支持指数退避 |
| 输出校验 | Pydantic 校验 | 增加 JSON Schema 版本管理，支持 schema 演进 |
| 任务幂等 | 无内置支持 | 基于 `task.id` + `key`(MD5) 实现幂等执行 |
| 超时控制 | 无 | 为 `execute_sync` 增加 `timeout` 参数，使用 `concurrent.futures` 包装 |
| 监控埋点 | EventBus 事件 | 接入 Prometheus + Grafana，记录每个 Task 的执行耗时/重试次数 |

---

## 6. 面试深挖问题清单

### Q1: `output_json` 和 `output_pydantic` 有什么区别？能同时设置吗？

**标准答案**：不能同时设置，源码中 `check_output` 校验器会抛出 `PydanticCustomError`。区别在于：
- `output_json`：最终输出为 `dict[str, Any]`，`TaskOutput.json_dict` 有值
- `output_pydantic`：最终输出为 `BaseModel` 实例，`TaskOutput.pydantic` 有值
- `response_model`：使用 LLM 提供商的原生 JSON Mode（如 OpenAI 的 `response_format`），Agent 直接返回 Pydantic 实例，性能更好但依赖提供商支持

### Q2: `NOT_SPECIFIED` 哨兵值的设计目的是什么？

**标准答案**：区分"用户未设置"和"用户显式设为 None"。在 `copy()` 方法中，`NOT_SPECIFIED` 不会被复制，`None` 会被复制。这确保了 `context` 字段的语义正确性——如果用户没设置 `context`，拷贝后保持未设置状态；如果用户显式设为 `None`，拷贝后也是 `None`。

### Q3: 护栏重试时发生了什么？

**标准答案**：护栏校验失败后，Task 使用 `I18N_DEFAULT.errors("validation_error")` 构造错误上下文，然后调用 `agent.execute_task(task, context=error_context, tools)` 让 Agent 重新执行。Agent 会在 prompt 中看到上次的输出和护栏的错误反馈，从而修正输出。每个护栏有独立的 `_guardrail_retry_counts` 计数。

### Q4: `_execute_core` 和 `_aexecute_core` 的区别是什么？

**标准答案**：`_execute_core` 同步执行，`_aexecute_core` 使用 `async/await` 异步执行。两者的核心逻辑完全一致，但异步版本调用 `agent.aexecute_task()` 和 `await self._aexport_output()`。异步版本适用于 FastAPI 等异步 Web 框架中的集成。

### Q5: `context` 字段如何影响 Task 执行？

**标准答案**：`context` 是 `list[Task]` 类型，表示当前 Task 依赖的前置 Task。Crew 在执行时，会先执行 `context` 中的 Task，将其输出拼接为上下文字符串，作为 `context` 参数传入 `execute_sync()`，最终传给 Agent 的 `execute_task()`。Agent 会将这个上下文注入到 prompt 中。

### Q6: `copy()` 方法为什么需要 `task_mapping`？

**标准答案**：因为 `context` 中引用了其他 Task 对象。当 Crew 复制整个 Task 列表时，需要确保 `context` 中的引用指向的是拷贝后的新 Task 对象，而不是原始对象。`task_mapping` 维护了原始 Task key → 拷贝 Task 的映射关系。

### Q7: `_deny_user_set_id` 校验器的作用是什么？

**标准答案**：防止用户手动设置 `id` 字段。`id` 字段有 `frozen=True` 和 `default_factory=uuid.uuid4`，但仍可通过 `model_validate` 的 `context` 参数绕过。此校验器检查 `info.context` 中是否有 `from_checkpoint` 标记——只有从检查点恢复时才允许设置 `id`，否则抛出 `PydanticCustomError`。

### Q8: `process_guardrail` 函数为什么要发射两个事件？

**标准答案**：`LLMGuardrailStartedEvent` 和 `LLMGuardrailCompletedEvent` 提供护栏执行的可观测性。外部监听器可以基于这些事件实现：
- 护栏执行耗时监控
- 护栏失败率统计
- 护栏重试次数追踪
- 实时告警（护栏失败超阈值）

---

## 7. 简易可运行 Demo 代码

```python
"""
Task 模块完整 Demo
演示：context 依赖、output_json 结构化输出、guardrail 护栏、ConditionalTask 条件跳过
"""

from pydantic import BaseModel, Field
from typing import Literal
from crewai import Agent, Task, Crew, Process
from crewai.tasks.conditional_task import ConditionalTask
from crewai.tasks.task_output import TaskOutput

# ═══════════════════════════════════════════════════════════════
# 1. 定义 Pydantic 输出模型（用于 output_json）
# ═══════════════════════════════════════════════════════════════
class SentimentResult(BaseModel):
    """情感分析结果的结构化定义"""
    sentiment: Literal["positive", "negative", "neutral"] = Field(
        description="情感分类：positive/negative/neutral"
    )
    score: float = Field(
        description="置信度分数 0.0-1.0", ge=0.0, le=1.0
    )
    keywords: list[str] = Field(
        description="关键情感词列表", default_factory=list
    )


# ═══════════════════════════════════════════════════════════════
# 2. 创建 Agent
# ═══════════════════════════════════════════════════════════════
analyst = Agent(
    role="情感分析师",
    goal="准确分析文本的情感倾向",
    backstory="你是一位经验丰富的情感分析专家，擅长从文本中提取情感信号。",
    verbose=True,
)

summarizer = Agent(
    role="总结专家",
    goal="将分析结果总结为简洁的摘要",
    backstory="你擅长将复杂分析报告浓缩为一句话总结。",
    verbose=True,
)


# ═══════════════════════════════════════════════════════════════
# 3. 定义民用护栏函数（用于 guardrail）
# ═══════════════════════════════════════════════════════════════
def validate_sentiment_output(task_output: TaskOutput) -> tuple[bool, any]:
    """
    护栏函数签名：(TaskOutput) -> tuple[bool, Any]
    - 返回 (True, result)：校验通过，result 为通过后的输出
    - 返回 (False, error_msg)：校验失败，error_msg 为错误描述
    """
    import json
    try:
        data = json.loads(task_output.raw)
        # 检查必填字段
        if "sentiment" not in data or "score" not in data:
            return False, "输出缺少 sentiment 或 score 字段，请补充完整"
        # 检查 sentiment 枚举值
        if data["sentiment"] not in ("positive", "negative", "neutral"):
            return False, (
                f"sentiment 值 '{data['sentiment']}' 无效，"
                f"必须为 positive/negative/neutral 之一"
            )
        # 检查 score 范围
        if not 0.0 <= data["score"] <= 1.0:
            return False, (
                f"score 值 {data['score']} 超出范围，必须在 0.0-1.0 之间"
            )
        return True, task_output.raw
    except json.JSONDecodeError:
        return False, "输出不是有效的 JSON 格式，请确保返回合法的 JSON"


# ═══════════════════════════════════════════════════════════════
# 4. 定义 Task（展示 context 依赖 + output_json + guardrail）
# ═══════════════════════════════════════════════════════════════
task_analyze = Task(
    description="分析以下文本的情感倾向：{text}",
    expected_output=(
        "返回 JSON 格式，包含 sentiment（positive/negative/neutral）"
        "和 score（0.0-1.0 置信度）"
    ),
    agent=analyst,
    output_json=SentimentResult,  # ← 结构化输出
    guardrail=validate_sentiment_output,  # ← 自定义护栏
    guardrail_max_retries=2,  # ← 护栏失败最多重试 2 次
)

# ═══════════════════════════════════════════════════════════════
# 5. 定义依赖 Task（展示 context 依赖）
# ═══════════════════════════════════════════════════════════════
task_summarize = Task(
    description=(
        "基于前面的情感分析结果，用一句话总结分析结论。"
        "请说明文本的情感倾向和置信度。"
    ),
    expected_output="一句话总结，包含情感倾向和置信度",
    agent=summarizer,
    context=[task_analyze],  # ← context 依赖：等 task_analyze 完成后取其输出
)

# ═══════════════════════════════════════════════════════════════
# 6. 定义 ConditionalTask（展示条件跳过）
# ═══════════════════════════════════════════════════════════════
def should_alert(context: TaskOutput) -> bool:
    """
    条件函数：如果情感分析结果是 negative 且 score > 0.8，则触发告警
    """
    if context.json_dict:
        return (
            context.json_dict.get("sentiment") == "negative"
            and context.json_dict.get("score", 0) > 0.8
        )
    return False


task_alert = ConditionalTask(
    description="检测到极度负面情绪，请生成告警报告",
    expected_output="告警报告：包含原始文本摘要、负面关键词、建议处理措施",
    agent=analyst,
    condition=should_alert,  # ← 条件函数
    context=[task_analyze],  # ← 依赖 task_analyze 的输出
)


# ═══════════════════════════════════════════════════════════════
# 7. 创建 Crew 并执行
# ═══════════════════════════════════════════════════════════════
def main():
    crew = Crew(
        agents=[analyst, summarizer],
        tasks=[task_analyze, task_summarize, task_alert],
        process=Process.sequential,
        verbose=True,
    )

    # 执行：传入模板变量 {text}
    result = crew.kickoff(inputs={
        "text": "这个产品太差了，完全不值这个价格，非常失望！"
    })

    print("\n" + "=" * 60)
    print("执行结果：")
    print("=" * 60)
    print(result)

    # 查看每个 Task 的输出
    print("\n" + "=" * 60)
    print("各 Task 输出详情：")
    print("=" * 60)
    for task in [task_analyze, task_summarize, task_alert]:
        if task.output:
            print(f"\n[{task.description[:30]}...]")
            print(f"  raw: {task.output.raw[:100]}")
            print(f"  json_dict: {task.output.json_dict}")
            print(f"  output_format: {task.output.output_format}")


if __name__ == "__main__":
    main()
```

---

> **文档生成时间**：2026-07-14
> **对应源码版本**：CrewAI 最新稳定版