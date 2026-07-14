# 阶段 B：tasks/ — Task 任务模块实现逻辑详解

## 1. 模块定位与架构图

### 1.1 模块定位

`tasks/` 模块是 CrewAI 框架中 **任务定义、执行与输出管理** 的核心模块。它负责：

- 定义任务的描述、期望输出、执行 Agent 等元信息（`Task` 类）
- 支持条件任务执行（`ConditionalTask`）
- 提供 LLM 驱动的输出护栏校验与重试（`LLMGuardrail`）
- 定义统一的结构化输出格式（`OutputFormat` 枚举）
- 封装任务执行结果（`TaskOutput` 数据类）

### 1.2 模块组成

```
lib/crewai/src/crewai/
├── task.py                   # 顶层 Task 类（核心：字段定义 + 执行流程）
└── tasks/
    ├── __init__.py            # 导出 OutputFormat, TaskOutput
    ├── conditional_task.py    # ConditionalTask 条件任务
    ├── llm_guardrail.py       # LLMGuardrail LLM 护栏校验
    ├── output_format.py       # OutputFormat 枚举（RAW/JSON/PYDANTIC）
    └── task_output.py         # TaskOutput 任务输出数据结构
```

### 1.3 架构图

```
┌──────────────────────────────────────────────────────────────────┐
│                          Task (task.py)                           │
│  字段: description, expected_output, agent, context, tools, ...  │
│  方法: execute_sync(), execute_async(), prompt(), ...            │
│  验证: guardrail validate → model_validator → field_validator    │
├──────────────────────────────────────────────────────────────────┤
│                              │                                    │
│    ┌─────────────────────────┼─────────────────────────┐         │
│    ▼                         ▼                         ▼         │
│ ┌──────────────┐  ┌──────────────────┐  ┌──────────────────────┐ │
│ │ConditionalTask│  │  LLMGuardrail    │  │  TaskOutput          │ │
│ │ (继承 Task)   │  │  (独立类)        │  │  (BaseModel)         │ │
│ │               │  │                  │  │                      │ │
│ │ condition字段  │  │ __call__(output) │  │ raw / json_dict /    │ │
│ │ should_execute│  │ → (bool, Any)   │  │ pydantic 属性        │ │
│ └──────────────┘  └──────────────────┘  └──────────────────────┘ │
│                                                                   │
│  ┌──────────────────┐                                             │
│  │  OutputFormat     │  ← 枚举: RAW="raw", JSON="json",           │
│  │  (Enum)           │          PYDANTIC="pydantic"               │
│  └──────────────────┘                                             │
└──────────────────────────────────────────────────────────────────┘
```

---

## 2. 核心实现逻辑详解

### 2.1 Task 类 — 字段定义与任务执行流程

**源码位置**：`lib/crewai/src/crewai/task.py`，第 114-1463 行。

`Task` 继承自 Pydantic 的 `BaseModel`（第 114 行），是一个带有丰富字段验证和执行逻辑的数据模型。

#### 2.1.1 核心字段一览

| 字段名 | 类型 | 默认值 | 源码行号 | 说明 |
|--------|------|--------|----------|------|
| `description` | `str` | 必填 | 146 | 任务的文字描述，告诉 Agent 要做什么 |
| `expected_output` | `str` | 必填 | 147-149 | 清晰定义期望的输出格式/内容 |
| `agent` | `BaseAgent \| None` | `None` | 157-160 | 负责任务执行的 Agent，通过 `BeforeValidator(_resolve_agent)` 支持字符串解析 |
| `context` | `list[Task] \| None \| _NotSpecified` | `NOT_SPECIFIED` | 161-164 | 前序任务列表，其输出作为本任务的上下文 |
| `async_execution` | `bool \| None` | `False` | 165-168 | 是否异步执行 |
| `human_input` | `bool \| None` | `False` | 227-230 | 是否需要人工审核 Agent 的最终回答 |
| `markdown` | `bool \| None` | `False` | 231-234 | 是否要求 Agent 返回 Markdown 格式 |
| `output_json` | `type[BaseModel] \| None` | `None` | 169-178 | 用于结构化 JSON 输出的 Pydantic 模型 |
| `output_pydantic` | `type[BaseModel] \| None` | `None` | 179-188 | 用于结构化 Pydantic 输出的 Pydantic 模型 |
| `response_model` | `type[BaseModel] \| None` | `None` | 189-198 | 使用 LLM 原生 structured output 能力的模型 |
| `output_file` | `str \| None` | `None` | 199-202 | 输出文件路径 |
| `create_directory` | `bool \| None` | `True` | 203-206 | 是否自动创建 output_file 的目录 |
| `guardrail` | `GuardrailType \| None` | `None` | 246-256 | 单个护栏函数（callable）或护栏描述（str） |
| `guardrails` | `GuardrailsType \| None` | `None` | 257-267 | 多个护栏函数列表，也支持单个函数或字符串 |
| `guardrail_max_retries` | `int` | `3` | 273-275 | 护栏失败时最大重试次数 |
| `retry_count` | `int` | `0` | 276 | 当前重试计数 |
| `tools` | `list[BaseTool] \| None` | `[]` | 210-213 | 此任务限定使用的工具列表 |
| `callback` | `SerializableCallable \| None` | `None` | 154-156 | 任务完成后的回调函数 |
| `config` | `dict[str, Any] \| None` | `None` | 150-153 | 任务配置字典 |
| `id` | `uuid.UUID` | `uuid.uuid4()` | 222-226 | 任务唯一标识（frozen，不允许用户设置） |
| `input_files` | `dict[str, FileInput]` | `{}` | 214-217 | 命名输入文件字典 |
| `security_config` | `SecurityConfig` | `SecurityConfig()` | 218-221 | 安全配置（含指纹） |
| `allow_crewai_trigger_context` | `bool \| None` | `None` | 283-286 | 是否注入 trigger payload |

