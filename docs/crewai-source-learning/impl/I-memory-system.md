# 阶段 I：memory/ — 记忆系统实现逻辑详解

## 1. 模块定位与架构图

CrewAI 的记忆系统（`crewai.memory`）是一个**统一的、LLM 驱动的智能记忆模块**，为 Agent 和 Crew 提供持久化记忆能力。它并非简单的 key-value 存储，而是一个具备**自适应深度召回（RLM-inspired）**、**LLM 分析编码**、**分层作用域隔离**、**可插拔存储后端**的完整记忆子系统。

### 架构总览

```
┌─────────────────────────────────────────────────────────────────┐
│                      Memory (UnifiedMemory)                     │
│  统一入口：remember() / recall() / forget() / scope() / slice()  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │  RecallFlow  │    │ EncodingFlow │    │ MemoryScope  │      │
│  │  (召回流程)   │    │ (编码流程)   │    │  /Slice      │      │
│  │              │    │              │    │ (作用域视图)  │      │
│  │ • 查询分析   │    │ • 批量嵌入   │    │              │      │
│  │ • 并行搜索   │    │ • 批内去重   │    │ • 作用域隔离 │      │
│  │ • 置信度路由 │    │ • 并行分析   │    │ • 多域切片   │      │
│  │ • 深度探索   │    │ • 执行规划   │    │              │      │
│  └──────┬───────┘    └──────┬───────┘    └──────────────┘      │
│         │                   │                                   │
│  ┌──────┴───────────────────┴──────────────────────────┐       │
│  │                  StorageBackend (Protocol)           │       │
│  │  save / search / delete / update / list / reset ...  │       │
│  ├──────────────────────────────────────────────────────┤       │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │       │
│  │  │ LanceDB  │  │  Qdrant  │  │  Custom Factory  │   │       │
│  │  │ (默认)   │  │  (Edge)  │  │  (set_memory_    │   │       │
│  │  │          │  │          │  │  storage_factory) │   │       │
│  │  └──────────┘  └──────────┘  └──────────────────┘   │       │
│  └──────────────────────────────────────────────────────┘       │
│                                                                 │
│  ┌──────────────────────────────────────────────────────┐       │
│  │              辅助模块                                  │       │
│  │  analyze.py:  LLM 分析（查询分析/保存分析/合并决策）     │       │
│  │  types.py:    数据类型（MemoryRecord/Match/Config）     │       │
│  │  utils.py:    工具函数（scope 路径处理）                │       │
│  └──────────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────────┘
```

### 数据流向

```
存储路径: remember(content) → EncodingFlow → StorageBackend.save()
召回路径: recall(query)   → RecallFlow   → StorageBackend.search() → 排序/去重
```

---

## 2. 核心实现逻辑详解

### 2.1 UnifiedMemory — 统一记忆管理

**源码位置**：`lib/crewai/src/crewai/memory/unified_memory.py`

`Memory` 类（第 76 行）是整个记忆系统的**唯一对外入口**，它是一个 Pydantic `BaseModel`，封装了记忆的存储、召回、更新、删除等所有操作。

#### 2.1.1 核心字段与配置

**Memory 类字段**（第 86-159 行）：

```python
class Memory(BaseModel):
    memory_kind: Literal["memory"] = "memory"  # 类型标记，用于序列化反序列化判别
    llm: BaseLLM | str                           # LLM 实例或模型名称，默认 "gpt-5.4-mini"
    storage: StorageBackend | str                # 存储后端或路径，默认 "lancedb"
    embedder: Any                                # 嵌入器，默认 OpenAI text-embedding-3-large
    recency_weight: float = 0.3                  # 时间新鲜度权重
    semantic_weight: float = 0.5                 # 语义相似度权重
    importance_weight: float = 0.2               # 重要性权重
    recency_half_life_days: int = 30             # 时间衰减半衰期（天）
    consolidation_threshold: float = 0.85        # 合并触发阈值
    consolidation_limit: int = 5                 # 合并时比较的最大现有记录数
    default_importance: float = 0.5              # 默认重要性
    confidence_threshold_high: float = 0.8       # 高置信度阈值（直接返回结果）
    confidence_threshold_low: float = 0.5        # 低置信度阈值（触发深度探索）
    complex_query_threshold: float = 0.7         # 复杂查询的深度探索阈值
    exploration_budget: int = 1                  # 深度探索轮数
    query_analysis_threshold: int = 200          # 短查询跳过 LLM 分析的字符阈值
    read_only: bool = False                      # 只读模式
    root_scope: str | None = None                # 根作用域前缀
```

**私有属性**（第 161-172 行）：

```python
_config: MemoryConfig          # 内部配置对象（第 208 行初始化）
_llm_instance: BaseLLM | None  # 懒加载 LLM 实例
_embedder_instance: Any        # 懒加载嵌入器实例
_storage: StorageBackend       # 存储后端实例
_save_pool: ThreadPoolExecutor # 保存线程池（max_workers=1，序列化写入）
_pending_saves: list[Future]   # 待完成的保存 Future
_pending_lock: threading.Lock  # pending_saves 的线程锁
_reset_lock: RLock             # 重置操作的锁
```

`_save_pool` 使用 `max_workers=1` 的线程池（第 166 行），**确保所有写入操作串行化**，避免并发写入冲突。

#### 2.1.2 初始化流程（model_post_init，第 206-251 行）

初始化分三步：

1. **构建 MemoryConfig**（第 208-221 行）：将字段值封装为 `MemoryConfig` 对象，方便传递给 RecallFlow 和 EncodingFlow。

