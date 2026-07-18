# CrewAI A2A (Agent-to-Agent) 模块深度分析

> **目标读者**: 小白友好的深度源码分析，采用"需求串讲 → 实现逻辑 → 通俗解释"三步法。

---

## 目录

1. [整体架构概览](#1-整体架构概览)
2. [顶层：wrapper.py - Agent 包装器](#2-顶层wrapperpy---agent-包装器)
3. [中层：配置与委托执行](#3-中层配置与委托执行)
   - [3.1 config.py - A2A 配置体系](#31-configpy---a2a-配置体系)
   - [3.2 delegation.py - 委托执行核心](#32-delegationpy---委托执行核心)
   - [3.3 task_helpers.py - 任务状态处理](#33-task_helperspy---任务状态处理)
   - [3.4 response_model.py - 响应模型工厂](#34-response_modelpy---响应模型工厂)
   - [3.5 extensions/ - 扩展机制](#35-extensions---扩展机制)
4. [底层：基础设施层](#4-底层基础设施层)
   - [4.1 auth/ - 认证体系](#41-auth---认证体系)
   - [4.2 utils/transport.py - 传输协议协商](#42-utilstransportpy---传输协议协商)
   - [4.3 utils/content_type.py - 内容类型协商](#43-utilscontent_typepy---内容类型协商)
   - [4.4 utils/agent_card.py - 名片获取与缓存](#44-utilsagent_cardpy---名片获取与缓存)
   - [4.5 utils/agent_card_signing.py - 名片签名验证](#45-utilsagent_card_signingpy---名片签名验证)
   - [4.6 utils/task.py - 服务端任务执行](#46-utilstaskpy---服务端任务执行)
   - [4.7 updates/ - 更新机制（轮询/流式/推送）](#47-updates---更新机制轮询流式推送)
   - [4.8 errors.py - 错误体系](#48-errorspy---错误体系)
   - [4.9 templates.py - 提示词模板](#49-templatespy---提示词模板)
   - [4.10 extensions/a2ui/ - 声明式 UI 扩展](#410-extensionsa2ui---声明式-ui-扩展)
   - [4.11 extensions/server.py - 服务端扩展](#411-extensionsserverpy---服务端扩展)
   - [4.12 utils/logging.py - 结构化日志](#412-utilsloggingpy---结构化日志)
5. [完整调用链路图](#5-完整调用链路图)

---

## 1. 整体架构概览

### 模块定位

A2A 模块是 CrewAI 实现 **Agent-to-Agent 协议** 的核心模块。它让一个 CrewAI Agent 能够像"打电话"一样，把任务委托给另一个远程的 A2A Agent 去执行，接收返回结果，甚至在多轮对话中持续沟通。

### 三层架构总览

```
┌──────────────────────────────────────────────────────────────────┐
│  顶层：wrapper.py                                                │
│  - 包装 Agent 的 execute_task / kickoff 方法                     │
│  - 注入 A2A 委托能力                                              │
│  - 管理多轮对话循环                                               │
├──────────────────────────────────────────────────────────────────┤
│  中层：                                                           │
│  - config.py        → 配置类（客户端/服务端/通用）                 │
│  - delegation.py    → 委托执行核心（建立连接、发送消息、获取结果） │
│  - task_helpers.py  → 任务状态处理（完成/失败/需要输入等）        │
│  - response_model.py→ 动态创建响应模型（AgentResponse）          │
│  - extensions/      → 扩展注册表（工具注入/提示增强/响应处理）    │
├──────────────────────────────────────────────────────────────────┤
│  底层：                                                           │
│  - auth/            → 7种认证方案（Bearer/OAuth2/API Key/mTLS等）│
│  - utils/transport.py   → 传输协议协商（JSONRPC/GRPC/HTTP+JSON） │
│  - utils/content_type.py→ 内容类型协商（MIME类型匹配）            │
│  - utils/agent_card.py  → AgentCard 获取与缓存                   │
│  - utils/agent_card_signing.py → JWS 签名验证                    │
│  - utils/task.py     → 服务端任务执行（A2A Server）               │
│  - updates/          → 更新机制（轮询/流式/推送通知）              │
│  - errors.py         → 30+ 种错误码定义                           │
│  - templates.py      → 提示词模板                                 │
│  - extensions/a2ui/  → 声明式 UI 组件（按钮/卡片/表单等）         │
│  - extensions/server.py → 服务端扩展机制                          │
│  - utils/logging.py  → JSON 结构化日志                            │
└──────────────────────────────────────────────────────────────────┘
```

---

## 2. 顶层：wrapper.py - Agent 包装器

### 需求串讲

**业务场景**：你有一个 CrewAI Agent，原本它只能自己调用 LLM 来完成任务。现在你想让它"聪明"一点——当它判断某个任务更适合交给另一个远程 Agent 时，它能自动把任务发给那个远程 Agent，拿到结果，然后继续处理。

**核心问题**：怎么在不大改 Agent 原有代码的情况下，给它加上这个"打电话给其他 Agent"的能力？

**设计思路**：用一个"包装器"（Wrapper）——在 Agent 原有的 `execute_task` 方法外面包一层，先检查是否需要 A2A 委托，如果需要就走 A2A 流程，如果不需要就照常调用原来的方法。

### 实现逻辑

[wrapper.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/a2a/wrapper.py) 是整个 A2A 模块的**入口函数**，核心函数是 `wrap_agent_with_a2a_instance`。

#### 2.1 包装流程

```
wrap_agent_with_a2a_instance(agent, extension_registry)
    │
    ├─ 1. 注入扩展工具 (extension_registry.inject_all_tools)
    │
    ├─ 2. 保存原始方法引用
    │     original_execute_task = agent.execute_task.__func__
    │     original_aexecute_task = agent.aexecute_task.__func__
    │
    ├─ 3. 创建带 A2A 的新方法（用 @wraps 保持原方法签名）
    │     execute_task_with_a2a / aexecute_task_with_a2a
    │     kickoff_with_a2a / kickoff_async_with_a2a
    │
    ├─ 4. 替换 Agent 实例的方法
    │     object.__setattr__(agent, "execute_task", MethodType(...))
    │     object.__setattr__(agent, "aexecute_task", MethodType(...))
    │     object.__setattr__(agent, "kickoff", MethodType(...))
    │     object.__setattr__(agent, "kickoff_async", MethodType(...))
    │
    └─ 5. 注入 A2A 服务端方法 (inject_a2a_server_methods)
```

#### 2.2 包装后的执行流程（以 execute_task 为例）

```
execute_task_with_a2a(task, context, tools)
    │
    ├─ 检查: agent.a2a 配置是否为空？
    │   ├─ 是 → 调用原始方法 original_execute_task(self, task, context, tools)
    │   └─ 否 → 继续
    │
    ├─ 提取 A2A 配置列表 + 创建响应模型
    │     a2a_agents, agent_response_model = get_a2a_agents_and_response_model(self.a2a)
    │
    └─ 调用 _execute_task_with_a2a()
          │
          ├─ 并发获取所有远程 Agent 的 AgentCard
          │     _fetch_agent_cards_concurrently(a2a_agents)
          │
          ├─ 如果所有 Agent 都不可用 → 在提示词中告知 LLM，回退到普通执行
          │
          ├─ 增强提示词（加入 A2A 代理信息和对话历史）
          │     _augment_prompt_with_a2a(...)
          │
          ├─ 调用 LLM（使用原始方法）
          │     raw_result = original_fn(self, task, context, tools)
          │
          ├─ 解析 LLM 响应
          │     agent_response = _parse_agent_response(raw_result, agent_response_model)
          │
          ├─ 检查: LLM 是否决定委托给 A2A Agent？
          │     agent_response.is_a2a == True？
          │     ├─ 是 → 进入多轮委托循环 _delegate_to_a2a()
          │     └─ 否 → 返回 agent_response.message（即 LLM 自身的回答）
          │
          └─ 最终恢复 task.description（防止污染后续调用）
```

#### 2.3 多轮对话循环（_delegate_to_a2a）

```
_delegate_to_a2a(agent_response, task, original_fn, ...)
    │
    ├─ 1. 准备委托上下文 (_prepare_delegation_context)
    │     - 确定目标 Agent 的 endpoint
    │     - 提取 max_turns（最大对话轮数，默认10）
    │     - 提取 context_id / task_id（跨轮对话关联）
    │
    ├─ 2. 初始化对话状态 (_init_delegation_state)
    │     - current_request = LLM 的请求文本
    │     - conversation_history = []（对话历史）
    │     - reference_task_ids = []（已完成的任务ID列表）
    │
    └─ 3. 多轮对话循环（for turn_num in range(max_turns)）
          │
          ├─ 发送委托请求
          │     execute_a2a_delegation(endpoint, task_description, ...)
          │
          ├─ 获取结果 a2a_result
          │     - status: completed / failed / input_required / ...
          │     - result: 远程 Agent 的回复文本
          │     - history: 对话历史消息列表
          │
          ├─ 更新对话状态
          │     - conversation_history = a2a_result["history"]
          │     - task_id / context_id 从最后一条消息中提取
          │
          ├─ 如果远程任务完成 (completed) 或需要输入 (input_required)
          │   │
          │   ├─ _handle_task_completion()
          │   │   - 如果设了 trust_remote_completion_status → 直接返回远程结果
          │   │   - 否则将完成的任务ID加入 reference_task_ids
          │   │
          │   └─ _handle_agent_response_and_continue()
          │       - 增强提示词（加入最新对话历史）
          │       - 再次调用 LLM
          │       - 解析 LLM 响应
          │       - 如果 LLM 说 is_a2a=false → 返回最终结果
          │       - 如果 LLM 说 is_a2a=true → 继续下一轮
          │
          ├─ 如果远程任务失败
          │   └─ _handle_agent_response_and_continue()
          │       - LLM 看到错误信息后决定下一步
          │
          └─ 如果超过 max_turns
              └─ _handle_max_turns_exceeded()
                  - 从对话历史中找最后一条 Agent 消息作为最终结果
```

### 通俗解释

**打个比方**：wrapper.py 就像给 Agent 装了一个"秘书插件"。

1. 原本 Agent 只能自己干活（调用 LLM）。
2. 装了秘书插件后，Agent 每次接到任务，秘书会先问："这个任务需要我帮你找外援吗？"
3. 秘书会给 Agent 一份"外援名册"（就是 `_augment_prompt_with_a2a` 往提示词里加的可用 Agent 列表）。
4. Agent 看完任务描述和外援名册，决定要不要找外援。如果要找，它会说"is_a2a=true，请把这个任务交给 xxx Agent"。
5. 秘书就帮 Agent 去联系那个外援（`execute_a2a_delegation`），拿到回复后交给 Agent。
6. Agent 看完回复，决定是接着问还是结束。如果接着问，秘书再跑一趟。最多跑 max_turns 趟（默认 10 趟）。

---

## 3. 中层：配置与委托执行

### 3.1 config.py - A2A 配置体系

#### 需求串讲

A2A 通信涉及很多参数：远程 Agent 的地址是什么？用什么认证方式？超时多久？用哪种传输协议？这些配置需要一个统一的结构来管理，让用户配置起来简单明了。

#### 实现逻辑

[config.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/a2a/config.py) 定义了三种配置类，形成了"通用→客户端→服务端"的层次结构：

```
A2AConfig (通用配置 - 既可以当客户端也可以当服务端)
    ├─ endpoint: 远程 Agent 的 URL
    ├─ auth: 认证方案（Bearer/OAuth2/API Key等）
    ├─ timeout: 请求超时时间（默认 120 秒）
    ├─ max_turns: 最大对话轮数（默认 10 轮）
    ├─ trust_remote_completion_status: 是否信任远程的完成状态
    ├─ transport: 传输协议配置
    ├─ response_model: 结构化输出模型
    ├─ updates: 更新机制配置（轮询/流式/推送）
    ├─ fail_fast: 获取 AgentCard 失败时是否立即报错
    ├─ extensions: A2A 协议扩展 URI 列表
    └─ client_extensions: CrewAI 客户端扩展实例列表

A2AClientConfig (纯客户端配置 - 继承 A2AConfig)
    └─ accepted_output_modes: 客户端能接受的 MIME 类型

A2AServerConfig (纯服务端配置 - 继承 A2AConfig)
    └─ default_input_modes: 服务端允许的输入 MIME 类型

ClientTransportConfig (传输配置)
    ├─ preferred: 首选传输协议
    ├─ supported: 支持的传输协议列表
    └─ grpc: gRPC 专用配置

GRPCClientConfig (gRPC 配置)
    ├─ host: gRPC 主机地址
    ├─ secure: 是否使用 TLS
    ├─ max_send_message_length: 最大发送消息大小
    ├─ max_receive_message_length: 最大接收消息大小
    └─ keepalive 相关参数
```

#### 通俗解释

**A2AConfig** 就像一张"名片模板"——包含了联系一个远程 Agent 所需的所有信息：
- 它的地址（endpoint）
- 怎么证明你的身份（auth）
- 最多聊几轮（max_turns）
- 等多久没回复就放弃（timeout）

**A2AClientConfig** 是在"名片模板"上加了一行"我能接受文本和 JSON 格式的回复"。

**A2AServerConfig** 是在"名片模板"上加了一行"我只接受文本和 JSON 格式的请求"。

---

### 3.2 delegation.py - 委托执行核心

#### 需求串讲

这是 A2A 模块最核心的执行逻辑。当一个 CrewAI Agent 决定委托任务给远程 Agent 时，需要完成以下步骤：
1. 获取远程 Agent 的"名片"（AgentCard），了解它的能力
2. 协商用哪种传输协议通信（JSONRPC？GRPC？HTTP+JSON？）
3. 协商用哪种内容格式（纯文本？JSON？图片？）
4. 建立加密连接，发送任务描述
5. 根据配置选择更新机制（流式接收？轮询？等待推送通知？）
6. 获取结果并返回

#### 实现逻辑

[delegation.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/a2a/utils/delegation.py) 提供了同步和异步两套接口。

**核心函数：`aexecute_a2a_delegation`（异步版本）**

```
aexecute_a2a_delegation(endpoint, auth, timeout, task_description, ...)
    │
    ├─ 1. 计算认证哈希，存入缓存
    │     auth_hash = _auth_store.compute_key(...)
    │     _auth_store.set(auth_hash, auth)
    │
    ├─ 2. 获取远程 AgentCard（带缓存）
    │     agent_card = await _afetch_agent_card_cached(endpoint, auth_hash, timeout)
    │     - 这一步是 HTTP GET 请求远程 Agent 的 /.well-known/agent-card.json
    │     - 返回的 AgentCard 包含：名称、能力、技能、安全要求、支持的传输协议等
    │
    ├─ 3. 验证认证方案是否匹配 AgentCard 的要求
    │     validate_auth_against_agent_card(agent_card, auth)
    │     - 如果 AgentCard 说需要 OAuth2，但用户只提供了 API Key，就报错
    │
    ├─ 4. 验证扩展兼容性
    │     validate_required_extensions(agent_card, client_extensions)
    │     - 如果远程 Agent 要求必须支持某个扩展，但客户端不支持，就报错
    │
    ├─ 5. 传输协议协商
    │     negotiate_transport(agent_card, client_supported_transports, ...)
    │     - 客户端说"我支持 JSONRPC、GRPC"
    │     - 服务端说"我支持 JSONRPC、HTTP+JSON"
    │     - 协商结果：JSONRPC（双方都支持的）
    │
    ├─ 6. 内容类型协商
    │     negotiate_content_types(agent_card, client_output_modes, ...)
    │     - 客户端说"我能接收 text/plain 和 application/json"
    │     - 服务端说"我能输出 text/plain 和 image/png"
    │     - 协商结果：text/plain（双方都支持的）
    │
    ├─ 7. 准备认证头
    │     headers, _ = await _prepare_auth_headers(auth, timeout)
    │     - 如果是 Bearer Token：Authorization: Bearer xxx
    │     - 如果是 OAuth2：自动获取/刷新 token
    │
    ├─ 8. 构建消息
    │     message = Message(
    │         role=Role.user,
    │         parts=[TextPart(text=task_description)],
    │         context_id=context_id,
    │         task_id=task_id,
    │         ...
    │     )
    │     - 如果提供了 response_model，还会在 metadata 中附带 JSON Schema
    │     - 如果有 input_files，会转换为 FilePart 附加到消息中
    │
    ├─ 9. 选择更新机制处理器
    │     handler = get_handler(updates)
    │     - 默认：StreamingHandler（流式接收）
    │     - 如果配置了 PollingConfig：PollingHandler（轮询）
    │     - 如果配置了 PushNotificationConfig：PushNotificationHandler（推送通知）
    │
    ├─ 10. 创建 A2A 客户端
    │      _create_a2a_client(agent_card, transport_protocol, timeout, ...)
    │      - 根据协商的传输协议创建对应的客户端
    │      - 如果是 GRPC：创建 gRPC channel + 拦截器
    │      - 如果是 JSONRPC：使用 HTTP 客户端
    │
    └─ 11. 由 handler 执行消息发送和结果获取
         result = await handler.execute(client, message, ...)
         - StreamingHandler：发送消息 → 流式接收事件 → 处理结果
         - PollingHandler：发送消息 → 获取 task_id → 轮询任务状态
         - PushNotificationHandler：发送消息 → 等待推送通知
```

**同步版本 `execute_a2a_delegation`**：
- 内部调用 `aexecute_a2a_delegation`
- 如果在已有事件循环中，用 `ThreadPoolExecutor` 在新线程中运行
- 如果不在事件循环中，直接用 `asyncio.run()`

**A2A 客户端创建 `_create_a2a_client`**：

```
_create_a2a_client(agent_card, transport_protocol, ...)
    │
    ├─ 创建 HTTP 客户端 (httpx.AsyncClient)
    │     - 设置超时、认证头、TLS 验证
    │     - 配置 DigestAuth / APIKeyAuth 的客户端钩子
    │
    ├─ 如果是 GRPC 传输
    │   └─ _create_grpc_channel_factory(grpc_config, auth)
    │       - 创建 gRPC 通道工厂函数
    │       - 配置 TLS 证书、消息大小限制、keepalive
    │       - 创建 gRPC 拦截器（元数据注入、认证注入）
    │       - 处理各种认证方案到 gRPC 元数据的转换
    │
    ├─ 构建 ClientConfig
    │     - supported_transports: [协商后的传输协议]
    │     - streaming: 是否开启流式（非轮询时开启）
    │     - polling: 是否开启轮询
    │     - accepted_output_modes: 协商后的输出 MIME 类型
    │     - push_notification_configs: 推送通知配置
    │     - grpc_channel_factory: gRPC 通道工厂
    │
    ├─ 创建 Client
    │     factory = ClientFactory(config)
    │     client = factory.create(agent_card)
    │
    └─ 如果有扩展，添加扩展中间件
          client.add_request_middleware(ExtensionsMiddleware(client_extensions))
```

#### 通俗解释

**delegation.py 就像一个"出差专员"**：

1. 出发前，先去查一下对方的"名片"（AgentCard），了解对方是谁，会什么技能，需要什么认证。
2. 确认一下自己的认证方式对不对（比如对方要求 OAuth2，你不能拿 API Key 去糊弄）。
3. 协商"用什么语言沟通"（传输协议协商）和"用什么格式写文件"（内容类型协商）。
4. 建立安全连接，把任务描述发过去。
5. 根据对方的工作方式，选择"怎么收结果"：
   - 如果对方是"即时回复型"（流式），就等着接收。
   - 如果对方是"异步处理型"（轮询），就每隔几秒去问一次"好了没"。
   - 如果对方是"通知型"（推送），就留个地址等对方通知。
6. 拿到结果后返回。

---

### 3.3 task_helpers.py - 任务状态处理

#### 需求串讲

当远程 Agent 处理任务时，任务会经历多个状态：submitted（已提交）→ working（工作中）→ completed（完成）/ failed（失败）/ input_required（需要更多输入）。我们需要一个统一的逻辑来处理这些状态，提取结果或错误信息。

#### 实现逻辑

[task_helpers.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/a2a/task_helpers.py) 定义了任务状态分类和处理逻辑。

**状态分类**：

```python
# 终态：任务结束了，不会再变化
TERMINAL_STATES = {completed, failed, rejected, canceled}

# 需要行动的状态：任务暂停了，需要你做点什么
ACTIONABLE_STATES = {input_required, auth_required}

# 等待中的状态：任务还在进行中
PENDING_STATES = {submitted, working}
```

**核心函数 `process_task_state`**：

```
process_task_state(a2a_task, new_messages, agent_card, turn_number, ...)
    │
    ├─ 如果状态是 completed（完成）
    │   ├─ 提取结果文本（从 status.message > history > artifacts 中找）
    │   ├─ 发出 A2AResponseReceivedEvent 事件
    │   └─ 返回 TaskStateResult(status=completed, result=..., history=...)
    │
    ├─ 如果状态是 input_required（需要输入）
    │   ├─ 提取错误/提示信息
    │   ├─ 如果没有历史消息，创建一个包含提示信息的 Agent 消息
    │   ├─ 发出 A2AResponseReceivedEvent 事件
    │   └─ 返回 TaskStateResult(status=input_required, error=..., history=...)
    │
    ├─ 如果状态是 failed / rejected（失败/拒绝）
    │   ├─ 提取错误信息
    │   └─ 返回 TaskStateResult(status=failed, error=..., history=...)
    │
    ├─ 如果状态是 auth_required（需要认证）
    │   └─ 返回 TaskStateResult(status=auth_required, error=...)
    │
    ├─ 如果状态是 canceled（已取消）
    │   └─ 返回 TaskStateResult(status=canceled, error=...)
    │
    └─ 如果状态是 PENDING_STATES（等待中）
        └─ 返回 None（表示还需要继续等待）
```

**`send_message_and_get_task_id`**：发送消息后处理初始响应
- 如果远程立即返回 Message → 任务同步完成，直接返回结果
- 如果远程返回 Task → 返回 task_id，需要后续轮询/等待
- 处理 HTTP 错误和意外异常

**结果提取逻辑 `extract_task_result_parts`**：
1. 先从 `status.message` 中提取文本部分
2. 如果没有，从 `history` 中找最后一条 Agent 角色的消息
3. 如果还没有，从 `artifacts`（产出物）中提取

#### 通俗解释

**task_helpers.py 就像"任务跟踪表"**：

- 每个任务有几个状态：提交了、正在做、做完了、失败了、需要你补充信息、被取消了。
- `process_task_state` 就是根据当前状态，决定怎么处理：
  - 做完了 → 提取结果，高兴地返回
  - 失败了 → 提取错误信息，遗憾地返回
  - 需要补充信息 → 返回提示，让 LLM 决定下一步
  - 还在做 → 返回 None，告诉上层"再等等"
- `extract_task_result_parts` 是从多个地方找结果文本（因为结果可能藏在不同的位置）。

---

### 3.4 response_model.py - 响应模型工厂

#### 需求串讲

当 Agent 被赋予 A2A 能力后，需要一种方式让 LLM 表达"我要委托给哪个 Agent，说什么话"。这个需求通过动态创建一个 Pydantic 模型来实现——`AgentResponse`，包含三个字段：
- `a2a_ids`：要委托给哪个/哪些远程 Agent（用 endpoint 标识）
- `message`：要发送给远程 Agent 的消息内容
- `is_a2a`：true 表示要委托，false 表示不委托（自己回答）

#### 实现逻辑

[response_model.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/a2a/utils/response_model.py)

**核心函数 `create_agent_response_model`**：

```python
def create_agent_response_model(agent_ids: tuple[str, ...]) -> type[BaseModel] | None:
    if not agent_ids:
        return None  # 没有可用的 A2A Agent，不需要创建模型

    # 用 Literal 类型约束 a2a_ids 只能是配置中的 endpoint 之一
    DynamicLiteral = create_literals_from_strings(agent_ids)

    return create_model(
        "AgentResponse",
        a2a_ids=(tuple[DynamicLiteral, ...], Field(default_factory=tuple, ...)),
        message=(str, Field(description="...")),
        is_a2a=(bool, Field(description="...")),
        __base__=BaseModel,
    )
```

**辅助函数 `get_a2a_agents_and_response_model`**：
- 从 A2A 配置中提取客户端配置（过滤掉 A2AServerConfig）
- 提取所有 endpoint 作为 agent_ids
- 调用 `create_agent_response_model` 创建响应模型

**`extract_a2a_agent_ids_from_config`**：
- 过滤掉 `A2AServerConfig`（服务端配置不需要委托）
- 只保留 `A2AConfig` 和 `A2AClientConfig`（客户端配置）

#### 通俗解释

**response_model.py 就像一个"委托表单生成器"**：

1. 看看你配置了哪些远程 Agent（比如 `agent1.example.com` 和 `agent2.example.com`）
2. 自动生成一个表单，上面有三个字段：
   - "选哪个 Agent"（下拉框，只能选配置过的）
   - "跟他说什么"（文本框）
   - "是否要委托"（开关）
3. LLM 填好这个表单，系统就知道它想委托给谁、说什么了。

---

### 3.5 extensions/ - 扩展机制

#### 需求串讲

A2A 协议支持两种扩展：
1. **A2A 协议扩展**（Protocol Extensions）：通过 HTTP Header `X-A2A-Extensions` 声明，遵循 A2A 规范
2. **CrewAI 处理钩子**（Processing Hooks）：在 CrewAI 内部使用的扩展，用于注入工具、增强提示词、处理响应

#### 实现逻辑

**`extensions/base.py`** - 客户端扩展接口

定义了 `A2AExtension` 协议，有 5 个可选方法：

```python
class A2AExtension(Protocol):
    def inject_tools(self, agent: Agent) -> None:
        """在 Agent 包装时注入自定义工具"""
        ...

    def extract_state_from_history(self, conversation_history) -> ConversationState | None:
        """从对话历史中提取扩展状态"""
        ...

    def augment_prompt(self, base_prompt, conversation_state) -> str:
        """增强提示词"""
        ...

    def process_response(self, agent_response, conversation_state) -> Any:
        """处理/修改 Agent 响应"""
        ...

    def prepare_message_metadata(self, conversation_state) -> dict:
        """准备出站消息的元数据"""
        ...
```

**`ExtensionRegistry`** - 扩展注册表

管理多个扩展，提供批量调用方法：
- `inject_all_tools(agent)` → 遍历所有扩展，注入工具
- `extract_all_states(history)` → 遍历所有扩展，提取状态
- `augment_prompt_with_all(prompt, states)` → 链式增强提示词
- `process_response_with_all(response, states)` → 链式处理响应
- `prepare_all_metadata(states)` → 合并所有扩展的元数据

**`extensions/registry.py`** - 协议扩展工具

- `get_extensions_from_config(a2a_config)` → 从配置中提取扩展 URI
- `ExtensionsMiddleware` → HTTP 中间件，在请求头中添加 `X-A2A-Extensions`
- `validate_required_extensions(agent_card, client_extensions)` → 验证客户端是否支持服务端要求的扩展
- `create_extension_registry_from_config(a2a_config)` → 从配置创建 ExtensionRegistry

#### 通俗解释

**扩展机制就像"插件系统"**：

- **A2A 协议扩展**：相当于你告诉对方"我能理解 A2UI 界面"或者"我支持流式传输"。这些通过 HTTP Header 传递。
- **CrewAI 处理钩子**：相当于在 Agent 处理流程中"插队"——在提示词发给 LLM 之前加点东西，在 LLM 回复之后改点东西，或者给 Agent 装几个额外的工具。

---

## 4. 底层：基础设施层

### 4.1 auth/ - 认证体系

#### 需求串讲

A2A 通信需要认证，因为远程 Agent 需要知道你是谁，是否有权限调用它。不同的远程 Agent 可能使用不同的认证方式——有的用简单的 Bearer Token，有的用 OAuth2，有的用客户端证书（mTLS）。

#### 实现逻辑

[client_schemes.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/a2a/auth/client_schemes.py) 定义了 7 种认证方案：

**认证方案层次结构**：

```
ClientAuthScheme (ABC - 抽象基类)
    ├─ BearerTokenAuth      → Authorization: Bearer <token>
    ├─ HTTPBasicAuth        → Authorization: Basic base64(user:pass)
    ├─ HTTPDigestAuth       → 使用 httpx.DigestAuth（挑战-响应模式）
    ├─ APIKeyAuth           → 在 Header/Query/Cookie 中发送 API Key
    ├─ OAuth2ClientCredentials → 自动获取/刷新 access_token
    ├─ OAuth2AuthorizationCode→ 交互式授权码流程
    └─ (已废弃) AuthScheme  → 指向 ClientAuthScheme
```

**TLSConfig** - TLS/mTLS 配置：
- 支持客户端证书（mTLS）——客户端也要出示证书证明身份
- 支持自定义 CA 证书——验证服务端证书
- 同时支持 httpx 和 gRPC 两种客户端

**每种认证方案的实现细节**：

**BearerTokenAuth**：最简单，直接设置 `Authorization: Bearer xxx` 头。

**HTTPBasicAuth**：将 `username:password` 做 Base64 编码后放到 `Authorization: Basic xxx` 头。

**HTTPDigestAuth**：使用 HTTP 摘要认证（挑战-响应模式），由 httpx 库自动处理。有防重复配置的幂等性保护。

**APIKeyAuth**：支持三种位置：
- `header`：设置 `X-API-Key: xxx` 头
- `query`：添加到 URL 查询参数中（通过 httpx 事件钩子）
- `cookie`：设置 `Cookie: X-API-Key=xxx`

**OAuth2ClientCredentials**：自动管理 token 生命周期
- 线程安全：使用 `asyncio.Lock` 防止并发刷新 token
- 自动刷新：token 过期前 60 秒自动刷新
- 双重检查锁定：避免多个协程同时刷新 token

**OAuth2AuthorizationCode**：交互式授权
- 需要用户提供一个回调函数来处理授权 URL
- 支持 refresh_token 自动刷新

**`auth/utils.py`** - 认证工具函数：
- `_AuthStore`：线程安全的认证方案存储（使用 SHA-256 哈希 + 线程锁）
- `validate_auth_against_agent_card`：验证提供的认证方案是否匹配 AgentCard 的安全要求
- `retry_on_401`：遇到 401 错误时自动重试（解析 WWW-Authenticate 头，重新认证，指数退避）
- `parse_www_authenticate`：解析 WWW-Authenticate 头

#### 通俗解释

**认证体系就像"门禁系统"**：

1. **Bearer Token**：就像拿着一张门禁卡，刷卡进门。
2. **HTTP Basic**：就像输入用户名密码。
3. **HTTP Digest**：更安全的密码验证，密码不会明文传输。
4. **API Key**：就像拿着一张特殊的通行证，可以放在手里（Header）、贴在门上（Query）、或者放在口袋里（Cookie）。
5. **OAuth2 Client Credentials**：就像有一个自动续期的访客证——到期前自动去前台续期。
6. **OAuth2 Authorization Code**：就像需要你亲自去前台签字领证，之后可以自动续期。
7. **mTLS**：双方都要出示身份证（证书），互相验证。

`retry_on_401` 就像一个"智能重试"机制：如果门禁说"认证失败"，它会自动去前台重新认证，然后再试一次（最多试 3 次，每次间隔越来越长）。

---

### 4.2 utils/transport.py - 传输协议协商

#### 需求串讲

A2A 协议支持三种传输方式：JSONRPC、GRPC、HTTP+JSON。客户端和服务器需要协商出一个双方都支持的传输协议，就像两个人打电话前先商量"用微信还是用电话还是用邮件"。

#### 实现逻辑

[transport.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/a2a/utils/transport.py)

**传输协议**：
- `JSONRPC`：JSON-RPC 2.0 协议（默认）
- `GRPC`：gRPC 协议（高性能二进制）
- `HTTP+JSON`：纯 HTTP JSON 协议

**协商优先级**：
1. 如果客户端指定了首选协议，且服务端支持 → 使用客户端首选
2. 如果服务端有首选协议，且客户端支持 → 使用服务端首选
3. 按客户端支持列表顺序，找第一个服务端也支持的 → 使用 fallback
4. 都没找到 → 抛出 `TransportNegotiationError`

**`_get_server_interfaces`**：从 AgentCard 中提取所有可用接口
- 优先使用 `preferred_transport`（默认为 JSONRPC）
- 加上 `additional_interfaces` 中的额外接口
- 去重（相同 URL + 相同传输协议只保留一个）

**协商结果 `NegotiatedTransport`**：
- `transport`：协商后的传输协议
- `url`：该传输协议对应的 URL
- `source`：协商来源（`client_preferred` / `server_preferred` / `fallback`）

#### 通俗解释

**传输协议协商就像"选沟通方式"**：

A 说："我会说中文、英文、日文"
B 说："我会说英文、法文"
协商结果：英文（因为双方都会）

如果 A 说"我首选中文"，但 B 不会中文，那就找双方都会的——英文。

---

### 4.3 utils/content_type.py - 内容类型协商

#### 需求串讲

除了传输协议，还需要协商内容格式。客户端说"我能接收文本和 JSON"，服务端说"我还能输出图片"，最终协商出双方都支持的内容类型。

#### 实现逻辑

[content_type.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/a2a/utils/content_type.py)

**支持的内容类型**：
- `text/plain`：纯文本
- `application/json`：JSON 数据
- `image/png`、`image/jpeg`、`image/*`：图片
- `application/pdf`：PDF 文件
- `application/octet-stream`：二进制流
- `application/json+a2ui`：A2UI 专用格式

**通配符匹配**：
- `image/*` 可以匹配 `image/png`、`image/jpeg` 等
- 支持 `*/*` 匹配所有类型

**协商流程**：
1. 获取服务端的有效输入/输出模式（可以按 skill 指定）
2. 对输入和输出分别找到兼容的模式
3. 返回 `NegotiatedContentTypes`（包含协商后的输入/输出模式）

**`validate_message_parts`**：验证消息中的每个 Part 的内容类型是否在允许列表中。

#### 通俗解释

**内容类型协商就像"选文件格式"**：

客户端："我能打开 .txt 和 .json 文件"
服务端："我能生成 .txt、.json 和 .png 文件"
协商结果：用 .txt 或 .json 格式传递（因为客户端打不开 .png）。

---

### 4.4 utils/agent_card.py - 名片获取与缓存

#### 需求串讲

在 A2A 协议中，每个 Agent 都有一个"名片"（AgentCard），描述了它的名称、能力、技能、支持的传输协议、安全要求等。客户端需要先获取这个名片，才能知道怎么和它通信。

#### 实现逻辑

[agent_card.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/a2a/utils/agent_card.py)

**核心函数**：

**同步版本 `fetch_agent_card`**：
```
fetch_agent_card(endpoint, auth, timeout, use_cache=True, cache_ttl=300)
    │
    ├─ 如果启用缓存：
    │   ├─ 计算认证哈希（排除敏感字段如 access_token）
    │   ├─ 存入 _auth_store
    │   ├─ 计算 TTL 哈希（按 cache_ttl 秒分桶）
    │   └─ 调用 _fetch_agent_card_cached（带 lru_cache）
    │
    └─ 如果不启用缓存：
        └─ 调用 afetch_agent_card（异步版本）
            └─ 如果在事件循环中 → ThreadPoolExecutor 运行
            └─ 如果不在事件循环中 → asyncio.run()
```

**异步版本 `afetch_agent_card`**：
```
afetch_agent_card(endpoint, auth, timeout, use_cache=True)
    │
    ├─ 如果启用缓存：
    │   └─ _afetch_agent_card_cached（aiocache 装饰器，TTL=300秒）
    │
    └─ 如果不启用缓存：
        └─ _afetch_agent_card_impl（实际 HTTP 请求）
```

**实际请求 `_afetch_agent_card_impl`**：
```
_afetch_agent_card_impl(endpoint, auth, timeout)
    │
    ├─ 解析 URL（提取 base_url 和 agent_card_path）
    ├─ 准备认证头
    ├─ 发送 HTTP GET 请求
    ├─ 带 401 重试机制（retry_on_401）
    ├─ 验证响应，解析为 AgentCard
    ├─ 发出 A2AAgentCardFetchedEvent 事件
    └─ 返回 AgentCard
```

**错误处理**：
- 401 → 发出 `A2AAuthenticationFailedEvent`，抛出 `A2AClientHTTPError`
- HTTP 错误 → 发出 `A2AConnectionErrorEvent`
- 超时 → 发出 `A2AConnectionErrorEvent`
- 连接错误 → 发出 `A2AConnectionErrorEvent`
- 请求错误 → 发出 `A2AConnectionErrorEvent`

**缓存策略**：
- 同步版本：使用 `@lru_cache` + TTL 哈希（按 300 秒分桶，桶变了就失效）
- 异步版本：使用 `aiocache`（支持 Redis 或内存缓存，TTL=300 秒）

**`_task_to_skill`**：将 CrewAI Task 转换为 A2A AgentSkill（用于生成 AgentCard 中的技能列表）。

#### 通俗解释

**AgentCard 获取就像"查对方的公司官网"**：

1. 你要联系一个远程 Agent，先访问它的 `/.well-known/agent-card.json` 地址。
2. 这个地址返回一个 JSON，描述了它的"名片"——叫什么名字、会什么技能、用什么协议通信、需要什么认证。
3. 为了避免每次都去查（太慢），系统会缓存 5 分钟。
4. 如果认证失败（401），会尝试重新认证再重试（最多 2 次）。

---

### 4.5 utils/agent_card_signing.py - 名片签名验证

#### 需求串讲

在某些安全敏感的场景下，你需要验证远程 Agent 的名片是否被篡改过。这通过 JWS（JSON Web Signature，RFC 7515）来实现——Agent 用私钥对名片内容签名，客户端用公钥验证签名。

#### 实现逻辑

[agent_card_signing.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/a2a/utils/agent_card_signing.py)

**支持的签名算法**：RS256/384/512、ES256/384/512、PS256/384/512

**`sign_agent_card`** - 签名：
1. 将 AgentCard 序列化为规范 JSON（排除 signatures 字段，排序键，紧凑格式）
2. 用 JWS 编码（payload 是序列化后的 JSON）
3. 返回 `AgentCardSignature`（包含 protected header 和 signature）

**`verify_agent_card_signature`** - 验证：
1. 重新序列化 AgentCard（排除 signatures 字段）
2. 用公钥解码 JWS token
3. 验证签名是否有效

#### 通俗解释

**名片签名就像"公证处的公章"**：

- 签名：Agent 用自己的私钥在名片上盖个章（数字签名）。这个章的内容和名片内容绑定——内容改了，章就无效了。
- 验证：客户端用 Agent 公开的公钥验证这个章是不是真的。如果章是真的，说明名片内容没有被篡改。

---

### 4.6 utils/task.py - 服务端任务执行

#### 需求串讲

当 CrewAI Agent 作为 A2A 服务端运行时（即它接收其他 Agent 的委托请求），需要处理传入的任务：解析消息、创建 Task、执行、返回结果。还需要支持取消、列出任务等功能。

#### 实现逻辑

[task.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/a2a/utils/task.py)

**`execute` / `execute_with_extensions`** - 执行 A2A 任务：

```
execute(agent, context, event_queue)
    │
    └─ _execute_impl(agent, context, event_queue, extension_registry, extension_context)
        │
        ├─ 1. 验证消息内容类型
        │     validate_message_parts(context.message.parts, allowed_modes)
        │     - 如果客户端发送了不支持的类型，抛出 ServerError
        │
        ├─ 2. 如果配置了扩展，调用 on_request 钩子
        │
        ├─ 3. 解析消息
        │     - 提取响应 Schema（如果客户端指定了结构化输出格式）
        │     - 提取结构化数据（DataParts）
        │     - 提取文件（FileParts）
        │
        ├─ 4. 创建 CrewAI Task
        │     Task(
        │         description=用户消息 + 结构化数据,
        │         expected_output="Response to the user's request",
        │         agent=agent,
        │         response_model=从 Schema 创建的模型,
        │         input_files=转换后的文件,
        │     )
        │
        ├─ 5. 发出 A2AServerTaskStartedEvent
        │
        ├─ 6. 执行任务
        │     result = await agent.aexecute_task(task=task, tools=agent.tools)
        │
        ├─ 7. 如果配置了扩展，调用 on_response 钩子
        │
        ├─ 8. 构建结果
        │     - 创建产出物（Artifact）
        │     - 构建历史消息列表
        │     - 入队完成事件
        │
        ├─ 9. 发出 A2AServerTaskCompletedEvent
        │
        └─ 错误处理
            ├─ CancelledError → A2AServerTaskCanceledEvent
            └─ 其他异常 → A2AServerTaskFailedEvent + ServerError
```

**`cancellable` 装饰器** - 任务取消机制：

```
cancellable(fn)
    │
    └─ wrapper(*args, **kwargs)
        │
        ├─ 并发运行两个任务：
        │   ├─ execute_task = fn(*args, **kwargs)  # 实际执行
        │   └─ cancel_watch = watch_for_cancel()   # 监听取消
        │
        ├─ 如果 cancel_watch 先完成 → 取消 execute_task
        │
        └─ 取消监听逻辑：
            ├─ 如果缓存是 SimpleMemoryCache → 轮询检查 cancel:{task_id} 键
            └─ 如果缓存是 Redis → 订阅 cancel:{task_id} 频道
```

**`cancel` 函数** - 触发取消：
1. 在缓存中设置 `cancel:{task_id} = True`
2. 如果是 Redis，发布 `cancel:{task_id}` 消息
3. 入队取消状态更新事件

**`list_tasks` 函数** - 任务列表（分页 + 过滤）：
- 支持按 context_id、status、时间戳过滤
- 支持游标分页（base64 编码的任务 ID）
- 支持限制历史消息长度和是否包含产出物

**缓存配置**：支持 Redis（通过 `REDIS_URL` 环境变量）或内存缓存。

#### 通俗解释

**服务端任务执行就像"外包公司接单"**：

1. 收到一个请求（`context`），先检查格式对不对（内容类型验证）。
2. 把请求解析成内部任务（创建 CrewAI Task）。
3. 交给指定的 Agent 去执行（`agent.aexecute_task`）。
4. 执行完了，把结果打包好返回。
5. 如果执行过程中有人取消了（`cancellable` 装饰器），就停止执行。
6. 取消机制通过缓存实现——设置一个标志位，执行中的任务每 0.1 秒检查一次。

---

### 4.7 updates/ - 更新机制（轮询/流式/推送）

#### 需求串讲

A2A 协议支持三种获取任务结果的方式：
1. **流式（Streaming）**：发送消息后，持续接收服务端推送的事件流
2. **轮询（Polling）**：发送消息后，定期询问"任务做完了吗？"
3. **推送通知（Push Notification）**：发送消息后，留一个回调地址，服务端完成后通知

#### 实现逻辑

**`updates/base.py`** - 基础定义

定义了 `UpdateHandler` 协议和参数类型：
- `PollingHandlerKwargs`：轮询间隔、超时、历史长度
- `StreamingHandlerKwargs`：流式参数
- `PushNotificationHandlerKwargs`：推送配置、结果存储

**`HANDLER_REGISTRY`** - 配置类型到处理器的映射：
```python
HANDLER_REGISTRY = {
    PollingConfig: PollingHandler,
    StreamingConfig: StreamingHandler,
    PushNotificationConfig: PushNotificationHandler,
}
```

**`updates/polling/handler.py`** - 轮询处理器

```
PollingHandler.execute(client, message, new_messages, agent_card, **kwargs)
    │
    ├─ 1. 发送消息，获取 task_id
    │     send_message_and_get_task_id(client.send_message(message), ...)
    │     - 如果远程立即返回结果 → 直接返回
    │     - 如果远程返回 Task → 获取 task_id 进行轮询
    │
    ├─ 2. 轮询等待任务完成
    │     _poll_task_until_complete(client, task_id, polling_interval, polling_timeout, ...)
    │     │
    │     └─ while True:
    │         ├─ task = await client.get_task(TaskQueryParams(id=task_id))
    │         ├─ 发出 A2APollingStatusEvent（每次轮询都发出状态事件）
    │         ├─ 如果状态是终态或需要行动 → 返回 task
    │         ├─ 如果超时 → 抛出 A2APollingTimeoutError
    │         └─ await asyncio.sleep(polling_interval)
    │
    └─ 3. 处理最终结果
          process_task_state(final_task, new_messages, agent_card, ...)
```

**`updates/streaming/handler.py`** - 流式处理器

流式处理通过 `send_message_and_get_task_id` 函数处理事件流中的每个事件。

**`updates/push_notifications/handler.py`** - 推送通知处理器

发送消息后，等待推送通知（通过 `PushNotificationResultStore` 存储结果）。

#### 通俗解释

**三种更新机制就像"三种等外卖的方式"**：

1. **流式（Streaming）**：就像外卖小哥实时给你发定位——"我取餐了"、"我在路上了"、"我到了"。你持续收到状态更新。

2. **轮询（Polling）**：就像你每隔 2 分钟打电话问外卖小哥"到哪了？"。每次轮询都会发出 `A2APollingStatusEvent` 事件，让你知道进度。

3. **推送通知（Push Notification）**：就像你留了个地址，外卖到了给你发短信。你不需要一直问，等着就行。

---

### 4.8 errors.py - 错误体系

#### 需求串讲

A2A 协议需要一套完整的错误处理系统，涵盖 JSON-RPC 标准错误、A2A 协议特定错误和 CrewAI 自定义扩展错误。

#### 实现逻辑

[errors.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/a2a/errors.py)

**错误码体系**（遵循 JSON-RPC 2.0 规范）：

| 错误码范围 | 类型 | 示例 |
|-----------|------|------|
| -32700 ~ -32600 | JSON-RPC 标准错误 | 解析错误、无效请求、方法未找到 |
| -32099 ~ -32000 | A2A 特定错误 | 任务未找到、不支持的操作、内容类型不兼容 |
| -32768 ~ -32100 | CrewAI 自定义扩展 | 版本不支持、扩展不支持、认证失败、速率限制、超时 |

**基类 `A2AError`**：
- `code`：错误码
- `message`：人类可读的错误信息
- `data`：可选的附加数据
- `to_dict()`：转为 JSON-RPC 错误对象
- `to_response(request_id)`：转为完整的 JSON-RPC 错误响应

**具体错误类**（20+ 种）：
- `JSONParseError`、`InvalidRequestError`、`MethodNotFoundError`
- `TaskNotFoundError`、`TaskNotCancelableError`、`PushNotificationNotSupportedError`
- `UnsupportedOperationError`、`ContentTypeNotSupportedError`、`InvalidAgentResponseError`
- `UnsupportedVersionError`、`UnsupportedExtensionError`
- `AuthenticationRequiredError`、`AuthorizationFailedError`
- `RateLimitExceededError`（带 retry_after）
- `TaskTimeoutError`、`TransportNegotiationFailedError`
- `ContextNotFoundError`、`SkillNotFoundError`、`ArtifactNotFoundError`

**工具函数**：
- `create_error_response(code, message, data, request_id)` → 创建 JSON-RPC 错误响应
- `is_retryable_error(code)` → 判断错误是否可重试（内部错误、速率限制、超时）
- `is_client_error(code)` → 判断是否是客户端错误

#### 通俗解释

**错误体系就像"医院的分诊系统"**：

- 每种错误都有一个唯一的"疾病编码"（错误码）
- 每个错误都有"病情描述"（错误信息）
- 有些"病"可以自愈（可重试错误），有些需要"病人"改行为（客户端错误）
- `to_response` 就是"开处方"——生成标准的错误响应格式

---

### 4.9 templates.py - 提示词模板

#### 需求串讲

当 Agent 被赋予 A2A 能力后，需要在 LLM 的提示词中加入关于可用远程 Agent 的信息、对话历史、当前轮次等。这些信息通过模板来格式化。

#### 实现逻辑

[templates.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/a2a/templates.py) 使用 Python 的 `string.Template` 来定义模板。

**模板列表**：

1. **`AVAILABLE_AGENTS_TEMPLATE`**：列出可用的 A2A Agent
   ```xml
   <AVAILABLE_A2A_AGENTS>
       {agent的JSON信息}
   </AVAILABLE_A2A_AGENTS>
   ```

2. **`PREVIOUS_A2A_CONVERSATION_TEMPLATE`**：展示之前的对话历史
   ```xml
   <PREVIOUS_A2A_CONVERSATION>
       {历史消息JSON}
   </PREVIOUS_A2A_CONVERSATION>
   ```

3. **`CONVERSATION_TURN_INFO_TEMPLATE`**：显示当前轮次和最大轮次
   ```xml
   <CONVERSATION_PROGRESS>
       turn="3" max_turns="10"
       WARNING: Next turn will be the last...
   </CONVERSATION_PROGRESS>
   ```

4. **`UNAVAILABLE_AGENTS_NOTICE_TEMPLATE`**：当 Agent 不可用时的通知

5. **`REMOTE_AGENT_COMPLETED_NOTICE`**：远程 Agent 完成后的通知
   - 告诉 LLM：远程 Agent 已经完成了，不要再发消息了，提取答案并结束

6. **`REMOTE_AGENT_RESPONSE_NOTICE`**：远程 Agent 回复后的通知
   - 告诉 LLM：用第三人称汇报远程 Agent 说了什么

#### 通俗解释

**模板就像"填表系统"**——预定义了格式，只替换动态内容：

- 就像你写邮件时用的模板：`尊敬的{客户姓名}，关于{项目名称}...`
- 这里是把"可用 Agent 列表"、"对话历史"、"轮次信息"等动态内容填入 XML 格式的模板中
- 用 XML 标签包裹是为了让 LLM 更容易理解这些信息的边界和含义

---

### 4.10 extensions/a2ui/ - 声明式 UI 扩展

#### 需求串讲

A2UI（Agent-to-UI）是 A2A 协议的一个扩展，允许 Agent 在回复中描述 UI 界面——比如按钮、卡片、表单、列表等。这让远程 Agent 不仅能回答问题，还能生成交互式界面。

#### 实现逻辑

**`client_extension.py`** - 客户端扩展

`A2UIClientExtension` 实现了 `A2AExtension` 协议：

1. **`extract_state_from_history`**：扫描对话历史中的 A2UI DataParts，跟踪 UI 表面（surface）状态
   - 支持 `beginRendering`、`surfaceUpdate`、`dataModelUpdate`、`deleteSurface` 等消息类型
   - 支持 v0.8 和 v0.9 两个协议版本

2. **`augment_prompt`**：在提示词中追加 A2UI 系统提示
   - 告诉 LLM 可以使用哪些 UI 组件
   - 告诉 LLM 如何生成 A2UI JSON

3. **`process_response`**：从 Agent 输出中提取和验证 A2UI JSON
   - 提取 JSON 对象
   - 验证是否符合 A2UI 规范
   - 如果设置了 `allowed_components`，过滤掉不允许的组件

4. **`prepare_message_metadata`**：在出站消息中注入 A2UI 客户端能力声明

**支持版本**：
- **v0.8**：使用 `beginRendering`、`surfaceUpdate`、`dataModelUpdate`、`deleteSurface`
- **v0.9**：使用 `createSurface`、`updateComponents`、`updateDataModel`、`deleteSurface`

**`catalog.py`** - UI 组件目录

定义了丰富的 UI 组件：Text、Button、Card、Column、Row、List、Modal、Tabs、TextField、CheckBox、Slider、DateTimeInput、Image、Video、AudioPlayer、Divider、Icon、MultipleChoice 等。

**`models.py`** - 数据模型

定义了 A2UI 消息/事件的数据模型（A2UIMessage、A2UIResponse、A2UIEvent、BeginRendering、SurfaceUpdate、DataModelUpdate、DeleteSurface、UserAction 等）。

**`prompt.py`** - 系统提示词生成

根据 catalog_id 和 allowed_components 生成 A2UI 系统提示词，告诉 LLM 如何生成 A2UI JSON。

**`validator.py`** - 验证器

验证 A2UI 消息和事件是否符合规范。

#### 通俗解释

**A2UI 就像"Agent 画界面"**：

- 普通 Agent 只能回复文字。
- 有了 A2UI，Agent 可以回复"请画一个按钮，上面写着'确认'，还有一个输入框"。
- 客户端收到这个描述后，就可以渲染出真正的 UI 界面。
- v0.8 和 v0.9 就像"画图指令"的两个版本——v0.8 用一套指令，v0.9 用另一套更新的指令。

---

### 4.11 extensions/server.py - 服务端扩展

#### 需求串讲

当 CrewAI Agent 作为 A2A 服务端运行时，它也可以支持协议扩展。客户端在请求中声明支持哪些扩展，服务端根据声明的扩展激活相应的功能。

#### 实现逻辑

[server.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/a2a/extensions/server.py)

**`ServerExtension`** - 服务端扩展基类：

```python
class ServerExtension(ABC):
    uri: str          # 扩展的唯一标识符
    required: bool    # 客户端是否必须支持
    description: str  # 人类可读的描述

    def agent_extension(self) -> AgentExtension:
        """生成 AgentCard 中的扩展声明"""

    def is_active(self, context: ExtensionContext) -> bool:
        """检查客户端是否声明支持此扩展"""

    async def on_request(self, context: ExtensionContext) -> None:
        """请求处理前钩子"""

    async def on_response(self, context: ExtensionContext, result: Any) -> Any:
        """响应处理后钩子"""
```

**`ExtensionContext`** - 扩展上下文：
- `metadata`：请求元数据
- `client_extensions`：客户端声明的扩展 URI 集合
- `state`：扩展间共享的状态字典
- `get_extension_metadata(uri, key)`：获取扩展特定的元数据（命名空间格式：`{uri}/{key}`）

**`ServerExtensionRegistry`** - 扩展注册表：
- `register(extension)`：注册扩展（URI 唯一）
- `get_agent_extensions()`：获取所有扩展的 AgentExtension 声明
- `invoke_on_request(context)`：调用所有活跃扩展的 on_request 钩子
- `invoke_on_response(context, result)`：链式调用所有活跃扩展的 on_response 钩子

#### 通俗解释

**服务端扩展就像"酒店的附加服务"**：

- 酒店（服务端）在官网上列出可以提供的附加服务（扩展声明）。
- 客人（客户端）预订时说"我需要WiFi和早餐"（在请求中声明扩展）。
- 酒店根据客人选择的附加服务，在入住时（on_request）和退房时（on_response）提供相应的服务。
- `ExtensionContext` 就像一个"服务单"，记录了客人选了哪些服务，以及服务之间的共享信息。

---

### 4.12 utils/logging.py - 结构化日志

#### 需求串讲

A2A 通信涉及多个 Agent 之间的交互，调试时需要清晰的日志。JSON 格式的结构化日志便于日志聚合系统（如 ELK、Splunk）解析和搜索。

#### 实现逻辑

[logging.py](file:///e:/AI/GitHub/crewAI-main/lib/crewai/src/crewai/a2a/utils/logging.py)

**`JSONFormatter`**：将日志记录格式化为 JSON
- 包含：timestamp、level、logger、message
- 自动包含异常信息
- 支持上下文变量（ContextVar）注入额外字段
- 支持特定属性（task_id、context_id、agent、endpoint、extension、error）

**`LogContext`**：上下文管理器，在作用域内为所有日志添加额外字段
```python
with LogContext(task_id="abc", context_id="xyz"):
    logger.info("Processing task")  # 日志中自动包含 task_id 和 context_id
```

**`configure_json_logging`**：配置 JSON 格式日志

#### 通俗解释

**结构化日志就像"表格化的日志"**：

- 普通日志：`2024-01-01 10:00:00 INFO Processing task`
- JSON 日志：`{"timestamp": "2024-01-01T10:00:00", "level": "INFO", "message": "Processing task", "task_id": "abc"}`
- JSON 格式方便机器解析，可以快速搜索"所有 task_id=abc 的日志"。

---

## 5. 完整调用链路图

### 5.1 客户端委托流程（完整版）

```
用户调用 agent.execute_task(task)
    │
    ▼
execute_task_with_a2a (包装后的方法)
    │
    ├─ 检查 agent.a2a 配置
    │
    ├─ get_a2a_agents_and_response_model()
    │   └─ 提取 A2A 配置 + 创建 AgentResponse 模型
    │
    └─ _execute_task_with_a2a()
        │
        ├─ _fetch_agent_cards_concurrently()
        │   └─ 并发获取所有远程 AgentCard
        │       └─ fetch_agent_card() → _afetch_agent_card_impl()
        │           ├─ HTTP GET /.well-known/agent-card.json
        │           ├─ 401 重试 (retry_on_401)
        │           └─ 返回 AgentCard
        │
        ├─ _augment_prompt_with_a2a()
        │   ├─ 构建可用 Agent 列表 (AVAILABLE_AGENTS_TEMPLATE)
        │   ├─ 构建对话历史 (PREVIOUS_A2A_CONVERSATION_TEMPLATE)
        │   ├─ 构建轮次信息 (CONVERSATION_TURN_INFO_TEMPLATE)
        │   └─ 扩展增强提示词 (extension_registry.augment_prompt_with_all)
        │
        ├─ original_fn(self, task, context, tools)  # 调用 LLM
        │
        ├─ _parse_agent_response()  # 解析 LLM 输出
        │
        └─ 如果 is_a2a == True:
            └─ _delegate_to_a2a()
                │
                └─ for turn in range(max_turns):
                    │
                    ├─ execute_a2a_delegation() / aexecute_a2a_delegation()
                    │   │
                    │   ├─ _afetch_agent_card_cached()  # 获取 AgentCard (缓存)
                    │   ├─ validate_auth_against_agent_card()  # 验证认证
                    │   ├─ validate_required_extensions()  # 验证扩展
                    │   ├─ negotiate_transport()  # 协商传输协议
                    │   ├─ negotiate_content_types()  # 协商内容类型
                    │   ├─ _prepare_auth_headers()  # 准备认证头
                    │   ├─ 构建 Message
                    │   ├─ _create_a2a_client()  # 创建 A2A 客户端
                    │   │   ├─ 创建 httpx.AsyncClient
                    │   │   ├─ 如果是 GRPC → _create_grpc_channel_factory()
                    │   │   └─ ClientFactory.create(agent_card)
                    │   │
                    │   └─ handler.execute(client, message, ...)
                    │       │
                    │       ├─ [Streaming] send_message → 处理事件流
                    │       ├─ [Polling] send_message → get task_id → 轮询
                    │       └─ [Push] send_message → 等待推送通知
                    │
                    ├─ _handle_task_completion()
                    │   ├─ 如果 trust_remote_completion_status → 直接返回
                    │   └─ 否则更新 reference_task_ids
                    │
                    └─ _handle_agent_response_and_continue()
                        ├─ _augment_prompt_with_a2a()  # 重新增强提示词
                        ├─ original_fn()  # 再次调用 LLM
                        └─ _process_response_result()
                            ├─ 如果 is_a2a=false → 返回最终结果
                            └─ 如果 is_a2a=true → 继续下一轮
```

### 5.2 服务端处理流程

```
远程客户端发送请求
    │
    ▼
execute(agent, context, event_queue)
    │
    └─ _execute_impl()
        │
        ├─ validate_message_parts()  # 验证内容类型
        ├─ extension_registry.invoke_on_request()  # 扩展钩子
        ├─ 解析消息 (Schema / DataParts / FileParts)
        ├─ 创建 CrewAI Task
        ├─ agent.aexecute_task(task)  # 执行任务
        │   └─ [cancellable 装饰器监控取消]
        ├─ extension_registry.invoke_on_response()  # 扩展钩子
        ├─ 创建产出物 (Artifact)
        └─ event_queue.enqueue_event()  # 返回结果
```

### 5.3 关键事件流

```
A2A 委托生命周期事件:
    A2ADelegationStartedEvent
        → A2AConversationStartedEvent (首轮)
        → A2ATransportNegotiatedEvent
        → A2AContentTypeNegotiatedEvent
        → A2AMessageSentEvent
        → A2AResponseReceivedEvent
        → A2AConversationCompletedEvent
    → A2ADelegationCompletedEvent

A2A 服务端事件:
    A2AServerTaskStartedEvent
        → A2AServerTaskCompletedEvent
        / A2AServerTaskFailedEvent
        / A2AServerTaskCanceledEvent

AgentCard 获取事件:
    A2AAgentCardFetchedEvent
    / A2AAuthenticationFailedEvent
    / A2AConnectionErrorEvent

轮询事件:
    A2APollingStartedEvent
        → A2APollingStatusEvent (每次轮询)
        → A2AResponseReceivedEvent (最终)
```

---

## 总结

A2A 模块是 CrewAI 中实现 Agent 间通信的完整协议栈，其设计遵循以下原则：

1. **分层清晰**：顶层包装器 → 中层配置与执行 → 底层基础设施
2. **协议兼容**：严格遵循 A2A 协议规范，支持 JSON-RPC 2.0 错误码、JWS 签名、扩展机制
3. **灵活扩展**：客户端扩展（A2AExtension）+ 服务端扩展（ServerExtension）+ A2UI 声明式 UI
4. **安全第一**：7 种认证方案 + TLS/mTLS + AgentCard 签名验证 + 认证不匹配检测
5. **容错健壮**：多轮对话支持、超时处理、401 重试、错误分类、Agent 不可用回退
6. **同步/异步双支持**：所有核心功能都有 sync/async 两个版本
7. **可观测性**：完整的事件系统 + 结构化 JSON 日志