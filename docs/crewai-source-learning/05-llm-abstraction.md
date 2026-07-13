# 阶段五：LLM 抽象层 — 源码深度解析

---

## 1. 模块定位

### 1.1 一句话概括

**LLM 抽象层是 CrewAI 与所有大模型交互的统一接口，通过「工厂模式 + 原生 SDK 优先 + LiteLLM 兜底」的策略，实现了 OpenAI、Anthropic、Gemini、Bedrock 等 20+ 模型提供商的透明接入，并提供 KV-Cache 优化、Token 计数、流式输出等企业级能力。**

### 1.2 在整体架构中的位置

```
Agent/Crew/Task 调用 LLM
    │
    ▼
LLM(model="gpt-4o")  ← 门面类（工厂模式）
    │
    ├── 原生 SDK 路由（优先级最高）
    │   ├── openai → OpenAILLM
    │   ├── anthropic → AnthropicLLM
    │   ├── gemini → GeminiLLM
    │   └── bedrock → BedrockLLM
    │
    └── LiteLLM 兜底（通用适配）
        └── 懒加载 litellm 库
            │
            ▼
        BaseLLM.call() / acall()
```

### 1.3 本阶段涉及的核心源码文件

| 文件 | 行数 | 核心职责 |
|------|------|----------|
| `llm.py` | ~800+ 行 | LLM 门面类：工厂路由、LiteLLM 集成、流式处理 |
| `llms/base_llm.py` | ~450+ 行 | 抽象基类：接口定义、Token 统计、停止词控制 |
| `llms/cache.py` | ~37 行 | Prompt 缓存断点标记（KV-Cache 优化） |
| `llms/_finish_reason_utils.py` | 工具函数 | 完成原因提取与处理 |
| `llms/constants.py` | 模型列表 | 各 Provider 的已知模型常量 |

---

## 2. 源码分层拆解

### 2.1 第一层：BaseLLM（抽象基类）

**文件：** `lib/crewai/src/crewai/llms/base_llm.py`

```python
class BaseLLM(BaseModel, ABC):
    """所有 LLM 实现的抽象基类"""
    llm_type: str = "base"
    model: str                                    # 模型名称（必填）
    temperature: float | None = None              # 温度参数
    top_p: float | None = None                    # top_p 采样
    max_tokens: int | float | None = None         # 最大输出 Token
    stream: bool | None = None                    # 流式输出开关
    seed: int | None = None                       # 随机种子
    frequency_penalty: float | None = None        # 频率惩罚
    presence_penalty: float | None = None         # 存在惩罚
    api_key: str | None = None                    # API 密钥
    base_url: str | None = None                   # 自定义端点
    provider: str = "openai"                      # 提供商标识
    stop: list[str] = []                          # 停止词列表
    additional_params: dict[str, Any] = {}        # 额外参数（透传）
```

**核心抽象方法：**

```python
@abstractmethod
def call(self, messages, tools=None, callbacks=None, available_functions=None,
         from_task=None, from_agent=None, response_model=None) -> str | Any:
    """调用 LLM 的核心方法，所有子类必须实现。"""
```

**Token 统计（PrivateAttr）：**

```python
_token_usage: dict[str, int] = PrivateAttr(default_factory=lambda: {
    "total_tokens": 0,
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "successful_requests": 0,
    "cached_prompt_tokens": 0,      # 缓存的提示 Token
    "reasoning_tokens": 0,           # 推理 Token（o1 等模型）
    "cache_creation_tokens": 0,      # 缓存创建 Token
})
```

**停止词上下文覆盖机制：**

```python
@property
def stop_sequences(self) -> list[str]:
    """获取当前调用作用域的停止词（支持上下文覆盖）。"""
    overrides = _call_stop_override_var.get()  # 从 contextvars 获取
    if overrides is not None:
        override = overrides.get(id(self))
        if override is not None:
            return override
    return self.stop  # 回退到实例级 stop 字段
```

**设计亮点：** `stop_sequences` 使用 `contextvars` 实现线程安全的上下文覆盖，而不是直接修改实例属性——这样在并发环境（ThreadPoolExecutor）中不会互相干扰。