2. **初始化 LLM**（第 223-225 行）：如果 `llm` 是字符串，延迟到首次使用时创建；如果是实例，调用 `_non_streaming_analysis_llm()` 创建非流式副本。

3. **初始化存储后端**（第 232-251 行）：
   - 如果 `storage` 是字符串，先查自定义工厂 `resolve_memory_storage()`
   - 如果是 `"qdrant-edge"`→`QdrantEdgeStorage`
   - 如果是 `"lancedb"`→`LanceDBStorage()`（默认路径）
   - 其他字符串→`LanceDBStorage(path=...)`（自定义路径）
   - 如果直接传入 `StorageBackend` 实例，则直接使用

**非流式 LLM 副本**（第 58-73 行 `_non_streaming_analysis_llm`）：记忆分析需要结构化输出，不能使用流式模式。通过 `copy.copy()` 或 `model_copy()` 创建副本，然后设置 `stream=False`。

#### 2.1.3 懒加载机制

**LLM 懒加载**（第 255-275 行 `_llm` property）：

```python
@property
def _llm(self) -> BaseLLM:
    if self._llm_instance is None:
        from crewai.llm import LLM
        model_name = self.llm if isinstance(self.llm, str) else str(self.llm)
        self._llm_instance = LLM(model=model_name)
    return self._llm_instance
```

只有在首次调用 `_llm` 时才创建 LLM 实例。如果初始化失败，会抛出带有详细修复建议的 `RuntimeError`。

**嵌入器懒加载**（第 277-295 行 `_embedder` property）：类似逻辑，首次访问时通过 `build_embedder()` 创建。

#### 2.1.4 保存记忆（remember / remember_many）

**`remember()` 方法**（第 430-521 行）：同步保存单条记忆。

核心流程：
1. 检查 `read_only` 模式（第 466 行）
2. 确定 `effective_root`（第 470 行）：per-call 的 `root_scope` 参数优先于实例级配置
3. 发射 `MemorySaveStartedEvent`（第 474-480 行）
4. 通过 `_submit_save()` 提交到线程池（第 485-495 行）
5. 阻塞等待 `future.result()` 返回 `MemoryRecord`
6. 发射 `MemorySaveCompletedEvent`（第 500-509 行）
7. 失败时发射 `MemorySaveFailedEvent`（第 512-521 行）

**`remember_many()` 方法**（第 523-579 行）：批量异步保存。

与 `remember()` 的区别：
- 返回空列表，不等待保存完成（第 579 行）
- 通过 `_submit_save()` 提交到后台线程（第 567 行），调用 `_background_encode_batch()`
- 写入屏障：后续的 `recall()` 调用会自动 `drain_writes()` 等待所有待保存操作完成

**`_encode_batch()` 方法**（第 372-428 行）：核心编码逻辑，创建 `EncodingFlow` 实例执行 5 步编码流程。

**`_submit_save()` 方法**（第 297-322 行）：提交保存任务到线程池。如果线程池已关闭（`RuntimeError`），降级为同步执行。

**`_background_encode_batch()` 方法**（第 581-665 行）：后台线程中的编码 + 事件发射。关键细节：
- 所有 `emit()` 调用都包裹在 try/except 中，防止进程退出时事件总线已关闭导致的异常（第 617-626 行、第 652-664 行）
- 处理 `RuntimeError("cannot schedule new futures")` 异常：进程关闭时静默放弃保存（第 641-649 行）

#### 2.1.5 召回记忆（recall）

**`recall()` 方法**（第 681-816 行）：核心召回接口。

两种模式：
- **`shallow`**（浅层）：直接嵌入查询 → 单次向量搜索 → 计算复合分数 → 排序返回
- **`deep`**（深层，默认）：使用 `RecallFlow` 进行自适应深度召回

关键流程：
1. **写入屏障**：`drain_writes()` 等待所有后台保存完成（第 713 行）
2. **作用域处理**（第 715-719 行）：如果设置了 `root_scope`，自动拼接作用域路径
3. **浅层模式**（第 734-762 行）：
   - 调用 `embed_text()` 嵌入查询
   - 调用 `storage.search()` 向量搜索
   - 过滤私有记录（`include_private` 控制）
   - 调用 `compute_composite_score()` 计算综合分数
   - 按分数降序排序
4. **深层模式**（第 763-782 行）：创建 `RecallFlow` 实例，执行完整召回流程
5. **触摸记录**（第 784-790 行）：更新已召回记录的 `last_accessed` 时间戳
6. 发射 `MemoryQueryCompletedEvent` / `MemoryQueryFailedEvent`

#### 2.1.6 其他操作

- **`forget()`**（第 818-850 行）：按条件删除记忆，支持 `scope`、`categories`、`older_than`、`metadata_filter`、`record_ids` 等过滤
- **`update()`**（第 852-896 行）：按 ID 更新记录，支持内容重新嵌入
- **`extract_memories()`**（第 667-679 行）：使用 LLM 从原始内容中提取离散记忆片段
- **`scope()`**（第 898-902 行）：返回 `MemoryScope` 作用域视图
- **`slice()`**（第 904-918 行）：返回 `MemorySlice` 多域切片视图
- **`list_scopes()` / `list_records()` / `info()` / `tree()` / `list_categories()`**：管理操作
- **`reset()` / `reset_all()`**：重置操作，带锁保护
- **`drain_writes()` / `close()`**：生命周期管理

#### 2.1.7 深度复制支持

`__deepcopy__` 方法（第 174-204 行）处理了 `ThreadPoolExecutor` 和 `threading.Lock` 等不可 pickle 的私有属性，确保 Memory 实例可以被正确复制（例如在多 Agent 场景中）。

