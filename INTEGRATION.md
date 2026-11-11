# PySig Dual Calculation Engine Integration

**Status:** Implementation specification\
**Audience:** Developers implementing the dual calculation approach in
PySig\
**Repository:** `ha-mish/PySig`\
**Scope:** Retain the existing time-sliced simulation method and
introduce an analytical, event-driven fluid-queue method selectable
through YAML.

------------------------------------------------------------------------

## 1. Purpose

PySig should support two calculation methods:

1.  **Simulation** --- the existing deterministic, time-sliced queue
    calculation.
2.  **Analytical** --- a deterministic, event-driven fluid-queue
    calculation using exact event boundaries and analytical queue/delay
    integration.

The selected method must be configurable for each model run. Both
methods should accept the same model and demand inputs where their
supported features overlap, and return a common result structure.

The intention is not to force the methods to use the same internal
algorithms. They are mathematically different approaches and should
remain separate calculation engines behind a small, stable interface.

### Design objectives

-   Preserve the existing simulation method and its current behaviour
    during the initial integration.
-   Add the analytical method without making it depend on time-step
    logic.
-   Keep the public PySig entry point as stable as practical.
-   Standardise outputs so reporting and optimisation code do not need
    to know the internal details of each engine.
-   Identify unsupported features explicitly; never silently ignore a
    requested model feature.
-   Make it possible to run comparable cases through both methods for
    validation.

### Non-objectives for the first implementation

The first analytical implementation is not required to reproduce every
existing simulation feature. In particular, advanced shared-lane
allocation, finite link storage, upstream spillback and downstream
interactions may remain simulation-only until separately specified and
validated.

------------------------------------------------------------------------

## 2. Terminology and method behaviour

### 2.1 Simulation method

The current implementation in `traffic_model/simulation.py` is a
deterministic, time-sliced aggregate model. It advances queues in
increments of `network.time_slice_s`.

Current behaviour includes, among other things:

-   adding arrivals during each time slice;
-   evaluating signal permission at the start of each time slice;
-   allocating service to eligible movements;
-   applying lane/link storage constraints;
-   accumulating queue-area delay using the post-step queue.

This method should initially be retained rather than rewritten as part
of the analytical work. Any changes required to place it behind the
common interface should be structural only, unless a separate bug fix is
agreed and tested.

The current method is not individual-vehicle microsimulation. It is an
aggregate deterministic simulation.

### 2.2 Analytical method

The analytical method represents demand, signal service and queues as
continuous functions over time. It should calculate queue changes at
exact event boundaries rather than advancing in arbitrary fixed time
increments.

The initial analytical kernel should support:

-   deterministic demand;
-   piecewise-constant arrival rates;
-   constant saturation flow over each service interval;
-   fixed-time signal service intervals;
-   queue growth and dissipation;
-   queue-clearance events;
-   exact integration of queue area and delay;
-   queue continuity across consecutive analysis periods.

Piecewise-linear demand can be added after the constant-rate kernel is
validated.

The analytical method is a fluid-queue model. Queue values may be
fractional PCU; it does not track individual vehicles.

------------------------------------------------------------------------

## 3. YAML configuration

Add a top-level `calculation` section.

``` yaml
calculation:
  method: simulation  # simulation | analytical

network:
  horizon_s: 3600
  warm_up_s: 0

  # Used by the simulation method only.
  time_slice_s: 1.0
```

Valid method values:

-   `simulation`
-   `analytical`

### Configuration rules

1.  For backward compatibility, configurations that omit
    `calculation.method` must continue to select `simulation` during the
    migration period.
2.  An unknown method must raise a clear configuration error listing the
    valid values.
3.  `time_slice_s` is required only by the simulation method. Existing
    validation should be retained for simulation runs.
4.  The analytical engine must not use `time_slice_s` to approximate
    queue evolution.
5.  Method-specific settings should be validated by the selected engine,
    not scattered throughout unrelated modules.
6.  The selected method must be included in output metadata.

Example analytical configuration:

``` yaml
calculation:
  method: analytical

network:
  horizon_s: 7200
  warm_up_s: 0
```

