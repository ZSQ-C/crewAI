# 阶段 H：knowledge/ + rag/ — 知识检索与RAG实现逻辑详解

## 1. 模块定位与架构图

CrewAI 的 `knowledge/` 模块负责知识的加载、分块、向量化存储和检索，是 Agent 获取外部知识（文档、文本、数据文件）的核心通道。`rag/` 模块则提供底层的向量数据库客户端抽象（ChromaDB 默认，Qdrant 可选）和 Embedding 提供者工厂，是知识检索的底层基础设施。

### 架构分层

```
┌─────────────────────────────────────────────────────────────────┐
│                    Agent / Task / Crew                           │
│          (通过 knowledge_sources 参数注入知识)                     │
├─────────────────────────────────────────────────────────────────┤
│              Knowledge 类 (knowledge.py)                         │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  • sources 管理 (list[BaseKnowledgeSource])               │   │
│  │  • query() / aquery() — 同步/异步检索                     │   │
│  │  • add_sources() / aadd_sources() — 加载知识到向量库       │   │
│  │  • reset() / areset() — 清空知识库                        │   │
│  │  • _resolve_knowledge_sources() — 字典→类型实例自动转换     │   │
│  └──────────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────┤
│          知识源层 (source/)                                       │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  BaseKnowledgeSource (ABC) — 分块策略、存储绑定            │   │
│  │    ├─ BaseFileKnowledgeSource (ABC) — 文件路径处理         │   │
│  │    │   ├─ PDFKnowledgeSource   (pdfplumber)               │   │
│  │    │   ├─ CSVKnowledgeSource   (csv.reader)               │   │
│  │    │   ├─ JSONKnowledgeSource  (json.load + 递归展开)      │   │
│  │    │   ├─ TextFileKnowledgeSource (直接读取)               │   │
│  │    │   ├─ ExcelKnowledgeSource (openpyxl)                 │   │
│  │    │   └─ CrewDoclingSource   (docling 文档解析)           │   │
│  │    └─ StringKnowledgeSource — 纯文本字符串                  │   │
│  └──────────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────┤
│          存储层 (storage/)                                        │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  BaseKnowledgeStorage (ABC) — 抽象接口                    │   │
│  │    └─ KnowledgeStorage — ChromaDB 集成实现                 │   │
│  │         • _client: BaseClient (ChromaDB/Qdrant 适配)      │   │
│  │         • embedder → build_embedder() → 嵌入函数           │   │
│  │         • search/asearch / save/asave / reset/areset      │   │
│  │  factory.py — set_knowledge_storage_factory() 可插拔工厂   │   │
│  └──────────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────┤
│          配置层                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  KnowledgeConfig — results_limit (默认5), score_threshold │   │
│  └──────────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────┤
│          RAG 基础设施 (rag/)                                      │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  rag/factory.py — create_client() 工厂分发                │   │
│  │    ├─ chromadb → ChromaDBConfig + ChromaClient            │   │
│  │    └─ qdrant   → QdrantConfig   + QdrantClient            │   │
│  │  rag/embeddings/factory.py — build_embedder()             │   │
│  │    ├─ 20+ 嵌入提供者 (openai, cohere, ollama, onnx, ...)  │   │
│  │    └─ ProviderSpec dict / BaseEmbeddingsProvider 实例      │   │
│  │  rag/types.py — BaseRecord, SearchResult 类型定义          │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 核心设计思想

1. **关注点分离**：`Knowledge` 负责编排，`BaseKnowledgeSource` 子类负责加载和分块，`KnowledgeStorage` 负责向量化存储和检索，`rag/` 负责底层向量数据库和嵌入模型适配。
2. **可插拔架构**：存储后端和嵌入提供者都通过工厂模式注册，支持自定义扩展。
3. **同步/异步双通道**：所有核心操作（add、query、reset）都提供同步和异步两种实现。
4. **字典自动转换**：`Knowledge` 接收 `sources` 参数时，通过 `_resolve_knowledge_sources()` 自动将 `{"source_type": "pdf", ...}` 字典转换为对应的 `BaseKnowledgeSource` 子类实例。

---

## 2. 核心实现逻辑详解

### 2.1 Knowledge 类 — 知识管理

**源码位置**：`lib/crewai/src/crewai/knowledge/knowledge.py`

`Knowledge` 是知识管理系统的入口类，继承自 Pydantic `BaseModel`。它聚合了知识源（sources）、存储后端（storage）和嵌入配置（embedder），对外暴露检索和加载接口。

#### 2.1.1 已知源类型注册表（第23-31行）

```python
_KNOWN_SOURCES: dict[str, type[BaseKnowledgeSource]] = {
    "string": StringKnowledgeSource,
    "docling": CrewDoclingSource,
    "csv": CSVKnowledgeSource,
    "excel": ExcelKnowledgeSource,
    "json": JSONKnowledgeSource,
    "pdf": PDFKnowledgeSource,
    "text_file": TextFileKnowledgeSource,
}
```

这是一个模块级字典，记录了所有内置的 `source_type` 字符串到具体 `BaseKnowledgeSource` 子类的映射。当用户以字典形式传入 `source_type` 时，`_resolve_knowledge_sources()` 函数会查此表进行实例化。

#### 2.1.2 字典自动解析函数（第34-63行）

`_resolve_knowledge_sources()` 是 Pydantic 的 `BeforeValidator`，在 `sources` 字段赋值前自动调用。核心逻辑：

- **第39行**：如果传入的不是 `list`，直接透传（pass-through）。
- **第43-62行**：遍历列表中的每一项：
  - 如果是 `dict`（第43行），提取 `source_type` 键（第44行）。
  - 查 `_KNOWN_SOURCES` 表获取对应的类（第48行），找不到则抛出 `ValueError` 并列出所有可用类型（第50-53行）。
  - 调用 `cls.model_validate(item)` 进行 Pydantic 验证和实例化（第55行），失败则包装为 `ValueError`（第57-60行）。
  - 如果不是 `dict`（如已经是 `BaseKnowledgeSource` 实例），直接保留（第62行）。

这允许用户用两种方式传入知识源：
```python
# 方式1：字典声明式
Knowledge(sources=[{"source_type": "pdf", "file_paths": "doc.pdf"}])