---

### 2.2 RecallFlow — 记忆召回流程

**源码位置**：`lib/crewai/src/crewai/memory/recall_flow.py`

`RecallFlow` 是一个基于 CrewAI Flow 框架的**自适应深度召回流程**（第 58 行），灵感来自 RLM（Retrieval Language Model）的检索策略。它实现了：

- LLM 查询蒸馏为多个目标子查询
- 时间过滤
- 并行多查询、多作用域搜索
- 基于置信度的路由（迭代加深）
- 证据缺口追踪

#### 2.2.1 状态管理（RecallState，第 37-55 行）

```python
class RecallState(BaseModel):
    id: str
    query: str                           # 原始查询
    scope: str | None                    # 搜索作用域
    categories: list[str] | None         # 类别过滤
    time_cutoff: datetime | None         # 时间过滤截止点
    source: str | None                   # 来源过滤
    include_private: bool                # 是否包含私有记录
    limit: int                           # 结果数量限制
    query_embeddings: list[tuple[str, list[float]]]  # (查询文本, 嵌入向量) 对
    query_analysis: QueryAnalysis | None # LLM 查询分析结果
    candidate_scopes: list[str]          # 候选作用域列表
    chunk_findings: list[Any]            # 各分块搜索结果
    evidence_gaps: list[str]             # 证据缺口
    confidence: float                    # 当前置信度
    final_results: list[MemoryMatch]     # 最终结果
    exploration_budget: int              # 剩余探索预算
```

#### 2.2.2 步骤 1：查询分析（analyze_query_step，第 178-241 行）

这是 Flow 的起点（`@start()` 装饰器，第 178 行）。

**短查询快速路径**（第 192-202 行）：
- 查询长度 < `query_analysis_threshold`（默认 200 字符）→ 跳过 LLM 分析
- 直接使用原始查询作为搜索词，复杂度设为 `"simple"`
- 节省约 1-3 秒的 LLM 调用时间

**长查询深度分析**（第 204-226 行）：
- 获取可用作用域列表 `storage.list_scopes()`
- 获取当前作用域信息 `storage.get_scope_info()`
- 调用 `analyze_query()` LLM 函数，输出 `QueryAnalysis`：
  - `recall_queries`：1-3 个蒸馏后的搜索短语
  - `suggested_scopes`：建议搜索的作用域
  - `complexity`：`"simple"` 或 `"complex"`
  - `time_filter`：ISO 8601 时间过滤（如 `"2026-02-01"`）
- 如果分析出时间过滤，设置 `time_cutoff`

**批量嵌入**（第 228-240 行）：
- 取最多 3 个召回查询（第 231 行）
- 调用 `embed_texts()` **一次性批量嵌入**所有查询（而非逐个调用）
- 如果批量嵌入失败，降级为原始查询的嵌入

#### 2.2.3 步骤 2：作用域选择（filter_and_chunk，第 243-264 行）

使用 `@listen(analyze_query_step)` 装饰器（第 243 行），在查询分析完成后执行：

- 如果 LLM 分析给出了 `suggested_scopes`，使用建议的作用域（第 248 行）
- 否则通过 `storage.list_scopes()` 获取所有子作用域（第 252 行）
- 最多选 20 个候选作用域（第 262 行）
- 如果没有任何候选，使用当前作用域前缀（第 260-261 行）

#### 2.2.4 步骤 3：并行搜索（search_chunks，第 266-269 行）

调用 `_do_search()` 方法（第 87-176 行）：

**搜索策略**：
- 构建笛卡尔积任务：`(embeddings) × (scopes)`（第 115-119 行）
- 每个搜索使用 `_RECALL_OVERSAMPLE_FACTOR`（默认 2 倍）的 limit，确保后续过滤有足够候选

**并行执行**（第 123-172 行）：
- 单任务：直接串行执行
- 多任务：使用 `ThreadPoolExecutor`（最多 4 workers）并行执行
- 每个搜索任务内部：
  - 调用 `storage.search()` 进行向量搜索
  - 应用 `time_cutoff` 时间过滤
  - 应用私有记录过滤（`include_private` / `source` 匹配）
- 计算每个 found 的 top 记录的 `compute_composite_score()`

**置信度更新**（第 175 行）：
```python
self.state.confidence = max((f["top_score"] for f in findings), default=0.0)
```

#### 2.2.5 步骤 4：深度路由（decide_depth，第 271-289 行）

使用 `@router(search_chunks)` 装饰器（第 271 行），根据置信度决定下一步：

```python
def decide_depth(self) -> str:
    if (analysis and analysis.complexity == "complex"
        and self.state.confidence < self._config.complex_query_threshold):
        if self.state.exploration_budget > 0:
            return "explore_deeper"  # 复杂查询 + 低置信度 + 有预算 → 深度探索
    if self.state.confidence >= self._config.confidence_threshold_high:
        return "synthesize"          # 高置信度 → 直接合成结果
    if (self.state.exploration_budget > 0
        and self.state.confidence < self._config.confidence_threshold_low):
        return "explore_deeper"      # 低置信度 + 有预算 → 深度探索
    return "synthesize"              # 默认 → 合成结果
```

**路由规则总结**：
| 条件 | 结果 |
|------|------|
| 复杂查询 + 置信度 < 0.7 + 有预算 | explore_deeper |
| 置信度 ≥ 0.8 | synthesize |
| 置信度 < 0.5 + 有预算 | explore_deeper |
| 其他 | synthesize |

#### 2.2.6 步骤 5：深度探索（recursive_exploration，第 291-331 行）

