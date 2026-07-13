# 阶段九：Memory 记忆系统 — 源码深度解析

---

## 1. 模块定位

### 1.1 一句话概括

**Memory 记忆系统是 CrewAI 的智能记忆层，基于「统一记忆入口 + LLM 分析 + 向量存储 + 自适应深度召回」架构，实现了记忆的自动分类、重要性推断、语义检索和范围隔离，让 Agent 具备跨会话的长期记忆能力。**

### 1.2 在整体架构中的位置

```
Agent/Crew 配置 memory=True
    │
    ▼
Memory (统一记忆入口)
    ├── remember(content)         ← 记忆保存（LLM 分析 → 向量化 → 存储）
    │   ├── LLM 分析：提取 scope、categories、importance
    │   ├── embedder.embed(content) → 向量
    │   └── StorageBackend.save(record) → LanceDB/ChromaDB
    │
    ├── recall(query)             ← 记忆召回（自适应深度检索）
    │   ├── shallow: 简单向量搜索
    │   └── deep: RecallFlow → LLM 查询分析 → 多轮探索
    │
    ├── forget(scope)             ← 记忆遗忘
    └── MemoryScope / MemorySlice ← 范围隔离视图
```

### 1.3 本阶段涉及的核心源码文件

| 文件 | 核心职责 |
|------|----------|
| `memory/unified_memory.py` | 统一记忆主类：remember、recall、forget、LLM 分析 |
| `memory/memory_scope.py` | 范围隔离视图：MemoryScope / MemorySlice |
| `memory/recall_flow.py` | 自适应深度召回流程：RLM 风格的多轮探索 |
| `memory/analyze.py` | 记忆分析：提取 memories、分析查询 |
| `memory/encoding_flow.py` | 编码流水线：批量记忆处理 |
| `memory/storage/backend.py` | 存储后端协议：StorageBackend Protocol |
| `memory/storage/lancedb_storage.py` | LanceDB 存储实现（默认） |
| `memory/types.py` | 类型定义：MemoryRecord、MemoryMatch、MemoryConfig |

---

## 2. 源码分层拆解

### 2.1 第一层：Memory（统一记忆入口）

**文件：** `lib/crewai/src/crewai/memory/unified_memory.py`

#### 2.1.1 核心配置

```python
class Memory(BaseModel):
    """统一记忆：独立运行，LLM 分析，智能召回。"""

    memory_kind: Literal["memory"] = "memory"
    llm: BaseLLM | str = "gpt-5.4-mini"  # 分析用 LLM
    storage: StorageBackend | str = "lancedb"  # 存储后端
    embedder: Any = None  # Embedding 函数

    # 复合评分权重
    recency_weight: float = 0.3       # 时间权重
    semantic_weight: float = 0.5      # 语义权重
    importance_weight: float = 0.2    # 重要性权重

    # 召回阈值
    recency_half_life_days: int = 30  # 记忆衰减半衰期
    consolidation_threshold: float = 0.85  # 去重合并阈值
    consolidation_limit: int = 5      # 去重时比较的最大记录数

    # 自适应召回配置
    confidence_threshold_high: float = 0.8   # 高置信度直接返回
    confidence_threshold_low: float = 0.5    # 低置信度深入探索
    exploration_budget: int = 1              # 探索轮数

    read_only: bool = False           # 只读模式
    root_scope: str | None = None     # 根范围前缀
```

#### 2.1.2 remember() — 记忆保存

```python
def remember(self, content, scope=None, categories=None, metadata=None,
             importance=None, source=None, private=False) -> MemoryRecord | None:
    """保存一条记忆到存储。"""
    # 1. 只读模式跳过
    if self.read_only:
        return None

    # 2. LLM 分析：提取 scope、categories、importance
    analysis = self._analyze_content(content)

    # 3. 构建 MemoryRecord
    record = MemoryRecord(
        content=content,
        scope=analysis.scope or scope or "/",
        categories=analysis.categories or categories or [],
        importance=analysis.importance or importance or self.default_importance,
        timestamp=datetime.now(timezone.utc),
        metadata=metadata or {},
        source=source,
        private=private,
    )

    # 4. 去重检查（consolidation）
    if not self._should_consolidate(record):
        return None

    # 5. 向量化 + 异步保存
    record.embedding = self._embedder.embed(content)
    self._save_async(record)

    # 6. 发射 MemorySaveCompletedEvent
    crewai_event_bus.emit(self, MemorySaveCompletedEvent(...))

    return record
```

#### 2.1.3 recall() — 记忆召回

