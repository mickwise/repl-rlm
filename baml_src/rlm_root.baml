/// =============================================================================
/// rlm_root.baml
///
/// Purpose
/// -------
/// Defines the root LLM contract for one turn of the RLM controller loop.
/// This module accepts the current task context, available runtime surface,
/// prior observations, and DSL guidance, then returns exactly one next action.
///
/// Key behaviors
/// -------------
/// - Accepts text, attachment metadata, current binding snapshots, and prior
///   execution observations for the active RLM session.
/// - Returns one structured next-turn decision: run one DSL program, answer
///   finally, or ask for clarification.
/// - Uses a typed tagged-node mirror of the current REPL expression and step
///   AST so host code can translate planner output into executable runtime
///   structures.
/// - Does NOT execute tools, mutate host state, or invent runtime results.
///
/// Conventions
/// -----------
/// - Output must be strictly machine-parseable and conform to schema.
/// - The planner should emit one bounded next action per turn.
/// - Concurrency should be used only when clearly beneficial and supported by
///   the current task decomposition.
/// - Recursive child calls should be used only for narrower scoped subproblems,
///   not as a default replacement for ordinary control flow.
///
/// Downstream usage
/// ----------------
/// The host RLM loop should call PlanRlmRootTurn(...), inspect the returned
/// RootRlmResponse, either execute the emitted program through the REPL runtime
/// or surface the final answer / clarification, then feed the resulting
/// observation back into the next loop iteration.
///
/// Notes
/// -----
/// - This module intentionally defines a stable control protocol shared across
///   tasks rather than a new schema per task.
/// - Task-specific extraction schemas should live in separate subcall modules
///   and not change this root-turn contract.
///
/// =============================================================================


enum RootDecisionKind {
  /// RootDecisionKind
  ///
  /// Purpose
  /// -------
  /// Represents the top-level action chosen by the root RLM planner for the
  /// current loop iteration.
  ///
  /// Fields
  /// ------
  /// - RUN_PROGRAM: emit one executable DSL program for the host runtime.
  /// - FINAL_ANSWER: emit a final user-facing answer and stop the loop.
  /// - CLARIFICATION: emit a follow-up question and pause execution.
  ///
  /// Invariants
  /// ----------
  /// - Exactly one decision kind must apply per response.
  ///
  /// Notes
  /// -----
  /// Host code should enforce that only the fields relevant to the selected
  /// decision kind are consumed.

  RUN_PROGRAM @description("Emit one executable DSL program for this turn")
  FINAL_ANSWER @description("Return a final user-facing answer and stop")
  CLARIFICATION @description("Ask a follow-up question before proceeding")
}


enum ObservationKind {
  /// ObservationKind
  ///
  /// Purpose
  /// -------
  /// Categorizes the observation records fed back from host execution into the
  /// next RLM planning turn.
  ///
  /// Fields
  /// ------
  /// - PROGRAM_RESULT: a program ran and produced a normal execution summary.
  /// - VALIDATION_ERROR: the emitted program failed structural validation.
  /// - EXECUTION_ERROR: the emitted program failed during runtime execution.
  /// - HOST_NOTE: host runtime supplied an informational note outside direct
  ///   program execution.
  ///
  /// Invariants
  /// ----------
  /// - Observation kind should match the fields populated in the observation
  ///   payload.
  ///
  /// Notes
  /// -----
  /// This enum keeps planner feedback explicit and machine-readable.

  PROGRAM_RESULT @description("Program executed and produced a normal result summary")
  VALIDATION_ERROR @description("Program failed structural validation before execution")
  EXECUTION_ERROR @description("Program failed during runtime execution")
  HOST_NOTE @description("Informational host note outside direct execution")
}


enum ComparisonOperator {
  /// ComparisonOperator
  ///
  /// Purpose
  /// -------
  /// Enumerates the legal comparison operators for comparison expressions in
  /// the REPL DSL mirror.
  ///
  /// Fields
  /// ------
  /// - GREATER_THAN: ">"
  /// - GREATER_THAN_OR_EQUAL: ">="
  /// - EQUAL: "=="
  /// - LESS_THAN_OR_EQUAL: "<="
  /// - LESS_THAN: "<"
  /// - NOT_EQUAL: "!="
  ///
  /// Invariants
  /// ----------
  /// - Only these operators may appear in a comparison expression node.
  ///
  /// Notes
  /// -----
  /// Host code is responsible for mapping these variants into runtime operator
  /// enums.

