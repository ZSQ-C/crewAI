# 阶段 E：llms/ / llm.py — LLM 抽象层实现逻辑详解

## 1. 模块定位与架构图

CrewAI 的 LLM 抽象层是整个框架与各大模型提供商之间的"翻译层"和"适配器层"。它提供了统一的接口来调用不同的 LLM（OpenAI、Anthropic、Gemini 等），同时支持原生 SDK 调用和 LiteLLM 回退两种路径。

### 架构分层

```
┌─────────────────────────────────────────────────────────────┐
│                    Agent / Task / Crew                       │
│              (使用 LLM 的上层构建块)                           │
├─────────────────────────────────────────────────────────────┤
│                    LLM 工厂封装 (llm.py)                      │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  LLM.__new__() → 路由决策                             │   │
│  │    ├─ 原生 SDK 路径 (OpenAICompletion / Anthropic-    │   │
│  │    │    Completion / GeminiCompletion / ...)           │   │
│  │    └─ LiteLLM 回退路径 (LLM 自身)                      │   │
│  └──────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│                 BaseLLM (base_llm.py)                        │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  抽象基类：事件发射、Token 追踪、Hook 系统、             │   │
│  │  消息格式化、工具执行、Stop Words、流式会话              │   │
│  └──────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│              Provider 适配层 (providers/)                     │
│  ┌───────────┐ ┌──────────────┐ ┌──────────┐ ┌─────────┐  │
│  │  OpenAI   │ │  Anthropic   │ │  Gemini  │ │ Bedrock  │  │
│  │Completion │ │  Completion  │ │Completion│ │Completion│  │
│  └───────────┘ └──────────────┘ └──────────┘ └─────────┘  │
├─────────────────────────────────────────────────────────────┤
│              缓存标记 (cache.py)                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  CACHE_BREAKPOINT_KEY → 提示缓存标记                   │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### 核心设计思想

1. **工厂模式路由**：`LLM(model="openai/gpt-4o")` 通过 `__new__` 方法自动路由到正确的 Provider 实现
2. **双路径策略**：优先使用原生 SDK（速度更快、功能更全），无法识别时回退到 LiteLLM（覆盖面广）
3. **事件驱动**：所有 LLM 调用通过 `crewai_event_bus` 发射 `LLMCallStartedEvent`、`LLMCallCompletedEvent`、`LLMStreamChunkEvent` 等事件
4. **上下文变量管理**：使用 `contextvars` 实现调用级别的 stop 覆盖和流式覆盖，线程安全

---

## 2. 核心实现逻辑详解

### 2.1 BaseLLM — 抽象基类

**文件位置**：`lib/crewai/src/crewai/llms/base_llm.py`

`BaseLLM` 继承自 `pydantic.BaseModel` 和 `ABC`，是所有 LLM 实现的统一抽象基类。

#### 2.1.1 核心字段定义（第 150-190 行）

```python
class BaseLLM(BaseModel, ABC):
    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    llm_type: str = "base"          # 类型标识，子类覆写为 "openai" / "anthropic" / "litellm"
    model: str                       # 模型标识符，必填
    temperature: float | None = None
    top_p: float | None = None
    max_tokens: int | float | None = None
    stream: bool | None = None
    seed: int | None = None
    frequency_penalty: float | None = None
    presence_penalty: float | None = None
    api_key: str | None = None
    base_url: str | None = None
    provider: str = Field(default="openai")
    stop: list[str] = Field(default_factory=list, validation_alias=AliasChoices("stop", "stop_sequences"))
    additional_params: dict[str, Any] = Field(default_factory=dict)
```

`stop` 字段通过 `AliasChoices` 同时支持 `stop` 和 `stop_sequences` 两种别名，提供向后兼容（第 186-189 行）。`additional_params` 用于收集不在 Pydantic 模型字段中的额外参数（第 190 行）。

#### 2.1.2 模型验证器 `_validate_init_fields`（第 256-287 行）

这是一个 `mode="before"` 的验证器，在 Pydantic 初始化之前执行：

1. **模型名必填**（第 262-263 行）：`model` 为空时抛出 `ValueError`
2. **stop 序列规范化**（第 265-274 行）：支持 `stop_sequences` 别名，字符串 → 列表转换
3. **默认 provider**（第 276-277 行）：未指定时默认为 `"openai"`
4. **额外参数收集**（第 279-285 行）：未知字段自动合并到 `additional_params`

```python
# 第 279-285 行
known_fields = set(cls.model_fields.keys())
extras = {k: v for k, v in data.items() if k not in known_fields}
for k in extras:
    data.pop(k)
existing = data.get("additional_params") or {}
existing.update(extras)
data["additional_params"] = existing
```

#### 2.1.3 `__setattr__` 属性拦截（第 196-213 行）

重写了 `__setattr__` 方法，对 `stop` / `stop_sequences` 属性做特殊处理：字符串自动包装为列表，非列表类型转为列表。同时优雅处理非字段属性的赋值（如 mock 打补丁场景）。

```python
# 第 196-204 行
def __setattr__(self, name: str, value: Any) -> None:
    if name in ("stop", "stop_sequences"):
        if value is None:
            value = []
        elif isinstance(value, str):
            value = [value]
        elif not isinstance(value, list):
            value = list(value)
        name = "stop"
