# 阶段 F：tools/ — 工具系统实现逻辑详解

## 1. 模块定位与架构图

CrewAI 工具系统负责定义、描述、调用和缓存 Agent 可用的工具。整个系统由 5 个核心模块组成，分层协作：

```
┌─────────────────────────────────────────────────────────────────┐
│                        @tool 装饰器                              │
│              (base_tool.py:687-772)                              │
│              用户最常使用的入口                                    │
└──────────────────────────┬──────────────────────────────────────┘
                           │ 创建
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Tool (Generic[P, R])                        │
│              (base_tool.py:507-649)                              │
│              泛型工具包装器，包装可调用对象                          │
│              继承自 BaseTool                                     │
└──────────────────────────┬──────────────────────────────────────┘
                           │ 继承
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                   BaseTool (ABC, BaseModel)                      │
│              (base_tool.py:102-503)                              │
│              工具抽象基类：名称、描述、Schema、运行、计数           │
└──────────────┬────────────────────────────┬─────────────────────┘
               │ to_structured_tool()        │
               ▼                            ▼
┌──────────────────────────┐   ┌──────────────────────────────────┐
│   CrewStructuredTool     │   │        ToolUsage                  │
│ (structured_tool.py:183) │◄──│  (tool_usage.py:76-1054)          │
│   结构化工具表示           │   │  工具调用编排器：                   │
│   - 参数解析              │   │  - 缓存检查                        │
│   - 结果校验              │   │  - 使用计数                        │
│   - invoke/ainvoke       │   │  - 错误重试                        │
│   - 工具描述格式化         │   │  - 事件发射                        │
└──────────────────────────┘   └──────────────┬───────────────────┘
                                              │ 使用
                                              ▼
┌─────────────────────────────────────────────────────────────────┐
│           ToolCalling / InstructorToolCalling                     │
│              (tool_calling.py:11-24)                              │
│              LLM 工具调用选择的 Pydantic 数据模型                   │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                      CacheTools                                   │
│              (cache_tools/cache_tools.py:8-28)                    │
│              缓存工具：读取缓存中的工具结果                          │
│              依赖 CacheHandler                                    │
└─────────────────────────────────────────────────────────────────┘
```

**核心设计理念**：BaseTool 是 Pydantic BaseModel，Tool 是泛型可调用包装器，CrewStructuredTool 是独立的结构化工具表示。工具通过 `to_structured_tool()` 在两者之间转换，ToolUsage 作为编排层统一管理工具的执行全生命周期。

---

## 2. 核心实现逻辑详解

### 2.1 BaseTool — 工具基类

**文件**：`lib/crewai/src/crewai/tools/base_tool.py`

BaseTool 是整个工具系统的根基，它同时继承了 Pydantic 的 `BaseModel` 和 Python 的 `ABC`（抽象基类），使得工具既能享受 Pydantic 的数据校验/序列化能力，又能强制子类实现核心方法。

#### 2.1.1 类注册机制

**关键代码**（第 48-55 行，第 108-111 行）：

```python
_TOOL_TYPE_REGISTRY: dict[str, type] = {}

class BaseTool(BaseModel, ABC):
    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        key = f"{cls.__module__}.{cls.__qualname__}"
        _TOOL_TYPE_REGISTRY[key] = cls
```

每当任何子类继承 `BaseTool` 时，`__init_subclass__` 钩子会自动将该子类以 `模块路径.类名` 为键注册到全局字典 `_TOOL_TYPE_REGISTRY` 中。这用于**检查点反序列化**——当从磁盘恢复工具时，系统通过 `tool_type` 字段找到对应的具体类，调用 `model_validate` 还原。

**反序列化入口**（第 58-77 行 `_resolve_tool_dict`）：

```python
def _resolve_tool_dict(value: dict[str, Any]) -> Any:
    dotted = value.get("tool_type", "")
    tool_cls = _TOOL_TYPE_REGISTRY.get(dotted)
    if tool_cls is None:
        mod_path, cls_name = dotted.rsplit(".", 1)
        tool_cls = getattr(importlib.import_module(mod_path), cls_name)
    # 预处理 cache_function 的字符串反序列化
    ...
    return tool_cls.model_validate(data)
```

先查注册表，未命中则动态 import，最后调用 `model_validate` 重建实例。

#### 2.1.2 Pydantic 核心 Schema 定制

**关键代码**（第 113-136 行 `__get_pydantic_core_schema__`）：

BaseTool 通过重写 `__get_pydantic_core_schema__` 实现了一个**包装验证器**（wrap validator）：当 Pydantic 解析一个 `list[BaseTool]` 字段时，如果遇到 `dict` 且包含 `tool_type` 键，就自动调用 `_resolve_tool_dict` 反序列化为具体子类。这解决了多态反序列化问题。

```python
@classmethod
def __get_pydantic_core_schema__(cls, source_type, handler):
    default_schema = handler(source_type)
    if cls is not _BASE_TOOL_CLS:
        return default_schema  # 子类不做特殊处理
    def _validate_tool(value, nxt):
        if isinstance(value, _BASE_TOOL_CLS):
            return value
        if isinstance(value, dict) and "tool_type" in value:
            return _resolve_tool_dict(value)
        return nxt(value)
    return core_schema.no_info_wrap_validator_function(_validate_tool, default_schema, ...)
```

`_BASE_TOOL_CLS` 哨兵（第 504 行）在模块末尾设置，用于区分 BaseTool 自身和其子类。