  GREATER_THAN @description("Strictly greater-than comparison")
  GREATER_THAN_OR_EQUAL @description("Greater-than-or-equal comparison")
  EQUAL @description("Equality comparison")
  LESS_THAN_OR_EQUAL @description("Less-than-or-equal comparison")
  LESS_THAN @description("Strictly less-than comparison")
  NOT_EQUAL @description("Inequality comparison")
}


enum LogicalOperator {
  /// LogicalOperator
  ///
  /// Purpose
  /// -------
  /// Enumerates the legal logical operators for logical expressions in the
  /// REPL DSL mirror.
  ///
  /// Fields
  /// ------
  /// - AND: logical conjunction.
  /// - OR: logical disjunction.
  ///
  /// Invariants
  /// ----------
  /// - Only these operators may appear in a logical expression node.
  ///
  /// Notes
  /// -----
  /// Host code is responsible for mapping these variants into runtime operator
  /// enums.

  AND @description("Logical conjunction")
  OR @description("Logical disjunction")
}


enum UnaryOperator {
  /// UnaryOperator
  ///
  /// Purpose
  /// -------
  /// Enumerates the legal unary operators for unary expressions in the REPL
  /// DSL mirror.
  ///
  /// Fields
  /// ------
  /// - MINUS: numeric negation.
  /// - NOT: logical negation.
  ///
  /// Invariants
  /// ----------
  /// - Only these operators may appear in a unary expression node.
  ///
  /// Notes
  /// -----
  /// Host code is responsible for mapping these variants into runtime operator
  /// enums.

  MINUS @description("Numeric negation")
  NOT @description("Logical negation")
}


enum ExprKind {
  /// ExprKind
  ///
  /// Purpose
  /// -------
  /// Tags the concrete expression variant carried by an ExprNode.
  ///
  /// Fields
  /// ------
  /// - LITERAL: atomic literal value.
  /// - REF: runtime binding reference.
  /// - TASK_REF: runtime task-handle reference.
  /// - OBJECT: structured object expression.
  /// - LIST: ordered list expression.
  /// - COMPARISON: binary comparison expression.
  /// - LOGICAL: binary logical expression.
  /// - UNARY: unary expression.
  ///
  /// Invariants
  /// ----------
  /// - expr_kind determines which optional fields on ExprNode should be set.
  ///
  /// Notes
  /// -----
  /// Host code should validate that each ExprNode uses fields consistent with
  /// its selected kind.

  LITERAL @description("Atomic literal value expression")
  REF @description("Runtime binding reference expression")
  TASK_REF @description("Spawned task-handle reference expression")
  OBJECT @description("Structured object expression")
  LIST @description("Ordered list expression")
  COMPARISON @description("Binary comparison expression")
  LOGICAL @description("Binary logical expression")
  UNARY @description("Unary operator expression")
}


enum StepKind {
  /// StepKind
  ///
  /// Purpose
  /// -------
  /// Tags the concrete step variant carried by a StepNode.
  ///
  /// Fields
  /// ------
  /// - TOOL_CALL: deterministic tool invocation.
  /// - IF: conditional control flow.
  /// - FOREACH: bounded iteration.
  /// - RETURN: explicit return from current program.
  /// - LLM_CALL: plain LLM-backed value call.
  /// - RECURSIVE_CALL: recursive child-program generation and execution.
  /// - ASSIGNMENT: binding assignment.
  /// - SPAWN: concurrent child-program spawn.
  /// - JOIN: synchronization over spawned tasks.
  ///
  /// Invariants
  /// ----------
  /// - step_kind determines which optional fields on StepNode should be set.
  ///
  /// Notes
  /// -----
  /// Host code should validate that each StepNode uses fields consistent with
  /// its selected kind.

  TOOL_CALL @description("Deterministic tool invocation step")
  IF @description("Conditional branch step")
  FOREACH @description("Bounded iteration step")
  RETURN @description("Explicit program return step")
  LLM_CALL @description("LLM-backed value call step")
  RECURSIVE_CALL @description("Recursive child-program generation step")
  ASSIGNMENT @description("Binding assignment step")
  SPAWN @description("Concurrent child-program spawn step")
  JOIN @description("Synchronization over spawned tasks")
}