```

#### 2.1.4 上下文变量系统（第 79-148 行）

CrewAI 使用 `contextvars` 实现调用级别的状态覆盖，保证线程安全：

- **`_current_call_id`**（第 79-81 行）：追踪当前调用 ID，用于事件关联
- **`_call_stop_override_var`**（第 82-84 行）：存储 `{id(llm): [stop_words]}` 映射，允许覆盖特定 LLM 实例的 stop 序列
- **`_call_stream_override_var`**（第 85-87 行）：存储 `{id(llm): bool}` 映射，允许覆盖流式模式

配套的上下文管理器：
- `llm_call_context()`（第 90-98 行）：生成唯一 `call_id`，管理调用生命周期
- `call_stop_override()`（第 101-123 行）：临时覆盖 stop 列表，退出时自动恢复
- `call_stream_override()`（第 126-136 行）：临时覆盖流式标志

**`stop_sequences` 属性**（第 221-235 行）优先返回上下文覆盖值，否则返回实例级别的 `stop`：

```python
@property
def stop_sequences(self) -> list[str]:
    overrides = _call_stop_override_var.get()
    if overrides is not None:
        override = overrides.get(id(self))
        if override is not None:
            return override
    return self.stop
```

#### 2.1.5 抽象方法 `call` / `acall`（第 311-418 行）

`call` 是核心抽象方法（第 311-347 行），所有 Provider 必须实现。参数包括：
- `messages`：输入消息（字符串或消息列表）
- `tools`：工具定义列表
- `callbacks`：回调函数列表
- `available_functions`：可调用的函数映射
- `from_task` / `from_agent`：调用来源追踪
- `response_model`：结构化输出模型

`acall`（第 382-418 行）是异步版本，默认抛出 `NotImplementedError`，由子类按需覆写。

#### 2.1.6 `stream_events` 方法（第 349-380 行）

将普通 `call` 包装为流式会话，通过 `call_stream_override` 强制开启流式模式，返回 `StreamSession` 对象：

```python
def stream_events(self, messages, ...) -> StreamSession[Any]:
    result_holder: list[Any] = []
    state = create_frame_streaming_state(result_holder, use_async=False)
    output_holder: list[StreamSession[Any]] = []

    def run_llm_call() -> Any:
        with call_stream_override(self, True):
            return self.call(messages=messages, ...)

    stream_session: StreamSession[Any] = StreamSession(
        sync_iterator=create_frame_generator(state, run_llm_call, output_holder)
    )
    return stream_session
```

#### 2.1.7 Stop Words 处理（第 433-492 行）

- **`supports_stop_words()`**（第 433-439 行）：返回 `DEFAULT_SUPPORTS_STOP_WORDS`（`True`）
- **`_supports_stop_words_implementation()`**（第 441-451 行）：检查实际是否配置了 stop words
- **`_apply_stop_words()`**（第 452-492 行）：核心方法，在响应文本中查找最早出现的 stop 词位置并截断：

```python
def _apply_stop_words(self, content: str) -> str:
    stops = self.stop_sequences
    if not stops or not content:
        return content
    earliest_stop_pos = len(content)
    found_stop_word = None
    for stop_word in stops:
        stop_pos = content.find(stop_word)
        if stop_pos != -1 and stop_pos < earliest_stop_pos:
            earliest_stop_pos = stop_pos
            found_stop_word = stop_word
    if found_stop_word is not None:
        truncated = content[:earliest_stop_pos].strip()
        return truncated
    return content
```

#### 2.1.8 事件发射系统（第 545-712 行）

BaseLLM 提供了完整的事件发射方法：

- **`_emit_call_started_event()`**（第 545-606 行）：发射 `LLMCallStartedEvent`，包含所有调用参数（temperature、top_p、max_tokens、stream、seed 等），通过 `crewai_event_bus.emit()` 发送
- **`_emit_call_completed_event()`**（第 608-636 行）：发射 `LLMCallCompletedEvent`，携带响应、token 用量、finish_reason
- **`_emit_call_failed_event()`**（第 638-654 行）：发射 `LLMCallFailedEvent`
- **`_emit_stream_chunk_event()`**（第 656-686 行）：流式内容块事件
- **`_emit_thinking_chunk_event()`**（第 688-712 行）：推理/思考内容块事件

#### 2.1.9 工具执行处理（第 714-804 行）

`_handle_tool_execution()` 方法封装了工具执行的完整生命周期：

1. 查找函数名（第 734 行）
2. 发射 `ToolUsageStartedEvent`（第 743-751 行）
3. 执行函数（第 753-754 行）
4. 发射 `ToolUsageFinishedEvent`（第 756-767 行）
5. 发射 `LLMCallCompletedEvent`（第 769-774 行）
6. 异常时发射 `ToolUsageErrorEvent`（第 787-796 行）

返回结果时，非字符串结果自动转为字符串（第 776 行）。

#### 2.1.10 消息格式化与文件处理（第 806-894 行）

- **`_format_messages()`**（第 806-843 行）：将字符串转换为 `[{"role": "user", "content": "..."}]`，验证每条消息有 `role` 和 `content`，并**剥离 `CACHE_BREAKPOINT_KEY`**（第 838-839 行），避免缓存标记污染 API 调用
- **`_process_message_files()`**（第 845-894 行）：处理消息中的文件附件，通过 `crewai_files.format_multimodal_content()` 转换为 provider 特定的内容块格式

#### 2.1.11 结构化输出验证（第 896-932 行）

`_validate_structured_output()` 静态方法处理响应到 Pydantic 模型的转换：
1. 尝试直接 JSON 解析（第 917-919 行）
2. 正则提取 JSON 块（第 921-924 行）：使用 `_JSON_EXTRACTION_PATTERN = re.compile(r"\{.*}", re.DOTALL)`（第 77 行）
3. 失败时抛出 `ValueError`

#### 2.1.12 Token 追踪（第 244-254、948-979 行）

`_token_usage` 私有属性（第 244-254 行）追踪累计 token 使用：

```python
_token_usage: dict[str, int] = PrivateAttr(default_factory=lambda: {
    "total_tokens": 0,
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "successful_requests": 0,
    "cached_prompt_tokens": 0,
    "reasoning_tokens": 0,
    "cache_creation_tokens": 0,
})
```

`_track_token_usage_internal()`（第 948-964 行）通过 `UsageMetrics.from_provider_dict()` 标准化各种 provider 的用量格式并累加。

#### 2.1.13 LLM Hook 系统（第 981-1113 行）

- **`_invoke_before_llm_call_hooks()`**（第 981-1046 行）：在 LLM 调用前执行 hook，任意 hook 返回 `False` 则阻止调用
- **`_invoke_after_llm_call_hooks()`**（第 1048-1113 行）：在 LLM 调用后处理响应，hook 可修改响应内容

---

### 2.2 LLM 工厂封装（llm.py）

**文件位置**：`lib/crewai/src/crewai/llm.py`

`LLM` 类继承自 `BaseLLM`，是整个框架的"入口类"。它既是 LiteLLM 回退路径的实现，也是 Provider 路由的工厂。

#### 2.2.1 `__new__` 工厂方法（第 393-512 行）

这是最核心的路由逻辑。`LLM(model="openai/gpt-4o")` 在对象创建时就决定了实例化哪个类：

**路由决策流程**：

```
1. custom_openai=True → 强制 OpenAI 原生 SDK
   ├─ 必须有 base_url / OPENAI_BASE_URL
   └─ 返回 OpenAICompletion 实例