Demand-profile and analysis-period YAML formats should be designed as a
separate, backward-compatible extension. Do not make the initial
engine-selection change depend on completing the full time-dependent
demand schema. Initially, existing scalar movement flows can be
interpreted as constant demand over the model horizon.

------------------------------------------------------------------------

## 4. Target architecture

Introduce a calculation package containing the common interface and the
two engine implementations.

Suggested structure:

``` text
traffic_model/
    calculation/
        __init__.py
        base.py
        factory.py
        results.py
        analytical/
            __init__.py
            engine.py
            demand.py
            signals.py
            events.py
            queue.py
            delay.py
        simulation/
            __init__.py
            engine.py
    simulation.py          # compatibility facade, if needed
    domain.py
    loader.py
    assignment.py
    timing.py
    output.py
    optimisation.py
```

This is a proposed organisation, not a requirement to move every
existing file immediately. In particular, avoid a large unrelated
refactor. The existing simulation code can initially be wrapped by
`calculation/simulation/engine.py` and moved later if that reduces risk.

### 4.1 Common engine interface

Both engines should implement the same conceptual interface:

``` python
class CalculationEngine:
    def calculate(
        self,
        model,
        movement_flows,
        controllers=None,
    ):
        ...
```

Use a `Protocol` or abstract base class according to existing project
conventions. The interface should be typed and documented.

The common interface should receive domain objects, not raw YAML
dictionaries. YAML parsing and validation belong in the
loader/configuration layer.

### 4.2 Engine factory

The factory should be the only place that maps the configuration value
to a concrete engine.

``` python
def create_calculation_engine(method: str) -> CalculationEngine:
    if method == "analytical":
        return AnalyticalEngine()

    if method == "simulation":
        return SimulationEngine()

    raise ValueError(
        f"Unknown calculation method {method!r}. "
        "Expected 'analytical' or 'simulation'."
    )
```

Adapt naming and error types to existing project conventions.

### 4.3 Public entry point and compatibility

Keep the existing public
`simulate(model, movement_flows, controllers=None)` entry point working
during the transition.

Preferred approach:

-   Introduce a new orchestration function, such as `calculate(...)`,
    which selects the configured engine.
-   Keep `simulate(...)` as a compatibility wrapper for the existing
    simulation behaviour, unless repository usage indicates that it is
    safe and appropriate to change its semantics.
-   Update internal callers to use the new orchestration path.
-   Do not silently change existing callers from simulation to
    analytical merely because a new default has been introduced.

The exact API decision should be confirmed by inspecting imports and
call sites, including optimisation and tests, before implementation.

------------------------------------------------------------------------

## 5. Common result contract

Reporting, export and optimisation should consume common result objects
rather than engine-specific internal structures.

The common result contract should preserve existing fields where
possible. Avoid breaking the current `MovementResult`, `LaneResult` and
output schema unnecessarily.

At minimum, the common result should make the following information
available where applicable:

### Movement-level results

-   movement identifier;
-   initial queue;
-   total arrivals;
-   total departures;
-   final queue;
-   maximum queue;
-   total queue-area delay;
-   average queue over the analysis duration;
-   a clearly defined average delay measure;
-   analysis duration;
-   method and methodology metadata.

### Period-level results

The analytical method must support results by analysis period:

``` python
@dataclass(frozen=True, slots=True)
class PeriodResult:
    period_id: str
    start_s: float
    end_s: float
    initial_queue_pcu: float
    arrivals_pcu: float
    departures_pcu: float
    final_queue_pcu: float
    maximum_queue_pcu: float
    average_queue_pcu: float
    total_delay_pcu_seconds: float
```

The exact types and location of these dataclasses should follow existing
project conventions. This example is a design illustration, not a
requirement to duplicate an existing type.

### Methodology metadata

Every result set should identify its calculation method. For example:

``` json
{
  "calculation_method": "analytical",
  "queue_model": "deterministic_analytical_fluid_queue",
  "time_resolution": "event_driven",
  "delay_method": "analytical_queue_integration"
}
```

