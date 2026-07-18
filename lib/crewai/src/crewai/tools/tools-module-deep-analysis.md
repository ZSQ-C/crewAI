# CrewAI Tools 模块深度分析

> 本文档面向初学者，从"需求串讲 → 核心实现逻辑 → 通俗解释"三个维度，逐层拆解 tools 模块的每一行关键代码。

---

## 目录

- [第零步：提示词 -- 如何让 AI 帮我分析这个模块](#第零步提示词----如何让-ai-帮我分析这个模块)
- [第一步：整体架构概览（先看地图再走路）](#第一步整体架构概览先看地图再走路)
- [第二步：顶层 -- 用户入口层（你是怎么用工具的）](#第二步顶层----用户入口层你是怎么用工具的)
  - [2.1 `@tool` 装饰器 -- 把普通函数变成工具](#21-tool-装饰器----把普通函数变成工具)
  - [2.2 `BaseTool` -- 所有工具的"老爸"](#22-basetool----所有工具的老爸)
  - [2.3 `Tool` -- 包装可调用函数的工具](#23-tool----包装可调用函数的工具)
- [第三步：中层 -- 结构化工具层（工具如何被系统理解和使用）](#第三步中层----结构化工具层工具如何被系统理解和使用)
  - [3.1 `CrewStructuredTool` -- 工具的统一中间表示](#31-crewstructuredtool----工具的统一中间表示)
  - [3.2 `ToolUsage` -- 工具调用的"总指挥"](#32-toolusage----工具调用的总指挥)
- [第四步：底层 -- 具体实现层（实际干活的各种工具）](#第四步底层----具体实现层实际干活的各种工具)
  - [4.1 Agent 工具 -- 委托工作与提问](#41-agent-工具----委托工作与提问)
  - [4.2 内存工具 -- 记忆与回忆](#42-内存工具----记忆与回忆)
  - [4.3 MCP 工具 -- 连接外部工具服务器](#43-mcp-工具----连接外部工具服务器)
  - [4.4 缓存工具与文件工具](#44-缓存工具与文件工具)
- [第五步：完整调用链路图](#第五步完整调用链路图)
- [第六步：总结 -- 三层架构的关系](#第六步总结----三层架构的关系)

---

## 第零步：提示词 -- 如何让 AI 帮我分析这个模块

> 如果你以后需要让 AI 帮你分析其他模块，可以直接使用以下提示词模板：

```
我需要你帮我深度分析 [模块名] 模块的代码实现，具体要求如下：

1. 先列出该模块下所有文件，并简要说明每个文件的作用。
2. 按照"顶层入口 → 中层抽象 → 底层具体实现"三层架构，逐层分析每个类的实现逻辑。
3. 对每个核心类/函数，先来一段"需求串讲"（用通俗的话描述"这个类要解决什么问题、输入什么、输出什么、核心流程是怎样的"），然后再展开源码级别的详细分析。
4. 画出完整的调用链路图，标注每一层之间的依赖关系和调用方向。
5. 对关键的技术概念（如抽象基类、工厂模式、事件驱动、依赖注入等）给出通俗易懂的解释。
6. 最后总结三层之间的关系，说明数据如何从顶层流向底层。

目标读者是初学者，请多用比喻和通俗语言，避免跳跃式概括。
```

---

## 第一步：整体架构概览（先看地图再走路）

在深入代码之前，我们先看一张"地图"——tools 模块的整体架构：

```
┌─────────────────────────────────────────────────────────────────┐
│                        顶层：用户入口层                           │
│                                                                  │
│  @tool 装饰器  →  Tool 类  →  BaseTool 抽象类                     │
│  （用户写一个函数，加上 @tool 就变成 AI 能调用的工具）               │
└──────────────────────────┬──────────────────────────────────────┘
                           │ to_structured_tool()
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                      中层：结构化工具层                            │
│                                                                  │
│  CrewStructuredTool  ←→  ToolUsage（工具调用总指挥）                │
│  （统一的工具中间表示，负责参数校验、调用执行、结果格式化）          │
│  ToolCalling / InstructorToolCalling（工具调用数据结构）            │
└──────────────────────────┬──────────────────────────────────────┘
                           │ 继承 / 调用
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                      底层：具体实现层                              │
│                                                                  │
│  Agent 工具：DelegateWorkTool, AskQuestionTool                    │
│  内存工具：RecallMemoryTool, RememberTool                         │
│  MCP 工具：MCPNativeTool, MCPToolWrapper                          │
│  文件工具：ReadFileTool, AddImageTool                             │
│  缓存工具：CacheTools                                             │
└─────────────────────────────────────────────────────────────────┘
```

**一句话概括**：用户用 `@tool` 装饰器定义工具 → 系统将其转为 `CrewStructuredTool` 统一格式 → `ToolUsage` 在 Agent 需要时调用这些工具，并处理缓存、事件、重试等所有周边逻辑。

---

## 第二步：顶层 -- 用户入口层（你是怎么用工具的）

### 2.1 `@tool` 装饰器 -- 把普通函数变成工具

**文件位置**：[base_tool.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/tools/base_tool.py#L687-L772)

#### 需求串讲

想象你写了一个 Python 函数，比如：

```python
def greet(name: str) -> str:
    """向某人打招呼"""
    return f"Hello, {name}!"
```

你希望 AI Agent 能调用这个函数。但 AI 不知道这个函数叫什么、需要什么参数、返回什么。`@tool` 装饰器的作用就是：**自动读取函数的签名（参数类型、返回值类型）和文档字符串，包装成一个 Tool 对象，让 AI 能理解并调用它**。

**核心流程**：
1. 用户给函数加上 `@tool` 装饰器
2. 装饰器读取函数的 `__name__`（名字）、`__doc__`（描述）、参数类型注解
3. 用 Pydantic 的 `create_model` 动态生成一个参数校验模型（args_schema）
4. 打包成一个 `Tool` 对象返回

#### 源码解析

```python
# base_tool.py 第 687-772 行
def tool(
    *args: Callable[P2, R2] | str,
    result_schema: type[BaseModel] | None = None,
    result_as_answer: bool = False,
    max_usage_count: int | None = None,
) -> Tool[P2, R2] | Callable[[Callable[P2, R2]], Tool[P2, R2]]:
```

这个函数支持三种用法（通过 Python 的 `@overload` 声明）：

| 用法 | 示例 | 说明 |
|------|------|------|
| 无参数 | `@tool` | 直接用函数名作为工具名 |
| 带名字 | `@tool("my_name")` | 自定义工具名 |
| 带选项 | `@tool(result_as_answer=True)` | 配置选项 |

**核心逻辑在 `_make_with_name` 内部函数**（第 718-760 行）：

```python
def _make_with_name(tool_name: str) -> Callable[[Callable[P2, R2]], Tool[P2, R2]]:
    def _make_tool(f: Callable[P2, R2]) -> Tool[P2, R2]:
        # 1. 函数必须有文档字符串（作为工具描述）
        if f.__doc__ is None:
            raise ValueError("Function must have a docstring")
        # 2. 函数必须有类型注解
        if f.__annotations__ is None:
            raise ValueError("Function must have type annotations")

        # 3. 遍历函数签名，提取参数名和类型
        func_sig = signature(f)
        fields: dict[str, Any] = {}
        for param_name, param in func_sig.parameters.items():
            if param_name == "return":
                continue
            if param.kind in (Parameter.VAR_POSITIONAL, Parameter.VAR_KEYWORD):
                continue
            annotation = param.annotation if param.annotation != param.empty else Any
            if param.default is param.empty:
                fields[param_name] = (annotation, ...)  # 必填参数
            else:
                fields[param_name] = (annotation, param.default)  # 可选参数

        # 4. 用 Pydantic 动态创建参数校验模型
        class_name = "".join(tool_name.split()).title()
        args_schema = create_model(class_name, **fields)

        # 5. 返回 Tool 对象
        return Tool(
            name=tool_name,
            description=f.__doc__,
            func=f,
            args_schema=args_schema,
            ...
        )
    return _make_tool
```

**通俗解释**：`@tool` 就像一个"函数翻译官"。它把 Python 函数的"身份证"（签名 + 文档）翻译成 AI 能看懂的格式（JSON Schema）。比如 `greet(name: str)` 会被翻译成 `{"name": {"type": "string"}}`，AI 就知道调用这个工具需要传一个字符串参数。

---

### 2.2 `BaseTool` -- 所有工具的"老爸"

**文件位置**：[base_tool.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/tools/base_tool.py#L102-L504)

#### 需求串讲

`BaseTool` 是所有工具的抽象基类（Abstract Base Class）。它定义了"一个工具应该具备哪些能力"的**标准模板**，但不实现具体功能（把 `_run` 方法留空，让子类去实现）。

**核心职责**：
1. **定义工具的基本属性**：名字、描述、参数 schema、结果 schema
2. **参数校验**：调用前自动校验传入的参数是否符合 schema
3. **使用次数限制**：限制每个工具最多被调用多少次
4. **工具注册**：自动把子类注册到全局注册表（用于 checkpoint 恢复）
5. **同步/异步双模式**：提供 `run()` 和 `arun()` 两个入口

#### 源码解析

**工具注册机制**（第 108-111 行）：

```python
def __init_subclass__(cls, **kwargs: Any) -> None:
    super().__init_subclass__(**kwargs)
    key = f"{cls.__module__}.{cls.__qualname__}"
    _TOOL_TYPE_REGISTRY[key] = cls
```

`__init_subclass__` 是 Python 的一个特殊方法：**当任何类继承 BaseTool 时，这个方法会自动被调用**。它把子类的完整路径（如 `crewai.tools.agent_tools.delegate_work_tool.DelegateWorkTool`）注册到全局字典 `_TOOL_TYPE_REGISTRY` 中。

**通俗解释**：这就像公司的人力资源系统，每个新员工（子类）入职时自动登记。以后 checkpoint 恢复时，系统可以通过名字找到对应的类。

**参数自动推导**（第 199-246 行）：

```python
@field_validator("args_schema", mode="before")
@classmethod
def _default_args_schema(cls, v):
    # 如果用户没提供 args_schema，自动从 _run 方法的签名中推导
    run_sig = signature(cls._run)
    fields: dict[str, Any] = {}
    for param_name, param in run_sig.parameters.items():
        if param_name in ("self", "return"):
            continue
        annotation = param.annotation if param.annotation != param.empty else Any
        if param.default is param.empty:
            fields[param_name] = (annotation, ...)  # 必填
        else:
            fields[param_name] = (annotation, param.default)  # 可选
    return create_model(f"{cls.__name__}Schema", **fields)
```

**通俗解释**：如果你写了一个工具类，只定义了 `_run(self, query: str, limit: int = 10)`，但没有手动写 args_schema，BaseTool 会自动从 `_run` 的参数中推导出 schema：`query` 是必填的字符串，`limit` 是可选的整数（默认 10）。

**使用次数限制**（第 294-311 行）：

```python
def _claim_usage(self) -> str | None:
    with self._usage_lock:  # 线程锁，保证并发安全
        if (
            self.max_usage_count is not None
            and self.current_usage_count >= self.max_usage_count
        ):
            return f"Tool '{self.name}' has reached its usage limit..."
        self.current_usage_count += 1
        return None
```

**通俗解释**：每个工具可以设置一个"最大使用次数"，比如"搜索工具最多用 3 次"。每次调用前，系统会检查计数器，如果超了就直接返回错误提示。`_usage_lock` 是一个线程锁，确保多个线程同时调用时不会出现计数错误（比如两个线程同时读到 count=2，都认为还能用，结果用了 4 次）。

**同步/异步调用入口**（第 313-365 行）：

```python
def run(self, *args, **kwargs) -> Any:
    if not args:
        kwargs = self._validate_kwargs(kwargs)  # 先校验参数
    limit_error = self._claim_usage()           # 再检查次数
    if limit_error:
        return limit_error
    result = self._run(*args, **kwargs)         # 调用子类实现
    if asyncio.iscoroutine(result):             # 如果返回了协程，自动 await
        result = asyncio.run(result)
    return result

async def arun(self, *args, **kwargs) -> Any:
    if not args:
        kwargs = self._validate_kwargs(kwargs)
    limit_error = self._claim_usage()
    if limit_error:
        return limit_error
    return await self._arun(*args, **kwargs)
```

**调用流程**：`run()` → 参数校验 → 次数检查 → `_run()`（子类实现）→ 返回结果。每一步都像一个安检关卡，确保工具在被正确使用。

---

### 2.3 `Tool` -- 包装可调用函数的工具

**文件位置**：[base_tool.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/tools/base_tool.py#L507-L649)

#### 需求串讲

`Tool` 是 `BaseTool` 的子类，专门用于包装一个**可调用函数**（callable）。它和 `BaseTool` 的区别是：
- `BaseTool`：你必须继承它，实现 `_run` 方法
- `Tool`：你直接传入一个函数，它帮你自动调用

#### 源码解析

```python
class Tool(BaseTool, Generic[P, R]):
    func: Callable[P, R | Awaitable[R]]

    def _run(self, *args, **kwargs) -> R:
        return self.func(*args, **kwargs)  # 直接调用包装的函数

    async def _arun(self, *args, **kwargs) -> R:
        result = self.func(*args, **kwargs)
        if _is_awaitable(result):
            return await result
        raise NotImplementedError(...)
```

**通俗解释**：`BaseTool` 是"你自己做菜"（实现 `_run`），`Tool` 是"你给菜谱，我帮你做"（传入 `func`，自动调用）。

---

## 第三步：中层 -- 结构化工具层（工具如何被系统理解和使用）

### 3.1 `CrewStructuredTool` -- 工具的统一中间表示

**文件位置**：[structured_tool.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/tools/structured_tool.py#L183-L465)

#### 需求串讲

在 CrewAI 中，工具可以来自很多地方：用户用 `@tool` 定义的、LangChain 工具转换来的、MCP 服务器提供的……`CrewStructuredTool` 的作用是**提供一个统一的"中间格式"**，无论工具来源是什么，最终都转成这个格式，方便系统统一处理。

**核心职责**：
1. 统一工具的数据结构（name, description, args_schema, result_schema, func）
2. 提供 `from_function` 工厂方法，从函数创建工具
3. 提供 `invoke` / `ainvoke` 方法，统一调用入口
4. 参数解析和校验
5. 结果格式化（用于返回给 Agent）

#### 源码解析

**数据结构**：

```python
class CrewStructuredTool(BaseModel):
    name: str                           # 工具名称
    description: str                    # 工具描述（给 AI 看的）
    args_schema: type[BaseModel] | None # 参数 schema（Pydantic 模型）
    result_schema: type[BaseModel] | None # 结果 schema
    func: Any                           # 实际执行的函数（不会序列化）
    result_as_answer: bool              # 结果是否直接作为 Agent 的最终回答
    max_usage_count: int | None         # 最大使用次数
    current_usage_count: int            # 当前已使用次数
    cache_function: Any                 # 缓存判断函数
```

**`from_function` 工厂方法**（第 227-287 行）：

```python
@classmethod
def from_function(cls, func, name=None, description=None, ...) -> CrewStructuredTool:
    name = name or func.__name__
    description = description or inspect.getdoc(func)
    # 如果没提供 args_schema，从函数签名自动推导
    if args_schema is not None:
        schema = args_schema
    elif infer_schema:
        schema = cls._create_schema_from_function(name, func)
    return cls(name=name, description=description, args_schema=schema, func=func, ...)
```

**`ainvoke` 异步调用**（第 373-407 行）：

```python
async def ainvoke(self, input, config=None, **kwargs) -> Any:
    parsed_args = self._parse_args(input)  # 1. 解析并校验参数
    if self.has_reached_max_usage_count(): # 2. 检查使用次数
        raise ToolUsageLimitExceededError(...)
    self._increment_usage_count()          # 3. 递增计数

    if inspect.iscoroutinefunction(self.func):
        return await self.func(**parsed_args, **kwargs)  # 4a. 异步函数直接 await
    # 4b. 同步函数放到线程池执行（避免阻塞事件循环）
    return await asyncio.get_event_loop().run_in_executor(
        None, lambda: self.func(**parsed_args, **kwargs)
    )
```

**通俗解释**：`CrewStructuredTool` 就像一个"万能插座适配器"。不管你的插头是美标、欧标还是国标（不同来源的工具），插上这个适配器后都能统一接入 CrewAI 的电路系统。

**`_parse_args` 参数解析**（第 349-371 行）：

```python
def _parse_args(self, raw_args: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(raw_args, str):
        raw_args = json.loads(raw_args)  # 字符串转字典
    if not self.args_schema:
        return raw_args if isinstance(raw_args, dict) else {}
    # 用 Pydantic 校验参数
    validated_args = self.args_schema.model_validate(raw_args)
    return dict(validated_args.model_dump())
```

**通俗解释**：AI 传过来的参数可能是 JSON 字符串 `'{"query": "hello"}'`，也可能是字典 `{"query": "hello"}`。`_parse_args` 把它统一转为字典，然后用 Pydantic 校验（比如 query 必须是字符串，不能是数字）。

**结果格式化**（[structured_tool.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/tools/structured_tool.py#L58-L87) 的 `_format_tool_output_for_agent`）：

```python
def _format_tool_output_for_agent(tool, raw_result) -> str:
    # 如果有 result_schema，用 Pydantic 校验后序列化为 JSON
    if result_schema and issubclass(result_schema, BaseModel):
        validated = result_schema.model_validate(validation_input)
        return validated.model_dump_json()
    return str(raw_result)
```

**通俗解释**：工具执行完返回的结果可能是一个 Python 对象（比如一个 Pydantic 模型），但 Agent 只能读文本。这个方法把结果转成 Agent 能读的字符串，如果有 result_schema 就输出格式化的 JSON。

---

### 3.2 `ToolUsage` -- 工具调用的"总指挥"

**文件位置**：[tool_usage.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/tools/tool_usage.py#L76-L1054)

#### 需求串讲

`ToolUsage` 是工具调用流程的"总指挥"。当 AI Agent 决定要调用某个工具时，`ToolUsage` 负责整个调用过程的管理：

1. **解析 AI 的输出**：AI 输出的工具调用可能是 JSON、可能是自然语言，需要解析出"工具名"和"参数"
2. **选择工具**：根据工具名，从可用工具列表中找到对应的工具
3. **缓存检查**：如果之前调用过相同的工具+参数，直接返回缓存结果
4. **执行调用**：调用工具的 `invoke` 方法
5. **事件发射**：在调用前后发射事件（ToolUsageStartedEvent、ToolUsageFinishedEvent 等）
6. **错误处理与重试**：如果调用失败，尝试重试（最多 N 次）
7. **结果格式化**：把结果格式化成 Agent 能理解的文本

#### 源码解析

**初始化**（第 89-119 行）：

```python
class ToolUsage:
    def __init__(self, tools_handler, tools, task, function_calling_llm, agent, action, ...):
        self.tools = tools                          # 可用工具列表
        self.tools_description = render_text_description_and_args(tools)  # 工具描述文本
        self.tools_names = get_tool_names(tools)    # 工具名列表
        self.tools_handler = tools_handler          # 工具处理器（含缓存）
        self._run_attempts = 1                      # 当前尝试次数
        self._max_parsing_attempts = 3              # 最大解析尝试次数
        # 如果是 OpenAI 大模型，调整重试参数
        if function_calling_llm.model in OPENAI_BIGGER_MODELS:
            self._max_parsing_attempts = 2
```

**同步入口 `use()`**（第 132-169 行）：

```python
def use(self, calling, tool_string) -> str:
    # 1. 如果解析本身就是错误，直接返回错误
    if isinstance(calling, ToolUsageError):
        return error

    # 2. 根据工具名选择工具
    tool = self._select_tool(calling.tool_name)

    # 3. 特殊处理 add_image 工具（不需要包在字符串里）
    if tool is add_image_tool:
        return self._use(...)

    # 4. 调用内部方法
    return f"{self._use(...)}"
```

**核心执行 `_use()`**（第 469-707 行）。这是整个模块最核心的方法，让我按阶段拆解：

**阶段 1：重复使用检查**（第 476-491 行）

```python
if self._check_tool_repeated_usage(calling=calling):
    # 如果这次调用和上次完全一样（工具名+参数都相同），拒绝执行
    result = "You already used this tool with the same arguments..."
    return self._format_result(result=result)
```

**通俗解释**：防止 Agent 陷入死循环——如果 Agent 用同样的参数调了同一个工具两次，说明它可能卡住了，系统会提醒它"你已经用过这个了"。

**阶段 2：发射开始事件**（第 496-514 行）

```python
if self.agent:
    crewai_event_bus.emit(self, ToolUsageStartedEvent(
        agent_key=self.agent.key,
        agent_role=self.agent.role,
        tool_name=self.action.tool,
        tool_args=self.action.tool_input,
        ...
    ))
```

**通俗解释**：就像一个"广播系统"，告诉所有监听者"工具调用开始了"。其他模块（如 tracing、日志）可以监听这个事件做相应处理。

**阶段 3：缓存检查**（第 523-534 行）

```python
if self.tools_handler and self.tools_handler.cache:
    input_str = json.dumps(calling.arguments)
    result = self.tools_handler.cache.read(
        tool=sanitize_tool_name(calling.tool_name), input=input_str
    )
    from_cache = result is not None
```

**通俗解释**：如果之前调用过同样的工具+同样的参数，直接从缓存拿结果，不用再执行一遍。就像你问过"今天天气怎么样"，5 秒内再问同样的问题，系统直接给你上次的答案。

**阶段 4：参数过滤**（第 570-587 行）

```python
if calling.arguments:
    try:
        # 只保留工具 schema 中定义的参数，过滤掉多余的
        acceptable_args = tool.args_schema.model_json_schema()["properties"].keys()
        arguments = {k: v for k, v in calling.arguments.items() if k in acceptable_args}
        result = tool.invoke(input=arguments, config=fingerprint_config)
    except Exception:
        # 如果过滤后校验失败，用原始参数再试一次
        arguments = calling.arguments
        result = tool.invoke(input=arguments, config=fingerprint_config)
```

**通俗解释**：AI 有时会多传参数（比如传了 `{"query": "hello", "extra": "unused"}`），但工具只接受 `query`。这里会过滤掉 `extra`，只传 `query`。如果过滤后出错了，再用原始参数试一次。

**阶段 5：缓存写入**（第 591-606 行）

```python
if self.tools_handler:
    should_cache = True
    cache_func = available_tool.cache_function
    if cache_func:
        should_cache = cache_func(calling.arguments, result)  # 用户自定义缓存策略
    self.tools_handler.on_tool_use(calling=calling, output=result, should_cache=should_cache)
```

**通俗解释**：执行完后，把结果写入缓存。用户可以自定义 `cache_function` 来决定"这个结果要不要缓存"——比如某些敏感数据不应该缓存。

**阶段 6：结果格式化与事件**（第 608-661 行）

```python
self.last_raw_result = result
result = self._format_result(result=tool.format_output_for_agent(result))
# 追加到 agent.tools_results
data = {"result": result, "tool_name": ..., "tool_args": ...}
if self.agent:
    self.agent.tools_results.append(data)
```

**阶段 7：错误处理**（第 662-686 行）

```python
except Exception as e:
    self.on_tool_error(tool=tool, tool_calling=calling, e=e)  # 发射错误事件
    self._run_attempts += 1
    if self._run_attempts > self._max_parsing_attempts:
        # 超过最大重试次数，放弃
        result = ToolUsageError("...").message
    else:
        should_retry = True  # 重试
```

**阶段 8：完成事件**（第 693-701 行）

```python
finally:
    if started_event_emitted and not error_event_emitted:
        self.on_tool_use_finished(...)  # 发射 ToolUsageFinishedEvent
```

**通俗解释**：`finally` 块中的代码无论成功还是失败都会执行。这里确保"工具调用完成"事件一定会被发射，用于追踪和日志。

**工具选择 `_select_tool()`**（第 759-802 行）：

```python
def _select_tool(self, tool_name: str) -> Any:
    sanitized_input = sanitize_tool_name(tool_name)
    # 按相似度排序（用 SequenceMatcher 计算字符串相似度）
    order_tools = sorted(
        self.tools,
        key=lambda tool: SequenceMatcher(None, sanitize_tool_name(tool.name), sanitized_input).ratio(),
        reverse=True,
    )
    for tool in order_tools:
        if sanitized_tool == sanitized_input or similarity > 0.85:
            return tool
    raise Exception(f"Action '{tool_name}' don't exist...")
```

**通俗解释**：AI 说"用 Delegate work to coworker"，但实际工具名是"Delegate work to coworker"。这里用字符串相似度匹配（SequenceMatcher），容忍一些小差异（如大小写、空格）。如果相似度超过 85%，就认为匹配成功。

**工具调用解析 `_tool_calling()`**（第 861-882 行）：

```python
def _tool_calling(self, tool_string: str):
    try:
        try:
            return self._original_tool_calling(tool_string, raise_error=True)
        except Exception:
            if self.function_calling_llm:
                return self._function_calling(tool_string)  # 用 LLM 帮忙解析
            return self._original_tool_calling(tool_string)
    except Exception as e:
        self._run_attempts += 1
        if self._run_attempts > self._max_parsing_attempts:
            return ToolUsageError(...)
        return self._tool_calling(tool_string)  # 递归重试
```

**解析策略**：先用原始方法解析（直接从 action 中提取），如果失败且配置了 function_calling_llm，就用 LLM 帮忙解析。最多重试 3 次。

**参数校验 `_validate_tool_input()`**（第 884-930 行）：

这个方法展示了 CrewAI 的"容错"设计哲学——**用多种方式尝试解析 AI 的输出**：

```python
def _validate_tool_input(self, tool_input: str | None) -> dict[str, Any]:
    # 尝试 1：标准 JSON 解析
    try: return json.loads(tool_input)
    except: pass

    # 尝试 2：Python 字面量解析（如 {'key': 'value'}）
    try: return ast.literal_eval(tool_input)
    except: pass

    # 尝试 3：json5 解析（支持尾部逗号、注释等）
    try: return json5.loads(tool_input)
    except: pass

    # 尝试 4：json_repair 修复损坏的 JSON 后再解析
    repaired_input = repair_json(tool_input, skip_json_loads=True)
    return json.loads(repaired_input)
```

**通俗解释**：AI 输出的 JSON 经常不完美——可能少了引号、多了逗号、用了单引号。这里用 4 种方式依次尝试，最大化容错能力。`json_repair` 是一个专门修复损坏 JSON 的库。

---

## 第四步：底层 -- 具体实现层（实际干活的各种工具）

### 4.1 Agent 工具 -- 委托工作与提问

**文件位置**：
- [base_agent_tools.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/tools/agent_tools/base_agent_tools.py)
- [delegate_work_tool.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/tools/agent_tools/delegate_work_tool.py)
- [ask_question_tool.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/tools/agent_tools/ask_question_tool.py)
- [agent_tools.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/tools/agent_tools/agent_tools.py)

#### 需求串讲

在一个 Crew（团队）中，多个 Agent 需要协作。比如经理 Agent 需要把任务分配给研究员 Agent，或者向专家 Agent 提问。Agent 工具提供了"委托工作"和"提问"两种协作方式。

**`DelegateWorkTool`**：把一项任务委托给另一个 Agent 执行
**`AskQuestionTool`**：向另一个 Agent 提问

#### 源码解析

**继承链**：

```
BaseTool → BaseAgentTool → DelegateWorkTool / AskQuestionTool
```

**`BaseAgentTool`**（base_agent_tools.py）：

```python
class BaseAgentTool(BaseTool):
    agents: list[BaseAgent] = Field(description="List of available agents")

    def _execute(self, agent_name, task, context=None) -> str:
        # 1. 清理 Agent 名称（大小写不敏感、去空格、去引号）
        sanitized_name = self.sanitize_agent_name(agent_name)

        # 2. 在 Agent 列表中查找匹配的 Agent
        agent = [a for a in self.agents
                 if self.sanitize_agent_name(a.role) == sanitized_name]

        # 3. 如果找不到，返回错误提示
        if not agent:
            return "No agent found with role '...' ..."

        # 4. 创建 Task 并委托给选中的 Agent 执行
        task_with_assigned_agent = Task(
            description=task,
            agent=selected_agent,
            expected_output="..."
        )
        return selected_agent.execute_task(task_with_assigned_agent, context)
```

**核心逻辑**：`_execute` 方法用 `sanitize_agent_name` 做模糊匹配（大小写不敏感、去引号、去换行），然后创建一个 `Task` 对象，调用目标 Agent 的 `execute_task` 方法。**本质上就是"A 创建一个任务给 B 执行"**。

**`DelegateWorkTool`**（delegate_work_tool.py）：

```python
class DelegateWorkToolSchema(BaseModel):
    task: str           # 要委托的任务描述
    context: str        # 上下文信息
    coworker: str       # 委托给谁

class DelegateWorkTool(BaseAgentTool):
    name: str = "Delegate work to coworker"
    args_schema = DelegateWorkToolSchema

    def _run(self, task, context, coworker=None, **kwargs):
        coworker = self._get_coworker(coworker, **kwargs)
        return self._execute(coworker, task, context)
```

**`AskQuestionTool`**（ask_question_tool.py）：

```python
class AskQuestionToolSchema(BaseModel):
    question: str       # 要问的问题
    context: str        # 上下文
    coworker: str       # 问谁

class AskQuestionTool(BaseAgentTool):
    name: str = "Ask question to coworker"
    args_schema = AskQuestionToolSchema

    def _run(self, question, context, coworker=None, **kwargs):
        coworker = self._get_coworker(coworker, **kwargs)
        return self._execute(coworker, question, context)
```

**两者的区别**：本质上它们都调用 `_execute`，只是语义不同——"委托工作"意味着对方要执行任务并返回结果，"提问"意味着对方要回答问题。在代码层面，它们都是创建一个 Task 让目标 Agent 执行。

**`AgentTools` 管理器**（agent_tools.py）：

```python
class AgentTools:
    def __init__(self, agents: Sequence[BaseAgent]):
        self.agents = agents

    def tools(self) -> list[BaseTool]:
        coworkers = ", ".join([f"{agent.role}" for agent in self.agents])
        delegate_tool = DelegateWorkTool(agents=self.agents, description=f"...{coworkers}")
        ask_tool = AskQuestionTool(agents=self.agents, description=f"...{coworkers}")
        return [delegate_tool, ask_tool]
```

**通俗解释**：`AgentTools` 是一个"工具工厂"，根据当前 Crew 中的 Agent 列表，自动生成委托工具和提问工具，并把可用的同事名字写入描述中，这样 AI 就知道可以委托给谁。

---

### 4.2 内存工具 -- 记忆与回忆

**文件位置**：[memory_tools.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/tools/memory_tools.py)

#### 需求串讲

Agent 在对话过程中需要"记忆"——记住重要的信息，并在需要时"回忆"起来。CrewAI 提供了两个内存工具：

- **`RecallMemoryTool`**：搜索记忆，找到相关信息
- **`RememberTool`**：保存信息到记忆

#### 源码解析

**`RecallMemoryTool`**（搜索记忆）：

```python
class RecallMemoryTool(BaseTool):
    name: str = "Search memory"
    args_schema = RecallMemorySchema  # queries: list[str]
    memory: Any                        # 记忆实例（由外部注入）

    def _run(self, queries: list[str] | str, **kwargs) -> str:
        if isinstance(queries, str):
            queries = [queries]
        all_lines = []
        seen_ids = set()
        for query in queries:
            matches = self.memory.recall(query, limit=20)  # 每种查询最多 20 条
            for m in matches:
                if m.record.id not in seen_ids:  # 去重
                    seen_ids.add(m.record.id)
                    all_lines.append(m.format())
        return "Found memories:\n" + "\n".join(all_lines) if all_lines else "No relevant memories found."
```

**通俗解释**：Agent 可以同时搜索多个查询（如 `["项目截止日期", "用户偏好"]`），工具会去记忆库中搜索相关记录，去重后返回给 Agent。

**`RememberTool`**（保存记忆）：

```python
class RememberTool(BaseTool):
    name: str = "Save to memory"
    memory: Any

    def _run(self, contents: list[str] | str, **kwargs) -> str:
        if isinstance(contents, str):
            contents = [contents]
        if len(contents) == 1:
            record = self.memory.remember(contents[0])
            return f"Saved to memory (scope={record.scope}, importance={record.importance:.1f})."
        self.memory.remember_many(contents)
        return f"Saving {len(contents)} items to memory in background."
```

**通俗解释**：Agent 可以一次性保存多条记忆。如果只保存一条，会返回保存的详细信息（作用域、重要性评分）；如果多条，会在后台批量保存。

**工厂函数 `create_memory_tools()`**：

```python
def create_memory_tools(memory) -> list[BaseTool]:
    tools = [RecallMemoryTool(memory=memory, description=...)]
    if not memory.read_only:  # 只读记忆不提供 RememberTool
        tools.append(RememberTool(memory=memory, description=...))
    return tools
```

**通俗解释**：如果记忆是只读的（比如共享的知识库），就不提供"保存"工具，避免 Agent 尝试写入。

---

### 4.3 MCP 工具 -- 连接外部工具服务器

**文件位置**：
- [mcp_native_tool.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/tools/mcp_native_tool.py)
- [mcp_tool_wrapper.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/tools/mcp_tool_wrapper.py)

#### 需求串讲

MCP（Model Context Protocol）是一个开放协议，允许 AI 应用连接外部工具服务器。比如有一个天气查询的 MCP 服务器，CrewAI 可以通过 MCP 工具来调用它。

CrewAI 提供了两种 MCP 工具封装：
- **`MCPNativeTool`**：每次调用创建新的客户端连接（适合并发场景）
- **`MCPToolWrapper`**：按需连接，支持重试和超时（适合不稳定网络）

#### 源码解析

**`MCPNativeTool`**（mcp_native_tool.py）：

```python
class MCPNativeTool(BaseTool):
    def __init__(self, client_factory, tool_name, tool_schema, server_name):
        # client_factory: 一个返回新 MCPClient 的函数
        self._client_factory = client_factory
        self._original_tool_name = original_tool_name or tool_name

    async def _run_async(self, **kwargs) -> str:
        client = self._client_factory()  # 每次调用都创建新客户端
        await client.connect()
        try:
            result = await client.call_tool(self.original_tool_name, kwargs)
        finally:
            await client.disconnect()  # 确保断开连接
        # 处理结果格式...
        return str(result)
```

**关键设计**：每次调用 `_run_async` 时都通过 `client_factory` 创建新的客户端，用完后立即断开。这保证了**并发安全**——即使同一个工具被多个线程同时调用，每个调用都有自己的独立连接，不会互相干扰。

**通俗解释**：就像每次打电话都拿一个新手机，打完就挂断。这样 10 个人同时打电话也不会串线。

**`MCPToolWrapper`**（mcp_tool_wrapper.py）：

```python
class MCPToolWrapper(BaseTool):
    async def _run_async(self, **kwargs) -> str:
        return await self._retry_with_exponential_backoff(
            self._execute_tool_with_timeout, **kwargs
        )

    async def _retry_with_exponential_backoff(self, operation_func, **kwargs):
        """指数退避重试"""
        for attempt in range(MCP_MAX_RETRIES):  # 最多 3 次
            result, error, should_retry = await self._execute_single_attempt(...)
            if result is not None:
                return result
            if not should_retry:
                return error
            wait_time = 2 ** attempt  # 1秒, 2秒, 4秒...
            await asyncio.sleep(wait_time)

    async def _execute_single_attempt(self, operation_func, **kwargs):
        try:
            result = await operation_func(**kwargs)
            return result, "", False
        except ImportError:
            return None, "MCP library not available...", False  # 不可重试
        except asyncio.TimeoutError:
            return None, "Connection timed out...", True          # 可重试
        except Exception as e:
            if "authentication" in error_str:
                return None, "Authentication failed...", False    # 不可重试
            if "connection" in error_str:
                return None, "Network connection failed...", True # 可重试
```

**错误分类**：不同类型的错误有不同的处理策略：
- **ImportError**（库没装）：不重试，直接告诉用户
- **认证失败**：不重试（重试也没用，密码不对）
- **超时/网络错误**：重试（可能是暂时的网络波动）
- **JSON 解析错误**：重试（可能是服务端暂时返回了异常数据）

**`_execute_tool`**（第 162-191 行）：

```python
async def _execute_tool(self, **kwargs) -> str:
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    server_url = self.mcp_server_params["url"]
    async with streamablehttp_client(server_url, terminate_on_close=True) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(self.original_tool_name, kwargs)
            # 提取结果内容
            if result.content:
                content_item = result.content[0]
                if isinstance(content_item, TextContent):
                    return content_item.text
                return str(content_item)
            return str(result)
```

**通俗解释**：通过 HTTP 连接到 MCP 服务器，初始化会话，调用工具，最后提取文本结果。`terminate_on_close=True` 确保连接关闭时服务器端也清理资源。

---

### 4.4 缓存工具与文件工具

#### 缓存工具

**文件位置**：[cache_tools.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/tools/cache_tools/cache_tools.py)

```python
class CacheTools(BaseModel):
    name: str = "Hit Cache"
    cache_handler: CacheHandler

    def tool(self) -> CrewStructuredTool:
        return CrewStructuredTool.from_function(
            func=self.hit_cache,
            name="Hit Cache",
            description="Reads directly from the cache",
        )

    def hit_cache(self, key: str) -> str | None:
        split = key.split("tool:")
        tool = split[1].split("|input:")[0].strip()
        tool_input = split[1].split("|input:")[1].strip()
        return self.cache_handler.read(tool, tool_input)
```

**通俗解释**：允许 Agent 直接从缓存中读取之前工具调用的结果。key 的格式是 `"tool:tool_name|input:arguments"`。

#### 文件工具

**`ReadFileTool`**（[read_file_tool.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/tools/agent_tools/read_file_tool.py)）：

```python
class ReadFileTool(BaseTool):
    name: str = "read_file"
    _files: dict[str, FileInput] | None = PrivateAttr(default=None)

    def _run(self, file_name: str, **kwargs) -> str:
        file_input = self._files[file_name]
        content = file_input.read()
        content_type = file_input.content_type

        # PDF 文件：提取文本
        if content_type == "application/pdf":
            return self._read_pdf_text(content, filename)

        # 文本文件：直接解码
        if any(content_type.startswith(t) for t in ("text/", "application/json", ...)):
            return content.decode("utf-8")

        # 二进制文件：返回 base64
        encoded = base64.b64encode(content).decode("ascii")
        return f"[Binary file: {filename}]\nBase64: {encoded}"
```

**通俗解释**：Agent 可以读取用户在 kickoff 时传入的文件。PDF 会被提取为文本，普通文本文件直接返回内容，二进制文件（如图片）返回 base64 编码。

**`AddImageTool`**（[add_image_tool.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/tools/agent_tools/add_image_tool.py)）：

```python
class AddImageTool(BaseTool):
    name: str = "Add image to content"
    args_schema = AddImageToolSchema  # image_url, action

    def _run(self, image_url, action=None, **kwargs):
        content = [
            {"type": "text", "text": action},
            {"type": "image_url", "image_url": {"url": image_url}},
        ]
        return {"role": "user", "content": content}
```

**通俗解释**：Agent 可以添加图片到对话上下文中，支持多模态模型（如 GPT-4V）分析图片。

---

## 第五步：完整调用链路图

```
用户代码:
  @tool
  def search(query: str) -> str:
      '''搜索工具'''
      return results

       │
       ▼
  Tool 对象创建（base_tool.py:tool()）
  ├── 从函数签名提取参数 → create_model 生成 args_schema
  └── 返回 Tool(func=search, args_schema=SearchSchema, ...)

       │ Agent 启动时
       ▼
  to_structured_tool()（base_tool.py:392-407）
  └── 转换为 CrewStructuredTool

       │ Agent 执行时
       ▼
  ToolUsage 初始化（tool_usage.py:__init__）
  ├── render_text_description_and_args(tools) → 生成工具描述文本
  └── get_tool_names(tools) → 提取工具名列表

       │ Agent 输出工具调用
       ▼
  ToolUsage.parse_tool_calling(tool_string)
  └── _tool_calling(tool_string)
      ├── _original_tool_calling() → 从 action 中提取工具名和参数
      │   └── _validate_tool_input() → 4 种方式解析参数
      │       ├── json.loads()
      │       ├── ast.literal_eval()
      │       ├── json5.loads()
      │       └── json_repair + json.loads()
      │
      └── _function_calling() → 如果原始解析失败，用 LLM 帮忙解析

       │
       ▼
  ToolUsage.use(calling, tool_string)
  └── _use(tool_string, tool, calling)
      ├── 1. _check_tool_repeated_usage() → 检查是否重复调用
      ├── 2. emit(ToolUsageStartedEvent) → 发射开始事件
      ├── 3. cache.read() → 检查缓存
      ├── 4. _check_usage_limit() → 检查使用次数限制
      ├── 5. tool.invoke(arguments) → 执行工具
      │   └── CrewStructuredTool.invoke()
      │       ├── _parse_args(input) → 参数校验
      │       ├── has_reached_max_usage_count() → 次数检查
      │       └── func(**parsed_args) → 执行实际函数
      ├── 6. cache.write() → 写入缓存
      ├── 7. tool.format_output_for_agent(result) → 格式化结果
      ├── 8. emit(ToolUsageFinishedEvent) → 发射完成事件
      └── 9. 如果出错 → 重试 或 返回错误
```

---

## 第六步：总结 -- 三层架构的关系

| 层级 | 类/文件 | 职责 | 比喻 |
|------|---------|------|------|
| **顶层** | `@tool` 装饰器, `Tool`, `BaseTool` | 定义工具的"身份证"（名字、参数、描述） | 工厂的"产品设计图纸" |
| **中层** | `CrewStructuredTool`, `ToolUsage` | 统一管理工具调用流程（解析、校验、缓存、事件、重试） | 工厂的"生产流水线" |
| **底层** | `DelegateWorkTool`, `MCPNativeTool`, `RecallMemoryTool` 等 | 实际执行具体任务 | 工厂的"操作工人" |

**数据流向**：

```
用户定义函数 → @tool 包装成 Tool → to_structured_tool() 转为 CrewStructuredTool
→ Agent 决策调用 → ToolUsage 管理调用流程 → CrewStructuredTool.invoke() 执行函数
→ 结果格式化 → 返回给 Agent
```

**核心设计模式**：

1. **模板方法模式**：`BaseTool` 定义 `run()` 的流程（校验→次数检查→执行），子类只实现 `_run()`
2. **工厂模式**：`@tool` 装饰器和 `CrewStructuredTool.from_function()` 都是工厂，从函数创建工具对象
3. **适配器模式**：`CrewStructuredTool` 是统一适配器，把不同来源的工具转成统一格式
4. **观察者模式**：`crewai_event_bus.emit()` 发射事件，允许其他模块监听工具调用
5. **策略模式**：`cache_function` 允许用户自定义缓存策略