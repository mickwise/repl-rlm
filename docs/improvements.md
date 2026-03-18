# Possible Improvements

## Latency

### 1. Conservative dependency-aware async scheduling

The main idea is to let the runtime detect opportunities for concurrency even when the emitted program is more sequential than necessary.

A useful way to think about each step is in terms of:

* **read set**: which bindings or task handles the step depends on
* **write set**: which bindings or task handles the step creates or mutates
* **effect profile**: whether the step is pure, idempotent, externally side-effectful, or unknown

If two steps:

* do not depend on each other's writes,
* do not race on the same mutable state,
* and are safe to reorder,

then the runtime could launch them early and only join when their outputs are actually needed.

This is especially attractive for:

* independent LLM calls,
* pure tool calls,
* long-running read-only subcalls,
* deterministic transformations over already-available data.

#### Best current version of the idea

Implement this conservatively rather than trying to optimize everything automatically.

A practical first version would:

1. annotate tools / LLM-backed functions with metadata such as:

   * `is_pure`
   * `is_idempotent`
   * `safe_to_parallelize`
   * `may_have_external_side_effects`
2. compute read/write sets for each step before execution when possible
3. detect independent pure calls whose inputs are already available
4. eagerly schedule those calls as async tasks
5. continue running unrelated logic
6. await only when a downstream step actually needs the result

This effectively gives the runtime a lightweight task scheduler over the AST.

#### Where this likely helps most

The highest-ROI case is independent sub-LLM calls. Those are likely to dominate latency more than local interpretation overhead.

Examples:

* two independent sub-LLM calls that both depend only on already-bound values
* two pure retrieval-style tool calls over different sources
* multiple spawned subprograms whose outputs are only needed later

#### Guardrails

This should be conservative.

Do **not** auto-parallelize steps that:

* write to external systems,
* cancel / mutate / commit state,
* send user-visible messages,
* depend on implicit ordering,
* or have unknown effect profiles.

Examples of risky categories:

* database writes
* email / notification sending
* booking / cancellation APIs
* payment or account mutations

For those categories, the runtime should preserve explicit program order unless the emitted program itself makes concurrency intentions clear and the tools are marked safe.

#### Potential implementation path

* start with a scheduler that only optimizes pure `ToolCallStep` and pure `LlmCallStep`
* later extend it to spawned subprograms
* only after that consider full DAG scheduling over the step graph

This is likely a real system-level improvement if latency becomes a bottleneck.

---

### 2. Program / template caching with task-to-program translation

The main idea is to avoid planner calls when a previously successful program already matches the current task closely enough.

The strongest form is not exact whole-program caching, but **template reuse**.

Instead of caching only complete programs for exact task matches, cache:

* prior successful task descriptions,
* normalized task signatures,
* successful programs,
* and ideally program templates with slots.

Then, when a new request arrives:

1. translate the task into a normalized retrieval representation
2. retrieve one or more similar prior tasks / program templates
3. adapt or instantiate the candidate program for the current task
4. validate it against the current task and environment
5. if validation succeeds, execute it without paying for a fresh planner call
6. otherwise fall back to ordinary planning

#### Why this is attractive

Many real workloads contain recurring structures:

* cancel a booking
* fetch status of a booking
* roll and compare multiple players
* extract field X and then branch on it
* gather results from several independent subtasks and combine them

Even if surface wording differs, the control structure is often the same.

That means the real challenge is not exact caching. It is the quality of the **task similarity translator**.

#### Best current version of the idea

The strongest current formulation is:

* use a task translator that maps tasks into a canonical similarity space
* retrieve candidate programs or templates from cache
* reuse those candidates only after task-level validation

Task-level validation here means validation against the **actual task**, not just structural AST validation.

That might include:

* checking that the retrieved program's tool usage matches the current task's needs
* checking that required fields / bindings / arguments exist
* checking that the retrieved template can be instantiated safely
* optionally running a light dry-run or simulation when that is cheap

If the translator is good, the expensive validation burden can be lighter.
If the translator is poor, validation has to become stricter.

So the real leverage point is the translator quality.

#### Why template caching is better than exact program caching

Exact task duplication is rare.
Structural reuse is common.

For example:

* "cancel flight AA123"
* "cancel flight UA809"

should ideally hit the same reusable control template, not two unrelated cache entries.

Likewise:

* "roll 1d20 and if above 10 do X"
* "roll 1d20 and if above 12 do Y"

share most of their program structure.

That suggests storing reusable skeletons with parameter slots rather than only frozen full programs.

#### Suggested cache layers

A practical layered design could be:

1. **exact task cache**

   * cheap, high precision
2. **normalized task signature cache**

   * lower precision, higher recall
3. **program template cache**

   * reusable control-flow skeletons with task-specific slots
4. **partial subprogram cache**

   * reusable fragments for common subtasks

#### Risks and guardrails

A cached program can be:

* structurally valid,
* historically successful,
* and still wrong for the current task.

So cache hits should not automatically bypass semantic checks in sensitive domains.

The level of required checking should depend on the tool category:

* low-risk read-only tasks can tolerate lighter checks
* high-risk external actions should require stronger task-level validation

#### Potential implementation path

* begin with exact successful-program caching for read-only tasks
* then add normalized task retrieval
* then move to template caching with slot filling
* only later add cache-aware planner fallback or blended reuse / repair flows

This is likely one of the highest-value latency improvements because it can skip whole planner calls, not just reduce waiting inside one run.

---

### 3. Combined strategy: cached proposal first, async scheduler second

If latency becomes a real problem, the most promising sequence is probably:

1. try task-to-template retrieval first
2. if a strong cached candidate exists, validate and execute it
3. if no strong cached candidate exists, fall back to fresh planning
4. during execution, use conservative async scheduling for pure independent subcalls

This gives two independent wins:

* skip some planner calls entirely
* reduce latency inside runs that still require planning

This combined strategy is likely stronger than either idea alone.

---

### 4. Open questions to revisit later

* how to define read/write sets for all step types cleanly
* how to annotate tool purity and side effects in a maintainable way
* how to represent task similarity for cache retrieval
* whether retrieval should operate over raw task text, normalized metadata, or latent embeddings
* whether cached results should store full programs, templates, or both
* how strong task-level validation needs to be in different domains
* whether certain program fragments should be cached independently of whole programs

---

### 5. Current recommendation

If latency becomes painful, try these in this order:

1. **program/template caching** for recurring tasks
2. **conservative async scheduling** for independent pure calls
3. only later attempt full dependency-DAG optimization over the AST

That order likely gives the best engineering return for the lowest implementation risk.
