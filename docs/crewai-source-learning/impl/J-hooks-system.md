# 阶段 J：hooks/ — 钩子系统实现逻辑详解

## 1. 模块定位与架构图

### 1.1 模块定位

`hooks/` 模块是 CrewAI 框架的**执行期拦截基础设施**，提供对 LLM 调用和工具调用的**细粒度生命周期钩子**。与 `kickoff hooks`（在 Crew 启动前后执行）不同，`hooks/` 模块拦截的是**每一个 Agent 执行步骤中的具体操作**，允许开发者：

- **在 LLM 调用前**：修改 prompt、注入上下文、阻止调用
- **在 LLM 调用后**：修改响应、清理敏感信息、修改对话历史
- **在工具调用前**：修改参数、验证输入、阻止危险操作
- **在工具调用后**：修改结果、清理输出、记录日志

模块采用**全局注册 + 执行器级挂载**的混合架构，支持两种注册方式：**装饰器注册**（`@before_llm_call` 等）和**命令式 API 注册**（`register_before_llm_call_hook()` 等）。

### 1.2 整体架构图

```
┌──────────────────────────────────────────────────────────────────────┐
│                        hooks/ 模块架构                                │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────────┐│
│  │                    types.py — 类型定义层                          ││
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   ││
│  │  │ Hook Protocol │  │ BeforeLLMCall │  │ AfterLLMCallHook     │   ││
│  │  │ (泛型基类)    │  │ Hook          │  │                      │   ││
│  │  └──────────────┘  └──────────────┘  └──────────────────────┘   ││
│  │  ┌──────────────────┐  ┌──────────────────┐                     ││
│  │  │ BeforeToolCall   │  │ AfterToolCall    │                     ││
│  │  │ Hook             │  │ Hook             │                     ││
│  │  └──────────────────┘  └──────────────────┘                     ││
│  └──────────────────────────────────────────────────────────────────┘│
│                                                                       │
│  ┌──────────────────────────┐  ┌──────────────────────────┐         │
│  │   llm_hooks.py           │  │   tool_hooks.py           │         │
│  │  ┌─────────────────────┐ │  │  ┌─────────────────────┐  │         │
│  │  │ LLMCallHookContext  │ │  │  │ ToolCallHookContext  │  │         │
│  │  │ - executor/messages │ │  │  │ - tool_name/input    │  │         │
│  │  │ - agent/task/crew   │ │  │  │ - tool/agent/task    │  │         │
│  │  │ - llm/iterations    │ │  │  │ - crew/result        │  │         │
│  │  │ - response          │ │  │  │ - request_human_input│  │         │
│  │  │ - request_human_input│ │  │  └─────────────────────┘  │         │
│  │  └─────────────────────┘ │  │  register/unregister/     │         │
│  │  register/unregister/    │  │  get/clear 系列函数        │         │
│  │  get/clear 系列函数       │  │                           │         │
│  └──────────────────────────┘  └──────────────────────────┘         │
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────────┐│
│  │                    decorators.py — 装饰器注册层                    ││
│  │  ┌────────────────────────────────────────────────────────────┐  ││
│  │  │  _create_hook_decorator() — 工厂函数（消除重复代码）          │  ││
│  │  │    ├─ 支持 @before_llm_call / @after_llm_call               │  ││
│  │  │    ├─ 支持 @before_tool_call / @after_tool_call             │  ││
│  │  │    ├─ 支持 agent 过滤 (agents=["Researcher"])               │  ││
│  │  │    ├─ 支持 tool 过滤 (tools=["delete_file"])                │  ││
│  │  │    └─ 自动判断函数/方法，方法跳过自动注册                     │  ││
│  │  └────────────────────────────────────────────────────────────┘  ││
│  └──────────────────────────────────────────────────────────────────┘│
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────────┐│
│  │                    wrappers.py — 包装器层                          ││
│  │  ┌──────────────────┐  ┌──────────────────┐                      ││
│  │  │ BeforeLLMCall     │  │ AfterLLMCall     │                      ││
│  │  │ HookMethod        │  │ HookMethod       │                      ││
│  │  │ (描述符协议)       │  │ (描述符协议)      │                      ││
│  │  └──────────────────┘  └──────────────────┘                      ││
│  │  ┌──────────────────┐  ┌──────────────────┐                      ││
│  │  │ BeforeToolCall    │  │ AfterToolCall    │                      ││
│  │  │ HookMethod        │  │ HookMethod       │                      ││
│  │  └──────────────────┘  └──────────────────┘                      ││
│  └──────────────────────────────────────────────────────────────────┘│
│                                                                       │
│  调用方：agent_utils.py / tool_utils.py                               │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │  _setup_before_llm_call_hooks()    → 遍历 executor 的 hooks 列表 │ │
│  │  _setup_after_llm_call_hooks()     → 支持 Pydantic 模型重新解析   │ │
│  │  tool_utils.py 中的工具执行流程     → 遍历全局 hooks 列表         │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                                                                       │
└──────────────────────────────────────────────────────────────────────┘
```

### 1.3 核心文件清单

| 文件 | 职责 |
|------|------|
| `types.py` | Protocol 类型定义：`Hook` 泛型基类 + 4 种具体 Hook 协议 + 类型别名 |
| `llm_hooks.py` | `LLMCallHookContext` 上下文类 + 全局 LLM 钩子注册/注销/查询/清除 |
| `tool_hooks.py` | `ToolCallHookContext` 上下文类 + 全局工具钩子注册/注销/查询/清除 |
| `decorators.py` | 4 个装饰器 (`@before_llm_call` 等) + `_create_hook_decorator` 工厂函数 |
| `wrappers.py` | 4 个 `HookMethod` 包装器类，用于 `@CrewBase` 类中的方法标记 |
| `__init__.py` | 模块公开 API 汇总 + `clear_all_global_hooks()` 便捷函数 |