---

### 2.2 第二层：LLM（门面类 / 工厂模式）

**文件：** `lib/crewai/src/crewai/llm.py`

#### 2.2.1 `__new__` 工厂路由

```python
class LLM(BaseLLM):
    def __new__(cls, model: str, is_litellm: bool = False, **kwargs):
        """
        工厂方法：根据 model 字符串自动路由到原生 SDK 或 LiteLLM。
        
        路由优先级：
        1. custom_openai=True → 强制原生 OpenAI（需要自定义端点）
        2. 显式 provider 参数 → 使用指定 provider
        3. model 包含 "/" → 解析前缀确定 provider
        4. 否则 → 根据 model 名称推断 provider
        """
        # 步骤 1：解析 provider
        if "/" in model:
            prefix, _, model_part = model.partition("/")
            # provider_mapping: {"openai": "openai", "anthropic": "anthropic", ...}
            canonical_provider = provider_mapping.get(prefix.lower())
            if canonical_provider and valid_native_model:
                provider = canonical_provider
                use_native = True
                model_string = model_part
            else:
                provider = prefix
                use_native = False  # 非原生，走 LiteLLM
                model_string = model_part

        # 步骤 2：尝试原生 SDK
        native_class = cls._get_native_provider(provider)
        if native_class and provider in SUPPORTED_NATIVE_PROVIDERS:
            return native_class(model=model_string, provider=provider, **kwargs)

        # 步骤 3：LiteLLM 兜底
        if not _ensure_litellm():
            raise ImportError("需要安装 litellm...")
        return object.__new__(cls)  # 返回 LLM 实例，走 LiteLLM 路径
```

**支持的 Provider 映射：**

```python
SUPPORTED_NATIVE_PROVIDERS = [
    "openai", "anthropic", "claude", "azure", "azure_openai",
    "google", "gemini", "bedrock", "aws", "openrouter",
    "deepseek", "ollama", "ollama_chat", "hosted_vllm",
    "cerebras", "dashscope", "snowflake",
]
```

**大白话解释：** 你写 `LLM(model="gpt-4o")` 时，`__new__` 方法会根据 `gpt-4o` 这个名字自动判断该用 OpenAI 原生 SDK 还是 LiteLLM。如果匹配到原生 SDK，直接返回 `OpenAILLM` 实例；否则降到 LiteLLM 通用适配层。

#### 2.2.2 LiteLLM 懒加载

```python
_litellm_loaded = False
LITELLM_AVAILABLE = False

def _ensure_litellm() -> bool:
    """懒加载 litellm，避免启动时的 dotenv 污染。"""
    global _litellm_loaded, LITELLM_AVAILABLE
    if _litellm_loaded:
        return LITELLM_AVAILABLE
    _litellm_loaded = True
    try:
        import litellm as _litellm
        # ... 导入所有 litellm 类型
        LITELLM_AVAILABLE = True
    except ImportError:
        LITELLM_AVAILABLE = False
    return LITELLM_AVAILABLE
```

**设计亮点：** LiteLLM 在模块级别 `import litellm` 时会自动调用 `dotenv.load_dotenv()`，覆盖环境变量。CrewAI 通过懒加载避免了这个问题——只有真正需要 LiteLLM 时才加载。

---

### 2.3 第三层：Prompt 缓存优化（KV-Cache）

**文件：** `lib/crewai/src/crewai/llms/cache.py`

```python
CACHE_BREAKPOINT_KEY = "cache_breakpoint"

def mark_cache_breakpoint(message: dict[str, Any]) -> dict[str, Any]:
    """在消息字典上标记缓存断点，返回新字典（不修改原消息）。"""
    return {**message, CACHE_BREAKPOINT_KEY: True}

def strip_cache_breakpoint(message: dict[str, Any]) -> None:
    """移除缓存断点标记（在发送给 Provider 前清理）。"""
    message.pop(CACHE_BREAKPOINT_KEY, None)
```

**使用场景（在 CrewAgentExecutor 中）：**