#### 2.1.3 核心字段

**关键代码**（第 138-191 行）：

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | `str` | 工具唯一名称，用于 LLM 选择和匹配 |
| `description` | `str` | 告诉 LLM 何时/如何使用该工具 |
| `env_vars` | `list[EnvVar]` | 工具所需的环境变量声明 |
| `args_schema` | `type[BaseModel]` | 工具参数的 Pydantic Schema |
| `result_schema` | `type[BaseModel] \| None` | 工具输出结果的 Pydantic Schema |
| `cache_function` | `SerializableCallable` | 决定是否缓存此次调用结果的可调用对象 |
| `result_as_answer` | `bool` | 为 True 时工具结果直接作为 Agent 最终回答 |
| `max_usage_count` | `int \| None` | 工具最大使用次数限制 |
| `current_usage_count` | `int` | 当前已使用次数 |
| `_usage_lock` | `threading.Lock` | 线程安全锁（PrivateAttr） |

`tool_type` 是 `@computed_field`（第 193-197 行），动态返回 `模块.类名`，不存储在模型字段中：

```python
@computed_field
@property
def tool_type(self) -> str:
    cls = type(self)
    return f"{cls.__module__}.{cls.__qualname__}"
```

#### 2.1.4 args_schema 自动推断

**关键代码**（第 199-246 行 `_default_args_schema` 验证器）：

当用户未显式提供 `args_schema` 时，系统自动从 `_run` 方法签名推断：

```python
@field_validator("args_schema", mode="before")
@classmethod
def _default_args_schema(cls, v):
    if isinstance(v, dict):
        restored = _deserialize_schema(v)  # 反序列化
        if restored is not None:
            return restored
    if v is None or v == cls._ArgsSchemaPlaceholder:
        pass  # 从签名推断
    elif isinstance(v, type):
        return v

    run_sig = signature(cls._run)
    fields = {}
    for param_name, param in run_sig.parameters.items():
        if param_name in ("self", "return"):
            continue
        if param.kind in (Parameter.VAR_POSITIONAL, Parameter.VAR_KEYWORD):
            continue
        annotation = param.annotation if param.annotation != param.empty else Any
        if param.default is param.empty:
            fields[param_name] = (annotation, ...)  # 必填
        else:
            fields[param_name] = (annotation, param.default)  # 有默认值
    # 如果 _run 无参数，回退到 _arun 推断
    if not fields:
        arun_sig = signature(cls._arun)
        ...
    return create_model(f"{cls.__name__}Schema", **fields)
```

这段逻辑的处理顺序是：
1. 如果是 `dict` → 尝试反序列化（从 checkpoint 恢复）
2. 如果是 `None` 或占位符 → 从 `_run` 方法签名自动生成
3. 如果 `_run` 没有参数 → 回退到 `_arun` 方法签名
4. 使用 `create_model` 动态创建 Pydantic 模型

#### 2.1.5 工具执行与使用计数

**关键代码**（第 313-365 行）：

`run()` 方法是同步执行入口，`arun()` 是异步执行入口。两者都遵循相同的执行流程：

```python
def run(self, *args, **kwargs) -> Any:
    if not args:
        kwargs = self._validate_kwargs(kwargs)  # 用 args_schema 校验参数
    limit_error = self._claim_usage()            # 原子检查使用次数
    if limit_error:
        return limit_error
    result = self._run(*args, **kwargs)          # 调用子类实现
    if asyncio.iscoroutine(result):
        result = asyncio.run(result)             # 同步化异步结果
    return result
```

`_claim_usage()`（第 294-311 行）使用 `threading.Lock` 保证线程安全：

```python
def _claim_usage(self) -> str | None:
    with self._usage_lock:
        if (self.max_usage_count is not None
            and self.current_usage_count >= self.max_usage_count):
            return f"Tool '{self.name}' has reached its usage limit..."
        self.current_usage_count += 1
        return None
```

`_run` 是抽象方法（第 374-390 行），所有子类必须实现。`_arun` 默认抛出 `NotImplementedError`（第 355-364 行），子类可选覆盖。

#### 2.1.6 工具描述格式化

**关键代码**（第 481-488 行）：

```python
@property
def formatted_description(self) -> str:
    return format_description_for_llm(self.name, self.args_schema, self.description)
```

`formatted_description` 属性将工具名称、参数 Schema 和用户描述组合成 LLM 可读的格式。实际的格式化逻辑在 `structured_tool.py` 的 `format_description_for_llm` 函数中（详见 2.2.3 节）。

#### 2.1.7 to_structured_tool 转换

**关键代码**（第 392-407 行）：

```python
def to_structured_tool(self) -> CrewStructuredTool:
    self._set_args_schema()
    structured_tool = CrewStructuredTool(
        name=self.name,
        description=self.description,
        args_schema=self.args_schema,
        result_schema=self.result_schema,
        func=self._run,
        result_as_answer=self.result_as_answer,
        max_usage_count=self.max_usage_count,
        current_usage_count=self.current_usage_count,
        cache_function=self.cache_function,
    )
    structured_tool._original_tool = self
    return structured_tool
```

将 BaseTool 转换为 CrewStructuredTool 时，保留原始工具的引用（`_original_tool`），以便后续反向获取缓存函数等属性。

---

### 2.2 Tool — 泛型工具包装器

**文件**：`lib/crewai/src/crewai/tools/base_tool.py`（第 507-649 行）