---

## 2. 核心实现逻辑详解

### 2.1 types.py — 类型定义层

**源码位置：** `lib/crewai/src/crewai/hooks/types.py`

这是整个钩子系统的**类型基础**，定义了所有钩子函数的签名契约。

#### 2.1.1 Hook 泛型 Protocol

第 16-44 行定义了 `Hook` 泛型 Protocol，这是所有钩子类型的基础：

```python
# 第 12-13 行 — 泛型类型变量
ContextT = TypeVar("ContextT", contravariant=True)  # 逆变：允许接受更宽泛的上下文
ReturnT = TypeVar("ReturnT", covariant=True)         # 协变：允许返回更具体的类型

# 第 16-44 行 — Hook 泛型 Protocol
@runtime_checkable                          # 支持 isinstance() 运行时检查
class Hook(Protocol, Generic[ContextT, ReturnT]):
    def __call__(self, context: ContextT) -> ReturnT: ...
```

**设计要点：**
- 使用 `@runtime_checkable` 装饰器（第 16 行），使得可以在运行时通过 `isinstance(obj, Hook)` 检查对象是否满足协议
- `ContextT` 使用 `contravariant=True`（逆变），意味着如果一个函数接受 `LLMCallHookContext` 的父类型，它也满足协议
- `ReturnT` 使用 `covariant=True`（协变），意味着返回子类型也满足协议

#### 2.1.2 四种具体 Hook Protocol

第 47-123 行定义了四种具体的钩子协议：

**BeforeLLMCallHook（第 47-64 行）：**
```python
class BeforeLLMCallHook(Hook["LLMCallHookContext", bool | None], Protocol):
    def __call__(self, context: LLMCallHookContext) -> bool | None:
        # False = 阻止 LLM 执行
        # True/None = 允许执行
        ...
```

**AfterLLMCallHook（第 67-84 行）：**
```python
class AfterLLMCallHook(Hook["LLMCallHookContext", str | None], Protocol):
    def __call__(self, context: LLMCallHookContext) -> str | None:
        # 返回 str = 修改后的响应
        # 返回 None = 保持原响应
        ...
```

**BeforeToolCallHook（第 87-104 行）：**
```python
class BeforeToolCallHook(Hook["ToolCallHookContext", bool | None], Protocol):
    def __call__(self, context: ToolCallHookContext) -> bool | None:
        # False = 阻止工具执行
        # True/None = 允许执行
        ...
```

**AfterToolCallHook（第 107-123 行）：**
```python
class AfterToolCallHook(Hook["ToolCallHookContext", str | None], Protocol):
    def __call__(self, context: ToolCallHookContext) -> str | None:
        # 返回 str = 修改后的工具结果
        # 返回 None = 保持原结果
        ...
```

**统一规则（第 126-127 行注释）：**
```
# All before hooks: bool | None → False = block, True/None = allow
# All after hooks:  str | None  → str = modified result, None = keep original
```

#### 2.1.3 类型别名

第 128-137 行定义了两种类型的别名：

```python
# 第 128-131 行 — Protocol 类型别名（推荐用于 isinstance 检查）
BeforeLLMCallHookType = Hook["LLMCallHookContext", bool | None]
AfterLLMCallHookType = Hook["LLMCallHookContext", str | None]
BeforeToolCallHookType = Hook["ToolCallHookContext", bool | None]
AfterToolCallHookType = Hook["ToolCallHookContext", str | None]

# 第 133-137 行 — Callable 类型别名（兼容普通函数）
BeforeLLMCallHookCallable = Callable[["LLMCallHookContext"], bool | None]
AfterLLMCallHookCallable = Callable[["LLMCallHookContext"], str | None]
BeforeToolCallHookCallable = Callable[["ToolCallHookContext"], bool | None]
AfterToolCallHookCallable = Callable[["ToolCallHookContext"], str | None]
```

**设计意图：** 提供 `Type` 和 `Callable` 两套别名，`Type` 版本沿用 `Hook` 泛型 Protocol，支持 `isinstance` 检查；`Callable` 版本更简洁，兼容普通的 lambda 或函数。

---

### 2.2 llm_hooks.py — LLM 生命周期钩子

**源码位置：** `lib/crewai/src/crewai/hooks/llm_hooks.py`

#### 2.2.1 LLMCallHookContext — 上下文对象

第 24-151 行定义了 `LLMCallHookContext`，是传递给 LLM 钩子的核心上下文对象。

**属性设计（第 51-58 行）：**
```python
executor: CrewAgentExecutor | AgentExecutor | LiteAgent | None  # 执行器引用
messages: list[LLMMessage]    # 消息列表（可直接修改）
agent: Any                     # 当前 Agent
task: Any                      # 当前 Task
crew: Any                      # 当前 Crew
llm: BaseLLM | None | str | Any  # LLM 实例
iterations: int                # 当前迭代次数
response: str | None           # LLM 响应（仅 after 钩子有值）
```

**构造函数（第 60-107 行）支持两种模式：**

