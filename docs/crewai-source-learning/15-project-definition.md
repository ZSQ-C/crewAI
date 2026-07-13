# 阶段十五：Project 声明式定义 — 源码深度解析

---

## 1. 模块定位

### 1.1 一句话概括

**Project 声明式定义是 CrewAI 的项目脚手架层，通过「`@CrewBase` 元类 + `@agent`/`@task`/`@tool` 装饰器 + YAML 配置文件 + JSON/JSONC Crew 定义加载」架构，让开发者用声明式方式定义整个 Crew 项目，实现代码与配置分离、组件复用和一键部署。**

### 1.2 在整体架构中的位置

```
┌──────────────────────────────────────────────────────────────────┐
│                    Project 声明式定义架构                        │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  开发体验层 (Decorators)         配置层 (YAML/JSON)               │
│  ┌──────────────────────┐     ┌───────────────────────┐          │
│  │ @CrewBase            │     │ config/agents.yaml    │          │
│  │   class MyCrew:      │────▶│ config/tasks.yaml     │          │
│  │     @agent           │     │ crew.json / crew.jsonc│          │
│  │     def researcher() │     └───────────────────────┘          │
│  │     @task             │                                       │
│  │     def research()   │     加载层 (Loader)                    │
│  │     @tool             │     ┌───────────────────────┐          │
│  │     def search()     │────▶│ CrewLoader.load()     │          │
│  └──────────────────────┘     │ JSONCrewProject       │          │
│                               └───────────┬───────────┘          │
│                                           │                       │
│                               ┌───────────▼───────────┐          │
│                               │ Crew 实例化            │          │
│                               │ Agent + Task + Crew   │          │
│                               └───────────────────────┘          │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

### 1.3 本阶段涉及的核心源码文件

| 文件 | 核心职责 |
|------|----------|
| `project/annotations.py` | 装饰器定义：`@agent`、`@task`、`@tool`、`@before_kickoff`、`@after_kickoff` 等 |
| `project/crew_base.py` | CrewBaseMeta 元类：类创建时扫描、配置加载、方法注入 |
| `project/crew_definition.py` | CrewDefinition：声明式 Crew 定义的数据模型（可序列化） |
| `project/crew_loader.py` | CrewLoader：从 JSON/JSONC 文件加载 Crew 实例 |
| `project/wrappers.py` | 包装器类型：AgentMethod、TaskMethod、ToolMethod、CrewMetadata |
| `project/utils.py` | 工具函数：memoize 等 |
| `project/json_loader.py` | JSON 加载器：解析 crew.json 文件 |

---

## 2. 源码分层拆解

### 2.1 第一层：装饰器（Annotations）

**文件：** `lib/crewai/src/crewai/project/annotations.py`

```python
def agent(meth: Callable[P, R]) -> AgentMethod[P, R]:
    """标记方法为 Agent 工厂。"""
    return AgentMethod(memoize(meth))

def task(meth: Callable[P, TaskResultT]) -> TaskMethod[P, TaskResultT]:
    """标记方法为 Task 工厂。"""
    return TaskMethod(memoize(meth))

def tool(meth: Callable[P, R]) -> ToolMethod[P, R]:
    """标记方法为 Tool 工厂。"""
    return ToolMethod(memoize(meth))

def before_kickoff(meth: Callable[P, R]) -> BeforeKickoffMethod[P, R]:
    """标记方法在 kickoff 前执行。"""
    return BeforeKickoffMethod(meth)

def after_kickoff(meth: Callable[P, R]) -> AfterKickoffMethod[P, R]:
    """标记方法在 kickoff 后执行。"""
    return AfterKickoffMethod(meth)

def llm(meth: Callable[P, R]) -> LLMMethod[P, R]:
    """标记方法为 LLM 提供者。"""
    return LLMMethod(memoize(meth))

def output_json(cls: type[T]) -> OutputJsonClass[T]:
    """标记类为 JSON 输出格式。"""
    return OutputJsonClass(cls)

def output_pydantic(cls: type[T]) -> OutputPydanticClass[T]:
    """标记类为 Pydantic 输出格式。"""
    return OutputPydanticClass(cls)