```python
def recall(self, query, scope=None, categories=None, limit=10,
           depth="deep", source=None, include_private=False) -> list[MemoryMatch]:
    """召回相关记忆。"""
    # 1. 发射 MemoryQueryStartedEvent

    if depth == "shallow":
        # 浅层检索：直接向量搜索
        results = self._shallow_recall(query, scope, categories, limit)
    else:
        # 深度检索：RecallFlow 多轮探索
        recall_flow = RecallFlow(self._storage, self._llm, self._embedder)
        results = recall_flow.run(query, scope, categories, limit)

    # 2. 计算复合评分
    scored = [
        MemoryMatch(
            record=r,
            score=compute_composite_score(r, query, self._config),
        )
        for r in results
    ]

    # 3. 发射 MemoryQueryCompletedEvent
    return sorted(scored, key=lambda m: m.score, reverse=True)[:limit]
```

**复合评分公式：**

```
composite_score = recency_weight * recency_score
                + semantic_weight * semantic_score
                + importance_weight * importance_score

其中 recency_score = 2^(-days_since / recency_half_life_days)
```

---

### 2.2 第二层：MemoryScope（范围隔离视图）

**文件：** `lib/crewai/src/crewai/memory/memory_scope.py`

```python
class MemoryScope(BaseModel):
    """将 Memory 限制在特定 root_path 下的视图。"""
    memory_kind: Literal["scope"] = "scope"
    root_path: str = "/"  # 根路径

    def remember(self, content, scope="/", **kwargs):
        path = self._scope_path(scope)  # 拼接为 /root_path/scope
        return self._memory.remember(content, scope=path, **kwargs)

    def recall(self, query, scope=None, **kwargs):
        search_scope = self._scope_path(scope) if scope else self._root
        return self._memory.recall(query, scope=search_scope, **kwargs)
```

**大白话：** MemoryScope 相当于 Linux 的 `chroot`——把 Agent 的记忆限制在 `/crew/research` 下，Agent 只能看到该范围内的记忆，实现多 Agent 记忆隔离。

---

### 2.3 第三层：RecallFlow（自适应深度召回）

**文件：** `lib/crewai/src/crewai/memory/recall_flow.py`

```python
class RecallFlow(Flow[RecallState]):
    """RLM 风格的智能记忆召回流程。"""

    @start()
    def analyze_query(self):
        """LLM 分析查询，生成子查询 + 时间过滤 + 候选范围。"""
        self.state.query_analysis = analyze_query(self.state.query, self._llm)
        # 生成子查询: 原始查询 → ["CrewAI 执行策略", "Sequential vs Hierarchical"]

    @listen(analyze_query)
    def embed_and_search(self):
        """对每个子查询进行向量化 + 并行搜索。"""
        # 1. 向量化所有子查询
        embeddings = embed_texts(sub_queries)

        # 2. 并行搜索（线程池）
        with ThreadPoolExecutor() as pool:
            futures = [pool.submit(self._do_search, emb, scope) for emb in embeddings]

        # 3. 合并结果
        self.state.chunk_findings = merge_results(futures)

    @router(embed_and_search)
    def route_by_confidence(self):
        """根据置信度决定是否继续探索。"""
        if self.state.confidence >= self._config.confidence_threshold_high:
            return "done"  # 高置信度 → 直接返回
        elif self.state.confidence < self._config.confidence_threshold_low:
            return "explore"  # 低置信度 → 深入探索
        return "done"

    @listen("explore")
    def deep_explore(self):
        """深入探索：LLM 生成新查询 → 搜索 → 评估。"""
        # 预算控制
        for _ in range(self._config.exploration_budget):
            new_queries = self._llm.generate_followups(self.state.evidence_gaps)
            # 搜索...
            # 重新评估置信度...
```

---

### 2.4 第四层：StorageBackend（存储后端协议）

**文件：** `lib/crewai/src/crewai/memory/storage/backend.py`

```python
@runtime_checkable
class StorageBackend(Protocol):
    """可插拔存储后端协议。"""

    def save(self, records: list[MemoryRecord]) -> None: ...
    def search(self, query_embedding, scope_prefix=None, categories=None,
               limit=10, min_score=0.0) -> list[tuple[MemoryRecord, float]]: ...
    def delete(self, scope_prefix=None, categories=None, record_ids=None,
               older_than=None, metadata_filter=None) -> int: ...
    def list_scopes(self, prefix="/") -> list[str]: ...
    def info(self, prefix="/") -> ScopeInfo: ...
```

**支持的后端：**
- **LanceDB**（默认）：嵌入式列式向量数据库，零配置
- **ChromaDB**：通过 Adapter 支持
- **Qdrant**：`qdrant_edge_storage.py`
- **自定义**：实现 `StorageBackend` Protocol 即可

---