##### 私有属性（PrivateAttr）

```python
# task.py 第 287-295 行
_guardrail: GuardrailCallable | None = PrivateAttr(default=None)       # 解析后的单个护栏函数
_guardrails: list[GuardrailCallable] = PrivateAttr(default_factory=list)  # 解析后的护栏函数列表
_guardrail_retry_counts: dict[int, int] = PrivateAttr(default_factory=dict) # 每个护栏的独立重试计数
_original_description: str | None = PrivateAttr(default=None)    # 模板插值前的原始描述
_original_expected_output: str | None = PrivateAttr(default=None) # 模板插值前的原始期望输出
_original_output_file: str | None = PrivateAttr(default=None)    # 模板插值前的原始输出文件路径
_thread: threading.Thread | None = PrivateAttr(default=None)      # 异步执行线程
```

#### 2.1.2 字段验证器链

Task 类在初始化时经过一系列 Pydantic 验证器，确保数据正确性：

**（1）`validate_guardrail_function`（第 302-358 行）**

验证 `guardrail` 字段：如果传入的是 callable，则检查其函数签名必须恰好有一个位置参数，且返回值类型注解必须是 `Tuple[bool, Any]`（如果标注了返回类型）。如果传入的是字符串，则直接放行（后续由 `LLMGuardrail` 处理）。

```python
# task.py 第 332-338 行
if v is not None and callable(v):
    sig = inspect.signature(v)
    positional_args = [
        param for param in sig.parameters.values()
        if param.default is inspect.Parameter.empty
    ]
    if len(positional_args) != 1:
        raise ValueError("Guardrail function must accept exactly one parameter")
```

**（2）`process_model_config`（第 360-363 行）**

`mode="before"` 验证器，在所有字段解析前调用 `process_config(values, cls)`，支持从 YAML 配置文件加载任务字段。

**（3）`validate_required_fields`（第 365-375 行）**

`mode="after"` 验证器，确保 `description` 和 `expected_output` 不为 `None`。

**（4）`ensure_guardrail_is_callable`（第 377-396 行）**

`mode="after"` 验证器，如果 `guardrail` 是字符串，则自动创建 `LLMGuardrail` 实例并赋值给 `_guardrail` 私有属性。这要求 `agent` 不为 `None` 且 `agent.llm` 是 `BaseLLM` 实例。

```python
# task.py 第 379-394 行
if callable(self.guardrail):
    self._guardrail = self.guardrail
elif isinstance(self.guardrail, str):
    from crewai.tasks.llm_guardrail import LLMGuardrail
    if self.agent is None:
        raise ValueError("Agent is required to use LLMGuardrail")
    if not isinstance(self.agent.llm, BaseLLM):
        raise ValueError("Agent must have a BaseLLM instance to use LLMGuardrail")
    self._guardrail = cast(
        GuardrailCallable,
        LLMGuardrail(description=self.guardrail, llm=self.agent.llm),
    )
```

**（5）`ensure_guardrails_is_list_of_callables`（第 398-458 行）**

`mode="after"` 验证器，将 `guardrails` 字段（可以是单个 callable、单个字符串、列表）统一转换为 `_guardrails` 私有属性列表。**注意第 454-456 行**：如果 `_guardrails` 列表非空，则清空 `guardrail` 和 `_guardrail`，确保不会同时使用两者。

**（6）`_deny_user_set_id`（第 460-467 行）**

禁止用户设置 `id` 字段，除非是从 checkpoint 恢复（`from_checkpoint` 上下文标记）。

**（7）`output_file_validation`（第 487-531 行）**

验证 `output_file` 路径的安全性：禁止路径穿越（`..`）、Shell 扩展字符（`~`、`$`）、Shell 特殊字符（`|`、`>`、`<`、`&`、`;`）。支持模板变量如 `{var}`。

**（8）`set_attributes_based_on_config`（第 533-539 行）**

将 `config` 字典中的键值对逐一设置为 Task 实例的属性。

**（9）`check_tools`（第 541-546 行）**

如果 Task 未设置 `tools` 但 Agent 有 `tools`，则自动继承 Agent 的工具。

**（10）`check_output`（第 548-558 行）**

确保 `output_json` 和 `output_pydantic` 不能同时设置。

**（11）`handle_max_retries_deprecation`（第 560-570 行）**

已弃用的 `max_retries` 字段的兼容处理，自动迁移到 `guardrail_max_retries`。

#### 2.1.3 任务执行流程

##### 同步执行：`execute_sync()` → `_execute_core()`

```
execute_sync(agent, context, tools)                # task.py 第 572-580 行
  │
  ├─ self.start_time = datetime.datetime.now()
  └─ _execute_core(agent, context, tools)          # task.py 第 762-885 行
       │
       ├─ set_current_task_id(str(self.id))         # 设置当前任务 ID 上下文
       ├─ _store_input_files()                      # 存储输入文件到 file store
       ├─ agent = agent or self.agent               # 确定执行 Agent
       ├─ 检查 agent 不为 None
       ├─ 设置 self.prompt_context = context
       ├─ tools = tools or self.tools or []         # 确定工具列表
       ├─ self.processed_by_agents.add(agent.role)  # 记录处理 Agent
       ├─ crewai_event_bus.emit(TaskStartedEvent)   # 发送任务开始事件
       │
       ├─ result = agent.execute_task(...)           # ★ 核心：Agent 执行任务
       │
       ├─ _post_agent_execution(agent)              # 后处理（当前为空实现）
       │
       ├─ 处理 result 类型分支：
       │   ├─ isinstance(result, BaseModel):         # 第 798-808 行
       │   │   └─ 根据 output_pydantic/output_json 设置 raw/pydantic/json
       │   ├─ 无 guardrail:                          # 第 809-811 行
       │   │   └─ 调用 _export_output(result) 做格式转换
       │   └─ 有 guardrail:                          # 第 812-814 行
       │       └─ 暂不转换，留待 guardrail 处理
       │
       ├─ 创建 TaskOutput 实例                       # 第 816-826 行
       │
       ├─ 调用 _invoke_guardrail_function() 处理护栏  # 第 828-844 行
       │
       ├─ self.output = task_output
       ├─ self.end_time = datetime.datetime.now()
       ├─ 执行 callback 和 crew.task_callback         # 第 849-863 行
       ├─ 保存 output_file                           # 第 865-873 行
       ├─ crewai_event_bus.emit(TaskCompletedEvent)  # 发送任务完成事件
       └─ clear_task_files / reset_current_task_id   # finally 清理
```