使用 `@listen("explore_deeper")` 装饰器（第 291 行），消耗探索预算：

1. `exploration_budget -= 1`（第 297 行）
2. 遍历每个 finding，取 top 5 结果的内容拼接（第 300-303 行）
3. 发送给 LLM 提取最重要信息，同时检测缺失信息（第 305-310 行）
4. 如果 LLM 响应中包含 "missing"，添加到 `evidence_gaps`（第 313-314 行）
5. 将 LLM 提取结果附加到 finding 中（第 315-321 行）

#### 2.2.7 步骤 6：重新搜索与路由（第 333-341 行）

`re_search` 调用 `_do_search()` 重新执行搜索，更新置信度。`re_decide_depth` 再次执行路由判断，形成**循环**直到预算耗尽或置信度达标。

#### 2.2.8 步骤 7：结果合成（synthesize_results，第 343-378 行）

使用 `@listen("synthesize")` 装饰器（第 343 行）：

1. **去重**：按 `record.id` 去重（第 346 行）
2. **复合评分**：为每个记录调用 `compute_composite_score()`（第 361-363 行）
3. **排序截断**：按分数降序排序，取前 `limit` 条（第 371-372 行）
4. **证据缺口**：将 `evidence_gaps` 附加到第一条结果的 `evidence_gaps` 字段（第 375-376 行）

---

### 2.3 EncodingFlow — 记忆编码流程

**源码位置**：`lib/crewai/src/crewai/memory/encoding_flow.py`

`EncodingFlow` 是一个**批量原生编码流水线**（第 75 行），处理 `remember()` 和 `remember_many()` 中的所有保存逻辑。它通过 5 个步骤最大化并行度。

#### 2.3.1 状态管理

**ItemState**（第 37-61 行）：每个记忆项的跟踪状态。

```python
class ItemState(BaseModel):
    content: str                          # 内容
    scope / categories / metadata / importance / source / private  # 调用者提供
    root_scope: str | None                # 根作用域前缀
    # --- 解析后字段 ---
    resolved_scope / resolved_categories / resolved_metadata
    resolved_importance / resolved_source / resolved_private
    embedding: list[float]                # 嵌入向量
    dropped: bool                         # 是否被批内去重丢弃
    similar_records: list[MemoryRecord]   # 存储中的相似记录
    top_similarity: float                 # 最高相似度
    plan: ConsolidationPlan | None        # 合并计划
    result_record: MemoryRecord | None    # 最终保存的记录
```

**EncodingState**（第 64-72 行）：批级状态，包括 `items`、`records_inserted`、`records_updated`、`records_deleted`、`items_dropped_dedup`。

#### 2.3.2 步骤 1：批量嵌入（batch_embed，第 110-117 行）

`@start()` 装饰器（第 110 行），Flow 的起点。

**关键优化**：调用 `embed_texts()` **一次性嵌入所有 items**（第 115 行），而非逐个调用。这大幅减少了 API 调用次数。

#### 2.3.3 步骤 2：批内去重（intra_batch_dedup，第 119-138 行）

`@listen(batch_embed)` 装饰器（第 119 行）。

- 计算批内所有 item 对之间的余弦相似度（第 128-138 行）
- 使用 `batch_dedup_threshold`（默认 **0.98**，types.py 第 203 行）作为阈值
- **注意**：阈值设得非常高（0.98），只丢弃几乎完全相同的重复项，避免误删有意义的相似记忆
- 被丢弃的 item 标记 `dropped=True`（第 136 行）

**余弦相似度计算**（第 140-150 行）：
```python
@staticmethod
def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)
```

#### 2.3.4 步骤 3：并行查找相似记录（parallel_find_similar，第 152-219 行）

`@listen(intra_batch_dedup)` 装饰器（第 152 行）。

为每个活跃 item 在存储中搜索相似记录：

- 搜索范围限制在 `root_scope` 边界内（第 169-175 行）
- 使用 `consolidation_limit`（默认 5）限制返回数量（第 181 行）
- 多 item 时使用 `ThreadPoolExecutor`（最多 8 workers）并行执行（第 199 行）

#### 2.3.5 步骤 4：并行 LLM 分析（parallel_analyze，第 221-345 行）

`@listen(parallel_find_similar)` 装饰器（第 221 行）。

这是最复杂的步骤，将每个 item 分为四组，决定 LLM 调用策略：

**分组逻辑**（第 261-308 行）：

| 组 | 条件 | LLM 调用 |
|----|------|----------|
| A | 字段已提供 + 无相似记录 | 0 次（快速路径） |
| B | 字段已提供 + 有相似记录 | 1 次（合并分析） |
| C | 字段缺失 + 无相似记录 | 1 次（字段解析） |
| D | 字段缺失 + 有相似记录 | 2 次（字段解析 + 合并分析） |

**字段已提供**的判断标准（第 265-269 行）：
```python
fields_provided = (
    item.scope is not None
    and item.categories is not None
    and item.importance is not None
)
```

**有相似记录**的判断标准：`item.top_similarity >= consolidation_threshold`（默认 0.85）

**并行执行**（第 259-344 行）：
- 所有 LLM 调用通过 `ThreadPoolExecutor(max_workers=10)` 并行提交（第 259 行）
- 使用 `contextvars.copy_context().run` 传递上下文（第 278 行）
- 先收集所有 `save_futures` 和 `consol_futures`
- 先处理字段解析结果（第 310-340 行），再处理合并结果（第 342-343 行）

**字段解析**（`analyze_for_save`，analyze.py 第 267-315 行）：
- LLM 推断 `suggested_scope`、`categories`、`importance`、`extracted_metadata`
- 预取现有作用域和类别作为上下文（第 237-254 行）
- 失败时返回安全默认值（scope="/", categories=[], importance=0.5）

