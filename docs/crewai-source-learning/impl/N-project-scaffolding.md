# 阶段 N：project/ — 项目脚手架实现逻辑详解

## 1. 模块定位与架构图

### 1.1 模块定位

`project/` 模块是 CrewAI 框架的 **项目脚手架（Project Scaffolding）**，负责提供声明式/装饰器风格的 Crew 定义方式。它包括五大核心能力：

- **元类驱动**：通过 `CrewBaseMeta` 元类在类创建时自动注入方法、设置配置路径
- **装饰器标注**：`@agent`、`@task`、`@tool`、`@crew` 等装饰器将方法标注为特定角色
- **YAML 配置加载**：自动从 `config/agents.yaml` 和 `config/tasks.yaml` 加载配置，并完成变量映射（将 YAML 字符串引用解析为实际实例）
- **声明式定义**：`CrewDefinition` / `CrewAgentDefinition` / `CrewTaskDefinition` 支持纯 JSON/YAML 的 Crew 定义（无需 Python 代码）
- **JSON 加载器**：`CrewLoader` 将 JSON/JSONC 项目文件转换为可运行的 `Crew` 实例

### 1.2 涉及的核心源码文件

| 文件 | 行数 | 核心职责 |
|------|------|----------|
| `lib/crewai/src/crewai/project/crew_base.py` | ~809 行 | `CrewBaseMeta` 元类、`CrewBase` 装饰器类、配置加载、变量映射、MCP 集成、Hook 注册 |
| `lib/crewai/src/crewai/project/annotations.py` | ~278 行 | 所有装饰器：`@agent`、`@task`、`@tool`、`@crew`、`@before_kickoff`、`@after_kickoff`、`@llm`、`@output_json`、`@output_pydantic`、`@callback`、`@cache_handler` |
| `lib/crewai/src/crewai/project/crew_definition.py` | ~378 行 | Pydantic 数据模型：`CrewDefinition`、`CrewAgentDefinition`、`CrewTaskDefinition`、`AgentDefinition`、`LLMDefinition`、`PythonReferenceDefinition` |
| `lib/crewai/src/crewai/project/crew_loader.py` | ~180 行 | `load_crew`、`load_crew_from_definition`、`load_crew_and_kickoff` 函数 |
| `lib/crewai/src/crewai/project/wrappers.py` | ~420 行 | 包装器类型：`AgentMethod`、`TaskMethod`、`ToolMethod`、`BeforeKickoffMethod`、`AfterKickoffMethod`、`LLMMethod`、`CallbackMethod`、`CacheHandlerMethod`、`OutputJsonClass`、`OutputPydanticClass`、`CrewMetadata`、`CrewInstance` Protocol、`CrewClass` Protocol |
| `lib/crewai/src/crewai/project/utils.py` | ~98 行 | `memoize` 缓存工具函数 |

### 1.3 架构图

```
用户代码（@CrewBase 装饰的类）
│
│  class MyCrew:
│      @agent  def researcher(self) -> Agent: ...
│      @task    def research_task(self) -> Task: ...
│      @crew    def crew(self) -> Crew: ...
│
│  ┌─ 类创建时（CrewBaseMeta.__new__）─────────────────────────────────────┐
│  │  crew_base.py 第 196-227 行                                            │
│  │                                                                        │
│  │  _CLASS_SETUP_FUNCTIONS:                          _METHODS_TO_INJECT:  │
│  │  ├── _set_base_directory()     第 135-144 行     ├── close_mcp_server │
│  │  ├── _set_config_paths()       第 147-156 行     ├── get_mcp_tools    │
│  │  └── _set_mcp_params()         第 159-166 行     ├── _load_config     │
│  │                                                   ├── load_configs    │
│  │  cls.is_crew_class = True                         ├── load_yaml       │
│  │  cls._crew_name = name                            ├── map_all_agent_vars│
│  │                                                   └── map_all_task_vars │
│  └────────────────────────────────────────────────────────────────────────┘
│
│  ┌─ 实例化时（CrewBaseMeta.__call__）────────────────────────────────────┐
│  │  crew_base.py 第 229-241 行                                            │
│  │                                                                        │
│  │  _initialize_crew_instance() 第 244-287 行:                            │
│  │  ├── load_configurations() → 加载 agents.yaml / tasks.yaml             │
│  │  ├── map_all_agent_variables() → llm/tool/cache_handler 字符串→实例   │
│  │  ├── map_all_task_variables() → agent/task/context/Json 字符串→实例   │
│  │  ├── _post_initialize_crew_hooks 钩子执行                              │
│  │  ├── __crew_metadata__ 元数据构建 (CrewMetadata)                      │
│  │  └── _register_crew_hooks() → LLM/Tool Hook 注册                      │
│  └────────────────────────────────────────────────────────────────────────┘
│
│  ┌─ 调用 crew() 方法时（@crew 装饰器）───────────────────────────────────┐
│  │  annotations.py 第 188-278 行                                          │
│  │                                                                        │
│  │  wrapper():                                                            │
│  │  ├── 遍历 original_tasks → 实例化 Task, 提取 Agent                     │
│  │  ├── 遍历 original_agents → 实例化 Agent, 去重                          │
│  │  ├── 设置 self.agents / self.tasks                                     │
│  │  ├── 调用 meth(self) → 获取 Crew 实例                                  │
│  │  ├── 设置 crew_instance.name                                           │
│  │  ├── 注册 before_kickoff_callbacks                                     │
│  │  ├── 注册 after_kickoff_callbacks                                      │
│  │  └── return crew_instance (memoized)                                   │
│  └────────────────────────────────────────────────────────────────────────┘
│
│  ┌─ 声明式路径（JSON/JSONC → Crew）──────────────────────────────────────┐
│  │  crew_loader.py 第 25-180 行                                           │
│  │                                                                        │
│  │  load_crew(source) → load_crew_from_definition(definition)             │
│  │  ├── CrewDefinition 解析 (crew_definition.py)                          │
│  │  ├── JSONCrewProject 构建 (json_loader.py)                             │
│  │  ├── Agent 实例化 (build_agent)                                        │
│  │  ├── Task 实例化 (task_class → task_kwargs)                            │
│  │  └── Crew 实例化 (Crew(**crew_kwargs))                                │
│  └────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 核心实现逻辑详解

### 2.1 CrewBaseMeta — 元类

**源码位置**：`lib/crewai/src/crewai/project/crew_base.py`，第 193-287 行。

`CrewBaseMeta` 是 `type` 的子类，也是整个 `@CrewBase` 装饰器魔术的核心引擎。它通过 Python 元类机制，在类**创建时**和**实例化时**两个阶段分别注入不同的行为。

#### 2.1.1 `__new__` — 类创建时的设置函数注入

**源码位置**：`crew_base.py`，第 196-227 行。

```python
# crew_base.py 第 196-227 行
def __new__(
    mcs, name: str, bases: tuple[type, ...],
    namespace: dict[str, Any], **kwargs: Any,
) -> type[CrewClass]:
    cls = cast(
        type[CrewClass], cast(object, super().__new__(mcs, name, bases, namespace))
    )

    cls.is_crew_class = True     # 第 218 行：标记这是个 Crew 类
    cls._crew_name = name        # 第 219 行：记住类名（后续用作 Crew name）

    for setup_fn in _CLASS_SETUP_FUNCTIONS:  # 第 221-222 行：执行类设置函数
        setup_fn(cls)

    for method in _METHODS_TO_INJECT:        # 第 224-225 行：注入方法到类
        setattr(cls, method.__name__, method)

    return cls
```

`_CLASS_SETUP_FUNCTIONS` 在 `crew_base.py` 第 743-747 行定义：

```python
# crew_base.py 第 743-747 行
_CLASS_SETUP_FUNCTIONS: tuple[Callable[[type[CrewClass]], None], ...] = (
    _set_base_directory,   # 第 135-144 行：设置 cls.base_directory
    _set_config_paths,     # 第 147-156 行：设置 agents_config / tasks_config 路径
    _set_mcp_params,       # 第 159-166 行：设置 MCP 服务器参数
)
```

**大白话**：`__new__` 在类被定义的那一刻就执行（不是实例化时）。它做了三件事：① 标记 `is_crew_class = True`，② 通过 `inspect.getfile(cls)` 获取类所在文件的目录作为 `base_directory`，③ 设置 YAML 配置路径（默认 `"config/agents.yaml"` 和 `"config/tasks.yaml"`，用户可在类定义中覆盖）。

**`_set_base_directory`**（`crew_base.py` 第 135-144 行）：

```python
# crew_base.py 第 135-144 行
def _set_base_directory(cls: type[CrewClass]) -> None:
    try:
        cls.base_directory = Path(inspect.getfile(cls)).parent  # 第 142 行
    except (TypeError, OSError):
        cls.base_directory = Path.cwd()  # 第 144 行：fallback 到当前目录
```

**大白话**：`inspect.getfile(cls)` 获取类定义所在的 `.py` 文件的绝对路径，然后取父目录。这就是为什么 `config/agents.yaml` 是相对于类文件所在目录的——你不需要写绝对路径。

**`_set_config_paths`**（`crew_base.py` 第 147-156 行）：

```python
# crew_base.py 第 147-156 行
def _set_config_paths(cls: type[CrewClass]) -> None:
    cls.original_agents_config_path = getattr(
        cls, "agents_config", "config/agents.yaml"   # 第 153-154 行
    )
    cls.original_tasks_config_path = getattr(
        cls, "tasks_config", "config/tasks.yaml"      # 第 156 行
    )