## 3. 完整调用时序图

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        Memory 记忆系统完整时序                             │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  1. 初始化                                                                 │
│     memory = Memory(                                                      │
│         llm="gpt-4o-mini",         ← 分析用 LLM                          │
│         storage="lancedb",         ← 存储后端（LanceDB 默认）             │
│         embedder={"provider": "openai"},                                  │
│     )                                                                     │
│     │                                                                      │
│     ├── 构建 embedder: build_embedder({"provider": "openai"})             │
│     ├── 初始化 StorageBackend: LanceDB(path)                              │
│     └── 创建后台保存线程池: ThreadPoolExecutor(max_workers=1)              │
│                                                                           │
│  2. 记忆保存（remember）                                                    │
│     memory.remember("CrewAI 支持 Sequential 和 Hierarchical 两种策略")     │
│     │                                                                      │
│     ├── 发射 MemorySaveStartedEvent                                        │
│     │                                                                      │
│     ├── LLM 分析内容                                                        │
│     │   ├── 推断 scope: "/crewai/execution"                                │
│     │   ├── 推断 categories: ["framework", "execution_strategy"]           │
│     │   └── 推断 importance: 0.8                                           │
│     │                                                                      │
│     ├── 去重检查（consolidation）                                           │
│     │   ├── 搜索已有记录（相似度 > 0.85）                                   │
│     │   ├── 找到相似记录 → 更新（合并重要性）                               │
│     │   └── 未找到 → 创建新记录                                            │
│     │                                                                      │
│     ├── embedder.embed(content) → 向量 [0.12, -0.34, ...]                  │
│     │                                                                      │
│     ├── 异步保存（后台线程池）                                              │
│     │   └── StorageBackend.save([MemoryRecord(...)])                       │
│     │                                                                      │
│     └── 发射 MemorySaveCompletedEvent                                      │
│                                                                           │
│  3. 记忆召回（recall）                                                      │
│     memory.recall("CrewAI 有哪些执行策略?")                                 │
│     │                                                                      │
│     ├── 发射 MemoryQueryStartedEvent                                       │
│     │                                                                      │
│     ├── [深度模式] RecallFlow.run()                                        │
│     │   ├── analyze_query() → LLM 分析查询                                 │
│     │   │   ├── 子查询: ["CrewAI 执行策略", "Sequential", "Hierarchical"]  │
│     │   │   ├── 时间过滤: None                                             │
│     │   │   └── 候选范围: ["/crewai/execution"]                            │
│     │   │                                                                  │
│     │   ├── embed_and_search() → 并行搜索                                  │
│     │   │   ├── embed_texts(sub_queries) → 3 个向量                        │
│     │   │   ├── ThreadPoolExecutor 并行搜索                                │
│     │   │   └── 合并结果 → chunk_findings                                  │
│     │   │                                                                  │
│     │   ├── route_by_confidence()                                          │
│     │   │   ├── confidence >= 0.8 → "done"                                 │
│     │   │   ├── confidence < 0.5 → "explore"                               │
│     │   │   └── 否则 → "done"                                              │
│     │   │                                                                  │
│     │   └── [可选] deep_explore() → 多轮探索                                │
│     │                                                                      │
│     ├── 计算复合评分                                                        │
│     │   └── composite_score = 0.3*recency + 0.5*semantic + 0.2*importance │
│     │                                                                      │
│     └── 发射 MemoryQueryCompletedEvent                                     │
│                                                                           │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 4. 核心设计亮点

### 4.1 LLM 驱动的记忆分析

保存记忆时自动调用 LLM 分析内容，提取：
- **scope**（范围）：自动分类到 `/crewai/execution`、`/agent/researcher` 等
- **categories**（类别）：自动打标签
- **importance**（重要性）：0.0-1.0 的评分

### 4.2 复合评分机制

```python
score = recency_weight * recency + semantic_weight * semantic + importance_weight * importance
```

通过加权组合三个维度，新近且重要的记忆排前面，避免"旧记忆淹没"。

### 4.3 记忆去重合并（Consolidation）

```python
consolidation_threshold = 0.85  # 相似度 > 85% 视为重复
```

保存新记忆时，先搜索相似记录，如果相似度超过 85% 则合并（更新重要性），避免重复。

### 4.4 自适应深度召回（RecallFlow）

- **shallow**：简单向量搜索，速度快
- **deep**：LLM 分析查询 → 生成子查询 → 并行搜索 → 置信度评估 → 可能多轮探索

### 4.5 可插拔存储后端

通过 `StorageBackend` Protocol 实现，默认 LanceDB（零配置、嵌入式），支持 ChromaDB、Qdrant 等。

---

## 5. 生产落地拓展改造

### 5.1 持久化到 PostgreSQL（pgvector）

```python
class PgVectorBackend:
    def save(self, records: list[MemoryRecord]):
        with self.conn.cursor() as cur:
            for r in records:
                cur.execute(
                    "INSERT INTO memories (content, embedding, scope) VALUES (%s, %s, %s)",
                    (r.content, r.embedding, r.scope)
                )

    def search(self, query_embedding, scope_prefix=None, limit=10):
        cur.execute(
            "SELECT content, 1 - (embedding <=> %s) AS score FROM memories ...",
            (query_embedding,)
        )
```