- **Executor 模式**（第 81-97 行）：传入 `executor` 参数，自动从 executor 中提取 `messages`、`llm`、`iterations`、`agent`、`task`、`crew`。又细分为：
  - `CrewAgentExecutor`（第 86-89 行）：通过 `hasattr(executor, "agent")` 判断，使用 `cast` 安全地访问 `task` 和 `crew`
  - `LiteAgent`（第 90-97 行）：没有 `agent` 属性，使用 `original_agent` 或 executor 自身作为 agent，`task` 和 `crew` 为 None

- **直接模式**（第 98-105 行）：没有 executor 时，手动传入所有参数，`iterations` 设为 0

**关键设计：** `messages` 属性是**直接引用** executor 的消息列表（第 83 行），钩子函数可以直接就地修改列表（`append`、`extend`、`remove`），但**不能替换**列表引用（`context.messages = []`），否则会断开与 executor 的关联。

**request_human_input 方法（第 109-151 行）：**

支持在钩子执行期间暂停输出、请求人类输入。核心流程：
1. 第 138 行：`event_listener.formatter.pause_live_updates()` 暂停实时输出
2. 第 141-142 行：打印提示信息和默认消息
3. 第 143 行：`input().strip()` 等待用户输入
4. 第 150 行：`finally` 块中确保 `resume_live_updates()` 恢复输出

#### 2.2.2 全局钩子注册表

第 153-154 行定义了模块级别的全局钩子列表：
```python
_before_llm_call_hooks: list[BeforeLLMCallHookType | BeforeLLMCallHookCallable] = []
_after_llm_call_hooks: list[AfterLLMCallHookType | AfterLLMCallHookCallable] = []
```

这两个列表是**模块级全局变量**，存储所有通过命令式 API 注册的全局钩子。

#### 2.2.3 注册/注销/查询 API

| 函数 | 行号 | 说明 |
|------|------|------|
| `register_before_llm_call_hook(hook)` | 157-190 | 追加到 `_before_llm_call_hooks` 列表 |
| `register_after_llm_call_hook(hook)` | 193-218 | 追加到 `_after_llm_call_hooks` 列表 |
| `get_before_llm_call_hooks()` | 221-229 | 返回 `_before_llm_call_hooks.copy()`（浅拷贝，避免外部修改） |
| `get_after_llm_call_hooks()` | 232-238 | 返回 `_after_llm_call_hooks.copy()` |
| `unregister_before_llm_call_hook(hook)` | 241-264 | 调用 `list.remove()`，找不到返回 `False` |
| `unregister_after_llm_call_hook(hook)` | 267-290 | 同上 |
| `clear_before_llm_call_hooks()` | 293-307 | `list.clear()`，返回清除数量 |
| `clear_after_llm_call_hooks()` | 310-324 | 同上 |
| `clear_all_llm_call_hooks()` | 327-341 | 清除所有 LLM 钩子，返回 `(before_count, after_count)` |

**关键设计细节：**
- `get_*` 函数返回的是 `.copy()`（第 229、238 行），防止外部代码直接修改内部列表
- `unregister_*` 使用 `try/except ValueError` 模式（第 260-264、286-290 行），处理钩子不存在的情况
- 所有函数都接受 `Type | Callable` 联合类型，兼容两种钩子定义方式

#### 2.2.4 LLM 钩子的实际执行位置

钩子并不在 `llm_hooks.py` 中执行，而是在 `agent_utils.py` 的工具函数中。执行流程如下：

**_setup_before_llm_call_hooks（agent_utils.py 第 1678-1731 行）：**

```
1. 检查 executor_context.before_llm_call_hooks 是否非空（第 1693 行）
2. 创建 LLMCallHookContext(executor_context)（第 1698 行）
3. 遍历 hooks 列表，依次调用 hook(hook_context)（第 1700-1708 行）
4. 任一 hook 返回 False → 打印提示 → 返回 False（阻止 LLM 调用）
5. 检查 messages 是否仍为 list（第 1716 行）：防止钩子错误地替换了列表引用
6. 返回 True（允许 LLM 调用）
```

**_setup_after_llm_call_hooks（agent_utils.py 第 1734-1807 行）：**

```
1. 检查 executor_context.after_llm_call_hooks 是否非空（第 1751 行）
2. 处理 Pydantic 模型响应（第 1756-1759 行）：
   - 如果是 BaseModel → 转为 JSON 字符串
3. 创建 LLMCallHookContext(executor_context, response=hook_response)（第 1764 行）
4. 遍历 hooks 列表，依次调用（第 1766-1769 行）：
   - 钩子返回非 None 字符串 → 替换 hook_response
   - 钩子返回 None → 保持原值
5. 检查 messages 引用完整性（第 1778-1791 行）
6. 如果是 Pydantic 模型且响应被修改（第 1793-1803 行）：
   - 尝试用 model_validate_json 重新解析
   - 解析失败 → 保持原模型
7. 返回修改后的 answer
```

---

### 2.3 tool_hooks.py — 工具生命周期钩子

**源码位置：** `lib/crewai/src/crewai/hooks/tool_hooks.py`

#### 2.3.1 ToolCallHookContext — 上下文对象

第 24-122 行定义了 `ToolCallHookContext`，结构比 `LLMCallHookContext` 更简单，因为工具调用不涉及 executor。