```

**大白话**：如果用户在类中定义了 `agents_config = "custom/agents.yaml"`，就用用户的；否则用默认值 `"config/agents.yaml"`。

#### 2.1.2 `_METHODS_TO_INJECT` — 方法注入

**源码位置**：`crew_base.py`，第 749-759 行。

```python
# crew_base.py 第 749-759 行
_METHODS_TO_INJECT = (
    close_mcp_server,              # 第 290-308 行：关闭 MCP 服务器
    get_mcp_tools,                 # 第 311-334 行：获取 MCP 工具
    _load_config,                  # 第 337-365 行：加载 YAML 配置
    load_configurations,           # 第 368-375 行：加载 agents 和 tasks 配置
    staticmethod(load_yaml),       # 第 378-396 行：静态方法，解析 YAML 文件
    map_all_agent_variables,       # 第 594-613 行：映射 Agent 变量
    _map_agent_variables,          # 第 616-659 行：映射单个 Agent 变量
    map_all_task_variables,        # 第 662-685 行：映射 Task 变量
    _map_task_variables,           # 第 688-741 行：映射单个 Task 变量
)
```

**大白话**：这些方法在 `__new__` 中通过 `setattr(cls, method.__name__, method)` 被直接注入到类中。这意味着用户类不需要继承任何基类，也能获得 `load_configurations()`、`map_all_agent_variables()` 等能力。注意 `load_yaml` 用了 `staticmethod` 包装，所以它在类上作为静态方法存在。

#### 2.1.3 `__call__` — 实例初始化时的拦截

**源码位置**：`crew_base.py`，第 229-241 行。

```python
# crew_base.py 第 229-241 行
def __call__(cls, *args: Any, **kwargs: Any) -> CrewInstance:
    instance: CrewInstance = super().__call__(*args, **kwargs)  # 第 239 行：先创建实例
    CrewBaseMeta._initialize_crew_instance(instance, cls)       # 第 240 行：然后初始化
    return instance
```

**大白话**：元类的 `__call__` 在每次 `MyCrew()` 实例化时被调用。它先调用 `super().__call__()` 走正常的 `__new__` + `__init__` 流程创建实例，然后调用 `_initialize_crew_instance()` 完成 Crew 特定的初始化工作。

#### 2.1.4 `_initialize_crew_instance` — 实例初始化全流程

**源码位置**：`crew_base.py`，第 244-287 行。

```python
# crew_base.py 第 244-287 行
@staticmethod
def _initialize_crew_instance(instance: CrewInstance, cls: type) -> None:
    instance._mcp_server_adapter = None                    # 第 251 行
    instance.load_configurations()                         # 第 252 行：加载 YAML
    instance._all_methods = _get_all_methods(instance)     # 第 253 行：收集所有方法
    instance.map_all_agent_variables()                     # 第 254 行：Agent 变量映射
    instance.map_all_task_variables()                      # 第 255 行：Task 变量映射

    for hook in _post_initialize_crew_hooks:               # 第 257-258 行：外部钩子
        hook(instance)

    original_methods = {                                   # 第 260-273 行：收集带标记的方法
        name: method
        for name, method in cls.__dict__.items()
        if any(hasattr(method, attr) for attr in [
            "is_task", "is_agent", "is_before_kickoff",
            "is_after_kickoff", "is_kickoff",
        ])
    }

    after_kickoff_callbacks = _filter_methods(original_methods, "is_after_kickoff")
    after_kickoff_callbacks["close_mcp_server"] = instance.close_mcp_server  # 第 276 行

    instance.__crew_metadata__ = CrewMetadata(             # 第 278-285 行
        original_methods=original_methods,
        original_tasks=_filter_methods(original_methods, "is_task"),
        original_agents=_filter_methods(original_methods, "is_agent"),
        before_kickoff=_filter_methods(original_methods, "is_before_kickoff"),
        after_kickoff=after_kickoff_callbacks,             # 含 close_mcp_server
        kickoff=_filter_methods(original_methods, "is_kickoff"),
    )

    _register_crew_hooks(instance, cls)                    # 第 287 行：注册 Hook
```

**流程解读**：

1. **第 252 行** `load_configurations()`：调用 `_load_config()` 加载 `agents.yaml` 和 `tasks.yaml`，存入 `self.agents_config` 和 `self.tasks_config`。

2. **第 253 行** `_get_all_methods(instance)`：通过 `dir(self)` 获取实例所有非 `__dunder__` 的可调用属性。这会把 `@agent`、`@task`、`@tool` 等装饰过的方法都收集进来。

3. **第 254-255 行** 变量映射：这是关键步骤——YAML 配置中的字符串引用（如 `llm: "openai_llm"`、`agent: "researcher"`）在此被解析为实际的可调用对象。详见 2.1.5 和 2.1.6。

4. **第 260-273 行** `original_methods`：遍历 `cls.__dict__`（类自身的属性，不含继承的），筛选出带有 `is_task`、`is_agent`、`is_before_kickoff`、`is_after_kickoff`、`is_kickoff` 标记的方法。这些标记来自装饰器（如 `@task` 装饰器返回的 `TaskMethod` 对象有 `is_task = True` 属性）。

5. **第 276 行**：自动将 `close_mcp_server` 注册为 after_kickoff 回调，确保 Crew 执行完毕后清理 MCP 连接。

6. **第 287 行** `_register_crew_hooks(instance, cls)`：检测 `@before_llm_call_hook`、`@after_llm_call_hook` 等 Hook 装饰器标记的方法，并注册到全局 Hook 系统中。

#### 2.1.5 配置加载 — `load_configurations` 与 `load_yaml`

**源码位置**：`crew_base.py`，第 337-396 行。

```python
# crew_base.py 第 337-365 行
def _load_config(
    self, config_path: str | None, config_type: Literal["agent", "task"]
) -> dict[str, Any]:
    if isinstance(config_path, str):
        full_path = self.base_directory / config_path          # 第 351 行：拼接绝对路径
        try:
            return self.load_yaml(full_path)                   # 第 353 行
        except FileNotFoundError:
            logging.warning(...)                               # 第 355-358 行
            return {}
    else:
        logging.warning(...)
        return {}
```

```python
# crew_base.py 第 378-396 行
def load_yaml(config_path: Path) -> dict[str, Any]:
    try:
        with open(config_path, encoding="utf-8") as file:     # 第 391 行
            content = yaml.safe_load(file)                     # 第 392 行
        return content if isinstance(content, dict) else {}    # 第 393 行
    except FileNotFoundError:
        logging.warning(f"File not found: {config_path}")     # 第 395 行
        raise                                                  # 第 396 行：重新抛出
```

**大白话**：`load_yaml` 是静态方法，直接用 `yaml.safe_load()` 解析 YAML 文件。`_load_config` 包装了路径拼接和错误处理。如果文件不存在，`_load_config` 吞掉异常返回 `{}`（但 `load_yaml` 日志后会重新抛出，所以是 `_load_config` 的 `try/except` 捕获了 `FileNotFoundError`）。

**YAML 配置示例**（`config/agents.yaml`）：

```yaml
researcher:
  role: "Research Analyst"
  goal: "Research {topic}"
  backstory: "Expert researcher"
  llm: "openai_llm"           # ← 字符串引用，需映射为实际 LLM 实例
  tools:                        # ← 字符串引用列表，需映射为实际工具实例
    - "search_tool"
    - "scrape_tool"
```

**YAML 配置示例**（`config/tasks.yaml`）：

```yaml
research_task:
  description: "Research {topic}"
  expected_output: "Key findings"
  agent: "researcher"            # ← 字符串引用，需映射为实际 Agent 实例
  context:                       # ← 字符串引用列表，需映射为实际 Task 实例
    - "analysis_task"
```

#### 2.1.6 Agent 变量映射 — `map_all_agent_variables`

**源码位置**：`crew_base.py`，第 594-659 行。

```python
# crew_base.py 第 594-613 行
def map_all_agent_variables(self: CrewInstance) -> None:
    llms = _filter_methods(self._all_methods, "is_llm")                    # 第 600 行
    tool_functions = _filter_methods(self._all_methods, "is_tool")         # 第 601 行
    cache_handler_functions = _filter_methods(self._all_methods, "is_cache_handler")  # 第 602 行
    callbacks = _filter_methods(self._all_methods, "is_callback")          # 第 603 行

    for agent_name, agent_info in self.agents_config.items():              # 第 605 行
        self._map_agent_variables(
            agent_name=agent_name, agent_info=agent_info,
            llms=llms, tool_functions=tool_functions,
            cache_handler_functions=cache_handler_functions, callbacks=callbacks,
        )
```

**核心逻辑**（`_map_agent_variables`，`crew_base.py` 第 616-659 行）：

```python
# crew_base.py 第 616-659 行
def _map_agent_variables(self, agent_name, agent_info, llms, tool_functions, ...):
    # ① LLM 映射（第 636-638 行）
    if llm := agent_info.get("llm"):
        factory = llms.get(llm)
        self.agents_config[agent_name]["llm"] = factory() if factory else llm

    # ② 工具映射（第 640-644 行）
    if tools := agent_info.get("tools"):
        if _is_string_list(tools):
            self.agents_config[agent_name]["tools"] = [
                tool_functions[tool]() for tool in tools
            ]

    # ③ function_calling_llm 映射（第 646-650 行）
    if function_calling_llm := agent_info.get("function_calling_llm"):
        factory = llms.get(function_calling_llm)
        self.agents_config[agent_name]["function_calling_llm"] = (
            factory() if factory else function_calling_llm
        )

    # ④ step_callback 映射（第 652-653 行）
    if step_callback := agent_info.get("step_callback"):
        self.agents_config[agent_name]["step_callback"] = callbacks[step_callback]()

    # ⑤ cache_handler 映射（第 655-659 行）
    if cache_handler := agent_info.get("cache_handler"):
        if _is_string_value(cache_handler):
            self.agents_config[agent_name]["cache_handler"] = cache_handler_functions[
                cache_handler
            ]()