# 方式2：直接实例化
Knowledge(sources=[PDFKnowledgeSource(file_paths="doc.pdf")])
```

#### 2.1.3 embedder 序列化（第69-85行）

`_serialize_embedder_spec()` 配合 Pydantic 的 `PlainSerializer` 在序列化（如 checkpoint）时处理 embedder 的三种情况：
- `None` → 返回 `None`（第70-71行）
- `BaseEmbeddingsProvider` 实例 → 调用 `model_dump(mode="json")` 序列化（第72-73行）
- `dict` → 直接返回（第74-75行）
- `type`（类而非实例）→ 抛出 `TypeError` 提示用户需要实例化（第76-80行）

#### 2.1.4 类定义与字段（第88-109行）

```python
class Knowledge(BaseModel):
    sources: Annotated[
        list[BaseKnowledgeSource],
        BeforeValidator(_resolve_knowledge_sources),
    ] = Field(default_factory=list)
    model_config = ConfigDict(arbitrary_types_allowed=True)
    storage: BaseKnowledgeStorage | None = Field(default=None)
    embedder: Annotated[
        EmbedderConfig | None,
        PlainSerializer(_serialize_embedder_spec, ...),
    ] = None
    collection_name: str | None = None
```

关键设计：
- `sources` 的 `BeforeValidator` 确保字典自动转换。
- `model_config = ConfigDict(arbitrary_types_allowed=True)` 允许 Pydantic 模型持有非标准类型（如 `BaseKnowledgeStorage`、`np.ndarray` 等）。
- `storage` 和 `embedder` 默认为 `None`，在 `__init__` 中延迟初始化。

#### 2.1.5 构造函数（第111-133行）

```python
def __init__(self, collection_name: str, sources: list[BaseKnowledgeSource],
             embedder: EmbedderConfig | None = None,
             storage: BaseKnowledgeStorage | None = None, **data):
```

初始化逻辑：
1. 调用 `super().__init__(**data)` 触发 Pydantic 验证（第119行）。
2. **storage 决策**（第120-132行）：
   - 如果用户显式传入了 `storage`，直接使用（第120-121行）。
   - 否则，调用 `resolve_knowledge_storage()` 检查是否有全局注册的自定义工厂（第125行）。
   - 如果工厂返回了自定义存储，使用它；否则使用默认的 `KnowledgeStorage`，传入 `embedder` 和 `collection_name`（第126-132行）。
3. 将 `sources` 赋值给 `self.sources`（第133行）。

#### 2.1.6 query — 同步检索（第135-152行）

```python
def query(self, query: list[str], results_limit: int = 5,
          score_threshold: float = 0.6) -> list[SearchResult]:
```

- 参数 `query` 是 `list[str]`，支持多查询字符串（第136行）。
- 校验 `storage` 不为 `None`（第145-146行）。
- 委托给 `self.storage.search(query, limit=results_limit, score_threshold=score_threshold)`（第148-152行）。
- 返回 `list[SearchResult]`，每个 `SearchResult` 包含 `id`、`content`、`metadata`、`score` 四个字段（定义在 `rag/types.py` 第32-49行）。

#### 2.1.7 add_sources — 加载知识到向量库（第154-160行）

遍历所有 `self.sources`，对每个 source：
1. 设置 `source.storage = self.storage`（第157行）—— 将当前 Knowledge 的存储后端注入到每个 source。
2. 调用 `source.add()`（第158行）—— 触发该 source 的内容加载、分块、嵌入计算和保存。

#### 2.1.8 aquery / aadd_sources / areset（异步版本）（第167-205行）

异步版本与同步版本逻辑完全一致，区别在于调用 `storage.asearch()`、`source.aadd()`、`storage.areset()` 等异步方法。

---

### 2.2 BaseKnowledgeSource — 知识源基类

**源码位置**：`lib/crewai/src/crewai/knowledge/source/base_knowledge_source.py`

`BaseKnowledgeSource` 是所有知识源的抽象基类，继承自 `BaseModel` 和 `ABC`。它定义了分块策略、存储绑定和文档保存的通用逻辑。

#### 2.2.1 字段定义（第16-29行）

```python
class BaseKnowledgeSource(BaseModel, ABC):
    chunk_size: int = 4000        # 每个分块的最大字符数
    chunk_overlap: int = 200      # 相邻分块之间的重叠字符数
    chunks: list[str] = Field(default_factory=list)
    chunk_embeddings: list[np.ndarray] = Field(default_factory=list, exclude=True)
    storage: BaseKnowledgeStorage | None = Field(default=None)
    metadata: dict[str, Any] = Field(default_factory=dict)
    collection_name: str | None = Field(default=None)