2. 显式 provider 参数 → 使用该 provider
   └─ 返回对应原生 Provider 实例

3. model 含 "/" 前缀 → 解析前缀
   ├─ 查 provider_mapping 找到 canonical_provider
   ├─ 验证 model_part 是否在已知常量中
   │   ├─ 是 → 原生 SDK 路径
   │   └─ 否 → 检查是否 custom_openai 路由
   │       └─ 否 → LiteLLM 回退
   └─ 返回对应实例

4. 无前缀 → 推断 provider（从常量列表匹配）
   └─ 返回对应原生 Provider 实例
```

**Provider 映射表**（第 432-450 行）：

```python
provider_mapping = {
    "openai": "openai", "anthropic": "anthropic", "claude": "anthropic",
    "azure": "azure", "azure_openai": "azure",
    "google": "gemini", "gemini": "gemini",
    "bedrock": "bedrock", "aws": "bedrock",
    "openrouter": "openrouter", "deepseek": "deepseek",
    "ollama": "ollama", "ollama_chat": "ollama_chat",
    "hosted_vllm": "hosted_vllm", "cerebras": "cerebras",
    "dashscope": "dashscope", "snowflake": "snowflake",
}
```

**原生 Provider 分发**（第 477-491 行）：如果 `native_class` 存在且 provider 在 `SUPPORTED_NATIVE_PROVIDERS` 列表中，则实例化原生 Provider 类，否则走 LiteLLM 回退。

#### 2.2.2 `_get_native_provider()` 方法（第 664-715 行）

将 canonical provider 名映射到具体实现类：

- `openai` → `OpenAICompletion`
- `anthropic` / `claude` → `AnthropicCompletion`
- `azure` / `azure_openai` → `AzureCompletion`
- `google` / `gemini` → `GeminiCompletion`
- `bedrock` → `BedrockCompletion`
- `snowflake` → `SnowflakeCompletion`
- OpenAI 兼容类（openrouter、deepseek、ollama 等）→ `OpenAICompatibleCompletion`

#### 2.2.3 模型验证与模式匹配（第 514-662 行）

- **`_matches_provider_pattern()`**（第 514-582 行）：通过命名模式匹配，支持不在硬编码常量中的新模型（如 `gpt-5`、`claude-4` 等）
- **`_validate_model_in_constants()`**（第 584-617 行）：先查常量表，再回退到模式匹配
- **`_infer_provider_from_model()`**（第 633-662 行）：从模型名推断 provider，无前缀时默认返回 `"openai"`

#### 2.2.4 LiteLLM 延迟加载（第 76-161 行）

LiteLLM 采用**延迟加载**策略，避免其模块级别的 `dotenv.load_dotenv()` 污染环境变量：

```python
_litellm_loaded = False
LITELLM_AVAILABLE = False

def _ensure_litellm() -> bool:
    global _litellm_loaded, LITELLM_AVAILABLE
    if _litellm_loaded:
        return LITELLM_AVAILABLE
    _litellm_loaded = True
    try:
        import litellm as _litellm
        # ... 导入所有需要的类型
        LITELLM_AVAILABLE = True
    except ImportError:
        LITELLM_AVAILABLE = False
    return LITELLM_AVAILABLE
```

#### 2.2.5 LLM.call() 方法（第 1820-1957 行）

这是 LiteLLM 回退路径的 `call` 实现。核心流程：

1. **进入调用上下文**（第 1856 行）：`with llm_call_context()`
2. **发射开始事件**（第 1857-1864 行）
3. **参数验证**（第 1866 行）：`_validate_call_params()`
4. **o1 模型特殊处理**（第 1870-1874 行）：将 system 角色转为 assistant
5. **执行 before hooks**（第 1876-1877 行）
6. **准备参数**（第 1883 行）：`_prepare_completion_params()`
7. **分流处理**（第 1884-1891 行）：
   - 流式 → `_handle_streaming_response()`
   - 非流式 → `_handle_non_streaming_response()`
8. **执行 after hooks**（第 1903-1906 行）
9. **异常处理**（第 1914-1957 行）：自动检测 `stop` 参数不被支持的情况并重试

#### 2.2.6 上下文窗口管理（第 2443-2469 行）

`get_context_window_size()` 返回模型上下文窗口的 **85%**（`CONTEXT_WINDOW_USAGE_RATIO = 0.85`），防止消息被截断：

```python
self.context_window_size = int(DEFAULT_CONTEXT_WINDOW_SIZE * CONTEXT_WINDOW_USAGE_RATIO)
for key, value in LLM_CONTEXT_WINDOW_SIZES.items():
    if self.model.startswith(key):
        self.context_window_size = int(value * CONTEXT_WINDOW_USAGE_RATIO)