`Tool` 是 `BaseTool` 的泛型子类，用于包装任意可调用对象：

```python
class Tool(BaseTool, Generic[P, R]):
    func: Callable[P, R | Awaitable[R]]
```

#### 2.2.1 _run 实现

**关键代码**（第 542-552 行）：

```python
def _run(self, *args, **kwargs) -> R:
    return self.func(*args, **kwargs)
```

直接委托给 `self.func`，简洁明了。

#### 2.2.2 异步执行

**关键代码**（第 554-592 行）：

```python
async def _arun(self, *args, **kwargs) -> R:
    result = self.func(*args, **kwargs)
    if _is_awaitable(result):
        return await result
    raise NotImplementedError(...)
```

`_arun` 首先调用 `func`，然后判断返回值是否可等待（`_is_awaitable` 函数在第 90-92 行，使用 `asyncio.iscoroutine` 和 `asyncio.isfuture` 进行类型缩窄）。如果 `func` 本身是同步的，则抛出 `NotImplementedError`。

#### 2.2.3 @tool 装饰器

**关键代码**（第 687-772 行）：

`@tool` 装饰器是用户最常用的工具创建入口，支持三种调用方式：

```python
# 方式 1：无参数装饰器
@tool
def greet(name: str) -> str:
    """Greet someone."""
    return f"Hello, {name}!"

# 方式 2：自定义名称
@tool("my_greeter")
def greet(name: str) -> str:
    """Greet someone."""
    return f"Hello, {name}!"

# 方式 3：带选项
@tool(result_as_answer=True, max_usage_count=5)
def greet(name: str) -> str:
    """Greet someone."""
    return f"Hello, {name}!"
```

核心实现逻辑（第 718-772 行）：

```python
def _make_with_name(tool_name: str) -> Callable:
    def _make_tool(f):
        if f.__doc__ is None:
            raise ValueError("Function must have a docstring")
        if f.__annotations__ is None:
            raise ValueError("Function must have type annotations")
        # 从函数签名提取参数字段
        func_sig = signature(f)
        fields = {}
        for param_name, param in func_sig.parameters.items():
            if param_name == "return":
                continue
            ...
        class_name = "".join(tool_name.split()).title()
        args_schema = create_model(class_name, **fields)
        resolved_result_schema = result_schema or _infer_result_schema_from_callable(f)
        return Tool(name=tool_name, description=f.__doc__, func=f,
                    args_schema=args_schema, result_schema=resolved_result_schema, ...)
    return _make_tool
```

要求函数必须有 docstring 和类型注解，docstring 作为 `description`，类型注解用于自动生成 `args_schema`。

---

### 2.3 CrewStructuredTool — 结构化工具

**文件**：`lib/crewai/src/crewai/tools/structured_tool.py`

#### 2.3.1 类定义

**关键代码**（第 183-210 行）：

```python
class CrewStructuredTool(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    name: str = Field(default="")
    description: str = Field(default="")
    args_schema: Annotated[
        type[BaseModel] | None,
        BeforeValidator(_deserialize_schema),
        PlainSerializer(_serialize_schema),
    ] = Field(default=None)
    result_schema: Annotated[
        type[BaseModel] | None,
        BeforeValidator(_deserialize_schema),
        PlainSerializer(_serialize_schema),
    ] = Field(default=None)
    func: Any = Field(default=None, exclude=True)
    ...
```

`args_schema` 和 `result_schema` 字段使用 `Annotated` 结合 `BeforeValidator` 和 `PlainSerializer` 实现自定义序列化/反序列化：
- `BeforeValidator(_deserialize_schema)`：从 JSON dict 反序列化为 Pydantic 模型类
- `PlainSerializer(_serialize_schema)`：序列化为 JSON Schema dict

`func` 字段标记 `exclude=True`，在序列化时排除（因为不可序列化）。

#### 2.3.2 Schema 序列化/反序列化

**关键代码**（第 32-41 行）：

```python
def _serialize_schema(v: type[BaseModel] | None) -> dict[str, Any] | None:
    return v.model_json_schema() if v else None

def _deserialize_schema(v: Any) -> type[BaseModel] | None:
    if v is None or isinstance(v, type):
        return v
    if isinstance(v, dict):
        return create_model_from_schema(v)  # 从 JSON Schema dict 重建模型
    return None
```

序列化：通过 Pydantic 的 `model_json_schema()` 获取 JSON Schema 格式。
反序列化：调用 `create_model_from_schema`（来自 `pydantic_schema_utils`）从 JSON Schema 字典重建 Pydantic 模型类。

#### 2.3.3 LLM 描述格式化

**关键代码**（第 139-176 行 `format_description_for_llm`）：

```python
def format_description_for_llm(name, args_schema, description):
    description = strip_composite_description_prefix(description)
    if args_schema is not None:
        schema = generate_model_description(args_schema)
        args_json = json.dumps(schema["json_schema"]["schema"], indent=2)
    else:
        args_json = "{}"
    return (
        f"Tool Name: {sanitize_tool_name(name)}\n"
        f"Tool Arguments: {args_json}\n"
        f"Tool Description: {description}"
    )
```

输出格式为：
```
Tool Name: my_tool
Tool Arguments: {"properties": {...}, "required": [...]}
Tool Description: 工具的原始描述文本
```

`strip_composite_description_prefix`（第 127-136 行）处理向后兼容——如果 `description` 已经是旧版本写入的复合格式，则剥离前缀只保留原始描述。