def callback(meth: Callable[P, R]) -> CallbackMethod[P, R]:
    """标记方法为回调。"""
    return CallbackMethod(memoize(meth))

def cache_handler(meth: Callable[P, R]) -> CacheHandlerMethod[P, R]:
    """标记方法为缓存处理器。"""
    return CacheHandlerMethod(memoize(meth))
```

**大白话：** 每个装饰器返回一个特定类型的包装器（如 `AgentMethod`、`TaskMethod`），这些包装器带有 `is_agent`、`is_task` 等标记属性，元类通过检查这些属性来识别方法。

---

### 2.2 第二层：CrewBaseMeta 元类

**文件：** `lib/crewai/src/crewai/project/crew_base.py`

```python
class CrewBaseMeta(type):
    """Crew 类的元类，注入 crew 功能。"""

    def __new__(mcs, name, bases, namespace, **kwargs):
        """创建 Crew 类时："""
        cls = super().__new__(mcs, name, bases, namespace)

        # 1. 标记为 crew 类
        cls.is_crew_class = True
        cls._crew_name = name

        # 2. 执行类设置函数
        for setup_fn in _CLASS_SETUP_FUNCTIONS:
            setup_fn(cls)  # 设置 base_directory、config_paths 等

        # 3. 注入方法（load_configurations、get_mcp_tools 等）
        for method in _METHODS_TO_INJECT:
            setattr(cls, method.__name__, method)

        return cls

    def __call__(cls, *args, **kwargs):
        """拦截实例创建，初始化 crew 功能。"""
        instance = super().__call__(*args, **kwargs)  # 创建实例

        # 1. 加载配置（YAML 文件）
        instance.load_configurations()

        # 2. 收集所有方法
        instance._all_methods = _get_all_methods(instance)

        # 3. 映射 YAML 变量到 Agent/Task
        instance.map_all_agent_variables()
        instance.map_all_task_variables()

        # 4. 构建 CrewMetadata
        instance.__crew_metadata__ = CrewMetadata(
            original_methods=original_methods,
            original_tasks=_filter_methods(original_methods, "is_task"),
            original_agents=_filter_methods(original_methods, "is_agent"),
            before_kickoff=_filter_methods(original_methods, "is_before_kickoff"),
            after_kickoff=after_kickoff_callbacks,
            kickoff=_filter_methods(original_methods, "is_kickoff"),
        )

        return instance
```

**类设置函数：**

```python
_CLASS_SETUP_FUNCTIONS = [
    _set_base_directory,    # 设置 base_directory = 类定义文件所在目录
    _set_config_paths,      # 设置 agents_config/tasks_config 路径
    _set_mcp_params,        # 设置 MCP 服务器参数
]
```

**大白话：** CrewBaseMeta 是 Project 模块的核心——它在类定义时扫描并注入基础设施，在实例化时加载 YAML 配置、映射变量、构建元数据。

---

### 2.3 第三层：CrewDefinition（声明式定义）

**文件：** `lib/crewai/src/crewai/project/crew_definition.py`

```python
class CrewDefinition(BaseModel):
    """声明式 Crew 定义（可序列化为 JSON/YAML）。"""

    name: str | None = None
    description: str | None = None
    agents: dict[str, CrewAgentDefinition]  # Agent 定义映射
    tasks: list[CrewTaskDefinition]         # Task 定义列表
    process: str = "sequential"             # 执行策略
    manager_agent: str | None = None        # 层级模式的管理者
    inputs: dict[str, Any] = {}             # 默认输入
    tools: list[str] | None = None          # 全局工具

class CrewAgentDefinition(BaseModel):
    """Agent 定义。"""
    role: str | None = None
    goal: str | None = None
    backstory: str | None = None
    type: str | PythonReferenceDefinition | None = None  # 内置类型或 Python 引用
    llm: LLMDefinition | None = None
    tools: list[str] | None = None
    # ... 其他字段

class CrewTaskDefinition(BaseModel):
    """Task 定义。"""
    description: str
    expected_output: str
    agent: str                             # 引用的 Agent 名称
    context: list[str] | None = None       # 依赖的 Task 名称
    tools: list[str] | None = None
    async_execution: bool = False
    # ... 其他字段
