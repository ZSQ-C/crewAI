# CrewAI RAG 模块 — 深度源码实现分析

> 面向小白，逐层逐方法拆解 `lib/crewai/src/crewai/rag/` 的全部实现逻辑

---

## 目录

- [0. 整体概述：这个模块要解决什么问题](#0-整体概述这个模块要解决什么问题)
- [1. 三层架构总览](#1-三层架构总览)
- [2. 顶层：`factory.py` — 客户端工厂路由](#2-顶层factorypy--客户端工厂路由)
- [3. 中层：核心抽象层](#3-中层核心抽象层)
- [4. 底层（一）：ChromaDB 客户端实现](#4-底层一chromadb-客户端实现)
- [5. 底层（二）：Embedding 嵌入层](#5-底层二embedding-嵌入层)
- [6. 支撑层：Config / Types / Storage](#6-支撑层config--types--storage)
- [7. 完整调用链路](#7-完整调用链路)

---

## 0. 整体概述：这个模块要解决什么问题

### 需求串讲

在上一个 knowledge 模块中，我们学习了"知识管理"——把文档切块、转向量、存到向量数据库。但 knowledge 模块依赖的底层基础设施（向量数据库操作、embedding 计算）是谁提供的呢？

就是 **RAG 模块**。

RAG 是 "Retrieval-Augmented Generation"（检索增强生成）的缩写。但 CrewAI 的 RAG 模块不仅仅是"检索"，它是一整套**向量数据库操作的底层基础设施**。

**核心职责**：
1. 管理向量数据库客户端（ChromaDB、Qdrant 等）
2. 管理 Embedding 函数（OpenAI、Google、Cohere 等 18 种提供商）
3. 提供统一的接口，让上层模块（knowledge、memory）不需要关心底层用的是哪个向量数据库

**通俗理解**：RAG 模块就像"水电煤"基础设施。knowledge 模块是"房子"，RAG 模块是"地基和管道"。房子可以换装修风格，但地基只需要一套。

---

## 1. 三层架构总览

```
┌──────────────────────────────────────────────────────────────┐
│               顶层：factory.py（客户端工厂路由）                 │
│   "用户说用 ChromaDB → 我帮你创建 ChromaDB 客户端"              │
│   "用户说用 Qdrant → 我帮你创建 Qdrant 客户端"                  │
│   "用户注册了自定义工厂 → 优先使用自定义的"                       │
├──────────────────────────────────────────────────────────────┤
│               中层：核心抽象层                                  │
│   ┌─────────────────────────────────────────────────────┐    │
│   │  BaseClient（协议/接口）                               │    │
│   │  - 定义向量数据库的标准操作：                            │    │
│   │    create_collection, add_documents, search, reset   │    │
│   │  - 同步 + 异步双版本                                  │    │
│   ├─────────────────────────────────────────────────────┤    │
│   │  BaseEmbeddingsProvider（嵌入提供者抽象）               │    │
│   │  - 定义 embedding 函数的创建接口                       │    │
│   │  - 支持 18 种提供商                                   │    │
│   ├─────────────────────────────────────────────────────┤    │
│   │  EmbeddingFunction（嵌入函数协议）                      │    │
│   │  - 定义嵌入函数的输入输出规范                           │    │
│   │  - 自动归一化和校验 embedding 结果                     │    │
│   └─────────────────────────────────────────────────────┘    │
├──────────────────────────────────────────────────────────────┤
│               底层：具体实现                                   │
│   ┌──────────────────────┬──────────────────────────────┐    │
│   │  向量数据库实现         │   Embedding 提供商实现        │    │
│   │  ChromaDBClient       │  OpenAIProvider              │    │
│   │  QdrantClient         │  GoogleGenerativeAiProvider  │    │
│   │  (可扩展)             │  CohereProvider              │    │
│   │                       │  HuggingFaceProvider         │    │
│   │                       │  OllamaProvider              │    │
│   │                       │  ... 共 18 种                │    │
│   └──────────────────────┴──────────────────────────────┘    │
├──────────────────────────────────────────────────────────────┤
│               支撑层                                          │
│   config/     → 配置管理（BaseRagConfig, contextvars）         │
│   types.py    → 类型定义（BaseRecord, SearchResult）          │
│   storage/    → 旧版兼容层（BaseRAGStorage）                  │
└──────────────────────────────────────────────────────────────┘
```

---

## 2. 顶层：`factory.py` — 客户端工厂路由

### 2.1 需求串讲

**问题**：用户可能想用 ChromaDB（默认），也可能想用 Qdrant，甚至想用自己的向量数据库。如何让用户灵活切换，而不用修改上层代码？

**解决思路**：用工厂模式。`create_client(config)` 根据配置中的 `provider` 字段，动态创建对应的客户端。还支持用户注册自定义工厂。

**通俗理解**：就像你点外卖，App 会根据你选的餐厅（provider）自动匹配对应的配送员。

### 2.2 源码位置

[factory.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/rag/factory.py)（78 行）

### 2.3 核心方法：`create_client`

```python
def create_client(config: RagConfigType) -> BaseClient:
    # 第1优先级：检查用户注册的自定义工厂
    factory = _factories.get(config.provider)
    if factory is not None:
        return factory(config)    # 用自定义工厂创建

    # 第2优先级：内置的 ChromaDB
    if config.provider == "chromadb":
        chromadb_mod = require("crewai.rag.chromadb.factory", ...)
        return chromadb_mod.create_client(config)

    # 第3优先级：内置的 Qdrant
    if config.provider == "qdrant":
        qdrant_mod = require("crewai.rag.qdrant.factory", ...)
        return qdrant_mod.create_client(config)

    raise ValueError(f"Unsupported provider: {config.provider}")
```

**路由优先级**：

```
create_client(config)
  │
  ├── 1. 检查用户自定义工厂
  │     └── _factories[config.provider] 存在？
  │           └── Yes → 调用自定义工厂，返回自定义客户端
  │
  ├── 2. config.provider == "chromadb"？
  │     └── Yes → 延迟导入 chromadb.factory，创建 ChromaDBClient
  │
  ├── 3. config.provider == "qdrant"？
  │     └── Yes → 延迟导入 qdrant.factory，创建 QdrantClient
  │
  └── 4. 都不匹配 → 抛 ValueError
```

**关键设计**：`require()` 是**延迟导入**。ChromaDB 和 Qdrant 的依赖包不是必装的，只有用户实际使用时才会导入，避免模块加载时的依赖错误。

### 2.4 自定义工厂注册机制

```python
_factories: dict[str, RagClientFactory] = {}

def register_rag_client_factory(provider: str, factory: RagClientFactory) -> None:
    _factories[provider] = factory

def unregister_rag_client_factory(provider: str) -> None:
    _factories.pop(provider, None)
```

**使用示例**：

```python
# 注册 Weaviate 客户端
def my_weaviate_factory(config):
    return WeaviateClient(url=config.weaviate_url, ...)

register_rag_client_factory("weaviate", my_weaviate_factory)
```

---

## 3. 中层：核心抽象层

### 3.1 BaseClient — 向量数据库标准接口

**源码位置**：[core/base_client.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/rag/core/base_client.py)（448 行）

**需求串讲**：不同的向量数据库（ChromaDB、Qdrant、Weaviate）有各自的 API，如果上层代码直接调用 ChromaDB 的 API，切换到 Qdrant 时就要全部重写。

**解决思路**：定义 `BaseClient` 协议，规定所有向量数据库必须实现的标准方法。上层代码只依赖 BaseClient，不依赖具体实现。

**BaseClient 定义的核心方法**：

```python
@runtime_checkable
class BaseClient(Protocol):
    client: Any                    # 底层数据库客户端实例
    embedding_function: EmbeddingFunction  # embedding 函数

    # 集合管理
    def create_collection(self, collection_name, ...) -> None: ...
    def get_or_create_collection(self, collection_name, ...) -> Any: ...
    def delete_collection(self, collection_name, ...) -> None: ...

    # 文档操作
    def add_documents(self, collection_name, documents, ...) -> None: ...

    # 搜索
    def search(self, collection_name, query, limit, score_threshold, ...) -> list[SearchResult]: ...

    # 重置
    def reset(self) -> None: ...

    # 每个方法都有对应的 async 版本
```

**通俗理解**：BaseClient 就像"USB 接口标准"。不管你插的是 U 盘（ChromaDB）还是移动硬盘（Qdrant），只要符合 USB 标准，电脑就能识别。

---

### 3.2 EmbeddingFunction — 嵌入函数协议

**源码位置**：[core/base_embeddings_callable.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/rag/core/base_embeddings_callable.py)（150 行）

**需求串讲**：文本需要先转成向量才能存入向量数据库。不同提供商（OpenAI、Google、Cohere）的 embedding 函数格式各不相同。需要统一标准。

**核心协议**：

```python
@runtime_checkable
class EmbeddingFunction(Protocol[D]):
    def __call__(self, input: D) -> Embeddings:
        """把输入转为向量"""
```

**最关键的设计**：`__init_subclass__` 自动包装机制

```python
def __init_subclass__(cls) -> None:
    """自动包装 __call__ 方法，添加归一化和校验"""
    super().__init_subclass__()
    original_call = cls.__call__

    def wrapped_call(self, input):
        result = original_call(self, input)     # 调用原始方法
        if result is None:
            raise ValueError("Embedding function returned None")
        normalized = normalize_embeddings(result)  # 归一化格式
        if normalized is None:
            raise ValueError("Normalization returned None")
        return validate_embeddings(normalized)      # 校验有效性

    cls.__call__ = wrapped_call  # 替换原始方法
```

**通俗理解**：就像你去快递站寄包裹，快递员在收件后会自动帮你检查包装是否完好（`normalize_embeddings`），然后贴上标准标签（`validate_embeddings`）。你不需要自己操心这些。

**归一化函数 `normalize_embeddings`**：把各种格式的 embedding 统一转成 `list[np.ndarray]`：

```python
def normalize_embeddings(target):
    # 情况1：单个 numpy 数组 → 包装成列表
    if isinstance(target, np.ndarray) and target.ndim == 1:
        return [target.astype(np.float32)]
    # 情况2：二维数组 → 按行拆分
    if isinstance(target, np.ndarray) and target.ndim == 2:
        return [row.astype(np.float32) for row in target]
    # 情况3：浮点数列表 → 包装成数组
    if isinstance(first, (int, float)):
        return [np.array(target, dtype=np.float32)]
    # 情况4：列表的列表 → 逐个转数组
    if isinstance(first, list):
        return [np.array(emb, dtype=np.float32) for emb in target]
```

---

### 3.3 BaseEmbeddingsProvider — 嵌入提供者抽象

**源码位置**：[core/base_embeddings_provider.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/rag/core/base_embeddings_provider.py)（24 行）

```python
class BaseEmbeddingsProvider(BaseSettings, Generic[T]):
    model_config = SettingsConfigDict(extra="allow", populate_by_name=True)
    embedding_callable: type[T] = Field(...)  # 嵌入函数类
```

**设计用意**：每个 Provider（如 OpenAIProvider）都继承这个基类，它告诉工厂"我对应哪个 embedding 函数类"。工厂调用 `provider.embedding_callable(**config)` 来创建实际的 embedding 函数。

**通俗理解**：BaseEmbeddingsProvider 是一张"说明书"，告诉系统"我这个 Provider 要用的 embedding 函数是哪个类，以及需要哪些配置参数"。

---

## 4. 底层（一）：ChromaDB 客户端实现

### 4.1 需求串讲

**问题**：ChromaDB 有同步和异步两种客户端 API，需要适配。文档需要批量处理（避免单次请求过大），需要跨进程锁保护。

**解决思路**：`ChromaDBClient` 封装 ChromaDB 的原生 API，提供同步/异步双版本，自动分批处理，加跨进程锁。

### 4.2 源码位置

[chromadb/client.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/rag/chromadb/client.py)（648 行）

### 4.3 核心组件

#### 组件 A：初始化 — 接收外部依赖

```python
class ChromaDBClient(BaseClient):
    def __init__(
        self, client, embedding_function,
        default_limit=5, default_score_threshold=0.6,
        default_batch_size=100, lock_name=""
    ):
        self.client = client                    # ChromaDB 原生客户端
        self.embedding_function = embedding_function  # embedding 函数
        self.default_limit = default_limit
        self.default_score_threshold = default_score_threshold
        self.default_batch_size = default_batch_size
        self._lock_name = lock_name             # 跨进程锁名
```

**关键设计**：`client` 和 `embedding_function` 是外部传入的，不在 `ChromaDBClient` 内部创建。这是"依赖注入"模式，让 `ChromaDBClient` 只负责操作，不负责创建。

#### 组件 B：跨进程锁

```python
def _locked(self) -> AbstractContextManager[None]:
    return store_lock(self._lock_name) if self._lock_name else nullcontext()

async def _alocked(self) -> AsyncIterator[None]:
    """异步锁通过在 executor 中运行同步锁实现"""
    lock_cm = store_lock(self._lock_name)
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, lock_cm.__enter__)
    try:
        yield
    finally:
        await loop.run_in_executor(None, lock_cm.__exit__, None, None, None)
```

**通俗理解**：就像多人同时操作一个文件，如果两个人同时写，文件会乱。锁保证同一时间只有一个人在操作。

#### 组件 C：`add_documents` — 添加文档（含批量处理）

```python
def add_documents(self, **kwargs):
    collection_name = kwargs["collection_name"]
    documents = kwargs["documents"]
    batch_size = kwargs.get("batch_size", self.default_batch_size)

    with self._locked():  # 加锁
        # 1. 获取或创建 collection
        collection = self.client.get_or_create_collection(
            name=_sanitize_collection_name(collection_name),
            embedding_function=self.embedding_function,
        )
        # 2. 准备文档（自动生成 ID、处理 metadata）
        prepared = _prepare_documents_for_chromadb(documents)
        # 3. 分批 upsert（避免单次请求过大）
        for i in range(0, len(prepared.ids), batch_size):
            batch_ids, batch_texts, batch_metadatas = _create_batch_slice(
                prepared=prepared, start_index=i, batch_size=batch_size
            )
            collection.upsert(
                ids=batch_ids,
                documents=batch_texts,
                metadatas=batch_metadatas,
            )
```

**批量处理流程**：

```
add_documents(documents=[1000个文档])
  │
  ├── _prepare_documents_for_chromadb()
  │     ├── 为每个文档自动生成 ID（SHA256 哈希）
  │     └── 提取 metadata
  │
  ├── batch_size = 100
  │
  ├── 第1批: 文档 0-99   → collection.upsert(...)
  ├── 第2批: 文档 100-199 → collection.upsert(...)
  ├── ...
  └── 第10批: 文档 900-999 → collection.upsert(...)
```

**为什么需要分批**：ChromaDB 的 embedding 计算有 token 限制，一次传太多文档会超限。

#### 组件 D：`search` — 向量搜索

```python
def search(self, **kwargs):
    # 1. 提取搜索参数
    params = _extract_search_params(kwargs)
    # 2. 获取 collection
    collection = self.client.get_or_create_collection(
        name=_sanitize_collection_name(params.collection_name),
        embedding_function=self.embedding_function,
    )
    # 3. 执行查询
    results: QueryResult = collection.query(
        query_texts=[params.query],
        n_results=params.limit,
        where=params.metadata_filter,  # 元数据过滤
        where_document=params.where_document,
        include=params.include,
    )
    # 4. 处理结果，过滤 score_threshold
    return _process_query_results(collection, results, params)
```

**搜索流程**：

```
search(collection_name="my_kb", query="什么是AI", limit=5, score_threshold=0.6)
  │
  ├── 1. sanitize 集合名 → "my_kb"
  ├── 2. get_or_create_collection("my_kb")
  ├── 3. collection.query(query_texts=["什么是AI"], n_results=5)
  │     └── ChromaDB 内部：
  │           ├── embedding_function("什么是AI") → [0.1, 0.3, ...]
  │           ├── 计算余弦相似度
  │           └── 返回最相似的 5 个文档
  ├── 4. _process_query_results()
  │     └── 过滤 score < 0.6 的结果
  └── 5. 返回 list[SearchResult]
```

---

## 5. 底层（二）：Embedding 嵌入层

### 5.1 需求串讲

**问题**：有 18 种 embedding 提供商（OpenAI、Google、Cohere、HuggingFace、Ollama、Jina、VoyageAI 等），每个提供商的 API 不同。如何统一管理？

**解决思路**：用工厂模式。`build_embedder(spec)` 根据 `spec` 中的 `provider` 字段，动态找到对应的 Provider 类，创建 embedding 函数。

### 5.2 源码位置

[embeddings/factory.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/rag/embeddings/factory.py)（379 行）

### 5.3 核心方法：`build_embedder`

```python
def build_embedder(spec):
    # 如果 spec 已经是 Provider 实例 → 直接构建
    if isinstance(spec, BaseEmbeddingsProvider):
        return build_embedder_from_provider(spec)
    # 如果 spec 是字典 → 先找到 Provider 类，再构建
    return build_embedder_from_dict(spec)
```

#### `build_embedder_from_dict` — 字典到 embedding 函数

```python
def build_embedder_from_dict(spec):
    provider_name = spec["provider"]  # 如 "openai"
    provider_path = PROVIDER_PATHS[provider_name]  # 查找类路径
    provider_class = import_and_validate_definition(provider_path)  # 动态导入
    provider_config = spec.get("config", {})
    provider = provider_class(**provider_config)  # 创建 Provider 实例
    return build_embedder_from_provider(provider)  # 构建 embedding 函数
```

**PROVIDER_PATHS 映射表**（部分）：

```python
PROVIDER_PATHS = {
    "openai":         "crewai.rag.embeddings.providers.openai.openai_provider.OpenAIProvider",
    "google":         "crewai.rag.embeddings.providers.google.generative_ai.GenerativeAiProvider",
    "cohere":         "crewai.rag.embeddings.providers.cohere.cohere_provider.CohereProvider",
    "huggingface":    "crewai.rag.embeddings.providers.huggingface...",
    "ollama":         "crewai.rag.embeddings.providers.ollama...",
    "sentence-transformer": "crewai.rag.embeddings.providers.sentence_transformer...",
    "voyageai":       "crewai.rag.embeddings.providers.voyageai...",
    "jina":           "crewai.rag.embeddings.providers.jina...",
    "azure":          "crewai.rag.embeddings.providers.microsoft.azure...",
    "amazon-bedrock": "crewai.rag.embeddings.providers.aws.bedrock...",
    "onnx":           "crewai.rag.embeddings.providers.onnx...",
    "openclip":       "crewai.rag.embeddings.providers.openclip...",
    "text2vec":       "crewai.rag.embeddings.providers.text2vec...",
    "watsonx":        "crewai.rag.embeddings.providers.ibm.watsonx...",
    "instructor":     "crewai.rag.embeddings.providers.instructor...",
    "roboflow":       "crewai.rag.embeddings.providers.roboflow...",
    "custom":         "crewai.rag.embeddings.providers.custom...",
    "google-vertex":  "crewai.rag.embeddings.providers.google.vertex...",
}
```

**使用示例**：

```python
# 方式1：字典配置
embedder = build_embedder({
    "provider": "openai",
    "config": {
        "api_key": "sk-...",
        "model_name": "text-embedding-3-small"
    }
})

# 方式2：Provider 实例
provider = OpenAIProvider(api_key="sk-...", model_name="text-embedding-3-small")
embedder = build_embedder(provider)
```

---

## 6. 支撑层：Config / Types / Storage

### 6.1 BaseRagConfig — 配置基类

**源码位置**：[config/base.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/rag/config/base.py)（19 行）

```python
@pyd_dataclass(frozen=True)
class BaseRagConfig:
    provider: SupportedProvider       # "chromadb" | "qdrant"
    embedding_function: Any | None    # embedding 函数
    limit: int = 5                    # 默认返回 5 条
    score_threshold: float = 0.6       # 默认相似度阈值 0.6
    batch_size: int = 100             # 默认批量大小 100
```

**注意**：`frozen=True` 表示配置对象是不可变的，创建后不能修改。这保证了配置的一致性和线程安全。

### 6.2 ChromaDBConfig — ChromaDB 专用配置

**源码位置**：[chromadb/config.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/rag/chromadb/config.py)（78 行）

```python
@pyd_dataclass(frozen=True)
class ChromaDBConfig(BaseRagConfig):
    provider: Literal["chromadb"] = "chromadb"
    tenant: str = DEFAULT_TENANT
    database: str = DEFAULT_DATABASE
    settings: Settings = _default_settings()  # 持久化目录、是否允许重置等
    embedding_function: ChromaEmbeddingFunctionWrapper = _default_embedding_function()
```

**默认设置**：

```python
def _default_settings():
    return Settings(
        persist_directory="./chroma_db",  # 持久化存储目录
        allow_reset=True,                  # 允许重置
        is_persistent=True,                # 数据持久化
        anonymized_telemetry=False,        # 不发送遥测数据
    )
```

### 6.3 config/utils.py — 全局 RAG 上下文管理

**源码位置**：[config/utils.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/rag/config/utils.py)（86 行）

**需求串讲**：多个模块（knowledge、memory）可能都需要使用同一个 RAG 客户端，但不想每次都创建新实例。需要一个全局的 RAG 客户端管理器。

**解决思路**：使用 `contextvars` 存储全局 RAG 配置和客户端实例。

```python
_rag_context: ContextVar[RagContext | None] = ContextVar("_rag_context", default=None)

def set_rag_config(config: RagConfigType) -> None:
    """设置全局 RAG 配置（并创建客户端）"""
    client = create_client(config)
    _rag_context.set(RagContext(config=config, client=client))

def get_rag_client() -> BaseClient:
    """获取全局 RAG 客户端（懒加载）"""
    context = _rag_context.get()
    if context is None:
        get_rag_config()  # 自动创建默认配置
        context = _rag_context.get()
    if context and context.client is None:
        context.client = create_client(context.config)
    return context.client
```

**关键设计**：`get_rag_client()` 在首次调用时自动创建默认配置和客户端，后续调用直接返回缓存的实例。这就是"懒加载 + 单例"模式。

### 6.4 types.py — 核心类型定义

**源码位置**：[types.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/rag/types.py)（49 行）

```python
class BaseRecord(TypedDict, total=False):
    doc_id: str          # 文档 ID（可选，不提供则自动生成）
    content: Required[str]  # 文档内容（必填）
    metadata: Mapping | list  # 元数据

class SearchResult(TypedDict):
    id: str              # 文档 ID
    content: str         # 文档内容
    metadata: dict[str, Any]  # 元数据
    score: float         # 相似度分数（0-1）
```

### 6.5 BaseRAGStorage — 旧版兼容层

**源码位置**：[storage/base_rag_storage.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/rag/storage/base_rag_storage.py)（55 行）

这是旧版 API 的兼容层，现在已被 `BaseClient` 协议替代。保留它只是为了向后兼容。

---

## 7. 完整调用链路

### 场景一：knowledge 模块使用 RAG

```
用户代码:
  kb = Knowledge(
      collection_name="my_kb",
      sources=[PDFKnowledgeSource(file_paths=["doc.pdf"])],
      embedder={"provider": "openai", "config": {"model": "text-embedding-3-small"}},
  )

═══════════════════════════════════════════════════════════════
第1步：Knowledge 初始化 → 创建 KnowledgeStorage
═══════════════════════════════════════════════════════════════

KnowledgeStorage.__init__(embedder={"provider": "openai", ...}, collection_name="my_kb")
  │
  └── _init_client()
        │
        ├── build_embedder({"provider": "openai", "config": {...}})
        │     │
        │     └── build_embedder_from_dict()
        │           ├── provider_name = "openai"
        │           ├── provider_path = "crewai.rag.embeddings.providers.openai..."
        │           ├── import_and_validate_definition(provider_path)
        │           │     └── 动态导入 OpenAIProvider 类
        │           ├── provider = OpenAIProvider(api_key="sk-...", model_name="text-embedding-3-small")
        │           └── build_embedder_from_provider(provider)
        │                 └── provider.embedding_callable(**config)
        │                       └── OpenAIEmbeddingFunction(api_key="sk-...", model_name="text-embedding-3-small")
        │
        ├── config = ChromaDBConfig(embedding_function=openai_embedding_fn)
        │     └── provider="chromadb", settings=Settings(persist_directory="./chroma_db")
        │
        └── create_client(config)
              ├── config.provider == "chromadb" → Yes
              ├── require("crewai.rag.chromadb.factory")
              └── chromadb.factory.create_client(config)
                    ├── PersistentClient(path="./chroma_db", settings=...)
                    └── ChromaDBClient(
                          client=persistent_client,
                          embedding_function=openai_embedding_fn,
                          default_limit=5,
                          default_score_threshold=0.6,
                          default_batch_size=100,
                          lock_name="chromadb:./chroma_db",
                        )

═══════════════════════════════════════════════════════════════
第2步：kb.add_sources() → 保存文档
═══════════════════════════════════════════════════════════════

kb.add_sources()
  └── source.add()
        └── _save_documents()
              └── storage.save(chunks)  # KnowledgeStorage.save()
                    │
                    └── _get_client() → ChromaDBClient
                          │
                          └── add_documents(collection_name="knowledge_my_kb", documents=[...])
                                ├── _prepare_documents_for_chromadb()
                                │     └── 自动生成 doc_id, 提取 metadata
                                ├── get_or_create_collection("knowledge_my_kb")
                                └── 分批 upsert (batch_size=100)

═══════════════════════════════════════════════════════════════
第3步：kb.query() → 搜索
═══════════════════════════════════════════════════════════════

kb.query(["什么是 AI"])
  └── storage.search(["什么是 AI"], limit=5, score_threshold=0.6)
        └── _get_client() → ChromaDBClient
              └── search(collection_name="knowledge_my_kb", query="什么是 AI", limit=5)
                    ├── get_or_create_collection("knowledge_my_kb")
                    ├── collection.query(query_texts=["什么是 AI"], n_results=5)
                    └── _process_query_results()
                          └── 过滤 score < 0.6 的结果
                          └── 返回 list[SearchResult]
```

### 场景二：全局 RAG 客户端（懒加载）

```
第一次调用 get_rag_client():
  │
  ├── _rag_context.get() → None
  ├── get_rag_config()
  │     ├── require("crewai.rag.chromadb.config", "RAG configuration")
  │     ├── ChromaDBConfig()  # 默认配置
  │     └── set_rag_config(config)
  │           └── create_client(config) → ChromaDBClient
  └── 返回 ChromaDBClient

第二次调用 get_rag_client():
  │
  ├── _rag_context.get() → RagContext(config=..., client=ChromaDBClient)
  └── 直接返回缓存的 ChromaDBClient（不创建新实例！）
```

---

## 总结

### 模块文件清单

```
lib/crewai/src/crewai/rag/
├── __init__.py
├── factory.py                    # 客户端工厂路由（78 行）
├── types.py                      # 核心类型定义（49 行）
├── core/
│   ├── base_client.py            # BaseClient 协议（448 行）
│   ├── base_embeddings_provider.py  # 嵌入提供者抽象（24 行）
│   ├── base_embeddings_callable.py  # 嵌入函数协议 + 自动包装（150 行）
│   ├── types.py                  # 核心类型（29 行）
│   └── exceptions.py
├── chromadb/
│   ├── client.py                 # ChromaDB 客户端实现（648 行）
│   ├── config.py                 # ChromaDB 配置（78 行）
│   ├── factory.py                # ChromaDB 客户端工厂（43 行）
│   ├── types.py
│   ├── constants.py
│   └── utils.py                  # 辅助函数
├── qdrant/                       # Qdrant 客户端（结构同 ChromaDB）
├── embeddings/
│   ├── factory.py                # Embedding 工厂（379 行）
│   ├── types.py                  # 类型定义（74 行）
│   └── providers/                # 18 种 embedding 提供商
│       ├── openai/               # OpenAI
│       ├── google/               # Google (GenerativeAI + VertexAI)
│       ├── cohere/               # Cohere
│       ├── huggingface/          # HuggingFace
│       ├── ollama/               # Ollama
│       ├── voyageai/             # VoyageAI
│       ├── jina/                 # Jina
│       ├── microsoft/            # Azure
│       ├── aws/                  # Amazon Bedrock
│       ├── ibm/                  # IBM WatsonX
│       ├── instructor/           # Instructor
│       ├── sentence_transformer/ # SentenceTransformer
│       ├── onnx/                 # ONNX
│       ├── openclip/             # OpenCLIP
│       ├── roboflow/             # Roboflow
│       ├── text2vec/             # Text2Vec
│       └── custom/               # 自定义
├── config/
│   ├── base.py                   # 配置基类（19 行）
│   ├── types.py                  # 配置类型（36 行）
│   ├── utils.py                  # 全局 RAG 上下文管理（86 行）
│   ├── constants.py
│   └── optional_imports/         # 可选依赖处理
└── storage/
    └── base_rag_storage.py       # 旧版兼容层（55 行）
```

### 设计亮点总结

| 设计 | 作用 | 行号 |
|------|------|------|
| Protocol 协议（非 ABC） | 支持结构化子类型，无需显式继承 | [base_client.py#L67](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/rag/core/base_client.py#L67) |
| `__init_subclass__` 自动包装 | 嵌入函数自动归一化+校验 | [base_embeddings_callable.py#L129](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/rag/core/base_embeddings_callable.py#L129) |
| 工厂路由 + 可注册 | 支持内置 + 自定义向量数据库 | [factory.py#L41](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/rag/factory.py#L41) |
| 18 种 embedding 提供商 | 覆盖主流嵌入服务 | [embeddings/factory.py#L90](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/rag/embeddings/factory.py#L90) |
| 批量 upsert | 避免单次请求过大 | [chromadb/client.py#L349](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/rag/chromadb/client.py#L349) |
| 跨进程锁 | 多进程并发安全 | [chromadb/client.py#L78](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/rag/chromadb/client.py#L78) |
| contextvars 全局懒加载 | 单例 RAG 客户端，按需创建 | [config/utils.py#L26](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/rag/config/utils.py#L26) |
| 延迟导入 | 模块加载时不报错 | [factory.py#L61](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/rag/factory.py#L61) |
| frozen 配置 | 不可变配置，线程安全 | [config/base.py#L11](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/rag/config/base.py#L11) |