### 5.2 记忆衰减策略

```python
class DecayingMemory(Memory):
    def recall(self, query, **kwargs):
        results = super().recall(query, **kwargs)
        # 应用指数衰减
        for m in results:
            days = (datetime.now() - m.record.timestamp).days
            m.score *= 0.5 ** (days / self.recency_half_life_days)
        return results
```

### 5.3 跨会话记忆共享

```python
shared_memory = Memory(
    storage="lancedb",  # 持久化到磁盘
    root_scope="/shared",  # 共享范围
)
# 多个 Crew 共享同一个 Memory 实例
crew1 = Crew(agents=[...], memory=shared_memory)
crew2 = Crew(agents=[...], memory=shared_memory)
```

---

## 6. 面试深挖问题清单

| # | 问题 | 考察点 |
|---|------|--------|
| 1 | Memory 的复合评分由哪三个维度组成？ | 记忆排序、权重设计 |
| 2 | `consolidation_threshold` 的作用是什么？ | 记忆去重、合并策略 |
| 3 | RecallFlow 的 shallow 和 deep 模式有何区别？ | 自适应检索、预算控制 |
| 4 | MemoryScope 如何实现多 Agent 记忆隔离？ | 范围隔离、chroot 类比 |
| 5 | LLM 在记忆保存时承担什么角色？ | 自动分析、scope/category/importance 推断 |
| 6 | StorageBackend Protocol 的设计目的是什么？ | 可插拔架构、接口隔离 |
| 7 | 为什么默认使用 LanceDB 而不是 ChromaDB？ | 嵌入式、列式存储、性能 |
| 8 | `recency_half_life_days` 参数如何影响召回？ | 指数衰减、时间衰减 |
| 9 | 记忆保存为什么要异步执行？ | 非阻塞、后台线程池 |
| 10 | `read_only` 模式的使用场景是什么？ | 只读记忆、安全隔离 |

---

## 7. 简易可运行 Demo

```python
"""Demo: Memory 记忆保存、召回、范围隔离"""
from crewai import Agent, Task, Crew
from crewai.memory.unified_memory import Memory

# 1. 创建独立记忆（不绑定 Agent/Crew）
memory = Memory(
    llm="gpt-4o-mini",
    storage="lancedb",  # 默认使用 LanceDB，零配置
    embedder={"provider": "openai", "config": {"model": "text-embedding-3-small"}},
)

# 2. 保存记忆
memory.remember(
    content="CrewAI 支持 Sequential（顺序执行）和 Hierarchical（层级执行）两种策略",
    scope="/crewai/execution",
    importance=0.8,
)

memory.remember(
    content="Tools 工具系统通过 BaseTool 抽象，支持自定义工具和缓存",
    scope="/crewai/tools",
    importance=0.7,
)

# 3. 召回记忆
results = memory.recall(
    query="CrewAI 有哪些执行模式?",
    limit=5,
    depth="deep",  # 深度召回
)
for r in results:
    print(f"[{r.score:.2f}] {r.record.content[:80]}...")

# 4. 范围隔离视图
tools_scope = memory.scope("/crewai/tools")
tools_results = tools_scope.recall("工具系统")
print(f"\n工具范围记忆数: {len(tools_results)}")

# 5. 绑定到 Agent（自动使用 Agent 的 role 作为 scope）
agent = Agent(
    role="CrewAI 研究员",
    goal="回答 CrewAI 相关问题",
    memory=True,  # 启用内置记忆
    llm="gpt-4o-mini",
)
```

---

**下一阶段解析指令：**

```
# 当前解析目标
模块名称：Hooks 钩子系统
对应源码文件路径：
- lib/crewai/src/crewai/hooks/hooks.py（Hooks 主类）
- lib/crewai/src/crewai/hooks/llm_hooks.py（LLM 钩子）
- lib/crewai/src/crewai/hooks/tool_hooks.py（工具钩子）
- lib/crewai/src/crewai/hooks/agent_hooks.py（Agent 钩子）
- lib/crewai/src/crewai/hooks/task_hooks.py（Task 钩子）

# 本次输出硬性要求，缺一不可
1. 模块定位（一句话 + 架构位置 + 核心文件清单）
2. 源码分层拆解（文件→类→方法→关键代码行）
3. 完整调用时序图（钩子注册 → 生命周期触发 → before/after 执行）
4. 核心设计亮点（装饰器注册、链式调用、异常处理、条件钩子）
5. 生产落地拓展改造（AOP 日志注入、性能监控、断路器模式）
6. 面试深挖问题清单（10 题）
7. 简易可运行 Demo 代码
```