#### 2.3.4 from_function 工厂方法

**关键代码**（第 228-287 行）：

```python
@classmethod
def from_function(cls, func, name=None, description=None, return_direct=False,
                  args_schema=None, result_schema=None, infer_schema=True, **kwargs):
    name = name or func.__name__
    description = description or inspect.getdoc(func)
    if description is None:
        raise ValueError("Function must have a docstring...")
    description = textwrap.dedent(description).strip()
    if args_schema is not None:
        schema = args_schema
    elif infer_schema:
        schema = cls._create_schema_from_function(name, func)
    else:
        raise ValueError("Either args_schema must be provided or infer_schema must be True.")
    return cls(name=name, description=description, args_schema=schema,
               result_schema=result_schema or _infer_result_schema_from_callable(func),
               func=func, result_as_answer=return_direct, **kwargs)
```

这是另一条创建工具的路径，与 `@tool` 装饰器平行。`_create_schema_from_function`（第 293-323 行）同样从函数签名推断 Schema，但使用 `get_type_hints` 获取更精确的类型提示。

#### 2.3.5 工具调用 invoke / ainvoke

**关键代码**（第 417-441 行 `invoke`）：

```python
def invoke(self, input, config=None, **kwargs):
    parsed_args = self._parse_args(input)         # 1. 解析参数
    if self.has_reached_max_usage_count():         # 2. 检查使用次数
        raise ToolUsageLimitExceededError(...)
    self._increment_usage_count()                  # 3. 递增计数
    if inspect.iscoroutinefunction(self.func):
        return asyncio.run(self.func(**parsed_args, **kwargs))
    result = self.func(**parsed_args, **kwargs)
    if asyncio.iscoroutine(result):
        return asyncio.run(result)
    return result
```

`ainvoke`（第 373-407 行）是异步版本，对于同步函数使用 `run_in_executor` 避免阻塞事件循环。

`_parse_args`（第 349-371 行）处理两种输入格式：
- `str`：尝试 JSON 解析
- `dict`：直接使用

然后通过 `args_schema.model_validate` 校验并转换为模型实例。

#### 2.3.6 结果格式化

**关键代码**（第 58-87 行 `_format_tool_output_for_agent`）：

```python
def _format_tool_output_for_agent(tool, raw_result):
    original_tool = getattr(tool, "_original_tool", None)
    if original_tool is not None:
        return original_tool.format_output_for_agent(raw_result)
    result_schema = getattr(tool, "result_schema", None)
    if not (isinstance(result_schema, type) and issubclass(result_schema, BaseModel)):
        return str(raw_result)
    try:
        validation_input = raw_result
        if isinstance(raw_result, BaseModel) and not isinstance(raw_result, result_schema):
            validation_input = raw_result.model_dump()
        validated = result_schema.model_validate(validation_input)
        return validated.model_dump_json()
    except Exception:
        return str(raw_result)
```

当存在 `result_schema` 时，将原始结果校验并序列化为 JSON 字符串；否则直接 `str()`。如果工具是从 BaseTool 转换来的，会优先使用 `_original_tool.format_output_for_agent`。

---

### 2.4 ToolUsage — 工具使用编排器

**文件**：`lib/crewai/src/crewai/tools/tool_usage.py`

`ToolUsage` 是工具调用的**核心编排器**，负责工具选择、缓存检查、参数解析、执行、结果格式化、错误处理和事件发射的完整生命周期。

#### 2.4.1 初始化

**关键代码**（第 89-119 行）：

```python
def __init__(self, tools_handler, tools, task, function_calling_llm, agent, action, fingerprint_context):
    self._run_attempts: int = 1
    self._max_parsing_attempts: int = 3
    self._remember_format_after_usages: int = 3
    self.tools_description = render_text_description_and_args(tools)  # 工具描述文本
    self.tools_names = get_tool_names(tools)                          # 工具名列表
    ...
```

关键属性：
- `_max_parsing_attempts = 3`：最大解析重试次数
- `_remember_format_after_usages = 3`：每 3 次工具使用后重新注入工具描述
- `tools_description`：通过 `render_text_description_and_args`（`agent_utils.py:138`）渲染，遍历所有工具调用 `formatted_description` 属性并用换行符连接

对于 OpenAI 更大模型（`gpt-4`、`gpt-4o`、`o1` 系列），调整为 `_max_parsing_attempts = 2`，`_remember_format_after_usages = 4`（第 114-119 行）。

#### 2.4.2 工具调用解析

**关键代码**（第 861-882 行 `_tool_calling`）：

```python
def _tool_calling(self, tool_string):
    try:
        try:
            return self._original_tool_calling(tool_string, raise_error=True)
        except Exception:
            if self.function_calling_llm:
                return self._function_calling(tool_string)
            return self._original_tool_calling(tool_string)
    except Exception as e:
        self._run_attempts += 1
        if self._run_attempts > self._max_parsing_attempts:
            return ToolUsageError(...)
        return self._tool_calling(tool_string)  # 递归重试
```

三级解析策略：
1. **`_original_tool_calling`**（第 838-859 行）：从 Agent 的 `action` 对象直接提取 `tool_name` 和 `tool_input`
2. **`_function_calling`**（第 809-836 行）：使用 LLM 从文本中解析工具调用，根据 LLM 是否支持 function calling 选择 `InstructorToolCalling` 或 `ToolCalling` 模型
3. 失败后递归重试，最多 `_max_parsing_attempts` 次