```

**大白话**：YAML 里写的是字符串 `"openai_llm"`，但 Agent 构造函数需要的是真正的 `BaseLLM` 实例。`_map_agent_variables` 负责这个转换：它从 `_all_methods` 中找出所有 `@llm` 装饰的方法，然后按名字匹配——如果 `agents_config["researcher"]["llm"]` 的值是 `"openai_llm"`，就找到对应的 `@llm` 方法并调用它（`factory()` 或 `llms.get(llm)`），把返回值替换掉原来的字符串。

**关键点**：
- `_is_string_list(tools)`（`crew_base.py` 第 169-178 行）是类型守卫：只有当列表里全是字符串时才映射；如果 YAML 里已经直接写了 `BaseTool` 实例，就跳过映射。
- `_is_string_value(cache_handler)`（`crew_base.py` 第 181-190 行）同理：只有当 `cache_handler` 是字符串时才映射，否则保留原值。

#### 2.1.7 Task 变量映射 — `map_all_task_variables`

**源码位置**：`crew_base.py`，第 662-741 行。

```python
# crew_base.py 第 662-685 行
def map_all_task_variables(self: CrewInstance) -> None:
    agents = _filter_methods(self._all_methods, "is_agent")                # 第 668 行
    tasks = _filter_methods(self._all_methods, "is_task")                  # 第 669 行
    output_json_functions = _filter_methods(self._all_methods, "is_output_json")   # 第 670 行
    tool_functions = _filter_methods(self._all_methods, "is_tool")         # 第 671 行
    callback_functions = _filter_methods(self._all_methods, "is_callback") # 第 672 行
    output_pydantic_functions = _filter_methods(self._all_methods, "is_output_pydantic")  # 第 673 行

    for task_name, task_info in self.tasks_config.items():                 # 第 675 行
        self._map_task_variables(...)
```

**核心逻辑**（`_map_task_variables`，`crew_base.py` 第 688-741 行）：

```python
# crew_base.py 第 688-741 行
def _map_task_variables(self, task_name, task_info, agents, tasks, ...):
    # ① context 映射（第 712-715 行）
    if context_list := task_info.get("context"):
        self.tasks_config[task_name]["context"] = [
            tasks[context_task_name]() for context_task_name in context_list
        ]

    # ② tools 映射（第 717-721 行）
    if tools := task_info.get("tools"):
        if _is_string_list(tools):
            self.tasks_config[task_name]["tools"] = [
                tool_functions[tool]() for tool in tools
            ]

    # ③ agent 映射（第 723-724 行）
    if agent_name := task_info.get("agent"):
        self.tasks_config[task_name]["agent"] = agents[agent_name]()

    # ④ output_json 映射（第 726-727 行）
    if output_json := task_info.get("output_json"):
        self.tasks_config[task_name]["output_json"] = output_json_functions[output_json]

    # ⑤ output_pydantic 映射（第 729-732 行）
    if output_pydantic := task_info.get("output_pydantic"):
        self.tasks_config[task_name]["output_pydantic"] = output_pydantic_functions[
            output_pydantic
        ]

    # ⑥ callbacks 映射（第 734-737 行）
    if callbacks := task_info.get("callbacks"):
        self.tasks_config[task_name]["callbacks"] = [
            callback_functions[callback]() for callback in callbacks
        ]
```

**大白话**：与 Agent 变量映射类似，但多了 `context`（任务依赖）、`output_json`、`output_pydantic` 的映射。注意 `context` 映射是将字符串 `"analysis_task"` 替换为对应 `@task` 方法的返回值（即 `Task` 实例）。

#### 2.1.8 Hook 注册 — `_register_crew_hooks`

**源码位置**：`crew_base.py`，第 434-591 行。

`_register_crew_hooks` 检测类中定义的 `@before_llm_call_hook`、`@after_llm_call_hook`、`@before_tool_call_hook`、`@after_tool_call_hook` 等方法，并将其注册到全局 Hook 系统中。

**关键细节**：

```python
# crew_base.py 第 441-453 行
hook_methods = {
    name: method
    for name, method in cls.__dict__.items()
    if any(
        hasattr(method, attr)
        for attr in [
            "is_before_llm_call_hook",
            "is_after_llm_call_hook",
            "is_before_tool_call_hook",
            "is_after_tool_call_hook",
        ]
    )
}
```

对于每个 Hook 方法，会检查其 `_filter_agents` 和 `_filter_tools` 属性（来自 `@filter_agents`、`@filter_tools` 装饰器），如果有过滤条件，则生成包装函数。例如，`@filter_agents(["researcher"])` 的 `before_llm_call_hook` 只在 Agent.role 为 "researcher" 时才触发（`crew_base.py` 第 476-497 行）。

---

### 2.2 Annotations — 装饰器

**源码位置**：`lib/crewai/src/crewai/project/annotations.py`，第 1-278 行。

#### 2.2.1 `@agent` — 标注 Agent 工厂方法

**源码位置**：`annotations.py`，第 78-87 行。

```python
# annotations.py 第 78-87 行
def agent(meth: Callable[P, R]) -> AgentMethod[P, R]:
    return AgentMethod(memoize(meth))
```

**大白话**：`@agent` 装饰器将方法包装为 `AgentMethod` 对象（`wrappers.py` 第 336-339 行），该类有 `is_agent = True` 标记。外层的 `memoize` 确保同一个 `@agent` 方法用相同参数只会执行一次——Agent 实例被缓存，避免重复创建。

**关键**：`AgentMethod` 继承自 `DecoratedMethod`（`wrappers.py` 第 157-226 行），后者实现了 Python 描述符协议（`__get__` 方法），使得 `self.researcher()` 调用时能正确绑定 `self`。

#### 2.2.2 `@task` — 标注 Task 工厂方法

**源码位置**：`annotations.py`，第 66-75 行。

```python
# annotations.py 第 66-75 行
def task(meth: Callable[P, TaskResultT]) -> TaskMethod[P, TaskResultT]:
    return TaskMethod(memoize(meth))
```

**大白话**：与 `@agent` 类似，但 `TaskMethod` 有额外逻辑：`ensure_task_name()` 方法（`wrappers.py` 第 284-295 行）确保 Task 的 `name` 不为空——如果为空，就用方法名填充。

```python
# wrappers.py 第 284-295 行
def ensure_task_name(self, result: TaskResultT) -> TaskResultT:
    if not result.name:
        result.name = self._meth.__name__  # 用方法名作为 Task 名称
    return result
```

`TaskMethod` 还有 `BoundTaskMethod`（`wrappers.py` 第 240-267 行），它是通过 `__get__` 返回的绑定版本，确保 `self` 被正确传递。

#### 2.2.3 `@tool` — 标注工具方法

**源码位置**：`annotations.py`，第 126-135 行。

```python
# annotations.py 第 126-135 行
def tool(meth: Callable[P, R]) -> ToolMethod[P, R]:
    return ToolMethod(memoize(meth))
```

`ToolMethod` 在 `wrappers.py` 第 348-351 行定义，有 `is_tool = True` 标记。工具方法在 `map_all_agent_variables` 中被收集和映射。

#### 2.2.4 `@before_kickoff` / `@after_kickoff` — 生命周期钩子

**源码位置**：`annotations.py`，第 42-63 行。

```python
# annotations.py 第 42-51 行
def before_kickoff(meth: Callable[P, R]) -> BeforeKickoffMethod[P, R]:
    return BeforeKickoffMethod(meth)  # 不 memoize

# annotations.py 第 54-63 行
def after_kickoff(meth: Callable[P, R]) -> AfterKickoffMethod[P, R]:
    return AfterKickoffMethod(meth)  # 不 memoize
```

**大白话**：这两个装饰器的返回值**不经过 memoize**。因为 `before_kickoff` 和 `after_kickoff` 回调每次执行都应该真的运行，缓存结果没有意义。

它们的实际调用发生在 `@crew` 装饰器的 `wrapper` 函数中（`annotations.py` 第 267-274 行）：

```python
# annotations.py 第 267-274 行
for hook_callback in self.__crew_metadata__["before_kickoff"].values():
    crew_instance.before_kickoff_callbacks.append(
        callback_wrapper(hook_callback, self)
    )
for hook_callback in self.__crew_metadata__["after_kickoff"].values():
    crew_instance.after_kickoff_callbacks.append(
        callback_wrapper(hook_callback, self)
    )
