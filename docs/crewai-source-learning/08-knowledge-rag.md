# 阶段八：Knowledge 知识检索 — 源码深度解析

---

## 1. 模块定位

### 1.1 一句话概括

**Knowledge 知识检索模块是 CrewAI 的 RAG 能力层，通过「多源知识加载 → 文本分块 → Embedding 向量化 → ChromaDB 存储 → 语义检索」的标准 RAG 流水线，让 Agent 能够基于外部知识库（文档、字符串、PDF、CSV 等）进行上下文增强推理。**

### 1.2 在整体架构中的位置

```
Agent 配置 knowledge_sources
    │
    ▼
Knowledge(sources=[...], embedder=...)
    │
    ├── add_sources()  ← 知识入库
    │   └── for source in sources:
    │       ├── validate_content()     ← 校验内容
    │       ├── _chunk_text()          ← 文本分块 (chunk_size=4000, overlap=200)
    │       └── storage.save(chunks)   ← 向量化 + 存储到 ChromaDB
    │
    └── query(["问题"])  ← 知识检索
        └── storage.search(query, limit=5, score_threshold=0.6)
            ├── embedder.embed(query)  ← 查询向量化
            └── ChromaDB.query()       ← 相似度检索
                └── 返回 SearchResult[]
```

### 1.3 本阶段涉及的核心源码文件

| 文件 | 核心职责 |
|------|----------|
| `knowledge/knowledge.py` | Knowledge 主类：多源管理、查询入口、存储初始化 |
| `knowledge/source/base_knowledge_source.py` | 知识源基类：分块、验证、保存 |
| `knowledge/source/string_knowledge_source.py` | 字符串知识源 |
| `knowledge/source/pdf_knowledge_source.py` | PDF 知识源 |
| `knowledge/source/csv_knowledge_source.py` | CSV 知识源 |
| `knowledge/source/crew_docling_source.py` | Docling 文档解析源（支持多种格式） |
| `knowledge/storage/base_knowledge_storage.py` | 存储抽象基类 |
| `knowledge/storage/knowledge_storage.py` | ChromaDB 存储实现 |
| `knowledge/storage/factory.py` | 存储工厂（自定义存储注入） |
| `rag/` 目录 | RAG 底层：Embedder、Client、ChromaDB 配置 |

---

## 2. 源码分层拆解

### 2.1 第一层：Knowledge（知识管理主类）

**文件：** `lib/crewai/src/crewai/knowledge/knowledge.py`

```python
class Knowledge(BaseModel):
    """知识库主类，管理多个知识源和向量存储。"""

    sources: list[BaseKnowledgeSource] = []  # 知识源列表
    storage: BaseKnowledgeStorage | None = None  # 向量存储后端
    embedder: EmbedderConfig | None = None  # Embedding 模型配置
    collection_name: str | None = None  # ChromaDB 集合名称
```

**核心方法 — query：**

```python
def query(self, query: list[str], results_limit: int = 5,
          score_threshold: float = 0.6) -> list[SearchResult]:
    """跨所有知识源查询最相关信息。"""
    if self.storage is None:
        raise ValueError("Storage is not initialized.")
    return self.storage.search(query, limit=results_limit,
                               score_threshold=score_threshold)
```

**核心方法 — add_sources：**

```python
def add_sources(self) -> None:
    """将所有知识源添加到存储中。"""
    for source in self.sources:
        source.storage = self.storage  # 注入存储引用
        source.add()  # 触发分块 → 向量化 → 存储
```

**支持的知识源类型：**

```python
_KNOWN_SOURCES = {
    "string": StringKnowledgeSource,
    "docling": CrewDoclingSource,       # 支持 Word/PDF/HTML 等
    "csv": CSVKnowledgeSource,
    "excel": ExcelKnowledgeSource,
    "json": JSONKnowledgeSource,
    "pdf": PDFKnowledgeSource,
    "text_file": TextFileKnowledgeSource,
}
```

---

### 2.2 第二层：BaseKnowledgeSource（知识源基类）

**文件：** `lib/crewai/src/crewai/knowledge/source/base_knowledge_source.py`