#### 2.4.3 工具选择

**关键代码**（第 759-802 行 `_select_tool`）：

```python
def _select_tool(self, tool_name):
    sanitized_input = sanitize_tool_name(tool_name)
    order_tools = sorted(
        self.tools,
        key=lambda tool: SequenceMatcher(
            None, sanitize_tool_name(tool.name), sanitized_input
        ).ratio(),
        reverse=True,  # 按相似度降序排列
    )
    for tool in order_tools:
        sanitized_tool = sanitize_tool_name(tool.name)
        if (sanitized_tool == sanitized_input
            or SequenceMatcher(None, sanitized_tool, sanitized_input).ratio() > 0.85):
            return tool
    raise Exception(error)
```

使用 `SequenceMatcher` 模糊匹配工具名称。先对工具名称进行 sanitize（移除特殊字符），然后按相似度排序，完全匹配或相似度 > 85% 即视为命中。未命中则抛出异常并发射 `ToolSelectionErrorEvent`。

#### 2.4.4 同步工具执行

**关键代码**（第 469-707 行 `_use`）：

完整的同步执行流程：

```
1. _check_tool_repeated_usage()     → 检查是否重复调用（相同工具+相同参数）
2. 发射 ToolUsageStartedEvent       → 事件通知
3. 检查缓存                         → tools_handler.cache.read()
4. _check_usage_limit()             → 检查使用次数限制
5. 过滤参数（acceptable_args）      → 只传入 schema 中定义的参数
6. tool.invoke()                    → 调用工具
7. 检查 cache_function              → 决定是否缓存结果
8. tools_handler.on_tool_use()      → 记录工具使用
9. tool.format_output_for_agent()   → 格式化结果
10. 发射 ToolUsageFinishedEvent     → 事件通知
11. 失败时重试（最多 max_parsing_attempts 次）
```

参数过滤逻辑（第 571-579 行）：

```python
acceptable_args = tool.args_schema.model_json_schema()["properties"].keys()
arguments = {k: v for k, v in calling.arguments.items() if k in acceptable_args}
```

只传入工具 Schema 中声明的参数，额外参数被丢弃，防止 LLM 幻觉参数导致调用失败。

#### 2.4.5 缓存判断

**关键代码**（第 591-606 行）：

```python
should_cache = True
original_tool = getattr(available_tool, "_original_tool", None)
cache_func = None
if original_tool and hasattr(original_tool, "cache_function"):
    cache_func = original_tool.cache_function
elif hasattr(available_tool, "cache_function"):
    cache_func = available_tool.cache_function
if cache_func:
    should_cache = cache_func(calling.arguments, result)
self.tools_handler.on_tool_use(calling=calling, output=result, should_cache=should_cache)
```

优先从 `_original_tool`（BaseTool）获取 `cache_function`，回退到 `available_tool`（CrewStructuredTool）。`cache_function` 接收 `(arguments, result)` 返回布尔值，决定是否缓存。

#### 2.4.6 参数校验

**关键代码**（第 884-930 行 `_validate_tool_input`）：

参数校验支持多种格式的自动修复：

```python
def _validate_tool_input(self, tool_input):
    # 1. 尝试标准 JSON 解析
    try: arguments = json.loads(tool_input); ...
    # 2. 尝试 Python 字面量解析（ast.literal_eval）
    try: arguments = ast.literal_eval(tool_input); ...
    # 3. 尝试 JSON 修复（repair_json）
    try: repaired_input = str(repair_json(tool_input, skip_json_loads=True)); ...
    # 4. 尝试 json5 解析（支持注释、尾逗号等）
    try: arguments = json5.loads(tool_input); ...
```

---

### 2.5 ToolCalling / InstructorToolCalling — 工具调用数据模型

**文件**：`lib/crewai/src/crewai/tools/tool_calling.py`

```python
class ToolCalling(BaseModel):
    tool_name: str = Field(..., description="The name of the tool to be called.")
    arguments: dict[str, Any] | None = Field(
        ..., description="A dictionary of arguments to be passed to the tool."
    )

class InstructorToolCalling(PydanticBaseModel):
    tool_name: str = PydanticField(..., description="The name of the tool to be called.")
    arguments: dict[str, Any] | None = PydanticField(
        ..., description="A dictionary of arguments to be passed to the tool."
    )
```

这两个类结构完全相同，但继承自不同的基类：
- `ToolCalling` 继承自 `crewai` 的 `BaseModel`（可能带有额外配置）
- `InstructorToolCalling` 继承自 Pydantic 原生 `BaseModel`

在 `_function_calling`（`tool_usage.py:809-836`）中，根据 LLM 是否支持原生 function calling 来选择使用哪个模型。`InstructorToolCalling` 用于支持 function calling 的 LLM（通过 `instructor` 库进行结构化输出）。

---

### 2.6 CacheTools — 工具缓存

**文件**：`lib/crewai/src/crewai/tools/cache_tools/cache_tools.py`

```python
class CacheTools(BaseModel):
    name: str = "Hit Cache"
    cache_handler: CacheHandler = Field(default_factory=CacheHandler)

    def tool(self) -> CrewStructuredTool:
        return CrewStructuredTool.from_function(
            func=self.hit_cache,
            name=sanitize_tool_name(self.name),
            description="Reads directly from the cache",
        )

    def hit_cache(self, key: str) -> str | None:
        split = key.split("tool:")
        tool = split[1].split("|input:")[0].strip()
        tool_input = split[1].split("|input:")[1].strip()
        return self.cache_handler.read(tool, tool_input)
```