class AttachmentInput {
  /// AttachmentInput
  ///
  /// Purpose
  /// -------
  /// Represents one task-relevant attachment available to the root planner for
  /// the current turn.
  ///
  /// Fields
  /// ------
  /// - attachment_name: original filename or host-generated attachment label.
  /// - mime_type: MIME type if known.
  /// - source_ref: host-visible reference such as a URL, local path, or opaque
  ///   attachment handle.
  /// - summary: optional host-provided summary or extracted preview.
  ///
  /// Invariants
  /// ----------
  /// - source_ref should be non-empty when an attachment exists.
  ///
  /// Notes
  /// -----
  /// The planner may use attachment metadata to decide whether to call
  /// ingestion or parsing tools rather than reading raw file bytes directly.

  attachment_name string @description("Original filename or attachment label")
  mime_type string? @description("Attachment MIME type if known")
  source_ref string @description("Host-visible attachment reference or handle")
  summary string? @description("Optional host-provided summary or preview")
}


class BindingSnapshot {
  /// BindingSnapshot
  ///
  /// Purpose
  /// -------
  /// Represents one current runtime binding summarized for planner
  /// consumption.
  ///
  /// Fields
  /// ------
  /// - binding_name: runtime binding name currently available.
  /// - value_summary: host-generated compact summary of the current value.
  ///
  /// Invariants
  /// ----------
  /// - value_summary should be descriptive enough to support planning without
  ///   dumping unbounded runtime state.
  ///
  /// Notes
  /// -----
  /// This is a summary surface for planning, not a lossless serialization of
  /// runtime values.

  binding_name string @description("Name of a runtime binding currently available")
  value_summary string @description("Compact host summary of the binding value")
}


class ToolDescriptor {
  /// ToolDescriptor
  ///
  /// Purpose
  /// -------
  /// Describes one deterministic host tool available to the REPL runtime.
  ///
  /// Fields
  /// ------
  /// - tool_name: registry-visible tool name.
  /// - description: concise description of behavior and intended use.
  /// - argument_contract: optional summary of accepted structured arguments.
  ///
  /// Invariants
  /// ----------
  /// - tool_name should match the actual runtime registry key used by host
  ///   execution.
  ///
  /// Notes
  /// -----
  /// The planner should rely on these descriptors instead of inventing tool
  /// names or argument shapes.

  tool_name string @description("Runtime registry name of the tool")
  description string @description("Concise description of tool behavior")
  argument_contract string? @description("Optional summary of accepted structured arguments")
}


class LlmFunctionDescriptor {
  /// LlmFunctionDescriptor
  ///
  /// Purpose
  /// -------
  /// Describes one registered LLM-backed function available to the REPL
  /// runtime.
  ///
  /// Fields
  /// ------
  /// - function_name: registry-visible BAML function name.
  /// - description: concise description of the function's purpose.
  /// - argument_contract: optional summary of accepted structured arguments.
  /// - returns_child_program: true when this function is intended for
  ///   RecursiveCallStep use and should return a child program.
  ///
  /// Invariants
  /// ----------
  /// - returns_child_program should be true only for functions that the host
  ///   runtime can safely use for recursive child-program generation.
  ///
  /// Notes
  /// -----
  /// This descriptor lets the root planner distinguish plain model-backed
  /// value calls from recursive subprogram generators.

  function_name string @description("Runtime registry name of the LLM function")
  description string @description("Concise description of the function purpose")
  argument_contract string? @description("Optional summary of accepted structured arguments")
  returns_child_program bool @description("Whether the function returns a child program")
}


class RuntimeBudgetSnapshot {
  /// RuntimeBudgetSnapshot
  ///
  /// Purpose
  /// -------
  /// Captures the current recursion and iteration budget visible to the root
  /// planner.
  ///
  /// Fields
  /// ------
  /// - current_recursive_depth: current runtime recursive depth.
  /// - max_recursive_depth: configured maximum recursive depth.
  /// - recursive_calls_used: total recursive calls already consumed.
  /// - max_recursive_calls: configured maximum recursive calls allowed.
  /// - iteration_index: current outer-loop iteration index.
  /// - max_iterations: maximum outer-loop iterations allowed.
  ///
  /// Invariants
  /// ----------
  /// - Used values should never exceed configured maximums in normal host
  ///   operation.
  ///
  /// Notes
  /// -----
  /// This snapshot helps the planner choose bounded next actions and avoid
  /// wasteful recursion.