For the existing simulation, use accurate metadata describing its actual
time-sliced calculation. Do not retain metadata such as
`fifo_composition` as a claim of literal vehicle FIFO unless the
implementation genuinely models that behaviour.

If the output schema changes, update its schema version and document the
change. Preserve old output compatibility where practical.

### Delay definitions

The result contract must distinguish:

-   **Total queue-area delay:** (`\int `{=tex}Q(t),dt), in PCU-seconds
    (or converted PCU-hours).
-   **Average queue:** total queue area divided by elapsed analysis
    duration.
-   **Average delay per arrival:** total queue-area delay divided by
    arrivals, only where that definition is appropriate and clearly
    labelled.
-   **Residual queue:** vehicles/PCU still queued at the end of the
    analysis.

Do not label queue-area delay divided by departures as an unconditional
mean delay when a residual queue remains. The treatment of vehicles
still queued at the end must be explicit.

Queue-area delay is not automatically the same as total control delay.
Deceleration, acceleration and other delay components should not be
added without a defined methodology that avoids double counting.

------------------------------------------------------------------------

## 6. Analytical engine requirements

### 6.1 Demand

Initially, support constant movement flow rates over the analysis
horizon. Convert the existing scalar flow representation to a consistent
internal rate, preferably PCU/s.

For a constant rate (a):

\[ A(t_0,t_1)=a(t_1-t_0) \]

The next extension should support piecewise-constant demand segments. A
later extension may support piecewise-linear demand.

Demand must be represented independently of the queue algorithm. This
allows both engines to consume the same demand input even though they
process it differently.

### 6.2 Signal service intervals

The analytical engine must obtain explicit service intervals for each
movement or signal group.

Add a signal-timing function with a contract similar to:

``` python
get_service_intervals(
    controller,
    signal_group_id,
    start_s,
    end_s,
) -> list[tuple[float, float]]
```

The function should return exact permitted intervals clipped to the
requested analysis window.

Requirements:

-   Handle cycles that begin before the analysis start.
-   Handle intervals that cross the analysis end.
-   Handle offsets and phase transitions correctly.
-   Respect effective green and clearance conventions already used by
    PySig.
-   Avoid duplicating signal timing logic in the queue solver.
-   Test boundary instants and cycle wrap-around.

The analytical engine must not determine signal permission once per
arbitrary time slice.

### 6.3 Queue dynamics

For a movement with arrival rate (a(t)) and available service rate
(`\mu`{=tex}(t)), the queue is non-negative.

When the queue is positive:

\[ `\frac{dQ}{dt}`{=tex}=a(t)-`\mu`{=tex}(t) \]

When the queue is zero, unused service capacity cannot create a negative
queue. The queue remains zero when service exceeds demand and begins to
grow only when arrivals exceed service.

For constant arrival and service rates over an interval, queue evolution
is linear until a queue-clearance or other event occurs.

If (`\mu`{=tex}\>a) and the initial queue is (Q_0\>0), the
queue-clearance time is:

\[ t\_{`\mathrm{clear}`{=tex}}=`\frac{Q_0}{\mu-a}`{=tex} \]

The solver must split the interval at this event. After clearance, queue
remains zero unless subsequent demand exceeds service.

The solver must also handle:

-   a queue growing during red;
-   a queue dissipating during green;
-   a queue that does not clear during green;
-   a queue that clears part-way through green;
-   demand or service changes at an interval boundary;
-   a queue carried into the next analysis period.

Do not implement the analytical method by choosing a very small time
step. That would simply create a second simulation method.

### 6.4 Event-driven solution

The analytical engine should split the horizon at all points where the
governing rates or conditions can change, including:

-   demand segment boundaries;
-   signal service start and end times;
-   analysis-period boundaries;
-   queue-clearance events;
-   any future saturation-flow or control changes.

Within each resulting interval, use the applicable closed-form queue
evolution and integrate queue area exactly.

For a linear queue changing from (Q_0) to (Q_1) over an interval of
duration (`\Delta `{=tex}t):

\[ D=`\frac{Q_0+Q_1}{2}`{=tex}`\Delta `{=tex}t \]