**合并分析**（`analyze_for_consolidation`，analyze.py 第 321-375 行）：
- LLM 决定对每个现有相似记录执行 `keep`、`update` 或 `delete` 操作
- 同时决定是否 `insert_new`（插入新记录）
- 失败时默认 `insert_new=True`（安全优先）

**作用域路径处理**（第 313-317 行）：
```python
inner_scope = item.scope or analysis.suggested_scope or "/"
if item.root_scope:
    item.resolved_scope = join_scope_paths(item.root_scope, inner_scope)
else:
    item.resolved_scope = inner_scope
```

#### 2.3.6 步骤 5：执行计划（execute_plans，第 369-499 行）

`@listen(parallel_analyze)` 装饰器（第 369 行）。

**操作去重**（第 381-418 行）：
- 多个 item 可能引用相同的现有记录 → 需要去重
- 对于同一 `record_id`，只保留第一个操作（"先到先得"）
- 防止 LanceDB 对同一记录进行两次操作导致的 commit 冲突

**执行顺序**：
1. 收集所有要插入的记录（第 429-448 行）
2. **先删除**旧记录（第 451-453 行）
3. **再更新**记录（第 455-472 行），重新嵌入更新后的内容
4. **最后插入**新记录（第 474-479 行），批量 `storage.save()`
5. 为非插入的 item 设置 `result_record`（第 482-498 行）

**增量更新**：`records_inserted`、`records_updated`、`records_deleted` 计数器被更新。

---

### 2.4 MemoryScope — 记忆作用域

**源码位置**：`lib/crewai/src/crewai/memory/memory_scope.py`

#### 2.4.1 MemoryScope（第 38-224 行）

`MemoryScope` 是 Memory 的**单作用域视图**，所有操作自动限制在 `root_path` 下。

**核心设计**：
- 持有 `_memory: Memory` 私有引用（第 47 行），所有操作委托给底层 Memory
- `_scope_path()` 方法（第 91-100 行）将相对路径转换为绝对路径

**作用域路径计算**（第 91-100 行）：
```python
def _scope_path(self, scope: str | None) -> str:
    if not scope or scope == "/":
        return self._root or "/"          # 无 scope → 返回 root
    s = scope.rstrip("/")
    if not s.startswith("/"):
        s = "/" + s
    if not self._root:
        return s
    base = self._root.rstrip("/")
    return f"{base}{s}"                   # 拼接 root + scope
```

**代理方法**：`remember()`、`remember_many()`、`recall()`、`forget()`、`list_scopes()` 等都通过 `_scope_path()` 转换后代理给底层 Memory。

**`subscope()` 方法**（第 217-224 行）：创建更窄的子作用域视图。

**`bind()` 方法**（第 68-75 行）：支持从 checkpoint 反序列化后重新绑定 Memory 实例。

**`model_validator`**（第 50-66 行）：在构造时从 dict 中提取 `memory` 依赖，并规范化 `root_path`。

#### 2.4.2 MemorySlice（第 227-379 行）

`MemorySlice` 是 Memory 的**多作用域视图**，用于跨多个作用域搜索。

**核心设计**：
- `scopes: list[str]`：要搜索的多个作用域列表
- `read_only: bool = True`：默认只读，防止意外写入
- `recall()` 遍历所有作用域，合并结果并去重排序（第 292-324 行）
- `info()` 聚合所有作用域的信息（第 338-370 行）
- `list_categories()` 跨作用域汇总类别计数（第 372-379 行）

**多作用域召回**（第 292-324 行）：
```python
def recall(self, query, ...):
    all_matches = []
    for sc in self.scopes:
        matches = self._require_memory().recall(
            query, scope=sc, limit=limit * _RECALL_OVERSAMPLE_FACTOR, ...
        )
        all_matches.extend(matches)
    # 去重 + 按分数排序 + 截断
    seen_ids = set()
    unique = []
    for m in sorted(all_matches, key=lambda x: x.score, reverse=True):
        if m.record.id not in seen_ids:
            seen_ids.add(m.record.id)
            unique.append(m)
            if len(unique) >= limit: break
    return unique
```

#### 2.4.3 向后兼容

`_ensure_memory_kind()` 函数（第 20-35 行）处理老版本配置的兼容性：
- 如果 dict 中有 `scopes` 键 → `memory_kind = "slice"`
- 如果 dict 中有 `root_path` 键 → `memory_kind = "scope"`
- 否则 → `memory_kind = "memory"`

---

### 2.5 Storage Factory — 存储工厂

**源码位置**：`lib/crewai/src/crewai/memory/storage/factory.py`

#### 2.5.1 设计理念

存储工厂是一种**进程级的一次性配置机制**，允许应用程序将 Memory 的存储后端路由到自定义实现（不同的向量数据库、远程服务、测试用的内存假实现），而无需在每个 `Memory()` 构造点传递 `storage=` 实例。

#### 2.5.2 核心接口

**`MemoryStorageFactory` 类型**（第 28 行）：
```python
MemoryStorageFactory = Callable[[str], "StorageBackend | None"]
```
接收原始 `storage` 规格字符串，返回一个 `StorageBackend` 实例或 `None`（`None` 表示不处理该规格，回退到内置选择）。

**`set_memory_storage_factory()` 函数**（第 33-45 行）：
```python
def set_memory_storage_factory(factory: MemoryStorageFactory | None) -> None:
    global _factory
    _factory = factory
```
设置全局工厂函数。传入 `None` 恢复默认行为。只影响之后构造的 `Memory` 实例。