```

关键设计：
- `chunk_size=4000` 和 `chunk_overlap=200`：默认分块策略，子类可以覆盖。
- `chunk_embeddings` 使用 `exclude=True`，在序列化时排除（避免序列化大型 numpy 数组）。
- `storage` 字段：在 `Knowledge.add_sources()` 中被注入，用于保存分块后的文档。

#### 2.2.2 抽象方法（第31-37行、第63-65行）

三个抽象方法，子类必须实现：

| 方法 | 签名 | 作用 |
|------|------|------|
| `validate_content()` | `-> Any` | 验证加载的内容有效性 |
| `add()` | `-> None` | 同步：加载内容 → 分块 → 嵌入 → 保存 |
| `aadd()` | `-> None` | 异步：同上，异步版本 |

#### 2.2.3 _chunk_text — 分块策略（第43-48行）

```python
def _chunk_text(self, text: str) -> list[str]:
    return [
        text[i : i + self.chunk_size]
        for i in range(0, len(text), self.chunk_size - self.chunk_overlap)
    ]
```

这是一个**固定大小滑动窗口**分块算法：
- 步长 = `chunk_size - chunk_overlap` = 4000 - 200 = 3800
- 每个 chunk 长度为 `chunk_size`（4000字符），相邻 chunk 之间有 200 字符的重叠
- 重叠的目的是保证语义边界不会被切断，提升检索质量

**示例**：对于 8000 字符的文本，会产生：
- chunk[0]：字符 0-3999
- chunk[1]：字符 3800-7799
- chunk[2]：字符 7600-8000（最后一块可能小于 chunk_size）

#### 2.2.4 _save_documents — 保存到存储（第50-61行）

```python
def _save_documents(self) -> None:
    if self.storage is not None:
        self.storage.save(self.chunks)
    else:
        raise ValueError("No storage found to save documents.")
```

直接将 `self.chunks`（分块后的文本列表）传给 `storage.save()`。注意：`KnowledgeStorage.save()` 内部会将每个 chunk 包装为 `BaseRecord` 格式（`{"content": doc}`），然后调用底层 RAG 客户端的 `add_documents`。

#### 2.2.5 文件源基类 BaseFileKnowledgeSource

**源码位置**：`lib/crewai/src/crewai/knowledge/source/base_file_knowledge_source.py`

继承自 `BaseKnowledgeSource`，为所有文件类知识源提供通用能力：

- **文件路径处理**（第17-23行、第89-116行）：
  - 支持 `file_path`（已废弃，兼容保留）和 `file_paths` 两种参数。
  - `_process_file_paths()` 将各种输入格式统一转换为 `list[Path]`。
  - `convert_to_path()` 对字符串路径自动添加 `KNOWLEDGE_DIRECTORY` 前缀（第87行）。
  
- **内容加载流程**（第44-48行 `model_post_init`）：
  1. `_process_file_paths()` → 解析文件路径
  2. `validate_content()` → 验证文件存在
  3. `load_content()` → 子类实现，加载文件内容为 `dict[Path, str]`

- **抽象方法 `load_content()`**（第50-52行）：每个子类实现自己的文件解析逻辑。

#### 2.2.6 各知识源子类加载逻辑

| 子类 | 文件路径 | `load_content()` 实现 |
|------|---------|----------------------|
| **StringKnowledgeSource** | `source/string_knowledge_source.py:8-41` | 无需加载，直接使用 `self.content` 字符串 |
| **PDFKnowledgeSource** | `source/pdf_knowledge_source.py:13-28` | 使用 `pdfplumber` 逐页提取文本，拼接 `\n` |
| **CSVKnowledgeSource** | `source/csv_knowledge_source.py:13-23` | 使用 `csv.reader` 逐行读取，空格连接列值 |
| **JSONKnowledgeSource** | `source/json_knowledge_source.py:13-35` | `json.load` + `_json_to_text()` 递归展开为缩进文本 |
| **TextFileKnowledgeSource** | `source/text_file_knowledge_source.py:12-19` | `open(path).read()` 直接读取 |
| **ExcelKnowledgeSource** | `source/excel_knowledge_source.py` | 使用 `openpyxl` 读取工作表 |
| **CrewDoclingSource** | `source/crew_docling_source.py` | 使用 `docling` 库解析多种文档格式 |

所有子类的 `add()` 方法模式一致：遍历 `self.content` 的值 → 调用 `_chunk_text()` 分块 → `chunks.extend()` 追加 → `_save_documents()` 保存。

---

### 2.3 KnowledgeStorage — 知识存储

**源码位置**：`lib/crewai/src/crewai/knowledge/storage/knowledge_storage.py`

`KnowledgeStorage` 继承自 `BaseKnowledgeStorage`（抽象基类，定义在 `storage/base_knowledge_storage.py`），是知识存储的默认实现，底层使用 ChromaDB 作为向量数据库。

#### 2.3.1 字段定义（第28-35行）

```python
class KnowledgeStorage(BaseKnowledgeStorage):
    collection_name: str | None = None
    embedder: ProviderSpec | BaseEmbeddingsProvider | type[BaseEmbeddingsProvider] | None
        = Field(default=None, exclude=True)
    _client: BaseClient | None = PrivateAttr(default=None)