**属性设计（第 47-77 行）：**
```python
tool_name: str              # 工具名称
tool_input: dict[str, Any]   # 工具输入参数（可变字典，就地修改）
tool: CrewStructuredTool     # 工具实例引用
agent: Agent | BaseAgent | None  # 执行 Agent
task: Task | None            # 当前任务
crew: Crew | None            # Crew 实例
tool_result: str | None      # 工具结果字符串（仅 after 钩子有值）
raw_tool_result: Any | None  # 原始 Python 结果（仅 after 钩子有值，不被钩子修改）
```

**关键设计：**
- `tool_input` 是可变字典（第 71 行），钩子通过 `context.tool_input['key'] = value` 就地修改
- 不能替换整个字典（`context.tool_input = {}`），否则不会影响实际工具执行
- `raw_tool_result`（第 77 行）保存原始 Python 对象，不被 after 钩子修改，供调试/审计使用

**request_human_input 方法（第 79-121 行）：**

与 `LLMCallHookContext.request_human_input` 完全相同的实现模式（第 109-121 行），允许在工具执行前进行人工审批。

#### 2.3.2 全局钩子注册表

第 124-125 行定义：
```python
_before_tool_call_hooks: list[BeforeToolCallHookType | BeforeToolCallHookCallable] = []
_after_tool_call_hooks: list[AfterToolCallHookType | AfterToolCallHookCallable] = []
```

API 函数与 LLM 钩子完全对称（第 128-318 行），差异仅在于：
- 函数名：`register_before_tool_call_hook` / `register_after_tool_call_hook`
- 上下文类型：`ToolCallHookContext`
- `clear_all_tool_call_hooks()` 返回 `(before_count, after_count)` 元组

#### 2.3.3 工具钩子的实际执行位置

工具钩子在两个文件中执行，分别处理同步和异步场景：

**同步执行（tool_utils.py 第 91-157 行）：**
```
1. 创建 ToolCallHookContext（第 96-103 行）
2. 遍历 get_before_tool_call_hooks()（第 105-116 行）
   - 任一 hook 返回 False → 阻止工具执行
3. 执行工具（第 118 行）
4. 创建 after_hook_context（第 121-130 行），包含 tool_result 和 raw_tool_result
5. 遍历 get_after_tool_call_hooks()（第 132-139 行）
   - 钩子返回非 None 字符串 → 替换结果
```

**异步执行（tool_utils.py 第 211-257 行）：** 流程与同步完全一致，只是工具执行使用 `await tool_usage.ause()`。

**agent_utils.py 中的执行（第 1440-1596 行）：** 处理 `NativeToolCallResult` 格式的工具调用，流程相同。

---

### 2.4 decorators.py — 装饰器注册

**源码位置：** `lib/crewai/src/crewai/hooks/decorators.py`

#### 2.4.1 _create_hook_decorator — 工厂函数

第 18-85 行定义了一个**工厂函数**，消除了四个装饰器的重复代码。

**核心逻辑：**

```python
def _create_hook_decorator(
    hook_type: str,                           # "llm" 或 "tool"
    register_function: Callable[..., Any],    # 注册函数引用
    marker_attribute: str,                    # 标记属性名
) -> Callable[..., Any]:
```

**内部 decorator_factory 函数（第 36-83 行）的关键逻辑：**

1. **工具名清理**（第 42-43 行）：如果指定了 `tools` 过滤，先调用 `sanitize_tool_name()` 标准化工具名
2. **标记属性**（第 46 行）：`setattr(f, marker_attribute, True)` 在函数上设置标记，用于后续 `@CrewBase` 类扫描
3. **方法检测**（第 48-50 行）：通过 `inspect.signature` 检查第一个参数是否为 `self`，判断是函数还是实例方法
4. **过滤逻辑**（第 57-69 行）：当指定了 `tools` 或 `agents` 过滤时，创建 `filtered_hook` 闭包：
   - `tools` 过滤（第 61-63 行）：检查 `context.tool_name` 是否在过滤列表中
   - `agents` 过滤（第 65-67 行）：检查 `context.agent.role` 是否在过滤列表中
   - 不匹配时返回 `None`（允许继续执行）
5. **自动注册**（第 71-77 行）：
   - **非方法**（`not is_method`）：自动调用 `register_function()` 注册到全局钩子列表
   - **方法**（`is_method`）：跳过自动注册，由 `@CrewBase` 类初始化时手动注册
6. **双模式支持**（第 81-83 行）：支持 `@before_llm_call`（无参数）和 `@before_llm_call(agents=["X"])`（带参数）两种用法

**大白话：** 这个工厂函数像一个"钩子装饰器生成器"，接收注册函数和标记属性，返回一个装饰器。装饰器内部自动判断被装饰的是函数还是方法——函数直接全局注册，方法留到 `@CrewBase` 类实例化时再绑定。

#### 2.4.2 四个公开装饰器

**before_llm_call（第 88-134 行）：**
- 支持 `@before_llm_call` 和 `@before_llm_call(agents=["..."])` 两种用法
- 通过 `@overload` 提供类型提示（第 88-100 行）
- 调用 `_create_hook_decorator(hook_type="llm", register_function=register_before_llm_call_hook, marker_attribute="is_before_llm_call_hook")`
- 仅支持 `agents` 过滤（因为 LLM 调用不涉及具体工具）

**after_llm_call（第 137-188 行）：**
- 结构同 `before_llm_call`，差异在 `register_function=register_after_llm_call_hook`

**before_tool_call（第 191-249 行）：**
- 支持 `tools` 和 `agents` 两种过滤参数
- 可以组合使用：`@before_tool_call(tools=["write_file"], agents=["Developer"])`