  current_recursive_depth int @description("Current recursive depth in the runtime")
  max_recursive_depth int @description("Configured maximum recursive depth")
  recursive_calls_used int @description("Total recursive calls already consumed")
  max_recursive_calls int @description("Configured maximum recursive calls allowed")
  iteration_index int @description("Current outer-loop iteration index")
  max_iterations int @description("Maximum outer-loop iterations allowed")
}


class RootObservation {
  /// RootObservation
  ///
  /// Purpose
  /// -------
  /// Represents one host-generated observation fed back into the next root RLM
  /// planning turn.
  ///
  /// Fields
  /// ------
  /// - observation_kind: category of the observation.
  /// - summary: compact natural-language or structured summary of what
  ///   happened.
  /// - error_code: optional native runtime error code when execution failed.
  /// - error_message: optional native runtime error message when execution
  ///   failed.
  /// - did_return: optional flag indicating whether a program terminated via
  ///   return.
  /// - return_value_summary: optional compact summary of the returned value.
  /// - changed_bindings: optional list of updated bindings after execution.
  /// - active_task_names: optional list of task-handle names still active after
  ///   execution.
  ///
  /// Invariants
  /// ----------
  /// - error_code and error_message should be populated together for error
  ///   observations.
  ///
  /// Notes
  /// -----
  /// Host code should keep this object compact and planner-useful rather than
  /// dumping full runtime state or large documents back into context.

  observation_kind ObservationKind @description("Category of the host observation")
  summary string @description("Compact summary of what happened")
  error_code string? @description("Native runtime error code when execution failed")
  error_message string? @description("Native runtime error message when execution failed")
  did_return bool? @description("Whether the program terminated via return")
  return_value_summary string? @description("Compact summary of the returned value")
  changed_bindings BindingSnapshot[]? @description("Updated bindings after execution")
  active_task_names string[]? @description("Spawned task handles still active after execution")
}


class ProgramMetadataEntry {
  /// ProgramMetadataEntry
  ///
  /// Purpose
  /// -------
  /// Represents one lightweight metadata key/value pair attached to an emitted
  /// RLM program.
  ///
  /// Fields
  /// ------
  /// - key: metadata key name.
  /// - value: metadata value as a compact string.
  ///
  /// Invariants
  /// ----------
  /// - Metadata should remain lightweight and should not duplicate full task
  ///   context.
  ///
  /// Notes
  /// -----
  /// This mirrors the host runtime's program metadata in a bounded form that is
  /// easy for the planner to emit reliably.

  key string @description("Metadata key name")
  value string @description("Compact metadata value")
}


class ObjectField {
  /// ObjectField
  ///
  /// Purpose
  /// -------
  /// Represents one named field within a structured object expression.
  ///
  /// Fields
  /// ------
  /// - field_name: field key name.
  /// - value_expr: nested expression for the field value.
  ///
  /// Invariants
  /// ----------
  /// - Field names should be unique within the containing object.
  ///
  /// Notes
  /// -----
  /// This helper type exists because the root BAML contract uses tagged nodes
  /// instead of recursive union aliases.

  field_name string @description("Object field key name")
  value_expr ExprNode @description("Expression for the field value")
}


class LiteralValue {
  /// LiteralValue
  ///
  /// Purpose
  /// -------
  /// Represents one atomic literal value carried by a literal expression node.
  ///
  /// Fields
  /// ------
  /// - string_value: string literal, if present.
  /// - int_value: integer literal, if present.
  /// - float_value: floating-point literal, if present.
  /// - bool_value: boolean literal, if present.
  /// - is_null: true when the literal value is null.
  ///
  /// Invariants
  /// ----------
  /// - Exactly one of string_value, int_value, float_value, bool_value, or
  ///   is_null=true should represent the active literal payload.
  ///
  /// Notes
  /// -----
  /// Host code should validate that the emitted literal is unambiguous before
  /// converting it into the runtime Literal node.