`CacheTools` 是一个非常简单的工具，它将缓存读取操作包装为一个 CrewStructuredTool。`hit_cache` 方法解析缓存键格式 `tool:<tool_name>|input:<tool_input>`，从中提取工具名和输入，然后调用 `CacheHandler.read()` 读取缓存。

缓存键格式举例：
```
tool:web_search|input:{"query": "AI news"}
```

---

## 3. 完整调用时序图

```
Agent                    ToolUsage              CrewStructuredTool       CacheHandler        EventBus
  │                         │                          │                      │                  │
  │  1. 生成 tool_string    │                          │                      │                  │
  │ ──────────────────────► │                          │                      │                  │
  │                         │                          │                      │                  │
  │  2. parse_tool_calling  │                          │                      │                  │
  │     (解析工具调用)        │                          │                      │                  │
  │                         │ _tool_calling()          │                      │                  │
  │                         │ ├─ _original_tool_calling│                      │                  │
  │                         │ │  (从 action 提取)       │                      │                  │
  │                         │ └─ _function_calling()   │                      │                  │
  │                         │    (LLM 解析备选)         │                      │                  │
  │                         │                          │                      │                  │
  │  3. use(calling)        │                          │                      │                  │
  │ ──────────────────────► │                          │                      │                  │
  │                         │                          │                      │                  │
  │                         │ _select_tool()           │                      │                  │
  │                         │ (模糊匹配工具名)           │                      │                  │
  │                         │                          │                      │                  │
  │                         │ _check_tool_repeated_usage│                     │                  │
  │                         │                          │                      │                  │
  │                         │ 发射 ToolUsageStartedEvent│                     │                  │
  │                         │ ────────────────────────────────────────────────────────────────► │
  │                         │                          │                      │                  │
  │                         │ cache.read()             │                      │                  │
  │                         │ ──────────────────────────────────────────────► │                  │
  │                         │ ◄────────────────────────────────────────────── │                  │
  │                         │                          │                      │                  │
  │                         │ [缓存未命中]               │                      │                  │
  │                         │                          │                      │                  │
  │                         │ _check_usage_limit()     │                      │                  │
  │                         │                          │                      │                  │
  │                         │ invoke(input)            │                      │                  │
  │                         │ ────────────────────────►│                      │                  │
  │                         │                          │                      │                  │
  │                         │                          │ _parse_args()       │                  │
  │                         │                          │ (JSON 解析+校验)     │                  │
  │                         │                          │                      │                  │
  │                         │                          │ has_reached_max_usage│                  │
  │                         │                          │                      │                  │
  │                         │                          │ func(**parsed_args)  │                  │
  │                         │                          │                      │                  │
  │                         │          result          │                      │                  │
  │                         │ ◄────────────────────────│                      │                  │
  │                         │                          │                      │                  │
  │                         │ cache_function(args, res)│                      │                  │
  │                         │                          │                      │                  │
  │                         │ on_tool_use()            │                      │                  │
  │                         │ ──────────────────────────────────────────────► │                  │
  │                         │                          │                      │                  │
  │                         │ format_output_for_agent()│                      │                  │
  │                         │ ────────────────────────►│                      │                  │
  │                         │    formatted_result      │                      │                  │
  │                         │ ◄────────────────────────│                      │                  │
  │                         │                          │                      │                  │
  │                         │ 发射 ToolUsageFinishedEvent                     │                  │
  │                         │ ────────────────────────────────────────────────────────────────► │
  │                         │                          │                      │                  │
  │  4. 返回格式化结果        │                          │                      │                  │
  │ ◄───────────────────────│                          │                      │                  │
```

---

## 4. 完整可运行示例

### 示例 1：使用 @tool 装饰器创建工具

```python
"""示例 1：使用 @tool 装饰器创建并运行工具"""
from crewai.tools.base_tool import tool

# 方式 1：无参数装饰器
@tool
def calculator(expression: str) -> str:
    """计算数学表达式，支持加减乘除和幂运算。"""
    try:
        result = eval(expression, {"__builtins__": {}}, {})
        return f"计算结果: {result}"
    except Exception as e:
        return f"计算错误: {e}"

# 方式 2：自定义名称
@tool("weather_reporter")
def get_weather(city: str) -> str:
    """获取指定城市的天气信息。"""
    weather_data = {
        "北京": "晴，25°C",
        "上海": "多云，28°C",
        "深圳": "雷阵雨，30°C",
    }
    return weather_data.get(city, f"未找到 {city} 的天气数据")

# 方式 3：带选项
@tool(result_as_answer=True, max_usage_count=3)
def search_knowledge(query: str) -> str:
    """在知识库中搜索信息。"""
    knowledge = {
        "crewai": "CrewAI 是一个用于构建 AI Agent 团队的 Python 框架。",
        "python": "Python 是一种解释型、面向对象的高级编程语言。",
    }
    return knowledge.get(query.lower(), f"未找到关于 '{query}' 的信息。")

# 运行示例
print("=== 工具基本信息 ===")
print(f"工具名称: {calculator.name}")
print(f"工具描述: {calculator.description}")
print(f"LLM 格式描述:\n{calculator.formatted_description}")
print()

print("=== 同步调用 ===")
result = calculator.run(expression="3 * (4 + 5)")
print(f"calculator: {result}")

result = get_weather.run(city="北京")
print(f"get_weather: {result}")

print()
print("=== 使用次数限制 ===")
for i in range(4):
    result = search_knowledge.run(query="crewai")
    print(f"第 {i+1} 次调用: {result[:50]}...")
```