```python
class BaseKnowledgeSource(BaseModel, ABC):
    """所有知识源的抽象基类。"""

    chunk_size: int = 4000        # 分块大小（默认 4000 字符）
    chunk_overlap: int = 200      # 分块重叠（默认 200 字符）
    chunks: list[str] = []        # 分块后的文本列表
    chunk_embeddings: list[np.ndarray] = []  # 分块对应的向量
    storage: BaseKnowledgeStorage | None = None  # 存储后端引用
    metadata: dict[str, Any] = {}  # 元数据

    @abstractmethod
    def validate_content(self) -> Any:
        """加载并验证原始内容。"""

    @abstractmethod
    def add(self) -> None:
        """处理内容 → 分块 → 计算 Embedding → 保存。"""

    def _chunk_text(self, text: str) -> list[str]:
        """滑动窗口分块（带重叠）。"""
        return [
            text[i : i + self.chunk_size]
            for i in range(0, len(text), self.chunk_size - self.chunk_overlap)
        ]

    def _save_documents(self) -> None:
        """将分块保存到存储后端。"""
        if self.storage is not None:
            self.storage.save(self.chunks)
        else:
            raise ValueError("No storage found to save documents.")
```

**大白话解释分块策略：** 假设 `chunk_size=4000, chunk_overlap=200`，第一块取 `[0:4000]`，第二块取 `[3800:7800]`（重叠 200 字符），第三块取 `[7600:11600]`... 这样保证相邻块有上下文重叠，检索时不会丢失边界信息。

---

### 2.3 第三层：StringKnowledgeSource（字符串知识源）

**文件：** `lib/crewai/src/crewai/knowledge/source/string_knowledge_source.py`

```python
class StringKnowledgeSource(BaseKnowledgeSource):
    """最简单的知识源：直接传入字符串内容。"""

    source_type: Literal["string"] = "string"
    content: str = Field(...)  # 文本内容

    def add(self) -> None:
        new_chunks = self._chunk_text(self.content)  # 分块
        self.chunks.extend(new_chunks)
        self._save_documents()  # 保存到向量库
```

---

### 2.4 第四层：KnowledgeStorage（ChromaDB 存储）

**文件：** `lib/crewai/src/crewai/knowledge/storage/knowledge_storage.py`

```python
class KnowledgeStorage(BaseKnowledgeStorage):
    """基于 ChromaDB 的向量存储实现。"""

    collection_name: str | None = None
    embedder: ProviderSpec | BaseEmbeddingsProvider | None = None
    _client: BaseClient | None = None  # ChromaDB 客户端

    @model_validator(mode="after")
    def _init_client(self) -> Self:
        """初始化 ChromaDB 客户端和 Embedding 函数。"""
        if self.embedder:
            embedding_function = build_embedder(self.embedder)  # 构建 Embedder
            config = ChromaDBConfig(embedding_function=embedding_function)
            self._client = create_client(config)  # 创建 ChromaDB 客户端
        return self

    def search(self, query, limit=5, score_threshold=0.6) -> list[SearchResult]:
        """语义搜索。"""
        client = self._get_client()
        collection_name = f"knowledge_{self.collection_name}" or "knowledge"
        query_text = " ".join(query) if len(query) > 1 else query[0]
        return client.search(
            collection_name=collection_name,
            query=query_text,
            limit=limit,
            score_threshold=score_threshold,  # 相似度阈值
        )

    def save(self, documents: list[str]) -> None:
        """保存文档到向量库。"""
        client = self._get_client()
        client.get_or_create_collection(collection_name=collection_name)  # 确保集合存在
        rag_documents = [{"content": doc} for doc in documents]
        client.add_documents(collection_name=collection_name, documents=rag_documents)
```

**关键设计：** `collection_name` 会加前缀 `knowledge_`，与 Memory 模块的 `memory_` 前缀区分，避免命名冲突。

---