```

`LLM_CONTEXT_WINDOW_SIZES`（第 168-323 行）是一个包含 100+ 模型的上下文窗口大小映射表。

#### 2.2.7 流式响应处理（第 800-1126 行）

`_handle_streaming_response()` 方法处理 LiteLLM 的流式输出：

1. 遍历 `litellm.completion(**params)` 的 chunk 流（第 843 行）
2. 从每个 chunk 提取 `delta.content`（第 887-891 行）
3. 处理流式工具调用（第 897-911 行），通过 `AccumulatedToolArgs` 累积分散的 JSON 片段
4. 发射 `LLMStreamChunkEvent` 事件（第 919-929 行）
5. 空响应回退到非流式（第 930-943 行）
6. 收集 usage 信息（第 872-875 行，LiteLLM 的 usage 存储在 `model_extra` 中）

#### 2.2.8 流式工具调用处理（第 1128-1175 行）

`_handle_streaming_tool_calls()` 使用 `defaultdict[int, AccumulatedToolArgs]` 按 `tool_call.index` 累积分散的工具调用参数。当 JSON 参数完整时（`json.loads` 成功），立即执行工具：

```python
AccumulatedToolArgs = {
    function: {
        name: str,     # 工具名称
        arguments: str # 累积的 JSON 参数字符串
    }
}
```

#### 2.2.9 消息格式化（第 2304-2362 行）

`_format_messages_for_provider()` 处理多 provider 的格式差异：

- **o1 模型**（第 2329-2338 行）：system 消息转为 assistant 角色
- **Mistral 模型**（第 2341-2344 行）：最后一条消息不能是 assistant，追加 "Please continue." 用户消息
- **Ollama**（第 2348-2353 行）：最后一条消息不能是 assistant，追加空用户消息
- **Anthropic**（第 2355-2362 行）：第一条消息必须是 user 角色

#### 2.2.10 深拷贝与浅拷贝（第 2540-2668 行）

`__copy__` 和 `__deepcopy__` 方法确保 LLM 实例可以被安全复制，过滤掉 `additional_params` 中与显式字段重复的参数。

---

### 2.3 OpenAI Provider 适配

**文件位置**：`lib/crewai/src/crewai/llms/providers/openai/completion.py`

`OpenAICompletion` 继承自 `BaseLLM`，通过 OpenAI 原生 Python SDK 调用 API，支持 **Chat Completions API** 和 **Responses API** 两种模式。

#### 2.3.1 核心字段（第 166-238 行）

```python
class OpenAICompletion(BaseLLM):
    llm_type: Literal["openai"] = "openai"
    model: str = "gpt-4o"
    api: Literal["completions", "responses"] = "completions"  # API 模式选择
    max_retries: int = 2
    organization: str | None = None
    project: str | None = None
    reasoning_effort: str | None = None
    is_o1_model: bool = False
    is_gpt4_model: bool = False
    custom_openai: bool = False      # 自定义端点（非 OpenAI 官方）
    interceptor: BaseInterceptor | None = None  # HTTP 拦截器
```

**Responses API 特有字段**（第 226-233 行）：

```python
api: Literal["completions", "responses"] = "completions"
instructions: str | None = None          # 系统级指令
store: bool | None = None               # 是否存储响应
previous_response_id: str | None = None  # 多轮对话
include: list[str] | None = None        # 额外包含数据
builtin_tools: list[str] | None = None   # 内置工具
auto_chain: bool = False                # 自动多轮对话
auto_chain_reasoning: bool = False       # 自动推理链
```

#### 2.3.2 客户端初始化（第 286-308 行）

客户端在模型验证后**延迟初始化**（第 273-284 行），支持 API key 未就绪时仍然可以构造对象：

```python
@model_validator(mode="after")
def _init_clients(self) -> OpenAICompletion:
    try:
        self._client = self._build_sync_client()
        self._async_client = self._build_async_client()
    except ValueError:
        pass  # API key 可能尚未设置，延迟到首次调用
    return self
```

支持 `interceptor` 注入自定义 HTTP Transport（第 287-298 行），用于请求/响应拦截。

#### 2.3.3 call() 方法路由（第 414-481 行）

```python
def call(self, messages, ...):
    with llm_call_context():
        formatted_messages = self._format_messages(messages)
        if self.api == "responses":
            return self._call_responses(...)
        return self._call_completions(...)