### 示例 2：自定义 BaseTool 子类

```python
"""示例 2：通过继承 BaseTool 创建自定义工具"""
from typing import Any
from crewai.tools.base_tool import BaseTool

class FileReaderTool(BaseTool):
    """读文件工具"""

    name: str = "File Reader"
    description: str = "读取指定路径的文件内容并返回。"

    def _run(self, file_path: str) -> str:
        """同步读取文件"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            return content[:500]  # 限制长度
        except FileNotFoundError:
            return f"错误: 文件 '{file_path}' 不存在"
        except Exception as e:
            return f"读取错误: {e}"

    async def _arun(self, file_path: str) -> str:
        """异步读取文件（使用 aiofiles 或 run_in_executor）"""
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._run, file_path)

# 使用示例
print("=== 自定义 BaseTool 子类 ===")
reader = FileReaderTool()
print(f"工具名称: {reader.name}")
print(f"args_schema 自动生成: {reader.args_schema.model_json_schema()['properties']}")
print(f"LLM 格式描述:\n{reader.formatted_description}")

# 转换为结构化工具
structured = reader.to_structured_tool()
print(f"\n转换为 CrewStructuredTool: {structured}")
print(f"调用 invoke: {structured.invoke({'file_path': 'nonexistent.txt'})}")
```

### 示例 3：CrewStructuredTool.from_function 用法

```python
"""示例 3：使用 CrewStructuredTool.from_function 创建工具"""
from crewai.tools.structured_tool import CrewStructuredTool
from pydantic import BaseModel, Field

# 定义输出 Schema
class TranslationResult(BaseModel):
    original: str = Field(description="原文")
    translated: str = Field(description="翻译结果")
    source_lang: str = Field(description="源语言")
    target_lang: str = Field(description="目标语言")

def translate(text: str, source_lang: str = "auto", target_lang: str = "en") -> dict:
    """
    多语言翻译工具。
    支持自动检测源语言，将文本翻译为目标语言。
    """
    # 模拟翻译
    translations = {
        ("你好", "en"): "Hello",
        ("Hello", "zh"): "你好",
        ("谢谢", "en"): "Thank you",
        ("Thank you", "zh"): "谢谢",
    }
    key = (text, target_lang)
    translated = translations.get(key, f"[{text} -> {target_lang}]")
    return {
        "original": text,
        "translated": translated,
        "source_lang": source_lang,
        "target_lang": target_lang,
    }

# 创建工具
tool = CrewStructuredTool.from_function(
    func=translate,
    name="translator",
    result_schema=TranslationResult,
)

print("=== CrewStructuredTool.from_function ===")
print(f"工具名称: {tool.name}")
print(f"参数 Schema: {tool.args}")
print(f"输出 Schema: {tool.result_schema.model_json_schema()['properties'] if tool.result_schema else 'None'}")

# 同步调用
result = tool.invoke({"text": "你好", "target_lang": "en"})
print(f"\n同步调用结果: {result}")

# 格式化输出
formatted = tool.format_output_for_agent(result)
print(f"格式化后输出: {formatted}")

# 异步调用
import asyncio
async def async_demo():
    result = await tool.ainvoke({"text": "Hello", "target_lang": "zh"})
    print(f"异步调用结果: {result}")

asyncio.run(async_demo())
```

### 示例 4：ToolUsage 工具调用编排

```python
"""示例 4：模拟 ToolUsage 编排工具调用流程"""
from crewai.tools.tool_usage import ToolUsage
from crewai.tools.tool_calling import ToolCalling
from crewai.tools.base_tool import tool

# 准备工具
@tool
def web_search(query: str) -> str:
    """搜索互联网获取信息。"""
    search_results = {
        "crewai": "CrewAI - 多 Agent 协作框架",
        "agent": "AI Agent 是能自主执行任务的智能体",
    }
    return search_results.get(query.lower(), f"搜索结果: 关于 '{query}' 的信息...")

@tool
def send_email(to: str, subject: str, body: str) -> str:
    """发送电子邮件。"""
    return f"邮件已发送至 {to}，主题: '{subject}'"

# 转换为结构化工具
tools = [web_search.to_structured_tool(), send_email.to_structured_tool()]

# 模拟 ToolCalling（通常由 LLM 生成）
calling = ToolCalling(
    tool_name="web_search",
    arguments={"query": "crewai"}
)

print("=== 工具描述渲染 ===")
print(f"可用工具:\n{render_text_description_and_args(tools)}")

# 注意：ToolUsage 需要 LLM 实例，这里仅展示关键方法
print(f"\n=== 工具选择模拟 ===")
# 模拟模糊匹配
from crewai.utilities.string_utils import sanitize_tool_name
from difflib import SequenceMatcher

def select_tool(tools, name):
    sanitized = sanitize_tool_name(name)
    for tool in tools:
        if sanitize_tool_name(tool.name) == sanitized:
            return tool
        ratio = SequenceMatcher(None, sanitize_tool_name(tool.name), sanitized).ratio()
        if ratio > 0.85:
            return tool
    return None

selected = select_tool(tools, "web_search")
print(f"选择工具 'web_search': {selected}")

selected_fuzzy = select_tool(tools, "web search")  # 带空格也能匹配
print(f"模糊匹配 'web search': {selected_fuzzy}")
```