```python
# System Prompt 是每个 Agent 固定的，标记为缓存断点
self.messages.append(
    mark_cache_breakpoint(format_message_for_llm(system_prompt, role="system"))
)
# User Prompt 是每个 Task 的固定前缀，也标记
self.messages.append(
    mark_cache_breakpoint(format_message_for_llm(user_prompt))
)
# 后续 ReAct 循环中的消息不标记，每次都会变化
```

**大白话：** Anthropic 的 Claude 等模型支持 Prompt Caching。标记 `cache_breakpoint` 后，Provider 适配器会将其转换为 API 的缓存指令，让 LLM 复用已计算的 KV 值，节省 90% 的 prompt 处理延迟。

---

### 2.4 第四层：上下文窗口管理

```python
# llm.py 中定义了大量模型的上下文窗口大小
LLM_CONTEXT_WINDOW_SIZES = {
    "gpt-4": 8192,
    "gpt-4o": 128000,
    "gpt-4o-mini": 200000,
    "gemini-1.5-pro": 2097152,  # 最大 200 万 Token！
    "gemini-2.0-flash": 1048576,
    "deepseek-chat": 128000,
    # ... 100+ 模型
}

CONTEXT_WINDOW_USAGE_RATIO = 0.85  # 使用 85% 的窗口时触发截断
```

**面试重点：** `CONTEXT_WINDOW_USAGE_RATIO = 0.85` 意味着当消息历史达到窗口 85% 时，框架会自动裁剪消息，保留 system prompt + 最近的消息，避免 LLM 调用失败。

---

## 3. 完整调用时序图

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         LLM 调用完整时序                                  │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  1. 创建 LLM 实例                                                         │
│     LLM(model="gpt-4o")                                                   │
│         │                                                                  │
│         ├── __new__() 工厂方法                                             │
│         │   ├── 解析 model 字符串 → provider="openai", model="gpt-4o"     │
│         │   ├── 匹配原生 SDK：_get_native_provider("openai")              │
│         │   │   └── 返回 OpenAILLM 实例 ✅                                 │
│         │   └── 如不匹配：LiteLLM 兜底                                      │
│         │                                                                  │
│         └── 返回 LLM 实例（可能是原生子类或 LLM 自身）                     │
│                                                                           │
│  2. 调用 LLM                                                              │
│     llm.call(messages, tools, callbacks, ...)                              │
│         │                                                                  │
│         ├── 进入 llm_call_context()  ← 生成唯一 call_id                   │
│         │                                                                  │
│         ├── 发射 LLMCallStartedEvent                                       │
│         │                                                                  │
│         ├── 处理消息格式                                                   │
│         │   ├── 多模态文件处理（format_multimodal_content）                │
│         │   ├── 移除缓存断点标记（strip_cache_breakpoint）                 │
│         │   └── 工具 Schema 转换（OpenAI 格式）                            │
│         │                                                                  │
│         ├── 实际调用（以 LiteLLM 路径为例）                                │
│         │   ├── litellm.completion(model, messages, tools, ...)            │
│         │   │   ├── 流式？→ 逐块 yield                                     │
│         │   │   └── 非流式？→ 等待完整响应                                 │
│         │   └── 错误处理                                                   │
│         │       ├── ContextLengthError → 裁剪消息重试                      │
│         │       └── 其他错误 → 发射 LLMCallFailedEvent                     │
│         │                                                                  │
│         ├── 后处理                                                         │
│         │   ├── 提取 choices → finish_reason                               │
│         │   ├── 工具调用？→ 解析 function_call 返回                       │
│         │   ├── 结构化输出？→ 解析 JSON → Pydantic 验证                    │
│         │   └── 更新 _token_usage（prompt_tokens, completion_tokens）     │
│         │                                                                  │
│         ├── 执行 callbacks（TokenCalcHandler）                             │
│         │                                                                  │
│         ├── 发射 LLMCallCompletedEvent                                     │
│         │                                                                  │
│         └── 返回结果（str | BaseModel | tool_calls）                       │
│                                                                           │
│  3. Token 统计                                                             │
│     _token_usage = {                                                       │
│         "total_tokens": 累计,                                              │
│         "prompt_tokens": 累计,                                             │
│         "completion_tokens": 累计,                                         │
│         "successful_requests": 累计,                                       │
│         "cached_prompt_tokens": 缓存命中数,                                │
│         "reasoning_tokens": 推理 Token 数,                                 │
│     }                                                                      │
│                                                                           │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 4. 核心设计亮点