```

根据 `self.api` 的值选择 Chat Completions 或 Responses API 路径。

#### 2.3.4 Chat Completions 处理（第 1654-1814 行）

`_handle_completion()` 处理非流式 Chat Completions：

1. **结构化输出**（第 1664-1695 行）：使用 `beta.chat.completions.parse()` 获取解析后的 Pydantic 模型
2. **标准调用**（第 1697 行）：`client.chat.completions.create(**params)`
3. **工具调用处理**（第 1712-1746 行）：
   - 无 `available_functions` → 返回 `tool_calls` 列表，由 executor 处理
   - 有 `available_functions` → 直接执行工具并返回结果
4. **Stop Words 应用**（第 1769 行）：`self._apply_stop_words(content)`
5. **异常处理**（第 1788-1812 行）：区分 `NotFoundError`、`APIConnectionError`、上下文超限

#### 2.3.5 流式 Chat Completions（第 1921-2073 行）

`_handle_streaming_completion()` 使用 `Stream[ChatCompletionChunk]`：

1. 遍历 `completion_stream`（第 1990 行）
2. 提取 `delta.content`（第 2010-2017 行）
3. 累积工具调用（第 2019-2056 行）：通过 `tool_calls[dict[int, dict]]` 按 index 合并
4. 通过 `_finalize_streaming_response()` 统一处理（第 2058 行）

#### 2.3.6 Responses API 支持（第 609-669 行）

`_call_responses()` 使用 OpenAI 的新 Responses API：

- 参数从 `messages` 转为 `input`（第 677-708 行）
- system 消息转为 `instructions`（第 688-697 行）
- 内置工具支持：web_search、file_search、code_interpreter、computer_use（第 198-203 行）
- 工具格式从 `{type: "function", function: {...}}` 转为 `{type: "function", name: ..., description: ..., parameters: ...}`（第 791-829 行）
- 支持 `auto_chain` 自动多轮对话（第 843-844 行）
- 支持 `auto_chain_reasoning` ZDR 合规推理链（第 846-849 行）
- `_extract_builtin_tool_outputs()`（第 1426-1543 行）解析内置工具输出为 `ResponsesAPIResult`

#### 2.3.7 工具格式转换（第 1625-1652 行）

`_convert_tools_for_interference()` 将 CrewAI 工具格式转为 OpenAI 的 function calling 格式：

```python
openai_tool = {
    "type": "function",
    "function": {
        "name": name,
        "description": description,
        "strict": True,
        "parameters": sanitize_tool_params_for_openai_strict(params_dict)
    }
}
```

#### 2.3.8 Token 用量提取（第 2480-2502 行）

`_extract_openai_token_usage()` 从 `ChatCompletion` 或 `ChatCompletionChunk` 提取用量，包括 `cached_prompt_tokens`（来自 `prompt_tokens_details`）和 `reasoning_tokens`（来自 `completion_tokens_details`）。

#### 2.3.9 o1 模型特殊处理（第 2504-2518 行）

`_format_messages()` 中，o1 模型的 system 消息被转为 `{"role": "user", "content": f"System: {content}"}`（第 2511-2516 行），因为 o1 不支持 system 角色。

---

### 2.4 Anthropic Provider 适配

**文件位置**：`lib/crewai/src/crewai/llms/providers/anthropic/completion.py`

`AnthropicCompletion` 继承自 `BaseLLM`，通过 Anthropic 原生 Python SDK 调用 API。

#### 2.4.1 核心字段（第 148-168 行）

```python
class AnthropicCompletion(BaseLLM):
    llm_type: Literal["anthropic"] = "anthropic"
    model: str = "claude-3-5-sonnet-20241022"
    max_tokens: int = 4096
    max_retries: int = 2
    thinking: AnthropicThinkingConfig | None = None  # 扩展思考配置
    tool_search: AnthropicToolSearchConfig | None = None  # 工具搜索
    is_claude_3: bool = False
    supports_tools: bool = True
```

**Thinking 配置**（第 127-129 行）：
```python
class AnthropicThinkingConfig(BaseModel):
    type: Literal["enabled", "disabled"]
    budget_tokens: int | None = None
```

**Tool Search 配置**（第 132-145 行）：支持 Claude 的服务端工具搜索，动态发现和加载工具：
```python
class AnthropicToolSearchConfig(BaseModel):
    type: Literal["regex", "bm25"] = "bm25"
```

#### 2.4.2 消息格式化（第 653-850 行）

`_format_messages_for_anthropic()` 是 Anthropic 适配中最复杂的部分，处理 Anthropic 特有的消息格式要求：

1. **System 消息分离**（第 717 行）：提取为独立的 `system_message`
2. **工具结果处理**（第 729-744 行）：`tool` 角色消息转为 `tool_result` 内容块
3. **工具调用转换**（第 747-765 行）：`tool_calls` 转为 `tool_use` 内容块
4. **Thinking 块注入**（第 768-778 行）：当 `thinking` 启用时，保留之前的 thinking 块
5. **首条消息保证**（第 809-812 行）：第一条必须是 user 角色
6. **缓存标记**（第 674-713 行，第 814-849 行）：读取 `CACHE_BREAKPOINT_KEY`，通过 `_stamp_cache_control_on_message()` 在消息末尾添加 `{"cache_control": {"type": "ephemeral"}}`

**图片格式转换**（第 609-651 行）：
`_convert_image_blocks()` 将 OpenAI 风格的 `image_url` 格式转换为 Anthropic 的 `{"type": "image", "source": {"type": "base64", ...}}` 格式。

#### 2.4.3 结构化输出（第 72-87 行，第 871-965 行）

Anthropic 支持两种结构化输出方式：

1. **原生方式**（Claude 4.5 系列，第 72-87 行）：通过 `ANTHROPIC_STRUCTURED_OUTPUTS_BETA` beta 头 + `output_format` 参数
2. **工具回退方式**（其他模型，第 899-907 行）：将 JSON Schema 包装为 `structured_output` 工具，强制 `tool_choice`

```python
# 原生方式（第 888-898 行）
if _supports_native_structured_outputs(self.model):
    betas.append(ANTHROPIC_STRUCTURED_OUTPUTS_BETA)
    extra_body = {"output_format": {"type": "json_schema", "schema": schema}}

# 工具回退（第 899-907 行）
else:
    structured_tool = {
        "name": "structured_output",
        "description": "Output the structured response",
        "input_schema": schema,
    }
    params["tools"] = [structured_tool]
    params["tool_choice"] = {"type": "tool", "name": "structured_output"}