## 3. 完整调用时序图

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        Knowledge RAG 流水线                               │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  1. 初始化知识库                                                           │
│     knowledge = Knowledge(                                                 │
│         collection_name="my_docs",                                         │
│         sources=[                                                          │
│             StringKnowledgeSource(content="CrewAI 是一个..."),              │
│             PDFKnowledgeSource(file_path="docs/guide.pdf"),                │
│         ],                                                                 │
│         embedder={"provider": "openai", "model": "text-embedding-3-small"}  │
│     )                                                                      │
│     │                                                                      │
│     ├── 创建 KnowledgeStorage                                              │
│     │   ├── build_embedder(embedder) → OpenAIEmbeddingFunction            │
│     │   ├── ChromaDBConfig(embedding_function)                            │
│     │   └── create_client(config) → ChromaDB Client                      │
│     │                                                                      │
│     └── 注入 storage 到各 source                                           │
│                                                                           │
│  2. 知识入库（add_sources）                                                │
│     knowledge.add_sources()                                                │
│     │                                                                      │
│     ├── source 1: StringKnowledgeSource                                    │
│     │   ├── validate_content() → 验证字符串不为空                           │
│     │   ├── _chunk_text(content)                                           │
│     │   │   └── 滑动窗口: [0:4000], [3800:7800], [7600:11600], ...       │
│     │   ├── chunks = ["CrewAI 是一个...", "多Agent框架...", ...]           │
│     │   └── _save_documents()                                              │
│     │       └── storage.save(chunks)                                       │
│     │           ├── ChromaDB.get_or_create_collection("knowledge_my_docs") │
│     │           ├── 对每个 chunk 调用 embedder.embed(chunk)                │
│     │           └── ChromaDB.add_documents(vectors, documents)             │
│     │                                                                      │
│     ├── source 2: PDFKnowledgeSource                                       │
│     │   ├── 解析 PDF → 提取文本                                            │
│     │   ├── _chunk_text(text) → 分块                                       │
│     │   └── _save_documents() → 向量化 + 存储                              │
│     │                                                                      │
│     └── 完成：所有知识已存入 ChromaDB 向量库                                │
│                                                                           │
│  3. 知识检索（query）                                                       │
│     results = knowledge.query(["CrewAI 是什么框架"], limit=5)               │
│     │                                                                      │
│     └── storage.search(query, limit=5, score_threshold=0.6)                │
│         ├── embedder.embed("CrewAI 是什么框架") → 查询向量                 │
│         ├── ChromaDB.query(query_vector, n_results=5)                      │
│         │   └── 余弦相似度计算 → 返回 top-5 匹配 chunks                    │
│         └── 返回 [SearchResult(score=0.92, content="CrewAI 是一个..."), ...]│
│                                                                           │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 4. 核心设计亮点

### 4.1 多源知识统一抽象

所有知识源（String、PDF、CSV、JSON、Excel、Docling）都继承 `BaseKnowledgeSource`，统一 `add()` 和 `validate_content()` 接口，Knowledge 主类无需关心具体类型。

### 4.2 滑动窗口分块（带重叠）

```python
def _chunk_text(self, text: str) -> list[str]:
    return [
        text[i : i + self.chunk_size]
        for i in range(0, len(text), self.chunk_size - self.chunk_overlap)
    ]
```

**面试高频考点：** `chunk_overlap` 保证相邻块有上下文重叠，避免检索时丢失语义边界。默认 4000/200 的配置适用于大多数场景。

### 4.3 Embedding 模型抽象

```python
# 支持多种 Embedding 提供者
embedder = {
    "provider": "openai",        # 或 "google", "azure", "bedrock"
    "model": "text-embedding-3-small",
    "api_key": "...",
}
```

通过 `build_embedder()` 工厂函数统一创建，支持 OpenAI、Google、Azure、Bedrock、Ollama 等。

### 4.4 ChromaDB 作为默认向量存储

- 轻量级、嵌入式、无需外部服务
- 支持持久化（`persist_directory`）
- 支持 metadata 过滤

### 4.5 存储工厂模式

```python
# factory.py: 允许用户注入自定义存储后端
def resolve_knowledge_storage(embedder, collection_name) -> BaseKnowledgeStorage | None:
    # 检查是否有自定义存储注册
    # 否则返回 None → 使用默认 KnowledgeStorage
```

---

## 5. 生产落地拓展改造

### 5.1 混合检索（BM25 + 向量）

```python
class HybridKnowledgeStorage(BaseKnowledgeStorage):
    def __init__(self, vector_store, bm25_index):
        self.vector_store = vector_store
        self.bm25 = bm25_index

    def search(self, query, limit=5, **kwargs):
        # 向量检索
        vector_results = self.vector_store.search(query, limit=limit*2)
        # BM25 关键词检索
        bm25_results = self.bm25.search(query, limit=limit*2)
        # RRF (Reciprocal Rank Fusion) 融合
        return self._rrf_fusion(vector_results, bm25_results, limit)
```

### 5.2 多模态知识库

```python
class MultimodalKnowledgeSource(BaseKnowledgeSource):
    """支持图片、音频等多模态知识源。"""
    def add(self):
        # 图片 → CLIP/ViT Embedding → 向量库
        # 音频 → Whisper 转录 → 文本 Embedding → 向量库
        pass
```

### 5.3 知识图谱增强