### 4.1 工厂模式 + 原生 SDK 优先

| 层次 | 机制 | 优势 |
|------|------|------|
| 第1层 | 原生 SDK（OpenAI、Anthropic 等） | 零额外依赖、性能最优、支持最新功能 |
| 第2层 | LiteLLM 通用适配 | 覆盖 100+ 模型、统一接口、自动 fallback |

**关键代码：** `__new__` 方法根据 model 字符串自动路由，用户无需关心底层实现。

### 4.2 LiteLLM 懒加载（避免环境变量污染）

```python
# 只在需要时才 import litellm
def _ensure_litellm() -> bool:
    if _litellm_loaded:
        return LITELLM_AVAILABLE
    # ... 第一次调用时才加载
```

**面试高频考点：** LiteLLM 在 import 时会自动调用 `load_dotenv()`，可能覆盖用户设置的环境变量。懒加载策略避免了这个问题。

### 4.3 ContextVar 实现的线程安全停止词覆盖

```python
_call_stop_override_var = contextvars.ContextVar("_call_stop_override_var", default=None)

@contextmanager
def call_stop_override(llm, stop):
    """通过 contextvars 实现线程安全的停止词覆盖。"""
    current = _call_stop_override_var.get()
    new_overrides = dict(current) if current else {}
    new_overrides[id(llm)] = stop
    token = _call_stop_override_var.set(new_overrides)
    try:
        yield
    finally:
        _call_stop_override_var.reset(token)
```

**大白话：** 在 ThreadPoolExecutor 并行执行时，每个线程有独立的 `contextvars` 副本，`call_stop_override` 的修改只影响当前线程，不会污染其他线程。

### 4.4 上下文窗口自动管理

```python
CONTEXT_WINDOW_USAGE_RATIO = 0.85  # 85% 阈值

def handle_context_length(respect_context_window, messages, llm, ...):
    """当消息超过上下文窗口 85% 时，自动裁剪。"""
    if not respect_context_window:
        raise  # 不尊重窗口则直接抛出
    # 保留 system prompt + 最近 N 条消息
    # 删除中间的消息
```

### 4.5 多模态内容自动处理

```python
if HAS_CREWAI_FILES:
    from crewai_files import format_multimodal_content
    # 自动将图片、音频等文件转换为 Provider 原生格式
    messages = format_multimodal_content(messages, files)
```

---

## 5. 生产落地拓展改造

### 5.1 多模型路由与降级

```python
class ModelRouter:
    """根据任务类型和成本自动选择模型。"""
    def __init__(self):
        self.routes = {
            "simple": "gpt-4o-mini",       # 简单任务用小模型
            "complex": "gpt-4o",            # 复杂任务用大模型
            "vision": "gpt-4o",             # 视觉任务
            "fallback": "claude-3-5-sonnet", # 降级模型
        }

    def get_llm(self, task_type: str) -> LLM:
        try:
            return LLM(model=self.routes[task_type])
        except Exception:
            return LLM(model=self.routes["fallback"])
```

### 5.2 请求速率限制（Token Bucket）

```python
import time
from threading import Semaphore

class RateLimitedLLM:
    def __init__(self, llm: LLM, rpm: int = 60):
        self.llm = llm
        self.min_interval = 60.0 / rpm
        self._last_call = 0.0
        self._lock = Semaphore(1)

    def call(self, messages, **kwargs):
        with self._lock:
            elapsed = time.time() - self._last_call
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)
            result = self.llm.call(messages, **kwargs)
            self._last_call = time.time()
            return result
```

### 5.3 请求重试与断路器

```python
from tenacity import retry, stop_after_attempt, wait_exponential

class ResilientLLM:
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=lambda e: isinstance(e, (TimeoutError, ConnectionError))
    )
    def call(self, messages, **kwargs):
        return self.llm.call(messages, **kwargs)
```

