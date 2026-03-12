"""
Purpose
-------
Define the expression-layer abstract syntax tree node types and operator enums
used by the REPL DSL. This module exists to give parsers, validators, and
interpreters a shared structural representation for evaluatable expressions.

Key behaviors
-------------
- Defines the `AtomicType` alias for primitive literal values allowed directly
  in expression nodes.
- Defines the `Expr` sum-type alias over all concrete expression node classes.
- Defines enum types for comparison, unary, and logical operators so operator
  syntax is restricted to a known supported set.
- Defines immutable dataclass nodes for literals, references, structured
  objects, lists, binary comparisons, logical expressions, and unary
  expressions.
- Defines both binding references (`Ref`) and task-registry references
  (`TaskRef`) as first-class expression nodes.
- Does not perform evaluation, validation, name resolution, mutation, or any
  side-effecting work.

Conventions
-----------
- Expression nodes are immutable dataclasses and should be treated as
  structural AST descriptions rather than runtime values.
- Atomic literal values are restricted to `int`, `float`, `str`, `bool`, and
  `None` via `AtomicType`.
- Structured expression containers use abstract `Mapping` and tuple-based
  storage so downstream code can rely on stable field names and ordering
  without assuming concrete mutable container types.
- Operator compatibility, short-circuit behavior, and reference resolution are
  defined downstream rather than in this module.
- This module is expression-only and does not define step-level program
  control-flow nodes.

Downstream usage
----------------
Parser or planner code should construct these nodes to represent expression
syntax in the DSL. Validator, interpreter, and execution-layer code should
consume the resulting `Expr` trees to enforce semantic rules, resolve
references, and evaluate expression values in later passes.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Tuple, TypeAlias


AtomicType: TypeAlias = int | float | str | bool | None
Expr: TypeAlias = (
    "Literal"
    | "Ref"
    | "TaskRef"
    | "ObjectExpr"
    | "ListExpr"
    | "ComparisonExpr"
    | "LogicalExpr"
    | "UnaryExpr"
)


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
class TaskRef:
    """
    Purpose
    -------
    Represent a named task-reference expression in the DSL. This node exists
    to look up a previously registered task handle from runtime task state by
    name.

    Key behaviors
    -------------
    - Stores the symbolic name of a task handle to resolve at runtime.
    - Allows expressions and steps to refer to spawned asynchronous work
      tracked in runtime task registry state.

    Parameters
    ----------
    name : str
        Name of the task handle to resolve from runtime task registry.

    Attributes
    ----------
    name : str
        Name of the task handle to resolve from runtime task registry.

    Notes
    -----
    - Resolution semantics are handled by downstream runtime or validation
      passes.
    - This node does not itself guarantee that the referenced task exists.
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