**after_tool_call（第 252-305 行）：**
- 同样支持 `tools` 和 `agents` 过滤

**所有装饰器都使用延迟导入**（第 128、182、243、299 行），在函数体内才 `from crewai.hooks.xxx import register_xxx`，避免循环导入。

---

### 2.5 wrappers.py — 包装器

**源码位置：** `lib/crewai/src/crewai/hooks/wrappers.py`

#### 2.5.1 元数据复制工具

第 15-26 行的 `_copy_method_metadata` 函数：
```python
def _copy_method_metadata(wrapper, original):
    wrapper.__name__ = original.__name__
    wrapper.__doc__ = original.__doc__
    wrapper.__module__ = original.__module__
    wrapper.__qualname__ = original.__qualname__
    wrapper.__annotations__ = original.__annotations__
```

手动复制函数元数据，确保包装后的方法在调试和文档生成时表现正常。

#### 2.5.2 四种 HookMethod 包装器

每个包装器类都遵循相同的模式，以 `BeforeLLMCallHookMethod`（第 29-74 行）为例：

**类属性标记（第 36 行）：**
```python
is_before_llm_call_hook: bool = True
```
这个类属性用于 `@CrewBase` 类扫描时识别钩子方法。

**构造函数（第 38-51 行）：**
- 保存原始方法 `_meth` 和过滤参数 `agents`
- 调用 `_copy_method_metadata` 复制元数据

**描述符协议（第 62-74 行）：**
```python
def __get__(self, obj, objtype=None):
    if obj is None:
        return self        # 通过类访问，返回包装器本身
    return lambda context: self._meth(obj, context)  # 通过实例访问，返回绑定了 self 的 lambda
```

**关键设计：** 通过实现 `__get__` 方法（描述符协议），包装器支持两种访问方式：
- 类级别访问：`MyCrew.my_hook` → 返回 `BeforeLLMCallHookMethod` 实例
- 实例级别访问：`crew.my_hook` → 返回 `lambda context: self._meth(crew, context)`

这使得 `@CrewBase` 类在初始化时可以扫描类属性找到标记的方法，然后绑定到实例上。

**四种包装器的差异：**

| 包装器 | 过滤参数 | 返回值类型 |
|--------|----------|-----------|
| `BeforeLLMCallHookMethod` | `agents` | `None` |
| `AfterLLMCallHookMethod` | `agents` | `str \| None` |
| `BeforeToolCallHookMethod` | `tools`, `agents` | `bool \| None` |
| `AfterToolCallHookMethod` | `tools`, `agents` | `str \| None` |

---

## 3. 完整调用时序图

```
┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│   Crew       │   │  Executor    │   │  agent_utils │   │  LLM/Tool    │
│  kickoff()   │   │  invoke()    │   │  /tool_utils │   │  Provider    │
└──────┬───────┘   └──────┬───────┘   └──────┬───────┘   └──────┬───────┘
       │                  │                  │                  │
       │  kickoff()       │                  │                  │
       │─────────────────>│                  │                  │
       │                  │                  │                  │
       │                  │  ┌───────────────────────────────────────────┐
       │                  │  │ 初始化时加载全局钩子到 executor:            │
       │                  │  │ executor.before_llm_call_hooks =           │
       │                  │  │   get_before_llm_call_hooks()              │
       │                  │  │ executor.after_llm_call_hooks =            │
       │                  │  │   get_after_llm_call_hooks()               │
       │                  │  └───────────────────────────────────────────┘
       │                  │                  │                  │
       │                  │  ┌─ ReAct Loop ──────────────────────────────┐
       │                  │  │               │                  │         │
       │                  │  │ ① LLM 调用前  │                  │         │
       │                  │  │────────────────────────────────>│         │
       │                  │  │               │                  │         │
       │                  │  │    _setup_before_llm_call_hooks()          │
       │                  │  │    ├─ 创建 LLMCallHookContext(executor)    │
       │                  │  │    ├─ 遍历 executor.before_llm_call_hooks │
       │                  │  │    ├─ hook(context) → False? 阻止调用      │
       │                  │  │    └─ 检查 messages 引用完整性             │
       │                  │  │               │                  │         │
       │                  │  │ ② 实际 LLM 调用                           │
       │                  │  │──────────────────────────────────────────>│
       │                  │  │<───────────────────────────────────────────│
       │                  │  │   返回 response                            │
       │                  │  │               │                  │         │
       │                  │  │ ③ LLM 调用后  │                  │         │
       │                  │  │    _setup_after_llm_call_hooks()           │
       │                  │  │    ├─ 创建 LLMCallHookContext(executor,    │
       │                  │  │    │              response=answer)          │
       │                  │  │    ├─ 遍历 executor.after_llm_call_hooks  │
       │                  │  │    ├─ 钩子返回 str → 替换 response         │
       │                  │  │    ├─ Pydantic → 重新 model_validate_json  │
       │                  │  │    └─ 检查 messages 引用完整性             │
       │                  │  │               │                  │         │
       │                  │  │ ④ 解析工具调用                            │
       │                  │  │               │                  │         │
       │                  │  │ ⑤ 工具调用前  │                  │         │
       │                  │  │    ├─ 创建 ToolCallHookContext             │
       │                  │  │    ├─ 遍历 get_before_tool_call_hooks()   │
       │                  │  │    └─ hook(context) → False? 阻止执行      │
       │                  │  │               │                  │         │
       │                  │  │ ⑥ 实际工具执行                            │
       │                  │  │──────────────────────────────────────────>│
       │                  │  │<───────────────────────────────────────────│
       │                  │  │   返回 tool_result                         │
       │                  │  │               │                  │         │
       │                  │  │ ⑦ 工具调用后  │                  │         │
       │                  │  │    ├─ 创建 ToolCallHookContext(包含结果)   │
       │                  │  │    ├─ 遍历 get_after_tool_call_hooks()    │
       │                  │  │    └─ 钩子返回 str → 替换 result           │
       │                  │  │               │                  │         │
       │                  │  └───────────────────────────────────────────┘         │
       │                  │                  │                  │         │
       │<─────────────────│  返回最终结果    │                  │         │
       │                  │                  │                  │         │
```