**`resolve_memory_storage()` 函数**（第 48-55 行）：
```python
def resolve_memory_storage(spec: str) -> StorageBackend | None:
    factory = _factory
    return factory(spec) if factory is not None else None
```
在 `Memory.model_post_init()` 中被调用（unified_memory.py 第 235 行）。如果工厂返回 `None`，则回退到内置的 LanceDB/Qdrant 选择。

#### 2.5.3 内置存储后端

在 `Memory.model_post_init()` 中的选择逻辑（第 232-251 行）：

| `storage` 参数 | 后端 |
|---------------|------|
| `"lancedb"` | `LanceDBStorage()` — 默认本地路径 |
| `"qdrant-edge"` | `QdrantEdgeStorage()` — Edge 环境 Qdrant |
| 其他字符串 | `LanceDBStorage(path=...)` — 自定义路径 |
| `StorageBackend` 实例 | 直接使用 |

#### 2.5.4 StorageBackend 协议

**源码位置**：`lib/crewai/src/crewai/memory/storage/backend.py`

`StorageBackend` 是一个 `Protocol`（第 45 行），定义了所有存储后端必须实现的方法：

| 方法 | 功能 |
|------|------|
| `save(records)` | 批量保存记录 |
| `search(query_embedding, scope_prefix, categories, limit, min_score)` | 向量搜索 |
| `delete(scope_prefix, categories, record_ids, older_than, metadata_filter)` | 条件删除 |
| `update(record)` | 更新单条记录 |
| `get_record(record_id)` | 按 ID 获取记录 |
| `list_records(scope_prefix, limit, offset)` | 列表查询 |
| `get_scope_info(scope)` | 作用域信息 |
| `list_scopes(parent)` | 子作用域列表 |
| `list_categories(scope_prefix)` | 类别列表 |
| `count(scope_prefix)` | 记录计数 |
| `reset(scope_prefix)` | 重置作用域 |

还有对应的异步版本 `asave`、`asearch`、`adelete`。

---

### 2.6 辅助模块详解

#### 2.6.1 数据类型（types.py）

**核心数据结构**：

- **`MemoryRecord`**（第 20-73 行）：单条记忆记录，包含 `id`、`content`、`scope`、`categories`、`metadata`、`importance`、`created_at`、`last_accessed`、`embedding`、`source`、`private` 等字段。

- **`MemoryMatch`**（第 76-107 行）：召回结果，包含 `record`、`score`、`match_reasons`、`evidence_gaps`。`format()` 方法提供人类可读的格式化输出。

- **`ScopeInfo`**（第 109-133 行）：作用域信息，包含 `path`、`record_count`、`categories`、`oldest_record`、`newest_record`、`child_scopes`。

- **`MemoryConfig`**（第 135-286 行）：内部配置对象，封装所有评分权重、阈值、探索预算等参数。用户通过 `Memory(...)` 构造参数配置，内部转换为 `MemoryConfig`。

**复合评分函数**（第 345-380 行 `compute_composite_score`）：

```python
composite = w_semantic * semantic + w_recency * decay + w_importance * importance
```

其中 `decay = 0.5^(age_days / half_life_days)`，30 天的半衰期意味着 30 天前的记忆新鲜度减半。

**匹配原因**：
- 始终包含 `"semantic"`
- `decay > 0.5` → 添加 `"recency"`
- `importance > 0.5` → 添加 `"importance"`

#### 2.6.2 LLM 分析（analyze.py）

四个核心分析函数：

| 函数 | 用途 | 失败降级 |
|------|------|----------|
| `extract_memories_from_content()` | 从原始文本提取离散记忆 | 返回完整内容作为单条记忆 |
| `analyze_query()` | 分析召回查询 | 返回简单默认值，所有作用域 |
| `analyze_for_save()` | 推断保存字段 | 返回 scope="/" 等安全默认值 |
| `analyze_for_consolidation()` | 合并决策 | 返回 insert_new=True |

每个函数都实现了**优雅降级**：LLM 调用失败不会导致整个流程失败，而是使用安全默认值继续。

#### 2.6.3 工具函数（utils.py）

- **`sanitize_scope_name()`**（第 8-36 行）：将名称（crew 名、agent 角色等）转换为安全的作用域路径名（小写、连字符分隔）
- **`normalize_scope_path()`**（第 39-64 行）：规范化作用域路径（去除双斜杠、确保前导斜杠）
- **`join_scope_paths()`**（第 67-103 行）：安全拼接根作用域和子作用域

---

## 3. 完整调用时序图

### 3.1 保存记忆（remember）时序

```
调用者         Memory           EncodingFlow          StorageBackend       LLM
  │              │                   │                     │                │
  │─remember()──>│                   │                     │                │
  │              │─emit Started─────>│                     │                │
  │              │─_submit_save()───>│                     │                │
  │              │                   │                     │                │
  │              │          ┌────────┴────────┐            │                │
  │              │          │ 1. batch_embed  │            │                │
  │              │          │    embed_texts  │            │                │
  │              │          ├─────────────────┤            │                │
  │              │          │ 2. intra_batch  │            │                │
  │              │          │    _dedup       │            │                │
  │              │          │    (cosine sim) │            │                │
  │              │          ├─────────────────┤            │                │
  │              │          │ 3. parallel_    │            │                │
  │              │          │    find_similar │─search()──>│                │
  │              │          │    (并行)       │<──结果─────│                │
  │              │          ├─────────────────┤            │                │
  │              │          │ 4. parallel_    │            │                │
  │              │          │    analyze      │────────────│─analyze_for_  │
  │              │          │  • 字段解析     │            │  save()──────>│
  │              │          │  • 合并决策     │            │<──analysis───│
  │              │          │  (并行 LLM)     │────────────│─analyze_for_  │
  │              │          │                 │            │  consolidation│
  │              │          │                 │            │  ()──────────>│
  │              │          │                 │            │<──plan───────│
  │              │          ├─────────────────┤            │                │
  │              │          │ 5. execute_     │            │                │
  │              │          │    plans        │─delete()──>│                │
  │              │          │                 │─update()──>│                │
  │              │          │                 │─save()────>│                │
  │              │          └────────┬────────┘            │                │
  │              │<──records─────────│                     │                │
  │              │─emit Completed───>│                     │                │
  │<─MemoryRecord│                   │                     │                │
```