### 示例 5：缓存工具使用

```python
"""示例 5：CacheTools 缓存工具演示"""
from crewai.tools.cache_tools.cache_tools import CacheTools
from crewai.agents.cache.cache_handler import CacheHandler

# 创建缓存处理器并预填充数据
cache = CacheHandler()
cache.add(tool="web_search", input='{"query": "crewai"}', output="CrewAI 缓存结果")
cache.add(tool="calculator", input='{"expression": "1+1"}', output="2")

# 创建缓存工具
cache_tools = CacheTools(name="Hit Cache", cache_handler=cache)
cache_tool = cache_tools.tool()

print("=== 缓存工具 ===")
print(f"工具名称: {cache_tool.name}")
print(f"工具描述: {cache_tool.description}")

# 缓存命中
key = "tool:web_search|input:{\"query\": \"crewai\"}"
result = cache_tool.invoke({"key": key})
print(f"\n缓存命中 (web_search): {result}")

# 缓存未命中
key_miss = "tool:web_search|input:{\"query\": \"unknown\"}"
result_miss = cache_tool.invoke({"key": key_miss})
print(f"缓存未命中 (web_search): {result_miss}")

# 另一个缓存命中
key_calc = "tool:calculator|input:{\"expression\": \"1+1\"}"
result_calc = cache_tool.invoke({"key": key_calc})
print(f"缓存命中 (calculator): {result_calc}")

# 查看缓存内容
print(f"\n当前缓存条目: {list(cache._cache.keys())}")
```

---

## 5. 设计亮点与注意事项

### 5.1 设计亮点

1. **Pydantic + ABC 双重继承**（`base_tool.py:102`）：BaseTool 同时是 Pydantic Model 和抽象基类，实现了数据校验、序列化与抽象约束的完美融合。这使工具既能享受 Pydantic 的自动校验、JSON Schema 导出，又能强制子类实现 `_run`。

2. **多态反序列化**（`base_tool.py:113-136`）：通过 `__get_pydantic_core_schema__` 重写，实现了 `list[BaseTool]` 字段的自动多态反序列化。当 checkpoint 恢复时，根据 `tool_type` 字段自动找到正确的子类。

3. **Schema 自动推断**（`base_tool.py:199-246`）：从 `_run` 方法签名自动生成 `args_schema`，从返回值类型注解推断 `result_schema`。用户无需手动编写 Pydantic 模型，大幅降低使用门槛。

4. **线程安全的使用计数**（`base_tool.py:294-311`）：`_claim_usage` 使用 `threading.Lock` 保证原子性，防止并发场景下的计数竞态。

5. **三级解析回退策略**（`tool_usage.py:861-882`）：工具调用解析先尝试原始解析，失败后使用 LLM function calling，再失败则递归重试。这种渐进式回退保证了鲁棒性。

6. **参数过滤**（`tool_usage.py:571-579`）：调用工具前过滤掉不在 Schema 中的参数，避免 LLM 幻觉参数导致调用失败。

7. **多格式参数修复**（`tool_usage.py:884-930`）：支持 JSON、Python 字面量、json5、JSON 修复四种解析方式，最大化容错能力。

8. **缓存函数回调**（`tool_usage.py:591-606`）：允许用户通过 `cache_function` 自定义缓存策略，接收 `(args, result)` 返回布尔值，灵活控制缓存行为。

9. **事件驱动架构**（`tool_usage.py:257-274, 975-996`）：工具使用的全生命周期通过 EventBus 发射事件，便于监控、日志和扩展。

### 5.2 注意事项

1. **`@tool` 装饰器要求函数必须有 docstring 和类型注解**（`base_tool.py:720-723`），否则会抛出 `ValueError`。这是硬性约束。

2. **BaseTool 和 CrewStructuredTool 是两套平行的工具表示**。BaseTool 通过 `to_structured_tool()` 转换，转换后的 `_original_tool` 引用用于反向访问缓存函数等属性。在 ToolUsage 中，实际操作的是 CrewStructuredTool。

3. **`_claim_usage` 在 BaseTool 中使用 threading.Lock，而 CrewStructuredTool 的 `_increment_usage_count` 没有锁**（`structured_tool.py:450-454`）。后者通过 `_original_tool` 同步计数，但同步本身不是原子的。

4. **`cache_function` 字段类型是 `SerializableCallable`**（`base_tool.py:175`），在反序列化时通过 `_resolve_tool_dict` 预处理（`base_tool.py:69-75`），将字符串路径解析为实际的可调用对象。

5. **`formatted_description` 的幂等性设计**（`structured_tool.py:139-176`）：`format_description_for_llm` 通过 `strip_composite_description_prefix` 确保即使输入已经是复合格式，也能正确提取原始描述重新生成。这解决了 checkpoint 恢复时的兼容性问题。

6. **重试机制**：`_use` / `_ause` 在 `finally` 块中发射完成事件后再执行重试（`tool_usage.py:703-705`），确保每次尝试都有完整的开始/完成事件对。

7. **`CacheTools` 的缓存键格式**（`cache_tools.py:24-28`）是固定的 `tool:<name>|input:<input>` 格式，与 `CacheHandler.read()` 的参数签名匹配。修改格式需要同步修改 `CacheHandler`。