```

- `embedder`：支持三种类型 — `ProviderSpec`（字典）、`BaseEmbeddingsProvider` 实例、或 `BaseEmbeddingsProvider` 子类。`exclude=True` 避免序列化。
- `_client`：Pydantic `PrivateAttr`，不在模型字段中暴露，用于持有底层 RAG 客户端实例。

#### 2.3.2 _init_client — 模型验证器初始化客户端（第37-53行）

```python
@model_validator(mode="after")
def _init_client(self) -> Self:
```

在 Pydantic 模型验证完成后自动调用：
1. **第39-43行**：抑制 ChromaDB 的废弃警告。
2. **第45-46行**：如果 `self.embedder` 不为空，调用 `build_embedder(self.embedder)` 创建嵌入函数。
3. **第47-50行**：用嵌入函数创建 `ChromaDBConfig`。
4. **第52行**：调用 `create_client(config)` 创建 RAG 客户端（ChromaDB 或 Qdrant）。

#### 2.3.3 _get_client — 客户端获取策略（第55-57行）

```python
def _get_client(self) -> BaseClient:
    return self._client if self._client else get_rag_client()
```

优先使用实例自己的 `_client`（如果有配置 embedder），否则回退到全局 RAG 客户端（`get_rag_client()`，用于内存系统等场景）。

#### 2.3.4 search — 同步检索（第59-89行）

```python
def search(self, query: list[str], limit: int = 5,
           metadata_filter: dict | None = None,
           score_threshold: float = 0.6) -> list[SearchResult]:
```

核心流程：
1. **第67-68行**：校验 `query` 不为空。
2. **第70行**：获取 RAG 客户端。
3. **第71-75行**：构建 collection 名称 — 格式为 `knowledge_{collection_name}`，如果未指定 collection_name 则使用 `"knowledge"`。
4. **第76行**：将多查询字符串合并为一个查询文本（空格连接）。
5. **第78-84行**：调用 `client.search()` 执行向量检索。
6. **第85-89行**：异常处理 — 捕获所有异常，记录日志，返回空列表（优雅降级）。

#### 2.3.5 save — 同步保存（第105-136行）

```python
def save(self, documents: list[str]) -> None:
```

核心流程：
1. **第106-107行**：如果 `documents` 为空，直接返回。
2. **第110-115行**：获取客户端，构建 collection 名称，调用 `client.get_or_create_collection()` 确保 collection 存在。
3. **第118行**：将每个文档字符串包装为 `BaseRecord` 格式：`[{"content": doc} for doc in documents]`。
4. **第120-122行**：调用 `client.add_documents()` 存入向量数据库。
5. **第123-136行**：特殊错误处理 —
   - 如果是 `dimension mismatch` 错误（第124行），提示用户可能是切换了嵌入模型导致维度不匹配，建议执行 `crewai reset-memories -a` 重置（第125-129行）。
   - 其他错误记录日志并重新抛出（第135-136行）。

#### 2.3.6 reset — 清空知识库（第91-103行）

调用 `client.delete_collection(collection_name)` 删除整个 collection，实现知识库的清空。

#### 2.3.7 异步版本（第138-231行）

`asearch`、`asave`、`areset` 三个异步方法，逻辑与同步版本完全一致，调用的是客户端的异步方法（`client.asearch`、`client.aget_or_create_collection`、`client.aadd_documents`、`client.adelete_collection`）。

#### 2.3.8 存储工厂可插拔机制

**源码位置**：`lib/crewai/src/crewai/knowledge/storage/factory.py`

```python
KnowledgeStorageFactory = Callable[
    ["EmbedderConfig | None", "str | None"], "BaseKnowledgeStorage | None"
]

def set_knowledge_storage_factory(factory: KnowledgeStorageFactory | None) -> None:
    global _factory
    _factory = factory

def resolve_knowledge_storage(embedder, collection_name) -> BaseKnowledgeStorage | None:
    factory = _factory
    return factory(embedder, collection_name) if factory is not None else None
```

这是一个进程级全局注册机制：
- 应用启动时调用 `set_knowledge_storage_factory(my_factory)` 注册自定义存储工厂。
- `Knowledge.__init__` 中调用 `resolve_knowledge_storage()` 检查是否有自定义工厂。
- 工厂返回 `None` 时回退到默认 `KnowledgeStorage`。
- 传入 `None` 可恢复默认行为。

---

### 2.4 KnowledgeConfig — 知识配置

**源码位置**：`lib/crewai/src/crewai/knowledge/knowledge_config.py`

```python
class KnowledgeConfig(BaseModel):
    results_limit: int = Field(default=5, description="The number of results to return")
    score_threshold: float = Field(
        default=0.6,
        description="The minimum score for a result to be considered relevant",
    )
```

这是一个简单的 Pydantic 配置模型，只有两个字段：

| 字段 | 类型 | 默认值 | 含义 |
|------|------|--------|------|
| `results_limit` | `int` | `5` | 每次检索返回的最大文档数 |
| `score_threshold` | `float` | `0.6` | 相似度阈值，低于此分数的结果被过滤 |

这两个参数贯穿整个检索链路：
- `Knowledge.query()` 的 `results_limit` 和 `score_threshold` 参数 → `KnowledgeStorage.search()` → `client.search()`。
- 在 Agent/Task 中，可以通过 `KnowledgeConfig` 配置这些参数，影响知识检索的召回量和精度。

---

### 2.5 RAG Factory — RAG 工厂

**源码位置**：`lib/crewai/src/crewai/rag/factory.py`

RAG 工厂负责根据配置创建向量数据库客户端，支持 ChromaDB 和 Qdrant 两种后端，同时支持自定义扩展。

#### 2.5.1 工厂注册机制（第20-38行）

```python
RagClientFactory = Callable[[RagConfigType], BaseClient]
_factories: dict[str, RagClientFactory] = {}