##### 异步执行：`execute_async()` → `_execute_task_async()`

```
execute_async(agent, context, tools)               # task.py 第 596-610 行
  │
  ├─ 创建 Future[TaskOutput]
  ├─ 复制 contextvars
  └─ 启动 daemon 线程执行 _execute_task_async()
       │
       └─ _execute_task_async(agent, context, tools, future)  # task.py 第 612-625 行
            │
            ├─ self.start_time = datetime.datetime.now()
            ├─ result = self._execute_core(agent, context, tools)
            └─ future.set_result(result) 或 future.set_exception(e)
```

`execute_async()` 通过 `contextvars.copy_context()` + `threading.Thread` 实现异步执行，返回 `Future` 对象。这使得调用方可以在不阻塞主线程的情况下等待任务完成。

##### 原生异步执行：`aexecute_sync()` → `_aexecute_core()`

```
aexecute_sync(agent, context, tools)               # task.py 第 627-635 行（async def）
  │
  └─ _aexecute_core(agent, context, tools)          # task.py 第 637-761 行（async def）
       │
       └─ 与 _execute_core 流程完全对称，区别在于：
          ├─ agent.execute_task() → await agent.aexecute_task()
          ├─ _export_output()    → await _aexport_output()
          ├─ _invoke_guardrail_function() → await _ainvoke_guardrail_function()
          ├─ callback 使用 inspect.isawaitable() 检查
          └─ result 处理中 async 使用 await 而非同步调用
```

#### 2.1.4 `prompt()` 方法 — 生成任务提示词

**源码位置**：第 890-980 行。

`prompt()` 方法负责生成发给 Agent 的最终提示词字符串，由三部分组成：