This is exact when queue evolution is linear throughout that interval.

If piecewise-linear demand is introduced, queue evolution may be
quadratic within an event interval. Integrate that polynomial exactly
and check any internal stationary point when calculating maximum queue.

### 6.5 Conservation

For every movement and analysis period, validate:

\[ Q\_{`\mathrm{end}`{=tex}} = Q\_{`\mathrm{start}`{=tex}} + A - D \]

where (A) is admitted demand and (D) is departures.

The initial analytical implementation should not discard arrivals
because of finite storage. Until upstream blocking/spillback is
implemented analytically, storage exceedance should be reported as a
limitation or validation condition rather than silently dropping demand.

### 6.6 Multiple periods

Queues must carry between consecutive analysis periods:

\[ Q\_{i+1,0}=Q\_{i,`\mathrm{end}`{=tex}} \]

The queue must not be reset at a period boundary unless an explicit
reset is part of the model specification.

The period result should report initial and final queue, arrivals,
departures, maximum queue, average queue and queue-area delay.

------------------------------------------------------------------------

## 7. Simulation engine requirements

The simulation engine should initially preserve the existing
implementation and results.

Tasks:

1.  Wrap the existing `simulate()` calculation in the common engine
    interface.
2.  Preserve current shared-lane, storage and link-receiving behaviour.
3.  Preserve existing time-slice configuration and validation.
4.  Map existing outputs into the common result contract.
5.  Record accurate method metadata.
6.  Keep existing simulation tests passing.

Do not refactor the simulation algorithm at the same time as introducing
the analytical kernel unless a change is essential to establish the
interface. This separation makes regressions easier to identify.

------------------------------------------------------------------------

## 8. Feature capability checks

The engines will not necessarily support the same features. Make this
explicit.

Introduce a capability declaration or validation mechanism. For example:

``` python
class AnalyticalEngine:
    capabilities = {
        "constant_demand": True,
        "piecewise_constant_demand": True,
        "piecewise_linear_demand": False,
        "fixed_time_signals": True,
        "shared_lane_interactions": False,
        "finite_storage": False,
        "upstream_spillback": False,
    }
```

The exact mechanism may be a typed capability object rather than a
dictionary.

Before calculation, validate the model against the selected engine's
capabilities. If a model requests an unsupported feature, raise a clear,
actionable error. Include the feature and selected method in the
message.

Do not silently:

-   ignore finite storage;
-   treat a shared lane as independent lanes;
-   drop rejected arrivals;
-   omit a demand profile;
-   simplify a controller without telling the user.

As analytical capabilities are implemented and tested, update the
declarations and documentation.

------------------------------------------------------------------------

## 9. Integration with existing modules

### `traffic_model/domain.py`

-   Add the calculation method setting to the model/configuration
    domain.
-   Keep `time_slice_s` available for simulation.
-   Introduce analysis-period and demand-profile domain objects in a way
    that does not break existing scalar-flow inputs.
-   Use immutable dataclasses if consistent with current conventions.

Possible future types:

``` python
@dataclass(frozen=True, slots=True)
class AnalysisPeriod:
    period_id: str
    start_s: float
    end_s: float
```

``` python
@dataclass(frozen=True, slots=True)
class DemandSegment:
    start_s: float
    end_s: float
    start_flow_pcu_per_hour: float
    end_flow_pcu_per_hour: float
```

Initially, scalar movement flows should be interpreted as constant over
the model horizon. Do not require users to provide profiles until the
profile schema is ready.

### `traffic_model/loader.py`

-   Parse and validate `calculation.method`.
-   Default to simulation when the setting is absent.
-   Validate method-specific configuration.
-   Preserve existing YAML examples and tests.
-   Add examples for both methods.

### `traffic_model/assignment.py`

-   Keep assignment and calculation engine responsibilities separate.
-   Initially, continue to produce scalar movement flows as today.
-   Pass those flows to the selected engine.
-   Later, support demand profiles without embedding queue logic in
    assignment.

### `traffic_model/timing.py`