```

#### 2.2.5 `@crew` — 核心执行入口

**源码位置**：`annotations.py`，第 180-278 行。

这是最复杂的装饰器，我们逐步拆解。

**（A）装饰器签名**（`annotations.py` 第 180-190 行）：

```python
# annotations.py 第 180-190 行
@overload
def crew(meth: Callable[Concatenate[SelfT, P], Crew]) -> Callable[Concatenate[SelfT, P], Crew]: ...
@overload
def crew(meth: Callable[Concatenate[CrewInstance, P], Crew]) -> Callable[Concatenate[CrewInstance, P], Crew]: ...
def crew(meth: Callable[..., Crew]) -> Callable[..., Crew]:
```

**大白话**：两个 `@overload` 签名用于类型检查，确保 `self` 参数的类型正确。

**（B）wrapper 函数**（`annotations.py` 第 200-277 行）：

```python
# annotations.py 第 200-277 行
@wraps(meth)
def wrapper(self: CrewInstance, *args: Any, **kwargs: Any) -> Crew:
    instantiated_tasks: list[Task] = []          # 第 212 行
    instantiated_agents: list[Agent] = []        # 第 213 行
    agent_roles: set[str] = set()                # 第 214 行

    tasks = self.__crew_metadata__["original_tasks"].items()    # 第 216 行
    agents = self.__crew_metadata__["original_agents"].items()  # 第 217 行

    # 步骤 ①：先实例化所有 Task，并从中提取 Agent（第 219-225 行）
    for _, task_method in tasks:
        task_instance = _call_method(task_method, self)          # 第 220 行
        instantiated_tasks.append(task_instance)                 # 第 221 行
        agent_instance = getattr(task_instance, "agent", None)   # 第 222 行
        if agent_instance and agent_instance.role not in agent_roles:
            instantiated_agents.append(agent_instance)           # 第 224 行
            agent_roles.add(agent_instance.role)                 # 第 225 行

    # 步骤 ②：再实例化独立的 Agent（去重）（第 227-231 行）
    for _, agent_method in agents:
        agent_instance = _call_method(agent_method, self)        # 第 228 行
        if agent_instance.role not in agent_roles:
            instantiated_agents.append(agent_instance)           # 第 230 行
            agent_roles.add(agent_instance.role)                 # 第 231 行

    # 步骤 ③：设置实例属性（第 233-234 行）
    self.agents = instantiated_agents
    self.tasks = instantiated_tasks

    # 步骤 ④：调用用户定义的 crew() 方法（第 236 行）
    crew_instance: Crew = _call_method(meth, self, *args, **kwargs)

    # 步骤 ⑤：设置 Crew 名称（第 237-238 行）
    if "name" not in crew_instance.model_fields_set:
        crew_instance.name = getattr(self, "_crew_name", None) or crew_instance.name

    # 步骤 ⑥：注册 before_kickoff / after_kickoff 回调（第 267-274 行）
    for hook_callback in self.__crew_metadata__["before_kickoff"].values():
        crew_instance.before_kickoff_callbacks.append(
            callback_wrapper(hook_callback, self)
        )
    for hook_callback in self.__crew_metadata__["after_kickoff"].values():
        crew_instance.after_kickoff_callbacks.append(
            callback_wrapper(hook_callback, self)
        )

    return crew_instance