def register_rag_client_factory(provider: str, factory: RagClientFactory) -> None:
    _factories[provider] = factory

def unregister_rag_client_factory(provider: str) -> None:
    _factories.pop(provider, None)
```

- `RagClientFactory` 是一个可调用类型：接收 `RagConfigType` 配置，返回 `BaseClient`。
- `_factories` 字典以 provider 名称为键，存储注册的工厂函数。
- 注册的工厂优先级高于内置实现（第55-56行）。

#### 2.5.2 create_client — 核心分发函数（第41-78行）

```python
def create_client(config: RagConfigType) -> BaseClient:
```

分发逻辑：
1. **第54-56行**：先查注册表 `_factories`，如果找到注册的工厂，直接调用。
2. **第58-66行**：如果 `config.provider == "chromadb"`，使用 `require()` 延迟导入 `crewai.rag.chromadb.factory`，调用其 `create_client(config)`。
3. **第68-76行**：如果 `config.provider == "qdrant"`，延迟导入 `crewai.rag.qdrant.factory`，调用其 `create_client(config)`。
4. **第78行**：其他 provider 抛出 `ValueError`。

使用 `require()` 延迟导入的好处是：只有在实际需要某个 provider 时才加载对应的依赖，避免强制安装所有向量数据库的 SDK。

#### 2.5.3 ChromaDBConfig 配置

**源码位置**：`lib/crewai/src/crewai/rag/chromadb/config.py`

```python
@pyd_dataclass(frozen=True)
class ChromaDBConfig(BaseRagConfig):
    provider: Literal["chromadb"] = "chromadb"
    tenant: str = DEFAULT_TENANT
    database: str = DEFAULT_DATABASE
    settings: Settings = field(default_factory=_default_settings)
    embedding_function: ChromaEmbeddingFunctionWrapper = field(
        default_factory=_default_embedding_function
    )
```

- `_default_settings()`（第34-45行）：创建持久化 ChromaDB 设置，启用 `allow_reset` 和 `is_persistent`。
- `_default_embedding_function()`（第48-65行）：默认使用 OpenAI 的 `text-embedding-3-small` 模型，通过 `OPENAI_API_KEY` 环境变量认证。

#### 2.5.4 build_embedder — 嵌入函数工厂

**源码位置**：`lib/crewai/src/crewai/rag/embeddings/factory.py`

`build_embedder()` 支持两种输入（第352-375行）：
1. **`BaseEmbeddingsProvider` 实例**（第373行）→ 调用 `build_embedder_from_provider()`，直接调用 `provider.embedding_callable(**config)` 创建嵌入函数。
2. **`dict`（ProviderSpec）**（第375行）→ 调用 `build_embedder_from_dict()`，从字典中提取 `provider` 和 `config` 键，查 `PROVIDER_PATHS` 表找到对应的 Provider 类，实例化后创建嵌入函数。

支持的嵌入提供者（`PROVIDER_PATHS`，第90-110行）共 20+ 种：

| Provider | 模块路径 |
|----------|---------|
| `openai` | `crewai.rag.embeddings.providers.openai.OpenAIProvider` |
| `azure` | `crewai.rag.embeddings.providers.microsoft.azure.AzureProvider` |
| `ollama` | `crewai.rag.embeddings.providers.ollama.OllamaProvider` |
| `cohere` | `crewai.rag.embeddings.providers.cohere.CohereProvider` |
| `huggingface` | `crewai.rag.embeddings.providers.huggingface.HuggingFaceProvider` |
| `google` / `google-generativeai` | `...google.generative_ai.GenerativeAiProvider` |
| `google-vertex` | `...google.vertex.VertexAIProvider` |
| `amazon-bedrock` | `...aws.bedrock.BedrockProvider` |
| `sentence-transformer` | `...sentence_transformer.SentenceTransformerProvider` |
| `jina` | `...jina.JinaProvider` |
| `voyageai` | `...voyageai.VoyageAIProvider` |
| `watsonx` | `...ibm.watsonx.WatsonXProvider` |
| `onnx`、`instructor`、`text2vec`、`openclip`、`roboflow`、`custom` | ... |

---

## 3. 完整调用时序图

### 3.1 知识加载与检索全流程

```
用户代码                 Knowledge           BaseKnowledgeSource      KnowledgeStorage        RAG Factory/Client
  │                        │                        │                       │                       │
  │  Knowledge(            │                        │                       │                       │
  │    collection_name,    │                        │                       │                       │
  │    sources=[...],      │                        │                       │                       │
  │    embedder=...)       │                        │                       │                       │
  │───────────────────────>│                        │                       │                       │
  │                        │                        │                       │                       │
  │                        │ __init__()             │                       │                       │
  │                        │─── resolve_knowledge_storage(embedder, name) ──>│                       │
  │                        │                        │                       │                       │
  │                        │                        │    KnowledgeStorage.__init__()                │
  │                        │                        │──────────────────────>│                       │
  │                        │                        │                       │ _init_client()        │
  │                        │                        │                       │── build_embedder() ──>│
  │                        │                        │                       │<── embedding_fn ──────│
  │                        │                        │                       │── create_client() ───>│
  │                        │                        │                       │<── BaseClient ────────│
  │                        │                        │                       │                       │
  │                        │                        │                       │                       │
  │  knowledge.add_sources()                        │                       │                       │
  │───────────────────────>│                        │                       │                       │
  │                        │                        │                       │                       │
  │                        │  for source in sources:│                       │                       │
  │                        │    source.storage = storage                     │                       │
  │                        │    source.add() ──────>│                       │                       │
  │                        │                        │                       │                       │
  │                        │                        │ load_content()        │                       │
  │                        │                        │── 读取文件/解析内容    │                       │
  │                        │                        │                       │                       │
  │                        │                        │ _chunk_text(text)     │                       │
  │                        │                        │── 滑动窗口分块        │                       │
  │                        │                        │   chunks = [...]      │                       │
  │                        │                        │                       │                       │
  │                        │                        │ _save_documents()     │                       │
  │                        │                        │──────────────────────>│                       │
  │                        │                        │                       │                       │
  │                        │                        │                       │ save(chunks)          │
  │                        │                        │                       │── get_or_create_col() │
  │                        │                        │                       │── add_documents() ───>│
  │                        │                        │                       │                       │
  │                        │                        │                       │                       │
  │  knowledge.query(["..."])                       │                       │                       │
  │───────────────────────>│                        │                       │                       │
  │                        │                        │                       │                       │
  │                        │ storage.search(query) ────────────────────────>│                       │
  │                        │                        │                       │                       │
  │                        │                        │                       │ _get_client()         │
  │                        │                        │                       │ client.search() ─────>│
  │                        │                        │                       │<── SearchResult[] ────│
  │                        │<── SearchResult[] ────────────────────────────│                       │
  │<── list[SearchResult] ─│                        │                       │                       │