```

---

### 2.4 第四层：CrewLoader（加载器）

**文件：** `lib/crewai/src/crewai/project/crew_loader.py`

```python
def load_crew(source: Path | str) -> tuple[Crew, dict[str, Any]]:
    """从 JSON/JSONC 定义文件加载 Crew。"""
    crew_path = Path(source)
    project = load_json_crew_project(crew_path)
    return _load_crew_project(project, project_root=crew_path.parent)

def _load_crew_project(project, project_root):
    """将 JSONCrewProject 转换为 Crew 实例。"""
    # 1. 创建 Agent 列表
    agents = []
    for agent_name, agent_def in project.agents.items():
        agent_kwargs = _agent_kwargs_from_definition(agent_def)
        agents.append(Agent(**agent_kwargs))

    # 2. 创建 Task 列表
    tasks = []
    for task_def in project.tasks:
        task_kwargs = _task_kwargs_from_definition(task_def)
        task_kwargs["agent"] = agent_map[task_def["agent"]]
        tasks.append(Task(**task_kwargs))

    # 3. 创建 Crew
    crew = Crew(
        agents=agents,
        tasks=tasks,
        process=project.process,
        **crew_kwargs,
    )
    return crew, project.inputs
```

---

### 2.5 第五层：YAML 配置加载

```python
# config/agents.yaml
researcher:
  role: "Research Specialist"
  goal: "Find the latest information on {topic}"
  backstory: "Expert researcher with 10 years experience"
  tools: ["search_tool"]
  verbose: true

# config/tasks.yaml
research_task:
  description: "Research {topic} thoroughly"
  expected_output: "A detailed research report"
  agent: "researcher"

# Python 代码
@CrewBase
class ResearchCrew:
    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    @agent
    def researcher(self) -> Agent:
        return Agent(
            config=self.agents_config["researcher"],  # 自动从 YAML 加载
            tools=[self.search_tool()],
        )

    @task
    def research_task(self) -> Task:
        return Task(
            config=self.tasks_config["research_task"],
            agent=self.researcher(),
        )

    @tool
    def search_tool(self) -> BaseTool:
        return SerperDevTool()
```

---

## 3. 完整调用时序图

```
┌──────────────────────────────────────────────────────────────────────────┐
│                     Project 声明式定义完整时序                            │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  1. 类定义阶段（CrewBaseMeta.__new__）                                     │
│     @CrewBase                                                             │
│     class ResearchCrew:                                                   │
│         │                                                                  │
│         └── CrewBaseMeta.__new__("ResearchCrew", bases, namespace)        │
│             ├── namespace 包含:                                           │
│             │   ├── researcher: AgentMethod (被 @agent 标记)              │
│             │   ├── research_task: TaskMethod (被 @task 标记)             │
│             │   └── search_tool: ToolMethod (被 @tool 标记)               │
│             │                                                              │
│             ├── cls.is_crew_class = True                                  │
│             ├── cls._crew_name = "ResearchCrew"                           │
│             │                                                              │
│             ├── _set_base_directory(cls)                                  │
│             │   └── cls.base_directory = Path(inspect.getfile(cls)).parent│
│             │                                                              │
│             ├── _set_config_paths(cls)                                    │
│             │   ├── cls.agents_config_path = "config/agents.yaml"         │
│             │   └── cls.tasks_config_path = "config/tasks.yaml"           │
│             │                                                              │
│             └── 注入方法: load_configurations, get_mcp_tools, ...         │
│                                                                           │
│  2. 实例化阶段（CrewBaseMeta.__call__）                                    │
│     crew = ResearchCrew()                                                 │
│         │                                                                  │
│         ├── super().__call__() → 创建实例                                  │
│         │                                                                  │
│         ├── instance.load_configurations()                                │
│         │   ├── 加载 config/agents.yaml → self.agents_config              │
│         │   └── 加载 config/tasks.yaml → self.tasks_config                │
│         │                                                                  │
│         ├── instance._all_methods = _get_all_methods(instance)            │
│         │   └── 收集所有带 is_agent/is_task/is_tool 标记的方法             │
│         │                                                                  │
│         ├── instance.map_all_agent_variables()                            │
│         │   ├── 遍历 agents_config 中的所有 Agent                         │
│         │   └── 将 YAML 中的 {topic} 等占位符替换为实际值                  │
│         │                                                                  │
│         ├── instance.map_all_task_variables()                             │
│         │   └── 同上，处理 tasks_config                                    │
│         │                                                                  │
│         └── 构建 metadata: CrewMetadata(                                  │
│               original_agents={"researcher": researcher_method},          │
│               original_tasks={"research_task": task_method},              │
│               before_kickoff={},                                          │
│               after_kickoff={},                                           │
│             )                                                              │
│                                                                           │
│  3. 执行阶段                                                               │
│     crew.kickoff()                                                        │
│         │                                                                  │
│         ├── 执行 before_kickoff 回调                                      │
│         │                                                                  │
│         ├── crew.crew() → 构建 Crew 实例                                  │
│         │   ├── 调用 @agent 方法 → Agent 实例                             │
│         │   │   └── Agent(config=self.agents_config["researcher"], ...)   │
│         │   ├── 调用 @task 方法 → Task 实例                               │
│         │   │   └── Task(config=self.tasks_config["research_task"], ...)  │
│         │   └── Crew(agents=[...], tasks=[...], process="sequential")     │
│         │                                                                  │
│         ├── crew.kickoff() → 调度执行                                     │
│         │                                                                  │
│         └── 执行 after_kickoff 回调                                       │
│                                                                           │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 4. 核心设计亮点