return memoize(wrapper)  # 第 278 行：wrapper 本身也被 memoize
```

**大白话**：`@crew` 装饰器的 `wrapper` 做了以下事情：

1. **先实例化 Task**（第 219-225 行）：因为 Task 可能已经关联了 Agent（`task.agent`），所以先遍历 Task 并从中提取 Agent。
2. **再实例化独立 Agent**（第 227-231 行）：那些没有在 Task 中关联的 Agent 在这里被实例化。通过 `agent_roles` 集合去重。
3. **设置实例属性**（第 233-234 行）：`self.agents` 和 `self.tasks` 被赋值。
4. **调用用户方法**（第 236 行）：调用用户定义的 `crew()` 方法（如 `Crew(agents=self.agents, tasks=self.tasks)`），获取 `Crew` 实例。
5. **设置名称**（第 237-238 行）：如果用户没有显式设置 `name`，就用类名作为 Crew 名称。
6. **注册回调**（第 267-274 行）：将 `@before_kickoff` 和 `@after_kickoff` 方法注册为 Crew 的回调。
7. **memoize 包装**（第 278 行）：整个 wrapper 被 `memoize` 包装，确保 `crew()` 方法用相同参数只执行一次。

**`_call_method` 辅助函数**（`annotations.py` 第 162-177 行）：

```python
# annotations.py 第 162-177 行
def _call_method(method: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    result = method(*args, **kwargs)
    if inspect.iscoroutine(result):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop and loop.is_running():
            import concurrent.futures
            ctx = contextvars.copy_context()
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(ctx.run, asyncio.run, result).result()
        return asyncio.run(result)
    return result
```

**大白话**：`_call_method` 智能处理同步和异步方法。如果方法返回协程且当前事件循环正在运行，就用 `ThreadPoolExecutor` 在新线程中 `asyncio.run()`；否则直接用 `asyncio.run()`。

#### 2.2.6 `@llm` — 标注 LLM 工厂方法

**源码位置**：`annotations.py`，第 90-99 行。

```python
# annotations.py 第 90-99 行
def llm(meth: Callable[P, R]) -> LLMMethod[P, R]:
    return LLMMethod(memoize(meth))
```

**大白话**：`@llm` 方法返回 `BaseLLM` 实例。在 `map_all_agent_variables` 中，YAML 配置的 `llm: "openai_llm"` 字符串会被解析为对应的 `@llm` 方法调用。

#### 2.2.7 `@callback` / `@cache_handler` — 回调与缓存

**源码位置**：`annotations.py`，第 138-159 行。

```python
# annotations.py 第 138-147 行
def callback(meth: Callable[P, R]) -> CallbackMethod[P, R]:
    return CallbackMethod(memoize(meth))

# annotations.py 第 150-159 行
def cache_handler(meth: Callable[P, R]) -> CacheHandlerMethod[P, R]:
    return CacheHandlerMethod(memoize(meth))
```

**大白话**：`@callback` 用于定义 Agent 的 `step_callback`（每个步骤执行后的回调）。`@cache_handler` 用于定义自定义缓存处理器。它们都被 memoize 包装。

#### 2.2.8 `@output_json` / `@output_pydantic` — 输出格式

**源码位置**：`annotations.py`，第 102-123 行。

```python
# annotations.py 第 102-111 行
def output_json(cls: type[T]) -> OutputJsonClass[T]:
    return OutputJsonClass(cls)

# annotations.py 第 114-123 行
def output_pydantic(cls: type[T]) -> OutputPydanticClass[T]:
    return OutputPydanticClass(cls)
```

**大白话**：这两个是**类装饰器**（不是方法装饰器），用于标注输出格式。`OutputJsonClass` 和 `OutputPydanticClass` 继承自 `OutputClass`（`wrappers.py` 第 372-420 行），它通过 `__getattr__` 代理所有属性访问到原始类，同时添加 `is_output_json` 或 `is_output_pydantic` 标记。在 `map_all_task_variables` 中，`output_json_functions[output_json]` 获得的是 `OutputJsonClass` 包装器本身（不是实例），Task 的 `output_json` 参数直接接收这个类。

---

### 2.3 CrewDefinition — 声明式定义

**源码位置**：`lib/crewai/src/crewai/project/crew_definition.py`，第 1-378 行。

这个模块定义了声明式 Crew 定义的 Pydantic 数据模型，让你可以用纯 JSON/YAML 描述一个 Crew，而不需要写 Python 代码。

#### 2.3.1 `PythonReferenceDefinition` — Python 引用

**源码位置**：`crew_definition.py`，第 22-41 行。

```python
# crew_definition.py 第 22-41 行
class PythonReferenceDefinition(BaseModel):
    python: str = Field(
        description="Dotted Python import path to load.",
        examples=["my_project.schemas.SupportReply"],
    )

    @field_validator("python")
    @classmethod
    def _validate_python_ref(cls, value: str) -> str:
        path = value.strip()
        if not path:
            raise ValueError("Python reference 'python' must be a string")
        if "." not in path:
            raise ValueError(
                f"Python reference '{path}' must be a dotted import path "
                "like 'module.attribute'"
            )
        return path
```

**大白话**：一个简单的 Pydantic 模型，只有一个字段 `python`，必须是有效的点号分隔的 Python 导入路径。验证器 `_validate_python_ref` 确保路径非空且包含 `"."`。

#### 2.3.2 `LLMDefinition` — LLM 配置

**源码位置**：`crew_definition.py`，第 44-61 行。

```python
# crew_definition.py 第 44-61 行
class LLMDefinition(BaseModel):
    model_config = ConfigDict(extra="allow")  # 第 47 行：允许额外字段

    model: str = Field(description="Model identifier ...", examples=["openai/gpt-4o-mini"])
    max_tokens: int | None = Field(default=None, ...)
```

**大白话**：LLM 配置模型，`extra="allow"` 意味着可以传入任意额外字段（如 `temperature`、`top_p` 等），它们会被透传给 LLM 构造函数。

#### 2.3.3 `CrewAgentDefinition` — 内联 Agent 定义

**源码位置**：`crew_definition.py`，第 64-193 行。

```python
# crew_definition.py 第 64-193 行
class CrewAgentDefinition(BaseModel):
    model_config = ConfigDict(extra="allow")

    role: str | None = None
    goal: str | None = None
    backstory: str | None = None
    type: str | PythonReferenceDefinition | None = None  # 第 93 行
    from_repository: str | None = None
    settings: dict[str, Any] = Field(default_factory=dict)
    llm: str | LLMDefinition | None = None               # 第 112 行
    planning_config: PlanningConfig | None = None
    allow_delegation: bool | None = None
    max_iter: int | None = None
    max_rpm: int | None = None
    max_execution_time: int | None = None
    tools: list[str | dict[str, Any]] | None = None       # 第 148 行
    apps: list[str] | None = None
    mcps: list[str | dict[str, Any]] | None = None        # 第 165 行
```

**大白话**：这是 Agent 的完整配置模型，几乎所有字段都是可选的。关键设计点：

- `type`（第 93 行）：可以是字符串 `"agent"` 或 `PythonReferenceDefinition`，用于加载自定义 Agent 类。
- `llm`（第 112 行）：可以是字符串（模型名）或 `LLMDefinition` 对象。
- `tools`（第 148 行）：支持 CrewAI 内置工具名、`custom:<name>` 自定义工具、`module:Class` 完全限定引用。
- `mcps`（第 165 行）：支持 MCP 服务器 URL、集成 slug、`#tool_name` 后缀过滤特定工具。

#### 2.3.4 `CrewTaskDefinition` — 内联 Task 定义

**源码位置**：`crew_definition.py`，第 243-281 行。

```python
# crew_definition.py 第 243-281 行
class CrewTaskDefinition(BaseModel):
    model_config = ConfigDict(extra="allow")

    description: str = Field(...)           # 第 248 行：必填
    expected_output: str = Field(...)       # 第 255 行：必填
    name: str | None = None
    agent: str | None = None               # 第 267 行：Agent 名称引用
    context: list[str] | None = None       # 第 272 行：依赖 Task 名称列表
    type: str | PythonReferenceDefinition | None = None  # 第 277 行
```

**大白话**：`description` 和 `expected_output` 是必填的。`agent` 是字符串引用，指向 `CrewDefinition.agents` 中的 key。`context` 是 Task 名称列表，表示依赖关系。

#### 2.3.5 `CrewDefinition` — 顶层 Crew 定义

**源码位置**：`crew_definition.py`，第 287-378 行。

```python
# crew_definition.py 第 287-378 行
class CrewDefinition(BaseModel):
    model_config = ConfigDict(extra="allow")

    agents: dict[str, CrewAgentDefinition] = Field(...)  # 第 292 行：Agent 字典
    tasks: list[CrewTaskDefinition] = Field(...)          # 第 304 行：Task 列表
    inputs: dict[str, Any] = Field(default_factory=dict)  # 第 317 行：默认输入
    manager_agent: str | PythonReferenceDefinition | None = None  # 第 325 行
```

**关键验证器**：

`_validate_inline_agents`（`crew_definition.py` 第 338-369 行）支持两种 Agent 定义格式：

```python
# crew_definition.py 第 338-369 行
@field_validator("agents", mode="before", ...)
@classmethod
def _validate_inline_agents(cls, value: Any) -> Any:
    if isinstance(value, dict):
        return value  # 已经是字典格式，直接返回
    if not isinstance(value, list):
        return value

    # 列表格式：支持两种写法
    agents: dict[str, Any] = {}
    for index, item in enumerate(value):
        if "name" in item:
            # 写法 ①：{"name": "researcher", "role": "..."}
            name = item["name"]
            agents[name] = {key: val for key, val in item.items() if key != "name"}
        elif len(item) == 1:
            # 写法 ②：{"researcher": {"role": "..."}}
            name, definition = next(iter(item.items()))
            agents[str(name)] = definition
    return agents
```

**大白话**：`agents` 字段可以写成字典 `{"researcher": {...}}`，也可以写成列表 `[{"name": "researcher", "role": "..."}]` 或 `[{"researcher": {"role": "..."}}]`。验证器将它们统一转换为字典格式。

`_validate_inline_shape`（`crew_definition.py` 第 371-378 行）确保 `agents` 和 `tasks` 非空。

---

### 2.4 CrewLoader — 加载器

**源码位置**：`lib/crewai/src/crewai/project/crew_loader.py`，第 1-180 行。

#### 2.4.1 `load_crew` — 从文件加载

**源码位置**：`crew_loader.py`，第 25-37 行。

```python
# crew_loader.py 第 25-37 行
def load_crew(
    source: Path | str,
    agents_dir: Path | None = None,
) -> tuple[Any, dict[str, Any]]:
    crew_path = Path(source)
    project = load_json_crew_project(crew_path, agents_dir=agents_dir)  # 第 36 行
    return _load_crew_project(project, project_root=crew_path.parent)    # 第 37 行
```

**大白话**：`load_crew` 接收一个 JSON/JSONC 文件路径，调用 `load_json_crew_project`（来自 `json_loader.py`）解析项目结构，然后调用 `_load_crew_project` 将解析结果转换为 `Crew` 实例。返回 `(Crew, inputs)` 元组。

#### 2.4.2 `load_crew_from_definition` — 从内存定义加载

**源码位置**：`crew_loader.py`，第 40-60 行。

```python
# crew_loader.py 第 40-60 行
def load_crew_from_definition(
    definition: CrewDefinition | dict[str, Any],
    *, source: str | Path = "<inline crew>",
    project_root: str | Path | None = None,
) -> tuple[Any, dict[str, Any]]:
    root = Path(project_root) if project_root is not None else Path.cwd()
    crew_definition = (
        definition
        if isinstance(definition, CrewDefinition)
        else CrewDefinition.model_validate(definition)  # 第 52 行：字典 → CrewDefinition
    )
    definition_data = crew_definition.model_dump(mode="python", exclude_none=True)  # 第 54 行
    project = _crew_project_from_definition(definition_data, ...)  # 第 55-59 行
    return _load_crew_project(project, project_root=root)          # 第 60 行
```

**大白话**：接受 `CrewDefinition` 实例或字典，内部转换为 `CrewDefinition` → 构建 `JSONCrewProject` → 加载为 `Crew`。

#### 2.4.3 `_load_crew_project` — 核心转换逻辑

**源码位置**：`crew_loader.py`，第 92-166 行。

```python
# crew_loader.py 第 92-166 行
def _load_crew_project(project: JSONCrewProject, *, project_root: Path):
    from crewai import Crew, Task

    # 步骤 ①：构建 Agent 实例（第 101-115 行）
    def build_agent(agent_def: JSONAgentDefinition) -> Any:
        return agent_def.agent_class(**agent_def.kwargs)

    agents_map: dict[str, Any] = {}
    for name, agent_def in project.agents.items():
        agents_map[name] = build_agent(agent_def)       # 第 115 行

    # 步骤 ②：构建 Task 实例（第 117-146 行）
    tasks_list: list[Task] = []
    task_name_map: dict[str, Task] = {}
    for index, task_defn in enumerate(project.task_definitions):
        task_class = _task_class_from_definition(task_defn, ...)  # 第 122 行
        task_kwargs = _task_kwargs_from_definition(               # 第 127 行
            task_defn, agents_map=agents_map,
            task_name_map=task_name_map, ...
        )
        task = task_class(**task_kwargs)                          # 第 135 行
        tasks_list.append(task)
        task_name_map[task_name] = task                           # 第 146 行

    # 步骤 ③：构建 Crew 实例（第 148-164 行）
    crew_kwargs = _crew_kwargs_from_definition(
        project.definition,
        agents=[agents_map[name] for name in project.agent_names],
        tasks=tasks_list, agents_map=agents_map, ...
    )
    crew = Crew(**crew_kwargs)                                    # 第 158 行

    return crew, project.definition.get("inputs", {})             # 第 166 行
```

**大白话**：`_load_crew_project` 是核心转换函数，按顺序：① 构建 Agent 实例（调用 `agent_class(**kwargs)`），② 构建 Task 实例（解析 `agent` 引用、`context` 引用），③ 构建 Crew 实例。每一步都有错误处理，失败时抛出 `JSONProjectError`。

#### 2.4.4 `load_crew_and_kickoff` — 一键加载并执行

**源码位置**：`crew_loader.py`，第 169-180 行。

```python
# crew_loader.py 第 169-180 行
def load_crew_and_kickoff(
    crew_path: Path | str,
    input_overrides: dict[str, Any] | None = None,
) -> Any:
    crew, default_inputs = load_crew(crew_path)          # 第 174 行
    merged_inputs = {**default_inputs}                   # 第 176 行
    if input_overrides:
        merged_inputs.update(input_overrides)            # 第 178 行
    return crew.kickoff(inputs=merged_inputs)            # 第 180 行
```

---

### 2.5 Wrappers — 包装器类型

**源码位置**：`lib/crewai/src/crewai/project/wrappers.py`，第 1-420 行。

#### 2.5.1 `DecoratedMethod` — 基础包装器

**源码位置**：`wrappers.py`，第 157-226 行。

```python
# wrappers.py 第 157-226 行
class DecoratedMethod(Generic[P, R]):
    def __init__(self, meth: Callable[P, R]) -> None:
        self._meth = meth
        _copy_method_metadata(self, meth)  # 复制 __name__、__doc__

    def __get__(self, obj, objtype=None) -> Self | Callable[..., R]:
        if obj is None:
            return self                     # 类级别访问，返回自身
        inner = partial(self._meth, obj)    # 实例级别访问，绑定 self

        def _bound(*args, **kwargs) -> R:
            result = _resolve_result(inner(*args, **kwargs))
            return result

        # 复制标记属性到绑定函数
        for attr in ("is_agent", "is_llm", "is_tool", ...):
            if hasattr(self, attr):
                setattr(_bound, attr, getattr(self, attr))
        return _bound

    def __call__(self, *args, **kwargs) -> R:
        return self._meth(*args, **kwargs)

    def unwrap(self) -> Callable[P, R]:
        return self._meth
```

**大白话**：`DecoratedMethod` 实现了 Python 描述符协议（`__get__`），使得装饰器可以同时支持类级别和实例级别访问。当通过 `MyCrew.researcher` 访问时（`obj is None`），返回 `DecoratedMethod` 自身；当通过 `my_crew.researcher()` 访问时，返回一个绑定了 `self` 的 `_bound` 函数。

**关键**：`_bound` 函数会复制所有标记属性（`is_agent`、`is_llm` 等），这样 `hasattr(method, "is_agent")` 在绑定后的函数上仍然有效——这是 `_filter_methods` 和 `_initialize_crew_instance` 中检测标记的基础。

#### 2.5.2 `TaskMethod` — Task 专用包装器

**源码位置**：`wrappers.py`，第 270-333 行。

`TaskMethod` 不继承 `DecoratedMethod`，而是独立实现，因为它需要 `ensure_task_name` 和 `BoundTaskMethod` 绑定逻辑。

```python
# wrappers.py 第 270-333 行
class TaskMethod(Generic[P, TaskResultT]):
    is_task: bool = True

    def __init__(self, meth: Callable[P, TaskResultT]) -> None:
        self._meth = meth
        _copy_method_metadata(self, meth)

    def ensure_task_name(self, result: TaskResultT) -> TaskResultT:
        if not result.name:
            result.name = self._meth.__name__  # 用方法名填充 Task 名称
        return result

    def __get__(self, obj, objtype=None) -> Self | BoundTaskMethod[TaskResultT]:
        if obj is None:
            return self
        return BoundTaskMethod(self, obj)  # 返回绑定版本

    def __call__(self, *args, **kwargs) -> TaskResultT:
        result = self._meth(*args, **kwargs)
        result = _resolve_result(result)
        return self.ensure_task_name(result)
```

**大白话**：`TaskMethod` 的 `__call__` 和 `BoundTaskMethod.__call__` 都调用 `ensure_task_name`，确保 Task 的 `name` 不为空。如果用户创建 Task 时没设 `name`，就用方法名自动填充。

#### 2.5.3 `OutputClass` — 输出格式包装器

**源码位置**：`wrappers.py`，第 372-420 行。

```python
# wrappers.py 第 372-420 行
class OutputClass(Generic[T]):
    def __init__(self, cls: type[T]) -> None:
        self._cls = cls
        self.__name__ = cls.__name__
        self.__qualname__ = cls.__qualname__
        self.__module__ = cls.__module__
        self.__doc__ = cls.__doc__

    def __call__(self, *args, **kwargs) -> T:
        return self._cls(*args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._cls, name)
```

**大白话**：`OutputClass` 是一个代理包装器——它包装一个类，通过 `__getattr__` 将所有属性访问代理到原始类，同时添加 `is_output_json` 或 `is_output_pydantic` 标记。这使得 `Task(output_json=MyOutputClass)` 可以正常工作，`Task` 内部通过 `is_output_json` 标记判断类型。

#### 2.5.4 `CrewMetadata` — 元数据字典

**源码位置**：`wrappers.py`，第 31-42 行。

```python
# wrappers.py 第 31-42 行
class CrewMetadata(TypedDict):
    original_methods: dict[str, Callable[..., Any]]
    original_tasks: dict[str, Callable[..., Task]]
    original_agents: dict[str, Callable[..., Agent]]
    before_kickoff: dict[str, Callable[..., Any]]
    after_kickoff: dict[str, Callable[..., Any]]
    kickoff: dict[str, Callable[..., Any]]
```

**大白话**：这是一个 `TypedDict`，定义了 `instance.__crew_metadata__` 的结构。在 `_initialize_crew_instance`（`crew_base.py` 第 278-285 行）中构建。

#### 2.5.5 `CrewInstance` / `CrewClass` — Protocol

**源码位置**：`wrappers.py`，第 70-138 行。

```python
# wrappers.py 第 70-116 行
class CrewInstance(Protocol):
    __crew_metadata__: CrewMetadata
    _mcp_server_adapter: Any
    _all_methods: dict[str, Callable[..., Any]]
    agents: list[Agent]
    tasks: list[Task]
    base_directory: Path
    agents_config: dict[str, Any]
    tasks_config: dict[str, Any]
    ...

# wrappers.py 第 118-138 行
class CrewClass(Protocol):
    is_crew_class: bool
    _crew_name: str
    base_directory: Path
    ...
```

**大白话**：这两个 Protocol 定义了实例和类的接口契约，用于类型检查。它们不是基类，不需要继承，只是告诉类型检查器"这些属性/方法一定存在"。

#### 2.5.6 `memoize` — 缓存机制

**源码位置**：`lib/crewai/src/crewai/project/utils.py`，第 1-98 行。

```python
# utils.py 第 38-52 行
def memoize(meth: Callable[P, R]) -> Callable[P, R]:
    if inspect.iscoroutinefunction(meth):
        return cast(Callable[P, R], _memoize_async(meth))
    return _memoize_sync(meth)
```

**`_memoize_sync`**（`utils.py` 第 55-74 行）：

```python
# utils.py 第 55-74 行
def _memoize_sync(meth: Callable[P, R]) -> Callable[P, R]:
    @wraps(meth)
    def wrapper(*args, **kwargs):
        hashable_args = tuple(_make_hashable(arg) for arg in args)
        hashable_kwargs = tuple(sorted((k, _make_hashable(v)) for k, v in kwargs.items()))
        cache_key = str((hashable_args, hashable_kwargs))

        cached_result = cache.read(tool=meth.__name__, input=cache_key)
        if cached_result is not None:
            return cached_result

        result = meth(*args, **kwargs)
        cache.add(tool=meth.__name__, input=cache_key, output=result)
        return result
    return wrapper
```

**大白话**：`memoize` 是一个基于 `CacheHandler` 的方法级缓存。它通过 `_make_hashable` 将参数（包括 Pydantic 模型 → JSON 字符串、dict → 排序后的 tuple、list → tuple）转换为可哈希的键，然后用 `CacheHandler` 存储和检索。这确保了：

- `@agent` 方法不会重复创建 Agent 实例
- `@task` 方法不会重复创建 Task 实例
- `@crew` 方法不会重复创建 Crew 实例
- `@tool`、`@llm`、`@callback` 方法同理

**`_make_hashable`**（`utils.py` 第 18-35 行）处理各种参数类型：

```python
# utils.py 第 18-35 行
def _make_hashable(arg: Any) -> Any:
    if isinstance(arg, BaseModel):
        return arg.model_dump_json()          # Pydantic → JSON 字符串
    if isinstance(arg, dict):
        return tuple(sorted(...))              # dict → 排序后的 tuple
    if isinstance(arg, list):
        return tuple(_make_hashable(item) ...)  # list → tuple
    if hasattr(arg, "__dict__"):
        return ("__instance__", id(arg))       # 自定义对象 → 对象 ID
    return arg
```

---

## 3. 完整调用时序图

```
用户代码                  CrewBaseMeta          crew_base.py       annotations.py     wrappers.py       utils.py
   │                         │                      │                    │                 │                │
   │  @CrewBase              │                      │                    │                 │                │
   │  class MyCrew:          │                      │                    │                 │                │
   │───── 类定义 ───────────►│                      │                    │                 │                │
   │                         │ __new__()            │                    │                 │                │
   │                         │──────┐               │                    │                 │                │
   │                         │     │ _set_base_directory()               │                 │                │
   │                         │     │ _set_config_paths()                 │                 │                │
   │                         │     │ _set_mcp_params()                   │                 │                │
   │                         │     │ setattr(cls, method.__name__, ...)  │                 │                │
   │                         │◄────┘               │                    │                 │                │
   │                         │                      │                    │                 │                │
   │  my_crew = MyCrew()     │                      │                    │                 │                │
   │──────── 实例化 ────────►│                      │                    │                 │                │
   │                         │ __call__()           │                    │                 │                │
   │                         │──────┐               │                    │                 │                │
   │                         │     │ super().__call__() → 创建实例       │                 │                │
   │                         │     │ _initialize_crew_instance()         │                 │                │
   │                         │     │──────┐          │                    │                 │                │
   │                         │     │     │ load_configurations()          │                 │                │
   │                         │     │     │   → load_yaml() → agents_config, tasks_config
   │                         │     │     │ _get_all_methods() → _all_methods
   │                         │     │     │ map_all_agent_variables()      │                 │                │
   │                         │     │     │   → _filter_methods(is_llm)   │                 │                │
   │                         │     │     │   → _filter_methods(is_tool)  │                 │                │
   │                         │     │     │   → _map_agent_variables()    │                 │                │
   │                         │     │     │     → llm字符串 → factory()   │                 │                │
   │                         │     │     │     → tool字符串 → factory()  │                 │                │
   │                         │     │     │ map_all_task_variables()       │                 │                │
   │                         │     │     │   → agent字符串 → factory()   │                 │                │
   │                         │     │     │   → context字符串 → factory() │                 │                │
   │                         │     │     │ 构建 __crew_metadata__         │                 │                │
   │                         │     │     │ _register_crew_hooks()         │                 │                │
   │                         │     │◄────┘          │                    │                 │                │
   │                         │◄────┘               │                    │                 │                │
   │◄── 返回 my_crew ────────│                      │                    │                 │                │
   │                         │                      │                    │                 │                │
   │  crew = my_crew.crew()  │                      │                    │                 │                │
   │─────────────────────────┼──────────────────────┼───────────────────►│                 │                │
   │                         │                      │                    │ wrapper()       │                │
   │                         │                      │                    │──────┐          │                │
   │                         │                      │                    │     │ 遍历 original_tasks     │                │
   │                         │                      │                    │     │   → _call_method(task_method, self)
   │                         │                      │                    │     │     → Task实例         │                │
   │                         │                      │                    │     │     → 提取 agent       │                │
   │                         │                      │                    │     │ 遍历 original_agents   │                │
   │                         │                      │                    │     │   → _call_method(agent_method, self)
   │                         │                      │                    │     │     → Agent实例(去重)  │                │
   │                         │                      │                    │     │ self.agents/tasks = ...│                │
   │                         │                      │                    │     │ _call_method(meth, self)│               │
   │                         │                      │                    │     │   → Crew实例         │                │
   │                         │                      │                    │     │ 注册 before/after 回调│                │
   │                         │                      │                    │     │ memoize → cache     │────────────────►│
   │                         │                      │                    │◄────┘          │                │ memoize()
   │◄── 返回 Crew ───────────┼──────────────────────┼───────────────────│                 │                │
   │                         │                      │                    │                 │                │
   │  crew.kickoff()         │                      │                    │                 │                │
   │─────────────────────────┼──────────────────────┼───────────────────│                 │                │
   │                         │                      │ before_kickoff_callbacks               │                │
   │                         │                      │   → 执行钩子方法                      │                │
   │                         │                      │ 执行任务...                           │                │
   │                         │                      │ after_kickoff_callbacks                │                │
   │                         │                      │   → close_mcp_server()                │                │
   │◄── 返回 CrewOutput ─────│                      │                    │                 │                │
```

---

## 4. 完整可运行示例

### 4.1 示例一：基础 @CrewBase 装饰器用法

```python
"""示例一：使用 @CrewBase 装饰器定义 Crew — 最简用法"""
import os
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task

# 设置环境变量（实际使用时替换为你的 API Key）
os.environ["OPENAI_API_KEY"] = "sk-your-key"

@CrewBase
class ResearchCrew:
    """一个简单的研究 Crew"""

    agents_config = "config/agents.yaml"   # 可省略，这是默认值
    tasks_config = "config/tasks.yaml"     # 可省略，这是默认值

    @agent
    def researcher(self) -> Agent:
        """创建研究员 Agent"""
        return Agent(
            role="Research Analyst",
            goal="Research {topic} thoroughly",
            backstory="Expert researcher with years of experience",
            verbose=True,
        )

    @agent
    def writer(self) -> Agent:
        """创建写手 Agent"""
        return Agent(
            role="Content Writer",
            goal="Write a compelling report on {topic}",
            backstory="Skilled writer with attention to detail",
            verbose=True,
        )

    @task
    def research_task(self) -> Task:
        """创建研究任务"""
        return Task(
            description="Research the topic: {topic}",
            expected_output="Detailed research notes on {topic}",
            agent=self.researcher(),
        )

    @task
    def writing_task(self) -> Task:
        """创建写作任务"""
        return Task(
            description="Write a report based on the research",
            expected_output="A well-written report",
            agent=self.writer(),
        )

    @crew
    def crew(self) -> Crew:
        """组装 Crew"""
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
        )


# 运行
if __name__ == "__main__":
    my_crew = ResearchCrew()
    result = my_crew.crew().kickoff(inputs={"topic": "AI safety"})
    print(result)
```

**运行说明**：

1. 在类文件所在目录下创建 `config/agents.yaml` 和 `config/tasks.yaml`（可以为空文件 `{}`，因为示例中 Agent 和 Task 都是直接在代码中定义的）。
2. 设置 `OPENAI_API_KEY` 环境变量。
3. 运行 `python example.py`。

**关键点说明**：

- `@CrewBase` 装饰器触发 `CrewBaseMeta` 元类，在类创建时设置 `base_directory`、配置路径等。
- `@agent` 和 `@task` 装饰器将方法标记为特定角色，并启用 memoize 缓存。
- `@crew` 装饰器的 wrapper 自动实例化所有 Task 和 Agent，然后调用用户方法。
- `self.agents` 和 `self.tasks` 在 `@crew` wrapper 中被自动赋值。

### 4.2 示例二：YAML 配置驱动 + 变量映射

```python
"""示例二：使用 YAML 配置文件驱动 Agent 和 Task 定义"""
import os
from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, llm, task, tool

os.environ["OPENAI_API_KEY"] = "sk-your-key"


@CrewBase
class YAMLDrivenCrew:
    """用 YAML 配置管理 Crew 的示例"""

    # 类定义与 YAML 文件同目录
    # config/agents.yaml:
    #   researcher:
    #     role: "Research Analyst"
    #     goal: "Research {topic}"
    #     backstory: "Expert researcher"
    #     llm: "gpt4_llm"           # ← 字符串引用
    #     tools:                    # ← 字符串引用列表
    #       - "web_search"
    #   writer:
    #     role: "Content Writer"
    #     goal: "Write about {topic}"
    #     backstory: "Skilled writer"
    #     llm: "gpt4_llm"
    #
    # config/tasks.yaml:
    #   research_task:
    #     description: "Research {topic}"
    #     expected_output: "Research notes"
    #     agent: "researcher"        # ← 字符串引用
    #   writing_task:
    #     description: "Write report"
    #     expected_output: "Report"
    #     agent: "writer"

    @llm
    def gpt4_llm(self) -> LLM:
        """LLM 工厂方法 — 被 YAML 中的 llm: 'gpt4_llm' 引用"""
        return LLM(model="gpt-4o-mini")

    @tool
    def web_search(self) -> object:
        """工具工厂方法 — 被 YAML 中的 tools: ['web_search'] 引用"""
        from crewai_tools import SerperDevTool

        return SerperDevTool()

    @agent
    def researcher(self) -> Agent:
        """从 YAML 配置创建 researcher Agent"""
        return Agent(
            config=self.agents_config["researcher"],  # ← 从 YAML 加载
        )

    @agent
    def writer(self) -> Agent:
        """从 YAML 配置创建 writer Agent"""
        return Agent(
            config=self.agents_config["writer"],
        )

    @task
    def research_task(self) -> Task:
        """从 YAML 配置创建 research Task"""
        return Task(
            config=self.tasks_config["research_task"],
        )

    @task
    def writing_task(self) -> Task:
        """从 YAML 配置创建 writing Task"""
        return Task(
            config=self.tasks_config["writing_task"],
        )

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
        )


if __name__ == "__main__":
    my_crew = YAMLDrivenCrew()
    # 此时 load_configurations() 已自动执行
    # agents_config["researcher"]["llm"] 是字符串 "gpt4_llm"
    # map_all_agent_variables() 将其替换为 gpt4_llm() 的返回值
    # agents_config["researcher"]["tools"] 是 ["web_search"]
    # map_all_agent_variables() 将其替换为 [web_search()]

    # agents_config["researcher"]["llm"] 现在是一个 LLM 实例
    print(type(my_crew.agents_config["researcher"]["llm"]))
    # <class 'crewai.llm.LLM'>

    result = my_crew.crew().kickoff(inputs={"topic": "AI safety"})
    print(result)
```

**运行说明**：

1. 在脚本同目录创建 `config/agents.yaml` 和 `config/tasks.yaml`（内容见代码注释）。
2. 安装 `crewai_tools` 或替换 `SerperDevTool` 为其他工具。
3. 设置环境变量并运行。

**关键点说明**：

- YAML 中的 `llm: "gpt4_llm"` 是字符串引用。`map_all_agent_variables()` 会查找 `@llm` 装饰的方法（`is_llm = True`），找到 `gpt4_llm` 后调用它，用返回值替换字符串。
- YAML 中的 `tools: ["web_search"]` 同理，`map_all_agent_variables()` 调用 `_is_string_list()` 类型守卫确认是字符串列表后，逐个调用对应的 `@tool` 方法。
- YAML 中的 `agent: "researcher"` 在 `map_all_task_variables()` 中被解析为 `agents["researcher"]()` 的返回值。

### 4.3 示例三：before_kickoff / after_kickoff 生命周期钩子

```python
"""示例三：使用 before_kickoff 和 after_kickoff 钩子"""
import os
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, after_kickoff, agent, before_kickoff, crew, task

os.environ["OPENAI_API_KEY"] = "sk-your-key"


@CrewBase
class HookedCrew:
    """演示生命周期钩子的 Crew"""

    @before_kickoff
    def log_start(self, inputs: dict) -> None:
        """在 Crew 执行前记录日志"""
        print(f"[BEFORE KICKOFF] Starting crew with inputs: {inputs}")

    @before_kickoff
    def validate_inputs(self, inputs: dict) -> None:
        """在 Crew 执行前验证输入"""
        if "topic" not in inputs:
            raise ValueError("Missing required input: 'topic'")
        print(f"[BEFORE KICKOFF] Input validation passed for topic: {inputs['topic']}")

    @after_kickoff
    def log_completion(self, outputs) -> None:
        """在 Crew 执行后记录日志"""
        print(f"[AFTER KICKOFF] Crew completed! Raw output: {outputs.raw[:100]}...")

    @after_kickoff
    def close_mcp_server(self, instance, outputs):
        """MCP 清理（框架自动注册，这里展示可自定义）"""
        print("[AFTER KICKOFF] Cleaning up resources...")
        return outputs

    @agent
    def researcher(self) -> Agent:
        return Agent(
            role="Researcher",
            goal="Research {topic}",
            backstory="Expert researcher",
            verbose=True,
        )

    @task
    def research_task(self) -> Task:
        return Task(
            description="Research {topic}",
            expected_output="Research notes",
            agent=self.researcher(),
        )

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
        )


if __name__ == "__main__":
    my_crew = HookedCrew()
    result = my_crew.crew().kickoff(inputs={"topic": "quantum computing"})
    print(f"\nFinal result: {result.raw}")
```

**运行说明**：直接运行即可。观察输出中 `[BEFORE KICKOFF]` 和 `[AFTER KICKOFF]` 的打印顺序。

**关键点说明**：

- `@before_kickoff` 方法接收 `inputs` 参数（`crew.kickoff(inputs=...)` 传入的输入），返回 `None`。
- `@after_kickoff` 方法接收 `outputs` 参数（`CrewOutput` 实例），必须返回 `outputs`（或修改后的 `outputs`）。
- 这两个钩子**不经过 memoize**，每次执行都会真正运行。
- 框架自动注册 `close_mcp_server` 为 after_kickoff 回调（`crew_base.py` 第 276 行）。

### 4.4 示例四：声明式 Crew 定义（JSON 方式）

```python
"""示例四：使用 CrewDefinition 声明式定义 Crew（纯 JSON/字典）"""
import os
from crewai.project.crew_loader import load_crew_from_definition

os.environ["OPENAI_API_KEY"] = "sk-your-key"

# 纯字典定义的 Crew — 不需要任何 Python 类
crew_definition = {
    "agents": {
        "researcher": {
            "role": "Research Analyst",
            "goal": "Research {topic} thoroughly",
            "backstory": "Expert researcher with 10 years of experience",
            "llm": "gpt-4o-mini",
            "allow_delegation": False,
            "verbose": True,
        },
        "writer": {
            "role": "Content Writer",
            "goal": "Write a compelling report about {topic}",
            "backstory": "Professional writer with attention to detail",
            "llm": "gpt-4o-mini",
            "verbose": True,
        },
    },
    "tasks": [
        {
            "name": "research_task",
            "description": "Research the topic: {topic}",
            "expected_output": "Detailed research notes",
            "agent": "researcher",
        },
        {
            "name": "writing_task",
            "description": "Write a report based on the research",
            "expected_output": "A well-written report in markdown format",
            "agent": "writer",
            "context": ["research_task"],  # ← 依赖 research_task 的输出
        },
    ],
    "inputs": {
        "topic": "AI safety",
    },
    "process": "sequential",
}

if __name__ == "__main__":
    # 从内存定义加载 Crew
    crew, default_inputs = load_crew_from_definition(crew_definition)

    print(f"Default inputs: {default_inputs}")
    # Default inputs: {'topic': 'AI safety'}

    print(f"Crew agents: {[a.role for a in crew.agents]}")
    # Crew agents: ['Research Analyst', 'Content Writer']

    print(f"Crew tasks: {len(crew.tasks)} tasks")
    # Crew tasks: 2 tasks

    # 执行 Crew
    result = crew.kickoff(inputs={"topic": "quantum computing"})
    print(f"\nResult: {result.raw}")
```

**运行说明**：直接运行。不需要任何 YAML 文件或类定义——所有配置都在字典中。

**关键点说明**：

- `load_crew_from_definition` 接受字典或 `CrewDefinition` 实例。
- 内部流程：字典 → `CrewDefinition.model_validate()` → `_crew_project_from_definition()` → `_load_crew_project()` → `Crew` 实例。
- `context: ["research_task"]` 表示 writing_task 依赖 research_task 的输出，CrewAI 会自动处理任务间的依赖顺序。
- `inputs` 字段定义了默认输入，可以在 `kickoff(inputs=...)` 中覆盖。

### 4.5 示例五：output_json / output_pydantic 输出格式

```python
"""示例五：使用 output_json 和 output_pydantic 定义输出格式"""
import os
from pydantic import BaseModel, Field
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, output_json, output_pydantic, task

os.environ["OPENAI_API_KEY"] = "sk-your-key"


# 定义 JSON 输出格式（使用 @output_json 类装饰器）
@output_json
class ResearchReport:
    """研究报告的输出格式"""
    topic: str
    findings: list[str]
    conclusion: str


# 定义 Pydantic 输出格式（使用 @output_pydantic 类装饰器）
@output_pydantic
class WritingReport(BaseModel):
    """写作报告的输出格式"""
    title: str = Field(description="报告标题")
    summary: str = Field(description="报告摘要")
    key_points: list[str] = Field(description="关键要点")
    word_count: int = Field(description="字数统计")


@CrewBase
class OutputFormatCrew:
    """使用输出格式的 Crew"""

    @agent
    def researcher(self) -> Agent:
        return Agent(
            role="Research Analyst",
            goal="Research {topic}",
            backstory="Expert researcher",
            verbose=True,
        )

    @agent
    def writer(self) -> Agent:
        return Agent(
            role="Content Writer",
            goal="Write about {topic}",
            backstory="Professional writer",
            verbose=True,
        )

    @task
    def research_task(self) -> Task:
        return Task(
            description="Research {topic}",
            expected_output="Research findings",
            agent=self.researcher(),
            output_json=ResearchReport,  # ← 使用 @output_json 类
        )

    @task
    def writing_task(self) -> Task:
        return Task(
            description="Write a report about {topic}",
            expected_output="A structured report",
            agent=self.writer(),
            output_pydantic=WritingReport,  # ← 使用 @output_pydantic 类
        )

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
        )


if __name__ == "__main__":
    my_crew = OutputFormatCrew()
    result = my_crew.crew().kickoff(inputs={"topic": "AI safety"})

    # 访问 Pydantic 输出
    print(f"Pydantic output: {result.pydantic}")
    # 访问 JSON 输出
    print(f"JSON output: {result.json_dict}")
    print(f"Raw output: {result.raw}")
```

**运行说明**：直接运行。注意 `ResearchReport` 是普通类（使用 `@output_json`），`WritingReport` 是 Pydantic 模型（使用 `@output_pydantic`）。

**关键点说明**：

- `@output_json` 返回 `OutputJsonClass` 包装器，有 `is_output_json = True` 标记。
- `@output_pydantic` 返回 `OutputPydanticClass` 包装器，有 `is_output_pydantic = True` 标记。
- 在 `map_all_task_variables` 中，`output_json` 和 `output_pydantic` 字段保持为类本身（不调用），直接传给 Task 构造函数。
- `OutputClass` 通过 `__getattr__` 代理所有属性访问到原始类，所以 `ResearchReport.topic` 等属性仍然可用。

---

## 5. 设计亮点与注意事项

### 5.1 设计亮点

1. **元类 + 装饰器分离设计**：`CrewBaseMeta` 元类负责"类创建时"的行为（`__new__`）和"实例化时"的行为（`__call__`），装饰器（`@agent`、`@task` 等）负责"方法标注"。两者职责清晰，互不干扰。

2. **描述符协议实现绑定**：`DecoratedMethod.__get__` 和 `TaskMethod.__get__` 实现了 Python 描述符协议，使得装饰器方法在类级别和实例级别都能正确工作。绑定后的函数会复制标记属性（`is_agent` 等），确保 `hasattr(method, "is_agent")` 在实例方法上仍然可用。

3. **memoize 缓存避免重复创建**：`@agent`、`@task`、`@crew`、`@tool`、`@llm` 等方法都经过 `memoize` 包装。相同参数只会创建一次实例，既提升性能又避免副作用（如多次创建 Agent 导致 token 消耗）。

4. **YAML → 实例的自动映射**：`map_all_agent_variables` 和 `map_all_task_variables` 将 YAML 配置中的字符串引用自动解析为实际实例。配合类型守卫（`_is_string_list`、`_is_string_value`），既支持字符串引用也支持直接传入实例。

5. **声明式 Crew 定义**：`CrewDefinition` + `CrewLoader` 提供了一条完全不需要 Python 代码的 Crew 定义路径。JSON/YAML 配置可以直接转换为可运行的 `Crew` 实例，适合低代码场景。

6. **Hook 系统集成**：`_register_crew_hooks` 将 Crew 类中的 Hook 方法自动注册到全局 Hook 系统，支持 `@filter_agents` 和 `@filter_tools` 过滤，实现精细的 Hook 控制。

7. **MCP 生命周期管理**：`close_mcp_server` 自动注册为 after_kickoff 回调，`get_mcp_tools` 支持懒加载 MCP 工具，MCP 服务器参数通过 `_set_mcp_params` 在类创建时自动设置。

8. **Protocol 类型安全**：`CrewInstance` Protocol 和 `CrewClass` Protocol 提供了完整的类型注解，IDE 和类型检查器可以验证 `@CrewBase` 装饰类的接口契约。

### 5.2 注意事项

1. **`__new__` 执行时机**：`CrewBaseMeta.__new__` 在类**定义时**就执行，不是实例化时。这意味着 `base_directory` 在模块加载时就确定了。如果类定义在临时文件中，`inspect.getfile(cls)` 可能抛出 `TypeError`（回退到 `Path.cwd()`）。

2. **memoize 的副作用**：`@agent`、`@task` 等方法被 memoize 后，**相同参数只会执行一次**。如果你需要在每次调用时创建新实例（例如用不同的 LLM 配置），需要传入不同的参数来打破缓存。如果需要强制刷新，需要手动清除 `CacheHandler` 中的缓存。

3. **YAML 配置路径**：`config/agents.yaml` 和 `config/tasks.yaml` 的路径是相对于 `base_directory`（类文件所在目录）的。如果类文件在子包中，配置路径需要相应调整。

4. **字符串引用的命名一致性**：YAML 中的 `llm: "gpt4_llm"` 引用的名字必须与 `@llm` 方法的**方法名**（`__name__`）一致。同样，`agent: "researcher"` 必须与 `@agent` 方法名一致。名字不匹配会导致 `KeyError`。

5. **`@crew` 中 Agent 的去重**：`@crew` wrapper 中通过 `agent_roles` 集合去重 Agent。如果两个 Agent 有相同的 `role`，后者会被跳过。这可能导致意外的 Agent 丢失——确保每个 Agent 有唯一的 `role`。

6. **`CrewDefinition` 的验证**：`_validate_inline_shape` 在 `model_validator(mode="after")` 中执行，确保 `agents` 和 `tasks` 非空。如果传入空的 `agents` 或 `tasks`，会抛出 `ValueError`。

7. **`load_crew` 的返回值**：`load_crew` 和 `load_crew_from_definition` 返回 `(Crew, dict)` 元组，第二个元素是 `inputs` 默认值。不要忘记解包。

8. **`_call_method` 的异步处理**：`_call_method` 在事件循环运行时使用 `ThreadPoolExecutor` 执行异步方法。如果异步方法依赖线程局部变量，可能会有问题。

9. **`OutputClass` 的代理陷阱**：`OutputClass.__getattr__` 代理所有属性访问到原始类，但如果原始类有 `__slots__`，某些属性可能无法通过 `getattr` 访问。

10. **装饰器顺序**：`@CrewBase` 必须是最外层装饰器。`@agent`、`@task`、`@crew` 等装饰器的顺序不重要，因为它们只设置标记属性，不修改方法签名。