```

#### 2.4.4 工具转换（第 487-535 行）

`_convert_tools_for_interference()` 将 CrewAI 工具转换为 Anthropic 格式：

```python
anthropic_tool = {
    "name": name,
    "description": description,
    "input_schema": sanitize_tool_params_for_anthropic_strict(parameters)
                     if strict_enabled else parameters
}
```

与 OpenAI 不同，Anthropic 使用 `input_schema`（扁平的 JSON Schema）而非 `function.parameters`（OpenAI 的嵌套格式）。

#### 2.4.5 Tool Search（第 537-579 行）

`_apply_tool_search()` 在工具数量 ≥ 2 时启用：
1. 注入工具搜索工具定义（regex 或 bm25 类型）
2. 所有普通工具标记 `defer_loading: True`，Claude 按需搜索和加载

#### 2.4.6 流式处理（第 1027-1228 行）

Anthropic 的流式处理使用 `client.messages.stream()` 上下文管理器：

1. 文本增量：`event.delta.text`（第 1084-1092 行）
2. 工具调用开始：`event.type == "content_block_start"` 且 `block.type == "tool_use"`（第 1094-1119 行）
3. 工具参数增量：`event.delta.type == "input_json_delta"`，累积 `partial_json`（第 1120-1143 行）
4. Thinking 块提取：`_extract_thinking_block()`（第 1147-1155 行）

#### 2.4.7 Token 用量提取（第 1882-1903 行）

`_extract_anthropic_token_usage()` 从 Anthropic 响应提取用量，包括独有的 `cache_read_input_tokens` 和 `cache_creation_input_tokens`：

```python
result = {
    "input_tokens": input_tokens,
    "output_tokens": output_tokens,
    "total_tokens": input_tokens + output_tokens,
    "cached_prompt_tokens": cache_read_tokens,
    "cache_creation_tokens": cache_creation_tokens,
}
```

#### 2.4.8 工具使用对话流程（第 1307-1419 行）

`_handle_tool_use_conversation()` 实现 Anthropic 的完整工具调用模式：
1. Claude 请求工具使用
2. 执行工具并收集结果
3. 将工具结果以 `tool_result` 格式发送回 Claude
4. Claude 处理结果并生成最终响应

---

### 2.5 LLM 缓存

**文件位置**：`lib/crewai/src/crewai/llms/cache.py`

CrewAI 的缓存系统是**标记式**而非存储式的。它不缓存 LLM 响应本身，而是提供一种通用的标记机制，让上游代码标记哪些消息应该被 LLM Provider 的**提示缓存**（Prompt Caching）机制缓存。

#### 2.5.1 核心概念

```python
CACHE_BREAKPOINT_KEY = "cache_breakpoint"
```

`CACHE_BREAKPOINT_KEY` 是一个特殊的字典键，标记消息中稳定前缀的结束位置。Provider 适配器会将其翻译为对应 API 的缓存指令。

#### 2.5.2 API 函数

- **`mark_cache_breakpoint(message)`**（第 27-32 行）：返回带有缓存标记的新字典（不修改原消息）
- **`strip_cache_breakpoint(message)`**（第 35-37 行）：原地移除缓存标记

#### 2.5.3 各 Provider 的翻译方式

缓存标记在各 Provider 中被翻译为不同的 API 指令：

| Provider | 翻译方式 |
|----------|---------|
| **Anthropic** | `_stamp_cache_control_on_message()` 在消息末尾添加 `{"cache_control": {"type": "ephemeral"}}` |
| **OpenAI** | 自动缓存（无需显式标记），`_format_messages()` 中剥离 `CACHE_BREAKPOINT_KEY` |
| **Gemini** | 自动缓存，剥离标记 |
| **其他** | 在 `_format_messages()` 中统一剥离 `CACHE_BREAKPOINT_KEY`（第 838-839 行），避免污染 API 请求 |

#### 2.5.4 BaseLLM 中的处理

在 `base_llm.py` 的 `_format_messages()` 方法（第 830-843 行）中，每条消息被复制时**主动剥离** `CACHE_BREAKPOINT_KEY`：

```python
copy: dict[str, Any] = {
    k: v for k, v in msg.items() if k != CACHE_BREAKPOINT_KEY
}
```

这确保了缓存标记不会泄露到不支持缓存的 Provider 的 API 请求中。

#### 2.5.5 Anthropic 缓存实现细节

在 `AnthropicCompletion._format_messages_for_anthropic()`（第 653-850 行）中：

1. **读取阶段**（第 674-713 行）：在 `super()._format_messages()` 剥离标记之前，先读取带有 `CACHE_BREAKPOINT_KEY` 的消息
2. **匹配阶段**（第 814-837 行）：通过内容匹配找到格式化后的对应消息
3. **标记阶段**（第 852-868 行）：`_stamp_cache_control_on_message()` 在消息的最后一个内容块上添加 `{"cache_control": {"type": "ephemeral"}}`
4. **System 缓存**（第 839-849 行）：如果 system 消息被标记，转换为 `[{"type": "text", "text": ..., "cache_control": {"type": "ephemeral"}}]` 格式

---

## 3. 完整调用时序图

```
┌──────┐     ┌─────┐     ┌──────────┐     ┌──────────────┐     ┌──────────┐
│ User │     │Agent│     │  LLM.__new__()  │ BaseLLM /    │     │ Provider │
│      │     │     │     │  (工厂)     │     │ Provider     │     │ API      │
└──┬───┘     └──┬──┘     └─────┬──────┘     └──────┬───────┘     └────┬─────┘
   │            │              │                    │                  │
   │ 创建 LLM   │              │                    │                  │
   │───────────>│              │                    │                  │
   │            │ LLM(model)   │                    │                  │
   │            │─────────────>│                    │                  │
   │            │              │                    │                  │
   │            │              │ 解析 provider      │                  │
   │            │              │──┐                 │                  │
   │            │              │<─┘                 │                  │
   │            │              │                    │                  │
   │            │              │ 路由到原生 Provider │                  │
   │            │              │───────────────────>│                  │
   │            │              │                    │ 初始化客户端      │
   │            │              │                    │──┐               │
   │            │              │   返回实例          │<─┘               │
   │            │<─────────────│<───────────────────│                  │
   │            │              │                    │                  │
   │ 执行任务   │              │                    │                  │
   │───────────>│              │                    │                  │
   │            │ llm.call()   │                    │                  │
   │            │──────────────┼───────────────────>│                  │
   │            │              │                    │                  │
   │            │              │         llm_call_context()             │
   │            │              │              ┌─────┐                  │
   │            │              │              │call_id│                │
   │            │              │              └─────┘                  │
   │            │              │                    │                  │
   │            │              │   _emit_call_started_event()          │
   │            │              │   ──────────────────>                 │
   │            │              │   (crewai_event_bus)                  │
   │            │              │                    │                  │
   │            │              │   _format_messages()                  │
   │            │              │   ──────────────────>                 │
   │            │              │   (剥离缓存标记)     │                  │
   │            │              │                    │                  │
   │            │              │   _invoke_before_llm_call_hooks()     │
   │            │              │   ──────────────────>                 │
   │            │              │                    │                  │
   │            │              │   _prepare_completion_params()        │
   │            │              │   ──────────────────>                 │
   │            │              │                    │                  │
   │            │              │                    │  API Request     │
   │            │              │                    │─────────────────>│
   │            │              │                    │                  │
   │            │              │                    │  API Response    │
   │            │              │                    │<─────────────────│
   │            │              │                    │                  │
   │            │              │                    │ _track_token_    │
   │            │              │                    │ usage_internal() │
   │            │              │                    │──┐               │
   │            │              │                    │<─┘               │
   │            │              │                    │                  │
   │            │              │   _apply_stop_words()                 │
   │            │              │   ──────────────────>                 │
   │            │              │                    │                  │
   │            │              │   _invoke_after_llm_call_hooks()      │
   │            │              │   ──────────────────>                 │
   │            │              │                    │                  │
   │            │              │   _emit_call_completed_event()        │
   │            │              │   ──────────────────>                 │
   │            │              │   (crewai_event_bus)                  │
   │            │              │                    │                  │
   │            │   返回结果   │                    │                  │
   │            │<─────────────┼────────────────────│                  │
   │            │              │                    │                  │