### 4.1 装饰器 + 元类 = 声明式

```python
@CrewBase
class MyCrew:
    @agent
    def researcher(self) -> Agent: ...

    @task
    def research(self) -> Task: ...
```

用装饰器标记方法，元类自动扫描和注入，代码极其简洁。

### 4.2 YAML 配置分离

```yaml
# config/agents.yaml — 纯配置，无代码
researcher:
  role: "Research Specialist"
  goal: "Research {topic}"
```

Agent 定义从代码中分离到 YAML，非开发者也能修改配置。

### 4.3 包装器类型系统

```python
class AgentMethod(Generic[P, R]):
    is_agent: bool = True
    def __call__(self, ...) -> R: ...

class TaskMethod(Generic[P, TaskResultT]):
    is_task: bool = True
    ...
```

每个装饰器返回一个带类型标记的包装器，元类通过 `is_agent`、`is_task` 等属性识别方法，无需字符串匹配。

### 4.4 Memoize 缓存

```python
def agent(meth: Callable[P, R]) -> AgentMethod[P, R]:
    return AgentMethod(memoize(meth))  # 自动 memoize
```

Agent 和 Task 工厂方法自动 memoize，多次调用返回同一个实例，避免重复创建。

### 4.5 变量映射

```python
# YAML 中: "Research {topic}"
# 代码中调用: instance.map_all_agent_variables()
# 结果: "Research AI Agents"
```

支持 `{variable}` 占位符替换，结合 Crew 的 inputs 实现参数化配置。

---

## 5. 生产落地拓展改造

### 5.1 多环境 YAML 配置

```python
# config/agents.dev.yaml, config/agents.prod.yaml
import os
env = os.getenv("CREW_ENV", "dev")

@CrewBase
class MyCrew:
    agents_config = f"config/agents.{env}.yaml"
    tasks_config = f"config/tasks.{env}.yaml"
```

### 5.2 远程配置中心

```python
class RemoteConfigLoader:
    def load_configurations(self):
        import requests
        resp = requests.get(f"https://config.example.com/crew/{self._crew_name}/agents.yaml")
        self.agents_config = yaml.safe_load(resp.text)
```

### 5.3 环境变量注入

```python
# YAML 中引用环境变量
# agents.yaml
researcher:
  role: "Research Specialist"
  llm: "${OPENAI_API_KEY}"  # 自动替换为环境变量

# 在 map_all_agent_variables 中扩展
def _substitute_env_vars(self, config):
    import os, re
    for key, value in config.items():
        if isinstance(value, str):
            config[key] = re.sub(r'\$\{(\w+)\}', lambda m: os.getenv(m.group(1), ''), value)
```