**关键时序说明：**

1. **全局钩子加载时机**：在 Executor 构造函数中，通过 `get_before_llm_call_hooks()` 和 `get_after_llm_call_hooks()` 获取全局钩子列表的**快照**，赋值给 `executor.before_llm_call_hooks` 和 `executor.after_llm_call_hooks`。这意味着在 Executor 创建后注册的新全局钩子不会影响已创建的 Executor。

2. **工具钩子每次实时获取**：与 LLM 钩子不同，工具钩子每次调用时都通过 `get_before_tool_call_hooks()` 实时获取最新列表，因此工具钩子支持动态注册。

3. **钩子异常处理**：所有钩子执行都包裹在 `try/except Exception` 中，钩子抛出的异常不会中断主流程，只会打印警告日志。

---

## 4. 完整可运行示例

### 示例 1：LLM 调用日志与迭代限制

```python
"""示例 1：记录 LLM 调用日志，并对超过 5 次迭代的调用进行阻止。

演示：before_llm_call + after_llm_call 的基本用法，以及
通过返回 False 阻止 LLM 调用的机制。
"""

from crewai import Agent, Task, Crew
from crewai.hooks import (
    LLMCallHookContext,
    register_before_llm_call_hook,
    register_after_llm_call_hook,
)


# --- 定义钩子 ---

def log_before_llm_call(context: LLMCallHookContext) -> bool | None:
    """每次 LLM 调用前：记录迭代次数和消息数量。"""
    print(f"[Before LLM] 迭代 #{context.iterations}, 消息数: {len(context.messages)}")

    # 超过 5 次迭代 → 阻止 LLM 调用
    if context.iterations > 5:
        print(f"[Before LLM] ⛔ 迭代次数超过上限，阻止 LLM 调用")
        return False
    return None  # 允许执行


def log_after_llm_call(context: LLMCallHookContext) -> str | None:
    """每次 LLM 调用后：记录响应长度。"""
    if context.response:
        print(f"[After LLM]  响应长度: {len(context.response)} 字符")
    return None  # 保持原响应


# --- 注册全局钩子 ---
register_before_llm_call_hook(log_before_llm_call)
register_after_llm_call_hook(log_after_llm_call)

# --- 创建 Agent 和 Crew ---
agent = Agent(
    role="分析助手",
    goal="回答用户的问题",
    backstory="你是一个乐于助人的分析助手。",
    max_iter=3,  # 限制迭代次数，避免无限循环
)

task = Task(
    description="简要回答：什么是 Python？",
    expected_output="一段简洁的 Python 介绍。",
    agent=agent,
)

crew = Crew(agents=[agent], tasks=[task], verbose=False)
result = crew.kickoff()

print(f"\n✅ 最终结果: {result.raw}")
```

**预期输出：**
```
[Before LLM] 迭代 #1, 消息数: 2
[After LLM]  响应长度: xxx 字符
[Before LLM] 迭代 #2, 消息数: 4
[After LLM]  响应长度: xxx 字符
✅ 最终结果: Python 是一种...
```

---

### 示例 2：工具调用安全审批（人工介入）

```python
"""示例 2：通过 before_tool_call 钩子实现工具调用人工审批。

演示：ToolCallHookContext、request_human_input、返回 False 阻止执行。
"""

from crewai import Agent, Task, Crew
from crewai.hooks import ToolCallHookContext, register_before_tool_call_hook
from crewai.tools import tool


# --- 定义工具 ---
@tool("delete_file")
def delete_file_tool(file_path: str) -> str:
    """模拟删除文件。"""
    return f"文件 {file_path} 已删除"


@tool("read_file")
def read_file_tool(file_path: str) -> str:
    """模拟读取文件。"""
    return f"文件 {file_path} 的内容: Hello, World!"


# --- 定义钩子：对所有 "delete_file" 工具调用进行审批 ---
def approve_dangerous_tools(context: ToolCallHookContext) -> bool | None:
    if context.tool_name == "delete_file":
        print(f"\n⚠️  检测到危险操作：{context.tool_name}")
        print(f"   参数: {context.tool_input}")

        # 在交互环境中，这里会等待用户输入
        # 为了示例可自动运行，我们模拟一个拒绝响应
        response = context.request_human_input(
            prompt="是否允许此操作？",
            default_message="输入 'yes' 允许，其他任意键拒绝:",
        )
        if response.lower() != "yes":
            print(f"   ❌ 操作被拒绝")
            return False  # 阻止工具执行
        print(f"   ✅ 操作被批准")
    return None  # 允许执行


# --- 注册全局钩子 ---
register_before_tool_call_hook(approve_dangerous_tools)

# --- 创建 Agent 和 Crew ---
agent = Agent(
    role="文件管理员",
    goal="读取并删除指定文件",
    backstory="你是一个文件管理员，负责管理文件系统。",
    tools=[delete_file_tool, read_file_tool],
)

task = Task(
    description="先读取文件 /tmp/test.txt，然后删除它。",
    expected_output="确认文件已读取并删除。",
    agent=agent,
)

crew = Crew(agents=[agent], tasks=[task], verbose=False)
result = crew.kickoff()

print(f"\n✅ 最终结果: {result.raw}")
```