```

### 3.2 embedder 配置链路

```
用户代码: embedder={"provider": "openai", "config": {"api_key": "sk-...", "model_name": "..."}}
                             │
                             ▼
Knowledge.__init__(embedder=...)  → 透传给 KnowledgeStorage
                             │
                             ▼
KnowledgeStorage._init_client()
  └─ build_embedder(self.embedder)            # rag/embeddings/factory.py:352
       └─ build_embedder_from_dict(spec)       # 第223行
            ├─ provider_name = spec["provider"]  # "openai"
            ├─ 查 PROVIDER_PATHS → "crewai.rag.embeddings.providers.openai.OpenAIProvider"
            ├─ import_and_validate_definition() → OpenAIProvider 类
            ├─ provider = OpenAIProvider(**spec["config"])
            └─ build_embedder_from_provider(provider)
                 └─ provider.embedding_callable(**provider.model_dump())
                      → OpenAIEmbeddingFunction 实例
                             │
                             ▼
ChromaDBConfig(embedding_function=OpenAIEmbeddingFunction)
                             │
                             ▼
create_client(ChromaDBConfig)                  # rag/factory.py:41
  └─ config.provider == "chromadb"
       └─ chromadb_mod.create_client(config)    # rag/chromadb/factory.py
            → ChromaDB Client (PersistentClient)
```

---

## 4. 完整可运行示例

### 示例 1：使用 StringKnowledgeSource 进行文本知识检索

```python
"""示例 1：使用 StringKnowledgeSource 加载文本知识并检索"""
import os

# 设置 OpenAI API Key（如果使用默认 OpenAI embedding）
os.environ["OPENAI_API_KEY"] = "sk-your-api-key"

from crewai.knowledge.knowledge import Knowledge
from crewai.knowledge.source.string_knowledge_source import StringKnowledgeSource

# 创建知识源 — 直接传入文本内容
source = StringKnowledgeSource(
    content="CrewAI is a framework for orchestrating AI agents. "
            "It supports role-based agents, task delegation, and tool integration. "
            "Knowledge sources allow agents to access external documents and data. "
            "The RAG (Retrieval-Augmented Generation) system uses ChromaDB for vector storage. "
            "Embeddings can be generated using OpenAI, Cohere, Ollama, or local models."
)

# 创建 Knowledge 实例
knowledge = Knowledge(
    collection_name="my_docs",
    sources=[source],
    embedder={
        "provider": "openai",
        "config": {
            "api_key": os.environ["OPENAI_API_KEY"],
            "model_name": "text-embedding-3-small",
        },
    },
)

# 加载知识到向量库
knowledge.add_sources()
print("知识已加载到向量库")

# 检索知识
results = knowledge.query(
    query=["What framework is used for AI agents?"],
    results_limit=3,
)

for i, result in enumerate(results):
    print(f"\n结果 {i+1}:")
    print(f"  内容: {result['content'][:100]}...")
    print(f"  相似度: {result['score']:.4f}")

# 清理
knowledge.reset()
```

### 示例 2：使用 PDFKnowledgeSource 读取 PDF 文件

```python
"""示例 2：使用 PDFKnowledgeSource 加载 PDF 文档"""
import os
os.environ["OPENAI_API_KEY"] = "sk-your-api-key"

from crewai.knowledge.knowledge import Knowledge
from crewai.knowledge.source.pdf_knowledge_source import PDFKnowledgeSource