```python
# task.py 第 963-980 行
tasks_slices = [description]

# 第一部分：期望输出
output = I18N_DEFAULT.slice("expected_output").format(
    expected_output=self.expected_output
)
tasks_slices = [description, output]

# 第二部分：Markdown 格式指令（如果 markdown=True）
if self.markdown:
    markdown_instruction = """Your final answer MUST be formatted in Markdown syntax.
Follow these guidelines:
- Use # for headers
- Use ** for bold text
- Use * for italic text
- Use - or * for bullet points
- Use `code` for inline code
- Use ```language for code blocks"""
    tasks_slices.append(markdown_instruction)

return "\n".join(tasks_slices)
```

此外，`prompt()` 还处理以下逻辑：

- **Trigger Payload 注入**（第 902-909 行）：当 `allow_crewai_trigger_context=True` 且 crew 的 `_inputs` 中存在 `crewai_trigger_payload` 时，自动追加到 description 末尾。
- **输入文件列表注入**（第 911-961 行）：根据 LLM 是否支持多模态，将输入文件分为"自动注入（已加载到对话中）"和"工具可用（需通过 read_file 工具读取）"两类，追加到 description 末尾。

#### 2.1.5 `interpolate_inputs_and_add_conversation_history()` — 模板插值与会话历史

**源码位置**：第 982-1061 行。

此方法在任务执行前被调用，负责：

1. **保存原始值**（第 995-1000 行）：将 `description`、`expected_output`、`output_file` 的原始值保存到 `_original_*` 私有属性，以便 `key` 属性（第 582-588 行）基于原始值计算 MD5 哈希。

2. **模板插值**（第 1006-1034 行）：使用 `interpolate_only()` 函数将 `{var}` 模板变量替换为 `inputs` 字典中的值。例如 `description="分析 {topic}"` 在 `inputs={"topic": "AI"}` 下变为 `"分析 AI"`。

3. **内容处理**（第 1016-1019 行）：调用 `process_content()` 对 description 和 expected_output 进行额外处理。

4. **会话历史注入**（第 1036-1061 行）：如果 `inputs` 中包含 `crew_chat_messages`，则将其解析为对话历史并追加到 `description` 末尾。

#### 2.1.6 `copy()` 方法 — 深拷贝任务

**源码位置**：第 1073-1114 行。

`copy()` 方法创建任务的深拷贝，同时保留原始类类型（对 `ConditionalTask` 等子类友好）。它排除了 `id`、`agent`、`context`、`tools` 字段，通过 `task_mapping` 和 agent 角色重新关联克隆后的上下文和 Agent。

#### 2.1.7 `key` 属性 — 任务指纹

**源码位置**：第 582-588 行。

```python
@property
def key(self) -> str:
    description = self._original_description or self.description
    expected_output = self._original_expected_output or self.expected_output
    source = [description, expected_output]
    return md5("|".join(source).encode(), usedforsecurity=False).hexdigest()
```

基于原始 description 和 expected_output 的 MD5 哈希，用于标识同一任务（即使模板插值后内容不同）。

---

### 2.2 ConditionalTask — 条件任务执行

**源码位置**：`lib/crewai/src/crewai/tasks/conditional_task.py`，第 14-68 行。

`ConditionalTask` 继承自 `Task`（第 14 行），新增了一个 `condition` 字段（第 28-31 行），类型为 `SerializableCallable | None`：

```python
# conditional_task.py 第 28-31 行
condition: SerializableCallable | None = Field(
    default=None,
    description="Function that determines whether the task should be executed based on previous task output.",
)
```

#### 核心方法

**`should_execute(context: TaskOutput) -> bool`**（第 41-55 行）：

```python
def should_execute(self, context: TaskOutput) -> bool:
    if self.condition is None:
        raise ValueError("No condition function set for conditional task")
    return bool(self.condition(context))
```

- 接收前一个任务的 `TaskOutput` 作为参数
- 调用 `condition` 函数，传入 `context`（即前一个任务的输出）
- 返回 `bool` 值决定是否执行此任务
- 如果 `condition` 为 `None`，抛出 `ValueError`

**`get_skipped_task_output()`**（第 57-68 行）：

```java
// 当条件判断为 False 时，返回一个空的 TaskOutput，标记任务被跳过
```

```python
# conditional_task.py 第 57-68 行
def get_skipped_task_output(self) -> TaskOutput:
    return TaskOutput(
        description=self.description,
        raw="",
        agent=self.agent.role if self.agent else "",
        output_format=OutputFormat.RAW,
    )
```

#### 与普通 Task 的区别

| 特性 | Task | ConditionalTask |
|------|------|-----------------|
| `condition` 字段 | 无 | 有，决定是否执行 |
| 执行判断 | 始终执行 | 通过 `should_execute()` 判断 |
| 跳过时行为 | 不适用 | 返回 `get_skipped_task_output()` |
| 使用限制 | 无 | 不能是唯一任务，不能是第一个任务 |

---

### 2.3 LLMGuardrail — 护栏校验

**源码位置**：`lib/crewai/src/crewai/tasks/llm_guardrail.py`，第 49-119 行。

#### 2.3.1 类结构

`LLMGuardrail` 是一个独立的类（非 Pydantic 模型），用于通过 LLM 验证任务输出是否符合预设规则。

```python
# llm_guardrail.py 第 49-67 行
class LLMGuardrail:
    def __init__(self, description: str, llm: BaseLLM):
        self.description = description  # 护栏校验规则的文字描述
        self.llm: BaseLLM = llm         # 用于校验的 LLM 实例
```

#### 2.3.2 辅助数据模型

`LLMGuardrailResult`（第 39-46 行）是一个 Pydantic 模型，用于结构化 LLM 的校验结果：

```python
class LLMGuardrailResult(BaseModel):
    valid: bool = Field(description="Whether the task output complies with the guardrail")
    feedback: str | None = Field(
        description="A feedback about the task output if it is not valid", default=None
    )
```

#### 2.3.3 调用时机

`LLMGuardrail` 的调用链路如下：

```
Task 初始化
  └─ ensure_guardrail_is_callable / ensure_guardrails_is_list_of_callables
       └─ 如果 guardrail 是字符串 → 创建 LLMGuardrail(description, llm)
            └─ 赋值给 _guardrail 或 _guardrails

Task 执行 (_execute_core / _aexecute_core)
  └─ Agent 执行完毕，产生 result
       └─ 创建 TaskOutput
            └─ _invoke_guardrail_function() / _ainvoke_guardrail_function()
                 └─ process_guardrail() 调用 guardrail(task_output)
                      └─ LLMGuardrail.__call__(task_output)  ← 在此处被调用
```

#### 2.3.4 `__call__` 方法 — 校验逻辑

**源码位置**：第 98-119 行。

```python
def __call__(self, task_output: TaskOutput) -> tuple[bool, Any]:
    try:
        result = self._validate_output(task_output)
        if not isinstance(result.pydantic, LLMGuardrailResult):
            raise ValueError("The guardrail result is not a valid pydantic model")
        if result.pydantic.valid:
            return True, task_output.raw       # 校验通过 → 返回原始输出
        return False, result.pydantic.feedback  # 校验失败 → 返回反馈信息
    except Exception as e:
        return False, f"Error while validating the task output: {e!s}"
```

返回 `tuple[bool, Any]`：
- `(True, task_output.raw)` — 校验通过
- `(False, feedback)` — 校验失败，返回 LLM 生成的反馈信息

#### 2.3.5 `_validate_output` 方法 — LLM 校验

**源码位置**：第 69-96 行。

```python
def _validate_output(self, task_output: TaskOutput) -> LiteAgentOutput:
    agent = Agent(
        role="Guardrail Agent",
        goal="Validate the output of the task",
        backstory="You are a expert at validating the output of a task...",
        llm=self.llm,
    )
    query = f"""
    Ensure the following task result complies with the given guardrail.
    Task result:
    {task_output.raw}
    Guardrail:
    {self.description}
    Your task:
    - Confirm if the Task result complies with the guardrail.
    - If not, provide clear feedback explaining what is wrong...
    - Focus only on identifying issues — do not propose corrections.
    - If the Task result complies with the guardrail, saying that is valid
    """
    kickoff_result = agent.kickoff(query, response_format=LLMGuardrailResult)
    ...
```

核心逻辑：
1. 创建一个专门的 `Guardrail Agent`，使用用户提供的 `llm`
2. 构造一个包含任务输出和护栏规则的 query
3. 调用 `agent.kickoff()` 并指定 `response_format=LLMGuardrailResult`，让 LLM 输出结构化的校验结果
4. 处理协程/同步两种情况（`_is_coroutine` + `_run_coroutine_sync`）

#### 2.3.6 重试机制

**源码位置**：task.py 第 1246-1463 行（`_invoke_guardrail_function` / `_ainvoke_guardrail_function`）。

当护栏校验失败时，重试流程如下：

```
guardrail 返回 (False, error_message)
  │
  ├─ 检查 attempt >= guardrail_max_retries（默认 3） → 抛出异常
  │
  ├─ 递增 retry_count（单护栏）或 _guardrail_retry_counts[guardrail_index]（多护栏）
  │
  ├─ 构造 context = I18N_DEFAULT.errors("validation_error").format(
  │       guardrail_result_error=..., task_output=...)
  │
  ├─ 重新调用 agent.execute_task(task=self, context=context, tools=tools)
  │     └─ 将校验失败信息作为上下文传递给 Agent，让它重新生成
  │
  └─ 用新结果创建 TaskOutput，再次调用 guardrail
       └─ 循环直到成功或达到最大重试次数
```

关键设计点：
- **每个护栏独立重试计数**（`_guardrail_retry_counts: dict[int, int]`），通过 `guardrail_index` 区分
- 失败时，Agent 会收到包含错误信息的 context，知道上次哪里没通过校验
- 重试时重新执行 `agent.execute_task()`（同步）或 `await agent.aexecute_task()`（异步）

---

### 2.4 OutputFormat — 结构化输出

**源码位置**：`lib/crewai/src/crewai/tasks/output_format.py`，第 6-17 行。

```python
class OutputFormat(str, Enum):
    JSON = "json"
    PYDANTIC = "pydantic"
    RAW = "raw"
```

一个简单的枚举，定义了三种输出格式。它被 `TaskOutput` 引用以标记输出的格式类型，也被 `Task._get_output_format()` 方法使用（task.py 第 1168-1173 行）：

```python
def _get_output_format(self) -> OutputFormat:
    if self.output_json:
        return OutputFormat.JSON
    if self.output_pydantic:
        return OutputFormat.PYDANTIC
    return OutputFormat.RAW
```

#### 结构化输出在 Task 中的实现

Task 通过 `output_json`、`output_pydantic`、`response_model` 三个字段支持结构化输出：

**（1）`output_json` 和 `output_pydantic` — 后处理转换**

这两个字段在 Agent 执行完毕后，通过 `convert_to_model()` / `async_convert_to_model()` 函数（converter.py 第 190-258 行）将 Agent 的文本输出转换为结构化数据：

```python
# task.py 第 1116-1132 行（同步）
def _export_output(self, result: str | BaseModel) -> tuple[BaseModel | None, dict | None]:
    if self.output_pydantic or self.output_json:
        model_output = convert_to_model(
            result, self.output_pydantic, self.output_json, self.agent, self.converter_cls
        )
        pydantic_output, json_output = self._unpack_model_output(model_output)
    return pydantic_output, json_output

# task.py 第 1134-1151 行（异步）
async def _aexport_output(self, result: str | BaseModel) -> ...:
    if self.output_pydantic or self.output_json:
        model_output = await async_convert_to_model(
            result, self.output_pydantic, self.output_json, self.agent, self.converter_cls
        )
        pydantic_output, json_output = self._unpack_model_output(model_output)
    return pydantic_output, json_output
```

`convert_to_model()` 的转换策略（converter.py 第 190-258 行）：
1. 如果 `result` 已经是目标模型的实例 → 直接返回
2. 尝试 JSON 解析 → `model.model_validate_json()`
3. JSON 解析失败 → 正则提取 JSON 片段 → `model.model_validate()`
4. 仍然失败 → 使用 LLM 通过 `Converter` 类进行结构化转换
5. 如果指定了 `converter_cls`，则直接使用自定义转换器

**（2）`response_model` — 原生 structured output**

`response_model` 字段的设计意图是使用 LLM 提供商的原生 structured output 功能（如 OpenAI 的 `response_format`）。在 Agent 执行时，如果 Agent 支持 `response_model`，则 LLM 会直接返回符合 Pydantic 模型的 JSON 对象，无需后处理转换。

**（3）JSON Schema 注入到 prompt**

当 LLM 不支持 function calling 时，`get_conversion_instructions()`（converter.py 第 530-562 行）会将 Pydantic 模型的 JSON Schema 注入到转换提示词中：

```python
# converter.py 第 530-562 行
def get_conversion_instructions(model, llm):
    if llm.supports_function_calling():
        schema_dict = generate_model_description(model)
        schema = json.dumps(schema_dict, indent=2)
        instructions += I18N_DEFAULT.slice("formatted_task_instructions").format(
            output_format=schema
        )
    else:
        model_description = generate_model_description(model)
        schema_json = json.dumps(model_description, indent=2)
        instructions += I18N_DEFAULT.slice("formatted_task_instructions").format(
            output_format=schema_json
        )
    return instructions
```

---

### 2.5 TaskOutput — 任务输出

**源码位置**：`lib/crewai/src/crewai/tasks/task_output.py`，第 14-104 行。

#### 2.5.1 数据结构

```python
# task_output.py 第 14-48 行
class TaskOutput(BaseModel):
    description: str              # 任务描述
    name: str | None = None       # 任务名称
    expected_output: str | None = None  # 期望输出
    summary: str | None = None    # 摘要（自动生成）
    raw: str = ""                 # 原始输出（字符串）
    pydantic: BaseModel | None = None  # Pydantic 模型输出
    json_dict: dict[str, Any] | None = None  # JSON 字典输出
    agent: str                    # 执行 Agent 的角色名
    output_format: OutputFormat = OutputFormat.RAW  # 输出格式
    messages: list[LLMMessage] = []  # Agent 的消息历史
```

#### 2.5.2 核心属性与方法

| 属性/方法 | 源码行号 | 说明 |
|-----------|----------|------|
| `set_summary` | 50-59 | `model_validator`，自动从 `description` 前 10 个词生成摘要 |
| `json` | 61-83 | 属性方法，返回 JSON 字符串。仅在 `output_format == JSON` 时可用，否则抛出 `ValueError` |
| `to_dict()` | 85-97 | 返回字典，优先使用 `json_dict`，其次使用 `pydantic.model_dump()` |
| `__str__()` | 99-104 | 字符串表示，按优先级返回 `pydantic`、`json_dict`、`raw` |

#### 2.5.3 `raw`、`json_dict`、`pydantic` 三属性关系

```
Agent 执行结果 (result)
  │
  ├─ result 是 BaseModel 实例
  │   ├─ raw = result.model_dump_json()          # JSON 字符串
  │   ├─ output_pydantic → pydantic = result     # Pydantic 实例
  │   └─ output_json → json_dict = result.model_dump()  # dict
  │
  ├─ result 是字符串 + 无 guardrail
  │   ├─ raw = result                            # 原始字符串
  │   └─ _export_output(result) → pydantic / json_dict  # 后处理转换
  │
  └─ result 是字符串 + 有 guardrail
      ├─ raw = result                            # 原始字符串
      └─ pydantic = json_dict = None             # 暂不转换，等 guardrail 处理后
```

---

## 3. 完整调用时序图

```
┌──────┐   ┌──────┐   ┌───────────┐   ┌──────────┐   ┌────────────┐   ┌───────────┐
│ Crew │   │ Task │   │Conditional│   │LLMGuardrail│  │  Converter  │   │TaskOutput │
│      │   │      │   │   Task    │   │           │   │            │   │           │
└──┬───┘   └──┬───┘   └─────┬─────┘   └─────┬─────┘   └─────┬──────┘   └─────┬─────┘
   │          │              │               │               │               │
   │ 1. Task(description, expected_output, agent, ...)                       │
   │─────────>│              │               │               │               │
   │          │ 2. Pydantic 验证器链                                          │
   │          │────┐         │               │               │               │
   │          │    │ validate_guardrail_function                              │
   │          │    │ process_model_config                                     │
   │          │    │ validate_required_fields                                 │
   │          │    │ ensure_guardrail_is_callable → LLMGuardrail(desc, llm)  │
   │          │<───┘         │               │               │               │
   │          │              │               │               │               │
   │ 3. 如果是 ConditionalTask                                              │
   │────────────────────────>│               │               │               │
   │          │              │ 4. should_execute(prev_output)                │
   │          │              │────┐          │               │               │
   │          │              │    │ condition(prev_output) → bool            │
   │          │              │<───┘          │               │               │
   │          │              │               │               │               │
   │ 5. task.execute_sync() / execute_async()                                │
   │─────────>│              │               │               │               │
   │          │ 6. interpolate_inputs_and_add_conversation_history()         │
   │          │ 7. agent.execute_task(task, context, tools)                  │
   │          │──────────────────────────────────────────────────────────────│
   │          │              │               │               │ result        │
   │          │<──────────────────────────────────────────────────────────────│
   │          │              │               │               │               │
   │          │ 8. 处理 result 类型分支                                       │
   │          │────┐         │               │               │               │
   │          │    │ is BaseModel? → 直接赋值                               │
   │          │    │ 无 guardrail? → convert_to_model() ──────>│              │
   │          │    │                                   │ to_pydantic/to_json │
   │          │    │                                   │<──────│              │
   │          │<───┘         │               │               │               │
   │          │              │               │               │               │
   │          │ 9. 创建 TaskOutput(description, raw, pydantic, json_dict)    │
   │          │──────────────────────────────────────────────────────────────>│
   │          │              │               │               │               │
   │          │ 10. _invoke_guardrail_function(task_output, agent, tools)     │
   │          │────┐         │               │               │               │
   │          │    │ process_guardrail(output, guardrail)                     │
   │          │    │──────────────────────>│               │               │
   │          │    │              │        │ 11. guardrail(task_output)       │
   │          │    │              │        │────┐          │               │
   │          │    │              │        │    │ _validate_output()         │
   │          │    │              │        │    │ → Agent(Guardrail)         │
   │          │    │              │        │    │ → kickoff(query,            │
   │          │    │              │        │    │   response_format=Result)   │
   │          │    │              │        │<───┘          │               │
   │          │    │              │        │               │               │
   │          │    │              │        │ 12. (bool, Any)                 │
   │          │    │<──────────────────────│               │               │
   │          │    │              │        │               │               │
   │          │    │ 13. 如果失败 & retry < max_retries:                     │
   │          │    │     agent.execute_task(context=error_msg)  ← 重试       │
   │          │    │──────────────────────────────────────────────────────────│
   │          │    │              │        │               │               │
   │          │    │ 14. 如果成功: 更新 task_output                         │
   │          │<───┘         │               │               │               │
   │          │              │               │               │               │
   │          │ 15. self.output = task_output                                │
   │          │ 16. callback(self.output)                                    │
   │          │ 17. crew.task_callback(self.output)                          │
   │          │ 18. 保存 output_file                                         │
   │          │ 19. emit TaskCompletedEvent                                  │
   │          │              │               │               │               │
   │<─────────│ 20. return task_output                                       │
   │          │              │               │               │               │
```

---

## 4. 完整可运行示例

### 示例 1：基础 Task 创建与同步执行

```python
"""示例 1：创建基础 Task 并同步执行"""
import os
from crewai import Agent, Task, Crew
from crewai.llms.providers.openai.completion import OpenAICompletion

# 设置 API Key（请替换为实际值）
os.environ["OPENAI_API_KEY"] = "your-api-key"

# 创建 LLM
llm = OpenAICompletion(model="gpt-4o")

# 创建 Agent
researcher = Agent(
    role="Research Analyst",
    goal="分析给定的主题并提供专业见解",
    backstory="你是一位经验丰富的研究分析师，擅长数据分析和趋势预测。",
    llm=llm,
    verbose=True,
)

# 创建 Task
task = Task(
    description="分析人工智能在医疗领域的应用现状和未来趋势",
    expected_output="一份结构化的分析报告，包含：1) 当前主要应用场景 2) 关键技术 3) 未来趋势预测",
    agent=researcher,
)

# 执行任务
output = task.execute_sync()
print(f"任务描述: {output.description}")
print(f"任务摘要: {output.summary}")
print(f"原始输出: {output.raw[:200]}...")
print(f"输出格式: {output.output_format}")
print(f"执行 Agent: {output.agent}")
```

### 示例 2：使用 `output_pydantic` 实现结构化输出

```python
"""示例 2：使用 output_pydantic 将 Agent 输出转换为结构化 Pydantic 模型"""
import os
from pydantic import BaseModel, Field
from crewai import Agent, Task
from crewai.llms.providers.openai.completion import OpenAICompletion

os.environ["OPENAI_API_KEY"] = "your-api-key"

# 定义输出的 Pydantic 模型
class MedicalAIReport(BaseModel):
    """医疗 AI 分析报告"""
    current_applications: list[str] = Field(description="当前主要应用场景列表")
    key_technologies: list[str] = Field(description="关键技术列表")
    future_trends: list[str] = Field(description="未来趋势预测列表")
    overall_assessment: str = Field(description="总体评估")

llm = OpenAICompletion(model="gpt-4o")

researcher = Agent(
    role="Research Analyst",
    goal="分析给定的主题并提供专业见解",
    backstory="你是一位经验丰富的研究分析师。",
    llm=llm,
    verbose=True,
)

# 创建带结构化输出的 Task
task = Task(
    description="分析人工智能在医疗领域的应用现状和未来趋势",
    expected_output="一份结构化的分析报告",
    agent=researcher,
    output_pydantic=MedicalAIReport,  # 指定 Pydantic 模型
)

# 执行任务
output = task.execute_sync()

# 直接访问结构化数据
print(f"输出格式: {output.output_format}")  # OutputFormat.PYDANTIC
if output.pydantic:
    report: MedicalAIReport = output.pydantic
    print(f"当前应用: {report.current_applications}")
    print(f"关键技术: {report.key_technologies}")
    print(f"未来趋势: {report.future_trends}")
    print(f"总体评估: {report.overall_assessment}")

# 也可以使用 to_dict() 转换为字典
print(f"\n字典形式: {output.to_dict()}")
```

### 示例 3：使用 `output_json` 实现 JSON 输出

```python
"""示例 3：使用 output_json 将 Agent 输出转换为 JSON 字典"""
import os
from pydantic import BaseModel, Field
from crewai import Agent, Task
from crewai.llms.providers.openai.completion import OpenAICompletion

os.environ["OPENAI_API_KEY"] = "your-api-key"

class ProductReview(BaseModel):
    """产品评审"""
    product_name: str = Field(description="产品名称")
    rating: int = Field(description="评分 (1-5)")
    pros: list[str] = Field(description="优点列表")
    cons: list[str] = Field(description="缺点列表")
    recommendation: str = Field(description="推荐意见")

llm = OpenAICompletion(model="gpt-4o")

reviewer = Agent(
    role="Product Reviewer",
    goal="对产品进行专业评审",
    backstory="你是一位资深产品评审专家。",
    llm=llm,
)

task = Task(
    description="对 iPhone 15 Pro 进行详细评审",
    expected_output="一份详细的 JSON 格式产品评审",
    agent=reviewer,
    output_json=ProductReview,  # 指定 output_json（而非 output_pydantic）
)

output = task.execute_sync()
print(f"输出格式: {output.output_format}")  # OutputFormat.JSON

# 访问 JSON 字典
if output.json_dict:
    print(f"产品: {output.json_dict['product_name']}")
    print(f"评分: {output.json_dict['rating']}")
    print(f"优点: {output.json_dict['pros']}")

# 使用 json 属性获取 JSON 字符串
print(f"\nJSON 字符串: {output.json}")
```

### 示例 4：ConditionalTask 条件任务执行

```python
"""示例 4：使用 ConditionalTask 实现条件任务执行"""
import os
from crewai import Agent, Task, Crew
from crewai.llms.providers.openai.completion import OpenAICompletion
from crewai.tasks.conditional_task import ConditionalTask
from crewai.tasks.task_output import TaskOutput

os.environ["OPENAI_API_KEY"] = "your-api-key"

llm = OpenAICompletion(model="gpt-4o")

# 创建 Agent
analyst = Agent(
    role="Data Analyst",
    goal="分析数据并判断是否需要深入调查",
    backstory="你是一位数据分析专家。",
    llm=llm,
)

investigator = Agent(
    role="Investigator",
    goal="对异常情况进行深入调查",
    backstory="你是一位专业的调查员。",
    llm=llm,
)

# 第一个任务：分析数据
analysis_task = Task(
    description="分析以下销售数据：Q1销售额下降15%，Q2恢复增长5%。判断是否需要深入调查。",
    expected_output="分析结果，明确指出是否需要深入调查（是/否）",
    agent=analyst,
)

# 定义一个条件函数：检查前一个任务输出是否包含"需要调查"
def needs_investigation(previous_output: TaskOutput) -> bool:
    """如果前一个任务输出包含'需要调查'或'深入'关键词，则执行调查任务"""
    raw_lower = previous_output.raw.lower()
    return "需要调查" in raw_lower or "深入" in raw_lower

# 第二个任务：条件任务（仅在条件满足时执行）
investigation_task = ConditionalTask(
    description="根据分析结果，对异常销售数据进行深入调查，找出根本原因。",
    expected_output="详细的调查报告，包含根本原因和建议措施。",
    agent=investigator,
    condition=needs_investigation,  # 条件函数
)

# 创建 Crew 来执行任务链
crew = Crew(
    agents=[analyst, investigator],
    tasks=[analysis_task, investigation_task],
    llm=llm,
    verbose=True,
)

result = crew.kickoff()
print(f"\n最终结果: {result}")
```

### 示例 5：LLMGuardrail 护栏校验

```python
"""示例 5：使用 LLMGuardrail 对任务输出进行护栏校验"""
import os
from crewai import Agent, Task
from crewai.llms.providers.openai.completion import OpenAICompletion
from crewai.tasks.task_output import TaskOutput

os.environ["OPENAI_API_KEY"] = "your-api-key"

llm = OpenAICompletion(model="gpt-4o")

# 创建 Agent
writer = Agent(
    role="Content Writer",
    goal="撰写高质量的内容",
    backstory="你是一位专业的内容创作者。",
    llm=llm,
    verbose=True,
)

# 方式一：使用字符串描述护栏（LLMGuardrail 自动创建）
task_with_string_guardrail = Task(
    description="写一篇关于人工智能伦理的短文",
    expected_output="一篇关于AI伦理的短文，约300字",
    agent=writer,
    guardrail="任务输出必须包含以下三个关键词：'隐私'、'公平性'、'透明度'。如果不包含全部三个关键词，则校验失败。",
    guardrail_max_retries=2,  # 最多重试2次
)

# 方式二：使用自定义 callable 护栏函数
def custom_guardrail(task_output: TaskOutput) -> tuple[bool, str]:
    """自定义护栏：检查输出长度是否超过100字"""
    if len(task_output.raw) >= 100:
        return (True, task_output.raw)
    return (False, f"输出太短（{len(task_output.raw)}字），需要至少100字")

task_with_callable_guardrail = Task(
    description="写一篇关于人工智能伦理的短文",
    expected_output="一篇关于AI伦理的短文，约300字",
    agent=writer,
    guardrail=custom_guardrail,
    guardrail_max_retries=2,
)

# 方式三：使用多个护栏（guardrails 列表）
task_with_multiple_guardrails = Task(
    description="写一篇关于人工智能伦理的短文",
    expected_output="一篇关于AI伦理的短文，约300字",
    agent=writer,
    guardrails=[
        "任务输出必须包含关键词'隐私'",
        "任务输出必须包含关键词'公平性'",
        custom_guardrail,
    ],
    guardrail_max_retries=3,
)

# 执行任务（使用方式一）
print("=== 使用字符串护栏 ===")
try:
    output = task_with_string_guardrail.execute_sync()
    print(f"输出: {output.raw[:200]}...")
except Exception as e:
    print(f"护栏校验失败: {e}")
```

---

## 5. 设计亮点与注意事项

### 5.1 设计亮点

1. **Pydantic 验证器链实现声明式字段校验**（task.py 第 302-570 行）
   - 通过 `@field_validator` 和 `@model_validator` 装饰器，将字段验证、护栏函数转换、弃用字段迁移等逻辑以声明式方式组织，每个验证器职责单一。
   - 例如 `ensure_guardrail_is_callable` 验证器自动将字符串护栏转换为 `LLMGuardrail` 实例，用户无需关心底层实现。

2. **对称的同步/异步执行路径**（task.py 第 572-885 行）
   - `_execute_core()` 和 `_aexecute_core()` 方法在逻辑上完全对称，只是调用方式不同（同步 vs async/await）。
   - 输出转换也提供了 `_export_output` 和 `_aexport_output` 的对称实现。
   - 护栏函数也提供了 `_invoke_guardrail_function` 和 `_ainvoke_guardrail_function` 的对称实现。

3. **护栏独立重试机制**（task.py 第 1246-1463 行）
   - 每个护栏有独立的 `_guardrail_retry_counts` 字典（第 291-293 行），多护栏场景下互不干扰。
   - 重试时将校验失败信息作为 context 传递给 Agent，让 Agent 知道上次哪里不符合要求，有针对性地修正。

4. **contextvars 安全隔离**（task.py 第 604、636 行）
   - `execute_async()` 使用 `contextvars.copy_context()` 确保异步线程中的上下文变量隔离。
   - `set_current_task_id()` / `reset_current_task_id()` 使用 `contextvars` 令牌机制，确保任务 ID 在嵌套调用中正确恢复。

5. **输出格式的多级降级策略**（converter.py 第 190-327 行）
   - `convert_to_model()` 实现了四级降级：直接匹配 → JSON 解析 → 正则提取 → LLM 转换，最大程度保证结构化输出成功。

6. **安全性设计**（task.py 第 487-531 行）
   - `output_file_validation` 防止路径穿越、Shell 注入等安全风险。
   - `_deny_user_set_id` 防止用户篡改任务 ID。

### 5.2 注意事项

1. **`output_json` 和 `output_pydantic` 互斥**（task.py 第 548-558 行）
   - 两者不能同时设置，`check_output` 验证器会抛出 `PydanticCustomError`。如果同时需要 JSON 字典和 Pydantic 对象，使用 `output_pydantic` 并通过 `model_dump()` 获取字典。

2. **`guardrail` 和 `guardrails` 互斥**（task.py 第 454-456 行）
   - 当 `guardrails` 列表非空时，`ensure_guardrails_is_list_of_callables` 验证器会自动清空 `guardrail` 和 `_guardrail`。即不能同时使用两者。

3. **字符串护栏需要 Agent 和 LLM**（task.py 第 384-390 行）
   - 如果使用字符串形式的 `guardrail`，必须确保 Task 有 `agent` 且 `agent.llm` 是 `BaseLLM` 实例，否则会抛出 `ValueError`。

4. **`max_retries` 已弃用**（task.py 第 560-570 行）
   - 应使用 `guardrail_max_retries` 替代，`max_retries` 将在 v1.0.0 中移除。

5. **`key` 属性基于原始值**（task.py 第 582-588 行）
   - `key` 属性基于 `_original_description` 和 `_original_expected_output`（模板插值前的值）计算 MD5，确保同一任务在多次插值后仍被视为同一任务。

6. **`ConditionalTask` 不能是第一个任务**（conditional_task.py 第 24-26 行）
   - 因为需要前一个任务的输出来判断是否执行，所以不能在任务链中作为第一个任务，也不能是 Crew 中唯一的任务。

7. **`callback` 必须是可序列化的**（task.py 第 154-156 行）
   - `callback` 字段类型为 `SerializableCallable`，确保在 checkpoint 和序列化场景下可用。

8. **`model_config = {"arbitrary_types_allowed": True}`**（task.py 第 300 行）
   - Task 的 Pydantic 配置允许任意类型，以支持 `BaseAgent`、`BaseTool`、`threading.Thread` 等非标准 Pydantic 类型。