```

**流式调用时序**（非流式步骤 7 之后）：

```
   │            │              │                    │                  │
   │            │              │   _handle_streaming_completion()      │
   │            │              │   ──────────────────>                 │
   │            │              │                    │                  │
   │            │              │                    │ Stream Request   │
   │            │              │                    │─────────────────>│
   │            │              │                    │                  │
   │            │              │                    │  Chunk 1         │
   │            │              │                    │<─────────────────│
   │            │              │  _emit_stream_chunk_event()           │
   │            │              │  ──────────────────>                  │
   │            │              │  (crewai_event_bus)                   │
   │            │              │                    │                  │
   │            │              │                    │  Chunk 2 (tool)  │
   │            │              │                    │<─────────────────│
   │            │              │  _emit_stream_chunk_event(TOOL_CALL)  │
   │            │              │  ──────────────────>                  │
   │            │              │                    │                  │
   │            │  ...更多 chunks ...              │                  │
   │            │              │                    │                  │
   │            │              │                    │  Chunk N (usage) │
   │            │              │                    │<─────────────────│
   │            │              │  _emit_call_completed_event()         │
   │            │              │  ──────────────────>                  │
```

---

## 4. 完整可运行示例

### 示例 1：使用 OpenAI 原生 SDK 调用

```python
"""示例 1：通过 LLM 工厂创建 OpenAI 原生 SDK 实例并调用"""
import os
from crewai.llm import LLM

# 设置 API Key（实际使用时设置为你的真实 key）
os.environ["OPENAI_API_KEY"] = "sk-your-key-here"

# 方式 1：使用 provider/model 前缀格式
llm = LLM(model="openai/gpt-4o-mini", temperature=0.7)

# 方式 2：直接使用模型名（自动推断 provider）
llm2 = LLM(model="gpt-4o-mini")

# 方式 3：显式指定 provider
llm3 = LLM(model="gpt-4o-mini", provider="openai")

# 调用 LLM
response = llm.call(messages="Hello, what is the capital of France?")
print(f"Response: {response}")

# 使用消息列表格式
messages = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "What is 2+2?"},
]
response2 = llm.call(messages=messages)
print(f"Response2: {response2}")

# 查看 token 用量
usage = llm.get_token_usage_summary()
print(f"Token usage: {usage}")
```

### 示例 2：使用 Anthropic 原生 SDK 调用

```python
"""示例 2：通过 LLM 工厂创建 Anthropic 原生 SDK 实例"""
import os
from crewai.llm import LLM

os.environ["ANTHROPIC_API_KEY"] = "sk-ant-your-key-here"

# 创建 Anthropic LLM 实例
llm = LLM(
    model="anthropic/claude-3-5-sonnet-20241022",
    temperature=0.7,
    max_tokens=1024,
)

# 基本调用
response = llm.call(messages="Explain quantum computing in one sentence.")
print(f"Response: {response}")

# 带 stop sequences 的调用
llm_with_stop = LLM(
    model="anthropic/claude-3-5-sonnet-20241022",
    stop=["END", "STOP"],
)
response2 = llm_with_stop.call(
    messages="Write a short story ending with END."
)
print(f"Response (with stop): {response2}")
```

### 示例 3：使用 LiteLLM 回退路径

```python
"""示例 3：使用 LiteLLM 回退路径（需要在 pip install litellm 之后）"""
import os
from crewai.llm import LLM

os.environ["OPENAI_API_KEY"] = "sk-your-key-here"

# 对于不被原生 SDK 支持的模型，自动回退到 LiteLLM
# 例如：使用 openrouter 的非标准模型
llm = LLM(
    model="openrouter/deepseek/deepseek-chat",
    temperature=0.5,
    max_tokens=500,
)

# 流式调用
llm_stream = LLM(
    model="gpt-4o-mini",
    stream=True,
)

response = llm_stream.call(
    messages="Count from 1 to 5, one number per line."
)
print(f"Streaming response: {response}")
```

### 示例 4：结构化输出

```python
"""示例 4：使用 response_model 获取结构化输出"""
import os
from pydantic import BaseModel, Field
from crewai.llm import LLM

os.environ["OPENAI_API_KEY"] = "sk-your-key-here"


class WeatherReport(BaseModel):
    """天气报告模型"""
    city: str = Field(description="城市名称")
    temperature: float = Field(description="温度（摄氏度）")
    condition: str = Field(description="天气状况，如 sunny、rainy、cloudy")
    humidity: int = Field(description="湿度百分比")