-   Retain existing timing functionality needed by simulation.
-   Add exact service-interval generation for analytical calculations.
-   Avoid changing simulation signal behaviour as an incidental
    consequence of adding the analytical API.

### `traffic_model/output.py`

-   Map both engines to a common reporting structure.
-   Include method metadata.
-   Add period-level results when available.
-   Clarify delay and residual-queue definitions.
-   Update CSV/JSON output and schema versioning as required.

### `traffic_model/optimisation.py`

-   Inspect all calls to `simulate()` and all assumptions about result
    fields.
-   Route optimisation runs through the configured calculation method
    where appropriate.
-   Ensure the objective function consumes common result fields.
-   Do not assume both methods support every optimisation feature.
-   Add tests to ensure optimisation still works in simulation mode and
    can use analytical mode for supported cases.

### `traffic_model/engine.py`

This appears to be an older or alternative engine. Before modifying it,
establish whether it is imported or used by current execution paths.
Avoid maintaining multiple competing queue implementations. Document its
status and either leave it untouched or plan a separate
deprecation/removal change.

------------------------------------------------------------------------

## 10. Testing and validation

Testing should establish both backward compatibility and analytical
correctness.

### 10.1 Preserve existing tests

Run the complete existing test suite before changes and record the
baseline.

Retain and adapt existing tests, particularly:

-   `tests/test_shared_lane_kernel.py`
-   `tests/test_outputs.py`
-   `tests/test_signal_timing.py`
-   `tests/test_core.py`

Simulation results should not change as a result of the initial
integration, except for separately documented and approved bug fixes.

### 10.2 Configuration tests

Test:

-   explicit `simulation` selection;
-   explicit `analytical` selection;
-   missing method defaults to simulation;
-   invalid method produces a clear error;
-   simulation time-step validation remains in force;
-   analytical calculation does not depend on the simulation time step.

### 10.3 Analytical kernel tests

Create focused tests for:

-   zero demand and zero initial queue;
-   demand below service with no queue;
-   demand above service and queue growth;
-   queue dissipation during service;
-   queue clearing part-way through a service interval;
-   queue not clearing before the end of green;
-   red/green transitions;
-   signal cycle wrap-around;
-   demand changes at interval boundaries;
-   exact queue-area integration;
-   maximum queue;
-   residual queue at the end of the horizon;
-   queue continuity between consecutive periods;
-   vehicle/PCU conservation.

Use small hand-calculated examples with exact expected values. These
tests should not rely solely on comparing the analytical engine to the
existing simulation, because the simulation itself may have time-step
approximation error.

### 10.4 Cross-method comparison tests

For cases supported by both methods:

1.  Build a simple single-movement or independent-movement scenario.
2.  Use identical demand, saturation flow and signal timing.
3.  Run the analytical engine.
4.  Run the simulation engine at progressively smaller time steps.
5.  Compare arrivals, departures, final queue, maximum queue and total
    queue-area delay.
6.  Confirm the simulation converges towards the analytical result
    within a documented tolerance.

Do not expect exact equality at finite time-step sizes. Differences may
arise from time discretisation and the existing simulation's boundary
handling.

### 10.5 Benchmark and reference tests

Where suitable, compare selected cases against hand calculations and
published analytical examples. Any comparison with Akçelik, Austroads,
HCM or other methods must identify differences in assumptions and delay
definitions. Do not claim equivalence merely because two outputs have
similar names.

------------------------------------------------------------------------

## 11. Recommended implementation sequence

Deliver this as a series of small, reviewable changes.

### Phase 0 --- Baseline and code-path audit

-   Run the existing test suite.
-   Identify all callers of `simulate()`.
-   Inspect optimisation and output dependencies.
-   Confirm whether `engine.py` is active or legacy.
-   Record representative simulation outputs for regression comparison.

**Deliverable:** baseline test report and a short map of current
calculation call paths.

### Phase 1 --- Engine selection and simulation wrapper

-   Add `calculation.method` to configuration.
-   Add the common engine interface and factory.
-   Wrap the existing simulation calculation without changing its
    algorithm.
-   Route the main execution path through the factory.
-   Preserve the old public API as a compatibility facade where needed.
-   Add configuration and regression tests.