### 3.2 召回记忆（recall / deep）时序

```
调用者         Memory           RecallFlow           StorageBackend       LLM
  │              │                   │                     │                │
  │─recall()────>│                   │                     │                │
  │              │─drain_writes()    │                     │                │
  │              │                   │                     │                │
  │              │          ┌────────┴────────┐            │                │
  │              │          │ 1. analyze_query│            │                │
  │              │          │  • 短查询跳过   │            │                │
  │              │          │  • 长查询 LLM   │────────────│─analyze_query>│
  │              │          │  • 批量嵌入     │<──analysis─│                │
  │              │          ├─────────────────┤            │                │
  │              │          │ 2. filter_and   │            │                │
  │              │          │    _chunk       │─list_scopes│                │
  │              │          │  (选择作用域)    │  ()───────>│                │
  │              │          ├─────────────────┤            │                │
  │              │          │ 3. search_chunks│            │                │
  │              │          │  (并行搜索)     │─search()──>│                │
  │              │          │  embeddings×    │─search()──>│                │
  │              │          │  scopes         │─search()──>│                │
  │              │          ├─────────────────┤            │                │
  │              │          │ 4. decide_depth │            │                │
  │              │          │  ┌──────────────┤            │                │
  │              │          │  │ 如果低置信度: │            │                │
  │              │          │  │ 5. recursive  │────────────│─LLM 提取────>│
  │              │          │  │    exploration│<──提取─────│                │
  │              │          │  │ 6. re_search │─search()──>│                │
  │              │          │  │ 7. re_decide │            │                │
  │              │          │  └──循环直到……──┤            │                │
  │              │          ├─────────────────┤            │                │
  │              │          │ 8. synthesize   │            │                │
  │              │          │  • 去重         │            │                │
  │              │          │  • 复合评分     │            │                │
  │              │          │  • 排序截断     │            │                │
  │              │          └────────┬────────┘            │                │
  │              │<──results─────────│                     │                │
  │              │─touch_records()──>│                     │                │
  │              │─emit Completed───>│                     │                │
  │<─[MemoryMatch]                   │                     │                │
```

---

## 4. 完整可运行示例

### 4.1 基础记忆保存与召回

```python
from crewai.memory import Memory

# 创建记忆实例（使用默认 LanceDB 存储）
memory = Memory(
    llm="gpt-4o-mini",          # LLM 模型
    embedder={"provider": "openai", "config": {"model": "text-embedding-3-small"}},
    storage="lancedb",          # 本地 LanceDB
)

# 保存记忆
record = memory.remember(
    content="项目 Alpha 的截止日期是 2026 年 8 月 15 日，负责人是张三。",
    categories=["project", "deadline"],
)
print(f"已保存记录: {record.id}")

# 召回记忆
results = memory.recall(query="Alpha 项目什么时候截止？", limit=3)
for match in results:
    print(f"[{match.score:.2f}] {match.record.content}")
    print(f"  匹配原因: {match.match_reasons}")
```

### 4.2 批量保存与浅层/深层召回对比

```python
from crewai.memory import Memory

memory = Memory()

# 批量保存多条记忆
contents = [
    "用户偏好：喜欢简洁的 UI 设计，对暗色主题有强烈偏好。",
    "上次会议结论：Q3 重点推进移动端适配。",
    "技术决策：后端采用 FastAPI，前端使用 React + TypeScript。",
    "预算信息：Q3 研发预算为 200 万元。",
]

memory.remember_many(
    contents=contents,
    scope="/company/decisions",
    categories=["meeting"],
    importance=0.8,
)

# 浅层召回：直接向量搜索
shallow_results = memory.recall(
    query="前端的用什么技术栈？",
    depth="shallow",
    limit=3,
)
print("=== 浅层召回 ===")
for m in shallow_results:
    print(f"[{m.score:.2f}] {m.record.content}")

# 深层召回：LLM 蒸馏 + 自适应深度探索
deep_results = memory.recall(
    query="Q3 的研发预算有多少？前端技术选型是什么？",
    depth="deep",
    limit=3,
)
print("\n=== 深层召回 ===")
for m in deep_results:
    print(f"[{m.score:.2f}] {m.record.content}")
    if m.evidence_gaps:
        print(f"  证据缺口: {m.evidence_gaps}")
```

### 4.3 作用域隔离（MemoryScope）

```python
from crewai.memory import Memory

memory = Memory()

# 使用作用域视图隔离不同 Agent 的记忆
agent_a_scope = memory.scope("/agent/researcher")
agent_b_scope = memory.scope("/agent/writer")

# Agent A 保存研究相关的记忆
agent_a_scope.remember(
    content="市场调研显示 AI 助手市场年增长率为 35%",
    scope="/market",
    categories=["research"],
)

# Agent B 保存写作相关的记忆
agent_b_scope.remember(
    content="文档风格指南：使用主动语态，避免技术术语",
    scope="/style",
    categories=["writing"],
)

# Agent A 的召回限在其作用域内
a_results = agent_a_scope.recall(query="市场增长率")
print("Agent A 的召回结果：")
for m in a_results:
    print(f"  [{m.score:.2f}] {m.record.content}")

# 查看作用域树
print("\n作用域树：")
print(memory.tree())
```