---

## 6. 面试深挖问题清单

| # | 问题 | 考察点 |
|---|------|--------|
| 1 | `@CrewBase` 元类在类定义时做了哪些事？ | 元类注入、类设置 |
| 2 | `@agent` 和 `@task` 装饰器返回的包装器类型是什么？ | 标记属性、类型系统 |
| 3 | `memoize` 在装饰器中的作用是什么？ | 缓存、单例模式 |
| 4 | YAML 配置中的 `{variable}` 占位符是如何替换的？ | 变量映射、模板替换 |
| 5 | `before_kickoff` 和 `after_kickoff` 的执行顺序？ | 生命周期钩子 |
| 6 | `CrewMetadata` 存储了哪些关键信息？ | 元数据、方法注册 |
| 7 | `CrewDefinition` 与 `CrewBaseMeta` 的关系？ | 声明式 vs 过程式 |
| 8 | `load_crew` 如何从 JSON 文件创建 Crew 实例？ | 加载器、反序列化 |
| 9 | `_CLASS_SETUP_FUNCTIONS` 列表的设计模式是什么？ | 责任链、管道模式 |
| 10 | Project 模式与纯代码模式相比的优缺点？ | 配置分离、协作、调试 |

---

## 7. 简易可运行 Demo

```python
"""Demo: Project 声明式定义 — @CrewBase + YAML"""
from crewai import Agent, Task, Crew, Process
from crewai.project import CrewBase, agent, task, tool, before_kickoff, after_kickoff
from crewai.tools import BaseTool

# 文件结构:
# my_crew/
#   crew.py          ← 本文件
#   config/
#     agents.yaml    ← Agent 配置
#     tasks.yaml     ← Task 配置

# config/agents.yaml:
# researcher:
#   role: "Research Specialist"
#   goal: "Research {topic} thoroughly"
#   backstory: "Expert researcher"
#   verbose: true
#
# writer:
#   role: "Content Writer"
#   goal: "Write a compelling report about {topic}"
#   backstory: "Professional writer"
#   verbose: true

# config/tasks.yaml:
# research_task:
#   description: "Research {topic}"
#   expected_output: "Research findings"
#   agent: "researcher"
#
# write_task:
#   description: "Write a report based on research"
#   expected_output: "Final report"
#   agent: "writer"
#   context: ["research_task"]


@CrewBase
class ResearchCrew:
    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    @before_kickoff
    def setup_logging(self):
        print("[Setup] 初始化日志系统...")

    @agent
    def researcher(self) -> Agent:
        return Agent(
            config=self.agents_config["researcher"],
            tools=[self.search_tool()],
        )

    @agent
    def writer(self) -> Agent:
        return Agent(
            config=self.agents_config["writer"],
        )

    @task
    def research_task(self) -> Task:
        return Task(
            config=self.tasks_config["research_task"],
            agent=self.researcher(),
        )

    @task
    def write_task(self) -> Task:
        return Task(
            config=self.tasks_config["write_task"],
            agent=self.writer(),
        )

    @tool
    def search_tool(self) -> BaseTool:
        from crewai_tools import SerperDevTool
        return SerperDevTool()

    @after_kickoff
    def cleanup(self, outputs):
        print("[Cleanup] Crew 执行完成")
        return outputs

    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
        )


# 使用
crew_instance = ResearchCrew()
result = crew_instance.crew().kickoff(inputs={"topic": "AI Agents"})
print(f"结果: {result}")
```

---

**下一阶段解析指令：**

```
# 当前解析目标
模块名称：跨模块综合复盘
对应范围：全模块串联

# 本次输出硬性要求，缺一不可
1. 全模块架构总览图（一图看懂所有模块及其关系）
2. 关键数据流追踪（从 kickoff() 到最终输出的完整路径）
3. 各模块面试高频考点汇总（按模块×考点矩阵）
4. 简历可写项目经验模板（3 个档次：入门/进阶/专家）
5. 生产环境部署检查清单
6. 学习路径建议（从入门到源码贡献）
```