"""
Purpose
-------
Define the core abstract syntax tree node types for the restricted DSL used by
the online REPL runtime. This module exists to give planner output and
interpreter input a shared, explicit in-memory representation.

Key behaviors
-------------
- Defines immutable dataclass node types for executable steps and evaluatable
  expressions.
- Defines enum types for comparison, logical, and unary operators used inside
  expression nodes.
- Defines the `Step` and `Expr` type families that downstream validation and
  interpreter passes operate over.
- Defines the top-level `Program` container for ordered step execution.

Conventions
-----------
- AST nodes are immutable dataclasses and should be treated as structural
  program descriptions, not runtime objects with embedded execution logic.
- `Step` and `Expr` are sum-type aliases over concrete node classes.
- `ObjectExpr` fields and `Program.metadata` are typed as mappings and may be
  backed by concrete mapping implementations supplied by upstream code.
- Atomic literal values are restricted to `int`, `float`, `str`, `bool`, and
  `None`.
- This module does not perform validation, execution, name resolution, or
  side-effecting work.

Downstream usage
----------------
Planner or schema-boundary code should construct instances of these node types
to represent legal DSL programs. Validator, resolver, and interpreter modules
should consume these nodes directly and implement behavior as separate passes
over the tree.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias, Tuple, Mapping, Any
from enum import Enum

AtomicType: TypeAlias = int | float | str | bool | None

@dataclass(frozen=True)
class Literal:
    """
    Purpose
    -------
    Represent an atomic literal expression in the DSL. This node exists to
    embed directly written primitive values in the syntax tree.

    Key behaviors
    -------------
    - Stores an already-formed atomic literal value.
    - Evaluates directly to its stored value without further structural
      traversal.

    Parameters
    ----------
    value : AtomicType
        Atomic literal value carried by the node.

    Attributes
    ----------
    value : AtomicType
        Atomic literal value carried by the node.

    Notes
    -----
    - Literal values are restricted to the `AtomicType` alias.
    - Structured values should be represented using `ObjectExpr` or `ListExpr`
      instead of nested Python containers here.
    """
    value: AtomicType


@dataclass(frozen=True)
class Ref:
    """
    Purpose
    -------
    Represent a named reference expression in the DSL. This node exists to look
    up a previously bound value from runtime state by name.

    Key behaviors
    -------------
    - Stores the symbolic name of a binding to resolve at runtime.
    - Allows later steps and expressions to reuse previously produced values.

    Parameters
    ----------
    name : str
        Name of the binding to resolve from runtime state.

    Attributes
    ----------
    name : str
        Name of the binding to resolve from runtime state.

    Notes
    -----
    - Resolution semantics are handled by downstream runtime or validation
      passes.
    - This node does not itself guarantee that the referenced binding exists.
    """
    name: str


@dataclass(frozen=True)
class ObjectExpr:
    """
    Purpose
    -------
    Represent a structured object expression in the DSL. This node exists to
    build named-field structured values out of nested expressions.

    Key behaviors
    -------------
    - Stores a mapping from field names to expression nodes.
    - Allows downstream evaluation to recursively construct structured argument
      or result objects.

    Parameters
    ----------
    fields : Mapping[str, Expr]
        Mapping from field names to expression nodes.

    Attributes
    ----------
    fields : Mapping[str, Expr]
        Mapping from field names to expression nodes.

    Notes
    -----
    - Field values are expressions and may require recursive evaluation.
    - The mapping is typed abstractly as a `Mapping`; callers may supply any
      compatible mapping implementation.
    """
    fields: Mapping[str, Expr]


@dataclass(frozen=True)
class ListExpr:
    """
    Purpose
    -------
    Represent a list expression in the DSL. This node exists to build ordered
    structured values from nested expression elements.

    Key behaviors
    -------------
    - Stores an ordered tuple of expression nodes.
    - Allows downstream evaluation to recursively construct list values.

    Parameters
    ----------
    values : Tuple[Expr, ...]
        Ordered tuple of expression nodes forming the list.

    Attributes
    ----------
    values : Tuple[Expr, ...]
        Ordered tuple of expression nodes forming the list.

    Notes
    -----
    - Elements are expressions and may require recursive evaluation.
    - Tuple storage keeps the structural container immutable at the AST level.
    """
    values: Tuple[Expr, ...]


@dataclass(frozen=True)
class ComparisonExpr:
    """
    Purpose
    -------
    Represent a binary comparison expression in the DSL. This node exists to
    compare two operand expressions using a comparison operator.

    Key behaviors
    -------------
    - Stores left-hand and right-hand operand expressions.
    - Stores the comparison operator that determines the comparison performed.

    Parameters
    ----------
    lhs_expr : Expr
        Left-hand operand expression.
    rhs_expr : Expr
        Right-hand operand expression.
    operator : ComparisonOperator
        Comparison operator to apply to the evaluated operands.

    Attributes
    ----------
    lhs_expr : Expr
        Left-hand operand expression.
    rhs_expr : Expr
        Right-hand operand expression.
    operator : ComparisonOperator
        Comparison operator to apply to the evaluated operands.

    Notes
    -----
    - This node is structural only; operand evaluation and operator semantics
      are handled downstream.
    - The evaluated result is expected to be boolean-like.
    """
    lhs_expr: Expr
    rhs_expr: Expr
    operator: ComparisonOperator


@dataclass(frozen=True)
class LogicalExpr:
    """
    Purpose
    -------
    Represent a binary logical expression in the DSL. This node exists to
    combine two operand expressions using a logical operator.

    Key behaviors
    -------------
    - Stores left-hand and right-hand operand expressions.
    - Stores the logical operator that determines how the evaluated operands
      are combined.

    Parameters
    ----------
    lhs_expr : Expr
        Left-hand operand expression.
    rhs_expr : Expr
        Right-hand operand expression.
    operator : LogicalOperator
        Logical operator to apply to the evaluated operands.

    Attributes
    ----------
    lhs_expr : Expr
        Left-hand operand expression.
    rhs_expr : Expr
        Right-hand operand expression.
    operator : LogicalOperator
        Logical operator to apply to the evaluated operands.

    Notes
    -----
    - This node is structural only; operand evaluation and short-circuit policy
      are handled downstream.
    - The evaluated result is expected to be boolean-like.
    """
    lhs_expr: Expr
    rhs_expr: Expr
    operator: LogicalOperator


@dataclass(frozen=True)
class UnaryExpr:
    """
    Purpose
    -------
    Represent a unary expression in the DSL. This node exists to apply a unary
    operator to a single operand expression.

    Key behaviors
    -------------
    - Stores the operand expression for the unary operation.
    - Stores the unary operator controlling how the operand is interpreted.

    Parameters
    ----------
    expr : Expr
        Operand expression for the unary operation.
    operator : UnaryOperator
        Unary operator to apply to the evaluated operand.

    Attributes
    ----------
    expr : Expr
        Operand expression for the unary operation.
    operator : UnaryOperator
        Unary operator to apply to the evaluated operand.

    Notes
    -----
    - This node is structural only; operand evaluation and operator semantics
      are handled downstream.
    - Semantic validation should enforce compatible operand types for each
      operator.
    """
    expr: Expr
    operator: UnaryOperator


class ComparisonOperator(str, Enum):
    """
    Purpose
    -------
    Enumerate the legal comparison operators for comparison expressions. This
    enum exists to constrain comparison syntax to a known supported set.

    Key behaviors
    -------------
    - Provides stable symbolic values for binary comparison operations.
    - Prevents arbitrary free-form operator strings from appearing in the AST.

    Parameters
    ----------
    None

    Attributes
    ----------
    GREATER_THAN : ComparisonOperator
        Greater-than comparison operator.
    GREATER_THAN_OR_EQUAL : ComparisonOperator
        Greater-than-or-equal comparison operator.
    EQUAL : ComparisonOperator
        Equality comparison operator.
    LESS_THAN_OR_EQUAL : ComparisonOperator
        Less-than-or-equal comparison operator.
    LESS_THAN : ComparisonOperator
        Less-than comparison operator.
    NOT_EQUAL : ComparisonOperator
        Inequality comparison operator.

    Notes
    -----
    - Enum members inherit from `str` for convenient serialization and display.
    - Downstream evaluation defines operand compatibility and runtime semantics.
    """
    GREATER_THAN = ">"
    GREATER_THAN_OR_EQUAL = ">="
    EQUAL = "=="
    LESS_THAN_OR_EQUAL = "<="
    LESS_THAN = "<"
    NOT_EQUAL = "!="


class UnaryOperator(str, Enum):
    """
    Purpose
    -------
    Enumerate the legal unary operators for unary expressions. This enum exists
    to constrain unary syntax to a known supported set.

    Key behaviors
    -------------
    - Provides stable symbolic values for unary operations.
    - Prevents arbitrary free-form operator strings from appearing in the AST.

    Parameters
    ----------
    None

    Attributes
    ----------
    MINUS : UnaryOperator
        Numeric negation operator.
    NOT : UnaryOperator
        Logical negation operator.

    Notes
    -----
    - Enum members inherit from `str` for convenient serialization and display.
    - Downstream evaluation defines operand compatibility and runtime semantics.
    """
    MINUS = "-"
    NOT = "not"


class LogicalOperator(str, Enum):
    """
    Purpose
    -------
    Enumerate the legal logical operators for logical expressions. This enum
    exists to constrain logical syntax to a known supported set.

    Key behaviors
    -------------
    - Provides stable symbolic values for binary logical operations.
    - Prevents arbitrary free-form operator strings from appearing in the AST.

    Parameters
    ----------
    None

    Attributes
    ----------
    AND : LogicalOperator
        Logical conjunction operator.
    OR : LogicalOperator
        Logical disjunction operator.

    Notes
    -----
    - Enum members inherit from `str` for convenient serialization and display.
    - Downstream evaluation defines operand compatibility and short-circuit
      semantics.
    """
    AND = "and"
    OR = "or"


@dataclass(frozen=True)
class ToolCallStep:
    """
    Purpose
    -------
    Represent a deterministic tool invocation step in the DSL. This node exists
    to describe which registered tool should be called and with what structured
    arguments.

    Key behaviors
    -------------
    - Carries the symbolic tool name used by the runtime registry or dispatch
      layer.
    - Carries structured named arguments as an object expression or `None` when
      no arguments are supplied.

    Parameters
    ----------
    tool_name : str
        Registry-visible name of the tool to invoke.
    args : ObjectExpr | None
        Structured named argument payload for the tool call, or `None` when the
        call takes no arguments.

    Attributes
    ----------
    tool_name : str
        Registry-visible name of the tool to invoke.
    args : ObjectExpr | None
        Structured named argument payload for the tool call, or `None` when the
        call takes no arguments.

    Notes
    -----
    - This class describes a call structurally and does not contain executable
      function objects.
    - Actual dispatch, validation, and side effects are handled by downstream
      runtime code.
    """
    tool_name: str
    args: ObjectExpr | None


@dataclass(frozen=True)
class IfStep:
    """
    Purpose
    -------
    Represent conditional control flow in the DSL. This node exists to choose
    between two ordered step sequences based on the evaluated truth value of an
    expression.

    Key behaviors
    -------------
    - Holds a condition expression that downstream code must evaluate to a
      boolean-like result.
    - Holds ordered step tuples for the true and false branches.

    Parameters
    ----------
    condition : Expr
        Expression whose evaluated value determines which branch is executed.
    then_steps : Tuple[Step, ...]
        Steps to execute when the condition evaluates truthfully.
    else_steps : Tuple[Step, ...]
        Steps to execute when the condition evaluates falsely.

    Attributes
    ----------
    condition : Expr
        Expression whose evaluated value determines which branch is executed.
    then_steps : Tuple[Step, ...]
        Steps to execute when the condition evaluates truthfully.
    else_steps : Tuple[Step, ...]
        Steps to execute when the condition evaluates falsely.

    Notes
    -----
    - This node stores branch structure only and does not perform evaluation by
      itself.
    - Downstream validation should enforce that `condition` is semantically
      usable as a boolean condition.
    """
    condition: Expr
    then_steps: Tuple[Step, ...]
    else_steps: Tuple[Step, ...]


@dataclass(frozen=True)
class ForEachStep:
    """
    Purpose
    -------
    Represent bounded iteration over an iterable expression in the DSL. This
    node exists to bind each iterated element to a loop variable and execute a
    body of steps for each element.

    Key behaviors
    -------------
    - Holds an expression whose runtime value should be iterable.
    - Introduces a loop-scoped binding name for the current iteration element.
    - Holds an ordered body of steps to execute for each element.

    Parameters
    ----------
    iterable_expr : Expr
        Expression whose evaluated value is expected to be iterable.
    loop_var_name : str
        Name introduced into loop scope for the current iteration element.
    body_steps : Tuple[Step, ...]
        Steps to execute for each iterated element.

    Attributes
    ----------
    iterable_expr : Expr
        Expression whose evaluated value is expected to be iterable.
    loop_var_name : str
        Name introduced into loop scope for the current iteration element.
    body_steps : Tuple[Step, ...]
        Steps to execute for each iterated element.

    Notes
    -----
    - This node encodes structural loop semantics only and does not itself
      manage scope or iteration.
    - Downstream runtime code is responsible for enforcing iteration limits and
      loop-scope behavior.
    """
    iterable_expr: Expr
    loop_var_name: str
    body_steps: Tuple[Step, ...]


@dataclass(frozen=True)
class ReturnStep:
    """
    Purpose
    -------
    Represent an explicit return from the current program or subprogram. This
    node exists to mark the expression whose evaluated value should become the
    returned result.

    Key behaviors
    -------------
    - Holds a single expression whose evaluated value is returned by the
      current execution context.
    - Allows downstream interpreter code to terminate the current step sequence
      early once reached.

    Parameters
    ----------
    value_expr : Expr
        Expression whose evaluated value becomes the returned result.

    Attributes
    ----------
    value_expr : Expr
        Expression whose evaluated value becomes the returned result.

    Notes
    -----
    - This node does not itself stop execution; the interpreter implements that
      control-flow effect.
    - Return semantics for nested contexts should be defined by downstream
      runtime code.
    """
    value_expr: Expr


@dataclass(frozen=True)
class LlmCallStep:
    """
    Purpose
    -------
    Represent an explicit LLM-backed subcall in the DSL. This node exists to
    invoke a named BAML function with structured arguments as part of online
    program execution.

    Key behaviors
    -------------
    - Carries the symbolic BAML function name used by the LLM-call dispatch
      layer.
    - Carries structured named arguments as an object expression or `None` when
      no arguments are supplied.

    Parameters
    ----------
    baml_func_name : str
        Name of the BAML function to invoke.
    args : ObjectExpr | None
        Structured named argument payload for the LLM call, or `None` when the
        call takes no arguments.

    Attributes
    ----------
    baml_func_name : str
        Name of the BAML function to invoke.
    args : ObjectExpr | None
        Structured named argument payload for the LLM call, or `None` when the
        call takes no arguments.

    Notes
    -----
    - This node represents an explicit model-backed action and should remain
      distinct from deterministic control-flow nodes.
    - Actual recursion, prompting, and model dispatch are handled downstream by
      the runtime.
    """
    baml_func_name: str
    args: ObjectExpr | None


@dataclass(frozen=True)
class AssignmentStep:
    """
    Purpose
    -------
    Represent a binding operation in the DSL. This node exists to evaluate an
    expression and store its resulting value under a named binding target in
    runtime state.

    Key behaviors
    -------------
    - Holds a value expression to evaluate.
    - Holds the binding target name under which the resulting value should be
      stored.

    Parameters
    ----------
    value_expr : Expr
        Expression whose evaluated value should be assigned.
    binding_target : str
        Name to bind the resulting value to in runtime state.

    Attributes
    ----------
    value_expr : Expr
        Expression whose evaluated value should be assigned.
    binding_target : str
        Name to bind the resulting value to in runtime state.

    Notes
    -----
    - This node does not define scope or rebinding policy by itself.
    - Downstream runtime code must decide whether rebinding is allowed and how
      bindings are stored.
    """
    value_expr: Expr
    binding_target: str


Step: TypeAlias = ToolCallStep | IfStep | ForEachStep | ReturnStep | LlmCallStep | AssignmentStep


Expr: TypeAlias = Literal | Ref | ObjectExpr | ListExpr | ComparisonExpr | LogicalExpr | UnaryExpr


@dataclass(frozen=True)
class Program:
    """
    Purpose
    -------
    Represent the top-level DSL program as an ordered sequence of executable
    steps plus program-level metadata. This class exists to serve as the root
    node consumed by downstream validation and interpreter passes.

    Key behaviors
    -------------
    - Stores the ordered step sequence that defines program execution order.
    - Stores program-level metadata for tracing, configuration, or planner
      annotations.

    Parameters
    ----------
    steps : Tuple[Step, ...]
        Ordered tuple of executable step nodes.
    metadata : Mapping[str, Any]
        Program-level metadata attached to the AST root.

    Attributes
    ----------
    steps : Tuple[Step, ...]
        Ordered tuple of executable step nodes.
    metadata : Mapping[str, Any]
        Program-level metadata attached to the AST root.

    Notes
    -----
    - This class is structural only and does not itself execute steps.
    - Metadata is intentionally unstructured at this layer and should be
      interpreted by downstream code according to project conventions.
    """
    steps: Tuple[Step, ...]
    metadata: Mapping[str, Any]
