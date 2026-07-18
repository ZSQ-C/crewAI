# CrewAI Knowledge 模块 — 深度源码实现分析

> 面向小白，逐层逐方法拆解 `lib/crewai/src/crewai/knowledge/` 的全部实现逻辑

---

## 目录

- [0. 整体概述：这个模块要解决什么问题](#0-整体概述这个模块要解决什么问题)
- [1. 三层架构总览](#1-三层架构总览)
- [2. 顶层：`knowledge.py` — Knowledge 类（用户入口）](#2-顶层knowledgepy--knowledge-类用户入口)
- [3. 中层：Source 抽象层](#3-中层source-抽象层)
- [4. 底层（一）：7 种 Source 具体实现](#4-底层一7-种-source-具体实现)
- [5. 底层（二）：Storage 存储层](#5-底层二storage-存储层)
- [6. 支撑层：Config / SourceHelper / knowledge_utils](#6-支撑层config--sourcehelper--knowledge_utils)
- [7. 完整调用链路（从用户代码到知识检索结果）](#7-完整调用链路从用户代码到知识检索结果)

---

## 0. 整体概述：这个模块要解决什么问题

### 需求串讲

想象你是一个新入职的员工，公司有大量文档：Word 文档、PDF 手册、Excel 表格、CSV 数据、JSON 配置。老板问你一个问题，你需要去这些文档里找答案。如果每次都要手动翻文档，效率极低。

CrewAI 的 Knowledge 模块就是你的"智能文档助手"。你把各种文件扔给它，它会把文件内容切成小块，转成向量（数字表示），存到向量数据库里。以后你问问题，它会找到最相关的内容片段返回给你。

**核心流程**：文件 → 加载内容 → 切分（chunk）→ 转向量（embedding）→ 存入向量数据库 → 查询时搜索最相似片段

**通俗理解**：就像把一本书的每一页拍成照片，然后存到相册里。以后你想找"关于猫的内容"，不需要翻整本书，只需要在相册中搜索"猫"相关的照片即可。

---

## 1. 三层架构总览

```
┌──────────────────────────────────────────────────────────────┐
│                    顶层：knowledge.py                         │
│                   Knowledge 类（用户入口）                      │
│   "用户把数据源给我，我帮你管理全流程"                            │
│   提供：query() 查询、add_sources() 添加、reset() 重置          │
├──────────────────────────────────────────────────────────────┤
│                    中层：Source 抽象层                         │
│   ┌─────────────────────────────────────────────────────┐    │
│   │  BaseKnowledgeSource（抽象基类）                       │    │
│   │  - 定义 chunk_size / chunk_overlap 参数               │    │
│   │  - 提供 _chunk_text() 文本切分工具                     │    │
│   │  - 定义 add() / aadd() 抽象方法                       │    │
│   │  - 提供 _save_documents() 保存方法                    │    │
│   ├─────────────────────────────────────────────────────┤    │
│   │  BaseFileKnowledgeSource（文件源基类）                  │    │
│   │  - 定义 file_path / file_paths 字段                   │    │
│   │  - 处理文件路径校验和转换                               │    │
│   │  - 定义 load_content() 抽象方法                       │    │
│   └─────────────────────────────────────────────────────┘    │
├──────────────────────────────────────────────────────────────┤
│                    底层：具体实现                              │
│   ┌──────────────────────┬──────────────────────────────┐    │
│   │  7 种 Source 实现      │   Storage 存储层              │    │
│   │  StringKnowledgeSource │  BaseKnowledgeStorage(抽象)  │    │
│   │  CSVKnowledgeSource    │  KnowledgeStorage(具体实现)   │    │
│   │  PDFKnowledgeSource    │  factory.py(存储工厂)        │    │
│   │  JSONKnowledgeSource   │                              │    │
│   │  ExcelKnowledgeSource  │  底层依赖：                    │    │
│   │  TextFileKnowledgeSrc  │  → crewai.rag (ChromaDB)     │    │
│   │  CrewDoclingSource     │  → embedding provider        │    │
│   └──────────────────────┴──────────────────────────────┘    │
├──────────────────────────────────────────────────────────────┤
│                    支撑层                                     │
│   knowledge_config.py  → 查询参数配置                         │
│   source_helper.py     → 文件类型→Source类映射                │
│   knowledge_utils.py   → 搜索结果格式化                       │
└──────────────────────────────────────────────────────────────┘
```

**调用关系图**：

```
用户代码
  │
  ▼
Knowledge(sources=[...], embedder=...)
  │
  ├── __init__()
  │     ├── resolve_knowledge_storage() → 检查是否有自定义存储工厂
  │     └── KnowledgeStorage() → 创建默认存储（ChromaDB + embedding）
  │
  ├── add_sources()
  │     │
  │     └── for source in sources:
  │           source.storage = self.storage   ← 注入存储后端
  │           source.add()
  │             │
  │             ├── load_content()    ← 加载文件内容
  │             ├── _chunk_text()     ← 切分成小块
  │             └── _save_documents()
  │                   └── storage.save(chunks)
  │                         └── client.add_documents()  ← 转向量+存入ChromaDB
  │
  └── query(["什么是AI?"])
        └── storage.search(query, limit=5)
              └── client.search()  ← 向量相似度搜索
                    └── 返回 list[SearchResult]
```

---

## 2. 顶层：`knowledge.py` — Knowledge 类（用户入口）

### 2.1 需求串讲

**问题**：用户有多种数据源（字符串、PDF、CSV、JSON 等），需要一个统一的入口来管理这些数据源，并能方便地查询。

**解决思路**：设计一个 `Knowledge` 类，它接收一个数据源列表和一个 embedding 配置，内部自动创建存储后端，提供 `query()`、`add_sources()`、`reset()` 三个核心方法。

**通俗理解**：`Knowledge` 就像一个"图书馆管理员"。你把资料交给他，他帮你分类、编目、上架。你想查资料时，告诉他关键词，他帮你找到最相关的资料。

### 2.2 源码位置

[knowledge.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/knowledge/knowledge.py)（205 行）

### 2.3 逐组件解析

---

#### 组件 A：已知数据源注册表

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

**解释**：这是一个"字典"，把字符串名字（如 `"pdf"`）映射到对应的 Python 类（如 `PDFKnowledgeSource`）。

**通俗理解**：就像快递站有一张"快递公司对照表"——看到"顺丰"就知道找顺丰快递员，看到"圆通"找圆通快递员。

**为什么需要这个表**：用户可以用字典格式配置数据源：
```python
Knowledge(
    sources=[{"source_type": "pdf", "file_paths": ["doc.pdf"]}],
    ...
)
```
`_resolve_knowledge_sources` 函数看到 `source_type="pdf"`，就查这张表，找到 `PDFKnowledgeSource` 类，然后用这个类来创建真正的数据源对象。

---

#### 组件 B：`_resolve_knowledge_sources` — 字典转数据源对象

```python
def _resolve_knowledge_sources(value: Any) -> Any:
    """把字典列表转成真正的 BaseKnowledgeSource 子类实例"""
    if not isinstance(value, list):
        return value
    resolved: list[Any] = []
    for idx, item in enumerate(value):
        if isinstance(item, dict):
            tag = item.get("source_type")        # 取出 "pdf" 这样的标记
            cls = _KNOWN_SOURCES.get(tag)         # 查到 PDFKnowledgeSource 类
            if cls is None:
                raise ValueError(f"Unknown source_type={tag!r}")
            resolved.append(cls.model_validate(item))  # 用类创建实例
        else:
            resolved.append(item)                 # 已经是实例，直接保留
    return resolved
```

**注意**：这个函数用了 Pydantic 的 `BeforeValidator`，意味着它在 `Knowledge` 对象创建之前自动执行。用户传字典也能自动转成对象。

**通俗理解**：就像你写"顺丰"在快递单上，快递系统自动帮你找到顺丰的快递员来取件。

---

#### 组件 C：`Knowledge.__init__` — 初始化（创建存储后端）

```python
def __init__(
    self,
    collection_name: str,              # 集合名称（必填），用于区分不同知识库
    sources: list[BaseKnowledgeSource], # 数据源列表
    embedder: EmbedderConfig | None = None,  # embedding 配置
    storage: BaseKnowledgeStorage | None = None,  # 自定义存储后端
    **data: object,
) -> None:
    super().__init__(**data)
    
    # 第1步：确定存储后端
    if storage is not None:
        self.storage = storage          # 用户传了自定义存储 → 用自定义的
    else:
        from crewai.knowledge.storage.factory import resolve_knowledge_storage
        custom = resolve_knowledge_storage(embedder, collection_name)
        self.storage = (
            custom
            if custom is not None
            else KnowledgeStorage(       # 都没有 → 创建默认存储
                embedder=embedder, collection_name=collection_name
            )
        )
    
    self.sources = sources               # 保存数据源列表
```

**初始化流程**：

```
Knowledge(collection_name="my_kb", sources=[...], embedder=...)
  │
  ├── storage 参数是否传入？
  │     ├── Yes → 直接用用户传入的 storage
  │     └── No  → resolve_knowledge_storage()
  │                 ├── 有注册的工厂函数？
  │                 │     ├── Yes → 调用工厂函数创建
  │                 │     └── No  → 返回 None
  │                 └── None → KnowledgeStorage(embedder, collection_name)
  │
  └── self.sources = sources
```

**通俗理解**：初始化就像一个房屋装修过程。你可以自己带装修队（`storage=`），也可以用物业推荐的装修队（工厂函数），都没有的话就用默认的装修队（`KnowledgeStorage`）。

---

#### 组件 D：`add_sources` — 添加数据源

```python
def add_sources(self) -> None:
    try:
        for source in self.sources:
            source.storage = self.storage   # 把存储后端注入到每个数据源
            source.add()                     # 让数据源执行"添加"流程
    except Exception as e:
        raise e
```

**关键点**：`source.storage = self.storage` 这一行非常重要。它把 `Knowledge` 实例的存储后端"注入"到每个数据源中。这样数据源在 `add()` 时就知道往哪里存数据了。

**通俗理解**：图书馆管理员（Knowledge）告诉每个资料处理员（Source）："处理完资料后，放到这个书架上（storage）"。

---

#### 组件 E：`query` — 查询知识

```python
def query(
    self, query: list[str], results_limit: int = 5, score_threshold: float = 0.6
) -> list[SearchResult]:
    """查询知识库"""
    if self.storage is None:
        raise ValueError("Storage is not initialized.")
    return self.storage.search(
        query,
        limit=results_limit,           # 最多返回 5 条结果
        score_threshold=score_threshold, # 相似度最低 0.6（60%）
    )
```

**参数解释**：
- `query: list[str]`：查询关键词列表，如 `["什么是 AI", "人工智能"]`
- `results_limit`：最多返回几条结果，默认 5
- `score_threshold`：相似度阈值，0.6 表示只返回相似度 ≥ 60% 的结果

**通俗理解**：你去图书馆管理员那里问"关于猫的书"，管理员（`query`）在书架（`storage`）上搜索，返回最相关的 5 本书，相关性低于 60% 的不返回。

---

## 3. 中层：Source 抽象层

### 3.1 需求串讲

**问题**：我们有 7 种不同的数据源（字符串、PDF、CSV、JSON、Excel、文本文件、Docling），每种数据源的加载方式不同，但处理流程相同：加载内容 → 切分 → 保存。如果每个数据源都写一遍切分和保存逻辑，代码会非常冗余。

**解决思路**：把公共逻辑（切分、保存）抽到 `BaseKnowledgeSource` 基类中，把文件相关的公共逻辑（路径处理、文件校验）抽到 `BaseFileKnowledgeSource` 中。子类只需要实现 `load_content()`（怎么加载）和 `add()`（怎么添加）。

**通俗理解**：就像快餐店，不管你点汉堡还是炸鸡，流程都是：接单 → 制作 → 打包。`BaseKnowledgeSource` 定义了"接单"和"打包"的标准流程，每个子类只负责"制作"这一步。

---

### 3.2 BaseKnowledgeSource — 最底层抽象基类

**源码位置**：[base_knowledge_source.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/knowledge/source/base_knowledge_source.py)（78 行）

#### 字段定义

```python
class BaseKnowledgeSource(BaseModel, ABC):
    chunk_size: int = 4000           # 每个文本块的大小（字符数）
    chunk_overlap: int = 200         # 块之间的重叠字符数
    chunks: list[str] = []           # 切分后的文本块
    chunk_embeddings: list[np.ndarray] = []  # 文本块的向量表示
    storage: BaseKnowledgeStorage | None = None  # 存储后端（由 Knowledge 注入）
    metadata: dict[str, Any] = {}    # 元数据
    collection_name: str | None = None  # 集合名称
```

#### 核心方法：`_chunk_text` — 文本切分

```python
def _chunk_text(self, text: str) -> list[str]:
    """把一段长文本切成小块"""
    return [
        text[i : i + self.chunk_size]
        for i in range(0, len(text), self.chunk_size - self.chunk_overlap)
    ]
```

**示例**：

```python
text = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"  # 26 个字符
chunk_size = 10
chunk_overlap = 3

# 切分过程：
# i=0:  text[0:10]   = "ABCDEFGHIJ"
# i=7:  text[7:17]   = "HIJKLMNOPQ"   ← 与上一块重叠 "HIJ"
# i=14: text[14:24]  = "OPQRSTUVWX"
# i=21: text[21:31]  = "VWXYZ"

# 结果：["ABCDEFGHIJ", "HIJKLMNOPQ", "OPQRSTUVWX", "VWXYZ"]
```

**为什么需要重叠（overlap）**：如果一句话正好被切在两块的边界上，没有重叠的话，这句话的语义就会丢失。重叠保证边界附近的句子同时出现在两块中，不会丢失上下文。

**通俗理解**：就像用剪刀把一根长绳子剪成小段，但每段之间留一点重叠，确保不会把绳结（关键信息）剪断。

#### 核心方法：`_save_documents` — 保存到存储

```python
def _save_documents(self) -> None:
    if self.storage is not None:
        self.storage.save(self.chunks)   # 委托给 storage 去保存
    else:
        raise ValueError("No storage found to save documents.")
```

**解释**：这个方法不直接操作数据库，而是委托给 `self.storage` 去保存。`self.storage` 是 `Knowledge` 在 `add_sources()` 中注入的。

**通俗理解**：资料处理员（Source）处理好资料后，交给图书管理员（Storage）去上架。

---

### 3.3 BaseFileKnowledgeSource — 文件源基类

**源码位置**：[base_file_knowledge_source.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/knowledge/source/base_file_knowledge_source.py)（116 行）

**需求串讲**：CSV、PDF、JSON、TextFile 等数据源都需要处理文件路径，如果每个子类都写一遍路径校验、路径转换的代码，非常冗余。

**解决思路**：在 `BaseKnowledgeSource` 和具体文件源之间加一层 `BaseFileKnowledgeSource`，专门处理文件相关的公共逻辑。

#### 字段定义

```python
class BaseFileKnowledgeSource(BaseKnowledgeSource, ABC):
    file_path: Path | list[Path] | str | list[str] | None = None   # 旧字段，已弃用
    file_paths: Path | list[Path] | str | list[str] | None = []    # 新字段
    content: dict[Path, str] = {}   # 加载后的内容 {文件路径: 文件内容}
    safe_file_paths: list[Path] = []  # 校验后的安全路径列表
```

#### 核心方法：`model_post_init` — 初始化流程

```python
def model_post_init(self, _: Any) -> None:
    self.safe_file_paths = self._process_file_paths()  # 第1步：处理路径
    self.validate_content()                             # 第2步：校验文件存在
    self.content = self.load_content()                  # 第3步：加载文件内容
```

**执行流程**：

```
model_post_init() 自动执行
  │
  ├── 1. _process_file_paths()
  │     ├── 检查 file_path（旧字段）→ 有则迁移到 file_paths
  │     ├── 检查 file_paths 是否为空 → 空则报错
  │     ├── 统一转成 list[Path]
  │     └── 每个路径调用 convert_to_path()
  │           └── 相对路径 → 加上 KNOWLEDGE_DIRECTORY 前缀
  │
  ├── 2. validate_content()
  │     └── 遍历 safe_file_paths
  │           ├── path.exists()? → 否则报 FileNotFoundError
  │           └── path.is_file()? → 否则报错
  │
  └── 3. load_content()  ← 子类实现，不同的文件类型加载方式不同
```

#### 核心方法：`convert_to_path` — 路径转换

```python
def convert_to_path(self, path: Path | str) -> Path:
    return Path(KNOWLEDGE_DIRECTORY + "/" + path) if isinstance(path, str) else path
```

**解释**：如果用户传的是字符串（相对路径），自动拼接上 `KNOWLEDGE_DIRECTORY`（默认是 `knowledge` 目录）。所以用户写 `"doc.pdf"` 等价于 `"knowledge/doc.pdf"`。

---

## 4. 底层（一）：7 种 Source 具体实现

### 4.1 需求串讲

不同文件类型需要不同的加载方式：
- **CSV**：用 Python 的 `csv` 模块按行读取
- **PDF**：用 `pdfplumber` 库提取文本
- **JSON**：用 `json` 模块加载，递归转成文本
- **Excel**：用 `pandas` 读取每个 sheet 转 CSV
- **文本文件**：直接 `open().read()`
- **字符串**：不需要加载文件，直接使用内容
- **Docling**：用 `docling` 库支持更多格式（PDF、DOCX、HTML、图片等）

---

### 4.2 StringKnowledgeSource — 字符串源

**源码位置**：[string_knowledge_source.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/knowledge/source/string_knowledge_source.py)（41 行）

**特点**：不是从文件加载，而是直接从字符串内容创建知识。

```python
class StringKnowledgeSource(BaseKnowledgeSource):
    source_type: Literal["string"] = "string"
    content: str = Field(...)  # 直接接收字符串
```

**add() 方法**：

```python
def add(self) -> None:
    new_chunks = self._chunk_text(self.content)  # 把字符串切成小块
    self.chunks.extend(new_chunks)               # 追加到 chunks 列表
    self._save_documents()                       # 保存
```

**使用示例**：

```python
source = StringKnowledgeSource(
    content="AI Safety 是人工智能领域的重要研究方向...",
    chunk_size=1000,
    chunk_overlap=100,
)
```

---

### 4.3 CSVKnowledgeSource — CSV 文件源

**源码位置**：[csv_knowledge_source.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/knowledge/source/csv_knowledge_source.py)（51 行）

**load_content() 方法**：

```python
def load_content(self) -> dict[Path, str]:
    content_dict = {}
    for file_path in self.safe_file_paths:
        with open(file_path, "r", encoding="utf-8") as csvfile:
            reader = csv.reader(csvfile)
            content = ""
            for row in reader:
                content += " ".join(row) + "\n"  # 每行用空格连接
            content_dict[file_path] = content
    return content_dict
```

**通俗理解**：CSV 文件每一行是一个记录，这个方法把每行的各个字段用空格拼起来，所有行拼成一个大字符串。

**示例**：

```
CSV 文件：
name,age,city
Alice,30,NYC
Bob,25,LA

加载后：
"name age city\nAlice 30 NYC\nBob 25 LA\n"
```

---

### 4.4 PDFKnowledgeSource — PDF 文件源

**源码位置**：[pdf_knowledge_source.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/knowledge/source/pdf_knowledge_source.py)（63 行）

**load_content() 方法**：

```python
def load_content(self) -> dict[Path, str]:
    pdfplumber = self._import_pdfplumber()  # 动态导入 pdfplumber 库
    content = {}
    for path in self.safe_file_paths:
        text = ""
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        content[path] = text
    return content
```

**关键设计**：`_import_pdfplumber()` 使用**延迟导入**。pdfplumber 不是必装依赖，只有在用户确实使用 PDF 源时才导入。如果没安装，会抛出一个友好的错误提示。

**通俗理解**：PDF 就像一本扫描版的书，pdfplumber 是一个"OCR 识别器"，把每一页的图片转成文字。

---

### 4.5 JSONKnowledgeSource — JSON 文件源

**源码位置**：[json_knowledge_source.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/knowledge/source/json_knowledge_source.py)（63 行）

**核心亮点**：`_json_to_text()` 递归转换方法

```python
def _json_to_text(self, data: Any, level: int = 0) -> str:
    text = ""
    indent = "  " * level
    if isinstance(data, dict):
        for key, value in data.items():
            text += f"{indent}{key}: {self._json_to_text(value, level + 1)}\n"
    elif isinstance(data, list):
        for item in data:
            text += f"{indent}- {self._json_to_text(item, level + 1)}\n"
    else:
        text += f"{data!s}"
    return text
```

**示例**：

```json
{
  "name": "AI Safety",
  "topics": ["Alignment", "Robustness"],
  "details": {"year": 2024, "status": "active"}
}
```

转换后：

```
name: AI Safety
topics: - Alignment
        - Robustness
details: year: 2024
         status: active
```

---

### 4.6 ExcelKnowledgeSource — Excel 文件源

**源码位置**：[excel_knowledge_source.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/knowledge/source/excel_knowledge_source.py)（181 行）

**特点**：Excel 可能有多个 Sheet（工作表），每个 Sheet 都要处理。

```python
def _load_content(self) -> dict[Path, dict[str, str]]:
    pd = self._import_dependencies()
    content_dict = {}
    for file_path in self.safe_file_paths:
        with pd.ExcelFile(file_path) as xl:
            sheet_dict = {
                str(sheet_name): str(
                    pd.read_excel(xl, sheet_name).to_csv(index=False)
                )
                for sheet_name in xl.sheet_names
            }
        content_dict[file_path] = sheet_dict
    return content_dict
```

**注意**：`ExcelKnowledgeSource` 直接继承 `BaseKnowledgeSource`（而不是 `BaseFileKnowledgeSource`），因为它的 `content` 类型是 `dict[Path, dict[str, str]]`（多了一层 Sheet），不能复用 `BaseFileKnowledgeSource` 的逻辑。

---

### 4.7 TextFileKnowledgeSource — 文本文件源

**源码位置**：[text_file_knowledge_source.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/knowledge/source/text_file_knowledge_source.py)（43 行）

最简单的实现，直接读取文件：

```python
def load_content(self) -> dict[Path, str]:
    content = {}
    for path in self.safe_file_paths:
        with open(path, "r", encoding="utf-8") as f:
            content[path] = f.read()
    return content
```

---

### 4.8 CrewDoclingSource — 通用文档源

**源码位置**：[crew_docling_source.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/knowledge/source/crew_docling_source.py)（192 行）

**特点**：使用 `docling` 库，支持更多格式：PDF、DOCX、HTML、图片、PPTX、XLSX、MD、AsciiDoc。

**支持的格式**：

```python
def _build_default_document_converter() -> DocumentConverter:
    docling = _import_docling()
    return docling.document_converter(
        allowed_formats=[
            MD,          # Markdown
            ASCIIDOC,    # AsciiDoc
            PDF,         # PDF
            DOCX,        # Word 文档
            HTML,        # 网页
            IMAGE,       # 图片（OCR）
            XLSX,        # Excel
            PPTX,        # PowerPoint
        ]
    )
```

**核心流程**：

```python
def add(self) -> None:
    for doc in self.content:
        new_chunks_iterable = self._chunk_doc(doc)  # 用 docling 的分块器
        self.chunks.extend(list(new_chunks_iterable))
    self._save_documents()

def _chunk_doc(self, doc: DoclingDocument) -> Iterator[str]:
    chunker = _import_docling().hierarchical_chunker()  # 层级分块器
    for chunk in chunker.chunk(doc):
        yield chunk.text
```

**与普通 PDF 源的区别**：`CrewDoclingSource` 使用 docling 的 `HierarchicalChunker`（层级分块器），它不仅按字符数切分，还会考虑文档的层级结构（标题、段落、列表），切分质量更高。

**还支持 URL**：

```python
def validate_content(self) -> list[Path | str]:
    for path in self.file_paths:
        if isinstance(path, str):
            if path.startswith(("http://", "https://")):
                if self._validate_url(path):
                    processed_paths.append(path)  # 直接传 URL！
```

---

## 5. 底层（二）：Storage 存储层

### 5.1 需求串讲

**问题**：知识数据需要存到向量数据库里，以便后续查询。但向量数据库有很多种（ChromaDB、Qdrant 等），需要一种灵活的方式支持切换。

**解决思路**：定义 `BaseKnowledgeStorage` 抽象接口，`KnowledgeStorage` 是默认实现（基于 ChromaDB），通过 `factory.py` 支持用户自定义存储后端。

---

### 5.2 BaseKnowledgeStorage — 存储抽象接口

**源码位置**：[base_knowledge_storage.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/knowledge/storage/base_knowledge_storage.py)（51 行）

```python
class BaseKnowledgeStorage(BaseModel, ABC):
    @abstractmethod
    def search(self, query, limit, metadata_filter, score_threshold) -> list[SearchResult]:
        """搜索知识"""

    @abstractmethod
    def save(self, documents: list[str]) -> None:
        """保存文档"""

    @abstractmethod
    def reset(self) -> None:
        """重置知识库"""
    
    # 以及对应的 async 版本：asearch, asave, areset
```

**设计模式**：这是经典的"面向接口编程"。通过定义抽象接口，具体的存储实现（ChromaDB、Qdrant 等）可以任意替换，只要它们实现了这些方法。

---

### 5.3 KnowledgeStorage — 默认存储实现（ChromaDB）

**源码位置**：[knowledge_storage.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/knowledge/storage/knowledge_storage.py)（232 行）

#### 初始化流程

```python
class KnowledgeStorage(BaseKnowledgeStorage):
    collection_name: str | None = None
    embedder: ProviderSpec | ... | None = None
    _client: BaseClient | None = PrivateAttr(default=None)

    @model_validator(mode="after")
    def _init_client(self) -> Self:
        if self.embedder:
            embedding_function = build_embedder(self.embedder)  # 构建 embedding 函数
            config = ChromaDBConfig(embedding_function=embedding_function)
            self._client = create_client(config)  # 创建 ChromaDB 客户端
        return self
```

**初始化流程**：

```
KnowledgeStorage(embedder=..., collection_name="my_kb")
  │
  ├── embedder 存在？
  │     ├── Yes → build_embedder(embedder)
  │     │         └── 比如 OpenAIEmbeddings("text-embedding-3-small")
  │     │     → ChromaDBConfig(embedding_function=...)
  │     │     → create_client(config)
  │     │         └── 创建 ChromaDB 客户端
  │     └── No  → _client 保持 None
  │
  └── 完成
```

#### 搜索方法

```python
def search(self, query, limit=5, metadata_filter=None, score_threshold=0.6):
    client = self._get_client()  # 获取客户端
    collection_name = f"knowledge_{self.collection_name}" if self.collection_name else "knowledge"
    query_text = " ".join(query) if len(query) > 1 else query[0]
    
    return client.search(
        collection_name=collection_name,
        query=query_text,
        limit=limit,
        metadata_filter=metadata_filter,
        score_threshold=score_threshold,
    )
```

**搜索流程**：

```
search(["什么是 AI", "AI 定义"], limit=5)
  │
  ├── 1. _get_client() → 获取 ChromaDB 客户端
  │
  ├── 2. 拼接查询文本："什么是 AI AI 定义"
  │
  ├── 3. client.search(
  │       collection_name="knowledge_my_kb",
  │       query="什么是 AI AI 定义",
  │       limit=5,
  │       score_threshold=0.6,
  │     )
  │     │
  │     └── ChromaDB 内部：
  │           ├── 把查询文本转成向量（用 embedding 函数）
  │           ├── 在向量空间中找到最相似的 5 个文档
  │           └── 返回相似度 ≥ 0.6 的结果
  │
  └── 4. 返回 list[SearchResult]
```

#### 保存方法

```python
def save(self, documents: list[str]) -> None:
    if not documents:
        return
    
    client = self._get_client()
    collection_name = f"knowledge_{self.collection_name}" if self.collection_name else "knowledge"
    
    # 确保 collection 存在
    client.get_or_create_collection(collection_name=collection_name)
    
    # 构建文档记录
    rag_documents: list[BaseRecord] = [{"content": doc} for doc in documents]
    
    # 添加文档（ChromaDB 会自动计算 embedding）
    client.add_documents(collection_name=collection_name, documents=rag_documents)
```

**通俗理解**：`save()` 就像把书放到书架上。ChromaDB 会自动给每本书贴上标签（embedding），以后查询时就能快速找到。

---

### 5.4 factory.py — 存储工厂

**源码位置**：[factory.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/knowledge/storage/factory.py)（56 行）

**需求串讲**：有些用户可能不想用 ChromaDB，想用 Qdrant 或其他向量数据库。但不可能让每个用户都去修改 `Knowledge` 类的源码。

**解决思路**：提供一个"工厂函数注册机制"。用户可以在应用启动时注册自己的存储后端工厂，之后所有 `Knowledge` 实例都会自动使用用户的自定义后端。

```python
# 全局变量，存储用户注册的工厂函数
_factory: KnowledgeStorageFactory | None = None

def set_knowledge_storage_factory(factory: KnowledgeStorageFactory | None) -> None:
    """注册自定义存储后端工厂"""
    global _factory
    _factory = factory

def resolve_knowledge_storage(
    embedder: EmbedderConfig | None, collection_name: str | None
) -> BaseKnowledgeStorage | None:
    """调用工厂函数，返回自定义存储后端（或 None 回退到默认）"""
    factory = _factory
    return factory(embedder, collection_name) if factory is not None else None
```

**使用场景**：

```python
# 在应用启动时注册
def my_qdrant_storage(embedder, collection_name):
    return QdrantKnowledgeStorage(embedder=embedder, collection_name=collection_name)

set_knowledge_storage_factory(my_qdrant_storage)

# 之后所有 Knowledge 实例都会使用 Qdrant
kb = Knowledge(collection_name="my_kb", sources=[...])
```

---

## 6. 支撑层：Config / SourceHelper / knowledge_utils

### 6.1 KnowledgeConfig — 查询参数配置

**源码位置**：[knowledge_config.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/knowledge/knowledge_config.py)（16 行）

```python
class KnowledgeConfig(BaseModel):
    results_limit: int = 5         # 默认返回 5 条结果
    score_threshold: float = 0.6    # 默认相似度阈值 60%
```

**作用**：Agent 可以配置自己的知识检索参数。比如某个 Agent 需要更多上下文，可以把 `results_limit` 调到 10。

---

### 6.2 SourceHelper — 文件类型到 Source 类的映射

**源码位置**：[source_helper.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/knowledge/source/utils/source_helper.py)（70 行）

```python
class SourceHelper:
    _FILE_TYPE_MAP: ClassVar[dict[str, type[BaseKnowledgeSource]]] = {
        ".csv": CSVKnowledgeSource,
        ".pdf": PDFKnowledgeSource,
        ".json": JSONKnowledgeSource,
        ".txt": TextFileKnowledgeSource,
        ".xlsx": ExcelKnowledgeSource,
        ".xls": ExcelKnowledgeSource,
    }

    @classmethod
    def get_source(cls, file_path: str, metadata=None) -> BaseKnowledgeSource:
        """根据文件扩展名自动创建对应的 Source 实例"""
        for ext, source_cls in cls._FILE_TYPE_MAP.items():
            if file_path.lower().endswith(ext):
                return source_cls(file_path=[file_path], metadata=metadata)
```

**使用场景**：用户只需要提供文件路径，不用手动指定 Source 类型：

```python
# 自动根据扩展名选择 Source
source = SourceHelper.get_source("data.pdf")   # → PDFKnowledgeSource
source = SourceHelper.get_source("data.csv")   # → CSVKnowledgeSource
source = SourceHelper.get_source("data.xlsx")  # → ExcelKnowledgeSource
```

---

### 6.3 knowledge_utils.py — 搜索结果格式化

**源码位置**：[knowledge_utils.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/knowledge/utils/knowledge_utils.py)（12 行）

```python
def extract_knowledge_context(knowledge_snippets: list[SearchResult]) -> str:
    """把搜索结果格式化为 Agent 可以理解的文本"""
    valid_snippets = [
        result["content"]
        for result in knowledge_snippets
        if result and result.get("content")
    ]
    snippet = "\n".join(valid_snippets)
    return f"Additional Information: {snippet}" if valid_snippets else ""
```

**示例**：

```python
# 输入
results = [
    {"content": "AI Safety 是人工智能安全研究领域"},
    {"content": "对齐问题是 AI Safety 的核心"},
]

# 输出
extract_knowledge_context(results)
# → "Additional Information: AI Safety 是人工智能安全研究领域\n对齐问题是 AI Safety 的核心"
```

**作用**：把搜索结果拼成一段文本，注入到 Agent 的 Prompt 中，让 Agent 基于这些知识回答问题。

---

## 7. 完整调用链路（从用户代码到知识检索结果）

### 7.1 场景一：添加知识源

```
用户代码:
  kb = Knowledge(
      collection_name="my_kb",
      sources=[PDFKnowledgeSource(file_paths=["doc.pdf"])],
      embedder={"provider": "openai", "config": {"model": "text-embedding-3-small"}},
  )

═══════════════════════════════════════════════════════════════
第1步：创建 Knowledge 实例
═══════════════════════════════════════════════════════════════

Knowledge.__init__()
  │
  ├── storage 参数？→ 未传入
  │
  ├── resolve_knowledge_storage(embedder, "my_kb")
  │     └── _factory 为 None → 返回 None
  │
  ├── KnowledgeStorage(embedder=..., collection_name="my_kb")
  │     │
  │     └── _init_client()
  │           ├── build_embedder({"provider": "openai", ...})
  │           │     └── 创建 OpenAIEmbeddings 实例
  │           ├── ChromaDBConfig(embedding_function=...)
  │           └── create_client(config)
  │                 └── 创建 ChromaDB 客户端
  │
  └── self.sources = [PDFKnowledgeSource(...)]

═══════════════════════════════════════════════════════════════
第2步：添加数据源
═══════════════════════════════════════════════════════════════

kb.add_sources()
  │
  └── for source in self.sources:  # 遍历每个数据源
        │
        ├── source.storage = self.storage  ← 注入存储后端
        │
        └── source.add()  # PDFKnowledgeSource.add()
              │
              ├── 遍历 self.content.values()
              │     └── self.content = {"doc.pdf": "PDF 文件内容..."}
              │
              ├── _chunk_text("PDF 文件内容...")
              │     └── ["PDF 文件内容...的第1段", "第2段...", ...]
              │
              ├── self.chunks.extend(new_chunks)
              │
              └── _save_documents()
                    └── self.storage.save(self.chunks)
                          │
                          ├── client.get_or_create_collection("knowledge_my_kb")
                          ├── rag_documents = [{"content": "第1段"}, {"content": "第2段"}, ...]
                          └── client.add_documents(collection_name, rag_documents)
                                └── ChromaDB 自动计算 embedding 并存入

═══════════════════════════════════════════════════════════════
第3步：查询知识
═══════════════════════════════════════════════════════════════

kb.query(["什么是 AI"])
  │
  └── self.storage.search(["什么是 AI"], limit=5, score_threshold=0.6)
        │
        ├── _get_client() → ChromaDB 客户端
        ├── collection_name = "knowledge_my_kb"
        ├── query_text = "什么是 AI"
        │
        └── client.search(
              collection_name="knowledge_my_kb",
              query="什么是 AI",
              limit=5,
              score_threshold=0.6,
            )
              │
              └── 返回 [
                    {"content": "AI 是人工智能的缩写...", "score": 0.95},
                    {"content": "人工智能研究包括...", "score": 0.87},
                    ...
                  ]
```

### 7.2 场景二：用字典配置数据源

```
用户代码:
  kb = Knowledge(
      collection_name="my_kb",
      sources=[
          {"source_type": "pdf", "file_paths": ["doc.pdf"]},
          {"source_type": "csv", "file_paths": ["data.csv"]},
      ],
      embedder={"provider": "openai", "config": {"model": "text-embedding-3-small"}},
  )

═══════════════════════════════════════════════════════════════

Knowledge.__init__() 之前，Pydantic 自动执行:

_resolve_knowledge_sources([
    {"source_type": "pdf", "file_paths": ["doc.pdf"]},
    {"source_type": "csv", "file_paths": ["data.csv"]},
])
  │
  ├── item 0: {"source_type": "pdf", ...}
  │     ├── tag = "pdf"
  │     ├── cls = _KNOWN_SOURCES["pdf"] → PDFKnowledgeSource
  │     └── PDFKnowledgeSource.model_validate({"source_type": "pdf", "file_paths": ["doc.pdf"]})
  │           └── 创建 PDFKnowledgeSource 实例
  │
  ├── item 1: {"source_type": "csv", ...}
  │     ├── tag = "csv"
  │     ├── cls = _KNOWN_SOURCES["csv"] → CSVKnowledgeSource
  │     └── CSVKnowledgeSource.model_validate({"source_type": "csv", "file_paths": ["data.csv"]})
  │           └── 创建 CSVKnowledgeSource 实例
  │
  └── 返回 [PDFKnowledgeSource(...), CSVKnowledgeSource(...)]
```

---

## 总结

### 模块文件清单

```
lib/crewai/src/crewai/knowledge/
├── __init__.py
├── knowledge.py              # Knowledge 类（顶层入口，205 行）
├── knowledge_config.py       # 查询参数配置（16 行）
├── source/
│   ├── base_knowledge_source.py       # 源抽象基类（78 行）
│   ├── base_file_knowledge_source.py  # 文件源基类（116 行）
│   ├── string_knowledge_source.py     # 字符串源（41 行）
│   ├── csv_knowledge_source.py        # CSV 源（51 行）
│   ├── pdf_knowledge_source.py        # PDF 源（63 行）
│   ├── json_knowledge_source.py       # JSON 源（63 行）
│   ├── excel_knowledge_source.py      # Excel 源（181 行）
│   ├── text_file_knowledge_source.py  # 文本文件源（43 行）
│   ├── crew_docling_source.py         # Docling 通用文档源（192 行）
│   └── utils/
│       └── source_helper.py           # 文件类型映射（70 行）
├── storage/
│   ├── base_knowledge_storage.py      # 存储抽象接口（51 行）
│   ├── knowledge_storage.py           # 默认存储实现 ChromaDB（232 行）
│   └── factory.py                     # 存储工厂注册机制（56 行）
└── utils/
    └── knowledge_utils.py             # 搜索结果格式化（12 行）
```

### 设计亮点总结

| 设计 | 作用 | 行号 |
|------|------|------|
| `_resolve_knowledge_sources` | 字典自动转成 Source 实例 | [knowledge.py#L34](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/knowledge/knowledge.py#L34) |
| `_KNOWN_SOURCES` 注册表 | 字符串名映射到类 | [knowledge.py#L23](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/knowledge/knowledge.py#L23) |
| 三层继承体系 | 公共逻辑复用（BaseKnowledgeSource → BaseFileKnowledgeSource → 具体实现） | [base_knowledge_source.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/knowledge/source/base_knowledge_source.py) |
| chunk 重叠机制 | 防止边界信息丢失 | [base_knowledge_source.py#L43](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/knowledge/source/base_knowledge_source.py#L43) |
| 延迟导入依赖 | 模块导入时不报错，使用时才检查 | [pdf_knowledge_source.py#L30](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/knowledge/source/pdf_knowledge_source.py#L30) |
| 存储工厂注册机制 | 用户可替换存储后端（ChromaDB → Qdrant 等） | [factory.py#L36](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/knowledge/storage/factory.py#L36) |
| 存储注入模式 | source.storage = self.storage，解耦 Source 和 Storage | [knowledge.py#L157](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/knowledge/knowledge.py#L157) |
| SourceHelper 自动映射 | 根据文件扩展名自动选择 Source 类 | [source_helper.py#L47](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/knowledge/source/utils/source_helper.py#L47) |
| Docling 层级分块 | 按文档结构（标题、段落）智能分块 | [crew_docling_source.py#L154](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/knowledge/source/crew_docling_source.py#L154) |