  string_value string? @description("String literal payload if present")
  int_value int? @description("Integer literal payload if present")
  float_value float? @description("Floating-point literal payload if present")
  bool_value bool? @description("Boolean literal payload if present")
  is_null bool @description("True when the literal value is null")
}


class ExprNode {
  /// ExprNode
  ///
  /// Purpose
  /// -------
  /// Represents one tagged expression node in the root planner's BAML mirror
  /// of the REPL DSL.
  ///
  /// Fields
  /// ------
  /// - expr_kind: concrete expression variant tag.
  /// - literal_value: payload for literal expressions.
  /// - ref_name: binding name for REF expressions.
  /// - task_ref_name: task-handle name for TASK_REF expressions.
  /// - object_fields: named field list for OBJECT expressions.
  /// - list_values: ordered element list for LIST expressions.
  /// - lhs_expr: left-hand operand for COMPARISON and LOGICAL expressions.
  /// - rhs_expr: right-hand operand for COMPARISON and LOGICAL expressions.
  /// - comparison_operator: operator for COMPARISON expressions.
  /// - logical_operator: operator for LOGICAL expressions.
  /// - unary_operator: operator for UNARY expressions.
  /// - operand_expr: operand for UNARY expressions.
  ///
  /// Invariants
  /// ----------
  /// - expr_kind determines which payload fields should be populated.
  ///
  /// Notes
  /// -----
  /// Host code should validate consistency between expr_kind and populated
  /// fields before translating to the Python AST.

  expr_kind ExprKind @description("Tag naming the concrete expression variant")
  literal_value LiteralValue? @description("Payload for literal expressions")
  ref_name string? @description("Binding name for REF expressions")
  task_ref_name string? @description("Task-handle name for TASK_REF expressions")
  object_fields ObjectField[]? @description("Named fields for OBJECT expressions")
  list_values ExprNode[]? @description("Ordered elements for LIST expressions")
  lhs_expr ExprNode? @description("Left operand for comparison or logical expressions")
  rhs_expr ExprNode? @description("Right operand for comparison or logical expressions")
  comparison_operator ComparisonOperator? @description("Operator for COMPARISON expressions")
  logical_operator LogicalOperator? @description("Operator for LOGICAL expressions")
  unary_operator UnaryOperator? @description("Operator for UNARY expressions")
  operand_expr ExprNode? @description("Operand for UNARY expressions")
}


class StepNode {
  /// StepNode
  ///
  /// Purpose
  /// -------
  /// Represents one tagged executable step node in the root planner's BAML
  /// mirror of the REPL DSL.
  ///
  /// Fields
  /// ------
  /// - step_kind: concrete step variant tag.
  /// - tool_name: tool registry key for TOOL_CALL steps.
  /// - args_object: structured argument object for TOOL_CALL, LLM_CALL, and
  ///   RECURSIVE_CALL steps.
  /// - binding_target: destination binding for result-producing steps.
  /// - condition_expr: condition for IF steps.
  /// - then_steps: true branch body for IF steps.
  /// - else_steps: false branch body for IF steps.
  /// - iterable_expr: iterable expression for FOREACH steps.
  /// - loop_var_name: loop variable name for FOREACH steps.
  /// - body_steps: loop body for FOREACH steps.
  /// - value_expr: returned or assigned expression for RETURN and ASSIGNMENT
  ///   steps.
  /// - baml_func_name: LLM function name for LLM_CALL and RECURSIVE_CALL steps.
  /// - sub_program: child program for SPAWN steps.
  /// - join_task_ref_names: task-handle names for JOIN steps.
  ///
  /// Invariants
  /// ----------
  /// - step_kind determines which payload fields should be populated.
  ///
  /// Notes
  /// -----
  /// Host code should validate consistency between step_kind and populated
  /// fields before translating to the Python AST.

