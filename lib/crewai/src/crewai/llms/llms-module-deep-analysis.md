# CrewAI LLM 抽象层模块 — 深度源码实现分析

> 面向小白，逐层逐方法拆解 `lib/crewai/src/crewai/llms/` 的全部实现逻辑

---

## 目录

- [0. 整体概述：这个模块要解决什么问题](#0-整体概述这个模块要解决什么问题)
- [1. 三层架构总览](#1-三层架构总览)
- [2. 顶层：`llm.py` — LLM 类的工厂路由](#2-顶层llmpy--llm-类的工厂路由)
- [3. 中层：`base_llm.py` — BaseLLM 抽象基类](#3-中层base_llmpy--basellm-抽象基类)
- [4. 底层（一）：`providers/openai/completion.py` — OpenAICompletion](#4-底层一providersopenaicompletionpy--openaicompletion)
- [5. 底层（二）：其余 Provider 子类](#5-底层二其余-provider-子类)
- [6. 支撑层：`constants.py` / `cache.py` / `hooks` / `utils`](#6-支撑层constantspy--cachepy--hooks--utils)
- [7. 完整调用链路（从用户代码到 AI 返回结果）](#7-完整调用链路从用户代码到-ai-返回结果)

---

## 0. 整体概述：这个模块要解决什么问题

### 需求串讲

想象你是一个快递公司，你的客户要把包裹寄到全国各地。但是每个目的地的快递公司不同：寄到北京用顺丰，寄到上海用圆通，寄到美国用 DHL。如果让客户自己去找对应的快递公司，他会很烦。

CrewAI 的 LLM 模块就是这个"快递中转站"。用户只需要说"我要用 gpt-4o"，模块内部会自动找到 OpenAI 的 SDK 去调用；用户说"我要用 claude-3.5-sonnet"，模块会自动找到 Anthropic 的 SDK。对用户来说，调用方式完全一样，他不需要关心底层是谁。

**核心问题**：如何让用户用一行代码 `LLM(model="gpt-4o")` 就能调用任何大模型？

**解决方案**：三层架构 — 工厂路由（顶层）→ 抽象基类（中层）→ 具体实现（底层）。

---

## 1. 三层架构总览

```
┌──────────────────────────────────────────────────────────────┐
│                    顶层：llm.py                               │
│              LLM.__new__() 工厂路由                           │
│   "用户说 gpt-4o → 我帮你找到 OpenAICompletion"                │
│   "用户说 claude-3 → 我帮你找到 AnthropicCompletion"           │
│   "都不认识 → 我帮你用 LiteLLM 兼容层"                         │
├──────────────────────────────────────────────────────────────┤
│                    中层：base_llm.py                          │
│              BaseLLM 抽象基类                                 │
│   定义所有 Provider 必须遵守的"规矩"：                          │
│   - 必须实现 call() 方法                                      │
│   - 自动发射事件（Started / Completed / Failed）               │
│   - 提供 contextvars 线程安全上下文                            │
│   - 提供工具执行封装                                          │
│   - 提供 stop 词截断                                          │
├──────────────────────────────────────────────────────────────┤
│                    底层：providers/                           │
│   ┌──────────┬──────────┬──────────┬──────────┬──────────┐   │
│   │  OpenAI  │Anthropic │  Azure   │ Gemini   │ Bedrock  │   │
│   │Completion│Completion│Completion│Completion│Completion│   │
│   └──────────┴──────────┴──────────┴──────────┴──────────┘   │
│            每个都是 BaseLLM 的子类，实现 call()                 │
│            用自己的 SDK 直连对应的大模型                        │
├──────────────────────────────────────────────────────────────┤
│                    支撑层                                     │
│   constants.py  → 模型名白名单                                │
│   cache.py      → 缓存断点标记                                │
│   hooks/        → HTTP 请求/响应拦截器                         │
│   providers/utils/ → 工具转换公共函数                          │
└──────────────────────────────────────────────────────────────┘
```

**调用关系图**：

```
用户代码
  │
  ▼
LLM(model="gpt-4o")          ← 顶层：工厂路由
  │
  ▼
OpenAICompletion(model="gpt-4o")  ← 底层：具体实现
  │
  ├── 继承 BaseLLM 的字段和方法   ← 中层：抽象基类
  │
  ├── call(messages) 被调用
  │     │
  │     ├── llm_call_context()       ← 设置调用上下文
  │     ├── _emit_call_started_event()  ← 发射事件
  │     ├── OpenAI SDK 发起 HTTP 请求   ← 实际调用
  │     ├── _emit_call_completed_event() ← 发射事件
  │     └── 返回结果
  │
  └── 返回给用户
```

---

## 2. 顶层：`llm.py` — LLM 类的工厂路由

### 2.1 需求串讲

**问题**：用户告诉我 "gpt-4o"，我怎么知道要创建 `OpenAICompletion` 还是 `AnthropicCompletion`？如果用户写了 100 种模型名，我难道要写 100 个 if-else？

**解决思路**：用 Python 的 `__new__` 方法（不是 `__init__`）在对象创建之前拦截，根据模型名"路由"到正确的 Provider 子类。

**通俗理解**：`__new__` 是房子的"建筑商"，`__init__` 是"装修队"。建筑商决定建什么类型的房子（OpenAI 风格还是 Anthropic 风格），装修队再进去装修（设置 temperature、max_tokens 等参数）。

### 2.2 源码位置

[llm.py#L368-L512](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/llm.py#L368-L512)

### 2.3 逐行解析

#### 第一步：LLM 类定义

```python
class LLM(BaseLLM):
    llm_type: Literal["litellm"] = "litellm"
    # ... 字段定义 ...
```

**解释**：`LLM` 类继承自 `BaseLLM`。注意这里 `LLM` 是 LiteLLM 回退方案的代表，它的 `llm_type` 是 `"litellm"`。但有趣的是，`LLM.__new__()` 大部分时候不会返回 `LLM` 实例，而是返回 `OpenAICompletion` 等子类实例。`LLM` 本身只在找不到匹配的 Native Provider 时才被创建。

#### 第二步：`__new__` 方法 — 核心路由逻辑

```python
def __new__(cls, model: str, is_litellm: bool = False, **kwargs: Any) -> LLM:
    if not model or not isinstance(model, str):
        raise ValueError("Model must be a non-empty string")
```

**解释**：第一行检查，model 必须是字符串。比如 `LLM(model="gpt-4o")` 合法，`LLM(model=123)` 报错。

**路由优先级 1：custom_openai**

```python
    custom_openai = bool(kwargs.pop("custom_openai", False))
    if custom_openai:
        if not cls._has_custom_openai_endpoint(kwargs):
            raise ValueError("custom_openai=True requires base_url...")
        provider = "openai"
        use_native = True
```

**解释**：如果用户传了 `custom_openai=True`，说明用户有自己的 OpenAI 兼容服务（比如 Azure OpenAI 或者本地部署的 vLLM）。这时强制走 OpenAI Provider，但必须提供 `base_url`。

**通俗理解**：用户说"我虽然用的是 OpenAI 的接口格式，但服务器是我自己的"，框架说"好的，那我还是用 OpenAI 的 SDK 去连你的服务器"。

**路由优先级 2：显式 provider**

```python
    elif explicit_provider:
        provider = explicit_provider
        use_native = True
        model_string = model
```

**解释**：如果用户传了 `provider="anthropic"`，就直接用 Anthropic Provider。

**路由优先级 3：模型名含 "/"**

```python
    elif "/" in model:
        prefix, _, model_part = model.partition("/")
        
        provider_mapping = {
            "openai": "openai",
            "anthropic": "anthropic",
            "claude": "anthropic",
            "azure": "azure",
            "azure_openai": "azure",
            "google": "gemini",
            "gemini": "gemini",
            "bedrock": "bedrock",
            "aws": "bedrock",
            "openrouter": "openrouter",
            "deepseek": "deepseek",
            "ollama": "ollama",
            "ollama_chat": "ollama_chat",
            "hosted_vllm": "hosted_vllm",
            "cerebras": "cerebras",
            "dashscope": "dashscope",
            "snowflake": "snowflake",
        }
        
        canonical_provider = provider_mapping.get(prefix.lower())
```

**解释**：这是最常用的路由方式。用户写 `LLM(model="openai/gpt-4o")`，`model.partition("/")` 把字符串切成三块：`("openai", "/", "gpt-4o")`。

`provider_mapping` 是一个字典，把用户可能写的各种前缀映射到统一的 provider 名。比如用户写 `"claude/xxx"` 和 `"anthropic/xxx"`，都会映射到 `"anthropic"`。

**通俗理解**：就像快递单上写"顺丰/北京市"，快递站看到"顺丰"就知道走顺丰的流程。

然后判断这个模型名是否在 Native Provider 的白名单中：

```python
        valid_native_model = bool(
            canonical_provider
            and cls._validate_model_in_constants(model_part, canonical_provider)
        )
```

**解释**：`_validate_model_in_constants` 会去 `constants.py` 里查，比如 `"gpt-4o"` 在 `OPENAI_MODELS` 列表中，所以返回 True。如果模型名不在白名单中（比如很新的模型），但用户设置了 `base_url`，也会走 custom_openai 模式。

**路由优先级 4：从模型名推断 provider**

```python
    else:
        provider = cls._infer_provider_from_model(model)
        use_native = True
        model_string = model
```

**解释**：用户直接写 `LLM(model="gpt-4o")`，不含 "/"。`_infer_provider_from_model` 方法会检查模型名的前缀：

```python
@classmethod
def _matches_provider_pattern(cls, model: str, provider: str) -> bool:
    model_lower = model.lower()
    if provider == "openai":
        return any(model_lower.startswith(prefix) for prefix in ["gpt-", "o1", "o3", "o4", "whisper-"])
    if provider == "anthropic" or provider == "claude":
        return any(model_lower.startswith(prefix) for prefix in ["claude-", "anthropic."])
    if provider == "gemini" or provider == "google":
        return any(model_lower.startswith(prefix) for prefix in ["gemini-", "gemma-", "learnlm-"])
```

**通俗理解**：就像你看到"gpt-4o"这个名字，就知道它是 OpenAI 的模型；看到"claude-3"就知道是 Anthropic 的。框架也是这样"猜"的。

#### 第三步：创建 Native Provider 实例

```python
    native_class = cls._get_native_provider(provider) if use_native else None
    if native_class and not is_litellm and provider in SUPPORTED_NATIVE_PROVIDERS:
        try:
            kwargs_copy = {k: v for k, v in kwargs.items() if k != "provider"}
            if custom_openai_route:
                kwargs_copy["custom_openai"] = True
            return cast(
                Self,
                native_class(model=model_string, provider=provider, **kwargs_copy),
            )
```

**解释**：`_get_native_provider("openai")` 返回 `OpenAICompletion` 类。然后 `native_class(model="gpt-4o", provider="openai", **kwargs)` 创建 `OpenAICompletion` 实例并返回。

**重点**：`__new__` 返回的不是 `LLM` 类实例，而是 `OpenAICompletion` 实例！这就是工厂模式的核心。

#### 第四步：回退到 LiteLLM

```python
    # FALLBACK to LiteLLM
    if not _ensure_litellm():
        raise ImportError(...)
    return object.__new__(cls)
```

**解释**：如果找不到 Native Provider，就回退到 LiteLLM。LiteLLM 是一个第三方库，兼容 100+ 种大模型。`object.__new__(cls)` 创建一个 `LLM` 实例（此时 `LLM` 自己作为 LiteLLM 的适配器）。

### 2.4 完整路由流程图

```
LLM(model="gpt-4o")
  │
  ├── 检查 model 是否为空 → 否
  ├── 检查 custom_openai → 否
  ├── 检查显式 provider → 否
  ├── 检查是否含 "/" → 否
  ├── _infer_provider_from_model("gpt-4o")
  │     └── "gpt-" 开头 → provider="openai"
  ├── _get_native_provider("openai") → OpenAICompletion 类
  ├── OpenAICompletion(model="gpt-4o", provider="openai")
  │     └── 返回 OpenAICompletion 实例
  └── 用户拿到的是 OpenAICompletion 实例（不是 LLM 实例！）

LLM(model="ollama/llama3")
  │
  ├── 检查是否含 "/" → 是，prefix="ollama"
  ├── provider_mapping["ollama"] → 不存在
  ├── use_native=False
  ├── 回退到 LiteLLM
  └── 返回 LLM 实例（LiteLLM 适配器）
```

---

## 3. 中层：`base_llm.py` — BaseLLM 抽象基类

### 3.1 需求串讲

**问题**：我们有 6 个不同的 Provider（OpenAI、Anthropic、Azure、Gemini、Bedrock、Snowflake），每个 Provider 都要做同样的事情：发射开始事件、调用 API、发射完成事件、处理工具调用、处理 stop 词。如果每个 Provider 都写一遍这些逻辑，代码会非常冗余。

**解决思路**：把这些公共逻辑抽到一个抽象基类 `BaseLLM` 中，Provider 子类只需要实现 `call()` 方法，其他公共逻辑全部继承。

**通俗理解**：BaseLLM 就像一个"标准操作手册"，规定了所有 Provider 必须遵守的流程。每个 Provider 只负责"打电话给 AI"这一步，而"打电话前记录日志"、"打电话后记录结果"这些步骤都是手册规定好的，自动执行。

### 3.2 源码位置

[base_llm.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/llms/base_llm.py)（全文件 800+ 行）

### 3.3 逐组件解析

---

#### 组件 A：contextvars 线程安全上下文

**需求串讲**：CrewAI 支持并发执行多个 Agent。Agent A 和 Agent B 同时调用 LLM，如果用一个全局变量记录"当前是谁在调用"，就会互相覆盖。必须有一种机制让每个调用有独立的上下文。

**源码位置**：[base_llm.py#L79-L98](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/llms/base_llm.py#L79-L98)

```python
_current_call_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "_current_call_id", default=None
)
_call_stop_override_var: contextvars.ContextVar[dict[int, list[str]] | None] = (
    contextvars.ContextVar("_call_stop_override_var", default=None)
)
_call_stream_override_var: contextvars.ContextVar[dict[int, bool] | None] = (
    contextvars.ContextVar("_call_stream_override_var", default=None)
)
```

**解释**：`contextvars.ContextVar` 是 Python 3.7+ 提供的机制，每个协程（asyncio Task）有自己独立的上下文，互不干扰。

**通俗理解**：想象一个酒店，每个房间有自己的电话分机。`contextvars` 就是每个房间的分机号码——你打房间 301 的电话，不会串到房间 302。

```python
@contextmanager
def llm_call_context() -> Generator[str, None, None]:
    """上下文管理器，为每次 LLM 调用创建独立的 call_id"""
    call_id = str(uuid.uuid4())           # 生成唯一 ID
    token = _current_call_id.set(call_id)  # 设置当前上下文
    try:
        yield call_id                     # 让调用代码执行
    finally:
        _current_call_id.reset(token)     # 恢复之前的上下文
```

**执行流程**：

```
with llm_call_context() as call_id:
    # call_id = "abc-123"
    # 在这个 with 块内，_current_call_id.get() 返回 "abc-123"
    llm.call(messages)
    # 调用完成
# 退出 with 块后，_current_call_id 恢复为之前的值
```

**为什么这样设计**：如果 Agent A 调用 LLM 时 crash 了，`finally` 块确保上下文被恢复，不会污染其他 Agent 的调用。

---

#### 组件 B：stop_sequences 的 per-instance 覆盖

**需求串讲**：同一个 Agent 可能有两个 LLM 实例：`llm`（主 LLM）和 `function_calling_llm`（工具调用 LLM）。调用时可能需要给它们设置不同的 stop 词。但不能直接修改实例的 `stop` 属性（因为两个调用可能并发）。

**源码位置**：[base_llm.py#L101-L123](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/llms/base_llm.py#L101-L123)

```python
@contextmanager
def call_stop_override(llm: BaseLLM, stop: list[str] | None) -> Generator[None, None, None]:
    """在当前调用中临时覆盖 llm 的 stop 列表"""
    current = _call_stop_override_var.get()
    new_overrides: dict[int, list[str]] = dict(current) if current else {}
    if stop is None:
        new_overrides.pop(id(llm), None)   # 清除覆盖
    else:
        new_overrides[id(llm)] = stop      # 设置覆盖（用 id(llm) 作为 key）
    token = _call_stop_override_var.set(new_overrides)
    try:
        yield
    finally:
        _call_stop_override_var.reset(token)
```

**解释**：`id(llm)` 是 Python 内置函数，返回对象的内存地址，是唯一的。用 `id(llm)` 作为 key，可以区分不同的 LLM 实例。

**stop_sequences 属性**（源码位置：[base_llm.py#L221-L235](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/llms/base_llm.py#L221-L235)）：

```python
@property
def stop_sequences(self) -> list[str]:
    """获取当前调用的 stop 列表"""
    overrides = _call_stop_override_var.get()
    if overrides is not None:
        override = overrides.get(id(self))
        if override is not None:
            return override          # 有覆盖 → 用覆盖的值
    return self.stop                 # 没有覆盖 → 用实例默认值
```

**执行流程**：

```
场景：Agent 有 llm 和 function_calling_llm 两个实例

with call_stop_override(llm, ["Observation:"]):
    # llm.stop_sequences 返回 ["Observation:"]
    # function_calling_llm.stop_sequences 返回它自己的 stop 列表
    llm.call(messages)
```

---

#### 组件 C：事件发射模板方法

**需求串讲**：每次 LLM 调用都要发射事件（Started、Completed、Failed、StreamChunk），让监控系统知道发生了什么。如果每个 Provider 都自己写事件发射代码，容易出现遗漏或不一致。

**源码位置**：[base_llm.py#L545-L712](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/llms/base_llm.py#L545-L712)

BaseLLM 提供了 5 个事件发射模板方法：

```python
# 1. 调用开始
def _emit_call_started_event(self, messages, tools, from_task, from_agent, ...):
    crewai_event_bus.emit(self, event=LLMCallStartedEvent(
        model=self.model,
        call_id=get_current_call_id(),  # 从 contextvars 获取
        messages=to_serializable(messages),
        temperature=temperature,
        max_tokens=max_tokens,
        stream=stream,
        ...
    ))

# 2. 调用完成
def _emit_call_completed_event(self, response, call_type, usage, finish_reason, ...):
    crewai_event_bus.emit(self, event=LLMCallCompletedEvent(
        response=to_serializable(response),
        call_type=call_type,  # LLM_CALL 或 TOOL_CALL
        model=self.model,
        call_id=get_current_call_id(),
        usage=usage,          # {"prompt_tokens": 100, "completion_tokens": 50}
        ...
    ))

# 3. 调用失败
def _emit_call_failed_event(self, error, from_task, from_agent):
    crewai_event_bus.emit(self, event=LLMCallFailedEvent(
        error=error,
        model=self.model,
        call_id=get_current_call_id(),
        ...
    ))

# 4. 流式 chunk
def _emit_stream_chunk_event(self, chunk, tool_call, response_id, ...):
    crewai_event_bus.emit(self, event=LLMStreamChunkEvent(
        chunk=chunk,
        response_id=response_id,  # 同一个响应的所有 chunk 共享这个 ID
        ...
    ))

# 5. 推理 chunk（如 Claude 的 thinking）
def _emit_thinking_chunk_event(self, chunk, response_id, ...):
    crewai_event_bus.emit(self, event=LLMThinkingChunkEvent(
        chunk=chunk,
        ...
    ))
```

**通俗理解**：这些方法就像快递公司的"扫码枪"。快递员取件时扫一下（Started），送到时扫一下（Completed），丢件时记录（Failed）。每个快递员用的都是同一套扫码流程，不需要自己发明。

---

#### 组件 D：工具执行封装

**需求串讲**：LLM 可能会要求调用工具（如搜索、计算器）。工具调用的流程是：记录开始 → 执行函数 → 记录结果 → 如失败则记录错误。这个流程对所有 Provider 都一样。

**源码位置**：[base_llm.py#L714-L800](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/llms/base_llm.py#L714-L800)

```python
def _handle_tool_execution(
    self, function_name, function_args, available_functions, from_task, from_agent
) -> str | None:
    """执行 LLM 请求的工具调用"""
    
    # 1. 检查函数是否存在
    if function_name not in available_functions:
        logging.warning(f"Function '{function_name}' not found")
        return None
    
    try:
        started_at = datetime.now()
        
        # 2. 发射 ToolUsageStartedEvent
        crewai_event_bus.emit(self, event=ToolUsageStartedEvent(
            tool_name=function_name,
            tool_args=function_args,
            from_agent=from_agent,
            from_task=from_task,
        ))
        
        # 3. 执行函数
        fn = available_functions[function_name]
        result = fn(**function_args)
        
        # 4. 发射 ToolUsageFinishedEvent
        crewai_event_bus.emit(self, event=ToolUsageFinishedEvent(
            output=result,
            tool_name=function_name,
            tool_args=function_args,
            started_at=started_at,
            finished_at=datetime.now(),
            from_task=from_task,
            from_agent=from_agent,
        ))
        
        # 5. 发射 LLMCallCompletedEvent（call_type=TOOL_CALL）
        self._emit_call_completed_event(
            response=result,
            call_type=LLMCallType.TOOL_CALL,
        )
        
        return str(result) if not isinstance(result, str) else result
    
    except Exception as e:
        # 6. 发射 ToolUsageErrorEvent
        crewai_event_bus.emit(self, event=ToolUsageErrorEvent(
            tool_name=function_name,
            tool_args=function_args,
            error=str(e),
            ...
        ))
        self._emit_call_failed_event(error=str(e))
```

**执行流程时序**：

```
LLM 返回 tool_calls: [{"name": "search", "args": {"query": "AI"}}]
  │
  ├── 1. 检查 "search" 是否在 available_functions 中
  ├── 2. 发射 ToolUsageStartedEvent
  ├── 3. fn = available_functions["search"]
  │      result = fn(query="AI")  → "搜索结果: ..."
  ├── 4. 发射 ToolUsageFinishedEvent
  └── 5. 返回 "搜索结果: ..."
```

---

#### 组件 E：stop 词截断

**需求串讲**：CrewAI 的 Agent 使用 ReAct 模式，LLM 输出格式是：
```
Thought: 我需要搜索
Action: search
Action Input: {"query": "AI"}
Observation: 搜索结果...
```

如果 LLM 在 `Observation:` 之后继续生成内容（幻觉），Agent 的解析器会出错。所以需要在 LLM 返回后，在第一个 stop 词处截断。

**源码位置**：[base_llm.py#L452-L492](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/llms/base_llm.py#L452-L492)

```python
def _apply_stop_words(self, content: str) -> str:
    """在第一个 stop 词处截断"""
    stops = self.stop_sequences
    if not stops or not content:
        return content
    
    earliest_stop_pos = len(content)
    found_stop_word = None
    
    # 遍历所有 stop 词，找到最早出现的位置
    for stop_word in stops:
        stop_pos = content.find(stop_word)
        if stop_pos != -1 and stop_pos < earliest_stop_pos:
            earliest_stop_pos = stop_pos
            found_stop_word = stop_word
    
    # 截断
    if found_stop_word is not None:
        truncated = content[:earliest_stop_pos].strip()
        return truncated
    
    return content
```

**示例**：

```python
content = "Thought: 我需要搜索\nAction: search\nObservation: 搜索结果..."
stops = ["Observation:", "Final Answer:"]

# _apply_stop_words(content) 返回:
# "Thought: 我需要搜索\nAction: search"
```

---

#### 组件 F：BaseLLM 的字段定义

**源码位置**：[base_llm.py#L150-L190](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/llms/base_llm.py#L150-L190)

```python
class BaseLLM(BaseModel, ABC):
    """所有 LLM 实现的抽象基类"""
    
    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)
    
    # 核心字段
    llm_type: str = "base"
    model: str                          # 模型名
    temperature: float | None = None
    max_tokens: int | float | None = None
    stream: bool | None = None
    stop: list[str] = Field(default_factory=list)
    api_key: str | None = None
    base_url: str | None = None
    provider: str = Field(default="openai")
    
    # 抽象方法
    @abstractmethod
    def call(self, messages, tools=None, ...) -> str | Any:
        """子类必须实现"""
    
    # 异步调用（可选实现）
    async def acall(self, messages, ...) -> str | Any:
        raise NotImplementedError
```

**为什么继承 `BaseModel + ABC`**：`BaseModel` 提供 Pydantic 的序列化和校验，`ABC` 提供抽象方法的强制约束。

---

## 4. 底层（一）：`providers/openai/completion.py` — OpenAICompletion

### 4.1 需求串讲

**问题**：OpenAI 有 Chat Completions API 和 Responses API 两种，还有流式和非流式，还有结构化输出（response_model）。如何在一个类中优雅地支持所有这些模式？

**解决思路**：`call()` 方法作为入口，根据配置分流到不同的内部方法。`_handle_completion` 处理非流式，`_handle_streaming_completion` 处理流式。有 `response_model` 时走 `beta.chat.completions.parse`。

### 4.2 源码位置

[openai/completion.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/llms/providers/openai/completion.py)（全文件 2000+ 行）

### 4.3 逐组件解析

---

#### 组件 A：类定义和字段

```python
class OpenAICompletion(BaseLLM):
    """OpenAI 原生 SDK 实现"""
    
    llm_type: Literal["openai"] = "openai"
    model: str = "gpt-4o"
    
    # OpenAI 专属字段
    organization: str | None = None      # 组织 ID
    project: str | None = None           # 项目 ID
    timeout: float | None = None         # 超时时间
    max_retries: int = 2                 # 重试次数
    max_completion_tokens: int | None = None  # 最大输出 token
    response_format: JsonResponseFormat | type[BaseModel] | None = None
    reasoning_effort: str | None = None  # 推理强度（o1/o3 模型）
    
    # API 选择
    api: Literal["completions", "responses"] = "completions"
    
    # 内置工具（Responses API 专用）
    builtin_tools: list[str] | None = None  # ["web_search", "file_search", "code_interpreter"]
    parse_tool_outputs: bool = False
    auto_chain: bool = False               # 自动链式多轮对话
    
    # 私有属性
    _client: Any = PrivateAttr(default=None)       # 同步客户端
    _async_client: Any = PrivateAttr(default=None) # 异步客户端
    _last_response_id: str | None = PrivateAttr(default=None)  # 链式对话 ID
```

**解释**：`PrivateAttr` 是 Pydantic 的私有属性，不会参与序列化，也不会暴露给用户。`_client` 是 OpenAI SDK 的客户端实例，`_last_response_id` 是 Responses API 多轮对话的上下文 ID。

---

#### 组件 B：初始化 — 创建 HTTP 客户端

```python
@model_validator(mode="after")
def _init_clients(self) -> OpenAICompletion:
    """创建时初始化 HTTP 客户端"""
    try:
        self._client = self._build_sync_client()
        self._async_client = self._build_async_client()
    except ValueError:
        pass  # 如果 API key 还没设置，延迟到首次调用时创建
    return self
```

**`_build_sync_client` 方法**：

```python
def _build_sync_client(self) -> Any:
    client_config = self._get_client_params()
    if self.interceptor:                     # 如果用户配置了拦截器
        transport = HTTPTransport(interceptor=self.interceptor)
        client_config["http_client"] = httpx.Client(transport=transport)
    return OpenAI(**client_config)           # 创建 OpenAI SDK 客户端
```

**`_get_client_params` 方法**：

```python
def _get_client_params(self) -> dict[str, Any]:
    if self.api_key is None:
        self.api_key = os.getenv("OPENAI_API_KEY")  # 从环境变量读取
        if self.api_key is None:
            raise ValueError("OPENAI_API_KEY is required")
    
    base_params = {
        "api_key": self.api_key,
        "organization": self.organization,
        "project": self.project,
        "base_url": self.base_url or os.getenv("OPENAI_BASE_URL"),
        "timeout": self.timeout,
        "max_retries": self.max_retries,
    }
    return {k: v for k, v in base_params.items() if v is not None}
```

**延迟初始化**：`_get_sync_client` 方法在第一次调用时才创建客户端：

```python
def _get_sync_client(self) -> Any:
    if self._client is None:
        self._client = self._build_sync_client()  # 按需创建
    return self._client
```

**通俗理解**：就像你的外卖 App，注册时不需要登录（`_init_clients` 跳过），但下单时如果还没登录，会弹出登录框（`_get_sync_client` 触发创建）。

---

#### 组件 C：`call()` 方法 — 入口

**源码位置**：[openai/completion.py#L414-L481](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/llms/providers/openai/completion.py#L414-L481)

```python
def call(self, messages, tools=None, callbacks=None, available_functions=None,
         from_task=None, from_agent=None, response_model=None) -> str | Any:
    """OpenAI API 调用入口"""
    
    # 第1步：进入调用上下文
    with llm_call_context():
        try:
            # 第2步：发射 LLMCallStartedEvent
            self._emit_call_started_event(
                messages=messages, tools=tools, from_task=from_task, from_agent=from_agent
            )
            
            # 第3步：格式化消息（处理多模态等）
            formatted_messages = self._format_messages(messages)
            
            # 第4步：执行 before_llm_call hooks
            if not self._invoke_before_llm_call_hooks(formatted_messages, from_agent):
                raise ValueError("LLM call blocked by before_llm_call hook")
            
            # 第5步：路由到具体 API
            if self.api == "responses":
                return self._call_responses(...)     # Responses API
            return self._call_completions(...)       # Chat Completions API
            
        except Exception as e:
            # 第6步：失败时发射事件
            self._emit_call_failed_event(error=str(e), from_task=from_task, from_agent=from_agent)
            raise
```

**流程图**：

```
call(messages, tools, available_functions)
  │
  ├── 1. llm_call_context()  → 设置 call_id
  ├── 2. _emit_call_started_event()  → 通知监控系统
  ├── 3. _format_messages()  → 标准化消息格式
  ├── 4. _invoke_before_llm_call_hooks()  → 用户可以修改消息
  ├── 5. api == "responses" ?
  │     ├── Yes → _call_responses()  → Responses API
  │     └── No  → _call_completions()
  │               ├── _effective_stream() ?
  │               │     ├── Yes → _handle_streaming_completion()
  │               │     └── No  → _handle_completion()
  │               └── 返回结果
  └── 6. 如果异常 → _emit_call_failed_event()
```

---

#### 组件 D：`_handle_completion` — 核心执行逻辑（非流式）

**源码位置**：[openai/completion.py#L1654-L1760](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/llms/providers/openai/completion.py#L1654-L1760)

这是整个模块最核心的方法，处理三种情况：

```python
def _handle_completion(self, params, available_functions=None, from_task=None,
                       from_agent=None, response_model=None) -> str | Any:
    
    # ===== 情况1：结构化输出 =====
    if response_model:
        # 使用 OpenAI beta API 的 parse 功能
        parse_params = {k: v for k, v in params.items() if k != "response_format"}
        parsed_response = self._get_sync_client().beta.chat.completions.parse(
            **parse_params,
            response_format=response_model,  # 传入 Pydantic 模型类
        )
        # 提取 token 用量
        usage = self._extract_openai_token_usage(parsed_response)
        self._track_token_usage_internal(usage)
        # 发射完成事件
        self._emit_call_completed_event(...)
        # 返回 Pydantic 对象（不是字符串！）
        return parsed_response.choices[0].message.parsed
    
    # ===== 情况2：普通调用 =====
    response = self._get_sync_client().chat.completions.create(**params)
    choice = response.choices[0]
    message = choice.message
    
    # ===== 情况2a：工具调用，但没有 available_functions =====
    # 返回 tool_calls 列表，让执行器去处理
    if message.tool_calls and not available_functions:
        self._emit_call_completed_event(response=list(message.tool_calls), ...)
        return list(message.tool_calls)
    
    # ===== 情况2b：工具调用，有 available_functions =====
    # 直接执行工具
    if message.tool_calls and available_functions:
        tool_call = message.tool_calls[0]  # 取第一个
        function_name = tool_call.function.name
        function_args = json.loads(tool_call.function.arguments)
        # 调用 BaseLLM 的工具执行方法
        result = self._handle_tool_execution(
            function_name=function_name,
            function_args=function_args,
            available_functions=available_functions,
            from_task=from_task,
            from_agent=from_agent,
        )
        if result is not None:
            return result
    
    # ===== 情况2c：纯文本响应 =====
    content = message.content or ""
    # 应用 stop 词截断
    return self._apply_stop_words(content)
```

**三种情况的分支逻辑**：

```
response_model 存在？
  ├── Yes → beta.chat.completions.parse() → 返回 Pydantic 对象
  └── No  → chat.completions.create()
              ├── tool_calls 存在？
              │     ├── Yes + available_functions 存在 → 执行工具 → 返回 tool_result
              │     ├── Yes + available_functions 不存在 → 返回 tool_calls 列表
              │     └── No  → 纯文本 → _apply_stop_words() → 返回字符串
```

**通俗理解**：`_handle_completion` 就像一个"快递分拣员"：
- 有 `response_model`？→ 走"特快专递"通道（结构化输出）
- LLM 要求调用工具？→ 走"工具执行"通道（直接执行或返回给执行器）
- 普通文本？→ 走"普通通道"，截断 stop 词后返回

---

#### 组件 E：`_format_messages` — 消息格式化

```python
def _format_messages(self, messages: str | list[LLMMessage]) -> list[LLMMessage]:
    if isinstance(messages, str):
        return [{"role": "user", "content": messages}]
    return messages
```

**解释**：如果用户直接传字符串，自动包装成 OpenAI 格式的消息列表。

---

## 5. 底层（二）：其余 Provider 子类

### 5.1 需求串讲

除了 OpenAI，CrewAI 还支持 Anthropic、Azure、Gemini、Bedrock、Snowflake、OpenAI Compatible。每个 Provider 的实现思路都高度一致：
1. 继承 `BaseLLM`
2. 实现 `call()` 和 `acall()`
3. 在 `call()` 中调用对应 SDK 的 API
4. 使用 BaseLLM 提供的事件发射和工具执行方法

### 5.2 AnthropicCompletion

**源码位置**：[anthropic/completion.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/llms/providers/anthropic/completion.py)

**特点**：
- 使用 Anthropic 官方 SDK（`anthropic.Anthropic`）
- 原生支持 structured outputs（Claude 4.5+ 模型）
- 支持 thinking（推理过程）提取
- 有 `system` 参数（Anthropic 特有的系统消息字段）

**关键差异**：

```python
# Anthropic 的 API 调用格式不同
response = self._get_sync_client().messages.create(
    model=self.model,
    system=system_prompt,      # Anthropic 有独立的 system 字段
    messages=formatted_messages,  # 不包含 system 消息
    tools=tools,
    max_tokens=self.max_tokens or 4096,  # Anthropic 必须传 max_tokens
)
```

### 5.3 AzureCompletion

**源码位置**：[azure/completion.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/llms/providers/azure/completion.py)

**特点**：
- 使用 Azure AI Inference SDK
- 需要 `endpoint` 和 `api_key`（Azure 特有）
- `api_version` 字段（Azure API 版本）

### 5.4 GeminiCompletion

**源码位置**：[gemini/completion.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/llms/providers/gemini/completion.py)

**特点**：
- 使用 Google GenAI SDK
- 支持 `safety_settings`（Gemini 特有的安全设置）
- 原生支持多模态（图片、音频、视频）
- 支持 `thinking_config`（Gemini 2.0+ 的推理配置）

### 5.5 BedrockCompletion

**源码位置**：[bedrock/completion.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/llms/providers/bedrock/completion.py)

**特点**：
- 使用 AWS Bedrock SDK
- 需要 `aws_access_key_id`、`aws_secret_access_key`、`aws_region`
- 支持 `inference_profile`（Bedrock 特有的推理配置）

### 5.6 SnowflakeCompletion

**源码位置**：[snowflake/completion.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/llms/providers/snowflake/completion.py)

**特点**：使用 Snowflake Cortex API。

### 5.7 OpenAICompatibleCompletion

**源码位置**：[openai_compatible/completion.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/llms/providers/openai_compatible/completion.py)

**特点**：兼容任何 OpenAI 格式的 API（如 vLLM、Ollama、LocalAI 等）。

---

## 6. 支撑层：`constants.py` / `cache.py` / `hooks` / `utils`

### 6.1 constants.py — 模型名白名单

**需求串讲**：`LLM.__new__()` 需要判断一个模型名是否属于已知的 Native Provider。它不能每次都发网络请求去验证，所以维护了一个本地的模型名白名单。

**源码位置**：[constants.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/llms/constants.py)

```python
OPENAI_MODELS: list[OpenAIModels] = [
    "gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "o1", "o1-mini", "o3-mini", "o4-mini",
    "gpt-5", "gpt-5-mini", "gpt-5-nano", "gpt-5-pro",
    # ... 100+ 个模型名
]

ANTHROPIC_MODELS: list[AnthropicModels] = [
    "claude-opus-4-5-20251101", "claude-sonnet-4-5-20250929",
    "claude-3-7-sonnet-20250219", "claude-3-5-haiku-20241022",
    # ... 20+ 个模型名
]

GEMINI_MODELS: list[GeminiModels] = [
    "gemini-3-pro-preview", "gemini-2.5-pro", "gemini-2.5-flash",
    "gemini-2.0-flash", "gemini-1.5-pro",
    # ... 50+ 个模型名
]

AZURE_MODELS: list[AzureModels] = [
    "gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "o1", "o3-mini",
    # ... 30+ 个模型名
]

BEDROCK_MODELS: list[BedrockModels] = [
    "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
    "amazon.nova-pro-v1:0", "meta.llama3-2-90b-instruct-v1:0",
    # ... 100+ 个模型名
]
```

**设计目的**：白名单验证 + 模糊匹配。如果模型名不在白名单中，但符合 Provider 的命名模式（如 `gpt-*` 开头），也会被接受。

---

### 6.2 cache.py — 缓存断点标记

**需求串讲**：LLM 的 Prompt 通常有一个"稳定的前缀"（system prompt + tool descriptions）和一个"变化的后缀"（用户的具体问题）。如果每次都传整个 Prompt，会浪费 token。Anthropic 等 Provider 支持"Prompt Caching"，允许标记哪些部分是稳定的，可以缓存。

**源码位置**：[cache.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/llms/cache.py)

```python
CACHE_BREAKPOINT_KEY = "cache_breakpoint"

def mark_cache_breakpoint(message: dict[str, Any]) -> dict[str, Any]:
    """给消息打上缓存断点标记"""
    return {**message, CACHE_BREAKPOINT_KEY: True}

def strip_cache_breakpoint(message: dict[str, Any]) -> None:
    """移除缓存标记（在发送给不支持缓存的 Provider 前）"""
    message.pop(CACHE_BREAKPOINT_KEY, None)
```

**使用场景**：

```python
messages = [
    mark_cache_breakpoint({"role": "system", "content": "你是一个助手..."}),   # 稳定
    mark_cache_breakpoint({"role": "user", "content": "工具列表：..."}),       # 稳定
    {"role": "user", "content": "帮我搜索 AI Safety"},  # 变化（不打标记）
]
# Anthropic 会缓存前两条消息，后续请求只传第三条
```

---

### 6.3 hooks/ — HTTP 拦截器体系

**需求串讲**：有时候用户需要在 HTTP 请求发出前或收到响应后做一些自定义操作（如添加自定义 Header、记录日志、修改响应）。这需要一个"拦截器"机制。

**源码位置**：
- [hooks/base.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/llms/hooks/base.py) — BaseInterceptor 抽象类
- [hooks/transport.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/llms/hooks/transport.py) — HTTPTransport 实现

**BaseInterceptor**：

```python
class BaseInterceptor(ABC, Generic[T, U]):
    """HTTP 传输层拦截器"""
    
    @abstractmethod
    def on_outbound(self, message: T) -> T:
        """请求发出前拦截"""
    
    @abstractmethod
    def on_inbound(self, message: U) -> U:
        """响应收到后拦截"""
    
    async def aon_outbound(self, message: T) -> T:
        """异步版本"""
        raise NotImplementedError
    
    async def aon_inbound(self, message: U) -> U:
        """异步版本"""
        raise NotImplementedError
```

**HTTPTransport**：

```python
class HTTPTransport(_HTTPTransport):
    def __init__(self, interceptor: BaseInterceptor[Request, Response], **kwargs):
        super().__init__(**kwargs)
        self.interceptor = interceptor
    
    def handle_request(self, request: Request) -> Response:
        request = self.interceptor.on_outbound(request)   # 拦截请求
        response = super().handle_request(request)        # 发送请求
        return self.interceptor.on_inbound(response)      # 拦截响应
```

**通俗理解**：拦截器就像快递站的"安检机"。包裹进来时（on_outbound）检查一下，包裹出去时（on_inbound）再检查一下。

**用户自定义拦截器示例**：

```python
class LoggingInterceptor(BaseInterceptor[httpx.Request, httpx.Response]):
    def on_outbound(self, request):
        print(f"发送请求: {request.method} {request.url}")
        return request
    
    def on_inbound(self, response):
        print(f"收到响应: {response.status_code}")
        return response

llm = LLM(model="gpt-4o", interceptor=LoggingInterceptor())
```

---

### 6.4 providers/utils/common.py — 工具转换

**需求串讲**：不同 Provider 对工具（function calling）的格式要求各不相同。需要一个公共的工具转换函数来处理这些差异。

**源码位置**：[providers/utils/common.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/llms/providers/utils/common.py)

**核心函数**：

```python
def extract_tool_info(tool: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    """从各种格式的工具定义中提取 name, description, parameters"""
    if "function" in tool:
        # OpenAI 格式: {"type": "function", "function": {"name": "...", ...}}
        function_info = tool["function"]
        name = function_info.get("name", "")
        description = function_info.get("description", "")
        parameters = function_info.get("parameters", {})
    else:
        # 直接格式: {"name": "...", "description": "...", ...}
        name = tool.get("name", "")
        description = tool.get("description", "")
        parameters = tool.get("parameters", {})
    return name, description, parameters

def safe_tool_conversion(tool, provider) -> tuple[str, str, dict[str, Any]]:
    """安全转换工具定义（含名称校验和日志）"""
    log_tool_conversion(tool, provider)
    name, description, parameters = extract_tool_info(tool)
    sanitized_name = sanitize_function_name(name)      # 名称规范化
    validated_name = validate_function_name(sanitized_name, provider)  # 校验
    return validated_name, description, parameters
```

**函数名校验规则**：

```python
def validate_function_name(name: str, provider: str = "LLM") -> str:
    if not name or not isinstance(name, str):
        raise ValueError("函数名不能为空")
    if not (name[0].isalpha() or name[0] == "_"):
        raise ValueError("函数名必须以字母或下划线开头")
    if len(name) > 64:
        raise ValueError("函数名不能超过 64 个字符")
    if not re.match(r"^[a-z_][a-z0-9_]*$", name):
        raise ValueError("函数名只能包含小写字母、数字和下划线")
    return name
```

---

## 7. 完整调用链路（从用户代码到 AI 返回结果）

### 需求串讲

现在我们把所有知识点串起来，跟踪一个完整的调用链路：用户写 `LLM(model="gpt-4o").call(messages)` 到拿到 AI 返回结果。

### 完整调用链路图

```
用户代码:
  llm = LLM(model="gpt-4o")
  response = llm.call(messages=[{"role": "user", "content": "Hello"}])

═══════════════════════════════════════════════════════════════
第1步：创建 LLM 实例
═══════════════════════════════════════════════════════════════

LLM.__new__(model="gpt-4o")
  │
  ├── _infer_provider_from_model("gpt-4o")
  │     └── "gpt-" 开头 → provider="openai"
  │
  ├── _get_native_provider("openai") → OpenAICompletion 类
  │
  ├── OpenAICompletion(model="gpt-4o", provider="openai")
  │     │
  │     ├── BaseLLM.__init__()  → 设置 model, temperature 等字段
  │     │
  │     └── OpenAICompletion._init_clients()  → model_validator
  │           ├── _build_sync_client()  → OpenAI(api_key=..., ...)
  │           └── _build_async_client() → AsyncOpenAI(...)
  │
  └── 返回 OpenAICompletion 实例

═══════════════════════════════════════════════════════════════
第2步：调用 call()
═══════════════════════════════════════════════════════════════

OpenAICompletion.call(messages=[{"role": "user", "content": "Hello"}])
  │
  ├── llm_call_context()  ← 设置 call_id = "abc-123"
  │     │
  │     ├── _emit_call_started_event()
  │     │     └── crewai_event_bus.emit(LLMCallStartedEvent(
  │     │           model="gpt-4o", call_id="abc-123", messages=...))
  │     │
  │     ├── _format_messages(messages)
  │     │     └── 已经是 list，直接返回
  │     │
  │     ├── _invoke_before_llm_call_hooks()
  │     │     └── 没有注册 hook，跳过
  │     │
  │     ├── api == "responses"? → No
  │     │
  │     └── _call_completions()
  │           │
  │           ├── _prepare_completion_params()
  │           │     └── 构建 params = {
  │           │           "model": "gpt-4o",
  │           │           "messages": [{"role": "user", "content": "Hello"}],
  │           │           "temperature": None,
  │           │           "max_tokens": None,
  │           │           "stream": False,
  │           │           "stop": [],
  │           │         }
  │           │
  │           └── _effective_stream()? → False
  │                 │
  │                 └── _handle_completion(params)
  │                       │
  │                       ├── response_model? → No
  │                       │
  │                       ├── _get_sync_client().chat.completions.create(**params)
  │                       │     │
  │                       │     └── OpenAI SDK 发送 HTTP POST
  │                       │           │
  │                       │           └── https://api.openai.com/v1/chat/completions
  │                       │                 │
  │                       │                 └── 返回 ChatCompletion 对象
  │                       │
  │                       ├── _extract_openai_token_usage(response)
  │                       │     └── {"prompt_tokens": 10, "completion_tokens": 5, ...}
  │                       │
  │                       ├── _track_token_usage_internal(usage)
  │                       │     └── 累积到 self._token_usage
  │                       │
  │                       ├── message.tool_calls? → No
  │                       │
  │                       ├── content = "Hello! How can I help you?"
  │                       │
  │                       ├── _apply_stop_words("Hello! How can I help you?")
  │                       │     └── 没有 stop 词，原样返回
  │                       │
  │                       ├── _emit_call_completed_event(
  │                       │       response="Hello! How can I help you?",
  │                       │       call_type=LLM_CALL,
  │                       │       usage={"prompt_tokens": 10, ...},
  │                       │       finish_reason="stop",
  │                       │     )
  │                       │
  │                       └── 返回 "Hello! How can I help you?"
  │
  └── 返回 "Hello! How can I help you?"

═══════════════════════════════════════════════════════════════
第3步：用户拿到结果
═══════════════════════════════════════════════════════════════

response = "Hello! How can I help you?"
```

---

### 带工具调用的完整链路

```
用户代码:
  llm = LLM(model="gpt-4o")
  response = llm.call(
      messages=[{"role": "user", "content": "搜索 AI Safety"}],
      tools=[search_tool.to_openai_tool()],
      available_functions={"search": search_tool._run},
  )

═══════════════════════════════════════════════════════════════

OpenAICompletion.call()
  │
  └── _handle_completion(params, available_functions={...})
        │
        ├── _get_sync_client().chat.completions.create(**params)
        │     └── OpenAI 返回: message.tool_calls = [{
        │           "function": {"name": "search", "arguments": '{"query": "AI Safety"}'}
        │         }]
        │
        ├── message.tool_calls? → Yes
        ├── available_functions? → Yes
        │
        ├── tool_call = message.tool_calls[0]
        ├── function_name = "search"
        ├── function_args = json.loads('{"query": "AI Safety"}')
        │     └── {"query": "AI Safety"}
        │
        └── self._handle_tool_execution(
              function_name="search",
              function_args={"query": "AI Safety"},
              available_functions={"search": search_tool._run},
            )
              │
              ├── 1. 检查 "search" 在 available_functions 中 → Yes
              ├── 2. 发射 ToolUsageStartedEvent
              ├── 3. fn = search_tool._run
              │      result = fn(query="AI Safety") → "搜索结果: AI Safety 是..."
              ├── 4. 发射 ToolUsageFinishedEvent
              ├── 5. 发射 LLMCallCompletedEvent(call_type=TOOL_CALL)
              └── 返回 "搜索结果: AI Safety 是..."
```

---

### 带结构化输出的完整链路

```
用户代码:
  class Summary(BaseModel):
      title: str
      key_points: list[str]
  
  llm = LLM(model="gpt-4o")
  result = llm.call(
      messages=[{"role": "user", "content": "总结 AI Safety"}],
      response_model=Summary,
  )

═══════════════════════════════════════════════════════════════

OpenAICompletion.call()
  │
  └── _handle_completion(params, response_model=Summary)
        │
        ├── response_model? → Yes
        │
        ├── parse_params = params 去掉 "response_format" 字段
        │
        ├── _get_sync_client().beta.chat.completions.parse(
        │       **parse_params,
        │       response_format=Summary,  # Pydantic 模型类
        │     )
        │     └── OpenAI 直接返回 Pydantic 对象
        │
        ├── parsed_object = Summary(
        │       title="AI Safety Overview",
        │       key_points=["Alignment", "Robustness", "Interpretability"]
        │     )
        │
        ├── _emit_call_completed_event(...)
        └── 返回 Summary 对象（不是字符串！）
```

---

## 总结

### 模块文件清单

```
lib/crewai/src/crewai/llms/
├── __init__.py                    # 包声明
├── base_llm.py                    # BaseLLM 抽象基类（800+ 行）
│   ├── contextvars 上下文管理
│   ├── 事件发射模板方法
│   ├── 工具执行封装
│   └── stop 词截断
├── llm.py                         # LLM 类（LiteLLM 回退）
├── constants.py                   # 模型名白名单
├── cache.py                       # 缓存断点标记
├── _finish_reason_utils.py        # 公共提取器
├── hooks/
│   ├── base.py                    # BaseInterceptor 抽象类
│   └── transport.py               # HTTPTransport / AsyncHTTPTransport
└── providers/
    ├── openai/completion.py       # OpenAICompletion（2000+ 行）
    ├── anthropic/completion.py    # AnthropicCompletion
    ├── azure/completion.py        # AzureCompletion
    ├── gemini/completion.py       # GeminiCompletion
    ├── bedrock/completion.py      # BedrockCompletion
    ├── snowflake/completion.py    # SnowflakeCompletion
    ├── openai_compatible/         # OpenAICompatibleCompletion
    └── utils/common.py            # 工具转换公共函数
```

### 设计亮点总结

| 设计 | 作用 | 行号 |
|------|------|------|
| `__new__` 工厂路由 | 根据模型名自动选择最佳 Provider | [llm.py#L393](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/llm.py#L393) |
| `contextvars` 隔离 | 并发安全，每个协程独立上下文 | [base_llm.py#L79](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/llms/base_llm.py#L79) |
| per-instance stop 覆盖 | 同一 Agent 多个 LLM 互不干扰 | [base_llm.py#L101](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/llms/base_llm.py#L101) |
| 事件发射模板方法 | 所有 Provider 自动获得事件能力 | [base_llm.py#L545](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/llms/base_llm.py#L545) |
| 工具执行封装 | 统一工具调用流程（事件+错误处理） | [base_llm.py#L714](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/llms/base_llm.py#L714) |
| Native + LiteLLM 双层 | Native 高性能，LiteLLM 兼容 100+ 模型 | [llm.py#L493](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/llm.py#L493) |
| 延迟初始化客户端 | 模块导入时不报错，首次调用才创建 | [openai/completion.py#L273](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/llms/providers/openai/completion.py#L273) |
| HTTP 拦截器 | 用户可以拦截请求/响应做自定义处理 | [hooks/transport.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/llms/hooks/transport.py) |
| 模型名白名单 | 本地验证模型名，避免无效网络请求 | [constants.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/llms/constants.py) |
| 模型名模糊匹配 | 白名单外的模型按命名模式匹配 | [llm.py#L514](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/llm.py#L514) |