# CrewAI 从0到1构建指南

> 以应用开发工程师视角，从头构建一个多Agent协作框架

---

## 目录

1. [项目概述与架构蓝图](#1-项目概述与架构蓝图)
2. [第一阶段：数据模型层 — Pydantic 基石](#2-第一阶段数据模型层--pydantic-基石)
3. [第二阶段：LLM 抽象层 — 多模型统一接口](#3-第二阶段llm-抽象层--多模型统一接口)
4. [第三阶段：工具系统 — Agent 的手和脚](#4-第三阶段工具系统--agent-的手和脚)
5. [第四阶段：事件总线 — 系统的神经中枢](#5-第四阶段事件总线--系统的神经中枢)
6. [第五阶段：Prompt 管理 — Agent 的大脑语言](#6-第五阶段prompt-管理--agent-的大脑语言)
7. [第六阶段：核心 Agent 类 — 智能体本体](#7-第六阶段核心-agent-类--智能体本体)
8. [第七阶段：Task 任务定义 — 工作单元](#8-第七阶段task-任务定义--工作单元)
9. [第八阶段：Agent 执行器 — 思考-行动循环](#9-第八阶段agent-执行器--思考-行动循环)
10. [第九阶段：Crew 调度引擎 — 多Agent编排](#10-第九阶段crew-调度引擎--多agent编排)
11. [第十阶段：记忆系统 — 持久化上下文](#11-第十阶段记忆系统--持久化上下文)
12. [第十一阶段：知识检索 RAG — 外部知识注入](#12-第十一阶段知识检索-rag--外部知识注入)
13. [第十二阶段：Flow 工作流 — 声明式编排](#13-第十二阶段flow-工作流--声明式编排)
14. [第十三阶段：高级特性 — Hook、State、MCP、A2A](#14-第十三阶段高级特性--hookstatemcpa2a)
15. [第十四阶段：CLI 与 Project 脚手架](#15-第十四阶段cli-与-project-脚手架)
16. [附录：完整目录结构](#16-附录完整目录结构)

---

## 1. 项目概述与架构蓝图

### 1.1 我们要做什么

构建一个 **多Agent协作框架**，核心能力：
- 定义 Agent（角色、目标、工具、LLM）
- 定义 Task（任务描述、期望输出、上下文）
- 用 Crew 编排多个 Agent 协作执行 Task
- 支持记忆、知识检索、Hook、Streaming 等高级特性

### 1.2 分层架构图

```
┌──────────────────────────────────────────────────┐
│                   CLI / Project                    │  用户入口
├──────────────────────────────────────────────────┤
│     Crew（调度引擎）         Flow（工作流引擎）      │  编排层
├──────────────────────────────────────────────────┤
│           Agent（智能体）    Task（任务定义）         │  核心层
├──────────────────────────────────────────────────┤
│  AgentExecutor（执行器）     Tools（工具系统）        │  执行层
├──────────────────────────────────────────────────┤
│    BaseLLM（LLM抽象）    EventBus（事件总线）        │  基础设施
├──────────────────────────────────────────────────┤
│  Memory（记忆）  Knowledge（知识）  Hook（钩子）      │  扩展层
└──────────────────────────────────────────────────┘
```

### 1.3 核心调用链

```
Crew.kickoff()
  └─> Crew._run_sequential_process()
        └─> Agent.execute_task(task)
              ├─> 1. 构建 Prompt（role + goal + backstory + task + context）
              ├─> 2. 检索 Memory（历史记忆）
              ├─> 3. 检索 Knowledge（RAG）
              ├─> 4. 准备 Tools
              ├─> 5. AgentExecutor.invoke()  ← ReAct 循环
              │     ├─> LLM.call()           ← 发送 messages
              │     ├─> 解析响应（Thought/Action/Final Answer）
              │     ├─> 执行 Tool（如果需要）
              │     └─> 循环直到 FINISH
              ├─> 6. Guardrail 校验
              └─> 7. 保存到 Memory
```

### 1.4 数据流概览

```
用户输入 (inputs)
  │
  ▼
Task.prompt() ─── 生成任务提示词
  │
  ├── Memory.recall() ─── 注入历史记忆
  ├── Knowledge.query() ─── 注入外部知识
  ├── Tools ─── 转换为 LLM 可调用格式
  │
  ▼
AgentExecutor ─── ReAct 循环
  │
  ├── LLM.call(messages)
  │     ├── LLMCallStartedEvent
  │     └── LLMCallCompletedEvent (含 usage)
  │
  ├── parse(response) ─── AgentAction / AgentFinish
  │
  ├── Tool._run() ─── 执行工具
  │     ├── ToolUsageStartedEvent
  │     └── ToolUsageFinishedEvent
  │
  └── AgentFinish ─── 最终输出
  │
  ▼
TaskOutput ─── 结构化输出
  │
  ▼
CrewOutput ─── 聚合所有 Task 输出
```

---

## 2. 第一阶段：数据模型层 — Pydantic 基石

### 2.1 为什么选 Pydantic

CrewAI 全部核心类都是 Pydantic BaseModel：

- **自动校验**：`@model_validator` 和 `@field_validator` 保证数据一致性
- **序列化**：`model_dump()` / `model_validate()` 支持 checkpoint 持久化
- **类型安全**：IDE 自动补全、mypy 静态检查
- **JSON Schema**：自动生成工具的 input schema 给 LLM

### 2.2 用户示例

```python
from pydantic import BaseModel, Field, model_validator

class AgentConfig(BaseModel):
    role: str = Field(description="Agent 的角色")
    goal: str = Field(description="Agent 的目标")
    llm: str | None = Field(default=None)

    @model_validator(mode="after")
    def validate_role(self):
        if not self.role.strip():
            raise ValueError("role 不能为空")
        return self
```

### 2.3 源码实现要点

**2.3.1 复杂字段的序列化**

源码位置：[lib/crewai/src/crewai/agent/core.py#L215-L219](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/agent/core.py#L215-L219)

```python
llm: Annotated[
    str | BaseLLM | None,
    BeforeValidator(_validate_llm_ref),  # 输入时转换：str -> BaseLLM
    PlainSerializer(_serialize_llm_ref, return_type=dict | None, when_used="json"),  # 序列化时转换
] = Field(description="Language model that will run the agent.", default=None)
```

**2.3.2 PrivateAttr 与 Field 的区别**

源码位置：[lib/crewai/src/crewai/agent/core.py#L200-L202](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/agent/core.py#L200-L202)

```python
_times_executed: int = PrivateAttr(default=0)  # 不对用户暴露，不参与序列化
_mcp_resolver: MCPToolResolver | None = PrivateAttr(default=None)
_last_messages: list[LLMMessage] = PrivateAttr(default_factory=list)
```

**设计决策**：
- `PrivateAttr`：运行时状态，不参与校验和序列化
- `Field`：用户可配置的公共属性，参与校验和序列化

### 2.4 实现步骤

```
Step 1: 安装 pydantic
Step 2: 定义核心数据模型基类
Step 3: 添加 BeforeValidator / PlainSerializer 处理复杂类型
Step 4: 用 model_validator 实现跨字段校验
```

---

## 3. 第二阶段：LLM 抽象层 — 多模型统一接口

### 3.1 设计目标

支持 OpenAI、Anthropic、Azure、Gemini、Bedrock 等所有主流 LLM 提供商，通过统一接口调用。

### 3.2 用户示例

```python
from crewai import LLM

# 方式1：字符串配置
llm = LLM(model="gpt-4o")

# 方式2：完整配置
llm = LLM(
    model="gpt-4o",
    api_key="sk-xxx",
    temperature=0.7,
    max_tokens=4096,
    stop=["Observation:"],
)

# 方式3：直接使用
response = llm.call(
    messages=[{"role": "user", "content": "Hello"}],
    tools=[...],  # 可选：function calling
    response_format=MyModel,  # 可选：结构化输出
)
```

### 3.3 源码架构

**核心类层次**：

```
BaseLLM (ABC)  ← 抽象基类（源码位置：lib/crewai/src/crewai/llms/base_llm.py#L150）
  ├── call()      ← 同步调用（抽象方法）
  ├── acall()     ← 异步调用（抽象方法）
  ├── supports_function_calling()  ← 是否支持原生 function calling
  └── stop_sequences  ← 自定义 stop words

子类实现：
  ├── OpenAICompletion   (lib/crewai/src/crewai/llms/providers/openai/completion.py)
  ├── AnthropicCompletion (lib/crewai/src/crewai/llms/providers/anthropic/completion.py)
  ├── AzureCompletion    (lib/crewai/src/crewai/llms/providers/azure/completion.py)
  ├── BedrockCompletion  (lib/crewai/src/crewai/llms/providers/bedrock/completion.py)
  ├── GeminiCompletion   (lib/crewai/src/crewai/llms/providers/gemini/completion.py)
  └── OpenAICompatibleCompletion (lib/crewai/src/crewai/llms/providers/openai_compatible/completion.py)
```

**关键设计：contextvars 实现线程安全**

源码位置：[lib/crewai/src/crewai/llms/base_llm.py#L79-L124](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/llms/base_llm.py#L79-L124)

```python
_current_call_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(...)
_call_stop_override_var: contextvars.ContextVar[...] = contextvars.ContextVar(...)
_call_stream_override_var: contextvars.ContextVar[...] = contextvars.ContextVar(...)

@contextmanager
def llm_call_context() -> Generator[str, None, None]:
    """每次 LLM 调用都在独立上下文中，支持并发安全"""
    call_id = str(uuid.uuid4())
    token = _current_call_id.set(call_id)
    try:
        yield call_id
    finally:
        _current_call_id.reset(token)
```

**为什么用 contextvars 而不是全局变量**：Python 的 `contextvars` 是协程安全的，每个 `asyncio.Task` 有独立上下文，适合异步并发场景。

### 3.4 事件发射

每次 LLM 调用自动发射事件（源码位置：[lib/crewai/src/crewai/llms/base_llm.py#L31-L39](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/llms/base_llm.py#L31-L39)）：

```python
LLMCallStartedEvent  →  LLM 调用开始
LLMStreamChunkEvent  →  流式输出 chunk
LLMThinkingChunkEvent →  推理过程 chunk（如 Claude thinking）
LLMCallCompletedEvent →  LLM 调用完成（含 usage metrics）
LLMCallFailedEvent   →  LLM 调用失败
```

### 3.5 实现步骤

```
Step 1: 定义 BaseLLM 抽象类（call, acall 抽象方法）
Step 2: 实现 contextvars 管理（call_id, stop_override, stream_override）
Step 3: 实现事件发射（LLMCallStarted/Completed/Failed）
Step 4: 逐个实现各 Provider 子类
Step 5: 实现 LLM 工厂函数 create_llm()（lib/crewai/src/crewai/utilities/llm_utils.py）
```

---

## 4. 第三阶段：工具系统 — Agent 的手和脚

### 4.1 设计目标

让 Agent 能调用外部工具完成任务（搜索、读文件、调 API 等），支持两种模式：
- **Native Function Calling**：利用 LLM 原生 function calling（OpenAI/Anthropic）
- **Text Tool Calling**：通过 Prompt 文本描述让 LLM 按格式输出工具调用

### 4.2 用户示例

```python
from crewai.tools import BaseTool

# 方式1：继承 BaseTool
class SearchTool(BaseTool):
    name: str = "Web Search"
    description: str = "搜索互联网获取信息"

    def _run(self, query: str) -> str:
        # 实际搜索逻辑
        return f"搜索结果: {query}"

# 方式2：使用 @tool 装饰器
from crewai.tools import tool

@tool("计算器")
def calculator(expression: str) -> str:
    return str(eval(expression))

# 方式3：使用 CrewStructuredTool（LangChain 兼容）
from crewai.tools import CrewStructuredTool
```

### 4.3 源码架构

**核心类层次**：

```
BaseTool (Pydantic BaseModel)  ← 源码位置：lib/crewai/src/crewai/tools/base_tool.py#L102
  ├── name: str
  ├── description: str
  ├── args_schema: type[BaseModel]  ← 自动从 _run 签名推断
  ├── _run()          ← 同步执行（子类实现）
  ├── _arun()         ← 异步执行（可选）
  ├── cache_function  ← 缓存策略
  └── result_as_answer: bool  ← 结果是否直接作为最终答案

CrewStructuredTool  ← 源码位置：lib/crewai/src/crewai/tools/structured_tool.py
  ├── 包装任意 callable 为 LangChain 兼容工具
  └── 自动推断 args_schema 和 result_schema
```

**关键设计：自动生成 JSON Schema**

源码位置：[lib/crewai/src/crewai/tools/structured_tool.py#L183](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/tools/structured_tool.py#L183)

```python
class CrewStructuredTool:
    """从 callable 自动生成 Pydantic args_schema"""
    @classmethod
    def from_function(cls, func: Callable, ...) -> CrewStructuredTool:
        # 1. 分析 func 的 type hints
        # 2. 生成 Pydantic model 作为 args_schema
        # 3. 生成 JSON Schema 描述给 LLM
        pass
```

### 4.4 Native vs Text Tool Calling 双模式

源码位置：[lib/crewai/src/crewai/utilities/agent_utils.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/utilities/agent_utils.py)

```python
def check_native_tool_support(llm: BaseLLM, tools: list[BaseTool]) -> bool:
    """检测 LLM 是否支持原生 function calling"""
    return (
        hasattr(llm, "supports_function_calling")
        and llm.supports_function_calling()
        and len(tools) > 0
    )

def setup_native_tools(tools: list[BaseTool]) -> list[dict]:
    """将 CrewAI 工具转换为 OpenAI function calling 格式"""
    return [tool.to_openai_tool() for tool in tools]

def build_text_tool_calling_fallback_message(tools: list[BaseTool]) -> str:
    """构建文本格式的工具描述（用于不支持 function calling 的 LLM）"""
    descriptions = [f"{tool.name}: {tool.description}" for tool in tools]
    return "可用工具:\n" + "\n".join(descriptions)
```

### 4.5 实现步骤

```
Step 1: 定义 BaseTool 基类（name, description, _run, args_schema）
Step 2: 实现自动 schema 推断（从 _run 方法签名提取参数类型）
Step 3: 实现 CrewStructuredTool（包装任意函数）
Step 4: 实现 Native/Text 双模式适配
Step 5: 实现工具缓存（CacheHandler）
```

---

## 5. 第四阶段：事件总线 — 系统的神经中枢

### 5.1 设计目标

一个**单例事件总线**，让所有模块通过事件通信，不直接耦合。支持：
- 同步/异步事件处理
- 事件依赖图（某些事件必须在其他事件之后处理）
- 流式事件
- 事件范围（Scope）管理

### 5.2 用户示例

```python
from crewai.events.event_bus import crewai_event_bus
from crewai.events.types.agent_events import AgentExecutionStartedEvent

# 发送事件
crewai_event_bus.emit(
    agent,
    event=AgentExecutionStartedEvent(
        agent=agent,
        tools=agent.tools,
        task_prompt="...",
    ),
)

# 监听事件
from crewai.events.event_listener import EventListener

@EventListener(AgentExecutionStartedEvent)
def on_execution_start(event: AgentExecutionStartedEvent):
    print(f"Agent {event.agent.role} 开始执行任务")
```

### 5.3 源码架构

**核心类**：

```
CrewAIEventsBus (单例)  ← 源码位置：lib/crewai/src/crewai/events/event_bus.py#L95
  ├── emit()        ← 发射事件
  ├── aemit()       ← 异步发射
  ├── on()          ← 注册处理器
  ├── off()         ← 移除处理器
  └── _enter_runtime_scope() / _exit_runtime_scope()  ← 运行时范围管理

BaseEvent (Pydantic BaseModel)  ← 源码位置：lib/crewai/src/crewai/events/base_events.py#L66
  ├── event_id: str  ← 唯一事件ID
  ├── parent_id: str | None  ← 父事件ID（构建事件树）
  └── timestamp: datetime

事件类型（按模块分类）：
  ├── agent_events.py    ← AgentExecutionStarted/Completed/Error
  ├── task_events.py     ← TaskStarted/Completed/Failed
  ├── crew_events.py     ← CrewKickoffStarted/Completed/Failed
  ├── llm_events.py      ← LLMCallStarted/Completed/StreamChunk
  ├── tool_usage_events.py ← ToolUsageStarted/Finished/Error
  ├── memory_events.py   ← MemoryRetrievalStarted/Completed
  ├── knowledge_events.py ← KnowledgeQueryStarted/Completed
  └── flow_events.py     ← FlowStarted/Finished, MethodExecutionStarted/Finished
```

**关键设计：事件依赖图**

源码位置：[lib/crewai/src/crewai/events/handler_graph.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/events/handler_graph.py)

```python
def build_execution_plan(handlers: dict) -> ExecutionPlan:
    """构建事件处理器的执行计划（拓扑排序）
    
    某些处理器依赖其他处理器先执行。
    例如：TraceBatchManager 需要在 ConsoleFormatter 之前执行。
    """
    # 使用有向图 + 拓扑排序确定执行顺序
    pass
```

### 5.4 实现步骤

```
Step 1: 定义 BaseEvent 基类（event_id, parent_id, timestamp）
Step 2: 实现 CrewAIEventsBus 单例（emit, on, off）
Step 3: 实现事件类型定义（按模块分类）
Step 4: 实现 EventListener 装饰器（声明式注册）
Step 5: 实现事件依赖图（handler_graph.py）
Step 6: 实现事件范围管理（event_context.py）
```

---

## 6. 第五阶段：Prompt 管理 — Agent 的大脑语言

### 6.1 设计目标

- 模板化 Prompt 构建（role + goal + backstory + tools + task → 完整 Prompt）
- 支持 i18n 国际化
- 支持自定义模板

### 6.2 用户示例

```python
from crewai.utilities.prompts import Prompts

prompts = Prompts(
    i18n="en",
    tools=[search_tool, calculator_tool],
)

# 构建系统 Prompt
system_prompt = prompts.system_prompt(agent)
# 构建任务 Prompt
task_prompt = prompts.task_prompt(agent, task, context)
```

### 6.3 源码架构

```
Prompts 类  ← 源码位置：lib/crewai/src/crewai/utilities/prompts.py
  ├── system_prompt()     ← 构建系统 Prompt
  │     └── "You are {role}. {backstory}. Your goal: {goal}."
  ├── task_prompt()       ← 构建任务 Prompt
  │     └── "Task: {description}. Expected output: {expected_output}."
  ├── tool_prompt()       ← 构建工具描述 Prompt
  │     └── "Available tools: {tools_description}"
  └── i18n                ← 多语言模板

i18n 模板  ← 源码位置：lib/crewai/src/crewai/translations/en.json
  tools: "You have access to the following tools:\n{tools}\n"
  memory: "Relevant memories:\n{memory}\n"
  ...
```

### 6.4 Prompt 构建流程

```
Agent.role + Agent.goal + Agent.backstory
  │
  ▼
system_prompt = f"You are {role}. {backstory}. Your goal: {goal}."
  │
  ├── + tools_prompt = "Available tools: {tools_json}"
  └── + task_prompt = "Task: {description}. Expected: {expected_output}."
  │
  ▼
完整 messages = [
  {"role": "system", "content": system_prompt},
  {"role": "user", "content": task_prompt + context + memory + knowledge},
]
```

### 6.5 实现步骤

```
Step 1: 定义 Prompt 模板常量
Step 2: 实现 Prompts 类（模板渲染）
Step 3: 实现 i18n 国际化支持
Step 4: 实现工具描述生成（render_text_description_and_args）
```

---

## 7. 第六阶段：核心 Agent 类 — 智能体本体

### 7.1 设计目标

Agent 是框架的核心实体，封装了：
- 角色定义（role, goal, backstory）
- LLM 配置
- 工具列表
- 执行器（AgentExecutor）
- 记忆、知识、Hook 等扩展能力

### 7.2 用户示例

```python
from crewai import Agent

researcher = Agent(
    role="研究员",
    goal="深入调研指定主题",
    backstory="你是一位经验丰富的研究员，擅长信息搜集和分析",
    llm="gpt-4o",
    tools=[search_tool, read_file_tool],
    verbose=True,
    allow_delegation=True,
)
```

### 7.3 源码架构

**Agent 类继承链**：

```
BaseAgent (Pydantic BaseModel)  ← 源码位置：lib/crewai/src/crewai/agents/agent_builder/base_agent.py#L200
  ├── role, goal, backstory
  ├── llm, tools, verbose
  ├── max_iter, max_rpm
  └── allow_delegation

Agent(BaseAgent)  ← 源码位置：lib/crewai/src/crewai/agent/core.py#L171
  ├── + execute_task()       ← Crew 调用的入口
  ├── + kickoff()            ← 独立执行入口（无需 Crew）
  ├── + planning_config      ← 计划配置
  ├── + guardrail            ← 输出校验
  ├── + knowledge, skills    ← 知识/技能
  ├── + a2a                  ← A2A 协议
  ├── + checkpoint           ← 检查点
  └── + agent_executor       ← 执行器

LiteAgent (BaseAgent)  ← 源码位置：lib/crewai/src/crewai/lite_agent.py#L187
  ├── + kickoff()            ← 简化版独立执行
  └── 不依赖 Crew
```

**Agent.execute_task() 完整流程**（源码位置：[lib/crewai/src/crewai/agent/core.py#L760-L820](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/agent/core.py#L760-L820)）：

```python
def execute_task(self, task: Task, context: str | None = None, tools: list[BaseTool] | None = None) -> Any:
    # 1. 准备阶段
    task_prompt = self._prepare_task_execution(task, context)
    #    ├── _inject_date_to_task()    ← 注入当前日期
    #    ├── task.prompt()             ← 构建任务提示
    #    ├── build_task_prompt_with_schema() ← 添加结构化输出 schema
    #    ├── format_task_with_context() ← 添加上下文
    #    └── _retrieve_memory_context() ← 检索记忆

    # 2. 知识检索
    knowledge_config = get_knowledge_config(self)
    task_prompt = handle_knowledge_retrieval(self, task, task_prompt, knowledge_config, ...)

    # 3. 最终化 Prompt
    task_prompt = self._finalize_task_prompt(task_prompt, tools, task)
    #    ├── prepare_tools()           ← 准备工具
    #    └── apply_training_data()     ← 应用训练数据

    # 4. 发射事件
    crewai_event_bus.emit(self, event=AgentExecutionStartedEvent(...))

    # 5. 执行（带超时控制）
    if self.max_execution_time is not None:
        result = self._execute_with_timeout(task_prompt, task, self.max_execution_time)
    else:
        result = self._execute_without_timeout(task_prompt, task)
    # 核心：agent_executor.invoke(task_prompt)

    # 6. 最终化
    result = self._finalize_task_execution(task, result)
    #    ├── process_tool_results()    ← 处理工具结果
    #    ├── AgentExecutionCompletedEvent
    #    └── save_last_messages()      ← 保存最后消息
    return result
```

### 7.4 Agent.kickoff() - 独立执行

源码位置：[lib/crewai/src/crewai/agent/core.py#L1542-L1621](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/agent/core.py#L1542-L1621)

```python
def kickoff(self, messages, response_format=None, input_files=None, from_checkpoint=None):
    """Agent 独立执行，不需要 Crew"""
    # 1. 检查点恢复
    restored = apply_checkpoint(self, from_checkpoint)
    if restored is not None:
        return restored.kickoff(...)

    # 2. 检测事件循环（Flow 内自动返回 coroutine）
    if is_inside_event_loop():
        return self.kickoff_async(...)

    # 3. 准备阶段
    executor, inputs, agent_info, parsed_tools = self._prepare_kickoff(...)

    # 4. 执行
    output = self._execute_and_build_output(executor, inputs, ...)

    # 5. 最终化（Guardrail + Memory + Event）
    return self._finalize_kickoff(output, executor, ...)
```

### 7.5 实现步骤

```
Step 1: 定义 BaseAgent 基类（role, goal, backstory, llm, tools）
Step 2: 实现 Agent 类继承 BaseAgent
Step 3: 实现 execute_task() 方法（Crew 调用入口）
Step 4: 实现 kickoff() 方法（独立执行入口）
Step 5: 实现 _prepare_task_execution() 和 _finalize_task_execution()
Step 6: 实现错误处理和重试逻辑
```

---

## 8. 第七阶段：Task 任务定义 — 工作单元

### 8.1 设计目标

Task 是 Agent 执行的工作单元，包含：
- 任务描述和期望输出
- 绑定的 Agent
- 上下文依赖（其他 Task 的输出）
- 结构化输出（Pydantic 模型）
- Guardrail 校验
- 条件执行

### 8.2 用户示例

```python
from crewai import Task

research_task = Task(
    description="调研 {topic} 的最新进展",
    expected_output="一份详细的调研报告，包含关键发现和引用来源",
    agent=researcher,
    context=[previous_task],  # 依赖前一个 Task 的输出
    output_pydantic=ResearchReport,  # 结构化输出
    guardrail=check_quality,  # 质量校验
)
```

### 8.3 源码架构

**Task 类** 源码位置：[lib/crewai/src/crewai/task.py#L114](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/task.py#L114)

```python
class Task(BaseModel):
    name: str | None                    # 任务名
    description: str                    # 任务描述
    expected_output: str                # 期望输出
    agent: BaseAgent | None             # 执行 Agent
    context: list[Task] | None          # 依赖的 Task 列表
    async_execution: bool               # 是否异步执行
    output_json: type[BaseModel] | None # JSON 结构化输出
    output_pydantic: type[BaseModel] | None  # Pydantic 结构化输出
    response_model: type[BaseModel] | None   # 原生结构化输出
    output_file: str | None             # 输出文件路径
    tools: list[BaseTool] | None        # 任务专属工具
    guardrail: GuardrailType | None     # 输出校验
    guardrails: GuardrailsType | None   # 多个校验
    human_input: bool                   # 是否需要人工输入
    callback: Any                       # 完成回调
    config: dict | None                 # 额外配置
    markdown: str | None                # Markdown 格式描述
    allow_crewai_trigger_context: bool | None  # 触发器上下文注入
```

**ConditionalTask** 源码位置：[lib/crewai/src/crewai/tasks/conditional_task.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/tasks/conditional_task.py)

```python
class ConditionalTask(Task):
    """条件任务：满足 condition 时才执行"""
    condition: Callable[[TaskOutput], bool]
```

**TaskOutput** 源码位置：[lib/crewai/src/crewai/tasks/task_output.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/tasks/task_output.py)

```python
class TaskOutput(BaseModel):
    description: str     # 任务描述
    summary: str         # 执行摘要
    raw: str             # 原始输出
    pydantic: BaseModel | None  # 结构化输出
    json_dict: dict | None      # JSON 输出
    agent: str           # 执行的 Agent
    output_format: OutputFormat  # 输出格式
```

### 8.4 Task.prompt() 方法

```python
def prompt(self) -> str:
    """生成任务的 Prompt 文本"""
    prompt = self.description
    if self.expected_output:
        prompt += f"\n\nExpected Output: {self.expected_output}"
    return prompt
```

### 8.5 实现步骤

```
Step 1: 定义 Task 类（Pydantic BaseModel）
Step 2: 实现 prompt() 方法
Step 3: 实现 ConditionalTask 子类
Step 4: 实现 TaskOutput 类
Step 5: 实现上下文依赖解析（Task 间的 context 传递）
Step 6: 实现 Guardrail 校验集成
```

---

## 9. 第八阶段：Agent 执行器 — 思考-行动循环

### 9.1 设计目标

AgentExecutor 是 Agent 的"大脑"——实现 **ReAct (Reasoning + Acting) 循环**，同时支持 **Plan-and-Execute** 模式：

```
┌─────────────────────────────────────┐
│         AgentExecutor (Flow)         │
│                                      │
│  ┌──────────────────────────────┐   │
│  │  Plan Phase (可选)            │   │
│  │  生成 TodoList，规划步骤       │   │
│  └──────────┬───────────────────┘   │
│             ▼                        │
│  ┌──────────────────────────────┐   │
│  │  ReAct Loop                   │   │
│  │                               │   │
│  │  ┌─ LLM.call(messages) ───┐  │   │
│  │  │  返回 Thought + Action  │  │   │
│  │  └────────┬───────────────┘  │   │
│  │           ▼                   │   │
│  │  ┌─ parse(response) ──────┐  │   │
│  │  │  AgentAction 或 AgentFinish│   │
│  │  └────────┬───────────────┘  │   │
│  │           ▼                   │   │
│  │  ┌─ Tool._run() ──────────┐  │   │
│  │  │  执行工具，返回结果     │  │   │
│  │  └────────┬───────────────┘  │   │
│  │           ▼                   │   │
│  │  ┌─ 追加到 messages ──────┐  │   │
│  │  │  循环直到 AgentFinish  │  │   │
│  │  └────────────────────────┘  │   │
│  └──────────────────────────────┘   │
└─────────────────────────────────────┘
```

### 9.2 用户示例

```python
from crewai.experimental.agent_executor import AgentExecutor

executor = AgentExecutor(
    llm=llm,
    tools=[search_tool, calculator_tool],
    max_iter=15,
    prompt=system_prompt,
)
result = executor.invoke({"messages": [{"role": "user", "content": "research AI"}]})
```

### 9.3 源码架构

**AgentExecutor 继承链**：

```
Flow[AgentExecutorState]  ← Flow 工作流引擎（提供声明式编排能力）
  └── BaseAgentExecutor   ← 基础执行器（提供记忆方法）

AgentExecutor  ← 源码位置：lib/crewai/src/crewai/experimental/agent_executor.py#L164
  ├── executor_type: "experimental"
  ├── llm: BaseLLM
  ├── tools: list[CrewStructuredTool]
  ├── max_iter: int
  ├── prompt: SystemPromptResult
  └── tools_handler: ToolsHandler
```

**AgentExecutorState** 源码位置：[lib/crewai/src/crewai/experimental/agent_executor.py#L126-L161](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/experimental/agent_executor.py#L126-L161)

```python
class AgentExecutorState(BaseModel):
    """执行器状态（持久化到 checkpoint）"""
    id: str
    messages: list[LLMMessage]  # 对话历史
    iterations: int             # 当前迭代次数
    current_answer: AgentAction | AgentFinish | None  # 当前解析结果
    is_finished: bool           # 是否完成
    use_native_tools: bool      # 是否使用原生 function calling
    pending_tool_calls: list    # 待执行的工具调用
    plan: str | None            # 执行计划
    plan_ready: bool            # 计划是否就绪
    todos: TodoList             # 待办事项列表
    replan_count: int           # 重新规划次数
    observations: dict          # 步骤观察
    execution_log: list         # 审计日志
```

**关键设计：Flow 化执行器**

AgentExecutor 继承自 `Flow[AgentExecutorState]`，意味着 ReAct 循环的每一步都是 Flow 的一个方法，用 `@start` / `@listen` 装饰器声明：

```python
@start()
def plan_or_react(self):
    """规划阶段，决定是否生成 TodoList"""
    ...

@listen(plan_or_react)
def call_llm(self):
    """调用 LLM"""
    ...

@listen(call_llm)
def parse_response(self):
    """解析 LLM 响应"""
    ...

@listen(parse_response)
def execute_tool_or_finish(self):
    """执行工具或结束"""
    ...
```

### 9.4 ReAct 循环核心逻辑

源码位置：[lib/crewai/src/crewai/experimental/agent_executor.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/experimental/agent_executor.py)

```python
# 简化版 ReAct 循环
def _invoke(self, messages):
    while not state.is_finished and state.iterations < self.max_iter:
        # 1. 调用 LLM
        response = self.llm.call(messages, tools=self.tools)
        
        # 2. 解析响应
        parsed = parse(response)
        
        if isinstance(parsed, AgentFinish):
            # 3a. 完成，返回结果
            return parsed.return_values["output"]
        
        elif isinstance(parsed, AgentAction):
            # 3b. 执行工具
            tool_result = self.tools_handler.execute(parsed.tool, parsed.tool_input)
            # 追加到 messages
            messages.append({"role": "tool", "content": tool_result})
        
        state.iterations += 1
```

### 9.5 实现步骤

```
Step 1: 定义 AgentExecutorState（Pydantic model）
Step 2: 实现 BaseAgentExecutor（记忆方法）
Step 3: 实现 AgentExecutor（继承 Flow + BaseAgentExecutor）
Step 4: 实现 ReAct 循环（@start/@listen 声明式编排）
Step 5: 实现 Plan-and-Execute 模式（TodoList 管理）
Step 6: 实现 Native/Text 双模式工具调用
Step 7: 实现 Hook 集成（before/after LLM call, before/after Tool call）
```

---

## 10. 第九阶段：Crew 调度引擎 — 多Agent编排

### 10.1 设计目标

Crew 是顶层编排器，负责：
- 管理多个 Agent 和 Task
- 按指定流程执行任务（Sequential / Hierarchical）
- 管理共享资源（Memory、Cache、Knowledge）
- 支持 Checkpoint、Streaming、Tracing

### 10.2 用户示例

```python
from crewai import Crew, Process

crew = Crew(
    agents=[researcher, writer],
    tasks=[research_task, writing_task],
    process=Process.sequential,  # 顺序执行
    verbose=True,
    memory=True,
    planning=True,
)

result = crew.kickoff(inputs={"topic": "AI Safety"})
print(result.raw)
```

### 10.3 源码架构

**Crew 类** 源码位置：[lib/crewai/src/crewai/crew.py#L159](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/crew.py#L159)

```python
class Crew(FlowTrackable, BaseModel):
    # 核心配置
    name: str
    agents: list[BaseAgent]
    tasks: list[Task]
    process: Process  # sequential / hierarchical
    
    # LLM 配置
    manager_llm: str | BaseLLM | None  # Hierarchical 模式的 Manager LLM
    manager_agent: BaseAgent | None    # 自定义 Manager Agent
    function_calling_llm: ...          # 全局 function calling LLM
    
    # 扩展能力
    memory: bool | Memory | MemoryScope | MemorySlice
    knowledge: Knowledge | None
    knowledge_sources: list[BaseKnowledgeSource] | None
    embedder: EmbedderConfig | None
    
    # 执行控制
    cache: bool
    max_rpm: int | None
    stream: bool
    planning: bool
    
    # 安全与追踪
    security_config: SecurityConfig
    checkpoint: CheckpointConfig | bool | None
    tracing: bool | None
    
    # 回调
    before_kickoff_callbacks: list
    after_kickoff_callbacks: list
    step_callback: ...
    task_callback: ...
```

**Crew.kickoff()** 源码位置：[lib/crewai/src/crewai/crew.py#L978-L1068](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/crew.py#L978-L1068)

```python
def kickoff(self, inputs=None, input_files=None, from_checkpoint=None):
    # 1. 检查点恢复
    restored = apply_checkpoint(self, from_checkpoint)
    if restored is not None:
        return restored.kickoff(...)

    # 2. Streaming 模式
    if self.stream:
        # 启动后台线程执行，通过 StreamingContext 输出
        ...

    # 3. OpenTelemetry 上下文
    baggage_ctx = baggage.set_baggage("crew_context", CrewContext(...))
    token = attach(baggage_ctx)

    # 4. 运行时范围
    runtime_scope = crewai_event_bus._enter_runtime_scope()

    try:
        # 5. 准备
        inputs = prepare_kickoff(self, inputs, input_files)

        # 6. 按流程执行
        if self.process == Process.sequential:
            result = self._run_sequential_process()
        elif self.process == Process.hierarchical:
            result = self._run_hierarchical_process()

        # 7. 后处理回调
        for after_callback in self.after_kickoff_callbacks:
            result = after_callback(result)

        # 8. 最终化
        result = self._post_kickoff(result)
        self.usage_metrics = self.calculate_usage_metrics()
        return result

    except Exception as e:
        crewai_event_bus.emit(self, CrewKickoffFailedEvent(...))
        raise
    finally:
        self._drain_memory_writes()
        clear_files(self.id)
        detach(token)
        crewai_event_bus._exit_runtime_scope(runtime_scope)
```

### 10.4 Sequential 执行流程

```python
def _run_sequential_process(self):
    """顺序执行所有任务"""
    task_outputs = []
    
    for task in self.tasks:
        # 1. 跳过条件任务（如果条件不满足）
        if isinstance(task, ConditionalTask):
            if not task.condition(task_outputs[-1] if task_outputs else None):
                continue
        
        # 2. 构建任务上下文
        context = self._build_task_context(task, task_outputs)
        
        # 3. 执行任务
        agent = task.agent or self._pick_agent(task)
        output = agent.execute_task(task, context=context)
        
        # 4. 保存输出
        task_output = TaskOutput(
            description=task.description,
            raw=output if isinstance(output, str) else str(output),
            agent=agent.role,
        )
        task_outputs.append(task_output)
        
        # 5. 保存到记忆
        if self.memory:
            self._memory.save(task_output)
    
    return CrewOutput(tasks_output=task_outputs, ...)
```

### 10.5 Hierarchical 执行流程

```python
def _run_hierarchical_process(self):
    """分层执行：Manager Agent 分配任务给其他 Agent"""
    manager = self.manager_agent or self._create_manager_agent()
    
    for task in self.tasks:
        # Manager 决定哪个 Agent 执行
        # 通过 delegate_work tool 分配
        output = manager.execute_task(task)
        # 或在内部通过 delegation 分发
        task_outputs.append(output)
    
    return CrewOutput(tasks_output=task_outputs, ...)
```

### 10.6 实现步骤

```
Step 1: 定义 Process 枚举（sequential, hierarchical）
Step 2: 实现 Crew 类（Pydantic BaseModel + FlowTrackable）
Step 3: 实现 kickoff() 方法（入口）
Step 4: 实现 _run_sequential_process()（顺序执行）
Step 5: 实现 _run_hierarchical_process()（分层执行）
Step 6: 实现准备流程（prepare_kickoff, prepare_task_execution）
Step 7: 实现 CrewOutput 聚合（crew_output.py）
Step 8: 实现 Streaming 支持
Step 9: 实现 Checkpoint 集成
```

---

## 11. 第十阶段：记忆系统 — 持久化上下文

### 11.1 设计目标

让 Agent 和 Crew 记住历史执行上下文，包括：
- **短期记忆**（Short-term）：当前对话上下文
- **长期记忆**（Long-term）：跨会话持久化
- **实体记忆**（Entity）：实体关系
- **用户记忆**（User）：用户偏好

### 11.2 用户示例

```python
from crewai import Crew

crew = Crew(
    agents=[agent],
    tasks=[task],
    memory=True,  # 启用默认记忆
)
```

### 11.3 源码架构

```
Memory 类  ← 源码位置：lib/crewai/src/crewai/memory/unified_memory.py#L76
  ├── save()      ← 保存记忆
  ├── recall()    ← 检索记忆
  ├── delete()    ← 删除记忆
  └── reset()     ← 重置记忆

MemoryScope  ← 源码位置：lib/crewai/src/crewai/memory/memory_scope.py
  ├── 控制记忆范围（crew 级 vs agent 级）
  └── 支持读写权限控制

MemorySlice  ← 组合同一 MemoryScope 下的多个 Memory
  ├── 支持自定义存储后端（LanceDB, Qdrant）
  └── 支持向量化存储

存储后端：
  ├── LanceDBStorage  ← 默认本地存储
  └── QdrantEdgeStorage ← 边缘部署存储
```

### 11.4 记忆存储流程

```python
# 保存记忆
memory.save(
    task_output=task_output,
    kind="short_term",  # short_term / long_term / entity / user
    score=0.8,
)

# 检索记忆
matches = memory.recall(
    query="AI safety research",
    limit=5,
    kind="long_term",
)
```

### 11.5 实现步骤

```
Step 1: 定义 Memory 基类
Step 2: 实现 UnifiedMemory（统一记忆接口）
Step 3: 实现 MemoryScope（范围控制）
Step 4: 实现 LanceDB 存储后端
Step 5: 实现向量化存储（embedding → 向量 → 存储）
Step 6: 实现相似度检索（recall）
```

---

## 12. 第十一阶段：知识检索 RAG — 外部知识注入

### 12.1 设计目标

让 Agent 在执行任务前从外部知识源检索相关信息，注入到 Prompt 中。

### 12.2 用户示例

```python
from crewai import Agent, Knowledge
from crewai.knowledge.source import PDFKnowledgeSource, StringKnowledgeSource

knowledge = Knowledge(
    sources=[
        PDFKnowledgeSource(file_path="docs/research.pdf"),
        StringKnowledgeSource(content="AI Safety best practices..."),
    ],
    embedder={"provider": "openai", "model": "text-embedding-3-small"},
)

agent = Agent(
    role="研究员",
    knowledge=knowledge,
    ...
)
```

### 12.3 源码架构

```
Knowledge 类  ← 源码位置：lib/crewai/src/crewai/knowledge/knowledge.py
  ├── sources: list[BaseKnowledgeSource]
  ├── embedder: EmbedderConfig
  ├── collection_name: str
  ├── add_sources()  ← 加载所有知识源
  └── query()        ← 检索相关知识

RAG 流水线：
  加载 → 分块 → 向量化 → 存储 → 检索

知识源类型：
  ├── PDFKnowledgeSource
  ├── CSVKnowledgeSource
  ├── ExcelKnowledgeSource
  ├── JSONKnowledgeSource
  ├── StringKnowledgeSource
  ├── TextFileKnowledgeSource
  └── CrewDoclingSource (高级文档解析)

向量存储：
  ├── ChromaDB  ← 默认
  └── Qdrant
```

### 12.4 RAG 检索流程

```python
def handle_knowledge_retrieval(agent, task, task_prompt, config, ...):
    # 1. 生成搜索查询
    query = task.description  # 或自定义 knowledge_search_query
    
    # 2. 向量检索
    results = knowledge.query(query, limit=5)
    
    # 3. 注入到 Prompt
    if results:
        knowledge_context = "相关知识:\n" + "\n".join(r.content for r in results)
        task_prompt += f"\n\n{knowledge_context}"
    
    return task_prompt
```

### 12.5 实现步骤

```
Step 1: 定义 Knowledge 类和 BaseKnowledgeSource
Step 2: 实现 PDF/CSV/JSON 等知识源加载器
Step 3: 实现文本分块（Chunking）
Step 4: 实现 Embedding 工厂（支持多种 embedding 提供商）
Step 5: 实现 ChromaDB/Qdrant 向量存储
Step 6: 实现 query() 检索方法
Step 7: 集成到 Agent.execute_task() 流程
```

---

## 13. 第十二阶段：Flow 工作流 — 声明式编排

### 13.1 设计目标

Flow 提供比 Crew 更灵活的编排方式，支持：
- **声明式方法编排**：用 `@start` / `@listen` / `@router` 装饰器定义流程
- **状态管理**：Pydantic 模型驱动的状态
- **条件分支**：`or_` / `and_` 条件
- **人工反馈**：`@human_feedback` 暂停等待人工输入
- **持久化**：SQLite 持久化

### 13.2 用户示例

```python
from crewai.flow.flow import Flow, start, listen, router
from pydantic import BaseModel

class MyState(BaseModel):
    query: str = ""
    results: list = []
    approved: bool = False

class ResearchFlow(Flow[MyState]):
    @start()
    def search(self):
        self.state.query = "AI Safety"
        self.state.results = ["result1", "result2"]

    @listen(search)
    def analyze(self):
        self.state.approved = len(self.state.results) > 0

    @router(analyze)
    def route(self):
        if self.state.approved:
            return "SUCCESS"
        return "RETRY"

flow = ResearchFlow()
flow.kickoff()
```

### 13.3 源码架构

```
Flow 模块拆分：
  ├── flow.py          ← 公开 API 重导出
  ├── dsl/             ← 装饰器定义（@start, @listen, @router, or_, and_）
  ├── flow_definition.py ← 可序列化的 Flow 定义
  ├── runtime/         ← Flow 执行引擎
  │     ├── __init__.py    ← RuntimeFlow, FlowMeta, FlowState
  │     ├── _actions.py    ← 执行动作
  │     └── _outputs.py    ← 输出处理
  ├── persistence/     ← 持久化
  │     └── sqlite.py     ← SQLiteFlowPersistence
  ├── visualization/   ← 可视化
  ├── expressions.py   ← 表达式引擎
  └── conversation.py  ← 对话式编排
```

**FlowMeta 元类** 源码位置：[lib/crewai/src/crewai/flow/runtime/__init__.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/flow/runtime/__init__.py)

```python
class FlowMeta(type):
    """元类：收集 @start/@listen/@router 装饰的方法，构建执行图"""
    def __new__(cls, name, bases, namespace):
        # 1. 收集所有 Flow 方法
        # 2. 构建方法依赖图
        # 3. 验证图的完整性
        pass
```

### 13.4 执行流程

```
Flow.kickoff()
  │
  ├── FlowMeta 构建执行图（启动时）
  │     └── 拓扑排序确定方法执行顺序
  │
  ├── RuntimeFlow._execute_flow()
  │     ├── 执行所有 @start() 方法
  │     ├── 根据 @listen() 依赖依次执行
  │     ├── 根据 @router() 条件分支
  │     └── 发射 FlowStartedEvent / FlowFinishedEvent
  │
  └── 返回最终状态
```

### 13.5 实现步骤

```
Step 1: 定义 FlowMeta 元类（方法收集 + 图构建）
Step 2: 实现 @start / @listen / @router 装饰器
Step 3: 实现 RuntimeFlow（执行引擎）
Step 4: 实现 FlowState + FlowDefinition（可序列化）
Step 5: 实现条件表达式（or_ / and_）
Step 6: 实现 SQLite 持久化
Step 7: 实现可视化（HTML 流程图）
Step 8: 实现人工反馈（human_feedback）
```

---

## 14. 第十三阶段：高级特性 — Hook、State、MCP、A2A

### 14.1 Hook 钩子系统

**目标**：在 Agent 执行的关键节点插入自定义逻辑。

**源码位置**：[lib/crewai/src/crewai/hooks/](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/hooks/)

```python
# 注册 Hook
from crewai.hooks.decorators import before_llm_call, after_llm_call, before_tool_call, after_tool_call

@before_llm_call
def modify_messages(messages: list, **kwargs):
    """在 LLM 调用前修改 messages"""
    messages.append({"role": "system", "content": "Be concise."})
    return messages

@after_tool_call
def validate_tool_result(result: str, **kwargs):
    """在工具调用后校验结果"""
    if len(result) > 10000:
        return result[:10000] + "..."
    return result
```

**Hook 执行时机**：

```
AgentExecutor ReAct Loop:
  │
  ├── before_llm_call hooks  ← 修改 messages
  ├── LLM.call()
  ├── after_llm_call hooks   ← 修改 response
  ├── before_tool_call hooks ← 修改 tool_args
  ├── Tool._run()
  └── after_tool_call hooks  ← 修改 tool_result
```

### 14.2 State & Checkpoint

**目标**：支持 Crew/Agent/Flow 的状态持久化和恢复。

**源码位置**：[lib/crewai/src/crewai/state/](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/state/)

```python
from crewai.state.checkpoint_config import CheckpointConfig

# 启用 checkpoint
crew = Crew(
    agents=[agent],
    tasks=[task],
    checkpoint=CheckpointConfig(
        save_every=1,  # 每个 task 完成后保存
        save_path="./checkpoints",
    ),
)

# 从 checkpoint 恢复
restored_crew = Crew.from_checkpoint(
    CheckpointConfig(restore_from="./checkpoints/crew_checkpoint.json")
)
restored_crew.kickoff()  # 从上次中断处继续
```

**Checkpoint 结构**：

```
State 层次：
  RuntimeState
    ├── Crew (序列化)
    │     ├── Agents (序列化)
    │     ├── Tasks (序列化)
    │     └── TaskOutputs
    └── Event Records (事件流)

存储后端：
  ├── JSONProvider   ← JSON 文件
  └── SQLiteProvider ← SQLite 数据库
```

### 14.3 MCP 协议

**目标**：支持 Model Context Protocol，让 Agent 接入外部 MCP 工具服务器。

**源码位置**：[lib/crewai/src/crewai/mcp/](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/mcp/)

```python
from crewai.mcp.config import MCPServerConfig

agent = Agent(
    role="研究员",
    mcp_servers=[
        MCPServerConfig(
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem", "/data"],
        ),
    ],
)
```

**MCP 传输层**：

```
MCP Transport:
  ├── StdioTransport   ← 标准输入输出
  ├── SSETransport     ← Server-Sent Events
  └── HTTPTransport    ← HTTP 请求

MCPClient:
  ├── 连接 MCP Server
  ├── 获取工具列表
  └── 执行工具调用
```

### 14.4 A2A 协议

**目标**：Agent-to-Agent 通信协议，支持跨进程/跨网络的 Agent 委托。

**源码位置**：[lib/crewai/src/crewai/a2a/](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/a2a/)

```python
from crewai.a2a.config import A2AConfig, A2AServerConfig, A2AClientConfig

agent = Agent(
    role="Coordinator",
    a2a=[
        A2AServerConfig(host="0.0.0.0", port=8000),
        A2AClientConfig(remote_agent_url="http://other-agent:8001"),
    ],
)
```

**A2A 架构**：

```
A2A Wrapper (lib/crewai/src/crewai/a2a/wrapper.py):
  └── wrap_agent_with_a2a_instance()
        ├── 装饰 Agent.execute_task()
        ├── 装饰 Agent.aexecute_task()
        └── 装饰 Agent.kickoff()
              │
              ├── 本地 Agent → 直接执行
              └── 远程 Agent → 通过 A2A Client 委托

A2A Server (lib/crewai/src/crewai/a2a/):
  ├── 暴露 Agent Card（能力描述）
  ├── 接收委托请求
  └── 返回执行结果

A2A Client (lib/crewai/src/crewai/a2a/):
  ├── 发现远程 Agent
  ├── 发送委托请求
  └── 接收执行结果
```

### 14.5 实现步骤

```
Hook 系统：
  Step 1: 定义 Hook 类型（LLM/Tool/Agent）
  Step 2: 实现装饰器注册机制
  Step 3: 实现 Hook 上下文（HookContext）
  Step 4: 集成到 AgentExecutor

State & Checkpoint：
  Step 1: 定义 RuntimeState 结构
  Step 2: 实现 CheckpointConfig
  Step 3: 实现 JSON/SQLite Provider
  Step 4: 实现 from_checkpoint() 恢复

MCP：
  Step 1: 实现 MCP Client（连接 + 工具发现）
  Step 2: 实现 Transport 层（Stdio/SSE/HTTP）
  Step 3: 实现 MCP Tool Resolver

A2A：
  Step 1: 定义 A2A Config（Server/Client）
  Step 2: 实现 A2A Server（Agent Card + 请求处理）
  Step 3: 实现 A2A Client（远程调用）
  Step 4: 实现 Agent Wrapper（透明代理）
```

---

## 15. 第十四阶段：CLI 与 Project 脚手架

### 15.1 设计目标

提供 `crewai` CLI 命令，让用户快速创建和管理项目。

### 15.2 用户示例

```bash
# 创建新项目
crewai create crew my-project

# 安装依赖
crewai install

# 运行
crewai run
```

### 15.3 Project 声明式定义

**源码位置**：[lib/crewai/src/crewai/project/](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/project/)

```python
# crew_definition.py - 声明式 Crew 定义
from crewai.project import CrewBase, agent, task, crew

@CrewBase
class ResearchCrew:
    """调查研究 Crew"""

    @agent
    def researcher(self) -> Agent:
        return Agent(role="研究员", ...)

    @agent
    def writer(self) -> Agent:
        return Agent(role="写手", ...)

    @task
    def research_task(self) -> Task:
        return Task(description="调研...", agent=self.researcher())

    @task
    def writing_task(self) -> Task:
        return Task(description="撰写...", agent=self.writer(), context=[self.research_task()])

    @crew
    def crew(self) -> Crew:
        return Crew(agents=self.agents, tasks=self.tasks, ...)
```

**Project 架构**：

```
Project 模块：
  ├── annotations.py      ← @CrewBase, @agent, @task, @crew 装饰器
  ├── crew_base.py        ← CrewBase 元类
  ├── crew_definition.py  ← CrewDefinition（可序列化）
  ├── crew_loader.py      ← Crew 加载器
  ├── json_loader.py      ← JSON 格式加载
  ├── utils.py            ← 工具函数
  └── wrappers.py         ← 装饰器包装
```

### 15.4 实现步骤

```
Step 1: 实现 @CrewBase 装饰器 + 元类
Step 2: 实现 @agent, @task, @crew 收集器
Step 3: 实现 CrewDefinition（可序列化）
Step 4: 实现 CLI 命令（create, install, run）
Step 5: 实现 JSON Project 加载器
```

---

## 16. 附录：完整目录结构

```
lib/crewai/src/crewai/
├── __init__.py              # 包入口
├── crew.py                  # Crew 调度引擎
├── task.py                  # Task 任务定义
├── llm.py                   # LLM 便捷接口
├── lite_agent.py            # LiteAgent（简化版 Agent）
├── process.py               # Process 枚举
├── context.py               # 执行上下文
│
├── agent/                   # Agent 核心
│   ├── core.py              # Agent 类
│   ├── utils.py             # Agent 工具函数
│   └── planning_config.py   # 计划配置
│
├── agents/                  # Agent 基础设施
│   ├── agent_builder/
│   │   ├── base_agent.py           # BaseAgent 基类
│   │   └── base_agent_executor.py  # BaseAgentExecutor 基类
│   ├── cache/
│   │   └── cache_handler.py        # 工具调用缓存
│   ├── parser.py                   # AgentAction/AgentFinish 解析
│   ├── crew_agent_executor.py      # CrewAgentExecutor（已弃用）
│   ├── step_executor.py            # 步骤执行器
│   ├── tools_handler.py            # 工具处理器
│   └── planner_observer.py         # 计划观察者
│
├── llms/                    # LLM 抽象层
│   ├── base_llm.py          # BaseLLM 抽象基类
│   ├── hooks/               # LLM Hook
│   └── providers/           # 各 Provider 实现
│       ├── openai/
│       ├── anthropic/
│       ├── azure/
│       ├── bedrock/
│       ├── gemini/
│       └── openai_compatible/
│
├── tools/                   # 工具系统
│   ├── base_tool.py         # BaseTool 基类
│   ├── structured_tool.py   # CrewStructuredTool
│   ├── tool_usage.py        # 工具使用追踪
│   ├── mcp_native_tool.py   # MCP 原生工具
│   └── agent_tools/         # Agent 内置工具
│
├── events/                  # 事件系统
│   ├── event_bus.py         # CrewAIEventsBus 单例
│   ├── base_events.py       # BaseEvent 基类
│   ├── event_listener.py    # EventListener 装饰器
│   ├── event_context.py     # 事件范围管理
│   ├── handler_graph.py     # 事件依赖图
│   └── types/               # 事件类型定义
│
├── memory/                  # 记忆系统
│   ├── unified_memory.py    # Memory 统一接口
│   ├── memory_scope.py      # MemoryScope
│   └── storage/             # 存储后端
│
├── knowledge/               # 知识系统
│   ├── knowledge.py         # Knowledge 类
│   └── source/              # 知识源
│
├── rag/                     # RAG 基础设施
│   ├── embeddings/          # Embedding 提供者
│   ├── chromadb/            # ChromaDB 存储
│   └── qdrant/              # Qdrant 存储
│
├── flow/                    # Flow 工作流
│   ├── flow.py              # Flow 公开 API
│   ├── dsl/                 # 装饰器（@start/@listen/@router）
│   ├── runtime/             # 执行引擎
│   ├── flow_definition.py   # Flow 定义
│   └── persistence/         # 持久化
│
├── hooks/                   # Hook 钩子
│   ├── llm_hooks.py         # LLM Hook
│   ├── tool_hooks.py        # Tool Hook
│   └── decorators.py        # 装饰器
│
├── state/                   # 状态管理
│   ├── runtime.py           # RuntimeState
│   ├── checkpoint_config.py # CheckpointConfig
│   └── provider/            # 存储 Provider
│
├── mcp/                     # MCP 协议
│   ├── client.py            # MCPClient
│   ├── config.py            # MCPServerConfig
│   └── transports/          # 传输层
│
├── a2a/                     # A2A 协议
│   ├── config.py            # A2AConfig
│   ├── wrapper.py           # Agent Wrapper
│   └── extensions/          # A2A 扩展
│
├── project/                 # Project 脚手架
│   ├── annotations.py       # @CrewBase, @agent, @task
│   ├── crew_base.py         # CrewBase 元类
│   └── crew_definition.py   # CrewDefinition
│
├── tasks/                   # Task 子模块
│   ├── conditional_task.py  # ConditionalTask
│   ├── task_output.py       # TaskOutput
│   ├── llm_guardrail.py     # LLM Guardrail
│   └── output_format.py     # OutputFormat
│
├── crews/                   # Crew 子模块
│   ├── crew_output.py       # CrewOutput
│   └── utils.py             # Crew 工具函数
│
├── skills/                  # 技能系统
├── security/                # 安全
├── utilities/               # 工具函数
├── types/                   # 类型定义
├── cli/                     # CLI
├── auth/                    # 认证
├── telemetry/               # 遥测
└── experimental/            # 实验性功能
    ├── agent_executor.py    # AgentExecutor
    └── evaluation/          # 评估系统
```

---

## 17. 构建顺序总结

按依赖关系，从0到1的构建顺序：

```
第1步: 数据模型层 (Pydantic)
  └→ 第2步: LLM 抽象层 (BaseLLM + Providers)
    └→ 第3步: 工具系统 (BaseTool + CrewStructuredTool)
      └→ 第4步: 事件总线 (CrewAIEventsBus + Event Types)
        └→ 第5步: Prompt 管理 (Prompts + i18n)
          └→ 第6步: Agent 核心 (BaseAgent → Agent)
            └→ 第7步: Task 定义 (Task + TaskOutput)
              └→ 第8步: Agent 执行器 (AgentExecutor + ReAct Loop)
                └→ 第9步: Crew 调度 (Crew + Sequential/Hierarchical)
                  ├→ 第10步: 记忆系统 (Memory + Storage)
                  ├→ 第11步: 知识检索 (Knowledge + RAG)
                  ├→ 第12步: Flow 工作流 (Flow + DSL)
                  └→ 第13步: 高级特性 (Hook, State, MCP, A2A)
```

**核心理念**：每一层都只依赖下一层，不依赖上一层。LLM 不知道 Agent 的存在，Tool 不知道 Task 的存在。EventBus 是唯一的横向通信通道。

---

> 文档生成时间：2026-07-16
> 基于 CrewAI 源码版本：lib/crewai/src/crewai/