---

### 示例 3：装饰器注册 + 过滤

```python
"""示例 3：使用装饰器注册钩子，并通过 agents 过滤指定目标。

演示：@before_llm_call、@after_llm_call、@before_tool_call 装饰器，
以及 agents 过滤参数的使用。
"""

from crewai import Agent, Task, Crew
from crewai.hooks import (
    LLMCallHookContext,
    ToolCallHookContext,
    before_llm_call,
    after_llm_call,
    before_tool_call,
)
from crewai.tools import tool


# --- 定义工具 ---
@tool("search")
def search_tool(query: str) -> str:
    """模拟搜索。"""
    return f"搜索结果: 关于 '{query}' 的信息..."


# --- 使用装饰器注册钩子 ---

@before_llm_call(agents=["研究员"])  # 仅对角色为"研究员"的 Agent 生效
def researcher_before_hook(context: LLMCallHookContext) -> bool | None:
    print(f"[研究员-Before] 调用 LLM，消息数: {len(context.messages)}")
    return None


@after_llm_call(agents=["研究员"])  # 仅对角色为"研究员"的 Agent 生效
def researcher_after_hook(context: LLMCallHookContext) -> str | None:
    if context.response:
        # 在研究员响应前添加标记
        return f"[研究员标记] {context.response}"
    return None


@before_tool_call(agents=["研究员"])  # 仅对研究员使用工具时触发
def log_researcher_tools(context: ToolCallHookContext) -> bool | None:
    print(f"[研究员-工具] 调用工具: {context.tool_name}, 参数: {context.tool_input}")
    return None


# --- 创建 Agent 和 Crew ---
researcher = Agent(
    role="研究员",
    goal="研究并回答用户问题",
    backstory="你是一个研究员，擅长搜索和分析信息。",
    tools=[search_tool],
)

writer = Agent(
    role="写手",
    goal="撰写报告",
    backstory="你是一个写手，负责撰写最终报告。",
)

task = Task(
    description='搜索 "Python 最佳实践" 并撰写简短报告。',
    expected_output="一份简短报告。",
    agent=researcher,
)

crew = Crew(agents=[researcher, writer], tasks=[task], verbose=False)
result = crew.kickoff()

print(f"\n✅ 最终结果: {result.raw}")
```

**说明：** 由于 `agents=["研究员"]` 过滤，钩子只对"研究员" Agent 触发。如果任务由"写手"执行，钩子不会触发。

---

### 示例 4：after_tool_call 结果清理

```python
"""示例 4：通过 after_tool_call 钩子清理工具返回中的敏感信息。

演示：@after_tool_call 装饰器、tools 过滤、返回修改后的结果。
"""

from crewai import Agent, Task, Crew
from crewai.hooks import ToolCallHookContext, after_tool_call
from crewai.tools import tool


# --- 定义工具 ---
@tool("api_call")
def api_call_tool(endpoint: str) -> str:
    """模拟 API 调用，返回包含敏感信息的结果。"""
    return f'{{"data": "ok", "api_key": "sk-abc123xyz", "endpoint": "{endpoint}"}}'


@tool("read_file")
def read_file_tool(path: str) -> str:
    """模拟读取文件。"""
    return f"文件内容: 普通文本，无敏感信息"


# --- 使用装饰器注册钩子：仅对 api_call 工具的结果进行清理 ---

@after_tool_call(tools=["api_call"])
def sanitize_api_results(context: ToolCallHookContext) -> str | None:
    """清理 API 返回结果中的敏感信息。"""
    if context.tool_result and "api_key" in context.tool_result:
        print(f"[清理] 检测到 api_key，执行脱敏处理...")
        sanitized = context.tool_result.replace("sk-abc123xyz", "sk-***REDACTED***")
        return sanitized
    return None  # 保持原结果


# --- 创建 Agent 和 Crew ---
agent = Agent(
    role="API 测试员",
    goal="调用 API 并读取文件",
    backstory="你是一个 API 测试员。",
    tools=[api_call_tool, read_file_tool],
)

task = Task(
    description="调用 api_call 工具查询 /users 端点，然后读取 /tmp/config.txt 文件。",
    expected_output="API 调用结果和文件内容。",
    agent=agent,
)

crew = Crew(agents=[agent], tasks=[task], verbose=False)
result = crew.kickoff()

print(f"\n✅ 最终结果: {result.raw}")
```

**预期输出：** 工具返回的 `api_key` 值会被替换为 `sk-***REDACTED***`，而 `read_file` 工具的结果不受影响。

---

### 示例 5：动态钩子注册/注销