### 4.4 多作用域切片（MemorySlice）

```python
from crewai.memory import Memory

memory = Memory()

# 创建跨作用域切片
slice_view = memory.slice(
    scopes=["/agent/researcher", "/agent/writer"],
    categories=["planning"],
    read_only=True,
)

# 在切片中召回：跨所有作用域合并结果
results = slice_view.recall(query="下个季度的计划")
for m in results:
    print(f"[{m.score:.2f}] scope={m.record.scope} | {m.record.content}")

# 查看切片聚合信息
info = slice_view.info()
print(f"\n切片总记录数: {info.record_count}")
print(f"时间范围: {info.oldest_record} ~ {info.newest_record}")
```

### 4.5 自定义存储后端

```python
from crewai.memory import Memory
from crewai.memory.storage.factory import set_memory_storage_factory

# 方式 1：直接传入 StorageBackend 实例
from crewai.memory.storage.lancedb_storage import LanceDBStorage

memory = Memory(
    storage=LanceDBStorage(path="./my_custom_memory"),
    llm="gpt-4o-mini",
)

# 方式 2：注册全局工厂（对后续所有 Memory 实例生效）
def my_factory(spec: str):
    if spec == "my-custom-backend":
        # 返回你的自定义 StorageBackend 实现
        from crewai.memory.storage.lancedb_storage import LanceDBStorage
        return LanceDBStorage(path="./factory_memory")
    return None  # 其他规格回退到默认

set_memory_storage_factory(my_factory)

# 现在通过字符串即可使用
memory2 = Memory(storage="my-custom-backend")

# 恢复默认
set_memory_storage_factory(None)
```

---

## 5. 设计亮点与注意事项

### 设计亮点

1. **自适应深度召回（RLM-inspired）**：`RecallFlow` 不是简单的一轮向量搜索，而是通过 LLM 分析查询意图、蒸馏子查询、基于置信度自适应路由到深度探索。这种设计在多跳推理和复杂查询场景下显著提升召回质量。

2. **批量编码 + 并行 LLM 分析**：`EncodingFlow` 的 5 步流水线大量使用并行化（批量嵌入、并行搜索、并行 LLM 分析），最大化吞吐量。特别是步骤 4 按四组策略并行调用 LLM，避免不必要的 LLM 调用。

3. **优雅降级**：所有 LLM 分析函数（`analyze_for_save`、`analyze_for_consolidation`、`analyze_query`、`extract_memories_from_content`）在失败时都返回安全默认值，确保即使 LLM 不可用，记忆系统仍能正常运作。

4. **写入序列化 + 读取屏障**：`_save_pool` 使用 `max_workers=1` 确保写入串行化，`recall()` 开头自动 `drain_writes()` 确保读取一致性。

5. **可插拔存储后端**：通过 `StorageBackend` 协议和 `set_memory_storage_factory` 工厂函数，支持 LanceDB、Qdrant 以及任意自定义后端，无需修改核心代码。

6. **分层作用域隔离**：`MemoryScope` 和 `MemorySlice` 提供了多租户/多 Agent 场景下的记忆隔离机制，支持从 checkpoint 恢复后重新绑定。

7. **短查询快速路径**：`RecallFlow` 中 `query_analysis_threshold` 阈值让短查询（< 200 字符）跳过 LLM 分析，直接嵌入搜索，节省约 1-3 秒。

8. **复合评分机制**：`compute_composite_score` 综合考虑语义相似度（0.5 权重）、时间新鲜度（0.3 权重，30 天半衰期指数衰减）、重要性（0.2 权重），提供更合理的排序。

### 注意事项

1. **LLM 依赖**：默认 LLM 为 `gpt-5.4-mini`，需要设置 `OPENAI_API_KEY`。如果 LLM 不可用，保存时必须显式提供所有字段（`scope`、`categories`、`importance`），召回只能使用 `depth="shallow"`。

2. **嵌入器维度一致性**：默认嵌入器 `text-embedding-3-large` 产生 3072 维向量。如果之前使用 `text-embedding-3-small`（1536 维），升级后需要重置记忆或指定旧嵌入器（见 `EmbeddingDimensionMismatchError`）。

3. **批内去重阈值极高**：`batch_dedup_threshold = 0.98`，只丢弃几乎完全相同的项。如果需要更激进的去重，需自行调整。

4. **合并阈值敏感**：`consolidation_threshold = 0.85` 控制何时触发 LLM 合并决策。太高会导致大量重复记忆，太低会导致不相关记忆被错误合并。

5. **只读模式**：`MemorySlice` 默认 `read_only=True`，如果需要写入多域切片，必须显式设置 `read_only=False`。

6. **线程安全**：`_save_pool` 是 `max_workers=1` 的线程池，确保写入串行化，但 `_reset_lock` 是 `RLock`，重置操作需要获取此锁。

7. **进程退出时的事件发射**：`_background_encode_batch` 中所有 `emit()` 调用都包裹在 try/except 中，防止事件总线在进程退出时已关闭导致的异常。

8. **深度探索预算**：`exploration_budget` 默认只有 1 轮，如果需要更深入的探索，可以通过 `Memory(exploration_budget=3)` 增加。