# 创建 PDF 知识源
# 注意：pdfplumber 是可选依赖，需要 pip install pdfplumber
source = PDFKnowledgeSource(
    file_paths=["path/to/document.pdf"],  # 替换为实际 PDF 路径
    chunk_size=2000,   # 自定义分块大小
    chunk_overlap=200,  # 自定义重叠大小
)

knowledge = Knowledge(
    collection_name="pdf_docs",
    sources=[source],
    embedder={
        "provider": "openai",
        "config": {
            "api_key": os.environ["OPENAI_API_KEY"],
            "model_name": "text-embedding-3-small",
        },
    },
)

# 加载 PDF 内容到向量库
knowledge.add_sources()
print(f"PDF 已加载，共 {len(source.chunks)} 个分块")

# 检索
results = knowledge.query(
    query=["summarize the key points"],
    results_limit=5,
    score_threshold=0.5,
)

for result in results:
    print(f"[{result['score']:.4f}] {result['content'][:80]}...")

knowledge.reset()
```

### 示例 3：使用 CSV 和 JSON 知识源

```python
"""示例 3：使用 CSVKnowledgeSource 和 JSONKnowledgeSource"""
import os
os.environ["OPENAI_API_KEY"] = "sk-your-api-key"

from crewai.knowledge.knowledge import Knowledge
from crewai.knowledge.source.csv_knowledge_source import CSVKnowledgeSource
from crewai.knowledge.source.json_knowledge_source import JSONKnowledgeSource

# 创建 CSV 知识源
csv_source = CSVKnowledgeSource(
    file_paths=["data/products.csv"],  # CSV 文件路径
)

# 创建 JSON 知识源
json_source = JSONKnowledgeSource(
    file_paths=["data/config.json"],  # JSON 文件路径
)

# 同时加载多个不同类型的知识源
knowledge = Knowledge(
    collection_name="multi_source",
    sources=[csv_source, json_source],
    embedder={
        "provider": "openai",
        "config": {
            "api_key": os.environ["OPENAI_API_KEY"],
            "model_name": "text-embedding-3-small",
        },
    },
)

knowledge.add_sources()
print(f"CSV: {len(csv_source.chunks)} 分块, JSON: {len(json_source.chunks)} 分块")

# 跨源检索
results = knowledge.query(
    query=["product pricing information", "configuration settings"],
    results_limit=10,
)

for r in results:
    print(f"[{r['score']:.4f}] {r['content'][:100]}...")

knowledge.reset()
```

### 示例 4：使用字典声明式配置知识源

```python
"""示例 4：使用字典声明式配置 — 无需手动实例化 Source 类"""
import os
os.environ["OPENAI_API_KEY"] = "sk-your-api-key"

from crewai.knowledge.knowledge import Knowledge

# 直接用字典列表声明知识源，_resolve_knowledge_sources 自动转换
knowledge = Knowledge(
    collection_name="docs",
    sources=[
        {
            "source_type": "string",
            "content": "CrewAI uses Pydantic for data validation and configuration management.",
        },
        {
            "source_type": "string",
            "content": "ChromaDB is the default vector store for knowledge retrieval in CrewAI.",
        },
        {
            "source_type": "text_file",
            "file_paths": ["path/to/readme.txt"],
        },
    ],
    embedder={
        "provider": "openai",
        "config": {
            "api_key": os.environ["OPENAI_API_KEY"],
            "model_name": "text-embedding-3-small",
        },
    },
)

knowledge.add_sources()
print(f"加载了 {len(knowledge.sources)} 个知识源")

results = knowledge.query(
    query=["vector database", "data validation"],
    results_limit=5,
)

for r in results:
    print(f"[{r['score']:.4f}] {r['content'][:80]}...")

knowledge.reset()
```

### 示例 5：自定义存储后端 + 异步检索

```python
"""示例 5：自定义存储工厂 + 异步操作"""
import os
import asyncio
os.environ["OPENAI_API_KEY"] = "sk-your-api-key"

from crewai.knowledge.knowledge import Knowledge
from crewai.knowledge.storage.base_knowledge_storage import BaseKnowledgeStorage
from crewai.knowledge.storage.knowledge_storage import KnowledgeStorage
from crewai.knowledge.storage.factory import set_knowledge_storage_factory


# 方式 1：注册自定义存储工厂（进程级全局）
def custom_storage_factory(embedder, collection_name):
    """自定义存储工厂：可以在这里添加日志、监控等逻辑"""
    print(f"[Factory] 创建存储: collection={collection_name}")
    # 返回 None 表示使用默认 KnowledgeStorage
    # 返回自定义实例则使用自定义存储
    return None  # 这里回退到默认

set_knowledge_storage_factory(custom_storage_factory)


async def main():
    from crewai.knowledge.source.string_knowledge_source import StringKnowledgeSource

    source = StringKnowledgeSource(
        content="Async operations allow non-blocking knowledge retrieval "
                "and loading in CrewAI."
    )

    # 方式 2：直接传入自定义 storage 实例
    custom_storage = KnowledgeStorage(
        collection_name="async_demo",
        embedder={
            "provider": "openai",
            "config": {
                "api_key": os.environ["OPENAI_API_KEY"],
                "model_name": "text-embedding-3-small",
            },
        },
    )

    knowledge = Knowledge(
        collection_name="async_demo",
        sources=[source],
        storage=custom_storage,  # 使用自定义存储实例
    )

    # 异步加载
    await knowledge.aadd_sources()
    print("异步加载完成")

    # 异步检索
    results = await knowledge.aquery(
        query=["non-blocking operations"],
        results_limit=3,
    )

    for r in results:
        print(f"[{r['score']:.4f}] {r['content']}")

    # 异步清理
    await knowledge.areset()

