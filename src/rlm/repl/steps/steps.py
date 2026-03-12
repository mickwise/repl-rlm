"""
Purpose
-------
Define the concrete step-level abstract syntax tree node types used by the REPL
DSL, along with the top-level `Program` root node and the `Step` sum-type alias.
This module exists to represent executable control-flow, action structure, and
first-class concurrency constructs separately from expression nodes.

Key behaviors
-------------
- Defines immutable dataclass node types for tool calls, LLM calls,
  assignments, conditionals, iteration, returns, concurrency operations, and
  whole-program structure.
- Defines the `Step` type family as a sum-type alias over the concrete step
  node classes in this module.
- Uses `Expr` and `ObjectExpr` imported from the expressions layer for step
  fields that carry evaluatable expressions or structured argument payloads.
- Defines the `Program` container as the root node holding ordered steps and
  program-level metadata.

Conventions
-----------
- Step nodes are immutable dataclasses and should be treated as structural AST
  descriptions rather than runtime execution objects.
- Expression node definitions do not live in this module; they are imported
  from `rlm.repl.expressions.expressions` and referenced here by composition.
- Branch bodies, loop bodies, spawned subprograms, and program bodies are
  represented as ordered step structures.
- Program metadata is stored as a generic mapping so downstream planners,
  validators, and runtimes can attach annotations without constraining this
  layer.
- This module does not perform validation, interpretation, dispatch, scope
  management, scheduling, or side-effecting work.

Downstream usage
----------------
Planner or parsing code should construct these step nodes to describe legal DSL
program structure. Validator, resolver, scheduler, and interpreter code should
consume the resulting `Program` and `Step` trees and implement execution
behavior in separate downstream passes.
"""
from __future__ import annotations


from dataclasses import dataclass
from typing import TypeAlias, Tuple, Mapping, Any

from rlm.repl.expressions.expressions import Expr, ObjectExpr, TaskRef

Step: TypeAlias = (
    "ToolCallStep"
    |
    "IfStep"
    |
    "ForEachStep"
    |
    "ReturnStep"
    |
    "LlmCallStep"
    |
    "AssignmentStep"
    |
    "SpawnStep"
    |
    "JoinStep"
)


@dataclass(frozen=True)
class ToolCallStep:
    """
    Purpose
    -------
    Represent a deterministic tool invocation step in the DSL. This node exists
    to describe which registered tool should be called, with what structured
    arguments, and optionally where its result should be bound.

    Key behaviors
    -------------
    - Carries the symbolic tool name used by the runtime registry or dispatch
      layer.
    - Carries structured named arguments as an object expression or `None` when
      no arguments are supplied.
    - Optionally carries a binding target name for storing the tool result in
      runtime state.

    Parameters
    ----------
    tool_name : str
        Registry-visible name of the tool to invoke.
    args : ObjectExpr | None
        Structured named argument payload for the tool call, or `None` when the
        call takes no arguments.
    binding_target : str | None
        Optional runtime binding name under which the tool result should be
        stored.

    Attributes
    ----------
    tool_name : str
        Registry-visible name of the tool to invoke.
    args : ObjectExpr | None
        Structured named argument payload for the tool call, or `None` when the
        call takes no arguments.
    binding_target : str | None
        Optional runtime binding name under which the tool result should be
        stored.

    Notes
    -----
    - This class describes a call structurally and does not contain executable
      function objects.
    - Actual dispatch, validation, binding, and side effects are handled by
      downstream runtime code.
    """
    tool_name: str
    args: ObjectExpr | None
    binding_target: str | None


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
    program execution and optionally bind its result.

    Key behaviors
    -------------
    - Carries the symbolic BAML function name used by the LLM-call dispatch
      layer.
    - Carries structured named arguments as an object expression or `None` when
      no arguments are supplied.
    - Optionally carries a binding target name for storing the LLM result in
      runtime state.

    Parameters
    ----------
    baml_func_name : str
        Name of the BAML function to invoke.
    args : ObjectExpr | None
        Structured named argument payload for the LLM call, or `None` when the
        call takes no arguments.
    binding_target : str | None
        Optional runtime binding name under which the LLM result should be
        stored.

    Attributes
    ----------
    baml_func_name : str
        Name of the BAML function to invoke.
    args : ObjectExpr | None
        Structured named argument payload for the LLM call, or `None` when the
        call takes no arguments.
    binding_target : str | None
        Optional runtime binding name under which the LLM result should be
        stored.

    Notes
    -----
    - This node represents an explicit model-backed action and should remain
      distinct from deterministic control-flow nodes.
    - Actual recursion, prompting, dispatch, and binding are handled downstream
      by the runtime.
    """
    baml_func_name: str
    args: ObjectExpr | None
    binding_target: str | None


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


@dataclass(frozen=True)
class SpawnStep:
    """
    Purpose
    -------
    Represent a first-class concurrency operation that launches a child program
    asynchronously. This node exists to create a task handle that can later be
    joined by downstream concurrency-aware runtime code.

    Key behaviors
    -------------
    - Holds a binding target name under which the spawned task handle should be
      stored in runtime state.
    - Holds a child program that should execute concurrently in a spawned task.

    Parameters
    ----------
    binding_target : str
        Runtime binding name under which the spawned task handle should be
        stored.
    sub_program : Program
        Child program to execute concurrently.

    Attributes
    ----------
    binding_target : str
        Runtime binding name under which the spawned task handle should be
        stored.
    sub_program : Program
        Child program to execute concurrently.

    Notes
    -----
    - This node describes concurrent work structurally and does not itself
      schedule tasks.
    - Downstream runtime code is responsible for child-state handling, task
      creation, and task-table updates.
    """
    binding_target: str
    sub_program: Program


@dataclass(frozen=True)
class JoinStep:
    """
    Purpose
    -------
    Represent a first-class concurrency operation that waits for one or more
    previously spawned tasks to finish. This node exists to provide a fan-in
    synchronization point and optionally bind the collected results.

    Key behaviors
    -------------
    - Holds references to one or more task handles that should be awaited.
    - Optionally holds a binding target name under which the collected task
      results should be stored.

    Parameters
    ----------
    tasks_ref : Tuple[Ref, ...]
        References to task handles that should be joined.
    binding_target : str | None
        Optional runtime binding name under which the collected task results
        should be stored.

    Attributes
    ----------
    tasks_ref : Tuple[Ref, ...]
        References to task handles that should be joined.
    binding_target : str | None
        Optional runtime binding name under which the collected task results
        should be stored.

    Notes
    -----
    - This node does not itself await tasks; downstream runtime code implements
      the actual synchronization semantics.
    - Using a tuple allows one join step to gather multiple task handles at a
      single synchronization point.
    """
    tasks_ref: Tuple[TaskRef, ...]
    binding_target: str | None


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
