# Graph Report - lib/crewai  (2026-07-16)

## Corpus Check
- Large corpus: 1355 files · ~1,462,703 words. Semantic extraction will be expensive (many Claude tokens). Consider running on a subfolder.

## Summary
- 18446 nodes · 39193 edges · 794 communities (625 shown, 169 thin omitted)
- Extraction: 68% EXTRACTED · 32% INFERRED · 0% AMBIGUOUS · INFERRED: 12663 edges (avg confidence: 0.67)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- .message()
- ._build_execution_prompt()
- PollingHandler
- Printer
- RootModel
- trace_batch_manager.py
- .create_agent_executor()
- Agent
- FlowTrigger
- Connection
- _RouteT
- ._collapse_to_outcome()
- FlowMethodName
- test_openai.py
- .aexecute_task()
- ExpressionData
- .fingerprint()
- .get_delegation_tools()
- _human_feedback.py
- AsyncQdrantClient
- FlowConditionType
- llm_events.py
- Json
- cohere_provider.py
- Flow
- BaseAgentExecutor
- conversational.py
- AbstractEventLoop
- BetaMessage
- ._rebind_memory_view()
- EdgeConfig
- test_azure.py
- ChatCompletion
- test_multimodal_integration.py
- _asummarize_chunks()
- InferenceConfigurationTypeDef
- .post_init_setup()
- Artifact
- dtype
- P2
- test_crew_multimodal.py
- SendMessageEvent
- test_anthropic.py
- A2AClientConfig
- ContextT
- APIKeyAuth
- AbstractContextManager
- ChatCompletionDeltaToolCall
- AmazonBedrockEmbeddingFunction
- Panel
- A2AServerConfig
- .handle_a2a_conversation_compl
- test_agent_multimodal.py
- .aquery_knowledge()
- EmbeddingDimensionMismatchErro
- test_multimodal.py
- test_bedrock.py
- v0_9.py
- A2UIAnyMessageDict
- _AgentDefinitionLoader
- client_schemes.py
- ._register_handlers()
- interactive.js
- CallableT
- FirstTimeTraceHandler
- convert_to_model()
- memory_scope.py
- catalog.py
- create_model_from_schema()
- convert_tools_to_openai_schema
- test_trace_enable_disable.py
- LLMGuardrailCompletedEvent
- .from_declaration()
- test_anthropic_interceptor.py
- AvailableExport
- AfterToolCallHookCallable
- config.py
- human_input.py
- persist()
- .batch_embed()
- EventNode
- output_format.py
- test_planning_types.py
- Event
- openai_adapter.py
- system_events.py
- OAuth2SecurityScheme
- _kickoff_with_a2a_support()
- completion.py
- .from_function()
- test_openai_interceptor.py
- test_unsupported_providers.py
- events.py
- test_flow_multimodal.py
- base_agent_adapter.py
- ConsoleFormatter
- AzureCompletion
- format_skill_context()
- test_utils.py
- client.py
- BaseSettings
- CrewOutput
- event_context.py
- reasoning_events.py
- .usage_metrics()
- test_crew_agent_parser.py
- test_token_manager.py
- SelfT
- ._handle_crew_planning()
- file_store.py
- interpolate_only()
- test_task_guardrails.py
- CaptureFixture
- NoReturn
- properties
- ._aexecute_tasks()
- Reset the emission sequence co
- read_file_tool.py
- test_async_tools.py
- HTTPTransport
- ._setup_executor()
- MemoryStorageFactory
- GeminiCompletion
- unified_memory.py
- test_azure_responses.py
- BoundTaskMethod
- converter.py
- test_task.py
- test_tool_call_streaming.py
- ._get_memory_systems()
- load_crew()
- Self
- test_human_feedback_integratio
- get_platform_integration_token
- Token
- CrewAIEventsBus
- .from_declaration()
- .aclose()
- wrappers.py
- KickoffTaskOutputsSQLiteStorag
- Any
- test_utils.py
- ExecutionPlan
- base.py
- Event emitted when a task eval
- result.py
- tool_resolver.py
- test_project.py
- AsyncHandlerSet
- MCPReadStream
- A2UIEvent
- ._is_any_available_memory()
- .__call__()
- _ConversationalMixin
- get_before_llm_call_hooks()
- .list_categories()
- test_crew_scoped_hooks.py
- AnyClassMethod
- analyze_query()
- plus_api.py
- BaseClient
- test_async_crew.py
- _conversation_start_router()
- ImportError
- ._setup_agent_executor()
- text_file_knowledge_source.py
- find_crew_json_file()
- rw_lock.py
- .search()
- BeforeToolCallHookCallable
- .skill()
- call_stop_override()
- OpenAICompatibleCompletion
- test_agent_a2a_kickoff.py
- test_transport.py
- test_embedding_factory.py
- llm_guardrail_events.py
- ClientCallContext
- AgentEvaluationCompletedEvent
- load_resources()
- test_agent_reasoning.py
- DoclingDocument
- content_type.py
- base_tool_adapter.py
- stdio.py
- _custom_tool_file()
- utils.py
- test_okta.py
- Path
- _build_data_part_v09()
- decorators.py
- excel_knowledge_source.py
- test_structured_planning.py
- COMPONENTS
- KnowledgeStorageFactory
- models.py
- trace_listener.py
- create_default_evaluator()
- crew_evaluator_handler.py
- import_utils.py
- args
- .create_status_content()
- ConversationState
- EvaluationScore
- ._init_client()
- base.py
- config.py
- discover_skills()
- mcp_tool_wrapper.py
- CalculatorTool
- ChatCompletions
- ._configure_format_from_task()
- base_agent.py
- sse.py
- PreparedDocuments
- test_google.py
- .on_inbound()
- server_capabilities.json
- base.py
- PlanStep
- Test when newer version is ava
- test_depends.py
- test_validation.py
- test_crew_thread_safety.py
- CodeExecutorTool
- Tests for typed file wrapper c
- Tests for the generic File cla
- Tests for the FUNCTION_SCHEMA 
- D
- MetadataFilter
- stream_context.py
- .create_lite_agent_branch()
- .get_trace()
- types.py
- base_file_knowledge_source.py
- EdgeType
- content_processor.py
- ._add_file_tools()
- transport.py
- ._ahandle_completion()
- Serialize a single guardrail v
- test_decorators.py
- test_litellm_async.py
- test_openai_async.py
- test_amp_mcp.py
- Tests for streaming cancellati
- Extension
- ModelWrapValidatorHandler
- surfaces
- extract_a2ui_json_objects()
- ._training_handler()
- .create_crew_memory()
- get_next_emission_sequence()
- get_triggering_event_id()
- lite_agent_output.py
- http.py
- parser.py
- _common_strict_pipeline()
- test_entra_id.py
- test_base_interceptor.py
- AgentCardSignature
- ChatCompletionsToolDefinition
- Content
- Settings
- properties
- description
- _serialize_input_provider()
- pdf_knowledge_source.py
- completion.py
- base.py
- loader.py
- core.py
- memory_tools.py
- Import and return the class/fu
- test_keycloak.py
- AsyncInterceptor
- Tests for LLM factory integrat
- MonkeyPatch
- test_streaming_integration.py
- RagClientFactory
- base_converter_adapter.py
- SkillModel
- cache.py
- FlowMethod
- Normalize an LLM call's raw us
- json_knowledge_source.py
- json_provider.py
- .ensure_guardrail_is_callable(
- T
- import_and_validate_definition
- test_event_replay.py
- test_storage_factory.py
- test_flow_crew_span_integratio
- test_flow_human_input_integrat
- createSurface
- basic_catalog.json
- ._setup_graph()
- .check_config()
- conversational_mixin.py
- filters.py
- .uuid_str()
- _is_non_roundtrippable()
- internal_instructor.py
- _FixedUsageLLM
- test_azure_async.py
- test_bedrock_async.py
- test_google_async.py
- Tests for the OPENAI_COMPATIBL
- test_google_vertex_memory_inte
- AsyncCodeExecutorTool
- A2AClientConfigTypes
- AgentInterface
- .validate_and_set_attributes()
- Any
- base_evaluator.py
- goal_metrics.py
- Manages the global skill cache
- crew_loader.py
- crew_context.py
- serialization.py
- test_workos.py
- TestTemplateCommand
- test_callback.py
- test_tool_usage_limit.py
- A2AError
- $ref
- base_output_converter.py
- .create_panel()
- handlers.py
- csv_knowledge_source.py
- ._has_custom_openai_base_url()
- azure.py
- mcp_native_tool.py
- Convert a dotted path string t
- test_auth0.py
- Test _is_version_yanked helper
- test_client.py
- test_file_store.py
- Tests for normalize_input_file
- A2AClientTimeoutError
- GenerateContentResponse
- condition
- .augment_prompt()
- structured_output_converter.py
- constants.py
- .answer_from_history_turn()
- _flag.py
- .format_text_content()
- crew_definition.py
- file_handler.py
- Any
- test_cache.py
- test_telemetry_disable.py
- ClassDefContext
- ModuleSpec
- description
- any
- _normalize_ollama_base_url()
- common.py
- process.py
- EmbeddingFunction
- parse_tool_call_args()
- PickleHandler
- GuardrailResult
- build_rich_field_description()
- test_base_agent.py
- test_agent_a2a_wrapping.py
- test_factory_azure.py
- test_execution_span_assignment
- _flow_level_persist_yaml()
- Tests for async method support
- ._run()
- Tests for MIME type detection.
- test_lock_store.py
- Unit tests with mocked LLM pro
- GenerateContentConfig
- OTLPSpanExporter
- Signals
- ArtifactNotFoundError
- description
- any
- structured_output_converter.py
- Push the latest recorded ``tas
- on_signal()
- extract_json_from_llm_response
- flow_config.py
- Strip JSONC comments and trail
- Validate JSON crew structure w
- Any
- Path
- CustomLLM
- Regression tests for EPD-179: 
- test_training_converter.py
- PrinterColor
- updateDataModel
- .to_dict()
- description
- description
- parser.py
- JSONAgentDefinition
- validation.py
- callable_to_string()
- aclear_task_files()
- Recursively resolve all local 
- test_run_crew.py
- test_prompt_cache.py
- Tests for _resolve_external wi
- test_tool_resolver_native.py
- test_client_factory_registry.p
- Test that invalid JSON falls b
- assert_parity()
- test_agent_tools.py
- test_files.py
- Tests for FileStream class.
- test_serialization.py
- Tests for AgentReasoning with 
- ChannelCredentials
- id
- path
- ._migrate_deprecated_transport
- allOf
- description
- anyOf
- description
- description
- base_event_listener.py
- source_helper.py
- OutputClass
- BaseModel
- test_agent_inject_date.py
- test_utils.py
- JWTAuthLLM
- .call()
- Custom LLM implementation with
- test_llm_streaming_finish_reas
- EventT_co
- currency
- name
- surfaceId
- client_capabilities.json
- meta.py
- .sanitize_tool_name()
- ._gracefully_fail()
- .add_event()
- AgentMessage
- .to_dict()
- ._parse_amp_ref()
- Unpack
- Unpack
- handle_partial_json()
- test_main.py
- test_replay_from_task.py
- Test execution behavior of cre
- Test suite for async AsyncHTTP
- test_openai_compatible.py
- Test acreate_collection with a
- assert_agent_runtime_field_sch
- test_markdown_task.py
- Tests for args_schema validati
- test_thread_safety.py
- Tests for wrap_file_source fun
- Node
- _get_default_update_config()
- additionalProperties
- server_to_client.json
- description
- ._check_execution_error()
- ._call_handlers()
- set_tui_mode()
- Any
- _router.py
- _types.py
- _outputs.py
- types.py
- cache.py
- bedrock.py
- watsonx.py
- Self
- force_additional_properties_fa
- Remove null type from anyOf/ty
- test_custom_llm.py
- test_crewai_event_bus.py
- test_file_handler.py
- components
- deleteSurface
- supportedCatalogIds
- properties
- description
- description
- length
- not
- numeric
- openUrl
- pluralize
- regex
- required
- description
- FunctionCall
- additionalProperties
- LogContext
- .get_multimodal_tools()
- ._get_context()
- flow_trackable.py
- constants.py
- ensure_type_in_schemas()
- test_callback_with_taskoutput.
- test_factory.py
- test_models.py
- test_imports.py
- Test implementation with a syn
- Tests for args_schema validati
- Integration tests with real LL
- FlowPersistenceFactory
- Pattern
- common_types.json
- config.py
- ._cleanup_mcp_clients()
- __init__.py
- Any
- reasoning_metrics.py
- __init__.py
- ._init_client()
- __init__.py
- types.py
- types.py
- types.py
- types.py
- types.py
- types.py
- types.py
- types.py
- types.py
- types.py
- types.py
- types.py
- types.py
- types.py
- checkpoint_config.py
- .append()
- BaseModel
- .__init__()
- DisclosureLevel
- allOf
- allOf
- allOf
- allOf
- DateTimeInput
- Divider
- Icon
- Image
- List
- Modal
- Row
- Slider
- Tabs
- Text
- TextField
- Video
- description
- description
- url
- event_bus.py
- testing.py
- TypedDict
- _start.py
- .aclose()
- ._get_responses_base_url()
- ._add_property_ordering()
- __init__.py
- _map_task_variables()
- .__init__()
- Documents
- Test that the LLM factory pass
- Test compaction triggered via 
- Test compaction triggered via 
- AuthorizationFailedError
- ContextNotFoundError
- MethodNotFoundError
- The specified task was not fou
- The task cannot be canceled.
- The requested operation is not
- The requested A2A version is n
- Client does not support requir
- Task execution timed out.
- Failed to negotiate a compatib
- The specified skill was not fo
- DynamicBoolean
- DynamicString
- .get_output_converter()
- .to_json()
- Any
- .__aenter__()
- Any
- Any
- conftest.py
- _checkpoint_chain_flow()
- __init__.py
- __init__.py
- __init__.py
- __init__.py
- templates.py
- __init__.py
- __init__.py
- __init__.py
- __init__.py
- __init__.py
- __init__.py
- __init__.py
- constants.py
- constants.py
- __init__.py
- oauth2.py
- auth0.py
- base_provider.py
- entra_id.py
- __init__.py
- keycloak.py
- okta.py
- workos.py
- token.py
- token_manager.py
- utils.py
- __init__.py
- __init__.py
- .fetch_inputs()
- ._set_tasks_callbacks()
- __init__.py
- event_bus_types.py
- __init__.py
- __init__.py
- __init__.py
- __init__.py
- flow_context.py
- __init__.py
- __init__.py
- __init__.py
- __init__.py
- __init__.py
- __init__.py
- __init__.py
- __init__.py
- __init__.py
- __init__.py
- __init__.py
- constants.py
- constants.py
- __init__.py
- __init__.py
- types.py
- types.py
- __init__.py
- types.py
- __init__.py
- __init__.py
- __init__.py
- __init__.py
- __init__.py
- __init__.py
- __init__.py
- __init__.py
- __init__.py
- __init__.py
- __init__.py
- __init__.py
- __init__.py
- __init__.py
- __init__.py
- __init__.py
- __init__.py
- __init__.py
- __init__.py
- types.py
- constants.py
- __init__.py
- __init__.py
- constants.py
- __init__.py
- __init__.py
- Increment the delegations coun
- Validate the output file path.
- Set attributes based on the ag
- .__init__()
- Set the summary field based on
- Get the JSON string representa
- constants.py
- __init__.py
- __init__.py
- __init__.py
- __init__.py
- lock_store.py
- paths.py
- printer.py
- version.py
- __init__.py
- __init__.py
- __init__.py
- __init__.py
- __init__.py
- __init__.py
- __init__.py
- test_concurrent_storage.py
- Test that acreate_collection c
- Test that get_or_create_collec
- Test get_or_create_collection 
- Test that aget_or_create_colle
- Test aget_or_create_collection
- Test that add_documents adds d
- Test add_documents with custom
- Test add_documents with docume
- Test add_documents when all do
- Test that add_documents raises
- Test that aadd_documents adds 
- Test aadd_documents with docum
- Test that aadd_documents raise
- Test that search queries the c
- Test search with optional para
- Test that asearch queries the 
- Test asearch with optional par
- Test that delete_collection ca
- Test that adelete_collection c
- Test that areset calls the und
- Test add_documents with batch 
- Test add_documents with explic
- Test aadd_documents with batch
- Test aadd_documents with expli
- Test that create_collection ca
- Test that client initializes w
- Test create_collection with al
- setup.sh
- __init__.py
- crewai
- Type stub for decorator usage.

## God Nodes (most connected - your core abstractions)
1. `LLM` - 984 edges
2. `Agent` - 780 edges
3. `Crew` - 614 edges
4. `Task` - 611 edges
5. `BaseLLM` - 310 edges
6. `BaseTool` - 300 edges
7. `BaseEvent` - 238 edges
8. `BaseAgent` - 235 edges
9. `AgentExecutor` - 201 edges
10. `Flow` - 200 edges

## Surprising Connections (you probably didn't know these)
- `agent()` --calls--> `Agent`  [INFERRED]
  tests/mcp/test_amp_mcp.py → src/crewai/agent/core.py
- `agent()` --calls--> `Agent`  [INFERRED]
  tests/mcp/test_tool_resolver_native.py → src/crewai/agent/core.py
- `sample_agent()` --calls--> `Agent`  [INFERRED]
  tests/test_task_guardrails.py → src/crewai/agent/core.py
- `base_agent()` --calls--> `Agent`  [INFERRED]
  tests/utilities/test_events.py → src/crewai/agent/core.py
- `test_integration_valid_and_invalid()` --indirect_call--> `AgentFinish`  [INFERRED]
  tests/agents/test_crew_agent_parser.py → src/crewai/agents/parser.py

## Import Cycles
- 1-file cycle: `src/crewai/rag/chromadb/config.py -> src/crewai/rag/chromadb/config.py`

## Communities (794 total, 169 thin omitted)

### Community 0 - ".message()"
Cohesion: 0.01
Nodes (329): Send a single message and get a response.          Creates a temporary Task + Cr, Crew, BaseModel, Represents a group of agents, defining how they should collaborate and the     t, Add recall and remember tools when memory is available.          Args:, Ensure that a crew has at least one non-conditional task., Ensure the first task is not a ConditionalTask., Ensure that ConditionalTask is not async. (+321 more)

### Community 1 - "._build_execution_prompt()"
Cohesion: 0.02
Nodes (193): Build the execution prompt, stop words, and RPM limit function.          Args:, PlanningConfig, BaseModel, Configuration for agent planning/reasoning before task execution.      This allo, AgentAction, OutputParserError, Exception, Represents an action to be taken by an agent. (+185 more)

### Community 2 - "PollingHandler"
Cohesion: 0.02
Nodes (239): PollingHandler, Polling-based update handler., PushNotificationHandler, Push notification (webhook) based update handler., SSE streaming-based update handler., StreamingHandler, _afetch_agent_card_impl(), Internal async implementation of AgentCard fetching. (+231 more)

### Community 3 - "Printer"
Cohesion: 0.02
Nodes (181): Printer, CrewAgentExecutor, AgentAction, Any, Execute the agent asynchronously with given inputs.          Args:             i, Execute agent loop asynchronously until completion.          Checks if the LLM s, Execute agent loop asynchronously using ReAct text-based pattern.          Retur, Execute agent loop asynchronously using native function calling.          This m (+173 more)

### Community 4 - "RootModel"
Cohesion: 0.02
Nodes (143): RootModel, Self, Restore an Agent from a checkpoint, ready to resume via kickoff().          Args, Fork an Agent from a checkpoint, creating a new execution branch.          Args:, Re-create runtime objects after restoring from a checkpoint.          Args:, Rebuild the event scope stack from the checkpoint's event record.          Args:, apply_execution_context(), capture_execution_context() (+135 more)

### Community 5 - "trace_batch_manager.py"
Cohesion: 0.02
Nodes (165): Any, Mark a trace batch as failed, routing to the correct endpoint., Mark that an event handler started processing (for synchronization)., Mark that an event handler finished processing (for synchronization)., Wait for all pending event handlers to finish processing          Args:, Send buffered events to backend with graceful failure handling, Finalize batch and return it for sending, Send batch finalization to backend          Args:             events_count: Numb (+157 more)

### Community 6 - ".create_agent_executor()"
Cohesion: 0.02
Nodes (159): Create an agent executor for the agent.          Returns:             An instanc, Update executor parameters without recreating instance.          Args:, AgentAction, Execute text-parsed tool calls with tool usage events., Any, BaseModel, Callback handler for tool usage.      Attributes:         last_used_tool: The mo, Run when tool ends running.          Args:             calling: The tool calling (+151 more)

### Community 7 - "Agent"
Cohesion: 0.02
Nodes (164): Agent, SkillModel, Inject the current date into the task description if inject_date is enabled., Deprecated: No-op. CodeInterpreterTool is no longer available., Represents an agent in a system.      Each agent has a role, a goal, a backstory, Check if planning is enabled for this agent., Load configured skills while preserving explicit disclosure levels.          Pat, Apply skill context, tool preparation, and training data to the task prompt. (+156 more)

### Community 8 - "FlowTrigger"
Cohesion: 0.02
Nodes (154): FlowTrigger, Creates a routing method that directs flow execution based on conditions.      T, router(), test_sets_flow_context_when_inside_flow(), test_sets_flow_context_when_using_crewbase_pattern_inside_flow(), ``suppress_flow_events=True`` silences MethodExecution events so         infrast, Path, Tests for the static Flow Definition contract. (+146 more)

### Community 9 - "Connection"
Cohesion: 0.02
Nodes (114): Connection, HumanFeedbackPending, HumanFeedbackProvider, PendingFeedbackContext, Any, Exception, Flow, Protocol (+106 more)

### Community 10 - "_RouteT"
Cohesion: 0.02
Nodes (93): _RouteT, Build an observation without an LLM call.          Used when ``PlanningConfig.ob, AgentExecutor, Any, Handle full replanning — regenerate the remaining plan.          Preserves compl, Check if todos were created from planning.          Routes to todo-driven execut, Find todos whose dependencies are satisfied.          Determines if we can execu, Execute a single todo using StepExecutor (Plan-and-Execute mode)         or fall (+85 more)

### Community 11 - "._collapse_to_outcome()"
Cohesion: 0.01
Nodes (149): Collapse free-form feedback to a predefined outcome using LLM.          This met, LLM, LiteLLM sends ``max_tokens or max_completion_tokens`` as the cap., Derives the custom_llm_provider from the model string.         - For example, if, Check if the model supports function calling.          Note: This method is only, Returns the context window size, using 75% of the maximum to avoid         cutti, Create a shallow copy of the LLM instance., Create a deep copy of the LLM instance. (+141 more)

### Community 12 - "FlowMethodName"
Cohesion: 0.02
Nodes (93): FlowMethodName, PendingListenerKey, Restore the event scope stack from a checkpoint., restore_event_scope(), Set tracing enabled state for current execution context.      Args:         enab, set_tracing_enabled(), Emit a final ``FlowFinishedEvent`` and finalize the trace batch.          Pairs, FlowPersistence (+85 more)

### Community 13 - "test_openai.py"
Cohesion: 0.01
Nodes (170): Test that builtin_tools parameter is properly configured., Test that builtin_tools can be combined with custom function tools., Custom OpenAI-compatible endpoints may serve non-OpenAI model ids., Test Responses API with web_search built-in tool., Test ResponsesAPIResult dataclass functionality., Test ResponsesAPIResult.has_tool_outputs() method., Test ResponsesAPIResult.has_reasoning() method., Test that parse_tool_outputs parameter is properly configured. (+162 more)

### Community 14 - ".aexecute_task()"
Cohesion: 0.03
Nodes (111): Prepare common setup for task execution shared by sync and async paths., Finalize task execution with RPM cleanup, tool processing, and event emission., Execute a task with the agent.          Args:             task: Task to execute., Execute a task with the agent asynchronously.          Args:             task: T, build_task_prompt_with_schema(), format_task_with_context(), get_knowledge_config(), Get knowledge configuration from agent.      Args:         agent: The agent inst (+103 more)

### Community 15 - "ExpressionData"
Cohesion: 0.04
Nodes (103): ExpressionData, LocalContext, NestedStepRunner, FlowConversationalDefinition, FlowConversationalRouterDefinition, BaseModel, Static conversational Flow definition models.  This module is part of the serial, Static conversational router configuration. (+95 more)

### Community 16 - ".fingerprint()"
Cohesion: 0.02
Nodes (125): Get the agent's fingerprint.          Returns:             Fingerprint: The agen, Set the agent's security fingerprint., Get the crew's fingerprint.          Returns:             Fingerprint: The crew', Fingerprint, Any, BaseModel, datetime, Self (+117 more)

### Community 17 - ".get_delegation_tools()"
Cohesion: 0.02
Nodes (88): Check if the LLM supports native function calling with the given tools., LangGraphAgentAdapter, Any, LangGraph agent adapter for CrewAI integration.  This module contains the LangGr, Build a system prompt for the LangGraph agent.          Creates a prompt that in, Configure the LangGraph agent for execution.          Args:             tools: O, Configure tools for the LangGraph agent.          Merges additional tools with e, Implement delegation tools support for LangGraph.          Creates delegation to (+80 more)

### Community 18 - "_human_feedback.py"
Cohesion: 0.02
Nodes (95): human_feedback(), Any, F, Decorator for Flow methods that require human feedback.      The decorator is a, _deserialize_llm_from_context(), _distill_and_store_lessons(), DistilledLessons, _get_hitl_prompt() (+87 more)

### Community 19 - "AsyncQdrantClient"
Cohesion: 0.02
Nodes (83): AsyncQdrantClient, ClientMethodMismatchError, Core exceptions for RAG module., Create a ClientMethodMismatchError.          Args:             method_name: Meth, Raised when a method is called with the wrong client type.      Typically used w, Any, Unpack, QdrantClient (+75 more)

### Community 20 - "FlowConditionType"
Cohesion: 0.03
Nodes (115): FlowConditionType, and_(), _coerce_trigger(), _condition_tree(), _is_condition(), or_(), Any, FlowDefinitionCondition (+107 more)

### Community 21 - "llm_events.py"
Cohesion: 0.03
Nodes (101): FunctionCall, LLMEventBase, LLMStreamChunkEvent, LLMThinkingChunkEvent, BaseModel, Event emitted when a streaming chunk is received, Event emitted when a thinking/reasoning chunk is received from a thinking model, ToolCall (+93 more)

### Community 22 - "Json"
Cohesion: 0.02
Nodes (83): Json, LogRecord, configure_json_logging(), JSONFormatter, Structured JSON logging utilities for A2A module., Configure JSON logging for the A2A module.      Args:         logger_name: Logge, JSON formatter for structured logging.      Outputs logs as JSON with consistent, Format log record as JSON string. (+75 more)

### Community 23 - "cohere_provider.py"
Cohesion: 0.03
Nodes (77): CohereProvider, Cohere embeddings provider., Cohere embeddings provider., GenerativeAiProvider, Google Generative AI embeddings provider., Google Generative AI embeddings provider., Google Vertex AI embeddings provider.  This module supports both the new google-, Google Vertex AI embeddings provider with dual SDK support.      Supports both l (+69 more)

### Community 24 - "Flow"
Cohesion: 0.02
Nodes (71): Flow, A test flow that creates and runs an agent., Test that LiteAgent with tools works correctly inside a Flow., test_lite_agent_inside_flow_with_tools(), TestFlow, Test that from_pending uses SQLiteFlowPersistence by default., Test that resume raises error without pending context., MockInputProvider (+63 more)

### Community 25 - "BaseAgentExecutor"
Cohesion: 0.03
Nodes (86): BaseAgentExecutor, BaseModel, analyze_for_consolidation(), analyze_for_save(), ConsolidationPlan, ExtractedMetadata, _get_prompt(), MemoryAnalysis (+78 more)

### Community 26 - "conversational.py"
Cohesion: 0.03
Nodes (55): _conversational_only(), ConversationConfig, ConversationMessage, F, Conversational types and helpers shared by ``Flow`` (experimental).  The convers, Canonical user-facing message shared across conversational turns., Mark a method as part of the conversational built-in graph.      Methods carryin, LLM router configuration for the experimental conversational ``Flow``.      .. w (+47 more)

### Community 27 - "AbstractEventLoop"
Cohesion: 0.03
Nodes (84): AbstractEventLoop, Queue, FileInput, Executes the Crew's workflow for each input and aggregates results.          Arg, Asynchronous kickoff method to start the crew execution.          Args:, Executes the Crew's workflow for each input asynchronously.          Args:, Native async kickoff method using async task execution throughout.          Unli, Native async execution of the Crew's workflow for each input.          Uses nati (+76 more)

### Community 28 - "BetaMessage"
Cohesion: 0.04
Nodes (69): BetaMessage, BetaToolUseBlock, LLMCallType, Enum, Type of LLM call being made, Delta, FunctionArgs, TypedDict (+61 more)

### Community 29 - "._rebind_memory_view()"
Cohesion: 0.03
Nodes (96): Reattach a fresh ``Memory`` to a restored ``MemoryScope``/``MemorySlice``., Resolve memory field: True creates a default Memory(), instance is used as-is., Reattach a live ``Memory`` to restored ``MemoryScope``/``MemorySlice`` views., extract_memories_from_content(), ExtractedMemories, Use the LLM to extract discrete memory statements from raw content.      This is, LLM output for extracting discrete memories from raw content., Memory (+88 more)

### Community 30 - "EdgeConfig"
Cohesion: 0.04
Nodes (71): EdgeConfig, EdgeShard, Filter, Point, _build_scope_ancestors(), Any, datetime, Path (+63 more)

### Community 31 - "test_azure.py"
Cohesion: 0.02
Nodes (100): mock_azure_credentials(), Test that the completion module is properly imported when using Azure provider, Test that api_version is properly passed to the client, Test that timeout and max_retries parameters are stored, Test that optional parameters are included in completion params when set, Test that 'azure/' prefix is properly stripped when constructing endpoint, Test that all message roles (system, user, assistant) are preserved correctly, Test that DeepSeek and other non-OpenAI models work correctly with Azure AI Infe (+92 more)

### Community 32 - "ChatCompletion"
Cohesion: 0.04
Nodes (54): ChatCompletion, ChatCompletionChunk, OpenAICompletion, Any, BaseModel, Response, Handle streaming Responses API call., Handle async streaming Responses API call. (+46 more)

### Community 33 - "test_multimodal_integration.py"
Cohesion: 0.03
Nodes (72): _build_multimodal_message(), _build_multimodal_message_with_upload(), _build_responses_message_with_upload(), Integration tests for LLM multimodal functionality with cassettes.  These tests, Integration tests for OpenAI o4-mini reasoning model with vision., Test o4-mini can describe an image., Integration tests for OpenAI GPT-4.1-mini with vision., Test GPT-4.1-mini can describe an image. (+64 more)

### Community 34 - "_asummarize_chunks()"
Cohesion: 0.03
Nodes (56): _asummarize_chunks(), _estimate_token_count(), _extract_summary_tags(), _format_messages_for_summary(), Estimate token count using a conservative cross-provider heuristic.      Args:, Format messages with role labels for summarization.      Skips system messages., Split messages into chunks at message boundaries.      Excludes system messages, Extract content between <summary></summary> tags.      Falls back to the full te (+48 more)

### Community 35 - "InferenceConfigurationTypeDef"
Cohesion: 0.04
Nodes (60): InferenceConfigurationTypeDef, ClientError, Reports a client-side error., Get messages from the last task execution.          Returns:             List of, Compatibility property - returns state messages., Get native provider class if available., llm_call_context(), Context manager that establishes an LLM call scope with a unique call_id. (+52 more)

### Community 36 - ".post_init_setup()"
Cohesion: 0.03
Nodes (58): Self, Initialize LLM, executor, code tools, and skills after model creation., Check to determine if stop words are being used.          Returns:             b, Set up the LLM and other components after initialization., BaseLLM, Any, Invoke after_llm_call hooks for direct LLM calls (no agent context).          Th, Abstract base class for LLM implementations.      This class defines the interfa (+50 more)

### Community 37 - "Artifact"
Cohesion: 0.03
Nodes (69): Artifact, EventQueue, FileWithBytes, FileWithUri, RequestContext, ServerCallContext, Extract A2UI catalog preferences from the client request.          Stores the ne, ExtensionContext (+61 more)

### Community 38 - "dtype"
Cohesion: 0.03
Nodes (63): dtype, ndarray, EmbedderConfig, Initialize knowledge sources with the agent or crew embedder config., Reset crew and agent knowledge storage., Create the knowledge for the crew., Knowledge, BaseModel (+55 more)

### Community 39 - "P2"
Cohesion: 0.03
Nodes (63): P2, R2, _ArgsSchemaPlaceholder, _default_cache_function(), EnvVar, _is_async_callable(), _is_awaitable(), ABC (+55 more)

### Community 40 - "test_crew_multimodal.py"
Cohesion: 0.03
Nodes (64): audio_file(), _create_analyst_crew(), image_bytes(), image_file(), pdf_file(), AudioFile, ImageFile, PDFFile (+56 more)

### Community 41 - "SendMessageEvent"
Cohesion: 0.03
Nodes (78): SendMessageEvent, extract_error_message(), extract_task_result_parts(), process_task_state(), A2ATask, AgentCard, Any, Message (+70 more)

### Community 42 - "test_anthropic.py"
Cohesion: 0.02
Nodes (88): mock_anthropic_api_key(), Test that Anthropic correctly tracks cached_prompt_tokens when tools are used., tool_search=True should inject bm25 tool search and defer all tools., Test Anthropic-specific parameters like stop_sequences and streaming, tool_search with regex config should use regex variant., tool_search=None (default) should NOT inject anything., If user passes a tool search tool manually, don't inject a duplicate., _convert_tools_for_interference should pass through tool search tools unchanged. (+80 more)

### Community 43 - "A2AClientConfig"
Cohesion: 0.06
Nodes (84): A2AClientConfig, A2AConfig, Configuration for A2A protocol integration.      Deprecated:         Use A2AClie, Configuration for connecting to remote A2A agents.      Attributes:         endp, ExtensionRegistry, Registry for managing A2A extensions.      Maintains a collection of extensions, Initialize the extension registry., create_extension_registry_from_config() (+76 more)

### Community 44 - "ContextT"
Cohesion: 0.03
Nodes (58): ContextT, ReturnT, LLMCallHookContext, Any, Request human input during LLM hook execution.          This method pauses live, Context object passed to LLM call hooks.      Provides hooks with complete acces, Initialize hook context with executor reference or direct parameters.          A, AfterLLMCallHook (+50 more)

### Community 45 - "APIKeyAuth"
Cohesion: 0.04
Nodes (80): APIKeyAuth, HandlerType, HTTPDigestAuth, Role, ClientAuthScheme, Base class for client-side authentication schemes.      Client auth schemes appl, BaseModel, Base class for server-side authentication schemes.      Each scheme validates in (+72 more)

### Community 46 - "AbstractContextManager"
Cohesion: 0.05
Nodes (65): AbstractContextManager, AsyncClientAPI, AsyncCollection, ClientAPI, Collection, Include, QueryResult, ChromaDBClient (+57 more)

### Community 47 - "ChatCompletionDeltaToolCall"
Cohesion: 0.05
Nodes (40): ChatCompletionDeltaToolCall, defaultdict, AccumulatedToolArgs, _ensure_litellm(), Any, BaseModel, Lazy-load litellm on first use. Returns True if available., Handle callbacks with usage info for streaming responses.          Args: (+32 more)

### Community 48 - "AmazonBedrockEmbeddingFunction"
Cohesion: 0.04
Nodes (73): AmazonBedrockEmbeddingFunction, CohereEmbeddingFunction, GoogleGenerativeAiEmbeddingFunction, HuggingFaceEmbeddingFunction, InstructorEmbeddingFunction, JinaEmbeddingFunction, OllamaEmbeddingFunction, ONNXMiniLM_L6_V2 (+65 more)

### Community 49 - "Panel"
Cohesion: 0.04
Nodes (64): Panel, Show a message when tracing is disabled., Display the ephemeral trace link to the user and automatically open browser., Show message when user declines tracing., Check if this is first time and initialize collection., Handle the completion flow as shown in your diagram., Send batch initialization to backend, Show a message when tracing is disabled. (+56 more)

### Community 50 - "A2AServerConfig"
Cohesion: 0.04
Nodes (53): A2AServerConfig, Configuration for exposing a Crew or Agent as an A2A server.      All fields cor, afetch_agent_card(), _afetch_agent_card_cached(), _agent_to_agent_card(), _crew_to_agent_card(), fetch_agent_card(), _fetch_agent_card_cached() (+45 more)

### Community 51 - ".handle_a2a_conversation_compl"
Cohesion: 0.04
Nodes (38): Handle plan refinement event., Handle plan replan triggered event., Handle goal achieved early event., Handle agent logs started event., Handle memory retrieval started event with panel display., Handle memory retrieval completed event with panel display., Handle memory query failed event with panel display., Handle memory save started event with panel display. (+30 more)

### Community 52 - "test_agent_multimodal.py"
Cohesion: 0.04
Nodes (54): audio_file(), _create_analyst_agent(), image_bytes(), image_file(), pdf_file(), AudioFile, ImageFile, PDFFile (+46 more)

### Community 53 - ".aquery_knowledge()"
Cohesion: 0.04
Nodes (55): Query the crew's knowledge base for relevant information., Query the crew's knowledge base for relevant information asynchronously., Query across all knowledge sources to find the most relevant information., Query across all knowledge sources asynchronously.          Args:             qu, KnowledgeStorage, Any, Search for documents in the knowledge base asynchronously.          Args:, Save documents to the knowledge base asynchronously.          Args: (+47 more)

### Community 54 - "EmbeddingDimensionMismatchErro"
Cohesion: 0.06
Nodes (43): EmbeddingDimensionMismatchError, ValueError, Raised when an embedding's dimensionality doesn't match the existing store., LanceDBStorage, Any, datetime, Path, Read vector dimension from an existing table's schema. (+35 more)

### Community 55 - "test_multimodal.py"
Cohesion: 0.03
Nodes (43): mock_api_keys(), Unit tests for LLM multimodal functionality across all providers., Test unsupported content type is skipped., Test OpenAI Responses PDF support with an inferred GPT provider., Tests for Anthropic provider multimodal functionality., Test Claude 3 supports multimodal., Test Claude 4 supports multimodal., Test Anthropic image format uses source-based structure. (+35 more)

### Community 56 - "test_bedrock.py"
Cohesion: 0.03
Nodes (70): bedrock_mocks(), _create_bedrock_mocks(), mock_aws_credentials(), Ensure single tool call still produces a single-block user message., Tool results from different assistant turns must NOT be merged., Test that cached tokens (cacheReadInputTokenCount) are tracked for Bedrock., Test that the alternate key cacheReadInputTokens also works., Test that missing cache token keys default to zero. (+62 more)

### Community 57 - "v0_9.py"
Cohesion: 0.04
Nodes (68): AccessibilityAttributes, ActionEvent, ActionV09, AudioPlayerV09, ButtonV09, CardV09, CheckBoxV09, CheckRule (+60 more)

### Community 58 - "A2UIAnyMessageDict"
Cohesion: 0.05
Nodes (62): A2UIAnyMessageDict, A2UIClientExtension, A2UIConversationState, A2UIMessageDict, A2UIMessageV09Dict, BeginRenderingDict, ComponentEntryDict, CreateSurfaceDict (+54 more)

### Community 59 - "_AgentDefinitionLoader"
Cohesion: 0.12
Nodes (68): _AgentDefinitionLoader, _a2a_python_ref_errors(), _agent_allowed_fields(), _agent_class_from_definition(), _agent_kwargs_from_definition(), _crew_allowed_fields(), _crew_kwargs_from_definition(), _definition_has_python_type() (+60 more)

### Community 60 - "client_schemes.py"
Cohesion: 0.06
Nodes (49): APIKeyAuth, AuthScheme, BearerTokenAuth, HTTPBasicAuth, HTTPDigestAuth, OAuth2AuthorizationCode, OAuth2ClientCredentials, ABC (+41 more)

### Community 61 - "._register_handlers()"
Cohesion: 0.05
Nodes (28): _ensure_handlers_registered(), _find_checkpoint(), Register the checkpoint handler on all known event classes.      Only the sync h, Register checkpoint handlers on the event bus once, lazily., Coerce a checkpoint field value.      Returns:         CheckpointConfig — use th, Resolve a checkpoint config starting from an agent, walking to its crew., Find the CheckpointConfig for an event source.      Walks known relationships: T, _register_all_handlers() (+20 more)

### Community 62 - "interactive.js"
Cohesion: 0.06
Nodes (9): AnimationManager, CONSTANTS, DrawerManager, drawRoundedRect(), highlightPython(), loadVisCDN(), NetworkManager, NodeRenderer (+1 more)

### Community 63 - "CallableT"
Cohesion: 0.05
Nodes (54): CallableT, AgentConfig, close_mcp_server(), CrewBase, CrewBaseMeta, _CrewBaseType, _filter_methods(), _get_all_methods() (+46 more)

### Community 64 - "FirstTimeTraceHandler"
Cohesion: 0.04
Nodes (38): FirstTimeTraceHandler, Handles the first-time user trace collection and display flow., Set reference to batch manager for sending events.          Args:             ba, Mark that events have been collected during execution., Initialize trace collection listener.          Args:             batch_manager:, Tests: trace_batch_id is cleared when _initialize_backend_batch fails., trace_batch_id must be None when the API call raises an exception., trace_batch_id must be set from the server response on success. (+30 more)

### Community 65 - "convert_to_model()"
Cohesion: 0.07
Nodes (64): convert_to_model(), Converter, get_conversion_instructions(), Convert a result to a Pydantic model or JSON.      Args:         result: The res, Class that converts text into either pydantic or json., Generate conversion instructions based on the model and LLM capabilities.      A, InternalInstructor, Class that wraps an agent LLM with instructor for structured output generation. (+56 more)

### Community 66 - "memory_scope.py"
Cohesion: 0.05
Nodes (39): _ensure_memory_kind(), MemoryScope, MemorySlice, Any, BaseModel, datetime, Self, Scoped and sliced views over unified Memory. (+31 more)

### Community 67 - "catalog.py"
Cohesion: 0.06
Nodes (62): Action, ActionBoundValue, ActionContextEntry, ArrayBinding, AudioPlayer, BooleanBinding, Button, Card (+54 more)

### Community 68 - "create_model_from_schema()"
Cohesion: 0.05
Nodes (18): create_model_from_schema(), Create a Pydantic model from a JSON schema.      This function takes a JSON sche, Tests for pydantic_schema_utils module.  Covers: - create_model_from_schema: typ, Realistic MCP tool schema exercising multiple features simultaneously., TestAllOfMerging, TestCreateModelFromSchemaRecursive, TestEdgeCases, TestEndToEndMCPSchema (+10 more)

### Community 69 - "convert_tools_to_openai_schema"
Cohesion: 0.05
Nodes (36): convert_tools_to_openai_schema(), Convert CrewAI tools to OpenAI function calling format.      This function conve, Tests that malformed JSON tool arguments produce clear errors     instead of sil, Create a minimal CrewAgentExecutor with mocked dependencies., Malformed JSON args must return a descriptive error, not silently become {}., Valid JSON args should execute the tool as before., Unsupported native tools errors should continue through ReAct., When func_args is already a dict, no JSON parsing occurs. (+28 more)

### Community 70 - "test_trace_enable_disable.py"
Cohesion: 0.04
Nodes (33): Tests to verify that traces are sent when enabled and not sent when disabled.  V, Test suite to verify trace sending behavior with VCR cassette recording., Test execution when tracing disabled via CREWAI_TRACING_ENABLED=false., Test execution when tracing=False explicitly set., Test execution when tracing enabled via CREWAI_TRACING_ENABLED=true., Test execution when tracing=True explicitly set., TestTraceEnableDisable, Test that non-ephemeral batch initialization does not send anon_id (+25 more)

### Community 71 - "LLMGuardrailCompletedEvent"
Cohesion: 0.04
Nodes (57): LLMGuardrailCompletedEvent, Event emitted when a guardrail task completes      Attributes:         success:, CalculatorTool, With memory=None (default), _memory is None and no memory is used., With memory=True, _memory is a Memory instance., With a custom memory instance, kickoff calls recall and then extract_memories/re, Test that Agent can use tools., Test that Agent can return a simple structured output. (+49 more)

### Community 72 - ".from_declaration()"
Cohesion: 0.06
Nodes (55): Load a declarative flow from contents or a file path., test_agent_action_rejects_non_string_input_in_definition(), test_agent_action_reports_invalid_cel_expression(), test_agent_action_round_trips_with_inline_definition(), test_config_input_provider_from_declaration(), test_crew_action_normalizes_named_agent_list_definition(), test_crew_action_rejects_incomplete_inline_agent_definition(), test_crew_action_rejects_non_mapping_inputs_in_definition() (+47 more)

### Community 73 - "test_anthropic_interceptor.py"
Cohesion: 0.04
Nodes (39): AnthropicHeaderInterceptor, AnthropicLoggingInterceptor, AnthropicTestInterceptor, Request, Response, Tests for Anthropic provider with interceptor integration., Interceptor that logs Anthropic request/response details., Initialize logging lists. (+31 more)

### Community 74 - "AvailableExport"
Cohesion: 0.06
Nodes (57): AvailableExport, EnvVarEntry, extract_available_exports(), _extract_env_vars(), _extract_field_default(), _extract_init_params_schema(), _extract_run_params_schema(), _extract_single_tool_metadata() (+49 more)

### Community 75 - "AfterToolCallHookCallable"
Cohesion: 0.06
Nodes (41): AfterToolCallHookCallable, AfterToolCallHookType, clear_all_tool_call_hooks(), get_after_tool_call_hooks(), Register a global after_tool_call hook.      Global hooks are added to all tool, Get all registered global after_tool_call hooks.      Returns:         List of r, Unregister a specific global before_tool_call hook.      Args:         hook: The, Unregister a specific global after_tool_call hook.      Args:         hook: The (+33 more)

### Community 76 - "config.py"
Cohesion: 0.04
Nodes (44): _coerce_signature(), PushNotificationConfig, BaseModel, Push notification update mechanism configuration., Convert string secret to WebhookSignatureConfig., Configuration for webhook-based task updates.      Attributes:         url: Call, BaseModel, Enum (+36 more)

### Community 77 - "human_input.py"
Cohesion: 0.05
Nodes (37): _async_readline(), AsyncExecutorContext, ExecutorContext, get_provider(), HumanInputProvider, Protocol, Token, Human input provider for HITL (Human-in-the-Loop) flows. (+29 more)

### Community 78 - "persist()"
Cohesion: 0.04
Nodes (52): persist(), T, Decorator to persist flow state.      This decorator can be applied at either th, PoemState, Test that persisted state properly overrides default values., Test that persisted state values override class defaults., Test default value override with multiple start methods., Test state model with default values that should be overridden. (+44 more)

### Community 79 - ".batch_embed()"
Cohesion: 0.05
Nodes (41): Any, Embed all items in a single embedder call., Apply all consolidation plans with batch re-embedding and bulk insert., Initialize the encoding flow.          Args:             storage: Storage backen, Deduplicate, composite-score, rank, and attach evidence gaps., Get information about a scope.          Args:             scope: The scope path., compute_composite_score(), embed_text() (+33 more)

### Community 80 - "EventNode"
Cohesion: 0.08
Nodes (22): EventNode, EventRecord, BaseModel, Directed record of execution events with O(1) node lookup.      Events are added, Return a snapshot of every node under the read lock.          Returns:, Remove all nodes from the record under the write lock., A node wrapping a single event with its adjacency lists., The execution event record. (+14 more)

### Community 81 - "output_format.py"
Cohesion: 0.04
Nodes (34): OutputFormat, Enum, str, Task output format definitions for CrewAI., Enum that represents the output format of a task.      Attributes:         JSON:, _AsyncOnlyOutput, BaseModel, Tests for async task execution. (+26 more)

### Community 82 - "test_planning_types.py"
Cohesion: 0.04
Nodes (31): Tests for planning types (PlanStep, TodoItem, TodoList)., Test TodoItem creation with all fields., Test all valid status values., Test that each TodoItem gets a unique auto-generated ID., Test TodoItem can be serialized to dict., Tests for the PlanStep model., Tests for the TodoList model., Create an empty TodoList. (+23 more)

### Community 83 - "Event"
Cohesion: 0.06
Nodes (50): Event, ChatInputField, ChatInputs, BaseModel, Crew chat input models.  This module provides models for defining chat inputs an, Represents a single required input for the crew.      Example:         ```python, Holds crew metadata and input field definitions.      Example:         ```python, build_system_message() (+42 more)

### Community 84 - "openai_adapter.py"
Cohesion: 0.05
Nodes (37): OpenAIAgentAdapter, Any, Unpack, OpenAI agents adapter for CrewAI integration.  This module contains the OpenAIAg, Execute a task using the OpenAI Assistant.          Configures the assistant, pr, Configure the OpenAI agent for execution.          While OpenAI handles executio, Configure tools for the OpenAI Assistant.          Args:             tools: Opti, Process OpenAI Assistant execution result.          Converts any structured outp (+29 more)

### Community 85 - "system_events.py"
Cohesion: 0.06
Nodes (37): IntEnum, System signal event types for CrewAI.  This module contains event types for syst, Enumeration of supported system signals., Event emitted when SIGTERM is received., Event emitted when SIGINT is received., Event emitted when SIGHUP is received., Event emitted when SIGTSTP is received.      Note: SIGSTOP cannot be caught - it, SigHupEvent (+29 more)

### Community 86 - "OAuth2SecurityScheme"
Cohesion: 0.05
Nodes (37): OAuth2SecurityScheme, APIKeyServerAuth, AuthenticatedUser, _coerce_secret_str(), EnterpriseTokenAuth, HTTPException, MTLSServerAuth, OAuth2ServerAuth (+29 more)

### Community 87 - "_kickoff_with_a2a_support()"
Cohesion: 0.06
Nodes (31): _kickoff_with_a2a_support(), LiteAgent, AfterLLMCallHookCallable, AfterLLMCallHookType, Any, BaseModel, BeforeLLMCallHookCallable, BeforeLLMCallHookType (+23 more)

### Community 88 - "completion.py"
Cohesion: 0.10
Nodes (12): _base_url_from_account_identifier(), _normalize_snowflake_base_url(), Any, Drop dangling Claude tool-use turns before sending to Snowflake.          Snowfl, Return a Snowflake Cortex REST OpenAI-compatible base URL., Snowflake Cortex REST API native completion implementation.      Snowflake expos, SnowflakeCompletion, MonkeyPatch (+4 more)

### Community 89 - ".from_function()"
Cohesion: 0.05
Nodes (47): Create a tool from a function.          Args:             func: The function to, _build_inferred_structured_value(), _build_plain_structured_value(), build_simple_crew(), _build_structured_values(), custom_tool(), custom_tool_decorator(), BaseModel (+39 more)

### Community 90 - "test_openai_interceptor.py"
Cohesion: 0.05
Nodes (33): AuthInterceptor, LoggingInterceptor, OpenAITestInterceptor, Request, Response, Tests for OpenAI provider with interceptor integration., Interceptor that logs request/response details for testing., Initialize logging lists. (+25 more)

### Community 91 - "test_unsupported_providers.py"
Cohesion: 0.05
Nodes (34): DummyInterceptor, Request, Response, Tests for interceptor behavior with unsupported providers., Test that Bedrock LLM raises NotImplementedError with interceptor., Test that Bedrock raises NotImplementedError when interceptor is used., Test that Bedrock LLM works without interceptor., Set dummy API keys for providers that require them. (+26 more)

### Community 92 - "events.py"
Cohesion: 0.06
Nodes (32): Download lifecycle events for registry-backed skills.  These events are emitted, Event emitted when a registry skill download begins., Event emitted when a registry skill download completes., SkillDownloadCompletedEvent, SkillDownloadStartedEvent, download_skill(), _is_noninteractive(), is_registry_ref() (+24 more)

### Community 93 - "test_flow_multimodal.py"
Cohesion: 0.05
Nodes (39): audio_file(), image_bytes(), image_file(), pdf_file(), AudioFile, ImageFile, PDFFile, TextFile (+31 more)

### Community 94 - "base_agent_adapter.py"
Cohesion: 0.06
Nodes (28): BaseAgentAdapter, ABC, Any, Base class for all agent adapters in CrewAI.      This abstract class defines th, Configure and adapt tools for the specific agent implementation.          Args:, Configure the structured output for the specific agent implementation., Set private attributes., BaseModel (+20 more)

### Community 95 - "ConsoleFormatter"
Cohesion: 0.05
Nodes (26): ConsoleFormatter, Handle A2A message sent event - store for display with response., Pause Live session updates to allow for human input without interference., Resume Live session updates after human input is complete.          New streamin, Show crew started panel., Show flow started panel., Handle completion of LLM streaming - stop the streaming live display., Show version update message if a newer version is available.          Only displ (+18 more)

### Community 96 - "AzureCompletion"
Cohesion: 0.04
Nodes (39): AzureCompletion, Check if the model supports function calling., Get the context window size for the model., Azure reasoning/newer chat models cap via ``max_completion_tokens``., Get the last response ID from Responses API auto-chaining., Reset the Responses API auto-chain state., Reset the Responses API reasoning chain state., Check if the model supports multimodal inputs.          Azure OpenAI vision-enab (+31 more)

### Community 97 - "format_skill_context()"
Cohesion: 0.06
Nodes (26): format_skill_context(), Format skill information for agent prompt injection.      At METADATA level: ret, Any, BaseModel, Path, Pydantic data models for the Agent Skills standard.  Defines DisclosureLevel, Sk, Skill name from frontmatter., Skill description from frontmatter. (+18 more)

### Community 98 - "test_utils.py"
Cohesion: 0.06
Nodes (40): create_file(), create_init_file(), Create a temporary directory for testing tool extraction., Test that extract_tools_metadata returns empty list for empty project., Test that extract_tools_metadata returns empty list when no __init__.py exists., Test that extract_tools_metadata returns empty list for empty __init__.py., Test that extract_tools_metadata returns empty list when __all__ is not defined., Test that extract_tools_metadata extracts metadata from a valid BaseTool class. (+32 more)

### Community 99 - "client.py"
Cohesion: 0.07
Nodes (27): MCPClient, Any, BaseException, datetime, Self, _T, MCP client with session management for CrewAI agents., Check if client is connected to server. (+19 more)

### Community 100 - "BaseSettings"
Cohesion: 0.05
Nodes (32): BaseSettings, ProviderSpec, Any, Coerce list of dicts into typed BaseKnowledgeSource subclasses via source_type., _resolve_knowledge_sources(), _serialize_embedder_spec(), BaseEmbeddingsProvider, Base class for embedding providers. (+24 more)

### Community 101 - "CrewOutput"
Cohesion: 0.06
Nodes (38): CrewOutput, Any, BaseModel, Class that represents the result of a crew., Token usage as a plain dict.          Same attribute name and shape as ``LiteAge, Convert json_output and pydantic_output to a dictionary., AfterKickoffMethod, AgentMethod (+30 more)

### Community 102 - "event_context.py"
Cohesion: 0.08
Nodes (35): EmptyStackError, event_scope(), EventContextConfig, EventPairingError, get_current_parent_id(), get_enclosing_parent_id(), handle_empty_pop(), handle_mismatch() (+27 more)

### Community 103 - "reasoning_events.py"
Cohesion: 0.07
Nodes (29): AgentReasoningCompletedEvent, AgentReasoningFailedEvent, AgentReasoningStartedEvent, Any, Event emitted when an agent starts reasoning about a task., Event emitted when an agent finishes its reasoning process., Event emitted when the reasoning process fails., Base event for reasoning events. (+21 more)

### Community 104 - ".usage_metrics()"
Cohesion: 0.06
Nodes (26): Aggregated LLM token usage for the most recent kickoff (or         resume) of th, LiteAgentOutput, Any, BaseModel, Get only the completed todos., Get only the failed todos., Check if the agent executed with a plan., Return the raw output as a string. (+18 more)

### Community 105 - "test_crew_agent_parser.py"
Cohesion: 0.04
Nodes (3): # TODO: ADD TEST TO MAKE SURE ** REMOVAL DOESN'T MESS UP ANYTHING, test_integration_valid_and_invalid(), test_valid_final_answer_parsing()

### Community 106 - "test_token_manager.py"
Cohesion: 0.04
Nodes (25): Tests for TokenManager with atomic file operations., Test that expired token returns None., Test that missing token file returns None., Test clearing tokens deletes the token file., Test atomic file operations directly., Set up test fixtures with temp directory., Test cases for TokenManager., Clean up temp directory. (+17 more)

### Community 107 - "SelfT"
Cohesion: 0.07
Nodes (43): SelfT, after_kickoff(), agent(), before_kickoff(), cache_handler(), _call_method(), callback(), crew() (+35 more)

### Community 108 - "._handle_crew_planning()"
Cohesion: 0.08
Nodes (24): Handles the Crew planning., CrewPlanner, PlannerTaskPydanticOutput, PlanPerTask, BaseModel, Handles planning and coordination of crew tasks., Safely retrieve knowledge source content from the task's agent.          Args:, Creates a summary of all tasks.          Returns:             A string summarizi (+16 more)

### Community 109 - "file_store.py"
Cohesion: 0.09
Nodes (37): aclear_files(), aget_all_files(), aget_files(), aget_task_files(), astore_files(), astore_task_files(), clear_files(), get_all_files() (+29 more)

### Community 110 - "interpolate_only()"
Cohesion: 0.06
Nodes (32): interpolate_only(), Any, Interpolate placeholders (e.g., {key}) in a string while leaving JSON untouched., Test the interpolate_only method for various scenarios including JSON structure, Test the interpolate_only method for various scenarios including JSON structure, test_interpolate_complex_combination(), test_interpolate_custom_object_validation(), test_interpolate_edge_cases() (+24 more)

### Community 111 - "test_task_guardrails.py"
Cohesion: 0.06
Nodes (44): create_smart_task(), Test that guardrail error is passed in context for retry., Smart task factory that automatically assigns a mock agent when guardrails are p, Test that LLMGuardrail correctly validates task output.      Note: Due to VCR ca, Test that HallucinationGuardrail integrates properly with the task system., Test that tasks work normally without guardrails (backward compatibility)., Test that multiple guardrails are processed sequentially., Test multiple guardrails where one fails validation. (+36 more)

### Community 112 - "CaptureFixture"
Cohesion: 0.08
Nodes (14): CaptureFixture, _create_sqlite_checkpoint(), _make_checkpoint_data(), Any, Tests for checkpoint CLI commands., TestDiffCheckpoints, TestParseDuration, TestPruneCommand (+6 more)

### Community 113 - "NoReturn"
Cohesion: 0.07
Nodes (26): NoReturn, _is_resuming_agent_executor(), Any, FileInput, PlatformAppOrAction, TypeIs, Core agent implementation for the CrewAI framework., Deprecated: CodeInterpreterTool is no longer available. (+18 more)

### Community 114 - "properties"
Cohesion: 0.05
Nodes (42): properties, description, $ref, description, $ref, description, $ref, description (+34 more)

### Community 115 - "._aexecute_tasks()"
Cohesion: 0.07
Nodes (25): Future, Executes tasks sequentially using native async and returns the final output., Creates and assigns a manager agent to complete the tasks using native async., Executes tasks using native async and returns the final output.          Args:, Handle conditional task evaluation using native async., Process pending async tasks and return their outputs., Executes tasks sequentially and returns the final output., Creates and assigns a manager agent to complete the tasks. (+17 more)

### Community 116 - "Reset the emission sequence co"
Cohesion: 0.08
Nodes (24): Reset the emission sequence counter to 1.      Resets for the current context on, reset_emission_counter(), Reset the last event ID to None.      Should be called at the start of a new flo, reset_last_event_id(), Parallel flow executions should maintain correct triggered_by chains independent, AND condition listener should have triggered_by_event_id pointing to the last co, Events emitted after exception should still have correct triggered_by., Synchronous methods should still have correct triggered_by. (+16 more)

### Community 117 - "read_file_tool.py"
Cohesion: 0.05
Nodes (25): BaseModel, FileInput, Tool for reading input files provided to the crew., Schema for read file tool arguments., Tool for reading input files provided to the crew kickoff.      Provides agents, Set available input files.          Args:             files: Dictionary mapping, Read an input file by name.          Args:             file_name: The name of th, Extract text from a PDF instead of returning base64. (+17 more)

### Community 118 - "test_async_tools.py"
Cohesion: 0.05
Nodes (26): AsyncTool, Tests for async tool functionality., Test async decorated tool works with run()., Test tool with synchronous _run method., Test sync decorated tool arun() raises NotImplementedError., Test async decorated tool works with arun()., Tests for async tools with simulated I/O operations., Test async tool with simulated I/O delay. (+18 more)

### Community 119 - "HTTPTransport"
Cohesion: 0.08
Nodes (33): HTTPTransport, MCPServerHTTP, MCPServerSSE, MCPServerStdio, BaseModel, MCP server configuration models for CrewAI agents.  This module provides Pydanti, Stdio MCP server configuration.      This configuration is used for connecting t, HTTP/Streamable HTTP MCP server configuration.      This configuration is used f (+25 more)

### Community 120 - "._setup_executor()"
Cohesion: 0.07
Nodes (29): Self, Configure executor after Pydantic field initialization., clear_all_global_hooks(), Clear all global hooks across all hook types (LLM and Tool).      This is a conv, clear_after_llm_call_hooks(), clear_all_llm_call_hooks(), clear_before_llm_call_hooks(), get_after_llm_call_hooks() (+21 more)

### Community 121 - "MemoryStorageFactory"
Cohesion: 0.06
Nodes (25): MemoryStorageFactory, Any, datetime, Protocol, Storage backend protocol for the unified memory system., Update an existing record. Replaces the record with the same ID., Return a single record by ID, or None if not found.          Args:             r, List records in a scope, newest first.          Args:             scope_prefix: (+17 more)

### Community 122 - "GeminiCompletion"
Cohesion: 0.05
Nodes (35): GeminiCompletion, Check if the model supports function calling., Check if the model supports stop words., Get the context window size for the model., Gemini caps generation via ``max_output_tokens``., Check if the model supports multimodal inputs.          Gemini models support im, Google Gemini native completion implementation.      This class provides direct, Test that stop words are NOT applied when response_model is provided.     This e (+27 more)

### Community 123 - "unified_memory.py"
Cohesion: 0.06
Nodes (25): _default_embedder(), _non_streaming_analysis_llm(), _passthrough(), Any, datetime, Future, OpenAIEmbeddingFunction, Unified Memory class: single intelligent memory with LLM analysis and pluggable (+17 more)

### Community 124 - "test_azure_responses.py"
Cohesion: 0.07
Nodes (18): azure_env(), _create_azure_responses(), mock_openai_completion(), Tests for Azure OpenAI Responses API support.  Verifies that AzureCompletion wit, When api='responses', azure-ai-inference clients should not be created., Endpoint with /openai/deployments/... should still produce correct base_url., Set Azure environment variables for tests., Params left at defaults should not be passed to the delegate. (+10 more)

### Community 125 - "BoundTaskMethod"
Cohesion: 0.08
Nodes (27): BoundTaskMethod, _copy_method_metadata(), DecoratedMethod, args, kwargs, P, R, Self (+19 more)

### Community 126 - "converter.py"
Cohesion: 0.10
Nodes (30): async_convert_to_model(), async_convert_with_instructions(), async_handle_partial_json(), convert_with_instructions(), ConverterError, create_converter(), Any, BaseModel (+22 more)

### Community 127 - "test_task.py"
Cohesion: 0.05
Nodes (26): clear_cache(), mock_agent(), mock_context(), mock_event_queue(), Tests for A2A task utilities., Function raises CancelledError when cancel flag is set., Cancel flag is cleaned up after execution., Context can be passed as keyword argument. (+18 more)

### Community 128 - "test_tool_call_streaming.py"
Cohesion: 0.07
Nodes (30): get_all_stream_events(), get_temperature_tool_schema(), get_tool_call_events(), mock_emit(), Any, Tests for tool call streaming events across LLM providers.  These tests verify t, Tests for the structure and content of tool call streaming events., Test that tool call events accumulate arguments progressively. (+22 more)

### Community 129 - "._get_memory_systems()"
Cohesion: 0.08
Nodes (28): Reset specific or all memories for the crew.          Args:             command_, Reset a single memory system.          Args:             system: The memory syst, Reset all available memory systems., Reset a specific memory system.          Args:             memory_type: Type of, Get all available memory systems with their configuration.          Returns:, mock_crew(), Tests for CLI commands that require crewai core (reset-memories).  Non-core CLI, test_reset_agent_knowledge() (+20 more)

### Community 130 - "load_crew()"
Cohesion: 0.22
Nodes (10): load_crew(), Load a ``Crew`` from a JSON/JSONC definition file.      The definition file desc, _input_file_path(), MonkeyPatch, Path, Tests for crewai.project.crew_loader., TestLoadCrew, _write_agent() (+2 more)

### Community 131 - "Self"
Cohesion: 0.06
Nodes (27): Self, Records that a feature was used. One span = one count.          Args:, Records when a template is downloaded and installed.          Args:, Set the tracer provider if ready and not already set., Flush and shutdown the telemetry provider on process exit.          Uses a short, Records the start of a deployment process.          Args:             uuid: Uniq, Records the creation of a new crew deployment., Records the retrieval of crew logs.          Args:             uuid: Unique iden (+19 more)

### Community 132 - "test_human_feedback_integratio"
Cohesion: 0.05
Nodes (26): Integration tests for the @human_feedback decorator with Flow.  This module test, Tests for routing integration with @listen decorators., Test that collapsed outcome routes to the matching @listen method., Tests for state management with human feedback., Test that feedback is accessible in downstream listeners., Test that feedback history is preserved across flow execution., Tests for async flow integration., Test that @human_feedback works with async flows. (+18 more)

### Community 133 - "get_platform_integration_token"
Cohesion: 0.11
Nodes (15): get_platform_integration_token(), platform_context(), Set the platform integration token in the current context.      Args:         in, Get the platform integration token from the current context or environment., Context manager to temporarily set the platform integration token.      Args:, set_platform_integration_token(), Test that platform_context properly resets token even when exception occurs., Test platform_context when initial state is None. (+7 more)

### Community 134 - "Token"
Cohesion: 0.09
Nodes (22): Token, Set the current task ID in the context. Returns a token for reset., Reset the current task ID to its previous value., reset_current_task_id(), set_current_task_id(), _deserialize_model_class(), Any, BaseModel (+14 more)

### Community 135 - "CrewAIEventsBus"
Cohesion: 0.08
Nodes (24): CrewAIEventsBus, Self, Create or return the singleton instance.          Returns:             The singl, Initialize the event bus internal state.          Creates handler dictionaries., Run the background async event loop., Set the RuntimeState that will be passed to event handlers., The RuntimeState currently attached to the bus, if any., Detach the RuntimeState and clear the entity registry. (+16 more)

### Community 136 - ".from_declaration()"
Cohesion: 0.05
Nodes (36): Path, Build a runnable declarative flow from contents or a file path., _run_capturing_flow_lifecycle(), test_code_action_interpolates_strings_and_lists(), test_code_action_renders_keyword_inputs(), test_code_action_supports_callable_instance_refs(), test_config_checkpoint_from_declaration(), test_config_defer_trace_finalization_from_declaration() (+28 more)

### Community 137 - ".aclose()"
Cohesion: 0.06
Nodes (19): Any, Cancel streaming and clean up resources., Cancel streaming and clean up resources., Base class for streaming output with result access.      Provides iteration over, Initialize streaming output base., Check if streaming has completed., Check if streaming was cancelled., Get all collected chunks so far. (+11 more)

### Community 138 - "wrappers.py"
Cohesion: 0.08
Nodes (23): AfterLLMCallHookMethod, AfterToolCallHookMethod, BeforeLLMCallHookMethod, BeforeToolCallHookMethod, _copy_method_metadata(), Any, Wrapper for methods marked as before_tool_call hooks within @CrewBase classes., Initialize the hook method wrapper. (+15 more)

### Community 139 - "KickoffTaskOutputsSQLiteStorag"
Cohesion: 0.08
Nodes (23): KickoffTaskOutputsSQLiteStorage, Any, Update an existing task output record in the database.          Updates fields o, Load all task output records from the database.          Returns:             Li, An updated SQLite storage class for kickoff task outputs storage., Delete all task output records from the database.          This method removes a, Initialize the SQLite database and create the latest_kickoff_task_outputs table., Add a new task output record to the database.          Args:             task: T (+15 more)

### Community 140 - "Any"
Cohesion: 0.07
Nodes (19): Any, Span, Records human feedback feature usage.          Args:             event_type: Typ, Execute telemetry operation safely, checking both readiness and environment vari, Records the creation of a crew.          Args:             crew: The crew being, Records task started in a crew.          Args:             crew: The crew execut, Records the completion of a task execution in a crew.          Args:, Records when a tool is used repeatedly, which might indicate an issue. (+11 more)

### Community 141 - "test_utils.py"
Cohesion: 0.06
Nodes (20): Tests for ChromaDB utility functions., Test suite for _prepare_documents_for_chromadb function., Test preparing documents that already have doc_ids., Test preparing documents without doc_ids (should generate hashes)., Test preparing documents with list metadata (should take first item)., Test preparing documents without metadata., Test suite for ChromaDB utility functions., Test that identical content produces identical hashes. (+12 more)

### Community 142 - "ExecutionPlan"
Cohesion: 0.08
Nodes (25): ExecutionPlan, Handler, Depends, T, Declares a dependency on another event handler.      Similar to FastAPI's Depend, Initialize a dependency on a handler.          Args:             handler: The ha, Return a string representation of the dependency.          Returns:, Check equality based on the handler reference.          Args:             other: (+17 more)

### Community 143 - "base.py"
Cohesion: 0.09
Nodes (22): A2AExtension, ConversationState, Any, Message, Protocol, Base extension interface for CrewAI A2A wrapper processing hooks.  This module d, Augment the task prompt with extension-specific instructions.          Called du, Process and potentially modify the agent response.          Called after parsing (+14 more)

### Community 144 - "Event emitted when a task eval"
Cohesion: 0.10
Nodes (22): Event emitted when a task evaluation is completed, TaskEvaluationEvent, Entity, Any, BaseModel, Evaluate the training data based on the llm output, human feedback, and improved, A class to evaluate the performance of an agent based on the tasks they have per, Initializes the TaskEvaluator with the given LLM and agent.          Args: (+14 more)

### Community 145 - "result.py"
Cohesion: 0.10
Nodes (11): ExperimentResultsDisplay, Any, ExperimentResult, ExperimentResults, Any, BaseModel, ExperimentRunner, Any (+3 more)

### Community 146 - "tool_resolver.py"
Cohesion: 0.10
Nodes (18): MCPToolResolver, Any, MCP tool resolution for CrewAI agents.  This module extracts all MCP-related too, Fetch AMP configs in bulk and return their tools and clients.          Resolves, Fetch MCP server configurations via CrewAI+ API.          Sends a GET request to, Resolve an HTTPS MCP server URL into tools., Resolve an ``MCPServerConfig`` into tools.          Returns ``(tools, clients)``, Resolves MCP server references / configs into CrewAI ``BaseTool`` instances. (+10 more)

### Community 147 - "test_project.py"
Cohesion: 0.11
Nodes (21): another_simple_tool(), InternalCrew, InternalCrewWithMCP, @crew-decorated factory method should set Crew.name to the decorated class name., Explicit Crew(name=...) inside @crew should win over the @CrewBase class name., simple_tool(), SimpleCrew, test_after_kickoff_modification() (+13 more)

### Community 148 - "AsyncHandlerSet"
Cohesion: 0.08
Nodes (21): AsyncHandlerSet, Any, AsyncHandler, Future, P, R, SyncHandler, Lazily initialize the thread pool executor and event loop.          Called on fi (+13 more)

### Community 149 - "MCPReadStream"
Cohesion: 0.07
Nodes (22): MCPReadStream, MCPWriteStream, BaseTransport, ABC, Any, BaseException, Enum, Self (+14 more)

### Community 150 - "A2UIEvent"
Cohesion: 0.10
Nodes (22): A2UIEvent, A2UIMessage, Union wrapper for the four server-to-client A2UI message types.      Exactly one, Enforce the spec's exactly-one-of constraint., Union wrapper for client-to-server events., Enforce the spec's exactly-one-of constraint., _json_schema_valid(), Any (+14 more)

### Community 151 - "._is_any_available_memory()"
Cohesion: 0.08
Nodes (23): Save kickoff result to memory. No-op if agent has no memory., Check if unified memory is available (agent or crew)., get_i18n(), I18N, BaseModel, Self, Internationalization support for CrewAI prompts and messages., Retrieve a prompt by kind and key.          Args:             kind: The kind of (+15 more)

### Community 152 - ".__call__()"
Cohesion: 0.10
Nodes (30): message_to_llm_dict(), Message history from state, coerced to LLM-shaped dicts., Any, Coerce a stored ``ConversationMessage`` (or dict) into an ``LLMMessage``., Use this config as a class decorator., append_message(), _coerce_user_message_text(), ConversationalConfig (+22 more)

### Community 153 - "_ConversationalMixin"
Cohesion: 0.12
Nodes (10): _ConversationalMixin, _iter_condition_labels(), Any, BaseModel, ConversationState, Route the current turn via the LLM router.          When ``ConversationConfig.ro, Append a message to conversation history (legacy ChatState path)., Whether per-turn ``FlowFinished`` + ``finalize_batch`` should be skipped. (+2 more)

### Community 154 - "get_before_llm_call_hooks()"
Cohesion: 0.09
Nodes (25): get_before_llm_call_hooks(), BeforeLLMCallHookCallable, BeforeLLMCallHookType, Register a global before_llm_call hook.      Global hooks are added to all execu, Get all registered global before_llm_call hooks.      Returns:         List of r, Unregister a specific global before_llm_call hook.      Args:         hook: The, register_before_llm_call_hook(), unregister_before_llm_call_hook() (+17 more)

### Community 155 - ".list_categories()"
Cohesion: 0.09
Nodes (13): List categories and counts.          Args:             path: Scope path to filte, List immediate child scopes under path.          Args:             path: Scope p, List records in a scope, newest first.          Args:             scope: Optiona, Return a formatted tree of scopes (string).          Args:             path: Roo, join_scope_paths(), normalize_scope_path(), Utility functions for the unified memory system., Normalize a scope path by removing double slashes and ensuring proper format. (+5 more)

### Community 156 - "test_crew_scoped_hooks.py"
Cohesion: 0.06
Nodes (21): clear_hooks(), Tests for crew-scoped hooks within @CrewBase classes., Test that different crew instances have isolated hooks., Test that filtered crew-scoped hooks work correctly., Test that crew-scoped hooks are not registered twice., Clear global hooks before and after each test., Test that crew-scoped hooks have correct signature (self + context)., Test crew-scoped hooks with agent filters. (+13 more)

### Community 157 - "AnyClassMethod"
Cohesion: 0.10
Nodes (30): AnyClassMethod, ConfigDict, Any, add_const_to_oneof_variants(), add_key_in_dict_recursively(), _build_model_from_schema(), fix_discriminator_mappings(), _inline_top_level_ref() (+22 more)

### Community 158 - "analyze_query()"
Cohesion: 0.08
Nodes (22): analyze_query(), QueryAnalysis, Use the LLM to analyze a recall query.      On LLM failure, returns safe default, LLM output for analyzing a recall query., Any, BaseModel, RLM-inspired intelligent recall flow for memory retrieval.  Implements adaptive-, Analyze the query, embed distilled sub-queries, extract filters.          Short (+14 more)

### Community 160 - "BaseClient"
Cohesion: 0.08
Nodes (20): BaseClient, Any, CoreSchema, GetCoreSchemaHandler, Protocol, Unpack, Generate Pydantic core schema for BaseClient Protocol.          This allows the, Create a new collection/index in the vector database.          Keyword Args: (+12 more)

### Community 161 - "test_async_crew.py"
Cohesion: 0.06
Nodes (22): Tests for async crew execution., Test async crew kickoff with multiple tasks., Test that async kickoff handles exceptions properly., Test that async kickoff calls before_kickoff_callbacks., Test that async kickoff calls after_kickoff_callbacks., Tests for async crew kickoff_for_each methods., Test basic async kickoff_for_each., Test that async kickoff_for_each runs concurrently. (+14 more)

### Community 162 - "_conversation_start_router()"
Cohesion: 0.16
Nodes (31): _conversation_start_router(), _build_config_definition(), _build_conversational_definition(), _build_conversational_router_definition(), build_flow_definition(), _build_flow_definition_from_class(), _build_human_feedback_definition(), _build_method_definition() (+23 more)

### Community 163 - "ImportError"
Cohesion: 0.08
Nodes (20): ImportError, GoogleGenAIVertexEmbeddingFunction, Any, Documents, Embeddings, Unpack, Google Vertex AI embedding function implementation.  This module supports both t, Check if the model uses the legacy SDK. (+12 more)

### Community 164 - "._setup_agent_executor()"
Cohesion: 0.11
Nodes (14): Initialize the agent's tools handler and optional tool cache.          Tool-resu, Set the cache handler for the agent.          Args:             cache_handler: A, CacheHandler, Any, BaseModel, Cache handler for tool usage results., Handles caching of tool execution results.      Provides thread-safe in-memory c, Add a tool result to the cache.          Args:             tool: Name of the too (+6 more)

### Community 165 - "text_file_knowledge_source.py"
Cohesion: 0.08
Nodes (25): Path, Load and preprocess text file content., Add text file content to the knowledge source, chunk it, compute embeddings,, Add text file content asynchronously., Utility method to split text into chunks., A knowledge source that stores and queries text file content using embeddings., TextFileKnowledgeSource, mock_vector_db() (+17 more)

### Community 166 - "find_crew_json_file()"
Cohesion: 0.13
Nodes (14): find_crew_json_file(), find_json_project_file(), load_agent(), _looks_like_windows_absolute_path(), Return ``stem.jsonc`` or ``stem.json``, preferring JSONC., Find the JSON crew definition in a project root., Load an existing ``Agent`` from a ``.json`` / ``.jsonc`` definition file., Path (+6 more)

### Community 167 - "rw_lock.py"
Cohesion: 0.10
Nodes (22): Read-write lock for thread-safe concurrent access.  This module provides a reade, Read-write lock for managing concurrent read and exclusive write access.      Al, Initialize the read-write lock., Acquire a read lock, blocking if a writer holds the lock., Release a read lock and notify waiting writers if last reader., Context manager for acquiring a read lock.          Yields:             None, Acquire a write lock, blocking if any readers or writers are active., Release a write lock and notify all waiting threads. (+14 more)

### Community 168 - ".search()"
Cohesion: 0.09
Nodes (12): CodeExecutorInput, DictAnnotatedSearchTool, ExplicitSearchTool, InferredSearchTool, _make_explicit_decorator_tool(), _make_inferred_decorator_tool(), _make_root_decorator_tool(), BaseModel (+4 more)

### Community 169 - "BeforeToolCallHookCallable"
Cohesion: 0.09
Nodes (20): BeforeToolCallHookCallable, BeforeToolCallHookType, get_before_tool_call_hooks(), Register a global before_tool_call hook.      Global hooks are added to all tool, Get all registered global before_tool_call hooks.      Returns:         List of, register_before_tool_call_hook(), Detect and register crew-scoped hook methods.      Args:         instance: Crew, _register_crew_hooks() (+12 more)

### Community 170 - ".skill()"
Cohesion: 0.17
Nodes (17): Return a portable Markdown skill for authoring Flow declarations., contains_python_reference(), extract_discriminator(), FlowSkillReferenceExtractor, format_inline_example(), format_inline_value(), join_unique(), markdown_heading_anchor() (+9 more)

### Community 171 - "call_stop_override()"
Cohesion: 0.10
Nodes (14): call_stop_override(), Override the stop list for ``llm`` within the current call scope.      Only ``ll, _as_str(), extract_choices_finish_reason_and_id(), Any, Shared extractors for ``finish_reason`` + ``response_id`` across LLM providers., Extract ``(finish_reason, response_id)`` from a choices-shaped response.      Ha, mock_emit() (+6 more)

### Community 172 - "OpenAICompatibleCompletion"
Cohesion: 0.09
Nodes (17): OpenAICompatibleCompletion, OpenAI-compatible completion implementation.      This class provides support fo, Check if the provider supports function calling.          Delegates to the paren, Tests for OpenAICompatibleCompletion class., Test that unknown provider raises ValueError., Test that missing required API key raises ValueError., Test API key is read from environment variable., Test explicit API key overrides environment variable. (+9 more)

### Community 173 - "test_agent_a2a_kickoff.py"
Cohesion: 0.07
Nodes (17): Tests for Agent.kickoff() with A2A delegation using VCR cassettes., Test that agent handles multi-turn A2A conversations., Test that agent without A2A config works normally., Test that agent handles failed A2A connection gracefully., Test that agent.kickoff() works with list of messages., Tests for async Agent.kickoff_async() with A2A delegation., Create a research agent with A2A configuration., Tests for Agent.kickoff() with A2A delegation. (+9 more)

### Community 174 - "test_transport.py"
Cohesion: 0.08
Nodes (19): Request, Response, Tests for transport layer with interceptor integration., Test interceptor that tracks all calls., Initialize tracking lists., Test suite for transport integration scenarios., Test that multiple requests through same interceptor are tracked., Test that multiple async requests through same interceptor are tracked. (+11 more)

### Community 175 - "test_embedding_factory.py"
Cohesion: 0.07
Nodes (16): Tests for embedding function factory., Test building HuggingFace embedder., Test embedding factory functions., Test building Cohere embedder., Test building OpenAI embedder., Test building VoyageAI embedder., Test building WatsonX embedder., Test error handling for unknown provider. (+8 more)

### Community 176 - "llm_guardrail_events.py"
Cohesion: 0.09
Nodes (21): LLMGuardrailBaseEvent, LLMGuardrailStartedEvent, Any, Event emitted when a guardrail task starts      Attributes:         guardrail: T, HallucinationGuardrail, Any, Hallucination Guardrail Placeholder for CrewAI.  This is a no-op version of the, Placeholder for the HallucinationGuardrail feature.      Attributes:         con (+13 more)

### Community 177 - "ClientCallContext"
Cohesion: 0.08
Nodes (21): ClientCallContext, ClientCallInterceptor, ExtensionsMiddleware, AgentCard, AgentExtension, Any, A2A Protocol extension utilities.  This module provides utilities for working wi, Middleware to add X-A2A-Extensions header to requests.      This middleware adds (+13 more)

### Community 178 - "AgentEvaluationCompletedEvent"
Cohesion: 0.18
Nodes (8): AgentEvaluationCompletedEvent, AgentEvaluationFailedEvent, AgentEvaluationStartedEvent, AgentEvaluator, ExecutionState, Any, AgentEvaluationResult, TestAgentEvaluator

### Community 179 - "load_resources()"
Cohesion: 0.10
Nodes (19): load_resources(), Promote a skill to RESOURCES disclosure level.      Args:         skill: Skill t, load_skill_instructions(), load_skill_resources(), parse_skill_md(), Path, Promote a skill to INSTRUCTIONS disclosure level.      Reads the full SKILL.md b, Promote a skill to RESOURCES disclosure level.      Catalogs available resource (+11 more)

### Community 180 - "test_agent_reasoning.py"
Cohesion: 0.07
Nodes (27): Tests for planning/reasoning in agents., Test the planning_enabled property on Agent., Test agent with reasoning=True (backward compatibility)., Test agent with reasoning=True and max_reasoning_attempts (backward compatibilit, Test Agent.kickoff() with planning enabled generates a plan., Test Agent.kickoff() without planning skips plan generation., Test Agent.kickoff() with planning explicitly disabled via planning=False., Test Agent.kickoff() with a multi-step task that benefits from planning. (+19 more)

### Community 181 - "DoclingDocument"
Cohesion: 0.11
Nodes (17): DoclingDocument, DocumentConverter, _build_default_document_converter(), CrewDoclingSource, _DoclingModules, _import_docling(), Any, NamedTuple (+9 more)

### Community 182 - "content_type.py"
Cohesion: 0.11
Nodes (25): ContentTypeNegotiationError, _find_compatible_modes(), _get_effective_modes(), get_part_content_type(), _mime_types_compatible(), negotiate_content_types(), NegotiatedContentTypes, _normalize_mime_type() (+17 more)

### Community 183 - "base_tool_adapter.py"
Cohesion: 0.11
Nodes (20): BaseToolAdapter, ABC, Any, Base class for all tool adapters in CrewAI.      This abstract class defines the, Configure and convert tools for the specific implementation.          Args:, Return all converted tools., ConcreteToolAdapter, ConcreteToolAdapterWithoutRequiredMethods (+12 more)

### Community 184 - "stdio.py"
Cohesion: 0.09
Nodes (19): Any, BaseException, Self, Stdio transport for MCP servers running as local processes., Terminate the MCP server process and close connection., Async context manager entry., Async context manager exit., Stdio transport for connecting to local MCP servers.      This transport connect (+11 more)

### Community 185 - "_custom_tool_file()"
Cohesion: 0.13
Nodes (17): _custom_tool_file(), _find_tool_class(), _import_tool_class(), _instantiate_tool_import_ref(), JSONProjectError, ValueError, Resolve tool specs into tool instances or serialized BaseTool dicts.      String, Look up a tool class by name from the ``crewai_tools`` package. (+9 more)

### Community 186 - "utils.py"
Cohesion: 0.09
Nodes (22): clear_rag_config(), get_rag_client(), get_rag_config(), BaseModel, RagConfigType, RagContext, RAG client configuration utilities., Context holding RAG configuration and client instance. (+14 more)

### Community 188 - "Path"
Cohesion: 0.09
Nodes (15): Path, Test that FilePath raises for directories., Test content type detection from file content., Test keys() method for dict unpacking., Test File creation from path string., Test File creation from Path object., Test File supports ** unpacking syntax., Test File keys() method. (+7 more)

### Community 189 - "_build_data_part_v09()"
Cohesion: 0.09
Nodes (22): _build_data_part_v09(), Validate a v0.9 A2UI message and wrap it as a DataPart dict., A2UIEventV09, A2UIMessageV09, Union wrapper for v0.9 server-to-client message types.      Exactly one message, Enforce the spec's exactly-one-of constraint., Union wrapper for v0.9 client-to-server events., Enforce the spec's exactly-one-of constraint. (+14 more)

### Community 190 - "decorators.py"
Cohesion: 0.10
Nodes (19): after_llm_call(), after_tool_call(), before_llm_call(), before_tool_call(), _create_hook_decorator(), Any, Decorator to register a function as a before_llm_call hook.      Example:, Decorator to register a function as an after_llm_call hook.      Example: (+11 more)

### Community 191 - "excel_knowledge_source.py"
Cohesion: 0.11
Nodes (15): ExcelKnowledgeSource, Any, ModuleType, Path, Load and preprocess Excel file content from multiple sheets.          Each sheet, A knowledge source that stores and queries Excel file content using embeddings., Convert a path to a Path object., Dynamically import dependencies. (+7 more)

### Community 192 - "test_structured_planning.py"
Cohesion: 0.09
Nodes (18): create_research_tools(), Tests for structured planning with steps and todo generation.  These tests verif, Create research tools for testing structured planning., Integration tests for OpenAI structured planning with research workflow., Test that OpenAI generates structured plan steps for a research task., Integration tests for Anthropic structured planning with research workflow., Mock API key if not set., Test that Anthropic generates structured plan steps for a research task. (+10 more)

### Community 193 - "COMPONENTS"
Cohesion: 0.10
Nodes (16): COMPONENTS, Prompts, BaseModel, Constructs a prompt string from specified components.          Args:, Manages and generates prompts for a generic agent.      Notes:         - Need to, Tests for prompt generation to prevent thought leakage.  These tests verify that, Tests to verify prompts don't encourage thought leakage., Test that 'your job depends on it' is not in no-tools prompts. (+8 more)

### Community 194 - "KnowledgeStorageFactory"
Cohesion: 0.09
Nodes (17): KnowledgeStorageFactory, BaseKnowledgeStorage, ABC, Any, BaseModel, Search for documents in the knowledge base., Search for documents in the knowledge base asynchronously., Save documents to the knowledge base. (+9 more)

### Community 195 - "models.py"
Cohesion: 0.11
Nodes (24): A2UIResponse, BeginRendering, BoundValue, ComponentEntry, DataEntry, DataModelUpdate, DeleteSurface, MapEntry (+16 more)

### Community 196 - "trace_listener.py"
Cohesion: 0.08
Nodes (14): Trace collection listener for orchestrating trace collection., Re-exports of version utilities from ``crewai_core.version``.  Kept as a stable, Test for version management., Test _find_latest_non_yanked_version helper., Test that yanked versions are skipped., Test that the highest non-yanked version is returned., Test that None is returned when all versions are yanked., Test that pre-release versions are skipped. (+6 more)

### Community 197 - "create_default_evaluator()"
Cohesion: 0.16
Nodes (9): create_default_evaluator(), BaseEvaluator, MetricCategory, ParameterExtractionEvaluator, ToolInvocationEvaluator, ToolSelectionEvaluator, TestParameterExtractionEvaluator, TestToolInvocationEvaluator (+1 more)

### Community 198 - "crew_evaluator_handler.py"
Cohesion: 0.11
Nodes (10): CrewEvaluator, Any, BaseModel, Evaluates the performance of the agents in the crew based on the tasks they have, A class to evaluate the performance of the agents in the crew based on the tasks, Sets up the crew for evaluating., Sets the current iteration of the evaluation.          Args:             iterati, Prints the evaluation result of the crew in a table.         A Crew with 2 tasks (+2 more)

### Community 199 - "import_utils.py"
Cohesion: 0.12
Nodes (16): OptionalDependencyError, ModuleType, Import utilities for optional dependencies., Exception raised when an optional dependency is not installed., Import a module, optionally returning a specific attribute.      Args:         n, require(), Tests for import utilities., Test the require function. (+8 more)

### Community 200 - "args"
Cohesion: 0.11
Nodes (24): args, description, required, type, unevaluatedProperties, description, required, type (+16 more)

### Community 201 - ".create_status_content()"
Cohesion: 0.08
Nodes (12): Handle step observation failure event., Display guardrail evaluation started status.          Args:             guardrai, Display guardrail evaluation result.          Args:             success: Whether, Create standardized status content with consistent formatting., Handle crew completion/failure with panel display., Show task completion/failure panel., Show flow started panel., Show flow status panel. (+4 more)

### Community 202 - "ConversationState"
Cohesion: 0.12
Nodes (12): ConversationState, Return the current user message for conversational route selection.          Thi, Route the current turn to a listener label., Built-in conversation terminator., Append a user message, run one conversational turn, and return output., Run an interactive terminal chat loop for a conversational Flow.          ``chat, Append a final user-visible assistant message., Emit a compact transcript event for conversational trace views. (+4 more)

### Community 203 - "EvaluationScore"
Cohesion: 0.16
Nodes (7): EvaluationScore, Any, ReasoningEfficiencyEvaluator, SemanticQualityEvaluator, Any, TestReasoningEfficiencyEvaluator, TestSemanticQualityEvaluator

### Community 204 - "._init_client()"
Cohesion: 0.09
Nodes (19): Self, ChromaDBConfig, _default_embedding_function(), _default_settings(), ChromaDB configuration model., Create default ChromaDB settings.      Returns:         Settings with persistent, Create default ChromaDB embedding function.      Returns:         Default embedd, Configuration for ChromaDB client. (+11 more)

### Community 205 - "base.py"
Cohesion: 0.08
Nodes (19): BaseRagConfig, Base configuration class for RAG providers., Base class for RAG configuration with Pydantic serialization support., Creates a Qdrant client from configuration., Qdrant client implementation., QdrantConfig, Configuration for Qdrant client., create_client() (+11 more)

### Community 206 - "config.py"
Cohesion: 0.10
Nodes (21): _default_embedding_function(), _default_options(), Qdrant configuration model., Create default Qdrant client options.      Returns:         Default options with, Create default Qdrant embedding function.      Returns:         Default embeddin, CommonCreateFields, CreateCollectionParams, PreparedSearchParams (+13 more)

### Community 207 - "discover_skills()"
Cohesion: 0.17
Nodes (14): discover_skills(), Scan a directory for skill directories containing SKILL.md.      Loads each disc, load_skill_metadata(), Load a skill at METADATA disclosure level.      Parses SKILL.md frontmatter only, _create_skill_dir(), Path, Tests for skills/loader.py., Helper to create a skill directory with SKILL.md. (+6 more)

### Community 208 - "mcp_tool_wrapper.py"
Cohesion: 0.12
Nodes (13): MCPToolWrapper, Any, MCP Tool Wrapper for on-demand MCP server connections., Execute single operation attempt and return (result, error_message, should_retry, Execute tool with timeout wrapper., Execute the actual MCP tool call., Lightweight wrapper for MCP tools that connects on-demand., Initialize the MCP tool wrapper.          Args:             mcp_server_params: P (+5 more)

### Community 209 - "CalculatorTool"
Cohesion: 0.08
Nodes (13): CalculatorTool, Test OpenAI agent can use native tool calling., Test OpenAI agent kickoff with mocked LLM call., A calculator tool that performs mathematical calculations., Execute the calculation., Test Anthropic agent can use native tool calling., Test Anthropic agent kickoff with mocked LLM call., Test Gemini agent can use native tool calling. (+5 more)

### Community 210 - "ChatCompletions"
Cohesion: 0.13
Nodes (14): ChatCompletions, AzureCompletionParams, BaseModel, TypedDict, Finalize streaming response with usage tracking, tool execution, and events., Handle streaming chat completion., Handle streaming chat completion asynchronously., Azure ``ChatCompletions`` / ``StreamingChatCompletionsUpdate``         share the (+6 more)

### Community 211 - "._configure_format_from_task()"
Cohesion: 0.10
Nodes (18): Determine output format and schema from task requirements.          This is a he, convert_oneof_to_anyof(), ensure_all_properties_required(), generate_model_description(), JsonSchemaInfo, ModelDescription, TypedDict, Convert oneOf to anyOf for OpenAI compatibility.      OpenAI's Structured Output (+10 more)

### Community 212 - "base_agent.py"
Cohesion: 0.11
Nodes (16): ABC, Any, UUID4, Interpolate inputs into the agent description and backstory., _resolve_agent(), _serialize_crew_ref(), _serialize_executor_ref(), _serialize_llm_ref() (+8 more)

### Community 213 - "sse.py"
Cohesion: 0.10
Nodes (15): Any, BaseException, Self, Server-Sent Events (SSE) transport for MCP servers., Async context manager entry., SSE transport for connecting to remote MCP servers.      This transport connects, Async context manager exit., Initialize SSE transport.          Args:             url: Server URL (e.g., "htt (+7 more)

### Community 214 - "PreparedDocuments"
Cohesion: 0.15
Nodes (15): PreparedDocuments, NamedTuple, Prepared documents ready for ChromaDB insertion.      Attributes:         ids: L, _create_batch_slice(), Create a batch slice from prepared documents.      Args:         prepared: Prepa, Test suite for _create_batch_slice function., Test creating a normal batch slice., Test creating a batch slice that goes beyond the end. (+7 more)

### Community 215 - "test_google.py"
Cohesion: 0.09
Nodes (22): mock_google_api_key(), Mock GOOGLE_API_KEY for tests only if real keys are not set., Test that GeminiCompletion.call is actually invoked when running a crew, Test that GeminiCompletion.call is invoked with correct arguments, Test that GeminiCompletion.call is invoked multiple times for multiple tasks, Test that GeminiCompletion.call is invoked with tools when agent has tools, Test that Gemini properly handles tools that return non-dict values like floats., Test that Google Gemini streaming calls return proper token usage metrics. (+14 more)

### Community 216 - ".on_inbound()"
Cohesion: 0.11
Nodes (14): Response, Simple test interceptor implementation., Test suite for BaseInterceptor class., Initialize tracking lists., Test that interceptor can be instantiated., Test that on_outbound is called and tracks requests., Test that on_inbound is called and tracks responses., Test that interceptor tracks multiple outbound calls. (+6 more)

### Community 217 - "server_capabilities.json"
Cohesion: 0.09
Nodes (21): default, description, type, description, $id, type, v0.9, properties (+13 more)

### Community 218 - "base.py"
Cohesion: 0.13
Nodes (16): BaseInterceptor, ABC, Any, CoreSchema, GetCoreSchemaHandler, T, Base classes for LLM transport interceptors.  This module provides abstract base, Validate that the value is a BaseInterceptor instance.      Args:         value: (+8 more)

### Community 219 - "PlanStep"
Cohesion: 0.10
Nodes (14): PlanStep, A single step in the reasoning plan., Test PlanStep creation with only required fields., Test PlanStep creation with all fields., Test PlanStep with multiple dependencies., Test that step_number is required., Test that description is required., Test PlanStep can be serialized to dict. (+6 more)

### Community 220 - "Test when newer version is ava"
Cohesion: 0.09
Nodes (12): Test when newer version is available., Test when no newer version is available., Test when PyPI fetch fails., Test version checking utilities., Test getting current crewai version., Test cache file path generation., Test cache validation with fresh cache., Test cache validation with stale cache. (+4 more)

### Community 221 - "test_depends.py"
Cohesion: 0.13
Nodes (21): DependsTestEvent, Tests for FastAPI-style dependency injection in event handlers., Test async handler with dependency on sync handler., Test event for dependency tests., Test mix of sync and async handlers with dependencies., Test that handlers without dependencies can run concurrently., Test that handler with dependency runs after its dependency., Test that handlers without dependencies still work as before. (+13 more)

### Community 222 - "test_validation.py"
Cohesion: 0.16
Nodes (5): _make(), Tests for skills validation., Create a SkillFrontmatter with the given name., Tests for skill name constraints via SkillFrontmatter., TestSkillNameValidation

### Community 223 - "test_crew_thread_safety.py"
Cohesion: 0.12
Nodes (12): crew_factory(), TestCrewThreadSafety, LookupArgs, make_live_tool(), make_scripted_llm(), BaseModel, EPD-180: with no opt-in, both identical calls must really execute., Opting in via Crew(cache=True) restores the dedup behavior. (+4 more)

### Community 224 - "CodeExecutorTool"
Cohesion: 0.12
Nodes (12): CodeExecutorTool, Tests for args_schema validation in BaseTool.run()., Valid keyword arguments should pass schema validation and execute., All keyword arguments including optional ones should pass., Calling run() with no arguments should raise a clear ValueError,         not a c, Missing required kwargs should raise ValueError from schema validation., Kwargs not matching any schema field should trigger validation error         for, Positional-arg calls should bypass schema validation (backwards compat). (+4 more)

### Community 225 - "Tests for typed file wrapper c"
Cohesion: 0.09
Nodes (12): Tests for typed file wrapper classes., Test ImageFile creation from bytes., Test ImageFile creation from path string., Test TextFile.read_text method., Test PDFFile creation., Test AudioFile creation., Test VideoFile creation., Test that files support ** unpacking syntax. (+4 more)

### Community 226 - "Tests for the generic File cla"
Cohesion: 0.09
Nodes (12): Tests for the generic File class with auto-detection., Test File creation from text bytes auto-detects content type., Test File creation from PNG bytes auto-detects image type., Test File creation from PDF bytes auto-detects PDF type., Test File.read_text method., Test File dict unpacking with bytes (no filename)., Test File creation from stream., Test File has default mode of 'auto'. (+4 more)

### Community 227 - "Tests for the FUNCTION_SCHEMA "
Cohesion: 0.09
Nodes (12): Tests for the FUNCTION_SCHEMA used in structured planning., Test that FUNCTION_SCHEMA has the correct structure., Test that parameters have correct structure., Test that schema includes plan property., Test that schema includes steps array property., Test that steps items have correct structure., Test that step items have all required properties., Test that step required fields are correct. (+4 more)

### Community 228 - "D"
Cohesion: 0.12
Nodes (17): D, Embedding, PyEmbedding, EmbeddingFunction, maybe_cast_one_to_many(), normalize_embeddings(), Embeddings, T (+9 more)

### Community 229 - "MetadataFilter"
Cohesion: 0.12
Nodes (19): MetadataFilter, PointStruct, QueryResponse, _create_point_from_document(), _ensure_list_embedding(), _normalize_qdrant_score(), _prepare_search_params(), _process_search_results() (+11 more)

### Community 230 - "stream_context.py"
Cohesion: 0.16
Nodes (19): add_stream_sink(), Token, Scoped stream sinks for converting emitted events into public frames., Register a sink in the current context., Restore the stream sink context., reset_stream_sinks(), StreamSink, AsyncTestEvent (+11 more)

### Community 231 - ".create_lite_agent_branch()"
Cohesion: 0.10
Nodes (11): Any, Handle agent logs execution event., Print to console. Simplified to only handle panel-based output., Handle LLM tool usage started with panel display., Handle tool usage started event with panel display., Handle LLM stream chunk event - display streaming text in a panel.          Args, Show lite agent started panel., Show lite agent status panel. (+3 more)

### Community 232 - ".get_trace()"
Cohesion: 0.10
Nodes (11): Any, Handle a lite agent execution start event.          Args:             agent_info, Initialize a trace entry.          Args:             trace_key: The key to store, Handle an agent execution start event.          Args:             agent: The age, Handle an agent execution completion event.          Args:             agent: Th, Reset the current agent and task tracking state., Handle a lite agent execution completion event.          Args:             outpu, Record a tool usage event in the current trace.          Args:             tool_ (+3 more)

### Community 233 - "types.py"
Cohesion: 0.12
Nodes (19): CompletedMethodData, ExecutionMethodData, FlowData, FlowExecutionData, FlowMethodCallable, FlowMethodData, InputHistoryEntry, args (+11 more)

### Community 234 - "base_file_knowledge_source.py"
Cohesion: 0.14
Nodes (12): BaseFileKnowledgeSource, ABC, Any, Path, Base class for knowledge sources that load content from files., Validate that at least one of file_path or file_paths is provided., Post-initialization method to load content., Load and preprocess file content. Should be overridden by subclasses. Assume tha (+4 more)

### Community 235 - "EdgeType"
Cohesion: 0.12
Nodes (13): EdgeType, _build_event_type_map(), Any, Directed record of execution events.  Stores events as nodes with typed edges fo, Add an event to the record and wire its edges.          Args:             event:, Look up a node by event ID.          Args:             event_id: The event's uni, Return all descendant nodes, children recursively.          Args:             ev, Return all root nodes — events with no parent.          Returns:             Lis (+5 more)

### Community 236 - "content_processor.py"
Cohesion: 0.13
Nodes (16): ContentProcessorProvider, get_processor(), NoOpContentProcessor, process_content(), Any, Protocol, Content processor provider for extensible content processing., Process content before use.          Args:             content: The content to p (+8 more)

### Community 237 - "._add_file_tools()"
Cohesion: 0.12
Nodes (10): Any, UUID4, Add file reading tool when input files are available.          Args:, Replay the crew execution from a specific task., Creates a deep copy of the Crew instance.          Returns:             Crew: A, Interpolates the inputs in the tasks and agents., Test and evaluate the Crew with the given inputs for n iterations.          Uses, Prevent manual setting of the 'id' field by users. (+2 more)

### Community 238 - "transport.py"
Cohesion: 0.16
Nodes (15): AsyncHTTPTransport, HTTPTransport, HTTPTransportKwargs, Request, Response, TypedDict, Unpack, HTTP transport implementations for LLM request/response interception.  This modu (+7 more)

### Community 239 - "._ahandle_completion()"
Cohesion: 0.15
Nodes (8): Any, Handle non-streaming chat completion asynchronously., Get the last reasoning items from Responses API auto-chain reasoning., Eagerly build clients when credentials are available, otherwise         defer so, Return an Azure credential, preferring the API key when set.          Without an, Extend base config with Azure-specific fields., Handle completion-specific errors including context length checks.          Args, Handle non-streaming chat completion.

### Community 240 - "Serialize a single guardrail v"
Cohesion: 0.18
Nodes (19): Serialize a single guardrail value for JSON checkpointing.      String descripti, Serialize a guardrails value (single or sequence) for JSON checkpointing.      D, serialize_guardrail_for_json(), serialize_guardrails_for_json(), _example_guardrail(), Tests for JSON serialization of guardrail fields on Task, Agent, and LiteAgent., Serialized guardrails must round-trip — None entries would fail validation., test_agent_model_dump_json_with_callable_guardrail() (+11 more)

### Community 241 - "test_decorators.py"
Cohesion: 0.10
Nodes (13): clear_hooks(), Tests for decorator-based hook registration., Clear global hooks before and after each test., Test that decorators set proper attributes on functions., Test that decorator sets is_before_llm_call_hook attribute., Test that decorator with filters sets filter attributes., Test LLM hook decorators., Test that @before_llm_call decorator registers the hook. (+5 more)

### Community 242 - "test_litellm_async.py"
Cohesion: 0.10
Nodes (19): Tests for LiteLLM fallback async completion functionality., Test async call with multiple parameters., Test basic async call with LiteLLM fallback., Test async streaming call with LiteLLM fallback., Test async streaming call with multiple parameters., Test async call with temperature parameter., Test async call with max_tokens parameter., Test async call with system message. (+11 more)

### Community 243 - "test_openai_async.py"
Cohesion: 0.10
Nodes (19): Tests for OpenAI async completion functionality., Test async call with response_format set to None., Test async call with JSON response format., Test basic async call with OpenAI., Test async call with multiple parameters., Test async call with temperature parameter., Test async call with max_tokens parameter., Test async call with system message. (+11 more)

### Community 244 - "test_amp_mcp.py"
Cohesion: 0.10
Nodes (6): agent(), Tests for AMP MCP config fetching and tool resolution., notion#get-page must match the tool whose sanitized name is get_page., resolver(), TestFetchAmpMCPConfigs, TestGetMCPToolsAmpIntegration

### Community 245 - "Tests for streaming cancellati"
Cohesion: 0.10
Nodes (11): Tests for streaming cancellation and resource cleanup., Test that aclose() stops iteration and marks as cancelled., Test that calling aclose() multiple times is safe., Test using streaming output as async context manager., Test context manager cleans up on early exit., Test that close() stops sync streaming and marks as cancelled., Test that calling close() multiple times is safe., Test that FlowStreamingOutput aclose() is no-op after normal completion. (+3 more)

### Community 246 - "Extension"
Cohesion: 0.14
Nodes (16): Extension, calculate_execution_paths(), Calculate number of possible execution paths through the flow.      Args:, calculate_node_positions(), CSSExtension, JSExtension, Interactive HTML renderer for Flow structure visualization., Jinja2 extension for rendering CSS link tags.      Provides {% css 'path/to/file (+8 more)

### Community 247 - "ModelWrapValidatorHandler"
Cohesion: 0.16
Nodes (15): ModelWrapValidatorHandler, _backfill_discriminators(), _backfill_memory_kind(), _backfill_source_type(), _backfill_sources_on(), _migrate(), Any, Unified runtime state for crewAI.  ``RuntimeState`` is a ``RootModel`` whose ``m (+7 more)

### Community 248 - "surfaces"
Cohesion: 0.11
Nodes (18): surfaces, additionalProperties, description, type, description, $id, version, properties (+10 more)

### Community 249 - "extract_a2ui_json_objects()"
Cohesion: 0.12
Nodes (15): extract_a2ui_json_objects(), Any, Extract JSON objects containing A2UI keys from text.      Uses ``json.JSONDecode, A2UIServerExtension, _build_data_part(), Any, A2UI server extension for the A2A protocol., Validate a v0.8 A2UI message and wrap it as a DataPart dict. (+7 more)

### Community 250 - "._training_handler()"
Cohesion: 0.12
Nodes (6): Handle training data for the agent task prompt to improve output on Training., Use trained data for the agent task prompt to improve output., Sets up the crew for training., CrewTrainingHandler, Clear the training data by removing the file or resetting its contents., InternalCrewTrainingHandler

### Community 251 - ".create_crew_memory()"
Cohesion: 0.16
Nodes (6): Initialize unified memory, respecting crew embedder config.          When memory, Return the LLM auto-created memory should use for analysis., Sanitize a name for use in hierarchical scope paths.      Converts to lowercase,, sanitize_scope_name(), Tests for sanitize_scope_name utility., TestSanitizeScopeName

### Community 252 - "get_next_emission_sequence()"
Cohesion: 0.14
Nodes (14): get_next_emission_sequence(), _get_or_create_counter(), Get the emission counter for the current context, creating if needed., Get the next emission sequence number.      Returns:         The next sequence n, Register source, set scope/sequence metadata, and record the event.          Thi, get_last_event_id(), Get the ID of the last emitted event for linear chain tracking.      Returns:, Set the ID of the last emitted event.      Args:         event_id: The event_id (+6 more)

### Community 253 - "get_triggering_event_id()"
Cohesion: 0.19
Nodes (11): get_triggering_event_id(), Get the ID of the event that triggered the current execution.      Returns:, Set the ID of the triggering event for causal chain tracking.      Args:, Context manager to set the triggering event ID for causal chain tracking.      A, set_triggering_event_id(), triggered_by_scope(), Tests for event context management., Tests for causal chain event ID tracking. (+3 more)

### Community 254 - "lite_agent_output.py"
Cohesion: 0.12
Nodes (8): Output class for LiteAgent execution results., Type aliases for guardrails., _FixedUsageLLM, Single accessor written against the CrewOutput shape., Single accessor written against the LiteAgentOutput shape., Offline BaseLLM that records fixed usage (100/10 tokens) per call., Mirror of the EPD-178 clean-room repro, offline via a fake BaseLLM., TestUsageShapeEndToEnd

### Community 255 - "http.py"
Cohesion: 0.13
Nodes (12): HTTPTransport, Any, BaseException, Self, HTTP and Streamable HTTP transport for MCP servers., Close HTTP connection., Async context manager entry., Async context manager exit. (+4 more)

### Community 256 - "parser.py"
Cohesion: 0.18
Nodes (9): parse_frontmatter(), Any, ValueError, SKILL.md file parsing for the Agent Skills standard.  Parses YAML frontmatter an, Error raised when SKILL.md parsing fails., Split SKILL.md content into frontmatter dict and body text.      Args:         c, SkillParseError, Tests for parse_frontmatter. (+1 more)

### Community 257 - "_common_strict_pipeline()"
Cohesion: 0.15
Nodes (12): _common_strict_pipeline(), Remove format annotations that OpenAI strict mode doesn't support.      OpenAI o, Recursively delete a fixed set of keys from a schema., Shared strict sanitization: inline refs, close objects, require all properties., Sanitize a JSON schema for OpenAI strict function calling., Sanitize a JSON schema for Anthropic strict tool use., sanitize_tool_params_for_anthropic_strict(), sanitize_tool_params_for_openai_strict() (+4 more)

### Community 259 - "test_base_interceptor.py"
Cohesion: 0.13
Nodes (12): ModifyingInterceptor, Request, Tests for base interceptor functionality., Track outbound calls.          Args:             message: The outbound request., Test suite for interceptor that modifies messages., Test that interceptor can add headers to outbound requests., Test that interceptor can add headers to inbound responses., Test that interceptor preserves existing headers. (+4 more)

### Community 260 - "AgentCardSignature"
Cohesion: 0.17
Nodes (17): AgentCardSignature, SigningAlgorithm, _base64url_encode(), get_key_id_from_signature(), _normalize_private_key(), AgentCard, SecretStr, AgentCard JWS signing utilities.  This module provides functions for signing and (+9 more)

### Community 261 - "ChatCompletionsToolDefinition"
Cohesion: 0.13
Nodes (11): ChatCompletionsToolDefinition, call_stream_override(), Override streaming for ``llm`` within the current call scope., Exception, Check if the model supports stop words.          Models using the Responses API, Handle API errors with appropriate logging and events.          Args:, Call Azure AI Inference API.          Args:             messages: Input messages, Call Azure AI Inference API asynchronously.          Args:             messages: (+3 more)

### Community 262 - "Content"
Cohesion: 0.20
Nodes (10): Content, BaseModel, Finalize streaming response with usage tracking, function execution, and events., Handle streaming content generation., Convert contents to dict format., Call Google Gemini generate content API.          Args:             messages: In, Format messages for Gemini API.          Gemini has specific requirements:, Validate content against response model and emit completion event.          Args (+2 more)

### Community 263 - "Settings"
Cohesion: 0.18
Nodes (3): Settings, Re-exports of shared settings from ``crewai_core.settings``.  Existing imports f, TestSettings

### Community 264 - "properties"
Cohesion: 0.15
Nodes (18): properties, additionalProperties, anyOf, type, unevaluatedProperties, const, properties, properties (+10 more)

### Community 265 - "description"
Cohesion: 0.11
Nodes (18): description, oneOf, oneOf, description, type, $defs, Action, ChildList (+10 more)

### Community 266 - "_serialize_input_provider()"
Cohesion: 0.16
Nodes (12): _serialize_input_provider(), _dotted_path_to_instance(), _instance_to_dotted_path(), Any, Serializable callback type for Pydantic models.  Provides a ``SerializableCallab, Serialize an instance to a dotted path naming its class., Resolve a dotted path to a class and instantiate it with no args.      If *value, Return True only if ``CREWAI_DESERIALIZE_CALLBACKS`` is an explicit yes. (+4 more)

### Community 267 - "pdf_knowledge_source.py"
Cohesion: 0.13
Nodes (12): PDFKnowledgeSource, ModuleType, Path, Load and preprocess PDF file content., Dynamically import pdfplumber., Add PDF file content to the knowledge source, chunk it, compute embeddings,, Add PDF file content asynchronously., Utility method to split text into chunks. (+4 more)

### Community 268 - "completion.py"
Cohesion: 0.13
Nodes (11): ProviderConfig, Any, OpenAI-compatible providers implementation.  This module provides a thin subclas, Resolve the API key from explicit value, env var, or default.          Args:, Resolve the base URL from explicit value, env var, or default.          Args:, Merge user headers with provider default headers.          Args:             hea, Configuration for an OpenAI-compatible provider.      Attributes:         base_u, Tests for ProviderConfig dataclass. (+3 more)

### Community 269 - "base.py"
Cohesion: 0.12
Nodes (14): _MissingProvider, Base classes for missing provider configurations., Base class for missing provider configurations.      Raises RuntimeError when in, Raises error indicating the provider is not installed., MissingChromaDBConfig, MissingQdrantConfig, Provider-specific missing configuration classes., Placeholder for missing ChromaDB configuration. (+6 more)

### Community 270 - "loader.py"
Cohesion: 0.17
Nodes (9): load_skill(), load_skills(), Path, Filesystem discovery and progressive loading for Agent Skills.  Provides functio, Load one skill input into Skill objects.      Accepts a pre-loaded Skill object,, Load skill inputs into de-duplicated Skill objects.      Preserves first-seen or, MonkeyPatch, Tests for load_skill. (+1 more)

### Community 271 - "core.py"
Cohesion: 0.12
Nodes (11): BaseProvider, ABC, BaseModel, Base class for state providers., Read a snapshot asynchronously.          Args:             location: The identif, Base class for persisting and restoring runtime state checkpoints.      Implemen, Persist a snapshot synchronously.          Args:             data: The serialize, Persist a snapshot asynchronously.          Args:             data: The serializ (+3 more)

### Community 272 - "memory_tools.py"
Cohesion: 0.14
Nodes (15): create_memory_tools(), Any, BaseModel, Memory tools that give agents active recall and remember capabilities., Create Recall and Remember tools for the given memory instance.      When memory, Schema for the recall memory tool., Tool that lets an agent search memory for one or more queries at once., Search memory for relevant information.          Args:             queries: One (+7 more)

### Community 273 - "Import and return the class/fu"
Cohesion: 0.15
Nodes (11): Import and return the class/function from the import path.      Args:         v:, validate_import_path(), Test validation with non-existent module., Test validation when attribute doesn't exist in module., Test validation with nested module path., Test that package name is correctly extracted for error message., Test the validate_import_path function., Test successful import of a class. (+3 more)

### Community 275 - "AsyncInterceptor"
Cohesion: 0.15
Nodes (11): AsyncInterceptor, Handle async outbound.          Args:             message: The outbound request., Handle async inbound.          Args:             message: The inbound response., Test suite for async interceptor functionality., Test that sync methods still work on async interceptor., Test async outbound hook., Test async inbound hook., Test that default async methods raise NotImplementedError. (+3 more)

### Community 276 - "Tests for LLM factory integrat"
Cohesion: 0.11
Nodes (10): Tests for LLM factory integration with OpenAI-compatible providers., Test LLM factory creates OpenAICompatibleCompletion for DeepSeek., Test LLM factory creates OpenAICompatibleCompletion for Ollama., Test LLM factory creates OpenAICompatibleCompletion for OpenRouter., Test LLM factory creates OpenAICompatibleCompletion for hosted_vllm., Test LLM factory creates OpenAICompatibleCompletion for Cerebras., Test LLM factory creates OpenAICompatibleCompletion for Dashscope., Test LLM with explicit provider parameter. (+2 more)

### Community 277 - "MonkeyPatch"
Cohesion: 0.12
Nodes (18): MonkeyPatch, Path, test_agent_action_renders_text_custom_expression_input(), test_agent_action_repository_fetch_does_not_block_event_loop(), test_agent_action_runs_inline_yaml_definition(), test_agent_action_runs_inside_each(), test_agent_action_runs_repository_yaml_definition(), test_crew_action_from_declaration_rejects_paths_outside_flow_file() (+10 more)

### Community 278 - "test_streaming_integration.py"
Cohesion: 0.11
Nodes (12): Integration tests for streaming with real LLM interactions using cassettes., Test async streaming example from documentation., Create a researcher agent for testing., Test kickoff_for_each streaming example from documentation., Create a simple research task., Integration tests for crew streaming that match documentation examples., Test basic streaming example from documentation., Test streaming with chunk context example from documentation. (+4 more)

### Community 279 - "RagClientFactory"
Cohesion: 0.13
Nodes (15): RagClientFactory, ChromaFactoryModule, Protocol, QdrantFactoryModule, Protocol definitions for RAG factory modules., Protocol for ChromaDB factory module., Protocol for Qdrant factory module., create_client() (+7 more)

### Community 280 - "base_converter_adapter.py"
Cohesion: 0.14
Nodes (10): BaseConverterAdapter, ABC, Base converter adapter for structured output conversion., Extract valid JSON from text that may contain markdown or other formatting., Abstract base class for converter adapters in CrewAI.      Defines the common in, Initialize the converter adapter.          Args:             agent_adapter: The, Configure agents to return structured output.          Must support both JSON an, Enhance the system prompt with structured output instructions.          Args: (+2 more)

### Community 281 - "SkillModel"
Cohesion: 0.21
Nodes (9): SkillModel, Resolve crew-level skill paths once so agents don't repeat the work., _resolve_crew_skills(), _create_skill_dir(), Path, Integration tests for the skills system., Helper to create a skill directory with SKILL.md., End-to-end tests for discover + activate workflow. (+1 more)

### Community 282 - "cache.py"
Cohesion: 0.18
Nodes (11): Path, TarFile, Cache manager for registry-downloaded skills.  Manages ~/.crewai/skills/{org}/{n, Remove a cached skill.          Returns:             True if the cache entry exi, Path-traversal-safe extraction for Python versions without tar filters.      Val, Path-traversal-safe ZIP extraction., Return the cached skill directory path if it exists, else None., Unpack an archive into the cache and write metadata.          Uses tarfile with (+3 more)

### Community 283 - "FlowMethod"
Cohesion: 0.15
Nodes (12): FlowMethod, Any, args, kwargs, P, R, Self, Get the original unwrapped method.          Returns:             The original me (+4 more)

### Community 284 - "Normalize an LLM call's raw us"
Cohesion: 0.15
Nodes (12): Normalize an LLM call's raw usage dict into ``UsageMetrics``.      Thin wrapper, _usage_dict_to_metrics(), _coerce_int(), _first_int(), Any, Self, Usage metrics tracking for CrewAI execution.  This module provides models for tr, Normalize a provider's raw usage dict into a ``UsageMetrics``.          Accepts (+4 more)

### Community 285 - "json_knowledge_source.py"
Cohesion: 0.14
Nodes (11): JSONKnowledgeSource, Any, Path, Load and preprocess JSON file content., Recursively convert JSON data to a text representation., Add JSON file content to the knowledge source, chunk it, compute embeddings,, Add JSON file content asynchronously., Utility method to split text into chunks. (+3 more)

### Community 286 - "json_provider.py"
Cohesion: 0.13
Nodes (11): _build_path(), Path, Filesystem JSON state provider., Extract the checkpoint ID from a file path.          The filename format is ``{t, Read a JSON checkpoint file.          Args:             location: Filesystem pat, Build a timestamped checkpoint file path under a branch subdirectory.      Filen, Validate that a branch name doesn't escape the base directory.      Raises:, Write a JSON checkpoint file.          Args:             data: The serialized JS (+3 more)

### Community 287 - ".ensure_guardrail_is_callable("
Cohesion: 0.17
Nodes (11): _is_coroutine(), LLMGuardrail, LLMGuardrailResult, Any, BaseModel, TypeIs, Check if obj is a coroutine for type narrowing., Run a coroutine synchronously, handling an already-running event loop. (+3 more)

### Community 288 - "T"
Cohesion: 0.12
Nodes (9): T, Check if the stream iterator was fully consumed., Return collected frames., Get the final result after streaming completes.          Returns:             Th, Base stream session with ordered frame iteration and result access., Return the final result after stream exhaustion or completion., Check if the stream has completed., Check if the stream was cancelled. (+1 more)

### Community 289 - "import_and_validate_definition"
Cohesion: 0.15
Nodes (11): import_and_validate_definition(), Any, Pydantic-compatible function to import a class/function from a string path., Test the import_and_validate_definition function., Test successful import through Pydantic adapter., Test importing a function instead of a class., Test that invalid paths raise ValueError., Test error handling for missing modules. (+3 more)

### Community 290 - "test_event_replay.py"
Cohesion: 0.15
Nodes (11): _make_started(), Tests for event bus replay dispatch and is_replaying flag., A flow resumed from a checkpoint replays MethodExecution* events for     complet, Build a MethodExecutionStartedEvent with explicit ids/sequence., replay() must not overwrite event_id, parent_event_id, or emission_sequence., is_replaying() must be True inside handlers dispatched via replay()., CheckpointListener must early-return during replay., TestCheckpointListenerOptsOut (+3 more)

### Community 291 - "test_storage_factory.py"
Cohesion: 0.15
Nodes (11): _FakeKnowledgeStorage, Any, Tests for the pluggable knowledge storage factory seam.  We verify our own logic, Minimal stand-in implementing the abstract interface., Reset the factory around each test without clobbering preexisting state., reset_factory(), test_explicit_storage_bypasses_factory(), test_factory_receives_embedder_and_collection_name() (+3 more)

### Community 292 - "test_flow_crew_span_integratio"
Cohesion: 0.15
Nodes (16): create_mock_llm(), enable_telemetry_for_tests(), BaseModel, Test that crew execution spans work correctly when crews run inside flows.  Note, Test that crew._execution_span is None when share_crew=False in flow.      Verif, Test that multiple crews in a flow each get proper execution spans.      This en, Simple state for flow testing., Test that crew execution spans work in async flow methods.      Verifies that cr (+8 more)

### Community 293 - "test_flow_human_input_integrat"
Cohesion: 0.12
Nodes (9): Test human input in training mode., Test that ConsoleFormatter pause/resume methods exist and are callable., Non-empty input should be displayed as feedback to process., Test that human input pauses Flow status updates., Test multiple rounds of human input with Flow status management., Test pause/resume methods handle case when no Live session exists., Test integration between Flow execution and human input functionality., Test that resume is called even if exception occurs during human input. (+1 more)

### Community 294 - "createSurface"
Cohesion: 0.14
Nodes (16): createSurface, updateComponents, additionalProperties, properties, required, type, $defs, CreateSurfaceMessage (+8 more)

### Community 295 - "basic_catalog.json"
Cohesion: 0.12
Nodes (15): discriminator, oneOf, oneOf, catalogId, $defs, anyComponent, anyFunction, theme (+7 more)

### Community 296 - "._setup_graph()"
Cohesion: 0.16
Nodes (12): Set up the LangGraph workflow graph.          Initializes the memory saver and c, LangGraphCheckPointMemoryModule, LangGraphMemorySaver, LangGraphPrebuiltModule, Any, Protocol, Type protocols for LangGraph modules., Initialize the memory saver. (+4 more)

### Community 297 - ".check_config()"
Cohesion: 0.12
Nodes (8): Self, Validates that the language model is set when using hierarchical process., Validates that the crew is properly configured with agents and tasks., Validates that the crew ends with at most one asynchronous task., Validates that if a task is set to be executed asynchronously,         it cannot, Validates that a task's context does not include future tasks., Initializes agents and tasks from the provided config., Creates a task instance from its configuration.          Args:             task_

### Community 298 - "conversational_mixin.py"
Cohesion: 0.12
Nodes (10): _clear_or_listeners(), _collapse_to_outcome(), _copy_and_serialize_state(), kickoff(), method_outputs(), Conversational graph + helpers as an experimental Flow extension.  The conversat, Return whether this turn can be answered from message history., Map user text to one of the given outcomes using an LLM. (+2 more)

### Community 299 - "filters.py"
Cohesion: 0.16
Nodes (13): create_dynamic_tool_filter(), create_static_tool_filter(), Any, BaseModel, Tool filtering support for MCP servers.  This module provides utilities for filt, Create a dynamic tool filter function.      This function wraps a dynamic filter, Context for dynamic tool filtering.      This context is passed to dynamic tool, Static tool filter with allow/block lists.      This filter provides simple allo (+5 more)

### Community 300 - ".uuid_str()"
Cohesion: 0.20
Nodes (14): Get the string representation of the UUID for this fingerprint., add_agent_fingerprint_to_span(), add_crew_and_task_attributes(), add_crew_attributes(), add_task_attributes(), close_span(), Any, Span (+6 more)

### Community 301 - "_is_non_roundtrippable()"
Cohesion: 0.19
Nodes (6): _is_non_roundtrippable(), Return ``True`` if *fn* cannot survive a serialize/deserialize round-trip., _CallableInstance, _HasMethod, Callable class instance — non-roundtrippable., TestIsNonRoundtrippable

### Community 302 - "internal_instructor.py"
Cohesion: 0.13
Nodes (10): _is_valid_llm(), Any, T, TypeGuard, Extract provider from LLM model name.          Returns:             Provider nam, Convert the structured output to JSON format.          Returns:             JSON, Generate structured output using the specified Pydantic model.          Returns:, Type guard to ensure LLM is valid and not None.      Args:         llm: The LLM (+2 more)

### Community 303 - "_FixedUsageLLM"
Cohesion: 0.18
Nodes (5): _FixedUsageLLM, Offline BaseLLM that records fixed usage (100/10 tokens) per call., Regression tests for EPD-177: kickoff results used to expose the LLM     instanc, A guardrail retry re-invokes the LLM within the same kickoff, so         the res, TestKickoffUsageMetricsArePerCall

### Community 304 - "test_azure_async.py"
Cohesion: 0.12
Nodes (15): Tests for Azure async completion functionality., Test async call with conversation history., Test basic async non-streaming call., Test making multiple async calls in sequence., Test async call with temperature parameter., Test async call with max_tokens parameter., Test async call with system message., Test async call with multiple parameters. (+7 more)

### Community 305 - "test_bedrock_async.py"
Cohesion: 0.12
Nodes (15): Tests for Bedrock async completion functionality.  Note: These tests are skipped, Test async call with multiple parameters., Test basic async call with Bedrock., Test async call with temperature parameter., Test async call with max_tokens parameter., Test async call with system message., Test async call with conversation history., Test making multiple async calls in sequence. (+7 more)

### Community 306 - "test_google_async.py"
Cohesion: 0.12
Nodes (15): Tests for Google (Gemini) async completion functionality., Test async call with multiple parameters., Test basic async call with Gemini., Test async call with temperature parameter., Test async call with max_tokens parameter., Test async call with system message., Test async call with conversation history., Test making multiple async calls in sequence. (+7 more)

### Community 307 - "Tests for the OPENAI_COMPATIBL"
Cohesion: 0.12
Nodes (9): Tests for the OPENAI_COMPATIBLE_PROVIDERS registry., Test OpenRouter provider configuration., Test DeepSeek provider configuration., Test Ollama provider configuration., Test ollama_chat is configured same as ollama., Test hosted_vllm provider configuration., Test Cerebras provider configuration., Test Dashscope provider configuration. (+1 more)

### Community 308 - "test_google_vertex_memory_inte"
Cohesion: 0.13
Nodes (15): _fake_embedder(), google_vertex_embedder_config(), Integration tests for Google Vertex embeddings with Crew memory.  These tests ma, Test Crew memory with Google Vertex using project_id authentication., Set up environment for Vertex AI tests.      Sets GOOGLE_GENAI_USE_VERTEXAI=true, Fixture providing Google Vertex embedder configuration., Fixture providing a simple test agent., Fixture providing a simple test task. (+7 more)

### Community 309 - "AsyncCodeExecutorTool"
Cohesion: 0.17
Nodes (9): AsyncCodeExecutorTool, Tests for args_schema validation in BaseTool.arun()., Valid keyword arguments should pass schema validation in arun., Calling arun() with no arguments should raise a clear ValueError (GH-4611)., Missing required kwargs should raise ValueError in arun., Kwargs not matching schema fields should trigger validation error in arun., Extra kwargs not in the schema should be stripped in arun., Usage count should NOT increment when arun validation fails. (+1 more)

### Community 310 - "A2AClientConfigTypes"
Cohesion: 0.18
Nodes (13): A2AClientConfigTypes, A2AConfigTypes, create_agent_response_model(), extract_a2a_agent_ids_from_config(), get_a2a_agents_and_response_model(), BaseModel, Response model utilities for A2A agent interactions., Create a dynamic AgentResponse model with Literal types for agent IDs.      Args (+5 more)

### Community 311 - "AgentInterface"
Cohesion: 0.17
Nodes (13): AgentInterface, _get_server_interfaces(), negotiate_transport(), NegotiatedTransport, AgentCard, Exception, Transport negotiation utilities for A2A protocol.  This module provides function, Negotiate the transport protocol between client and server.      Compares the cl (+5 more)

### Community 312 - ".validate_and_set_attributes()"
Cohesion: 0.14
Nodes (8): BaseModel, Self, Controls request rate limiting for API calls., Manages requests per minute limiting., Resets the RPM counter and starts the timer if max_rpm is set.          Returns:, Checks if a new request can be made based on the RPM limit.          Returns:, Stops the RPM counter and cancels any active timers., RPMController

### Community 313 - "Any"
Cohesion: 0.13
Nodes (9): Any, Parse tool args from the parser output into a dict payload for events., Parse a VISION_IMAGE sentinel into (media_type, base64_data), or None., Build an observation message, converting vision sentinels to image blocks., Execute step using native function calling with a multi-turn loop.          Iter, Execute a batch of native tool calls and return their results.          Returns, Check if a response is a list of tool calls., is_tool_call_list() (+1 more)

### Community 314 - "base_evaluator.py"
Cohesion: 0.21
Nodes (6): AgentAggregatedEvaluationResult, AggregationStrategy, BaseModel, Enum, EvaluationDisplayFormatter, Any

### Community 315 - "goal_metrics.py"
Cohesion: 0.20
Nodes (3): GoalAlignmentEvaluator, BaseEvaluationMetricsTest, TestGoalAlignmentEvaluator

### Community 316 - "Manages the global skill cache"
Cohesion: 0.34
Nodes (6): Manages the global skill cache at ~/.crewai/skills/., SkillCacheManager, _make_tar_gz(), Path, Build an in-memory .tar.gz containing the given filename → content mapping., TestSkillCacheManager

### Community 317 - "crew_loader.py"
Cohesion: 0.22
Nodes (11): _crew_project_from_definition(), load_crew_and_kickoff(), load_crew_from_definition(), _load_crew_project(), Any, Path, Load crew definitions from JSON/JSONC files and produce Crew instances., Convenience function: load a crew and immediately kick it off. (+3 more)

### Community 318 - "crew_context.py"
Cohesion: 0.20
Nodes (12): get_crew_context(), Context management utilities for tracking crew and task execution context using, Get the current crew context from OpenTelemetry baggage.      Returns:         C, CrewContext, BaseModel, Models for crew-related data structures., Model representing crew context information.      Attributes:         id: Unique, test_baggage_exception_handling() (+4 more)

### Community 319 - "serialization.py"
Cohesion: 0.17
Nodes (14): Any, Serializable, Serializes an object into a JSON string.      Args:         obj: Object to seria, Converts a Python object into a JSON-compatible representation.      Supports pr, to_serializable(), _to_serializable_key(), to_string(), Test max depth handling with a deeply nested structure (+6 more)

### Community 322 - "test_callback.py"
Cohesion: 0.21
Nodes (6): _Model, module_level_function(), BaseModel, Tests for crewai.types.callback — SerializableCallable round-tripping., Plain module-level function that should round-trip., TestSerializableCallableRoundTrip

### Community 323 - "test_tool_usage_limit.py"
Cohesion: 0.13
Nodes (14): Test that ToolUsage class correctly enforces usage limits., Test that tools without usage limits work normally., Test usage limit with @tool decorator., Test that tools have unlimited usage by default., Test that negative usage limits raise ValueError., Test that reset_usage_count method works correctly., Test that tools respect usage limits., test_default_unlimited_usage() (+6 more)

### Community 324 - "A2AError"
Cohesion: 0.14
Nodes (13): A2AError, AuthenticatedExtendedCardNotConfiguredError, InternalError, InvalidAgentResponseError, InvalidRequestError, JSONParseError, Exception, Base exception for A2A protocol errors.      Attributes:         code: The A2A/J (+5 more)

### Community 325 - "$ref"
Cohesion: 0.15
Nodes (14): $ref, properties, description, type, additionalProperties, description, type, catalogId (+6 more)

### Community 326 - "base_output_converter.py"
Cohesion: 0.16
Nodes (11): OutputConverter, ABC, Any, BaseModel, Base output converter for transforming text into structured formats., Abstract base class for converting text to structured formats.      Uses languag, Convert text to a Pydantic model instance.          Args:             current_at, Convert text to a JSON dictionary.          Args:             current_attempt: C (+3 more)

### Community 327 - ".create_panel()"
Cohesion: 0.14
Nodes (7): Handle MCP connection started event., Handle MCP connection completed event., Handle MCP connection failed event., Handle MCP config fetch failed event (AMP resolution failures)., Handle MCP tool execution started event., Handle MCP tool execution failed event., Create a standardized panel with consistent styling.

### Community 328 - "handlers.py"
Cohesion: 0.20
Nodes (13): _get_param_count(), _get_param_count_cached(), is_async_handler(), is_call_handler_safe(), Any, AsyncHandler, Exception, SyncHandler (+5 more)

### Community 329 - "csv_knowledge_source.py"
Cohesion: 0.16
Nodes (9): CSVKnowledgeSource, Path, Load and preprocess CSV file content., Add CSV file content to the knowledge source, chunk it, compute embeddings,, Add CSV file content asynchronously., Utility method to split text into chunks., A knowledge source that stores and queries CSV file content using embeddings., Test CSVKnowledgeSource with a simple CSV file. (+1 more)

### Community 330 - "._has_custom_openai_base_url()"
Cohesion: 0.15
Nodes (8): Factory method that routes to native SDK or falls back to LiteLLM.          Rout, Check if a model name matches provider-specific patterns.          This allows s, Validate if a model name exists in the provider's constants or matches provider, Return whether this call explicitly configures a custom endpoint., Return whether a custom endpoint is configured explicitly or by env., Infer the provider from the model name.          This method first checks the ha, Test the _validate_model_in_constants method., test_validate_model_in_constants()

### Community 331 - "azure.py"
Cohesion: 0.14
Nodes (8): AzureProvider, Any, Azure OpenAI embeddings provider., Azure OpenAI embeddings provider., Test Azure config from memory.mdx documentation., Test RagTool Azure config from ragtool.mdx documentation., Test Azure embeddings don't inherit the OpenAI chat model env var., Test Azure provider accepts 'model' as alias for 'model_name'.

### Community 332 - "mcp_native_tool.py"
Cohesion: 0.18
Nodes (8): MCPNativeTool, Any, Native MCP tool wrapper for CrewAI agents.  This module provides a tool wrapper, Async implementation of tool execution.          A fresh ``MCPClient`` is create, Native MCP tool that creates a fresh client per invocation.      A ``client_fact, Initialize native MCP tool.          Args:             client_factory: Zero-arg, Get the original tool name., Execute tool using the MCP client session.          Args:             **kwargs:

### Community 333 - "Convert a dotted path string t"
Cohesion: 0.26
Nodes (5): Convert a dotted path string to the callable it references.      If *value* is a, string_to_callable(), MonkeyPatch, TestStringToCallable, WarningsChecker

### Community 335 - "Test _is_version_yanked helper"
Cohesion: 0.14
Nodes (8): Test _is_version_yanked helper., Test a non-yanked version returns False., Test a yanked version returns True with reason., Test a yanked version returns True with empty reason., Test an unknown version returns False., Test a version with mixed yanked/non-yanked files is not yanked., Test that the first available reason is returned., TestIsVersionYanked

### Community 336 - "test_client.py"
Cohesion: 0.14
Nodes (13): async_client(), async_client_with_batch_size(), client(), client_with_batch_size(), mock_async_chromadb_client(), mock_chromadb_client(), Tests for ChromaDBClient implementation., Create a mock ChromaDB client. (+5 more)

### Community 337 - "test_file_store.py"
Cohesion: 0.14
Nodes (9): Unit tests for file_store module., Test that get_all_files returns None when no files exist., Tests for asynchronous file store operations., Tests for synchronous file store operations., Set up test fixtures., Test storing and retrieving crew files., Test that get_files returns None for non-existent keys., TestAsyncFileStore (+1 more)

### Community 338 - "Tests for normalize_input_file"
Cohesion: 0.14
Nodes (8): Tests for normalize_input_files function., Test normalizing path strings., Test normalizing Path objects., Test normalizing raw bytes., Test normalizing FileSource objects., Test normalizing mixed input types., Test normalizing empty input list., TestNormalizeInputFiles

### Community 339 - "A2AClientTimeoutError"
Cohesion: 0.15
Nodes (12): A2AClientTimeoutError, A2APollingTimeoutError, AuthenticationRequiredError, is_client_error(), is_retryable_error(), PushNotificationNotSupportedError, A2A error codes and error response utilities.  This module provides a centralize, Raised when polling exceeds the configured timeout. (+4 more)

### Community 340 - "GenerateContentResponse"
Cohesion: 0.21
Nodes (7): GenerateContentResponse, Handle non-streaming content generation., Extract raw finish_reason and response_id from a Gemini         ``GenerateConten, Extract token usage and response metadata from Gemini response., Extract text content from Gemini response without triggering warnings., Process response, execute function calls, and finalize completion.          Args, Process a single streaming chunk.          Args:             chunk: The streamin

### Community 341 - "condition"
Cohesion: 0.15
Nodes (13): condition, message, additionalProperties, description, properties, required, type, $ref (+5 more)

### Community 342 - ".augment_prompt()"
Cohesion: 0.18
Nodes (10): Append A2UI system prompt instructions to the base prompt., build_a2ui_system_prompt(), build_a2ui_v09_system_prompt(), System prompt generation for A2UI-capable agents., Build a v0.8 system prompt fragment instructing the LLM to produce A2UI output., Build a v0.9 system prompt fragment instructing the LLM to produce A2UI output., load_schema(), Any (+2 more)

### Community 343 - "structured_output_converter.py"
Cohesion: 0.18
Nodes (8): LangGraphConverterAdapter, Any, LangGraph structured output converter for CrewAI task integration.  This module, Adapter for handling structured output conversion in LangGraph agents.      Conv, Initialize the converter adapter with a reference to the agent adapter., Configure the structured output for LangGraph.          Analyzes the task's outp, Generate an appendix for the system prompt to enforce structured output., Add structured output instructions to the system prompt if needed.          Args

### Community 344 - "constants.py"
Cohesion: 0.17
Nodes (10): _llm_via_environment_or_fallback(), _normalize_key_name(), Maps environment variable names to recognized litellm parameter keys.      Args:, Creates an LLM instance based on environment variables or defaults.      Returns, Test that Huggingface environment variables are properly configured., Test that Huggingface models are properly configured., Test that Huggingface is in the PROVIDERS list., test_huggingface_env_vars() (+2 more)

### Community 345 - ".answer_from_history_turn()"
Cohesion: 0.18
Nodes (5): Built-in chat handler over canonical conversation history., Answer directly from canonical conversation history when configured., Build context used by the routing policy for the current turn., Build canonical message context for an agent or direct LLM call., Return the effective conversational system prompt.

### Community 346 - "_flag.py"
Cohesion: 0.24
Nodes (11): ExperimentalFeatureDisabledError, is_enabled(), RuntimeError, Experimental feature gate for the Skills Repository., Raised when an experimental feature is used without the flag set., require_experimental_skills(), MonkeyPatch, Tests for the CREWAI_EXPERIMENTAL gate on Skills Repository. (+3 more)

### Community 347 - ".format_text_content()"
Cohesion: 0.18
Nodes (6): Any, Gemini uses a single client for both sync and async calls., Extend base config with Gemini/Vertex-specific fields., Format text as a Gemini content block.          Gemini uses {"text": "..."} form, Get a Gemini file uploader using this LLM's client.          Returns:, Get client parameters for compatibility with base class.          Note: This met

### Community 348 - "crew_definition.py"
Cohesion: 0.19
Nodes (10): CrewAgentDefinition, CrewTaskDefinition, LLMDefinition, BaseModel, PythonReferenceDefinition, Definition models for inline CrewAI crew configurations., Dotted Python reference used by crew definitions., Task definition used by a crew definition. (+2 more)

### Community 349 - "file_handler.py"
Cohesion: 0.18
Nodes (9): FileHandler, LogEntry, TypedDict, Unpack, TypedDict for log entry kwargs with optional fields for flexibility., Handler for file operations supporting both JSON and text-based logging.      At, Initialize the FileHandler with the specified file path.         Args:, Initialize the file path based on the input type.          Args:             fil (+1 more)

### Community 350 - "Any"
Cohesion: 0.17
Nodes (4): Any, Minimal concrete BaseLLM for testing event emission., _StubLLM, TestEmitCallCompletedEventPassesUsage

### Community 351 - "test_cache.py"
Cohesion: 0.22
Nodes (12): TarFile, Tests for SkillCacheManager., A symlink whose target escapes dest is rejected before extraction., A hardlink whose target escapes dest is rejected., Special tar members such as FIFOs are rejected., A symlink that stays within dest is permitted., Build an in-memory tar archive via `build(tf)` and return it for reading., _tar_from_members() (+4 more)

### Community 352 - "test_telemetry_disable.py"
Cohesion: 0.15
Nodes (12): cleanup_telemetry(), Automatically clean up Telemetry singleton between tests., Test telemetry state with different environment variable configurations., Test that telemetry is enabled by default., Test that telemetry operations are disabled when env var is set after singleton, Test that multiple telemetry instances respect dynamically changed env vars., Test that OTEL_SDK_DISABLED also works when set after singleton creation., test_telemetry_disable_after_singleton_creation() (+4 more)

### Community 353 - "ClassDefContext"
Cohesion: 0.20
Nodes (9): ClassDefContext, Plugin, CrewAIPlugin, plugin(), Mypy plugin for CrewAI decorator type checking.  This plugin informs mypy about, Mypy plugin that handles @CrewBase decorator attribute injection., Return hook for class decorators.          Args:             fullname: Fully qua, Add injected attributes to @CrewBase decorated classes.          Args: (+1 more)

### Community 354 - "ModuleSpec"
Cohesion: 0.23
Nodes (7): ModuleSpec, ModuleType, Deprecated: use ``crewai_cli`` instead.  The CLI was extracted into the standalo, Returns an already-imported ``crewai_cli`` submodule without re-executing it., Maps ``crewai.cli[.X]`` imports onto ``crewai_cli[.X]``., _ShimFinder, _ShimLoader

### Community 355 - "description"
Cohesion: 0.17
Nodes (12): description, type, description, format, type, description, pattern, type (+4 more)

### Community 356 - "any"
Cohesion: 0.17
Nodes (12): any, array, boolean, number, object, string, void, returnType (+4 more)

### Community 357 - "_normalize_ollama_base_url()"
Cohesion: 0.21
Nodes (8): _normalize_ollama_base_url(), Normalize Ollama base URL to ensure it ends with /v1.      Ollama uses OLLAMA_HO, Tests for _normalize_ollama_base_url helper., Test that /v1 is added when missing., Test that existing /v1 is preserved., Test that trailing slash is handled., Test /v1/ is normalized., TestNormalizeOllamaBaseUrl

### Community 358 - "common.py"
Cohesion: 0.27
Nodes (11): extract_tool_info(), log_tool_conversion(), Any, Validate function name according to common LLM provider requirements.      Args:, Sanitize function name for LLM provider compatibility.      Args:         name:, Safely extract and validate tool information.      Combines extraction, validati, Extract tool information from various schema formats.      Handles both OpenAI/s, Log tool conversion for debugging.      Args:         tool: The tool being conve (+3 more)

### Community 359 - "process.py"
Cohesion: 0.23
Nodes (7): Process, Enum, str, # TODO: consensual = 'consensual', Class representing the different processes that can be used to tackle tasks, The auto-created hierarchical manager is built outside the agents     loop that, TestHierarchicalManagerCacheWiring

### Community 360 - "EmbeddingFunction"
Cohesion: 0.17
Nodes (9): EmbeddingFunction, QdrantClientType, Initialize QdrantClient with client and embedding function.          Args:, AsyncEmbeddingFunction, Protocol, QueryEmbedding, Convert text to embedding vector.          Args:             text: Input text to, Protocol for async embedding functions that convert text to vectors. (+1 more)

### Community 361 - "parse_tool_call_args()"
Cohesion: 0.27
Nodes (4): parse_tool_call_args(), Parse tool call arguments from a JSON string or dict.      Returns:         ``(a, Unit tests for parse_tool_call_args., TestParseToolCallArgs

### Community 362 - "PickleHandler"
Cohesion: 0.20
Nodes (7): PickleHandler, Any, Handler for saving and loading data using pickle.      Attributes:         file_, Initialize the PickleHandler with the name of the file where data will be stored, Initialize the file with an empty dictionary and overwrite any existing data., Save the data to the specified file using pickle.          Args:           data:, Load the data from the specified file using pickle.          Returns:

### Community 363 - "GuardrailResult"
Cohesion: 0.21
Nodes (10): GuardrailResult, process_guardrail(), Any, BaseModel, GuardrailCallable, Self, Create a GuardrailResult from a validation tuple.          Args:             res, Process the guardrail for the agent output.      Args:         output: The outpu (+2 more)

### Community 364 - "build_rich_field_description()"
Cohesion: 0.29
Nodes (3): build_rich_field_description(), Build a comprehensive field description including constraints.      Embeds forma, TestBuildRichFieldDescription

### Community 365 - "test_base_agent.py"
Cohesion: 0.23
Nodes (4): MockAgent, Any, BaseModel, test_key()

### Community 366 - "test_agent_a2a_wrapping.py"
Cohesion: 0.17
Nodes (11): Test A2A wrapper is only applied when a2a is passed to Agent., Verify that agents without a2a don't get the wrapper applied., Verify that agents with a2a get the wrapper applied., Verify that creating an agent with a2a succeeds and applies wrapper., Verify that multiple agents without a2a work correctly., Verify that agents with and without a2a have different execute_task methods., test_agent_with_a2a_creates_successfully(), test_agent_with_a2a_has_wrapper() (+3 more)

### Community 367 - "test_factory_azure.py"
Cohesion: 0.17
Nodes (7): Test Azure embedder configuration with factory., Test Azure embedder configuration with factory function., Test handling of import errors for Azure provider., Test Azure configuration with nested config key., Test regular OpenAI configuration with nested config., Test Azure provider with minimal required configuration., TestAzureEmbedderFactory

### Community 368 - "test_execution_span_assignment"
Cohesion: 0.17
Nodes (11): Test that crew execution span is properly assigned during kickoff., Test that _execution_span is None when share_crew=False.      When share_crew is, Test that _execution_span is assigned during async kickoff.      Verifies that t, Test that _execution_span is assigned for each crew execution.      Verifies tha, Test that _execution_span is assigned to crew after kickoff.      The bug: event, Test that end_crew receives a valid execution span to close.      This verifies, test_crew_execution_span_assigned_on_kickoff(), test_crew_execution_span_assigned_on_kickoff_async() (+3 more)

### Community 369 - "_flow_level_persist_yaml()"
Cohesion: 0.17
Nodes (12): _flow_level_persist_yaml(), _method_level_persist_yaml(), _saved_methods(), test_class_level_persist_without_instance_kwarg_saves_and_restores(), test_combined_class_and_method_persist_saves_once_per_method(), test_definition_persist_equivalence(), test_flow_level_persist_from_declaration_saves_once_per_method(), test_method_level_persist_decorator_saves_only_that_method() (+4 more)

### Community 370 - "Tests for async method support"
Cohesion: 0.17
Nodes (7): Tests for async method support in @agent, @task decorators., Async agent methods should be properly memoized., Async task methods should be properly memoized., Async task should have name inferred from method name., Async agent decorator should return Agent, not coroutine., Async task decorator should return Task, not coroutine., TestAsyncDecoratorSupport

### Community 371 - "._run()"
Cohesion: 0.17
Nodes (10): AsyncTool, Test implementation with an asynchronous _run method, Process input text asynchronously., Test that _run in a synchronous tool returns a direct result, not a coroutine., Test that _run in an asynchronous tool returns a coroutine object., Test that asyncio.run is called when using async tools., test_async_run_returns_coroutine(), test_creating_a_tool_using_baseclass() (+2 more)

### Community 372 - "Tests for MIME type detection."
Cohesion: 0.17
Nodes (7): Tests for MIME type detection., Test detection of plain text content., Test detection of JSON content., Test detection of PNG content., Test detection of JPEG header., Test detection of PDF header., TestDetectContentType

### Community 373 - "test_lock_store.py"
Cohesion: 0.17
Nodes (3): Tests for lock_store.  We verify our own logic: the _redis_available guard, whic, Ensure a custom backend never leaks across tests., reset_backend()

### Community 374 - "Unit tests with mocked LLM pro"
Cohesion: 0.23
Nodes (7): Unit tests with mocked LLM providers for faster execution., Helper to create mock plan response., Test parsing OpenAI structured response., Test parsing Anthropic structured response (same format)., Test parsing Gemini structured response (same format)., Test parsing Azure OpenAI structured response (same format as OpenAI)., TestStructuredPlanningWithMockedProviders

### Community 375 - "GenerateContentConfig"
Cohesion: 0.22
Nodes (6): GenerateContentConfig, Handle async non-streaming content generation., Handle async streaming content generation., Async call to Google Gemini generate content API.          Args:             mes, Prepare generation config for Google Gemini API.          Args:             syst, Convert CrewAI tool format to Gemini function declaration format.

### Community 376 - "OTLPSpanExporter"
Cohesion: 0.18
Nodes (7): OTLPSpanExporter, SpanExportResult, Check if telemetry should be disabled based on environment variables., Check if telemetry operations should be executed., Safe wrapper for OTLP span exporter that handles exceptions gracefully.      Thi, Export spans to the telemetry backend safely.          Args:             spans:, SafeOTLPSpanExporter

### Community 377 - "Signals"
Cohesion: 0.18
Nodes (7): Signals, Event emitted when SIGCONT is received., SigContEvent, Register handlers for graceful shutdown on process exit and signals., Register a signal handler that emits an event.          Args:             sig: T, Test adapter correctly parses SIGCONT event., Test SigContEvent has correct defaults.

### Community 378 - "ArtifactNotFoundError"
Cohesion: 0.18
Nodes (7): ArtifactNotFoundError, ContentTypeNotSupportedError, InvalidParamsError, RateLimitExceededError, Invalid method parameter(s)., Incompatible content types., The specified artifact was not found.

### Community 379 - "description"
Cohesion: 0.18
Nodes (11): description, type, properties, description, type, description, $ref, type (+3 more)

### Community 380 - "any"
Cohesion: 0.18
Nodes (11): any, array, boolean, number, object, string, void, returnType (+3 more)

### Community 381 - "structured_output_converter.py"
Cohesion: 0.20
Nodes (7): OpenAIConverterAdapter, Any, OpenAI structured output converter for CrewAI task integration.  This module con, Adapter for handling structured output conversion in OpenAI agents.      This ad, Initialize the converter adapter with a reference to the agent adapter., Configure the structured output for OpenAI agent based on task requirements., Enhance the base system prompt with structured output requirements if needed.

### Community 382 - "Push the latest recorded ``tas"
Cohesion: 0.29
Nodes (5): Push the latest recorded ``task_started`` scope for a task.      Args:         t, resume_task_scope(), Tests for the checkpoint-resume scope helper., The pushed scope must be popped by a matching task_completed., TestResumeTaskScope

### Community 383 - "on_signal()"
Cohesion: 0.18
Nodes (8): on_signal(), T, Decorator to register a handler for all signal events.      Args:         func:, Tests for the @on_signal decorator., Test that @on_signal registers handler for all signal event types., Test that @on_signal returns the original function., Test that @on_signal preserves function metadata., TestOnSignalDecorator

### Community 384 - "extract_json_from_llm_response"
Cohesion: 0.22
Nodes (5): extract_json_from_llm_response(), Any, Any, Any, Any

### Community 385 - "flow_config.py"
Cohesion: 0.18
Nodes (7): FlowConfig, Global Flow configuration.  This module provides a singleton configuration objec, Global configuration for Flow execution.      Attributes:         hitl_provider:, Get the configured HITL provider., Set the HITL provider., Get the configured input provider for ``Flow.ask()``.          Returns:, Set the input provider for ``Flow.ask()``.          Args:             provider:

### Community 386 - "Strip JSONC comments and trail"
Cohesion: 0.29
Nodes (4): Strip JSONC comments and trailing commas while preserving string values., strip_jsonc_comments(), _strip_trailing_commas(), TestStripJsoncComments

### Community 387 - "Validate JSON crew structure w"
Cohesion: 0.40
Nodes (4): Validate JSON crew structure without kicking off the crew., validate_crew_project(), MonkeyPatch, TestValidationDoesNotExecuteTools

### Community 388 - "Any"
Cohesion: 0.25
Nodes (7): Any, Manages storage and retrieval of task outputs.      This handler provides an int, Update an existing task output in storage.          Args:             task_index, Add a new task output to storage.          Args:             task: The task that, Clear all stored task outputs., Load all stored task outputs.          Returns:             List of task output, TaskOutputStorageHandler

### Community 389 - "Path"
Cohesion: 0.24
Nodes (7): Path, Test is_current_version_yanked public function., Test reading yanked status from a valid cache., Test non-yanked status from a valid cache., Test that a stale cache triggers a re-fetch., Test that fetch failure returns not yanked., TestIsCurrentVersionYanked

### Community 390 - "CustomLLM"
Cohesion: 0.18
Nodes (6): CustomLLM, Custom LLM implementation for testing.      This is a simple implementation of t, Mock LLM call that returns a predefined response.         Properly formats messa, Return False to indicate that function calling is not supported.          Return, Return False to indicate that stop words are not supported.          Returns:, Return a default context window size.          Returns:             4096, a typi

### Community 391 - "Regression tests for EPD-179: "
Cohesion: 0.29
Nodes (4): Regression tests for EPD-179: BaseTool.model_post_init silently     rewrote the, Authored text that merely mentions "Tool Description:" must reach         the LL, A description that already contains a composed block (old         checkpoints, a, TestAuthoredDescriptionPreserved

### Community 392 - "test_training_converter.py"
Cohesion: 0.20
Nodes (3): BaseModel, TestModel, TestTrainingConverter

### Community 393 - "PrinterColor"
Cohesion: 0.20
Nodes (7): PrinterColor, get_logger(), Get a logger configured for structured JSON output.      Args:         name: Log, Initialize MCP client.          Args:             transport: Transport instance, Logger, BaseModel, Log a message with timestamp if verbose mode is enabled.          Args:

### Community 394 - "updateDataModel"
Cohesion: 0.20
Nodes (10): updateDataModel, UpdateDataModelMessage, updateDataModel, additionalProperties, description, type, additionalProperties, properties (+2 more)

### Community 395 - ".to_dict()"
Cohesion: 0.24
Nodes (8): A2AErrorCode, create_error_response(), Any, IntEnum, Convert to JSON-RPC error object format., Convert to full JSON-RPC error response., A2A protocol error codes.      Codes follow JSON-RPC 2.0 specification with A2A-, Create a JSON-RPC error response.      Args:         code: Error code (A2AErrorC

### Community 396 - "description"
Cohesion: 0.20
Nodes (10): description, properties, type, AccessibilityAttributes, description, $ref, description, $ref (+2 more)

### Community 397 - "description"
Cohesion: 0.20
Nodes (10): description, type, properties, catalogId, sendDataModel, theme, description, type (+2 more)

### Community 398 - "parser.py"
Cohesion: 0.27
Nodes (9): _clean_action(), _extract_thought(), parse(), Agent output parsing module for ReAct-style LLM responses.  This module provides, Extract the thought portion from the text.      Args:         text: The full age, Clean action string by removing non-essential formatting characters.      Args:, Safely repair JSON input.      Args:         tool_input: The tool input string t, Parse agent output text into AgentAction or AgentFinish.      Expects output to (+1 more)

### Community 399 - "JSONAgentDefinition"
Cohesion: 0.20
Nodes (8): JSONAgentDefinition, Parsed JSON agent definition and constructor kwargs., CustomEmbeddingFunction, Documents, Embeddings, Custom embedding function base implementation., Convert input documents to embeddings.          Args:             input: List of, Base class for custom embedding functions.      This provides a concrete impleme

### Community 400 - "validation.py"
Cohesion: 0.24
Nodes (7): Path, Validation functions for Agent Skills specification constraints.  Validates skil, Validate that a directory name matches the skill name.      Args:         skill_, validate_directory_name(), Path, Tests for validate_directory_name., TestValidateDirectoryName

### Community 401 - "callable_to_string()"
Cohesion: 0.33
Nodes (3): callable_to_string(), Serialize a module-level callable as a ``"module.qualname"`` string.      Args:, TestCallableToString

### Community 402 - "aclear_task_files()"
Cohesion: 0.20
Nodes (7): aclear_task_files(), clear_task_files(), Clear files for a task execution asynchronously.      Args:         task_id: Uni, Clear files for a task execution.      Args:         task_id: Unique identifier, Crew-level input_files should attach to the LLM user message., Clean up after tests., Test clearing task files.

### Community 403 - "Recursively resolve all local "
Cohesion: 0.29
Nodes (4): Recursively resolve all local $refs in the given JSON Schema using $defs as the, resolve_refs(), TestResolveRefs, TestResolveRefsRecursive

### Community 404 - "test_run_crew.py"
Cohesion: 0.24
Nodes (5): CliRunner, Tests for the ``crewai run`` command and its subprocess plumbing., runner(), test_run_passes_filename_to_run_crew(), test_run_without_filename_passes_none()

### Community 405 - "test_prompt_cache.py"
Cohesion: 0.20
Nodes (5): Regression tests for the provider-agnostic prompt-cache breakpoint flag., The strip-on-format pass must not erase markers from the caller's     messages l, TestBaseFormatDoesNotMutate, TestCacheMarkerHelpers, TestNonAnthropicStripsMarker

### Community 406 - "Tests for _resolve_external wi"
Cohesion: 0.20
Nodes (4): Tests for _resolve_external with #tool-name filtering., https://...#get-page must match the sanitized key get_page in schemas., https://...#get_page must also match the sanitized key get_page., TestResolveExternalToolFilter

### Community 407 - "test_tool_resolver_native.py"
Cohesion: 0.20
Nodes (6): agent(), http_config(), Tests for MCPToolResolver native (non-AMP) resolution paths., resolver(), TestResolveNativeEmptyTools, TestResolveNativeRuntimeError

### Community 408 - "test_client_factory_registry.p"
Cohesion: 0.20
Nodes (3): Tests for the RAG client factory registry seam.  We verify our own logic: a regi, Reset the registry around each test without clobbering preexisting state., reset_registry()

### Community 409 - "Test that invalid JSON falls b"
Cohesion: 0.20
Nodes (6): Test that invalid JSON falls back to string matching., Test that LLM exception triggers fallback to simple prompting., Tests for _collapse_to_outcome JSON parsing edge cases., Test that JSON string response from LLM is correctly parsed., Test that plain string response is correctly matched., TestCollapseToOutcomeJsonParsing

### Community 410 - "assert_parity()"
Cohesion: 0.20
Nodes (10): assert_parity(), _run_with_events(), _state_without_id(), test_and_or_merge_parity(), test_cyclic_flow_parity(), test_definition_config_equivalence(), test_definition_flow_events_use_definition_name(), test_pydantic_state_from_ref_parity() (+2 more)

### Community 412 - "test_files.py"
Cohesion: 0.20
Nodes (6): Unit tests for files module., Tests for FileBytes class., Test creating FileBytes from raw bytes., Test creating FileBytes with optional filename., Test content type detection from bytes., TestFileBytes

### Community 413 - "Tests for FileStream class."
Cohesion: 0.20
Nodes (6): Tests for FileStream class., Test creating FileStream from a file-like object., Test that stream content is cached., Test filename extraction from stream with name attribute., Test closing the underlying stream., TestFileStream

### Community 414 - "test_serialization.py"
Cohesion: 0.42
Nodes (9): Address, Container, DataclassPerson, Person, BaseModel, test_dataclass_serialization_recurses_into_nested_values(), test_exclude_keys(), test_polymorphic_field_serializes_concrete_subclass() (+1 more)

### Community 415 - "Tests for AgentReasoning with "
Cohesion: 0.20
Nodes (6): Tests for AgentReasoning with mocked LLM responses., Create a mock agent for testing., Test that steps are correctly parsed from LLM function response., Test that missing optional fields are handled correctly., Test that steps with missing fields get default values., TestAgentReasoningWithMockedLLM

### Community 416 - "ChannelCredentials"
Cohesion: 0.22
Nodes (7): ChannelCredentials, BaseModel, SSLContext, TLS/mTLS configuration for secure client connections.      Supports mutual TLS (, Build SSL context for httpx client.          Returns:             SSL context if, Build gRPC channel credentials for secure connections.          Returns:, TLSConfig

### Community 417 - "id"
Cohesion: 0.22
Nodes (9): id, $ref, properties, required, type, ComponentCommon, $ref, accessibility (+1 more)

### Community 418 - "path"
Cohesion: 0.22
Nodes (9): path, additionalProperties, properties, required, type, DataBinding, description, type (+1 more)

### Community 419 - "._migrate_deprecated_transport"
Cohesion: 0.22
Nodes (5): Self, Ensure exactly one key source is provided., Migrate deprecated transport fields to new config., Migrate deprecated transport fields to new config., Migrate deprecated fields to new config.

### Community 420 - "allOf"
Cohesion: 0.22
Nodes (9): allOf, type, unevaluatedProperties, allOf, type, unevaluatedProperties, components, AudioPlayer (+1 more)

### Community 421 - "description"
Cohesion: 0.22
Nodes (9): description, type, type, inlineCatalogs, supportedCatalogIds, description, items, type (+1 more)

### Community 422 - "anyOf"
Cohesion: 0.22
Nodes (9): anyOf, additionalProperties, description, type, description, type, properties, args (+1 more)

### Community 423 - "description"
Cohesion: 0.22
Nodes (9): description, properties, type, description, items, type, Checkable, $ref (+1 more)

### Community 424 - "description"
Cohesion: 0.22
Nodes (9): description, items, minItems, type, components, surfaceId, description, type (+1 more)

### Community 425 - "base_event_listener.py"
Cohesion: 0.28
Nodes (6): BaseEventListener, ABC, Base event listener for CrewAI event system., Initialize the event listener and register handlers., Setup event listeners on the event bus.          Args:             crewai_event_, Abstract base class for event listeners.

### Community 426 - "source_helper.py"
Cohesion: 0.25
Nodes (6): Any, Helper utilities for knowledge sources., Helper class for creating and managing knowledge sources., Check if a file type is supported.          Args:             file_path: Path to, Create appropriate KnowledgeSource based on file extension.          Args:, SourceHelper

### Community 427 - "OutputClass"
Cohesion: 0.25
Nodes (6): OutputClass, T, Base wrapper for classes marked as output format., Initialize the output class wrapper.          Args:             cls: The class t, Create an instance of the wrapped class.          Args:             *args: Posit, Delegate attribute access to the wrapped class.          Args:             name:

### Community 428 - "BaseModel"
Cohesion: 0.28
Nodes (7): BaseModel, Model representing a reasoning plan for a task., ReasoningPlan, Tests for the ReasoningPlan model with structured steps., Test ReasoningPlan can be created with empty steps., Test ReasoningPlan with structured steps., TestReasoningPlan

### Community 429 - "test_agent_inject_date.py"
Cohesion: 0.22
Nodes (8): Test that the inject_date flag injects the current date into the task.      Test, Test that without inject_date flag, no date is injected.      Tests that when in, Test that the inject_date flag with custom date_format works correctly.      Tes, Test error handling with invalid date format.      Tests that when an invalid da, test_agent_inject_date(), test_agent_inject_date_custom_format(), test_agent_inject_date_invalid_format(), test_agent_without_inject_date()

### Community 431 - "JWTAuthLLM"
Cohesion: 0.22
Nodes (5): JWTAuthLLM, Custom LLM implementation with JWT authentication., Return True to indicate that function calling is supported., Return True to indicate that stop words are supported., Return a default context window size.

### Community 432 - ".call()"
Cohesion: 0.22
Nodes (7): Any, Record the call and return a predefined response., Test a custom LLM implementation with JWT authentication., Simulate API calls with timeout handling and retry logic.          Args:, Test a custom LLM implementation with timeout handling and retry logic., test_custom_llm_with_jwt_auth(), test_timeout_handling_llm()

### Community 433 - "Custom LLM implementation with"
Cohesion: 0.22
Nodes (5): Custom LLM implementation with timeout handling and retry logic., Return True to indicate that function calling is supported.          Returns:, Return True to indicate that stop words are supported.          Returns:, Return a default context window size.          Returns:             8192, a typi, TimeoutHandlingLLM

### Community 434 - "test_llm_streaming_finish_reas"
Cohesion: 0.31
Nodes (8): _chunks_with_usage_tail(), _completed_event(), mock_emit(), Any, Regression: LiteLLM emits a final usage-only chunk (choices=[]) when ``stream_op, Three-chunk stream mirroring LiteLLM's include_usage behavior:     two content c, test_async_stream_emits_finish_reason_and_response_id_from_loop(), test_sync_stream_emits_finish_reason_and_response_id_from_loop()

### Community 435 - "EventT_co"
Cohesion: 0.25
Nodes (6): EventT_co, EventHandler, Any, Dependency injection system for event handlers.  This module provides a FastAPI-, Protocol for event handler functions.      Generic protocol that accepts any sub, Event handler signature.          Args:             source: The object that emit

### Community 436 - "currency"
Cohesion: 0.25
Nodes (8): currency, format, other, pattern, url, value, values, required

### Community 437 - "name"
Cohesion: 0.25
Nodes (8): name, parameters, returnType, FunctionDefinition, additionalProperties, description, required, type

### Community 438 - "surfaceId"
Cohesion: 0.25
Nodes (8): surfaceId, additionalProperties, description, properties, required, type, deleteSurface, required

### Community 439 - "client_capabilities.json"
Cohesion: 0.25
Nodes (7): description, $id, v0.9, required, $schema, title, type

### Community 440 - "meta.py"
Cohesion: 0.25
Nodes (6): AgentMeta, Any, ModelMetaclass, Generic metaclass for agent extensions.  This metaclass enables extension capabi, Generic metaclass for agent extensions.      Detects extension fields (like 'a2a, Create a new class with extension support.          Args:             name: The

### Community 441 - ".sanitize_tool_name()"
Cohesion: 0.25
Nodes (4): Sanitize tool name for API compatibility., Save task result to unified memory (memory or crew._memory)., Build the Executor's system prompt., Fail step execution when a required tool is configured but not called.

### Community 442 - "._gracefully_fail()"
Cohesion: 0.25
Nodes (4): Reset batch manager state to allow future executions to re-initialize., Handle errors gracefully without disrupting user experience., Show message when traces were collected locally but couldn't be uploaded., Initialize backend batch and send collected events.

### Community 443 - ".add_event()"
Cohesion: 0.25
Nodes (4): Any, Individual trace event payload, TraceEvent, Successful send must not restore a stale event buffer (duplicate events).

### Community 444 - "AgentMessage"
Cohesion: 0.29
Nodes (6): AgentMessage, ConversationEvent, Record an agent result, optionally making it visible to the user., BaseModel, Private per-agent message or scratch result., Structured trace/event that is separate from user-visible messages.

### Community 445 - ".to_dict()"
Cohesion: 0.32
Nodes (4): _object_ref(), Any, Format a class or instance as the canonical ``module:qualname`` ref., Serialize the definition to a declaration-ready dictionary.

### Community 447 - "Unpack"
Cohesion: 0.25
Nodes (6): Unpack, Initialize WatsonX embedding function.          Args:             verbose: Wheth, TypedDict, Type definitions for IBM WatsonX embedding providers., Configuration for WatsonX provider., WatsonXProviderConfig

### Community 448 - "Unpack"
Cohesion: 0.25
Nodes (6): Unpack, Initialize VoyageAI embedding function.          Args:             **kwargs: Con, TypedDict, Type definitions for VoyageAI embedding providers., Configuration for VoyageAI provider., VoyageAIProviderConfig

### Community 449 - "handle_partial_json()"
Cohesion: 0.25
Nodes (8): handle_partial_json(), Handle partial JSON in a result string and convert to Pydantic model or dict., JSON values with literal newlines/tabs (lenient parsing) must still     validate, A regex match that is not actually JSON (e.g. GraphQL) must fall through     to, test_handle_partial_json_accepts_literal_control_chars_in_strings(), test_handle_partial_json_falls_through_for_non_json_curly_blocks(), test_handle_partial_json_with_invalid_partial(), test_handle_partial_json_with_valid_partial()

### Community 451 - "test_replay_from_task.py"
Cohesion: 0.32
Nodes (5): CliRunner, Tests for ``crewai replay`` and the trained-agents file plumbing., runner(), test_replay_passes_filename(), test_replay_without_filename_passes_none()

### Community 452 - "Test execution behavior of cre"
Cohesion: 0.25
Nodes (5): Test execution behavior of crew-scoped hooks., Test that crew-scoped hook executes with self properly bound., Test that crew-scoped hooks can modify instance variables., Test that multiple instances of the same crew maintain separate state., TestCrewScopedHookExecution

### Community 453 - "Test suite for async AsyncHTTP"
Cohesion: 0.25
Nodes (5): Test suite for async AsyncHTTPransport with interceptor., Test that async transport can be instantiated with interceptor., Test that async transport requires interceptor parameter., Test that async interceptor hooks are called during request handling., TestAsyncHTTPTransport

### Community 454 - "test_openai_compatible.py"
Cohesion: 0.25
Nodes (5): Tests for OpenAI-compatible providers., Tests for mocking the call method., Test that the call method can be mocked for testing., Test that acall method exists for async calls., TestCallMocking

### Community 455 - "Test acreate_collection with a"
Cohesion: 0.25
Nodes (5): Test acreate_collection with all optional parameters., Test aadd_documents with custom document IDs., Test that reset calls the underlying client correctly., Test suite for ChromaDBClient., TestChromaDBClient

### Community 456 - "assert_agent_runtime_field_sch"
Cohesion: 0.39
Nodes (6): assert_agent_runtime_field_schema(), assert_llm_definition_schema(), assert_planning_config_schema(), Any, test_agent_action_json_schema_describes_inline_agent_definitions(), test_crew_action_json_schema_describes_inline_crew_definitions()

### Community 457 - "test_markdown_task.py"
Cohesion: 0.25
Nodes (7): Test the markdown attribute in Task class., Test that markdown flag correctly controls the inclusion of markdown formatting, Test markdown formatting with empty description., Test markdown with JSON output format to ensure compatibility., test_markdown_option_in_task_prompt(), test_markdown_with_complex_output_format(), test_markdown_with_empty_description()

### Community 458 - "Tests for args_schema validati"
Cohesion: 0.25
Nodes (5): Tests for args_schema validation in Tool.run() (decorator-based tools)., Decorator-created tools should also validate kwargs against schema., Decorator tools should reject missing required args via validation., Positional args to decorator tools should bypass validation., TestToolDecoratorRunValidation

### Community 459 - "test_thread_safety.py"
Cohesion: 0.36
Nodes (5): Tests for thread safety in CrewAI event bus.  This module tests concurrent event, test_concurrent_emit_from_multiple_threads(), test_concurrent_handler_registration(), test_stress_test_rapid_emit(), ThreadSafetyTestEvent

### Community 460 - "Tests for wrap_file_source fun"
Cohesion: 0.25
Nodes (5): Tests for wrap_file_source function., Test wrapping image source returns ImageFile., Test wrapping PDF source returns PDFFile., Test wrapping text source returns TextFile., TestWrapFileSource

### Community 461 - "Node"
Cohesion: 0.33
Nodes (5): Node, Parser, Parse {% css 'styles.css' %} tag.          Args:             parser: Jinja2 pars, Parse {% js 'script.js' %} tag.          Args:             parser: Jinja2 parser, test_unlimited_depth_still_detects_dataclass_cycles()

### Community 462 - "_get_default_update_config()"
Cohesion: 0.29
Nodes (6): _get_default_update_config(), UpdateConfig, BaseModel, Streaming update mechanism configuration., Configuration for SSE-based task updates., StreamingConfig

### Community 463 - "additionalProperties"
Cohesion: 0.29
Nodes (7): additionalProperties, description, required, type, $defs, Catalog, catalogId

### Community 464 - "server_to_client.json"
Cohesion: 0.29
Nodes (6): description, $id, oneOf, $schema, title, type

### Community 465 - "description"
Cohesion: 0.29
Nodes (7): description, type, path, value, properties, additionalProperties, description

### Community 466 - "._check_execution_error()"
Cohesion: 0.38
Nodes (4): Exception, Check if an execution error should be re-raised immediately.          Args:, Handle execution errors with retry logic (sync path).          Args:, Handle execution errors with retry logic (async path).          Args:

### Community 467 - "._call_handlers()"
Cohesion: 0.29
Nodes (4): Call provided synchronous handlers.          Args:             source: The emitt, Emit an event with dependency-aware handler execution.          Handlers are gro, Dependency-aware dispatch with the replaying flag set., SyncHandlerSet

### Community 468 - "set_tui_mode()"
Cohesion: 0.52
Nodes (6): set_tui_mode(), _make_formatter(), Flow panels must be suppressed while a TUI owns the screen., test_flow_panel_prints_when_not_tui_mode(), test_flow_panel_suppressed_in_tui_mode(), test_non_flow_panel_unaffected_by_tui_mode()

### Community 469 - "Any"
Cohesion: 0.62
Nodes (3): Any, Set task identity and fingerprint data on an event., _set_task_fingerprint()

### Community 470 - "_router.py"
Cohesion: 0.62
Nodes (6): _get_router_return_events(), _normalize_router_emit(), Any, _return_annotation(), _string_values_from_annotation(), _unwrap_function()

### Community 471 - "_types.py"
Cohesion: 0.29
Nodes (5): FlowMethodDecorator, F, Protocol, Private typing helpers for the Python Flow DSL., Decorator returned by Flow DSL authoring helpers.      The runtime wraps methods

### Community 472 - "_outputs.py"
Cohesion: 0.43
Nodes (6): _MethodOutput, _output_value(), outputs_by_name(), Any, TypedDict, Shared FlowDefinition runtime output helpers.

### Community 473 - "types.py"
Cohesion: 0.33
Nodes (6): NodeMetadata, TypedDict, Type definitions for Flow structure visualization., Metadata for a single node in the flow structure., Represents a connection in the flow structure., StructureEdge

### Community 474 - "cache.py"
Cohesion: 0.33
Nodes (6): mark_cache_breakpoint(), Any, Provider-agnostic prompt-cache breakpoint marker.  Application code (prompt buil, Return ``message`` with the cache-breakpoint flag set.      Returns a new dict s, Remove the breakpoint flag from a message in place., strip_cache_breakpoint()

### Community 475 - "bedrock.py"
Cohesion: 0.29
Nodes (6): BedrockProvider, create_aws_session(), Any, Amazon Bedrock embeddings provider., Create an AWS session for Bedrock.      Returns:         boto3.Session: AWS sess, Amazon Bedrock embeddings provider.

### Community 476 - "watsonx.py"
Cohesion: 0.29
Nodes (5): Self, IBM WatsonX embeddings provider., IBM WatsonX embeddings provider.      Note: Requires custom implementation as Wa, Validate that either space_id or project_id is provided., WatsonXProvider

### Community 477 - "Self"
Cohesion: 0.29
Nodes (3): Self, Check if the tools are set., Check if an output type is set.

### Community 478 - "force_additional_properties_fa"
Cohesion: 0.43
Nodes (3): force_additional_properties_false(), Force additionalProperties=false on all object-type dicts recursively.      Open, TestForceAdditionalPropertiesFalse

### Community 479 - "Remove null type from anyOf/ty"
Cohesion: 0.43
Nodes (3): Remove null type from anyOf/type arrays.      Pydantic generates `T | None` for, strip_null_from_types(), TestStripNullFromTypes

### Community 480 - "test_custom_llm.py"
Cohesion: 0.29
Nodes (6): Test that the custom LLM properly formats messages, Test that JWT token validation works correctly., Test that a custom LLM implementation works with create_llm., test_custom_llm_implementation(), test_custom_llm_message_formatting(), test_jwt_auth_llm_validation()

### Community 481 - "test_crewai_event_bus.py"
Cohesion: 0.43
Nodes (6): Test that multiple handlers can be registered for the same event type., Test that handler exceptions are caught and don't break the event bus., test_event_bus_error_handling(), test_multiple_handlers_same_event(), test_specific_event_handler(), TestEvent

### Community 483 - "components"
Cohesion: 0.33
Nodes (6): components, updateComponents, additionalProperties, description, required, type

### Community 484 - "deleteSurface"
Cohesion: 0.33
Nodes (6): deleteSurface, DeleteSurfaceMessage, additionalProperties, properties, required, type

### Community 485 - "supportedCatalogIds"
Cohesion: 0.33
Nodes (6): supportedCatalogIds, properties, v0.9, description, required, type

### Community 486 - "properties"
Cohesion: 0.33
Nodes (6): properties, type, CatalogComponentCommon, weight, description, type

### Community 487 - "description"
Cohesion: 0.33
Nodes (6): description, properties, required, type, unevaluatedProperties, formatNumber

### Community 488 - "description"
Cohesion: 0.33
Nodes (6): description, properties, required, type, unevaluatedProperties, formatString

### Community 489 - "length"
Cohesion: 0.33
Nodes (6): length, description, properties, required, type, unevaluatedProperties

### Community 490 - "not"
Cohesion: 0.33
Nodes (6): not, description, properties, required, type, unevaluatedProperties

### Community 491 - "numeric"
Cohesion: 0.33
Nodes (6): numeric, description, properties, required, type, unevaluatedProperties

### Community 492 - "openUrl"
Cohesion: 0.33
Nodes (6): openUrl, description, properties, required, type, unevaluatedProperties

### Community 493 - "pluralize"
Cohesion: 0.33
Nodes (6): pluralize, description, properties, required, type, unevaluatedProperties

### Community 494 - "regex"
Cohesion: 0.33
Nodes (6): regex, description, properties, required, type, unevaluatedProperties

### Community 495 - "required"
Cohesion: 0.33
Nodes (6): required, description, properties, required, type, unevaluatedProperties

### Community 496 - "description"
Cohesion: 0.33
Nodes (6): description, items, type, items, $ref, functions

### Community 497 - "FunctionCall"
Cohesion: 0.33
Nodes (6): FunctionCall, description, oneOf, required, type, call

### Community 498 - "additionalProperties"
Cohesion: 0.33
Nodes (6): additionalProperties, description, required, type, catalogId, createSurface

### Community 499 - "LogContext"
Cohesion: 0.40
Nodes (3): LogContext, Any, Context manager for adding fields to all logs within a scope.      Example:

### Community 500 - ".get_multimodal_tools()"
Cohesion: 0.33
Nodes (4): Return tools for multimodal agent capabilities., AddImageTool, Any, Tool for adding images to the content

### Community 501 - "._get_context()"
Cohesion: 0.47
Nodes (4): aggregate_raw_outputs_from_task_outputs(), aggregate_raw_outputs_from_tasks(), Generate string context from the task outputs.      Args:         task_outputs:, Generate string context from the tasks.      Args:         tasks: List of Task o

### Community 502 - "flow_trackable.py"
Cohesion: 0.33
Nodes (4): FlowTrackable, BaseModel, Self, Mixin that tracks flow execution context for objects created within flows.

### Community 503 - "constants.py"
Cohesion: 0.33
Nodes (3): _NotSpecified, CoreSchema, Sentinel class to detect when no value has been explicitly provided.      Notes:

### Community 504 - "ensure_type_in_schemas()"
Cohesion: 0.47
Nodes (3): ensure_type_in_schemas(), Ensure all schema objects in anyOf/oneOf have a 'type' key.      OpenAI strict m, TestEnsureTypeInSchemas

### Community 505 - "test_callback_with_taskoutput."
Cohesion: 0.33
Nodes (5): Test callback decorator with TaskOutput arguments., Test that @callback decorator works with TaskOutput arguments., Integration test for callback with actual task execution., test_callback_decorator_with_taskoutput(), test_callback_decorator_with_taskoutput_integration()

### Community 506 - "test_factory.py"
Cohesion: 0.33
Nodes (5): Tests for RAG config factory., Test ChromaDB client creation., Test unsupported provider raises ValueError., test_create_client_chromadb(), test_create_client_unsupported_provider()

### Community 507 - "test_models.py"
Cohesion: 0.33
Nodes (3): Tests for skills/models.py., Tests for DisclosureLevel constants., TestDisclosureLevel

### Community 508 - "test_imports.py"
Cohesion: 0.33
Nodes (5): Test that all public API classes are properly importable., Test that CrewOutput can be imported from crewai., Test that TaskOutput can be imported from crewai., test_crew_output_import(), test_task_output_import()

### Community 509 - "Test implementation with a syn"
Cohesion: 0.33
Nodes (5): Test implementation with a synchronous _run method, Process input text synchronously., Test that asyncio.run is NOT called when using sync tools., SyncTool, test_run_does_not_call_asyncio_run_for_sync_tools()

### Community 510 - "Tests for args_schema validati"
Cohesion: 0.33
Nodes (4): Tests for args_schema validation in Tool.arun() (decorator-based async tools)., Async decorator tools should validate kwargs in arun., Async decorator tools should reject missing required args in arun., TestToolDecoratorArunValidation

### Community 511 - "Integration tests with real LL"
Cohesion: 0.33
Nodes (4): Integration tests with real LLM calls to verify no thought leakage., Test that agent without tools produces clean output without 'Thought:' prefix., Test that a simple task produces clean output without internal reasoning., TestRealLLMNoThoughtLeakage

### Community 512 - "FlowPersistenceFactory"
Cohesion: 0.40
Nodes (4): FlowPersistenceFactory, Pluggable default persistence backend for flows.  By default, ``@persist`` and t, Replace the process-wide default flow persistence factory.      Intended for one, set_flow_persistence_factory()

### Community 513 - "Pattern"
Cohesion: 0.50
Nodes (4): Pattern, _duplicate_separator_pattern(), Convert text to a URL-safe slug.      Normalizes Unicode characters, removes spe, slugify()

### Community 514 - "common_types.json"
Cohesion: 0.40
Nodes (4): description, $id, $schema, title

### Community 515 - "config.py"
Cohesion: 0.40
Nodes (4): PollingConfig, BaseModel, Polling update mechanism configuration., Configuration for polling-based task updates.      Attributes:         interval:

### Community 516 - "._cleanup_mcp_clients()"
Cohesion: 0.40
Nodes (3): MCPServerConfig, Convert MCP server references/configs to CrewAI tools.          Delegates to :cl, Cleanup MCP client connections after task execution.

### Community 517 - "__init__.py"
Cohesion: 0.40
Nodes (4): __getattr__(), Any, CrewAI events system for monitoring and extending agent behavior.  This module p, Lazy import for event types and registered extensions.

### Community 518 - "Any"
Cohesion: 0.40
Nodes (5): Any, Safely serialize an object to a dictionary for event data., Truncate message content and limit number of messages, safe_serialize_to_dict(), truncate_messages()

### Community 519 - "reasoning_metrics.py"
Cohesion: 0.50
Nodes (4): Enum, Agent reasoning efficiency evaluators.  This module provides evaluator implement, # NOTE: Uses simple n-gram similarity; embedding-based would be more robust, ReasoningPatternType

### Community 520 - "__init__.py"
Cohesion: 0.40
Nodes (4): __getattr__(), Any, Async human feedback support for CrewAI Flows.  This module provides abstraction, Support extensions via dynamic attribute lookup.

### Community 521 - "._init_client()"
Cohesion: 0.40
Nodes (3): Client, Eagerly build the client when credentials resolve, otherwise defer         so ``, Initialize the Google Gen AI client with proper parameter handling.          Arg

### Community 522 - "__init__.py"
Cohesion: 0.40
Nodes (4): __getattr__(), Any, Memory module: unified Memory with LLM analysis and pluggable storage.  Heavy de, Lazily import Memory / EncodingFlow to avoid pulling in lancedb at import time.

### Community 523 - "types.py"
Cohesion: 0.40
Nodes (4): BedrockProviderConfig, TypedDict, Type definitions for AWS embedding providers., Configuration for Bedrock provider.

### Community 524 - "types.py"
Cohesion: 0.40
Nodes (4): CohereProviderConfig, TypedDict, Type definitions for Cohere embedding providers., Configuration for Cohere provider.

### Community 525 - "types.py"
Cohesion: 0.40
Nodes (4): CustomProviderConfig, TypedDict, Type definitions for custom embedding providers., Configuration for Custom provider.

### Community 526 - "types.py"
Cohesion: 0.40
Nodes (4): HuggingFaceProviderConfig, TypedDict, Type definitions for HuggingFace embedding providers., Configuration for HuggingFace provider.

### Community 527 - "types.py"
Cohesion: 0.40
Nodes (4): InstructorProviderConfig, TypedDict, Type definitions for Instructor embedding providers., Configuration for Instructor provider.

### Community 528 - "types.py"
Cohesion: 0.40
Nodes (4): JinaProviderConfig, TypedDict, Type definitions for Jina embedding providers., Configuration for Jina provider.

### Community 529 - "types.py"
Cohesion: 0.40
Nodes (4): AzureProviderConfig, TypedDict, Type definitions for Microsoft Azure embedding providers., Configuration for Azure provider.

### Community 530 - "types.py"
Cohesion: 0.40
Nodes (4): OllamaProviderConfig, TypedDict, Type definitions for Ollama embedding providers., Configuration for Ollama provider.

### Community 531 - "types.py"
Cohesion: 0.40
Nodes (4): ONNXProviderConfig, TypedDict, Type definitions for ONNX embedding providers., Configuration for ONNX provider.

### Community 532 - "types.py"
Cohesion: 0.40
Nodes (4): OpenAIProviderConfig, TypedDict, Type definitions for OpenAI embedding providers., Configuration for OpenAI provider.

### Community 533 - "types.py"
Cohesion: 0.40
Nodes (4): OpenCLIPProviderConfig, TypedDict, Type definitions for OpenCLIP embedding providers., Configuration for OpenCLIP provider.

### Community 534 - "types.py"
Cohesion: 0.40
Nodes (4): TypedDict, Type definitions for Roboflow embedding providers., Configuration for Roboflow provider., RoboflowProviderConfig

### Community 535 - "types.py"
Cohesion: 0.40
Nodes (4): TypedDict, Type definitions for SentenceTransformer embedding providers., Configuration for SentenceTransformer provider., SentenceTransformerProviderConfig

### Community 536 - "types.py"
Cohesion: 0.40
Nodes (4): TypedDict, Type definitions for Text2Vec embedding providers., Configuration for Text2Vec provider., Text2VecProviderConfig

### Community 537 - "checkpoint_config.py"
Cohesion: 0.40
Nodes (4): _coerce_checkpoint(), Any, Checkpoint configuration for automatic state persistence., BeforeValidator for checkpoint fields on Crew/Flow/Agent.      Converts True to

### Community 538 - ".append()"
Cohesion: 0.40
Nodes (3): Any, Append new training data for a specific agent and iteration.          Args:, Save the trained data for a specific agent.          Args:             agent_id:

### Community 539 - "BaseModel"
Cohesion: 0.40
Nodes (5): BaseModel, Structure for research results., ResearchResult, Test that stop words are NOT applied when response_model is provided.     This e, test_openai_stop_words_not_applied_to_structured_output()

### Community 541 - "DisclosureLevel"
Cohesion: 0.50
Nodes (3): DisclosureLevel, ResourceDirName, Create a new Skill at a different disclosure level.          Args:             l

### Community 542 - "allOf"
Cohesion: 0.50
Nodes (4): allOf, type, unevaluatedProperties, Button

### Community 543 - "allOf"
Cohesion: 0.50
Nodes (4): allOf, type, unevaluatedProperties, CheckBox

### Community 544 - "allOf"
Cohesion: 0.50
Nodes (4): allOf, type, unevaluatedProperties, ChoicePicker

### Community 545 - "allOf"
Cohesion: 0.50
Nodes (4): allOf, type, unevaluatedProperties, Column

### Community 546 - "DateTimeInput"
Cohesion: 0.50
Nodes (4): DateTimeInput, allOf, type, unevaluatedProperties

### Community 547 - "Divider"
Cohesion: 0.50
Nodes (4): Divider, allOf, type, unevaluatedProperties

### Community 548 - "Icon"
Cohesion: 0.50
Nodes (4): Icon, allOf, type, unevaluatedProperties

### Community 549 - "Image"
Cohesion: 0.50
Nodes (4): Image, allOf, type, unevaluatedProperties

### Community 550 - "List"
Cohesion: 0.50
Nodes (4): List, allOf, type, unevaluatedProperties

### Community 551 - "Modal"
Cohesion: 0.50
Nodes (4): Modal, allOf, type, unevaluatedProperties

### Community 552 - "Row"
Cohesion: 0.50
Nodes (4): Row, allOf, type, unevaluatedProperties

### Community 553 - "Slider"
Cohesion: 0.50
Nodes (4): Slider, allOf, type, unevaluatedProperties

### Community 554 - "Tabs"
Cohesion: 0.50
Nodes (4): Tabs, allOf, type, unevaluatedProperties

### Community 555 - "Text"
Cohesion: 0.50
Nodes (4): Text, allOf, type, unevaluatedProperties

### Community 556 - "TextField"
Cohesion: 0.50
Nodes (4): TextField, allOf, type, unevaluatedProperties

### Community 557 - "Video"
Cohesion: 0.50
Nodes (4): Video, allOf, type, unevaluatedProperties

### Community 558 - "description"
Cohesion: 0.50
Nodes (4): description, minimum, type, max

### Community 559 - "description"
Cohesion: 0.50
Nodes (4): description, minimum, type, min

### Community 560 - "url"
Cohesion: 0.50
Nodes (4): url, description, format, type

### Community 561 - "event_bus.py"
Cohesion: 0.50
Nodes (3): is_replaying(), Event bus for managing and dispatching events in CrewAI.  This module provides a, Return True if the current context is dispatching a replayed event.      Listene

### Community 562 - "testing.py"
Cohesion: 0.83
Nodes (3): assert_experiment_no_regression(), assert_experiment_successfully(), _get_baseline_filepath_fallback()

### Community 563 - "TypedDict"
Cohesion: 0.50
Nodes (3): TypedDict, Return metadata for every cached skill., SkillMetadata

### Community 564 - "_start.py"
Cohesion: 0.50
Nodes (3): FlowTrigger, Marks a method as a flow's starting point.      This decorator designates a meth, start()

### Community 567 - "._add_property_ordering()"
Cohesion: 0.50
Nodes (3): Add propertyOrdering to JSON schema for Gemini 2.0 compatibility.          Gemin, Test that _add_property_ordering correctly adds propertyOrdering to schemas., test_add_property_ordering_to_schema()

### Community 568 - "__init__.py"
Cohesion: 0.50
Nodes (3): __getattr__(), Any, MCP (Model Context Protocol) client support for CrewAI agents.  This module prov

### Community 569 - "_map_task_variables()"
Cohesion: 0.50
Nodes (4): _map_task_variables(), Resolve and map variables for a single task.      Args:         self: Crew insta, Type definition for task configuration dictionary.      All fields are optional, TaskConfig

### Community 570 - ".__init__()"
Cohesion: 0.50
Nodes (3): ChromaDBClientType, ChromaEmbeddingFunction, Initialize ChromaDBClient with client and embedding function.          Args:

### Community 571 - "Documents"
Cohesion: 0.50
Nodes (3): Documents, Embeddings, Generate embeddings for input documents.          Args:             input: List

### Community 572 - "Test that the LLM factory pass"
Cohesion: 0.50
Nodes (3): Test that the LLM factory passes api='responses' through to AzureCompletion., LLM(model='azure/gpt-4o', api='responses') should create AzureCompletion, TestAzureResponsesViaLLMFactory

### Community 573 - "Test compaction triggered via "
Cohesion: 0.50
Nodes (3): Test compaction triggered via Crew.kickoff() with small context window., Test that compaction is triggered during kickoff with small context_window_size., TestCrewKickoffCompaction

### Community 574 - "Test compaction triggered via "
Cohesion: 0.50
Nodes (3): Test compaction triggered via Agent.execute_task()., Test that Agent.execute_task() works with small context_window_size., TestAgentExecuteTaskCompaction

### Community 586 - "DynamicBoolean"
Cohesion: 0.67
Nodes (3): DynamicBoolean, description, oneOf

### Community 587 - "DynamicString"
Cohesion: 0.67
Nodes (3): DynamicString, description, oneOf

### Community 595 - "_checkpoint_chain_flow()"
Cohesion: 0.67
Nodes (3): _checkpoint_chain_flow(), test_fork_with_definition_branches_yaml_flow(), test_from_checkpoint_with_definition_restores_yaml_flow()

## Knowledge Gaps
- **361 isolated node(s):** `crewai`, `$schema`, `$id`, `title`, `description` (+356 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **169 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `LLM` connect `._collapse_to_outcome()` to `.message()`, `._build_execution_prompt()`, `PollingHandler`, `Printer`, `trace_batch_manager.py`, `.create_agent_executor()`, `Agent`, `Connection`, `_RouteT`, `FlowMethodName`, `test_openai.py`, `.aexecute_task()`, `.get_delegation_tools()`, `_human_feedback.py`, `llm_events.py`, `Json`, `conversational.py`, `BetaMessage`, `._rebind_memory_view()`, `test_azure.py`, `test_multimodal_integration.py`, `_asummarize_chunks()`, `InferenceConfigurationTypeDef`, `.post_init_setup()`, `test_crew_multimodal.py`, `test_anthropic.py`, `ContextT`, `ChatCompletionDeltaToolCall`, `test_agent_multimodal.py`, `test_multimodal.py`, `test_bedrock.py`, `Test that the LLM factory pass`, `Test compaction triggered via `, `Test compaction triggered via `, `convert_to_model()`, `convert_tools_to_openai_schema`, `LLMGuardrailCompletedEvent`, `test_anthropic_interceptor.py`, `AfterToolCallHookCallable`, `Event`, `_kickoff_with_a2a_support()`, `completion.py`, `test_openai_interceptor.py`, `test_unsupported_providers.py`, `base_agent_adapter.py`, `reasoning_events.py`, `.usage_metrics()`, `test_task_guardrails.py`, `._setup_executor()`, `GeminiCompletion`, `test_azure_responses.py`, `converter.py`, `test_tool_call_streaming.py`, `test_human_feedback_integratio`, `CrewAIEventsBus`, `test_project.py`, `_ConversationalMixin`, `get_before_llm_call_hooks()`, `call_stop_override()`, `OpenAICompatibleCompletion`, `llm_guardrail_events.py`, `test_agent_reasoning.py`, `test_structured_planning.py`, `COMPONENTS`, `create_default_evaluator()`, `EvaluationScore`, `CalculatorTool`, `base_agent.py`, `test_google.py`, `PlanStep`, `test_crew_thread_safety.py`, `Tests for the FUNCTION_SCHEMA `, `test_litellm_async.py`, `test_openai_async.py`, `completion.py`, `Tests for LLM factory integrat`, `test_flow_crew_span_integratio`, `internal_instructor.py`, `test_azure_async.py`, `test_bedrock_async.py`, `test_google_async.py`, `Tests for the OPENAI_COMPATIBL`, `goal_metrics.py`, `base_output_converter.py`, `._has_custom_openai_base_url()`, `constants.py`, `Any`, `_normalize_ollama_base_url()`, `parse_tool_call_args()`, `Tests for async method support`, `Unit tests with mocked LLM pro`, `Test that invalid JSON falls b`, `Tests for AgentReasoning with `, `BaseModel`, `test_llm_streaming_finish_reas`, `test_openai_compatible.py`, `Integration tests with real LL`?**
  _High betweenness centrality (0.176) - this node is a cross-community bridge._
- **Why does `Crew` connect `.message()` to `._build_execution_prompt()`, `PollingHandler`, `RootModel`, `.create_agent_executor()`, `Agent`, `._collapse_to_outcome()`, `.aexecute_task()`, `.fingerprint()`, `.get_delegation_tools()`, `Json`, `BaseAgentExecutor`, `AbstractEventLoop`, `._rebind_memory_view()`, `.post_init_setup()`, `dtype`, `test_crew_multimodal.py`, `Panel`, `A2AServerConfig`, `.aquery_knowledge()`, `._register_handlers()`, `Test compaction triggered via `, `Test compaction triggered via `, `memory_scope.py`, `test_trace_enable_disable.py`, `AvailableExport`, `AfterToolCallHookCallable`, `human_input.py`, `Any`, `Event`, `.from_function()`, `CrewOutput`, `.usage_metrics()`, `._handle_crew_planning()`, `.fetch_inputs()`, `._set_tasks_callbacks()`, `._aexecute_tasks()`, `Reset the emission sequence co`, `read_file_tool.py`, `._get_memory_systems()`, `Self`, `Any`, `Event emitted when a task eval`, `result.py`, `test_project.py`, `.list_categories()`, `test_async_crew.py`, `._setup_agent_executor()`, `.search()`, `AgentEvaluationCompletedEvent`, `crew_evaluator_handler.py`, `CalculatorTool`, `test_google.py`, `test_crew_thread_safety.py`, `CodeExecutorTool`, `._add_file_tools()`, `ModelWrapValidatorHandler`, `._training_handler()`, `.create_crew_memory()`, `lite_agent_output.py`, `MonkeyPatch`, `test_streaming_integration.py`, `SkillModel`, `.check_config()`, `.uuid_str()`, `test_google_vertex_memory_inte`, `AsyncCodeExecutorTool`, `.validate_and_set_attributes()`, `crew_loader.py`, `file_handler.py`, `process.py`, `test_execution_span_assignment`, `Tests for async method support`, `._run()`, `OTLPSpanExporter`, `Any`, `Regression tests for EPD-179: `, `PrinterColor`, `Tests for args_schema validati`, `._get_context()`, `flow_trackable.py`, `Test implementation with a syn`, `Tests for args_schema validati`, `Integration tests with real LL`?**
  _High betweenness centrality (0.131) - this node is a cross-community bridge._
- **Why does `Agent` connect `Agent` to `.message()`, `._build_execution_prompt()`, `PollingHandler`, `Printer`, `._cleanup_mcp_clients()`, `RootModel`, `.create_agent_executor()`, `FlowTrigger`, `_RouteT`, `._collapse_to_outcome()`, `test_openai.py`, `.aexecute_task()`, `.fingerprint()`, `.get_delegation_tools()`, `conversational.py`, `AbstractEventLoop`, `._rebind_memory_view()`, `test_azure.py`, `InferenceConfigurationTypeDef`, `.post_init_setup()`, `Artifact`, `dtype`, `test_crew_multimodal.py`, `test_anthropic.py`, `A2AClientConfig`, `ChatCompletionDeltaToolCall`, `A2AServerConfig`, `test_agent_multimodal.py`, `test_bedrock.py`, `_map_task_variables()`, `A2UIAnyMessageDict`, `_AgentDefinitionLoader`, `._register_handlers()`, `Test compaction triggered via `, `Test compaction triggered via `, `convert_to_model()`, `test_trace_enable_disable.py`, `LLMGuardrailCompletedEvent`, `AfterToolCallHookCallable`, `.get_output_converter()`, `human_input.py`, `Any`, `output_format.py`, `.from_function()`, `.usage_metrics()`, `._handle_crew_planning()`, `test_task_guardrails.py`, `NoReturn`, `._aexecute_tasks()`, `HTTPTransport`, `converter.py`, `base.py`, `Event emitted when a task eval`, `result.py`, `tool_resolver.py`, `test_project.py`, `._is_any_available_memory()`, `test_async_crew.py`, `._setup_agent_executor()`, `rw_lock.py`, `test_agent_a2a_kickoff.py`, `AgentEvaluationCompletedEvent`, `test_agent_reasoning.py`, `test_structured_planning.py`, `COMPONENTS`, `create_default_evaluator()`, `crew_evaluator_handler.py`, `CalculatorTool`, `base_agent.py`, `test_google.py`, `test_crew_thread_safety.py`, `Serialize a single guardrail v`, `test_amp_mcp.py`, `ModelWrapValidatorHandler`, `._training_handler()`, `lite_agent_output.py`, `MonkeyPatch`, `test_streaming_integration.py`, `SkillModel`, `.ensure_guardrail_is_callable(`, `.check_config()`, `internal_instructor.py`, `_FixedUsageLLM`, `test_google_vertex_memory_inte`, `goal_metrics.py`, `process.py`, `test_agent_a2a_wrapping.py`, `test_execution_span_assignment`, `Tests for async method support`, `extract_json_from_llm_response`, `Tests for _resolve_external wi`, `test_tool_resolver_native.py`, `test_agent_inject_date.py`, `._parse_amp_ref()`, `handle_partial_json()`, `test_markdown_task.py`, `._check_execution_error()`, `.get_multimodal_tools()`, `test_callback_with_taskoutput.`, `Integration tests with real LL`?**
  _High betweenness centrality (0.107) - this node is a cross-community bridge._
- **Are the 807 inferred relationships involving `LLM` (e.g. with `BaseAgent` and `_validate_llm_ref()`) actually correct?**
  _`LLM` has 807 INFERRED edges - model-reasoned connections that need verification._
- **Are the 559 inferred relationships involving `Agent` (e.g. with `A2UIClientExtension` and `A2UIConversationState`) actually correct?**
  _`Agent` has 559 INFERRED edges - model-reasoned connections that need verification._
- **Are the 453 inferred relationships involving `Crew` (e.g. with `Agent` and `.message()`) actually correct?**
  _`Crew` has 453 INFERRED edges - model-reasoned connections that need verification._
- **Are the 423 inferred relationships involving `Task` (e.g. with `_execute_impl()` and `_kickoff_with_a2a_support()`) actually correct?**
  _`Task` has 423 INFERRED edges - model-reasoned connections that need verification._