```python
"""示例 5：演示钩子的动态注册、注销和清除操作。

演示：register_*、unregister_*、get_*、clear_* 系列 API 的完整用法。
"""

from crewai.hooks import (
    LLMCallHookContext,
    register_before_llm_call_hook,
    register_after_llm_call_hook,
    unregister_before_llm_call_hook,
    get_before_llm_call_hooks,
    get_after_llm_call_hooks,
    clear_before_llm_call_hooks,
    clear_all_global_hooks,
)


# --- 定义几个钩子函数 ---
def hook_a(context: LLMCallHookContext) -> bool | None:
    print("Hook A 执行")
    return None


def hook_b(context: LLMCallHookContext) -> bool | None:
    print("Hook B 执行")
    return None


def hook_c(context: LLMCallHookContext) -> bool | None:
    print("Hook C 执行")
    return None


# --- 1. 注册钩子 ---
register_before_llm_call_hook(hook_a)
register_before_llm_call_hook(hook_b)
register_before_llm_call_hook(hook_c)
register_after_llm_call_hook(lambda ctx: None)

print(f"注册后 before 钩子数: {len(get_before_llm_call_hooks())}")  # 3
print(f"注册后 after 钩子数: {len(get_after_llm_call_hooks())}")     # 1

# --- 2. 注销单个钩子 ---
removed = unregister_before_llm_call_hook(hook_b)
print(f"注销 hook_b: {'成功' if removed else '失败'}")  # 成功

# 重复注销 → 失败
removed = unregister_before_llm_call_hook(hook_b)
print(f"重复注销 hook_b: {'成功' if removed else '失败'}")  # 失败

print(f"注销后 before 钩子数: {len(get_before_llm_call_hooks())}")  # 2

# --- 3. 清除所有 before 钩子 ---
cleared = clear_before_llm_call_hooks()
print(f"清除 before 钩子数: {cleared}")  # 2
print(f"清除后 before 钩子数: {len(get_before_llm_call_hooks())}")  # 0

# --- 4. 一键清除所有全局钩子 ---
result = clear_all_global_hooks()
print(f"最终清除结果: {result}")
# 输出: {'llm_hooks': (0, 1), 'tool_hooks': (0, 0), 'total': (0, 1)}
```

---

## 5. 设计亮点与注意事项

### 5.1 设计亮点

1. **工厂函数消除重复**：`decorators.py` 中的 `_create_hook_decorator`（第 18-85 行）是一个典型的工厂模式应用。四个装饰器（`before_llm_call`、`after_llm_call`、`before_tool_call`、`after_tool_call`）共享完全相同的逻辑结构，差异仅在于：注册函数、标记属性、是否支持 `tools` 过滤。通过工厂函数，将约 200 行重复代码压缩为约 30 行核心逻辑。

2. **Protocol + Callable 双类型体系**：`types.py` 同时提供 `BeforeLLMCallHookType`（Protocol 类型，第 128 行）和 `BeforeLLMCallHookCallable`（Callable 类型，第 134 行），兼顾了类型检查的严谨性（Protocol 支持 `isinstance` 检查）和使用的简洁性（Callable 对 lambda 更友好）。

3. **防御性编程 - 引用完整性保护**：在 `agent_utils.py` 的 `_setup_before_llm_call_hooks`（第 1716-1729 行）和 `_setup_after_llm_call_hooks`（第 1778-1791 行）中，都检查了 `messages` 是否仍为 `list` 类型——如果钩子错误地执行了 `context.messages = []`，框架会自动恢复原始引用并打印警告。这是对"就地修改"约定的强约束保护。

4. **描述符协议支持 @CrewBase 类方法**：`wrappers.py` 中的四个 `HookMethod` 类通过实现 `__get__`（如第 62-74 行），使得钩子方法可以在 `@CrewBase` 类中作为实例方法使用，同时保留了类级别的扫描能力。

5. **Pydantic 响应往返支持**：`_setup_after_llm_call_hooks`（agent_utils.py 第 1756-1803 行）能够处理 Pydantic 模型响应：将模型转为 JSON → 钩子修改 → 尝试重新解析为原模型。解析失败时保持原模型，确保类型安全。

### 5.2 注意事项

1. **全局钩子快照时机**：LLM 全局钩子在 Executor 构造时加载为快照（`get_before_llm_call_hooks()` 返回的是 `.copy()`），Executor 创建后注册的新钩子对其无效。如果需要动态注册，应使用工具钩子（每次实时获取）或在 Executor 创建前完成注册。

2. **就地修改 vs 替换引用**：所有上下文对象中的可变属性（`messages`、`tool_input`）都要求**就地修改**而非替换引用。例如：
   - ✅ 正确：`context.messages.append(msg)` / `context.tool_input['key'] = value`
   - ❌ 错误：`context.messages = new_list` / `context.tool_input = new_dict`

3. **钩子异常被静默捕获**：所有钩子执行都包裹在 `try/except Exception` 中（如 agent_utils.py 第 1709-1714 行），异常不会中断主流程。如果钩子中有关键逻辑，应在钩子内部自行处理异常和日志。

4. **方法 vs 函数的自动注册差异**：装饰器通过 `inspect.signature` 检测第一个参数是否为 `self`（decorators.py 第 48-50 行）来判断是函数还是方法。函数会被自动注册到全局钩子列表，而方法不会——由 `@CrewBase` 类在初始化时手动注册。这要求 `@CrewBase` 类中的钩子方法第一个参数必须是 `self`。

5. **工具名标准化**：在装饰器中指定 `tools` 过滤时，工具名会通过 `sanitize_tool_name()` 标准化（decorators.py 第 43 行），确保与注册的工具名格式一致。

6. **Python 版本要求**：`Protocol` 的 `@runtime_checkable` 需要 Python 3.8+，`TypeVar` 的 `contravariant`/`covariant` 需要在 `from __future__ import annotations` 下使用（Python 3.12+ 原生支持）。