asyncio.run(main())
```

---

## 5. 设计亮点与注意事项

### 设计亮点

1. **字典自动转换（`_resolve_knowledge_sources`）**
   - 位置：`knowledge.py` 第34-63行
   - 用户可以用 `{"source_type": "pdf", "file_paths": "..."}` 字典声明知识源，无需手动导入和实例化对应的 Source 类。这极大简化了 YAML/JSON 配置场景下的知识源定义。
   - 通过 `_KNOWN_SOURCES` 注册表（第23-31行）实现类型分发，新增源类型只需在表中注册。

2. **可插拔的三层架构**
   - **存储层**：`set_knowledge_storage_factory()`（`storage/factory.py` 第36-44行）允许全局替换默认存储后端。
   - **RAG 客户端层**：`register_rag_client_factory()`（`rag/factory.py` 第25-33行）允许注册自定义 provider。
   - **嵌入层**：`build_embedder()`（`rag/embeddings/factory.py` 第352行）支持 20+ 嵌入提供者，并支持 `custom` provider 类型（第259行）。
   - 每一层都可以独立替换，无需修改核心代码。

3. **同步/异步双通道**
   - 所有关键操作都有 `xxx()` 和 `axxx()` 两个版本：
     - `Knowledge`：`query`/`aquery`、`add_sources`/`aadd_sources`、`reset`/`areset`
     - `BaseKnowledgeSource`：`add`/`aadd`、`_save_documents`/`_asave_documents`
     - `KnowledgeStorage`：`search`/`asearch`、`save`/`asave`、`reset`/`areset`
   - 异步版本在 agent 并发执行场景下可以避免阻塞事件循环。

4. **优雅的错误处理**
   - `KnowledgeStorage.search()`（第85-89行）在检索失败时返回空列表而非抛出异常，保证 Agent 不会因知识检索故障而崩溃。
   - `KnowledgeStorage.save()`（第124-134行）对 `dimension mismatch` 错误提供明确的诊断信息和修复建议。
   - `BaseFileKnowledgeSource.validate_content()`（第54-70行）在文件不存在时提供清晰的错误信息。

5. **延迟导入（Lazy Import）**
   - `rag/factory.py` 使用 `require()` 函数延迟导入 ChromaDB 和 Qdrant 的工厂模块（第59-65行、第69-76行）。
   - `rag/embeddings/factory.py` 使用 `import_and_validate_definition()` 延迟导入嵌入提供者（第253行）。
   - 好处：不会强制安装所有可选依赖，按需加载节省启动时间。

6. **分块策略的语义保留**
   - `_chunk_text()`（`base_knowledge_source.py` 第43-48行）使用 `chunk_overlap=200` 的重叠窗口，确保相邻分块之间有语义连续性。
   - 默认 `chunk_size=4000` 适合大多数 embedding 模型的上下文窗口，子类可覆盖。

### 注意事项

1. **embedder 必须传实例而非类**
   - `knowledge.py` 第76-80行：如果传入 `BaseEmbeddingsProvider` 的子类（而非实例），会抛出 `TypeError`。这是因为 `build_embedder` 需要 provider 实例来调用 `model_dump()` 提取配置参数。

2. **collection_name 命名约定**
   - `KnowledgeStorage` 内部自动在 `collection_name` 前添加 `knowledge_` 前缀（`knowledge_storage.py` 第71-75行）。如果用户传入 `collection_name="my_docs"`，实际的 ChromaDB collection 名称是 `knowledge_my_docs`。

3. **embedder 与 storage 的绑定时机**
   - `KnowledgeStorage` 的 embedder 在 `_init_client()`（`model_validator`，第37-53行）中初始化，这意味着 embedder 在 Pydantic 模型验证后就确定，后续无法动态更换。
   - 如果需要更换 embedder，必须创建新的 `KnowledgeStorage` 实例。

4. **维度不匹配问题**
   - 如果先后使用不同 embedding 模型向同一个 collection 写入数据，ChromaDB 会抛出 `dimension mismatch` 错误（`knowledge_storage.py` 第124行）。解决方案是调用 `knowledge.reset()` 清空 collection 后重新加载。

5. **文件路径处理**
   - `BaseFileKnowledgeSource.convert_to_path()`（第85-87行）对字符串路径自动添加 `KNOWLEDGE_DIRECTORY` 前缀。如果文件不在该目录下，应使用绝对路径或 `Path` 对象。

6. **TOKENIZERS_PARALLELISM 环境变量**
   - `knowledge.py` 第66行设置 `os.environ["TOKENIZERS_PARALLELISM"] = "false"`，禁用 HuggingFace tokenizers 的多进程并行，避免在子进程中出现死锁问题。

7. **chunk_embeddings 字段的特殊处理**
   - `base_knowledge_source.py` 第22-23行：`chunk_embeddings` 使用 `exclude=True`，在序列化时被排除。这意味着 checkpoint 时不会保存嵌入向量，恢复时需要重新计算。