  step_kind StepKind @description("Tag naming the concrete step variant")
  tool_name string? @description("Tool registry key for TOOL_CALL steps")
  args_object ObjectField[]? @description("Structured argument object for call steps")
  binding_target string? @description("Binding that should receive the step result")
  condition_expr ExprNode? @description("Condition expression for IF steps")
  then_steps StepNode[]? @description("Steps to run when the IF condition is true")
  else_steps StepNode[]? @description("Steps to run when the IF condition is false")
  iterable_expr ExprNode? @description("Iterable expression for FOREACH steps")
  loop_var_name string? @description("Loop variable name for FOREACH steps")
  body_steps StepNode[]? @description("Body steps for FOREACH steps")
  value_expr ExprNode? @description("Expression used by RETURN or ASSIGNMENT steps")
  baml_func_name string? @description("LLM function name for LLM or recursive calls")
  sub_program RlmProgram? @description("Child program to spawn concurrently")
  join_task_ref_names string[]? @description("Task-handle names to join")
}


class RlmProgram {
  /// RlmProgram
  ///
  /// Purpose
  /// -------
  /// Represents the top-level executable REPL program emitted by the root
  /// planner.
  ///
  /// Fields
  /// ------
  /// - steps: ordered executable step list.
  /// - metadata: optional lightweight metadata entries for tracing or planner
  ///   annotations.
  ///
  /// Invariants
  /// ----------
  /// - steps should be emitted in execution order.
  ///
  /// Notes
  /// -----
  /// Metadata is intentionally lightweight here and should stay compact.

  steps StepNode[] @description("Ordered executable step list")
  metadata ProgramMetadataEntry[]? @description("Optional lightweight planner metadata")
}


class RootRlmRequest {
  /// RootRlmRequest
  ///
  /// Purpose
  /// -------
  /// Represents the full planner-visible state for one root RLM loop turn.
  ///
  /// Fields
  /// ------
  /// - user_text: raw user task text for the current session or turn.
  /// - attachments: task-relevant attachment metadata and references.
  /// - current_bindings: compact summaries of bindings currently visible to the
  ///   runtime.
  /// - observation_history: compact host-generated observations from earlier
  ///   loop iterations.
  /// - available_tools: deterministic host tools available to the emitted
  ///   program.
  /// - available_llm_functions: registered LLM-backed functions available to
  ///   the emitted program.
  /// - dsl_summary: concise explanation of the REPL language surface and usage
  ///   constraints.
  /// - planner_instructions: optional host-provided extra instructions for this
  ///   run.
  /// - budget: current iteration and recursion budget snapshot.
  ///
  /// Invariants
  /// ----------
  /// - The request should contain enough information for the planner to choose
  ///   one bounded next action without inventing unavailable tools or bindings.
  ///
  /// Notes
  /// -----
  /// Host code is responsible for keeping this request compact and relevant.

  user_text string? @description("Raw user task text for the current session or turn")
  attachments AttachmentInput[] @description("Task-relevant attachment metadata and references")
  current_bindings BindingSnapshot[] @description("Compact summaries of current runtime bindings")
  observation_history RootObservation[] @description("Prior host observations from earlier loop iterations")
  available_tools ToolDescriptor[] @description("Deterministic host tools available to the program")
  available_llm_functions LlmFunctionDescriptor[] @description("Registered LLM-backed functions available to the program")
  dsl_summary string @description("Concise summary of the REPL DSL surface and constraints")
  planner_instructions string? @description("Optional extra host instructions for this run")
  budget RuntimeBudgetSnapshot @description("Current iteration and recursion budget snapshot")
}


class RootRlmResponse {
  /// RootRlmResponse
  ///
  /// Purpose
  /// -------
  /// Represents the root planner's next-turn decision for the RLM controller
  /// loop.
  ///
  /// Fields
  /// ------
  /// - decision_kind: top-level planner choice for this turn.
  /// - program: emitted program when decision_kind=RUN_PROGRAM.
  /// - final_answer: final user-facing answer when decision_kind=FINAL_ANSWER.
  /// - clarification_question: follow-up question when
  ///   decision_kind=CLARIFICATION.
  /// - planner_notes: optional compact planner note for host logs or tracing.
  ///
  /// Invariants
  /// ----------
  /// - RUN_PROGRAM requires program.
  /// - FINAL_ANSWER requires final_answer.
  /// - CLARIFICATION requires clarification_question.
  ///
  /// Notes
  /// -----
  /// Host code should validate the selected branch before acting on the
  /// response.

  decision_kind RootDecisionKind @description("Top-level planner choice for this turn")
  program RlmProgram? @description("Program to run when decision_kind is RUN_PROGRAM")
  final_answer string? @description("Final user-facing answer when decision_kind is FINAL_ANSWER")
  clarification_question string? @description("Follow-up question when decision_kind is CLARIFICATION")
  planner_notes string? @description("Optional compact planner note for logs or tracing")
}