```python
class GraphRAGKnowledge(Knowledge):
    """结合知识图谱的 RAG。"""
    def __init__(self, *args, neo4j_uri=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.graph_store = Neo4jClient(neo4j_uri)

    def query(self, query, **kwargs):
        # 1. 向量检索 → 获取候选实体
        # 2. 知识图谱 → 扩展关联实体
        # 3. 融合上下文 → 返回增强结果
        pass
```

---

## 6. 面试深挖问题清单

| # | 问题 | 考察点 |
|---|------|--------|
| 1 | BaseKnowledgeSource 的 `chunk_overlap` 参数有什么作用？ | 文本分块策略、语义边界 |
| 2 | Knowledge 如何管理多个知识源？ | 多源聚合、统一接口 |
| 3 | ChromaDB 作为向量存储的优缺点是什么？ | 嵌入式数据库、持久化 |
| 4 | `build_embedder()` 工厂函数支持哪些 Provider？ | 多模型抽象 |
| 5 | `score_threshold` 参数的作用是什么？ | 相似度过滤、检索质量 |
| 6 | Knowledge 和 Memory 的存储如何区分？ | collection_name 前缀隔离 |
| 7 | 如何实现自定义存储后端？ | 工厂模式、接口实现 |
| 8 | `_resolve_knowledge_sources` 验证器的作用是什么？ | 反序列化、类型恢复 |
| 9 | CrewDoclingSource 相比其他源的优势是什么？ | 多格式文档解析 |
| 10 | 大规模知识库（百万级文档）如何优化检索？ | 索引优化、ANN 近似搜索 |

---

## 7. 简易可运行 Demo

```python
"""Demo: 知识库创建、入库、检索"""
from crewai import Agent, Task, Crew
from crewai.knowledge.source.string_knowledge_source import StringKnowledgeSource
from crewai.knowledge.source.text_file_knowledge_source import TextFileKnowledgeSource

# 1. 创建知识源
content = """
CrewAI 是一个用于编排 AI Agent 的框架。
它支持 Sequential 和 Hierarchical 两种执行策略。
Agent 可以配置 Tools、Knowledge、Memory 等能力。
"""

string_source = StringKnowledgeSource(
    content=content,
    metadata={"topic": "crewai_intro"}
)

# 2. 配置 Embedder（使用 OpenAI）
embedder_config = {
    "provider": "openai",
    "model": "text-embedding-3-small",
    "api_key": "your-api-key",
}

# 3. 创建知识库
knowledge = Knowledge(
    collection_name="crewai_docs",
    sources=[string_source],
    embedder=embedder_config,
)

# 4. 知识入库
knowledge.add_sources()
print("知识入库完成")

# 5. 检索
results = knowledge.query(["CrewAI 支持哪些执行策略?"], limit=3)
for i, r in enumerate(results):
    print(f"结果 {i+1}: [相似度={r['score']:.2f}] {r['content'][:100]}...")

# 6. 将 Knowledge 绑定到 Agent
agent = Agent(
    role="CrewAI 专家",
    goal="回答关于 CrewAI 的问题",
    knowledge_sources=[string_source],  # 或使用 knowledge 对象
    embedder=embedder_config,
)
```

---

**下一阶段解析指令：**

```
# 当前解析目标
模块名称：Memory 记忆系统
对应源码文件路径：
- lib/crewai/src/crewai/memory/memory.py（Memory 主类）
- lib/crewai/src/crewai/memory/short_term/short_term_memory.py（短期记忆）
- lib/crewai/src/crewai/memory/long_term/long_term_memory.py（长期记忆）
- lib/crewai/src/crewai/memory/entity/entity_memory.py（实体记忆）
- lib/crewai/src/crewai/memory/user/user_memory.py（用户记忆）
- lib/crewai/src/crewai/memory/storage/mem0_storage.py（Mem0 存储）
- lib/crewai/src/crewai/memory/unified_memory.py（统一记忆入口）

# 本次输出硬性要求，缺一不可
1. 模块定位（一句话 + 架构位置 + 核心文件清单）
2. 源码分层拆解（文件→类→方法→关键代码行）
3. 完整调用时序图（记忆工厂 → 存储初始化 → 查询/保存 → 向量检索）
4. 核心设计亮点（四种记忆类型、统一记忆入口、Mem0 集成、向量化存储）
5. 生产落地拓展改造（持久化到 PostgreSQL、记忆衰减策略、跨会话记忆共享）
6. 面试深挖问题清单（10 题）
7. 简易可运行 Demo 代码
```