### 5.4 成本追踪与告警

```python
class CostTrackingLLM(LLM):
    PRICING = {
        "gpt-4o": {"input": 2.50/1_000_000, "output": 10.00/1_000_000},
        "gpt-4o-mini": {"input": 0.15/1_000_000, "output": 0.60/1_000_000},
    }

    def call(self, messages, **kwargs):
        result = super().call(messages, **kwargs)
        cost = self._calculate_cost()
        if cost > self.budget_limit:
            self._alert("预算超限", cost)
        return result
```

---

## 6. 面试深挖问题清单

| # | 问题 | 考察点 |
|---|------|--------|
| 1 | LLM 类的 `__new__` 工厂方法如何路由到不同 Provider？ | 工厂模式、Provider 路由 |
| 2 | 为什么 LiteLLM 要懒加载？不懒加载会有什么问题？ | 环境变量污染、启动性能 |
| 3 | `contextvars` 在停止词覆盖中起什么作用？ | 线程安全、上下文变量 |
| 4 | `mark_cache_breakpoint` 的工作原理是什么？ | KV-Cache、Prompt Caching |
| 5 | CrewAI 如何处理上下文窗口超限？ | 自动截断、窗口管理 |
| 6 | BaseLLM 的 `_token_usage` 统计了哪些指标？ | Token 计数、用量追踪 |
| 7 | 原生 SDK 和 LiteLLM 的优先级策略是什么？ | 多层 fallback |
| 8 | `LLM_CONTEXT_WINDOW_SIZES` 字典的作用是什么？ | 模型能力映射 |
| 9 | `to_config_dict()` 方法的设计目的是什么？ | 序列化、检查点保存 |
| 10 | 如何在 CrewAI 中接入一个 LiteLLM 不支持的自定义模型？ | 扩展 BaseLLM、自定义 Provider |

---

## 7. 简易可运行 Demo

```python
"""Demo: LLM 抽象层的三种使用方式"""
from crewai import LLM

# 方式 1：原生 OpenAI SDK（自动路由）
llm_openai = LLM(model="gpt-4o-mini")
print(f"类型: {type(llm_openai).__name__}")
# 输出: 类型: OpenAILLM

# 方式 2：显式指定 Provider
llm_anthropic = LLM(model="anthropic/claude-3-5-sonnet-latest")
print(f"类型: {type(llm_anthropic).__name__}")
# 输出: 类型: AnthropicLLM

# 方式 3：使用 provider 参数
llm_gemini = LLM(model="gemini-2.0-flash", provider="gemini")
print(f"类型: {type(llm_gemini).__name__}")
# 输出: 类型: GeminiLLM

# 调用 LLM
response = llm_openai.call([
    {"role": "system", "content": "你是一个助手"},
    {"role": "user", "content": "用一句话解释什么是工厂模式"}
])
print(f"\n回复: {response}")
print(f"Token 用量: {llm_openai._token_usage}")
```

---

**下一阶段解析指令：**

```
# 当前解析目标
模块名称：Tools 工具系统
对应源码文件路径：
- lib/crewai/src/crewai/tools/base_tool.py（工具基类）
- lib/crewai/src/crewai/tools/structured_tool.py（结构化工具）
- lib/crewai/src/crewai/tools/tool_usage.py（工具调用执行器）
- lib/crewai/src/crewai/tools/tool_calling.py（ToolCalling 封装）
- lib/crewai/src/crewai/tools/tool_types.py（工具类型定义）

# 本次输出硬性要求，缺一不可
1. 模块定位（一句话 + 架构位置 + 核心文件清单）
2. 源码分层拆解（文件→类→方法→关键代码行）
3. 完整调用时序图（Agent → ToolRegistry → BaseTool._run() → 结果返回）
4. 核心设计亮点（Pydantic Schema 生成、结果缓存、result_as_answer、多模态工具）
5. 生产落地拓展改造（MCP 工具聚合、工具超时控制、Tool 调用链追踪）
6. 面试深挖问题清单（10 题）
7. 简易可运行 Demo 代码
```