# 创建 LLM 实例
llm = LLM(model="openai/gpt-4o-mini", temperature=0)

# 使用 response_model 获取结构化输出
result = llm.call(
    messages="What's the weather like in Tokyo today?",
    response_model=WeatherReport,
)
print(f"Type: {type(result)}")
print(f"City: {result.city}")
print(f"Temperature: {result.temperature}°C")
print(f"Condition: {result.condition}")
print(f"Humidity: {result.humidity}%")
```

### 示例 5：带工具调用的完整流程

```python
"""示例 5：使用工具调用（Function Calling）"""
import os
import json
from crewai.llm import LLM

os.environ["OPENAI_API_KEY"] = "sk-your-key-here"


def get_current_weather(location: str, unit: str = "celsius") -> str:
    """获取指定位置的当前天气"""
    # 模拟天气数据
    weather_data = {
        "Beijing": {"temp": 28, "condition": "sunny", "humidity": 45},
        "Shanghai": {"temp": 32, "condition": "cloudy", "humidity": 70},
    }
    data = weather_data.get(location, {"temp": 25, "condition": "unknown", "humidity": 50})
    return json.dumps({
        "location": location,
        "temperature": data["temp"],
        "unit": unit,
        "condition": data["condition"],
        "humidity": data["humidity"],
    })


# 定义工具 schema（OpenAI 格式）
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_current_weather",
            "description": "Get the current weather in a given location",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "The city name, e.g. Beijing",
                    },
                    "unit": {
                        "type": "string",
                        "enum": ["celsius", "fahrenheit"],
                    },
                },
                "required": ["location"],
            },
        },
    }
]

# 创建 LLM 实例
llm = LLM(model="openai/gpt-4o-mini", temperature=0)

# 调用 LLM 并传入工具
response = llm.call(
    messages="What's the weather in Beijing?",
    tools=tools,
    available_functions={"get_current_weather": get_current_weather},
)

print(f"Tool call result: {response}")
```

---

## 5. 设计亮点与注意事项

### 设计亮点

1. **工厂模式 + 路由分派**：`LLM.__new__()` 在对象创建阶段就完成 Provider 路由，用户无需关心底层实现。`openai/gpt-4o` 和 `anthropic/claude-3-5-sonnet` 通过同一接口创建，自动路由到不同的原生 SDK。

2. **双路径策略（原生 SDK + LiteLLM 回退）**：原生 SDK 路径提供更好的性能和功能支持（如 Anthropic 的 thinking、tool_search），LiteLLM 回退提供 100+ 模型的广泛兼容性。

3. **上下文变量（contextvars）实现线程安全**：`call_stop_override` 和 `call_stream_override` 使用 `contextvars` 而非实例属性，确保在并发场景下（如多个 Agent 共享同一 LLM 实例）不会相互干扰。

4. **事件驱动架构**：通过 `crewai_event_bus` 发射所有 LLM 调用事件，支持可观测性（日志、追踪、监控）的扩展，而不侵入核心调用逻辑。

5. **Provier 无关的缓存标记**：`CACHE_BREAKPOINT_KEY` 提供统一的缓存标记接口，各 Provider 自行翻译为各自的 API 指令（Anthropic 的 `cache_control`、OpenAI 的自动缓存等）。

6. **延迟加载 LiteLLM**：`_ensure_litellm()` 采用惰性导入，避免 LiteLLM 的 `dotenv.load_dotenv()` 在模块导入时覆盖环境变量，解决了 `MODEL=` 环境变量污染 embedder 模型名的问题。

7. **流式工具调用累积**：`AccumulatedToolArgs` 和 `defaultdict[int, AccumulatedToolArgs]` 设计优雅地处理了流式 API 中工具调用参数分散在多个 chunk 中的问题，在 JSON 完整时立即执行，减少了等待时间。

8. **Stop Words 统一处理**：`_apply_stop_words()` 在基类中实现，扫描最早出现的 stop word 并截断响应，所有 Provider 共享一致的 stop 行为。

### 注意事项

1. **API Key 必须设置**：各 Provider 需要对应的环境变量（`OPENAI_API_KEY`、`ANTHROPIC_API_KEY` 等），`BaseLLM` 不会自动加载，需要用户在调用前设置。

2. **LiteLLM 不是默认依赖**：需要 `pip install litellm` 或 `uv add 'crewai[litellm]'` 才能使用回退路径。如果原生 SDK 和 LiteLLM 都不可用，`LLM.__new__()` 会抛出 `ImportError`。

3. **o1 模型的 system 消息限制**：o1 系列模型不支持 system 角色，代码中自动将 system 消息转为 user 或 assistant 角色。使用 o1 模型时需要注意这一行为差异。

4. **Anthropic 消息格式严格**：Anthropic 要求消息以 user 开始、user/assistant 交替，且工具结果必须在 user 消息中。`_format_messages_for_anthropic()` 会自动处理这些转换，但多轮工具调用时需要注意消息顺序。

5. **上下文窗口使用 85%**：`CONTEXT_WINDOW_USAGE_RATIO = 0.85` 意味着实际使用的上下文窗口只有模型最大值的 85%，留出空间给响应输出。

6. **缓存标记是单向的**：`CACHE_BREAKPOINT_KEY` 只在消息格式化时被读取，然后被剥离。如果需要在多次调用中重用缓存标记，需要每次重新设置。

7. **流式响应中的空内容处理**：`_handle_streaming_response()` 在收到 chunk 但无内容时会尝试回退到非流式模式（第 930-943 行），这是对某些 API 边缘情况的防御性处理。

8. **`additional_params` 的自动收集**：`BaseLLM._validate_init_fields()` 会将未识别的字段自动收集到 `additional_params`，这意味着拼写错误的字段名会被静默地传递到 API 调用中，可能导致意外行为。