**Deliverable:** both configuration values can be selected, with
simulation still behaving as before. Analytical selection may initially
return a clear "not yet implemented" error until Phase 2 is complete.

### Phase 2 --- Analytical constant-rate queue kernel

-   Implement constant demand and service intervals.
-   Implement queue growth and dissipation.
-   Split intervals at queue-clearance events.
-   Integrate queue area exactly.
-   Calculate maximum and residual queue.
-   Validate conservation.
-   Add hand-calculated unit tests.

**Deliverable:** a tested analytical kernel independent of the existing
simulation time-step logic.

### Phase 3 --- Analytical signal integration

-   Generate exact signal service intervals.
-   Handle cycle offsets and analysis-window boundaries.
-   Connect signal intervals to the queue kernel.
-   Test red/green transitions and cycle wrap-around.

**Deliverable:** analytical calculations for fixed-time signal control.

### Phase 4 --- Common outputs and application integration

-   Map analytical results into the common result contract.
-   Add method metadata and period-level results.
-   Integrate with reporting and exports.
-   Update optimisation to use the common result contract.
-   Add cross-method comparison tests.

**Deliverable:** end-to-end analytical and simulation runs from YAML.

### Phase 5 --- Time-dependent demand and expanded analytical features

-   Add piecewise-constant demand profiles.
-   Add consecutive analysis periods and queue carry-over.
-   Add piecewise-linear demand if justified.
-   Design and implement analytical shared-lane treatment.
-   Add storage and upstream interaction only with a defined analytical
    formulation.

**Deliverable:** expanded analytical functionality, with capability
checks updated as features become supported.

------------------------------------------------------------------------

## 12. Acceptance criteria

The dual-method integration is complete when all of the following are
true:

1.  A user can select `simulation` or `analytical` in YAML.
2.  An omitted method continues to select simulation for backward
    compatibility.
3.  The existing simulation method remains available and its regression
    tests pass.
4.  The analytical engine is independent of fixed time-step queue
    advancement.
5.  Both engines implement the common calculation interface.
6.  Both engines return compatible core result structures for supported
    outputs.
7.  Results identify the method and relevant calculation methodology.
8.  Unsupported analytical features produce clear validation errors.
9.  Analytical queue and delay calculations pass hand-calculated tests.
10. Queue conservation and period-to-period queue continuity are tested.
11. Comparable cases can be run through both methods and compared.
12. Reporting and optimisation use the common result contract rather
    than relying on engine-specific internals.

------------------------------------------------------------------------

## 13. Implementation cautions

-   **Do not rewrite both engines simultaneously.** First wrap and
    preserve the simulation method.
-   **Do not make the analytical method a small-time-step simulation.**
    Its defining feature is event-driven, exact interval calculation.
-   **Do not force feature parity prematurely.** Explicitly identify
    which method supports each feature.
-   **Do not conflate queueing delay and control delay.** Keep the
    metric definitions explicit.
-   **Do not hide residual queues.** Report them and define how average
    delay is calculated.
-   **Do not discard arrivals to make storage constraints fit.** Storage
    and spillback need a coherent treatment.
-   **Do not make assignment responsible for queue evolution.**
    Assignment supplies demand; the selected engine calculates
    performance.
-   **Do not make output consumers depend on engine internals.** Use the
    common result contract.
-   **Do not change the existing simulation's numerical behaviour during
    structural integration without dedicated tests and an explicit
    decision.**

------------------------------------------------------------------------

## 14. Summary of the design decision

PySig should use a **dual-engine architecture**:

-   YAML selects the calculation method.
-   A factory constructs the selected engine.
-   Both engines implement a common calculation interface.
-   Both engines return a common result contract and identify their
    methodology.
-   The simulation engine initially retains existing time-sliced
    behaviour.
-   The analytical engine is developed independently as an event-driven
    fluid-queue solver.
-   Capability checks prevent unsupported features from being silently
    misrepresented.

This approach preserves the existing PySig functionality while creating
a clean foundation for analytical queue modelling, time-dependent demand
and future comparison/validation between calculation methods.