function PlanRlmRootTurn(
  request: RootRlmRequest
) -> RootRlmResponse {
  /// function PlanRlmRootTurn(request: RootRlmRequest) -> RootRlmResponse
  ///
  /// Summary
  /// -------
  /// Plans exactly one next root-turn action for the RLM controller loop.
  ///
  /// Inputs
  /// ------
  /// - request: full root-turn planning context including user task text,
  ///   attachments, runtime summaries, prior observations, available runtime
  ///   surface, DSL guidance, and current budgets.
  /// - If request.user_text is empty, the planner must rely on observations,
  ///   bindings, and planner instructions already present in the request.
  ///
  /// Output contract
  /// ---------------
  /// - Must output ONLY a RootRlmResponse (no prose).
  /// - Must follow schema exactly (use {{ ctx.output_format }}).
  /// - Must emit exactly one bounded next action for this turn.
  ///
  /// Failure / ambiguity policy
  /// --------------------------
  /// - If the task can be answered safely from current information, return
  ///   FINAL_ANSWER.
  /// - If essential information is missing and no safe next program can resolve
  ///   it, return CLARIFICATION.
  /// - Otherwise return RUN_PROGRAM with one executable bounded program.
  /// - Do not invent tools, LLM functions, bindings, attachment contents, or
  ///   runtime results that are not supported by the request.
  ///
  /// Notes
  /// -----
  /// - The host loop is responsible for executing emitted programs, collecting
  ///   observations, and deciding whether to continue or stop.
  /// - Concurrency should be encoded inside the emitted program only when it
  ///   clearly improves the plan.

  client CustomOllama
  prompt #"
    You are the root planner for a recursive-language-model REPL runtime.

    Your job is to decide the single next action for this turn.
    You do NOT execute tools.
    You do NOT fabricate runtime results.
    You do NOT mutate host state directly.
    You only return a RootRlmResponse.

    This controller loop is iterative. Prior observations may include successful
    program results, validation failures, execution failures, or host notes from
    earlier turns. Use those observations to decide the next bounded action.

    Hard rules
    ----------
    1. Return exactly one of:
    - RUN_PROGRAM
    - FINAL_ANSWER
    - CLARIFICATION
    2. If you return RUN_PROGRAM, emit one bounded executable RlmProgram.
    3. Use only tool names, LLM function names, binding names, task handles, and
    other runtime surface justified by the request context.
    4. Do not invent attachment contents, tool results, binding values, or runtime
    observations that are not present in the request.
    5. Prefer simple sequential programs unless concurrency is clearly beneficial.
    6. Use recursive child calls only for narrower scoped subproblems and only
    when decomposition is clearly justified.
    7. If the answer is already supported by current information, prefer
    FINAL_ANSWER over unnecessary extra work.
    8. If a safe next step is impossible without missing information, prefer
    CLARIFICATION over guessing.
    9. If prior observations contain a validation or execution error, treat that
    error as feedback on the previous program. Revise the next action
    accordingly instead of repeating the same failing structure.
    10. Prefer the smallest repair that resolves the observed failure while
        preserving useful prior work.
    11. If a prior failure shows that the current approach is invalid or
        unsupported, choose a different bounded next action rather than retrying
        blindly.

    Tagged-node construction rules
    ------------------------------
    1. ExprNode.expr_kind determines which ExprNode payload fields should be set.
    2. StepNode.step_kind determines which StepNode payload fields should be set.
    3. Leave irrelevant optional fields null.
    4. Keep programs compact, concrete, and execution-ready.
    5. If you spawn tasks, join them when their results are needed.
    6. If a result should become the program output, use an explicit RETURN step.
    7. Use only the runtime surface described in the request. Do not invent new
    tools, functions, bindings, or task handles.
    8. If tool or function discovery metadata is provided in the request, use it
    to choose available runtime actions rather than guessing names or argument
    contracts.

  Request
  -------
  {{ request }}

  DSL summary
  -----------
  {{ request.dsl_summary }}

  Return output in this exact schema:
  {{ ctx.output_format }}
  "#
}
